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
    want = round(4 * (90.0 * _lit.PV - _lit.COMM) + 3 * ((25110.0 - 25047.0) * _lit.PV - _lit.COMM), 2)
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
    want = round(6 * (90.0 * _lit.PV - _lit.COMM) + want_q[0] * (64.75 * _lit.PV - _lit.COMM), 2)
    check("6. cloud ledger: the add sized by scale_in_qty on the ledger's eval state (as the PC), $ includes it",
          qa == want_q and abs(usd - want) < 0.01, f"{qa} {want_q} {usd} {want} room {room}")
    usd_n, qa_n = cm.lit_add_usd({}, tr, 5, {"mode": "normal"}, 1.0)
    check("6. cloud ledger normal mode: the model's add x paper micros / model micros (10 x 5 / 10 = 5)", qa_n == [5], qa_n)


def main():
    adapter_tests()
    bot_tests()
    cloud_tests()
    n = sum(RES)
    print(f"\nscale-in add safety: {n}/{len(RES)} {'PASS' if n == len(RES) else 'FAIL'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
