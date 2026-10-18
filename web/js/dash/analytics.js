// Deep Stats page: history analytics over one normalised trade set. Sources: the loaded backtest (ENG(), continuous NQ
// futures history), the dash API's 5-year windowed run, or completed paper trades (/api/dash/trades). Real CME futures only.
import { $, $$, esc, fmt$, fmtS$, fmtN, fmtR, cls, css, etParts, etStr } from '../util.js';
import { S, ENG, on, cj, baseOpts } from '../state.js';
import { widget, body, meta, buildGrid, openLayout } from './widgets.js';
import { waiting, stat, heat, heatSeq, dash, dashIndex, pref, saveCSV, weekOf, spark } from './kit.js';

const A = { src: pref.get('anSrc', 'bt'), range: pref.get('anRange', 'all'), set: null, note: '', loading: false };
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const kzOf = (ts) => { const p = etParts(ts), m = p.h * 60 + p.mi; return m >= 570 && m < 690 ? 'NY AM' : m >= 810 && m < 930 ? 'NY PM' : 'other'; };
const dowOf = (d) => new Date(d + 'T00:00:00Z').getUTCDay();
const sum = (a) => a.reduce((x, y) => x + y, 0);
const mean = (a) => a.length ? sum(a) / a.length : null;
const median = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
function grp(trades) {
  const n = trades.length, wins = trades.filter(t => t.pnl > 0);
  const gp = sum(wins.map(t => t.pnl)), gl = -sum(trades.filter(t => t.pnl < 0).map(t => t.pnl));
  return { n, wr: n ? wins.length / n * 100 : null, avg_r: mean(trades.map(t => t.r)), total_r: sum(trades.map(t => t.r)), pnl: sum(trades.map(t => t.pnl)), pf: gl ? gp / gl : gp ? Infinity : null };
}
const pfTxt = (v) => v == null ? '—' : v === Infinity ? '∞' : fmtN(v, 2);

// ------------------------------------------------------------------ data
function fromBacktest(res) {
  const trades = (res?.trades || []).map(t => ({ day: t.day, entry_t: t.entry_t, exit_t: t.exit_t, dir: t.dir, pnl: t.pnl, r: t.pnl_r, mae: t.mae, mfe: t.mfe, grade: t.grade, exit: t.exit_reason,
    regime: t.regime, trigger: t.trigger, bars: t.bars_held, kz: kzOf(t.entry_t), target: t.target_label }));
  const days = (res?.days || []).map(d => ({ date: d.date, pnl: d.pnl, trades: d.trades }));
  return { trades, days, label: `Backtest · ${res?.sym || 'NQ'} futures ${res?.range?.[0] || ''} → ${res?.range?.[1] || ''}` };
}
function fromApi(j, label) {
  const trades = (j.trades || []).map(t => ({ day: t.day, entry_t: t.entry_t, exit_t: t.exit_t, dir: t.dir, pnl: t.pnl, r: t.r, mae: t.mae, mfe: t.mfe, grade: t.grade, exit: t.exit_reason,
    regime: t.regime, trigger: t.trigger, bars: t.bars_held, kz: t.killzone || kzOf(t.entry_t), target: t.target_label })).sort((a, b) => a.entry_t - b.entry_t);
  return { trades, days: null, label: `${label} · ${j.meta?.from || ''} → ${j.meta?.to || ''}` };
}
// weekdays between two dates as pseudo-days when the source has no day list (no trades = 0)
function fillDays(trades, from, to) {
  const by = {};
  for (const t of trades) { const d = by[t.day] ||= { date: t.day, pnl: 0, trades: 0 }; d.pnl += t.pnl; d.trades++; }
  const out = [];
  if (!from || !to) return Object.values(by);
  for (let d = new Date(from + 'T00:00:00Z'); d <= new Date(to + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + 1)) {
    const k = d.toISOString().slice(0, 10), w = d.getUTCDay();
    if (w === 0 || w === 6) continue;
    out.push(by[k] || { date: k, pnl: 0, trades: 0 });
  }
  return out;
}
async function load() {
  const seq = A.seq = (A.seq || 0) + 1;            // a newer load (source / range change) wins; stale results are dropped
  const stale = () => seq !== A.seq;
  A.loading = true; A.note = '';
  let set = null;
  if (A.src === 'bt') {
    if (!ENG()) { A.set = null; A.loading = false; A.note = 'Waiting for the backtest to finish…'; renderAll(); return; }
    set = fromBacktest(ENG());
  } else {
    A.set = null; renderAll();
    await dashIndex();
    const j = await dash(`/api/dash/trades?source=${A.src}&limit=1000&sort=entry_t&order=asc`, { keep: true, ttl: 60000 });
    if (stale()) return;
    if (!j) { A.set = null; A.loading = false; A.note = A.src === 'paper' ? 'Paper analytics arrive with /api/dash/trades (dash API planned, not deployed yet).' : 'The 5-year windowed run arrives with /api/dash/trades?source=5y (dash API planned, not deployed yet).'; renderAll(); return; }
    if (j.status === 'no_data') { A.set = null; A.loading = false; A.note = j.message || 'No paper trades yet: the paper bot has not completed a trade.'; renderAll(); return; }
    if (j.status === 'computing') { A.set = null; A.loading = false; A.note = `Building the dataset${j.job ? ` · ${j.job.step}/${j.job.steps} ${j.job.msg || ''}` : ''}…`; renderAll(); setTimeout(load, (j.retry_after_s || 10) * 1000); return; }
    set = fromApi(j, A.src === '5y' ? '5-year windowed NQ' : 'Paper trades');
  }
  // range filter
  const all = set.trades;
  const lastDay = set.days?.at(-1)?.date || all.at(-1)?.day;
  let cut = null;
  if (lastDay && A.range !== 'all') {
    const d = new Date(lastDay + 'T00:00:00Z');
    if (A.range === '120') { const ds = (set.days || fillDays(all, all[0]?.day, lastDay)).slice(-120); cut = ds[0]?.date; }
    else { d.setUTCMonth(d.getUTCMonth() - ({ '3y': 36, '1y': 12, '6m': 6 }[A.range] || 0)); cut = d.toISOString().slice(0, 10); }
  }
  const trades = cut ? all.filter(t => t.day >= cut) : all;
  let days = set.days ? (cut ? set.days.filter(d => d.date >= cut) : set.days) : fillDays(trades, cut || all[0]?.day, lastDay);
  A.set = { ...set, trades, days, from: days[0]?.date, to: days.at(-1)?.date };
  A.loading = false;
  renderAll();
}

