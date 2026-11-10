#!/usr/bin/env python3
"""OLYMPUS map builder: regenerates docs/OLYMPUS_MAP.md (every app: id, district, group, an 8-word description, the data it reads, its test). Stdlib only, read only, offline.

    python tools/olympus_map_build.py            # rewrite docs/OLYMPUS_MAP.md
    python tools/olympus_map_build.py --check    # exit 1 when the file is not what this script writes now (tests.test_olympus_map runs it)
    python tools/olympus_map_build.py --selftest

Sources (all in the repo, nothing is typed by hand):
  * tools/web_public/jarvis/apps.js   BUILT_INS rows: app('id', 'Name', 'group', 'accent', 'sub', ...)  -> name, group, description (first 8 words of `sub`)
  * tools/web_public/atlas/atlas.js   the five districts `zones` (id, title, ids[]); an app in no list falls back like the page does (money -> Money, life -> Life, else Market)
  * tools/web_public/<id>/*.js|html   the published JSON files an app reads (getJSON / fetch / load string literals ending .json), then its fixture.json
  * tests/test_<id>_page.py | test_<id>.py | any test_*<id>*.py   the test that covers it, else the kit test
After editing jarvis/apps.js or the Atlas districts: run this, then `python tools/apps_list_build.py`.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
OUT = os.path.join(ROOT, "docs", "OLYMPUS_MAP.md")
HEAD = """# OLYMPUS map

Every app, in the five districts of the Atlas command center (`tools/web_public/atlas/`). The district is the way you find it; the **group** column is the older registry group (`jarvis/apps.js`: trading / money / life) that the launcher and the Jarvis switcher use. **This file is generated: `python tools/olympus_map_build.py` (do not edit the table by hand; `tests.test_olympus_map` fails when it is stale).**

Finding things: Atlas has search (names and plain words), pinned rooms (long-press a room or tap the star), recent rooms, a "what needs me now" strip and an all-apps-on-one-screen view. The Zenith launcher button and the Jarvis orb have the same search, favourites (long-press a tile), recent apps and a MAP view.

Data: apps only read published JSON (and bundled `fixture.json` / demo fallbacks). No app places orders. Look: AGORA (`docs/DESIGN_AGORA.md`). Wiring a new app: `tools/wire_new_apps.py` + `tools/new_apps.json` (`docs/NEW_APPS_WIRING.md`).
"""
FOOT = """
## Where the organizing code lives

