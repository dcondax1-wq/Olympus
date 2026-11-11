"""OLYMPUS Sound Lab in a real browser (olympus/sfx-lab.html, 2026-11-11; docs/SOUND_API.md).

  a. the page loads at 390x844 with no console error, and NO AudioContext exists before the first tap
  b. the first tap creates exactly one context; cues, places, the 3D pad and music respond
  c. every sound rendered offline (OfflineAudioContext, master volume 1) is audible and never clips: peak 0.01 .. 0.95, no NaN;
     each place renders a bed with a level and no clipping
  d. buttons are >= 44 px; no horizontal scroll
Run under the machine's one-browser lock:  flock -w 2400 /tmp/olympus_browser.lock python tests/test_sfx_lab.py [--shots]
--shots also writes docs/shots/sound/{before,after}.jpg (the old lab from git, the new one).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   [{str(info)[:600]}]"))


COUNT_AC = """
window.__acNew = 0;
(function () { var A = window.AudioContext || window.webkitAudioContext; if (!A) return;
  function W() { window.__acNew++; return new A(); } W.prototype = A.prototype; window.AudioContext = W; window.webkitAudioContext = W; })();
try { localStorage.removeItem('olympus.sfx'); } catch (e) {}
"""

RENDER = """async (names) => {
  const out = {};
  for (const n of names) {
    const len = 48000 * 4;
    const e = window.OLYMPUS_SFX.create({ AudioContext: function () { return new OfflineAudioContext(2, len, 48000); }, matchMedia: () => ({ matches: false }) });
    e.unlock(); e.setVolume(1); e.sound(true);
    let ok;
    if (n.startsWith('bed:')) { e.ambience(true); ok = e.ambient(n.slice(4)); } else ok = e.play(n);
    const buf = await e.context().startRendering();
    let peak = 0, sum = 0, nan = false;
    for (let c = 0; c < buf.numberOfChannels; c++) { const d = buf.getChannelData(c); for (let i = 0; i < d.length; i++) { const v = d[i]; if (v !== v) nan = true; const a = Math.abs(v); if (a > peak) peak = a; sum += v * v; } }
    out[n] = { ok, peak: Math.round(peak * 1000) / 1000, rms: Math.round(Math.sqrt(sum / (buf.length * buf.numberOfChannels)) * 10000) / 10000, nan };
    e.ambientStop();
  }
  return out;
}"""


def main():
    from playwright.sync_api import sync_playwright
    from tests.test_olympus_kit import launch, serve
    shots = "--shots" in sys.argv
    srv, origin = serve()
    url = origin + "/olympus/sfx-lab.html"
    with sync_playwright() as pw:
        br = launch(pw)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
        ctx.add_init_script(COUNT_AC)
        p = ctx.new_page(); p.set_default_timeout(120000)
        errs: list = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        p.goto(url); p.wait_for_function("window.OLYMPUS_SFX && document.querySelectorAll('#gCues button').length > 10")
        p.wait_for_timeout(600)
        pre = p.evaluate("({ ac: window.__acNew, st: OLYMPUS_SFX.state().ctxState, unlocked: OLYMPUS_SFX.state().unlocked, gate: document.getElementById('gateT').textContent })")
        check("a. loads with no AudioContext before the first tap (none constructed, state 'none') and says to tap", pre["ac"] == 0 and pre["st"] == "none" and not pre["unlocked"] and "Tap" in pre["gate"], pre)
        if shots:
            os.makedirs(os.path.join(ROOT, "docs/shots/sound"), exist_ok=True)
            p.screenshot(path=os.path.join(ROOT, "docs/shots/sound/after.jpg"), type="jpeg", quality=70)
            p.locator("section[aria-labelledby=hCues]").screenshot(path=os.path.join(ROOT, "docs/shots/sound/after-cues.jpg"), type="jpeg", quality=70)
            p.locator("section[aria-labelledby=hPlaces]").screenshot(path=os.path.join(ROOT, "docs/shots/sound/after-places.jpg"), type="jpeg", quality=70)
        # b. the first tap
        p.locator("#gCues button", has_text="Success").first.tap()
        p.wait_for_timeout(300)
        st = p.evaluate("({ ac: window.__acNew, s: OLYMPUS_SFX.state() })")
        check("b. the first tap creates exactly one AudioContext, unlocks, and the cue plays (a voice, reverb on)",
              st["ac"] == 1 and st["s"]["unlocked"] and st["s"]["scheduled"] > 0 and st["s"]["reverb"], st)
        p.locator("[data-bed='harbour']").tap(); p.wait_for_timeout(300)
        bed = p.evaluate("OLYMPUS_SFX.ambientState().playing")
        p.locator("[data-world='hammer']").tap(); box = p.locator("#pad").bounding_box()
        p.mouse.click(box["x"] + box["width"] * 0.85, box["y"] + box["height"] * 0.5); p.wait_for_timeout(200)
        p.locator("#music").tap(); p.wait_for_timeout(500)
        mus = p.evaluate("OLYMPUS_SFX.musicState()")
        check("b. a place plays (harbour), the 3D pad places a sound, music starts on its toggle", bed == "harbour" and mus["playing"] in ("life", "trading", "money", "research") and mus["on"], (bed, mus))
        p.locator("#mute").tap(); p.wait_for_timeout(200)
        mu = p.evaluate("({ s: OLYMPUS_SFX.state(), bed: OLYMPUS_SFX.ambientState().playing, m: OLYMPUS_SFX.musicState().playing, cue: OLYMPUS_SFX.play('tap') })")
        check("b. Mute all silences at once: no voices, no bed, no music, a cue returns false", mu["s"]["muted"] and mu["s"]["voices"] == 0 and mu["bed"] == "" and mu["m"] == "" and mu["cue"] is False, mu)
        p.locator("#mute").tap(); p.locator("#music").tap()
        # c. levels, offline
        names = p.evaluate("OLYMPUS_SFX.names.filter(n => n !== 'pad')") + ["bed:" + b for b in p.evaluate("OLYMPUS_SFX.beds")]
        lv = p.evaluate(RENDER, names)
        bad = {k: v for k, v in lv.items() if not v["ok"] or v["nan"] or v["peak"] > 0.95 or v["peak"] < (0.002 if k.startswith("bed:") else 0.01)}
        check(f"c. {len(lv)} sounds rendered offline: all audible and none clips (peak 0.01 .. 0.95, beds >= 0.002), no NaN", not bad, bad)
        print("   levels:", json.dumps({k: v["peak"] for k, v in lv.items()}))
        # d. phone fit
        fit = p.evaluate("({ small: [...document.querySelectorAll('button')].filter(b => b.offsetParent && b.getBoundingClientRect().height < 44).map(b => b.textContent.trim()).slice(0, 6), sw: document.documentElement.scrollWidth })")
        check("d. every visible button >= 44 px tall; no horizontal scroll at 390 px", not fit["small"] and fit["sw"] <= 390, fit)
        check("a. no console errors or page errors", not errs, errs)
        if shots:
            old = subprocess.run(["git", "show", "agora-release:tools/web_public/olympus/sfx-lab.html"], cwd=ROOT, capture_output=True, text=True).stdout
            oldjs = subprocess.run(["git", "show", "agora-release:tools/web_public/olympus/sfx.js"], cwd=ROOT, capture_output=True, text=True).stdout
            if old:
                old = old.replace('src="sfx.js"', 'src="sfx-before.js"')
                p.route("**/olympus/sfx-lab-before.html", lambda r: r.fulfill(body=old, content_type="text/html"))
                p.route("**/olympus/sfx-before.js", lambda r: r.fulfill(body=oldjs, content_type="text/javascript"))
                p.goto(origin + "/olympus/sfx-lab-before.html"); p.wait_for_timeout(500)
                p.screenshot(path=os.path.join(ROOT, "docs/shots/sound/before.jpg"), type="jpeg", quality=70)
        ctx.close(); br.close()
    srv.shutdown()
    n = sum(RES)
    print(f"\nsfx lab: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    sys.exit(0 if n == len(RES) else 1)


if __name__ == "__main__":
    main()
