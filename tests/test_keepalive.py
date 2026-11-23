"""MFFU 7-day keep-alive trade (engine/keepalive.py, OFF by default), replayed on the simulated NinjaTrader (engine.ninjatrader
._FakeNT) through real NinjaTraderAdapter instances on Sim accounts. Temp dirs only; no phone, no order leaves the machine.

    python -X utf8 -m tests.test_keepalive

  a. the plan: the last full CME session on or before last trade + 6 (Zlarior 50K last traded Mon 11-16 -> Fri 11-20),
     Thanksgiving / Christmas weeks, past the deadline (the next session), the windows (15:33-15:48, half days before the cut)
  b. replay, switch ON, quiet since Mon 11-16: exactly ONE keep-alive (1 MNQ at 15:33, closed 120 s later, flat, nothing
     working), the heads-up + entry + result alerts, the idle clock restarts (nothing more the next days)
  c. a real trade today / a LIT position open / the eval passed / the kill switch / skip today: nothing
  d. OFF: no order ever; the warnings: the session before ("next session is the last safe day"), the act day ("TODAY")
  e. restart safety: a restart with the keep-alive open closes it on the next tick and never re-enters that day; a crash
     after the write-ahead save (no order sent) is retried
  f. hard windows: every entry of a 3-week replay inside its day's window, never 16:10-18:00 / weekend / after a half day's
     halt / a CME closure; a Tier-1 release blocks the window (and the owner is told); the bot's stop and target are 40 ticks
  g. no hedge: another account SHORT -> the keep-alive sells; both sides -> nothing; a strategy entry the other way closes
     an open keep-alive first (multi_account.opposite_open)
  h. MFFU rule checks: room under $100, the daily loss used up -> nothing
  i. lanes on one NinjaTrader account (the Rapid's LIT + ATLAS lanes) are ONE target; account_b's idle counter counts a
     keep-alive; LiveBot wiring; the CLI switch needs --yes; the exit alert words
  j-r. round 1 (owner stops, confirmed fills, --traded, a new account's start, alert thread + retry, the keep-alive's own
     key, a real LiveBot, one warning a day, entry / result straight to ntfy)
  s-z. round 2: a restart on a later day keeps the fill days (real LiveBot, an extra account); a stale heartbeat never
     covers (ops_checks, the board card, the morning brief); hand trades seen in NinjaTrader's Log; the refusal push is
     retried until 16:05; the CLI refuses unknown keys / a future --start, the bot's save keeps a --traded written meanwhile;
     the rest of the owner's stops + LIT's soft daily loss; the push words
"""
from __future__ import annotations

import datetime as dt
import io
import os
import shutil
import sys
import tempfile
import types
from contextlib import redirect_stdout
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import keepalive as K  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []
PX = 26380.0


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:900]}"), flush=True)


