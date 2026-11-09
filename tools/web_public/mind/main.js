// OLYMPUS Mind: the page. Wires the data adapter (data.js), the model (graph.js), the layout (layout.js, in a worker), the
// renderer (render.js), the camera (controls.js) and the overlay (ui.js). Owns the page's state: the current graph, the
// focus mode (one galaxy), the search, the focused note, the view (galaxy / constellation) and the time-lapse.
// "Constantly learning": a fresh snapshot every 60 s and on every index change; new notes fly in from the edge and ignite,
// edited notes ignite and fire a synapse, recently edited notes pulse, each new "learned" item becomes a cyan spark that
// flies from the ticker to its note and bursts into synapses there, and the thought stream at the bottom grows. While idle
// the brain "thinks": quiet pulses run along its links. Jarvis's memories ring "Me" in cyan.
// While open inside Jarvis it posts its live card (notes, links, learned this week) to Jarvis.
// Themes: applyTheme(theme) restyles the page; it follows olympus.js's theme (OLYMPUS.theme() / onTheme) when the kit has one.
// 2026-11-04 overhaul: the dock under the search opens nine pages (panels.js: Home, Notes, Days, Learned, Graph, Review, Teach, Stats,
// Look); graph filters and a tag filter dim the brain (insights.js filterSet); Teach writes into Jarvis's own keys (teach.js, the one
// writer); skins (skins.js) tint the UI and the nebula sky; ambient dust, sounds through OLYMPUS.sfx, Obsidian deep links on the card.
import * as THREE from '../jarvis/three.module.min.js';
import { openFeed, demoSnapshot } from './data.js';
import { watchLive, withLive } from './live.js';
import { createDemo } from './demo.js';
import { buildGraph, diffGraphs, search, resolve, thoughts, dayLog } from './graph.js';
import { anchorsFor, createLayoutHost, ringRadius, ringSpot } from './layout.js';
import { Brain } from './render.js';
import { OrbitRig } from './controls.js';
import { createUI } from './ui.js';
import { createPanels } from './panels.js';
import { filterSet, obsidianLink } from './insights.js';
import { teach } from './teach.js';
import { createSound } from './sound.js';
import { SKINS, skinById } from './skins.js';
import { load, save } from './store.js';

const O = window.OLYMPUS || null;          // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil
const QUALITY_KEY = 'mind.quality';        // the old per-app key: read only when the kit is missing
const VIEW_KEY = 'mind.view';              // galaxy | stars (this phone only)
// a theme's colour names -> this page's CSS custom properties (mind.css :root)
const THEME_KEYS = { accent: '--cyan', primary: '--cyan', bg: '--bg', background: '--bg', glass: '--glass', panel: '--glass-hi',
  text: '--text', dim: '--dim', muted: '--mut', line: '--line', gold: '--gold' };
const THEME = '#14110e';
const reduced = O ? O.reduced() : matchMedia('(prefers-reduced-motion: reduce)').matches;
const canvas = document.getElementById('gl');

const saved = savedQuality();
const state = {
  graph: null, mode: 'loading', filter: null, query: '', matches: null, focus: -1, lapse: null, pending: null,
  quality: saved || (O && O.lite() ? 'low' : autoQuality()), chosen: !!saved, fps: 0, settled: false,
  view: savedView(), streamKeys: new Set(), gmode: 'all', gmin: 0, tag: null, preview: false,
};
// this phone's choices (skin, atmosphere, sound, the Obsidian vault name) and the review cards, under 'mind.' keys (store.js)
const prefs = { skin: 'auto', sky: true, dust: true, sound: true, vault: '', ...load('prefs', {}) };
if (!SKINS.some((k) => k.id === prefs.skin)) prefs.skin = 'auto';
let review = load('review', { cards: {}, days: [] });
if (!review || typeof review !== 'object' || typeof review.cards !== 'object') review = { cards: {}, days: [] };
const sound = createSound(O, prefs.sound !== false);

const ui = createUI({
  onSearch(q) {
    const g = state.graph;
    if (!g) return;
    const found = search(g, q);
    state.query = q;
    state.matches = q.trim() ? new Set(found.map((n) => n.i)) : null;
    ui.results(found.slice(0, 6), g.clusters, q);
    look();
  },
  onPick(id) { state.query = ''; state.matches = null; panels.close(); focus(id, true); },
  onFly(id) { panels.close(); focus(id, true); },
  onCloseCard: unfocus,
  onFilter(key) { applyFilter(key); },
  onClearFilter() { clearPill(); },
  obsidian: (n) => obsidianLink(prefs.vault, n),
  onView() { setView(state.view === 'stars' ? 'galaxy' : 'stars'); ui.toast(state.view === 'stars' ? 'Constellation view' : 'Galaxy view'); },
  resolve: (name) => (state.graph ? resolve(state.graph, name) : null),
  onToday(open) {
    const want = typeof open === 'boolean' ? open : document.getElementById('day').hidden;
    ui.dayOpen(want);
    if (want && state.graph) ui.day(dayLog(state.graph, Date.now()), state.graph.nodes);
  },
  onReplayDay() { replayDay(); },
  onTimeLapse() { if (state.lapse) stopLapse(); else startLapse(); },
  onQuality() {
    setQuality(state.quality === 'high' ? 'low' : 'high');
    state.chosen = true;
    if (O) O.setFx(state.quality === 'high' ? 'high' : 'low');
    else try { localStorage.setItem(QUALITY_KEY, state.quality); } catch (_) { /* private mode: this visit only */ }
    ui.toast(state.quality === 'high' ? 'High quality' : 'Light mode: smoother on older phones');
  },
});
ui.quality(state.quality);
ui.view(state.view);

