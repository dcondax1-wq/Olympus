"""A2 pre-launch audit (2026-10-25): LIT baseline reproduction, complete trade ledgers, the 2026 signal ledger and a
robustness table at $1.90 a micro. Read-only research: changes no engine file and no live_model*.json, stores no run.

    python -X utf8 tools/a2_lit_audit.py base      # reproduce both configs + COMPLETE_TRADE_LEDGER.csv + SIGNAL_LEDGER_LIT.csv
    python -X utf8 tools/a2_lit_audit.py robust    # robustness table (research/handoff/2026-10-25/A2_robustness.{csv,json})
    python -X utf8 tools/a2_lit_audit.py all

Outputs go to research/handoff/2026-10-25/. Labels: BASELINE (both configs), RESEARCH_VARIANT (every robustness row).
"""
from __future__ import annotations

import collections
import copy
import csv
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from engine import lit  # noqa: E402
from tools import runlib as rl  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "handoff", "2026-10-25")
ET = None
COMM_MFFU = 1.90


# ------------------------------------------------------------------------------------------------ configs + hashes
def configs():
    cur = json.load(open("live_model.json", encoding="utf-8"))
    pre = json.loads(subprocess.check_output(["git", "show", "4a6f7f3^:live_model.json"], cwd=ROOT).decode())
    return {"pre_switch": {"lit": pre["lit"], "lit_sizing": pre["lit_sizing"], "run": "lit_adopt_t15_be_off",
                           "eval_run": "lit_adopt_t15_be_off_eval", "eval_cfg": {"two_week": {"room_f": 0.6}}},
            "current": {"lit": cur["lit"], "lit_sizing": cur["lit_sizing"], "run": "lit_live",
                        "eval_run": "hq_lit_sw_c22_r55_wk12_eval", "eval_cfg": {"two_week": {"room_f": 0.55}, "wk_loss_usd": 1200}}}


def cfg_hash(c):
    return hashlib.sha1(json.dumps({"lit": c["lit"], "lit_sizing": c["lit_sizing"]}, sort_keys=True).encode()).hexdigest()


def sha10(p):
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for ch in iter(lambda: fh.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()[:10]


def data_hash():
    return (f"5m:{rl._data_key()}|1m:{os.path.getsize('data/NQ_1m.csv')}-{sha10('data/NQ_1m.csv')}"
            f"|VIX:{sha10('data/VIX_1d.csv')}|VXN:{sha10('data/VXN_1d.csv')}")


def et(t):
    global ET
    if ET is None:
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
    return dt.datetime.fromtimestamp(int(t), ET).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------------------------ helpers
def et_min(t):
    x = dt.datetime.fromisoformat(et(t))
    return x.hour * 60 + x.minute


def key(T):
    return [(t["day"], int(t["entry_t"]), round(float(t["pnl"]), 2), t["exit"], int(t["qty"])) for t in sorted(T, key=lambda t: t["entry_t"])]


def stored_key(rid):
    r = rl.load(rid)
    c = r["trade_cols"]
    return [(x[c.index("day")], int(x[c.index("entry_t")]), round(float(x[c.index("pnl")]), 2), x[c.index("exit")], int(x[c.index("qty")]))
            for x in sorted(r["trades"], key=lambda x: x[c.index("entry_t")])], r


def span_stats(T, a, z):
    ss = [d for d in F.SESS if a <= d <= z]
    TT = [t for t in T if a <= t["day"] <= z]
    p = np.array([t["pnl"] for t in TT] or [0.0])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(TT) else 0.0
    return {"n": len(TT), "sessions": len(ss), "tpw": round(len(TT) / (len(ss) / 5), 2) if ss else None,
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum()), 2),
            "per_month": round(float(p.sum()) / (len(ss) / 21)) if ss else None, "dd": round(dd),
            "win": round(100.0 * float((p > 0).mean()), 1) if TT else None}


SPANS = (("2026", "2026-01-01", "2026-12-31"), ("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"),
         ("2021-25", "2021-01-01", "2025-12-31"))


