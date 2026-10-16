import { $, $$, seg, esc, fmtN, fmt$, fmtS$, fmtR, cls, etStr, store, toast, css, downloadFile } from './util.js';
import { S, on, PARAM_SCHEMA, PRESETS, WINDOW_PRESETS, effective, getParam, setParam, cj, baseOpts } from './state.js';
import { kpiTiles, go, run } from './app.js';
import * as chartPage from './page-chart.js';

let bdKey = store.get('bdKey', 'conf');
let filter = 'all';
let sortKey = 'entry_t', sortDir = -1;

const hm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const unhm = (s) => { const [h, m] = s.split(':').map(Number); return h * 60 + (m || 0); };

export function init() {
  on(render);
  seg($('#bdSeg'), [['conf', 'Confluence'], ['pool', 'Pool swept'], ['trigger', 'Trigger'], ['target', 'Target'], ['score', 'Score'], ['hour', 'Hour'], ['dir', 'Side']], bdKey,
    (v) => { bdKey = v; store.set('bdKey', v); renderBreakdown(); });
  seg($('#tradeFilter'), [['all', 'All'], ['win', 'Winners'], ['loss', 'Losers'], ['long', 'Longs'], ['short', 'Shorts']], filter, (v) => { filter = v; renderTable(); });
  $('#exportCsv').onclick = exportCsv;
  $('#exportJson').onclick = () => downloadFile(`backtest_${S.sym}.json`, JSON.stringify({ params: S.res.params, stats: S.res.stats, trades: S.res.trades }, null, 2), 'application/json');
}
export function show() { if (S.meta && !$('#paramPanel').dataset.built) buildParams(); }

// ------------------------------------------------------------------ parameter panel
function buildParams() {
  const el = $('#paramPanel');
  el.dataset.built = 1;
  const saved = store.get('userPresets', {});
  let html = `<div class="card-h"><h3>Strategy parameters</h3><button class="btn primary sm" id="pRun">▶ Run</button></div>
    <div class="presets">${Object.keys(PRESETS).map(k => `<button class="btn ghost sm" data-preset="${esc(k)}">${esc(k)}</button>`).join('')}
    ${Object.keys(saved).map(k => `<button class="btn ghost sm" data-upreset="${esc(k)}">★ ${esc(k)}</button>`).join('')}</div>
    <div class="row gap" style="margin-bottom:6px"><button class="btn ghost sm" id="pSave">Save preset</button><button class="btn ghost sm" id="pReset">Reset defaults</button>
    <select class="sel sm" id="pTf"></select></div>`;
  for (const [group, items] of PARAM_SCHEMA) {
    html += `<div class="pgroup"><h4>${group}</h4>`;
    for (const [key, label, type, hint, extra = {}] of items) {
      const v = getParam(key);
      let input;
      if (type === 'bool') input = `<input type="checkbox" data-k="${key}" ${v ? 'checked' : ''}>`;
      else if (type === 'sel') input = `<select data-k="${key}">${extra.options.map(o => `<option ${o === v ? 'selected' : ''}>${o}</option>`).join('')}</select>`;
      else if (type === 'time') input = `<input type="time" data-k="${key}" data-t="time" value="${hm(v)}" style="width:100%;font:500 12px var(--mono);background:var(--surface-2);color:var(--ink);border:1px solid var(--border);border-radius:7px;padding:4px 6px">`;
      else if (type === 'win') {
        const cur = JSON.stringify(v);
        const name = Object.entries(WINDOW_PRESETS).find(([, w]) => JSON.stringify(w) === cur)?.[0];
        input = `<select data-k="${key}" data-t="win">${Object.keys(WINDOW_PRESETS).map(n => `<option ${n === name ? 'selected' : ''}>${n}</option>`).join('')}</select>`;
      } else if (type === 'text') input = `<input type="text" data-k="${key}" data-t="text" value="${esc(v ?? '')}" style="width:100%;font:500 12px var(--mono);background:var(--surface-2);color:var(--ink);border:1px solid var(--border);border-radius:7px;padding:4px 6px">`;
      else input = `<input type="number" data-k="${key}" value="${v}" step="${extra.step || 1}">`;
      html += `<label class="prow"><span>${label}${hint ? `<span class="hint">${hint}</span>` : ''}</span>${input}</label>`;
    }
    html += `</div>`;
  }
  el.innerHTML = html;
  const tfs = (S.meta.available[S.sym] || []).filter(x => ['1m', '5m'].includes(x));
  $('#pTf').innerHTML = tfs.map(x => `<option ${x === S.tf ? 'selected' : ''} value="${x}">exec TF ${x}</option>`).join('');
  $('#pTf').onchange = (e) => { S.tf = e.target.value; S.bars = {}; run(); };
  el.addEventListener('change', (e) => {
    const k = e.target.dataset.k; if (!k) return;
    let v;
    if (e.target.type === 'checkbox') v = e.target.checked;
    else if (e.target.dataset.t === 'time') v = unhm(e.target.value);
    else if (e.target.dataset.t === 'win') v = WINDOW_PRESETS[e.target.value];
    else if (e.target.dataset.t === 'text') v = e.target.value;
    else if (e.target.tagName === 'SELECT') v = e.target.value;
    else v = parseFloat(e.target.value);
    setParam(k, v);
  });
  $('#pRun').onclick = run;
  $('#pReset').onclick = () => { S.params = {}; store.set('params', {}); rebuild(); run(); };
  $('#pSave').onclick = () => {
    const name = prompt('Preset name'); if (!name) return;
    const sp = store.get('userPresets', {}); sp[name] = S.params; store.set('userPresets', sp); rebuild(); toast('Preset saved');
  };
  el.onclick = (e) => {
    const b = e.target.closest('[data-preset],[data-upreset]'); if (!b) return;
    S.params = b.dataset.preset ? { ...PRESETS[b.dataset.preset] } : { ...store.get('userPresets', {})[b.dataset.upreset] };
    store.set('params', S.params); rebuild(); run(); toast('Preset: ' + (b.dataset.preset || b.dataset.upreset));
  };
}
function rebuild() { delete $('#paramPanel').dataset.built; buildParams(); }

