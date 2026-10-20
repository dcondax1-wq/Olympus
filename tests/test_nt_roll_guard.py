"""Roll guard on the NinjaTrader route (engine/ninjatrader.place_bracket): the LE_BarFeed chart left on MNQ 12-26 after the
order contract switched to MNQ 03-27 (Thu 2026-12-10 00:00 ET) must not send an entry with December-priced stop/target.

    python -X utf8 -m tests.test_nt_roll_guard        (~1 s, fake NinjaTrader, no network)

1. le_feed/MNQ_instrument.txt = "MNQ 12-26" on 2026-12-10 (orders -> MNQ 03-27): entry refused, no order file, alert text
   "Chart is on the old contract (MNQ 12-26): switch it to MNQ 03-27".
2. Chart on "MNQ 03-27": the entry goes through.
3. No instrument file (an older LE_BarFeed): no check; but a fill ~330 pts from the chart's price (the backstop) places no
   bracket and flattens at once.
4. Before the roll (2026-12-09, orders on 12-26) a 12-26 chart passes.
5. Default fill-gap limit 0.3% (nt_max_fill_gap_pct): a 0.5% gap is flattened, a 24-pt offset (the worst 2026 LIT entry
   bar vs the model price was 0.08%) is not. The last 8 NQ rolls were 0.86-1.36% of price.
6. A late entry fill (reported after place_bracket returned) a roll gap away is flattened in tick(), never protected.
7. A continuous-contract chart ("MNQ ##-##") turns the contract check off: loud alert once a day.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.ninjatrader import ET, FEED_DIR  # noqa: E402
from tests.test_lit_add_safety import World  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info and not ok else ''}")
    RES.append(bool(ok))


def chart(w, name):
    d = os.path.join(w.folder, FEED_DIR)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "MNQ_instrument.txt")
    if name is None:
        if os.path.exists(p):
            os.remove(p)
        return
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(name)


def main():
    w = World()
    fake = w.fake
    w.now[0] = dt.datetime(2026, 12, 10, 3, 0, 3, tzinfo=ET).timestamp()
    ad = w.make("r.json")
    check("order contract on 2026-12-10 is MNQ 03-27", ad._instruments()["micro"] == "MNQ 03-27", ad._instruments())
    t = int(w.now[0]) - 3
    fake.move(25330.0)
    chart(w, "MNQ 12-26")
    k, na = len(fake.files), len(w.alerts)
    r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    check("1. chart on MNQ 12-26, orders on MNQ 03-27 -> entry refused, no order file, alert",
          not r["ok"] and "Chart is on the old contract (MNQ 12-26): switch it to MNQ 03-27" in r["error"]
          and len(fake.files) == k and not ad.legs and len(w.alerts) > na
          and "switch it to MNQ 03-27" in w.alerts[-1], [r, w.alerts[-1:]])
    chart(w, "MNQ 03-27")
    r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 25300.0, "target": 25400.0, "entry": 25330.0, "entry_t": t})
    check("2. chart on MNQ 03-27 -> entry and bracket go in", r["ok"] and ad.legs and ad.legs[0]["status"] == "protected", r)
    ad.send({"side": "exit", "reason": "x", "entry_t": t})
    # 3. no instrument file, chart prices ~310 pts under the March fill: the fill-gap backstop flattens
    chart(w, None)
    w.now[0] += 1800
    t = int(w.now[0]) - 3
    k = len(fake.files)
    r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    lines = [ln for _, ls in fake.files[k:] for ln in ls]
    check("3. unknown chart contract + fill 310 pts from the chart price -> no stop/target placed, flattened",
          not r["ok"] and "flattened" in r["error"] and not any("STOPMARKET" in ln for ln in lines)
          and any(ln.startswith("CLOSEPOSITION") for ln in lines) and fake.pos[("Sim101", "MNQ 03-27")][0] == 0
          and not ad.legs, [r, lines])
    # 4. before the roll: orders and chart both on 12-26
    w.now[0] = dt.datetime(2026, 12, 9, 3, 0, 3, tzinfo=ET).timestamp()
    ad2 = w.make("r2.json")
    chart(w, "MNQ 12-26")
    fake.move(25020.0)
    t = int(w.now[0]) - 3
    r = ad2.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    check("4. 2026-12-09: chart and orders on MNQ 12-26 -> entry goes in", r["ok"] and ad2._instruments()["micro"] == "MNQ 12-26", r)
    ad2.send({"side": "exit", "reason": "x", "entry_t": t})
    # 5. default fill-gap limit 0.3%: a 0.5% gap (125 pts at 25020) is caught, a normal 24-pt offset (0.1%) is not
    chart(w, None)
    w.now[0] += 1800
    t = int(w.now[0]) - 3
    fake.move(25020.0 * 1.005)
    k = len(fake.files)
    r = ad2.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    lines = [ln for _, ls in fake.files[k:] for ln in ls]
    check("5. fill 0.5% (125 pts) from the chart price -> no stop/target, flattened",
          not r["ok"] and not any("STOPMARKET" in ln for ln in lines) and fake.pos[("Sim101", "MNQ 12-26")][0] == 0, [r, lines])
    w.now[0] += 1800
    t = int(w.now[0]) - 3
    fake.move(25044.0)
    r = ad2.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    check("5. fill 24 pts (the worst 2026 LIT entry-bar offset, 0.08-0.1%) from the model price -> bracket placed",
          r["ok"] and ad2.legs and ad2.legs[0]["status"] == "protected", r)
    ad2.send({"side": "exit", "reason": "x", "entry_t": t})
    # 6. a fill reported late (entry pending) a roll gap away: tick() flattens instead of protecting it
    w.now[0] += 1800
    t = int(w.now[0]) - 3
    fake.move(25020.0)
    fake.hold_market = True
    r = ad2.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    fake.hold_market = False
    eid = ad2.legs[0]["entry_id"]
    fake.price = 25330.0
    fake._fill(eid, 2, 25330.0)
    k, na = len(fake.files), len(w.alerts)
    ad2.tick()
    lines = [ln for _, ls in fake.files[k:] for ln in ls]
    check("6. late fill 310 pts from the chart price (pending entry, protected in tick) -> no stop/target, flattened, alert",
          r.get("ok") is False and not any("STOPMARKET" in ln for ln in lines) and any(ln.startswith("CLOSEPOSITION") for ln in lines)
          and fake.pos[("Sim101", "MNQ 12-26")][0] == 0 and not ad2.legs and len(w.alerts) > na, [lines, w.alerts[na:]])
    # 7. chart on a continuous contract: the contract check cannot run -> loud warning (alert, once a day), entry allowed
    chart(w, "MNQ ##-##")
    w.now[0] += 1800
    t = int(w.now[0]) - 3
    fake.move(25020.0)
    na = len(w.alerts)
    r = ad2.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    al = w.alerts[na:]
    check("7. chart on MNQ ##-## (continuous) -> alert 'continuous contract ... roll check is OFF', entry still goes in",
          r["ok"] and any("continuous contract" in a and "roll check is OFF" in a for a in al), [r, al])
    ad2.send({"side": "exit", "reason": "x", "entry_t": t})
    w.now[0] += 600
    t = int(w.now[0]) - 3
    na = len(w.alerts)
    ad2.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    check("7. ... warned once per day", not any("continuous" in a for a in w.alerts[na:]), w.alerts[na:])
    ad2.send({"side": "exit", "reason": "x", "entry_t": t})
    n = sum(RES)
    print(f"\nroll guard: {n}/{len(RES)} {'PASS' if n == len(RES) else 'FAIL'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
