// PC dashboard: the night-3 layer (2026-10-30, owner: "more very useful features ... organized, clean ... shock me"; read-only).
//   Home      one status bar on top ("is everything OK right now?": PC bot, NinjaTrader, feed, each bot, the next window,
//             alerts; a click opens every line with its fix) and the "Sunday open" card on weekends (the clock change,
//             the CME reopen, what each bot does first, a readiness list). Renderer ./statuscore.js (window.StatusUI,
//             byte-identical to tools/web_public/statuscore.js), on MissionUI's accounts so every number matches.
//   motion    page entrances and card rises (css/polish.css); reduced motion = none
//   sky       a little parallax from the mouse (fx3d's FX.parallax when the 3D scene has it, the CSS sky otherwise)
// Data: GET /api/next/board (board.js, cached) and /api/next/news?compact=1. Nothing here talks to the bot.
import { boardData } from './board.js';
import { loadMissionCore } from './mission.js';

const V = 1;
let SP = null;
function loadStatusCore() {
  if (window.StatusUI) return Promise.resolve();
  if (SP) return SP;
  SP = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL(`./statuscore.js?v=${V}`, import.meta.url).href;
    s.onload = () => ok(); s.onerror = () => { SP = null; bad(new Error('statuscore.js did not load')); };
    document.head.appendChild(s);
  });
  return SP;
}
(function css() {
  if (!document.querySelector('link[href^="/css/polish.css"]')) { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = `/css/polish.css?v=${V}`; document.head.appendChild(l); }
})();
async function getJSON(url) { try { const r = await fetch(url, { cache: 'no-store' }); return r.ok ? await r.json() : null; } catch { return null; } }
const N = { at: 0, v: [] };
async function news() {
  if (Date.now() - N.at < 600000) return N.v;
  const d = await getJSON('/api/next/news?compact=1'); N.at = Date.now();
  N.v = (d && Array.isArray(d.events) ? d.events : []).filter((e) => e && +e.t).map((e) => ({ t: +e.t, title: e.title, impact: String(e.impact || 'high').toLowerCase() }));
  return N.v;
}
let LAST = null;
async function model() {
  const [b, nw] = await Promise.all([boardData(15000), news()]);
  return { now: Date.now() / 1000, where: 'pc', board: b && !b.error ? b : null, lv: null, news: nw, cloud: null, blitz: null, alerts: [] };
}
const active = (p) => document.getElementById('page-' + p)?.classList.contains('active');
const go = (id) => `data-goto="${id}"`;
function place() {
  const el = document.getElementById('page-cc'); if (!el || !LAST || !window.StatusUI) return;
  const SU = window.StatusUI;
  let box = el.querySelector(':scope > #nxStatusHome');
  if (!box) { box = document.createElement('div'); box.id = 'nxStatusHome'; box.className = 'nx-st-home'; el.prepend(box); }
  else if (el.firstElementChild !== box) el.prepend(box);
  const more = `<a class="pl-btn" ${go('mission')}>Mission Control</a><a class="pl-btn" ${go('board')}>Live board</a><a class="pl-btn" ${go('start')}>Start page</a>`;
  const row = (SU.week ? SU.week(LAST) : '') + SU.sunday(LAST, { where: 'pc' });
  const html = SU.bar(LAST, { open: SU.isOpen(), more, where: 'pc', go }) + (row ? `<div class="nx-st-row">${row}</div>` : '');
  if (box.__h !== html) { box.innerHTML = html; box.__h = html; SU.tick(box); }
  SU.wire(box);
}
async function refresh() {
  try { await Promise.all([loadStatusCore(), loadMissionCore()]); } catch (e) { return; }
  LAST = await model();
  window.StatusUI.css();
  if (active('cc')) place();
}
export function initPolish() {
  const el = document.getElementById('page-cc');
  if (el && !el.__stObs) {
    el.__stObs = new MutationObserver(() => { if (LAST && active('cc') && el.firstElementChild?.id !== 'nxStatusHome') place(); });
    el.__stObs.observe(el, { childList: true });
  }
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 15000);
  addEventListener('hashchange', () => setTimeout(() => { if (active('cc')) place(); }, 300));
  document.addEventListener('click', (e) => { if (e.target.closest('[data-goto],[data-page],#nav a')) setTimeout(() => { if (active('cc')) place(); }, 400); });
  // a little parallax from the mouse on the sky (reduced motion: none)
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const S = document.querySelector('.space-css');
  if (S && !calm) {
    let raf = 0, x = 0, y = 0;
    addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse') return;
      x = (e.clientX / innerWidth - 0.5) * 12; y = (e.clientY / innerHeight - 0.5) * 8;
      if (!raf) raf = requestAnimationFrame(() => { raf = 0; S.style.setProperty('--px', x.toFixed(2)); S.style.setProperty('--py', y.toFixed(2)); const F = window.FX; if (F && typeof F.parallax === 'function') F.parallax(x / 12, y / 12); });
    }, { passive: true });
  }
  document.documentElement.dataset.polish = 'on';
}
