"""Two-minute smoke check (owner 2026-11-15, "save usage"): the fast suites that catch most breakage, run in parallel.
Run it first; the big area / browser suites only after it is green.  python tests/smoke.py   (exit 0 = all green)"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITES = [
    ["-m", "engine.ninjatrader", "--selftest", "--quiet"],
    ["-X", "utf8", "-m", "tests.test_no_yahoo"],
    ["-X", "utf8", "-m", "tests.test_sizing_caps"],
    ["-X", "utf8", "-m", "tests.test_atlas_deep"],
    ["-X", "utf8", "-m", "tests.test_hidden_bots"],
    ["-X", "utf8", "-m", "tests.test_autoupdate_source"],
    ["-X", "utf8", "-m", "tests.test_apps_list"],
    ["-X", "utf8", "-m", "tests.test_zenith_mode"],
]


def run(args):
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        return args, r.returncode, tail[0][:110], time.time() - t0
    except subprocess.TimeoutExpired:
        return args, 124, "timed out (600 s)", time.time() - t0


def main() -> int:
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(run, SUITES))
    bad = 0
    for args, rc, tail, dt in res:
        name = args[-1] if args[-1].startswith("tests.") else " ".join(a for a in args if not a.startswith("-X") and a != "utf8")
        print(f"[{'OK ' if rc == 0 else 'BAD'}] {name:<34} {dt:5.0f}s  {tail}")
        bad += rc != 0
    print(f"smoke: {len(res) - bad}/{len(res)} green in {time.time() - t0:.0f}s")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
