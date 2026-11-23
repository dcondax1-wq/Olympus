"""READY check from the cloud (day-ready 2026-11-22): reads the PC's PUBLIC status post (tools/board.fetch_lite) and prints the
same verdict the phone shows ("rd" block: READY / NOT READY + the first blocker and its fix). For a Claude session to watch.
Read-only; prints no ids; nothing is sent, started, stopped or armed.

    python tools/ready_check.py            exit 0 READY / WARN, 1 NOT READY, 2 no verdict (PC silent / old PC version)
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
STALE_S = 30 * 60


def verdict(lite, now=None) -> dict:
    """{"state": "ok" | "warn" | "no" | "unknown", "line": plain words, "fix": str, "age_s": seconds since the PC's post} from a fetched post."""
    now = time.time() if now is None else now
    L = lite if isinstance(lite, dict) else None
    if not L:
        return {"state": "unknown", "line": "UNKNOWN: no PC status post could be read (PC silent or no internet).", "fix": "", "age_s": None}
    try:
        age = max(0, int(now - float(L.get("t"))))
    except (TypeError, ValueError):
        age = None
    if age is None or age > STALE_S:
        return {"state": "unknown", "line": f"UNKNOWN: the PC's last report is {'unknown' if age is None else str(age // 60) + ' min'} old (PC silent).",
                "fix": "On the PC: STOP_BOT.bat then START_BOT.bat.", "age_s": age}
    r = L.get("rd")
    if not isinstance(r, dict) or r.get("s") not in ("ok", "warn", "no"):
        return {"state": "unknown", "line": "UNKNOWN: the PC reports, but has no ready check yet (older version; UPDATE.bat).", "fix": "", "age_s": age}
    w, b = r.get("w") or "the next window", r.get("b") or ""
    if r["s"] == "ok":
        line = f"READY for {w}"
    elif r["s"] == "warn":
        line = f"READY, 1 to watch: {b}"
    else:
        line = f"NOT READY for {w}: {b}" + (f" (+{int(r['n']) - 1} more)" if int(r.get("n") or 1) > 1 else "")
    return {"state": r["s"], "line": line, "fix": str(r.get("f") or ""), "age_s": age}


def main(argv=None) -> int:
    from tools import board
    v = verdict(board.fetch_lite())
    print(v["line"])
    if v["fix"]:
        print("Fix:", v["fix"])
    if v["age_s"] is not None:
        print(f"(PC reported {v['age_s'] // 60} min ago)")
    return {"ok": 0, "warn": 0, "no": 1}.get(v["state"], 2)


if __name__ == "__main__":
    sys.exit(main())
