import { $, $$, esc, fmtN, fmtS$, fmtR, cls, api, busy } from './util.js';
import { S, on, effective } from './state.js';
import { go } from './app.js';
import * as chartPage from './page-chart.js';

// Regimes page: real CME futures only (NQ by month + ES). No CFD data is offered or shown.
let study = null, studyKey = '';
export function init() { on(() => { if (S.page === 'regime') render(); }); }
export async function show() {
  render();
  const key = JSON.stringify(S.params || {});
  if (!study || key !== studyKey) {
    busy(true);
    try { study = await api('/api/regime', { params: S.params }); studyKey = key; } catch (e) { /* offline */ }
    busy(false);
    render();
  }
}

function weeksOf(p) {
  if (!p?.from || !p?.to) return null;
  return Math.max(1, Math.round((Date.parse(p.to) - Date.parse(p.from)) / (7 * 86400000)));
}

function render() {
  const r = S.res;
  if (!r) return;
  const days = r.days.filter(d => d.er10 != null);
  const last = days.at(-1) || {};
  const p = effective();
  const rot = days.filter(d => d.regime === 'rotational'), tre = days.filter(d => d.regime === 'trending');
  const k = [['Current regime', (last.regime || '—').toUpperCase(), last.regime === 'trending' ? 'dn' : 'up'],
    ['10-day efficiency', last.er10 != null ? fmtN(last.er10, 2) : '—', ''], ['5-day efficiency', last.er5 != null ? fmtN(last.er5, 2) : '—', ''],
    ['Trending threshold', p.regime_er10_max ? `> ${p.regime_er10_max}` : 'off', ''], ['In trending regime', p.regime_mode === 'skip' ? 'stand aside' : 'half size', ''],
    ['Rotational / trending days', `${rot.length} / ${tre.length}`, '']];
  $('#regKpis').innerHTML = k.map(([a, b, c]) => `<div class="kpi"><div class="k">${a}</div><div class="v ${c}">${esc(b)}</div></div>`).join('');

  // per-period table (futures only)
  const periods = study?.periods || [];
  const nqAll = periods.find(x => x.sym === 'NQ' && x.period.endsWith('all'));
  const wk = weeksOf(nqAll);
  if (study?.periods) {
    const cell = (x) => x ? `<td class="mono">${x.trades}t${x.days != null ? ` / ${x.days}d` : ''}</td><td class="mono ${cls(x.avg_r)}">${x.avg_r == null ? '—' : fmtR(x.avg_r)}</td><td class="mono ${cls(x.pnl)}">${fmtS$(x.pnl)}</td>` : '<td colspan="3">—</td>';
    $('#regTable').innerHTML = periods.length ? `<div class="table-wrap" style="max-height:none"><table class="tbl"><tr><th>Period</th><th>Sessions</th><th>Avg 10-day eff.</th><th colspan="3">All trades</th><th colspan="3">Rotational</th><th colspan="3">Trending</th></tr>
      ${periods.map(x => `<tr${x.period.endsWith('all') ? ' style="font-weight:600"' : ''}><td>${esc(x.period)}<div class="muted small mono">${esc(x.from || '')} → ${esc(x.to || '')}</div></td><td class="mono">${x.days}</td><td class="mono">${fmtN(x.er10, 2)}</td>${cell(x.total)}${cell(x.rotational)}${cell(x.trending)}</tr>`).join('')}</table></div>
      <div class="note">Real CME futures only, flat sizing so periods compare in R. This is about <b>${wk ?? 10} weeks</b> of history: a small sample, so treat the per-regime split as a hint, not proof. Months with few trending days cannot say much about the trending rule.</div>`
      : '<div class="empty">No futures periods with enough sessions yet.</div>';
  } else $('#regTable').innerHTML = '<div class="empty">Running the regime study on the futures history…</div>';

  // calendar
  const maxAbs = Math.max(1, ...r.days.map(d => Math.abs(d.pnl)));
  $('#regCal').innerHTML = `<div class="regcal">${r.days.map(d => {
    const a = Math.min(1, Math.abs(d.pnl) / maxAbs);
    return `<div class="rc ${d.regime || 'na'}" data-day="${d.date}" title="${d.date} · ${d.regime || 'n/a'} · eff ${d.er10 ?? '—'} · ${fmtS$(d.pnl)}">
      <span class="dd">${d.date.slice(5)}</span><span class="pp ${cls(d.pnl)}" style="opacity:${d.trades ? 0.5 + a / 2 : 0.35}">${d.trades ? (d.pnl > 0 ? '+' : '') + Math.round(d.pnl) : '·'}</span></div>`;
  }).join('')}</div><div class="row gap small" style="margin-top:8px"><span class="rc-key rotational"></span> rotational <span class="rc-key trending"></span> trending · click a day to open it</div>`;
  $$('#regCal [data-day]').forEach(c => c.onclick = () => { chartPage.openDay(c.dataset.day); go('chart'); });

  const trendTrades = nqAll?.trending?.trades;
  $('#regHow').innerHTML = `<ul class="check">
    <li><b>10-day efficiency ratio</b> = |net move over 10 sessions| ÷ the sum of each day's move. Near 0 = price rotated back and forth; near 1 = it moved in a straight line. Measured from completed sessions only, before the open.</li>
    <li>Above <b>${p.regime_er10_max || 0.45}</b> the market is treated as <b>trending</b>: the bot keeps taking its 1–4 trades a week but at <b>half size</b>, because sweep reversals fail more often in persistent trends.</li>
    <li><b>Data used: real CME futures only.</b> NQ${nqAll ? ` ${esc(nqAll.from)} → ${esc(nqAll.to)} (${nqAll.days} sessions, about ${wk} weeks)` : ''}, split by month, plus ES over the same weeks as a second market. That is roughly <b>10 weeks</b> of history, which is short: one unusual week can move a month's numbers a lot.</li>
    <li>${trendTrades != null ? `Only <b>${trendTrades}</b> NQ trade${trendTrades === 1 ? '' : 's'} fell on trending days in this window, so the half-size rule is` : 'The half-size rule is'} mostly <b>untested on real futures</b> so far. It stays on as a cautious default, not as a proven edge.</li>
    <li><b>More history:</b> import more CME bars to lengthen the record. On the <a class="link" data-goto="tv">TradingView page</a> export MNQ1! / NQ1! 5-minute chart data and drop the CSV in, or use <span class="mono">data/import_futures.py</span> (TradingView, NinjaTrader or Databento exports). Every page re-tests on the longer history automatically.</li>
    <li>Exits (break-even at 1R, 30-minute time stop, no partials) and the trend-day continuation setup (off) are unchanged. Re-check them here once a longer futures record is loaded.</li></ul>`;
}