| Piece | File | Test |
|---|---|---|
| Atlas command center (districts, search, pins, recent, needs-me strip, one-screen map) | `tools/web_public/atlas/` (`atlas.js`, `hub.js`, `atlas.css`) | `node --test tests/test_atlas_standalone_hub.mjs`, `tests/test_atlas_intro.mjs` |
| Zenith launcher sheet (favourites, search, recent, MAP) | `tools/web_public/launcher.js` = `web_next/js/next/launcher.js` (byte-identical) | `tests.test_apps_list` |
| Jarvis switcher (search, MAP, favourites, recent) | `tools/web_public/jarvis/switcher.js` | `tests.test_jarvis_hub` (parts n, p, s) |
| App registry | `tools/web_public/jarvis/apps.js` -> `olympus/apps-list.js` | `tests.test_apps_list` |
| This map | `tools/olympus_map_build.py` -> `docs/OLYMPUS_MAP.md` | `tests.test_olympus_map` |
"""
FALLBACK_DATA = "bundled fixture / its own files"
MAX_DATA = 5


def read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def unescape(s):
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s).replace("\\'", "'").replace('\\"', '"')


def parse_apps(src):
    """[(id, name, group, sub)] from the BUILT_INS rows of jarvis/apps.js, in file order."""
    out = []
    for m in re.finditer(r"^\s*app\(\s*'([a-z0-9_-]+)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*'([a-z]+)'\s*,\s*'[^']*'\s*,\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")", src, re.M):
        out.append((m.group(1), unescape(m.group(2)), m.group(3), unescape(m.group(4)[1:-1])))
    return out


def parse_zones(src):
    """[(zone id, title, [app ids])] from atlas.js."""
    out = []
    for m in re.finditer(r"\{\s*id:\s*'(\w+)'\s*,\s*title:\s*'([^']+)'[^\n]*?ids:\s*\[([^\]]*)\]", src):
        out.append((m.group(1), m.group(2), re.findall(r"'([a-z0-9_-]+)'", m.group(3))))
    return out


def zone_of(app_id, group, zones):
    for zid, title, ids in zones:
        if app_id in ids:
            return title
    want = "risk" if group == "money" else "life" if group == "life" else "market"
    return next((t for z, t, _ in zones if z == want), "Market")


def words8(s):
    w = re.sub(r"\s+", " ", s).strip().split(" ")
    return " ".join(w[:8]).rstrip(",.;:") if w and w != [""] else ""


def reads_of(app_id):
    d = os.path.join(WEB, app_id)
    if app_id == "zenith":
        return "data.json, home.json, live.json (the bot feeds)"
    found = []
    pats = (r"getJSON\(\s*['\"`]([^'\"`]+?\.json)", r"fetch\(\s*['\"`]([^'\"`]+?\.json)", r"(?:load\w*|fetchJson|readJson)\(\s*['\"`]([^'\"`]+?\.json)")
    for f in sorted(glob.glob(os.path.join(d, "*.js")) + glob.glob(os.path.join(d, "index.html"))):
        for p in pats:
            for m in re.finditer(p, read(f)):
                u = m.group(1).split("?")[0]
                if u not in found and not u.startswith("http") and not u.endswith("manifest.json"):
                    found.append(u)
    if os.path.isfile(os.path.join(d, "fixture.json")) and "fixture.json" not in found and "./fixture.json" not in found:
        found.append("fixture.json")
    found = [u[2:] if u.startswith("./") else u for u in found]
    if not found:
        return FALLBACK_DATA
    shown = found[:MAX_DATA] + (["..."] if len(found) > MAX_DATA else [])
    return ", ".join(f"`{u}`" if u != "..." else u for u in shown)


def test_of(app_id):
    for cand in (f"test_{app_id}_page.py", f"test_{app_id}.py"):
        if os.path.isfile(os.path.join(ROOT, "tests", cand)):
            return f"`tests.{cand[:-3]}`"
    hits = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(ROOT, "tests", f"test_*{app_id}*.py")))
    return f"`tests.{hits[0]}`" if hits else "covered by `tests.test_olympus_kit`"


def build():
    apps = parse_apps(read(os.path.join(WEB, "jarvis", "apps.js")))
    zones = parse_zones(read(os.path.join(WEB, "atlas", "atlas.js")))
    order = {t: i for i, (_, t, _) in enumerate(zones)}
    rows = []
    for aid, name, group, sub in apps:
        dist = zone_of(aid, group, zones)
        rows.append((order.get(dist, 99), aid, f"| {name} (`{aid}`) | {dist} | {group} | {words8(sub)} | {reads_of(aid)} | {test_of(aid)} |"))
    rows.sort(key=lambda r: (r[0], r[1]))
    table = ["| App (id) | District | Group | What it is | Data it reads | Test |", "|---|---|---|---|---|---|"] + [r[2] for r in rows]
    n = len(apps)
    foot = f"\n{n} apps. Rebuild the registry list after editing `jarvis/apps.js` or `olympus.js`: `python tools/apps_list_build.py`; recount: `python tools/apps_list_build.py --check`.\n"
    return HEAD + "\n" + "\n".join(table) + "\n" + foot + FOOT


def main(argv=None):
    ap = argparse.ArgumentParser(description="Regenerate docs/OLYMPUS_MAP.md from apps.js, the Atlas districts and the tests.")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    text = build()
    if a.check:
        ok = read(a.out) == text
        print("OLYMPUS_MAP.md is in step" if ok else "OLYMPUS_MAP.md is NOT what olympus_map_build.py writes: run  python tools/olympus_map_build.py")
        return 0 if ok else 1
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {a.out}")
    return 0


def selftest():
    bad = []

    def ck(name, ok, info=""):
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))
        if not ok:
            bad.append(name)
    src = "export const BUILT_INS = Object.freeze([\n  app('zenith', 'Zenith', 'trading', '#a855f7', 'NQ bots \\u00b7 Zlarior', { url: '../' }),\n  app('pheme', 'Pheme', 'trading', '#c8a24a', \"The word on the street: releases, and NQ's past moves on them\", { glyph: 'X' }),\n  app('plan', 'Planner', 'life', '#fff', 'Day plan', {}),\n])"
    a = parse_apps(src)
    ck("apps.js rows: ids, names, groups, escaped and double-quoted subs", [x[0] for x in a] == ["zenith", "pheme", "plan"] and a[0][3] == "NQ bots · Zlarior" and a[1][3].startswith("The word on the street") and a[2][2] == "life", a)
    z = parse_zones("const zones = [\n { id:'market', title:'Market', colour:'#c8a24a', note:'x', ids:['zenith','oracle'] },\n { id:'risk', title:'Money', colour:'#1', note:'y', ids:['hera'] },\n { id:'life', title:'Life', colour:'#2', note:'z', ids:[] }\n];")
    ck("zones: id, title, ids", z == [("market", "Market", ["zenith", "oracle"]), ("risk", "Money", ["hera"]), ("life", "Life", [])], z)
    ck("district: listed, else by group (money -> Money, life -> Life, trading -> Market)", zone_of("zenith", "trading", z) == "Market" and zone_of("new", "money", z) == "Money" and zone_of("new", "life", z) == "Life" and zone_of("new", "trading", z) == "Market")
    ck("8 words: longer sentences are cut, trailing punctuation dropped, short ones kept", words8("The word on the street: releases, and NQ's past moves on them") == "The word on the street: releases, and NQ's" and words8("Day plan") == "Day plan" and words8("") == "")
    ck("the unknown app has the fallbacks (bundled data, the kit test)", reads_of("zzz-none") == FALLBACK_DATA and test_of("zzz-none") == "covered by `tests.test_olympus_kit`")
    real = build()
    n = len(parse_apps(read(os.path.join(WEB, "jarvis", "apps.js"))))
    ck("the real map has one row per BUILT_INS app and five districts", real.count("\n| ") >= n and n > 30 and all(f"| {d} |" in real for d in ("Market", "Research", "Money", "Command", "Life")), n)
    ck("deterministic", build() == real)
    print(f"\n{'ALL PASS' if not bad else str(len(bad)) + ' FAILED'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
