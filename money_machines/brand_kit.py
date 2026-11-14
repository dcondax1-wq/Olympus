"""BRAND KIT: a simple logo + brand kit made from code (SVG), for the "logo + brand kit" gig and the agency's clients.

    python -m money_machines.brand_kit --name "Bloom & Stem" --industry florist --out DIR        # 3 concepts + the whole kit of concept 1
    python -m money_machines.brand_kit --name "Peak Plumbing" --tagline "Fast, fair, local" --industry plumber --concept 2 --out DIR
    python -m money_machines.brand_kit --name "..." --mark leaf --palette sage --font serif --case upper --out DIR
    python -m money_machines.brand_kit --list                                                       # marks, palettes, industries
    python -m money_machines.brand_kit --selftest

What it writes (DIR): concepts.svg (the 3 concepts on one board, for the client to pick), concept_1..3.svg, and for the
chosen concept: logo_primary.svg (mark + name), logo_stacked.svg, logo_mark.svg, logo_wordmark.svg, logo_mono_dark.svg,
logo_mono_light.svg (reversed), favicon.svg, social_avatar.svg (1080 x 1080, circle-safe), social_banner.svg (1500 x 500),
business_card_front.svg / _back.svg (3.5 x 2 in at 300 dpi), palette.svg, brand.json (colours, fonts, contrast: the other
tools read it) and brand_guide.html (one page: every logo, the colours, the fonts, the rules). --png also renders PNG copies
of the avatar, favicon and banner with the pre-installed Chromium (optional; the SVGs are the real files).

Letters are vector paths from open-licence fonts (fonts/glyphs_*.json, SIL OFL 1.1: Inter and Caladea), so every SVG looks
the same on any computer and no font has to be installed. Stdlib only, no network, deterministic (same input = same files).
The owner checks the result before delivery (spelling, the client's colours, that it is not too close to a famous logo).
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import html
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
SVG_NS = "http://www.w3.org/2000/svg"
VERSION = "1.0"

# ------------------------------------------------------------------------------------------------ colours
# name: (primary, secondary, accent, ink, paper). Every palette passes: ink on paper >= 7:1, paper on primary >= 4.5:1.
PALETTES = {
    "agora": ("#7d5f25", "#9c6b3c", "#7f8a52", "#14110e", "#f3ece0"),
    "harbor": ("#1f3a5f", "#2a6f7f", "#e0a43a", "#14212e", "#f6f4ef"),
    "sage": ("#4a6656", "#6f8f7c", "#c98f86", "#1e2a24", "#f4f1ea"),
    "terracotta": ("#a8472f", "#7c3a2a", "#d9a441", "#2a1a14", "#faf3ea"),
    "spruce": ("#2f5d50", "#55824a", "#e7b53c", "#17231f", "#f5f3ec"),
    "slate": ("#34495e", "#566d82", "#e67e22", "#1b2631", "#f4f6f7"),
    "berry": ("#6d2e46", "#9a5a62", "#c9a227", "#2b1720", "#f8f1f1"),
    "ocean": ("#1b6496", "#2f8aa8", "#f2b134", "#102a3a", "#f3f8fb"),
    "ember": ("#a5352a", "#3a3a3a", "#f0a202", "#1a1a1a", "#f7f4f0"),
    "orchard": ("#5b4b8a", "#7a6aa8", "#e3a857", "#1f1a2e", "#f6f4fa"),
}
PALETTE_NOTES = {
    "agora": "warm classic: gold-brown, bronze, olive (the OLYMPUS look)", "harbor": "trust: navy and teal with a warm accent",
    "sage": "calm: sage green with a soft rose (health, wellness)", "terracotta": "warm: clay red with mustard (food, bakeries)",
    "spruce": "outdoors: deep green with sunflower (landscaping, gardens)", "slate": "pro: slate blue with safety orange (trades)",
    "berry": "beauty: plum and rose with gold", "ocean": "clean: ocean blue with sun yellow (cleaning, plumbing, pools)",
    "ember": "bold: brick red with charcoal (auto, heating)", "orchard": "friendly: violet with apricot (kids, creative, pets)",
}


def _rgb(hexc: str):
    h = hexc.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def luminance(hexc: str) -> float:
    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in _rgb(hexc))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def custom_palette(primary: str) -> tuple:
    """A palette from one brand colour (the client's): darker/lighter partners, a complementary accent, safe ink and paper."""
    r, g, b = _rgb(primary)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    prim = primary
    while contrast(prim, "#f7f5f0") < 4.5 and l > 0.05:       # dark enough for paper-coloured text on it
        l -= 0.04
        prim = _hex(colorsys.hls_to_rgb(h, l, s))
    sec = _hex(colorsys.hls_to_rgb(h, min(0.62, l + 0.16), max(0.2, s * 0.8)))
    acc = _hex(colorsys.hls_to_rgb((h + 0.5) % 1, 0.58, min(0.75, max(0.45, s))))
    ink = _hex(colorsys.hls_to_rgb(h, 0.11, min(0.35, s)))
    paper = _hex(colorsys.hls_to_rgb(h, 0.965, min(0.3, s)))
    return (prim, sec, acc, ink, paper)


# ------------------------------------------------------------------------------------------------ letters as paths
_FONTS: dict = {}


def font(kind: str) -> dict:
    if kind not in _FONTS:
        with open(os.path.join(FONT_DIR, f"glyphs_{kind}.json"), encoding="utf-8") as fh:
            _FONTS[kind] = json.load(fh)
    return _FONTS[kind]


def _glyph(f: dict, ch: str):
    g = f["glyphs"].get(ch)
    if g is None:
        base = unicodedata.normalize("NFKD", ch)[:1]
        g = f["glyphs"].get(base) or f["glyphs"]["?"]
    return g


def measure(text: str, kind: str, size: float, tracking: float = 0.0) -> float:
    """Width in px of `text` at `size` px (font size = 1 em), tracking in em."""
    f = font(kind)
    k = size / f["upm"]
    w = 0.0
    for i, ch in enumerate(text):
        w += _glyph(f, ch)[0] + f["kern"].get(text[i:i + 2], 0)
        if i < len(text) - 1:
            w += tracking * f["upm"]
    return w * k


def text_paths(text: str, kind: str, size: float, x: float, y: float, fill: str, tracking: float = 0.0) -> str:
    """The text as one <g> of glyph paths, baseline at y, starting at x."""
    f = font(kind)
    k = size / f["upm"]
    parts, pen = [], 0.0
    for i, ch in enumerate(text):
        adv, d = _glyph(f, ch)
        if d:
            parts.append(f'<path transform="translate({_n(x + pen * k)} {_n(y)}) scale({_n(k, 5)})" d="{d}"/>')
        pen += adv + f["kern"].get(text[i:i + 2], 0) + (tracking * f["upm"] if i < len(text) - 1 else 0)
    return f'<g fill="{fill}">' + "".join(parts) + "</g>"


def cap_height(kind: str, size: float) -> float:
    f = font(kind)
    return f["cap"] * size / f["upm"]


def _n(v: float, nd: int = 2) -> str:
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ------------------------------------------------------------------------------------------------ marks (100 x 100 box)
def _mark_drop(c, bg):
    return (f'<path fill="{c}" d="M50 14C50 14 24 45 24 62A26 26 0 0 0 76 62C76 45 50 14 50 14Z"/>'
            f'<path fill="none" stroke="{bg}" stroke-width="5" stroke-linecap="round" d="M38 63A12 12 0 0 0 49 75"/>')


def _mark_flame(c, bg):
    return (f'<path fill="{c}" d="M53 12C58 30 74 38 74 60A24 24 0 0 1 26 60C26 47 33 39 38 31C40 41 44 46 49 48C53 37 51 25 53 12Z"/>'
            f'<path fill="{bg}" d="M50 54C53 61 60 63 60 71A10 10 0 0 1 40 71C40 65 45 61 50 54Z"/>')


def _mark_bolt(c, bg):
    return f'<path fill="{c}" d="M58 10 26 56H47L41 90 74 42H53L58 10Z"/>'


def _mark_house(c, bg):
    return (f'<path fill="{c}" fill-rule="evenodd" d="M50 14 12 46H24V84H76V46H88L50 14ZM43 84V62H57V84H43Z"/>'
            f'<rect fill="{c}" x="64" y="18" width="8" height="18"/>')


def _mark_roof(c, bg):
    return (f'<path fill="none" stroke="{c}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round" d="M14 54 50 24 86 54"/>'
            f'<path fill="none" stroke="{c}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round" d="M28 72 50 54 72 72"/>')


def _mark_leaf(c, bg):
    return (f'<path fill="{c}" d="M22 80C20 44 42 22 82 18C84 58 62 80 26 82Z"/>'
            f'<path fill="none" stroke="{bg}" stroke-width="4.5" stroke-linecap="round" d="M30 74C44 58 56 46 70 32"/>')


def _mark_flower(c, bg):
    petals = "".join(f'<ellipse fill="{c}" cx="50" cy="29" rx="12" ry="17" transform="rotate({a} 50 50)"/>' for a in range(0, 360, 72))
    return petals + f'<circle fill="{bg}" cx="50" cy="50" r="9"/>'


def _mark_sparkle(c, bg):
    return (f'<path fill="{c}" d="M46 12C49 36 57 45 82 48C57 51 49 60 46 86C43 60 35 51 10 48C35 45 43 36 46 12Z"/>'
            f'<path fill="{c}" d="M76 12C77 20 80 23 88 24C80 25 77 28 76 36C75 28 72 25 64 24C72 23 75 20 76 12Z"/>')


def _mark_paw(c, bg):
    toes = "".join(f'<ellipse fill="{c}" cx="{x}" cy="{y}" rx="8.5" ry="11" transform="rotate({r} {x} {y})"/>'
                   for x, y, r in ((24, 44, -20), (39, 28, -6), (61, 28, 6), (76, 44, 20)))
    return toes + f'<path fill="{c}" d="M50 48C62 48 76 62 76 74C76 84 66 86 58 82C54 80 46 80 42 82C34 86 24 84 24 74C24 62 38 48 50 48Z"/>'


def _mark_gear(c, bg):
    teeth, n = [], 8
    for i in range(n):
        a = i * 2 * math.pi / n
        for da, r in ((-0.2, 30), (-0.13, 40), (0.13, 40), (0.2, 30)):
            teeth.append((50 + r * math.cos(a + da), 50 + r * math.sin(a + da)))
    d = "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in teeth) + "Z"
    return f'<path fill="{c}" fill-rule="evenodd" d="{d}M50 37A13 13 0 1 0 50 63A13 13 0 1 0 50 37Z"/>'


def _mark_tooth(c, bg):
    return (f'<path fill="{c}" d="M34 18C22 18 17 30 20 44C22 56 29 61 31 76C32 86 41 88 43 79L47 62C48 57 52 57 53 62L57 79C59 88 68 86 69 76'
            f'C71 61 78 56 80 44C83 30 78 18 66 18C58 18 56 23 50 23C44 23 42 18 34 18Z"/>')


def _mark_heart(c, bg):
    return f'<path fill="{c}" d="M50 84C20 64 12 46 20 32C28 18 45 21 50 35C55 21 72 18 80 32C88 46 80 64 50 84Z"/>'


def _mark_plus(c, bg):
    return f'<path fill="{c}" d="M40 14H60V40H86V60H60V86H40V60H14V40H40Z"/>'


def _mark_cup(c, bg):
    return (f'<path fill="{c}" d="M18 40H70V58C70 72 60 82 46 82H42C28 82 18 72 18 58Z"/>'
            f'<path fill="none" stroke="{c}" stroke-width="7" d="M69 46H74A9 9 0 0 1 74 64H68"/>'
            f'<path fill="none" stroke="{c}" stroke-width="5" stroke-linecap="round" d="M34 30C30 24 38 20 34 14M48 30C44 24 52 20 48 14"/>')


def _mark_key(c, bg):
    return (f'<path fill="{c}" fill-rule="evenodd" d="M30 26A20 20 0 1 1 30 66A20 20 0 1 1 30 26ZM30 38A8 8 0 1 0 30 54A8 8 0 1 0 30 38Z"/>'
            f'<path fill="{c}" d="M48 42H90V52H84V64H75V52H68V60H59V52H48Z"/>')


def _mark_scissors(c, bg):
    return (f'<g fill="none" stroke="{c}" stroke-width="7"><circle cx="28" cy="70" r="11"/><circle cx="72" cy="70" r="11"/></g>'
            f'<path fill="{c}" d="M35 60 68 12 74 16 45 66ZM65 60 32 12 26 16 55 66Z"/>')


def _mark_dumbbell(c, bg):
    return (f'<rect fill="{c}" x="12" y="34" width="12" height="32" rx="3"/><rect fill="{c}" x="24" y="26" width="12" height="48" rx="3"/>'
            f'<rect fill="{c}" x="36" y="45" width="28" height="10"/><rect fill="{c}" x="64" y="26" width="12" height="48" rx="3"/>'
            f'<rect fill="{c}" x="76" y="34" width="12" height="32" rx="3"/>')


def _mark_bowl(c, bg):
    return (f'<path fill="{c}" d="M14 48H86C86 68 70 82 50 82C30 82 14 68 14 48Z"/>'
            f'<path fill="none" stroke="{c}" stroke-width="5" stroke-linecap="round" d="M36 38C32 32 40 28 36 22M50 38C46 32 54 28 50 22M64 38C60 32 68 28 64 22"/>')


def _mark_brush(c, bg):
    return (f'<path fill="{c}" d="M60 12 88 40 58 54 46 42Z"/>'
            f'<path fill="{c}" d="M42 46 54 58C50 72 38 86 16 86C22 78 20 66 28 58C32 54 37 50 42 46Z"/>')


def _mark_column(c, bg):
    flutes = "".join(f'<rect fill="{bg}" x="{x}" y="34" width="3" height="40"/>' for x in (37, 45.5, 54, 62.5))
    return (f'<path fill="{c}" d="M20 18H80V26H74V30H26V26H20Z"/><rect fill="{c}" x="30" y="32" width="40" height="44"/>{flutes}'
            f'<path fill="{c}" d="M26 78H74V82H80V88H20V82H26Z"/>')


def _mark_wave(c, bg):
    return (f'<path fill="none" stroke="{c}" stroke-width="8" stroke-linecap="round" d="M12 42C22 32 32 32 42 42S62 52 72 42 86 34 90 38"/>'
            f'<path fill="none" stroke="{c}" stroke-width="8" stroke-linecap="round" d="M12 64C22 54 32 54 42 64S62 74 72 64 86 56 90 60"/>')


def _mark_sun(c, bg):
    rays = "".join(f'<rect fill="{c}" x="47" y="8" width="6" height="14" rx="3" transform="rotate({a} 50 50)"/>' for a in range(0, 360, 45))
    return rays + f'<circle fill="{c}" cx="50" cy="50" r="20"/>'


def _mark_mountain(c, bg):
    return (f'<path fill="{c}" d="M8 82 38 30 54 56 64 42 92 82Z"/>'
            f'<path fill="{bg}" d="M38 30 46 44 40 42 34 47 30 44Z"/><circle fill="{c}" cx="74" cy="22" r="8"/>')


MARKS = {
    "drop": ("Water drop", _mark_drop), "flame": ("Flame", _mark_flame), "bolt": ("Lightning bolt", _mark_bolt),
    "house": ("House", _mark_house), "roof": ("Roof lines", _mark_roof), "leaf": ("Leaf", _mark_leaf), "flower": ("Flower", _mark_flower),
    "sparkle": ("Sparkle", _mark_sparkle), "paw": ("Paw", _mark_paw), "gear": ("Gear", _mark_gear), "tooth": ("Tooth", _mark_tooth),
    "heart": ("Heart", _mark_heart), "plus": ("Health cross", _mark_plus), "cup": ("Coffee cup", _mark_cup), "key": ("Key", _mark_key),
    "scissors": ("Scissors", _mark_scissors), "dumbbell": ("Dumbbell", _mark_dumbbell), "bowl": ("Bowl", _mark_bowl),
    "brush": ("Paint brush", _mark_brush), "column": ("Column", _mark_column), "wave": ("Waves", _mark_wave), "sun": ("Sun", _mark_sun),
    "mountain": ("Mountain", _mark_mountain),
}

# containers around a mark (100 x 100 box); "none" = the mark alone
CONTAINERS = {
    "circle": lambda c: f'<circle fill="{c}" cx="50" cy="50" r="50"/>',
    "rounded": lambda c: f'<rect fill="{c}" x="0" y="0" width="100" height="100" rx="24"/>',
    "shield": lambda c: f'<path fill="{c}" d="M50 0 96 14V48C96 74 76 92 50 100C24 92 4 74 4 48V14Z"/>',
    "hexagon": lambda c: f'<path fill="{c}" d="M50 0 93.3 25V75L50 100 6.7 75V25Z"/>',
    "arch": lambda c: f'<path fill="{c}" d="M0 100V46A50 46 0 0 1 100 46V100Z"/>',
    "none": lambda c: "",
}

# B1's lead categories (agency/categories.py) -> mark, palette, font. "generic" for anything else.
INDUSTRIES = {
    "plumber": ("drop", "ocean", "sans"), "hvac": ("flame", "ember", "sans"), "electrician": ("bolt", "slate", "sans"),
    "roofer": ("roof", "slate", "sans"), "painter": ("brush", "orchard", "sans"), "builder": ("house", "slate", "sans"),
    "locksmith": ("key", "harbor", "sans"), "landscaper": ("leaf", "spruce", "sans"), "cleaner": ("sparkle", "ocean", "sans"),
    "florist": ("flower", "berry", "serif"), "pet_grooming": ("paw", "orchard", "sans"), "auto_repair": ("gear", "ember", "sans"),
    "car_wash": ("drop", "ocean", "sans"), "dentist": ("tooth", "harbor", "sans"), "chiropractor": ("plus", "sage", "sans"),
    "physio": ("plus", "sage", "sans"), "vet": ("paw", "sage", "sans"), "massage": ("leaf", "sage", "serif"), "gym": ("dumbbell", "ember", "sans"),
    "restaurant": ("bowl", "terracotta", "serif"), "cafe": ("cup", "terracotta", "serif"), "bakery": ("sun", "terracotta", "serif"),
    "barber": ("scissors", "slate", "serif"), "salon": ("scissors", "berry", "serif"), "beauty": ("sparkle", "berry", "serif"),
    "tattoo": ("sparkle", "ember", "serif"), "outdoors": ("mountain", "spruce", "sans"), "pool": ("wave", "ocean", "sans"),
    "law": ("column", "agora", "serif"), "finance": ("column", "harbor", "serif"), "health": ("heart", "sage", "sans"),
    "generic": ("monogram", "harbor", "sans"),
}
ALIASES = {"plumbing": "plumber", "heating": "hvac", "ac": "hvac", "electrical": "electrician", "roofing": "roofer", "painting": "painter",
           "contractor": "builder", "handyman": "builder", "landscaping": "landscaper", "lawn": "landscaper", "cleaning": "cleaner",
           "maid": "cleaner", "flowers": "florist", "grooming": "pet_grooming", "pets": "pet_grooming", "mechanic": "auto_repair",
           "auto": "auto_repair", "dental": "dentist", "chiro": "chiropractor", "physical therapy": "physio", "veterinary": "vet",
           "fitness": "gym", "food": "restaurant", "coffee": "cafe", "hair": "salon", "nails": "beauty", "spa": "massage",
           "lawyer": "law", "accountant": "finance", "insurance": "finance", "bookkeeping": "finance"}

FONT_INFO = {
    "sans": {"logo": "Inter Bold", "web_heading": "Inter (Google Fonts, free)", "web_body": "Inter (Google Fonts, free)"},
    "serif": {"logo": "Caladea Bold", "web_heading": "Caladea (Google Fonts, free)", "web_body": "Inter (Google Fonts, free)"},
}


def industry_key(s: str) -> str:
    k = (s or "generic").strip().lower().replace("-", "_")
    k = ALIASES.get(k, k)
    return k if k in INDUSTRIES else "generic"


def initials(name: str) -> str:
    words = [w for w in re.split(r"[\s\-&/+.]+", name) if w and w[0].isalnum()]
    skip = {"and", "the", "of", "llc", "inc", "co"}
    core = [w for w in words if w.lower() not in skip] or words or ["X"]
    return (core[0][0] + (core[1][0] if len(core) > 1 else "")).upper()


# ------------------------------------------------------------------------------------------------ pieces
def _svg(w: float, h: float, body: str, title: str, bg: str = "") -> str:
    rect = f'<rect width="{_n(w)}" height="{_n(h)}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="{SVG_NS}" width="{_n(w)}" height="{_n(h)}" viewBox="0 0 {_n(w)} {_n(h)}" role="img">'
            f"<title>{html.escape(title)}</title>{rect}{body}</svg>\n")


