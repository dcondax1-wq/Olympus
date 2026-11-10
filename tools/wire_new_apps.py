#!/usr/bin/env python3
"""WIRE NEW APPS: does the lead's wiring of tools/new_apps.json safely, in one go (2026-11-10).

  python tools/wire_new_apps.py --dry-run     print a unified diff of what would change, write nothing
  python tools/wire_new_apps.py --check       exit 1 if any app that has a folder is missing from any of the six files (prints which)
  python tools/wire_new_apps.py --apply       write the six files, then run tools/apps_list_build.py
  options: --root DIR (another copy of the repo, used by the tests)   --list FILE (another app list)

For every app in tools/new_apps.json whose folder tools/web_public/<id>/index.html exists (others are listed and skipped), it adds what is missing to:
  (a) tools/web_public/jarvis/apps.js          BUILT_INS row, inserted before the clio row
  (b) tools/web_public/olympus/olympus.js      the APPS entry and the AMBIENT bed
  (c) tools/build_web_dashboard.py             the app tuple of the site build ("for app in (...)")
  (d) tools/web_public/sw.js                   OTHER_APPS
  (e) tools/web_public/olympus/intro-app.js    FLAVOUR
  (f) tools/web_public/jarvis/transitions.js   REGISTRY row, inserted before the clio row
Idempotent (an id already in a file is skipped there, so a second run changes nothing), never touches an existing row, keeps each file's style, and REFUSES (exit 2,
nothing written) when an anchor is not found or an entry looks wrong: it never guesses. It does not bump caches (sw.js CACHE) or the pinned test strings: that stays with the lead.
Writes only the six files above (and what apps_list_build.py writes). Stdlib only.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIST = os.path.join(HERE, "new_apps.json")
WEB = os.path.join("tools", "web_public")
FILES = {
    "apps": os.path.join(WEB, "jarvis", "apps.js"),
    "olympus": os.path.join(WEB, "olympus", "olympus.js"),
    "build": os.path.join("tools", "build_web_dashboard.py"),
    "sw": os.path.join(WEB, "sw.js"),
    "intro": os.path.join(WEB, "olympus", "intro-app.js"),
    "trans": os.path.join(WEB, "jarvis", "transitions.js"),
}
LABEL = {"apps": "jarvis/apps.js BUILT_INS", "olympus": "olympus.js APPS + AMBIENT", "build": "build_web_dashboard.py app tuple", "sw": "sw.js OTHER_APPS", "intro": "intro-app.js FLAVOUR", "trans": "transitions.js REGISTRY"}
GROUPS = ("trading", "money", "life")


class Refuse(Exception):
    """An anchor was not found or an entry is wrong: nothing is written."""


WARN: list = []   # things that are harmless but worth a look (the app still gets wired): an unknown intro scene falls back to the stars, an unknown transition to a fade


# ------------------------------------------------------------------------------------------------ small helpers
def q(s: str) -> str:
    """A JS string literal in the files' own style: single quotes, double quotes when the text has an apostrophe."""
    s = str(s)
    if "'" not in s and "\\" not in s and "\n" not in s:
        return "'" + s + "'"
    if '"' not in s and "\\" not in s and "\n" not in s:
        return '"' + s + '"'
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ") + "'"


def read(root: str, key: str) -> str:
    p = os.path.join(root, FILES[key])
    if not os.path.isfile(p):
        raise Refuse(f"{FILES[key]} not found")
    with open(p, encoding="utf-8", newline="") as fh:
        t = fh.read()
    if "\r" in t:
        raise Refuse(f"{FILES[key]} has Windows line endings: not touching it")
    return t


def need(m, what: str, key: str):
    if not m:
        raise Refuse(f"{FILES[key]}: could not find {what}")
    return m