# ------------------------------------------------------------------------------------------------ eval path (two_week)
def run_eval_s(seq, by, horizon=20, keep=None, cfg=None, stuck=None):
    """tools/hq_lit.run_eval_hq (the live two_week sizing via engine/sizing.lit_qty, eval weekly loss stop, $1.90) with one
    addition: stuck (None = off) ends the eval as "STUCK" at a session close when the room to the trailing max-loss floor is
    below $stuck (the bot's "EVAL STUCK: buy a new one" push, research/writeups/sizing-caps.md)."""
    from tools import lit_adv_manage as A
    from tools import lit_big_ideas as BI
    from engine import sizing as SZ
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    wk_pnl = collections.defaultdict(float)
    PV, SLIP = lit.PV, lit.SLIP
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        wk = lit.iso_week(A.S26[si])
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0, "wk_pnl": wk_pnl[wk] + cum}
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t.get("tgt_size", t["tgt"]), "size_mult": 1.0}, cfg,
                           room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl, low, tot = BI.trade_pnl(t, q, q, st)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2)}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        wk_pnl[wk] += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
        if stuck is not None and bal - floor < stuck:
            return "STUCK", kk + 1
    return "OPEN", min(len(seq), horizon)


def _eval_setup(T, eval_cfg):
    from tools import hq_lit as HQ
    from tools import lit_adv_manage as A
    U = HQ.engine_units(T)
    cfg = {**copy.deepcopy(HQ.CFG0), **eval_cfg}
    cfg["two_week"] = {**HQ.CFG0["two_week"], **eval_cfg.get("two_week", {})}
    return A, A.by_day(U), cfg


def eval_path_tagged(T, eval_cfg, stuck=None):
    """Back-to-back eval path (owner policy: a new eval only after a pass or a fail [or STUCK when stuck is set]), H1 and H2
    separately, as tools/hq_lit.eval_path / lit_adv_manage.b2b, with the eval number and its result on every trade."""
    A, by, cfg = _eval_setup(T, eval_cfg)
    out, evs = [], []
    for sp in ("H1", "H2"):
        a, z = A.span_ix(sp)
        k = a
        while k < z:
            keep = []
            r, used = run_eval_s(list(range(k, z)), by, z - k, keep=keep, cfg=cfg, stuck=stuck)
            eid = f"{sp}-E{len([e for e in evs if e['span'] == sp]) + 1:02d}"
            evs.append({"id": eid, "span": sp, "start": A.S26[k], "result": r, "sessions": used, "n": len(keep),
                        "net": round(sum(x["pnl"] for x in keep), 2)})
            for x in keep:
                x["eval_id"], x["eval_result"] = eid, r
            out += keep
            if r == "OPEN":
                break
            k += used
    return out, evs, cfg


def fresh_evals(T, eval_cfg, stuck=None):
    """A fresh eval started on every session of each half (only starts that see the full 10 / 20 sessions count, as
    tools/lit_adv_manage.evals): % pass / fail / stuck within 10 and 20 sessions (the rest is open)."""
    A, by, cfg = _eval_setup(T, eval_cfg)
    o = {}
    for sp in ("H1", "H2"):
        a, z = A.span_ix(sp)
        res = [(run_eval_s(list(range(i, min(z, i + 20))), by, 20, cfg=cfg, stuck=stuck), z - i) for i in range(a, z)]
        for h in (10, 20):
            R_ = [r for r, av in res if av >= h]
            N = len(R_) or 1
            o[f"{sp}_{h}"] = {"starts": len(R_), **{k.lower(): round(100.0 * sum(1 for r in R_ if r[0] == k and r[1] <= h) / N, 1)
                                                   for k in ("PASS", "FAIL", "STUCK")}}
    return o


# ------------------------------------------------------------------------------------------------ ledger rows
LEDGER_COLS = ["trade_id", "strategy", "setup_id", "account_profile", "contract", "signal_known_at", "entry_submit_at",
               "entry_fill_at", "direction", "quantity", "entry_price", "initial_stop", "target_price", "exit_time", "exit_price",
               "exit_reason", "gross_pnl", "commissions", "slippage_model", "net_pnl", "initial_risk_cash", "mfe_r", "mae_r",
               "config_hash", "data_hash"]


def setup_id(day, i, d):
    return f"LIT-{day}-i{int(i)}-{'L' if int(d) == 1 else 'S'}"


