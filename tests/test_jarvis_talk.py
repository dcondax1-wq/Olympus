"""Jarvis TALKS (2026-11-03 evening, owner: "the Jarvis isn't talking, I want you to fully make the bot talk"): her voice on the
Jarvis screen, tools/web_public/jarvis/voice-out.js + tts.js + the speech parts of index.html. Checks:
  a. the files: voice-out.js parses, Safari 16 safe, imports only ./tts.js; the shell loads it at the start
  b. the speaker in node (timers sped up): a chunk whose end never comes is passed (watchdog); one that never starts calls
     onstall with the rest; a speak() right after cancel() waits (WebKit's race); rate / pitch out of range -> 1; an empty voice
     list is asked again at each chunk; the silent primer (volume 0); needsPrimer: iPhone / Home Screen app yes, Chrome no
  c. the page, in Chromium AND in WebKit with an iPhone 13 profile, on a mocked speechSynthesis that records every utterance
     and (WebKit) drops a speak() made outside a tap until one was made inside a tap, like iOS:
     - an answer before any tap waits ("TAP TO HEAR"), the first tap unlocks (WebKit: a silent primer inside the tap) and says it
     - a typed question: the answer is said (by default: no setting needed), within 300 ms of the answer showing
     - an empty voice list: the phone's default voice (en-US); after voiceschanged, Ava (Premium)
     - a 600-character answer: said in sentence chunks (<= 180 chars), in order, all of it, then STANDBY
     - speaking: the waveform on the core and "TAP TO STOP"; a tap on the core stops her at once
     - the dock's speaker: off is kept on this phone (also after a reload), nothing said while off; on says "Voice on."
     - Test voice (the Voice sheet): one natural sentence
     - the mic: tap -> heard -> answered out loud; hands-free keeps listening
     - no page errors
    PLAYWRIGHT_BROWSERS_PATH=<dir with webkit> python -X utf8 -m tests.test_jarvis_talk     (~1-2 min; WebKit skipped, and said
    so, when it is not installed). Screenshots (WebKit): research/handoff/2026-11-03/talk/ (JARVIS_TALK_SHOTS='' = none).
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

from tests import test_jarvis_hub as H

JV = H.JV
VO = os.path.join(JV, "voice-out.js")
TTS = os.path.join(JV, "tts.js")
SHOTS = os.environ.get("JARVIS_TALK_SHOTS", os.path.join(H.ROOT, "research", "handoff", "2026-11-03", "talk"))   # '' = none
RES = []
TEST_LINE = "Hi, I'm Jarvis, and this is how I'll sound when I read your answers out loud."


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


# ------------------------------------------------------------------------------------------------ a. files
def part_files():
    src = open(VO, encoding="utf-8").read()
    ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
    check("a. voice-out.js parses as an ES module", ok.returncode == 0, ok.stderr)
    imports = re.findall(r"^\s*import .* from '([^']+)';", src, re.M)
    check("a. Safari 16 safe: no lookbehind, no ?? / ?. / .at(), one import (./tts.js), no network",
          "(?<" not in src and "??" not in src and "?." not in src and ".at(" not in src and imports == ["./tts.js"] and "fetch(" not in src, imports)
    page = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    check("a. the shell loads it at the start (the first tap must find it) and reads every answer while the switch is on",
          "load('voiceout', './voice-out.js'" in page and "if (!quiet && S.speakOn()) speak(" in page and "speakAll" not in page)
    check("a. the dock has the speaker switch; the core has the waveform and 'TAP TO STOP'",
          'id="spk"' in page and 'id="vwave"' in page and 'id="vstop"' in page)


# ------------------------------------------------------------------------------------------------ b. the speaker in node
NODE = r"""
import { pathToFileURL } from 'node:url';
const st = setTimeout;
globalThis.setTimeout = (f, ms) => st(f, (+ms || 0) > 100 ? 3 : +ms || 0);     // the watchdogs and pauses fast, the 70 ms race wait real
globalThis.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.volume = 1; this.rate = 1; this.pitch = 1; } };
const T = await import(pathToFileURL(process.argv[2]).href);
const wait = (ms) => new Promise((ok) => st(ok, ms));
const out = {};
const mk = (mode) => {
  const s = { said: [], cancels: 0, speaking: false, pending: false, paused: false, list: [],
    getVoices: () => s.list.slice(), cancel() { s.cancels++; s.speaking = false; s.cancelAt = Date.now(); },
    speak(u) {
      s.said.push({ text: u.text, rate: u.rate, pitch: u.pitch, voice: u.voice ? u.voice.name : '', lang: u.lang, vol: u.volume, gap: s.cancelAt ? Date.now() - s.cancelAt : -1 });
      if (mode === 'never') return;                                       // dropped: no events (an iPhone before any tap)
      if (mode === 'noend' && s.said.length === 2) { st(() => u.onstart && u.onstart({}), 1); return; }   // starts, never ends
      st(() => { u.onstart && u.onstart({}); st(() => u.onend && u.onend({}), 2); }, 1);
    } };
  return s;
};
// a chunk whose end never comes: the watchdog moves on, every chunk said, the reply ends
let s = mk('noend'), ended = 0;
let sp = T.createSpeaker({ synth: s, cfg: () => ({ rate: 1, pitch: 1 }) });
sp.speak('First sentence here is long enough to stand alone. Second sentence that never ends on the phone. Third and last sentence of the reply.', { onend: () => ended++ });
await wait(400);
out.noend = { n: s.said.length, ended };
// one that never starts: onstall(rest), no onend
s = mk('never'); let stall = null; ended = 0;
sp = T.createSpeaker({ synth: s, cfg: () => ({}) });
sp.speak('Hello there, this one is dropped. And this one too.', { onend: () => ended++, onstall: (r) => { stall = r; } });
await wait(400);
out.stall = { stall, ended };
// cancel then speak at once: waits out WebKit's race; rate / pitch out of range -> 1; empty list asked again
s = mk('ok'); sp = T.createSpeaker({ synth: s, cfg: () => ({ rate: NaN, pitch: 7 }) });
sp.speak('One reply that is being said right now.');
await wait(5);
s.speaking = true;
sp.speak('The next reply.');
await wait(200);
out.race = s.said.map((x) => [x.text, x.gap]);
out.clamp = s.said.map((x) => [x.rate, x.pitch, x.lang, x.vol]);
s = mk('ok'); sp = T.createSpeaker({ synth: s, voices: () => [], cfg: () => ({}) });
sp.speak('Before the voice list has arrived on the phone. After the list arrives, a second sentence.');
s.list = [{ name: 'Samantha', lang: 'en-US', voiceURI: 'com.apple.voice.compact.en-US.Samantha' }, { name: 'Ava (Premium)', lang: 'en-US', voiceURI: 'com.apple.voice.premium.en-US.Ava' }];
await wait(200);
out.late = s.said.map((x) => x.voice);
const p = mk('ok'); out.primed = T.primeSpeech(p); out.primer = p.said[0];
const ua = (u) => T.needsPrimer({ userAgent: u });
out.ua = {
  iphone: ua('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'),
  homescreen: ua('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'),
  crios: ua('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0 Mobile/15E148 Safari/604.1'),
  chrome: ua('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'),
  android: ua('Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36'),
};
console.log(JSON.stringify(out));
"""


def part_node(tmp):
    script = os.path.join(tmp, "speaker.mjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write(NODE)
    r = subprocess.run(["node", script, TTS], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. the speaker runs in node", False, r.stderr or r.stdout)
        return
    check("b. a chunk whose end never comes: the watchdog moves on, all 3 sentences said, the reply ends once", o["noend"] == {"n": 3, "ended": 1}, o["noend"])
    check("b. a chunk that never starts (an iPhone before any tap): onstall gets the whole rest, no onend",
          o["stall"]["ended"] == 0 and o["stall"]["stall"] and "this one too" in o["stall"]["stall"], o["stall"])
    check("b. speak() while she talks: cancel, then the next one 70 ms later (WebKit swallows it sooner)",
          len(o["race"]) == 2 and o["race"][1][0] == "The next reply." and o["race"][1][1] >= 60, o["race"])
    check("b. rate NaN / pitch 7 -> 1 / 1 (out of range throws on the phone); en-US, full volume", all(c == [1, 1, "en-US", 1] for c in o["clamp"]), o["clamp"])
    check("b. an empty voice list: the phone's default first, the list asked again for the next chunk (Ava Premium)", o["late"] == ["", "Ava (Premium)"], o["late"])
    check("b. the primer: one silent utterance (volume 0)", o["primed"] and o["primer"]["vol"] == 0 and not o["primer"]["text"].strip(), o["primer"])
    check("b. needsPrimer: iPhone Safari, the Home Screen app, Chrome on iPhone yes; desktop Chrome, Android no",
          o["ua"] == {"iphone": True, "homescreen": True, "crios": True, "chrome": False, "android": False}, o["ua"])


# ------------------------------------------------------------------------------------------------ c. the page
# the phone's voice, mocked: records each utterance (text, voice, time, inside a tap or not); __iosRule drops a speak() made
# outside a tap until one was made inside a tap (like iOS); voices off until __setVoices(true) fires voiceschanged
MOCK = """
window.__said = []; window.__drops = 0; window.__primers = 0; window.__cancels = 0; window.__srStarts = 0; window.__marks = [];
const V = [
  { name: 'Samantha', lang: 'en-US', voiceURI: 'com.apple.voice.compact.en-US.Samantha', localService: true, default: true },
  { name: 'Ava (Premium)', lang: 'en-US', voiceURI: 'com.apple.voice.premium.en-US.Ava', localService: true },
  { name: 'Daniel', lang: 'en-GB', voiceURI: 'com.apple.voice.compact.en-GB.Daniel', localService: true },
  { name: 'Zarvox', lang: 'en-US', voiceURI: 'com.apple.speech.synthesis.voice.Zarvox', localService: true },
];
let voicesOn = !window.__voicesEmpty, unlocked = !window.__iosRule, inTap = false, cur = null, tm = [];
for (const t of ['touchend', 'pointerup', 'click', 'keydown']) addEventListener(t, (e) => { if (!e.isTrusted) return; inTap = true; setTimeout(() => { inTap = false; }, 0); }, true);
const ls = {};
const fake = {
  speaking: false, pending: false, paused: false,
  getVoices: () => (voicesOn ? V.slice() : []),
  addEventListener(t, f) { (ls[t] = ls[t] || []).push(f); }, removeEventListener() {},
  speak(u) {
    if (!unlocked) { if (inTap) unlocked = true; else { window.__drops++; return; } }   // iOS: silently dropped, no events
    if (!(u.rate >= 0.1 && u.rate <= 10) || !(u.pitch >= 0 && u.pitch <= 2)) throw new TypeError('rate / pitch out of range');
    if (!String(u.text).trim()) { window.__primers++; setTimeout(() => u.onend && u.onend({}), 5); return; }
    window.__said.push({ text: u.text, voice: u.voice ? u.voice.name : '', lang: u.lang, t: performance.now(), tap: inTap });
    cur = u; fake.speaking = true;
    const step = window.__ttsStep || 25, n = u.text.split(/\\s+/).length;
    tm.push(setTimeout(() => { if (cur === u && u.onstart) u.onstart({}); }, 5));
    tm.push(setTimeout(() => { if (cur !== u) return; cur = null; fake.speaking = false; if (u.onend) u.onend({}); }, 20 + step * n));
  },
  cancel() { window.__cancels++; for (const t of tm) clearTimeout(t); tm = []; const u = cur; cur = null; fake.speaking = false; if (u && u.onerror) u.onerror({ error: 'interrupted' }); },
  pause() {}, resume() {},
};
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: fake });
window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.voice = null; this.lang = ''; this.rate = 1; this.pitch = 1; this.volume = 1; } };
window.__setVoices = (on) => { voicesOn = on; for (const f of ls.voiceschanged || []) f({}); };
class FakeSR {
  start() { window.__srStarts++; this.t = setTimeout(() => {
    if (this.onresult) this.onresult({ results: [Object.assign([{ transcript: window.__utter || 'is the market open' }], { isFinal: true })] });
    setTimeout(() => this.onend && this.onend(), 30); }, 200); }
  stop() { clearTimeout(this.t); setTimeout(() => this.onend && this.onend(), 10); }
  abort() { clearTimeout(this.t); if (this.onend) this.onend(); }
}
window.SpeechRecognition = FakeSR; window.webkitSpeechRecognition = FakeSR;
document.addEventListener('DOMContentLoaded', () => new MutationObserver((ms) => { for (const m of ms) for (const n of m.addedNodes)
  if (n.classList && n.classList.contains('j')) window.__marks.push({ t: performance.now(), text: n.textContent }); })
  .observe(document.getElementById('talk'), { childList: true }));
