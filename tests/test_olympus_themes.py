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
PLAIN = ["agora", "ivory", "midnight", "terminal", "carbon", "royal"]            # 2026-11-14: the colour looks
STYLED = ["night", "aurora", "amber", "lime", "stocks", "editorial", "brutal", "noir", "sunset", "ocean", "carbonred", "forest", "rosegold",      # the style looks
          "swiss", "paperdark", "solarized", "nord", "cyber", "deco", "zen", "desert", "monoblack", "monowhite", "vapor", "bullion", "wallstreet", "marble"]
OLD = ["olympus", "zeus", "poseidon", "hades", "athena", "apollo", "artemis"]      # 2026-11-03, kept for Jarvis / Settings
IDS = PLAIN + STYLED + OLD
LIGHT = ["ivory", "stocks", "editorial", "brutal", "swiss", "zen", "desert", "monowhite", "vapor", "marble", "athena"]
DEFAULT_ID = "agora"                 # AGORA is the default since 2026-11-09 (docs/DESIGN_AGORA.md); "olympus" is the old violet look, selectable
NAMES = {"night": "Olympus Night", "ivory": "Ivory", "midnight": "Midnight", "terminal": "Terminal", "carbon": "Carbon", "royal": "Royal", "aurora": "Glass Aurora", "amber": "Amber",
         "lime": "Lime", "stocks": "Stocks Light", "editorial": "Editorial", "brutal": "Neo Brutal", "noir": "Noir Gold", "sunset": "Sunset", "ocean": "Ocean",
         "carbonred": "Carbon Red", "forest": "Forest", "rosegold": "Rose Gold", "swiss": "Swiss", "paperdark": "Paper Dark", "solarized": "Solarized", "nord": "Nord",
         "cyber": "Cyber Minimal", "deco": "Art Deco", "zen": "Zen", "desert": "Desert", "monoblack": "Mono Black", "monowhite": "Mono White", "vapor": "Vapor Soft",
         "bullion": "Gold Bullion", "wallstreet": "Wall Street", "marble": "Marble White", "agora": "Agora", "olympus": "Olympus Night", "zeus": "Zeus Storm", "poseidon": "Poseidon", "hades": "Hades", "athena": "Athena", "apollo": "Apollo"}
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
const at = {}, ls = {};
const root = { style: { setProperty(k, v) { st[k] = v; }, removeProperty(k) { delete st[k]; }, getPropertyValue(k) { return st[k] || ''; } },
  setAttribute(k, v) { at[k] = v; }, getAttribute(k) { return k in at ? at[k] : null; }, removeAttribute(k) { delete at[k]; } };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), { window: w, location: { pathname: '/nq/' }, document: { documentElement: root, body: null, addEventListener() {}, querySelector() { return null; } },
  localStorage: { getItem(k) { return k in ls ? ls[k] : null; }, setItem(k, v) { ls[k] = String(v); }, removeItem(k) { delete ls[k]; }, key(i) { return Object.keys(ls)[i]; }, get length() { return Object.keys(ls).length; } } });
