"""Router determinism: LIT (its own account) + ATLAS (account B, engine/account_b.py). Pre-launch audit A4 (2026-10-25,
research/handoff/2026-10-25/A4_eval_risk.md). Paper only: paper / recording adapters, temp state files, second_model.json
and live_model*.json only read (account B is OFF in the shipped second_model.json: "account_b": null).

  1. ATLAS never opposes LIT: a B entry is blocked while LIT holds, is entering, has a limit ARMED, is waiting for its 1m
     CISD, or still has a routed position in the other direction (both directions when both LIT setups are armed); the same
     direction is allowed; an extra account holding the other side blocks too
  2. one poll, fixed order: LIT routes first (poll_once: _route_signals -> _second_route_tick -> _account_b_tick), and inside
     LIT's entry the B hedge check (close + confirm) comes before LIT's order (_route_primary)
  3. simultaneous signals: LIT entering SHORT in the same poll in which ATLAS would go LONG at the 5m open -> ATLAS blocked;
     LIT entering while B is LONG -> B's HEDGE close is sent and confirmed before LIT's sell (recorded order)
  4. cancel / fill races (BUG_FIX 2026-10-25): (a) B's own entry sent and not yet confirmed blocks a 2nd entry; (b) a HEDGE
     close the broker refuses keeps B's position (never marked flat), LIT's opposite entry waits and is routed once a retry
     is confirmed; (c) never confirmed within LIT's entry deadline (90 s from the 1m fill bar open) -> LIT's entry skipped,
     critical "HEDGE BLOCKED: ATLAS close not confirmed", B still managed; (d) NinjaTrader: CLOSEPOSITION accepted but the
     leg still "closing" (position file not FLAT) = not confirmed; B's PENDING entry (sent, not filled) counts as opposite
  5. no duplicate ATLAS position: members signalling on the same 5m open -> ONE order, the first member in the configured
     order (EMA > MACD > S/R) whose own signal passes the no-hedging rule, the size and the guards (BUG_FIX 2026-10-25, =
     the research executor tools/atlas: a blocked member hands the bar to the next); a 2nd poll on the same bar sends
     nothing; an account-level block (2 a day, lock, eval passed / stuck) stops every member
  6. daily counters survive a restart: account B's entries today, its soft-daily-loss lock (same day only), LIT's account
     ledger (second-strategy rows today) are restored from the state files
  7. day / week boundaries: the CME trading day starts at 18:00 ET (17:59:59 -> today, 18:00 -> next day; Sunday 18:00 ->
     Monday; the DST weekends), identical in engine/live.py, engine/account_b.py, engine/multi_account.py; eval sessions skip
     Christmas; the eval week is the ISO week of the trading day; the calendar guard blocks Christmas, the weekend, the
     17:00-18:00 break and entries within 15 min of the 13:15 early close on Nov 27 / Dec 24; the 25K adapter caps 20 micros

    python -X utf8 -m tests.test_router_determinism        # ~3 s
"""
from __future__ import annotations

import datetime as dt
import inspect
import json
import logging
import os
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
logging.disable(logging.CRITICAL)

import pandas as pd  # noqa: E402

from engine import account_b as AB  # noqa: E402
from engine import guards as G  # noqa: E402
from engine import live  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import second  # noqa: E402
from engine import sizing as sz  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []
NOTES = []
TMP = tempfile.mkdtemp()
KEYS = ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def note(text):
    NOTES.append(text)
    print(f"[NOTE] {text}", flush=True)


def at(day, h, m, s=0):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m, s), ET).timestamp())


NOW = at("2026-10-21", 10, 0)          # a Wednesday 10:00 ET, a 5m open


class Rec:
    """A recording adapter: every send lands in one shared order list (who, side, reason)."""

    def __init__(self, who, log, ok=True):
        self.who, self.log, self.ok, self.name = who, log, ok, who     # ok: True / False, or a list of answers in turn

    def send(self, a):
        self.log.append((self.who, a.get("side"), a.get("reason")))
        ok = self.ok.pop(0) if isinstance(self.ok, list) and self.ok else self.ok
        if isinstance(ok, list):
            ok = False
        return {"ok": True} if ok else {"ok": False, "error": "REFUSED by the test broker"}