def ts(y, m, d, hh, mm=0, ss=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


# ------------------------------------------------------------------------------------------------ the harness
def fill_rows(day, pnl=0.0, ok=True, hh=10):
    """A LIT trade the ledger way: the entry row (result ok = the broker took it) at hh:00 ET and its exit row."""
    y, m, d = map(int, day.split("-"))
    t = ts(y, m, d, hh)
    return [{"t": t, "sym": "NQ", "side": "buy", "qty": 2, "entry_t": t - 60, "result": {"ok": bool(ok)}},
            {"t": t + 1800, "sym": "NQ", "side": "exit", "qty": 2, "entry_t": t - 60, "reason": "STOP", "pnl": float(pnl)}]


class Bot:
    """What engine/keepalive reads from engine/live.LiveBot (the primary LIT account = Zlarior 50K eval). days = the booked
    P&L per day (eval_days) AND, for each, a filled trade in the ledger (fills = False: only the booked $, no fill)."""

    def __init__(self, tmp, ad, now, ka=None, days=None, name="Sim101", fills=True):
        self.cfg = {"sym": "NQ", "adapter": "ninjatrader", "nt_account": name, "model": "lit",
                    "keepalive": {"accounts": {"lit": True}} if ka is None else ka}
        self.state_path = os.path.join(tmp, "live_state.json")
        self.state = {"model": "lit", "eval_life": {"status": "open", "balance": 49193.0, "floor": 48168.0, "room": 1025.0,
                                                    "target_balance": 53000.0, "days_traded": 5}}
        self.adapter = ad
        self.kill = False
        self.health = {}
        self.bars_tail = [{"time": 0, "close": PX}]
        self.days = dict({"2026-11-16": -129.4} if days is None else days)
        self.ledger = [r for d, v in sorted(self.days.items()) for r in fill_rows(d, v)] if fills else []
        self._now = now
        self.logs = []
        self.acct_b = self.acct_r = self.acct_c = self.accts = self.fleet = None
        self._open_routed = None
        self._startup_ok = 1                       # a running bot latched its startup reconcile (guards.startup_tick)
        self._no_entries_day = None

    def clock(self):
        return self._now[0]

    def eval_days(self):
        return dict(self.days)

    def eval_start(self):
        return "2026-10-19"

    def _log(self, kind, text, **kw):
        self.logs.append((kind, text))


class Env:
    def __init__(self, name="Sim101", price=PX):
        from engine.ninjatrader import _FakeNT
        self.tmp = tempfile.mkdtemp(prefix="le_keepalive_")
        self.folder = os.path.join(self.tmp, "NinjaTrader 8")
        self.fake = _FakeNT(self.folder, price=price)
        self.now = [0.0]
        self.alerts = []
        self.adapters = {}

    def cfg(self, name="Sim101", tag=""):
        return {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_account": name, "nt_folder": self.folder,
                "params": {"max_micros": 40, "flat_mod": 955}, "model": "lit", "model_params": {"window": [[120, 930]]},
                "nt_state_path": os.path.join(self.tmp, f"nt_{name}{tag}.json"), "nt_audit_log": os.path.join(self.tmp, f"oif_{name}.log"),
                "nt_max_entries_day": 999, "nt_file_tag": tag}

    def adapter(self, name="Sim101", tag=""):
        from engine.ninjatrader import NinjaTraderAdapter
        ad = NinjaTraderAdapter(self.cfg(name, tag), clock=lambda: self.now[0])
        ad._sleep = lambda s: (self.fake.process(), self.now.__setitem__(0, self.now[0] + s))
        ad._alert_fn = lambda *a, **k: None
        self.adapters[(name, tag)] = ad
        return ad

    def entries(self, acct=None):
        """Our MARKET entries NinjaTrader took: [(order id, account, action)]."""
        return [(k, o["account"], o["action"]) for k, o in self.fake.orders.items()
                if o["type"] == "MARKET" and k.startswith("LE") and k.endswith("E") and (acct is None or o["account"] == acct)]

    def working(self, acct):
        from engine.ninjatrader import LIVE_STATES
        return [k for k, o in self.fake.orders.items() if o["account"] == acct and o["state"] in LIVE_STATES]

    def flat(self, ad):
        p = ad.position_for(ad._instruments()["micro"])
        return (p or {}).get("side", "FLAT") == "FLAT"

    def done(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def poll(env, bot, t, px=PX, extra=()):
    """One LiveBot poll the keep-alive way: adapters' ticks, the manage-only call, (routing), the post-routing call."""
    env.now[0] = t
    env.fake.process()
    for ad in [bot.adapter] + [getattr(o, "adapter", None) for o in extra]:
        if ad is not None:
            ad.tick()
    out = K.tick(bot, t, may_open=False)
    bar = t - t % 60 - 60
    bot.bars_tail = [{"time": bar, "close": px}]
    return out + K.tick(bot, t, px=px, bar_t=bar, may_open=True)


def replay(env, bot, t0, t1, step=30, fine=(15 * 60 + 25, 15 * 60 + 52), coarse=600, extra=(), px=PX):
    """Polls from t0 to t1: every `step` s inside `fine` ET minutes (and the half-day windows), else every `coarse` s."""
    out, t = [], t0
    while t < t1:
        out += [dict(x, t=t) for x in poll(env, bot, t, px, extra)]
        m = K._mod(t)
        w = K.window(K.trading_day(t))
        near = (fine[0] <= m < fine[1]) or (w and w[0] - 5 <= m < w[1] + 5) or (9 * 60 + 25 <= m < 9 * 60 + 35)
        t += step if near else coarse
    return out


def hook(env):
    K.ALERT_HOOK = lambda kind, p: env.alerts.append((kind, p))


# ------------------------------------------------------------------------------------------------ a. the plan
def t_plan():
    print("a. the plan: when, and in which window", flush=True)
    p = K.plan("2026-11-16", ts(2026, 11, 20, 10))
    check("Zlarior 50K last traded Mon 11-16: MFFU's literal limit Mon 11-23, cautious deadline Sun 11-22 -> the keep-alive "
          "acts TODAY Fri 11-20 (day 4, the last full session before the deadline)",
          p["hard"] == "2026-11-23" and p["deadline"] == "2026-11-22" and p["act_day"] == "2026-11-20" and p["due"]
          and p["idle_days"] == 4, p)
    p = K.plan("2026-11-16", ts(2026, 11, 19, 10))
    check("... the day before (Thu 11-19): not due, 'eve' (the next session is the act day)", not p["due"] and p["eve"], p)
    p = K.plan("2026-11-18", ts(2026, 11, 20, 10))
    check("Zlarior 25K #2 (start Wed 11-18, no trade): acts Tue 11-24 (day 6), not today", p["act_day"] == "2026-11-24" and not p["due"], p)
    p = K.plan("2026-11-20", ts(2026, 11, 23, 10))
    check("ATLAS funded traded Fri 11-20: Thanksgiving week -> Wed 11-25 (the last FULL session; Thu 11-26 is a 13:00 half day)",
          p["act_day"] == "2026-11-25" and "2026-11-26" in p["sessions"], p)
    p = K.plan("2026-11-20", ts(2026, 11, 25, 15, 50))
    check("... Wed 11-25 after its window: the rescue moves to the Thu 11-26 half day (before the deadline)",
          p["act_day"] == "2026-11-26" and not p["due"], p)
    p = K.plan("2026-12-21", ts(2026, 12, 23, 10))
    check("Christmas week (last trade Mon 12-21): Wed 12-23 (Thu 12-24 half day, Fri 12-25 closed, the deadline a Sunday)",
          p["act_day"] == "2026-12-23" and p["due"], p)
    p = K.plan("2026-11-10", ts(2026, 11, 20, 10))
    check("past the deadline (last trade 11-10): late, acts at the next session (today) anyway", p["late"] and p["due"], p)
    p = K.plan("2026-11-20", ts(2026, 11, 20, 15, 40))
    check("traded today: never due", not p["due"] and p["idle_days"] == 0, p)
    check("windows: full day 15:33-15:48 ET; Thanksgiving 12:33-12:43 (halt 13:00, entry cut 12:45); Fri 11-27 12:48-12:58 "
          "(halt 13:15); Christmas / Saturday / New Year: none",
          K.window("2026-11-20") == (933, 948) and K.window("2026-11-26") == (753, 763) and K.window("2026-11-27") == (768, 778)
          and K.window("2026-12-25") is None and K.window("2026-11-21") is None and K.window("2027-01-01") is None,
          [K.window(d) for d in ("2026-11-20", "2026-11-26", "2026-11-27", "2026-12-25")])
    check("the cost: about $2.40 (commission $1.90 + 1 tick), at most $22.90 (stop 10 pts + 2 ticks + commission)",
          K.EXPECTED_COST == 2.40 and K.WORST_COST == 22.90 and K.STOP_PTS == K.TARGET_PTS == 10.0 and K.QTY == 1)


# ------------------------------------------------------------------------------------------------ b. one keep-alive
def t_one():
    print("b. replay, ON, quiet since Mon 11-16: exactly one keep-alive", flush=True)
    env = Env()
    hook(env)
    try:
        ad = env.adapter()
        bot = Bot(env.tmp, ad, env.now)
        out = replay(env, bot, ts(2026, 11, 20, 8), ts(2026, 11, 20, 17))
        ents = env.entries("Sim101")
        opens = [x for x in out if x.get("do") == "open"]
        check("Fri 11-20: ONE entry sent, 1 MNQ BUY at 15:33 ET (the window's first poll)",
              len(ents) == 1 and len(opens) == 1 and K._mod(opens[0]["t"]) == 933 and ents[0][2] == "BUY"
              and env.fake.orders[ents[0][0]]["qty"] == 1, (ents, opens))
        closes = [x for x in out if x.get("do") == "close"]
        dn = [x for x in out if x.get("do") == "done"]
        check("closed at market 2 minutes later (CLOSEPOSITION, hold 120 s, inside the 15:33-15:50 window), NinjaTrader flat, "
              "no stop / target left working",
              len(closes) == 1 and closes[0]["t"] - opens[0]["t"] == 120 and K.HOLD_S == 120 and K._mod(closes[0]["t"]) < 950
              and env.flat(ad) and not env.working("Sim101")
              and len(dn) == 1, (closes, dn, env.working("Sim101")))
        lg = next((h for h in ad.history if h.get("keepalive")), {})
        check("the bracket at NinjaTrader: stop 26,370.00 / target 26,390.00 (40 ticks), never a tight one",
              lg.get("stop0") == PX - 10 and lg.get("target") == PX + 10, lg)
        check("result: about -$2.40 (no move: commission + 1 tick), the state 'done', MFFU clock restarts from 11-20",
              dn and dn[0]["usd"] == -2.40 and K.last_day(bot, "lit") == "2026-11-20", dn)
        kinds = [(k, p.get("title")) for k, p in env.alerts]
        heads = [p for k, p in env.alerts if k == "problem" and "Keep-alive today" in p.get("title", "")]
        res = [p for k, p in env.alerts if k == "trade"]
        check("alerts: ONE heads-up at 09:30 ('Keep-alive today on Zlarior 50K', about -$2.40, at most -$22.90, how to skip) "
              "and ONE result ('Keep-alive on Zlarior 50K: LONG closed', -$2.40, key out:<entry>)",
              len(heads) == 1 and "-$2.40" in heads[0]["body"] and "-$22.90" in heads[0]["body"] and "--skip lit" in heads[0]["body"]
              and len(res) == 1 and res[0]["kind"] == "outcome" and res[0]["usd"] == -2.40 and res[0]["exit"] == "KEEP-ALIVE"
              and res[0]["who"] == "Keep-alive on Zlarior 50K" and res[0]["key"] == f"out:{opens[0]['t']}", kinds)
        check("the keep-alive never wrote to the strategy's ledger (no stats, no sizing, no audit change)",
              bot.ledger == fill_rows("2026-11-16", -129.4), bot.ledger[2:])
        out2 = replay(env, bot, ts(2026, 11, 20, 17), ts(2026, 11, 25, 9))
        check("the next days (Sat 11-21 .. Wed 11-25 morning): nothing more (the clock restarted on 11-20; next act day "
              "Wed 11-25)", len(env.entries("Sim101")) == 1 and not [x for x in out2 if x.get("do") == "open"]
              and K.plan(K.last_day(bot, "lit"), ts(2026, 11, 23, 10))["act_day"] == "2026-11-25", out2[:3])
    finally:
        K.ALERT_HOOK = None
        env.done()


# ------------------------------------------------------------------------------------------------ c. nothing when ...
def t_nothing():
    print("c. a real trade / a position / passed / kill / skip: nothing", flush=True)
    cases = [("a real trade today (LIT's entry filled 11-20 10:00)", lambda b: b.ledger.extend(fill_rows("2026-11-20", 312.0))),
             ("a LIT position open through the window", lambda b: b.state.update(position={"entry_t": ts(2026, 11, 20, 15, 20), "dir": 1})),
             ("the eval passed", lambda b: b.state["eval_life"].update(status="passed")),
             ("the kill switch", lambda b: setattr(b, "kill", True)),
             ("feed stale (entries blocked)", lambda b: b.health.update(entries_blocked=True)),
             ("skip today (--skip lit)", lambda b: b.cfg["keepalive"].update(skip={"lit": "2026-11-20"}))]
    for name, mut in cases:
        env = Env()
        hook(env)
        try:
            bot = Bot(env.tmp, env.adapter(), env.now)
            mut(bot)
            replay(env, bot, ts(2026, 11, 20, 15), ts(2026, 11, 20, 16, 20))
            check(f"{name}: no order", not env.entries(), env.entries())
        finally:
            K.ALERT_HOOK = None
            env.done()


# ------------------------------------------------------------------------------------------------ d. OFF
def t_off():
    print("d. OFF: no order ever, the owner's warnings instead", flush=True)
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now, ka={"accounts": {}})
        replay(env, bot, ts(2026, 11, 19, 8), ts(2026, 11, 20, 17))
        check("Thu 11-19 + Fri 11-20 replayed with the switch OFF: no order", not env.entries(), env.entries())
        eve = [p for k, p in env.alerts if "next session is the last safe day" in p.get("title", "")]
        today = [p for k, p in env.alerts if "TODAY is the last safe day" in p.get("title", "")]
        check("Thu: ONE 'Zlarior 50K: the next session is the last safe day' (soft); Fri: ONE 'TODAY is the last safe day: "
              "place 1 MNQ by hand before 15:50 ET' (rings)",
              len(eve) == 1 and eve[0].get("soft") and len(today) == 1 and not today[0].get("soft")
              and "15:50 ET" in today[0]["body"] and "--traded lit" in today[0]["body"], [p.get("title") for _, p in env.alerts])
        n = len(env.alerts)
        bot2 = Bot(env.tmp, bot.adapter, env.now, ka={"accounts": {}})
        replay(env, bot2, ts(2026, 11, 20, 9), ts(2026, 11, 20, 12))
        check("a restart the same day: no repeat warning", len(env.alerts) == n, env.alerts[n:])
    finally:
        K.ALERT_HOOK = None
        env.done()


# ------------------------------------------------------------------------------------------------ e. restart safety
def t_restart():
    print("e. restart safety", flush=True)
    env = Env()
    hook(env)
    try:
        ad = env.adapter()
        bot = Bot(env.tmp, ad, env.now)
        t_in = ts(2026, 11, 20, 15, 33, 2)
        poll(env, bot, t_in)
        check("the keep-alive is open at 15:33:02 (the state file says 'open', written before the order)",
              len(env.entries()) == 1 and not env.flat(ad)
              and K.load_state(K.state_path_for(bot))["acc"]["lit"]["phase"] == "open")
        # the bot dies here; a new process: a new adapter (restores its bracket) and a new bot (re-reads the keep-alive state)
        ad2 = env.adapter(tag="")
        bot2 = Bot(env.tmp, ad2, env.now)
        check("after the restart the adapter restored the keep-alive's bracket", any(lg.get("keepalive") for lg in ad2.legs), ad2.legs)
        out = replay(env, bot2, t_in + 30, ts(2026, 11, 20, 16, 30))
        check("the next tick closes it (flat, nothing working); no second entry that day",
              env.flat(ad2) and not env.working("Sim101") and len(env.entries()) == 1
              and [x["do"] for x in out if x.get("do") in ("close", "done", "open")] == ["close", "done"], out)
    finally:
        K.ALERT_HOOK = None
        env.done()
    env = Env()
    hook(env)
    try:
        ad = env.adapter()
        bot = Bot(env.tmp, ad, env.now)
        sp = K.state_path_for(bot)
        t_in = ts(2026, 11, 20, 15, 33, 2)
        K.save_state({"v": 1, "acc": {"lit": {"day": "2026-11-20", "phase": "sending", "tries": 1, "entry_t": t_in, "sent_at": t_in,
                                              "side": "buy", "dir": 1, "ref": PX, "label": "Zlarior 50K"}},
                      "sent": [], "notes": {}, "log": []}, sp)
        out = replay(env, bot, t_in + 30, ts(2026, 11, 20, 16, 10))
        check("a crash right after the write-ahead save (no order went out): marked not filled, retried 2 minutes later, "
              "exactly one entry, done", [x["do"] for x in out if x.get("do") in ("not_filled", "open", "done")] == ["not_filled", "open", "done"]
              and len(env.entries()) == 1 and env.flat(ad), out)
    finally:
        K.ALERT_HOOK = None
        env.done()


# ------------------------------------------------------------------------------------------------ f. hard windows
def t_windows():
    print("f. hard windows", flush=True)
    bad = []
    for day in range(16, 31):
        for m in range(0, 24 * 60):
            t = ts(2026, 11, day, m // 60, m % 60)
            if not K.in_window(t):
                continue
            e = dt.datetime.fromtimestamp(t, ET)
            w = K.window(e.date())
            if e.weekday() >= 5 or not w or not (w[0] <= m < w[1]) or 16 * 60 + 10 <= m < 18 * 60:
                bad.append(e.isoformat())
            from engine import cme_calendar as CC
            ec = CC.early_close(e.date())
            if ec is not None and m >= CC.entry_cut(e.date(), 955):
                bad.append(("past cut", e.isoformat()))
    check("in_window over Nov 16-30 (every minute): only 15:33-15:48 on full days, 12:33-12:43 Thanksgiving, 12:48-12:58 "
          "Fri 11-27, never a weekend / 16:10-18:00 / at or after a half day's entry cut", not bad, bad[:5])
    env = Env()
    hook(env)
    try:
        ad = env.adapter()
        bot = Bot(env.tmp, ad, env.now, days={"2026-11-09": 50.0})
        out = replay(env, bot, ts(2026, 11, 16, 8), ts(2026, 12, 5, 8))
        opens = [x["t"] for x in out if x.get("do") == "open"]
        inw = all(K.in_window(t) for t in opens)
        days = [K.trading_day(t) for t in opens]
        exp, last, d = [], "2026-11-09", None
        for t in opens:
            exp.append(K.plan(last, t)["due"])
            last = K.trading_day(t)
        check(f"3 weeks of no strategy trade (Nov 16 - Dec 4): keep-alives on {', '.join(days)}, each inside its window, each "
              "due by the plan (at least one calendar day before MFFU's limit, except the first: already late)",
              opens and inw and all(exp) and days[0] == "2026-11-16" and "2026-11-26" not in days and "2026-11-27" not in days
              and all(K.plan(days[i - 1], ts(*map(int, days[i].split("-")), 15, 33))["hard"] > days[i] for i in range(1, len(days))),
              days)
        check("... and every keep-alive closed, NinjaTrader flat, nothing working at the end",
              env.flat(ad) and not env.working("Sim101") and len(env.entries()) == len(opens), (len(env.entries()), len(opens)))
    finally:
        K.ALERT_HOOK = None
        env.done()
    env = Env()
    hook(env)
    old = K._releases
    try:
        K._releases = lambda now: [ts(2026, 11, 20, 15, 40)]
        bot = Bot(env.tmp, env.adapter(), env.now)
        replay(env, bot, ts(2026, 11, 20, 15), ts(2026, 11, 20, 16, 20))
        told = [p for k, p in env.alerts if "did not go through" in p.get("title", "")]
        check("a Tier-1 release at 15:40 ET: the whole window is inside its 10-min pad -> no order, and the owner is told at "
              "the window's end to place it by hand", not env.entries() and len(told) == 1 and "Tier-1 release" in told[0]["body"],
              [p.get("title") for _, p in env.alerts])
        K._releases = lambda now: []
        replay(env, bot, ts(2026, 11, 23, 15), ts(2026, 11, 23, 16, 20))
        check("... Mon 11-23 (MFFU's literal day 7): the late keep-alive runs", len(env.entries()) == 1, env.entries())
        check("news_block: a release 9 min after the hold ends blocks, 11 min after does not",
              K.news_block(1000, 30, [1000 + 30 + 60 + 9 * 60]) and not K.news_block(1000, 30, [1000 + 30 + 60 + 11 * 60]))
    finally:
        K._releases = old
        K.ALERT_HOOK = None
        env.done()


# ------------------------------------------------------------------------------------------------ g. no hedge
class Other:
    """Another account's lane (account B style): open_t + prov[open_t]["dir"]."""

    def __init__(self, name, d=None, adapter=None):
        self.name, self.label, self.problem = name, name, None
        self.open_t = 1 if d else None
        self.prov = {1: {"dir": d}} if d else {}
        self.closes, self.ledger = [["2026-11-20", 0, 10.0, 1]], []
        self.adapter = adapter
        self.spec = {"plan": "builder25k", "eval_start": "2026-11-01"}

    def eval_view(self, now=None):
        return {"stage": "funded", "plan_start": 25000.0, "balance": 25401.0, "floor": 24514.0, "status": "funded", "funded": {}}

    def funded(self):
        return True


def t_hedge():
    print("g. no hedge across accounts", flush=True)
    for d, side, label in ((-1, "SELL", "ATLAS's 25K holds a SHORT -> the keep-alive SELLS (same side)"),
                           (1, "BUY", "ATLAS's 25K holds a LONG -> it buys")):
        env = Env()
        hook(env)
        try:
            bot = Bot(env.tmp, env.adapter(), env.now)
            bot.acct_b = Other("Sim102", d)
            replay(env, bot, ts(2026, 11, 20, 15, 30), ts(2026, 11, 20, 15, 40))
            e = env.entries("Sim101")
            check(label, len(e) == 1 and e[0][2] == side, e)
        finally:
            K.ALERT_HOOK = None
            env.done()
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now)
        bot.acct_b = Other("Sim102", -1)
        bot.acct_c = Other("Sim106", 1)
        replay(env, bot, ts(2026, 11, 20, 15, 30), ts(2026, 11, 20, 15, 50))
        check("accounts hold both sides: no keep-alive", not env.entries("Sim101"), env.entries())
    finally:
        K.ALERT_HOOK = None
        env.done()
    env = Env()
    hook(env)
    try:
        ad = env.adapter()
        bot = Bot(env.tmp, ad, env.now)
        poll(env, bot, ts(2026, 11, 20, 15, 33, 2))
        from engine import multi_account as MA
        router = object.__new__(MA.AccountRouter)
        router.bot, router.accounts = bot, []
        env.now[0] = ts(2026, 11, 20, 15, 33, 10)
        why = router.opposite_open(-1)
        check("a strategy entry SHORT while the keep-alive is LONG: opposite_open closes the keep-alive first (flat) and lets "
              "the entry go", why is None and env.flat(ad) and not env.working("Sim101"), why)
        check("... a LONG entry is not touched by it", router.opposite_open(1) is None)
    finally:
        K.ALERT_HOOK = None
        env.done()


# ------------------------------------------------------------------------------------------------ h. MFFU rule checks
def t_rules():
    print("h. MFFU rule checks", flush=True)
    orig = K._facts
    for name, facts in (("room $90 (under the $100 stuck line)", None),
                        ("the soft daily loss used up today (-$990 of $1,000)",
                         {"start": 50000.0, "balance": 48203.0, "floor": 47193.0, "day_pnl": -990.0})):
        env = Env()
        hook(env)
        try:
            bot = Bot(env.tmp, env.adapter(), env.now)
            if facts is None:
                bot.state["eval_life"]["floor"] = 49103.0
            else:                                  # (a loss today is a trade today: the rule check itself is what is tested)
                K._facts = lambda b, gg, now, f=facts: dict(f)
            g = K.targets(bot)[0]
            why = K._gate(bot, g, "mffu_builder_50k", ts(2026, 11, 20, 15, 33, 2), PX, ts(2026, 11, 20, 15, 32), K.load_config(bot))
            check(f"{name}: blocked ({why})", isinstance(why, str) and ("room" in why or "daily loss" in why), why)
        finally:
            K._facts = orig
            K.ALERT_HOOK = None
            env.done()


# ------------------------------------------------------------------------------------------------ i. the rest
def t_misc():
    print("i. targets, idle hook, wiring, CLI, alert words", flush=True)
    env = Env()
    try:
        lane = types.SimpleNamespace(spec={"lane": "rapid", "nt_account": "Sim103", "adapter": "ninjatrader", "preset": "mffu_rapid_eod_25k"},
                                     id="rapid", adapter=env.adapter("Sim103", "rapid_"), problem=None, mode="two_week", lock=None,
                                     closes=[], ledger=[], open_t=None, start_day=lambda: "2026-11-20")
        ra = types.SimpleNamespace(name="Sim103", adapter=env.adapter("Sim103", "acctr_"), problem=None, open_t=None, prov={},
                                   closes=[], ledger=[], spec={"eval_start": "2026-11-20"}, label="ATLAS Rapid")
        bot = Bot(env.tmp, env.adapter(), env.now)
        bot.accts = types.SimpleNamespace(accounts=[lane])
        bot.acct_r = ra
        T = K.targets(bot)
        rp = [g for g in T if g["key"] == "rapid"]
        check("the Rapid's LIT lane + ATLAS lane (one NinjaTrader account) are ONE target 'rapid', traded through the LIT lane's "
              "adapter, labelled 'Rapid EOD 25K', plan mffu_rapid_eod_25k",
              len(T) == 2 and len(rp) == 1 and len(rp[0]["lanes"]) == 2 and rp[0]["adapter"] is lane.adapter
              and rp[0]["label"] == "Rapid EOD 25K" and K._plan_id(rp[0]) == "mffu_rapid_eod_25k", [(g["key"], g["label"]) for g in T])
        ra.open_t, ra.prov = 5, {5: {"dir": 1}}
        why = K._gate(bot, rp[0], "mffu_rapid_eod_25k", ts(2026, 11, 20, 15, 33, 2), PX, ts(2026, 11, 20, 15, 32), K.load_config(bot))
        check("ATLAS's lane holds a position on the Rapid: the account is busy (one position per account)",
              isinstance(why, str) and "position" in why, why)
    finally:
        env.done()
    # account_b's idle counter (its 7-day push) counts a keep-alive day
    from engine import account_b as AB
    tmp = tempfile.mkdtemp(prefix="le_keepalive_idle_")
    try:
        b = types.SimpleNamespace(state_path=os.path.join(tmp, "live_state.json"))
        K.save_state({"v": 1, "acc": {"atlas": {"last": "2026-11-24"}}, "sent": [], "notes": {}, "log": []}, K.state_path_for(b))
        fake = types.SimpleNamespace(bot=b, spec={"eval_start": "2026-11-10"}, prov={}, funded=lambda: False,
                                     all_closes=lambda: [["2026-11-17", 0, 10.0, 0]])
        n = AB.AccountB.idle_days(fake, ts(2026, 11, 25, 10))
        check("account_b.idle_days: last close 11-17 but a keep-alive filled 11-24 -> 1 idle day (its 7-day push stops)", n == 1, n)
        r = K.mark_traded("x:b25k_2", "2026-11-23", path=K.state_path_for(b), now=ts(2026, 11, 23, 16))
        check("--traded x:b25k_2 2026-11-23 notes a hand trade (the clock restarts from it)",
              r["marked"] == "2026-11-23" and K.last_day(b, "x:b25k_2") == "2026-11-23", r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    ma = open(os.path.join(ROOT, "engine", "multi_account.py"), encoding="utf-8").read()
    ab = open(os.path.join(ROOT, "engine", "account_b.py"), encoding="utf-8").read()
    check("LiveBot wiring: _keepalive_tick after the routing (with the poll's 1m close) and a manage-only call after the "
          "adapters' ticks; every entry route asks keepalive.before_entry first (LiveBot._route, AccountB.route, multi_account "
          "Account.route, AccountRouter.opposite_open)",
          "self._keepalive_tick(df1, now)" in src and "self._keepalive_tick(None, now, may_open=False)" in src
          and "hedge = self._keepalive_yield(action, self)" in src and "_ka.before_entry(self, 1 if" in src
          and "_ka.before_entry(self.bot, d, self.bot if exclude is None else exclude)" in ma
          and ma.count("ka = self._keepalive_yield(action)") == 1 and ab.count("ka = self._keepalive_yield(action)") == 1
          and "_ka.before_entry(self.bot, 1 if" in ab)
    from engine import live as L
    bot = types.SimpleNamespace(_note_error=lambda m: (_ for _ in ()).throw(AssertionError(m)), state_path="/nonexistent/x.json",
                                cfg={"keepalive": {"accounts": {}}}, clock=lambda: 0)
    ok = True
    try:
        L.LiveBot._keepalive_tick(bot, None, 0)
    except Exception:
        ok = False
    check("LiveBot._keepalive_tick never raises on a bot with nothing to do", ok)
    tmp = tempfile.mkdtemp(prefix="le_keepalive_cli_")
    old = K.CONFIG_PATH
    try:
        K.CONFIG_PATH = os.path.join(tmp, "keepalive.json")
        with redirect_stdout(io.StringIO()):
            rc1 = K.main(["--on", "lit"])
        f1 = os.path.exists(K.CONFIG_PATH)
        with redirect_stdout(io.StringIO()):
            rc2 = K.main(["--on", "lit", "--yes"])
        c = K.load_config(None)
        with redirect_stdout(io.StringIO()):
            K.main(["--off", "lit"])
        check("CLI: --on without --yes refuses (exit 2, nothing written); --on --yes writes the switch; --off clears it",
              rc1 == 2 and not f1 and rc2 == 0 and c["accounts"].get("lit") is True and K.load_config(None)["accounts"].get("lit") is False,
              (rc1, f1, rc2, c))
        check("a harness bot never reads the owner's file (no 'keepalive' block = OFF)",
              K.load_config(types.SimpleNamespace(cfg={}, state_path=os.path.join(tmp, "s.json")))["accounts"] == {})
    finally:
        K.CONFIG_PATH = old
        shutil.rmtree(tmp, ignore_errors=True)
    from engine import notify, push
    t_in = ts(2026, 11, 20, 15, 33, 2)
    p = push.outcome_payload("MFFU 50K", "LONG", "KEEP-ALIVE", -2.4, t_in, t_in + 30, src="pc", qty=1,
                             who="Keep-alive on Zlarior 50K")
    m = notify.exit_message(p, now=t_in + 31, ctx={})
    check("the phone's exit alert (whole dollars, as every exit alert): 'Keep-alive on Zlarior 50K: closed LONG -$2 "
          "(keep-alive)' / '1 MNQ · 3:33 PM ET.'", m["title"] == "Keep-alive on Zlarior 50K: closed LONG −$2 (keep-alive)"
          or m["title"] == "Keep-alive on Zlarior 50K: closed LONG -$2 (keep-alive)", m)
    check("a real-account alert (the phone gets it), never a Sim / paper one", notify.real_trade(p)
          and not notify.real_trade(dict(p, account="Sim101")))


# ------------------------------------------------------------------------------------------------ j. the owner's stops (round 1)
def t_owner_stops():
    print("j. the owner's stops + the entry guards LIT / ATLAS obey (skeptic round 1, HIGH)", flush=True)
    from engine import entry_pause, guards as G
    keep_clock = G.clock_problem

    def pause(b, env):
        entry_pause.set_pause("tomorrow", now=ts(2026, 11, 20, 9), path=entry_pause.path_for(b))

    def startup(b, env):
        b._startup_ok = None
        b.adapter.startup_problems = lambda: ["NinjaTrader connection not confirmed yet"]

    def clock(b, env):
        G.clock_problem = lambda bot, c: "PC clock 9.0 s behind internet time (max 5 s)"

    cases = [("the phone / dashboard pause ('pause until tomorrow')", pause, "your pause blocks the keep-alive"),
             ("the remote flatten ('no new entries today', LiveBot._no_entries_day)",
              lambda b, env: setattr(b, "_no_entries_day", "2026-11-20"), "you flattened remotely today"),
             ("the startup reconcile not passed yet (STARTUP DISARMED)", startup, "STARTUP DISARMED"),
             ("the PC clock guard (clock off by 9 s)", clock, "PC clock")]
    for name, mut, words in cases:
        env = Env()
        hook(env)
        try:
            bot = Bot(env.tmp, env.adapter(), env.now)
            mut(bot, env)
            replay(env, bot, ts(2026, 11, 20, 15), ts(2026, 11, 20, 16, 20))
            told = [p for k, p in env.alerts if "did not go through" in p.get("title", "")]
            check(f"{name}: NO order, and the 15:47 'place 1 MNQ by hand' push says why ('{words}')",
                  not env.entries() and len(told) == 1 and words in told[0]["body"], (env.entries(), [p.get("body") for p in told]))
        finally:
            G.clock_problem = keep_clock
            K.ALERT_HOOK = None
            env.done()
    env = Env()
    try:
        lane = types.SimpleNamespace(spec={"lane": "rapid", "nt_account": "Sim103", "adapter": "ninjatrader", "preset": "mffu_rapid_eod_25k"},
                                     id="rapid", adapter=env.adapter("Sim103", "rapid_"), problem=None, mode="two_week", lock=None,
                                     closes=[], ledger=[], open_t=None, start_day=lambda: "2026-11-16",
                                     entry_block=lambda now: None)
        ra = types.SimpleNamespace(name="Sim103", adapter=env.adapter("Sim103", "acctr_"), problem=None, open_t=None, prov={},
                                   closes=[], ledger=[], spec={"eval_start": "2026-11-16"}, label="ATLAS Rapid",
                                   startup_block=lambda now: "STARTUP DISARMED until reconciled: chart on the wrong contract")
        bot = Bot(env.tmp, env.adapter(), env.now)
        bot.accts = types.SimpleNamespace(accounts=[lane])
        bot.acct_r = ra
        g = next(g for g in K.targets(bot) if g["key"] == "rapid")
        t_in, C = ts(2026, 11, 20, 15, 33, 2), K.load_config(bot)
        w1 = K._gate(bot, g, "mffu_rapid_eod_25k", t_in, PX, t_in - 62, C)
        ra.startup_block = lambda now: None
        ra.lock = {"day": "2026-11-20", "reason": "soft daily loss"}
        w2 = K._gate(bot, g, "mffu_rapid_eod_25k", t_in, PX, t_in - 62, C)
        ra.lock = None
        lane.entry_block = lambda now: "news ban: Tier-1 release at 15:40 ET"
        w3 = K._gate(bot, g, "mffu_rapid_eod_25k", t_in, PX, t_in - 62, C)
        lane.entry_block = lambda now: "already traded today (1 trade a day)"
        w4 = K._gate(bot, g, "mffu_rapid_eod_25k", t_in, PX, t_in - 62, C)
        check("lane guards: ATLAS's STARTUP DISARMED, its lock-out, the extra lane's entry block (news ban) each block; the lane's "
              "'already traded today' count does not (its confirmed fills decide that)",
              "STARTUP DISARMED" in str(w1) and "locked out today" in str(w2) and "news ban" in str(w3)
              and not (isinstance(w4, str) and "already traded" in w4), (w1, w2, w3, w4))
    finally:
        env.done()


# ------------------------------------------------------------------------------------------------ k. confirmed fills only
def t_fills():
    print("k. only CONFIRMED fills count (skeptic round 1, HIGH)", flush=True)
    env = Env()
    hook(env)
    try:
        ad = env.adapter()
        bot = Bot(env.tmp, ad, env.now)
        bot.days.update({"2026-11-18": 0.0, "2026-11-19": 0.0})          # booked $0 days, nothing filled
        bot.ledger += fill_rows("2026-11-18", 0.0, ok=False)             # an entry NinjaTrader refused + its $0 'not placed' exit
        g = K.targets(bot)[0]
        last = K.last_known(bot, g, K.load_config(bot))
        replay(env, bot, ts(2026, 11, 20, 15), ts(2026, 11, 20, 16, 20))
        check("last real fill Mon 11-16 + a refused entry Wed 11-18 ($0 exit row) + a $0 eval day Thu 11-19: the last trade "
              "is still 11-16, and the keep-alive acts TODAY Fri 11-20 (MFFU's limit Mon 11-23)",
              last[0] == "2026-11-16" and not last[2] and len(env.entries()) == 1, (last, env.entries()))
    finally:
        K.ALERT_HOOK = None
        env.done()
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now, days={"2026-11-16": -129.4, "2026-11-19": 85.0})
        replay(env, bot, ts(2026, 11, 20, 15), ts(2026, 11, 20, 16, 20))
        check("control: a REAL fill Thu 11-19 -> no keep-alive Fri (next act day Wed 11-25)",
              not env.entries() and K.plan(K.last_known(bot, K.targets(bot)[0])[0], ts(2026, 11, 20, 10))["act_day"] == "2026-11-25")
    finally:
        K.ALERT_HOOK = None
        env.done()
    t_ev = ts(2026, 11, 15, 19, 5)                       # Sunday 19:05 ET = trading day Mon 11-16
    rows = [{"t": t_ev, "side": "sell", "entry_t": t_ev - 60, "result": {"ok": True}}]
    x = types.SimpleNamespace(closes=[["2026-11-19", ts(2026, 11, 19, 10), 0.0, ts(2026, 11, 19, 9)]], ledger=[])
    check("an evening fill counts on its ET calendar date (Sun 11-15, not the trading day 11-16); an extra lane's $0 close "
          "with no filled entry counts nothing",
          K._fill_days(rows) == {"2026-11-15"} and K._lane_days("extra", x, None) == set())


# ------------------------------------------------------------------------------------------------ l. --traded
def t_traded():
    print("l. --traded: no future day, at most 7 days back, the ET date (skeptic round 1, HIGH + LOW)", flush=True)
    tmp = tempfile.mkdtemp(prefix="le_keepalive_traded_")
    try:
        p = os.path.join(tmp, "keepalive_state.json")
        now = ts(2026, 11, 20, 19)
        bad = []
        for day in ("2026-12-20", "2026-11-21", "2026-11-12"):
            try:
                K.mark_traded("atlas", day, path=p, now=now)
                bad.append(day)
            except ValueError:
                pass
        check("refused: 2026-12-20 (a typo for 11-20), tomorrow 11-21, 8 days back 11-12; nothing written",
              not bad and not os.path.exists(p), bad)
        r = K.mark_traded("atlas", "2026-11-13", path=p, now=now)
        check("accepted: 7 days back (11-13)", r["marked"] == "2026-11-13", r)
        r = K.mark_traded("lit", None, path=p, now=ts(2026, 11, 24, 19))
        check("no date, typed Tue 11-24 at 19:00 ET (after the 18:00 roll): noted Tue 11-24 (the ET date), not Wed 11-25",
              r["marked"] == "2026-11-24" and K.trading_day(ts(2026, 11, 24, 19)) == "2026-11-25", r)
        old = K.state_path_for
        K.state_path_for = lambda bot=None: p
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc_bad = K.main(["--traded", "atlas", "2099-01-01"])
            out_bad = buf.getvalue()
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc_ok = K.main(["--traded", "x:b25k_2"])
            out_ok = buf.getvalue()
        finally:
            K.state_path_for = old
        check("CLI: a future day -> 'NOT noted' (exit 2); today -> noted, and it prints MFFU's new limit and the last safe day",
              rc_bad == 2 and "NOT noted" in out_bad and rc_ok == 0 and "MFFU's 7 days now end" in out_ok
              and "last safe day" in out_ok, (out_bad, out_ok))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ m. a new account's start
def x_lane(env, start="2026-11-18", key_id="b25k_2", name="Sim104"):
    return types.SimpleNamespace(spec={"id": key_id, "nt_account": name, "adapter": "ninjatrader", "preset": "mffu_builder_25k",
                                       "name": "Zlarior 25K #2"},
                                 id=key_id, adapter=env.adapter(name, f"{key_id}_"), problem=None, mode="two_week", lock=None,
                                 closes=[], ledger=[], open_t=None, start_day=lambda: start, entry_block=lambda now: None)


def t_start():
    print("m. an account with no trade yet: day 1 = its start; the earliest lane start (skeptic round 1, HIGH + LOW)", flush=True)
    check("no fill yet, start Wed 11-18: counted from Tue 11-17 (the start day is day 1) -> acts Mon 11-23, MFFU's limit "
          "Tue 11-24 (was Tue 11-24 / limit 11-25)",
          K.last_of(set(), "2026-11-18") == ("2026-11-17", True)
          and K.plan("2026-11-17", ts(2026, 11, 20, 10))["act_day"] == "2026-11-23"
          and K.plan("2026-11-17", ts(2026, 11, 20, 10))["hard"] == "2026-11-24")
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now, ka={"accounts": {}})
        bot.accts = types.SimpleNamespace(accounts=[x_lane(env)])
        g = next(g for g in K.targets(bot) if g["key"] == "x:b25k_2")
        env.now[0] = ts(2026, 11, 20, 9)                 # (the bot's clock: a start after "today" is ignored)
        lk = K.last_known(bot, g, K.load_config(bot))
        replay(env, bot, ts(2026, 11, 20, 9), ts(2026, 11, 20, 10))
        t2 = [p for k, p in env.alerts if p.get("title", "").startswith("Zlarior 25K #2: TODAY is the last safe day")]
        check("the 25K #2 (bot start Wed 11-18, on the PC Tue 11-17 evening: START_DEFAULTS): start 11-17, counted from 11-16 "
              "-> TODAY Fri 11-20 is its last safe day: ONE push 'Zlarior 25K #2: TODAY is the last safe day', 'since it "
              "started (2026-11-17)'",
              lk == ("2026-11-16", "2026-11-17", True) and len(t2) == 1 and "since it started (2026-11-17)" in t2[0]["body"]
              and "--traded x:b25k_2" in t2[0]["body"], (lk, [p.get("title") for _, p in env.alerts]))
        C = {"start": {"x:b25k_2": "2026-11-01"}}
        check("an override only moves the start EARLIER and by at most 7 days (a stale 11-01 is ignored; a later one too)",
              K._start_override(C, "x:b25k_2", "2026-11-18") == "2026-11-18"
              and K._start_override({"start": {"x:b25k_2": "2026-11-19"}}, "x:b25k_2", "2026-11-18") == "2026-11-18"
              and K._start_override({}, "x:other", "2026-11-18") == "2026-11-18")
    finally:
        K.ALERT_HOOK = None
        env.done()
    env = Env()
    try:
        lane = types.SimpleNamespace(spec={"lane": "rapid", "nt_account": "Sim103", "adapter": "ninjatrader", "preset": "mffu_rapid_eod_25k"},
                                     id="rapid", adapter=env.adapter("Sim103", "rapid_"), problem=None, mode="two_week", lock=None,
                                     closes=[], ledger=[], open_t=None, start_day=lambda: "2026-11-20")
        t12 = ts(2026, 11, 12, 10)
        ra = types.SimpleNamespace(name="Sim103", adapter=env.adapter("Sim103", "acctr_"), problem=None, open_t=None, prov={},
                                   closes=[], ledger=[{"t": t12, "side": "buy", "entry_t": t12 - 60, "result": {"ok": True}}],
                                   spec={"eval_start": "2026-11-10"}, label="ATLAS Rapid")
        bot = Bot(env.tmp, env.adapter(), env.now)
        bot.accts = types.SimpleNamespace(accounts=[lane])
        bot.acct_r = ra
        g = next(g for g in K.targets(bot) if g["key"] == "rapid")
        days, start = K.account_days(bot, g)
        check("two lanes on one account (ATLAS from 11-10, the LIT lane switched on 11-20): start = 11-10 (the earliest), so "
              "ATLAS's 11-12 fill still counts", start == "2026-11-10" and days == {"2026-11-12"}, (days, start))
    finally:
        env.done()