def slip_text(tf, ref):
    s = ("entry: market at the next bar open after the CISD close +1 tick; STOP / BE / EOD / CUT_T15 exits -1 tick; TARGET "
         "limit at the price, no slippage; stop fill = stop level -1 tick even on a gap through")
    s += "; bars " + ("1m" if tf == 1 else "5m (no full 1m coverage that day)")
    if ref:
        s += "; REFERENCE 2021-25: 5m bars only, 1m CISD approximated on 5m (cisd1m//5 bars), t_check never acts"
    return s


def ledger_lit(T, profile, chash, dhash, comm):
    rows = []
    for n, t in enumerate(sorted(T, key=lambda t: t["entry_t"]), 1):
        q, d = int(t["qty"]), int(t["dir"])
        secs = 60 if t.get("tf") == 1 else 300
        pts = (t["pnl"] + lit.COMM * q) / (lit.PV * q)            # per micro after slippage (engine $1.40 commission)
        exit_px = round((float(t["entry_px"]) * d + pts) * d, 2)
        gross = round(pts * lit.PV * q, 2)
        com = round(comm * q, 2)
        ref = t["day"] < "2026-01-01"
        xt = int(t["exit_t"]) - (secs if t["exit"] == "CUT_T15" else 0)
        rows.append({
            "trade_id": f"{'REF' if ref else 'T'}-{t['day']}-{n:04d}", "strategy": "LIT", "setup_id": setup_id(t["day"], t["i"], d),
            "account_profile": profile + ("|REF_2021-25_5m_only" if ref else ""), "contract": "MNQ (priced on TradingView CME NQ1! continuous, back-adjusted)",
            "signal_known_at": et(int(t["_sig_t"])) if t.get("_sig_t") else "UNKNOWN",
            "entry_submit_at": et(int(t["entry_t"])), "entry_fill_at": et(int(t["entry_t"])),
            "direction": "long" if d == 1 else "short", "quantity": q, "entry_price": t["entry_px"], "initial_stop": t["stop_px"],
            "target_price": t["target_px"],
            "exit_time": et(xt) + ("" if t["exit"] in ("EOD", "CUT_T15") else " (bar end; intrabar time UNKNOWN)"),
            "exit_price": exit_px, "exit_reason": t["exit"], "gross_pnl": gross, "commissions": com, "slippage_model": slip_text(t.get("tf"), ref),
            "net_pnl": round(gross - com, 2), "initial_risk_cash": t["risk_usd"], "mfe_r": t["mfe"], "mae_r": t["mae"],
            "config_hash": chash, "data_hash": dhash})
    return rows


def ledger_eval(TP, T, profile, chash, dhash):
    by = {(t["day"], int(t["entry_t"])): t for t in T}
    rows = []
    for n, x in enumerate(TP, 1):
        t = by[(x["day"], int(x["entry_t"]))]
        q, d = int(x["qty"]), int(x["dir"])
        secs = 60 if t.get("tf") == 1 else 300
        pts_u = (t["pnl"] + lit.COMM * t["qty"]) / (lit.PV * t["qty"])
        com = round(COMM_MFFU * q, 2)
        gross_u = round(pts_u * lit.PV * q, 2)
        clamped = abs((gross_u - com) - x["pnl"]) > 0.05
        xt = int(t["exit_t"]) - (secs if t["exit"] == "CUT_T15" else 0)
        rows.append({
            "trade_id": f"EV{'S' if 'stuck200' in profile else 'N'}-{x['eval_id']}-{n:04d}", "strategy": "LIT", "setup_id": setup_id(t["day"], t["i"], d),
            "account_profile": f"{profile}|{x['eval_id']}|{x['eval_result']}", "contract": "MNQ (priced on TradingView CME NQ1! continuous, back-adjusted)",
            "signal_known_at": et(int(t["_sig_t"])) if t.get("_sig_t") else "UNKNOWN",
            "entry_submit_at": et(int(t["entry_t"])), "entry_fill_at": et(int(t["entry_t"])),
            "direction": "long" if d == 1 else "short", "quantity": q, "entry_price": t["entry_px"], "initial_stop": t["stop_px"],
            "target_price": t["target_px"],
            "exit_time": et(xt) + ("" if t["exit"] in ("EOD", "CUT_T15") else " (bar end; intrabar time UNKNOWN)"),
            "exit_price": "UNKNOWN (daily-loss clamp)" if clamped else round((float(t["entry_px"]) * d + pts_u) * d, 2),
            "exit_reason": t["exit"] + (" +DLL_CLAMP" if clamped else ""),
            "gross_pnl": round(x["pnl"] + com, 2) if clamped else gross_u, "commissions": com,
            "slippage_model": slip_text(t.get("tf"), False) + "; eval scoring $1.90/micro",
            "net_pnl": x["pnl"], "initial_risk_cash": x["risk_usd"], "mfe_r": t["mfe"], "mae_r": t["mae"],
            "config_hash": chash, "data_hash": dhash})
    return rows


