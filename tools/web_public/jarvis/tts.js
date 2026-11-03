// Jarvis's voice (owner 2026-11-03: "a voice that doesn't sound like a bot. Should be a female voice."). One ES module, no
// imports, no DOM except speechSynthesis / Audio when a speaker is made. Shared by the Jarvis screen (index.html speak()) and
// voice mode (voice-mode.js), so both use the same chosen voice.
//
//   import { bestVoice, voiceChoices, voiceScore, voiceLabel, cleanSpeech, speechChunks, createSpeaker, savedVoiceName } from './tts.js';
//   voiceScore(v)              a natural female English voice first (Ava / Zoe / Allison / Samantha, premium > enhanced > compact);
//                              male voices low; novelty voices (Zarvox, Bubbles, ...) 0 = never; not English -1
//   bestVoice(list, saved?)    the owner's pick while the phone has it, else the best scored voice (null = the phone's default)
//   voiceChoices(list)         every English voice worth offering, best first (the Voice picker, voice mode's VOICE button)
//   cleanSpeech(text)          what is said: no markdown, emojis, links or symbols; money, %, k / M, /mo said in words
//   speechChunks(text, max?)   natural sentence chunks (<= max chars, split at . ! ? then ; : , then a space), commas added
//                              before "but / so / because" in long sentences
//   createSpeaker({ synth, voices(), cfg(), cloud() , fetch, Audio })
//     .speak(text, { onstart, onend, onboundary(charIndex in the cleaned text), onstall(rest) }) -> { text (cleaned), cancel() }
//     .cancel() · .speaking · .prime() (a silent utterance: call it inside a tap, the iPhone's unlock)
//   One utterance per chunk, each started when the last one ends, with a 140 ms breath between sentences (shorter chunks also
//   keep Chrome from cutting long utterances off).
//   iPhone traps handled here (2026-11-03 evening, owner: "the Jarvis isn't talking"): each utterance stays referenced until
//   it ends (a collected one loses its events); a chunk whose end never comes is passed by a watchdog; one that never starts
//   (WebKit silently drops a speak() made before any tap) calls onstall(rest), so the caller can say it at the next tap; a
//   speak() right after cancel() waits 70 ms (WebKit swallows it otherwise); a paused voice is resumed; rate and pitch are
//   always finite and in range (an out-of-range value throws).
//   primeSpeech(synth)         one silent utterance (volume 0): inside a tap it lifts WebKit's tap-only rule for the page
//   needsPrimer(navigator)     true on Apple WebKit (iPhone Safari, the Home Screen app, any iPhone browser): only a speak()
//                              inside a tap unlocks the voice there; Chrome / Android / Edge unlock on any earlier tap
//
// The optional cloud voice (Groq's Orpheus text-to-speech on the owner's own free Groq key): only when he turns it on AND has
// a Groq key (the smart-mode one). The key is sent only to api.groq.com. Any failure (no key, the model's terms not accepted,
// a rate limit, offline, the audio blocked) falls back to the phone's voice for that reply; a 429 parks it until tomorrow.
// iPhone Safari 16: plain ES2020, no regex lookbehind.

export const CFG_KEY = 'jarvis.voiceCfg';           // { voice, rate, pitch } (the shell's Voice sheet)
export const VM_KEY = 'jarvis.vmVoice';             // voice mode's old pick (read as a fallback, kept in step)
export const CLOUD_KEY = 'jarvis.tts';               // { cloud: bool, voice: 'hannah' | 'diana' | 'autumn' }
export const DEFAULTS = { rate: 1.0, pitch: 1.0 };
const PAUSE_MS = 140;                                 // the breath between two sentences (half after a comma cut)
const AFTER_CANCEL_MS = 70;                           // WebKit swallows a speak() made right after cancel()
const START_MS = 5000;                                // a chunk not started by then never will (no tap yet on the iPhone)
const num = (v, lo, hi, d) => { const x = +v; return v != null && v !== '' && Number.isFinite(x) && x >= lo && x <= hi ? x : d; };
const safe = (f, d) => { try { return f(); } catch (_) { return d; } };
export const CLOUD = { url: 'https://api.groq.com/openai/v1/audio/speech', model: 'canopylabs/orpheus-v1-english', voices: ['hannah', 'diana', 'autumn'], max: 200 };

