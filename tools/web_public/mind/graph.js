// OLYMPUS Mind: the graph model. Turns a normalized snapshot into what the page draws and counts:
//   buildGraph(snap, now) -> {nodes, index, edges, clusters, learned, stats, sig}
//   diffGraphs(prev, next) -> {first, added, changed, learned, structural}
//   search(graph, query) -> every matching node, best first (title, then tag, then path)
//   resolve(graph, name) -> the id a [[wikilink]] names (by title, file name or path), or null
//   dayLog(graph, now) -> today's lessons (local midnight on): {items oldest first, hours[24], edits, start}
//   thoughts(graph, limit) -> the thought stream: what Jarvis learned and which notes changed, newest first
// Clusters ("galaxies"): Jarvis memories, daily notes, the inbox and the "me" note by kind; every other note by its first tag
// or folder that names a known topic (trading, goals, health, Kalshi, business), else its own tag or folder, else "Other".

const TOPICS = [
  ['trading', 'Trading', '#c8a24a', /^(trad|nq|es$|lit|futures?|mffu|prop|eval|ifvg|cisd|liquidity|setup|risk|journal|market)/],
  ['goals', 'Goals', '#b58aa0', /^(goal|plan|vision|habit|routine|discipline|mindset|review)/],
  ['health', 'Health', '#8a9a62', /^(gym|health|fitness|workout|training|sleep|diet|food|nutrition|run|lift|body)/],
  ['kalshi', 'Kalshi', '#c0603f', /^(kalshi|prediction|polymarket|bets?$)/],
  ['business', 'Business', '#d08a3c', /^(business|biz|money|startup|side|brand|content|client|olympus|idea|work|project)/],
];
const KIND_CLUSTERS = {
  memory: ['memory', 'Jarvis memory', '#ece0c0'],
  daily: ['daily', 'Daily notes', '#6a95b0'],
  inbox: ['inbox', 'Inbox', '#e0b060'],
  me: ['me', 'Me', '#ffffff'],
};
const OTHER = ['other', 'Other', '#9a8f7d'];
const MAX_OWN = 8;                                    // own tag / folder clusters beyond the known topics
const HOUR = 3600e3, WEEK = 7 * 24 * HOUR, PULSE_FOR = 72 * HOUR;

function topicOf(word) {
  for (const t of TOPICS) if (t[3].test(word)) return t;
  return null;
}

function clusterKey(n) {
  if (KIND_CLUSTERS[n.kind]) return { key: n.kind, def: KIND_CLUSTERS[n.kind] };
  const folders = n.path.split('/').slice(0, -1).map((f) => f.toLowerCase());
  for (const w of [...n.tags, ...folders]) {
    const t = topicOf(w);
    if (t) return { key: t[0], def: t };
  }
  if (n.tags.length) return { key: 'tag:' + n.tags[0], own: '#' + n.tags[0] };
  if (folders.length) return { key: 'dir:' + folders[0], own: n.path.split('/')[0] };
  return { key: 'other', def: OTHER };
}

/** A soft colour for clusters the page does not know, spread around the wheel away from the known hues. */
function ownColour(k) {
  const h = (200 + k * 137.508) % 360;
  return `hsl(${h.toFixed(0)}, 38%, 62%)`;
}

const learnedKey = (l) => l.t + '|' + l.text;

