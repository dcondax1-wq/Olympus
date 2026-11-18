"""The OLYMPUS Home Screen icon (2026-11-18): a gold Greek temple on deep navy. ONE source, web/icons/icon.svg; this renders its PNGs.

    python tools/icon_temple.py            # web/icons/*.png (the phone root site + the PC site: build_web_dashboard copies them)
                                           # and tools/web_public/jarvis/ (Jarvis / Olympus and the apps that use its icon)

Sizes: 1024, 512, 192, 180 (apple-touch-icon), 152, 120 and a maskable 512 (the art scaled 0.8 into the safe circle).
All PNGs are RGB full-bleed squares (iOS rounds the corners itself). Rendering: Playwright's Chromium (gradients as in Safari).
After a change: bump the ?v= tags (python tools/bump_versions.py for jarvis/; the icons/...?v= tag by hand) and, on the iPhone,
delete the Home Screen icon and "Add to Home Screen" again: iOS keeps the old icon otherwise.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "web", "icons", "icon.svg")
OUTS = [os.path.join(ROOT, "web", "icons"), os.path.join(ROOT, "tools", "web_public", "jarvis")]
SIZES = [("icon-1024.png", 1024, 1.0), ("icon-512.png", 512, 1.0), ("icon-192.png", 192, 1.0), ("apple-touch-icon.png", 180, 1.0),
         ("icon-152.png", 152, 1.0), ("icon-120.png", 120, 1.0), ("icon-maskable-512.png", 512, 0.8)]
JARVIS_FILES = {"icon-512.png", "icon-192.png", "apple-touch-icon.png", "icon-maskable-512.png"}


def html(svg, size, scale):
    if scale != 1.0:      # the maskable version: the art (<g id="art">) scaled about the centre, the background untouched
        svg = svg.replace('<g id="art"', f'<g transform="translate(512 512) scale({scale}) translate(-512 -512)"><g id="art"', 1)
        i = svg.rfind("</g>")
        svg = svg[:i] + "</g></g>" + svg[i + 4:]
    svg = svg.replace('width="1024" height="1024"', f'width="{size}" height="{size}"', 1)
    return f"<!doctype html><html><body style='margin:0;background:#000'><div id='i' style='width:{size}px;height:{size}px;line-height:0'>{svg}</div></body></html>"


def main():
    from PIL import Image
    from playwright.sync_api import sync_playwright
    svg = open(SRC, encoding="utf-8").read()
    tmp = os.path.join(ROOT, "web", "icons")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 1100}, device_scale_factor=1)
        for name, size, scale in SIZES:
            pg.set_content(html(svg, size, scale))
            pg.wait_for_timeout(80)
            dst = os.path.join(tmp, name)
            pg.locator("#i").screenshot(path=dst)
            Image.open(dst).convert("RGB").save(dst, optimize=True)
            print("wrote", os.path.relpath(dst, ROOT))
        b.close()
    for name in sorted(JARVIS_FILES):
        shutil.copy(os.path.join(tmp, name), os.path.join(OUTS[1], name))
        print("copied", name, "-> tools/web_public/jarvis/")
    shutil.copy(SRC, os.path.join(OUTS[1], "icon.svg"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
