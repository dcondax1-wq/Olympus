"""Trader-brain (engine/narrative.py) evaluation. Single process, real CME NQ1!/ES1! 5m only.

  python -X utf8 tools/lab_narrative_run.py dist             -> outcome-blind grade distribution on the 2026 dev bed
  python -X utf8 tools/lab_narrative_run.py eval [--v2]      -> the pre-registered evaluation (NARRATIVE_RULES.md s.5-6)
  python -X utf8 tools/lab_narrative_run.py atm [--v2]       -> part (b): the ATM model's own trades (tools/lab_models/atm.py)
  python -X utf8 tools/lab_narrative_run.py examples         -> part (c): 10 thought logs -> research/lab/NARRATIVE_EXAMPLES.md

Outputs: research/lab/NARRATIVE_results.json, NARRATIVE_trades.json, NARRATIVE_RESULTS.md, NARRATIVE_EXPERIENCE_LOG.md.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.strategy_lab import OUT, PERIODS, SLIP_PTS, bars, stats  # noqa: E402
from engine import narrative as N  # noqa: E402

BED = os.path.join(OUT, "conf_testbed_orig1day.json")
FIVE = os.path.join(ROOT, "research", "five_year", "run_live.json")
RES_JSON = os.path.join(OUT, "NARRATIVE_results.json")
TR_JSON = os.path.join(OUT, "NARRATIVE_trades.json")
DEV, CONF = PERIODS["dev"], PERIODS["confirm"]
Y25 = PERIODS["y2025"]
GRADES = ("A", "B", "C", "SKIP")
KEEP = ("trades", "tpw", "weeks_in_2_5", "win_rate", "avg_r", "ci95_r", "pf", "net", "max_dd", "worst_day", "rolling_pass",
        "zero_edge_pass", "losing_months", "months")


# ------------------------------------------------------------------------------------------------ frames and judging
_F = {}


def frames():
    if not _F:
        _F["nq"] = bars("NQ", "5m")
        _F["es"] = bars("ES", "5m")
    return _F["nq"], _F["es"]


def judge(setup, nq, es, versions, cuts=None):
    nar = N.narrative(nq, setup["entry_t"], es)
    ver = {v: N.assess(setup, nar, nq, es, version=v, cuts=cuts) for v in versions}
    return nar, ver


def engine_records(trades, source, versions, cuts=None, sim=False):
    nq, es = frames()
    out = []
    for t in trades:
        s = N.infer_setup(nq, t["entry_t"], t["dir"], t["risk_pts"], (t.get("f") or {}).get("rr_plan"), t.get("trigger"))
        nar, ver = judge(s, nq, es, versions, cuts)
        rec = {"key": f"{int(t['entry_t'])}:{int(t['dir'])}", "source": source, "day": t["day"], "entry_t": int(t["entry_t"]),
               "dir": int(t["dir"]), "r": float(t["r"]), "pnl": float(t["pnl"]), "qty": int(t.get("qty") or 1),
               "risk_pts": float(t["risk_pts"]), "exit": t.get("exit") or t.get("exit_kind"), "setup": s,
               "nar": _nar_light(nar), "ver": {v: _ver_light(x) for v, x in ver.items()}}
        if sim:
            r_ = N.simulate(nq, s, ver["v1"], nar, fill_t=t["entry_t"], entry_fill=s["entry"])
            rec["brain"] = {"r": r_["r"], "log": r_["log"], "legs": r_["legs"]}
        out.append(rec)
    return out


def atm_setup(t):
    info = t.get("info") or {}
    d = int(t["dir"])
    st = info.get("ext_t")
    if st is None and info.get("bars_to_entry") is not None:
        sec = 60 * int(info.get("tf", 5) or 5)
        st = int(t["entry_t"]) - sec - sec * int(info["bars_to_entry"])
    return {"entry_t": int(t["entry_t"]), "dir": d, "entry": float(t["entry"]), "stop": float(t["stop"]),
            "sweep_level": info.get("atm_l") if d > 0 else info.get("atm_h"), "sweep_label": "ATM-L" if d > 0 else "ATM-H",
            "sweep_t": st, "trigger_tf": f"{info.get('trigger_tf', info.get('tf', 5))}m", "ifvg_pts": info.get("ifvg_pts"),
            "bars_to_v": info.get("bars_to_v"), "targets": [float(t["target"])] if t.get("target") else []}


def atm_records(trades, versions, cuts=None):
    nq, es = frames()
    out = []
    for t in trades:
        if t.get("exit_kind") == "open":
            continue
        s = atm_setup(t)
        nar, ver = judge(s, nq, es, versions, cuts)
        out.append({"key": f"{int(t['entry_t'])}:{int(t['dir'])}", "source": "atm", "day": t["day"], "entry_t": int(t["entry_t"]),
                    "dir": int(t["dir"]), "r": float(t["r"]), "pnl": float(t["pnl"]), "qty": int(t["qty"]),
                    "risk_pts": float(t["risk_pts"]), "mae_usd": float(t.get("mae_usd", 0.0)), "exit": t.get("exit_kind"),
                    "owner_tier": t.get("tier"), "setup": s, "nar": _nar_light(nar), "ver": {v: _ver_light(x) for v, x in ver.items()}})
    return out


def _nar_light(n):
    keep = ("day", "bias", "bias_dir", "conviction", "bias_score", "draw", "day_type", "po3", "premarket_story", "update",
            "story", "bias_failed", "draw_hit", "today_range", "remaining", "adr10")
    return {k: n.get(k) for k in keep}


def _ver_light(v):
    return {"decision": v["decision"], "grade": v["grade"], "score": v["score"], "veto": v["veto"], "plan": v["target_plan"]["plan"],
            "plan_text": v["target_plan"]["text"], "mode": v["manage_mode"], "thoughts": v["thoughts"],
            "el": {e: x["score"] for e, x in v["elements"].items()}, "why": {e: x["why"] for e, x in v["elements"].items()},
            "facts": v["facts"]}


# ------------------------------------------------------------------------------------------------ metrics
def _spearman(x, y):
    if len(x) < 5:
        return None
    a = pd.Series(x).rank().to_numpy()
    b = pd.Series(y).rank().to_numpy()
    if a.std() == 0 or b.std() == 0:
        return None
    return round(float(np.corrcoef(a, b)[0, 1]), 3)


def _boot_diff(a, b, n=4000, seed=5):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or len(b) < 3:
        return None
    g = np.random.default_rng(seed)
    d = g.choice(a, (n, len(a))).mean(1) - g.choice(b, (n, len(b))).mean(1)
    return [round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3), round(float((d > 0).mean()), 3)]


def grade_table(recs, gkey, a, z):
    """gkey(rec) -> (grade, score). Avg R by grade, Spearman(score, R), A-minus-C with bootstrap CI."""
    rs = [x for x in recs if a <= x["day"] <= z]
    by = collections.defaultdict(list)
    sc, rr = [], []
    for x in rs:
        g, s = gkey(x)
        by[g].append(x["r"])
        sc.append(s)
        rr.append(x["r"])
    tab = {g: {"n": len(by[g]), "avg_r": round(float(np.mean(by[g])), 3) if by[g] else None,
               "win": round(100 * float(np.mean([r > 0 for r in by[g]])), 1) if by[g] else None,
               "sum_r": round(float(np.sum(by[g])), 2)} for g in GRADES}
    av = [tab[g]["avg_r"] for g in ("A", "B", "C")]
    mono = all(v is not None for v in av) and av[0] > av[1] > av[2]
    ac = _boot_diff(by["A"], by["C"] + by["SKIP"]) if by["A"] and (by["C"] + by["SKIP"]) else None
    return {"n": len(rs), "by_grade": tab, "monotone_A_B_C": mono, "spearman": _spearman(sc, rr),
            "A_minus_CS": (round(float(np.mean(by["A"]) - np.mean(by["C"] + by["SKIP"])), 3) if by["A"] and (by["C"] + by["SKIP"]) else None),
            "A_minus_CS_ci": ac}


def qty_for(grade, risk_pts):
    rs = risk_pts + SLIP_PTS
    if grade == "A":
        return min(N.TIER_A_MAX_QTY, int(700.0 // (rs * 2.0)))
    if grade == "B":
        return min(40, int(350.0 // (rs * 2.0)))
    if grade == "C":
        return max(1, min(40, int(175.0 // (rs * 2.0))))
    return 0


def policy(recs, gkey, a, z, days=None, mode="drop", r_key=None):
    """Re-size by grade. mode 'drop' (C and SKIP removed) | 'tier' (C kept at $175) | 'base' (as traded).
    r_key: None = the trade's own P&L; 'brain' = brain-managed R x the new risk."""
    rs = sorted([x for x in recs if a <= x["day"] <= z], key=lambda x: x["entry_t"])
    out, scale = [], {}
    dstate = collections.defaultdict(lambda: {"losses": 0, "pnl": 0.0, "done": False})
    for x in rs:
        g = gkey(x)[0]
        if mode == "base":
            q = x["qty"]
        elif g == "SKIP" or (mode == "drop" and g == "C"):
            q = 0
        else:
            q = qty_for(g, x["risk_pts"])
        st = dstate[x["day"]]
        if mode != "base" and st["done"]:          # daily stops (R2/R3): 2 losses, -$600, or after a +1R winner
            q = 0
        if q < 1:
            scale[x["day"]] = scale.get(x["day"], 0.0)
            continue
        per = x["pnl"] / max(x["qty"], 1)
        pnl = per * q
        if r_key == "brain":
            pnl = x["brain"]["r"] * x["risk_pts"] * 2.0 * q
        t = {"day": x["day"], "entry_t": x["entry_t"], "dir": x["dir"], "pnl": round(pnl, 2), "r": x["r"] if r_key is None else x["brain"]["r"],
             "qty": q, "risk_pts": x["risk_pts"]}
        if "mae_usd" in x:
            t["mae_usd"] = x["mae_usd"] / max(x["qty"], 1) * q
        out.append(t)
        scale[x["day"]] = q / max(x["qty"], 1)
        st["pnl"] += t["pnl"]
        st["losses"] += int(t["pnl"] < 0)
        if st["losses"] >= 2 or st["pnl"] <= -600.0 or t["r"] >= 1.0:
            st["done"] = True
    gd = None
    if days is not None:
        bypnl = collections.defaultdict(float)
        for t in out:
            bypnl[t["day"]] += t["pnl"]
        gd = []
        for d in days:
            if not (a <= d["date"] <= z):
                continue
            f = scale.get(d["date"], 0.0)
            lo = d["low"] * f if r_key is None else min(0.0, bypnl.get(d["date"], 0.0))
            gd.append({"date": d["date"], "pnl": round(bypnl.get(d["date"], 0.0), 2), "low": round(min(lo, bypnl.get(d["date"], 0.0), 0.0), 2),
                       "trades": sum(1 for t in out if t["day"] == d["date"])})
    s = stats(out, a, z, given_days=gd)
    return {k: s.get(k) for k in KEEP}


