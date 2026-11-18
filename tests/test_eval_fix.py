"""engine/eval_fix.py + LiveBot._void_refused_days: an earlier eval day on which NinjaTrader refused every order
("account does not exist") and filled nothing books $0 (2026-10-27: -$965.20 on the 50K).
    python -X utf8 -m tests.test_eval_fix   (temp files only)"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import eval_fix as E  # noqa: E402
from engine import live  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def main():
    t = tempfile.mkdtemp(prefix="le_evalfix_")
    lg = os.path.join(t, "log")
    os.makedirs(lg)
    open(os.path.join(lg, "log.20261027.00000.txt"), "w").write(
        "2026-10-27 06:12:04:100|3|1|OIF, 'PLACE;MFFUEVBLD000006016;MNQ 12-26;SELL;7;MARKET;0;0;DAY;;LE1793095920W924ME;;' "
        "account does not exist 'MFFUEVBLD000006016'\n2026-10-27 06:40:06:678|3|1|OIF, 'CLOSEPOSITION;MFFUEVBLD000006016;MNQ 12-26;;' "
        "account does not exist 'MFFUEVBLD000006016'\n")
    open(os.path.join(lg, "log.20261028.00000.txt"), "w").write(
        "2026-10-28 04:01:27:342|1|8|Execution='660338100805_1' Instrument='MNQ 12-26' Account='MFFUEVBLDR000006016' Price=29987.75\n")
    days = {"0000-00-00": -100.0, "2026-10-23": 0.0, "2026-10-26": 12.0, "2026-10-27": -965.2, "2026-10-28": -437.0}
    v = E.void_days(days, t)
    check("10-27 (every PLACE refused, nothing filled) is void; 10-28 (a real fill), 10-26 (no log) and the prior are kept",
          v == ["2026-10-27"], v)
    b = live.LiveBot()
    b.cfg = {"adapter": "ninjatrader", "nt_folder": t}
    b._eval_prev = dict(days)
    b._void_refused_days()
    check("LiveBot: the 50K's -$965.20 on 2026-10-27 -> $0, the real -$437 kept",
          b._eval_prev["2026-10-27"] == 0.0 and b._eval_prev["2026-10-28"] == -437.0 and b._eval_prev["0000-00-00"] == -100.0, b._eval_prev)
    b2 = live.LiveBot()
    b2.cfg = {"adapter": "paper", "nt_folder": t}
    b2._eval_prev = dict(days)
    b2._void_refused_days()
    check("paper bot: never voids", b2._eval_prev["2026-10-27"] == -965.2)
    check("no NinjaTrader folder -> nothing voided", E.void_days(days, os.path.join(t, "nope")) == [])
    # ---- account B (ATLAS, 2026-10-29): the same day-level void for B's own closes (state-file integrity at start)
    import threading
    import types
    from engine import account_b as AB
    from engine.ninjatrader import ET
    import datetime as dt
    now = int(dt.datetime(2026, 10, 29, 3, 0, tzinfo=ET).timestamp())

    def mk(adapter):
        B = AB.AccountB.__new__(AB.AccountB)
        B.bot = types.SimpleNamespace(cfg={"adapter": adapter, "nt_folder": t}, clock=lambda: now)
        B.name, B.label, B.notified, B.mx = "MFFUEVBLDR000006017", "ATLAS 25K", [], threading.RLock()
        B.closes = [["2026-10-26", 1, 50.0, 11], ["2026-10-27", 2, -310.0, 12], ["2026-10-28", 3, 120.0, 13],
                    ["2026-10-29", 4, -40.0, 14]]
        B.ledger = [{"side": "exit", "entry_t": 12, "pnl": -310.0}, {"side": "exit", "entry_t": 13, "pnl": 120.0}]
        B.logs, B.pushes, B.saved = [], [], []
        B.log = lambda k, x: B.logs.append((k, x))
        B._push_text = lambda title, body, key: B.pushes.append((title, key))
        B.save = lambda: B.saved.append(1)
        B.adapter_cfg = lambda: {"adapter": adapter}
        return B
    B = mk("ninjatrader")
    v = B.void_refused_days(now)
    v2 = B.void_refused_days(now)
    check("account B: its -$310 close of 10-27 (every order refused, nothing filled) is removed from the eval, its exit marked "
          "void; 10-26 (no log), 10-28 (a fill) and today's close kept; one push, one log line; a second run changes nothing",
          v == ["2026-10-27"] and [c[0] for c in B.closes] == ["2026-10-26", "2026-10-28", "2026-10-29"]
          and B.ledger[0].get("void") == "refused day" and not B.ledger[1].get("void") and len(B.pushes) == 1
          and v2 == [] and any("Voided account B" in x for _, x in B.logs), (v, B.closes, B.ledger, B.pushes))
    P = mk("paper")
    check("account B on paper: never voids", P.void_refused_days(now) == [] and len(P.closes) == 4)
    n = sum(RES)
    print(f"eval fix: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
