// ARGUS: the watchtower. A sphere of a hundred eyes; each eye belongs to one health light and opens green (fine), amber (look)
// or red (act); grey eyes rest. All the words and rules come from arguscore.js; this file is the screen and the 3D.
// 3D goes through the OLYMPUS render core (tone mapping, environment light, bloom, anti-aliasing) and follows OLYMPUS.fx() tiers.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { metal, glass, neon, starfield } from '../olympus/materials.js';
import * as CORE from './arguscore.js';
import { APPS, analyze, cardOf } from './arguscore.js';

const O = window.OLYMPUS || null;
const Q = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
const KEY = 'argus.v1';
const N_EYES = 100;
const COLOR = { ok: '#46d79a', warn: '#f5b84a', bad: '#ff4d5e', idle: '#6b7690' };
const GROUPS = { bots: 'THE BOTS', pc: 'THE PC', feed: 'PRICES AND NINJATRADER', pipes: 'THE CLOUD', rules: 'MFFU RULES AND MONEY', apps: 'OLYMPUS APPS' };
const S = { R: null, tab: 'fix', sel: null, offline: false, asOf: null, errors: [], room: null, loaded: false, open: new Set() };

const T0 = Date.now(), BASE = (() => { const q = Q.get('now'); const d = q ? new Date(q) : null; return d && !Number.isNaN(+d) ? +d : T0; })();
const nowS = () => (BASE + (Date.now() - T0)) / 1000;
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hm = (t) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short' }).format(new Date(t * 1000)) + ' ET';

// ------------------------------------------------------------------------------------------------ data (read only, with a copy for offline)
async function getJson(url, ms = 6000) {
  try {
    const ac = typeof AbortController === 'function' ? new AbortController() : null; const tm = ac ? setTimeout(() => ac.abort(), ms) : 0;
    const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); clearTimeout(tm);
    return r.ok ? await r.json() : null;
  } catch (_) { return null; }
}
const keep = (o, ks) => { const r = {}; for (const k of ks) if (o && o[k] !== undefined) r[k] = o[k]; return r; };
/** only the parts of home.json / data.json the lights read (keeps the offline copy small) */
function slim(h) {
  if (!h || typeof h !== 'object') return null;
  const b = h.board && typeof h.board === 'object' ? h.board : {}, pc = h.live && h.live.pc && typeof h.live.pc === 'object' ? h.live.pc : {};
  const acct = (a) => (a && typeof a === 'object' ? keep(a, ['status', 'blocks', 'quiet_days', 'room', 'mll', 'floor', 'eval_start', 'error']) : a);
  return { built: h.built, live: { last_run: h.live && h.live.last_run, pc: { running: pc.running, health: { running: pc.health && pc.health.running, account: pc.health && pc.health.account && keep(pc.health.account, ['armed']) } } },
    board: { data_t: b.data_t, running: b.running, real: { trades: (b.real && Array.isArray(b.real.trades) ? b.real.trades : []).map((t) => ({ acct: t.acct, day: t.day })).slice(0, 60) }, lit: acct(b.lit), atlas: acct(b.atlas), health: b.health && { items: b.health.items } } };
}
function save(snap) { try { localStorage.setItem(KEY, JSON.stringify(snap)); } catch (_) { /* private mode */ } }
function load() { try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); return s && s.home ? s : null; } catch (_) { return null; } }

async function fetchAll() {
  let home = await getJson('../home.json'); if (!home || !home.board) { const d = await getJson('../data.json'); home = d || home; }
  const cronos = await getJson('../cronos/status.json');
  const got = await Promise.all(APPS.map(([id]) => getJson(`../${id}/jarvis.json`, 5000)));
  const cards = {}; APPS.forEach(([id], i) => { cards[id] = got[i]; });
  if (home && typeof home === 'object') {
    const snap = { saved: nowS(), home: slim(home), cronos: cronos, cards };
    save(snap);
    return { ...snap, offline: false };
  }
  const c = load();
  if (c) return { ...c, offline: true };
  return { saved: null, home: null, cronos, cards, offline: true };
}

