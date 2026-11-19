"""Jarvis SOUNDS LIKE A PERSON (2026-11-18, owner: "Jarvis voice sucks, it sounds like a bot, it should sound like a person. I'm only
asking once to fix it." He picked Male, British). Node only, no browser, ~10 s:
  a. the files: speech-text.js / neural-voice.js / neural-voice-worker.js parse, Safari 16 safe (no lookbehind, no ?? / ?. / .at()),
     no console logging; the CDN files at exact versions (kokoro-js@1.2.1, @huggingface/transformers@3.5.1), the model from huggingface.co
     pinned to one commit; no cache name starts with 'jarvis-' (Jarvis's service worker deletes those on update); speech-text.js has no
     imports and no network
  b. the words a person says (speech-text.js): the owner's examples ($3,807, -$113, P&L, 25K, 6:45 PM), times, dates, money with cents
     and per month, prices read like a trader in a trade sentence, decimals, ranges, tickers and names in capitals, markdown / emoji / links
     never read, contractions; nothing left that a voice would read as a symbol or a digit
  c. the pieces the AI voice makes (sentences): a short first piece cut at a comma, never mid-phrase, every word kept in order
  d. the fallback order when the AI voice is not ready (tts.js voiceScore / bestVoice): a British man first (Premium > Enhanced > plain),
     then another British-sounding man, then a US man, then a woman; novelty voices never; no list yet = the phone's British default
  e. the one setting (neural-voice.js): AI voice (George) by default, iPhone voice, Off; older modes read as AI; the old female pick dropped once
  f. the engine with a fake worker: the one-time download's progress line, ready, the descriptor only when ready, audio as WAV with its
     length, short lines kept, a tap drops queued work, a reply too long for a slow phone goes to the iPhone voice, a crash = the iPhone
     voice and a 10-minute rest (unless he picks it again), 3 crashes = a day's rest
  g. the speaker with the AI voice (tts.js createSpeaker): every piece asked for at once, played in order with the words lit across each
     clip, the raw text normalized ("-$113"), a late piece -> the iPhone voice says only the rest, a tap aborts the work in flight
    python -X utf8 -m tests.test_jarvis_speech
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(name):
    return open(os.path.join(JV, name), encoding="utf-8").read()


# ------------------------------------------------------------------------------------------------ a. files
def part_files():
    for name in ("speech-text.js", "neural-voice.js", "neural-voice-worker.js"):
        src = read(name)
        ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
        check(f"a. {name} parses as an ES module", ok.returncode == 0, ok.stderr)
        check(f"a. {name}: Safari 16 safe (no lookbehind, no ?? / ?. / .at()), no console logging",
              "(?<" not in src and "??" not in src and not re.search(r"[\w)\]]\?\.[\w(\[]", src) and ".at(" not in src
              and not re.search(r"\bconsole\.(log|warn|error|info|debug)", src), name)
    st = read("speech-text.js")
    check("a. speech-text.js: no imports, no network", not re.search(r"^\s*import ", st, re.M) and "fetch(" not in st and not re.findall(r"https?://", st))
    nv = read("neural-voice.js")
    check("a. neural-voice.js imports only ./speech-text.js", re.findall(r"^\s*import .* from '([^']+)';", nv, re.M) == ["./speech-text.js"])
    cdn = re.findall(r"https://cdn\.jsdelivr\.net/npm/[^'\"`\s]+", nv)
    check("a. the CDN files: cdn.jsdelivr.net/npm at exact versions only (kokoro-js@1.2.1, @huggingface/transformers@3.5.1)",
          cdn and all(re.search(r"@\d+\.\d+\.\d+/", u) for u in cdn) and any("kokoro-js@1.2.1/" in u for u in cdn) and any("transformers@3.5.1/" in u for u in cdn), cdn)
    hosts = set(re.findall(r"https://([a-z0-9.-]+)", nv + read("neural-voice-worker.js")))
    check("a. hosts: only cdn.jsdelivr.net, huggingface.co (the model) and the local clip-cache key", hosts <= {"cdn.jsdelivr.net", "huggingface.co", "olympus.local"}, hosts)
    check("a. the model repo pinned to one commit (main is rewritten to it), q8 on WebAssembly",
          "const HF_REV = '1939ad2a8e416c0acfeecc08a694d14ef25f2231'" in nv and "dtype: 'q8', device: 'wasm'" in nv and "hfPin + url.slice(c.hfMain.length)" in read("neural-voice-worker.js"))
    names = re.findall(r"(?:cacheName|clipCache): '([^']+)'", nv)
    check("a. cache names never start with 'jarvis-' (Jarvis's service worker clears those on every update)", names and not any(n.startswith("jarvis-") for n in names), names)
    check("a. the progress line says the real size: \"Getting Jarvis's voice ready (one time, about 117 MB)\"",
          "approxMB: 117" in nv and "Getting Jarvis's voice ready (one time, about " in nv)


NODE = r"""
import { pathToFileURL } from 'node:url';
const dir = process.argv[2];
const imp = (f) => import(pathToFileURL(dir + '/' + f).href);
const S = await imp('speech-text.js'), N = await imp('neural-voice.js'), T = await imp('tts.js');
const out = [];
const ck = (name, ok, info) => out.push({ name, ok: !!ok, info: ok ? '' : JSON.stringify(info === undefined ? null : info) });
const say = (t) => S.speechText(t);
const has = (t, w) => say(t).toLowerCase().indexOf(w.toLowerCase()) >= 0;
const st0 = setTimeout;
const wait = (ms) => new Promise((ok) => st0(ok, ms));

