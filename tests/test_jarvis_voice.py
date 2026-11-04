"""Jarvis VOICE MODE (tools/web_public/jarvis/voice-mode.js, owner 2026-11-03: "like the movie J.A.R.V.I.S."): the full-screen
conversation. Runs the real Jarvis page (the folder as it is: the real brain, the real 3D core) in Chromium with a fake mic
(--use-fake-device-for-media-stream: a tone the analyser hears), a mocked speech recognizer and a mocked phone voice that
reports its word timing, and checks:
  a. the files: the module parses, exports its parts, Safari 16 safe; in the worker's SHELL (jarvis-v14); the shell loads it
     after the start, never as part of it
  b. the pure parts in node: the voice ranking (tts.js, owner 2026-11-03 "a female voice": Ava premium first, a natural female
     voice over any male one, the owner's pick kept, novelty voices never),
     the holographic cards (copied from the reply's cards and "Name: $x" lines); the brain's "voice mode" / "exit voice mode"
     controls and its farewell flag
  c. entering: the Voice mode tile, "Jarvis, voice mode" typed (a spoken entry), holding the big mic; the core goes full
     screen (the Jarvis screen's core waits behind), the greeting in her best voice (Ava premium), the mic analyser only after a tap
  d. a turn: mocked recognition -> the brain's spoken answer in the captions (word by word, as the voice reports), the same
     words said (in sentence chunks, one after the other), the reply also kept in the Jarvis chat; listening again after; the cards of the numbers cited float out;
     the HUD arc shows the system verdict; the core reacts to the mic (level up while you talk)
  e. barge-in: a tap while Jarvis speaks stops the voice at once and listens
  f. leaving: END, "exit voice mode", "goodbye", going out of sight: the mic's tracks stopped, the audio closed, recognition
     aborted, the Jarvis screen's core back
  g. no recognition (a Home Screen app): the same screen with a type-to-talk field, said once per launch; the recognizer
     refusing the mic switches to it too
  h. reduce motion and 3D effects Off: no animation loop, no mic analyser, everything shown at once; the voice pick is kept
  i. no page errors anywhere
    python -X utf8 -m tests.test_jarvis_voice      (temp folder + a local server; nothing else touched; ~1-2 min)
Screenshots: research/handoff/2026-11-03/voice/ (set JARVIS_VOICE_SHOTS=<folder> to change, '' to skip).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from tests import test_jarvis_hub as H

ROOT = H.ROOT
JV = H.JV
VM = os.path.join(JV, "voice-mode.js")
SHOTS = os.environ.get("JARVIS_VOICE_SHOTS", os.path.join(ROOT, "research", "handoff", "2026-11-03", "voice"))
RES = []


def flat(t):
    """the words of a line (the voice may add a comma for a breath)"""
    return " ".join(str(t or "").replace(",", " ").split())


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


# the phone's speech and mic, mocked: a recognizer that hears window.__utter (modes: talk | once | silent | hang | blocked), a voice
# that says each word 60 ms apart (__ttsStep ms when set) with word boundaries, and a record of every mic stream handed out
MOCKS = """
window.__said = []; window.__cancels = 0; window.__srStarts = 0; window.__srAborts = 0; window.__gum = []; window.__srMode = 'talk';
const VOICES = [
  { name: 'Samantha', lang: 'en-US', voiceURI: 'com.apple.voice.compact.en-US.Samantha', localService: true, default: true },
  { name: 'Ava (Premium)', lang: 'en-US', voiceURI: 'com.apple.voice.premium.en-US.Ava', localService: true },
  { name: 'Ava', lang: 'en-US', voiceURI: 'com.apple.voice.compact.en-US.Ava', localService: true },
  { name: 'Zarvox', lang: 'en-US', voiceURI: 'com.apple.speech.synthesis.voice.Zarvox', localService: true },
  { name: 'Daniel', lang: 'en-GB', voiceURI: 'com.apple.voice.compact.en-GB.Daniel', localService: true },
  { name: 'Daniel (Enhanced)', lang: 'en-GB', voiceURI: 'com.apple.voice.enhanced.en-GB.Daniel', localService: true },
  { name: 'Thomas', lang: 'fr-FR', voiceURI: 'com.apple.voice.compact.fr-FR.Thomas', localService: true },
];
let cur = null, timers = [];
const clear = () => { for (const t of timers) clearTimeout(t); timers = []; };
const fake = {
  speaking: false, pending: false, paused: false,
  getVoices: () => VOICES.slice(),
  addEventListener() {}, removeEventListener() {},
  speak(u) {
    window.__said.push({ text: u.text, voice: u.voice ? u.voice.name : '', rate: u.rate, pitch: u.pitch });
    cur = u; fake.speaking = true;
    const step = window.__ttsStep || 60, rx = /\\S+/g; let m, k = 0;
    while ((m = rx.exec(u.text))) { const ci = m.index, n = m[0].length; timers.push(setTimeout(() => { if (cur === u && u.onboundary) u.onboundary({ name: 'word', charIndex: ci, charLength: n }); }, 20 + step * k++)); }
    timers.push(setTimeout(() => { if (cur !== u) return; cur = null; fake.speaking = false; if (u.onend) u.onend({}); }, 60 + step * k));
  },
  cancel() { window.__cancels++; clear(); const u = cur; cur = null; fake.speaking = false; if (u && u.onerror) u.onerror({ error: 'interrupted' }); },
  pause() {}, resume() {},
};
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: fake });
window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.voice = null; this.lang = ''; this.rate = 1; this.pitch = 1; } };
class FakeSR {
  start() {
    window.__srStarts++; window.__sr = this; const me = this, mode = window.__srMode;
    if (mode === 'hang') return;
    if (mode === 'once') window.__srMode = 'hang';                  // one answer, then silence until the test says more
    if (mode === 'blocked') { setTimeout(() => { if (me.onerror) me.onerror({ error: 'not-allowed' }); if (me.onend) me.onend(); }, 60); return; }
    const words = String(window.__utter || 'is the market open');
    me.t1 = setTimeout(() => { if (mode === 'silent') return; if (me.onspeechstart) me.onspeechstart();
      if (me.onresult) me.onresult({ results: [Object.assign([{ transcript: words.split(' ').slice(0, 2).join(' ') }], { isFinal: false })] }); }, 150);
    me.t2 = setTimeout(() => {
      if (mode !== 'silent' && me.onresult) me.onresult({ results: [Object.assign([{ transcript: words }], { isFinal: true })] });
      setTimeout(() => me.onend && me.onend(), 30); }, window.__srMs || 500);
  }
  stop() { clearTimeout(this.t1); clearTimeout(this.t2); setTimeout(() => this.onend && this.onend(), 10); }
  abort() { window.__srAborts++; clearTimeout(this.t1); clearTimeout(this.t2); if (this.onend) this.onend(); }
}
if (window.__noSR) { window.SpeechRecognition = undefined; window.webkitSpeechRecognition = undefined; }
else { window.SpeechRecognition = FakeSR; window.webkitSpeechRecognition = FakeSR; }
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
  const gum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = (c) => gum(c).then((s) => { window.__gum.push(s); return s; });
}
window.__phases = [];
document.addEventListener('DOMContentLoaded', () => new MutationObserver(() => { const v = document.getElementById('vm');
  if (v && window.__phases[window.__phases.length - 1] !== v.dataset.phase) window.__phases.push(v.dataset.phase); })
  .observe(document.body, { attributes: true, subtree: true, attributeFilter: ['data-phase'] }));
