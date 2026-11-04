#!/usr/bin/env python3
"""Give every OLYMPUS app page the shared kit's two small tags, idempotently (docs/OLYMPUS_A11Y.md, the per-app intro).

    python tools/add_kit_tags.py                  dry run (the default): print what is missing, change nothing
    python tools/add_kit_tags.py --apply          insert the missing tags
    python tools/add_kit_tags.py --check          exit 1 when a page that loads the kit lacks a tag
    python tools/add_kit_tags.py --shell          also print the kit files the apps load that Jarvis' worker does not save (ready to paste)
    options: --with-css (also the optional a11y.css link)   --root DIR (tests)

Pages: every app in olympus/apps-list.js (<path>index.html; the root page uses `olympus/...`, an app folder `../olympus/...`) plus jarvis/, kalshi/,
bridge/ and pc/ when they exist. A page that does not load the kit (no olympus/olympus.js script tag) is SKIPPED and listed: it needs the full kit first.
For a page that does, on their own new lines immediately after the olympus.js tag (same indentation, so a merge of other edits to nearby lines
conflicts as little as possible), each only when missing (found by the src substring, before or after, with or without ?v=):
    <script src="../olympus/intro-app.js?v=i1" defer></script>      (the per-app intro)
    <script src="../olympus/a11y.js" defer></script>                (text size, contrast, focus, names, live regions, motion)
    <link rel="stylesheet" href="../olympus/a11y.css">              (only with --with-css; the script adds it anyway)
Never touches a page that has them all, never duplicates, keeps the file's line endings; writes nothing in dry-run / --check.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

WEB = "tools/web_public"
EXTRA_PAGES = ["jarvis", "kalshi", "bridge", "pc"]
KIT_TAG = re.compile(r"""<script\b[^>]*\bsrc=(["'])([^"']*?)olympus/olympus\.js[^"']*\1[^>]*>\s*</script>""", re.I)
INTRO_V = "i1"


def app_paths(web):
    """the folders of olympus/apps-list.js ('' = the root page), then the extra pages that exist"""
    paths = []
    fp = os.path.join(web, "olympus", "apps-list.js")
    if os.path.isfile(fp):
        with open(fp, encoding="utf-8") as fh:
            paths = re.findall(r'"path":\s*"([^"]*)"', fh.read())
    for e in EXTRA_PAGES:
        if e + "/" not in paths:
            paths.append(e + "/")
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def page_plan(text, with_css=False):
    """(status, tags to add, prefix) for one page's text. status: 'ok' | 'missing' | 'nokit'"""
    m = KIT_TAG.search(text)
    if not m:
        return "nokit", [], ""
    prefix = m.group(2)                                                  # '../' + 'olympus/' ... up to the kit folder: '../' / './' / ''
    base = prefix + "olympus/"
    add = []
    if "intro-app.js" not in text:
        add.append(f'<script src="{base}intro-app.js?v={INTRO_V}" defer></script>')
    if "olympus/a11y.js" not in text:
        add.append(f'<script src="{base}a11y.js" defer></script>')
    if with_css and "olympus/a11y.css" not in text:
        add.append(f'<link rel="stylesheet" href="{base}a11y.css">')
    return ("missing" if add else "ok"), add, base


def insert_after_kit(text, add):
    m = KIT_TAG.search(text)
    nl = "\r\n" if "\r\n" in text else "\n"
    ls = text.rfind("\n", 0, m.start()) + 1
    before = text[ls:m.start()]
    indent = before if not before.strip() else re.match(r"[ \t]*", before).group(0)
    eol = text.find("\n", m.end())
    rest = text[m.end(): eol if eol >= 0 else len(text)]
    block = "".join(nl + indent + t for t in add)
    if rest.strip():                                                    # something else shares the line: it moves to its own line after the new tags
        return text[: m.end()] + block + nl + indent + text[m.end():].lstrip(" \t")
    return text[: m.end()] + block + text[m.end():]


def scan(root, with_css=False):
    web = os.path.join(root, *WEB.split("/"))
    rows = []
    for p in app_paths(web):
        rel = f"{WEB}/{p}index.html"
        fp = os.path.join(root, *rel.split("/"))
        if not os.path.isfile(fp):
            rows.append({"page": rel, "status": "absent", "add": [], "fp": fp})
            continue
        with open(fp, encoding="utf-8", newline="") as fh:
            text = fh.read()
        st, add, _ = page_plan(text, with_css)
        rows.append({"page": rel, "status": st, "add": add, "fp": fp, "text": text})
    return rows


def kit_files_needed(root):
    """the olympus/ files the apps load (script / link / import / lazy fx files) that Jarvis' worker should hold for offline"""
    web = os.path.join(root, *WEB.split("/"))
    need = set()
    pat = re.compile(r"""olympus/([A-Za-z0-9_.-]+\.(?:js|css))(\?v=[A-Za-z0-9]+)?""")
    for dp, dns, fns in os.walk(web):
        dns[:] = [d for d in dns if d not in ("node_modules", "three-addons", "fx", "jarvis")]
        if os.path.relpath(dp, web).split(os.sep)[0] in ("olympus",):
            continue
        for fn in fns:
            if fn.endswith((".html", ".js", ".mjs")) and "three.module" not in fn:
                fp = os.path.join(dp, fn)
                if os.path.getsize(fp) > 1_500_000:
                    continue
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    for m in pat.finditer(fh.read()):
                        need.add((m.group(1), m.group(2) or ""))
    kit = os.path.join(web, "olympus")
    if os.path.isdir(kit):                                              # what the kit itself loads on demand
        for fn in sorted(os.listdir(kit)):
            if fn.endswith(".js"):
                with open(os.path.join(kit, fn), encoding="utf-8", errors="ignore") as fh:
                    src = fh.read()
                for m in re.finditer(r"""['"](fx-[a-z0-9]+\.js|a11y\.css)(\?v=[A-Za-z0-9]+)?['"]""", src):
                    need.add((m.group(1), m.group(2) or ""))
    return need


def jarvis_shell(root):
    fp = os.path.join(root, *WEB.split("/"), "jarvis", "sw.js")
    if not os.path.isfile(fp):
        return set(), ""
    with open(fp, encoding="utf-8") as fh:
        sw = fh.read()
    m = re.search(r"const SHELL = \[([^\]]*)\]", sw)
    return {s.split("?")[0] for s in re.findall(r"'([^']+)'", m.group(1))} if m else set(), sw


def shell_missing(root):
    have, _ = jarvis_shell(root)
    web = os.path.join(root, *WEB.split("/"))
    vers = {}
    for name, v in kit_files_needed(root):
        vers.setdefault(name, set()).add(v)
    out = []
    for name in sorted(vers):
        if f"../olympus/{name}" in have or not os.path.isfile(os.path.join(web, "olympus", name)):
            continue
        v = next(iter(vers[name])) if len(vers[name]) == 1 else ""      # one query everywhere: keep it; mixed: the bare name (the worker matches ignoring the query)
        out.append(f"'../olympus/{name}{v}'")
    return out


def main(argv=None):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description="add the kit's intro + a11y tags to every app page that loads the kit")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--with-css", action="store_true")
    ap.add_argument("--shell", action="store_true", help="print the kit files Jarvis' worker does not save yet")
    ap.add_argument("--root", default=here)
    a = ap.parse_args(argv)
    rows = scan(a.root, a.with_css)
    todo = [r for r in rows if r["status"] == "missing"]
    nokit = [r for r in rows if r["status"] == "nokit"]
    w = max([len(r["page"]) for r in rows] + [4])
    print(f"{'page':<{w}}  status    add")
    print(f"{'-' * w}  --------  {'-' * 40}")
    for r in rows:
        what = ", ".join(re.search(r"olympus/([\w.-]+)", t).group(1) for t in r["add"]) if r["add"] else ""
        print(f"{r['page']:<{w}}  {r['status']:<8}  {what}")
    print(f"\n{len(todo)} page(s) missing a tag, {sum(1 for r in rows if r['status'] == 'ok')} complete, {len(nokit)} without the kit (skipped), "
          f"{sum(1 for r in rows if r['status'] == 'absent')} absent.")
    if nokit:
        print("pages with NO olympus.js tag (they need the full kit first): " + ", ".join(r["page"] for r in nokit))
    miss = shell_missing(a.root)
    if a.shell or miss:
        print("Jarvis worker SHELL entries to add (paste into jarvis/sw.js SHELL; bump its CACHE): " + (", ".join(miss) if miss else "none"))
    if a.apply:
        for r in todo:
            new = insert_after_kit(r["text"], r["add"])
            with open(r["fp"], "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
        print(f"applied: {len(todo)} page(s) written.")
        return 0
    if a.check:
        if todo:
            print("CHECK FAILED: pages are missing kit tags (run tools/add_kit_tags.py --apply).")
            return 1
        print("check ok.")
        return 0
    print("dry run: nothing written (use --apply).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
