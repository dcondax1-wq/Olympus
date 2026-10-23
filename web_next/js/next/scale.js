// Data → Scaling plan: "you are at step N; next step: <action> when <trigger>; progress X%", the ladder 2 -> 4 -> 6 -> 8 ->
// 10 accounts (LIT + ATLAS) with $ a month on 2026-like and 2025-like trades, fees, risk at once, eval $ and months to get
// there. Data: /api/next/scale (engine/next_api.py -> engine/scale_plan.pc_view: business.json + the running PC bot's LIT
// eval, extra accounts and account B). Renderer: ./scalecore.js (a byte-identical copy of tools/web_public/scalecore.js,
// shared with the phone app). Read-only.
import { $, esc } from '../util.js';

let S = null, loading = null;

function core() {
  if (window.ScaleUI) return Promise.resolve();
  if (!loading) loading = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL('./scalecore.js?v=1', import.meta.url).href;
    s.onload = () => ok(); s.onerror = () => { loading = null; bad(new Error('scalecore.js did not load')); };
    document.head.appendChild(s);
  });
  return loading;
}

async function show() {
  const el = $('#page-scale'); if (!el) return;
  if (!S) el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  try {
    await core();
    const r = await fetch('/api/next/scale');
    const d = await r.json();
    if (!r.ok || d.error) { el.innerHTML = `<div class="banner warn">${esc(d.error || 'HTTP ' + r.status)}</div>`; return; }
    S = d;
  } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  el.innerHTML = '<div id="scRoot"></div>';
  window.ScaleUI.render($('#scRoot', el), S);
}
export const scale = { show };