/** Focus mode: one galaxy lit, the rest dimmed to a whisper (a chip, a galaxy row on a page, Escape or × to leave). */
function applyFilter(key) {
  if (!state.graph) return;
  state.filter = key;
  const c = state.graph.clusters.find((k) => k.key === key) || null;
  ui.chips(state.graph.clusters, key);
  ui.focusBar(c);
  look();
  pushPanels();
  if (!brain) return;
  if (c && brain.centres) {
    const ring = c.key === 'memory' && brain.ringInfo, p = ring || brain.centres[c.i];
    rig.flyTo(p, Math.max(90, (ring ? ring.r * 1.4 : p.r) * 3));
  } else home();
}

// the nine pages of the dock (panels.js); they read a context and call these handlers
const panels = createPanels({
  fly(id) { panels.close(); focus(id, true); sound.play('tick'); },
  cluster(key) { panels.close(); applyFilter(key); },
  tag(t) { state.tag = t; showPill(); look(); pushPanels(); sound.play('tap'); },
  gmode(mode, min) { state.gmode = mode; state.gmin = min; showPill(); look(); pushPanels(); sound.play('tap'); },
  replay(items) { panels.close(); replayItems(items); },
  teach(input) {
    const r = teach(input);
    if (r.ok) sound.play(input.kind === 'note' ? 'portal' : 'rankup');
    pushPanels();
    return r;
  },
  skin(id) { prefs.skin = id; save('prefs', prefs); applySkin(); pushPanels(); sound.play('tap'); },
  pref(name, value) {
    prefs[name] = value;
    save('prefs', prefs);
    if (name === 'sound') sound.set(value);
    if (name === 'sky' || name === 'dust') applyAmbient();
    if (name === 'vault' && state.focus >= 0 && state.graph) ui.card.show(state.graph.nodes[state.focus], state.graph);
    pushPanels();
    if (name === 'sound' && value) sound.play('tap');
  },
  review(next) { review = next; save('review', review); pushPanels(); },
  play: (name) => sound.play(name),
  surprise() {
    const g = state.graph, pool = g ? g.nodes.filter((n) => n.kind !== 'me') : [];
    if (!pool.length) return;
    panels.close();
    focus(pool[Math.floor(Math.random() * pool.length)].id, true);
    sound.play('portal');
  },
  toast: (t) => ui.toast(t),
  preview() { togglePreview(); },
  beforeOpen() { if (state.focus >= 0) unfocus(); },
});

document.getElementById('sp-teach').addEventListener('click', () => { sound.play('tap'); panels.open('teach'); });
document.getElementById('sp-preview').addEventListener('click', () => { sound.play('tap'); togglePreview(); });

function pushPanels() {
  if (!state.graph) return;
  panels.update({ g: state.graph, mode: state.mode, now: Date.now(), live, prefs, review, tag: state.tag, gmode: state.gmode, gmin: state.gmin,
    filter: state.filter, focus: state.focus, soundOk: sound.available, preview: state.preview, sparse: isSparse() });
  paintSparse();
}

// ------------------------------------------------------------------ a tiny vault is never a blank sky: say what to do, and let the owner look at a grown brain
const SPARSE_BELOW = 12;                                         // notes (not counting the Me note)
let demoSnap = null;
function isSparse() {
  const g = state.graph;
  return !!g && !state.preview && (state.mode === 'live' || state.mode === 'offline') && g.nodes.filter((n) => n.kind !== 'me').length < SPARSE_BELOW;
}
function paintSparse() {
  const g = state.graph;
  if (!g) return;
  if (state.preview) ui.sparse({ preview: true, text: 'Previewing a demo brain, not your vault.' });
  else if (isSparse()) {
    const n = g.nodes.filter((x) => x.kind !== 'me').length;
    ui.sparse({ preview: false, text: n ? `Your brain is just starting: ${n} note${n === 1 ? '' : 's'}.` : 'Your brain is empty so far.' });
  } else ui.sparse(null);
}
/** Show the demo brain in place of the small real one (and back). Nothing is written anywhere. */
async function togglePreview() {
  if (!rawUpdate) return;
  state.preview = !state.preview;
  if (state.preview) {
    if (!demoSnap) { try { demoSnap = await demoSnapshot(); } catch (_) { state.preview = false; ui.toast('The demo brain could not load'); return; } }
    panels.close();
    onUpdate({ mode: 'demo', snap: withLive(demoSnap, live) });
    ui.toast('Demo brain. Tap Back to my vault any time.');
  } else {
    onUpdate({ ...rawUpdate, snap: withLive(rawUpdate.snap, live) });
  }
}

