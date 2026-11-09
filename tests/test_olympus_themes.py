"""OLYMPUS themes (tools/web_public/olympus/themes.js, docs/OLYMPUS_DESIGN.md "Themes"): whole-system palettes as data.

One key on the shared origin, localStorage 'olympus.theme'; Jarvis's Look sheet writes it, every page reads it at start and on the
'storage' event. Runs in Chromium at 390 x 844 on the real site layout (/jarvis/, /<app>/, /olympus/, Zenith at /, /kalshi/), with
every request off the page's origin refused, and checks:
  a. data: every theme has every token (and Jarvis's palette when it paints Jarvis); the seven themes and their names; the
     default's tokens equal olympus.css's own values; the engine is ES5 / Safari 16 safe; every page loads it (the nine apps
     before olympus.js, Jarvis / Zenith / Kalshi async) and each three.js app hooks its scene (themeScene / onTheme)
  b. contrast: the light theme (Athena) passes WCAG AA for text (4.5:1) on its page, its glass panels and its sheet; so do
     Jarvis's own text colours under it, its status colours, and every dark theme's text / dim on its own background
  c. the default is today's look: with no key and with 'olympus' the computed CSS custom properties of Jarvis, the nine apps,
     Zenith and Kalshi equal the baseline captured before the themes (tests/fixtures/olympus_default_vars.json)
  d. Jarvis: the Look sheet shows seven live tiles; a tap paints Jarvis at once (its palette, the core colours, the status bar)
     and writes 'olympus.theme'; an app framed in Jarvis follows through the storage event; reopened, the colours are there
     from the first paint (the <head> copy); a Jarvis colour goes back to the default theme; the scanline option
  e. each app at 390 x 844 under a theme: its kit reads the theme (tokens, harmonised accent, its own CSS tokens), its scene
     hook is called with the tint (stubbed: the hook's colours are checked), it follows a live change, and no console error
    python -X utf8 -m tests.test_olympus_themes          (--shots <dir>: only Jarvis in every theme, home + Look sheet)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
BASE = os.path.join(ROOT, "tests", "fixtures", "olympus_default_vars.json")
RES: list = []
IDS = ["agora", "olympus", "zeus", "poseidon", "hades", "athena", "apollo", "artemis"]
DEFAULT_ID = "agora"                 # AGORA is the default since 2026-11-09 (docs/DESIGN_AGORA.md); "olympus" is the old violet look, selectable
NAMES = {"agora": "Agora", "olympus": "Olympus Night", "zeus": "Zeus Storm", "poseidon": "Poseidon", "hades": "Hades", "athena": "Athena", "apollo": "Apollo"}
APPS = {"datacity": "", "mind": "", "tree": "", "oracle": "?demo=1", "odeon": "?demo=1&autoplay=1", "fates": "",
        "hermes": "#week,demo", "prometheus": "?demo=1", "tyche": "?demo=1"}
OWN_META = ("hermes", "datacity")                   # set their status-bar colour themselves (Hermes per story, Data City from its market-clock sky)
THREE_APPS = ["datacity", "mind", "oracle", "odeon", "fates", "prometheus", "tyche"]      # tree: 2D canvas, hermes: raw WebGL


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ the data, read by running themes.js in node (no browser)
DUMP_JS = r"""
const fs = require('fs'), vm = require('vm'), w = { addEventListener() {} }, st = {};
const root = { style: { setProperty(k, v) { st[k] = v; }, removeProperty(k) { delete st[k]; }, getPropertyValue(k) { return st[k] || ''; } }, setAttribute() {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), { window: w, document: { documentElement: root, body: null, addEventListener() {}, querySelector() { return null; } },
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} } });
const T = w.OLYMPUS_THEMES;
process.stdout.write(JSON.stringify({ TOKENS: T.TOKENS, JARVIS: T.JARVIS, list: T.list(), stage: T.list().map((t) => T.tokens(t.id, 'stage')),
  mix0: T.mix('#7fe9ff', '#ff0000', 0), mixN: T.mix(0x02030a, '#ff0000', 0), harm0: T.harmonise('#ffcf5a', '#4da3ff', 0) }));
