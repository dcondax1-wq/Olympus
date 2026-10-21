"""Dashboard research files for LIT (the live strategy since 2026-10-18), in the same shape the Evals and Intraday pages read.

  python tools/lit_dash_data.py            # both files
  python tools/lit_dash_data.py mc         # research/lab/montecarlo.json only
  python tools/lit_dash_data.py heat       # research/lab/intraday_heat.json only
  python tools/lit_dash_data.py intel      # research/lab/trade_intel.json only (tools/trade_intel.py; "all" rebuilds it only
                                           # when run lit_live changed)

montecarlo.json   MFFU Builder 50K Monte Carlo on LIT's 2026 sessions (stored run lit_live = the live settings, costs in):
                  4,000 resampled 60-session paths in 5-session blocks (tools/research_mc.py's eval engine: $3,000 target,
                  $2,000 end-of-day trailing max loss checked against the intraday low, locks at $50,100). "press" is the
                  fast-eval sizing switch (lit_sizing.mode fast_eval, run lit_x_fast_eval: $800 up to a 40-pt stop), OFF live.
                  Also the exact rolling evals (a fresh eval on every session) for 2026, its two halves and 2021-25 (reference).
intraday_heat.json  LIT replay trades (research/lab/backtest_live.json) by weekday x ET entry hour, 01:00-16:00 (LIT enters
                  02:00-15:30, London included). cells = 2026 (LIT is judged on 2026); periods = 2026 H1 / H2 / 2021-25 reference.

The previous strategy's versions are kept in research/archive/engine-2026-10-17/.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import research_mc as mc      # noqa: E402

LAB = os.path.join(ROOT, "research", "lab")
RUNS = os.path.join(ROOT, "research", "runs")
ET = ZoneInfo("America/New_York")
LIVE_RUN, FAST_RUN = "lit_live", "lit_x_fast_eval"
POOLS = {"2026": ("2026-01-01", "2026-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 H2": ("2026-07-01", "2026-12-31"),
         "2021-25": ("2021-01-01", "2025-12-31"), "all": ("2000-01-01", "2100-01-01")}


def _load(name):
    with open(os.path.join(RUNS, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def _data(run):
    """research_mc's per-session arrays from a stored run's day list [date, pnl, low, trades] (no cold-streak state: LIT has none)."""
    cols = run["day_cols"]
    ix = {c: i for i, c in enumerate(cols)}
    days = sorted(run["days"], key=lambda d: d[ix["date"]])
    sess = [d[ix["date"]] for d in days]
    pnl = np.array([float(d[ix["pnl"]]) for d in days])
    low = np.array([float(d[ix["low"]]) for d in days]) if "low" in ix else np.minimum(pnl, 0.0)
    cold = np.zeros(len(sess), dtype=bool)
    return {"sessions": sess, "N": len(sess), "pnl": pnl, "low": low, "ntr": np.array([int(d[ix.get("trades", 3)] or 0) for d in days]),
            "cold": cold, "streak": mc.streak_lengths(cold)}


def _prob(r):
    return {"pass_2w": r["pass_2w"], "fail_2w": r["fail_2w"], "pass_3w": r["pass_3w"], "fail_3w": r["fail_3w"],
            "pass_4w": r["pass_4w"], "fail_4w": r["fail_4w"], "pass_6w": r["pass_6w"], "fail_6w": r["fail_6w"],
            "pass_60": r["pass_60"], "fail_60": r["fail_60"], "open_60": r["open_60"],
            "pass_days_median": r["pass_days"]["median"], "pass_days_p90": r["pass_days"]["p90"],
            "dd_median": r["dd"]["median"], "dd_p90": r["dd"]["p90"], "dd_worst": r["dd"]["worst"]}


def _pick(paths, n=300):
    """Mixed outcomes for the fan / 3D view: proportional, at least 40 of each outcome when there are that many."""
    by = collections.defaultdict(list)
    for p in paths:
        by[p["result"]].append(p)
    pick = []
    for res in ("PASS", "FAIL", "OPEN"):
        pick.extend(by[res][:max(40, int(round(n * len(by[res]) / max(1, len(paths)))))])
    pick = pick[:n]
    if len(pick) < n:
        pick.extend([p for p in paths if p not in pick][:n - len(pick)])
    return pick


def montecarlo(n=4000, seed=7):
    mc.POOLS.update(POOLS)                              # research_mc's pool table gains the 2026 halves
    live, fast = _load(LIVE_RUN), _load(FAST_RUN)
    D, F = _data(live), _data(fast)
    main = mc.simulate(D, "2026", "block5", "live", n=n, seed=seed, keep_paths=900)
    press = mc.simulate(F, "2026", "block5", "live", n=n, seed=seed)
    cases = []
    for name, data in (("live", D), ("fast_eval", F)):
        for pool in ("2026", "2026 H1", "2026 H2"):
            for scheme in ("block5", "iid"):
                r = main if (name, pool, scheme) == ("live", "2026", "block5") else \
                    press if (name, pool, scheme) == ("fast_eval", "2026", "block5") else mc.simulate(data, pool, scheme, "live", n=n, seed=seed)
                cases.append({**{k: v for k, v in r.items() if k != "paths"}, "sizing": name})
    exact = []
    for name, data in (("live", D), ("fast_eval", F)):
        for pool in ("2026", "2026 H1", "2026 H2", "2021-25"):
            exact.append({**mc.exact_rolling(data, pool, "live"), "sizing": name})
    chain = {"locked": mc.chains(D, "2026", "block5", "live", n=2000), "press": mc.chains(F, "2026", "block5", "live", n=2000)}
    s26 = live["spans"]["2026"]
    out = {
        "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "lit_mc", "strategy_model": "lit",
        "writeup": "research/writeups/lit-final.md",
        "strategy": ("LIT (live_model.json): lit_final + loss pack (weekly stop, Monday rule, 2026-10-18) + 15-minute check, "
                     "scale-in after breakeven, breakeven at entry + 1.25 pts (2026-10-20); LIT size rule ($800 up to a 20-pt stop)"),
        "plan": "MFFU Builder 50K: +$3,000 target, $2,000 EOD trailing max loss (intraday low checked), locks at $50,100",
        "method": (f"{n} resampled 60-session evals drawn in blocks of 5 consecutive sessions from LIT's 2026 sessions "
                   f"(run {LIVE_RUN}, Jan 2 - Oct 16 2026, {sum(1 for d in D['sessions'] if d.startswith('2026'))} sessions, costs in). "
                   "LIT is judged on 2026 only (picked on Jan-Jun, checked on Jul-Oct); the H2 rows are the honest rate. "
                   f"Exact rolling evals on the real 2026 history: pass/fail within 2 weeks {s26.get('p10')}% / {s26.get('f10')}%, "
                   f"within 1 month {s26.get('p20')}% / {s26.get('f20')}%."),
        "paths": _pick(main["paths"]), "paths_pool": "2026, block5, LIT live sizing",
        "hist": main["hist"], "prob": _prob(main), "press": _prob(press),
        "press_rule": (f"fast-eval sizing switch (lit_sizing.mode fast_eval, run {FAST_RUN}): $800 of risk up to a 40-point stop, "
                       "then $800 x 40 / stop; OFF in the live settings (stored on the LIT final rules, without the loss pack "
                       "and the 2026-10-20 upgrades)"),
        "chain": chain, "cases": cases, "exact": exact,
        "halves": {k: _prob(next(c for c in cases if c["sizing"] == "live" and c["pool"] == k and c["scheme"] == "block5"))
                   for k in ("2026 H1", "2026 H2")},
    }
    path = os.path.join(LAB, "montecarlo.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), default=float)
    p = out["prob"]
    print(f"wrote research/lab/montecarlo.json ({os.path.getsize(path) // 1024} KB): LIT 2026 block5 pass/fail 2 wk {p['pass_2w']}/{p['fail_2w']}%, "
          f"4 wk {p['pass_4w']}/{p['fail_4w']}%, 60 sessions {p['pass_60']}/{p['fail_60']}/{p['open_60']}%, median {p['pass_days_median']} sessions; "
          f"fast-eval 2 wk {out['press']['pass_2w']}/{out['press']['fail_2w']}%; H2 2 wk {out['halves']['2026 H2']['pass_2w']}/{out['halves']['2026 H2']['fail_2w']}%")
    return out


def heat():
    with open(os.path.join(LAB, "backtest_live.json"), encoding="utf-8") as fh:
        bt = json.load(fh)
    if (bt.get("meta") or {}).get("model") != "lit":
        raise SystemExit("research/lab/backtest_live.json is not the LIT replay: run python tools/export_backtest.py first")
    hours = list(range(1, 16))
    trades = []
    for t in bt.get("trades") or []:
        e = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
        if e.weekday() > 4:
            continue
        trades.append((str(t["day"]), e.weekday(), e.hour, float(t.get("r") or 0), float(t.get("pnl") or 0)))

    def cells(a, z):
        out = []
        for d in range(5):
            for h in hours:
                xs = [x for x in trades if a <= x[0] <= z and x[1] == d and x[2] == h]
                n = len(xs)
                w = round(100.0 * sum(1 for x in xs if x[4] > 0) / n, 1) if n else 0.0
                out.append({"dow": d, "hour": h, "n": n, "avg_r": round(sum(x[3] for x in xs) / n, 3) if n else 0.0,
                            "net": round(sum(x[4] for x in xs)), "win": w, "win_pct": w})
        return out
    H = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "strategy_model": "lit",
         "source": "LIT replay (research/lab/backtest_live.json, run lit_live settings), live sizing, costs included",
         "cells_label": "2026", "dow_labels": ["Mon", "Tue", "Wed", "Thu", "Fri"], "hours": hours,
         "note": "LIT enters 02:00-15:30 ET (London and New York). 2026 is the judged year: picked on Jan-Jun, checked on Jul-Oct; "
                 "2021-25 has no 1-minute data, so it is a reference line only.",
         "cells": cells("2026-01-01", "2026-12-31"),
         "periods": {"2026 H1": cells("2026-01-01", "2026-06-30"), "2026 H2": cells("2026-07-01", "2026-12-31"),
                     "2021-25 (reference)": cells("2021-01-01", "2025-12-31")}}
    path = os.path.join(LAB, "intraday_heat.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(H, fh, indent=1)
    n26 = sum(c["n"] for c in H["cells"])
    early = sum(c["n"] for c in H["cells"] if c["hour"] < 8)
    print(f"wrote research/lab/intraday_heat.json: {n26} trades in 2026 ({early} entered before 08:00 ET), hours {hours[0]:02d}-{hours[-1]:02d}")
    return H


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "heat"):
        heat()
    if what in ("all", "mc"):
        montecarlo()
    if what in ("all", "intel"):
        from tools import trade_intel
        trade_intel.build()
