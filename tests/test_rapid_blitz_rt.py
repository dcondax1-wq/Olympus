"""Red team on day-rapidsize (2026-11-23): BLITZ on the Rapid EOD 25K eval. Fakes only, nothing armed.

    python -X utf8 -m tests.test_rapid_blitz_rt        (< 2 s)

1. OFF unless the owner typed the phrase: a Rapid block without "blitz": true gets no lane (FOUND: ON by default + the
   Rapid's existing "armed" = real-money BLITZ on the first restart after landing, nobody typing anything).
2. keep-alive: BLITZ's Rapid lane (LiveBot.acct_rb) is a lane of the Rapid's OWN target (grouped by its Name, key rapid), so a
   keep-alive never fires on top of a BLITZ trade there and sees its fills (FOUND: only NinjaTrader's Log saw them).
3. AccountC.opposite reads ATLAS's combo lanes (LiveBot.acct_x, day-combo25) too: absent here = nothing changes.
"""
from __future__ import annotations

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import keepalive as KA, rapid_blitz as RB  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info != '' and not ok else ''}")
    RES.append(bool(ok))


def main():
    blk = {"account": "Sim-R25", "plan": "mffu_rapid_eod_25k", "stage": "eval", "eval_start": "2026-11-23", "armed": True}
    check("1. an ARMED Rapid 25K eval without \"blitz\": true gets NO BLITZ lane", not RB.wanted(blk)[0], RB.wanted(blk))
    check("1. \"blitz\": true (set only by --blitz on with the typed phrase) gets it", RB.wanted({**blk, "blitz": True})[0])

    nt = lambda acct: types.SimpleNamespace(name="ninjatrader", account=acct)  # noqa: E731
    lane = types.SimpleNamespace(id="rapid", problem=None, spec={"nt_account": "Sim-R25", "adapter": "ninjatrader", "lane": "rapid"},
                                 adapter=nt("Sim-R25"))
    atl = types.SimpleNamespace(problem=None, name="Sim-R25", adapter=nt("Sim-R25"), slot="rapid")
    bz = types.SimpleNamespace(problem=None, name="Sim-R25", adapter=nt("Sim-R25"), slot="rapid")
    bot = types.SimpleNamespace(cfg={"model": "lit"}, adapter=None, state={}, acct_b=None, acct_r=atl, acct_r2=None, acct_c=None,
                                fleet=None, accts=types.SimpleNamespace(accounts=[lane]), acct_rb=None, acct_rb2=None)
    before = [l["key"] for l in KA.lanes(bot)]
    bot.acct_rb = bz
    after = KA.lanes(bot)
    check("2. OFF (acct_rb None): the lanes are as before", "rapid" in before and not any(l["obj"] is bz for l in KA.lanes(
        types.SimpleNamespace(**{**vars(bot), "acct_rb": None}))))
    check("2. ON: BLITZ's Rapid lane is listed (kind acct, key rapid, the Rapid's Name)",
          any(l["obj"] is bz and l["kind"] == "acct" and l["key"] == "rapid" and l["nt"] == "Sim-R25" for l in after), after)
    gs = KA.targets(bot)
    g = next((g for g in gs if g["nt"] == "Sim-R25"), None)
    check("2. ON: ONE target for the Rapid holding LIT's lane, ATLAS and BLITZ",
          len(gs) == 1 and g is not None and {id(l["obj"]) for l in g["lanes"]} == {id(lane), id(atl), id(bz)},
          [(x["key"], [l["kind"] for l in x["lanes"]]) for x in gs])
    src = open(os.path.join(ROOT, "engine", "account_c.py"), encoding="utf-8").read()
    check("3. AccountC.opposite also reads LiveBot.acct_x (combo25 lanes; absent = {})",
          'getattr(b, "acct_x", None) or {}' in src)
    ok = sum(RES)
    print(f"\nrapid blitz red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
