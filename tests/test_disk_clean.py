"""tools/disk_clean.py (the weekly container clean) on a fixture: a fake /tmp, a fake checkout and a fake home.

  a. the dry run lists exactly the stale test temp folders, the checkout's __pycache__ and replay cache, the download
     caches; it deletes nothing
  b. never: a fresh test folder, one a process has open (file or cwd), /tmp/claude-* (agent logs), lock files, a folder
     that is not a test's, the repo's own files, data/, the run library, a pycache written this minute, other checkouts
     under .claude/, a venv, a cache whose tool is missing; open files unknown (no /proc) = busy
  c. --apply removes exactly the plan (a temp FILE too), the caches through their tool's own command

  python -X utf8 -m tests.test_disk_clean
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import disk_clean as DC  # noqa: E402

RES: list[bool] = []
H = 3600


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:900]})" if detail and not cond else ""))


def put(path, age_s, now, data=b"x" * 1000):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    t = now - age_s
    os.utime(path, (t, t))
    d = os.path.dirname(path)
    os.utime(d, (t, t))
    return path


def age_tree(p, age_s, now):
    t = now - age_s
    for d, ds, fs in os.walk(p):
        for n in ds + fs:
            os.utime(os.path.join(d, n), (t, t))
    os.utime(p, (t, t))


def main() -> int:
    now = time.time()
    base = tempfile.mkdtemp(prefix="dc_fixture_")
    try:
        tmp, root, home = (os.path.join(base, x) for x in ("tmp", "repo", "home"))
        # ---- /tmp
        old = [put(os.path.join(tmp, "board_test_aaaa", "data", "x.json"), 5 * H, now),
               put(os.path.join(tmp, "prometheus_page_bbbb", "site", "index.html"), 30 * H, now),
               put(os.path.join(tmp, "le_cs_cccc", "home", "f.txt"), 4 * H, now)]
        for d in ("board_test_aaaa", "prometheus_page_bbbb", "le_cs_cccc"):
            age_tree(os.path.join(tmp, d), 5 * H, now)
        chrom = put(os.path.join(tmp, ".org.chromium.Chromium.zzzz"), 6 * H, now, b"")          # a temp FILE
        keep_fresh = put(os.path.join(tmp, "board_test_fresh", "x.json"), 10 * 60, now)         # touched 10 min ago
        keep_open = put(os.path.join(tmp, "nqbot_dryrun_open", "state.json"), 9 * H, now)       # a process has it open
        keep_cwd = put(os.path.join(tmp, "fleet_dry_cwd", "a.txt"), 9 * H, now)                 # a process works in it
        age_tree(os.path.join(tmp, "nqbot_dryrun_open"), 9 * H, now)
        age_tree(os.path.join(tmp, "fleet_dry_cwd"), 9 * H, now)
        keep = [keep_fresh, keep_open, keep_cwd,
                put(os.path.join(tmp, "claude-0", "logs", "agent.jsonl"), 50 * H, now),          # agent logs: never
                put(os.path.join(tmp, "olympus_browser.lock"), 50 * H, now, b""),
                put(os.path.join(tmp, "le_heavy.lock"), 50 * H, now, b""),
                put(os.path.join(tmp, "notes_of_someone", "n.txt"), 50 * H, now)]                # not a test's folder
        # ---- the checkout
        pyc = [put(os.path.join(root, "engine", "__pycache__", "a.cpython-313.pyc"), 2 * H, now),
               put(os.path.join(root, "tools", "money", "__pycache__", "b.cpython-313.pyc"), 2 * H, now)]
        runc = put(os.path.join(root, "research", "runs", "_cache", "lit_x.pkl"), 10 * H, now)
        age_tree(os.path.join(root, "research", "runs", "_cache"), 10 * H, now)
        keep += [put(os.path.join(root, "engine", "lit.py"), 50 * H, now),
                 put(os.path.join(root, "data", "NQ_5m.csv"), 50 * H, now),
                 put(os.path.join(root, "research", "runs", "lit_live.json"), 50 * H, now),
                 put(os.path.join(root, "tests", "__pycache__", "now.cpython-313.pyc"), 5, now),       # written this minute
                 put(os.path.join(root, ".claude", "worktrees", "h1", "engine", "__pycache__", "c.pyc"), 9 * H, now),
                 put(os.path.join(root, ".venv", "lib", "__pycache__", "d.pyc"), 9 * H, now)]
        # ---- home caches (pip has a tool; "nosuchtool" does not)
        pipc = put(os.path.join(home, ".cache", "pip", "http-v2", "a", "b"), 50 * H, now, b"y" * 5000)
        opened = {keep_open, os.path.join(tmp, "fleet_dry_cwd"), "/proc/self/fd/0"}
        saved_caches, saved_which, saved_running = DC.CACHES, DC.shutil.which, DC.running
        DC.CACHES = (("pip", (".cache", "pip"), ["pip", "cache", "purge"]), ("nosuchtool", (".cache", "pip"), ["nosuchtool", "x"]))
        DC.shutil.which = lambda t: "/usr/bin/pip" if t == "pip" else None
        DC.running = lambda names: False
        try:
            items = DC.plan(root=root, tmp=tmp, home=home, now=now, opened=opened, worktrees=False)
            got = {(k, os.path.relpath(p, base)) for k, p in items}
            want = {("tmp", "tmp/board_test_aaaa"), ("tmp", "tmp/prometheus_page_bbbb"), ("tmp", "tmp/le_cs_cccc"),
                    ("tmp", "tmp/.org.chromium.Chromium.zzzz"), ("pycache", "repo/engine/__pycache__"),
                    ("pycache", "repo/tools/money/__pycache__"), ("runcache", "repo/research/runs/_cache"), ("cache:pip", "home/.cache/pip")}
            check("a. the plan is exactly the stale test folders + the temp file, two __pycache__, the replay cache and the pip cache",
                  got == want, {"extra": sorted(got - want), "missing": sorted(want - got)})
            check("a. the dry run (plan only) deletes nothing", all(os.path.exists(p) for p in old + pyc + keep + [runc, pipc, chrom]))
            check("b. the busy rule: a fresh, an open and a cwd folder are busy, a stale one is not; unknown open files (no /proc) = busy",
                  DC.busy(os.path.join(tmp, "board_test_fresh"), opened, now) and DC.busy(os.path.join(tmp, "nqbot_dryrun_open"), opened, now)
                  and DC.busy(os.path.join(tmp, "fleet_dry_cwd"), opened, now) and not DC.busy(os.path.join(tmp, "board_test_aaaa"), opened, now)
                  and DC.busy(os.path.join(tmp, "board_test_aaaa"), None, now))
            ran = []
            for k, p in items:
                DC.remove(k, p, root=root, run=lambda cmd, **kw: ran.append(cmd))
            check("c. --apply: every planned folder and the temp file are gone", not [p for p in old + pyc + [runc, chrom] if os.path.exists(p)],
                  [os.path.relpath(p, base) for p in old + pyc + [runc, chrom] if os.path.exists(p)])
            check("c. --apply: NOT ONE kept file was removed (fresh / open / cwd temp folders, agent logs, locks, a person's folder, "
                  "the repo's code, data, the run library, a pyc of this minute, other checkouts, a venv)",
                  all(os.path.exists(p) for p in keep), [os.path.relpath(p, base) for p in keep if not os.path.exists(p)])
            check("c. --apply: the pip cache is cleared by pip's own command (not deleted by hand)", ran == [["pip", "cache", "purge"]] and os.path.exists(pipc), ran)
        finally:
            DC.CACHES, DC.shutil.which, DC.running = saved_caches, saved_which, saved_running
        check("the real test-folder pattern never matches the agent logs, the browser lock or the heavy-job locks",
              not any(DC.TMP_TEST.match(n) and not DC.TMP_NEVER.match(n) for n in ("claude-0", "claude-code.log", "olympus_browser.lock", "heavy1.lock", "heavy2.lock")))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_disk_clean():                 # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
