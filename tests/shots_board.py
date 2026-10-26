"""Screenshots of the live board (engine/live_board.py) on both dashboards, drawn from a real PC heartbeat (account names
masked), with a console-error check. Needs Playwright + Chromium.

  PC     the real server app (server.py, nothing auto-starts: LE_NO_AUTOSTART=1, no heartbeat / live.json / audit threads)
         on a free port, /api/next/board answered from the heartbeat -> the Command center "Right now" row and the Live
         board page at 1440x900, dark and light
  phone  a built site (tools/build_web_dashboard.py --out <site>) copied to a temp folder with the heartbeat's board in
         data.json / home.json -> Home (the Right now cut) and #/board at 390x844

    git fetch origin heartbeat
    python -X utf8 -m tests.shots_board --site <built site> --out research/handoff/2026-10-26/ui_live [--hb heartbeat.json]

Exit code 1 when a page logs a console error or does not draw.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.shots_brain import _launch, _real  # noqa: E402

MASK = re.compile(r"MFFU[A-Z]*\d{6,}")


def masked(obj):
    """Account numbers out of the pictures: MFFUEVBLD...016 -> 'MFFU 50K eval' / 'MFFU 25K eval'."""
    s = json.dumps(obj, default=str)
    names = sorted(set(MASK.findall(s)))
    for i, n in enumerate(names):
        s = s.replace(n, ["MFFU-50K-EVAL", "MFFU-25K-EVAL"][i] if i < 2 else f"MFFU-ACCOUNT-{i + 1}")
    s = re.sub(r"DESKTOP-[A-Z0-9]+", "SURFACE", s)
    return json.loads(s)


def heartbeat(path=None) -> dict:
    if path:
        return json.load(open(path, encoding="utf-8"))
    r = subprocess.run(["git", "show", "origin/heartbeat:heartbeat.json"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("no heartbeat: git fetch origin heartbeat (or pass --hb)")
    return json.loads(r.stdout)


FRESH_KEYS = {"t", "last_t", "last_ok_t", "last_1m_t", "last_5m_t", "last_error_t", "at", "checks_t", "tick_t"}


def shifted(obj, delta: int):
    """--fresh: the check-in times moved forward by delta (the PC's own ages stay as it reported them; trade times and
    levels are untouched), so the pictures show a live PC rather than one silent since the heartbeat."""
    if isinstance(obj, dict):
        return {k: (v + delta if k in FRESH_KEYS and isinstance(v, int) and 1.7e9 < v < 2.1e9 else shifted(v, delta)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shifted(x, delta) for x in obj]
    return obj


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def snapshot_files() -> dict:
    """The tracked files the dashboard server refreshes on import / start (bar cache, VIX / VXN, news): restored after the
    shots so a screenshot run leaves the checkout as it was."""
    import glob
    pats = ["cache/dash/*.json", "data/VIX_1d.csv", "data/VXN_1d.csv", "data/news/*.csv", "data/news/*.json", "tools/web_hub_snapshot.json"]
    out = {}
    for p in pats:
        for f in glob.glob(os.path.join(ROOT, p)):
            try:
                out[f] = open(f, "rb").read()
            except OSError:
                pass
    return out


def restore_files(snap: dict):
    for f, b in snap.items():
        try:
            if not os.path.exists(f) or open(f, "rb").read() != b:
                open(f, "wb").write(b)
        except OSError:
            pass


def start_pc(hb) -> str:
    for k, v in (("LE_NO_AUTOSTART", "1"), ("LE_HEARTBEAT", "0"), ("LE_LIVE_PUBLISH", "0"), ("LE_EXEC_AUDIT", "0")):
        os.environ[k] = v
    import uvicorn
    import server
    from engine import board_api, live_board
    board_api.board_view = lambda bot, now=None: masked(live_board.from_heartbeat(hb, now=int(time.time()), where="pc", n_trades=60))
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(200):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    return f"http://127.0.0.1:{port}"


def serve_site(site, hb) -> tuple:
    from engine import live_board
    tmp = tempfile.mkdtemp(prefix="le_board_site_")
    dst = os.path.join(tmp, "site")
    shutil.copytree(site, dst)
    for src in ("board.js", "boardcore.js", "index.html", "sw.js"):
        shutil.copy(os.path.join(ROOT, "tools", "web_public", src), os.path.join(dst, src))
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


def pc_shots(base, out, errors, n):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = _launch(p)
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(f"pc console: {m.text}") if m.type == "error" and _real(m.text) else None)
        pg.on("pageerror", lambda e: errors.append(f"pc pageerror: {e}") if _real(str(e)) else None)
        pg.add_init_script("localStorage.setItem('page', 'cc'); localStorage.setItem('nx.fx', 'off');")
        pg.goto(base + "/?fxfixed", wait_until="domcontentloaded")
        try:
            pg.wait_for_selector("#page-cc.active #ccBoard .bd-homecut", timeout=60000)
        except Exception as e:
            errors.append(f"pc: Command center Right now row not drawn ({e.__class__.__name__})")
        pg.wait_for_timeout(800)
        pg.evaluate("() => document.getElementById('ccBoard')?.scrollIntoView({block: 'start'})")
        pg.wait_for_timeout(500)
        shot(pg, out, n, "pc_home_right_now")
        pg.evaluate("() => window.LE.go('board')")
        try:
            pg.wait_for_selector("#page-board.active .bd-wrap .bd-ladder", timeout=60000)
        except Exception as e:
            errors.append(f"pc: Live board not drawn ({e.__class__.__name__})")
        pg.wait_for_timeout(1200)
        pg.evaluate("() => window.scrollTo(0, 0)")
        shot(pg, out, n, "pc_board_right_now")
        for sel, name in ((".bd-health", "pc_board_health_map"), (".bd-prog", "pc_board_week_eval"), (".bd-trades", "pc_board_trade_log")):
            pg.evaluate(f"() => document.querySelector('#page-board {sel}')?.closest('.bd-card, .bd-health')?.scrollIntoView({{block: 'start'}})")
            pg.wait_for_timeout(500)
            shot(pg, out, n, name)
        pg.evaluate("() => document.querySelector('#page-board .bd-hp.bad, #page-board .bd-hp.warn')?.click()")
        pg.evaluate("() => document.querySelector('#page-board .bd-health')?.scrollIntoView({block: 'start'})")
        pg.wait_for_timeout(400)
        shot(pg, out, n, "pc_board_health_detail")
        pg.evaluate("() => window.scrollTo(0, 0)")
        pg.screenshot(path=os.path.join(out, f"{len(n) + 1:02d}_pc_board_full.png"), full_page=True)
        n.append("pc_board_full")
        pg.evaluate("() => document.getElementById('ccTheme')?.click()")
        pg.wait_for_timeout(1500)
        pg.evaluate("() => window.scrollTo(0, 0)")
        shot(pg, out, n, "pc_board_light")
        pg.evaluate("() => document.getElementById('ccTheme')?.click()")
        br.close()


def phone_shots(base, out, errors, n):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = _launch(p)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(f"phone console: {m.text}") if m.type == "error" and _real(m.text) else None)
        pg.on("pageerror", lambda e: errors.append(f"phone pageerror: {e}") if _real(str(e)) else None)
        pg.goto(base + "/index.html?fxfixed#/today", wait_until="domcontentloaded")
        try:
            pg.wait_for_selector(".bd-homecut", timeout=60000)
        except Exception as e:
            errors.append(f"phone: Home Right now cut not drawn ({e.__class__.__name__})")
        pg.wait_for_timeout(1500)
        pg.evaluate("() => document.querySelector('.bd-homecut')?.scrollIntoView({block: 'start'})")
        pg.wait_for_timeout(400)
        shot(pg, out, n, "phone_home_right_now")
        pg.evaluate("() => { location.hash = '#/board'; }")
        try:
            pg.wait_for_selector("#bdRoot .bd-ladder", timeout=60000)
        except Exception as e:
            errors.append(f"phone: #/board not drawn ({e.__class__.__name__})")
        pg.wait_for_timeout(1200)
        shot(pg, out, n, "phone_board_top")
        for sel, name in ((".bd-band", "phone_board_map"), (".bd-prog", "phone_board_week_eval"), (".bd-trades", "phone_board_trade_log")):
            pg.evaluate(f"() => document.querySelector('{sel}')?.scrollIntoView({{block: 'start'}})")
            pg.wait_for_timeout(500)
            shot(pg, out, n, name)
        wide = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        if wide > 1:
            errors.append(f"phone: the page scrolls sideways by {wide}px")
        pg.evaluate("() => window.scrollTo(0, 0)")
        pg.screenshot(path=os.path.join(out, f"{len(n) + 1:02d}_phone_board_full.png"), full_page=True)
        n.append("phone_board_full")
        br.close()


def shot(pg, out, n, name):
    n.append(name)
    pg.screenshot(path=os.path.join(out, f"{len(n):02d}_{name}.png"))
    print("shot", name, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="a built site folder (tools/build_web_dashboard.py --out ...) for the phone shots")
    ap.add_argument("--hb", help="a heartbeat.json (default: origin/heartbeat)")
    ap.add_argument("--out", default=os.path.join("research", "handoff", "2026-10-26", "ui_live"))
    ap.add_argument("--no-pc", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="move the heartbeat's check-in times to now (a live-looking PC)")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    hb = heartbeat(a.hb)
    if a.fresh:
        hb = shifted(hb, int(time.time()) - int(hb.get("t") or time.time()))
    errors, n = [], []
    snap = snapshot_files()
    try:
        if not a.no_pc:
            pc_shots(start_pc(hb), a.out, errors, n)
        if a.site:
            base, tmp = serve_site(a.site, hb)
            try:
                phone_shots(base, a.out, errors, n)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    finally:
        restore_files(snap)
    for e in errors:
        print("ERROR", e)
    print(f"{'OK' if not errors else 'FAIL'}: {len(n)} screenshots in {a.out}, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
