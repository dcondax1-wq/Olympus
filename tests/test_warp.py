"""OLYMPUS warp: the world-to-world jump (tools/web_public/olympus/warp.js + warp.css, 2026-11-19, night-warp; owner: "crazy effects
world to world"). Every jump from one app (a world) to another is a hyperspace jump out of the page you tapped and an arrival
through a cross-document View Transition into the next world, each family with its own signature.

  a. static: warp.js is ES5 / Safari 16 safe, no WebGL, no network but the page itself, devicePixelRatio capped at 2; its door
     table equals olympus/doors.js; themes.js carries the exact WARP BOOT copy and loads warp.js; agora.css, jarvis.css, kalshi.css
     and zenith_agora.css @import warp.css first; warp.css opts in (@view-transition, type oly-warp), has every family's arrival,
     a reduced-motion fade and the 3D Off fade; the pages without themes.js (Doors, ZEUS hub, Help, Atlas) load warp.js; the
     launcher copies stay byte-identical; the family of every kind of address
  b. the jump (iPhone size, 2x): Doors page -> NQ: the overlay and its canvas (<= 2x pixels) draw frames, the page goes at ~250 ms,
     NQ arrives through a View Transition typed oly-warp with family zeus (ow-old + ow-zeus), nothing is left behind, no page
     error, click -> arrival finished within the bound; then NQ -> Jarvis (the kit's seat): family home ("returning", ow-home)
  c. reduced motion: a 150 ms fade, no canvas, the arrival a 200 ms fade (ow-fade-in), nothing scales
  d. a tap during the jump goes at once
  e. never blocks: no 2D canvas -> it still goes; 'oly.warp' = 'off' -> a plain load, no overlay, no transition
  f. a script's location.href right after a tap (the Navigation API: Polis' buildings, the search boxes' Enter) jumps too
  g. left alone: same-page hash links, new tabs, other sites, files that are not pages
    python -X utf8 -m tests.test_warp            (browser parts under: flock -w 2400 /tmp/olympus_browser.lock)
    python -X utf8 -m tests.test_warp --shots    also writes research/handoff/2026-11-19/warp/ (3 key frames at 2x + warp.mp4)
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-19", "warp")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------ a. static
def boot_of(js):
    a = js.find("  function olyWarpBoot(W, d) {")
    b = js.find("  /* <<< WARP BOOT */")
    return js[a:b] if a >= 0 and b > a else ""


def test_static():
    js, css, th = read(KIT, "warp.js"), read(KIT, "warp.css"), read(KIT, "themes.js")
    code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    bad = [p for p in (r"=>", r"\blet\s", r"\bconst\s", r"`", r"\?\.", r"\?\?", r"\bclass\s+[A-Z]", r"\.\.\.[a-z]") if re.search(p, code)]
    check("a. warp.js is ES5 / Safari 16 safe (no arrows, let / const, template strings, ?. / ??, classes, spread)", not bad, bad)
    check("a. warp.js draws on a 2D canvas only (no WebGL), capped at 2x pixels, loads nothing but the next page (prefetch)",
          "getContext('2d')" in js and "webgl" not in code.lower() and "MAX_DPR = 2" in js and "Math.min(MAX_DPR, W.devicePixelRatio" in js
          and len(re.findall(r"\bfetch\(", code)) == 1 and "XMLHttpRequest" not in js and "import(" not in code and "https://" not in code)
    check("a. warp.js never blocks: errors navigate at once, a timer goes without frames, a give-up timer frees the page, taps skip",
          "catch (e) {\n      st.err" in js and "setTimeout(function () { go(r); }, r.navAt + 70)" in js and "T.give" in js
          and "addEventListener('pointerdown'" in js and "skip()" in js)
    # the door table = olympus/doors.js ids
    out = subprocess.run(["node", "-e", "const D = require(process.argv[1]); const o = {}; D.DOORS.forEach((d) => { o[d.id] = d.ids.join(' '); }); console.log(JSON.stringify(o));",
                          os.path.join(KIT, "doors.js")], capture_output=True, text=True, timeout=30)
    doors = json.loads(out.stdout or "{}")
    mine = dict(re.findall(r"^\s{4}(zeus|money|kalshi|more): '([a-z ]+)'", js, re.M))
    check("a. warp.js's door table is olympus/doors.js's (every app's family = its door, the cities and home first)", doors and mine == doors, (mine, doors))
    boot = boot_of(js)
    check("a. themes.js carries warp.js's WARP BOOT letter for letter, runs it, then loads warp.js async (never waited on)",
          boot and boot in th and "olyWarpBoot(window, document);" in th and "new URL('warp.js?v=w2', me.src)" in th and "s.async = true" in th, len(boot))
    check("a. the boot reads the one-shot hand-off before the first frame only (no body yet), 6 s fresh, for this page, then removes it",
          "d.body) return" in boot and "Date.now() - h.t < 6000" in boot and "h.to !== p" in boot and "s.removeItem('oly.warp.in')" in boot and "pagereveal" in boot)
    agora = re.sub(r"/\*.*?\*/", "", read(KIT, "agora.css"), flags=re.S).lstrip()
    check("a. agora.css (every kit app: its files come from the network anyway) @import warp.css as its first rule: the arrival before the first frame",
          agora.startswith('@import url("warp.css?v=w2");'))
    sw_pages = {"jarvis/index.html": "../olympus/warp.css?v=w2", "index.html": "olympus/warp.css?v=w2", "kalshi/index.html": "../olympus/warp.css?v=w2"}
    pair = '<style>@view-transition{navigation:auto;types:oly-warp}</style><link rel="stylesheet" href="%s" media="print" onload="this.media=\'all\'">'
    bad = [f for f, u in sw_pages.items() if (pair % u) not in read(WEB, *f.split("/")) or read(WEB, *f.split("/")).find(pair % u) > read(WEB, *f.split("/")).find("<script")]
    clean = [f for f in ("jarvis/jarvis.css", "kalshi/kalshi.css", "zenith_agora.css") if "warp.css" in read(WEB, *f.split("/"))]
    check("a. Jarvis, Zenith and Kalshi (their worker serves their sheets from its own copy) opt in inline at the top of <head> and load warp.css "
          "without holding the first frame (a slow site never keeps them white); their own sheets import nothing", not bad and not clean, (bad, clean))
    fams = ["home", "zeus", "money", "kalshi", "city", "lab"]
    check("a. warp.css opts in (@view-transition navigation auto, type oly-warp) and scopes every rule to it (same-page transitions keep their own)",
          "@view-transition { navigation: auto; types: oly-warp; }" in css and not re.search(r"(^|\})\s*::view-transition", css))
    check("a. warp.css: an arrival animation for every family (+ hop and back), the flash and the shape inside the new page",
          all(f"@keyframes ow-{k}" in css for k in ["in", "old", "old-home", "home", "zeus", "money", "kalshi", "city", "lab", "hop", "glow", "flash-out"])
          and all(f'data-oly-warp="{f}"' in css for f in fams) and "data-oly-warp-back" in css and "data-oly-warp-hop" in css)
    rm = css[css.find("@media (prefers-reduced-motion: reduce)"):]
    check("a. warp.css: reduced motion and 3D Off = a 200 ms fade (nothing scales, no shape); only transform / opacity move",
          "ow-fade-in .2s" in rm and "transform: none !important" in rm and 'data-fx="off"' in rm
          and not re.search(r"@keyframes[^{]*\{[^}]*(clip-path|width|height|left|top|filter)\s*:", css))
    pages = ["hub/doors.html", "hub/zeus.html", "hub/help.html", "atlas/index.html"]
    check("a. the pages without themes.js load warp.js themselves (Doors, the ZEUS hub, Help, Atlas)",
          all('src="../olympus/warp.js?v=w2" defer' in read(WEB, *p.split("/")) and "olympus/themes.js?v=" not in read(WEB, *p.split("/")) for p in pages))
    check("a. launcher.js stays byte-identical in both dashboards", read(WEB, "launcher.js") == read(ROOT, "web_next", "js", "next", "launcher.js"))
    # phone QA 2026-11-19: a jump INTO Olympus World was a View Transition the page refused ("ViewTransition opt-in disabled") and the kit
    # showed "Cities could not load"; the World now opts in like every app, and a skipped transition is never a page failure
    world, kit = read(WEB, "cities", "world", "index.html"), read(KIT, "olympus.js")
    check("a. Olympus World opts in (@view-transition, warp.css without holding the first frame) and loads warp.js for the way out",
          "@view-transition{navigation:auto;types:oly-warp}" in world and 'href="../../olympus/warp.css?v=w2" media="print"' in world
          and 'src="../../olympus/warp.js?v=w2" defer' in world)
    trap = kit[kit.find("addEventListener('unhandledrejection'"):][:900]
    check("a. the kit: a View Transition the browser skipped (AbortError / InvalidStateError ... transition) never shows 'could not load'",
          "/transition/i.test(" in trap and "InvalidStateError" in trap and trap.find("transition/i.test(") < trap.find("fail("))
    # phone QA 2026-11-19: the flash held the phone near-white (mean luminance ~210 of 255) while the next page loaded
    fk = re.search(r"@keyframes ow-flash\{[^']*\}\}", js)
    bk = re.search(r"@keyframes ow-breathe\{[^']*\}\}", js)
    check("a. the flash is a flash, not a white screen: it settles to <= 0.7 opacity, the wait breathes <= 0.6, a small white core (<= 5%)",
          fk and float(re.findall(r"opacity:([\d.]+)", fk.group(0))[-1]) <= 0.7 and bk and max(float(x) for x in re.findall(r"opacity:([\d.]+)", bk.group(0))) <= 0.6
          and "#fff 9%" not in js and "#fff 9%" not in css and "#fff 8%" not in css, (fk and fk.group(0), bk and bk.group(0)))
    # the family of each kind of address (node, a fake window)
    probe = r"""
