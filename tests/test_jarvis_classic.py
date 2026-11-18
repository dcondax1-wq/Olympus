"""Classic Jarvis (night A 2026-11-16, owner: "bring back our Jarvis we had"): the old violet HUD as an opt-in Jarvis look; AGORA stays the default.

  a. static: classic.css is its own sheet, every rule under html:root[data-jlook="classic"] (the AGORA default never reads it), the old
     palette (#a855f7 / #7c3aed / #c084fc on black), Orbitron + Rajdhani from the files in jarvis/; jarvis.css keeps no violet / techno font
  b. static: the first paint adds data-jlook + the sheet only for 'jarvis.look' = 'classic' under the default OLYMPUS theme; the Look sheet's
     Jarvis look switch (AGORA / Classic Jarvis), the palette entries and the voice phrases; the 3D core gets the violet of classic.css
  c. Chromium (phone size): Classic (the default since 2026-11-18) -> violet from the first paint; AGORA -> gold again and saved;
     Classic again from the Look sheet; "classic Jarvis" typed in the command bar switches it; picking another OLYMPUS theme turns Classic off;
     no page error

    python -X utf8 -m tests.test_jarvis_classic          (browser part under: flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
WP = os.path.join(ROOT, "tools", "web_public")
JV = os.path.join(WP, "jarvis")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"   -> {str(info)[:300]}"))


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def part_static():
    css, main, page = read(JV, "classic.css"), read(JV, "jarvis.css"), read(JV, "index.html")
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    sels = [s.strip() for s in re.findall(r"(?:^|\})\s*([^{}@]+)\{", body) if s.strip()]
    check("a. every classic.css rule is scoped to html:root[data-jlook=\"classic\"] (fonts aside)", sels and all(s.startswith('html:root[data-jlook="classic"]') for s in sels), sels[:5])
    check("a. the old palette and fonts", all(x in css for x in ("#a855f7", "#7c3aed", "#c084fc", "--bg: #000", "orbitron.woff2", "rajdhani-500.woff2", "Orbitron", "Rajdhani"))
          and all(os.path.isfile(os.path.join(JV, f)) for f in ("orbitron.woff2", "rajdhani-400.woff2", "rajdhani-500.woff2", "rajdhani-600.woff2", "rajdhani-700.woff2")))
    check("a. jarvis.css (the AGORA default) stays free of the violet and the techno fonts", "#a855f7" not in main and "@font-face" not in main and "data-jlook" not in main)
    head = page[:page.index("</head>")]
    check("b. the first paint: Classic by default (2026-11-18, owner: 'back to how it was'), AGORA only for 'jarvis.look' = 'agora'; under the default OLYMPUS theme; its own sheet, added then",
          "g('jarvis.look') !== 'agora' && (g('olympus.theme') || 'agora') === 'agora'" in head and "d.setAttribute('data-jlook', 'classic')" in head
          and "cl.href = 'classic.css?v=c2'" in head and "d.setAttribute('data-theme', 'agora')" in head)
    check("b. the Look sheet: Jarvis look AGORA / Classic Jarvis; palette entries; the voice phrases; the core key",
          'id="jlookSeg"' in page and 'data-jlook-k="classic"' in page and 'data-jlook-k="agora"' in page and "function setJLook(k)" in page
          and "Look: Classic Jarvis" in page and "bring back (the )?old (jarvis|look)" in page and "if (root.dataset.jlook === 'classic' && !olyOn()) return themeColors();" in page)
    check("b. any OLYMPUS theme replaces Classic; back on the default theme Classic returns (unless AGORA was picked)",
          "if (olyOn() && root.dataset.jlook) delete root.dataset.jlook;" in page and "else if (!olyOn() && !root.dataset.jlook && raw('jarvis.look') !== 'agora') { classicSheet(); root.dataset.jlook = 'classic'; }" in page)


def part_browser():
    import browser_kit as BK
    from playwright.sync_api import sync_playwright

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=WP))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/jarvis/?demo=1"
    st = """() => { const r = document.documentElement, cs = getComputedStyle(r); return { jlook: r.dataset.jlook || '', c: cs.getPropertyValue('--c').trim(),
      bg: getComputedStyle(document.body).backgroundColor, fh: cs.getPropertyValue('--fh').trim(), saved: localStorage.getItem('jarvis.look'), sheet: !!document.getElementById('jclassic') }; }"""
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, service_workers="block", is_mobile=True, has_touch=True)
            ctx.add_init_script("try{ if (!sessionStorage.getItem('t.once')) { sessionStorage.setItem('t.once','1'); localStorage.setItem('jarvis.look','classic'); }"
                                " localStorage.setItem('jarvis.intro','off'); sessionStorage.setItem('jarvis.booted','1'); }catch(e){}")
            ctx.route("**/*", lambda r: r.abort() if not r.request.url.startswith("http://127.0.0.1") else r.continue_())
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)[:200]))
            p.goto(url, wait_until="load")
            p.wait_for_function("document.documentElement.dataset.brain === 'module'", timeout=BK.limit_ms(30000))
            a = p.evaluate(st)
            check("c. saved Classic: violet + black + Orbitron from the first paint, its sheet loaded", a["jlook"] == "classic" and a["c"] == "#a855f7" and a["bg"] == "rgb(0, 0, 0)"
                  and "Orbitron" in a["fh"] and a["sheet"], a)
            p.evaluate("() => { document.querySelector('#look').hidden = false; document.querySelector('[data-jlook-k=agora]').click(); }")
            b = p.evaluate(st)
            check("c. AGORA: gold again, the choice saved ('agora': Classic is the default)", b["jlook"] == "" and b["c"] == "#c8a24a" and b["saved"] == "agora", b)
            p.evaluate("() => document.querySelector('[data-jlook-k=classic]').click()")
            p.wait_for_timeout(300)
            c = p.evaluate(st)
            pressed = p.evaluate("() => document.querySelector('[data-jlook-k=classic]').getAttribute('aria-pressed')")
            check("c. Classic from the Look sheet: violet, saved, its button pressed", c["jlook"] == "classic" and c["c"] == "#a855f7" and c["saved"] is None and pressed == "true", (c, pressed))
            p.evaluate("() => { document.querySelector('[data-jlook-k=agora]').click(); document.querySelector('#look').hidden = true; }")
            p.fill("#q", "classic Jarvis")
            p.press("#q", "Enter")
            p.wait_for_timeout(500)
            d = p.evaluate(st)
            check("c. 'classic Jarvis' typed in the command bar switches it (back to the default: nothing saved)", d["jlook"] == "classic" and d["saved"] is None, d)
            p.evaluate("() => window.OLYMPUS_THEMES && window.OLYMPUS_THEMES.set('nord')")
            p.wait_for_timeout(600)
            e = p.evaluate(st)
            check("c. another OLYMPUS theme turns Classic off", e["jlook"] == "" and e["saved"] is None, e)
            p.evaluate("() => window.OLYMPUS_THEMES && window.OLYMPUS_THEMES.set('agora')")
            check("c. no page error", not errs, errs[:3])
            ctx.close()
    finally:
        srv.shutdown()


def main() -> int:
    part_static()
    if "--static" not in sys.argv:
        part_browser()
    n, ok = len(RES), sum(RES)
    print(f"jarvis classic: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
