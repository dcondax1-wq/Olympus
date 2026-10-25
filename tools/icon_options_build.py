"""Render the Home Screen icon options (tools/web_public/icon_options/<a..m>/icon.svg) to PNGs + two preview sheets.

    python tools/icon_options_build.py            # all PNGs + research/handoff/2026-10-25/icon_options.png (A-C)
                                                  #   and icon_options_more.png (D-M)
    python tools/icon_options_build.py d e        # rebuild only some options (both sheets are redrawn)
    python tools/icon_options_build.py --sheet-only

Each option folder gets: icon-1024.png, icon-512.png, icon-192.png, apple-touch-icon.png (180), icon-152.png,
icon-120.png, icon-maskable-512.png (art scaled 0.8 into the safe circle) and info.json (name + one line).
All PNGs are RGB (no alpha), full-bleed squares; iOS rounds the corners itself.
Rendering: Playwright + the Chromium in /opt/pw-browsers (SVG filters/gradients render exactly as in Safari/Chrome).
Nothing live is touched; tools/icon_apply.py <a..m> switches the live icon.
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
SHEET_MORE = os.path.join(ROOT, "research", "handoff", "2026-10-25", "icon_options_more.png")
LIVE = os.path.join(ROOT, "web", "icons", "icon-512.png")

OPTIONS = {
    "a": ("Reclaim", "A faceted teal glass candle whose spear-tipped wick sweeps below a gold liquidity line and closes back above it."),
    "b": ("Apex", "A crest monogram: a bold A with one teal leg (LIT) and one indigo leg (ATLAS), the gold liquidity line as its crossbar."),
    "c": ("Atlas", "A glowing indigo globe with bold meridians, circled by one tilted teal-to-gold orbit with a bright node on it."),
    "d": ("Blade", "The sweep wick as a neon teal glass blade with a gold guard, its point cutting down through a gold liquidity line."),
    "e": ("Bull Crest", "A low-poly indigo bull head with polished gold horns and a glowing teal candle as its blaze."),
    "f": ("Hex L", "A bevelled indigo-metal hexagon crest holding a neon teal L (for LIT) and a gold target dot."),
    "g": ("Market Eye", "A gold-to-teal rimmed eye whose glowing iris has a candle-shaped pupil: the bot watching the market."),
    "h": ("Strike", "An indigo glass candle whose lower wick is a gold lightning bolt striking through a teal liquidity line."),
    "i": ("Vault", "A steel vault door with twelve gold bolts; the keyhole is filled with glowing teal liquidity."),
    "j": ("Compass", "An eight-point atlas star in faceted gold and indigo over a teal ring, with a teal gem at its heart."),
    "k": ("Orbit", "A tall teal glass candle circled by a tilted gold neon ring that passes behind and in front of it."),
    "l": ("Wave", "One thick indigo-to-teal neon ribbon that rolls over a crest, dives below a gold level and surges back up through a bright reclaim point."),
    "m": ("Facet", "A brilliant-cut gem in teal and indigo facets with gold edges and one white sparkle."),
}
FIRST, MORE = list("abc"), list("defghijklm")
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


def build_assets(page, keys):
    for key in keys:
        name, line = OPTIONS[key]
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


def build_sheet(page, keys, out, cols, every):
    """keys: options on the sheet; cols: big icons per row; every: a placeholder app after every N options on the phone."""
    big = "".join(
        f'<div class="big"><img src="{data_url(os.path.join(OPT, k, "icon-1024.png"))}"><h2>{k.upper()} &middot; {OPTIONS[k][0]}</h2>'
        f'<p>{OPTIONS[k][1]}</p></div>' for k in keys)
    # a dark iPhone Home Screen: 60 pt icons (shown at 2x here = 120 px PNGs), iOS corner radius ~22.4%
    filler = iter([("Phone", "#2fbf5b"), ("Mail", "#2f7bf6"), ("Maps", "#4b9e6a"), ("Clock", "#1c1c1e"), ("Notes", "#f6c544"),
                   ("Photos", "#e8e8ea"), ("Wallet", "#111"), ("Settings", "#8e8e93"), ("Music", "#fa3c55"),
                   ("Weather", "#3a8ee6"), ("Camera", "#444"), ("Health", "#f4f4f6")])
    apps = [(OPTIONS[k][0], data_url(os.path.join(OPT, k, "icon-120.png"))) for k in keys]
    if os.path.exists(LIVE):
        apps.append(("Live now", data_url(LIVE)))
    order = []
    for i, a in enumerate(apps):
        order.append(a)
        if (i + 1) % every == 0:
            order.append(None)
    while len(order) % 4:
        order.append(None)
    cells = []
    for o in order:
        if o is None:
            lab, col = next(filler, ("App", "#333"))
            cells.append(f'<div class="app"><div class="ic" style="background:{col}"></div><span>{lab}</span></div>')
        else:
            cells.append(f'<div class="app"><img class="ic" src="{o[1]}"><span>{o[0]}</span></div>')
    small_rows = "".join(
        f'<div class="row"><b>{k.upper()} &middot; {OPTIONS[k][0]}</b>' +
        "".join(f'<img src="{data_url(os.path.join(OPT, k, "icon-120.png"))}" style="width:{s}px;height:{s}px;'
                f'border-radius:{s*0.2237:.1f}px">' for s in (60, 40, 29)) + "</div>"
        for k in keys)
    rcols = 1 if len(keys) <= 4 else 2
    letters = "|".join(keys)
    html = f"""<html><head><style>
    body{{margin:0;background:#07080c;color:#eef1f8;font-family:Inter,system-ui,sans-serif;width:1800px}}
    h1{{font-size:40px;margin:48px 56px 8px}} .sub{{color:#a9b1c3;margin:0 56px 32px;font-size:20px}}
    .bigs{{display:grid;grid-template-columns:repeat({cols},1fr);gap:40px;padding:0 56px}}
    .big img{{width:100%;border-radius:22.37%;display:block;box-shadow:0 20px 60px rgba(0,0,0,.6)}}
    .big h2{{font-size:{30 if cols <= 3 else 24}px;margin:18px 0 6px}} .big p{{color:#a9b1c3;font-size:{19 if cols <= 3 else 16}px;line-height:1.4;margin:0}}
    .low{{display:flex;gap:56px;padding:56px;align-items:flex-start}}
    .phone{{flex:none;width:393px;border-radius:56px;padding:70px 22px 60px;box-sizing:border-box;border:10px solid #22252e;
      background:radial-gradient(120% 80% at 30% 10%,#1d2347 0%,#0b0d1a 55%,#030306 100%)}}
    .grid{{display:grid;grid-template-columns:repeat(4,1fr);row-gap:26px}}
    .app{{display:flex;flex-direction:column;align-items:center;gap:6px}}
    .ic{{width:60px;height:60px;border-radius:13.4px;display:block}} .app span{{font-size:11.5px;color:#fff}}
    .side h3{{font-size:24px;margin:0 0 18px}} .rows{{display:grid;grid-template-columns:repeat({rcols},auto);column-gap:60px}}
    .row{{display:flex;align-items:center;gap:26px;margin-bottom:26px}}
    .row b{{width:200px;font-size:20px}} .note{{color:#6f788b;font-size:17px;max-width:900px;line-height:1.5}}
    </style></head><body>
    <h1>Home Screen icon options {keys[0].upper()}-{keys[-1].upper()} &middot; pick one</h1>
    <p class="sub">2026-10-25 &middot; Obsidian palette (teal #3ee0c8, indigo #6d7cff, gold #f2c35b on near-black) &middot; apply with: python tools/icon_apply.py {letters}</p>
    <div class="bigs">{big}</div>
    <div class="low">
      <div class="phone"><div class="grid">{''.join(cells)}</div></div>
      <div class="side"><h3>Actual size (60 / 40 / 29 pt)</h3><div class="rows">{small_rows}</div>
        <p class="note">Left: a dark iPhone Home Screen at true 60 pt size, with the current live icon ("Live now", Chrome Drop)
        for comparison. All files are opaque full-bleed squares; iOS rounds the corners.</p></div>
    </div></body></html>"""
    page.set_viewport_size({"width": 1800, "height": 1000})
    page.set_content(html)
    page.wait_for_timeout(300)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    page.screenshot(path=out, full_page=True)
    print("sheet", out)


def main():
    pw, browser = chromium()
    try:
        page = browser.new_page()
        keys = [k for k in sys.argv[1:] if k in OPTIONS] or list(OPTIONS)
        if "--sheet-only" not in sys.argv:
            build_assets(page, keys)
        build_sheet(page, FIRST, SHEET, 3, 2)
        build_sheet(page, MORE, SHEET_MORE, 5, 3)
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    main()