def validate(a: dict) -> None:
    i = a.get("id", "?")
    if not re.fullmatch(r"[a-z][a-z0-9]{1,24}", str(i)):
        raise Refuse(f"app id {i!r} is not a plain lowercase id")
    for k in ("name", "group", "accent", "glyph", "description", "ambient"):
        if not isinstance(a.get(k), str) or not a[k].strip():
            raise Refuse(f"{i}: '{k}' is missing")
    if a["group"] not in GROUPS:
        raise Refuse(f"{i}: group {a['group']!r} is not one of {GROUPS}")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", a["accent"]):
        raise Refuse(f"{i}: accent {a['accent']!r} is not #rrggbb")
    f = a.get("flavour")
    if not (isinstance(f, list) and len(f) == 3 and all(isinstance(x, str) and x for x in f)):
        raise Refuse(f"{i}: flavour must be [scene, tagline, sound]")
    t = a.get("transition")
    if not (isinstance(t, dict) and isinstance(t.get("kind"), str) and isinstance(t.get("ms"), int) and (t.get("n") is None or isinstance(t["n"], int))):
        raise Refuse(f"{i}: transition must be {{kind, ms, n?}}")


# ------------------------------------------------------------------------------------------------ the six edits (text in -> text out, plus the ids added)
def edit_apps(t: str, apps: list):
    have = set(re.findall(r"^\s*app\('(\w+)',", t, re.M))
    todo = [a for a in apps if a["id"] not in have]
    if not todo:
        return t, []
    m = need(re.search(r"^  app\('clio', .*\n", t, re.M), "the clio row (the insert point)", "apps")
    rows = "".join(f"  app({q(a['id'])}, {q(a['name'])}, {q(a['group'])}, {q(a['accent'])}, {q(a['description'])}, {{ glyph: {q(a['glyph'])} }}),\n" for a in todo)
    return t[:m.start()] + rows + t[m.start():], [a["id"] for a in todo]


def edit_olympus(t: str, apps: list):
    added = []
    m = need(re.search(r"^  var APPS = \{\n", t, re.M), "'var APPS = {'", "olympus")
    end = need(re.search(r"^  \};", t[m.end():], re.M), "the end of APPS", "olympus")
    block = t[m.end():m.end() + end.start()]
    todo = [a for a in apps if not re.search(r"(?<![\w])" + a["id"] + r":\s*\[", block)]
    if todo:
        line = "    " + " ".join(f"{a['id']}: [{q(a['name'])}, {q(a['glyph'])}, {q(a['accent'])}]," for a in todo) + "\n"
        t = t[:m.end()] + line + t[m.end():]
        added += [a["id"] for a in todo]
    am = need(re.search(r"^(  var AMBIENT = \{ )", t, re.M), "'var AMBIENT = { '", "olympus")
    stmt = need(re.search(r"\};", t[am.end():]), "the end of AMBIENT", "olympus")
    body = t[am.end():am.end() + stmt.start()]
    todo2 = [a for a in apps if not re.search(r"(?<![\w])" + a["id"] + r":\s*'", body)]
    if todo2:
        ins = "".join(f"{a['id']}: {q(a['ambient'])}, " for a in todo2)
        t = t[:am.end()] + ins + t[am.end():]
        added += [a["id"] for a in todo2 if a["id"] not in added]
    return t, added


def edit_build(t: str, apps: list):
    m = need(re.search(r"^(\s+for app in \()(\"jarvis\"[^)\n]*)(\):)$", t, re.M), 'the site build loop (for app in ("jarvis", ...):)', "build")
    have = set(re.findall(r'"(\w+)"', m.group(2)))
    todo = [a for a in apps if a["id"] not in have]
    if not todo:
        return t, []
    new = m.group(1) + m.group(2) + "".join(f', "{a["id"]}"' for a in todo) + m.group(3)
    return t[:m.start()] + new + t[m.end():], [a["id"] for a in todo]


