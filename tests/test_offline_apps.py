"""Every visible app opens OFFLINE after one visit (Olympus bar 5, day-quality 2026-11-20). Browser (tests/run_area.py takes the lock).

As on the phone: the Home Screen app (Zenith) opened once (it registers the root worker), the app opened once, the network cut, a
reload: the app must open (not the browser's "no internet" page). tools/perf_sweep.offline_sweep does the walk.
  * with the root worker's app-folder rule in (sw.js `appNetFirst`, research/handoff/2026-11-20/olympus2/perf/sw-offline.patch):
    EVERY visible app must be ok
  * before it lands: the apps with their own worker (zenith, jarvis, kalshi) must be ok, the rest is reported ("waits for the patch")
    python -X utf8 -m tests.test_offline_apps [--only nq,ledger]
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import perf_sweep as P  # noqa: E402

RES = []
ALWAYS = ("zenith", "jarvis", "kalshi")


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""))


def main() -> int:
    pages = P.visible_apps()
    if "--only" in sys.argv:
        want = sys.argv[sys.argv.index("--only") + 1].split(",")
        pages = [p for p in pages if p[0] in want]
    full = P.patch_in()
    res = P.offline_sweep(P.SITE, pages, say=lambda *_a: None)
    for app, r in res.items():
        ok = r.get("offline") == "ok"
        if full or app in ALWAYS:
            check(f"{app} opens offline after one visit{' (shows its data age)' if r.get('offline_age') else ''}", ok, r)
        else:
            print(f"[INFO] {app}: {r.get('offline')} (waits for the worker patch, LEAD_WIRES 1 of the perf hand-off)")
    print(f"\noffline: {'every app must open' if full else 'worker patch not in yet: only ' + ', '.join(ALWAYS) + ' are checked'}")
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
