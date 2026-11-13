"""tools/kalshi_paper.py: the K1 forward paper tester. Offline and deterministic: a stub public API, no network, nothing outside
a temp folder. Checks the fee rounding, the dead-bracket logic, de-duplication, settlement, the paper-only ledger, and that no
order or portfolio endpoint is ever called (the tool is GET-only on public market data).
    python -X utf8 -m tests.test_kalshi_paper
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import kalshi_paper as KP  # noqa: E402


def main() -> int:
    rc = KP.selftest()
    src = open(os.path.join(ROOT, "tools", "kalshi_paper.py"), encoding="utf-8").read()
    ok = True
    for bad in ("/portfolio", "/orders", "Authorization", "KALSHI-ACCESS", "private_key", "method=\"POST\"", "method='POST'"):
        if bad in src.replace("\"/orders\" in u", "").replace("\"/portfolio\" in u", ""):
            print(f"[FAIL] source mentions {bad}")
            ok = False
    if not re.search(r"PAPER ONLY", src):
        print("[FAIL] the docstring must say PAPER ONLY")
        ok = False
    print("[PASS] GET-only, no key handling in the source" if ok else "[FAIL] source checks")
    return 0 if rc == 0 and ok else 1


if __name__ == "__main__":
    sys.exit(main())
