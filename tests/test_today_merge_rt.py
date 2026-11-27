"""Red team 2026-11-26: ONE Telegram /today after guard2 (accounts brief + PC signing-key line) and big-payout (the payout plan)
both landed: parse_text hands "today" to the owner-only tick path, the reply carries the payouts AND ends with the key line, and
payout names are masked.
    python -X utf8 -m tests.test_today_merge_rt
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import payout_engine as PE, tg_cmd as T, today_brief as TB   # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    c, say = T.parse_text("/today")
    check("/today -> the tick path (cmd today, behind is_owner), not a parse-time reply", c == {"cmd": "today"} and say is None, (c, say))
    keep = (TB.key_line, PE.gather)
    TB.key_line = lambda: "PC signing key: ABCDEF"
    PE.gather = lambda *a, **k: [{"name": "MFFUSF123456", "line": "request $1,000 today", "ready": True, "to_you": 800, "kind": "builder"}]
    try:
        txt = T.today_reply(1795700000, live_fn=lambda: None)
    finally:
        TB.key_line, PE.gather = keep
    lines = txt.splitlines()
    check("the reply has the payout plan", any(ln.startswith("Payouts: 1 ready today") for ln in lines), txt)
    check("the PC signing-key line stays LAST", lines[-1] == "PC signing key: ABCDEF", lines[-3:])
    check("payout account names masked", "MFFUSF123456" not in txt and "...3456" in txt, txt)
    print(f"\ntoday merge red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