const T = w.OLYMPUS_THEMES;
// the mix: app beats district beats the one look
ls['olympus.theme'] = 'midnight'; ls['olympus.theme.v'] = '2';
ls['olympus.themeMix'] = JSON.stringify({ district: { trading: 'amber', money: 'stocks' }, app: { gate: 'aurora', helios: 'forest' }, of: { nq: 'trading', helios: 'trading', mint: 'money' } });
const mixed = { nq: T.lookFor('nq'), helios: T.lookFor('helios'), mint: T.lookFor('mint'), gate: T.lookFor('gate'), today: T.lookFor('today'), jarvis: T.lookFor('jarvis'), page: T.page(), here: T.id() };
T.apply('page'); mixed.style = at['data-oly-style'] || null; mixed.case = st['--oly-th-title-case'] || null; mixed.n3 = st['--oly-th-n3'] || null;
T.set('ivory'); mixed.afterSet = [T.id(), 'olympus.themeMix' in ls, at['data-oly-style'] || null];
T.set('agora'); mixed.afterDefault = [Object.keys(st).filter((k) => k.indexOf('--oly-th-') === 0).length, at['data-oly-style'] || null];
const slots = {}; T.list().forEach((t) => { slots[t.id] = { page: T.slots(t.id, 'page'), stage: T.slots(t.id, 'stage') }; });
// T2 (2026-11-14): the extra slots of every look (info blue, ring, shadows), the <head> copies a pick writes, the preview, no-blur
const pick = (o, ks) => { const r = {}; ks.forEach((k) => { r[k] = o[k]; }); return r; };
const EXK = ['--oly-th-info', '--oly-th-infot', '--oly-th-ring', '--oly-th-shadow', '--oly-th-e1', '--oly-th-n3', '--oly-th-n4', '--oly-th-n5', '--oly-th-n7', '--oly-th-card-bg', '--oly-th-card-blur'];
const extras = {}; T.list().forEach((t) => { extras[t.id] = { page: pick(T.paintOf(t.id, 'page').vars, EXK), stage: pick(T.paintOf(t.id, 'stage').vars, EXK) }; });
const lookKeys = () => Object.keys(ls).filter((k) => k.indexOf('olympus.theme.look.') === 0).sort();
const t2 = {};
T.set('midnight'); t2.afterSet = lookKeys();
T.setMix({ district: { bots: 'amber', money: 'stocks' }, app: { gate: 'aurora' }, of: { nq: 'bots' } }); t2.afterMix = lookKeys();
T.set('ivory'); t2.afterOne = lookKeys();
T.apply('page'); const before = st['--oly-th-n3'];
t2.preview = [T.preview('carbon'), at['data-oly-theme'], st['--oly-th-n3'] !== before, ls['olympus.theme'], lookKeys().indexOf('olympus.theme.look.page.carbon') < 0];
t2.previewEnd = [T.preview(null), at['data-oly-theme'], st['--oly-th-n3'] === before];
T.noblur(true); const nb = T.paintOf('aurora', 'page').vars; t2.noblur = [nb['--oly-th-card-blur'], nb['--oly-th-card-bg']]; T.noblur(false);
t2.blur = T.paintOf('aurora', 'page').vars['--oly-th-card-blur'];
T.set('agora'); t2.afterDefault = lookKeys();
process.stdout.write(JSON.stringify({ TOKENS: T.TOKENS, JARVIS: T.JARVIS, GRID: T.GRID, STYLE: T.STYLE, plain: T.plain().map((t) => t.id), mixed, slots, extras, t2,
  groups: T.groups().map((g) => [g.id, g.themes.map((t) => t.id)]),
  styles: T.list().map((t) => [t.id, t.style || null, t.feel || null]), list: T.list(), stage: T.list().map((t) => T.tokens(t.id, 'stage')),
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
        check(f"a. {len(IDS)} themes in picker order: Agora (default), the 5 colour looks, the {len(STYLED)} style looks, then the 7 earlier ones; the Gate shows the first {len(PLAIN + STYLED)}",
              ids == IDS and data["plain"] == PLAIN + STYLED, (ids, data["plain"]))
        grp = dict(data["groups"])
        check("a. the picker's groups: Dark, Light, Bold, Luxury hold every look but the default exactly once; every light theme is in Light or a bold / luxury group",
              [g for g, _ in data["groups"]] == ["dark", "light", "bold", "luxury"] and sorted(sum(grp.values(), [])) == sorted(PLAIN[1:] + STYLED)
              and all(i in grp["light"] + grp["bold"] + grp["luxury"] for i in LIGHT if i != "athena"), data["groups"])
        GATE_ORDER[:] = ["agora"] + sum((ids_ for _, ids_ in data["groups"]), [])
        check("a. names: plain words (Ivory, Midnight, Terminal ... Glass Aurora, Amber, Stocks Light ... Rose Gold)",
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
        check("a. every light theme (Ivory, Stocks Light, Editorial, Neo Brutal, Athena) has a dark 'stage' palette for the 3D apps / Kalshi / pages not checked in light",
              sorted(t["id"] for t in light) == sorted(LIGHT) and all(t.get("stage") and data["stage"][IDS.index(t["id"])]["scheme"] == "dark" for t in light), [t["id"] for t in light])
        test_reach_data(data)
    for app in APPS:
        html = read(WEB, app, "index.html")
        i_th, i_js = html.find('<script src="../olympus/themes.js?v=o11"></script>'), html.find(f'../olympus/olympus.js?v=o27" data-app="{app}"')
        check(f"a. {app}: loads the theme engine just before the kit", 0 < i_th < i_js, (i_th, i_js))
    for app in THREE_APPS:
        code = "".join(read(p) for p in glob.glob(os.path.join(WEB, app, "*.js")))
        check(f"a. {app}: its scene takes the theme's tint in one line (OLYMPUS themeScene / onTheme + tint)",
              "O?.themeScene?.(" in code or ("O?.onTheme(" in code and "O.tint(" in code)
              or ("onTheme(" in code and ("applyTheme" in code or "setAccent" in code)))   # 2026-11-03 day: the apps' own hooks
    jv = read(WEB, "jarvis", "index.html")
    check("a. Jarvis: the engine loads async (never part of the start), the <head> paints its copy, the Look sheet has the tiles",
          '<script src="../olympus/themes.js?v=o11" id="olyThemesJs" async></script>' in jv and "('jarvis', 'page');" in jv
          and 'id="olyThemes"' in jv and "function setOlyTheme(" in jv and "t.apply('page', { jarvis: true, cache: true })" in jv)
    check("a. Zenith and Kalshi load the engine (async) and apply the tokens on their own surfaces",
          "s.src = 'olympus/themes.js?v=o11'" in read(WEB, "index.html") and "s.src = '../olympus/themes.js?v=o11'" in read(WEB, "kalshi", "index.html"))


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
    # OLYMPUS NIGHT (2026-11-20) is the owner's default: an empty or AGORA choice moves to 'night' once (themes.js stored()); these checks are about
    # the engine's own rules, so they run with that one-time switch already done (the marker): no key / 'agora' = the default that paints nothing.
    # test_night_default() checks the switch itself.
    init = ("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('olympus.theme.night', '1');"
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
        if not p.locator("#look").is_hidden() and p.locator("#olyThemes .oth").count():
            return
        if p.locator("#more").is_hidden():
            p.click("#moreB")
        p.wait_for_timeout(150)
        p.click('#more [data-key="theme"]')
        try:
            p.wait_for_selector("#olyThemes .oth", timeout=8000)
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
          fr["attr"] == "zeus" and fr["theme"] == "zeus" and fr["glass"] == "rgba(6, 14, 34, .74)" and fr["accent"] not in ("", "#7fb0a3"), fr)
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
    p.evaluate("window.__jarvis.setTheme('agora')")
    p.wait_for_timeout(200)
    back = p.evaluate("() => [localStorage.getItem('olympus.theme'), document.documentElement.dataset.olyTheme, getComputedStyle(document.documentElement).getPropertyValue('--c').trim(), document.documentElement.style.getPropertyValue('--c'), localStorage.getItem('olympus.theme.paint')]")
    check("d. a Jarvis colour (Agora) goes back to the OLYMPUS default and shows its own colour (no inline paint left): Classic Jarvis's violet, the Jarvis default since 2026-11-18",
          back[0] == "agora" and back[1] == "agora" and back[2] == "#a855f7" and back[3] == "" and back[4] is None, back)
    p.evaluate("window.__jarvis.setTheme('agora')")
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


# ------------------------------------------------------------------ f. the reach (2026-11-14): tokenized stylesheets, the ramp, style looks, the mix
sys.path.insert(0, os.path.join(ROOT, "tools"))
import theme_tokenize as TOK  # noqa: E402

TOKENIZED = ["olympus/agora.css", "olympus/agora-apps.css", "gate/gate.css", "gate/index.html", "index.html", "zenith.css", "zenith_agora.css", "polish.css",
             "nq/nq.css", "helios/helios.css", "polis/polis.css", "olympus/polis.css", "jarvis/jarvis.css", "jarvis/home3d.css", "kalshi/kalshi.css",
             "olympus/gate-nav.js", "launcher.js", "olympus/polis-life.js", "jarvis/switcher.js", "jarvis/copilot-card.js", "hub/hub.css", "hub/index.html",
             # T2 (2026-11-14, "lock down the looks"): every app on the QA matrix, the dashboard's injected sheets, the kit's own
             "aegis/aegis.css", "mint/mint.css", "oikos/oikos.css", "ledger/ledger.css", "planner/planner.css", "cities/world.css", "cities/agora-cities.css",
             "symposium/symposium.css", "olympus/people.css", "settings/settings.css", "olympus/olympus.css", "holo.css", "mission.css", "liveview.css",
             "statuscore.js", "realcore.js", "blitzcore.js", "zenithcore.js", "sessioncore.js", "moneynowcore.js", "boardcore.js",
             "liveview.js", "jarvis/assist-ui.js", "goals.js", "features.js", "more.js", "hub.js", "olympus/glossary-lite.js"]
LAYER = "style themes (olympus/themes.js 'style', 2026-11-14)"


def test_reach_data(data):
    check("f. the grid of theme slots in themes.js equals tools/theme_tokenize.py's (the tool and the engine agree on every slot)",
          {k: list(v) for k, v in data["GRID"].items()} == {k: list(v) for k, v in TOK.GRID.items()}, (data["GRID"], TOK.GRID))
    mx = data["mixed"]
    check("f. the mix: an app's own look beats its district's, which beats the one look (nq -> Amber via Trading, helios -> Forest (its own), mint -> Stocks Light, the Gate -> Glass Aurora, the dashboard counts as Trading, Jarvis keeps Midnight)",
          [mx[k] for k in ("nq", "helios", "mint", "gate", "today", "jarvis", "page", "here")] == ["amber", "forest", "stocks", "aurora", "amber", "midnight", "nq", "amber"], mx)
    check("f. a style look paints its style tokens and marks <html data-oly-style> (Amber: capitals); 'One look' clears the mix; the default paints no slot and no style",
          mx["style"] == "amber" and mx["case"] == "uppercase" and mx["n3"] and mx["afterSet"] == ["ivory", False, None] and mx["afterDefault"] == [0, None], mx)
    st = {i: (s, f) for i, s, f in data["styles"]}
    miss = {i: [k for k in data["STYLE"] if not (st[i][0] or {}).get(k)] for i in STYLED}
    miss = {k: v for k, v in miss.items() if v}
    fonts = " ".join(str((st[i][1] or {}).get("display", "")) + " " + str((st[i][0] or {}).get("body", "")) for i in IDS)
    check("f. every style look carries every style token (page, card, border, shadow, blur, title weight / case / tracking / italic, body font, button) and only system fonts (no download)",
          not miss and "url(" not in fonts and "http" not in fonts and all(st[i][1] and st[i][1].get("radius") for i in STYLED), miss)
    defs = []
    for fp in glob.glob(os.path.join(WEB, "**", "*.css"), recursive=True) + glob.glob(os.path.join(WEB, "**", "*.html"), recursive=True):
        # Jarvis's own Classic look (jarvis/classic.css, the Jarvis default since 2026-11-18) repaints the slots, but only inside rules scoped
        # to <html data-jlook="classic">: those blocks are its look, not a stylesheet painting the AGORA default
        txt = re.sub(r'html:root\[data-jlook="classic"\][^{}]*\{[^{}]*\}', "", read(fp))
        if re.search(r"--oly-th-[\w-]+\s*:", txt):
            defs.append(os.path.relpath(fp, WEB))
    check("f. no stylesheet defines a theme slot (--oly-th-*): only themes.js paints them, so on the default every var(--oly-th-x, <AGORA colour>) is the AGORA colour", not defs, defs)
    left, layer_bad = {}, {}
    for f in TOKENIZED:
        txt = read(WEB, f)
        body = txt.split(LAYER)[0]
        un = TOK.untokenize(body)
        if "--oly-th-" in un or "var(--oly-th-" not in txt:
            left[f] = un[un.find("--oly-th-") - 80:un.find("--oly-th-") + 60] if "--oly-th-" in un else "not tokenized"
        if LAYER in txt:
            sels = re.findall(r"(?m)^([^{}\n/][^{}]*)\{", txt.split(LAYER)[1].split("*/", 1)[1])
            bad = [x.strip() for x in sels if not x.strip().startswith("html[data-oly-style]")]
            if bad:
                layer_bad[f] = bad
    check(f"f. {len(TOKENIZED)} stylesheets / scripts read theme slots, each with its AGORA literal as the fallback (the tool's untokenize gives back plain colours)", not left, left)
    check("f. the style layers (agora.css, gate.css, zenith_agora.css, jarvis.css) only match under <html data-oly-style>", not layer_bad and all(LAYER in read(WEB, f) for f in (
        "olympus/agora.css", "gate/gate.css", "zenith_agora.css", "jarvis/jarvis.css")), layer_bad)
    ag = read(KIT, "agora.css")
    check("f. agora.css's own tokens read the theme with the AGORA values as fallbacks (--ag-night, --ag-gold, --ag-text, the radius, the heading / number fonts)",
          "--ag-night: var(--oly-th-n3, #14110e)" in ag and "--ag-gold: var(--oly-th-a8, #c8a24a)" in ag and "--ag-text: var(--oly-th-n37, #f3ece0)" in ag
          and "--ag-radius: var(--oly-th-radius, 16px)" in ag and "--ag-serif: var(--oly-th-display," in ag and "--ag-num: var(--oly-th-num," in ag)


def stops(c):
    """the colours of a CSS background (a colour, or every colour stop of a gradient)"""
    return re.findall(r"#[0-9a-fA-F]{6}|rgba?\([^)]*\)", c) or [c]


def test_slot_contrast(data):
    if not data:
        return
    TXT = {"text": "n37", "soft": "n30", "muted": "n24", "gain": "g8", "loss": "r10", "gold as text": "a8", "warn": "warn"}
    SURF = {"page": "n3", "panel": "n4", "raised": "n5", "s4": "n7"}
    styles = {i: s for i, s, f in data["styles"]}
    for tid in PLAIN[1:] + STYLED:
        t = data["list"][IDS.index(tid)]
        for where in (("page", "stage") if t["scheme"] == "light" else ("page",)):
            sl = data["slots"][tid][where]
            low = {}
            for tn, tk in TXT.items():
                for sn, sk in SURF.items():
                    v = contrast(sl[tk], sl[sk])
                    if v < 4.5:
                        low[f"{tn}/{sn}"] = round(v, 2)
            sty = styles.get(tid)
            if sty and where == "page":
                pg = rgba(stops(sty["page"])[0]) if stops(sty["page"])[0].startswith(("#", "rgb")) else rgba(sl["n3"])
                for stop in stops(sty["page"]):
                    if stop.startswith("#"):
                        card = over(rgba(stops(sty["card"])[0]), rgba(stop))
                        for tn in ("text", "soft", "muted"):
                            v = contrast(sl[TXT[tn]], card)
                            if v < 4.5:
                                low[f"{tn}/card over {stop}"] = round(v, 2)
                        for tn in ("gold as text",):                       # section titles sit on the page itself
                            v = contrast(sl[TXT[tn]], rgba(stop))
                            if v < 4.5:
                                low[f"{tn}/page {stop}"] = round(v, 2)
                for b in stops(sty["btn"]):
                    if b == "transparent":
                        b = sl["n3"]
                    v = contrast(sty["btnFg"], rgba(b) if b.startswith(("#", "rgb")) else rgba(sl["n3"]))
                    if v < 4.5:
                        low[f"button text on {b}"] = round(v, 2)
            check(f"b. {t['name']} ({where}): every text colour the pages show (text, soft, muted, gains, losses, gold-as-text, warn) is >= 4.5:1 on the page, the panels"
                  + (", the cards and the button" if sty and where == "page" else ""), not low, low)


GATE_Q = "?now=2026-11-12T15:00:00Z"
GATE_ORDER: list = []                        # Agora, then the groups (filled from the data)


def gate_ready(p):
    p.wait_for_function("() => window.GATE && window.GATE.ready() && !document.getElementById('lookSec').hidden", timeout=60000)
    p.wait_for_timeout(300)


# 2026-11-14: the Me hub (team ME1, a page hub: health, cards, home) has its own Mix row and takes Plan & Day's look in the combos
MIX_ROWS = ["Bots & Evals", "My Money", "Today", "Me", "Plan & Day", "Jarvis", "Research", "Kalshi", "Worlds", "Settings & Help", "This Gate"]   # the Gate's hub order (2026-11-16: Bots & Evals and My Money lead, Kalshi and Worlds last)
TRADER_HUBS = {"today": "amber", "me": "forest", "bots": "amber", "kalshi": "stocks", "money": "stocks", "plan": "forest", "research": "amber", "jarvis": "forest", "worlds": "aurora", "settings": "forest"}


def test_gate_look(br, origin):
    ctx, p, errs = ctx_page(br, origin, None)
    p.goto(origin + "/gate/" + GATE_Q)
    gate_ready(p)
    sw = p.evaluate("""() => [...document.querySelectorAll('#looks .g-sw')].map((b) => ({ id: b.dataset.themeId, on: b.getAttribute('aria-checked'), h: b.getBoundingClientRect().height,
        name: b.querySelector('b').textContent }))""")
    heads = p.evaluate("() => [...document.querySelectorAll('#looks .g-lookg')].map((h) => h.textContent)")
    check(f"g. the Gate's Look row: One look shows {len(PLAIN + STYLED)} swatches in groups (Default, Dark, Light, Bold, Luxury), Agora picked, each a 44 px+ target, no sideways page scroll",
          [x["id"] for x in sw] == (GATE_ORDER or [x["id"] for x in sw]) and len(sw) == len(PLAIN + STYLED) and heads == ["Default", "Dark", "Light", "Bold", "Luxury"]
          and sw[0]["on"] == "true" and all(x["h"] >= 44 for x in sw) and p.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, (heads, sw[:3]))
    p.click('#looks [data-theme-id="midnight"]')
    p.wait_for_timeout(250)
    st = p.evaluate("""() => { const r = document.documentElement, cs = getComputedStyle(r);
        return { key: localStorage.getItem('olympus.theme'), attr: r.dataset.olyTheme, style: r.dataset.olyStyle || null, n3: cs.getPropertyValue('--oly-th-n3').trim(),
          card: getComputedStyle(document.querySelector('.g-card')).backgroundImage, on: document.querySelector('#looks [aria-checked="true"]').dataset.themeId,
          meta: document.querySelector('meta[name="theme-color"]').content }; }""")
    check("g. a tap on Midnight: 'olympus.theme' = midnight, the Gate repainted at once (slots painted, the cards navy), the swatch picked, the status bar navy",
          st["key"] == "midnight" and st["attr"] == "midnight" and st["style"] is None and st["n3"].startswith("#") and st["on"] == "midnight" and st["meta"] == "#0b1220", st)
    p.click('#looks [data-theme-id="aurora"]')
    p.wait_for_timeout(300)
    au = p.evaluate("""() => { const r = document.documentElement, c = getComputedStyle(document.querySelector('.g-card')), t = getComputedStyle(document.querySelector('.g-title'));
        return { style: r.dataset.olyStyle || null, page: getComputedStyle(r).backgroundImage.slice(0, 40), blur: c.backdropFilter || c.webkitBackdropFilter, radius: c.borderTopLeftRadius,
          weight: t.fontWeight, btn: getComputedStyle(document.getElementById('bringBack')).backgroundImage.slice(0, 30), sx: document.documentElement.scrollWidth - innerWidth }; }""")
    check("g. Glass Aurora (a style look): <html data-oly-style>, the aurora gradient page, frosted cards (blur, 24 px corners), bold titles, nothing spills sideways",
          au["style"] == "aurora" and "radial-gradient" in au["page"] and "blur" in str(au["blur"]) and au["radius"] == "24px" and au["weight"] == "700" and au["sx"] <= 0, au)
    p.click("#lookTab2")
    p.wait_for_timeout(200)
    mx = p.evaluate("""() => ({ combos: [...document.querySelectorAll('.g-combo')].map((b) => b.dataset.combo), rows: [...document.querySelectorAll('.g-mixrow .g-mixh b')].map((b) => b.textContent),
        minis: document.querySelectorAll('.g-mixrow')[0].querySelectorAll('.g-mini').length, one: document.getElementById('looks').hidden,
        h: Math.min(...[...document.querySelectorAll('.g-mini, .g-combo, #lookTab1, #lookTab2')].map((b) => b.getBoundingClientRect().height)) })""")
    check(f"g. Mix: three ready-made combos (Trader, Luxury, Clean), a row per hub (IA v2: the nine hubs + Me) and this Gate, each with 'Same' + the {len(PLAIN + STYLED)} looks; targets 44 px+",
          mx["combos"] == ["trader", "luxury", "clean"] and mx["rows"] == MIX_ROWS and mx["minis"] == 1 + len(PLAIN + STYLED) and mx["one"] and mx["h"] >= 44, mx)
    p.click('.g-combo[data-combo="trader"]')
    p.wait_for_timeout(250)
    m = p.evaluate("() => [JSON.parse(localStorage.getItem('olympus.themeMix') || 'null'), document.documentElement.dataset.olyTheme, document.querySelector('.g-combo[data-combo=\"trader\"]').getAttribute('aria-pressed')]")
    check("g. the Trader combo, per hub through its v1 district (Today / Bots / Research = Amber, Kalshi / Money = Stocks Light, Plan / Jarvis / Settings = Forest,"
          " Worlds = Glass Aurora), the app -> hub map (+ each hub page) from the catalog saved with it; the Gate keeps the one look",
          m[0] and m[0]["district"] == TRADER_HUBS and m[0]["of"].get("nq") == "bots" and m[0]["of"].get("mint") == "money" and m[0]["of"].get("hub-plan") == "plan"
          and m[1] == "aurora" and m[2] == "true", m)
    rows = p.locator(".g-mixrow")
    rows.nth(len(MIX_ROWS) - 1).locator('.g-mini[data-theme-id="forest"]').click()
    p.wait_for_timeout(250)
    gf = p.evaluate("() => [document.documentElement.dataset.olyTheme, JSON.parse(localStorage.getItem('olympus.themeMix')).app]")
    check("g. This Gate's own look (Forest) repaints the Gate at once and is kept as an app override", gf[0] == "forest" and gf[1].get("gate") == "forest", gf)
    p2 = ctx.new_page()
    looks = {}
    for app, q in (("nq", "?demo=1"), ("helios", "?demo=1"), ("mint", "?demo=1")):
        p2.goto(f"{origin}/{app}/{q}")
        p2.wait_for_function("() => document.documentElement.hasAttribute('data-oly-theme')", timeout=30000)
        p2.wait_for_timeout(400)
        looks[app] = p2.evaluate("() => [document.documentElement.dataset.olyTheme, document.documentElement.dataset.olyStyle || null, getComputedStyle(document.querySelector('h1')).textTransform]")
    check("g. the mix reaches the apps: NQ (Bots & Evals) and Helios (Today) open in Amber (its capitals), Mint (My Money) in Stocks Light",
          looks["nq"][:2] == ["amber", "amber"] and looks["nq"][2] == "uppercase" and looks["helios"][0] == "amber" and looks["mint"][0] == "stocks", looks)
    hubs = {}
    for hid in ("bots", "money", "plan", "worlds"):
        p2.goto(f"{origin}/hub/index.html?h={hid}")
        p2.wait_for_function("() => window.HUB && window.HUB.ready() && document.documentElement.hasAttribute('data-oly-theme')", timeout=30000)
        hubs[hid] = p2.evaluate("() => [document.documentElement.dataset.olyTheme, document.documentElement.dataset.olyPage, getComputedStyle(document.body).color]")
    check("g. ... and the hub pages (hub-<id>): Bots & Evals in Amber, My Money in Stocks Light, Plan & Day in Forest, Worlds in Glass Aurora",
          [hubs[h][0] for h in ("bots", "money", "plan", "worlds")] == ["amber", "stocks", "forest", "aurora"] and hubs["bots"][1] == "hub-bots", hubs)
    p.click("#lookTab1")
    p.click('#looks [data-theme-id="agora"]')
    p.wait_for_timeout(300)
    back = p.evaluate("""() => { const r = document.documentElement; return [localStorage.getItem('olympus.themeMix'), r.dataset.olyTheme, r.dataset.olyStyle || null,
        [...r.style].filter((k) => k.indexOf('--oly-th-') === 0).length]; }""")
    check("g. One look -> Agora: the mix cleared, the default back, no theme slot or style left painted", back == [None, "agora", None, 0], back)
    check("g. the Gate's Look row: no console error", not real(errs), real(errs)[:3])
    ctx.close()


LEFT_JS = os.path.join(ROOT, "tools", "theme_leftovers.js")
REACH = [("gate", "/gate/" + GATE_Q), ("dashboard", "/"), ("jarvis", "/jarvis/"), ("nq", "/nq/?demo=1"), ("helios", "/helios/?demo=1"), ("kalshi", "/kalshi/")]


def test_reach(br, origin):
    src = read(LEFT_JS)
    for theme in ("midnight", "terminal"):
        for name, path in REACH:
            ctx, p, errs = ctx_page(br, origin, theme)
            try:
                p.goto(origin + path)
                p.wait_for_function("() => document.documentElement.getAttribute('data-oly-theme') === %s" % json.dumps(theme), timeout=60000)
                p.wait_for_timeout(2500)
                left = p.evaluate("(a) => (" + src + ")(a)", {"max": 12})
                check(f"h. {name} under {theme}: no AGORA brown or gold left on screen (every card, bar, title and label follows the theme)", not left,
                      [f"{x['sel']} {x['prop']}={x['value']} <- {x['rule']}" for x in left[:5]])
            except Exception as e:
                check(f"h. {name} under {theme}: comes up themed", False, e)
            ctx.close()
    for theme in ("ivory", "stocks"):
        for name, path in REACH[:1] + REACH[3:5]:
            ctx, p, errs = ctx_page(br, origin, theme)
            try:
                p.goto(origin + path)
                p.wait_for_function("() => document.documentElement.getAttribute('data-oly-theme') === %s" % json.dumps(theme), timeout=60000)
                p.wait_for_timeout(1500)
                got = p.evaluate("""() => { const r = document.documentElement, c = (e) => getComputedStyle(e);
                    const h = document.querySelector('h1'), card = document.querySelector('.g-card, .ag-card');
                    return { scheme: r.dataset.olyScheme, cs: c(r).colorScheme, h1: c(h).color, card: c(card).backgroundColor, n3: c(r).getPropertyValue('--oly-th-n3').trim() }; }""")
                ok = got["scheme"] == "light" and lum(rgba(got["n3"])) > 0.7 and contrast(got["h1"], rgba(got["n3"])) >= 4.5
                check(f"h. {name} under {NAMES[theme]}: a light page (checked in light: data-oly-light / the Gate), its title AA on the page", ok, got)
            except Exception as e:
                check(f"h. {name} under {theme}: light", False, e)
            ctx.close()


def test_same_as_before(br):
    """the default (no key) on each page, served as-is and served with every theme slot replaced by its fallback (tools/theme_tokenize.py
    untokenize: the files as they were before the reach work): every element's computed colours, borders, shadows, fonts and radius are equal"""
    class Raw(Handler):
        def send_head(self):
            path = self.translate_path(self.path)
            if os.path.isdir(path):
                path = os.path.join(path, "index.html")
            if not path.endswith((".css", ".js", ".html")) or not os.path.isfile(path):
                return super().send_head()
            body = TOK.untokenize(open(path, encoding="utf-8").read()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            import io
            return io.BytesIO(body)
    raw = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Raw, directory=WEB))
    threading.Thread(target=raw.serve_forever, daemon=True).start()
    norm = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=WEB))
    threading.Thread(target=norm.serve_forever, daemon=True).start()
    o_raw, o_now = (f"http://127.0.0.1:{s.server_address[1]}" for s in (raw, norm))
    DUMPS = """() => { const P = ['color', 'background-color', 'background-image', 'border-top-color', 'border-bottom-color', 'border-top-left-radius', 'box-shadow', 'font-family', 'font-weight', 'text-transform', 'letter-spacing', 'outline-color', 'fill', 'stroke'];
        const out = []; for (const e of [document.documentElement, ...document.querySelectorAll('body, body *')]) { if (e.closest('svg') && e.tagName !== 'svg') continue; const cs = getComputedStyle(e);
          const own = [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.nodeValue).join('').trim().replace(/\\s+/g, ' ').replace(/[|]/g, '/').slice(0, 24);
          out.push(e.tagName + '.' + (typeof e.className === 'string' ? e.className : '') + '\\u0001' + own + '|' + P.map((k) => cs.getPropertyValue(k)).join('|')); } return out; }"""
    for name, path in (("gate", "/gate/" + GATE_Q), ("nq", "/nq/?demo=1"), ("helios", "/helios/?demo=1"), ("polis", "/polis/?demo=1"), ("kalshi", "/kalshi/"), ("dashboard", "/"), ("jarvis", "/jarvis/"),
                       ("hub", "/hub/index.html?h=money"), ("aegis", "/aegis/?demo=1"), ("mint", "/mint/?demo=1"), ("oikos", "/oikos/?demo=1"), ("ledger", "/ledger/?demo=1"),
                       ("planner", "/planner/?demo=1"), ("cities", "/cities/?demo=1"), ("symposium", "/symposium/?demo=1"), ("settings", "/settings/")):
        res = []
        for origin in (o_raw, o_now):
            ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block", reduced_motion="reduce")
            ctx.route("**/*", (lambda o: lambda r: r.continue_() if r.request.url.startswith(o) else r.abort())(origin))
            ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('olympus.theme.night', '1'); } catch (e) {}")
            if name == "jarvis":                 # Jarvis's AGORA look (Classic, the default since 2026-11-18, is its own violet palette, not the slots' AGORA literals)
                ctx.add_init_script("try { localStorage.setItem('jarvis.look', 'agora'); } catch (e) {}")
            p = ctx.new_page()
            p.set_default_timeout(90000)
            try:
                p.goto(origin + path, wait_until="domcontentloaded")
                p.wait_for_timeout(3500)
                res.append(p.evaluate(DUMPS))
            except Exception as e:
                res.append(["error: " + str(e)[:200]])
            ctx.close()
        def group(rows, own):                    # element kind (tag.class) [+ its own text] -> the set of computed looks it has
            g = {}
            for r in rows:
                k, _, v = r.partition("|")
                kind, _, txt = k.partition("\x01")
                g.setdefault((kind, txt) if own else kind, set()).add(v)
            return g
        ka, kb = group(res[0], False), group(res[1], False)
        both = [k for k in ka if k in kb]
        # each element against the same element on the other page (its kind and its own text): a card that arrives late on one page only (a page
        # that loads cards late differs in count) is no difference; elements without text of their own are compared by kind, as before
        ga, gb = group(res[0], True), group(res[1], True)
        diff = {k[0] + (" '" + k[1] + "'" if k[1] else ""): (sorted(ga[k] - gb[k])[:1], sorted(gb[k] - ga[k])[:1]) for k in ga if k in gb and ga[k] != gb[k]}
        check(f"c. {name}: on the default, every kind of element computes the same colours / borders / shadows / fonts / radius as the page with every slot replaced by its AGORA literal ({len(both)} kinds, {len(res[1])} elements)",
              len(both) > 20 and len(both) >= 0.9 * max(len(ka), len(kb)) and not diff, {"kinds": (len(ka), len(kb), len(both)), "diff": dict(list(diff.items())[:2])})
    raw.shutdown()
    norm.shutdown()


