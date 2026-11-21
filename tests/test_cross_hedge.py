"""No long + short across accounts when an EXTRA LIT account enters against ATLAS on another account (night-rehearse 2026-11-18).

    python -X utf8 -m tests.test_cross_hedge          # ~5 s, paper bot, temp files, made-up names

Found by tools/rehearse_day.py on 2026-10-06 (ATLAS long 04:10 on the funded 25K, LIT short 04:32): the extra accounts route in
their own threads (engine/multi_account.AccountRouter.begin) and checked only each other and the bot's own account, so the 25K #2
eval went SHORT while ATLAS's funded 25K was still LONG: for 5 min when NinjaTrader confirmed ATLAS's close late, for the whole
trade when Zlarior's 50K was stood down (passed: the bot's own LIT never ran its hedge close). MFFU bans long + short across
your own accounts. Now: the extra account waits (tried again each poll up to LIT's entry deadline, then HEDGE BLOCKED) and the
router starts the bot's hedge close itself (LiveBot._hedge_clear) before the account threads run.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import multi_account as MA  # noqa: E402
from engine.live import LiveBot  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []
DAY = "2026-10-06"


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)


def ts(h, mi, s=0):
    return int(dt.datetime(2026, 10, 6, h, mi, s, tzinfo=ET).timestamp())


T0 = ts(4, 30)                      # LIT's SHORT (5m entry bar)
TB = ts(4, 10)                      # ATLAS's LONG on its own account


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def short_pos(entry_t=T0):
    return {"entry_t": entry_t, "dir": -1, "qty": 5, "entry": 31384.0, "stop": 31408.5, "stop0": 31408.5, "target": 31100.0,
            "risk_pts": 24.5, "be": False}


def make(tmp, clock):
    MA.ADAPTER_FACTORY = None
    keep, clock.t = clock.t, T0 - 600            # the bot runs from before the entry (an entry before the start is not taken)
    b = LiveBot()
    b.clock = clock
    b.state_path = os.path.join(tmp, "live_state.json")
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955},
           "accounts_parallel": False, "account_b": None, "account_c": None, "fleet": None,
           "accounts": [{"id": "b25k_2", "name": "Zlarior Builder 25K #2", "adapter": "paper", "preset": "mffu_builder_25k",
                         "mode": "two_week", "eval_start": DAY}]}
    r = b.start(cfg, spawn=False)
    clock.t = keep
    assert r.get("ok"), r
    ls = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
    b._lit_sizing = {**ls, "mode": "two_week", "eval_start": DAY}
    return b


def atlas(d=1, open_t=TB):
    return types.SimpleNamespace(name="SimATLAS", open_t=open_t, prov={TB: {"dir": d}} if open_t else {})


def sells(acc):
    return [r for r in acc.ledger if r.get("side") in ("buy", "sell")]


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="xhedge_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        clock = Clock(T0 + 303)
        b = make(os.path.join(tmp, "a"), clock)
        acc = b.accts.accounts[0]
        R = b.accts
        check("others_opposite: ATLAS long on another account vs a LIT SHORT -> who",
              "ATLAS's 25K" in str(R.others_opposite(-1, acc)) if (setattr(b, "acct_b", atlas(1)) or True) else False,
              R.others_opposite(-1, acc))
        check("others_opposite: same side (LIT LONG) -> None", R.others_opposite(1, acc) is None)
        b.acct_b = atlas(0)
        check("others_opposite: ATLAS's side unknown -> fails closed", R.others_opposite(1, acc) is not None)
        b.acct_b = atlas(1)
        acc.spec = {**acc.spec, "nt_account": "SimATLAS"}
        check("others_opposite: ATLAS on the SAME account is the lane's own shared() job, not this check",
              R.others_opposite(-1, acc) is None)
        acc.spec = {**acc.spec, "nt_account": ""}

        # 1. ATLAS long, its close NOT confirmed: the extra account waits, the router started the bot's hedge close
        calls = []
        b._hedge_clear = lambda ent, sym, now: (calls.append((ent["entry_t"], now)), False)[1]
        b.state = {"model": "lit", "position": short_pos(), "lit": {}}
        R.route({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        check("ATLAS long, close unconfirmed: the 25K #2 does NOT go short", not sells(acc), acc.ledger)
        check("... it waits (tried again next poll), nothing blocked", ("entry", T0) not in acc.seen and T0 not in acc.blocked
              and T0 in acc.hedge_wait)
        check("... and the router started the hedge close itself (also when the bot's own account takes no entry)",
              calls and calls[0][0] == T0, calls)
        # 2. ATLAS's close confirmed: the next poll routes the short
        clock.t = T0 + 363
        b.acct_b = atlas(1, open_t=None)
        n_calls = len(calls)
        R.route({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        s = sells(acc)
        check("ATLAS flat: the 25K #2 goes short on the next poll", len(s) == 1 and s[0]["side"] == "sell" and acc.open_t == T0, acc.ledger)
        check("... no hedge close asked when nobody holds the other side", len(calls) == n_calls)

        # 3. ATLAS still long past LIT's entry deadline: skipped with HEDGE BLOCKED, never routed
        b2 = make(os.path.join(tmp, "b"), clock)
        a2 = b2.accts.accounts[0]
        b2._hedge_clear = lambda ent, sym, now: False
        b2.acct_b = atlas(1)
        b2.state = {"model": "lit", "position": short_pos(), "lit": {}}
        clock.t = T0 + 303
        b2.accts.route({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        clock.t = T0 + 300 + 2 * 300 + 61 + 300
        b2.accts.route({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        check("ATLAS never confirmed flat: past the deadline the entry is skipped (HEDGE BLOCKED), never routed",
              not sells(a2) and T0 in a2.blocked, a2.ledger)

        # 4. ATLAS on the same side: routed at once, no wait, no close
        b3 = make(os.path.join(tmp, "c"), clock)
        a3 = b3.accts.accounts[0]
        c3 = []
        b3._hedge_clear = lambda ent, sym, now: (c3.append(1), True)[1]
        b3.acct_b = atlas(-1)
        b3.state = {"model": "lit", "position": short_pos(), "lit": {}}
        clock.t = T0 + 303
        b3.accts.route({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        check("ATLAS short too (same side): the 25K #2 shorts at once, ATLAS untouched", len(sells(a3)) == 1 and not c3, (a3.ledger, c3))

        # 5. the Rapid's ATLAS on another account and BLITZ (account C) count the same way
        b3.acct_b = None
        b3.acct_r = types.SimpleNamespace(name="SimRAPID", open_t=TB, prov={TB: {"dir": 1}})
        check("ATLAS on the Rapid EOD (another account) long vs LIT SHORT -> held", "Rapid" in str(b3.accts.others_opposite(-1, a3)))
        b3.acct_r = None
        b3.acct_c = types.SimpleNamespace(name="SimBLITZ", open_t=TB, prov={TB: {"dir": 1}})
        check("BLITZ (account C) long vs LIT SHORT -> held", "BLITZ" in str(b3.accts.others_opposite(-1, a3)))
    finally:
        MA.ADAPTER_FACTORY = None
        os.environ.pop("LE_LIT_LEARNING", None)
        shutil.rmtree(tmp, ignore_errors=True)
    # 6. hand trades (day-redteam2 2026-11-20): NinjaTrader's own position files, tests/test_hand_hedge.py
    print("hand trades (engine/hand_hedge.py):", flush=True)
    from tests import test_hand_hedge
    hand_ok = test_hand_hedge.main() == 0
    ok = all(RESULTS) and hand_ok
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + (" + hand trades" if hand_ok else " (hand trades FAILED)") + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
