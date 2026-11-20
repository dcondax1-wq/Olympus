"""OLYMPUS accessibility + usability sweep (day-a11y 2026-11-20). No paid service, no network: the local site, Chromium, axe-core
(vendored, MPL-2.0: tools/a11y/axe.min.js) and our own iPhone rules (tools/a11y/rules.js).

    python tools/a11y_sweep.py                          every visible app (the doors minus the Archive) + Jarvis, the Gate, the hubs
    python tools/a11y_sweep.py --apps compass,ledger    only these (ids as in APPS below)
    python tools/a11y_sweep.py --quick                  6 screens per app instead of the full 12 (faster, same rules)
    python tools/a11y_sweep.py --compare research/handoff/2026-11-20/olympus2/a11y/baseline.json
                                                        a before / after table against an earlier run (the lead's re-run after landing)
    options: --out DIR   (default scratch/a11y/<time>/: results.json + REPORT.md + issues_<team>.md)
             --workers N (default 2; each worker opens its own Chromium)   --no-lock (do not wait for /tmp/olympus_browser.lock)

The screens (full = 12 per app): 320x568, 390x844, 430x932  x  dark (AGORA) / light (Ivory)  x  reduced motion on / off.
Rules (the OLYMPUS BAR item 6), one category each, scored 0 issues = 1, 1-2 = 0.5, 3+ = 0, app score = the mean x 100:
    contrast   WCAG AA text contrast (axe color-contrast), dark and light
    names      every button / link / icon / image / frame has a name VoiceOver can read (axe *-name, image-alt, svg-img-alt ...)
    forms      every field has a label (axe label, select-name)
    headings   headings in order, one h1, none empty (axe heading-order, page-has-heading-one, empty-heading)
    zoom       pinch zoom not blocked (axe meta-viewport)
    structure  lang, title, lists, nested buttons, ARIA used right (the rest of axe wcag2a/aa)
    tap        tap targets >= 44 x 44 px
    text       body text >= 15 px (20+ characters), nothing under 12 px
    dyntype    text grows when the root font size grows 25 % (no fixed px text)  [390 px screens]
    hscroll    no sideways scroll at 320 / 390 / 430
    bottom     fixed bars clear the home indicator (env(safe-area-inset-bottom)) on viewport-fit=cover pages
    motion     with reduced motion on: no forever / long CSS animation, no 3D transform, no requestAnimationFrame loop
    color      a red / green money amount also carries a + / - sign or a word
    focus      tabbing shows a visible focus ring
"""
from __future__ import annotations

import argparse
import colorsys
import datetime
import json
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
AXE = os.path.join(ROOT, "tools", "a11y", "axe.min.js")
RULES = os.path.join(ROOT, "tools", "a11y", "rules.js")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

# who owns each app right now (the 2026-11-20 "olympus2" teams); an app nobody owns is ours (A11Y) to fix directly
OWNER = {
    "hub": "nav", "hub-zeus": "nav",
    "zenith": "design", "business": "design", "ledger": "design", "aegis": "design", "demeter": "design", "fates": "design", "hera": "design",
    "journal": "design", "helios": "design", "compass": "design", "kronos": "design", "pnyx": "design", "chrysos": "design", "mercury": "design",
    "oikos": "design", "planner": "design", "clio": "design", "settings": "design", "atlas": "design",
    "nq": "datatruth", "trading": "datatruth", "board": "datatruth",
    "jarvis": "jarvis",
    "gate": "home", "cities": "home", "widget": "home",
    "kalshi": "kalshi", "dionysus": "kalshi",
    "agency": "a11y", "inbox": "a11y", "tyche": "a11y",
}
EXTRA = [("jarvis", "jarvis/"), ("gate", "gate/"), ("hub", "hub/doors.html"), ("hub-zeus", "hub/zeus.html")]


def visible_apps() -> list:
    """[(id, url path)]: every app in a door that is not folded under Archive (olympus/doors.js), then Jarvis, the Gate and the hubs"""
    src = os.path.join(WEB, "olympus", "doors.js")
    js = "const d=require(%r);console.log(JSON.stringify({doors:d.DOORS.map(x=>x.ids),arch:d.ARCHIVE}))" % src
    try:
        out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30).stdout)
        ids = [i for door in out["doors"] for i in door if i not in out["arch"]]
    except Exception:
        ids = [k for k in OWNER if k not in dict(EXTRA)]
    apps = [(i, "index.html" if i == "zenith" else f"{i}/") for i in ids]
    return apps + [e for e in EXTRA if e[0] not in ids]


