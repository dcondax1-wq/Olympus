// Trades page: every trade of the live-settings replay (research/lab/backtest_live.json via /api/next/trades) with
// stop pts, micros, $ risk, R, half-size flag, and the per-trade report (why it entered, plan, result, lessons).
import { $, $$, api, esc, fmt$, fmtS$, fmtN, fmtR, cls, etStr, store } from '../util.js';
import { S } from '../state.js';
import * as chartPage from '../page-chart.js';
import { go } from '../app.js';
import { icon } from './icons.js';
import { lineChart, countAll } from './viz.js';
import { mount3d } from './fx3d.js';

// trade charts (the same tradechart.js as the phone site: tools/web_public/tradechart.js, copied to /js/tradechart.js by
// `cd tools/web_public/fx && npm run build`): a LIT trade drawn like TradingView's Long / Short Position tool, loaded on demand;
// records from /api/next/tradechart/<id> (research/lab/replays.json "charts", tools/export_replays.py)
let TCP = null;
const loadTC = () => TCP || (TCP = import('../tradechart.js?v=b1526d92').catch((e) => { TCP = null; throw e; }));
export function chartInto(box, t, opts = {}) {
  if (!box) return;
  if (!t?.chart) { box.innerHTML = '<div class="muted small">No chart for this trade: charts are drawn for the 2026 LIT replay trades (1-minute data).</div>'; return; }
  box.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  loadTC().then((TC) => TC.load(t.chart, { base: '/api/next/tradechart/', ext: '' }).then((rec) => { if (box.isConnected) TC.mount(box, rec, opts); }))
    .catch((e) => { console.warn('trade chart', e); if (box.isConnected) box.innerHTML = '<div class="muted small">The chart could not load: run <span class="mono">python tools/export_replays.py</span>.</div>'; });
}
const tcBtn = (t) => (t.chart ? `<span class="nx-tcb" role="button" tabindex="0" data-chart title="Open the trade chart">${icon('chart')}Chart</span>` : '');
export function tcCss() {
  if (!document.getElementById('nx-tc-css')) {
    const c = document.createElement('style'); c.id = 'nx-tc-css';
    c.textContent = `.nx-sheet.nx-sheet-tc{width:min(980px,calc(100vw - 24px))}.nx-tcbox{background:var(--surface-2,#161a23);border:1px solid var(--border,rgba(160,170,220,.12));border-radius:14px;padding:12px;min-height:120px;margin-bottom:6px}
.nx-tcb{display:inline-flex;align-items:center;gap:5px;padding:3px 10px 3px 8px;border-radius:999px;font:600 12px var(--sans,system-ui);color:var(--ink,#eef1f8);cursor:pointer;background:color-mix(in srgb,var(--brand,#6d7cff) 16%,transparent);border:1px solid color-mix(in srgb,var(--brand,#6d7cff) 45%,transparent)}
.nx-tcb svg{width:13px;height:13px}.nx-tcb:hover{background:color-mix(in srgb,var(--brand,#6d7cff) 28%,transparent)}`;
    document.head.appendChild(c);
  }
}
// the chart on its own, in a wide sheet (the Chart button on a trade row)
export function openChart(t) {
  openSheet(t, { chartOnly: true });
}

const st = { year: store.get('nx.trYear', '2026'), filter: 'all', q: '', sort: 'new', shown: 60, data: null, years: [] };
let loaded = null;

const FILTERS = [['all', 'All'], ['win', 'Wins'], ['loss', 'Losses'], ['long', 'Long'], ['short', 'Short'], ['half', 'Half size']];
const SORTS = [['new', 'Newest first'], ['old', 'Oldest first'], ['best', 'Best R'], ['worst', 'Worst R'], ['stop', 'Widest stop'], ['tight', 'Tightest stop']];