# ------------------------------------------------------------------------------------------------ signal ledger
def prefill(M, B, z, ep, tgt, stop, P):
    """Mirror of engine/lit.py simulate_x up to the fill (non-live, no research options): (status, detail, fill index)."""
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    if k0 >= B.n:
        return "no_bars", "", None
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    wait_s = P["wait"] * 300
    tgt_cancel = tgt[1]
    tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or lit._late(B.mod[k], P["flat_mod"], False):
            return ("tapped_no_cisd_before_flat" if tapped is not None else "flat_before_tap"), et(int(B.t[k])), None
        if tapped is None and B.t[k] >= t0 + wait_s:
            return "limit_expired_30min", f"no tap by {et(t0 + wait_s)}", None
        if lo_d[k] <= stop:
            return ("extreme_broken_after_tap_before_cisd" if tapped is not None else "extreme_broken_before_tap"), et(int(B.t[k])), None
        if tapped is None and lo_d[k] <= ep:
            tapped = k
        if tapped is None and hi_d[k] >= tgt_cancel:
            return "target_touched_before_tap", et(int(B.t[k])), None
        if tapped is not None:
            if k - tapped > cis:
                return "no_1m_cisd_within_window", f"tapped {et(int(B.t[tapped]))}, window {cis} bars", None
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1
                entry = float(o_d[fill]) + lit.SLIP
                risk = entry - stop
                if risk <= 0:
                    return "risk_nonpositive_after_fill", "", None
                if not tgt[2] and tgt[1] - entry < P["min_rr"] * risk:
                    return "below_min_rr_after_fill", f"target {round((tgt[1] - entry) / risk, 2)}R from the 1m fill", None
                if lit.qty_for(risk) < 1:
                    return "qty_zero", "", None
                return "filled", et(int(B.t[fill])), fill
        k += 1
    return "data_end", "", None


def signal_ledger(M, C, P, B1, B5, T, chash, dhash):
    from engine import brain
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    trades = {(t["day"], int(t["i"]), int(t["dir"])): t for t in T}
    busy, per_day = -1, collections.Counter()
    rows, mism = [], []
    for z in C:
        if z["day"] < "2026-01-01" or z["day"] not in set(F.SESS):
            continue
        d = z["dir"]
        chk = brain._checks(M, z, P, day_block=per_day[z["day"]] >= P["max_per_day"])
        filt_fail = next((c["key"] for c in chk if not c["ok"] and c["key"] != "day"), None)
        ep = min(float(z["ref_d"]), z["trig_c"]); stop = z["ext_d"] - P["stop_buf"]; risk = ep - stop
        tgt_c = next((c for c in chk if c["key"] == "target"), {})
        row = {"setup_id": setup_id(z["day"], z["i"], d), "day": z["day"], "direction": "long" if d == 1 else "short",
               "trigger_bar_open": et(int(M.t[z["i"]])), "signal_known_at": et(int(M.t[z["entry_i"]])),
               "entry_bar_et_min": z["mod"], "swept": ";".join(z["swept"]), "sweep_extreme": round(z["ext_d"] * d, 2),
               "depth_atr": z["depth_atr"], "disp_atr": z["disp"],
               "idm_ok_count": sum(1 for dd, aa in (z.get("idm_a") or []) if P.get("idm_a") and dd <= P["idm_a"][0] and aa <= P["idm_a"][1]),
               "limit_px": round(ep * d, 2), "stop_px": round(stop * d, 2), "risk_pts": round(risk, 2),
               "target_rr_at_limit": tgt_c.get("value"), "filter_first_fail": filt_fail or "",
               "status": "", "first_failing_rule": "", "detail": "", "trade_id_ref": "", "config_hash": chash, "data_hash": dhash}
        tr = trades.get((z["day"], int(z["i"]), int(d)))
        if z["entry_i"] <= busy:
            row.update(status="skipped", first_failing_rule="busy_open_trade", detail="a trade was still open")
        elif per_day[z["day"]] >= P["max_per_day"]:
            row.update(status="skipped", first_failing_rule="day", detail="1 trade a day: the day already traded")
        elif filt_fail:
            c = next(c for c in chk if c["key"] == filt_fail)
            row.update(status="rejected", first_failing_rule=filt_fail, detail=c["text"])
        else:
            use1 = B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
            B = B1 if use1 else B5
            sh = z["entry_d"] - ep
            TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
            best = None
            for c in P["classes"]:
                for dist in TT.get(c, []):
                    if dist >= P["min_rr"] * risk:
                        best = dist if best is None or dist < best else best
                        break
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
            st, det, _ = prefill(M, B, z, ep, ("lvl", ep + tp, False), stop, P)
            row.update(status="armed_" + ("filled" if st == "filled" else "no_trade"), first_failing_rule="" if st == "filled" else st,
                       detail=det + ("" if use1 else " [5m bars]"))
            if (st == "filled") != (tr is not None):
                mism.append((row["setup_id"], st, tr is not None))
        if tr is not None:
            busy = tr["exit_i"]; per_day[z["day"]] += 1
            row["trade_id_ref"] = f"T-{tr['day']}-{int(tr['_n']):04d}"
            row["status"] = "TRADE"
        rows.append(row)
    return rows, mism


