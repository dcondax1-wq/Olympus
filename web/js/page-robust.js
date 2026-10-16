import { $, esc, fmtN, fmt$, fmtS$, fmtR, cls, store, css, api, busy, toast } from './util.js';
import { S, on, cj, baseOpts } from './state.js';

const NUMERIC = ['min_rr', 'max_rr', 'fallback_rr', 'risk_usd', 'min_score', 'arm_expiry_min', 'leg_lookback_min', 'max_trades_day', 'daily_max_loss', 'partial_pct', 'partial_r', 'slippage_ticks', 'cushion_frac', 'w_htf', 'w_lrl', 'w_amt', 'w_smt'];

export function init() {
  on(renderOOS);
  $('#optX').innerHTML = NUMERIC.map(k => `<option ${k === 'min_rr' ? 'selected' : ''}>${k}</option>`).join('');
  $('#optY').innerHTML = NUMERIC.map(k => `<option ${k === 'max_rr' ? 'selected' : ''}>${k}</option>`).join('');
  $('#stressRun').onclick = runStress;
  $('#optRun').onclick = runOpt;
  $('#longRun').onclick = runLong;
  $('#exitRun').onclick = runExit;
  $('#placeboRun').onclick = runPlacebo;
}

async function runPlacebo() {
  const sym = $('#placeboSym').value || S.sym;
  busy(true);
  $('#placeboOut').textContent = 'Running 500 placebo strategies…';
  try {
    const r = await api('/api/placebo', { sym, tf: '5m', params: S.params });
    if (!r.n_trades) { $('#placeboOut').textContent = 'No trades to test.'; busy(false); return; }
    const centers = r.edges.slice(0, -1).map((e, i) => (e + r.edges[i + 1]) / 2);
    cj('placeboChart', {
      type: 'bar',
      data: { labels: centers.map(c => (c >= 0 ? '+' : '') + c.toFixed(2)), datasets: [{ data: r.hist, backgroundColor: centers.map(c => c >= r.real ? css('--gold') : css('--muted')), borderRadius: 3, borderSkipped: 'start' }] },
      options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { title: c => `placebo avg R ≈ ${c[0].label}`, label: c => `${c.parsed.y} of 500 runs` } } },
        scales: { x: { title: { display: true, text: `placebo average R per trade · real strategy = ${r.real >= 0 ? '+' : ''}${r.real}R` }, grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { ticks: { precision: 0 } } } }),
    });
    const good = r.p_value <= 0.05;
    $('#placeboOut').innerHTML = `<b>${sym}</b> · ${r.n_trades} trades · real <b class="${cls(r.real)}">${fmtR(r.real)}</b> vs placebo mean ${fmtR(r.placebo_mean)} (top 1%: ${fmtR(r.placebo_p99)}).
      <b>p = ${r.p_value}</b> ${good ? '<span class="up">✔ beats random: entries carry real information</span>' : '<span class="dn">✖ not distinguishable from (or worse than) random</span>'}.
      Same entries, opposite side: ${fmtR(r.flipped)}. 90% confidence interval of avg R: ${fmtR(r.ci90[0])} to ${fmtR(r.ci90[1])}.`;
  } catch (e) { toast(e.message); }
  busy(false);
}

