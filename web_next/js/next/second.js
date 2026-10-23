// ATLAS (strategy 2, the 25K; internal key "second"): the EMA / MACD / S/R members pooled on their own account next to LIT.
//   ATLAS (top level)   everything about it on one page: status, today, the 25K eval card, the ATLAS brain per member,
//                       go / no-go, trades, rules, backtest + 25K eval odds, "with LIT" (SecondUI.atlas)
//   Today (top)         two cards: "LIT · 50K" and "ATLAS · 25K" (#twoStrat; status, today, this week, eval, next action)
//   #second (old link)  opens ATLAS (app.js go)
// Data: /api/next/second (engine/next_api.py second_view -> engine/second.dashboard_block of LiveBot.second, .atlas),
// /api/next/brain/second, /api/next/pc/status + /api/next/pc/account (the LIT card). Renderer: ./secondcore.js (a
// byte-identical copy of tools/web_public/secondcore.js, shared with the phone app). Read-only.
import { $, esc } from '../util.js';

let loading = null;

function core() {
  if (window.SecondUI && window.SecondUI.atlas) return Promise.resolve();
  if (!loading) loading = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL('./secondcore.js?v=6', import.meta.url).href;
    s.onload = () => ok(); s.onerror = () => { loading = null; bad(new Error('secondcore.js did not load')); };
    document.head.appendChild(s);
  });
  return loading;
}
async function getJ(u) { const r = await fetch(u); const d = await r.json().catch(() => ({})); if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status); return d; }
const brainOf = (d) => (!d || d.empty || d.error || !window.SecondUI) ? null : window.SecondUI.brainList(d, 'PC bot');

async function show() {
  const el = $('#page-second'); if (!el) return;
  el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  let S;
  try { await core(); S = await getJ('/api/next/second'); }
  catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  el.innerHTML = '<div id="scRoot"></div>';
  window.SecondUI.render($('#scRoot', el), S, {});
}
export const second = { show };

async function showAtlas() {
  const el = $('#page-atlas'); if (!el) return;
  if (!el.querySelector('#atRoot')) el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  let S, B = null;
  try {
    await core();
    [S, B] = await Promise.all([getJ('/api/next/second'), getJ('/api/next/brain/second').catch(() => null)]);
  } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  el.innerHTML = `<div class="nx-hero"><div><div class="nx-eyebrow">Strategy 2 · the 25K</div><h2>ATLAS</h2>
    <p class="muted">EMA + MACD + S/R on its own 25K, next to LIT on the 50K: status, brain, go / no-go, trades, rules, backtest. Read-only.</p></div></div><div id="atRoot"></div>`;
  window.SecondUI.atlas($('#atRoot', el), S, { brain: brainOf(B) });
}
export const atlas = { show: showAtlas };

// ------------------------------------------------------------------ Today: "LIT · 50K" and "ATLAS · 25K"
const ok = (v) => v != null && !isNaN(v);
function litCard(st, ac) {
  const v = (st && st.verdict) || {}, h = (st && st.health) || {}, e = (ac && ac.eval) || {}, pn = (ac && ac.pnl) || {}, a = (ac && ac.account) || {};
  const parts = [];
  if (ok(e.to_target)) parts.push('$' + Math.round(e.to_target).toLocaleString('en-US') + ' to pass');
  if (ok(e.session)) parts.push('session ' + e.session + '/' + (e.sessions || 10));
  if (ok(e.room)) parts.push('room $' + Math.round(e.room).toLocaleString('en-US'));
  return { name: 'LIT', plan: (a.plan ? 'MFFU ' + String(a.plan).replace(/^MFFU\s*/, '') : 'MFFU Builder 50K') + (a.name ? ' · ' + a.name : ''),
    status: v.label || v.code || (st && st.error ? 'NO ANSWER' : '—'), lvl: v.level === 'good' ? 'good' : v.level === 'bad' ? 'bad' : v.level ? 'warn' : '',
    today: pn.today, week: pn.week, prog: ok(e.profit) ? e.profit / 3000 : 0, progText: parts.join(' · ') || 'eval not reporting',
    next: (h.lit && h.lit.text) || (st && st.model_state) || '', goto: 'brain' };
}
let tTimer = null;
async function drawTwo() {
  const el = document.getElementById('twoStrat'); if (!el) return;
  const pg = document.getElementById('page-command');
  if (pg && !pg.classList.contains('active') && el.innerHTML) return;
  try {
    await core();
    const [st, ac, S, B] = await Promise.all([getJ('/api/next/pc/status').catch((e) => ({ error: e.message })), getJ('/api/next/pc/account?bars=0').catch(() => null),
      getJ('/api/next/second').catch(() => null), getJ('/api/next/brain/second').catch(() => null)]);
    const at = window.SecondUI.atlasCard(S, null, brainOf(B)); at.goto = 'atlas';
    el.innerHTML = window.SecondUI.twoCards([litCard(st, ac), at]);
  } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; }
}
export function initTwoCards() {
  drawTwo();
  clearInterval(tTimer); tTimer = setInterval(drawTwo, 60000);
}
