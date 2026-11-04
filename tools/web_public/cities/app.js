// OLYMPUS Cities: the world map of floating city islands and every city inside it. This file is the page's controller; the
// engine is data-driven (cities.json = the list of city specs, datasets.js = the adapters, generator.js = the generic builder,
// scene.js = the three.js world on the OLYMPUS render core). Adding a city is one entry in cities.json.
//
//   hub    drag to look, pinch to zoom, two fingers to move, tap an island for its card, Enter to land. Tour flies past them all.
//   city   tap a building for its card, Find (search), Top 10, Surprise me, ORBIT / SKIM / DRONE / GRAND cameras, the minimap.
// Read-only: every number is data the site already publishes; nothing here writes, trades or sends anything.
import { $, el, store, clamp, lerp, hash32, rng, cityOfDay, todayStr, fmtField, plain } from './util.js';
import { DATASETS, loadDataset, fieldMap } from './datasets.js';
import { generate, validateSpec, Picker, evalExpr, parseExpr } from './generator.js';
import { Stage, TIERS, BUDGETS } from './scene.js';
import { Rig, makePath } from './rig.js';

const GROUPS = { trading: ['Trading', '#4f8cff'], research: ['Research', '#a68bff'], markets: ['Markets', '#ffc94a'], money: ['Money', '#ff9f43'], life: ['Life', '#39e59a'] };
const GROUP_ORDER = Object.keys(GROUPS);
const ICON = {
  tour: 'M7 4l13 8-13 8z', find: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.5-4.5', surprise: 'M12 2l2.6 6.3L21 9l-5 4.4L17.5 20 12 16.7 6.5 20 8 13.4 3 9l6.4-.7z',
  today: 'M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z', top: 'M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3',
  hub: 'M12 3l9 5v8l-9 5-9-5V8zM12 12l9-4M12 12v9M12 12L3 8',
};
const S = { specs: [], byId: new Map(), fixture: {}, islands: [], hubSel: -1, mode: 'hub', cur: null, busy: false, live: [], real: new Map(), fxDs: new Map(), sumCache: new WeakMap(),
  sheet: null, tour: false, cam: 'orbit', hubPose: null, demo: false, ready: false, errors: [] };
const q = new URLSearchParams(location.search);
S.demo = q.get('demo') === '1';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const O = () => window.OLYMPUS || null;
const sfx = (n) => { try { if (window.OLYMPUS_SFX && !O().reduced()) window.OLYMPUS_SFX.play(n); } catch (e) { /* silent */ } };
const reduced = () => { try { return !!(O() && O().reduced()); } catch (e) { return false; } };

// ------------------------------------------------------------------ data
const getJson = async (url, ms = 14000) => {
  const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null, timer = setTimeout(() => ctl && ctl.abort(), ms);
  try {
    const r = await fetch(url, { cache: 'no-cache', signal: ctl ? ctl.signal : undefined });
    if (!r.ok) throw new Error(url + ' ' + r.status);
    return await r.json();
  } finally { clearTimeout(timer); }
};
const env = {
  get: (url) => (S.demo ? Promise.reject(new Error('demo')) : getJson(url)),
  fixture: {},
  vault: async () => { try { const m = await import('../jarvis/obsidian.js'); return await m.graphSnapshot(); } catch (e) { return null; } },
};
const fxEnv = { get: () => Promise.reject(new Error('sample')), fixture: {} };
const fxCache = new Map(), realCache = new Map();

/** the sample dataset (instant: it ships with the page) */
const sampleDs = (id) => loadDataset(id, fxEnv, fxCache);
/** the real dataset (cached; falls back to the sample when the file does not answer) */
const realDs = async (id) => { const ds = await loadDataset(id, env, realCache); if (!ds.demo) S.real.set(id, ds); return ds; };
const dsNow = (id) => S.real.get(id) || S.fxDs.get(id);

const summary = (spec, ds) => {
  let m = S.sumCache.get(ds);
  if (m && m[spec.id]) return m[spec.id];
  const T = evalExpr(spec.height_by, ds.items), f = parseExpr(spec.district_by).field, d = new Set(ds.items.map((it) => it.f[f]));
  let best = 0;
  for (let i = 1; i < T.length; i++) if (T[i] > T[best]) best = i;
  const hp = parseExpr(spec.height_by.replace(/^-/, '')).field, it = ds.items[best];
  const out = { n: ds.items.length, districts: d.size, top: it ? ds.label(it) : '–', topVal: it ? fmtField(fieldMap(ds)[hp], it.f[hp]) : '–' };
  if (!m) S.sumCache.set(ds, (m = {}));
  m[spec.id] = out;
  return out;
};

// ------------------------------------------------------------------ small UI helpers
const sheet = $('#sheet'), sheetBody = $('#sheetBody'), chips = $('#chips'), dock = $('#dock'), tagEl = $('#tag'), toastEl = $('#toast'), capEl = $('#caption'), canvas = $('#c');
let toastT = 0, capT = 0;
const toast = (msg, ms = 3200) => { toastEl.textContent = msg; toastEl.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => toastEl.classList.remove('on'), ms); };
const caption = (small, text, ms = 4200) => { capEl.replaceChildren(el('small', null, small), document.createTextNode(text)); capEl.classList.add('on'); clearTimeout(capT); capT = setTimeout(() => capEl.classList.remove('on'), ms); };
const svg = (path) => { const n = 'http://www.w3.org/2000/svg', s = document.createElementNS(n, 'svg'), p = document.createElementNS(n, 'path'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '2'); p.setAttribute('d', path); s.appendChild(p); return s; };
const SHORT = { 'Surprise me': 'Wow', 'World map': 'World' };
const tab = (id, label, icon, fn) => { const b = el('button', 'tab'); b.id = id; b.setAttribute('aria-label', label); b.append(svg(icon), document.createTextNode(SHORT[label] || label)); b.addEventListener('click', fn); return b; };
const grid = (rows) => { const g = el('div', 'grid4'); for (const [k, v] of rows) { const d = el('div'); d.append(el('small', null, k), el('b', null, v)); g.append(d); } return g; };
const closeSheet = () => { sheet.classList.remove('on'); const was = S.sheet; S.sheet = null; document.querySelectorAll('.tab').forEach((t) => t.classList.remove('on')); if (S.mode === 'city' && was === 'building') { S.stage.setSelected(-1); tagEl.style.display = 'none'; S.cur.sel = -1; } if (S.mode === 'hub' && was === 'find') hubFilter(null);
  if (S.mode === 'city' && S.cur && S.cur.match) { S.stage.setDim(null); S.cur.match = null; } };