// ------------------------------------------------------------------------------------------------ ranking the phone's voices
// Novelty / robotic voices: never picked, never offered.
const NOVELTY = /\b(albert|bad news|bahh|bells|boing|bubbles|cellos|good news|jester|organ|superstar|trinoids|whisper|wobble|zarvox|deranged|hysterical|pipe organ|grandma|grandpa|eddy|flo|reed|rocko|sandy|shelley|fred|junior|ralph|kathy|princess|vicki|victoria)\b/i;
// natural female voices, best first (iOS / macOS names, Chrome's Google voices, Edge's natural voices)
const FEMALE = [
  [/\bava\b/i, 60], [/\bzoe\b/i, 56], [/\ballison\b/i, 52], [/\bsamantha\b/i, 48], [/google uk english female/i, 46], [/\b(aria|jenny|sonia|libby|michelle|emma|ana|natasha|clara)\b.*\b(natural|online)\b/i, 46],
  [/\b(serena|kate|susan|stephanie|evelyn|nicky|joelle|noelle|tessa|moira|karen|fiona|veena|catherine|siri female|isha|hazel|zira|heera)\b/i, 34],
  [/google us english/i, 36],
];
const MALE = /\b(daniel|alex|tom|aaron|arthur|oliver|rishi|gordon|lee|evan|nathan|malcolm|george|jamie|guy|ryan|david|mark|christopher|eric|roger|steffan|thomas|male)\b/i;
const isEnglish = (v) => !!v && /^en([-_]|$)/i.test(String(v.lang || ''));
export function voiceScore(v) {
  if (!isEnglish(v)) return -1;
  const name = String(v.name || ''), id = `${name} ${v.voiceURI || ''}`;
  if (NOVELTY.test(name)) return 0;
  let s = 10;
  const f = FEMALE.find((x) => x[0].test(name));
  if (f) s += f[1];
  else if (MALE.test(name)) s -= 40;               // offered, never chosen over a female voice (even a premium one)
  if (/premium/i.test(id)) s += 50;
  else if (/enhanced|neural|natural/i.test(id)) s += 30;
  if (/compact/i.test(id)) s -= 10;
  if (/^en[-_]us/i.test(v.lang)) s += 4; else if (/^en[-_](gb|au|ie|ca)/i.test(v.lang)) s += 2;
  if (v.localService) s += 1;
  return Math.max(1, s);
}
export function bestVoice(list, saved) {
  const all = Array.isArray(list) ? list.filter(Boolean) : [];
  const mine = saved ? all.find((v) => v.name === saved && voiceScore(v) > 0) : null;
  if (mine) return mine;
  let best = null, bs = 0;
  for (const v of all) { const s = voiceScore(v); if (s > bs) { bs = s; best = v; } }
  return best;
}
export function voiceChoices(list) {
  return (Array.isArray(list) ? list.filter(Boolean) : []).filter((v) => voiceScore(v) > 0).sort((a, b) => voiceScore(b) - voiceScore(a));
}
// "Ava (Premium)" -> "Ava · Premium", for the picker
export function voiceLabel(v) {
  if (!v) return 'Automatic';
  const id = `${v.name || ''} ${v.voiceURI || ''}`, base = String(v.name || '').replace(/\s*\(.*\)$/, '').replace(/^Microsoft\s+|\s+Online.*$/g, '');
  const q = /premium/i.test(id) ? 'Premium' : /enhanced|neural|natural/i.test(id) ? 'Enhanced' : /compact/i.test(id) ? 'Compact' : '';
  return [base, q, String(v.lang || '').replace('_', '-')].filter(Boolean).join(' · ');
}
// the owner's saved pick: the Voice sheet's, else voice mode's older one
export function savedVoiceName(storage) {
  const st = storage || (typeof localStorage !== 'undefined' ? localStorage : null);
  try { const c = JSON.parse((st && st.getItem(CFG_KEY)) || '{}'); if (c && typeof c.voice === 'string' && c.voice) return c.voice; } catch (_) { /* junk */ }
  try { return (st && st.getItem(VM_KEY)) || ''; } catch (_) { return ''; }
}
export function voiceCfg(storage) {
  const st = storage || (typeof localStorage !== 'undefined' ? localStorage : null);
  let c = {};
  try { c = JSON.parse((st && st.getItem(CFG_KEY)) || '{}') || {}; } catch (_) { c = {}; }
  const rate = +c.rate, pitch = +c.pitch;
  return { voice: typeof c.voice === 'string' ? c.voice : '', rate: rate >= 0.5 && rate <= 2 ? rate : DEFAULTS.rate, pitch: pitch >= 0.5 && pitch <= 2 ? pitch : DEFAULTS.pitch };
}

