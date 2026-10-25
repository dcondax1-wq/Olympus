"""Render the three Home Screen icon options (tools/web_public/icon_options/{a,b,c}/icon.svg) to PNGs + a preview sheet.

    python tools/icon_options_build.py            # all PNGs + research/handoff/2026-10-25/icon_options.png

Each option folder gets: icon-1024.png, icon-512.png, icon-192.png, apple-touch-icon.png (180), icon-152.png,
icon-120.png, icon-maskable-512.png (art scaled 0.8 into the safe circle) and info.json (name + one line).
All PNGs are RGB (no alpha), full-bleed squares; iOS rounds the corners itself.
Rendering: Playwright + the Chromium in /opt/pw-browsers (SVG filters/gradients render exactly as in Safari/Chrome).
Nothing live is touched; tools/icon_apply.py <a|b|c> switches the live icon.
"""
import base64
import glob
import io
import json
import os
import sys

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPT = os.path.join(ROOT, "tools", "web_public", "icon_options")
SHEET = os.path.join(ROOT, "research", "handoff", "2026-10-25", "icon_options.png")
LIVE = os.path.join(ROOT, "web", "icons", "icon-512.png")

OPTIONS = {
    "a": ("Reclaim", "A faceted teal glass candle whose spear-tipped wick sweeps below a gold liquidity line and closes back above it."),
    "b": ("Apex", "A crest monogram: a bold A with one teal leg (LIT) and one indigo leg (ATLAS), the gold liquidity line as its crossbar."),
    "c": ("Atlas", "A glowing indigo globe with bold meridians, circled by one tilted teal-to-gold orbit with a bright node on it."),
}
SIZES = {"icon-512.png": 512, "icon-192.png": 192, "apple-touch-icon.png": 180, "icon-152.png": 152, "icon-120.png": 120}


def chromium():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw, pw.chromium.launch(**({"executable_path": exe} if exe else {}))


def render_svg(page, svg, size=1024):
    b64 = base64.b64encode(svg.encode()).decode()
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(f'<html><body style="margin:0;background:#000"><img id="i" src="data:image/svg+xml;base64,{b64}" '
                     f'style="width:{size}px;height:{size}px;display:block"></body></html>')
    page.wait_for_function("document.getElementById('i').complete")
    page.wait_for_timeout(150)
    return Image.open(io.BytesIO(page.screenshot())).convert("RGB")


def maskable(svg):
    # Android maskable: background stays full bleed, the art sits inside the central 80% safe circle
    return svg.replace('<g id="art">', '<g id="art" transform="translate(102.4 102.4) scale(0.8)">', 1)


def small(img, n):
    out = img.resize((n, n), Image.LANCZOS)
    if n <= 192:
        out = out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=45, threshold=1))
    return out


def build_assets(page):
    for key, (name, line) in OPTIONS.items():
        d = os.path.join(OPT, key)
        svg = open(os.path.join(d, "icon.svg"), encoding="utf-8").read()
        master = render_svg(page, svg)
        master.save(os.path.join(d, "icon-1024.png"), optimize=True)
        for fn, n in SIZES.items():
            small(master, n).save(os.path.join(d, fn), optimize=True)
        small(render_svg(page, maskable(svg)), 512).save(os.path.join(d, "icon-maskable-512.png"), optimize=True)
        with open(os.path.join(d, "info.json"), "w", encoding="utf-8") as fh:
            json.dump({"key": key, "name": name, "line": line}, fh, indent=1)
        print("built", key, name)