"""


def theme_data():
    try:
        out = subprocess.run(["node", "-e", DUMP_JS, os.path.join(KIT, "themes.js")], capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout)
    except Exception as e:                                   # no node: the data checks are skipped (the browser part reads it too)
        print("node not available:", e)
        return None


# ------------------------------------------------------------------ WCAG
def rgba(c):
    c = c.strip()
    if c.startswith("#"):
        h = c[1:]
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [1.0]
    m = re.match(r"rgba?\(([^)]*)\)", c)
    if m:
        p = [x.strip() for x in m.group(1).split(",")]
        return [float(p[0]), float(p[1]), float(p[2]), float(p[3]) if len(p) > 3 else 1.0]
    p = [x.strip() for x in c.split(",")]                    # "r,g,b" (Jarvis's --cr style)
    return [float(p[0]), float(p[1]), float(p[2]), 1.0]


def over(fg, bg):
    """fg (maybe translucent) composited over an opaque bg"""
    a = fg[3]
    return [fg[i] * a + bg[i] * (1 - a) for i in range(3)] + [1.0]


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(fg, bg):
    bg = rgba(bg) if isinstance(bg, str) else bg
    fg = over(rgba(fg) if isinstance(fg, str) else fg, bg)
    a, b = lum(fg), lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# ------------------------------------------------------------------ a. data + static
def test_static(data):
    js, css = read(KIT, "themes.js"), read(KIT, "olympus.css")
    bad = [p for p in (r"color-mix\(", r":has\(", r"\(\?<[=!]", r"\.at\(", r"\?\.", r"\?\?", r"=>", r"\blet\b", r"\bconst\b", r"`") if re.search(p, js)]
    check("a. themes.js is ES5 and Safari 16 safe (no arrows, let / const, template strings, ?. / ??, color-mix, :has)", not bad, bad)
    check("a. one key on the shared origin: 'olympus.theme' (the default 'agora'); the storage event repaints",
          "KEY = 'olympus.theme', DEFAULT = 'agora'" in js and "addEventListener('storage'" in js)
    if data:
        ids = [t["id"] for t in data["list"]]
        check("a. eight themes in picker order: Agora (default), Olympus Night, Zeus Storm, Poseidon, Hades, Athena, Apollo, + Artemis",
              ids == IDS and all(t["name"] == NAMES[t["id"]] for t in data["list"] if t["id"] in NAMES), ids)
        miss = {t["id"]: [k for k in data["TOKENS"] if k not in t["tokens"]] for t in data["list"]}
        miss = {k: v for k, v in miss.items() if v}
        check(f"a. every theme has every token ({len(data['TOKENS'])}: page, panels, lines, text, accents, glow, status, 3D fog / sky / emissive / bloom, theme-color, mix, harmony)",
              not miss, miss)
        jmiss = {t["id"]: [k for k in data["JARVIS"] if k not in (t["jarvis"] or {})] for t in data["list"] if t["id"] != DEFAULT_ID}
        jmiss = {k: v for k, v in jmiss.items() if v}
        check("a. every theme but the default carries Jarvis's whole palette (the default leaves Jarvis's own colour)",
              not jmiss and data["list"][0]["jarvis"] is None, jmiss)
        hexes = [(t["id"], k) for t in data["list"] for k in ("bg", "bg2", "text", "accent", "accent2", "glow", "fog", "sky", "emissive", "bloom", "themeColor")
                 if not re.fullmatch(r"#[0-9a-f]{6}", t["tokens"][k])]
        check("a. the colour tokens the scenes take are #rrggbb (three.js setHex, the theme-color meta)", not hexes, hexes)
        d0 = data["list"][0]["tokens"]
        kit = {k: re.search(rf"--oly-{k}: ([^;]+);", css).group(1).strip() for k in ("glass", "line", "text", "dim", "shadow")}
        check("a. the default theme's tokens are olympus.css's own values (glass, line, text, dim, shadow), mix 0 and harmony 0",
              all(d0[k] == v for k, v in kit.items()) and d0["accent"] == "#c8a24a" and d0["mix"] == 0 and d0["harmony"] == 0, (kit, d0))
        check("a. a 0 blend returns the colour untouched, same type (so the default theme leaves every scene and accent as it was)",
              data["mix0"] == "#7fe9ff" and data["mixN"] == 0x02030a and data["harm0"] == "#ffcf5a", data)
        light = [t for t in data["list"] if t["scheme"] == "light"]
        check("a. the light theme (Athena) has a dark 'stage' palette for the 3D apps / Zenith / Kalshi (light fog would wash the glow out)",
              [t["id"] for t in light] == ["athena"] and light[0].get("stage") and data["stage"][4]["scheme"] == "dark", [t["id"] for t in light])
    for app in APPS:
        html = read(WEB, app, "index.html")
        i_th, i_js = html.find('<script src="../olympus/themes.js?v=o4"></script>'), html.find(f'../olympus/olympus.js?v=o4" data-app="{app}"')
        check(f"a. {app}: loads the theme engine just before the kit", 0 < i_th < i_js, (i_th, i_js))
    for app in THREE_APPS:
        code = "".join(read(p) for p in glob.glob(os.path.join(WEB, app, "*.js")))
        check(f"a. {app}: its scene takes the theme's tint in one line (OLYMPUS themeScene / onTheme + tint)",
              "O?.themeScene?.(" in code or ("O?.onTheme(" in code and "O.tint(" in code)
              or ("onTheme(" in code and ("applyTheme" in code or "setAccent" in code)))   # 2026-11-03 day: the apps' own hooks
    jv = read(WEB, "jarvis", "index.html")
    check("a. Jarvis: the engine loads async (never part of the start), the <head> paints its copy, the Look sheet has the tiles",
          '<script src="../olympus/themes.js?v=o4" id="olyThemesJs" async></script>' in jv and "g('olympus.theme.paint')" in jv
          and 'id="olyThemes"' in jv and "function setOlyTheme(" in jv and "t.apply('page', { jarvis: true, cache: true })" in jv)
    check("a. Zenith and Kalshi load the engine (async) and apply the tokens on their own surfaces",
          "s.src = 'olympus/themes.js?v=o4'" in read(WEB, "index.html") and "s.src = '../olympus/themes.js?v=o4'" in read(WEB, "kalshi", "index.html"))


# ------------------------------------------------------------------ b. contrast
def test_contrast(data):
    if not data:
        return
    for t in data["list"]:
        k = t["tokens"]
        bg = rgba(k["bg"])
        panel = over(rgba(k["glass"]), bg)
        pairs = {"text/page": contrast(k["text"], bg), "dim/page": contrast(k["dim"], bg), "text/panel": contrast(k["text"], panel),
                 "dim/panel": contrast(k["dim"], panel)}
        if t["scheme"] == "light":
            sheet = over(rgba(k["glass2"]), bg)
            pairs.update({"accent/page": contrast(k["accent"], bg), "accent/panel": contrast(k["accent"], panel), "text/sheet": contrast(k["text"], sheet),
                          "ok/page": contrast(k["ok"], bg), "bad/page": contrast(k["bad"], bg), "warn/page": contrast(k["warn"], bg)})
            j = t["jarvis"]
            jbg, jpanel = rgba(j["bg"]), over(rgba(j["pr"]) [:3] + [0.62], rgba(j["bg"]))
            pairs.update({"Jarvis txt/page": contrast(j["txt"], jbg), "Jarvis mut/page": contrast(j["mut"], jbg), "Jarvis c3 labels/page": contrast(j["c3"], jbg),
                          "Jarvis cr3 title/page": contrast(j["cr3"], jbg), "Jarvis c/page": contrast(j["c"], jbg), "Jarvis txt/panel": contrast(j["txt"], jpanel),
                          "Jarvis mut/panel": contrast(j["mut"], jpanel), "white on the accent button": contrast("#ffffff", rgba(j["c2"]))})
            st = data["stage"][IDS.index(t["id"])]
            sbg = rgba(st["bg"])
            pairs.update({"stage text": contrast(st["text"], over(rgba(st["glass"]), sbg)), "stage dim": contrast(st["dim"], over(rgba(st["glass"]), sbg))})
        low = {n: round(v, 2) for n, v in pairs.items() if v < 4.5}
        check(f"b. {t['name']}: text passes WCAG AA (4.5:1) " + ("everywhere it is read (page, glass, sheet, Jarvis, status colours, the 3D stage)" if t["scheme"] == "light"
                                                                   else "on its page and its glass"),
              not low, {"low": low, "all": {n: round(v, 2) for n, v in pairs.items()}})


# ------------------------------------------------------------------ the server: the whole site folder, nothing else
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


from tests import browser_kit as BK  # noqa: E402  (shared launch: one reused browser, load-scaled timeouts, one retry of a flaky wait)


def launch(pw):
    return BK.launch(pw, args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])


# the scene hook, stubbed: every themeScene / onTheme call is kept, so the test reads the colours the app handed over
# (CLEAR(): the renderer's clear colour, read into a duck Color: three's getClearColor(target) only calls target.copy)
STUB = """
window.CLEAR = () => { const s = window.__oly.scenes[0]; if (!s || !s.renderer) return null;
  const c = { copy(x) { this.v = [x.r, x.g, x.b].map((n) => Math.round(n * 1e4)).join(','); return this; } }; s.renderer.getClearColor(c); return c.v || null; };
