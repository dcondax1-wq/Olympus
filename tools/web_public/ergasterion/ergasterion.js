// ERGASTERION page (ES module): the workshop where every worker is visible.
// Reads ./queue.json (tools/ergasterion_build.py), ../home.json, ../money/index.json, the public kalshi.json feed, ../cronos/status.json, ../prometheus/forge.json, ../hephaestus/data.json and ./fixture.json (DEMO when none of the live files is there).
// Read only and paper only: it sends nothing and starts nothing. Text only through textContent / createElementNS. The 3D floor comes from floor.js (optional, loaded by floorload.js); the flat plan is always drawn first.
// window.ERGASTERION is the test hook.
import * as C from './ergasterioncore.js';

const O = window.OLYMPUS || null;
const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
function sv(tag, attrs, text) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = String(text); return e; }
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
const reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
const S = { fixture: null, inputs: null, demo: false, forced: false, workers: [], head: null, events: [], lessons: [], next: [], sel: null, follow: '', view: 'plan', floor: null, ready: false, now: Date.now(), tried: false };
const LAMPC = { working: '#8fa05a', idle: '#4b7a99', stale: '#e0b060', failed: '#c96a4a', sample: '#b8ad98' };

async function getJSON(url, ms) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, timer = ac ? setTimeout(() => ac.abort(), ms || 6000) : 0;
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(timer); }
}
function say(t) { $('status').textContent = t; }
function shortAgo(ms, now) { const a = C.ageH(ms, now); return a == null ? '' : a < 1 ? Math.max(1, Math.round(a * 60)) + ' min' : a < 36 ? Math.round(a) + ' h' : Math.round(a / 24) + ' d'; }

function model() {
  S.now = Date.now();
  const got = !S.forced && S.inputs && C.haveReal(S.inputs);
  S.demo = !got;
  const inp = got ? S.inputs : C.resolveDemo(S.fixture, S.now);
  S.inp = inp;
  S.workers = C.buildWorkers(inp, S.now);
  S.head = C.headline(S.workers);
  S.events = C.events(S.workers, S.now, 12);
  S.lessons = C.lessons(S.workers, S.now, 12);
  S.next = C.suggestions(S.workers, inp.queue, S.now);
}
const byId = (id) => S.workers.find((w) => w.id === id) || null;

// ------------------------------------------------------------------------------------------------ the plan (also the minimap)
function sx(x) { return 180 + x * 14.2; } function sy(z) { return 150 + z * 14.2; }
function drawPlan(svg, mini) {
  clear(svg);
  svg.appendChild(sv('rect', { x: 8, y: 6, width: 344, height: 278, rx: 8, fill: mini ? 'none' : '#2a2318', stroke: '#9c6b3c', 'stroke-width': mini ? 3 : 1.5 }));
  svg.appendChild(sv('rect', { x: 60, y: 10, width: 240, height: 10, rx: 3, fill: '#c8a24a', opacity: 0.85 }));
  if (!mini) {
    svg.appendChild(sv('text', { x: 180, y: 19, 'text-anchor': 'middle', fill: '#1b1610', 'font-size': 8.5, 'font-weight': 700 }, 'Learning board'));
    svg.appendChild(sv('text', { x: 180, y: 281, 'text-anchor': 'middle', fill: '#9a8f7d', 'font-size': 9 }, 'Door'));
  }
  for (const w of S.workers) {
    const x = sx(w.x), y = sy(w.z), sel = S.sel === w.id;
    const g = sv('g', mini ? {} : { role: 'button', tabindex: 0, 'aria-label': w.name + ': ' + C.STATUS_WORD[w.status] + '. Open its card.', 'data-id': w.id });
    if (!mini) g.appendChild(sv('rect', { x: x - 28, y: y - 28, width: 56, height: 50, fill: 'transparent' }));
    g.appendChild(sv('rect', { x: x - 14, y: y + 11, width: 28, height: 3, rx: 1.5, fill: '#9c6b3c' }));
    g.appendChild(sv('circle', { cx: x, cy: y - 4, r: mini ? 9 : 13, fill: '#d9d2c3', stroke: sel ? '#c8a24a' : '#9c6b3c', 'stroke-width': sel ? 3 : 1.5 }));
    g.appendChild(sv('circle', { cx: x, cy: y - 4, r: mini ? 5 : 7, fill: LAMPC[w.status] || LAMPC.stale, stroke: 'rgba(0,0,0,.35)' }));
    if (!mini) g.appendChild(sv('text', { x, y: y + 24, 'text-anchor': 'middle', fill: sel ? '#e0b060' : '#f3ece0', 'font-size': 9.5, 'font-weight': 600 }, w.name.split(' ')[0].slice(0, 9)));
    if (!mini) { g.addEventListener('click', () => open(w.id)); g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(w.id); } }); }
    svg.appendChild(g);
  }
  if (mini && S.floor && S.floor.ok) {
    const p = S.floor.pos(), x = sx(p.x), y = sy(p.z), a = p.yaw;
    svg.appendChild(sv('path', { d: 'M0 -9 L6 7 L0 3 L-6 7 Z', fill: '#f3ece0', transform: 'translate(' + x.toFixed(1) + ' ' + y.toFixed(1) + ') rotate(' + (-a * 180 / Math.PI).toFixed(0) + ')' }));
  }
}