def fake_bot(**kw):
    b = types.SimpleNamespace(state=kw.get("state") or {}, _open_routed=kw.get("open_routed"), ledger=kw.get("ledger") or [],
                              accts=kw.get("accts"), cfg={"adapter": "paper", "sym": "NQ"}, health={}, kill=False,
                              state_path=None, logs=[], pushed=[], _no_entries_day=None, _forming={}, _lit_sizing=None)
    b.clock = lambda: kw.get("now", NOW + 2)
    b._log = lambda kind, text, **k: b.logs.append((kind, text))
    b._note_error = lambda text: b.logs.append(("error", text))
    b._push_send = lambda p: b.pushed.append(p)
    return b


def spec(plan="builder25k", keys=None):
    return AB.normalize({"account": "Sim102", "plan": plan, "eval_start": "2026-10-19", "strategies": keys or list(KEYS)})


def acct_b(bot, name="b.json", log=None, ok=True, plan="builder25k"):
    B = AB.AccountB(bot, spec(plan), state_path=os.path.join(TMP, name))
    B.adapter = Rec("B", log if log is not None else [], ok)
    B.guard = lambda act, entry_t, now: None          # the guards themselves are checked in part 7 / tests.test_guards
    return B


def signals(tb, sigs):
    """engine/second.run stand-in: {key: dir} -> one OPEN trade at the 5m open tb per key."""
    def run(df5, one_min=None, now=None, cfg=None, lit=None):
        out = {}
        for k in (cfg or {}).get("strategies") or {}:
            if k in sigs:
                d = sigs[k]
                e = 25000.0
                out[k] = {"trades": [{"entry_t": tb, "exit_kind": "OPEN", "dir": d, "entry": e, "stop": e - 20.0 * d,
                                      "target": e + 40.0 * d, "qty": 3}]}
            else:
                out[k] = {"trades": []}
        return {"strategies": out}
    return run


def probe(B, tb, sigs, now=None):
    df5 = pd.DataFrame({"time": [tb - 300], "open": [25000.0], "high": [25001.0], "low": [24999.0], "close": [25000.0],
                        "volume": [10.0]})
    B.bot.state.setdefault("price", 25000.0)
    old = second.run
    second.run = signals(tb, sigs)
    try:
        sc = second.load_cfg()
        sub = {**sc, "strategies": {k: sc["strategies"][k] for k in B.spec["keys"]}}
        B.entry(df5, None, sub, list(B.spec["keys"]), "NQ", now if now is not None else tb + 2)
    finally:
        second.run = old
    return [r for r in B.ledger if r.get("side") in ("buy", "sell")]


# ------------------------------------------------------------------------------------------------ 1
def part_opposite():
    S = spec()
    mk = lambda **kw: AB.AccountB(fake_bot(**kw), S, state_path=os.path.join(TMP, "x.json"))
    cases = {
        "position": {"state": {"position": {"dir": -1}}},
        "entering (1m CISD closed, market order now)": {"state": {"enter_now": {"dir": -1}}},
        "limit armed": {"state": {"setups": {"short": {"tapped_t": None, "limit": 25010.0}}}},
        "tapped, waiting for its 1m CISD": {"state": {"setups": {"short": {"tapped_t": NOW - 120, "limit": 25010.0}}}},
        "routed position (ledger)": {"ledger": [{"side": "sell", "entry_t": NOW - 600}], "open_routed": NOW - 600},
    }
    res = {lab: (bool(mk(**kw).lit_opposite(1)), mk(**kw).lit_opposite(-1) is None) for lab, kw in cases.items()}
    check("1 LIT SHORT in any state (position / entering / limit armed / waiting for its 1m CISD / routed) blocks an ATLAS "
          "LONG and allows an ATLAS SHORT", all(a and b for a, b in res.values()), res)
    mir = {lab: bool(mk(**{k: (json.loads(json.dumps(v).replace('"dir": -1', '"dir": 1').replace('"short"', '"long"')
                                       .replace('"sell"', '"buy"')) if k != "open_routed" else v) for k, v in kw.items()}).lit_opposite(-1))
           for lab, kw in cases.items()}
    check("1 mirrored: LIT LONG in any state blocks an ATLAS SHORT", all(mir.values()), mir)
    both = mk(state={"setups": {"long": {"tapped_t": None}, "short": {"tapped_t": NOW - 60}}})
    check("1 both LIT setups armed (a long limit and a short waiting for its 1m CISD) -> ATLAS blocked both ways",
          bool(both.lit_opposite(1)) and bool(both.lit_opposite(-1)))
    acc = types.SimpleNamespace(opposite_open=lambda d, exclude=None: "extra account SimX holds a SHORT" if d == 1 else None)
    check("1 an extra account holding the other side blocks an ATLAS entry", bool(mk(accts=acc).lit_opposite(1))
          and mk(accts=acc).lit_opposite(-1) is None)