// ------------------------------------------------------------------ widgets
function need(id, minTrades = 1) {
  const el = body(id); if (!el) return null;
  if (!A.set) { el.innerHTML = waiting(A.loading ? 'Loading…' : 'Waiting for data', esc(A.note)); return null; }
  if (A.set.trades.length < minTrades) { el.innerHTML = waiting('Not enough trades', `${A.set.trades.length} trade(s) in this range; need ${minTrades}.`); return null; }
  return el;
}

function renderYheat() {
  const el = need('yheat'); if (!el) return;
  const days = A.set.days;
  const byYear = {};
  for (const d of days) (byYear[d.date.slice(0, 4)] ||= []).push(d);
  const absP = days.map(d => Math.abs(d.pnl)).filter(Boolean).sort((a, b) => a - b);
  const max = absP[Math.floor(absP.length * .95)] || 1;
  const yrs = Object.keys(byYear).sort().reverse();
  el.innerHTML = `<div class="ycal">${yrs.map(y => {
    const map = Object.fromEntries(byYear[y].map(d => [d.date, d]));
    const start = new Date(Date.UTC(+y, 0, 1)); start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7));
    let cells = '';
    for (let d = new Date(start); d.getUTCFullYear() <= +y; d.setUTCDate(d.getUTCDate() + 1)) {
      const w = d.getUTCDay(); if (w === 0 || w === 6) continue;
      const k = d.toISOString().slice(0, 10), x = map[k];
      if (k.slice(0, 4) !== y) { cells += '<i style="visibility:hidden"></i>'; continue; }
      cells += x ? `<i style="background:${x.trades ? heat(x.pnl, max) : 'color-mix(in srgb,var(--surface-3) 70%,transparent)'}" title="${k} ${DOW[w]} · ${x.trades ? fmtS$(x.pnl) + ' · ' + x.trades + ' trade' + (x.trades > 1 ? 's' : '') : 'no trade'}"></i>` : '<i style="opacity:.35"></i>';
    }
    const tot = sum(byYear[y].map(d => d.pnl));
    return `<div class="ycal-y"><b>${y}<br><span class="${cls(tot)}" style="font-size:10px">${fmtS$(tot)}</span></b><div class="ycal-g">${cells}</div></div>`;
  }).join('')}</div>
  <div class="ycal-key">loss <i style="background:${heat(-max, max)}"></i><i style="background:${heat(-max / 3, max)}"></i><i style="background:color-mix(in srgb,var(--surface-3) 70%,transparent)"></i><i style="background:${heat(max / 3, max)}"></i><i style="background:${heat(max, max)}"></i> win · scale ±${fmt$(max)} (95th pct) · rows Mon–Fri</div>`;
}

let hxMetric = pref.get('hxMetric', 'avg_r');
function renderHxw() {
  const el = need('hxw'); if (!el) return;
  const hours = [...new Set(A.set.trades.map(t => etParts(t.entry_t).h))].sort((a, b) => a - b);
  const cell = {};
  for (const t of A.set.trades) { const k = etParts(t.entry_t).h + '|' + dowOf(t.day); (cell[k] ||= []).push(t); }
  const val = (ts) => { const g = grp(ts); return hxMetric === 'avg_r' ? g.avg_r : hxMetric === 'pnl' ? g.pnl : hxMetric === 'wr' ? g.wr : g.n; };
  const vals = Object.values(cell).map(val).filter(v => v != null);
  const max = Math.max(...vals.map(Math.abs), 1e-9);
  const fmtV = (v) => v == null ? '' : hxMetric === 'avg_r' ? fmtR(v) : hxMetric === 'pnl' ? (Math.abs(v) >= 1000 ? (v / 1000).toFixed(1) + 'k' : fmtN(v, 0)) : hxMetric === 'wr' ? Math.round(v) + '%' : v;
  const col = (v) => hxMetric === 'n' ? heatSeq(v / max) : hxMetric === 'wr' ? heat(v - 50, 50) : heat(v, max);
  el.innerHTML = `<div class="seg sm" id="hxSeg" style="margin-bottom:8px">${[['avg_r', 'avg R'], ['pnl', 'net $'], ['wr', 'win %'], ['n', 'trades']].map(([k, l]) => `<button data-v="${k}" class="${k === hxMetric ? 'on' : ''}">${l}</button>`).join('')}</div>
    <div class="hm" style="grid-template-columns:44px repeat(5,minmax(0,1fr)) 64px"><div></div>${[1, 2, 3, 4, 5].map(d => `<div class="ax">${DOW[d]}</div>`).join('')}<div class="ax">all</div>
    ${hours.map(h => `<div class="ax">${String(h).padStart(2, '0')}:00</div>${[1, 2, 3, 4, 5].map(d => { const ts = cell[h + '|' + d] || []; const v = ts.length ? val(ts) : null;
      return `<div class="c" style="background:${v == null ? 'var(--surface-2)' : col(v)}" title="${DOW[d]} ${h}:00 ET · ${ts.length} trades · ${fmtS$(sum(ts.map(t => t.pnl)))} · ${fmtR(mean(ts.map(t => t.r)))}">${fmtV(v)}<small>${ts.length ? 'n ' + ts.length : ''}</small></div>`; }).join('')}
      ${(() => { const ts = A.set.trades.filter(t => etParts(t.entry_t).h === h); return `<div class="c" style="background:${col(val(ts))}"><b>${fmtV(val(ts))}</b><small>n ${ts.length}</small></div>`; })()}`).join('')}</div>
    <div class="muted small" style="margin-top:6px">Entry hour (ET) × weekday. Thin cells (n &lt; 10) are noise, not a schedule.</div>`;
  $('#hxSeg', el).onclick = (e) => { const b = e.target.closest('button'); if (b) { hxMetric = b.dataset.v; pref.set('hxMetric', hxMetric); renderHxw(); } };
}

