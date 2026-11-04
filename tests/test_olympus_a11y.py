"""OLYMPUS accessibility + readability layer (2026-11-04, docs/OLYMPUS_A11Y.md): tools/web_public/olympus/a11y.js + a11y.css.
  a. static: both files exist; a11y.js is a classic ES5 script (no arrow, let / const, template string, optional chaining, import), no network,
     sets window.OLYMPUS_A11Y once, honours data-oly-skip; a11y.css has the focus ring, reduced motion, more contrast and big text rules and
     nothing Safari 16 cannot read (no nesting, color-mix, :has)
  b. ink: every theme's text / muted ink / accents / ok / bad / warn reach 4.5:1 on its own background (page and stage palettes), and the
     muted ink tokens of the app stylesheets (--dim / --muted / --faint ...) do too (Jarvis's and Kalshi's --dim are fills, listed)
  c. Chromium 390 x 844, jfx=off, on olympus/a11y-demo.html: icon-only buttons get an aria-label (glyph, class words, explicit data-oly-label),
     data-oly-skip and named / worded buttons are left alone, an unnamed one is reported; a placeholder names its field; a button added later is
     named; toasts get role=status / aria-live=polite (errors role=alert); big text toggles 16 -> 20 px, is kept on this phone and survives
     a reload; a button with outline: none still shows a 3 px ring on keyboard focus; reduced motion stops the loop; more contrast lifts the
     ink; a weak --oly-dim is lifted to 4.5:1; the page never grows sideways at big text; no page error
    python -X utf8 -m tests.test_olympus_a11y
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------------ colours (WCAG 2.x)
def col(s):
    s = s.strip()
    m = re.match(r"^#([0-9a-f]{3,8})\b", s, re.I)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255 if len(h) == 8 else 1]
    m = re.match(r"^rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?", s)
    if m:
        a = m.group(4)
        a = 1 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return [float(m.group(1)), float(m.group(2)), float(m.group(3)), a]
    return None


def over(fg, bg):
    return [fg[i] * fg[3] + bg[i] * (1 - fg[3]) for i in range(3)] + [1]


def lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])


def ratio(fg, bg):
    f = over(col(fg), over(col(bg), [0, 0, 0, 1])) if isinstance(fg, str) else fg
    b = over(col(bg), [0, 0, 0, 1])
    x, y = lum(f), lum(b)
    return (max(x, y) + .05) / (min(x, y) + .05)


# ------------------------------------------------------------------------------------------------------ a. static
def test_static():
    js, css = os.path.join(KIT, "a11y.js"), os.path.join(KIT, "a11y.css")
    check("a. a11y.js, a11y.css and the demo page exist", all(os.path.isfile(p) for p in (js, css, os.path.join(KIT, "a11y-demo.html"))))
    src = read(js)
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", code)
    check("a. a11y.js is a classic ES5 script: no arrow function, let / const, template string, optional chaining, spread, import / export, no network call",
          not re.search(r"=>|\blet\s|\bconst\s|`|\?\.[\w(\[]|\.\.\.|^\s*(import|export)\s|\bfetch\(|XMLHttpRequest|\basync\b|\bclass\s+\w", code, re.M), re.findall(r"=>|\blet\s|\bconst\s|`", code)[:4])
    check("a. a11y.js sets window.OLYMPUS_A11Y once (a second include does nothing), never throws out of its start, honours data-oly-skip and keeps a saved choice 'olympus.a11y'",
          "if (window.OLYMPUS_A11Y) return;" in src and "window.OLYMPUS_A11Y = api" in src and "data-oly-skip" in src and "'olympus.a11y'" in src and src.count("try {") >= 10)
    c = read(css)
    check("a. a11y.css: the focus ring, reduced motion, more contrast, big text and the skip opt-out are there",
          "focus-visible" in c and "prefers-reduced-motion" in c and "prefers-contrast: more" in c and 'data-oly-text="big"' in c and "data-oly-skip" in c and "data-oly-motion" in c)
    check("a. a11y.css is Safari 16 safe: no nesting, color-mix, :has, @container", not re.search(r"(?m)^\s*&\s*[.:#\[]|color-mix\(|:has\(|@container", c))
    th = read(os.path.join(KIT, "themes.js"))
    check("a. the kit's own CSS and script are untouched by the layer (a11y.css is a new file; olympus.css has no a11y rule of its own to collide)", "a11y" not in read(os.path.join(KIT, "olympus.css")))
    return th


# ------------------------------------------------------------------------------------------------------ b. ink
CONTRAST_JS = r"""
const vm = require('vm'), fs = require('fs');
const ls = {}, st = { setProperty() {}, removeProperty() {} };
const doc = { documentElement: { style: st, setAttribute() {}, removeAttribute() {}, getAttribute() { return null; }, dataset: {} }, querySelector() { return null; }, addEventListener() {}, head: { appendChild() {} }, createElement() { return { style: {}, setAttribute() {} }; } };
const win = { localStorage: { getItem: (k) => ls[k] || null, setItem() {}, removeItem() {} }, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }), document: doc };
win.window = win; win.self = win; vm.createContext(win); vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), win);
const T = win.OLYMPUS_THEMES, out = [];
for (const th of T.list()) for (const where of ['page', 'stage']) { const tk = T.tokens(th.id, where); if (tk) out.push({ id: th.id, where, tk: { bg: tk.bg, bg2: tk.bg2, glass: tk.glass, text: tk.text, dim: tk.dim, accent: tk.accent, accent2: tk.accent2, ok: tk.ok, bad: tk.bad, warn: tk.warn } }); }
for (const th of T.list()) if (th.jarvis) out.push({ id: th.id, where: 'jarvis', tk: { bg: th.jarvis.bg, pr: 'rgb(' + th.jarvis.pr + ')', txt: th.jarvis.txt, mut: th.jarvis.mut, c: th.jarvis.c, c3: th.jarvis.c3 } });
console.log(JSON.stringify(out));
"""
# --dim of these sheets is a dark fill / border colour, not text ink
NOT_INK = {("jarvis/jarvis.css", "--dim"), ("jarvis/core-demo.html", "--dim"), ("kalshi/kalshi.css", "--dim")}
INK = re.compile(r"^(mut|muted|dim|dim-text|sub|subtle|faint|soft|ink2|ink-2|txt2|text2|tx2|mute|label|lbl|fg2|fg-dim|txt-dim)$")
BGN = ("bg", "bg0", "bg1", "bg2", "back", "surface", "panel", "pr")


def test_ink():
    node = shutil.which("node")
    if node:
        d = tempfile.mkdtemp(prefix="a11yink_")
        try:
            with open(os.path.join(d, "c.js"), "w", encoding="utf-8") as fh:
                fh.write(CONTRAST_JS)
            r = subprocess.run([node, os.path.join(d, "c.js"), os.path.join(KIT, "themes.js")], capture_output=True, text=True, timeout=60)
            rows = json.loads(r.stdout.strip().splitlines()[-1])
        finally:
            shutil.rmtree(d, ignore_errors=True)
        bad, n = [], 0
        for row in rows:
            tk = row["tk"]
            bg = tk["bg"]
            for k, v in tk.items():
                if k in ("bg", "bg2", "pr", "glass"):
                    continue
                n += 1
                on = tk["glass"] if k in ("text", "dim") and row["where"] != "jarvis" and "glass" in tk else bg
                for base in {bg, on}:
                    if not col(v) or not col(base):
                        continue
                    base_c = over(col(base), over(col(bg), [0, 0, 0, 1]))
                    rr = ratio(over(col(v), base_c), "rgb(%d,%d,%d)" % tuple(base_c[:3]))
                    if rr < 4.5:
                        bad.append((row["id"], row["where"], k, round(rr, 2)))
        check(f"b. every theme's text, muted ink, accents, ok / bad / warn reach 4.5:1 on their background (page, stage and Jarvis palettes: {n} pairs)", not bad, bad[:8])
    else:
        check("b. theme ink audit skipped: node not found", True)
    low = []
    for f in sorted(glob.glob(WEB + "/**/*.css", recursive=True) + glob.glob(WEB + "/**/*.html", recursive=True)):
        rel = os.path.relpath(f, WEB).replace(os.sep, "/")
        if re.search(r"icon_options|three-addons|(^|/)fx/|render-lab|sfx-lab|fx-lab", rel):
            continue
        t = read(f)
        for m in re.finditer(r"((?::root|html|body)[^{]*)\{([^}]*)\}", t):
            vars_ = {k.lower(): v.strip() for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", m.group(2))}
            bg = None
            for k, v in vars_.items():
                if re.sub(r"^(oly-|c-)", "", k) in BGN and col(v) and col(v)[3] > .9:
                    bg = v
                    break
            if not bg:
                continue
            for k, v in vars_.items():
                nm = re.sub(r"^(oly-|c-)", "", k)
                if INK.match(nm) and (rel, "--" + k) not in NOT_INK and col(v):
                    if ratio(over(col(v), col(bg)), bg) < 4.5:
                        low.append((rel, "--" + k, v[:26], round(ratio(over(col(v), col(bg)), bg), 2)))
    check("b. the muted ink tokens of the app stylesheets (--dim / --muted / --faint ...) are at least 4.5:1 on their own background", not low, low[:8])


# ------------------------------------------------------------------------------------------------------ c. Chromium
def test_browser():
    from playwright.sync_api import sync_playwright
    from tests.test_olympus_kit import launch, serve
    srv, origin = serve()
    url = origin + "/olympus/a11y-demo.html"
    with sync_playwright() as pw:
        br = launch(pw)

        def new(reduced=False, saved=None):
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, reduced_motion="reduce" if reduced else "no-preference")
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
            init = "try { localStorage.setItem('jfx', 'off'); } catch (e) {}"
            ctx.add_init_script(init)
            p = ctx.new_page()
            errs: list = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url)
            p.wait_for_function("() => window.OLYMPUS_A11Y && document.documentElement.dataset.olyA11y === 'on'", timeout=60000)
            p.wait_for_timeout(300)
            return ctx, p, errs

        ctx, p, errs = new()
        names = p.evaluate("""() => { const g = (id) => document.getElementById(id).getAttribute('aria-label'); return { close: g('close'), gear: g('gear'), srch: g('srch'), own: g('own'), skip: g('skipme'), named: g('named'),
          words: g('words'), mystery: g('mystery'), field: g('field'), un: window.OLYMPUS_A11Y.unlabeled.map((e) => e.id) }; }""")
        check("c. icon-only buttons are named: x -> Close, the gear -> Settings, the search class -> Search, an explicit data-oly-label wins",
              names["close"] == "Close" and names["gear"] == "Settings" and names["srch"] == "Search" and names["own"] == "Open the chart", names)
        check("c. data-oly-skip, a title and visible words are left alone; a field takes its placeholder; an unnameable button is reported (not invented)",
              names["skip"] is None and names["named"] is None and names["words"] is None and names["field"] == "Search the notes" and names["un"] == ["mystery"] and names["mystery"] is None, names)
        p.evaluate("() => { const b = document.createElement('button'); b.className = 'back'; b.id = 'late'; b.textContent = '\\u2190'; document.body.appendChild(b); }")
        p.wait_for_function("() => document.getElementById('late').getAttribute('aria-label') === 'Back'", timeout=10000)
        check("c. a button added later is named by the observer (back arrow -> Back)", True)
        live = p.evaluate("() => { const a = document.getElementById('toast'), b = document.getElementById('etoast'); return [a.getAttribute('role'), a.getAttribute('aria-live'), b.getAttribute('role'), b.getAttribute('aria-live'), b.getAttribute('aria-atomic')]; }")
        check("c. toasts are live regions: status + polite, an error toast alert + assertive", live == ["status", "polite", "alert", "assertive", "true"], live)

        f0 = p.evaluate("() => [parseFloat(getComputedStyle(document.documentElement).fontSize), parseFloat(getComputedStyle(document.getElementById('rem')).fontSize), window.OLYMPUS_A11Y.scale()]")
        p.evaluate("() => document.getElementById('big').click()")
        f1 = p.evaluate("() => [parseFloat(getComputedStyle(document.documentElement).fontSize), parseFloat(getComputedStyle(document.getElementById('rem')).fontSize), document.documentElement.dataset.olyText,"
                        " document.getElementById('big').getAttribute('aria-pressed'), localStorage.getItem('olympus.a11y'), document.documentElement.scrollWidth <= innerWidth]")
        check("c. big text: the rem text grows 16 -> 20 px (x1.25), the choice is kept on the phone, the toggle says aria-pressed, the page does not grow sideways",
              f0[:2] == [16, 16] and f0[2] == 1 and f1[:2] == [20, 20] and f1[2] == "big" and f1[3] == "true" and '"text":"big"' in f1[4] and f1[5] is True, (f0, f1))
        p.reload()
        p.wait_for_function("() => window.OLYMPUS_A11Y && document.documentElement.dataset.olyA11y === 'on'", timeout=60000)
        f2 = p.evaluate("() => [parseFloat(getComputedStyle(document.getElementById('rem')).fontSize), document.documentElement.dataset.olyText]")
        p.evaluate("() => document.getElementById('big').click()")
        f3 = p.evaluate("() => parseFloat(getComputedStyle(document.getElementById('rem')).fontSize)")
        check("c. big text survives a reload and the toggle turns it back to 16 px", f2 == [20, "big"] and f3 == 16, (f2, f3))

        # keyboard focus on a button the page styled with outline: none
        p.evaluate("() => document.getElementById('close').focus()")
        p.keyboard.press("Tab")
        p.keyboard.press("Shift+Tab")
        ring = p.evaluate("() => { const e = document.activeElement, c = getComputedStyle(e); return [e.id, c.outlineStyle, c.outlineWidth]; }")
        check("c. keyboard focus shows a 3 px solid ring even on a button that said outline: none", ring[0] == "close" and ring[1] == "solid" and ring[2] == "3px", ring)

        # the muted ink guard and more contrast
        ink = p.evaluate("""() => { const r = document.documentElement; r.style.setProperty('--oly-dim', 'rgba(214, 220, 236, .22)'); window.OLYMPUS_A11Y.set({});
          const cs = getComputedStyle(r); return [window.OLYMPUS_A11Y.ink(cs.getPropertyValue('--oly-bg'), cs.getPropertyValue('--oly-dim')), cs.getPropertyValue('--oly-dim').trim()]; }""")
        check("c. a muted ink weaker than 4.5:1 (--oly-dim at .22 alpha) is lifted to at least 4.5:1", ink[0] >= 4.5, ink)
        p.evaluate("() => document.getElementById('hc').click()")
        hc = p.evaluate("() => { const cs = getComputedStyle(document.documentElement); return [document.documentElement.dataset.olyContrast, cs.getPropertyValue('--oly-dim').trim(), cs.getPropertyValue('--oly-text').trim()]; }")
        check("c. the more-contrast toggle makes the muted ink the full text colour", hc[0] == "more" and hc[1] == hc[2] and hc[1] != "", hc)
        check("c. no page error", not errs, errs[:3])
        ctx.close()

        # a desktop browser (no touch): the root font size does the growing
        ctx = br.new_context(viewport={"width": 900, "height": 700})
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
        p = ctx.new_page()
        p.goto(url)
        p.wait_for_function("() => window.OLYMPUS_A11Y && document.documentElement.dataset.olyA11y === 'on'", timeout=60000)
        p.evaluate("() => window.OLYMPUS_A11Y.toggleBig()")
        dk = p.evaluate("() => [parseFloat(getComputedStyle(document.documentElement).fontSize), parseFloat(getComputedStyle(document.getElementById('rem')).fontSize), document.documentElement.style.fontSize]")
        check("c. without touch the root font size does the growing (rem text 16 -> 20 px, once, never doubled by text-size-adjust)", dk[:2] == [20, 20] and dk[2] in ("20px", "20.00px"), dk)
        ctx.close()

        ctx, p, errs = new(reduced=True)
        rm = p.evaluate("() => { const c = getComputedStyle(document.getElementById('spin')); return [document.documentElement.dataset.olyMotion, c.animationDuration, c.animationIterationCount]; }")
        ctx.close()
        ctx, p, errs = new(reduced=False)
        nm = p.evaluate("() => { const c = getComputedStyle(document.getElementById('spin')); return [document.documentElement.dataset.olyMotion || '', c.animationDuration, c.animationIterationCount]; }")
        p.evaluate("() => window.OLYMPUS_A11Y.set({ motion: 'reduce' })")
        mo = p.evaluate("() => { const c = getComputedStyle(document.getElementById('spin')); return [document.documentElement.dataset.olyMotion, c.animationDuration, c.animationIterationCount]; }")
        check("c. reduced motion (the phone's setting, or the choice) stops the loop: 0.001 s, once; without it the spinner runs (1 s, infinite)",
              rm[0] == "reduce" and rm[1] == "0.001s" and rm[2] == "1" and nm == ["", "1s", "infinite"] and mo[0] == "reduce" and mo[1] == "0.001s", (rm, nm, mo))
        ctx.close()
        br.close()
    srv.shutdown()


def main():
    test_static()
    test_ink()
    if "--static" not in sys.argv:
        test_browser()
    n = sum(RES)
    print(f"\nolympus a11y: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    sys.exit(0 if n == len(RES) else 1)


if __name__ == "__main__":
    main()
