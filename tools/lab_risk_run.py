"""Risk-manager lab: compare the sizing policies in engine/risk_policy.py on recorded trade sequences (MFFU Builder 50K).

For every trade sequence x policy:
  1. CHRONO   the real day order: evals back-to-back (a new eval starts the day after a pass or fail), days to pass,
              max drawdown of the continuous equity path; plus the rolling pass rate (a fresh eval started on every
              day, as engine/analytics.rolling_evals does).
  2. BOOT     day-block bootstrap Monte Carlo: whole trading days (no-trade days included, intraday trade order kept)
              resampled with replacement, 5,000 runs x 60 trading days. P(pass), P(fail), median days to pass.
              ZERO-EDGE: the same runs with every trade's R de-meaned (r - mean r of the sequence), same stops.
              HALF-EDGE (engine sequences): r - 0.5 x mean r.
              All policies share the same random day draws (common random numbers), so differences between policies
              are not sampling noise between runs.
Re-sizing: each file's P&L already includes costs, and costs are per micro (commission + ticks of slippage), so P&L
per micro = pnl / qty is size-invariant; new P&L = new qty x that. Worst open P&L per micro = MAE (capped at the
stop) from the file. Day rules, the trailing MLL and the soft daily limit come from engine/risk_policy.EvalAccount.

    python tools/lab_risk_run.py                 # full run (~20 min) -> research/lab/RISK_results.json + RISK_tables.md
    python tools/lab_risk_run.py --chain         # + one-year "buy a new eval after each fail" chains (~6 min)
    python tools/lab_risk_run.py --summary       # RISK_tables.md, RISK_summary.md, RISK_report_tables.md
    python tools/lab_risk_run.py --only ATM      # re-run some sequences (prefixes), keep the rest of the results
    python tools/lab_risk_run.py --add P0_500 --only ENGINE   # add policies to sequences already in the results
    python tools/lab_risk_run.py --quick         # 1,000 runs, engine sequences only (smoke test)
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import os
import statistics
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.risk_policy import POLICIES, EvalAccount, dead_threshold, size  # noqa: E402

LAB = os.path.join(ROOT, "research", "lab")
FIVE = os.path.join(ROOT, "research", "five_year", "run_live_nograde_max1.json")
SLIP = 0.25   # strategy_lab modules size on stop + 1 tick of entry slippage

# "REC" = the file's own recorded quantities (the engine's internal sizing), a cross-check against the leaderboard
ENGINE_POLICIES = ["REC"] + [p for p in POLICIES if p != "RECOMMENDED"]
OTHER_POLICIES = ["P0", "P0g", "P0_500", "P1", "P1g", "P1b", "P2f_k35", "P3_30w", "P4a", "P4b1", "P5_f_c35_f1",
                  "P5_f_c35_w30", "P5_f_c35_w30_f1", "P5_1b_c35_f1", "P5_t_c_d_f2"]
NARR_POLICIES = ["P0g", "P1", "P1g", "P1b", "P2_k35", "P5_1b_c35_f1", "P5_t_c_d_f2"]
REGIME_POLICIES = ["P1g", "P2_k35"]
# "buy a new eval after each fail" chains (one trading year) for the shortlist
CHAIN_POLICIES = ["P0", "P0g", "P0_500", "P1", "P1g", "P1b", "P2f_k35", "P2_k35", "P3_30w", "P4b1", "P5_f_c35_f1",
                  "P5_f_c35_w30_f1", "P5_f_c35_w30"]
POLICY_NAMES = {**{k: v["name"] for k, v in POLICIES.items()}, "REC": "as recorded (engine's own sizing)"}
# shortlist that also gets a 250-trading-day horizon ("eventual" pass odds, no 60-day cut-off)
LONG_POLICIES = ["REC", "P0", "P0g", "P0_500", "P1", "P1b", "P2f_k35", "P3_30w", "P4b1", "P5_f_c35_f1",
                 "P5_f_c35_w30", "P5_f_c35_w30_f1", "P5_1b_c35_f1"]


# ------------------------------------------------------------------------------------------------ sequences
def _boot_ci(x, n=4000, seed=7):
    x = np.asarray(x, float)
    if len(x) < 5:
        return [None, None]
    m = x[np.random.default_rng(seed).integers(0, len(x), (n, len(x)))].mean(1)
    return [round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)]


def _norm_engine(t):
    """Liquidity Engine trade: qty micros, risk_pts = sizing stop, mae in R units."""
    q = t["qty"]
    rp = float(t["risk_pts"])
    unit = rp * 2.0
    mae_pm = min(float(t.get("mae") or 0.0), 1.0) * unit
    return {"day": t["day"], "t": t["entry_t"], "grade": t.get("grade"), "stop": rp, "unit": unit,
            "ppm": t["pnl"] / q, "mae_pm": mae_pm, "r": float(t["r"]), "qty0": q,
            "plan_r": (t.get("f") or {}).get("rr_plan"), "regime": t.get("regime")}


def _norm_lab(t, pv):
    """strategy_lab rule-module trade: qty micros, risk_pts = |entry - stop|, mae_usd at the file's qty."""
    q = t["qty"]
    rp = float(t["risk_pts"])
    unit = rp * pv
    mae_pm = min(abs(float(t.get("mae_usd") or 0.0)) / q, unit) if q else 0.0
    plan = None
    if t.get("target") is not None and rp > 0:
        plan = abs(t["target"] - t["entry"]) / rp
    return {"day": t["day"], "t": t["entry_t"], "grade": t.get("tier"), "stop": rp + SLIP, "unit": unit,
            "ppm": t["pnl"] / q, "mae_pm": mae_pm, "r": float(t["r"]), "qty0": q, "plan_r": plan,
            "exit_t": t.get("exit_t")}