def emblem(spec: dict, size: float, x: float, y: float, colors: dict, mono: str = "") -> str:
    """The mark in its container, `size` px square, top-left at (x, y)."""
    box, fill_c, mark_c = spec["container"], colors["primary"], colors["paper"]
    if mono:
        fill_c = mono
        mark_c = colors["paper"] if mono != colors["paper"] else colors["ink"]
    if box == "none":
        mark_c, fill_c = (mono or colors["primary"]), ""
    inner = CONTAINERS[box](fill_c) if box != "none" else ""
    if spec["mark"] == "monogram":
        ini = spec["initials"]
        fs = 46 if len(ini) == 2 else 58
        w = measure(ini, spec["font"], fs, 0.02)
        ch = cap_height(spec["font"], fs)
        cy = 54 if box == "arch" else 50
        glyph = text_paths(ini, spec["font"], fs, 50 - w / 2, cy + ch / 2, mark_c, 0.02)
    else:
        bgc = fill_c or colors["paper"]
        scale = 0.66 if box != "none" else 1.0
        off = (100 - 100 * scale) / 2 + (5 if box == "arch" else 0)
        glyph = f'<g transform="translate({_n(off)} {_n(off)}) scale({scale})">{MARKS[spec["mark"]][1](mark_c, bgc)}</g>'
    return f'<g transform="translate({_n(x)} {_n(y)}) scale({_n(size / 100, 4)})">{inner}{glyph}</g>'