function openSheet(view, title, build) {
  sheet.dataset.view = view; $('#sheetTitle').textContent = title; sheetBody.replaceChildren(); build(sheetBody); sheet.classList.add('on'); sheet.scrollTop = 0; S.sheet = view;
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t.dataset.view === view));
}
$('#sheetX').addEventListener('click', closeSheet);
const setChips = (list) => {
  chips.replaceChildren();
  for (const c of list) {
    const e = el(c.fn ? 'button' : 'span', 'chip' + (c.cls ? ' ' + c.cls : ''));
    if (c.b) { e.append(document.createTextNode(c.label + ' '), el('b', null, c.b)); } else e.textContent = c.label;
    if (c.fn) e.addEventListener('click', c.fn);
    chips.append(e);
  }
};

// ------------------------------------------------------------------ the hub
const hubSlots = () => clamp(Math.floor(S.stage.caps().mini / Math.max(1, S.specs.length)), 24, 260);

function layoutIslands() {
  return S.specs.map((s, i) => {
    const a = i * 2.399963, r = 78 * Math.sqrt(i + 1.6), seed = (hash32(s.id) % 1000) / 1000;
    return { spec: s, i, x: Math.cos(a) * r, z: Math.sin(a) * r, y: Math.sin(i * 1.7) * 16 + (i % 3) * 5, R: 32 + seed * 7, seed, top: s.palette.ground, rim: s.palette.accent };
  });
}

function buildHub() {
  const st = S.stage, slots = hubSlots();
  S.islands = layoutIslands();
  st.buildHub(S.islands.map((s) => ({ x: s.x, y: s.y, z: s.z, R: s.R, top: s.top, rim: s.rim, seed: s.seed })), slots);
  S.slots = slots;
  S.islands.forEach((isl) => miniOf(isl));
  S.hubR = Math.max(...S.islands.map((i) => Math.hypot(i.x, i.z))) + 60;
}
function miniOf(isl) {
  const ds = dsNow(isl.spec.dataset);
  if (!ds || !ds.items.length) { S.stage.setMini(isl.i, null); return; }
  const c = generate(isl.spec, ds, { cap: S.slots });
  S.stage.setMini(isl.i, c);
  isl.n = ds.items.length;
}

async function prefetch() {
  if (S.demo) return;
  const ids = [...new Set(S.specs.map((s) => s.dataset))].filter((id) => !DATASETS[id].remote && !DATASETS[id].vault);
  const rank = (id) => (DATASETS[id].heavy ? 2 : DATASETS[id].from ? 1 : 0);
  ids.sort((a, b) => rank(a) - rank(b));
  for (const id of ids) {
    await sleep(60);
    const ds = await realDs(id);
    if (ds.demo) continue;
    let n = 0;
    for (const isl of S.islands) {
      if (isl.spec.dataset !== id) continue;
      miniOf(isl); S.live[isl.i] = true;
      if (++n % 3 === 0) await sleep(10);           // many cities on one big file: never hold the page for long
    }
    refreshChips();
    if (S.hubSel >= 0 && S.sheet === 'island' && S.islands[S.hubSel].spec.dataset === id) showIsland(S.hubSel);
  }
}

function pickIsland(x, y) {
  const w = canvas.clientWidth, h = canvas.clientHeight, ray = S.stage.ray(x, y, w, h);
  let best = -1, bt = Infinity;
  for (const is of S.islands) {
    const cx = is.x - ray.o.x, cy = is.y + is.R * 0.35 - ray.o.y, cz = is.z - ray.o.z, r = is.R * 1.2;
    const tca = cx * ray.d.x + cy * ray.d.y + cz * ray.d.z;
    if (tca < 0) continue;
    const d2 = cx * cx + cy * cy + cz * cz - tca * tca;
    if (d2 > r * r) continue;
    const t = tca - Math.sqrt(r * r - d2);
    if (t < bt) { bt = t; best = is.i; }
  }
  return best;
}

function dataTag(ds) { return ds.demo ? ['SAMPLE', 'demo'] : ['LIVE DATA', 'live']; }

function showIsland(i) {
  const isl = S.islands[i], spec = isl.spec, ds = dsNow(spec.dataset);
  if (!ds) return;
  const sm = summary(spec, ds), [tag, cls] = dataTag(ds);
  openSheet('island', spec.name, (b) => {
    const gp = GROUPS[spec.group];
    const tags = el('div');
    tags.append(el('span', 'badge ' + cls, tag), el('span', 'badge', gp ? gp[0] : spec.group), el('span', 'badge', spec.landmark.label));
    b.append(tags, el('p', 'note', spec.motto));
    b.append(grid([['Buildings', plain(sm.n)], ['Districts', plain(sm.districts)], ['Tallest', sm.top.slice(0, 34)], ['Its height', sm.topVal]]));
    if (ds.demo) b.append(el('p', 'note', ds.note || 'A small sample stands in until the live file answers.'));
    b.append(el('p', 'note', `Data: ${ds.title} (${ds.source}).`));
    const a = el('div', 'actions'), go = el('button', 'pill go', 'Enter ' + spec.name);
    go.addEventListener('click', () => enterCity(spec.id));
    a.append(go);
    b.append(a);
  });
}

async function selectIsland(i, fly = true) {
  if (S.tour) stopTour();
  S.hubSel = i; S.stage.selectIsland(i);
  const isl = S.islands[i];
  if (fly) S.rig.flyTo({ x: isl.x, y: isl.y + isl.R * 0.35, z: isl.z, dist: isl.R * 4.4, pitch: 0.5 }, 1.0);
  sfx('tick');
  showIsland(i);
  refreshChips();
  const id = isl.spec.dataset;
  if (!S.real.has(id) && !S.demo && (DATASETS[id].remote || DATASETS[id].vault)) {          // the private / remote feeds load when you come near
    const ds = await realDs(id);
    if (!ds.demo) { miniOf(isl); S.live[i] = true; if (S.hubSel === i && S.sheet === 'island') showIsland(i); refreshChips(); }
  }
}

