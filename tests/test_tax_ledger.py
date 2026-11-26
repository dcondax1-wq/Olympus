"""tools/tax_ledger.py on a temp root (never the real data/ or money_out/): your ledger + the site's eval prices + the bot's recorded
payouts -> ledger / monthly CSV + the yearly summary, no double counting, Kalshi left out, missing fees named.

    python -X utf8 -m tests.test_tax_ledger      (~1 s)
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import tax_ledger as TL  # noqa: E402

RES = []


def check(name, ok, info=None):
    RES.append((name, bool(ok)))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + ("" if ok or info is None else f"  {str(info)[:300]}"))


def _months_since_sep() -> int:
    import datetime as dt
    t = dt.date.today()
    if t.year > 2026:
        return 4
    return max(0, t.month - 9 + 1) if t.day >= 1 else 0


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "data"))
        os.makedirs(os.path.join(d, "tools", "web_public", "ledger"))
        shutil.copy(os.path.join(ROOT, "tools", "web_public", "ledger", "rules.json"), os.path.join(d, "tools", "web_public", "ledger", "rules.json"))
        led = {"entries": [
            {"kind": "fee", "amount": 63, "date": "2026-11-17", "acct": "acc25k2", "note": "private note"},
            {"kind": "fee", "amount": 97.2, "date": "2026-11-20", "acct": "rapid"},
            {"kind": "payout_in", "amount": 800, "date": "2026-11-24", "acct": "atlas25k"},     # = the bot's $1,000 gross x 80%
            {"kind": "expense", "amount": 30, "date": "2026-09-01", "acct": "general", "rec": {"every": "month"}},
            {"kind": "deposit", "amount": 500, "date": "2026-11-05", "acct": "kalshi"},
            {"kind": "payout_req", "amount": 1000, "date": "2026-11-23", "acct": "atlas25k"},
            {"kind": "tax", "amount": 200, "date": "2026-11-25", "acct": "general"},
            {"kind": "fee", "amount": 91.8, "date": "2025-12-01", "acct": "old"}]}
        json.dump(led, open(os.path.join(d, "data", "money_ledger.json"), "w"))
        json.dump({"account_b": {"account": "x", "plan": "builder25k", "stage": "funded", "payouts": {"2026-11-24": 1000, "2026-11-25": 750, "2099-01-02": 999}}},
                  open(os.path.join(d, "data", "account_b.json"), "w"))
        json.dump({"accounts": [{"id": "acc25k2", "preset": "mffu_builder_25k"}, {"id": "acc50k3", "preset": "mffu_builder_50k",
                                                                               "funded": {"payouts": {"2026-11-25": 2000}}}]},
                  open(os.path.join(d, "data", "accounts.json"), "w"))
        json.dump({"account": "r", "plan": "rapideod25k", "stage": "funded", "payouts": {"2026-11-25": 600}}, open(os.path.join(d, "data", "rapid.json"), "w"))
        res = TL.collect(2026, d)
        out = os.path.join(d, "out")
        w = TL.write(res, out)
        rows = list(csv.DictReader(open(w["ledger"])))
        amt = lambda k, a=None: round(sum(float(r["amount_usd"]) for r in rows if r["kind"] == k and (a is None or r["account"] == a)), 2)
        check("auto eval fees at your real prices (50K $91.80, ATLAS 25K $43) + your own fees", amt("fee") == -(91.8 + 43 + 63 + 97.2), amt("fee"))
        check("ATLAS payout 11-24 counted once (your $800 = the bot's $1,000 x 80%); 11-25 from the bot at 80% ($600); a future day never",
              amt("payout_in", "atlas25k") == 1400.0, [r for r in rows if r["account"] == "atlas25k"])
        check("Rapid payout x 90% ($540), extra 50K x 80% ($1,600)", amt("payout_in", "rapid") == 540.0 and amt("payout_in", "acc50k3") == 1600.0)
        check("recurring expense expanded per month up to today ($30 a month from Sep), never in the future",
              all(r["date"] <= __import__("datetime").date.today().isoformat() for r in rows) and amt("expense") == -30.0 * _months_since_sep(), amt("expense"))
        check("Kalshi deposit, payout request and tax payment are NOT P&L rows; 2025 left out of 2026",
              not any(r["kind"] in ("deposit", "payout_req", "tax") for r in rows) and all(r["date"].startswith("2026") for r in rows))
        check("no private note written", "private note" not in open(w["ledger"]).read())
        mon = list(csv.DictReader(open(w["monthly"])))
        tot = round(sum(float(m["net"]) for m in mon), 2)
        check(f"monthly net adds up to the summary's net (${w['net']:,.2f})", abs(tot - w["net"]) < 0.02, (tot, w["net"]))
        s = open(w["summary"]).read()
        check("summary: SE tax 15.3% x 92.35% of net, 30% set-aside, Jan 15 2027, Kalshi note",
              f"{round(max(0, w['net']) * 0.9235 * 0.153, 2):,.2f}" in s and "Jan 15, 2027" in s and "Kalshi" in s and "200.00" in s)
        check(f"fee missing named for accounts the bot knows without a fee ({res['missing_fee']})", res["missing_fee"] == ["acc50k3"], res["missing_fee"])
    fails = [n for n, ok in RES if not ok]
    print(f"\n{len(RES) - len(fails)}/{len(RES)} OK" + (f"  FAIL: {fails}" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
