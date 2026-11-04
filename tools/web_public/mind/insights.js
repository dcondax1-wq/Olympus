// OLYMPUS Mind: what the brain knows about itself. Pure functions over a built graph (graph.js): no DOM, no storage, no network.
//   activity(g)            -> Set of local days (YYYY-MM-DD) on which something was learned or written
//   streak(days, now)      -> {current, best}: days in a row (today may still be empty)
//   growth(g, now, weeks)  -> [{t, total, added}] notes by last edit, cumulative, one point per week
//   weekly(g, now, weeks)  -> {edits[], learned[]} per week, oldest first
//   learnedFeed(g)         -> everything Jarvis learned, newest first: [{t, text, i, src: 'lesson' | 'memory'}]
//   timeline(g, now, days) -> [{key, daily[], edits[], editsMore, learned[]}] newest day first (only days with something)
//   tagCloud(g, limit)     -> [{tag, count, weight 0..1, colour}] alphabetical
//   orphans(g) / hubs(g, n)-> notes with no links at all / the most linked notes
//   ego(g, i, cap)         -> the local map of one note: {centre, ring: [{n, dir: 'out' | 'back' | 'both'}], more, links: [[a, b]]}
//   filterSet(g, mode, min, now) -> Set of node indices a graph filter keeps (null = everything)
//   previewText(node, max) -> a plain one-line preview of a note (never empty)
//   obsidianLink(vault, node) -> obsidian://open?vault=...&file=... (null for notes that only live in Jarvis's memory)
//   brainStats(g, now)     -> the numbers of the Stats page; brainLevel(g) -> {level, name, progress, xp}
//   greeting(now)          -> 'Good morning' / 'Good afternoon' / 'Good evening'
import { dayKey } from './dom.js';

const DAY = 864e5, WEEK = 7 * DAY;
const LEVELS = ['Spark', 'Neuron', 'Synapse', 'Circuit', 'Cortex', 'Mind', 'Oracle', 'Titan'];

function activity(g) {
  const days = new Set();
  for (const l of g.learned) if (l.t) days.add(dayKey(l.t));
  for (const n of g.nodes) if (n.mtime) days.add(dayKey(n.mtime));
  return days;
}

function streak(days, now = Date.now()) {
  let cur = 0, at = now;
  if (!days.has(dayKey(at))) at -= DAY;                       // today may still be empty: the streak is alive until midnight
  while (days.has(dayKey(at))) { cur++; at -= DAY; }
  const sorted = [...days].sort();
  let best = 0, run = 0, prev = null;
  for (const k of sorted) {
    const t = new Date(k + 'T12:00:00').getTime();
    run = prev !== null && Math.round((t - prev) / DAY) === 1 ? run + 1 : 1;
    prev = t;
    best = Math.max(best, run);
  }
  return { current: cur, best: Math.max(best, cur) };
}

function growth(g, now = Date.now(), weeks = 12) {
  const out = [];
  for (let k = 0; k < weeks; k++) {
    const end = now - (weeks - 1 - k) * WEEK;
    let total = 0, added = 0;
    for (const n of g.nodes) {
      if (!n.mtime || n.mtime <= end) total++;                // a note with no date counts from the start
      if (n.mtime && n.mtime <= end && n.mtime > end - WEEK) added++;
    }
    out.push({ t: end, total, added });
  }
  return out;
}

function weekly(g, now = Date.now(), weeks = 8) {
  const edits = new Array(weeks).fill(0), learned = new Array(weeks).fill(0);
  const slot = (t) => { const k = weeks - 1 - Math.floor((now - t) / WEEK); return k >= 0 && k < weeks && t <= now + 60000 ? k : -1; };
  for (const n of g.nodes) if (n.mtime) { const k = slot(n.mtime); if (k >= 0) edits[k]++; }
  for (const l of g.learned) if (l.t) { const k = slot(l.t); if (k >= 0) learned[k]++; }
  return { edits, learned };
}

