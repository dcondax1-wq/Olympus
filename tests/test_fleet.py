"""The fleet (engine/fleet.py): in-house copy trading of Zlarior / ATLAS / BLITZ to follower accounts at any firm, Sim or
real, and the owner's personal LIVE account. Temp dirs only: never the real data/, .env.local.ps1, second_model.json or
live_model*.json; paper / recording adapters, no NinjaTrader, nothing armed.

    python -X utf8 -m tests.test_fleet            # unit checks + a LiveBot replay of 3 October sessions with followers (~2 min)
    python -X utf8 -m tests.test_fleet --quick    # unit checks only (~5 s)

Covers: OFF = nothing built and no payload key; copy sizing per account (Zlarior two_week eval sizing on each plan, funded,
fixed $ risk, the LIVE account's own stops); the firm caps (contracts, floor, daily loss); fleet-wide anti-hedge incl.
accounts B / C and the extra accounts (a follower never opposite any account; a lead entering against a follower closes it
first; ATLAS held back by a Zlarior follower); a refused order on one follower (nothing booked, the others trade); kill per
account / fleet-wide / the bot's kill switch; the live gate for a real follower; stagger; slippage vs the lead fill;
lifecycle (passed / failed / payout ready pushes); persistence across a restart; the heartbeat block (< 6 KB); the API;
the CLI on a temp file; the LiveBot replay (the primary's ledger identical with and without the fleet).
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import fleet as FL  # noqa: E402
from engine import firms as FM  # noqa: E402
from engine.ninjatrader import LIVE_ENV  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
DAY = "2026-10-21"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)
    return bool(ok)


def ts(day, hh, mm=0, ss=0):
    y, m, d = (int(x) for x in day.split("-"))
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


class Rec:
    """A recording adapter: paper-like (name "paper") or broker-like (route_stop_moves / route_all_exits, fills in legs)."""

    def __init__(self, cfg, broker=False, refuse=False, fill_off=0.0):
        self.cfg, self.sent, self.refuse, self.fill_off = cfg, [], refuse, fill_off
        self.name = "ninjatrader" if broker else "paper"
        self.route_stop_moves = self.route_all_exits = broker
        self.legs = []
        self.disabled = None

    def send(self, a):
        self.sent.append(dict(a))
        if self.refuse and a.get("side") in ("buy", "sell"):
            return {"ok": False, "error": "REJECTED: account disabled by the broker"}
        if a.get("side") in ("buy", "sell"):
            d = 1 if a["side"] == "buy" else -1
            self.legs.append({"entry_t": a["entry_t"], "fill_px": float(a["entry"]) + d * self.fill_off, "filled": True})
        return {"ok": True}


class Lead:
    """A stand-in for account B / C (ledger, closes, open_t, prov)."""

    def __init__(self, name):
        self.name, self.ledger, self.closes, self.open_t, self.prov, self.adapter = name, [], [], None, {}, None

    def enter(self, t, d, qty, entry, stop, target, ok=True):
        self.ledger.append({"t": t, "sym": "NQ", "side": "buy" if d == 1 else "sell", "qty": qty, "entry": entry, "stop": stop,
                            "target": target, "entry_t": t, "result": {"ok": ok}})
        if ok:
            self.open_t = t
            self.prov[t] = {"dir": d, "qty": qty}

    def exit(self, t, pnl, reason="TARGET"):
        et_ = self.open_t
        self.ledger.append({"t": t, "sym": "NQ", "side": "exit", "qty": self.prov[et_]["qty"], "reason": reason, "entry_t": et_, "result": {"ok": True}})
        self.closes.append([FL.trading_day(t), t, float(pnl), et_])
        self.open_t = None

    def closing_open(self):
        return []


class Bot:
    def __init__(self, tmp, now, cfg=None):
        self.cfg = {"adapter": "paper", "sym": "NQ", "nt_account": "Sim101", **(cfg or {})}
        self.state_path = os.path.join(tmp, "live_state.json")
        self.ledger, self._open_routed, self._open_src = [], None, None
        self.state = {"price": 20000.0}
        self.kill = False
        self.started_at = now - 3600
        self.adapter, self.acct_b, self.acct_c, self.accts = None, None, None, None
        try:
            self._lit_sizing = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
        except Exception:
            self._lit_sizing = {}
        self.t = now
        self.logs = []

    def clock(self):
        return self.t

    def _log(self, k, t):
        self.logs.append((k, t))

    def lit_enter(self, d, entry, stop, target, qty=10, ok=True, t=None):
        t = t or self.t
        self.ledger.append({"t": t, "sym": "NQ", "side": "buy" if d == 1 else "sell", "qty": qty, "entry": entry, "stop": stop,
                            "target": target, "entry_t": t, "result": {"ok": ok} if ok else {"ok": False, "error": "refused"}})
        if ok:
            self._open_routed = t
        return t

    def lit_modify(self, stop, t=None):
        self.ledger.append({"t": t or self.t, "sym": "NQ", "side": "modify", "stop": stop, "entry_t": self._open_routed, "result": {"ok": True}})

    def lit_exit(self, pnl, reason="TARGET", qty=10, t=None):
        et_ = self._open_routed
        self.ledger.append({"t": t or self.t, "sym": "NQ", "side": "exit", "qty": qty, "reason": reason, "pnl": pnl, "entry_t": et_,
                            "exit_t": t or self.t, "result": {"ok": True}})
        self._open_routed = None


def make(tmp, accounts, now, bot=None, factory=None, kill=False, **kw):
    b = bot or Bot(tmp, now)
    ads = {}

    def fac(f, cfg):
        ad = (factory or (lambda f_, c_: Rec(c_)))(f, cfg)
        ads[f.id] = ad
        return ad
    notes = []
    fl = FL.Fleet(b, {"accounts": copy.deepcopy(accounts), "kill": kill}, state_path=os.path.join(tmp, "live_state_fleet.json"),
                  adapter_factory=fac, parallel=False, sleep=kw.get("sleep") or (lambda s: None),
                  notify=lambda t, body, k: notes.append((t, body, k))).start()
    b.fleet = fl
    return b, fl, ads, notes


def fol(fl, i):
    return next(f for f in fl.followers if f.id == i)


def ents(ad):
    return [a for a in ad.sent if a.get("side") in ("buy", "sell")]


# ------------------------------------------------------------------------------------------------------------- units
def off_checks(tmp):
    b = Bot(tmp, ts(DAY, 9, 0))
    check("OFF: build() with no block / no accounts -> None (nothing built)", FL.build(b, None) is None and FL.build(b, {"accounts": []}) is None)
    check("OFF: raw_cfg() of a missing data/fleet.json -> None", FL.raw_cfg(os.path.join(tmp, "nope", "fleet.json")) is None)
    from engine import heartbeat as HB
    from engine.live import LiveBot
    lb = LiveBot()
    lb.state_path = os.path.join(tmp, "lb", "live_state.json")
    lb.cfg = {"sym": "NQ", "adapter": "paper"}
    lb._fleet_tick("NQ", ts(DAY, 9, 0))
    check("OFF: LiveBot._fleet_tick with no block leaves bot.fleet None (test harness: no data/fleet.json read)", lb.fleet is None)
    check("OFF: the heartbeat helper gives None (no 'fleet' key)", HB._fleet(lb) is None)
    from engine import live_publish as LP
    lj = LP.build({"running": True, "health": {}}, now=ts(DAY, 9, 0), lm={})
    check("OFF: live.json has no pc.fleet", "fleet" not in (lj.get("pc") or {}))
    src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    check("live.py: every fleet hook is behind getattr(self, 'fleet', None) / self.fleet is None",
          src.count("getattr(self, \"fleet\", None) is not None") >= 4 and "if blk is None and self.fleet is None:" in src)


def copy_checks(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": "luc", "name": "Lucid 50K", "lead": "zlarior", "plan": "lucid_pro_50k", "start": DAY},
           {"id": "m25", "name": "MFFU 25K", "lead": "zlarior", "plan": "mffu_builder_25k", "start": DAY},
           {"id": "fix", "name": "Fixed $200", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY, "sizing": "fixed", "risk_usd": 200},
           {"id": "fun", "name": "Funded 50K", "lead": "zlarior", "plan": "mffu_builder_50k", "stage": "funded", "funded_start": "2026-10-01"},
           {"id": "liv", "name": "My live", "lead": "zlarior", "plan": "live", "start": DAY,
            "live": {"start": 10000, "max_risk_usd": 100, "daily_stop_usd": 250, "weekly_stop_usd": 500, "max_micros": 3}}]
    b, fl, ads, notes = make(os.path.join(tmp, "copy"), acc, now)
    check("5 followers built, all ready", all(f.problem is None and f.adapter is not None for f in fl.followers),
          [(f.id, f.problem) for f in fl.followers])
    b.t = now
    et_ = b.lit_enter(1, 20000.0, 19980.0, 20120.0, qty=30)
    b.t = now + 3
    fl.tick("NQ", b.t)
    q = {i: (ents(ads[i])[0]["qty"] if ents(ads[i]) else 0) for i in ads}
    want = {}
    for f in fl.followers:
        sz = f.size({"sym": "NQ", "entry": 20000.0, "stop": 19980.0, "target": 20120.0}, b.t)
        want[f.id] = sz["qty"]
    check("each follower entered once on the lead's entry", all(len(ents(ads[i])) == 1 for i in ads), q)
    check("same side / stop / target as the lead on every follower", all(ents(ads[i])[0]["side"] == "buy" and ents(ads[i])[0]["stop"] == 19980.0
                                                                       and ents(ads[i])[0]["target"] == 20120.0 for i in ads))
    check("Zlarior two_week sizing differs per plan (Lucid 50K vs MFFU 25K: the 25K's $1,500 target / 20 micros)",
          q["luc"] != q["m25"] and q["m25"] <= 20 and q["luc"] <= 40, q)
    one = (20 + FM.SLIP_PTS) * 2 + FM.COMM
    check("fixed sizing: $200 / $42.90 a micro -> 4", q["fix"] == int(200 // one), q)
    check("LIVE account: fixed $100 risk -> 2 micros, never an eval size", q["liv"] == min(3, int(100 // one)), q)
    check("funded follower sized by the funded rule (60% of the room, <= $1,500) and the firm caps", 0 < q["fun"] <= 40, q)
    f25 = fol(fl, "m25")
    check("the 25K's size fits its $600 soft daily loss at the stop", q["m25"] * one <= 600, q["m25"])
    # the lead's stop move (BE) only reaches broker-style adapters
    b.t += 600
    b.lit_modify(20001.25)
    fl.tick("NQ", b.t)
    check("paper followers: the lead's BE stop is tracked (no modify order needed on paper)", fol(fl, "luc").pos["stop"] == 20001.25)
    # the lead exits: every follower closes and books lead $ per micro x its own micros
    b.t += 900
    b.lit_exit(30 * (120 * 2 - FM.COMM), "TARGET", qty=30)
    fl.tick("NQ", b.t)
    pm = (120 * 2 - FM.COMM)
    got = {f.id: (f.closes[-1][2] if f.closes else None) for f in fl.followers}
    check("every follower closed with the lead and booked the lead's $ a micro x its own micros",
          all(abs(got[i] - round(pm * q[i], 2)) < 0.02 for i in got) and all(f.pos is None for f in fl.followers), (got, q))
    check("a paper follower routes its exit (reason TARGET)", any(a.get("side") == "exit" and a.get("reason") == "TARGET" for a in ads["luc"].sent))
    r = fl.api(b.t)
    check("API rows: firm, plan, stage, balance, room, today's P&L, slippage, warnings per account",
          all(set(("firm", "plan", "stage", "balance", "room", "today", "slip_ticks", "warn")) <= set(x) for x in r["accounts"]), r["accounts"][0])
    real_live = FL.normalize({"id": "x", "plan": "live", "start": DAY, "adapter": "ninjatrader", "nt_account": "MYBROKER-1", "live": {"start": 5000}})
    check("the personal live account is labelled LIVE everywhere (LIVE PAPER on paper, LIVE on a real account; a prop account REAL)",
          fol(fl, "liv").stage == "live" and fol(fl, "liv").spec["label"] == "LIVE PAPER" and real_live["label"] == "LIVE"
          and FL.normalize({"id": "y", "plan": "mffu_builder_50k", "start": DAY, "adapter": "ninjatrader", "nt_account": "MFFU-1"})["label"] == "REAL")
    hb = fl.hb_block(b.t)
    check("heartbeat block is compact (< 6 KB) and lists every account", len(json.dumps(hb, separators=(",", ":"))) < 6000 and len(hb["acc"]) == 5,
          len(json.dumps(hb)))
    # a second LIT entry the same day: LIT's 1 a day -> not copied
    b.t += 600
    b.lit_enter(-1, 20100.0, 20120.0, 19980.0, qty=10)
    fl.tick("NQ", b.t)
    check("the lead's own day limit applies (LIT 1 a day): a second entry is not copied", all(len(ents(ads[i])) == 1 for i in ads))
    check("... and the skip says why (an eval that passed on the first copy: 'passed'; the others: the day limit)",
          "entries today" in fol(fl, "fix").skips[-1]["why"] and "passed" in fol(fl, "luc").skips[-1]["why"], (fol(fl, "fix").skips, fol(fl, "luc").skips))
    # restart: state persists
    fl.save()
    b2 = Bot(os.path.join(tmp, "copy"), b.t)
    b2.t = b.t
    fl2 = FL.Fleet(b2, {"accounts": acc}, state_path=os.path.join(tmp, "copy", "live_state_fleet.json"), adapter_factory=lambda f, c: Rec(c),
                   parallel=False).start()
    check("restart: every follower's closed copies and seen entries come back from its state file",
          all(len(fol(fl2, i).closes) == len(fol(fl, i).closes) and fol(fl2, i).seen == fol(fl, i).seen for i in ads))


def firm_cap_checks(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": "m50", "lead": "zlarior", "plan": "mffu_builder_50k", "start": "2026-10-19", "prior_pnl": -1850.0}]
    b, fl, ads, notes = make(os.path.join(tmp, "cap"), acc, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, qty=30)
    b.t = now + 3
    fl.tick("NQ", b.t)
    f = fol(fl, "m50")
    one = (20 + FM.SLIP_PTS) * 2 + FM.COMM
    q = ents(ads["m50"])[0]["qty"] if ents(ads["m50"]) else 0
    check("$150 room to the EOD floor: the copy is capped so a full stop-out stays above the floor", 0 < q and q * one < 150, (q, f.last_size))
    acc2 = [{"id": "dead", "lead": "zlarior", "plan": "mffu_builder_50k", "start": "2026-10-19", "prior_pnl": -2000.0}]
    b, fl, ads, notes = make(os.path.join(tmp, "cap2"), acc2, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    b.t = now + 3
    fl.tick("NQ", b.t)
    check("floor reached: no copy, the skip names it", not ents(ads["dead"]) and ("failed" in fol(fl, "dead").skips[-1]["why"]
                                                                                   or "floor" in fol(fl, "dead").skips[-1]["why"]),
          fol(fl, "dead").skips)
    acc3 = [{"id": "apx", "lead": "zlarior", "plan": "apex_eod_50k", "start": DAY, "adapter": "ninjatrader", "nt_account": "Sim105"}]
    b, fl, ads, notes = make(os.path.join(tmp, "cap3"), acc3, now)
    check("a firm that bans bots (Apex) cannot be a NinjaTrader follower (paper only)", fol(fl, "apx").problem and "does not allow" in fol(fl, "apx").problem,
          fol(fl, "apx").problem)
    acc4 = [{"id": "own", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY, "adapter": "ninjatrader", "nt_account": "Sim101"}]
    b, fl, ads, notes = make(os.path.join(tmp, "cap4"), acc4, now)
    check("a follower on the lead's own account Name is refused", "own account" in (fol(fl, "own").problem or ""), fol(fl, "own").problem)
    # late entry: never chased
    acc5 = [{"id": "late", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY}]
    b, fl, ads, notes = make(os.path.join(tmp, "cap5"), acc5, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, t=now)
    b.t = now + FL.MAX_AGE_S + 30
    fl.tick("NQ", b.t)
    check("a lead entry first seen > 90 s late is not chased", not ents(ads["late"]) and "seen" in fol(fl, "late").skips[-1]["why"])
    # a refused LEAD entry is never copied
    acc6 = [{"id": "r", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY}]
    b, fl, ads, notes = make(os.path.join(tmp, "cap6"), acc6, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, ok=False)
    fl.tick("NQ", now + 3)
    check("a lead entry its broker refused is never copied", not ents(ads["r"]))


def hedge_checks(tmp):
    now = ts(DAY, 10, 0)
    acc = [{"id": "fz", "name": "Z copy", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY},
           {"id": "fa", "name": "A copy", "lead": "atlas", "plan": "mffu_builder_25k", "start": DAY},
           {"id": "fb", "name": "B copy", "lead": "blitz", "plan": "mffu_builder_25k", "start": DAY}]
    b, fl, ads, notes = make(os.path.join(tmp, "hedge"), acc, now)
    b.acct_b, b.acct_c = Lead("Sim102"), Lead("Sim103")
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    b.t = now + 3
    fl.tick("NQ", b.t)
    check("Zlarior follower copies the LONG", len(ents(ads["fz"])) == 1)
    b.acct_b.enter(b.t, -1, 3, 20010.0, 20030.0, 19950.0)       # ATLAS short while LIT long (as if the leads had hedged)
    b.t += 2
    fl.tick("NQ", b.t)
    check("fleet-wide anti-hedge: an ATLAS follower never goes SHORT while LIT's account is LONG",
          not ents(ads["fa"]) and "hedging" in fol(fl, "fa").skips[-1]["why"], fol(fl, "fa").skips)
    b.acct_b.exit(b.t + 60, 0.0, "HEDGE")
    b.lit_exit(10 * (20 * 2 - FM.COMM), "TARGET")
    b.t += 120
    fl.tick("NQ", b.t)
    # ATLAS short copied, then LIT enters long: the follower is closed first (HEDGE), LIT may route
    b.t = ts(DAY, 11, 0)
    b.acct_b.enter(b.t, -1, 3, 20010.0, 20030.0, 19950.0)
    fl.tick("NQ", b.t + 2)
    check("ATLAS short copied once LIT is flat", len(ents(ads["fa"])) == 1 and fol(fl, "fa").pos is not None)
    why = fl.opposite_open(1)
    check("the fleet reports the follower's SHORT to a lead about to go LONG (LiveBot._route refuses it)", why and "A copy" in why, why)
    ok = fl.yield_to(1, 0, "NQ", b.t + 5, who="LIT")
    check("LIT entering LONG: the ATLAS follower's SHORT is closed at market first (HEDGE), then LIT may route",
          ok and fol(fl, "fa").pos is None and fol(fl, "fa").closes[-1][4] == "HEDGE")
    check("a follower never blocks the other side once flat", fl.opposite_open(1) is None)
    # ATLAS held back by a Zlarior follower (LIT priority); BLITZ followers yield to ATLAS
    from engine import account_b as AB
    from engine import account_c as AC
    b.t = ts(DAY, 12, 0)
    fz = fol(fl, "fz")
    fz.pos = {"entry_t": b.t, "dir": 1, "qty": 2, "entry": 20000.0, "stop": 19980.0, "target": 20100.0, "t": b.t, "sym": "NQ"}
    fake_b = type("B", (), {})()
    fake_b.bot = b
    b.state = {"price": 20000.0}
    why = AB.AccountB.lit_opposite(fake_b, -1)
    check("account B: a Zlarior follower's LONG holds ATLAS's SHORT back (no hedge, LIT priority)", why and "fleet follower" in why, why)
    fz.pos = None
    fbf = fol(fl, "fb")
    fbf.pos = {"entry_t": b.t, "dir": 1, "qty": 2, "entry": 20000.0, "stop": 19980.0, "target": 20100.0, "t": b.t, "sym": "NQ"}
    fake_b.bot = b
    fake_b.log = lambda *a: None
    r = AB.AccountB._fleet_yield(fake_b, -1, "NQ", b.t)
    check("account B entering SHORT: a BLITZ follower's LONG is closed first (BLITZ ranks last)", r is None and fbf.pos is None, r)
    fbf.pos = {"entry_t": b.t, "dir": 1, "qty": 2, "entry": 20000.0, "stop": 19980.0, "target": 20100.0, "t": b.t, "sym": "NQ"}
    fake_c = type("C", (), {})()
    fake_c.bot = b
    import inspect
    gate = AC.AccountC.opposite
    check("account C's no-hedge gate asks the fleet (any follower)", "fl.opposite_open(d)" in inspect.getsource(gate))
    try:
        why_c = gate(fake_c, -1) if gate is not None else None
    except Exception as e:
        why_c = f"{e}"
    check("account C: any follower holding the other side masks BLITZ's signal", why_c and "fleet follower" in str(why_c), why_c)
    fbf.pos = None
    # extra accounts (multi_account) see the fleet too
    src = open(os.path.join(ROOT, "engine", "multi_account.py"), encoding="utf-8").read()
    check("extra accounts (multi_account) never go opposite a follower", "fl.opposite_open(1 if ent[\"dir\"] == 1 else -1)" in src)
    # account C as a lead: its follower copies, a LIT follower never opposite it
    b.acct_b.exit(ts(DAY, 12, 30), 0.0, "HEDGE")
    b.t = ts(DAY, 13, 0)
    b.acct_c.enter(b.t, 1, 4, 20000.0, 19990.0, 20200.0)
    fl.tick("NQ", b.t + 1)
    check("BLITZ follower copies account C's entry", len(ents(ads["fb"])) == 1)
    b.acct_c.exit(b.t + 600, 4 * (10 * 2 - FM.COMM), "TIME")
    fl.tick("NQ", b.t + 602)
    check("... and its exit (TIME), booked at C's $ a micro", fol(fl, "fb").closes and abs(fol(fl, "fb").closes[-1][2] -
                                                                                              round((10 * 2 - FM.COMM) * ents(ads["fb"])[0]["qty"], 2)) < 0.02)


def refuse_checks(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": "bad", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY, "adapter": "ninjatrader", "nt_account": "Sim104"},
           {"id": "good", "lead": "zlarior", "plan": "mffu_builder_25k", "start": DAY}]
    fac = lambda f, c: Rec(c, broker=True, refuse=True) if f.id == "bad" else Rec(c)
    b, fl, ads, notes = make(os.path.join(tmp, "ref"), acc, now, factory=fac)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    b.t = now + 3
    fl.tick("NQ", b.t)
    bad, good = fol(fl, "bad"), fol(fl, "good")
    check("refused on one follower: no position there, the skip says REFUSED", bad.pos is None and "REFUSED" in bad.skips[-1]["why"], bad.skips)
    check("... the other follower trades normally", good.pos is not None and len(ents(ads["good"])) == 1)
    check("... and a push 'copy NOT placed'", any("NOT placed" in n[0] for n in notes), notes)
    b.t += 900
    b.lit_exit(10 * 100.0, "TARGET")
    fl.tick("NQ", b.t)
    check("the refused follower books nothing at the lead's exit; the other books its share", not bad.closes and len(good.closes) == 1,
          (bad.closes, good.closes))
    check("no exit order is routed for the refused copy", not [a for a in ads["bad"].sent if a.get("side") == "exit"])
    # NOT OK but a leg still working ("fill not reported yet"): kept and managed (never dropped on a guess), then dropped
    # without booking once NinjaTrader retired it unfilled (engine/ninjatrader.entry_never_placed, as LIT / account B)

    class Unclear(Rec):
        def send(self, a):
            self.sent.append(dict(a))
            if a.get("side") in ("buy", "sell"):
                self.legs.append({"entry_t": a["entry_t"], "status": "pending", "filled": 0})
                return {"ok": False, "error": "fill not reported yet", "legs": [{"state": "WORKING", "filled": 0}]}
            return {"ok": True}
    acc2 = [{"id": "unc", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY, "adapter": "ninjatrader", "nt_account": "Sim109"}]
    b, fl, ads, notes = make(os.path.join(tmp, "ref2"), acc2, now, factory=lambda f, c: Unclear(c, broker=True))
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl.tick("NQ", now + 3)
    u = fol(fl, "unc")
    check("NOT OK with a leg still working: the copy is KEPT (unconfirmed) and a push says 'NOT confirmed'",
          u.pos is not None and u.pos.get("unconfirmed") and any("NOT confirmed" in n[0] for n in notes), (u.pos, notes))
    ads["unc"].legs[-1]["status"] = "cancelled"
    fl.tick("NQ", now + 120)
    check("... NinjaTrader retired it unfilled: dropped, nothing booked, push 'NOT placed'",
          u.pos is None and not u.closes and "never placed" in u.skips[-1]["why"] and any("NOT placed" in n[0] for n in notes), (u.pos, u.skips))


def kill_checks(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": "k1", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY},
           {"id": "k2", "lead": "zlarior", "plan": "mffu_builder_25k", "start": DAY}]
    b, fl, ads, notes = make(os.path.join(tmp, "kill"), acc, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    b.t = now + 3
    fl.tick("NQ", b.t)
    cfg = {"accounts": copy.deepcopy(acc)}
    cfg["accounts"][0]["killed"] = True
    fl.update_cfg(cfg)
    b.t += 60
    fl.tick("NQ", b.t)
    check("per-account kill: k1 flattened (KILL SWITCH), k2 keeps its position",
          fol(fl, "k1").pos is None and fol(fl, "k1").closes[-1][4] == "KILL SWITCH" and fol(fl, "k2").pos is not None)
    b.lit_exit(100.0, "TARGET")
    b.t = ts(DAY, 9, 40) + 86400
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, t=b.t)
    fl.tick("NQ", b.t + 2)
    check("a killed follower takes no new entry; the other one does", len(ents(ads["k1"])) == 1 and len(ents(ads["k2"])) == 2)
    out = fl.kill("NQ")
    check("fleet-wide kill: every open follower flattened, no new entry", fol(fl, "k2").pos is None and fl.killed() and out)
    b.lit_exit(100.0, "TARGET")
    b.t += 86400
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, t=b.t)
    fl.tick("NQ", b.t + 2)
    check("after the fleet kill nothing is copied", len(ents(ads["k2"])) == 2)
    b2, fl2, ads2, _ = make(os.path.join(tmp, "kill2"), acc, now, kill=True)
    b2.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl2.tick("NQ", now + 3)
    check("'kill': true in data/fleet.json = no copy at all", not ents(ads2["k1"]) and not ents(ads2["k2"]))
    b3, fl3, ads3, _ = make(os.path.join(tmp, "kill3"), acc, now)
    b3.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl3.tick("NQ", now + 3)
    b3.kill = True
    fl3.tick("NQ", now + 60)
    check("the bot's own kill switch flag flattens every follower", all(f.pos is None for f in fl3.followers))


def gate_checks(tmp):
    now = ts(DAY, 9, 40)
    saved = os.environ.get(LIVE_ENV)
    os.environ.pop(LIVE_ENV, None)
    try:
        real = {"id": "real", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY, "adapter": "ninjatrader", "nt_account": "LUCID-123456"}
        made = []
        fac = lambda f, c: made.append(f.id) or Rec(c, broker=True)
        b, fl, ads, _ = make(os.path.join(tmp, "gate"), [real], now, factory=fac)
        check("a real (non-Sim) follower that is not armed: no adapter, never trades", fol(fl, "real").adapter is None and "not armed" in fol(fl, "real").problem
              and not made, fol(fl, "real").problem)
        b2 = Bot(os.path.join(tmp, "gate2"), now)
        _, fl2, _, _ = make(os.path.join(tmp, "gate2"), [{**real, "armed": True}], now, bot=b2, factory=fac)
        check("armed in the file but no phrase at the bot's start: refused", "phrase" in (fol(fl2, "real").problem or ""), fol(fl2, "real").problem)
        b3 = Bot(os.path.join(tmp, "gate3"), now, cfg={"confirm": LIVE_PHRASE})
        _, fl3, _, _ = make(os.path.join(tmp, "gate3"), [{**real, "armed": True}], now, bot=b3, factory=fac)
        check("armed + phrase but no NINJATRADER_LIVE=1: refused", LIVE_ENV in (fol(fl3, "real").problem or ""), fol(fl3, "real").problem)
        sim = {**real, "nt_account": "Sim107", "id": "sim"}
        _, fl4, ads4, _ = make(os.path.join(tmp, "gate4"), [sim], now, factory=lambda f, c: Rec(c, broker=True))
        check("a Sim follower needs no arming", fol(fl4, "sim").problem is None and fol(fl4, "sim").adapter is not None)
        cfg = fl3.adapter_cfg(fol(fl3, "real"))
        check("adapter cfg: the follower's own Name / OIF tag / state file; the bot's own arming never inherited when not armed",
              cfg["nt_account"] == "LUCID-123456" and cfg["nt_file_tag"].startswith("fl") and "fleet_real" in cfg["nt_state_path"])
        cfg0 = fl.adapter_cfg(fol(fl, "real"))
        check("a not-armed follower's adapter cfg carries no phrase", cfg0["confirm"] == "" and cfg0["armed"] is False)
        src = open(os.path.join(ROOT, "engine", "fleet.py"), encoding="utf-8").read()
        check("engine/fleet.py never sets NINJATRADER_LIVE and never arms by itself", "os.environ[" not in src and "environ.setdefault" not in src)
    finally:
        if saved is not None:
            os.environ[LIVE_ENV] = saved


def misc_checks(tmp):
    now = ts(DAY, 9, 40)
    slept = []
    acc = [{"id": "s", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY, "stagger_ms": 250, "adapter": "ninjatrader", "nt_account": "Sim108"}]
    b, fl, ads, notes = make(os.path.join(tmp, "misc"), acc, now, factory=lambda f, c: Rec(c, broker=True, fill_off=0.5), sleep=slept.append)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    b.adapter = type("A", (), {"legs": [{"entry_t": b._open_routed, "fill_px": 20000.25}]})()
    b.t = now + 3
    fl.tick("NQ", b.t)
    check("stagger: the follower waits its 250 ms before its entry", slept == [0.25], slept)
    f = fol(fl, "s")
    check("slippage vs the lead fill: +1 tick worse (20000.50 vs 20000.25)", f.slips and f.slips[-1]["ticks"] == 1.0, f.slips)
    b.t += 300
    b.lit_modify(20001.25)
    fl.tick("NQ", b.t)
    check("broker follower: the lead's BE stop move is routed as a modify", any(a.get("side") == "modify" and a.get("stop") == 20001.25 for a in ads["s"].sent))
    # the lead's trade vanishes without a close (never placed / voided): flattened after the grace period
    b._open_routed = None
    b.t += 30
    fl.tick("NQ", b.t)
    check("lead position gone without a close: kept during the grace period", f.pos is not None)
    b.t += FL.GONE_GRACE_S + 5
    fl.tick("NQ", b.t)
    check("... then flattened (LEAD GONE), booked at the mark", f.pos is None and f.closes[-1][4] == "LEAD GONE")
    # lifecycle: an eval that passes stops and pushes
    acc2 = [{"id": "p", "lead": "zlarior", "plan": "mffu_builder_25k", "start": "2026-10-19", "prior_pnl": 1400.0}]
    b, fl, ads, notes = make(os.path.join(tmp, "life"), acc2, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl.tick("NQ", now + 3)
    q = ents(ads["p"])[0]["qty"] if ents(ads["p"]) else 0
    b.t = now + 1200
    b.lit_exit(10 * (120 * 2 - FM.COMM), "TARGET")
    fl.tick("NQ", b.t)
    check("eval passed (+$1,500 on the 25K): push 'EVAL PASSED' with the --to-funded line", q > 0 and any("EVAL PASSED" in n[0] and "--to-funded" in n[1] for n in notes),
          (q, notes))
    b.t = now + 86400
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, t=b.t)
    fl.tick("NQ", b.t + 2)
    check("a passed eval takes no new entry", len(ents(ads["p"])) == 1 and "passed" in fol(fl, "p").skips[-1]["why"])
    acc3 = [{"id": "fd", "lead": "zlarior", "plan": "mffu_builder_50k", "stage": "funded", "funded_start": "2026-10-01", "prior_pnl": 2500.0}]
    b, fl, ads, notes = make(os.path.join(tmp, "life2"), acc3, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl.tick("NQ", now + 3)
    b.t = now + 1200
    b.lit_exit(10 * (60 * 2 - FM.COMM), "TARGET")
    fl.tick("NQ", b.t)
    check("funded: above the $2,100 buffer + $500 -> push 'PAYOUT READY' (never requested by the bot)", any("PAYOUT READY" in n[0] for n in notes), notes)
    acc4 = [{"id": "f1", "lead": "zlarior", "plan": "mffu_builder_50k", "stage": "funded", "funded_start": "2026-10-01"},
            {"id": "f2", "lead": "atlas", "plan": "mffu_builder_50k", "stage": "funded", "funded_start": "2026-10-01"}]
    b, fl, ads, notes = make(os.path.join(tmp, "life3"), acc4, now)
    w = fl.api(now)["warnings"]
    check("fleet warning: 2 funded MFFU Builder 50K followers, MFFU allows 1 per person (verified)", w and "allows 1" in w[0], w)
    check("MFFU profile warns that copying between your own accounts is not confirmed (ask support)",
          any("copying between your own accounts" in x for x in FM.profile("mffu_builder_50k")["warn"]))


def cli_checks(tmp):
    p = os.path.join(tmp, "cli", "fleet.json")
    run = lambda *a: FL.main(list(a) + ["--file", p])
    r1 = run("--add", "--id", "luc", "--lead", "zlarior", "--plan", "lucid_pro_50k", "--account", "Sim110", "--start", "2026-11-02")
    r2 = run("--add", "--id", "liv", "--plan", "live", "--account", "MYLIVE-1", "--start", "2026-11-02", "--balance", "10000", "--max-risk", "100")
    r3 = run("--add", "--id", "bad", "--plan", "no_such_plan", "--start", "2026-11-02")
    d = FL.load_file(p)
    check("CLI --add: two followers saved (Sim + LIVE), an unknown plan refused", r1 == 0 and r2 == 0 and r3 == 1 and [x["id"] for x in d["accounts"]] == ["luc", "liv"],
          (r1, r2, r3, d))
    check("CLI --add never arms (armed false)", all(x.get("armed") is False for x in d["accounts"]))
    run("--kill", "luc")
    run("--kill", "all")
    d = FL.load_file(p)
    check("CLI --kill <id> / --kill all", d["kill"] is True and d["accounts"][0]["killed"] is True)
    run("--unkill", "all")
    run("--to-funded", "luc", "--account", "Sim111", "--start", "2026-11-20")
    run("--payout", "luc", "2026-12-01=1000")
    d = FL.load_file(p)
    a = d["accounts"][0]
    check("CLI --to-funded (new Name, disarmed) and --payout", a["stage"] == "funded" and a["nt_account"] == "Sim111" and a["payouts"] == {"2026-12-01": 1000.0}
          and a["armed"] is False and d["kill"] is False, a)
    run("--arm", "liv")
    d = FL.load_file(p)
    txt = open(p, encoding="utf-8").read()
    check("CLI --arm writes armed true but never the phrase", d["accounts"][1]["armed"] is True and LIVE_PHRASE not in txt)
    run("--remove", "liv")
    check("CLI --remove", [x["id"] for x in FL.load_file(p)["accounts"]] == ["luc"])
    check("CLI --status runs", run("--status") == 0)
    from engine import ninjatrader as NT
    check("CLI --arm of a real Name puts it on the account allowlist (the owner's own command; a temp allowlist here)",
          "MYLIVE-1" in NT.allowed_accounts() and NT.ALLOW_PATH.startswith(tmp))
    run("--add", "--id", "rl", "--lead", "zlarior", "--plan", "lucid_pro_50k", "--account", "LUCID-9", "--start", "2026-11-02")
    pf = FL.preflight("rl", p, nt_folder=os.path.join(tmp, "no_nt"), env={})
    st = {x["key"]: x["state"] for x in pf["lines"]}
    check("--preflight a real follower: not allowlisted / not armed / not live = NOT READY, read-only",
          pf["ok"] is False and st.get("allow") == "bad" and st.get("armed") == "bad" and st.get("live") == "wait"
          and st.get("firm_bot") == "good" and FL.load_file(p)["accounts"][-1]["armed"] is False, pf["lines"])
    run("--add", "--id", "ax", "--lead", "zlarior", "--plan", "apex_eod_50k", "--start", "2026-11-02")
    st2 = {x["key"]: x["state"] for x in FL.preflight("ax", p, env={})["lines"]}
    check("--preflight: a firm that bans bots is red (Apex), a paper follower needs no NinjaTrader", st2.get("firm_bot") == "bad" and st2.get("route") == "info", st2)
    run("--add", "--id", "sm", "--lead", "zlarior", "--plan", "mffu_builder_25k", "--account", "Sim115", "--start", "2026-11-02")
    pf3 = FL.preflight("sm", p, env={})
    check("--preflight a Sim follower: no arming lines; MFFU copy trading not confirmed = WAIT", not any(x["key"] in ("armed", "allow") for x in pf3["lines"])
          and {x["key"]: x["state"] for x in pf3["lines"]}.get("copy") == "wait", pf3["lines"])
    trades = [{"entry_t": ts("2026-10-13", 9, 35), "exit_t": ts("2026-10-13", 10, 20), "dir": 1, "qty": 20, "entry": 25000.0, "stop": 24980.0,
               "target": 25100.0, "pnl": 20 * (100 * 2 - 1.9), "exit_reason": "TARGET"}]
    cfg = {"accounts": [{"id": "d1", "lead": "zlarior", "plan": "mffu_builder_50k", "start": "2026-10-13"}]}
    out = FL.dry_run("2026-10-13", cfg, trades=trades)
    check("--dry-run: the day's lead trades replayed on paper through the fleet", out["accounts"][0]["trades"] == 1 and out["accounts"][0]["today"] > 0, out["accounts"])


def api_checks(tmp):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import fleet_api as FA
    app = FastAPI()
    app.include_router(FA.router)
    c = TestClient(app)
    FA._bot = lambda: None
    r = c.get("/api/next/fleet").json()
    check("GET /api/next/fleet with no bot / no fleet: {on: false} (never 500)", r.get("on") is False, r)
    now = ts(DAY, 9, 40)
    b, fl, ads, _ = make(os.path.join(tmp, "api"), [{"id": "a1", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY}], now)
    FA._bot = lambda: b
    r = c.get("/api/next/fleet").json()
    check("GET /api/next/fleet: every account with firm / plan / stage / balance / room / today / open / slippage / warnings",
          r.get("on") is True and r["accounts"][0]["firm"].startswith("MyFundedFutures") and "room" in r["accounts"][0], r)
    check("GET /api/next/fleet: the firm catalog for the add guide", r.get("firms") and any(x["id"] == "lucid" for x in r["firms"]), list(r))
    # POST /api/next/fleet/set: the page's buttons = the CLI on data/fleet.json, PC only, never arms
    from engine import cloud_guard as CG
    keep = FL.FLEET_PATH
    FL.FLEET_PATH = os.path.join(tmp, "api_post", "fleet.json")
    try:
        loc = TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001))
        phone = TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003))
        tunnel = TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50005), headers={"X-Forwarded-For": "203.0.113.9"})
        body = {"action": "add", "id": "luc", "lead": "zlarior", "plan": "lucid_pro_50k", "account": "Sim112", "start": "2026-11-02"}
        rp, rt = phone.post("/api/next/fleet/set", json=body), tunnel.post("/api/next/fleet/set", json=body)
        check("POST /api/next/fleet/set from the phone / through a proxy: 403, nothing written",
              rp.status_code == 403 and rt.status_code == 403 and not os.path.exists(FL.FLEET_PATH), (rp.text, rt.text))
        rl = loc.post("/api/next/fleet/set", json=body)
        d = FL.load_file()
        check("POST add from the PC: saved, not armed", rl.status_code == 200 and rl.json().get("ok") and d["accounts"][0]["id"] == "luc"
              and d["accounts"][0]["armed"] is False and d["accounts"][0]["nt_account"] == "Sim112", rl.text)
        ra = loc.post("/api/next/fleet/set", json={"action": "arm", "id": "luc"})
        check("POST arm is refused (arming is never done from a page)", ra.status_code == 400 and FL.load_file()["accounts"][0]["armed"] is False, ra.text)
        rb = loc.post("/api/next/fleet/set", json={**body, "id": "x2", "account": 'Sim1;PLACE;"'})
        rc = loc.post("/api/next/fleet/set", json={**body, "id": "x3", "plan": "nope"})
        rd = loc.post("/api/next/fleet/set", json={**body, "id": "../x", "account": "Sim113"})
        check("POST refuses a Name with ; / quotes, an unknown plan, a bad id (400, nothing saved)",
              rb.status_code == 400 and rc.status_code == 400 and rd.status_code == 400 and len(FL.load_file()["accounts"]) == 1, (rb.text, rc.text, rd.text))
        rk = loc.post("/api/next/fleet/set", json={"action": "kill", "id": "all"})
        rf = loc.post("/api/next/fleet/set", json={"action": "to_funded", "id": "luc", "account": "Sim114", "start": "2026-11-20"})
        ry = loc.post("/api/next/fleet/set", json={"action": "payout", "id": "luc", "usd": "1000", "day": "2026-12-01"})
        d = FL.load_file()
        check("POST kill all / to_funded / payout work like the CLI", rk.json().get("ok") and rf.json().get("ok") and ry.json().get("ok")
              and d["kill"] is True and d["accounts"][0]["stage"] == "funded" and d["accounts"][0]["payouts"] == {"2026-12-01": 1000.0}, d)
        pf = loc.get("/api/next/fleet/preflight/luc").json()
        bad = loc.get("/api/next/fleet/preflight/..%2Fx")
        check("GET /api/next/fleet/preflight/<id>: the read-only checks (a Sim follower), a bad id refused",
              "lines" in pf and any(x["key"] == "sim" for x in pf["lines"]) and bad.status_code in (400, 404), (pf, bad.status_code))
        check("the POST route is cloud-blocked", "/api/next/fleet/set" in CG.CLOUD_BLOCKED and set(r.path for r in FA.router.routes
                                                                                                  if "POST" in getattr(r, "methods", set())) == set(CG.FLEET_WRITES))
    finally:
        FL.FLEET_PATH = keep


def nt_checks(tmp):
    """A Sim follower on the real NinjaTrader adapter against a simulated NinjaTrader 8 folder (engine/ninjatrader._FakeNT,
    as tests/test_multi_account): the order files carry the follower's own Name and OIF tag, the fill gives the slippage vs
    the lead, the lead's exit closes it."""
    from engine.ninjatrader import NinjaTraderAdapter, _FakeNT
    fake = _FakeNT(os.path.join(tmp, "nt", "NinjaTrader 8"), price=20000.5)
    folder = os.path.dirname(fake.inc)
    now = ts(DAY, 9, 40)
    clock = type("Clk", (), {"t": now, "__call__": lambda self: self.t})()

    def fac(f, cfg):
        ad = NinjaTraderAdapter({**cfg, "nt_folder": folder}, clock=clock)
        ad._sleep = lambda s: fake.process()
        ad._alert_fn = lambda text: None
        return ad
    acc = [{"id": "nts", "name": "Sim copy", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY, "adapter": "ninjatrader",
            "nt_account": "Sim102"}]
    b = Bot(os.path.join(tmp, "nt"), now, cfg={"adapter": "paper", "sym": "NQ", "instrument": "MNQ 12-26"})
    b.clock = clock
    b, fl, ads, notes = make(os.path.join(tmp, "nt"), acc, now, bot=b, factory=fac)
    f = fol(fl, "nts")
    check("NinjaTrader Sim follower: the adapter is built and not disabled", f.adapter is not None and not getattr(f.adapter, "disabled", None),
          (f.problem, getattr(f.adapter, "disabled", None)))
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, qty=10)
    b.adapter = type("A", (), {"legs": [{"entry_t": b._open_routed, "fill_px": 20000.25}]})()
    clock.t = now + 3
    fl.tick("NQ", clock.t)
    fake.process()
    names = " ".join(n for n, _ in fake.files)
    lines = " ".join(" ".join(ln) for _, ln in fake.files)
    check("the order file is tagged with the follower's own tag and routed to Sim102 only", "flnts_" in names and "Sim102" in lines
          and "Sim101" not in lines, (names[:200], lines[:300]))
    check("the copy is open on the follower", f.pos is not None and f.pos["qty"] > 0, (f.pos, f.skips))
    fl.adapter_tick()
    clock.t += 60
    fl.tick("NQ", clock.t)
    check("the fill is read back and the slippage vs the lead's fill recorded", f.slips and f.slips[-1]["ticks"] is not None, (f.slips, f.pos))
    clock.t += 600
    b.lit_exit(10 * (20 * 2 - 1.9), "TARGET", qty=10, t=clock.t)
    fl.tick("NQ", clock.t)
    fake.process()
    check("the lead's exit closes the follower on NinjaTrader (CLOSEPOSITION) and books it", f.pos is None and f.closes
          and "CLOSEPOSITION" in " ".join(" ".join(ln) for _, ln in fake.files), (f.pos, f.closes))
    check("the simulated NinjaTrader saw no grammar error", not fake.errors, fake.errors[:3])