def wordmark(spec: dict, size: float, x: float, baseline: float, color: str, tag_color: str, align: str = "left"):
    """Name (+ tagline under it). Returns (svg, width, tagline baseline or None)."""
    name = spec["display"]
    tr = 0.08 if spec["case"] == "upper" else 0.0
    w = measure(name, spec["font"], size, tr)
    tag, tag_w, tag_base = "", 0.0, None
    if spec["tagline"]:
        ts = size * 0.34
        tag_w = measure(spec["tagline"], "text", ts, 0.01)
        tag_base = baseline + size * 0.62
    width = max(w, tag_w)
    x0 = x if align == "left" else x - width / 2
    nx = x0 if align == "left" else x - w / 2
    out = text_paths(name, spec["font"], size, nx, baseline, color, tr)
    if spec["tagline"]:
        tx = x0 if align == "left" else x - tag_w / 2
        tag = text_paths(spec["tagline"], "text", size * 0.34, tx, tag_base, tag_color, 0.01)
    return out + tag, width, tag_base


def make_spec(name, tagline="", industry="generic", mark=None, palette=None, font_kind=None, container=None, case=None,
              primary=None, concept=1) -> dict:
    ind = industry_key(industry)
    d_mark, d_pal, d_font = INDUSTRIES[ind]
    seed = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16)
    pals = list(PALETTES)
    alt_pal = [p for p in pals if p != d_pal]
    if concept == 1:
        c_mark, c_pal, c_font, c_box = d_mark, d_pal, d_font, "circle" if d_mark != "monogram" else "rounded"
    elif concept == 2:
        c_mark, c_pal, c_font, c_box = "monogram", alt_pal[seed % len(alt_pal)], "serif" if d_font == "sans" else "sans", "rounded"
    else:
        c_mark = d_mark if d_mark != "monogram" else "column"
        c_pal, c_font, c_box = alt_pal[(seed // 7) % len(alt_pal)], d_font, "none"
    c_mark = mark or c_mark
    c_pal = palette or c_pal
    c_font = font_kind or c_font
    c_box = container or c_box
    if c_mark != "monogram" and c_mark not in MARKS:
        raise ValueError(f"unknown mark {c_mark!r}; one of: monogram, " + ", ".join(MARKS))
    if c_box not in CONTAINERS:
        raise ValueError(f"unknown container {c_box!r}; one of: " + ", ".join(CONTAINERS))
    if c_font not in FONT_INFO:
        raise ValueError("font must be sans or serif")
    if primary:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", primary):
            raise ValueError("--primary must look like #1f3a5f")
        cols = custom_palette(primary.lower())
        c_pal = "custom"
    else:
        if c_pal not in PALETTES:
            raise ValueError(f"unknown palette {c_pal!r}; one of: " + ", ".join(PALETTES))
        cols = PALETTES[c_pal]
    c_case = case or ("upper" if c_font == "sans" and len(name) <= 16 else "title")
    display = name.upper() if c_case == "upper" else name
    return {"name": name, "display": display, "tagline": tagline.strip(), "industry": ind, "mark": c_mark, "container": c_box,
            "font": c_font, "case": c_case, "palette": c_pal, "initials": initials(name), "concept": concept,
            "colors": dict(zip(("primary", "secondary", "accent", "ink", "paper"), cols))}


# ------------------------------------------------------------------------------------------------ the files
def logo_primary(spec, mono="", bg=""):
    c = spec["colors"]
    ink = mono or c["ink"]
    tag_c = mono or c["secondary"]
    h, em = 160, 120
    fs = 64 if len(spec["display"]) <= 14 else 52
    ch = cap_height(spec["font"], fs)
    has_tag = bool(spec["tagline"])
    base = h / 2 + ch / 2 - (fs * 0.2 if has_tag else 0)
    body_mark = emblem(spec, em, 20, (h - em) / 2, c, mono)
    words, w, _ = wordmark(spec, fs, 20 + em + 28, base, ink, tag_c)
    width = 20 + em + 28 + w + 24
    return _svg(width, h, body_mark + words, f'{spec["name"]} logo', bg)


def logo_stacked(spec, mono="", bg=""):
    c = spec["colors"]
    fs = 64 if len(spec["display"]) <= 14 else 50
    w_name = measure(spec["display"], spec["font"], fs, 0.08 if spec["case"] == "upper" else 0)
    w_tag = measure(spec["tagline"], "text", fs * 0.34, 0.01) if spec["tagline"] else 0
    width = max(300, w_name, w_tag) + 48
    em = 150
    base = 24 + em + 30 + cap_height(spec["font"], fs)
    words, _, tag_base = wordmark(spec, fs, width / 2, base, mono or c["ink"], mono or c["secondary"], align="center")
    height = (tag_base or base) + 32
    return _svg(width, height, emblem(spec, em, (width - em) / 2, 24, c, mono) + words, f'{spec["name"]} logo (stacked)', bg)


def logo_mark(spec, size=512, mono="", bg=""):
    pad = size * 0.06
    return _svg(size, size, emblem(spec, size - 2 * pad, pad, pad, spec["colors"], mono), f'{spec["name"]} mark', bg)


def logo_wordmark(spec, mono="", bg=""):
    c = spec["colors"]
    fs = 72
    ch = cap_height(spec["font"], fs)
    words, w, tag_base = wordmark(spec, fs, 24, 24 + ch, mono or c["ink"], mono or c["secondary"])
    return _svg(w + 48, (tag_base or 24 + ch) + 28, words, f'{spec["name"]} wordmark', bg)


def favicon(spec):
    c = spec["colors"]
    s = dict(spec)
    if s["container"] == "none":
        s["container"] = "rounded"
    return _svg(64, 64, emblem(s, 64, 0, 0, c), f'{spec["name"]} favicon')


def social_avatar(spec):
    c = spec["colors"]
    s = dict(spec, container="none")
    size = 1080
    em = 560
    body = f'<circle cx="540" cy="540" r="540" fill="{c["primary"]}"/>' + emblem(s, em, (size - em) / 2, (size - em) / 2, c, mono=c["paper"])
    return _svg(size, size, body, f'{spec["name"]} profile picture', c["primary"])


def social_banner(spec):
    c = spec["colors"]
    w, h = 1500, 500
    em = 220
    fs = 92 if len(spec["display"]) <= 14 else 72
    ch = cap_height(spec["font"], fs)
    words, ww, _ = wordmark(spec, fs, 0, 0, c["ink"], c["secondary"])
    total = em + 48 + ww
    x0 = (w - total) / 2
    base = h / 2 + ch / 2 - (fs * 0.2 if spec["tagline"] else 0)
    words, _, _ = wordmark(spec, fs, x0 + em + 48, base, c["ink"], c["secondary"])
    stripe = f'<rect x="0" y="{h - 18}" width="{w}" height="18" fill="{c["primary"]}"/><rect x="0" y="{h - 26}" width="{w}" height="8" fill="{c["accent"]}"/>'
    return _svg(w, h, emblem(spec, em, x0, (h - em) / 2, c) + words + stripe, f'{spec["name"]} banner', c["paper"])


def business_card(spec, side, contact):
    c = spec["colors"]
    w, h = 1050, 600
    if side == "front":
        s = dict(spec)
        em = 200
        fs = 58 if len(spec["display"]) <= 14 else 46
        words, ww, tag_base = wordmark(s, fs, w / 2, 0, c["paper"], c["paper"], align="center")
        base = (h - em) / 2 + em + 48 + cap_height(spec["font"], fs) - 50
        words, ww, tag_base = wordmark(s, fs, w / 2, base, c["paper"], c["paper"], align="center")
        mark = emblem(dict(s, container="none"), em, (w - em) / 2, (h - em) / 2 - 70, c, mono=c["paper"])
        return _svg(w, h, mark + words, f'{spec["name"]} business card (front)', c["primary"])
    lines = [x for x in (contact.get("person"), contact.get("phone"), contact.get("email"), contact.get("website"), contact.get("address")) if x]
    if not lines:
        lines = ["Your Name", "(555) 555-0100", "hello@example.com", "example.com"]
    rows, y = [], 250
    for i, ln in enumerate(lines[:5]):
        fs = 44 if i == 0 else 32
        rows.append(text_paths(ln, "sans" if i == 0 else "text", fs, 96, y, c["ink"] if i == 0 else c["secondary"]))
        y += 70 if i == 0 else 56
    em = 150
    body = (emblem(spec, em, w - em - 80, 80, c) + "".join(rows) +
            f'<rect x="0" y="0" width="28" height="{h}" fill="{c["primary"]}"/><rect x="28" y="0" width="10" height="{h}" fill="{c["accent"]}"/>')
    return _svg(w, h, body, f'{spec["name"]} business card (back)', c["paper"])


def palette_board(spec):
    c = spec["colors"]
    names = ("primary", "secondary", "accent", "ink", "paper")
    w, h, sw = 1200, 420, 220
    parts = []
    for i, k in enumerate(names):
        x = 20 + i * (sw + 15)
        txt = c["paper"] if contrast(c[k], c["paper"]) >= contrast(c[k], c["ink"]) else c["ink"]
        parts.append(f'<rect x="{x}" y="20" width="{sw}" height="260" rx="18" fill="{c[k]}" stroke="#00000022"/>')
        parts.append(text_paths(k.capitalize(), "sans", 30, x + 18, 70, txt))
        parts.append(text_paths(c[k].upper(), "text", 26, x + 18, 250, txt))
        r, g, b = (round(v * 255) for v in _rgb(c[k]))
        parts.append(text_paths(f"RGB {r} {g} {b}", "text", 22, x + 18, 320, c["ink"]))
    parts.append(text_paths(f'Text on paper: {contrast(c["ink"], c["paper"])}:1   White on primary: {contrast("#ffffff", c["primary"])}:1',
                            "text", 24, 20, 385, c["ink"]))
    return _svg(w, h, "".join(parts), f'{spec["name"]} colours', "#ffffff")


def concepts_board(specs):
    w, row = 1400, 260
    parts = []
    for i, s in enumerate(specs):
        y = 30 + i * row
        parts.append(f'<rect x="20" y="{y - 10}" width="{w - 40}" height="{row - 20}" rx="22" fill="{s["colors"]["paper"]}" stroke="#d9d3c7"/>')
        parts.append(text_paths(f"Concept {s['concept']}", "text", 26, 50, y + 36, "#6b6256"))
        em = 150
        parts.append(emblem(s, em, 50, y + 60, s["colors"]))
        fs = 56 if len(s["display"]) <= 14 else 46
        ch = cap_height(s["font"], fs)
        words, _, _ = wordmark(s, fs, 50 + em + 32, y + 60 + em / 2 + ch / 2 - (fs * 0.2 if s["tagline"] else 0), s["colors"]["ink"], s["colors"]["secondary"])
        parts.append(words)
        sx = w - 40 - 5 * 54
        for j, k in enumerate(("primary", "secondary", "accent", "ink", "paper")):
            parts.append(f'<rect x="{sx + j * 54}" y="{y + 30}" width="44" height="44" rx="10" fill="{s["colors"][k]}" stroke="#00000022"/>')
        parts.append(text_paths(f'{MARKS[s["mark"]][0] if s["mark"] != "monogram" else "Monogram"} / {s["container"]} / {s["palette"]} / {s["font"]}',
                                "text", 22, sx - 10 - measure(f'{MARKS[s["mark"]][0] if s["mark"] != "monogram" else "Monogram"} / {s["container"]} / {s["palette"]} / {s["font"]}', "text", 22) + 5 * 54 + 10,
                                y + 108, "#6b6256"))
    return _svg(w, 30 + len(specs) * row, "".join(parts), "Logo concepts", "#ffffff")


def brand_json(spec) -> dict:
    c = spec["colors"]
    return {"v": 1, "kind": "brand-kit", "tool": f"money_machines.brand_kit {VERSION}", "name": spec["name"], "tagline": spec["tagline"],
            "industry": spec["industry"], "concept": spec["concept"],
            "logo": {"mark": spec["mark"], "container": spec["container"], "font": FONT_INFO[spec["font"]]["logo"], "case": spec["case"],
                     "letters": "vector paths (no font needed)"},
            "colors": c, "palette": spec["palette"],
            "fonts": {"heading": FONT_INFO[spec["font"]]["web_heading"], "body": FONT_INFO[spec["font"]]["web_body"]},
            "contrast": {"ink_on_paper": contrast(c["ink"], c["paper"]), "paper_on_primary": contrast(c["paper"], c["primary"]),
                         "white_on_primary": contrast("#ffffff", c["primary"]), "primary_on_paper": contrast(c["primary"], c["paper"])},
            "rules": ["Keep clear space around the logo equal to the height of the mark's inner symbol (at least 1/4 of the mark).",
                      "Smallest size: mark 24 px on screen / 10 mm in print; full logo 120 px wide / 30 mm.",
                      "Use the dark logo on light backgrounds and the light logo on dark or photo backgrounds.",
                      "Do not stretch, rotate, recolour outside the palette, or add shadows or outlines."]}


GUIDE_CSS = ("body{margin:0;font-family:-apple-system,'Segoe UI',Inter,system-ui,sans-serif;background:#f4f1ea;color:#1c1a17}"
             "main{max-width:980px;margin:0 auto;padding:24px 16px 80px}h1{font-family:Georgia,'Palatino Linotype',serif;font-size:2rem;margin:.2em 0}"
             "h2{font-family:Georgia,'Palatino Linotype',serif;font-size:1.3rem;margin:1.6em 0 .5em;border-bottom:2px solid #c8a24a;padding-bottom:4px}"
             ".card{background:#fff;border-radius:16px;padding:16px;margin:10px 0;box-shadow:0 2px 10px rgba(0,0,0,.08)}"
             ".card.dark{background:var(--ink)}img,svg{max-width:100%;height:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}"
             "table{border-collapse:collapse;width:100%}td,th{padding:6px 8px;border-bottom:1px solid #e3ddd1;text-align:left;font-variant-numeric:tabular-nums}"
             ".sw{display:inline-block;width:18px;height:18px;border-radius:5px;vertical-align:middle;margin-right:6px;border:1px solid #0002}"
             "small{color:#6b6256}")


def guide_html(spec, files: dict) -> str:
    c = spec["colors"]
    b = brand_json(spec)
    rows = "".join(f'<tr><td><span class="sw" style="background:{v}"></span>{k.capitalize()}</td><td>{v.upper()}</td>'
                   f'<td>{" ".join(str(round(x * 255)) for x in _rgb(v))}</td></tr>' for k, v in c.items())
    cons = "".join(f"<tr><td>{k.replace('_', ' ')}</td><td>{v}:1</td><td>{'passes AA text (4.5:1)' if v >= 4.5 else ('large text / graphics only (3:1)' if v >= 3 else 'decoration only')}</td></tr>"
                   for k, v in b["contrast"].items())
    rules = "".join(f"<li>{html.escape(r)}</li>" for r in b["rules"])

    def emb(key, dark=False):
        return f'<div class="card{" dark" if dark else ""}">{files[key]}<br><small>{html.escape(key)}.svg</small></div>'

    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(spec['name'])} brand guide</title><style>:root{{--ink:{c['ink']}}}{GUIDE_CSS}</style></head><body><main>"
            f"<h1>{html.escape(spec['name'])}</h1><p>{html.escape(spec['tagline'] or 'Brand guide')}</p>"
            f"<h2>Logo</h2>{emb('logo_primary')}<div class=\"grid\">{emb('logo_stacked')}{emb('logo_mark')}{emb('logo_wordmark')}</div>"
            f"<div class=\"grid\">{emb('logo_mono_dark')}{emb('logo_mono_light', dark=True)}</div>"
            f"<h2>Colours</h2><div class=\"card\"><table><tr><th>Colour</th><th>Hex</th><th>RGB</th></tr>{rows}</table></div>"
            f"<div class=\"card\"><table><tr><th>Pair</th><th>Contrast</th><th>Use</th></tr>{cons}</table></div>"
            f"<h2>Fonts</h2><div class=\"card\"><p>Logo letters: {html.escape(b['logo']['font'])}, drawn as shapes (no font needed to open the files).</p>"
            f"<p>Website headings: {html.escape(b['fonts']['heading'])}. Body text: {html.escape(b['fonts']['body'])}.</p></div>"
            f"<h2>Use it well</h2><div class=\"card\"><ul>{rules}</ul></div>"
            f"<h2>Social and print</h2><div class=\"grid\">{emb('social_avatar')}{emb('favicon')}</div>{emb('social_banner')}"
            f"<div class=\"grid\">{emb('business_card_front')}{emb('business_card_back')}</div>"
            "<p><small>Made with simple, original shapes. Check that the name is free to use in your area (a quick search of your state's business"
            " register and the USPTO trademark search) before printing.</small></p></main></body></html>\n")