// ---------------------------------------------------------------- b. the words
ck("b. the owner's examples: $3,807, -$113, P&L, 25K, 6:45 PM", say('$3,807') === 'Three thousand eight hundred and seven dollars.' && say('-$113') === 'Minus a hundred and thirteen dollars.'
  && say('P&L') === 'P and L.' && say('25K') === 'Twenty-five K.' && say('6:45 PM') === 'Six forty-five PM.', ['$3,807', '-$113', 'P&L', '25K', '6:45 PM'].map(say));
const T1 = [['9:30 AM', 'nine thirty AM'], ['10:00 AM', 'ten AM'], ['18:00 ET', 'six PM Eastern'], ['12:00 PM', 'noon'], ['9:05', "nine oh five"], ['at 5pm', 'five PM'], ['0:00', 'midnight']];
ck('b. times read naturally (9:30 AM, 10:00 AM, 18:00 ET, noon, 9:05, 5pm, midnight)', T1.every((x) => has(x[0], x[1])), T1.map((x) => say(x[0])));
const M1 = [['$12.50', 'twelve dollars and fifty cents'], ['~$1,250/mo', 'about twelve hundred and fifty dollars a month'], ['+$213 today', 'up two hundred and thirteen dollars today'],
  ['lost -$50', 'lost fifty dollars'], ['$0.50', 'fifty cents'], ['$1', 'one dollar'], ['made $1.2k', 'twelve hundred dollars'], ['$49,192.78', 'forty-nine thousand one hundred and ninety-two dollars and seventy-eight cents'],
  ['$1,025 room', 'a thousand and twenty-five dollars'], ['49,193 dollars', 'forty-nine thousand one hundred and ninety-three dollars'], ['minus 113 dollars', 'minus a hundred and thirteen dollars'],
  ['Builder 50K $91.80', 'fifty K ninety-one dollars and eighty cents']];
ck('b. money: cents, per month, up / minus, already-worded dollars, British "and"', M1.every((x) => has(x[0], x[1])), M1.filter((x) => !has(x[0], x[1])).map((x) => [x[0], say(x[0])]));
ck('b. the trade alert: prices read like a trader (twenty-four nine fifty-five), the 50K as "fifty K"',
  say('Zlarior just went long on the 50K. Stop is at 24,955, target 25,360.') === 'Zlarior just went long on the fifty K. Stop is at twenty-four nine fifty-five, target twenty-five three sixty.',
  say('Zlarior just went long on the 50K. Stop is at 24,955, target 25,360.'));
ck('b. prices with quarters (ES at 6,812.25), never trader-style outside a trade sentence', has('ES at 6,812.25.', 'sixty-eight twelve and a quarter') && has('25,360.75 stop', 'twenty-five three sixty and three quarters')
  && has('ATLAS funded is at 24,887 dollars.', 'twenty-four thousand eight hundred and eighty-seven dollars'), [say('ES at 6,812.25.'), say('ATLAS funded is at 24,887 dollars.')]);
