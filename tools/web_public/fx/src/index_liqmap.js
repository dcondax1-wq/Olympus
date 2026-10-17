// PRIVATE test index for the liqmap view (deleted after testing): core + LiquidityMap only, same mount API as index.js.
import { THREE, Q, setLevel as setQuality, readTheme, wake, toScreen } from './core.js';
import { LiquidityMap } from './liqmap.js';

const KINDS = { liqmap: LiquidityMap };
const reg = new Map();
let inited = false;
export function supported() { try { return !!document.createElement('canvas').getContext('webgl2'); } catch { return false; } }
export function init({ level = 'max' } = {}) {
  if (inited) return Q.level;
  inited = true; readTheme(); setLevel(level);
  window.__LEFX = { Q, reg, toScreen, THREE };
  return Q.level;
}
export function setLevel(level) {
  const lv = level === 'off' || !supported() ? 'off' : level;
  setQuality(lv); document.documentElement.dataset.fx = lv;
  if (lv === 'off') { for (const v of reg.values()) v.dispose(); reg.clear(); return lv; }
  wake(); return lv;
}
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
  return v;
}
export function get(key) { return reg.get(key) || null; }
export function detachAll() { for (const v of reg.values()) v.detach(); }
export function scene() { } export function warp() { } export function pulse() { } export function ripple() { return false; }
export { Q };