window.__tracks = () => window.__gum.map((s) => s.getTracks().map((t) => t.readyState).join(',')).join('|');
"""

VMS = "window.__jarvis.vm()"


def new_page(br, no_sr=False, reduced=False, fx=None, width=390, height=844):
    ctx = br.new_context(viewport={"width": width, "height": height}, device_scale_factor=2, service_workers="block",
                         permissions=["microphone"], reduced_motion="reduce" if reduced else "no-preference")
    H.feeds(ctx, H.kalshi_feed())
    ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9'));"
                        " localStorage.setItem('jarvis.intro', 'off'); } catch (e) {}")
    if fx:
        ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
    if no_sr:
        ctx.add_init_script("window.__noSR = true;")
    ctx.add_init_script(MOCKS)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    return ctx, p, errs


def start(p, url):
    p.goto(url + "jarvis/")
    H.ready(p)
    p.wait_for_function("document.documentElement.dataset.voice === 'module'", timeout=20000)


def vm(p):
    return p.evaluate(VMS) or {}


def wait_phase(p, phase, timeout=15000):
    try:
        p.wait_for_function(f"(() => {{ const s = {VMS}; return !!s && s.open && s.phase === '{phase}'; }})()", timeout=timeout, polling=50)
    except Exception:
        print("   (waiting for", phase, "; phases:", p.evaluate("window.__phases.slice(-12)"), "; voice mode:", vm(p), "; said:", p.evaluate("window.__said.map((x) => x.text.slice(0, 50))"), ")", flush=True)
        raise


def shot(p, name):
    if not SHOTS:
        return
    os.makedirs(SHOTS, exist_ok=True)
    p.screenshot(path=os.path.join(SHOTS, name))


# ------------------------------------------------------------------------------------------------ a. files
def part_files():
    src = open(VM, encoding="utf-8").read()
    ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
    check("a. voice-mode.js parses as an ES module", ok.returncode == 0, ok.stderr)
    check("a. it exports createVoiceMode, bestVoice, voiceChoices, voiceScore, fragmentsOf, VOICE_KEY",
          all(f"export function {f}(" in src for f in ("createVoiceMode", "bestVoice", "voiceChoices", "voiceScore", "fragmentsOf"))
          and "export const VOICE_KEY = 'jarvis.vmVoice';" in src)
    imports = re.findall(r"^\s*import .* from '([^']+)';", src, re.M)
    check("a. Safari 16 safe: no regex lookbehind, one import (./tts.js, the shared voice), no network, no ?? / ?. / .at()",
          "(?<" not in src and imports == ["./tts.js"] and len(re.findall(r"^\s*import ", src, re.M)) == 1 and "fetch(" not in src
          and "XMLHttpRequest" not in src and "??" not in src and "?." not in src and ".at(" not in src, imports)
    check("a. the mic only from a tap (getUserMedia in ensureMic, called from the taps), released on close (tracks stopped, context closed)",
          src.count("getUserMedia(") == 1 and "t.stop()" in src and "actx.close()" in src and "releaseMic();" in src[src.index("function close("):])
    sw = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    check("a. worker jarvis-v24 saves voice-mode.js (and jarvis.css?v=j13)", "const CACHE = 'jarvis-v24';" in sw and "'./voice-mode.js'" in sw and "'./jarvis.css?v=j13'" in sw)
    page = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    check("a. the shell loads it after the start (bootDone + 1.5 s, or at first use), never in the start's own list",
          "load('voice', './voice-mode.js'" in page and "bootDone.then(() => setTimeout(voiceMod, 1500));" in page
          and "voice-mode" not in page[page.index("const ready = {"):page.index("const within =")])
    check("a. one turn shared by the Jarvis screen and voice mode (answer()), no second brain call path",
          "async function answer(t, voice)" in page and "answer: (t) => answer(t, true).then((x) => x.r)" in page and page.count("await think(") == 1)


# ------------------------------------------------------------------------------------------------ b. pure parts in node
NODE_PURE = r"""
import { pathToFileURL } from 'node:url';
const m = await import(pathToFileURL(process.argv[2]).href);
const b = await import(pathToFileURL(process.argv[3]).href);
const V = (name, lang, uri) => ({ name, lang, voiceURI: uri || name, localService: true });
const L = [V('Samantha', 'en-US', 'com.apple.voice.compact.en-US.Samantha'), V('Zarvox', 'en-US'), V('Daniel', 'en-GB', 'com.apple.voice.compact.en-GB.Daniel'),
  V('Daniel (Enhanced)', 'en-GB', 'com.apple.voice.enhanced.en-GB.Daniel'), V('Thomas', 'fr-FR'), V('Karen', 'en-AU')];