function hubFilter(match) {          // match(spec) -> bool; null clears
  S.hubDim = match ? S.islands.map((i) => !match(i.spec)) : null;
  S.stage.setHubDim(S.hubDim);
}

function openFind() {
  openSheet('find', 'Find a city', (b) => {
    const inp = el('input'); inp.type = 'search'; inp.placeholder = 'Search cities, data, landmarks'; inp.setAttribute('aria-label', 'Search cities');
    const seg = el('div', 'seg'), list = el('ul', 'list');
    let grp = '';
    const draw = () => {
      const t = inp.value.trim().toLowerCase();
      const hit = S.specs.filter((s) => (!grp || s.group === grp) && (!t || `${s.name} ${s.motto} ${s.dataset} ${s.landmark.label} ${s.group}`.toLowerCase().includes(t)));
      list.replaceChildren();
      list.append(el('li', 'count', `${hit.length} of ${S.specs.length} cities`));
      for (const s of hit.slice(0, 60)) {
        const li = el('li'), k = el('span', 'k'), t2 = el('span', 't'), isl = S.islands[S.specs.indexOf(s)], ds = dsNow(s.dataset);
        k.style.background = s.palette.accent; t2.append(document.createTextNode(s.name), el('small', null, s.motto));
        li.append(k, t2, el('span', 'm', ds ? plain(ds.items.length) : ''));
        li.addEventListener('click', () => selectIsland(isl.i));
        list.append(li);
      }
      hubFilter(t || grp ? (s) => hit.includes(s) : null);
    };
    for (const [id, label] of [['', 'All'], ...GROUP_ORDER.map((g) => [g, GROUPS[g][0]])]) {
      const bt = el('button', id === '' ? 'on' : '', label);
      bt.addEventListener('click', () => { grp = id; seg.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === bt)); draw(); });
      seg.append(bt);
    }
    inp.addEventListener('input', draw);
    b.append(inp, seg, list); draw();
    if (!matchMedia('(pointer:coarse)').matches) inp.focus();
  });
}

function openToday() {
  const id = cityOfDay(todayStr(), S.specs.map((s) => s.id)), spec = S.byId.get(id);
  if (!spec) return;
  const ds = dsNow(spec.dataset), sm = ds ? summary(spec, ds) : null;
  openSheet('today', 'City of the day', (b) => {
    b.append(el('h3', null, spec.name), el('p', 'note', spec.motto));
    if (sm) b.append(grid([['Buildings', plain(sm.n)], ['Tallest', sm.top.slice(0, 34)], ['Its height', sm.topVal], ['Landmark', spec.landmark.label]]));
    const a = el('div', 'actions'), go = el('button', 'pill go', 'Enter ' + spec.name), see = el('button', 'pill', 'Show on the map');
    go.addEventListener('click', () => enterCity(spec.id));
    see.addEventListener('click', () => selectIsland(S.specs.indexOf(spec)));
    a.append(go, see); b.append(a, el('p', 'note', 'A new city every day, the same for everyone.'));
  });
}

function surpriseHub() {
  const r = rng(hash32(String(Date.now())));
  const i = Math.floor(r() * S.specs.length);
  caption('SURPRISE', S.specs[i].name, 2400);
  enterCity(S.specs[i].id);
}

// ------------------------------------------------------------------ the hub tour
function startTour() {
  closeSheet();
  const n = S.islands.length, pos = [], look = [];
  S.islands.forEach((is, j) => {
    const a = j * 0.9 + 0.6;
    pos.push([is.x + Math.cos(a) * is.R * 3.2, is.y + is.R * 1.5, is.z + Math.sin(a) * is.R * 3.2]);
    look.push([is.x, is.y + is.R * 0.5, is.z]);
  });
  if (n < 3) return;
  S.tour = true;
  S.rig.follow(makePath(pos, look, true), 62, true, 'tour');
  $('#tourB') && $('#tourB').classList.add('on');
  S.tourT = 0; S.tourLast = -1;
  caption('TOUR', 'Flying past every city. Touch to take over.', 3600);
}
function stopTour() { S.tour = false; S.rig.stopPath(); $('#tourB') && $('#tourB').classList.remove('on'); }
function tourTick(dt) {
  S.tourT += dt;
  if (S.tourT < 0.4) return;
  S.tourT = 0;
  let best = -1, bd = Infinity;
  for (const is of S.islands) { const d = Math.hypot(is.x - S.rig.t.x, is.z - S.rig.t.z) + Math.abs(is.y - S.rig.t.y) * 0.5; if (d < bd) { bd = d; best = is.i; } }
  if (best !== S.tourLast && bd < 60) { S.tourLast = best; S.stage.selectIsland(best); caption('CITY', S.islands[best].spec.name + ': ' + S.islands[best].spec.motto, 3000); }
}

// ------------------------------------------------------------------ entering and leaving a city
const veil = $('#veil');
function showVeil(on, name, sub) {
  if (name) { $('#veilName').textContent = name; $('#veilSub').textContent = sub || ''; }
  veil.classList.toggle('on', on);
}

async function enterCity(id) {
  const spec = S.byId.get(id);
  if (!spec || S.busy) return;
  S.busy = true;
  try {
    if (S.tour) stopTour();
    closeSheet();
    const isl = S.islands.find((i) => i.spec === spec);
    if (S.mode === 'hub') {
      S.hubPose = { x: S.rig.t.x, y: S.rig.t.y, z: S.rig.t.z, dist: S.rig.dist, pitch: S.rig.pitch, yaw: S.rig.yaw };
      if (isl && !reduced()) await Promise.race([S.rig.flyTo({ x: isl.x, y: isl.y + 6, z: isl.z, dist: isl.R * 1.6, pitch: 0.28 }, 0.8), sleep(1400)]);
    }
    showVeil(true, spec.name, spec.motto);
    sfx(spec.sound === 'tick' || spec.sound === 'tap' ? 'portal' : spec.sound);
    await sleep(reduced() ? 20 : 380);
    const ds = await realDs(spec.dataset);
    S.fxDs.set(spec.dataset, S.fxDs.get(spec.dataset) || ds);
    buildCityView(spec, ds);
    showVeil(false);
    S.busy = false;
    if (ds.demo) toast(ds.note || 'Showing a small sample.', 4500);
    else if (S.cur.city.capped) toast(`Showing ${plain(S.cur.city.n)} of ${plain(S.cur.city.total)} (the tier's cap): all the tallest, the rest sampled.`, 4500);
  } catch (e) {
    S.busy = false; showVeil(false);
    S.errors.push(String(e && e.stack || e));
    toast('That city could not be built: ' + (e && e.message ? e.message : e), 5000);
    console.warn('city failed', e);
  }
}

