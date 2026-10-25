"""Real balance from NinjaTrader (2026-10-25): engine/broker_balance.py reads le_feed/accounts.csv (ninjatrader/LE_BarFeed.cs)
and (a) anchors the eval at each day close from the real balance, (b) sizes from min(ledger room, real room), (c) pushes
"balance differs" once a day, (d) changes NOTHING when the file is missing / stale.

    python -X utf8 -m tests.test_broker_balance

Paper only: temp folders, simulated accounts.csv; nothing is armed or routed.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import broker_balance as BB, eval_life as EL, sizing as sz  # noqa: E402
from engine.ninjatrader import _FakeNT  # noqa: E402
from tests.test_multi_account import Clock, make_bot, ts  # noqa: E402

RESULTS = []
LSZ = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
A = {"as_of": "2026-10-23", "balance": 49710.80, "floor": 48168.20}
NAME, BNAME = "MFFU50K-EVAL-1", "MFFU25K-EVAL-2"
T_MON = ts(2026, 10, 26, 10, 0)
HDR = "name,time,cash,realized,unrealized,netliq\n"


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def near(a, b, tol=0.005):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def write(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(HDR + "".join(",".join("" if v is None else str(v) for v in r) + "\n" for r in rows))


# ------------------------------------------------------------------------------------------------ parse / stale / sanity
def parse_checks(tmp):
    rows = BB.parse(HDR + f"{NAME},100,49800.5,-12.5,30,\n{NAME},90,1,1,1,1\ngarbage\n,5,1\nSim101,100,100000,0,0,100000\n"
                    f"{BNAME},100,24900,0,0,24950.25\n")
    check("parse: newest row per name, empty netliq = None, bad lines skipped",
          rows[NAME]["cash"] == 49800.5 and rows[NAME]["netliq"] is None and rows[NAME]["realized"] == -12.5
          and rows[BNAME]["netliq"] == 24950.25 and len(rows) == 3, rows)
    p = os.path.join(tmp, "accounts.csv")
    r0 = BB.read(path=p, now=T_MON)
    check("read: missing file -> not ok, a reason", not r0["ok"] and "no accounts.csv" in r0["why"], r0)
    write(p, [(NAME, T_MON - 60, 49800, 0, 0, None)])
    r1 = BB.read(path=p, now=T_MON)
    check("read: a 60 s old row is fresh", r1["ok"] and r1["rows"][NAME]["fresh"], r1)
    r2 = BB.read(path=p, now=T_MON + 200)
    check("read: a 260 s old row is stale (> 3 min)", not r2["ok"] and not r2["rows"][NAME]["fresh"] and "stale" in r2["why"], r2)
    ok50 = BB.sane({"cash": 49800.0, "unrealized": -50.0}, BB.R50K)[0]
    bad_sim = BB.sane({"cash": 100000.0}, BB.R50K)
    bad_neg = BB.sane({"cash": -5.0})
    bad_u = BB.sane({"cash": 49000.0, "unrealized": 90000.0})
    ok25 = BB.sane({"cash": 24900.0}, BB.R25K)[0] and not BB.sane({"cash": 49800.0}, BB.R25K)[0]
    check("sanity: a $49,800 50K is fine; $100,000 (Sim101), negative cash, $90,000 unrealized, a 50K row on a 25K refused",
          ok50 and not bad_sim[0] and not bad_neg[0] and not bad_u[0] and ok25, (bad_sim, bad_neg, bad_u))
    b = BB.Broker(p, os.path.join(tmp, "bb.json"), clock=lambda: T_MON)
    write(p, [("Sim101", T_MON - 10, 50000, 0, 0, 50000), (NAME, T_MON - 10, 49800, 0, 0, None)])
    check("row(): a Sim account is never used; the eval account is", b.row("Sim101") is None and b.row(NAME)["cash"] == 49800)


# ------------------------------------------------------------------------------------------------ the anchor math
def anchor_checks(tmp):
    check("next_floor 50K: trails (eod - $2,000), never down, locks at $50,100, never above the balance",
          near(BB.next_floor(48168.20, 49800), 48168.20) and near(BB.next_floor(48168.20, 50500), 48500)
          and near(BB.next_floor(48500, 52600), 50100) and near(BB.next_floor(50100, 51000), 50100)
          and near(BB.next_floor(50100, 54000), 50100) and near(BB.next_floor(48500, 48400), 48400))
    check("next_floor 25K: MLL $1,000, lock $25,100",
          near(BB.next_floor(24000, 24800, BB.R25K), 24000) and near(BB.next_floor(24000, 25500, BB.R25K), 24500)
          and near(BB.next_floor(24500, 26400, BB.R25K), 25100))
    p = os.path.join(tmp, "accounts.csv")
    clock = Clock(ts(2026, 10, 26, 10, 0))
    b = BB.Broker(p, os.path.join(tmp, "bb_anchor.json"), clock=clock)
    days = [(ts(2026, 10, 26, 16, 30), 49800.0), (ts(2026, 10, 27, 16, 30), 50500.0), (ts(2026, 10, 28, 16, 30), 52600.0),
            (ts(2026, 10, 29, 16, 30), 51000.0)]
    made = []
    for t, cash in days:
        clock.t = t
        write(p, [(NAME, t - 20, cash, 0, 0, None)])
        made.append(b.observe(NAME, "2026-10-19", None, book_floor=lambda: 99999.0, now=t))   # not used: nothing to close yet
        clock.t = t + 3 * 3600                   # 19:30 ET: the next trading day
        made.append(b.observe(NAME, "2026-10-19", None, book_floor=lambda: 48168.20, now=clock.t))   # first close only
    an = [m for m in made if m]
    check("auto-anchor: one anchor per day close, as_of = that day, balance = the real cash",
          [a["as_of"] for a in an] == ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29"]
          and [a["balance"] for a in an] == [49800.0, 50500.0, 52600.0, 51000.0], an)
    check("auto-anchor floor: first from the book ($48,168.20), then trails $48,500, locks $50,100, stays locked",
          [a["floor"] for a in an] == [48168.20, 48500.0, 50100.0, 50100.0], [a["floor"] for a in an])
    check("auto-anchor persisted (gitignored data/broker_balance.json next to the state file); a new Broker reads it",
          BB.Broker(p, os.path.join(tmp, "bb_anchor.json")).anchor(NAME, "2026-10-19")["as_of"] == "2026-10-29")
    check("auto-anchor of an older eval is ignored after a new eval_start", b.anchor(NAME, "2026-11-02") is None)
    # the last fresh value of the day wins (a late manual trade at 16:50 ET)
    b2 = BB.Broker(p, os.path.join(tmp, "bb_late.json"), clock=clock)
    for t, cash in ((ts(2026, 10, 26, 15, 0), 49800.0), (ts(2026, 10, 26, 16, 50), 49650.0)):
        write(p, [(NAME, t - 5, cash, 0, 0, None)])
        b2.observe(NAME, "2026-10-19", None, book_floor=lambda: 48168.20, now=t)
    a2 = b2.observe(NAME, "2026-10-19", None, now=ts(2026, 10, 26, 18, 5))
    check("the last fresh value before 18:00 ET is the day's balance ($49,650 after a manual trade)", a2 and a2["balance"] == 49650.0, a2)
    a3 = b2.observe(NAME, "2026-10-19", None, now=ts(2026, 10, 26, 18, 10))
    check("each day is anchored once", a3 is None)


# ------------------------------------------------------------------------------------------------ min room + drift
def room_checks(tmp):
    p = os.path.join(tmp, "accounts.csv")
    b = BB.Broker(p, os.path.join(tmp, "bb_room.json"), clock=lambda: T_MON)
    st = {"profit": -289.20, "cum": 0.0, "room": 1542.60, "session": 6}
    write(p, [(NAME, T_MON - 10, 49710.80, 0, -300.0, None)])
    c = b.cap_state(st, NAME, now=T_MON)
    check("min room: real equity = cash + unrealized -$300 -> room $1,242.60 (ledger $1,542.60)",
          near(c["room"], 1242.60) and near(c["broker"]["ledger_room"], 1542.60) and near(c["broker"]["floor"], 48168.20), c)
    write(p, [(NAME, T_MON - 10, 49900.0, 0, 0, 50100.0)])
    c2 = b.cap_state(st, NAME, now=T_MON)
    check("min room: a higher real balance never raises the room above the ledger's", near(c2["room"], 1542.60), c2)
    write(p, [(NAME, T_MON - 10, 49710.80, 0, 0, 49600.0)])
    c3 = b.cap_state(st, NAME, now=T_MON)
    check("min room: NetLiquidation is used when NinjaTrader gives it ($49,600 -> room $1,431.80)", near(c3["room"], 1431.80), c3)
    check("cap_state input untouched (a copy)", st["room"] == 1542.60 and "broker" not in st)
    write(p, [(NAME, T_MON - 900, 40000.0, 0, 0, None)])
    check("min room: a stale row -> the same state object back (nothing changes)", b.cap_state(st, NAME, now=T_MON) is st)
    q_led = sz.two_week_qty({"risk_pts": 30.0, "tgt_pts": 200.0}, {**st, "room": 1542.60}, LSZ.get("two_week"))
    q_real = sz.two_week_qty({"risk_pts": 30.0, "tgt_pts": 200.0}, c, LSZ.get("two_week"))
    check("sizing from the capped room is never more micros than from the ledger room", q_real <= q_led, (q_real, q_led))
    # drift
    d = BB.Broker(p, os.path.join(tmp, "bb_drift.json"), clock=lambda: T_MON)
    write(p, [(NAME, T_MON - 10, 49630.0, 0, 0, None)])
    r1 = d.drift(NAME, 49710.80, now=T_MON)
    write(p, [(NAME, T_MON + 290, 49630.0, 0, 0, None)])
    r2 = d.drift(NAME, 49710.80, now=T_MON + 310)
    write(p, [(NAME, T_MON + 600, 49630.0, 0, 0, None)])
    r3 = d.drift(NAME, 49710.80, now=T_MON + 620)
    check("drift: $80.80 apart -> nothing at first, one alert after 5 min with both numbers, then quiet that day",
          r1 is None and r2 and near(r2["real"], 49630.0) and near(r2["ledger"], 49710.80) and near(r2["diff"], -80.80) and r3 is None,
          (r1, r2, r3))
    d2 = BB.Broker(p, os.path.join(tmp, "bb_drift2.json"), clock=lambda: T_MON)
    write(p, [(NAME, T_MON - 10, 49680.0, 0, 0, None)])
    q1, q2 = d2.drift(NAME, 49710.80, now=T_MON), d2.drift(NAME, 49710.80, now=T_MON + 400)
    check("drift: $30.80 apart (commission noise) -> no alert", q1 is None and q2 is None)
    pl = BB.drift_payload("Sim101", NAME, r2, T_MON)
    check("drift push: 'balance differs' with both numbers, keyed once a day", "balance differs" in pl["title"]
          and "49,630.00" in pl["body"] and "49,710.80" in pl["body"] and pl["key"] == f"baldiff:{NAME}:2026-10-26", pl)


# ------------------------------------------------------------------------------------------------ the PC bot
def bot_checks(tmp):
    fake = _FakeNT(os.path.join(tmp, "NinjaTrader 8"))
    clock = Clock(T_MON + 290)
    csv = os.path.join(tmp, "nt_accounts.csv")
    prev = {"2026-10-19": -250.0, "2026-10-22": 61.0}

    def bot(name, extra=None):
        b = make_bot(os.path.join(tmp, name), fake, clock, None, extra_cfg={"eval_start": "2026-10-19", **(extra or {})})
        b._lit_sizing = copy.deepcopy(LSZ)
        b._eval_prev = dict(prev)
        b.state = {"model": "lit"}
        EL.save_anchor(A, path=EL.anchor_path(b.state_path))
        return b
    on = {"broker_balance": True, "broker_balance_file": csv, "nt_account": NAME}
    b0 = bot("plain")
    b1 = bot("absent", on)
    check("switch unset on a test bot (own state file): off", BB.for_bot(b0) is None and BB.enabled(b0) is False)
    s0, s1 = b0.eval_state(), b1.eval_state()
    check("file ABSENT: eval_state / eval_room / eval_anchor identical to the bot without the switch",
          s0 == s1 and b0.eval_room() == b1.eval_room() and b0.eval_anchor() == b1.eval_anchor(), (s0, s1))
    b1._broker_tick()
    check("file absent: the poll tick writes no anchor", b1._broker_anchor() is None)
    trade = {"risk_pts": 30.0, "tgt_pts": 200.0, "size_mult": 1.0}
    q0 = sz.lit_qty(20, trade, LSZ, room=b0.eval_room(), state=b0.eval_state())["qty"]
    q1 = sz.lit_qty(20, trade, LSZ, room=b1.eval_room(), state=b1.eval_state())["qty"]
    check("file absent: identical sizing", q0 == q1, (q0, q1))
    write(csv, [(NAME, T_MON - 3600, 40000.0, 0, 0, None)])
    check("file STALE: identical eval_state / eval_room", b1.eval_state() == s0 and b1.eval_room() == b0.eval_room())
    write(csv, [("Sim101", T_MON + 280, 100000.0, 0, 0, 100000.0)])
    check("only a Sim101 row: identical", b1.eval_state() == s0)
    # fresh: real balance $49,650 (a $60.80 commission / manual drift), open trade -$200
    write(csv, [(NAME, T_MON + 280, 49650.0, 0, -200.0, None), (BNAME, T_MON + 280, 24900.0, 0, 0, None)])
    s2 = b1.eval_state()
    check("file FRESH: room = min(ledger $1,542.60, real $49,450 - $48,168.20 = $1,281.80); 'broker' block",
          near(s2["room"], 1281.80) and s2["broker"]["name"] == NAME and near(s2["broker"]["ledger_room"], 1542.60), s2)
    check("file fresh: eval_room capped the same way", near(b1.eval_room(), 1281.80), b1.eval_room())
    q2 = sz.lit_qty(20, trade, LSZ, room=b1.eval_room(), state=s2)["qty"]
    check("file fresh: never more micros than the ledger sizing", q2 <= q0, (q2, q0))
    from engine import brain
    out = brain._sizing({"risk": 30.0, "tgt": 200.0, "what": "test"}, {"lit_sizing": LSZ, "eval_state": s2}, None, {}, None)
    st_ = {x["label"]: x for x in out["steps"]}
    check("Bot Brain sizing line: 'balance from NinjaTrader $X, floor $Y, room $Z'",
          "Real balance" in st_ and out.get("broker_line", "").startswith("balance from NinjaTrader $49,450.00, floor $48,168.20, room $1,281.80"),
          out.get("broker_line"))
    # the day close -> the next session anchors from the real balance
    clock.t = ts(2026, 10, 26, 16, 40)
    write(csv, [(NAME, clock.t - 5, 49650.0, 0, 0, None)])
    b1._broker_tick()
    clock.t = ts(2026, 10, 26, 18, 30)
    b1._broker_tick()
    a = b1.eval_anchor()
    check("day close: the bot's eval anchor = real $49,650 as of 2026-10-26, floor $48,168.20",
          a and a["as_of"] == "2026-10-26" and near(a["balance"], 49650.0) and near(a["floor"], 48168.20), a)
    clock.t = ts(2026, 10, 27, 10, 0)
    write(csv, [(NAME, clock.t - 5, 49650.0, 0, 0, None)])
    s3 = b1.eval_state()
    check("next session: profit = real balance - $50,000, room $1,481.80 (the drift is absorbed)",
          near(s3["profit"], -350.0) and near(s3["room"], 1481.80), s3)
    # launch checklist
    from engine import launch_check as LC
    f = LC.broker_fact(b1, NAME, clock.t, path=csv)
    items = {i["key"]: i for i in LC.checklist({"broker": f}, {}, True, clock.t)["items"]}
    check("launch checklist: 'Real balance from NinjaTrader' green when fresh, with floor / room",
          items["broker"]["state"] == "good" and "49,650.00" in items["broker"]["detail"] and "room" in items["broker"]["detail"],
          items["broker"])
    f2 = LC.broker_fact(b1, NAME, clock.t + 3600, path=csv)
    i2 = {i["key"]: i for i in LC.checklist({"broker": f2}, {}, True, clock.t)["items"]}["broker"]
    f3 = LC.broker_fact(b1, NAME, clock.t, path=os.path.join(tmp, "none.csv"))
    i3 = {i["key"]: i for i in LC.checklist({"broker": f3}, {}, True, clock.t)["items"]}["broker"]
    check("launch checklist: stale / missing -> display only (info), never blocks the launch",
          i2["state"] == "info" and i3["state"] == "info" and "ledger" in i3["detail"], (i2, i3))
    return csv


def account_b_checks(tmp, csv):
    from engine import account_b as AB
    from engine import live
    sp = AB.normalize({"account": BNAME, "plan": "builder25k", "eval_start": "2026-10-19"}, scfg={"strategies": {}})
    clock = Clock(T_MON + 290)
    bot = SimpleNamespace(cfg={"adapter": "ninjatrader", "broker_balance": True, "broker_balance_file": csv},
                          state_path=os.path.join(tmp, "bbot", "live_state.json"), clock=clock, _log=lambda *a: None,
                          _note_error=lambda *a: None, _push_send=lambda p: None)
    os.makedirs(os.path.dirname(bot.state_path), exist_ok=True)
    B = AB.AccountB(bot, sp, state_path=os.path.join(tmp, "bbot", "b.json"))
    B.adapter = live.PaperAdapter({})
    write(csv, [(NAME, clock.t - 10, 49650.0, 0, 0, None), (BNAME, clock.t - 10, 24900.0, 0, -150.0, None)])
    st = B.eval_state(clock.t)
    check("account B reads ITS OWN row (25K: $24,900 - $150), never the 50K's",
          st and st["broker"]["name"] == BNAME and near(st["broker"]["equity"], 24750.0) and near(st["room"], 750.0), st)
    clock.t = ts(2026, 10, 26, 18, 30)
    write(csv, [(BNAME, ts(2026, 10, 26, 16, 50), 24900.0, 0, 0, None)])
    B.broker_tick(ts(2026, 10, 26, 16, 51))
    B.broker_tick(clock.t)
    a = B.anchor()
    check("account B day close: its own anchor ($24,900, 25K floor $24,000)", a and a["as_of"] == "2026-10-26"
          and near(a["balance"], 24900.0) and near(a["floor"], 24000.0), a)
    check("account B's anchor does not leak into the 50K", BB.for_bot(bot).anchor(NAME, "2026-10-19") is None)


def main():
    tmp = tempfile.mkdtemp(prefix="bb_test_")
    os.environ.setdefault("LE_LIT_LEARNING", os.path.join(tmp, "no_learning.json"))
    try:
        parse_checks(tmp)
        anchor_checks(tmp)
        room_checks(tmp)
        csv = bot_checks(tmp)
        account_b_checks(tmp, csv)
        check("selftest", BB.selftest())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(RESULTS)
    print(f"\n{sum(RESULTS)}/{n} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
