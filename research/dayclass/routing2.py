"""Round 2 (DESIGN.md addendum): BLITZ only, later checkpoints C4 11:30 / C5 12:30 / C6 13:30. PAPER RESEARCH ONLY.

    python -X utf8 research/dayclass/routing2.py   -> research/dayclass/routing2.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import routing as RT  # noqa: E402

NY = zoneinfo.ZoneInfo("America/New_York")


def ck_late(entry_t):
    e = dt.datetime.fromtimestamp(entry_t, NY)
    m = e.hour * 60 + e.minute
    if 1080 > m >= 810:
        return "C6"
    if 1080 > m >= 750:
        return "C5"
    if 1080 > m >= 690:
        return "C4"
    return RT._ck_r1(entry_t)


RT._ck_r1 = RT.ck_of
RT.ck_of = ck_late
RT.N_TESTS = 19
RT.OUT = os.path.join(HERE, "routing2.json")
RT.RULES = {"blitz": [("R2-B1 skip: top = range", lambda v: 0.0 if v[0] == "range" else 1.0),
                      ("R2-B2 x0.5: top = range", lambda v: 0.5 if v[0] == "range" else 1.0),
                      ("R2-B3 skip: P(range) >= 0.60", "prange"),
                      ("R2-B4 x1.5: top = trend with", lambda v: 1.5 if v[0] == "trend_with" else 1.0)]}

_view = RT.view


def view2(C, t, oracle=False):
    v = _view(C, t, oracle)
    if v is None:
        return None
    x = C[RT.ck_of(t["entry_t"])].get(t["day"])
    pr = 1.0 if oracle and x[1] == "range" else (0.0 if oracle else float(x[0][0]))
    return v + (pr,)


RT.view = view2
_mults = RT.mults


def mults2(T, C, rule, rkey, oracle=False):
    if rule == "prange":
        rule = lambda v: 0.0 if v[4] >= 0.60 else 1.0  # noqa: E731
    return _mults(T, C, rule, rkey, oracle)


RT.mults = mults2
_acc = json.load(open(os.path.join(HERE, "accuracy.json")))
if __name__ == "__main__":
    RT.main(["--n", "300"])