def data_url(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()


def build_sheet(page):
    big = "".join(
        f'<div class="big"><img src="{data_url(os.path.join(OPT, k, "icon-1024.png"))}"><h2>{k.upper()} &middot; {n}</h2>'
        f'<p>{l}</p></div>' for k, (n, l) in OPTIONS.items())
    # a dark iPhone Home Screen: 60 pt icons (shown at 2x here = 120 px PNGs), iOS corner radius ~22.4%
    filler = [("Phone", "#2fbf5b"), ("Mail", "#2f7bf6"), ("Maps", "#4b9e6a"), ("Clock", "#1c1c1e"), ("Notes", "#f6c544"),
              ("Photos", "#e8e8ea"), ("Wallet", "#111"), ("Settings", "#8e8e93"), ("Music", "#fa3c55")]
    apps = [(f"{OPTIONS[k][0]}", data_url(os.path.join(OPT, k, "icon-120.png"))) for k in OPTIONS]
    live = ("Live now", data_url(LIVE)) if os.path.exists(LIVE) else None
    cells, f = [], iter(filler)
    order = [apps[0], None, apps[1], None, None, apps[2], None, live, None, None, None, None]
    for o in order:
        if o is None:
            lab, col = next(f, ("App", "#333"))
            cells.append(f'<div class="app"><div class="ic" style="background:{col}"></div><span>{lab}</span></div>')
        else:
            cells.append(f'<div class="app"><img class="ic" src="{o[1]}"><span>{o[0]}</span></div>')
    small_rows = "".join(
        f'<div class="row"><b>{k.upper()} &middot; {n}</b>' +
        "".join(f'<img src="{data_url(os.path.join(OPT, k, "icon-120.png"))}" style="width:{s}px;height:{s}px;'
                f'border-radius:{s*0.2237:.1f}px">' for s in (60, 40, 29)) + "</div>"
        for k, (n, _) in OPTIONS.items())
    html = f"""<html><head><style>
    body{{margin:0;background:#07080c;color:#eef1f8;font-family:Inter,system-ui,sans-serif;width:1800px}}
    h1{{font-size:40px;margin:48px 56px 8px}} .sub{{color:#a9b1c3;margin:0 56px 32px;font-size:20px}}
    .bigs{{display:flex;gap:40px;padding:0 56px}} .big{{flex:1}}
    .big img{{width:100%;border-radius:22.37%;display:block;box-shadow:0 20px 60px rgba(0,0,0,.6)}}
    .big h2{{font-size:30px;margin:22px 0 6px}} .big p{{color:#a9b1c3;font-size:19px;line-height:1.4;margin:0}}
    .low{{display:flex;gap:56px;padding:56px;align-items:flex-start}}
    .phone{{width:393px;height:500px;border-radius:56px;padding:70px 22px 0;box-sizing:border-box;border:10px solid #22252e;
      background:radial-gradient(120% 80% at 30% 10%,#1d2347 0%,#0b0d1a 55%,#030306 100%)}}
    .grid{{display:grid;grid-template-columns:repeat(4,1fr);row-gap:26px}}
    .app{{display:flex;flex-direction:column;align-items:center;gap:6px}}
    .ic{{width:60px;height:60px;border-radius:13.4px;display:block}} .app span{{font-size:11.5px;color:#fff}}
    .side h3{{font-size:24px;margin:0 0 18px}} .row{{display:flex;align-items:center;gap:26px;margin-bottom:26px}}
    .row b{{width:180px;font-size:20px}} .note{{color:#6f788b;font-size:17px;max-width:900px;line-height:1.5}}
    </style></head><body>
    <h1>Home Screen icon options &middot; pick one</h1>
    <p class="sub">2026-10-25 &middot; Obsidian palette (teal #3ee0c8, indigo #6d7cff, gold #f2c35b on near-black) &middot; apply with: python tools/icon_apply.py a|b|c</p>
    <div class="bigs">{big}</div>
    <div class="low">
      <div class="phone"><div class="grid">{''.join(cells)}</div></div>
      <div class="side"><h3>Actual size (60 / 40 / 29 pt)</h3>{small_rows}
        <p class="note">Left: a dark iPhone Home Screen at true 60 pt size, with the current live icon ("Live now", Chrome Drop)
        for comparison. All files are opaque full-bleed squares; iOS rounds the corners.</p></div>
    </div></body></html>"""
    page.set_viewport_size({"width": 1800, "height": 1000})
    page.set_content(html)
    page.wait_for_timeout(300)
    os.makedirs(os.path.dirname(SHEET), exist_ok=True)
    page.screenshot(path=SHEET, full_page=True)
    print("sheet", SHEET)


def main():
    pw, browser = chromium()
    try:
        page = browser.new_page()
        if "--sheet-only" not in sys.argv:
            build_assets(page)
        build_sheet(page)
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    main()
