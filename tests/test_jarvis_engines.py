"""Jarvis HUMAN VOICE (2026-11-04, owner: "Jarvis sounds like a bot, I want a real person, free"): the natural-speech layer
(tools/web_public/jarvis/prosody.js), the voice engine chooser (voice-engines.js: Auto / Natural cloud = Gemini + Groq /
On-device neural = Kokoro / Phone voice), the on-device engine's integrity checks (kokoro-engine.js) and their wiring into
tts.js, voice-out.js and the Voice sheet. Checks:
  a. the files: parse, Safari 16 safe (no lookbehind, no ?? / ?.), tts.js still import-free and talking only to api.groq.com,
     the new files talk only to their own hosts, no key is ever logged or put in a URL
  b. in node, with the network mocked: numbers / money / percent / time / year / ordinal / ticker -> words; conversational
     contractions; nothing symbolic left after cleanSpeech + prepare (no $ % @ # & digits, links or emoji); phrases, pauses and
     rate / pitch by sentence type; the request shapes (Groq Orpheus, Gemini generateContent with the key in a header only);
     Gemini PCM -> WAV, model fall-through, 429 retry-after; Auto / cloud / device / phone picking (premium phone, long reply,
     parked cloud, the older 'cloud off' switch); the audio cache (memory + Cache Storage for short phrases, nothing for long ones);
     the speaker with the engines: the spoken text, barge-in aborting the request in flight, a mid-reply failure continuing in
     the phone's voice with only what was not said, a 429 parking only that voice; the shared player; Kokoro refuses a damaged or
     tampered model part and never touches huggingface.co
  c. the page, in Chromium AND in WebKit with an iPhone 13 profile, the network mocked (Gemini / Groq answers, no real audio):
     a saved Gemini key -> Auto speaks with it (the request has the number in words, the key only in a header), a tap stops it,
     the Voice sheet's engine chooser (4 engines, Phone voice -> the phone says it, samples, Test voice, the Premium guide,
     the on-device download failing politely), a Groq refusal -> the phone's voice for that reply plus one plain toast
  d. (optional, RUN_KOKORO=1 and the files in KOKORO_DIR) the real Kokoro model in Chromium: downloads from a mocked CDN, joins and
     checks the parts, speaks, and never asks huggingface.co
    PLAYWRIGHT_BROWSERS_PATH=<dir with webkit> python -X utf8 -m tests.test_jarvis_engines     (~2-3 min; WebKit skipped, and said so,
    when it is not installed)
"""
from __future__ import annotations

import base64
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from tests import test_jarvis_hub as H
from tests import test_jarvis_talk as T

JV = H.JV
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(name):
    return open(os.path.join(JV, name), encoding="utf-8").read()


# ------------------------------------------------------------------------------------------------ a. files
def part_files():
    for name in ("prosody.js", "voice-engines.js", "kokoro-engine.js", "tts.js", "voice-out.js"):
        src = read(name)
        ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
        check(f"a. {name} parses as an ES module", ok.returncode == 0, ok.stderr)
        check(f"a. {name}: Safari 16 safe (no lookbehind, no ?? / ?.)",
              "(?<" not in src and "??" not in src and not re.search(r"[\w)\]]\?\.[\w(\[]", src) and ".at(" not in src, name)
    check("a. tts.js is still the import-free fallback, talking only to api.groq.com",
          not re.search(r"^\s*import ", read("tts.js"), re.M) and set(re.findall(r"https?://[a-z0-9.-]+", read("tts.js"))) <= {"https://api.groq.com"})
    check("a. prosody.js: no imports, no network", not re.search(r"^\s*import ", read("prosody.js"), re.M) and "fetch(" not in read("prosody.js") and not re.findall(r"https?://", read("prosody.js")))
    ve = read("voice-engines.js")
    hosts = set(re.findall(r"https?://[a-z0-9.-]+", ve))
    check("a. voice-engines.js talks only to api.groq.com, generativelanguage.googleapis.com (+ a page address in a message and the local cache key)",
          hosts <= {"https://api.groq.com", "https://generativelanguage.googleapis.com", "https://console.groq.com", "https://jarvis.local"}, hosts)
    check("a. voice-engines.js imports only ./prosody.js (kokoro-engine.js is a lazy import())", re.findall(r"^\s*import .* from '([^']+)';", ve, re.M) == ["./prosody.js"] and "import('./kokoro-engine.js')" in ve)
    check("a. no key is ever logged: no console.log / warn / error in the new files, the Gemini key only in a header", not re.search(r"\bconsole\.(log|warn|error|info|debug)", ve + read("kokoro-engine.js") + read("prosody.js"))
          and "'x-goog-api-key': o.key" in ve and "?key=" not in ve)
    ko = read("kokoro-engine.js")
    kh = set(re.findall(r"https?://[a-z0-9.-]+", ko))
    check("a. kokoro-engine.js: CDN files only from cdn.jsdelivr.net/npm at an exact version (huggingface.co is only the cache key)",
          kh <= {"https://cdn.jsdelivr.net", "https://huggingface.co"} and all(re.search(r"@\d+\.\d+\.\d+", u) for u in re.findall(r"https://cdn\.jsdelivr\.net/npm/[^'\"`]+", ko)), kh)
    check("a. kokoro-engine.js: the model parts are each checked against a SHA-256 (the third-party npm package is not trusted)", len(re.findall(r"^\s+'[0-9a-f]{64}',$", ko, re.M)) == 6 and "shardSha256" in ko)
    page = read("index.html")
    check("a. the shell loads voice-engines.js (optional) and the Voice sheet has the engine chooser, the samples, the Premium guide",
          "load('engines', './voice-engines.js'" in page and all(i in page for i in ('id="vEngine"', 'id="vSamples"', 'id="vPremium"', 'id="vDevDl"', 'id="vProsody"', 'id="vCloud"')))