function renderMonths() {
  const el = need('months'); if (!el) return;
  const by = {};
  for (const t of A.set.trades) { const k = t.day.slice(0, 7); (by[k] ||= []).push(t); }
  const years = [...new Set(Object.keys(by).map(k => k.slice(0, 4)))].sort().reverse();
  const nets = Object.values(by).map(ts => Math.abs(sum(ts.map(t => t.pnl))));
  const max = Math.max(...nets, 1);
  const k$ = (v) => (v >= 0 ? '+' : '−') + (Math.abs(v) >= 1000 ? (Math.abs(v) / 1000).toFixed(1) + 'k' : Math.round(Math.abs(v)));
  const green = Object.values(by).filter(ts => sum(ts.map(t => t.pnl)) > 0).length;
  el.innerHTML = `<div class="table-wrap" style="max-height:none"><table class="mtx"><tr><th></th>${MON.map(m => `<th>${m}</th>`).join('')}<th>Year</th></tr>
    ${years.map(y => { const row = MON.map((_, i) => by[`${y}-${String(i + 1).padStart(2, '0')}`]); const tot = sum(row.filter(Boolean).flat().map(t => t.pnl));
      return `<tr><th class="yr">${y}</th>${row.map(ts => ts ? (() => { const v = sum(ts.map(t => t.pnl)); return `<td style="background:${heat(v, max)}" title="${ts.length} trades · ${fmtS$(v)}">${k$(v)}</td>`; })() : '<td class="muted">·</td>').join('')}<td class="tot ${cls(tot)}">${k$(tot)}</td></tr>`; }).join('')}</table></div>
    <div class="muted small" style="margin-top:6px">${green} of ${Object.keys(by).length} months green · net per calendar month in $.</div>`;
}