// ------------------------------------------------------------------------------------------------ the cards
function renderHero() {
  const hd = S.head;
  $('heroTitle').textContent = hd.title; $('heroLine').textContent = hd.line + (S.demo ? ' These are example workers, not the real ones.' : ''); $('hero').dataset.level = hd.level;
  const p = $('heroPill'); p.textContent = hd.level === 'ok' ? 'All fine' : hd.level === 'bad' ? 'Needs you' : 'Look once'; p.className = 'pill ' + (hd.level === 'ok' ? 'ok' : hd.level === 'bad' ? 'bad' : 'warn');
}
function lampSpan(s) { const e = h('span', 'lamp'); e.dataset.s = s; e.setAttribute('aria-hidden', 'true'); return e; }
function renderLegend() {
  const ul = $('legend'); clear(ul);
  for (const s of ['working', 'idle', 'stale', 'failed', 'sample']) { const li = h('li'); li.appendChild(lampSpan(s)); li.appendChild(document.createTextNode(C.STATUS_WORD[s] + ': ' + C.STATUS_HELP[s])); ul.appendChild(li); }
}
function renderFollow() {
  const sel = $('follow'); if (sel.options.length > 1) return;
  for (const s of C.STATIONS) { const o = document.createElement('option'); o.value = s.id; o.textContent = s.name; sel.appendChild(o); }
}
function renderWorkers() {
  const ul = $('workers'); clear(ul); let grp = '';
  for (const w of S.workers) {
    if (w.group !== grp) { grp = w.group; ul.appendChild(h('li', 'grp', grp)); }
    const li = h('li'), b = h('button'); b.type = 'button'; b.dataset.id = w.id; b.setAttribute('aria-pressed', String(S.sel === w.id));
    b.setAttribute('aria-label', w.name + ', ' + C.STATUS_WORD[w.status] + '. ' + w.doing);
    const l = lampSpan(w.status); l.style.marginRight = '0';
    const mid = h('span'); mid.appendChild(h('span', 'nm', w.name)); mid.appendChild(h('span', 'sm', w.doing));
    b.appendChild(l); b.appendChild(mid); b.appendChild(h('span', 'pill ' + (w.status === 'working' ? 'ok' : w.status === 'failed' ? 'bad' : w.status === 'stale' ? 'warn' : 'info'), C.STATUS_WORD[w.status]));
    b.addEventListener('click', () => open(w.id)); li.appendChild(b); ul.appendChild(li);
  }
}
function renderSheet() {
  const w = S.sel && byId(S.sel); $('sheet').hidden = !w; if (!w) return;
  $('sheetH').textContent = w.name; const p = $('sheetPill'); p.textContent = C.STATUS_WORD[w.status]; p.className = 'pill ' + (w.status === 'working' ? 'ok' : w.status === 'failed' ? 'bad' : w.status === 'stale' ? 'warn' : 'info');
  $('sheetRole').textContent = w.role + (w.demo ? ' (example data)' : '') + '.';
  $('sheetDoing').textContent = w.doing || 'Nothing recorded.';
  const o = $('sheetOut'); clear(o);
  if (!w.outputs.length) o.appendChild(h('li', '', 'No outputs on record yet.'));
  for (const x of w.outputs) { const li = h('li', '', x.text); if (x.t != null) li.appendChild(h('span', 'when', C.agoText(x.t, S.now))); o.appendChild(li); }
  const L = $('sheetLearn'); clear(L);
  if (!w.learned.length) L.appendChild(h('li', '', 'Nothing learned and written down yet.'));
  for (const x of w.learned) { const li = h('li', '', x.text); li.appendChild(h('span', 'src', (x.d ? x.d + ' · ' : 'undated · ') + 'source: ' + x.src)); L.appendChild(li); }
  $('sheetHealth').textContent = w.health || 'No health note.';
  $('sheetFollow').textContent = S.follow === w.id ? 'Stop following' : 'Follow this worker';
  $('sheetWalk').hidden = !(S.floor && S.floor.ok);
}
function renderTicker() {
  const ul = $('ticker'); clear(ul);
  if (!S.events.length) ul.appendChild(h('li', '', 'No dated events yet. Workers write theirs here when they run.'));
  for (const e of S.events) { const li = h('li'); li.appendChild(h('span', 't', shortAgo(e.t, S.now) + ' ago')); const d = h('span'); d.appendChild(h('b', '', e.name + ': ')); d.appendChild(document.createTextNode(e.text)); li.appendChild(d); ul.appendChild(li); }
}
function renderBoard() {
  const ol = $('lessons'); clear(ol); const wk = S.lessons.filter((l) => l.week).length;
  $('boardNote').textContent = S.lessons.length ? wk + ' of these ' + S.lessons.length + ' are from the last 7 days; the gold bar marks them. Each lesson names the file it came from.' + (S.demo ? ' Example lessons.' : '') : 'No lessons are written down yet.';
  for (const l of S.lessons) {
    const li = h('li'); li.dataset.week = l.week ? '1' : '0';
    li.appendChild(h('b', '', l.name + (l.d ? ' · ' + l.d : ' · undated') + (l.sample ? ' · example' : ''))); li.appendChild(document.createElement('br')); li.appendChild(document.createTextNode(l.text));
    li.appendChild(h('span', 'src', 'source: ' + l.src)); ol.appendChild(li);
  }
}
function renderNext() {
  const ol = $('next'); clear(ol);
  for (const s of S.next) { const li = h('li'); li.appendChild(h('b', '', s.title)); li.appendChild(document.createTextNode(s.why)); li.appendChild(h('span', 'go', 'Next: ' + s.next)); ol.appendChild(li); }
}