# ------------------------------------------------------------------------------------------------ experience layer
HALF_LIFE_M = 12.0
N0 = 40.0
SCALE = 0.3


def _months_between(day, m0):
    y, m = int(day[:4]), int(day[5:7])
    Y, M = int(m0[:4]), int(m0[5:7])
    return (Y - y) * 12 + (M - m) - (int(day[8:10]) - 1) / 30.0


def trust_at(memory, month, eids, ver="v1"):
    """Trust multiplier per element from trades before `month` (YYYY-MM). Returns (trust, evidence)."""
    m0 = month + "-01"
    past = [x for x in memory if x["day"] < m0]
    tr, ev = {}, {}
    for e in eids:
        groups = {"pos": [], "neg": [], "zero": []}
        for x in past:
            s = x["ver"].get(ver, {}).get("el", {}).get(e)
            if s is None:
                continue
            w = 0.5 ** (_months_between(x["day"], m0) / HALF_LIFE_M)
            groups["pos" if s > 0 else ("neg" if s < 0 else "zero")].append((w, x["r"]))

        def wm(g):
            if not g:
                return None, 0.0
            w = np.array([a for a, _ in g])
            r = np.array([b for _, b in g])
            return float((w * r).sum() / w.sum()), float(w.sum() ** 2 / (w ** 2).sum())

        P, Ng, Z = groups["pos"], groups["neg"], groups["zero"]
        if len(P) >= 10 and len(Ng) >= 10:
            g1, g2, how = P, Ng, "liked vs disliked"
        elif len(P) >= 10 and len(Ng + Z) >= 10:
            g1, g2, how = P, Ng + Z, "liked vs the rest"
        elif len(Ng) >= 10 and len(P + Z) >= 10:
            g1, g2, how = P + Z, Ng, "the rest vs disliked"
        else:
            tr[e] = 1.0
            ev[e] = {"how": "cold start", "n1": len(P), "n2": len(Ng)}
            continue
        m1, n1 = wm(g1)
        m2, n2 = wm(g2)
        delta = m1 - m2
        nh = 2.0 / (1.0 / max(n1, 1e-9) + 1.0 / max(n2, 1e-9))
        ds = delta * nh / (nh + N0)
        tr[e] = float(min(2.0, max(0.0, 1.0 + ds / SCALE)))
        ev[e] = {"how": how, "m1": round(m1, 3), "m2": round(m2, 3), "n1": round(n1, 1), "n2": round(n2, 1),
                 "delta": round(delta, 3), "delta_s": round(ds, 3), "trust": round(tr[e], 2)}
    return tr, ev


def exp_grade(rec, trust, ver="v1", cuts=None):
    el = rec["ver"][ver]["el"]
    S = float(sum(trust.get(e, 1.0) * s for e, s in el.items()))
    gc = cuts or N.GRADE_CUT
    g = "A" if S >= gc["A"] else ("B" if S >= gc["B"] else ("C" if S >= gc["C"] else "SKIP"))
    if rec["ver"][ver]["veto"]:
        g = "SKIP"
    return g, round(S, 3)


def month_list(a, z):
    out, y, m = [], int(a[:4]), int(a[5:7])
    while f"{y:04d}-{m:02d}" <= z[:7]:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def learn_log(memory, months, eids, ver="v1"):
    """Plain-English monthly learning log + the trust table."""
    lines, table, prev = [], {}, {e: 1.0 for e in eids}
    for mo in months:
        tr, ev = trust_at(memory, mo, eids, ver)
        table[mo] = {"trust": {e: round(v, 2) for e, v in tr.items()}, "evidence": ev}
        ch = sorted(eids, key=lambda e: -abs(tr[e] - prev[e]))
        bits = []
        for e in ch[:3]:
            x = ev[e]
            if x["how"] == "cold start":
                continue
            verb = (f"trust up x{prev[e]:.2f} -> " if tr[e] > prev[e] + 0.02 else
                    (f"trust down x{prev[e]:.2f} -> " if tr[e] < prev[e] - 0.02 else "trust kept at "))
            g1 = {"liked vs disliked": "when it liked this", "liked vs the rest": "when it liked this",
                  "the rest vs disliked": "when it did not object"}[x["how"]]
            g2 = {"liked vs disliked": "when it disliked it", "liked vs the rest": "otherwise",
                  "the rest vs disliked": "when it objected"}[x["how"]]
            bits.append(f"{N.LABEL.get(e, e)}: {g1} {x['m1']:+.2f}R (n~{x['n1']:.0f}) vs {g2} {x['m2']:+.2f}R (n~{x['n2']:.0f}) "
                        f"-> {verb}x{tr[e]:.2f}")
        lines.append(f"- **{mo}** ({sum(1 for x in memory if x['day'] < mo + '-01')} past trades): " + ("; ".join(bits) if bits else "nothing new learned"))
        prev = dict(tr)
    return lines, table


# ------------------------------------------------------------------------------------------------ commands
def load_bed():
    with open(BED, encoding="utf-8") as fh:
        return json.load(fh)


def calib_cuts(recs, ver="v1"):
    """Outcome-blind check (NARRATIVE_RULES s.3): grade shares on 2026 dev from scores only."""
    dev = [x for x in recs if DEV[0] <= x["day"] <= DEV[1]]
    cnt = collections.Counter(x["ver"][ver]["grade"] for x in dev)
    n = max(1, len(dev))
    shares = {g: round(100 * cnt[g] / n, 1) for g in GRADES}
    bad = any(shares[g] < 10 or shares[g] > 60 for g in ("A", "B", "C"))
    cuts = dict(N.VERSION_CUTS.get(ver, N.GRADE_CUT))
    if bad:      # outcome-blind recalibration: A = top 30%, C = bottom 25%, score-SKIP only below min(-2, P5)
        sc = np.array([x["ver"][ver]["score"] for x in dev])
        cuts = {"A": float(np.percentile(sc, 70)), "B": float(np.percentile(sc, 25)),
                "C": float(min(N.GRADE_CUT["C"], np.percentile(sc, 5)))}
    return shares, bad, cuts