# ------------------------------------------------------------------------------------------------ base
def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def base():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    CF = configs()
    dh = data_hash()
    rep = {"data_hash": dh, "data_commit": subprocess.check_output(["git", "log", "-1", "--format=%h %cs", "--", "data/NQ_5m.csv"],
                                                                     cwd=ROOT).decode().strip(), "configs": {}}
    ledger, sig_rows = [], None
    for nm, c in CF.items():
        P = {**lit.DEFAULTS, **c["lit"]}
        T = F.run(P)
        M, C = F.market(P["ref"], P["extra_boxes"])
        sig_t = {(z["day"], int(z["i"]), int(z["dir"])): int(M.t[z["entry_i"]]) for z in C}
        for n, t in enumerate(sorted(T, key=lambda t: t["entry_t"]), 1):
            t["_sig_t"] = sig_t.get((t["day"], int(t["i"]), int(t["dir"])))
            t["_n"] = n
        ch = cfg_hash(c)
        sk, srun = stored_key(c["run"])
        same = key(T) == sk
        diff = [x for x in key(T) if x not in set(sk)][:5] + [x for x in sk if x not in set(key(T))][:5]
        o = {sp: span_stats(T, a, z) for sp, a, z in SPANS}
        o190 = {sp: span_stats([{**t, "pnl": t["pnl"] - (COMM_MFFU - lit.COMM) * t["qty"]} for t in T], a, z) for sp, a, z in SPANS}
        TP, evs, cfg_used = eval_path_tagged(T, c["eval_cfg"])
        TPs, evs_s, _ = eval_path_tagged(T, c["eval_cfg"], stuck=200.0)
        eos = {sp: span_stats(TPs, a, z) for sp, a, z in SPANS[:3]}
        fe = {"no_stuck_rule": fresh_evals(T, c["eval_cfg"]), "stuck200": fresh_evals(T, c["eval_cfg"], stuck=200.0)}
        post = {}
        for rid, path in (("sizing_cap_lit_eval", TP), ("sizing_cap_lit_eval_stuck200", TPs)):   # stored after the 2026-10-24 cap invariant
            if nm == "pre_switch" and os.path.exists(os.path.join(rl.RUNS, rid + ".json")):
                kk_, _r = stored_key(rid)
                mine = sorted([(x["day"], int(x["entry_t"]), round(float(x["pnl"]), 2), x["exit"], int(x["qty"])) for x in path],
                              key=lambda x: x[1])
                post[rid] = {"same": mine == kk_, "n_mine": len(mine), "n_stored": len(kk_),
                             "net_mine": round(sum(x[2] for x in mine)), "net_stored": round(sum(x[2] for x in kk_))}
        ek, erun = stored_key(c["eval_run"])
        ekey = [(x["day"], int(x["entry_t"]), round(float(x["pnl"]), 2), x["exit"], int(x["qty"])) for x in TP]
        e_same = sorted(ekey, key=lambda x: x[1]) == ek
        eo = {sp: span_stats(TP, a, z) for sp, a, z in SPANS[:3]}
        ev_sum = {sp: dict(collections.Counter(e["result"] for e in evs if e["span"] == sp)) for sp in ("H1", "H2")}
        n5_26 = sum(1 for t in T if t["day"] >= "2026-01-01" and t.get("tf") != 1)
        late = [t for t in T if t["day"] >= "2026-01-01" and et_min(t["entry_t"]) >= 930]
        rs = [t["risk_pts"] for t in T if t["day"] >= "2026-01-01"]
        rep["configs"][nm] = {
            "config_hash": ch, "stored_run": c["run"], "reproduces_stored_run": same, "n_trades_all": len(T), "first_diffs": diff,
            "stored_verdict": srun["verdict"][:900], "LIT_size_rule_1.40": o, "LIT_size_rule_1.90": o190,
            "eval_run": c["eval_run"], "eval_reproduces": e_same, "eval_cfg": cfg_used, "eval_path_1.90": eo, "evals_b2b": ev_sum,
            "eval_path_stuck200_1.90": eos, "evals_b2b_stuck200": {sp: dict(collections.Counter(e["result"] for e in evs_s if e["span"] == sp))
                                                                    for sp in ("H1", "H2")},
            "evals_list": evs, "evals_list_stuck200": evs_s, "fresh_evals": fe, "post_cap_runs": post,
            "eval_stored_verdict": erun["verdict"][:900], "trades_2026_on_5m_fallback": n5_26,
            "fills_after_15_30_2026": [(t["day"], et(t["entry_t"])) for t in late],
            "risk_pts_2026_min_max": [min(rs), max(rs)], "risk_outside_8_80_2026": sum(1 for r in rs if r < 8 or r > 80),
            "exits_2026": dict(collections.Counter(t["exit"] for t in T if t["day"] >= "2026-01-01"))}
        print(nm, ch, "reproduces", c["run"], same, "| eval", c["eval_run"], e_same, json.dumps(o["2026"]), json.dumps(eo), flush=True)
        prof = "LIT_size_rule" + ("" if nm == "current" else "_PRESWITCH")
        if nm == "current":
            ledger += ledger_lit(T, "LIT_size_rule($1.40 engine commission)", ch, dh, lit.COMM)
            ledger += ledger_eval(TPs, T, "two_week_eval_path_b2b_stuck200($1.90)", ch, dh)
            ledger += ledger_eval(TP, T, "two_week_eval_path_b2b_no_stuck_rule($1.90)", ch, dh)
            B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
            sig_rows, mism = signal_ledger(M, C, P, B1, B5, T, ch, dh)
            rep["signal_ledger"] = {"rows": len(sig_rows), "status": dict(collections.Counter(r["status"] for r in sig_rows)),
                                    "first_failing_rule": dict(collections.Counter(r["first_failing_rule"] for r in sig_rows)),
                                    "classifier_mismatches": mism}
        else:
            rep["configs"][nm]["ledger_note"] = f"not written to the ledger ({prof}); reproduced only"
    write_csv(os.path.join(OUT, "COMPLETE_TRADE_LEDGER.csv"), ledger, LEDGER_COLS)
    write_csv(os.path.join(OUT, "SIGNAL_LEDGER_LIT.csv"), sig_rows, list(sig_rows[0].keys()))
    rep["seconds"] = round(time.time() - t0)
    json.dump(rep, open(os.path.join(OUT, "A2_reproduce.json"), "w", encoding="utf-8"), indent=1, default=str)
    print(json.dumps(rep["signal_ledger"], indent=1), flush=True)
    print("done", rep["seconds"], "s")


