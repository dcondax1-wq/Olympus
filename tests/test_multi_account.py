"""Several accounts on one PC bot (engine/multi_account.py): independent sizing, lock-outs, kill, live locks, auto-resume,
heartbeat / health / Accounts sections, and the single-account bot unchanged.

  python -X utf8 -m tests.test_multi_account            # unit checks + a LiveBot replay of 3 October sessions with accounts
  python -X utf8 -m tests.test_multi_account --quick    # unit checks only (~5 s)

Sim101 / Sim10x and made-up account names only, simulated NinjaTrader folders (engine/ninjatrader._FakeNT), temp state
files; nothing is routed to a real NinjaTrader and no real account is ever armed.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import math
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import accounts, autoresume, multi_account as MA, sizing as sz  # noqa: E402
from engine.live import LiveBot, tick_px  # noqa: E402
from engine.ninjatrader import NinjaTraderAdapter, _FakeNT, LIVE_ENV  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


T0 = ts(2026, 10, 21, 10, 0)          # Wednesday 10:00 ET: the 5m bar of the entry
DAY = "2026-10-21"


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def pos_at(entry_t, qty=13, entry=25020.0, stop=24990.0, target=25220.0, d=1):
    return {"entry_t": entry_t, "dir": d, "qty": qty, "entry": entry, "stop": stop, "stop0": stop, "target": target,
            "risk_pts": abs(entry - stop), "be": False}


ACCTS = [
    {"id": "lucid", "name": "LucidPro 50K", "adapter": "ninjatrader", "nt_account": "Sim102", "preset": "lucid_pro_50k",
     "mode": "two_week", "eval_start": DAY},
    {"id": "fn", "name": "FundedNext 50K", "adapter": "ninjatrader", "nt_account": "Sim103", "preset": "fn_rapid_daily_50k",
     "mode": "two_week", "eval_start": "2026-10-20", "eval_prior_pnl": 2500.0},
    {"id": "fund", "name": "Paper funded", "adapter": "paper", "preset": "mffu_builder_50k", "mode": "funded",
     "funded": {"start": "2026-10-01", "payouts": {}}},
]


def make_bot(tmp, fake, clock, accounts_=None, extra_cfg=None, factory=True):
    """A LiveBot on paper (the primary) + the extra accounts; NinjaTrader accounts go to the simulated folder."""
    folder = os.path.dirname(fake.inc)

    def fac(acc, cfg):
        ad = NinjaTraderAdapter({**cfg, "nt_folder": folder}, clock=clock) if cfg["adapter"] == "ninjatrader" else None
        if ad is None:
            from engine.live import ADAPTERS
            return ADAPTERS[cfg["adapter"]](cfg)
        ad._sleep = lambda s: (fake.process(), setattr(clock, "t", clock.t + 0))
        ad._alert_fn = lambda text: None
        return ad
    MA.ADAPTER_FACTORY = fac if factory else None
    b = LiveBot()
    b.clock = clock
    b.state_path = os.path.join(tmp, "live_state.json")
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955},
           "accounts_parallel": False, **(extra_cfg or {})}
    if accounts_ is not None:
        cfg["accounts"] = copy.deepcopy(accounts_)
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    b._lit_sizing = {"mode": "normal"}
    return b


def signal(b, pos=None, trades=(), now=None):
    b.state = {"model": "lit", "position": pos, "lit": {}}
    b._route_signals({"trades": list(trades), "events": []}, "NQ", int(now or b.clock()), 300)


def acc(b, i):
    return next(a for a in b.accts.accounts if a.id == i)


def entries(rows):
    return [r for r in rows if r.get("side") in ("buy", "sell")]


def unit(tmp):
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    for k in (LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER"):
        os.environ.pop(k, None)
    fake = _FakeNT(os.path.join(tmp, "NinjaTrader 8"))
    clock = Clock(T0 + 290)                 # the bot starts just before the entry's bar closes; the signal comes 5 s after it

    # ---- 0. off by default: no "accounts" list = the one-account bot
    b0 = make_bot(os.path.join(tmp, "b0"), fake, clock)
    check("no accounts list: no router (today's bot)", b0.accts is None)
    p = pos_at(T0)
    clock.t = T0 + 305
    signal(b0, p)
    one = [{k: r.get(k) for k in ("side", "qty", "stop", "target", "entry", "entry_t")} for r in b0.ledger]

    # ---- 1. three accounts get independent micros from their own state
    clock.t = T0 + 290
    b = make_bot(os.path.join(tmp, "b1"), fake, clock, ACCTS)
    clock.t = T0 + 305
    check("router built with 3 extra accounts, all enabled",
          b.accts is not None and [a.id for a in b.accts.accounts] == ["lucid", "fn", "fund"] and all(a.enabled for a in b.accts.accounts),
          [(a.id, a.disabled_reason()) for a in (b.accts.accounts if b.accts else [])])
    signal(b, p)
    prim = [{k: r.get(k) for k in ("side", "qty", "stop", "target", "entry", "entry_t")} for r in b.ledger]
    check("primary routed exactly as without accounts (same rows)", prim == one, (prim, one))
    tgt = 200.0
    q_lucid = sz.two_week_qty({"risk_pts": 30.0, "tgt_pts": tgt}, {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1},
                              {"room_f": 0.4, "max_usd": 1000.0}, acct={"dll": 1200.0, "max_micros": 40})
    q_fn = sz.two_week_qty({"risk_pts": 30.0, "tgt_pts": tgt}, {"profit": 2500.0, "cum": 0.0, "room": 2000.0, "session": 2},
                           {"room_f": 0.4, "max_usd": 1000.0}, acct={"dll": 1000.0, "max_micros": 40})
    q_fund = sz.funded_qty({"risk_pts": 30.0, "tgt_pts": tgt}, {"room": 2000.0, "cum": 0.0, "locked": False},
                           PRESET_FUNDED, acct={"dll": 1000.0, "max_micros": 40})
    got = {a.id: [r["qty"] for r in entries(a.ledger)] for a in b.accts.accounts}
    check("lucid: one winner passes ($3,000 need, 40% room, $1,000 cap)", got["lucid"] == [q_lucid] and q_lucid == math.ceil(3000 / (tgt * 2 - 1.9)),
          (got, q_lucid))
    check("fn: needs only $500 after +$2,500 prior -> fewer micros", got["fn"] == [q_fn] and q_fn < q_lucid, (got, q_fn))
    check("funded paper: funded_qty (40% room, $800, winner <= $1,500)", got["fund"] == [q_fund] and q_fund >= 1, (got, q_fund))
    check("the four accounts' micros are independent", len({one[0]["qty"], q_lucid, q_fn, q_fund}) == 4, (one[0]["qty"], q_lucid, q_fn, q_fund))
    e_l = entries(acc(b, "lucid").ledger)[0]
    check("same entry / stop / target on every account (ticked like the primary)",
          all(entries(a.ledger)[0]["stop"] == tick_px(p["stop"], 1) and entries(a.ledger)[0]["target"] == tick_px(p["target"], 1, target=True)
              for a in b.accts.accounts) and e_l["entry_t"] == T0)
    lines = [ln for _, ls in fake.files for ln in ls]
    check("separate NinjaTrader orders per account (Sim102 and Sim103 brackets)",
          any(ln.startswith(f"PLACE;Sim102;MNQ 12-26;BUY;{q_lucid};MARKET") for ln in lines)
          and any(ln.startswith(f"PLACE;Sim103;MNQ 12-26;BUY;{q_fn};MARKET") for ln in lines)
          and sum(1 for ln in lines if "STOPMARKET" in ln) >= 2, lines[-6:])
    check("separate fills / positions: each NT adapter holds its own bracket",
          acc(b, "lucid").adapter.legs and acc(b, "fn").adapter.legs and acc(b, "lucid").adapter.legs[0]["filled"] == q_lucid
          and acc(b, "fn").adapter.legs[0]["filled"] == q_fn and fake.pos.get(("Sim102", "MNQ 12-26"), [0])[0] == q_lucid)
    names = os.listdir(os.path.join(tmp, "b1"))
    check("own state files per account (router + one NinjaTrader state each)",
          "live_state_accounts.json" in names and "ninjatrader_state_lucid.json" in names and "ninjatrader_state_fn.json" in names, names)
    # the stop moves to breakeven: each account's own bracket
    p_be = {**p, "stop": p["entry"], "be": True}
    signal(b, p_be)
    mods = {a.id: [r for r in a.ledger if r["side"] == "modify"] for a in b.accts.accounts}
    check("breakeven: one stop move per NinjaTrader account (paper: none)",
          len(mods["lucid"]) == 1 and len(mods["fn"]) == 1 and not mods["fund"] and acc(b, "lucid").adapter.legs[0]["stop"] == 25020.0,
          {k: len(v) for k, v in mods.items()})
    # the model exit: each account's own $ (scaled to its micros)
    tr = {"entry_t": T0, "exit_t": T0 + 3600, "exit_reason": "BE", "pnl": -24.7, "qty": 13, "dir": 1, "pnl_r": 0.0}
    clock.t = T0 + 3600 + 30
    signal(b, None, [tr])
    pnl = {a.id: [c[2] for c in a.closes] for a in b.accts.accounts}
    check("exits: every account flat, P&L = model $ x its micros / model micros",
          pnl == {"lucid": [round(-24.7 * q_lucid / 13, 2)], "fn": [round(-24.7 * q_fn / 13, 2)], "fund": [round(-24.7 * q_fund / 13, 2)]}
          and all(a.open_t is None for a in b.accts.accounts) and not acc(b, "lucid").adapter.legs
          and fake.pos.get(("Sim102", "MNQ 12-26"), [0])[0] == 0, pnl)

    # ---- 2. one account locked out never stops the others
    clock.t = ts(2026, 10, 22, 10, 4) + 50
    b2 = make_bot(os.path.join(tmp, "b2"), fake, clock, ACCTS + [
        {"id": "lost", "name": "Lost eval", "adapter": "paper", "preset": "paper_50k", "mode": "two_week", "eval_start": "2026-10-20",
         "eval_prior_pnl": -2000.0}])
    fn2 = acc(b2, "fn")
    fn2.closes.append(["2026-10-22", ts(2026, 10, 22, 4, 0), -1050.0, ts(2026, 10, 22, 3, 0)])
    fn2.check_lock(clock.t)
    p2 = pos_at(ts(2026, 10, 22, 10, 0), target=25220.0)
    clock.t = ts(2026, 10, 22, 10, 5) + 5
    signal(b2, p2)
    got2 = {a.id: len(entries(a.ledger)) for a in b2.accts.accounts}
    check("daily-loss lock-out: fn (-$1,050 today) routes nothing, lucid / fund still trade",
          got2 == {"lucid": 1, "fn": 0, "fund": 1, "lost": 0} and fn2.lock and "daily loss" in fn2.lock["reason"], got2)
    check("max-loss floor reached (prior -$2,000): that account is locked, the primary still trades",
          "floor" in ((acc(b2, "lost").lock or {}).get("reason") or "") and len(entries(b2.ledger)) == 1)
    h = {r["id"]: r for r in b2.accts.health()}
    check("health rows show the lock-outs", "daily loss" in (h["fn"]["locked"] or "") and h["lucid"]["locked"] is None)

    # ---- 3. kill switch flattens every account
    b2.kill_switch()
    check("kill: FakeNT flat on every account, paper accounts got their exit, bot stopped",
          all(v[0] == 0 for v in fake.pos.values()) and any(r["side"] == "exit" and r["reason"] == "KILL SWITCH" for r in acc(b2, "fund").ledger)
          and any(r["side"] == "exit" and r["reason"] == "KILL SWITCH" for r in acc(b2, "lucid").ledger) and not b2.running and b2.kill)
    signal(b2, pos_at(ts(2026, 10, 22, 11, 0)), now=ts(2026, 10, 22, 11, 5) + 5)
    check("after kill: no account routes a new entry", got2 == {a.id: len(entries(a.ledger)) for a in b2.accts.accounts})

    # ---- 4. live locks per account (never inherited from the primary)
    MA.ADAPTER_FACTORY = None
    live = [{"id": "real", "adapter": "ninjatrader", "nt_account": "LTFAKE0001", "preset": "lucid_pro_50k", "eval_start": DAY}]
    nt_cfg = {"adapter": "ninjatrader", "nt_account": "Sim101", "armed": True, "confirm": LIVE_PHRASE,
              "nt_folder": os.path.dirname(fake.inc), "nt_state_path": os.path.join(tmp, "nt_prim.json")}
    os.environ[LIVE_ENV] = "1"
    try:
        n_g = [0]

        def gate(entry, cfg=nt_cfg):
            n_g[0] += 1
            bb = make_bot(os.path.join(tmp, f"g{n_g[0]}"), fake, clock, [entry], extra_cfg={**cfg, "nt_audit_log": os.path.join(tmp, "a.log")},
                          factory=False)
            a = bb.accts.accounts[0]
            return a.disabled_reason()
        r0 = gate(live[0])
        r1 = gate({**live[0], "armed": True})
        r2n = gate({**live[0], "armed": True, "confirm": LIVE_PHRASE})          # not in the account allowlist
        os.environ["NINJATRADER_ALLOW"] = "LTFAKE0001"
        r2 = gate({**live[0], "armed": True, "confirm": LIVE_PHRASE})
        os.environ.pop("NINJATRADER_ALLOW", None)
        os.environ.pop(LIVE_ENV, None)
        r3 = gate({**live[0], "armed": True, "confirm": LIVE_PHRASE})
    finally:
        os.environ.pop(LIVE_ENV, None)
    check("real account: the primary's armed + phrase are NOT inherited", r0 and "not armed" in r0, r0)
    check("real account: armed but no phrase -> refused", r1 and "phrase" in r1, r1)
    check("real account: armed + phrase + NINJATRADER_LIVE=1 but not in the account allowlist -> refused",
          r2n and "allowlist" in r2n, r2n)
    check("real account: armed + phrase + NINJATRADER_LIVE=1 + allowlisted -> enabled", r2 is None, r2)
    check("real account: armed + phrase without NINJATRADER_LIVE=1 -> refused", r3 and LIVE_ENV in r3, r3)
    bad = MA.specs_from_cfg({"adapter": "ninjatrader", "nt_account": "Sim101", "accounts": [
        {"id": "dup", "adapter": "ninjatrader", "nt_account": "Sim101"}, {"id": "x", "adapter": "tradovate"},
        {"id": "y", "preset": "nope"}, {"id": "y", "adapter": "paper"}, {"id": "off", "adapter": "paper", "enabled": False}]})
    check("config problems refused per account (own account twice, tradovate, unknown preset, duplicate id, disabled)",
          [bool(s["problem"]) for s in bad] == [True] * 5, [s["problem"] for s in bad])

    # ---- 5. restart: the router restores today's ledger, closes and lock-outs
    clock.t = ts(2026, 10, 22, 12, 0)
    b3 = make_bot(os.path.join(tmp, "b2"), fake, clock, ACCTS, extra_cfg={"clear_kill": True})
    check("restart: closes and the daily-loss lock restored", acc(b3, "fn").lock and len(acc(b3, "lucid").closes) == 0
          and len(acc(b3, "fn").closes) == 1 and len(entries(acc(b3, "lucid").ledger)) == 1)
    clock.t = ts(2026, 10, 23, 9, 0)
    b4 = make_bot(os.path.join(tmp, "b2"), fake, clock, ACCTS)
    check("next day: the lock-out is gone, the closes stay (eval state)", acc(b4, "fn").lock is None and len(acc(b4, "fn").closes) == 1
          and acc(b4, "fn").eval_days().get("2026-10-22") == -1050.0)

    # ---- 6. funded_state wiring (primary and extras)
    st = MA.sizing_state("funded", [("2026-10-01", 1, 1500.0), ("2026-10-02", 2, 800.0)], "2026-10-03", "2026-10-01",
                         MA.PRESETS["mffu_builder_50k"]["rules"], payouts={"2026-10-02": 500.0})
    check("funded_state: balance after payouts, floor trails the EOD high, locked at +$100",
          st["balance"] == 1800.0 and st["floor"] == 100.0 and st["locked"] and st["room"] == 1700.0, st)
    sti = MA.sizing_state("funded", [("2026-10-01", 1, 1500.0), ("2026-10-01", 2, -600.0)], "2026-10-02", "2026-10-01",
                          {**MA.PRESETS["mffu_rapid_50k"]["rules"]})
    ste = MA.sizing_state("eval", [("2026-10-01", 1, 1500.0), ("2026-10-01", 2, -600.0)], "2026-10-02", "2026-10-01",
                          {**MA.PRESETS["mffu_rapid_50k"]["rules"]})
    check("intraday trailing (Rapid funded): the floor moved after the +$1,500 trade, the EOD eval floor did not",
          sti["room"] == 1400.0 and ste["room"] == 2000.0, (sti, ste))
    pb = make_bot(os.path.join(tmp, "pb"), fake, clock, None, extra_cfg={"eval_start": "2026-10-01", "funded": {"payouts": {"2026-10-02": 500.0}}})
    pb._eval_prev = {"2026-10-01": 1500.0, "2026-10-02": 800.0}
    pst = MA.primary_state(pb, "funded")
    check("primary funded mode gets its funded_state (was: unknown -> smallest size)", pst and pst["balance"] == 1800.0, pst)
    pb._lit_sizing = {"mode": "funded", "funded": PRESET_FUNDED}
    pb.state = {"model": "lit"}
    q = pb._equity_qty(T0, 13, pos_at(T0))
    exp = sz.funded_qty({"risk_pts": 30.0, "tgt_pts": 200.0}, pst, PRESET_FUNDED)
    check("primary funded qty = funded_qty on its own state", q == exp, (q, exp))
    # best-day rule (Rapid eval): the day's win stays inside 50% x $3,000 x 0.95
    clock.t = T0 + 290
    rb = make_bot(os.path.join(tmp, "rb"), fake, clock, [
        {"id": "rapid", "adapter": "paper", "preset": "mffu_rapid_50k", "mode": "eval", "eval_start": DAY}])
    clock.t = T0 + 305
    signal(rb, pos_at(T0, qty=30, target=25120.0))
    rq = entries(acc(rb, "rapid").ledger)[0]["qty"]
    check("best-day rule: a Rapid eval winner pays <= $1,425", rq * (100 * 2 - 1.9) <= 1425 and rq == int(1425 / (100 * 2 - 1.9)), rq)

    # ---- 6b. the MFFU Builder 25K eval next to the 50K (owner's next account): its own target / floor / daily loss / micros
    ex = json.load(open(os.path.join(ROOT, "ninjatrader", "accounts.example.json"), encoding="utf-8"))["accounts"]
    clock.t = T0 + 290
    kb = make_bot(os.path.join(tmp, "k25"), fake, clock, [{**ex[0], "adapter": "paper"}])
    clock.t = T0 + 305
    signal(kb, pos_at(T0, qty=13, target=25060.0))          # a 40-pt target, 30-pt stop
    k = acc(kb, "mffu25k")
    kq = entries(k.ledger)[0]["qty"] if entries(k.ledger) else None
    need = math.ceil(1500 / (40 * 2 - 1.9))                 # one winner covers $1,500 -> 20
    room_cap = int(0.5 * 1000 / 60)                         # 50% of the $1,000 room / ($2 x 30 pts) -> 8 (lit-builder-25k.md)
    dll_cap = int(600 / ((30 + 0.5) * 2 + 1.9))             # $600 soft daily loss -> 9
    q50 = sz.lit_qty(13, pos_at(T0, qty=13, target=25060.0), {"mode": "two_week", "two_week": {"room_f": 0.6, "wk": False}},
                     room=2000.0, state={"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0})["qty"]
    check("25K eval: its own rules (target $1,500, 50% of the $1,000 room, $600 daily loss, max 20) -> the 25K qty, not the 50K's",
          kq == min(need, room_cap, dll_cap, 20) == 8 and k.rules["target"] == 1500.0, (kq, need, room_cap, dll_cap))
    check("25K qty is about half the same signal on the 50K plan", q50 >= 2 * kq - 1 and q50 > kq, (kq, q50))
    # stuck: room under $100 -> no new entry on that account, a phone notice "25K stuck: room $X, buy a new one"
    notes = []
    kb.accts.notify = lambda title, body, key: notes.append(title)
    k.closes.append(["2026-10-21", T0 - 3600, -930.0, T0 - 7200])          # earlier today: room $1,000 - $930 = $70
    clock.t = T0 + 1800 + 290
    why = k.entry_block(clock.t)
    check("25K stuck (room $70 < $100): entries stop, push '25K stuck: room $70, buy a new one'",
          why and "stuck" in why and notes and notes[0] == "MFFU 25K Eval stuck: room $70, buy a new one", (why, notes))
    k.closes.pop()
    k.lock = None
    # hedging guard: never long on one account and short on another
    hb = make_bot(os.path.join(tmp, "hedge"), fake, clock, [{"id": "h1", "adapter": "paper", "preset": "paper_50k", "mode": "normal"},
                                                             {"id": "h2", "adapter": "paper", "preset": "paper_50k", "mode": "normal"}])
    acc(hb, "h1").open_t = 111
    acc(hb, "h1").ledger.append({"t": clock.t, "side": "buy", "qty": 1, "entry_t": 111, "sym": "NQ"})
    clock.t = T0 + 1800 + 305
    signal(hb, pos_at(T0 + 1800, d=-1, stop=25050.0, target=24900.0))
    check("hedging guard: a SHORT is refused on every other account while h1 is LONG (primary included)",
          not entries(acc(hb, "h2").ledger) and hb.ledger and hb.ledger[-1]["result"].get("ok") is False
          and "hedging" in hb.ledger[-1]["result"].get("error", ""), [r.get("result") for r in hb.ledger])
    st25 = k.state(DAY)
    check("25K eval state: room $1,000, session 1", st25["room"] == 1000.0 and st25["session"] == 1, st25)
    s25 = next(x for x in kb.accts.summary(clock.t) if x["id"] == "mffu25k")
    check("25K Accounts section plan: $25,000 start, floor locks at $25,100", s25["plan_rules"]["start"] == 25000.0 and s25["plan_rules"]["lock"] == 25100.0)

    # ---- 7. heartbeat acct block, health block, Accounts sections
    clock.t = T0 + 600
    a = accounts.pc_activity(b, now=clock.t, journal_path=os.path.join(tmp, "none.jsonl"))
    subs = a.get("accounts") or []
    check("heartbeat acct block: one sub-block per extra account, no phrase / paths",
          [s.get("id") for s in subs] == ["lucid", "fn", "fund"] and LIVE_PHRASE not in json.dumps(a) and tmp not in json.dumps(a), [s.get("id") for s in subs])
    hl = accounts.pc_health(b, now=clock.t)
    check("pc_health lists every account (label, mode, enabled)", [r["id"] for r in hl.get("accounts") or []] == ["lucid", "fn", "fund"]
          and hl["accounts"][0]["label"] == "SIM" and hl["accounts"][2]["label"] == "PAPER")
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    secs = accounts.build_accounts({"last_run": clock.t, "pc": {"present": True, "t": clock.t - 60, "acct": a}, "ledger": {}}, lm, now=clock.t)
    ids = [s["id"] for s in secs]
    ls = next(s for s in secs if s["id"] == "lucid")
    check("cloud Accounts page: a section per extra account after the MFFU eval", ids == ["mffu50k_eval", "lucid", "fn", "fund", "cloud_paper"]
          and ls.get("extra") and ls["eval"]["dll"] == 1200.0 and ls["mode"] == "two_week", ids)
    check("lucid section: its own closed trade and eval balance", ls["stats"]["n"] == 1 and abs(ls["eval"]["balance"] - (50000 + round(-24.7 * q_lucid / 13, 2))) < 0.01,
          (ls["stats"], ls["eval"]["balance"]))
    from engine import pcdash_api
    av = pcdash_api.account_view(b, now=clock.t, lm=lm, bars=False, journal_path=os.path.join(tmp, "none.jsonl"))
    check("PC Accounts page: the extra accounts card rows", [r["id"] for r in av.get("accounts") or []] == ["lucid", "fn", "fund"], av.get("accounts"))
    snap = b.snapshot()["cfg"]
    check("API snapshot: no per-account phrase field", snap.get("accounts") and all("confirm" not in x for x in snap["accounts"]))

    # ---- 8. auto-resume per account, or a clean refusal
    op = os.path.join(tmp, "auto_resume.json")
    autoresume.enable("MAINFAKE01", LIVE_PHRASE, {}, path=op)
    try:
        autoresume.enable_extra("Sim102", LIVE_PHRASE, path=op)
        sim_ok = False
    except ValueError:
        sim_ok = True
    autoresume.enable_extra("LTFAKE0002", LIVE_PHRASE, path=op)
    rec = autoresume.load(op)
    check("opt-in: an extra real account gets its own proof, no phrase stored",
          [x["account"] for x in rec.get("extra") or []] == ["LTFAKE0002"] and LIVE_PHRASE not in json.dumps(rec) and sim_ok)
    auto_cfg = {"adapter": "ninjatrader", "nt_account": "MAINFAKE01", "accounts": [
        {"id": "s", "adapter": "ninjatrader", "nt_account": "Sim102"},
        {"id": "l", "adapter": "ninjatrader", "nt_account": "LTFAKE0002", "armed": True},
        {"id": "f", "adapter": "ninjatrader", "nt_account": "FNFAKE0003", "armed": True},
        {"id": "u", "adapter": "ninjatrader", "nt_account": "LTFAKE0002X", "armed": False}]}
    d = autoresume.decide(rec, auto_cfg, {}, env={LIVE_ENV: "1"}, now=T0, connected=True)
    acs = {x["id"]: x for x in (d.get("cfg") or {}).get("accounts") or []}
    check("auto-resume: the bot resumes; Sim and opted-in real accounts come back",
          d["resume"] and acs["s"].get("enabled", True) and acs["l"].get("confirm") == LIVE_PHRASE and acs["l"].get("enabled", True), d.get("reason"))
    check("auto-resume: real accounts not opted in / not armed are left out cleanly (named in the refusals)",
          acs["f"]["enabled"] is False and acs["u"]["enabled"] is False and
          sorted(x["id"] for x in d.get("refused_accounts") or []) == ["f", "u"], d.get("refused_accounts"))
    d2 = autoresume.decide(rec, {"adapter": "ninjatrader", "nt_account": "MAINFAKE01"}, {}, env={LIVE_ENV: "1"}, now=T0, connected=True)
    check("auto-resume without accounts: exactly as before", d2["resume"] and "accounts" not in d2["cfg"] and "refused_accounts" not in d2)
    # data/accounts.json -> the --start body (the phrase in memory only for armed real accounts)
    fp = os.path.join(tmp, "accounts.json")
    MA.save_file([{"id": "l", "adapter": "ninjatrader", "nt_account": "LTFAKE0002", "armed": True, "confirm": LIVE_PHRASE},
                  {"id": "s", "adapter": "ninjatrader", "nt_account": "Sim102"}], fp)
    raw = open(fp, encoding="utf-8").read()
    body = MA.merge_into_start({"adapter": "ninjatrader"}, LIVE_PHRASE, path=fp)
    check("accounts.json never stores the phrase; --start gives it to armed real accounts only",
          LIVE_PHRASE not in raw and body["accounts"][0].get("confirm") == LIVE_PHRASE and "confirm" not in body["accounts"][1])
    cli = MA.main(["--file", fp, "--add", "--id", "fn50k", "--nt-account", "FNFAKE0003", "--preset", "fn_rapid_daily_50k",
                   "--eval-start", "2026-10-21"])
    check("CLI --add writes a valid entry", cli == 0 and any(r["id"] == "fn50k" for r in MA.load_file(fp)))
    MA.ADAPTER_FACTORY = None


PRESET_FUNDED = MA.PRESETS["mffu_builder_50k"]["sizing"]["funded"]


def replay(tmp):
    """The LiveBot replay of tests/test_lit_live (3 October sessions, paper) with two paper accounts: the primary's ledger
    must be identical to the run without accounts, and each account routes every trade once with its own micros."""
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
    acc_cfg = {"accounts": [{"id": "pe", "adapter": "paper", "preset": "paper_50k", "mode": "two_week", "eval_start": "2026-10-13"},
                            {"id": "pn", "adapter": "paper", "preset": "lucid_pro_50k", "mode": "normal", "max_micros": 5}]}
    r1 = run(acc_cfg)
    b1 = bots[-1]
    led1 = [{k: v for k, v in r.items() if k != "result"} for r in b1.ledger]
    check(f"replay: the single-account bot routes every trade ({r0['entries_ok']}/{r0['want']} entries, {r0['exits_ok']}/{r0['want']} exits)",
          r0["ok"], r0.get("not_routed"))
    check("replay with 2 extra accounts: the primary's ledger is identical (rows, prices, micros, times)", led0 == led1 and r1["ok"],
          (len(led0), len(led1)))
    check("replay: primary routed timing unchanged", r0["entry_route_delay_s"] == r1["entry_route_delay_s"],
          (r0["entry_route_delay_s"], r1["entry_route_delay_s"]))
    want = {int(t["entry_t"]) for d in ("2026-10-13", "2026-10-14", "2026-10-15") for t in by_day.get(d, [])}
    for a in b1.accts.accounts:
        en = {int(r["entry_t"]): r for r in entries(a.ledger)}
        ex = [r for r in a.ledger if r["side"] == "exit"]
        check(f"replay account {a.id}: every trade entered once and exited once", set(en) == want and len(ex) == len(want),
              (sorted(en), sorted(want), len(ex)))
    pn = acc(b1, "pn")
    check("replay account pn: its own max 5 micros", all(r["qty"] <= 5 for r in entries(pn.ledger)))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_multi_")
    saved = {k: os.environ.get(k) for k in (LIVE_ENV, "LE_LIT_LEARNING", "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER")}
    try:
        unit(tmp)
        if "--quick" not in sys.argv:
            replay(tmp)
    finally:
        MA.ADAPTER_FACTORY = None
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"multi_account: {sum(RESULTS)}/{len(RESULTS)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
