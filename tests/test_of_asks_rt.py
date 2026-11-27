"""Red team #29 (night-of-asks): the "of" ask dedup is ONE per answering night (16:00 ET .. next 15:59), never a sliding 20 h that
skips the next night; "bf" (backfill) asks are never swallowed by it.
    python -X utf8 -m tests.test_of_asks_rt
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import datafeed as D        # noqa: E402

R = []
E = ZoneInfo("America/New_York")


def ts(*a):
    return int(dt.datetime(*a, tzinfo=E).timestamp())


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    st = {"sent": [{"t": ts(2026, 11, 23, 23, 0), "page": 1, "req": "abc", "day": "2026-11-23"}]}
    check("a 2nd cloud ask the SAME night (00:30) is a duplicate", D.of_answered_recently(st, ts(2026, 11, 24, 0, 30)))
    check("the NEXT night's ask (17:00, 18 h later) is answered", not D.of_answered_recently(st, ts(2026, 11, 24, 17, 0)))
    st2 = {"sent": [{"t": ts(2026, 11, 23, 23, 0), "page": 1, "req": "push1a2b", "day": "2026-11-23"}]}
    check("the owner's own push never blocks a cloud ask", not D.of_answered_recently(st2, ts(2026, 11, 24, 0, 30)))
    st3 = {"sent": [], "bf_sent": [{"t": ts(2026, 11, 23, 23, 0), "page": 1, "req": "bf1"}]}
    check("a backfill page (bf_sent) never blocks an 'of' ask", not D.of_answered_recently(st3, ts(2026, 11, 24, 0, 30)))
    print(f"\nof asks red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
