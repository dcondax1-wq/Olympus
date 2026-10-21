// Data → Trade intel: every LIT trade (backtest run lit_live 2026 + 2021-25, the paper ledger, the PC's live trades) with
// ~60 columns, the win / loss signs per feature (2026 H1 / H2 / 2021-25 buckets) and an MFE / MAE scatter.
// Data: /api/next/intel (engine/next_api.py intel -> tools/trade_intel.py, research/lab/trade_intel.json). Read-only.
import { $, api, esc, fmtS$, fmtN, fmtR, cls } from '../util.js';
import { icon } from './icons.js';
import { openSheet } from './trades.js';
import { go } from '../app.js';

let D = null, ROWS = null, BT = null;
const st = { tab: 'trades', src: 'all', span: 'all', out: 'all', side: 'all', q: '', sort: 'entry_t', dir: -1, limit: 120,
  sSpan: 'all', sOnly: false, gx: 'mae', gy: 'mfe' };
const SHOW = ['source', 'span', 'day', 'entry_hm', 'weekday', 'session', 'side', 'lvl_type', 'n_lvls', 'depth_atr', 'idm_n', 'disp', 'stop_pts',
  'rr', 'vix', 'exit', 'r', 'pnl', 'mfe', 'mae', 'mins'];
const seg = (id, items, cur) => `<div class="seg" id="${id}">${items.map(([v, l]) => `<button type="button" data-v="${esc(v)}" class="${v === cur ? 'on' : ''}">${esc(l)}</button>`).join('')}</div>`;
const onSeg = (id, fn) => { const s = $('#' + id); if (s) s.onclick = (e) => { const b = e.target.closest('button[data-v]'); if (b) fn(b.dataset.v); }; };
const COLOR = { win: 'var(--good)', loss: 'var(--bad, #ef5350)', scratch: 'var(--gold, #d4a72c)' };

function cell(c, v) {
  if (v == null || v === '') return '<span class="muted">—</span>';
  if (c.key === 'r') return `<b class="${cls(v)}">${fmtR(v)}</b>`;
  if (c.key === 'pnl') return `<span class="${cls(v)}">${fmtS$(v)}</span>`;
  if (c.kind === 'bool') return v ? 'yes' : 'no';
  if (c.key === 'entry_t') return String(v);
  if (c.kind === 'num') return fmtN(v, Math.abs(v) >= 100 || Number.isInteger(v) ? 0 : 2);
  if (c.key === 'side') return `<span class="${v === 'LONG' ? 'up' : 'dn'}">${esc(v)}</span>`;
  return esc(String(v));
}
function filtered() {
  const q = st.q.trim().toLowerCase();
  let R = ROWS.filter((r) => (st.src === 'all' || r.source === st.src) && (st.span === 'all' || r.span === st.span)
    && (st.out === 'all' || r.outcome === st.out) && (st.side === 'all' || r.side === st.side)
    && (!q || [r.day, r.swept, r.session, r.lvl_type, r.exit, r.weekday].join(' ').toLowerCase().includes(q)));
  const k = st.sort, d = st.dir;
  R = R.slice().sort((a, b) => { const x = a[k], y = b[k]; if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * d; });
  return R;
}
function stat(R) {
  const n = R.length, net = R.reduce((s, r) => s + (r.pnl || 0), 0), w = R.filter((r) => (r.pnl || 0) > 0).length;
  const gw = R.reduce((s, r) => s + Math.max(0, r.pnl || 0), 0), gl = -R.reduce((s, r) => s + Math.min(0, r.pnl || 0), 0);
  return { n, net, win: n ? 100 * w / n : null, pf: gl > 0 ? gw / gl : null, avg: n ? R.reduce((s, r) => s + (r.r || 0), 0) / n : null };
}

