"""Tracked files the PC bot / server / ops tasks rewrite by themselves (caches, daily data refreshes, check reports).

A local change to one of these is never the owner's work, so it must not block an update:
  * the dirty check (engine/autoupdate.py, the remote 'update', UPDATE.bat, scripts/one_time_setup.ps1) ignores them;
  * right before the fast-forward, the local copy of each one that the update ALSO changes is put back to HEAD
    (`git checkout HEAD -- <files>`), so `git merge --ff-only` / `git pull --ff-only` cannot fail on them. Ones the update
    does not touch keep their local copy (git carries it across a fast-forward); the bot rewrites them anyway.
Hand edits to any other tracked file (engine/*.py, live_model.json, ...) still block the update.

Why not .gitignore + `git rm --cached`: the commit that untracks them deletes them upstream, and a PC with the file locally
modified then fails the pull ("Your local changes would be overwritten"), which is exactly the bug. Keeping them tracked and
discarding before the pull works on every PC.

  python -m engine.generated_files --dirty            other (blocking) local changes, one per line; exit 1 if any
  python -m engine.generated_files --prepare-pull     fetch origin main, discard the generated files it changes; exit 0
  python -m engine.generated_files --discard-all      discard every dirty generated file (before a branch switch)
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GENERATED = (
    "cache/dash/*",                       # engine/dash_data.py dashboard cache (5y, bt_*, coverage, es_fresh)
    "data/GEX_1d.csv",                    # engine/gamma.py daily GEX refresh
    "data/VIX_1d.csv", "data/VXN_1d.csv", "data/CBOE_vol_1d.csv",   # engine/news.py CBOE daily closes
    "data/news/ff_thisweek.json", "data/news/ff_archive.csv", "data/news/hub.json",   # engine/news.py, tools/news_hub.py
    "data/news/events.csv", "data/news/official_meta.json",   # engine/news_official.py (ops task, once a day: future rows only)
    "data/lit_learning.json",             # engine/lit_learn.py learning loop
    "data/lit_journal.jsonl",             # LiveBot._journal: the LIT learning journal (2026-10-27: its 06:12 line blocked the update)
    "data/discovery.json",                # engine/discovery.py cache
    "data/confluence_registry.json", "research/CONFLUENCE_LOG.md",  # server.py learning cycle (engine.confluence_search)
    "research/lit/live_check.json", "research/lit/live_timing.json",  # tests the ops checks run
    "research/lit/live_exit_route.json", "research/lit/rehearsal.json",
    "tools/web_hub_snapshot.json",        # tools/build_web_dashboard.py
    "tools/web_public/business/week.json",   # tools/weekly_review.py (Friday ops task: ZEUS this week)
    "tools/web_public/business/dash.json",   # tools/money/dash_build.py (run by tools/build_web_dashboard.py, 2026-11-20)
)


def is_generated(path: str) -> bool:
    p = path.strip().strip('"').replace("\\", "/")
    return any(fnmatch.fnmatchcase(p, g) for g in GENERATED)


def porcelain_paths(text: str) -> list:
    """Paths from `git status --porcelain` lines (a rename 'R  a -> b' gives both)."""
    out = []
    for ln in (text or "").splitlines():
        if len(ln) < 4:
            continue
        for p in ln[3:].split(" -> "):
            out.append(p.strip().strip('"'))
    return out


def split_dirty(text: str) -> tuple:
    """(generated, other) changed tracked paths from `git status --porcelain --untracked-files=no`."""
    gen, other = [], []
    for p in porcelain_paths(text):
        (gen if is_generated(p) else other).append(p)
    return gen, other


def discard(git, paths) -> tuple:
    """Put these generated files back to HEAD (index + work tree). git(*args) -> (code, out). Only generated paths."""
    paths = [p for p in paths if is_generated(p)]
    if not paths:
        return 0, ""
    return git("checkout", "HEAD", "--", *paths)


_GIT = {"exe": None}


def git_exe() -> str:
    """git on PATH, else Git for Windows' or GitHub Desktop's own copy (the owner's Surface had no git on PATH for START
    BOT, 2026-10-25). Falls back to plain "git"."""
    if _GIT["exe"]:
        return _GIT["exe"]
    import glob
    import shutil
    exe = shutil.which("git")
    if not exe and os.name == "nt":
        cands = []
        for base in ("%ProgramFiles%", "%ProgramFiles(x86)%", "%LOCALAPPDATA%\\Programs"):
            cands += glob.glob(os.path.expandvars(base + r"\Git\cmd\git.exe"))
        cands += sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe")))[::-1]
        exe = next(iter(cands), None)
    _GIT["exe"] = exe or "git"
    return _GIT["exe"]


def _git(*args, cwd=ROOT, timeout=180):
    try:
        r = subprocess.run([git_exe(), *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 127, f"{e.__class__.__name__}: {e}"


def prepare_pull(git=_git, branch: str = "main") -> list:
    """Before `git pull --ff-only origin <branch>`: fetch, then discard the dirty generated files the pull changes.
    Returns the discarded paths. Never touches any other file (engine/autoupdate.fast_forward does the rest: ATLAS's
    account block moved out of second_model.json, files checked out from main by hand, a shallow history)."""
    c, st = git("status", "--porcelain", "--untracked-files=no")
    gen, _ = split_dirty(st) if c == 0 else ([], [])
    if not gen:
        return []
    c, _ = git("fetch", "-q", "origin", branch)
    if c != 0:
        return []
    c, ch = git("diff", "--name-only", "HEAD", f"origin/{branch}")
    up = set(ch.split()) if c == 0 else set()
    hit = [p for p in gen if p in up]
    if hit:
        discard(git, hit)
    return hit


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if "--dirty" in a:
        c, st = _git("status", "--porcelain", "--untracked-files=no")
        _, other = split_dirty(st) if c == 0 else ([], [])
        for p in other:
            print(p)
        return 1 if other else 0
    if "--discard-all" in a:                          # before a branch switch (scripts/one_time_setup.ps1)
        c, st = _git("status", "--porcelain", "--untracked-files=no")
        gen = split_dirty(st)[0] if c == 0 else []
        if gen:
            discard(_git, gen)
            print("  [OK]  Reset bot-made files: " + ", ".join(gen[:6]))
        return 0
    if "--prepare-pull" in a:
        hit = prepare_pull()
        if hit:
            print("  [OK]  Reset bot-made files the update replaces: " + ", ".join(hit[:6]))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
