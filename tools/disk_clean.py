"""Weekly disk clean for the Claude container (owner 2026-11-15: a full disk stopped a helper). Dry run by default.

    python tools/disk_clean.py            say what it would free
    python tools/disk_clean.py --apply    free it
Removes only: helper worktrees under .claude/worktrees whose branch is fully merged, whose tree is clean and idle for 12 h (a running helper is never touched); leftover test
temp folders in /tmp named le_* / privacy-* older than 2 days. Never touches the repo's files, data/, or anything else."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*a, cwd=ROOT):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def size(p):
    t = 0
    for d, _, fs in os.walk(p):
        for f in fs:
            try:
                t += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
    return t


def plan():
    out = []
    for w in sorted(glob.glob(os.path.join(ROOT, ".claude", "worktrees", "*"))):
        c, br = git("rev-parse", "--abbrev-ref", "HEAD", cwd=w)
        if c or not br:
            continue
        c1, ahead = git("rev-list", "--count", f"HEAD..{br}")
        c2, st = git("status", "--porcelain", "--untracked-files=no", cwd=w)
        idx = os.popen(f"git -C '{w}' rev-parse --git-path index").read().strip()
        idx = idx if os.path.isabs(idx) else os.path.join(w, idx)
        quiet = os.path.exists(idx) and os.path.getmtime(idx) < time.time() - 12 * 3600   # a helper still at work touches its index
        if c1 == 0 and ahead == "0" and c2 == 0 and not st and quiet:
            out.append(("worktree", w))
    cut = time.time() - 2 * 86400
    for p in glob.glob("/tmp/le_*") + glob.glob("/tmp/privacy-*"):
        try:
            if os.path.isdir(p) and os.path.getmtime(p) < cut:
                out.append(("tmp", p))
        except OSError:
            pass
    return out


def main(argv=None) -> int:
    apply = "--apply" in (argv if argv is not None else sys.argv[1:])
    items = plan()
    total = 0
    for kind, p in items:
        n = size(p)
        total += n
        print(f"  {'free' if apply else 'would free'} {n / 1e9:5.2f} GB  {kind:8} {p}")
        if apply:
            if kind == "worktree":
                git("worktree", "remove", "-f", "-f", p)
            else:
                shutil.rmtree(p, ignore_errors=True)
    if apply:
        git("worktree", "prune")
    print(f"{'freed' if apply else 'would free'} {total / 1e9:.1f} GB in {len(items)} item(s)" + ("" if apply else " (dry run: add --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
