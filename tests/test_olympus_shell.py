"""THE MAIN PAGES' SHELL (night-revamp-main, 2026-11-20). Owner: "The bottom of my screen is still a little funky ... lag, glitches."
The Gate, Zenith, Jarvis, the Doors page, a hub and Settings, in Chromium at 390 x 844 and 430 x 932 with the iPhone's home bar emulated
(34 px, tools/olympus_shell_audit.py). Fails when:
  a. static: olympus/shell.css is missing, or a main page does not load it (last; Zenith inline; Jarvis keeps its own sheets: its offline copy
     (jarvis/sw.js, lead-only) has no shell.css, so a link would hold its first frame on a slow site), or it loses its tokens / glued bars / reduced-motion rule
  b. a page scrolls sideways
  c. a fixed bottom bar's keys reach into the home bar, or page text hides under a bottom bar at the end of the page
  d. a page error (an uncaught exception), or a 404 on a file that is in the repo's site (the live data files home.json, data.json,
     kalshi.json, money/*, me/me.json and the build's icons/ are written by the publisher, not kept in git: they are allowed)
    python -X utf8 -m tests.test_olympus_shell            (--static: part a only)
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
WEB = AK.WEB
LIVE = re.compile(r"^(home\.json|data\.json|kalshi\.json|money/|me/me\.json|icons/|alerts\.json|writeups/|status_feed\.json|live\.json|kalshicity/(forward|scan)\.json|kalshi/kit\.json)")
MAIN = {"hub/doors.html": "../olympus/shell.css",
        "hub/index.html": "../olympus/shell.css", "settings/index.html": "../olympus/shell.css"}


def test_static():
    css = AK.read(os.path.join(WEB, "olympus", "shell.css"))
    check("a. olympus/shell.css: the tokens (colour, type, spacing, radius, motion, safe area), a light set, the glued bars, reduced motion",
          all(t in css for t in ("--o-bg:", "--o-font:", "--o-4:", "--o-r-md:", "--o-ease:", "--o-sab: var(--jz-sa-bottom, env(safe-area-inset-bottom", "--o-bar-total:",
                                 'html[data-oly-scheme="light"]', "nav#tabs.tabs", "prefers-reduced-motion: reduce")))
    for page, href in MAIN.items():
        html = AK.read(os.path.join(WEB, page))
        i = html.find(href + "?v=")
        after = [ln for ln in html[i:html.find("</head>")].split("\n")[1:] if "home-fx.css" not in ln]   # night-effects: only the home's effects layer may sit on top
        check(f"a. {page} loads the shell layer after its own sheets (last stylesheet in <head>, the home-fx effects layer aside)",
              i > 0 and '<link rel="stylesheet"' not in "\n".join(after), href)
    z, css2 = AK.read(os.path.join(WEB, "index.html")), re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    zi = z[z.find('<style id="oly-shell">'):z.find("</style>", z.find('<style id="oly-shell">'))]
    rules = [r.strip() for r in re.findall(r"[^{}]+\{[^{}]*\}", re.sub(r"@media[^{]+\{", "", css2)) if "nav#tabs" in r or "--o-bar-total:" in r]
    check("a. Zenith carries the shell layer inline (a slow site never holds its first frame), in step with olympus/shell.css",
          zi and all(" ".join(r.split()) in " ".join(zi.split()) for r in rules) and z.find('<style id="oly-shell">') > z.find("zenith_agora.css"), len(rules))
    gate = AK.read(os.path.join(WEB, "gate", "index.html"))
    check("a. the Gate loads the shell layer right after gate.css (from GATE_BASE)", gate.find("'olympus/shell.css?v=") > gate.find("'gate/gate.css?v="))


def test_browser():
    sys.path.insert(0, os.path.join(AK.ROOT, "tools"))
    import olympus_shell_audit as AU
    srv, origin = AK.serve()
    try:
        res = AU.run(origin + "/", shots=None, throttle=1)
    finally:
        srv.shutdown()
    for r in res:
        tag = f"{r['page']} {r['w']}x{r['h']}"
        check(f"b. {tag}: no sideways scroll", r["sideways"] <= 0, r["sideways"])
        check(f"c. {tag}: bottom bars keep their keys above the home bar; nothing hides under them at the end of the page",
              all(b["clears"] for b in r["bars"]) and not r["hidden"], (r["bars"], r["hidden"]))
        pe = [e for e in r["errors"] if e.startswith("pageerror")]
        bad = [b for b in r["bad"] if not LIVE.match(b.split(" ", 1)[1])]
        check(f"d. {tag}: no page error, no missing site file", not pe and not bad, (pe, bad))


if __name__ == "__main__":
    test_static()
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
