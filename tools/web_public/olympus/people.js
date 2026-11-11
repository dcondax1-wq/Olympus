// PEOPLE OF OLYMPUS (docs/PERSONA_API.md): see any worker as a person and talk to them. ES module; also window.OLYMPUS_PEOPLE.
//   <script type="module" src="../olympus/people.js?v=p1"></script>      then, anywhere:  if (window.OLYMPUS_PEOPLE) OLYMPUS_PEOPLE.open('scanner:sibyl')
// A person is a friendly cartoon character that speaks for ONE real worker and only from that worker's own published files (people-core.js builds the facts,
// people-talk.js answers offline). Nothing is sent anywhere, with one exception the owner set up himself: when Jarvis's "Connect my brain" is on, a question
// the offline engine cannot answer goes to his own model with the persona and the facts (people-brain.js), and a reply with an invented number is dropped.
// A person cannot place orders, change files or predict prices. Requests are notes kept on this phone (localStorage olympus.requests.v1) for the owner to copy to Claude.
// Text only through textContent / createElementNS: no markup is ever built from data.
import * as C from './people-core.js';
import * as T from './people-talk.js';
import { createData } from './people-data.js';
import { connection, askModel } from './people-brain.js';

const NS = 'http://www.w3.org/2000/svg';
const REQ_KEY = 'olympus.requests.v1', ME_KEY = 'olympus.me.v1', MEM_KEY = 'olympus.people.mem.v1', SPEAK_KEY = 'olympus.people.speak';
const D = createData();
const S = { roster: C.normRoster(null), ready: null, facts: new Map(), provided: new Map(), mem: new Map(), sheet: null, cur: null, log: [], busy: false, anchor: null, blinkT: 0, rec: null };
const reduced = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (_) { return false; } };
const store = { get(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (_) { return null; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (_) { return false; } } };
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
function svgNode(n) { const e = document.createElementNS(NS, n.tag); for (const k in n.attrs) if (k !== 'xmlns') e.setAttribute(k, n.attrs[k]); for (const c of n.children) e.appendChild(svgNode(c)); return e; }
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
const fire = (name, detail) => { try { window.dispatchEvent(new CustomEvent(name, { detail })); } catch (_) { /* old browser */ } };

// ------------------------------------------------------------------------------------------------ roster
function ready() {
  if (!S.ready) S.ready = D.roster().then((j) => { S.roster = C.normRoster(j); }, () => { S.roster = C.normRoster(null); });
  return S.ready;
}
function get(id) { if (id === 'me') return me(); if (C.isObj(id) && id.id) return id; return C.resolve(S.roster, id); }
function list(filter) {
  const f = filter, all = C.isObj(f) && (f.all || f.kind === 'villager') ? S.roster.people.concat(S.roster.villagers) : S.roster.people;
  if (C.isObj(f) && f.all) return all.slice();
  return C.filterPeople(all, f);
}

// ------------------------------------------------------------------------------------------------ the owner's own character
function me() {
  const v = store.get(ME_KEY), ok = C.isObj(v);
  const p = { id: 'me', name: ok && typeof v.name === 'string' && v.name.trim() ? C.clean(v.name, 24) : 'You', title: 'The owner', kind: 'owner', area: '', app: '', seed: C.seedOf('me'), temperament: 'calm', voice: { pitch: 1, rate: 1 }, sources: [], home: { scene: '', place: '' }, bio: '', aliases: [], made: ok, look: ok && C.isObj(v.look) ? v.look : null };
  p.spec = C.spec(p, p.look);
  return p;
}
function setMe(v) {
  const look = C.isObj(v) && C.isObj(v.look) ? v.look : {}, keep = {};
  for (const k of ['skin', 'hair', 'hairStyle', 'outfit', 'accent', 'build', 'accessory']) if (typeof look[k] === 'string' && look[k].length < 20) keep[k] = look[k];
  if (C.num(look.height) != null) keep.height = Math.max(0.85, Math.min(1.15, look.height));
  if (C.isObj(look.face)) { keep.face = {}; for (const k of ['eyes', 'brows', 'mouth', 'beard']) if (typeof look.face[k] === 'string' && look.face[k].length < 20) keep.face[k] = look.face[k]; for (const k of ['glasses', 'freckles']) if (typeof look.face[k] === 'boolean') keep.face[k] = look.face[k]; }
  store.set(ME_KEY, { v: 1, name: C.clean(C.isObj(v) ? v.name : '', 24), look: keep, t: new Date().toISOString() });
  fire('olympus:people:me', { me: me() });
  return me();
}

// ------------------------------------------------------------------------------------------------ the look
function specOf(id, over) {
  if (C.isObj(id) && id.hairStyle && id.skin) return id;
  const p = get(id);
  if (!p) return C.spec({ id: String(id || 'someone') }, over);
  const f = S.facts.get(p.id);
  return C.spec(p, { ...(p.look || {}), ...(f ? { mood: f.f.mood } : {}), ...(over || {}) });
}
/** a round avatar (head and shoulders) as an SVG element; the same character as the 3D figure. opts: { mood, blink, talk, ring, label } */
function portrait(id, size, opts) {
  const o = opts || {}, p = C.isObj(id) && id.hairStyle ? null : get(id), sp = specOf(id), f = p ? S.facts.get(p.id) : null;
  const tree = C.portraitTree(sp, { size: size || 44, mood: o.mood || sp.mood, blink: o.blink, talk: o.talk, ring: o.ring || (f ? C.STATUS_COLOUR[f.f.status] : '#9c6b3c'), label: o.label || (p ? p.name : 'portrait'), uid: o.uid });
  const el = svgNode(tree);
  el.setAttribute('class', 'pp-portrait');
  return el;
}
/** the same avatar as SVG text (for a canvas texture in a 3D scene) */
function portraitText(id, size, opts) { const sp = specOf(id); return C.svgText(C.portraitTree(sp, { size: size || 128, mood: (opts && opts.mood) || sp.mood, ...(opts || {}) })); }

// ------------------------------------------------------------------------------------------------ facts
async function facts(id, opts) {
  await ready();
  const p = get(id), o = opts || {};
  if (!p || p.id === 'me') return { status: 'idle', doing: '', last: [], learned: [], numbers: [], asof: null, sample: false, sources: [], mood: 'calm', metrics: {} };
  let f = C.buildFacts(p, await D.inputs(p), Date.now());
  const extra = o.facts || S.provided.get(p.id);
  if (extra) f = C.mergeSceneFacts(f, extra);
  S.facts.set(p.id, { t: Date.now(), f });
  return f;
}
/** what is known without waiting (the last facts, or facts from whatever is already loaded) */
function factsNow(id) {
  const p = get(id); if (!p) return null;
  const hit = S.facts.get(p.id); if (hit) return hit.f;
  let f = C.buildFacts(p, D.peek(p), Date.now()); const extra = S.provided.get(p.id); if (extra) f = C.mergeSceneFacts(f, extra);
  return f;
}
/** a scene may add what it knows about its own person (a polis keeper, a tent): { doing, last, learned, numbers, blocked, status, source } */
function provide(id, extra) { const p = get(id); if (p && C.isObj(extra)) { S.provided.set(p.id, extra); S.facts.delete(p.id); } }
/** load everyone's files in the background so stand-ups and moods are ready */
function warm(ids) { return ready().then(() => Promise.all((ids ? ids.map(get).filter(Boolean) : S.roster.people).map((p) => facts(p.id).catch(() => null)))); }

// ------------------------------------------------------------------------------------------------ talking
function memOf(id) { let m = S.mem.get(id); if (!m) { const kept = store.get(MEM_KEY); m = { cur: {}, prevQ: C.isObj(kept) && C.isObj(kept[id]) ? C.clean(kept[id].q, 120) : '' }; S.mem.set(id, m); } return m; }
function keepQuestion(id, q) { const kept = store.get(MEM_KEY), o = C.isObj(kept) ? kept : {}; o[id] = { q: C.clean(q, 120), t: Date.now() }; const ids = Object.keys(o).sort((a, b) => (o[b].t || 0) - (o[a].t || 0)).slice(0, 60), out = {}; for (const k of ids) out[k] = o[k]; store.set(MEM_KEY, out); }
const env = (ctx) => ({ now: Date.now(), hour: new Date().getHours(), roster: S.roster.people, ownerName: me().made ? me().name : '', ...(ctx || {}) });
async function ask(id, text, ctx) {
  await ready();
  const p = get(id), c = ctx || {};
  if (!p || p.id === 'me') return { text: 'I don\'t know who that is.', sources: [], actions: [], followups: [], intent: 'fallback', via: 'offline' };
  const f = c.factsObj || await facts(p.id, c.facts ? { facts: c.facts } : null), mem = c.mem || memOf(p.id);
  const a = T.answer(p, f, text, mem, env(c.env));
  if (!c.mem) S.mem.set(p.id, a.mem);
  a.via = 'offline';
  if (a.open && !c.noModel) {
    const conn = connection();
    if (conn) {
      const reply = await askModel(T.brainContext(p, f), c.turns || [], text, { connection: conn });
      if (reply && !T.ungrounded(reply, T.corpus(p, f, [text])).length) { a.text = reply; a.via = 'model'; a.intent = 'model'; a.sources = C.arr(f.sources).slice(0, 2).concat(['your own model (' + conn.name + '), from my facts']); }
    }
  }
  if (!c.mem && !c.silent) keepQuestion(p.id, text);
  delete a.mem;
  return a;
}
function standupFrom(rows) { return T.standup(rows); }
/** one line per person, from what is already loaded (call ready() and warm() first, or use standupAsync) */
function standup(ids) { const ps = (ids ? ids.map(get).filter(Boolean) : S.roster.people); return ps.map((p) => ({ id: p.id, line: T.standupLine(p, factsNow(p.id)) })); }
async function standupAsync(ids) { await ready(); const ps = (ids ? ids.map(get).filter(Boolean) : S.roster.people), rows = []; for (const p of ps) rows.push({ person: p, facts: await facts(p.id) }); return standupFrom(rows); }
async function roundTable(question, ids) { await ready(); const ps = (ids ? ids.map(get).filter(Boolean) : S.roster.people), rows = []; for (const p of ps) rows.push({ person: p, facts: await facts(p.id) }); return T.roundTable(question, rows, env()); }
async function debate(idA, idB, topic) { await ready(); const a = get(idA), b = get(idB); if (!a || !b) return null; return T.debate(a, await facts(a.id), b, await facts(b.id), topic, env()); }

// ------------------------------------------------------------------------------------------------ requests (notes on this phone only)
function requests() { const v = store.get(REQ_KEY); return C.arr(v).filter((r) => C.isObj(r) && typeof r.id === 'string' && typeof r.text === 'string').map((r) => ({ rid: String(r.rid || r.time || ''), id: r.id, name: C.clean(r.name || '', 40), text: C.clean(r.text, 600), time: String(r.time || '') })); }
function request(id, text) {
  const p = get(id), t = C.clean(text, 600);
  if (!p || !t) return null;
  const row = { rid: Date.now().toString(36) + Math.floor(Math.random() * 1e6).toString(36), id: p.id, name: p.name, text: t, time: new Date().toISOString() };
  const all = requests().concat([row]).slice(-200);
  if (!store.set(REQ_KEY, all)) return null;
  fire('olympus:people:request', { id: p.id, text: t, time: row.time, rid: row.rid });
  return row;
}
function removeRequest(rid) { const all = requests().filter((r) => r.rid !== rid); store.set(REQ_KEY, all); fire('olympus:people:request', { removed: rid }); return all; }
function clearRequests() { store.set(REQ_KEY, []); fire('olympus:people:request', { cleared: true }); }
/** one text block the owner can paste to Claude, grouped per person */
function exportRequests() {
  const all = requests();
  if (!all.length) return 'Request box: empty.';
  const by = new Map();
  for (const r of all) { if (!by.has(r.id)) by.set(r.id, []); by.get(r.id).push(r); }
  const lines = ['Requests from the owner (OLYMPUS request box), copied ' + new Date().toISOString().slice(0, 10) + '. Each note was left for one worker; please act on them.'];
  for (const [id, rows] of by) {
    const p = get(id);
    lines.push('', 'For ' + (p ? p.name + ' (' + id + ', ' + p.title + ')' : id) + ':');
    for (const r of rows) lines.push('- [' + r.time.slice(0, 16).replace('T', ' ') + '] ' + r.text);
  }
  return lines.join('\n');
}

// ------------------------------------------------------------------------------------------------ voice
const speakOn = () => { try { return localStorage.getItem(SPEAK_KEY) === '1'; } catch (_) { return false; } };
function speak(id, text) {
  const p = get(id), t = String(text || '').replace(/\[[^\]]*\]/g, '').slice(0, 500);
  if (!t) return false;
  try {
    const jv = window.JARVIS_VOICE || (window.JARVIS && window.JARVIS.voice);
    if (jv && typeof jv.speak === 'function') { jv.speak(t); return true; }
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance !== 'function') return false;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(t);
    u.pitch = p && p.voice ? Math.max(0.5, Math.min(1.6, p.voice.pitch)) : 1; u.rate = p && p.voice ? Math.max(0.8, Math.min(1.2, p.voice.rate)) : 1; u.lang = 'en-US';
    window.speechSynthesis.speak(u);
    return true;
  } catch (_) { return false; }
}
function hush() { try { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); } catch (_) { /* nothing */ } }

