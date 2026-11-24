"""Red team on day-zerotouch2 (2026-11-24). Temp git repo, nothing real touched.

    python -X utf8 -m tests.test_zerotouch2_rt        (~3 s)

1. the phone inbox is read newest-by-TIME: with 14 old status-* / update-* files on the branch, a new pause-* (or restart-* /
   resume_entries-*) tap is still among the 12 read (FOUND: sorted by NAME, so 'pause-...' sorted before every old 'status-'
   / 'update-' file and fell out of the 12 for good).
2. auto-park never touches a rule file the running bot reads: MFFU / firm rules, the combo rule values, the owner's Decide
   answers (as for second_model.json / live_model*.json / data/); a plain code / doc file stays parkable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import remote_ctl as RC, self_heal as SH  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info != '' and not ok else ''}")
    RES.append(bool(ok))


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout


def main():
    with tempfile.TemporaryDirectory() as tmp:
        git(tmp, "init", "-q")
        git(tmp, "config", "user.email", "t@example.com")
        git(tmp, "config", "user.name", "t")
        d = os.path.join(tmp, "control", "inbox")
        os.makedirs(d)
        t0 = 1795600000
        for i in range(7):
            for cmd in ("status", "update"):
                n = f"{cmd}-{t0 + 60 * i}-a{i}"
                json.dump({"id": n, "ts": t0 + 60 * i, "cmd": cmd}, open(os.path.join(d, n + ".json"), "w"))
        new = f"pause-{t0 + 3600}-zz"
        json.dump({"id": new, "ts": t0 + 3600, "cmd": "pause", "until": "tomorrow"}, open(os.path.join(d, new + ".json"), "w"))
        git(tmp, "add", "-A")
        git(tmp, "commit", "-q", "-m", "inbox")
        got = [json.loads(t)["id"] for t in RC.read_inbox(tmp, ref="HEAD")]
        check("1. 14 old status/update files + a NEW pause tap: the pause is read", new in got and len(got) == RC.INBOX_MAX, got)
        check("1. the oldest files are the ones left out", f"status-{t0}-a0" not in got and f"update-{t0}-a0" not in got, got)

    for f in ("research/lit/mffu_rules.json", "research/props/firm_rules.json", "research/lab/combo_50k.json",
              "tools/web_public/business/decisions.json", "second_model.json", "live_model_lit.json", "data/rapid.json"):
        check(f"2. never parked: {f}", not SH.parkable(f))
    check("2. a code / doc file stays parkable", SH.parkable("engine/trade_home.py") and SH.parkable("docs/OWNER_MANUAL.md"))
    ok = sum(RES)
    print(f"\nzerotouch2 red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
