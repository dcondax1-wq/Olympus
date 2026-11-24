"""day-ledgerfix (2026-11-24, research/writeups/livegap-2026-11-24.md "two bookkeeping bugs" + the armed record). Fake clock, temp
files, no NinjaTrader, never the owner's phone.

    python -X utf8 -m tests.test_ledgerfix

  1. a MODEL entry the bot never routed (Nov 16 06:20 ET, "entered during a gap") whose exit shows up days later (Nov 20 10:44
     ET) sends NO flatten and books no row (engine/live.unrouted_exit_skip, LiveBot + engine/multi_account); today's entry with
     an unknown broker state keeps the old "in case" flatten; a flat NinjaTrader account sends nothing.
  2. never a ledger / close row in an account for a trade before its eval started, and the one-time repair of the copied
     Nov 16 -$129.40 on Zlarior 25K #2 (engine/multi_account.Account.restore).
  3. the 01:55 / 09:00 armed + routed rows are kept per day (logs/arm_daily.json) and ride the PC feed ("arm", masked).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:600]}"), flush=True)


def ts(y, m, d, hh, mm=0, ss=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


def _nt(*sides, bracket=False):
    return SimpleNamespace(positions=lambda: {"ok": True, "positions": [{"instrument": "MNQ 12-26", "side": s, "qty": 0 if s == "FLAT" else 1}
                                                                        for s in sides]},
                           has_open_bracket=lambda *a: bracket)


def t_skip():
    print("1. un-routed model entry: no order for a position the broker never had", flush=True)
    from engine.live import unrouted_exit_skip as U
    e16, n20 = ts(2026, 11, 16, 6, 20), ts(2026, 11, 20, 10, 44)
    check("Nov 16 06:20 entry, exit seen Nov 20 10:44 -> dropped (an ended session), whatever the broker shows",
          U(_nt("LONG"), e16, n20) and "2026-11-16" in U(_nt("LONG"), e16, n20))
    e, n = ts(2026, 11, 20, 6, 20), ts(2026, 11, 20, 7, 0)
    check("today's entry, NinjaTrader shows the account FLAT and no bracket -> no order", bool(U(_nt("FLAT"), e, n)))
    check("today's entry, NinjaTrader shows a position -> the 'in case' flatten stays (None)", U(_nt("FLAT", "LONG"), e, n) is None)
    check("today's entry, no position files at all (never proves flat) -> flatten stays", U(_nt(), e, n) is None)
    check("today's entry, flat but a bracket of ours open -> flatten stays", U(_nt("FLAT", bracket=True), e, n) is None)
    check("an adapter without positions() (Tradovate / tests) -> flatten stays", U(SimpleNamespace(), e, n) is None)
    check("18:00 ET rolls the session: a 17:30 entry seen at 18:30 is an ended session",
          bool(U(_nt("LONG"), ts(2026, 11, 20, 15, 30), ts(2026, 11, 20, 18, 30))))
    # the extra-account path (engine/multi_account.Account._process), the livegap case
    from engine import multi_account as MA
    clock = {"t": ts(2026, 11, 20, 10, 44)}
    sent, logs = [], []

    class R:
        bot = SimpleNamespace(fleet=None)
        def clock(self): return clock["t"]
        def log(self, kind, text): logs.append(text)
        def save(self): pass
        def killed(self): return False
        def opposite_open(self, *a, **k): return None
        def others_opposite(self, *a, **k): return None
        def notify_outcome(self, *a, **k): pass

    spec = {"id": "z50k", "name": "Zlarior 50K", "rules": {"news_ban": None}, "mode": "eval", "adapter": "ninjatrader"}
    acc = MA.Account(spec, R())
    acc.added_t = 0
    acc.adapter = SimpleNamespace(route_all_exits=True, send=lambda a: sent.append(a) or {"ok": True})
    tr = {"entry_t": ts(2026, 11, 16, 6, 20), "exit_t": clock["t"] - 30, "exit_reason": "TIME", "qty": 1, "pnl": 12.0, "dir": 1}
    ctx = {"res": {"trades": [tr]}, "sym": "NQ", "now": clock["t"], "secs": 300, "state": {}, "flat_mod": 955,
           "start": ts(2026, 11, 16, 1, 0), "fill_bar_seen": lambda t: True}
    acc._process(ctx)
    check("extra account: the Nov 16 un-routed entry's exit on Nov 20 -> no CLOSEPOSITION, no ledger row, no close",
          not sent and not acc.ledger and not acc.closes, (sent, acc.ledger))
    check("...and one log line says why", any("never routed" in x and "no flatten" in x for x in logs), logs)
    tr2 = {**tr, "entry_t": clock["t"] - 600, "exit_t": clock["t"] - 30}
    acc2 = MA.Account({**spec, "id": "z2"}, R())
    acc2.added_t = 0
    acc2.adapter = SimpleNamespace(route_all_exits=True, send=lambda a: sent.append(a) or {"ok": True})
    acc2._process({**ctx, "res": {"trades": [tr2]}})
    ex = [a for a in sent if a.get("side") == "exit"]
    check("today's un-routed entry, broker state unknown -> the safety flatten still goes, at $0", len(ex) == 1 and ex[0].get("pnl") == 0.0, sent)


def t_eval_start():
    print("2. never a row before the account's eval start; the one-time repair", flush=True)
    from engine import multi_account as MA
    clock = {"t": ts(2026, 11, 18, 9, 0)}
    sent, logs = [], []

    class R:
        bot = SimpleNamespace(fleet=None)
        def clock(self): return clock["t"]
        def log(self, kind, text): logs.append(text)
        def save(self): pass
        def killed(self): return False
        def opposite_open(self, *a, **k): return None
        def others_opposite(self, *a, **k): return None
        def notify_outcome(self, *a, **k): pass

    spec = {"id": "b25k_2", "name": "Zlarior 25K #2", "rules": {"news_ban": None}, "mode": "eval", "adapter": "ninjatrader",
            "eval_start": "2026-11-18", "nt_account": "MFFUEVX0001234"}
    acc = MA.Account(spec, R())
    acc.added_t = 0                                     # even with no join time (a restart): the eval start decides
    acc.adapter = SimpleNamespace(route_all_exits=True, send=lambda a: sent.append(a) or {"ok": True})
    acc.seen.add(("entry", ts(2026, 11, 16, 6, 16)))   # worst case: it even thinks it routed it
    old = {"entry_t": ts(2026, 11, 16, 6, 16), "exit_t": clock["t"] - 60, "exit_reason": "STOP", "qty": 1, "pnl": -129.4, "dir": 1}
    acc._process({"res": {"trades": [old]}, "sym": "NQ", "now": clock["t"], "secs": 300, "state": {}, "flat_mod": 955,
                  "start": ts(2026, 11, 16, 1, 0), "fill_bar_seen": lambda t: True})
    check("Nov 16 06:16 trade on an account whose eval started Nov 18 -> no order, no ledger row, no close",
          not sent and not acc.ledger and not acc.closes, (sent, acc.ledger, acc.closes))
    good = ["2026-11-19", ts(2026, 11, 19, 7, 0), 55.0, ts(2026, 11, 19, 6, 30)]
    bad = ["2026-11-16", ts(2026, 11, 16, 7, 0), -129.4, ts(2026, 11, 16, 6, 16)]
    acc2 = MA.Account(spec, R())
    acc2.restore({"nt_account": spec["nt_account"], "day": "2026-11-19", "closes": [bad, good], "ledger": []}, "2026-11-24")
    check("repair: the copied Nov 16 -$129.40 close is removed when the account loads; its own Nov 19 close stays",
          acc2.closes == [good], acc2.closes)
    check("...with one log line naming it", any("removed" in x and "-129.40" in x for x in logs), logs)
    acc3 = MA.Account({**spec, "eval_start": ""}, R())
    acc3.restore({"nt_account": spec["nt_account"], "day": "2026-11-19", "closes": [bad, good], "ledger": []}, "2026-11-24")
    check("an account with no eval start keeps every close (nothing to compare)", len(acc3.closes) == 2, acc3.closes)


def t_arm(tmp):
    print("3. the armed + routed record (logs + the PC feed)", flush=True)
    from engine import live_guard as LG
    p = os.path.join(tmp, "arm_daily.json")
    rows = [{"label": "Zlarior (LIT)", "account": "...6018", "armed": True, "routed": True, "why": ""},
            {"label": "Rapid EOD 25K (LIT)", "account": "?", "armed": False, "routed": False, "why": "not armed at START"}]
    t1 = ts(2026, 11, 25, 1, 55)
    LG.save_arm(rows, t1, path=p)
    LG.save_arm(rows[:1], ts(2026, 11, 25, 9, 0), path=p)
    d = json.load(open(p))
    check("both slots of the day are kept (01:55 and 09:00)", sorted(d["days"]["2026-11-25"]) == ["01:55", "09:00"], d)
    tiny = LG.arm_tiny(p, now=ts(2026, 11, 25, 9, 5))
    check("feed block: the last check, one short row per account, ids masked", tiny and tiny["s"] == "09:00"
          and tiny["a"][0][:4] == ["Zlarior (LIT)", "...6018", 1, 1] and len(json.dumps(tiny)) < 400, tiny)
    check("older than 36 h -> not in the feed", LG.arm_tiny(p, now=ts(2026, 11, 27, 9, 5)) is None)
    for i in range(40):
        LG.save_arm(rows, t1 + (i + 1) * 86400, path=p)
    check("30 days kept at most", len(json.load(open(p))["days"]) == 30)
    sent = []
    g = LG.LiveGuard(send=lambda x: sent.append(x) or "sent", state_path=os.path.join(tmp, "lg.json"),
                     au_path=os.path.join(tmp, "none.json"), arm_path=os.path.join(tmp, "arm2.json"))
    bot = SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "armed": True, "nt_account": "Sim101"}, seen=set(), state={},
                          accts=None, acct_b=None, acct_r=None, acct_r2=None)
    g.step(bot, ts(2026, 11, 25, 1, 56))
    d2 = json.load(open(os.path.join(tmp, "arm2.json")))
    check("the 01:55 check writes its rows and sends its line", d2["last"]["slot"] == "01:56" and any(x["code"] == "armed" for x in sent),
          (d2, sent))
    from tools import pc_report as PR
    import inspect
    check("pc_report puts live_guard.arm_tiny() in the feed as 'arm'", "arm_tiny()" in inspect.getsource(PR))


def main():
    tmp = tempfile.mkdtemp(prefix="ledgerfix_")
    try:
        for f in (t_skip, t_eval_start, lambda: t_arm(tmp)):
            try:
                f()
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{getattr(f, '__name__', 'test')} ran", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"\nledgerfix: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