// ------------------------------------------------------------------ results
function render(res) {
  if (!res) return;
  if (S.meta && !$('#paramPanel').dataset.built) buildParams();
  kpiTiles($('#btKpis'), res.stats, res);
  const tr = res.trades;
  const eq = [res.params.start_balance];
  tr.forEach(t => eq.push(eq.at(-1) + t.pnl));
  const labels = ['start', ...tr.map(t => t.day.slice(5))];
  cj('btEquity', {
    type: 'line',
    data: { labels, datasets: [{ data: eq, borderColor: css('--accent'), borderWidth: 2, pointRadius: 2.5, pointBackgroundColor: ['transparent', ...tr.map(t => t.pnl > 0 ? css('--good') : css('--bad'))], pointBorderWidth: 0, tension: .1, fill: { target: { value: res.params.start_balance }, above: 'rgba(12,163,12,.08)', below: 'rgba(208,59,59,.10)' } }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => fmt$(c.parsed.y) + (c.dataIndex ? `  (${fmtS$(tr[c.dataIndex - 1].pnl)})` : '') } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } }, y: { ticks: { callback: v => '$' + (v / 1000).toFixed(1) + 'k' } } } }),
  });
  let peak = eq[0];
  const dd = eq.map(v => { peak = Math.max(peak, v); return v - peak; });
  cj('btDD', {
    type: 'line',
    data: { labels, datasets: [
      { data: dd, borderColor: css('--bad'), backgroundColor: 'rgba(208,59,59,.15)', fill: 'origin', borderWidth: 1.5, pointRadius: 0, stepped: true },
      { data: dd.map(() => -res.plan.mll), borderColor: css('--muted'), borderDash: [4, 4], borderWidth: 1, pointRadius: 0 }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.datasetIndex ? 'MLL ' + fmt$(c.parsed.y) : 'Drawdown ' + fmt$(c.parsed.y) } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } }, y: { max: 0, ticks: { callback: v => '$' + v } } } }),
  });
  // R histogram
  // bins centred on half-R steps: a -1.02R stop lands in "-1R"
  const bins = [-1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5];
  const counts = bins.map(() => 0);
  tr.forEach(t => { const c = Math.max(-1.5, Math.min(5, Math.round(t.pnl_r * 2) / 2)); counts[bins.indexOf(c)]++; });
  cj('btHist', {
    type: 'bar',
    data: { labels: bins.map(b => (b >= 0 ? '+' : '') + b + 'R'), datasets: [{ data: counts, backgroundColor: bins.map(b => b < 0 ? css('--bad') : b < 0.5 ? css('--muted') : css('--good')), borderRadius: 4, borderSkipped: 'start' }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.parsed.y} trades` } } }, scales: { x: { grid: { display: false } }, y: { ticks: { precision: 0 } } } }),
  });
  barBy('btHour', res.breakdowns.hour);
  const order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  barBy('btDow', order.map(d => res.breakdowns.dow.find(x => x.key === d) || { key: d, n: 0, pnl: 0, wr: 0 }));
  renderCalendar(res);
  renderBreakdown();
  renderTable();
}

function barBy(id, rows) {
  cj(id, {
    type: 'bar',
    data: { labels: rows.map(r => r.key), datasets: [{ data: rows.map(r => r.pnl), backgroundColor: rows.map(r => r.pnl >= 0 ? css('--good') : css('--bad')), borderRadius: 4, borderSkipped: 'start' }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${fmtS$(rows[c.dataIndex].pnl)} · ${rows[c.dataIndex].n} trades · ${rows[c.dataIndex].wr}% win` } } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => '$' + v } } } }),
  });
}

