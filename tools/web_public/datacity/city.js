// Olympus Data City: the NQ data machine (tools/datacity) drawn as a city. Reads ./city.json (written by
// `python -m tools.datacity`) and any plug-in districts (./plugins.json); without city.json, a demo city from ./fixture.json.
// Paper only: it shows research, never trades.
//
// Every building is one combination (a time x a confluence x up to two "while" states): height = $ per trade per micro after
// costs, colour = stability (gold: holds everywhere + FDR, green: both periods, amber: one, grey: noise), lit windows =
// sample size, pulsing roof = rising. ~32k buildings in 9 districts + the Strategies, the Harbor (LIT's trades as ships),
// the discoveries round the plaza and LIT's tower in the middle. The sky runs on the futures clock, the weather on the VIX.
// Routes: #top #today #watch #find #read #tour #b=<id> #d=<district>. Test hooks: ?synth=N (N synthetic grey buildings),
// ?vix=V (weather), ?sky=live|night|day, window.__city (state, stats()).
//
//   data.js (decode + plug-ins) · layout.js (where things stand) · scene.js (three.js world) · skyline.js (tiles + LOD)
//   fx.js (rays, fog, rain, traffic, beam, billboards) · sky.js (market clock, weather) · controls.js (camera)
//   tour.js (the cinematic tour) · minimap.js · ui.js (top bar, sheet, cards) · theme.js · city.js (this: wiring, frame loop)
//   OLYMPUS v2 (2026-11-03): scene.js draws through the OLYMPUS render core (../olympus/render.js: ACES, 4x MSAA, bloom, film finish,
//   tiers from OLYMPUS.fx(); LITE = 2 passes + a 30 fps cap) · landmarks.js (temple, forum, Pharos, Poseidon gate, district gates: PBR
//   marble / gold / glass, tap for a card) · streams.js (data arcs + pulses) · outskirts.js (scenery ring) · fly.js (SKIM / DRONE /
//   GRAND cameras; routes #cam=skim|drone|grand, #l=temple|forum|pharos|poseidon).
import * as THREE from '../jarvis/three.module.min.js';
import { $, el, clsRank, settings, money, num, pct } from './util.js';
import { decode, loadPlugins, labelOf } from './data.js';
import { layout } from './layout.js';
import { CityScene } from './scene.js';
import { Orbit } from './controls.js';
import { Tour, shots } from './tour.js';
import { MODES, flight } from './fly.js';
import { Minimap } from './minimap.js';
import { etClock, sunOf, weatherOf } from './sky.js';
import { applyTheme, watchTheme } from './theme.js';
import * as UI from './ui.js';

const O = window.OLYMPUS || null;   // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil
const LQ_FPS = 40;                  // below this for 3 s in a row (HQ, not chosen by the viewer) -> low quality
const SKY_MODES = ['live', 'night', 'day'];
const P = new URLSearchParams(location.search);
const state = window.__city = { ready: false, mode: null, buildings: 0, quality: null, fps: 0, found: 0, errors: [], today: { on: false, lit: 0 },
                                tour: { on: false, step: -1, steps: 0, caption: '' }, cam: { mode: 'orbit', on: false }, landmark: null, sky: null, weather: null, frames: 0 };

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

/** The live city, else the demo fixture. */
async function loadCity() {
  try {
    const d = await getJSON('./city.json');
    if (Array.isArray(d?.buildings) && d.buildings.length) return { data: d, demo: !!d.demo };
  } catch (e) { /* not published yet: the demo city */ }
  return { data: await getJSON('./fixture.json'), demo: true };
}

function billboards(model) {
  return (model.discoveries || []).slice(0, 12).map((d, i) => {
    const b = model.byId.get(d.id) || {};
    return { title: `DISCOVERY ${i + 1} / ${Math.min(12, model.discoveries.length)}${d.new ? ' · NEW' : ''}`, lines: [labelOf(b, model.D) || d.text],
             big: `${money(b.e)}/trade · ${b.cls || ''}${b.fdr ? ' · FDR' : ''}`, color: b.cls === 'gold' ? '#ffd36b' : b.cls === 'green' ? '#39e59a' : '#7fe9ff' };
  });
}