# ------------------------------------------------------------------------------------------------ 2
def part_order():
    src = inspect.getsource(live.LiveBot.poll_once)
    i = [src.find(x) for x in ("self._route_signals(", "self._save_state()", "self._second_route_tick(", "self._account_b_tick(")]
    check("2 one poll: LIT routes, the state is saved, then the routed second strategies, then account B (fixed order)",
          all(x >= 0 for x in i) and i == sorted(i), i)
    rp = inspect.getsource(live.LiveBot._route_primary)
    j = [rp.find(x) for x in ("self._hedge_clear(ent, sym, now)", "self._second_preempt(", "rr = self._route(self._entry_action(ent, q, sym))")]
    check("2 inside LIT's entry: account B's hedge close + confirmation, then the second-strategy pre-empt, then LIT's order",
          all(x >= 0 for x in j) and j == sorted(j), j)


# ------------------------------------------------------------------------------------------------ 3 + 4
class NTLike(Rec):
    """A NinjaTrader-like recorder: keeps legs; CLOSEPOSITION is accepted but the leg stays "closing" until flat_now()."""

    def __init__(self, who, log, et_, status="protected"):
        super().__init__(who, log, True)
        self.legs = [{"entry_t": et_, "status": status, "instrument": "MNQ 12-26"}]

    def send(self, a):
        self.log.append((self.who, a.get("side"), a.get("reason")))
        if a.get("side") == "exit":
            for lg in self.legs:
                lg["status"] = "closing"
        return {"ok": True}

    def flat_now(self):
        self.legs = []


def lit_bot(order, b_ok=True, b_adapter=None, b_dir=1):
    bot = live.LiveBot()
    bot.state_path = os.path.join(TMP, "live_state.json")
    bot.cfg = {"adapter": "paper", "sym": "NQ", "tf": "5m", "params": {}}
    bot.clock = lambda: NOW + 3
    bot.started_at = NOW - 3600
    bot.adapter = Rec("LIT", order)
    bot._equity_qty = lambda et, q, pos=None: int(q)
    bot._guard_entry = lambda *a, **k: None
    bot._guard_routed = lambda *a, **k: None
    bot._push_fill = lambda *a, **k: None
    bot._push_outcome = lambda *a, **k: None
    B = AB.AccountB(bot, spec(), state_path=os.path.join(TMP, f"b_hedge_{len(RESULTS)}.json"))
    B.adapter = b_adapter if b_adapter is not None else Rec("B", order, ok=b_ok)
    B.prov = {NOW - 900: {"key": "ema_lon_vix", "short": "EMA", "dir": b_dir, "qty": 4, "entry": 25000.0, "day": "2026-10-21"}}
    B.open_t = NOW - 900
    bot.acct_b = B
    ent = {"entry_t": NOW, "dir": -1, "qty": 6, "entry": 25010.0, "stop": 25030.0, "target": 24950.0, "tf": "1m"}
    bot.state = {"model": "lit", "position": None, "enter_now": ent, "setups": {}}
    poll(bot, 3)
    return bot, B


def poll(bot, dt_s):
    """One LIT routing pass dt_s seconds after the 1m fill bar opened (NOW)."""
    bot.clock = lambda: NOW + dt_s
    bot._route_primary({"trades": []}, "NQ", NOW + dt_s, 300)