async function runExit() {
  busy(true);
  $('#exitOut').innerHTML = '<div class="empty">Running ~35 backtests…</div>';
  try {
    const r = await api('/api/exitstudy', { sym: S.sym, tf: S.tf, params: S.params });
    let html = '';
    for (const [g, rows] of Object.entries(r.groups)) {
      const bestIs = Math.max(...rows.map(x => x.is.avg_r)), bestOos = Math.max(...rows.map(x => x.oos.avg_r));
      const cur = rows[0];
      html += `<div class="mini-label" style="margin:10px 0 4px">${g}</div><table class="tbl"><tr><th>Variant</th><th>Before split</th><th>After split</th><th>All</th><th>Net</th><th>Verdict</th></tr>` +
        rows.map((x, i) => {
          const both = x.is.avg_r > cur.is.avg_r + 0.02 && x.oos.avg_r > cur.oos.avg_r + 0.02;
          const worse = x.is.avg_r < cur.is.avg_r - 0.02 && x.oos.avg_r < cur.oos.avg_r - 0.02;
          const verdict = i === 0 ? '<span class="tag-chip">current</span>' : both ? '<span class="tag-chip" style="background:var(--good);color:#fff">better both halves</span>'
            : worse ? '<span class="tag-chip" style="background:var(--bad);color:#fff">worse both halves</span>' : '<span class="muted small">mixed</span>';
          const c = (v, best) => `<span class="${cls(v)}" style="${Math.abs(v - best) < 1e-9 ? 'font-weight:800' : ''}">${fmtR(v)}</span>`;
          return `<tr><td>${esc(x.name)}</td><td class="mono">${x.is.n}t ${c(x.is.avg_r, bestIs)}</td><td class="mono">${x.oos.n}t ${c(x.oos.avg_r, bestOos)}</td>
            <td class="mono">${x.all.n}t ${fmtR(x.all.avg_r)} · PF ${fmtN(x.all.pf)}</td><td class="mono ${cls(x.all.net)}">${fmtS$(x.all.net)}</td><td>${verdict}</td></tr>`;
        }).join('') + '</table>';
    }
    html += `<div class="note">"Better both halves" = beats the current setting before <i>and</i> after ${r.split} by more than 0.02R. Only those are worth adopting; "mixed" results are usually noise.</div>`;
    $('#exitOut').innerHTML = html;
    const a = r.anatomy;
    cj('anatomyChart', {
      type: 'line',
      data: { labels: a.levels.map(x => '+' + x + 'R'), datasets: [
        { label: 'All trades reaching', data: a.reach_all, borderColor: css('--accent'), borderWidth: 2, pointRadius: 3 },
        { label: 'Losers that first reached', data: a.reach_losers, borderColor: css('--bad'), borderWidth: 2, pointRadius: 3 },
        { label: 'Winners that first heated to −', data: a.winners_mae, borderColor: css('--gold'), borderWidth: 2, pointRadius: 3, borderDash: [5, 4] },
      ] },
      options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'start' }, tooltip: { callbacks: { label: c => `${c.dataset.label} ${c.label}: ${c.parsed.y}%` } } },
        scales: { x: { grid: { display: false } }, y: { max: 100, ticks: { callback: v => v + '%' } } } }),
    });
    const i1 = a.levels.indexOf(1);
    $('#anatomyNote').innerHTML = `${a.reach_all[i1]}% of trades reach +1R, but only ${a.reach_losers[i1] ?? 0}% of losers do, so breakeven at +1R rarely costs a winner.
      Just ${a.winners_mae[a.levels.indexOf(0.5)] ?? 0}% of winners heat past −0.5R. ${a.reach_all[a.levels.indexOf(4)]}% run to +4R, so partials and trails that cut runners lose money.`;
  } catch (e) { toast(e.message); $('#exitOut').innerHTML = ''; }
  busy(false);
}
export function show() {
  const syms = Object.keys(S.meta?.available || {}).filter(s => S.meta.available[s].includes('5m'));
  const el = $('#placeboSym');
  if (el && !el.options.length) el.innerHTML = syms.map(s => `<option ${s === S.sym ? 'selected' : ''}>${s}</option>`).join('');
}

const parseList = (s) => s.split(/[ ,]+/).filter(Boolean).map(Number).filter(x => !isNaN(x));
const summ = (trs) => {
  const n = trs.length; if (!n) return { n: 0, net: 0, pf: 0, wr: 0, avg_r: 0 };
  const gp = trs.filter(t => t.pnl > 0).reduce((a, t) => a + t.pnl, 0), gl = -trs.filter(t => t.pnl <= 0).reduce((a, t) => a + t.pnl, 0);
  return { n, net: gp - gl, pf: gl ? gp / gl : 99, wr: trs.filter(t => t.pnl > 0).length / n * 100, avg_r: trs.reduce((a, t) => a + t.pnl_r, 0) / n };
};
const statRow = (name, s) => `<tr><td>${name}</td><td class="mono">${s.n}</td><td class="mono ${cls(s.net)}">${fmtS$(s.net)}</td><td class="mono">${fmtN(s.pf)}</td><td class="mono">${fmtN(s.wr, 1)}%</td><td class="mono ${cls(s.avg_r)}">${fmtR(s.avg_r)}</td></tr>`;
const head = '<tr><th>Scenario</th><th>Trades</th><th>Net</th><th>PF</th><th>Win%</th><th>Avg R</th></tr>';

