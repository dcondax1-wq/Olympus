"""Red team 2026-11-26 (big-shadow): the buy gate's "bg" block stays < 400 UTF-8 bytes whatever its lines hold, and a damaged
logs/buy_gate.json (no / unknown verdict) shows nothing (never a stray "OK to buy").
    python -X utf8 -m tests.test_buy_gate_rt
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import buy_gate as B        # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    t = B.tiny({"shown": True, "verdict": "STOP", "line": "· STOP " * 80, "shadow": "· €" * 200, "t": 1795800000})
    n = len(json.dumps(t, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    check("the bg block stays < 400 bytes with long non-ASCII lines (as pc_report counts it)", n < 400, n)
    check("no verdict: nothing shown", B.tiny({"shown": True, "line": "x"}) is None)
    check("an unknown verdict: nothing shown", B.tiny({"shown": True, "verdict": "MAYBE"}) is None)
    check("switch off: nothing shown", B.tiny({"shown": False, "verdict": "OK"}) is None)
    print(f"\nbuy gate red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