function buildCityView(spec, ds) {
  const st = S.stage, tier = st.caps();
  const city = generate(spec, ds, { cap: tier.cap });
  st.buildCity(spec, city);
  st.look(spec); st.setFogRadius(city.bounds.r); st.show('city');
  const picker = new Picker(city);
  S.cur = { spec, ds, city, picker, f: fieldMap(ds), sel: -1, match: null, base: null };
  S.mode = 'city'; document.body.dataset.mode = 'city';
  $('#title').textContent = spec.name; $('#backB').hidden = false;
  S.rig.limits = { min: 10, max: city.bounds.r * 4 + 260, pmin: 0.05, pmax: 1.52 };
  S.rig.auto = 0.05;
  const far = city.bounds.r * 1.7 + 70;
  S.rig.t.set(0, city.maxH * 0.28, 0);
  const p0 = spec.cam_pitch || (city.layout === 'terrain' ? 0.62 : 0.42);
  S.rig.dist = far; S.rig.pitch = p0 - 0.06; S.rig.yaw = 0; S.rig.fly = null; S.rig.path = null; S.rig.apply();
  S.rig.flyTo({ dist: far * 0.82, pitch: p0, yaw: 0.25 }, reduced() ? 0.01 : 2.4);
  setCam('orbit', true);
  drawMiniBase();
  setDock();
  refreshChips();
  location.hash = spec.id;
  dock.querySelectorAll('.tab').forEach((t) => t.classList.remove('on'));
  caption(spec.landmark.label.toUpperCase(), spec.motto, 4200);
}

async function leaveCity() {
  if (S.mode !== 'city' || S.busy) return;
  S.busy = true;
  closeSheet(); tagEl.style.display = 'none';
  showVeil(true, S.cur.spec.name, '');
  await sleep(reduced() ? 20 : 300);
  S.stage.clearCity(); S.stage.look(null); S.stage.setFogRadius(S.hubR); S.stage.show('hub');
  S.mode = 'hub'; document.body.dataset.mode = 'hub'; S.cur = null;
  $('#title').textContent = 'Cities'; $('#backB').hidden = true;
  S.rig.limits = { min: 50, max: S.hubR * 3, pmin: 0.08, pmax: 1.5 };
  S.rig.stopPath();
  const p = S.hubPose || { x: 0, y: 0, z: 0, dist: S.hubR * 1.15 + 140, pitch: 0.86, yaw: 0.3 };
  Object.assign(S.rig, { dist: p.dist, pitch: p.pitch, yaw: p.yaw }); S.rig.t.set(p.x, p.y, p.z); S.rig.apply();
  S.cam = 'orbit';
  setDock(); refreshChips();
  history.replaceState(null, '', location.pathname + location.search);
  showVeil(false);
  S.busy = false;
  if (S.hubSel >= 0) { S.stage.selectIsland(S.hubSel); showIsland(S.hubSel); }
}

// ------------------------------------------------------------------ inside a city
const itemOf = (k) => S.cur.ds.items[S.cur.city.item[k]];
const heightField = () => parseExpr(S.cur.spec.height_by.replace(/^-/, '')).field;

function selectBuilding(k, fly = true) {
  const C = S.cur, city = C.city, it = itemOf(k), spec = C.spec;
  C.sel = k; S.stage.setSelected(k);
  if (fly) S.rig.flyTo({ x: city.x[k], y: city.h[k] * 0.55, z: city.z[k], dist: Math.max(30, city.w[k] * 6 + city.h[k] * 0.9), pitch: 0.46 }, 0.9);
  sfx('tick');
  const dst = city.districts[city.dist[k]], hf = heightField(), lessCount = (() => { let c = 0; for (let j = 0; j < city.n; j++) if (city.h[j] < city.h[k]) c++; return c; })();
  openSheet('building', C.ds.label(it), (b) => {
    const bd = el('span', 'badge', dst.label);
    bd.style.background = dst.color; bd.style.color = '#0a0a12';
    b.append(bd);
    const v = it.f[hf], big = el('div', 'big'), val = el('span', 'v' + (typeof v === 'number' ? (v > 0 ? ' pos' : v < 0 ? ' neg' : '') : ''), fmtField(C.f[hf], v));
    big.append(val, el('span', 'u', C.f[hf] ? C.f[hf].label : hf));
    b.append(big);
    b.append(grid(spec.card.filter((f) => f !== hf).slice(0, 6).map((f) => [C.f[f].label, fmtField(C.f[f], it.f[f])])));
    b.append(el('p', 'note', `Taller than ${Math.round((100 * lessCount) / Math.max(1, city.n))}% of the ${plain(city.n)} buildings. District ${dst.label}: ${plain(dst.count)} buildings.`));
    if (it.text) b.append(el('p', 'note', String(it.text).slice(0, 400)));
    const a = el('div', 'actions'), close = el('button', 'pill', 'Close'), near = el('button', 'pill', 'Fly closer');
    close.addEventListener('click', closeSheet);
    near.addEventListener('click', () => S.rig.flyTo({ x: city.x[k], y: city.h[k] * 0.6, z: city.z[k], dist: Math.max(18, city.w[k] * 3.4), pitch: 0.4 }, 0.8));
    a.append(near, close); b.append(a);
  });
  const t = $('#tag');
  t.replaceChildren(el('b', null, String(C.ds.label(it)).slice(0, 38)), el('span', null, fmtField(C.f[hf], v0(it, hf))));
}
const v0 = (it, f) => it.f[f];

function openTop() {
  const C = S.cur, city = C.city, hf = heightField();
  const ord = Array.from({ length: city.n }, (_, k) => k).sort((a, b) => city.h[b] - city.h[a] || a - b).slice(0, 10);
  openSheet('top', 'Top 10 tallest', (b) => {
    const ul = el('ul', 'list');
    ord.forEach((k, r) => {
      const it = itemOf(k), li = el('li'), kk = el('span', 'k', r + 1), t = el('span', 't');
      kk.style.background = city.districts[city.dist[k]].color; t.append(document.createTextNode(String(C.ds.label(it)).slice(0, 70)), el('small', null, city.districts[city.dist[k]].label));
      li.append(kk, t, el('span', 'm', fmtField(C.f[hf], it.f[hf])));
      li.addEventListener('click', () => selectBuilding(k));
      ul.append(li);
    });
    b.append(ul);
  });
}

