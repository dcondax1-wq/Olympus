"""Screenshots of the Bot Brain (PC dashboard tabs at 1440 and 390 px wide, the phone app's Brain page at 390 px) with a
console-error check. Needs Playwright + Chromium and a running dashboard server.

    python -X utf8 -m tests.shots_brain --pc http://127.0.0.1:8766 --out <dir>
    python -X utf8 -m tests.shots_brain --phone <dir with index.html + data.json> --out <dir>

Exit code 1 when a page logs a console error or fails to draw the Brain.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import sys
import threading

def _launch(p):
    """Chromium for Playwright; falls back to any chromium under PLAYWRIGHT_BROWSERS_PATH when the bundled build is missing."""
    try:
        return p.chromium.launch()
    except Exception:
        import glob
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        for exe in sorted(glob.glob(os.path.join(root, "chromium-*", "chrome-linux", "chrome")), reverse=True):
            return p.chromium.launch(executable_path=exe)
        raise


# errors of this sandbox, not of the page: external CDNs (Chart.js, fonts) are unreachable, so the Today page's charts fail
ENV_ERR = ("ERR_TUNNEL_CONNECTION_FAILED", "ERR_NAME_NOT_RESOLVED", "ERR_INTERNET_DISCONNECTED", "Chart is not defined",
           "Failed to load resource")


def _real(text):
    return not any(k in text for k in ENV_ERR)


TABS = ["now", "levels", "setups", "sizing", "trade", "guards", "log", "replay"]


def pc_shots(base, out, errors):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = _launch(p)
        for w, h in ((1440, 1000), (390, 844)):
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg = ctx.new_page()
            pg.on("console", lambda m, w=w: errors.append(f"pc {w}: {m.text}") if m.type == "error" and _real(m.text) else None)
            pg.on("pageerror", lambda e, w=w: errors.append(f"pc {w} pageerror: {e}") if _real(str(e)) else None)
            pg.add_init_script("localStorage.setItem('page', 'brain'); localStorage.setItem('nx.page', 'brain');")
            pg.goto(base + "/?fxfixed", wait_until="domcontentloaded")
            pg.wait_for_timeout(1500)
            pg.evaluate("() => { const a = document.querySelector('[data-page=\"brain\"], [data-goto=\"brain\"]'); if (a) a.click(); }")
            pg.wait_for_selector("#page-brain.active .bb-tabs", timeout=20000)
            # the live Brain arrives with the first /api/next/brain answer (the server may still be busy with its boot)
            pg.wait_for_function("() => document.querySelector('#page-brain .bb-wait, #page-brain .nx-empty-hub h3') && "
                                 "!/Loading/.test(document.querySelector('#page-brain .nx-empty-hub h3')?.textContent || '')", timeout=90000)
            for tab in TABS:
                pg.evaluate(f"() => document.querySelector('#bbTab button[data-v=\"{tab}\"]').click()")
                if tab == "replay":
                    pg.wait_for_selector("#bbRange", timeout=60000)
                    pg.wait_for_selector("#bbRView", timeout=60000)
                else:
                    pg.wait_for_timeout(400)
                pg.wait_for_timeout(600)
                ok = pg.evaluate("() => !!document.querySelector('#page-brain .bb-tabs') && !/Could not draw/.test(document.querySelector('#page-brain').innerText)")
                if not ok:
                    errors.append(f"pc {w}: tab {tab} did not draw")
                path = os.path.join(out, f"pc_brain_{tab}_{w}.png")
                pg.screenshot(path=path, full_page=(w == 390 or tab in ("setups", "levels")))
                print("shot", path)
            if w == 1440:                    # the scrubber: one step back, then a log line jump
                pg.evaluate("() => document.querySelector('#bbPrev').click()")
                pg.wait_for_timeout(1500)
                pg.screenshot(path=os.path.join(out, "pc_brain_replay_scrub_1440.png"))
            ctx.close()
        br.close()


def phone_shots(root, out, errors):
    from playwright.sync_api import sync_playwright
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as p:
            br = _launch(p)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
            pg = ctx.new_page()
            pg.route("**/api.github.com/**", lambda r: r.abort())
            pg.route("**/raw.githubusercontent.com/**", lambda r: r.abort())
            pg.on("console", lambda m: errors.append(f"phone: {m.text}") if m.type == "error" and _real(m.text) else None)
            pg.on("pageerror", lambda e: errors.append(f"phone pageerror: {e}") if _real(str(e)) else None)
            for sub in ("now", "levels", "setups", "log"):
                pg.goto(f"{base}/index.html?fxfixed#/brain", wait_until="domcontentloaded")
                pg.wait_for_selector(".bz-tabs", timeout=30000)
                pg.evaluate(f"() => {{ const b = document.querySelector('#brTab button[data-v=\"{sub}\"]'); if (b) b.click(); }}")
                pg.wait_for_timeout(700)
                path = os.path.join(out, f"phone_brain_{sub}_390.png")
                pg.screenshot(path=path, full_page=True)
                print("shot", path)
            pg.goto(f"{base}/index.html?fxfixed#/today", wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)
            pg.screenshot(path=os.path.join(out, "phone_home_390.png"))
            br.close()
    finally:
        srv.shutdown()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc")
    ap.add_argument("--phone")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    errors: list = []
    if a.pc:
        pc_shots(a.pc.rstrip("/"), a.out, errors)
    if a.phone:
        phone_shots(a.phone, a.out, errors)
    for e in errors:
        print("ERROR", e)
    print("console errors:", len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