# ------------------------------------------------------------------------------------------------ robustness
def sess_of(t):
    m = et_min(t["entry_t"])
    return "London 02:00-07:59" if m < 480 else "NY AM 08:00-11:59" if m < 720 else "NY PM 12:00-15:55"


def recost(T, comm=COMM_MFFU, extra_ticks=0, target_too=False):
    """$1.40 engine trades -> `comm` a micro, plus extra adverse ticks on every affected fill (market entry, STOP / BE / EOD /
    CUT exits; a TARGET is a resting limit, so only its entry is affected). The base 1 tick is already in the prices."""
    out = []
    for t in T:
        q = int(t.get("qty_total") or t["qty"])
        fills = 1 + (0 if (t["exit"] == "TARGET" and not target_too) else 1)
        adj = (comm - lit.COMM) * q + extra_ticks * fills * lit.TICK * lit.PV * q
        out.append({**t, "pnl": round(t["pnl"] - adj, 2), "low": round(min(float(t.get("low") or 0.0) - adj, t["pnl"] - adj), 2)})
    return out


def weeks_of(S):
    return sorted({lit.iso_week(d) for d in S})


def boot_ci(T, S, n=5000, seed=20261025):
    """Chronological block bootstrap: ISO weeks of the span are the blocks (a week keeps its trades and their order),
    resampled with replacement to the span's number of weeks. Returns 5/95% of net, PF and $/month."""
    W = weeks_of(S)
    by = collections.defaultdict(list)
    for t in T:
        by[lit.iso_week(t["day"])].append(t["pnl"])
    rng = np.random.default_rng(seed)
    nets, pfs = [], []
    arr = [np.array(by[w]) for w in W]
    for _ in range(n):
        ix = rng.integers(0, len(W), len(W))
        p = np.concatenate([arr[i] for i in ix] + [np.zeros(0)])
        nets.append(p.sum())
        gl = -p[p < 0].sum()
        pfs.append(p[p > 0].sum() / gl if gl else np.nan)
    m = len(S) / 21
    return {"net_ci90": [round(float(np.percentile(nets, 5))), round(float(np.percentile(nets, 95)))],
            "pf_ci90": [round(float(np.nanpercentile(pfs, 5)), 2), round(float(np.nanpercentile(pfs, 95)), 2)],
            "p_net_le0": round(100.0 * float(np.mean(np.array(nets) <= 0)), 2),
            "per_month_ci90": [round(float(np.percentile(nets, 5)) / m), round(float(np.percentile(nets, 95)) / m)]}