def lit_sells(order):
    return [x for x in order if x == ("LIT", "sell", None)]


def part_simultaneous():
    bot = fake_bot(state={"enter_now": {"dir": -1}})
    B = acct_b(bot, "b_sim.json")
    r = probe(B, NOW, {"ema_lon_vix": 1})
    check("3 same poll: LIT is entering SHORT (its 1m CISD just closed) while EMA would go LONG at the 5m open -> no ATLAS order",
          not r and any("no hedging: LIT is entering SHORT" in t for _, t in bot.logs), bot.logs[-2:])
    bot = fake_bot(state={"setups": {"short": {"tapped_t": NOW - 60}}})
    B = acct_b(bot, "b_sim2.json")
    r = probe(B, NOW, {"ema_lon_vix": 1})
    check("3 same poll: LIT's short tapped and waiting for its 1m CISD -> the ATLAS LONG is not routed", not r, bot.logs[-1:])
    bot = fake_bot(state={"enter_now": {"dir": 1}})
    B = acct_b(bot, "b_sim3.json")
    r = probe(B, NOW, {"ema_lon_vix": 1})
    check("3 same poll, same direction (LIT entering LONG, EMA LONG) -> the ATLAS LONG is routed (two accounts, one side)",
          len(r) == 1 and r[0]["side"] == "buy" and r[0]["qty"] >= 1, (r, bot.logs[-2:]))
    order = []
    bot, B = lit_bot(order)
    check("3 LIT enters SHORT while ATLAS holds a LONG: B's HEDGE close goes out and is confirmed BEFORE LIT's sell",
          order[:2] == [("B", "exit", "HEDGE"), ("LIT", "sell", None)] and B.open_t is None, order)
    order = []
    bot, B = lit_bot(order, b_dir=-1)
    check("3 LIT SHORT while ATLAS is SHORT too (same side): no close, LIT routed, B kept", order == [("LIT", "sell", None)]
          and B.open_t == NOW - 900, order)
    # 4a: a sent-but-unconfirmed B entry blocks the next one
    bot = fake_bot()
    B = acct_b(bot, "b_pend.json")
    B.open_t = NOW - 300
    r = probe(B, NOW, {"macd_sweep": 1})
    check("4a ATLAS's own entry sent and not yet confirmed (open_t set) -> no 2nd probe, no 2nd order", not r and ("probe", NOW) not in B.seen)
    # 4b: the broker refuses the HEDGE close once, the retry is accepted
    order = []
    bot, B = lit_bot(order, b_ok=[False, True])
    held = not lit_sells(order) and B.open_t == NOW - 900 and (B.prov[NOW - 900].get("closing") or {}).get("done") is False \
        and not B.closes and ("entry", NOW) not in bot.seen
    check("4b BUG_FIX refused HEDGE close: B is NOT marked flat (position kept, no P&L booked), LIT's SHORT is NOT routed",
          held, (order, B.open_t, B.prov[NOW - 900].get("closing"), B.closes))
    from engine import alerts_plus as AP
    crit = [c for c in AP.pc_conditions(bot, NOW + 3) if c["kind"] == "hedge"]
    check("4b the unconfirmed close is a critical condition ('ATLAS close not confirmed', repeats until acknowledged)",
          any(c["title"] == "ATLAS close not confirmed" for c in crit) and AP.KINDS["hedge"][2] is True, crit)
    poll(bot, 33)
    check("4b next poll: the close is re-sent, accepted -> B booked flat, THEN LIT's SHORT is routed (30 s late, inside 90 s)",
          order == [("B", "exit", "HEDGE"), ("B", "exit", "HEDGE"), ("LIT", "sell", None)] and B.open_t is None
          and len(B.closes) == 1 and bot._open_routed == NOW, order)
    # 4c: never confirmed -> skipped at the deadline, HEDGE BLOCKED, B still managed
    order = []
    bot, B = lit_bot(order, b_ok=False)
    for s in (33, 63, 89):
        poll(bot, s)
    waited = not lit_sells(order)
    poll(bot, 95)
    crit = [c for c in AP.pc_conditions(bot, NOW + 95) if c["kind"] == "hedge"]
    check("4c BUG_FIX close never confirmed: LIT waits (polls at 3 / 33 / 63 / 89 s), then at 95 s (> LIT_MAX_LATE_S 90) the "
          "entry is skipped with the critical alert 'HEDGE BLOCKED: ATLAS close not confirmed'",
          waited and not lit_sells(order) and NOW in bot._blocked_entries
          and any(c["title"] == "HEDGE BLOCKED: ATLAS close not confirmed" for c in crit)
          and any("HEDGE BLOCKED" in (r.get("text") or "") for r in bot.log), (order, crit))
    check("4c B stays managed: still open (open_t kept), the close retried at polls >= 10 s apart, no P&L booked",
          B.open_t == NOW - 900 and order.count(("B", "exit", "HEDGE")) == 4 and not B.closes, (order, B.open_t))
    poll(bot, 125)
    check("4c later polls never route the skipped LIT entry", not lit_sells(order), order)
    # 4d: NinjaTrader-like adapter: CLOSEPOSITION accepted but the position file is not FLAT yet
    order = []
    nt_ad = NTLike("B", order, NOW - 900)
    bot, B = lit_bot(order, b_adapter=nt_ad)
    w = not lit_sells(order) and B.open_t == NOW - 900
    nt_ad.flat_now()                                   # NinjaTrader's position file shows FLAT
    poll(bot, 20)
    check("4d NinjaTrader: CLOSEPOSITION accepted but the leg still 'closing' -> LIT waits; once the position is FLAT the close "
          "is booked and LIT is routed (no 2nd close needed)", w and bool(lit_sells(order)) and B.open_t is None
          and order.count(("B", "exit", "HEDGE")) == 1, order)
    order = []
    nt_ad = NTLike("B", order, NOW - 900, status="entry_sent")
    bot, B = lit_bot(order, b_adapter=nt_ad)
    check("4d B's entry SENT and not filled yet (pending) counts as opposite: closed / cancelled and confirmed before LIT",
          order == [("B", "exit", "HEDGE")] and not lit_sells(order) and B.open_t == NOW - 900, order)
    B.save()
    B2 = AB.AccountB(fake_bot(), spec(), state_path=B.state_path)
    B2._load()
    check("4 restart with a close unconfirmed: B's state file still holds the open position and the pending close",
          B2.open_t == NOW - 900 and (B2.prov[NOW - 900].get("closing") or {}).get("done") is False)


