#!/usr/bin/env python3
"""OLYMPUS map builder: regenerates docs/OLYMPUS_MAP.md (every app: id, district, group, an 8-word description, the data it reads, its test). Stdlib only, read only, offline.

    python tools/olympus_map_build.py            # rewrite docs/OLYMPUS_MAP.md
    python tools/olympus_map_build.py --check    # exit 1 when the file is not what this script writes now (tests.test_olympus_map runs it)
    python tools/olympus_map_build.py --selftest

Sources (all in the repo, nothing is typed by hand):
  * tools/web_public/jarvis/apps.js   BUILT_INS rows: app('id', 'Name', 'group', 'accent', 'sub', ...)  -> name, group, description (first 8 words of `sub`)
  * tools/web_public/atlas/atlas.js   the FOUR DOORS `zones` (2026-11-18, = olympus/doors.js: id, title, ids[]); an app in no list falls back like the page does
                                      (money -> Money, trading -> ZEUS Trading, else More)
  * tools/web_public/<id>/*.js|html   the published JSON files an app reads (getJSON / fetch / load string literals ending .json), then its fixture.json
  * tests/test_<id>_page.py | test_<id>.py | any test_*<id>*.py   the test that covers it, else the kit test
  * tools/web_public/olympus/doors.js ARCHIVE                    which apps open first in their door and which are folded under "Archive"
  * MERGED below (2026-11-20, from the day helpers' hand-offs)     where a folded app's content lives now (a card on a main page)
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

**How Olympus is organized (2026-11-21, owner: "more organized").** One structure, everywhere:

1. **Home** (`gate/`) shows **the 6 arenas** (NQ Bot, Kalshi, Business, Websites, Jarvis, Cities) and **Everything else**. Each arena tile opens the
   arena's **front page** (its main app), and the row under the tiles ("All apps in ...") opens the arena's page `hub/arena.html?a=<arena>`: every live app
   of that arena grouped by job. So **every app is at most 2 taps from Home**.
2. **Every page has the same way back:** `Home > arena > app` at the top (plain names, not Greek ones), plus "Go to" (search, then the same 7 arenas). One tap on Home goes Home.
   It comes from `olympus/gate-nav.js`, loaded by the AGORA shell (`agora-ui.js`), by the a11y kit (`a11y.js`) or directly; the public client pages
   (agency demos, audits, showcase, factory, caller portal, concept sites) never get it.
3. **Retired apps redirect** to their replacement (`?stay=1` keeps the old page; nothing is deleted). Table below.
4. **One place per fact:** every account, its payout and its 7-day clocks live on **My MFFU Accounts** (`business/mffu.html`); Ledger keeps the real cash.
   A page that repeats one of them shows a "Main copy" chip linking there.

The arenas, the retired list and the fact owners are DATA in `tools/web_public/olympus/gate-catalog.js` (ARENAS, REPLACE, FACTS). **This file is generated:
`python tools/olympus_map_build.py` (do not edit by hand; `tests.test_olympus_map` fails when it is stale).** The link crawler and the nav checks:
`tests.test_olympus_nav`.

Data: apps only read published JSON (and bundled `fixture.json` / demo fallbacks). No app places orders. Look: OLYMPUS NIGHT (`docs/DESIGN_AGORA.md`).
"""
FOOT = """
## Where the organizing code lives

| Piece | File | Test |
|---|---|---|
| The arenas, retired -> replacement, one place per fact, every app's plain name and hub | `tools/web_public/olympus/gate-catalog.js` (ARENAS, REPLACE, FACTS, R) | `tests.test_olympus_nav`, `tests.test_gate_page`, `tests.test_hubs` |
| The breadcrumb Home > arena > app, Go to, the retired redirect, the Main copy chips | `tools/web_public/olympus/gate-nav.js` (loaded by `agora-ui.js`, `a11y.js` or the page) | `tests.test_olympus_nav` |
| The arena pages | `tools/web_public/hub/arena.html` + `arena.js` + `arena.css` | `tests.test_olympus_nav` |
| Home: the 6 arenas, Everything else, the All apps row | `tools/web_public/gate/index.html`, `gate/arenas.js`, `gate/gate.js` | `tests.test_gate_page` |
| The hubs (an older grouping; their tabs still show in search) | `tools/web_public/hub/` | `tests.test_hubs` |
| App registry (Jarvis switcher, launcher) | `tools/web_public/jarvis/apps.js` -> `olympus/apps-list.js` | `tests.test_apps_list` |
| The four doors (2026-11-18; hidden on Home since the arenas, kept for old links) | `tools/web_public/olympus/doors.js`, `hub/doors.html` | `tests.test_apps_list` (part d) |
| This map | `tools/olympus_map_build.py` -> `docs/OLYMPUS_MAP.md` | `tests.test_olympus_map` |
"""
FALLBACK_DATA = "bundled fixture / its own files"
# where a folded app lives now (2026-11-20). Sources: research/handoff/2026-11-20/nqdash3/LEAD_WIRES.md (Ares, Kairos, Chronos -> NQ; Odeon,
# Why -> Trading), kalshi/LEAD_WIRES_merge.md (Sibyl, Kalshi City -> Dionysus), arenas/REPORT.md (folded-in links: Journal, Helios, Hera,
# Pnyx). [old id, the page it lives on now (site path), the card / what is there]. The old URL always still works.
MERGED = [
    ("ares", "nq/#gateCard", "NQ page: GO / WAIT / HALT per account"),
    ("kairos", "nq/#dayCard", "NQ page: the bots' day strip (windows, now line, trades)"),
    ("chronos", "nq/#pastCard", "NQ page: the last 8 trading days, each opens its replay"),
    ("odeon", "trading/#reelsCard", "Trading: 8 trade reels, live first"),
    ("why", "trading/#whyCard", "Trading: why trades win and lose, per bot"),
    ("sibyl", "dionysus/", "Kalshi desk: paper picks"),
    ("kalshicity", "dionysus/", "Kalshi desk: the edges map"),
    ("apollo", "journal/", "Journal: the week review"),
    ("epilogue", "journal/", "Journal: the week in 60 seconds"),
    ("kratos", "journal/", "Journal: habits and what they cost"),
    ("nemesis", "journal/", "Journal: losing trades"),
    ("pythia", "helios/", "Morning brief: the market-risk calendar, next 5 days"),
    ("delphi", "helios/", "Morning brief: the plan and go / no-go"),
    ("forum", "helios/", "Morning brief: the market morning notes"),
    ("plutus", "hera/", "Payout plan"),
    ("argo", "hera/", "Payout plan"),
    ("labyrinth", "pnyx/", "Rules and size calculator: eval sizing"),
]
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
    want = "money" if group == "money" else "zeus" if group == "trading" else "more"
    return next((t for z, t, _ in zones if z == want), "More")


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