# ------------------------------------------------------------------ t2. lock down the looks (2026-11-14, team T2): no flash, every page, the picker, QA
FIRST_PAGES = [("gate/index.html", "('gate', 'page');"), ("hub/index.html", "(document.documentElement.getAttribute('data-oly-page') || 'hub', 'page');"),
               ("index.html", "('today', (function () {"), ("jarvis/index.html", "('jarvis', 'page');"), ("kalshi/index.html", "('kalshi', 'page');")]
LIGHT_APPS = ["nq", "helios", "aegis", "mint", "oikos", "ledger", "planner", "polis", "cities", "symposium"]


def test_t2_static(data):
    js = read(KIT, "themes.js")
    m = re.search(r"FIRST PAINT >>>\n(.*?)\n \* <<< FIRST PAINT", js, re.S)
    snip = m.group(1) if m else "?"
    bad = [p for p, call in FIRST_PAGES if snip + call not in read(WEB, p)]
    check("t2. the pages whose engine arrives after their first frame (the Gate, the hubs, the dashboard, Jarvis, Kalshi) carry themes.js's FIRST PAINT "
          "copy letter for letter, called with their page id: the look they get is on the first frame", m and not bad, bad)
    light = [a for a in LIGHT_APPS if "data-oly-light" not in read(WEB, a, "index.html").split(">", 2)[1]]
    check("t2. every app on the look QA matrix is checked in light (<html data-oly-light>): a light look is light on every page, not dark on half of them",
          not light, light)
    kal = read(WEB, "kalshi", "index.html")
    check("t2. Kalshi takes the full page palette (a light look is light there too) and its old token hook no longer clears the engine's data-oly-theme",
          "T.apply('page', { meta: true })" in kal and "e.newValue.charAt(0) !== '{'" in read(WEB, "kalshi", "kfx.js"))
    hs = read(KIT, "hero-stage.js")
    check("t2. the hero scenes (olympus/hero-stage.js: NQ, Aegis, Helios, Mint ...) lean their painted sky, fog and light toward the look (lean(), O.onTheme, back on the default)",
          "export function lean(pal, t)" in hs and "O.onTheme((t) => paintPal(lean(appSky, t)))" in hs and "olympus:theme-default" in hs)
    if not data:
        return
    low = {}
    for tid in PLAIN[1:] + STYLED + OLD[1:]:
        for where in ("page", "stage"):
            x = data["extras"][tid][where]
            surf = [x[k] for k in ("--oly-th-n3", "--oly-th-n4", "--oly-th-n5", "--oly-th-n7")]
            for k, need, on in (("--oly-th-infot", 4.5, surf), ("--oly-th-info", 3, surf[:2]), ("--oly-th-ring", 3, surf[:3])):
                v = min(contrast(x[k], s) for s in on)
                if v < need:
                    low[f"{tid}/{where} {k}"] = round(v, 2)
    check(f"t2. the extra slots read on every look ({len(PLAIN) - 1 + len(STYLED) + len(OLD) - 1} x page / stage): the info blue (text 4.5:1, fill 3:1) and the keyboard focus ring "
          "(3:1) on the page, the panels and the raised panels", not low, low)
    lightsh = [t for t in LIGHT if t != "athena" and "rgba(0, 0, 0, .35)" in data["extras"][t]["page"]["--oly-th-shadow"]]
    check("t2. a light look's shadows are soft and ink-tinted (--oly-th-shadow / --oly-th-e1..e3), never AGORA's black .35", not lightsh and all(
        data["extras"][t]["page"]["--oly-th-e1"] for t in LIGHT if t != "athena"), lightsh)
    t2 = data["t2"]
    key = lambda w, i: f"olympus.theme.look.{w}.{i}"     # noqa: E731
    check("t2. a pick writes the <head> copy of every look in use (page + stage): one look -> its two, a mix -> each of its looks + the one look, a new pick drops the rest, the default keeps none",
          t2["afterSet"] == [key("page", "midnight"), key("stage", "midnight")]
          and t2["afterMix"] == sorted(key(w, i) for w in ("page", "stage") for i in ("amber", "aurora", "midnight", "stocks"))
          and t2["afterOne"] == [key("page", "ivory"), key("stage", "ivory")] and t2["afterDefault"] == [], t2)
    check("t2. preview(id) shows a look on this page only (painted, nothing stored, no copy written) and preview(null) puts the chosen look back",
          t2["preview"] == ["carbon", "carbon", True, "ivory", True] and t2["previewEnd"] == [None, "ivory", True], (t2["preview"], t2["previewEnd"]))
    check("t2. noblur(true) (P2's cheap path): a frosted look keeps its cards, as one solid colour without the blur pass; off again, the frost is back",
          t2["noblur"][0] == "none" and re.fullmatch(r"#[0-9a-f]{6}", t2["noblur"][1] or "") and "blur(" in t2["blur"], t2)