# ------------------------------------------------------------------------------------------------ n. alerts: thread + retry
def t_alerts():
    print("n. alerts: a background thread outside the lock; a key only after ntfy took it, retried 5 min apart (round 1, LOW)",
          flush=True)
    import threading
    import time as _time
    env = Env()
    old_alert = K._alert
    go = threading.Event()
    seen = []
    try:
        def slow(bot, kind, p):
            seen.append(threading.current_thread().name)
            go.wait(5)
            return "sent"
        K._alert = slow
        bot = Bot(env.tmp, env.adapter(), env.now, ka={"accounts": {}})
        env.now[0] = ts(2026, 11, 20, 9, 30, 2)
        t0 = _time.time()
        K.tick(bot, env.now[0], px=PX, bar_t=env.now[0] - 62)
        took = _time.time() - t0
        free = K._MX.acquire(timeout=0.5)
        if free:
            K._MX.release()
        pending = not (K.load_state(K.state_path_for(bot)).get("sent"))
        go.set()
        if K._LAST_THREAD is not None:
            K._LAST_THREAD.join(5)
        st = K.load_state(K.state_path_for(bot))
        check("a slow ntfy (the push hangs): the tick returns at once, the keep-alive's lock is free, the push goes out from "
              "the 'keepalive-alerts' thread; its key is recorded only after it was sent",
              took < 3.0 and free and seen == ["keepalive-alerts"] and pending and "ka:today:lit:2026-11-20" in st["sent"],
              (took, free, seen, st["sent"]))
    finally:
        go.set()
        K._alert = old_alert
        env.done()
    env = Env()
    answers = ["ntfy did not take it (the 15-minute report sends it instead)", "sent"]
    tries = []
    try:
        def flaky(bot, kind, p):
            tries.append((K._mod(env.now[0]), p.get("key")))
            return answers.pop(0) if answers else "sent"
        K._alert = flaky
        K.SYNC_ALERTS = True
        bot = Bot(env.tmp, env.adapter(), env.now, ka={"accounts": {}})
        for t in range(ts(2026, 11, 20, 9, 30, 2), ts(2026, 11, 20, 9, 50), 30):
            env.now[0] = t
            K.tick(bot, t, px=PX, bar_t=t - 62)
        st = K.load_state(K.state_path_for(bot))
        lit = [m for m, k in tries if k == "ka:today:lit:2026-11-20"]
        check("ntfy refuses 'TODAY is the last safe day' at 09:30: NOT marked sent, tried again at 09:35 (not every poll), "
              "taken then, recorded, never again", lit == [570, 575] and "ka:today:lit:2026-11-20" in st["sent"], (tries, st["sent"]))
    finally:
        K._alert = old_alert
        K.SYNC_ALERTS = False
        env.done()