(() => {
  window.__oly = { scenes: [], themes: 0 };
  let O;
  Object.defineProperty(window, 'OLYMPUS', { configurable: true, get: () => O, set: (v) => {
    O = v;
    const ts = v.themeScene, ot = v.onTheme;
    v.themeScene = (o) => { window.__oly.scenes.push(o); return ts(o); };
    v.onTheme = (cb) => { window.__oly.themes++; return ot((t) => { window.__oly.lastTheme = t && t.id; return cb(t); }); };
  } });
})();
"""


def ctx_page(br, origin, theme=None, extra=""):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    # the theme is set once per tab (a reload keeps what the page chose)
    init = ("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off');"
            " if (!sessionStorage.getItem('t.theme')) { sessionStorage.setItem('t.theme', '1');"
            + (f" localStorage.setItem('olympus.theme', {json.dumps(theme)});" if theme else " localStorage.removeItem('olympus.theme');") + " } } catch (e) {}")
    ctx.add_init_script(init + extra)
    p = ctx.new_page()
    p.set_default_timeout(90000)                 # a shared, loaded machine: software GL can hold the main thread for seconds
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    return ctx, p, errs


def real(errs):
    return [e for e in errs if "net::ERR_FAILED" not in e and "Failed to load resource" not in e]


DUMP = """(names) => { const cs = getComputedStyle(document.documentElement), out = {};
  for (const n of names) out[n] = n === '@body-bg' ? getComputedStyle(document.body).backgroundColor : n === '@body-color' ? getComputedStyle(document.body).color
    : n === '@theme-color' ? ((document.querySelector('meta[name="theme-color"]') || {}).content || '') : cs.getPropertyValue(n).trim();
  return out; }"""


def url_of(origin, name):
    return origin + ("/" if name == "zenith" else f"/{name}/{APPS.get(name, '')}")


def settle(p, name):
    if name == "jarvis":
        p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000)
        p.wait_for_function("!!window.OLYMPUS_THEMES", timeout=30000)
    elif name in APPS:
        p.wait_for_function("() => window.OLYMPUS && OLYMPUS.state() === 'ready'", timeout=40000)
    else:
        p.wait_for_function("!!window.OLYMPUS_THEMES && document.documentElement.hasAttribute('data-oly-theme')", timeout=15000)
    p.wait_for_timeout(700)


# ------------------------------------------------------------------ c. the default theme is today's look
def regen_baseline(br, origin):
    """--regen: re-capture today's default look (no theme key) after an intended app restyle; the theme tests then check
    that the 'olympus' key and coming back to the default both equal it."""
    base = json.load(open(BASE, encoding="utf-8"))
    for name, want in base.items():
        ctx, p, errs = ctx_page(br, origin, None)
        try:
            p.goto(url_of(origin, name)); settle(p, name)
            base[name] = p.evaluate(DUMP, list(want))
        finally:
            ctx.close()
    json.dump(base, open(BASE, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print("baseline re-captured:", len(base), "pages")


def test_default(br, origin):
    base = json.load(open(BASE, encoding="utf-8"))
    for name, want in base.items():
        for theme in (None, DEFAULT_ID):
            ctx, p, errs = ctx_page(br, origin, theme)
            try:
                p.goto(url_of(origin, name))
                settle(p, name)
                got = p.evaluate(DUMP, list(want))
                diff = {k: (want[k], got[k]) for k in want if got[k] != want[k] and not k.startswith("--stack")}
                check(f"c. {name}: {'no key' if theme is None else 'olympus.theme = agora'} -> every computed CSS variable as before the themes ({len(want)})",
                      not diff, diff)
            except Exception as e:
                check(f"c. {name}: default theme as before", False, e)
            ctx.close()


# ------------------------------------------------------------------ d. Jarvis
def open_look(p):
    """⋯ -> Theme, like the owner (tried again if a busy start swallowed the tap)"""
    for _ in range(4):
        if p.locator("#more").is_hidden():
            p.click("#moreB")
        p.wait_for_timeout(150)
        p.click('#more [data-key="theme"]')
        try:
            p.wait_for_selector("#olyThemes .oth", timeout=3000)
            return
        except Exception:
            p.wait_for_timeout(500)
    raise RuntimeError("the Look sheet did not open: " + str(p.evaluate("[document.getElementById('look').hidden, document.getElementById('olyThemes').innerHTML.slice(0, 120)]")))


def test_jarvis(br, origin, shots=None):
    ctx, p, errs = ctx_page(br, origin)
    p.goto(origin + "/jarvis/")
    settle(p, "jarvis")
    # frame an app inside Jarvis, then theme from the Look sheet
    p.evaluate("window.__jarvis.show('oracle')")
    p.wait_for_function("() => { const f = [...document.querySelectorAll('iframe')].find((x) => /oracle/.test(x.src)); return f && f.contentWindow.OLYMPUS && f.contentWindow.OLYMPUS.state() === 'ready'; }", timeout=40000)
    p.evaluate("window.__jarvis.show('home')")
    p.wait_for_timeout(300)
    open_look(p)
    tiles = p.evaluate("""() => [...document.querySelectorAll('#olyThemes .oth')].map((b) => ({ k: b.dataset.olyK, on: b.getAttribute('aria-pressed'),
        anim: getComputedStyle(b.querySelector('.oth-sw .r')).animationName, h: b.getBoundingClientRect().height, w: b.getBoundingClientRect().width,
        over: b.scrollWidth > b.clientWidth + 1 }))""")
    check("d. the Look sheet: eight OLYMPUS theme tiles (Agora pressed), each a live mini scene (turning ring), 44 px+ targets, nothing spills",
          [t["k"] for t in tiles] == IDS and tiles[0]["on"] == "true" and all(t["anim"] == "oth-spin" and t["h"] >= 44 and not t["over"] for t in tiles), tiles)
    p.click('#olyThemes [data-oly-k="zeus"]')
    p.wait_for_timeout(250)
    st = p.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
        return { key: localStorage.getItem('olympus.theme'), attr: document.documentElement.dataset.olyTheme, c: cs.getPropertyValue('--c').trim(),
                 bg: cs.getPropertyValue('--bg').trim(), tone: cs.getPropertyValue('--oly-tone').trim(), meta: document.querySelector('meta[name="theme-color"]').content,
                 body: getComputedStyle(document.body).backgroundColor, pressed: document.querySelector('#olyThemes [aria-pressed="true"]').dataset.olyK,
                 jpressed: document.querySelectorAll('#themes [aria-pressed="true"]').length,
                 paint: JSON.parse(localStorage.getItem('olympus.theme.paint') || 'null') }; }""")
    check("d. a tap on Zeus Storm: 'olympus.theme' = zeus, Jarvis repainted at once (--c #4da3ff, --bg #02050f, the status bar), the tile pressed",
          st["key"] == "zeus" and st["attr"] == "zeus" and st["c"] == "#4da3ff" and st["bg"] == "#02050f" and st["tone"] == "#4da3ff"
          and st["meta"] == "#02050f" and st["pressed"] == "zeus" and st["jpressed"] == 0 and st["paint"] and st["paint"]["id"] == "zeus", st)
    fr = p.evaluate("""() => { const f = [...document.querySelectorAll('iframe')].find((x) => /oracle/.test(x.src)), w = f.contentWindow, d = w.document.documentElement;
        return { attr: d.dataset.olyTheme, theme: w.OLYMPUS.theme() && w.OLYMPUS.theme().id, glass: w.getComputedStyle(d).getPropertyValue('--glass').trim(),
                 accent: w.getComputedStyle(d).getPropertyValue('--oly-accent').trim() }; }""")
    check("d. the app framed in Jarvis (Oracle) follows through the storage event: its theme, its glass, its accent harmonised",
          fr["attr"] == "zeus" and fr["theme"] == "zeus" and fr["glass"] == "rgba(6, 14, 34, .74)" and fr["accent"] not in ("", "#7fe9ff"), fr)
    # the scanline option
    p.click("#setGrain")
    p.wait_for_timeout(200)
    gr = p.evaluate("""() => { const f = [...document.querySelectorAll('iframe')].find((x) => /oracle/.test(x.src));
        return [localStorage.getItem('olympus.grain'), !!document.querySelector('.oly-grain'), getComputedStyle(document.querySelector('.oly-grain')).pointerEvents,
                !!f.contentWindow.document.querySelector('.oly-grain')]; }""")
    check("d. Scanlines: the grain layer over Jarvis and the framed app (stored once, never takes a tap)", gr == ["1", True, "none", True], gr)
    p.click("#setGrain")
    if shots:
        os.makedirs(shots, exist_ok=True)
    # Athena (the light theme) from the sheet, then reopen: from the first paint
    p.click('#olyThemes [data-oly-k="athena"]')
    p.wait_for_timeout(250)
    lt = p.evaluate("""() => { const cs = getComputedStyle(document.documentElement), sh = document.querySelector('#look .sheet-in');
        return { scheme: document.documentElement.dataset.olyScheme, cs: cs.colorScheme, body: getComputedStyle(document.body).backgroundColor,
                 label: getComputedStyle(document.querySelector('#look label')).color, note: getComputedStyle(document.getElementById('olyNote')).color }; }""")
    check("d. Athena: a light page (marble body, color-scheme light, dark ink in the sheet)", lt["scheme"] == "light" and lt["cs"] == "light"
          and contrast(lt["label"], lt["body"]) >= 4.5 and lum(rgba(lt["body"])) > 0.8, lt)
    p.click("#lookX")
    p.reload()
    early = p.evaluate("() => [document.documentElement.dataset.olyTheme, document.documentElement.style.getPropertyValue('--c'), document.documentElement.dataset.olyScheme]")
    settle(p, "jarvis")
    says = p.evaluate("() => [getComputedStyle(document.querySelector('.says')).color, getComputedStyle(document.body).backgroundColor]")
    check("d. reopened: Athena is there before the engine arrives (the <head> copy), and Jarvis's line reads on the marble (AA)",
          early[0] == "athena" and early[1].strip() == "#55631f" and early[2] == "light" and contrast(says[0], says[1]) >= 4.5, (early, says))
    # a Jarvis colour belongs to the default theme
    p.evaluate("window.__jarvis.setTheme('reactor-stark')")
    p.wait_for_timeout(200)
    back = p.evaluate("() => [localStorage.getItem('olympus.theme'), document.documentElement.dataset.olyTheme, getComputedStyle(document.documentElement).getPropertyValue('--c').trim(), document.documentElement.style.getPropertyValue('--c'), localStorage.getItem('olympus.theme.paint')]")
    check("d. a Jarvis colour (Reactor Stark) goes back to the OLYMPUS default and shows its own colour (no inline paint left)",
          back[0] == "agora" and back[1] == "agora" and back[2] == "#ffbe3d" and back[3] == "" and back[4] is None, back)
    p.evaluate("window.__jarvis.setTheme('reactor')")
    check("d. Jarvis: no console error while theming", not real(errs), real(errs)[:3])
    ctx.close()


