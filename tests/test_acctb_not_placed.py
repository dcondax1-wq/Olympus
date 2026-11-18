"""Account B entry the broker never took (engine/account_b.py never_placed / _drop_unplaced / reconcile_unplaced, owner
2026-10-27): the 03:30 MACD LONG 3 on the 25K was refused, yet B kept it "open" to its exit (B's other entries blocked all
day, its paper P&L booked on B's eval, the phone showed a trade that never existed).

    python -X utf8 -m tests.test_acctb_not_placed          # ~1 min, temp folders only

  1. refused entry (stub adapter): B is flat at once, the entry does not count toward the 2 a day, one "order NOT placed"
     push with the reason (paths removed), no entry push, the heartbeat row carries ok False + the reason.
  2. NinjaTrader did not pick the file up (the real adapter on the offline fake NinjaTrader, withdrawn): flat, pushed.
  3. a leg still working ("fill not reported yet"): B KEEPS the position (it may exist), one "NOT confirmed" push; once the
     adapter retires that leg unfilled, the next poll drops it; a leg that filled is never dropped.
  4. NinjaTrader shows a position on B's contract: never dropped.
  5. a state saved by the old version (the phantom kept open, or already closed with its paper P&L booked): the first poll
     drops it, the booked close is voided (B's eval back to its real balance), one push; a placed trade's close is kept.
  6. LIT entering the other way while B holds a never-placed entry: nothing is closed at market, LIT is not held back.
  7. LIT on the 50K (engine/live.py, the LiveBot replay of tests.test_lit_live on 2026-10-13, a +$3,169 TARGET day): the
     broker refuses the entry -> one "order NOT placed" push with the reason, no entry push, its exit books $0 (was the
     backtest's +$3,169 on the eval), no outcome push; control: the same day with the entry taken books the trade.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import ninjatrader as N  # noqa: E402
from engine import second  # noqa: E402

RES = []
TB = 1793086200                    # Tue 2026-10-27 03:30 ET (the real refused entry)
KEY = "macd_sweep"
SIG = {"entry_t": TB, "exit_kind": "OPEN", "dir": 1, "entry": 29323.25, "stop": 29288.5, "target": 29601.25, "qty": 3}
REFUSED = "REFUSED: NinjaTrader reports every connection DISCONNECTED (C:\\Users\\someone\\Documents\\NinjaTrader 8\\x.txt)"


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


class FakeBot:
    def __init__(self, now):
        self._now = now
        self.state = {"price": 29323.25}
        self.ledger = []
        self._open_routed = None
        self.accts = None
        self.cfg = {"adapter": "paper", "sym": "NQ"}
        self.health = {}
        self.kill = False
        self.state_path = None
        self.logs = []
        self.pushed = []

    def clock(self):
        return self._now

    def _log(self, kind, text, **kw):
        self.logs.append((kind, text))

    def _note_error(self, text):
        self.logs.append(("error", text))

    def _push_send(self, p):
        self.pushed.append(p)


class StubAdapter:
    """send() answers what the test sets; legs / history / position as the NinjaTrader adapter keeps them."""
    name = "stub"

    def __init__(self, answer, legs=None, pos="FLAT"):
        self.answer, self.legs, self.history, self.pos, self.sent = answer, list(legs or []), [], pos, []

    def send(self, action):
        self.sent.append(dict(action))
        return dict(self.answer) if action.get("side") in ("buy", "sell") else {"ok": True}

    def _instruments(self):
        return {"mini": "NQ 12-26", "micro": "MNQ 12-26"}

    def position_for(self, inst):
        if inst == "MNQ 12-26" and self.pos != "FLAT":
            return {"side": self.pos, "qty": 3}
        return {"side": "FLAT", "qty": 0}


def spec():
    blk = {"account": "Sim102", "plan": "builder25k", "eval_start": "2026-10-26", "strategies": ["ema_lon_vix", KEY, "sr_nyreclaim"],
           "sizing": "need"}
    return AB.normalize(blk, second.load_cfg())


def frames():
    t5 = [TB - 300 * i for i in range(60, 0, -1)]
    t1 = [TB - 60 * i for i in range(120, 0, -1)]
    row = lambda t: {"time": t, "open": 29320.0, "high": 29325.0, "low": 29315.0, "close": 29322.0, "volume": 100.0}
    return pd.DataFrame([row(t) for t in t5]), pd.DataFrame([row(t) for t in t1])


def make(tmp, adapter, now=TB + 12):
    bot = FakeBot(now)
    B = AB.AccountB(bot, spec(), state_path=os.path.join(tmp, f"b_{len(os.listdir(tmp))}.json"))
    B.adapter = adapter
    return bot, B


def enter(B, trade=SIG):
    """B.entry on the 03:30 open with the MACD signal (second.run stubbed to it)."""
    real = second.run
    second.run = lambda *a, **k: {"strategies": {KEY: {"short": "MACD", "trades": [dict(trade)]}}}
    try:
        df5, df1 = frames()
        sub = {"strategies": {KEY: {"short": "MACD", "route": True}}}
        B.entry(df5, df1, sub, [KEY], "NQ", B.clock())
    finally:
        second.run = real


def texts(bot):
    return [f"{p.get('title', '')} | {p.get('body', '')}" for p in bot.pushed]


def part1(tmp):
    bot, B = make(tmp, StubAdapter({"ok": False, "error": REFUSED}))
    enter(B)
    sent = [a for a in B.adapter.sent if a.get("side") == "buy"]
    check("1. the refused entry was sent once (BUY at the 03:30 open)", len(sent) == 1 and sent[0]["entry_t"] == TB, B.adapter.sent)
    check("1. ... B is flat at once (no phantom position)", B.open_t is None and B.position() is None, B.open_t)
    check("1. ... the entry does not count toward the 2 a day", B.entries_today("2026-10-27") == 0)
    pv = B.prov.get(TB) or {}
    check("1. ... marked not placed + final (never managed to an exit)", pv.get("final") and (pv.get("not_placed") or {}).get("error"), pv)
    tx = texts(bot)
    np_ = [t for t in tx if "NOT placed" in t]
    check("1. ... one 'order NOT placed' push with the reason, no entry push", len(np_) == 1 and "DISCONNECTED" in np_[0]
          and len(tx) == 1, tx)
    check("1. ... the push carries no file path", all("Users" not in t for t in tx), tx)
    row = (B.info(TB + 60).get("routed") or [{}])[-1]
    check("1. heartbeat row: ok False + NinjaTrader's reason (path removed)", row.get("ok") is False and "DISCONNECTED" in
          (row.get("error") or "") and "Users" not in row.get("error", ""), row)
    B.tick(*frames(), "NQ", TB + 60)
    check("1. the next poll: nothing re-sent, no second push", len([a for a in B.adapter.sent if a.get("side") == "buy"]) == 1
          and len(texts(bot)) == 1, (B.adapter.sent, texts(bot)))
    # a placed entry is untouched
    bot2, B2 = make(tmp, StubAdapter({"ok": True, "legs": [{"instrument": "MNQ 12-26", "qty": 3, "filled": 3, "ok": True}]}))
    enter(B2)
    check("1. control: an entry NinjaTrader took stays open (B holds it, counts 1 today)", B2.open_t == TB
          and B2.entries_today("2026-10-27") == 1 and not B2.never_placed(TB), B2.open_t)


def part2(tmp):
    fold = os.path.join(tmp, "nt", "NinjaTrader 8")
    fake = N._FakeNT(fold)
    fake.move(29323.0)
    now = [float(TB + 5)]
    cfg = {"adapter": "ninjatrader", "sym": "NQ", "nt_account": "Sim102", "nt_folder": fold,
           "params": {"max_micros": 20, "flat_mod": 955}, "nt_state_path": os.path.join(tmp, "nt_st.json"),
           "nt_audit_log": os.path.join(tmp, "oif.log"), "nt_session_from": 120}
    ad = N.NinjaTraderAdapter(cfg, clock=lambda: now[0])
    ad._sleep = lambda s: now.__setitem__(0, now[0] + s)      # NinjaTrader never picks the file up
    ad._gate = lambda kind: None
    bot, B = make(tmp, ad, now=TB + 12)
    bot.clock = lambda: now[0]
    enter(B)
    r = B.entry_result(TB) or {}
    check("2. NinjaTrader did not pick the order up: withdrawn, NOT OK", r.get("ok") is False
          and "withdrawn and NOT executed" in str(r.get("error")), r)
    check("2. ... B flat, one 'order NOT placed' push", B.open_t is None and len([t for t in texts(bot) if "NOT placed" in t]) == 1,
          (B.open_t, texts(bot)))


def part3(tmp):
    leg = {"instrument": "MNQ 12-26", "qty": 3, "entry_t": TB, "status": "pending", "filled": 0}
    ans = {"ok": False, "error": "MNQ 12-26: fill not reported yet: the stop and target go in the moment NinjaTrader reports it",
           "legs": [{"instrument": "MNQ 12-26", "qty": 3, "ok": False, "state": "ACCEPTED", "note": "fill not reported yet"}]}
    bot, B = make(tmp, StubAdapter(ans, legs=[leg]))
    enter(B)
    tx = texts(bot)
    check("3. a leg still working: B KEEPS the position (it may exist)", B.open_t == TB and not B.never_placed(TB), B.open_t)
    check("3. ... one 'NOT confirmed' push, no 'NOT placed'", len([t for t in tx if "NOT confirmed" in t]) == 1
          and not [t for t in tx if "NOT placed" in t], tx)
    B.tick(*frames(), "NQ", TB + 60)
    check("3. ... still kept on the next poll while the leg works", B.open_t == TB)
    B.adapter.legs.remove(leg)
    B.adapter.history.append({**leg, "status": "rejected", "closed": "entry rejected"})
    B.reconcile_unplaced(TB + 120)
    check("3. the adapter retired the leg unfilled: the next poll drops it, one 'NOT placed' push", B.open_t is None
          and len([t for t in texts(bot) if "NOT placed" in t]) == 1, (B.open_t, texts(bot)))
    bot2, B2 = make(tmp, StubAdapter(ans, legs=[dict(leg)]))
    enter(B2)
    B2.adapter.legs[0].update(status="protected", filled=3)
    B2.reconcile_unplaced(TB + 60)
    B2.adapter.history.append({**B2.adapter.legs.pop(0), "status": "closed", "closed": "target"})
    B2.reconcile_unplaced(TB + 120)
    check("3. a late fill (then closed at the broker): never dropped", B2.open_t == TB and not (B2.prov[TB].get("not_placed")),
          B2.prov.get(TB))
    bot3, B3 = make(tmp, StubAdapter(ans, legs=[]))
    enter(B3)
    check("3. a working leg the adapter no longer knows (restart): kept (unknown is never 'not placed')", B3.open_t == TB)


def part4(tmp):
    bot, B = make(tmp, StubAdapter({"ok": False, "error": REFUSED}, pos="LONG"))
    enter(B)
    check("4. NinjaTrader shows a position on B's contract: kept, never dropped", B.open_t == TB and not B.never_placed(TB), B.open_t)


def part5(tmp):
    # the old version: the refused entry kept open (the PC's state at 05:24 ET on 2026-10-27)
    bot, B = make(tmp, StubAdapter({"ok": False, "error": REFUSED}), now=TB + 2 * 3600)
    B.ledger = [{"t": TB + 12, "sym": "NQ", "side": "buy", "qty": 3, "stop": 29288.5, "target": 29601.25, "entry": 29323.25,
                 "entry_t": TB, "src": KEY, "strategy": "MACD", "result": {"ok": False, "error": REFUSED}}]
    B.prov = {TB: {"key": KEY, "short": "MACD", "qty": 3, "dir": 1, "entry": 29323.25, "stop": 29288.5, "target": 29601.25,
                   "day": "2026-10-27", "fill": 29323.25, "checked": True}}
    B.open_t = TB
    B.save()
    bot1, B1 = make(tmp, StubAdapter({"ok": False, "error": REFUSED}), now=TB + 2 * 3600)
    B1.state_path = B.state_path
    B1._load()
    check("5. the old state restores the phantom (as on the PC)", B1.open_t == TB)
    B1.tick(*frames(), "NQ", TB + 2 * 3600)
    check("5. ... the first poll drops it: flat, one 'NOT placed' push", B1.open_t is None
          and len([t for t in texts(bot1) if "NOT placed" in t]) == 1, (B1.open_t, texts(bot1)))
    # the old version already closed it at its target and booked the paper win on B's eval
    bot2, B2 = make(tmp, StubAdapter({"ok": False, "error": REFUSED}), now=TB + 9 * 3600)
    B2.ledger = list(B.ledger) + [{"t": TB + 6 * 3600, "sym": "NQ", "side": "exit", "qty": 3, "reason": "TARGET", "pnl": 1668.0,
                                   "entry_t": TB, "src": KEY}]
    B2.prov = {TB: {**B.prov[TB], "final": True}}
    B2.closes = [["2026-10-27", TB + 6 * 3600, 1668.0, TB]]
    before = B2.eval_view(TB + 9 * 3600)
    B2.tick(*frames(), "NQ", TB + 9 * 3600)
    after = B2.eval_view(TB + 9 * 3600)
    check(f"5. a booked paper close of a never-placed entry is voided: eval {before.get('status')} ${before.get('balance'):,.0f} "
          f"-> {after.get('status')} ${after.get('balance'):,.0f}", before.get("status") == "passed" and after.get("status") == "open"
          and abs(float(after.get("balance")) - 25000.0) < 0.01 and not B2.closes, (before, after))
    row = [r for r in B2.info(TB + 9 * 3600)["routed"] if r.get("side") == "exit"]
    check("5. ... its exit row is marked void on the heartbeat", row and row[-1].get("void") == "not placed", row)
    # a placed trade's booked close is kept
    bot3, B3 = make(tmp, StubAdapter({"ok": True}), now=TB + 9 * 3600)
    B3.ledger = [{**B.ledger[0], "result": {"ok": True, "legs": [{"filled": 3, "ok": True}]}}]
    B3.prov = {TB: {**B.prov[TB], "final": True}}
    B3.closes = [["2026-10-27", TB + 6 * 3600, 1668.0, TB]]
    B3.tick(*frames(), "NQ", TB + 9 * 3600)
    check("5. control: a placed trade's booked close is kept", len(B3.closes) == 1)


def part6(tmp):
    bot, B = make(tmp, StubAdapter({"ok": False, "error": REFUSED}), now=TB + 3600)
    B.ledger = [{"t": TB + 12, "sym": "NQ", "side": "buy", "qty": 3, "entry_t": TB, "src": KEY, "result": {"ok": False, "error": REFUSED}}]
    B.prov = {TB: {"key": KEY, "short": "MACD", "qty": 3, "dir": 1, "entry": 29323.25, "day": "2026-10-27"}}
    B.open_t = TB
    ok = B.lit_entering({"dir": -1, "entry_t": TB + 3600, "entry": 29400.0}, "NQ", TB + 3600)
    exits = [a for a in B.adapter.sent if a.get("side") == "exit"]
    check("6. LIT SHORT while B holds a never-placed LONG: LIT routes, nothing closed at market, nothing booked",
          ok is True and not exits and not B.closes and B.open_t is None, (ok, exits, B.closes))


class LitBroker:
    """A NinjaTrader-like broker for the LiveBot replay: refuses (or takes) every entry, takes every exit / stop move."""
    name = "ninjatrader"
    route_all_exits = True
    route_stop_moves = True
    reports_fills = True

    def __init__(self, take):
        self.take, self.sent, self.legs, self.history = take, [], [], []

    def send(self, a):
        self.sent.append(dict(a))
        if a.get("side") in ("buy", "sell") and not self.take:
            return {"ok": False, "error": REFUSED}
        if a.get("side") in ("buy", "sell"):
            return {"ok": True, "legs": [{"instrument": "MNQ 12-26", "qty": a.get("qty"), "filled": a.get("qty"), "ok": True}]}
        return {"ok": True}

    def has_open_bracket(self, entry_t=None):
        return self.take

    def _instruments(self):
        return {"mini": "NQ 12-26", "micro": "MNQ 12-26"}

    def position_for(self, inst):
        return {"side": "FLAT", "qty": 0}


def part7(tmp):
    import collections
    import json
    from tests import test_lit_live as TL
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    day = "2026-10-13"
    by_day = collections.defaultdict(list)
    for t in F.run(P):
        if t["day"] == day:
            by_day[day].append(t)
    want = by_day[day]
    if len(want) != 1:
        check(f"7. {day} has one LIT trade in the backtest", False, want)
        return
    t0 = want[0]
    out = {}
    for take in (False, True):
        held = {}

        def hook(bot, take=take, held=held):
            bot.cfg["adapter"] = "ninjatrader"
            bot.adapter = LitBroker(take)
            held["bot"], held["pushed"] = bot, []
            bot._push_send = lambda p: held["pushed"].append(p)
        TL.bot_replay(P, by_day, sessions=(day,), on_bot=hook)
        b = held["bot"]
        ent = [r for r in b.ledger if r.get("side") in ("buy", "sell") and int(r.get("entry_t") or 0) == int(t0["entry_t"])]
        exi = [r for r in b.ledger if r.get("side") == "exit" and int(r.get("entry_t") or 0) == int(t0["entry_t"])]
        out[take] = {"ent": ent, "exi": exi, "days": b.eval_days(), "pushed": [f"{p.get('title')} | {p.get('body')}" for p in held["pushed"]]}
    r, c = out[False], out[True]
    check(f"7. LIT {day}: the refused entry was sent once, NOT OK", len(r["ent"]) == 1 and (r["ent"][0].get("result") or {}).get("ok") is False,
          r["ent"])
    np_ = [x for x in r["pushed"] if "NOT placed" in x]
    check("7. ... one 'order NOT placed' push with the reason (no path), no entry / outcome push", len(np_) == 1 and "DISCONNECTED" in np_[0]
          and "Users" not in np_[0] and len(r["pushed"]) == 1, r["pushed"])
    pn = [float(x.get("pnl") or 0) for x in r["exi"]]
    check(f"7. ... its exit books $0 (the backtest's {t0['exit']} ${t0['pnl']:,.0f} is not on the eval): {pn}, eval day "
          f"${sum(v for k, v in r['days'].items() if k != '0000-00-00'):,.2f}", r["exi"] and all(abs(v) < 1e-9 for v in pn)
          and abs(sum(v for k, v in r["days"].items() if k != "0000-00-00")) < 1e-9, (r["exi"], r["days"]))
    cp = [float(x.get("pnl") or 0) for x in c["exi"]]
    check(f"7. control: the entry taken -> the trade is booked (${sum(cp):,.2f}, backtest at $1.90 ${TL.booked(t0):,.2f})",
          len(c["ent"]) == 1 and c["exi"] and abs(sum(cp) - TL.booked(t0)) < 0.01, (c["ent"], c["exi"]))


class TraceAdapter(StubAdapter):
    """A restarted adapter: no legs, NinjaTrader's outgoing\\ listing and position files as given."""

    def __init__(self, names=(), pos="FLAT"):
        super().__init__({"ok": True})
        self.names, self.pos_side = list(names), pos

    def _listing(self):
        return list(self.names)

    def position_for(self, inst):
        return None if self.pos_side is None else {"side": self.pos_side, "qty": 0 if self.pos_side == "FLAT" else 7}


