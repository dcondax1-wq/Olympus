"""Ship in one command (owner 2026-11-15, "save usage"): checks, then push to the ONE home, dcondax1-wq/Olympus branch pc.

    python tools/ship.py              smoke check + model list check, then push (refuses on a red check or a dirty tree)
    python tools/ship.py --zip DIR    also build the PC code zip (OLYMPUS_BACKUP_<date>_<sha>.zip + .sha256.txt) into DIR
    python tools/ship.py --no-tests   push without the smoke check (only right after you ran the area's own tests)
Pushes HEAD to dcondax1-wq/Olympus refs/heads/pc only (owner 2026-11-20: "Olympus branch pc is now the main home"): the remote whose
URL is that repo, whatever its name (origin in a fresh clone, olympus on older checkouts). The old demetrades2000-coder/nq-liquidity-engine
repo is never pushed to any more, even when a remote still points at it (docs/AUTO_UPDATE.md)."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME_REPO, BRANCH = "dcondax1-wq/olympus", "pc"     # the only push target (compared lower-case)
OLD_REPO = "demetrades2000-coder/nq-liquidity-engine"   # retired 2026-11-20: never pushed
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


def _repo_of(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    u = u[:-4] if u.endswith(".git") else u
    u = u.split("github.com", 1)[-1].lstrip(":/")
    return "/".join(u.split("/")[-2:])


def home_remote() -> str | None:
    """The git remote that points at dcondax1-wq/Olympus (None = none; then nothing is pushed)."""
    for name in sh("git", "remote").split():
        if _repo_of(sh("git", "remote", "get-url", "--push", name, check=False)) == HOME_REPO:
            return name
    return None


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


def vault_sync() -> bool:
    """night-reds2 2026-11-23: vault/ is GENERATED from the repo (tools/obsidian_brain.py: STATE.md, docs, research write-ups,
    the app map). A landing that changed those left it stale until the nightly rebuild, and tests.test_obsidian_brain g went
    red on every branch cut from it. Rebuilt here (1-2 s, deterministic) and committed as its own commit before the push.
    True = a rebuild commit was made. A failing build never blocks a ship (the test then says so)."""
    r = subprocess.run([sys.executable, "-X", "utf8", "tools/obsidian_brain.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        return False
    b = subprocess.run([sys.executable, "-X", "utf8", "tools/obsidian_brain.py"], cwd=ROOT, capture_output=True, text=True)
    if b.returncode != 0:
        print(f"  [..] vault rebuild failed: {(b.stdout + b.stderr).strip()[-200:]}")
        return False
    if not sh("git", "status", "--porcelain", "--", "vault", check=False):
        return False
    sh("git", "add", "-A", "--", "vault")
    sh("git", "commit", "-q", "-m", "vault: rebuilt for this landing (tools/obsidian_brain.py)")
    print("  [OK] vault/ was stale: rebuilt and committed")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip")
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args(argv)
    dirty = [ln for ln in sh("git", "status", "--porcelain").splitlines() if not ln.startswith("??")]
    if dirty:
        raise SystemExit("[STOP] uncommitted changes: commit first\n  " + "\n  ".join(dirty[:10]))
    sh(sys.executable, "tools/model_versions.py", "--check")
    vault_sync()
    if subprocess.run([sys.executable, "tools/win_paths.py"], cwd=ROOT).returncode != 0:   # even with --no-tests: a bad name
        raise SystemExit("[STOP] a file name Windows refuses: the PC update would roll back. Nothing pushed")  # blocks every PC update
    # LEAD_CHECKLIST A3 (2026-11-23): the Research Brain + Hub data follow LEDGER / write-ups / decisions; a stale file turns
    # tests.test_brain_hub / test_research_hub2 red on the phone site. Order matters: the hub reads brain-data.json.
    for tool in ("tools/build_brain_hub.py", "tools/build_research_hub.py", "tools/build_strategy_lab.py"):
        if subprocess.run([sys.executable, tool, "--check"], cwd=ROOT).returncode != 0:
            subprocess.run([sys.executable, tool], cwd=ROOT)
            raise SystemExit(f"[STOP] {tool} was stale: rebuilt it; commit the new data file and ship again. Nothing pushed")
    if not a.no_tests and subprocess.run([sys.executable, "tests/smoke.py"], cwd=ROOT).returncode != 0:
        raise SystemExit("[STOP] smoke check red: nothing pushed")
    rem = home_remote()
    if rem is None:
        raise SystemExit(f"[STOP] no git remote points at {HOME_REPO}: git remote add olympus https://github.com/dcondax1-wq/Olympus")
    ok = push(rem, f"refs/heads/{BRANCH}")
    print(f"[{'OK' if ok else 'FIX'}] Olympus pc ({rem})   at {sh('git', 'rev-parse', '--short', 'HEAD')}   (old repo: not pushed)")
    if a.zip:
        print(f"[OK] zip {build_zip(a.zip)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