class App {
  constructor(model, demo) {
    this.model = model;
    this.L = layout(model);
    this.quality = O ? (O.lite() ? 'lq' : 'hq') : settings.get('dc.q', 'hq');
    this.skyMode = SKY_MODES.includes(P.get('sky')) ? P.get('sky') : settings.get('dc.sky', 'live');
    this.wxOn = settings.get('dc.wx', '1') === '1';
    this.weather = weatherOf(P.has('vix') ? +P.get('vix') : model.weather?.vix);
    const winRate = model.buildings.reduce((a, b) => a + (b.w || 50), 0) / Math.max(1, model.buildings.length) / 100;
    this.calm = O ? O.reduced() : !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    this.city = new CityScene($('#c'), this.L, { quality: this.quality, winRate: Math.max(0.3, Math.min(0.7, winRate)), billboards: billboards(model), calm: this.calm,
      onTier: (q) => this.onTier(q) });
    this.quality = this.city.quality;     // the render core's tier decides (OLYMPUS.fx())
    O?.onTheme(() => this.applyDay());   // OLYMPUS theme: the sky / fog follow it (scene.js setDay)
    O?.mode(this.quality === 'lq');
    this.orbit = new Orbit(this.city.camera, $('#c'), {
      calm: this.calm, radius: Math.max(150, Math.min(460, (this.L.bounds.x1 - this.L.bounds.x0) * 0.5)),
      onTap: (x, y) => this.tap(x, y), onFlyEnd: () => { this.endTour(); this.endCam(); },
    });
    this.index = new Map();
    this.L.items.forEach((it, i) => { if (it.b?.id && (!this.index.has(it.b.id) || it.kind !== 'd')) this.index.set(it.b.id, i); });
    let w = [];
    try { w = JSON.parse(settings.get('dc.watch', '[]')); } catch (e) { w = []; }
    this.watch = new Set(Array.isArray(w) ? w.filter((x) => typeof x === 'string').slice(0, 64) : []);
    this.todayOn = settings.get('dc.today', '0') === '1';
    this.keep = null;
    this.selected = -1;
    this.minimap = new Minimap($('#mini'), this.L, (x, z, d) => (d ? this.openDistrict(d) : this.orbit.focus(x, 0, z, 90)));
    Object.assign(state, { mode: demo ? 'demo' : 'live', buildings: this.L.items.filter((it) => it.kind === 'b').length, items: this.L.items.length,
                           quality: this.quality, districts: this.L.districts.map((d) => d.key), tiles: this.L.tiles.length, blocks: this.L.blocks.length });
    state.stats = () => this.stats();
    state.applyTheme = (t) => applyTheme(t, this.city);
    UI.hud(model, demo);
    this.wire();
    this.applyStates();
    this.setToday(this.todayOn, true);
    this.applySky(true);
    watchTheme((t) => applyTheme(t, this.city));
    document.fonts?.ready?.then(() => this.city.refreshText()).catch(() => {});
    $('#qB').textContent = this.quality.toUpperCase();
  }

  // -- the per-building state (search dim, Today, watch / selected): written when it changes, never per frame
  applyStates() {
    const items = this.L.items, keep = this.keep;
    this.city.skyline.apply(keep ? (i) => !keep[i] : null, (i) => items[i].b?.td || 0,
      (i) => (i === this.selected ? 2 : this.watch.has(items[i].b?.id) ? 1 : 0));
    const pins = [...this.watch].map((id) => this.index.get(id)).filter((i) => i !== undefined);
    this.city.setPins(pins);
    this.minimap.pins = pins.map((i) => [items[i].x, items[i].z]);
    state.today.lit = items.filter((it) => it.kind === 'b' && it.b.td).length;
    state.watch = pins.length;
  }

  setToday(on, quiet) {
    this.todayOn = on;
    this.city.setToday(on);
    state.today.on = on;
    if (!quiet) { settings.set('dc.today', on ? '1' : '0'); UI.toast(on ? `Today layer: ${state.today.lit.toLocaleString()} buildings true on ${this.model.today?.day || 'the last session'}` : 'Today layer off'); }
    return on;
  }

