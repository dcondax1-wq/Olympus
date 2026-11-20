"""The 'Archived' strip on every archived app (day-archive 2026-11-20, tools/archive_banners.py). No browser, under a second.
    python -m tests.test_archive_banners
Checks: every app in olympus/doors.js ARCHIVE that the archive team owns carries the strip (and nothing else in MAP is un-archived but
atlascity); every strip links to a real live app folder; every data-src it reads for the age is a file the repo or the site has; the
generator is idempotent; the strip text never shows a number typed in by hand (the age is read from the page's own file)."""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import archive_banners as A  # noqa: E402

WEB = A.ROOT
SITE_FEEDS = {"home.json", "money/index.json"}      # published by the site build (tools/pc_publish.py), not in the repo
OTHER_TEAMS = {"datacity", "sibyl", "kalshicity"}   # archived, but owned by the Cities / Kalshi teams
ok = bad = 0


def check(name, cond, info=""):
    global ok, bad
    if cond:
        ok += 1; print(f"[PASS] {name}")
    else:
        bad += 1; print(f"[FAIL] {name}  -> {info}")


def main():
    doors = open(os.path.join(WEB, "olympus", "doors.js"), encoding="utf-8").read()
    arc = set(re.findall(r"'([a-z]+)'", doors[doors.index("var ARCHIVE"):doors.index("var WORDS")]))
    mine = arc - OTHER_TEAMS
    check("every archived app (archive team) is in MAP", mine <= set(A.MAP), sorted(mine - set(A.MAP)))
    check("MAP holds only archived apps (+ atlascity, which no door lists)", set(A.MAP) - arc <= {"atlascity"}, sorted(set(A.MAP) - arc - {"atlascity"}))
    miss, links, srcs, dup = [], [], [], []
    for app, (target, name, src) in A.MAP.items():
        html = open(os.path.join(WEB, app, "index.html"), encoding="utf-8").read()
        if html.count(A.START) != 1 or html.count(A.END) != 1 or A.banner(app) not in html:
            miss.append(app)
        if not os.path.isfile(os.path.join(WEB, target, "index.html")) or target in arc:
            links.append(f"{app}->{target}")
        if src:
            rel = os.path.normpath(os.path.join(app, src)).replace(os.sep, "/")
            if rel not in SITE_FEEDS and not os.path.isfile(os.path.join(WEB, rel)):
                srcs.append(f"{app}:{rel}")
        if A.apply(A.apply(html, app), app) != A.apply(html, app):
            dup.append(app)
    check(f"all {len(A.MAP)} pages carry exactly one current strip right after <body>", not miss, miss)
    check("every strip links to a live (not archived) app that exists", not links, links)
    check("every age source is a repo file or a site feed", not srcs, srcs)
    check("the generator is idempotent", not dup, dup)
    b = A.banner("apollo")
    check("the strip has no hand-typed number or $: only 'Archived', the link, and an age the script fills",
          not re.search(r"\$\d|\b\d{1,3}(,\d{3})+\b|days old", re.sub(r'<script>.*?</script>|style="[^"]*"', "", b)), b[:200])
    check("the strip is a labelled note with a real link (a11y), and full-screen pages are pushed down, not covered",
          'role="note"' in b and 'aria-label="Archived page"' in b and 'href="../journal/"' in b and "insertBefore(b,d)" in b and "paddingTop" in b)
    check("--check passes", A.main(["--check"]) == 0)
    print(f"{ok}/{ok + bad} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