async function runStress() {
  busy(true);
  try {
    const r = await api('/api/stress', { sym: S.sym, tf: S.tf, params: S.params });
    const names = { baseline: 'Baseline', slippage_2t: 'Slippage 2 ticks/side', slippage_3t: 'Slippage 3 ticks/side', commission_x2: 'Commissions ×2', minus_best_3: 'Remove best 3 trades', minus_best_5: 'Remove best 5 trades' };
    $('#stressOut').innerHTML = `<table class="tbl">${head}${Object.entries(names).map(([k, n]) => statRow(n, r[k])).join('')}</table>
      <div class="mini-label" style="margin:12px 0 6px">Walk-forward folds (contiguous blocks)</div>
      <table class="tbl">${head}${r.folds.map(f => statRow(`${f.from} → ${f.to}`, f)).join('')}</table>
      <div class="note">${r.folds.every(f => f.net > 0) ? '✓ Every fold is profitable, so the edge is not one hot streak.' : '⚠ At least one fold loses money. Expect regime-dependent performance.'}
      ${r.minus_best_5.net > 0 ? ' Still profitable without the 5 best trades.' : ' Depends on a few outlier winners. Normal for runner-style systems, but expect lumpy equity.'}</div>`;
  } catch (e) { toast(e.message); }
  busy(false);
}

async function runOpt() {
  const x = { name: $('#optX').value, values: parseList($('#optXv').value) };
  const y = { name: $('#optY').value, values: parseList($('#optYv').value) };
  if (x.values.length * y.values.length > 64) { toast('Keep the grid at 64 cells or fewer'); return; }
  busy(true);
  $('#optOut').innerHTML = '<div class="empty">Running ' + x.values.length * y.values.length + ' backtests…</div>';
  try {
    const r = await api('/api/optimize', { sym: S.sym, tf: S.tf, params: S.params, x, y });
    const all = r.grid.flat();
    const max = Math.max(1, ...all.map(c => Math.abs(c.net)));
    const cur = { x: S.res.params[x.name], y: S.res.params[y.name] };
    let html = `<div class="heat" style="grid-template-columns:70px repeat(${r.xs.length},1fr)"><div class="ax">${esc(y.name)} ↓ / ${esc(x.name)} →</div>${r.xs.map(v => `<div class="ax">${v}</div>`).join('')}`;
    for (const row of r.grid.slice().reverse()) {
      html += `<div class="ax">${row[0].y}</div>`;
      for (const c of row) {
        const a = Math.abs(c.net) / max;
        const bg = c.net >= 0 ? `rgba(12,163,12,${0.12 + a * 0.6})` : `rgba(208,59,59,${0.12 + a * 0.6})`;
        const isCur = c.x === cur.x && c.y === cur.y;
        html += `<div class="c" style="background:${bg};${isCur ? 'outline:2px solid var(--accent)' : ''}" title="${x.name}=${c.x}, ${y.name}=${c.y}: ${c.n} trades, PF ${c.pf}, WR ${c.wr}%">${fmtS$(c.net)}<br><span style="font-weight:500;opacity:.8">${c.n}t · ${fmtR(c.avg_r)}</span></div>`;
      }
    }
    html += '</div>';
    const pos = all.filter(c => c.net > 0).length;
    html += `<div class="note">${pos}/${all.length} cells profitable. ${pos / all.length > 0.75 ? '✓ Broad plateau, so the edge does not hinge on exact settings.' : '⚠ Narrow profitable region, a sign of overfitting risk.'} Outlined cell = current setting.</div>`;
    $('#optOut').innerHTML = html;
  } catch (e) { toast(e.message); $('#optOut').innerHTML = ''; }
  busy(false);
}

