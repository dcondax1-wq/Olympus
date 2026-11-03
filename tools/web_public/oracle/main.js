// ORACLE: a live 3D market radar of NQ, the LIT bot's world (owner 2026-11-03). Read-only: it never trades, never writes.
// Boot, the data schedule and the animation loop. live.json every 30-60 s while the page is visible (and at once when it
// comes back), the site's home.json every 5 min; the freshest one wins. Older than 20 min: LAST SEEN with the last world
// kept. Nothing at all: a real session replayed (demo.js). "Replay today" rebuilds today's session from the live World and
// plays it with a scrubber. Quality: HD, or LITE (fewer stars, a thinner aurora, lower resolution) chosen by the owner or
// switched on once by itself when frames run slow; prefers-reduced-motion stops the motion. applyTheme(tokens) takes an
// OLYMPUS theme (window.OLYMPUS.theme() / onTheme, when the kit has them).
import * as THREE from '../jarvis/three.module.min.js';
import { fetchLive, fetchSite, normalize, FRESH_S } from './data.js';
import { loadDemo, docAt, span, todayFx } from './demo.js';
import { Scene } from './scene.js';
import { Hud, usd } from './hud.js';
import { Ladder } from './ladder.js';
import { Ribbon, ribbonOf } from './events.js';

const O = window.OLYMPUS || null;          // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil
const QUALITY_KEY = 'oracle.quality';      // the old per-app key: read only when the kit is missing
const THEME = '#04050d';
const SITE_EVERY_S = 300;
const reduced = O ? O.reduced() : matchMedia('(prefers-reduced-motion: reduce)').matches;
const forced = new URLSearchParams(location.search).has('demo');

let saved = null;
if (O) saved = O.chosen() ? (O.lite() ? 'low' : 'high') : null;
else try { saved = localStorage.getItem(QUALITY_KEY); } catch (_) { /* private mode */ }
const state = {
  mode: 'loading', world: null, live: null, site: null, gate: { apiUntil: 0 }, every: 45, history: [],
  demo: null, fixture: null, demoT: 0, playing: true, hold: 0, dragging: false, canToday: false, userDemo: forced, quality: saved === 'low' || saved === 'high' ? saved : O && O.lite() ? 'low' : 'high',
  chosen: saved === 'low' || saved === 'high', fps: 0, card: '', lastDemoDoc: 0, siteAt: 0, span: null,
};
const nowS = () => (state.mode === 'demo' ? state.demoT : Date.now() / 1000);

const hud = new Hud();
hud.quality(state.quality);
const ladder = new Ladder(document.getElementById('ladder'));
const ribbon = new Ribbon(document.getElementById('events'), document.getElementById('ev-empty'));
let scene = null;
try {
  scene = new Scene(THREE, document.getElementById('gl'), { quality: state.quality, reduced });
  O?.track(scene.renderer);
} catch (e) {
  hud.noGL();
  O?.ready();                                  // the numbers still update: the page is up
}
O?.mode(state.quality === 'low');

function setQuality(q, chosen) {
  state.quality = q;
  if (chosen) {
    state.chosen = true;
    if (O) O.setFx(q === 'high' ? 'high' : 'low');
    else try { localStorage.setItem(QUALITY_KEY, q); } catch (_) { /* this visit only */ }
  }
  O?.mode(q === 'low');
  hud.quality(q);
  if (scene) scene.setQuality(q);
}
document.getElementById('quality').addEventListener('click', () => setQuality(state.quality === 'high' ? 'low' : 'high', true));
document.getElementById('replay').addEventListener('click', () => {
  if (state.mode === 'demo') { state.userDemo = false; decide(); } else { state.userDemo = true; startDemo(); }
});
document.getElementById('today').addEventListener('click', () => startToday());
document.getElementById('demo-play').addEventListener('click', () => setPlaying(!state.playing));
const scrub = document.getElementById('scrub');
const scrubTo = () => { if (!state.span) return; setPlaying(false); seekDemo(state.span.from + (+scrub.value / 1000) * (state.span.to - state.span.from)); };
scrub.addEventListener('input', () => { state.dragging = true; scrubTo(); });
scrub.addEventListener('change', () => { scrubTo(); state.dragging = false; });
scrub.addEventListener('pointerup', () => { state.dragging = false; });

function fit() {
  const r = hud.freeRect();
  if (scene) scene.setBand(r);
  ladder.setBand({ y0: r.ly0, y1: r.ly1 });
  const L = document.getElementById('ladder');
  L.style.setProperty('--ladder-y0', Math.round(r.ly0) + 'px');
  L.style.setProperty('--ladder-h', Math.max(0, Math.round(r.ly1 - r.ly0)) + 'px');
}
addEventListener('resize', fit);
if (window.ResizeObserver) { const ro = new ResizeObserver(fit); ro.observe(document.getElementById('top')); ro.observe(document.getElementById('dock')); }