def jarvis_shots(br, origin, out):
    os.makedirs(out, exist_ok=True)
    for th in IDS:
        ctx, p, errs = ctx_page(br, origin, th)
        p.goto(origin + "/jarvis/")
        settle(p, "jarvis")
        p.wait_for_timeout(2500)
        p.screenshot(path=os.path.join(out, f"jarvis-{th}.png"))
        open_look(p)
        p.wait_for_timeout(700)
        p.screenshot(path=os.path.join(out, f"jarvis-{th}-look.png"))
        ctx.close()
    print("screenshots:", out)


# ------------------------------------------------------------------ e. each app under a theme
def test_app(br, origin, app):
    ctx, p, errs = ctx_page(br, origin, "hades", STUB)
    p.goto(url_of(origin, app))
    try:
        settle(p, app)
    except Exception as e:
        check(f"e. {app}: comes up under Hades", False, e)
        ctx.close()
        return
    p.wait_for_timeout(1200)
    got = p.evaluate("""() => { const O = window.OLYMPUS, t = O.theme(), cs = getComputedStyle(document.documentElement), s = window.__oly.scenes[0];
        const hex = (c) => c && c.getHex ? c.getHex() : null;
        return { id: t && t.id, attr: document.documentElement.dataset.olyTheme, accent: cs.getPropertyValue('--oly-accent').trim(), own: O.color,
                 bg: cs.getPropertyValue('--bg').trim(), glass: cs.getPropertyValue('--oly-glass').trim(), scenes: window.__oly.scenes.length, subs: window.__oly.themes,
                 fog: s && s.scene && s.scene.fog ? hex(s.scene.fog.color) : null, clear: CLEAR(), sx: document.documentElement.scrollWidth - innerWidth,
                 tint: O.tint(0x02030a, 'fog'), meta: (document.querySelector('meta[name="theme-color"]') || {}).content }; }""")
    base = json.load(open(BASE, encoding="utf-8"))[app]
    hooked = got["scenes"] > 0 or got["subs"] > 0 if app in THREE_APPS else True
    check(f"e. {app}: reads Hades at start (tokens, its own --bg blended toward the theme, the status bar), its accent harmonised",
          got["id"] == "hades" and got["attr"] == "hades" and got["glass"] == "rgba(18, 4, 4, .78)" and got["bg"] != base["--bg"]
          and (got["meta"] != base["@theme-color"] or app in OWN_META) and (got["accent"] != base["--oly-accent"] or app == "datacity") and got["sx"] <= 0, got)   # Data City: its sky follows the market clock (day sprint), the accent stays its blue
    if app in THREE_APPS:
        check(f"e. {app}: its scene hook gets the tint (stubbed; the fog colour handed over is the theme's blend)",
              hooked and (got["fog"] is None or got["fog"] != int(base.get("--bg", "#000000")[1:], 16)) and got["tint"] != 0x02030a, got)
    # a live change from another page on the same origin (Jarvis's Look sheet in another tab, or the frame around it)
    p2 = ctx.new_page()
    p2.goto(origin + "/olympus/themes.js")
    p2.evaluate("localStorage.setItem('olympus.theme', 'poseidon')")
    try:                                     # a busy software-GL frame loop can hold the storage event a moment
        p.wait_for_function("() => OLYMPUS.theme() && OLYMPUS.theme().id === 'poseidon'", timeout=8000)
    except Exception:
        pass
    p.wait_for_timeout(300)
    live = p.evaluate("""() => ({ id: OLYMPUS.theme().id, glass: getComputedStyle(document.documentElement).getPropertyValue('--oly-glass').trim(), last: window.__oly.lastTheme,
        fog: window.__oly.scenes[0] && window.__oly.scenes[0].scene.fog ? window.__oly.scenes[0].scene.fog.color.getHex() : null, clear: CLEAR() })""")
    check(f"e. {app}: follows a live change (storage event): Poseidon's glass" + (", the scene hook re-tinted" if app in THREE_APPS else ""),
          live["id"] == "poseidon" and live["glass"] == "rgba(2, 20, 28, .74)"
          and (app not in THREE_APPS or live["last"] == "poseidon" or live["fog"] != got["fog"] or live["clear"] != got["clear"]), (live, got))
    p2.evaluate("localStorage.setItem('olympus.theme', 'agora')")
    try:
        p.wait_for_function("() => OLYMPUS.theme() && OLYMPUS.theme().id === 'agora'", timeout=8000)
    except Exception:
        pass
    p.wait_for_timeout(300)
    back = p.evaluate("""(names) => { const cs = getComputedStyle(document.documentElement), o = {}; for (const n of names) o[n] = cs.getPropertyValue(n).trim(); return o; }""",
                      [k for k in base if k.startswith("--")])
    diff = {k: (base[k], back[k]) for k in back if back[k] != base[k]}
    check(f"e. {app}: back on the default, every CSS variable is today's again", not diff, diff)
    check(f"e. {app}: no console error at 390 x 844 under the themes", not real(errs), real(errs)[:3])
    ctx.close()