function openCityFind() {
  const C = S.cur, city = C.city;
  openSheet('cfind', 'Find a building', (b) => {
    const inp = el('input'); inp.type = 'search'; inp.placeholder = 'Search ' + C.spec.name; inp.setAttribute('aria-label', 'Search buildings');
    const list = el('ul', 'list');
    const draw = () => {
      const t = inp.value.trim().toLowerCase();
      list.replaceChildren();
      if (!t) { S.stage.setDim(null); C.match = null; list.append(el('li', 'count', `${plain(city.n)} buildings. Type to light up matches.`)); return; }
      const hit = [];
      const m = new Uint8Array(city.n);
      for (let k = 0; k < city.n; k++) {
        const it = itemOf(k);
        if (String(C.ds.label(it)).toLowerCase().includes(t) || city.districts[city.dist[k]].label.toLowerCase().includes(t)) { m[k] = 1; hit.push(k); }
      }
      C.match = m;
      S.stage.setDim((k) => !m[k]);
      hit.sort((a, c) => city.h[c] - city.h[a] || a - c);
      list.append(el('li', 'count', `${plain(hit.length)} match${hit.length === 1 ? '' : 'es'}${hit.length > 40 ? ' (the 40 tallest shown)' : ''}`));
      for (const k of hit.slice(0, 40)) {
        const it = itemOf(k), li = el('li'), kk = el('span', 'k'), tt = el('span', 't');
        kk.style.background = city.districts[city.dist[k]].color;
        tt.append(document.createTextNode(String(C.ds.label(it)).slice(0, 80)), el('small', null, city.districts[city.dist[k]].label));
        li.append(kk, tt, el('span', 'm', fmtField(C.f[heightField()], it.f[heightField()])));
        li.addEventListener('click', () => selectBuilding(k));
        list.append(li);
      }
    };
    inp.addEventListener('input', draw);
    b.append(inp, list); draw();
    if (!matchMedia('(pointer:coarse)').matches) inp.focus();
  });
}

function surpriseCity() {
  const city = S.cur.city, r = rng(hash32(String(Date.now())));
  const k = Math.floor(r() * city.n);
  selectBuilding(k);
  caption('SURPRISE', String(S.cur.ds.label(itemOf(k))).slice(0, 80), 2800);
}

function openRead() {
  const C = S.cur, spec = C ? C.spec : null;
  openSheet('read', spec ? 'How to read ' + spec.name : 'How to read the world', (b) => {
    if (!spec) {
      b.append(el('p', 'note', 'Every island is a miniature of one city. Each city is built from numbers this site already publishes: trades, tested ideas, simulations, notes, bets.'));
      b.append(el('p', 'note', 'Drag to look around, pinch to zoom, use two fingers to move. Tap an island to see its card, then Enter to land. Tour flies past every island. Find searches; Surprise picks one for you; Today is the city of the day.'));
      b.append(el('p', 'note', `${S.specs.length} cities. Adding a city is one entry in cities.json: the generator, the search, the minimap and the cameras come with it.`));
      return;
    }
    const f = C.f, name = (e) => { const p = parseExpr(String(e).replace(/^-/, '')); return (f[p.field] && f[p.field].label) || p.field; };
    const L = [`Each building is one row of "${C.ds.title}" (${C.ds.source}).`, `Height: ${name(spec.height_by)}.`, `Districts: ${name(spec.district_by)}.`,
      `Glowing roof: ${name(spec.glow_by)}.`, `Lit windows: ${name(spec.window_by)}.`,
      { sign: 'Colour: green above zero, red below.', district: 'Colour: one colour per district.', ramp: `Colour: from calm to hot by ${name(spec.color_by.split(':').slice(1).join(':'))}.`, cat: `Colour: by ${name(spec.color_by.split(':').slice(1).join(':'))}.` }[spec.color_by.split(':')[0]]];
    L.push(`Landmark: ${spec.landmark.label}.`);
    if (C.city.capped) L.push(`Showing ${plain(C.city.n)} of ${plain(C.city.total)} buildings (this device's cap): the tallest all stay.`);
    L.forEach((t) => b.append(el('p', 'note', t)));
    b.append(el('p', 'note', 'Tap a building for its card. ORBIT, SKIM, DRONE and GRAND fly the camera for you. The little map flies you anywhere.'));
  });
}

// ------------------------------------------------------------------ cameras
function setCam(mode, quiet) {
  S.cam = mode;
  document.querySelectorAll('#cams button').forEach((b) => b.classList.toggle('on', b.dataset.cam === mode));
  const C = S.cur; if (!C) return;
  const city = C.city, r = city.bounds.r, mH = city.maxH, spd = clamp(r / 150, 0.7, 3.2);
  if (mode === 'orbit') { S.rig.stopPath(); return; }
  let pos = [], look = [], speed = 40 * spd;
  if (mode === 'drone') {
    for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; pos.push([Math.cos(a) * r * 0.95, mH * 1.1 + 55 + Math.sin(i * 1.3) * 12, Math.sin(a) * r * 0.95]); look.push([Math.cos(a + 1.4) * r * 0.12, mH * 0.3, Math.sin(a + 1.4) * r * 0.12]); }
    speed = 52 * spd;
  } else if (mode === 'skim') {
    const ds = city.districts.length >= 3 ? city.districts.slice() : [];
    ds.sort((a, b) => Math.atan2(a.cz, a.cx) - Math.atan2(b.cz, b.cx));
    const n = Math.max(ds.length, 8);
    for (let i = 0; i < n; i++) {
      const d = ds[i % Math.max(1, ds.length)] || null, a = (i / n) * Math.PI * 2, rr = d ? Math.hypot(d.cx, d.cz) : r * 0.55;
      const ang = d ? Math.atan2(d.cz, d.cx) : a;
      pos.push([Math.cos(ang) * (rr + city.pitch * 3), 9 + mH * 0.1, Math.sin(ang) * (rr + city.pitch * 3)]);
      look.push([Math.cos(ang + 0.5) * rr * 0.9, mH * 0.22, Math.sin(ang + 0.5) * rr * 0.9]);
    }
    speed = 30 * spd;
  } else if (mode === 'grand') {
    const lm = city.site;
    pos.push([lm.x + lm.scale * 1.4, lm.scale * 1.2, lm.z + lm.scale * 2.4]); look.push([lm.x, lm.scale * 1.2, lm.z]);
    const top = Array.from({ length: city.n }, (_, k) => k).sort((a, b) => city.h[b] - city.h[a] || a - b).slice(0, 5);
    top.forEach((k) => { const a = Math.atan2(city.z[k], city.x[k]); pos.push([city.x[k] + Math.cos(a) * (city.w[k] * 4 + 28), city.h[k] * 0.7 + 12, city.z[k] + Math.sin(a) * (city.w[k] * 4 + 28)]); look.push([city.x[k], city.h[k] * 0.7, city.z[k]]); });
    speed = 34 * spd;
  }
  if (pos.length < 3) return;
  S.rig.follow(makePath(pos, look, true), speed, true, mode);
  if (!quiet) caption(mode.toUpperCase(), 'Touch to take the camera back.', 2600);
}

