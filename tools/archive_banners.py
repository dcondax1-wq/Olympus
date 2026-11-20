"""Archived-page banner (day-archive 2026-11-20, owner: "a lot of those arenas are shit. We need the main stuff.").

Every app in olympus/doors.js ARCHIVE (plus atlascity) gets the same small strip at the top of its page:
    Archived · data Oct 28, 23 days old                          Journal ->
(the date is read live from the file the page itself uses, never typed in; amber when older than 2 days)
so an old page can never pass for the live one. The strip is plain HTML + one tiny inline script (no extra file, works offline),
between the markers  <!-- archived:start -->  and  <!-- archived:end -->  right after <body>. Re-running replaces it (idempotent).

    python tools/archive_banners.py            write / refresh every banner
    python tools/archive_banners.py --check    exit 1 if a banner is missing or differs (tests.test_archive_banners)
    python tools/archive_banners.py --remove   take them all out again

To bring an app back to the main list: take it out of ARCHIVE in doors.js (lead) and out of MAP below, then run --remove for it by
deleting its entry and re-running (a page that is not in MAP loses its banner).
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_public")
START, END = "<!-- archived:start -->", "<!-- archived:end -->"

# app id -> (live app folder, its name in plain words, the data file the page reads for its numbers or None)
MAP = {
    "apollo": ("journal", "Journal", "../odeon/trades.json"),
    "epilogue": ("journal", "Journal", "../home.json"),
    "kratos": ("journal", "Journal", "../odeon/trades.json"),
    "nemesis": ("journal", "Journal", "../odeon/trades.json"),
    "nike": ("journal", "Journal", "../odeon/trades.json"),
    "ares": ("nq", "NQ bots", "../home.json"),
    "kairos": ("nq", "NQ bots", "../odeon/trades.json"),
    "chronos": ("nq", "NQ bots", "../odeon/trades.json"),
    "oracle": ("nq", "NQ bots", None),
    "odeon": ("trading", "Trading", "trades.json"),
    "why": ("trading", "Trading", "why.json"),
    "delphi": ("helios", "Morning brief", "../home.json"),
    "forum": ("helios", "Morning brief", "../pantheon/pantheon.json"),
    "pythia": ("helios", "Morning brief", "events.json"),
    "pantheon": ("helios", "Morning brief", "pantheon.json"),
    "pheme": ("helios", "Morning brief", "stats.json"),
    "labyrinth": ("pnyx", "Pnyx", "../odeon/trades.json"),
    "moirai": ("fates", "Fates", None),
    "plutus": ("hera", "Hera", "roadmap.json"),
    "argo": ("hera", "Hera", "../home.json"),
    "mint": ("business", "Business", "../money/index.json"),
    "mintcity": ("business", "Business", "../money/index.json"),
    "harmonia": ("business", "Business", "../money/index.json"),
    "arbiter": ("business", "Business", None),
    "hermes": ("ledger", "Ledger", None),
    "stoa": ("compass", "Compass", "../home.json"),
    "hestia": ("compass", "Compass", "../home.json"),
    "argus": ("board", "Board", "../home.json"),
    "herald": ("board", "Board", "edition.json"),
    "symposium": ("board", "Board", None),
    "ergasterion": ("board", "Board", None),
    "mind": ("jarvis", "Jarvis", None),
    "bridge": ("jarvis", "Jarvis", None),
    "athena": ("clio", "Clio", None),
    "lyceum": ("clio", "Clio", None),
    "archive": ("clio", "Clio", "index.json"),
    "observatory": ("clio", "Clio", None),
    "tree": ("clio", "Clio", None),
    "prometheus": ("clio", "Clio", "forge.json"),
    "hephaestus": ("clio", "Clio", "data.json"),
    "pinakes": ("clio", "Clio", "catalog.json"),
    "colosseum": ("clio", "Clio", "extra.json"),
    "arena": ("atlas", "Atlas", None),
    "gallery": ("atlas", "Atlas", None),
    "polis": ("atlas", "Atlas", None),
    "atlascity": ("atlas", "Atlas", None),
}

CSS = ("position:sticky;top:0;z-index:2147483000;display:flex;align-items:center;gap:8px;margin:0;"
       "padding:calc(4px + env(safe-area-inset-top,0px)) 12px 4px;box-sizing:border-box;width:100%;min-height:34px;"
       "background:var(--oly-th-n4,#1d1914);color:var(--oly-th-n30,#cfc4b2);border-bottom:1px solid rgba(243,236,224,.16);"
       "font:500 12.5px/1.25 -apple-system,system-ui,'Helvetica Neue',Arial,sans-serif;letter-spacing:0;text-align:left")
LINK = ("margin-left:auto;flex:none;color:var(--oly-th-a11,#dac08b);font-weight:600;text-decoration:none;padding:6px 0;"
        "white-space:nowrap")
# 1) a full-screen page (html/body overflow hidden, its own HUD pinned at top 0): the strip moves out of <body> and the page is
#    pushed down under it (body becomes the box its fixed parts sit in), so nothing of the page is covered;
# 2) reads the first date-ish field of the page's own data file -> "Archived · its data: Oct 28, 23 days old" (amber when > 2 days).
JS = ("(function(){var b=document.currentScript.parentNode,h=document.documentElement,d=document.body;try{"
      "var y=function(e){return getComputedStyle(e).overflowY};if(d&&(y(h)==='hidden'||y(d)==='hidden')){h.insertBefore(b,d);"
      "b.style.position='fixed';b.style.left='0';b.style.right='0';var fit=function(){var H=b.offsetHeight;h.style.paddingTop=H+'px';"
      "h.style.boxSizing='border-box';d.style.transform='translateZ(0)';d.style.height=d.style.minHeight=d.style.maxHeight=(innerHeight-H)+'px';};"
      "fit();addEventListener('resize',fit);}}catch(e){}"
      "var s=b.getAttribute('data-src'),o=b.querySelector('[data-age]');if(!s||!o||!window.fetch)return;"
      "fetch(s,{cache:'no-cache'}).then(function(r){return r.ok?r.json():null}).then(function(j){if(!j||typeof j!=='object')return;"
      "var v=j.upto||j.asof||j.as_of||j.built||j.updated||j.date||j.generated_at||j.t,ms=null;"
      "if(typeof v==='number')ms=v<1e12?v*1000:v;else if(typeof v==='string'){var m=v.match(/^(\\d{4})-(\\d\\d)-(\\d\\d)(?:[ T](\\d\\d):(\\d\\d))?/);"
      "if(m)ms=new Date(+m[1],m[2]-1,+m[3],+(m[4]||12),+(m[5]||0)).getTime();}if(!ms||!isFinite(ms))return;"
      "var n=Math.floor((Date.now()-ms)/864e5),w=new Date(ms).toLocaleDateString('en-US',{month:'short',day:'numeric'});"
      "o.textContent=' · data '+w+(n<1?', today':n===1?', 1 day old':', '+n+' days old');"
      "if(n>2)o.style.color='var(--oly-th-warn,#e0b060)';}).catch(function(){});})();")


def banner(app: str) -> str:
    target, name, src = MAP[app]
    src_attr = f' data-src="{src}"' if src else ""
    return (f'{START}<aside data-archived="{target}"{src_attr} role="note" aria-label="Archived page" style="{CSS}">'
            f'<span style="min-width:0">Archived<span data-age></span></span>'
            f'<a href="../{target}/" style="{LINK}">{name} &rarr;</a><script>{JS}</script></aside>{END}')


def apply(html: str, app: str | None) -> str:
    html = re.sub(r"\n?" + re.escape(START) + r".*?" + re.escape(END), "", html, flags=re.S)
    if app is None:
        return html
    m = re.search(r"<body\b[^>]*>", html, flags=re.I)
    if not m:
        raise ValueError("no <body>")
    return html[:m.end()] + "\n" + banner(app) + html[m.end():]


def main(argv: list[str]) -> int:
    check, remove = "--check" in argv, "--remove" in argv
    bad = 0
    for app in sorted(MAP):
        path = os.path.join(ROOT, app, "index.html")
        if not os.path.isfile(path):
            print(f"[FIX] {app}: no index.html"); bad += 1; continue
        old = open(path, encoding="utf-8").read()
        new = apply(old, None if remove else app)
        if check:
            if old != new:
                print(f"[FIX] {app}: banner missing or stale (python tools/archive_banners.py)"); bad += 1
        elif old != new:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            print(f"[OK] {app}")
    if check and not bad:
        print(f"[OK] {len(MAP)} archived pages carry the banner")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
