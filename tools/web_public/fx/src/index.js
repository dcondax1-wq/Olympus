// Public API of the 3D layer (bundled to fx.js). Both dashboards load it lazily after the first paint:
//   const FX = await import('./fx.js');  FX.init({ level: 'max' | 'lite' | 'off', gyro });
//   FX.mount('trades-galaxy', el, 'galaxy', rows, { onPick });   // views are reused when the page re-renders
//   FX.detachAll()  before a page replaces its HTML;  FX.mood({...}) FX.warp() FX.pulse()
import { THREE, Q, setLevel as setQuality, readTheme, theme, enableGyro, wake, toScreen } from './core.js';
import { Field } from './field.js';
import { initTaps, spark, setTapColors, setTaps } from './taps.js';
import { Orb } from './orb.js';
import { Galaxy } from './galaxy.js';
import { City } from './city.js';
import { Candles } from './candles.js';
import { Constellation } from './constellation.js';
import { Ribbon } from './ribbon.js';
import { Reactor } from './reactor.js';
import { Pipeline } from './pipeline.js';
import { Losses } from './losses.js';

export const version = 1;
const KINDS = { orb: Orb, galaxy: Galaxy, city: City, candles: Candles, constellation: Constellation, ribbon: Ribbon, reactor: Reactor, pipeline: Pipeline, losses: Losses };
const reg = new Map();
let field = null, bg = null, inited = false;

export function supported() {
  try { const c = document.createElement('canvas'); return !!c.getContext('webgl2'); } catch { return false; }
}
const tapColors = () => ['#' + theme.accent.getHexString(), '#' + theme.accent2.getHexString(), '#ff2bd6', '#c084fc', '#ffffff'];

export function init({ level = 'max', gyro = false } = {}) {
  if (inited) return Q.level;
  inited = true;
  readTheme();
  initTaps({ colors: tapColors() });
  setLevel(level);
  if (gyro) enableGyro(true);
  window.__LEFX = { Q, reg, get field() { return field; }, toScreen, THREE };
  return Q.level;
}

export function setLevel(level) {
  const lv = level === 'off' || !supported() ? 'off' : level;
  setQuality(lv);
  document.documentElement.dataset.fx = lv;
  setTaps(lv !== 'off');
  if (lv === 'off') {
    if (field) { field.dispose(); field = null; }
    bg?.remove(); bg = null;
    for (const v of reg.values()) v.dispose(); reg.clear();
    return lv;
  }
  if (!field) {
    bg = document.createElement('div'); bg.className = 'fx-bg'; bg.setAttribute('aria-hidden', 'true');
    document.body.prepend(bg);
    field = new Field(); field.attach(bg);
  }
  wake();
  return lv;
}

// a 3D view inside a page element; the same key keeps the same WebGL view across re-renders
export function mount(key, el, kind, data, opts = {}) {
  if (Q.level === 'off' || !el || !KINDS[kind]) return null;
  let v = reg.get(key);
  if (v && v.kind !== kind) { v.dispose(); reg.delete(key); v = null; }
  if (!v) {
    try { v = new KINDS[kind](opts); } catch (e) { console.warn('fx mount', kind, e); return null; }
    v.kind = kind; reg.set(key, v);
  }
  v.opts = { ...v.opts, ...opts };
  v.attach(el);
  try { v.setData(data, opts); } catch (e) { console.warn('fx data', kind, e); }
  v.lastUsed = performance.now();
  evict();
  return v;
}
export function get(key) { return reg.get(key) || null; }
export function detachAll() { for (const v of reg.values()) v.detach(); }
function evict() {
  if (reg.size <= 4) return;
  const idle = [...reg.entries()].filter(([, v]) => !v.attached).sort((a, b) => a[1].lastUsed - b[1].lastUsed);
  while (reg.size > 4 && idle.length) { const [k, v] = idle.shift(); v.dispose(); reg.delete(k); }
}

// ---- background mood
export function mood(m) { field?.setMood(m); }
export function warp() { field?.warp(); }
export function pulse() { field?.pulse(); }
export function sweep() { field?.sweep(); }
export function burst(x, y, n, power) { spark(x, y, n, undefined, power); }
export function retheme() { readTheme(); setTapColors(tapColors()); }
export { enableGyro, Q };
