"""Before / after screenshots of the main PC dashboard pages at 1440x900 (the 2026-10-25 "clean up" pass) and the
before/after contact sheet. Needs Playwright + Chromium and a running dashboard server (server.py). Read-only: it only
opens pages, nothing is clicked that talks to the bot.

    python -X utf8 -m tests.shots_ui_clean --pc http://127.0.0.1:8766 --out research/handoff/2026-10-25/ui_clean/after
    python -X utf8 -m tests.shots_ui_clean --sheet research/handoff/2026-10-25/ui_clean

Exit code 1 when a page logs a console error.
"""
from __future__ import annotations

import argparse
import os
import sys

from tests.shots_brain import _launch, _real

PAGES = [("cc", "Command center"), ("command", "Today"), ("brain", "Bot Brain"), ("atlas", "ATLAS"), ("botctl", "Bot Control"),
         ("accounts", "Accounts"), ("trades", "Trades"), ("results", "Results"), ("modules", "Modules / Tools"), ("settings", "Settings")]


def shots(base, out, errors):
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        br = _launch(p)
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, service_workers="block")
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and _real(m.text) else None)
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}") if _real(str(e)) else None)
        pg.add_init_script("if (!sessionStorage.getItem('shot')) { localStorage.clear(); localStorage.setItem('page', 'cc'); sessionStorage.setItem('shot', '1'); }")
        pg.goto(base + "/?fxfixed", wait_until="domcontentloaded")
        pg.wait_for_timeout(2500)
        for i, (page, _) in enumerate(PAGES, 1):
            pg.evaluate(f"() => window.LE.go('{page}')")
            pg.wait_for_timeout(3500 if page in ("cc", "command", "results") else 2200)
            pg.screenshot(path=os.path.join(out, f"{i:02d}_{page}.png"))
            print("shot", page, flush=True)
        # extras: the Home lower half, the top bar's "..." menu, the Advanced group open
        pg.evaluate("() => window.LE.go('cc')")
        pg.wait_for_timeout(2500)
        pg.evaluate("() => { const p = document.getElementById('page-cc'); p.scrollTo(0, p.scrollHeight); }")
        pg.wait_for_timeout(600)
        pg.screenshot(path=os.path.join(out, "x1_cc_lower.png"))
        if pg.query_selector("#nxTopMore .nx-more-b"):
            pg.click("#nxTopMore .nx-more-b")
            pg.wait_for_timeout(400)
            pg.screenshot(path=os.path.join(out, "x2_top_menu.png"))
            pg.keyboard.press("Escape")
        if pg.query_selector(".nx-adv-h"):
            pg.click(".nx-adv-h")
            pg.wait_for_timeout(400)
            pg.screenshot(path=os.path.join(out, "x3_advanced_open.png"))
            pg.click(".nx-adv-h")
        br.close()


def sheet(root):
    from PIL import Image, ImageDraw, ImageFont
    b, a = os.path.join(root, "before"), os.path.join(root, "after")
    rows = [(f"{i:02d}_{p}.png", t) for i, (p, t) in enumerate(PAGES, 1) if os.path.exists(os.path.join(b, f"{i:02d}_{p}.png"))
            and os.path.exists(os.path.join(a, f"{i:02d}_{p}.png"))]
    W, H, pad, lab = 720, 450, 16, 34
    img = Image.new("RGB", (pad * 3 + W * 2, 70 + len(rows) * (H + lab + pad)), (14, 16, 22))
    d = ImageDraw.Draw(img)
    try:
        f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    d.text((pad, 20), "PC dashboard 2026-10-25: before (left) / after (right), 1440x900", fill=(235, 238, 245), font=f1)
    y = 70
    for fn, title in rows:
        d.text((pad, y + 6), f"{title}: before", fill=(170, 176, 190), font=f2)
        d.text((pad * 2 + W, y + 6), f"{title}: after", fill=(120, 220, 160), font=f2)
        for k, folder in enumerate((b, a)):
            im = Image.open(os.path.join(folder, fn)).convert("RGB").resize((W, H), Image.LANCZOS)
            img.paste(im, (pad + k * (W + pad), y + lab))
        y += H + lab + pad
    out = os.path.join(root, "pc_before_after.png")
    img.quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(out, optimize=True)   # palette PNG: a fraction of the size
    print("sheet", out, len(rows), "rows")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", default="http://127.0.0.1:8766")
    ap.add_argument("--out", default=os.path.join("research", "handoff", "2026-10-25", "ui_clean", "after"))
    ap.add_argument("--sheet", default=None, help="build <dir>/pc_before_after.png from <dir>/before and <dir>/after")
    a = ap.parse_args(argv)
    if a.sheet:
        sheet(a.sheet)
        return 0
    errors: list = []
    shots(a.pc.rstrip("/"), a.out, errors)
    for e in errors:
        print("ERROR", e)
    print(f"{'OK' if not errors else 'FAIL'}: {len(PAGES)} screenshots in {a.out}, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