# ------------------------------------------------------------------------------------------------ 5
def part_duplicates():
    bot = fake_bot()
    B = acct_b(bot, "b_dup.json")
    r = probe(B, NOW, {"macd_sweep": -1, "ema_lon_vix": 1, "sr_nyreclaim": 1})
    check("5 EMA, MACD and S/R signal on the same 5m open -> ONE order, EMA's (the configured priority EMA > MACD > S/R)",
          len(r) == 1 and r[0]["src"] == "ema_lon_vix" and r[0]["side"] == "buy", r)
    r2 = probe(B, NOW, {"macd_sweep": -1}, now=NOW + 30)
    check("5 a 2nd poll on the same 5m open sends nothing (probe de-dup + one position on B)", len(r2) == 1, r2)
    bot = fake_bot()
    B = acct_b(bot, "b_dup2.json")
    r = probe(B, NOW, {"macd_sweep": 1, "sr_nyreclaim": -1})
    check("5 MACD + S/R on the same open (EMA silent) -> MACD's order only", len(r) == 1 and r[0]["src"] == "macd_sweep", r)
    bot = fake_bot(state={"setups": {"long": {"tapped_t": None}}})
    B = acct_b(bot, "b_dup3.json")
    r = probe(B, NOW, {"ema_lon_vix": -1, "macd_sweep": 1, "sr_nyreclaim": 1})
    check("5 BUG_FIX priority = the first ALLOWED member: EMA SHORT blocked by LIT's armed long -> MACD's LONG is routed "
          "(not S/R's), one order", len(r) == 1 and r[0]["src"] == "macd_sweep" and r[0]["side"] == "buy", (r, bot.logs[-2:]))
    bot = fake_bot(state={"setups": {"long": {"tapped_t": None}}})
    B = acct_b(bot, "b_dup4.json")
    r = probe(B, NOW, {"ema_lon_vix": -1, "macd_sweep": -1})
    check("5 every member blocked (both SHORT against LIT's armed long) -> nothing routed, each logged",
          not r and sum("NOT routed on account B" in t for _, t in bot.logs) == 2, bot.logs[-2:])
    bot = fake_bot()
    B = acct_b(bot, "b_dup5.json")
    B.ledger = [{"t": NOW - 7200, "side": "buy", "entry_t": NOW - 7200, "qty": 2, "result": {"ok": True}},
                {"t": NOW - 3600, "side": "sell", "entry_t": NOW - 3600, "qty": 2, "result": {"ok": True}}]
    r = probe(B, NOW, {"ema_lon_vix": 1, "macd_sweep": 1})
    check("5 an account-level block (2 entries today) stops every member on the bar (logged once)", len(r) == 2
          and sum("NOT routed on account B" in t for _, t in bot.logs) == 1, bot.logs[-2:])


