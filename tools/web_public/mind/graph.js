// OLYMPUS Mind: the graph model. Turns a normalized snapshot into what the page draws and counts:
//   buildGraph(snap, now) -> {nodes, index, edges, clusters, learned, stats, sig}
//   diffGraphs(prev, next) -> {first, added, changed, learned, structural}
//   search(graph, query) -> every matching node, best first (title, then tag, then path)
// Clusters ("galaxies"): Jarvis memories, daily notes, the inbox and the "me" note by kind; every other note by its first tag
// or folder that names a known topic (trading, goals, health, Kalshi, business), else its own tag or folder, else "Other".

const TOPICS = [
  ['trading', 'Trading', '#f5c451', /^(trad|nq|es$|lit|futures?|mffu|prop|eval|ifvg|cisd|liquidity|setup|risk|journal|market)/],
  ['goals', 'Goals', '#a77bff', /^(goal|plan|vision|habit|routine|discipline|mindset|review)/],
  ['health', 'Health', '#46d79a', /^(gym|health|fitness|workout|training|sleep|diet|food|nutrition|run|lift|body)/],
  ['kalshi', 'Kalshi', '#ff6fae', /^(kalshi|prediction|polymarket|bets?$)/],
  ['business', 'Business', '#ff8a4c', /^(business|biz|money|startup|side|brand|content|client|olympus|idea|work|project)/],
];
const KIND_CLUSTERS = {
  memory: ['memory', 'Jarvis memory', '#3fe0ff'],
  daily: ['daily', 'Daily notes', '#8ea7ff'],
  inbox: ['inbox', 'Inbox', '#ffd9a0'],
  me: ['me', 'Me', '#ffffff'],
};
const OTHER = ['other', 'Other', '#9aa3b8'];
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
  return `hsl(${h.toFixed(0)}, 72%, 68%)`;
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
    n.size = Math.min(26, 4.6 + 2.1 * Math.log2(1 + n.degree) + 1.1 * Math.log2(1 + n.words / 150)) * (n.kind === 'me' ? 1.8 : n.kind === 'memory' ? 0.85 : 1);
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