  // -- the sky (market clock) and the weather (VIX)
  clock() {
    if (this.tour?.info.on) {                                    // the tour runs one futures day in time-lapse
      const k = (this.tour.i + Math.min(1, this.tour.t / 8)) / Math.max(1, this.tour.list.length);
      return { mod: (k * 1440) % 1440, mins: (k * 1440 + 1080) % 1440, dow: 2, label: 'time-lapse' };
    }
    if (this.skyMode === 'night') return { mod: 1380, mins: 1020, dow: 2, label: 'night' };
    if (this.skyMode === 'day') return { mod: 930, mins: 570, dow: 2, label: 'day' };
    return etClock(new Date());
  }

  applySky(force) {
    const c = this.clock(), sun = sunOf(c), w = this.wxOn ? this.weather : weatherOf(14);
    const theme = this.city.setSun(sun, w);
    if (force || this._theme !== theme) { this._theme = theme; document.querySelector('meta[name=theme-color]').setAttribute('content', theme); }
    const txt = `${c.label} · ${sun.session}${this.wxOn ? ` · VIX ${w.vix.toFixed(1)} ${w.sky}` : ''}`;
    if (this._clockTxt !== txt) { this._clockTxt = txt; $('#clock').textContent = txt; }
    state.sky = { mode: this.skyMode, elev: +sun.elev.toFixed(3), day: +sun.day.toFixed(3), session: sun.session };
    state.weather = { sky: w.sky, rain: w.rain, vix: w.vix, on: this.wxOn };
    $('#skyB').classList.toggle('on', this.skyMode !== 'live');
    $('#skyB').setAttribute('aria-label', `Sky: ${this.skyMode === 'live' ? 'market clock' : this.skyMode}`);
    $('#wxB').classList.toggle('on', this.wxOn);
  }

  // -- opening things
  openId(id) { const i = this.index.get(id); if (i !== undefined) this.open(i); }

  open(i, quiet) {
    const it = this.L.items[i];
    if (!it) return;
    const b = it.b, sec = this.L.districts[it.d];
    const ctx = { label: labelOf(b, this.model.D), district: sec?.name, watched: this.watch.has(b.id), monument: it.kind === 'd',
                  onWatch: () => this.toggleWatch(b.id) };
    if (it.kind === 's') UI.showStrategy(b);
    else if (it.kind === 'ship') UI.showShip(b);
    else if (b.plugin) UI.showPlugin(b, sec, ctx);
    else UI.showBuilding(b, ctx);
    this.selected = i;
    this.applyStates();
    this.city.beam.show(it.x, it.z, it.h, it.color);
    this.setTag(it, labelOf(b, this.model.D));
    if (!quiet) this.orbit.focus(it.x, Math.min(it.h * 0.5, 6), it.z, 34 + it.h * 2);
    try { history.replaceState(null, '', '#b=' + encodeURIComponent(b.id)); } catch (e) { /* file:// */ }
  }

  openLit() {
    UI.showLit(this.model.lit);
    this.city.beam.show(0, 0, 50, 0x3fd8ff);
    this.orbit.focus(0, 16, 0, 90);
  }

  /** Tap-to-zoom: the camera hops over to a district (or to a point in it: a far block, a tapped street) and the sheet
   *  shows what lives there. */
  openDistrict(d, at) {
    if (at) this.orbit.focus(at.x, 0, at.z, at.r, 0.85);
    else this.orbit.focus(d.cx, 0, d.cz, Math.max(70, (d.wide ? d.w * 0.5 : d.half) * 2.3), 0.9);
    const best = this.L.items.map((it, i) => [it, i]).filter(([it]) => this.L.districts[it.d] === d && it.kind !== 'ship')
      .sort((a, b) => clsRank(a[0].b.cls) - clsRank(b[0].b.cls) || (b[0].b.e || 0) - (a[0].b.e || 0)).slice(0, 8);
    UI.showDistrict(d, (body) => {
      if (!best.length) return;
      body.appendChild(el('h3', null, 'Tallest honest buildings here'));
      const ul = el('ul', 'list');
      for (const [it, i] of best) {
        const li = el('li');
        const k = el('span', 'k', ''); k.style.background = '#' + it.color.toString(16).padStart(6, '0');
        const t = el('span', 't'); t.appendChild(el('div', null, labelOf(it.b, this.model.D)));
        li.append(k, t, el('span', 'm ' + ((it.b.e || 0) >= 0 ? 'pos' : 'neg'), money(it.b.e)));
        li.addEventListener('click', () => this.open(i));
        ul.appendChild(li);
      }
      body.appendChild(ul);
    });
    try { history.replaceState(null, '', '#d=' + encodeURIComponent(d.key)); } catch (e) { /* file:// */ }
    state.district = d.key;
  }

