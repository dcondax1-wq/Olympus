// Data → Second strategies (PAPER): the EMA / MACD / S/R research winners run next to LIT on the PC bot's bars, paper only.
// Data: /api/next/second (engine/next_api.py second_view -> engine/second.dashboard_block of LiveBot.second). Renderer:
// ./secondcore.js (a byte-identical copy of tools/web_public/secondcore.js, shared with the phone app). Read-only.
import { $, esc } from '../util.js';

let loading = null;

function core() {
  if (window.SecondUI) return Promise.resolve();
  if (!loading) loading = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL('./secondcore.js?v=2', import.meta.url).href;
    s.onload = () => ok(); s.onerror = () => { loading = null; bad(new Error('secondcore.js did not load')); };
    document.head.appendChild(s);
  });
  return loading;
}

async function show() {
  const el = $('#page-second'); if (!el) return;
  el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  let S;
  try {
    await core();
    const r = await fetch('/api/next/second');
    S = await r.json();
    if (!r.ok || S.error) { el.innerHTML = `<div class="banner warn">${esc(S.error || 'HTTP ' + r.status)}</div>`; return; }
  } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  el.innerHTML = '<div id="scRoot"></div>';
  window.SecondUI.render($('#scRoot', el), S, {});
}
export const second = { show };
