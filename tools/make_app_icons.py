#!/usr/bin/env python3
"""Home Screen icons for the new OLYMPUS apps (2026-11-10): renders each app's own icon.svg (AGORA marble / bronze / gold, one simple Greek glyph) to
    <app>/apple-touch-icon.png (180), <app>/icon-192.png, <app>/icon-512.png, <app>/icon-maskable-512.png (glyph inside the 80 % safe zone)
and makes the app's index.html <head> and manifest.webmanifest point at them (idempotent: only gaps are filled, the app's own text is kept).

    python tools/make_app_icons.py                 all apps in APPS whose folder exists
    python tools/make_app_icons.py mercury lyceum  only these
    python tools/make_app_icons.py --check         exit 1 when a PNG is missing or a tag / manifest field would change (no browser needed)
Needs Playwright + Chromium to rasterise (the repo's tests already use it). The OLYMPUS logo set (jarvis/*.png, tools/make_olympus_icons.py) is untouched.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
APPS = ("hestia demeter apollo hera dionysus clio delphi pnyx planner mint mercury chrysos sibyl oikos arbiter stoa aegis lyceum nike kronos moirai epilogue "
        "kairos kratos argo pythia mintcity gallery").split()
BG, THEME = "#1d1914", "#000000"
HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1d1914"/><circle cx="32" cy="32" r="26" fill="none" stroke="#9c6b3c" stroke-width="2"/>'
G, I, B, O, T = "#c8a24a", "#f3ece0", "#9c6b3c", "#7f8a52", "#c96a4a"

# glyphs redrawn where two apps looked alike or the mark was not a Greek one (Lyceum was a second temple next to Pnyx; Mint a bar chart; Mercury a ticket)
GLYPHS = {
    "lyceum": f'<path d="M20 17l7 6-6 3z" fill="{G}"/><path d="M44 17l-7 6 6 3z" fill="{G}"/><ellipse cx="32" cy="35" rx="12" ry="15" fill="{G}"/>'
              f'<circle cx="27" cy="29" r="5.5" fill="{I}"/><circle cx="37" cy="29" r="5.5" fill="{I}"/><circle cx="27" cy="29" r="2.4" fill="{BG}"/><circle cx="37" cy="29" r="2.4" fill="{BG}"/>'
              f'<path d="M32 31l-2.6 5h5.2z" fill="{B}"/><path d="M26 42q3 3 6 0q3 3 6 0M27 46q2.5 2.5 5 0q2.5 2.5 5 0" fill="none" stroke="{B}" stroke-width="1.4" stroke-linecap="round"/>'
              f'<rect x="15" y="50" width="34" height="3" rx="1.5" fill="{B}"/>',
    "mint": f'<circle cx="32" cy="32" r="16" fill="{G}"/><circle cx="32" cy="32" r="12" fill="none" stroke="{BG}" stroke-width="1.5"/>'
            f'<path d="M24 40q7-14 16-16" fill="none" stroke="{BG}" stroke-width="1.8" stroke-linecap="round"/>'
            f'<ellipse cx="27.5" cy="34" rx="3.4" ry="1.5" transform="rotate(-52 27.5 34)" fill="{BG}"/><ellipse cx="32.5" cy="29.5" rx="3.4" ry="1.5" transform="rotate(-38 32.5 29.5)" fill="{BG}"/>'
            f'<ellipse cx="38" cy="26" rx="3.2" ry="1.4" transform="rotate(-20 38 26)" fill="{BG}"/><path d="M19 23a15 15 0 0 1 9-7" fill="none" stroke="{I}" stroke-width="1.8" stroke-linecap="round" opacity=".75"/>',
    "mercury": f'<rect x="31" y="16" width="2" height="35" rx="1" fill="{I}"/><circle cx="32" cy="15" r="2.8" fill="{G}"/>'
               f'<path id="w" d="M31 21Q22 14 13 19Q19 20 21 24Q16 24 15 28Q22 27 31 27Z" fill="{G}"/><use href="#w" transform="translate(64 0) scale(-1 1)"/>'
               f'<path d="M32 29C42 32 22 38 32 42C41 45 25 48 32 51" fill="none" stroke="{O}" stroke-width="2.2" stroke-linecap="round"/>'
               f'<path d="M32 29C22 32 42 38 32 42C23 45 39 48 32 51" fill="none" stroke="#e0b060" stroke-width="1.6" stroke-linecap="round" opacity=".9"/>',
}


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s)


def split_svg(svg):
    """-> (open tag incl. viewBox, inner markup after the background rect) of one of our 64 x 64 icons."""
    m = re.match(r"\s*(<svg[^>]*>)\s*<rect[^>]*/>(.*)</svg>\s*$", svg, re.S)
    return (m.group(1), m.group(2)) if m else (None, None)


def variant(svg, kind):
    """kind 'full' = full-bleed square (iOS and Android round it themselves); 'maskable' = glyph scaled into the 80 % safe zone."""
    head, inner = split_svg(svg)
    if head is None:
        raise ValueError("icon.svg is not in the app icon layout (svg, one background rect, the glyph)")
    bg = f'<rect width="64" height="64" fill="{BG}"/>'
    if kind == "maskable":
        inner = f'<g transform="translate(32 32) scale(.78) translate(-32 -32)">{inner}</g>'
    return head + bg + inner + "</svg>"


def app_name(html, app):
    m = re.search(r"<title>([^<]*)</title>", html)
    return (m.group(1).strip() if m else app.title())[:12]


def patch_html(html, app):
    """Fill only what is missing in <head>; always point the apple-touch-icon at the app's own PNG. Returns the new text."""
    name = app_name(html, app)
    meta = {
        'name="theme-color"': f'<meta name="theme-color" content="{THEME}">',
        'name="mobile-web-app-capable"': '<meta name="mobile-web-app-capable" content="yes">',
        'name="apple-mobile-web-app-capable"': '<meta name="apple-mobile-web-app-capable" content="yes">',
        'name="apple-mobile-web-app-status-bar-style"': '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
        'name="apple-mobile-web-app-title"': f'<meta name="apple-mobile-web-app-title" content="{name}">',
        'name="color-scheme"': '<meta name="color-scheme" content="dark">',
    }
    add = [t for k, t in meta.items() if k not in html]
    if "viewport-fit=cover" not in html:
        html = re.sub(r'(<meta name="viewport" content=")([^"]*)(")', lambda m: m.group(1) + m.group(2).rstrip(", ") + ", viewport-fit=cover" + m.group(3), html, count=1)
    links = []
    if 'rel="icon"' not in html:
        links.append('<link rel="icon" href="icon.svg">')
    if 'rel="manifest"' not in html:
        links.append('<link rel="manifest" href="manifest.webmanifest">')
    if re.search(r'<link[^>]*rel="apple-touch-icon"', html):
        html = re.sub(r'(<link[^>]*rel="apple-touch-icon"[^>]*href=")[^"]*(")', r"\1apple-touch-icon.png\2", html, count=1)
    else:
        links.append('<link rel="apple-touch-icon" href="apple-touch-icon.png">')
    if add or links:
        block = "\n".join(add + links) + "\n"
        m = re.search(r'<meta name="viewport"[^>]*>\n?', html)
        html = html[:m.end()] + ("" if html[m.end() - 1] == "\n" else "\n") + block + html[m.end():] if m else html.replace("</head>", block + "</head>", 1)
    return html