export function learnedFeed(g) {
  const seen = new Set(), out = [];
  const add = (t, text, i, src) => {
    const key = text.toLowerCase().slice(0, 60);
    if (!text || seen.has(key)) return;
    seen.add(key);
    out.push({ t, text, i, src });
  };
  for (const l of g.learned) add(l.t, l.text, l.i, 'lesson');
  for (const n of g.nodes) if (n.kind === 'memory' || n.id.startsWith('live:')) add(n.mtime, n.snippet || n.title, n.i, 'memory');
  return out.sort((a, b) => b.t - a.t);
}

export function timeline(g, now = Date.now(), days = 21) {
  const from = now - days * DAY, by = new Map();
  const slot = (t) => { const k = dayKey(t); if (!by.has(k)) by.set(k, { key: k, daily: [], edits: [], editsMore: 0, learned: [] }); return by.get(k); };
  for (const n of g.nodes) {
    if (!n.mtime || n.mtime < from || n.mtime > now + DAY || n.kind === 'memory') continue;
    const s = slot(n.mtime);
    if (n.kind === 'daily') s.daily.push(n.i);
    else if (s.edits.length < 5) s.edits.push(n.i);
    else s.editsMore++;
  }
  for (const l of g.learned) if (l.t >= from && l.t <= now + 60000) slot(l.t).learned.push(l);
  return [...by.values()].sort((a, b) => (a.key < b.key ? 1 : -1));
}

export function tagCloud(g, limit = 28) {
  const count = new Map(), where = new Map();
  for (const n of g.nodes) {
    for (const t of n.tags) {
      count.set(t, (count.get(t) || 0) + 1);
      const w = where.get(t) || new Map();
      w.set(n.cluster, (w.get(n.cluster) || 0) + 1);
      where.set(t, w);
    }
  }
  const top = [...count].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, limit);
  if (!top.length) return [];
  const hi = top[0][1], lo = top[top.length - 1][1];
  return top.map(([tag, c]) => {
    const home = [...where.get(tag)].sort((a, b) => b[1] - a[1])[0][0];
    return { tag, count: c, weight: hi === lo ? 0.6 : (c - lo) / (hi - lo), colour: g.clusters[home].colour };
  }).sort((a, b) => (a.tag < b.tag ? -1 : 1));
}

const linked = (n) => n.out.length + n.back;
export const orphans = (g) => g.nodes.filter((n) => !linked(n) && n.kind !== 'me' && n.kind !== 'memory');

export function hubs(g, n = 8) {
  return g.nodes.filter((x) => x.degree >= 3 && x.kind !== 'me').sort((a, b) => b.degree - a.degree || b.words - a.words).slice(0, n);
}

export function ego(g, i, cap = 7) {
  const c = g.nodes[i];
  if (!c) return null;
  const outs = new Set(c.out), backs = new Set(g.nodes.filter((m) => m.out.includes(i)).map((m) => m.i));
  const all = new Set([...outs, ...backs]);
  const order = [...all].map((k) => g.nodes[k]).sort((a, b) => b.degree - a.degree);
  const shown = order.slice(0, cap), keep = new Set(shown.map((n) => n.i));
  const links = [];
  for (const a of shown) for (const b of shown) if (a.i < b.i && (a.out.includes(b.i) || b.out.includes(a.i))) links.push([a.i, b.i]);
  return {
    centre: c, more: Math.max(0, all.size - shown.length), links,
    ring: shown.map((n) => ({ n, dir: outs.has(n.i) && backs.has(n.i) ? 'both' : outs.has(n.i) ? 'out' : 'back' })).filter((r) => keep.has(r.n.i)),
  };
}

export function filterSet(g, mode, min = 0, now = Date.now()) {
  if (mode === 'all' && !min) return null;
  const set = new Set();
  const top = hubs(g, Math.max(3, Math.ceil(g.nodes.length * 0.1))).map((n) => n.i);
  const hubSet = new Set(top);
  const lonely = new Set(orphans(g).map((n) => n.i));
  for (const n of g.nodes) {
    if (min && n.degree < min) continue;
    if (mode === 'linked' && !linked(n)) continue;
    if (mode === 'hubs' && !hubSet.has(n.i)) continue;
    if (mode === 'orphans' && !lonely.has(n.i)) continue;
    if (mode === 'recent' && !(n.mtime && now - n.mtime < WEEK)) continue;
    set.add(n.i);
  }
  return set;
}

