"""Rebuild the OLYMPUS / Jarvis PWA icon set from the owner's logo.

Source: tools/web_public/olympus/brand/olympus-logo-source.png (1254x1254, black bg).
Writes: jarvis/apple-touch-icon.png (180), icon-192.png, icon-512.png, icon-maskable-512.png,
jarvis/icon.svg (hand-drawn approximation, rewritten each run) and olympus/brand/olympus-logo-1024.png.
Run from the repo root:  python tools/make_olympus_icons.py
"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
SRC = os.path.join(WEB, "olympus", "brand", "olympus-logo-source.png")
JV = os.path.join(WEB, "jarvis")

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1254 1254">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe27a"/><stop offset=".55" stop-color="#f5a623"/><stop offset="1" stop-color="#b86a0a"/></linearGradient>
<linearGradient id="g2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffd24a"/><stop offset="1" stop-color="#9a5a08"/></linearGradient>
<linearGradient id="r" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc247"/><stop offset="1" stop-color="#ff7a18" stop-opacity=".6"/></linearGradient>
</defs>
<rect width="1254" height="1254" fill="#000"/>
<circle cx="620" cy="510" r="315" fill="none" stroke="url(#r)" stroke-width="22"/>
<path d="M60 934 L385 632 L432 658 L628 452 L808 698 L770 716 Z" fill="url(#g)"/>
<path d="M308 922 L600 622 L650 692 L895 852 L760 722 L640 690 Z" fill="url(#g2)"/>
<path d="M770 722 L860 648 L890 662 L1172 936 L838 770 Z" fill="url(#g)"/>
<path d="M556 618 L620 596 L690 618 L670 640 L560 640 Z" fill="#000"/>
<path d="M578 568 L626 552 L676 570 L676 582 L578 582 Z M584 586 h8 v28 h-8 z M600 586 h8 v28 h-8 z M616 586 h8 v28 h-8 z M632 586 h8 v28 h-8 z M648 586 h8 v28 h-8 z M664 586 h8 v28 h-8 z" fill="#000"/>
</svg>
"""


def content_crop(img):
    g = img.convert("L").point(lambda v: 255 if v > 24 else 0)
    return img.crop(g.getbbox())


def render(logo, size, width_frac):
    """Black square, logo scaled to width_frac of the side, centred."""
    w = round(size * width_frac)
    h = round(logo.height * w / logo.width)
    big = logo.resize((w, h), Image.LANCZOS)
    out = Image.new("RGB", (size, size), (0, 0, 0))
    out.paste(big, ((size - w) // 2, (size - h) // 2))
    return out


def main():
    logo = content_crop(Image.open(SRC).convert("RGB"))
    master = render(logo, 1024, 0.86)
    master.save(os.path.join(WEB, "olympus", "brand", "olympus-logo-1024.png"), optimize=True)
    # any-purpose icons: 86% wide; maskable: 62% wide stays inside the 80% safe circle
    for name, size, frac in (("apple-touch-icon.png", 180, 0.80), ("icon-192.png", 192, 0.86),
                             ("icon-512.png", 512, 0.86), ("icon-maskable-512.png", 512, 0.62)):
        render(logo, size * 4, frac).resize((size, size), Image.LANCZOS).save(os.path.join(JV, name), optimize=True)
    with open(os.path.join(JV, "icon.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(SVG)
    print("ok")


if __name__ == "__main__":
    main()