def ui_checks(tmp):
    """The phone and PC pages rendered in node (tests/fleet_render.js) on a real heartbeat block / API answer; static checks:
    read-only (no POST, no arming), registered with one line each, nothing changed in clean.js / the layout lists."""
    import subprocess
    now = ts(DAY, 9, 40)
    acc = [{"id": "luc", "name": "Lucid 50K", "lead": "zlarior", "plan": "lucid_pro_50k", "start": DAY},
           {"id": "liv", "name": "My live", "lead": "zlarior", "plan": "live", "start": DAY, "live": {"start": 10000}}]
    b, fl, ads, _ = make(os.path.join(tmp, "ui"), acc, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl.tick("NQ", now + 3)
    from engine import fleet_api as FA
    keep = FA._bot
    FA._bot = lambda: b
    try:
        api = json.loads(FA.fleet_get().body)
    finally:
        FA._bot = keep
    p = os.path.join(tmp, "ui", "render.json")
    json.dump({"hb": fl.hb_block(now + 3), "api": api}, open(p, "w"))
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "fleet_render.js"), p], capture_output=True, text=True, timeout=60)
        out = json.loads(r.stdout or "{}")
    except Exception as e:
        out = {"error": f"node not available: {e}"}
    ph = (out.get("phone") or {}).get("html") or ""
    check("phone page: registered (#/fleet, System group) and renders a card per follower with LIVE / PAPER, room, today",
          (out.get("phone") or {}).get("registered") and (out.get("phone") or {}).get("grouped") and "Lucid 50K" in ph and "My live" in ph
          and "Room to floor" in ph and "LONG" in ph, out.get("error") or ph[:300])
    check("phone page off: the 3 steps, no card", "Add an account" in (out.get("phone_off") or "") and "Room to floor" not in (out.get("phone_off") or ""))
    pc = out.get("pc") or ""
    check("PC page renders the accounts, the firm rules table (owner's price only) and the add steps",
          "Lucid 50K" in pc and "Firm rules" in pc and "Add an account" in pc and "nx-glass" in pc, out.get("error") or pc[:300])
    js_p = open(os.path.join(ROOT, "tools", "web_public", "fleet.js"), encoding="utf-8").read()
    js_c = open(os.path.join(ROOT, "web_next", "js", "next", "fleet.js"), encoding="utf-8").read()
    check("phone page is read-only (no POST, no arm, no kill call)", "method: 'POST'" not in js_p and "/arm" not in js_p and "fetch(" not in js_p)
    posts = re.findall(r"fetch\('([^']+)', \{ method: 'POST'", js_c)
    check("PC page: its only POST is /api/next/fleet/set, it never sends an arm action",
          posts == ["/api/next/fleet/set"] and "action: 'arm'" not in js_c and "'arm'" not in js_c and "/arm" not in js_c, posts)
    check("PC page: Add / Off / Kill / Remove / Kill ALL ask before they post; the add says NOT armed",
          "window.confirm(confirmText)" in js_c and "It is NOT armed" in js_c and "Kill EVERY follower?" in js_c)
    idx = open(os.path.join(ROOT, "tools", "web_public", "index.html"), encoding="utf-8").read()
    scripts = re.findall(r'<script src="([^"]+)" defer></script>', idx)
    check("phone index.html: fleet.js is one <script defer> line after the last script", scripts and scripts[-1].startswith("fleet.js"), scripts[-3:])
    app = open(os.path.join(ROOT, "web_next", "js", "app.js"), encoding="utf-8").read()
    rts = open(os.path.join(ROOT, "web_next", "js", "next", "routes.js"), encoding="utf-8").read()
    check("PC: PAGES.fleet in app.js + the route entry (CC / TITLES) in routes.js, no layout list changed",
          "PAGES.fleet = fleetPage;" in app and "CC.push(FLEET); TITLES.fleet = FLEET.label;" in rts and "'fleet'" not in rts.split("export const GROUPS")[1].split("];")[0])


