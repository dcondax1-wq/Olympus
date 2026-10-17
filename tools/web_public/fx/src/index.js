// Public API of the 3D layer (bundled to fx.js). Both dashboards load it lazily after the first paint:
//   const FX = await import('./fx.js');  FX.init({ level: 'max' | 'lite' | 'off', gyro });
//   FX.mount('trades-galaxy', el, 'galaxy', rows, { onPick });   // views are reused when the page re-renders
//   FX.detachAll()  before a page replaces its HTML;  FX.mood({...}) FX.warp() FX.pulse()
//   FX.scene(pageId)  the background's mood for a page: palette, galaxy orientation and spin, blended in over ~1.5 s.
//     Presets: today chart trades results lab losses eval engine settings; every page id of both dashboards maps to one
//     (replays/stops -> trades, experiments/writeups/run/compare/learned/study -> lab, system/cold/sources/modules -> engine,
//     data -> results, mffu -> eval; anything else -> today). Returns the preset used. Call it on every route change
//     (next to FX.warp()). FX.scenes lists the presets.
//   FX.ripple(clientX, clientY)  a wave through the background at a screen point (taps on empty background do it already).
// Kinds for FX.mount (data shapes in each file's header): orb galaxy city candles constellation ribbon reactor pipeline losses jarvis
//   newsradar montecarlo heat liqmap weekring.
import { THREE, Q, setLevel as setQuality, readTheme, theme, enableGyro, wake, toScreen } from './core.js';
import { Field } from './field.js';
import { initTaps, spark, setTapColors, setTaps, setBgTap } from './taps.js';
import { resolveScene, sceneNames } from './field.js';
import { Orb } from './orb.js';
import { Galaxy } from './galaxy.js';
import { City } from './city.js';
import { Candles } from './candles.js';
import { Constellation } from './constellation.js';
import { Ribbon } from './ribbon.js';
import { Reactor } from './reactor.js';
import { Pipeline } from './pipeline.js';
import { Losses } from './losses.js';
import { Jarvis } from './jarvis.js';
import { NewsRadar } from './newsradar.js';
import { MonteCarlo } from './montecarlo.js';
import { HeatCube } from './heat.js';
import { LiquidityMap } from './liqmap.js';
import { WeekRing } from './weekring.js';

export const version = 1;
const KINDS = { orb: Orb, galaxy: Galaxy, city: City, candles: Candles, constellation: Constellation, ribbon: Ribbon, reactor: Reactor, pipeline: Pipeline, losses: Losses, jarvis: Jarvis,
  newsradar: NewsRadar, montecarlo: MonteCarlo, heat: HeatCube, liqmap: LiquidityMap, weekring: WeekRing };
const reg = new Map();
let field = null, bg = null, inited = false, sceneName = 'today';

export function supported() {
  try { const c = document.createElement('canvas'); return !!c.getContext('webgl2'); } catch { return false; }
}
const tapColors = () => ['#' + theme.accent.getHexString(), '#' + theme.accent2.getHexString(), '#ff2bd6', '#c084fc', '#ffffff'];

export function init({ level = 'max', gyro = false } = {}) {
  if (inited) return Q.level;
  inited = true;
  readTheme();
  initTaps({ colors: tapColors() });
  setBgTap((x, y) => (field ? field.ripple(x, y) : false));
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
    field = new Field(); field.attach(bg); field.setScene(sceneName, true);
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
export function scene(name) { sceneName = resolveScene(name); field?.setScene(sceneName); document.documentElement.dataset.fxScene = sceneName; return sceneName; }
export function ripple(x, y) { return field ? field.ripple(x, y) : false; }
export const scenes = sceneNames;
export function warp() { field?.warp(); }
export function pulse() { field?.pulse(); }
export function sweep() { field?.sweep(); }
export function burst(x, y, n, power) { spark(x, y, n, undefined, power); }
export function retheme() { readTheme(); setTapColors(tapColors()); }
export { enableGyro, Q };