def pick_on(p, origin, look, where="/hub/index.html?h=settings"):
    """the owner's way: OLYMPUS_THEMES.set on a page of the site (here a hub page, which loads the engine in its <head>)"""
    p.goto(origin + where, wait_until="load")
    p.wait_for_function("() => !!window.OLYMPUS_THEMES", timeout=30000)
    p.evaluate("(id) => window.OLYMPUS_THEMES.set(id)", look)


def look_page(br, origin, set_id, url, init="", size=(390, 844)):
    """a tab where the owner picked set_id, then opened url"""
    ctx = br.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=1, is_mobile=True, has_touch=True, service_workers="block", reduced_motion="reduce")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off');"
                        " localStorage.setItem('olympus.intro', 'off'); localStorage.setItem('olympus.theme.night', '1'); } catch (e) {}" + init)
    p = ctx.new_page()
    p.set_default_timeout(60000)
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    pick_on(p, origin, set_id)
    if url:
        p.goto(origin + url, wait_until="load")
    return ctx, p, errs


FIRST_JS = """(() => { const rec = window.__t2first = { first: null }; requestAnimationFrame(() => { const r = document.documentElement;
  rec.first = { theme: r.getAttribute('data-oly-theme'), bg: getComputedStyle(r).backgroundColor, body: document.body ? getComputedStyle(document.body).backgroundColor : '' }; }); })();"""


