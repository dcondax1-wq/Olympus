// PC dashboard: the REAL accounts (2026-10-28, both MFFU accounts trade for real). Read-only.
//   Home (cc.js)   <div id="ccReal">: "Today · real accounts" (one card per real account + the Strategy 3 slot, the ledger
//                  check, LIT vs ATLAS, what happened today) and <div id="ccSafe">: the Safety card
//   #real          "Real results": real trades only, running P&L, win rate, streaks, R distribution, $ by strategy,
//                  this week's report card, incidents, live vs the backtest band, CSV export
// Data: GET /api/next/board (engine/live_board.py, its "real" block) through board.js; renderer ./realcore.js
// (window.RealUI, byte-identical to tools/web_public/realcore.js). Nothing here talks to the bot.
import { $, esc } from '../util.js';
import { boardData, loadBoardCore, boardOpts } from './board.js';

let RP = null;
function loadReal() {
  if (window.RealUI && window.RealUI.today) return Promise.resolve();
  if (RP) return RP;
  RP = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = new URL('./realcore.js?v=4', import.meta.url).href;   // v3 (2026-10-29): BLITZ's own 25K as a third real card; v2 (2026-10-28): the 3D / glass look
    s.onload = () => res(); s.onerror = () => { RP = null; rej(new Error('realcore.js did not load')); };
    document.head.appendChild(s);
  });
  return RP;
}
const OPTS = () => ({ ...boardOpts(), where: 'pc' });
const S = { timer: null, last: null };
const active = () => document.getElementById('page-real')?.classList.contains('active');

// the Home slots (cc.js renders them and calls this after every render: the last board at once, then the fresh one)
export async function fillRealHome() {
  let painted = null;
  const paint = (B) => {
    const a = document.getElementById('ccReal'), b = document.getElementById('ccSafe');
    if (!window.RealUI || !B || (B === painted && a?.firstChild)) return;   // the same board twice: keep the cards (and their play-in) as they are
    painted = B;
    if (a) { a.innerHTML = window.RealUI.today(B, OPTS()); window.RealUI.wire(a, B, OPTS()); }
    if (b) { b.innerHTML = B.error ? '' : window.RealUI.safety(B, OPTS()); }
  };
  if (!document.getElementById('ccReal')) return;
  if (S.last) paint(S.last);
  try { await Promise.all([loadBoardCore(), loadReal()]); } catch { return; }
  S.last = await boardData(10000);
  paint(S.last);
}

async function draw(force) {
  const el = $('#page-real'); if (!el) return;
  if (!el.querySelector('.rc-host')) {
    el.innerHTML = `<header class="nx-hero cc-hero"><div><div class="nx-eyebrow">Results · real money</div><h2>Real results</h2>
      <p class="muted">Only what happened on the two MFFU accounts (never the paper run), next to what the backtest expects. Refreshes every 30 s.</p></div></header>
      <div class="rc-host"><div class="cc-skel"></div></div>`;
  }
  const host = el.querySelector('.rc-host');
  try { await Promise.all([loadBoardCore(), loadReal()]); } catch (e) { host.innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  const B = await boardData(force ? 0 : 10000);
  S.last = B;
  if (!active() || (!force && host.querySelector('.rc-lr.on'))) return;   // keep an open trade timeline still
  const y = window.scrollY;
  host.innerHTML = window.RealUI.results(B, OPTS());
  window.RealUI.wire(host, B, OPTS());
  if (!force) window.scrollTo(0, y);
}
export const real = {
  show: () => {
    draw(true);
    clearInterval(S.timer);
    S.timer = setInterval(() => { if (active()) draw(false); else clearInterval(S.timer); }, 30000);
  },
};
