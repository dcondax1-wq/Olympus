#!/usr/bin/env python3
"""Make OLYMPUS apps 'Add to Home Screen' ready (iPhone first), idempotent. The owner's logo (jarvis/apple-touch-icon.png, icon-192/512/maskable, rebuilt by
tools/make_olympus_icons.py) is the icon of every app; nothing is copied: each app points at ../jarvis/.

    python tools/homescreen_apply.py ledger inbox settings        # these apps' index.html + manifest.webmanifest
    python tools/homescreen_apply.py --all                        # every app folder of olympus/apps-list.js (only gaps are filled; nothing is overwritten)
    python tools/homescreen_apply.py --check ledger               # exit 1 when something would change

Per app it fills ONLY what is missing, in the <head> of index.html: apple-touch-icon (180 PNG), apple-mobile-web-app-capable, mobile-web-app-capable,
apple-mobile-web-app-status-bar-style (black-translucent), apple-mobile-web-app-title (the app's name, <= 12 characters), the manifest link; and in
manifest.webmanifest: name, short_name, id, start_url './', scope './', display standalone, colours (from the page's theme-color) and the icons (the app's own
SVG kept, plus the three PNGs: 192 any, 512 any, 512 maskable). tests/test_homescreen.py is the audit.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
V = "?v=j4"
PNGS = [("../jarvis/icon-192.png" + V, "192x192", "any"), ("../jarvis/icon-512.png" + V, "512x512", "any"), ("../jarvis/icon-maskable-512.png" + V, "512x512", "maskable")]


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s)


def app_rows():
    src = read(os.path.join(WEB, "olympus", "apps-list.js"))
    return {a["id"]: a for a in json.loads(src[src.index("["):src.rindex("]") + 1])}


def has(h, rx):
    return re.search(rx, h, re.I) is not None


def apply_app(app_id, row, write_files=True):
    d = os.path.join(WEB, app_id)
    idx = os.path.join(d, "index.html")
    if not os.path.isfile(idx):
        return None
    h = read(idx)
    name = (row.get("name") or app_id.title())[:12]
    tc = (re.search(r'<meta[^>]*name="theme-color"[^>]*content="(#[0-9a-fA-F]{3,8})"', h) or [None, row.get("colour") or "#000000"])[1]
    add = []
    if not has(h, r'<link[^>]*rel="apple-touch-icon"'):
        add.append(f'<link rel="apple-touch-icon" href="../jarvis/apple-touch-icon.png{V}">')
    if not has(h, r'<meta[^>]*name="apple-mobile-web-app-capable"'):
        add.append('<meta name="apple-mobile-web-app-capable" content="yes">')
    if not has(h, r'<meta[^>]*name="mobile-web-app-capable"'):
        add.append('<meta name="mobile-web-app-capable" content="yes">')
    if not has(h, r'<meta[^>]*name="apple-mobile-web-app-status-bar-style"'):
        add.append('<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">')
    if not has(h, r'<meta[^>]*name="apple-mobile-web-app-title"'):
        add.append(f'<meta name="apple-mobile-web-app-title" content="{name}">')
    if not has(h, r'<link[^>]*rel="manifest"'):
        add.append('<link rel="manifest" href="manifest.webmanifest">')
    changed = []
    if add:
        m = re.search(r'<meta[^>]*name="theme-color"[^>]*>[^\n]*\n', h) or re.search(r'<meta[^>]*name="viewport"[^>]*>[^\n]*\n', h)
        if not m:
            return None
        h = h[:m.end()] + "\n".join(add) + "\n" + h[m.end():]
        changed.append("index.html +" + str(len(add)))
        if write_files:
            write(idx, h)
    mp_rel = (re.search(r'<link[^>]*rel="manifest"[^>]*href="([^"?#]+)', h) or [None, "manifest.webmanifest"])[1]
    mp = os.path.join(d, mp_rel)
    try:
        man = json.loads(read(mp)) if os.path.isfile(mp) else {}
    except ValueError:
        man = {}
    before = json.dumps(man, sort_keys=True)
    man.setdefault("name", row.get("name") or name)
    man.setdefault("short_name", name)
    if len(str(man["short_name"])) > 12:
        man["short_name"] = name
    man.setdefault("description", (row.get("purpose") or "")[:200])
    man.setdefault("id", "./")
    man.setdefault("start_url", "./")
    man.setdefault("scope", "./")
    man["display"] = "standalone"
    man.setdefault("orientation", "portrait")
    man.setdefault("background_color", tc)
    man.setdefault("theme_color", tc)
    icons = [i for i in man.get("icons", []) if isinstance(i, dict)]
    have = {(i.get("sizes"), i.get("purpose", "any")) for i in icons if i.get("type") == "image/png"}
    if os.path.isfile(os.path.join(d, "icon.svg")) and not any(i.get("type") == "image/svg+xml" for i in icons):
        icons.insert(0, {"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"})
    for src, sizes, purpose in PNGS:
        if (sizes, purpose) not in have:
            icons.append({"src": src, "sizes": sizes, "type": "image/png", "purpose": purpose})
    man["icons"] = icons
    if json.dumps(man, sort_keys=True) != before:
        changed.append("manifest")
        if write_files:
            write(mp, json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    return changed


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in a
    rows = app_rows()
    ids = [x for x in a if not x.startswith("--")]
    if "--all" in a:
        ids = [i for i, r in rows.items() if r.get("path") and os.path.isdir(os.path.join(WEB, i))]
    todo = 0
    for i in ids:
        if i not in rows:
            print(f"{i}: not in olympus/apps-list.js")
            continue
        r = apply_app(i, rows[i], write_files=not check)
        if r is None:
            print(f"{i}: no index.html / head to edit")
        elif r:
            todo += 1
            print(f"{i}: {', '.join(r)}")
    return 1 if check and todo else 0


if __name__ == "__main__":
    sys.exit(main())