# ------------------------------------------------------------------------------------------------ b. node
NODE = r"""
import { pathToFileURL } from 'node:url';
import { webcrypto } from 'node:crypto';
const dir = process.argv[2];
const imp = (f) => import(pathToFileURL(dir + '/' + f).href);
const P = await imp('prosody.js'), T = await imp('tts.js'), E = await imp('voice-engines.js'), K = await imp('kokoro-engine.js');
const out = [];
const ck = (name, ok, info) => out.push({ name, ok: !!ok, info: ok ? '' : JSON.stringify(info === undefined ? null : info) });
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const wait = (ms) => new Promise((ok) => setTimeout(ok, ms));
const KEYG = 'AIzaTESTKEY0123456789', KEYQ = 'gsk_TESTKEY0123456789';
const logs = []; const realLog = console.log.bind(console); for (const m of ['log', 'warn', 'error', 'info', 'debug']) { console[m] = (...a) => { logs.push(a.map(String).join(' ')); }; }

// ---------------------------------------------------------------- the words
ck('b. numberToWords', [[0, 'zero'], [13, 'thirteen'], [21, 'twenty one'], [100, 'one hundred'], [1133, 'one thousand one hundred thirty three'], [12345, 'twelve thousand three hundred forty five'],
  [1000000, 'one million'], [2500000000, 'two billion five hundred million'], [-5, 'minus five']].every(([n, w]) => P.numberToWords(n) === w), [P.numberToWords(1133), P.numberToWords(2500000000)]);
ck('b. money in hundreds: 1,133 -> eleven hundred thirty three; 2,500 -> twenty five hundred; 1,000 and 2,026 stay thousands',
  P.spokenMoney(1133) === 'eleven hundred thirty three' && P.spokenMoney(2500) === 'twenty five hundred' && P.spokenMoney(1000) === 'one thousand' && P.spokenMoney(2026) === 'two thousand twenty six');
const ex = [['1,133 dollars', 'eleven hundred thirty three dollars'], ['up 213 dollars', 'up two hundred thirteen dollars'], ['2.5 percent', 'two point five percent'], ['9:30 AM', 'nine thirty A M'],
  ['9:05', 'nine oh five'], ['10:00', "ten o'clock"], ['3 PM', 'three P M'], ['12.50 dollars', 'twelve dollars fifty cents'], ['in 2026', 'in twenty twenty six'], ['May 3, 2025', 'May three, twenty twenty five'],
  ['the 21st', 'the twenty first'], ['8R target', 'eight R target'], ['1.5R', 'one point five R'], ['a 15m chart', 'a fifteen minutes chart'], ['-5 points', 'minus five points'], ['3-5 trades', 'three to five trades'],
  ['20,260 points', 'twenty thousand two hundred sixty points'], ['0.45', 'zero point four five'], ['2,000 dollars a month', 'two thousand dollars a month'], ['1.2 thousand dollars', 'one point two thousand dollars'],
  ['15:55 ET', 'fifteen fifty five Eastern time'], ['4 trades', 'four trades'], ['since 2026-10-24', 'since October twenty fourth, twenty twenty six']];
const bad = ex.filter(([i, w]) => P.prepare(i, { conversational: false }) !== w).map(([i, w]) => [i, P.prepare(i, { conversational: false }), w]);
ck('b. numbers, money, percents, times, years, ordinals, risk multiples, ranges -> words (' + ex.length + ' cases)', bad.length === 0, bad);
ck('b. tickers said the way a trader says them: NQ -> N Q, ES -> E S, MNQ, VIX, MFFU; ordinary words untouched', P.prepare('NQ and ES moved, the VIX fell. MFFU said yes. It is on.', { conversational: false }) === 'N Q and E S moved, the vicks fell. M F F U said yes. It is on.', P.prepare('NQ and ES moved, the VIX fell. MFFU said yes. It is on.', { conversational: false }));
const conv = P.conversational('It is fine. However, we do not know. I am sure you are right, and I will not stop. Yes it is. We cannot wait.');
ck('b. conversational: contractions and plain words (but, also), not before the end of a sentence ("Yes it is.")', conv === "It's fine. But we don't know. I'm sure you're right, and I won't stop. Yes it is. We can't wait.", conv);
// nothing symbolic left after the whole path
const nasty = ['**Net** +$1,133 (2.5%) at 9:30am - see https://x.example/z?a=1 [docs](https://d.example) \u{1F600} #1 @bot & co', '`code` ```x = 1``` | a | b | ->  8R ~$300/mo, e.g. 3x', 'Rate: 4.5% & $12.50 on 5/6. Wow… ok'];
const left = nasty.map((s) => P.prepare(T.cleanSpeech(s))).filter((s) => /[\d$%@#&*_<>{}|\\^~`\[\]]|https?:|www\.|\p{Extended_Pictographic}/u.test(s));
ck('b. never reads symbols, emoji or URLs: cleanSpeech + prepare leave no digit, $ % @ # & * _ ~ | brackets, link or emoji', left.length === 0, left.map((s) => P.prepare(T.cleanSpeech(s))));
ck('b. preparing twice changes nothing', nasty.every((s) => { const a = P.prepare(T.cleanSpeech(s)); return P.prepare(a) === a; }));

// ---------------------------------------------------------------- phrases, pauses, rate / pitch
const txt = 'Your room today is eleven hundred thirty three dollars, and the week is up two point five percent, which is a good start for the whole team. Is that right? Great!';
const pl = P.plan(txt), pl2 = P.plan(txt);
ck('b. plan: deterministic, every phrase <= 180, nothing lost, long sentence cut at commas into breaths', eq(pl, pl2) && pl.every((x) => x.text.length <= 180) && pl.map((x) => x.text).join(' ').replace(/\s+/g, ' ') === txt && pl.length >= 4, pl.map((x) => x.text));
const q = pl.find((x) => x.type === 'q'), s = pl.find((x) => x.type === 's'), c = pl.find((x) => x.type === 'c'), x = pl.find((x) => x.type === 'x');
ck('b. a question lifts (pitch up), a statement settles, a comma breath is short, a sentence end is a longer pause', q && s && c && x && q.pitch > s.pitch + 0.05 && c.pause < s.pause && s.pause <= q.pause && x.rate > s.rate - 0.01 && pl.every((y) => y.rate > 0.9 && y.rate < 1.1 && y.pitch > 0.9 && y.pitch < 1.12), pl);
const mg = P.merge(pl, 200);
ck('b. merge (cloud): parts <= 200 chars, fewer requests, the pause after a part is the last piece\'s', mg.length < pl.length && mg.every((y) => y.text.length <= 200) && mg.map((y) => y.text).join(' ') === pl.map((y) => y.text).join(' '), mg.map((y) => y.text.length));

// ---------------------------------------------------------------- mocks
const mkStore = (init) => { const m = new Map(Object.entries(init || {})); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), _m: m }; };
const mkCaches = () => { const stores = new Map(); const open = async (n) => { if (!stores.has(n)) stores.set(n, new Map()); const s = stores.get(n);
  return { match: async (u) => (s.has(String(u)) ? s.get(String(u)).clone() : undefined), put: async (u, r) => { s.set(String(u), r.clone ? r.clone() : r); }, keys: async () => [...s.keys()].map((u) => ({ url: u })), delete: async (u) => s.delete(u.url || String(u)) }; };
  return { open, delete: async (n) => stores.delete(n), _stores: stores }; };
const pcm = (n) => { const b = new Uint8Array(n); for (let i = 0; i < n; i += 2) b[i] = (i / 2) % 100; return b; };
const b64 = (u8) => Buffer.from(u8).toString('base64');
const gemOk = (u8, mime) => new Response(JSON.stringify({ candidates: [{ content: { parts: [{ inlineData: { mimeType: mime || 'audio/L16;codec=pcm;rate=24000', data: b64(u8) } }] } }] }), { status: 200, headers: { 'content-type': 'application/json' } });
const wavBytes = (n) => { const b = new Uint8Array(44 + n); const v = new DataView(b.buffer); const w = (o, t) => { for (let i = 0; i < t.length; i++) b[o + i] = t.charCodeAt(i); }; w(0, 'RIFF'); v.setUint32(4, 36 + n, true); w(8, 'WAVE'); w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, 24000, true); v.setUint32(28, 48000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, n, true); return b; };
const mkFetch = (handler) => { const calls = []; const f = async (url, init) => { const c = { url: String(url), init: init || {}, body: init && init.body ? JSON.parse(init.body) : null, signal: init && init.signal }; calls.push(c); return handler(c, calls.length); }; f.calls = calls; return f; };
const mkEng = (o) => { const st = mkStore(o.store || {}); const caches = o.caches || mkCaches(); const f = o.fetch || mkFetch(() => gemOk(pcm(4800)));
  const e = E.createVoiceEngines({ storage: st, fetch: f, caches, keys: () => o.keys || {}, phoneVoice: () => o.phone || null, loadKokoro: o.loadKokoro, player: o.player || undefined, Audio: class { }, URL: { createObjectURL: () => 'blob:x', revokeObjectURL() {} } });
  return { e, st, f, caches }; };
const premium = { name: 'Ava (Premium)', voiceURI: 'com.apple.voice.premium.en-US.Ava', lang: 'en-US' }, compact = { name: 'Samantha', voiceURI: 'com.apple.voice.compact.en-US.Samantha', lang: 'en-US' };

// ---------------------------------------------------------------- the request shapes
{
  const f = mkFetch(() => new Response(wavBytes(2000), { status: 200, headers: { 'content-type': 'audio/wav' } }));
  const b = await E.groqSynth('Hello there.', { fetch: f, key: KEYQ, voice: 'diana' });
  const c = f.calls[0];
  ck('b. Groq: POST api.groq.com/openai/v1/audio/speech, Orpheus, the chosen voice, wav, the key only in Authorization', c.url === 'https://api.groq.com/openai/v1/audio/speech' && c.init.method === 'POST' && c.init.headers.Authorization === 'Bearer ' + KEYQ
    && c.body.model === 'canopylabs/orpheus-v1-english' && c.body.voice === 'diana' && c.body.response_format === 'wav' && c.body.input === 'Hello there.' && !JSON.stringify(c.body).includes(KEYQ) && !c.url.includes(KEYQ) && b.size === 2044, [c.url, c.body]);
  const f2 = mkFetch(() => gemOk(pcm(4800)));
  const g = await E.geminiSynth('Hello there.', { fetch: f2, key: KEYG, voice: 'Aoede' });
  const gc = f2.calls[0], gb = new Uint8Array(await g.arrayBuffer());
  ck('b. Gemini: POST generativelanguage.googleapis.com/v1beta/models/<model>:generateContent, the AUDIO modality, the prebuilt voice, the key only in x-goog-api-key',
    /^https:\/\/generativelanguage\.googleapis\.com\/v1beta\/models\/gemini-[\w.-]+:generateContent$/.test(gc.url) && gc.init.headers['x-goog-api-key'] === KEYG && !gc.url.includes(KEYG) && !JSON.stringify(gc.body).includes(KEYG)
    && eq(gc.body.generationConfig.responseModalities, ['AUDIO']) && gc.body.generationConfig.speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName === 'Aoede' && gc.body.contents[0].parts[0].text === 'Hello there.', [gc.url, gc.body]);
  ck('b. Gemini 24 kHz PCM -> a WAV (RIFF header, 24000 Hz, 16-bit mono, the PCM after it); a WAV answer passes through', String.fromCharCode(...gb.slice(0, 4)) === 'RIFF' && new DataView(gb.buffer).getUint32(24, true) === 24000 && gb.length === 44 + 4800, [gb.length]);
  const f3 = mkFetch(() => gemOk(wavBytes(1000), 'audio/wav'));
  const g3 = await E.geminiSynth('x', { fetch: f3, key: KEYG, voice: 'Kore' });
  ck('b. Gemini WAV answer unchanged', g3.size === 1044, g3.size);
  let seen = [];
  const f4 = mkFetch((c, n) => { seen.push(c.url.split('/').pop().split(':')[0]); return n === 1 ? new Response('{"error":{"message":"model not found"}}', { status: 404 }) : n === 2 ? new Response('{}', { status: 429, headers: { 'retry-after': '9' } }) : gemOk(pcm(200)); });
  let used = '';
  const g4 = await E.geminiSynth('x', { fetch: f4, key: KEYG, voice: 'Kore', onModel: (m) => { used = m; } });
  ck('b. Gemini: a missing model (404) or an exhausted one (429) hands over to the next model; the working one is remembered', seen.length === 3 && new Set(seen).size === 3 && used === seen[2] && g4.size === 244, [seen, used]);
  const f5 = mkFetch(() => new Response('{"error":{"message":"quota"}}', { status: 429, headers: { 'retry-after': '7' } }));
  let err = null; try { await E.geminiSynth('x', { fetch: f5, key: KEYG, voice: 'Kore' }); } catch (e) { err = e; }
  ck('b. Gemini: every model out of quota -> a 429 error carrying retry-after 7 and reason "rate"', err && err.status === 429 && err.retryAfter === 7 && err.reason === 'rate' && f5.calls.length === E.GEMINI.models.length, [err && err.status, f5.calls.length]);
  const f6 = mkFetch(() => new Response('{"error":{"code":"model_terms_required","message":"accept the terms"}}', { status: 400 }));
  let e6 = null; try { await E.groqSynth('x', { fetch: f6, key: KEYQ, voice: 'hannah' }); } catch (e) { e6 = e; }
  const m6 = mkEng({ keys: { groq: KEYQ } }).e.explain(e6, 'groq');
  ck('b. Groq: the model-terms refusal is recognised and explained in plain words with the page to open (once)', e6 && e6.reason === 'terms' && /console\.groq\.com\/playground\?model=canopylabs\/orpheus-v1-english/.test(m6) && /phone voice/i.test(m6), [e6 && e6.reason, m6]);
  const f7 = mkFetch(() => new Response('{"error":{"message":"API key not valid"}}', { status: 400 }));
  let e7 = null; try { await E.geminiSynth('x', { fetch: f7, key: 'bad', voice: 'Kore' }); } catch (e) { e7 = e; }
  ck('b. Gemini: a bad key (400 API key not valid) is a "key" error, not retried on other models', e7 && e7.reason === 'key' && f7.calls.length === 1, [e7 && e7.reason, f7.calls.length]);
}

// ---------------------------------------------------------------- picking the engine
{
  const id = (o, ctx) => { const d = mkEng(o).e.pick(ctx || { len: 40 }); return d ? d.id : null; };
  const dev = { 'jarvis.kokoro.ready': '1' };
  globalThis.WebAssembly = globalThis.WebAssembly || {};
  ck('b. Auto, no key, nothing downloaded: the phone voice (null)', id({}) === null);
  ck('b. Auto: Gemini key -> gemini; Groq key -> groq; both -> gemini first; brand "groq" picks Groq', id({ keys: { gemini: KEYG } }) === 'gemini' && id({ keys: { groq: KEYQ } }) === 'groq' && id({ keys: { gemini: KEYG, groq: KEYQ } }) === 'gemini'
    && id({ keys: { gemini: KEYG, groq: KEYQ }, store: { 'jarvis.voiceEngine': JSON.stringify({ brand: 'groq' }) } }) === 'groq');
  ck('b. Auto: a long reply (over ' + E.AUTO_CLOUD_MAX + ' chars) spares the small free quota: the next best voice (on-device if downloaded, else the phone)', id({ keys: { gemini: KEYG } }, { len: 900 }) === null
    && id({ keys: { gemini: KEYG }, store: dev }, { len: 900 }) === 'kokoro' && id({ keys: { gemini: KEYG } }, { len: 300 }) === 'gemini');
  ck('b. Auto: a Premium phone voice beats the on-device one (instant, offline), the cloud still comes first for short replies', id({ store: dev, phone: premium }) === null && id({ store: dev, phone: compact }) === 'kokoro'
    && id({ keys: { gemini: KEYG }, phone: premium }) === 'gemini');
  const mode = (m) => ({ 'jarvis.voiceEngine': JSON.stringify({ mode: m }) });
  ck('b. modes: Phone voice is always the phone; Natural cloud ignores the length; On-device needs the download', id({ keys: { gemini: KEYG }, store: mode('phone') }) === null && id({ keys: { gemini: KEYG }, store: mode('cloud') }, { len: 900 }) === 'gemini'
    && id({ store: mode('device') }) === null && id({ store: { ...mode('device'), ...dev } }) === 'kokoro' && id({ keys: { gemini: KEYG }, store: mode('device') }) === null);
  ck('b. the older "cloud voice off" switch still stops Auto from using a key', id({ keys: { groq: KEYQ }, store: { 'jarvis.tts': JSON.stringify({ cloud: false }) } }) === null && id({ keys: { groq: KEYQ }, store: { 'jarvis.tts': JSON.stringify({ cloud: true }) } }) === 'groq');
  // a 429 parks that voice; Auto goes on to the next
  const m = mkEng({ keys: { gemini: KEYG, groq: KEYQ }, fetch: mkFetch(() => new Response('{}', { status: 429 })) });
  const d1 = m.e.pick({ len: 10 });
  let er = null; try { await d1.synth('Hello', {}); } catch (e) { er = e; }
  const d2 = m.e.pick({ len: 10 }), st = m.e.status();
  ck('b. a 429 parks Gemini (until tomorrow without a retry-after); Auto goes on to Groq; the status shows it', er && er.status === 429 && d1.id === 'gemini' && d2 && d2.id === 'groq' && st.parked.gemini > 3600e3, [d2 && d2.id, st.parked]);
  const d = mkEng({ keys: { gemini: KEYG } }).e.describe(), d0 = mkEng({ phone: compact }).e.describe();
  ck('b. describe(): says what Auto uses and what to do for a better voice', /Gemini/.test(d.note) && d.using === 'gemini' && /Gemini or Groq key/.test(d0.note) && /Premium/.test(d0.note) && d0.using === 'phone', [d.note, d0.note]);
}

// ---------------------------------------------------------------- the audio cache
{
  const caches = mkCaches(), f = mkFetch(() => gemOk(pcm(4800)));
  const a = mkEng({ keys: { gemini: KEYG }, fetch: f, caches }), da = a.e.pick({ len: 10 });
  await da.synth('Voice on.', {}); await da.synth('Voice on.', {});
  const long = 'This is a much longer sentence that is not a short repeated phrase, so it should only live in memory for this page.';
  await da.synth(long, {}); await da.synth(long, {});
  ck('b. cache: a repeated line is fetched once (memory), a different line again', f.calls.length === 2, f.calls.length);
  const st = caches._stores.get('jarvis-voice-v1');
  ck('b. cache: the short phrase is kept in Cache Storage, the long sentence is not', st && st.size === 1 && [...st.keys()][0].startsWith('https://jarvis.local/voice/'), st && [...st.keys()]);
  await wait(20);
  const f2 = mkFetch(() => gemOk(pcm(4800)));
  const b = mkEng({ keys: { gemini: KEYG }, fetch: f2, caches }), db = b.e.pick({ len: 10 });
  await db.synth('Voice on.', {});
  ck('b. cache: a new page load answers "Voice on." from Cache Storage with no request and no quota', f2.calls.length === 0, f2.calls.length);
  const o = mkEng({ keys: { gemini: KEYG }, fetch: mkFetch(() => gemOk(pcm(100))) }).e.pick({ len: 10 });
  await o.synth('Hello', {});
  const k1 = a.e.cache.key('gemini', 'Kore', 'x'), k2 = a.e.cache.key('gemini', 'Aoede', 'x'), k3 = a.e.cache.key('groq', 'Kore', 'x');
  ck('b. cache keys differ by engine and voice (a voice change never plays an old clip)', k1 !== k2 && k1 !== k3);
}

// ---------------------------------------------------------------- the speaker with the engines
const phoneSynth = (said) => ({ speaking: false, pending: false, paused: false, getVoices: () => [{ name: 'Ava (Premium)', lang: 'en-US', voiceURI: 'com.apple.voice.premium.en-US.Ava' }], cancel() {},
  speak(u) { said.push({ text: u.text, rate: u.rate, pitch: u.pitch }); setTimeout(() => u.onstart && u.onstart({}), 1); setTimeout(() => u.onend && u.onend({}), 4); }, addEventListener() {} });
globalThis.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.volume = 1; this.rate = 1; this.pitch = 1; } };
const mkPlayer = () => { const p = { played: [], stops: 0, play: (b) => { p.played.push(b.size); return new Promise((ok) => setTimeout(ok, 5)); }, stop() { p.stops++; }, unlock() {} }; return p; };
{
  const said = [], player = mkPlayer(), f = mkFetch(() => gemOk(pcm(4800))), { e } = mkEng({ keys: { gemini: KEYG }, fetch: f });
  const sp = T.createSpeaker({ synth: phoneSynth(said), cfg: () => ({}), cloud: (c) => e.pick(c), prosody: () => e.prosody, player: () => player });
  let ended = 0, engine = '';
  sp.speak('Your room is **$1,133**, and the week is up 2.5%. NQ opens at 9:30 AM, so I do not see a setup yet.', { onend: () => ended++, onengine: (i) => { engine = i; } });
  await wait(200);
  const sent = f.calls.map((c) => c.body.contents[0].parts[0].text).join(' | ');
  ck('b. speaker + Gemini: the request carries the words, not the symbols (eleven hundred thirty three dollars, two point five percent, N Q, nine thirty A M, don\'t)', /eleven hundred thirty three dollars/.test(sent) && /two point five percent/.test(sent) && /N Q opens at nine thirty A M/.test(sent) && /don't/.test(sent) && !/[$%\d]/.test(sent), sent);
  ck('b. speaker + Gemini: fewer, longer requests (sentences joined up to the limit), played through the shared player, the phone silent, onend once, engine reported', f.calls.length <= 2 && player.played.length === f.calls.length && said.length === 0 && ended === 1 && engine === 'gemini', [f.calls.length, player.played, said.length, ended, engine]);
  ck('b. the key is in no URL, no body and no log', f.calls.every((c) => !c.url.includes(KEYG) && !JSON.stringify(c.body).includes(KEYG)) && !logs.join('\n').includes(KEYG) && !logs.join('\n').includes(KEYQ), logs.slice(0, 3));
}
{ // barge-in: a tap while the request is in flight
  const said = [], player = mkPlayer(); let sig = null;
  const f = mkFetch((c) => { sig = c.signal; return new Promise((ok, bad) => { c.signal.addEventListener('abort', () => bad(Object.assign(new Error('aborted'), { name: 'AbortError' }))); }); });
  const { e } = mkEng({ keys: { gemini: KEYG }, fetch: f });
  const sp = T.createSpeaker({ synth: phoneSynth(said), cfg: () => ({}), cloud: (c) => e.pick(c), prosody: () => e.prosody, player: () => player });
  let ended = 0, fell = 0;
  sp.speak('This one will be cut off by a tap.', { onend: () => ended++, onfallback: () => fell++ });
  await wait(30);
  sp.cancel();
  await wait(60);
  ck('b. barge-in: a tap aborts the request in flight and stops the player; no phone voice takes over, no onend, no error', sig && sig.aborted && player.stops >= 1 && said.length === 0 && ended === 0 && fell === 0 && !sp.speaking, [sig && sig.aborted, player.stops, said.length, ended, fell]);
  const say2 = [], pl2 = mkPlayer(); let n = 0;
  const f2 = mkFetch(() => gemOk(pcm(4800)));
  const m2 = mkEng({ keys: { gemini: KEYG }, fetch: f2 });
  const p2 = { played: 0, stops: 0, play: () => new Promise(() => { p2.played++; }), stop() { p2.stops++; } };
  const sp2 = T.createSpeaker({ synth: phoneSynth(say2), cfg: () => ({}), cloud: (c) => m2.e.pick(c), prosody: () => m2.e.prosody, player: () => p2 });
  let end2 = 0; sp2.speak('Playing right now.', { onend: () => end2++ });
  await wait(40); sp2.cancel(); await wait(20);
  ck('b. barge-in while the clip is playing: the player is stopped and the speaker is free at once', p2.played === 1 && p2.stops >= 1 && !sp2.speaking && end2 === 0 && say2.length === 0, [p2.played, p2.stops, end2]);
}
{ // the second part fails: the phone says only what was not said yet
  const said = [], player = mkPlayer();
  const f = mkFetch((c, n) => (n === 1 ? new Response(wavBytes(2000), { status: 200 }) : new Response('{"error":{"message":"overloaded"}}', { status: 500 })));
  const { e } = mkEng({ keys: { groq: KEYQ }, fetch: f });
  const sp = T.createSpeaker({ synth: phoneSynth(said), cfg: () => ({}), cloud: (c) => e.pick(c), prosody: () => e.prosody, player: () => player });
  const first = 'The first part is a fairly long sentence that fills most of a single request on its own, so the next one needs a new request.';
  const second = 'The second part fails, and it is also a long enough sentence that it cannot be joined onto the first one at all.';
  let fell = null, ended = 0;
  sp.speak(first + ' ' + second, { onend: () => ended++, onfallback: (er, id) => { fell = [er && er.reason, id]; } });
  await wait(500);
  const spoken = said.map((s) => s.text).join(' ');
  ck('b. a failure after the first part: the reply goes on in the phone voice with ONLY the rest (nothing said twice), one onend, the error reported', player.played.length === 1 && /long enough sentence/.test(spoken) && !/second part fails/.test(spoken) && !/first part is a fairly/.test(spoken) && ended === 1 && fell && fell[1] === 'groq', [player.played, spoken, ended, fell]);
}
{ // a 429 with a short retry-after parks only that voice, for that long
  const said = [], player = mkPlayer();
  const f = mkFetch(() => new Response('{}', { status: 429, headers: { 'retry-after': '5' } }));
  const { e } = mkEng({ keys: { gemini: KEYG }, fetch: f });
  const sp = T.createSpeaker({ synth: phoneSynth(said), cfg: () => ({}), cloud: (c) => e.pick(c), prosody: () => e.prosody, player: () => player });
  sp.speak('First try.', {}); await wait(120);
  const n1 = f.calls.length;
  sp.speak('Second try.', {}); await wait(120);
  const left = sp.parked('gemini');
  ck('b. a 429 (retry-after 5): that reply in the phone voice, the next one does not even try (parked for about 7 s, not the whole day)', said.map((s) => s.text).join(' ').includes('First try') && said.map((s) => s.text).join(' ').includes('Second try') && f.calls.length === n1 && left > 3000 && left < 9000, [n1, f.calls.length, left]);
}
{ // the phone voice with the natural layer: words, contractions, a lifted question, a settled statement
  const said = [], { e } = mkEng({});
  const sp = T.createSpeaker({ synth: phoneSynth(said), cfg: () => ({}), cloud: () => null, prosody: () => e.prosody });
  sp.speak('Your room is $1,133 today. Is that right? I do not think it is high. It is fine, so keep going and do not stop for anything at all, because the plan is simple.', {}); await wait(1800);
  const u = said.map((s) => s.text);
  const qi = u.findIndex((t) => /right\?$/.test(t)), si = u.findIndex((t) => /today\.$/.test(t));
  ck('b. phone voice: the natural layer applies (number in words, contractions), a question has a higher pitch than the statement before it, rates stay in range',
    /eleven hundred thirty three dollars/.test(u[0]) && u.some((t) => /don't/.test(t)) && qi > 0 && si >= 0 && said[qi].pitch > said[si].pitch + 0.04 && said.every((s) => s.rate >= 0.9 && s.rate <= 1.1), said);
  e.setSettings({ prosody: false });
  const said2 = []; const sp2 = T.createSpeaker({ synth: phoneSynth(said2), cfg: () => ({}), cloud: () => null, prosody: () => e.prosody });
  sp2.speak('Your room is $1,133 today.', {}); await wait(100);
  ck('b. "Natural speech" off: exactly the old text (1,133 dollars), rate and pitch 1', said2.length === 1 && /1,133 dollars/.test(said2[0].text) && said2[0].rate === 1 && said2[0].pitch === 1, said2);
}
{ // the player
  const log = []; class A { constructor() { this.attrs = {}; log.push('new'); } setAttribute(k, v) { this.attrs[k] = v; } play() { log.push('play ' + String(this.src).slice(0, 14) + ' vol' + this.volume); return Promise.resolve(); } pause() { log.push('pause'); } }
  const pl = E.createPlayer({ Audio: A, URL: { createObjectURL: () => 'blob:clip', revokeObjectURL() { log.push('revoke'); } } });
  pl.unlock(); pl.unlock();
  ck('b. player: ONE element, unlocked once inside the tap with a silent clip (volume 0), then reused', log.filter((x) => x === 'new').length === 1 && log.filter((x) => x.startsWith('play data:audio/wav')).length === 1 && pl.unlocked(), log);
  const el = pl.element(); const done = pl.play(new Blob([new Uint8Array(10)])); await wait(5); let fin = false; done.then(() => { fin = true; }); el.onended(); await wait(5);
  const d2 = pl.play(new Blob([new Uint8Array(10)])); let fin2 = false; d2.then(() => { fin2 = true; }); await wait(5); pl.stop(); await wait(5);
  ck('b. player: play() settles when the clip ends; stop() settles a clip that is playing (barge-in) and frees the blob', fin && fin2 && log.includes('revoke') && !pl.playing(), log);
}

// ---------------------------------------------------------------- Kokoro: integrity first
{
  const caches = mkCaches(), puts = [];
  const orig = caches.open; caches.open = async (n) => { const c = await orig(n); const p = c.put; c.put = async (u, r) => { puts.push(String(u)); return p(u, r); }; return c; };
  const reqs = [];
  const fetchBad = async (u) => { reqs.push(String(u)); return new Response(new Uint8Array(K.KO.shards[0]), { status: 200 }); };     // right size, wrong bytes
  const fetchShort = async (u) => { reqs.push(String(u)); return new Response(new Uint8Array(1000), { status: 200 }); };
  class W { } const st = mkStore();
  const mk = (f) => K.createKokoro({ storage: st, fetch: f, caches, crypto: webcrypto, Worker: W, Blob, URL: { createObjectURL: () => 'blob:w' } });
  let e1 = null; try { await mk(fetchBad).download(() => {}); } catch (e) { e1 = e; }
  let e2 = null; try { await mk(fetchShort).download(() => {}); } catch (e) { e2 = e; }
  ck('b. Kokoro refuses a tampered model part (right size, wrong SHA-256) and a damaged one; nothing is installed, not marked ready, huggingface.co never asked',
    e1 && /checksum/.test(e1.message) && e2 && /damaged/.test(e2.message) && !puts.length && st.getItem('jarvis.kokoro.ready') === null && reqs.every((u) => u.startsWith('https://cdn.jsdelivr.net/npm/kokoro-q8-shards@1.0.0/')), [e1 && e1.message, e2 && e2.message, puts, reqs]);
  const k = mk(async () => new Response('x'));
  ck('b. Kokoro supported() says why when it cannot run (no worker / old iPhone) and synth() refuses before a download',
    (() => { const s = K.createKokoro({ storage: st, caches, crypto: webcrypto, Worker: undefined, Blob, URL }).supported(); return !s.ok && /worker/i.test(s.why); })() && await k.synth('x').then(() => false, (e) => /not downloaded/.test(e.message)));
  ck('b. Kokoro: 4 voices, an exact-version CDN list, model 92,361,116 bytes in 6 parts that add up', K.KO.shards.reduce((a, b) => a + b, 0) === K.KO.modelBytes && Object.keys(K.KO.voices).length === 4 && /^[0-9a-f]{64}$/.test(K.KO.modelSha256));
}
// a damaged download after the flag was set (storage cleared): synth clears the flag and never reaches for huggingface.co
{
  const st = mkStore({ 'jarvis.kokoro.ready': '1' }); class W { constructor() { throw new Error('must not start'); } }
  const k = K.createKokoro({ storage: st, fetch: async () => { throw new Error('no network'); }, caches: mkCaches(), crypto: webcrypto, Worker: W, Blob, URL: { createObjectURL: () => 'blob:w' } });
  const er = await k.synth('hello').then(() => null, (e) => e);
  ck('b. Kokoro: the phone cleared its storage -> "cleared from this phone", the ready flag is dropped, no worker started', er && /cleared/.test(er.message) && st.getItem('jarvis.kokoro.ready') === null, er && er.message);
}
realLog(JSON.stringify(out));
"""