// ------------------------------------------------------------------------------------------------ the screen
function row(e, i) {
  return `<button type="button" class="fixrow ${e.level}${S.sel === e.id ? ' sel' : ''}" data-light="${esc(e.id)}"><span class="num">${i + 1}</span><span class="t"><b>${esc(e.label)}: ${esc(e.value)}</b>`
    + `<span class="w">${esc(e.fix || e.detail)}</span><span class="d">${esc(e.detail)}</span></span></button>`;
}
function lrow(e) {
  return `<button type="button" class="lrow ${e.level}${S.sel === e.id ? ' sel' : ''}${S.open.has(e.id) ? ' open' : ''}" data-light="${esc(e.id)}" aria-expanded="${S.open.has(e.id)}"><i class="dot"></i>`
    + `<span class="t"><b>${esc(e.label)}</b><span class="more">${esc(e.detail)}${e.fix ? ' <br>Do this: ' + esc(e.fix) : ''}</span></span><span class="v">${esc(e.value)}</span></button>`;
}
function paint() {
  const R = S.R; if (!R) return;
  const v = R.verdict;
  $('vk').textContent = v.word.toUpperCase();
  $('vs').textContent = R.hasData ? `${R.counts.bad} red · ${R.counts.warn} amber · ${R.counts.ok} green` : '';
  $('verdict').dataset.level = v.level;
  $('vline').textContent = (S.offline && R.hasData ? 'Offline, as of ' + hm(S.asOf) + '. ' : '') + v.line;
  $('fixN').textContent = String(R.fix.length);
  $('offtag').hidden = !S.offline;
  $('sub').textContent = !R.hasData ? 'No dashboard data yet.' : S.offline ? `Offline. Showing what I saw at ${hm(S.asOf)}.` : `${R.eyes.length} lights, ${N_EYES} eyes, checked ${hm(nowS())}.`;
  $('p-fix').innerHTML = R.fix.length ? R.fix.map(row).join('') : `<p class="empty">${R.hasData ? 'Nothing to fix. Every light that matters is green.' : 'Waiting for data.'}</p>`;
  const groups = {}; for (const e of R.eyes) (groups[e.group] = groups[e.group] || []).push(e);
  $('p-all').innerHTML = Object.keys(GROUPS).filter((g) => groups[g]).map((g) => `<p class="grp">${GROUPS[g]}</p>${groups[g].map(lrow).join('')}`).join('');
  document.documentElement.dataset.argus = v.level;
  if (S.room) S.room.set(R);
}
function setTab(t) {
  S.tab = t === 'all' ? 'all' : 'fix';
  $('p-fix').hidden = S.tab !== 'fix'; $('p-all').hidden = S.tab !== 'all';
  document.querySelectorAll('#tabs button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.tab === S.tab)));
}
function select(id, fromEye) {
  const e = S.R && S.R.eyes.find((x) => x.id === id);
  S.sel = e ? id : null;
  const pick = $('pick');
  if (e) { pick.hidden = false; pick.innerHTML = `<b>${esc(e.label)}</b> · ${esc(e.value)}`; if (fromEye) { S.open.add(id); setTab('all'); } } else pick.hidden = true;
  paint();
  if (e && fromEye) { const el = document.querySelector(`#p-all [data-light="${CSS.escape(id)}"]`); if (el) el.scrollIntoView({ block: 'nearest' }); }
  if (S.room) S.room.focus(S.sel);
}
function bind() {
  document.querySelectorAll('#tabs button').forEach((b) => b.addEventListener('click', () => { setTab(b.dataset.tab); location.hash = b.dataset.tab === 'all' ? '#all' : '#fix'; }));
  $('sheet').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-light]'); if (!b) return;
    const id = b.dataset.light;
    if (b.classList.contains('lrow')) { if (S.open.has(id)) S.open.delete(id); else S.open.add(id); }
    select(S.sel === id && b.classList.contains('fixrow') ? null : id, false);
  });
  addEventListener('hashchange', route);
}
function route() { setTab({ all: 'all', lights: 'all', fix: 'fix' }[location.hash.slice(1)] || 'fix'); }

// ------------------------------------------------------------------------------------------------ the 3D sphere of eyes
const R_SPHERE = 2.0;
const hash = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const easeOut = (x) => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3);