const GMODE_NAMES = { linked: 'linked notes', hubs: 'hubs', orphans: 'orphans', recent: 'edited this week', all: 'every note' };
/** The pill under the search bar: the tag filter, else the graph filter (× clears it). */
function showPill() {
  if (state.tag) ui.filterBar({ kind: 'Tag', name: '#' + state.tag, colour: 'var(--gold)' });
  else if (state.gmode !== 'all' || state.gmin) ui.filterBar({ kind: 'Showing', name: GMODE_NAMES[state.gmode] + (state.gmin ? ` · ${state.gmin}+ links` : ''), colour: 'var(--cyan)' });
  else ui.filterBar(null);
}
function clearPill() {
  state.tag = null; state.gmode = 'all'; state.gmin = 0;
  showPill(); look(); pushPanels();
}

// ------------------------------------------------------------------ the 3D view (the overlay alone without WebGL)
let brain = null, rig = null, needsDraw = true;
if (hasWebGL()) {
  try {
    brain = new Brain(THREE, canvas, { quality: state.quality, reduced });
    O?.track(brain.renderer);
    O?.themeScene?.({ scene: brain.scene, renderer: brain.renderer, clear: 0x14110e, redraw: () => { needsDraw = true; } });   // OLYMPUS theme tints
    rig = new OrbitRig(brain.camera, canvas, {
      reduced,
      onTap(x, y) { const i = brain.pick(x, y); if (i >= 0) focus(state.graph.nodes[i].id, false); else if (state.focus >= 0) unfocus(); },
      onDoubleTap(x, y) {                     // the first tap already focused the note (and the view may have slid since)
        const i = brain.pick(x, y), to = i >= 0 ? i : state.focus;
        if (to >= 0) focus(state.graph.nodes[to].id, true); else home();
      },
    });
  } catch (_) {
    brain = null;
  }
}
if (!brain) { ui.noGL(); O?.ready(); }        // the numbers and the search still work: the page is up
else {
  brain.setView(state.view);
  // the OLYMPUS render core (bloom, MSAA, film finish) loads beside the first frame; without it the plain renderer keeps drawing
  import('../olympus/render.js').then((m) => { if (brain.useCore(m.createRenderer)) needsDraw = true; }).catch(() => { /* old build: plain look */ });
}
O?.mode(state.quality === 'low');
const layout = brain ? createLayoutHost((pos, asleep) => { brain.setTargets(pos); state.settled = asleep; needsDraw = true; }) : null;
addEventListener('resize', () => { if (brain) { brain.resize(); frameFocus(); needsDraw = true; } });

function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch (_) {
    return false;
  }
}

function savedQuality() {
  if (O) return O.chosen() ? (O.lite() ? 'low' : 'high') : null;
  try {
    const q = localStorage.getItem(QUALITY_KEY);
    return q === 'high' || q === 'low' ? q : null;
  } catch (_) {
    return null;                                    // no storage: decide again on each visit
  }
}

function savedView() {
  try { return localStorage.getItem(VIEW_KEY) === 'stars' ? 'stars' : 'galaxy'; } catch (_) { return 'galaxy'; }
}

function setView(v) {
  state.view = v;
  ui.view(v);
  if (brain) { brain.setView(v); needsDraw = true; }
  try { localStorage.setItem(VIEW_KEY, v); } catch (_) { /* private mode: this visit only */ }
}

function autoQuality() {
  const weak = (navigator.deviceMemory && navigator.deviceMemory <= 2) || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2);
  return weak ? 'low' : 'high';
}

function setQuality(q) {
  state.quality = q;
  O?.mode(q === 'low');
  ui.quality(q);
  if (brain) { brain.setQuality(q); look(); }
}