def part_node(tmp):
    script = os.path.join(tmp, "engines.mjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write(NODE)
    r = subprocess.run(["node", script, JV], capture_output=True, text=True, timeout=180)
    if r.returncode:
        check("b. the engines run in node", False, (r.stderr or r.stdout)[-1500:])
        return
    for o in json.loads(r.stdout.strip().splitlines()[-1]):
        check(o["name"], o["ok"], o["info"])


# ------------------------------------------------------------------------------------------------ c. the page
def b64(n):
    return base64.b64encode(bytes((i // 2) % 100 for i in range(n))).decode()


MEDIA = """
window.__plays = []; window.__pauses = 0;
HTMLMediaElement.prototype.play = function () { window.__plays.push({ src: String(this.src).slice(0, 20), vol: this.volume }); const el = this; if (this.volume > 0) setTimeout(() => el.dispatchEvent(new Event('ended')), window.__clipMs || 40); return Promise.resolve(); };
HTMLMediaElement.prototype.pause = function () { window.__pauses++; };
"""


def page(br, url, keys, device=None, voices=True):
    kw = dict(device or {})
    kw.update(service_workers="block")
    if not device:
        kw.update(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx = br.new_context(**kw)
    H.feeds(ctx, H.kalshi_feed())
    ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off'); } catch (e) {}")
    if keys:
        ctx.add_init_script("try { localStorage.setItem('jarvis.smart', JSON.stringify({ v: 2, on: false, provider: 'groq', keys: %s })); } catch (e) {}" % json.dumps(keys))
    ctx.add_init_script(f"window.__iosRule = {json.dumps(bool(device))}; window.__voicesEmpty = {json.dumps(not voices)};")
    ctx.add_init_script(T.MOCK)
    ctx.add_init_script(MEDIA)
    net = {"gemini": [], "groq": [], "other": []}

    def cors(route, body, status=200, ctype="application/json", extra=None):
        h = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "POST, OPTIONS"}
        h.update(extra or {})
        route.fulfill(status=status, body=body, content_type=ctype, headers=h)

    def gemini(route):
        if route.request.method == "OPTIONS":
            return cors(route, "", 204)
        net["gemini"].append({"url": route.request.url, "key": route.request.headers.get("x-goog-api-key"), "body": json.loads(route.request.post_data or "{}")})
        if net.get("gemini_fail"):
            return cors(route, '{"error":{"message":"quota"}}', 429, extra={"retry-after": "120"})
        cors(route, json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": b64(9600)}}]}}]}))

    def groq(route):
        if route.request.method == "OPTIONS":
            return cors(route, "", 204)
        net["groq"].append({"url": route.request.url, "auth": route.request.headers.get("authorization"), "body": json.loads(route.request.post_data or "{}")})
        if net.get("groq_terms"):
            return cors(route, '{"error":{"code":"model_terms_required","message":"accept the terms"}}', 400)
        wav = bytearray(b"RIFF" + (36 + 4800).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
                        + (24000).to_bytes(4, "little") + (48000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") + b"data" + (4800).to_bytes(4, "little"))
        wav += bytes(4800)
        cors(route, bytes(wav), 200, "audio/wav")

    ctx.route("https://generativelanguage.googleapis.com/**", gemini)
    ctx.route("https://api.groq.com/**", groq)
    ctx.route(re.compile(r"https://(cdn\.jsdelivr\.net|huggingface\.co|unpkg\.com)/.*"), lambda r: (net["other"].append(r.request.url), r.abort()))
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text and "WebGL" not in m.text
         and "net::ERR" not in m.text and "Failed to fetch" not in m.text else None)
    p.goto(url + "jarvis/")
    H.ready(p)
    p.wait_for_function("document.documentElement.dataset.voiceout === 'module' && document.documentElement.dataset.engines === 'module' && !!window.__jarvis.voice()", timeout=90000)
    return ctx, p, errs, net


def idle(p, ms=60000):
    p.wait_for_function("window.__jarvis.state() === 'idle' && !window.__jarvis.voice().speaking", timeout=ms)


def part_page(br, url, name, device=None):
    tag = f"c[{name}]"
    KEY = "AIzaFAKEKEY0123456789"
    ctx, p, errs, net = page(br, url, {"gemini": KEY}, device=device)
    for _ in range(4):                                              # the first tap: unlocks the shared audio element on the iPhone (a loaded machine may need a second)
        p.mouse.click(3, 420)
        try:
            p.wait_for_function("window.__plays.length >= 1", timeout=5000)
            break
        except Exception:
            pass
    p.wait_for_function("window.__plays.length >= 1", timeout=5000)
    check(f"{tag} the first tap unlocks ONE shared audio element with a silent clip (volume 0)", p.evaluate("window.__plays[0].src.startsWith('data:audio/wav')") and p.evaluate("window.__plays[0].vol") == 0, p.evaluate("window.__plays"))
    p.evaluate("window.__said = []; window.__plays = []")
    p.evaluate("window.__jarvis.talk('Your room is $1,133 today, and the week is up 2.5%.')")
    p.wait_for_function("window.__plays.length >= 1", timeout=15000)
    idle(p)
    g = net["gemini"]
    sent = " ".join(x["body"]["contents"][0]["parts"][0]["text"] for x in g)
    check(f"{tag} a saved Gemini key: Auto speaks with Gemini; the request has the numbers in words, the key only in the x-goog-api-key header",
          g and "eleven hundred thirty three dollars" in sent and "two point five percent" in sent and "$" not in sent and all(x["key"] == KEY and KEY not in x["url"] and KEY not in json.dumps(x["body"]) for x in g), (sent, [x["url"] for x in g]))
    plays = p.evaluate("window.__plays")
    said = [x for x in p.evaluate("window.__said") if x["text"].strip()]
    check(f"{tag} the clip plays through the shared element (volume 1) and the phone voice stays silent", plays and plays[0]["vol"] == 1 and not said and p.evaluate("window.__jarvis.voice().speaking") is False, (plays, said))
    # barge-in: a tap on the core while a clip plays (the mocked clip lasts 6 s)
    p.evaluate("window.__clipMs = 6000; window.__plays = []")
    p.evaluate("window.__jarvis.talk('This is a reply that will be stopped by a tap on the core.')")
    p.wait_for_function("window.__plays.length >= 1 && window.__jarvis.voice().speaking === true", timeout=15000)
    p.wait_for_timeout(700)
    n0 = p.evaluate("window.__pauses")
    p.click("#stage", position={"x": 40, "y": 40})
    p.wait_for_function("window.__jarvis.voice().speaking === false", timeout=5000)
    check(f"{tag} a tap stops her at once (the audio element is paused, no longer speaking)", p.evaluate("window.__pauses") > n0, (n0, p.evaluate("window.__pauses")))
    p.evaluate("window.__clipMs = 40")
    if p.evaluate("window.__jarvis.state()") == "listening":
        p.click("#stage", position={"x": 40, "y": 40})
    # the Voice sheet
    idle(p)
    p.evaluate("document.getElementById('vset').click()")
    p.wait_for_function("!document.getElementById('voice').hidden", timeout=5000)
    sheet = p.evaluate("""({ box: !document.getElementById('vEngBox').hidden, opts: [...document.getElementById('vEngine').options].map((o) => o.value), mode: document.getElementById('vEngine').value,
      note: document.getElementById('vEngNote').textContent, cv: [...document.getElementById('vCVoice').options].map((o) => o.value), samples: document.querySelectorAll('#vSamples [data-sample]').length,
      prem: document.getElementById('vPremium').textContent, cloud: document.getElementById('vCloud').checked, dl: !document.getElementById('vDevDl').hidden, pros: document.getElementById('vProsody').checked })""")
    check(f"{tag} the Voice sheet: four engines (Auto chosen), the Gemini voices, 3 samples, the Premium guide with the exact iPhone steps, Natural speech on",
          sheet["box"] and sheet["opts"] == ["auto", "cloud", "device", "phone"] and sheet["mode"] == "auto" and "Gemini" in sheet["note"] and "Kore" in sheet["cv"] and sheet["samples"] == 3
          and "Accessibility → Spoken Content → Voices → English" in sheet["prem"] and sheet["cloud"] and sheet["pros"], sheet)
    p.evaluate("window.__plays = []")
    n1 = len(net["gemini"])
    p.click("#vSamples [data-sample='1']")
    p.wait_for_function("window.__plays.length >= 1", timeout=15000)
    sample = net["gemini"][n1]["body"]["contents"][0]["parts"][0]["text"]
    check(f"{tag} sample 'trade' is said with the chosen engine, tickers and times in words", "N Q opens at nine thirty A M" in sample and "don't" in sample and "eight R" in sample, sample)
    idle(p)
    p.click("#vTest")
    p.wait_for_function("window.__plays.length >= 2", timeout=15000)
    idle(p)
    last = net["gemini"][-1]["body"]["contents"][0]["parts"][0]["text"]
    check(f"{tag} Test voice still says its one natural sentence", last == "Hi, I'm Jarvis, and this is how I'll sound when I read your answers out loud.", last)
    # the phone voice engine
    p.select_option("#vEngine", "phone")
    p.evaluate("window.__said = []; window.__plays = []")
    n2 = len(net["gemini"])
    p.evaluate("window.__jarvis.talk('Your room is $1,133 today.')")
    p.wait_for_function("window.__said.filter((x) => x.text.trim()).length >= 1", timeout=15000)
    idle(p)
    said = [x["text"] for x in p.evaluate("window.__said") if x["text"].strip()]
    check(f"{tag} Phone voice: nothing is fetched; the phone says it with the number in words", len(net["gemini"]) == n2 and said and "eleven hundred thirty three dollars" in said[0] and not p.evaluate("window.__plays"), (said, len(net["gemini"]), n2))
    p.select_option("#vEngine", "device")
    p.wait_for_function("document.getElementById('vEngNote').textContent.indexOf('Download the on-device voice') >= 0", timeout=5000)
    dl = p.evaluate("({ dl: !document.getElementById('vDevDl').hidden, note: document.getElementById('vDevNote').textContent })")
    check(f"{tag} On-device neural before the download: the note says to download, the phone voice is used meanwhile, the button shows the size", dl["dl"] and "115 MB" in dl["note"], dl)
    p.click("#vDevDl")
    p.wait_for_function("document.getElementById('vDevNote').textContent.indexOf('did not finish') >= 0", timeout=60000)
    check(f"{tag} the on-device download failing (no network to the CDN) says so politely, the button is back, nothing broke",
          p.evaluate("!document.getElementById('vDevDl').disabled") and not any("huggingface" in u for u in net["other"]) and not errs, (net["other"][:3], errs))
    # Premium guide: only compact voices on this phone
    check(f"{tag} the Premium guide names the voice the phone has now", "Ava" in p.evaluate("document.getElementById('vPremNote').textContent"), p.evaluate("document.getElementById('vPremNote').textContent"))
    check(f"{tag} no page errors", not errs, errs)
    ctx.close()
    # a Groq key only; its terms refusal -> the phone's voice for that reply + one plain toast
    ctx, p, errs, net = page(br, url, {"groq": "gsk_FAKEKEY0123456789"}, device=device)
    for _ in range(4):
        p.mouse.click(3, 420)
        try:
            p.wait_for_function("window.__plays.length >= 1", timeout=5000)
            break
        except Exception:
            pass
    p.wait_for_function("window.__plays.length >= 1", timeout=5000)
    net["groq_terms"] = True
    p.evaluate("window.__said = []; window.__plays = []")
    p.evaluate("window.__jarvis.talk('Hello from the Groq voice.')")
    p.wait_for_function("window.__said.filter((x) => x.text.trim()).length >= 1", timeout=15000)
    idle(p)
    toast = p.evaluate("document.body.textContent")
    check(f"{tag} Groq asked first (Authorization header, Orpheus), refused for its terms: the phone says the reply, one plain toast says what to do",
          net["groq"] and net["groq"][0]["auth"] == "Bearer gsk_FAKEKEY0123456789" and net["groq"][0]["body"]["model"] == "canopylabs/orpheus-v1-english" and not net["gemini"]
          and [x["text"] for x in p.evaluate("window.__said") if x["text"].strip()] and "console.groq.com/playground?model=canopylabs/orpheus-v1-english" in toast, (net["groq"][:1], toast[-300:]))
    net["groq_terms"] = False
    check(f"{tag} no page errors (Groq)", not errs, errs)
    ctx.close()


# ------------------------------------------------------------------------------------------------ d. the real Kokoro model (optional, heavy)
KO_PAGE = """<!doctype html><meta charset=utf-8><title>ko</title><script type=module>
import { createKokoro } from '/kokoro-engine.js';
const k = createKokoro({}); window.k = k;
window.go = async (text) => {
  try {
    const out = { sup: k.supported() };
    if (!k.ready()) await k.download(() => {});
    const t = performance.now();
    const blob = await k.synth(text, { voice: 'af_heart' });
    const b = new Uint8Array(await blob.arrayBuffer());
    let peak = 0; const dv = new DataView(b.buffer); for (let i = 44; i + 1 < b.length; i += 2) peak = Math.max(peak, Math.abs(dv.getInt16(i, true)));
    return Object.assign(out, { ms: Math.round(performance.now() - t), secs: (b.length - 44) / 48000, riff: String.fromCharCode(...b.slice(0, 4)), peak, downloaded: await k.downloaded() });
  } catch (e) { return { err: String((e && e.stack) || e) }; }
};
window.ready = true;</script>"""


def part_kokoro(pw, exe):
    d = os.environ.get("KOKORO_DIR", "")
    need = ["kokoro.web.js", "ort.mjs", "ort.wasm", "af_heart.bin", "af_bella.bin", "af_nicole.bin", "bf_emma.bin"] + [f"p{i}.bin" for i in range(6)]
    if os.environ.get("RUN_KOKORO") != "1" or not all(os.path.exists(os.path.join(d, f)) for f in need):
        print("[SKIP] d. the real Kokoro model (RUN_KOKORO=1 and KOKORO_DIR=<dir with the CDN files>): heavy, run by hand", flush=True)
        return
    import http.server
    import threading

    class S(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body, ct = (KO_PAGE.encode(), "text/html") if self.path == "/" else (open(os.path.join(JV, "kokoro-engine.js"), "rb").read(), "text/javascript") if self.path == "/kokoro-engine.js" else (b"", "text/plain")
            self.send_response(200 if body else 404); self.send_header("content-type", ct); self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "https://cdn.jsdelivr.net/npm/"
    mp = {base + "kokoro-js@1.2.1/dist/kokoro.web.js": ("kokoro.web.js", "text/javascript"),
          base + "@huggingface/transformers@3.5.1/dist/ort-wasm-simd-threaded.jsep.mjs": ("ort.mjs", "text/javascript"),
          base + "@huggingface/transformers@3.5.1/dist/ort-wasm-simd-threaded.jsep.wasm": ("ort.wasm", "application/wasm")}
    for i in range(6):
        mp[base + f"kokoro-q8-shards@1.0.0/kokoro-q8.part{i}.bin"] = (f"p{i}.bin", "application/octet-stream")
    for v in ("af_heart", "af_bella", "af_nicole", "bf_emma"):
        mp[base + f"kokoro-js@1.2.1/voices/{v}.bin"] = (v + ".bin", "application/octet-stream")
    br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
    ctx = br.new_context()
    other = []

    def route(r):
        u = r.request.url
        if u.startswith("http://127.0.0.1") or u.startswith("blob:") or u.startswith("data:"):
            return r.continue_()
        if u in mp:
            f, ct = mp[u]
            return r.fulfill(status=200, body=open(os.path.join(d, f), "rb").read(), headers={"content-type": ct, "access-control-allow-origin": "*", "cross-origin-resource-policy": "cross-origin"})
        other.append(u)
        r.abort()
    ctx.route("**/*", route)
    p = ctx.new_page()
    p.goto(f"http://127.0.0.1:{srv.server_address[1]}/")
    p.wait_for_function("window.ready === true", timeout=30000)
    r = p.evaluate("window.go('Your room today is eleven hundred thirty three dollars, and the week is up two point five percent.')")
    check("d. the real Kokoro model: downloaded from the (mocked) CDN, parts joined and checked, speaks 24 kHz WAV, never asked huggingface.co or anything else",
          "err" not in r and r["riff"] == "RIFF" and r["secs"] > 3 and r["peak"] > 3000 and r["downloaded"] and not other, (r, other))
    br.close()
    srv.shutdown()


def webkit_ready():
    return bool(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", os.path.expanduser("~/.cache/ms-playwright")), "webkit-*")))


def main():
    part_files()
    tmp = tempfile.mkdtemp(prefix="le_jarvis_engines_")
    part_node(tmp)
    path = H.site(tmp, "T", "asis")
    srv = H.serve(tmp)
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + path
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"], **({"executable_path": exe} if exe else {}))
            part_page(br, url, "chromium")
            br.close()
            part_kokoro(pw, exe)
            if webkit_ready():
                br = pw.webkit.launch()
                part_page(br, url, "webkit iPhone 13", device=pw.devices["iPhone 13"])
                br.close()
            else:
                print("[SKIP] WebKit is not installed: PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright install webkit", flush=True)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis engines: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
