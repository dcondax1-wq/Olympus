"""Red team on day-blitz150 (2026-11-23): research/blitz/learn.py's fresh test needs real evidence. Fakes only.

    python -X utf8 -m tests.test_blitz_learn_rt        (< 2 s)

1. a fix that removes only 3 fresh losers never passes (FOUND: a bootstrap of 3 all-negative R is negative in every
   resample, p = 1/(BOOT+1) = 0.00025 <= 0.05/k, so it "passed" on 3 trades); it waits for 10 removed trades.
2. 12 removed trades that lost R clearly still pass (the guard does not block a real effect).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "research", "blitz")):
    if p not in sys.path:
        sys.path.insert(0, p)

import learn as L  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info != '' and not ok else ''}")
    RES.append(bool(ok))


def rows(n_late, n_other, late_r=-1.0, other_r=0.4):
    out, t = [], 1795600000
    for i in range(n_late + n_other):
        late = i < n_late
        et = t + i * 86400 + (15 * 3600 + 30 * 60 if late else 10 * 3600)       # 15:30 vs 10:00 (UTC-ish offsets; only order matters)
        out.append({"day": "2026-12-%02d" % (1 + i % 28), "entry_t": et, "exit_t": et + 600, "pts": 10.0, "risk": 10.0,
                    "r": late_r if late else other_r, "mode": "paper", "dir": 1})
    return out


def main():
    cid = next((c for c in ("no_late", "no_wide", "no_news", "one_loss_day", "lit_gap30") if c in L.CANDIDATES), None)
    check("setup: a candidate exists", cid is not None, list(L.CANDIDATES))
    orig = L.CANDIDATES[cid]
    try:
        # a fake fix: drop the first `drop` BLITZ trades by entry_t (only the count / R matter for the test)
        def make(drop):
            def f(dts, ctx):
                return [t for t in dts if not (t["strat"] == "BLITZ" and t["entry_t"] in drop)]
            return f
        fr3 = rows(3, 40)
        L.CANDIDATES[cid] = (orig[0], orig[1], make({r["entry_t"] for r in fr3[:3]}))
        r3 = L.fresh_test(cid, fr3, "2026-11-01", k=1, lit=[], news=[])
        check("1. 3 removed losers (all -1R) never pass: waiting for 10", not r3["pass"] and r3["removed"] == 3
              and "waiting" in r3["why"], r3)
        fr12 = rows(12, 40)
        L.CANDIDATES[cid] = (orig[0], orig[1], make({r["entry_t"] for r in fr12[:12]}))
        r12 = L.fresh_test(cid, fr12, "2026-11-01", k=1, lit=[], news=[])
        check("2. 12 removed losers (all -1R) pass at k=1", r12["pass"] and r12["removed"] == 12, r12)
    finally:
        L.CANDIDATES[cid] = orig
    ok = sum(RES)
    print(f"\nblitz learn red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
