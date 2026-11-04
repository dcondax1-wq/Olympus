// OLYMPUS Mind: Jarvis learning, live. Jarvis keeps what she learns on this phone (localStorage, the same origin as this page);
// this module only READS three of her keys, never writes, never fetches and never touches the vault token ('jarvis.vault'):
//   jarvis.assistant.v1       { facts: [{id, t, text}], notes: [{id, t, text}], todos }   what you told her / "note: ..."
//   jarvis.vault.learned      [{t (unix s), text, note (path) | null}]                   lessons she saved
//   jarvis.vault.local        [{path, text, t}]                                          notes written / pasted
//   (readLive, internal) -> {items: [{id, kind: 'fact'|'note'|'lesson', t (ms), text, topic}], counts: {memories, written, topics}}
//   withLive(snap, live) -> a snapshot with every live item added as a note (topic tag -> its constellation, else Jarvis memory)
//   watchLive(cb, {storage, every}) -> stop()      cb(live) on a `storage` event from another tab and on a poll (the same tab cannot hear itself)
const POLL_MS = 4000;
const TOPICS = [
  ['trading', /\b(trad\w*|nq|es|mffu|futures?|eval|prop|ifvg|cisd|liquidity|stop|risk|setup|journal|market)\b/i],
  ['goals', /\b(goals?|plan|vision|habit|routine|discipline|mindset)\b/i],
  ['health', /\b(gym|health|fitness|workout|sleep|diet|food|lift|run|leg day)\b/i],
  ['kalshi', /\b(kalshi|polymarket|prediction|bets?)\b/i],
  ['business', /\b(business|money|startup|brand|content|client|olympus|idea|work|project)\b/i],
];
const text = (v, max = 300) => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim().slice(0, max) : '');
const ms = (v) => { const x = Number(v); return Number.isFinite(x) && x > 0 ? (x < 1e11 ? x * 1000 : x) : 0; };
const topicOf = (s) => { for (const [k, rx] of TOPICS) if (rx.test(s)) return k; return ''; };
const store = (s) => { if (s) return s; try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch (_) { return null; } };
let bad = false;                                        // a key that is there but not JSON (half-written): the last good read stays
function get(st, key) {
  try { const v = st && st.getItem(key); return v ? JSON.parse(v) : null; } catch (_) { bad = true; return null; }
}
const arr = (v) => (Array.isArray(v) ? v.filter((x) => x && typeof x === 'object') : []);

function readLive(storage) {
  const st = store(storage), items = [], seen = new Set();
  bad = false;
  const add = (kind, id, t, raw) => {
    const s = text(raw);
    if (!s || seen.has(kind + id)) return;
    seen.add(kind + id);
    items.push({ id: kind + ':' + id, kind, t: ms(t) || 0, text: s, topic: topicOf(s) });
  };
  const A = get(st, 'jarvis.assistant.v1') || {};
  arr(A.facts).forEach((f, i) => add('fact', f.id != null ? f.id : i, f.t, f.text));
  arr(A.notes).forEach((n, i) => add('note', n.id != null ? n.id : i, n.t, n.text));
  const L = arr(get(st, 'jarvis.vault.learned'));
  L.forEach((l) => add('lesson', ms(l.t) + '|' + text(l.text, 40), l.t, l.text));
  const local = arr(get(st, 'jarvis.vault.local'));
  local.forEach((n) => add('note', 'local|' + text(n.path, 120), n.t, String(n.path || '').split('/').pop().replace(/\.md$/i, '') || n.text));
  items.sort((a, b) => a.t - b.t);
  const written = L.filter((l) => l.note).length + local.length;
  const topics = new Set(items.map((x) => x.topic).filter(Boolean));
  return { items, counts: { memories: items.filter((x) => x.kind === 'fact').length, written, topics: topics.size }, sig: items.map((x) => x.id).join('\n'), bad };
}

/** The snapshot plus every live item that the vault does not already show (by title), as notes of the right constellation. */
export function withLive(snap, live) {
  if (!snap || !live || !live.items.length) return snap;
  const have = new Set(snap.notes.map((n) => n.title.toLowerCase())), notes = snap.notes.slice();
  for (const it of live.items) {
    if (it.kind === 'lesson') continue;                         // lessons already arrive through the vault's own `learned` list
    const title = it.text.slice(0, 80);
    if (have.has(title.toLowerCase())) continue;
    notes.push({ id: 'live:' + it.id, path: `Jarvis/${it.kind}/${it.id.slice(it.kind.length + 1)}`, title, tags: it.topic ? [it.topic] : [], links: [],
      mtime: it.t, words: it.text.split(' ').length, kind: it.topic ? 'note' : 'memory', snippet: it.text });
  }
  const known = new Set((snap.learned || []).map((l) => l.t + '|' + l.text));
  const learned = (snap.learned || []).slice();
  for (const it of live.items) {
    if (it.kind !== 'lesson' || known.has(it.t + '|' + it.text)) continue;
    learned.push({ t: it.t, text: it.text, note: null });
  }
  return { ...snap, notes, learned };
}

export function watchLive(cb, { storage, every = POLL_MS } = {}) {
  let last = null, stopped = false;
  const check = () => {
    if (stopped) return;
    const live = readLive(storage);
    if (live.bad) return;
    if (live.sig !== last) { const first = last === null; last = live.sig; cb(live, first); }
  };
  const onStorage = (e) => { if (!e || !e.key || e.key.startsWith('jarvis.')) check(); };
  window.addEventListener('storage', onStorage);
  const timer = setInterval(() => { if (!document.hidden) check(); }, every);
  check();
  return () => { stopped = true; window.removeEventListener('storage', onStorage); clearInterval(timer); };
}
