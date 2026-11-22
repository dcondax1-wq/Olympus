"""Publish the phone site to GitHub Pages (dcondax1-wq.github.io) from the cloud (owner 2026-11-18: "get it off Netlify, do it
through GitHub, keep a backup"). Netlify stays up as the backup host.

    python tools/gh_publish.py            build (pc_publish folder provider = privacy pass + lite set), copy, commit, push
    python tools/gh_publish.py --dry-run  build and copy only, no commit / push

What goes out: exactly pc_publish's privacy-checked folder output, minus runs/ (2,300 backtest files, 233 MB; the Netlify site
never had them), plus the 3D Data City (privacy-checked file by file), plus .nojekyll. A cloud build has no NinjaTrader, so every
"connected": false in home.json / data.json becomes null (unknown): the live PC feed (ntfy) is the only source of connection state,
never a cloud build. Paced so GitHub never sees a bot: at most MAX_PER_DAY publishes a day, and nothing is pushed when nothing changed.
Never touches the trading bot, live_model*.json or any order."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
REPO = os.environ.get("LE_GH_SITE_DIR", "/home/user/dcondax1-wq.github.io")
WORK = os.environ.get("LE_GH_SITE_WORK", os.path.join(ROOT, "data", "gh_publish"))
MAX_PER_DAY = 6                     # 4 -> 6 (2026-11-19): a morning fix for the owner; still far from bot-like
SKIP = ("runs/",)
NAME, EMAIL = "dcondax1-wq", "dcondax1-wq@users.noreply.github.com"


def unknown_connection(obj):
    """Every "connected": False -> None, recursively (a cloud build cannot know). Returns how many were changed."""
    n = 0
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "connected" and v is False:
                obj[k] = None
                n += 1
            else:
                n += unknown_connection(v)
    elif isinstance(obj, list):
        for v in obj:
            n += unknown_connection(v)
    return n


def run(*cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def mirror(out, repo, skip=SKIP):
    """out -> repo (keep .git, never runs/): copy only files whose bytes differ, delete only files that are gone. Before
    (2026-11-20) the whole Pages copy was deleted and every file copied again: git then re-hashed ~280 MB of new mtimes on every
    publish. -> (copied, removed)."""
    import filecmp
    want = set()
    copied = removed = 0
    for base, dirs, files in os.walk(out):
        rel_base = os.path.relpath(base, out).replace(os.sep, "/")
        rel_base = "" if rel_base == "." else rel_base + "/"
        dirs[:] = [d for d in dirs if not (rel_base + d + "/").startswith(skip)]
        for f in files:
            rel = rel_base + f
            want.add(rel)
            src, dst = os.path.join(base, f), os.path.join(repo, *rel.split("/"))
            if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src) and filecmp.cmp(src, dst, shallow=False):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    for base, dirs, files in os.walk(repo, topdown=False):
        rel_base = os.path.relpath(base, repo).replace(os.sep, "/")
        if rel_base == ".git" or rel_base.startswith(".git/"):
            continue
        rel_base = "" if rel_base == "." else rel_base + "/"
        for f in files:
            if rel_base + f not in want and rel_base + f != ".nojekyll":
                os.remove(os.path.join(base, f))
                removed += 1
        if rel_base and not os.listdir(base):
            os.rmdir(base)
    return copied, removed


def pushes_today(log_path, today):
    try:
        with open(log_path, encoding="utf-8") as fh:
            return sum(1 for line in fh if line.startswith(today))
    except OSError:
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(os.path.join(REPO, ".git")):
        print(f"[FIX] no clone at {REPO}: add_repo dcondax1-wq/dcondax1-wq.github.io, then clone it there")
        return 1
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    log_path = os.path.join(WORK, "pushes.log")
    if not a.dry_run and pushes_today(log_path, today) >= MAX_PER_DAY:
        print(f"[SKIP] already {MAX_PER_DAY} publishes today (paced so GitHub never sees a bot)")
        return 0
    out = os.path.join(WORK, "out")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, LE_DASH_BUILD="1")   # the cloud build refreshes business/dash.json (never on the PC: tools/build_web_dashboard.py)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pc_publish.py"), "--work", WORK, "--provider", "folder",
                        "--folder", out, "--force", "--strict"], cwd=ROOT, text=True, capture_output=True, env=env)
    if r.returncode:
        print("[FIX] build failed:\n" + r.stdout[-800:] + r.stderr[-800:])
        return 1
    from tools import site_privacy
    site = os.path.join(WORK, "site")
    dc = os.path.join(site, "datacity")
    for base, _, files in os.walk(dc):
        for f in files:
            full = os.path.join(base, f)
            rel = os.path.relpath(full, site).replace(os.sep, "/")
            raw = open(full, "rb").read() if f.endswith(".json") else None
            if site_privacy.private_file(rel, raw):
                continue
            dst = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(full, dst)
    changed = 0
    for name in ("home.json", "data.json"):
        p = os.path.join(out, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            n = unknown_connection(d)
            if n:
                with open(p, "w", encoding="utf-8") as fh:
                    json.dump(d, fh, separators=(",", ":"))
                changed += n
    copied, removed = mirror(out, REPO)
    open(os.path.join(REPO, ".nojekyll"), "a").close()
    print(f"[OK] mirror: {copied} file(s) copied, {removed} removed (unchanged files untouched)")
    print(f"[OK] site copied ({changed} cloud 'not connected' flags set to unknown)")
    if a.dry_run:
        return 0
    run("git", "add", "-A", cwd=REPO)
    if not run("git", "status", "--porcelain", cwd=REPO).stdout.strip():
        print("[OK] nothing changed: nothing pushed")
        return 0
    sha = run("git", "rev-parse", "--short", "HEAD", cwd=ROOT).stdout.strip()
    run("git", "-c", f"user.name={NAME}", "-c", f"user.email={EMAIL}", "commit", "-qm", f"Olympus phone site ({sha})", cwd=REPO)
    p = run("git", "-c", "push.negotiate=true", "push", "origin", "HEAD:main", cwd=REPO, check=False)
    if p.returncode:
        print("[FIX] push failed:\n" + p.stderr[-600:])
        return 1
    os.makedirs(WORK, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now(dt.timezone.utc).isoformat()} {sha}\n")
    print("[OK] published: https://dcondax1-wq.github.io/jarvis/ (live in about a minute)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