function renderCalendar(res) {
  const days = res.days.filter(d => d.dow < 5);
  if (!days.length) return;
  const maxAbs = Math.max(1, ...days.map(d => Math.abs(d.pnl)));
  const weeks = {};
  for (const d of days) {
    const dt = new Date(d.date + 'T12:00:00Z');
    const monday = new Date(dt - ((dt.getUTCDay() + 6) % 7) * 86400000).toISOString().slice(0, 10);
    (weeks[monday] ||= Array(5).fill(null))[d.dow] = d;
  }
  let html = `<div class="cal"><div></div>${['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].map(x => `<div class="h">${x}</div>`).join('')}`;
  for (const [wk, arr] of Object.entries(weeks)) {
    const wsum = arr.reduce((a, d) => a + (d?.pnl || 0), 0);
    html += `<div class="wk" title="week P&L ${fmtS$(wsum)}">${wk.slice(5)}<br><span class="${cls(wsum)}">${Math.round(wsum)}</span></div>`;
    for (const d of arr) {
      if (!d) { html += '<div></div>'; continue; }
      const a = Math.min(1, Math.abs(d.pnl) / maxAbs);
      const bg = d.pnl > 0 ? `rgba(12,163,12,${0.12 + a * 0.55})` : d.pnl < 0 ? `rgba(208,59,59,${0.12 + a * 0.55})` : 'var(--surface-2)';
      html += `<div class="d" data-day="${d.date}" style="background:${bg}" title="${d.date}: ${fmtS$(d.pnl)} · ${d.trades} trades"><span class="dn2">${d.date.slice(8)}</span><span class="pv">${d.trades ? (d.pnl >= 0 ? '+' : '') + Math.round(d.pnl) : '·'}</span></div>`;
    }
  }
  html += '</div><div class="muted small" style="margin-top:6px">Click a day to open it on the chart.</div>';
  $('#btCal').innerHTML = html;
  $$('#btCal [data-day]').forEach(c => c.onclick = () => { chartPage.openDay(c.dataset.day); go('chart'); });
}

function renderBreakdown() {
  const rows = (S.res?.breakdowns?.[bdKey] || []).slice().sort((a, b) => b.pnl - a.pnl);
  if (!rows.length) { $('#btBreak').innerHTML = '<div class="empty">No data</div>'; return; }
  const max = Math.max(1, ...rows.map(r => Math.abs(r.pnl)));
  $('#btBreak').innerHTML = `<div class="bars-list">` + rows.map(r => {
    const w = Math.abs(r.pnl) / max * 50;
    return `<div class="bl-row"><span class="lbl" title="${esc(r.key)}">${esc(r.key)}</span>
      <div class="bl-track"><div class="mid"></div><div class="fill" style="${r.pnl >= 0 ? `left:50%;width:${w}%;background:var(--good)` : `right:50%;width:${w}%;background:var(--bad)`}"></div></div>
      <span class="mono small ${cls(r.pnl)}" style="text-align:right">${fmtS$(r.pnl)}</span><span class="mono small muted">${r.n}t</span><span class="mono small muted">${Math.round(r.wr)}%</span></div>`;
  }).join('') + `</div><div class="muted small" style="margin-top:8px">Trades can carry several tags, so the confluence and pool rows overlap.</div>`;
}