function open(id, fromFloor) {
  if (id === 'board') { try { $('boardCard').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' }); } catch (_) { /* nothing */ } return; }
  if (!byId(id)) return;
  S.sel = id; renderSheet(); renderWorkers(); drawPlan($('plan'), false);
  const w = byId(id); say(w.name + ': ' + C.STATUS_WORD[w.status] + '. ' + w.doing);
  try { $('sheet').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'nearest' }); } catch (_) { /* nothing */ }
  if (fromFloor && S.floor && S.floor.ok) S.floor.face(id);
}
function setFollow(id) {
  S.follow = id || ''; $('follow').value = S.follow;
  if (S.floor && S.floor.ok) S.floor.follow(S.follow || null);
  renderSheet();
  if (S.follow) { const w = byId(S.follow); say('Following ' + (w ? w.name : '') + '.'); }
}

function renderScene() {
  drawPlan($('plan'), false); drawPlan($('mini'), true);
  const f = S.floor && S.floor.ok;
  $('stage').hidden = !(f && S.view === '3d'); $('plan').hidden = f && S.view === '3d';
  $('viewBtn').hidden = !f && !S.canTry; $('viewBtn').textContent = S.view === '3d' ? 'Plan view' : 'Walk the floor';
  $('resetBtn').hidden = !(f && S.view === '3d');
  $('sceneNote').textContent = f && S.view === '3d' ? 'First person: drag to look, joystick (or arrow keys) to walk, tap a platform to open its card, or pick a worker to follow.'
    : 'Plan of the floor: tap a worker to open its card.' + (S.canTry ? ' "Walk the floor" shows the 3D version.' : '');
  if (f) S.floor.set(S.workers, S.lessons);
}