function tradesTab() {
  const R = filtered(), S = stat(R), C = D.cols;
  const cols = st.all ? C : C.filter((c) => SHOW.includes(c.key));
  return `<div class="nx-toolbar" style="flex-wrap:wrap;gap:8px">
      ${seg('tiSrc', [['all', 'All sources'], ['backtest', 'Backtest'], ['paper', 'Paper'], ['live', 'Live']], st.src)}
      ${seg('tiSpan', [['all', 'All'], ['H1', '2026 H1'], ['H2', '2026 H2'], ['2021-25', '2021-25']], st.span)}
      ${seg('tiOut', [['all', 'Any result'], ['win', 'Wins'], ['scratch', 'Scratches'], ['loss', 'Losses']], st.out)}
      ${seg('tiSide', [['all', 'Both sides'], ['LONG', 'Long'], ['SHORT', 'Short']], st.side)}
      <input id="tiQ" class="input" placeholder="Search day, level, session…" value="${esc(st.q)}" style="min-width:180px;height:34px">
      <button class="btn ghost" type="button" id="tiAll">${st.all ? 'Fewer columns' : 'All ' + C.length + ' columns'}</button></div>
    <div class="nx-stats">
      <div class="nx-stat"><span>Trades</span><b>${S.n}</b><em>${Object.entries(D.meta.sources || {}).map(([k, v]) => `${v} ${k}`).join(' · ')}</em></div>
      <div class="nx-stat"><span>Net</span><b class="${cls(S.net)}">${fmtS$(S.net)}</b><em>costs in</em></div>
      <div class="nx-stat"><span>Win %</span><b>${S.win == null ? '—' : fmtN(S.win, 1) + '%'}</b><em>$ &gt; 0</em></div>
      <div class="nx-stat"><span>PF · avg R</span><b>${S.pf == null ? '—' : fmtN(S.pf, 2)}</b><em>${fmtR(S.avg)} a trade</em></div></div>
    <div class="card nx-glass" style="overflow:auto;max-height:70vh;padding:0"><table class="tbl" id="tiTbl" style="min-width:${Math.max(900, cols.length * 92)}px">
      <thead><tr>${cols.map((c) => `<th data-k="${c.key}" title="${esc(c.desc)}${c.when === 'after' ? ' (after: not known at entry)' : ''}" style="cursor:pointer;white-space:nowrap;position:sticky;top:0">${esc(c.label)}${c.when === 'after' ? ' ·a' : ''}${st.sort === c.key ? (st.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead>
      <tbody>${R.slice(0, st.limit).map((r, i) => `<tr data-i="${ROWS.indexOf(r)}" style="cursor:pointer">${cols.map((c) => `<td class="mono" style="white-space:nowrap">${cell(c, r[c.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
    ${R.length > st.limit ? `<button class="btn" type="button" id="tiMore" style="margin-top:8px">Show ${Math.min(200, R.length - st.limit)} more (${R.length - st.limit} left)</button>` : ''}
    <p class="muted small" style="margin-top:8px">Click a header to sort, a row for every column and the trade's report + chart. Columns marked ·a are outcomes (known only after the trade). Backtest $ use the LIT size rule; paper / live $ are what was routed.</p>
    <div id="tiDetail"></div>`;
}
function bindTrades() {
  onSeg('tiSrc', (v) => { st.src = v; render(); }); onSeg('tiSpan', (v) => { st.span = v; render(); });
  onSeg('tiOut', (v) => { st.out = v; render(); }); onSeg('tiSide', (v) => { st.side = v; render(); });
  const q = $('#tiQ'); if (q) q.oninput = () => { st.q = q.value; clearTimeout(q._t); q._t = setTimeout(() => { render(); const n = $('#tiQ'); if (n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } }, 250); };
  $('#tiAll')?.addEventListener('click', () => { st.all = !st.all; render(); });
  $('#tiMore')?.addEventListener('click', () => { st.limit += 200; render(); });
  $('#tiTbl thead')?.addEventListener('click', (e) => { const th = e.target.closest('th[data-k]'); if (!th) return; const k = th.dataset.k; st.dir = st.sort === k ? -st.dir : -1; st.sort = k; render(); });
  $('#tiTbl tbody')?.addEventListener('click', (e) => { const tr = e.target.closest('tr[data-i]'); if (tr) detail(ROWS[+tr.dataset.i]); });
}
async function detail(r) {
  const box = $('#tiDetail'); if (!box) return;
  const groups = {};
  for (const c of D.cols) (groups[c.group] = groups[c.group] || []).push(c);
  box.innerHTML = `<div class="card nx-glass" style="margin-top:12px"><div class="card-h"><h3>${esc(r.day)} · ${esc(r.entry_hm || '')} ET · ${esc(r.side || '')} · ${esc(r.source)}</h3>
    <span><b class="${cls(r.r)}">${fmtR(r.r)}</b> <span class="${cls(r.pnl)}">${fmtS$(r.pnl)}</span></span></div>
    ${Object.entries(groups).filter(([g]) => g !== 'id').map(([g, cs]) => `<h4 style="margin:10px 0 4px;text-transform:capitalize">${esc(g)}</h4>
      <div class="nx-nums">${cs.map((c) => `<div title="${esc(c.desc)}"><span>${esc(c.label)}${c.when === 'after' ? ' (after)' : ''}</span><b>${cell(c, r[c.key])}</b></div>`).join('')}</div>`).join('')}
    <div style="margin-top:10px"><button class="btn primary" type="button" id="tiOpen" ${r.source !== 'backtest' ? 'disabled' : ''}>${icon('chart')}Report + chart</button>
      ${r.source !== 'backtest' ? '<span class="muted small"> paper / live trades: see Accounts for the order log</span>' : ''}</div></div>`;
  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  $('#tiOpen')?.addEventListener('click', async () => {
    try {
      if (!BT) { const d = await api('/api/next/trades?year=all'); BT = new Map((d.trades || []).map((t) => [t.day + '|' + t.entry_t, t])); }
      const t = BT.get(r.day + '|' + r.entry_t);
      if (t) openSheet(t); else box.insertAdjacentHTML('beforeend', '<div class="banner warn">No report for this trade in backtest_live.json (run tools/export_backtest.py).</div>');
    } catch (e) { box.insertAdjacentHTML('beforeend', `<div class="banner warn">${esc(e.message)}</div>`); }
  });
}

function bstat(s) {
  if (!s || !s.n) return '<td class="mono muted" colspan="4">—</td>';
  return `<td class="mono">${s.n}</td><td class="mono">${s.win == null ? '—' : fmtN(s.win, 0) + '%'}</td><td class="mono ${cls(s.avg_r)}">${fmtR(s.avg_r)}</td><td class="mono ${cls(s.net)}">${fmtS$(s.net)}<span class="muted"> · PF ${s.pf == null ? '—' : fmtN(s.pf, 2)}</span></td>`;
}
function signsTab() {
  const sm = D.summary || {};
  const list = (D.signs || []).filter((s) => !st.sOnly || s.consistent);
  const li = (a) => a.map((w) => `<li>${esc(w.text)}${w.held_5y ? ' <span class="up small">holds 2021-25</span>' : ''}</li>`).join('') || '<li class="muted">none</li>';
  const g = sm.groups || {}, lab = g.labels || {};
  const gk = Object.keys(lab);
  return `<div class="banner warn" style="margin-bottom:12px">${esc(sm.warning || '')}</div>
    <div class="nx-stats">
      <div class="nx-stat"><span>Consistent signs</span><b>${sm.n_consistent ?? '—'} / ${sm.n_features ?? '—'}</b><em>same side better in H1 and H2 by ≥ ${sm.min_gap}R, ${D.meta.min_side}+ trades a side</em></div>
      <div class="nx-stat"><span>By chance</span><b>${sm.chance ?? '—'}</b><em>on shuffled outcomes (average of 20)</em></div>
      <div class="nx-stat"><span>+1R then gave back</span><b>${g.gave_back?.n ?? '—'}</b><em>2026 · ${fmtS$(g.gave_back?.net)}</em></div>
      <div class="nx-stat"><span>Clean wins</span><b class="up">${g.clean_win?.n ?? '—'}</b><em>2026 · ${fmtS$(g.clean_win?.net)}</em></div></div>
    <div class="grid2" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px">
      <div class="card nx-glass"><div class="card-h"><h3>What winners have in common</h3></div><ul class="nx-list">${li(sm.winners || [])}</ul></div>
      <div class="card nx-glass"><div class="card-h"><h3>What losers have in common</h3></div><ul class="nx-list">${li(sm.losers || [])}</ul></div></div>
    <div class="card nx-glass"><div class="card-h"><h3>+1R then gave it back vs clean wins (2026, medians)</h3></div>
      <table class="tbl"><thead><tr><th>Median</th><th>Gave back (${g.gave_back?.n ?? 0})</th><th>Clean wins (${g.clean_win?.n ?? 0})</th><th>All 2026 (${g.all_2026?.n ?? 0})</th></tr></thead>
      <tbody>${gk.map((k) => `<tr><td>${esc(lab[k])}</td>${['gave_back', 'clean_win', 'all_2026'].map((x) => `<td class="mono">${g[x]?.med?.[k] == null ? '—' : fmtN(g[x].med[k], 2)}</td>`).join('')}</tr>`).join('')}</tbody></table>
      <p class="muted small">Gave back = reached +1R, ended under +0.5R (breakeven or a cut). Clean win = target hit, never 0.5R under water.</p></div>
    <div class="nx-toolbar">${seg('tiSOnly', [['0', 'Every feature'], ['1', 'Consistent only']], st.sOnly ? '1' : '0')}
      <span class="muted small">Tested as rules in: ${(sm.writeups || []).map((w) => `<a href="#" data-doc="${esc(w.slug)}">${esc(w.slug)}</a>`).join(' · ')}</span></div>
    ${list.map((s) => `<div class="card nx-glass" style="${s.consistent ? 'border-color:var(--good)' : ''}"><div class="card-h"><h3>${s.consistent ? icon('check') + ' ' : ''}${esc(s.label)}</h3>
      <span class="small ${s.consistent ? 'up' : 'muted'}">${esc(s.why)}${s.held_5y == null ? '' : s.held_5y ? ' · holds 2021-25' : ' · not in 2021-25'}</span></div>
      <p class="muted small">${esc(s.desc)}${s.cuts ? ` · terciles set on 2026 H1 (${s.cuts.map((x) => fmtN(x, 2)).join(' / ')})` : ''}</p>
      <div style="overflow:auto"><table class="tbl"><thead><tr><th rowspan="2">Bucket</th><th colspan="4">2026 H1 (picked)</th><th colspan="4">2026 H2 (check)</th><th colspan="4">2021-25 (reference)</th></tr>
      <tr>${'<th>n</th><th>win</th><th>avg R</th><th>$</th>'.repeat(3)}</tr></thead>
      <tbody>${s.buckets.map((b) => `<tr><td>${esc(b.label)}</td>${bstat(b.H1)}${bstat(b.H2)}${bstat(b['2021-25'])}</tr>`).join('')}</tbody></table></div></div>`).join('')}`;
}
function bindSigns() {
  onSeg('tiSOnly', (v) => { st.sOnly = v === '1'; render(); });
  document.querySelectorAll('#page-intel a[data-doc]').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); go('writeups'); }));
}

function scatterTab() {
  const R = ROWS.filter((r) => r.mfe != null && r.mae != null && (st.span === 'all' || r.span === st.span) && (st.src === 'all' || r.source === st.src));
  const W = 900, H = 420, P = 56;
  const xm = Math.max(1.2, ...R.map((r) => r.mae)), ym = Math.max(2, ...R.map((r) => Math.min(r.mfe, 10)));
  const X = (v) => P + (W - 2 * P) * Math.min(v, xm) / xm, Y = (v) => H - P - (H - 2 * P) * Math.min(v, ym) / ym;
  const ticks = (m, n) => Array.from({ length: n + 1 }, (_, i) => +(m * i / n).toFixed(1));
  return `<div class="nx-toolbar" style="flex-wrap:wrap;gap:8px">${seg('tiSpan', [['all', 'All'], ['H1', '2026 H1'], ['H2', '2026 H2'], ['2021-25', '2021-25']], st.span)}
      ${seg('tiSrc', [['all', 'All sources'], ['backtest', 'Backtest'], ['paper', 'Paper'], ['live', 'Live']], st.src)}</div>
    <div class="card nx-glass"><div class="card-h"><h3>MFE vs MAE (${R.length} trades)</h3><span class="small">
      ${Object.entries(COLOR).map(([k, c]) => `<span style="color:${c}">●</span> ${k}`).join(' &nbsp; ')}</span></div>
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto" role="img" aria-label="MFE vs MAE scatter">
        ${ticks(xm, 6).map((t) => `<line x1="${X(t)}" x2="${X(t)}" y1="${P}" y2="${H - P}" stroke="currentColor" stroke-opacity=".08"/><text x="${X(t)}" y="${H - P + 16}" font-size="11" text-anchor="middle" fill="currentColor" opacity=".6">${t}R</text>`).join('')}
        ${ticks(ym, 5).map((t) => `<line x1="${P}" x2="${W - P}" y1="${Y(t)}" y2="${Y(t)}" stroke="currentColor" stroke-opacity=".08"/><text x="${P - 6}" y="${Y(t) + 4}" font-size="11" text-anchor="end" fill="currentColor" opacity=".6">${t}R</text>`).join('')}
        <line x1="${P}" x2="${W - P}" y1="${Y(1)}" y2="${Y(1)}" stroke="var(--gold,#d4a72c)" stroke-dasharray="4 4" stroke-opacity=".7"/>
        <text x="${W - P}" y="${Y(1) - 4}" font-size="11" text-anchor="end" fill="var(--gold,#d4a72c)">+1R (breakeven moves here)</text>
        <text x="${W / 2}" y="${H - 6}" font-size="12" text-anchor="middle" fill="currentColor" opacity=".75">MAE: worst open loss (R)</text>
        <text x="18" y="${H / 2}" font-size="12" text-anchor="middle" fill="currentColor" opacity=".75" transform="rotate(-90 18 ${H / 2})">MFE: best open profit (R, max 10)</text>
        ${R.map((r) => `<circle cx="${X(r.mae).toFixed(1)}" cy="${Y(r.mfe).toFixed(1)}" r="${r.source === 'backtest' ? 3.2 : 5.5}" fill="${COLOR[r.outcome] || 'gray'}" fill-opacity="${r.span === '2021-25' ? 0.35 : 0.8}" ${r.source !== 'backtest' ? 'stroke="var(--ink)" stroke-width="1.5"' : ''}><title>${esc(r.day)} ${esc(r.side)} ${esc(r.exit)} ${fmtR(r.r)} · MFE ${fmtN(r.mfe, 2)} · MAE ${fmtN(r.mae, 2)}</title></circle>`).join('')}
      </svg>
      <p class="muted small">Every dot is one trade. Top-left = clean winners (little heat, big run); bottom-right = stop-outs (full -1R, never ran). Dots above the gold line reached +1R: when they are not green they gave it back (breakeven or a cut). Paper / live trades are the large outlined dots.</p></div>`;
}

function render() {
  const el = $('#page-intel'); if (!el) return;
  const T = D.totals || {};
  const tl = (k, l) => T[k] && T[k].n ? `<div class="nx-stat"><span>${l}</span><b>${T[k].n}</b><em class="${cls(T[k].net)}">${fmtS$(T[k].net)} · PF ${T[k].pf == null ? '—' : fmtN(T[k].pf, 2)} · win ${fmtN(T[k].win, 0)}%</em></div>` : '';
  el.innerHTML = `<div class="nx-hero"><div><div class="nx-eyebrow">${icon('stats')} Data · Trade intel · built ${esc(D.meta.built || '')} · run ${esc(D.meta.run || '')}</div>
      <h2>Every trade, every sign</h2><p class="muted">All LIT trades from every source with ~60 facts each: what was known at entry (time, level, sweep, inducement, displacement, stop, target, VIX, gamma, ranges, news, weekly stop) and what happened after (exit, R, $, MFE / MAE, time to +1R, heat before breakeven). Signs are judged on 2026 H1 (picked) and H2 (check); 2021-25 is a reference.</p></div></div>
    <div class="nx-stats">${tl('H1', '2026 H1')}${tl('H2', '2026 H2')}${tl('2021-25', '2021-25 ref')}${tl('paper', 'Paper (cloud)')}${tl('live', 'Live (PC)')}</div>
    <div class="nx-toolbar">${seg('tiTab', [['trades', 'Trades'], ['signs', 'Signs'], ['scatter', 'MFE / MAE']], st.tab)}</div>
    <div id="tiBody">${st.tab === 'signs' ? signsTab() : st.tab === 'scatter' ? scatterTab() : tradesTab()}</div>`;
  onSeg('tiTab', (v) => { st.tab = v; render(); });
  if (st.tab === 'trades') bindTrades();
  else if (st.tab === 'signs') bindSigns();
  else { onSeg('tiSpan', (v) => { st.span = v; render(); }); onSeg('tiSrc', (v) => { st.src = v; render(); }); }
}

async function show() {
  const el = $('#page-intel'); if (!el) return;
  if (!D) {
    el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
    try {
      const r = await fetch('/api/next/intel');
      const d = await r.json();
      if (!r.ok || d.error) { el.innerHTML = `<div class="card nx-glass nx-empty-hub"><span class="nx-tile-i">${icon('stats')}</span><h3>Not built yet</h3><p class="muted">${esc(d.error || 'HTTP ' + r.status)}</p></div>`; return; }
      D = d;
      const keys = d.cols.map((c) => c.key);
      ROWS = d.rows.map((a) => Object.fromEntries(keys.map((k, i) => [k, a[i]])));
    } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  }
  render();
}
export const intel = { show };