export function buildGraph(snap, now = Date.now()) {
  const notes = snap.notes;
  const index = new Map(notes.map((n, i) => [n.id, i]));
  // clusters: the known ones keep their colours; own tags / folders take the biggest MAX_OWN, the rest join "Other"
  const keys = notes.map(clusterKey);
  const ownCount = new Map();
  keys.forEach((k) => { if (k.own) ownCount.set(k.key, (ownCount.get(k.key) || 0) + 1); });
  const keepOwn = new Set([...ownCount].sort((a, b) => b[1] - a[1]).slice(0, MAX_OWN).map((x) => x[0]));
  const clusters = [], byKey = new Map();
  const clusterOf = (k) => {
    let key = k.key, label, colour;
    if (k.own && !keepOwn.has(key)) key = 'other';
    if (byKey.has(key)) return byKey.get(key);
    if (key === 'other') [, label, colour] = OTHER;
    else if (k.own) { label = k.own; colour = ownColour(clusters.length); }
    else [, label, colour] = k.def;
    const c = { i: clusters.length, key, label, colour, count: 0 };
    clusters.push(c); byKey.set(key, c);
    return c;
  };
  const nodes = notes.map((n, i) => {
    const c = clusterOf(keys[i]);
    c.count++;
    const age = n.mtime ? now - n.mtime : Infinity;
    return { ...n, i, cluster: c.i, out: [], back: 0, degree: 0,
      pulse: age >= 0 && age < PULSE_FOR ? (1 - age / PULSE_FOR) ** 2 : 0 };
  });
  // links: resolved, no self links, one edge per pair
  const pairs = new Set(), edgeList = [];
  for (const a of nodes) {
    for (const id of a.links) {
      const j = index.get(id);
      if (j === undefined || j === a.i) continue;
      if (!a.out.includes(j)) { a.out.push(j); nodes[j].back++; }
      const lo = Math.min(a.i, j), hi = Math.max(a.i, j), k = lo * 1e6 + hi;
      if (pairs.has(k)) continue;
      pairs.add(k); edgeList.push(lo, hi);
      nodes[lo].degree++; nodes[hi].degree++;
    }
  }
  for (const n of nodes) {
    n.size = Math.min(26, 4.6 + 2.1 * Math.log2(1 + n.degree) + 1.1 * Math.log2(1 + n.words / 150)) * (n.kind === 'me' ? 1.8 : n.kind === 'memory' ? 1.2 : 1);
  }
  const learned = snap.learned.map((l) => ({ ...l, i: l.note != null && index.has(l.note) ? index.get(l.note) : -1 }));
  const weekAgo = now - WEEK;
  let sig = 2166136261;                              // FNV-1a over ids and edges: a change means the layout must move
  const mix = (s) => { for (let k = 0; k < s.length; k++) sig = Math.imul(sig ^ s.charCodeAt(k), 16777619); };
  notes.forEach((n) => mix(n.id + '\n'));
  mix(edgeList.join(','));
  return {
    nodes, index, clusters, learned,
    edges: Uint32Array.from(edgeList),
    learnedKeys: new Set(learned.map(learnedKey)),
    sig: (sig >>> 0).toString(36) + ':' + nodes.length + ':' + edgeList.length,
    stats: {
      notes: nodes.length,
      links: edgeList.length / 2,
      clusters: clusters.filter((c) => c.count).length,
      learnedWeek: learned.filter((l) => l.t >= weekAgo).length,
    },
  };
}

export function diffGraphs(prev, next) {
  if (!prev) return { first: true, added: [], changed: [], learned: [], structural: true };
  const added = [], changed = [];
  for (const n of next.nodes) {
    const j = prev.index.get(n.id);
    if (j === undefined) added.push(n.i);
    else if (n.mtime > prev.nodes[j].mtime || n.words !== prev.nodes[j].words) changed.push(n.i);
  }
  return {
    first: false, added, changed,
    learned: next.learned.filter((l) => !prev.learnedKeys.has(learnedKey(l))),
    structural: next.sig !== prev.sig,
  };
}

export function search(graph, query) {
  const q = query.trim().toLowerCase().replace(/^#/, '');
  if (!q) return [];
  const scored = [];
  for (const n of graph.nodes) {
    const t = n.title.toLowerCase();
    const s = t === q ? 0 : t.startsWith(q) ? 1 : t.includes(q) ? 2 : n.tags.some((g) => g.startsWith(q)) ? 3 : n.path.toLowerCase().includes(q) ? 4 : -1;
    if (s >= 0) scored.push([s, -n.degree, n]);
  }
  scored.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2].title.localeCompare(b[2].title));
  return scored.map((x) => x[2]);
}

/** The note a [[wikilink]] points at: its title, its file name or its path (case-insensitive), else null. */
export function resolve(graph, name) {
  if (!graph.byName) {
    const m = new Map(), put = (k, id) => { k = String(k || '').toLowerCase(); if (k && !m.has(k)) m.set(k, id); };
    for (const n of graph.nodes) { put(n.path.replace(/\.md$/i, ''), n.id); put(n.title, n.id); put(n.path.split('/').pop().replace(/\.md$/i, ''), n.id); put(n.id, n.id); }
    graph.byName = m;
  }
  return graph.byName.get(String(name || '').trim().toLowerCase()) || null;
}

/** The thought stream, newest first: every lesson Jarvis learned ({kind: 'learned', t, text, i}) and the notes edited most
 * recently ({kind: 'edit', t, text, i}); i = -1 for a lesson about no note in particular. */
export function thoughts(graph, limit = 24) {
  const learned = graph.learned.map((l) => ({ kind: 'learned', t: l.t, text: l.text, i: l.i }));
  const edits = graph.nodes.filter((n) => n.mtime && n.kind !== 'memory').sort((a, b) => b.mtime - a.mtime).slice(0, limit)
    .map((n) => ({ kind: 'edit', t: n.mtime, text: n.title, i: n.i }));
  return learned.concat(edits).sort((a, b) => b.t - a.t).slice(0, limit);
}

/** What Jarvis learned today (since local midnight): the lessons in time order, how many per hour, and how many notes were edited. */
export function dayLog(graph, now = Date.now()) {
  const d = new Date(now); d.setHours(0, 0, 0, 0);
  const start = d.getTime(), hours = new Array(24).fill(0);
  const items = graph.learned.filter((l) => l.t >= start && l.t <= now + 60000).sort((a, b) => a.t - b.t);
  for (const l of items) hours[Math.min(23, new Date(l.t).getHours())]++;
  const edits = graph.nodes.filter((n) => n.mtime && n.mtime >= start && n.kind !== 'memory').length;
  return { start, items, hours, edits };
}
