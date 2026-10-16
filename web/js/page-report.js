import { $, esc, fmtN, fmtS$, fmtR, cls, etStr, api, toast, store, tradingDay } from './util.js';
import { S, on } from './state.js';
import { feed, go } from './app.js';
import * as chartPage from './page-chart.js';

let day = null;
export function init() {
  on(() => { if (S.page === 'report') render(); });
  $('#repDay').onchange = (e) => { day = e.target.value; render(); };
  $('#repCopy').onclick = async () => {
    const txt = reportText();
    try { await navigator.clipboard.writeText(txt); toast('Report copied'); } catch (e) { toast('Copy blocked by the browser'); }
  };
  $('#repSend').onclick = async () => {
    const r = await api('/api/alerts/send', { text: reportText(), kind: 'daily', force: true });
    toast(r.sent ? 'Report sent to your phone' : 'Set up Telegram or Discord in Settings first');
  };
  $('#repChart').onclick = () => { chartPage.openDay(day); go('chart'); };
}
export function show() { render(); }

function dayData() {
  const r = S.res;
  const d = r.days.find(x => x.date === day) || {};
  const trs = r.trades.filter(t => t.day === day);
  const evs = r.events.filter(e => tradingDay(e.t) === day);
  return { d, trs, evs };
}

function render() {
  const r = S.res;
  if (!r) return;
  const days = r.days.slice().reverse();
  if (!day || !r.days.some(x => x.date === day)) day = (days.find(x => x.trades) || days[0]).date;
  $('#repDay').innerHTML = days.map(x => `<option value="${x.date}" ${x.date === day ? 'selected' : ''}>${x.date} · ${x.trades ? `${x.trades} trade${x.trades > 1 ? 's' : ''} ${fmtS$(x.pnl)}` : 'no trades'}${x.regime ? ' · ' + x.regime : ''}</option>`).join('');
  const { d, trs, evs } = dayData();
  const wins = trs.filter(t => t.pnl > 0).length;
  const avgR = trs.length ? trs.reduce((a, t) => a + t.pnl_r, 0) / trs.length : null;
  const k = [['Day P&L', fmtS$(d.pnl || 0), cls(d.pnl)], ['Trades', `${trs.length}`, ''], ['Win / loss', `${wins} / ${trs.length - wins}`, ''],
    ['Avg R', avgR == null ? '—' : fmtR(avgR), cls(avgR)], ['Grades', trs.map(t => t.grade || '?').join(' ') || '—', ''],
    ['Regime', (d.regime || '—').toUpperCase(), d.regime === 'trending' ? 'dn' : 'up'], ['Balance', fmtN(d.balance || 0, 0), ''], ['Trailing MLL', fmtN(d.mll || 0, 0), '']];
  $('#repKpis').innerHTML = k.map(([a, b, c]) => `<div class="kpi"><div class="k">${a}</div><div class="v ${c}">${esc(b)}</div></div>`).join('');
  const signs = (t) => Object.entries(t.xsig || {}).sort((a, b) => a[1].k - b[1].k).map(([n, x]) =>
    `<span class="pill ${t.exit_signal === n ? 'bad' : ''}" title="bar +${x.k} · ${x.r >= 0 ? '+' : ''}${x.r}R at the time${x.gain != null ? ` · leaving would have made ${x.gain >= 0 ? '+' : ''}${x.gain}R more` : ''}">${t.exit_signal === n ? '✕ ' : '⚠ '}${esc(n)}</span>`).join(' ') || '<span class="muted small">none</span>';
  $('#repTrades').innerHTML = trs.length ? `<table class="tbl"><tr><th>Entry</th><th>Side</th><th>Grade</th><th>Trigger</th><th>Target</th><th>Exit</th><th>Warning signs</th><th>R</th><th>P&amp;L</th></tr>
    ${trs.map(t => `<tr><td class="mono">${etStr(t.entry_t)}</td><td><span class="dir ${t.dir === 1 ? 'L' : 'S'}">${t.dir === 1 ? 'LONG' : 'SHORT'}</span></td>
      <td><span class="grade g-${esc(t.grade || '').replace('+', 'p')}" style="font-size:11px;padding:2px 7px">${esc(t.grade || '—')}</span></td><td>${t.trigger}</td>
      <td class="small">${esc(t.target_label)}</td><td class="small">${t.exit_reason}</td><td class="small">${signs(t)}</td><td class="mono ${cls(t.pnl_r)}">${fmtR(t.pnl_r)}</td><td class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)}</td></tr>`).join('')}</table>`
    : '<div class="empty">No trades this session.</div>';
  feed($('#repFeed'), evs.slice().reverse());
  // takeaways: generated from what happened + your journal notes
  const J = store.get('journal', {});
  const notes = [];
  const sweeps = evs.filter(e => e.type === 'sweep' && !e.text.startsWith('Also')).length;
  const passes = evs.filter(e => e.type === 'skip' || e.type === 'news').length;
  notes.push(`${sweeps} liquidity sweep${sweeps === 1 ? '' : 's'} armed setups; ${trs.length} became trades and ${passes} candidate${passes === 1 ? ' was' : 's were'} passed on by the rules.`);
  for (const t of trs) {
    const pro = (t.checklist || []).filter(c => c.state * c.weight > 0).map(c => c.label);
    const con = (t.checklist || []).filter(c => c.state * c.weight < 0).map(c => c.label);
    notes.push(`${t.dir === 1 ? 'Long' : 'Short'} ${t.grade || ''} → ${t.exit_reason} ${fmtR(t.pnl_r)}. For: ${pro.slice(0, 3).join(', ') || '—'}. Against: ${con.slice(0, 2).join(', ') || 'nothing'}.`);
    const jn = J[`${S.sym}-${t.entry_t}`]?.note;
    if (jn) notes.push(`Your note: “${jn}”`);
  }
  if (d.regime === 'trending') notes.push('Trending regime: the bot traded at half size by design.');
  $('#repNotes').innerHTML = `<ul class="check">${notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>`;
}

function reportText() {
  const { d, trs } = dayData();
  const lines = [`📊 ${S.sym} daily report · ${day}`, `P&L ${fmtS$(d.pnl || 0)} · ${trs.length} trades · regime ${d.regime || '—'}`];
  for (const t of trs) lines.push(`${etStr(t.entry_t)} ${t.dir === 1 ? 'LONG' : 'SHORT'} ${t.grade || ''} ${t.trigger} → ${t.exit_reason} ${fmtR(t.pnl_r)} ${fmtS$(t.pnl)}`);
  lines.push(`Balance ${fmtN(d.balance || 0, 0)} · trailing max-loss ${fmtN(d.mll || 0, 0)}`);
  return lines.join('\n');
}