def patch_manifest(man, name, desc):
    out = dict(man) if isinstance(man, dict) else {}
    out.setdefault("name", name)
    out["short_name"] = out.get("short_name") if out.get("short_name") and len(out["short_name"]) <= 12 else name
    out.setdefault("description", desc)
    out.update({"id": "./", "start_url": "./", "scope": "./", "display": "standalone", "orientation": "portrait", "background_color": THEME, "theme_color": THEME})
    out["icons"] = [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}, {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}, {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
    return out


def targets(names):
    return [a for a in (names or APPS) if os.path.isfile(os.path.join(WEB, a, "index.html"))]


def render(apps):
    from playwright.sync_api import sync_playwright
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    jobs = [("apple-touch-icon.png", 180, "full"), ("icon-192.png", 192, "full"), ("icon-512.png", 512, "full"), ("icon-maskable-512.png", 512, "maskable")]
    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        page = br.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=1)
        for a in apps:
            d = os.path.join(WEB, a)
            svg = read(os.path.join(d, "icon.svg"))
            for fn, px, kind in jobs:
                v = variant(svg, kind).replace("<svg ", f'<svg width="{px}" height="{px}" ', 1)
                page.set_viewport_size({"width": px, "height": px})
                page.set_content(f'<body style="margin:0;background:{BG}">{v}</body>')
                page.screenshot(path=os.path.join(d, fn), clip={"x": 0, "y": 0, "width": px, "height": px})
        br.close()


def main(argv):
    check = "--check" in argv
    names = [a for a in argv if not a.startswith("--")]
    apps = targets(names)
    if not check:
        for a, svg in GLYPHS.items():
            if a in apps:
                write(os.path.join(WEB, a, "icon.svg"), HEAD + svg + "</svg>\n")
        render(apps)
    bad = []
    for a in apps:
        d = os.path.join(WEB, a)
        html = read(os.path.join(d, "index.html"))
        new = patch_html(html, a)
        mp = os.path.join(d, "manifest.webmanifest")
        man = json.loads(read(mp)) if os.path.isfile(mp) else {}
        desc = re.search(r'<meta name="description" content="([^"]*)"', html)
        nm = patch_manifest(man, app_name(html, a), desc.group(1) if desc else "")
        if check:
            for fn in ("apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png"):
                if not os.path.isfile(os.path.join(d, fn)):
                    bad.append(f"{a}/{fn} missing")
            if new != html:
                bad.append(f"{a}/index.html head would change")
            if nm != man:
                bad.append(f"{a}/manifest.webmanifest would change")
        else:
            write(os.path.join(d, "index.html"), new)
            write(mp, json.dumps(nm, indent=2, ensure_ascii=False) + "\n")
    print(("check: " if check else "done: ") + f"{len(apps)} apps" + ("" if not bad else "; " + "; ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