  tap(x, y) {
    const hit = this.city.pick(x, y);
    if (hit?.lit) this.openLit();
    else if (hit?.landmark) this.openLandmark(hit.landmark);
    else if (hit?.item !== undefined) this.open(hit.item);
    else if (hit?.block !== undefined) {
      const B = this.L.blocks[hit.block];
      this.openDistrict(this.L.districts[B.d], { x: (B.x0 + B.x1) / 2, z: (B.z0 + B.z1) / 2, r: 46 });
    } else {                                                    // a street or an empty lot: zoom to its district, if any
      const g = this.city.groundAt(x, y), d = g && this.L.districts.find((q) => Math.abs(q.cx - g.x) <= (q.wide ? q.w / 2 : q.half) && Math.abs(q.cz - g.z) <= q.half);
      if (d && (UI.sheet.view !== 'district' || state.district !== d.key)) this.openDistrict(d, { x: g.x, z: g.z, r: 70 });
      else UI.sheet.close();
    }
  }

  // -- the tag over a tapped building (its name and result, riding on the building until the card closes)
  setTag(it, label) {
    const t = $('#tag');
    if (!it || !t) { this.tagAt = null; if (t) t.style.display = 'none'; return; }
    const b = it.b || {};
    t.replaceChildren(el('b', null, label || b.lab || b.id || ''), el('span', null,
      it.kind === 'ship' ? `${money(b.pnl)} · ${b.R >= 0 ? '+' : ''}${num(b.R, 2)}R` : it.kind === 's' ? 'strategy tower'
      : `${money(b.e)}/trade/micro · ${b.cls || ''}${b.n ? ' · ' + b.n.toLocaleString() + ' trades' : ''}`));
    this.tagAt = { it, v: new THREE.Vector3() };
    state.tag = label || b.id || '';
  }

  updateTag() {
    const k = this.tagAt, t = $('#tag');
    if (!k || !t) return;
    k.v.set(k.it.x, k.it.h + 1.5, k.it.z).project(this.city.camera);
    if (k.v.z > 1 || k.v.z < -1) { t.style.display = 'none'; return; }
    const W = innerWidth, H = innerHeight, w = t.offsetWidth || 120;
    const x = Math.max(8, Math.min(W - w - 90, (k.v.x * 0.5 + 0.5) * W - w / 2)), y = Math.max(96, Math.min(H - 190, (-k.v.y * 0.5 + 0.5) * H - 46));
    t.style.display = 'block';
    t.style.transform = `translate(${x.toFixed(0)}px,${y.toFixed(0)}px)`;
  }

