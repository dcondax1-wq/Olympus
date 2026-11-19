"""Weekly disk clean for the Claude container (owner 2026-11-15: a full disk stopped a helper). Dry run by default.

    python tools/disk_clean.py            say what it would free, item by item
    python tools/disk_clean.py --apply    free it
Removes only:
  - helper worktrees under .claude/worktrees whose branch is fully merged, whose tree is clean and idle for 12 h (a running
    helper is never touched)
  - test temp folders in /tmp (the names the suites use: le_*, privacy-*, board_test_*, nqbot_dryrun_*, prometheus_page_*,
    playwright_chromiumdev_profile-* ...) that nothing touched for 3 h and that no running process has open (2026-11-19)
  - download caches that rebuild themselves: pip, uv, npm (each tool's own clean command; skipped while that tool runs)
  - this checkout's __pycache__ folders and the research replay cache research/runs/_cache (both rebuilt on demand; skipped
    while anything inside is open or was touched in the last 3 h)
Never: the repo's tracked files, data/, /tmp/claude-* (agent logs), lock files, Playwright's browsers, other checkouts."""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDLE_S = 3 * 3600
# the temp folders the test suites and shot scripts make (tempfile.mkdtemp prefixes); anything else in /tmp stays
TMP_TEST = re.compile(r"^(le_|privacy-|board_test_|nqbot_dryrun_|cities_card_|prometheus_page_|jhome|fleet_dry_|"
                      r"playwright_chromiumdev_profile-|playwright-artifacts-|forge_plus_|decide_test|daphne_branches_|lite_test|"
                      r"holo_fix_|athena_unit_|athena_train_|archive-st-|sibyl|arb-|planner-core-|phone_holo|erg-|helios-ref-|"
                      r"hb_board|stoa-real-|rapid_replay_|pythia-|pheme-|chry-|e2e_|dbg_|jfixdiag_|\.org\.chromium\.Chromium\.)")
TMP_NEVER = re.compile(r"^(claude|\.X|ssh-|systemd-|snap|tmux|.*\.lock$|.*\.pid$|.*\.sock$)")
CACHES = (("pip", (".cache", "pip"), ["pip", "cache", "purge"]),
          ("uv", (".cache", "uv"), ["uv", "cache", "clean"]),
          ("npm", (".npm", "_cacache"), ["npm", "cache", "clean", "--force"]))


def git(*a, cwd=ROOT):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def size(p):
    if os.path.isfile(p) or os.path.islink(p):
        try:
            return os.lstat(p).st_size
        except OSError:
            return 0
    t = 0
    for d, _, fs in os.walk(p):
        for f in fs:
            try:
                t += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
    return t


def newest(p):
    """The newest change time anywhere inside p (the folder itself included)."""
    try:
        t = os.lstat(p).st_mtime
    except OSError:
        return time.time()
    for d, ds, fs in os.walk(p):
        for n in ds + fs:
            try:
                t = max(t, os.lstat(os.path.join(d, n)).st_mtime)
            except OSError:
                pass
    return t


def open_paths():
    """Every path a running process has open, as its cwd or root (Linux /proc). None when /proc cannot be read: then
    nothing that depends on it is touched."""
    if not os.path.isdir("/proc"):
        return None
    out = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        for sub in ("cwd", "root"):
            try:
                out.add(os.readlink(f"/proc/{pid}/{sub}"))
            except OSError:
                pass
        try:
            for fd in os.listdir(f"/proc/{pid}/fd"):
                try:
                    out.add(os.readlink(f"/proc/{pid}/fd/{fd}"))
                except OSError:
                    pass
        except OSError:
            pass
    return out


def running(names):
    """True when a process whose command is one of `names` (pip, uv, npm ...) is running."""
    try:
        for pid in os.listdir("/proc"):
            if pid.isdigit():
                try:
                    with open(f"/proc/{pid}/cmdline", "rb") as fh:
                        argv = [a.decode("utf-8", "replace") for a in fh.read().split(b"\0") if a]
                except OSError:
                    continue
                if any(os.path.basename(a) in names for a in argv[:3]):
                    return True
    except OSError:
        return True
    return False