def screens(quick: bool) -> list:
    """[(name, w, h, theme, motion, what)]: what = 'full' (axe + every rule) or 'layout' (our layout rules + motion)"""
    out = []
    for w, h in ((390, 844), (320, 568), (430, 932)):
        for theme in ("dark", "light"):
            for mo in ("reduce", "no-preference"):
                full = (w == 390 and mo == "reduce")
                if quick and not (full or (w == 390 and theme == "dark") or (mo == "reduce" and (w == 320 or theme == "dark"))):
                    continue
                out.append((f"{w}-{theme}-{'rm' if mo == 'reduce' else 'motion'}", w, h, theme, mo, "full" if full else "layout"))
    return out


AXE_CAT = {
    "color-contrast": "contrast", "color-contrast-enhanced": None,
    "button-name": "names", "link-name": "names", "image-alt": "names", "input-button-name": "names", "input-image-alt": "names", "svg-img-alt": "names",
    "role-img-alt": "names", "frame-title": "names", "aria-command-name": "names", "aria-toggle-field-name": "names", "aria-meter-name": "names",
    "aria-progressbar-name": "names", "aria-tooltip-name": "names", "aria-dialog-name": "names", "object-alt": "names", "area-alt": "names",
    "summary-name": "names", "aria-treeitem-name": "names",
    "label": "forms", "select-name": "forms", "aria-input-field-name": "forms", "label-title-only": "forms",
    "heading-order": "headings", "page-has-heading-one": "headings", "empty-heading": "headings",
    "meta-viewport": "zoom", "meta-viewport-large": "zoom",
    "region": None, "landmark-one-main": None, "landmark-unique": None, "landmark-complementary-is-top-level": None, "landmark-no-duplicate-banner": None,
    "landmark-no-duplicate-contentinfo": None, "landmark-main-is-top-level": None, "landmark-banner-is-top-level": None, "landmark-contentinfo-is-top-level": None,
    "target-size": None,   # ours (44 px) is stricter than axe's 24 px
}
OWN_CAT = {"tap-target": "tap", "small-text": "text", "tiny-text": "text", "fixed-text": "dyntype", "h-scroll": "hscroll", "bottom-bar": "bottom",
           "motion": "motion", "color-only": "color", "no-focus": "focus"}
CATS = ["contrast", "names", "forms", "headings", "zoom", "structure", "tap", "text", "dyntype", "hscroll", "bottom", "motion", "color", "focus"]
CAT_WORDS = {"contrast": "text contrast (AA)", "names": "names for VoiceOver", "forms": "labelled fields", "headings": "headings in order",
             "zoom": "pinch zoom", "structure": "page structure / ARIA", "tap": "tap targets 44 px", "text": "text size 15 px", "dyntype": "Dynamic Type",
             "hscroll": "no sideways scroll", "bottom": "clear of the home bar", "motion": "reduced motion", "color": "not colour alone", "focus": "visible focus"}


# ------------------------------------------------------------------------------------------------ colour helpers (the exact contrast fix)
def _rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _lum(c):
    f = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]


def ratio(fg, bg):
    a, b = _lum(_rgb(fg)), _lum(_rgb(bg))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def fix_color(fg, bg, need=4.5):
    """the nearest colour to fg (same hue, lightness moved away from bg) that reaches `need` on bg; '' when it cannot"""
    try:
        r, g, b = _rgb(fg)
    except Exception:
        return ""
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    up = _lum(_rgb(bg)) < 0.18
    for i in range(1, 101):
        l2 = min(1, l + i / 100) if up else max(0, l - i / 100)
        c = "#%02x%02x%02x" % tuple(round(x * 255) for x in colorsys.hls_to_rgb(h, l2, s))
        if ratio(c, bg) >= need + 0.05:
            return c
    return ""