  // -- the landmarks: tap one for its card (real numbers from the model), the camera glides there
  landmarkInfo(key) {
    const m = this.model, g = m.guard || {}, lit = m.lit?.spans?.['2026'], S = this.city.lm.spots[key];
    if (key === 'temple') {
      const gold = m.buildings.filter((b) => b.cls === 'gold').sort((a, c) => (c.e || 0) - (a.e || 0));
      return { name: 'Temple of the Gold', kind: 'landmark', blurb: 'The acropolis: the few combinations that hold in 2026, in 2021-25 and in every year, and pass the false-discovery guard. The hologram turns over the roof, the beam reaches into the sky.',
        tiles: [['gold buildings', String(gold.length)], ['pass FDR', String(g.fdr_pos ?? '–')], ['placebo passes', String(g.placebo_fdr ?? '–')], ['discoveries', String((m.discoveries || []).length)]],
        lines: gold.slice(0, 3).map((b) => `${labelOf(b, m.D)}: ${money(b.e)} per trade per micro`) };
    }
    if (key === 'forum') {
      const c = g.classes || {};
      return { name: 'The Forum', kind: 'landmark', blurb: 'The colonnade round the plaza: every claim in the city is tested in the open here. The gaps in the columns are the boulevards to the districts.',
        tiles: [['tried', (g.tried || 0).toLocaleString()], ['tested (30+ trades)', (g.tested || 0).toLocaleString()], ['gold / green', `${c.gold ?? '–'} / ${c.green ?? '–'}`], ['grey (noise)', (c.grey ?? 0).toLocaleString()]],
        lines: [`Picked on 2021-24 only, ${g.holdout?.picked_2021_24 ?? '–'} combinations; ${g.holdout?.pct_positive ?? '–'}% stayed positive in 2025-26. Most of the city is noise, and the city says so.`] };
    }
    if (key === 'pharos') {
      const ships = this.L.items.filter((it) => it.kind === 'ship').map((it) => it.b), won = ships.filter((x) => x.pnl >= 0).length, net = ships.reduce((a, x) => a + (x.pnl || 0), 0);
      return { name: 'Pharos lighthouse', kind: 'landmark', blurb: 'The harbor\'s lighthouse: its beams sweep the water where one ship per LIT trade is moored (the live settings replayed, costs in; paper, not broker fills).',
        tiles: [['ships (trades)', ships.length.toLocaleString()], ['won', ships.length ? pct((100 * won) / ships.length) : '–'], ['net', money(net)], ['2026 PF', num(lit?.pf, 2)]],
        go: { label: 'Fly to the Harbor', fn: () => { const d = this.L.districts.find((q) => q.kind === 'harbor'); if (d) this.openDistrict(d); } } };
    }
    if (key === 'poseidon') {
      const w = m.weather || {}, v = this.weather;
      return { name: 'Gate of Poseidon', kind: 'weather gate', blurb: 'The trident\'s lantern is the weather: cyan under VIX 15, amber to 20, blue to 25, red above (it pulses faster as the VIX rises). The city\'s rain and storms follow the same number.',
        tiles: [['VIX', num(w.vix ?? v.vix, 1)], ['VXN', num(w.vxn, 1)], ['VIX3M', num(w.vix3m, 1)], ['sky', v.sky]],
        lines: [`CBOE closes${w.vix_date ? ': VIX ' + w.vix_date : ''}${w.source ? ' · ' + w.source : ''}.`] };
    }
    return { name: S?.name || key, kind: 'landmark', blurb: '' };
  }

  openLandmark(key) {
    state.landmark = key;
    if (key.startsWith('gate:')) {
      const d = this.L.districts.find((q) => q.key === key.slice(5));
      if (d) this.openDistrict(d);
      return;
    }
    const S = this.city.lm.spots[key];
    if (!S) return;
    UI.showLandmark(this.landmarkInfo(key));
    this.setTag(null);
    this.orbit.focus(S.x, Math.min(S.h * 0.4, 24), S.z, S.r * 1.7, 0.95);
    try { history.replaceState(null, '', '#l=' + key); } catch (e) { /* file:// */ }
  }

  // -- the fly-through cameras (fly.js): the manual orbit is the fourth
  startCam(mode) {
    if (mode === 'orbit') { this.orbit.stopFly(); this.endCam(); return; }
    if (this.tour) this.orbit.stopFly();
    const cam = this.city.camera, dir = new THREE.Vector3();
    cam.getWorldDirection(dir);
    const f = flight(mode, this.L, this.city.lm.spots, { pos: cam.position.clone(), look: cam.position.clone().add(dir.multiplyScalar(70)) });
    if (!f) return;
    this.orbit.drive((dt) => f.step(dt));
    this.cam = { mode, f, lm: null };
    state.cam = { mode, on: true };
    UI.sheet.close();
    UI.caption(MODES.find((x) => x.key === mode).hint + ' · drag to take over', 0, 0, mode.toUpperCase());
    this.camButtons();
  }

