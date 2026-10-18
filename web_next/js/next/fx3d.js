// 3D layer on the PC dashboard: the same bundle as the phone site (tools/web_public/fx, built to /js/fx.js).
// It loads after the first paint and only where WebGL2 works; Settings > Interface switches it Max / Lite / Off.
// Pages call mount3d(key, el, kind, data, opts): null while it is off or still loading, and the page's 2D view stays.
// Views asked for before the bundle arrived are mounted as soon as it does.
import { $, esc, store, fmtN, etStr, api } from '../util.js';
import { L, onLive } from '../dash/live.js';
import { S } from '../state.js';

let FX = null;
const pend = new Map();
const root = document.documentElement;
export const fxLevel = () => store.get('nx.fx', 'max');

export async function initFX() {
  const lv = fxLevel();
  root.dataset.fx = lv;
  if (lv === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches) { root.dataset.fx = 'off'; return; }
  await new Promise(r => setTimeout(r, 300));
  try { FX = await import('/js/fx.js?v=b8f02cba'); } catch (e) { console.warn('3D layer not loaded', e); root.dataset.fx = 'off'; return; }
  if (!FX.supported()) { FX = null; root.dataset.fx = 'off'; return; }
  root.dataset.fx = FX.init({ level: lv });
  for (const [key, a] of pend) mount3d(key, ...a);
  pend.clear();
  mood();
  setInterval(mood, 60000);
  onLive(() => { mood(); oracle(); });
  oracle();
  document.addEventListener('le-appearance', () => FX?.retheme());
}

export function mount3d(key, el, kind, data, opts) {
  if (!el || fxLevel() === 'off') return null;
  if (!FX) { pend.set(key, [el, kind, data, opts]); return null; }
  const v = FX.mount(key, el, kind, data, opts);
  el.classList.toggle('fx-live', !!v);
  if (v) el.closest('[data-fx-card]')?.removeAttribute('hidden');
  return v;
}
export const fxWarp = () => FX?.warp();
export const fxScene = (page) => FX?.scene?.(page);   // per-page background mood (palette, galaxy tilt, spin)
export const fxPulse = () => FX?.pulse();

export function setFxLevel(lv) {
  store.set('nx.fx', lv);
  if (!FX) { if (lv !== 'off') initFX(); else root.dataset.fx = 'off'; return; }
  root.dataset.fx = FX.setLevel(lv);
  if (lv === 'off') document.querySelectorAll('[data-fx-card]').forEach(c => c.hidden = true);
}

// ------------------------------------------------------------------ mood + the Live Oracle on Today
const NY = (t = Date.now()) => { const s = new Date(t).toLocaleString('en-US', { timeZone: 'America/New_York', hour12: false, weekday: 'short', hour: '2-digit', minute: '2-digit' });
  const [wd, hm] = s.split(' '); const [h, m] = hm.split(':').map(Number); return { wd: wd.replace(',', ''), m: (h % 24) * 60 + m }; };
// the live strategy's entry window (LIT: 02:00-15:30 ET, Mon-Fri); the FX mood key keeps its name
function killzone() { const { wd, m } = NY(); return !['Sat', 'Sun'].includes(wd) && m >= 120 && m < 930; }
function mood() {
  const s = L.live?.state || {}, pos = s.position;
  FX?.mood({ killzone: killzone(), live: !!L.live?.running, cold: s.equity_filter?.on === false, pnl: +(L.live?.day_pnl_routed || 0) });
  return { killzone: killzone(), live: !!L.live?.running, inTrade: !!pos, side: pos?.dir };
}
// bot stopped (no live bars): the last bars of the NQ data file and the levels the dash computes from them, every 5 min
let lastSig = '', fb = null, fbAt = 0;
async function fallback() {
  if (Date.now() - fbAt < 300000) return fb; fbAt = Date.now();
  try {
    const lq = await api('/api/dash/liquidity');
    if (lq?.status !== 'ok') return fb;
    const r = await api(`/api/bars?sym=NQ&tf=5m&start=${lq.t - 7200}`);
    const lv = [...(lq.pools || []), ...(lq.levels || []).filter(x => x.kind !== 'open' && (x.side === 'H' || x.side === 'L') && !x.swept)];
    fb = { bars: r.t.map((t, i) => [t, r.o[i], r.h[i], r.l[i], r.c[i]]).slice(-12), price: lq.price, pools: lv.map(x => ({ price: x.price, side: x.side, label: x.label, strength: x.strength })) };
    oracle();
  } catch { }
  return fb;
}
function oracle() {
  const el = $('#nxOrb'); if (!el || !FX) return;
  const lv = L.live || {}, s = lv.state || {};
  let bars = (lv.bars || []).slice(-12).map(b => [b.time, b.open, b.high, b.low, b.close]), price = s.price ?? bars.at(-1)?.[4];
  let pools = (s.active_pools || []).map(p => ({ price: p.price, side: p.side, label: p.label, strength: p.strength }));
  const fromFile = !bars.length;
  if (fromFile) {
    fallback(); if (fb) { bars = fb.bars; price = fb.price; pools = fb.pools; }
    const ls = S.res?.model === 'lit' ? S.res.state : null;     // bot stopped: the LIT levels at the last bar (/api/next/lit_backtest)
    if (ls?.active_pools?.length) pools = ls.active_pools.filter(p => p.kind !== 'vix').map(p => ({ price: p.price, side: p.side, label: p.label, strength: p.strength }));
  }
  pools = pools.filter(p => price && Math.abs(p.price - price) / price < 0.03);
  mount3d('today-orb', el, 'orb', { bars, pools, price, mood: mood() });
  const pos = s.position, t = $('#nxOracleT');
  const sig = [s.model_state, price, pos?.entry, lv.running, bars.length].join('|');
  if (t && sig !== lastSig) {
    lastSig = sig;
    t.innerHTML = `<div class="nx-eyebrow">PC paper bot · ${lv.running ? 'running' : 'stopped'}${killzone() ? ' · LIT entry window open' : ''}</div>
      <h2>${esc(s.model_state || (bars.length ? (killzone() ? 'Watching the LIT levels' : 'Outside the LIT entry window (02:00-15:30 ET)') : 'Waiting for bars'))}</h2>
      <p class="muted">${pos ? `In ${pos.dir === 1 ? 'LONG' : 'SHORT'} @ ${fmtN(pos.entry)} → TP ${fmtN(pos.target)} / SL ${fmtN(pos.stop)}` : 'Flat. Paper only, never places real orders.'}</p>
      <div class="nx-oracle-px"><span class="muted small">NQ futures · ${fromFile ? 'last bar in the data file' : 'live feed'}</span><b class="mono">${price != null ? fmtN(price) : '—'}</b>
        <span class="muted small">${bars.length ? etStr(bars.at(-1)[0]) + ' ET · last ' + bars.length + ' bars in the orb' : ''}</span></div>`;
  }
}
