"""Zenith shell (2026-11-03 day, owner: "make everything way higher quality, 3D UI effects", "more organized ... like a maid
swept", "higher quality / futuristic"): zenithcore.js (window.ZenithFX, byte-identical on both apps), the phone glue zenith.js
+ zenith.css, the PC skins through the one token writer. Read-only UI.

  a. static   zenithcore.js byte-identical on both apps; the phone loads zenith.css after polish.css and zenithcore.js then
              zenith.js after pro.js (before embed.js); caches bumped (phone le-public-v52+, OTHER_APPS kept; PC
              le-shell-next-v32+ precaches the core, index.html loads it before app.js); skins.js writes tokens through
              ZenithFX.applyTokens; no fetch / POST / arm / route in the new files
  b. node     ZenithFX in a stub DOM: number parse / format (+$, −$, R, %), applyTokens (accent -> its rgb + glow, null clears),
              Olympus themes (an id, an object of colours, JSON in the stored key, an unknown id = back to Zenith's own look),
              the jfx quality (missing = high, low = lite, off = still), View Transitions only when moving
  c. phone    Playwright 390x844 on a copy of tools/web_public: the breadcrumb (Zlarior › Results over "Performance"), a page
              hero that only repeated the title loses the copy, Home's money panel (today / this month / eval $) with the
              ribbon canvas inside the greeting (the older Home order kept), no sideways scroll during a page change with
              3D on (the View Transition; the old slide pushed the page 28 px wider), 44 px hit areas on the bot sections and
              chips, the glint on a pressed card, Settings > 3D effects > 3D quality writes jfx (shared with Jarvis), an
              Olympus theme in localStorage recolours the accent, no page errors

  python -X utf8 -m tests.test_zenith_shell [--shots <dir>]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


OTHER_APPS = ["jarvis/", "planner/", "kalshi/", "datacity/", "mind/", "tree/", "oracle/", "odeon/", "fates/", "hermes/", "prometheus/", "tyche/", "olympus/"]


def part_a():
    core = rd("tools", "web_public", "zenithcore.js")
    check("a. zenithcore.js byte-identical on both apps", core == rd("web_next", "js", "next", "zenithcore.js"))
    idx, sw = rd("tools", "web_public", "index.html"), rd("tools", "web_public", "sw.js")
    head = idx[:idx.find("</head>")]
    check("a. phone: zenith.css in the head after polish.css", 0 < head.find("polish.css?v=") < head.find("zenith.css?v="))
    o = [idx.find(f'src="{n}?v=') for n in ("pro.js", "zenithcore.js", "zenith.js", "embed.js")]
    check("a. phone: zenithcore.js then zenith.js after pro.js, before embed.js", all(i > 0 for i in o) and o == sorted(o), o)
    m = re.search(r"const OTHER_APPS = \[([^\]]*)\]", sw)
    kept = m and all(f"'{d}'" in m.group(1) for d in OTHER_APPS)
    check("a. phone worker le-public-v52+, OTHER_APPS kept (every app folder)", int(re.search(r"le-public-v(\d+)", sw).group(1)) >= 52 and kept, m and m.group(1))
    pidx, psw, sk = rd("web_next", "index.html"), rd("web_next", "sw.js"), rd("web_next", "js", "skins.js")
    check("a. PC: index.html loads zenithcore.js (classic) before app.js; le-shell-next-v32+ precaches it",
          0 < pidx.find("/js/next/zenithcore.js?v=") < pidx.find("/js/app.js") and int(re.search(r"le-shell-next-v(\d+)", psw).group(1)) >= 32
          and "/js/next/zenithcore.js?v=" in psw)
    check("a. PC skins.js writes its accent through ZenithFX.applyTokens and uses its glass", "Z.applyTokens(tok)" in sk and "Z.glass(document.body" in sk)
    for n in ("zenithcore.js", "zenith.js", "zenith.css"):
        src = rd("tools", "web_public", n)
        check(f"a. {n} is read-only (no fetch, no POST, no /api/, no arm)", "fetch(" not in src and "POST" not in src and "/api/" not in src and "arm_" not in src)


NODE = r"""
const path = process.argv[2];
const props = {}, ds = {}, cls = new Set();
const style = { setProperty: (k, v) => { props[k] = v; }, removeProperty: (k) => { delete props[k]; } };
const R = { dataset: ds, style, classList: { toggle: (c, on) => { if (on) cls.add(c); else cls.delete(c); } } };
let LS = {}, mqReduced = false;
global.window = global; global.document = { documentElement: R, addEventListener() {}, getElementById() { return null; }, createElement() { return { id: '', textContent: '' }; }, head: { appendChild() {} } };
global.addEventListener = () => {}; global.dispatchEvent = () => {}; global.CustomEvent = function (n, o) { this.detail = o && o.detail; };
global.matchMedia = (q) => ({ matches: /reduce/.test(q) ? mqReduced : false, addEventListener() {} });
global.localStorage = { getItem: (k) => (k in LS ? LS[k] : null), setItem: (k, v) => { LS[k] = String(v); } };
require(path);
const Z = window.ZenithFX, out = {};
out.parse = ['+$3,289', '−$289', '$1,500', '-1.01R', '12.5R', '0%', 'Room $1'].map((t) => { const p = Z.parse(t); return p ? p.v : null; });
out.q0 = Z.quality(); LS.jfx = 'low'; out.q1 = [Z.quality(), Z.lite(), Z.still()]; LS.jfx = 'off'; out.q2 = [Z.quality(), Z.still()];
LS.jfx = 'ultra'; out.q3 = [Z.quality(), Z.lite(), Z.still()]; mqReduced = true; out.q4 = [Z.still(), Z.canVT()]; mqReduced = false;
Z.applyTokens({ accent: '#e9b44c' }); out.t1 = { a: props['--accent'], rgb: props['--zn-accent-rgb'], glow: props['--glow'] };
Z.applyTokens({ accent: null }); out.t2 = { a: props['--accent'] || null, rgb: props['--zn-accent-rgb'] || null };
Z.olympus('gold'); out.o1 = props['--accent'];
Z.olympus({ id: 'custom', colors: { primary: '#123456', text: '#fafafa', bg: '#010203' } }); out.o2 = [props['--accent'], props['--ink'], props['--page']];
Z.olympus(JSON.stringify({ id: 'aurora' })); out.o3 = props['--accent'];
Z.olympus('no-such-theme'); out.o4 = [props['--accent'] || null, props['--ink'] || null, ds.olyTheme];
Z.use3d(() => false); out.m = [Z.moving(), Z.canVT()]; Z.use3d(null);
console.log(JSON.stringify(out));
"""


def part_b(tmp):
    js = os.path.join(tmp, "zn_node.js")
    open(js, "w").write(NODE)
    p = subprocess.run(["node", js, os.path.join(ROOT, "tools", "web_public", "zenithcore.js")], capture_output=True, text=True, timeout=60)
    if p.returncode:
        check("b. node runs ZenithFX", False, p.stderr[:1500])
        return
    O = json.loads(p.stdout.strip().splitlines()[-1])
    check("b. numbers: +$3,289 / −$289 / $1,500 / -1.01R / 12.5R / 0% parse; a sentence does not", O["parse"] == [3289, -289, 1500, -1.01, 12.5, 0, None], O["parse"])
    check("b. jfx: missing = high, low = lite, off = still, ultra = full; reduced motion = still, no View Transition",
          O["q0"] == "high" and O["q1"] == ["low", True, False] and O["q2"] == ["off", True] and O["q3"] == ["ultra", False, False] and O["q4"] == [True, False], O)
    check("b. applyTokens: the accent, its rgb triple and its glow; null clears them", O["t1"] == {"a": "#e9b44c", "rgb": "233,180,76", "glow": "rgba(233,180,76,.35)"}
          and O["t2"] == {"a": None, "rgb": None}, (O["t1"], O["t2"]))
    check("b. Olympus themes: an id, an object of colours, JSON in the stored key; an unknown id = Zenith's own look again",
          O["o1"] == "#e9b44c" and O["o2"] == ["#123456", "#fafafa", "#010203"] and O["o3"] == "#2fd3c0" and O["o4"] == [None, None, "no-such-theme"], O)
    check("b. the app's 3D switch off: nothing moves, no View Transition", O["m"] == [False, False], O["m"])


def part_c(tmp, shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    from tests import test_blitz_tab as TB
    F = TB.build()
    for k, sc in (("lit", 1.0), ("atlas", 0.4)):            # a few real days on the accounts: the ribbon has a curve
        if isinstance(F["board"].get(k), dict):
            F["board"][k]["days"] = [[f"2026-09-{d:02d}", round(v * sc, 2)] for d, v in zip((1, 2, 3, 4, 8, 9, 10, 11), (420, -180, 610, -240, 380, 150, -320, 540))]
    s = TB.site(tmp, F)
    lvp = os.path.join(tmp, "liveview.json")
    json.dump(F["lv"], open(lvp, "w"), default=str)
    srv = TB.serve(s)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    sh = (lambda pg, n: pg.screenshot(path=os.path.join(shots, n))) if shots else (lambda *a: None)
    with sync_playwright() as p:
        br = TB.launch(p)
        errs = []
        ctx, pg = TB.phone_ctx(br, F, lvp, "off", errs)
        ctx.add_init_script("try { localStorage.setItem('olympus.theme', 'aurora'); localStorage.removeItem('jfx'); } catch (e) {}")
        pg.goto(base + "#/today")
        pg.wait_for_selector(".pl-home .su-accts", timeout=30000)
        pg.wait_for_selector(".pl-hi .zn-hi .zn-money", timeout=15000)
        pg.wait_for_timeout(1200)
        if pg.query_selector("#moInstX"):
            pg.click("#moInstX")
        H = pg.evaluate("""() => { const h = document.querySelector('#page > .pl-home'), z = h.querySelector('.pl-hi .zn-hi');
          return { kids: [...h.children].map(c => c.className.split(' ')[0]).slice(0, 4), money: [...z.querySelectorAll('.zn-m b')].map(b => b.textContent),
            labels: [...z.querySelectorAll('.zn-m em')].map(e => e.textContent), cv: !!z.querySelector('.zn-rib canvas'), h: Math.round(z.getBoundingClientRect().height),
            accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(), a8: getComputedStyle(document.documentElement).getPropertyValue('--oly-th-a8').trim() }; }""")
        check("c. Home: money first in the greeting: Today · This month · Eval P&L in $, the ribbon canvas; the Home order kept",
              H["kids"] == ["pl-hi", "su-bar", "su-accts", "pl-now"] and H["labels"] == ["Today", "This month", "Eval P&L"] and all("$" in m for m in H["money"]) and H["cv"] and H["h"] < 160, H)
        pg.wait_for_selector(".pl-hi > #mnCard", timeout=15000)
        MN = pg.evaluate("""() => { const hi = document.querySelector('#page > .pl-home > .pl-hi'), c = hi.querySelector(':scope > #mnCard');
          const exp = Math.max(2, window.MissionUI.accounts(window.POLISH.model()).filter((a) => a && !a.placeholder).length);
          return { order: [...hi.children].map((e) => e.id || e.className.split(' ')[0] || e.tagName.toLowerCase()), rows: c.querySelectorAll('.mn-row').length, exp,
            txt: c.innerText.replace(/\\s+/g, ' '), taps: [...c.querySelectorAll('.mn-row')].map((r) => Math.round(r.getBoundingClientRect().height)), top: Math.round(c.getBoundingClientRect().top),
            x: document.documentElement.scrollWidth - innerWidth }; }""")
        i_m = MN["order"].index("mnCard")
        check(f"c. Zenith Home: 'Money now' is the first card, inside the greeting box ahead of the Today hero and the money ribbon ({MN['rows']} account rows = the accounts the board has)",
              i_m == 2 and all(MN["order"].index(k) > i_m for k in ("zn-hi",) if k in MN["order"]) and ("zh-hero" not in MN["order"] or MN["order"].index("zh-hero") > i_m) and MN["rows"] == MN["exp"] and MN["x"] <= 0, MN)
        check("c. Zenith Home: each row reads 'Drawdown left $X of $max loss' (not days), today's $, what the bot waits for and its status; every row is a 44 px tap",
              MN["txt"].count("Drawdown left") == MN["rows"] and MN["txt"].count("max loss") >= MN["rows"] and "10 days" not in MN["txt"] and "next" in MN["txt"].lower() and "Bot " in MN["txt"]
              and all(h >= 44 for h in MN["taps"]) and "NaN" not in MN["txt"] and "undefined" not in MN["txt"], MN)
        # 2026-11-14 (team T2): 'aurora' is now the OLYMPUS look Glass Aurora, painted by olympus/themes.js through its slots; the old kit's
        # token set of the same name (#2fd3c0) no longer covers it (the node part still checks the old kit's mapping where no engine runs)
        check("c. an OLYMPUS look in localStorage ('aurora' = Glass Aurora) recolours Zenith's accent: the look's own accent slot, not the old kit's",
              H["a8"].startswith("#") and H["accent"].lower() == H["a8"].lower() and H["accent"].lower() != "#2fd3c0", (H["accent"], H["a8"]))
        sh(pg, "zenith_home.png")
        # the breadcrumb + the hero that repeated the title
        pg.evaluate("() => { location.hash = '#/perf'; }")
        pg.wait_for_timeout(1300)
        B = pg.evaluate("""() => ({ crumb: [...document.querySelectorAll('#crumb span')].map(s => s.textContent), title: document.getElementById('title').textContent,
          dup: !!document.querySelector('#page > .hero.zn-hdup'), h2: (() => { const h = document.querySelector('#page > .hero h2'); return h ? getComputedStyle(h).display : 'none'; })() })""")
        check("c. where am I: 'Zlarior › Results' over 'Performance'; the page's own copy of the title is hidden", B["crumb"] == ["Zlarior", "Results"] and B["title"] == "Performance"
              and (not B["dup"] or B["h2"] == "none"), B)
        sh(pg, "zenith_breadcrumb.png")
        W = {}
        for h in ("#/lit", "#/holo"):
            pg.evaluate(f"() => {{ location.hash = '{h}'; }}")
            pg.wait_for_timeout(1300)
            W[h] = pg.evaluate("() => ({ crumb: [...document.querySelectorAll('#crumb span')].map(s => s.textContent), title: document.getElementById('title').textContent, tab: (document.querySelector('#tabs a.on') || {}).dataset?.t || null })")
        check("c. where am I: Zlarior's main page reads 'Zlarior › Today' over 'Overview' (not the bot's name twice); the Holodeck sits under Home with Home lit",
              W["#/lit"] == {"crumb": ["Zlarior", "Today"], "title": "Overview", "tab": "lit"} and W["#/holo"]["crumb"] == ["Home"] and W["#/holo"]["tab"] == "today", W)
        pg.evaluate("() => { location.hash = '#/perf'; }")
        pg.wait_for_timeout(900)
        # 44 px hit areas on the bot sections and chips
        T = pg.evaluate("""() => [...document.querySelectorAll('#sub .zl-seg button, #sub .zl-chips button')].map(b => { const r = b.getBoundingClientRect(), a = getComputedStyle(b, '::after');
          const hh = a.content !== 'none' ? Math.max(r.height, parseFloat(a.height) || 0) : r.height, ww = a.content !== 'none' ? Math.max(r.width, parseFloat(a.width) || 0) : r.width; return [Math.round(ww), Math.round(hh)]; })""")
        check("c. 44 px taps: every section button and chip on a bot tab has a 44 px hit area", T and all(w >= 44 and h >= 44 for w, h in T), T)
        # page changes with the 3D look on (the app's 3D switch on without loading the WebGL sky here): no sideways scroll at any
        # moment, sampled every frame through the changes
        WALK = """(noVT) => new Promise((res) => { ZenithFX.use3d(() => true); if (noVT) document.startViewTransition = undefined; const seen = []; let n = 0;
          const H = ['#/atlas', '#/blitz', '#/real', '#/system', '#/lit', '#/today'];
          let i = 0; const go = () => { if (i < H.length) { location.hash = H[i++]; setTimeout(go, 450); } };
          const f = () => { seen.push(document.documentElement.scrollWidth - innerWidth); if (n++ < 200) requestAnimationFrame(f); else res({ max: Math.max(...seen), vt: document.documentElement.classList.contains('zn-vt') }); };
          go(); requestAnimationFrame(f); })"""
        X = pg.evaluate(WALK, False)
        pg.wait_for_timeout(600)
        X2 = pg.evaluate(WALK, True)           # an older Safari: no View Transitions, the CSS slide instead
        check("c. no sideways scroll during page changes, with View Transitions and with the CSS slide (it made the page 28 px wider)",
              X["max"] <= 0 and X["vt"] and X2["max"] <= 0 and not X2["vt"], (X, X2))
        pg.wait_for_timeout(800)
        # the glint: press a card
        pg.evaluate("() => { location.hash = '#/today'; }")
        pg.wait_for_timeout(1200)
        box = pg.query_selector(".pl-home .su-acct")
        g = None
        if box:
            bb = box.bounding_box()
            pg.mouse.move(bb["x"] + bb["width"] * 0.7, bb["y"] + 20)
            pg.dispatch_event(".pl-home .su-acct", "pointerdown", {"pointerType": "touch", "clientX": bb["x"] + bb["width"] * 0.7, "clientY": bb["y"] + 20, "bubbles": True})
            g = pg.evaluate("() => { const g = document.querySelector('.zn-glint'); return g ? { on: g.classList.contains('on'), w: Math.round(parseFloat(g.style.width) || 0), mx: g.style.getPropertyValue('--mx') } : null; }")
            pg.dispatch_event(".pl-home .su-acct", "pointercancel", {"bubbles": True})
        check("c. glass: pressing a card lights its edge where the finger is (one shared glint over the card)", g and g["on"] and g["w"] > 200 and g["mx"].endswith("%"), g)
        # Settings: the shared 3D quality inside the 3D effects card
        pg.evaluate("() => { location.hash = '#/settings'; }")
        pg.wait_for_selector("#znQ", timeout=10000)
        inside = pg.evaluate("() => !!document.querySelector('#znQ').closest('.card').querySelector('#sFx')")
        pg.click("#znQ button[data-v='low']")
        pg.wait_for_timeout(200)
        q = pg.evaluate("() => ({ k: localStorage.getItem('jfx'), zq: document.documentElement.dataset.zq })")
        check("c. Settings > 3D effects > 3D quality: one place for 3D; Low writes the shared key jfx (Jarvis + every OLYMPUS app)", inside and q == {"k": "low", "zq": "low"}, (inside, q))
        sh(pg, "zenith_settings.png")
        check("c. no page errors", not errs, errs[:4])
        ctx.close()
        br.close()


def main():
    shots = ""
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    part_a()
    tmp = tempfile.mkdtemp(prefix="le_zenith_shell_")
    try:
        part_b(tmp)
        part_c(tmp, shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nZenith shell: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
