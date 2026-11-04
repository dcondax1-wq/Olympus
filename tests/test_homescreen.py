"""'Add to Home Screen' quality of every OLYMPUS app (iPhone first), checked statically from the files:
  the owner's logo is the icon: a 180 x 180 PNG apple-touch-icon (jarvis/apple-touch-icon.png, rebuilt by tools/make_olympus_icons.py) that exists, the
  tags iOS reads (apple-mobile-web-app-capable, status-bar-style, a short title <= 12 characters, theme-color, viewport-fit=cover), and a web manifest
  (name, short_name <= 12, start_url inside the app folder, scope, display standalone, 192 + 512 + maskable PNG icons whose files exist and whose real
  PNG size (read from the file header) matches what the manifest says; no dangling path). The app list is dynamic: olympus/apps-list.js.
  Every app's folder must be published by the build (tools/build_web_dashboard.py copies the folders it names, whole).
  Apps listed in PENDING belong to someone else this moment: their gaps are PRINTED (a table), and the test fails if an app NOT in PENDING has a gap
  or if a PENDING app became clean (remove it from the list).
    python -X utf8 -m tests.test_homescreen
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []
# apps another agent owns right now: gaps are listed, not fixed here (the lead removes a name when its owner has fixed it)
PENDING = {"arena", "ares", "chronos", "cities", "datacity", "fates", "forum", "hephaestus", "hermes", "kalshi", "labyrinth", "nemesis", "odeon", "oracle", "pantheon",
           "plutus", "prometheus", "pc", "tyche"}
NOT_AN_APP = {"pc"}                              # plain files, not an app (the PC helper downloads): never needs icons


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def png_size(path):
    """(w, h) from the PNG header, or None when it is not a PNG."""
    try:
        with open(path, "rb") as fh:
            h = fh.read(24)
        if h[:8] != b"\x89PNG\r\n\x1a\n" or h[12:16] != b"IHDR":
            return None
        return struct.unpack(">II", h[16:24])
    except OSError:
        return None


def apps():
    src = rd(WEB, "olympus", "apps-list.js")
    rows = json.loads(src[src.index("["):src.rindex("]") + 1])
    return [(a["id"], a["name"], a["path"]) for a in rows]


def tag(html, rx):
    m = re.search(rx, html, re.I)
    return m.group(1) if m else None


def resolve(base, href):
    """An href / src relative to a folder -> the file inside tools/web_public (query and hash dropped), or None when it points outside or is absolute."""
    h = (href or "").split("#")[0].split("?")[0]
    if not h or re.match(r"(https?:|data:|/)", h):
        return None
    p = os.path.normpath(os.path.join(base, h))
    return p if p.startswith(WEB) else None


def audit(app_dir, name, root_icons=None):
    """-> [problem words] for one app folder (index.html + manifest)."""
    bad = []
    idx = os.path.join(app_dir, "index.html")
    if not os.path.isfile(idx):
        return ["no index.html"]
    h = rd(idx)
    if "viewport-fit=cover" not in h:
        bad.append("viewport-fit=cover")
    tc = tag(h, r'<meta[^>]*name="theme-color"[^>]*content="(#[0-9a-fA-F]{3,8})"')
    if not tc:
        bad.append("theme-color")
    href = tag(h, r'<link[^>]*rel="apple-touch-icon"[^>]*href="([^"]+)"')
    p = resolve(app_dir, href) if href else None
    if not href:
        bad.append("apple-touch-icon link")
    elif not p or png_size(p) != (180, 180):
        bad.append(f"apple-touch-icon is not a 180x180 PNG ({href})")
    if tag(h, r'<meta[^>]*name="apple-mobile-web-app-capable"[^>]*content="(yes)"') is None:
        bad.append("apple-mobile-web-app-capable")
    if tag(h, r'<meta[^>]*name="mobile-web-app-capable"[^>]*content="(yes)"') is None:
        bad.append("mobile-web-app-capable")
    if tag(h, r'<meta[^>]*name="apple-mobile-web-app-status-bar-style"[^>]*content="(default|black|black-translucent)"') is None:
        bad.append("status-bar-style")
    ti = tag(h, r'<meta[^>]*name="apple-mobile-web-app-title"[^>]*content="([^"]*)"')
    if not ti or len(ti) > 12:
        bad.append(f"apple-mobile-web-app-title ({ti!r})")
    mf = tag(h, r'<link[^>]*rel="manifest"[^>]*href="([^"]+)"')
    mp = resolve(app_dir, mf) if mf else None
    if not mp or not os.path.isfile(mp):
        return bad + ["manifest link / file"]
    try:
        m = json.loads(rd(mp))
    except ValueError:
        return bad + ["manifest is not JSON"]
    if not m.get("name") or not m.get("short_name") or len(m["short_name"]) > 12:
        bad.append("manifest name / short_name")
    su, sc = m.get("start_url", ""), m.get("scope", "")
    sp = resolve(os.path.dirname(mp), su.split("#")[0] or "./")
    if not su or su.startswith(("/", "http", "..")) or sp is None or not (sp + os.sep).startswith(app_dir + os.sep) or sc not in ("./", ""):
        bad.append(f"start_url / scope inside the app folder ({su!r}, {sc!r})")
    if m.get("display") != "standalone":
        bad.append("display standalone")
    if not m.get("theme_color") or not m.get("background_color"):
        bad.append("manifest theme_color / background_color")
    got = set()
    for ic in m.get("icons") or []:
        f = resolve(os.path.dirname(mp), ic.get("src", ""))
        if f is None or not os.path.isfile(f):
            bad.append(f"dangling icon {ic.get('src')}")
            continue
        if str(ic.get("type", "")) == "image/png":
            wh = png_size(f)
            if wh is None or "%dx%d" % wh != ic.get("sizes"):
                bad.append(f"icon size {ic.get('src')} says {ic.get('sizes')}, file is {wh}")
            else:
                got.add((ic["sizes"], ic.get("purpose", "any")))
    for need in (("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")):
        if need not in got:
            bad.append("manifest icon " + "/".join(need))
    return bad


def published():
    """The folders tools/build_web_dashboard.py copies whole (the `for app in (...)` tuple)."""
    src = rd(ROOT, "tools", "build_web_dashboard.py")
    m = re.search(r'for app in \(([^)]*)\):\s*\n\s*src_dir = os\.path\.join\(WEB, app\)', src)
    return set(re.findall(r'"([a-z0-9_]+)"', m.group(1))) if m else set()


def main():
    A = apps()
    folders = [(i, n, p) for i, n, p in A if p and os.path.isdir(os.path.join(WEB, p.strip("/")))]
    check(f"the app list (olympus/apps-list.js) has {len(A)} apps; every one with a folder here has an index.html",
          len(A) >= 25 and all(os.path.isfile(os.path.join(WEB, p.strip("/"), "index.html")) for _, _, p in folders) and {"ledger", "settings", "kalshicity"} <= {i for i, _, _ in folders}, [i for i, _, _ in folders])
    pub = published()
    missing = [i for i, _, p in folders if i not in pub and i not in ("pc",)]
    check("every app folder is published by the build (tools/build_web_dashboard.py copies the folders it names, whole): none is missing from that list", not missing and len(pub) > 20, missing)
    # the OLYMPUS logo set the apps share
    brand = {"apple-touch-icon.png": (180, 180), "icon-192.png": (192, 192), "icon-512.png": (512, 512), "icon-maskable-512.png": (512, 512)}
    check("the owner's logo icon set exists in jarvis/ with the right sizes (180 touch icon, 192, 512, maskable 512) and the source logo is kept in olympus/brand/",
          all(png_size(os.path.join(WEB, "jarvis", f)) == s for f, s in brand.items()) and png_size(os.path.join(WEB, "olympus", "brand", "olympus-logo-1024.png")) == (1024, 1024)
          and os.path.isfile(os.path.join(WEB, "olympus", "brand", "olympus-logo-source.png")), None)
    gaps = {}
    for i, n, p in folders:
        if i in NOT_AN_APP:
            continue
        g = audit(os.path.join(WEB, p.strip("/")), n)
        if g:
            gaps[i] = g
    mine = [i for i, _, _ in folders if i not in PENDING and i not in NOT_AN_APP]
    check(f"the {len(mine)} apps nobody else owns right now are complete: touch icon, capable, status bar, title, theme-color, viewport-fit, manifest (start_url in the folder, standalone, 192 / 512 / maskable PNGs that exist at the right size)",
          not any(i in gaps for i in mine), {i: gaps[i] for i in mine if i in gaps})
    stale = [i for i in PENDING if i in {x for x, _, _ in folders} and i not in gaps and i not in NOT_AN_APP]
    check("PENDING only lists apps that still have a gap (remove a name once its owner has fixed it)", not stale, stale)
    root = rd(WEB, "index.html")
    ricons = os.path.join(ROOT, "web", "icons")
    rm = json.loads(rd(WEB, "manifest.webmanifest"))
    rbad = [x for x, ok in (("viewport-fit=cover", "viewport-fit=cover" in root), ("apple-touch-icon", 'rel="apple-touch-icon"' in root), ("capable", 'name="apple-mobile-web-app-capable"' in root),
                            ("manifest", 'rel="manifest"' in root), ("standalone", rm.get("display") == "standalone"), ("start_url", rm.get("start_url", "").startswith("./")),
                            ("icons 192/512/maskable", {(i.get("sizes"), i.get("purpose")) for i in rm.get("icons", [])} >= {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")}),
                            ("source icons", all(png_size(os.path.join(ricons, f)) == s for f, s in brand.items())))
            if not ok]
    check("Zenith (the root page): the same tags, a standalone manifest and the 180 / 192 / 512 / maskable icons in web/icons, which the build copies to icons/", not rbad, rbad)
    if gaps:
        print("\n| app | gaps | owner now |\n|---|---|---|")
        for i, g in sorted(gaps.items()):
            print(f"| {i} | {'; '.join(g)[:150]} | {'someone else (listed)' if i in PENDING else 'THIS TEST: fix'} |")
    print(f"\nhome screen: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED") + f"; {len([i for i in gaps if i in PENDING])} apps listed as gaps")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