// ------------------------------------------------------------------ the world in
/** A new World on screen. Lightning only for sweeps between two Worlds of the same source (not on a switch). */
function show(w, mode) {
  const first = !state.world || state.mode !== mode;
  state.world = w;
  state.mode = mode;
  if (scene) scene.setWorld(w, { strikes: !first });
  hud.render(w);
  ribbon.render(ribbonOf(w.log, w.t));
  chip();
  hud.tick(nowS());
  postCard();
}

/** The source chip, with the data's age as of now. */
function chip() {
  const w = state.world;
  if (!w) return;
  hud.mode(state.mode, state.mode === 'demo' ? w : { ...w, age_s: Math.max(0, Math.round(Date.now() / 1000 - w.t)) },
    { day: state.demo && (state.demo.today ? 'TODAY' : state.demo.day), canLeave: !!(state.live || state.site) });
  document.getElementById('today').hidden = state.mode === 'demo' || !state.canToday;
}

/** The freshest real world, or the demo when there is none (or the owner asked for the replay). */
function decide() {
  const now = Date.now() / 1000;
  const cands = [state.live, state.site].filter(Boolean).map((d) => normalize(d, now)).filter(Boolean);
  if (state.userDemo || !cands.length) return state.mode === 'demo' ? null : startDemo();
  const w = cands.sort((a, b) => b.t - a.t)[0];
  if (w.src === 'live') {
    const bars = (state.site && state.site.bars) || [];
    const hist = state.history.filter((h) => !bars.length || h[0] > bars[bars.length - 1][0]);
    w.bars = [...bars, ...hist];
  }
  state.canToday = !!todayFx(w, state.site && state.site.ohlc, state.history);
  show(w, w.age_s > FRESH_S ? 'stale' : w.src);
}

async function pollLive(force) {
  if (!force && document.hidden) return;
  try {
    const { j, every } = await fetchLive(state.gate);
    state.every = every;
    if (!state.live || j.t !== state.live.t) {
      state.live = j;
      if (Number.isFinite(+j.price)) state.history = [...state.history, [+j.t, +j.price]].slice(-240);
    }
  } catch (_) { state.every = 60; }
}

async function pollSite() {
  const s = await fetchSite();
  if (s) state.site = s;
  state.siteAt = Date.now();
}

async function refresh(force) {
  if (!force && document.hidden) return;
  await Promise.all([pollLive(force), force || Date.now() - (state.siteAt || 0) > SITE_EVERY_S * 1000 ? pollSite() : null]);
  decide();
}

let timer = 0;
function loop() { clearTimeout(timer); timer = setTimeout(async () => { await refresh(false); loop(); }, state.every * 1000); }
let lastFocus = 0;
document.addEventListener('visibilitychange', () => {
  if (document.hidden || Date.now() - lastFocus < 10000) return;
  lastFocus = Date.now();
  refresh(true).then(loop);
});

// ------------------------------------------------------------------ the demo (a real day replayed)
async function startDemo() {
  try {
    if (!state.fixture) state.fixture = await loadDemo();
  } catch (_) { return; }
  play(state.fixture);
}

/** Today's session, rebuilt from the live World, replayed from the 18:00 open to now (the scrubber walks it). */
function startToday() {
  const fx = todayFx(state.world, state.site && state.site.ohlc, state.history);
  if (!fx) return;
  state.userDemo = true;
  play(fx);
}

function play(fx) {
  if (state.demo !== fx) { state.demo = fx; state.span = span(fx); state.demoT = state.span.from; }
  state.mode = 'demo';
  state.world = null;
  setPlaying(true);
  demoStep();
}

function setPlaying(on) {
  state.playing = !!on;
  hud.playing(state.playing);
}

function seekDemo(t) {
  state.demoT = Math.max(state.span.from, Math.min(state.span.to, t));
  state.world = null;                                   // a jump: no lightning for the levels skipped over
  demoStep();
}

function demoStep() {
  const w = normalize(docAt(state.demo, state.demoT));
  if (w) show(w, 'demo');
  hud.demoProgress(state.demoT, state.span, state.dragging);
}

function demoAdvance(dt) {
  if (!state.playing) return;
  if (state.demoT >= state.span.to) {
    state.hold += dt;
    if (state.hold < 3) return;
    state.hold = 0;
    state.demoT = state.span.from;
    state.world = null;
    return demoStep();
  }
  const slow = state.span.slow.some(([a, b]) => state.demoT >= a && state.demoT < b);
  state.demoT = Math.min(state.span.to, state.demoT + dt * (slow ? 240 : 900));
  if (performance.now() - state.lastDemoDoc > 90) { state.lastDemoDoc = performance.now(); demoStep(); }
}