def regrade(recs, ver, cuts):
    for x in recs:
        v = x["ver"][ver]
        S = v["score"]
        g = "A" if S >= cuts["A"] else ("B" if S >= cuts["B"] else ("C" if S >= cuts["C"] else "SKIP"))
        if v["veto"]:
            g = "SKIP"
        v["grade_raw"] = v["grade"]
        v["grade"] = g


def cmd_dist(versions):
    bed = load_bed()
    t0 = time.time()
    recs = engine_records(bed["ytd"]["trades"], "bed26", versions)
    for v in versions:
        shares, bad, cuts = calib_cuts(recs, v)
        sc = [x["ver"][v]["score"] for x in recs if DEV[0] <= x["day"] <= DEV[1]]
        print(v, "dev grade shares %", shares, "calibrate:", bad, "cuts", {k: round(c, 2) for k, c in cuts.items()},
              "score pctl 10/25/50/75/90", [round(float(np.percentile(sc, p)), 2) for p in (10, 25, 50, 75, 90)])
        el = collections.defaultdict(collections.Counter)
        for x in recs:
            for e, s in x["ver"][v]["el"].items():
                el[e]["+" if s > 0 else ("-" if s < 0 else "0")] += 1
        for e in el:
            print("   ", e, dict(el[e]))
    print("took", round(time.time() - t0, 1), "s")