def make_seq(name, family, period, cal, trades, pv=2.0, graded=False, note=""):
    cal = sorted(cal)
    calset = set(cal)
    trades = sorted([t for t in trades if t["day"] in calset], key=lambda t: t["t"])
    rs = [t["r"] for t in trades]
    mean_r = statistics.mean(rs) if rs else 0.0
    by_day = collections.defaultdict(list)
    overlap = 0
    for t in trades:
        lst = by_day[t["day"]]
        if lst and lst[-1].get("exit_t") and t["t"] < lst[-1]["exit_t"]:
            overlap += 1
        # edge variants: 0 = as recorded, 1 = zero edge (R de-meaned), 2 = half edge
        t["ppm_e"] = (t["ppm"], t["ppm"] - mean_r * t["unit"], t["ppm"] - 0.5 * mean_r * t["unit"])
        lst.append(t)
    pool = [[(t["grade"], t["stop"], t["ppm_e"], t["mae_pm"], t["qty0"]) for t in by_day.get(d, [])] for d in cal]
    weeks = len(cal) / 5.0
    gr = collections.defaultdict(list)
    for t in trades:
        gr[str(t["grade"])].append(t["r"])
    return {"name": name, "family": family, "period": period, "start": cal[0], "end": cal[-1], "sessions": len(cal),
            "cal": cal, "pool": pool, "trades": trades, "n": len(trades), "tpw": round(len(trades) / weeks, 2),
            "avg_r": round(mean_r, 3), "ci95_r": _boot_ci(rs), "sum_r": round(sum(rs), 1),
            "pf": _pf([t["ppm"] * t["qty0"] for t in trades]), "pv": pv, "graded": graded, "overlap": overlap,
            "multi_days": sum(1 for v in by_day.values() if len(v) > 1), "note": note,
            "stop_med": round(statistics.median([t["stop"] for t in trades]), 1) if trades else None,
            "by_grade": {g: {"n": len(v), "avg_r": round(statistics.mean(v), 3)} for g, v in sorted(gr.items())}}


def _pf(p):
    gp = sum(x for x in p if x > 0)
    gl = -sum(x for x in p if x < 0)
    return round(gp / gl, 2) if gl > 0 else None


def load_sequences(include_es=False, min_trades=20):
    seqs = []
    cb = json.load(open(os.path.join(LAB, "conf_testbed_orig1day.json")))
    cal = {k: [d["date"] for d in cb[k]["days"]] for k in ("ytd", "y2025")}
    for k, label in (("ytd", "2026"), ("y2025", "2025")):
        seqs.append(make_seq("ENGINE_orig1day", "engine", label, cal[k], [_norm_engine(t) for t in cb[k]["trades"]],
                             graded=True, note="current live pick (conf_testbed_orig1day.json)"))
    narr = os.path.join(LAB, "NARRATIVE_trades.json")
    if os.path.exists(narr):    # the trader-brain grades (v1, v2) for the same engine trades
        nd = json.load(open(narr))
        for bed, k, label in (("bed26", "ytd", "2026"), ("bed25", "y2025", "2025")):
            gm = {}
            for x in nd.get(bed, []):
                for v in ("v1", "v2"):
                    gm[(v, x["entry_t"], x["dir"])] = ((x.get("ver") or {}).get(v) or {}).get("grade")
            for v in ("v1", "v2"):
                trs = []
                for t in cb[k]["trades"]:
                    n = _norm_engine(t)
                    n["grade"] = gm.get((v, t["entry_t"], t["dir"]))
                    trs.append(n)
                seqs.append(make_seq(f"NARR_{v}_orig1day", "narrative", label, cal[k], trs, graded=True,
                                     note=f"engine trades graded by the trader brain {v} (NARRATIVE_trades.json); "
                                          f"SKIP = not traded by tier policies"))
    if os.path.exists(FIVE):
        fy = json.load(open(FIVE))
        c5 = [d["date"] for d in fy["days"] if d["date"] < "2026-01-01"]
        t5 = [_norm_engine(t) for t in fy["trades"] if t["day"] < "2026-01-01"]
        seqs.append(make_seq("ENGINE_orig1day", "engine", "2021-25", c5, t5, graded=True,
                             note="same config, five-year live-loop replay (research/five_year/run_live_nograde_max1.json)"))
    # the engine's own confidence signal: trending regime = C (half size), rotational = B
    for s in [s for s in seqs if s["family"] == "engine"]:
        cal_s = s["cal"]
        src = (cb["ytd"]["trades"] if s["period"] == "2026" else cb["y2025"]["trades"] if s["period"] == "2025"
               else [t for t in json.load(open(FIVE))["trades"] if t["day"] < "2026-01-01"])
        trs = []
        for t in src:
            n = _norm_engine(t)
            n["grade"] = "C" if n["regime"] == "trending" else "B"
            trs.append(n)
        seqs.append(make_seq("REGIME_orig1day", "regime", s["period"], cal_s, trs, graded=True,
                             note="engine trades graded by regime: trending = C ($175), rotational = B ($350)"))
    files = []
    for pat in ("SB_trades_*.json", "MECH_trades_*.json", os.path.join("M22_trades", "*.json"),
                os.path.join("CONT_trades", "*.json"), "ATM_trades_*.json"):
        files += sorted(glob.glob(os.path.join(LAB, pat)))
    for f in files:
        base = os.path.basename(f).replace(".json", "")
        sym = "ES" if "_ES_" in base else "NQ"
        if sym == "ES" and not include_es:
            continue
        if base.startswith("ATM_trades_") and base.endswith("_flat"):
            continue      # the _tier and _flat ATM files hold the same trades; keep _tier (it carries the grade)
        name = base.replace("_trades", "")
        pv = 5.0 if sym == "ES" else 2.0
        raw = json.load(open(f))
        if isinstance(raw, dict):       # newer files: {"variant", "sizing", "note", "trades": [...]}
            raw = raw.get("trades") or []
        tr = [_norm_lab(t, pv) for t in raw if isinstance(t, dict) and t.get("qty") and t.get("exit_kind") != "open"]
        graded = any(t["grade"] for t in tr)
        s = make_seq(name, name.split("_")[0], "2026", cal["ytd"], tr, pv=pv, graded=graded,
                     note=f"{sym} {os.path.relpath(f, LAB)}")
        if s["n"] >= min_trades:
            s["mtime"] = os.path.getmtime(f)
            seqs.append(s)
    return seqs


