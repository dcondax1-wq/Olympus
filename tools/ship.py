"""Ship in one command (owner 2026-11-15, "save usage"): checks, then push to GitHub and to the backup the PC updates from.

    python tools/ship.py              smoke check + model list check, then push (refuses on a red check or a dirty tree)
    python tools/ship.py --zip DIR    also build the PC code zip (OLYMPUS_BACKUP_<date>_<sha>.zip + .sha256.txt) into DIR
    python tools/ship.py --no-tests   push without the smoke check (only right after you ran the area's own tests)
Pushes HEAD to origin claude/clever-heisenberg-51zwcr and, when the remote exists, to olympus refs/heads/pc (docs/AUTO_UPDATE.md)."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "claude/clever-heisenberg-51zwcr"
ZIP_EXCLUDE = ("research", "data", "docs/shots", "cache")


def sh(*a, check=True):
    r = subprocess.run(list(a), cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"[STOP] {' '.join(a)}: {(r.stdout + r.stderr).strip()[-400:]}")
    return r.stdout.strip()


def push(remote, ref):
    for i in range(4):
        r = subprocess.run(["git", "push", "-q", remote, f"HEAD:{ref}"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            return True
        print(f"  push {remote} retry {i + 1}: {r.stderr.strip()[-160:]}")
    return False


def build_zip(out):
    os.makedirs(out, exist_ok=True)
    sha = sh("git", "rev-parse", "--short=7", "HEAD")
    day = dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    z = os.path.join(out, f"OLYMPUS_BACKUP_{day}_{sha}.zip")
    sh("git", "archive", "--format=zip", "-9", "-o", z, "HEAD", "--", ".", *[f":(exclude){x}" for x in ZIP_EXCLUDE])
    h = hashlib.sha256(open(z, "rb").read()).hexdigest()
    with open(z[:-4] + ".sha256.txt", "w", encoding="utf-8") as f:
        f.write(f"{h}  {os.path.basename(z)}  {os.path.getsize(z) / 1048576:.1f} MB\n")
    return z


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip")
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args(argv)
    dirty = [ln for ln in sh("git", "status", "--porcelain").splitlines() if not ln.startswith("??")]
    if dirty:
        raise SystemExit("[STOP] uncommitted changes: commit first\n  " + "\n  ".join(dirty[:10]))
    sh(sys.executable, "tools/model_versions.py", "--check")
    if not a.no_tests and subprocess.run([sys.executable, "tests/smoke.py"], cwd=ROOT).returncode != 0:
        raise SystemExit("[STOP] smoke check red: nothing pushed")
    ok = push("origin", BRANCH)
    remotes = sh("git", "remote").split()
    ok_b = push("olympus", "refs/heads/pc") if "olympus" in remotes else None
    print(f"[{'OK' if ok else 'FIX'}] GitHub {BRANCH}   [{'OK' if ok_b else ('SKIP' if ok_b is None else 'FIX')}] backup olympus/pc"
          f"   at {sh('git', 'rev-parse', '--short', 'HEAD')}")
    if a.zip:
        print(f"[OK] zip {build_zip(a.zip)}")
    return 0 if ok and ok_b is not False else 1


if __name__ == "__main__":
    sys.exit(main())