def cmd_eval(versions):
    t0 = time.time()
    bed = load_bed()
    nq, es = frames()
    print("frames", len(nq), len(es), round(time.time() - t0, 1), "s")
    r26 = engine_records(bed["ytd"]["trades"], "bed26", versions, sim=True)
    r25 = engine_records(bed["y2025"]["trades"], "bed25", versions, sim=True)
    with open(FIVE, encoding="utf-8") as fh:
        five = json.load(fh)["trades"]
    r5 = engine_records(five, "five", versions)
    print("judged", len(r26), len(r25), len(r5), round(time.time() - t0, 1), "s")
    res = {"generated": time.strftime("%Y-%m-%d %H:%M"), "versions": versions, "calibration": {}, "bed": {}, "five": {},
           "experience": {}, "brain_mgmt": {}}
    cuts_by = {}
    for v in versions:
        shares, bad, cuts = calib_cuts(r26, v)
        res["calibration"][v] = {"dev_shares": shares, "recalibrated": bad, "cuts": cuts}
        cuts_by[v] = cuts
        for R in (r26, r25, r5):
            regrade(R, v, cuts)
    days26, days25 = bed["ytd"]["days"], bed["y2025"]["days"]
    per = {"dev": (DEV, r26, days26), "confirm": (CONF, r26, days26), "ytd": (PERIODS["ytd"], r26, days26),
           "y2025": ((bed["y2025"]["start"], bed["y2025"]["end"]), r25, days25)}
    for v in versions:
        gk = (lambda vv: (lambda x: (x["ver"][vv]["grade"], x["ver"][vv]["score"])))(v)
        res["bed"][v] = {}
        for pn, ((a, z), R, D) in per.items():
            res["bed"][v][pn] = {"grades": grade_table(R, gk, a, z),
                                 "base": policy(R, gk, a, z, D, "base"), "drop": policy(R, gk, a, z, D, "drop"),
                                 "tier": policy(R, gk, a, z, D, "tier")}
        # five-year check by year
        res["five"][v] = {y: grade_table(r5, gk, f"{y}-01-01", f"{y}-12-31") for y in ("2021", "2022", "2023", "2024", "2025", "2026")}
        res["five"][v]["all"] = grade_table(r5, gk, "2021-01-01", "2026-12-31")
        res["five"][v]["pre2025"] = grade_table(r5, gk, "2021-01-01", "2024-12-31")
        # score-only readout (vetoes ignored): does the score itself rank trades?
        cu = cuts_by[v]
        gs = (lambda cc, vv: (lambda x: ("A" if x["ver"][vv]["score"] >= cc["A"] else ("B" if x["ver"][vv]["score"] >= cc["B"] else
                                         ("C" if x["ver"][vv]["score"] >= cc["C"] else "SKIP")), x["ver"][vv]["score"])))(cu, v)
        res["bed"][v + "_scoreonly"] = {pn: {"grades": grade_table(R, gs, a, z)} for pn, ((a, z), R, D) in per.items()}
        res["five"][v + "_scoreonly"] = {"all": grade_table(r5, gs, "2021-01-01", "2026-12-31"),
                                         "pre2025": grade_table(r5, gs, "2021-01-01", "2024-12-31")}
        res.setdefault("vetoes", {})[v] = {pn: dict(collections.Counter((x["ver"][v]["veto"] or "none").split(" (")[0][:60]
                                                                        for x in R if a <= x["day"] <= z)) for pn, ((a, z), R, D) in per.items()}
    # brain management (Alt-3), v1 plan
    gk1 = lambda x: (x["ver"]["v1"]["grade"], x["ver"]["v1"]["score"])  # noqa: E731
    for pn, ((a, z), R, D) in per.items():
        sub = [x for x in R if a <= x["day"] <= z]
        res["brain_mgmt"][pn] = {"n": len(sub), "engine_avg_r": round(float(np.mean([x["r"] for x in sub])), 3) if sub else None,
                                 "brain_avg_r": round(float(np.mean([x["brain"]["r"] for x in sub])), 3) if sub else None,
                                 "flat350_engine": policy(R, gk1, a, z, D, "base"),
                                 "flat350_brain": policy(R, gk1, a, z, D, "base", r_key="brain"),
                                 "tier_brain": policy(R, gk1, a, z, D, "tier", r_key="brain"),
                                 "by_grade_brain": {g: (round(float(np.mean([x["brain"]["r"] for x in sub if x["ver"]["v1"]["grade"] == g])), 3)
                                                       if any(x["ver"]["v1"]["grade"] == g for x in sub) else None) for g in GRADES}}
    # experience layer (Alt-2): memory = five-year + beds (+ ATM when cached), de-duplicated
    mem, seen = [], set()
    atm_cache = os.path.join(OUT, "NARRATIVE_atm_records.json")
    extra = []
    if os.path.exists(atm_cache):
        with open(atm_cache, encoding="utf-8") as fh:
            extra = json.load(fh).get("records", [])
    for x in r26 + r25 + r5 + extra:
        if x["key"] in seen:
            continue
        seen.add(x["key"])
        mem.append(x)
    for v in ["v1"]:                       # the experience layer is pre-registered on the v1 elements only
        eids = N.VERSIONS[v]
        months = month_list("2025-04-01", "2026-10-16")
        log, table = learn_log(mem, months, eids, v)
        res["experience"][v] = {"log": log, "table": table, "memory": len(mem)}
        ek = (lambda vv: (lambda x: exp_grade(x, table[x["day"][:7]]["trust"], vv, cuts_by[vv])))(v)
        res["experience"][v]["bed"] = {}
        for pn, ((a, z), R, D) in per.items():
            res["experience"][v]["bed"][pn] = {"grades": grade_table(R, ek, a, z), "drop": policy(R, ek, a, z, D, "drop"),
                                               "tier": policy(R, ek, a, z, D, "tier")}
    with open(RES_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    with open(TR_JSON, "w", encoding="utf-8") as fh:
        json.dump({"bed26": r26, "bed25": r25}, fh, default=float)
    print("done", round(time.time() - t0, 1), "s")
    summarize(res)
    return res


def cmd_atm(versions):
    t0 = time.time()
    from tools.lab_models import atm as M
    a0, z0 = "2025-04-14", "2026-10-16"
    src = None
    for a_ in sys.argv:
        if a_.startswith("--file="):
            src = a_.split("=", 1)[1]
    if src:                                   # a saved run() output of the ATM agent (e.g. its 1m ladder)
        with open(src, encoding="utf-8") as fh:
            trades = json.load(fh)
        trades = trades.get("trades", trades) if isinstance(trades, dict) else trades
    else:
        nqa, esa = bars("NQ", "5m", a0, z0, warmup_days=10), bars("ES", "5m", a0, z0, warmup_days=10)
        trades = [t for t in M.run(nqa, {"sizing": "flat"}, esa) if t["day"] >= a0]
    print("atm trades", len(trades), "from", src or "run() on 5m", round(time.time() - t0, 1), "s")
    recs = atm_records(trades, versions)
    cuts_path = RES_JSON
    cuts_by = {}
    if os.path.exists(cuts_path):
        with open(cuts_path, encoding="utf-8") as fh:
            cuts_by = {v: c["cuts"] for v, c in json.load(fh).get("calibration", {}).items()}
    for v in versions:
        if v in cuts_by:
            regrade(recs, v, cuts_by[v])
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "n": len(recs), "atm_mtime": os.path.getmtime(M.__file__), "by": {},
           "source": src or "atm.run() 5m defaults, sizing flat"}
    for v in versions:
        gk = (lambda vv: (lambda x: (x["ver"][vv]["grade"], x["ver"][vv]["score"])))(v)
        out["by"][v] = {}
        for pn in ("dev", "confirm", "ytd", "y2025"):
            a, z = PERIODS[pn]
            out["by"][v][pn] = {"grades": grade_table(recs, gk, a, z), "base": policy(recs, gk, a, z, None, "base"),
                                "drop": policy(recs, gk, a, z, None, "drop"), "tier": policy(recs, gk, a, z, None, "tier")}
    owner = lambda x: (x.get("owner_tier") or "C", {"A": 2, "B": 1, "C": 0}.get(x.get("owner_tier"), 0))  # noqa: E731
    out["owner_tier"] = {pn: grade_table(recs, owner, *PERIODS[pn]) for pn in ("dev", "confirm", "ytd", "y2025")}
    tag = "_1m" if (src and "1m" in os.path.basename(src)) else ""
    with open(os.path.join(OUT, f"NARRATIVE_atm{tag}_records.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated": out["generated"], "records": recs, "source": out["source"]}, fh, default=float)
    with open(os.path.join(OUT, f"NARRATIVE_atm{tag}_results.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    for v in versions:
        for pn in ("dev", "confirm", "ytd", "y2025"):
            g = out["by"][v][pn]["grades"]
            print(v, pn, "n", g["n"], {k: (x["n"], x["avg_r"]) for k, x in g["by_grade"].items()}, "mono", g["monotone_A_B_C"],
                  "rho", g["spearman"])
    print("owner tiers", {pn: {k: (x["n"], x["avg_r"]) for k, x in g["by_grade"].items()} for pn, g in out["owner_tier"].items()})
    print("done", round(time.time() - t0, 1), "s")
    return out


def summarize(res):
    for v, per in res["bed"].items():
        for pn, x in per.items():
            g = x["grades"]
            if "base" not in x:
                print(f"{v} {pn:8s} n={g['n']:3d} " + " ".join(f"{k}:{g['by_grade'][k]['n']}/{g['by_grade'][k]['avg_r']}" for k in GRADES) +
                      f" mono={g['monotone_A_B_C']} rho={g['spearman']}")
                continue
            print(f"{v} {pn:8s} n={g['n']:3d} " + " ".join(f"{k}:{g['by_grade'][k]['n']}/{g['by_grade'][k]['avg_r']}" for k in GRADES) +
                  f" mono={g['monotone_A_B_C']} rho={g['spearman']} A-CS={g['A_minus_CS']} {g['A_minus_CS_ci']}")
            for pol in ("base", "drop", "tier"):
                s = x[pol]
                print(f"      {pol:5s} n={s['trades']} tpw={s['tpw']} net={s['net']:+,.0f} pf={s['pf']} dd={s['max_dd']:,.0f} "
                      f"pass={s['rolling_pass']} (zero {s['zero_edge_pass']}) losing_m={s['losing_months']}")
    for v, ex in res["experience"].items():
        for pn, x in ex["bed"].items():
            g = x["grades"]
            print(f"EXP {v} {pn:8s} " + " ".join(f"{k}:{g['by_grade'][k]['n']}/{g['by_grade'][k]['avg_r']}" for k in GRADES) +
                  f" mono={g['monotone_A_B_C']} rho={g['spearman']} | drop net={x['drop']['net']:+,.0f} tpw={x['drop']['tpw']} "
                  f"| tier net={x['tier']['net']:+,.0f}")
    for pn, x in res["brain_mgmt"].items():
        print(f"BRAIN {pn:8s} engine avgR={x['engine_avg_r']} brain avgR={x['brain_avg_r']} flat350 engine net={x['flat350_engine']['net']:+,.0f} "
              f"brain net={x['flat350_brain']['net']:+,.0f} pf={x['flat350_brain']['pf']} dd={x['flat350_brain']['max_dd']:,.0f} by grade {x['by_grade_brain']}")
    for v, f in res["five"].items():
        print("FIVE", v, {y: ({k: (g["by_grade"][k]["n"], g["by_grade"][k]["avg_r"]) for k in GRADES}, g["spearman"]) for y, g in f.items()})


MODEL_BED = os.path.join(OUT, "conf_testbed_models.json")


def model_records(trades, model, versions, cuts=None):
    """Plain-dict setups for a lab model's trades: entry/stop from the trade, sweep inferred, no target (default)."""
    nq, es = frames()
    C = N.ctx(nq)
    out = []
    for t in trades:
        if t.get("exit_kind") == "open":
            continue
        d = int(t["dir"])
        i_dec = C.idx_at(int(t["entry_t"]))
        sw = N.infer_sweep(C, i_dec, d)
        s = {"entry_t": int(t["entry_t"]), "dir": d, "entry": float(t["entry"]), "stop": float(t["stop"]), "model": model,
             "trigger_tf": "5m", **sw}
        nar, ver = judge(s, nq, es, versions, cuts)
        out.append({"key": f"{int(t['entry_t'])}:{d}", "source": model, "day": t["day"], "entry_t": int(t["entry_t"]), "dir": d,
                    "r": float(t["r"]), "pnl": float(t["pnl"]), "qty": int(t.get("qty") or 1), "risk_pts": float(t["risk_pts"]),
                    "mae_usd": float(t.get("mae_usd", 0.0)), "exit": t.get("exit_kind"), "setup": s, "nar": _nar_light(nar),
                    "ver": {v: _ver_light(x) for v, x in ver.items()}})
    return out


def cmd_models(versions, names=("silver_bullet", "mech_ifvg", "ict2022")):
    t0 = time.time()
    with open(MODEL_BED, encoding="utf-8") as fh:
        bed = json.load(fh)
    cuts_by = {}
    if os.path.exists(RES_JSON):
        with open(RES_JSON, encoding="utf-8") as fh:
            cuts_by = {v: c["cuts"] for v, c in json.load(fh).get("calibration", {}).items()}
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "models": {}}
    for nm in names:
        recs = []
        for key in (nm, nm + "@2025"):
            if key in bed:
                recs += model_records(bed[key]["trades"], nm, versions)
        for v in versions:
            if v in cuts_by:
                regrade(recs, v, cuts_by[v])
        res = {}
        for v in versions:
            gk = (lambda vv: (lambda x: (x["ver"][vv]["grade"], x["ver"][vv]["score"])))(v)
            res[v] = {}
            for pn in ("dev", "confirm", "ytd", "y2025"):
                a, z = PERIODS[pn]
                res[v][pn] = {"grades": grade_table(recs, gk, a, z), "base": policy(recs, gk, a, z, None, "base"),
                              "drop": policy(recs, gk, a, z, None, "drop"), "tier": policy(recs, gk, a, z, None, "tier")}
                g = res[v][pn]["grades"]
                print(nm, v, pn, "n", g["n"], {k: (x["n"], x["avg_r"]) for k, x in g["by_grade"].items()}, "mono", g["monotone_A_B_C"],
                      "rho", g["spearman"], "| base", res[v][pn]["base"]["net"], "tier", res[v][pn]["tier"]["net"], res[v][pn]["tier"]["tpw"])
        out["models"][nm] = {"n": len(recs), "by": res}
    with open(os.path.join(OUT, "NARRATIVE_models_results.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print("done", round(time.time() - t0, 1), "s")
    return out



# ------------------------------------------------------------------------------------------------ daily-bias study (owner request)
BIAS_DEFS = ("brain_composite", "brain_premarket", "ttrades_b1", "daily_bos", "h1_bos", "htf_draw_b2")


def bias_dirs(setup, nq, es):
    """Each bias definition's direction (+1/-1/0) at the setup's decision time (all causal)."""
    C = N.ctx(nq)
    t = int(setup["entry_t"])
    i = C.idx_at(t)
    k = int(C.di[i])
    nar = N.narrative(nq, t, es)
    pm = N._premarket(C, k, min(t, int(C.t930[k])))
    st = N._b1_state(C, k)
    jd, j1 = C.D.at(t), C.H1.at(t)
    cx = {"C": C, "i_dec": i, "setup": {**setup, "dir": 1}}
    sc, why = N._h_draw(cx)
    b2 = 0 if ("two-sided" in why or "no draw" in why) else (1 if sc > 0 else -1)
    return {"brain_composite": nar["bias_dir"], "brain_premarket": pm["bias_dir"], "ttrades_b1": (st[1] if st else 0),
            "daily_bos": int(C.D.dir[jd]) if jd >= 0 else 0, "h1_bos": int(C.H1.dir[j1]) if j1 >= 0 else 0, "htf_draw_b2": b2}


def _grp(rows):
    if not rows:
        return {"n": 0, "avg_r": None, "win": None}
    return {"n": len(rows), "avg_r": round(float(np.mean(rows)), 3), "win": round(100 * float(np.mean([r > 0 for r in rows])), 1)}


def bias_table(recs, a, z):
    out = {}
    sub = [x for x in recs if a <= x["day"] <= z]
    for b in BIAS_DEFS:
        al = [x["r"] for x in sub if x["bias"][b] == x["dir"]]
        co = [x["r"] for x in sub if x["bias"][b] == -x["dir"]]
        ne = [x["r"] for x in sub if x["bias"][b] == 0]
        out[b] = {"aligned": _grp(al), "neutral": _grp(ne), "counter": _grp(co),
                  "aligned_minus_counter": (round(float(np.mean(al) - np.mean(co)), 3) if al and co else None),
                  "ci": _boot_diff(al, co) if al and co else None}
    return out


def cmd_bias():
    t0 = time.time()
    nq, es = frames()
    bed = load_bed()
    beds = {}
    beds["engine"] = engine_records(bed["ytd"]["trades"], "bed26", ["v1"]) + engine_records(bed["y2025"]["trades"], "bed25", ["v1"])
    with open(FIVE, encoding="utf-8") as fh:
        five = [t for t in json.load(fh)["trades"] if t["day"] < "2025-01-01"]
    beds["engine_2021_2024"] = engine_records(five, "five", ["v1"])
    with open(MODEL_BED, encoding="utf-8") as fh:
        mb = json.load(fh)
    for nm in ("silver_bullet", "mech_ifvg", "ict2022"):
        beds[nm] = model_records(mb[nm]["trades"] + mb[nm + "@2025"]["trades"], nm, ["v1"])
    ap = os.path.join(OUT, "NARRATIVE_atm_1m_records.json")
    if not os.path.exists(ap):
        ap = os.path.join(OUT, "NARRATIVE_atm_records.json")
    if os.path.exists(ap):
        with open(ap, encoding="utf-8") as fh:
            beds["atm"] = json.load(fh)["records"]
    for nm, R in beds.items():
        for x in R:
            x["bias"] = bias_dirs(x["setup"], nq, es)
    print("judged", {k: len(v) for k, v in beds.items()}, round(time.time() - t0, 1), "s")
    res = {"generated": time.strftime("%Y-%m-%d %H:%M"), "tables": {}, "require_alignment": {}}
    pers = {"dev": DEV, "confirm": CONF, "y2025": Y25, "all": ("2021-01-01", "2026-12-31")}
    for nm, R in beds.items():
        res["tables"][nm] = {pn: bias_table(R, a, z) for pn, (a, z) in pers.items()}
    # require_bias_alignment (v1 grades; counter-bias vs the brain's composite bias -> SKIP), on vs off
    days = {"bed26": bed["ytd"]["days"], "bed25": bed["y2025"]["days"]}
    for nm in ("engine", "silver_bullet", "mech_ifvg", "ict2022", "atm"):
        if nm not in beds:
            continue
        R = beds[nm]
        out = {}
        for pn in ("dev", "confirm", "ytd", "y2025"):
            a, z = PERIODS[pn]
            D = None
            if nm == "engine":
                D = days["bed25"] if pn == "y2025" else days["bed26"]
            gk_off = lambda x: (x["ver"]["v1"]["grade"], x["ver"]["v1"]["score"])  # noqa: E731
            gk_on = lambda x: (("SKIP" if (x["bias"]["brain_composite"] == -x["dir"]) else x["ver"]["v1"]["grade"]),  # noqa: E731
                               x["ver"]["v1"]["score"])
            flat_on = lambda x: ("B" if x["bias"]["brain_composite"] != -x["dir"] else "SKIP", 0)  # noqa: E731
            out[pn] = {"off_base": policy(R, gk_off, a, z, D, "base"), "off_tier": policy(R, gk_off, a, z, D, "tier"),
                       "on_flat350": policy(R, flat_on, a, z, D, "tier"), "on_tier": policy(R, gk_on, a, z, D, "tier")}
        res["require_alignment"][nm] = out
    with open(os.path.join(OUT, "NARRATIVE_bias_results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    for nm, T in res["tables"].items():
        for pn, tb in T.items():
            print(nm, pn, {b: (tb[b]["aligned"]["n"], tb[b]["aligned"]["avg_r"], tb[b]["counter"]["n"], tb[b]["counter"]["avg_r"]) for b in BIAS_DEFS})
    for nm, o in res["require_alignment"].items():
        for pn, x in o.items():
            print("REQ", nm, pn, {k: (v["trades"], v["tpw"], round(v["net"]), v["pf"], round(v["max_dd"])) for k, v in x.items()})
    print("done", round(time.time() - t0, 1), "s")


# ------------------------------------------------------------------------------------------------ diagnostics + report
def cmd_diag():
    """Does the pre-market narrative itself predict the day? Bias vs the RTH direction, draw hit rate vs the opposite side,
    day-type vs the RTH range. Descriptive, all days 2022-2026."""
    nq, es = frames()
    C = N.ctx(nq)
    rows = collections.defaultdict(list)
    for k in range(60, len(C.days)):
        day = C.days[k]
        t930 = int(C.t930[k])
        i930 = int(np.searchsorted(C.t, t930))
        if i930 >= len(C.t) or C.t[i930] != t930:
            continue
        ie = np.flatnonzero((C.di == k) & (C.mod == 950))
        if not len(ie):
            continue
        n = N.narrative(nq, t930, es)
        ie = int(ie[0])
        move = float(C.c[ie] - C.o[i930])
        rth_rng = float(C.h[i930:ie + 1].max() - C.l[i930:ie + 1].min())
        hit = opp_hit = None
        if n["draw"] and not n["draw"].get("two_sided"):
            d = n["draw"]
            hit = C.taken(d["side"], d["price"], i930, ie)
            pm = N._premarket(C, k, t930)
            opp = [q for q in pm["pools"] if q["side"] == -d["side"] and not q["taken"] and q["name"] in N.TIER_A
                   and (q["price"] - pm["price"]) * -d["side"] >= 0.15 * pm["adr10"]]
            if opp:
                o = min(opp, key=lambda q: abs(q["price"] - pm["price"]))
                opp_hit = C.taken(o["side"], o["price"], i930, ie)
        rows[day[:4]].append({"b": n["bias_dir"], "conv": n["conviction"], "mv": int(np.sign(move)), "hit": hit, "opp": opp_hit,
                              "dt": n["day_type"], "rr": rth_rng / max(n["adr10"], 1e-9)})
    out = {}
    for y, R in sorted(rows.items()):
        bi = [r for r in R if r["b"] != 0]
        hc = [r for r in bi if r["conv"] >= 0.67]
        pairs = [r for r in R if r["hit"] is not None and r["opp"] is not None]
        dts = collections.defaultdict(list)
        for r in R:
            dts[r["dt"]].append(r["rr"])
        out[y] = {"days": len(R), "bias_days": len(bi),
                  "bias_eq_rth_dir": round(100 * float(np.mean([r["b"] == r["mv"] for r in bi])), 1) if bi else None,
                  "high_conv_eq": round(100 * float(np.mean([r["b"] == r["mv"] for r in hc])), 1) if hc else None, "high_conv_n": len(hc),
                  "draw_hit": round(100 * float(np.mean([r["hit"] for r in pairs])), 1) if pairs else None,
                  "opposite_hit": round(100 * float(np.mean([r["opp"] for r in pairs])), 1) if pairs else None, "pairs": len(pairs),
                  "rth_range_adr_by_daytype": {k_: (len(v), round(float(np.mean(v)), 2)) for k_, v in sorted(dts.items())}}
        print(y, out[y])
    with open(os.path.join(OUT, "NARRATIVE_diag.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return out


def _f(x, nd=3, sign=True):
    if x is None:
        return "-"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def _gt_row(name, g):
    b = g["by_grade"]
    cells = " | ".join(f"{b[k]['n']} / {_f(b[k]['avg_r'], 2)}" for k in GRADES)
    ci = g.get("A_minus_CS_ci")
    cis = f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else ""
    return f"| {name} | {g['n']} | {cells} | {'yes' if g['monotone_A_B_C'] else 'no'} | {_f(g['spearman'], 2)} | {_f(g.get('A_minus_CS'), 2)} {cis} |"


def _pol_row(name, s):
    return (f"| {name} | {s['trades']} | {s['tpw']} | {s['net']:+,.0f} | {s['pf']} | {s['max_dd']:,.0f} | {s['rolling_pass']} ({s['zero_edge_pass']}) | "
            f"{s['losing_months']} |")


GT_HDR = ["| readout | n | A: n / avg R | B | C | SKIP | A > B > C? | Spearman(score, R) | A minus (C+SKIP) [95% CI] |",
          "|---|---:|---|---|---|---|---|---:|---|"]
POL_HDR = ["| policy | trades | /wk | net $ | PF | max DD $ | 50K pass % (zero-edge) | losing months |",
           "|---|---:|---:|---:|---:|---:|---|---:|"]


def cmd_report():
    R = json.load(open(RES_JSON, encoding="utf-8"))
    M = json.load(open(os.path.join(OUT, "NARRATIVE_models_results.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "NARRATIVE_models_results.json")) else None
    A = json.load(open(os.path.join(OUT, "NARRATIVE_atm_results.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "NARRATIVE_atm_results.json")) else None
    A1 = json.load(open(os.path.join(OUT, "NARRATIVE_atm_1m_results.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "NARRATIVE_atm_1m_results.json")) else None
    B = json.load(open(os.path.join(OUT, "NARRATIVE_bias_results.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "NARRATIVE_bias_results.json")) else None
    D = json.load(open(os.path.join(OUT, "NARRATIVE_diag.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "NARRATIVE_diag.json")) else None
    bed = R["bed"]
    L = ["# NARRATIVE RESULTS: does the trader brain rank trades?", "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M')} ET by `python -X utf8 tools/lab_narrative_run.py report` from `NARRATIVE_results.json`, "
         "`NARRATIVE_models_results.json`, `NARRATIVE_atm_results.json`, `NARRATIVE_bias_results.json` and `NARRATIVE_diag.json`. "
         "Rules: `NARRATIVE_RULES.md` (v1 pre-registered before any outcome; v2 section 7). Code: `engine/narrative.py`. "
         "Real CME NQ1!/ES1! 5m only. R = the trade's own result (its model's management); grades come from closed bars at the decision time.", ""]
    L += ["## What was run (all of it is reported)", "",
          "- **Primary:** v1 grades (10 judgment elements, fixed weights) on the engine's current picks (`conf_testbed_orig1day.json`).",
          "- **Alt-1:** v2 = v1 reworked with the broad-agreement heuristics from `TRADER_HEURISTICS.md` (19 elements, 3 hard vetoes).",
          "- **Alt-2:** experience layer: per-element trust re-learned every month from past trades only (walk-forward), applied to v1.",
          "- **Alt-3:** the brain's own in-trade management (`manage()`) replacing the engine's exits on the same entries.",
          "- Descriptive extras requested by the owner/coordinator (no selection made on them): score-only grades (vetoes ignored), "
          "other models' trades (Silver Bullet, Mech/IFVG, ICT2022, ATM), a daily-bias alignment study with 6 bias definitions, "
          "`require_bias_alignment` on/off, and whether the pre-market narrative predicts the day at all.", ""]
    # 1. engine bed
    L += ["## 1. Engine trades (2026 dev / confirm, 2025 check): grade ranking", ""] + GT_HDR
    for v in ("v1", "v2"):
        for pn in ("dev", "confirm", "y2025", "ytd"):
            if v in bed and pn in bed[v]:
                L.append(_gt_row(f"{v} {pn}", bed[v][pn]["grades"]))
    for v in ("v1_scoreonly", "v2_scoreonly"):
        for pn in ("dev", "confirm", "y2025"):
            if v in bed:
                L.append(_gt_row(f"{v} {pn}", bed[v][pn]["grades"]))
    ex = R["experience"].get("v1", {}).get("bed", {})
    for pn in ("dev", "confirm", "y2025"):
        if pn in ex:
            L.append(_gt_row(f"experience (v1 elements) {pn}", ex[pn]["grades"]))
    L += ["", "Cells are `n / avg R`. SKIP rows are trades the brain would have passed on (their R is what the engine actually got).", ""]
    L += ["### Policy readouts (2026 = dev + confirm; 2025 = holdout)", "",
          "`base` = every engine trade as traded ($350 risk). `drop` = C and SKIP removed, A at $700 risk (max 10 MNQ = 1 NQ), B at $350. "
          "`tier` = C kept at $175 (min 1 MNQ). Same entries, per-contract P&L x the new size; 50K pass = rolling MFFU 50K (`strategy_lab.stats`).", ""]
    for pn in ("dev", "confirm", "ytd", "y2025"):
        L += [f"**{pn}**", ""] + POL_HDR
        L.append(_pol_row("base (engine as is)", bed["v1"][pn]["base"]))
        for v in ("v1", "v2"):
            if v in bed:
                L.append(_pol_row(f"{v} drop C/SKIP, A/B tiered", bed[v][pn]["drop"]))
                L.append(_pol_row(f"{v} tier (C at $175)", bed[v][pn]["tier"]))
        if pn in ex:
            L.append(_pol_row("experience drop", ex[pn]["drop"]))
            L.append(_pol_row("experience tier", ex[pn]["tier"]))
        L.append("")
    months = sorted(set(bed["v1"]["ytd"]["base"]["months"]) | set(bed["v1"]["ytd"]["drop"]["months"]))
    L += ["### 2026 monthly P&L ($)", "", "| month | base trades | base net | v1 drop trades | v1 drop net | v1 tier net | v2 tier net |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for m in months:
        b0 = bed["v1"]["ytd"]["base"]["months"].get(m, {"trades": 0, "net": 0})
        d1 = bed["v1"]["ytd"]["drop"]["months"].get(m, {"trades": 0, "net": 0})
        t1 = bed["v1"]["ytd"]["tier"]["months"].get(m, {"trades": 0, "net": 0})
        t2 = bed.get("v2", {}).get("ytd", {}).get("tier", {}).get("months", {}).get(m, {"trades": 0, "net": 0})
        L.append(f"| {m} | {b0['trades']} | {b0['net']:+,.0f} | {d1['trades']} | {d1['net']:+,.0f} | {t1['net']:+,.0f} | {t2['net']:+,.0f} |")
    L.append("")
    # 2. five-year
    L += ["## 2. Same fixed grades on the engine's five-year trades (run_live.json, 2021-11 .. 2026-10)", ""] + GT_HDR
    for v in ("v1", "v2"):
        for y in ("2022", "2023", "2024", "2025", "2026", "pre2025", "all"):
            if v in R["five"] and y in R["five"][v]:
                L.append(_gt_row(f"{v} {y}", R["five"][v][y]))
    L.append("")
    # 3. other models
    if M:
        L += ["## 3. Other models' trades (cached lab beds, default params, NQ)", ""] + GT_HDR
        for nm, x in M["models"].items():
            for v in ("v1", "v2"):
                for pn in ("dev", "confirm", "y2025"):
                    if v in x["by"]:
                        L.append(_gt_row(f"{nm} {v} {pn}", x["by"][v][pn]["grades"]))
        L.append("")
        L += ["Policy readouts on those beds (2026 ytd):", ""] + POL_HDR
        for nm, x in M["models"].items():
            L.append(_pol_row(f"{nm} base", x["by"]["v1"]["ytd"]["base"]))
            for v in ("v1", "v2"):
                if v in x["by"]:
                    L.append(_pol_row(f"{nm} {v} tier", x["by"][v]["ytd"]["tier"]))
        L.append("")
    for AX, nm_ in ((A1, "ATM 1m ladder"), (A, "ATM 5m")):
        if not AX:
            continue
        L += [f"### {nm_} model ({AX['n']} trades; source: {AX.get('source', 'atm.run()')}; atm.py time "
              f"{time.strftime('%H:%M', time.localtime(AX['atm_mtime']))})", ""] + GT_HDR
        pns = [pn for pn in ("dev", "confirm", "y2025") if AX["by"]["v1"][pn]["grades"]["n"] > 0]
        for v in AX["by"]:
            for pn in pns:
                L.append(_gt_row(f"{nm_} {v} {pn}", AX["by"][v][pn]["grades"]))
        for pn in pns:
            L.append(_gt_row(f"{nm_} owner's own tiers {pn}", AX["owner_tier"][pn]))
        L += ["", POL_HDR[0], POL_HDR[1]]
        for pn in ("ytd", "y2025"):
            if AX["by"]["v1"][pn]["grades"]["n"] == 0:
                continue
            L.append(_pol_row(f"{nm_} base {pn}", AX["by"]["v1"][pn]["base"]))
            for v in AX["by"]:
                L.append(_pol_row(f"{nm_} {v} drop {pn}", AX["by"][v][pn]["drop"]))
                L.append(_pol_row(f"{nm_} {v} tier {pn}", AX["by"][v][pn]["tier"]))
        L.append("")
    # 4. experience
    L += ["## 4. Experience layer (Alt-2): what the brain learned", "",
          f"Memory: {R['experience']['v1']['memory']} de-duplicated past trades (engine 2021-2026, both beds). Monthly log: `NARRATIVE_EXPERIENCE_LOG.md`. "
          "Final trust multipliers (2026-10):", "", "| element | trust | evidence |", "|---|---:|---|"]
    tab = R["experience"]["v1"]["table"]
    last = sorted(tab)[-1]
    for e, tr in tab[last]["trust"].items():
        ev = tab[last]["evidence"][e]
        evs = (f"{ev['how']}: {ev['m1']:+.2f}R (n~{ev['n1']:.0f}) vs {ev['m2']:+.2f}R (n~{ev['n2']:.0f})" if "m1" in ev else ev["how"])
        L.append(f"| {N.LABEL.get(e, e)} | x{tr:.2f} | {evs} |")
    L.append("")
    # 5. brain management
    bm = R["brain_mgmt"]
    L += ["## 5. Brain management (Alt-3): `manage()` instead of the engine's exits, same entries, flat $350", "",
          "| period | engine avg R | brain avg R | engine net | brain net | brain PF | brain max DD |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pn in ("dev", "confirm", "ytd", "y2025"):
        x = bm[pn]
        L.append(f"| {pn} | {_f(x['engine_avg_r'])} | {_f(x['brain_avg_r'])} | {x['flat350_engine']['net']:+,.0f} | {x['flat350_brain']['net']:+,.0f} | "
                 f"{x['flat350_brain']['pf']} | {x['flat350_brain']['max_dd']:,.0f} |")
    L.append("")
    # 6. bias
    if B:
        L += ["## 6. Daily bias: does trading WITH the bias help? (owner request)", "",
              "Aligned = trade direction equals the bias; counter = opposite; neutral days not shown. Bias definitions (all causal at the "
              "decision time): `brain_composite` = the narrative's bias after the intraday failure check (v1 E1); `brain_premarket` = the "
              "same at 09:30; `ttrades_b1` = TTrades candle-closure target side; `daily_bos` / `h1_bos` = last daily / 1H BOS; "
              "`htf_draw_b2` = the B2 best-scored draw side (two-sided days = neutral).", "",
              "| bed | bias | aligned n / avg R | counter n / avg R | aligned minus counter [95% CI] |", "|---|---|---|---|---|"]
        for nm, T in B["tables"].items():
            tb = T["all"]
            for b in BIAS_DEFS:
                x = tb[b]
                ci = x.get("ci")
                cis = f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else ""
                L.append(f"| {nm} | {b} | {x['aligned']['n']} / {_f(x['aligned']['avg_r'], 2)} | {x['counter']['n']} / {_f(x['counter']['avg_r'], 2)} | "
                         f"{_f(x['aligned_minus_counter'], 2)} {cis} |")
        L += ["", "### `require_bias_alignment` (skip counter-bias setups unless the bias is neutral; brain composite bias), off vs on", "",
              "| bed | period | off: as traded | off: v1 tier | on: flat $350 | on: v1 tier |", "|---|---|---|---|---|---|"]
        for nm, o in B["require_alignment"].items():
            for pn, x in o.items():
                cell = lambda s_: f"{s_['trades']} tr, {s_['tpw']}/wk, {s_['net']:+,.0f}, PF {s_['pf']}"  # noqa: E731
                L.append(f"| {nm} | {pn} | {cell(x['off_base'])} | {cell(x['off_tier'])} | {cell(x['on_flat350'])} | {cell(x['on_tier'])} |")
        L.append("")
    if D:
        L += ["## 7. Does the pre-market narrative predict the day? (all sessions, descriptive)", "",
              "| year | days | bias days | bias = RTH direction % | high-conviction = RTH dir % (n) | primary draw hit % | nearest opposite pool hit % (pairs) | RTH range / ADR by day type |",
              "|---|---:|---:|---:|---|---:|---|---|"]
        for y, x in D.items():
            L.append(f"| {y} | {x['days']} | {x['bias_days']} | {x['bias_eq_rth_dir']} | {x['high_conv_eq']} ({x['high_conv_n']}) | {x['draw_hit']} | "
                     f"{x['opposite_hit']} ({x['pairs']}) | {x['rth_range_adr_by_daytype']} |")
        L.append("")
    EP = os.path.join(OUT, "NARRATIVE_elements.json")
    if os.path.exists(EP):
        E = json.load(open(EP, encoding="utf-8"))
        names = list(next(iter(E.values())).keys())
        L += ["## 8. Which trader judgments does the data agree with? (descriptive map, every element on every bed)", "",
              "Cell = avg R when the element liked the trade minus avg R when it disliked it (or vs the rest when one side is thin). "
              "Many cells are tested here, so expect several |diffs| of 0.3R by luck alone; look for the same sign everywhere.", "",
              "| element | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
        for e, row in E.items():
            L.append(f"| {N.LABEL.get(e, e)} ({e}) | " + " | ".join(_f(row[n]['diff'], 2) if row[n]['diff'] is not None else "thin" for n in names) + " |")
        L.append("")
    with open(os.path.join(OUT, "NARRATIVE_RESULTS_tables.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    lg = ["# NARRATIVE EXPERIENCE LOG: what the brain learned each month (walk-forward, v1 elements)", "",
          "Each month the brain re-weighs every judgment element from trades that closed before that month only "
          "(NARRATIVE_RULES.md section 6: 12-month half-life, shrinkage n0 = 40, trust = clip(1 + delta/0.3R, 0, 2)). "
          "The three biggest changes each month:", ""] + R["experience"]["v1"]["log"]
    with open(os.path.join(OUT, "NARRATIVE_EXPERIENCE_LOG.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lg) + "\n")
    print("wrote NARRATIVE_RESULTS_tables.md and NARRATIVE_EXPERIENCE_LOG.md")


def cmd_elements():
    """Descriptive: each judgment element's liked-minus-disliked avg R on every bed (multiple testing: read as a map, not proof)."""
    t0 = time.time()
    N.enable_v2()
    vers = ["v1", "v2"]
    bed = load_bed()
    beds = {"engine_2026": engine_records(bed["ytd"]["trades"], "bed26", vers),
            "engine_2025": engine_records(bed["y2025"]["trades"], "bed25", vers)}
    with open(FIVE, encoding="utf-8") as fh:
        five = [t for t in json.load(fh)["trades"] if t["day"] < "2025-01-01"]
    beds["engine_2021_24"] = engine_records(five, "five", vers)
    with open(MODEL_BED, encoding="utf-8") as fh:
        mb = json.load(fh)
    for nm in ("silver_bullet", "mech_ifvg", "ict2022"):
        beds[nm] = model_records(mb[nm]["trades"] + mb[nm + "@2025"]["trades"], nm, vers)
    eids = list(dict.fromkeys(N.VERSIONS["v1"] + N.VERSIONS["v2"]))
    out = {}
    for e in eids:
        out[e] = {}
        for nm, R in beds.items():
            v = "v1" if e in N.VERSIONS["v1"] else "v2"
            P = [x["r"] for x in R if x["ver"][v]["el"].get(e, 0) > 0]
            Q = [x["r"] for x in R if x["ver"][v]["el"].get(e, 0) < 0]
            Z = [x["r"] for x in R if x["ver"][v]["el"].get(e, 0) == 0]
            if len(P) >= 8 and len(Q) >= 8:
                d, how = float(np.mean(P) - np.mean(Q)), "+/-"
            elif len(P) >= 8 and len(Q + Z) >= 8:
                d, how = float(np.mean(P) - np.mean(Q + Z)), "+/rest"
            elif len(Q) >= 8 and len(P + Z) >= 8:
                d, how = float(np.mean(P + Z) - np.mean(Q)), "rest/-"
            else:
                d, how = None, "thin"
            out[e][nm] = {"diff": None if d is None else round(d, 3), "how": how, "n_pos": len(P), "n_neg": len(Q)}
    with open(os.path.join(OUT, "NARRATIVE_elements.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    names = list(beds)
    print("element".ljust(16), " ".join(n[:14].rjust(14) for n in names))
    for e in eids:
        print(e.ljust(16), " ".join((f"{out[e][n]['diff']:+.2f}" if out[e][n]["diff"] is not None else "thin").rjust(14) for n in names))
    print("done", round(time.time() - t0, 1), "s")


def cmd_lookahead(n=60, seed=3):
    """No-lookahead check: judge each sampled setup on the full history and on a frame cut at the decision time
    (only bars closed by entry_t, like live). Scores, grades, bias and draw must match exactly."""
    N.enable_v2()
    nq, es = frames()
    bed = load_bed()
    rng = np.random.default_rng(seed)
    pool = []
    for t in bed["ytd"]["trades"] + bed["y2025"]["trades"]:
        pool.append(("engine", N.infer_setup(nq, t["entry_t"], t["dir"], t["risk_pts"], t["f"].get("rr_plan"), t.get("trigger"))))
    ap = os.path.join(OUT, "NARRATIVE_atm_1m_records.json")
    if os.path.exists(ap):
        pool += [("atm1m", x["setup"]) for x in json.load(open(ap, encoding="utf-8"))["records"]]
    with open(MODEL_BED, encoding="utf-8") as fh:
        mb = json.load(fh)
    C = N.ctx(nq)
    for t in mb["silver_bullet"]["trades"][:60]:
        i_dec = C.idx_at(int(t["entry_t"]))
        pool.append(("silver_bullet", {"entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "entry": float(t["entry"]),
                                       "stop": float(t["stop"]), **N.infer_sweep(C, i_dec, int(t["dir"]))}))
    pick = [pool[i] for i in rng.choice(len(pool), size=min(n, len(pool)), replace=False)]
    bad = 0
    for src, s in pick:
        T = int(s["entry_t"])
        cut = nq[(nq["time"] + 300 <= T) & (nq["time"] >= T - 150 * 86400)].reset_index(drop=True)
        cut_es = es[(es["time"] + 300 <= T) & (es["time"] >= T - 150 * 86400)].reset_index(drop=True)
        cut_es = cut_es if len(cut_es) else None
        full_n = N.narrative(nq, T, es)
        cut_n = N.narrative(cut, T, cut_es)
        diffs = []
        for k in ("bias", "conviction", "day_type", "bias_failed", "draw_hit"):
            if full_n.get(k) != cut_n.get(k):
                diffs.append((k, full_n.get(k), cut_n.get(k)))
        if (full_n.get("draw") or {}).get("price") != (cut_n.get("draw") or {}).get("price"):
            diffs.append(("draw", (full_n.get("draw") or {}).get("price"), (cut_n.get("draw") or {}).get("price")))
        for v in ("v1", "v2"):
            a = N.assess(s, full_n, nq, es, version=v)
            b = N.assess(s, cut_n, cut, cut_es, version=v)
            for e in a["elements"]:
                if abs(a["elements"][e]["score"] - b["elements"][e]["score"]) > 1e-9:
                    diffs.append((v, e, a["elements"][e]["score"], b["elements"][e]["score"]))
            if a["grade"] != b["grade"] or (a["veto"] or "") != (b["veto"] or ""):
                diffs.append((v, "grade", a["grade"], b["grade"]))
        if diffs:
            bad += 1
            print("MISMATCH", src, dt.datetime.fromtimestamp(T, N.ET).strftime("%Y-%m-%d %H:%M"), diffs[:6])
    print(f"lookahead check: {len(pick)} setups, {bad} with any difference")
    with open(os.path.join(OUT, "NARRATIVE_lookahead.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M')} lookahead check: {len(pick)} sampled setups (engine 2025-26, ATM 1m, Silver Bullet), "
                 f"judged on the full history vs a frame cut at the decision time: {bad} with any difference\n")
    return bad

def _et(ts):
    return dt.datetime.fromtimestamp(int(ts), N.ET).strftime("%H:%M")


def pick_examples(recs, k=5):
    """5 winners and 5 losers at evenly spaced ranks by entry time (not hand-picked)."""
    w = sorted([x for x in recs if x["r"] > 0], key=lambda x: x["entry_t"])
    l_ = sorted([x for x in recs if x["r"] <= 0], key=lambda x: x["entry_t"])
    pick = lambda L: [L[round(i * (len(L) - 1) / (k - 1))] for i in range(k)] if len(L) >= k else L  # noqa: E731
    return pick(w), pick(l_)


def thought_log(x, ver="v1"):
    s, n, v = x["setup"], x["nar"], x["ver"][ver]
    d = "Long" if x["dir"] > 0 else "Short"
    L = [f"### {x['day']} {_et(x['entry_t'])} ET: {d} NQ, engine result {x['r']:+.2f}R (${x['pnl']:+,.0f}, exit {x['exit']})", ""]
    L.append(f"**Pre-market (09:30).** {n['premarket_story']}")
    L.append("")
    if n.get("update"):
        L.append(f"**Intraday update at the signal.** {n['update']}")
        L.append("")
    sw = N.NICE.get(s.get("sweep_label"), "local raid") if s.get("sweep_label") else "local raid (no named pool)"
    L.append(f"**Setup.** entry {s['entry']:,.2f}, stop {s['stop']:,.2f} ({x['risk_pts']:.1f} pts), swept: {sw}, "
             f"target {', '.join(f'{t:,.2f}' for t in s.get('targets') or []) or 'n/a'}.")
    L.append("")
    L.append(f"**At entry: {v['decision']} grade {v['grade']} (score {v['score']:+.2f}).** {v['thoughts']}")
    L.append("")
    L.append("| element | score | reason |")
    L.append("|---|---:|---|")
    for e, sc in v["el"].items():
        L.append(f"| {N.LABEL.get(e, e)} | {sc:+.2f} | {v['why'][e]} |")
    L.append("")
    b = x.get("brain")
    if b:
        L.append(f"**During the trade (the brain's own management, `manage()` replayed bar by bar; result {b['r']:+.2f}R vs the "
                 f"engine's {x['r']:+.2f}R).**")
        L.append("")
        for t, msg in b["log"]:
            L.append(f"- {_et(t)} {msg}")
        L.append("")
    return L


def cmd_examples():
    with open(TR_JSON, encoding="utf-8") as fh:
        recs = json.load(fh)["bed26"]
    w, l_ = pick_examples(recs)
    L = ["# NARRATIVE EXAMPLES: 10 thought logs from the trader brain (2026 engine trades)", "",
         "Generated by `python -X utf8 tools/lab_narrative_run.py examples` from `research/lab/NARRATIVE_trades.json`.",
         "Trades are the Liquidity Engine's 2026 picks (`conf_testbed_orig1day.json`). Selection is mechanical: winners and losers",
         "sorted by entry time and taken at evenly spaced ranks (5 each), not hand-picked. Everything the brain says is computed",
         "from closed bars at that moment. 'Engine result' is what the engine actually did; the in-trade log is what the brain's",
         "own `manage()` would have done on the same entry (rules in NARRATIVE_RULES.md section 4).", "", "## Winners", ""]
    for x in w:
        L += thought_log(x)
    L += ["## Losers", ""]
    for x in l_:
        L += thought_log(x)
    with open(os.path.join(OUT, "NARRATIVE_EXAMPLES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote NARRATIVE_EXAMPLES.md", len(w), len(l_))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dist"
    vers = ["v1", "v2"] if "--v2" in sys.argv else ["v1"]
    if "--v2" in sys.argv:
        N.enable_v2()                       # registers the v2 trader heuristics (NARRATIVE_RULES.md section 7)
    if cmd == "dist":
        cmd_dist(vers)
    elif cmd == "eval":
        cmd_eval(vers)
    elif cmd == "atm":
        cmd_atm(vers)
    elif cmd == "examples":
        cmd_examples()
    elif cmd == "models":
        cmd_models(vers)
    elif cmd == "bias":
        cmd_bias()
    elif cmd == "diag":
        cmd_diag()
    elif cmd == "report":
        cmd_report()
    elif cmd == "elements":
        cmd_elements()
    elif cmd == "lookahead":
        cmd_lookahead()