let qHist = null;
function quarterRows() {
  const rows = {};
  const qk = (d) => `${d.slice(0, 4)}Q${Math.floor((+d.slice(5, 7) - 1) / 3) + 1}`;
  for (const d of A.set.days) (rows[qk(d.date)] ||= { key: qk(d.date), sessions: 0, trades: [], weeks: {} }).sessions++;
  for (const t of A.set.trades) { const r = rows[qk(t.day)] ||= { key: qk(t.day), sessions: 0, trades: [], weeks: {} }; r.trades.push(t); }
  for (const d of A.set.days) { const r = rows[qk(d.date)]; const w = weekOf(d.date); r.weeks[w] = (r.weeks[w] || 0) + (d.trades || 0); }
  return Object.values(rows).sort((a, b) => a.key.localeCompare(b.key)).map(r => {
    const g = grp(r.trades), wk = Object.values(r.weeks);
    let eq = 0, pk = 0, dd = 0; for (const t of r.trades) { eq += t.pnl; pk = Math.max(pk, eq); dd = Math.min(dd, eq - pk); }
    return { key: r.key, sessions: r.sessions, trades: g.n, tpw: r.sessions ? g.n / (r.sessions / 5) : null, wr: g.wr, avg_r: g.avg_r, pf: g.pf, net: g.pnl, max_dd: dd,
      pct_weeks_in_band: wk.length ? wk.filter(n => n >= 2 && n <= 4).length / wk.length * 100 : null, pct_zero_weeks: wk.length ? wk.filter(n => n === 0).length / wk.length * 100 : null };
  });
}
function renderQuarters() {
  const el = body('quarters'); if (!el) return;
  const useApi = qHist?.periods?.length && A.src === '5y';
  if (!useApi && !need('quarters')) return;
  const rows = useApi ? qHist.periods : quarterRows();
  meta('quarters', `<span class="src-pill ${useApi ? 'live' : ''}">${useApi ? '5y windowed · dash api' : esc(A.src === 'bt' ? 'loaded backtest' : A.src)}</span>`);
  const green = rows.filter(r => r.net > 0).length;
  el.innerHTML = `<div class="kst-row" style="margin-bottom:8px">${stat('Quarters', rows.length, `${green} green · ${rows.length - green} red`)}${stat('Avg trades / wk', fmtN(mean(rows.map(r => r.tpw).filter(v => v != null)), 2), 'owner band 2–4')}
      ${stat('Quarters in band', `${rows.filter(r => r.tpw >= 2 && r.tpw <= 4).length}/${rows.length}`, 'avg trades/week 2–4')}${stat('Best quarter', fmtS$(Math.max(...rows.map(r => r.net))), rows.reduce((a, b) => b.net > a.net ? b : a, rows[0]).key, 'up')}
      ${stat('Worst quarter', fmtS$(Math.min(...rows.map(r => r.net))), rows.reduce((a, b) => b.net < a.net ? b : a, rows[0]).key, 'dn')}</div>
    <div class="chart-box h220"><canvas id="anQ"></canvas></div>
    <div class="table-wrap" style="margin-top:10px;max-height:340px"><table class="tbl"><tr><th>Quarter</th><th>Sessions</th><th>Trades</th><th>/wk</th><th>Weeks in band</th><th>Win %</th><th>Avg R</th><th>PF</th><th>Net</th><th>Max DD</th></tr>
      ${rows.slice().reverse().map(r => `<tr><td class="mono"><b>${esc(r.key)}</b></td><td class="mono">${r.sessions ?? '—'}</td><td class="mono">${r.trades}</td>
        <td class="mono ${r.tpw >= 2 && r.tpw <= 4 ? 'up' : 'dn'}">${fmtN(r.tpw, 2)}</td><td class="mono">${r.pct_weeks_in_band != null ? Math.round(r.pct_weeks_in_band) + '%' : '—'}</td>
        <td class="mono">${fmtN(r.wr, 1)}%</td><td class="mono ${cls(r.avg_r)}">${fmtR(r.avg_r)}</td><td class="mono">${pfTxt(r.pf)}</td><td class="mono ${cls(r.net)}">${fmtS$(r.net)}</td><td class="mono dn">${fmt$(r.max_dd)}</td></tr>`).join('')}</table></div>`;
  cj('anQ', { data: { labels: rows.map(r => r.key), datasets: [
    { type: 'bar', label: 'Net $', data: rows.map(r => r.net), yAxisID: 'y', backgroundColor: rows.map(r => r.net >= 0 ? css('--good') : css('--bad')), borderRadius: 3 },
    { type: 'line', label: 'Trades / week', data: rows.map(r => r.tpw), yAxisID: 'y1', borderColor: css('--accent'), backgroundColor: css('--accent'), borderWidth: 2, pointRadius: 2.5, tension: .25 },
    { type: 'line', label: 'band 2', data: rows.map(() => 2), yAxisID: 'y1', borderColor: css('--muted'), borderDash: [4, 4], borderWidth: 1, pointRadius: 0 },
    { type: 'line', label: 'band 4', data: rows.map(() => 4), yAxisID: 'y1', borderColor: css('--muted'), borderDash: [4, 4], borderWidth: 1, pointRadius: 0 }] },
    options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'end', labels: { filter: (i) => !i.text.startsWith('band') } } },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } }, y: { grid: { color: css('--grid') }, ticks: { callback: v => '$' + (v / 1000).toFixed(1) + 'k' } },
        y1: { position: 'right', min: 0, suggestedMax: 6, grid: { display: false }, title: { display: true, text: 'trades / week' } } } }) });
}

function weekCounts() {
  const by = {};
  for (const d of A.set.days) { const w = weekOf(d.date); by[w] = (by[w] || 0) + (d.trades || 0); }
  return Object.entries(by).sort(([a], [b]) => a.localeCompare(b)).map(([w, n]) => ({ week: w, n }));
}
function renderFreq() {
  const el = need('freq'); if (!el) return;
  const wk = weekCounts();
  if (!wk.length) { el.innerHTML = waiting('No weeks in range'); return; }
  const bins = [0, 1, 2, 3, 4, 5, 6].map(k => wk.filter(w => k === 6 ? w.n >= 6 : w.n === k).length);
  const inB = wk.filter(w => w.n >= 2 && w.n <= 4).length;
  const r4 = wk.slice(-4).map(w => w.n);
  const ns = wk.map(w => w.n);
  el.innerHTML = `<div class="kst-row">${stat('Weeks', wk.length)}${stat('In band 2–4', Math.round(inB / wk.length * 100) + '%', `${inB} weeks`, inB / wk.length >= .5 ? 'up' : 'dn')}${stat('Zero-trade weeks', Math.round(bins[0] / wk.length * 100) + '%', `${bins[0]} weeks`)}
      ${stat('Avg / median', `${fmtN(mean(ns), 2)} / ${median(ns)}`, 'trades per week')}${stat('Last 4 weeks', fmtN(mean(r4), 2), r4.join(' · '))}</div>
    <div class="chart-box h200" style="margin-top:8px"><canvas id="anFreq"></canvas></div>
    <div class="mini-label" style="margin-top:6px">Trades per week · last ${Math.min(52, wk.length)} weeks</div>${spark(ns.slice(-52), { w: 600, h: 34, color: css('--accent') })}`;
  cj('anFreq', { type: 'bar', data: { labels: ['0', '1', '2', '3', '4', '5', '6+'], datasets: [{ data: bins, borderRadius: 4,
    backgroundColor: [0, 1, 2, 3, 4, 5, 6].map(k => k >= 2 && k <= 4 ? css('--good') : k === 0 ? css('--bad') : css('--warn')) }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { title: c => `${c[0].label} trades in a week`, label: c => `${c.parsed.y} weeks (${Math.round(c.parsed.y / wk.length * 100)}%)` } } },
      scales: { x: { grid: { display: false }, title: { display: true, text: 'trades in the week · green = owner band 2–4' } }, y: { ticks: { precision: 0 } } } }) });
}

