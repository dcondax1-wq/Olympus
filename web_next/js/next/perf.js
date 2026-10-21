// Data → Performance: is live inside the backtest's expected range, live vs backtest on the same days, exit efficiency,
// robustness (+ the look-ahead audit of the research runs), the monthly out-of-sample scoreboard and the status page.
// Data: /api/next/perf (engine/next_api.py perf -> engine/perf.py pc_view). Renderer: ./perfcore.js (a byte-identical copy
// of tools/web_public/perfcore.js, shared with the phone app). Read-only.
import { $, esc } from '../util.js';

let P = null, tab = 'range', loading = null;
try { tab = localStorage.getItem('le-perf-tab') || 'range'; } catch (e) { /* private mode */ }

function core() {
  if (window.PerfUI) return Promise.resolve();
  if (!loading) loading = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL('./perfcore.js?v=1', import.meta.url).href;
    s.onload = () => ok(); s.onerror = () => { loading = null; bad(new Error('perfcore.js did not load')); };
    document.head.appendChild(s);
  });
  return loading;
}

async function show() {
  const el = $('#page-perf'); if (!el) return;
  if (!P) el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  try {
    await core();
    const r = await fetch('/api/next/perf');
    const d = await r.json();
    if (!r.ok || d.error) { el.innerHTML = `<div class="banner warn">${esc(d.error || 'HTTP ' + r.status)}</div>`; return; }
    P = d;
  } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  const h = (P.range && P.range.headline) || 'Expected range, live vs backtest, exit efficiency, robustness, months, status';
  el.innerHTML = `<div class="nx-hero-sub muted" style="margin:0 0 10px">${esc(h)}</div><div id="pfRoot"></div>`;
  window.PerfUI.render($('#pfRoot', el), P, { tab, onTab: (t) => { tab = t; try { localStorage.setItem('le-perf-tab', t); } catch (e) { /* ignore */ } } });
}
export const perf = { show };
