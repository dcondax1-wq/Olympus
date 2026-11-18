"""MFFU account lifecycle (engine/lifecycle.py + engine/ninjatrader.locked_reject): every routed account knows PASSED / FAILED /
LOCKED / PAYOUT READY / MFFU flat time, stands down on its own and tells the owner once.

    python -X utf8 -m tests.test_lifecycle        (~10 s; paper bots + a simulated NinjaTrader on Sim names, temp files)

  a. the pure checks: the rule numbers, pass (min days, Rapid 4 days + 30% best day), fail at the floor, MFFU's hours,
     funded payout (buffer + minimum + consistency + days; the Rapid's $1,000 cushion, once a day)
  b. PASS replay: the bot's book lags, NinjaTrader shows $26,946.10 -> PASSED, one push "ATLAS 25K PASSED: $26,946 ... Send Claude the
     new account name", board event, no more ATLAS entries; LIT keeps trading; account B's own pass push is not doubled
  c. LOCKED replay on a simulated NinjaTrader (Sim): the entry REJECTED with "...Limit: 0 Current: 1. Scope: MNQ Rule #3787" in
     NinjaTrader's Log -> LOCKED at once, one push, no retries, the generic "order NOT placed" push is not sent; a plain
     rejection is not a lock; a refusal at 16:30 ET (MFFU flat time) is never a lock
  d. FAIL replay: an extra 25K account at its $24,000 floor -> FAILED, its entry_block stands down, the others trade
  e. PAYOUT READY replay: an extra funded Builder 50K: up to $700 ($560 to you), the rules listed; once per cycle
  f. persistence (data/lifecycle.json survives a restart, sticky), a new account Name = a fresh row, the heartbeat "life"
     block (small, no account Name), the PC report pushes its events to ntfy once, notify maps the keys
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
os.environ["LE_PR_NO_NET"] = "1"

from engine import lifecycle as LC  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine.live import LiveBot  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
MFFU_TEXT = ("Your maximum order quantity has been met. Please contact support. Limit: 0 Current: 1. Scope: MNQ Rule #3787")


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:500]})" if info and not cond else ""))
    return bool(cond)


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def make_bot(tmp, clock, extra=None):
    os.makedirs(tmp, exist_ok=True)
    MA.ADAPTER_FACTORY = None
    b = LiveBot()
    b.clock = clock
    b.state_path = os.path.join(tmp, "live_state.json")
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955},
           "accounts_parallel": False, "account_c": None, "fleet": None, "rapid": None,
           "account_b": {"account": "Sim102", "plan": "builder25k", "eval_start": "2026-11-12",
                         "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "sizing": "need"}, **(extra or {})}
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    pushes = []
    b._push_send = pushes.append                 # the harness never sends; record what the real bot would
    book = LC.book_for(b)
    book.send = pushes.append
    board = []
    book.emit = lambda kind, key, text, data=None: board.append((kind, key, text, data))
    return b, pushes, board


# ============================================================================================== a pure
def pure():
    L25, L50, LR = LC.limits("builder25k"), LC.limits("mffu_builder_50k"), LC.limits("rapideod50k")
    check("a. rule numbers: 25K target $1,500 / buffer $1,100 / min $250 / max $1,000; 50K $3,000 / $2,100 / $500 / $2,000; "
          "Rapid 4 days, 30% best day, $1,000 cushion, 90%",
          (L25["target"], L25["buffer"], L25["pay_min"], L25["pay_max"], L25["start"]) == (1500, 1100, 250, 1000, 25000)
          and (L50["target"], L50["buffer"], L50["pay_min"], L50["pay_max"]) == (3000, 2100, 500, 2000)
          and (LR["min_days"], LR["best_day"], LR["cushion"], LR["split"]) == (4, 0.3, 1000, 0.9), (L25, L50, LR))
    base = {"kind": "eval", "start": 25000.0, "target": 1500.0, "floor": 24000.0, "days_traded": 5, "min_days": 1}
    d = LC.detect({**base, "balance": 26100.0, "real_balance": 26946.10})
    check("a. ATLAS's day: NinjaTrader's $26,946.10 >= $26,500 -> passed (the real cash wins over a lagging ledger)",
          d["stage"] == "passed" and d["src"] == "NinjaTrader" and d["balance"] == 26946.10, d)
    check("a. under the target -> eval; at the floor -> failed",
          LC.detect({**base, "balance": 26100.0})["stage"] == "eval" and LC.detect({**base, "balance": 24000.0})["stage"] == "failed")
    r = {"kind": "eval", "start": 50000.0, "target": 3000.0, "floor": 48000.0, "min_days": 4, "best_day_rule": 0.3}
    check("a. Rapid: the target with 3 days or a 40% best day waits; 4 days and a 25% best day passes",
          LC.detect({**r, "balance": 53200.0, "days_traded": 3, "best_day": 800.0})["stage"] == "eval"
          and LC.detect({**r, "balance": 53200.0, "days_traded": 5, "best_day": 1280.0})["stage"] == "eval"
          and LC.detect({**r, "balance": 53200.0, "days_traded": 5, "best_day": 800.0})["stage"] == "passed")
    check("a. MFFU hours: 16:10-18:00 ET and Fri 16:10 - Sun 18:00 are flat time; 10:00 and 18:05 are not",
          LC.outside_hours(ts(2026, 11, 18, 16, 10)) and LC.outside_hours(ts(2026, 11, 18, 17, 59))
          and LC.outside_hours(ts(2026, 11, 21, 12, 0)) and LC.outside_hours(ts(2026, 11, 22, 17, 0))
          and not LC.outside_hours(ts(2026, 11, 18, 10, 0)) and not LC.outside_hours(ts(2026, 11, 18, 18, 5))
          and not LC.outside_hours(ts(2026, 11, 22, 18, 5)) and not LC.outside_hours(ts(2026, 11, 18, 16, 9)))
    p = LC.payout_check(53000.0, L50, cycle_profit=2800.0, best_day=1000.0, cycle_days=3)
    q = LC.payout_check(53000.0, L50, cycle_profit=2800.0, best_day=1500.0, cycle_days=3)
    pr = LC.payout_check(53700.0, LR)
    pr2 = LC.payout_check(53700.0, LR, paid_today=True)
    check("a. payout: 50K at $53,000 = up to $900 ($720 to you); a 54% best day = not ready; Rapid keeps $53,100: $600 "
          "($540), not twice a day",
          p["ok"] and p["amount"] == 900 and p["to_you"] == 720 and not q["ok"] and q["amount"] == 0
          and pr["ok"] and pr["amount"] == 600 and pr["to_you"] == 540 and not pr2["ok"], (p, q, pr, pr2))
    t, b = LC.texts("passed", "ATLAS 25K", {"balance": 26946.10})
    check("a. the PASSED text: 'ATLAS 25K PASSED: $26,946' + 'MFFU locks it until the funded account is issued. Send Claude "
          "the new account name.'", t == "ATLAS 25K PASSED: $26,946" and b.startswith("MFFU locks it until the funded account is "
                                                                                     "issued. Send Claude the new account name."), (t, b))


# ============================================================================================== b pass
class FakeBroker:
    """NinjaTrader's accounts.csv row (engine/broker_balance.Broker.row) for one account: the real cash."""

    def __init__(self, cash):
        self.cash = cash

    def row(self, name, rules=None, now=None):
        return {"name": name, "cash": self.cash, "fresh": True}