# ------------------------------------------------------------------------------------------------ o. the keep-alive's own key
def t_key_for():
    print("o. account_b's idle counter reads the keep-alive's OWN key of its account (round 1, LOW)", flush=True)
    from engine import account_b as AB
    tmp = tempfile.mkdtemp(prefix="le_keepalive_key_")
    try:
        b = types.SimpleNamespace(state_path=os.path.join(tmp, "live_state.json"))
        K.save_state({"v": 1, "acc": {"rapid": {"last": "2026-11-24"}}, "sent": [], "notes": {}, "log": []}, K.state_path_for(b))
        fake = types.SimpleNamespace(bot=b, spec={"eval_start": "2026-11-10"}, prov={}, funded=lambda: False, problem=None,
                                     adapter=None, yield_to_lit=lambda *a: None, all_closes=lambda: [["2026-11-17", 0, 10.0, 0]])
        b.acct_b = fake                                    # ATLAS's funded 25K, with lit25 on: SharedAtlas (yield_to_lit)
        n = AB.AccountB.idle_days(fake, ts(2026, 11, 25, 10))
        check("ATLAS (a SharedAtlas: lifecycle.key_of says 'rapid'): the Rapid's keep-alive on 11-24 does NOT reset ATLAS's "
              "clock (key 'atlas'): 8 idle days, its 7-day push still comes", K.key_for(b, fake) == "atlas" and n == 8, n)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ p. a real LiveBot
