"""engine/payout_engine (big-payout 2026-11-26): the read-only payout planner, the Telegram /today line, the Money tile.
    python -X utf8 -m tests.test_payout_engine
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import funded_life as FL, payout_engine as PE, tg_cmd as TG  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def main():
    T = "2026-12-01"
    # 1. ready: 25K, balance 27,150 (> 25,000 + 1,100 + 1,000), 3 days, no day > 50 %
    t = FL.track({"2026-11-19": 700.0, "2026-11-20": 750.0, "2026-11-23": 700.0}, plan="builder25k", today=T, start="2026-11-19", name="ATLAS 25K")
    r = PE.builder_row(t, "atlas", T)
    check("ready 25K: REQUEST TODAY $1,000, $800 to you, keep $26,100", r["ready"] and r["next_amount"] == 1000 and r["to_you"] == 800
          and r["keep_balance"] == 26100 and "REQUEST TODAY: $1,000" in r["line"], r)
    # 2. below the ask line: $600 profit over 3 days -> $1,500 more at ~$200 a day = 8 trading days
    t = FL.track({"2026-11-24": 200.0, "2026-11-25": 200.0, "2026-11-27": 200.0}, plan="builder25k", today=T, start="2026-11-24")
    r = PE.builder_row(t, "atlas", T)
    check("below the line: the $ still needed, a date at the account's pace (trading days), keep the buffer",
          not r["ready"] and "$1,500 more profit" in r["line"] and r["next_date"] == PE.add_trading_days(T, 8) and r["keep_balance"] == 26100, r)
    # 3. consistency: one $1,800 day of $2,300 -> blocked by the 50 % rule
    t = FL.track({"2026-11-24": 1800.0, "2026-11-25": 250.0, "2026-11-27": 250.0}, plan="builder25k", today=T, start="2026-11-24")
    r = PE.builder_row(t, "atlas", T)
    check("best day over 50 %: says so, not ready", not r["ready"] and any("50% max" in b for b in r["blocks"]), r)
    # 4. 48 h after the first trade
    t = FL.track({"2026-12-01": 2200.0}, plan="builder25k", today="2026-12-01", start="2026-12-01")
    r = PE.builder_row(t, "atlas", "2026-12-01")
    check("first trade today: blocked until MFFU's 48 h / 2 days", not r["ready"] and r["next_date"] > "2026-12-01", r)
    # 5. payout #5 guard and a lost account
    r = PE.builder_row({"payouts_n": 4, "name": "ATLAS 25K"}, "atlas", T)
    check("4 payouts: do NOT take #5", "do NOT take #5" in r["line"] and not r.get("ready"), r)
    r = PE.builder_row({"lost": True, "name": "X"}, "x", T)
    check("lost: no payout", "lost" in r["line"], r)
    # 6. 50K plan numbers
    t = FL.track({"2026-11-19": 1500.0, "2026-11-20": 1500.0, "2026-11-23": 1200.0}, plan="builder50k", today=T, start="2026-11-19")
    r = PE.builder_row(t, "x:1", T)
    check("ready 50K: $2,000, $1,600 to you, keep $52,100", r["ready"] and r["next_amount"] == 2000 and r["to_you"] == 1600 and r["keep_balance"] == 52100, r)
    # 7. Rapid rows
    rr = PE.rapid_row({"stage": "funded", "payout": {"ready": True, "request": 600.0, "to_you": 540.0, "keep_at": 1200.0}}, "r1", "Rapid EOD 25K", T)
    rw = PE.rapid_row({"stage": "funded", "payout": {"ready": False, "since_short": 120.0}}, "r2", "Rapid EOD 25K", T)
    check("Rapid: ready $600 ($540 to you); waiting says MFFU's net-since-last rule", rr["ready"] and rr["to_you"] == 540 and "$120 more net" in rw["line"], (rr, rw))
    # 8. today line + tile + Telegram /today
    src = {"atlas": FL.track({"2026-11-19": 700.0, "2026-11-20": 750.0, "2026-11-23": 700.0}, plan="builder25k", today=T, start="2026-11-19"),
           "extras": [], "rapids": [("r2", {"stage": "funded", "payout": {"ready": False, "since_short": 120.0}}, "Rapid EOD 25K")]}
    rows = PE.gather(today=T, sources=src)
    line = PE.today_line(rows)
    check("today line: '1 ready today ($800 to you)' + one line per account", line.startswith("Payouts: 1 ready today ($800 to you)") and line.count("\n- ") == 2, line)
    tl = PE.tile(rows, now=1)
    check("tile JSON: small, ready counts, next, rows with keep / blocks / habit keys",
          tl["ready_today"] == 1 and tl["ready_to_you"] == 800 and tl["next"]["date"] == T and len(json.dumps(tl)) < 3000
          and all({"keep", "blocks", "line", "habit"} <= set(x) for x in tl["rows"]), tl)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "tile.json")
        check("write_tile writes plain JSON", PE.write_tile(p, rows) and json.load(open(p))["n"] == 2)
    keep = PE.today_line
    PE.today_line = lambda rows=None: "Payouts: test line"
    try:
        c, say = TG.parse_text("/today")
        check("Telegram /today: a read-only answer (nothing runs on the PC)", c is None and say == "Payouts: test line", (c, say))
        c, say = TG.parse_text("/today please")
        check("/today with words: not run", c is None and say != "Payouts: test line", say)
    finally:
        PE.today_line = keep
    check("/today is in the help text", "/today" in TG.HELP)
    check("no funded account: says so", PE.today_line([]) == "Payouts: no funded account yet.")
    # 9. read-only: nothing that requests / trades
    src_code = open(os.path.join(ROOT, "engine", "payout_engine.py"), encoding="utf-8").read()
    tree = ast.parse(src_code)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    check("payout_engine imports nothing that can trade or request", not any(m and any(b in m for b in ("ninjatrader", "live", "tradovate", "remote_ctl")) for m in mods), mods)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
