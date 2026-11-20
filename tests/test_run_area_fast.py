"""The faster landing runner (day-quality round 2, 2026-11-20): tests/suite_map.py + the parallel lanes / browser lock of tests/run_area.py.

  a. mapper: a change selects exactly the suites that read it (disk_clean.py -> disk_clean only), prose selects nothing, a shared kit
     file or a file no suite maps runs the whole area, another area's file is skipped, a changed suite file runs itself
  b. browser detection: Playwright / browser_kit suites are browser, plain ones (also one that names a chromium temp folder) are not
  c. the lock: taken when free, a second holder waits then times out, an outer `flock` of this process tree is recognised
     (no self-deadlock), released after
  d. run_all: plain suites run at once (3 x 1 s on 3 jobs < 2.5 s), browser suites one at a time and each under the lock,
     --no-lock takes none, rows come back in the area's order
    python -X utf8 -m tests.test_run_area_fast
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import browser_lock as BL  # noqa: E402
import run_area as RA  # noqa: E402
import suite_map as M  # noqa: E402

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:500]})" if detail and not cond else ""))


def main() -> int:
    pc, nq = RA.suites_for("pc"), RA.suites_for("nq")
    p = M.select(pc, ["tools/disk_clean.py"])
    check("a. tools/disk_clean.py selects disk_clean only in the pc area", p["run"] == ["disk_clean"] and not p["fallback"], p["run"])
    check("a. ... and names every skipped suite with a reason", len(p["skipped"]) == len(pc) - 1 and all(p["skipped"].values()))
    p = M.select(pc, ["tools/site_checks.py"])
    check("a. tools/site_checks.py selects site_checks", "site_checks" in p["run"] and "disk_clean" not in p["run"], p["run"])
    p = M.select(nq, ["engine/lit_live.py"])
    check("a. engine/lit_live.py runs the live-loop suites (lit_live, sizing_caps) in nq", {"lit_live", "sizing_caps"} <= set(p["run"]), p["run"])
    p = M.select(nq, ["STATE.md", "docs/SELF_HEAL.md", "research/writeups/x.md", "research/handoff/2026-11-20/quality/a.png"])
    check("a. prose only (STATE, docs, write-ups, hand-off pictures) runs nothing", p["run"] == [] and not p["fallback"], p)
    for f in ("tests/browser_kit.py", "tests/__init__.py", "tools/web_public/olympus/olympus.js", "requirements.txt"):
        p = M.select(pc, [f])
        check(f"a. shared {f} -> the whole area", p["run"] == pc and "shared" in p["fallback"], p["fallback"])
    p = M.select(pc, ["engine/" + "zz" + "_unmapped.py"])          # built here so this file itself does not "read" it
    check("a. a file no suite maps -> the whole area (safe fallback)", p["run"] == pc and "no suite maps" in p["fallback"], p["fallback"])
    p = M.select(nq, ["engine/kalshi_adapt.py"])
    check("a. another area's file (engine/kalshi_adapt.py in nq) is skipped, not a fallback", not p["fallback"] and "lit_live" not in p["run"], p)
    p = M.select(pc, ["tests/test_disk_clean.py"])
    check("a. a changed suite file runs itself", p["run"] == ["disk_clean"], p["run"])
    check("b. browser: athena_page, jarvis_core, zenith_mode; plain: disk_clean (names a chromium folder), site_checks, lit_live",
          all(M.is_browser(n) for n in ("athena_page", "jarvis_core", "zenith_mode")) and not any(M.is_browser(n) for n in ("disk_clean", "site_checks", "lit_live")),
          {n: M.is_browser(n) for n in ("athena_page", "jarvis_core", "zenith_mode", "disk_clean", "site_checks", "lit_live")})

    tmp = tempfile.mkdtemp(prefix="le_lock_")
    lock = os.path.join(tmp, "b.lock")
    try:
        with BL.hold(lock, wait=5) as how:
            held = os.getpid() in BL.holders(lock)
            code = ("import sys; sys.path.insert(0, %r); import browser_lock as BL\n"
                    "try:\n    with BL.hold(%r, wait=1.5, poll=0.2): print('GOT')\nexcept TimeoutError: print('TIMEOUT')") % (HERE, lock)
            out = os.path.join(tmp, "contender.txt")      # a contender OUTSIDE this process tree (else it is the ancestor's lock)
            subprocess.run(["sh", "-c", f"setsid {sys.executable} -c \"$0\" > {out} 2>&1 &", code], timeout=30)
            for _ in range(100):
                if os.path.exists(out) and open(out).read().strip():
                    break
                time.sleep(0.1)
            r = types.SimpleNamespace(stdout=open(out).read() if os.path.exists(out) else "", stderr="")
        check("c. taken when free (we are the holder)", how == "took" and held, (how, BL.holders(lock)))
        check("c. a second process waits, then times out", r.stdout.strip() == "TIMEOUT", r.stdout + r.stderr)
        r = subprocess.run([sys.executable, "-c", code.replace("wait=1.5", "wait=5")], capture_output=True, text=True, timeout=30)
        check("c. released after: the next one gets it", r.stdout.strip() == "GOT", r.stdout + r.stderr)
        if shutil.which("flock"):
            code2 = ("import sys; sys.path.insert(0, %r); import browser_lock as BL\n"
                     "with BL.hold(%r, wait=3, poll=0.2) as how: print(how)") % (HERE, lock)
            t0 = time.time()
            r = subprocess.run(["flock", "-w", "5", lock, sys.executable, "-c", code2], capture_output=True, text=True, timeout=30)
            check("c. under an outer `flock` of the same lock: recognised as the ancestor's, no deadlock",
                  r.stdout.strip() == "ancestor" and time.time() - t0 < 3, (r.stdout, r.stderr, time.time() - t0))

        calls, live = [], {"n": 0, "max": 0, "br": 0, "br_max": 0}
        mu = threading.Lock()
        browser = {"b1", "b2"}

        def fake_run_one(name, budget, env, args=()):
            with mu:
                live["n"] += 1
                live["max"] = max(live["max"], live["n"])
                if name in browser:
                    live["br"] += 1
                    live["br_max"] = max(live["br_max"], live["br"])
            locked = holding["n"] > 0
            time.sleep(1.0)
            with mu:
                live["n"] -= 1
                if name in browser:
                    live["br"] -= 1
                calls.append((name, locked))
            return {"suite": name, "passed": 1, "failed": 0, "seconds": 1.0, "state": "PASS", "exit": 0, "tail": "", "fails": []}

        holding = {"n": 0, "takes": 0}
        real_hold = BL.hold
        import contextlib

        @contextlib.contextmanager
        def counted_hold(path, wait=2400.0, poll=1.0):
            with real_hold(path, wait, poll) as how:
                holding["n"] += 1
                holding["takes"] += 1
                try:
                    yield how
                finally:
                    holding["n"] -= 1
        saved = (RA.run_one, M.is_browser, RA.gate)
        BL.hold = counted_hold
        RA.run_one, M.is_browser, RA.gate = fake_run_one, (lambda n: n in browser), (lambda *_a: "")
        try:
            args = types.SimpleNamespace(budget=60, gate=0, gate_wait=0, strict=False, no_lock=False, lock=lock, lock_wait=10)
            t0 = time.time()
            rows = RA.run_all(["p1", "b1", "p2", "b2", "p3"], args, {}, 3)
            took = time.time() - t0
            check("d. rows in the area's order", [r["suite"] for r in rows] == ["p1", "b1", "p2", "b2", "p3"], [r["suite"] for r in rows])
            check("d. three plain suites at once next to the browser lane (5 x 1 s in < 2.6 s)", took < 2.6 and live["max"] >= 3, (took, live))
            check("d. browser suites one at a time, each under its own take of the lock (2 takes for 2 suites); plain ones take none",
                  live["br_max"] == 1 and all(lk for n, lk in calls if n in browser) and holding["takes"] == 2, (calls, holding))
            calls.clear()
            args.no_lock = True
            holding["takes"] = 0
            RA.run_all(["b1", "p1"], args, {}, 2)
            check("d. --no-lock: browser suites run without the lock", not any(lk for _n, lk in calls) and holding["takes"] == 0, calls)
        finally:
            RA.run_one, M.is_browser, RA.gate = saved
            BL.hold = real_hold
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
