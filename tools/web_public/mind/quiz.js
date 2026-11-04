// OLYMPUS Mind: review mode, spaced repetition from the notes. Pure functions: no DOM, no storage, no network.
//   buildDeck(g, now)              -> [{id, kind, prompt, choices[4], answer, note, why, rank}] questions made from the notes:
//                                     fill the gap in a lesson / memory / note line, which galaxy a note lives in, which note it links to,
//                                     which tag it has, the biggest hub; plus a few starters about Mind itself (rank 2) so the deck is never empty
//   pickSession(deck, state, now, n) -> up to n questions: overdue first, then new ones, starters last, then "practice anyway"
//   grade(state, id, ok, now)      -> a new state with the card moved up a box (due later) or back to box 0
//   dueCount(deck, state, now)     -> how many questions are due or new
//   boxes(state)                   -> [count per box] for the Review page
// state = {cards: {id: {b: box 0..5, d: due ms}}, days: ['YYYY-MM-DD', ...]} (kept by the page under 'mind.review')
import { dayKey } from './dom.js';
import { hubs, tagCloud } from './insights.js';

const INTERVALS = [0, 1, 3, 7, 16, 35];                          // days until a card is due again, by box
const DAY = 864e5, MAX_CARDS = 600;
const NOISE = new Set('about their there which would could should these those where being after before every still other while again because really something someone always never today tomorrow yesterday going those'.split(' '));