// ------------------------------------------------------------------ chips, dock, quality
function refreshChips() {
  if (S.mode === 'hub') {
    const live = S.live.filter(Boolean).length, tid = cityOfDay(todayStr(), S.specs.map((s) => s.id)), t = S.byId.get(tid);
    setChips([{ label: 'cities', b: String(S.specs.length) }, { label: live ? 'live' : 'loading', b: live ? `${live}/${S.specs.length}` : '…', cls: live ? 'live' : '' },
      ...(t ? [{ label: 'Today:', b: t.name }] : [])]);
  } else if (S.cur) {
    const C = S.cur, [tag, cls] = dataTag(C.ds);
    setChips([{ label: tag, cls }, { label: 'buildings', b: plain(C.city.n) + (C.city.capped ? ' of ' + plain(C.city.total) : '') }, { label: 'districts', b: String(C.city.districts.length) },
      { label: GROUPS[C.spec.group] ? GROUPS[C.spec.group][0] : C.spec.group }]);
  }
}
function setDock() {
  dock.replaceChildren();
  const T = (id, label, icon, fn, view) => { const b = tab(id, label, icon, fn); if (view) b.dataset.view = view; dock.append(b); return b; };
  if (S.mode === 'hub') {
    T('tourB', 'Tour', ICON.tour, () => (S.tour ? stopTour() : startTour()));
    T('findB', 'Find', ICON.find, openFind, 'find');
    T('surpriseB', 'Surprise me', ICON.surprise, surpriseHub);
    T('todayB', 'Today', ICON.today, openToday, 'today');
  } else {
    T('hubB', 'World map', ICON.hub, leaveCity);
    T('topB', 'Top 10', ICON.top, openTop, 'top');
    T('cfindB', 'Find', ICON.find, openCityFind, 'cfind');
    T('csurpriseB', 'Surprise me', ICON.surprise, surpriseCity);
    T('creadB', 'Read', 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7.5v.5', openRead, 'read');
  }
}
function qLabel() { const fx = O() ? O().fx() : 'high'; return fx === 'low' || fx === 'off' ? 'LITE' : 'HD'; }
$('#qB').addEventListener('click', () => {
  const o = O(); if (!o || !o.setFx) return;
  o.setFx(qLabel() === 'HD' ? 'low' : 'high');
  $('#qB').textContent = qLabel(); toast(qLabel() === 'HD' ? 'HD: full effects.' : 'LITE: lighter, for a cooler phone.', 2200);
});
$('#readB').addEventListener('click', openRead);
$('#backB').addEventListener('click', leaveCity);
document.querySelectorAll('#cams button').forEach((b) => b.addEventListener('click', () => setCam(b.dataset.cam)));
window.addEventListener('hashchange', () => {
  const id = location.hash.slice(1);
  if (S.mode === 'city' && !id) leaveCity();
  else if (id && S.byId.has(id) && (!S.cur || S.cur.spec.id !== id) && S.ready) enterCity(id);
});

// ------------------------------------------------------------------ minimap
const mini = $('#mini'), mg = mini.getContext('2d');
let miniBase = null, miniScale = 1;
function drawMiniBase() {
  const city = S.cur.city, half = Math.max(Math.abs(city.bounds.minx), Math.abs(city.bounds.maxx), Math.abs(city.bounds.minz), Math.abs(city.bounds.maxz)) * 1.1 + 10;
  const W = mini.width;
  miniScale = W / (half * 2);
  const c = document.createElement('canvas'); c.width = c.height = W;
  const g = c.getContext('2d');
  g.fillStyle = 'rgba(8,6,18,0.9)'; g.fillRect(0, 0, W, W);
  for (const d of city.districts) {
    g.strokeStyle = d.color; g.globalAlpha = 0.35; g.lineWidth = 1.2;
    if (['districts', 'clock', 'calendar'].includes(city.layout)) g.strokeRect((d.x0 + half) * miniScale, (d.z0 + half) * miniScale, (d.x1 - d.x0) * miniScale, (d.z1 - d.z0) * miniScale);
  }
  g.globalAlpha = 1;
  const step = Math.max(1, Math.floor(city.n / 6000));
  for (let k = 0; k < city.n; k += step) {
    const r = Math.max(1.1, city.w[k] * miniScale * 0.8), t = 0.35 + 0.65 * Math.min(1, city.h[k] / Math.max(1, city.maxH));
    g.fillStyle = `rgb(${Math.round(city.col[k * 3] * 255 * t)},${Math.round(city.col[k * 3 + 1] * 255 * t)},${Math.round(city.col[k * 3 + 2] * 255 * t)})`;
    g.fillRect((city.x[k] + half) * miniScale - r / 2, (city.z[k] + half) * miniScale - r / 2, r, r);
  }
  g.fillStyle = '#fff'; g.beginPath(); g.arc((city.site.x + half) * miniScale, (city.site.z + half) * miniScale, 3.5, 0, 7); g.fill();
  miniBase = { c, half };
}
function drawMini() {
  if (!miniBase) return;
  const W = mini.width, { half } = miniBase, cam = S.stage.camera.position, t = S.rig.t;
  mg.clearRect(0, 0, W, W); mg.drawImage(miniBase.c, 0, 0);
  const cx = (cam.x + half) * miniScale, cz = (cam.z + half) * miniScale, tx = (t.x + half) * miniScale, tz = (t.z + half) * miniScale;
  mg.strokeStyle = '#ffc94a'; mg.fillStyle = '#ffc94a'; mg.lineWidth = 2;
  mg.beginPath(); mg.moveTo(cx, cz); mg.lineTo(tx, tz); mg.stroke();
  mg.beginPath(); mg.arc(cx, cz, 5, 0, 7); mg.fill();
}
mini.addEventListener('click', (e) => {
  if (!miniBase || !S.cur) return;
  const r = mini.getBoundingClientRect(), fx = ((e.clientX - r.left) / r.width) * mini.width, fz = ((e.clientY - r.top) / r.height) * mini.height;
  const x = fx / miniScale - miniBase.half, z = fz / miniScale - miniBase.half;
  S.rig.flyTo({ x, y: S.cur.city.maxH * 0.25, z, dist: clamp(S.rig.dist, 40, 220), pitch: 0.5 }, 1.1);
  setCam('orbit', true);
});

// ------------------------------------------------------------------ labels
const labelEls = Array.from({ length: 8 }, () => { const i = el('i'); $('#labels').append(i); return i; });
function updateLabels(frame) {
  if (frame % 3) return;
  const w = canvas.clientWidth, h = canvas.clientHeight, st = S.stage, cand = [];
  if (S.mode === 'hub') {
    for (const is of S.islands) {
      const p = st.project(is.x, is.y + is.R * 1.5, is.z, w, h);
      if (!p.on || p.x < -20 || p.x > w + 20 || p.y < 90 || p.y > h - 120) continue;
      const dist = Math.hypot(p.x - w / 2, (p.y - h / 2) * 1.2) + (is.i === S.hubSel ? -9999 : 0);
      cand.push({ p, text: is.spec.name, sel: is.i === S.hubSel, dist });
    }
  } else if (S.cur && S.cur.city.districts.length > 1 && ['districts', 'clock', 'calendar'].includes(S.cur.city.layout)) {
    for (const d of S.cur.city.districts) {
      const p = st.project(d.cx, d.top + 6, d.cz, w, h);
      if (!p.on || p.x < 10 || p.x > w - 10 || p.y < 100 || p.y > h - 130) continue;
      cand.push({ p, text: d.label, sel: false, dist: p.z * 1000 });
    }
  }
  cand.sort((a, b) => a.dist - b.dist);
  labelEls.forEach((e, i) => {
    const c = cand[i];
    if (!c) { e.style.display = 'none'; return; }
    e.style.display = 'block'; e.textContent = c.text; e.classList.toggle('sel', c.sel);
    e.style.transform = `translate(${Math.round(c.p.x)}px,${Math.round(c.p.y)}px) translate(-50%,-100%)`;
  });
}
function updateTag() {
  if (S.mode !== 'city' || !S.cur || S.cur.sel < 0) { tagEl.style.display = 'none'; return; }
  const C = S.cur, k = C.sel, p = S.stage.project(C.city.x[k], C.city.h[k] + 2, C.city.z[k], canvas.clientWidth, canvas.clientHeight);
  if (!p.on || p.y < 100) { tagEl.style.display = 'none'; return; }
  tagEl.style.display = 'block'; tagEl.style.transform = `translate(${Math.round(clamp(p.x, 60, canvas.clientWidth - 60))}px,${Math.round(p.y)}px) translate(-50%,-115%)`;
}

// ------------------------------------------------------------------ input
function onTap(x, y) {
  if (S.busy) return;
  if (S.mode === 'hub') {
    const i = pickIsland(x, y);
    if (i >= 0) selectIsland(i); else { closeSheet(); S.hubSel = -1; S.stage.selectIsland(-1); refreshChips(); }
    return;
  }
  const C = S.cur; if (!C) return;
  const ray = S.stage.ray(x, y, canvas.clientWidth, canvas.clientHeight), r = C.picker.pick(ray.o, ray.d);
  if (r.index >= 0) selectBuilding(r.index); else closeSheet();
}

// ------------------------------------------------------------------ the frame loop
let frame = 0;
let shiftX = 0, shiftY = 0;
function viewShift(dt) {           // keep what you tapped above the sheet: the view window slides while a sheet is open
  const w = canvas.clientWidth, h = canvas.clientHeight, land = w > h * 1.1, open = sheet.classList.contains('on') && !S.tour;
  const ty = open && !land ? h * 0.17 : 0, tx = open && land ? -w * 0.2 : 0, k = Math.min(1, dt * 7);
  shiftY += (ty - shiftY) * k; shiftX += (tx - shiftX) * k;
  if (Math.abs(shiftY) > 0.5 || Math.abs(shiftX) > 0.5) S.stage.camera.setViewOffset(w, h, shiftX, shiftY, w, h);
  else if (S.stage.camera.view && S.stage.camera.view.enabled) S.stage.camera.clearViewOffset();
  else return;
  S.stage.camera.updateProjectionMatrix();
}
function loop(dt, t) {
  frame++;
  S.rig.update(dt);
  viewShift(dt);
  S.stage.update(dt, t);
  if (S.tour) tourTick(dt);
  updateLabels(frame);
  if (S.mode === 'city') { updateTag(); if (frame % 4 === 0) drawMini(); }
}

// ------------------------------------------------------------------ boot
function fallbackList(why) {
  $('#loading').remove();
  const box = el('div', 'fallback');
  box.append(el('p', 'note', why + ' The 3D world needs WebGL. The cities are still here:'));
  for (const s of S.specs) { const p = el('p', 'note'); p.append(el('b', null, s.name + ': '), document.createTextNode(s.motto)); box.append(p); }
  document.body.append(box);
  document.body.dataset.ready = 'fallback';
}

async function boot() {
  let cfg, fx;
  try { [cfg, fx] = await Promise.all([getJson('./cities.json'), getJson('./fixture.json')]); } catch (e) { $('#loading').textContent = 'Could not load the city list.'; throw e; }
  for (const s of cfg.cities) {
    const errs = validateSpec(s, DATASETS);
    if (errs.length) { console.warn('city skipped', s.id, errs); continue; }
    S.specs.push(s); S.byId.set(s.id, s);
  }
  env.fixture = fx; fxEnv.fixture = fx;
  let stage;
  try { stage = new Stage(canvas, { onTier: (lv) => retier(lv) }); } catch (e) { fallbackList('3D is not available here.'); return; }
  S.stage = stage;
  S.rig = new Rig(stage.camera, canvas, { onTap, onFreed: () => { if (S.tour) { S.tour = false; $('#tourB') && $('#tourB').classList.remove('on'); } if (S.mode === 'city') setCam('orbit', true); } });
  await Promise.all([...new Set(S.specs.map((s) => s.dataset))].map(async (id) => { S.fxDs.set(id, await sampleDs(id)); }));
  S.live = S.specs.map(() => false);
  stage.look(null);
  buildHub();
  stage.setFogRadius(S.hubR);
  stage.show('hub');
  S.rig.limits = { min: 50, max: S.hubR * 3, pmin: 0.08, pmax: 1.5 };
  S.rig.t.set(0, 0, 0); S.rig.dist = S.hubR * 1.15 + 140; S.rig.pitch = 0.86; S.rig.yaw = 0.3; S.rig.auto = 0.03; S.rig.apply();
  setDock(); refreshChips(); $('#qB').textContent = qLabel();
  stage.start(loop);
  $('#loading').remove();
  document.body.dataset.ready = 'true';
  S.ready = true;
  window.addEventListener('olympus:theme', () => stage.look(S.cur ? S.cur.spec : null));
  const want = q.get('city') || location.hash.slice(1);
  if (want && S.byId.has(want)) enterCity(want);
  else prefetch();
  if (want && S.byId.has(want)) setTimeout(prefetch, 2500);
}

let retierT = 0;
function retier(lv) {
  clearTimeout(retierT);
  retierT = setTimeout(() => {
    if (!S.stage) return;
    const keep = S.cur && S.cur.sel >= 0 ? S.cur.ds.items[S.cur.city.item[S.cur.sel]].id : null;
    const hubSel = S.hubSel;
    buildHub();
    S.islands.forEach((i) => { if (S.live[i.i]) S.stage.selectIsland(-1); });
    if (hubSel >= 0) S.stage.selectIsland(hubSel);
    if (S.hubDim) S.stage.setHubDim(S.hubDim);
    if (S.cur) {
      const C = S.cur;
      C.city = generate(C.spec, C.ds, { cap: S.stage.caps().cap });
      S.stage.buildCity(C.spec, C.city);
      S.stage.look(C.spec); S.stage.setFogRadius(C.city.bounds.r);
      C.picker = new Picker(C.city); C.sel = -1; C.match = null;
      drawMiniBase(); refreshChips();
      if (keep) { const k = Array.from({ length: C.city.n }, (_, j) => j).find((j) => C.ds.items[C.city.item[j]].id === keep); if (k !== undefined) selectBuilding(k, false); }
    }
    $('#qB').textContent = qLabel();
  }, 60);
}

// the test / debug door
window.__cities = {
  get ready() { return S.ready; },
  get mode() { return S.mode; },
  specs: () => S.specs.map((s) => s.id),
  enter: (id) => enterCity(id),
  exit: () => leaveCity(),
  select: (i) => selectIsland(i),
  info: () => ({ mode: S.mode, id: S.cur && S.cur.spec.id, n: S.cur && S.cur.city.n, total: S.cur && S.cur.city.total, hash: S.cur && S.cur.city.hash, districts: S.cur && S.cur.city.districts.length,
    demo: S.cur && S.cur.ds.demo, islands: S.islands.length, slots: S.slots, hubSel: S.hubSel, sheet: S.sheet, cam: S.cam, tour: S.tour, live: S.live.filter(Boolean).length, errors: S.errors, sel: S.cur && S.cur.sel,
    tier: S.stage && S.stage.tier(), camPos: S.stage && [S.stage.camera.position.x, S.stage.camera.position.y, S.stage.camera.position.z] }),
  stats: () => { S.stage.frame(); return { ...S.stage.stats(), budget: BUDGETS[S.stage.tier()], caps: S.stage.caps() }; },
  frame: () => S.stage.frame(),
  pickScreen: (x, y) => { onTap(x, y); },
  pickBuilding: (k) => selectBuilding(k),
  tallest: () => { const c = S.cur.city; let b = 0; for (let k = 1; k < c.n; k++) if (c.h[k] > c.h[b]) b = k; return b; },
  nearestToCenter: () => {
    const c = S.cur.city, w = canvas.clientWidth, h = canvas.clientHeight; let best = -1, bd = Infinity;
    for (let k = 0; k < c.n; k++) { const p = S.stage.project(c.x[k], c.h[k] * 0.5, c.z[k], w, h); if (!p.on) continue; const d = Math.hypot(p.x - w / 2, p.y - h * 0.5); if (d < bd) { bd = d; best = k; } }
    return best;
  },
  project: (k) => { const c = S.cur.city; return S.stage.project(c.x[k], c.h[k] * 0.5, c.z[k], canvas.clientWidth, canvas.clientHeight); },
  projectIsland: (i) => { const is = S.islands[i]; return S.stage.project(is.x, is.y + is.R * 0.3, is.z, canvas.clientWidth, canvas.clientHeight); },
  cam: (m) => setCam(m),
  tour: () => (S.tour ? stopTour() : startTour()),
  surprise: () => (S.mode === 'hub' ? surpriseHub() : surpriseCity()),
  find: (t) => { if (S.mode === 'hub') openFind(); else openCityFind(); const i = $('#sheetBody input'); i.value = t; i.dispatchEvent(new Event('input')); },
  today: () => cityOfDay(todayStr(), S.specs.map((s) => s.id)),
  setTier: (lv) => S.stage.rc.setQuality(lv),
  generate: (id, cap) => { const s = S.byId.get(id); return realDs(s.dataset).then((ds) => { const c = generate(s, ds, { cap: cap || 40000 }); return { n: c.n, total: c.total, hash: c.hash, districts: c.districts.length }; }); },
  TIERS, BUDGETS,
};

boot().catch((e) => {
  console.error('cities boot failed', e);
  S.errors.push(String(e && e.stack || e));
  if (O() && O().fail) O().fail('The cities could not start: ' + (e && e.message ? e.message : e));
});

// keep the unused import honest for tooling
void lerp; void store;