const fs = require('fs'), vm = require('vm');
const mk = (href) => { const ev = {}; const w = { addEventListener(k, f) { ev[k] = f; }, location: new URL(href), innerWidth: 390, innerHeight: 844, devicePixelRatio: 3,
  sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} }, localStorage: { getItem() { return null; } }, navigator: {} };
  const el = () => ({ style: { setProperty() {} }, setAttribute() {}, appendChild() {}, classList: { add() {}, remove() {}, contains() { return false; } } });
  const d = { documentElement: el(), body: {}, head: el(), currentScript: { src: 'https://x.io/site/olympus/warp.js?v=w2' }, addEventListener() {}, querySelector() { return null; },
    getElementById() { return null; }, createElement: el };
  w.window = w; w.document = d; w.URL = URL; w.JSON = JSON; w.Math = Math; w.Date = Date; w.setTimeout = setTimeout;
  vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), Object.assign(w, { location: w.location, navigator: w.navigator }));
  return w.OLYMPUS_WARP; };
const A = mk('https://x.io/site/hub/doors.html'), f = (u) => { const r = A.world('https://x.io/site/' + u); return r ? r.fam + ':' + r.id : null; };
console.log(JSON.stringify({ nq: f('nq/'), root: f(''), idx: f('index.html#/brain'), jarvis: f('jarvis/'), gate: f('gate/'), ledger: f('ledger/'), accounts: f('business/accounts.html'),
  taxes: f('business/taxes.html'), kalshi: f('kalshi/'), tyche: f('tyche/'), polis: f('polis/'), kcity: f('kalshicity/'), clio: f('clio/'), zhub: f('hub/zeus.html'),
  mhub: f('hub/index.html?h=money'), dmoney: f('hub/doors.html#money'), json: f('nq/fixture.json'), other: A.world('https://other.io/nq/'), outside: A.world('https://x.io/elsewhere/'), newcity: f('world/athens/') }));