PENDING = {"ok": False, "error": "MNQ 12-26: fill not reported yet: the stop and target go in the moment NinjaTrader reports it",
           "legs": [{"instrument": "MNQ 12-26", "qty": 7, "ok": False, "state": None, "note": "fill not reported yet"}]}


def part8(tmp):
    t = 1793095920                       # Zlarior's 06:12 SELL 7 on 2026-10-27
    f = lambda ad, now: N.entry_never_placed(ad, t, PENDING, now=now)
    check("8. 'fill not reported yet', adapter restarted, no order file, position FLAT, 10+ min later -> never placed",
          f(TraceAdapter(), t + 700))
    check("8. ... within 10 min -> unknown (kept)", not f(TraceAdapter(), t + 300))
    check("8. ... NinjaTrader wrote an order file of it -> kept", not f(TraceAdapter([f"LE{t}W924ME.txt"]), t + 700))
    check("8. ... no position file (NinjaTrader restarted) -> kept", not f(TraceAdapter(pos=None), t + 700))
    check("8. ... a position shown -> kept", not f(TraceAdapter(pos="SHORT"), t + 700))
    lf = os.path.join(tmp, "NT8", "log")
    os.makedirs(lf)
    with open(os.path.join(lf, "log.20261027.00000.txt"), "w") as fh:
        fh.write(f"10/27/2026 6:12:04 AM|ATI|OIF, 'PLACE;MFFUEVBLD000006016;MNQ 12-26;SELL;7;MARKET;0;0;DAY;;LE{t}W924ME;;' "
                 "account does not exist 'MFFUEVBLD000006016'\n")
    ad = TraceAdapter(pos=None)
    ad.folder = os.path.join(tmp, "NT8")
    check("8. NinjaTrader's Log: 'account does not exist' for this PLACE -> never placed at once (no position file needed)",
          N.entry_never_placed(ad, t, PENDING, now=t + 60))
    ad2 = TraceAdapter(pos=None)
    ad2.folder = os.path.join(tmp, "NT8")
    check("8. ... another entry's id -> not proof", not N.entry_never_placed(ad2, t + 300, PENDING, now=t + 400))
    # B's 03:30 BUY 3 the same way: its restored phantom is dropped, the booked HEDGE +$525.30 voided
    bot, B = make(tmp, TraceAdapter(), now=TB + 3 * 3600)
    B.ledger = [{"t": TB + 12, "sym": "NQ", "side": "buy", "qty": 3, "entry_t": TB, "src": KEY, "result": dict(PENDING)},
                {"t": TB + 9724, "sym": "NQ", "side": "exit", "qty": 3, "reason": "HEDGE", "pnl": 525.3, "entry_t": TB, "src": KEY}]
    B.prov = {TB: {"key": KEY, "short": "MACD", "qty": 3, "dir": 1, "entry": 29323.25, "day": "2026-10-27", "final": True}}
    B.closes = [["2026-10-27", TB + 9724, 525.3, TB]]
    B.tick(*frames(), "NQ", TB + 3 * 3600)
    ev = B.eval_view(TB + 3 * 3600)
    check(f"8. ATLAS: the HEDGE +$525.30 of the never-filled 03:30 entry voided -> balance ${ev['balance']:,.2f}",
          not B.closes and abs(ev["balance"] - 25000.0) < 0.01, (B.closes, ev))