def build(spec: dict, out: str, contact=None, concepts=None, png=False) -> dict:
    os.makedirs(out, exist_ok=True)
    c = spec["colors"]
    files = {
        "logo_primary": logo_primary(spec), "logo_stacked": logo_stacked(spec), "logo_mark": logo_mark(spec),
        "logo_wordmark": logo_wordmark(spec), "logo_mono_dark": logo_primary(spec, mono=c["ink"]),
        "logo_mono_light": logo_primary(spec, mono=c["paper"], bg=c["ink"]), "favicon": favicon(spec),
        "social_avatar": social_avatar(spec), "social_banner": social_banner(spec),
        "business_card_front": business_card(spec, "front", contact or {}), "business_card_back": business_card(spec, "back", contact or {}),
        "palette": palette_board(spec),
    }
    if concepts:
        files["concepts"] = concepts_board(concepts)
        for s in concepts:
            files[f"concept_{s['concept']}"] = logo_primary(s)
    written = []
    for k, v in files.items():
        p = os.path.join(out, k + ".svg")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(v)
        written.append(p)
    with open(os.path.join(out, "brand.json"), "w", encoding="utf-8") as fh:
        json.dump(brand_json(spec), fh, indent=1)
    with open(os.path.join(out, "brand_guide.html"), "w", encoding="utf-8") as fh:
        fh.write(guide_html(spec, files))
    written += [os.path.join(out, "brand.json"), os.path.join(out, "brand_guide.html")]
    if png:
        written += render_png(out, (("social_avatar", 1080, 1080), ("favicon", 64, 64), ("social_banner", 1500, 500), ("logo_mark", 512, 512)))
    return {"out": out, "files": written, "spec": spec}