/** A plain, never-empty line about a note: its first sentences without markdown, else what it connects to. */
export function previewText(node, max = 150) {
  const raw = String(node.snippet || '');
  const text = raw.split('\n').map((l) => l.replace(/^\s*(#{1,6}|[-*+>]|\d+\.)\s+/, '').replace(/\[[ xX]\]\s*/, '').replace(/\[\[([^\]|]+\|)?([^\]]+)\]\]/g, '$2')
    .replace(/[*_`=]+/g, '').trim()).filter(Boolean).join(' · ').replace(/\s+/g, ' ').trim();
  if (text) return text.length > max ? text.slice(0, max - 1).trimEnd() + '…' : text;
  const parts = [];
  if (node.out.length + node.back) parts.push(`Linked with ${node.out.length + node.back} note${node.out.length + node.back === 1 ? '' : 's'}`);
  if (node.words) parts.push(`${node.words} words`);
  return parts.join(' · ') || 'A fresh note, still empty';
}

export function obsidianLink(vault, node) {
  const name = String(vault || '').trim();
  if (!name || !node || !node.path || node.id.startsWith('live:')) return null;
  return `obsidian://open?vault=${encodeURIComponent(name)}&file=${encodeURIComponent(node.path.replace(/\.md$/i, ''))}`;
}

function brainLevel(g) {
  const links = g.edges.length / 2;
  const xp = g.nodes.length * 3 + links * 2 + g.learned.length * 5 + g.nodes.reduce((a, n) => a + n.words, 0) / 200;
  const level = Math.floor(Math.sqrt(xp / 8)) + 1, lo = (level - 1) ** 2 * 8, hi = level ** 2 * 8;
  return { level, name: LEVELS[Math.min(LEVELS.length - 1, Math.floor((level - 1) / 3))], progress: Math.max(0, Math.min(1, (xp - lo) / (hi - lo))), xp: Math.round(xp) };
}

export function brainStats(g, now = Date.now()) {
  const n = g.nodes.length, links = g.edges.length / 2, words = g.nodes.reduce((a, x) => a + x.words, 0);
  const dated = g.nodes.filter((x) => x.mtime);
  const days = activity(g), s = streak(days, now);
  const lonely = orphans(g), top = hubs(g, 1)[0] || null;
  const longest = g.nodes.slice().sort((a, b) => b.words - a.words)[0] || null;
  const newest = dated.slice().sort((a, b) => b.mtime - a.mtime)[0] || null, oldest = dated.slice().sort((a, b) => a.mtime - b.mtime)[0] || null;
  const perDay = new Map();
  for (const k of days) perDay.set(k, 0);
  for (const l of g.learned) if (l.t) perDay.set(dayKey(l.t), (perDay.get(dayKey(l.t)) || 0) + 1);
  const bestDay = [...perDay].sort((a, b) => b[1] - a[1])[0] || null;
  return {
    notes: n, links, words, avgWords: n ? Math.round(words / n) : 0, avgLinks: n ? Math.round((links * 2 / n) * 10) / 10 : 0,
    orphans: lonely.length, orphanPct: n ? Math.round((lonely.length / n) * 100) : 0, hub: top, longest, newest, oldest,
    streak: s, activeDays: days.size, bestDay: bestDay && bestDay[1] ? { key: bestDay[0], n: bestDay[1] } : null,
    learned: g.learned.length, tags: new Set(g.nodes.flatMap((x) => x.tags)).size,
    galaxies: g.clusters.filter((c) => c.count).slice().sort((a, b) => b.count - a.count),
    weekly: weekly(g, now, 8), growth: growth(g, now, 12), level: brainLevel(g),
    today: g.learned.filter((l) => dayKey(l.t) === dayKey(now)).length,
  };
}

export function greeting(now = Date.now()) {
  const h = new Date(now).getHours();
  return h < 5 ? 'Late night' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}
