"""tools/perf_sweep.py (day-quality, Olympus v2 PERF team, 2026-11-20): the phone-profile sweep of every visible app + the offline pass.

  a. pure: the visible apps = apps-list minus doors.js ARCHIVE (+ jarvis, gate, hub); file kinds; long tasks -> count / max / TBT;
     a row from raw numbers; budgets (own over default, offline must be ok, sideways never); the table
  b. the real repo's budgets file is valid JSON and names only visible apps
  c. one real browser run on a 2-page fixture site (https, as GitHub Pages): a good app (worker-cached, shows "updated 5 min ago")
     opens offline WITH its age; a bad one (console error, 600 px wide, not cached) is caught: errors 1, sideways, offline not ok
    python -X utf8 -m tests.test_perf_sweep
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import perf_sweep as P  # noqa: E402

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:500]})" if detail and not cond else ""))


SITE = {
    "index.html": "<!doctype html><title>home</title><p>Home screen app</p><script>"
                  "if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js');</script>",
    "sw.js": "self.addEventListener('install', (e) => self.skipWaiting());\n"
             "self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));\n"
             "self.addEventListener('fetch', (e) => { const u = new URL(e.request.url); if (u.pathname.startsWith('/bad/')) return;\n"
             "  e.respondWith(fetch(e.request).then((r) => { const c = r.clone(); caches.open('t').then((k) => k.put(e.request, c)); return r; })\n"
             "    .catch(() => caches.match(e.request, { ignoreSearch: true }))); });\n",
    "good/index.html": "<!doctype html><meta name=viewport content='width=device-width'><title>good</title>"
                       "<main><h1>Good app</h1><p>Drawdown left $1,025 of $2,000. Data updated 5 min ago.</p></main>",
    "bad/index.html": "<!doctype html><meta name=viewport content='width=device-width'><title>bad</title>"
                      "<div style='width:600px'>A page that is too wide for a phone and logs an error</div><script>console.error('boom')</script>",
}


def main() -> int:
    vis = P.visible_apps()
    ids = [a for a, _p in vis]
    check("a. visible apps: the Doors set (no archived app) + jarvis, gate, hub", "nq" in ids and "ledger" in ids and "jarvis" in ids and "gate" in ids
          and "hub" in ids and "oracle" not in ids and "odeon" not in ids and len(ids) == len(set(ids)), ids)
    check("a. file kinds", [P.kind_of(u) for u in ("a/x.js?v=1", "b.mjs", "c.webp", "d.woff2", "e.css", "f.json", "g.html")]
          == ["js", "js", "img", "font", "css", "data", "other"])
    check("a. long tasks: count, longest, TBT (time over 50 ms each)", P.long_tasks([[0, 60], [10, 250], [20, 51]]) == {"lt_n": 3, "lt_max": 250, "tbt": 211}
          and P.long_tasks([]) == {"lt_n": 0, "lt_max": 0, "tbt": 0})
    raw = {"fcp": 900, "lcp": 1200, "nav": {"t": 10240, "e": 100}, "res": [{"n": "http://h/a.js", "t": 20480, "d": 40960, "e": 500},
                                                                          {"n": "http://h/b.webp", "t": 102400, "d": 102400, "e": 2000}], "heap": 3 * 1048576}
    r = P.row_of(raw, {"lt": [[0, 120]], "cls": 0.0123, "sideways": True}, ["console: x"], "http://h")
    check("a. a row: bytes by kind, paints, long tasks, CLS, errors, sideways, the 3 biggest files",
          r["kb"] == 130.0 and r["img_kb"] == 100.0 and r["js_kb"] == 40.0 and r["fcp_ms"] == 900 and r["lcp_ms"] == 1200 and r["lt_max"] == 120
          and r["tbt"] == 70 and r["cls"] == 0.012 and r["errors"] == 1 and r["sideways"] and r["top3"][0] == "/b.webp 100 KB", r)
    b = {"default": {"fcp_ms": 1000, "errors": 0, "offline": True, "sideways": False}, "x": {"fcp_ms": 1500}}
    check("a. budgets: the app's own number beats the default; offline must be ok; sideways never",
          P.over("x", dict(r, offline="ok"), b) == ["errors 1 > 0", "scrolls sideways"]
          and P.over("y", dict(r, offline="blank"), b) == ["errors 1 > 0", "offline blank", "scrolls sideways"]
          and P.over("z", {"error": "timeout"}, b) == ["did not load: timeout"], P.over("y", dict(r, offline="blank"), b))
    t = P.table([("x", dict(r, offline="ok", offline_age=True, offline_sw=True)), ("y", {"error": "timeout"})])
    check("a. the table: one row per app, offline 'ok +age (sw)', a load error as its own row",
          len(t) == 4 and "ok +age (sw)" in t[2] and "did not load: timeout" in t[3], t)
    try:
        bj = json.load(open(P.BUDGETS, encoding="utf-8"))
        check("b. tools/perf_budgets.json is valid and names only visible apps", isinstance(bj.get("default"), dict)
              and not [k for k in bj if k not in ("default", "_note") and k not in ids], [k for k in bj if k not in ids])
    except (OSError, ValueError) as e:
        check("b. tools/perf_budgets.json is valid", False, repr(e))

    site = tempfile.mkdtemp(prefix="le_perfsweep_")
    try:
        for rel, txt in SITE.items():
            p = os.path.join(site, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(txt)
        rows = dict(P.sweep(site, [("good", "good/"), ("bad", "bad/")], cpu=1, net="none", say=lambda *_a: None))
        g, bd = rows["good"], rows["bad"]
        check("c. a real run: the good app has a first paint and bytes", g.get("fcp_ms", 0) > 0 and g.get("kb", 0) > 0, g)
        check("c. the good app opens OFFLINE after one visit and shows its data age", g.get("offline") == "ok" and g.get("offline_age") and g.get("offline_sw"), g)
        check("c. the bad app: console error counted, sideways caught, offline not ok", bd.get("errors", 0) >= 1 and bd.get("sideways")
              and bd.get("offline") != "ok", bd)
    finally:
        shutil.rmtree(site, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