def part9(tmp):
    from engine import live
    t = 1793095920
    b = live.LiveBot()
    now = [t + 3 * 3600]
    b.clock = lambda: now[0]
    b.state_path = os.path.join(tmp, "ls.json")
    b.cfg = {"adapter": "ninjatrader", "sym": "NQ", "tf": "5m"}
    b.adapter = TraceAdapter()
    b.ledger = [{"t": t + 10, "sym": "NQ", "side": "sell", "qty": 7, "entry_t": t, "result": dict(PENDING)},
                {"t": t + 1686, "sym": "NQ", "side": "exit", "qty": 7, "reason": "STOP", "pnl": -965.3, "entry_t": t},
                {"t": t - 9000, "sym": "NQ", "side": "buy", "qty": 2, "entry_t": t - 9100, "result": {"ok": True}},
                {"t": t - 8000, "sym": "NQ", "side": "exit", "qty": 2, "reason": "TARGET", "pnl": 400.0, "entry_t": t - 9100}]
    b._void_unplaced_exits()
    ex = [r for r in b.ledger if r["side"] == "exit"]
    check("9. Zlarior: the booked -$965.30 STOP of the never-filled 06:12 SELL 7 -> $0 (kept as pnl_void)",
          ex[0]["pnl"] == 0.0 and ex[0].get("pnl_void") == -965.3 and ex[0].get("void") == "not placed", ex[0])
    check("9. ... a real trade's +$400 is untouched", ex[1]["pnl"] == 400.0 and not ex[1].get("void"), ex[1])
    days = b.eval_days()
    check(f"9. ... the eval day books only the real trade: {days}", abs(sum(v for k, v in days.items() if k != '0000-00-00') - 400.0) < 0.01, days)
    b._void_unplaced_exits()
    check("9. ... twice = nothing more", ex[0]["pnl"] == 0.0 and ex[1]["pnl"] == 400.0)
    b.cfg = {"adapter": "paper", "sym": "NQ", "tf": "5m"}
    b.ledger[1].update(pnl=-965.3, void=None)
    b._void_unplaced_exits()
    check("9. paper bot: never voids", b.ledger[1]["pnl"] == -965.3)


