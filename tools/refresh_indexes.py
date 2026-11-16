"""Rebuild every committed generated index in the right order (night team D, 2026-11-16).

    python tools/refresh_indexes.py           rebuild: write-ups INDEX.md -> Archive -> Colosseum -> Ergasterion -> Pinakes, then Herald --check
    python tools/refresh_indexes.py --check   only check (exit 1 and name the stale ones)

Why: a new research run or write-up makes the committed archive / colosseum / ergasterion / pinakes files stale, and their page tests
(run by tests/run_gate.py --fast) then go red. Run this after adding research, then commit the changed files. Stdlib, about 30 s."""
from __future__ import annotations

import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# order matters: the Archive reads the write-ups, Ergasterion reads the Archive index, Pinakes catalogues every file
STEPS = [("writeups", ["-X", "utf8", "tools/writeups_index.py"]), ("archive", ["tools/archive_build.py"]), ("colosseum", ["tools/colosseum_build.py"]),
         ("ergasterion", ["tools/ergasterion_build.py"]), ("pinakes", ["tools/pinakes_build.py"])]


def main(argv=None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    bad = []
    for name, args in STEPS:
        if check and name == "colosseum":                     # colosseum_build.py has no --check: the page test compares it
            continue
        r = subprocess.run([sys.executable, *args] + (["--check"] if check else []), cwd=ROOT, capture_output=True, text=True)
        tail = ((r.stdout + r.stderr).strip().splitlines() or [""])[-1][:140]
        print(f"[{'OK ' if r.returncode == 0 else 'BAD'}] {name:<12} {tail}")
        if r.returncode:
            bad.append(name)
    r = subprocess.run([sys.executable, "tools/herald_build.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    print(f"[{'OK ' if r.returncode == 0 else 'BAD'}] {'herald':<12} {(r.stdout + r.stderr).strip()[-140:]}")
    if r.returncode:
        bad.append("herald (python tools/herald_build.py --date <the edition's date>)")
    print("all indexes up to date" if not bad else "stale: " + ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