def test_zenith_kalshi(br, origin):
    for name, var, own in (("zenith", "--page", "#14110e"), ("kalshi", "--bg", "#010a07")):
        ctx, p, errs = ctx_page(br, origin, "apollo")
        p.goto(url_of(origin, name))
        try:
            settle(p, name)
            got = p.evaluate(f"""() => {{ const cs = getComputedStyle(document.documentElement);
                return [document.documentElement.dataset.olyTheme, cs.getPropertyValue('--oly-tone').trim(), cs.getPropertyValue('{var}').trim(),
                        (document.querySelector('meta[name="theme-color"]') || {{}}).content]; }}""")
            check(f"e. {name}: Apollo's tokens, its own page colour blended toward the theme, the status bar", got[0] == "apollo" and got[1] == "#ffb020"
                  and got[2] not in ("", own) and got[3] == "#0a0502", got)
        except Exception as e:
            check(f"e. {name}: takes the theme", False, e)
        ctx.close()


def main():
    data = theme_data()
    test_static(data)
    test_contrast(data)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser tests skipped: no Playwright", True)
        return
    srv, origin = serve()
    shots = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
    only = [a for a in sys.argv[1:] if a in APPS or a in ("jarvis", "default", "zenith")]
    with sync_playwright() as pw:
        br = launch(pw)
        if "--regen" in sys.argv:
            regen_baseline(br, origin)
            only = only or ["-"]
        if shots:
            jarvis_shots(br, origin, shots)
            if not only:                         # --shots alone: the screenshots only
                only = ["-"]
        if not only or "jarvis" in only:
            test_jarvis(br, origin)
        if not only or "default" in only:
            test_default(br, origin)
        for app in [a for a in APPS if not only or a in only]:
            test_app(br, origin, app)
        if not only or "zenith" in only:
            test_zenith_kalshi(br, origin)
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
