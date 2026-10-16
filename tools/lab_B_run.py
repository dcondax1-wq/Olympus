"""Track B runner: evaluate session_po3 variants on a period without writing scorecards (explore), or score them.

  python tools/lab_B_run.py explore --grid research/lab/B_grid_<x>.json      # list of [label, params]
  python tools/lab_B_run.py score --label base --params '{}' --period dev    # writes B_<label>__<period>.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import strategy_lab as lab  # noqa: E402
from tools.lab_models import session_po3 as m  # noqa: E402

_CACHE = {}


def data(period):
    if period not in _CACHE:
        a, z = lab.PERIODS[period] if period in lab.PERIODS else period.split(":")
        nq = lab.bars("NQ", "5m", a, z, warmup_days=10)
        es = lab.bars("ES", "5m", a, z, warmup_days=10)
        _CACHE[period] = (a, z, nq, es)
    return _CACHE[period]


def trades_for(params, period):
    a, z, nq, es = data(period)
    tr = m.run(nq, params, es)
    return [t for t in tr if a <= t["day"] <= z]


def quick(tr, a, z):
    """Cheap summary (no eval sim)."""
    n = len(tr)
    ss = lab.sessions(a, z)
    pn = [t["pnl"] for t in tr]
    gp = sum(x for x in pn if x > 0)
    gl = -sum(x for x in pn if x < 0)
    eq, pk, dd = 0.0, 0.0, 0.0
    byd = collections.defaultdict(float)
    for t in tr:
        byd[t["day"]] += t["pnl"]
    for d in ss:
        eq += byd.get(d, 0.0)
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    return {"n": n, "tpw": round(n / (len(ss) / 5), 2), "wr": round(100 * sum(x > 0 for x in pn) / max(n, 1), 1),
            "pf": round(gp / gl, 2) if gl else 99.0, "net": round(sum(pn), 0), "dd": round(dd, 0),
            "avg_r": round(sum(t["r"] for t in tr) / max(n, 1), 3)}


def halves(tr, period):
    a, z = lab.PERIODS[period] if period in lab.PERIODS else period.split(":")
    if period == "dev":
        cuts = [("Q1", "2026-01-02", "2026-03-31"), ("Q2", "2026-04-01", "2026-06-30")]
    elif period == "confirm":
        cuts = [("Jul-Aug", "2026-07-01", "2026-08-31"), ("Sep-Oct", "2026-09-01", "2026-10-16")]
    else:
        cuts = [("Q1", "2026-01-02", "2026-03-31"), ("Q2", "2026-04-01", "2026-06-30"), ("Q3", "2026-07-01", "2026-09-30"),
                ("Q4", "2026-10-01", "2026-10-16")]
    return {k: quick([t for t in tr if s <= t["day"] <= e], s, e) for k, s, e in cuts}


def fmt(q):
    return f"n={q['n']:3d} tpw={q['tpw']:4.2f} wr={q['wr']:4.1f} PF={q['pf']:5.2f} net={q['net']:+7.0f} dd={q['dd']:6.0f} R={q['avg_r']:+.3f}"


def explore(grid, period="dev", full=False):
    a, z, _, _ = data(period)
    rows = []
    for label, params in grid:
        tr = trades_for(params, period)
        q = quick(tr, a, z)
        hv = halves(tr, period)
        line = f"{label:34s} {fmt(q)} | " + " | ".join(f"{k} n={v['n']} PF={v['pf']} {v['net']:+.0f}" for k, v in hv.items())
        if full:
            s = lab.stats(tr, a, z)
            line += f" | pass={s['rolling_pass']} zero={s['zero_edge_pass']} wk2-5={s['weeks_in_2_5']}"
        print(line, flush=True)
        rows.append((label, q, hv))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["explore", "score"])
    ap.add_argument("--grid")
    ap.add_argument("--label")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--period", default="dev")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--dump")
    x = ap.parse_args()
    if x.cmd == "explore":
        with open(x.grid, encoding="utf-8") as fh:
            g = json.load(fh)
        explore(g, x.period, x.full)
    else:
        p = json.loads(x.params)
        tr = trades_for(p, x.period)
        s = lab.score(tr, f"B_{x.label}", x.period, params={**m.PARAMS, **p})
        for k, v in halves(tr, x.period).items():
            print(f"  {k}: {fmt(v)}")
        print("  months:", {k: (v["trades"], v["net"]) for k, v in s["months"].items()})
        print(f"  weeks_in_2_5={s['weeks_in_2_5']} weeks_zero={s['weeks_zero']} worst_day={s['worst_day']} losing_months={s['losing_months']}")
        if x.dump:
            with open(x.dump, "w", encoding="utf-8") as fh:
                json.dump(tr, fh, indent=0)