// ------------------------------------------------------------------ data in
function onUpdate(update) {
  if (state.lapse) { state.pending = update; return; }        // a time-lapse plays to its end first
  const { mode, snap } = update, now = Date.now(), prev = state.graph;
  const next = buildGraph(snap, now);
  const d = diffGraphs(prev, next);
  const focusId = state.focus >= 0 && prev ? prev.nodes[state.focus].id : null;
  state.mode = mode;
  state.graph = next;
  if (state.filter && !next.clusters.some((c) => c.key === state.filter && c.count)) state.filter = null;
  ui.mode(mode);
  ui.stats(next.stats);
  ui.chips(next.clusters, state.filter);
  ui.focusBar(next.clusters.find((c) => c.key === state.filter) || null);
  if (d.first || d.learned.length) ui.ticker(next.learned, !d.first && d.learned.length > 0);
  stream(next, d.first);
  ui.day(dayLog(next, now), next.nodes, now);
  state.focus = focusId && next.index.has(focusId) ? next.index.get(focusId) : -1;
  if (state.focus >= 0) ui.card.show(next.nodes[state.focus], next); else ui.card.hide();
  frameFocus();
  pushPanels();
  if (d.first) openHome();
  if (brain) {
    place(prev, next, d);
    const sparked = new Set(), me = next.clusters.find((c) => c.key === 'me');
    const meNode = me ? next.nodes.find((x) => x.cluster === me.i) : null;
    for (const l of d.learned) {                                // a lesson about no note in particular is about you
      const to = l.i >= 0 ? l.i : meNode ? meNode.i : -1;
      if (to >= 0) { brain.spark(to); sparked.add(to); }
    }
    for (const i of d.added) brain.ignite(i, null, false);           // it glows as it flies in from the edge
    for (const i of d.changed) if (!sparked.has(i)) { brain.ignite(i); brain.synapse(i); }
  }
  state.matches = state.query.trim() ? new Set(search(next, state.query).map((x) => x.i)) : null;
  look();
  postCard(next, mode);
}

let replayTimers = [];
/** Replay what Jarvis learned: a spark flies to each note in time order (reduced motion: faster, no flight needed). */
function replayItems(items) {
  replayTimers.forEach(clearTimeout); replayTimers = [];
  const g = state.graph;
  if (!g) return;
  const me = meId(g), gap = reduced ? 250 : 700;
  items.forEach((l, k) => {
    replayTimers.push(setTimeout(() => {
      ui.dayMark(l.t);
      const to = l.i >= 0 ? l.i : me && g.index.has(me) ? g.index.get(me) : -1;
      if (brain && to >= 0) { brain.spark(to); needsDraw = true; }
      sound.play('tick');
    }, k * gap));
  });
  replayTimers.push(setTimeout(() => ui.dayMark(null), items.length * gap + 900));
  if (!items.length) ui.toast('Nothing to replay yet'); else if (items.length > 1) ui.toast(`Replaying ${items.length} things Jarvis learned`);
}

/** Replay today's lessons (the Today strip). */
function replayDay() {
  const g = state.graph;
  if (!g) return;
  const log = dayLog(g, Date.now());
  if (!log.items.length) { ui.toast('Nothing learned yet today'); return; }
  replayItems(log.items);
}

/** The thought stream: lessons and edits, newest first; the ones that were not there before slide in. */
function stream(g, first) {
  const list = thoughts(g, 24).map((x) => {
    const node = x.i >= 0 ? g.nodes[x.i] : null;
    return { ...x, key: x.kind + '|' + x.t + '|' + x.text, id: node ? node.id : meId(g), colour: node ? g.clusters[node.cluster].colour : '#fff' };
  });
  const fresh = first ? new Set() : new Set(list.filter((x) => !state.streamKeys.has(x.key)).map((x) => x.key));
  state.streamKeys = new Set(list.map((x) => x.key));
  ui.stream(list, fresh);
}

function meId(g) {
  const me = g.clusters.find((c) => c.key === 'me'), n = me ? g.nodes.find((x) => x.cluster === me.i) : null;
  return n ? n.id : null;
}

/** Positions for the new graph: kept notes stay where they are; new ones are seeded near their links (or their galaxy) for the
 * layout, and drawn from far out so they fly in. The first graph is a big bang from the centre. Jarvis's memories take their
 * seats on the ring around Me. */
