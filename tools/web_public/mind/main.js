// OLYMPUS Mind: the page. Wires the data adapter (data.js), the model (graph.js), the layout (layout.js, in a worker), the
// renderer (render.js), the camera (controls.js) and the overlay (ui.js). Owns the page's state: the current graph, the
// filter, the search, the focused note and the time-lapse.
// "Constantly learning": a fresh snapshot every 60 s and on every index change; new notes fly in from the edge and ignite,
// edited notes ignite, recently edited notes pulse, and each new "learned" item becomes a cyan spark that flies from the
// ticker to its note. While open inside Jarvis it posts its live card (notes, links, learned this week) to Jarvis.
import * as THREE from '../jarvis/three.module.min.js';
import { openFeed } from './data.js';
import { createDemo } from './demo.js';
import { buildGraph, diffGraphs, search } from './graph.js';
import { anchorsFor, createLayoutHost } from './layout.js';
import { Brain } from './render.js';
import { OrbitRig } from './controls.js';
import { createUI } from './ui.js';

const O = window.OLYMPUS || null;          // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil
const QUALITY_KEY = 'mind.quality';        // the old per-app key: read only when the kit is missing
const THEME = '#03040a';
const reduced = O ? O.reduced() : matchMedia('(prefers-reduced-motion: reduce)').matches;
const canvas = document.getElementById('gl');

const saved = savedQuality();
const state = {
  graph: null, mode: 'loading', filter: null, query: '', matches: null, focus: -1, lapse: null, pending: null,
  quality: saved || (O && O.lite() ? 'low' : autoQuality()), chosen: !!saved, fps: 0, settled: false,
};

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
  onPick(id) { state.query = ''; state.matches = null; focus(id, true); },
  onFly(id) { focus(id, true); },
  onCloseCard: unfocus,
  onFilter(key) {
    state.filter = key;
    ui.chips(state.graph.clusters, key);
    look();
    if (!brain) return;
    const c = state.graph.clusters.find((k) => k.key === key);
    if (c && brain.centres) { const p = brain.centres[c.i]; rig.flyTo(p, Math.max(90, p.r * 3)); } else home();
  },
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

// ------------------------------------------------------------------ the 3D view (the overlay alone without WebGL)
let brain = null, rig = null, needsDraw = true;
if (hasWebGL()) {
  try {
    brain = new Brain(THREE, canvas, { quality: state.quality, reduced });
    O?.track(brain.renderer);
    O?.themeScene?.({ scene: brain.scene, renderer: brain.renderer, clear: 0x03040a, redraw: () => { needsDraw = true; } });   // OLYMPUS theme tints
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
  if (d.first || d.learned.length) ui.ticker(next.learned, !d.first && d.learned.length > 0);
  state.focus = focusId && next.index.has(focusId) ? next.index.get(focusId) : -1;
  if (state.focus >= 0) ui.card.show(next.nodes[state.focus], next); else ui.card.hide();
  frameFocus();
  if (brain) {
    place(prev, next, d);
    const sparked = new Set(), me = next.clusters.find((c) => c.key === 'me');
    const meNode = me ? next.nodes.find((x) => x.cluster === me.i) : null;
    for (const l of d.learned) {                                // a lesson about no note in particular is about you
      const to = l.i >= 0 ? l.i : meNode ? meNode.i : -1;
      if (to >= 0) { brain.spark(to); sparked.add(to); }
    }
    for (const i of d.added) brain.ignite(i, null, false);           // it glows as it flies in from the edge
    for (const i of d.changed) if (!sparked.has(i)) brain.ignite(i);
  }
  state.matches = state.query.trim() ? new Set(search(next, state.query).map((x) => x.i)) : null;
  look();
  postCard(next, mode);
}

/** Positions for the new graph: kept notes stay where they are; new ones are seeded near their links (or their galaxy) for the
 * layout, and drawn from far out so they fly in. The first graph is a big bang from the centre. */
function place(prev, next, d) {
  const n = next.nodes.length, sizes = next.clusters.map((c) => c.count);
  const center = next.clusters.findIndex((c) => c.key === 'me');
  const anchors = anchorsFor(sizes, center);
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
    for (let a = 0; a < 3; a++) targets[i3 + a] = src[at + a] + jitter(spread);
    if (d.first) for (let a = 0; a < 3; a++) start[i3 + a] = reduced ? targets[i3 + a] : targets[i3 + a] * 0.03;
    else start.set(brain.edgePoint(targets, node.i), i3);
  }
  brain.setGraph(next, { targets, start, normals: anchors.normal });
  if (d.first) { rig.target = { x: 0, y: 0, z: 0 }; rig.radius = (anchors.radius + 40) * (innerWidth < innerHeight ? 3.1 : 2.2); }
  if (d.structural) {
    state.settled = false;
    layout.run({ pos: targets, cluster: Int32Array.from(next.nodes, (x) => x.cluster), edges: next.edges, sizes, center, alpha: d.first ? 1 : 0.3 });
  }
  needsDraw = true;
}

// ------------------------------------------------------------------ look: filter, search, focus, time-lapse
function look() {
  const g = state.graph;
  if (!g || !brain) return;
  const n = g.nodes.length, emph = new Float32Array(n).fill(1);
  if (state.filter) for (const node of g.nodes) if (g.clusters[node.cluster].key !== state.filter) emph[node.i] = 0.1;
  if (state.matches) for (let i = 0; i < n; i++) emph[i] = state.matches.has(i) ? 1.6 : Math.min(emph[i], 0.16);
  if (state.focus >= 0) {
    const f = g.nodes[state.focus], near = new Set(f.out);
    for (const m of g.nodes) if (m.out.includes(f.i)) near.add(m.i);
    for (let i = 0; i < n; i++) emph[i] = i === f.i ? 2 : near.has(i) ? Math.max(emph[i], 1.2) : emph[i] * 0.45;
  }
  brain.setLook(emph, state.lapse ? state.lapse.show : new Float32Array(n).fill(1));
  needsDraw = true;
}

function focus(id, fly) {
  const g = state.graph, i = g ? g.index.get(id) : undefined;
  if (i === undefined) return;
  state.focus = i;
  ui.card.show(g.nodes[i], g);
  frameFocus();
  look();
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
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (state.lapse) stepLapse(now);
  if (reduced && !needsDraw && !brain.busy && !rig.busy) return;  // nothing moves: no frame
  needsDraw = false;
  brain.frame(dt, now / 1000, rig);
  if (labelTick++ % 2 === 0) labels();
  meter(dt);
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
    const cam = brain.camera.position, reach = rig.radius + brain.extent;
    g.clusters.forEach((c, k) => {
      const p = brain.centres[k];
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
  ui.labels(out);
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
  get layout() { return layout ? layout.mode : 'none'; },
  get settled() { return state.settled; },
  camera: () => rig && { target: { ...rig.target }, radius: rig.radius, flying: !!rig.flight },
  labelBand: () => ui.band(),
  nodePoint: (id) => (brain && state.graph.index.has(id) ? brain.nodePoint(state.graph.index.get(id)) : null),
  screenOf: (id) => (brain && state.graph.index.has(id) ? brain.screenOf(brain.nodePoint(state.graph.index.get(id))) : null),
};
openFeed(onUpdate, { demo: createDemo({ size: demoSize }) });
