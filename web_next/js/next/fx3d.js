// 3D layer on the PC dashboard: the same bundle as the phone site (tools/web_public/fx, built to /js/fx.js).
// It loads after the first paint and only where WebGL2 works; Settings > Interface switches it Max / Lite / Off.
// Pages call mount3d(key, el, kind, data, opts): null while it is off or still loading, and the page's 2D view stays.
// Views asked for before the bundle arrived are mounted as soon as it does.
import { $, esc, store, fmtN, etStr, api } from '../util.js';
import { L, onLive } from '../dash/live.js';
import { S } from '../state.js';

let FX = null;
// the bundle's URL: fx/build.mjs stamps the bundle's content hash into the next line (the first fx.js URL of this file)
const FX_URL = '/js/fx.js?v=d4f02163';
const pend = new Map();
const root = document.documentElement;
// Deep space by default (owner 2026-10-29: "make it look cooler ... almost like 3D space"; it was off since 2026-10-25, calm).
// One-time: an 'off' saved under the calm default is cleared once; a choice made after this version is kept. Automated
// browsers (tests) start off unless the URL asks (?fx=max|lite), so the other UI tests stay fast and identical.
try { if (!store.get('nx.fx2', false)) { if (store.get('nx.fx', null) === 'off') localStorage.removeItem('nx.fx'); store.set('nx.fx2', true); } } catch { }
const FXQ = (location.search.match(/[?&]fx=(max|lite|off)\b/) || [])[1];
export const fxLevel = () => FXQ || store.get('nx.fx', navigator.webdriver ? 'off' : 'max');
export const fxBg = () => store.get('nx.fxbg', 'space');

export async function initFX() {
  const lv = fxLevel();
  root.dataset.fx = lv;
  if (lv === 'off') { root.dataset.fx = 'off'; return; }      // reduced motion: space.js draws one still frame
  await new Promise(r => setTimeout(r, 300));
  try { FX = await import(FX_URL); } catch (e) { console.warn('3D layer not loaded', e); root.dataset.fx = 'off'; return; }
  if (!FX.supported()) { FX = null; root.dataset.fx = 'off'; return; }
  root.dataset.fx = FX.init({ level: lv, bg: fxBg() });
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
// the bundle itself, also while the background is off (the Holodeck page, js/next/holo.js, runs its own 3D view)
export const fxModule = () => (FX ? Promise.resolve(FX) : import(FX_URL));
export const fxWarp = () => FX?.warp();
export const fxScene = (page) => FX?.scene?.(page);   // per-page background mood (palette, galaxy tilt, spin)
export const fxPulse = () => FX?.pulse();
// the deep-space scene's live hooks (js/next/mission.js): satellites per bot, a shooting star per closed trade, the aurora tint
export const fxBots = (st) => FX?.bots?.(st);
export const fxShoot = (kind) => FX?.shoot?.(kind);
export const fxPnl = (usd) => FX?.pnl?.(usd);
export const fxStats = () => FX?.stats?.() || null;
export const fxReady = () => !!FX;
export function setFxBg(kind) { store.set('nx.fxbg', kind); FX?.background?.(kind); }

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