function stats(rows) {
  const n = rows.length, wins = rows.filter(t => t.pnl > 0);
  const gp = wins.reduce((a, t) => a + t.pnl, 0), gl = -rows.filter(t => t.pnl < 0).reduce((a, t) => a + t.pnl, 0);
  const days = rows.map(t => t.day).sort();
  const spanDays = n ? (Date.parse(days.at(-1)) - Date.parse(days[0])) / 864e5 : 0;
  const weeks = n ? Math.max(1, spanDays / 7) : 1, months = n ? Math.max(0.5, spanDays / 30.44) : null;
  let eq = 0, peak = 0, dd = 0;
  [...rows].sort((a, b) => a.entry_t - b.entry_t).forEach(t => { eq += t.pnl; peak = Math.max(peak, eq); dd = Math.min(dd, eq - peak); });
  return { n, win: n ? wins.length / n * 100 : 0, pf: gl ? gp / gl : null, net: gp - gl, avgR: n ? rows.reduce((a, t) => a + (t.r || 0), 0) / n : 0,
    half: rows.filter(t => t.half).length, tpw: n / weeks, dd, pm: months ? (gp - gl) / months : null, avg$: n ? (gp - gl) / n : null };
}

function pass(t) {
  const f = st.filter;
  if (f === 'win' && !(t.pnl > 0)) return false;
  if (f === 'loss' && !(t.pnl < 0)) return false;
  if (f === 'long' && t.side !== 'LONG') return false;
  if (f === 'short' && t.side !== 'SHORT') return false;
  if (f === 'half' && !t.half) return false;
  if (st.q) {
    const hay = [t.day, t.side, t.trigger, t.exit, t.grade, t.regime, t.target_label, ...(t.pools || []), ...(t.report?.lessons || []), ...(t.conf_tags || [])].join(' ').toLowerCase();
    if (!st.q.split(/\s+/).every(w => hay.includes(w))) return false;
  }
  return true;
}
function sorted(rows) {
  const k = { new: (a, b) => b.entry_t - a.entry_t, old: (a, b) => a.entry_t - b.entry_t, best: (a, b) => b.r - a.r, worst: (a, b) => a.r - b.r,
    stop: (a, b) => b.risk_pts - a.risk_pts, tight: (a, b) => a.risk_pts - b.risk_pts }[st.sort];
  return [...rows].sort(k);
}

function chip(txt, kind = '') { return `<span class="nx-chip ${kind}">${txt}</span>`; }

function row(t, i) {
  const win = t.pnl > 0, be = Math.abs(t.r) < 0.05;
  return `<button type="button" class="nx-trade ${win ? 'win' : be ? 'be' : 'loss'}" data-i="${i}">
    <span class="nx-trade-side ${t.side === 'LONG' ? 'L' : 'S'}">${icon(t.side === 'LONG' ? 'long' : 'short')}</span>
    <span class="nx-trade-main">
      <span class="nx-trade-top"><b>${esc(t.day)}</b><span class="muted">${etStr(t.entry_t)} ET</span><span class="nx-side-txt ${t.side === 'LONG' ? 'up' : 'dn'}">${t.side}</span>
        ${t.half ? chip('half size', 'warn') : ''}</span>
      <span class="nx-trade-meta">
        ${chip(`<i>stop</i> ${fmtN(t.risk_pts, 1)} pts`)}${chip(`<i>micros</i> ${t.qty}`)}${chip(`<i>risk</i> ${fmt$(t.risk_usd)}`)}
        ${chip(esc(t.trigger))}${chip(esc(t.exit))}${t.grade ? chip('grade ' + esc(t.grade)) : ''}${tcBtn(t)}
      </span>
    </span>
    <span class="nx-trade-res"><b class="${cls(t.r)}">${fmtR(t.r)}</b><span class="${cls(t.pnl)}">${fmtS$(t.pnl)}</span></span>
  </button>`;
}