def pass_replay(tmp):
    clock = Clock(ts(2026, 11, 17, 11, 0))
    bot, pushes, board = make_bot(os.path.join(tmp, "pass"), clock)
    ab = bot.acct_b
    check("b. paper bot with ATLAS (account B, Builder 25K) up", ab is not None and not ab.problem, getattr(ab, "problem", None))
    # the 2026-11-17 bug: the bot's book lagged (+$1,100 booked) while NinjaTrader's account showed $26,946.10
    ab.closes = [["2026-11-12", ts(2026, 11, 12, 10, 0), 600.0, ts(2026, 11, 12, 9, 40)],
                 ["2026-11-13", ts(2026, 11, 13, 10, 0), 500.0, ts(2026, 11, 13, 9, 40)]]
    ab._broker = lambda: FakeBroker(26946.10)
    ev0 = ab.eval_view(clock.t)
    ab._lifecycle(clock.t)
    check("b. ATLAS's own book: $26,100, still 'open' (it never saw the pass: nobody was told)",
          abs(ev0["balance"] - 26100.0) < 0.01 and ev0["status"] == "open" and not pushes, (ev0, pushes))
    evs = LC.tick(bot, clock.t, force=True)
    atl = [p for p in pushes if "ATLAS" in p.get("title", "")]
    check("b. PASSED from NinjaTrader's $26,946.10: one push 'ATLAS 25K PASSED: $26,946' saying MFFU locks it and to send "
          "Claude the new account name",
          [e["stage"] for e in evs if e["key"] == "atlas"] == ["passed"] and len(atl) == 1
          and atl[0]["title"] == "ATLAS 25K PASSED: $26,946" and "Send Claude the new account name" in atl[0]["body"], (evs, pushes))
    check("b. board event life_passed for 'atlas' with the real balance",
          any(k == "life_passed" and key == "atlas" and abs(d["balance"] - 26946.10) < 0.01 for k, key, _, d in board), board)
    clock.t += 60
    ab._lifecycle(clock.t)
    LC.tick(bot, clock.t, force=True)
    check("b. not repeated on the next polls", len(pushes) == 1, pushes)
    check("b. ATLAS stands down (no entry, no retry); LIT's account keeps trading",
          "PASSED" in str(ab.life_block(clock.t)) and bot._life_block(clock.t) is None, (ab.life_block(clock.t), bot._life_block(clock.t)))
    # the bot's own book sees the pass too (ledger caught up): account B's EVAL PASSED push, lifecycle does not double it
    clock2 = Clock(ts(2026, 11, 17, 11, 0))
    bot2, pushes2, _ = make_bot(os.path.join(tmp, "pass2"), clock2)
    ab2 = bot2.acct_b
    ab2.closes = ab.closes + [["2026-11-17", ts(2026, 11, 17, 10, 30), 846.10, ts(2026, 11, 17, 9, 45)]]
    ab2._lifecycle(clock2.t)
    LC.tick(bot2, clock2.t, force=True)
    check("b. book at $26,946.10: account B's own 'EVAL PASSED' push (now says send Claude the new account name), ONE push in "
          "all; lifecycle stage passed, ATLAS stood down",
          len(pushes2) == 1 and "EVAL PASSED" in pushes2[0]["title"] and "send Claude the new account name" in pushes2[0]["body"]
          and LC.book_for(bot2).stage("atlas") == "passed" and ab2.life_block(clock2.t), pushes2)
    return bot