function renderStreaks() {
  const el = need('streaks', 2); if (!el) return;
  const seq = A.set.trades.map(t => t.pnl > 0 ? 1 : 0);
  const runs = []; let cur = { w: seq[0], len: 0 };
  for (const s of seq) { if (s === cur.w) cur.len++; else { runs.push(cur); cur = { w: s, len: 1 }; } }
  runs.push(cur);
  const maxW = Math.max(0, ...runs.filter(r => r.w).map(r => r.len)), maxL = Math.max(0, ...runs.filter(r => !r.w).map(r => r.len));
  const lossH = {}; runs.filter(r => !r.w).forEach(r => { lossH[r.len] = (lossH[r.len] || 0) + 1; });
  const dseq = A.set.days.filter(d => d.trades).map(d => d.pnl > 0 ? 1 : d.pnl < 0 ? -1 : 0);
  let dcur = 0; for (let i = dseq.length - 1; i >= 0 && dseq[i] === dseq.at(-1) && dseq[i] !== 0; i--) dcur++;
  const tail = A.set.trades.slice(-160);
  const lmax = Math.max(...Object.keys(lossH).map(Number), 1);
  el.innerHTML = `<div class="kst-row">${stat('Current', `${cur.len} ${cur.w ? 'W' : 'L'}`, cur.w ? 'winning run' : 'losing run', cur.w ? 'up' : 'dn')}${stat('Max win run', maxW, 'trades', 'up')}${stat('Max loss run', maxL, 'trades', 'dn')}${stat('Day streak', `${dcur} ${dseq.at(-1) > 0 ? 'green' : 'red'}`, 'trading days')}</div>
    <div class="mini-label" style="margin-top:10px">Losing-run lengths</div>
    <div class="q-bars" style="height:80px">${Array.from({ length: lmax }, (_, i) => { const n = lossH[i + 1] || 0; const mx = Math.max(...Object.values(lossH)); return `<div class="qb" title="${n} runs of ${i + 1} losses"><i style="height:${n / mx * 100}%;background:var(--bad);opacity:${.35 + .65 * (i + 1) / lmax}"></i></div>`; }).join('')}</div>
    <div class="row" style="justify-content:space-between;font:500 10px var(--mono);color:var(--muted)"><span>1</span><span>${lmax} in a row</span></div>
    <div class="mini-label" style="margin-top:10px">Last ${tail.length} trades</div><div class="streak-strip">${tail.map(t => `<i style="background:${t.pnl > 0 ? 'var(--good)' : t.pnl < 0 ? 'var(--bad)' : 'var(--muted)'};opacity:${Math.min(1, .35 + Math.abs(t.r) / 3)}" title="${t.day} ${fmtR(t.r)}"></i>`).join('')}</div>
    <div class="muted small" style="margin-top:6px">A low win-rate / high-R model runs long losing streaks by design: size so ${maxL} losses in a row stays well inside the $2,000 MLL.</div>`;
}

function renderMaeMfe() {
  const el = need('maemfe', 3); if (!el) return;
  const pts = A.set.trades.filter(t => t.mae != null && t.mfe != null);
  if (!pts.length) { el.innerHTML = waiting('No MAE / MFE recorded for this source'); return; }
  const W = pts.filter(t => t.pnl > 0), Lo = pts.filter(t => t.pnl <= 0);
  const cap = W.length ? mean(W.filter(t => t.mfe > 0).map(t => Math.min(1.5, t.r / t.mfe))) : null;
  if (!el.querySelector('canvas')) el.innerHTML = `<div class="kst-row" id="mmStats"></div><div class="chart-box h260" style="margin-top:8px"><canvas id="anMM"></canvas></div><div class="muted small" style="margin-top:6px">Heat taken (MAE) vs best open profit (MFE) in R. Winners far right with small MAE are clean; losers high on MFE gave back a winner.</div>`;
  $('#mmStats', el).innerHTML = stat('Winners median MAE', fmtR(median(W.map(t => t.mae))), 'heat before winning') + stat('Losers median MFE', fmtR(median(Lo.map(t => t.mfe))), 'best before losing') +
    stat('Avg capture', cap != null ? Math.round(cap * 100) + '%' : '—', 'R banked / MFE') + stat('Left on table', fmtN(sum(W.map(t => Math.max(0, t.mfe - t.r))), 1) + 'R', 'winners, MFE − R');
  const clip = (v) => Math.min(6, v);
  cj('anMM', { type: 'scatter', data: { datasets: [
    { label: 'Winners', data: W.map(t => ({ x: clip(t.mae), y: clip(t.mfe), t })), backgroundColor: css('--good') + 'b0', pointRadius: 3 },
    { label: 'Losers', data: Lo.map(t => ({ x: clip(t.mae), y: clip(t.mfe), t })), backgroundColor: css('--bad') + '90', pointRadius: 3 }] },
    options: baseOpts({ interaction: { mode: 'nearest', intersect: true }, plugins: { legend: { display: true, position: 'top', align: 'end' }, tooltip: { callbacks: { label: (c) => { const t = c.raw.t; return `${t.day} ${t.dir === 1 ? 'L' : 'S'} ${t.grade || ''} · MAE ${fmtN(t.mae, 2)}R · MFE ${fmtN(t.mfe, 2)}R · ${fmtR(t.r)} ${t.exit || ''}`; } } } },
      scales: { x: { min: 0, max: 6, title: { display: true, text: 'MAE (R)' }, grid: { color: css('--grid') } }, y: { min: 0, max: 6, title: { display: true, text: 'MFE (R)' } } } }) });
}

