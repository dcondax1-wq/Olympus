"""Screenshots of the real-account views (2026-10-28: Home "Today · real accounts" + Safety, Real results, REAL next to
paper figures) on both dashboards, drawn from a real PC heartbeat (account names masked), with a console-error check.
Needs Playwright + Chromium and a built phone site (tools/build_web_dashboard.py --out <site>).

    git fetch origin heartbeat
    python -X utf8 -m tests.shots_real --site <built site> --out <dir> [--hb heartbeat.json]

PC at 1440 and 390 px (dark + light), phone at 390 px. Exit code 1 when a page logs a console error or does not draw.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.shots_board import heartbeat, masked, restore_files, shifted, snapshot_files, start_pc  # noqa: E402
from tests.shots_brain import _launch, _real  # noqa: E402


def serve_site(site, hb):
    from engine import live_board
    tmp = tempfile.mkdtemp(prefix="le_real_site_")
    dst = os.path.join(tmp, "site")
    shutil.copytree(site, dst)
    web = os.path.join(ROOT, "tools", "web_public")
    for n in os.listdir(web):                      # the working tree's app files over the built copy
        if os.path.isfile(os.path.join(web, n)):
            shutil.copy(os.path.join(web, n), os.path.join(dst, n))
    bd = masked(live_board.from_heartbeat(hb, now=int(time.time()), where="live", n_trades=40))
    for name in ("data.json", "home.json"):
        p = os.path.join(dst, name)
        d = json.load(open(p, encoding="utf-8"))
        d["board"] = bd
        json.dump(d, open(p, "w", encoding="utf-8"), default=str)

    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=dst, **k)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", tmp


def _wait(pg, sel, errors, what, t=60000):
    try:
        pg.wait_for_selector(sel, timeout=t)
        return True
    except Exception as e:
        errors.append(f"{what}: {sel} not drawn ({e.__class__.__name__})")
        return False


def pc_shots(base, out, errors, shots):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = _launch(p)
        for w, h in ((1440, 900), (390, 844)):
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if w > 500 else 2)
            pg = ctx.new_page()
            pg.on("console", lambda m: errors.append(f"pc{w} console: {m.text}") if m.type == "error" and _real(m.text) else None)
            pg.on("pageerror", lambda e: errors.append(f"pc{w} pageerror: {e}") if _real(str(e)) else None)
            pg.add_init_script("localStorage.setItem('page', 'cc'); localStorage.setItem('nx.fx', 'off');")
            pg.goto(base + "/?fxfixed", wait_until="domcontentloaded")
            pg.wait_for_function("() => window.LE && window.LE.go", timeout=60000)
            # a stopped bot opens the Start page first (once its status arrives): wait for that, then go Home
            try:
                pg.wait_for_selector("#page-start.active", timeout=20000)
            except Exception:
                pass
            pg.wait_for_timeout(800)
            pg.evaluate("() => window.LE.go('cc')")
            _wait(pg, "#page-cc.active #ccReal .rc-today .rc-acct", errors, f"pc{w} home")
            _wait(pg, "#page-cc.active #ccSafe .rc-safe", errors, f"pc{w} safety")
            pg.wait_for_timeout(900)
            f = os.path.join(out, f"dash_pc_home_{w}.png"); pg.screenshot(path=f); shots.append(f)
            f = os.path.join(out, f"dash_pc_home_{w}_full.png"); pg.screenshot(path=f, full_page=True); shots.append(f)
            pg.evaluate("() => window.LE.go('real')")
            _wait(pg, "#page-real.active .rc-res .rc-kpis", errors, f"pc{w} real")
            pg.wait_for_timeout(700)
            pg.evaluate("() => document.querySelector('#page-real [data-rc-row=\"0\"]')?.click()")
            pg.wait_for_timeout(400)
            f = os.path.join(out, f"dash_pc_real_{w}_full.png"); pg.screenshot(path=f, full_page=True); shots.append(f)
            if w == 1440:
                pg.evaluate("() => window.LE.go('board')")
                _wait(pg, "#page-board.active .bd-trades", errors, "pc board")
                pg.wait_for_timeout(900)
                pg.evaluate("() => { const s = document.querySelector('#page-board .bd-seg[data-bd-f=\"src\"] button[data-v=\"all\"]'); s && s.click(); }")
                pg.wait_for_timeout(400)
                pg.evaluate("() => document.querySelector('#page-board .bd-trades')?.scrollIntoView({block: 'start'})")
                pg.wait_for_timeout(400)
                f = os.path.join(out, "dash_pc_board_paper_vs_real_1440.png"); pg.screenshot(path=f); shots.append(f)
                pg.evaluate("() => window.LE.go('cc')")
                _wait(pg, "#page-cc.active #ccReal .rc-acct", errors, "pc home again")
                pg.evaluate("() => document.getElementById('ccTheme')?.click()")
                pg.wait_for_timeout(1800)
                pg.evaluate("() => window.scrollTo(0, 0)")
                f = os.path.join(out, "dash_pc_home_1440_light.png"); pg.screenshot(path=f); shots.append(f)
                pg.evaluate("() => document.getElementById('ccTheme')?.click()")
            ctx.close()
        br.close()


def phone_shots(base, out, errors, shots):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = _launch(p)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(f"phone console: {m.text}") if m.type == "error" and _real(m.text) else None)
        pg.on("pageerror", lambda e: errors.append(f"phone pageerror: {e}") if _real(str(e)) else None)
        pg.goto(base + "/index.html?fxfixed#/today", wait_until="domcontentloaded")
        _wait(pg, ".rc-homebox .rc-acct", errors, "phone home")
        pg.wait_for_timeout(1500)
        f = os.path.join(out, "dash_phone_home_390.png"); pg.screenshot(path=f); shots.append(f)
        f = os.path.join(out, "dash_phone_home_390_full.png"); pg.screenshot(path=f, full_page=True); shots.append(f)
        pg.evaluate("() => { location.hash = '#/real'; }")
        _wait(pg, ".rc-res .rc-kpis", errors, "phone real")
        pg.wait_for_timeout(900)
        f = os.path.join(out, "dash_phone_real_390_full.png"); pg.screenshot(path=f, full_page=True); shots.append(f)
        w = pg.evaluate("() => document.documentElement.scrollWidth")
        if w > 392:
            errors.append(f"phone: horizontal scroll on #/real ({w} px wide)")
        br.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hb", default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    hb = heartbeat(a.hb)
    hb = shifted(hb, int(time.time()) - int(hb.get("t") or time.time()))
    snap = snapshot_files()
    errors, shots = [], []
    try:
        base = start_pc(hb)
        pc_shots(base, a.out, errors, shots)
        site, tmp = serve_site(a.site, hb)
        phone_shots(site, a.out, errors, shots)
        shutil.rmtree(tmp, ignore_errors=True)
    finally:
        restore_files(snap)
    for e in errors:
        print("ERROR", e)
    print(f"{'OK' if not errors else 'FAIL'}: {len(shots)} screenshots in {a.out}, {len(errors)} error(s)")
    for s in shots:
        print(" ", s)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
