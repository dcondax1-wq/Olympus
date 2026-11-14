"""Post designs drawn from code: 11 typographic layouts x the trade's fonts, palette, icons and motif -> one HTML page per image.

Square 1080 x 1080 (feed) and story 1080 x 1920 (9:16). No photos, no AI images, no web fonts from the network: the fonts are
OFL files in agency/content/fonts/ embedded as data URIs, the icons and patterns are SVG written here. A small script fits
each headline to its box (shrinks the type until it fits the line budget), then sets <html data-ready="1"> for the renderer.

Layouts: bold, split, tip, quote, offer, holiday, date, checklist, qa, frame, minimal.
"""
from __future__ import annotations

import base64
import html
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
SIZES = {"square": (1080, 1080), "story": (1080, 1920)}
LAYOUTS = ["bold", "split", "tip", "quote", "offer", "holiday", "date", "checklist", "qa", "frame", "minimal"]
DARK_LAYOUTS = {"bold", "split", "quote", "holiday", "checklist"}

# ------------------------------------------------------------------------------------------------------------------- fonts
# role key -> (css family, files [(file, weight, style)], weight used, style used, size scale for headlines, line height, case)
FONTS = {
    "bebas": ("Bebas Neue", [("bebas-neue-latin-400-normal.woff2", 400, "normal")], 400, "normal", 1.00, 0.92, "upper"),
    "anton": ("Anton", [("anton-latin-400-normal.woff2", 400, "normal")], 400, "normal", 0.86, 1.00, "upper"),
    "archivo": ("Archivo Black", [("archivo-black-latin-400-normal.woff2", 400, "normal")], 400, "normal", 0.66, 1.02, "upper"),
    "fraunces": ("Fraunces", [("fraunces-latin-600-normal.woff2", 600, "normal"), ("fraunces-latin-700-normal.woff2", 700, "normal")], 700, "normal", 0.74, 1.02, "none"),
    "cormorant": ("Cormorant Garamond", [("cormorant-garamond-latin-600-normal.woff2", 600, "normal"),
                                         ("cormorant-garamond-latin-600-italic.woff2", 600, "italic")], 600, "normal", 0.86, 0.98, "none"),
    "dmserif": ("DM Serif Display", [("dm-serif-display-latin-400-normal.woff2", 400, "normal"),
                                     ("dm-serif-display-latin-400-italic.woff2", 400, "italic")], 400, "normal", 0.78, 1.02, "none"),
    "dmserif_i": ("DM Serif Display", [("dm-serif-display-latin-400-normal.woff2", 400, "normal"),
                                       ("dm-serif-display-latin-400-italic.woff2", 400, "italic")], 400, "italic", 0.78, 1.04, "none"),
    "playfair_i": ("Playfair Display", [("playfair-display-latin-700-normal.woff2", 700, "normal"),
                                        ("playfair-display-latin-500-italic.woff2", 500, "italic")], 500, "italic", 0.74, 1.06, "none"),
    "manrope": ("Manrope", [("manrope-latin-500-normal.woff2", 500, "normal"), ("manrope-latin-700-normal.woff2", 700, "normal"),
                            ("manrope-latin-800-normal.woff2", 800, "normal")], 800, "normal", 0.64, 1.04, "none"),
    "manrope_x": ("Manrope", [("manrope-latin-500-normal.woff2", 500, "normal"), ("manrope-latin-700-normal.woff2", 700, "normal"),
                              ("manrope-latin-800-normal.woff2", 800, "normal")], 800, "normal", 0.64, 1.02, "none"),
    "caveat": ("Caveat", [("caveat-latin-600-normal.woff2", 600, "normal")], 600, "normal", 0.9, 1.0, "none"),
}
_B64: dict[str, str] = {}


def _b64(fname: str) -> str:
    if fname not in _B64:
        with open(os.path.join(FONT_DIR, fname), "rb") as fh:
            _B64[fname] = base64.b64encode(fh.read()).decode("ascii")
    return _B64[fname]


def font_faces(keys) -> str:
    seen, out = set(), []
    for k in keys:
        fam, files = FONTS[k][0], FONTS[k][1]
        for fname, w, st in files:
            if fname in seen:
                continue
            seen.add(fname)
            out.append(f'@font-face{{font-family:"{fam}";src:url(data:font/woff2;base64,{_b64(fname)}) format("woff2");'
                       f'font-weight:{w};font-style:{st};font-display:block}}')
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------------------------ colours
def _rgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def mix(a: str, b: str, t: float) -> str:
    """t = 0 -> a, 1 -> b"""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def luminance(h: str) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(color: str, on: str, toward: str, ratio: float = 3.2) -> str:
    """the colour, pushed toward `toward` until it reads on `on` (headline-size text: 3:1 and up)"""
    c, t = color, 0.0
    while contrast(c, on) < ratio and t < 1:
        t += 0.06
        c = mix(color, toward, t)
    return c


def palette_vars(p: dict) -> dict:
    v = dict(p)
    v["ink2"] = mix(p["ink"], p["bg"], 0.2)
    v["pink2"] = mix(p["paper_ink"], p["paper"], 0.22)
    v["acc_d"] = readable(p["accent"], p["bg"], p["ink"])
    v["acc_p"] = readable(p["accent"], p["paper"], "#000000", 3.0)          # darken toward black: keeps the hue (bronze, not olive)
    v["on_acc"] = p["bg"] if contrast(p["bg"], p["accent"]) >= contrast(p["paper_ink"], p["accent"]) else p["paper_ink"]
    if contrast(v["on_acc"], p["accent"]) < 3.5:
        v["on_acc"] = "#FFFFFF" if luminance(p["accent"]) < 0.3 else "#111111"
    v["card"] = mix(p["paper"], "#FFFFFF", 0.55)
    v["line_d"] = mix(p["ink"], p["bg"], 0.72)
    v["line_p"] = mix(p["paper_ink"], p["paper"], 0.8)
    return v


def brand_palette(primary: str, accent: str | None = None) -> dict:
    """a palette from a client's own colours (client["brand_colors"] or --colors): primary = the big colour"""
    dark = luminance(primary) < 0.3
    bg = primary if dark else mix(primary, "#101010", 0.72)
    ink = mix("#FFFFFF", primary, 0.06)
    paper = mix(primary, "#FFFFFF", 0.9) if dark else mix(primary, "#FFFFFF", 0.78)
    paper_ink = mix(primary, "#0B0B0B", 0.55) if dark else mix(primary, "#0B0B0B", 0.7)
    acc = accent or mix(primary, "#FFFFFF", 0.45)
    return {"name": "Client brand", "bg": bg, "ink": ink, "accent": acc, "paper": paper, "paper_ink": paper_ink, "soft": bg}


# -------------------------------------------------------------------------------------------------------------------- icons
def _poly(points) -> str:
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points) + " Z"


def _star(cx=32, cy=32, ro=26, ri=11, n=5) -> str:
    pts = []
    for i in range(n * 2):
        a = -math.pi / 2 + i * math.pi / n
        r = ro if i % 2 == 0 else ri
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return _poly(pts)


