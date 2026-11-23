"""HERMETIC SCAN (night-hermetic 2026-11-23): which test suites touch the bot's LIVE files (data/, logs/, cache/, the strategy /
config files at the top, ~/.olympus) instead of a temp folder.

Why: the PC's weekly self-test (engine/pc_selftest.py) runs test suites ON THE OWNER'S PC; a test that writes data/arm_status.json,
rapid.json, accounts.json, keepalive.json ... there changes live state (2026-11-22: a pc-area suite left data/arm_status.json, which
then changed the Brain glance and turned tests.test_brain red).

Two independent detectors per suite, run one suite at a time:
  1. the write guard (tests/write_guard/sitecustomize.py, LE_WRITE_GUARD=log): every write by any Python process of the suite, with
     its path (children too);
  2. a snapshot of every file under data/ logs/ cache/ + the top config files (size + mtime + sha1 for files under 2 MB) before and
     after: also catches node / PowerShell writers the guard cannot see. A file that changed is restored from the snapshot copy
     (--restore, default on), so the scan itself leaves the folder as it found it.

    python tools/hermetic_scan.py pc nq fleet             the run_area areas (default: the PC self-test's suites)
    python tools/hermetic_scan.py --suites go,ops         given suites
    python tools/hermetic_scan.py --selftest              exactly engine/pc_selftest.SUITES
  -> scratch/hermetic/scan.json + a table on stdout (suite | rc | live files written | other repo files written)
Never runs tests.test_win_scripts. Read-only towards the bot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
GUARD = os.path.join(ROOT, "tests", "write_guard")
WATCH_DIRS = ("data", "logs", "cache")
WATCH_TOP = ("live_model.json", "live_model_lit.json", "live_model_engine.json", "second_model.json", "dashboard_view.json",
             "notify_settings.json", "update_source.json")
NEVER = {"win_scripts"}
HASH_MAX = 2 * 1024 * 1024


def snapshot(root: str = ROOT) -> dict:
    """{relative path: (size, mtime_ns, sha1 | None)} of every watched file."""
    out = {}
    paths = [os.path.join(root, t) for t in WATCH_TOP]
    for d in WATCH_DIRS:
        for dp, dn, fn in os.walk(os.path.join(root, d)):
            dn[:] = [x for x in dn if x != "__pycache__"]
            paths += [os.path.join(dp, f) for f in fn]
    for p in paths:
        try:
            st = os.stat(p)
        except OSError:
            continue
        h = None
        if st.st_size <= HASH_MAX:
            try:
                with open(p, "rb") as fh:
                    h = hashlib.sha1(fh.read()).hexdigest()
            except OSError:
                h = None
        out[os.path.relpath(p, root).replace("\\", "/")] = (st.st_size, st.st_mtime_ns, h)
    return out


def diff(a: dict, b: dict) -> dict:
    """{"added", "removed", "changed"} (content: the hash, else size + mtime)."""
    ch = [k for k in a if k in b and ((a[k][2] or b[k][2]) and a[k][2] != b[k][2] or not (a[k][2] or b[k][2]) and a[k][:2] != b[k][:2])]
    return {"added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)), "changed": sorted(ch)}


def backup(root: str, rels, dst: str) -> None:
    for r in rels:
        s = os.path.join(root, r)
        if os.path.isfile(s):
            os.makedirs(os.path.dirname(os.path.join(dst, r)), exist_ok=True)
            shutil.copy2(s, os.path.join(dst, r))


def guard_env(log: str, tag: str, base=None, mode: str = "log") -> dict:
    env = dict(os.environ if base is None else base)
    env["PYTHONPATH"] = GUARD + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.update({"LE_WRITE_GUARD": mode, "LE_WRITE_GUARD_LOG": log, "LE_WRITE_GUARD_TAG": tag, "LE_WRITE_GUARD_ROOT": ROOT})
    return env


def run_one(suite: str, timeout: float = 600, restore: bool = True, root: str = ROOT) -> dict:
    tmp = tempfile.mkdtemp(prefix=f"herm_{suite}_")
    log = os.path.join(tmp, "guard.jsonl")
    keep = os.path.join(tmp, "keep")
    before = snapshot(root)
    backup(root, [k for k in before if before[k][0] <= 20 * 1024 * 1024], keep)
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", f"tests.test_{suite}"], cwd=root, env=guard_env(log, suite),
                           capture_output=True, text=True, timeout=timeout)
        rc, tail = p.returncode, (p.stdout or "").strip().splitlines()[-1:] or [""]
    except subprocess.TimeoutExpired:
        rc, tail = -9, ["TIMEOUT"]
    after = snapshot(root)
    d = diff(before, after)
    rows = []
    try:
        with open(log, encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
    except OSError:
        pass
    live = sorted({r["path"] for r in rows if r.get("kind") == "protected"})
    repo = sorted({r["path"] for r in rows if r.get("kind") == "repo"})
    if restore:
        for r in d["changed"] + d["removed"]:
            s = os.path.join(keep, r)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(root, r))
        for r in d["added"]:
            try:
                os.remove(os.path.join(root, r))
            except OSError:
                pass
    shutil.rmtree(tmp, ignore_errors=True)
    return {"suite": suite, "rc": rc, "s": round(time.time() - t0, 1), "tail": tail[0][:100], "live_writes": live, "repo_writes": repo,
            "changed": d, "dirty": bool(live or d["added"] or d["removed"] or d["changed"])}


def suites_of(areas, selftest: bool) -> list:
    out = []
    if selftest or not areas:
        from engine import pc_selftest
        for s in pc_selftest.SUITES:
            for a in s.get("argv") or []:
                m = re.match(r"tests\.test_(\w+)$", str(a))
                if m:
                    out.append(m.group(1))
    if areas:
        import importlib.util
        sp = importlib.util.spec_from_file_location("run_area_h", os.path.join(ROOT, "tests", "run_area.py"))
        ra = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(ra)
        for a in areas:
            out += ra.AREAS.get(a, [])
    seen, res = set(), []
    for s in out:
        if s not in seen and s not in NEVER and os.path.exists(os.path.join(ROOT, "tests", f"test_{s}.py")):
            seen.add(s)
            res.append(s)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("areas", nargs="*")
    ap.add_argument("--suites", default="")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--no-restore", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "scratch", "hermetic", "scan.json"))
    a = ap.parse_args(argv)
    names = [x for x in a.suites.split(",") if x] or suites_of(a.areas, a.selftest)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    res = []
    for n in names:
        r = run_one(n, a.timeout, restore=not a.no_restore)
        res.append(r)
        ch = r["changed"]
        print(f"{'DIRTY' if r['dirty'] else 'clean'} {n:28s} rc={r['rc']:<3} {r['s']:>6}s live={r['live_writes'][:4]} "
              f"snap+={ch['added'][:3]} snap~={ch['changed'][:3]} snap-={ch['removed'][:3]} repo={r['repo_writes'][:3]}", flush=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(f"\n{sum(1 for r in res if r['dirty'])} dirty of {len(res)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