def live_bot(tmp, now, ad, ka=None):
    from engine import live
    b = live.LiveBot()
    b.clock = lambda: now[0]
    b.state_path = os.path.join(tmp, "live_state.json")
    b._remember = lambda *a, **kw: None
    b._journal = lambda *a, **kw: None
    b.pushes = []
    b._push_send = lambda p: b.pushes.append(p)
    b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "nt_account": "Sim101", "params": {"max_micros": 40},
             "model": "lit", "keepalive": ka if ka is not None else {"accounts": {"lit": True}}}
    b.state = {"model": "lit"}
    b.adapter = ad
    b.started_at = int(now[0]) - 6 * 3600
    return b


def open_keepalive(env, bot, ad, t_in, label="Zlarior 50K"):
    """A keep-alive LONG 1 MNQ open the keep-alive's way (its bracket at NinjaTrader + its book 'open')."""
    env.now[0] = t_in
    r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "entry": PX, "stop": PX - 10, "target": PX + 10, "entry_t": t_in,
                 "who": f"Keep-alive on {label}", "reason": "KEEP-ALIVE", "keepalive": True})
    lg = K._leg_of(ad, t_in)
    if lg is not None:
        lg["keepalive"] = True
    b = K._book(bot)
    b["st"]["acc"]["lit"] = {"day": K.trading_day(t_in), "phase": "open", "tries": 1, "entry_t": t_in, "sent_at": t_in,
                             "side": "buy", "dir": 1, "ref": PX, "label": label, "fill": (lg or {}).get("fill_px")}
    K._save_book(bot, b)
    return r


def t_live_bot():
    print("p. a real LiveBot: the reconcile guard and LIT's own entry during the 2-minute hold (round 1, LOW)", flush=True)
    from engine import guards as G
    env = Env()
    try:
        ad = env.adapter()
        bot = live_bot(env.tmp, env.now, ad)
        t_in = ts(2026, 11, 20, 15, 33, 2)
        r = open_keepalive(env, bot, ad, t_in)
        k = len(env.fake.files)
        for dt_ in (0, 30, 60, 90, 120):
            env.now[0] = t_in + 1 + dt_
            env.fake.process()
            G.reconcile_tick(bot, G.DEFAULTS, int(env.now[0]))
        lines = [ln for _, ls in env.fake.files[k:] for ln in ls]
        probs = G.startup_problems(bot, G.DEFAULTS, int(env.now[0]))
        check("NinjaTrader LONG 1 (the keep-alive) for 2 minutes, LIT's ledger flat: no 'Position mismatch' push, no RECONCILE "
              "close, nothing logged as a manual trade; the startup check counts it too",
              r.get("ok") and not env.flat(ad) and not bot.pushes and not any(ln.startswith("CLOSEPOSITION") for ln in lines)
              and not any(x.get("reason") == "RECONCILE" for x in bot.ledger) and G._keepalive_net(ad) == 1
              and not any("shows LONG" in p for p in probs), (bot.pushes, lines, probs))
    finally:
        env.done()
    env = Env()
    try:
        ad = env.adapter()
        bot = live_bot(env.tmp, env.now, ad)
        t_in = ts(2026, 11, 20, 15, 33, 2)
        open_keepalive(env, bot, ad, t_in)
        env.now[0] = t_in + 70
        res = bot._route({"sym": "NQ", "side": "buy", "qty": 2, "entry": PX, "stop": PX - 20, "target": PX + 60,
                          "entry_t": t_in + 60})
        kal = [h for h in ad.history if h.get("keepalive")]
        mine = [lg for lg in ad.legs if lg.get("entry_t") == t_in + 60]
        check("a LIT entry the SAME way during the hold: the keep-alive is closed first (CLOSEPOSITION, flat), then LIT's entry "
              "goes out and fills (never 'the bracket of the entry at 15:33 is still open')",
              res.get("ok") and kal and mine and mine[0].get("filled") == 2
              and K.load_state(K.state_path_for(bot))["acc"]["lit"]["phase"] == "closing", (res, kal, ad.legs))
        out = K.tick(bot, env.now[0] + 30, px=PX, bar_t=env.now[0] - 30)
        check("... the next tick books the keep-alive (done, MFFU's clock restarts); the strategy's ledger has only LIT's own "
              "entry", any(x.get("do") == "done" for x in out) and [x.get("side") for x in bot.ledger] == ["buy"], (out, bot.ledger))
    finally:
        env.done()