def parse_archive(src):
    """the ids in olympus/doors.js ARCHIVE (folded under "Archive" at the end of their door)."""
    m = re.search(r"var ARCHIVE = \[(.*?)\];", src, re.S)
    return re.findall(r"'([a-z0-9_-]+)'", m.group(1)) if m else []


def shown_part(apps, zones):
    """Open first vs Archive, per door, + where each merged app lives now (names only: no `(id)` cells, the app table stays the one list)."""
    arc = set(parse_archive(read(os.path.join(WEB, "olympus", "doors.js"))))
    names = {a[0]: a[1] for a in apps}
    out = ["", "## What each door opens first, and what is folded under Archive (2026-11-20)", "",
           "The Doors page, the launcher and Jarvis's switcher show a door's visible apps first and fold the rest under \"Archive\" at its end",
           "(`tools/web_public/olympus/doors.js` ARCHIVE). Nothing is deleted: every URL works and search finds every app.", "",
           "| Door | Open first | Archive (folded) |", "|---|---|---|"]
    for zid, title, _ in zones:
        ids = sorted((a[0] for a in apps if zone_of(a[0], a[2], zones) == title), key=lambda i: names[i].lower())
        vis = ", ".join(names[i] for i in ids if i not in arc) or "-"
        hid = ", ".join(names[i] for i in ids if i in arc) or "-"
        out.append(f"| {title} | {vis} | {hid} |")
    nv = sum(1 for a in apps if a[0] not in arc)
    out += ["", f"{nv} apps open first, {len(apps) - nv} folded under Archive.", "",
            "## Merged: where a folded app lives now", "",
            "| Old app | Now on | What is there |", "|---|---|---|"]
    for aid, where, what in MERGED:
        if aid in names:
            out.append(f"| {names[aid]} | {where} | {what} |")
    return "\n".join(out) + "\n"


CAT_JS = r"""
const C = require(process.argv[1]);
const o = { arenas: C.arenas.map((x) => ({ id: x.id, name: x.name, front: x.front, line: x.line, count: x.count })), app: {}, label: {}, replace: {}, facts: {}, retired: C.RETIRED };
C.apps.forEach((a) => { const x = C.arenaOf(a.id); o.app[a.id] = x ? x.id : 'else'; o.label[a.id] = a.label; });
C.RETIRED.forEach((id) => { const r = C.replacementOf(id); if (r) o.replace[id] = r.id; });
Object.keys(C.FACTS).forEach((k) => { o.facts[k] = { app: C.FACTS[k].app, path: C.FACTS[k].path || '', name: C.FACTS[k].name || '', label: C.FACTS[k].label, also: C.FACTS[k].also }; });
console.log(JSON.stringify(o));
"""
ALIAS = {"zenith": "today"}     # apps.js id -> its catalog id


