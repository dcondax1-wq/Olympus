// PC dashboard: the Scorecard (2026-11-03 night quest; read-only: nothing here talks to the bot).
//   #pro   Zenith score, expectancy in $, eval pace, underwater vs the MFFU floor, playbook, what-if sizing, $ by tag
//          (sidebar Insight). Renderer ./procore.js (window.ProUI, byte-identical to tools/web_public/procore.js).
// Data: GET /api/next/lit_backtest?period=all (the live-settings LIT replay, research/lab/backtest_live.json; 5-25 s the
// first time, cached here 10 min), the live board (board.js boardData). The part sits in nx.proPart (this browser).
import { $, esc, store } from '../util.js';
import { boardData } from './board.js';

const V = 1;
(function ensureSec() {
  if (document.getElementById('page-pro')) return;
  const ref = document.getElementById('page-deck') || document.querySelector('section.page');
  const s = document.createElement('section'); s.className = 'page'; s.id = 'page-pro'; s.innerHTML = '<div class="empty">Loading the Scorecard…</div>';
  if (ref && ref.parentNode) ref.parentNode.insertBefore(s, ref.nextSibling); else document.body.appendChild(s);
})();
let coreP = null;
function core() {
  if (window.ProUI) return Promise.resolve();
  if (!coreP) coreP = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL(`./procore.js?v=${V}`, import.meta.url).href;
    s.onload = () => ok(); s.onerror = () => { coreP = null; bad(new Error('procore.js did not load')); };
    document.head.appendChild(s);
  });
  return coreP;
}
let BT = null, BT_AT = 0, BT_BUSY = null;
async function backtest() {
  if (BT && Date.now() - BT_AT < 600000) return BT;
  if (BT_BUSY) return BT_BUSY;
  BT_BUSY = fetch('/api/next/lit_backtest?period=all', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null)
    .then((j) => { BT_BUSY = null; if (j && !j.error) { BT = j; BT_AT = Date.now(); } return BT; });
  return BT_BUSY;
}
const go = (id, arg) => (id === 'pro' ? `data-pro-part="${esc(arg || 'score')}"` : `data-goto="${esc(id)}"`);
async function draw() {
  const el = $('#page-pro'); if (!el) return;
  try { await core(); } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  const [bt, board] = await Promise.all([backtest(), boardData(10000).catch(() => null)]);
  const PU = window.ProUI, part = store.get('nx.proPart', 'score');
  const model = () => PU.model({ now: Date.now() / 1000, span: PU.pref().span, mult: PU.pref().mult, trades: (bt && bt.trades) || [],
    real: (board && !board.error && board.trades) || [], periods: (bt && bt.periods) || {}, board: board && !board.error ? board : null, tags: store.get('jtags', {}) || {} });
  el.innerHTML = PU.page(model(), part, { go }) + (bt ? '' : '<p class="pr-foot">The LIT replay did not load (run python tools/export_backtest.py on the PC); the real-trade span still works.</p>');
  PU.wire(el, draw, { model });
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('#page-pro [data-pro-part]'); if (!b) return;
  e.preventDefault(); store.set('nx.proPart', b.dataset.proPart); draw();
});
export const pro = { show: () => { draw(); } };