function place(prev, next, d) {
  const n = next.nodes.length, sizes = next.clusters.map((c) => c.count);
  const center = next.clusters.findIndex((c) => c.key === 'me');
  const ring = center >= 0 ? next.clusters.findIndex((c) => c.key === 'memory') : -1;
  const anchors = anchorsFor(sizes, center);
  const memories = ring >= 0 ? next.nodes.filter((x) => x.cluster === ring) : [];
  const seat = new Map(memories.map((x, k) => [x.i, ringSpot(k, memories.length, ringRadius(n))]));
  const targets = new Float32Array(n * 3), start = new Float32Array(n * 3);
  const old = (node) => (prev ? prev.index.get(node.id) : undefined);
  const jitter = (s) => (Math.random() - 0.5) * s;
  for (const node of next.nodes) {
    const i3 = node.i * 3, j = old(node);
    if (j !== undefined) {
      targets.set(brain.target.subarray(j * 3, j * 3 + 3), i3);
      start.set(brain.disp.subarray(j * 3, j * 3 + 3), i3);
      continue;
    }
    const near = node.out.map(old).filter((k) => k !== undefined);
    const src = near.length ? brain.target : anchors.pos, at = near.length ? near[0] * 3 : node.cluster * 3;
    const spread = near.length ? 12 : 30 + 3 * Math.sqrt(next.clusters[node.cluster].count);
    if (seat.has(node.i)) targets.set(seat.get(node.i), i3);
    else for (let a = 0; a < 3; a++) targets[i3 + a] = src[at + a] + jitter(spread);
    if (d.first) for (let a = 0; a < 3; a++) start[i3 + a] = reduced ? targets[i3 + a] : targets[i3 + a] * 0.03;
    else start.set(brain.edgePoint(targets, node.i), i3);
  }
  brain.setGraph(next, { targets, start, normals: anchors.normal });
  if (d.first) { rig.target = { x: 0, y: 0, z: 0 }; rig.radius = (anchors.radius + 40) * (innerWidth < innerHeight ? 3.1 : 2.2); }
  if (d.structural) {
    state.settled = false;
    layout.run({ pos: targets, cluster: Int32Array.from(next.nodes, (x) => x.cluster), edges: next.edges, sizes, center, ring, alpha: d.first ? 1 : 0.3 });
  }
  needsDraw = true;
}

/** Home opens by itself on the first visit of a session (a half-height dashboard over the brain), on a portrait phone, never under
 * automation unless ?home=1, never with ?home=0. */
function openHome() {
  const q = params.get('home');
  if (q === '0' || (navigator.webdriver && q !== '1') || matchMedia('(orientation: landscape) and (max-height: 500px)').matches) return;
  try { if (sessionStorage.getItem('mind.home') === '1' && q !== '1') return; sessionStorage.setItem('mind.home', '1'); } catch (_) { /* no session storage: every visit */ }
  panels.open('home', { peek: true });
}

// ------------------------------------------------------------------ look: filter, search, focus, time-lapse
function look() {
  const g = state.graph;
  if (!g || !brain) return;
  const n = g.nodes.length, emph = new Float32Array(n).fill(1);
  const cluster = g.clusters.map((c) => (state.filter && c.key !== state.filter ? 0.03 : 1));
  if (state.filter) for (const node of g.nodes) if (g.clusters[node.cluster].key !== state.filter) emph[node.i] = 0.07;
  const gset = filterSet(g, state.gmode, state.gmin, Date.now());                 // the Graph page: linked / hubs / orphans / recent / min links
  if (gset) for (let i = 0; i < n; i++) if (!gset.has(i)) emph[i] = Math.min(emph[i], 0.08);
  if (state.tag) for (const node of g.nodes) if (!node.tags.includes(state.tag)) emph[node.i] = Math.min(emph[node.i], 0.08);
  if (state.matches) {
    for (let i = 0; i < n; i++) emph[i] = state.matches.has(i) ? 1.6 : Math.min(emph[i], 0.16);
    cluster.forEach((v, k) => { cluster[k] = v * 0.45; });
  }
  if (state.focus >= 0) {
    const f = g.nodes[state.focus], near = new Set(f.out);
    for (const m of g.nodes) if (m.out.includes(f.i)) near.add(m.i);
    for (let i = 0; i < n; i++) emph[i] = i === f.i ? 2 : near.has(i) ? Math.max(emph[i], 1.2) : emph[i] * 0.45;
    cluster.forEach((v, k) => { cluster[k] = v * (k === f.cluster ? 0.9 : 0.5); });
  }
  brain.setLook(emph, state.lapse ? state.lapse.show : new Float32Array(n).fill(1), cluster);
  needsDraw = true;
}

function focus(id, fly) {
  const g = state.graph, i = g ? g.index.get(id) : undefined;
  if (i === undefined) return;
  const opened = state.focus !== i;
  if (!document.getElementById('panel').hidden) panels.close();
  state.focus = i;
  ui.card.show(g.nodes[i], g);
  frameFocus();
  look();
  if (brain && opened) brain.synapse(i);              // opening a note fires its synapses
  if (fly && brain) rig.flyTo(brain.nodePoint(i), 70 + g.nodes[i].size * 7);
}

function unfocus() {
  state.focus = -1;
  ui.card.hide();
  frameFocus();
  look();
}

/** Keep the focused note in the open part of the screen: above its card (portrait) or beside it (landscape side sheet). */
function frameFocus() {
  if (!brain) return;
  const card = document.getElementById('card');
  if (card.hidden) { brain.shiftTo(0, 0); return; }
  const r = card.getBoundingClientRect(), top = document.getElementById('top').getBoundingClientRect();
  if (r.width < innerWidth * 0.7) brain.shiftTo((r.right + innerWidth) / 2 - innerWidth / 2, 0);
  else brain.shiftTo(0, (top.bottom + r.top) / 2 - innerHeight / 2);
}