def busy(p, opened, now, idle=IDLE_S):
    """Something has it open (as a file, a cwd or a root), or it changed in the last `idle` seconds."""
    if opened is None:
        return True
    pre = p.rstrip("/") + "/"
    if any(o == p or o.startswith(pre) for o in opened):
        return True
    return now - newest(p) < idle


def plan(root=ROOT, tmp="/tmp", home=None, now=None, opened=None, worktrees=True, caches=True):
    """[(kind, path)]: what --apply would remove. kind: worktree | tmp | cache:<tool> | pycache | runcache."""
    now = time.time() if now is None else now
    opened = open_paths() if opened is None else opened
    home = home or os.path.expanduser("~")
    out = []
    if worktrees:
        for w in sorted(glob.glob(os.path.join(root, ".claude", "worktrees", "*"))):
            c, br = git("rev-parse", "--abbrev-ref", "HEAD", cwd=w)
            if c or not br:
                continue
            c1, ahead = git("rev-list", "--count", f"HEAD..{br}")
            c2, st = git("status", "--porcelain", "--untracked-files=no", cwd=w)
            idx = os.popen(f"git -C '{w}' rev-parse --git-path index").read().strip()
            idx = idx if os.path.isabs(idx) else os.path.join(w, idx)
            quiet = os.path.exists(idx) and os.path.getmtime(idx) < now - 12 * 3600   # a helper still at work touches its index
            if c1 == 0 and ahead == "0" and c2 == 0 and not st and quiet:
                out.append(("worktree", w))
    if os.path.isdir(tmp):
        for name in sorted(os.listdir(tmp)):
            p = os.path.join(tmp, name)
            if TMP_NEVER.match(name) or not TMP_TEST.match(name) or os.path.islink(p):
                continue
            if not busy(p, opened, now):
                out.append(("tmp", p))
    if caches:
        for tool, rel, _cmd in CACHES:
            p = os.path.join(home, *rel)
            if os.path.isdir(p) and shutil.which(tool) and not running({tool, tool + "3"}):
                out.append((f"cache:{tool}", p))
    skip = {".git", "node_modules", ".venv", "venv"}
    for d, ds, _fs in os.walk(root):
        ds[:] = [x for x in ds if x not in skip and not (d == root and x == ".claude")]
        if "__pycache__" in ds:
            p = os.path.join(d, "__pycache__")
            if not busy(p, opened, now, idle=60):              # every import rewrites a .pyc: only one open or written this minute stays
                out.append(("pycache", p))
            ds.remove("__pycache__")
    rc = os.path.join(root, "research", "runs", "_cache")
    if os.path.isdir(rc) and not busy(rc, opened, now):
        out.append(("runcache", rc))
    return out


def remove(kind, p, root=ROOT, run=subprocess.run):
    if kind == "worktree":
        git("worktree", "remove", "-f", "-f", p, cwd=root)
    elif kind.startswith("cache:"):
        cmd = next(c for t, _r, c in CACHES if "cache:" + t == kind)
        run(cmd, capture_output=True, text=True, timeout=600)
    elif os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p, ignore_errors=True)
    else:
        try:
            os.remove(p)
        except OSError:
            pass


def main(argv=None) -> int:
    apply = "--apply" in (argv if argv is not None else sys.argv[1:])
    items = plan()
    total = 0
    for kind, p in items:
        n = size(p)
        total += n
        print(f"  {'free' if apply else 'would free'} {n / 1e9:5.2f} GB  {kind:9} {p}")
        if apply:
            remove(kind, p)
    if apply and any(k == "worktree" for k, _ in items):
        git("worktree", "prune")
    print(f"{'freed' if apply else 'would free'} {total / 1e9:.1f} GB in {len(items)} item(s)" + ("" if apply else " (dry run: add --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