let bdDim = pref.get('bdDim', 'grade');
const DIMS = [['grade', 'Grade', t => t.grade || '—'], ['kz', 'Killzone', t => t.kz], ['dir', 'Direction', t => t.dir === 1 ? 'Long' : 'Short'], ['regime', 'Regime', t => t.regime || '—'],
  ['exit', 'Exit', t => t.exit || '—'], ['trigger', 'Trigger', t => t.trigger || '—'], ['dow', 'Weekday', t => DOW[dowOf(t.day)]], ['hour', 'Hour', t => String(etParts(t.entry_t).h).padStart(2, '0') + ':00']];
function bdRows() {
  const [, , f] = DIMS.find(d => d[0] === bdDim) || DIMS[0];
  const by = {};
  for (const t of A.set.trades) (by[f(t)] ||= []).push(t);
  return Object.entries(by).map(([k, ts]) => ({ key: k, ...grp(ts) })).sort((a, b) => bdDim === 'grade' ? ['A+', 'A', 'B', 'C', 'D'].indexOf(a.key) - ['A+', 'A', 'B', 'C', 'D'].indexOf(b.key) : bdDim === 'hour' || bdDim === 'dow' ? 0 : b.n - a.n);
}
function renderBreakdown() {
  const el = need('breakdown'); if (!el) return;
  const rows = bdRows();
  const max = Math.max(.2, ...rows.map(r => Math.abs(r.avg_r || 0)));
  el.innerHTML = `<div class="seg sm bd-tabs" id="bdSeg2">${DIMS.map(([k, l]) => `<button data-v="${k}" class="${k === bdDim ? 'on' : ''}">${l}</button>`).join('')}</div>
    <div class="bd-row h"><span>${DIMS.find(d => d[0] === bdDim)[1]}</span><span class="m">n</span><span class="m">win %</span><span>avg R</span><span class="m">net</span><span class="m">PF</span></div>
    ${rows.map(r => `<div class="bd-row"><span class="k">${esc(r.key)}</span><span class="m">${r.n}</span><span class="m">${fmtN(r.wr, 0)}%</span>
      <span style="display:flex;align-items:center;gap:6px"><div class="dbar" style="flex:1"><span class="${r.avg_r >= 0 ? 'pos' : 'neg'}" style="${r.avg_r >= 0 ? 'left:50%' : `left:${50 - Math.abs(r.avg_r) / max * 50}%`};width:${Math.abs(r.avg_r) / max * 50}%"></span></div><b class="mono ${cls(r.avg_r)}" style="font-size:11.5px;min-width:52px;text-align:right">${fmtR(r.avg_r)}</b></span>
      <span class="m ${cls(r.pnl)}">${fmtS$(r.pnl)}</span><span class="m">${pfTxt(r.pf)}</span></div>`).join('')}
    <div class="muted small" style="margin-top:6px">Groups under ~20 trades are anecdotes. Grade weights only change after the confluence registry's fold tests agree.</div>`;
  $('#bdSeg2', el).onclick = (e) => { const b = e.target.closest('button'); if (b) { bdDim = b.dataset.v; pref.set('bdDim', bdDim); renderBreakdown(); } };
}

function renderRdist() {
  const el = need('rdist', 3); if (!el) return;
  const rs = A.set.trades.map(t => t.r).filter(v => v != null);
  const lo = -1.5, hi = 5, bw = .25, nb = Math.round((hi - lo) / bw);
  const bins = Array(nb + 1).fill(0);
  for (const r of rs) bins[Math.max(0, Math.min(nb, Math.floor((r - lo) / bw)))]++;
  const m = mean(rs), sd = Math.sqrt(mean(rs.map(r => (r - m) ** 2))), sk = sd ? mean(rs.map(r => ((r - m) / sd) ** 3)) : 0;
  if (!el.querySelector('canvas')) el.innerHTML = `<div class="kst-row" id="rdStats"></div><div class="chart-box h200" style="margin-top:8px"><canvas id="anRd"></canvas></div>`;
  $('#rdStats', el).innerHTML = stat('Mean', fmtR(m), `median ${fmtR(median(rs))}`, cls(m)) + stat('≥ +2R', Math.round(rs.filter(r => r >= 2).length / rs.length * 100) + '%', 'runners') + stat('≤ −1R', Math.round(rs.filter(r => r <= -1).length / rs.length * 100) + '%', 'full stops') + stat('Skew', fmtN(sk, 2), `σ ${fmtN(sd, 2)}R`);
  cj('anRd', { type: 'bar', data: { labels: bins.map((_, i) => i === nb ? `${hi}+` : (lo + i * bw).toFixed(2)), datasets: [{ data: bins, borderRadius: 2, backgroundColor: bins.map((_, i) => lo + i * bw >= 0 ? css('--good') : css('--bad')) }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { title: c => `${c[0].label}R bucket`, label: c => `${c.parsed.y} trades` } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 9 } }, y: { ticks: { precision: 0 } } } }) });
}