# ------------------------------------------------------------------------------------------------ 6
def part_restart():
    path = os.path.join(TMP, "b_restart.json")
    bot = fake_bot()
    B = AB.AccountB(bot, spec(), state_path=path)
    B.adapter = Rec("B", [])
    B.ledger = [{"t": NOW - 7200, "side": "buy", "entry_t": NOW - 7200, "qty": 2, "result": {"ok": True}},
                {"t": NOW - 3600, "side": "sell", "entry_t": NOW - 3600, "qty": 2, "result": {"ok": True}}]
    B.closes = [["2026-10-21", NOW - 3000, -610.0, NOW - 3600]]
    B.check_lock(NOW)
    B.save()
    B2 = AB.AccountB(fake_bot(), spec(), state_path=path)
    B2._load()
    B2.adapter = Rec("B", [])
    B2.guard = lambda *a: None
    check("6 restart: account B's entries today (2) and its soft-daily-loss lock come back from its state file",
          B2.entries_today("2026-10-21") == 2 and (B2.lock or {}).get("day") == "2026-10-21", (B2.entries_today("2026-10-21"), B2.lock))
    r = probe(B2, NOW, {"ema_lon_vix": 1})
    check("6 restart: a 3rd ATLAS signal that day is not routed (max 2 a day survives the restart)", len(r) == 2
          and any("entries on account B today" in t or "locked out" in t for _, t in B2.bot.logs), B2.bot.logs[-1:])
    B3 = AB.AccountB(fake_bot(now=at("2026-10-22", 10, 0)), spec(), state_path=path)
    B3._load()
    check("6 next trading day: the lock is dropped (soft daily loss is per day), the ledger stays", B3.lock is None and len(B3.ledger) == 2)
    bot = live.LiveBot()
    bot.state_path = os.path.join(TMP, "live_restart.json")
    bot.cfg = {"adapter": "paper", "sym": "NQ", "tf": "5m"}
    bot.clock = lambda: NOW
    bot.started_at = NOW - 7200
    bot.ledger = [{"t": NOW - 5000, "side": "buy", "qty": 3, "entry_t": NOW - 5000, "src": "ema_lon_vix", "sym": "NQ"},
                  {"t": NOW - 4000, "side": "exit", "qty": 3, "entry_t": NOW - 5000, "src": "ema_lon_vix", "pnl": -80.0, "sym": "NQ"}]
    bot._save_state()
    b2 = live.LiveBot()
    b2.state_path = bot.state_path
    b2.cfg = dict(bot.cfg)
    b2.clock = lambda: NOW + 60
    b2.started_at = NOW + 60
    b2._restore()
    check("6 restart: LIT's account ledger (1 second-strategy entry today, -$80) comes back -> the 1-a-day second slot stays used",
          len(b2._second_rows_today("2026-10-21")) == 1 and b2.day_pnl_routed() == -80.0, (b2._restored, b2.day_pnl_routed()))


