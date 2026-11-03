// Olympus Data City: the NQ data machine (tools/datacity) drawn as a night city. Reads ./city.json (written by
// `python -m tools.datacity`); without it, a demo city from ./fixture.json. Paper only: it shows research, never trades.
// Districts: Times, Confluences, While-states (one building per combination), Strategies (sized, with MFFU eval odds),
// Discoveries (monuments round the plaza) and the LIT tower in the middle. Height = $ per trade per micro after costs,
// colour = stability (gold: holds everywhere + FDR, green: both periods, amber: one, grey: noise), lit windows = sample
// size, pulsing roof = rising. Drag / pinch to orbit, tap a building for its card. Routes: #top, #today, #b=<id>.
//
//   util.js (helpers) · layout.js (where things stand) · shaders.js · scene.js (three.js world) · controls.js (camera)
//   ui.js (panels and cards) · city.js (this: data, wiring, the frame loop)
import { $, el, clsRank, settings } from './util.js';
import { layout, flyPath } from './layout.js';
import { CityScene } from './scene.js';
import { Orbit } from './controls.js';
import * as UI from './ui.js';

const O = window.OLYMPUS || null;   // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil
const LQ_FPS = 40;           // below this for 3 s in a row (HQ, not chosen by the viewer) -> low quality
const state = window.__city = { ready: false, mode: null, buildings: 0, quality: null, fps: 0, found: 0, errors: [] };

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

class App {
  constructor(data, demo) {
    this.data = data;
    this.L = layout(data);
    this.quality = O ? (O.lite() ? 'lq' : 'hq') : settings.get('dc.q', 'hq');
    this.day = settings.get('dc.day', '0') === '1';
    this.cls = 'all';
    const winRate = data.buildings.reduce((a, b) => a + (b.w || 50), 0) / Math.max(1, data.buildings.length) / 100;
    this.city = new CityScene($('#c'), this.L, { quality: this.quality, day: this.day, winRate: Math.max(0.3, Math.min(0.7, winRate)) });
    O?.track(this.city.renderer);
    O?.mode(this.quality === 'lq');
    this.orbit = new Orbit(this.city.camera, $('#c'), {
      calm: O ? O.reduced() : window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
      onTap: (x, y) => this.tap(x, y),
      onFlyEnd: () => $('#flyB').classList.remove('on'),
    });
    Object.assign(state, { mode: demo ? 'demo' : 'live', buildings: this.L.items.length, quality: this.quality });
    UI.hud(data, demo);
    UI.fillTop(data, (id) => this.openId(id));
    UI.fillToday(data, (id) => this.openId(id));
    UI.fillRead(data);
    this.wire();
    this.applyDay();
    $('#qB').textContent = this.quality.toUpperCase();
  }

  // -- opening things
  itemById(id) {
    return this.L.items.find((it) => it.b.id === id && it.kind !== 'd') || this.L.items.find((it) => it.b.id === id);
  }

  openId(id) { this.open(this.itemById(id)); }

  open(it) {
    if (!it) return;
    if (it.kind === 's') UI.showStrategy(it.b);
    else UI.showBuilding(it.b, it.kind === 'd');
    this.orbit.focus(it.x, Math.min(it.h * 0.5, 6), it.z, 40 + it.h * 2);
    try { history.replaceState(null, '', '#b=' + encodeURIComponent(it.b.id)); } catch (e) { /* file:// */ }
  }

  openLit() {
    UI.showLit(this.data.lit);
    this.orbit.focus(0, 16, 0, 80);
  }

  tap(x, y) {
    const hit = this.city.pick(x, y);
    if (!hit) UI.closeAll();
    else if (hit.lit) this.openLit();
    else this.open(this.L.items[hit.index]);
  }

  route() {
    const h = decodeURIComponent(location.hash || '');
    if (h === '#top') UI.openPanel('topP');
    else if (h === '#today' || h === '#discoveries') UI.openPanel('todayP');
    else if (h.startsWith('#b=')) this.openId(h.slice(3));
  }

