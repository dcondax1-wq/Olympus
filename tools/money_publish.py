#!/usr/bin/env python3
"""MONEY PUBLISH: copies the money engine's JSON to the site so the Mint, Stoa and the five money pages can read ../money/*.json. PAPER ONLY.

  python tools/money_publish.py --site <site_dir>              copy money_out/*.json -> <site_dir>/money/
  python tools/money_publish.py --site <site_dir> --src DIR    another source folder
  python tools/money_publish.py --selftest

Only the contract files are copied (<id>.json and index.json): never the lock file, a scanner's state file or anything else. When the source has no
index.json (the engine has not run yet) it builds a SAMPLE index from the bundled fixtures (status sample, "not real"), so the pages are never blank
and never show invented money as real. Stdlib only, writes only under <site_dir>/money/.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import money_engine as M  # noqa: E402

DEFAULT_SRC = M.DEFAULT_OUT
# sibyl_forward.json = Sibyl's own paper ledger (tools/money/sibyl_ledger.py writes it next to sibyl.json; the Sibyl page reads
# money/sibyl_forward.json). QA round 6: it was never copied, so a real ledger could not reach the page.
KEEP = set(M.IDS) | {"index", "sibyl_forward"}
# when no ledger exists yet: an honest "not started" file (kind 'none': sibylcore.normOwn ignores it, exactly as for a missing file), so the
# page gets a file and not a 404 in the console
EMPTY_FORWARD = {"v": 1, "kind": "none", "published": False, "note": "Sibyl's own paper ledger has not started yet (tools/money/sibyl_ledger.py)."}


def publish(src: str, site: str, quiet: bool = False) -> list[str]:
    """Copy the contract JSON files from src to <site>/money/. Returns the file names written."""
    dst = os.path.join(site, "money")
    os.makedirs(dst, exist_ok=True)
    work = None
    if not os.path.isfile(os.path.join(src, "index.json")):
        work = tempfile.mkdtemp(prefix="money-sample-")
        M.run(work, True, 5, scanners=os.path.join(work, "none"), quiet=True)   # fixtures only: a sample index, never a scanner
        src = work
        if not quiet:
            print("money_publish: no index.json yet, publishing the SAMPLE index")
    done = []
    try:
        for name in sorted(os.listdir(src)):
            base, ext = os.path.splitext(name)
            if ext != ".json" or base not in KEEP:
                continue
            if M.read_json(os.path.join(src, name)) is None:   # a half-written or broken file is never published
                continue
            tmp = os.path.join(dst, name + ".tmp")
            shutil.copyfile(os.path.join(src, name), tmp)
            os.replace(tmp, os.path.join(dst, name))
            done.append(name)
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)
    fwd = os.path.join(dst, "sibyl_forward.json")
    if not os.path.exists(fwd):
        with open(fwd, "w", encoding="utf-8") as fh:
            json.dump(EMPTY_FORWARD, fh, separators=(",", ":"))
    if not quiet:
        print(f"money_publish: {len(done)} files -> {dst}")
    return done


def selftest() -> int:
    tmp = tempfile.mkdtemp(prefix="money-pub-")
    site, src = os.path.join(tmp, "site"), os.path.join(tmp, "src")
    a = publish(src if os.path.isdir(src) else os.path.join(tmp, "nothing"), site, True)
    ok1 = "index.json" in a and len(a) == 6
    os.makedirs(src)
    M.run(src, True, 5, scanners=os.path.join(tmp, "none"), quiet=True)
    open(os.path.join(src, "mercury_state.json"), "w").write("{}")
    open(os.path.join(src, "broken.json"), "w").write("{")
    open(os.path.join(src, "sibyl.json"), "w").write("{nope")
    b = publish(src, site, True)
    ok2 = "mercury_state.json" not in b and "broken.json" not in b and "sibyl.json" not in b and "index.json" in b
    fw = M.read_json(os.path.join(site, "money", "sibyl_forward.json")) or {}
    ok3 = fw.get("kind") == "none" and fw.get("published") is False
    open(os.path.join(src, "sibyl_forward.json"), "w").write('{"v": 1, "kind": "sibyl-forward", "bets": []}')
    c = publish(src, site, True)
    ok4 = "sibyl_forward.json" in c and (M.read_json(os.path.join(site, "money", "sibyl_forward.json")) or {}).get("kind") == "sibyl-forward"
    print(("[PASS] " if ok3 else "[FAIL] ") + "no ledger yet -> an honest 'not started' sibyl_forward.json (no 404 on the Sibyl page)")
    print(("[PASS] " if ok4 else "[FAIL] ") + "a real sibyl_forward.json ledger is published")
    print(("[PASS] " if ok1 else "[FAIL] ") + "no source -> a sample index and the five sample files")
    print(("[PASS] " if ok2 else "[FAIL] ") + "state files, unknown files and broken JSON are never published")
    return 0 if ok1 and ok2 and ok3 and ok4 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Copy the money engine's JSON to <site>/money/.")
    ap.add_argument("--site")
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.site:
        ap.error("--site is required")
    publish(a.src, a.site, a.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