function render() {
  model();
  $('demo').hidden = !S.demo; try { $('lite').hidden = !(O && O.lite && O.lite()); } catch (_) { $('lite').hidden = true; }
  renderHero(); renderLegend(); renderFollow(); renderWorkers(); renderSheet(); renderTicker(); renderBoard(); renderNext(); renderScene();
  say(S.head.title + '. ' + S.head.line);
  S.ready = true;
  try { if (O && O.ready) O.ready(); } catch (_) { /* the veil lifts by itself */ }
  tryFloor();
}

// ------------------------------------------------------------------------------------------------ the optional 3D floor
function mountFloor() {
  const M = window.__ergFloor;
  if (!M) return false;
  S.stopMini && clearInterval(S.stopMini);
  $('stage').hidden = false;
  const fl = M.createFloor($('floor3d'), { reduced, stations: C.STATIONS, onPick: (id) => open(id, true) });
  if (!fl || !fl.ok) { $('stage').hidden = true; S.floor = null; S.why = fl && fl.reason; return false; }
  S.floor = fl; S.view = '3d';
  S.stopMini = setInterval(() => { if (!document.hidden && S.view === '3d') drawPlan($('mini'), true); }, 250);
  return true;
}
function tryFloor() {
  if (S.tried || !S.ready) return;
  let lite = false; try { lite = !!(O && O.lite && O.lite()); } catch (_) { /* nothing */ }
  const q = new URLSearchParams(location.search);
  if (lite || q.get('flat') === '1' || q.get('q') === 'low' || q.get('q') === 'off') { S.tried = true; S.canTry = false; renderScene(); return; }
  if (!window.__ergFloor) return;
  S.tried = true; S.canTry = true;
  try { mountFloor(); } catch (_) { S.floor = null; }
  if (!S.floor) S.canTry = false;
  renderScene();
}
window.addEventListener('erg-floor', tryFloor);

function toggleView() {
  if (S.view === '3d') { if (S.floor) { try { S.floor.dispose(); } catch (_) { /* nothing */ } } S.floor = null; S.view = 'plan'; S.canTry = true; clearInterval(S.stopMini); S.follow = ''; $('follow').value = ''; renderScene(); renderSheet(); return; }
  try { mountFloor(); } catch (_) { S.floor = null; }
  if (!S.floor) { S.canTry = false; say('3D is not available on this device; the plan stays.'); }
  renderScene(); renderSheet();
}

