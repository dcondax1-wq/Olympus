"""HERMETIC (night-hermetic 2026-11-23): tests never change the bot's LIVE files.

The PC's weekly self-test (engine/pc_selftest.py) runs suites ON THE OWNER'S PC: a test that writes data/arm_status.json,
rapid.json, accounts.json ... there changes live state (2026-11-22: data/arm_status.json left by a suite turned test_brain red).
  a. the write guard (tests/write_guard/sitecustomize.py): refuses a live write in raise mode, logs it in log mode, ignores temp
     folders, existing-folder makedirs and dir_fd bare names (shutil.rmtree of a temp folder)
  b. engine/pc_selftest.child_env seals every self-test child with it (LE_WRITE_GUARD=raise) + HOME / USERPROFILE / OLYMPUS_HOME in temp
  c. a SAMPLE of suites (the ones that were dirty, research/handoff/2026-11-23/HERMETIC.md) runs with data/ logs/ cache/ + the top
     config files snapshotted (sha1 of every file before / after, tools/hermetic_scan.py) and the write guard logging: nothing may change

    python -X utf8 -m tests.test_hermetic            # ~2-4 min (the sample); --quick = a + b only
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools import hermetic_scan as HS  # noqa: E402

RESULTS = []
SAMPLE = ("arm_report", "arm_rt", "go", "new_accounts", "launch_checklist", "run_switch", "start_api", "ops")


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"   -> {info!r}"[:600]))


def guard_unit():
    probe = os.path.join(ROOT, "data", "_hermetic_probe.txt")
    code = ("import os, shutil, tempfile\n"
            "os.makedirs('data', exist_ok=True)\n"
            "d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'data', 'x')); open(os.path.join(d, 'data', 'x', 'f'), 'w').write('1'); shutil.rmtree(d)\n"
            "r = []\n"
            "src = tempfile.mktemp(); open(src, 'w').write('t')\n"
            "for f in (lambda: open(%r, 'w'), lambda: os.replace(src, %r), lambda: open('live_model.json', 'a')):\n"
            "    try:\n        f(); r.append('open')\n    except PermissionError:\n        r.append('blocked')\n    except OSError:\n        r.append('oserr')\n"
            "print(','.join(r))\n") % (probe, os.path.join(ROOT, "data", "_hermetic_probe2"))
    env = HS.guard_env("", "unit", mode="raise")
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    check("a. raise mode: a temp folder (even one with a data/ inside) and makedirs on an existing data/ pass; a write into data/, a "
          "replace into data/ and an append to live_model.json are refused", p.stdout.strip() == "blocked,blocked,blocked"
          and not os.path.exists(probe), (p.stdout, p.stderr[-300:]))
    log = tempfile.mktemp(suffix=".jsonl")
    env = HS.guard_env(log, "unit", mode="log")
    subprocess.run([sys.executable, "-c", "import os; open('tools/_hp.txt','w').write('1'); os.remove('tools/_hp.txt'); "
                    "p='data/_hermetic_probe3'; open(p,'w').write('1'); os.remove(p)"], cwd=ROOT, env=env, timeout=60)
    rows = [json.loads(x) for x in open(log, encoding="utf-8")] if os.path.exists(log) else []
    kinds = {(r["kind"], r["path"].replace("\\", "/")) for r in rows}
    check("a. log mode: the live write is logged 'protected', another repo file 'repo' (allowed, for the scan)",
          ("protected", "data/_hermetic_probe3") in kinds and ("repo", "tools/_hp.txt") in kinds, kinds)
    try:
        os.remove(log)
    except OSError:
        pass


def selftest_env():
    from engine import pc_selftest as P
    tmp = tempfile.mkdtemp(prefix="herm_env_")
    env = P.child_env(tmp, base={"PATH": os.environ.get("PATH", ""), "HOME": "/home/owner", "USERPROFILE": "C:\\Users\\owner"})
    check("b. pc_selftest.child_env: the write guard in raise mode on PYTHONPATH, rooted at the repo",
          env.get("LE_WRITE_GUARD") == "raise" and env.get("PYTHONPATH", "").split(os.pathsep)[0] == HS.GUARD
          and env.get("LE_WRITE_GUARD_ROOT") == ROOT, {k: env.get(k) for k in ("LE_WRITE_GUARD", "PYTHONPATH", "LE_WRITE_GUARD_ROOT")})
    check("b. pc_selftest.child_env: HOME / USERPROFILE / OLYMPUS_HOME in the suite's temp folder (never the owner's ~/.olympus)",
          all(str(env.get(k, "")).startswith(tmp) for k in ("HOME", "USERPROFILE", "OLYMPUS_HOME")), env)
    src = open(os.path.join(ROOT, "engine", "pc_selftest.py"), encoding="utf-8").read()
    check("b. every self-test suite runs through child_env (run_suite)", "child_env(tmp)" in src)
    names = HS.suites_of([], True)
    check("b. the sample covers suites of the PC self-test", any(s in names for s in SAMPLE), names)


def sample_runs():
    for s in SAMPLE:
        if not os.path.exists(os.path.join(ROOT, "tests", f"test_{s}.py")):
            continue
        r = HS.run_one(s, timeout=600, restore=True)
        ch = r["changed"]
        check(f"c. tests.test_{s} leaves data/ logs/ cache/ + the config files as they were (rc {r['rc']}, {r['s']} s)",
              not r["dirty"], {"live": r["live_writes"][:6], "added": ch["added"][:6], "changed": ch["changed"][:6], "removed": ch["removed"][:6]})


if __name__ == "__main__":
    guard_unit()
    selftest_env()
    if "--quick" not in sys.argv:
        sample_runs()
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"\nhermetic: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    sys.exit(0 if ok == n else 1)
