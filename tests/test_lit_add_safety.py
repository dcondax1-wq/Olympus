"""Safety of the LIT scale-in (add after breakeven) live route, against the self-test's fake NinjaTrader (engine/ninjatrader
_FakeNT) and a LiveBot with a stub adapter. Regression tests for the 2026-10-20 safety review.

    python -X utf8 -m tests.test_lit_add_safety          (~2 s, no data files, no network)

1. BE gate: the adapter refuses an add while the bracket's stop is not at (or better than) the add's stop; LiveBot does not
   route an add while the broker stop (bracket + accepted modifies) is not the model's breakeven stop.
2. Naked remainder: an add fills, the old-quantity stop fills before the resize -> the remainder is closed at once.
3. Double add after a restart: a new adapter from the same state file refuses the same add number; LiveBot has saved the
   add as done before the broker call.
4. Real fills: a pending add later cancelled -> 0 micros in the ledger; a partial / repriced fill -> the broker's qty / price.
5. Age limit: an add seen > 20 s after its 1m CISD candle closed is not routed.
6. Cloud paper ledger: an add is sized like the PC (engine/sizing.scale_in_qty on the ledger's own eval state).
Second review (A-C):
A. A partial stop fill then the resized target filling the rest -> flat: no false "rest had no stop" CLOSEPOSITION / alert
   (the other leg's fill is subtracted; the position file written after the fill decides).
B. An add that fills after the model's exit (its cancel too late): the retired leg stays watched (also across a restart,
   state file "watch") and the leftover is closed at once + alert.
C. A crash between the add's order file and the state save: the add is saved first; LiveBot books an add it lost from
   the adapter's add_fills.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import live  # noqa: E402
from engine import ninjatrader as N  # noqa: E402
from engine.ninjatrader import ET, NinjaTraderAdapter, _FakeNT  # noqa: E402
from engine.sizing import LIVE_COMM  # noqa: E402  (live bookings: $1.90 a micro, not the research $1.40)

RES = []
P = ("Sim101", "MNQ 12-26")


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info and not ok else ''}")
    RES.append(bool(ok))


class World:
    def __init__(self):
        self.tmp = tempfile.mkdtemp()
        self.folder = os.path.join(self.tmp, "NinjaTrader 8")
        self.fake = _FakeNT(self.folder)
        self.now = [dt.datetime(2026, 10, 22, 10, 0, 3, tzinfo=ET).timestamp()]
        self.alerts = []

    def make(self, sp="s.json"):
        cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": self.folder,
               "params": {"max_micros": 40, "flat_mod": 955}, "model": "lit", "model_params": {"window": [[120, 930]]},
               "nt_state_path": os.path.join(self.tmp, sp), "nt_audit_log": os.path.join(self.tmp, "oif.log")}
        ad = NinjaTraderAdapter(cfg, clock=lambda: self.now[0])
        ad._sleep = lambda s: (self.fake.process(), self.now.__setitem__(0, self.now[0] + s))
        ad._alert_fn = self.alerts.append
        return ad

    def working(self):
        return {k: (o["type"], o["qty"]) for k, o in self.fake.orders.items() if o["state"] in N.LIVE_STATES}


def adapter_tests():
    w = World()
    fake = w.fake
    # ---- 2. add fills, the BE stop (still qty 2) fills before the resize -> remainder closed
    fake.move(25020.0)
    ad = w.make("a.json")
    t = int(w.now[0]) - 3
    ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    ad.send({"side": "modify", "stop": 25021.25, "entry_t": t})
    fake.move(25040.0)
    fake.hold_market = True
    r = ad.send({"side": "add", "qty": 3, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25, "target": 25100.0})
    fake.hold_market = False
    aid = ad.legs[0]["adds"][0]["id"]
    fake._fill(aid, 3, 25040.0)            # the add fills (position 5) ...
    fake.move(25021.0)                     # ... and the BE stop (qty 2) fills before any resize: 3 left with no stop
    n_al = len(w.alerts)
    ad.tick()
    check("2. stop filled at the old qty after an add -> the remainder (3) is closed at once, nothing left working, alert",
          r.get("pending") and fake.pos.get(P, [0])[0] == 0 and not ad.legs and not w.working() and len(w.alerts) > n_al,
          json.dumps([fake.pos.get(P), w.working(), r]))
    # ---- 1. the broker stop never moved to BE: the add is refused (no order file)
    w.now[0] += 3600
    fake.move(25020.0)
    ad = w.make("b.json")
    t = int(w.now[0]) - 3
    ad.send({"sym": "NQ", "side": "buy", "qty": 10, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    fake.move(25040.0)
    k = len(fake.files)
    r = ad.send({"side": "add", "qty": 10, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25, "target": 25100.0})
    r0 = ad.send({"side": "add", "qty": 10, "dir": 1, "entry_t": t, "n": 1})
    check("1. adapter: add refused while the bracket stop is 24990 and the add was sized at 25021.25; an add without a stop "
          "is refused; no order file", not r["ok"] and "not adding while the stop" in r["error"] and not r0["ok"]
          and len(fake.files) == k and fake.pos[P][0] == 10, json.dumps([r, r0]))
    ad.send({"side": "modify", "stop": 25021.25, "entry_t": t})
    r = ad.send({"side": "add", "qty": 10, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25, "target": 25100.0})
    check("1. adapter: the same add goes through once the stop is at breakeven (bracket 20)",
          r["ok"] and fake.pos[P][0] == 20 and ad.legs[0]["bracket_qty"] == 20, json.dumps(r))
    # ---- 3. restart: a new adapter from the same state file, the same add n=1 again -> refused
    ad2 = w.make("b.json")
    ad2.tick()
    k = len(fake.files)
    r2 = ad2.send({"side": "add", "qty": 10, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25, "target": 25100.0})
    check("3. adapter restart: add 1 again for the same entry -> refused (add numbers in the state file), no order file",
          not r2["ok"] and "already sent" in r2["error"] and len(fake.files) == k and fake.pos[P][0] == 20, json.dumps(r2))
    fills = ad2.add_fills(t)
    check("4. add_fills reports the real add (n 1, 10 filled @ 25040)",
          len(fills) == 1 and fills[0]["n"] == 1 and fills[0]["filled"] == 10 and fills[0]["fill_px"] == 25040.0, fills)
    ad2.send({"side": "exit", "reason": "x", "entry_t": t})
    check("cleanup flat", fake.pos[P][0] == 0)
    # ---- 4. a pending add cancelled unfilled after the timeout -> status rejected, 0 filled
    w.now[0] += 3600
    fake.move(25020.0)
    ad = w.make("c.json")
    t = int(w.now[0]) - 3
    ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    ad.send({"side": "modify", "stop": 25021.25, "entry_t": t})
    fake.move(25040.0)
    fake.hold_market = True
    ad.send({"side": "add", "qty": 3, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25})
    fake.hold_market = False
    w.now[0] += 60
    ad.tick()                                      # > 45 s: cancel sent
    ad.tick()                                      # CANCELLED read back
    fl = ad.add_fills(t)
    check("4. pending add never filled -> cancelled after 45 s, add_fills shows 0 filled (status rejected)",
          fl and fl[0]["filled"] == 0 and fl[0]["status"] == "rejected" and fake.pos[P][0] == 2, json.dumps(fl))
    ad.send({"side": "exit", "reason": "x", "entry_t": t})
    return w


class StubAdapter:
    """A broker adapter for LiveBot: route_adds + route_stop_moves, records every action, real add fills on demand."""
    name = "stub"
    route_adds = route_stop_moves = True

    def __init__(self, bot):
        self.bot, self.sent, self.fills, self.on_add = bot, [], [], None

    def send(self, a):
        self.sent.append(dict(a))
        if a.get("side") == "add":
            if self.on_add:
                self.on_add(a)
            return {"ok": False, "pending": True, "add_id": "X1"}
        return {"ok": True}

    def has_open_bracket(self, entry_t=None):
        return True

    def add_fills(self, entry_t):
        return list(self.fills)


def make_bot(tmp, now):
    b = live.LiveBot()
    b.clock = lambda: now[0]
    b.state_path = os.path.join(tmp, "live_state.json")
    b._remember = lambda *a, **kw: None
    b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "params": {"max_micros": 40}}
    b.adapter = StubAdapter(b)
    b.state = {"model": "lit", "strategy": {"params": {"scale_in": {"f": 1.0}}}}
    return b


def bot_tests():
    tmp = tempfile.mkdtemp()
    t_b = int(dt.datetime(2026, 10, 22, 4, 0, tzinfo=ET).timestamp())
    now = [t_b + 9 * 60 + 2]
    pos = {"entry_t": t_b, "dir": 1, "qty": 4, "entry": 25020.0, "stop": 25021.25, "stop0": 24990.0, "target": 25110.0,
           "risk_pts": 30.0, "be": True}
    an = {"n": 1, "t": t_b + 9 * 60, "cisd_t": t_b + 8 * 60, "px": 25045.25, "est": False, "rk": 24.0, "prev_rk": [],
          "dist": 25.25, "qty": 4, "f": 1.0}
    entry_row = {"t": t_b, "sym": "NQ", "side": "buy", "qty": 4, "stop": 24990.0, "target": 25110.0, "entry_t": t_b,
                 "result": {"ok": True}}
    # ---- 1. LiveBot: broker stop still the first stop -> not routed
    b = make_bot(tmp, now)
    b._open_routed, b._open_qty = t_b, 4
    b.ledger = [dict(entry_row)]
    b._route_add({**pos, "add_now": an}, "NQ")
    check("1. LiveBot: add not routed while the broker stop is 24990 (BE 25021.25 never accepted)",
          not [a for a in b.adapter.sent if a["side"] == "add"] and not b._open_adds, b.adapter.sent)
    # modify refused -> still not routed; accepted -> routed
    b = make_bot(tmp, now)
    b._open_routed, b._open_qty = t_b, 4
    b.ledger = [dict(entry_row), {"t": t_b + 300, "side": "modify", "stop": 25021.25, "entry_t": t_b, "result": {"ok": False}}]
    b._route_add({**pos, "add_now": an}, "NQ")
    ok1 = not [a for a in b.adapter.sent if a["side"] == "add"]
    b = make_bot(tmp, now)
    b._open_routed, b._open_qty = t_b, 4
    b.ledger = [dict(entry_row), {"t": t_b + 300, "side": "modify", "stop": 25021.25, "entry_t": t_b, "result": {"ok": True}}]
    seen_at_send = []
    b.adapter.on_add = lambda a: seen_at_send.append(
        ["add", t_b, 1] in json.load(open(b.state_path, encoding="utf-8")).get("seen", []))
    b._route_add({**pos, "add_now": an}, "NQ")
    adds = [a for a in b.adapter.sent if a["side"] == "add"]
    check("1. LiveBot: a refused BE modify blocks the add; an accepted one lets it through with the BE stop",
          ok1 and len(adds) == 1 and adds[0]["stop"] == 25021.25 and adds[0]["n"] == 1, b.adapter.sent)
    check("3. LiveBot: the add is saved as done (state file 'seen') before the broker call", seen_at_send == [True], seen_at_send)
    b._route_add({**pos, "add_now": an}, "NQ")
    check("3. LiveBot: the same add decision is not routed twice", len([a for a in b.adapter.sent if a["side"] == "add"]) == 1)
    # ---- 4. real fills: pending -> cancelled = 0; partial / repriced
    check("4. pending add booked at the asked size until the broker reports", b._adds_qty(t_b) == 4, b._open_adds)
    b.adapter.fills = [{"n": 1, "id": "X1", "qty": 4, "filled": 0, "fill_px": None, "status": "rejected"}]
    q_cancel = b._adds_qty(t_b)
    b.adapter.fills = [{"n": 1, "id": "X1", "qty": 4, "filled": 3, "fill_px": 25047.0, "status": "filled"}]
    q_part = b._adds_qty(t_b)
    tr = {"entry_t": t_b, "exit_t": t_b + 1800, "exit_reason": "TARGET", "qty": 4, "pnl": 0.0, "dir": 1, "entry": 25020.0,
          "exit_price": 25110.0, "pts": 90.0, "adds": [{"px": 25045.25, "qty": 4, "pts": 64.75}]}
    from engine import lit as _lit
    want = round(4 * (90.0 * _lit.PV - LIVE_COMM) + 3 * ((25110.0 - 25047.0) * _lit.PV - LIVE_COMM), 2)
    pnl = b._routed_pnl(tr, 4)
    check("4. add cancelled unfilled -> 0 micros; partial fill 3 @ 25047 -> ledger P&L from 3 @ 25047 (not 4 @ 25045.25)",
          q_cancel == 0 and q_part == 3 and abs(pnl - want) < 0.01, f"{q_cancel} {q_part} {pnl} {want}")
    # ---- 5. age limit
    b = make_bot(tmp, now)
    b._open_routed, b._open_qty = t_b, 4
    b.ledger = [dict(entry_row), {"t": t_b + 300, "side": "modify", "stop": 25021.25, "entry_t": t_b, "result": {"ok": True}}]
    now[0] = an["t"] + 25
    b._route_add({**pos, "add_now": an}, "NQ")
    late = [a for a in b.adapter.sent if a["side"] == "add"]
    b2 = make_bot(tmp, now)
    b2._open_routed, b2._open_qty = t_b, 4
    b2.ledger = list(b.ledger)
    now[0] = an["t"] + 15
    b2._route_add({**pos, "add_now": an}, "NQ")
    check("5. add seen 25 s after its CISD close -> not routed; 15 s -> routed", not late
          and len([a for a in b2.adapter.sent if a["side"] == "add"]) == 1)


def cloud_tests():
    from engine import sizing
    from tools import cloud_monitor as cm
    t0 = int(dt.datetime(2026, 10, 22, 4, 0, tzinfo=ET).timestamp())
    tr = {"entry_t": t0, "exit_t": t0 + 1800, "exit_reason": "TARGET", "qty": 10, "pnl": 0.0, "pnl_r": 3.0, "dir": 1,
          "entry": 25020.0, "stop": 24990.0, "target": 25110.0, "exit_price": 25110.0, "pts": 90.0, "risk_pts": 30.0,
          "adds": [{"px": 25045.25, "qty": 10, "pts": 64.75, "rk": 24.0, "prev_rk": []}]}
    ls = {"mode": "two_week", "eval_start": "2026-10-19"}
    before = {t0 - 86400: {"day": "2026-10-21", "usd": -1500.0, "exit": "STOP", "exit_ts": t0 - 86000}}
    usd, qa = cm.lit_add_usd(before, tr, 6, ls, 1.0)
    room = cm.eval_track(before, "2026-10-19")["cushion"]
    want_q = sizing.scale_in_qty(6, 6, 30.0, [{"rk": 24.0, "prev_rk": []}], f=1.0, state={"room": room, "cum": 0.0})
    from engine import lit as _lit
    want = round(6 * (90.0 * _lit.PV - LIVE_COMM) + want_q[0] * (64.75 * _lit.PV - LIVE_COMM), 2)
    check("6. cloud ledger: the add sized by scale_in_qty on the ledger's eval state (as the PC), $ includes it",
          qa == want_q and abs(usd - want) < 0.01, f"{qa} {want_q} {usd} {want} room {room}")
    usd_n, qa_n = cm.lit_add_usd({}, tr, 5, {"mode": "normal"}, 1.0)
    check("6. cloud ledger normal mode: the model's add x paper micros / model micros (10 x 5 / 10 = 5)", qa_n == [5], qa_n)


def _lines(fake, k):
    return [ln for _, ls in fake.files[k:] for ln in ls]


def _be_with_add(w, sp, held=True):
    """Long 2 @ 25020, stop at BE 25021.25, then an add of 3 sent while the market holds (pending)."""
    f = w.fake
    f.move(25020.0)
    ad = w.make(sp)
    t = int(w.now[0]) - 3
    ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    ad.send({"side": "modify", "stop": 25021.25, "entry_t": t})
    f.move(25040.0)
    f.hold_market = held
    r = ad.send({"side": "add", "qty": 3, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25, "target": 25100.0})
    return ad, t, r


def review2_tests():
    """Second safety review (2026-10-20): A false 'rest had no stop', B late add fill after the exit, C crash between the
    add's order file and the state save."""
    # ---- A. stop fills 1 of 4, the target is resized to 3, the target fills 3 -> flat: no CLOSEPOSITION, no alert
    w = World()
    f = w.fake
    f.move(25020.0)
    ad = w.make("ra.json")
    t = int(w.now[0]) - 3
    ad.send({"sym": "NQ", "side": "buy", "qty": 4, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    lg = ad.legs[0]
    f._fill(lg["stop_id"], 1, 24990.0)
    ad.tick()
    tq = f.orders[lg["target_id"]]["qty"]
    f.move(25100.0)
    na, k = len(w.alerts), len(f.files)
    ad.tick()
    ln = _lines(f, k)
    check("A. partial stop 1/4 then target 3/3 -> flat: no CLOSEPOSITION, no 'had no stop' alert, retired as target filled",
          tq == 3 and f.pos[P][0] == 0 and not any(x.startswith("CLOSEPOSITION") for x in ln) and len(w.alerts) == na
          and ad.history[-1]["closed"] == "target filled" and not ad.legs, json.dumps([tq, ln, w.alerts[na:]]))
    # A2. the same with the position file NOT flat after the target fill (a real leftover) -> still closed + alert
    w = World()
    f = w.fake
    f.move(25020.0)
    ad = w.make("ra2.json")
    t = int(w.now[0]) - 3
    ad.send({"sym": "NQ", "side": "buy", "qty": 4, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    lg = ad.legs[0]
    f._fill(lg["stop_id"], 1, 24990.0)
    ad.tick()
    f.pos[P][0] += 2                                   # 2 more long that the bracket does not cover (e.g. a fill nobody saw)
    f.move(25100.0)
    na = len(w.alerts)
    ad.tick()
    check("A. target filled but NinjaTrader still shows a position afterwards -> CLOSEPOSITION + alert",
          f.pos[P][0] == 0 and len(w.alerts) > na and "no stop" in w.alerts[-1], json.dumps([f.pos[P], w.alerts[na:]]))
    # ---- B. add pending, the model exits (CUT_T15), the add fills after its cancel -> closed at once + alert
    w = World()
    f = w.fake
    f.close_cancels = False
    ad, t, r = _be_with_add(w, "rb.json")
    f.slow_cancel = True
    x = ad.send({"side": "exit", "reason": "CUT_T15", "entry_t": t})
    aid = ad.history[-1]["adds"][0]["id"]
    watched = len(ad.watch)
    f.hold_market = False
    f._fill(aid, 3, 25041.0)                            # NinjaTrader filled the add after all: 3 long, no stop
    w.now[0] += 60
    na, k = len(w.alerts), len(f.files)
    ad.tick()
    ln = _lines(f, k)
    check("B. late add fill after the exit: the retired leg is watched, the 3 left are closed at once, alert",
          x.get("ok") and watched == 1 and f.pos[P][0] == 0 and any(z.startswith("CLOSEPOSITION") for z in ln)
          and len(w.alerts) > na and "AFTER the bot closed it" in w.alerts[na], json.dumps([watched, f.pos[P], ln, w.alerts[na:]]))
    fl = ad.add_fills(t)
    check("B. add_fills still reports the late add (3 @ 25041) for the ledger",
          fl and fl[0]["filled"] == 3 and fl[0]["fill_px"] == 25041.0, fl)
    # B2. the same late fill seen only by a NEW process (restart after the exit): the watch is in the state file
    w = World()
    f = w.fake
    f.close_cancels = False
    ad, t, r = _be_with_add(w, "rb2.json")
    f.slow_cancel = True
    ad.send({"side": "exit", "reason": "TIME", "entry_t": t})
    aid = ad.history[-1]["adds"][0]["id"]
    ad2 = w.make("rb2.json")
    restored = len(ad2.watch)
    f.hold_market = False
    f._fill(aid, 3, 25041.0)
    w.now[0] += 60
    na = len(w.alerts)
    ad2.tick()
    check("B. restart after the exit: the new adapter still watches the add and closes its late fill",
          restored == 1, restored)
    check("B. ... position flat, alert", f.pos[P][0] == 0 and len(w.alerts) > na, json.dumps([f.pos[P], w.alerts[na:]]))
    # B3. the add's cancel works (no fill): the watch ends, nothing closed
    w = World()
    f = w.fake
    ad, t, r = _be_with_add(w, "rb3.json")
    ad.send({"side": "exit", "reason": "CUT_T15", "entry_t": t})
    k = len(f.files)
    w.now[0] += 60
    ad.tick()
    check("B. add cancelled cleanly with the exit -> no watch left, no CLOSEPOSITION",
          not ad.watch and not any(z.startswith("CLOSEPOSITION") for z in _lines(f, k)) and f.pos[P][0] == 0,
          json.dumps([ad.watch, _lines(f, k)]))
    # ---- C. crash after the add's order file, before anything else: the add is in the state file already
    w = World()
    f = w.fake
    f.move(25020.0)
    ad = w.make("rc.json")
    t = int(w.now[0]) - 3
    ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t})
    ad.send({"side": "modify", "stop": 25021.25, "entry_t": t})
    f.move(25040.0)
    orig = ad._send_lines

    def crash(lines, label):
        res = orig(lines, label)
        if label == "ADD":
            raise RuntimeError("process killed")
        return res
    ad._send_lines = crash
    ad.send({"side": "add", "qty": 3, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25, "target": 25100.0})
    ad2 = w.make("rc.json")
    ad2.tick()
    lg = ad2.legs[0] if ad2.legs else {}
    check("C. crash right after the add's order file: the restarted adapter knows the add, grows the bracket to 5",
          f.pos[P][0] == 5 and lg.get("bracket_qty") == 5 and f.orders[lg["stop_id"]]["qty"] == 5
          and f.orders[lg["target_id"]]["qty"] == 5, json.dumps([f.pos[P], lg.get("bracket_qty")]))
    r2 = ad2.send({"side": "add", "qty": 3, "dir": 1, "entry_t": t, "n": 1, "stop": 25021.25, "target": 25100.0})
    fl = ad2.add_fills(t)
    check("C. ... the same add is refused again; add_fills reports it (3 @ 25040)",
          not r2["ok"] and "already sent" in r2["error"] and fl and fl[0]["filled"] == 3 and fl[0]["fill_px"] == 25040.0,
          json.dumps([r2, fl]))
    f.move(25021.0)
    ad2.tick()
    check("C. ... the BE stop closes all 5", f.pos[P][0] == 0, f.pos[P])
    # C. LiveBot lost the add (crash before its own save): the ledger books it from the adapter's fills
    tmp = tempfile.mkdtemp()
    now = [t + 600]
    b = make_bot(tmp, now)
    b._open_routed, b._open_qty = t, 2
    b.adapter.fills = [{"n": 1, "id": "X1", "qty": 3, "filled": 3, "fill_px": 25040.0, "status": "filled"}]
    q = b._adds_qty(t)
    tr = {"entry_t": t, "exit_t": t + 1800, "exit_reason": "TARGET", "qty": 2, "pnl": 0.0, "dir": 1, "entry": 25020.0,
          "exit_price": 25100.0, "pts": 80.0}
    from engine import lit as _lit
    want = round(2 * (80.0 * _lit.PV - LIVE_COMM) + 3 * ((25100.0 - 25040.0) * _lit.PV - LIVE_COMM), 2)
    pnl = b._routed_pnl(tr, 2)
    check("C. LiveBot restart without the add in its ledger: booked from NinjaTrader's fill (3 @ 25040) in qty and P&L",
          q == 3 and abs(pnl - want) < 0.01 and b._open_adds and b._open_adds[0].get("restored"), f"{q} {pnl} {want} {b._open_adds}")
    b2 = make_bot(tmp, now)
    b2.adapter.fills = [{"n": 2, "id": "X2", "qty": 3, "filled": 0, "fill_px": None, "status": "sent"}]
    check("C. ... an unfilled adapter add is not booked", b2._adds_qty(t) == 0)


def main():
    adapter_tests()
    bot_tests()
    review2_tests()
    cloud_tests()
    n = sum(RES)
    print(f"\nscale-in add safety: {n}/{len(RES)} {'PASS' if n == len(RES) else 'FAIL'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