function home() { if (brain) rig.flyTo(brain.centre, brain.extent * 2.5); }

// ------------------------------------------------------------------ time-lapse: the vault growing, note by note, by mtime
function startLapse() {
  const g = state.graph;
  if (!g || g.nodes.length < 2) { ui.toast('Not enough notes for a time-lapse yet'); return; }
  const order = g.nodes.slice().sort((a, b) => a.mtime - b.mtime).map((x) => x.i);
  unfocus();
  state.lapse = { order, shown: 0, start: performance.now(), dur: Math.min(16000, 7000 + g.nodes.length * 6), show: new Float32Array(g.nodes.length) };
  home();
  stepLapse(performance.now());
}

function stepLapse(now) {
  const L = state.lapse, g = state.graph, p = Math.min(1, (now - L.start) / L.dur);
  const want = Math.ceil(p * L.order.length);
  let rings = 0;
  for (; L.shown < want; L.shown++) {
    const i = L.order[L.shown];
    L.show[i] = 1;
    if (brain) brain.ignite(i, null, rings++ < 1);            // every note flashes; one ring per frame, not a white-out
  }
  const last = g.nodes[L.order[Math.max(0, L.shown - 1)]];
  ui.timeLapse({ t: last.mtime || Date.now(), progress: p, count: L.shown });
  look();
  if (p >= 1 && now - L.start > L.dur + 1500) stopLapse();
}

function stopLapse() {
  state.lapse = null;
  ui.timeLapse(null);
  look();
  if (state.pending) { const u = state.pending; state.pending = null; onUpdate(u); }
}

// ------------------------------------------------------------------ Jarvis's live card (only while framed by Jarvis)
function postCard(g, mode) {
  if (window.parent === window) return;
  const latest = g.learned[g.learned.length - 1];
  const card = {
    v: 1, name: 'Mind', t: Math.floor(Date.now() / 1000), theme: THEME,
    status: mode === 'live' ? { level: 'ok', label: 'Brain online' } : mode === 'offline' ? { level: 'warn', label: 'Vault offline' } : { level: 'off', label: 'Demo: connect Obsidian' },
    kpis: [{ label: 'Notes', value: g.stats.notes.toLocaleString('en-US') }, { label: 'Links', value: g.stats.links.toLocaleString('en-US') },
      { label: 'Learned 7d', value: String(g.stats.learnedWeek) }],
    lines: latest ? [('Learned: ' + latest.text).slice(0, 120)] : [],
  };
  try { window.parent.postMessage({ jarvis: 1, href: location.href, card }, location.origin); } catch (_) { /* not Jarvis */ }
}

// ------------------------------------------------------------------ the frame loop
let last = performance.now(), win = { t: 0, frames: 0, slow: 0 }, labelTick = 0;
function frame(now) {
  requestAnimationFrame(frame);
  if (!brain || (O ? O.hidden() : document.hidden) || !state.graph) return;     // hidden tab: no frame (the battery)
  const gap = O && O.frameGap ? O.frameGap() : 0;                           // idle 30 / 15 fps, battery saver, 3D Off (docs/OLYMPUS_PERF.md)
  if (gap && now - last < gap - 3) return;
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (state.lapse) stepLapse(now);
  if (reduced && !needsDraw && !brain.busy && !rig.busy) return;  // nothing moves: no frame
  needsDraw = false;
  brain.frame(dt, now / 1000, rig);
  if (labelTick++ % 2 === 0) labels();
  if (gap) win.t = win.frames = 0; else meter(dt);                          // a deliberate cap is not a slow phone
}
requestAnimationFrame(frame);

/** Slow frames for 2 windows in a row on high quality (and no saved choice): switch to the light mode once. */
function meter(dt) {
  win.t += dt; win.frames++;
  if (win.t < 2.5) return;
  state.fps = Math.round(win.frames / win.t);
  win.slow = state.fps < 38 ? win.slow + 1 : 0;
  win.t = 0; win.frames = 0;
  if (win.slow >= 2 && state.quality === 'high' && !state.chosen && !reduced) {
    setQuality('low');
    ui.toast('Light mode on for smoother motion');
  }
}

