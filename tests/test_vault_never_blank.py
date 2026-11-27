"""QA #3 (night-nq-accounts 2026-11-27): the NQ page's "ATLAS first payout" vault is NEVER a blank black box.
olympus/nqfx.js hides the drawn 2D vault only after the 3D's first DRAWN frame (olympus/nqvault3d.js reads one pixel after the render);
no frame within 2 s, WebGL off, or a lost context = the 2D stays.

    python -X utf8 -m tests.test_vault_never_blank          (~40 s; skips without Playwright)

  a. normal WebGL (SwiftShader): the vault goes 3D, the canvas is on, the 2D fades out (the 3D really drew)
  b. Chromium --disable-webgl --disable-3d-apis: the drawn 2D vault, fully visible, no canvas
  c. WebGL that makes a context but never paints (drawArrays / drawElements stubbed out): after the 2 s watchdog the 3D is stopped,
     the 2D is fully visible again, data-nqfx-vault = 2d (before the fix: a black box)
  every run: the vault box has a size and a visible picture, no console error
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests import test_accounts_screen as TA  # noqa: E402

check = AK.check
NOPAINT = """(() => { for (const C of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) { if (!C) continue;
  for (const f of ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced', 'drawRangeElements', 'clear'])
    if (C.prototype[f]) C.prototype[f] = function () {}; } })();"""
STATE = """() => { const h = document.getElementById('vault'); if (!h) return null; const p = h.querySelector('.nqfx-vault2d'), c = h.querySelector('canvas');
  const r = h.getBoundingClientRect(); return { mode: h.getAttribute('data-nqfx-vault'), pic: p ? +getComputedStyle(p).opacity : null,
  picH: p ? Math.round(p.getBoundingClientRect().height) : 0, canvas: !!c, on: !!(c && c.classList.contains('on')), w: Math.round(r.width), h: Math.round(r.height),
  card: !document.getElementById('vaultCard').hidden }; }"""


def run(pw, args, init=None, wait=6000):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    br = pw.chromium.launch(args=["--no-sandbox"] + args, **({"executable_path": exe} if exe else {}))
    try:
        at = dt.datetime.fromtimestamp(TA.NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ctx, p, errs, seen, off = AK.page(br, ORIGIN, w=390, h=844, mock={"json?poll=1": TA.ndjson(*TA.post())})
        if init:
            p.add_init_script(init)
        p.goto(f"{ORIGIN}/nq/index.html?at={at}")
        p.wait_for_timeout(2500)
        p.evaluate("document.getElementById('vaultCard') && document.getElementById('vaultCard').scrollIntoView({block: 'center'})")
        p.wait_for_timeout(wait)
        s = p.evaluate(STATE)
        e = [x for x in errs if "WebGL" not in x and "webgl" not in x]
        ctx.close()
        return s, e
    finally:
        br.close()


ORIGIN = None


def main():
    global ORIGIN
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  (playwright not installed: skipped)")
        return AK.finish()
    srv, ORIGIN = AK.serve({"/home.json": None})
    try:
        with sync_playwright() as pw:
            s, e = run(pw, ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            check("a. normal WebGL: 3D after its first drawn frame (canvas on), the 2D faded out", s and s["card"] and s["mode"] == "3d" and s["on"] and s["pic"] == 0 and not e, (s, e[:3]))
            s, e = run(pw, ["--disable-webgl", "--disable-3d-apis"])
            check("b. --disable-webgl: the drawn 2D vault, fully visible, a real size, no canvas", s and s["mode"] == "2d" and s["pic"] == 1 and s["picH"] > 100 and not s["canvas"] and not e, (s, e[:3]))
            s, e = run(pw, ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"], init=NOPAINT, wait=7000)
            check("c. WebGL that never paints: after the 2 s watchdog the 3D is gone and the 2D is fully visible (no black box)",
                  s and s["mode"] == "2d" and s["pic"] == 1 and s["picH"] > 100 and not s["canvas"] and not e, (s, e[:3]))
    finally:
        srv.shutdown()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
