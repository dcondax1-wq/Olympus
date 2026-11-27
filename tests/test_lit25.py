"""LIT also trades ATLAS's FUNDED Builder 25K (engine/lit25.py), OFF until data/lit25.json says {"on": true}.

    python -X utf8 -m tests.test_lit25            # unit checks + paper LiveBots (~10 s)

Paper bots, temp files, Sim names only: nothing routed to a real NinjaTrader, nothing real armed.
  a. off by default; ON in the eval stage changes nothing; the switch file never holds the phrase
  b. ON + funded: LIT's lane (preset mffu_builder_25k, funded) + ATLAS (SharedAtlas) on the same account; ONE book
  c. ATLAS sizing min($250, 30% of the room, the day left); LIT's lane = the 25K funded preset
  d. never two positions: ATLAS blocked while LIT holds / enters; LIT entering closes ATLAS first (any side), then routes
  e. arming follows ATLAS's 25K only (the bot never arms)
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

from engine import account_b as AB, lit25, multi_account as MA  # noqa: E402
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


T0 = ts(2026, 11, 19, 10, 0)
DAY = "2026-11-19"
EVAL_B = {"account": "Sim102", "plan": "builder25k", "eval_start": "2026-11-04", "sizing": "need",
          "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]}
FUNDED_B = {**EVAL_B, "account": "Sim107", "stage": "funded", "funded_start": "2026-11-18", "payouts": {},
            "eval_account": "Sim102"}


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def pos_at(entry_t, qty=5, entry=25020.0, stop=24990.0, target=25220.0, d=1):
    return {"entry_t": entry_t, "dir": d, "qty": qty, "entry": entry, "stop": stop, "stop0": stop, "target": target,
            "risk_pts": abs(entry - stop), "be": False}


def make_bot(tmp, clock, ab, on):
    os.makedirs(tmp, exist_ok=True)
    MA.ADAPTER_FACTORY = None
    b = LiveBot()
    b.clock = clock
    b.state_path = os.path.join(tmp, "live_state.json")
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955},
           "accounts_parallel": False, "account_b": ab, "account_c": None, "fleet": None, "rapid": None}
    if on is not None:
        cfg["lit25"] = {"on": on}
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    ls = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
    b._lit_sizing = {**ls, "mode": "normal"}
    return b


def lane(b):
    return next((a for a in (getattr(b.accts, "accounts", None) or []) if a.spec.get("lane") == "lit25"), None)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="lit25_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        clock = Clock(T0 + 290)
        # ---- a. off by default
        fp = os.path.join(tmp, "lit25.json")
        check("a. missing data/lit25.json = OFF", lit25.is_on(fp) is False)
        b0 = make_bot(os.path.join(tmp, "b0"), clock, FUNDED_B, None)
        check("a. test bot without the key: no lane, ATLAS is the plain account B",
              lane(b0) is None and type(b0.acct_b) is AB.AccountB, type(b0.acct_b))
        b1 = make_bot(os.path.join(tmp, "b1"), clock, FUNDED_B, False)
        check("a. switch off: no lane, plain account B", lane(b1) is None and type(b1.acct_b) is AB.AccountB)
        b2 = make_bot(os.path.join(tmp, "b2"), clock, EVAL_B, True)
        check("a. ON while ATLAS's 25K is in its eval: nothing changes (idle)", lane(b2) is None and type(b2.acct_b) is AB.AccountB)
        check("a. idle reason says so", "eval stage" in (lit25.why_idle(AB.normalize(EVAL_B)) or ""))
        lit25.save(True, fp)
        check("a. --on writes only {on: true}", lit25.is_on(fp) and LIVE_PHRASE not in open(fp, encoding="utf-8").read())
        lit25.save(False, fp)
        check("a. --off: OFF again", lit25.is_on(fp) is False)

        # ---- b. ON + funded: both lanes, one book
        b = make_bot(os.path.join(tmp, "b3"), clock, FUNDED_B, True)
        L, A = lane(b), b.acct_b
        check("b. ON + funded: LIT's lane + ATLAS on the same funded 25K",
              L is not None and isinstance(A, lit25.SharedAtlas) and L.spec["nt_account"] == A.name == "Sim107"
              and A.problem is None and L.problem is None, (A and A.problem, L and L.problem))
        check("b. lane: preset Builder 25K, funded from ATLAS's funded start", L.spec["preset"] == "mffu_builder_25k" and L.mode == "funded"
              and L.start_day() == "2026-11-18", (L.spec.get("preset"), L.mode, L.start_day()))
        check("b. ATLAS keeps its own order tag / state file", A.adapter_cfg()["nt_file_tag"] == "acctb_" and A.state_path.endswith("_acctb.json"))
        check("b. multi_account.shared(): the lane sees ATLAS", L.shared() is A)
        L.closes.append([DAY, T0 - 3600, 300.0, T0 - 4000])
        check("b. ATLAS sees LIT's closed $ (one day P&L, one funded balance)", A.day_pnl(DAY) == 300.0
              and A._state_raw(T0)["cum"] == 300.0 and A.funded_days(DAY).get(DAY) == 300.0)
        A.closes.append([DAY, T0 - 1800, -100.0, T0 - 2000])
        check("b. LIT's lane sees ATLAS's closed $", L.day_pnl(DAY) == 200.0 and L.state(DAY)["cum"] == 200.0)
        fv = A.funded_view(T0)
        check("b. ATLAS's payout tracker counts both", abs(float(fv["balance"]) - 25200.0) < 1e-6, fv.get("balance"))
        L.closes.clear()
        A.closes.clear()

        # ---- c. sizing
        st = A._state_raw(T0)
        s1 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, st)
        check("c. ATLAS $250 on a 10-pt stop (fresh funded, room $1,000): 11 micros (250 / 22.4)", s1["qty"] == 11, s1)
        s2 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, {**st, "room": 500.0})
        check("c. room $500: 30% = $150 -> 6 micros", s2["qty"] == 6, s2)
        s3 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, {**st, "cum": -500.0})
        check("c. -$500 today: $100 of the $600 soft day left -> 4 micros", s3["qty"] == 4, s3)
        q = L.qty_for({**pos_at(T0), "tgt_pts": 200.0}, T0 + 300)
        ref = AB.funded_qty(AB.normalize(FUNDED_B), {"risk_pts": 30.0, "tgt_pts": 200.0}, A._state_raw(T0))
        check("c. LIT's lane = the 25K funded rule at ATLAS's room share: same micros as account B's funded rule",
              q == ref["qty"] and 1 <= q <= 20, (q, ref, L.last_size))
        # day-alloc 2026-11-26 (lead): the lane follows the owner's 40% FUNDED_ON room, not the preset's 60%. A case where the
        # $1,000 winner cap does not bind: 30-pt stop, 30-pt target, room $1,000 -> 40% = $400 x 20/30 (ref stop) = $267 / $60 = 4
        # micros (the preset's 60% would be $600 x 20/30 = $400 / $60 = 6)
        q40 = L.qty_for({**pos_at(T0), "tgt_pts": 30.0}, T0 + 300)
        ref40 = AB.funded_qty(AB.normalize(FUNDED_B), {"risk_pts": 30.0, "tgt_pts": 30.0}, A._state_raw(T0))
        check("c. the lane sizes at ATLAS's 40% funded room (4 micros at $1,000 room / 30-pt stop, 60% would be 6), = account B",
              q40 == ref40["qty"] == 4 and (L.spec.get("lit_sizing") or {}).get("funded", {}).get("pct") == 0.4,
              (q40, ref40, L.spec.get("lit_sizing"), L.last_size))

        # ---- d. never two positions on the account
        b.state = {"model": "lit", "position": None, "lit": {}}
        check("d. LIT flat, no setup: ATLAS may enter", A.lit_opposite(1) is None, A.lit_opposite(1))
        L.open_t = T0 - 600
        check("d. LIT's lane holds a trade: ATLAS blocked (either side)", A.lit_opposite(1) and A.lit_opposite(-1))
        L.open_t = None
        b.state = {"model": "lit", "position": pos_at(T0 - 600), "lit": {}}
        check("d. LIT in a trade (on the 50K): ATLAS blocked here too", bool(A.lit_opposite(1)) and bool(A.lit_opposite(-1)))
        b.state = {"model": "lit", "position": None, "lit": {}, "setups": {"short": {"tapped_t": None}}}
        check("d. LIT short setup armed: ATLAS long blocked, short allowed", bool(A.lit_opposite(1)) and A.lit_opposite(-1) is None)
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
        check("d. LIT enters LONG while ATLAS holds LONG: ATLAS closed at market first (HEDGE), then LIT's lane routed",
              A.open_t is None and ex and ex[0]["reason"] == "HEDGE" and ent_l and L.open_t == T0
              and ex[0]["t"] <= ent_l[0]["t"], (A.open_t, ex, ent_l, L.last_size))

        # ---- e. arming
        sp = AB.normalize({**FUNDED_B, "armed": True})
        ls = lit25.lane_spec(sp, {"adapter": "ninjatrader", "confirm": LIVE_PHRASE})
        check("e. ATLAS's 25K armed (owner typed the phrase): the lane is armed with this start's phrase (memory only)",
              ls["armed"] is True and ls["confirm"] == LIVE_PHRASE)
        ls2 = lit25.lane_spec(AB.normalize(FUNDED_B), {"adapter": "ninjatrader", "confirm": LIVE_PHRASE})
        check("e. ATLAS's 25K not armed: the lane is not armed and gets no phrase", ls2["armed"] is False and "confirm" not in ls2)
        check("e. a paper bot: the lane is paper", lit25.lane_spec(sp, {"adapter": "paper"})["adapter"] == "paper")
    finally:
        MA.ADAPTER_FACTORY = None
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