# ------------------------------------------------------------------------------------------------ simulation
def _cfg(policy, seq):
    if policy == "REC":
        return None
    c = POLICIES[policy]
    if seq["pv"] != 2.0:
        c = {**c, "point_value": seq["pv"]}
    return c


def run_eval(days, cfg, ei, thr=0.0, acct=None, path=None):
    """One eval over an iterable of per-day trade lists. cfg None = recorded quantities.
    thr = dead-account cushion (risk_policy.dead_threshold at the sequence's median stop): an account whose cushion
    is below it can no longer trade a normal setup and counts as failed ("dead").
    Returns (status, days, taken, skip_wide, skip_guard, risk)."""
    acct = acct or EvalAccount()
    taken = sw = sg = 0
    risk = 0.0
    for trades in days:
        if thr and acct.balance - acct.mll < thr:
            acct.mark_dead()
            break
        for g, stop, ppm_e, mae_pm, q0 in trades:
            if cfg is None:
                q = q0
                risk += q0 * stop * 2.0
            else:
                dec = size(g, stop, acct.account_state(), acct.day_state(), cfg)
                q = dec["qty_micros"]
                if not q:
                    code = dec["code"]
                    if code == "too_wide":
                        sw += 1
                    elif code == "guard":
                        sg += 1
                    continue
                risk += dec["risk_usd"]
            taken += 1
            if acct.record_trade(q * ppm_e[ei], -q * mae_pm) != "OPEN":
                break
        acct.end_of_day()
        if path is not None:
            path.append(acct.balance)
        if acct.status != "OPEN":
            break
    return acct.status, acct.days, taken, sw, sg, risk


def _thr(seq, cfg):
    return 0.0 if cfg is None else dead_threshold(seq["stop_med"], cfg)


def chrono(seq, cfg, ei=0):
    pool, n = seq["pool"], len(seq["pool"])
    thr = _thr(seq, cfg)
    k, out = 0, {"passes": 0, "fails": 0, "dead": 0, "days_to_pass": [], "days_to_fail": [], "taken": 0,
                 "skip_wide": 0, "skip_guard": 0, "risk": 0.0}
    eq_path, base = [], 0.0
    open_info = None
    while k < n:
        acct = EvalAccount()
        path = []
        st, days, taken, sw, sg, risk = run_eval(pool[k:], cfg, ei, thr, acct, path)
        out["taken"] += taken
        out["skip_wide"] += sw
        out["skip_guard"] += sg
        out["risk"] += risk
        eq_path += [base + (b - 50000.0) for b in path]
        base += acct.balance - 50000.0
        if st == "PASS":
            out["passes"] += 1
            out["days_to_pass"].append(days)
        elif st == "FAIL":
            out["fails"] += 1
            out["dead"] += acct.fail_kind == "dead"
            out["days_to_fail"].append(days)
        else:
            open_info = {"days": days, "profit": round(acct.balance - 50000.0, 2)}
            break
        k += max(days, 1)
    eq = np.array([0.0] + eq_path)
    out["max_dd"] = round(float((eq - np.maximum.accumulate(eq)).min()), 2)
    out["net"] = round(base, 2)
    out["open"] = open_info
    out["avg_risk"] = round(out["risk"] / out["taken"], 1) if out["taken"] else 0.0
    out["tpw"] = round(out["taken"] / (n / 5.0), 2)
    del out["risk"]
    # rolling: a fresh eval started on every day (as analytics.rolling_evals)
    rp = rf = 0
    rdays = []
    for s in range(n):
        st, days, *_ = run_eval(pool[s:], cfg, ei, thr)
        if st == "PASS":
            rp += 1
            rdays.append(days)
        elif st == "FAIL":
            rf += 1
    out["rolling_pass"] = round(100.0 * rp / (rp + rf), 1) if rp + rf else None
    out["rolling_completed"] = rp + rf
    out["rolling_avg_days"] = round(float(np.mean(rdays)), 1) if rdays else None
    return out


