"""Account C = BLITZ, the scalper, on its OWN account (engine/account_c.py, owner 2026-10-28). OFF by default; temp folders only.

    python -X utf8 -m tests.test_account_c            # everything (~3-6 min: the 2026 replay + the LiveBot sessions)
    python -X utf8 -m tests.test_account_c --quick    # without the 2026 replay and the LiveBot sessions (~20 s)

  1. off = byte-identical bot: no block -> no account C (LiveBot, heartbeat, live board, narrator, hedge paths unchanged);
     engine/blitz.py's params dict at its default = today's rule (Engine and backtest, field for field).
  2. 2026 replay through account C on the paper adapter (minute polls 10:59-16:02 ET, the forming bar's open shown like
     NinjaTrader's feed): every BLITZ model trade = engine.blitz.backtest trade for trade (entry time, side, entry, stop, exit,
     kind); every routed trade books qty x the model's $ a micro, sized by the research's 25K eval rule (40% of the room,
     <= $600, <= 0.9 x the daily loss left); a new eval after each pass / fail / stuck (the owner buys one) -> the numbers.
  3. no hedging: C blocked while LIT holds / enters / has an armed setup the other way or ATLAS holds the other side; LIT
     (LiveBot._hedge_clear) or ATLAS (AccountB._c_yield) entering the other way closes C at market FIRST and waits for a
     CONFIRMED flat (an unconfirmed close holds them back, re-sent, never marked flat); same side never touched.
  4. a refused order (NinjaTrader NOT OK, nothing filled) is never booked: C flat, no close, one "order NOT placed" push.
  5. eval lifecycle: pass (push once, no new trade, the funded switch is the owner's), fail, stuck, the $600 soft daily loss,
     the funded switch (disarmed, new Name, the eval's state kept), the funded size (10% / $150 / +$400 day stop).
  6. the performance contract: 20+ trades under the research floor or 6 losing days in a row -> PAUSED (no entry, one push);
     the owner's --resume lifts it.
  7. the live gate: a real (non-Sim) account C is refused unless armed + the typed phrase + NINJATRADER_LIVE (never set here);
     a Sim account is not live-gated; the order files carry the acctc_ tag and C's own state file.
  8. trailing / time / 15:55 / early close: the trail is routed as a stop CHANGE (only tighter), the clock flattens at 15:55
     (+60 s) and 5 min before a CME early close; no entry in the last 15 min before an early close.
  9. LiveBot (engine/live.py) on 2026-10-13..15 with account C on (paper): LIT's routes identical to the backtest (and to the
     run without C); C routes BLITZ's model trades on its own ledger.
 10. switches: CLI / set_account_c / arm (only after the phrase) / resume / off; the Start page API (engine/go.py) slot.
 13. the first real day (2026-10-29): phone notices name BLITZ's own 25K (REAL) with NinjaTrader's fill, one per trade
     (keys :acctc; ATLAS's :acctb), BLITZ wording, the notices the owner must act on pushed; the go-live check
     (engine/blitz_preflight.py, CLI + GET route) line by line; 20 micros = MFFU 25K; the $600 lock; the floor lock at
     $25,100; the Nov 1 DST change and the session count.
 12. review 2026-10-29: no BLITZ entry against LIT's / ATLAS's bracket NinjaTrader has not confirmed flat; a model STOP exit's
     unconfirmed close keeps C "closing" (LIT waits); HEDGE BLOCKED names BLITZ's account; a LIT-account second strategy
     yields to C; LIT's / ATLAS's Name in another case refused; no switch off / to another Name while C holds a trade.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_c as AC  # noqa: E402
from engine import blitz as BZ  # noqa: E402

RES = []
T0 = time.time()


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:1400]}"), flush=True)


class FakeBot:
    def __init__(self, now=0, adapter="paper"):
        self._now = now
        self.state = {"price": None}
        self.ledger = []
        self._open_routed = None
        self.accts = None
        self.acct_b = None
        self.acct_c = None
        self.cfg = {"adapter": adapter, "sym": "NQ"}
        self.health = {}
        self.kill = False
        self.state_path = None
        self.logs = []
        self.pushed = []
        self._forming = {}
        self._hedge_wait = {}
        self._hedge_who = {}
        self._hedge_crit = {}

    def clock(self):
        return self._now

    def _log(self, kind, text, **kw):
        self.logs.append((kind, text))

    def _note_error(self, text):
        self.logs.append(("error", text))

    def _push_send(self, p):
        self.pushed.append(p)

    def _alert(self, *a, **k):
        return None

    def _hedge_clear_c(self, ent, sym, now):        # engine/live.LiveBot's own code on this fake bot
        from engine import live
        return live.LiveBot._hedge_clear_c(self, ent, sym, now)

    def _snote(self, key, kind, text):
        self.logs.append((kind, text))


class Paper:
    name = "paper"

    def __init__(self):
        self.sent = []

    def send(self, action):
        self.sent.append(dict(action))
        return {"ok": True, "adapter": "paper", "note": "simulated"}


class Stub:
    """Answers what the test sets; NinjaTrader-like capability flags and legs."""
    name = "stub"
    route_stop_moves = True
    route_all_exits = True
    reports_fills = False

    def __init__(self, entry_answer=None, exit_answer=None, legs=None):
        self.entry_answer = entry_answer or {"ok": True}
        self.exit_answer = exit_answer or {"ok": True}
        self.legs, self.history, self.sent = list(legs or []), [], []

    def send(self, action):
        self.sent.append(dict(action))
        s = action.get("side")
        if s in ("buy", "sell"):
            return dict(self.entry_answer)
        if s == "exit":
            return dict(self.exit_answer)
        return {"ok": True}

    def has_open_bracket(self, entry_t=None):
        return True

    def _instruments(self):
        return {"mini": "NQ 12-26", "micro": "MNQ 12-26"}

    def position_for(self, inst):
        return {"side": "FLAT", "qty": 0}


def spec(start="2026-01-02", name="Sim103", **kw):
    blk = {"account": name, "plan": "builder25k", "eval_start": start, **kw}
    return AC.normalize(blk)


def make(start="2026-01-02", adapter=None, now=0, **kw):
    bot = FakeBot(now)
    C = AC.AccountC(bot, spec(start, **kw), state_path="")
    C.adapter = adapter if adapter is not None else Paper()
    bot.acct_c = C
    return bot, C


def texts(bot):
    return [f"{p.get('title', '')} | {p.get('body', '')}" for p in bot.pushed]


def at_et(day, hh, mm, ss=0):
    return BZ.at_et(day, hh * 60 + mm) + ss


def sig_event(day, hh, mm, D=1, close=25000.0, stop=None):
    t = at_et(day, hh, mm) - 60                       # the signal bar opens a minute before its close hh:mm
    return {"ev": "signal", "t": t, "close_t": t + 60, "dir": D, "close": close, "band": close - D, "up": close - 1, "lo": close - 50,
            "sigma": 0.001, "o0": close, "atr5": 20.0, "taken": True, "why": None, "masked": False, "date": day,
            "stop": stop if stop is not None else close - D * 30.0}


# ================================================================================================ 1. off
def part1():
    check("1. no block -> raw_cfg None / normalize None / build None", AC.normalize(None) is None and AC.build(FakeBot(), None) is None)
    tmp = tempfile.mkdtemp(prefix="acctc_off_")
    try:
        check("1. no data/account_c.json in a fresh root = off", AC.raw_cfg(tmp) is None and AC.read_local(tmp) == (False, None))
        AC.write_local(None, tmp)
        check("1. account_c null = off", AC.raw_cfg(tmp) is None and AC.read_local(tmp)[0] is True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    from engine import live
    b = live.LiveBot()
    lb_tmp = tempfile.mkdtemp(prefix="acctc_lb_")
    b.state_path = os.path.join(lb_tmp, "live_state.json")
    b.cfg = {"adapter": "paper", "sym": "NQ"}
    b._sync_account_c()
    check("1. LiveBot without an account_c block (test harness / no file) -> acct_c None", b.acct_c is None)
    shutil.rmtree(lb_tmp, ignore_errors=True)               # (it used to stay in the temp folder)
    ent = {"entry_t": 1792000000, "dir": 1, "entry": 25000.0}
    check("1. LiveBot._hedge_clear with B and C off -> True at once (LIT never held back)", b._hedge_clear(ent, "NQ", 1792000003) is True
          and not b._hedge_wait)
    from engine import account_b as AB
    fb = FakeBot()
    B = AB.AccountB.__new__(AB.AccountB)
    B.bot = fb
    check("1. AccountB._c_yield with C off -> None (ATLAS unchanged)", B._c_yield(1, 1792000000, "NQ", 1792000003) is None)
    from engine import heartbeat as HB
    src = open(os.path.join(ROOT, "engine", "heartbeat.py"), encoding="utf-8").read()
    check("1. heartbeat: the account_c block is added only when account C is on", "account_c" in src and "_account_c(self.bot)" in src)
    hb = HB._account_c(FakeBot())
    check("1. heartbeat _account_c(bot without C) -> None (no key, no empty card)", hb is None)
    # the params dict at its default = today's rule
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    d = df[df["time"] >= df["time"].max() - 45 * 86400]
    a = BZ.backtest(d)
    b2 = BZ.backtest(d, params=dict(BZ.DEFAULT_PARAMS))
    check(f"1. blitz.backtest(params = DEFAULT_PARAMS) = backtest() ({len(a)} trades, field for field)", a == b2 and len(a) > 0)
    c = BZ.backtest(d, params={"hold": 20})
    check("1. a changed parameter changes the rule (hold 20: other exits)", c != a and all(r["bars"] <= 21 for r in c))
    E1, E2 = BZ.Engine(None), BZ.Engine(None, True, dict(BZ.DEFAULT_PARAMS))
    t, o, h, l, cl = BZ._bars_of(d)
    ev1, ev2 = [], []
    for i in range(len(t)):
        ev1 += E1.on_bar(int(t[i]), o[i], h[i], l[i], cl[i])
        ev2 += E2.on_bar(int(t[i]), o[i], h[i], l[i], cl[i])
    check(f"1. Engine(params=DEFAULT_PARAMS) = Engine() ({len(ev1)} events, same state)", ev1 == ev2 and E1.s == E2.s and E2.P is None)
    bad = []
    for over in ({"nope": 1}, {"hold": 0}, {"win": [500, 700]}, {"vm": "x"}):
        try:
            BZ.rule_params(over)
            bad.append(over)
        except ValueError:
            pass
    check("1. rule_params refuses unknown keys / values out of range", not bad, bad)
    s2 = spec(params={"hold": 25})
    check("1. account_c params plug in by config (only the changed keys kept); bad params = a problem",
          s2["params"] == {"hold": 25} and not s2["problem"] and spec(params={"hold": 0})["problem"])
    check("1. the default spec runs today's rule (params None, filtered)", spec()["params"] is None and spec()["filtered"] is True
          and spec(params=dict(BZ.DEFAULT_PARAMS))["params"] is None)
    pick = os.path.join(ROOT, "research", "scalp", "blitz_25k_pick.json")
    srcc = open(os.path.join(ROOT, "engine", "account_c.py"), encoding="utf-8").read()
    check("1. account C never reads research/scalp/blitz_25k_pick.json (a pick is adopted by config only)",
          "open(" not in srcc.split("blitz_25k_pick")[0][-200:] if "blitz_25k_pick" in srcc else True, os.path.exists(pick))


# ================================================================================================ 2. 2026 replay
def part2():
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv")).sort_values("time").reset_index(drop=True)
    ref = BZ.backtest(df)
    o1 = dict(zip(df["time"].astype("int64"), df["open"].astype(float)))
    tt = df["time"].to_numpy()
    days = sorted({BZ.et_date(int(x)) for x in tt[::60]})
    days = [d for d in days if pd.Timestamp(d).weekday() < 5 and d >= "2026-01-02"]
    bot, C = make("2026-01-02")
    bot.cfg["acct_c_history"] = False
    evals = []
    import numpy as np
    t_start = time.time()
    for d in days:
        lo = int(np.searchsorted(tt, at_et(d, 0, 0) - 86400))
        hi = int(np.searchsorted(tt, at_et(d, 17, 0)))
        d1 = df.iloc[0 if C.eng is None else lo:hi]
        times = [at_et(d, 9, 0, 2)] + [at_et(d, 10, 59, 2) + 60 * k for k in range(0, 304)]
        for now in times:
            bot._now = now
            tb = now - now % 60
            if tb in o1:
                bot._forming = {("NQ", 60): (tb, o1[tb])}
                bot.state["price"] = o1[tb]
            C.tick(d1, "NQ", now)
        ev = C.eval_view(at_et(d, 16, 30))
        if ev.get("status") in AC.STOP_STATUSES:
            evals.append({"start": C.spec["eval_start"], "end": d, "status": ev["status"], "profit": ev.get("profit"), "session": ev.get("session")})
            nxt = next((x for x in days if x > d), None)
            if nxt:                                   # the owner buys a new eval (research back-to-back path)
                C.spec = AC.normalize({"account": "Sim103", "plan": "builder25k", "eval_start": nxt})
                C.lock = None
    took = time.time() - t_start
    rows = [r for r in C.rows if r.get("model_entry_t") is not None]
    same = len(rows) == len(ref)
    diffs = []
    for a, b in zip(rows, ref):        # prices within 0.001 pt (the live 5m ATR is summed bar by bar: ~1e-8 of float noise)
        if (int(a["model_entry_t"]), int(a["dir"]), a["exit_kind"]) != (int(b["entry_t"]), int(b["dir"]), b["exit_kind"]) \
                or abs(float(a["entry"]) - float(b["entry"])) > 1e-3 or abs(float(a["exit"]) - float(b["exit"])) > 1e-3:
            diffs.append((a.get("model_entry_t"), a.get("exit_kind"), a.get("exit"), b["entry_t"], b["exit_kind"], b["exit"]))
    check(f"2. 2026 replay through account C ({len(rows)} BLITZ model trades, {took:.0f} s of minute polls) = engine.blitz.backtest "
          f"trade for trade ({len(ref)}): entry time, side, entry, exit, kind", same and not diffs, (len(rows), len(ref), diffs[:5]))
    stop_ok = all(abs(float(a["stop"]) - (BZ._tick_like(b["stop"], b["dir"]) if hasattr(BZ, "_tick_like") else float(b["stop"]))) < 0.26
                  for a, b in zip(rows, ref))
    check("2. ... every stop = the model's stop (the routed one on the tick)", stop_ok)
    routed = [r for r in rows if r.get("routed")]
    closes = {int(c[3]): c for c in C.closes}
    bad_usd = []
    for r in routed:
        b = next(x for x in ref if int(x["entry_t"]) == int(r["model_entry_t"]))
        c = closes.get(int(r["entry_t"]))
        if c is None or abs(float(c[2]) - round(int(r["qty"]) * float(b["pnl_pm"]), 2)) > 0.011:
            bad_usd.append((r["entry_t"], r.get("qty"), c and c[2], round(int(r["qty"]) * float(b["pnl_pm"]), 2)))
    check(f"2. ... {len(routed)} routed trades book qty x the model's $ a micro (costs in: $1.90 + 1 tick a fill)", routed and not bad_usd,
          bad_usd[:5])
    blocked = [r for r in rows if not r.get("routed")]
    whys = {}
    for r in blocked:
        w = str(r.get("skip") or "?").split("(")[0].split(":")[0][:40]
        whys[w] = whys.get(w, 0) + 1
    check("2. ... every model trade not routed has its reason (eval ended / size / daily loss ...)", all(r.get("skip") for r in blocked), whys)
    print("   not routed:", json.dumps(dict(sorted(whys.items(), key=lambda x: -x[1]))), "| paused:", C.paused)
    check("2. ... no 2026 trade refused by a guard (BLITZ's wide ATR stops pass its own 250-pt sanity cap, not LIT's 100)",
          not any(k.startswith("GUARD") for k in whys), whys)
    check("2. ... the performance contract never paused BLITZ on 2026 (it is the research year)", C.paused is None, C.paused)
    # the size rule = the research's (engine/blitz.qty) on the same room / day P&L
    sz_bad = []
    for room, cum, rk in ((1000.0, 0.0, 60.0), (600.0, -200.0, 45.0), (300.0, 0.0, 70.0), (1800.0, 100.0, 15.0), (100.0, 0.0, 80.0)):
        rpm = (rk + BZ.TICK) * BZ.PV + BZ.COMM
        a = AC.qty(spec(), rk, {"room": room, "cum": cum})["qty"]
        b = BZ.qty(rpm, room, cum)
        if a != b:
            sz_bad.append((room, cum, rk, a, b))
    check("2. ... account C's size = engine/blitz.qty (40% of the room, <= $600, <= 0.9 x the daily loss left, 20 micros)", not sz_bad, sz_bad)
    s4 = AC.qty(spec(), 60.0, {"room": 1000.0, "cum": 0.0, "session": 4})["qty"]
    s5 = AC.qty(spec(), 60.0, {"room": 1000.0, "cum": 0.0, "session": 5})
    sp = AC.qty(spec(sizing="paper"), 60.0, {"room": 1000.0, "cum": 0.0, "session": 5})["qty"]
    s5b = AC.qty(spec(), 60.0, {"room": 300.0, "cum": -100.0, "session": 9})["qty"]
    check("2. ... the 25K speed size (research/scalp/blitz_25k_pick.json eval_25k): session 4 40% of $1,000 -> 3; session 5 the full "
          "room, <= $600 and 0.9 x $600 = $540 -> 4; sizing 'paper' stays 40% -> 3; $300 room, -$100 today: 0.9 x $500 caps -> 2",
          (s4, s5["qty"], sp, s5b) == (3, 4, 3, 2) and "from session 5" in s5["reasons"][0], (s4, s5, sp, s5b))
    # numbers
    H = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31")}
    lines = []
    for nm, (a, z) in H.items():
        cs = [c for c in C.closes if a <= c[0] <= z]
        usd = sum(float(c[2]) for c in cs)
        gw = sum(float(c[2]) for c in cs if c[2] > 0)
        gl = -sum(float(c[2]) for c in cs if c[2] < 0)
        ev = [e for e in evals if a <= e["end"] <= z]
        months = (min(pd.Timestamp(z), pd.Timestamp("2026-10-16")) - pd.Timestamp(a)).days / 30.4
        fees = AC.PLANS["builder25k"]["price"] * (len(ev) + (1 if nm == "H2" else 0))
        lines.append(f"| 2026 {nm} | {len(cs)} | {len([r for r in rows if a <= r['day'] <= z])} | ${usd:+,.0f} | {gw / gl if gl else 0:.2f} | "
                     f"{sum(1 for e in ev if e['status'] == 'passed')}/{sum(1 for e in ev if e['status'] == 'failed')}/"
                     f"{sum(1 for e in ev if e['status'] == 'stuck')} | ${(usd - fees) / months:+,.0f} |")
    print("\nAccount C 2026 replay (paper adapter, the live loop; costs in; a new $63 eval after each pass / fail / stuck):")
    print("| Span | Routed trades | BLITZ model trades | Net $ on the evals | PF ($) | Evals pass / fail / stuck | $ a month after fees |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    print("\n".join(lines))
    print("evals:", json.dumps(evals))
    check("2. ... evals ended by pass / fail / stuck (the owner's new eval each time)", len(evals) >= 2, evals)


# ================================================================================================ 3. no hedging
def _open_long(C, bot, day="2026-11-03", hh=11, mm=0, close=25000.0):
    ev = sig_event(day, hh, mm, 1, close)
    tb = ev["t"] + 60
    bot._now = tb + 2
    bot._forming = {("NQ", 60): (tb, close)}
    C._enter(ev, "NQ", bot._now)
    return tb


def part3():
    # blocked by LIT's armed short setup / LIT short position / LIT entering short / account B short
    for what, setter, word in (
            ("LIT's SHORT setup armed (limit)", lambda b: b.state.update(setups={"short": {"arm_t": 1}}), "LIT has a SHORT setup armed"),
            ("LIT waiting for its 1m CISD SHORT", lambda b: b.state.update(setups={"short": {"arm_t": 1, "tapped_t": 2}}), "waiting for its 1m CISD"),
            ("LIT in a SHORT trade", lambda b: b.state.update(position={"dir": -1, "entry_t": 1}), "LIT is in a SHORT trade"),
            ("LIT entering SHORT", lambda b: b.state.update(enter_now={"dir": -1, "entry_t": 1}), "LIT is entering SHORT")):
        bot, C = make("2026-11-02")
        setter(bot)
        tb = _open_long(C, bot)
        r = C._row(et_=tb)
        check(f"3. BLITZ LONG blocked while {what}", C.open_t is None and not C.adapter.sent and word in str(r.get("skip")), r)

    class B:
        def __init__(self, d):
            self.open_t = 5
            self.prov = {5: {"dir": d}}

        def closing_open(self):
            return []
    bot, C = make("2026-11-02")
    bot.acct_b = B(-1)
    tb = _open_long(C, bot)
    check("3. BLITZ LONG blocked while ATLAS (account B) holds a SHORT", C.open_t is None and "ATLAS" in str(C._row(et_=tb).get("skip")))
    bot, C = make("2026-11-02")
    bot.acct_b = B(1)
    bot.state.update(setups={"long": {"arm_t": 1}})
    tb = _open_long(C, bot)
    check("3. same side as LIT / ATLAS is allowed (LONG next to LIT's LONG setup and ATLAS's LONG)", C.open_t == tb and C.adapter.sent)
    # LIT enters SHORT while C is LONG: C closed FIRST (paper: confirmed at once), LIT routes
    from engine import live
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot)
    ent = {"entry_t": tb + 600, "dir": -1, "entry": 25010.0}
    bot._now = tb + 603
    ok = live.LiveBot._hedge_clear(bot, ent, "NQ", bot._now)
    ex = [a for a in C.adapter.sent if a.get("side") == "exit"]
    check("3. LIT entering SHORT while BLITZ is LONG: BLITZ closed at market FIRST (HEDGE), then LIT routes", ok is True and C.open_t is None
          and ex and ex[-1]["reason"] == "HEDGE" and any(int(c[3]) == tb for c in C.closes))
    # the same with a close NinjaTrader does not confirm: LIT held back, C NOT flat, re-sent
    bot, C = make("2026-11-02", adapter=Stub(exit_answer={"ok": False, "error": "flat not confirmed yet"}))
    tb = _open_long(C, bot)
    C.adapter.legs = [{"entry_t": tb, "status": "closing"}]       # NinjaTrader's book: the bracket still open / closing
    ent = {"entry_t": tb + 600, "dir": -1, "entry": 25010.0}
    bot._now = tb + 603
    ok = live.LiveBot._hedge_clear(bot, ent, "NQ", bot._now)
    check("3. ... an UNCONFIRMED close: LIT NOT routed (waits), BLITZ still open (never marked flat), HEDGE WAIT logged",
          ok is False and C.open_t == tb and bot._hedge_who.get(tb + 600) == "BLITZ" and C.closing_open()
          and any("HEDGE WAIT" in t for _, t in bot.logs))
    n0 = len([a for a in C.adapter.sent if a.get("side") == "exit"])
    bot._now += 12
    ok2 = live.LiveBot._hedge_clear(bot, ent, "NQ", bot._now)
    n1 = len([a for a in C.adapter.sent if a.get("side") == "exit"])
    check("3. ... 12 s later still not flat: the close is RE-SENT, LIT still waits, C still open", ok2 is False and n1 == n0 + 1 and C.open_t == tb)
    C.adapter.exit_answer = {"ok": True}
    C.adapter.legs = []                                            # NinjaTrader shows the account flat
    bot._now += 12
    ok3 = live.LiveBot._hedge_clear(bot, ent, "NQ", bot._now)
    check("3. ... once NinjaTrader shows it flat: confirmed, booked, LIT routes on that poll", ok3 is True and C.open_t is None
          and any(int(c[3]) == tb for c in C.closes))
    bot._hedge_wait = {tb + 900: tb}
    bot._hedge_who = {tb + 900: "BLITZ"}
    live.LiveBot._hedge_blocked(bot, tb + 900, bot._now)
    check("3. ... an entry deadline passed while waiting: critical 'HEDGE BLOCKED: BLITZ close not confirmed'",
          any("HEDGE BLOCKED: BLITZ" in t for t in texts(bot)))
    # LIT entering the SAME side: nothing touched
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot)
    ok = live.LiveBot._hedge_clear(bot, {"entry_t": tb + 600, "dir": 1, "entry": 25010.0}, "NQ", tb + 603)
    check("3. LIT entering the SAME side: BLITZ untouched", ok is True and C.open_t == tb and not [a for a in C.adapter.sent if a["side"] == "exit"])
    # ATLAS (account B) entering SHORT while C is LONG: AccountB._c_yield closes C first
    from engine import account_b as AB
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot)
    Bx = AB.AccountB.__new__(AB.AccountB)
    Bx.bot = bot
    Bx.label = "ATLAS Sim102"
    Bx.log = lambda k, t: bot.logs.append((k, t))
    why = Bx._c_yield(-1, tb + 900, "NQ", tb + 902, 25005.0)
    check("3. ATLAS entering SHORT while BLITZ is LONG: BLITZ closed FIRST, ATLAS may route", why is None and C.open_t is None
          and [a for a in C.adapter.sent if a.get("side") == "exit"][-1]["reason"] == "HEDGE")
    bot, C = make("2026-11-02", adapter=Stub(exit_answer={"ok": False, "error": "no flat confirmation"}))
    tb = _open_long(C, bot)
    Bx.bot = bot
    why = Bx._c_yield(-1, tb + 900, "NQ", tb + 902, 25005.0)
    check("3. ... BLITZ's close not confirmed: ATLAS's entry NOT routed", why and "not confirmed" in why and C.open_t == tb)
    # the real AccountB.entry path calls _c_yield right before it routes
    src = open(os.path.join(ROOT, "engine", "account_b.py"), encoding="utf-8").read()
    i = src.find("k, t, nm, d, head, risk, sz, act = chosen")
    check("3. AccountB.entry asks account C to yield right before routing (after its own blocks / size / guards)",
          i > 0 and "self._c_yield(d, tb, sym, now" in src[i:i + 300])


def part3b():
    """The no-hedging mask on a real day (2026-10-15, 6 BLITZ longs in the research): with LIT's SHORT setup armed all day,
    every long candidate is masked at the signal (no model trade, no order); without it the day is the backtest's."""
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    day = "2026-10-15"
    df = df[(df["time"] >= at_et(day, 0, 0) - 45 * 86400) & (df["time"] < at_et(day, 17, 0))].reset_index(drop=True)
    ref = [t for t in BZ.backtest(df) if t["day"] == day]
    o1 = dict(zip(df["time"].astype("int64"), df["open"].astype(float)))
    out = {}
    for armed in (True, False):
        bot, C = make("2026-10-01")
        if armed:
            bot.state["setups"] = {"short": {"arm_t": at_et(day, 10, 0)}}
        for k, now in enumerate([at_et(day, 10, 58, 2)] + [at_et(day, 10, 59, 2) + 60 * i for i in range(0, 304)]):
            bot._now = now
            tb = now - now % 60
            if tb in o1:
                bot._forming = {("NQ", 60): (tb, o1[tb])}
                bot.state["price"] = o1[tb]
            C.tick(df[df["time"] < now - 59], "NQ", now)
        out[armed] = C
    Ca, Cb = out[True], out[False]
    ma = [r for r in Ca.rows if r.get("masked") and r["day"] == day]
    ta = [r for r in Ca.rows if r.get("model_entry_t") and r["day"] == day]
    tb_ = [r for r in Cb.rows if r.get("model_entry_t") and r["day"] == day]
    check(f"3b. {day} with LIT's SHORT setup armed all day: every BLITZ long candidate masked at the signal ({len(ma)}), no model "
          "trade, nothing routed", ma and not ta and not [a for a in Ca.adapter.sent if a.get("side") in ("buy", "sell")]
          and all("no hedging" in str(r.get("skip")) for r in ma), (len(ma), len(ta)))
    same = [(int(r["model_entry_t"]), r["exit_kind"]) for r in tb_] == [(int(t["entry_t"]), t["exit_kind"]) for t in ref]
    check(f"3b. ... the same day without it: account C's {len(tb_)} trades = the backtest's {len(ref)} (the mask frees the slot only when used)",
          same and len(ref) >= 3, ([(r.get("model_entry_t"), r.get("exit_kind")) for r in tb_], [(t["entry_t"], t["exit_kind"]) for t in ref]))