# ------------------------------------------------------------------------------------------------------------- replay
def replay(tmp):
    """tests/test_lit_live's LiveBot replay (3 October sessions, paper) with a fleet in the start cfg: the primary's ledger
    must be identical to the run without it, and each follower copies every LIT trade once with its own micros."""
    import collections
    from tests import test_lit_live as TL
    from tests import test_live_dryrun as TD
    from tools import lit_final as F
    P = json.load(open(TL.LIVE, encoding="utf-8"))["lit"]
    REF = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    by_day = collections.defaultdict(list)
    for t in REF:
        by_day[t["day"]].append(t)
    bots = []
    orig = TD.Replay.bot

    def run(cfg_extra):
        def bot(self, cfg=None, state_path=None, start_now=None):
            b = orig(self, {**(cfg or {}), **cfg_extra}, state_path, start_now)
            bots.append(b)
            return b
        TD.Replay.bot = bot
        try:
            return TL.bot_replay(P, by_day)
        finally:
            TD.Replay.bot = orig
    r0 = run({})
    led0 = [{k: v for k, v in r.items() if k != "result"} for r in bots[-1].ledger]
    fleet = {"accounts": [{"id": "pz", "lead": "zlarior", "plan": "lucid_pro_50k", "start": "2026-10-13"},
                          {"id": "p25", "lead": "zlarior", "plan": "mffu_builder_25k", "start": "2026-10-13"},
                          {"id": "plv", "lead": "zlarior", "plan": "live", "start": "2026-10-13",
                           "live": {"start": 10000, "max_risk_usd": 150, "daily_stop_usd": 300, "weekly_stop_usd": 600, "max_micros": 5}}]}
    r1 = run({"fleet": fleet})
    b1 = bots[-1]
    led1 = [{k: v for k, v in r.items() if k != "result"} for r in b1.ledger]
    check(f"replay: the bot alone routes every trade ({r0['entries_ok']}/{r0['want']} entries)", r0["ok"], r0.get("not_routed"))
    check("replay with 3 followers: the primary's ledger is identical (rows, prices, micros, times)", led0 == led1 and r1["ok"], (len(led0), len(led1)))
    check("replay: the primary's routing delay unchanged", r0["entry_route_delay_s"] == r1["entry_route_delay_s"])
    fl = getattr(b1, "fleet", None)
    check("replay: the fleet was built from the start cfg", fl is not None and len(fl.followers) == 3)
    if fl is None:
        return
    want = {int(r["entry_t"]) for r in b1.ledger if r.get("side") in ("buy", "sell")}
    for f in fl.followers:
        got = {int(c[3]) for c in f.closes}
        skipped = {int(s["entry_t"]) for s in f.skips}
        check(f"replay follower {f.id}: every lead trade copied once and closed once (or skipped with a reason)",
              got | skipped == want and not (got & skipped) and f.pos is None, (sorted(got), sorted(skipped), sorted(want), f.skips[-2:]))
    check("replay: every follower booked at least one copy (not only skips)", all(f.closes for f in fl.followers),
          [(f.id, len(f.closes), [s["why"][:60] for s in f.skips]) for f in fl.followers])
    lead_pm = {int(r["entry_t"]): float(r.get("pnl") or 0) / max(1, int(r.get("qty") or 1)) for r in b1.ledger if r.get("side") == "exit"}
    check("replay: each copy booked the lead's $ a micro x its own micros",
          all(abs(c[2] - round(lead_pm[int(c[3])] * next(int(r["qty"]) for r in f.ledger if r.get("side") in ("buy", "sell")
                                                            and int(r["entry_t"]) == int(c[3])), 2)) < 0.05
              for f in fl.followers for c in f.closes if int(c[3]) in lead_pm))
    lv = fol(fl, "plv")
    check("replay: the LIVE follower never above its 5 micros / $150 a trade",
          all(r["qty"] <= 5 for r in lv.ledger if r.get("side") in ("buy", "sell")))
    p25 = fol(fl, "p25")
    check("replay: the 25K follower never above 20 micros", all(r["qty"] <= 20 for r in p25.ledger if r.get("side") in ("buy", "sell")))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_fleet_")
    saved = {k: os.environ.get(k) for k in (LIVE_ENV, "LE_LIT_LEARNING")}
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    keep_path = FL.FLEET_PATH
    FL.FLEET_PATH = os.path.join(tmp, "no_fleet", "fleet.json")      # never the real data/fleet.json
    from engine import ninjatrader as NT
    keep_allow = NT.ALLOW_PATH
    NT.ALLOW_PATH = os.path.join(tmp, "nt_accounts_allow.json")      # never the real allowlist (--arm adds a real Name)
    try:
        off_checks(tmp)
        copy_checks(tmp)
        firm_cap_checks(tmp)
        hedge_checks(tmp)
        refuse_checks(tmp)
        kill_checks(tmp)
        gate_checks(tmp)
        misc_checks(tmp)
        cli_checks(tmp)
        api_checks(tmp)
        nt_checks(tmp)
        ui_checks(tmp)
        if "--quick" not in sys.argv:
            replay(tmp)
    finally:
        FL.FLEET_PATH = keep_path
        NT.ALLOW_PATH = keep_allow
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"fleet: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
