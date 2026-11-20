"""OLYMPUS NQ FX (tools/web_public/olympus/nqfx.js + nqvault3d.js, day-arenas 2026-11-20): the trading dashboard's effects on the kit's
FX library: win / loss / milestone moments, the goal ring, the number roll-up, the chart light trail, the 3D payout vault.
  a. static: the files, the vault module imports only local files (three r160 from jarvis/, RoomEnvironment), the API is documented
     (docs/DESIGN_SYSTEM.md section 6 + research/handoff/2026-11-20/nq4/FX_API.md), the lab page exists
  b. Chromium at 390 x 844 on the lab page (NQ_NO_BROWSER=1 skips): the vault is drawn first and turns 3D after load + idle, set() moves
     it, the trail follows a redrawn line, the moments fire toasts, stop() leaves nothing (no canvas, node, ticker); no long task > 200 ms
     before the 3D import; tier low = pixel ratio 1; reduced motion = no 3D, no moving trail, the ring and number still; no WebGL = the
     drawn vault; no console or page error
    python -X utf8 -m tests.test_nqfx
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
    files = [OLY / "nqfx.js", OLY / "nqvault3d.js", OLY / "nqfx-lab.html"]
    check("a. nqfx.js, nqvault3d.js and the lab page exist", all(f.exists() for f in files), [str(f) for f in files if not f.exists()])
    imp = re.findall(r"""^\s*import\s[^'"]*['"]([^'"]+)['"]""", (OLY / "nqvault3d.js").read_text(encoding="utf-8"), re.M)
    check("a. the vault module imports only local files (three r160 from jarvis/, RoomEnvironment)",
          set(imp) == {"../jarvis/three.module.min.js", "./three-addons/RoomEnvironment.js"}, imp)
    js = (OLY / "nqfx.js").read_text(encoding="utf-8")
    check("a. nqfx.js: classic script on fx-core (defines chartTrail + payoutVault with a still version), the 3D after load + idle, never with no WebGL / weak line",
          "FX.define('chartTrail'" in js and "FX.define('payoutVault'" in js and js.count("still: function") == 2 and "requestIdleCallback" in js
          and "WebGLRenderingContext" in js and "saveData" in js and not re.search(r"^\s*import\s", js, re.M))
    ds = (ROOT / "docs" / "DESIGN_SYSTEM.md").read_text(encoding="utf-8")
    api = ROOT / "research" / "handoff" / "2026-11-20" / "nq4" / "FX_API.md"
    verbs = ("win", "loss", "milestone", "ring", "roll", "trail", "vault")
    check("a. the API is documented: DESIGN_SYSTEM.md section 6 and nq4/FX_API.md name every verb",
          "## 6. NQ effects" in ds and api.exists() and all(f"NQFX.{v}(" in ds and f"NQFX.{v}(" in api.read_text(encoding="utf-8") for v in verbs))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


NOISE = re.compile(r"GL Driver Message|GPU stall|WebGL-|swiftshader|Automatic fallback", re.I)
LONG = """window.__long = []; try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__long.push([Math.round(e.startTime), Math.round(e.duration)]); })
  .observe({ type: 'longtask', buffered: true }); } catch (e) {}
  window.__imp = 0; const _imp = performance.now.bind(performance);
  new MutationObserver(() => { const v = document.getElementById('vault'); if (v && v.dataset.nqfxVault === 'waiting' && !window.__wait) window.__wait = Math.round(_imp()); }).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-nqfx-vault'] });"""


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("b. playwright is available", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(WEB)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/olympus/nqfx-lab.html"
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

        def page(ctx_opts=None, init=None, q=""):
            ctx = b.new_context(viewport={"width": 390, "height": 844}, **(ctx_opts or {}))
            if init:
                ctx.add_init_script(init)
            p = ctx.new_page()
            errs = []
            p.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") and not NOISE.search(m.text) else None)
            p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
            p.goto(url + q, wait_until="load")
            return ctx, p, errs

        # the full tier
        ctx, p, errs = page(init=LONG, q="?tier=high")
        first = p.evaluate("() => document.getElementById('vault').dataset.nqfxVault || ''")
        try:
            p.wait_for_function("() => document.getElementById('vault').dataset.nqfxVault === '3d'", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        p.wait_for_timeout(600)
        r = p.evaluate("""() => { const v = document.getElementById('vault'); return { mode: v.dataset.nqfxVault, gl: !!v.querySelector('canvas.nqfx-gl.on'),
          pic: !!v.querySelector('.nqfx-vault2d svg'), aria: v.getAttribute('aria-label'), label: v.querySelector('.nqfx-vault-label').textContent,
          tier: OLYMPUS_FX.tier(), long: window.__long, wait: window.__wait || 0 }; }""")
        check("b. the vault: drawn first, then 3D after load + idle (canvas on top), its label and a spoken label with the %",
              first in ("waiting", "2d", "") and r["mode"] == "3d" and r["gl"] and r["pic"] and "62%" in (r["aria"] or "") and r["label"] == "$1,860 of $3,000", r)
        before = [x for x in r["long"] if x[0] < (r["wait"] or 0) + 50]
        check(f"b. no long task > 200 ms before the 3D import (got {before})", all(x[1] <= 200 for x in before), r["long"])
        p.evaluate("() => window.__nq.vault.call('set', 0.25, '$750 of $3,000')")
        p.wait_for_timeout(300)
        r2 = p.evaluate("() => [document.querySelector('#vault .nqfx-vault-label').textContent, document.getElementById('vault').getAttribute('aria-label')]")
        check("b. vault.call('set', v, label) moves it and its labels", r2[0] == "$750 of $3,000" and "25%" in r2[1], r2)
        # the trail: 3 paths around the line, follows a redraw
        n0 = p.evaluate("() => document.querySelectorAll('svg.chart path').length")
        p.click("#redraw")
        p.wait_for_timeout(100)
        same = p.evaluate("() => { const ps = [...document.querySelectorAll('svg.chart path')], d = document.getElementById('line').getAttribute('d'); return ps.every(x => x.getAttribute('d') === d); }")
        seen = set()
        for _ in range(14):                                    # one run + its rest is 3.6 s: sample across it
            seen.add(p.evaluate("() => { const x = document.querySelector('svg.chart path[stroke-dasharray]'); return x ? x.getAttribute('stroke-dashoffset') : ''; }"))
            p.wait_for_timeout(300)
        check("b. the chart trail: a glow under the line and a moving light over it (4 paths), following a redrawn line",
              n0 == 4 and same and len(seen) > 3, (n0, same, sorted(seen)[:5]))
        # moments
        p.click("#pnlUp")
        p.click("#loss")
        p.click("#ms")
        p.wait_for_timeout(500)
        m = p.evaluate("() => ({ toasts: [...document.querySelectorAll('.oly-fx-toast')].map(t => t.textContent.trim()), pnl: document.getElementById('pnl').textContent })")
        check("b. the moments: Win +$420, Loss -$95, Eval passed toasts; the number rolls to $420",
              any("Win +$420" in t for t in m["toasts"]) and any("Loss -$95" in t for t in m["toasts"]) and any("Eval passed" in t for t in m["toasts"]), m)
        p.wait_for_timeout(1500)
        check("b. the number roll-up lands on its value", p.evaluate("() => document.getElementById('pnl').textContent") == "$420")
        # stop everything: nothing left behind
        p.wait_for_timeout(4000)
        left = p.evaluate("""() => { OLYMPUS_FX.stopAll(); const s = OLYMPUS_FX.stats(); return { canv: document.querySelectorAll('canvas').length, nodes: document.querySelectorAll('.nqfx-vault2d, .nqfx-vault-label').length,
          paths: document.querySelectorAll('svg.chart path').length, tickers: s.tickers, active: s.active, errors: s.errors, cls: document.querySelectorAll('.nqfx-vault').length }; }""")
        check("b. stop() leaves nothing: no canvas, vault nodes, extra chart paths, ticker or class", left == {"canv": 0, "nodes": 0, "paths": 1, "tickers": 0, "active": 0, "errors": [], "cls": 0}, left)
        check("b. no console or page error on the full tier", not errs, errs[:4])
        ctx.close()

        # tier low: the 3D at pixel ratio 1
        ctx, p, errs = page(ctx_opts={"device_scale_factor": 3}, q="?tier=low")
        try:
            p.wait_for_function("() => document.getElementById('vault').dataset.nqfxVault === '3d'", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        lo = p.evaluate("() => { const c = document.querySelector('#vault canvas.nqfx-gl'); return c ? [c.width, c.clientWidth] : null; }")
        check("b. tier low: the vault still in 3D at pixel ratio 1 (a phone with a 3x screen)", lo and abs(lo[0] - lo[1]) <= 1 and not errs, (lo, errs[:2]))
        ctx.close()

        # reduced motion: no 3D, no moving light, the ring and the number are still
        ctx, p, errs = page(ctx_opts={"reduced_motion": "reduce"}, q="?tier=high")
        p.wait_for_timeout(3500)
        rm = p.evaluate("""() => ({ mode: document.getElementById('vault').dataset.nqfxVault, gl: document.querySelectorAll('canvas.nqfx-gl').length,
          paths: document.querySelectorAll('svg.chart path').length, moving: document.querySelectorAll('svg.chart path[stroke-dasharray]').length,
          ring: !!document.querySelector('#ring canvas'), tier: OLYMPUS_FX.tier(), running: OLYMPUS_FX.stats().running })""")
        check("b. reduced motion: the drawn vault (no 3D), the glow under the line but no moving light, the ring drawn still, nothing running",
              rm["mode"] == "2d" and rm["gl"] == 0 and rm["paths"] == 2 and rm["moving"] == 0 and rm["ring"] and rm["tier"] == "off" and rm["running"] == 0 and not errs, (rm, errs[:2]))
        ctx.close()

        # no WebGL: the drawn vault, everything else works
        ctx, p, errs = page(init="delete window.WebGLRenderingContext; delete window.WebGL2RenderingContext;", q="?tier=high")
        p.wait_for_timeout(3000)
        ng = p.evaluate("() => [document.getElementById('vault').dataset.nqfxVault, !!document.querySelector('#vault .nqfx-vault2d svg'), document.querySelectorAll('svg.chart path').length]")
        check("b. no WebGL: the drawn vault stays, the trail still runs, no error", ng == ["2d", True, 4] and not errs, (ng, errs[:2]))
        ctx.close()
        b.close()
    srv.shutdown()


def main():
    static()
    if os.environ.get("NQ_NO_BROWSER") != "1":
        browser()
    print(f"nq fx: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