function render() {
  tcCss();
  const el = $('#page-trades');
  if (!st.data) return;
  const all = st.data;
  const rows = sorted(all.filter(pass));
  const s = stats(rows);
  const yearOpts = [...st.years].reverse().map(y => [y, y]).concat([['all', 'All years']]);
  el.innerHTML = `
    <div class="nx-hero">
      <div><div class="nx-eyebrow">Live settings · ${loaded?.model === 'lit' ? 'LIT replay' : 'exact live-loop replay'}${loaded?.built ? ` · built ${esc(loaded.built)}` : ''}</div>
        <h2>${st.year === 'all' ? (loaded?.model === 'lit' ? 'Every LIT trade since 2021-11' : 'Every trade, 5 years') : st.year + ' trades'}</h2>
        <p class="muted">${loaded?.model === 'lit' ? 'Same LIT rules, sizing and weekly stop as <span class="mono">live_model.json</span> (2026 entries on 1-minute bars; 2021-25 on 5-minute bars, a reference).' : 'Same engine, sizing and cold-streak filter as <span class="mono">live_model.json</span>.'} Costs included. Tap a trade for the full report.</p></div>
      <div class="seg nx-seg-lg" id="trYear">${yearOpts.map(([v, l]) => `<button class="${v === st.year ? 'on' : ''}" data-v="${v}">${l}</button>`).join('')}</div>
    </div>
    <div class="nx-stats">
      <div class="nx-stat"><span>Trades</span><b data-count="${s.n}">${s.n}</b><em>${fmtN(s.tpw, 1)} / week · aim 2–4</em></div>
      <div class="nx-stat"><span>Net</span><b class="${cls(s.net)}" data-count="${s.net}" data-fmt="s$">${fmtS$(s.net)}</b><em>${s.pm != null ? fmtS$(s.pm) + ' a month · ' : ''}max DD ${fmt$(s.dd)}</em></div>
      <div class="nx-stat"><span>Profit factor</span><b>${s.pf != null ? fmtN(s.pf) : '—'}</b><em>win ${fmtN(s.win, 1)}%</em></div>
      <div class="nx-stat"><span>Avg R</span><b class="${cls(s.avgR)}">${fmtR(s.avgR)}</b><em>${s.avg$ != null ? fmtS$(s.avg$) + ' per trade' : 'per trade'}</em></div>
      <div class="nx-stat"><span>Half size</span><b data-count="${s.half}">${s.half}</b><em>${loaded?.model === 'lit' ? 'weekly-stop trades' : 'cold-streak trades'}</em></div>
    </div>
    <div class="card nx-glass fx-card" data-fx-card hidden><div class="card-h"><h3>Trade galaxy · ${rows.length} trades</h3><span class="muted small">every trade is a star: time → right, R ↑, stop size ↗ · drag to turn · click a star for its report</span></div><div class="fx3d galaxy" id="trGal"></div></div>
    <div class="card nx-glass"><div class="card-h"><h3>Equity · filtered trades</h3><span class="muted small">cumulative net $, oldest → newest</span></div><div id="trEq"></div></div>
    <div class="nx-toolbar">
      <div class="seg" id="trFilter">${FILTERS.map(([v, l]) => `<button class="${v === st.filter ? 'on' : ''}" data-v="${v}">${l}</button>`).join('')}</div>
      <label class="nx-field grow">${icon('search')}<input class="inp" id="trQ" placeholder="Search trigger, pool, lesson, tag…" value="${esc(st.q)}" autocomplete="off"></label>
      <select class="sel" id="trSort">${SORTS.map(([v, l]) => `<option value="${v}" ${v === st.sort ? 'selected' : ''}>${l}</option>`).join('')}</select>
    </div>
    <div class="nx-count muted small">${rows.length} of ${all.length} trades</div>
    <div class="nx-trades" id="trList">${rows.slice(0, st.shown).map(t => row(t, all.indexOf(t))).join('') || '<div class="empty">No trades match.</div>'}</div>
    ${rows.length > st.shown ? `<div class="nx-more"><button class="btn ghost" id="trMore">Show ${Math.min(60, rows.length - st.shown)} more</button></div>` : ''}`;
  countAll(el.querySelector('.nx-stats'));
  let eq = 0;
  lineChart($('#trEq'), [...rows].sort((a, b) => a.entry_t - b.entry_t).map(t => {
    eq += t.pnl;
    return { x: t.day.slice(2), y: eq, tip: `<b>${t.day} · ${t.side}</b><span>${fmtR(t.r)} · ${fmtS$(t.pnl)}</span><span>total ${fmtS$(eq)}</span>` };
  }), { h: 200, color: 'var(--accent)' });
  mount3d('trades-galaxy', $('#trGal'), 'galaxy', rows, { onPick: (t) => t && openSheet(t) });
  $('#trYear').onclick = (e) => { const b = e.target.closest('button'); if (b) { st.year = b.dataset.v; store.set('nx.trYear', st.year); st.shown = 60; load(true); } };
  $('#trFilter').onclick = (e) => { const b = e.target.closest('button'); if (b) { st.filter = b.dataset.v; st.shown = 60; render(); } };
  $('#trSort').onchange = (e) => { st.sort = e.target.value; render(); };
  let tq;
  $('#trQ').oninput = (e) => { clearTimeout(tq); tq = setTimeout(() => { st.q = e.target.value.trim().toLowerCase(); st.shown = 60; render(); const q = $('#trQ'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }, 220); };
  $('#trMore')?.addEventListener('click', () => { st.shown += 60; render(); });
  $('#trList').onclick = (e) => { const b = e.target.closest('.nx-trade'); if (!b) return; const t = st.data[+b.dataset.i]; if (e.target.closest('[data-chart]')) openChart(t); else openSheet(t); };
}

// ------------------------------------------------------------------ detail sheet
export function openSheet(t, { chartOnly = false } = {}) {
  closeSheet();
  const rp = t.report || {};
  const ck = (t.checklist || []).map(([k, v]) => `<li class="${v > 0 ? 'ok' : v < 0 ? 'no' : 'na'}">${icon(v > 0 ? 'check' : v < 0 ? 'close' : 'minus')}<span>${esc(k)}</span></li>`).join('');
  const smc = Object.entries(t.smc || {}).filter(([, v]) => v).map(([k]) => chip(esc(k.replace(/^x_/, '').replace(/_/g, ' ')))).join('');
  const num = (k, v) => `<div><span>${k}</span><b>${v}</b></div>`;
  const wrap = document.createElement('div');
  wrap.className = 'nx-sheet-wrap';
  wrap.innerHTML = `<div class="nx-scrim"></div><aside class="nx-sheet${t.chart ? ' nx-sheet-tc' : ''}" role="dialog" aria-modal="true" aria-label="Trade report">
    <div class="nx-sheet-grab"></div>
    <header class="nx-sheet-h">
      <span class="nx-trade-side ${t.side === 'LONG' ? 'L' : 'S'}">${icon(t.side === 'LONG' ? 'long' : 'short')}</span>
      <div><div class="nx-eyebrow">${esc(t.day)} · ${esc(rp.time || etStr(t.entry_t) + ' ET')}</div><h3>${t.side} · ${esc(t.trigger)} · ${esc(t.exit)}</h3></div>
      <div class="nx-sheet-res"><b class="${cls(t.r)}">${fmtR(t.r)}</b><span class="${cls(t.pnl)}">${fmtS$(t.pnl)}</span></div>
      <button class="btn ghost icon nx-sheet-x" type="button" title="Close">✕</button>
    </header>
    <div class="nx-sheet-b">
      ${t.chart ? '<div class="nx-tcbox" id="nxTC"></div>' : ''}
      ${chartOnly ? '' : `<div class="nx-nums">${num('Stop', fmtN(t.risk_pts, 2) + ' pts')}${num('Micros', t.qty)}${num('$ risk', fmt$(t.risk_usd))}${num('Size', t.half ? `<span class="warn-t">half (${String(t.trigger || '').startsWith('LIT') ? 'weekly stop' : 'cold streak'})</span>` : 'full')}
        ${num('Entry', fmtN(t.entry))}${num('Stop price', fmtN(t.stop))}${num('Target', fmtN(t.target))}${num('Exit', fmtN(t.exit_price))}
        ${num('Best point', t.mfe != null ? '+' + fmtN(t.mfe, 2) + 'R' : '—')}${num('Bars held', t.bars_held ?? '—')}${num('Regime', esc(t.regime || '—'))}${num('Grade', esc(t.grade || '—'))}</div>
      <section><h4>${icon('target')}Plan</h4><p>${esc(rp.plan || '—')}</p><p class="muted small">Target: ${esc(t.target_label || '—')}</p></section>
      <section><h4>${icon('info')}Why it entered</h4><ul class="nx-list">${(rp.why || []).map(w => `<li>${esc(w)}</li>`).join('') || '<li>—</li>'}</ul></section>
      <section><h4>${icon('check')}Result</h4><p>${esc(rp.result || '—')}</p></section>
      <section><h4>${icon('learned')}Lessons</h4><ul class="nx-list">${(rp.lessons || []).map(w => `<li>${esc(w)}</li>`).join('') || '<li class="muted">none recorded</li>'}</ul></section>
      ${ck ? `<section><h4>${icon('rules')}Checklist</h4><ul class="nx-check">${ck}</ul></section>` : ''}
      ${(t.conf_tags || []).length ? `<section><h4>${icon('conf')}Confluences</h4><div class="nx-chips">${t.conf_tags.map(c => chip(esc(c))).join('')}</div></section>` : ''}
      ${smc ? `<section><h4>${icon('study')}Price action</h4><div class="nx-chips">${smc}</div></section>` : ''}`}
    </div>
    <footer class="nx-sheet-f">${chartOnly ? `<button class="btn" type="button" id="nxFull">${icon('trades')}Full report</button>` : ''}<button class="btn primary" type="button" id="nxOpenChart">${icon('chart')}Open day on chart</button></footer>
  </aside>`;
  document.body.appendChild(wrap);
  requestAnimationFrame(() => wrap.classList.add('on'));
  wrap.querySelector('.nx-scrim').onclick = closeSheet;
  wrap.querySelector('.nx-sheet-x').onclick = closeSheet;
  wrap.querySelector('#nxOpenChart').onclick = () => {
    closeSheet();
    const i = S.res?.trades?.findIndex(x => Math.abs(x.entry_t - t.entry_t) < 300) ?? -1;
    if (i >= 0) chartPage.openTrade(i); else chartPage.openDay?.(t.day);
    go('chart');
  };
  document.addEventListener('keydown', escClose);
  wrap.querySelector('#nxFull')?.addEventListener('click', () => openSheet(t));
  if (t.chart) chartInto(wrap.querySelector('#nxTC'), t);
  tcCss();
}
function escClose(e) { if (e.key === 'Escape') closeSheet(); }
export function closeSheet() {
  document.removeEventListener('keydown', escClose);
  $$('.nx-sheet-wrap').forEach(w => { w.classList.remove('on'); setTimeout(() => w.remove(), 220); });
}

async function load(force = false) {
  const el = $('#page-trades');
  if (loaded && loaded.year === st.year && !force) { render(); return; }
  if (!st.data) el.innerHTML = '<div class="nx-skel"><i></i><i></i><i></i></div>';
  try {
    loaded = await api('/api/next/trades?year=' + encodeURIComponent(st.year));
    st.data = loaded.trades; st.years = loaded.years;
    render();
  } catch (e) {
    el.innerHTML = `<div class="banner warn">Could not load the live replay: ${esc(e.message)}. Run <span class="mono">python tools/export_backtest.py</span>.</div>`;
  }
}

export function show() { load(); }
