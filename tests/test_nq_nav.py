"""NQ nav (night-nq-nav 2026-11-27; owner: "make everything better, 3D, higher quality, effects, features"): the NQ pages as ONE app.
tools/web_public/nq/nqnav.js + nqnav.css (the dock, the PC pill, pull-to-refresh, transitions, install / offline chips) + nqsw.js (NQ-only
offline worker) + nq/manifest.webmanifest. Lead wires: research/handoff/2026-11-27/nav/LEAD_WIRES.md.

  a. static: the files, no markup from data, no outside URL, OLYMPUS NIGHT colours (no cyan / brown), reduced motion, the worker touches
     only its own caches and same-origin GETs, the manifest opens into NQ and its shortcuts point at real pages, the lead's lines exist
  b. browser 390x844 (pages served with the one script line added, ntfy mocked with a PC post 4 min old: LIT + ATLAS + BLITZ armed):
     the dock on Home / Live / Accounts / Brain with the right tab lit, taps >= 44, no sideways scroll; the pill "PC 4m · 2 armed" (BLITZ never
     counted or named); the sheet; a tab tap navigates; pull-to-refresh hands 'nq:refresh' to the page; a 3 h old post = red; framed = no dock;
     reduced motion = no pulse; offline chip; the worker opens Live offline after one visit; 1440 floats the dock
Run: python -X utf8 -m tests.test_nq_nav [--shots]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

NQ = os.path.join(ROOT, "tools", "web_public", "nq")
WIRES = os.path.join(ROOT, "research", "handoff", "2026-11-27", "nav", "LEAD_WIRES.md")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "nav", "shots")
check = AK.check


def part_a():
    js, css, sw = (AK.read(os.path.join(NQ, f)) for f in ("nqnav.js", "nqnav.css", "nqsw.js"))
    check("a. nqnav.js / nqnav.css / nqsw.js are there", bool(js and css and sw))
    check("a. no markup from data (no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval)",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js))
    check("a. no outside address in nqnav.js (the PC feed only through ../pc_feed.js + ../status_feed.json)", not re.search(r"https?://(?!www\.w3\.org/2000/svg)", js))
    low = css.lower()
    check("a. OLYMPUS NIGHT: violet #9d59ee, gold #f1c14b, mint #77db89, cards #16131e; no cyan, no brown / olive",
          all(c in low for c in ("#9d59ee", "#f1c14b", "#77db89", "#16131e", "#3e255e", "#4d2e76"))
          and not re.search(r"cyan|#0ff\b|#00ffff|#22d3ee|#06b6d4|#67e8f9|brown|olive|#8b4513|#a0522d", low))
    check("a. motion only under prefers-reduced-motion: no-preference (transitions, pulse, sheet, chips, spinner)",
          low.count("prefers-reduced-motion: no-preference") >= 4 and "@view-transition" in low and "view-transition-name: nqnav-ink" in low)
    check("a. the worker: only 'nqnav-' caches deleted, same-origin GETs only, a 404 stays a 404, an offline page with Retry",
          "k.startsWith('nqnav-')" in sw and "u.origin !== self.location.origin" in sw and "req.method !== 'GET'" in sw and "if (r) return r;" in sw and "Retry" in sw)
    m = json.loads(AK.read(os.path.join(NQ, "manifest.webmanifest")))
    shortcuts = [s["url"] for s in m.get("shortcuts") or []]
    check("a. the manifest opens straight into NQ (start_url ./, scope ./, standalone, black) with real icons + shortcuts",
          m.get("start_url") == "./" and m.get("scope") == "./" and m.get("display") == "standalone" and m.get("background_color") == "#000000"
          and all(os.path.exists(os.path.join(NQ, i["src"])) for i in m["icons"]) and len(shortcuts) >= 3
          and all(os.path.exists(os.path.join(NQ, u.split("?")[0].lstrip("./"))) for u in shortcuts), (m.get("start_url"), shortcuts))
    w = AK.read(WIRES) if os.path.exists(WIRES) else ""
    check("a. LEAD_WIRES.md gives the one line per page", w.count('<script src="nqnav.js?v=1" defer></script>') >= 1 and "live.html" in w and "accounts.html" in w)


def post(age_s, now=None):
    now = now or time.time()
    t = int(now - age_s)
    lite = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": t, "every_s": 300,
            "pc_verdict": {"code": "TRADING", "label": "TRADING YOUR EVAL", "level": "ok"},
            "reporter": {"t": t + 20, "server": True, "nt": True, "market_open": True},
            "ar": {"lit": [1, 1], "atlas": [1, 1], "blitz": [1, 1], "rapid": [1, 0]},
            "board": {}, "accounts": []}
    return json.dumps({"event": "message", "time": t + 20, "message": json.dumps(lite)}) + "\n"


TAG = '<script src="nqnav.js?v=1" defer></script>'


def inject(ctx, origin):
    """the lead's one line, added on the fly until the pages carry it (a page that already has it is left as it is)"""
    def route(r):
        try:
            serve_one(r)
        except Exception:      # the context closed while a probe was in flight
            pass

    def serve_one(r):
        res = r.fetch()
        if res.status != 200 or r.request.method != "GET":
            r.fulfill(response=res)
            return
        body = res.text()
        if "nqnav.js" not in body:
            body = body.replace("</body>", TAG + "</body>")
        r.fulfill(response=res, body=body)
    ctx.route(re.compile(re.escape(origin) + r"/nq/[a-z_]+\.html(\?.*)?$"), route)