def mfe4(T):
    return {(t["day"], int(t["dir"])) for t in T if (t.get("mfe") or 0) >= 4.0}


def row(label, kind, T, base4, S26, note=""):
    S = {nm: [d for d in F.SESS if a <= d <= z] for nm, a, z in SPANS[:3]}
    o = {nm: span_stats(T, a, z) for nm, a, z in SPANS[:3]}
    T26 = [t for t in T if t["day"] >= "2026-01-01"]
    ci = boot_ci(T26, S["2026"])
    k4 = mfe4(T26)
    return {"variant": label, "label": kind, "n": o["2026"]["n"], "tpw": o["2026"]["tpw"], "pf": o["2026"]["pf"], "net": o["2026"]["net"],
            "per_month": o["2026"]["per_month"], "dd": o["2026"]["dd"], "h1_net": o["H1"]["net"], "h1_pf": o["H1"]["pf"],
            "h2_net": o["H2"]["net"], "h2_pf": o["H2"]["pf"], "net_ci90": ci["net_ci90"], "pf_ci90": ci["pf_ci90"],
            "p_net_le0": ci["p_net_le0"], "mfe4_winners": len(k4), "mfe4_retained": len(k4 & base4),
            "mfe4_retention_pct": round(100.0 * len(k4 & base4) / len(base4), 1) if base4 else None, "note": note}


