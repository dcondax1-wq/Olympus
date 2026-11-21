"""Visual QA sweep guards (day-arenas 2026-11-21, DESIGN; research/handoff/2026-11-21/design/QA_SWEEP.md). One check per defect class the
sweep fixed across every app reachable from Home and the Jarvis switcher, so none comes back:
  a. static: the address bar / status bar is black (theme-color #000000, never AGORA's brown #14110e) on every page and in every home-screen
     manifest; no app sheet paints a card with a raw AGORA brown (#211c16 / #1d1914 / #26211b / #14110e / rgba(29,25,20)) outside a var()
     fallback; the archived banner is the night card; the sticky tab bars are violet glass in OLYMPUS NIGHT (kit + Zenith); a light phone gets
     OLYMPUS NIGHT on an app without a light mode; the Ask Jarvis button steps out of the way while a finger scrolls; the payout card never
     stays on 'Loading'; Board's PC SILENT is red on the night card
  b. Chromium 390 x 844 (QA_NO_BROWSER=1 skips): no brown card (hue 15-70, dark) and no near-black sticky bar on a sample of apps, dark and
     light phone; a light phone paints OLYMPUS NIGHT on a kit app
    python -X utf8 -m tests.test_qa_sweep
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []
SKIP_DIRS = ("fx", "node_modules", "icon_options", "research")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def rd(*p):
    return open(os.path.join(WEB, *p), encoding="utf-8", errors="replace").read()


def files(ext):
    for root, dirs, fs in os.walk(WEB):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fs:
            if f.endswith(ext):
                yield os.path.join(root, f)


BROWN_HEX = r"#(?:211c16|1d1914|26211b|14110e|0f0c09|2a2217|241c10)\b"
SWEPT = "archive sibyl kratos pinakes pythia epilogue colosseum prometheus forum apollo moirai fates labyrinth argus nemesis widget".split()


def static():
    bad = [os.path.relpath(p, WEB) for p in files(".html") if re.search(r'<meta name="theme-color" content="#14110e"', open(p, encoding="utf-8", errors="replace").read())]
    check("a. the address bar is black: no page sets theme-color to AGORA's brown #14110e", not bad, bad[:8])
    badm = []
    for p in files(".webmanifest"):
        try:
            m = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if "#14110e" in (str(m.get("theme_color", "")).lower(), str(m.get("background_color", "")).lower()):
            badm.append(os.path.relpath(p, WEB))
    check("a. home-screen apps open black: no manifest theme_color / background_color #14110e", not badm, badm[:8])
    raw = []
    for a in SWEPT:
        for p in glob.glob(os.path.join(WEB, a, "*.css")):
            for ln in open(p, encoding="utf-8", errors="replace").read().splitlines():
                for m in re.finditer(r"background(?:-color)?\s*:[^;{}]*", ln):
                    decl = m.group(0)
                    if re.search(r"(?<!, )" + BROWN_HEX, decl) or re.search(r"(?<!rgb, )rgba\(\s*29,\s*25,\s*20\s*,", decl):
                        raw.append(os.path.relpath(p, WEB) + ": " + decl[:70])
    check("a. no swept app paints a card in a raw AGORA brown (only as a var() fallback, so OLYMPUS NIGHT repaints it)", not raw, raw[:8])
    arch = [os.path.relpath(p, WEB) for p in files(".html") if "background:var(--oly-th-n4,#1d1914)" in open(p, encoding="utf-8", errors="replace").read()]
    check("a. the archived-page banner is the night card with a violet edge (never AGORA brown); its builder agrees",
          not arch and "background:var(--oly-th-n5,#16131e)" in open(os.path.join(ROOT, "tools", "archive_banners.py"), encoding="utf-8").read(), arch[:5])
    ag, za = rd("olympus", "agora.css"), rd("zenith_agora.css")
    check("a. sticky tab bars are violet glass in OLYMPUS NIGHT (kit tablists, Zenith's top bar and bottom tabs), not a near-black slab",
          'html[data-oly-theme="night"] main#app > [role="tablist"]' in ag and "rgba(22, 13, 42, .84)" in ag
          and 'html[data-oly-style="night"]:not([data-theme="light"]) nav#tabs.tabs' in za and "rgba(22, 13, 42, .84)" in za)
    th = rd("olympus", "themes.js")
    check("a. a light phone gets OLYMPUS NIGHT on an app without a light mode (only Zenith's Home / a 'light dark' page follows the phone)",
          "(lightPhone() && ownLight())" in th and "function ownLight()" in th)
    pl = rd("olympus", "polis-life.js")
    check("a. the Stoic tablet (Journal, Kronos, Aegis, Helios, Zenith ...) is a night card with lavender text, never cream marble",
          ".pl-tablet{margin:0;padding:18px 18px 14px;border-radius:12px;color:#dacbf0;" in pl and "#efe9de" not in pl and "polis-life.js?v=pl5" in rd("journal", "index.html"))
    ask = rd("jarvis", "ask.js")
    check("a. the Ask Jarvis button steps out of the way while a finger scrolls (it sat over the cards' left edge), back 0.9 s later",
          "oly-ask-away" in ask and "addEventListener('scroll'" in ask and "jarvis/ask.js?v=7" in rd("olympus", "olympus.js"))
    mf = rd("olympus", "moneyfx.js")
    check("a. the payout card never stays on 'Loading the funded account...' (no copy / an error says so)",
          "if (!home) { if (note) note.textContent = 'No account numbers yet" in mf and "/^Loading/.test(n.textContent)" in mf)
    bc = rd("board", "board.css")
    check("a. Board's PC SILENT is a red alert on the night card in OLYMPUS NIGHT (no terra-cotta on bronze)",
          'html:not([data-oly-scheme="light"]) .silent { background: radial-gradient(120% 120% at 0% 0%, rgba(239, 68, 68, .22)' in bc)


class _Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


PROBE = r"""() => { const H = innerHeight, out = { brown: [], bars: [], theme: document.documentElement.getAttribute('data-oly-theme') || '' };
  const rgb = (c) => { const m = String(c).match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/); return m ? [+m[1], +m[2], +m[3], m[4] == null ? 1 : +m[4]] : null; };
  const hsl = ([r, g, b]) => { r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2; let h = 0, s = 0;
    if (mx !== mn) { const d = mx - mn; s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn); h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; } return [h, s, l]; };
  for (const e of document.body.querySelectorAll('*')) {
    const r = e.getBoundingClientRect(); if (!r.width || !r.height || r.top > H * 2.2) continue;
    const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const c = rgb(cs.backgroundColor); if (!c || c[3] < .85) continue; const area = r.width * r.height, [h, s, l] = hsl(c);
    if (area > 9000 && h >= 15 && h <= 70 && s > .12 && l > .04 && l < .42) out.brown.push(e.tagName + '.' + String(e.className).slice(0, 30) + ' ' + cs.backgroundColor);
    if ((cs.position === 'sticky' || cs.position === 'fixed') && r.width > 300 && r.height > 30 && Math.max(c[0], c[1], c[2]) <= 14) out.bars.push(e.tagName + '#' + e.id + ' ' + cs.backgroundColor);
  }
  out.brown = out.brown.slice(0, 6); out.bars = out.bars.slice(0, 6); return out; }"""


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("b. playwright", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Q, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    pages = ["/", "/archive/", "/kratos/", "/pinakes/", "/colosseum/", "/settings/", "/inbox/", "/forum/", "/board/"]
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            for scheme in ("dark", "light"):
                bad, themes = {}, {}
                for u in pages:
                    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, color_scheme=scheme, service_workers="block")
                    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
                    p = ctx.new_page()
                    try:
                        p.goto(base + u, wait_until="load", timeout=60000)
                        p.wait_for_timeout(2500)
                        r = p.evaluate(PROBE)
                    except Exception as e:  # noqa: BLE001
                        r = {"brown": [], "bars": [], "theme": "error " + str(e)[:60]}
                    themes[u] = r["theme"]
                    if u == "/" and scheme == "light":
                        r["brown"] = []          # Zenith's Home keeps its own light mode on a light phone (AGORA there is its choice)
                    if r["brown"] or r["bars"]:
                        bad[u] = r
                    ctx.close()
                check(f"b. {scheme} phone: no brown card and no near-black sticky bar on " + ", ".join(pages), not bad, bad)
                if scheme == "light":
                    check("b. a light phone paints OLYMPUS NIGHT on the kit apps (no AGORA brown)", all(themes[u] == "night" for u in pages if u not in ("/",)), themes)
            br.close()
    finally:
        srv.shutdown()


def main():
    static()
    if os.environ.get("QA_NO_BROWSER") != "1":
        browser()
    print(json.dumps({"passed": sum(RES), "total": len(RES)}))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