def test_night_default(br, origin):
    """OLYMPUS NIGHT (owner 2026-11-20): no key, or AGORA saved before the switch -> 'night', painted and saved once; a pick after it stays"""
    out = {}
    def dark(c):                                  # the page: black (the engine's darkest grid step, e.g. #040305)
        m = re.match(r"#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$", (c or "").strip().lower())
        return bool(m) and all(int(x, 16) <= 16 for x in m.groups())
    for case, init in (("empty", ""), ("agora before", "localStorage.setItem('olympus.theme', 'agora');"),
                       ("agora after", "localStorage.setItem('olympus.theme', 'agora'); localStorage.setItem('olympus.theme.night', '1');")):
        ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block", color_scheme="dark")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
        ctx.add_init_script("if (!sessionStorage.getItem('t.n')) { sessionStorage.setItem('t.n', '1'); try { localStorage.clear(); " + init + " } catch (e) {} }")
        p = ctx.new_page()
        p.goto(origin + "/ledger/", wait_until="load")
        p.wait_for_timeout(1500)
        out[case] = p.evaluate("() => [document.documentElement.getAttribute('data-oly-theme') || '', localStorage.getItem('olympus.theme'), getComputedStyle(document.documentElement).getPropertyValue('--ag-night').trim()]")
        ctx.close()
    ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block", color_scheme="dark")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script("if (!sessionStorage.getItem('t.n')) { sessionStorage.setItem('t.n', '1'); try { localStorage.clear(); } catch (e) {} }")
    p = ctx.new_page()
    p.goto(origin + "/jarvis/", wait_until="load")
    p.wait_for_timeout(2500)
    out["jarvis"] = p.evaluate("() => [document.documentElement.getAttribute('data-oly-theme') || '', localStorage.getItem('olympus.theme'), document.documentElement.getAttribute('data-jlook') || '']")
    ctx.close()
    # a light phone: every app has no light mode of its own, so night too (DESIGN QA 2026-11-21: it got AGORA's brown); only Zenith's Home steps aside
    ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block", color_scheme="light")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script("if (!sessionStorage.getItem('t.n')) { sessionStorage.setItem('t.n', '1'); try { localStorage.clear(); } catch (e) {} }")
    p = ctx.new_page()
    p.goto(origin + "/ledger/", wait_until="load")
    p.wait_for_timeout(1500)
    out["light"] = p.evaluate("() => document.documentElement.getAttribute('data-oly-theme') || ''")
    ctx.close()
    check("n. OLYMPUS NIGHT is the default look (painted, page black) but never saved as a choice; an AGORA saved before 2026-11-20 shows night too; "
          "an Agora picked after stays; the Jarvis page keeps the default, so Classic Jarvis stays on; a light phone gets night too on every app (only Zenith's Home, which has its own light mode, follows the phone)",
          out["empty"][:2] == ["night", None] and out["agora before"][:2] == ["night", "agora"] and dark(out["empty"][2])
          and out["agora after"][1] == "agora" and out["agora after"][0] in ("", "agora") and out["jarvis"][0] in ("", "agora") and out["jarvis"][1:] == [None, "classic"] and out["light"] == "night", out)