const N1 = [['PF 1.85', 'profit factor one point eight five'], ['up 2.5%', 'two point five percent'], ['2-4 trades/week', 'two to four trades a week'], ['8R', 'eight R'], ['the 1st', 'first'],
  ['Nov 18', 'November the eighteenth'], ['2026-11-18', 'November the eighteenth, twenty twenty-six'], ['Wed Nov 18', 'Wednesday November the eighteenth'], ['7 min ago', 'seven minutes ago'],
  ['#2', 'number two'], ['3 trades', 'three trades'], ['113 sessions', 'a hundred and thirteen sessions'], ['silent for 3.5 hours', 'three and a half hours'],
  ['long 1 MNQ at 24,955.25', 'long one M N Q at twenty-four nine fifty-five and a quarter'], ['1.5M views', 'one point five million'], ['~2.3 $/market-day', 'about two dollars and thirty cents per market-day']];
ck('b. numbers, percent, ranges, R, ordinals, dates, minutes, "number two"', N1.every((x) => has(x[0], x[1])), N1.filter((x) => !has(x[0], x[1])).map((x) => [x[0], say(x[0])]));
const W1 = [['NQ opens', 'N Q opens'], ['MFFU rules', 'M F F U rules'], ['ATLAS is funded', 'Atlas is funded'], ['ZEUS is running', 'Zeus is running'], ['Open LE START on the PC', 'Open L E Start on the P C'],
  ['edge GREEN', 'edge Green'], ['PnL today', 'P and L today'], ['max DD', 'max drawdown'], ['the VIX', 'the vix']];
