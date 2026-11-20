"""MFFU 7-day keep-alive trade (engine/keepalive.py, OFF by default), replayed on the simulated NinjaTrader (engine.ninjatrader
._FakeNT) through real NinjaTraderAdapter instances on Sim accounts. Temp dirs only; no phone, no order leaves the machine.

    python -X utf8 -m tests.test_keepalive

  a. the plan: the last full CME session on or before last trade + 6 (Zlarior 50K last traded Mon 11-16 -> Fri 11-20),
     Thanksgiving / Christmas weeks, past the deadline (the next session), the windows (15:33-15:48, half days before the cut)
  b. replay, switch ON, quiet since Mon 11-16: exactly ONE keep-alive (1 MNQ at 15:33, closed ~30 s later, flat, nothing
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
class Bot:
    """What engine/keepalive reads from engine/live.LiveBot (the primary LIT account = Zlarior 50K eval)."""

    def __init__(self, tmp, ad, now, ka=None, days=None, name="Sim101"):
        self.cfg = {"sym": "NQ", "adapter": "ninjatrader", "nt_account": name, "model": "lit",
                    "keepalive": {"accounts": {"lit": True}} if ka is None else ka}
        self.state_path = os.path.join(tmp, "live_state.json")
        self.state = {"model": "lit", "eval_life": {"status": "open", "balance": 49193.0, "floor": 48168.0, "room": 1025.0,
                                                    "target_balance": 53000.0, "days_traded": 5}}
        self.adapter = ad
        self.ledger = []
        self.kill = False
        self.health = {}
        self.bars_tail = [{"time": 0, "close": PX}]
        self.days = dict({"2026-11-16": -129.4} if days is None else days)
        self._now = now
        self.logs = []
        self.acct_b = self.acct_r = self.acct_c = self.accts = self.fleet = None
        self._open_routed = None

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
        check("closed at market 30 s later (CLOSEPOSITION), NinjaTrader flat, no stop / target left working",
              len(closes) == 1 and closes[0]["t"] - opens[0]["t"] == 30 and env.flat(ad) and not env.working("Sim101")
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
        check("the keep-alive never wrote to the strategy's ledger (no stats, no sizing, no audit change)", bot.ledger == [], bot.ledger)
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
    cases = [("a real trade today (LIT exit booked 11-20)", lambda b: b.days.update({"2026-11-20": 312.0})),
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
        r = K.mark_traded("x:b25k_2", "2026-11-23", path=K.state_path_for(b))
        check("--traded x:b25k_2 2026-11-23 notes a hand trade (the clock restarts from it)",
              r["marked"] == "2026-11-23" and K.last_day(b, "x:b25k_2") == "2026-11-23", r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    check("LiveBot wiring: _keepalive_tick after the routing (with the poll's 1m close) and a manage-only call after the "
          "adapters' ticks; multi_account.opposite_open asks keepalive.opposite",
          "self._keepalive_tick(df1, now)" in src and "self._keepalive_tick(None, now, may_open=False)" in src
          and "_ka.opposite(self.bot, d)" in open(os.path.join(ROOT, "engine", "multi_account.py"), encoding="utf-8").read())
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
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
