"""OLYMPUS dashboard FX (tools/web_public/olympus/dashfx.js + dashfx.css, day-arenas 2026-11-20): the one-tag "3D + glow" layer for every
dashboard (glass / tilt / reveal / roll / spark / bar / bg + the chart helpers), palette OLYMPUS NIGHT.
  a. static: the files, the palette defaults (no brown / olive card colours; gold only as an accent), zero-specificity variables, the CSS
     holds every reserved size (bars), reduced motion turns every animation off, no WebGL, no permission request, the docs name every effect
  b. Chromium 390 x 844 on olympus/dashfx-lab.html (DFX_NO_BROWSER=1 skips): every effect wires; layout shift 0 over load + a full scroll;
     the rolled numbers end on their exact text; bars reach their value (gold class at 100%); the sparkline gets its glow + area; the
     background runs, stops when the tab is hidden and runs again; no long task over 50 ms that the page without dashfx does not have;
     frames under 8 ms; reduced motion: no canvas, no animation running, final numbers and bars at once; stop() leaves nothing; no error
    python -X utf8 -m tests.test_dashfx
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "tools" / "web_public"
OLY = WEB / "olympus"
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def static():
    js, css = (OLY / "dashfx.js").read_text(encoding="utf-8"), (OLY / "dashfx.css").read_text(encoding="utf-8")
    check("a. dashfx.js, dashfx.css and the lab exist", (OLY / "dashfx-lab.html").exists())
    pal = {"base": "#000000", "card-a": "#16131e", "card-b": "#020204", "warm": "#231d16", "line": "#3e255e", "line-2": "#462a6a", "line-3": "#4d2e76",
           "glow": "#9d59ee", "hi": "#dacbf0", "dim": "#483081", "gold": "#f1c14b", "gold-text": "#ebbf4f", "gold-muted": "#ac8a36", "good": "#77db89",
           "good-line": "#557b61", "bad": "#ef4444", "text": "#ebe9f1", "muted": "#898497"}
    miss = [k for k, v in pal.items() if f"--dfx-{k}: {v};" not in css or f"'{k}': '{v}'" not in js.replace(f"{k}: '{v}'", f"'{k}': '{v}'")]
    check("a. the OLYMPUS NIGHT palette is the default in the CSS variables and in the script's fallback (same values)", not miss, miss)
    check("a. the variables sit at zero specificity (a page's own --dfx-* always wins)", ":where(:root) {" in css)
    cards = re.findall(r'\[data-dfx~="glass"\] \{[^}]*\}', css)
    check("a. glass cards are near-black violet (no gold / brown / olive card background); gold only in the edge light",
          cards and "var(--dfx-card-a), var(--dfx-card-b)" in cards[0] and "gold" not in cards[0])
    check("a. the bar's track has its height in the CSS (from the first frame), the fill scales (transform), never its width",
          "height: var(--dfx-bar-h)" in css and "transform: scaleX(var(--dfx-v, 0))" in css and "width:" not in re.search(r"\.dfx-bar-fill \{[^}]*\}", css).group(0))
    rm = css[css.index("@media (prefers-reduced-motion: reduce)"):]
    check("a. reduced motion: the CSS stops the edge light, the tilt, the reveal and the bar transition; the script draws no background",
          all(k in rm for k in ("animation: none", "transform: none", "opacity: 1", "transition: none")) and "if (reduced() || saveData()) return;" in js)
    check("a. no WebGL, never asks for motion permission, 30 fps background with <= 60 dots and pixel ratio <= 1.5",
          "getContext('webgl" not in js and ".requestPermission(" not in js and "Math.min(60," in js and "Math.min(1.5," in js and "now - last < 33" in js)
    doc = (ROOT / "research" / "handoff" / "2026-11-20" / "fx" / "DASHFX_API.md")
    ds = (ROOT / "docs" / "DESIGN_SYSTEM.md").read_text(encoding="utf-8")
    words = ("glass", "tilt", "reveal", "roll", "spark", "bar", "bg", "chart.svg", "chart.canvas", "chart.lwc", "theme(", "stop(")
    check("a. documented: DASHFX_API.md names every effect and verb; DESIGN_SYSTEM.md has section 7",
          doc.exists() and all(w in doc.read_text(encoding="utf-8") for w in words) and "## 7. Dashboard FX (olympus/dashfx.js)" in ds)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


INIT = """window.__cls = 0; window.__long = [];
try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__long.push(Math.round(e.duration)); }).observe({ type: 'longtask', buffered: true }); } catch (e) {}"""


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("b. playwright is available", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(WEB)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/olympus/dashfx-lab.html"
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        def page(q="", **kw):
            ctx = b.new_context(viewport={"width": 390, "height": 844}, **kw)
            ctx.add_init_script(INIT)
            p = ctx.new_page()
            errs = []
            p.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
            p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
            p.goto(url + q, wait_until="load")
            return ctx, p, errs

        # baseline: the same page without dashfx
        ctx, p, _ = page("?nofx=1")
        p.wait_for_timeout(1500)
        base_long = max(p.evaluate("window.__long") or [0])
        ctx.close()

        ctx, p, errs = page()
        p.wait_for_timeout(2200)
        r = p.evaluate("""() => ({ s: OLYMPUS_DASHFX.stats(), canv: document.querySelectorAll('canvas.dfx-bg').length,
          idle: [...document.querySelectorAll('[data-dfx~="glass"]')].filter(e => e.classList.contains('dfx-idle')).map(e => e.id),
          pre: [...document.querySelectorAll('.dfx-pre')].map(e => e.id), spark: document.querySelectorAll('#spk [data-dfx-made]').length,
          bar1: getComputedStyle(document.getElementById('bar1')).getPropertyValue('--dfx-v').trim(), full: document.getElementById('bar2').classList.contains('dfx-full'),
          pnl: document.getElementById('pnl').textContent, room: document.getElementById('room').textContent, dd: document.getElementById('dd').textContent,
          aria: document.getElementById('bar1').getAttribute('aria-valuenow') })""")
        check("b. every effect wires: 15 elements, the background (aurora + dots canvases), the sparkline glow + area, below-the-fold sections waiting, off-screen glass paused",
              r["s"]["wired"] == 15 and r["canv"] == 2 and r["spark"] == 2 and set(r["pre"]) == {"r1", "r2"} and "r1" in r["idle"], r)
        check("b. the rolled numbers end on their exact text; the bars reach their value (gold at 100%), spoken as a %",
              r["pnl"] == "+$1,284.50" and r["room"] == "$1,860" and r["dd"] == "-$412" and r["bar1"] == "0.72" and r["full"] and r["aria"] == "72", r)
        # scroll through the page: the reveals rise in, the late roll lands exactly, nothing shifts
        for y in range(0, 2000, 300):
            p.evaluate(f"window.scrollTo(0, {y})")
            p.wait_for_timeout(120)
        p.wait_for_timeout(1500)
        s = p.evaluate("""() => ({ cls: +window.__cls.toFixed(4), pre: document.querySelectorAll('.dfx-pre').length, inn: document.querySelectorAll('.dfx-in').length,
          r1n: document.getElementById('r1n').textContent, bar3: getComputedStyle(document.getElementById('bar3')).getPropertyValue('--dfx-v').trim() })""")
        check(f"b. layout shift 0 over load + a full scroll (got {s['cls']}); the reveals rose in; the late number lands on '$9,999.99'",
              s["cls"] == 0 and s["pre"] == 0 and s["inn"] == 2 and s["r1n"] == "$9,999.99" and s["bar3"] == "0.35", s)
        # the background: hidden tab = no frames; visible again = frames again
        f0 = p.evaluate("OLYMPUS_DASHFX.stats().frames")
        p.evaluate("Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange'))")
        p.wait_for_timeout(300)
        f1 = p.evaluate("OLYMPUS_DASHFX.stats().frames")
        p.wait_for_timeout(700)
        f2 = p.evaluate("OLYMPUS_DASHFX.stats()")
        p.evaluate("Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange'))")
        p.wait_for_timeout(700)
        f3 = p.evaluate("OLYMPUS_DASHFX.stats()")
        check("b. the background stops while the tab is hidden and runs again when it is back; frames stay under 8 ms",
              f0 > 0 and f2["frames"] - f1 <= 1 and not f2["bgRunning"] and f3["frames"] > f2["frames"] and f3["bgRunning"] and f3["maxFrameMs"] < 8, (f0, f1, f2, f3))
        long_ = p.evaluate("window.__long") or []
        check(f"b. no long task over 50 ms from dashfx (with {max(long_ or [0])} ms vs without {base_long} ms)", max(long_ or [0]) <= max(50, base_long), long_)
        # tilt: a mouse over the hero leans it, leaving puts it back
        p.evaluate("window.scrollTo(0, 0)")
        p.wait_for_timeout(200)
        p.mouse.move(60, 160)
        p.mouse.move(300, 300, steps=4)
        p.wait_for_timeout(150)
        t1 = p.evaluate("getComputedStyle(document.getElementById('hero')).getPropertyValue('--dfx-ry').trim()")
        check("b. tilt: the pointer leans the card (transform only)", t1 not in ("", "0deg", "0.00deg"), t1)
        # stop(): nothing left
        left = p.evaluate("""() => { OLYMPUS_DASHFX.stop(); return { canv: document.querySelectorAll('canvas.dfx-bg').length, made: document.querySelectorAll('[data-dfx-made], .dfx-bar-fill').length,
          cls: document.querySelectorAll('.dfx-idle, .dfx-pre, .dfx-in, .dfx-anim, .dfx-full, .dfx-bg-host').length,
          vars: [...document.querySelectorAll('[data-dfx]')].filter(e => e.style.getPropertyValue('--dfx-v') || e.style.getPropertyValue('--dfx-rx') || e.style.minWidth).length,
          pnl: document.getElementById('pnl').textContent, stroke: document.querySelector('#spk path').getAttribute('stroke'), undo: OLYMPUS_DASHFX.stats().undo }; }""")
        p.wait_for_timeout(300)
        check("b. stop() leaves nothing (no canvas, made node, class, inline variable; the texts and the line as they were)",
              left == {"canv": 0, "made": 0, "cls": 0, "vars": 0, "pnl": "+$1,284.50", "stroke": None, "undo": 0}, left)
        check("b. no console or page error", not errs, errs[:4])
        ctx.close()

        # reduced motion
        ctx, p, errs = page(reduced_motion="reduce")
        p.wait_for_timeout(800)
        rm = p.evaluate("""() => ({ canv: document.querySelectorAll('canvas.dfx-bg').length, anim: document.getAnimations().filter(a => a.playState === 'running').length,
          pnl: document.getElementById('pnl').textContent, r1n: document.getElementById('r1n').textContent, pre: document.querySelectorAll('.dfx-pre').length,
          bar1: getComputedStyle(document.getElementById('bar1')).getPropertyValue('--dfx-v').trim(), rolls: OLYMPUS_DASHFX.stats().rolls })""")
        check("b. reduced motion: no background canvas, no animation running, final numbers and bars at once, nothing hidden",
              rm == {"canv": 0, "anim": 0, "pnl": "+$1,284.50", "r1n": "$9,999.99", "pre": 0, "bar1": "0.72", "rolls": 0} and not errs, (rm, errs[:2]))
        ctx.close()

        # the chart helpers' API
        ctx, p, errs = page()
        p.wait_for_timeout(500)
        api = p.evaluate("""() => { const o = OLYMPUS_DASHFX.chart.lwc(null); const t = OLYMPUS_DASHFX.theme({ glow: '#123456', nope: '#fff', gold: 'red' });
          const back = OLYMPUS_DASHFX.theme({ glow: '#9d59ee' }); return { lwc: [o.lineColor, o.topColor, o.bottomColor, o.lineWidth], glow: t.glow, gold: t.gold, back: back.glow }; }""")
        check("b. chart.lwc gives lightweight-charts options in the palette; theme() sets valid colours only and can be put back",
              api == {"lwc": ["#9d59ee", "rgba(157,89,238,0.38)", "rgba(157,89,238,0)", 2], "glow": "#123456", "gold": "#f1c14b", "back": "#9d59ee"} and not errs, (api, errs[:2]))
        ctx.close()
        b.close()
    srv.shutdown()


def main():
    static()
    if os.environ.get("DFX_NO_BROWSER") != "1":
        browser()
    print(f"dashfx: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