def fix_for(rule, it):
    """the exact CSS / HTML change for one issue (the source rule when we found it)"""
    src, d = it.get("src") or "", it.get("detail") or ""
    where = src.split(" { ")[0] if src else it["sel"]
    if rule == "color-contrast":
        m = re.search(r"(#[0-9a-f]{6}) on (#[0-9a-f]{6}).*need ([\d.]+)", d)
        if m:
            c = fix_color(m.group(1), m.group(2), float(m.group(3)))
            return f"`{where} {{ color: {c}; }}` ({m.group(1)} -> {c}: {ratio(c, m.group(2)):.2f}:1 on {m.group(2)})" if c else "raise the text colour or darken the fill"
    if rule == "tap-target":
        return f"`{where} {{ min-height: 2.75rem; min-width: 2.75rem; }}` (44 px; keep the look with padding, or grow the hit area with `::before {{ content:''; position:absolute; inset:-8px; }}` on a `position:relative` control)"
    if rule in ("small-text", "tiny-text"):
        return f"`{where} {{ font-size: 0.9375rem; }}` (15 px: body text on a phone; a short label of a few words may stay at 0.8125rem = 13 px)" if rule == "small-text" else f"`{where} {{ font-size: 0.75rem; }}` (12 px is the floor for any text)"
    if rule == "fixed-text":
        m = re.match(r"([\d.]+)px", d)
        rem = f"{float(m.group(1)) / 16:.4g}rem" if m else "a rem value"
        return f"`{where} {{ font-size: {rem}; }}` (was px: write the same size in rem so Dynamic Type grows it)"
    if rule == "h-scroll":
        return f"`{where} {{ max-width: 100%; min-width: 0; overflow-wrap: anywhere; }}` (or give the row its own `overflow-x: auto`)"
    if rule == "bottom-bar":
        return f"`{where} {{ padding-bottom: calc(<its padding> + env(safe-area-inset-bottom)); }}`"
    if rule == "motion":
        if it.get("sel") == "screen":
            return "stop the draw loop when `matchMedia('(prefers-reduced-motion: reduce)').matches`: draw one still frame, then redraw only on data change / tap"
        if "3D" in d:
            return f"`@media (prefers-reduced-motion: reduce) {{ {where} {{ transform: none; }} }}`"
        return f"`@media (prefers-reduced-motion: reduce) {{ {where} {{ animation: none; }} }}`"
    if rule == "color-only":
        return "write the sign and a word: `+$120 up` / `-$80 down` (keep the colour)"
    if rule == "no-focus":
        return f"`{where}:focus-visible {{ outline: 3px solid var(--oly-accent, #c8a24a); outline-offset: 2px; }}` (remove any `outline: none` on it)"
    if rule in ("button-name", "link-name", "aria-command-name", "input-button-name"):
        return "add `aria-label=\"<what it does>\"` (icon-only control), or visible text"
    if rule in ("image-alt", "svg-img-alt", "role-img-alt"):
        return "`alt=\"<what it shows>\"` (or `alt=\"\"` / `aria-hidden=\"true\"` when it is decoration)"
    if rule in ("label", "select-name", "aria-input-field-name"):
        return "wrap it in `<label>` with visible words, or `aria-label=\"...\"`"
    if rule == "heading-order":
        return "use the next level down (h1 > h2 > h3, no jumps); style it with a class, not by picking a smaller tag"
    if rule == "page-has-heading-one":
        return "make the page title an `<h1>` (one per page)"
    if rule == "empty-heading":
        return "put text in the heading (or `aria-hidden=\"true\"` on a decorative one)"
    if rule == "meta-viewport":
        return "`<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">` (drop user-scalable=no / maximum-scale)"
    if rule == "nested-interactive":
        return "do not put a button / link inside another one: make the outer a `<div>` and keep one control"
    return it.get("help") or "see the axe rule page"


# ------------------------------------------------------------------------------------------------ in the page
SRC_JS = r"""(args) => {            // the CSS rule that sets `prop` on the element: 'file :: selector { prop: value }'
  const [q, prop] = args; let el = null; try { el = document.querySelector(q); } catch (e) { return ''; }
  if (!el) return '';
  let best = '', bestSpec = -1;
  // the WINNING rule: highest specificity of the matching selector, the later one on a tie (:where() counts 0; :is/:not/:has count roughly)
  const spec = (sel) => { const t = sel.replace(/:where\((?:[^()]|\([^()]*\))*\)/g, '').replace(/::?[\w-]+\(/g, m => m.startsWith('::') ? ' ' : ' ');
    const ids = (t.match(/#[\w-]+/g) || []).length, cls = (t.match(/\.[\w-]+|\[[^\]]*\]|:(?!:)[\w-]+/g) || []).length,
      tags = (t.replace(/\[[^\]]*\]/g, '').match(/(^|[\s>+~(])[a-zA-Z][\w-]*/g) || []).length; return ids * 10000 + cls * 100 + tags; };
  const walk = (list, href) => { for (const r of list) { if (r.cssRules && !r.selectorText) { try { walk(r.cssRules, href); } catch (e) {} continue; }
    if (!r.selectorText || !r.style) continue; const v = r.style.getPropertyValue(prop); if (!v) continue;
    let sp = -1; for (const part of r.selectorText.split(/,(?![^(]*\))/)) { let ok = false; try { ok = el.matches(part); } catch (e) {} if (ok) sp = Math.max(sp, spec(part) + (r.style.getPropertyPriority(prop) ? 1e6 : 0)); }
    if (sp >= 0 && sp >= bestSpec) { bestSpec = sp; best = (href ? new URL(href).pathname.replace(/^\//, '') + (new URL(href).search) : 'inline <style>') + ' :: ' + r.selectorText.slice(0, 90) + ' { ' + prop + ': ' + v + ' }'; } } };
  for (const s of document.styleSheets) { try { walk(s.cssRules, s.href); } catch (e) {} }
  if (el.style && el.style.getPropertyValue(prop)) best = 'style="" :: ' + prop + ': ' + el.style.getPropertyValue(prop);
  return best;
}"""

FOCUS_JS = r"""() => {
  const el = document.activeElement; if (!el || el === document.body || el === document.documentElement) return null;
  const r = el.getBoundingClientRect(); if (!r.width || !r.height) return null;
  const st = (e) => { const s = getComputedStyle(e); return [s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 ? s.outlineStyle + s.outlineWidth + s.outlineColor : '', s.boxShadow, s.borderColor, s.backgroundColor, s.color, s.textDecorationLine].join('|'); };
  const on = st(el); el.blur(); const off = st(el);
  try { el.focus({ focusVisible: true }); } catch (e) { el.focus(); }
  return { sel: window.__olyA11y.sel(el), text: (el.getAttribute('aria-label') || el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 50), visible: on !== off };
}"""

INIT_JS = r"""(() => { let n = 0; const raf = window.requestAnimationFrame; window.__olyRaf = () => n;
  window.requestAnimationFrame = function (cb) { n++; return raf.call(window, cb); };
  try { localStorage.setItem('olympus.theme', '%s'); localStorage.setItem('olympus.theme.v', '2'); } catch (e) {} })();"""

AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]


def check_page(page, origin, path, scr) -> dict:
    name, w, h, theme, mo, what = scr
    res = {"screen": name, "issues": [], "error": ""}
    try:
        page.goto(f"{origin}/{path}", wait_until="load", timeout=45000)
    except Exception as e:  # noqa: BLE001
        res["error"] = f"load: {str(e)[:120]}"
        return res
    page.wait_for_timeout(1500)
    page.add_script_tag(path=RULES)
    r0 = page.evaluate("() => window.__olyRaf ? window.__olyRaf() : 0")
    page.wait_for_timeout(1000)
    raf = page.evaluate("() => window.__olyRaf ? window.__olyRaf() : 0") - r0
    out = page.evaluate("(o) => window.__olyA11y.run(o)", {"layout": True, "vw": w, "motion": mo == "reduce", "rafPerSec": 0, "color": what == "full"})
    res["meta"] = out["meta"]
    res["meta"]["raf"] = raf
    found = [(rule, it) for rule, items in out["rules"].items() for it in items]
    if mo == "reduce":
        moved = screen_moves(page)
        res["meta"]["moved"] = moved
        if moved >= 0.01:
            found.append(("motion", {"sel": "screen", "text": "still moving", "detail": f"{moved * 100:.0f}% of the screen changed in 1 s with reduced motion on"
                                     + (f" (a requestAnimationFrame loop draws {raf}/s)" if raf >= 20 else "")}))
    if what == "full":
        # Dynamic Type: the root font size x 1.25, which text did not grow
        page.evaluate("() => window.__olyA11y.snapshotSizes()")
        page.evaluate("() => { const d = document.documentElement; window.__olyRoot = d.style.getPropertyValue('font-size'); d.style.setProperty('font-size', (parseFloat(getComputedStyle(d).fontSize) * 1.25) + 'px', 'important'); }")
        page.wait_for_timeout(400)
        ft = page.evaluate("() => window.__olyA11y.fixedText(1.25)")
        page.evaluate("() => { const d = document.documentElement; d.style.removeProperty('font-size'); if (window.__olyRoot) d.style.setProperty('font-size', window.__olyRoot); }")
        res["meta"]["dyntype_checked"] = ft["checked"]
        found += [("fixed-text", it) for it in ft["fails"]]
        # axe
        try:
            page.add_script_tag(path=AXE)
            ax = page.evaluate("""(tags) => axe.run(document, { runOnly: { type: 'tag', values: tags }, resultTypes: ['violations'],
                rules: { region: { enabled: false }, 'target-size': { enabled: false } } }).then(r => r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help,
                nodes: v.nodes.slice(0, 25).map(n => ({ sel: n.target.join(' '), html: n.html.slice(0, 140), data: (n.any[0] || n.all[0] || n.none[0] || {}).data || null })) })))""", AXE_TAGS)
        except Exception as e:  # noqa: BLE001
            ax = []
            res["error"] = f"axe: {str(e)[:120]}"
        for v in ax:
            for n in v["nodes"]:
                d = ""
                dt = n.get("data") or {}
                if v["id"] == "color-contrast" and isinstance(dt, dict) and dt.get("fgColor"):
                    d = f"{dt['fgColor']} on {dt['bgColor']} = {dt.get('contrastRatio')}:1, need {str(dt.get('expectedContrastRatio', '4.5:1')).split(':')[0]} ({dt.get('fontSize')})"
                found.append((v["id"], {"sel": n["sel"], "text": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", n["html"])).strip()[:60], "detail": d, "help": v["help"], "html": n["html"]}))
        # focus: tab through up to 14 controls
        try:
            seen = set()
            for _ in range(14):
                page.keyboard.press("Tab")
                f = page.evaluate(FOCUS_JS)
                if not f or f["sel"] in seen:
                    continue
                seen.add(f["sel"])
                if not f["visible"]:
                    found.append(("no-focus", {"sel": f["sel"], "text": f["text"], "detail": "no visible change when focused by keyboard"}))
        except Exception:  # noqa: BLE001
            pass
    # the source CSS rule for the fixable ones
    prop = {"tap-target": "min-height", "small-text": "font-size", "tiny-text": "font-size", "fixed-text": "font-size", "color-contrast": "color", "bottom-bar": "bottom"}
    for rule, it in found:
        if rule in prop and it.get("sel") and not it["sel"].startswith(("window", "…")):
            try:
                it["src"] = page.evaluate(SRC_JS, [it["sel"], prop[rule]])
                if not it["src"] and rule == "tap-target":
                    it["src"] = page.evaluate(SRC_JS, [it["sel"], "height"]) or page.evaluate(SRC_JS, [it["sel"], "padding"])
            except Exception:  # noqa: BLE001
                pass
        it["rule"] = rule
        res["issues"].append(it)
    return res


def screen_moves(page) -> float:
    """the share of the screen's pixels that change over one second (reduced motion on: a still page is ~0; a ticking clock is far below 1 %)"""
    try:
        import io
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(io.BytesIO(page.screenshot(animations="allow"))).convert("RGB"), dtype=np.int16)
        page.wait_for_timeout(1000)
        b = np.asarray(Image.open(io.BytesIO(page.screenshot(animations="allow"))).convert("RGB"), dtype=np.int16)
        if a.shape != b.shape:
            return 0.0
        return float((np.abs(a - b).max(axis=2) > 16).mean())
    except Exception:  # noqa: BLE001
        return 0.0


def serve_site(AK, over):
    """the site on a local port (tests/agora_kit.py), with what-if files served under their real type (css / js / html)"""
    if not over:
        return AK.serve()
    import functools
    import http.server
    import mimetypes
    import threading

    class H(AK.Handler):
        overrides = {}

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in over:
                body = over[path]
                self.send_response(200)
                self.send_header("Content-Type", (mimetypes.guess_type(path)[0] or "text/plain") + "; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=AK.WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


_PW = {}


def _worker(job):
    """one app, every screen, in this worker's own Chromium"""
    app, path, origin, scrs = job
    from playwright.sync_api import sync_playwright
    if "br" not in _PW:
        _PW["pw"] = sync_playwright().start()
        try:
            import browser_kit as BK
            _PW["br"] = BK.launch(_PW["pw"])
        except Exception:  # noqa: BLE001
            _PW["br"] = _PW["pw"].chromium.launch(args=["--no-sandbox", "--enable-unsafe-swiftshader"])
    br, out = _PW["br"], []
    t0 = time.time()
    for scr in scrs:
        name, w, h, theme, mo, what = scr
        ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=True, has_touch=True, reduced_motion=mo,
                             color_scheme="light" if theme == "light" else "dark", service_workers="block")
        ctx.add_init_script(INIT_JS % ("ivory" if theme == "light" else "agora"))
        ctx.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())
        page = ctx.new_page()
        try:
            out.append(check_page(page, origin, path, scr))
        except Exception as e:  # noqa: BLE001
            out.append({"screen": name, "issues": [], "error": f"crash: {str(e)[:160]}"})
        finally:
            ctx.close()
    return app, path, out, round(time.time() - t0, 1)


# ------------------------------------------------------------------------------------------------ scoring + reports
def category(rule):
    if rule in OWN_CAT:
        return OWN_CAT[rule]
    if rule in AXE_CAT:
        return AXE_CAT[rule]
    return "structure"


def has_a11y_js(path) -> bool:
    """the page loads the kit's olympus/a11y.js: on a touch phone it scales ALL text (px too) by iOS text-size-adjust, so px text still grows there"""
    f = os.path.join(WEB, path + "index.html" if path.endswith("/") else path)
    try:
        return "olympus/a11y.js" in open(f, encoding="utf-8").read()
    except OSError:
        return False


def score_of(n, kit) -> int:
    """each rule 1 (clean) / 0.5 (1-2 issues) / 0 (3+), the mean x 100. Dynamic Type is not scored on a page with a11y.js (see has_a11y_js)"""
    cats = [c for c in CATS if not (kit and c == "dyntype")]
    return round(100 * sum(1.0 if n[c] == 0 else 0.5 if n[c] <= 2 else 0.0 for c in cats) / len(cats))


def summarise(app, path, per_screen):
    issues = {}
    errors = [f"{s['screen']}: {s['error']}" for s in per_screen if s.get("error")]
    for s in per_screen:
        for it in s["issues"]:
            cat = category(it["rule"])
            if not cat:
                continue
            key = (it["rule"], it["sel"])
            if key not in issues:
                issues[key] = dict(it, cat=cat, screens=[])
            if s["screen"] not in issues[key]["screens"]:
                issues[key]["screens"].append(s["screen"])
    n = {c: 0 for c in CATS}
    for it in issues.values():
        n[it["cat"]] += 1
    ran_full = any(s["screen"].startswith("390-") and s["screen"].endswith("-rm") and not s.get("error") for s in per_screen)
    kit = has_a11y_js(path)
    score = score_of(n, kit) if ran_full else 0
    rank = {"contrast": 0, "names": 1, "hscroll": 2, "tap": 3, "text": 4, "bottom": 5, "motion": 6, "forms": 7, "focus": 8, "dyntype": 9, "color": 10, "headings": 11, "zoom": 12, "structure": 13}
    lst = sorted(issues.values(), key=lambda x: (rank[x["cat"]], -len(x["screens"])))
    for it in lst:
        it["fix"] = fix_for(it["rule"], it)
    return {"path": path, "owner": OWNER.get(app, "a11y"), "score": score, "counts": n, "a11y_js": kit, "issues": lst, "errors": errors,
            "looks": {s["screen"]: [s.get("meta", {}).get(k) for k in ("theme", "scheme", "bg", "raf")] for s in per_screen},
            "raf": max([s.get("meta", {}).get("raf", 0) for s in per_screen] or [0])}


def md_escape(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def write_reports(out_dir, data):
    apps = data["apps"]
    L = [f"# OLYMPUS accessibility sweep ({data['when']}, commit {data['commit']})", "",
         f"`python tools/a11y_sweep.py{' --quick' if data['quick'] else ''}`: {len(apps)} pages x {data['screens']} screens "
         "(320 / 390 / 430 px, dark AGORA + light Ivory, reduced motion on + off), axe-core " + data["axe"] + " + our iPhone rules (tools/a11y/rules.js).",
         "Score = the 14 rules below, each 1 (clean) / 0.5 (1-2 issues) / 0 (3+), averaged x 100. An issue is one element failing one rule (on any screen).",
         "Dynamic Type in (brackets) = not scored: the page loads olympus/a11y.js, which on the iPhone grows px text too (iOS text-size-adjust); still worth moving to rem.", "",
         "| App | Team | Score | " + " | ".join(CATS) + " |", "|---|---|---|" + "---|" * len(CATS)]
    for app, a in sorted(apps.items(), key=lambda kv: kv[1]["score"]):
        L.append(f"| {app} | {a['owner']} | **{a['score']}** | " + " | ".join((f"({a['counts'][c]})" if c == "dyntype" and a.get("a11y_js") else str(a["counts"][c])) if a["counts"][c] else "." for c in CATS) + " |")
    avg = round(sum(a["score"] for a in apps.values()) / max(1, len(apps)))
    tot = {c: sum(a["counts"][c] for a in apps.values()) for c in CATS}
    L += ["", f"**Average {avg}.** Issues per rule over all pages: " + ", ".join(f"{CAT_WORDS[c]} {tot[c]}" for c in CATS if tot[c]) + ".", ""]
    L += ["## Per app: the top issues (exact element, rule, fix)", ""]
    for app, a in sorted(apps.items(), key=lambda kv: kv[1]["score"]):
        L += [f"### {app} (`{a['path']}`, team {a['owner']}): {a['score']}", ""]
        if a["errors"]:
            L.append("Errors: " + "; ".join(a["errors"][:3]))
        for it in a["issues"][:8]:
            L.append(f"- **{CAT_WORDS[it['cat']]}** (`{it['rule']}`) `{md_escape(it['sel'])[:110]}` \"{md_escape(it.get('text'))[:50]}\" {md_escape(it.get('detail'))} "
                     f"[{len(it['screens'])} screens] -> {md_escape(it['fix'])}" + (f" (source: `{md_escape(it['src'])}`)" if it.get("src") else ""))
        if len(a["issues"]) > 8:
            L.append(f"- ... {len(a['issues']) - 8} more in results.json")
        L.append("")
    with open(os.path.join(out_dir, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    # one raw list per team (the FOR_<team>.md files quote these)
    teams = sorted({a["owner"] for a in apps.values()})
    for t in teams:
        T = [f"# Every a11y issue for team {t} ({data['when']}, `python tools/a11y_sweep.py`)", ""]
        for app, a in sorted(apps.items(), key=lambda kv: kv[1]["score"]):
            if a["owner"] != t:
                continue
            T += [f"## {app} (`{a['path']}`): score {a['score']}", ""]
            for it in a["issues"]:
                T.append(f"- [{it['cat']}] `{it['rule']}` `{md_escape(it['sel'])[:140]}` \"{md_escape(it.get('text'))[:50]}\" {md_escape(it.get('detail'))} "
                         f"(screens: {', '.join(it['screens'][:4])}{'...' if len(it['screens']) > 4 else ''})"
                         + (f"\n  - source: `{md_escape(it['src'])}`" if it.get("src") else "") + f"\n  - fix: {md_escape(it['fix'])}")
            T.append("")
        with open(os.path.join(out_dir, f"issues_{t}.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(T) + "\n")
        F = [f"# The fix list for team {t} ({data['when']}, generated by `python tools/a11y_sweep.py`)", "",
             "One line per CSS rule to change (file:line, the apps it fixes), most important first, then the one-off elements. Dynamic Type lines are left out",
             "for pages that load olympus/a11y.js (px text grows there on the iPhone).", ""] + team_fixes(data, t)
        with open(os.path.join(out_dir, f"fixes_{t}.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(F) + "\n")


def locate(src, page=""):
    """'olympus/agora.css?v=a7 :: .ag-chip { min-height: 36px }' -> ('tools/web_public/olympus/agora.css', line) or (file, 0) / ('', 0)"""
    src = (src or "").replace("inline <style> :: ", (page or "index.html") + " :: ")
    m = re.match(r"([^ ]+?)(?:\?[^ ]*)? :: (.+?) \{ ([\w-]+): (.+) \}$", src)
    if not m:
        return "", 0
    f = os.path.join(WEB, m.group(1))
    if not os.path.isfile(f):
        return "", 0
    sel, prop = m.group(2).strip(), m.group(3)
    try:
        lines = open(f, encoding="utf-8").read().split("\n")
    except OSError:
        return "", 0
    first = sel.split(",")[0].strip()
    for i, ln in enumerate(lines):
        if first in ln and (prop in ln or "{" in ln):
            for j in range(i, min(i + 6, len(lines))):
                if prop + ":" in lines[j].replace(" :", ":") or "font:" in lines[j]:
                    return os.path.relpath(f, ROOT), j + 1
            return os.path.relpath(f, ROOT), i + 1
    return os.path.relpath(f, ROOT), 0


def team_fixes(data, team):
    """the fix list for one team: one line per CSS rule to change (file:line, every app and element it fixes), then the per-element ones"""
    by_src, rest = {}, []
    for app, a in data["apps"].items():
        if a["owner"] != team:
            continue
        for it in a["issues"]:
            if it["cat"] == "dyntype" and a.get("a11y_js"):
                continue
            if it.get("src") and " :: " in it["src"]:
                k = (it["rule"], it["src"])
                e = by_src.setdefault(k, {"apps": set(), "els": [], "it": it, "page": a["path"] + "index.html" if a["path"].endswith("/") else a["path"]})
                e["apps"].add(app)
                if len(e["els"]) < 2:
                    e["els"].append(f"{app}: \"{md_escape(it.get('text'))[:40]}\"")
            else:
                rest.append((app, it))
    rank = {c: i for i, c in enumerate(["contrast", "names", "hscroll", "tap", "bottom", "motion", "color", "focus", "forms", "text", "headings", "structure", "zoom", "dyntype"])}
    L = []
    for (rule, src), e in sorted(by_src.items(), key=lambda kv: (rank[kv[1]["it"]["cat"]], -len(kv[1]["apps"]))):
        f, ln = locate(src, e["page"])
        where = f"`{f}:{ln}`" if f and ln else f"`{src.split(' :: ')[0]}`"
        L.append(f"- [{e['it']['cat']}] {where} `{md_escape(src.split(' :: ', 1)[1])[:120]}` ({rule}; {', '.join(sorted(e['apps']))}; e.g. {'; '.join(e['els'])}) "
                 f"{md_escape(e['it'].get('detail'))[:70]}\n  - fix: {md_escape(e['it']['fix'])}")
    seen = set()
    for app, it in sorted(rest, key=lambda x: (rank[x[1]["cat"]], x[0])):
        k = (app, it["rule"], it["sel"][:40])
        if k in seen:
            continue
        seen.add(k)
        L.append(f"- [{it['cat']}] {app} `{md_escape(it['sel'])[:110]}` \"{md_escape(it.get('text'))[:40]}\" ({it['rule']}) {md_escape(it.get('detail'))[:80]}\n  - fix: {md_escape(it['fix'])}")
    return L


def compare(old_path, data):
    with open(old_path, encoding="utf-8") as fh:
        old = json.load(fh)
    L = [f"# Before / after: {old.get('when')} ({old.get('commit')}) -> {data['when']} ({data['commit']})", "",
         "| App | Before | After | Change | Issues before | Issues after |", "|---|---|---|---|---|---|"]
    for app in sorted(set(old["apps"]) | set(data["apps"])):
        a, b = old["apps"].get(app), data["apps"].get(app)
        if not a or not b:
            continue
        d = b["score"] - a["score"]
        L.append(f"| {app} | {a['score']} | {b['score']} | {'+' if d > 0 else ''}{d} | {len(a['issues'])} | {len(b['issues'])} |")
    sa = sum(a["score"] for a in old["apps"].values()) / max(1, len(old["apps"]))
    sb = sum(a["score"] for a in data["apps"].values()) / max(1, len(data["apps"]))
    L += ["", f"Average {sa:.0f} -> {sb:.0f}."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apps", default="")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--compare", default="")
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--override", action="append", default=[], help="SITE_PATH=LOCAL_FILE: serve a proposed file instead (what-if, nothing written)")
    ap.add_argument("--rescore", default="", help="rewrite the reports of an earlier results.json with the current scoring (no browser)")
    a = ap.parse_args(argv)
    if a.rescore:
        with open(a.rescore, encoding="utf-8") as fh:
            data = json.load(fh)
        for app, r in data["apps"].items():
            r["a11y_js"] = has_a11y_js(r["path"])
            r["score"] = score_of(r["counts"], r["a11y_js"])
        out_dir = a.out or os.path.dirname(os.path.abspath(a.rescore))
        with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        write_reports(out_dir, data)
        print(f"rescored: {out_dir}/REPORT.md")
        return 0
    apps = visible_apps()
    if a.apps:
        want = [x.strip() for x in a.apps.split(",") if x.strip()]
        apps = [x for x in apps if x[0] in want] + [(w, f"{w}/") for w in want if w not in [x[0] for x in apps] and os.path.isdir(os.path.join(WEB, w))]
    scrs = screens(a.quick)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    out_dir = a.out or os.path.join(ROOT, "scratch", "a11y", stamp)
    os.makedirs(out_dir, exist_ok=True)
    from tests import agora_kit as AK
    over = {}
    for spec in a.override:                 # --override olympus/agora.css=/tmp/agora.css : serve a proposed file in place of the real one (a what-if)
        site, local = spec.split("=", 1)
        with open(local, "rb") as fh:
            over["/" + site.lstrip("/")] = fh.read()
    srv, origin = serve_site(AK, over)
    import contextlib
    lock = contextlib.nullcontext()
    if not a.no_lock:
        try:
            import browser_lock
            lock = browser_lock.hold(browser_lock.DEFAULT, wait=2400)
        except Exception:  # noqa: BLE001
            pass
    t0 = time.time()
    results = {}
    print(f"a11y sweep: {len(apps)} pages x {len(scrs)} screens, {a.workers} workers -> {out_dir}", flush=True)
    with lock:
        jobs = [(app, path, origin, scrs) for app, path in apps]
        ctx = mp.get_context("fork")
        with ctx.Pool(max(1, a.workers)) as pool:
            for app, path, per, secs in pool.imap_unordered(_worker, jobs):
                results[app] = summarise(app, path, per)
                print(f"  {app:12s} score {results[app]['score']:3d}  issues {len(results[app]['issues']):3d}  {secs:5.0f}s"
                      + (f"  errors: {results[app]['errors'][0]}" if results[app]["errors"] else ""), flush=True)
    srv.shutdown()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    axe_v = re.search(r"axe v([\d.]+)", open(AXE, encoding="utf-8").read(200)).group(1)
    data = {"when": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "commit": commit, "quick": a.quick, "screens": len(scrs), "axe": axe_v,
            "seconds": round(time.time() - t0), "apps": results}
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    write_reports(out_dir, data)
    avg = round(sum(r["score"] for r in results.values()) / max(1, len(results)))
    print(f"done in {data['seconds']}s: average score {avg}. {out_dir}/REPORT.md")
    if a.compare:
        txt = compare(a.compare, data)
        with open(os.path.join(out_dir, "COMPARE.md"), "w", encoding="utf-8") as fh:
            fh.write(txt)
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
