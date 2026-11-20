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
  - on the PC (day-quality 2026-11-20): NinjaTrader's own log\\ and trace\\ text files after 14 days, NinjaTrader's automatic
    backup zips (backup\\) after 30 days (the newest 2 always stay), and the Windows pip / npm caches (%LOCALAPPDATA%)
Never: the repo's tracked files, data/, .git, /tmp/claude-* (agent logs), lock files, Playwright's browsers, other checkouts,
NinjaTrader's db / workspaces / templates. Every item passes one last guard (safe()) before it is listed.

    python tools/disk_clean.py --top 15   the dry run also lists the 15 biggest folders, each marked never / keep / safe
    python tools/disk_clean.py --nt DIR   NinjaTrader's folder (default NINJATRADER_FOLDER, else ~/Documents/NinjaTrader 8)"""
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
# (tool, its cache under the home folder, its own clean command, its cache under %LOCALAPPDATA% on Windows)
CACHES = (("pip", (".cache", "pip"), ["pip", "cache", "purge"], ("pip", "Cache")),
          ("uv", (".cache", "uv"), ["uv", "cache", "clean"], ("uv", "cache")),
          ("npm", (".npm", "_cacache"), ["npm", "cache", "clean", "--force"], ("npm-cache", "_cacache")))
NT_LOG_DAYS, NT_BACKUP_DAYS, NT_BACKUP_KEEP = 14, 30, 2
NEVER_TOP = {"data": "never (trades, journal, state, bars)", ".git": "keep (git history: see docs/SELF_HEAL.md shallow clone)",
             "accounts": "never (account files)", "logs": "keep (the weekly clean ages it)"}


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


def tracked(root) -> set:
    """Every path git tracks in this checkout (repo-relative, '/'), empty when it is no git checkout."""
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {x.decode("utf-8", "replace") for x in r.stdout.split(b"\0") if x} if r.returncode == 0 else set()


def safe(p, root, tracked_set) -> bool:
    """The last guard every item passes: never inside data/ or .git of the checkout, never a tracked file, never a folder that
    holds one. Paths outside the checkout (temp, caches, NinjaTrader) pass; their own rule chose them."""
    rel = os.path.relpath(os.path.abspath(p), os.path.abspath(root)).replace(os.sep, "/")
    if rel.startswith("../") or rel == "..":
        return True
    if rel in (".", "") or rel.split("/")[0] in ("data", ".git", "accounts") or rel in tracked_set:
        return False
    pre = rel.rstrip("/") + "/"
    return not any(t.startswith(pre) for t in tracked_set)


def nt_default(env=None):
    env = os.environ if env is None else env
    if env.get("NINJATRADER_FOLDER"):
        return env["NINJATRADER_FOLDER"]
    d = os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8")
    return d if os.path.isdir(d) else None


def nt_items(nt, now) -> list:
    """NinjaTrader's own text logs / traces after 14 days, its automatic backup zips after 30 days (newest 2 stay). Nothing else
    of NinjaTrader's (db, workspaces, templates, incoming / outgoing order files) is ever listed."""
    out = []
    if not nt or not os.path.isdir(nt):
        return out
    for sub in ("log", "trace"):
        d = os.path.join(nt, sub)
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            if n.lower().endswith((".txt", ".log")) and os.path.isfile(p) and now - os.path.getmtime(p) > NT_LOG_DAYS * 86400:
                out.append(("nt-log", p))
    d = os.path.join(nt, "backup")
    try:
        zs = sorted((os.path.join(d, n) for n in os.listdir(d) if n.lower().endswith(".zip")), key=lambda x: -os.path.getmtime(x))
    except OSError:
        zs = []
    for p in zs[NT_BACKUP_KEEP:]:
        if os.path.isfile(p) and now - os.path.getmtime(p) > NT_BACKUP_DAYS * 86400:
            out.append(("nt-backup", p))
    return out


def cache_dirs(home, env=None):
    """[(tool, folder, command)] of the download caches that exist (home folder and, on Windows, %LOCALAPPDATA%)."""
    env = os.environ if env is None else env
    out = []
    for c in CACHES:
        tool, rel, cmd = c[0], c[1], c[2]
        cands = [os.path.join(home, *rel)]
        if len(c) > 3 and env.get("LOCALAPPDATA"):
            cands.append(os.path.join(env["LOCALAPPDATA"], *c[3]))
        for p in cands:
            if os.path.isdir(p):
                out.append((tool, p, cmd))
                break
    return out


