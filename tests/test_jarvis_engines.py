"""Jarvis's AI VOICE in the page (2026-11-18, owner: "Jarvis voice sucks, it sounds like a bot, it should sound like a person. I'm only
asking once to fix it." He picked Male, British). The real Jarvis page in Chromium, its AI voice worker (neural-voice-worker.js) replaced
by a stand-in that speaks the same messages without the 117 MB model, the phone's voice mocked (tests/test_jarvis_talk.py MOCK). Checks:
  a. the files: the shell loads neural-voice.js + speech-text.js (optional), never the old engine chooser (voice-engines.js), the Voice
     sheet is one setting (AI voice (George) / iPhone voice / Off), tts.js stays import-free, the worker is a same-origin module file
  b. first use: nothing downloads before Jarvis first talks; the first answer is said at once by the iPhone's British man (never silence)
     while the one-time download starts with its line "Getting Jarvis's voice ready (one time, about 117 MB) · N%" (never in the way of
     a tap); the worker is asked for the pinned model, q8 on WebAssembly, George; ready: the line says so and goes; the next answers are
     said by the AI voice in pieces with the words a person says ("minus a hundred and thirteen dollars", "twenty-four nine fifty-five"),
     the iPhone voice quiet
  c. the setting: iPhone voice (said in it, kept), Off (nothing said or made, kept after a reload), back to the AI voice; a worker that
     crashes: the iPhone voice says every answer, the line says why once, the Voice sheet says it can't run here, no retry storm
  d. (optional: RUN_KOKORO=1 KOKORO_DIR=<a copy of the CDN: jsd/kokoro-js@1.2.1/..., jsd/transformers@3.5.1/..., hf/<model repo files>>)
     the real model in Chromium from that local copy: it boots, speaks a real sentence (WAV, 24 kHz), a second open needs no network
    python -X utf8 -m tests.test_jarvis_engines       (~1-2 min; browser suite: run under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading

from tests import test_jarvis_hub as H
from tests import test_jarvis_talk as T

JV = H.JV
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(name):
    return open(os.path.join(JV, name), encoding="utf-8").read()


# ------------------------------------------------------------------------------------------------ a. files
def part_files():
    page = read("index.html")
    check("a. the shell loads the AI voice (neural-voice.js) and the spoken-English layer (speech-text.js), each optional; never the old chooser (voice-engines.js)",
          "load('nv', './neural-voice.js'" in page and "load('speech', './speech-text.js'" in page and "voice-engines.js" not in page)
    check("a. every speaking path uses it: the shell's cloudVoice (answers, ZEUS, briefings, alerts, reminders) and voice mode's deps",
          "return safe(() => nv.descriptor(ctx), null);" in page and "prosody: () => (voiceTest() ? null : spx), player: () => nvPlayer," in page
          and "cloud: cloudVoice, micBusy" in page and "talk: (t) => speak(String(t || ''), false)" in page)
    sheet = page[page.index('<div class="sheet" id="voice"'):page.index('<div class="sheet" id="palette"')]
    check("a. the Voice sheet: one setting with three choices (AI voice (George) / iPhone voice / Off), then hold to talk, talk style, the iPhone-voice tip, Test, Done",
          re.findall(r'data-vpick="(\w+)"', sheet) == ["ai", "phone", "off"] and ">AI voice (George)<" in sheet and all(i in sheet for i in ('id="vHold"', 'id="vStyle"', 'id="vPhoneTip"', 'id="vTest"', 'id="vX"'))
          and not any(i in sheet for i in ('id="vEngine"', 'id="vCloud"', 'id="vVoice"', 'id="vRate"')), re.findall(r'id="(\w+)"', sheet))
    check("a. tts.js is still import-free (the fallback); the worker is a same-origin module file",
          not re.search(r"^\s*import ", read("tts.js"), re.M) and "new URL('./neural-voice-worker.js', import.meta.url), { type: 'module' }" in read("neural-voice.js")
          and os.path.exists(os.path.join(JV, "neural-voice-worker.js")))


# ------------------------------------------------------------------------------------------------ b-c. the page
# the worker, replaced: the same messages, no model. 'crash' = it dies while starting (a phone out of memory)
FAKE_WORKER = r"""
const bc = new BroadcastChannel('fake-nv'), MODE = '__MODE__';
self.onmessage = (e) => {
  const m = e.data || {};
  if (m.type === 'init') {
    bc.postMessage({ k: 'init', cfg: { lib: m.cfg.lib, hfPin: m.cfg.hfPin, dtype: m.cfg.dtype, device: m.cfg.device, voice: m.cfg.voice, total: m.cfg.totalBytes } });
    if (MODE === 'crash') { setTimeout(() => { throw new Error('out of memory'); }, 400); return; }
    const T = m.cfg.totalBytes; let i = 0;
    const step = () => { i++; self.postMessage({ type: 'progress', loaded: Math.round(T * i / 6), total: T, file: 'onnx/model_quantized.onnx' });
      if (i < 6) setTimeout(step, 700); else setTimeout(() => self.postMessage({ type: 'ready', device: 'wasm', dtype: 'q8', ms: 4300, warmMs: 300, rtf: 0.5 }), 300); };
    setTimeout(step, 250);
    return;
  }
  if (m.type === 'gen') {
    bc.postMessage({ k: 'gen', text: m.text, voice: m.voice });
    const n = Math.round(24000 * Math.min(0.5, 0.1 + m.text.length / 200)), pcm = new Float32Array(n);
    for (let j = 0; j < n; j++) pcm[j] = 0.25 * Math.sin(j / 7) * Math.sin(Math.PI * j / n);
    setTimeout(() => self.postMessage({ type: 'audio', id: m.id, pcm, rate: 24000, ms: 90 }, [pcm.buffer]), 60);
  }
};
"""
SPY = """
window.__ai = []; window.__aiInit = []; window.__plays = 0;
try { const bc = new BroadcastChannel('fake-nv'); bc.onmessage = (e) => { const d = e.data || {}; if (d.k === 'gen') window.__ai.push(d.text); if (d.k === 'init') window.__aiInit.push(d.cfg); }; } catch (e) {}
window.__pill = [];                    // every line the progress pill showed (a loaded machine can poll past a short one)
document.addEventListener('DOMContentLoaded', () => new MutationObserver(() => { const e = document.getElementById('nvStatus');
  if (e && !e.hidden && e.textContent && window.__pill[window.__pill.length - 1] !== e.textContent) window.__pill.push(e.textContent); })
  .observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['hidden', 'style'] }));