function renderRolling() {
  const el = need('rolling', 21); if (!el) return;
  const N = 20, ts = A.set.trades, lab = [], ar = [], wr = [];
  for (let i = N - 1; i < ts.length; i++) { const w = ts.slice(i - N + 1, i + 1); lab.push(ts[i].day); ar.push(mean(w.map(t => t.r))); wr.push(w.filter(t => t.pnl > 0).length / N * 100); }
  if (!el.querySelector('canvas')) el.innerHTML = `<div class="chart-box h220"><canvas id="anRoll"></canvas></div><div class="muted small" style="margin-top:6px">Rolling ${N}-trade expectancy (R) and win rate. Dips below zero that last are the regime telling you something.</div>`;
  cj('anRoll', { type: 'line', data: { labels: lab, datasets: [
    { label: `avg R (${N})`, data: ar, borderColor: css('--accent'), borderWidth: 1.8, pointRadius: 0, yAxisID: 'y', fill: { target: 'origin', above: css('--good') + '30', below: css('--bad') + '30' } },
    { label: `win % (${N})`, data: wr, borderColor: css('--gold'), borderWidth: 1.2, pointRadius: 0, yAxisID: 'y1', borderDash: [3, 3] }] },
    options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'end' } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { grid: { color: css('--grid') }, title: { display: true, text: 'R' } }, y1: { position: 'right', min: 0, max: 100, grid: { display: false }, ticks: { callback: v => v + '%' } } } }) });
}