# ------------------------------------------------------------------------------------------------ 7
def part_boundaries():
    fns = (live.trading_day, AB.trading_day, MA.trading_day)
    cases = [(at("2026-10-21", 17, 59, 59), "2026-10-21"), (at("2026-10-21", 18, 0, 0), "2026-10-22"),
             (at("2026-10-25", 18, 0, 0), "2026-10-26"), (at("2026-10-23", 16, 30), "2026-10-23"),
             (at("2026-11-01", 18, 0), "2026-11-02"), (at("2026-10-31", 23, 0), "2026-11-01"),
             (at("2026-03-08", 18, 0), "2026-03-09"), (at("2026-11-02", 1, 0), "2026-11-02")]
    bad = [(t, want, [f(t) for f in fns]) for t, want in cases if any(f(t) != want for f in fns)]
    check("7 CME trading day starts 18:00 ET (17:59:59 -> today, 18:00 -> next, Sunday 18:00 -> Monday, DST weekends): "
          "live / account B / extra accounts agree", not bad, bad)
    check("7 eval sessions: 2026-10-19 -> 10-26 = session 6; 12-21 -> 12-28 = 5 (Christmas Friday has no session)",
          sz.eval_session("2026-10-19", "2026-10-26") == 6 and sz.eval_session("2026-12-21", "2026-12-28") == 5)
    wk = sz.eval_week_pnl({"2026-10-23": -700.0, "2026-10-22": -300.0, "2026-10-19": 50.0}, "2026-10-26", -100.0)
    check("7 eval week (wk_loss_usd): Monday 10-26 starts a new week (last week's -$950 not counted) -> -$100", wk == -100.0, wk)
    cal = {
        "Christmas Fri 12-25 10:00": G.calendar(at("2026-12-25", 10, 0), at("2026-12-25", 10, 0), 120, 955),
        "Sat 10:00": G.calendar(at("2026-10-24", 10, 0), at("2026-10-24", 10, 0), 120, 955),
        "17:30 daily break": G.calendar(at("2026-10-21", 17, 30), at("2026-10-21", 17, 30), 120, 955),
        "Nov 27 13:05 (13:15 early close)": G.calendar(at("2026-11-27", 13, 5), at("2026-11-27", 13, 5), 120, 955),
        "Dec 24 13:01": G.calendar(at("2026-12-24", 13, 1), at("2026-12-24", 13, 1), 120, 955),
    }
    ok_ = {"Nov 27 12:30": G.calendar(at("2026-11-27", 12, 30), at("2026-11-27", 12, 30), 120, 955),
           "Wed 10:00": G.calendar(NOW, NOW, 120, 955)}
    check("7 calendar guard blocks Christmas, the weekend, the 17:00-18:00 break, and entries within 15 min of the 13:15 "
          "early close; allows Nov 27 12:30 and a normal Wednesday", all(cal.values()) and not any(ok_.values()), (cal, ok_))
    B = AB.AccountB(fake_bot(), spec("builder25k"), state_path=os.path.join(TMP, "cap.json"))
    B50 = AB.AccountB(fake_bot(), spec("builder50k"), state_path=os.path.join(TMP, "cap50.json"))
    check("7 ATLAS adapter caps: 25K 20 micros, 50K 40 (NinjaTrader refuses more), never armed by the bot",
          B.adapter_cfg()["params"]["max_micros"] == 20 and B50.adapter_cfg()["params"]["max_micros"] == 40
          and B.adapter_cfg()["armed"] is False)
    shipped = json.load(open(second.CFG_PATH, encoding="utf-8"))
    note(f"7 second_model.json now: account_b {'OFF (null)' if shipped.get('account_b') is None else 'ON'}, routed on LIT's account: "
         f"{[k for k, v in shipped['strategies'].items() if (v or {}).get('route')] or 'none'}")


def main():
    part_opposite()
    part_order()
    part_simultaneous()
    part_duplicates()
    part_restart()
    part_boundaries()
    print(f"router determinism: {sum(RESULTS)}/{len(RESULTS)} passed, {len(NOTES)} notes")
    return all(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