const P = [V('Daniel (Premium)', 'en-GB', 'com.apple.voice.premium.en-GB.Daniel'), V('Ava', 'en-US', 'com.apple.voice.compact.en-US.Ava'),
  V('Ava (Premium)', 'en-US', 'com.apple.voice.premium.en-US.Ava'), V('Bubbles', 'en-US'), ...L];
const out = {
  best: m.bestVoice(L).name, premium: m.bestVoice(P).name, saved: m.bestVoice(L, 'Karen').name, gone: m.bestVoice(L, 'Nobody').name,
  saidNovelty: m.bestVoice(L, 'Zarvox').name, maleOnly: (m.bestVoice([V('Daniel', 'en-GB'), V('Zarvox', 'en-US')]) || {}).name,
  usOnly: (m.bestVoice([V('Samantha', 'en-US'), V('Zarvox', 'en-US')]) || {}).name, none: m.bestVoice([V('Thomas', 'fr-FR')]),
  pchoices: m.voiceChoices(P).map((v) => v.name),
  choices: m.voiceChoices(L).map((v) => v.name),
  frText: m.fragmentsOf({ text: 'Zlarior: $1,106 of room above the floor ($48,168).\nATLAS: $750 of room.\nLive feed 2 min old.' }),
  frCards: m.fragmentsOf({ text: 'x', cards: [{ title: 'Zlarior', kv: [['Today', '+$213'], ['Room', '$1,106'], ['To target', '$3,726']] }, 'plain'] }),
  frNone: m.fragmentsOf({ text: 'All quiet. Nothing needs you.' }), frBad: m.fragmentsOf(null),
};
const brain = b.createBrain({ getFacts: () => ({ now: Date.now(), market: { open: true, text: 'open' } }), now: () => new Date() });
const ask = async (q) => { const r = await brain.ask(q); return { c: r.control || '', end: !!r.end, speak: r.speak }; };
out.on = await ask('Jarvis, voice mode'); out.on2 = await ask('start voice mode'); out.off = await ask('exit voice mode');
out.off2 = await ask('voice mode off'); out.bye = await ask('goodbye'); out.stop = await ask('stop'); out.unmute = await ask('voice on');
console.log(JSON.stringify(out));
"""


def part_pure(tmp):
    script = os.path.join(tmp, "pure.mjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write(NODE_PURE)
    r = subprocess.run(["node", script, VM, os.path.join(JV, "brain.js")], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. the pure parts run in node", False, r.stderr or r.stdout)
        return
    check("b. voice: a female voice first (Samantha over Daniel Enhanced); Ava (Premium) over compact Ava and a premium male voice; never Zarvox / Bubbles; none English = the phone's default",
          o["best"] == "Samantha" and o["premium"] == "Ava (Premium)" and o["usOnly"] == "Samantha" and o["none"] is None
          and o["maleOnly"] == "Daniel" and o["pchoices"][:2] == ["Ava (Premium)", "Ava"] and "Bubbles" not in o["pchoices"], o)
    check("b. voice: the owner's pick is kept while the phone has it, else the best; a novelty pick is never used",
          o["saved"] == "Karen" and o["gone"] == "Samantha" and o["saidNovelty"] == "Samantha", o)
    check("b. voice: the choices are English only, best first, no novelty voice", o["choices"][:2] == ["Samantha", "Karen"]
          and "Zarvox" not in o["choices"] and "Thomas" not in o["choices"], o["choices"])
    check("b. cards from the text: 'Zlarior · room  $1,106', 'ATLAS · room  $750' (copied as written, nothing computed)",
          o["frText"] == [{"k": "Zlarior · room", "v": "$1,106"}, {"k": "ATLAS · room", "v": "$750"}], o["frText"])
    check("b. cards from the reply's cards first (two rows each), a plain line never a card, nothing from a reply without numbers",
          o["frCards"] == [{"k": "Zlarior · Today", "v": "+$213"}, {"k": "Zlarior · Room", "v": "$1,106"}] and o["frNone"] == [] and o["frBad"] == [], o)
    check("b. the brain: 'Jarvis, voice mode' / 'start voice mode' -> control voice_mode; 'exit voice mode' / 'voice mode off' -> voice_mode_off",
          o["on"]["c"] == "voice_mode" and o["on2"]["c"] == "voice_mode" and o["off"]["c"] == "voice_mode_off" and o["off2"]["c"] == "voice_mode_off", o)
    check("b. the brain: 'goodbye' is a farewell (end) and still said; 'stop' and 'voice on' unchanged",
          o["bye"]["end"] and o["bye"]["speak"] and o["stop"]["c"] == "stop" and o["unmute"]["c"] == "unmute", o)


# ------------------------------------------------------------------------------------------------ c-f. the conversation
def run_main(br, url):
    ctx, p, errs = new_page(br)
    start(p, url)
    home_core = p.evaluate("!!window.__jarvis.core() || document.getElementById('coreSlot').children.length > 0")
    check("c. before: Voice mode is a quick-action tile; voice mode closed, no mic asked", p.locator('#qa [data-qa="voice"]').count() == 1
          and not vm(p).get("open") and p.evaluate("window.__gum.length") == 0, vm(p))
    p.evaluate("window.__utter = 'is the market open'; window.__srMs = 900; window.__srMode = 'once'")
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function("window.__phases.includes('speaking')", timeout=15000)      # the greeting (short: a busy machine can poll past it)
    s = vm(p)
    box = p.evaluate("(() => { const r = document.getElementById('vm').getBoundingClientRect(); return [r.width, r.height, innerWidth, innerHeight]; })()")
    check("c. the tile opens voice mode full screen, greeting first", s.get("open") and box[0] == box[2] and box[1] == box[3], (s, box))
    p.wait_for_function("window.__said.length >= 1", timeout=5000)
    g = p.evaluate("window.__said[0]")
    check("c. the greeting in her voice: Ava (Premium), at the voice's own pace and pitch", g["voice"] == "Ava (Premium)" and "listening" in g["text"].lower()
          and g["rate"] == 1 and g["pitch"] == 1, g)
    check("c. the 3D core goes full screen (mounted in voice mode, the Jarvis screen's core let go: one core at a time)",
          s.get("core") is not None and p.evaluate("document.getElementById('coreSlot').children.length") == 0, (s.get("core"), home_core))
    check("c. the button labels the voice", p.inner_text("#vmVoice").startswith("VOICE · AVA"), p.inner_text("#vmVoice"))
    # the mic analyser (asked inside the tile's tap) and the core reacting to it while listening
    wait_phase(p, "listening", 8000)
    p.wait_for_function(f"{VMS}.mic && {VMS}.micLive", timeout=8000)
    lv = []
    for _ in range(12):
        lv.append(vm(p).get("level", 0))
        p.wait_for_timeout(60)
    check("c. audio-reactive: the mic analyser runs (the fake mic's tone) and lifts the core's level while you talk",
          vm(p)["mic"] and max(lv) > 0.12 and vm(p)["loop"], lv)
    shot(p, "voice_listening.png")
    # d. one turn: mocked recognition -> the brain's answer in the captions, said word by word
    p.wait_for_function("window.__said.length >= 2", timeout=15000)
    wait_phase(p, "listening", 15000)
    said = p.evaluate("({ text: window.__said.slice(1).map((x) => x.text).join(' '), n: window.__said.length - 1 })")
    caps = p.evaluate("[document.getElementById('vmYou').textContent, document.getElementById('vmJar').textContent, "
                      "[...document.querySelectorAll('#vmJar .w')].every((w) => w.classList.contains('on')), "
                      "[...document.querySelectorAll('#talk .msg.j')].map((m) => m.textContent).pop() || '']")
    check("d. a turn: you said 'is the market open' (caption), the brain's spoken answer is the caption, word for word, all lit",
          caps[0] == "is the market open" and flat(caps[1]) == flat(said["text"]) and "market" in said["text"].lower() and caps[2], (caps, said))
    check("d. the reply is also kept in the Jarvis chat (the shell's answer(), the same brain)", "market" in caps[3].lower(), caps[3])
    check("d. turn-taking: listening again after the answer", vm(p)["phase"] == "listening" and p.evaluate("window.__srStarts") >= 2, vm(p))
    vd = p.evaluate("document.getElementById('vmVerdict').textContent")
    check("d. the HUD arc shows the system verdict (the bots' RUNNING), in its colour", vd.startswith("SYSTEM · RUNNING")
          and p.evaluate("document.getElementById('vm').dataset.verdict") == "ok", vd)
    # the numbers cited float out: 'how much room do I have' -> Zlarior · room $1,106
    p.evaluate("window.__utter = 'how much room do I have'; window.__ttsStep = 1200; window.__srMode = 'once'; window.__sr.stop()")
    p.wait_for_function("document.querySelectorAll('#vmFrags .vm-frag.on').length >= 1", timeout=20000)
    p.wait_for_timeout(900)
    frags = p.evaluate("[...document.querySelectorAll('#vmFrags .vm-frag')].map((f) => [f.textContent, f.classList.contains('on')])")
    check("d. holographic cards: 'ZLARIOR · ROOM $1,106' floats out as Zlarior is named",
          any("Zlarior" in f[0] and "room" in f[0].lower() and "$1,106" in f[0] and f[1] for f in frags), frags)
    p.wait_for_timeout(800)                         # the cards' flight (0.7 s) ends
    off = p.evaluate("[...document.querySelectorAll('#vmFrags .vm-frag.on')].map((f) => f.getBoundingClientRect())"
                     ".filter((r) => r.left < 0 || r.right > document.documentElement.clientWidth).length")
    check("d. every card stays on the phone's screen (none cut at the edges)", off == 0, off)
    shot(p, "voice_speaking_cards.png")
    # e. barge-in: a tap while Jarvis speaks
    wait_phase(p, "speaking", 5000)
    c0, n0 = p.evaluate("[window.__cancels, window.__srStarts]")
    p.click("#vmStage", position={"x": 60, "y": 60})
    wait_phase(p, "listening", 8000)
    c1, n1 = p.evaluate("[window.__cancels, window.__srStarts]")
    check("e. barge-in: a tap while Jarvis speaks stops the voice at once and listens", c1 > c0 and n1 > n0 and not vm(p)["speaking"]
          and not p.evaluate("speechSynthesis.speaking"), (c0, c1, n0, n1))
    p.evaluate("window.__ttsStep = 0; window.__srMode = 'hang'")
    # a tap while listening pauses; the VOICE button steps to the next voice and keeps it
    p.click("#vmStage", position={"x": 60, "y": 60})
    wait_phase(p, "idle", 8000)
    p.click("#vmVoice")
    p.wait_for_function("window.__said.some((x) => /at your service/.test(x.text))", timeout=5000)
    pick = p.evaluate("[localStorage.getItem('jarvis.vmVoice'), window.__said[window.__said.length - 1].voice]")
    pick.append(p.evaluate("JSON.parse(localStorage.getItem('jarvis.voiceCfg') || '{}').voice || ''"))
    check("h. the VOICE button: the next voice (Ava compact), said and kept on this phone for voice mode and the Jarvis screen", pick == ["Ava", "Ava", "Ava"], pick)
    # f. END: the mic released
    p.click("#vmX")
    p.wait_for_function(f"!{VMS}.open", timeout=8000)
    p.wait_for_timeout(300)
    s = vm(p)
    tr = p.evaluate("window.__tracks()")
    check("f. END: voice mode closed, every mic track stopped, the audio closed, recognition aborted, no voice",
          not s["open"] and tr and "live" not in tr and s["audio"] == "closed" and not s["mic"] and p.evaluate("window.__srAborts") >= 1
          and not p.evaluate("speechSynthesis.speaking") and p.locator("#vm").is_hidden(), (s, tr))
    p.wait_for_function("document.getElementById('coreSlot').children.length > 0", timeout=15000)
    check("f. the Jarvis screen's core is back", True)
    # c. entering by voice: "Jarvis, voice mode" (typed here: the same path as the hands-free mic), then "exit voice mode"
    p.evaluate("window.__srMode = 'talk'; window.__utter = 'exit voice mode'; window.__srMs = 500")
    p.fill("#q", "Jarvis, voice mode")
    p.press("#q", "Enter")
    p.wait_for_function(f"{VMS} && {VMS}.open", timeout=8000)
    check("c. 'Jarvis, voice mode' opens voice mode (the brain's control)", vm(p)["open"])
    p.wait_for_function(f"!{VMS}.open", timeout=15000)
    last = p.evaluate("window.__said[window.__said.length - 1].text")
    check("f. 'exit voice mode' said in voice mode: 'Standing by.', then it closes", last == "Standing by." and not vm(p)["open"], last)
    # c. hold the big mic: voice mode; the mic joins on the release (a tap)
    gum0 = p.evaluate("window.__gum.length")
    p.evaluate("window.__utter = 'goodbye'; window.__srMs = 1500")
    p.wait_for_timeout(700)                         # the chat's smooth scroll settles: the mic holds still under the finger
    p.evaluate("document.getElementById('bigmic').scrollIntoView({ block: 'center' })")
    p.wait_for_timeout(300)
    b = p.locator("#bigmic").bounding_box()
    p.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    p.mouse.down()
    p.wait_for_function(f"{VMS} && {VMS}.open", timeout=4000)
    p.wait_for_timeout(150)
    before_up = p.evaluate("window.__gum.length")
    p.mouse.up()
    p.wait_for_function(f"{VMS}.mic", timeout=6000)
    check("c. holding the big mic opens voice mode; the mic is asked only at the release (a tap), never before",
          before_up == gum0 and p.evaluate("window.__gum.length") == gum0 + 1, (gum0, before_up))
    p.wait_for_function(f"!{VMS}.open", timeout=20000)
    bye = p.evaluate("window.__said[window.__said.length - 1].text")
    check("f. 'goodbye': the farewell is said, then voice mode ends and lets the mic go", bye and bye != "Standing by." and "live" not in p.evaluate("window.__tracks()"), bye)
    # f. out of sight: voice mode lets the mic go
    p.evaluate("window.__srMode = 'hang'")
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function(f"{VMS}.open && {VMS}.mic", timeout=8000)
    p.evaluate("Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange'))")
    p.wait_for_function(f"!{VMS}.open", timeout=8000)
    tr = p.evaluate("window.__tracks()")
    p.evaluate("delete document.visibilityState; document.dispatchEvent(new Event('visibilitychange'))")
    check("f. Jarvis out of sight: voice mode closes and every mic track is stopped", "live" not in tr, tr)
    # another app opened from voice mode ("open planner") closes it first
    p.evaluate("window.__srMode = 'talk'; window.__utter = 'open planner'; window.__srMs = 500")
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function("window.__jarvis.active() === 'planner'", timeout=20000)
    check("f. 'open planner' in voice mode: the answer is said, voice mode closes, the Planner opens", not vm(p)["open"] and "live" not in p.evaluate("window.__tracks()"))
    check("i. no page errors (main run)", not errs, errs)
    ctx.close()


def run_no_sr(br, url):
    ctx, p, errs = new_page(br, no_sr=True)
    start(p, url)
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function(f"{VMS} && {VMS}.open && {VMS}.typing", timeout=8000)
    p.wait_for_function("window.__said.length >= 1", timeout=5000)
    note = p.evaluate("window.__said[0].text")
    check("g. no recognition (a Home Screen app): the same screen with a type-to-talk field, and Jarvis says so",
          p.locator("#vmType").is_visible() and "not available" in note and not vm(p)["recognition"], note)
    shot(p, "voice_type_fallback.png")
    p.fill("#vmQ", "is the market open")
    p.press("#vmQ", "Enter")
    p.wait_for_function("window.__said.length >= 2", timeout=15000)
    p.wait_for_function(f"{VMS}.phase === 'idle'", timeout=15000)
    caps = p.evaluate("[document.getElementById('vmYou').textContent, document.getElementById('vmJar').textContent, window.__said.slice(1).map((x) => x.text).join(' ')]")
    check("g. typed: the brain's answer in the captions and said out loud", caps[0] == "is the market open" and flat(caps[1]) == flat(caps[2]) and "market" in caps[2].lower(), caps)
    p.click("#vmX")
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function(f"{VMS}.open && {VMS}.typing", timeout=8000)
    p.wait_for_timeout(800)
    n = p.evaluate("window.__said.filter((x) => /not available/.test(x.text)).length")
    check("g. said once per launch (not again on the second visit)", n == 1, n)
    p.click("#vmX")
    check("i. no page errors (no recognition)", not errs, errs)
    ctx.close()
    # the recognizer refusing the mic (a Home Screen app on some iPhones): the type field, said once
    ctx, p, errs = new_page(br)
    start(p, url)
    p.evaluate("window.__srMode = 'blocked'")
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function(f"{VMS} && {VMS}.typing", timeout=10000)
    p.wait_for_function("window.__said.some((x) => /blocked/.test(x.text))", timeout=6000)
    check("g. recognition refused ('not-allowed'): the type field, said once", p.locator("#vmType").is_visible() and not vm(p)["recognition"], vm(p))
    p.click("#vmX")
    check("i. no page errors (recognition refused)", not errs, errs)
    ctx.close()


def run_motion(br, url):
    ctx, p, errs = new_page(br, reduced=True)
    start(p, url)
    p.evaluate("window.__srMode = 'hang'")
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function(f"{VMS} && {VMS}.open", timeout=8000)
    p.wait_for_function("window.__said.length >= 1", timeout=5000)
    p.wait_for_timeout(600)
    s = vm(p)
    check("h. reduce motion: no animation loop, no mic analyser (no getUserMedia), the captions shown at once, the core still",
          not s["loop"] and not s["motion"] and p.evaluate("window.__gum.length") == 0
          and p.evaluate("[...document.querySelectorAll('#vmJar .w')].every((w) => w.classList.contains('on'))")
          and (s["core"] is None or s["core"] == "mounted" or s["core"].get("reduced") or s["core"].get("running") is False), s)
    p.click("#vmX")
    check("i. no page errors (reduce motion)", not errs, errs)
    ctx.close()
    ctx, p, errs = new_page(br, fx="off")
    start(p, url)
    p.evaluate("window.__srMode = 'hang'")
    p.click('#qa [data-qa="voice"]')
    p.wait_for_function(f"{VMS} && {VMS}.open", timeout=8000)
    p.wait_for_timeout(600)
    s = vm(p)
    still = s["core"].get("running") is False and s["core"].get("reduced") if isinstance(s.get("core"), dict) else s.get("core") is None
    check("h. 3D effects Off: the core still (its flat frame, not running), no animation loop, no mic analyser",
          not s["loop"] and not s["motion"] and p.evaluate("window.__gum.length") == 0 and still, s)
    p.click("#vmX")
    check("i. no page errors (3D off)", not errs, errs)
    ctx.close()


def main():
    part_files()
    tmp = tempfile.mkdtemp(prefix="le_jarvis_voice_")
    part_pure(tmp)
    path = H.site(tmp, "C", "asis")
    srv = H.serve(tmp)
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + path
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = next(iter(sorted(__import__("glob").glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"]
            br = pw.chromium.launch(args=args, **({"executable_path": exe} if exe else {}))
            run_main(br, url)
            run_no_sr(br, url)
            run_motion(br, url)
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis voice mode: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
