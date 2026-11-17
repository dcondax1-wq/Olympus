"""The MFFU Rapid EOD 50K (engine/rapid.py): LIT + ATLAS on ONE account, OFF until data/rapid.json names it.

    python -X utf8 -m tests.test_rapid            # unit checks + a paper LiveBot (~10 s)

Paper bots, temp files, made-up / Sim names only: nothing routed to a real NinjaTrader, nothing real armed.
  a. off by default (no block = no lane, no ATLAS lane); the owner's one line writes a DISARMED block; only the typed phrase
     arms it; the phrase never lands in the file
  b. on: LIT's lane (preset mffu_rapid_eod_50k) + ATLAS's lane on the same account; ONE book (balance, day $) for both
  c. never two positions: ATLAS blocked while LIT holds / enters; LIT entering closes ATLAS first (any side), then routes
  d. the 30% best-day cap on both lanes (on the combined day), ATLAS $500 / 30% of the room, pass needs 4 days + 30%
  e. funded: Tier-1 news ban on ATLAS (LIT's lane has the preset's), payout advice keeps $1,000 above the $2,100 buffer
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import multi_account as MA, rapid  # noqa: E402
from engine.live import LiveBot  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


T0 = ts(2026, 10, 21, 10, 0)
DAY = "2026-10-21"


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def pos_at(entry_t, qty=13, entry=25020.0, stop=24990.0, target=25220.0, d=1):
    return {"entry_t": entry_t, "dir": d, "qty": qty, "entry": entry, "stop": stop, "stop0": stop, "target": target,
            "risk_pts": abs(entry - stop), "be": False}


def make_bot(tmp, clock, blk):
    os.makedirs(tmp, exist_ok=True)
    MA.ADAPTER_FACTORY = None
    b = LiveBot()
    b.clock = clock
    b.state_path = os.path.join(tmp, "live_state.json")
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955},
           "accounts_parallel": False, "account_b": None, "account_c": None, "fleet": None}
    if blk is not False:
        cfg["rapid"] = blk
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    ls = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
    b._lit_sizing = {**ls, "mode": "normal"}
    return b


def lane(b):
    return next(a for a in b.accts.accounts if a.spec.get("lane") == "rapid")


def same_account_sim(tmp):
    """f. the two lanes' NinjaTrader adapters on ONE simulated Sim account (engine/ninjatrader._FakeNT): ATLAS's trade, its
    close, then LIT's bracket; neither adapter's tick touches the other's position; LIT's exit leaves the account flat."""
    from engine.ninjatrader import NinjaTraderAdapter, _FakeNT
    folder = os.path.join(tmp, "nt", "NinjaTrader 8")
    fake = _FakeNT(folder)
    now = [ts(2026, 10, 21, 10, 5)]

    def make(tag):
        cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": folder, "nt_account": "Sim105",
               "params": {"max_micros": 30, "flat_mod": 955}, "nt_max_entries_day": 999, "nt_file_tag": tag,
               "nt_state_path": os.path.join(tmp, f"nt_state_{tag}.json"), "nt_audit_log": os.path.join(tmp, f"oif_{tag}.log")}
        ad = NinjaTraderAdapter(cfg, clock=lambda: now[0])
        ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = lambda text: None
        return ad
    lit_ad, atl = make("rapid_"), make("acctr_")
    pos = lambda: sum(q for (a, _), (q, _x) in fake.pos.items() if a == "Sim105")
    check("f. Sim: both adapters enabled on the same account (one process, one account lock)",
          not lit_ad.disabled and not atl.disabled, (lit_ad.disabled, atl.disabled))
    T1 = ts(2026, 10, 21, 9, 35)
    r = atl.send({"sym": "NQ", "side": "buy", "qty": 3, "stop": 24990.0, "target": 25060.0, "entry": 25020.0, "entry_t": T1})
    fake.process()
    lit_ad.tick()
    fake.process()
    check("f. Sim: ATLAS long 3 placed; LIT's adapter tick leaves it alone", r.get("ok") and pos() == 3, (r, pos()))
    x = atl.send({"sym": "NQ", "side": "exit", "qty": 3, "reason": "HEDGE", "entry_t": T1})
    fake.process()
    check("f. Sim: ATLAS's close (LIT first) confirmed flat", x.get("ok") is not False and pos() == 0
          and not any(lg.get("status") in ("protected", "unprotected", "pending") for lg in atl.legs), (x, pos()))
    T2 = ts(2026, 10, 21, 10, 0)
    r2 = lit_ad.send({"sym": "NQ", "side": "buy", "qty": 5, "stop": 24990.0, "target": 25200.0, "entry": 25020.0, "entry_t": T2})
    fake.process()
    for _ in range(3):
        atl.tick()
        lit_ad.tick()
        fake.process()
    check("f. Sim: LIT long 5 with its bracket; ATLAS's adapter tick never closes LIT's position", r2.get("ok") and pos() == 5
          and any(lg.get("status") == "protected" for lg in lit_ad.legs), (r2, pos(), [lg.get("status") for lg in lit_ad.legs]))
    x2 = lit_ad.send({"sym": "NQ", "side": "exit", "qty": 5, "reason": "TIME", "entry_t": T2})
    fake.process()
    check("f. Sim: LIT's exit leaves the account flat, no order of either lane still working", x2.get("ok") is not False and pos() == 0
          and not [o for o in fake.orders.values() if o.get("state") in ("WORKING", "ACCEPTED")], (pos(), list(fake.orders.values())[:2]))
    for ad in (lit_ad, atl):
        try:
            ad.release_lock()
        except Exception:
            pass


def review_checks(tmp, clock, b, fb):
    """g. review 2026-11-17: a lane's unconfirmed NinjaTrader close still holds the account; LIT sizes after ATLAS's close is
    booked; a funded NEWS FLAT is booked at the market, not $0; the Rapid's Name is never ATLAS's 25K."""
    from types import SimpleNamespace
    from engine.sizing import LIVE_COMM
    L, A = lane(b), b.acct_r
    saved_t, saved_state = clock.t, b.state
    L.open_t, A.open_t = None, None
    b.state = {"model": "lit", "position": None, "lit": {}}
    L.adapter.legs = [{"status": "closing", "dir": 1, "entry_t": T0 - 600}]
    check("g. LIT's lane model flat but its CLOSEPOSITION unconfirmed: ATLAS blocked (either side)",
          bool(A.lit_opposite(1)) and bool(A.lit_opposite(-1)), A.lit_opposite(-1))
    del L.adapter.legs
    A.adapter.legs = [{"status": "closing", "dir": 1, "entry_t": T0 - 600}]
    check("g. ATLAS's model flat but its close unconfirmed: LIT on this account waits (any side)",
          A.yield_to_lit(1, "NQ", int(clock.t), any_side=True) is False)
    check("g. ... and Zlarior waits only for the opposite side",
          A.yield_to_lit(1, "NQ", int(clock.t)) is True and A.yield_to_lit(-1, "NQ", int(clock.t)) is False)
    del A.adapter.legs
    # LIT sizes after ATLAS's HEDGE close is booked: +$752 on ATLAS leaves no best-day room for LIT's 200-pt winner
    clock.t = T0 + 290
    b3 = make_bot(os.path.join(tmp, "b3"), clock, {"account": "Sim107", "eval_start": DAY, "armed": False})
    L3, A3 = lane(b3), b3.acct_r
    tb = T0 - 900
    A3.open_t = tb
    A3.prov[tb] = {"key": "macd_sweep", "short": "MACD", "qty": 20, "dir": 1, "entry": 25000.0, "stop": 24990.0,
                   "target": 25030.0, "t": tb, "risk_pts": 10.0, "day": DAY}
    A3.ledger.append({"t": tb, "sym": "NQ", "side": "buy", "qty": 20, "entry_t": tb, "result": {"ok": True}})
    clock.t = T0 + 305
    b3.state = {"model": "lit", "position": pos_at(T0), "lit": {}}
    b3._route_signals({"trades": [], "events": []}, "NQ", int(clock.t), 300)
    check("g. ATLAS closed +$752 first, then LIT re-sized on the combined day: best-day cap -> not routed",
          A3.open_t is None and A3.day_pnl(DAY) > 700 and not [r for r in L3.ledger if r.get("side") in ("buy", "sell")]
          and T0 in L3.blocked, (A3.day_pnl(DAY), L3.ledger, L3.last_size))
    # funded NEWS FLAT on LIT's lane: booked at the market
    FL_ = lane(fb)
    rel = T0 + 600
    old = MA.tier1_releases
    MA.tier1_releases = lambda day: [rel]
    try:
        clock.t = rel - 60
        et_ = T0 - 300
        fb.state = {"model": "lit", "position": pos_at(et_), "price": 25000.0, "lit": {}}
        FL_.open_t, FL_.open_qty = et_, 5
        FL_.seen.add(("entry", et_))
        fb._route_signals({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        want = round(5 * ((25000.0 - 25020.0 - 0.25) * 2.0 - float(LIVE_COMM)), 2)
        row = next((c for c in FL_.closes if len(c) > 3 and c[3] == et_), None)
        check("g. funded NEWS FLAT: LIT's lane flat and booked at the market (not $0)",
              FL_.open_t is None and row is not None and abs(float(row[2]) - want) < 0.01, (row, want))
        # held INTO the release (e.g. a restart inside the window): closed in the 2 minutes after it too
        clock.t = rel + 30
        et2 = T0 + 200
        fb.state = {"model": "lit", "position": pos_at(et2), "price": 25000.0, "lit": {}}
        FL_.open_t, FL_.open_qty = et2, 5
        FL_.seen.add(("entry", et2))
        fb._route_signals({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        check("g. funded: LIT's lane still open 30 s after the release -> NEWS FLAT", FL_.open_t is None and et2 in FL_.flattened)
        FA = fb.acct_r
        FA.open_t = et2
        FA.prov[et2] = {"key": "macd_sweep", "short": "MACD", "qty": 2, "dir": 1, "entry": 25000.0, "stop": 24990.0,
                        "target": 25030.0, "t": et2, "risk_pts": 10.0, "day": DAY}
        FA.ledger.append({"t": et2, "sym": "NQ", "side": "buy", "qty": 2, "entry_t": et2, "result": {"ok": True}})
        FA.tick(None, None, "NQ", int(clock.t))
        check("g. funded: ATLAS still open 30 s after the release -> NEWS FLAT",
              FA.open_t is None and any(r.get("reason") == "NEWS FLAT" for r in FA.ledger if r.get("side") == "exit"))
    finally:
        MA.tier1_releases = old
    # LIT's lane entry refused by NinjaTrader ("Limit 0"): never a position, so its model P&L is NOT booked on the Rapid
    clock.t = T0 + 290
    b4 = make_bot(os.path.join(tmp, "b4"), clock, {"account": "Sim108", "eval_start": DAY, "armed": False})
    L4, A4 = lane(b4), b4.acct_r
    L4.open_t, L4.open_qty = T0, 5
    L4.seen.add(("entry", T0))
    L4.ledger.append({"t": T0 + 3, "sym": "NQ", "side": "buy", "qty": 5, "entry_t": T0,
                      "result": {"ok": False, "error": "order rejected: Limit 0"}})
    clock.t = T0 + 605
    b4.state = {"model": "lit", "position": None, "lit": {}}
    tr = {**pos_at(T0), "exit_t": T0 + 600, "exit": 25220.0, "pnl": 2000.0, "exit_reason": "TARGET", "day": DAY}
    b4._route_signals({"trades": [tr], "events": []}, "NQ", int(clock.t), 300)
    check("g. LIT lane entry rejected ('Limit 0'): flat, no exit routed, $0 booked on the Rapid's book",
          L4.open_t is None and not L4.closes and A4.day_pnl(DAY) == 0.0
          and not [r for r in L4.ledger if r.get("side") == "exit"], (L4.open_t, L4.closes, L4.ledger[-1:]))
    check("g. ... and ATLAS is free again on that account", A4.lit_opposite(1) is None, A4.lit_opposite(1))
    L4.ledger.append({"t": T0 + 900, "sym": "NQ", "side": "buy", "qty": 5, "entry_t": T0 + 900, "result": {"ok": True}})
    L4.open_t, L4.open_qty = T0 + 900, 5
    L4._drop_unplaced(int(clock.t))
    check("g. an entry NinjaTrader took (ok) is never dropped", L4.open_t == T0 + 900)
    # the Rapid's Name = ATLAS's 25K account: neither lane trades
    b3.acct_b = SimpleNamespace(name="Sim107", open_t=None)
    b3._start_rapid()
    check("g. Rapid Name = ATLAS's 25K: ATLAS lane off, LIT's lane refused", b3.acct_r is None and bool(L3.problem), L3.problem)
    b3.acct_b = None
    clock.t, b.state = saved_t, saved_state


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rapid_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        clock = Clock(T0 + 290)
        # ---- a. off by default + the owner's one line
        b0 = make_bot(os.path.join(tmp, "b0"), clock, False)
        check("a. off: no data/rapid.json in a test bot = no lanes", b0.accts is None and b0.acct_r is None)
        fp = os.path.join(tmp, "rapid.json")
        check("a. read(): missing file = OFF", rapid.read(fp) is None)
        r = rapid.set_account("Sim105", p=fp, others={"Zlarior (50K)": "Sim101", "ATLAS (25K)": "Sim102"})
        blk = rapid.read(fp)
        check("a. the one line writes the block: account, eval from today, DISARMED",
              r["ok"] and blk and blk["account"] == "Sim105" and blk["armed"] is False and blk.get("eval_start"), r)
        check("a. refused: the Name of Zlarior's / ATLAS's account",
              not rapid.set_account("Sim102", p=os.path.join(tmp, "x.json"), others={"ATLAS (25K)": "Sim102"})["ok"])
        check("a. refused: a Name with ;", not rapid.set_account("A;B", p=os.path.join(tmp, "y.json"), others={})["ok"])
        check("a. arm without the phrase: refused, still disarmed",
              not rapid.arm("i accept", p=fp)["ok"] and rapid.read(fp)["armed"] is False)
        check("a. arm with the typed phrase: armed", rapid.arm(LIVE_PHRASE, p=fp)["ok"] and rapid.read(fp)["armed"] is True)
        check("a. the phrase never lands in the file", LIVE_PHRASE not in open(fp, encoding="utf-8").read())
        ls = rapid.lane_spec(rapid.read(fp), {"adapter": "ninjatrader", "confirm": LIVE_PHRASE})
        check("a. LIT lane: preset Rapid EOD, two_week, armed + this start's phrase (memory only)",
              ls["preset"] == "mffu_rapid_eod_50k" and ls["mode"] == "two_week" and ls["armed"] and ls["confirm"] == LIVE_PHRASE)
        ls2 = rapid.lane_spec({**rapid.read(fp), "armed": False}, {"adapter": "ninjatrader", "confirm": LIVE_PHRASE})
        check("a. disarmed block: no phrase handed to the lane", "confirm" not in ls2 and ls2["armed"] is False)
        check("a. off(): OFF again", rapid.off(p=fp)["ok"] and rapid.read(fp) is None)
        P = MA.PRESETS["mffu_rapid_eod_50k"]
        check("a. preset un-held: 30% best day, 4 days, funded news ban, live two_week eval size, funded 60% / $1,500",
              P["rules"]["best_day"] == 0.3 and P["rules"]["min_days"] == 4 and P["rules"]["news_ban"] == "funded"
              and "two_week" not in P["sizing"] and P["sizing"]["funded"]["pct_max_usd"] == 1500 and "HELD" not in P["note"])

        # ---- b. on: both lanes, one book
        b = make_bot(os.path.join(tmp, "b1"), clock, {"account": "Sim105", "eval_start": DAY, "armed": False})
        L, A = lane(b), b.acct_r
        check("b. on: LIT's lane + ATLAS's lane on the same account",
              L is not None and isinstance(A, rapid.RapidAtlas) and L.spec["nt_account"] == A.name == "Sim105"
              and A.problem is None and L.problem is None, (A and A.problem, L and L.problem))
        check("b. ATLAS lane: own order tag and state files", A.adapter_cfg()["nt_file_tag"] == "acctr_"
              and A.state_path.endswith("_acctr.json"))
        L.closes.append([DAY, T0 - 3600, 400.0, T0 - 4000])
        check("b. ATLAS sees LIT's closed $ (one day P&L)", A.day_pnl(DAY) == 400.0 and A._state_raw(T0)["cum"] == 400.0)
        A.closes.append([DAY, T0 - 1800, -100.0, T0 - 2000])
        check("b. LIT's lane sees ATLAS's closed $ (one balance)", L.day_pnl(DAY) == 300.0 and L.state(DAY)["cum"] == 300.0)
        L.closes.clear()
        A.closes.clear()

        # ---- d. sizing
        st = A._state_raw(T0)
        s1 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, st)
        check("d. ATLAS $500 risk on a 10-pt stop: 22 micros (500 / 22.4)", s1["qty"] == 22, s1)
        A.closes.append([DAY, T0 - 1800, 400.0, T0 - 2000])
        s2 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, A._state_raw(T0))
        check("d. 30% best day: $400 made today -> a winner pays <= $455 -> 11 micros", s2["qty"] == 11, s2)
        A.closes.append([DAY, T0 - 1700, 400.0, T0 - 1900])
        ent = {**pos_at(T0), "tgt_pts": 200.0}
        q = L.qty_for(ent, T0 + 300)
        check("d. LIT's lane: the best-day cap counts ATLAS's $ today (skip when 1 micro's winner is too big)",
              q == 0 and any("best-day" in x for x in (L.last_size or {}).get("reasons", [])), L.last_size)
        A.closes.clear()
        for i, d in enumerate(("2026-10-21", "2026-10-22", "2026-10-23")):
            A.closes.append([d, T0 + i * 86400, 1100.0, T0 + i * 86400 - 60])
        clock.t = ts(2026, 10, 26, 10, 0)
        ev = A.eval_view()
        check("d. $3,300 in 3 days: NOT passed (4 days + best day <= 30% needed)", ev["status"] == "open", ev.get("status"))
        A.closes[:] = [[d, T0 + i * 86400, 800.0, T0 + i * 86400 - 60]
                       for i, d in enumerate(("2026-10-21", "2026-10-22", "2026-10-23", "2026-10-26"))]
        clock.t = ts(2026, 10, 27, 10, 0)
        ev = A.eval_view()
        check("d. $3,200 in 4 days, best $800 <= 30%: passed (no new trade)", ev["status"] == "passed", ev)
        A.closes.clear()
        clock.t = T0 + 290

        # ---- c. never two positions on the account
        b.state = {"model": "lit", "position": None, "lit": {}}
        check("c. LIT flat, no setup: ATLAS may enter", A.lit_opposite(1) is None, A.lit_opposite(1))
        L.open_t = T0 - 600
        check("c. LIT's lane holds a trade: ATLAS blocked (either side)", A.lit_opposite(1) and A.lit_opposite(-1))
        L.open_t = None
        b.state = {"model": "lit", "position": pos_at(T0 - 600), "lit": {}}
        check("c. LIT in a trade (even one the lane skipped): ATLAS blocked", bool(A.lit_opposite(1)))
        b.state = {"model": "lit", "position": None, "lit": {}, "setups": {"short": {"tapped_t": None}}}
        check("c. LIT short setup armed: ATLAS long blocked, short allowed", bool(A.lit_opposite(1)) and A.lit_opposite(-1) is None)
        # ATLAS holds a LONG; LIT enters LONG (same side): ATLAS closed first, then LIT's lane routes
        tb = T0 - 900
        A.open_t = tb
        A.prov[tb] = {"key": "macd_sweep", "short": "MACD", "qty": 3, "dir": 1, "entry": 25000.0, "stop": 24990.0,
                      "target": 25030.0, "t": tb, "risk_pts": 10.0, "day": DAY}
        A.ledger.append({"t": tb, "sym": "NQ", "side": "buy", "qty": 3, "entry_t": tb, "result": {"ok": True}})
        clock.t = T0 + 305
        b.state = {"model": "lit", "position": pos_at(T0), "lit": {}}
        b._route_signals({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        ex = [r for r in A.ledger if r.get("side") == "exit"]
        ent_l = [r for r in L.ledger if r.get("side") in ("buy", "sell")]
        check("c. LIT enters while ATLAS holds: ATLAS closed at market first (HEDGE), then LIT's lane routed",
              A.open_t is None and ex and ex[0]["reason"] == "HEDGE" and ent_l and L.open_t == T0
              and ex[0]["t"] <= ent_l[0]["t"], (A.open_t, ex, ent_l, L.last_size))

        # ---- e. funded
        fb = make_bot(os.path.join(tmp, "b2"), clock, {"account": "Sim106", "eval_start": "2026-09-01", "stage": "funded",
                                                       "funded_start": "2026-10-01", "payouts": {}})
        FA, FL_ = fb.acct_r, lane(fb)
        check("e. funded: both lanes in the funded stage", FA.funded() and FL_.mode == "funded" and FL_.news_on())
        rel = T0 + 600
        old = MA.tier1_releases
        MA.tier1_releases = lambda day: [rel]
        try:
            g = FA.guard({"sym": "NQ", "side": "buy", "qty": 1, "stop": 1.0, "target": 2.0, "entry": 1.5, "entry_t": rel - 60},
                         rel - 60, rel - 60)
            check("e. funded: ATLAS entry inside -2/+2 min of a Tier-1 release refused", bool(g) and "news" in g, g)
            check("e. funded: outside the window no news block", FA.news_at(rel - 400) is None and FA.news_at(rel + 121) is None)
            check("e. eval: no news ban (MFFU allows news in the eval)", A.news_at(rel) is None)
        finally:
            MA.tier1_releases = old
        a1 = rapid.payout_advice(53700.0)
        check("e. payout: $53,700 -> request $600 ($540 to you), keeps $53,100 in", a1["ready"] and a1["request"] == 600
              and a1["to_you"] == 540.0 and a1["keep_at"] == 53100.0, a1)
        a2 = rapid.payout_advice(53400.0)
        check("e. payout: $53,400 -> nothing yet ($500 minimum above $53,100)", not a2["ready"] and a2["to_next"] == 200.0, a2)
        FA.closes.append(["2026-10-02", ts(2026, 10, 2, 11, 0), 3700.0, ts(2026, 10, 2, 10, 0)])
        fv = FA.funded_view(T0)
        check("e. funded tracker on the shared book: request $600 today", fv["ready"] and fv["request"] == 600.0, fv)
        s3 = FA.size({"risk_pts": 10.0, "tgt_pts": 20.0}, FA._state_raw(T0))
        check("e. funded ATLAS: $500 risk, no best-day cap", s3["qty"] == 22, s3)
        review_checks(tmp, clock, b, fb)
        same_account_sim(tmp)
    finally:
        MA.ADAPTER_FACTORY = None
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
