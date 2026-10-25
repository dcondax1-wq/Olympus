"""Switch the live Home Screen icon to one of the options in tools/web_public/icon_options/<a|b|c>/.

    python tools/icon_apply.py b             # apply option B
    python tools/icon_apply.py b --dry-run   # show what would change, write nothing
    python tools/icon_apply.py b --root DIR  # act on a copy of the repo (used by the self-test)

What it does:
1. Copies the option's icon files into web/icons/ (the one source: tools/build_web_dashboard.py copies them to the public
   dashboard, and the PC server serves web_next/ with fallback to web/), and into tools/web_public/icons/ if that exists.
2. Replaces the cache-busting tag (icons/...?v=<tag>) in every page, manifest and service worker of web/, web_next/ and
   tools/web_public/ with a new tag, so phones fetch the new files.
3. Bumps the service-worker cache versions (web/sw.js, web_next/sw.js, tools/web_public/sw.js).
iOS caches Home Screen icons: delete the app from the Home Screen and add it again to see the new icon.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png", "icon.svg",
         "icon-152.png", "icon-120.png", "icon-1024.png")
SCAN_DIRS = ("web", "web_next", os.path.join("tools", "web_public"))
SKIP = ("icon_options", "node_modules", "icons")
EXT = (".html", ".js", ".webmanifest")
TAG_RE = re.compile(r"(icons/[\w.-]+\?v=)([\w-]+)")
SW_RE = re.compile(r"(const (?:CACHE|SHELL) = '[\w-]*?-v)(\d+)(')")


def text_files(root):
    for d in SCAN_DIRS:
        base = os.path.join(root, d)
        for cur, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in SKIP]
            for f in files:
                if f.endswith(EXT):
                    yield os.path.join(cur, f)


def apply(key, root=ROOT, dry=False, today=None):
    src = os.path.join(root, "tools", "web_public", "icon_options", key)
    missing = [f for f in FILES[:5] if not os.path.exists(os.path.join(src, f))]
    if missing:
        sys.exit(f"option {key!r}: missing {missing} in {src} (run python tools/icon_options_build.py)")
    info = {}
    try:
        info = json.load(open(os.path.join(src, "info.json"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    tag = f"{key}{(today or dt.date.today()).strftime('%m%d')}"
    changes = []
    # 1. icon files
    dests = [os.path.join(root, "web", "icons")]
    if os.path.isdir(os.path.join(root, "tools", "web_public", "icons")):
        dests.append(os.path.join(root, "tools", "web_public", "icons"))
    for dest in dests:
        for f in FILES:
            if os.path.exists(os.path.join(src, f)):
                changes.append(f"copy {f} -> {os.path.relpath(dest, root)}/")
                if not dry:
                    os.makedirs(dest, exist_ok=True)
                    shutil.copy(os.path.join(src, f), os.path.join(dest, f))
    # 2. cache-busting tags + 3. service-worker cache versions
    for path in text_files(root):
        old = open(path, encoding="utf-8").read()
        new, n_tag = TAG_RE.subn(lambda m: m.group(1) + tag, old)
        n_sw = 0
        if os.path.basename(path) == "sw.js":
            new, n_sw = SW_RE.subn(lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}", new)
        if new != old:
            changes.append(f"edit {os.path.relpath(path, root)}: {n_tag} icon tag(s) -> ?v={tag}"
                           + (f", sw cache +1" if n_sw else ""))
            if not dry:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
    print(f"{'DRY RUN: ' if dry else ''}icon option {key.upper()} {info.get('name', '')}".rstrip())
    for c in changes:
        print("  " + c)
    if not dry:
        print("Done. On the iPhone: delete the app from the Home Screen, open the dashboard in Safari, Share > Add to Home Screen.")
    return changes


def main():
    ap = argparse.ArgumentParser(description="Switch the live Home Screen icon to option a, b or c.")
    ap.add_argument("option", choices=["a", "b", "c"])
    ap.add_argument("--root", default=ROOT, help="repo root to act on (default: this repo)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    apply(a.option, os.path.abspath(a.root), a.dry_run)


if __name__ == "__main__":
    main()
