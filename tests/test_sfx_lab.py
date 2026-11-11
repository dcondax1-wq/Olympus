"""OLYMPUS Sound Lab in a real browser (olympus/sfx-lab.html, 2026-11-11; docs/SOUND_API.md).

  a. the page loads at 390x844 with no console error, and NO AudioContext exists before the first tap
  b. the first tap creates exactly one context; cues, places, the 3D pad and music respond
  c. every sound rendered offline (OfflineAudioContext, master volume 1) is audible and never clips: peak 0.01 .. 0.95, no NaN;
     each place renders a bed with a level and no clipping
  d. buttons are >= 44 px; no horizontal scroll
  e. the recorded layer (CC0 recordings, assets/audio/): nothing is downloaded before the first tap; then the UI taps and the harp load (Opus here);
     every file decodes in Chromium (Ogg Opus; this Chromium build has no AAC, so the .m4a twins are checked by ffprobe in test_sfx_engine);
     every sound rendered with its recordings is audible, never clips and really uses them; every place with loops renders a bed with them
  f. a missing assets folder (404): the synth plays, the failure is recorded, no page error
  g. the lab lists every recording family, A/B switches the layer, the loudness meter moves
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


REC_RENDER = """async (names) => {
  const out = {};
  for (const n of names) {
    const bed = n.startsWith('bed:'), len = 48000 * (bed ? 8 : 3);
    const e = window.OLYMPUS_SFX.create({ AudioContext: function () { return new OfflineAudioContext(2, len, 48000); }, matchMedia: () => ({ matches: false }),
      fetch: window.fetch.bind(window), document: document });
    e.unlock(); e.setVolume(1); e.sound(true);
    let ok;
    if (bed) { e.ambience(true); await e.preload(n.slice(4)); ok = e.ambient(n.slice(4)); await new Promise(r => setTimeout(r, 30)); }
    else { await e.preload('all'); ok = e.play(n); }
    const used = e.state().samples.played, buf = await e.context().startRendering();
    let peak = 0, sum = 0, nan = false;
    for (let c = 0; c < 2; c++) { const d = buf.getChannelData(c); for (let i = 0; i < d.length; i++) { const v = d[i]; if (v !== v) nan = true; const a = Math.abs(v); if (a > peak) peak = a; sum += v * v; } }
    out[n] = { ok, used, peak: Math.round(peak * 1000) / 1000, rms: Math.round(Math.sqrt(sum / (buf.length * 2)) * 10000) / 10000, nan };
    e.ambientStop();
  }
  return out;
}"""

DECODE = """async (stems) => {
  const out = {}, a = document.createElement('audio');
  out._can = { ogg: a.canPlayType('audio/ogg; codecs="opus"'), m4a: a.canPlayType('audio/mp4; codecs="mp4a.40.2"') };
  for (const s of stems) for (const f of ['ogg', 'm4a']) {
    if (f === 'm4a' && !out._can.m4a) continue;
    try { const ab = await (await fetch('../assets/audio/' + s + '.' + f)).arrayBuffer(); const b = await new OfflineAudioContext(1, 4800, 48000).decodeAudioData(ab);
      out[s + '.' + f] = Math.round(b.duration * 1000) / 1000; } catch (e) { out[s + '.' + f] = 'FAIL ' + e; }
  }
  return out;
}"""


def serve_assets():
    """the kit's test server, plus tools/web_public/assets/ (the shared CC0 files)"""
    import http.server
    import threading
    from tests.test_olympus_kit import Handler, WEB

    class H(Handler):
        def translate_path(self, path):
            p = path.split("?")[0].split("#")[0]
            if p.startswith("/assets/"):
                return os.path.join(WEB, *p.lstrip("/").split("/"))
            return super().translate_path(path)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: H(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def main():
    from playwright.sync_api import sync_playwright
    from tests.test_olympus_kit import launch
    serve = serve_assets
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
        reqs: list = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        p.on("request", lambda r: reqs.append(r.url) if "/assets/audio/" in r.url and not r.url.endswith("manifest.json") else None)
        p.goto(url); p.wait_for_function("window.OLYMPUS_SFX && document.querySelectorAll('#gCues button').length > 10")
        p.wait_for_timeout(600)
        pre = p.evaluate("({ ac: window.__acNew, st: OLYMPUS_SFX.state().ctxState, unlocked: OLYMPUS_SFX.state().unlocked, gate: document.getElementById('gateT').textContent })")
        check("a. loads with no AudioContext before the first tap (none constructed, state 'none') and says to tap", pre["ac"] == 0 and pre["st"] == "none" and not pre["unlocked"] and "Tap" in pre["gate"], pre)
        if shots:
            os.makedirs(os.path.join(ROOT, "docs/shots/sound"), exist_ok=True)
            p.screenshot(path=os.path.join(ROOT, "docs/shots/sound/after.jpg"), type="jpeg", quality=70)
            p.locator("section[aria-labelledby=hCues]").screenshot(path=os.path.join(ROOT, "docs/shots/sound/after-cues.jpg"), type="jpeg", quality=70)
            p.locator("section[aria-labelledby=hPlaces]").screenshot(path=os.path.join(ROOT, "docs/shots/sound/after-places.jpg"), type="jpeg", quality=70)
        check("e. no recording is downloaded before the first tap", not reqs, reqs[:4])
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
        # e. the recorded layer
        p.wait_for_function("OLYMPUS_SFX.samples().loaded.indexOf('ui') >= 0 && OLYMPUS_SFX.samples().loaded.indexOf('harp') >= 0", timeout=60000)
        sm = p.evaluate("OLYMPUS_SFX.samples()")
        check("e. after the tap the UI taps and the harp load (Opus in Chromium), nothing failed", sm["fmt"] == "ogg" and not sm["failed"] and sm["kb"] > 100, sm)
        stems = p.evaluate("Object.keys(OLYMPUS_SFX.audio.files)")
        dec = p.evaluate(DECODE, stems)
        can = dec.pop("_can")
        man = json.load(open(os.path.join(ROOT, "tools/web_public/assets/audio/manifest.json"), encoding="utf-8"))
        badd = {k: v for k, v in dec.items() if isinstance(v, str) or abs(v - man["files"][k.rsplit(".", 1)[0]]["dur"]) > 0.05}
        check(f"e. all {len(dec)} recorded files decode in Chromium at their measured length (canPlayType {can}; no AAC in this build: .m4a checked by ffprobe)",
              not badd and len(dec) >= len(stems), badd)
        snd = [n for n in names if not n.startswith("bed:")]
        rec = p.evaluate(REC_RENDER, snd + ["bed:" + b for b in p.evaluate("OLYMPUS_SFX.beds")])
        synth_only = {"thunder", "groan", "bed:library", "bed:treasury"}          # no recording fits them / their recordings are events only
        badr = {k: v for k, v in rec.items() if not v["ok"] or v["nan"] or v["peak"] > 0.95 or v["peak"] < (0.002 if k.startswith("bed:") else 0.01)
                or (k not in synth_only and v["used"] < 1) or (k.startswith("bed:") and v["rms"] < 0.002)}
        check(f"e. {len(rec)} sounds and places rendered WITH their recordings: audible, never clipping, the recordings really used", not badr, badr)
        print("   recorded levels:", json.dumps({k: [v["peak"], v["rms"], v["used"]] for k, v in rec.items()}))
        # g. the lab: every family, A/B, the meter
        nb = p.evaluate("[document.querySelectorAll('[data-bank]').length, Object.keys(OLYMPUS_SFX.audio.banks).length, document.querySelectorAll('[data-loop]').length]")
        p.locator("[data-bank='anvil']").tap(); p.wait_for_timeout(250)
        mt = p.evaluate("document.getElementById('mOut').textContent")
        p.locator("[data-ab='synth']").tap(); ab1 = p.evaluate("OLYMPUS_SFX.samples().on"); p.locator("[data-ab='rec']").tap(); ab2 = p.evaluate("OLYMPUS_SFX.samples().on")
        check("g. the lab has a button for every recording family and loop; A/B turns the layer off and on; the meter reads a level",
              nb[0] == nb[1] and nb[2] == 9 and ab1 is False and ab2 is True and "dBFS" in mt and not mt.startswith("-"), (nb, ab1, ab2, mt))
        # d. phone fit
        fit = p.evaluate("({ small: [...document.querySelectorAll('button')].filter(b => b.offsetParent && b.getBoundingClientRect().height < 44).map(b => b.textContent.trim()).slice(0, 6), sw: document.documentElement.scrollWidth })")
        check("d. every visible button >= 44 px tall; no horizontal scroll at 390 px", not fit["small"] and fit["sw"] <= 390, fit)
        check("a. no console errors or page errors", not errs, errs)
        # f. no assets folder: the synth carries everything
        c2 = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        c2.route("**/*", lambda r: r.fulfill(status=404, body="") if "/assets/audio/" in r.request.url else (r.continue_() if r.request.url.startswith(origin) else r.abort()))
        p2 = c2.new_page(); p2.set_default_timeout(120000)
        e2: list = []
        p2.on("pageerror", lambda e: e2.append(str(e)))
        p2.goto(url); p2.wait_for_function("window.OLYMPUS_SFX && document.querySelectorAll('#gCues button').length > 10")
        p2.locator("#gCues button", has_text="Success").first.tap()
        p2.wait_for_function("OLYMPUS_SFX.samples().failed.indexOf('ui') >= 0", timeout=30000)
        fb = p2.evaluate("(() => { const s0 = OLYMPUS_SFX.state().scheduled; const ok = [OLYMPUS_SFX.play('tap'), OLYMPUS_SFX.play('money'), OLYMPUS_SFX.at('step', {x: 1, y: 0, z: -1}, {x: 0, y: 0, z: 0})]; return { ok, more: OLYMPUS_SFX.state().scheduled - s0, s: OLYMPUS_SFX.samples(), err: OLYMPUS_SFX.state().errors }; })()")
        check("f. assets missing (404): cues and world sounds still play (synth), the failure is recorded, no page error",
              fb["ok"] == [True, True, True] and fb["more"] > 3 and "ui" in fb["s"]["failed"] and fb["err"] == 0 and not e2, (fb, e2))
        c2.close()
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