def boot(seq, cfg, idx, ei):
    pool = seq["pool"]
    thr = _thr(seq, cfg)
    res = collections.Counter()
    dpass, taken_l, risk_t, sw_t, sg_t = [], [], 0.0, 0, 0
    days_run = 0
    for row in idx:
        acct = EvalAccount()
        st, days, taken, sw, sg, risk = run_eval((pool[i] for i in row), cfg, ei, thr, acct)
        res[st] += 1
        if st == "FAIL" and acct.fail_kind == "dead":
            res["DEAD"] += 1
        if st == "PASS":
            dpass.append(days)
        taken_l.append(taken)
        days_run += days
        risk_t += risk
        sw_t += sw
        sg_t += sg
    runs = len(idx)
    tk = sum(taken_l)
    return {"p_pass": round(100.0 * res["PASS"] / runs, 1), "p_fail": round(100.0 * res["FAIL"] / runs, 1),
            "p_dead": round(100.0 * res["DEAD"] / runs, 1), "p_open": round(100.0 * res["OPEN"] / runs, 1),
            "med_days": float(np.median(dpass)) if dpass else None,
            "p25_days": float(np.percentile(dpass, 25)) if dpass else None,
            "p75_days": float(np.percentile(dpass, 75)) if dpass else None,
            "tpw": round(tk / max(days_run, 1) * 5.0, 2), "avg_risk": round(risk_t / tk, 1) if tk else 0.0,
            "skip_wide": sw_t, "skip_guard": sg_t,
            "skip_rate": round(100.0 * (sw_t + sg_t) / max(tk + sw_t + sg_t, 1), 1)}


def chain(seq, cfg, ei, runs=2000, max_days=250, seed=99):
    """A trader who buys a new eval after every fail until one passes, for at most `max_days` trading days.
    Returns P(funded within max_days), median/mean trading days to the first pass, and evals bought per run."""
    pool, n = seq["pool"], len(seq["pool"])
    thr = _thr(seq, cfg)
    got, days_pass, evals_l = 0, [], []
    for r in range(runs):
        rng = np.random.default_rng((seed, r))
        idx = rng.integers(0, n, size=max_days)
        used, evals = 0, 0
        while used < max_days:
            evals += 1
            acct = EvalAccount()
            st, days, *_ = run_eval((pool[i] for i in idx[used:]), cfg, ei, thr, acct)
            used += max(days, 1)
            if st == "PASS":
                got += 1
                days_pass.append(used)
                break
            if st == "OPEN":
                break
        evals_l.append(evals)
    return {"p_funded": round(100.0 * got / runs, 1), "med_days": float(np.median(days_pass)) if days_pass else None,
            "mean_days": round(float(np.mean(days_pass)), 1) if days_pass else None,
            "evals_per_run": round(float(np.mean(evals_l)), 2),
            "evals_per_pass": round(float(np.sum(evals_l)) / got, 2) if got else None, "runs": runs, "max_days": max_days}


def run_chains(path, policies, families=("engine", "regime", "narrative")):
    res = json.load(open(path))
    seqs = {(s["name"], s["period"]): s for s in load_sequences()}
    t0 = time.time()
    for meta in res["sequences"]:
        if meta["family"] not in families:
            continue
        s = seqs.get((meta["name"], meta["period"]))
        if not s:
            continue
        for p in policies:
            if p not in meta["rows"]:
                continue
            cfg = _cfg(p, s)
            meta["rows"][p]["chain"] = chain(s, cfg, 0)
            meta["rows"][p]["chain_zero"] = chain(s, cfg, 1)
            c, z = meta["rows"][p]["chain"], meta["rows"][p]["chain_zero"]
            print(f"[{time.time() - t0:5.0f}s] chain {meta['name']:18s} {meta['period']:8s} {p:16s} funded {c['p_funded']:5.1f}% "
                  f"med {c['med_days']} d, evals/pass {c['evals_per_pass']} | zero {z['p_funded']:5.1f}% evals/pass {z['evals_per_pass']}",
                  flush=True)
        with open(path, "w") as fh:
            json.dump(res, fh, indent=1, default=str)