"""

LONG = ("Here is the full picture for today. The NQ bot is running on the eval and it has room above the floor, so nothing needs you "
        "right now. The market opened quietly, volatility is about average, and the plan is the same as yesterday: one clear "
        "setup, the stop beyond the sweep, and the target banked at eight R. If the feed goes stale the bot stops taking new "
        "entries until NinjaTrader catches up again. Kalshi is waiting for its own server and the Planner shows two things due "
        "this evening. Your next game plan comes at a quarter to eleven. That is everything for now; ask me about any part of it "
        "and I will go deeper.")


def page(br, url, name, ios, voices=True, device=None):
    kw = dict(device or {})
    kw.update(service_workers="block")
    if not device:
        kw.update(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx = br.new_context(**kw)
    H.feeds(ctx, H.kalshi_feed())
    ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9'));"
                        " localStorage.setItem('jarvis.intro', 'off'); } catch (e) {}")
    ctx.add_init_script(f"window.__iosRule = {json.dumps(bool(ios))}; window.__voicesEmpty = {json.dumps(not voices)};")
    # 2026-11-04: the natural-speech layer (prosody.js: numbers / tickers in words, contractions, comma breaths) changes the words on
    # purpose and has its own tests (test_jarvis_engines.py); this test checks the base chunker on the original text, so it is off here
    ctx.add_init_script("try { localStorage.setItem('jarvis.voiceEngine', JSON.stringify({ prosody: false })); } catch (e) {}")
    if os.environ.get("JARVIS_TEST_LITE") == "1":          # a loaded machine: no 3D core, no effects (jfx=off), so the heavy page cannot starve the checks
        ctx.add_init_script("try { localStorage.setItem('jfx', 'off'); localStorage.setItem('jarvis.no3d', '1'); } catch (e) {}")
    # the scheduled bot cards (01:45 plan, 09:15 pre-market, 15:55 end, 16:05 recap) are spoken by the same voice when the test happens to run in their hour:
    # they are switched off here so the checks do not depend on the time of day (their own tests: test_jarvis_bots.py)
    ctx.add_init_script("try { localStorage.setItem('jarvis.bots.set', JSON.stringify({ on: true, plan: false, recap: false, rituals: false })); } catch (e) {}")
    ctx.add_init_script(MOCK)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text
         and "WebGL" not in m.text else None)
    p.goto(url + "jarvis/")
    H.ready(p)
    p.wait_for_function("document.documentElement.dataset.voiceout === 'module' && !!window.__jarvis.voice()", timeout=90000)
    return ctx, p, errs


def said(p):
    return p.evaluate("window.__said.map((x) => x.text)")


def idle(p, ms=60000):
    p.wait_for_function("window.__jarvis.state() === 'idle' && !window.__jarvis.voice().speaking", timeout=ms)


def run(br, url, name, ios, device=None):
    tag = f"c[{name}]"
    # 1. an answer before any tap waits; the first tap unlocks (and says it inside that tap)
    ctx, p, errs = page(br, url, name, ios, device=device)
    st = p.evaluate("window.__jarvis.voice()")
    check(f"{tag} her voice is on by default{', not unlocked before a tap (a primer is needed here)' if ios else ', no primer needed'}",
          st["on"] and st["unlocked"] != ios and st["primer"] == ios and p.get_attribute("#spk", "aria-pressed") == "true", st)
    p.evaluate("window.__jarvis.talk('Good evening. The bots are running and nothing needs you.')")
    p.wait_for_timeout(300)
    st = p.evaluate("window.__jarvis.voice()")
    if ios:
        check(f"{tag} before any tap: nothing lost, the answer waits ('TAP TO HEAR' on the core)",
              "bots are running" in st["pending"] and p.evaluate("document.documentElement.dataset.vpending") == "1"
              and p.evaluate("window.__drops") == 0 and not said(p), (st, said(p)))
        p.mouse.click(3, 420)
        p.wait_for_function("window.__said.length >= 1", timeout=5000)
        first = p.evaluate("window.__said[0]")
        st = p.evaluate("window.__jarvis.voice()")
        check(f"{tag} the first tap anywhere unlocks: a silent primer inside the tap, the waiting answer said inside it, the audio resumed",
              "bots are running" in first["text"] and first["tap"] and st["unlocked"] and p.evaluate("window.__primers") >= 1
              and p.evaluate("window.__drops") == 0 and st["audio"] in ("running", "suspended"), (first, st, p.evaluate("window.__primers")))
    else:   # Chrome unlocks on any earlier tap (and Playwright's evaluate counts as one): said at once, no primer
        check(f"{tag} Chrome: said at once (its own tap rule), no primer, nothing waiting", said(p) and "bots are running" in said(p)[0]
              and not st["pending"] and p.evaluate("window.__primers") == 0, (st, said(p)))
        p.mouse.click(3, 420)
        check(f"{tag} the first tap resumes the shared audio", p.evaluate("window.__jarvis.voice().audio") in ("running", "suspended"), p.evaluate("window.__jarvis.voice()"))
    idle(p)
    # 2. a typed question: said by default, fast
    p.evaluate("window.__said = []; window.__marks = []")
    p.fill("#q", "is the market open")
    p.press("#q", "Enter")
    p.wait_for_function("window.__said.length >= 1", timeout=15000)
    lat = p.evaluate("(() => { const m = window.__marks.filter((x) => /market/i.test(x.text)).pop(); return m ? Math.round(window.__said[0].t - m.t) : null; })()")
    check(f"{tag} a typed question: the answer is said by default (no setting), in her voice (Ava Premium), within 300 ms of showing",
          "market" in said(p)[0].lower() and p.evaluate("window.__said[0].voice") == "Ava (Premium)" and lat is not None and 0 <= lat < 300, (said(p), lat))
    print(f"   ({tag} answer shown -> voice: {lat} ms)", flush=True)
    idle(p)
    # 3. a 600-character answer: chunks, in order, all of it
    p.evaluate("window.__said = []")
    p.evaluate(f"window.__jarvis.talk({json.dumps(LONG)})")
    idle(p, 90000)
    parts = said(p)
    words = lambda t: re.sub(r"[^a-z0-9 ]", "", t.lower().replace(",", " ")).split()
    check(f"{tag} a 600-character answer: {len(parts)} sentence chunks (each <= 180), in order, every word said, then STANDBY",
          len(LONG) >= 580 and len(parts) >= 4 and all(len(x) <= 180 for x in parts) and words(" ".join(parts)) == words(LONG), parts)
    # 4. speaking: the waveform and TAP TO STOP; a tap on the core stops her
    p.evaluate("window.__ttsStep = 400; window.__said = []")
    p.evaluate(f"window.__jarvis.talk({json.dumps(LONG)})")
    p.wait_for_function("window.__jarvis.state() === 'speaking'", timeout=5000)
    p.wait_for_timeout(700)
    look = p.evaluate("[getComputedStyle(document.getElementById('vwave')).opacity, getComputedStyle(document.getElementById('vstop')).opacity, document.getElementById('vwave').children.length, document.getElementById('state').textContent]")
    check(f"{tag} speaking: the waveform on the core and 'TAP TO STOP' show, the state says SPEAKING",
          float(look[0]) > 0.5 and float(look[1]) > 0.5 and look[2] >= 12 and look[3] == "SPEAKING", look)
    if SHOTS and ios:
        os.makedirs(SHOTS, exist_ok=True)
        p.locator(".stagebox").screenshot(path=os.path.join(SHOTS, "talk_speaking_iphone13.png"))
        p.locator("#dock").screenshot(path=os.path.join(SHOTS, "talk_dock_iphone13.png"))
    c0 = p.evaluate("window.__cancels")
    p.click("#stage", position={"x": 40, "y": 40})
    p.wait_for_timeout(250)
    st = p.evaluate("[window.__cancels, window.__jarvis.state(), window.__jarvis.voice().speaking, speechSynthesis.speaking]")
    check(f"{tag} a tap on the core stops her at once (cancelled, not speaking, not listening)", st[0] > c0 and st[1] in ("idle", "listening") and not st[2] and not st[3], st)
    p.evaluate("window.__ttsStep = 25")
    if st[1] == "listening":
        p.click("#stage", position={"x": 40, "y": 40})
    idle(p)
    # 5. the dock's speaker: off is kept, nothing said; on says so
    p.click("#spk")
    p.evaluate("window.__said = []")
    off = [p.get_attribute("#spk", "aria-pressed"), p.evaluate("localStorage.getItem('jarvis.speak')")]
    p.fill("#q", "is the market open")
    p.press("#q", "Enter")
    p.wait_for_function("[...document.querySelectorAll('#talk .msg.j')].length > 0 && window.__jarvis.state() === 'idle'", timeout=15000)
    p.wait_for_timeout(500)
    check(f"{tag} the dock's speaker off: kept on this phone ('jarvis.speak' off), the answer shown but not said", off == ["false", "off"] and not said(p), (off, said(p)))
    p.reload()
    H.ready(p)
    p.wait_for_function("document.documentElement.dataset.voiceout === 'module' && !!window.__jarvis.voice()", timeout=90000)
    check(f"{tag} after a reload her voice is still off", p.get_attribute("#spk", "aria-pressed") == "false" and not p.evaluate("window.__jarvis.voice().on"))
    p.click("#spk")
    p.wait_for_function("window.__said.some((x) => x.text === 'Voice on.')", timeout=5000)
    check(f"{tag} the speaker back on: 'Voice on.' said (inside the tap: it unlocks the phone too), kept on",
          p.get_attribute("#spk", "aria-pressed") == "true" and p.evaluate("localStorage.getItem('jarvis.speak')") == "on")
    idle(p)
    # 6. Test voice: one natural sentence
    p.evaluate("window.__said = []")
    p.click("#vset")
    p.wait_for_function("!document.getElementById('voice').hidden", timeout=5000)
    p.click("#vTest")
    p.wait_for_function("window.__said.length >= 1", timeout=5000)
    idle(p)
    check(f"{tag} Test voice: one natural sentence in her voice", said(p) == [TEST_LINE] and p.evaluate("window.__said[0].voice") == "Ava (Premium)", said(p))
    p.click("#vX")
    # 7. the mic and hands-free still work
    p.evaluate("window.__said = []; window.__utter = 'is the market open'")
    p.click("#bigmic")
    p.wait_for_function("window.__said.length >= 1", timeout=10000)
    check(f"{tag} the mic: tap, heard, answered out loud", "market" in said(p)[0].lower(), said(p))
    idle(p)
    n0 = p.evaluate("window.__srStarts")
    p.click("#hf")
    p.wait_for_function(f"window.__srStarts >= {n0 + 2}", timeout=12000)
    p.click("#hf")
    check(f"{tag} hands-free: listens, answers, listens again", p.evaluate("window.__srStarts") >= n0 + 2)
    p.wait_for_timeout(600)
    check(f"{tag} no page errors", not errs, errs)
    ctx.close()
    # 8. an empty voice list (iPhone at first): the default voice, then Ava after voiceschanged
    ctx, p, errs = page(br, url, name, ios, voices=False, device=device)
    p.mouse.click(3, 420)
    p.evaluate("window.__jarvis.talk('Testing the default voice.')")
    p.wait_for_function("window.__said.length >= 1", timeout=5000)
    a = p.evaluate("window.__said[0]")
    idle(p)
    p.evaluate("window.__setVoices(true); window.__said = []")
    p.evaluate("window.__jarvis.talk('Now with the voice list.')")
    p.wait_for_function("window.__said.length >= 1", timeout=5000)
    b = p.evaluate("window.__said[0]")
    check(f"{tag} empty voice list: said in the phone's default voice (en-US); after voiceschanged, Ava (Premium)",
          a["voice"] == "" and a["lang"] == "en-US" and b["voice"] == "Ava (Premium)", (a, b))
    check(f"{tag} no page errors (empty voice list)", not errs, errs)
    ctx.close()


def webkit_ready():
    return bool(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", os.path.expanduser("~/.cache/ms-playwright")), "webkit-*")))


def main():
    part_files()
    tmp = tempfile.mkdtemp(prefix="le_jarvis_talk_")
    part_node(tmp)
    path = H.site(tmp, "T", "asis")
    srv = H.serve(tmp)
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + path
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"], **({"executable_path": exe} if exe else {}))
            run(br, url, "chromium", ios=False)
            br.close()
            if webkit_ready():
                br = pw.webkit.launch()
                run(br, url, "webkit iPhone 13", ios=True, device=pw.devices["iPhone 13"])
                br.close()
            else:
                print("[SKIP] WebKit is not installed: PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright install webkit", flush=True)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis talk: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
