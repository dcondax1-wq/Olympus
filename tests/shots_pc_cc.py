"""Screenshots of the PC Command center upgrade at 1440x900 (every new page, dark + the home in light, the command palette
and the shortcut list) with a console-error check. Needs Playwright + Chromium and a running dashboard server.

    python -X utf8 -m tests.shots_pc_cc --pc http://127.0.0.1:8766 --out research/handoff/2026-10-25/ui_pc

Exit code 1 when a page logs a console error or does not draw.
"""
from __future__ import annotations

import argparse
import os
import sys

from tests.shots_brain import _launch, _real

PAGES = [("cc", ".cc-two"), ("goals", ".cc-ring"), ("evaltl", ".cc-tl"), ("sesscal", ".op-tab"), ("tradelog", "#tlT"),
         ("atlassetups", "#asT table"), ("runbook", ".cc-emerg"), ("audit", "#auM table"), ("features", ".cc-feat")]


def shots(base, out, errors):
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        br = _launch(p)
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and _real(m.text) else None)
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}") if _real(str(e)) else None)
        pg.add_init_script("localStorage.setItem('page', 'cc'); localStorage.setItem('nx.fx', 'off');")
        pg.goto(base + "/?fxfixed", wait_until="domcontentloaded")
        pg.wait_for_timeout(1500)
        for i, (page, sel) in enumerate(PAGES, 1):
            pg.evaluate(f"() => window.LE.go('{page}')")
            try:
                pg.wait_for_selector(f"#page-{page}.active {sel}", timeout=60000)
            except Exception as e:
                errors.append(f"{page}: {sel} not drawn ({e.__class__.__name__})")
            pg.wait_for_timeout(700)
            pg.screenshot(path=os.path.join(out, f"{i:02d}_{page}.png"))
            print("shot", page, flush=True)
        # the home, full page, then in light
        pg.evaluate("() => window.LE.go('cc')")
        pg.wait_for_selector("#page-cc.active .cc-two", timeout=60000)
        pg.wait_for_timeout(600)
        pg.evaluate("() => { const p = document.getElementById('page-cc'); p.scrollTo(0, p.scrollHeight); window.scrollTo(0, document.body.scrollHeight); }")
        pg.wait_for_timeout(600)
        pg.screenshot(path=os.path.join(out, "10_cc_lower.png"))
        pg.evaluate("() => { document.getElementById('page-cc').scrollTo(0, 0); window.scrollTo(0, 0); }")
        pg.evaluate("() => document.getElementById('ccTheme').click()")
        pg.wait_for_timeout(2500)
        pg.screenshot(path=os.path.join(out, "11_cc_light.png"))
        pg.evaluate("() => document.getElementById('ccTheme').click()")
        pg.wait_for_timeout(400)
        pg.keyboard.press("Control+k")
        pg.wait_for_timeout(500)
        pg.keyboard.type("runbook")
        pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(out, "12_palette.png"))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        pg.mouse.click(720, 300)
        pg.keyboard.press("?")
        pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(out, "13_shortcuts.png"))
        br.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", default="http://127.0.0.1:8766")
    ap.add_argument("--out", default=os.path.join("research", "handoff", "2026-10-25", "ui_pc"))
    a = ap.parse_args(argv)
    errors: list = []
    shots(a.pc.rstrip("/"), a.out, errors)
    for e in errors:
        print("ERROR", e)
    print(f"{'OK' if not errors else 'FAIL'}: {len(PAGES) + 4} screenshots in {a.out}, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