# ============================================================================================== c locked
def locked_replay(tmp):
    from engine.ninjatrader import NinjaTraderAdapter, _FakeNT
    clock = Clock(ts(2026, 11, 17, 10, 5))
    bot, pushes, board = make_bot(os.path.join(tmp, "lock"), clock)
    ab = bot.acct_b
    folder = os.path.join(tmp, "lock", "nt", "NinjaTrader 8")
    fake = _FakeNT(folder)
    now = [clock.t]
    cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": folder, "nt_account": "Sim102",
           "params": {"max_micros": 20, "flat_mod": 955}, "nt_max_entries_day": 999, "nt_file_tag": "acctb_",
           "nt_state_path": os.path.join(tmp, "lock", "nt_state_b.json"), "nt_audit_log": os.path.join(tmp, "lock", "oif_b.log")}
    ad = NinjaTraderAdapter(cfg, clock=lambda: now[0])
    ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
    ad._alert_fn = lambda text: None
    ab.adapter = ad
    # a plain rejection first: not a lock
    fake.reject = {"MARKET"}
    et0 = ts(2026, 11, 17, 9, 50)
    r0 = ab.route({"sym": "NQ", "side": "buy", "qty": 2, "stop": 25000.0, "target": 25040.0, "entry": 25020.0, "entry_t": et0})
    check("c. Sim: a plain REJECTED (no risk-desk text) is not a lock", r0.get("ok") is False and LC.book_for(bot).stage("atlas") != "locked"
          and ab.life_block(clock.t) is None, (r0, LC.book_for(bot).rows))
    et1 = ts(2026, 11, 17, 10, 0)
    os.makedirs(os.path.join(folder, "log"), exist_ok=True)
    with open(os.path.join(folder, "log", "log.20261117.00000.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"2026-11-17 10:05:01:000|1|4|Order='LE{et1}x1yzE/Sim102' Name='LE{et1}x1yzE' New state='Rejected' "
                 f"Instrument='MNQ 12-26' Action='Buy' Native error='{MFFU_TEXT}'\n")
    act = {"sym": "NQ", "side": "buy", "qty": 2, "stop": 25000.0, "target": 25040.0, "entry": 25020.0, "entry_t": et1}
    ab.open_t = et1
    ab.prov[et1] = {"key": "ema_lon_vix", "short": "EMA", "qty": 2, "dir": 1, "entry": 25020.0, "t": clock.t}
    r1 = ab.route(act)
    if ab.never_placed(et1, r1):
        ab._drop_unplaced(et1, r1, clock.t)
    titles = [p.get("title") for p in pushes]
    check("c. Sim: MFFU's 'Limit: 0 ... Rule #3787' rejection -> ATLAS LOCKED at once, one push naming the reason",
          LC.book_for(bot).stage("atlas") == "locked" and titles.count("ATLAS 25K LOCKED by MFFU") == 1
          and any("Rule #3787" in p.get("body", "") for p in pushes), (r1, titles))
    check("c. the generic 'order NOT placed' push is not sent on a locked account; board event life_locked",
          not any("NOT placed" in str(t) for t in titles) and any(k == "life_locked" for k, *_ in board), (titles, board))
    k = len(fake.files)
    why = ab.life_block(clock.t + 300)
    check("c. no retries: ATLAS's entry gate says LOCKED (nothing more goes to NinjaTrader); LIT and the others keep trading",
          "LOCKED" in str(why) and bot._life_block(clock.t + 300) is None and len(fake.files) == k, why)
    # outside hours: a refusal at 16:30 ET is MFFU's flat time, never a lock
    clock2 = Clock(ts(2026, 11, 18, 16, 30))
    bot2, pushes2, _ = make_bot(os.path.join(tmp, "lock2"), clock2)
    ev = LC.after_route(bot2, "atlas", "ATLAS 25K", None, {"side": "buy", "entry_t": clock2.t},
                        {"ok": False, "error": f"MNQ 12-26: entry REJECTED ({MFFU_TEXT})"})
    check("c. 16:30 ET: the same refusal is MFFU flat time, not a lock; every account's entry gate says 'outside MFFU hours'",
          ev is None and LC.book_for(bot2).stage("atlas") != "locked" and "outside MFFU hours" in str(bot2._life_block(clock2.t))
          and "outside MFFU hours" in str(bot2.acct_b.life_block(clock2.t)) and not pushes2, (ev, pushes2))
    try:
        ad.release_lock()
    except Exception:
        pass
    return bot


# ============================================================================================== d fail, e payout
def fail_and_payout(tmp):
    clock = Clock(ts(2026, 11, 17, 11, 0))
    accts = [{"id": "b25", "name": "Builder 25K #2", "adapter": "paper", "preset": "mffu_builder_25k", "mode": "two_week",
              "eval_start": "2026-11-12", "enabled": True},
             {"id": "f50", "name": "Funded 50K", "adapter": "paper", "preset": "mffu_builder_50k", "mode": "funded",
              "funded": {"start": "2026-11-09"}, "enabled": True}]
    bot, pushes, board = make_bot(os.path.join(tmp, "extra"), clock, {"accounts": accts, "account_b": None})
    by = {a.id: a for a in bot.accts.accounts}
    check("d. two extra paper accounts up (a 25K eval, a funded 50K)", set(by) == {"b25", "f50"}, list(by))
    check("d. an extra eval waits for the sizer's 2nd day (its 1-micro minimum-days trade) before PASSED",
          LC._extra_min_days(by["b25"]) == 2, LC._extra_min_days(by["b25"]))
    by["b25"].closes = [["2026-11-12", ts(2026, 11, 12, 10, 0), -400.0, 1], ["2026-11-13", ts(2026, 11, 13, 10, 0), -600.0, 2]]
    by["f50"].closes = [["2026-11-10", ts(2026, 11, 10, 10, 0), 1000.0, 3], ["2026-11-12", ts(2026, 11, 12, 10, 0), 900.0, 4],
                        ["2026-11-13", ts(2026, 11, 13, 10, 0), 900.0, 5]]
    LC.tick(bot, clock.t, force=True)
    bk = LC.book_for(bot)
    fp = [p for p in pushes if p.get("title", "").startswith("Builder 25K #2 FAILED")]
    check("d. FAIL: the 25K at its $24,000 floor -> FAILED, one push with your price ($63), its entry gate stands down",
          bk.stage("x:b25") == "failed" and len(fp) == 1 and "$63" in fp[0]["body"] and "FAILED" in str(by["b25"].entry_block(clock.t)),
          (bk.rows.get("x:b25"), [p.get("title") for p in pushes]))
    pp = [p for p in pushes if "PAYOUT READY" in p.get("title", "")]
    check("e. PAYOUT READY: the funded 50K at $52,800 -> 'Funded 50K PAYOUT READY: up to $700', $560 to you, the rules listed",
          bk.stage("x:f50") == "payout_ready" and len(pp) == 1 and pp[0]["title"] == "Funded 50K PAYOUT READY: up to $700"
          and "$560 to you" in pp[0]["body"] and "buffer" in pp[0]["body"] and "best day" in pp[0]["body"]
          and "PAYOUT" not in str(by["f50"].entry_block(clock.t)) and "stood down" not in str(by["f50"].entry_block(clock.t)),
          (bk.rows.get("x:f50"), [p.get("title") for p in pushes]))
    clock.t += 3600
    LC.tick(bot, clock.t, force=True)
    check("e. the same cycle: no second payout push; the eval failure is not repeated",
          len([p for p in pushes if "PAYOUT READY" in p.get("title", "")]) == 1 and len([p for p in pushes if "FAILED" in p.get("title", "")]) == 1)
    return bot


# ============================================================================================== f persistence, heartbeat, ntfy
def persist_and_wire(bot_pass, bot_lock):
    bk = LC.book_for(bot_pass)
    again = LC.Book(bk.path)
    check("f. data/lifecycle.json survives a restart: ATLAS still PASSED (sticky), its push key kept (not sent again)",
          again.stage("atlas") == "passed" and any(k.startswith("life:passed:atlas:") for k in again.rows["atlas"]["notified"]), again.rows)
    ev = again.update("atlas", "ATLAS 25K", {"kind": "eval", "start": 25000.0, "target": 1500.0, "balance": 25000.0, "floor": 24000.0,
                                              "acct": "Sim102"}, now=bot_pass.clock())
    check("f. sticky: the same account under target again stays PASSED", ev is None and again.stage("atlas") == "passed")
    again.update("atlas", "ATLAS 25K", {"kind": "eval", "start": 25000.0, "target": 1500.0, "balance": 25000.0, "floor": 24000.0,
                                         "acct": "Sim199"}, now=bot_pass.clock())
    check("f. a new account Name (the owner sent it, the config has it) = a fresh row: eval, trading again",
          again.stage("atlas") == "eval" and again.block("atlas", ts(2026, 11, 17, 10, 0)) is None, again.rows.get("atlas"))
    from engine import heartbeat as HB
    hb = HB._life(bot_lock)
    raw = json.dumps(hb)
    check("f. heartbeat 'life' block: stages + the last events, small, no account Name",
          hb and hb["acc"]["atlas"]["stage"] == "locked" and len(raw) < 1500 and "Sim102" not in raw
          and hb["ev"][-1]["title"] == "ATLAS 25K LOCKED by MFFU", raw[:300])
    from tools import pc_report as PR
    now = int(bot_lock.clock()) + 60
    snap = {"t": now, "hb": {"t": now, "running": True, "life": hb}, "market_open": True, "server": True, "hb_age": 10, "nt": True,
            "fills": [], "watch": []}
    st, msgs = PR.events({"seen": {}, "seeded": True}, snap)
    life = [m for m in msgs if str(m.get("key", "")).startswith("life:")]
    st2, msgs2 = PR.events(st, snap)
    check("f. the PC report pushes the LOCKED event to ntfy once (high), not again next run",
          len(life) == 1 and life[0]["title"] == "ATLAS 25K LOCKED by MFFU" and life[0]["priority"] == "high"
          and not [m for m in msgs2 if str(m.get("key", "")).startswith("life:")], (msgs, msgs2))
    from engine import notify as N
    check("f. notify types: every life: key (payout ready, locked, passed) -> account_status: ON by default, rings in quiet hours",
          N.kind_of("life:payout_ready:x:f50:abc:2026-11-13") == "account_status" and N.kind_of("life:locked:atlas:abc") == "account_status"
          and N.on("account_status", N.merge({})) and N.rings("account_status", N.merge({})))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="lifecycle_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        pure()
        bp = pass_replay(tmp)
        bl = locked_replay(tmp)
        fail_and_payout(tmp)
        persist_and_wire(bp, bl)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
