"""PAYDAY for the phone (night-nqdash2 2026-11-20): research/lab/payday_plan.json (tools/money/payday_plan.py) -> the small public copy
tools/web_public/business/payday.json that the MFFU account center (business/mffu.html, ../nqdeep.js payout()) draws as each account's
"first payout" date range. Only dates, $ and odds per account name: no account ids, no balances.

    python tools/nqdash_payday.py            # rewrite business/payday.json
    python tools/nqdash_payday.py --check    # exit 1 when the public copy is out of date
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "research", "lab", "payday_plan.json")
OUT = os.path.join(ROOT, "tools", "web_public", "business", "payday.json")
KEEP = ("name", "first_pay_p10", "first_pay_p25", "first_pay_med", "first_pay_p75", "first_pay_p90", "first_pay_usd", "first_pay_usd_p10",
        "p_by_dec31", "p_by_jan15", "p_by_jan31", "p_no_pay_6m", "p_lost_before_pay", "funded_med", "funded_p10", "p_funded_by_dec31")
ACCTS = ("Z50", "N25", "A25", "R25")


def build(plan: dict) -> dict:
    rows = {}
    for m, r in (plan.get("rows") or {}).items():
        acc = (r or {}).get("accounts") or {}
        rows[m] = {"accounts": {k: {f: acc[k].get(f) for f in KEEP if f in acc[k]} for k in ACCTS if isinstance(acc.get(k), dict)}}
    return {"v": 1, "src": "research/lab/payday_plan.json (tools/money/payday_plan.py), copied by tools/nqdash_payday.py",
            "what": "ESTIMATES: the first payout date per account from 1,000 simulated runs of each market kind. Not a promise.",
            "date": plan.get("date"), "n": plan.get("n"), "markets": plan.get("markets") or {}, "rows": rows}


def main(argv: list[str]) -> int:
    with open(SRC, encoding="utf-8") as fh:
        pub = build(json.load(fh))
    text = json.dumps(pub, indent=1, ensure_ascii=False) + "\n"
    if "--check" in argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        print("payday.json is current" if cur == text else "payday.json is OUT OF DATE: run python tools/nqdash_payday.py")
        return 0 if cur == text else 1
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(text)} bytes, {sum(len(r['accounts']) for r in pub['rows'].values())} account rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