def test_first_frame(br, origin):
    """every page wears the look from its first frame, also right after the owner picked another one (the copy a page keeps of its last look is stale)"""
    for name, path in (("gate", "/gate/" + GATE_Q), ("hub", "/hub/index.html?h=money"), ("dashboard", "/"), ("jarvis", "/jarvis/"), ("kalshi", "/kalshi/"), ("nq", "/nq/?demo=1")):
        ctx, p, errs = look_page(br, origin, "ivory", path, FIRST_JS)
        try:
            p.wait_for_function("() => document.documentElement.getAttribute('data-oly-theme') === 'ivory'", timeout=30000)
            p.wait_for_timeout(500)                                     # the page keeps its copy of Ivory
            pick_on(p, origin, "midnight")                               # then the owner picks Midnight elsewhere
            p.goto(origin + path, wait_until="load")
            p.wait_for_function("() => document.documentElement.getAttribute('data-oly-theme') === 'midnight'", timeout=30000)
            first = p.evaluate("() => window.__t2first.first")
            check(f"t2. {name}: right after a new pick (Ivory -> Midnight) the very first frame already wears Midnight, not AGORA nor the look before",
                  first and first["theme"] == "midnight", first)
        except Exception as e:
            check(f"t2. {name}: first frame", False, e)
        ctx.close()