def _snowflake() -> str:
    d = []
    for k in range(6):
        a = math.radians(90 + 60 * k)
        x, y = 32 + 26 * math.cos(a), 32 - 26 * math.sin(a)
        d.append(f"M32 32 L{x:.1f} {y:.1f}")
        for r, w in ((17, 6.5), (9, 4.5)):
            bx, by = 32 + r * math.cos(a), 32 - r * math.sin(a)
            for s in (-1, 1):
                b = a + s * math.radians(42)
                d.append(f"M{bx:.1f} {by:.1f} L{bx + w * math.cos(b):.1f} {by - w * math.sin(b):.1f}")
    return f'<path d="{" ".join(d)}"/>'


def _rays(n=8, r1=17, r2=25) -> str:
    d = []
    for k in range(n):
        a = 2 * math.pi * k / n
        d.append(f"M{32 + r1 * math.cos(a):.1f} {32 + r1 * math.sin(a):.1f} L{32 + r2 * math.cos(a):.1f} {32 + r2 * math.sin(a):.1f}")
    return " ".join(d)


def _gear() -> str:
    pts, n = [], 8
    for k in range(n * 4):
        a = 2 * math.pi * k / (n * 4) - math.pi / 2
        r = 25 if (k % 4) in (1, 2) else 19
        pts.append((32 + r * math.cos(a), 32 + r * math.sin(a)))
    return f'<path d="{_poly(pts)}"/><circle cx="32" cy="32" r="8"/>'


def _flower() -> str:
    out = []
    for k in range(5):
        a = -math.pi / 2 + 2 * math.pi * k / 5
        out.append(f'<circle cx="{32 + 13 * math.cos(a):.1f}" cy="{32 + 13 * math.sin(a):.1f}" r="10"/>')
    return "".join(out) + '<circle cx="32" cy="32" r="6" fill="currentColor"/>'


def _clover() -> str:
    out = []
    for k in range(3):
        a = -math.pi / 2 + 2 * math.pi * k / 3
        cx, cy = 32 + 11 * math.cos(a), 28 + 11 * math.sin(a)
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="10.5"/>')
    return "".join(out) + '<path d="M32 30 C33 42 36 50 42 58"/>'