// ------------------------------------------------------------------------------------------------ the chat sheet
function ensureCss() {
  if (document.querySelector('link[data-pp-css]')) return;
  const l = document.createElement('link'); l.rel = 'stylesheet'; l.setAttribute('data-pp-css', '1');
  try { l.href = new URL('./people.css?v=p1', import.meta.url).href; } catch (_) { l.href = '../olympus/people.css?v=p1'; }
  document.head.appendChild(l);
}
function buildSheet() {
  ensureCss();
  const root = h('div', 'pp-root'); root.hidden = true;
  const back = h('div', 'pp-back');
  const sheet = h('section', 'pp-sheet'); sheet.setAttribute('role', 'dialog'); sheet.setAttribute('aria-modal', 'true'); sheet.setAttribute('aria-labelledby', 'ppName'); sheet.tabIndex = -1;
  const head = h('header', 'pp-head'), face = h('div', 'pp-face'), who = h('div', 'pp-who');
  const name = h('h2', 'pp-name'); name.id = 'ppName';
  const title = h('p', 'pp-title'), status = h('p', 'pp-status'), dot = h('span', 'pp-dot'), stText = h('span', 'pp-sttext');
  status.append(dot, stText); who.append(name, title, status);
  const close = h('button', 'pp-close', '×'); close.type = 'button'; close.setAttribute('aria-label', 'Close the conversation');
  head.append(face, who, close);
  const log = h('div', 'pp-log'); log.setAttribute('role', 'log'); log.setAttribute('aria-live', 'polite'); log.setAttribute('aria-label', 'Conversation'); log.tabIndex = 0;
  const chips = h('div', 'pp-chips'); chips.setAttribute('aria-label', 'Suggested questions');
  const req = h('form', 'pp-req'); req.hidden = true;
  const reqLab = h('label', 'pp-reqlab'); reqLab.htmlFor = 'ppReqText';
  const reqText = h('textarea', 'pp-reqtext'); reqText.id = 'ppReqText'; reqText.rows = 3; reqText.maxLength = 600;
  const reqRow = h('div', 'pp-reqrow'), reqSave = h('button', 'pp-btn pp-primary', 'Save the request'), reqCancel = h('button', 'pp-btn', 'Cancel');
  reqSave.type = 'submit'; reqCancel.type = 'button'; reqRow.append(reqSave, reqCancel);
  const reqNote = h('p', 'pp-fine', 'Saved on this phone only. Nothing is sent. Copy it to Claude from the Request box in Symposium.');
  req.append(reqLab, reqText, reqRow, reqNote);
  const tools = h('div', 'pp-tools');
  const bWork = h('button', 'pp-btn', 'Open their work'), bReq = h('button', 'pp-btn', 'Leave a request'), bShare = h('button', 'pp-btn', 'Share'), bVoice = h('button', 'pp-btn', 'Voice: off');
  for (const b of [bWork, bReq, bShare, bVoice]) b.type = 'button';
  bVoice.setAttribute('aria-pressed', 'false');
  tools.append(bWork, bReq, bShare, bVoice);
  const form = h('form', 'pp-form');
  const input = h('input', 'pp-in'); input.type = 'text'; input.autocomplete = 'off'; input.maxLength = 300; input.setAttribute('enterkeyhint', 'send'); input.setAttribute('aria-label', 'Your question');
  const mic = h('button', 'pp-mic'); mic.type = 'button'; mic.setAttribute('aria-label', 'Speak your question'); mic.setAttribute('aria-pressed', 'false'); mic.appendChild(micIcon());
  const send = h('button', 'pp-send', 'Ask'); send.type = 'submit';
  form.append(input, mic, send);
  const toast = h('p', 'pp-toast'); toast.setAttribute('role', 'status'); toast.setAttribute('aria-live', 'polite');
  sheet.append(head, log, chips, req, tools, toast, form);
  root.append(back, sheet);
  document.body.appendChild(root);
  const U = { root, back, sheet, face, name, title, dot, stText, close, log, chips, req, reqLab, reqText, reqCancel, tools, bWork, bReq, bShare, bVoice, form, input, mic, send, toast };
  back.addEventListener('click', closeSheet); close.addEventListener('click', closeSheet);
  root.addEventListener('keydown', (e) => { if (e.key === 'Tab') trap(e, sheet); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !root.hidden) { e.stopPropagation(); closeSheet(); } }, true);
  form.addEventListener('submit', (e) => { e.preventDefault(); const v = input.value.trim(); if (v) { input.value = ''; sendText(v); } });
  bReq.addEventListener('click', () => showReq(true)); reqCancel.addEventListener('click', () => showReq(false));
  req.addEventListener('submit', (e) => { e.preventDefault(); const v = reqText.value.trim(); if (!v || !S.cur) return; const row = request(S.cur.id, v); reqText.value = ''; showReq(false); addBubble('me', 'Request: ' + v); addBubble('them', row ? 'Noted. It is in your request box; nothing was sent anywhere.' : 'I could not save that on this phone (storage is off).'); });
  bWork.addEventListener('click', () => { if (S.cur && S.cur.app) openWork(S.cur); });
  bShare.addEventListener('click', share);
  bVoice.addEventListener('click', () => { const on = !speakOn(); try { localStorage.setItem(SPEAK_KEY, on ? '1' : '0'); } catch (_) { /* not kept */ } if (!on) hush(); paintVoice(); if (on && S.cur) speak(S.cur.id, 'Voice is on.'); });
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) mic.hidden = true;
  else mic.addEventListener('click', () => listen(SR));
  const vv = window.visualViewport;
  if (vv) { const fit = () => { if (root.hidden) return; root.style.height = Math.round(vv.height) + 'px'; root.style.top = Math.round(vv.offsetTop) + 'px'; log.scrollTop = log.scrollHeight; }; vv.addEventListener('resize', fit); vv.addEventListener('scroll', fit); U.fit = fit; }
  return U;
}
function micIcon() { const s = document.createElementNS(NS, 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('width', '22'); s.setAttribute('height', '22'); s.setAttribute('aria-hidden', 'true'); for (const [tag, at] of [['rect', { x: 9, y: 3, width: 6, height: 11, rx: 3, fill: 'currentColor' }], ['path', { d: 'M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }]]) { const e = document.createElementNS(NS, tag); for (const k in at) e.setAttribute(k, at[k]); s.appendChild(e); } return s; }
function trap(e, box) { const f = Array.from(box.querySelectorAll('button, input, textarea, [tabindex="0"]')).filter((x) => !x.hidden && x.offsetParent !== null); if (!f.length) return; const a = f[0], z = f[f.length - 1]; if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); } }
function paintVoice() { const U = S.sheet, on = speakOn(); U.bVoice.textContent = 'Voice: ' + (on ? 'on' : 'off'); U.bVoice.setAttribute('aria-pressed', on ? 'true' : 'false'); }
function showReq(on) { const U = S.sheet; U.req.hidden = !on; U.tools.hidden = on; U.form.hidden = on; U.chips.hidden = on; if (on) { U.reqLab.textContent = 'A note for ' + S.cur.name + ' (Claude will read it for them)'; U.reqText.focus(); } else if (!U.root.hidden && !U.root.contains(document.activeElement)) { try { U.sheet.focus({ preventScroll: true }); } catch (_) { /* fine */ } } U.log.scrollTop = U.log.scrollHeight; }
function toast(t) { const U = S.sheet; U.toast.textContent = t; clearTimeout(S.toastT); S.toastT = setTimeout(() => { U.toast.textContent = ''; }, 2600); }
function openWork(p) { const url = '../' + p.app + '/'; fire('olympus:people:work', { id: p.id, app: p.app }); try { if (window.OLYMPUS && typeof window.OLYMPUS.go === 'function') { window.OLYMPUS.go(url); return; } } catch (_) { /* plain link */ } location.href = url; }
function paintHead(extra) {
  const U = S.sheet, p = S.cur, f = S.curFacts;
  clear(U.face); U.face.appendChild(portrait(p.id, 64, { ...(extra || {}), uid: 'h' }));
  U.name.textContent = p.name; U.title.textContent = p.title;
  U.dot.style.background = C.STATUS_COLOUR[f.status] || C.STATUS_COLOUR.stale;
  U.stText.textContent = C.STATUS_WORD[f.status] + (f.sample ? ' (not real)' : '') + ' · ' + f.mood;
}
function addBubble(who, text, meta) {
  const U = S.sheet, row = h('div', 'pp-row pp-' + who);
  if (who === 'them') { const a = h('span', 'pp-ava'); a.appendChild(portrait(S.cur.id, 32, { uid: 'b' + S.log.length })); row.appendChild(a); }
  const b = h('div', 'pp-bub'); b.appendChild(h('p', 'pp-text', text));
  if (meta && meta.sources && meta.sources.length) b.appendChild(h('p', 'pp-src', 'From: ' + meta.sources.join(', ')));
  if (meta && meta.actions) for (const a of meta.actions) { const btn = h('button', 'pp-btn pp-act', a.label); btn.type = 'button'; btn.addEventListener('click', () => { if (a.request) showReq(true); else if (a.open) { fire('olympus:people:work', { id: S.cur.id, open: a.open }); location.href = a.open; } }); b.appendChild(btn); }
  row.appendChild(b);
  if (who === 'me') { const a = h('span', 'pp-ava'); a.appendChild(portrait('me', 32, { uid: 'm' + S.log.length })); row.appendChild(a); }
  U.log.appendChild(row); U.log.scrollTop = U.log.scrollHeight;
  if (text) S.log.push({ who, text, sources: meta && meta.sources ? meta.sources : [] });
  return row;
}
function setChips(items) {
  const U = S.sheet; clear(U.chips);
  for (const q of items.slice(0, 4)) { const b = h('button', 'pp-chip', q); b.type = 'button'; b.addEventListener('click', () => { if (q === 'Leave a request') showReq(true); else sendText(q); }); U.chips.appendChild(b); }
}
async function sendText(text) {
  if (S.busy || !S.cur) return;
  S.busy = true;
  const U = S.sheet, p = S.cur, t0 = Date.now();
  addBubble('me', text);
  const typing = h('div', 'pp-row pp-them pp-typing'); const av = h('span', 'pp-ava'); av.appendChild(portrait(p.id, 32, { talk: true, uid: 't' })); const tb = h('div', 'pp-bub'); tb.setAttribute('aria-label', p.name + ' is thinking'); for (let i = 0; i < 3; i++) tb.appendChild(h('i', 'pp-tdot')); typing.append(av, tb);
  U.log.appendChild(typing); U.log.scrollTop = U.log.scrollHeight;
  let a;
  try { a = await ask(p.id, text, { turns: S.log.slice(-7, -1).map((m) => ({ role: m.who === 'me' ? 'user' : 'assistant', content: m.text })), facts: S.curExtra }); } catch (_) { a = { text: 'I don\'t have that.', sources: [], actions: [], followups: ['What are you doing?'] }; }
  const wait = reduced() ? 0 : Math.max(0, Math.min(450, 180 + a.text.length * 2) - (Date.now() - t0));
  if (wait) await new Promise((ok) => setTimeout(ok, wait));
  if (typing.parentNode) typing.parentNode.removeChild(typing);
  if (S.cur !== p) { S.busy = false; return; }
  S.curFacts = factsNow(p.id) || S.curFacts; paintHead();
  addBubble('them', a.text, { sources: a.sources, actions: a.actions });
  setChips(a.followups || []);
  if (speakOn()) speak(p.id, a.text);
  S.busy = false;
}
function listen(SR) {
  const U = S.sheet;
  if (S.rec) { try { S.rec.stop(); } catch (_) { /* gone */ } return; }
  try {
    const r = new SR(); r.lang = 'en-US'; r.interimResults = false; r.maxAlternatives = 1; S.rec = r;
    U.mic.setAttribute('aria-pressed', 'true'); U.mic.classList.add('on'); toast('Listening...');
    r.onresult = (e) => { const t = e.results && e.results[0] && e.results[0][0] ? String(e.results[0][0].transcript || '').trim() : ''; if (t) sendText(t); };
    r.onerror = () => toast('I could not hear that. Type it instead.');
    r.onend = () => { S.rec = null; U.mic.setAttribute('aria-pressed', 'false'); U.mic.classList.remove('on'); };
    r.start();
  } catch (_) { S.rec = null; toast('The microphone is not available here.'); }
}
function transcript() {
  const p = S.cur; if (!p) return '';
  const lines = ['Talk with ' + p.name + ' (' + p.title + '), ' + new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC'];
  for (const m of S.log) { lines.push((m.who === 'me' ? 'Me: ' : p.name + ': ') + m.text); if (m.sources && m.sources.length) lines.push('   (from: ' + m.sources.join(', ') + ')'); }
  if (S.curFacts && S.curFacts.sample) lines.push('Note: sample data, not real numbers.');
  return lines.join('\n');
}
async function share() {
  const text = transcript();
  try { if (navigator.share) { await navigator.share({ title: 'Talk with ' + S.cur.name, text }); return; } } catch (e) { if (e && e.name === 'AbortError') return; }
  try { await navigator.clipboard.writeText(text); toast('Copied the conversation as text.'); return; } catch (_) { /* no clipboard */ }
  const U = S.sheet, ta = h('textarea', 'pp-reqtext'); ta.value = text; ta.readOnly = true; ta.rows = 6; ta.setAttribute('aria-label', 'The conversation as text'); U.log.appendChild(ta); ta.focus(); ta.select(); toast('Select and copy the text.');
}
/** open the chat with a person. opts: { anchor (element to return focus to), facts (what the scene knows), question (ask it right away), request (open the note box) } */
async function open(id, opts) {
  const o = opts || {};
  await ready();
  const p = get(id);
  if (!p || p.id === 'me') return false;
  if (!S.sheet) S.sheet = buildSheet();
  const U = S.sheet;
  if (o.facts) provide(p.id, o.facts);
  S.cur = p; S.curExtra = o.facts || null; S.log = []; S.busy = false; S.anchor = o.anchor && o.anchor.focus ? o.anchor : document.activeElement;
  S.curFacts = factsNow(p.id);
  clear(U.log); clear(U.chips); showReq(false);
  U.bWork.hidden = !p.app; paintVoice(); paintHead();
  U.root.hidden = false; document.documentElement.classList.add('pp-open');
  if (U.fit) U.fit();
  U.input.placeholder = 'Ask ' + p.name + '...';
  try { U.sheet.focus({ preventScroll: true }); } catch (_) { U.sheet.focus(); }
  fire('olympus:people:open', { id: p.id });
  const f = await facts(p.id, o.facts ? { facts: o.facts } : null);
  if (S.cur !== p) return true;
  S.curFacts = f; paintHead();
  const mem = memOf(p.id);
  addBubble('them', T.greeting(p, f, { lastQ: mem.prevQ }, env()), { sources: f.sources.slice(0, 2) });
  setChips((START[p.kind] || START.keeper));
  if (connection()) toast('Open questions can go to your own model (' + connection().name + ').');
  clearInterval(S.blinkT);
  if (!reduced()) S.blinkT = setInterval(() => { if (!S.cur || U.root.hidden || document.hidden) return; paintHead({ blink: true }); setTimeout(() => { if (S.cur && !U.root.hidden) paintHead(); }, 130); }, 4200);
  if (o.request) showReq(true);
  else if (o.question) sendText(String(o.question));
  return true;
}
const START = { scanner: ['What did you find?', 'What is your top pick?', 'How sure are you?', 'Are you stuck?'], bot: ['How did today go?', 'How much drawdown is left?', 'What did you learn?', 'Are you stuck?'], mind: ['What are you doing?', 'What did you find?', 'What did you learn?', 'Are you stuck?'],
  builder: ['What are you doing?', 'What was your last commit?', 'Are you stuck?', 'What do you need from me?'], keeper: ['What are you doing?', 'Which ones need a look?', 'Good news first', 'Give me a number'], champion: ['What did you find?', 'How did the earlier years go?', 'Why were you adopted or rejected?', 'How sure are you?'], villager: ['What are you doing?', 'Give me a number', 'Are you stuck?', 'What should I ask you?'] };
function closeSheet() {
  const U = S.sheet; if (!U || U.root.hidden) return;
  const id = S.cur ? S.cur.id : null;
  U.root.hidden = true; document.documentElement.classList.remove('pp-open'); U.root.style.height = ''; U.root.style.top = '';
  clearInterval(S.blinkT); hush(); if (S.rec) { try { S.rec.abort(); } catch (_) { /* gone */ } S.rec = null; }
  S.cur = null;
  try { if (S.anchor && S.anchor.focus && document.contains(S.anchor)) S.anchor.focus({ preventScroll: true }); } catch (_) { /* nothing */ }
  fire('olympus:people:close', { id });
}

const API = { v: 1, ready, list, get, portrait, portraitText, spec: specOf, facts, factsNow, provide, warm, ask, open, close: closeSheet, isOpen: () => !!(S.sheet && !S.sheet.root.hidden), standup, standupAsync, roundTable, debate,
  request, requests, removeRequest, clearRequests, exportRequests, speak, me, setMe, transcript, connected: () => { const c = connection(); return c ? { provider: c.provider, name: c.name } : null; },
  roster: () => S.roster, core: C, talk: T };
if (typeof window !== 'undefined') { window.OLYMPUS_PEOPLE = API; ready().then(() => fire('olympus:people:ready', { n: S.roster.people.length })); }
export default API;
export { ready, list, get, portrait, portraitText, specOf as spec, facts, factsNow, provide, warm, ask, open, closeSheet as close, standup, standupAsync, roundTable, debate, request, requests, removeRequest, clearRequests, exportRequests, speak, me, setMe };