# ------------------------------------------------------------------------------------------------ checks
def sanity(seq):
    """P0 must reproduce the file's own sizing (flat $350) and P&L."""
    c = POLICIES["P0"]
    same = 0
    acct = EvalAccount()
    for t in seq["trades"]:
        d = size(t["grade"], t["stop"], acct.account_state(), {"pnl": 0, "trades": 0, "wins": 0, "losses": 0}, c)
        same += d["qty_micros"] == min(t["qty0"], 40)
    return {"qty_match_pct": round(100.0 * same / max(seq["n"], 1), 1)}


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5000)
    ap.add_argument("--horizon", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20261016)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--es", action="store_true", help="also run the ES rule modules (MES $5/pt)")
    ap.add_argument("--only", default="", help="comma list of sequence-name prefixes")
    ap.add_argument("--out", default=os.path.join(LAB, "RISK_results.json"))
    ap.add_argument("--long-runs", type=int, default=2000, help="runs for the 250-day 'eventual pass' check")
    ap.add_argument("--add", default="", help="comma list of policies to compute and merge into the existing results")
    a = ap.parse_args()
    runs = 1000 if a.quick else a.runs
    seqs = load_sequences(include_es=a.es)
    if a.quick:
        seqs = [s for s in seqs if s["family"] == "engine"]
    if a.only:
        seqs = [s for s in seqs if any(s["name"].startswith(p) for p in a.only.split(","))]
    if a.add:   # add policies to sequences already in the results file (same seeds, so rows stay comparable)
        res = json.load(open(a.out))
        by = {(s["name"], s["period"]): s for s in res["sequences"]}
        res["policies"] = POLICY_NAMES
        t0 = time.time()
        for s in seqs:
            meta = by.get((s["name"], s["period"]))
            if not meta:
                continue
            idx = np.random.default_rng(a.seed).integers(0, len(s["pool"]), size=(res["runs"], res["horizon"]))
            idx_long = np.random.default_rng(a.seed + 1).integers(0, len(s["pool"]), size=(a.long_runs, 250))
            variants = (0, 1, 2) if s["family"] == "engine" else (0, 1)
            for p in a.add.split(","):
                cfg = _cfg(p, s)
                row = {"chrono": chrono(s, cfg, 0)}
                for ei in variants:
                    row[("boot", "boot_zero", "boot_half")[ei]] = boot(s, cfg, idx, ei)
                if s["family"] == "engine":
                    row["long"] = boot(s, cfg, idx_long, 0)
                    row["long_zero"] = boot(s, cfg, idx_long, 1)
                meta["rows"][p] = row
                print(f"[{time.time() - t0:5.0f}s] add {s['name']:20s} {s['period']:8s} {p:16s} P(pass) {row['boot']['p_pass']} "
                      f"fail {row['boot']['p_fail']} zero {row['boot_zero']['p_pass']}"
                      + (f" | 250d {row['long']['p_pass']}/{row['long']['p_fail']}" if "long" in row else ""), flush=True)
            with open(a.out, "w") as fh:
                json.dump(res, fh, indent=1, default=str)
        write_tables(res)
        return
    results = {"built_at": time.time(), "runs": runs, "horizon": a.horizon, "seed": a.seed,
               "policies": POLICY_NAMES, "sequences": []}
    if a.only and os.path.exists(a.out):     # partial re-run: keep the other sequences
        old = json.load(open(a.out))
        keep = {(s["name"], s["period"]) for s in seqs}
        results["sequences"] = [s for s in old.get("sequences", []) if (s["name"], s["period"]) not in keep]
    t0 = time.time()
    tiered = {p for p in POLICIES if POLICIES[p]["tiers"]}
    for s in seqs:
        rng = np.random.default_rng(a.seed)
        idx = rng.integers(0, len(s["pool"]), size=(runs, a.horizon))
        idx_long = np.random.default_rng(a.seed + 1).integers(0, len(s["pool"]), size=(a.long_runs, 250))
        if s["family"] == "engine":
            pols = ENGINE_POLICIES
        elif s["family"] == "narrative":
            pols = NARR_POLICIES
        elif s["family"] == "regime":
            pols = REGIME_POLICIES
        else:   # ungraded sequences: tiered policies equal their flat versions (every setup is B), so skip them
            pols = [p for p in OTHER_POLICIES if s["graded"] or p not in tiered]
        variants = (0, 1, 2) if s["family"] == "engine" else (0, 1)
        meta = {k: v for k, v in s.items() if k not in ("cal", "pool", "trades")}
        meta["sanity"] = sanity(s)
        rows = {}
        for p in pols:
            cfg = _cfg(p, s)
            row = {"chrono": chrono(s, cfg, 0)}
            for ei in variants:
                row[("boot", "boot_zero", "boot_half")[ei]] = boot(s, cfg, idx, ei)
            if s["family"] == "engine" and p in LONG_POLICIES and not a.quick:
                row["long"] = boot(s, cfg, idx_long, 0)
                row["long_zero"] = boot(s, cfg, idx_long, 1)
            rows[p] = row
            print(f"[{time.time() - t0:6.0f}s] {s['name']:22s} {s['period']:8s} {p:12s} "
                  f"b2b {row['chrono']['passes']}/{row['chrono']['fails']} roll {row['chrono']['rolling_pass']} | "
                  f"P(pass) {row['boot']['p_pass']:5.1f} fail {row['boot']['p_fail']:5.1f} med {row['boot']['med_days']} | "
                  f"zero {row['boot_zero']['p_pass']:5.1f}" + (f" half {row['boot_half']['p_pass']:5.1f}" if 2 in variants else "")
                  + (f" | 250d {row['long']['p_pass']:5.1f}/{row['long']['p_fail']:5.1f} zero {row['long_zero']['p_pass']:5.1f}"
                     if "long" in row else ""), flush=True)
        meta["rows"] = rows
        results["sequences"].append(meta)
        with open(a.out, "w") as fh:
            json.dump(results, fh, indent=1, default=str)
    print(f"done in {time.time() - t0:.0f}s -> {a.out}")
    write_tables(results)


# ------------------------------------------------------------------------------------------------ tables
def _d(x):
    return "-" if x is None else (f"{x:.0f}" if isinstance(x, float) else str(x))


