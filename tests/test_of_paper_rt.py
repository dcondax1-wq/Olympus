"""Red team 2026-11-26: the OF paper bot's detached child starts BELOW_NORMAL on Windows (it runs during trading hours).
    python -X utf8 -m tests.test_of_paper_rt
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import ops_checks as OC     # noqa: E402


def main():
    seen = []
    now = dt.datetime(2026, 12, 1, 10, 0, tzinfo=ZoneInfo("America/New_York")).timestamp()
    old = os.name
    try:
        os.name = "nt"                                 # the Windows branch of the kick (no real process starts: popen is fake)
        r = OC.of_paper_kick(now, real=True, root=tempfile.mkdtemp(), popen=lambda cmd, **kw: seen.append(kw))
    finally:
        os.name = old
    ok = r == "started" and seen and seen[0].get("creationflags", 0) & 0x00004000
    print(f"  [{'PASS' if ok else 'FAIL'}] the paper child starts BELOW_NORMAL on Windows", "" if ok else (r, seen))
    print("of_paper red team:", "ALL PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