def catalog():
    """the arenas from olympus/gate-catalog.js (node); None without node"""
    import json
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        return None
    r = subprocess.run([node, "-e", CAT_JS, os.path.join(WEB, "olympus", "gate-catalog.js")], capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 else None


def arena_parts(apps, cat):
    names = {a[0]: a[1] for a in apps}
    lab = cat["label"]
    nm = lambda i: lab.get(i) or names.get(i) or i  # noqa: E731
    out = ["", "## The arenas", "", "| Arena | Front page (the Home tile) | Live apps | Its page |", "|---|---|---|---|"]
    for x in cat["arenas"]:
        front = f"{nm(x['front'])} (`{x['front']}/`)" if x["front"] else "-"
        out.append(f"| **{x['name']}** | {front} | {x['count']} | `hub/arena.html?a={x['id']}` |")
    out += ["", "## Retired: where each old app sends you now", "",
            "Retired apps are not on Home, in search or in A to Z. Their old links open the replacement (`?stay=1` keeps the old page).", "",
            "| Retired | Opens |", "|---|---|"]
    for i in sorted(cat["replace"]):
        out.append(f"| {names.get(i, i)} (`{i}`) | {nm(cat['replace'][i])} (`{cat['replace'][i]}`) |")
    out += ["", "## One place per fact", "", "| Fact | The one place | Also shown on (a 'Main copy' chip links back) |", "|---|---|---|"]
    for k, f in cat["facts"].items():
        out.append(f"| {f['label']} | {f.get('name') or nm(f['app'])} (`{f.get('path') or f['app']}`) | {', '.join(sorted(f['also']))} |")
    out += ["", "## Merged earlier: where a folded app's content lives now", "", "| Old app | Now on | What is there |", "|---|---|---|"]
    for aid, where, what in MERGED:
        if aid in names:
            out.append(f"| {names[aid]} | {where} | {what} |")
    return "\n".join(out) + "\n"


def build():
    apps = parse_apps(read(os.path.join(WEB, "jarvis", "apps.js")))
    cat = catalog()
    if cat is None:      # no node: the old door view, so the file still builds
        zones = parse_zones(read(os.path.join(WEB, "atlas", "atlas.js")))
        cat = {"arenas": [{"id": z, "name": t, "front": "", "line": "", "count": len(ids)} for z, t, ids in zones], "app": {}, "label": {}, "replace": {}, "facts": {}}
        arena_name = lambda aid, group: zone_of(aid, group, zones)  # noqa: E731
    else:
        an = {x["id"]: x["name"] for x in cat["arenas"]}
        arena_name = lambda aid, group: an.get(cat["app"].get(ALIAS.get(aid, aid), "else"), "Everything else")  # noqa: E731
    order = {x["name"]: i for i, x in enumerate(cat["arenas"])}
    rows = []
    for aid, name, group, sub in apps:
        ar = arena_name(aid, group)
        ret = " (retired)" if aid in set(cat.get("retired") or []) else ""
        rows.append((order.get(ar, 99), aid, f"| {name} (`{aid}`){ret} | {ar} | {group} | {words8(sub)} | {reads_of(aid)} | {test_of(aid)} |"))
    rows.sort(key=lambda r: (r[0], r[1]))
    table = ["## Every app", "", "| App (id) | Arena | Group | What it is | Data it reads | Test |", "|---|---|---|---|---|---|"] + [r[2] for r in rows]
    n = len(apps)
    foot = f"\n{n} apps. Rebuild the registry list after editing `jarvis/apps.js` or `olympus.js`: `python tools/apps_list_build.py`; recount: `python tools/apps_list_build.py --check`.\n"
    return HEAD + arena_parts(apps, cat) + "\n" + "\n".join(table) + "\n" + foot + FOOT


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
    z = parse_zones("const zones = [\n { id:'zeus', title:'ZEUS Trading', colour:'#c8a24a', note:'x', ids:['zenith','oracle'] },\n { id:'money', title:'Money', colour:'#1', note:'y', ids:['hera'] },\n { id:'more', title:'More', colour:'#2', note:'z', ids:[] }\n];")
    ck("zones: id, title, ids", z == [("zeus", "ZEUS Trading", ["zenith", "oracle"]), ("money", "Money", ["hera"]), ("more", "More", [])], z)
    ck("door: listed, else by group (money -> Money, trading -> ZEUS Trading, life -> More)", zone_of("zenith", "trading", z) == "ZEUS Trading" and zone_of("new", "money", z) == "Money" and zone_of("new", "life", z) == "More" and zone_of("new", "trading", z) == "ZEUS Trading")
    ck("8 words: longer sentences are cut, trailing punctuation dropped, short ones kept", words8("The word on the street: releases, and NQ's past moves on them") == "The word on the street: releases, and NQ's" and words8("Day plan") == "Day plan" and words8("") == "")
    ck("the unknown app has the fallbacks (bundled data, the kit test)", reads_of("zzz-none") == FALLBACK_DATA and test_of("zzz-none") == "covered by `tests.test_olympus_kit`")
    real = build()
    n = len(parse_apps(read(os.path.join(WEB, "jarvis", "apps.js"))))
    ck("the real map has one row per BUILT_INS app and the arenas", real.count("\n| ") >= n and n > 30 and all(f"| {d} |" in real for d in ("NQ Bot", "Business", "Kalshi", "Everything else")), n)
    ck("deterministic", build() == real)
    ck("the map has the arenas, retired -> replacement, one place per fact and the merged list",
       "## The arenas" in real and "| Delphi (`delphi`) |" in real and "## One place per fact" in real and "| Odeon | trading/#reelsCard |" in real)
    print(f"\n{'ALL PASS' if not bad else str(len(bad)) + ' FAILED'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