function labels() {
  const g = state.graph, out = [];
  if (brain.centres) {
    const cam = brain.camera.position, reach = rig.radius + brain.extent, ring = brain.ringInfo;
    g.clusters.forEach((c, k) => {
      let p = brain.centres[k];
      if (c.key === 'memory' && ring) p = { x: ring.x, y: ring.y + ring.r * 0.55, z: ring.z, r: ring.r * 0.5 };   // above the ring
      if (!p || c.count < 3 || c.key === 'me') return;
      const s = brain.screenOf({ x: p.x, y: p.y + p.r * 0.75 + 8, z: p.z });
      if (!s.front) return;
      const dist = Math.hypot(cam.x - p.x, cam.y - p.y, cam.z - p.z);
      let alpha = Math.max(0.2, Math.min(0.95, 1.35 - dist / reach));
      if (state.filter && state.filter !== c.key) alpha = 0.12;
      if (state.focus >= 0 || state.matches) alpha *= 0.45;
      out.push({ key: 'c:' + c.key, text: c.label, x: s.x, y: s.y, alpha, colour: c.colour });
    });
  }
  const notes = state.focus >= 0 ? [state.focus] : state.matches ? [...state.matches].slice(0, 5) : [];
  for (const i of notes) {
    const s = brain.screenOf(brain.nodePoint(i));
    if (s.front) out.push({ key: 'note:' + g.nodes[i].id, text: g.nodes[i].title, x: s.x, y: s.y, alpha: 1, colour: '#fff', note: true });
  }
  ui.labels(declutter(out));
}

/** Galaxy names never sit on top of each other: a note's name first, then Jarvis's memory ring, then the nearer (brighter)
 * galaxy; a name that would overlap one already placed waits for the view to turn. */
function declutter(list) {
  const kept = [], rank = (l) => (l.note ? 2 : l.key === 'c:memory' ? 1 : 0);
  for (const l of list.slice().sort((a, b) => rank(b) - rank(a) || b.alpha - a.alpha)) {
    const w = l.note ? 0 : l.text.length * 4.6 + 20;                       // about half a name's width at 11 px, spaced
    if (!l.note && kept.some((k) => !k.note && Math.abs(k.y - l.y) < 16 && Math.abs(k.x - l.x) < w + k.text.length * 4.6)) continue;
    kept.push(l);
  }
  return kept;
}

// ------------------------------------------------------------------ start (a debug handle for the console and the tests)
const params = new URLSearchParams(location.search);
const demoSize = Math.min(5000, parseInt(params.get('demo') || '0', 10) || 0);
window.mind = {
  get mode() { return state.mode; },
  get stats() { return state.graph && state.graph.stats; },
  get focus() { return state.focus >= 0 ? state.graph.nodes[state.focus].id : null; },
  get quality() { return state.quality; },
  get fps() { return state.fps; },
  get sparks() { return brain ? brain.sparks.length : 0; },
  get sparksLaunched() { return brain ? brain.launched : 0; },
  get layout() { return layout ? layout.mode : 'none'; },
  get settled() { return state.settled; },
  get view() { return state.view; },
  get filter() { return state.filter; },
  get synapses() { return brain ? brain.synapses.count : 0; },
  get nebulae() { return brain ? brain.nebulae.puffs.length : 0; },
  get ring() { return brain && brain.ringInfo ? { ...brain.ringInfo } : null; },
  get day() { return state.graph ? dayLog(state.graph, Date.now()) : null; },
  get core() { return brain && brain.rc ? brain.rc.passes() : null; },
  get live() { return live ? { ...live.counts, items: live.items.length } : null; },
  get thoughts() { return document.querySelectorAll('#stream li').length; },
  get panel() { return panels.current; },
  get review() { const q = panels.review; return q ? { id: q.id, prompt: q.prompt, choices: q.choices, answer: q.answer, kind: q.kind } : null; },
  get gmode() { return { mode: state.gmode, min: state.gmin }; },
  get tag() { return state.tag; },
  get preview() { return state.preview; },
  get sparse() { return isSparse(); },
  get prefs() { return { ...prefs }; },
  get ambient() { return brain ? { sky: brain.ambient.sky.visible, dust: brain.ambient.dust.visible, motes: brain.ambient.dust.geometry.attributes.aSeed.count } : null; },
  get dim() { return brain && brain.emph ? Array.from(brain.emph).filter((v) => v < 0.2).length : 0; },
  memoryOnRing: () => {                                  // how far each memory sits from the ring (share of its radius)
    const r = brain && brain.ringInfo, g = state.graph;
    if (!r || !g) return null;
    const mem = g.clusters.findIndex((c) => c.key === 'memory');
    return g.nodes.filter((x) => x.cluster === mem).map((x) => {
      const p = brain.nodePoint(x.i);
      return Math.abs(Math.hypot(p.x - r.x, p.y - r.y, p.z - r.z) - r.r) / r.r;
    });
  },
  setView: (v) => setView(v === 'stars' ? 'stars' : 'galaxy'),
  applyTheme: (t) => applyTheme(t),
  camera: () => rig && { target: { ...rig.target }, radius: rig.radius, flying: !!rig.flight },
  labelBand: () => ui.band(),
  nodePoint: (id) => (brain && state.graph.index.has(id) ? brain.nodePoint(state.graph.index.get(id)) : null),
  screenOf: (id) => (brain && state.graph.index.has(id) ? brain.screenOf(brain.nodePoint(state.graph.index.get(id))) : null),
};
// Jarvis learning, live: what she saves on this phone (live.js reads her localStorage keys, read-only) joins the brain the moment
// it lands: a storage event from another tab, plus a 4 s poll for this one. New items glow in their constellation with a ripple.
let rawUpdate = null, live = null;
const showBrain = (l) => ui.brain(l.counts, state.graph ? state.graph.clusters.filter((c) => c.count && c.key !== 'me' && c.key !== 'memory').length : 0);
openFeed((u) => { rawUpdate = u; if (state.preview) return; onUpdate({ ...u, snap: withLive(u.snap, live) }); showBrain(live || { counts: { memories: 0, written: 0 } }); }, { demo: createDemo({ size: demoSize }) });
watchLive((l, first) => {
  const had = new Set(live ? live.items.map((x) => x.id) : []);
  live = l;
  if (!rawUpdate) return;                                         // the first feed merges it
  const fresh = first ? [] : l.items.filter((x) => !had.has(x.id));
  if (!state.preview) onUpdate({ ...rawUpdate, snap: withLive(rawUpdate.snap, l) });
  showBrain(l);
  if (brain) for (const it of fresh) { const idx = state.graph.index.get('live:' + it.id); if (idx !== undefined) { brain.spark(idx); sound.play('portal'); } }
  if (fresh.length) ui.toast('Jarvis learned: ' + fresh[fresh.length - 1].text.slice(0, 90) + (fresh.length > 1 ? ` (+${fresh.length - 1} more)` : ''));
  needsDraw = true;
});

