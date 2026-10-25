// PC dashboard: the learning pages (2026-10-25). Zlarior > Results > Learning (#learnlit) and ATLAS > Results > Learning
// (#learnatlas): the PC's real-fill costs (slippage, latency, commission, the cost reserve), its trade reviews against the
// backtest twin, the weekly live-vs-backtest gap and "The bot suggests" cards. GET /api/next/pc/learning
// (engine/live_learning.view), read-only. Renderer: ./learncore.js (byte-identical to tools/web_public/learncore.js).
import { $, api, esc } from '../util.js';

let LP = null;
function loadCore() {
  if (window.LearnUI && window.LearnUI.page) return Promise.resolve();
  if (LP) return LP;
  LP = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = new URL('./learncore.js?v=1', import.meta.url).href;
    s.onload = () => res(); s.onerror = () => { LP = null; rej(new Error('learncore.js did not load')); };
    document.head.appendChild(s);
  });
  return LP;
}

async function show(id, bots, title) {
  const el = $('#page-' + id); if (!el) return;
  el.innerHTML = `<header class="hero"><div><div class="eyebrow">${esc(title)} · results</div><h2>${esc(title)} is learning</h2>
    <p>What the bot learned from real trading, the way a disciplined trader reviews his week. Read-only: a suggestion shows the command that would approve it.</p></div></header><div class="ll-host"><div class="muted small">Loading…</div></div>`;
  let B = null;
  try { B = await api('/api/next/pc/learning'); } catch (e) { B = { error: e.message }; }
  try { await loadCore(); } catch (e) { el.querySelector('.ll-host').innerHTML = `<div class="muted small">${esc(e.message)}</div>`; return; }
  const host = el.querySelector('.ll-host');
  if (host) host.innerHTML = window.LearnUI.page(B, bots, { foot: 'engine/live_learning.py · research/writeups/live-learning.md' });
}

export const learnlit = { show: () => show('learnlit', ['lit'], 'Zlarior') };
export const learnatlas = { show: () => show('learnatlas', ['atlas', 'atlas_v2'], 'ATLAS') };