const COLS = [
  ['entry_t', 'Entry (ET)', t => `${t.day} ${etStr(t.entry_t)}`],
  ['dir', 'Side', t => `<span class="dir ${t.dir === 1 ? 'L' : 'S'}">${t.dir === 1 ? 'LONG' : 'SHORT'}</span>`],
  ['trigger', 'Trigger', t => t.trigger],
  ['score', 'Score', t => t.score],
  ['qty', 'Size', t => esc(t.qty_label)],
  ['entry', 'Entry', t => fmtN(t.entry)],
  ['stop0', 'Stop', t => fmtN(t.stop0 ?? t.stop)],
  ['target', 'Target', t => fmtN(t.target)],
  ['target_label', 'DOL', t => `<span class="small">${esc(t.target_label)}</span>`],
  ['rr', 'Plan R', t => t.rr],
  ['exit_reason', 'Exit', t => t.exit_reason],
  ['bars_held', 'Bars', t => t.bars_held],
  ['mfe', 'MFE', t => fmtN(t.mfe, 2)],
  ['pnl_r', 'R', t => `<span class="${cls(t.pnl_r)}">${fmtR(t.pnl_r)}</span>`],
  ['pnl', 'P&L', t => `<b class="${cls(t.pnl)}">${fmtS$(t.pnl)}</b>`],
  ['pools', 'Swept', t => `<span class="small">${esc(t.pools.map(p => p.split('·').pop()).filter((v, i, a) => a.indexOf(v) === i).slice(0, 3).join(', '))}</span>`],
];

function renderTable() {
  if (!S.res) return;
  let trs = S.res.trades.map((t, i) => ({ ...t, _i: i }));
  if (filter === 'win') trs = trs.filter(t => t.pnl > 0);
  if (filter === 'loss') trs = trs.filter(t => t.pnl <= 0);
  if (filter === 'long') trs = trs.filter(t => t.dir === 1);
  if (filter === 'short') trs = trs.filter(t => t.dir === -1);
  trs.sort((a, b) => { const x = a[sortKey], y = b[sortKey]; return (x > y ? 1 : x < y ? -1 : 0) * sortDir; });
  const el = $('#tradeTable');
  el.innerHTML = `<tr>${COLS.map(([k, l]) => `<th data-k="${k}">${l}${sortKey === k ? (sortDir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr>` +
    trs.map(t => `<tr class="click" data-i="${t._i}">${COLS.map(([, , f]) => `<td>${f(t)}</td>`).join('')}</tr>`).join('');
  el.onclick = (e) => {
    const th = e.target.closest('th');
    if (th) { const k = th.dataset.k; sortDir = sortKey === k ? -sortDir : -1; sortKey = k; renderTable(); return; }
    const tr = e.target.closest('tr[data-i]');
    if (tr) { chartPage.openTrade(+tr.dataset.i); go('chart'); }
  };
}

function exportCsv() {
  const keys = ['day', 'entry_t', 'exit_t', 'dir', 'trigger', 'score', 'qty', 'qty_label', 'entry', 'stop0', 'target', 'target_label', 'rr', 'exit_reason', 'exit_price', 'pnl_r', 'pnl', 'comm', 'mfe', 'mae', 'bars_held'];
  const rows = [keys.join(',') + ',pools,confluence'];
  for (const t of S.res.trades) rows.push(keys.map(k => JSON.stringify(t[k] ?? '')).join(',') + ',' + JSON.stringify(t.pools.join(' | ')) + ',' + JSON.stringify(t.conf_tags.join(' | ')));
  downloadFile(`trades_${S.sym}_${S.res.range[0]}_${S.res.range[1]}.csv`, rows.join('\n'), 'text/csv');
}
