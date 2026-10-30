"""The 50K's eval days across restarts (2026-10-30): one real -$437.00 stop-out on 2026-10-28 was booked as -$1,311.00
(room $232 instead of ~$1,106) because LiveBot.eval_days() re-added the restored ledger's earlier-day exits on top of the
restored day totals at every restart after the 18:00 roll. Now: an earlier day keeps its restored total, a day booked as an
exact multiple of its own exits is repaired on restore (one push), a per-trade void after the roll still reaches the eval,
and the fill audit counts a "fill not reported yet" entry whose stop filled at the broker as a trade, not a missed one.
    python -X utf8 -m tests.test_eval_recount   (temp files only)"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import live  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
TMP = tempfile.mkdtemp(prefix="le_recount_")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def at(day, h, m=0):
    return int(dt.datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=ET).timestamp())


ENTRY_T = at("2026-10-28", 3, 43)
LEDGER = [{"t": ENTRY_T + 32, "side": "sell", "qty": 5, "entry_t": ENTRY_T, "entry": 29945.0, "stop": 29987.5,
           "target": 29665.75, "result": {"ok": False, "error": "MNQ 12-26: fill not reported yet"}},
          {"t": at("2026-10-28", 4, 2), "side": "exit", "qty": 5, "entry_t": ENTRY_T, "reason": "STOP", "exit_t": at("2026-10-28", 4, 2),
           "pnl": -437.0}]


def bot(now, name):
    b = live.LiveBot()
    b.state_path = os.path.join(TMP, name)
    b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "eval_start": "2026-10-19"}
    b.clock = lambda: now
    b.pushed = []
    b._push_send = lambda p: b.pushed.append(p)
    return b


def write_state(name, day, eval_days, ledger):
    with open(os.path.join(TMP, name), "w", encoding="utf-8") as f:
        json.dump({"version": live.STATE_VERSION, "saved_at": at(day, 9), "day": day, "sym": "NQ", "tf": "5m",
                   "ledger": ledger, "eval_days": eval_days}, f)


def main():
    # ---- restarts after the roll: the earlier day keeps its one booking (it was -437 -> -874 -> -1,311)
    write_state("a.json", "2026-10-29", {"2026-10-27": 0.0, "2026-10-28": -437.0}, LEDGER)
    vals = []
    for _ in range(3):
        b = bot(at("2026-10-29", 16, 45), "a.json")
        b._restore()
        vals.append(b.eval_days().get("2026-10-28"))
        b._save_state()
    check("3 restarts on the next day: 2026-10-28 stays -437.00 (was -874, then -1,311)", vals == [-437.0] * 3, vals)
    # ---- a process that ran across the roll (no restart): the earlier day comes from its ledger, once
    b = bot(at("2026-10-29", 9), "fresh.json")
    b.ledger = [dict(r) for r in LEDGER]
    check("no restart since the trade: 2026-10-28 = its ledger exits (-437.00)", b.eval_days().get("2026-10-28") == -437.0, b.eval_days())
    # ---- the PC's saved state today: 2026-10-28 booked 3x -> repaired on restore, one push on the first poll
    write_state("b.json", "2026-10-30", {"2026-10-27": 0.0, "2026-10-28": -1311.0}, LEDGER)
    b = bot(at("2026-10-30", 9), "b.json")
    b._restore()
    check("restore repairs 2026-10-28 from -1,311.00 (3x) to -437.00", b.eval_days().get("2026-10-28") == -437.0, b.eval_days())
    b._push_recount_fix()
    b._push_recount_fix()
    p = b.pushed
    check("one push: 'eval balance fixed', +$874.00", len(p) == 1 and "eval balance fixed" in json.dumps(p[0])
          and "+874.00" in json.dumps(p[0]), p)
    with open(b.state_path, encoding="utf-8") as f:
        saved = json.load(f)["eval_days"]
    check("the repaired day is saved", saved.get("2026-10-28") == -437.0, saved)
    b2 = bot(at("2026-10-30", 9, 30), "b.json")
    b2._restore()
    check("the next restart keeps -437.00, no second push", b2.eval_days().get("2026-10-28") == -437.0 and not getattr(b2, "_recount_fix", None))
    # ---- only the exact-multiple signature is touched
    write_state("c.json", "2026-10-30", {"2026-10-27": 0.0, "2026-10-28": -500.0, "2026-10-26": 0.0}, LEDGER)
    b = bot(at("2026-10-30", 9), "c.json")
    b._restore()
    check("a day that is not a whole multiple of its exits (-500 vs -437) is left as booked",
          b.eval_days().get("2026-10-28") == -500.0 and not getattr(b, "_recount_fix", None), b.eval_days())
    write_state("d.json", "2026-10-30", {"2026-10-28": 0.0}, LEDGER)
    b = bot(at("2026-10-30", 9), "d.json")
    b._restore()
    check("a day voided to $0 stays $0 (its ledger exits are not added back)", b.eval_days().get("2026-10-28") == 0.0, b.eval_days())
    # ---- a per-trade void after the roll still reaches the earlier day's total
    write_state("e.json", "2026-10-29", {"2026-10-28": -437.0}, LEDGER)
    b = bot(at("2026-10-29", 9), "e.json")
    b._restore()
    b._entry_never_placed = lambda et_: True
    b._void_unplaced_exits()
    check("a void after the roll: 2026-10-28 -437.00 -> 0.00", b.eval_days().get("2026-10-28") == 0.0, b.eval_days())
    # ---- the fill audit: NOT OK entry + its stop FILLED at the broker = a trade, not a missed one
    from engine import fill_audit as FA
    st = os.path.join(TMP, "audit")
    os.makedirs(st, exist_ok=True)
    with open(os.path.join(st, "ledger.jsonl"), "w", encoding="utf-8") as f:
        for r in LEDGER:
            f.write(json.dumps({**r, "adapter": "ninjatrader"}) + "\n")
    FA._orders_by_entry = lambda store: {ENTRY_T: {"stop": {"state": "FILLED", "avg": 29987.75, "mtime": at("2026-10-28", 4, 1)}}}
    lv = FA.live_trades(store=st, journal_path=os.path.join(TMP, "nojournal.jsonl")).get(ENTRY_T) or {}
    check("fill audit: 'fill not reported yet' + stop filled at the broker -> a real trade (ok, exit 29,987.75)",
          lv.get("ok") is True and lv.get("exit_px") == 29987.75 and lv.get("exit_src") == "broker", lv)
    FA._orders_by_entry = lambda store: {}
    FA._filled_in_nt_log = lambda et_, cache=None: False
    lv = FA.live_trades(store=st, journal_path=os.path.join(TMP, "nojournal.jsonl")).get(ENTRY_T) or {}
    check("fill audit: no broker fill anywhere -> still a refused entry", lv.get("ok") is False, lv)
    # ---- NinjaTrader's own Log line of 2026-10-28 (the 50K's stop Filled at 04:01) proves the fill
    import importlib
    from engine import ninjatrader as NT
    FA2 = importlib.reload(FA)
    nt = os.path.join(TMP, "nt")
    os.makedirs(os.path.join(nt, "log"), exist_ok=True)
    with open(os.path.join(nt, "log", "log.20261028.00000.txt"), "w", encoding="utf-8") as f:
        f.write("2026-10-28 04:01:26:325|1|32|Order='660338100805/MFFUEVBLDR602936016' Name='' New state='Filled' "
                "Instrument='MNQ 12-26' Action='Buy' Limit price=0 Stop price=29987.5 Quantity=5 Type='Stop Market' "
                f"Time in force=DAY Oco='LE{ENTRY_T}M23QMO' Filled=5\n")
    old = NT.default_folder
    NT.default_folder = lambda: nt
    try:
        c = {}
        check("NinjaTrader Log: the entry's bracket Filled -> True; another entry -> False; the log is read once",
              FA2._filled_in_nt_log(ENTRY_T, c) is True and FA2._filled_in_nt_log(ENTRY_T + 60, c) is False
              and "2026-10-28" in c, list(c))
    finally:
        NT.default_folder = old
    n = sum(RES)
    print(f"\neval recount: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