def robust():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    from tools import lit_robust as LR
    P = LR.live_params()
    W = LR.Win(P)
    T0 = W.run()
    run = rl.load("lit_live")
    same = sorted((r[0], int(r[1]), round(r[5], 2)) for r in run["trades"] if r[0] >= "2026-01-01") == \
        sorted((t["day"], int(t["entry_t"]), round(t["pnl"], 2)) for t in T0)
    print("window replay == run lit_live (2026):", same, len(T0), flush=True)
    S26 = W.S
    B = recost(T0)
    base4 = mfe4(B)
    R = [row("BASE live current @ $1.90/micro (+1 tick entry & non-target exits already in)", "BASELINE", B, base4, S26)]
    for k in (1, 2, 4):
        R.append(row(f"+{k} tick(s) per affected fill", "RESEARCH_VARIANT", recost(T0, extra_ticks=k), base4, S26,
                     "post-hoc, linear in micros; entry + non-target exit each worse by k ticks; paths unchanged"))
    for k in (1, 2):
        R.append(row(f"+{k} tick(s) on every fill incl. target limits", "RESEARCH_VARIANT", recost(T0, extra_ticks=k, target_too=True),
                     base4, S26, "post-hoc; stricter: the resting target limit also fills k ticks worse"))
    for nd in (1, 2):
        R.append(row(f"entry latency {nd} min (fills {nd} 1m bar(s) later)", "RESEARCH_VARIANT", recost(W.run({"entry_delay": nd})), base4, S26,
                     "engine option entry_delay: re-simulated; a stop/target touch in the gap = no trade"))
    R.append(row("fee +$0.50/micro ($2.40 round trip)", "RESEARCH_VARIANT", recost(T0, comm=COMM_MFFU + 0.5), base4, S26))
    for d, nm in ((1, "longs only"), (-1, "shorts only")):
        R.append(row(nm, "RESEARCH_VARIANT", [t for t in B if t["dir"] == d], base4, S26, "split of the base, not a strategy"))
    for s in ("London 02:00-07:59", "NY AM 08:00-11:59", "NY PM 12:00-15:55"):
        R.append(row(f"session {s} (by fill time)", "RESEARCH_VARIANT", [t for t in B if sess_of(t) == s], base4, S26, "split of the base"))
    srt = sorted(B, key=lambda t: -t["pnl"])
    for k in (1, 3, 5):
        drop = {(t["day"], int(t["entry_t"])) for t in srt[:k]}
        R.append(row(f"top-{k} winners removed", "RESEARCH_VARIANT", [t for t in B if (t["day"], int(t["entry_t"])) not in drop], base4, S26,
                     "removed: " + ", ".join(f"{t['day']} {t['pnl']:+.0f}" for t in srt[:k])))
    NB = [("disp", 0.7), ("disp", 0.9), ("disp", 1.0), ("depth", 0.4), ("depth", 0.6), ("cisd1m", 18), ("cisd1m", 20), ("cisd1m", 24),
          ("cisd1m", 26), ("idm_age", 24), ("idm_age", 48), ("idm_dist", 0.75), ("idm_dist", 1.25)]
    for k, v in NB:
        if k == "idm_age":
            x = {"idm_a": [P["idm_a"][0], v, P["idm_a"][2]]}
        elif k == "idm_dist":
            x = {"idm_a": [v, P["idm_a"][1], P["idm_a"][2]]}
        else:
            x = {k: v}
        R.append(row(f"neighbour {k}={v} (live {P['idm_a'][1] if k == 'idm_age' else P['idm_a'][0] if k == 'idm_dist' else P[k]})",
                     "RESEARCH_VARIANT", recost(W.run(x)), base4, S26, "full re-simulation on 2026"))
    # months
    mo = collections.defaultdict(list)
    for t in B:
        mo[t["day"][:7]].append(t["pnl"])
    months = [{"month": m, "n": len(v), "net": round(sum(v)), "pf": round(sum(x for x in v if x > 0) / -sum(x for x in v if x < 0), 2)
               if any(x < 0 for x in v) else None} for m, v in sorted(mo.items())]
    out = {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "same_as_lit_live": same,
           "method": "live current config (cisd1m 22), LIT size rule, 2026 sessions, commission $1.90/micro, 1 tick on market entry and "
                     "stop/BE/EOD/CUT exits already in the base; CI = chronological block bootstrap by ISO week (5,000 draws, 90%).",
           "rows": R, "months": months, "seconds": round(time.time() - t0)}
    json.dump(out, open(os.path.join(OUT, "A2_robustness.json"), "w", encoding="utf-8"), indent=1, default=float)
    cols = list(R[0].keys())
    write_csv(os.path.join(OUT, "A2_robustness.csv"), R, cols)
    for r in R:
        print(f"{r['variant'][:60]:60s} n={r['n']:3d} PF {r['pf']} net {r['net']:+9,.0f} H1 {r['h1_net']:+8,.0f} H2 {r['h2_net']:+8,.0f} "
              f"CI {r['net_ci90']} PFci {r['pf_ci90']} mfe4 {r['mfe4_retained']}/{len(base4)}", flush=True)
    print(json.dumps(months))
    print("done", out["seconds"], "s")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("base", "all"):
        base()
    if cmd in ("robust", "all"):
        robust()