ck('b. tickers and names in capitals said the way a trader says them (N Q, M F F U, Atlas, L E Start)', W1.every((x) => has(x[0], x[1])), W1.filter((x) => !has(x[0], x[1])).map((x) => [x[0], say(x[0])]));
const md = say('## Today\n**Zlarior**: $49,193 · _room_ $1,025 😀 → see https://example.com/x `code` [the Board](https://x.y)\n- ATLAS ok');
ck('b. markdown, emoji, links and code are never read; a list line becomes its own sentence', !/[#*_`😀→\[\]()]|https?:/.test(md) && /a link/.test(md) && /the Board/.test(md) && /Atlas okay\.$/.test(md), md);
const all = ['ZEUS · Wed Nov 18 · PC ok | Zlarior 50K $49,193 ($3,807 to pass) · 25K #2 $25,000 ($1,500 to pass)', 'Good morning. NQ opens at 9:30 AM ET. **Today**: 2-4 trades/week, PF 1.85, ~$1,250/mo. 😀',
  'It is 18:00 ET. I do not see a setup. The PC reported 7 min ago.', 'Room 42% · VIX 18.5 · 3x size? x=2 @ 5 & more <b>', 'On 2026-11-18 you made $1.2k. Max DD $400. Balance $49,192.78.'].map(say);
ck('b. nothing a voice would read as a symbol or a digit is left ($ % & @ # * _ ~ | < > = digits)', all.every((t) => !/[$%&@#*_~|<>=\d]/.test(t)), all);
ck('b. how a person talks: contractions ("It\'s", "don\'t"), "Yes, it is." kept whole, "However," -> "But"',
  say('It is 18:00 ET. I do not see a setup.').indexOf("It's six PM Eastern. I don't see a setup.") === 0 && say('Yes, it is.') === 'Yes, it is.' && say('However, we wait.') === 'But we wait.', [say('It is 18:00 ET. I do not see a setup.'), say('Yes, it is.')]);
ck('b. numberWords / moneyWords / priceWords / timeWords building blocks', S.numberWords(3050) === 'three thousand and fifty' && S.numberWords(101000, { a: true }) === 'a hundred and one thousand'
  && S.moneyWords(-113) === 'a hundred and thirteen dollars' && S.priceWords(25045) === 'twenty-five oh forty-five' && S.priceWords(25300) === 'twenty-five three hundred'
  && S.timeWords(18, 30) === 'six thirty PM' && S.yearWords(2026) === 'twenty twenty-six', [S.numberWords(3050), S.priceWords(25045), S.timeWords(18, 30)]);

// ---------------------------------------------------------------- c. the pieces
const long = say("Here's where you stand. Zlarior 50K: $49,193, $1,025 of room, $3,807 to pass. ATLAS funded 25K: $24,887, and today it's -$113.");
const pcs = S.sentences(long, { first: 60, max: 220 });
const words = (t) => t.toLowerCase().replace(/[^a-z' -]/g, ' ').split(/\s+/).filter(Boolean);
ck('c. pieces: the first is the first sentence or its first clause (<= 60, cut at a comma), each <= 220, every word kept in order',
  pcs.length >= 3 && pcs[0].length <= 60 && pcs.every((p) => p.length <= 220) && JSON.stringify(words(pcs.join(' '))) === JSON.stringify(words(long)), pcs);
const p2 = S.sentences('Zlarior fifty K eval is at forty-nine thousand one hundred and ninety-three dollars, three thousand eight hundred and seven dollars to pass.', { first: 60 });
ck('c. a long first sentence is cut at its comma, never in the middle of a phrase', p2.length === 2 && /dollars,$/.test(p2[0]) && /^three thousand/.test(p2[1]), p2);
ck('c. a tiny piece rides with the next ("Yes." + the sentence); a single short line stays whole', S.sentences('Yes. The PC checked in just now.').length === 1 && S.sentences('Voice on.').join('|') === 'Voice on.', S.sentences('Yes. The PC checked in just now.'));

// ---------------------------------------------------------------- d. the fallback order
const V = (name, lang, uri) => ({ name, lang, voiceURI: uri || name, localService: true });
const best = (l) => (T.bestVoice(l) || {}).name || null;
const D1 = [
  [[V('Samantha', 'en-US', 'com.apple.voice.compact.en-US.Samantha'), V('Ava (Premium)', 'en-US', 'com.apple.voice.premium.en-US.Ava'), V('Daniel', 'en-GB', 'com.apple.voice.compact.en-GB.Daniel'), V('Zarvox', 'en-US')], 'Daniel'],
  [[V('Ava (Premium)', 'en-US', 'com.apple.voice.premium.en-US.Ava'), V('Daniel (Enhanced)', 'en-GB', 'com.apple.voice.enhanced.en-GB.Daniel'), V('Daniel', 'en-GB', 'com.apple.voice.compact.en-GB.Daniel'), V('Jamie (Premium)', 'en-GB', 'com.apple.voice.premium.en-GB.Jamie')], 'Jamie (Premium)'],
  [[V('Daniel', 'en-GB', 'com.apple.voice.compact.en-GB.Daniel'), V('Daniel (Enhanced)', 'en-GB', 'com.apple.voice.enhanced.en-GB.Daniel')], 'Daniel (Enhanced)'],
  [[V('Lee (Enhanced)', 'en-AU', 'com.apple.voice.enhanced.en-AU.Lee'), V('Daniel', 'en-GB', 'com.apple.voice.compact.en-GB.Daniel')], 'Daniel'],
  [[V('Evan (Enhanced)', 'en-US', 'com.apple.voice.enhanced.en-US.Evan'), V('Lee (Enhanced)', 'en-AU', 'com.apple.voice.enhanced.en-AU.Lee'), V('Ava (Premium)', 'en-US', 'com.apple.voice.premium.en-US.Ava')], 'Lee (Enhanced)'],
  [[V('Evan (Enhanced)', 'en-US', 'com.apple.voice.enhanced.en-US.Evan'), V('Ava (Premium)', 'en-US', 'com.apple.voice.premium.en-US.Ava')], 'Evan (Enhanced)'],
  [[V('Serena (Premium)', 'en-GB', 'com.apple.voice.premium.en-GB.Serena'), V('Samantha', 'en-US')], 'Serena (Premium)'],
  [[V('Google UK English Female', 'en-GB'), V('Google UK English Male', 'en-GB'), V('Google US English', 'en-US')], 'Google UK English Male'],
  [[V('Microsoft Sonia Online (Natural) - English (United Kingdom)', 'en-GB'), V('Microsoft Ryan Online (Natural) - English (United Kingdom)', 'en-GB')], 'Microsoft Ryan Online (Natural) - English (United Kingdom)'],
  [[V('Zarvox', 'en-US'), V('Fred', 'en-US'), V('Albert', 'en-US'), V('Thomas', 'fr-FR')], null],
];
ck('d. fallback order: British man (Premium > Enhanced > plain) > British-sounding man > US man > woman; novelty / not English never',
  D1.every((x) => best(x[0]) === x[1]), D1.map((x) => [best(x[0]), x[1]]));
ck('d. the choices list leads with the British men, never a novelty voice', (() => { const c = T.voiceChoices(D1[1][0]).map((v) => v.name); return c[0] === 'Jamie (Premium)' && c[1] === 'Daniel (Enhanced)' && c.indexOf('Ava (Premium)') === 3; })(), T.voiceChoices(D1[1][0]).map((v) => v.name));
{
  globalThis.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.rate = 1; this.pitch = 1; this.volume = 1; this.lang = ''; this.voice = null; } };
  const said = [], synth = { speaking: false, pending: false, paused: false, getVoices: () => [], cancel() {}, speak(u) { said.push({ text: u.text, lang: u.lang, voice: u.voice ? u.voice.name : '' }); st0(() => { if (u.onstart) u.onstart({}); st0(() => u.onend && u.onend({}), 2); }, 1); } };
  const sp = T.createSpeaker({ synth, voices: () => [], cfg: () => ({}) });
  sp.speak('No voice list yet on this phone.');
  await wait(60);
  ck("d. no voice list yet (an iPhone at first): the phone's own British default (en-GB), never the US one", said.length === 1 && said[0].lang === 'en-GB' && !said[0].voice, said);
}

// ---------------------------------------------------------------- e. the one setting
class Mem { constructor(o) { this.m = Object.assign({}, o || {}); } getItem(k) { return k in this.m ? this.m[k] : null; } setItem(k, v) { this.m[k] = String(v); } removeItem(k) { delete this.m[k]; } }
{
  const m0 = new Mem(), a = N.voiceMode(m0), b = N.setVoiceMode(m0, 'phone'), c = N.setVoiceMode(m0, 'off'), offKey = m0.getItem('jarvis.speak'), d = N.setVoiceMode(m0, 'ai'), e = N.setVoiceMode(m0, 'nope');
  const old = ['auto', 'cloud', 'device'].map((md) => N.voiceMode(new Mem({ 'jarvis.voiceEngine': JSON.stringify({ mode: md }) })));
  ck('e. the setting: AI voice by default; iPhone voice; Off (jarvis.speak off, the dock switch); back on; junk ignored; old auto / cloud / device = AI voice',
    a === 'ai' && b === 'phone' && c === 'off' && offKey === 'off' && d === 'ai' && m0.getItem('jarvis.speak') === 'on' && e === 'ai' && old.every((x) => x === 'ai')
    && JSON.parse(m0.getItem('jarvis.voiceEngine')).mode === 'ai' && N.MODES.map((x) => x[1]).join('|') === 'AI voice (George)|iPhone voice|Off', [a, b, c, d, e, old]);
  const m1 = new Mem({ 'jarvis.voiceCfg': JSON.stringify({ voice: 'Ava (Premium)', rate: 1.1 }), 'jarvis.vmVoice': 'Ava', 'jarvis.voiceEngine': JSON.stringify({ mode: 'cloud', prosody: true }) });
  const did = N.migrate(m1), again = N.migrate(m1), cfg = JSON.parse(m1.getItem('jarvis.voiceCfg'));
  ck("e. once: the old female pick (Ava) and voice mode's are dropped, his speed kept, cloud -> AI voice; never twice",
    did && !again && !cfg.voice && cfg.rate === 1.1 && m1.getItem('jarvis.vmVoice') === null && JSON.parse(m1.getItem('jarvis.voiceEngine')).mode === 'ai' && JSON.parse(m1.getItem('jarvis.voiceEngine')).prosody === true, m1.m);
}

// ---------------------------------------------------------------- f. the engine, with a fake worker
function fakeCaches() {
  const stores = {};
  return { stores, async open(n) { const m = stores[n] || (stores[n] = new Map()); return { async match(u) { const r = m.get(typeof u === 'string' ? u : u.url); return r ? r.clone() : undefined; },
    async put(u, r) { m.set(typeof u === 'string' ? u : u.url, r); }, async keys() { return [...m.keys()].map((url) => ({ url })); }, async delete(k) { return m.delete(typeof k === 'string' ? k : k.url); } }; } };
}
function fakeWorker(opt) {
  const o = opt || {}, w = { sent: [], gens: [], drops: [], onmessage: null, onerror: null, terminated: false };
  const send = (m) => st0(() => { if (!w.terminated && w.onmessage) w.onmessage({ data: m }); }, 2);
  w.postMessage = (m) => {
    w.sent.push(m);
    if (m.type === 'init') {
      if (o.crash) { st0(() => w.onerror && w.onerror({ message: 'out of memory' }), 3); return; }
      send({ type: 'progress', loaded: 40e6, total: m.cfg.totalBytes, file: 'onnx/model_quantized.onnx' });
      send({ type: 'progress', loaded: 90e6, total: m.cfg.totalBytes, file: 'onnx/model_quantized.onnx' });
      st0(() => send({ type: 'ready', device: 'wasm', ms: 3000, warmMs: 900, rtf: o.rtf || 0.8 }), 5);
      return;
    }
    if (m.type === 'gen') {
      w.gens.push(m);
      if (o.hang && o.hang(m)) return;
      const n = Math.max(2400, Math.round(m.text.length / 14 * 24000)), pcm = new Float32Array(n);
      for (let i = 0; i < n; i++) pcm[i] = 0.2 * Math.sin(i / 9);
      st0(() => send({ type: 'audio', id: m.id, pcm, rate: 24000, ms: Math.round(n / 24 * (o.rtf || 0.8)) }), o.genDelay || 3);
      return;
    }
    if (m.type === 'drop') w.drops.push(m.id);
  };
  w.terminate = () => { w.terminated = true; };
  return w;
}
{
  const store = new Mem(), cs = fakeCaches(), prog = [], states = [];
  let wk = null;
  const nv = N.createNeuralVoice({ storage: store, caches: cs, makeWorker: () => (wk = fakeWorker({ rtf: 0.8 })), onProgress: (p) => prog.push(p), onState: (s) => states.push(s) });
  const before = nv.descriptor({ len: 40 });
  const ok = await nv.start();
  const init = wk.sent[0];
  ck("f. before it is ready: no AI voice (the iPhone voice speaks); start(): one worker, the pinned model, q8 on WebAssembly, George",
    before === null && ok && wk.sent.length >= 1 && init.type === 'init' && init.cfg.hfPin.indexOf('/resolve/1939ad2a8e416c0acfeecc08a694d14ef25f2231/') > 0 && init.cfg.dtype === 'q8' && init.cfg.device === 'wasm' && init.cfg.voice === 'bm_george', init && init.cfg);
  const loading = prog.filter((p) => p.state === 'loading');
  ck("f. the one-time download's progress line: \"Getting Jarvis's voice ready (one time, about 117 MB) · 34%\", then ready",
    loading.length >= 2 && loading[0].line.indexOf("Getting Jarvis's voice ready (one time, about 117 MB) · ") === 0 && loading[1].pct > loading[0].pct && states[0] === 'loading' && states[states.length - 1] === 'ready'
    && store.getItem('jarvis.nv.ready') === '1', loading.map((p) => p.line));
  const d = nv.descriptor({ len: 120 });
  ck('f. ready: the descriptor (kokoro, every piece queued at once, its own pieces, a wait per piece)', d && d.id === 'kokoro' && d.queueAll === true && typeof d.split === 'function' && d.timeoutFor(0, 'x') >= 6000
    && d.split('Hello there. All good.').length >= 1, d && Object.keys(d));
  const b1 = await nv.synth('Good evening.'), n1 = wk.gens.length, b2 = await nv.synth('Good evening.'), n2 = wk.gens.length;
  const nvb = N.createNeuralVoice({ storage: new Mem(), caches: cs, makeWorker: () => fakeWorker({ rtf: 0.8 }) });
  await nvb.start();
  const b3 = await nvb.synth('Good evening.');
  ck('f. audio: a WAV blob with its length (ms); a short line said again is the kept copy (no second job; Cache Storage between opens)',
    b1.type === 'audio/wav' && b1.dur > 0 && b1.size > 44 && n1 === 1 && n2 === 1 && b2 === b1 && b3.cached === true && b3.dur === b1.dur
    && (await cs.open('olympus-voice-clips-v1').then((c) => c.keys())).length === 1, [b1.type, b1.dur, n1, n2, b2 === b1, b3.cached, b3.dur]);
  const order0 = wk.gens.length;
  const two = [nv.synth('Right then.'), nv.synth('And this second sentence is a good deal longer than the first one, long enough to skip the clip cache entirely.')];
  await Promise.all(two);
  const order = wk.gens.slice(order0).map((g) => g.text.slice(0, 10));
  ck('f. pieces reach the worker in the order asked (a short first piece checking the clip cache never lets the long second one jump the queue)',
    order.length === 2 && order[0] === 'Right then' && order[1] === 'And this s', order);
  let hw = null;
  const nvh = N.createNeuralVoice({ storage: new Mem(), caches: fakeCaches(), makeWorker: () => (hw = fakeWorker({ hang: (m) => m.type === 'gen' })) });
  await nvh.start();
  const ac = new AbortController();
  const p = nvh.synth('A long answer that is still being made when he taps to cut in, so the worker drops what it was asked for here.', { signal: ac.signal });
  await wait(10);
  ac.abort();
  let aborted = false; try { await p; } catch (e) { aborted = e.name === 'AbortError'; }
  ck('f. a tap (abort): the waiting line is dropped in the worker too', aborted && hw.gens.length === 1 && hw.drops.length === 1 && hw.drops[0] === hw.gens[0].id, [aborted, hw.gens.length, hw.drops]);
  // a slow phone: long replies go to the iPhone voice
  const store2 = new Mem({ 'jarvis.nv.rtf': '2.9' });
  const nv2 = N.createNeuralVoice({ storage: store2, caches: fakeCaches(), makeWorker: () => fakeWorker({ rtf: 2.9 }) });
  await nv2.start();
  const slowStart = nv2.descriptor({ len: 38, text: 'Zlarior just went long on the fifty K.' }), sk0 = nv2.stats().skipped, quick = nv2.descriptor({ len: 13, text: 'Good morning.' });
  ck('f. a slow phone: a reply whose first piece would take over 4.5 s to make is said at once by the iPhone voice; a quick opener in the AI voice',
    !slowStart && sk0 === 'slow start' && !!quick, [!!slowStart, sk0, !!quick]);
  const shortD = nv2.descriptor({ len: 80 }), longD = nv2.descriptor({ len: 600 }), sk = nv2.stats().skipped;
  const fastD = d && nv.descriptor({ len: 2000 });
  ck('f. a slow phone (2.9 s of work per second of speech): a short answer in the AI voice, a long one (silences > 8 s) in the iPhone voice; a fast phone: everything',
    shortD && !longD && sk === 'long' && fastD && nv2.fits(80) && !nv2.fits(600) && +store2.getItem('jarvis.nv.rtf') > 2, [!!shortD, !!longD, sk, !!fastD]);
  // a crash: the iPhone voice, a 10-minute rest unless he picks it again; 3 in a row: a day
  let t = 1e12;
  const store3 = new Mem();
  let made = 0;
  const nv3 = N.createNeuralVoice({ storage: store3, caches: fakeCaches(), now: () => t, makeWorker: () => { made++; return fakeWorker({ crash: true }); } });
  const r1 = await nv3.start(), s1 = nv3.state(), r2 = await nv3.start(), m2 = made;
  t += 11 * 60e3; const r3 = await nv3.start(); const m3 = made;
  const r4 = await nv3.start(true), m4 = made, f4 = JSON.parse(store3.getItem('jarvis.nv.fail'));
  t += 11 * 60e3; const r5 = await nv3.start(), m5 = made;
  ck('f. a crash: failed, no AI voice (the iPhone voice speaks), no retry for 10 min, then one; he picks it again = at once; 3 in a row = rests a day',
    !r1 && s1 === 'failed' && nv3.descriptor({ len: 10 }) === null && !r2 && m2 === 1 && !r3 && m3 === 2 && !r4 && m4 === 3 && f4.n === 3 && !r5 && m5 === 3 && nv3.stats().resting, [r1, s1, m2, m3, m4, f4, m5]);
}

// ---------------------------------------------------------------- g. the speaker with the AI voice
{
  globalThis.setTimeout = (f, ms) => st0(f, Math.min(+ms || 0, 30) > 25 ? 25 : Math.min(+ms || 0, 30));   // pauses, waits and word ticks fast
  const phone = [], synth = { speaking: false, pending: false, paused: false, getVoices: () => [V('Daniel (Enhanced)', 'en-GB', 'com.apple.voice.enhanced.en-GB.Daniel')], cancel() {},
    speak(u) { phone.push(u.text); st0(() => { if (u.onstart) u.onstart({}); st0(() => u.onend && u.onend({}), 2); }, 1); } };
  const played = [];
  const player = { play(b) { played.push(b.text); return new Promise((ok) => st0(ok, 5)); }, stop() {}, unlock() {} };
  const asked = [], signals = [];
  let hangFrom = 99;
  const fake = (text, so) => { asked.push(text); signals.push(so && so.signal); const i = asked.length - 1; return new Promise((ok, bad) => {
    if (so && so.signal) so.signal.addEventListener('abort', () => bad(Object.assign(new Error('aborted'), { name: 'AbortError' })));
    if (i >= hangFrom) return;
    st0(() => { const b = new Blob(['x'], { type: 'audio/wav' }); b.text = text; b.dur = 40; ok(b); }, 3); }); };
  const nvd = N.createNeuralVoice({ storage: new Mem(), caches: fakeCaches(), makeWorker: () => fakeWorker({ rtf: 0.8 }) });
  await nvd.start();
  const desc = () => Object.assign({}, nvd.descriptor({ len: 100 }), { synth: fake });
  const sp = T.createSpeaker({ synth, voices: synth.getVoices, cfg: () => ({}), cloud: () => desc(), prosody: () => S.createSpeechText(), player: () => player });
  let ended = 0, bounds = [], eng = '';
  const raw = "Here's where you stand. Zlarior 50K: $49,193, $1,025 of room. ATLAS today: -$113.";
  sp.speak(raw, { onend: () => ended++, onboundary: (ci) => bounds.push(ci), onengine: (id) => { eng = id; } });
  await wait(20);
  const queuedAtOnce = asked.length;
  await wait(500);
  ck('g. every piece asked for at once (the worker never waits), the raw text normalized ("-$113" -> minus a hundred and thirteen dollars), played in order, one end',
    queuedAtOnce >= 3 && queuedAtOnce === played.length && played.join(' ') === asked.join(' ') && /minus a hundred and thirteen dollars\.$/.test(asked[asked.length - 1]) && ended === 1 && eng === 'kokoro' && !phone.length,
    { queuedAtOnce, asked, played, ended, eng, phone });
  ck('g. the words light up across each clip (boundaries inside the pieces, not only at their starts)', bounds.length > asked.length + 2, bounds.length);
  // a late piece: the iPhone voice says only the rest
  asked.length = 0; played.length = 0; phone.length = 0; hangFrom = 1; ended = 0; let fell = null;
  sp.speak('First sentence is quick. The second one never comes back. And a third one too.', { onend: () => ended++, onfallback: (e, id) => { fell = [e.reason, id]; } });
  await wait(700);
  ck('g. a late piece: the iPhone voice says only what the AI voice did not (never twice, never silence), once',
    played.length === 1 && phone.length >= 1 && phone.join(' ').indexOf('First sentence') < 0 && /second one/.test(phone.join(' ')) && /third/.test(phone.join(' ')) && fell && fell[0] === 'timeout' && fell[1] === 'kokoro' && ended === 1,
    { played, phone, fell, ended });
  // barge-in: a tap aborts the work in flight (the late piece above parked the AI voice for 2 minutes: let it back in)
  sp.unpark('kokoro');
  asked.length = 0; signals.length = 0; hangFrom = 0;
  const h = sp.speak('This one is still being made when he taps. Another sentence.', {});
  await wait(10);
  h.cancel();
  ck('g. a tap while the AI voice is still making the reply: every request in flight is aborted', signals.length >= 1 && signals.every((x) => x && x.aborted), signals.map((x) => x && x.aborted));
  globalThis.setTimeout = st0;
}
console.log(JSON.stringify(out));
"""


def part_node(tmp):
    script = os.path.join(tmp, "speech.mjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write(NODE)
    r = subprocess.run(["node", script, JV], capture_output=True, text=True, timeout=120)
    try:
        rows = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b-g. the node checks run", False, (r.stderr or r.stdout)[-1500:])
        return
    for row in rows:
        check(row["name"], row["ok"], row["info"])


def main():
    part_files()
    with tempfile.TemporaryDirectory(prefix="le_jarvis_speech_") as tmp:
        part_node(tmp)
    n = sum(RES)
    print(f"\njarvis speech: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
