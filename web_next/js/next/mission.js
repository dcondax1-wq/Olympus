// PC dashboard: Mission Control (2026-10-29, owner: "make it look cooler ... features I should have had"; read-only).
//   #mission   the three bots in orbit (Zlarior 50K, ATLAS 25K, BLITZ 25K: "paper / not live yet" until its account exists),
//              every number per account, today's mission, countdowns and the features (if it stops out now, why no trade
//              yet, session timeline, alerts center, health constellation, eval runway, streaks & consistency, daily loss &
//              week pace, next news). Renderer: ./missioncore.js (window.MissionUI, byte-identical to tools/web_public/).
//   3D sync    initMissionSync(): every 15 s the deep-space satellites follow each bot (armed / in a trade), a shooting star
//              for each newly closed trade (green win / red loss), the aurora follows today's real P&L (fx3d.js hooks).
// Data: GET /api/next/board (board.js, cached), GET /api/next/liveview (BLITZ's thinking + the feed, only while this page
// is open), GET /api/next/news?compact=1 (the day's events). Nothing here talks to the bot.
import { $, esc } from '../util.js';
import { boardData } from './board.js';
import { fxBots, fxShoot, fxPnl, fxReady } from './fx3d.js';
import { depth } from './depth.js';

(function ensure() {
  for (const [href, v] of [['/css/mission.css', 1]]) {
    if (!document.querySelector(`link[href^="${href}"]`)) { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = `${href}?v=${v}`; document.head.appendChild(l); }
  }
  if (!document.getElementById('page-mission')) {
    const ref = document.getElementById('page-cc') || document.querySelector('section.page');
    const s = document.createElement('section'); s.className = 'page'; s.id = 'page-mission';
    s.innerHTML = '<div class="empty">Loading Mission Control…</div>';
    if (ref?.parentNode) ref.parentNode.insertBefore(s, ref.nextSibling); else document.body.appendChild(s);
  }
})();

let CP = null;
export function loadMissionCore() {
  if (window.MissionUI && window.MissionUI.page) return Promise.resolve();
  if (CP) return CP;
  CP = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = new URL('./missioncore.js?v=2', import.meta.url).href;
    s.onload = () => res(); s.onerror = () => { CP = null; rej(new Error('missioncore.js did not load')); };
    document.head.appendChild(s);
  });
  return CP;
}
const S = { lv: null, lvAt: 0, news: null, newsAt: 0, timer: null, sync: null };
const active = () => document.getElementById('page-mission')?.classList.contains('active');
async function getJSON(url) { try { const r = await fetch(url); return r.ok ? await r.json() : null; } catch { return null; } }
async function liveview(maxAge) {
  if (S.lv && Date.now() - S.lvAt < maxAge) return S.lv;
  const d = await getJSON('/api/next/liveview?tf=5m'); S.lvAt = Date.now(); if (d && !d.error) S.lv = d; return S.lv;
}
async function news() {
  if (S.news && Date.now() - S.newsAt < 600000) return S.news;
  const d = await getJSON('/api/next/news?compact=1'); S.newsAt = Date.now();
  S.news = (d && Array.isArray(d.events) ? d.events : []).filter((e) => e && +e.t && /high|medium|fomc/i.test(String(e.impact || e.kind || '')))
    .map((e) => ({ t: +e.t, title: e.title, impact: String(e.impact || 'high').toLowerCase() }));
  return S.news;
}
async function model(maxAge = 10000, withLv = false) {
  const [board, lv, nw] = await Promise.all([boardData(maxAge), withLv ? liveview(30000) : Promise.resolve(S.lv), news()]);
  return { now: Date.now() / 1000, board: board && !board.error ? board : null, lv, news: nw, cloud: null, where: 'pc' };
}

async function draw(force) {
  const el = $('#page-mission'); if (!el) return;
  try { await loadMissionCore(); } catch (e) { el.innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  const M = await model(force ? 0 : 10000, true);
  if (!active() && !force) return;
  const y = window.scrollY, open = [...el.querySelectorAll('details.mc-why')].map((d) => d.open);
  el.innerHTML = M.board ? window.MissionUI.page(M, { go: (id) => `data-goto="${id}"` })
    : `<div class="card"><h3>Mission Control</h3><p class="muted">Waiting for the live board (GET /api/next/board).</p></div>`;
  if (open.length) el.querySelectorAll('details.mc-why').forEach((d, i) => { if (open[i] != null) d.open = open[i]; });
  window.MissionUI.wire(el);
  depth(el.querySelector('.mc-page'), 'mission');          // count-up numbers + the mouse tilt (depth.js)
  if (!force) window.scrollTo(0, y);
  sync(M);
}
export const mission = {
  show: () => {
    draw(true);
    clearInterval(S.timer);
    S.timer = setInterval(() => { if (active()) draw(false); else clearInterval(S.timer); }, 15000);
  },
};

// ------------------------------------------------------------------ the 3D scene follows the bots
const SEEN = 'nx.mc.seen';
function sync(M) {
  if (!fxReady() || !window.MissionUI || !M || !M.board) return;
  const MU = window.MissionUI;
  try {
    fxBots(MU.botStates(M));
    const A = MU.accounts(M).filter((a) => !a.placeholder && typeof a.today === 'number');
    if (A.length) fxPnl(A.reduce((s, a) => s + a.today, 0));
    const C = MU.closed(M), ids = C.map((c) => c.id);
    let seen = null; try { seen = JSON.parse(localStorage.getItem(SEEN) || 'null'); } catch { seen = null; }
    if (!seen) { try { localStorage.setItem(SEEN, JSON.stringify(ids.slice(0, 40))); } catch { } return; }
    const fresh = C.filter((c) => !seen.includes(c.id) && Date.now() / 1000 - c.t < 6 * 3600).slice(0, 3);
    fresh.forEach((c, i) => setTimeout(() => fxShoot((c.usd || 0) >= 0 ? 'win' : 'loss'), 400 + i * 1400));
    if (fresh.length) try { localStorage.setItem(SEEN, JSON.stringify([...new Set(ids.concat(seen))].slice(0, 60))); } catch { }
  } catch (e) { console.warn('mission 3D sync', e); }
}
export function initMissionSync() {
  const run = async () => { if (document.hidden || !fxReady()) return; try { await loadMissionCore(); sync(await model(15000)); } catch { } };
  setTimeout(run, 2500);
  clearInterval(S.sync); S.sync = setInterval(run, 15000);
}
