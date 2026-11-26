"""tools/livegap_daily.py on a fake audit (no data, no network): rows per account/day, the 4 difference kinds, no duplicates.
    python -X utf8 -m tests.test_livegap_daily
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import livegap_daily as LD  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        FAILS.append(name)


R = {"bars_to": "2026-11-20", "pc_days_pulled": ["2026-11-20"], "accounts": {
    "z50k": {"name": "Z", "trades": [
        {"day": "2026-11-10", "when": "Tue Nov 10 03:33", "side": "LONG", "twin_usd": -347.7, "twin_qty": 4, "live_qty": None,
         "live_usd": 0.0, "parts": {"MISSED": 347.7}, "cause": "MISSED: PC BOT OFF"},
        {"day": "2026-11-16", "when": "Mon Nov 16 06:16", "side": "LONG", "twin_usd": -129.0, "twin_qty": 1, "live_qty": 1,
         "live_usd": -129.4, "parts": {"SIZE": 0.0, "SLIPPED": -1.5}, "cause": "traded"},
        {"day": "2026-11-17", "when": "Tue Nov 17 04:00", "side": "SHORT", "twin_usd": 300.0, "twin_qty": 2, "live_qty": 3,
         "live_usd": 420.0, "parts": {"SIZE": 150.0, "SLIPPED": -30.0}, "cause": "traded"}]},
    "atlas25": {"name": "A", "trades": [
        {"day": "2026-11-18", "when": "Wed Nov 18 04:50", "member": "MACD", "side": "SHORT", "twin_usd_est": -128.0,
         "one_position_skip": True, "live_qty": None, "live_usd": 0.0, "parts": {}}]}}}
LIVE = [{"src": "live", "bot": "LIT", "acct": "zlarior", "t": 1000, "side": "LONG", "day": "2026-11-19", "hm": "03:00", "q": 2, "usd": -80.0},
        {"src": "live", "bot": "LIT", "acct": "zlarior", "t": 5000, "side": "SHORT", "day": "2026-11-17", "hm": "04:00", "q": 3, "usd": 420.0}]
TW = {"LIT": [{"entry_t": 5100, "dir": -1}], "ATLAS": []}

daily, lines = LD.build(R, LIVE, TW, today="2026-11-26T03:00")
kinds = sorted(j["kind"] for j in lines)
check("4 kinds: MISSED, SIZE, SLIPPED (>= $5 only), EXTRA (live with no twin); the -$1.50 slip and the one-position skip are not diffs",
      kinds == ["EXTRA", "MISSED", "SIZE", "SLIPPED"], kinds)
by = {(r["account"], r["day"]): r for r in daily["rows"]}
check("one row per account-day, gap = live - twin", by[("z50k", "2026-11-17")]["gap_usd"] == 120.0
      and by[("z50k", "2026-11-19")]["live_trades"] == 1 and ("atlas25", "2026-11-18") not in by, list(by))
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "j.jsonl")
    new = LD.append_new(lines, path=p, stamp="x")
    with open(p, "w") as fh:
        fh.write("\n".join(__import__("json").dumps(j) for j in new) + "\n")
    again = LD.append_new(lines, path=p, stamp="y")
    check("journal: a re-run adds nothing twice", len(new) == 4 and again == [], (len(new), again))
sys.exit(1 if FAILS else 0)
