"""Site self-check (job 23, 2026-11-04): after tools/build_web_dashboard.py built the site, say LOUDLY in the log when an expected file is missing.

Why: tonight a file that was missing from the sparse checkout (or a copy that failed inside a try/except in the build) was skipped
silently and the publish went on without it. This only READS: it never changes what is built or published.

    python tools/site_selfcheck.py --site site [--src tools/web_public] [--root .]     exit 1 when anything is missing or broken

It prints a table (what, expected, found, state), a GitHub Actions ::error:: line per problem (red in the run's annotations),
and the same table to $GITHUB_STEP_SUMMARY. The workflow step is `continue-on-error: true`: the step turns red, the publish is not touched.

Checks
  1. every OLYMPUS app folder the build copies (the list is read from build_web_dashboard.py): every file and subfolder file of
     tools/web_public/<app>/ is in <site>/<app>/ and not empty
  2. the top-level site files (index.html, sw.js, the .js / .css / manifest of tools/web_public/)
  3. must-haves by name: pc/move_bot.ps1 (equal to scripts/move_bot.ps1) and the FRESH_START files, bridge/status.json (valid JSON),
     the Cities card + data, the Kalshi City files, data.json / home.json (valid JSON), the Planner (planner/index.html), the Jarvis
     files the shell loads
  4. the sources the build reads from the sparse checkout (scripts/move_bot.ps1, scripts/add_planner.sh, tools/kalshi_kit/public)
  5. sparse-checkout gaps: a file the build / monitor read by a literal path that the workflow's sparse-checkout list does not bring
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# must-haves by name: (path under the site, why, kind) ; kind 'json' = also valid JSON
MUST = [
    ("pc/move_bot.ps1", "the PC fresh-start launcher downloads it (copy of scripts/move_bot.ps1)", ""),
    ("pc/FRESH_START.ps1", "the one-line PC fresh start", ""),
    ("pc/FRESH_START.bat", "the PC fresh start", ""),
    ("pc/index.html", "the PC page", ""),
    ("bridge/status.json", "live ChatGPT-link state (tools/bridge_sync.py)", "json"),
    ("bridge/jarvis.json", "the Bridge card in Jarvis", "json"),
    ("bridge/index.html", "the Bridge page", ""),
    ("cities/index.html", "the Cities page", ""),
    ("cities/app.js", "the Cities app", ""),
    ("cities/cities.json", "the Cities data", "json"),
    ("cities/jarvis.json", "the Cities card in Jarvis", "json"),
    ("kalshicity/index.html", "the Kalshi City page", ""),
    ("kalshicity/kalshicity.js", "the Kalshi City app", ""),
    ("kalshicity/edges.json", "the Kalshi City edges", "json"),
    ("kalshicity/ledger.json", "the Kalshi City ledger", "json"),
    ("kalshicity/learned.json", "the Kalshi City lessons", "json"),
    ("kalshicity/jarvis.json", "the Kalshi City card in Jarvis", "json"),
    ("kalshi/index.html", "the Kalshi page", ""),
    ("datacity/index.html", "Data City", ""),
    ("jarvis/index.html", "Jarvis", ""),
    ("jarvis/sw.js", "Jarvis's worker", ""),
    ("jarvis/backdrop.js", "the Jarvis home backdrop", ""),
    ("jarvis/home3d.js", "the Jarvis living home", ""),
    ("jarvis/briefing.js", "the Jarvis morning briefing", ""),
    ("olympus/render.js", "the OLYMPUS render core", ""),
    ("olympus/materials.js", "the OLYMPUS materials", ""),
    ("olympus/three-addons/EffectComposer.js", "the render core's vendored addons", ""),
    ("index.html", "Zenith", ""),
    ("sw.js", "Zenith's worker", ""),
    ("data.json", "the dashboard data", "json"),
    ("home.json", "the Jarvis home feed", "json"),
    ("planner/index.html", "the Planner (scripts/add_planner.sh keeps it across the publish)", ""),
]
# sources the build reads outside tools/web_public (they come from the workflow's sparse checkout)
SOURCES = [
    ("scripts/move_bot.ps1", "copied to <site>/pc/move_bot.ps1"),
    ("scripts/add_planner.sh", "keeps the Planner in the publish"),
    ("tools/kalshi_kit/public", "the Kalshi kit's public files (folder)"),
    ("tools/build_web_dashboard.py", "the build itself"),
]


def app_list(build_py: str) -> list:
    try:
        with open(build_py, encoding="utf-8") as fh:
            m = re.search(r"for app in \(([^)]*)\):", fh.read())
        if m:
            return re.findall(r'"([a-z0-9_]+)"', m.group(1))
    except OSError:
        pass
    return ["jarvis", "kalshi", "datacity", "olympus", "bridge", "cities", "kalshicity"]


def walk(d: str):
    for base, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith((".", "__"))]
        for f in files:
            yield os.path.relpath(os.path.join(base, f), d).replace(os.sep, "/")


def ok_file(p: str, kind: str = "") -> str:
    """'' = fine, else the problem"""
    if not os.path.isfile(p):
        return "MISSING"
    if os.path.getsize(p) == 0:
        return "EMPTY"
    if kind == "json":
        try:
            with open(p, encoding="utf-8") as fh:
                json.load(fh)
        except (ValueError, OSError):
            return "BAD JSON"
    return ""


def sparse_patterns(root: str) -> list:
    """the paths of the workflow's `sparse-checkout: |` block (what the cloud run actually has); [] when there is no workflow here"""
    try:
        with open(os.path.join(root, ".github", "workflows", "cloud-monitor.yml"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    out, on = [], False
    for ln in lines:
        t = ln.strip()
        if t.startswith("sparse-checkout: |"):
            on = True
            continue
        if on:
            if t.startswith("/"):
                out.append(t)
            else:
                break
    return out


def covered(path: str, pats: list) -> bool:
    for p in pats:
        q = p.lstrip("/")
        if q.endswith("/"):
            if path.startswith(q):
                return True
        elif path == q or fnmatch.fnmatch(path, q):
            return True
    return False


def sparse_gaps(root: str) -> list:
    """files the build / the monitor read by a literal path (research/, data/, scripts/, web/, docs/) that the workflow's sparse checkout does
    NOT bring: in the cloud run they are silently absent (the code's `if os.path.exists(...)` just skips them). [(path, read by)]"""
    pats = sparse_patterns(root)
    if not pats:
        return []
    gaps, seen = [], set()
    for rel in ("tools/build_web_dashboard.py", "tools/cloud_monitor.py", "tools/bridge_sync.py"):
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            continue
        found = []
        for m in re.finditer(r'os\.path\.join\((?:ROOT|BASE|REPO), ((?:"[^"]+",?\s*)+)\)', src):
            found.append("/".join(re.findall(r'"([^"]+)"', m.group(1))))
        for m in re.finditer(r'["\']((?:research|data|scripts|web|docs)/[A-Za-z0-9_./-]+)["\']', src):
            found.append(m.group(1))
        for f in found:
            if f.split("/")[0] in ("research", "data", "scripts", "web", "docs") and re.search(r"\.[A-Za-z0-9]{1,5}$", f) and f not in seen and not covered(f, pats):
                seen.add(f)
                gaps.append((f, rel))
    return gaps


def run(site: str, src: str, root: str) -> list:
    rows = []                                              # (group, what, expected, found, state, detail)
    build_py = os.path.join(root, "tools", "build_web_dashboard.py")
    # 1. every app folder
    for app in app_list(build_py):
        sd = os.path.join(src, app)
        if not os.path.isdir(sd):
            continue                                       # not in this checkout: the build skips it too (nothing to compare)
        want = list(walk(sd))
        miss = [f for f in want if ok_file(os.path.join(site, app, f))]
        rows.append(("app", f"{app}/", len(want), len(want) - len(miss), "OK" if not miss else "MISSING", ", ".join(miss[:6]) + (f" (+{len(miss) - 6})" if len(miss) > 6 else "")))
    # 2. the top-level files
    top = [f for f in sorted(os.listdir(src)) if os.path.isfile(os.path.join(src, f)) and f.endswith((".html", ".js", ".css", ".webmanifest", ".json"))] if os.path.isdir(src) else []
    miss = [f for f in top if ok_file(os.path.join(site, f))]
    rows.append(("top", "top-level files", len(top), len(top) - len(miss), "OK" if not miss else "MISSING", ", ".join(miss[:8])))
    # 3. the must-haves
    for rel, why, kind in MUST:
        bad = ok_file(os.path.join(site, rel), kind)
        rows.append(("must", rel, 1, 0 if bad else 1, bad or "OK", why if bad else ""))
    a, b = os.path.join(site, "pc", "move_bot.ps1"), os.path.join(root, "scripts", "move_bot.ps1")
    if os.path.isfile(a) and os.path.isfile(b):
        same = open(a, "rb").read() == open(b, "rb").read()
        rows.append(("must", "pc/move_bot.ps1 = scripts/move_bot.ps1", 1, int(same), "OK" if same else "DIFFERENT", "" if same else "the site copy is not the repo's script"))
    # 4. the sources
    for rel, why in SOURCES:
        p = os.path.join(root, rel)
        good = os.path.isdir(p) and bool(os.listdir(p)) if rel.endswith("public") else os.path.isfile(p)
        rows.append(("source", rel, 1, int(good), "OK" if good else "MISSING", "" if good else why + " (is it in the workflow's sparse-checkout?)"))
    # 5. the sparse checkout: a file the code reads by name that the cloud run does not even check out
    for f, by in sparse_gaps(root):
        rows.append(("sparse", f"sparse-checkout lacks {f}", 1, 0, "GAP", f"read by {by}; add /{f} to the workflow's sparse-checkout (else it is skipped silently in the cloud)"))
    return rows


def table(rows: list) -> str:
    w = max(len(r[1]) for r in rows)
    out = [f"| {'what':<{w}} | expected | found | state | detail |", f"|{'-' * (w + 2)}|---------:|------:|-------|--------|"]
    for g, what, exp, got, st, det in rows:
        out.append(f"| {what:<{w}} | {exp:>8} | {got:>5} | {st:<7} | {det} |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default="site")
    ap.add_argument("--src", default=os.path.join(ROOT, "tools", "web_public"))
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--quiet-ok", action="store_true", help="print only the problem rows when all is well count line")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.site):
        print(f"::error title=site_selfcheck::the site folder {a.site!r} does not exist: the build produced nothing")
        return 1
    rows = run(a.site, a.src, a.root)
    bad = [r for r in rows if r[4] != "OK"]
    shown = bad if (a.quiet_ok and bad) else rows
    md = table(shown)
    print("site self-check (read-only; the publish is not touched)\n" + md)
    for g, what, exp, got, st, det in bad:
        print(f"::error title=site_selfcheck {st}::{what}: {st}{(' - ' + det) if det else ''}")
    summary = f"{len(rows) - len(bad)}/{len(rows)} checks OK" + (f", {len(bad)} PROBLEM(S): " + "; ".join(f"{r[1]} {r[4]}" for r in bad) if bad else "")
    print(summary)
    sp = os.environ.get("GITHUB_STEP_SUMMARY")
    if sp:
        try:
            with open(sp, "a", encoding="utf-8") as fh:
                fh.write(f"### Site self-check\n\n{summary}\n\n{md}\n")
        except OSError:
            pass
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
