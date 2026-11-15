// PC dashboard: the Live board (2026-10-26, read-only). Page #board ("Live board" in the sidebar under Home) and the
// "Right now" cut on the Command center (cc.js calls fillBoardHome after each render). Data: GET /api/next/board
// (engine/board_api.py -> engine/live_board.py), trade pictures GET /api/next/charts (pics.js). Renderer: ./boardcore.js
// (window.BoardUI, byte-identical to tools/web_public/boardcore.js). Nothing here talks to the bot.
import { $, esc, downloadFile } from '../util.js';
import { charts as loadCharts, loadPics } from './pics.js';

let CP = null;
const S = { d: null, at: 0, timer: null, ch: null };
function loadCore() {
  if (window.BoardUI && window.BoardUI.page) return Promise.resolve();
  if (CP) return CP;
  CP = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = new URL('./boardcore.js?v=3', import.meta.url).href;
    s.onload = () => res(); s.onerror = () => { CP = null; rej(new Error('boardcore.js did not load')); };
    document.head.appendChild(s);
  });
  return CP;
}
async function getBoard(maxAge = 5000) {
  if (S.d && Date.now() - S.at < maxAge) return S.d;
  try {
    const r = await fetch('/api/next/board');
    const d = await r.json().catch(() => ({ error: 'HTTP ' + r.status }));
    S.d = r.ok ? d : { error: d.error || 'HTTP ' + r.status };
  } catch (e) { S.d = S.d && !S.d.error ? S.d : { error: e.message }; }
  S.at = Date.now();
  return S.d;
}
const OPTS = () => ({ charts: S.ch, where: 'pc', go: (id) => `data-goto="${id}"`, download: (n, t) => downloadFile(n, t, 'text/csv') });
const active = () => document.getElementById('page-board')?.classList.contains('active');

async function draw(force) {
  const el = $('#page-board'); if (!el) return;
  if (!el.querySelector('.bd-host')) {
    el.innerHTML = `<header class="nx-hero cc-hero"><div><div class="nx-eyebrow">Home · live</div><h2>Live board</h2>
      <p class="muted">Right now on both accounts, today's map, the bot's health, the week and the eval, and every trade with its picture. Read-only; refreshes every 15 s.</p></div></header>
      <div class="bd-host"><div class="cc-skel"></div></div>`;
  }
  const host = el.querySelector('.bd-host');
  try { await loadCore(); } catch (e) { host.innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  const [B] = await Promise.all([getBoard(force ? 0 : 5000), S.ch ? null : loadPics().then(() => loadCharts()).then((c) => { S.ch = c; }).catch(() => null)]);
  if (!active()) return;
  const open = host.querySelector('.bd-hp.on')?.dataset.bdH;
  const y = window.scrollY;
  host.innerHTML = window.BoardUI.page(B, OPTS());
  window.BoardUI.wire(host, B, OPTS());
  if (open != null) host.querySelector(`[data-bd-h="${open}"]`)?.click();
  if (!force) window.scrollTo(0, y);
}

export const board = {
  show: () => {
    draw(true);
    clearInterval(S.timer);
    S.timer = setInterval(() => { if (active()) draw(false); else clearInterval(S.timer); }, 15000);
  },
};

// the Command center's "Right now" row (cc.js renders <div id="ccBoard"> and calls this after every render)
export async function fillBoardHome() {
  const paint = (B) => {
    const slot = document.getElementById('ccBoard'); if (!slot || !window.BoardUI) return;
    if (!B || B.error) { slot.innerHTML = ''; return; }
    slot.innerHTML = window.BoardUI.home(B, OPTS());
    window.BoardUI.wire(slot, B, OPTS());
  };
  if (!document.getElementById('ccBoard')) return;
  if (S.d && !S.d.error && window.BoardUI) paint(S.d);          // the last board at once (cc.js re-renders every 15 s)
  try { await loadCore(); } catch { return; }
  paint(await getBoard(10000));
}

// shared with real.js (the Home "Today" cards and the Real results page read the same board)
export { getBoard as boardData, loadCore as loadBoardCore, OPTS as boardOpts };