READ = """() => { const tabs = [...document.querySelectorAll('.nqn-tab')]; const pill = document.querySelector('.nqn-float');
  return { tabs: tabs.map((a) => a.dataset.tab), shown: tabs.filter((a) => !a.hidden).map((a) => a.dataset.tab),
    on: tabs.filter((a) => a.classList.contains('is-on')).map((a) => a.dataset.tab), cur: (document.querySelector('.nqn-tab[aria-current=page]') || { getAttribute: () => '' }).getAttribute('data-tab'),
    small: tabs.filter((a) => !a.hidden).map((a) => a.getBoundingClientRect()).filter((r) => r.width < 44 || r.height < 44).length,
    pill: pill ? pill.textContent : null, lv: pill ? pill.dataset.lv : null, pillH: pill ? pill.getBoundingClientRect().height : 0,
    dockB: document.querySelector('.nqn-dock') ? Math.round(document.querySelector('.nqn-dock').getBoundingClientRect().bottom) - innerHeight : null,
    on2: document.documentElement.classList.contains('nqnav-on') } }"""


def part_b():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    srv, origin = AK.serve({"/home.json": None})
    shots = "--shots" in sys.argv
    want = {"index.html": "home", "live.html": "live", "accounts.html": "accounts", "brain.html": "brain"}
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": post(4 * 60)})
            inject(ctx, origin)
            for f, tab in want.items():
                p.goto(f"{origin}/nq/{f}")
                p.wait_for_function("window.NQNAV && document.querySelector('.nqn-float') && /PC \\d/.test(document.querySelector('.nqn-float').textContent)", timeout=60000)
                o = p.evaluate(READ)
                check(f"b. {f}: 7 tabs, '{tab}' lit (aria-current), every tab >= 44 px, dock at the bottom, no sideways scroll",
                      o["tabs"] == ["home", "live", "chart", "accounts", "flow", "brain", "pc"] and o["on"] == [tab] and o["cur"] == tab
                      and o["small"] == 0 and o["dockB"] == 0 and AK.no_sideways(p) and o["on2"], o)
                check(f"b. {f}: the pill 'PC 4m · 2 armed' green (BLITZ armed on the PC but never counted)", o["pill"] == "PC 4m · 2 armed" and o["lv"] == "ok" and o["pillH"] >= 30, o)
                if shots:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.screenshot(path=os.path.join(SHOTS, f"nav-390-{tab}.png"))
            check("b. no console error, nothing off the site but the mocked PC feed", not errs and not off and p.mocked, (errs[:3], off[:3]))

            # the sheet
            p.click(".nqn-float")
            p.wait_for_selector(".nqn-sheet")
            sh = p.evaluate("document.querySelector('.nqn-sheet').textContent")
            check("b. tap the pill = the sheet: heartbeat 4m, server answering, verdict, armed Zlarior + ATLAS, never BLITZ, Refresh + PC health",
                  "4m ago" in sh and "answering" in sh and "TRADING YOUR EVAL" in sh and "Zlarior 50K, ATLAS 25K" in sh and "BLITZ" not in sh.upper().replace("BLITZ", "BLITZ") and "blitz" not in sh.lower()
                  and "Refresh now" in sh and "PC health" in sh, sh)
            if shots:
                p.screenshot(path=os.path.join(SHOTS, "nav-390-sheet.png"))
            p.keyboard.press("Escape")
            check("b. Escape closes the sheet", p.evaluate("!document.querySelector('.nqn-sheet')"))

            # pull to refresh, claimed by the page
            p.evaluate("window.__ref = 0; addEventListener('nq:refresh', (e) => { e.preventDefault(); window.__ref++; e.detail.done(); }); scrollTo(0, 0)")
            p.evaluate("""() => { const t = document.querySelector('main') || document.body; const mk = (y) => new Touch({ identifier: 1, target: t, clientX: 195, clientY: y });
              t.dispatchEvent(new TouchEvent('touchstart', { touches: [mk(120)], bubbles: true }));
              for (let y = 130; y <= 330; y += 20) t.dispatchEvent(new TouchEvent('touchmove', { touches: [mk(y)], bubbles: true }));
              t.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [mk(330)], bubbles: true })); }""")
            p.wait_for_timeout(500)
            check("b. pull down at the top = one 'nq:refresh' handed to the page (it claimed it: no reload)", p.evaluate("window.__ref") == 1 and "brain.html" in p.url, p.evaluate("window.__ref"))

            # a tab tap navigates, the new page lights its tab
            p.click(".nqn-tab[data-tab=live]")
            p.wait_for_url("**/nq/live.html", timeout=30000)
            p.wait_for_function("window.NQNAV && document.querySelector('.nqn-tab.is-on')", timeout=30000)
            check("b. tap 'Live' = live.html with Live lit", p.evaluate("document.querySelector('.nqn-tab.is-on').dataset.tab") == "live")

            # offline chip
            ctx.set_offline(True)
            p.evaluate("dispatchEvent(new Event('offline'))")
            p.wait_for_selector(".nqn-chip.off", timeout=5000)
            chip = p.evaluate("document.querySelector('.nqn-chip.off').textContent")
            check("b. offline = the chip 'Offline: the numbers are from your last visit (PC report ... old)'", "Offline" in chip and "last visit" in chip and "PC report" in chip, chip)
            if shots:
                p.screenshot(path=os.path.join(SHOTS, "nav-390-offline-chip.png"))
            ctx.set_offline(False)
            ctx.unroute_all(behavior="ignoreErrors")
            ctx.close()

            # stale + saved pill + reduced motion
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, reduced=True, mock={"json?poll=1": post(3 * 3600)})
            inject(ctx, origin)
            p.goto(f"{origin}/nq/accounts.html")
            p.wait_for_function("document.querySelector('.nqn-float') && /PC \\d/.test(document.querySelector('.nqn-float').textContent)", timeout=60000)
            o = p.evaluate(READ)
            anim = p.evaluate("getComputedStyle(document.querySelector('.nqn-float i')).animationName")
            check("b. a post 3 h old = 'PC 3h · 2 armed' red; reduced motion = no pulse", o["pill"] == "PC 3h · 2 armed" and o["lv"] == "bad" and anim == "none", (o["pill"], o["lv"], anim))
            ctx.unroute_all(behavior="ignoreErrors")
            ctx.close()

            # framed: no dock (the host has its own navigation)
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": post(60)})
            inject(ctx, origin)
            p.goto(f"{origin}/nq/index.html")
            p.evaluate("(u) => { document.body.textContent = ''; const f = document.createElement('iframe'); f.src = u; f.style.cssText = 'width:390px;height:700px'; document.body.appendChild(f); }", f"{origin}/nq/live.html")
            p.wait_for_function("(() => { const f = document.querySelector('iframe'); return f && f.contentWindow && f.contentWindow.NQNAV; })()", timeout=60000)
            p.wait_for_timeout(300)
            fx = next(f for f in p.frames if f.url.endswith("/nq/live.html"))
            check("b. framed (inside Jarvis / a hub): no dock, no floating pill, no body padding", fx.evaluate("!document.querySelector('.nqn-dock') && !document.querySelector('.nqn-float') && !document.documentElement.classList.contains('nqnav-on')"))
            ctx.unroute_all(behavior="ignoreErrors")
            ctx.close()

            # night-nq-speed's shared feed (window.NQ_FEED) wins: the pill never polls ntfy itself
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": post(4 * 60)})
            ctx.add_init_script("""(() => { const t = Math.floor(Date.now() / 1000) - 120, post = { t, ar: { lit: [1, 1], blitz: [1, 1], atlas: [1, 0] }, reporter: { t, server: true } };
              let cbs = []; window.NQ_FEED = { cached: () => JSON.parse(JSON.stringify(post)), on: (cb) => { cbs.push(cb); cb(JSON.parse(JSON.stringify(post)), { src: 'net' }); return () => {}; },
                latest: () => Promise.resolve(post), refresh: () => Promise.resolve(post), info: () => ({ src: 'net' }) }; })()""")
            inject(ctx, origin)
            p.goto(f"{origin}/nq/accounts.html")
            p.wait_for_function("document.querySelector('.nqn-float') && /PC \\d/.test(document.querySelector('.nqn-float').textContent)", timeout=60000)
            pill = p.evaluate("document.querySelector('.nqn-float').textContent")
            nav_polls = [u for u in p.mocked]
            check("b. with nqfeed.js (window.NQ_FEED) the pill reads it: 'PC 2m · 1 armed' (BLITZ out)", pill == "PC 2m · 1 armed", (pill, len(nav_polls)))
            ctx.unroute_all(behavior="ignoreErrors")
            ctx.close()

            # 1440: the dock floats, centered
            ctx, p, errs, seen, off = AK.page(br, origin, w=1440, h=900, mock={"json?poll=1": post(4 * 60)})
            inject(ctx, origin)
            p.goto(f"{origin}/nq/live.html")
            p.wait_for_function("document.querySelector('.nqn-float') && /PC \\d/.test(document.querySelector('.nqn-float').textContent)", timeout=60000)
            r = p.evaluate("(() => { const b = document.querySelector('.nqn-dock').getBoundingClientRect(); return [Math.round(b.left), Math.round(b.width), Math.round(b.bottom)]; })()")
            check("b. 1440: the dock floats centered (600 px, 16 px above the bottom), no sideways scroll", r == [420, 600, 884] and AK.no_sideways(p), r)
            if shots:
                p.screenshot(path=os.path.join(SHOTS, "nav-1440-live.png"))
            ctx.unroute_all(behavior="ignoreErrors")
            ctx.close()

            # the worker: Live opens offline after one visit
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
            p = ctx.new_page()
            p.goto(f"{origin}/nq/live.html")
            p.evaluate("navigator.serviceWorker.register('nqsw.js', { scope: './' }).then(() => navigator.serviceWorker.ready)")
            p.wait_for_function("navigator.serviceWorker.controller || (location.reload(), false)", timeout=30000, polling=1500)
            p.wait_for_load_state("load")
            p.wait_for_timeout(1500)
            ctx.set_offline(True)
            p.reload()
            ok = p.evaluate("!!document.querySelector('script[src^=\"live.js\"]') && document.title.length > 0")
            p.goto(f"{origin}/nq/never_saved_page.html")
            msg = p.evaluate("document.body.textContent")
            check("b. the worker: Live opens offline after one visit; a never-saved page = the 'Offline · Retry' card, not a browser error",
                  ok and "Offline" in msg and "Retry" in msg, (ok, msg[:120]))
            ctx.unroute_all(behavior="ignoreErrors")
            ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
