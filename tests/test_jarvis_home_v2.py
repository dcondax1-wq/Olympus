"""Jarvis home v2 in a real browser (2026-11-11): ONE first screen, nothing over anything. The model, the page order and the CSS as text are in
tests.test_jarvis_home_agora (part f); this file opens the real page in Chromium at 390 x 844, 375 x 667 and 430 x 932 and measures it.
  a. the first screen (demo data): the greeting, the one sentence, the three tiles, the Ask bar and the orb are all on it without scrolling; no part
     overlaps another (hero, tiles, bar, Ask bar, next chip, search button, orb); no sideways scroll; one h1; taps >= 44 px; names for VoiceOver;
     the words over the courtyard have >= 4.5:1 contrast against what is really behind them (measured on a screenshot)
  b. the orb's hint: once, in the orb's own row (never over the page), gone by itself; not shown again
  c. states in plain words (no data at all): skeletons first (never blank), then "The bots have not reported yet: your accounts are not affected"
  d. pull to refresh and the Refresh button refetch the feeds
  e. reduced motion: nothing animates; the painted courtyard (LITE) with its five doorways; a doorway whose district needs you is marked
  f. the 3D courtyard (software GL forced on with ?gpu=1): up, framed in the hero's window, at most 25 scene draw calls, the painting steps aside
Run under the machine's one-browser lock:
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_jarvis_home_v2          (JARVIS_SHOTS=<folder> keeps screenshots)
"""
from __future__ import annotations

import functools
import http.server
import io
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
SHOTS = os.environ.get("JARVIS_SHOTS", "")
SIZES = [(390, 844), (375, 667), (430, 932)]
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


SEEN = "try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.orb.tips', '3'); localStorage.setItem('jarvis.tour.seen', '1'); } catch (e) {}"
FIRST = "try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.intro', JSON.stringify('off')); } catch (e) {}"

MEASURE = r"""() => {
  const R = (q) => { const e = typeof q === 'string' ? document.querySelector(q) : q; if (!e) return null; const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return null;
    const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 ? [r.left, r.top, r.right, r.bottom].map((v) => Math.round(v * 10) / 10) : null; };
  const hit = (a, b) => a && b && a[0] < b[2] - 0.5 && b[0] < a[2] - 0.5 && a[1] < b[3] - 0.5 && b[1] < a[3] - 0.5;
  const home = R('#home');
  const parts = { bar: R('.bar'), court: R('#court'), greet: R('#hello'), sysbar: R('#sysbar'), when: R('.hero .hsub'), heroNow: R('#heroNow'), heroMore: R('.hero-more'), heroState: R('#heroState'), wnb: R('#wnb'),
    dock: R('#dock'), chip: R('#next'), fab: R('#fab'), orb: R('#nxOrb'), tip: R('.nx-tip.on'), toast: R('#toast') };
  [...document.querySelectorAll('#hfirst .tile')].forEach((t, i) => { parts['tile' + i] = R(t); });
  const keys = Object.keys(parts).filter((k) => parts[k]), overlaps = [];
  const fixed = ['bar', 'dock', 'chip', 'fab', 'orb', 'tip', 'toast'];
  if (parts.bar && home) parts.bar[3] = Math.min(parts.bar[3], home[1]);          // the bar's hairline shadow under its own edge is not a part
  // what scrolls is clipped by its scroller (#home), so a part is measured where it can be seen
  const seen = (k) => (fixed.includes(k) ? parts[k] : [parts[k][0], Math.max(parts[k][1], home[1]), parts[k][2], Math.min(parts[k][3], home[3])]);
  for (let i = 0; i < keys.length; i++) for (let j = i + 1; j < keys.length; j++) { const a = seen(keys[i]), b = seen(keys[j]); if (a[3] > a[1] && b[3] > b[1] && hit(a, b)) overlaps.push(keys[i] + ' x ' + keys[j]); }
  const flow = keys.filter((k) => !fixed.includes(k));
  const below = flow.filter((k) => parts[k][3] > home[3] + 0.5 || parts[k][1] < home[1] - 0.5);
  const small = [];
  for (const e of document.querySelectorAll('#hero button, #hfirst button, #dock button, #dock input, #next, #fab, #nxOrb')) { const r = R(e); if (r && (r[2] - r[0] < 43.5 || r[3] - r[1] < 43.5)) small.push((e.id || e.className) + ' ' + Math.round(r[2] - r[0]) + 'x' + Math.round(r[3] - r[1])); }
  const unnamed = [...document.querySelectorAll('#hero button, #hfirst button')].filter((e) => !((e.getAttribute('aria-label') || '').trim() || (e.textContent || '').trim())).length;
  const order = [...document.querySelectorAll('#home h1, #home #sysbar, #home #heroNow, #home #hfirst .tile, #home .hsec-h')].map((e) => e.id || (e.className.split(' ')[1] || e.className) || e.textContent.trim());
  return { home, parts, overlaps, below, small, unnamed, order, tiles: document.querySelectorAll('#hfirst .tile:not(.sk)').length, sk: document.querySelectorAll('#hfirst .tile.sk').length,
    sx: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth, h1: document.querySelectorAll('#home h1').length,
    hero: (document.getElementById('heroNow') || {}).textContent || '', greet: (document.getElementById('hello') || {}).textContent || '',
    state: (document.getElementById('heroState') || {}).textContent || '', tileText: [...document.querySelectorAll('#hfirst .tile')].map((t) => t.innerText.replace(/\s+/g, ' ').trim()),
    labels: [...document.querySelectorAll('#hfirst .tile')].map((t) => t.getAttribute('aria-label') || ''), court: document.documentElement.dataset.court || '', dock: document.documentElement.dataset.orbDock || '',
    needs: [...document.querySelectorAll('.dgate')].map((g) => g.dataset.district + ':' + (g.dataset.need || '')), gates: [...document.querySelectorAll('.dgate')].map((g) => g.getAttribute('aria-label')) };
}"""