let oosSplit = null;
function renderOOS(res) {
  if (!res) return;
  const days = res.days.map(d => d.date);
  if (!oosSplit || !days.includes(oosSplit)) oosSplit = days.includes('2026-09-22') ? '2026-09-22' : days[Math.floor(days.length * 0.65)];
  const ins = res.trades.filter(t => t.day < oosSplit), oos = res.trades.filter(t => t.day >= oosSplit);
  $('#oosOut').innerHTML = `<div class="row gap" style="margin-bottom:8px"><span class="muted small">split at</span><select class="sel sm" id="oosSel">${days.map(d => `<option ${d === oosSplit ? 'selected' : ''}>${d}</option>`).join('')}</select></div>
    <table class="tbl">${head}${statRow('In-sample (before split)', summ(ins))}${statRow('Out-of-sample (after split)', summ(oos))}${statRow('Longs', summ(res.trades.filter(t => t.dir === 1)))}${statRow('Shorts', summ(res.trades.filter(t => t.dir === -1)))}</table>
    <div class="note">Default split 2026-09-22: the robust defaults came from a 384-config grid scored only on data before this date. With the current defaults NQ is profitable out-of-sample in 363 of 384 grid configs; ES in 0 of 384, so ES is not recommended. Caveat: several study rounds have now looked at the after-split window, so forward paper trading is the real test.</div>`;
  $('#oosSel').onchange = (e) => { oosSplit = e.target.value; renderOOS(S.res); };
}

// owner rule: real CME futures only. The long-horizon check runs the full NQ futures history (five years, back-adjusted NQ1!).
async function runLong() {
  if (!S.meta.available.NQ?.includes('5m')) { $('#longOut').innerHTML = '<div class="empty">No NQ futures 5m history loaded.</div>'; return; }
  busy(true);
  try {
    const r = S.res && S.sym === 'NQ' && S.tf === '5m' ? S.res : await api('/api/backtest', { sym: 'NQ', tf: '5m', params: S.params, plan: S.plan });
    const s = r.stats;
    const byM = {};
    for (const t of r.trades) { const m = t.day.slice(0, 7); (byM[m] ||= []).push(t); }
    const months = Object.keys(byM).sort();
    const posM = months.filter(m => byM[m].reduce((a, t) => a + t.pnl, 0) > 0).length;
    const byY = {};
    for (const t of r.trades) { const y = t.day.slice(0, 4); (byY[y] ||= []).push(t); }
    $('#longOut').innerHTML = `<div class="grid kpis small">
      ${[['Trades', s.trades], ['Trades/wk', s.trades_per_week], ['Win rate', s.win_rate + '%'], ['PF', s.profit_factor], ['Net', fmtS$(s.net)], ['Avg R', fmtR(s.avg_r)], ['Max DD', fmt$(s.max_dd)], ['Green months', `${posM}/${months.length}`]]
        .map(([k, v]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('')}</div>
      <div class="chart-box h200"><canvas id="longEq"></canvas></div>
      <table class="tbl" style="margin-top:8px">${head}${Object.keys(byY).sort().map(y => statRow(y, summ(byY[y]))).join('')}</table>
      <div class="note">${r.range[0]} → ${r.range[1]} · NQ futures (CME, back-adjusted). Rolling eval pass rate ${r.rolling.pass_rate ?? '—'}% over ${r.rolling.completed} starts. <a class="link" data-goto="analytics">Quarter detail on Deep Stats →</a></div>`;
    let eq = 0;
    cj('longEq', { type: 'line', data: { labels: r.trades.map(t => t.day), datasets: [{ data: r.trades.map(t => (eq += t.pnl)), borderColor: css('--accent'), borderWidth: 1.6, pointRadius: 0 }] },
      options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { ticks: { callback: v => '$' + (v / 1000).toFixed(0) + 'k' } } } }) });
  } catch (e) { toast(e.message); }
  busy(false);
}