// ------------------------------------------------------------------ themes (olympus.js: OLYMPUS.theme() / onTheme, when present)
/** Restyle the page from a theme: {accent, bg, glass, text, ...} or CSS custom properties ('--x': value), flat or one level
 * down (e.g. {name, vars: {...}}). Unknown keys are ignored; a bad value never breaks the page. Returns what it applied. */
function applyTheme(theme) {
  if (!theme || typeof theme !== 'object') return {};
  const known = (o) => Object.keys(o).some((k) => k.startsWith('--') || k in THEME_KEYS);
  const t = known(theme) ? theme : Object.values(theme).find((v) => v && typeof v === 'object' && !Array.isArray(v) && known(v));
  if (!t) return {};
  const root = document.documentElement.style, done = {};
  const hexRgb = (c) => { const m = /^#?([0-9a-f]{6})$/i.exec(String(c || '').trim()); if (!m) return null; const v = parseInt(m[1], 16); return [v >> 16 & 255, v >> 8 & 255, v & 255].join(', '); };
  const set = (k, v) => { if (typeof v === 'string' && v.length < 200 && !/[;{}<>]/.test(v)) { root.setProperty(k, v); done[k] = v; } };
  for (const [k, v] of Object.entries(t)) {
    if (k.startsWith('--')) set(k, v);
    else if (THEME_KEYS[k]) set(THEME_KEYS[k], v);
  }
  const accent = t.accent || t.primary || t['--cyan'];
  if (hexRgb(accent)) { set('--cyan-rgb', hexRgb(accent)); set('--line-hi', `rgba(${hexRgb(accent)}, 0.35)`); }
  const bg = t.bg || t.background || t['--bg'];
  if (brain && hexRgb(bg)) { brain.setBackground(bg); needsDraw = true; }
  return done;
}

// ------------------------------------------------------------------ skins (Look page) and the ambient layers
let skinKeys = [], kitTheme = null;
/** The chosen skin on top of the OLYMPUS theme: the accent and page colour as CSS variables, the three colours of the nebula sky. 'auto' = the kit alone. */
function applySkin() {
  const sk = skinById(prefs.skin), root = document.documentElement.style;
  for (const k of skinKeys) root.removeProperty(k);
  skinKeys = [];
  if (sk.accent) skinKeys = Object.keys(applyTheme({ accent: sk.accent, bg: sk.bg }));
  else if (kitTheme) applyTheme(kitTheme);
  const base = sk.bg || (kitTheme && (kitTheme.bg || kitTheme.background)) || THEME;
  if (brain) { brain.setSky(sk.sky, base); brain.setBackground(base); needsDraw = true; }
}
function applyAmbient() { if (brain) { brain.setAmbient({ sky: prefs.sky !== false, dust: prefs.dust !== false }); needsDraw = true; } }
applyAmbient();
applySkin();

(function followTheme() {
  const api = window.OLYMPUS || window.Olympus || null;
  if (!api) return;
  try {
    if (typeof api.theme === 'function') { const t = api.theme(); if (t && typeof t === 'object') { kitTheme = t; applyTheme(t); } }
    if (typeof api.onTheme === 'function') api.onTheme((t) => { kitTheme = t && typeof t === 'object' ? t : null; applyTheme(t); applySkin(); });
  } catch (_) { /* an older kit: the page's own look */ }
  applySkin();
})();