def test_picker(br, origin):
    ctx, p, errs = look_page(br, origin, "agora", "/gate/" + GATE_Q, size=(375, 812))
    try:
        gate_ready(p)
        p.evaluate("() => OLYMPUS_THEMES.set('midnight')")
        p.wait_for_timeout(300)
        now = p.evaluate("""() => { const n = document.getElementById('lookNow'); return { name: n && n.querySelector('b').textContent, on: [...document.querySelectorAll('#looks .g-sw .g-swon')].map((x) => x.parentNode.dataset.themeId),
            checked: [...document.querySelectorAll('#looks .g-sw[aria-checked="true"]')].map((x) => x.dataset.themeId), sx: document.documentElement.scrollWidth - innerWidth,
            small: [...document.querySelectorAll('#lookSec button, #lookSec input')].filter((b) => b.offsetParent && b.getBoundingClientRect().height < 44).map((b) => b.id || b.className) }; }""")
        check("t2. the picker at 375 px: the look on now in a card at the top (Midnight), its swatch marked 'On' and checked, every button and the search 44 px+, no sideways scroll",
              now["name"] == "Midnight" and now["on"] == ["midnight"] and now["checked"] == ["midnight"] and now["sx"] <= 0 and not now["small"], now)
        p.fill("#lookQ", "navy")
        p.wait_for_timeout(150)
        found = p.evaluate("() => [...document.querySelectorAll('#looks .g-sw')].map((b) => b.dataset.themeId)")
        p.fill("#lookQ", "zzzz")
        p.wait_for_timeout(150)
        none = p.evaluate("() => [document.querySelectorAll('#looks .g-sw').length, !!document.querySelector('#looks .g-lknone')]")
        p.fill("#lookQ", "")
        check("t2. search by name or mood: 'navy' finds Midnight and Royal; a word no look has says so (no empty grid)", "midnight" in found and "royal" in found and len(found) < 8 and none == [0, True], (found, none))
        p.dispatch_event('#looks .g-sw[data-theme-id="ivory"]', "pointerdown", {"pointerType": "touch", "button": 0, "isPrimary": True})
        p.wait_for_timeout(600)
        pv = p.evaluate("""() => ({ theme: document.documentElement.dataset.olyTheme, stored: localStorage.getItem('olympus.theme'), bar: !document.getElementById('lookBar').hidden,
            text: document.getElementById('lookBar').textContent, previewing: OLYMPUS_THEMES.previewing() })""")
        p.dispatch_event('#looks .g-sw[data-theme-id="ivory"]', "pointerup", {"pointerType": "touch", "button": 0, "isPrimary": True})
        check("t2. press and hold a swatch (Ivory): the page shows Ivory at once, nothing stored ('olympus.theme' still midnight), the bar at the thumb says it is a preview",
              pv["theme"] == "ivory" and pv["stored"] == "midnight" and pv["bar"] and "Preview: Ivory" in pv["text"] and pv["previewing"] == "ivory", pv)
        p.click("#lookBar .g-lkstar")
        p.wait_for_timeout(150)
        fav = p.evaluate("() => [JSON.parse(localStorage.getItem('olympus.theme.fav') || '[]'), [...document.querySelectorAll('#looks .g-lookg')].map((h) => h.textContent)[0]]")
        p.click("#lookUse")
        p.wait_for_timeout(250)
        used = p.evaluate("() => [localStorage.getItem('olympus.theme'), document.documentElement.dataset.olyTheme, document.getElementById('lookBar').hidden, OLYMPUS_THEMES.previewing()]")
        check("t2. the star keeps it in a Favourites row (first, this phone); Use it picks it for everything and closes the bar",
              fav[0] == ["ivory"] and fav[1] == "Favourites" and used == ["ivory", "ivory", True, None], (fav, used))
        p.click("#lookSurprise")
        p.wait_for_timeout(250)
        sp = p.evaluate("() => [OLYMPUS_THEMES.previewing(), localStorage.getItem('olympus.theme'), document.getElementById('lookBar').textContent]")
        p.click("#lookBar button:last-child")
        p.wait_for_timeout(200)
        back = p.evaluate("() => [OLYMPUS_THEMES.previewing(), document.documentElement.dataset.olyTheme, localStorage.getItem('olympus.theme')]")
        check("t2. Surprise me previews a look picked at random (never the one on now), with Another / Cancel; Cancel puts Ivory back, nothing stored",
              sp[0] and sp[0] != "ivory" and sp[1] == "ivory" and "Surprise:" in sp[2] and "Another" in sp[2] and back == [None, "ivory", "ivory"], (sp, back))
        p.evaluate("() => OLYMPUS_THEMES.set('agora')")
        check("t2. the picker: no console error", not real(errs), real(errs)[:3])
    except Exception as e:
        check("t2. the picker", False, e)
    ctx.close()