def biggest(root, top=12, tracked_set=None, extra=()):
    """[(bytes, path, mark)]: the biggest folders one and two levels into the checkout (+ `extra` folders such as the caches),
    each marked never / keep / safe-to-delete (by the plan) / has tracked files."""
    tracked_set = tracked(root) if tracked_set is None else tracked_set
    rows = []
    try:
        firsts = [os.path.join(root, n) for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)) and not os.path.islink(os.path.join(root, n))]
    except OSError:
        firsts = []
    for d in firsts:
        rows.append((size(d), d))
        if os.path.basename(d) in (".git", "node_modules"):
            continue
        try:
            for n in os.listdir(d):
                p = os.path.join(d, n)
                if os.path.isdir(p) and not os.path.islink(p):
                    rows.append((size(p), p))
        except OSError:
            pass
    rows += [(size(p), p) for p in extra if os.path.isdir(p)]
    out = []
    for n, p in sorted(rows, key=lambda r: -r[0])[:top]:
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        first = rel.split("/")[0]
        if first in NEVER_TOP:
            mark = NEVER_TOP[first]
        elif rel.startswith("../"):
            mark = "outside the checkout"
        elif any(t.startswith(rel + "/") for t in tracked_set):
            mark = "keep (git tracks files in it)"
        else:
            mark = "not tracked (check before deleting by hand)"
        out.append((n, p, mark))
    return out


def plan(root=ROOT, tmp="/tmp", home=None, now=None, opened=None, worktrees=True, caches=True, nt=None, env=None, tracked_set=None):
    """[(kind, path)]: what --apply would remove. kind: worktree | tmp | cache:<tool> | pycache | runcache | nt-log | nt-backup.
    Every item passes safe() (never data/, .git, a tracked file or a folder holding one)."""
    out = _plan(root, tmp, home, now, opened, worktrees, caches, env)
    now = time.time() if now is None else now
    out += nt_items(nt, now)
    tracked_set = tracked(root) if tracked_set is None else tracked_set
    return [(k, p) for k, p in out if k == "worktree" or safe(p, root, tracked_set)]


def _plan(root, tmp, home, now, opened, worktrees, caches, env):
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
        for tool, p, _cmd in cache_dirs(home, env):
            if shutil.which(tool) and not running({tool, tool + "3"}):
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
        cmd = next(c[2] for c in CACHES if "cache:" + c[0] == kind)
        run(cmd, capture_output=True, text=True, timeout=600)
    elif os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p, ignore_errors=True)
    else:
        try:
            os.remove(p)
        except OSError:
            pass


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    apply = "--apply" in argv
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 12
    nt = argv[argv.index("--nt") + 1] if "--nt" in argv else nt_default()
    tr = tracked(ROOT)
    items = plan(nt=nt, tracked_set=tr)
    if not apply and top > 0:
        print(f"Biggest folders (this checkout{' + download caches' if cache_dirs(os.path.expanduser('~')) else ''}):")
        for n, p, mark in biggest(ROOT, top, tr, extra=[c[1] for c in cache_dirs(os.path.expanduser("~"))]):
            safe_mark = "SAFE: in the list below" if any(p == q for _k, q in items) else mark
            print(f"  {n / 1e9:6.2f} GB  {os.path.relpath(p, ROOT) if not os.path.relpath(p, ROOT).startswith('..') else p:<42} {safe_mark}")
        print(f"NinjaTrader folder: {nt or 'not found (set NINJATRADER_FOLDER or --nt)'}")
        print("Safe to delete (nothing is removed in a dry run):")
    total = 0
    by_kind: dict = {}
    for kind, p in items:
        n = size(p)
        total += n
        by_kind[kind] = by_kind.get(kind, 0) + n
        print(f"  {'free' if apply else 'would free'} {n / 1e9:5.2f} GB  {kind:9} {p}")
        if apply:
            remove(kind, p)
    if apply and any(k == "worktree" for k, _ in items):
        git("worktree", "prune")
    if by_kind:
        print("  by kind: " + ", ".join(f"{k} {v / 1e9:.2f} GB" for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])))
    print(f"{'freed' if apply else 'would free'} {total / 1e9:.1f} GB in {len(items)} item(s)" + ("" if apply else " (dry run: add --apply)"))
    print("never touched: data/, .git, accounts/, files git tracks, NinjaTrader's db / workspaces / templates, agent logs, lock files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