  // -- search
  find() {
    const words = $('#q').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const filtering = words.length > 0 || this.cls !== 'all';
    const match = (it) => (this.cls === 'all' || it.b.cls === this.cls)
      && words.every((w) => (it.b.lab || '').toLowerCase().includes(w) || (it.b.id || '').toLowerCase().includes(w));
    const keep = this.L.items.map(match);
    this.city.dim(filtering ? (i) => keep[i] : null);
    const hits = this.L.items.filter((it, i) => keep[i] && it.kind === 'b')
      .sort((a, b) => clsRank(a.b.cls) - clsRank(b.b.cls) || (b.b.e || 0) - (a.b.e || 0));
    UI.fillFound(hits, (it) => this.open(it));
    state.found = hits.length;
  }

  resetFind() {
    $('#q').value = '';
    this.cls = 'all';
    $('#seg').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x.dataset.cls === 'all'));
    this.find();
  }

  // -- switches
  applyDay() {
    const theme = this.city.setDay(this.day);
    $('#skyB').classList.toggle('on', this.day);
    document.querySelector('meta[name=theme-color]').setAttribute('content', theme);
  }

  setQuality(q, auto) {
    this.quality = q;
    state.quality = q;
    if (!auto) { if (O) O.setFx(q === 'hq' ? 'high' : 'low'); else settings.set('dc.q', q); }
    this.city.setQuality(q);
    O?.mode(q === 'lq');
    $('#qB').textContent = q.toUpperCase();
    if (auto) UI.toast('Low-quality mode on for a smoother city (tap LQ to switch back)');
  }

  wire() {
    const seg = $('#seg');
    for (const [k, t] of [['all', 'All'], ['gold', 'Gold'], ['green', 'Both periods'], ['amber', 'One period'], ['grey', 'Noise']]) {
      const b = el('button', k === 'all' ? 'on' : '', t);
      b.dataset.cls = k;
      b.addEventListener('click', () => {
        this.cls = k;
        seg.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
        this.find();
      });
      seg.appendChild(b);
    }
    $('#q').addEventListener('input', () => this.find());
    document.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => {
      const id = b.dataset.open;
      if (UI.isOpen(id)) { UI.closeAll(); return; }
      if (id === 'findP') this.find();
      UI.openPanel(id);
    }));
    document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => {
      $('#' + b.dataset.close).classList.remove('on');
      if (b.dataset.close === 'findP') this.resetFind();
    }));
    $('#flyB').addEventListener('click', () => {
      if (this.orbit.flying) { this.orbit.stopFly(); return; }
      UI.closeAll();
      this.orbit.startFly(flyPath(this.L.centers));
      $('#flyB').classList.add('on');
    });
    $('#skyB').addEventListener('click', () => {
      this.day = !this.day;
      settings.set('dc.day', this.day ? '1' : '0');
      this.applyDay();
    });
    $('#qB').addEventListener('click', () => this.setQuality(this.quality === 'hq' ? 'lq' : 'hq'));
    window.addEventListener('resize', () => this.city.resize());
    window.addEventListener('hashchange', () => this.route());
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape') UI.closeAll(); });
  }

  // -- the frame loop (with the automatic low-quality switch)
  start() {
    let last = performance.now(), frames = 0, acc = 0, slow = 0;
    const frame = (now) => {
      if (O ? O.hidden() : document.hidden) { last = now; requestAnimationFrame(frame); return; }   // hidden tab: no frame
      const dt = Math.min(0.1, Math.max(0, (now - last) / 1000));
      last = now;
      this.orbit.update(dt);
      this.city.render(dt);
      frames++; acc += dt;
      if (acc >= 1) {
        state.fps = Math.round(frames / acc);
        frames = 0; acc = 0;
        slow = this.quality === 'hq' && state.fps < LQ_FPS && !document.hidden ? slow + 1 : 0;
        if (slow >= 3 && (O ? !O.chosen() : settings.get('dc.q', null) === null)) this.setQuality('lq', true);
      }
      requestAnimationFrame(frame);
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
  const app = new App(data, demo);
  $('#loading').remove();
  app.start();
  state.ready = true;
  postCard();
}

window.addEventListener('error', (e) => state.errors.push(String(e.message || e)));
main().catch((e) => {
  state.errors.push(String(e?.message || e));
  $('#loading')?.remove();
  if (O) O.fail(`the city could not be drawn on this device (${e?.message || 'error'})`);
  else document.body.appendChild(el('div', 'err', `The city could not be drawn on this device (${e?.message || 'error'}).`));
});