class Room {
  constructor(canvas) {
    this.canvas = canvas;
    this.camera = new THREE.PerspectiveCamera(46, 1, 0.1, 200);
    this.scene = new THREE.Scene();
    this.rc = createRenderer({ canvas, scene: this.scene, camera: this.camera, env: 'night', exposure: 1.05, maxDpr: 2 });   // quality follows OLYMPUS.fx()
    this.fx = O ? O.fx() : 'high';
    this.yaw = 0.5; this.pitch = 0.18; this.t = 0; this.last = performance.now(); this.dirty = true; this.frames = [];
    this.user = 0; this.target = null; this.lights = []; this.owner = new Int16Array(N_EYES); this.levels = new Array(N_EYES).fill('idle');
    this.color = new THREE.Color(); this.pulse = new Float32Array(N_EYES);
    this.build();
    addEventListener('resize', () => { this.dirty = true; });
    this.input(canvas);
    if (O && O.onFx) O.onFx(() => { this.fx = O.fx(); this.dirty = true; this.applyTier(); });
  }
  reduced() { return O ? O.reduced() : !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches); }
  build() {
    const S3 = this.scene;
    S3.add(new THREE.HemisphereLight(0x9fc8ff, 0x0a1022, 0.9));
    const key = new THREE.DirectionalLight(0xbfe0ff, 2.2); key.position.set(3, 5, 6); S3.add(key);
    this.stars = starfield({ count: 900, radius: 60 }); S3.add(this.stars);
    this.orb = new THREE.Group(); S3.add(this.orb);
    this.core = new THREE.Mesh(new THREE.SphereGeometry(R_SPHERE - 0.04, 48, 32), metal({ kind: 'gunmetal', color: '#222c44' }));
    this.orb.add(this.core);
    this.shell = new THREE.Mesh(new THREE.SphereGeometry(R_SPHERE + 0.5, 40, 28), glass({ rim: '#3ad7ff', opacity: 0.035, rimStrength: 0.5 }));
    this.orb.add(this.shell);
    this.ring = new THREE.Mesh(new THREE.TorusGeometry(R_SPHERE + 0.75, 0.02, 8, 120), neon({ color: '#ffffff', intensity: 2.2 }));
    this.ring.rotation.x = Math.PI / 2.3; S3.add(this.ring);
    // eyes: sclera (a glossy almond), iris (HDR so it blooms; the colour is per eye), pupil (a slit)
    const sc = new THREE.SphereGeometry(1, 20, 14), iris = new THREE.CircleGeometry(0.42, 28), pup = new THREE.CircleGeometry(0.16, 16);
    const wm = new THREE.MeshPhysicalMaterial({ color: 0xf2f6ff, roughness: 0.22, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.08, envMapIntensity: 1.1 });
    this.sclera = new THREE.InstancedMesh(sc, wm, N_EYES);
    this.iris = new THREE.InstancedMesh(iris, neon({ color: '#ffffff', intensity: 4 }), N_EYES);
    this.pupil = new THREE.InstancedMesh(pup, new THREE.MeshBasicMaterial({ color: 0x02040a }), N_EYES);
    for (const m of [this.sclera, this.iris, this.pupil]) { m.instanceMatrix.setUsage(THREE.DynamicDrawUsage); m.frustumCulled = false; this.orb.add(m); }
    this.iris.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(N_EYES * 3), 3);
    // a Fibonacci sphere: every eye the same distance from its neighbours; local +Z points out of the sphere
    this.pos = []; this.quat = [];
    const ga = Math.PI * (3 - Math.sqrt(5)), m4 = new THREE.Matrix4(), up = new THREE.Vector3(0, 1, 0), zero = new THREE.Vector3();
    for (let i = 0; i < N_EYES; i++) {
      const y = 1 - (2 * (i + 0.5)) / N_EYES, r = Math.sqrt(1 - y * y), a = i * ga;
      const p = new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r);
      this.pos.push(p);
      m4.lookAt(p, zero, up); this.quat.push(new THREE.Quaternion().setFromRotationMatrix(m4));
    }
    this.openAt = this.pos.map((p, i) => 0.25 + (1 - (p.y + 1) / 2) * 1.1 + hash(i) * 0.5);     // opens from the top down
    this.blink = this.pos.map((p, i) => 2 + hash(i + 50) * 7);
    this.applyTier();
  }
  applyTier() {
    const lite = this.fx === 'low' || this.fx === 'off';
    this.stars.visible = !lite; this.shell.visible = !lite;
    this.dirty = true;
  }
  set(R) {
    // the lights, in order; each one owns a band of the sphere (eyes run top to bottom): every eye shows its light's level
    this.lights = R.eyes;
    const L = Math.max(1, R.eyes.length);
    for (let i = 0; i < N_EYES; i++) {
      const k = Math.min(L - 1, Math.floor((i * L) / N_EYES));
      this.owner[i] = k;
      const lv = R.eyes[k] ? R.eyes[k].level : 'idle';
      if (lv !== this.levels[i]) { if (this.levels[i] !== 'idle' || lv !== 'idle') this.pulse[i] = 1; this.levels[i] = lv; }
      this.color.set(COLOR[lv]);
      const d = lv === 'idle' ? 0.35 : 1;
      this.iris.instanceColor.setXYZ(i, this.color.r * d, this.color.g * d, this.color.b * d);
    }
    this.iris.instanceColor.needsUpdate = true;
    this.ring.material.color.set(COLOR[R.verdict.level === 'idle' ? 'idle' : R.verdict.level]).multiplyScalar(2.2);
    this.dirty = true;
  }
  focus(id) {
    if (!id) { this.target = null; return; }
    const k = this.lights.findIndex((e) => e.id === id); if (k < 0) { this.target = null; return; }
    const n = new THREE.Vector3(); let c = 0;
    for (let i = 0; i < N_EYES; i++) if (this.owner[i] === k) { n.add(this.pos[i]); c++; }
    if (!c) return;
    n.divideScalar(c).normalize();
    const rho = Math.hypot(n.x, n.z);
    this.target = { yaw: Math.atan2(-n.x, n.z), pitch: Math.max(-0.9, Math.min(0.9, Math.atan2(n.y, rho))) };
    this.dirty = true;
  }
  input(cv) {
    let down = null, moved = 0;
    cv.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY, yaw: this.yaw, pitch: this.pitch }; moved = 0; cv.setPointerCapture?.(e.pointerId); });
    cv.addEventListener('pointermove', (e) => {
      if (!down) return; moved = Math.max(moved, Math.hypot(e.clientX - down.x, e.clientY - down.y));
      this.yaw = down.yaw + (e.clientX - down.x) * 0.01; this.pitch = Math.max(-1.1, Math.min(1.1, down.pitch + (e.clientY - down.y) * 0.008));
      this.target = null; this.user = this.t + 4; this.dirty = true;
    });
    const up = (e) => { if (down && moved < 6) this.pick(e); down = null; };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', () => { down = null; });
  }
  pick(e) {
    const r = this.canvas.getBoundingClientRect(), ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.orb.updateMatrixWorld(true);
    const rc = new THREE.Raycaster(); rc.setFromCamera(ndc, this.camera);
    const hit = rc.intersectObject(this.sclera, false)[0];
    if (hit && hit.instanceId != null) { const l = this.lights[this.owner[hit.instanceId]]; if (l) select(l.id, true); }
  }
  frame(now) {
    const dt = Math.min(0.1, (now - this.last) / 1000); this.last = now; this.t += dt;
    this.frames.push(dt); if (this.frames.length > 60) this.frames.shift();
    const still = this.reduced();
    if (still && !this.dirty) return;
    // the camera backs off until the whole sphere (and its ring) fits the canvas box
    const asp = this.camera.aspect || 1, half = (46 / 2) * Math.PI / 180, need = (R_SPHERE + 0.95) * 1.04;
    this.camera.position.set(0, 0, Math.max(need / Math.sin(half), need / (Math.tan(half) * asp) + need * 0.6));
    if (this.target) {
      const k = still ? 1 : Math.min(1, dt * 4);
      this.yaw += (this.target.yaw - this.yaw) * k; this.pitch += (this.target.pitch - this.pitch) * k;
      if (still) this.target = null;
    } else if (!still && this.t > this.user) this.yaw += dt * 0.18;
    this.orb.rotation.set(this.pitch, this.yaw, 0);
    this.ring.rotation.z += still ? 0 : dt * 0.25;
    this.stars.update(this.t, this.rc.renderer.getPixelRatio());
    const M = new THREE.Matrix4(), sc = new THREE.Vector3(), p = new THREE.Vector3(), selK = S.sel ? this.lights.findIndex((e) => e.id === S.sel) : -1;
    for (let i = 0; i < N_EYES; i++) {
      const lv = this.levels[i], idle = lv === 'idle';
      let open = still ? (idle ? 0.4 : 1) : easeOut((this.t - this.openAt[i]) / 0.55) * (idle ? 0.4 : 1);
      if (!still && !idle) {                                  // a blink every few seconds
        this.blink[i] -= dt;
        if (this.blink[i] < 0) { if (this.blink[i] < -0.18) this.blink[i] = 3 + hash(i + this.t) * 8; else open *= Math.abs(this.blink[i] + 0.09) / 0.09 * 0.9 + 0.1; }
      }
      if (this.pulse[i] > 0) { this.pulse[i] = Math.max(0, this.pulse[i] - dt * 1.3); if (!still) open *= 1 - 0.7 * Math.sin(this.pulse[i] * Math.PI); }
      const size = (lv === 'bad' ? 1.22 : lv === 'warn' ? 1.1 : 1) * (selK >= 0 && this.owner[i] === selK ? 1.25 : 1) * 0.35;
      const o = Math.max(0.02, open), base = this.pos[i], q = this.quat[i];
      p.copy(base).multiplyScalar(R_SPHERE);
      M.compose(p, q, sc.set(size, size * 0.62 * o, size * 0.45)); this.sclera.setMatrixAt(i, M);
      p.copy(base).multiplyScalar(R_SPHERE + size * 0.45 + 0.012);
      M.compose(p, q, sc.set(size * 1.0, size * Math.min(1, o * 1.45), 1)); this.iris.setMatrixAt(i, M);
      p.copy(base).multiplyScalar(R_SPHERE + size * 0.45 + 0.02);
      M.compose(p, q, sc.set(size * 0.5, size * 1.4 * Math.min(1, o * 1.45), 1)); this.pupil.setMatrixAt(i, M);
    }
    for (const m of [this.sclera, this.iris, this.pupil]) m.instanceMatrix.needsUpdate = true;
    this.rc.render(); this.dirty = false;
  }
  fps() { const a = this.frames; return a.length ? Math.round(a.length / a.reduce((s, x) => s + x, 0)) : 0; }
}