def edit_sw(t: str, apps: list):
    m = need(re.search(r"^(const OTHER_APPS = \[)([^\]\n]*)(\];)", t, re.M), "'const OTHER_APPS = [...]'", "sw")
    have = set(re.findall(r"'(\w+)/'", m.group(2)))
    todo = [a for a in apps if a["id"] not in have]
    if not todo:
        return t, []
    new = m.group(1) + m.group(2) + "".join(f", '{a['id']}/'" for a in todo) + m.group(3)
    return t[:m.start()] + new + t[m.end():], [a["id"] for a in todo]


def edit_intro(t: str, apps: list):
    m = need(re.search(r"^  var FLAVOUR = \{\n", t, re.M), "'var FLAVOUR = {'", "intro")
    end = need(re.search(r"^  \};", t[m.end():], re.M), "the end of FLAVOUR", "intro")
    block = t[m.end():m.end() + end.start()]
    todo = [a for a in apps if not re.search(r"(?<![\w])" + a["id"] + r":\s*\[", block)]
    if not todo:
        return t, []
    scenes = set(re.findall(r"^  SC\.(\w+) =", t, re.M))
    for a in todo:
        if scenes and a["flavour"][0] not in scenes:
            WARN.append(f"{a['id']}: intro scene {a['flavour'][0]!r} does not exist in intro-app.js (SC.*), so the intro shows the stars instead")
    rows = "".join(f"    {a['id']}: [{q(a['flavour'][0])}, {q(a['flavour'][1])}, {q(a['flavour'][2])}],\n" for a in todo)
    return t[:m.end()] + rows + t[m.end():], [a["id"] for a in todo]


def edit_trans(t: str, apps: list):
    m = need(re.search(r"^export const REGISTRY = \{\n", t, re.M), "'export const REGISTRY = {'", "trans")
    end = need(re.search(r"^\};", t[m.end():], re.M), "the end of REGISTRY", "trans")
    block = t[m.end():m.end() + end.start()]
    todo = [a for a in apps if not re.search(r"^\s*" + a["id"] + r":\s*\{", block, re.M)]
    if not todo:
        return t, []
    km = re.search(r"^export const KINDS = \{\n(.*?)^\};", t, re.M | re.S)
    kinds = set(re.findall(r"^  (\w+):", km.group(1), re.M)) if km else set()
    for a in todo:
        if kinds and a["transition"]["kind"] not in kinds:
            WARN.append(f"{a['id']}: transition kind {a['transition']['kind']!r} is not in transitions.js KINDS, so it gets the plain fade")
    anchor = need(re.search(r"^  clio:\s+\{.*\n", t[m.end():], re.M), "the clio row (the insert point)", "trans")
    at = m.end() + anchor.start()
    rows = ""
    for a in todo:
        tr = a["transition"]
        rows += f"  {(a['id'] + ':').ljust(12)}{{ kind: {(q(tr['kind']) + ',').ljust(17)}ms: {tr['ms']}" + (f", n: {tr['n']}" if tr.get("n") is not None else "") + " },\n"
    return t[:at] + rows + t[at:], [a["id"] for a in todo]


EDITS = {"apps": edit_apps, "olympus": edit_olympus, "build": edit_build, "sw": edit_sw, "intro": edit_intro, "trans": edit_trans}


def check_beds(root: str, apps: list) -> None:
    """The ambient bed must be one the sound kit has (when the kit's table can be read)."""
    p = os.path.join(root, WEB, "olympus", "sfx.js")
    if not os.path.isfile(p):
        return
    t = open(p, encoding="utf-8").read()
    m = re.search(r"var BEDS = \{\n(.*?)\n    \};", t, re.S)
    beds = set(re.findall(r"^\s{6}(\w+):", m.group(1), re.M)) if m else set()
    for a in apps:
        if beds and a["ambient"] not in beds:
            WARN.append(f"{a['id']}: ambient bed {a['ambient']!r} is not in olympus/sfx.js BEDS, so the app has no sound bed")


