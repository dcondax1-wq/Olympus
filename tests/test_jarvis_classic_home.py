"""Jarvis home as it was (2026-11-18, owner: "back to how it was"; "my screen looks weird"): Classic Jarvis is the default look again,
in the order of 2026-11-06 (f8df6008), and the bottom of the phone screen is fixed. Opens the real page in Chromium as an iPhone
(375 x 667, and 390 x 844 / 430 x 932 with the home-bar safe area) and checks:
  a. the default look is Classic (violet, data-jlook) with no saved choice; the AGORA courtyard banner is hidden
  b. the order: the HUD header (J.A.R.V.I.S. title, greeting, the one sentence) -> KALSHI TODAY / NQ BOTS TODAY -> the core -> the tiles
  c. the bottom: the dock sits at most 20 px above the screen's edge (no empty band), the page scrolls fully above it (the footer ends
     above the dock and its row), no sideways scroll
  d. the bottom-right 60 px corner is free of the dock's keys on a phone; Send shows once something is typed; nothing moves on focus alone
     (the full width comes back only while the keyboard is up: .kb from fitDock, not emulated here)
  e. a web host's badge in the corner (as "Powered by Netlify") lifts the dock above it
Run under the machine's one-browser lock:
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_jarvis_classic_home
"""
from __future__ import annotations

import functools
import http.server
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


SEEN = ("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.orb.tips', '3');"
        " localStorage.setItem('jarvis.tour.seen', '1'); localStorage.setItem('olympus.welcome.v1', '1'); } catch (e) {}")
R = """(q) => { const e = typeof q === 'string' ? document.querySelector(q) : q; if (!e) return null; const cs = getComputedStyle(e);
  if (cs.display === 'none' || cs.visibility === 'hidden') return null; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 ? [r.left, r.top, r.right, r.bottom].map(Math.round) : null; }"""
BADGE = """(() => { const b = document.createElement('a'); b.id = 'netlify-badge'; b.textContent = 'Powered by Netlify';
  b.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;background:#fff;color:#000;padding:10px 14px;border-radius:8px;font:600 14px sans-serif';
  document.body.appendChild(b); })()"""


def main():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/jarvis/?demo=1"
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            for w, h, inset in ((375, 667, 0), (390, 844, 34), (430, 932, 34)):
                dev = dict(pw.devices["iPhone 13"]); dev.pop("default_browser_type", None)
                dev.update(viewport={"width": w, "height": h}, device_scale_factor=1)
                ctx = br.new_context(**dev, service_workers="block")
                ctx.add_init_script(SEEN)
                ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)))
                if inset:
                    try:
                        ctx.new_cdp_session(p).send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": 47, "bottom": inset, "left": 0, "right": 0}})
                    except Exception as e:                                    # an older Chromium: the 8 px case only
                        print("[note] no safe-area override:", e)
                        inset = 0
                p.goto(url)
                p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
                p.wait_for_timeout(2500)
                tag = f"{w}x{h}"
                look = p.evaluate("[document.documentElement.dataset.jlook || '', localStorage.getItem('jarvis.look'), getComputedStyle(document.documentElement).getPropertyValue('--c').trim()]")
                check(f"a. {tag}: Classic Jarvis is the default look (violet), nothing saved; the AGORA courtyard banner hidden",
                      look == ["classic", None, "#a855f7"] and p.evaluate(R, "#court") is None and p.evaluate(R, ".jtitle") is not None, look)
                tops = [p.evaluate(R, q) for q in (".jtitle", "#hello", "#heroLine", "#kbox", "#stage", "#hfirst")]
                check(f"b. {tag}: the order as it was: title, greeting, the one sentence, KALSHI / NQ BOTS TODAY, the core, then the tiles",
                      all(tops) and [t[1] for t in tops] == sorted(t[1] for t in tops), tops)
                dock, sw = p.evaluate(R, "#dock"), p.evaluate("document.documentElement.scrollWidth")
                gap = h - dock[3]
                check(f"c. {tag}: the dock sits {gap} px above the edge (8 px, or the home-bar safe area less 16 px: no empty band); no sideways scroll",
                      gap == (max(8, inset - 16)) and sw <= w, (dock, sw))
                # the demo cards may still grow the page and the scroll may glide: keep asking for the end until the scroller is
                # really there (scrollTop at its max) and has stayed there with the same height for 3 polls (a real end, not a guess)
                try:
                    p.wait_for_function("""(() => { const s = document.getElementById('home'), k = s.scrollHeight + ':' + s.scrollTop;
                        const atEnd = s.scrollTop >= s.scrollHeight - s.clientHeight - 1;
                        window.__endN = atEnd && window.__endK === k ? (window.__endN || 0) + 1 : 0; window.__endK = k;
                        if (!atEnd) s.scrollTop = 1e6;
                        return window.__endN >= 3; })()""", timeout=30000, polling=250)
                except Exception as e:
                    print("[note] the scroller never settled at its end:", str(e)[:120])
                foot, home, chip = p.evaluate(R, "#home .hfoot"), p.evaluate(R, "#home"), p.evaluate(R, "#next")
                check(f"c. {tag}: scrolled to the end, the footer ends inside the scroller, above the chip row and the dock",
                      foot and home and foot[3] <= home[3] and home[3] <= chip[1] and home[3] <= dock[1], (foot, home, chip, dock))
                keys = [p.evaluate(R, q) for q in ("#mic", "#spk", "#ask .send", "#moreB")]
                free = all(k is None or k[2] <= w - 60 for k in keys)
                check(f"d. {tag}: the bottom-right 60 px corner is free of the dock's keys; Send rests while the field is empty", free and keys[2] is None, keys)
                more0 = p.evaluate(R, "#moreB")
                p.focus("#q")
                p.wait_for_timeout(300)
                more1 = p.evaluate(R, "#moreB")
                p.fill("#q", "how are my bots")
                p.wait_for_timeout(200)
                send = p.evaluate(R, "#ask .send")
                check(f"d. {tag}: focus alone moves no key (a tap on ⋯ while typing lands on ⋯); Send shows once something is typed",
                      more0 == more1 and send is not None, (more0, more1, send))
                p.fill("#q", "")
                p.evaluate("document.activeElement.blur()")
                p.evaluate(BADGE)
                p.wait_for_timeout(1200)
                b, d3 = p.evaluate(R, "#netlify-badge"), p.evaluate(R, "#dock")
                check(f"e. {tag}: a host's badge in the corner lifts the dock above it", b and d3 and d3[3] <= b[1], (b, d3))
                check(f"e. {tag}: no page errors", not errs, errs[:3])
                ctx.close()
            br.close()
    finally:
        srv.shutdown()
    n = sum(RES)
    print(f"\njarvis classic home: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