  endCam() {
    if (!this.cam) { this.camButtons(); return; }
    this.cam = null;
    state.cam = { mode: 'orbit', on: false };
    UI.caption('');
    this.camButtons();
  }

  camButtons() {
    const cur = this.cam?.mode || 'orbit';
    document.querySelectorAll('#cams [data-cam]').forEach((b) => b.classList.toggle('on', b.dataset.cam === cur));
  }

  updateCam() {
    const c = this.cam;
    if (!c) return;
    const i = c.f.info();
    state.cam = { ...state.cam, ...i };
    if (c.mode === 'grand' && i.landmark && i.landmark !== c.lm) {
      c.lm = i.landmark;
      UI.caption(this.landmarkInfo(i.landmark).blurb, 0, 0, (this.city.lm.spots[i.landmark]?.name || '').toUpperCase());
    }
  }

  toggleWatch(id) {
    if (this.watch.has(id)) this.watch.delete(id); else if (this.watch.size < 64) this.watch.add(id);
    settings.set('dc.watch', JSON.stringify([...this.watch]));
    this.applyStates();
    if (UI.sheet.isOpen('watch')) this.showView('watch');
    return this.watch.has(id);
  }

  // -- search: dims what does not match, beams onto the best match
  find(text, st) {
    const words = String(text || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    const D = this.model.D, cls = st?.cls || 'all', dk = st?.d || 'all';
    const filtering = words.length > 0 || cls !== 'all' || dk !== 'all';
    const items = this.L.items;
    const keep = items.map((it) => {
      if (it.kind === 'ship' || !it.b) return !filtering;
      if (cls !== 'all' && it.b.cls !== cls) return false;
      if (dk !== 'all' && this.L.districts[it.d]?.key !== dk) return false;
      if (!words.length) return true;
      const s = (labelOf(it.b, D) + ' ' + (it.b.id || '')).toLowerCase();
      return words.every((w) => s.includes(w));
    });
    this.keep = filtering ? keep : null;
    this.applyStates();
    const hits = items.map((it, i) => [it, i]).filter(([it, i]) => keep[i] && it.kind === 'b')
      .sort((a, b) => clsRank(a[0].b.cls) - clsRank(b[0].b.cls) || (b[0].b.e || 0) - (a[0].b.e || 0));
    UI.fillFound(hits.slice(0, 30).map(([it, i]) => ({ ...it, i })), (b) => labelOf(b, D), (it) => this.open(it.i), filtering ? hits.length : 0);
    state.found = filtering ? hits.length : 0;
    if (filtering && hits.length) { const [it] = hits[0]; this.city.beam.show(it.x, it.z, it.h, it.color); }
    else if (!filtering) this.city.beam.hide();
  }

  resetFind() {
    this.keep = null;
    this.applyStates();
    state.found = 0;
  }

  // -- the sheet's views
  showView(name) {
    const m = this.model;
    if (name === 'top') UI.sheet.open('top', 'Top 10: what holds in 2026 and 2021-25', (b) => UI.viewTop(b, m, (id) => this.openId(id)));
    else if (name === 'today') {
      if (!this.todayOn) this.setToday(true);
      const app = this;
      UI.sheet.open('today', "Today's city", (b) => UI.viewToday(b, m, (id) => this.openId(id), { get on() { return app.todayOn; }, toggle: () => app.setToday(!app.todayOn) }));
    } else if (name === 'watch') {
      const list = [...this.watch].map((id) => m.byId.get(id)).filter(Boolean).map((b) => ({ b, label: labelOf(b, m.D) }));
      UI.sheet.open('watch', `Watchlist (${list.length})`, (b) => UI.viewWatch(b, list, (id) => this.openId(id), (id) => this.toggleWatch(id)));
    } else if (name === 'find') {
      UI.sheet.open('find', 'Search the city', (b) => { this.findUI = UI.viewFind(b, m.sections, (q, st) => this.find(q, st)); });
      this.find('', this.findUI.state);
      setTimeout(() => this.findUI?.q.focus({ preventScroll: true }), 50);
    } else if (name === 'read') UI.sheet.open('read', 'How to read the city', (b) => UI.viewRead(b, m));
  }

  route() {
    const h = decodeURIComponent(location.hash || '');
    if (['#top', '#today', '#watch', '#find', '#read'].includes(h)) this.showView(h.slice(1));
    else if (h === '#discoveries') this.showView('today');
    else if (h === '#tour') this.startTour();
    else if (h.startsWith('#b=')) this.openId(h.slice(3));
    else if (h.startsWith('#l=')) this.openLandmark(h.slice(3));
    else if (h.startsWith('#cam=') && MODES.some((x) => x.key === h.slice(5))) this.startCam(h.slice(5));
    else if (h.startsWith('#d=')) { const d = this.L.districts.find((x) => x.key === h.slice(3)); if (d) this.openDistrict(d); }
  }

  // -- the tour
  startTour() {
    UI.sheet.close();
    this.todayBefore = this.todayOn;
    this.tour = new Tour(shots(this.model, this.L), THREE.Vector3, {
      onCaption: (t, i, n) => UI.caption(t, i, n),
      onShot: (s) => this.setToday(s.today ? true : this.todayBefore, true),
      onEnd: () => {},
    });
    const cam = this.city.camera, look = new THREE.Vector3();
    cam.getWorldDirection(look);
    this.tour.start(cam.position, cam.position.clone().add(look.multiplyScalar(80)));
    const speed = Math.max(1, Math.min(50, +P.get('tourSpeed') || 1));            // tests fast-forward the tour
    this.orbit.drive((dt) => this.tour?.step(dt * speed) ?? null);
    $('#tourB').classList.add('on');
    document.body.classList.add('cine');
  }

  endTour() {
    if (!this.tour) return;
    this.tour.stop();
    this.tour = null;
    UI.caption('');
    this.setToday(this.todayBefore, true);
    $('#tourB').classList.remove('on');
    document.body.classList.remove('cine');
    state.tour = { on: false, step: -1, steps: 0, caption: '', done: (state.tour.done || 0) + 1, last: state.tour.step };
  }

  // -- switches
  /** the render core changed tier (OLYMPUS choice or the core's own step-down): the page follows */
  onTier(q) {
    this.quality = q;
    state.quality = q;
    O?.mode(q === 'lq');
    $('#qB').textContent = q.toUpperCase();
  }

  setQuality(q, auto) {
    this.quality = q;
    state.quality = q;
    if (!auto) { if (O) O.setFx(q === 'hq' ? 'high' : 'low'); else settings.set('dc.q', q); }
    this.city.setQuality(q);
    O?.mode(q === 'lq');
    $('#qB').textContent = q.toUpperCase();
    if (auto) UI.toast('LITE mode on for a smoother city (tap LQ to switch back)');
  }

  wire() {
    document.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => {
      const v = b.dataset.tab;
      if (UI.sheet.isOpen(v)) { UI.sheet.close(); return; }
      this.showView(v);
    }));
    UI.sheet.onClose = () => {
      this.setTag(null);
      if (this.keep) this.resetFind();
      this.selected = -1;
      this.applyStates();
      this.city.beam.hide();
    };
    $('#sheetX').addEventListener('click', () => UI.sheet.close());
    document.querySelectorAll('#cams [data-cam]').forEach((b) => b.addEventListener('click', () => this.startCam(b.dataset.cam)));
    $('#tourB').addEventListener('click', () => (this.tour ? this.orbit.stopFly() : this.startTour()));
    $('#skyB').addEventListener('click', () => {
      this.skyMode = SKY_MODES[(SKY_MODES.indexOf(this.skyMode) + 1) % SKY_MODES.length];
      settings.set('dc.sky', this.skyMode);
      this.applySky(true);
      UI.toast({ live: 'Sky: the futures clock (sunrise at the Asia open)', night: 'Sky: night', day: 'Sky: day' }[this.skyMode]);
    });
    $('#wxB').addEventListener('click', () => {
      this.wxOn = !this.wxOn;
      settings.set('dc.wx', this.wxOn ? '1' : '0');
      this.applySky(true);
      UI.toast(this.wxOn ? `Weather from the VIX: ${this.weather.vix.toFixed(1)} = ${this.weather.sky}${this.model.weather?.vix_date ? ` (CBOE close ${this.model.weather.vix_date})` : ''}` : 'Weather off: a clear sky');
    });
    $('#qB').addEventListener('click', () => this.setQuality(this.quality === 'hq' ? 'lq' : 'hq'));
    window.addEventListener('resize', () => this.city.resize());
    window.addEventListener('hashchange', () => this.route());
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape') { UI.sheet.close(); if (this.tour) this.orbit.stopFly(); } });
  }

  stats() {
    const i = this.city.renderer.info;
    return { calls: this.lastCalls ?? i.render.calls, triangles: this.lastTris ?? i.render.triangles, points: i.render.points,
             geometries: i.memory.geometries, textures: i.memory.textures, programs: (i.programs || []).length,
             pixelRatio: this.city.renderer.getPixelRatio(), lod: this.city.skyline.info(), frames: state.frames };
  }

  // -- the frame loop (with the automatic low-quality switch)
  start() {
    let last = performance.now(), frames = 0, acc = 0, slow = 0, skyT = 0;
    const frame = (now) => {
      requestAnimationFrame(frame);
      if (O ? O.hidden() : document.hidden) { last = now; return; }          // hidden tab: no frame at all
      if (this.quality === 'lq' && now - last < 28) return;                  // LITE draws at 30 fps (half the work, half the heat)
      const dt = Math.min(0.1, Math.max(0, (now - last) / 1000));
      last = now;
      this.orbit.update(dt);
      skyT += dt;
      if (skyT > (this.tour ? 0.05 : 1)) { skyT = 0; this.applySky(); }
      this.updateCam();
      this.city.render(dt);
      this.updateTag();
      const info = this.city.renderer.info.render;
      this.lastCalls = info.calls; this.lastTris = info.triangles;
      this.minimap.draw(this.city.camera, this.tour || this.cam ? this.orbit.at : this.orbit.view.target, dt);
      if (this.tour) state.tour = { ...state.tour, ...this.tour.info };
      state.beam = !!this.city.beam.at;
      state.frames++;
      frames++; acc += dt;
      if (acc >= 1) {
        state.fps = Math.round(frames / acc);
        frames = 0; acc = 0;
        slow = this.quality === 'hq' && state.fps < LQ_FPS ? slow + 1 : 0;
        if (slow >= 3 && (O ? !O.chosen() : settings.get('dc.q', null) === null) && !P.has('nolite')) this.setQuality('lq', true);
      }
    };
    requestAnimationFrame(frame);
    this.route();
  }
}

async function postCard() {
  if (window.parent === window) return;
  try {
    window.parent.postMessage({ jarvis: 1, href: location.href, card: await getJSON('./jarvis.json') }, location.origin);
  } catch (e) { /* no card: Jarvis reads jarvis.json itself */ }
}

async function main() {
  const { data, demo } = await loadCity();
  const plugins = await loadPlugins(data, getJSON);
  const synth = Math.max(0, Math.min(60000, parseInt(P.get('synth') || '0', 10) || 0));
  const model = decode(data, plugins, synth);
  const app = new App(model, demo);
  window.__app = app;
  $('#loading').remove();
  app.start();
  state.ready = true;
  postCard();
}

window.addEventListener('error', (e) => state.errors.push(String(e.message || e)));
window.addEventListener('unhandledrejection', (e) => state.errors.push(String(e.reason?.message || e.reason || e)));
main().catch((e) => {
  state.errors.push(String(e?.message || e));
  $('#loading')?.remove();
  if (O) O.fail(`the city could not be drawn on this device (${e?.message || 'error'})`);
  else document.body.appendChild(el('div', 'err', `The city could not be drawn on this device (${e?.message || 'error'}).`));
});
