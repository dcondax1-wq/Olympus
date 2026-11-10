"""Home Screen polish of the new OLYMPUS apps (2026-11-10): every app folder below ships its own AGORA icon set and the same <head> as the finished apps.

  for each app folder that exists (the ones still to land are listed and skipped):
    - files: icon.svg, apple-touch-icon.png (180 x 180), icon-192.png, icon-512.png, icon-maskable-512.png (512 x 512), manifest.webmanifest, jarvis.json, index.html
    - the PNG sizes are real (read from the file header), opaque, full-bleed (a corner pixel is the marble colour), the maskable glyph sits inside the 80 % safe zone, no neon colours
    - every icon is different (hash of the SVG and of the 180 PNG): one simple Greek glyph each, not a letter on a square (the SVG has no <text>)
    - index.html: viewport-fit=cover, theme-color #14110e, apple-mobile-web-app-capable / mobile-web-app-capable / status-bar-style / title (<= 12), the apple-touch-icon is the app's own 180 PNG,
      the manifest link, and the OLYMPUS kit lines (olympus.css, agora.css, themes.js, olympus.js data-app, intro-app.js, a11y.js, sfx.js)
    - manifest: name, short_name (<= 12), id / start_url / scope './', standalone, portrait, colours #14110e, the svg + 192 any + 512 any + 512 maskable icons that exist with the sizes they claim
    - tools/make_app_icons.py --check is clean (nothing left to fill)
    python -X utf8 -m tests.test_new_app_icons
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import test_homescreen as HS  # noqa: E402

ROOT, WEB = HS.ROOT, HS.WEB
APPS = ("hestia demeter apollo hera dionysus clio delphi pnyx planner mint mercury chrysos sibyl oikos arbiter stoa aegis lyceum nike kronos moirai epilogue "
        "kairos kratos argo pythia mintcity gallery").split()
MUST = {"hestia", "demeter", "apollo", "hera", "dionysus", "clio", "delphi", "pnyx", "planner", "mint", "mercury", "chrysos", "sibyl", "oikos", "arbiter", "stoa", "aegis", "lyceum", "nike", "kronos", "moirai", "epilogue"}
PNGS = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512, "icon-maskable-512.png": 512}
NEON = re.compile(r"#(?:0ff|00f|f0f|0f0)\b|#00ffff|#ff00ff|#39ff14", re.I)
KIT = ("../olympus/olympus.css?v=o", "../olympus/agora.css", "../olympus/themes.js?v=o", "../olympus/intro-app.js", "../olympus/a11y.js", "../olympus/sfx.js")
check = HS.check


def pixel(path, xy):
    from PIL import Image
    with Image.open(path) as im:
        return im.convert("RGBA").getpixel(xy)


def bbox_off_bg(path):
    """bounding box of everything that is not the marble background colour, as fractions of the side"""
    from PIL import Image, ImageChops
    with Image.open(path) as im:
        im = im.convert("RGB")
        diff = ImageChops.difference(im, Image.new("RGB", im.size, (0x1d, 0x19, 0x14))).convert("L").point(lambda v: 255 if v > 12 else 0)
        b = diff.getbbox()
        return None if b is None else tuple(round(v / im.size[0], 3) for v in b)


def main():
    here = [a for a in APPS if os.path.isdir(os.path.join(WEB, a))]
    missing = [a for a in APPS if a not in here]
    for a in sorted(MUST - set(here)):
        check(f"{a}: the app folder exists", False, a)
    if missing:
        print(f"[skip] not in this tree yet: {', '.join(missing)} (checked once they land: python -X utf8 -m tests.test_new_app_icons)")
    svg_hash, png_hash, bad_files, bad_png, bad_look, bad_head, bad_kit, bad_man, bad_text = {}, {}, [], [], [], [], [], [], []
    for a in here:
        d = os.path.join(WEB, a)
        need = ["icon.svg", "manifest.webmanifest", "jarvis.json", "index.html", *PNGS]
        gone = [n for n in need if not os.path.isfile(os.path.join(d, n))]
        if gone:
            bad_files.append(f"{a}: {gone}")
            continue
        for fn, px in PNGS.items():
            if HS.png_size(os.path.join(d, fn)) != (px, px):
                bad_png.append(f"{a}/{fn} is {HS.png_size(os.path.join(d, fn))}, wants {px}x{px}")
        try:
            c = pixel(os.path.join(d, "apple-touch-icon.png"), (0, 0))
            if c[3] != 255 or abs(c[0] - 0x1d) > 3 or abs(c[1] - 0x19) > 3 or abs(c[2] - 0x14) > 3:
                bad_look.append(f"{a}: corner of the 180 PNG is {c}, not the marble colour (a rounded or transparent icon looks black on iOS)")
            b = bbox_off_bg(os.path.join(d, "icon-maskable-512.png"))
            if b is None or b[0] < 0.1 or b[1] < 0.1 or b[2] > 0.9 or b[3] > 0.9:
                bad_look.append(f"{a}: the maskable glyph is outside the 80 % safe zone {b}")
        except ImportError:
            print("[skip] Pillow is not installed: pixel checks skipped")
        svg = HS.rd(d, "icon.svg")
        if "<text" in svg or NEON.search(svg) or not svg.lstrip().startswith("<svg") or "viewBox" not in svg:
            bad_text.append(a)
        svg_hash.setdefault(hashlib.md5(svg.encode()).hexdigest(), []).append(a)
        png_hash.setdefault(hashlib.md5(open(os.path.join(d, "apple-touch-icon.png"), "rb").read()).hexdigest(), []).append(a)
        html = HS.rd(d, "index.html")
        p = HS.audit(d, a)
        bad_man += [f"{a}: {x}" for x in p]
        if not re.search(r'<meta[^>]*name="theme-color"[^>]*content="#14110e"', html) or "viewport-fit=cover" not in html:
            bad_head.append(f"{a}: theme-color #14110e / viewport-fit=cover")
        href = HS.tag(html, r'<link[^>]*rel="apple-touch-icon"[^>]*href="([^"]+)"')
        if href != "apple-touch-icon.png":
            bad_head.append(f"{a}: apple-touch-icon is {href!r}, not its own apple-touch-icon.png")
        if f'data-app="{a}"' not in html or not all(k in html for k in KIT):
            bad_kit.append(f"{a}: {[k for k in KIT if k not in html] or 'data-app'}")
        m = json.loads(HS.rd(d, "manifest.webmanifest"))
        got = {(i["src"], i.get("sizes"), i.get("purpose")) for i in m.get("icons", [])}
        want = {("icon.svg", "any", "any"), ("icon-192.png", "192x192", "any"), ("icon-512.png", "512x512", "any"), ("icon-maskable-512.png", "512x512", "maskable")}
        if got != want or m.get("id") != "./" or m.get("orientation") != "portrait" or m.get("theme_color") != "#14110e" or m.get("background_color") != "#14110e" or m.get("scope") != "./" or m.get("start_url") != "./":
            bad_man.append(f"{a}: manifest icons / id / start_url / scope / orientation / colours ({sorted(got ^ want)[:3]})")
    check(f"{len(here)} app folders checked: every one has icon.svg, the 180 / 192 / 512 / maskable PNGs, manifest.webmanifest, jarvis.json and index.html", not bad_files, bad_files)
    check("every PNG has the pixel size its name says (read from the file header)", not bad_png, bad_png)
    check("the icons are opaque full-bleed marble squares (corner = #1d1914) and the maskable glyph sits inside the 80 % safe zone", not bad_look, bad_look)
    check("the SVGs are plain marks: no <text> (not a letter on a square), no neon colours, a viewBox", not bad_text, bad_text)
    dup = [v for v in svg_hash.values() if len(v) > 1] + [v for v in png_hash.values() if len(v) > 1]
    check("every app has its own distinct icon (no two SVGs or 180 PNGs are the same)", not dup, dup)
    check("every page: viewport-fit=cover, theme-color #14110e, and the apple-touch-icon is the app's own 180 PNG", not bad_head, bad_head)
    check("every page carries the OLYMPUS kit lines (olympus.css, agora.css, themes.js, olympus.js data-app, intro-app.js, a11y.js, sfx.js)", not bad_kit, bad_kit)
    check("the same audit as tests/test_homescreen.py passes for each (apple tags, title <= 12, manifest, icons exist with their real sizes) and the manifests are consistent", not bad_man, bad_man)
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "make_app_icons.py"), "--check"], capture_output=True, text=True, timeout=120, cwd=ROOT)
    check("tools/make_app_icons.py --check has nothing left to fill", r.returncode == 0, r.stdout[-400:] + r.stderr[-300:])
    HS_bad = RES_bad = HS.RES.count(False)
    print(f"\n{len(HS.RES) - RES_bad}/{len(HS.RES)} passed")
    sys.exit(1 if RES_bad else 0)


if __name__ == "__main__":
    main()