function tick(now) {
  if (S.room && !(O ? O.hidden() : document.hidden)) S.room.frame(now);
  requestAnimationFrame(tick);
}

// ------------------------------------------------------------------------------------------------ run
async function refresh() {
  const d = await fetchAll();
  S.offline = !!d.offline;
  S.asOf = d.offline ? d.saved : null;
  S.R = analyze({ now: d.offline && d.saved ? d.saved : nowS(), home: d.home, cronos: d.cronos, cards: d.cards });
  paint();
  if (window.parent !== window) {
    try { window.parent.postMessage({ jarvis: 1, href: location.href, card: cardOf(S.R, nowS()) }, 'https://demetrades2000-coder.github.io'); } catch (_) { /* no parent */ }
  }
}

async function main() {
  addEventListener('error', (e) => S.errors.push(String(e.message || e)));
  bind(); route();
  try { S.room = new Room($('eyes')); tick(performance.now()); } catch (e) { S.room = null; $('nogl').hidden = false; O?.ready(); }
  window.__argus = { ready: true, CORE, get R() { return S.R; }, get tab() { return S.tab; }, get sel() { return S.sel; }, get offline() { return S.offline; }, errors: S.errors,
    get ready3d() { return !!S.room; }, get fx() { return S.room ? S.room.fx : null; }, get passes() { return S.room ? S.room.rc.passes() : []; }, get yaw() { return S.room ? S.room.yaw : 0; },
    get fps() { return S.room ? S.room.fps() : 0; }, get levels() { return S.room ? S.room.levels.slice() : []; }, get eyes() { return N_EYES; },
    get openness() { return S.room ? Array.from(S.room.sclera.instanceMatrix.array).filter((_, i) => i % 16 === 5) : []; },
    get stats() { return S.room ? S.room.rc.stats() : null; }, pickLight: (id) => select(id, true),
    /** client x / y of eye i when it faces the camera (the tests click it), else null */
    eyeXY: (i) => {
      const r = S.room; if (!r) return null;
      r.orb.updateMatrixWorld(true);
      const p = r.pos[i].clone().multiplyScalar(R_SPHERE).applyMatrix4(r.orb.matrixWorld);
      const n = r.pos[i].clone().transformDirection(r.orb.matrixWorld);
      if (n.dot(r.camera.position.clone().sub(p).normalize()) < 0.55) return null;
      const v = p.project(r.camera), b = r.canvas.getBoundingClientRect();
      return { x: b.left + (v.x + 1) / 2 * b.width, y: b.top + (1 - v.y) / 2 * b.height, owner: r.owner[i] };
    } };
  await refresh();
  window.__argus.siteLoaded = true;
  setInterval(() => { if (!(O ? O.hidden() : document.hidden)) refresh().catch((e) => S.errors.push(String(e))); }, 60000);
}
main().catch((e) => { S.errors.push(String(e)); O?.fail?.('Argus could not start'); });
