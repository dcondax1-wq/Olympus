"""BLITZ later-break size (research/writeups/atlas-blitz-edge-2026-10-30.md, research/scalp/blitz_25k_pick_v2.json): ON by default
since the owner approved it (2026-10-31); "later_break": false in data/account_c.json turns it off. engine/blitz counts the day's check closes beyond the band per side
("brk_n" on every signal and entry, traded or not); engine/account_c.qty sizes the eval x0.5 on the day's first break of a side
and x1.75 on a later one (f <= 1.0, the $ cap scales). Funded / paper sizing and the switch off = today's size.

  python -X utf8 -m tests.test_blitz_later_break          # ~1 min (the engine count runs on 2026 1m bars)
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import account_c as AC, blitz as BZ  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {info}"), flush=True)


def spec(**kw):
    s = AC.normalize({"account": "Sim103", "plan": "builder25k", "eval_start": "2026-11-02", **kw})
    return s


def main():
    st = {"room": 1000.0, "cum": 0.0, "session": 2}
    base = AC.qty(spec(later_break=False), 20.0, st)
    off2 = AC.qty(spec(later_break=False), 20.0, st, brk_n=2)
    check("switch off: brk_n changes nothing", base["qty"] == off2["qty"] > 0, (base, off2))
    on1 = AC.qty(spec(later_break=True), 20.0, st, brk_n=1)
    on2 = AC.qty(spec(later_break=True), 20.0, st, brk_n=2)
    rp = (20.0 + BZ.TICK) * AC.PV + AC.COMM
    check("switch on: first break = 0.5 x (20% of the room, cap $300)", on1["qty"] == int(min(300.0, 0.2 * 1000.0, 0.9 * 600.0) // rp), on1)
    check("switch on: later break = 1.75 x (70% of the room, cap $1,050)", on2["qty"] == int(min(1050.0, 0.7 * 1000.0, 0.9 * 600.0) // rp), on2)
    st5 = {"room": 1000.0, "cum": 0.0, "session": 6}
    on5 = AC.qty(spec(later_break=True), 20.0, st5, brk_n=3)
    check("from session 5 (full room) a later break stays <= 100% of the room", on5["qty"] == int(min(1050.0, 1.0 * 1000.0, 0.9 * 600.0) // rp), on5)
    pap = AC.qty(spec(later_break=True, sizing="paper"), 20.0, st, brk_n=2)
    check("paper sizing ignores it", pap["qty"] == AC.qty(spec(sizing="paper"), 20.0, st)["qty"], pap)
    check("a missing brk_n (older engine state) = today's size", AC.qty(spec(later_break=True), 20.0, st)["qty"] == base["qty"])
    check("the switch is on by default (owner 2026-10-31); false turns it off",
          spec()["later_break"] is True and spec(later_break=False)["later_break"] is False
          and AC.qty(spec(), 20.0, st, brk_n=2)["qty"] == on2["qty"])
    # the engine's per-side count on real 2026 bars: every signal carries brk_n = 1, 2, ... per side and day
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    df = df[(df["time"] >= 1772323200) & (df["time"] < 1777593600)]            # 2026-03-01 .. 2026-05-01
    eng = BZ.Engine(filtered=True)
    sigs = []
    for r in df.itertuples(index=False):
        for e in eng.on_bar(int(r.time), r.open, r.high, r.low, r.close):
            if e.get("ev") == "signal":
                sigs.append(e)
    ok, last = True, {}
    for s in sigs:
        k = (s["date"], s["dir"])
        want = last.get(k, 0) + 1
        ok = ok and s.get("brk_n") == want
        last[k] = want
    check(f"engine: brk_n counts each side's band breaks per day ({len(sigs)} signals, Mar-Apr 2026)", ok and len(sigs) > 20,
          [(s["date"], s["dir"], s.get("brk_n")) for s in sigs[:6]])
    check("engine: later breaks exist (brk_n >= 2 on some signals)", any((s.get("brk_n") or 0) >= 2 for s in sigs))
    print(f"\nBLITZ later-break: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