// joystick + keyboard (3D only)
function wireControls() {
  const joy = $('joy'), knob = $('knob'); let act = null;
  const setKnob = (dx, dy) => { knob.style.transform = 'translate(' + dx.toFixed(0) + 'px,' + dy.toFixed(0) + 'px)'; };
  const vec = (e) => { const r = joy.getBoundingClientRect(), R = r.width / 2, dx = e.clientX - (r.left + R), dy = e.clientY - (r.top + R), d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / (R - 8)); return { dx: dx / d * k * (R - 8), dy: dy / d * k * (R - 8), k, ux: dx / d * k, uy: dy / d * k }; };
  const push = (v) => { if (!S.floor || !S.floor.ok) return; if (S.follow) setFollow(''); S.floor.move({ fwd: -v.uy, side: v.ux }); if (reduced) S.floor.step(0.06); };
  joy.addEventListener('pointerdown', (e) => { act = e.pointerId; try { joy.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } const v = vec(e); setKnob(v.dx, v.dy); push(v); e.preventDefault(); });
  joy.addEventListener('pointermove', (e) => { if (act !== e.pointerId) return; const v = vec(e); setKnob(v.dx, v.dy); push(v); });
  const end = (e) => { if (act !== e.pointerId) return; act = null; setKnob(0, 0); if (S.floor && S.floor.ok) S.floor.move({ fwd: 0, side: 0 }); };
  joy.addEventListener('pointerup', end); joy.addEventListener('pointercancel', end);
  const keys = new Set();
  const upd = () => { if (!S.floor || !S.floor.ok) return; S.floor.move({ fwd: (keys.has('w') || keys.has('arrowup') ? 1 : 0) - (keys.has('s') || keys.has('arrowdown') ? 1 : 0), side: (keys.has('d') ? 1 : 0) - (keys.has('a') ? 1 : 0) }); if (reduced) S.floor.step(0.1); };
  window.addEventListener('keydown', (e) => {
    if (S.view !== '3d' || !S.floor || !S.floor.ok || /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test((e.target && e.target.tagName) || '')) return;
    const k = String(e.key).toLowerCase();
    if (k === 'arrowleft' || k === 'arrowright') { S.floor.look(k === 'arrowleft' ? -0.07 : 0.07, 0); e.preventDefault(); return; }
    if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown'].includes(k)) { if (S.follow) setFollow(''); keys.add(k); upd(); e.preventDefault(); }
  });
  window.addEventListener('keyup', (e) => { keys.delete(String(e.key).toLowerCase()); upd(); });
  $('viewBtn').addEventListener('click', toggleView);
  $('resetBtn').addEventListener('click', () => { if (S.floor && S.floor.ok) { setFollow(''); S.floor.reset(); } });
  $('follow').addEventListener('change', (e) => setFollow(e.target.value));
  $('sheetFollow').addEventListener('click', () => { if (!S.sel) return; if (!(S.floor && S.floor.ok)) { say('Following needs the 3D floor. Tap "Walk the floor" first.'); return; } setFollow(S.follow === S.sel ? '' : S.sel); });
  $('sheetWalk').addEventListener('click', () => { if (S.floor && S.floor.ok && S.sel) { const w = byId(S.sel); setFollow(''); S.floor.teleport(w.x, w.z + 3.2); S.floor.face(S.sel); say('Standing in front of ' + w.name + '.'); } });
  $('sheetClose').addEventListener('click', () => { S.sel = null; renderSheet(); renderWorkers(); drawPlan($('plan'), false); });
  $('refresh').addEventListener('click', () => { say('Refreshing...'); load().then(render); });
}

async function load() {
  const q = new URLSearchParams(location.search); S.forced = q.get('demo') === '1';
  const [fx, queue, home, money, kalshi, cron, forge, heph] = await Promise.all([getJSON('./fixture.json'), S.forced ? null : getJSON('./queue.json'), S.forced ? null : getJSON('../home.json'), S.forced ? null : getJSON('../money/index.json'),
    S.forced ? null : getJSON('https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json', 5000), S.forced ? null : getJSON('../cronos/status.json'), S.forced ? null : getJSON('../prometheus/forge.json'), S.forced ? null : getJSON('../hephaestus/data.json')]);
  S.fixture = fx; S.inputs = { home, money, kalshi, cron, forge, heph, queue };
}
async function boot() {
  wireControls();
  await load();
  render();
  setInterval(() => { if (!document.hidden) load().then(render); }, 5 * 60 * 1000);
}
window.ERGASTERION = { S, C, ready: () => S.ready, render, open, setFollow, floor: () => S.floor };
boot();
