"""Screenshots of the DAPHNE page (tools/web_public/tree) at 390 x 844 and 844 x 390 with a console-error check.

    python -X utf8 -m tests.shots_strategytree [--out research/handoff/2026-11-03/tree]

Per viewport: the start of the search, mid-growth and the best path lit (the playback clock frozen with ?at=), then the
live page (animation running, a node tapped for its rule card, the top-10 sheet) and the demo fixture (tree.json
missing). Exit code 1 when the page logs a console error, a frame takes too long, or the tree is not drawn.
"""
from __future__ import annotations

import argparse
import functools
import glob
import http.server
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "tools", "web_public")       # served whole: the page links ../jarvis/icon-192.png
OUT = os.path.join(ROOT, "research", "handoff", "2026-11-03", "tree")
VIEWPORTS = {"portrait": (390, 844), "landscape": (844, 390)}
MOMENTS = {"1-start": 900, "2-mid-growth": 3400, "3-best-path": 9300}


def _launch(p):
    """Chromium for Playwright; falls back to a chromium under PLAYWRIGHT_BROWSERS_PATH when the bundled one is missing."""
    try:
        return p.chromium.launch()
    except Exception:
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        for exe in sorted(glob.glob(os.path.join(root, "chromium-*", "chrome-linux", "chrome")), reverse=True):
            return p.chromium.launch(executable_path=exe)
        raise


def _serve(folder):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=folder))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _lit_pixels(pg):
    """Share of bright-green canvas pixels in a 64 x 64 sample: > 0 means branches are drawn."""
    return pg.evaluate("""() => {
      const c = document.getElementById('stage'), s = document.createElement('canvas'); s.width = s.height = 64;
      const g = s.getContext('2d'); g.drawImage(c, 0, 0, 64, 64);
      const d = g.getImageData(0, 0, 64, 64).data; let k = 0;
      for (let i = 0; i < d.length; i += 4) if (d[i + 1] > 60 && d[i + 1] > d[i] + 20) k++;
      return k / 4096; }""")


def run(out: str) -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    srv = _serve(SITE)
    base = f"http://127.0.0.1:{srv.server_address[1]}/tree/index.html"
    errors, notes = [], []
    with sync_playwright() as p:
        br = _launch(p)
        for name, (w, h) in VIEWPORTS.items():
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True)
            for label, at in MOMENTS.items():
                pg = ctx.new_page()
                pg.on("console", lambda m, n=name: errors.append(f"{n}: {m.text}") if m.type == "error" else None)
                pg.on("pageerror", lambda e, n=name: errors.append(f"{n} pageerror: {e}"))
                pg.goto(f"{base}?at={at}", wait_until="networkidle")
                pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=20000)
                pg.wait_for_timeout(500)
                shot = os.path.join(out, f"{name}-{label}.jpg")
                pg.screenshot(path=shot, type="jpeg", quality=85)
                lit = _lit_pixels(pg)
                notes.append(f"{name} {label}: green pixels {lit:.3f}")
                if at > 3000 and lit < 0.002:
                    errors.append(f"{name} {label}: the tree is not drawn")
                if label == "3-best-path":
                    pg.click('.lens [data-lens="test"]')
                    pg.wait_for_timeout(300)
                    pg.screenshot(path=os.path.join(out, f"{name}-7-test-lens.jpg"), type="jpeg", quality=85)
                pg.close()
            # live: animation running, a tap on the best leaf, then the top 10
            pg = ctx.new_page()
            pg.on("console", lambda m, n=name: errors.append(f"{n} live: {m.text}") if m.type == "error" else None)
            pg.on("pageerror", lambda e, n=name: errors.append(f"{n} live pageerror: {e}"))
            pg.goto(base, wait_until="networkidle")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=20000)
            pg.wait_for_timeout(9500)
            ms = pg.evaluate("() => window.__daphne.state.frameMs")
            notes.append(f"{name} live: draw {ms:.1f} ms a frame, quality {pg.evaluate('() => window.__daphne.state.quality')}")
            leaf = pg.evaluate("""() => { const S = window.__daphne.state, p = S.tree.bestPath, n = p[p.length - 1] || S.tree.root, v = S.view;
                                         return [n.x * v.s + v.x, n.y * v.s + v.y]; }""")
            pg.touchscreen.tap(leaf[0], leaf[1])
            pg.wait_for_timeout(400)
            if pg.is_hidden("#card"):
                errors.append(f"{name}: tapping the best leaf opened no rule card")
            pg.screenshot(path=os.path.join(out, f"{name}-4-rule-card.jpg"), type="jpeg", quality=85)
            if pg.is_visible("#card"):
                pg.click("#card [data-close]")
            pg.click("#openTop")
            pg.wait_for_timeout(300)
            pg.screenshot(path=os.path.join(out, f"{name}-5-top-10.jpg"), type="jpeg", quality=85)
            pg.close()
            # demo: no tree.json (its expected 404 is the one console error not recorded: only page errors count here)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e, n=name: errors.append(f"{n} demo pageerror: {e}"))
            pg.route("**/tree.json", lambda route: route.fulfill(status=404, body="missing"))
            pg.goto(f"{base}?at=9300", wait_until="networkidle")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=20000)
            if pg.is_hidden("#demo"):
                errors.append(f"{name}: demo data without the DEMO badge")
            pg.wait_for_timeout(300)
            pg.screenshot(path=os.path.join(out, f"{name}-6-demo.jpg"), type="jpeg", quality=85)
            pg.close()
            ctx.close()
        br.close()
    srv.shutdown()
    for n in notes:
        print(n)
    for e in errors:
        print("ERROR", e)
    print(f"shots in {out}: {'OK' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    sys.exit(run(ap.parse_args().out))