QA_SAMPLE = [("gate", "/gate/" + GATE_Q), ("hub-money", "/hub/index.html?h=money"), ("nq", "/nq/?demo=1"), ("mint", "/mint/?demo=1"), ("ledger", "/ledger/?demo=1"), ("kalshi", "/kalshi/")]
QA_LOOKS = ["midnight", "ivory", "aurora", "brutal"]


def test_look_qa(br, origin):
    """tools/theme_qa.js on a sample (6 pages x 4 looks, against the default), judged exactly as the matrix's table (theme_shots.look_issues): no
    AGORA colour left, no text under AA that the default does not have too, +$ green / -$ red, the status bar, a keyboard ring that shows.
    The whole matrix: tools/theme_shots.py --qa (docs/shots/themes_v2/qa.md)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import theme_shots as TS
    src = read(ROOT, "tools", "theme_qa.js")
    ag = TS.agora_palette()
    base = {}
    for look in ["agora"] + QA_LOOKS:
        ctx, p, errs = look_page(br, origin, look, None)
        for name, path in QA_SAMPLE:
            try:
                p.goto(origin + path, wait_until="load")
                p.wait_for_function("() => document.documentElement.hasAttribute('data-oly-theme')", timeout=30000)
                p.wait_for_timeout(1800)
                shot = os.path.join(SHOT_TMP, f"qa-{look}-{name}.png")
                rep = TS.measure(p, src, {"agora": ag if look != "agora" else [], "max": 20}, shot)
                fails, _ = TS.pixel_check(shot, rep["texts"], 390, 844)
                p.keyboard.press("Tab")
                ring = p.evaluate("() => window.__olyQA.focus()")
                res = {"view": "phone", "lowPx": fails, "lowBelow": [r for r in rep["low"] if r.get("top") is None and r["box"][1] >= 844 and not r.get("unsure")],
                       "left": rep["left"], "money": rep["money"], "focus": [ring] if ring else [], "canvases": rep.get("canvases") or [], "meta": rep["meta"], "sx": rep["sx"]}
                if look == "agora":
                    base[name] = res
                    continue
                iss = TS.look_issues(res, base.get(name, {}))
                check(f"t2. {look} on {name}: no AGORA colour left, no text under AA the default does not have too, +$ / -$ in green / red, the status bar follows, the focus ring shows (3:1)",
                      rep["theme"] == look and not iss, iss)
            except Exception as e:
                check(f"t2. {look} on {name}: QA", False, e)
        ctx.close()


SHOT_TMP = os.environ.get("OLY_QA_TMP") or os.path.join(__import__("tempfile").gettempdir(), "olympus_t2_qa")   # (a long TMPDIR breaks Chromium's sockets: never set TMPDIR for it)


def main():
    data = theme_data()
    test_static(data)
    test_contrast(data)
    test_slot_contrast(data)
    test_t2_static(data)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser tests skipped: no Playwright", True)
        return
    srv, origin = serve()
    shots = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
    only = [a for a in sys.argv[1:] if a in APPS or a in ("jarvis", "default", "zenith", "gate", "reach", "same", "first", "picker", "qa")]
    os.makedirs(SHOT_TMP, exist_ok=True)
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
        if not only or "gate" in only:
            test_gate_look(br, origin)
        if not only or "reach" in only:
            test_reach(br, origin)
        if not only or "same" in only:
            test_same_as_before(br)
        if not only or "first" in only:
            test_night_default(br, origin)
            test_first_frame(br, origin)
        if not only or "picker" in only:
            test_picker(br, origin)
        if not only or "qa" in only:
            test_look_qa(br, origin)
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
