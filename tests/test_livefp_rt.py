"""red team #44 (day-livefp 2026-11-27): a REPLACED tick file of the same / larger size restarts the day (no mixed trades); a stuck
build child is stopped before a new one starts (never two); data/livefp/ is git-ignored (an untracked file on the PC).
    python -X utf8 -m tests.test_livefp_rt
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def write(p, base, n=80):
    t0 = int(dt.datetime(2026, 11, 27, 10, 0, tzinfo=ET).timestamp() * 1000)
    with open(p, "w") as fh:
        fh.write("t_ms,price,size,bid,ask\n")
        for i in range(n):
            px = base + (i % 5) * 0.25
            fh.write(f"{t0 + i * 1000},{px:.2f},1,{px - 0.25:.2f},{px:.2f}\n")


def main():
    from engine import livefp as F
    now = dt.datetime(2026, 11, 27, 10, 9, tzinfo=ET).timestamp()
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "le_ticks"))
        p, out = os.path.join(td, "le_ticks", "NQ_2026-11-27.csv"), os.path.join(td, "out")
        write(p, 21000.0)
        F.build(td, out, now)
        write(p, 22000.0)                       # replaced with a file of the SAME size (other prices)
        F.build(td, out, now)
        d = json.load(open(os.path.join(out, "fp.json")))
        b = d["bars"][0] if d["bars"] else {}
        check("a replaced same-size file restarts the day (only the new trades)", d["rows"] == 80 and b.get("l", 0) >= 22000.0, (d["rows"], b.get("l")))
    # a stuck child
    class P:
        def __init__(self):
            self.killed = False
        def poll(self):
            return 0 if self.killed else None
        def kill(self):
            self.killed = True
        def wait(self, t):
            return 0
    old = P()
    with tempfile.TemporaryDirectory() as out:
        F._P.update(proc=old, started=1000.0)
        started = []
        ok = F.kick(1000.0 + F.BUILD_TIMEOUT_S + 1, out, spawn=lambda: started.append(1) or P())
        check("a child older than BUILD_TIMEOUT_S is killed before the new one starts", ok and old.killed and started == [1], (ok, old.killed))
        F._P.update(proc=P(), started=5000.0)
        check("a young running child: no second one", F.kick(5010.0, out, spawn=lambda: started.append(2) or P()) is False and started == [1])
        F._P.update(proc=None, started=0.0)
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", "data/livefp/state.json"], cwd=ROOT)
    check("data/livefp/ is git-ignored", r.returncode == 0, r.returncode)
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