# ------------------------------------------------------------------------------------------------ the plan
def load_list(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        raise Refuse(f"cannot read {path}: {e}")
    apps = d.get("apps") if isinstance(d, dict) else None
    if not isinstance(apps, list):
        raise Refuse(f"{path}: no 'apps' list")
    seen = set()
    for a in apps:
        validate(a)
        if a["id"] in seen:
            raise Refuse(f"{a['id']} is listed twice")
        seen.add(a["id"])
    return apps


def plan(root: str, list_path: str):
    """-> (changes {key: (old, new, ids)}, ready ids, skipped ids). Raises Refuse. Reads only."""
    del WARN[:]
    apps = load_list(list_path)
    ready = [a for a in apps if os.path.isfile(os.path.join(root, WEB, a["id"], "index.html"))]
    skipped = [a["id"] for a in apps if a not in ready]
    check_beds(root, ready)
    changes = {}
    for key, fn in EDITS.items():
        old = read(root, key)
        new, ids = fn(old, ready)
        if ids:
            changes[key] = (old, new, ids)
    return changes, [a["id"] for a in ready], skipped


def diff_of(root: str, changes: dict) -> str:
    out = []
    for key, (old, new, _ids) in changes.items():
        out.extend(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), "a/" + FILES[key].replace(os.sep, "/"), "b/" + FILES[key].replace(os.sep, "/"), n=1))
    return "".join(out)


def apply(root: str, changes: dict) -> None:
    for key, (old, new, _ids) in changes.items():
        p = os.path.join(root, FILES[key])
        if read(root, key) != old:
            raise Refuse(f"{FILES[key]} changed while planning: run again")
    for key, (old, new, _ids) in changes.items():
        p = os.path.join(root, FILES[key])
        tmp = p + ".wire.tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(new)
        os.replace(tmp, p)


def summary(changes: dict, ready: list, skipped: list) -> str:
    lines = [f"apps in the list with a folder: {len(ready)}" + (f" ({', '.join(ready)})" if ready else ""), f"skipped (no folder / no index.html yet): {', '.join(skipped) or 'none'}"]
    if not changes:
        lines.append("nothing to add: every ready app is already wired in all six files")
    for key, (_o, _n, ids) in changes.items():
        lines.append(f"  {LABEL[key]}: + {', '.join(ids)}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Wire the new OLYMPUS apps (tools/new_apps.json) into the six shared files, idempotently.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="print a unified diff, write nothing")
    g.add_argument("--check", action="store_true", help="exit 1 if anything is missing")
    g.add_argument("--apply", action="store_true", help="write the six files, then run tools/apps_list_build.py")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--list", default=None)
    a = ap.parse_args(argv)
    list_path = a.list or (os.path.join(a.root, "tools", "new_apps.json") if a.root != ROOT else LIST)
    try:
        changes, ready, skipped = plan(a.root, list_path)
    except Refuse as e:
        print(f"REFUSED: {e}\nNothing was written.", file=sys.stderr)
        return 2
    print(summary(changes, ready, skipped))
    for w in sorted(set(WARN)):
        print("  NOTE: " + w)
    if a.dry_run:
        d = diff_of(a.root, changes)
        if d:
            print("\n" + d)
        return 0
    if a.check:
        if changes:
            print("\nCHECK: not wired yet (run --apply)")
            return 1
        print("\nCHECK: ok")
        return 0
    try:
        apply(a.root, changes)
    except Refuse as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    if not changes:
        return 0
    print(f"\nwrote {len(changes)} file(s)")
    build = os.path.join(a.root, "tools", "apps_list_build.py")
    if os.path.isfile(build):
        r = subprocess.run([sys.executable, build], cwd=a.root, capture_output=True, text=True, timeout=120)
        print((r.stdout + r.stderr).strip()[-600:])
        if r.returncode:
            print("apps_list_build.py failed: fix and run it again", file=sys.stderr)
            return 3
    print("Not done by this tool: bump the sw.js CACHE and the pinned strings in the zenith / hub tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