# ------------------------------------------------------------------------------------------------ q. one warning a day, one place
def t_one_place():
    print("q. ONE inactivity warning per account and day, from one place; the counters count keep-alive days (round 1, LOW)",
          flush=True)
    from engine import live_board as LB, ops_checks as OC
    from tools import pc_guard as PG, morning_brief as MB
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now, ka={"accounts": {}})
        replay(env, bot, ts(2026, 11, 20, 9), ts(2026, 11, 20, 10))
        hb = K.hb_block(bot)
        check("the heartbeat block: the keep-alive covers 'lit' (its warnings), lane lit -> account lit, no names",
              hb and hb["cover"] == ["lit"] and hb["lane"] == {"lit": "lit"} and K.covered("lit", env.now[0], bot=bot), hb)
        today = [p for k, p in env.alerts if "TODAY" in p.get("title", "")]
        now = ts(2026, 11, 20, 10)
        view = {"is_live": True, "eval": {"status": "open", "start": "2026-10-19"}, "trades": [{"day": "2026-11-14"}],
                "position": None, "fresh": True, "keepalive": hb}
        n_ops = OC.inactivity_notice(view, now)
        n_ops_down = OC.inactivity_notice({k: v for k, v in view.items() if k != "keepalive"}, now)
        card = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "configured": True, "status": "open",
                "balance": 49000.0, "floor": 48000.0, "room": 1000.0, "mll": 2000.0, "today_pnl": 0.0, "quiet_days": 6,
                "eval_start": "2026-10-19", "position": None, "keepalive": {"key": "lit", "cover": True}}
        snap = {"t": now, "hb_age": 60, "mode": "LIVE", "live": {"board": {"lit": card}}}
        q_cov = [m for m in PG.account_pushes(snap, {}, now) if ":quiet:" in m["key"]]
        snap["live"]["board"]["lit"] = {**card, "keepalive": {"key": "lit", "cover": False}}
        q_down = [m for m in PG.account_pushes(snap, {}, now) if ":quiet:" in m["key"]]
        check("Fri 11-20, 6 days quiet: the keep-alive sends ONE 'TODAY is the last safe day'; ops_checks and pc_guard stay "
              "quiet while it covers the account, and warn as before when it does not (the bot down)",
              len(today) == 1 and n_ops is None and n_ops_down is not None and not q_cov and len(q_down) == 1,
              (len(today), n_ops, n_ops_down, q_cov, q_down))
        row = {"key": "zlarior", "label": "Zlarior 50K", "name": "Zlarior 50K", "stage": "eval", "balance": 49000.0, "_src": card}
        need_cov = [n for n in MB.accounts_line([row])[1] if "without a trade" in n]
        need_down = [n for n in MB.accounts_line([{**row, "_src": {**card, "keepalive": {"cover": False}}}])[1]
                     if "without a trade" in n]
        check("the morning brief: no '6 days without a trade: 1 MNQ by hand' line while the keep-alive covers the account, "
              "the line as before without it", not need_cov and len(need_down) == 1, (need_cov, need_down))
        blk = {"t": now, "on": {}, "last": {"lit": "2026-11-20"}, "cover": [], "lane": {"lit": "lit"}}
        lit = LB.lit_now({"acct": {"trades": [{"day": "2026-11-14"}], "eval": {"start": "2026-10-19"}}, "keepalive": blk}, [],
                         ts(2026, 11, 22, 10))
        lit0 = LB.lit_now({"acct": {"trades": [{"day": "2026-11-14"}], "eval": {"start": "2026-10-19"}}}, [], ts(2026, 11, 22, 10))
        n2 = OC.inactivity_notice({**view, "keepalive": blk, "trades": [{"day": "2026-11-14"}]}, ts(2026, 11, 22, 10))
        check("after a keep-alive Fri 11-20 (last strategy trade 11-14): the board's quiet days say 2 (not 8; the morning brief "
              "and pc_guard read them), ops_checks says nothing on Sun 11-22; without the block: 8 as before",
              lit["quiet_days"] == 2 and lit["keepalive"]["last"] == "2026-11-20" and lit0["quiet_days"] == 8
              and "keepalive" not in lit0 and n2 is None, (lit.get("quiet_days"), lit0.get("quiet_days"), n2, need_cov))
    finally:
        K.ALERT_HOOK = None
        env.done()
    from engine import account_b as AB
    tmp = tempfile.mkdtemp(prefix="le_keepalive_cover_")
    try:
        b = types.SimpleNamespace(state_path=os.path.join(tmp, "live_state.json"))
        pushes = []
        fake = types.SimpleNamespace(bot=b, spec={"eval_start": "2026-11-10"}, prov={}, funded=lambda: True, problem=None,
                                     adapter=None, notified=[], name="Sim102", label="ATLAS 25K",
                                     idle_days=lambda now: 6, eval_view=lambda now=None: {"status": "funded"},
                                     log=lambda *a, **k: None, _push_text=lambda *a: pushes.append(a))
        b.acct_b = fake
        now = ts(2026, 11, 20, 10)
        K.save_state({"v": 1, "acc": {}, "sent": [], "notes": {}, "log": [], "cover": {"t": now, "keys": ["atlas"]}},
                     K.state_path_for(b))
        AB.AccountB._idle_check(fake, now)
        n_cov = len(pushes)
        K.save_state({"v": 1, "acc": {}, "sent": [], "notes": {}, "log": [], "cover": {"t": now - 3600, "keys": ["atlas"]}},
                     K.state_path_for(b))
        fake.notified = []
        AB.AccountB._idle_check(fake, now)
        check("account_b's own 7-day push: quiet while the keep-alive covers ATLAS, sent as before when its cover is an hour "
              "old (the bot's keep-alive stopped)", n_cov == 0 and len(pushes) == 1, (n_cov, pushes))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ r. the entry / result straight to ntfy
def t_instant():
    print("r. the keep-alive's entry and result also go straight to ntfy (round 1, LOW)", flush=True)
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now)
        replay(env, bot, ts(2026, 11, 20, 15, 30), ts(2026, 11, 20, 15, 40))
        pr = [p for k, p in env.alerts if k == "problem"]
        ent = [p for p in pr if p.get("title", "").startswith("Keep-alive on Zlarior 50K: BUY 1 MNQ @")]
        res = [p for p in pr if p.get("title", "").startswith("Keep-alive on Zlarior 50K: closed LONG about -$2.40")]
        check("engine/notify.instant_problem gets 'Keep-alive on Zlarior 50K: BUY 1 MNQ @ 26,380.00' (stop / target, closes in "
              "about 2 min) and '... closed LONG about -$2.40' (next trade due by 11-27), each once, besides the trade alert",
              len(ent) == 1 and "about 2 min" in ent[0]["body"] and len(res) == 1 and "due by 2026-11-27" in res[0]["body"]
              and ent[0]["key"].startswith("ka:entry:lit:") and res[0]["key"].startswith("ka:result:lit:")
              and len([1 for k, p in env.alerts if k == "trade"]) == 1, [p.get("title") for p in pr])
        check("the hold fits the window: an entry at 15:47:00 fits (flat by 15:50), 15:47:30 does not; a half day "
              "(Thanksgiving, cut 12:45): 12:42:00 fits, 12:42:30 not",
              K.fits(ts(2026, 11, 20, 15, 47), 120) and not K.fits(ts(2026, 11, 20, 15, 47, 31), 120)
              and K.fits(ts(2026, 11, 26, 12, 42), 120) and not K.fits(ts(2026, 11, 26, 12, 42, 31), 120))
    finally:
        K.ALERT_HOOK = None
        env.done()


# ------------------------------------------------------------------------------------------------ s. a restart on a later day
def restart_bot(env, ad, ka, t, ledger=None, eval_start="2026-10-19"):
    """A real LiveBot started at `t` on the same state file (a new process: the state file + keepalive_state.json only)."""
    env.now[0] = t
    b = live_bot(env.tmp, env.now, ad, ka=ka)
    b.cfg["eval_start"] = eval_start
    if ledger is not None:
        b.ledger = ledger
        b._save_state()
        return b
    b._restore()
    b.state["eval_life"] = {"status": "open", "balance": 49193.0, "floor": 48168.0, "room": 1025.0, "target_balance": 53000.0,
                            "days_traded": 5}
    b._startup_ok = 1
    return b


def t_restart_days():
    print("s. a restart on a later day keeps the fill days (skeptic round 2, HIGH)", flush=True)
    for on in (False, True):
        env = Env()
        hook(env)
        try:
            ad = env.adapter()
            ka = {"accounts": {"lit": on}}
            restart_bot(env, ad, ka, ts(2026, 11, 18, 16, 30), ledger=fill_rows("2026-11-18", -50.0))   # Wed: LIT filled
            b2 = restart_bot(env, ad, ka, ts(2026, 11, 19, 9))                  # Thu 09:00: START BOT / PC update / crash
            g = K.targets(b2)[0]
            last = K.last_known(b2, g)
            out = replay(env, b2, ts(2026, 11, 19, 9, 25), ts(2026, 11, 19, 16, 10))
            check(f"switch {'ON' if on else 'OFF'}: LIT filled Wed 11-18, the bot restarted Thu 11-19 (its ledger is not restored "
                  "on a new day): the last trade is still 11-18 (the saved ledger's fills, LiveBot._ka_seed), no 'TODAY is the "
                  "last safe day' push, no keep-alive order on Thu (was: 'no trade for 32 days' + a REAL BUY 1 MNQ)",
                  last[0] == "2026-11-18" and not last[2] and not env.entries() and not out
                  and not [p for _, p in env.alerts if "TODAY" in p.get("title", "") or "Keep-alive" in p.get("title", "")],
                  (last, out, env.entries(), [p.get("title") for _, p in env.alerts]))
        finally:
            K.ALERT_HOOK = None
            env.done()
    env = Env()
    hook(env)
    try:
        ad = env.adapter()
        ka = {"accounts": {}}
        b1 = restart_bot(env, ad, ka, ts(2026, 11, 18, 16, 30), ledger=fill_rows("2026-11-18", -50.0))
        b1.state["eval_life"] = {"status": "open", "balance": 49193.0, "floor": 48168.0, "room": 1025.0}
        K.tick(b1, env.now[0], px=PX, bar_t=env.now[0] - 62)          # one poll after the fill: kept in keepalive_state.json
        kept = K.load_state(K.state_path_for(b1))["acc"].get("lit", {}).get("fills")
        restart_bot(env, ad, ka, ts(2026, 11, 19, 9), ledger=[])          # Thu: a restart, then the bot saved an empty ledger
        b3 = restart_bot(env, ad, ka, ts(2026, 11, 20, 9))                # Fri: a 2nd restart: the saved ledger has no fill now
        last = K.last_known(b3, K.targets(b3)[0])
        out = replay(env, b3, ts(2026, 11, 20, 9, 25), ts(2026, 11, 20, 16, 10))
        check("two restarts (Thu, Fri) after the Wed fill: the state file kept the fill day (acc.lit.fills), last trade 11-18, "
              "no warning Fri (MFFU's limit Wed 11-25)", kept == ["2026-11-18"] and last[0] == "2026-11-18" and not out
              and not env.alerts, (kept, last, out, [p.get("title") for _, p in env.alerts]))
        check("... and the heartbeat block / the other warners see it: last_day('lit') = 2026-11-18",
              K.last_day(b3, "lit") == "2026-11-18" and K.hb_block(b3)["last"].get("lit") == "2026-11-18", K.hb_block(b3))
    finally:
        K.ALERT_HOOK = None
        env.done()
    from engine import multi_account as MA
    a = types.SimpleNamespace(spec={"nt_account": "Sim104"}, closes=[], ledger=[], lock=None)
    t = ts(2026, 11, 24, 10)
    blob = {"nt_account": "Sim104", "day": "2026-11-24", "ledger": [{"t": t, "side": "buy", "entry_t": t - 60, "result": {"ok": True}}],
            "closes": [["2026-11-24", t, -40.0]]}
    MA.Account.restore(a, blob, "2026-11-30")                             # the bot restarted on Mon 11-30
    check("an extra account (the 25K #2) restored on a later day: its ledger is not, its fill day is (Account._ka_seed)",
          a.ledger == [] and K._lane_days("extra", a, None) == {"2026-11-24"}, (a.ledger, getattr(a, "_ka_seed", None)))