// ------------------------------------------------------------------ Jarvis's live card (when Jarvis frames this page)
function postCard() {
  if (window.parent === window || !state.world) return;
  const w = state.world, live = state.mode === 'live' || state.mode === 'site';
  const card = {
    v: 1, name: 'Oracle', theme: THEME, open: '#',
    status: live ? { level: 'ok', label: `Watching · ${w.stage.label}`.slice(0, 48) }
      : state.mode === 'stale' ? { level: 'warn', label: 'Last seen: the PC is quiet' } : { level: 'off', label: 'Demo replay' },
    kpis: [{ label: 'NQ', value: w.price == null ? '–' : w.price.toFixed(2) }, { label: 'Stage', value: (w.stage.label || '–').slice(0, 24) },
      { label: 'P&L today', value: usd(w.pnlNow, true) }],
    lines: [String(w.stage.waiting || '').replace(/\s+/g, ' ').slice(0, 120)].filter(Boolean),
  };
  const key = JSON.stringify(card);
  if (key === state.card) return;
  state.card = key;
  try { window.parent.postMessage({ jarvis: 1, href: location.href, card: { ...card, t: Math.round(Date.now() / 1000) } }, location.origin); } catch (_) { /* not Jarvis */ }
}

// ------------------------------------------------------------------ the frame loop
const perf = { frames: 0, t: 0, slow: 0 };
let last = performance.now(), lastDraw = 0, lastTick = 0;
function frame(ts) {
  requestAnimationFrame(frame);
  if (O ? O.hidden() : document.hidden) { last = ts; return; }       // hidden tab: no frame (the battery)
  const dt = Math.min(0.1, (ts - last) / 1000);
  last = ts;
  if (state.mode === 'demo' && state.demo) demoAdvance(dt);
  if (ts - lastTick > 1000) { lastTick = ts; hud.tick(nowS()); if (state.mode !== 'demo') chip(); }
  if (!scene || (reduced && ts - lastDraw < 100)) return;
  scene.frame(nowS(), (ts - lastDraw) / 1000);
  ladder.frame((p) => scene.screenY(p), ...scene.range(), state.world);
  lastDraw = ts;
  autoLite(dt);
}
/** Two slow 2-second windows in a row on HD (and no saved choice): LITE, once. */
function autoLite(dt) {
  perf.frames++;
  perf.t += dt;
  if (perf.t < 2) return;
  state.fps = Math.round(perf.frames / perf.t);
  perf.slow = state.fps < 40 ? perf.slow + 1 : 0;
  perf.frames = perf.t = 0;
  if (perf.slow >= 2 && state.quality === 'high' && !state.chosen && !reduced) setQuality('low', false);
}

// ------------------------------------------------------------------ themes (OLYMPUS)
/** An OLYMPUS theme's tokens ({accent, bg} or the CSS names --oly-accent / --bg) onto the HUD and the 3D column. */
function applyTheme(tokens) {
  const t = tokens || {}, root = document.documentElement.style;
  const accent = t.accent || t['--oly-accent'] || t['--accent'], bg = t.bg || t.background || t['--bg'];
  const hexOk = (c) => typeof c === 'string' && /^#[0-9a-f]{6}$/i.test(c);
  if (hexOk(accent)) {
    root.setProperty('--accent', accent);
    root.setProperty('--accent-rgb', [1, 3, 5].map((i) => parseInt(accent.substr(i, 2), 16)).join(', '));
  }
  if (hexOk(bg)) root.setProperty('--bg', bg);
  if (scene) scene.applyTheme(hexOk(accent) ? accent : null, hexOk(bg) ? bg : null);
  return { accent: hexOk(accent) ? accent : null, bg: hexOk(bg) ? bg : null };
}
const KIT = O || window.Olympus || null;
if (KIT && typeof KIT.onTheme === 'function') KIT.onTheme((tk) => applyTheme(tk));
if (KIT && typeof KIT.theme === 'function') { try { const tk = KIT.theme(); if (tk && typeof tk === 'object') applyTheme(tk); } catch (_) { /* no theme */ } }

// ------------------------------------------------------------------ boot
window.oracle = {
  get mode() { return state.mode; },
  get world() { return state.world; },
  get quality() { return state.quality; },
  get fps() { return state.fps; },
  get strikes() { return scene ? scene.market.strikes : 0; },
  get constellation() { return scene ? [...scene.sky.stars3.states] : []; },
  get events() { return ribbonOf(state.world && state.world.log, state.world && state.world.t); },
  get ladder() { return [...document.querySelectorAll('#ladder > div')].filter((e) => e.style.visibility === 'visible').map((e) => e.textContent); },
  get canToday() { return state.canToday; },
  refresh: () => refresh(true),
  applyTheme,
  today: () => startToday(),
  demo: {
    get t() { return state.demoT; },
    get span() { return state.span; },
    get today() { return !!(state.demo && state.demo.today); },
    pause() { setPlaying(false); },
    play() { setPlaying(true); },
    seek(t) { state.demoT = t; demoStep(); },
  },
};

(async () => {
  try { await Promise.race([document.fonts.load('600 44px Rajdhani'), new Promise((r) => setTimeout(r, 1500))]); } catch (_) { /* system font */ }
  if (forced) await startDemo();
  else await refresh(true);
  loop();
  requestAnimationFrame(frame);
  document.body.dataset.ready = '1';
})();