def render_png(out: str, items) -> list:
    """PNG copies with the pre-installed Chromium (optional). Returns the files written; [] without a browser."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (no PNGs: playwright is not installed; the SVG files are complete)")
        return []
    import glob
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    done = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        pg = br.new_page()
        for key, w, h in items:
            svg = open(os.path.join(out, key + ".svg"), encoding="utf-8").read()
            pg.set_viewport_size({"width": w, "height": h})
            pg.set_content(f"<html><body style='margin:0;background:transparent'>{svg}</body></html>")
            p = os.path.join(out, key + ".png")
            pg.locator("svg").first.screenshot(path=p, omit_background=True)
            done.append(p)
        br.close()
    return done


def kit(name, out, tagline="", industry="generic", concept=1, png=False, contact=None, **over) -> dict:
    concepts = [make_spec(name, tagline, industry, concept=i, **{k: v for k, v in over.items() if v and i == concept}) for i in (1, 2, 3)]
    chosen = concepts[concept - 1]
    return build(chosen, out, contact=contact, concepts=concepts, png=png)


def selftest() -> int:
    import tempfile
    import xml.etree.ElementTree as ET
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        r = kit("Bloom & Stem", tmp, tagline="Flowers for every day", industry="florist")
        for p in r["files"]:
            if p.endswith(".svg"):
                root = ET.parse(p).getroot()
                if root.tag != "{%s}svg" % SVG_NS or not root.get("viewBox"):
                    bad += 1
                    print("bad svg", p)
        for pal, cols in PALETTES.items():
            if contrast(cols[3], cols[4]) < 7 or contrast(cols[4], cols[0]) < 4.5:
                bad += 1
                print("palette contrast", pal, contrast(cols[3], cols[4]), contrast(cols[4], cols[0]))
    print("selftest", "ok" if not bad else f"{bad} problems")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.brand_kit", description="Simple logo + brand kit from code (SVG).")
    ap.add_argument("--name", help="the business name as it should read")
    ap.add_argument("--tagline", default="", help="short line under the name (optional)")
    ap.add_argument("--industry", default="generic", help="plumber, florist, cafe, dentist ... (picks mark, colours and letters)")
    ap.add_argument("--concept", type=int, default=1, choices=(1, 2, 3), help="which of the 3 concepts gets the full kit")
    ap.add_argument("--mark", help="override the symbol: monogram or one of --list")
    ap.add_argument("--container", help="circle, rounded, shield, hexagon, arch, none")
    ap.add_argument("--palette", help="one of --list")
    ap.add_argument("--primary", help="the client's own brand colour, like #1f3a5f (builds a palette around it)")
    ap.add_argument("--font", dest="font_kind", choices=("sans", "serif"))
    ap.add_argument("--case", choices=("upper", "title"))
    ap.add_argument("--person", default="")
    ap.add_argument("--phone", default="")
    ap.add_argument("--email", default="")
    ap.add_argument("--website", default="")
    ap.add_argument("--address", default="")
    ap.add_argument("--out", help="folder for the files")
    ap.add_argument("--png", action="store_true", help="also PNG copies of avatar, favicon, banner, mark (needs playwright)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.list:
        print("marks:      monogram, " + ", ".join(MARKS))
        print("containers: " + ", ".join(CONTAINERS))
        for k, v in PALETTES.items():
            print(f"palette {k:11s} {' '.join(v)}  {PALETTE_NOTES[k]}")
        print("industries: " + ", ".join(sorted(INDUSTRIES)))
        return 0
    if not a.name or not a.out:
        ap.error("--name and --out are needed (or --list / --selftest)")
    contact = {"person": a.person, "phone": a.phone, "email": a.email, "website": a.website, "address": a.address}
    try:
        r = kit(a.name, a.out, tagline=a.tagline, industry=a.industry, concept=a.concept, png=a.png, contact=contact,
                mark=a.mark, container=a.container, palette=a.palette, font_kind=a.font_kind, case=a.case, primary=a.primary)
    except ValueError as e:
        print(f"error: {e}")
        return 2
    s = r["spec"]
    print(f"{s['name']}: concept {s['concept']} = {s['mark']} in {s['container']}, palette {s['palette']}, {s['font']} letters ({s['case']})")
    print(f"{len(r['files'])} files in {r['out']}; open brand_guide.html to check it, then concepts.svg for the client to choose")
    return 0


if __name__ == "__main__":
    sys.exit(main())