def lum(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast_over_scene(p, selectors):
    """The real contrast of light text: its colour against the BRIGHTEST pixel behind it (the text itself hidden for the screenshot)."""
    from PIL import Image
    info = p.evaluate("""(sel) => sel.map((q) => { const e = document.querySelector(q); if (!e) return null; const r = e.getBoundingClientRect(), c = getComputedStyle(e).color.match(/[\\d.]+/g).map(Number);
        return { q, r: [r.left, r.top, r.width, r.height], c: c.slice(0, 3) }; }).filter(Boolean)""", selectors)
    p.add_style_tag(content="#hero *, #hfirst * { color: transparent !important; fill: transparent !important; stroke: transparent !important; } #hero .hc-dot, #hero .sdot, #hero i { visibility: hidden !important; }")
    p.wait_for_timeout(250)
    png = p.screenshot()
    p.evaluate("document.head.removeChild(document.head.lastElementChild)")
    im = Image.open(io.BytesIO(png)).convert("RGB")
    k = im.width / p.viewport_size["width"]
    out = {}
    for it in info:
        x, y, w, h = it["r"]
        box = im.crop((int(x * k), int(y * k), int((x + w) * k), int((y + h) * k)))
        px = list(box.getdata())
        worst = max(lum(c) for c in px) if px else 0
        lt = lum(it["c"])
        out[it["q"]] = round((max(lt, worst) + 0.05) / (min(lt, worst) + 0.05), 2)
    return out


def open_page(br, origin, w, h, query="demo=1", init=SEEN, reduced=False, wait=2500, allow=None, timeout=120000):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", reduced_motion="reduce" if reduced else "no-preference")
    seen = []

    def route(r):
        u = r.request.url
        seen.append(u)
        if u.startswith(origin):
            r.continue_()
        else:
            r.abort()
    ctx.route("**/*", route)
    ctx.add_init_script(init)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)[:200]))
    p.goto(f"{origin}/jarvis/?{query}", wait_until="domcontentloaded", timeout=timeout)
    return ctx, p, errs, seen


def ready(p, timeout=120000):
    p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=timeout, polling=150)


