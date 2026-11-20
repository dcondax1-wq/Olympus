"""Site sweep, no browser (night-siteqa 2026-11-20). Owner: "No mistakes" - every link and file a main page asks for exists.
For the main pages (Home / Zenith, the Gate, Doors, the ZEUS hub, Steps, Help, the hubs, every Business page, Widget + Glance, Kalshi,
Trading, the Board) and every app the Doors page shows (olympus/doors.js DOORS ids, not ARCHIVE; their index.html):
  a. every href / src in the HTML (links, scripts, styles, icons, the manifest; the ?v= tag and #part dropped) is a file in tools/web_public
     (a folder = its index.html). The Gate's data-to links are from the site root (GATE_BASE). Allowed: the live data files the publisher
     writes (not kept in git; the same list as tests/test_olympus_shell) and the build's icons/ (copied from web/icons/, which must hold it)
  b. olympus/doors.js: every door shortcut href, every door home, ALL and PAGE point at a file (archived apps included: they still open)
  c. every doors.js id (DOORS ids, ARCHIVE) is an app of olympus/apps-list.js whose folder has its index.html
  d. hub/help.json: every in-site link of the Help answers exists
    python -X utf8 -m tests.test_site_sweep          (about 1 s)
"""
from __future__ import annotations

import glob
import html.parser
import json
import os
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
ICONS = os.path.join(ROOT, "web", "icons")
RES: list = []
# written by the publisher / the PC at build time, not in git (tests/test_olympus_shell LIVE + the per-app private copies)
LIVE = re.compile(r"^(home\.json|data\.json|kalshi\.json|money/|me/me\.json|alerts\.json|writeups/|status_feed\.json|live\.json|chart\.png|recaps/"
                  r"|kalshicity/(forward|scan)\.json|kalshi/kit\.json|hub/learned\.json|business/business\.json|business/lab_pc\.json|agency/my_leads\.json)")
SKIP = ("#", "http:", "https:", "mailto:", "tel:", "sms:", "data:", "javascript:", "blob:", "about:", "//", "shortcuts:", "scriptable:")
MAIN = ["index.html", "gate/index.html", "hub/doors.html", "hub/zeus.html", "hub/steps.html", "hub/help.html", "hub/index.html",
        "widget/index.html", "widget/glance.html", "kalshi/index.html", "trading/index.html", "board/index.html"]


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"))


class Refs(html.parser.HTMLParser):
    """(attr value, from the site root?) of every href / src on a tag (inline script and style bodies are not read)"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs: list = []
        self.base = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "base" and a.get("href"):
            self.base = a["href"]
        for k in ("href", "src"):
            v = a.get(k)
            if v:
                self.refs.append((v.strip(), "data-to" in a))

    handle_startendtag = handle_starttag


def target(page_rel: str, ref: str, from_root: bool = False, base: str | None = None):
    """the file a link on page_rel points at (None = not a site file to check)"""
    if not ref or ref.startswith(SKIP) or any(t in ref for t in ("${", "{{", "' +", "'+", "\" +")):
        return None
    path = unquote(urlsplit(ref).path)
    if not path:
        return None
    if path.startswith("/"):
        rel = path.lstrip("/")
    else:
        d = "" if from_root else os.path.dirname(page_rel)
        if base and not from_root:
            d = os.path.normpath(os.path.join(d, base)) if not base.startswith("/") else base.lstrip("/")
        rel = os.path.normpath(os.path.join(d, path)).replace(os.sep, "/")
    if rel.startswith(".."):
        return ("outside", rel)
    return rel


def exists(rel: str) -> bool:
    p = os.path.join(WEB, rel)
    if os.path.isdir(p):
        return os.path.isfile(os.path.join(p, "index.html"))
    if os.path.isfile(p):
        return True
    if LIVE.match(rel):
        return True
    if rel.startswith("icons/"):                      # the build copies web/icons/<name> next to the site root's index.html
        return os.path.isfile(os.path.join(ICONS, rel[len("icons/"):]))
    return False


def page_refs(page_rel: str):
    with open(os.path.join(WEB, page_rel), encoding="utf-8") as f:
        p = Refs()
        p.feed(f.read())
    return [(ref, target(page_rel, ref, root, p.base)) for ref, root in p.refs]


def doors():
    with open(os.path.join(WEB, "olympus", "doors.js"), encoding="utf-8") as f:
        js = f.read()
    hrefs = re.findall(r"\bhref:\s*'([^']+)'", js) + re.findall(r"\bhome:\s*'([^']+)'", js) + re.findall(r"\b(?:ALL|PAGE):\s*'([^']+)'", js)
    ids = []
    for block in re.findall(r"\bids:\s*\[([^\]]*)\]", js):
        ids += re.findall(r"'([a-z0-9_]+)'", block)
    arc = re.findall(r"'([a-z0-9_]+)'", re.search(r"var ARCHIVE = \[([^\]]*)\]", js).group(1))
    return js, hrefs, ids, arc


def app_paths():
    with open(os.path.join(WEB, "olympus", "apps-list.js"), encoding="utf-8") as f:
        js = f.read()
    return {m.group(1): m.group(2) for m in re.finditer(r'"id": "([a-z0-9_]+)"[^}]*?"path": "([^"]*)"', js)}


def main() -> int:
    _, hrefs, ids, arc = doors()
    paths = app_paths()
    shown = [i for i in ids if i not in arc]
    pages = list(MAIN) + sorted(os.path.relpath(p, WEB).replace(os.sep, "/") for p in glob.glob(os.path.join(WEB, "business", "*.html")))
    for i in shown:
        p = paths.get(i)
        if p and p.endswith("/") and os.path.isfile(os.path.join(WEB, p, "index.html")) and p + "index.html" not in pages:
            pages.append(p + "index.html")

    # a. every href / src of the main pages and the shown apps
    n, bad = 0, []
    for pg in pages:
        if not os.path.isfile(os.path.join(WEB, pg)):
            bad.append((pg, "(the page itself is missing)"))
            continue
        for ref, rel in page_refs(pg):
            if rel is None:
                continue
            n += 1
            if isinstance(rel, tuple) or not exists(rel):
                bad.append((pg, ref))
    check(f"a. {len(pages)} main pages + shown apps: every href / src ({n} links, ?v= tags included) points at a file that exists", not bad and n > 300, bad[:12])

    # b. doors.js links (from the site root)
    miss = [h for h in hrefs if not exists(target("x.html", h))]
    check(f"b. olympus/doors.js: all {len(hrefs)} door shortcuts, door homes, ALL and PAGE open a file that exists", not miss and len(hrefs) >= 25, miss)

    # c. every id in a door (archived included) is an app with its page
    nopage = [i for i in ids + arc if i not in paths or (paths[i] and not exists(paths[i]))]
    check(f"c. doors.js: all {len(set(ids))} app ids ({len(arc)} archived) are apps of apps-list.js with a page", not nopage and set(arc) <= set(ids), nopage)

    # d. the Help answers' in-site links
    with open(os.path.join(WEB, "hub", "help.json"), encoding="utf-8") as f:
        hj = f.read()
    links = sorted(set(re.findall(r'"(?:href|link|url|to|go)"\s*:\s*"([^"]*)"', hj)))
    gone = [h for h in links if target("hub/help.json", h) and not exists(target("hub/help.json", h))]
    check(f"d. hub/help.json: every in-site link of the answers ({len(links)}) exists", not gone and links, gone)

    ok = sum(RES)
    print(f"\nsite sweep: {ok}/{len(RES)} " + ("ALL PASS" if ok == len(RES) else "FAILED"))
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
