"""Which trades does a candidate change vs the defaults? Per-week R and the added/removed trades.

    python -X utf8 study_combo_night_diff.py [--sym NQ] [--from ..] [--to ..] [--cand '{"w_htf": 0}']
"""
import argparse
import datetime as dt
import json

from engine import backtest

RESEARCH = {"dd_aware": False, "daily_max_loss": 1e9, "memory_seed": False}


def wk(d):
    x = dt.date.fromisoformat(d)
    return (x - dt.timedelta(days=x.weekday())).isoformat()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", default="NQ"); ap.add_argument("--from", dest="a", default="2026-08-06")
    ap.add_argument("--to", dest="z", default="2026-10-16"); ap.add_argument("--cand", default='{"w_htf": 0}')
    A = ap.parse_args()
    cand = json.loads(A.cand)
    f = lambda p: [t for t in backtest.run(A.sym, "5m", {**p, **RESEARCH}, light=True)["trades"] if A.a <= t["day"] <= A.z]
    d0, d1 = f({}), f(cand)
    k = lambda t: (t["entry_t"], t["dir"])
    s0, s1 = {k(t): t for t in d0}, {k(t): t for t in d1}
    print(f"{A.sym} defaults {len(d0)} trades {sum(t['pnl_r'] for t in d0):+.2f}R | cand {cand} {len(d1)} trades {sum(t['pnl_r'] for t in d1):+.2f}R")
    for lab, ks, src in (("only in defaults", s0.keys() - s1.keys(), s0), ("only in candidate", s1.keys() - s0.keys(), s1)):
        print(f"-- {lab}")
        for x in sorted(ks):
            t = src[x]
            print(f"   {t['day']} {'L' if t['dir'] == 1 else 'S'} {t['trigger']:5s} grade {t['grade']:2s} score {t['score']:+d} htf {t['htf_trend']:+d} "
                  f"{t['exit_reason']:12s} {t['pnl_r']:+.2f}R")
    same = [x for x in s0.keys() & s1.keys() if abs(s0[x]["pnl_r"] - s1[x]["pnl_r"]) > 1e-6]
    print(f"-- common trades with different outcome: {len(same)}")
    print("-- per-week sum R: week | defaults | candidate")
    for w in sorted(set(wk(t["day"]) for t in d0 + d1)):
        print(f"   {w} | {sum(t['pnl_r'] for t in d0 if wk(t['day']) == w):+.2f} | {sum(t['pnl_r'] for t in d1 if wk(t['day']) == w):+.2f}")