const op = HTMLMediaElement.prototype.play;
HTMLMediaElement.prototype.play = function () { if (String(this.src || '').indexOf('blob:') === 0) window.__plays++; return op.apply(this, arguments); };
"""


def new_page(br, url, mode):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
    H.feeds(ctx, H.kalshi_feed())                       # nothing leaves the machine (the CDN and huggingface.co included)
    ctx.route(re.compile(r".*/jarvis/neural-voice-worker\.js(\?.*)?$"), lambda r: r.fulfill(status=200, content_type="text/javascript", body=FAKE_WORKER.replace("__MODE__", mode)))
    ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9'));"
                        " localStorage.setItem('jarvis.intro', 'off'); } catch (e) {}")
    ctx.add_init_script("window.__iosRule = false; window.__voicesEmpty = false;")
    ctx.add_init_script("try { localStorage.setItem('jarvis.bots.set', JSON.stringify({ on: true, plan: false, recap: false, rituals: false })); } catch (e) {}")
    # the morning briefing (once a day from 07:00 ET) and the spoken alerts talk on their own: off here like the rituals above, so her first
    # words are the answer the test asked for (day-jarvis 2026-11-20: a briefing spoken in the slow test voice held the answer past 15 s)
    ctx.add_init_script("try { localStorage.setItem('jarvis.alerts.v1', JSON.stringify({ speak: false, brief: false, quiet: false, from: '22:00', to: '07:00' })); } catch (e) {}")
    if os.environ.get("JARVIS_TEST_LITE") == "1":
        ctx.add_init_script("try { localStorage.setItem('jfx', 'off'); localStorage.setItem('jarvis.no3d', '1'); } catch (e) {}")
    ctx.add_init_script(T.MOCK)
    ctx.add_init_script(SPY)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text and "WebGL" not in m.text else None)
    p.goto(url + "jarvis/")
    H.ready(p)
    p.wait_for_function("document.documentElement.dataset.voiceout === 'module' && document.documentElement.dataset.nv === 'module' && !!window.__jarvis.aiVoice()", timeout=90000)
    return ctx, p, errs


def idle(p, ms=60000):
    p.wait_for_function("window.__jarvis.state() === 'idle' && !window.__jarvis.voice().speaking", timeout=ms)


def run_ok(br, url):
    ctx, p, errs = new_page(br, url, "ok")
    st = p.evaluate("window.__jarvis.aiVoice()")
    check("b. the default is the AI voice (George); nothing is downloaded before Jarvis first talks", st["pick"] == "ai" and st["state"] == "idle" and p.evaluate("window.__aiInit.length") == 0, st)
    p.mouse.click(3, 420)                               # the first tap (the shared audio element is unlocked inside it)
    p.fill("#q", "is the market open")
    p.press("#q", "Enter")
    p.wait_for_function("window.__said.some((x) => /market/i.test(x.text))", timeout=15000)       # (a "Good evening." can come first, at the first tap)
    first = p.evaluate("window.__said.find((x) => /market/i.test(x.text))")
    p.wait_for_function("window.__pill.some((t) => /^Getting Jarvis's voice ready \\(one time, about 117 MB\\) · \\d+%$/.test(t))", timeout=20000)
    pill = p.evaluate("(() => { const e = document.getElementById('nvStatus'), r = e.getBoundingClientRect(); return { text: e.textContent, pe: getComputedStyle(e).pointerEvents, top: r.top, w: r.width, vw: innerWidth }; })()")
    init = p.evaluate("window.__aiInit[0] || null")
    check("b. first use: the answer is said at once by the iPhone's British man (Daniel), never silence, while the one-time download starts",
          "market" in first["text"].lower() and first["voice"] == "Daniel" and init is not None, (first, init))
    check("b. the progress line: \"Getting Jarvis's voice ready (one time, about 117 MB) · N%\", at the top, on the screen, never in the way of a tap",
          pill["pe"] == "none" and 0 <= pill["top"] < 80 and pill["w"] <= pill["vw"] - 30, pill)
    check("b. the worker is asked for the pinned model, q8 on WebAssembly, the British man George (kokoro-js 1.2.1 from cdn.jsdelivr.net)",
          init and init["dtype"] == "q8" and init["device"] == "wasm" and init["voice"] == "bm_george" and "/resolve/1939ad2a8e416c0acfeecc08a694d14ef25f2231/" in init["hfPin"]
          and init["lib"] == "https://cdn.jsdelivr.net/npm/kokoro-js@1.2.1/dist/kokoro.web.js" and init["total"] > 110e6, init)
    p.wait_for_function("window.__jarvis.aiVoice().state === 'ready'", timeout=20000)
    p.wait_for_function("window.__pill.some((t) => /AI voice is ready/.test(t))", timeout=15000)
    p.wait_for_function("document.getElementById('nvStatus').hidden", timeout=8000)
    check("b. ready: the line says so, then goes", True)
    idle(p)
    p.evaluate("window.__said = []; window.__ai = []; window.__plays = 0")
    p.evaluate("window.__jarvis.talk('ATLAS closed one trade today at -$113. Stop is at 24,955, target 25,360. Nothing else needs you.')")
    p.wait_for_function("window.__ai.length >= 3", timeout=15000)
    idle(p)
    ai = p.evaluate("window.__ai")
    st = p.evaluate("window.__jarvis.aiVoice()")
    check("b. ready: the answer in the AI voice, in pieces, with the words a person says (minus a hundred and thirteen dollars, twenty-four nine fifty-five); the iPhone voice quiet",
          len(ai) >= 3 and "minus a hundred and thirteen dollars" in " ".join(ai) and "twenty-four nine fifty-five" in " ".join(ai) and not re.search(r"[\d$]", " ".join(ai))
          and p.evaluate("window.__plays") == len(ai) and p.evaluate("window.__said.length") == 0 and st["engine"] == "kokoro", (ai, st, p.evaluate("window.__said")))
    # c. the setting
    p.click("#vset")
    p.wait_for_function("!document.getElementById('voice').hidden", timeout=5000)
    sheet = p.evaluate("[[...document.querySelectorAll('#vPick [data-vpick]')].map((b) => b.getAttribute('aria-pressed')), document.getElementById('vNote').textContent]")
    check("c. the Voice sheet: AI voice (George) picked, 'ready: made on this phone, nothing is sent anywhere'", sheet[0] == ["true", "false", "false"] and "is ready" in sheet[1] and "nothing is sent" in sheet[1], sheet)
    p.evaluate("window.__said = []; window.__ai = []")
    p.click('#vPick [data-vpick="phone"]')
    p.wait_for_function("window.__said.some((x) => x.text === 'This is the iPhone voice.')", timeout=8000)
    idle(p)
    p.evaluate("window.__jarvis.talk('The iPhone voice says this one.')")
    p.wait_for_function("window.__said.some((x) => /says this one/.test(x.text))", timeout=8000)
    idle(p)
    got = p.evaluate("[JSON.parse(localStorage.getItem('jarvis.voiceEngine')).mode, window.__said.map((x) => x.voice), window.__ai.length, document.querySelector('#vPick [data-vpick=phone]').getAttribute('aria-pressed')]")
    check("c. iPhone voice: said in it (Daniel), kept on this phone, the AI voice makes nothing", got[0] == "phone" and set(got[1]) == {"Daniel"} and got[2] == 0 and got[3] == "true", got)
    p.click('#vPick [data-vpick="off"]')
    p.evaluate("window.__said = []; window.__ai = []")
    p.evaluate("window.__jarvis.talk('Nobody should hear this.')")
    p.wait_for_timeout(900)
    off = p.evaluate("[localStorage.getItem('jarvis.speak'), window.__said.length, window.__ai.length, document.getElementById('spk').getAttribute('aria-pressed')]")
    check("c. Off: nothing said, nothing made, the dock's speaker shows off", off == ["off", 0, 0, "false"], off)
    p.reload()
    H.ready(p)
    p.wait_for_function("document.documentElement.dataset.nv === 'module' && !!window.__jarvis.aiVoice()", timeout=90000)
    p.click("#vset")
    p.wait_for_function("!document.getElementById('voice').hidden", timeout=5000)
    kept = p.evaluate("[[...document.querySelectorAll('#vPick [data-vpick]')].map((b) => b.getAttribute('aria-pressed')), window.__jarvis.aiVoice().pick]")
    check("c. after a reload the setting is kept (Off)", kept == [["false", "false", "true"], "off"], kept)
    p.evaluate("window.__said = []; window.__ai = []")
    p.click('#vPick [data-vpick="ai"]')
    p.wait_for_function("window.__said.some((x) => /George/.test(x.text)) || window.__ai.some((t) => /George/.test(t))", timeout=15000)
    back = p.evaluate("[window.__jarvis.aiVoice().pick, localStorage.getItem('jarvis.speak'), document.getElementById('spk').getAttribute('aria-pressed')]")
    check("c. back to the AI voice: on again, says who it is", back == ["ai", "on", "true"], back)
    p.click("#vX")
    p.wait_for_timeout(400)
    check("c. no page errors (the AI voice run)", not errs, errs)
    ctx.close()


def run_crash(br, url):
    ctx, p, errs = new_page(br, url, "crash")
    p.mouse.click(3, 420)
    p.fill("#q", "is the market open")
    p.press("#q", "Enter")
    p.wait_for_function("window.__said.length >= 1", timeout=15000)
    p.wait_for_function("window.__jarvis.aiVoice().state === 'failed'", timeout=15000)
    p.wait_for_function("window.__pill.some((t) => /AI voice right now/.test(t))", timeout=15000)
    idle(p)
    p.evaluate("window.__said = []")
    p.evaluate("window.__jarvis.talk('Still talking with the iPhone voice.')")
    p.wait_for_function("window.__said.some((x) => /Still talking/.test(x.text))", timeout=8000)
    idle(p)
    p.click("#vset")
    p.wait_for_function("!document.getElementById('voice').hidden", timeout=5000)
    note = p.evaluate("document.getElementById('vNote').textContent")
    tries = p.evaluate("window.__aiInit.length")
    check("c. a worker that dies (out of memory): every answer still said by the iPhone voice, the line says why once, the sheet says it can't run here, no retry storm",
          "can't run here" in note and tries == 1 and p.evaluate("window.__said.every((x) => x.voice === 'Daniel')"), (note, tries))
    p.click("#vX")
    check("c. no page errors (the crash run)", not errs, errs)
    ctx.close()


# ------------------------------------------------------------------------------------------------ d. the real model (optional)
REAL_PAGE = """<!doctype html><meta charset=utf-8><title>nv</title><script type=module>
import { createNeuralVoice } from './jarvis/neural-voice.js';
import { speechText } from './jarvis/speech-text.js';
const nv = createNeuralVoice({ urls: %s });
window.nv = nv;
window.say = async (t) => { const b = await nv.synth(speechText(t)); const v = new DataView(await b.arrayBuffer()); return { size: b.size, dur: b.dur, rate: v.getUint32(24, true), riff: v.getUint32(0, false) === 0x52494646 }; };
window.__ok = 1;
</script>"""


def run_real(br, base_dir):
    root = tempfile.mkdtemp(prefix="le_nv_real_")
    try:
        shutil.copytree(JV, os.path.join(root, "jarvis"))
        hits = []

        class C(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a): pass

            def end_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                super().end_headers()

            def do_GET(self):
                hits.append(self.path)
                super().do_GET()
        site = H.serve(root)
        cdn = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(C, directory=base_dir))
        threading.Thread(target=cdn.serve_forever, daemon=True).start()
        cb = f"http://127.0.0.1:{cdn.server_address[1]}/"
        urls = {"lib": cb + "jsd/kokoro-js@1.2.1/dist/kokoro.web.js", "wasmBase": cb + "jsd/transformers@3.5.1/dist/", "hfPin": cb + "hf/"}
        su = f"http://127.0.0.1:{site.server_address[1]}/"
        ctx = br.new_context()
        ctx.route(su + "__nv.html", lambda r: r.fulfill(status=200, content_type="text/html", body=REAL_PAGE % json.dumps(urls)))
        p = ctx.new_page()
        p.goto(su + "__nv.html")
        p.wait_for_function("window.__ok === 1", timeout=20000)
        ok = p.evaluate("nv.start()")
        r = p.evaluate("say('Zlarior just went long on the 50K.')") if ok else None
        check("d. the real model (local copy of the CDN): boots on WebAssembly and speaks a real sentence (WAV, 24 kHz, over a second)",
              ok and r and r["riff"] and r["rate"] == 24000 and r["dur"] > 1000, (ok, r, p.evaluate("nv.stats()")))
        n0 = len(hits)
        p2 = ctx.new_page()
        p2.goto(su + "__nv.html")
        p2.wait_for_function("window.__ok === 1", timeout=20000)
        ok2 = p2.evaluate("nv.start()")
        check("d. a second open: everything from the browser's storage, no network at all", ok2 and len(hits) == n0, hits[n0:])
        ctx.close()
        site.shutdown(); cdn.shutdown()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    part_files()
    tmp = tempfile.mkdtemp(prefix="le_jarvis_engines_")
    path = H.site(tmp, "E", "asis")
    srv = H.serve(tmp)
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + path
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"], **({"executable_path": exe} if exe else {}))
            run_ok(br, url)
            run_crash(br, url)
            if os.environ.get("RUN_KOKORO") == "1" and os.environ.get("KOKORO_DIR"):
                run_real(br, os.environ["KOKORO_DIR"])
            else:
                print("[SKIP] d. the real model: set RUN_KOKORO=1 and KOKORO_DIR=<a local copy of the CDN files>", flush=True)
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis ai voice: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
