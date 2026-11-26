"""Red team 2026-11-26 (big-zeroerr2 hang guard): (1) "flat" means flat on EVERY account (ATLAS / account C / combo / fleet / extra
legs live in their own data/ninjatrader_state_<x>.json); (2) a kill is never aimed at a pid that is not a Python process (pid reuse,
the old substring match); (3) no kill-restart loop (a 4th hang within 2 h is reported, not killed). Fakes only: nothing is killed.
    python -X utf8 -m tests.test_hang_guard_rt
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import hang_guard as HG     # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    tmp = tempfile.mkdtemp()
    try:
        d = os.path.join(tmp, "data")
        os.makedirs(d)
        json.dump({"saved_at": 0}, open(os.path.join(d, "live_state.json"), "w"))
        json.dump({"legs": []}, open(os.path.join(d, "ninjatrader_state.json"), "w"))
        check("1. LIT flat, no other account file: flat", HG.all_flat_reason(tmp) is None, HG.all_flat_reason(tmp))
        json.dump({"legs": [{"status": "protected", "instrument": "MNQ 12-26"}]}, open(os.path.join(d, "ninjatrader_state_acctb.json"), "w"))
        why = HG.all_flat_reason(tmp)
        check("1. ATLAS (acctb) holds a protected leg: NOT flat (no kill)", why and "acctb" in why, why)
        json.dump({"legs": [{"status": "closed"}]}, open(os.path.join(d, "ninjatrader_state_acctb.json"), "w"))
        open(os.path.join(d, "ninjatrader_state_fleet_x.json"), "w").write("{broken")
        why = HG.all_flat_reason(tmp)
        check("1. an unreadable account state file: NOT flat (fails closed)", why and "unreadable" in why, why)
        os.remove(os.path.join(d, "ninjatrader_state_fleet_x.json"))
        json.dump({"legs": [{"status": "protected"}]}, open(os.path.join(d, "ninjatrader_state_simcheck.json"), "w"))
        check("1. the self-test's simcheck file is not an account", HG.all_flat_reason(tmp) is None, HG.all_flat_reason(tmp))
        # 2. pid checks (Windows path, tasklist faked)
        keep_run, keep_name = subprocess.run, os.name
        out = {"txt": '"NinjaTrader.exe","1234","Console","1","300,000 K"\n'}
        subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a, 0, out["txt"], "")
        try:
            os.name = "nt"
            check("2. pid 123 vs a tasklist line for pid 1234: no such process (no substring match)", HG._image(123) == "", HG._image(123))
            check("2. pid 1234 now belongs to NinjaTrader: the server counts as gone", HG.alive(1234) is False)
            check("2. kill_tree refuses a pid that is not Python", HG.kill_tree(1234) is False)
            out["txt"] = '"python.exe","1234","Console","1","90,000 K"\n'
            check("2. the server's own python pid: alive", HG.alive(1234) is True)
        finally:
            subprocess.run, os.name = keep_run, keep_name
        # 3. no restart loop
        sp = os.path.join(tmp, "hg.json")
        now = 1_800_000_000
        json.dump({"hist": [{"t": now - 600 * i, "killed": True} for i in range(1, 4)]}, open(sp, "w"))
        kills, notes = [], []
        clock = {"t": now}
        g = HG.Guard(1, 1, root=tmp, clock=lambda: clock["t"], ping_fn=lambda: False, alive_fn=lambda: True,
                     kill_fn=lambda: kills.append(1) or True, flat_fn=lambda: None, notify=lambda t, b, k: notes.append(t),
                     state_path=sp, stacks=os.path.join(tmp, "none.txt"))
        g.started = now - 10_000
        for i in range(12):
            clock["t"] = now + 20 * i
            r = g.step()
        check("3. 3 kills in the last 2 h: a 4th hang is NOT killed, ONE alert", not kills and notes.count("PC server hangs again: NOT restarted") == 1,
              (kills, notes, r))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nhang guard red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