# ================================================================================================ 4. refused order
def part4():
    from engine import ninjatrader as N  # noqa: F401
    err = "REFUSED: NinjaTrader reports every connection DISCONNECTED (C:\\Users\\x\\Documents\\NinjaTrader 8\\y.txt)"
    bot, C = make("2026-11-02", adapter=Stub(entry_answer={"ok": False, "error": err}))
    tb = _open_long(C, bot)
    pv = C.prov.get(tb) or {}
    check("4. refused entry: C flat at once, marked not placed + final", C.open_t is None and pv.get("final") and (pv.get("not_placed") or {}).get("error"))
    check("4. ... the reason without the file path", "<path>" in pv["not_placed"]["error"] and "Users" not in pv["not_placed"]["error"])
    check("4. ... one 'order NOT placed' push, no entry push", sum("order NOT placed" in t for t in texts(bot)) == 1
          and not any(p.get("kind") == "fill" for p in bot.pushed))
    check("4. ... does not count as an entry today", C.entries_today("2026-11-03") == 0)
    # the model's exit later books nothing
    C.prov[tb]["model_entry_t"] = tb
    C._on_exit({"entry_t": tb, "exit_t": tb + 1860, "exit": 25040.0, "kind": "time", "pts": 40.0, "risk": 30.0, "r": 1.2, "pnl_pm": 78.1,
                "bars": 31}, "NQ", tb + 1862)
    check("4. ... its model exit later books $0 (no close on the eval)", not C.closes and C.eval_view(tb + 1900)["profit"] == 0)
    # a NOT OK answer with a leg still working: kept, one "NOT confirmed" push
    leg = {"entry_t": 0, "status": "pending", "filled": 0}
    bot, C = make("2026-11-02", adapter=Stub(entry_answer={"ok": False, "error": "fill not reported yet",
                                                         "legs": [{"instrument": "MNQ 12-26", "qty": 2, "ok": False, "state": "WORKING"}]}))
    ev = sig_event("2026-11-03", 11, 0, 1, 25000.0)
    tb = ev["t"] + 60
    leg["entry_t"] = tb
    C.adapter.legs = [leg]
    bot._now = tb + 2
    C._enter(ev, "NQ", bot._now)
    check("4. NOT OK with a leg still working: C KEEPS the position (it may exist), one 'NOT confirmed' push",
          C.open_t == tb and sum("NOT confirmed" in t for t in texts(bot)) == 1)