# ------------------------------------------------------------------------------------------------ t. a stale heartbeat
def t_stale_cover():
    print("t. a stale heartbeat never covers: with the bot down the old warnings come back (skeptic round 2, HIGH)", flush=True)
    from engine import live_board as LB, ops_checks as OC
    from tools import morning_brief as MB
    from tests import test_ops as TO
    last_hb = ts(2026, 11, 20, 16, 0)                       # the bot's last heartbeat: Fri 16:00 (down after the update)
    now = ts(2026, 11, 23, 8, 0)                            # Mon 08:00, 7 days after the last trade Mon 11-16
    blk = {"t": last_hb - 60, "on": {}, "last": {}, "cover": ["lit"], "lane": {"lit": "lit"}}
    h = TO.hb(last_hb + 60, trades=[{"day": "2026-11-16", "entry_t": ts(2026, 11, 16, 10), "pnl": -129.4}], start="2026-10-19")
    h["keepalive"] = blk
    v = OC.account_view(h, now)
    n_stale = OC.inactivity_notice(v, now)
    h2 = dict(h, keepalive=dict(blk, t=now - 120))
    n_fresh = OC.inactivity_notice({**OC.account_view(h2, now), "fresh": True}, now)
    check("ops_checks (its own 5-min task): the heartbeat block is 2.7 days old -> 'No trade for 7 days (MFFU closes an "
          "account at 7)' as before (was: silent); a fresh block from a running bot still covers",
          n_stale is not None and "No trade for 7 days" in n_stale["title"] and n_fresh is None, (v.get("fresh"), n_stale, n_fresh))
    check("hb_covers: the same block covers 'lit' at 16:05 Fri, not at 08:00 Mon",
          K.hb_covers(blk, "lit", last_hb + 300) and not K.hb_covers(blk, "lit", now))
    card = LB._ka_card({"keepalive": blk}, "lit", now)
    card_live = LB._ka_card({"keepalive": blk}, "lit", last_hb + 300)
    lit = LB.lit_now({"acct": {"trades": [{"day": "2026-11-16"}], "eval": {"start": "2026-10-19"}}, "keepalive": blk}, [], now)
    check("the board card (pc_guard, the morning brief): cover False on Mon (block 2.7 days old), True while the bot runs",
          card["cover"] is False and card_live["cover"] is True and lit["keepalive"]["cover"] is False, (card, card_live))
    src = {"id": "lit", "quiet_days": 7, "keepalive": {"key": "lit", "cover": True}}
    row = {"key": "zlarior", "label": "Zlarior 50K", "name": "Zlarior 50K", "stage": "eval", "balance": 49000.0, "_src": src}
    down = [n for n in MB.accounts_line([row], hb_fresh=False)[1] if "without a trade" in n]
    up = [n for n in MB.accounts_line([row], hb_fresh=True)[1] if "without a trade" in n]
    check("the morning brief with the bot's last report old: 'Zlarior 50K 7 days without a trade: 1 MNQ by hand' again "
          "(was: dropped); with a fresh report the keep-alive's cover still holds", len(down) == 1 and not up, (down, up))


# ------------------------------------------------------------------------------------------------ u. hand trades in NinjaTrader's Log
def nt_log(env, day, lines):
    d = os.path.join(env.folder, "log")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"log.{day.replace('-', '')}.00000.txt"), "a", encoding="utf-8") as fh:
        for ln in lines:
            fh.write(ln + "\n")


def exec_line(day, hhmm, acct, px=PX):
    return (f"{day} {hhmm}:11:123|1|8|Execution='{abs(hash((day, hhmm, acct))) % 10 ** 12}_1' Instrument='MNQ 12-26' "
            f"Account='{acct}' Exchange=Globex Price={px} Quantity=1 Market position=Long Operation=Operation_Add")


def t_hand_trades():
    print("u. the owner's hand trades are seen in NinjaTrader's Log, nothing to type (skeptic rounds 1 + 2, LOW)", flush=True)
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now)                       # switch ON, last fill Mon 11-16: due Fri 11-20
        nt_log(env, "2026-11-20", ["2026-11-20 10:05:00:001|1|8|OIF, 'PLACE;Sim101;MNQ 12-26;BUY;1;MARKET' (not a fill)",
                                   exec_line("2026-11-20", "10:05", "Sim999"),          # another account
                                   exec_line("2026-11-20", "13:20", "Sim101")])         # the owner's hand trade at 13:20
        out = replay(env, bot, ts(2026, 11, 20, 13, 30), ts(2026, 11, 20, 16, 20))
        g = K.targets(bot)[0]
        days, _ = K.account_days(bot, g)
        check("an 'Execution=' line for Sim101 at 13:20 Fri (the owner's 1 MNQ by hand): counted, so NO keep-alive at 15:33; "
              "another account's line and an order line count nothing",
              "2026-11-20" in days and not env.entries() and not [x for x in out if x.get("do") == "open"]
              and K.nt_exec_days(env.folder, "Sim999", env.now[0]) == {"2026-11-20"}, (sorted(days), out))
        st = K.load_state(K.state_path_for(bot))
        check("... kept in the state file (it survives a restart) and the heartbeat block carries it (the board's quiet days, "
              "ops_checks)", "2026-11-20" in st["acc"]["lit"].get("fills", []) and K.hb_block(bot)["last"]["lit"] == "2026-11-20",
              st["acc"].get("lit"))
    finally:
        K.ALERT_HOOK = None
        env.done()
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now, ka={"accounts": {}})
        nt_log(env, "2026-11-20", ["2026-11-20 08:00:00:001|1|0|startup line"])
        replay(env, bot, ts(2026, 11, 20, 9, 25), ts(2026, 11, 20, 10))
        n1 = len([p for _, p in env.alerts if "TODAY" in p.get("title", "")])
        nt_log(env, "2026-11-20", [exec_line("2026-11-20", "10:01", "Sim101")])      # appended later: read incrementally
        replay(env, bot, ts(2026, 11, 20, 10), ts(2026, 11, 21, 10))
        p = K.plan(K.last_known(bot, K.targets(bot)[0])[0], ts(2026, 11, 21, 10))
        check("switch OFF: the 09:30 'TODAY is the last safe day' (once), the hand trade 10:01 appended to the log is read on a "
              "later scan; the next act day moves to Thu 11-26's week (MFFU's limit Fri 11-27), no more warnings",
              n1 == 1 and p["hard"] == "2026-11-27" and len([x for _, x in env.alerts if "TODAY" in x.get("title", "")]) == 1, p)
        body = next(x["body"] for _, x in env.alerts if "TODAY" in x.get("title", ""))
        check("the push says no PC step is needed (the bot reads NinjaTrader's log); --traded only as the PC fallback",
              "NinjaTrader's log by itself" in body and "--traded lit" in body, body)
    finally:
        K.ALERT_HOOK = None
        env.done()
    relog = ("2026-11-23 10:31:02:004|1|8|Execution='9_1' Instrument='MNQ 12-26' Account='Sim101' Price=26380 Quantity=1 "
             "Market position=Long Operation=Operation_Add Time='11/22/2026 7:05:11 PM' Statement date='2026-11-23'")
    check("a log line's day is never later than its ET date; an execution logged again the next day (a reconnect) keeps "
          "its own day (Time='11/22/2026 7:05:11 PM' -> 11-22); a malformed line counts nothing",
          K._exec_line(exec_line("2026-11-20", "10:01", "Sim101"))[0] == "Sim101"
          and K._exec_line(exec_line("2026-11-20", "10:01", "Sim101"))[1] <= "2026-11-20"
          and K._exec_line(relog) == ("Sim101", "2026-11-22")
          and K._exec_line("garbage Execution= Account='x'") is None, K._exec_line(relog))


# ------------------------------------------------------------------------------------------------ v. the refusal push is retried
def t_refusal_retry():
    print("v. 'did not go through: place 1 MNQ by hand' is retried until 16:05 when ntfy refuses it (skeptic round 2, LOW)",
          flush=True)
    from engine import entry_pause
    old_alert = K._alert
    for answers, want in ((["ntfy refused"], [947.5, 952.5]), ([], None)):
        env = Env()
        tries = []
        try:
            def flaky(bot, kind, p, answers=answers):
                if str(p.get("key", "")).startswith("ka:refused:"):
                    tries.append(K._mod(env.now[0]) + (env.now[0] % 60) / 60.0)
                    if want is None:
                        return "ntfy refused"
                    return answers.pop(0) if answers else "sent"
                return "sent"
            K._alert = flaky
            K.SYNC_ALERTS = True
            bot = Bot(env.tmp, env.adapter(), env.now)                    # ON, due today; the owner's pause blocks it
            entry_pause.set_pause("tomorrow", now=ts(2026, 11, 20, 9), path=entry_pause.path_for(bot))
            for t in range(ts(2026, 11, 20, 15, 30), ts(2026, 11, 20, 16, 20), 30):
                poll(env, bot, t)
            st = K.load_state(K.state_path_for(bot))
            if want is not None:
                check("ntfy refuses the 15:47:30 push: kept for a retry, sent 5 min later (15:52:30), recorded, never again",
                      tries == want and "ka:refused:lit:2026-11-20" in st["sent"] and not st.get("retry"), (tries, st.get("retry")))
            else:
                check("ntfy refuses every try: 15:47:30, 15:52:30, 15:57:30, 16:02:30, then no more (16:05 is the hand-trade "
                      "time); no order", tries == [947.5, 952.5, 957.5, 962.5] and not env.entries(), tries)
        finally:
            K._alert = old_alert
            K.SYNC_ALERTS = False
            env.done()
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now)
        entry_pause.set_pause("tomorrow", now=ts(2026, 11, 20, 9), path=entry_pause.path_for(bot))
        replay(env, bot, ts(2026, 11, 20, 15), ts(2026, 11, 20, 16, 20))
        told = [p for _, p in env.alerts if "did not go through" in p.get("title", "")]
        check("the push: 'Place 1 MNQ by hand on this account before 16:05 ET' (a half day: 5 min before the halt)",
              len(told) == 1 and "before 16:05 ET" in told[0]["body"] and K.hand_by("2026-11-26") == 12 * 60 + 55,
              [p.get("body") for p in told])
    finally:
        K.ALERT_HOOK = None
        env.done()


