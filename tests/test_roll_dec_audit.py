"""December 2026 roll readiness audit (night-roll 2026-11-23): what happens around Thu Dec 10 if the owner does nothing,
and the gaps closed tonight. Fakes only (fake NinjaTrader folder, fake facts), no network. research/handoff/2026-11-23/ROLL.md.

    python -X utf8 -m tests.test_roll_dec_audit        (~2 s)

A. Contract names by date: MNQ / NQ / MES / ES on 12-26 through Wed Dec 9, 03-27 from Thu Dec 10 (the bot's rule: 8 days
   before the Dec 18 expiry); the LE_Feed add-on's list follows by itself.
B. Owner does nothing (chart left on MNQ 12-26): Thu Dec 10 every entry AND the keep-alive's entry is refused (no order file
   to the expiring contract, no order priced on December bars sent to March); a trade opened on 12-26 before midnight is
   closed on 12-26 (its own contract), never on March.
C. READY check (engine/readiness): chart on the old contract on/after the roll = NOT READY with the ROLL.bat fix; the day
   before = one WARN; a matching chart = nothing.
D. TRADING HOME: R runs ROLL.bat and says the result; the status screen names the roll first when it blocks entries.
E. Thanksgiving week: Nov 26 13:00 / Nov 27 13:15 early closes, no roll push that week, the next roll seen from Thanksgiving
   is Dec 10; no full closure.
F. Research data: NQ_rolls.json / ES_rolls.json anchored on the December contract, tools/data_pull records the roll from the
   PC's bars for BOTH symbols (tests/test_dec_roll.py E proves the math).
G. The clock wording: no 'Sync now' left in the swept files.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.ninjatrader import ET, FEED_DIR, feed_instruments, nt_instrument  # noqa: E402
from tests.test_lit_add_safety import World  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info and not ok else ''}")
    RES.append(bool(ok))


def ts(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def chart(w, name):
    d = os.path.join(w.folder, FEED_DIR)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "MNQ_instrument.txt"), "w", encoding="utf-8") as fh:
        fh.write(name)


def names():
    D = dt.date
    ok = all(nt_instrument(r, D(2026, 12, 9)) == f"{r} 12-26" and nt_instrument(r, D(2026, 12, 10)) == f"{r} 03-27"
             for r in ("MNQ", "NQ", "MES", "ES"))
    check("A1. MNQ/NQ/MES/ES: 12-26 through Wed Dec 9, 03-27 from Thu Dec 10", ok)
    f9, f10 = feed_instruments({"sym": "NQ", "signal_root": "MNQ"}, D(2026, 12, 9)), feed_instruments({"sym": "NQ", "signal_root": "MNQ"}, D(2026, 12, 10))
    check("A2. the LE_Feed add-on list follows by itself (MNQ + MES 12-26 -> 03-27)", f9 == ["MNQ 12-26", "MES 12-26"]
          and f10 == ["MNQ 03-27", "MES 03-27"], (f9, f10))


def owner_does_nothing():
    w = World()
    fake = w.fake
    # no entry can open after the 15:55 flat, so nothing is open at the 00:00 switch ...
    w.now[0] = ts(2026, 12, 9, 23, 30) + 3
    ad = w.make("r.json")
    chart(w, "MNQ 12-26")
    fake.move(25020.0)
    r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": int(w.now[0]) - 3})
    check("B1. Wed Dec 9 23:30: entry refused (outside the session): no position can be open at the 00:00 switch",
          not r["ok"] and "outside the session" in r["error"] and not ad.legs, r)
    # ... and even a 12-26 leg still on the books after midnight is closed on its own contract, never on March
    w.now[0] = ts(2026, 12, 9, 10, 0) + 3
    t = int(w.now[0]) - 3
    r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    w.now[0] = ts(2026, 12, 10, 0, 30)
    k = len(fake.files)
    ad.send({"side": "exit", "reason": "audit", "entry_t": t})
    lines = [ln for _, ls in fake.files[k:] for ln in ls]
    check("B2. a 12-26 leg (Wed 10:00) exited after the 00:00 switch: CLOSEPOSITION on MNQ 12-26, nothing to March",
          r["ok"] and any(ln.startswith("CLOSEPOSITION") and "MNQ 12-26" in ln for ln in lines) and not any("03-27" in ln for ln in lines),
          (r, lines))
    # Thu Dec 10 02:05, the chart still on 12-26: no entry, the keep-alive's entry neither
    w.now[0] = ts(2026, 12, 10, 2, 5) + 3
    ad2 = w.make("r2.json")
    k = len(fake.files)
    t2 = int(w.now[0]) - 3
    r = ad2.send({"sym": "NQ", "side": "sell", "qty": 2, "stop": 25050.0, "target": 24900.0, "entry": 25020.0, "entry_t": t2})
    ka = ad2.send({"sym": "NQ", "side": "buy", "qty": 1, "entry": 25020.0, "stop": 25000.0, "target": 25040.0, "entry_t": t2 + 60,
                   "who": "Keep-alive on Zlarior", "reason": "KEEP-ALIVE", "keepalive": True})
    check("B3. Thu Dec 10, chart left on 12-26: LIT's entry refused, no order file", not r["ok"] and "old contract" in r["error"]
          and len(fake.files) == k, r)
    check("B4. ... and the keep-alive's entry is refused the same way (it goes through the same send / roll guard)",
          not ka["ok"] and "old contract" in ka["error"] and len(fake.files) == k, ka)
    chart(w, "MNQ 03-27")
    fake.move(25320.0)
    r = ad2.send({"sym": "NQ", "side": "buy", "qty": 1, "entry": 25320.0, "stop": 25300.0, "target": 25340.0, "entry_t": t2 + 120,
                  "who": "Keep-alive on Zlarior", "reason": "KEEP-ALIVE", "keepalive": True})
    check("B5. chart switched to 03-27: the keep-alive goes to MNQ 03-27", r["ok"] and ad2.legs and ad2.legs[-1]["instrument"] == "MNQ 03-27", r)


def ready():
    from engine import readiness as R, roll_watch as RW
    mon = ts(2026, 12, 10, 1, 15)
    bad = RW.state(mon, "MNQ 12-26", "MNQ")
    v = R.ready_verdict(mon, facts={"checks": [], "hb": {}, "roll": bad})
    b = next((x for x in v["blockers"] if x.get("key") == "roll"), None)
    check("C1. Thu Dec 10 01:15, chart on MNQ 12-26: NOT READY 'Chart still on MNQ 12-26', fix ROLL.bat",
          v["level"] == "NOT_READY" and b and "MNQ 12-26" in b["what"] and "ROLL.bat" in b["exact_fix"], v)
    eve = ts(2026, 12, 9, 1, 15)
    v = R.ready_verdict(eve, facts={"checks": [], "hb": {}, "roll": RW.state(eve, "MNQ 12-26", "MNQ")})
    b = next((x for x in v["blockers"] if x.get("key") == "roll_soon"), None)
    check("C2. Wed Dec 9 (the day before): one WARN 'Contract roll tomorrow', still READY", v["ready"] and b
          and "MNQ 12-26 -> MNQ 03-27" in b["what"] and "ROLL.bat" in b["exact_fix"], v)
    v = R.ready_verdict(mon, facts={"checks": [], "hb": {}, "roll": RW.state(mon, "MNQ 03-27", "MNQ")})
    check("C3. chart on 03-27 on Thu: no roll line", not any(str(x.get("key")).startswith("roll") for x in v["blockers"]), v)
    v = R.ready_verdict(ts(2026, 11, 23, 1, 15), facts={"checks": [], "hb": {}, "roll": RW.state(ts(2026, 11, 23, 1, 15), "MNQ 12-26", "MNQ")})
    check("C4. a normal Monday (Nov 23): no roll line", not any(str(x.get("key")).startswith("roll") for x in v["blockers"]), v)


def trade_home():
    from engine import roll_watch as RW, trade_home as T
    mon = ts(2026, 12, 10, 1, 15)
    bad = RW.state(mon, "MNQ 12-26", "MNQ")
    L, P = T.status_screen(now=mon, bot={"running": True, "last_poll": mon - 30, "trades_today": 0}, accounts=[{"name": "MFFU123456", "armed": True}],
                           keepalive={"x": True}, alerts=(True, False, True), clock=0.2, roll=bad)
    check("D1. status: the roll line says BLOCKED and the first fix is R", any(ln.startswith("  Roll") and "BLOCKED" in ln for ln in L)
          and P and P[0][0] == "R" and L[-1].startswith("  [FIX]"), (L, P))
    L, P = T.status_screen(now=mon, bot={"running": True, "last_poll": mon - 30, "trades_today": 0}, accounts=[{"name": "MFFU123456", "armed": True}],
                           keepalive={"x": True}, alerts=(True, False, True), clock=0.2, roll=RW.state(mon, "MNQ 03-27", "MNQ"))
    check("D2. status with the chart on 03-27: no roll line, all green", not any(ln.startswith("  Roll") for ln in L) and not P, (L, P))
    ran, outs = [], []
    res = T.do_choice("R", out=outs.append, run=lambda a: ran.append(a) or 0, fx={"roll": lambda: RW.state(mon, "MNQ 03-27", "MNQ")})
    check("D3. R runs ROLL.bat and reads the result back ([OK] chart MNQ 03-27)", ran and ran[0][-1].endswith("ROLL.bat")
          and res.startswith("[OK]") and "MNQ 03-27" in res, (ran, res))
    res = T.do_choice("r", out=outs.append, run=lambda a: 0, fx={"roll": lambda: bad})
    check("D4. still on 12-26 after ROLL.bat: [FIX] with the line", res.startswith("[FIX]") and "MNQ 12-26" in res, res)
    check("D5. the menu lists R Contract roll", any(m.strip().startswith("R") and "Contract roll" in m for m in T.MENU), T.MENU)


def thanksgiving():
    from engine import roll_watch as RW
    from engine.cme_calendar import full_closure
    from engine.lit_live import early_close
    D = dt.date
    check("E1. Thanksgiving Thu Nov 26 closes 13:00 ET, Fri Nov 27 13:15 ET, neither a full closure",
          early_close(D(2026, 11, 26)) == 780 and early_close(D(2026, 11, 27)) == 795
          and not full_closure("2026-11-26") and not full_closure("2026-11-27"))
    pushes = [p for d in range(23, 30) for p in RW.countdown(RW.state(ts(2026, 11, d, 12), "MNQ 12-26", "MNQ"), ts(2026, 11, d, 12))]
    check("E2. no roll push in Thanksgiving week (the countdown starts Mon Dec 7)", not pushes, pushes)
    nr = RW.next_roll(D(2026, 11, 26))
    check("E3. from Thanksgiving the next roll is Thu Dec 10, 12-26 -> 03-27", nr == (D(2026, 12, 10), "MNQ 12-26", "MNQ 03-27"), nr)
    soon = [RW.state(ts(2026, 12, d, 12), "MNQ 12-26", "MNQ")["level"] for d in (2, 3, 9)]
    check("E4. the 'soon' line starts Thu Dec 3 (7 days before), after Thanksgiving", soon == ["ok", "soon", "soon"], soon)


def research():
    for sym, anchor in (("NQ", "NQZ26"), ("ES", "ESZ26")):
        d = json.load(open(os.path.join(ROOT, "data", f"{sym}_rolls.json"), encoding="utf-8"))
        check(f"F1. data/{sym}_rolls.json anchored on {anchor} (so the PC's 03-27 bars are detected as the next roll)",
              d.get("anchor") == anchor, d.get("anchor"))
    src = open(os.path.join(ROOT, "tools", "data_pull.py"), encoding="utf-8").read()
    check("F2. tools/data_pull records the roll from the PC's bars for NQ and ES (roll_from_pc in the import loop)",
          'for sym in ("NQ", "ES"):' in src and "roll_from_pc(sym, out_dir, data_dir, days, dry=dry)" in src)


def wording():
    bad = []
    for p in ("engine/pc_cc_api.py", "engine/alerts_plus.py", "engine/golive.py", "engine/ops_checks.py"):
        if "Sync now" in open(os.path.join(ROOT, p), encoding="utf-8").read():
            bad.append(p)
    check("G1. no 'Sync now' left in pc_cc_api / alerts_plus / golive / ops_checks (FIX_CLOCK.bat wording)", not bad, bad)


def main():
    os.environ.pop("LE_LIVE_MODEL", None)
    for fn in (names, owner_does_nothing, ready, trade_home, thanksgiving, research, wording):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{fn.__name__} crashed: {e.__class__.__name__}: {e}", False)
    ok = sum(RES)
    print(f"\nroll audit: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
