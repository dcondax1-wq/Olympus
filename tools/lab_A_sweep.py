"""Track A: Liquidity Engine -> straight rules, parameters only (engine/** untouched).

Runs batches of engine variants through the exact live-loop replay used by tools/strategy_lab.py (engine_trades), in one
4-process pool per batch, and records the shared scorecard (strategy_lab.stats/gate) plus Jan-Mar / Apr-Jun halves.

  python tools/lab_A_sweep.py --group one          # predefined group of variants (see GROUPS)
  python tools/lab_A_sweep.py --variants '{"x": {...}}' [--base S]   # ad-hoc variants (deltas on a base)
  python tools/lab_A_sweep.py --table              # print the sweep table

Raw trades/days go to research/lab/A_trades/<name>__<period>.json (a subfolder, so LEADERBOARD.md ignores them), and the
summary row to research/lab/A_trades/sweep.jsonl. Only --score writes a research/lab/A_<name>__<period>.json scorecard.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import five_year as fy  # noqa: E402
from tools import strategy_lab as SL  # noqa: E402

OUTD = os.path.join(ROOT, "research", "lab", "A_trades")
HALVES = {"dev": [("H1", "2026-01-02", "2026-03-31"), ("H2", "2026-04-01", "2026-06-30")],
          "confirm": [("Q3", "2026-07-01", "2026-09-30"), ("Q4", "2026-10-01", "2026-10-16")],
          "ytd": [("Q1", "2026-01-02", "2026-03-31"), ("Q2", "2026-04-01", "2026-06-30"),
                  ("Q3", "2026-07-01", "2026-09-30"), ("Q4", "2026-10-01", "2026-10-16")]}

# straight-rules base: fixed $350 risk (no grade / conviction / drawdown-aware / trending-half sizing), no learned exits
STRAIGHT = {"grade_sizing": False, "conviction_step": 0, "dd_aware": False, "exit_learn": False, "memory_seed": False}
BASES = {
    "D": {},                                                  # engine defaults
    "S": {**STRAIGHT, "regime_mode": "skip"},                 # straight, trending regime skipped
    "S0": {**STRAIGHT, "regime_er10_max": 0},                 # straight, no regime filter
}

ONE = {  # one-at-a-time deltas
    "base": {},
    "max1": {"max_trades_day": 1},
    "no_saw": {"stop_after_win": False},
    "ifvg_only": {"use_cisd": False},
    "cisd_only": {"spec": {"min_fvg": 999.0}},
    "ifvg_outer": {"ifvg_pick": "outer"},
    "ifvg_15m": {"ifvg_tf": "highest"},
    "am_only": {"entry_windows": [[570, 690]]},
    "pm_only": {"entry_windows": [[810, 930]]},
    "ext_win": {"entry_windows": [[570, 720], [780, 930]]},
    "am_long": {"entry_windows": [[570, 720]]},
    "arm_minor_off": {"arm_minor": False},
    "arm_exp30": {"arm_expiry_min": 30},
    "arm_exp90": {"arm_expiry_min": 90},
    "score0": {"min_score": 0},
    "score_off": {"min_score": -9},
    "score2": {"min_score": 2},
    "w_htf0": {"w_htf": 0},
    "w_lrl0": {"w_lrl": 0},
    "w_m15_0": {"w_m15": 0},
    "w_pd0": {"w_pd": 0},
    "maxstop45": {"spec": {"max_stop": 45.0}},
    "maxstop80": {"spec": {"max_stop": 80.0}},
    "minstop15": {"spec": {"min_stop": 15.0}},
    "stop_ifvg": {"stop_mode": "ifvg"},
    "tgt_dol": {"target_mode": "dol"},
    "tgt_fixed2": {"target_mode": "fixed", "fallback_rr": 2.0},
    "tgt_fixed3": {"target_mode": "fixed", "fallback_rr": 3.0},
    "minrr1": {"min_rr": 1.0},
    "minrr2": {"min_rr": 2.0},
    "maxrr3": {"max_rr": 3.0},
    "maxrr8": {"max_rr": 8.0},
    "be_off": {"be_at_r": 0},
    "be_1.5": {"be_at_r": 1.5},
    "tstop0": {"time_stop_min": 0},
    "tstop60": {"time_stop_min": 60},
    "no_giveback": {"exit_rules": ""},
    "regime_off": {"regime_er10_max": 0},
    "regime_0.35": {"regime_er10_max": 0.35},
    "range_off": {"day_range_max": 0},
    "range_1.2": {"day_range_max": 1.2},
    "trend_model": {"trend_model": True},
    "news_off": {"news_filter": False},
}
GROUPS = {"one": ONE}


def run_variants(variants: dict, period="dev", procs=4):
    """variants: {name: full_params}. Returns {name: (trades, days)} exactly as strategy_lab.engine_trades builds them."""
    s0, s1 = SL.PERIODS[period]
    jobs = []
    for name, p in variants.items():
        jobs += [j for j in fy.live_jobs(p, name) if s0 <= j[2] <= s1]
    with Pool(procs) as pool:
        outs = pool.map(fy.bt, jobs, chunksize=4)
    by = collections.defaultdict(list)
    for o in outs:
        by[o["label"].rsplit(":", 1)[0]].append(o)
    res = {}
    for name in variants:
        m = fy.merge(by[name], name)
        trades = [{**t, "setup": t.get("trigger") or "engine"} for t in m["trades"]]
        days = [{"date": d["date"], "pnl": d["pnl"], "low": d["low"], "trades": d.get("trades", 0)} for d in m["days"]]
        res[name] = (trades, days)
    return res


def summarize(name, params, delta, trades, days, period):
    a, z = SL.PERIODS[period]
    s = SL.stats(trades, a, z, given_days=days)
    g = SL.gate(s)
    row = {"name": name, "period": period, "delta": delta, "params": params,
           **{k: s[k] for k in ("trades", "tpw", "weeks_in_2_5", "weeks_zero", "win_rate", "avg_r", "ci95_r", "pf", "net",
                                "max_dd", "worst_day", "losing_months", "rolling_pass", "zero_edge_pass", "b2b_pass", "b2b_fail")},
           "months": s["months"], "gate": g["ok"], "fails": [k for k, v in g["checks"].items() if not v], "halves": {}}
    for h, ha, hz in HALVES[period]:
        tr = [t for t in trades if ha <= t["day"] <= hz]
        pnl = [t["pnl"] for t in tr]
        gp, gl = sum(x for x in pnl if x > 0), -sum(x for x in pnl if x < 0)
        nd = sum(1 for d in days if ha <= d["date"] <= hz)
        row["halves"][h] = {"trades": len(tr), "tpw": round(len(tr) / max(nd / 5, 1e-9), 2), "net": round(sum(pnl), 0),
                            "pf": round(gp / gl, 2) if gl > 0 else None,
                            "wr": round(100 * sum(1 for x in pnl if x > 0) / len(pnl), 1) if pnl else 0.0,
                            "avg_r": round(sum(t["r"] for t in tr) / len(tr), 3) if tr else 0.0}
    return row


def fmt(r):
    h = r["halves"]
    hs = " | ".join(f"{k}:{v['trades']}t {v['net']:+6.0f} pf{v['pf']}" for k, v in h.items())
    return (f"{r['name']:28s} n={r['trades']:3d} tpw={r['tpw']:.2f} wr={r['win_rate']:5.1f} avgR={r['avg_r']:+.3f} "
            f"PF={r['pf']} net={r['net']:+7.0f} dd={r['max_dd']:7.0f} wd={r['worst_day']:6.0f} pass={r['rolling_pass']}"
            f"({r['zero_edge_pass']}) wk2-5={r['weeks_in_2_5']:.0f}% || {hs} || {'GATE' if r['gate'] else ','.join(r['fails'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group")
    ap.add_argument("--variants")
    ap.add_argument("--base", default="S")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--period", default="dev")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--only", default="")
    ap.add_argument("--score", action="store_true", help="also write the shared research/lab/A_<name>__<period>.json scorecard")
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUTD, exist_ok=True)
    if a.table:
        with open(os.path.join(OUTD, "sweep.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                print(fmt(json.loads(line)))
        return
    if a.period != "dev" and not a.score:
        sys.exit("confirm/ytd runs must go through the logged scorecard (--score)")
    deltas = GROUPS[a.group] if a.group else json.loads(a.variants)
    if a.only:
        keep = set(a.only.split(","))
        deltas = {k: v for k, v in deltas.items() if k in keep}
    base = BASES[a.base]
    full = {}
    for k, dlt in deltas.items():
        p = {**base, **dlt}
        if "spec" in base and "spec" in dlt:
            p["spec"] = {**base["spec"], **dlt["spec"]}
        full[f"{a.prefix}{a.base}_{k}"] = (p, dlt)
    t0 = time.time()
    res = run_variants({n: v[0] for n, v in full.items()}, a.period, a.procs)
    with open(os.path.join(OUTD, "sweep.jsonl"), "a", encoding="utf-8") as fh:
        for n, (trades, days) in res.items():
            p, dlt = full[n]
            with open(os.path.join(OUTD, f"{n}__{a.period}.json"), "w", encoding="utf-8") as tf:
                json.dump({"params": p, "trades": trades, "days": days}, tf, default=float)
            row = summarize(n, p, dlt, trades, days, a.period)
            fh.write(json.dumps(row, default=float) + "\n")
            print(fmt(row), flush=True)
            if a.score:
                SL.score(trades, f"A_{n}", a.period, given_days=days, params=p)
    print(f"{len(res)} variants in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
