"""Red team on day-zeroerr bc17172e (2026-11-24): the eval_start skip never drops the exit of a position the account really holds.

    python -X utf8 -m tests.test_ledgerfix_rt        (< 2 s)

1. an extra account whose eval_start is typed in the FUTURE (Nov 25) holding today's routed trade (open_t / an open NinjaTrader
   leg of ours): the model's exit still routes the flatten (FOUND: the skip came before every routed check, so that real
   position kept only its bracket and the book lost the trade).
2. the Nov 16 copied case (only "seen", no open trade, no open leg) is still skipped.
3. the one-time repair at restore() ignores an eval_start in the future (FOUND: it would drop today's real closes from the book:
   the daily loss and the room then read too good).
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

from engine import multi_account as MA  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info != '' and not ok else ''}")
    RES.append(bool(ok))


def ts(y, m, d, hh, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def run(open_t=None, legs=None, entry=None):
    clock = {"t": ts(2026, 11, 24, 11, 0)}
    sent = []

    class R:
        bot = SimpleNamespace(fleet=None)
        def clock(self): return clock["t"]
        def log(self, kind, text): pass
        def save(self): pass
        def killed(self): return False
        def opposite_open(self, *a, **k): return None
        def others_opposite(self, *a, **k): return None
        def notify_outcome(self, *a, **k): pass

    spec = {"id": "x1", "name": "Zlarior 25K #2", "rules": {"news_ban": None}, "mode": "eval", "adapter": "ninjatrader",
            "eval_start": "2026-11-25", "nt_account": "MFFUEVX0001234"}
    acc = MA.Account(spec, R())
    acc.added_t = 0
    acc.adapter = SimpleNamespace(route_all_exits=True, legs=legs or [], send=lambda a: sent.append(a) or {"ok": True})
    acc.seen.add(("entry", entry))
    acc.open_t = open_t
    tr = {"entry_t": entry, "exit_t": clock["t"] - 60, "exit_reason": "STOP", "qty": 1, "pnl": -80.0, "dir": 1}
    acc._process({"res": {"trades": [tr]}, "sym": "NQ", "now": clock["t"], "secs": 300, "state": {}, "flat_mod": 955,
                  "start": ts(2026, 11, 24, 1, 0), "fill_bar_seen": lambda t: True})
    return [a for a in sent if a.get("side") == "exit"], acc


def main():
    e = ts(2026, 11, 24, 9, 40)
    ex, acc = run(open_t=e, entry=e)
    check("1. eval_start in the future + the account's OPEN trade: the exit still routes", len(ex) == 1, (ex, acc.ledger))
    ex2, _ = run(open_t=None, legs=[{"entry_t": e, "status": "protected"}], entry=e)
    check("1. eval_start in the future + an open NinjaTrader leg of ours: the exit still routes", len(ex2) == 1, ex2)
    ex3, acc3 = run(open_t=None, legs=[], entry=ts(2026, 11, 16, 6, 16))
    check("2. the Nov 16 copied case (seen only): still skipped, no row", not ex3 and not acc3.closes, (ex3, acc3.closes))
    class R2:
        bot = SimpleNamespace(fleet=None)
        def clock(self): return ts(2026, 11, 24, 11, 0)
        def log(self, kind, text): pass
    acc4 = MA.Account({"id": "x4", "name": "x", "rules": {"news_ban": None}, "mode": "eval", "adapter": "ninjatrader",
                       "eval_start": "2026-11-25", "nt_account": "MFFUEVX0009999"}, R2())
    today_close = ["2026-11-24", ts(2026, 11, 24, 10, 0), -150.0, ts(2026, 11, 24, 9, 30)]
    acc4.restore({"nt_account": "MFFUEVX0009999", "day": "2026-11-24", "closes": [today_close], "ledger": []}, "2026-11-24")
    check("3. restore with an eval_start in the FUTURE never drops today's real close (the book keeps -$150)",
          acc4.closes == [today_close], acc4.closes)
    ok = sum(RES)
    print(f"\nledgerfix red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