function hash(s) {
  let h = 2166136261;
  for (let k = 0; k < s.length; k++) h = Math.imul(h ^ s.charCodeAt(k), 16777619);
  return h >>> 0;
}
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function shuffled(list, seed) {
  const r = rng(seed), a = list.slice();
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
/** The four choices in a stable, shuffled order and where the right one landed. */
function ask(id, kind, prompt, right, wrong, extra = {}) {
  const pool = [...new Set(wrong)].filter((w) => w && w !== right).slice(0, 3);
  if (pool.length < 3) return null;
  const choices = shuffled([right, ...pool], hash(id));
  return { id, kind, prompt, choices, answer: choices.indexOf(right), note: null, why: '', rank: 1, ...extra };
}

const words = (s) => s.split(/\s+/).map((w) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')).filter(Boolean);
function keyword(sentence) {
  const w = words(sentence);
  let best = null;
  w.forEach((x, k) => {
    if (k === 0 || NOISE.has(x.toLowerCase())) return;
    const ok = /^\d{2,}/.test(x) || (/^\p{L}+$/u.test(x) && x.length >= 5);
    if (ok && (!best || x.length > best.length)) best = x;
  });
  return best;
}

function sentencesOf(text) {
  return String(text || '').split(/\n+/).flatMap((l) => l.replace(/^\s*(#{1,6}|[-*+>]|\d+\.)\s+/, '').replace(/\[[ xX]\]\s*/, '').replace(/\[\[([^\]|]+\|)?([^\]]+)\]\]/g, '$2').replace(/[*_`=]+/g, '').split(/(?:[.!?])\s+/))
    .map((s) => s.trim()).filter((s) => words(s).length >= 5 && words(s).length <= 22 && s.length <= 160);
}

const STARTERS = [
  ['s:dot', 'In your brain, what does a bigger, brighter dot mean?', 'A note with more links and more words', ['A note you deleted', 'A private note', 'An error'], 'Size follows links and words.'],
  ['s:teach', 'How do you teach Jarvis something new here?', 'Open Teach and save a line', ['Delete a note', 'Change the theme', 'Turn the sound off'], 'Teach writes into the same place Jarvis reads.'],
  ['s:orphan', 'What is an orphan note?', 'A note with no links in or out', ['A note with a long title', 'A note from last year', 'A note with many tags'], 'Link an orphan to something and it joins the brain.'],
  ['s:hub', 'What is a hub?', 'A note that many other notes link to', ['A note with the most words', 'Your newest note', 'A note with no tags'], 'Hubs are the big stars everything orbits.'],
  ['s:focus', 'What does focus mode do?', 'Lights one galaxy and dims the rest', ['Deletes the other galaxies', 'Locks the camera', 'Mutes Jarvis'], 'Tap a galaxy chip to focus it, tap again to leave.'],
  ['s:streak', 'What keeps your streak alive?', 'Learning or writing something every day', ['Opening the page', 'Switching the theme', 'Zooming in'], 'Even one line a day counts.'],
];

export function buildDeck(g, now = Date.now()) {
  const deck = [];
  // fill the gap: lessons, Jarvis's memories and the first lines of notes
  const lines = [];
  for (const l of g.learned) for (const s of sentencesOf(l.text)) lines.push({ s, note: l.i >= 0 ? g.nodes[l.i].id : null, from: 'a lesson' });
  for (const n of g.nodes) if (n.snippet && n.kind !== 'daily') for (const s of sentencesOf(n.snippet).slice(0, 2)) lines.push({ s, note: n.id, from: n.title });
  const seen = new Set(), kw = [];
  const usable = lines.filter((x) => { const k = x.s.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; }).slice(-80);
  for (const x of usable) { x.k = keyword(x.s); if (x.k) kw.push(x.k); }
  for (const x of usable) {
    if (!x.k) continue;
    const gap = x.s.replace(x.k, '▁▁▁');
    const sameKind = (w) => (/^\d/.test(w) === /^\d/.test(x.k)) && w.toLowerCase() !== x.k.toLowerCase();
    const wrong = shuffled(kw.filter(sameKind), hash('w' + x.s)).slice(0, 3);
    const q = ask('c:' + hash(x.s).toString(36), 'gap', `Fill the gap: “${gap}”`, x.k, wrong, { note: x.note, why: `From ${x.from}: ${x.s}` });
    if (q) deck.push(q);
  }
  // structure: galaxies, links, tags, the biggest hub
  const live = g.clusters.filter((c) => c.count && c.key !== 'me');
  const real = g.nodes.filter((n) => n.kind === 'note' || n.kind === 'daily' || n.kind === 'inbox');
  if (live.length >= 4) {
    for (const n of shuffled(real.filter((x) => x.degree >= 1), hash('g' + g.sig)).slice(0, 6)) {
      const c = g.clusters[n.cluster], q = ask('g:' + n.id, 'galaxy', `Which galaxy is “${n.title}” in?`, c.label, live.map((k) => k.label), { note: n.id, why: `${n.title} lives in ${c.label}.` });
      if (q) deck.push(q);
    }
  }
  for (const n of shuffled(real.filter((x) => x.out.length), hash('l' + g.sig)).slice(0, 6)) {
    const tgt = g.nodes[n.out[0]], not = real.filter((x) => x.i !== n.i && !n.out.includes(x.i) && !x.out.includes(n.i));
    const q = ask('l:' + n.id + '>' + tgt.id, 'link', `Which note does “${n.title}” link to?`, tgt.title, shuffled(not, hash('lw' + n.id)).slice(0, 3).map((x) => x.title), { note: n.id, why: `${n.title} links to ${tgt.title}.` });
    if (q) deck.push(q);
  }
  const cloud = tagCloud(g, 40).map((t) => t.tag);
  for (const n of shuffled(real.filter((x) => x.tags.length), hash('t' + g.sig)).slice(0, 5)) {
    const q = ask('t:' + n.id, 'tag', `Which tag belongs to “${n.title}”?`, '#' + n.tags[0], cloud.filter((t) => !n.tags.includes(t)).map((t) => '#' + t).sort((a, b) => hash(a + n.id) - hash(b + n.id)), { note: n.id, why: `${n.title} is tagged #${n.tags.join(' #')}.` });
    if (q) deck.push(q);
  }
  const top = hubs(g, 1)[0];
  if (top) {
    const lower = real.filter((x) => x.degree < top.degree).sort((a, b) => hash(a.id) - hash(b.id)).slice(0, 3).map((x) => x.title);
    const q = ask('h:' + top.id, 'hub', 'Which of these is your biggest hub?', top.title, lower, { note: top.id, why: `${top.title} has ${top.degree} links.` });
    if (q) deck.push(q);
  }
  for (const [id, prompt, right, wrong, why] of STARTERS) deck.push(ask(id, 'starter', prompt, right, wrong, { why, rank: 2 }));
  return deck.filter(Boolean);
}

export function pickSession(deck, state, now = Date.now(), n = 5) {
  const cards = (state && state.cards) || {};
  const score = (q) => {
    const c = cards[q.id];
    if (c && c.d <= now) return [0, c.d];                         // seen and due: the oldest first
    if (!c) return [q.rank, hash(q.id + dayKey(now))];             // new: a mix that changes each day
    return [9, c.d];                                               // not due yet: practice anyway
  };
  return deck.slice().sort((a, b) => { const x = score(a), y = score(b); return x[0] - y[0] || x[1] - y[1]; }).slice(0, n);
}

export function grade(state, id, ok, now = Date.now()) {
  const cards = { ...((state && state.cards) || {}) }, old = cards[id] || { b: 0, d: 0 };
  const b = ok ? Math.min(INTERVALS.length - 1, old.b + 1) : 0;
  cards[id] = { b, d: ok ? now + INTERVALS[b] * DAY : now };
  const keys = Object.keys(cards);
  if (keys.length > MAX_CARDS) for (const k of keys.sort((a, c) => cards[a].d - cards[c].d).slice(0, keys.length - MAX_CARDS)) delete cards[k];
  const today = dayKey(now), days = ((state && state.days) || []).filter((d) => d !== today);
  return { cards, days: [...days, today].slice(-60) };
}

export function dueCount(deck, state, now = Date.now()) {
  const cards = (state && state.cards) || {};
  return deck.filter((q) => !cards[q.id] || cards[q.id].d <= now).length;
}

export function boxes(state) {
  const out = new Array(INTERVALS.length).fill(0);
  for (const c of Object.values((state && state.cards) || {})) out[Math.min(out.length - 1, Math.max(0, c.b | 0))]++;
  return out;
}
