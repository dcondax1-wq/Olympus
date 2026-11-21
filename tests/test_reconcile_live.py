"""tools/reconcile_live.py (2026-11-21): live vs backtest per real trade. A synthetic PC day folder (the engine/datapipe format:
trades.jsonl.gz, fills.jsonl.gz, twin.json.gz, decisions.jsonl.gz) in a temp dir; the real files are never written.
    python -X utf8 -m tests.test_reconcile_live
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import reconcile_live as RL  # noqa: E402

R = []


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not ok else ""), flush=True)


def gzl(p, rows):
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


tmp = tempfile.mkdtemp(prefix="reconcile_")
try:
    d = os.path.join(tmp, "2026-11-18")
    os.makedirs(d)
    T1, T2, T3 = 1795513800, 1795521600, 1795530000
    rows = [
        # ATLAS short, 2 routed, filled 2 at 15 ticks worse, model stop exit
        {"mode": "live", "bot": "atlas", "src": "acctb", "acct": "...1234", "side": "sell", "entry_t": T1, "entry": 27395.5, "stop": 27422.5,
         "target": 27000.0, "qty": 2, "strategy": "macd_sweep", "result": {"ok": True, "legs": [{"filled": 2, "fill_px": 27391.75}]}},
        {"mode": "live", "bot": "atlas", "src": "acctb", "acct": "...1234", "side": "exit", "entry_t": T1, "exit_t": T1 + 900, "qty": 2,
         "reason": "STOP", "exit_px": 27422.75, "pnl": -112.8},
        # Zlarior long, 4 routed, only 3 filled (partial), target, priced exit in the twin 2 ticks worse
        {"mode": "live", "bot": "zlarior", "acct": "...5678", "side": "buy", "entry_t": T2, "entry": 27800.0, "stop": 27760.0,
         "target": 27900.0, "qty": 4, "result": {"ok": True, "legs": [{"filled": 3, "fill_px": 27800.5}]}},
        {"mode": "live", "bot": "zlarior", "acct": "...5678", "side": "exit", "entry_t": T2, "exit_t": T2 + 3000, "qty": 3, "reason": "TARGET",
         "exit_px": 27900.0, "pnl": 594.3},
        # a refused entry = missed; a paper row = ignored
        {"mode": "live", "bot": "zlarior", "acct": "...5678", "side": "buy", "entry_t": T3, "entry": 27850.0, "stop": 27800.0, "qty": 2,
         "result": {"ok": False, "error": "rejected: max order quantity"}},
        {"mode": "paper", "bot": "zlarior", "acct": "Sim101", "side": "buy", "entry_t": T3 + 60, "entry": 1.0, "stop": 0.5, "qty": 1},
    ]
    gzl(os.path.join(d, "trades.jsonl.gz"), rows)
    gzl(os.path.join(d, "fills.jsonl.gz"), [{"entry_t": T1, "fill_px": 27391.75, "filled": 2, "sent_s_after_open": 4.2, "fill_s_after_sent": 0.3},
                                             {"entry_t": T2, "fill_px": 27800.5, "filled": 3, "sent_s_after_open": 1.1, "fill_s_after_sent": 0.2}])
    with gzip.open(os.path.join(d, "twin.json.gz"), "wt", encoding="utf-8") as fh:
        json.dump({"day": "2026-11-18", "nightly": {"rows": [
            {"status": "matched", "entry_t": T2, "bt_entry": 27800.0, "bt_exit": 27900.0, "bt_exit_reason": "TARGET",
             "live_exit": 27899.5, "live_exit_kind": "TARGET", "exit_src": "outgoing order state"},
            {"status": "missed", "day": "2026-11-18", "entry_t": T3 + 7200, "bt_pnl": 250.0, "reason": "PC bot off"}]}}, fh)
    gzl(os.path.join(d, "decisions.jsonl.gz"), [{"src": "held_back", "entry_t": T3 + 3600, "reason": "ATLAS NOT routed: feed stale"}])
    old = RL.DAY_DIRS
    RL.DAY_DIRS = (tmp,)
    o = RL.build()
    RL.DAY_DIRS = old
    T = {t["bot"]: t for t in o["trades"]}
    a, z = T.get("ATLAS"), T.get("Zlarior")
    check("source = the day folders; paper rows ignored; 2 real trades", o["source"].startswith("data/pc_days") and len(o["trades"]) == 2, o["trades"])
    check("ATLAS: fill 15 ticks worse = -$15 at 2 micros", a["entry_ticks"] == 15.0 and a["entry_usd"] == -15.0, a)
    check("ATLAS: model R -1.01, real R lower (the late fill)", a["model_r"] == -1.01 and a["real_r"] < a["model_r"], (a["model_r"], a["real_r"]))
    check("ATLAS: model $ -112.80 at 2 micros, real $ -127.80, diff -$15", a["model_usd"] == -112.8 and a["real_usd"] == -127.8 and a["diff_usd"] == -15.0, a)
    check("ATLAS: cause latency + slippage (sent 4.2 s after the open, 15 ticks)", a["cause"].startswith("latency + slippage"), a["cause"])
    check("ATLAS: no priced exit -> flagged", a["exit_src"].startswith("model"), a["exit_src"])
    check("Zlarior: partial (3 of 4) named; the priced exit from the twin (2 ticks worse) = exit slippage? no: 2 is the threshold",
          "partial (3 of 4)" in z["cause"] and z["exit_ticks"] == 2.0 and "exit slippage" not in z["cause"] and z["real_exit"] == 27899.5, z)
    check("Zlarior: entry 2 ticks worse = not 'slippage' (<= 2)", z["entry_ticks"] == 2.0 and "slippage" not in z["cause"].replace("exit slippage", ""), z["cause"])
    causes = {m["cause"] for m in o["missed"]}
    check("missed: the refused entry, the twin's missed trade and the held-back ATLAS entry", len(o["missed"]) == 3
          and {"missed (refused by the broker)", "missed", "held back"} <= causes, o["missed"])
    tz = o["totals"]
    check("totals: per bot trades, median ticks, real vs model $ a trade, implied PF and the alarm check present",
          tz["ATLAS"]["trades"] == 1 and tz["ATLAS"]["entry_ticks_median"] == 15.0 and "real_usd_per_trade" in tz["Zlarior"]
          and "implied_pf40" in tz["ATLAS"] and "alarm_agrees" in tz["ATLAS"], tz)
    check("privacy: accounts as last 4 only", a["account"] == "...1234" and z["account"] == "...5678")
    before = os.path.getmtime(RL.OUT) if os.path.exists(RL.OUT) else None
    RL.DAY_DIRS = (tmp,)
    RL.main(["--print"])
    RL.DAY_DIRS = old
    check("--print writes no file", (os.path.getmtime(RL.OUT) if os.path.exists(RL.OUT) else None) == before)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print(f"reconcile live: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAILED'}")
sys.exit(0 if all(R) else 1)
