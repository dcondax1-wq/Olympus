"""Phone screenshots of the Goals view, the new More hub, the All features page and the new cards (iPhone width 390 px),
with a console-error check and a "Could not draw" check on every page. Needs Playwright + Chromium.

    python tools/build_web_dashboard.py --state <cloud_monitor out>/state.json --out <site>
    python -X utf8 -m tests.shots_goals --site <site> --out research/handoff/2026-10-25/ui_phone

Exit code 1 when a page logs a console error or fails to draw.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.shots_brain import _launch, _real  # noqa: E402

# (file name, hash route, full page?, theme)
SHOTS = [
    ("01_home_goals", "#/today", False, "dark"),
    ("02_home_full", "#/today", True, "dark"),
    ("03_goals_page", "#/goals", True, "dark"),
    ("04_more_hub", "#/system", True, "dark"),
    ("05_all_features", "#/features", False, "dark"),
    ("06_week_calendar", "#/weekcal", True, "dark"),
    ("07_health_lights", "#/lights", True, "dark"),
    ("08_eval_timeline", "#/evaltl", True, "dark"),
    ("09_home_light", "#/today", False, "light"),
    ("10_atlas_stats", "#/atstats", True, "dark"),
]


def serve(site):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Q, directory=site)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def shots(site, out, only=None):
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    srv = serve(site)
    base = f"http://127.0.0.1:{srv.server_address[1]}/index.html?fxfixed"
    errors = []
    with sync_playwright() as p:
        br = _launch(p)
        for name, hash_, full, theme in SHOTS:
            if only and name not in only:
                continue
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                 service_workers="block")
            pg = ctx.new_page()
            pg.on("console", lambda m, n=name: errors.append(f"{n}: {m.text}") if m.type == "error" and _real(m.text) else None)
            pg.on("pageerror", lambda e, n=name: errors.append(f"{n} pageerror: {e}") if _real(str(e)) else None)
            pg.add_init_script(f"try {{ localStorage.setItem('le.theme', '\"{theme}\"'); localStorage.setItem('le.fx', '\"off\"'); "
                               "localStorage.setItem('le.more.instLater', '9999999999999'); } catch (e) {}")
            pg.goto(base + hash_, wait_until="domcontentloaded")
            try:
                pg.wait_for_function("() => typeof D !== 'undefined' && !!D", timeout=30000)
            except Exception:
                errors.append(f"{name}: data.json never loaded")
            pg.wait_for_timeout(2500)
            txt = pg.evaluate("() => document.querySelector('#page') ? document.querySelector('#page').innerText : ''")
            if "Could not draw" in txt:
                errors.append(f"{name}: Could not draw ({txt[:200]})")
            path = os.path.join(out, name + ".png")
            pg.screenshot(path=path, full_page=full)
            print("shot", path, flush=True)
            ctx.close()
        br.close()
    srv.shutdown()
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "handoff", "2026-10-25", "ui_phone"))
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    errs = shots(a.site, a.out, a.only)
    for e in errs:
        print("ERROR", e)
    print("console errors:", len(errs))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