"""
    out = subprocess.run(["node", "-e", probe, os.path.join(KIT, "warp.js")], capture_output=True, text=True, timeout=30)
    try:
        got = json.loads(out.stdout)
    except ValueError:
        got = {"err": out.stderr[-500:]}
    want = {"nq": "zeus:nq", "root": "zeus:zenith", "idx": "zeus:zenith", "jarvis": "home:jarvis", "gate": "home:gate", "ledger": "money:ledger", "accounts": "zeus:business",
            "taxes": "money:business", "kalshi": "kalshi:kalshi", "tyche": "kalshi:tyche", "polis": "city:polis", "kcity": "city:kalshicity", "clio": "lab:clio",
            "zhub": "zeus:hub", "mhub": "money:hub", "dmoney": "money:hub", "json": None, "other": None, "outside": None, "newcity": "city:world"}
    check("a. the family of every kind of address (apps, the dashboard, Jarvis, the account center, hubs, doors, cities; files and other sites = none)", got == want,
          {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v} if isinstance(got, dict) else got)


# ------------------------------------------------------------------------------------------------ the browser parts
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class Server(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass                                                          # a page that left mid-download (the jump) is not an error


def serve():
    srv = Server(("127.0.0.1", 0), functools.partial(Handler, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


# every page of the context: the warp switched on (automation), and the arrival's View Transition recorded (types, its animations, when it ends)
INIT = r"""
try { if (!sessionStorage.getItem('test.nowarp')) localStorage.setItem('oly.warp', 'on'); else localStorage.setItem('oly.warp', 'off'); } catch (e) {}
addEventListener('pagereveal', (e) => {
  const v = e.viewTransition; window.__rv = { vt: !!v, t: Date.now() };
  if (!v) return;
  v.ready.then(() => {
    window.__rv.types = v.types ? Array.from(v.types) : null;
    window.__rv.anims = document.getAnimations().filter((a) => a.effect && a.effect.pseudoElement && (/^::view-transition/.test(a.effect.pseudoElement) || a.effect.target === document.documentElement)).map((a) => [a.effect.pseudoElement, a.animationName, Math.round(a.effect.getComputedTiming().endTime)]);
    const fz = sessionStorage.getItem('test.freeze');
    if (fz) { sessionStorage.removeItem('test.freeze'); document.getAnimations().forEach((a) => { if (a.effect && a.effect.pseudoElement && (/^::view-transition/.test(a.effect.pseudoElement) || a.effect.target === document.documentElement)) { a.pause(); a.currentTime = +fz; } }); window.__frozen = true; }
  }, (x) => { window.__rv.err = String(x); });
  v.finished.then(() => { window.__rv.done = Date.now(); });
});
addEventListener('pageswap', () => { try { sessionStorage.setItem('test.out', JSON.stringify(window.__olyWarp || null)); } catch (e) {} });
"""


def context(br, origin, reduced=False, scale=2, video=None):
    kw = dict(viewport={"width": 390, "height": 844}, device_scale_factor=scale, is_mobile=True, has_touch=True,
              reduced_motion="reduce" if reduced else "no-preference")
    if video:
        kw.update(record_video_dir=video, record_video_size={"width": 390, "height": 844})
    ctx = br.new_context(**kw)
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script(INIT)
    p = ctx.new_page()
    p.set_default_timeout(90000)
    errs: list = []
    p.on("pageerror", lambda e: errs.append("page error: " + str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "favicon" not in m.text else None)
    return ctx, p, errs


def open_doors(p, origin, door=""):
    p.goto(origin + "/hub/doors.html" + ("#" + door if door else ""))
    p.wait_for_function("() => window.OLYMPUS_WARP && document.querySelector('a.dr-row')", timeout=60000)


def arrived(p, url_glob):
    p.wait_for_url(url_glob, timeout=60000, wait_until="commit")
    p.wait_for_function("() => window.__rv && (window.__rv.done || !window.__rv.vt || window.__rv.err)", timeout=60000)
    return p.evaluate("""() => ({ rv: window.__rv, inn: window.__olyWarpIn, out: JSON.parse(sessionStorage.getItem('test.out') || 'null'),
      fam: document.documentElement.getAttribute('data-oly-warp'), overlay: !!document.querySelector('.oly-warp'),
      cls: document.documentElement.className, arrive: window.__olyWarp ? window.__olyWarp.arrive : 'no warp.js' })""")


def test_jump(br, origin):
    from tests import browser_kit as BK
    ctx, p, errs = context(br, origin)
    try:
        open_doors(p, origin)
        link = p.locator('a.dr-row[href="../nq/"]').first
        link.scroll_into_view_if_needed()
        t0 = p.evaluate("() => Date.now()")
        link.click()
        # the old page, while it jumps (it goes at ~250 ms; the overlay is there at once)
        a = arrived(p, "**/nq/")
        out, rv = a["out"] or {}, a["rv"] or {}
        check("b. Doors -> NQ: the jump played on the page we left (mode full, family zeus, canvas frames, went at ~250 ms)",
              out.get("mode") == "full" and out.get("fam") == "zeus" and out.get("to") == "nq" and out.get("frames", 0) >= 3 and 200 <= out.get("navAt", 0) <= 420, out)
        anims = {x[0]: x for x in rv.get("anims") or []}
        new, old = anims.get("::view-transition-new(root)"), anims.get("::view-transition-old(root)")
        check("b. NQ arrives through a cross-document View Transition typed oly-warp (old = ow-old, new = ow-zeus)",
              rv.get("vt") and "oly-warp" in (rv.get("types") or []) and new and new[1] == "ow-zeus" and old and old[1] == "ow-old", rv)
        check("b. the arrival: family zeus from the hand-off (read before the first frame), arrival animation <= 520 ms",
              a["fam"] == "zeus" and (a["inn"] or {}).get("f") == "zeus" and new and new[2] <= 520 and all(x[2] <= 520 for x in anims.values()), (a["fam"], a["inn"], anims))
        total, load = rv.get("done", 0) - t0, rv.get("t", 0) - t0 - out.get("navAt", 0)
        anim = max([x[2] for x in anims.values()] or [0])
        fx = out.get("navAt", 0) + anim
        lim = BK.limit_ms(2000) if hasattr(BK, "limit_ms") else 2000
        check(f"b. timing: the effect itself {fx} ms (jump {out.get('navAt')} + arrival {anim}) <= 900; click -> arrived {total} ms on this machine, "
              f"incl. {load} ms page load and software-GL frames (bound {lim:.0f})", 0 < fx <= 900 and 0 < total <= lim, (fx, total, load))
        check("b. nothing left behind: no overlay, no warp classes after the arrival", not a["overlay"] and "oly-warp-vt" not in a["cls"] and "oly-warp-in" not in a["cls"], a["cls"])
        # home: NQ -> Jarvis through the kit's seat ("Back to Jarvis")
        p.wait_for_function("() => window.OLYMPUS_WARP && document.querySelector('a.oly-home')", timeout=60000)
        p.evaluate("() => document.querySelector('a.oly-home').click()")
        h = arrived(p, "**/jarvis/")
        hout, hrv = h["out"] or {}, h["rv"] or {}
        hanims: dict = {}
        for x in hrv.get("anims") or []:
            hanims.setdefault(x[0], []).append(x[1])
        home = hanims.get("::view-transition-new(root)") == ["ow-home"] and hanims.get("::view-transition-old(root)") == ["ow-old-home"]
        plain = "-ua-view-transition-fade-in" in hanims.get("::view-transition-new(root)", [])      # warp.css not there yet (it never holds Jarvis's first frame)
        check(f"b. NQ -> Jarvis (the seat): the HOME jump (the light falls inward into the gold orb), Jarvis arrives through the typed View Transition "
              f"({'home: the old world falls away, home settles around you' if home else 'a cross-fade: warp.css was still on its way'})",
              hout.get("fam") == "home" and hout.get("to") == "jarvis" and hrv.get("vt") and "oly-warp" in (hrv.get("types") or []) and (home or plain), (hout, hrv))
        real = [e for e in errs if "Failed to load resource" not in e]
        check("b. no page error and no console error on Doors, NQ or Jarvis during the jumps", not real, real[:6])
    finally:
        ctx.close()


def test_reduced(br, origin):
    ctx, p, errs = context(br, origin, reduced=True)
    try:
        open_doors(p, origin, "money")
        p.locator('a.dr-row[href="../ledger/"]').first.click()
        a = arrived(p, "**/ledger/")
        out, rv = a["out"] or {}, a["rv"] or {}
        anims = {x[0]: x for x in rv.get("anims") or []}
        new = anims.get("::view-transition-new(root)")
        check("c. reduced motion: a 150 ms fade on the page we left (no canvas frames), it goes at ~150 ms",
              out.get("mode") == "fade" and out.get("frames") == 0 and 100 <= out.get("navAt", 0) <= 320, out)
        check("c. reduced motion: the arrival is a 200 ms fade (ow-fade-in), no shape, nothing longer than 250 ms",
              rv.get("vt") and new and new[1] == "ow-fade-in" and new[2] <= 250 and "::after" not in anims and all(x[2] <= 250 for x in anims.values()), anims)
    finally:
        ctx.close()


def test_skip_and_safety(br, origin):
    ctx, p, errs = context(br, origin)
    try:
        open_doors(p, origin)
        p.locator('a.dr-row[href="../trading/"]').first.click()
        p.wait_for_timeout(60)
        p.mouse.click(200, 400)                                       # a tap during the jump
        a = arrived(p, "**/trading/")
        out = a["out"] or {}
        check("d. a tap during the jump goes at once (skipped, went well before 250 ms)", out.get("skipped") is True and 0 < out.get("navAt", 999) < 230, out)
        # no 2D canvas: the jump still goes
        open_doors(p, origin)
        p.evaluate("() => { HTMLCanvasElement.prototype.getContext = function () { return null; }; }")
        p.locator('a.dr-row[href="../pnyx/"]').first.click()
        a = arrived(p, "**/pnyx/")
        out = a["out"] or {}
        check("e. no 2D canvas (an error mid-jump): it still goes, at once", "canvas" in (out.get("err") or "") and out.get("navAt", 999) < 200, out)
        # switched off: a plain load
        open_doors(p, origin)
        p.evaluate("() => { sessionStorage.setItem('test.nowarp', '1'); localStorage.setItem('oly.warp', 'off'); }")
        p.locator('a.dr-row[href="../aegis/"]').first.click()
        a = arrived(p, "**/aegis/")
        check("e. 'oly.warp' = 'off': a plain load (no jump, no View Transition, no hand-off)",
              (a["out"] or {}).get("runs") == 0 and not (a["rv"] or {}).get("vt") and not a["inn"], a)
        p.evaluate("() => { sessionStorage.removeItem('test.nowarp'); localStorage.setItem('oly.warp', 'on'); }")
        # a script's location.href right after a tap (the Navigation API)
        open_doors(p, origin)
        p.evaluate("""() => { const b = document.createElement('button'); b.id = 'scripted'; b.textContent = 'go'; b.style.cssText = 'position:fixed;left:10px;top:10px;z-index:99;width:90px;height:50px';
          b.onclick = () => { location.href = '../mint/'; }; document.body.appendChild(b); }""")
        p.click("#scripted")
        a = arrived(p, "**/mint/")
        out = a["out"] or {}
        has_nav = p.evaluate("() => !!window.navigation")
        check("f. location.href = ... right after a tap jumps too (Navigation API): family money", not has_nav or (out.get("fam") == "money" and out.get("runs", 0) >= 1 and a["fam"] == "money"), (has_nav, out, a["fam"]))
        # a page that does not opt in (Atlas): the jump plays, the browser's transition is skipped as we leave (no error on arrival)
        open_doors(p, origin, "more")
        n0 = len(errs)
        p.evaluate("""() => { const a = document.createElement('a'); a.href = '../atlas/'; a.id = 'toAtlas'; a.textContent = 'atlas';
          a.style.cssText = 'position:fixed;left:10px;top:10px;z-index:99;width:90px;height:50px'; document.body.appendChild(a); }""")
        p.click("#toAtlas")
        a = arrived(p, "**/atlas/")
        p.wait_for_timeout(800)
        late = [e for e in errs[n0:] if "Failed to load resource" not in e]
        check("g. Atlas (no arrival sheet): the jump plays, no View Transition, no error on arrival",
              (a["out"] or {}).get("fam") == "lab" and not (a["rv"] or {}).get("vt") and not late, (a["out"], late))
        # left alone
        open_doors(p, origin)
        res = p.evaluate("""() => { const W = OLYMPUS_WARP, mk = (h, t) => { const a = document.createElement('a'); a.href = h; if (t) a.target = t; a.textContent = 'x'; a.style.cssText = 'position:fixed;left:0;top:0;width:40px;height:40px;z-index:99'; document.body.appendChild(a); return a; };
          const out = {}; const tryOne = (k, h, t) => { const a = mk(h, t); let prevented = null; const f = (e) => { prevented = e.defaultPrevented; e.preventDefault(); }; window.addEventListener('click', f); a.click(); window.removeEventListener('click', f); a.remove(); out[k] = [prevented, W.state().active]; };
          tryOne('hash', '#money'); tryOne('blank', '../nq/', '_blank'); tryOne('other', 'https://example.com/'); tryOne('json', '../nq/fixture.json');
          return out; }""")
        check("g. left alone: a same-page hash, a new tab, another site, a file that is not a page (no jump, the link does what it did)",
              all(v == [False, False] for v in res.values()), res)
        real = [e for e in errs if "Failed to load resource" not in e]
        check("d-g. no page error and no console error", not real, real[:6])
    finally:
        ctx.close()


# ------------------------------------------------------------------------------------------------ --shots: 3 key frames + a short film
def shots(br, origin):
    os.makedirs(SHOTS, exist_ok=True)
    ctx, p, errs = context(br, origin, scale=2)
    try:
        open_doors(p, origin)
        rc = p.evaluate("() => { const r = document.querySelector('a.dr-row[href=\"../nq/\"]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        p.evaluate(f"() => OLYMPUS_WARP.play('nq', {{ at: 0.6, x: {rc[0]}, y: {rc[1]} }})")
        p.screenshot(path=os.path.join(SHOTS, "1-leave-zeus-lightning.png"))
        p.evaluate("() => OLYMPUS_WARP.play('jarvis', { at: 0.5, x: 195, y: 700 })")
        p.screenshot(path=os.path.join(SHOTS, "2-home-returning-to-jarvis.png"))
        p.evaluate("() => OLYMPUS_WARP.stop()")
        open_doors(p, origin, "money")
        p.evaluate("() => sessionStorage.setItem('test.freeze', '90')")
        p.locator('a.dr-row[href="../ledger/"]').first.click()
        p.wait_for_url("**/ledger/", timeout=60000, wait_until="commit")
        p.wait_for_function("() => window.__frozen === true", timeout=60000)
        p.wait_for_timeout(250)
        p.screenshot(path=os.path.join(SHOTS, "3-arrive-money-world.png"))
        check("shots: 3 key frames at 2x in research/handoff/2026-11-19/warp/", all(os.path.isfile(os.path.join(SHOTS, f)) for f in
              ("1-leave-zeus-lightning.png", "2-home-returning-to-jarvis.png", "3-arrive-money-world.png")))
    finally:
        ctx.close()
    # the film (<= 6 s): Doors -> NQ (ZEUS lightning) -> Jarvis (home, "returning"), at 390 x 844
    vdir = os.path.join(SHOTS, "_video")
    shutil.rmtree(vdir, ignore_errors=True)
    ctx, p, errs = context(br, origin, scale=1, video=vdir)
    try:
        open_doors(p, origin)
        p.wait_for_timeout(500)
        p.locator('a.dr-row[href="../nq/"]').first.click()
        arrived(p, "**/nq/")
        p.wait_for_timeout(900)
        p.wait_for_function("() => window.OLYMPUS_WARP && document.querySelector('a.oly-home')", timeout=60000)
        p.evaluate("() => document.querySelector('a.oly-home').click()")
        arrived(p, "**/jarvis/")
        p.wait_for_timeout(700)
    finally:
        video = p.video
        ctx.close()
    webm = video.path() if video else ""
    mp4 = os.path.join(SHOTS, "warp.mp4")
    if webm and shutil.which("ffmpeg"):
        subprocess.run(["/home/user/heavy.sh", "ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-t", "6", "-vf", "scale=390:-2", "-c:v", "libx264", "-preset", "slow", "-crf", "30",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", mp4], timeout=600)
    shutil.rmtree(vdir, ignore_errors=True)
    size = os.path.getsize(mp4) if os.path.isfile(mp4) else 0
    check(f"shots: warp.mp4 ({size // 1024} KB, under 3 MB)", 0 < size < 3 * 1024 * 1024, size)


def main():
    test_static()
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    srv, origin = serve()
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            for part in (test_jump, test_reduced, test_skip_and_safety):
                try:
                    part(br, origin)
                except Exception as e:  # noqa: BLE001 - a broken part is one failure, the rest still run
                    check(f"{part.__name__} ran to the end", False, repr(e)[:600])
            if "--shots" in sys.argv:
                shots(br, origin)
    finally:
        srv.shutdown()
    ok = sum(RES)
    print(f"\n{ok}/{len(RES)} passed")
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
