"""red team #40 (day-blitzready 2026-11-27): ONE BLITZ paper runner (an OS lock: a 2nd one exits at once and writes nothing, even from
another process); no module the lane loads at run time can trade (engine.blitz + engine.blitz_paper import no adapter / broker / live loop).
    python -X utf8 -m tests.test_blitz_paper_rt
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES: list = []
TRADING = ("engine.ninjatrader", "engine.live", "engine.lit_live", "engine.account_b", "engine.second", "engine.atlas_exec",
           "engine.of_lane", "engine.broker", "engine.tradovate")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def main():
    from engine import blitz_paper as BP
    with tempfile.TemporaryDirectory() as td:
        lk = BP.run_lock(td)
        check("the first runner takes the run lock", lk is not None)
        ticks = []
        r = BP.loop(td, clock=lambda: 1764255600, sleep=lambda s: ticks.append(s), max_runs=2)
        check("a second runner exits at once and writes no heartbeat", r == 0 and not ticks
              and not os.path.exists(os.path.join(td, "data", BP.RUN)), (r, ticks))
        code = ("import sys; sys.path.insert(0, %r); from engine import blitz_paper as BP; print('free' if BP.run_lock(%r) else 'held')"
                % (ROOT, td))
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout.strip()
        check("another process sees the lock held", out == "held", out)
        lk.close()
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout.strip()
        check("freed when the first runner ends", out == "free", out)
    code = ("import sys; sys.path.insert(0, %r); import engine.blitz_paper as BP, engine.blitz as BZ; import pandas as pd; "
            "BP.read_bars(%r, 1764255600, nt=''); print(','.join(sorted(m for m in sys.modules if m.startswith('engine.'))))" % (ROOT, ROOT))
    mods = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120).stdout.strip().split(",")
    bad = [m for m in mods if m in TRADING]
    check("loading the lane + reading bars imports nothing that can trade", mods and not bad, (bad, mods))
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