def write_tables(results, path=os.path.join(LAB, "RISK_tables.md")):
    L = [f"# Risk-policy tables (generated by tools/lab_risk_run.py, {dt.datetime.fromtimestamp(results['built_at']):%Y-%m-%d %H:%M})",
         "",
         f"Bootstrap: {results['runs']:,} runs x {results['horizon']} trading days, whole days resampled (common random "
         "numbers across policies). P(pass)/P(fail)/P(open) in %. Zero-edge = every trade's R de-meaned. "
         "b2b = back-to-back evals on the real day order (pass/fail). Rolling = a fresh eval started on every day "
         "(pass % of completed). Max DD = continuous equity path across the b2b evals. Skips = setups too wide for 1 MNQ "
         "at the policy's budget, or blocked by the MLL/daily-limit guard (bootstrap total).", ""]
    for s in results["sequences"]:
        half = any("boot_half" in r for r in s["rows"].values())
        L += [f"## {s['name']} {s['period']} ({s['start']}..{s['end']}, {s['sessions']} sessions)", "",
              f"{s['n']} trades, {s['tpw']}/wk, avg R {s['avg_r']:+.3f} {s['ci95_r']}, sum {s['sum_r']:+.1f}R, PF {s['pf']}, "
              f"median sizing stop {s['stop_med']} pts, days with 2+ trades {s['multi_days']}, P0 qty match "
              f"{s['sanity']['qty_match_pct']}%. {s['note']}", ""]
        if s["graded"]:
            L += ["Grades: " + ", ".join(f"{g} n={v['n']} avg R {v['avg_r']:+.2f}" for g, v in s["by_grade"].items()), ""]
        hdr = ("| policy | b2b P/F | days to pass | max DD $ | net $ | rolling % | /wk | avg risk $ | P(pass) | P(fail) (dead) "
               "| P(open) | med days | P(pass) zero-edge | P(fail) zero-edge | " + ("P(pass) half-edge | " if half else "") + "skips |")
        L += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
        for p, r in s["rows"].items():
            c, b, z = r["chrono"], r["boot"], r["boot_zero"]
            dtp = ",".join(str(x) for x in c["days_to_pass"]) or "-"
            L.append(f"| {p} {results['policies'][p]} | {c['passes']}/{c['fails']} | {dtp} | {c['max_dd']:,.0f} | {c['net']:+,.0f} | "
                     f"{_d(c['rolling_pass'])} | {b['tpw']} | {b['avg_risk']:.0f} | **{b['p_pass']}** | {b['p_fail']} ({b.get('p_dead', 0)}) | "
                     f"{b['p_open']} | {_d(b['med_days'])} | {z['p_pass']} | {z['p_fail']} | "
                     + (f"{r['boot_half']['p_pass']} | " if half else "") + f"{b['skip_wide'] + b['skip_guard']} |")
        L.append("")
        longs = {p: r for p, r in s["rows"].items() if "long" in r}
        if longs:
            L += ["250-trading-day horizon (no 60-day cut-off; separate random draws):", "",
                  "| policy | P(pass) | P(fail) (dead) | P(open) | med days | P(pass) zero-edge | P(fail) zero-edge |",
                  "|---|---|---|---|---|---|---|"]
            for p, r in longs.items():
                lg, lz = r["long"], r["long_zero"]
                L.append(f"| {p} {results['policies'][p]} | **{lg['p_pass']}** | {lg['p_fail']} ({lg['p_dead']}) | {lg['p_open']} | "
                         f"{_d(lg['med_days'])} | {lz['p_pass']} | {lz['p_fail']} |")
            L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("tables ->", path)


REPORT_ROWS = ["P0", "P0g", "P0_250", "P0_500", "P1", "P1b", "P2_k25", "P2f_k35", "P3_50h", "P3_30w", "P3_30h",
               "P4a", "P4b2", "P4b1", "P5_f_c35_f1", "P5_f_c35_w30", "P5_f_c35_w30_f1", "P5_t_c_d_f2", "REC"]