def part10(tmp):
    import datetime as dt
    from engine import nt_log
    d = os.path.join(tmp, "NinjaTrader 8", "log")
    os.makedirs(d)
    with open(os.path.join(d, "log.20261027.00000.txt"), "w", encoding="utf-8") as fh:
        fh.write("2026-10-27 06:12:05:101|1|64|Order='LE1793095920W924ME/MFFUEVBLD000006016' New state='Rejected' "
                 "Error='Order rejected' Native error='x C:\\Users\\someone\\file.txt'\n"
                 "2026-10-27 06:13:00:000|1|2|Chart refreshed\n2026-10-26 23:00:00:000|1|4|error for bob@mail.com\n"
                 "2026-10-20 01:00:00:000|1|4|old error line\n")
    r = nt_log.lines(os.path.dirname(d), today=dt.date(2026, 10, 27))
    ln = r.get("lines") or []
    check("10. NinjaTrader log for the heartbeat: our order's rejection line kept", ln and "LE1793095920" in ln[0] and "Rejected" in ln[0], r)
    check("10. ... no file path, no e-mail, nothing older than yesterday, no unrelated line",
          all("Users" not in x and "@" not in x for x in ln) and len(ln) == 2 and not any("old" in x or "Chart" in x for x in ln), ln)
    o = os.path.join(os.path.dirname(d), "outgoing")
    os.makedirs(o)
    for n, t in (("Simulation.txt", "CONNECTED"), ("MNQ 12-26 Globex_Sim101_position.txt", "FLAT;0;0"),
                 ("LE1793095920W924ME.txt", "WORKING;0;0"), ("abc123.txt", "FILLED;1;25000")):
        open(os.path.join(o, n), "w").write(t)
    sm = nt_log.outgoing_summary(os.path.dirname(d))
    check("10. outgoing summary: connections, accounts with position files, our order files", sm.get("connections") == ["Simulation=CONNECTED"]
          and sm.get("position_accounts") == {"Sim101": 1} and sm.get("le_orders") == 1 and sm.get("files") == 4, sm)


def main():
    tmp = tempfile.mkdtemp(prefix="le_notplaced_")
    try:
        for part in (part1, part2, part3, part4, part5, part6, part8, part9, part10, part7):
            d = os.path.join(tmp, part.__name__)
            os.makedirs(d)
            part(d)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"acct B not placed: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