function renderExits() {
  const el = need('exits'); if (!el) return;
  const by = {};
  for (const t of A.set.trades) (by[t.exit || '—'] ||= []).push(t);
  const rows = Object.entries(by).map(([k, ts]) => ({ key: k, ...grp(ts) })).sort((a, b) => b.n - a.n);
  const pal = [css('--accent'), css('--good'), css('--bad'), css('--gold'), css('--amt'), css('--ssl'), css('--bsl'), css('--fvg'), css('--muted')];
  if (!el.querySelector('canvas')) el.innerHTML = `<div style="display:grid;grid-template-columns:140px 1fr;gap:12px;align-items:center"><div class="chart-box" style="height:140px"><canvas id="anEx"></canvas></div><div id="exTbl"></div></div>`;
  $('#exTbl', el).innerHTML = rows.map((r, i) => `<div class="acct-row" style="margin-top:5px"><span><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${pal[i % pal.length]};margin-right:6px"></i>${esc(r.key)}</span><b>${r.n} · <span class="${cls(r.avg_r)}">${fmtR(r.avg_r)}</span></b></div>`).join('');
  cj('anEx', { type: 'doughnut', data: { labels: rows.map(r => r.key), datasets: [{ data: rows.map(r => r.n), backgroundColor: rows.map((_, i) => pal[i % pal.length]), borderColor: css('--surface'), borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '64%', plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.label}: ${c.parsed} trades` } } } } });
}

function renderHold() {
  const el = need('hold'); if (!el) return;
  const B = [[1, 1, '1 bar'], [2, 2, '2'], [3, 4, '3–4'], [5, 8, '5–8'], [9, 16, '9–16'], [17, 1e9, '17+']];
  const rows = B.map(([a, b, l]) => { const ts = A.set.trades.filter(t => t.bars != null && t.bars >= a && t.bars <= b); return { l, ...grp(ts) }; });
  const max = Math.max(.2, ...rows.map(r => Math.abs(r.avg_r || 0)));
  el.innerHTML = `${rows.map(r => `<div class="bd-row" style="grid-template-columns:60px 40px 1fr 60px"><span class="k">${r.l}</span><span class="m">${r.n}</span>
      <div class="dbar"><span class="${(r.avg_r || 0) >= 0 ? 'pos' : 'neg'}" style="${(r.avg_r || 0) >= 0 ? 'left:50%' : `left:${50 - Math.abs(r.avg_r) / max * 50}%`};width:${Math.abs(r.avg_r || 0) / max * 50}%"></span></div><span class="m ${cls(r.avg_r)}">${fmtR(r.avg_r)}</span></div>`).join('')}
    <div class="muted small" style="margin-top:6px">Average R by how long the trade was held (5m bars). The 30-minute time stop shapes the short end.</div>`;
}

function renderCumR() {
  const el = need('cumr', 2); if (!el) return;
  let a = 0, l = 0, s = 0;
  const lab = [], all = [], lg = [], sh = [];
  for (const t of A.set.trades) { a += t.r; if (t.dir === 1) l += t.r; else s += t.r; lab.push(t.day); all.push(+a.toFixed(2)); lg.push(+l.toFixed(2)); sh.push(+s.toFixed(2)); }
  if (!el.querySelector('canvas')) el.innerHTML = `<div class="chart-box h220"><canvas id="anCum"></canvas></div>`;
  meta('cumr', `<span class="mono small">${fmtN(a, 1)}R · L ${fmtN(l, 1)} · S ${fmtN(s, 1)}</span>`);
  cj('anCum', { type: 'line', data: { labels: lab, datasets: [
    { label: 'All', data: all, borderColor: css('--accent'), borderWidth: 2.2, pointRadius: 0 },
    { label: 'Longs', data: lg, borderColor: css('--good'), borderWidth: 1.3, pointRadius: 0 },
    { label: 'Shorts', data: sh, borderColor: css('--bad'), borderWidth: 1.3, pointRadius: 0 }] },
    options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'end' } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { grid: { color: css('--grid') }, title: { display: true, text: 'cumulative R' } } } }) });
}

function renderHeader() {
  const el = $('#anSrcNote'); if (!el) return;
  if (!A.set) { el.innerHTML = `<span class="muted">${esc(A.note || 'loading…')}</span>`; return; }
  const g = grp(A.set.trades);
  el.innerHTML = `<b>${esc(A.set.label)}</b> · showing ${esc(A.set.from || '')} → ${esc(A.set.to || '')} · ${g.n} trades · ${fmtS$(g.pnl)} · ${fmtR(g.avg_r)} avg · PF ${pfTxt(g.pf)}`;
}

function renderAll() {
  renderHeader();
  for (const f of [renderYheat, renderHxw, renderMonths, renderQuarters, renderFreq, renderStreaks, renderMaeMfe, renderBreakdown, renderRdist, renderRolling, renderExits, renderHold, renderCumR]) {
    try { f(); } catch (e) { console.error('analytics widget', f.name, e); }
  }
}

// ------------------------------------------------------------------ page
const tradeRows = () => (A.set?.trades || []).map(t => ({ day: t.day, entry_et: etStr(t.entry_t, true), dir: t.dir === 1 ? 'long' : 'short', grade: t.grade, killzone: t.kz, trigger: t.trigger, exit: t.exit, r: t.r, pnl: t.pnl, mae: t.mae, mfe: t.mfe, bars: t.bars, regime: t.regime }));
export function initAnalytics() {
  const page = $('#page-analytics'); if (!page) return;
  page.innerHTML = `<div class="page-tools"><span class="lbl">Source</span><div class="seg sm" id="anSrc"></div><span class="lbl">Range</span><div class="seg sm" id="anRange"></div>
      <span class="spacer"></span><button class="btn ghost sm" id="anCsv">⇩ Trades CSV</button><button class="btn ghost sm" id="anLayout">⚙ Layout</button></div>
    <div class="banner info small" id="anSrcNote">loading…</div><div id="anGrid"></div>`;
  const srcs = [['bt', 'Backtest · loaded'], ['5y', '5y windowed'], ['paper', 'Paper']];
  $('#anSrc').innerHTML = srcs.map(([k, l]) => `<button data-v="${k}" class="${k === A.src ? 'on' : ''}">${l}</button>`).join('');
  $('#anRange').innerHTML = [['all', 'All'], ['3y', '3y'], ['1y', '1y'], ['6m', '6m'], ['120', '120 sessions']].map(([k, l]) => `<button data-v="${k}" class="${k === A.range ? 'on' : ''}">${l}</button>`).join('');
  $('#anSrc').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; A.src = b.dataset.v; pref.set('anSrc', A.src); $$('#anSrc button').forEach(x => x.classList.toggle('on', x === b)); load(); };
  $('#anRange').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; A.range = b.dataset.v; pref.set('anRange', A.range); $$('#anRange button').forEach(x => x.classList.toggle('on', x === b)); load(); };
  $('#anCsv').onclick = () => saveCSV(`liquidity_trades_${A.src}`, tradeRows());
  $('#anLayout').onclick = () => openLayout('analytics');
  const W = (id, title, size, csv) => widget({ id, page: 'analytics', title, size, csv });
  W('yheat', 'P&amp;L calendar · every session', 'xl', () => ({ name: 'daily_pnl', rows: A.set?.days || [] }));
  W('quarters', 'Five years by quarter · NQ futures', 'xl', () => ({ name: 'quarters', rows: qHist?.periods?.length && A.src === '5y' ? qHist.periods : (A.set ? quarterRows() : []) }));
  W('freq', 'Trades per week vs the 2–4 band', 'l', () => ({ name: 'weekly_trades', rows: A.set ? weekCounts() : [] }));
  W('hxw', 'Hour × weekday', 'l');
  W('months', 'Monthly returns', 'l');
  W('breakdown', 'Edge breakdown', 'l', () => ({ name: 'breakdown_' + bdDim, rows: A.set ? bdRows() : [] }));
  W('maemfe', 'MAE / MFE · heat vs run', 'l', () => ({ name: 'mae_mfe', rows: tradeRows().map(t => ({ day: t.day, entry_et: t.entry_et, r: t.r, mae: t.mae, mfe: t.mfe, exit: t.exit })) }));
  W('streaks', 'Streaks', 'l');
  W('rdist', 'R-multiple distribution', 'm');
  W('exits', 'Exit mix', 'm');
  W('hold', 'Holding time vs R', 'm');
  W('rolling', 'Rolling 20-trade edge', 'l');
  W('cumr', 'Cumulative R · long vs short', 'l', () => ({ name: 'cum_r', rows: tradeRows().map(t => ({ day: t.day, dir: t.dir, r: t.r })) }));
  buildGrid('analytics', $('#anGrid'));
  on(() => { if (A.src === 'bt') load(); });
}
export async function showAnalytics() {
  if (!A.set && !A.loading) load();
  // 5-year history from the dash API (contract #12) when deployed
  const h = await dash('/api/dash/history?by=quarter', { ttl: 600000, keep: true });
  if (h?.status === 'ok') { qHist = h; renderQuarters(); }
  window.dispatchEvent(new Event('resize'));
}