// ------------------------------------------------------------------------------------------------ what is said
const EMOJI = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}\u{20E3}]/gu;
const UNIT = { k: 'thousand', K: 'thousand', m: 'million', M: 'million', b: 'billion', B: 'billion' };
const PER = { mo: 'a month', month: 'a month', wk: 'a week', week: 'a week', day: 'a day', d: 'a day', hr: 'an hour', h: 'an hour', yr: 'a year', year: 'a year' };
export function cleanSpeech(input) {
  let s = String(input == null ? '' : input);
  s = s.replace(/```[\s\S]*?```/g, ' ').replace(/`([^`]*)`/g, '$1');                         // code: never read out
  s = s.replace(/\[([^\]]+)\]\((?:https?:)?[^)]*\)/g, '$1').replace(/\bhttps?:\/\/\S+/gi, 'a link').replace(/\bwww\.\S+/gi, 'a link');
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, '').replace(/^\s*>\s?/gm, '').replace(/^\s*(?:[-*+•]|\d+[.)])\s+/gm, '').replace(/\*\*|__|~~|\*/g, '');
  s = s.replace(EMOJI, ' ').replace(/\|/g, ', ').replace(/\[([^\]]{1,80})\]/g, '$1');
  s = s.replace(/([.!?:;,])?[ \t]*\n+\s*/g, (m0, p) => (p ? p + ' ' : '. '));
  s = s.replace(/\s*(?:->|→|=>)\s*/g, ', then ').replace(/\s+[–—]\s+|\s+-\s+/g, ', ');
  s = s.replace(/\be\.g\.,?/gi, 'for example').replace(/\bi\.e\.,?/gi, 'that is').replace(/\betc\./gi, 'and so on').replace(/\bw\/(?=\s)/gi, 'with').replace(/\bvs\.?(?=\s)/gi, 'versus');
  s = s.replace(/\bapprox\.?(?=\s)/gi, 'about').replace(/~\s?(?=\$?\d)/g, 'about ').replace(/#(\d)/g, 'number $1');
  // money: "$1.2k" -> "1.2 thousand dollars", "+$213" -> "up 213 dollars", "$2,000/mo" -> "2,000 dollars a month"
  s = s.replace(/([+−-])\$(\d[\d,]*(?:\.\d+)?)([kKmMbB])?\b/g, (m0, sg, n, u, at, all) => {
    const said = /\b(made|earned|won|gained|lost|of|is|was|at)\s*$/i.test(all.slice(Math.max(0, at - 12), at));     // "made +$213": no "up"
    return `${said ? '' : sg === '+' ? 'up ' : 'down '}${n}${u ? ' ' + UNIT[u] : ''} dollars`;
  });
  s = s.replace(/\$(\d[\d,]*(?:\.\d+)?)([kKmMbB])?\b/g, (m0, n, u) => `${n}${u ? ' ' + UNIT[u] : ''} dollar${n === '1' && !u ? '' : 's'}`);
  s = s.replace(/\b(\d+(?:\.\d+)?)([kK])\b/g, '$1 thousand').replace(/\b(\d+(?:\.\d+)?)M\b/g, '$1 million');
  s = s.replace(/ dollars?\s*\/\s*(mo|month|wk|week|day|d|hr|h|yr|year)\b/gi, (m0, u) => ` dollars ${PER[u.toLowerCase()] || 'per ' + u}`);
  s = s.replace(/\b(\d+)\s?x\b(?=\s|$|[.,])/g, '$1 times').replace(/(\d)\s?%/g, '$1 percent').replace(/(\d)\s?°F/g, '$1 degrees');
  s = s.replace(/\b(\d{1,2})(?::(\d\d))?\s?(am|pm)\b/gi, (m0, h, mi, ap) => `${h}${mi && mi !== '00' ? ':' + mi : ''} ${ap.toUpperCase()}`);
  s = s.replace(/(\d)\s?\+\s?(\d)/g, '$1 plus $2').replace(/(\d)\s?=\s?(\d)/g, '$1 equals $2').replace(/(\d)\+/g, '$1 or more');
  s = s.replace(/\s&\s/g, ' and ').replace(/&/g, ' and ').replace(/@/g, ' at ').replace(/[_^<>{}\\]/g, ' ').replace(/[()]/g, ', ').replace(/"|“|”/g, '');
  s = s.replace(/…|\.\.\./g, '. ').replace(/\s*;\s*/g, ', ').replace(/\s*,\s*(,\s*)+/g, ', ').replace(/\s+([,.!?])/g, '$1').replace(/([,.!?])(?=[A-Za-z])/g, '$1 ');
  s = s.replace(/,\s*([.!?])/g, '$1').replace(/^[,.\s]+/, '').replace(/\.\s*\./g, '.').replace(/\s+/g, ' ').trim();
  if (s && !/[.!?]$/.test(s)) s += '.';
  return s;
}
// a comma before "but / so / because ..." in a long sentence gives the voice a breath
function breathe(sentence) {
  if (sentence.split(' ').length < 10) return sentence;
  return sentence.replace(/([a-z0-9])\s+(but|so|because|although|though|which|unless|and then)\s+/gi, '$1, $2 ');
}
export function speechChunks(text, max) {
  const lim = Math.max(40, max || 180), out = [];
  const sentences = String(text || '').match(/[\s\S]*?[.!?]+(?=\s|$)|[\s\S]+?$/g) || [];     // "1.2" stays whole
  for (let raw of sentences) {
    let s = breathe(raw.trim());
    if (!s) continue;
    while (s.length > lim) {                        // a long sentence: cut at the last ; : , before the limit, else a space
      const cut = s.slice(0, lim);
      let i = Math.max(cut.lastIndexOf(', '), cut.lastIndexOf('; '), cut.lastIndexOf(': '));
      if (i < lim * 0.4) i = cut.lastIndexOf(' ');
      if (i < 10) i = lim;
      out.push(s.slice(0, i + 1).trim());
      s = s.slice(i + 1).trim();
    }
    if (s) out.push(s);
  }
  // very short pieces ride with the next one ("Okay." + "Done.") so the rhythm stays natural
  const merged = [];
  for (const c of out) {
    const prev = merged[merged.length - 1];
    if (prev && prev.length < 24 && prev.length + c.length + 1 <= lim) merged[merged.length - 1] = prev + ' ' + c;
    else merged.push(c);
  }
  return merged;
}

// ------------------------------------------------------------------------------------------------ the iPhone's unlock
const PRIMERS = [];                                   // kept referenced until they end
export function needsPrimer(nav) {
  const ua = String(((nav || (typeof navigator !== 'undefined' ? navigator : null)) || {}).userAgent || '');
  return /AppleWebKit/i.test(ua) && /iPhone|iPad|iPod|Macintosh/i.test(ua) && !/Chrome\/|Chromium|Edg\/|Android/i.test(ua);
}
export function primeSpeech(synth) {
  if (!synth || typeof SpeechSynthesisUtterance === 'undefined') return false;
  try {
    const u = new SpeechSynthesisUtterance(' ');
    u.volume = 0; u.rate = 1; u.pitch = 1; u.lang = 'en-US';
    u.onend = u.onerror = () => { const i = PRIMERS.indexOf(u); if (i >= 0) PRIMERS.splice(i, 1); };
    PRIMERS.push(u); if (PRIMERS.length > 4) PRIMERS.shift();
    if (synth.paused && typeof synth.resume === 'function') synth.resume();
    synth.speak(u);
    return true;
  } catch (_) { return false; }
}

// ------------------------------------------------------------------------------------------------ the speaker
export function createSpeaker(opts) {
  const o = opts && typeof opts === 'object' ? opts : {};
  const synth = o.synth !== undefined ? o.synth : (typeof speechSynthesis !== 'undefined' ? speechSynthesis : null);
  const own = () => safe(() => (synth ? synth.getVoices() || [] : []), []);
  const voices = () => { const l = typeof o.voices === 'function' ? safe(() => o.voices() || [], []) : []; return l.length ? l : own(); };   // the caller's list, else ask again
  const cfg = () => { try { return Object.assign({}, DEFAULTS, typeof o.cfg === 'function' ? o.cfg() || {} : voiceCfg()); } catch (_) { return Object.assign({}, DEFAULTS); } };
  const cloudCfg = () => { try { return typeof o.cloud === 'function' ? o.cloud() : null; } catch (_) { return null; } };   // { key, voice } | null
  const doFetch = (...a) => (typeof o.fetch === 'function' ? o.fetch : fetch)(...a);
  let cur = null, parkedDay = '', cancelT = 0;
  const live = [];                                    // the utterances being said, referenced until they end
  const drop = (u) => { const j = live.indexOf(u); if (j >= 0) live.splice(j, 1); };
  const hardCancel = () => { safe(() => synth.cancel()); cancelT = Date.now(); live.length = 0; };

  // one utterance per chunk, each started when the last one ends, with a short breath between them (PAUSE_MS)
  function phone(text, chunks, h) {
    const c = cfg(), rate = num(c.rate, 0.5, 2, 1), pitch = num(c.pitch, 0.5, 2, 1);
    let at = 0, i = 0;
    const busy = !!safe(() => synth.speaking || synth.pending, false);
    if (busy) hardCancel();
    const offs = chunks.map((chunk) => { const b = text.indexOf(chunk.slice(0, 12), at), off = b < 0 ? at : b; at = off + chunk.length; return off; });
    const next = () => {
      if (h.done) return;
      if (i >= chunks.length) { h.finish(); return; }
      const k = i++, u = new SpeechSynthesisUtterance(chunks[k]), off = offs[k];
      const v = bestVoice(voices(), c.voice || savedVoiceName(o.storage));     // read each time: the iPhone's list comes late
      if (v) { u.voice = v; u.lang = v.lang || 'en-US'; } else u.lang = 'en-US';    // no list yet: the phone's default voice
      u.rate = rate; u.pitch = pitch; u.volume = 1;
      let ended = false, started = false;
      const end = () => {
        if (ended || h.done) return;
        ended = true; clearTimeout(h.wd); drop(u);
        if (h.onboundary && k + 1 < chunks.length) h.onboundary(offs[k + 1]);
        if (k + 1 >= chunks.length) { h.finish(); return; }                    // the last one: done at once
        h.timer = setTimeout(next, /[.!?]$/.test(chunks[k]) ? PAUSE_MS : PAUSE_MS / 2);
      };
      const begin = () => {
        if (started || ended) return;
        started = true; clearTimeout(h.wd);
        if (k === 0 && !h.done && h.onstart) h.onstart();
        h.wd = setTimeout(end, 2500 + (chunks[k].length * 95) / rate);         // its end never came (iPhone): move on
      };
      u.onstart = begin;
      u.onboundary = (e) => { begin(); if (h.done || (e && e.name && e.name !== 'word')) return; if (h.onboundary) h.onboundary(off + (+(e && e.charIndex) || 0)); };
      u.onend = u.onerror = (e) => {
        if (e && (e.error === 'interrupted' || e.error === 'canceled')) { drop(u); return; }   // cancelled: the next reply owns the voice
        end();
      };
      live.push(u);
      safe(() => { if (synth.paused) synth.resume(); });
      synth.speak(u);
      // never started: WebKit dropped it (no tap yet), so the caller may say the rest at the next tap; else move on
      h.wd = setTimeout(() => {
        if (started || ended || h.done) return;
        if (safe(() => synth.speaking, false)) { begin(); return; }            // speaking without saying so (an old WebKit)
        if (typeof h.onstall === 'function') { h.stalled = true; drop(u); h.finish(); h.onstall(chunks.slice(k).join(' ')); return; }
        end();
      }, START_MS);
    };
    if (busy || Date.now() - cancelT < AFTER_CANCEL_MS) h.timer = setTimeout(next, AFTER_CANCEL_MS); else next();
  }
  async function cloud(text, chunks, h, cc) {
    const audio = typeof o.Audio === 'function' ? o.Audio : (typeof Audio !== 'undefined' ? Audio : null);
    if (!audio || typeof URL === 'undefined' || !URL.createObjectURL) throw new Error('no audio');
    const parts = [];
    for (const c of chunks) { let s = c; while (s.length > CLOUD.max) { let i = s.lastIndexOf(' ', CLOUD.max); if (i < 20) i = CLOUD.max; parts.push(s.slice(0, i)); s = s.slice(i).trim(); } if (s) parts.push(s); }
    const fetchOne = (input) => doFetch(CLOUD.url, { method: 'POST', headers: { Authorization: 'Bearer ' + cc.key, 'content-type': 'application/json' },
      body: JSON.stringify({ model: CLOUD.model, voice: CLOUD.voices.includes(cc.voice) ? cc.voice : CLOUD.voices[0], input, response_format: 'wav' }) })
      .then(async (r) => { if (!r || !r.ok) { const e = new Error('HTTP ' + (r ? r.status : '?')); e.status = r ? r.status : 0; throw e; } return r.blob(); });
    let next = fetchOne(parts[0]), at = 0;
    for (let i = 0; i < parts.length; i++) {
      const blob = await next;
      if (h.done) return;
      if (i + 1 < parts.length) next = fetchOne(parts[i + 1]);     // the next piece downloads while this one plays
      const url = URL.createObjectURL(blob), a = new audio(url), off = text.indexOf(parts[i].slice(0, 12), at);
      at = (off < 0 ? at : off) + parts[i].length;
      h.audio = a;
      await new Promise((ok, bad) => {
        a.onended = ok; a.onerror = () => bad(new Error('audio'));
        const p = a.play(); if (p && typeof p.catch === 'function') p.catch(bad);
        if (i === 0 && h.onstart) h.onstart();
        if (h.onboundary) h.onboundary(off < 0 ? 0 : off);
      }).finally(() => { try { URL.revokeObjectURL(url); } catch (_) { /* gone */ } });
      if (h.done) return;
    }
    h.finish();
  }
  function speak(input, cb) {
    cancel();
    const c = cb && typeof cb === 'object' ? cb : {};
    const text = cleanSpeech(input), chunks = speechChunks(text);
    const h = { done: false, onstart: c.onstart, onboundary: c.onboundary, onstall: c.onstall, audio: null,
      finish() { if (h.done) return; h.done = true; clearTimeout(h.timer); clearTimeout(h.wd); if (cur === h) cur = null; if (!h.stalled && typeof c.onend === 'function') c.onend(); } };
    h.cancel = () => { if (h.done) return; h.done = true; clearTimeout(h.timer); clearTimeout(h.wd); if (cur === h) cur = null; if (h.audio) try { h.audio.pause(); } catch (_) { /* stopped */ } if (synth) hardCancel(); };
    cur = h;
    if (!chunks.length) { setTimeout(() => h.finish(), 0); return { text, cancel: h.cancel }; }
    const cc = cloudCfg(), today = new Date().toDateString();
    const usePhone = () => { if (h.done) return; if (synth && typeof SpeechSynthesisUtterance !== 'undefined') { try { phone(text, chunks, h); } catch (_) { h.finish(); } } else h.finish(); };
    if (cc && cc.key && parkedDay !== today) {
      cloud(text, chunks, h, cc).catch((e) => { if (e && e.status === 429) parkedDay = today; if (!h.done) { if (typeof c.onfallback === 'function') c.onfallback(e); usePhone(); } });
    } else usePhone();
    return { text, cancel: h.cancel };
  }
  function cancel() { if (cur) cur.cancel(); cur = null; }
  return { speak, cancel, get speaking() { return !!cur; }, prime: () => primeSpeech(synth), voice: () => bestVoice(voices(), cfg().voice || savedVoiceName(o.storage)) };
}
export default createSpeaker;