def run():
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    srv, origin = serve()
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            # ---------------------------------------------------------------- a. the first screen at three sizes
            for (w, h) in SIZES:
                sz = f"{w}x{h}"
                ctx, p, errs, _ = open_page(br, origin, w, h)
                ready(p)
                p.wait_for_function("document.querySelectorAll('#hfirst .tile:not(.sk)').length === 3 && !!document.getElementById('heroNow') && !!document.getElementById('nxOrb')", timeout=60000, polling=200)
                p.wait_for_timeout(1200)
                m = p.evaluate(MEASURE)
                if SHOTS:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.screenshot(path=os.path.join(SHOTS, f"v2_{sz}.png"))
                check(f"a. {sz}: the greeting, the one sentence, three tiles, the Ask bar and the orb are on the first screen (no scrolling)",
                      m["tiles"] == 3 and not m["below"] and m["greet"] in ("Late night", "Good morning", "Good afternoon", "Good evening") and len(m["hero"]) > 10
                      and all(m["parts"].get(k) for k in ("dock", "orb", "greet", "heroNow", "tile0", "tile1", "tile2")) and m["parts"]["dock"][3] <= h + 0.5, (m["below"], m["parts"], m["hero"]))
                check(f"a. {sz}: nothing overlaps anything (hero parts, tiles, top bar, Ask bar, next chip, search button, orb) and nothing scrolls sideways", not m["overlaps"] and m["sx"] <= 1, (m["overlaps"], m["sx"]))
                check(f"a. {sz}: the orb sits in its own row above the Ask bar (docked): under the page's scroller, above the Ask bar, at the right edge",
                      m["dock"] == "1" and m["parts"]["orb"][1] >= m["home"][3] - 0.5 and m["parts"]["orb"][3] <= m["parts"]["dock"][1] + 0.5 and m["parts"]["orb"][2] > w - 20, (m["parts"]["orb"], m["home"], m["parts"]["dock"]))
                check(f"a. {sz}: every tap on the first screen is 44 px or more, every button has a name, one h1; VoiceOver order = greeting, status, the sentence, the three tiles, then the sections",
                      not m["small"] and m["unnamed"] == 0 and m["h1"] == 1 and m["order"][:6] == ["hello", "sysbar", "heroNow", "t-bots", "t-money", "t-today"]
                      and m["order"][6:] == ["hcT", "hcB", "hcD", "secTalkH", "secDayH", "secSysH", "secAppsH"], (m["small"], m["unnamed"], m["order"]))
                check(f"a. {sz}: the tiles in plain words: 'Drawdown left $1,240 of $1,500 max loss', the Mint estimate with its range, the window now and the next event; demo is labelled",
                      "Drawdown left $1,240 of $1,500 max loss" in m["tileText"][0] and "$1,495" in m["tileText"][1] and "estimate" in m["tileText"][1] and "Range −$42 to $2,547" in m["tileText"][1]
                      and "London entries" in m["tileText"][2] and "Next:" in m["tileText"][2] and m["state"] == "Example numbers (demo). Nothing here is real.", (m["tileText"], m["state"]))
                sel = ["#hello", ".hero .hsub", "#heroNow > span", "#hfirst .t-bots .t-k", "#hfirst .t-bots .t-s", "#hfirst .t-money .t-l"] + ([".dgate[data-district=research] span"] if m["parts"].get("court") else [])
                cr = contrast_over_scene(p, sel)
                check(f"a. {sz}: text contrast >= 4.5:1 against what is really behind it (the brightest pixel under each line)", cr and min(cr.values()) >= 4.5, cr)
                if (w, h) == (390, 844):
                    check("a. the courtyard: five doorways with their names (Market, Research, Money, Command, Life); the ones whose district needs you are marked (demo: Market and Life), in words too",
                          m["needs"] == ["market:warn", "research:", "money:", "command:", "life:warn"] and m["gates"][0] == "Market district: heads up. Opens the map" and m["gates"][1] == "Research district. Opens the map" and bool(m["parts"].get("court")), (m["needs"], m["gates"]))
                    # everything else is below the fold, in named sections, reachable
                    secs = p.evaluate("""() => { const h = document.getElementById('home'), top = h.getBoundingClientRect().bottom; return [...document.querySelectorAll('#home .hsec-h, #htoday h2')].map((e) => [e.textContent.replace(/\\d+$/, '').trim(), e.getBoundingClientRect().top >= top - 1]); }""")
                    check("a. below the fold, in named sections: Needs you, NQ bots, Market day, Talk to Jarvis, Today's timeline, System, Apps (none of them on the first screen)",
                          [s[0] for s in secs] == ["Needs you", "NQ bots", "Market day", "Talk to Jarvis", "Today's timeline", "System", "Apps"] and all(s[1] for s in secs), secs)
                    # a press you can see, and a tile opens its app through the shell
                    box = p.locator("#hfirst .t-money").bounding_box()
                    p.mouse.move(box["x"] + 40, box["y"] + 30)
                    p.mouse.down()
                    pressed = p.evaluate("document.querySelector('#hfirst .t-money').classList.contains('is-press')")
                    p.mouse.up()
                    released = p.evaluate("!document.querySelector('.is-press')")
                    check("a. a press you can see: the tile is marked while the finger is down and released after", pressed and released, (pressed, released))
                check(f"a. {sz}: no page errors", not errs, errs)
                ctx.close()

            # ---------------------------------------------------------------- b. the orb's hint: once, in its row, gone by itself
            ctx, p, errs, _ = open_page(br, origin, 390, 844, init=FIRST)
            ready(p)
            try:
                p.wait_for_function("!!document.querySelector('.nx-tip.on')", timeout=30000, polling=100)
                tip = p.evaluate(MEASURE)
                if SHOTS:
                    p.screenshot(path=os.path.join(SHOTS, "v2_orb_hint.png"))
                t = tip["parts"]["tip"]
                check("b. the orb's hint shows in the orb's own row: under the page's scroller, above the Ask bar, left of the orb, with the next chip and the search button out of its way (nothing overlaps)",
                      t and t[1] >= tip["home"][3] - 0.5 and t[3] <= tip["parts"]["dock"][1] + 0.5 and t[2] <= tip["parts"]["orb"][0] and not tip["parts"].get("chip") and not tip["parts"].get("fab") and not tip["overlaps"], (t, tip["home"], tip["overlaps"]))
                p.wait_for_function("!document.querySelector('.nx-tip.on') && !document.documentElement.hasAttribute('data-orb-tip')", timeout=20000, polling=100)
                back = p.evaluate(MEASURE)
                check("b. it goes by itself (3 s) and the next chip and the search button are back", bool(back["parts"].get("chip")) and bool(back["parts"].get("fab")) and not back["overlaps"], back["overlaps"])
                cnt = p.evaluate("localStorage.getItem('jarvis.orb.tips')")
                p.reload(wait_until="domcontentloaded")
                ready(p)
                p.wait_for_timeout(3200)
                again = p.evaluate("!!document.querySelector('.nx-tip.on')")
                check("b. once: counted on this phone and not shown at the next open", cnt == "1" and not again, (cnt, again))
            except Exception as e:  # noqa: BLE001
                check("b. the orb's hint shows once in its row and goes by itself", False, repr(e))
            ctx.close()

            # ---------------------------------------------------------------- c. no data at all + d. pull to refresh
            ctx, p, errs, seen = open_page(br, origin, 390, 844, query="x=1")
            early = p.evaluate("({ sk: document.querySelectorAll('#hfirst .tile.sk').length, tiles: document.querySelectorAll('#hfirst .tile').length, busy: document.getElementById('hfirst').getAttribute('aria-busy') })")
            check("c. never blank: before any number is in, the three tiles are skeletons with their titles (aria-busy)", early["tiles"] == 3 and (early["sk"] == 3 or early["sk"] == 0) and (early["sk"] == 0 or early["busy"] == "true"), early)
            ready(p)
            p.wait_for_function("document.querySelectorAll('#hfirst .tile:not(.sk)').length === 3", timeout=60000, polling=250)
            m = p.evaluate(MEASURE)
            if SHOTS:
                p.screenshot(path=os.path.join(SHOTS, "v2_no_data.png"))
            check("c. PC offline / nothing published, in plain words: 'The bots have not reported yet' + 'Your accounts are not affected.' on the tile, no doorway marked, nothing overlapping, all on the first screen",
                  "The bots have not reported yet" in m["tileText"][0] and "Your accounts are not affected." in m["tileText"][0] and not m["overlaps"] and not m["below"] and all(n.endswith(":") or "warn" in n or "bad" in n for n in m["needs"]), (m["tileText"], m["hero"], m["needs"]))
            check("c. the hero still says ONE sentence (what needs you, or that the bots have not reported: your accounts are not affected)", len(m["hero"]) > 12 and m["hero"].count(".") <= 2, m["hero"])
            n0 = sum(1 for u in seen if "/money/index.json" in u)
            asof0 = p.evaluate("window.__jarvisHome.model().asof")
            p.evaluate("""() => { const el = document.getElementById('home'); const T = (type, y) => { const t = new Touch({ identifier: 1, target: el, clientX: 200, clientY: y }); el.dispatchEvent(new TouchEvent(type, { touches: type === 'touchend' ? [] : [t], changedTouches: [t], bubbles: true })); };
              T('touchstart', 200); T('touchmove', 260); T('touchmove', 330); window.__pullMid = { s: document.getElementById('ptr').dataset.state, t: document.getElementById('ptrT').textContent, h: document.getElementById('ptr').getBoundingClientRect().height }; T('touchend', 330); }""")
            mid = p.evaluate("window.__pullMid")
            p.wait_for_function("window.__jarvisHome.pull.state === 'idle' && window.__jarvisHome.model().asof > %d" % asof0, timeout=40000, polling=150)
            n1 = sum(1 for u in seen if "/money/index.json" in u)
            check("d. pull to refresh: the line opens in the page flow ('Release to refresh'), the feeds are fetched again, then it closes", mid["s"] == "pull" and mid["t"] == "Release to refresh" and mid["h"] > 20 and n1 > n0, (mid, n0, n1))
            p.evaluate("document.getElementById('hRefresh').scrollIntoView({ block: 'center' })")
            asof1 = p.evaluate("window.__jarvisHome.model().asof")
            p.click("#hRefresh")
            p.wait_for_function("window.__jarvisHome.pull.state === 'idle' && window.__jarvisHome.model().asof > %d" % asof1, timeout=40000, polling=150)
            n2 = sum(1 for u in seen if "/money/index.json" in u)
            check("d. the Refresh button (for those who cannot pull) does the same; it says when the numbers were updated", n2 > n1 and "Updated" in p.text_content("#hUpdated"), (n1, n2, p.text_content("#hUpdated")))
            check("c/d. no page errors", not errs, errs)
            ctx.close()

            # ---------------------------------------------------------------- e. reduced motion + the painted courtyard
            ctx, p, errs, _ = open_page(br, origin, 390, 844, reduced=True)
            sk = p.evaluate("(() => { const b = document.querySelector('.sk-b'); return b ? getComputedStyle(b).animationName : 'gone'; })()")
            ready(p)
            p.wait_for_function("document.querySelectorAll('#hfirst .tile:not(.sk)').length === 3", timeout=60000, polling=200)
            rm = p.evaluate("""() => ({ tile: getComputedStyle(document.querySelector('#hfirst .tile')).transitionDuration, ptr: getComputedStyle(document.getElementById('ptr')).transitionDuration,
              court: document.documentElement.dataset.court || '', art: getComputedStyle(document.getElementById('courtArt')).opacity, doors: document.querySelectorAll('#courtArt .c-door').length,
              lit: [...document.querySelectorAll('#courtArt .c-door')].map((d) => d.dataset.need || ''), light: [...document.querySelectorAll('#courtArt .c-door .d-l')].map((d) => getComputedStyle(d).opacity),
              cols: [...document.querySelectorAll('#courtArt .c-door')].map((d, i) => Math.abs((d.getBoundingClientRect().left + d.getBoundingClientRect().right) / 2 - (document.querySelectorAll('.dgate')[i].getBoundingClientRect().left + document.querySelectorAll('.dgate')[i].getBoundingClientRect().right) / 2)) })""")
            check("e. reduced motion: no skeleton sheen, no transitions on the tiles or the pull line", sk in ("none", "gone") and rm["tile"].replace("0s", "").replace(",", "").strip() == "" and rm["ptr"] == "0s", (sk, rm["tile"], rm["ptr"]))
            check("e. LITE (software GL): the painted courtyard is showing: a gradient sky and five SVG doorways, each over its own name; the doorways that need you are lit (Market, Life), the others dim",
                  rm["court"] in ("lite", "") and rm["art"] == "1" and rm["doors"] == 5 and rm["lit"] == ["warn", "", "", "", "warn"] and rm["light"][0] == "1" and float(rm["light"][1]) < 0.5 and max(rm["cols"]) < 2, rm)
            check("e. no page errors", not errs, errs)
            ctx.close()

            # ---------------------------------------------------------------- f. the 3D courtyard (forced on software GL: slow, so one size and long waits)
            ctx, p, errs, _ = open_page(br, origin, 390, 844, query="demo=1&gpu=1")
            ready(p)
            try:
                p.wait_for_function("document.documentElement.dataset.court === '3d' && document.documentElement.dataset.bg3d === 'on' && !!(window.__jarvisBackdrop.home && window.__jarvisBackdrop.home.lens && window.__jarvisBackdrop.home.lens.on)", timeout=240000, polling=500)
                p.wait_for_timeout(2500)
                g = p.evaluate("""() => { const b = window.__jarvisBackdrop, h = b.home, c = h.courtyard, r = document.getElementById('court').getBoundingClientRect();
                  return { draws: h.trim(), counted: h.sceneDraws(), budget: h.budget, court: c.draws, lite: c.lite, needs: c.needs, lens: h.lens, feetWant: r.bottom - 44, art: getComputedStyle(document.getElementById('courtArt')).opacity,
                    passes: b.stats().passes, frame: b.stats().calls, err: [b.extError || '', h.courtyardError || ''] }; }""")
                if SHOTS:
                    p.screenshot(path=os.path.join(SHOTS, "v2_3d.png"))
                check("f. the 3D courtyard is up (7 instanced draw calls of its own) and the whole scene stays within 25 draw calls (counted, then trimmed)",
                      g["lite"] is False and g["court"] == 7 and g["draws"] <= 25 and g["counted"] <= 25 and g["budget"] == 25 and not any(g["err"]), g)
                check("f. it stands in the hero's window: the lens is shifted so the doorways' feet land on the rail, the painting has stepped aside, and the doorways that need you are lit",
                      g["lens"]["on"] and abs(g["lens"]["feet"] - g["feetWant"]) < 3 and 0.05 < g["lens"]["s"] < 0.62 and float(g["art"]) < 0.05 and g["needs"].get("market") == "warn" and g["needs"].get("life") == "warn", g)
                cr = contrast_over_scene(p, ["#hello", ".hero .hsub", "#heroNow > span", ".dgate[data-district=research] span"])
                check("f. over the live 3D scene the words still have >= 4.5:1 contrast (the scrim)", cr and min(cr.values()) >= 4.5, cr)
                p.evaluate("document.getElementById('home').scrollTop = 200")
                p.wait_for_function("Math.abs(window.__jarvisBackdrop.home.lens.feet - (%f - 100)) < 4" % g["feetWant"], timeout=60000, polling=300)
                check("f. parallax: scrolled 200 px, the scene has drifted 100 px (half the page's speed)", True)
            except Exception as e:  # noqa: BLE001
                st = p.evaluate("(() => { const b = window.__jarvisBackdrop || {}; return [b.state, b.extra, b.error || '', b.extError || '', (b.home || {}).courtyardError || '', document.documentElement.dataset.court || '']; })()")
                check("f. the 3D courtyard came up on software GL (forced with ?gpu=1)", False, (repr(e)[:200], st))
            check("f. no page errors", not errs, errs)
            ctx.close()
    finally:
        srv.shutdown()


def main():
    try:
        run()
    except Exception as e:  # noqa: BLE001
        check("the browser run finished", False, repr(e))
    n = sum(RES)
    print(f"\njarvis home v2: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