def report_tables(results, path=os.path.join(LAB, "RISK_report_tables.md")):
    """The curated tables quoted in RISK_REPORT.md, straight from RISK_results.json."""
    S = {(s["name"], s["period"]): s for s in results["sequences"]}
    P = results["policies"]
    e26, e25, e5 = (S.get(("ENGINE_orig1day", k)) for k in ("2026", "2025", "2021-25"))
    L = ["# Report tables (generated by tools/lab_risk_run.py --summary)", ""]

    def pf(b):
        return f"{b['p_pass']} / {b['p_fail']}"

    L += ["## A. Leading candidate, 2026 bed (ENGINE_orig1day, 93 trades, +0.38R avg)", "",
          "| policy | 60-day P(pass) | P(fail) | median days to pass | zero-edge P(pass) | half-edge P(pass) | 250-day P(pass) / P(fail) | 250-day zero-edge P(pass) | real 2026 order: passes/fails (days to pass) | max DD $ | trades/wk |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in REPORT_ROWS:
        r = e26["rows"].get(p) if e26 else None
        if not r:
            continue
        b, z, h, c = r["boot"], r["boot_zero"], r["boot_half"], r["chrono"]
        lg, lz = r.get("long"), r.get("long_zero")
        L.append(f"| {p} {P[p]} | **{b['p_pass']}** | {b['p_fail']} | {_d(b['med_days'])} | {z['p_pass']} | {h['p_pass']} | "
                 + (f"{lg['p_pass']} / {lg['p_fail']} | {lz['p_pass']}" if lg else "- | -")
                 + f" | {c['passes']}/{c['fails']} ({','.join(map(str, c['days_to_pass'])) or '-'}) | {c['max_dd']:,.0f} | {b['tpw']} |")
    L += ["", "## B. Same settings on the no-edge beds: 60-day P(pass) / P(fail) [zero-edge P(pass)]; 250-day P(pass) / P(fail); real order passes/fails", "",
          "| policy | 2025: 60-day | 2025: 250-day | 2025 real order | 2021-25: 60-day | 2021-25: 250-day | 2021-25 real order |",
          "|---|---|---|---|---|---|---|"]
    for p in REPORT_ROWS:
        cells = []
        for s in (e25, e5):
            r = s["rows"].get(p) if s else None
            if not r:
                cells += ["-", "-", "-"]
                continue
            lg = r.get("long")
            cells += [f"{pf(r['boot'])} [{r['boot_zero']['p_pass']}]", pf(lg) if lg else "-",
                      f"{r['chrono']['passes']}/{r['chrono']['fails']}"]
        L.append(f"| {p} {P[p]} | " + " | ".join(cells) + " |")
    chained = [s for s in (e26, e25, e5) if s and any("chain" in r for r in s["rows"].values())]
    if chained:
        L += ["", "## C. Buy a new eval after every fail, for one trading year (250 days)", "",
              "P(funded) = share of traders holding a passed eval within the year; days = median trading days to that pass; evals/funded = evals bought per funded account. Zero-edge in brackets.", "",
              "| policy | " + " | ".join(f"{s['period']}: P(funded) / days / evals per funded [zero-edge P(funded) / evals]" for s in chained) + " |",
              "|---|" + "---|" * len(chained)]
        for p in CHAIN_POLICIES:
            cells = []
            for s in chained:
                r = s["rows"].get(p, {})
                c, z = r.get("chain"), r.get("chain_zero")
                e2 = (lambda x: "-" if x is None else f"{x:.2f}")
                cells.append(f"{c['p_funded']}% / {_d(c['med_days'])} / {e2(c['evals_per_pass'])} [{z['p_funded']}% / {e2(z['evals_per_pass'])}]" if c else "-")
            if any(x != "-" for x in cells):
                L.append(f"| {p} {P[p]} | " + " | ".join(cells) + " |")
    # D. confidence signals
    L += ["", "## D. Does any grade pick the better setups? avg R by tier (n), and tier sizing vs flat (60-day P(pass) / P(fail))", "",
          "| signal | period | A tier | B tier | C tier | SKIP | flat $350 + guards (P0g) | tiers + guards (P1g) | A $700 / B,C $350 (P1b) |",
          "|---|---|---|---|---|---|---|---|---|"]
    gmap = {"A+": "A", "A": "A", "B": "B", "C": "C", "D": "C", "SKIP": "SKIP", "None": "B"}
    for name, label in (("ENGINE_orig1day", "engine grade (A+/A, B, C/D)"), ("REGIME_orig1day", "regime (trending = C)"),
                        ("NARR_v1_orig1day", "trader brain v1"), ("NARR_v2_orig1day", "trader brain v2")):
        for per in ("2026", "2025", "2021-25"):
            s = S.get((name, per))
            if not s:
                continue
            agg = collections.defaultdict(lambda: [0, 0.0])
            for g, v in s["by_grade"].items():
                t = gmap.get(g, "B")
                agg[t][0] += v["n"]
                agg[t][1] += v["n"] * v["avg_r"]
            cell = lambda t: f"{agg[t][1] / agg[t][0]:+.2f} ({agg[t][0]})" if agg[t][0] else "-"  # noqa: E731
            base = S.get(("ENGINE_orig1day", per))
            r0 = (base or {}).get("rows", {}).get("P0g")
            r1, rb = s["rows"].get("P1g"), s["rows"].get("P1b")
            L.append(f"| {label} | {per} | {cell('A')} | {cell('B')} | {cell('C')} | {cell('SKIP')} | "
                     f"{pf(r0['boot']) if r0 else '-'} | {pf(r1['boot']) if r1 else '-'} | {pf(rb['boot']) if rb else '-'} |")
    # E. other models
    oth = [s for s in results["sequences"] if s["family"] not in ("engine", "narrative", "regime")]
    if oth:
        L += ["", "## E. Other models, 2026: 60-day P(pass) / P(fail) [zero-edge P(pass)]", "",
              "| model | trades | /wk | avg R [95% CI] | P0 flat $350 | P0g + guards | P3_30w | P2f_k35 | best of all tested |",
              "|---|---|---|---|---|---|---|---|---|"]
        seen = set()
        for s in oth:
            key = (s["n"], s["avg_r"], s["sum_r"])
            if key in seen:      # identical trade lists saved under two names
                continue
            seen.add(key)
            def cell(p):
                r = s["rows"].get(p)
                return f"{pf(r['boot'])} [{r['boot_zero']['p_pass']}]" if r else "-"
            best = max(s["rows"].items(), key=lambda kv: kv[1]["boot"]["p_pass"])
            L.append(f"| {s['name']} | {s['n']} | {s['tpw']} | {s['avg_r']:+.3f} {s['ci95_r']} | " + " | ".join(
                cell(p) for p in ("P0", "P0g", "P3_30w", "P2f_k35")) + f" | {best[0]}: {pf(best[1]['boot'])} [{best[1]['boot_zero']['p_pass']}] |")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("report tables ->", path)


def summary_md(results, policies, path=os.path.join(LAB, "RISK_summary.md")):
    """Compact cross-sequence tables for the report: one row per policy, one column group per sequence."""
    eng = [s for s in results["sequences"] if s["family"] == "engine"]
    nar = [s for s in results["sequences"] if s["family"] == "narrative"]
    reg = [s for s in results["sequences"] if s["family"] == "regime"]
    oth = [s for s in results["sequences"] if s["family"] not in ("engine", "narrative", "regime")]
    L = ["# Risk-policy summary (generated by tools/lab_risk_run.py --summary)", ""]
    if reg:
        L += ["## Regime as the confidence signal (trending = C $175, rotational = B $350) vs flat: 60-day P(pass) / P(fail) [zero-edge P(pass)]", "",
              "| policy | " + " | ".join(s["period"] for s in reg) + " |", "|---|" + "---|" * len(reg)]
        e_by = {s["period"]: s for s in eng}
        for lab, fam, p in (("flat $350 + guards (P0g)", "engine", "P0g"), ("regime tiers + guards (P1g)", "regime", "P1g"),
                            ("flat + cushion .35 (P2f_k35)", "engine", "P2f_k35"), ("regime tiers + cushion .35 (P2_k35)", "regime", "P2_k35")):
            cells = []
            for s in reg:
                src = e_by.get(s["period"]) if fam == "engine" else s
                r = (src or {}).get("rows", {}).get(p)
                cells.append(f"{r['boot']['p_pass']} / {r['boot']['p_fail']} [{r['boot_zero']['p_pass']}]" if r else "-")
            L.append(f"| {lab} | " + " | ".join(cells) + " |")
        L.append("")
    if nar:
        L += ["## Same engine trades, graded by the trader brain (NARRATIVE v1/v2): 60-day P(pass) / P(fail) [zero-edge P(pass)]", "",
              "| policy | " + " | ".join(f"{s['name'].split('_')[1]} {s['period']}" for s in nar) + " |",
              "|---|" + "---|" * len(nar)]
        for p in NARR_POLICIES:
            cells = []
            for s in nar:
                r = s["rows"].get(p)
                cells.append(f"{r['boot']['p_pass']} / {r['boot']['p_fail']} [{r['boot_zero']['p_pass']}], {r['boot']['tpw']}/wk" if r else "-")
            L.append(f"| {p} {results['policies'][p]} | " + " | ".join(cells) + " |")
        L += ["", "Grades: " + "; ".join(f"{s['name'].split('_')[1]} {s['period']}: " + ", ".join(
            f"{g} n={v['n']} {v['avg_r']:+.2f}R" for g, v in s["by_grade"].items()) for s in nar), ""]
    L += ["## Leading candidate (ENGINE_orig1day): 60-day bootstrap P(pass) / P(fail), zero-edge P(pass)", "",
          "| policy | " + " | ".join(f"{s['period']} pass/fail | {s['period']} zero" for s in eng) + " | 2026 half-edge | 2026 med days | 2026 b2b P/F |",
          "|---|" + "---|---|" * len(eng) + "---|---|---|"]
    for p in policies:
        cells = []
        for s in eng:
            r = s["rows"].get(p)
            cells.append(f"{r['boot']['p_pass']} / {r['boot']['p_fail']} | {r['boot_zero']['p_pass']}" if r else "- | -")
        r26 = eng[0]["rows"].get(p)
        L.append(f"| {p} {results['policies'][p]} | " + " | ".join(cells) + " | "
                 + (f"{r26['boot_half']['p_pass']} | {_d(r26['boot']['med_days'])} | {r26['chrono']['passes']}/{r26['chrono']['fails']} |" if r26 else "- | - | - |"))
    L += ["", "## Leading candidate, 250-trading-day horizon: P(pass) / P(fail), zero-edge P(pass) / P(fail)", "",
          "| policy | " + " | ".join(f"{s['period']} pass/fail | {s['period']} zero pass/fail" for s in eng) + " | 2026 med days |",
          "|---|" + "---|---|" * len(eng) + "---|"]
    for p in policies:
        if not all("long" in s["rows"].get(p, {}) for s in eng):
            continue
        cells = [f"{s['rows'][p]['long']['p_pass']} / {s['rows'][p]['long']['p_fail']} | "
                 f"{s['rows'][p]['long_zero']['p_pass']} / {s['rows'][p]['long_zero']['p_fail']}" for s in eng]
        L.append(f"| {p} {results['policies'][p]} | " + " | ".join(cells) + f" | {_d(eng[0]['rows'][p]['long']['med_days'])} |")
    chained = [s for s in eng + reg if any("chain" in r for r in s["rows"].values())]
    if chained:
        L += ["", "## Buy a new eval after every fail, for one trading year (250 days): P(funded) / median days to the pass / evals bought per funded account; zero-edge in brackets", "",
              "| policy | " + " | ".join(f"{s['name'].split('_')[0]} {s['period']}" for s in chained) + " |",
              "|---|" + "---|" * len(chained)]
        for p in CHAIN_POLICIES:
            cells = []
            for s in chained:
                r = s["rows"].get(p, {})
                c, z = r.get("chain"), r.get("chain_zero")
                e2 = lambda x: "-" if x is None else f"{x:.2f}"  # noqa: E731
                cells.append(f"{c['p_funded']}% / {_d(c['med_days'])} d / {e2(c['evals_per_pass'])} "
                             f"[{z['p_funded']}% / {e2(z['evals_per_pass'])}]" if c else "-")
            if any(x != "-" for x in cells):
                L.append(f"| {p} {results['policies'][p]} | " + " | ".join(cells) + " |")
    if oth:
        cols = ["P0", "P0g", "P3_30w", "P5_f_c35_w30", "P2f_k35", "P4b1"]
        L += ["", "## Other models, 2026: 60-day P(pass) / P(fail) [zero-edge P(pass)]", "",
              "| model | trades | /wk | avg R [95% CI] | " + " | ".join(cols) + " | best policy |",
              "|" + "---|" * (len(cols) + 5)]
        for s in oth:
            def cell(p):
                r = s["rows"].get(p)
                return f"{r['boot']['p_pass']} / {r['boot']['p_fail']} [{r['boot_zero']['p_pass']}]" if r else "-"
            best = max(s["rows"].items(), key=lambda kv: kv[1]["boot"]["p_pass"])
            L.append(f"| {s['name']} | {s['n']} | {s['tpw']} | {s['avg_r']:+.3f} {s['ci95_r']} | "
                     + " | ".join(cell(p) for p in cols)
                     + f" | {best[0]} {best[1]['boot']['p_pass']} [{best[1]['boot_zero']['p_pass']}] |")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("summary ->", path)


if __name__ == "__main__":
    if "--chain" in sys.argv:
        run_chains(os.path.join(LAB, "RISK_results.json"), CHAIN_POLICIES)
    elif "--summary" in sys.argv:
        _res = json.load(open(os.path.join(LAB, "RISK_results.json")))
        _res["policies"] = {**_res.get("policies", {}), **POLICY_NAMES}
        write_tables(_res)
        summary_md(_res, [p for p in ENGINE_POLICIES if any(p in s["rows"] for s in _res["sequences"])])
        report_tables(_res)
    else:
        main()