def _candles(n: int, center_tall: bool) -> str:
    d, flames = ["M8 50 H56"], []
    gap = 44 / (n - 1)
    for i in range(n):
        x = 10 + gap * i
        top = 22 if (center_tall and i == n // 2) else 30
        d.append(f"M{x:.1f} 50 V{top}")
        flames.append(f'<path d="M{x:.1f} {top - 9} c2.4 3 2.4 5.6 0 7 c-2.4-1.4-2.4-4 0-7z" fill="currentColor" stroke="none"/>')
    if center_tall:
        d.append("M32 50 V58 M24 58 H40")
    else:
        d.append("M14 50 L18 58 H46 L50 50")
    return f'<path d="{" ".join(d)}"/>' + "".join(flames)


ICONS = {
    "scissors": '<circle cx="19" cy="47" r="8"/><circle cx="45" cy="47" r="8"/><path d="M24.5 41.5 L46 8 M39.5 41.5 L18 8"/>'
                '<circle cx="32" cy="29.8" r="1.8" fill="currentColor"/>',
    "comb": '<g transform="rotate(-24 32 32)"><rect x="8" y="18" width="48" height="11" rx="3"/>'
            '<path d="M13 29v17M19 29v17M25 29v17M31 29v17M37 29v17M43 29v17M49 29v17"/></g>',
    "razor": '<rect x="13" y="9" width="38" height="11" rx="3"/><path d="M32 20 V54 M26 55 H38 M28.5 30 H35.5 M28.5 36 H35.5 M28.5 42 H35.5"/>',
    "sparkle": '<path d="M30 8 C32 24 38 30 54 32 C38 34 32 40 30 56 C28 40 22 34 6 32 C22 30 28 24 30 8Z"/>'
               '<path d="M51 6 c.6 4 2.2 5.6 6 6.2 c-3.8.6-5.4 2.2-6 6.2 c-.6-4-2.2-5.6-6-6.2 c3.8-.6 5.4-2.2 6-6.2z"/>',
    "mirror": '<ellipse cx="32" cy="24" rx="15" ry="18"/><path d="M32 42 V58 M26 58 H38"/><path d="M23.5 18 q2.5-6 8.5-7.5"/>',
    "cutlery": '<path d="M19 8 V22 a6 6 0 0 0 12 0 V8 M25 8 V22 M25 28 V56"/><path d="M45 56 V8 c6 4 8 12 8 20 s-4 10-8 10"/>',
    "chefhat": '<path d="M19 40 c-6-2-11-7-11-13 0-7 6-12 13-11 2-6 7-9 11-9 s9 3 11 9 c7-1 13 4 13 11 0 6-5 11-11 13"/>'
               '<path d="M19 40 V54 H45 V40 M19 47 H45"/>',
    "plate": '<path d="M12 46 a20 20 0 0 1 40 0 Z M32 26 V20 M27 19 H37 M6 52 H58"/>',
    "wrench": '<g transform="rotate(45 32 32)"><path d="M28 6.2 V15 H36 V6.2 A12 12 0 1 1 28 6.2 Z"/>'
              '<path d="M28 28.4 V54 a4 4 0 0 0 8 0 V28.4"/></g>',
    "droplet": '<path d="M32 6 C32 6 13 28 13 40 a19 19 0 0 0 38 0 C51 28 32 6 32 6Z"/><path d="M22.5 41 a9.5 9.5 0 0 0 7.5 9"/>',
    "flame": '<path d="M32 58 c-11 0-18-8-18-18 0-9 6-14 9-20 1 6 4 9 7 10 -1-9 3-18 10-24 1 9 6 14 9 19 3 5 1 10 1 15 0 10-7 18-18 18z"/>'
             '<path d="M32 58 c-5 0-8-4-8-9 0-5 4-8 6-12 1 4 3 6 5 7 2 3 5 5 5 9 0 3-3 5-8 5z"/>',
    "snowflake": _snowflake(),
    "leaf": '<path d="M12 52 C12 28 28 12 54 10 c0 26-16 42-42 42z"/><path d="M12 52 L38 26"/>',
    "tree": '<circle cx="32" cy="24" r="16"/><path d="M32 40 V58 M24 58 H40 M32 47 l-6-6 M32 44 l7-7"/>',
    "pine": '<path d="M32 6 L17 26 H25 L13 42 H51 L39 26 H47 Z"/><path d="M32 42 V56 M26 56 H38"/>',
    "sprout": '<path d="M32 58 V30"/><path d="M32 34 c0-10-8-16-18-16 0 10 8 16 18 16z"/><path d="M32 28 c0-10 7-16 18-16 0 10-7 16-18 16z"/><path d="M20 58 H44"/>',
    "car": '<path d="M7 43 V35 a4 4 0 0 1 3-4 l8-2 7-9 a6 6 0 0 1 5-2 h11 a6 6 0 0 1 5 2 l7 9 3.5 1 a4 4 0 0 1 3 4 V43 H53"/>'
           '<path d="M22 43 H42 M7 43 H12 M25 29 H48"/><circle cx="17" cy="44" r="5"/><circle cx="47" cy="44" r="5"/>',
    "gear": _gear(),
    "dumbbell": '<g transform="rotate(-30 32 32)"><path d="M20 32 H44 M6 26 V38 M58 26 V38"/><rect x="11" y="19" width="8" height="26" rx="2"/>'
                '<rect x="45" y="19" width="8" height="26" rx="2"/></g>',
    "kettlebell": '<path d="M23 28 V20 a9 9 0 0 1 18 0 V28"/><path d="M21.4 55 A16 16 0 1 1 42.6 55 Z"/>',
    "pulse": '<path d="M5 34 H17 L22 22 L30 46 L36 28 L40 34 H59"/>',
    "tooth": '<path d="M20 9 c-7 0-11 6-11 13 0 7 3 11 4 18 1 8 3 15 7 15 5 0 5-12 8-16 2-2 6-2 8 0 3 4 3 16 8 16 4 0 6-7 7-15 '
             '1-7 4-11 4-18 0-7-4-13-11-13 -5 0-8 3-12 3 s-7-3-12-3z"/>',
    "toothbrush": '<g transform="rotate(-35 32 32)"><rect x="6" y="36" width="52" height="7" rx="3.5"/><path d="M38 36 V27 M43 36 V27 M48 36 V27 M53 36 V27"/></g>',
    "gift": '<rect x="10" y="26" width="44" height="30" rx="3"/><path d="M7 18 H57 V26 H7 Z M32 18 V56"/>'
            '<path d="M32 18 c-3-7-14-11-14-4 0 3 4 4 14 4z M32 18 c3-7 14-11 14-4 0 3-4 4-14 4z"/>',
    "star": f'<path d="{_star()}"/>',
    "heart": '<path d="M32 54 C20 46 8 37 8 24 a12 12 0 0 1 24-5 a12 12 0 0 1 24 5 c0 13-12 22-24 30z"/>',
    "calendar": '<rect x="9" y="12" width="46" height="44" rx="5"/><path d="M9 25 H55 M21 6 V16 M43 6 V16"/>',
    "check": '<path d="M14 33 L25 44 L50 18"/>',
    "quote": '<path d="M10 42 c0-11 5-19 15-23 l2.5 4.5 c-5 2.5-8 6.5-8.5 10.5 H26 V50 H10 Z M36 42 c0-11 5-19 15-23 l2.5 4.5 '
             'c-5 2.5-8 6.5-8.5 10.5 H52 V50 H36 Z" fill="currentColor" stroke="none"/>',
    "sun": f'<circle cx="32" cy="32" r="11"/><path d="{_rays()}"/>',
    "pumpkin": '<path d="M32 22 c-1-6 1-10 5-12"/><ellipse cx="32" cy="39" rx="23" ry="17"/>'
               '<path d="M32 22 c-7 0-10 8-10 17 s3 17 10 17 10-8 10-17 -3-17-10-17z"/>',
    "clover": _clover(),
    "flower": _flower(),
    "spark": f'<path d="{_rays(8, 9, 25)}"/><circle cx="32" cy="32" r="3" fill="currentColor"/>',
    "clock": '<circle cx="32" cy="32" r="24"/><path d="M32 18 V32 L42 38"/>',
    "menorah": _candles(9, True),
    "candles7": _candles(7, False),
    "pin": '<path d="M32 58 s18-18 18-32 a18 18 0 0 0-36 0 c0 14 18 32 18 32z"/><circle cx="32" cy="26" r="6"/>',
    "phone": '<path d="M20 8 h-6 a4 4 0 0 0-4 4 c0 24 18 42 42 42 a4 4 0 0 0 4-4 v-6 l-11-5-5 5 c-7-3-12-8-15-15 l5-5 z"/>',
}


def icon(name: str, cls: str = "ic", stroke: float = 3.2, style: str = "") -> str:
    body = ICONS.get(name) or ICONS["star"]
    st = f' style="{style}"' if style else ""
    return (f'<svg class="{cls}"{st} viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


# ------------------------------------------------------------------------------------------------------------------ motifs
MOTIF_ICON = {"snow": "snowflake", "hearts": "heart", "clovers": "clover", "stars": "star", "leaves": "leaf", "flowers": "flower",
              "suns": "sun", "drops": "droplet", "confetti": None, "dots": None, "bubbles": None}


def scatter(seed: int, w: int, h: int, n: int, rmin: float, rmax: float, keep_out=None) -> list:
    """non-overlapping random circles (x, y, r): a deterministic spread for patterns. keep_out: one box or a list of boxes
    (x0, y0, x1, y1) that no circle may touch (the text, the footer)"""
    rnd = random.Random(seed)
    boxes = [] if not keep_out else ([keep_out] if isinstance(keep_out[0], (int, float)) else list(keep_out))
    out, tries = [], 0
    while len(out) < n and tries < n * 80:
        tries += 1
        r = rnd.uniform(rmin, rmax)
        x, y = rnd.uniform(-r * 0.3, w + r * 0.3), rnd.uniform(-r * 0.3, h + r * 0.3)
        if any(b[0] - r < x < b[2] + r and b[1] - r < y < b[3] + r for b in boxes):
            continue
        if all((x - a) ** 2 + (y - b) ** 2 > (r + c + 18) ** 2 for a, b, c in out):
            out.append((x, y, r))
    return out


def motif_svg(motif: str, w: int, h: int, seed: int, color: str, alt: str, opacity: float, keep_out=None, density=1.0) -> str:
    """a full-canvas SVG layer for a holiday or trade motif"""
    parts = []
    if motif in ("confetti",):
        rnd = random.Random(seed)
        for x, y, r in scatter(seed, w, h, int(70 * density), 8, 18, keep_out):
            c = color if rnd.random() < 0.6 else alt
            if rnd.random() < 0.5:
                parts.append(f'<rect x="{x - r / 2:.0f}" y="{y - r * 0.2:.0f}" width="{r:.0f}" height="{r * 0.4:.0f}" rx="2" fill="{c}" '
                             f'transform="rotate({rnd.uniform(0, 180):.0f} {x:.0f} {y:.0f})"/>')
            else:
                parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r * 0.32:.1f}" fill="{c}"/>')
    elif motif in ("dots", "bubbles"):
        rnd = random.Random(seed)
        for x, y, r in scatter(seed, w, h, int(34 * density), 10, 46 if motif == "bubbles" else 16, keep_out):
            if motif == "bubbles" and rnd.random() < 0.3:
                parts.append(f'<g transform="translate({x - r * 0.6:.0f} {y - r * 0.6:.0f}) scale({r / 54:.3f})" color="{alt}">{icon("sparkle")}</g>')
            else:
                parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r * 0.5:.1f}" fill="none" stroke="{color}" stroke-width="3"/>'
                             if motif == "bubbles" else f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r * 0.4:.1f}" fill="{color}"/>')
    else:
        name = MOTIF_ICON.get(motif) or "star"
        rnd = random.Random(seed)
        for x, y, r in scatter(seed, w, h, int(26 * density), 26, 54, keep_out):
            c = color if rnd.random() < 0.7 else alt
            s = r * 2 / 64
            parts.append(f'<g transform="translate({x - r:.0f} {y - r:.0f}) rotate({rnd.uniform(-30, 30):.0f} {r:.0f} {r:.0f}) scale({s:.3f})" '
                         f'color="{c}"><svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="3.4" '
                         f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg></g>')
    return (f'<svg class="motif" width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="opacity:{opacity}" aria-hidden="true">'
            + "".join(parts) + "</svg>")


def trade_pattern(motif: str, color: str, opacity: float) -> str:
    """the trade's own background texture, as CSS (barber pole, gingham, pipes, chevrons, bars, leaves, arcs, bubbles)"""
    c = color
    if motif == "pole":
        return f"repeating-linear-gradient(135deg,{c} 0 26px,transparent 26px 64px)"
    if motif == "gingham":
        return (f"repeating-linear-gradient(0deg,{c} 0 22px,transparent 22px 44px),"
                f"repeating-linear-gradient(90deg,{c} 0 22px,transparent 22px 44px)")
    if motif == "chevrons":
        return (f"linear-gradient(135deg,{c} 25%,transparent 25%) -40px 0/80px 80px,"
                f"linear-gradient(225deg,{c} 25%,transparent 25%) -40px 0/80px 80px")
    if motif == "bars":
        return f"repeating-linear-gradient(115deg,{c} 0 18px,transparent 18px 90px)"
    if motif == "pipes":
        return (f"repeating-linear-gradient(0deg,transparent 0 118px,{c} 118px 130px),"
                f"repeating-linear-gradient(90deg,transparent 0 238px,{c} 238px 250px)")
    if motif == "arcs":
        return f"repeating-radial-gradient(circle at 100% 0,transparent 0 46px,{c} 46px 50px)"
    if motif == "bubbles":
        return f"radial-gradient(circle,{c} 0 7px,transparent 8px) 0 0/64px 64px"
    return f"radial-gradient(circle,{c} 0 5px,transparent 6px) 0 0/48px 48px"     # leaves and anything else: soft dots


# ------------------------------------------------------------------------------------------------------------------ helpers
def esc(t) -> str:
    return html.escape(str(t or ""), quote=True)


def nb(text: str) -> str:
    """keep number ranges and short words together on images: 2-3 weeks never breaks after the hyphen"""
    return re.sub(r"(\d)-(\d)", "\\1\u2011\\2", text or "")


def rich(text: str) -> str:
    """*word* -> <em>word</em>, the rest escaped"""
    parts = re.split(r"(\*[^*]+\*)", nb(text))
    return "".join(f"<em>{esc(p[1:-1])}</em>" if p.startswith("*") and p.endswith("*") and len(p) > 2 else esc(p) for p in parts)


def initials(name: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", name or "") if w.lower() not in ("the", "and", "of", "co", "llc", "inc")]
    return ("".join(w[0] for w in words[:2]) or (name or "?")[:1]).upper()


FIT_JS = """(function(){function fit(e){var mx=+e.getAttribute('data-max'),mn=+(e.getAttribute('data-min')||26),ln=+(e.getAttribute('data-lines')||3),s=mx;
var box=e.closest('[data-box]');e.style.fontSize=s+'px';
function bad(){var lh=parseFloat(getComputedStyle(e).lineHeight)||s;return e.offsetHeight>lh*ln+3||e.scrollWidth>e.clientWidth+2||
(box&&box.scrollHeight>box.clientHeight+2);}
while(s>mn&&bad()){s-=2;e.style.fontSize=s+'px';}}
function go(){var a=document.querySelectorAll('[data-max]');for(var i=0;i<a.length;i++)fit(a[i]);document.documentElement.setAttribute('data-ready','1');}
if(document.fonts&&document.fonts.ready){document.fonts.ready.then(function(){requestAnimationFrame(go);});}else{go();}})();"""

GRAIN = ("data:image/svg+xml;base64," + base64.b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><filter id="n"><feTurbulence type="fractalNoise" '
    b'baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 0.5 0 0 0 0 0.5 0 0 0 0 0.5 0 0 0 1.4 -0.2"/></filter>'
    b'<rect width="100%" height="100%" filter="url(#n)"/></svg>').decode("ascii"))


def base_css(brand: dict, fmt: str) -> str:
    v = brand["vars"]
    fd = FONTS[brand["fonts"]["display"]]
    fa = FONTS[brand["fonts"]["accent"]]
    fh = FONTS[brand["fonts"].get("hand", "caveat")]
    up = fd[6] == "upper"
    w, h = SIZES[fmt]
    st = fmt == "story"
    m = 96 if st else 84
    return f"""
:root{{--bg:{v['bg']};--ink:{v['ink']};--ink2:{v['ink2']};--acc:{v['accent']};--accd:{v['acc_d']};--accp:{v['acc_p']};--paper:{v['paper']};
--pink:{v['paper_ink']};--pink2:{v['pink2']};--onacc:{v['on_acc']};--card:{v['card']};--lined:{v['line_d']};--linep:{v['line_p']};
--fd:"{fd[0]}";--fdw:{fd[2]};--fds:{fd[3]};--fa:"{fa[0]}";--faw:{fa[2]};--fas:{fa[3]};--fh:"{fh[0]}";--m:{m}px;--W:{w}px;--H:{h}px}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:var(--bg)}}
body{{font-family:"Manrope",system-ui,sans-serif;font-weight:500;-webkit-font-smoothing:antialiased;text-rendering:geometricPrecision}}
.cv{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:var(--bg);color:var(--ink)}}
.cv.light{{background:var(--paper);color:var(--pink)}}
.motif,.pat{{position:absolute;inset:0;pointer-events:none}}
.grain{{position:absolute;inset:0;background-image:url("{GRAIN}");background-size:320px;opacity:.07;mix-blend-mode:overlay;pointer-events:none}}
.light .grain{{mix-blend-mode:multiply;opacity:.06}}
.hl{{font-family:var(--fd),serif;font-weight:var(--fdw);font-style:var(--fds);line-height:{fd[5]};letter-spacing:{'.01em' if up else '-.012em'};
text-transform:{'uppercase' if up else 'none'};overflow-wrap:normal;word-break:normal;hyphens:none;text-wrap:balance}}
.hl em{{font-style:{'normal' if up else 'italic'};{'' if up else 'font-family:var(--fa),serif;font-weight:var(--faw);'}color:var(--accd)}}
.light .hl em{{color:var(--accp)}}
.serif{{font-family:var(--fa),serif;font-weight:var(--faw);font-style:var(--fas);letter-spacing:-.005em}}
.label{{display:inline-flex;align-items:center;gap:14px;font:800 {26 if st else 23}px/1 "Manrope";letter-spacing:.2em;text-transform:uppercase}}
.chip{{padding:{15 if st else 13}px {26 if st else 22}px {13 if st else 11}px;border-radius:999px;background:var(--acc);color:var(--onacc)}}
.sub{{font:500 {44 if st else 36}px/1.38 "Manrope";color:var(--ink2);text-wrap:pretty}}
.light .sub{{color:var(--pink2)}}
.rule{{width:{132 if st else 112}px;height:{9 if st else 8}px;border-radius:9px;background:var(--acc)}}
.foot{{position:absolute;left:var(--m);right:var(--m);bottom:{250 if st else 62}px;display:flex;align-items:center;gap:20px;
font:800 {25 if st else 22}px/1.1 "Manrope";letter-spacing:.15em;text-transform:uppercase;color:var(--ink)}}
.light .foot{{color:var(--pink)}}
.foot .mono{{flex:none;width:{70 if st else 62}px;height:{70 if st else 62}px;border-radius:50%;background:var(--acc);color:var(--onacc);
display:flex;align-items:center;justify-content:center;font-family:var(--fd);font-weight:var(--fdw);font-size:{30 if st else 27}px;
letter-spacing:{'.04em' if up else '0'};text-transform:uppercase}}
.foot .biz{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}}
.foot .city{{opacity:.62;white-space:nowrap}}
.foot .web{{margin-left:auto;letter-spacing:.06em;text-transform:none;font-weight:700;opacity:.86;white-space:nowrap}}
.ic{{display:block}}
.num,.day,.hl{{font-variant-numeric:lining-nums}}
"""


def foot(brand: dict, web: bool = True, center: bool = False, fmt: str = "square") -> str:
    """mark + name (+ city) (+ site or phone). A long name drops the city, then the site (both are in the caption anyway):
    the name itself is never cut. Stories put the site on its own line."""
    style = ' style="justify-content:center"' if center else ""
    name, city, site = brand["name"], brand.get("city") or "", brand.get("web") or ""
    show_web = bool(web and site and not center)
    budget = 50 if fmt == "story" else 44                              # characters that fit one line at the footer size
    if show_web and fmt != "story" and len(name) + len(city) + len(site) > budget:
        city = ""
        if len(name) + len(site) > budget:
            show_web = False
    if len(name) + len(city) > (budget - 8 if center else budget):
        city = ""
    w = f'<span class="web">{esc(site)}</span>' if show_web else ""
    city = f'<span class="city">&middot; {esc(city)}</span>' if city else ""
    if fmt == "story" and w:
        style = ' style="flex-wrap:wrap;row-gap:10px"'
        w = f'<span class="web" style="flex-basis:100%;margin-left:90px">{esc(site)}</span>'
    return (f'<div class="foot"{style}><span class="mono">{esc(brand["initials"])}</span><span class="biz">{esc(brand["name"])}</span>'
            f'{city}{w}</div>')


# ------------------------------------------------------------------------------------------------------------------ layouts
def _hl(text, mx, lines, extra="", mn=30, cls="hl"):
    return f'<h1 class="{cls}" data-max="{mx}" data-min="{mn}" data-lines="{lines}"{extra}>{rich(text)}</h1>'


def _sub(text, mx, lines, cls="sub"):
    return f'<p class="{cls}" data-max="{mx}" data-min="24" data-lines="{lines}">{esc(nb(text))}</p>'


def _scale(brand) -> float:
    return FONTS[brand["fonts"]["display"]][4]


def lay_bold(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    top, bot = (400, 470) if st else (170, 190)
    css = f""".L-bold .wm{{position:absolute;right:-150px;bottom:{-40 if st else -150}px;width:{900 if st else 760}px;height:{900 if st else 760}px;
color:var(--ink);opacity:.075;transform:rotate(-14deg)}}
.L-bold .wrap{{position:absolute;left:var(--m);right:var(--m);top:{top}px;bottom:{bot}px;display:flex;flex-direction:column;justify-content:center;gap:{40 if st else 32}px}}
.L-bold .lab{{position:absolute;left:var(--m);top:{300 if st else 78}px}}
.L-bold .pat{{background:{trade_pattern(b['motif'], b['vars']['line_d'], 1)};opacity:.45;-webkit-mask:linear-gradient(90deg,#000,transparent 55%);mask:linear-gradient(90deg,#000,transparent 55%)}}"""
    body = (f'<div class="pat"></div><div class="wm">{icon(p["icon"], stroke=2.4)}</div>'
            f'<div class="lab"><span class="label chip">{esc(p["label"])}</span></div>'
            f'<div class="wrap" data-box>{_hl(p["headline"], int((250 if st else 205) * s), 4 if st else 3)}<div class="rule"></div>'
            f'{_sub(p["sub"], 46 if st else 38, 4 if st else 3)}</div>{foot(b, fmt=fmt)}')
    return css, body, "dark"


def lay_split(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    cut = 1130 if st else 610
    css = f""".L-split .top{{position:absolute;left:0;right:0;top:0;height:{cut}px;background:var(--bg)}}
.L-split .bot{{position:absolute;left:0;right:0;top:{cut}px;bottom:0;background:var(--paper)}}
.L-split .band{{position:absolute;left:0;right:0;top:{cut - 10}px;height:10px;background:var(--acc)}}
.L-split .top::after{{content:"";position:absolute;inset:0;background:{trade_pattern(b['motif'], b['vars']['line_d'], 1)};opacity:.4;
-webkit-mask:linear-gradient(90deg,transparent 30%,#000);mask:linear-gradient(90deg,transparent 30%,#000)}}
.L-split .go{{margin-top:{34 if st else 26}px;font:800 {32 if st else 26}px/1.2 "Manrope";letter-spacing:.06em;color:var(--accp)}}
.L-split .t{{position:absolute;left:var(--m);right:{300 if st else 250}px;top:{300 if st else 96}px;bottom:{(1920 - cut) + 90 if st else (1080 - cut) + 70}px;display:flex;flex-direction:column;justify-content:flex-end;gap:{34 if st else 26}px}}
.L-split .disc{{position:absolute;right:var(--m);top:{cut - (120 if st else 104)}px;width:{240 if st else 208}px;height:{240 if st else 208}px;border-radius:50%;
background:var(--acc);color:var(--onacc);display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 {14 if st else 12}px var(--paper)}}
.L-split .disc .ic{{width:56%;height:56%}}
.L-split .b{{position:absolute;left:var(--m);right:var(--m);top:{cut + (170 if st else 128)}px;color:var(--pink)}}
.L-split .b .sub{{color:var(--pink2)}}
.L-split .foot{{color:var(--pink)}}"""
    body = (f'<div class="top"></div><div class="bot"></div><div class="band"></div>'
            f'<div class="t"><span class="label" style="color:var(--accd)">{esc(p["label"])}</span>'
            f'{_hl(p["headline"], int((230 if st else 168) * s), 3 if st else 2)}</div>'
            f'<div class="disc">{icon(p["icon"], stroke=3)}</div>'
            f'<div class="b">{_sub(p.get("sub_long") or p["sub"], 46 if st else 36, 5 if st else 3)}'
            f'{"<div class=go>" + esc(p["go"]) + "</div>" if p.get("go") else ""}</div>{foot(b, web=False, fmt=fmt)}')
    return css, body, "split"


def lay_tip(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    num = f'{p.get("number", 1):02d}'
    band = 150 if st else 132
    css = f""".L-tip .num{{position:absolute;left:{70 if st else 62}px;top:{290 if st else 26}px;font-family:var(--fd);font-weight:var(--fdw);
font-size:{int((560 if st else 400) * min(1.0, s + .12))}px;line-height:.82;color:var(--accp);letter-spacing:-.02em}}
.L-tip .lab{{position:absolute;right:var(--m);top:{300 if st else 92}px}}
.L-tip .wrap{{position:absolute;left:var(--m);right:var(--m);top:{820 if st else 420}px;bottom:{band + (330 if st else 70)}px;display:flex;flex-direction:column;justify-content:center;gap:{30 if st else 24}px}}
.L-tip .band{{position:absolute;left:0;right:0;bottom:0;height:{band + (210 if st else 0)}px;background:var(--bg)}}
.L-tip .foot{{color:var(--ink);bottom:{250 if st else 35}px}}
.L-tip .pat{{background:{trade_pattern(b['motif'], b['vars']['line_p'], 1)};opacity:.55;-webkit-mask:linear-gradient(180deg,#000,transparent 40%);mask:linear-gradient(180deg,#000,transparent 40%)}}"""
    body = (f'<div class="pat"></div><div class="num">{num}</div><div class="lab"><span class="label chip">{esc(p["label"])}</span></div>'
            f'<div class="wrap" data-box>{_hl(p["headline"], int((200 if st else 150) * s), 3)}<div class="rule"></div>{_sub(p["sub"], 44 if st else 35, 4 if st else 3)}</div>'
            f'<div class="band"></div>{foot(b, fmt=fmt)}')
    return css, body, "light"


def lay_quote(p, b, fmt):
    st = fmt == "story"
    q = p.get("quote")
    stars = "".join(f'<svg viewBox="0 0 64 64" class="st"><path d="{_star()}" fill="currentColor"/></svg>' for _ in range(5))
    css = f""".L-quote .qm{{position:absolute;left:{70 if st else 62}px;top:{290 if st else 52}px;width:{230 if st else 190}px;height:{230 if st else 190}px;color:var(--accd);opacity:.95}}
.L-quote .wrap{{position:absolute;left:var(--m);right:var(--m);top:{560 if st else 280}px;bottom:{520 if st else 190}px;display:flex;flex-direction:column;justify-content:center;gap:{40 if st else 30}px}}
.L-quote .stars{{display:flex;gap:{14 if st else 12}px;color:var(--accd)}}
.L-quote .st{{width:{60 if st else 50}px;height:{60 if st else 50}px}}
.L-quote .qt{{font-family:var(--fa),serif;font-weight:var(--faw);font-style:italic;line-height:1.16;color:var(--ink);text-wrap:balance}}
.L-quote .who{{font:800 {28 if st else 24}px/1.2 "Manrope";letter-spacing:.18em;text-transform:uppercase;color:var(--accd)}}
.L-quote .motif{{opacity:.9}}"""
    if q:
        inner = (f'<div class="stars">{stars}</div><p class="qt" data-max="{96 if st else 70}" data-min="34" data-lines="{8 if st else 6}">{esc(q["text"])}</p>'
                 f'<div class="who">&mdash; {esc(q["who"])}</div>')
    else:
        inner = (f'<div class="stars">{stars}</div>{_hl(p["headline"], int((220 if st else 160) * _scale(b)), 3)}'
                 f'{_sub(p["sub"], 44 if st else 36, 4 if st else 3)}<div class="who">{esc(p["label"])}</div>')
    body = f'<div class="qm">{icon("quote")}</div><div class="wrap" data-box>{inner}</div>{foot(b, fmt=fmt)}'
    return css, body, "dark"


def lay_offer(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    top, bot = (330, 470) if st else (128, 176)
    stub = 230 if st else 170
    cta = p.get("cta_short") or b.get("web") or b.get("phone") or "Ask us"
    css = f""".L-offer .pat{{background:{trade_pattern(b['motif'], b['vars']['line_p'], 1)};opacity:.7}}
.L-offer .tk{{position:absolute;left:var(--m);right:var(--m);top:{top}px;bottom:{bot}px;border-radius:{40 if st else 34}px;background:var(--bg);color:var(--ink);
box-shadow:0 30px 60px -30px rgba(0,0,0,.45)}}
.L-offer .tk::before,.L-offer .tk::after{{content:"";position:absolute;bottom:{stub - 36}px;width:72px;height:72px;border-radius:50%;background:var(--paper)}}
.L-offer .tk::before{{left:-36px}} .L-offer .tk::after{{right:-36px}}
.L-offer .perf{{position:absolute;left:56px;right:56px;bottom:{stub}px;border-top:4px dashed var(--lined)}}
.L-offer .in{{position:absolute;left:{70 if st else 60}px;right:{70 if st else 60}px;top:{90 if st else 56}px;bottom:{stub + (60 if st else 40)}px;display:flex;flex-direction:column;justify-content:center;gap:{30 if st else 22}px}}
.L-offer .stub{{position:absolute;left:{70 if st else 60}px;right:{70 if st else 60}px;bottom:0;height:{stub}px;display:flex;align-items:center;justify-content:space-between;gap:20px}}
.L-offer .cta{{font:800 {34 if st else 28}px/1 "Manrope";letter-spacing:.1em;color:var(--accd);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.L-offer .stub .ic{{width:{90 if st else 74}px;height:{90 if st else 74}px;color:var(--accd);flex:none}}
.L-offer .tk .sub{{color:var(--ink2)}}
.L-offer .tk .hl em{{color:var(--accd)}}
.L-offer .foot{{color:var(--pink)}}"""
    body = (f'<div class="pat"></div><div class="tk"><div class="in" data-box><span class="label" style="color:var(--accd)">{esc(p["label"])}</span>'
            f'{_hl(p["headline"], int((220 if st else 160) * s), 3)}{_sub(p["sub"], 42 if st else 33, 4 if st else 3)}</div><div class="perf"></div>'
            f'<div class="stub"><span class="cta">{esc(cta)}</span>{icon(p["icon"], stroke=3)}</div></div>{foot(b, web=False, fmt=fmt)}')
    return css, body, "light"


def lay_holiday(p, b, fmt):
    st = fmt == "story"
    w, h = SIZES[fmt]
    inset = 52 if st else 44
    keep = [(150, 380, 930, 1420), (120, 1560, 960, 1730)] if st else [(120, 150, 960, 850), (150, 900, 930, 1040)]
    mot = motif_svg(p.get("motif") or "stars", w, h, p["seed"], b["vars"]["acc_d"], b["vars"]["ink"], 0.30, keep_out=keep, density=1.2 if st else 0.75)
    css = f""".L-holiday .frame{{position:absolute;inset:{inset}px;border:2px solid var(--lined);border-radius:{30 if st else 24}px}}
.L-holiday .frame::after{{content:"";position:absolute;inset:14px;border:1.5px solid var(--accd);border-radius:{22 if st else 16}px;opacity:.6}}
.L-holiday .wrap{{position:absolute;left:{150 if st else 130}px;right:{150 if st else 130}px;top:{420 if st else 150}px;bottom:{560 if st else 200}px;display:flex;flex-direction:column;
align-items:center;justify-content:center;text-align:center;gap:{34 if st else 24}px}}
.L-holiday .big{{width:{170 if st else 120}px;height:{170 if st else 120}px;color:var(--accd)}}
.L-holiday .hh{{font-family:var(--fa),serif;font-weight:var(--faw);font-style:italic;line-height:1.02;letter-spacing:-.01em;color:var(--ink);text-wrap:balance}}
.L-holiday .hh em{{color:var(--accd);font-style:italic}}
.L-holiday .foot{{justify-content:center;bottom:{250 if st else 86}px}}"""
    body = (f'{mot}<div class="frame"></div><div class="wrap" data-box>{icon(p["icon"], "ic big", stroke=2.6)}'
            f'<span class="label" style="color:var(--accd)">{esc(p["label"])}</span>'
            f'<h1 class="hh" data-max="{150 if st else 118}" data-min="40" data-lines="{3 if st else 2}">{rich(p["headline"])}</h1>'
            f'{_sub(p["sub"], 42 if st else 33, 4 if st else 3)}</div>{foot(b, center=True, fmt=fmt)}')
    return css, body, "dark"


def lay_date(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    d = p.get("tile") or {}
    tw, th = (430, 500) if st else (318, 372)
    css = f""".L-date .pat{{background:{trade_pattern(b['motif'], b['vars']['line_p'], 1)};opacity:.6;-webkit-mask:linear-gradient(200deg,#000,transparent 45%);mask:linear-gradient(200deg,#000,transparent 45%)}}
.L-date .tile{{position:absolute;{'left:50%;margin-left:-' + str(tw // 2) + 'px;top:300px' if st else 'left:var(--m);top:84px'};width:{tw}px;height:{th}px;border-radius:{34 if st else 28}px;background:var(--bg);
color:var(--ink);overflow:hidden;box-shadow:0 28px 50px -26px rgba(0,0,0,.5);display:flex;flex-direction:column;align-items:center}}
.L-date .mon{{width:100%;height:{118 if st else 92}px;background:var(--acc);color:var(--onacc);display:flex;align-items:center;justify-content:center;
font:800 {58 if st else 44}px/1 "Manrope";letter-spacing:.24em;padding-left:.24em}}
.L-date .day{{font-family:var(--fd);font-weight:var(--fdw);font-size:{int(290 * max(s, .78)) if st else int(214 * max(s, .78))}px;line-height:1;margin-top:{26 if st else 18}px}}
.L-date .dow{{font:800 {28 if st else 22}px/1 "Manrope";letter-spacing:.24em;text-transform:uppercase;opacity:.75;margin-top:auto;margin-bottom:{36 if st else 28}px}}
.L-date .side{{position:absolute;left:{tw + 84 + 56}px;right:var(--m);top:84px;height:{th}px;display:flex;flex-direction:column;justify-content:center;gap:16px}}
.L-date .ev{{font-family:var(--fa),serif;font-weight:var(--faw);font-style:var(--fas);font-size:{60 if st else 52}px;line-height:1.05;color:var(--pink)}}
.L-date .wrap{{position:absolute;left:var(--m);right:var(--m);top:{870 if st else 520}px;bottom:{520 if st else 170}px;display:flex;flex-direction:column;justify-content:center;gap:{30 if st else 22}px;{'align-items:center;text-align:center' if st else ''}}}"""
    side = "" if st else (f'<div class="side"><span class="label" style="color:var(--accp)">{esc(p["label"])}</span>'
                          f'<div class="ev">{esc(d.get("event", ""))}</div></div>')
    lab = f'<span class="label" style="color:var(--accp)">{esc(p["label"])}</span>' if st else ""
    body = (f'<div class="pat"></div><div class="tile"><div class="mon">{esc(d.get("mon", ""))}</div><div class="day">{esc(d.get("day", ""))}</div>'
            f'<div class="dow">{esc(d.get("dow", ""))}</div></div>{side}'
            f'<div class="wrap" data-box>{lab}{_hl(p["headline"], int((210 if st else 150) * s), 3 if st else 2)}{_sub(p["sub"], 44 if st else 34, 4 if st else 3)}</div>{foot(b, fmt=fmt)}')
    return css, body, "light"


def lay_checklist(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    items = p.get("items") or []
    ck = icon("check", stroke=6)
    rows = "".join(f'<li><span class="ck">{ck}</span><span class="tx">{esc(nb(t))}</span></li>' for t in items[:5])
    css = f""".L-checklist .head{{position:absolute;left:var(--m);right:var(--m);top:{290 if st else 76}px;display:flex;flex-direction:column;gap:{28 if st else 20}px}}
.L-checklist ul{{list-style:none;position:absolute;left:var(--m);right:var(--m);top:{820 if st else 452}px;display:flex;flex-direction:column;gap:{40 if st else 26}px}}
.L-checklist li{{display:flex;align-items:center;gap:{30 if st else 26}px;font:700 {50 if st else 40}px/1.15 "Manrope";color:var(--ink)}}
.L-checklist .ck{{flex:none;width:{78 if st else 64}px;height:{78 if st else 64}px;border-radius:50%;background:var(--acc);color:var(--onacc);display:flex;align-items:center;justify-content:center}}
.L-checklist .ck .ic{{width:58%;height:58%}}
.L-checklist li+li{{padding-top:{40 if st else 26}px;border-top:2px solid var(--lined);margin-top:-{0}px}}
.L-checklist .wm{{position:absolute;right:-90px;bottom:{330 if st else 120}px;width:{620 if st else 520}px;height:{620 if st else 520}px;opacity:.05;color:var(--ink);transform:rotate(12deg)}}"""
    body = (f'<div class="head"><span class="label chip" style="align-self:flex-start">{esc(p["label"])}</span>'
            f'{_hl(p["headline"], int((200 if st else 128) * s), 2)}</div><ul>{rows}</ul>{foot(b, fmt=fmt)}')
    return css, body, "dark"


def lay_qa(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    css = f""".L-qa .q{{position:absolute;left:{66 if st else 58}px;top:{250 if st else 40}px;font-family:var(--fd);font-weight:var(--fdw);font-size:{int(430 * max(s, .8)) if st else int(320 * max(s, .8))}px;line-height:.9;color:var(--accp)}}
.L-qa .wrap{{position:absolute;left:var(--m);right:var(--m);top:{720 if st else 330}px;bottom:{480 if st else 160}px;display:flex;flex-direction:column;justify-content:center;gap:{40 if st else 28}px}}
.L-qa .ans{{display:flex;gap:{28 if st else 22}px;align-items:flex-start;padding-top:{40 if st else 28}px;border-top:3px solid var(--linep)}}
.L-qa .a{{flex:none;font:800 {64 if st else 52}px/1 "Manrope";color:var(--accp);margin-top:-2px}}
.L-qa .lab{{position:absolute;right:var(--m);top:{300 if st else 90}px}}
.L-qa .pat{{background:{trade_pattern(b['motif'], b['vars']['line_p'], 1)};opacity:.5;-webkit-mask:linear-gradient(160deg,transparent 40%,#000);mask:linear-gradient(160deg,transparent 40%,#000)}}"""
    body = (f'<div class="pat"></div><div class="q">Q</div><div class="lab"><span class="label chip">{esc(p["label"])}</span></div>'
            f'<div class="wrap" data-box>{_hl(p["headline"], int((190 if st else 128) * s), 3)}<div class="ans"><span class="a">A.</span>'
            f'{_sub(p["sub"], 44 if st else 35, 5 if st else 4)}</div></div>{foot(b, fmt=fmt)}')
    return css, body, "light"


def lay_frame(p, b, fmt):
    st = fmt == "story"
    pw, ph = (800, 900) if st else (560, 640)
    top = 300 if st else 64
    css = f""".L-frame .pat{{background:{trade_pattern(b['motif'], b['vars']['line_p'], 1)};opacity:.65}}
.L-frame .pol{{position:absolute;left:50%;top:{top}px;width:{pw}px;height:{ph}px;margin-left:-{pw // 2}px;background:var(--card);border-radius:10px;
transform:rotate(-3.2deg);box-shadow:0 40px 70px -30px rgba(0,0,0,.45),0 2px 6px rgba(0,0,0,.08);padding:{34 if st else 26}px {34 if st else 26}px 0}}
.L-frame .ph{{position:relative;width:100%;height:{ph - (250 if st else 172)}px;background:var(--bg);overflow:hidden;display:flex;align-items:center;justify-content:center;border-radius:4px}}
.L-frame .ph .pt{{position:absolute;inset:0;background:{trade_pattern(b['motif'], b['vars']['line_d'], 1)};opacity:.8}}
.L-frame .ph .mono{{position:relative;font-family:var(--fa),serif;font-style:var(--fas);font-weight:var(--faw);font-size:{300 if st else 220}px;line-height:1;color:var(--accd)}}
.L-frame .ph .ic{{position:absolute;right:{28 if st else 22}px;bottom:{28 if st else 22}px;width:{110 if st else 80}px;height:{110 if st else 80}px;color:var(--ink);opacity:.85}}
.L-frame .cap{{font-family:var(--fh),cursive;font-weight:600;color:var(--pink);text-align:center;line-height:1;padding-top:{30 if st else 22}px}}
.L-frame .tape{{position:absolute;left:50%;top:-22px;width:{200 if st else 160}px;height:44px;margin-left:-{100 if st else 80}px;background:var(--acc);opacity:.75;transform:rotate(2deg)}}
.L-frame .wrap{{position:absolute;left:{120 if st else 96}px;right:{120 if st else 96}px;top:{top + ph + (120 if st else 44)}px;bottom:{500 if st else 140}px;display:flex;
flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:{26 if st else 16}px}}
.L-frame .wrap .label{{color:var(--accp)}}"""
    body = (f'<div class="pat"></div><div class="pol"><div class="tape"></div><div class="ph"><div class="pt"></div><div class="mono">{esc(b["initials"])}</div>'
            f'{icon(p["icon"], stroke=2.6)}</div><p class="cap" data-max="{(104 if st else 84) if len(p["headline"]) < 26 else (76 if st else 58)}" data-min="30" data-lines="{1 if len(p["headline"]) < 26 else 2}">{esc(p["headline"].replace("*", ""))}</p></div>'
            f'<div class="wrap" data-box><span class="label">{esc(p["label"])}</span>{_sub(p["sub"], 42 if st else 31, 3 if st else 2)}</div>{foot(b, fmt=fmt)}')
    return css, body, "light"


def lay_minimal(p, b, fmt):
    st = fmt == "story"
    s = _scale(b)
    css = f""".L-minimal .b1{{position:absolute;inset:{48 if st else 40}px;border:3px solid var(--accp);border-radius:4px}}
.L-minimal .b2{{position:absolute;inset:{64 if st else 54}px;border:1.5px solid var(--linep);border-radius:2px}}
.L-minimal .wrap{{position:absolute;left:{150 if st else 130}px;right:{150 if st else 130}px;top:{420 if st else 140}px;bottom:{560 if st else 190}px;display:flex;flex-direction:column;align-items:center;
justify-content:center;text-align:center;gap:{34 if st else 26}px}}
.L-minimal .ic.top{{width:{110 if st else 86}px;height:{110 if st else 86}px;color:var(--accp)}}
.L-minimal .label{{color:var(--pink2)}}
.L-minimal .foot{{justify-content:center;bottom:{250 if st else 92}px}}"""
    body = (f'<div class="b1"></div><div class="b2"></div><div class="wrap" data-box>{icon(p["icon"], "ic top", stroke=2.6)}<span class="label">{esc(p["label"])}</span>'
            f'{_hl(p["headline"], int((210 if st else 150) * s), 3)}<div class="rule"></div>{_sub(p["sub"], 42 if st else 33, 4 if st else 3)}</div>{foot(b, center=True, fmt=fmt)}')
    return css, body, "light"


LAYOUT_FN = {"bold": lay_bold, "split": lay_split, "tip": lay_tip, "quote": lay_quote, "offer": lay_offer, "holiday": lay_holiday,
             "date": lay_date, "checklist": lay_checklist, "qa": lay_qa, "frame": lay_frame, "minimal": lay_minimal}


def page(post: dict, brand: dict, fmt: str) -> str:
    """one self-contained HTML page for one image"""
    css, body, tone = LAYOUT_FN[post["layout"]](post, brand, fmt)
    fonts = font_faces({brand["fonts"]["display"], brand["fonts"]["accent"], "manrope", brand["fonts"].get("hand", "caveat")})
    cls = "light" if tone == "light" else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(post.get("headline", ""))}</title>'
            f'<style>{fonts}{base_css(brand, fmt)}{css}</style></head><body><div class="cv L-{post["layout"]} {fmt} {cls}">{body}'
            f'<div class="grain"></div></div><script>{FIT_JS}</script></body></html>')