# ------------------------------------------------------------------------------------------------ w. the CLI + the bot's save
def t_cli_safety():
    print("w. the CLI refuses an unknown key / a future --start; the bot's save keeps a --traded written meanwhile (round 2, LOW)",
          flush=True)
    tmp = tempfile.mkdtemp(prefix="le_keepalive_cli_")
    old_sp, old_cp = K.state_path_for, K.CONFIG_PATH
    try:
        p = os.path.join(tmp, "keepalive_state.json")
        K.state_path_for = lambda bot=None: p
        K.CONFIG_PATH = os.path.join(tmp, "keepalive.json")
        outs = []
        for argv in (["--traded", "x:b25k2"], ["--on", "zlarior", "--yes"], ["--start", "x:b25k_2", "2099-01-01"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                outs.append((K.main(argv), buf.getvalue()))
        check("refused, nothing written: --traded x:b25k2 (a typo of x:b25k_2), --on zlarior, --start with a future day",
              all(rc == 2 and "NOT changed" in o for rc, o in outs) and not os.path.exists(p)
              and not os.path.exists(K.CONFIG_PATH), outs)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = K.main(["--traded", "x:b25k_2"])
        check("a known key still works (x:b25k_2, lit, atlas, rapid)", rc == 0 and {"lit", "atlas", "rapid", "x:b25k_2"} <= K.known_keys(p),
              buf.getvalue())
        # KEEPALIVE_ON.bat / tools/bat/KEEPALIVE_OFF.bat (owner's yes 2026-11-20): --on all needs --yes, then every known account
        outs = []
        for argv in (["--on", "all"], ["--on", "all", "--off", "lit", "--yes"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                outs.append((K.main(argv), buf.getvalue()))
        check("--on all without --yes / --on with --off: refused, nothing written",
              all(rc == 2 for rc, _ in outs) and not os.path.exists(K.CONFIG_PATH)
              and "REAL 1-MNQ" in outs[0][1] and "NOT changed" in outs[1][1], outs)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = K.main(["--on", "all", "--yes"])
        acc = K.load_config(None)["accounts"]
        want = K.known_keys(p)
        check("--on all --yes: every known account ON (lit, atlas, rapid, x:b25k_2)",
              rc == 0 and {"lit", "atlas", "rapid", "x:b25k_2"} <= set(acc) and all(acc.get(k) is True for k in want),
              (buf.getvalue(), acc))
        with redirect_stdout(io.StringIO()):
            rc = K.main(["--off", "all"])
        acc = K.load_config(None)["accounts"]
        check("--off all (no --yes needed): every account OFF", rc == 0 and acc and not any(acc.values()), acc)
        bats = {}
        for b in ("KEEPALIVE_ON.bat", "tools/bat/KEEPALIVE_OFF.bat"):
            with open(os.path.join(ROOT, b), "rb") as fh:
                bats[b] = fh.read()
        on = bats["KEEPALIVE_ON.bat"].decode()
        check("KEEPALIVE_ON.bat: CRLF, shows the cost first (--on all without --yes), only the typed phrase KEEP ALIVE ON "
              "runs --on all --yes; anything else changes nothing",
              all(b"\r\n" in v and b"\n" not in v.replace(b"\r\n", b"") for v in bats.values())
              and on.index("engine.keepalive --on all\r") < on.index('"KEEP ALIVE ON"') < on.index("--on all --yes")
              and on.count("--yes") == 1 and 'if /i not "!OK!"=="KEEP ALIVE ON" goto :no' in on
              and "EnableDelayedExpansion" in on, on[:300])   # delayed expansion: a typed quote never breaks the if (red-team 2026-11-21)
        check("tools/bat/KEEPALIVE_OFF.bat: --off all, never --on", "engine.keepalive --off all" in bats["tools/bat/KEEPALIVE_OFF.bat"].decode()
              and "--on" not in bats["tools/bat/KEEPALIVE_OFF.bat"].decode())
    finally:
        K.state_path_for, K.CONFIG_PATH = old_sp, old_cp
        shutil.rmtree(tmp, ignore_errors=True)
    now = ts(2026, 11, 20, 10)
    check("a future MFFU start is ignored even with no lane start of its own (it would drop every earlier fill); the Rapid "
          "counts from its purchase Thu 11-19 (START_DEFAULTS) when added within 7 days",
          K._start_override({"start": {"x:new": "2026-11-25"}}, "x:new", None, now) is None
          and K._start_override({}, "rapid", "2026-11-23", ts(2026, 11, 23, 10)) == "2026-11-19"
          and K._start_override({}, "rapid", "2026-12-01", ts(2026, 12, 1, 10)) == "2026-12-01")
    env = Env()
    try:
        bot = Bot(env.tmp, env.adapter(), env.now)
        sp = K.state_path_for(bot)
        K.save_state({"v": 1, "acc": {}, "sent": [], "notes": {}, "log": []}, sp)
        b = K._book(bot)
        b["st"]["acc"]["lit"] = {"fills": ["2026-11-16"]}                 # the bot's tick, in memory
        K.mark_traded("lit", "2026-11-19", path=sp, now=ts(2026, 11, 20, 10))   # the owner's --traded in another window
        K._save_book(bot, b)                                               # the bot saves its tick
        st = K.load_state(sp)
        check("--traded written while a bot tick ran: the bot's save keeps it (marked 11-19) and its own change (fills)",
              st["acc"]["lit"].get("marked") == "2026-11-19" and st["acc"]["lit"].get("fills") == ["2026-11-16"], st["acc"])
    finally:
        env.done()


# ------------------------------------------------------------------------------------------------ x. the rest of the owner's stops
def t_more_stops():
    print("x. the rest of the owner's stops (presence check-in, ai_watch) and LIT's soft daily loss block it (round 2, LOW)",
          flush=True)
    env = Env()
    try:
        t_in = ts(2026, 11, 20, 15, 33, 2)
        res = []
        for mut in (lambda b: b.cfg.update(guards={"presence_required": True, "presence_hours": 12}),
                    lambda b: setattr(b, "day_pnl_routed", lambda: -1200.0),
                    lambda b: None):
            bot = Bot(env.tmp, env.adapter(), env.now)
            bot._note_error = lambda *a, **k: None
            mut(bot)
            g = K.targets(bot)[0]
            env.now[0] = t_in
            res.append(K._gate(bot, g, "mffu_builder_50k", t_in, PX, t_in - 62, K.load_config(bot)))
        check("presence_required with no check-in -> 'your stop blocks the keep-alive (no check-in ...)'; today's routed P&L "
              "-$1,200 -> 'LIT's soft daily loss'; neither -> the gate passes",
              "your stop blocks the keep-alive (no check-in" in str(res[0]) and "LIT's soft daily loss" in str(res[1])
              and isinstance(res[2], dict), res)
    finally:
        env.done()


# ------------------------------------------------------------------------------------------------ y. the push words
def t_words():
    print("y. the push words (round 2, LOW)", flush=True)
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now)
        replay(env, bot, ts(2026, 11, 20, 9, 25), ts(2026, 11, 20, 9, 40))
        hu = next((p for _, p in env.alerts if "Keep-alive today" in p.get("title", "")), {})
        check("ON heads-up: 'buys 1 MNQ at 15:33 ET (or sells, the side an open account holds)'",
              "(or sells, the side an open account holds)" in hu.get("body", ""), hu)
    finally:
        K.ALERT_HOOK = None
        env.done()
    env = Env()
    hook(env)
    try:
        bot = Bot(env.tmp, env.adapter(), env.now, ka={"accounts": {}})
        replay(env, bot, ts(2026, 11, 19, 9, 25), ts(2026, 11, 19, 9, 40))
        eve = next((p for _, p in env.alerts if "next session" in p.get("title", "")), {})
        check("OFF 'the next session is the last safe day': '... or turn the keep-alive on: KEEPALIVE_ON.bat on the PC' "
              "(owner 2026-11-20: no MFFU contact)", "or turn the keep-alive on: KEEPALIVE_ON.bat on the PC." in eve.get("body", ""), eve)
    finally:
        K.ALERT_HOOK = None
        env.done()
    doc = " ".join((K.__doc__ or "").split())
    check("the docstring quotes Terms 12.4 as written (12.4.2 'smaller or larger numbers of positions') and qualifies the "
          "half day + 'never refused'", "12.4.2" in doc and "smaller or larger numbers of positions" in doc
          and "substantially smaller ... positions" not in doc and "a real trade is never refused" not in doc
          and "on a half day LIT can" in doc)


def t_redteam_1121():
    """Red-team 2026-11-21: only REAL broker fills count (never a paper lane's or a Sim101 test's 'ok' row), and --off all also
    clears a key only the config still names."""
    t0 = int(dt.datetime(2026, 11, 19, 10, 0, tzinfo=ZoneInfo("America/New_York")).timestamp())
    real = {"side": "buy", "t": t0 - 3 * 86400, "result": {"ok": True, "adapter": "ninjatrader", "account": "MFFUEVTEST001"}}
    paper = {"side": "buy", "t": t0, "result": {"ok": True, "adapter": "paper"}}
    sim = {"side": "sell", "t": t0, "result": {"ok": True, "adapter": "ninjatrader", "account": "Sim101"}}
    other = {"side": "sell", "t": t0, "result": {"ok": True, "adapter": "ninjatrader", "account": "MFFUEVOTHER02"}}
    days = K._fill_days([real, paper, sim])
    check("red-team 11-21: a paper row and a Sim101 row are NOT MFFU fills (only the real Monday fill counts)",
          days == {K._cal(real["t"])}, sorted(days))
    check("red-team 11-21: with the target's account given, a fill on ANOTHER NinjaTrader account is left out",
          K._fill_days([real, other], "MFFUEVTEST001") == {K._cal(real["t"])} and len(K._fill_days([real, other])) == 2)
    check("red-team 11-21: the restart seed ignores paper / Sim101 rows too", K.seed_days([paper, sim]) == set())
    tmp = tempfile.mkdtemp()
    try:
        cfg = os.path.join(tmp, "keepalive.json")
        old = getattr(K, "CONFIG_PATH", None)
        import json as _j
        with open(cfg, "w", encoding="utf-8") as fh:
            _j.dump({"accounts": {"lit": True, "x:gone_acct": True}}, fh)
        if old is not None:
            K.CONFIG_PATH = cfg
            try:
                with redirect_stdout(io.StringIO()):
                    rc = K.main(["--off", "all"])
                after = _j.load(open(cfg, encoding="utf-8"))["accounts"]
                check("red-team 11-21: --off all (tools/bat/KEEPALIVE_OFF.bat) also turns OFF a key only the config still names",
                      rc == 0 and after.get("x:gone_acct") is False and after.get("lit") is False, after)
            finally:
                K.CONFIG_PATH = old
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    t_plan()
    t_one()
    t_nothing()
    t_off()
    t_restart()
    t_windows()
    t_hedge()
    t_rules()
    t_misc()
    t_owner_stops()
    t_fills()
    t_traded()
    t_start()
    t_alerts()
    t_key_for()
    t_live_bot()
    t_one_place()
    t_instant()
    t_restart_days()
    t_stale_cover()
    t_hand_trades()
    t_refusal_retry()
    t_cli_safety()
    t_more_stops()
    t_words()
    t_redteam_1121()
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
