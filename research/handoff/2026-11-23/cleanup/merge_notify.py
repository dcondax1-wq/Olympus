"""Resolve the night-cleanup(-rt) + night-notify(-rt) merge (red team 2026-11-23). Run from the repo root right after
`git merge origin/night-notify-rt` stopped on its 3 conflicts (docs/ALERTS.md, engine/alert_bus.py, engine/trade_home.py):

    python research/handoff/2026-11-23/cleanup/merge_notify.py      then: git add -A && git commit --no-edit

1. each conflict keeps BOTH sides (cleanup's tools/bat paths + menu 10-14 / M, notify's ZERO-SETUP text + "T Test all alerts");
2. night-notify's own new lines that name a moved .bat by its old top-folder place get the tools/bat/ (tools\\bat\\) path, so
   tests/test_bat_menu d stays green. Prints every change; touches only the files listed below.
"""
import os
import re
import sys

ROOT = os.getcwd()
CONFLICT = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S)
MOVED = ("TEST_ALERT", "ALERTS_OFF", "ALERTS_ON")
RENAME_IN = ("docs/ALERTS.md", "tests/test_alert_map.py", "tools/alerts_setup.py", "engine/alert_bus.py", "engine/trade_home.py",
             "tools/pc_report.py")


def keep_both(path, ours, theirs):
    if path == "engine/alert_bus.py":                 # the same "Test:" line on both sides: cleanup's (tools/bat) + notify's paragraph
        theirs = theirs.split("\n", 1)[1] if theirs.startswith("Test:") else theirs
    return ours + theirs


def main() -> int:
    if not os.path.isdir(os.path.join(ROOT, "tools", "bat")):
        print("run it from the repo root of the merge (tools/bat/ must exist)")
        return 1
    for p in ("docs/ALERTS.md", "engine/alert_bus.py", "engine/trade_home.py"):
        f = os.path.join(ROOT, p)
        s = open(f, encoding="utf-8").read()
        n = len(CONFLICT.findall(s))
        s = CONFLICT.sub(lambda m: keep_both(p, m.group(1), m.group(2)), s)
        if "<<<<<<<" in s or ">>>>>>>" in s:
            print(f"[FIX] {p}: a conflict this script does not know; resolve by hand")
            return 1
        open(f, "w", encoding="utf-8", newline="").write(s)
        print(f"{p}: {n} conflict(s) -> both sides kept")
    rx = re.compile(r"(?<![A-Za-z0-9_./\\-])(" + "|".join(MOVED) + r")\.bat(?![A-Za-z0-9_])")
    for p in RENAME_IN:
        f = os.path.join(ROOT, p)
        if not os.path.exists(f):
            continue
        s = open(f, encoding="utf-8").read()
        back = "\\\\" if p.endswith(".py") and "tools\\\\bat" in s else "/"
        new = rx.sub(lambda m: f"tools{back}bat{back}{m.group(1)}.bat" if back == "/" else f"tools\\\\bat\\\\{m.group(1)}.bat", s)
        if new != s:
            open(f, "w", encoding="utf-8", newline="").write(new)
            print(f"{p}: {len(rx.findall(s))} old-place name(s) -> tools/bat/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