# ================================================================================================ 5. eval lifecycle
def part5():
    bot, C = make("2026-11-02")
    day = "2026-11-03"
    C.closes = [[day, at_et(day, 11, 31), 900.0, at_et(day, 11, 0), 1.0], [day, at_et(day, 12, 31), 650.0, at_et(day, 12, 0), 1.0]]
    bot._now = at_et(day, 12, 40)
    C._lifecycle(bot._now)
    C._lifecycle(bot._now + 60)
    ev = C.eval_view(bot._now)
    check("5. +$1,550 on the 25K: eval PASSED, one push naming the funded switch (never automatic)",
          ev["status"] == "passed" and sum("EVAL PASSED" in t for t in texts(bot)) == 1 and any("Passed → funded" in t for t in texts(bot)))
    tb = _open_long(C, bot, day, 13, 0)
    check("5. ... no new trade after the pass", C.open_t is None and "eval passed" in str(C._row(et_=tb).get("skip")))
    bot, C = make("2026-11-02")
    C.closes = [["2026-11-02", at_et("2026-11-02", 11, 31), -560.0, 1, -1.0], ["2026-11-03", at_et(day, 11, 31), -460.0, 2, -1.0]]
    bot._now = at_et(day, 12, 0)
    C._lifecycle(bot._now)
    check("5. -$1,020: eval FAILED (room <= 0), one push", C.eval_view(bot._now)["status"] == "failed" and sum("EVAL FAILED" in t for t in texts(bot)) == 1)
    bot, C = make("2026-11-02")
    C.closes = [["2026-11-02", at_et("2026-11-02", 11, 31), -780.0, 1, -1.0]]
    bot._now = at_et(day, 12, 0)
    C._lifecycle(bot._now)
    check("5. room $220 (< $249.56 = 2 x BLITZ's median stop-out): STUCK, push 'buy a new one'",
          C.eval_view(bot._now)["status"] == "stuck" and any("stuck" in t for t in texts(bot)))
    bot, C = make("2026-11-02")
    bot._now = at_et(day, 11, 40)
    C._close(at_et(day, 11, 0), at_et(day, 11, 31), -610.0, bot._now, r=-1.0)
    tb = _open_long(C, bot, day, 12, 0)
    check("5. -$610 today: the $600 soft daily loss locks C for the day (push), the next signal is not routed",
          C.lock and C.open_t is None and "locked out today" in str(C._row(et_=tb).get("skip")) and any("locked out" in t for t in texts(bot)))
    tb2 = _open_long(C, bot, "2026-11-04", 11, 0)
    check("5. ... the next day trades again", C.open_t == tb2)
    # the funded switch (temp root)
    tmp = tempfile.mkdtemp(prefix="acctc_fund_")
    try:
        ok = lambda: (True, "ok")
        r = AC.set_account_c("MFFUEVBLDRTEST1", start="2026-11-02", root=tmp, selftest=ok, lit_account="L", b_account="B")
        check("5. set_account_c on a real-looking Name: written, NOT armed", r["ok"] and AC.raw_cfg(tmp)["armed"] is False and r["sim"] is False)
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        with open(AC.state_file(tmp), "w", encoding="utf-8") as fh:
            json.dump({"account": "MFFUEVBLDRTEST1", "closes": [["2026-11-03", 1, 1600.0, 1, 2.0]]}, fh)
        r2 = AC.to_funded("MFFUEVBLDRTEST1", "2026-11-10", root=tmp, selftest=ok, allow=False, lit_account="L", b_account="B")
        check("5. the funded switch refuses the eval's own Name (MFFU gives a new one)", not r2["ok"] and "own new Name" in r2["error"])
        r3 = AC.to_funded("MFFUFNDTEST9", "2026-11-10", root=tmp, selftest=ok, allow=False, lit_account="L", b_account="B")
        blk = AC.raw_cfg(tmp)
        check("5. Passed -> funded: stage funded on the NEW Name, DISARMED, the eval kept as eval_account + its state file archived",
              r3["ok"] and blk["stage"] == "funded" and blk["account"] == "MFFUFNDTEST9" and blk["armed"] is False
              and blk["eval_account"] == "MFFUEVBLDRTEST1" and r3["archived"] and os.path.exists(r3["archived"]))
        fs = AC.normalize(blk)
        check("5. funded spec: no problem, funded size rule 10% / $150 / +$400 day stop", not fs["problem"] and AC.size_rule(fs)["f"] == 0.1)
        q1 = AC.qty(fs, 40.0, {"room": 1000.0, "cum": 0.0})["qty"]
        q2 = AC.qty(fs, 40.0, {"room": 1000.0, "cum": 420.0})
        check("5. ... funded micros: min(10% of $1,000, $150) / $83.40 = 1; after +$420 today: 0 (day profit stop)",
              q1 == 1 and q2["qty"] == 0 and "day profit stop" in q2["reasons"][0], (q1, q2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ 6. performance contract
def part6():
    B = AC.bands()
    check("6. research floor bands from the 330 trades of 2026 (bootstrap p5): 20 trades avg R < 0 < p50, PF p5 < 1",
          B[20]["avg_r_p5"] < 0 < B[20]["avg_r_p50"] and B[20]["pf_p5"] < 1.0 < B[20]["pf_p50"], B[20])
    good = [{"day": f"2026-11-{3 + i // 4:02d}", "r": (0.6 if i % 2 else -0.3), "usd": (60 if i % 2 else -30)} for i in range(24)]
    s = AC.score(good)
    check("6. 24 trades at +0.15R avg: scorecard ok", s["status"] == "ok" and s["n"] == 24, s)
    check("6. under 20 trades: warming (never paused)", AC.score(good[:19])["status"] == "warming")
    bad = [{"day": f"2026-11-{3 + i // 5:02d}", "r": (0.3 if i % 3 == 0 else -0.6), "usd": (30 if i % 3 == 0 else -60)} for i in range(21)]
    s2 = AC.score(bad)
    check("6. 21 trades at -0.30R avg: under the floor -> below", s2["status"] == "below" and s2["why"], s2)
    s3 = AC.score(bad, model=good)
    check("6. the R floor is judged on BLITZ's model trades when given (the floor's own population); $ stay the routed trades'",
          s3["status"] == "ok" and s3["n"] == 24 and s3["avg_r"] == 0.15 and s3["usd"] == sum(t["usd"] for t in bad), s3)
    check("6. ... and a weak model sample still pauses even if the routed trades look fine",
          AC.score(good, model=bad)["status"] == "below")
    streak = [{"day": f"2026-11-{3 + i:02d}", "r": -0.5, "usd": -50} for i in range(6)]
    check("6. 6 losing days in a row -> below (even under 20 trades)", AC.score(streak)["status"] == "below")
    bot, C = make("2026-11-02")
    for i, t in enumerate(bad):
        C.closes.append([t["day"], 1800000000 + i * 60, float(t["usd"]), 1800000000 + i, float(t["r"])])
    bot._now = at_et("2026-11-09", 12, 0)
    C._score_check(bot._now)
    check("6. account C PAUSED by the contract: one push naming the resume command", C.paused and sum("PAUSED" in t for t in texts(bot)) == 1
          and any("--resume" in t for t in texts(bot)))
    tb = _open_long(C, bot, "2026-11-10", 11, 0)
    check("6. ... no new entry while paused", C.open_t is None and "PAUSED" in str(C._row(et_=tb).get("skip")))
    C.spec["resume_after"] = bot._now + 10
    C._resume_check(bot._now + 20)
    tb2 = _open_long(C, bot, "2026-11-10", 11, 30)
    check("6. the owner's --resume lifts it at the next poll; entries again", C.paused is None and C.open_t == tb2)
    tmp = tempfile.mkdtemp(prefix="acctc_res_")
    try:
        AC.write_local({"account": "Sim103", "plan": "builder25k", "eval_start": "2026-11-02"}, tmp)
        r = AC.resume(tmp)
        check("6. resume(): writes resume_after into the local block only", r["ok"] and AC.raw_cfg(tmp).get("resume_after"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ 7. live gate
def part7():
    from engine import ninjatrader as N
    tmp = tempfile.mkdtemp(prefix="acctc_gate_")
    os.environ.pop(N.LIVE_ENV, None)
    try:
        for sub in ("incoming", "outgoing"):
            os.makedirs(os.path.join(tmp, "nt", sub), exist_ok=True)

        def adapter_for(name, armed, confirm=""):
            bot = FakeBot(adapter="ninjatrader")
            bot.cfg = {"adapter": "ninjatrader", "sym": "NQ", "nt_folder": os.path.join(tmp, "nt"), "confirm": confirm, "armed": True,
                       "nt_account": "LITACCOUNT", "params": {"max_micros": 40}, "nt_allow_path": os.path.join(tmp, "allow.json")}
            C = AC.AccountC(bot, AC.normalize({"account": name, "plan": "builder25k", "eval_start": "2026-11-02", "armed": armed}),
                            state_path=os.path.join(tmp, "live_state_acctc.json"))
            cfg = C.adapter_cfg()
            return C, cfg, N.NinjaTraderAdapter(cfg, readonly=True)
        C, cfg, ad = adapter_for("MFFUEVBLDRTEST1", False)
        check("7. real account, not armed -> refused (the bot's own arming is never inherited)", ad.disabled and "not armed" in ad.disabled, ad.disabled)
        check("7. ... C's own Name, tag acctc_, own NinjaTrader state file, 20 micros",
              cfg["nt_account"] == "MFFUEVBLDRTEST1" and cfg["nt_file_tag"] == "acctc_" and cfg["nt_state_path"].endswith("ninjatrader_state_acctc.json")
              and cfg["params"]["max_micros"] == 20 and cfg["confirm"] == "")
        C, cfg, ad = adapter_for("MFFUEVBLDRTEST1", True)
        check("7. armed but no typed phrase -> refused", ad.disabled and "confirm phrase" in ad.disabled, ad.disabled)
        C, cfg, ad = adapter_for("MFFUEVBLDRTEST1", True, N.LIVE_PHRASE)
        check(f"7. armed + phrase but {N.LIVE_ENV} not set -> refused (never set by the bot or this test)", ad.disabled and N.LIVE_ENV in ad.disabled, ad.disabled)
        C, cfg, ad = adapter_for("Sim103", False)
        check("7. a Sim account is not live-gated (Sim only until the owner arms)", N.NinjaTraderAdapter._live_gate(ad) is None)
        s = AC.normalize({"account": "LITACCOUNT", "plan": "builder25k"}, lit_account="LITACCOUNT")
        check("7. LIT's own account refused as account C", s["problem"] and "Zlarior" in s["problem"])
        s = AC.normalize({"account": "ATL", "plan": "builder25k"}, b_account="ATL")
        check("7. ATLAS's account refused as account C", s["problem"] and "ATLAS" in s["problem"])
        s = AC.normalize({"account": "X", "plan": "builder50k"})
        check("7. a 50K plan refused (one funded 50K per person = LIT's)", s["problem"] and "builder25k" in s["problem"])
        srcs = "".join(open(os.path.join(ROOT, "engine", f), encoding="utf-8").read() for f in ("account_c.py",))
        check("7. engine/account_c.py never sets the live switch / arming by itself", "environ[" not in srcs and "NINJATRADER_LIVE\"] =" not in srcs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ 8. management
def part8():
    bot, C = make("2026-11-02", adapter=Stub())
    tb = _open_long(C, bot)
    C.prov[tb]["model_entry_t"] = tb
    C.prov[tb]["fill_model"] = 25000.25
    C.eng = {"pos": {"entry_t": tb, "stp": 24985.13, "dir": 1}}
    C._trail("NQ")
    mods = [a for a in C.adapter.sent if a.get("side") == "modify"]
    check("8. the model's trailed stop -> a stop CHANGE on the tick (24,985.25)", mods and abs(mods[-1]["stop"] - 24985.25) < 1e-9, mods)
    C.eng = {"pos": {"entry_t": tb, "stp": 24980.0, "dir": 1}}
    C._trail("NQ")
    check("8. ... never looser", len([a for a in C.adapter.sent if a.get("side") == "modify"]) == len(mods))
    # the 15:55 clock flatten (+60 s grace) and the early close
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot, "2026-11-03", 15, 30)
    C._clock_flat("NQ", at_et("2026-11-03", 15, 55, 30))
    check("8. 15:55:30 with the model still open: no clock flatten yet (the 15:54 bar may be late)", C.open_t == tb)
    bot.state["price"] = 25003.0
    C._clock_flat("NQ", at_et("2026-11-03", 15, 56, 2))
    check("8. 15:56:02: the clock flattens C (TIME)", C.open_t is None and C.adapter.sent[-1]["reason"] == "TIME")
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot, "2026-11-27", 12, 30)           # the day after Thanksgiving: CME halts 13:15 ET
    check("8. day after Thanksgiving (13:15 close): a 12:30 entry is allowed", C.open_t == tb)
    C._clock_flat("NQ", at_et("2026-11-27", 13, 10, 2))
    check("8. ... flattened at 13:10 (5 min before the early close)", C.open_t is None)
    tb = _open_long(C, bot, "2026-11-27", 13, 0)
    check("8. ... no entry in the last 15 min before it (13:00 open)", C.open_t is None and "early close" in str(C._row(et_=tb).get("skip")))
    # late signal (a restart / catch-up) is not chased
    bot, C = make("2026-11-02")
    ev = sig_event("2026-11-03", 11, 0)
    C._enter(ev, "NQ", ev["t"] + 60 + 120)
    check("8. a signal seen 120 s after its entry bar opened is not chased", C.open_t is None and "not chasing" in str(C.rows[-1].get("skip")))
    # the model exit books qty x pnl_pm and routes the exit
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot)
    C._events([{"ev": "entry", "entry_t": tb, "sig_t": tb - 60, "dir": 1, "entry": 25000.25, "stop": 24970.0, "risk": 30.25}], "NQ", tb + 62)
    C._events([{"ev": "exit", "entry_t": tb, "exit_t": tb + 1860, "exit": 25030.0, "kind": "time", "pts": 29.75, "risk": 30.25,
                "r": 0.9, "pnl_pm": 29.75 * 2 - 1.9, "bars": 31, "mae": 3.0}], "NQ", tb + 1862)
    q = C.prov[tb]["qty"]
    check(f"8. the model's time exit: routed exit TIME, {q} x $57.60 booked", C.open_t is None and C.closes and abs(C.closes[-1][2] - round(q * 57.6, 2)) < 0.01
          and C.adapter.sent[-1]["reason"] == "TIME")
    inf = C.info(tb + 1900)
    check("8. info(): label BLITZ <name>, kind PAPER, eval, scorecard, today's rows", inf["label"] == "BLITZ Sim103" and inf["kind"] == "PAPER"
          and "scorecard" in inf and inf["trades_today"] and inf["eval"]["status"] == "open")


# ================================================================================================ 9. LiveBot sessions
def part9():
    from tests import test_lit_live as TL
    from tools import lit_final as F
    import collections
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    sessions = ("2026-10-13", "2026-10-14", "2026-10-15")
    by_day = collections.defaultdict(list)
    for t in F.run(P):
        if t["day"] in sessions:
            by_day[t["day"]].append(t)
    holder = {}

    lat = []
    real_route = AC.AccountC.route

    def timed_route(self, action):                   # wall time from the poll's start to account C's entry order
        if action.get("side") in ("buy", "sell"):
            lat.append(time.perf_counter() - getattr(self.bot, "_t0_wall", time.perf_counter()))
        return real_route(self, action)

    def on_bot(bot):
        bot.cfg["account_c"] = {"account": "Sim103", "plan": "builder25k", "eval_start": "2026-10-13"}
        bot.cfg["acct_c_history"] = True
        holder["bot"] = bot
        orig = bot.poll_once

        def poll_once():
            bot._t0_wall = time.perf_counter()
            return orig()
        bot.poll_once = poll_once
    AC.AccountC.route = timed_route
    try:
        r_on = TL.bot_replay(P, by_day, sessions=sessions, on_bot=on_bot)
    finally:
        AC.AccountC.route = real_route
    bot = holder.get("bot")
    C = getattr(bot, "acct_c", None)
    not_routed = [x for x in r_on.get("not_routed") or [] if "[BLITZ" not in x]
    check(f"9. LiveBot with account C on: LIT's {r_on['want']} trades routed and exited exactly as the backtest, nothing extra on LIT's ledger",
          r_on["entries_ok"] == r_on["want"] and r_on["exits_ok"] == r_on["want"] and r_on["extra"] == 0 and not r_on["errors"] and not not_routed,
          {k: r_on.get(k) for k in ("entries_ok", "exits_ok", "want", "extra", "errors")} | {"nr": not_routed[:3]})
    check("9. ... account C built inside the LiveBot from the start cfg (paper)", C is not None and C.kind() == "PAPER" and not C.disabled_reason(),
          getattr(C, "problem", None))
    if C is not None:
        rows = [r for r in C.rows if r.get("day") == "2026-10-15"]
        ref_d = [t for t in json.load(open(os.path.join(ROOT, "research", "scalp", "na_best_trades.json"), encoding="utf-8"))["trades"]
                 if t["entry_t"].startswith("2026-10-15")]
        check(f"9. ... BLITZ's 2026-10-15 trades seen by account C ({len(rows)}) = the research's ({len(ref_d)}), on C's own ledger",
              len(rows) == len(ref_d) and all(r.get("dir") == (1 if t["dir"] == "long" else -1) for r, t in zip(rows, ref_d)), rows[:3])
        routed = [r for r in rows if r.get("routed")]
        check(f"9. ... routed on account C: {len(routed)} (BLITZ rows on C's ledger, none on LIT's)",
              len([a for a in C.ledger if a.get("side") in ("buy", "sell")]) == len(routed) and routed)
        ents = [a for a in C.ledger if a.get("side") in ("buy", "sell")]
        dl = [int(a["t"]) - int(a["entry_t"]) for a in ents]
        check(f"9. ... latency: BLITZ's entries go out in the main poll right after the signal bar closed ({dl} s after the entry bar's "
              f"open at a poll 3 s after it; wall time from the poll's start {', '.join(f'{x:.2f}' for x in lat)} s on this machine)",
              ents and all(0 <= x <= 5 for x in dl) and lat and max(lat) < 10.0, (dl, lat))


# ================================================================================================ 10. switches
def part10():
    tmp = tempfile.mkdtemp(prefix="acctc_sw_")
    try:
        ok = lambda: (True, "ok")
        r = AC.set_account_c("Sim103", start="2026-11-02", root=tmp, selftest=ok, lit_account="L", b_account="B")
        check("10. switch on (Sim): written to data/account_c.json only", r["ok"] and r["sim"] is True and AC.raw_cfg(tmp)["account"] == "Sim103")
        r = AC.set_account_c("Sim103", start="2026-11-02", root=tmp, selftest=lambda: (False, "selftest broke"), lit_account="L", b_account="B")
        check("10. refused when engine.ninjatrader --selftest fails", not r["ok"] and "selftest" in r["error"])
        r = AC.set_account_c("L", root=tmp, selftest=ok, lit_account="L", b_account="B")
        check("10. refused on LIT's account", not r["ok"])
        r = AC.arm("Sim999", root=tmp, selftest=ok)
        check("10. arm() refuses another account", not r["ok"])
        r = AC.arm("Sim103", root=tmp, selftest=ok)
        check("10. arm(): armed true, everything else kept", r["ok"] and AC.raw_cfg(tmp)["armed"] is True and AC.raw_cfg(tmp)["eval_start"] == "2026-11-02")
        r = AC.set_account_c("off", root=tmp)
        check("10. off: account_c null", r["ok"] and AC.raw_cfg(tmp) is None)
        # the Start page's backend (engine/go.py) on temp files only
        from engine import go as G
        from engine import second as SE
        keep = (G.SECOND_PATH, G.ALLOW_PATH, G.CFG, AC._selftest_ok, G.bot_running)
        try:
            G.SECOND_PATH = os.path.join(tmp, "second_model.json")
            shutil.copy(SE.CFG_PATH, G.SECOND_PATH)
            G.ALLOW_PATH = os.path.join(tmp, "allow.json")
            G.CFG = os.path.join(tmp, "data", "start_bot.json")
            AC._selftest_ok = ok
            G.bot_running = lambda: False
            check("10. Start page: BLITZ slot off by default (status 'blitz' on False, no BLITZ account row)",
                  G.blitz_status()["on"] is False and not any(r.get("bot") == "BLITZ" for r in G.accounts({})["rows"]))
            r = G.set_blitz("Sim101", "2026-11-02")
            check("10. Start page: Sim test -> BLITZ on Sim101 (no arming needed)", r["ok"] and r["sim"] and G.blitz_status()["sim"]
                  and G.arm_c("I ACCEPT LIVE RISK")["ok"] is False)
            r = G.set_blitz("MFFUEVBLDRTEST7", "2026-11-02")
            st = G.blitz_status()
            check("10. Start page: an MFFU 25K -> set, allowlisted, NOT armed", r["ok"] and st["on"] and not st["sim"] and st["armed"] is False
                  and "MFFUEVBLDRTEST7" in G._allowed(), (r, st))
            check("10. Start page: the BLITZ row in Accounts (role c, not armed)", any(x.get("bot") == "BLITZ" and x["role"] == "c" and x["armed"] is False
                                                                                    for x in G.accounts({})["rows"]))
            check("10. Start page: arm refused without the exact phrase", G.arm_c("yes")["ok"] is False and AC.raw_cfg(tmp)["armed"] is False)
            r = G.arm_c("i accept live risk")
            check("10. Start page: Arm BLITZ with the typed phrase -> armed (nothing else changed)", r["ok"] and AC.raw_cfg(tmp)["armed"] is True
                  and AC.raw_cfg(tmp)["eval_start"] == "2026-11-02")
            check("10. Start page: BLITZ's Name is taken (not usable for ATLAS / Zlarior)", G.role_of("MFFUEVBLDRTEST7") == "BLITZ's 25K")
            r = G.remove_account("MFFUEVBLDRTEST7")
            check("10. Start page: Remove -> off, off the allowlist", r["ok"] and AC.raw_cfg(tmp) is None and "MFFUEVBLDRTEST7" not in G._allowed(), r)
        finally:
            G.SECOND_PATH, G.ALLOW_PATH, G.CFG, AC._selftest_ok, G.bot_running = keep
        gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read().splitlines()
        check("10. .gitignore: data/account_c.json and live_state_acctc.json", "data/account_c.json" in gi and "data/live_state_acctc*.json" in gi)
        from engine import go
        src = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
        check("10. Start page backend: go.set_blitz / go.arm_c (only after the phrase) / BLITZ row in accounts()",
              hasattr(go, "set_blitz") and hasattr(go, "arm_c") and "BLITZ" in src)
        doc = open(os.path.join(ROOT, "BLITZ_STRATEGY.md"), encoding="utf-8").read()
        check("10. BLITZ_STRATEGY.md: the rule, how it should perform ($ / month next to PF), the kill switch", all(w in doc for w in (
            "Kill switch", "$ a month", "PF", "2 weeks", "1.5 x", "15:55", "6 trades")))
        ref = open(os.path.join(ROOT, "docs", "CLAUDE_REFERENCE.md"), encoding="utf-8").read()
        check("10. docs/CLAUDE_REFERENCE.md: account C entry + the owner's turn-on steps", "engine/account_c.py" in ref and "account C" in ref)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ 11. dashboards data
def part11():
    from engine import accounts as A
    from engine import heartbeat as HB
    from engine import live_board as LB
    from engine import narrator as NR
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot)
    C._events([{"ev": "entry", "entry_t": tb, "sig_t": tb - 60, "dir": 1, "entry": 25000.25, "stop": 24970.0, "risk": 30.25}], "NQ", tb + 62)
    C._events([{"ev": "exit", "entry_t": tb, "exit_t": tb + 1860, "exit": 25030.0, "kind": "time", "pts": 29.75, "risk": 30.25,
                "r": 0.9, "pnl_pm": 57.6, "bars": 31, "mae": 3.0}], "NQ", tb + 1862)
    bot._now = tb + 1900
    blk = HB._account_c(bot)
    check("11. heartbeat account_c: label, kind, eval, scorecard, days, closed trades, no paths",
          blk and blk["label"] == "BLITZ Sim103" and blk["days"] and blk["closed"] and blk["scorecard"]["n"] == 1
          and "/tmp" not in json.dumps(blk), blk and list(blk))
    pc = {"present": True, "t": bot._now, "running": True, "adapter": "paper", "account_c": blk}
    secs = A.build_accounts({"pc": pc, "last_run": bot._now}, {}, bot._now)
    sec = next((s for s in secs if s.get("id") == "acct_c"), None)
    check("11. build_accounts: a 'BLITZ Sim103' section (source pc_blitz) with its eval, trades and P&L, before the cloud paper one",
          sec and sec["source"] == "pc_blitz" and sec["trades"] and sec["eval"] and sec["pnl"]["today"] == blk["day_pnl"]
          and secs[-1].get("source") == "cloud", sec)
    off = A.build_accounts({"pc": {k: v for k, v in pc.items() if k != "account_c"}, "last_run": bot._now}, {}, bot._now)
    check("11. ... without account_c: no BLITZ section (exactly the old list)", not any(s.get("id") == "acct_c" for s in off)
          and len(off) == len(secs) - 1)
    bd = LB.build({"pc": pc, "accounts": secs, "where": "pc"}, bot._now)
    bd0 = LB.build({"pc": {k: v for k, v in pc.items() if k != "account_c"}, "accounts": off, "where": "pc"}, bot._now)
    check("11. live board: a third card 'blitz' (balance, room, waiting, window, scorecard) + accts, BLITZ rows in the trade log",
          isinstance(bd.get("blitz"), dict) and bd["blitz"].get("name") == "BLITZ" and bd.get("accts") == ["lit", "atlas", "blitz"]
          and any(r.get("acct") == "blitz" for r in bd.get("trades") or []), {k: bd.get(k) for k in ("blitz", "accts")})
    check("11. ... off: no blitz key, no accts, no BLITZ rows", "blitz" not in bd0 and "accts" not in bd0
          and not any(r.get("acct") == "blitz" for r in bd0.get("trades") or []))
    msgs, _ = NR.derive(bot, now=bot._now)
    mine = [m for m in msgs if m.get("strat") == "scalp" and "PAPER · BLITZ" in str(m.get("title"))]
    check("11. narrator: account C's rows labelled with the account word (PAPER here, REAL on a real account), apart from the shadow",
          mine and all(not str(m.get("key") or m.get("id") or "").startswith("scalp:blitz:") for m in mine), [m.get("title") for m in msgs][:6])
    from engine import pc_cc_api as CC
    card = CC._blitz_card(bot, bot._now)
    check("11. Mission Control: the BLITZ card (Builder 25K, 6 a day, scorecard)", card and card["max_trades_day"] == 6 and card["scorecard"]["n"] == 1)
    bot2 = FakeBot()
    check("11. Mission Control off: no card", CC._blitz_card(bot2, 0) is None)


# ================================================================================================ 12. review 2026-10-29
def part12():
    """Independent review (2026-10-29): the hedging / isolation gaps found and closed."""
    from engine import live

    class Ad:                                        # another account's NinjaTrader adapter: its own book of brackets
        name = "ninjatrader"

        def __init__(self, legs):
            self.legs = legs

    # a) LIT's TIME exit CLOSEPOSITION not confirmed by NinjaTrader: its leg stays "closing" while LIT's model and
    #    _open_routed already show it flat -> no BLITZ entry the other way
    bot, C = make("2026-11-02")
    bot.adapter = Ad([{"entry_t": 1, "dir": -1, "side": "SELL", "status": "closing"}])
    tb = _open_long(C, bot)
    check("12a. LIT's SHORT close not confirmed at NinjaTrader (leg 'closing', model flat): BLITZ LONG NOT routed",
          C.open_t is None and not C.adapter.sent and "LIT's account still shows a SHORT" in str(C._row(et_=tb).get("skip")),
          C._row(et_=tb))
    bot, C = make("2026-11-02")
    bot.adapter = Ad([{"entry_t": 1, "side": "SELL", "status": "closing"}])           # an older leg without "dir"
    tb = _open_long(C, bot)
    check("12a. ... the same from the leg's side when it has no dir", C.open_t is None)
    bot, C = make("2026-11-02")
    bot.adapter = Ad([{"entry_t": 1, "dir": 1, "status": "closing"}, {"entry_t": 2, "dir": -1, "status": "closed"}])
    tb = _open_long(C, bot)
    check("12a. ... a LONG close in flight (same side) or a retired leg: BLITZ LONG allowed", C.open_t == tb)

    # b) ATLAS's model exit with an unconfirmed sync close: B shows flat (open_t None, nothing "closing") but its adapter
    #    still holds the leg
    class B:
        def __init__(self, legs):
            self.open_t = None
            self.prov = {}
            self.adapter = Ad(legs)

        def closing_open(self):
            return []
    bot, C = make("2026-11-02")
    bot.acct_b = B([{"entry_t": 2, "dir": -1, "status": "closing"}])
    tb = _open_long(C, bot)
    check("12b. ATLAS's SHORT not confirmed flat at NinjaTrader: BLITZ LONG NOT routed", C.open_t is None
          and "ATLAS's account (account B) still shows a SHORT" in str(C._row(et_=tb).get("skip")))

    # c) BLITZ's own model STOP exit (a trail NinjaTrader refused leaves the old stop there): the sync close is not
    #    confirmed -> C is NOT marked flat; LIT's opposite entry waits; booked once when NinjaTrader shows flat
    st = Stub(exit_answer={"ok": False, "flat_confirmed": False, "error": "flatten sent, not confirmed by NinjaTrader yet"})
    bot, C = make("2026-11-02", adapter=st)
    bot.cfg["adapter"] = "ninjatrader"
    tb = _open_long(C, bot)
    pv = C.prov[tb]
    C._events([{"ev": "entry", "entry_t": tb, "sig_t": pv["sig_t"], "dir": 1, "entry": pv["entry"], "stop": pv["stop"], "risk": 30.0}],
              "NQ", tb + 62)
    st.legs = [{"entry_t": tb, "dir": 1, "status": "closing"}]
    bot._now = tb + 662
    C._events([{"ev": "exit", "entry_t": tb, "sig_t": pv["sig_t"], "dir": 1, "entry": pv["entry"], "stop": pv["stop"], "exit_bar_t": tb + 600,
                "exit_t": tb + 660, "exit": pv["entry"] + 10, "kind": "stop", "pts": 10.0, "risk": 30.0, "r": 0.33, "pnl_pm": 18.1,
                "bars": 10}], "NQ", bot._now)
    check("12c. BLITZ's model STOP exit, sync close NOT confirmed: C still open / closing, nothing booked",
          C.open_t == tb and C.closing_open() and not C.closes and any("CLOSE NOT CONFIRMED (STOP)" in t for _, t in bot.logs))
    ent = {"entry_t": tb + 720, "dir": -1, "entry": 25010.0}
    ok = live.LiveBot._hedge_clear(bot, ent, "NQ", tb + 722)
    check("12c. ... LIT's SHORT entry meanwhile is NOT routed (HEDGE WAIT on BLITZ)", ok is False and bot._hedge_who.get(tb + 720) == "BLITZ")
    st.exit_answer, st.legs = {"ok": True}, []
    ok = live.LiveBot._hedge_clear(bot, ent, "NQ", tb + 740)
    check("12c. ... once NinjaTrader shows it flat: booked once (the model's $), LIT routes", ok is True and C.open_t is None
          and len(C.closes) == 1 and abs(C.closes[0][2] - round(pv["qty"] * 18.1, 2)) < 0.01 and C.prov[tb].get("final"))
    bot, C = make("2026-11-02")
    tb = _open_long(C, bot)
    pv = C.prov[tb]
    C._events([{"ev": "entry", "entry_t": tb, "sig_t": pv["sig_t"], "dir": 1, "entry": pv["entry"], "stop": pv["stop"], "risk": 30.0}],
              "NQ", tb + 62)
    C._events([{"ev": "exit", "entry_t": tb, "sig_t": pv["sig_t"], "dir": 1, "entry": pv["entry"], "stop": pv["stop"], "exit_bar_t": tb + 600,
                "exit_t": tb + 660, "exit": pv["entry"] - 30, "kind": "stop", "pts": -30.0, "risk": 30.0, "r": -1.0, "pnl_pm": -61.9,
                "bars": 10}], "NQ", tb + 662)
    check("12c. paper: a STOP exit is booked at once as before", C.open_t is None and len(C.closes) == 1)

    # d) the critical HEDGE BLOCKED alert names BLITZ's account (not "account B") when BLITZ held LIT back
    bot, C = make("2026-11-02")
    bot._hedge_wait, bot._hedge_who = {5000: 4990}, {5000: "BLITZ"}
    live.LiveBot._hedge_blocked(bot, 5000, 5100)
    t = texts(bot)
    check("12d. HEDGE BLOCKED for BLITZ: the body says BLITZ's account C (Sim103), not account B",
          t and "BLITZ's (account C)" in t[-1] and "Sim103" in t[-1] and "account B" not in t[-1], t)

    # e) a second strategy routed on LIT's own account (OFF by default) yields to BLITZ like LIT / ATLAS
    src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    i = src.find("def _second_entry")
    j = src.find("self._open_routed, self._open_src, self._open_qty, self._open_adds = tb, k, q, []", i)
    check("12e. LiveBot._second_entry asks account C to yield before it routes on LIT's account", i > 0 and j > i
          and "ac.yield_to(d" in src[i:j])

    # f) one account Name for two bots is refused whatever its case (NinjaTrader's position files match it case-blind)
    s1 = AC.normalize({"account": "mffuevbldr000006016", "plan": "builder25k"}, lit_account="MFFUEVBLDR000006016")
    s2 = AC.normalize({"account": "Mffu25kAtlas ", "plan": "builder25k"}, b_account="MFFU25KATLAS")
    check("12f. LIT's / ATLAS's Name in another case is refused as account C", s1["problem"] and "Zlarior" in s1["problem"]
          and s2["problem"] and "ATLAS" in s2["problem"])

    # g) switching account C off / to another Name while its state file shows an open BLITZ trade (or a close in flight)
    #    is refused: after a restart nobody would manage that position (no time exit, no 15:55 flat, no hedge hold)
    tmp = tempfile.mkdtemp(prefix="acctc_open_")
    try:
        ok_ = lambda: (True, "ok")
        AC.set_account_c("Sim103", start="2026-11-02", root=tmp, selftest=ok_, lit_account="L", b_account="B")
        sp = AC.state_file(tmp)
        os.makedirs(os.path.dirname(sp), exist_ok=True)
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump({"account": "Sim103", "open_t": 1793721600, "prov": {"1793721600": {"dir": 1, "qty": 2}}}, fh)
        r_off = AC.set_account_c("off", root=tmp)
        r_new = AC.set_account_c("Sim104", start="2026-11-02", root=tmp, selftest=ok_, lit_account="L", b_account="B")
        r_same = AC.set_account_c("Sim103", start="2026-11-03", root=tmp, selftest=ok_, lit_account="L", b_account="B")
        check("12g. BLITZ in a trade: 'off' / another Name refused, the same Name (new start) allowed",
              not r_off["ok"] and "open" in r_off["error"] and not r_new["ok"] and r_same["ok"]
              and AC.raw_cfg(tmp)["account"] == "Sim103", (r_off, r_new, r_same))
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump({"account": "Sim103", "open_t": None, "prov": {"1793721600": {"dir": 1, "closing": {"done": False}}}}, fh)
        r = AC.set_account_c("off", root=tmp)
        check("12g. ... a close not confirmed yet: 'off' refused too", not r["ok"])
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump({"account": "Sim103", "open_t": None, "prov": {"1793721600": {"dir": 1, "closing": {"done": True}, "final": True}}}, fh)
        r = AC.set_account_c("off", root=tmp)
        check("12g. ... flat: 'off' works", r["ok"] and AC.raw_cfg(tmp) is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ 13. the first real day (2026-10-29)
def part13():
    """What a first REAL BLITZ day on NinjaTrader needs that the paper / Sim parts do not show: the phone's entry / exit
    notices name BLITZ's own 25K (labelled REAL), never Zlarior's 50K; NinjaTrader's fill reaches the FILLED line (the
    adapter reports its own fills only for the bot's own account); the words fit BLITZ (no "15-minute check"); the go-live
    check (engine/blitz_preflight.py) turns every line green / red with its fix; the 20-micro cap = MFFU's 25K (2 minis);
    the $600 soft daily loss locks the day; the Nov 1 DST change and the eval's session count."""
    from engine import blitz_preflight as PF
    from engine import narrator as NR
    from engine import account_b as AB

    class NTStub(Stub):
        reports_fills = True                          # = engine/ninjatrader.NinjaTraderAdapter

        def send(self, action):
            self.sent.append(dict(action))
            if action.get("side") in ("buy", "sell"):
                return {"ok": True, "adapter": "ninjatrader", "account": "MFFUEVBLDR777", "legs": [
                    {"instrument": "MNQ 12-26", "qty": action["qty"], "filled": action["qty"], "fill_px": 25000.25, "ok": True}]}
            return {"ok": True, "flat_confirmed": True}

    bot = FakeBot(0, adapter="ninjatrader")
    bot._push_account = lambda: "MFFU 50K"            # Zlarior's label (LiveBot._push_account)
    C = AC.AccountC(bot, spec("2026-11-02", name="MFFUEVBLDR777", armed=True), state_path="")
    C.adapter = NTStub()
    bot.acct_c = C
    check("13. a real account C reads REAL (kind LIVE)", C.kind() == "LIVE" and C.real_word() == "REAL", C.kind())
    tb = _open_long(C, bot, day="2026-11-03")
    check("13. ... its own entry notice is left to the fill report (reports_fills): nothing pushed by account C itself",
          C.open_t == tb and not [p for p in bot.pushed if p.get("kind") == "fill"], texts(bot))
    C._events([{"ev": "entry", "entry_t": tb, "sig_t": tb - 60, "dir": 1, "entry": 25000.25, "stop": 24970.0, "risk": 30.25}], "NQ", tb + 62)
    C._events([{"ev": "exit", "entry_t": tb, "exit_t": tb + 1860, "exit": 25030.0, "kind": "time", "pts": 29.75, "risk": 30.25,
                "r": 0.9, "pnl_pm": 57.6, "bars": 31, "mae": 3.0}], "NQ", tb + 1862)
    bot._now = tb + 1900
    info = C.info(bot._now)
    ent = next((r for r in info["routed"] if r.get("side") == "buy"), {})
    check("13. info() routed rows carry NinjaTrader's fill and the entry price", ent.get("fill") == 25000.25 and ent.get("entry") is not None, ent)
    msgs, _ = NR.derive(bot, now=bot._now)
    fm = next((m for m in msgs if m.get("strat") == "scalp" and m.get("kind") == "entry"), None)
    xm = next((m for m in msgs if m.get("strat") == "scalp" and m.get("kind") == "exit"), None)
    check("13. narrator: a FILLED line for BLITZ's real entry (NinjaTrader's fill price)", fm and fm.get("fill") == 25000.25 and
          "REAL · BLITZ MFFUEVBLDR777" in fm["title"], [m.get("title") for m in msgs if m.get("strat") == "scalp"])
    sent = []
    bot._push_send = lambda p: sent.append(p) or True
    for m in (fm, xm):
        if m:
            NR.send_push(m, bot)
    pe = next((p for p in sent if p.get("kind") == "fill"), {})
    po = next((p for p in sent if p.get("kind") == "outcome"), {})
    check("13. phone entry notice: 'LONG · BLITZ MFFUEVBLDR777 (REAL)', body '(BLITZ scalp)', key fill:<t>:acctc, never 'MFFU 50K'",
          pe.get("title") == "LONG · BLITZ MFFUEVBLDR777 (REAL)" and pe.get("body", "").endswith("(BLITZ scalp)")
          and pe.get("key") == f"fill:{tb}:acctc" and "MFFU 50K" not in json.dumps(sent), sent)
    check("13. phone exit notice: BLITZ's account, REAL, the account-C key (one notice with account C's own HEDGE / TIME push)",
          po.get("title") == "LONG · BLITZ MFFUEVBLDR777 (REAL)" and po.get("key") == f"out:{tb}:acctc" and po.get("tag", "").endswith("-acctc"), po)
    check("13. BLITZ's TIME exit is worded as its 30-minute clock, not LIT's 15-minute check",
          xm and "30-minute clock" in xm["text"] and "15-minute" not in xm["text"], xm)
    # account C's own outcome push (TIME) has the same key / tag: the phone gets one notice
    own = []
    bot._push_send = lambda p: own.append(p) or True
    C._push_outcome({"dir": 1}, "TIME", 115.2, tb + 1860, 2, tb)
    check("13. account C's own TIME notice = the same key and tag as the narrator's", own and own[0]["key"] == po.get("key")
          and own[0]["tag"] == po.get("tag"), own)
    # the notices the owner must act on are pushed (kind ops); "order NOT placed" is pushed by the narrator's refused line
    bot._push_send = lambda p: own.append(p) or True
    own.clear()
    for k in (f"acctc:closing:{tb}", f"acctc:passed:2026-11-02:{C.name}", f"acctc:pause:{tb}", f"acctc:lock:2026-11-03",
              f"acctc:unconfirmed:{tb}", f"acctc:notplaced:{tb}"):
        C._push_text("t", "b", k)
    kinds = [p.get("kind") for p in own]
    check(f"13. CLOSE NOT CONFIRMED / EVAL PASSED / PAUSED / locked out / not confirmed reach the phone (kind ops); not placed via the "
          f"narrator ({kinds})", kinds == ["ops", "ops", "ops", "ops", "ops", "risk"], kinds)
    # ATLAS (account B) notices from the feed use account B's own keys (one notice per trade, never LIT's key)
    pa, _ = NR.payload_for({"kind": "entry", "entry_t": 555, "dir": -1, "qty": 5, "fill": 1.0, "strat": "atlas", "t": 556}, "Account B X")
    pb, _ = NR.payload_for({"kind": "exit", "entry_t": 555, "dir": -1, "usd": 10.0, "reason": "TIME", "t": 900, "strat": "atlas"}, "Account B X")
    pl, _ = NR.payload_for({"kind": "entry", "entry_t": 555, "dir": -1, "qty": 5, "fill": 1.0, "strat": "lit", "t": 556}, "MFFU 50K")
    check("13. ATLAS feed notices: keys fill:<t>:acctb / out:<t>:acctb (= account B's own), LIT's stay fill:<t>",
          pa["key"] == "fill:555:acctb" and pb["key"] == "out:555:acctb" and pl["key"] == "fill:555", (pa["key"], pb["key"], pl["key"]))
    # account B rows get the fill too (its NinjaTrader entries had no FILLED line / phone notice either)
    check("13. account B's routed rows: the same fill helper", AB._fill_of({"side": "sell", "result": {"ok": True, "legs": [{"fill_px": 1.5, "filled": 1}]}})
          == {"fill": 1.5} and AB._fill_of({"side": "sell", "result": {"ok": False, "legs": [{"fill_px": 1.5, "filled": 1}]}}) == {})
    # MFFU's 25K max = 2 minis = 20 micros; the cap holds at a tiny stop; the order check refuses 21
    sz = AC.qty(spec("2026-11-02"), 2.0, {"room": 1000.0, "cum": 0.0, "session": 6})
    check(f"13. the 25K's max contracts: {sz['qty']} micros at a 2-pt stop with the full room (MFFU Builder 25K: 2 minis = 20 micros)",
          sz["qty"] == 20 and spec("2026-11-02")["rules"]["max_micros"] == 20, sz)
    from engine import guards as G
    act = {"side": "buy", "qty": 21, "stop": 24970.0, "target": 25600.0, "entry": 25000.25, "sym": "NQ"}
    bad = G.sanity(act, 21, 20, {"max_stop_pts": AC.MAX_STOP_PTS})
    check("13. order check: 21 micros refused on the 25K", bool(bad), bad)
    # the $600 soft daily loss: after -$600 closed today no new BLITZ entry today; the next day trades again
    bot2, C2 = make("2026-11-02")
    day = "2026-11-03"
    C2.closes.append([day, at_et(day, 11, 31), -610.0, at_et(day, 11, 0), -1.0])
    C2.check_lock(at_et(day, 11, 32))
    tb2 = _open_long(C2, bot2, day=day, hh=12, mm=0)
    r2 = C2._row(et_=tb2)
    check("13. $600 soft daily loss: -$610 today -> locked, the 12:00 BLITZ signal NOT routed", C2.open_t is None and "locked out" in str(r2.get("skip")), r2)
    tb3 = _open_long(C2, bot2, day="2026-11-04", hh=11, mm=0)
    check("13. ... the next day trades again", C2.open_t == tb3, C2._row(et_=tb3))
    # the $1,000 EOD trailing floor locks at start + $100 ($25,100) once an end-of-day balance reaches $26,100
    bot4, C4 = make("2026-11-02")
    C4.closes.append(["2026-11-02", at_et("2026-11-02", 11, 31), 1100.0, at_et("2026-11-02", 11, 0), 2.0])
    bot4._now = at_et("2026-11-03", 10, 0)
    ev = C4.eval_view(bot4._now)
    C4.closes.append(["2026-11-03", at_et("2026-11-03", 11, 31), -300.0, at_et("2026-11-03", 11, 0), -1.0])
    bot4._now = at_et("2026-11-04", 10, 0)
    ev2 = C4.eval_view(bot4._now)
    check(f"13. trailing floor lock: +$1,100 day 1 -> floor ${ev.get('floor'):,.0f} (locked at $25,100), room ${ev.get('room'):,.0f}; "
          f"-$300 day 2 -> floor ${ev2.get('floor'):,.0f}, room ${ev2.get('room'):,.0f} (the floor never moves down)",
          abs(ev["floor"] - 25100.0) < 0.01 and abs(ev["room"] - 1000.0) < 0.01 and abs(ev2["floor"] - 25100.0) < 0.01
          and abs(ev2["room"] - 700.0) < 0.01, (ev, ev2))
    # Nov 1 2026 DST: the eval counts weekdays (Mon Nov 2 = session 1 for a Sunday Set); the checks stay 11:00 ... 15:30 New York
    from engine import sizing as SZ
    check("13. eval session count across the Nov 1 DST change: start Sun Nov 1 -> Mon Nov 2 = 1, Fri Nov 6 = 5, Mon Nov 9 = 6",
          SZ.eval_session("2026-11-01", "2026-11-02") == 1 and SZ.eval_session("2026-11-01", "2026-11-06") == 5
          and SZ.eval_session("2026-11-01", "2026-11-09") == 6)
    t_edt, t_est = BZ.at_et("2026-10-30", 11 * 60), BZ.at_et("2026-11-02", 11 * 60)
    check("13. BLITZ's 11:00 check is 11:00 New York on both sides of the change (15:00 UTC Fri Oct 30, 16:00 UTC Mon Nov 2)",
          (t_edt % 86400) // 3600 == 15 and (t_est % 86400) // 3600 == 16 and BZ.et_parts(t_est)[1] == 660)
    check("13. trading_day after 18:00 ET on Sun Nov 1 (EST) = Mon Nov 2", AC.trading_day(BZ.at_et("2026-11-01", 18 * 60 + 5)) == "2026-11-02")
    # the go-live check: every line from fixture facts, green / red with a fix
    tmp = tempfile.mkdtemp(prefix="acctc_pf_")
    try:
        os.makedirs(os.path.join(tmp, "data"))
        now = BZ.at_et("2026-11-01", 19 * 60)
        r = PF.check(None, root=tmp, now=now, names=("MFFUEVBLDR000006016", "MFFUEVBLDR000006017"), allowed=set(), nt_names=[],
                     connected=True, feed_problem=None, sim_rt={})
        check("13. preflight with BLITZ off: one red line 'BLITZ's account set' with the Start page fix",
              not r["all_green"] and [i["key"] for i in r["items"]] == ["config"] and "Start page" in r["items"][0]["fix"], r)
        AC.write_local({"account": "MFFUEVBLDR777", "plan": "builder25k", "eval_start": "2026-11-02", "armed": False}, tmp)
        kw = dict(names=("MFFUEVBLDR000006016", "MFFUEVBLDR000006017"), connected=True, feed_problem=None)
        r = PF.check(None, root=tmp, now=now, allowed={"MFFUEVBLDR777"}, nt_names=["MFFUEVBLDR777"],
                     sim_rt={"roundtrip": {"t": now - 3600, "ok": True, "account": "Sim101"}}, **kw)
        st = {i["key"]: i for i in r["items"]}
        want = {"config", "own", "nt", "visible", "allow", "sim", "armed", "bot", "eval", "size", "hedge", "contract", "calendar", "feed"}
        check(f"13. preflight lines: {sorted(st)}", want <= set(st), sorted(st))
        check("13. ... not armed = red with the Arm BLITZ fix; bot not running = red; the rest green",
              st["armed"]["state"] == "bad" and "Arm BLITZ" in st["armed"]["fix"] and st["bot"]["state"] == "bad"
              and all(st[k]["state"] == "good" for k in ("config", "own", "nt", "visible", "allow", "sim", "size", "hedge", "contract", "calendar", "feed"))
              and st["eval"]["state"] == "good" and "first session 2026-11-02" in st["eval"]["detail"] and "drawdown left $1,000.00 of $1,000" in st["eval"]["detail"], {k: (v["state"], v["detail"][:60]) for k, v in st.items()})
        check(f"13. ... first trade's size at the fresh 25K's room: {st['size']['detail'][:90]}", "3 micros at a 60-pt stop" in st["size"]["detail"]
              and "20" in st["size"]["detail"], st["size"])
        check(f"13. ... the calendar names the DST change: {st['calendar']['detail'][:110]}", "clocks go back" in st["calendar"]["detail"]
              or "Nov 01" in st["calendar"]["detail"] or "normal session" in st["calendar"]["detail"], st["calendar"])
        check("13. ... the kill-switch line shows the 20-trade floor (-0.150 / 0.62)", "-0.150" in st["contract"]["detail"] and "0.62" in st["contract"]["detail"],
              st["contract"])
        r = PF.check(None, root=tmp, now=now, allowed=set(), nt_names=["OTHER1"], sim_rt={}, **kw)
        st = {i["key"]: i for i in r["items"]}
        check("13. ... Name not in NinjaTrader / not allowlisted / no Sim test = three red lines, each with its fix",
              st["visible"]["state"] == "bad" and st["allow"]["state"] == "bad" and "--allow-account" in st["allow"]["fix"]
              and st["sim"]["state"] == "bad" and st["sim"]["fix"], {k: st[k]["state"] for k in ("visible", "allow", "sim")})
        r = PF.check(None, root=tmp, now=now, allowed={"MFFUEVBLDR777"}, folder=tmp, sim_rt={}, **kw)
        st = {i["key"]: i for i in r["items"]}
        check("13. ... NinjaTrader's account list not exported (no accounts.csv, as on the PC today): the Name line is information "
              "(check it by hand), not a red line", st["visible"]["state"] == "info" and "Accounts tab" in st["visible"]["detail"], st["visible"])
        AC.write_local({"account": "MFFUEVBLDR000006017", "plan": "builder25k", "eval_start": "2026-11-02"}, tmp)
        r = PF.check(None, root=tmp, now=now, allowed=set(), nt_names=[], sim_rt={}, **kw)
        st = {i["key"]: i for i in r["items"]}
        check("13. ... ATLAS's own 25K as BLITZ's = red 'Its own account'", st["own"]["state"] == "bad" and "ATLAS" in st["own"]["detail"], st["own"])
        AC.write_local({"account": "Sim101", "plan": "builder25k", "eval_start": "2026-11-02"}, tmp)
        PF.record_sim("Sim101", "2026-11-02", True, 2, root=tmp, now=now)
        r = PF.check(None, root=tmp, now=now, allowed=set(), nt_names=[], sim_rt={}, **kw)
        st = {i["key"]: i for i in r["items"]}
        check("13. ... BLITZ's own Sim session (data/account_c_sim.json) = the Sim line green; a Sim account needs no arming (info)",
              st["sim"]["state"] == "good" and "BLITZ traded 2 times on Sim101" in st["sim"]["detail"] and st["armed"]["state"] == "info", st["sim"])
        c = PF.compact(r)
        check("13. compact (launch checklist cut): count + the first red line", c["n_red"] >= 1 and c["first"]["state"] == "bad", c)
        # the running bot: an order of Zlarior's NinjaTrader just took proves the route (no Sim roundtrip needed mid-week)
        from types import SimpleNamespace
        AC.write_local({"account": "MFFUEVBLDR777", "plan": "builder25k", "eval_start": "2026-11-02", "armed": True}, tmp)
        os.remove(PF.sim_path(tmp))
        rb = SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "nt_account": "MFFUEVBLDR000006016", "armed": True},
                             health={"nt": {"connected": True}, "feed": {"age_1m_s": 20, "age_5m_s": 100, "stale": False, "market_open": True},
                                     "account": {"armed": True}},
                             ledger=[{"side": "buy", "t": now - 3600, "result": {"ok": True, "adapter": "ninjatrader", "account": "MFFUEVBLDR000006016"}}],
                             acct_b=None, acct_c=None, blitz=None, clock=lambda: now)
        old_env = os.environ.get("NINJATRADER_LIVE")
        r = PF.check(rb, root=tmp, now=now, allowed={"MFFUEVBLDR777"}, nt_names=["MFFUEVBLDR777"], sim_rt={}, **kw)
        st = {i["key"]: i for i in r["items"]}
        check("13. ... running bot, no Sim test file: Zlarior's order NinjaTrader took an hour ago = the route line green",
              st["sim"]["state"] == "good" and "Zlarior's order" in st["sim"]["detail"], st["sim"])
        check("13. ... armed BLITZ but the server without the live switch = red (BLITZ would wait)",
              old_env == "1" or (st["armed"]["state"] == "bad" and "not running live" in st["armed"]["detail"]), st["armed"])
        check("13. ... the bot runs, BLITZ not picked up yet = wait (next poll)", st["bot"]["state"] == "wait", st["bot"])
        # the GET route the Start page's BLITZ card reads (engine/start_api.py), read-only: the phone may read it too
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from engine import go as G
        from engine import start_api as SA
        old = (G.SECOND_PATH, SA._bot, SA._connected, SA._feed)
        try:
            G.SECOND_PATH = os.path.join(tmp, "second_model.json")        # go._c_root() = tmp
            SA._bot = lambda: SimpleNamespace(running=False, cfg={})
            SA._connected, SA._feed = (lambda: True), (lambda: None)
            SA._CPF.update(t=0.0, v=None)
            app = FastAPI()
            app.include_router(SA.router)
            js = TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003)).get(
                "/api/next/start/blitz/preflight?fresh=1").json()
            st = {i["key"]: i for i in js.get("items") or []}
            check("13. GET /api/next/start/blitz/preflight (also from the phone): the lines for the saved account, a cmd, not all green "
                  "(bot not running)", st.get("config", {}).get("state") == "good" and "MFFUEVBLDR777" in st["config"]["detail"]
                  and st.get("bot", {}).get("state") == "bad" and js.get("cmd") == PF.CMD and js.get("all_green") is False,
                  {k: v.get("state") for k, v in st.items()})
        finally:
            G.SECOND_PATH, SA._bot, SA._connected, SA._feed = old
            SA._CPF.update(t=0.0, v=None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    quick = "--quick" in sys.argv
    # account C's own contract with BLITZ shown (dashboard_view.json "hidden_bots": []): hidden (the default since 2026-11-15)
    # its paper / Sim pushes are silent, tests.test_hidden_bots checks that
    from engine import hidden_bots
    hidden_bots.FORCE = ()
    for name, fn in (("1", part1), ("3", part3), ("3b", part3b), ("4", part4), ("5", part5), ("6", part6), ("7", part7), ("8", part8), ("10", part10),
                     ("11", part11), ("12", part12), ("13", part13)):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"part {name} raised {e.__class__.__name__}: {e}", False)
    if not quick:
        for name, fn in (("2", part2), ("9", part9)):
            try:
                fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                check(f"part {name} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed in {time.time() - T0:.0f} s -> {'ALL PASS' if ok == n else 'FAILURES'}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
