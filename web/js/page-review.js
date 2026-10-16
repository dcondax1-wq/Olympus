// Weekly Review: trades grouped by ISO week with auto-written takeaways, exit/grade mix and a monthly P&L heatmap.
import { $, $$, api, esc, fmt$, fmtS$, fmtN, fmtR, cls, etStr, etParts, toast } from './util.js';
import { S, on } from './state.js';

const CSS = `
.rv-mix{display:grid;gap:12px}
.rv-mix h4{margin:0 0 6px;font:600 10px var(--display);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.rv-bar{display:grid;grid-template-columns:92px 1fr 34px;gap:8px;align-items:center;font-size:12px;color:var(--ink-2);margin-top:5px}
.rv-bar .t{height:9px;border-radius:5px;background:var(--surface-2);overflow:hidden}
.rv-bar .t i{display:block;height:100%;border-radius:5px;background:var(--accent);transition:width .6s cubic-bezier(.2,.8,.2,1)}
.rv-bar .t i.g{background:var(--good)}.rv-bar .t i.b{background:var(--bad)}.rv-bar .t i.w{background:var(--warn)}
.rv-bar b{font:600 11px var(--mono);color:var(--ink);text-align:right}
.rv-take{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.rv-take li{display:grid;grid-template-columns:22px 1fr;gap:8px;font-size:13px;line-height:1.55;color:var(--ink-2);padding:9px 11px;border-radius:10px;background:var(--surface-2);border:1px solid var(--border)}
.rv-take li i{font-style:normal;color:var(--accent);font-weight:700}
.rv-take li.warn i{color:var(--warn)}.rv-take li.good i{color:var(--good)}.rv-take li.bad i{color:var(--bad)}
.rv-cal{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px}
.rv-cal .h{font:600 10px var(--display);letter-spacing:.1em;text-align:center;color:var(--muted);padding-bottom:2px}
.rv-cal .c{aspect-ratio:1.35;border-radius:8px;background:var(--surface-2);border:1px solid transparent;padding:5px 6px;display:flex;flex-direction:column;justify-content:space-between;cursor:pointer;position:relative;transition:transform .12s}
.rv-cal .c:hover{transform:translateY(-1px);border-color:var(--accent)}
.rv-cal .c.off{opacity:.28;cursor:default}
.rv-cal .c.sel{box-shadow:inset 0 0 0 1.5px var(--accent)}
.rv-cal .c .n{font:500 9.5px var(--mono);color:var(--muted)}
.rv-cal .c .p{font:700 11px var(--mono);text-align:right;color:var(--ink)}
.rv-cal .c .k{position:absolute;top:5px;right:6px;font:600 8.5px var(--mono);color:var(--muted)}
.rv-week-pill{font:600 11px var(--mono)}
.rv-best{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.rv-best div{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:8px 10px;font-size:12px;color:var(--ink-2)}
.rv-best b{display:block;font:700 16px var(--display);margin-top:2px}
@media (max-width:760px){.rv-best{grid-template-columns:1fr 1fr}.rv-cal .c{aspect-ratio:1.1;padding:4px}.rv-bar{grid-template-columns:76px 1fr 30px}}
`;

let data = null;        // { weeks, days, trades, exit_signals, stats, plan, source }
let week = null, month = null, loading = false;

// ------------------------------------------------------------------ date helpers (all on yyyy-mm-dd strings)
const parse = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d)); };
const iso = (dt) => dt.toISOString().slice(0, 10);
function isoWeek(s) {
  const d = parse(s); const dow = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dow);
  const y = d.getUTCFullYear(); const start = Date.UTC(y, 0, 1);
  return `${y}-W${String(Math.ceil(((d - start) / 86400000 + 1) / 7)).padStart(2, '0')}`;
}
function monday(s) { const d = parse(s); const dow = d.getUTCDay() || 7; d.setUTCDate(d.getUTCDate() - dow + 1); return iso(d); }
const addDays = (s, n) => { const d = parse(s); d.setUTCDate(d.getUTCDate() + n); return iso(d); };
const entryMin = (t) => { const p = etParts(t.entry_t); return p.h * 60 + p.mi; };

// ------------------------------------------------------------------ aggregation (mirrors engine/extras_api.py)
function buildWeeks(trades, days, xs) {
  const W = new Map();
  const wk = (date) => { const k = isoWeek(date); if (!W.has(k)) { const m = monday(date); W.set(k, { key: k, start: m, end: addDays(m, 4), trades: [], days: [] }); } return W.get(k); };
  for (const d of days) wk(d.date).days.push(d);
  for (const t of trades.slice().sort((a, b) => a.entry_t - b.entry_t)) wk(t.day).trades.push(t);
  const out = []; let prev = null;
  for (const k of [...W.keys()].sort()) {
    const w = W.get(k), tr = w.trades, n = tr.length;
    const wins = tr.filter(t => t.pnl > 0), losses = tr.filter(t => t.pnl <= 0);
    const rs = tr.map(t => t.pnl_r), pnl = tr.reduce((a, t) => a + t.pnl, 0);
    const exits = {}, grades = {};
    for (const t of tr) { exits[t.exit_reason || '?'] = (exits[t.exit_reason || '?'] || 0) + 1; grades[t.grade || '?'] = (grades[t.grade || '?'] || 0) + 1; }
    const dp = w.days.map(d => d.pnl || 0);
    const row = { ...w, n, wins: wins.length, losses: losses.length, win_rate: n ? wins.length / n * 100 : null, sum_r: rs.reduce((a, b) => a + b, 0), avg_r: n ? rs.reduce((a, b) => a + b, 0) / n : null,
      pnl, best: n ? tr.reduce((a, t) => t.pnl > a.pnl ? t : a) : null, worst: n ? tr.reduce((a, t) => t.pnl < a.pnl ? t : a) : null, exits, grades,
      best_day: dp.length ? Math.max(...dp) : null, worst_day: dp.length ? Math.min(...dp) : null, active_days: w.days.filter(d => d.trades).length };
    row.takeaways = takeaways(row, prev, xs);
    out.push(row); prev = row;
  }
  return out;
}

function takeaways(w, prev, xs) {
  const tr = w.trades, out = [];
  const add = (tone, text) => out.push({ tone, text });
  if (!tr.length) { add('', 'No trades this week: every candidate was filtered, or no pool was swept inside a killzone.'); return out; }
  const losers = tr.filter(t => t.pnl <= 0);
  const early = losers.filter(t => { const m = entryMin(t); return m >= 570 && m < 615; });
  if (losers.length && early.length) add(early.length / losers.length >= .5 ? 'warn' : '', `${early.length} of ${losers.length} loser${losers.length !== 1 ? 's' : ''} ${early.length !== 1 ? 'were' : 'was a'} first-45-minute entr${early.length !== 1 ? 'ies' : 'y'} (09:30–10:15), the window the discovery scan flagged as weakest.`);
  const gb = tr.filter(t => /giveback/i.test(t.exit_reason || '') || t.exit_signal === 'giveback');
  if (gb.length) { const g = (xs || []).find(x => x.key === 'giveback'); const avg = g?.avg_gain ?? 0.6; add('good', `Giveback fired ${gb.length} time${gb.length !== 1 ? 's' : ''} and saved an estimated ${fmtR(avg * gb.length)} versus riding those trades to the stop.`); }
  const timeX = tr.filter(t => /TIME/i.test(t.exit_reason || ''));
  if (timeX.length >= 2) { const a = timeX.reduce((s, t) => s + t.pnl_r, 0) / timeX.length; add(a < 0 ? 'warn' : '', `${timeX.length} trades left on the time stop averaging ${fmtR(a)}: ${a < 0 ? 'the setups stalled rather than failed outright.' : 'cutting stalls kept them from becoming full losers.'}`); }
  const gi = {}; for (const t of tr) (gi[t.grade || '?'] ||= []).push(t.pnl_r);
  const top = ['A+', 'A'].filter(g => gi[g]), low = ['C', 'D'].filter(g => gi[g]);
  if (top.length && low.length) {
    const mean = (gs) => { const all = gs.flatMap(g => gi[g]); return all.reduce((a, b) => a + b, 0) / all.length; };
    const a = mean(top), c = mean(low);
    add(a > c ? 'good' : 'warn', `${top.join('/')} grades averaged ${fmtR(a)}; ${low.join('/')} grades averaged ${fmtR(c)}. ${a > c ? 'The grade did its job.' : 'The grade did not separate them this week.'}`);
  }
  const L = tr.filter(t => t.dir === 1), Sh = tr.filter(t => t.dir === -1);
  if (L.length && Sh.length) { const lp = L.reduce((a, t) => a + t.pnl, 0), sp = Sh.reduce((a, t) => a + t.pnl, 0); add('', `${lp > sp ? 'Longs' : 'Shorts'} carried the week: longs ${fmtS$(lp)} over ${L.length}, shorts ${fmtS$(sp)} over ${Sh.length}.`); }
  const trend = tr.filter(t => t.regime === 'trending' || w.days.find(d => d.date === t.day)?.regime === 'trending');
  if (trend.length) add('', `${trend.length} trade${trend.length !== 1 ? 's' : ''} came on trending days at half size, averaging ${fmtR(trend.reduce((a, t) => a + t.pnl_r, 0) / trend.length)}.`);
  const byDay = {}; for (const t of tr) byDay[t.day] = (byDay[t.day] || 0) + 1;
  const busiest = Object.entries(byDay).sort((a, b) => b[1] - a[1])[0];
  if (busiest && busiest[1] >= 3) add('', `${busiest[1]} trades on ${busiest[0]}: the busiest session of the week.`);
  if (w.pnl > 0 && w.best_day != null) { const share = w.best_day / w.pnl * 100; if (share > 50) add('warn', `Best day was ${Math.round(share)}% of the week's profit, above the 50% consistency line; a payout week needs more even days.`); }
  if (w.worst_day != null && w.worst_day <= -800) add('bad', `Worst day ${fmtS$(w.worst_day)} came within reach of the $1,000 daily soft stop.`);
  const streak = (() => { let best = 0, cur = 0; for (const t of tr) { cur = t.pnl <= 0 ? cur + 1 : 0; best = Math.max(best, cur); } return best; })();
  if (streak >= 3) add('warn', `A run of ${streak} consecutive losers: check whether they shared a trigger or a session.`);
  if (prev && prev.n) { const d = (w.avg_r || 0) - (prev.avg_r || 0); add(d >= 0 ? 'good' : '', `Expectancy ${d >= 0 ? 'improved' : 'slipped'} ${Math.abs(d).toFixed(2)}R per trade versus the prior week (${fmtS$(prev.pnl)}).`); }
  return out;
}

// ------------------------------------------------------------------ data source
function fromRes(res) {
  const days = res.days.map(d => ({ date: d.date, pnl: d.pnl || 0, trades: d.trades || 0, balance: d.balance, mll: d.mll, regime: d.regime }));
  return { weeks: buildWeeks(res.trades, days, res.exit_signals), days, trades: res.trades, exit_signals: res.exit_signals || [], stats: res.stats, plan: res.plan, source: 'live backtest' };
}
async function fromServer() {
  const r = await api(`/api/extras/week?sym=${encodeURIComponent(S.sym)}&tf=${encodeURIComponent(S.tf)}`);
  // the server already aggregated, but rebuilding here keeps the richer client-side takeaways and avoids two code paths in the UI
  return { weeks: buildWeeks(r.trades, r.days, r.exit_signals), days: r.days, trades: r.trades, exit_signals: r.exit_signals || [], stats: r.stats, plan: r.plan, source: 'server (default params)' };
}

// ------------------------------------------------------------------ render
function render() {
  if (!$('#rvWeek')) return;
  if (!data) { $('#rvKpis').innerHTML = `<div class="empty" style="grid-column:1/-1">${loading ? 'Building the weekly review…' : 'Run a backtest to review your weeks.'}</div>`; return; }
  const weeks = data.weeks;
  if (!weeks.length) { $('#rvKpis').innerHTML = '<div class="empty" style="grid-column:1/-1">No sessions in this data set.</div>'; return; }
  if (!week || !weeks.some(w => w.key === week)) week = (weeks.slice().reverse().find(w => w.n) || weeks.at(-1)).key;
  const w = weeks.find(x => x.key === week), idx = weeks.indexOf(w), prev = weeks[idx - 1];
  if (!month) month = w.start.slice(0, 7);
  $('#rvWeek').innerHTML = weeks.slice().reverse().map(x => `<option value="${x.key}" ${x.key === week ? 'selected' : ''}>${x.key} · ${x.start.slice(5)} → ${x.end.slice(5)} · ${x.n ? `${x.n} trade${x.n > 1 ? 's' : ''} ${fmtS$(x.pnl)}` : 'no trades'}</option>`).join('');
  $('#rvWeekPill').textContent = `${data.source} · ${S.sym}`;
  // KPIs
  const dR = prev && prev.n && w.n ? w.avg_r - prev.avg_r : null;
  const k = [
    ['Week P&L', fmtS$(w.pnl), `${w.active_days} active of ${w.days.length} sessions`, cls(w.pnl)],
    ['Trades', String(w.n), `${w.wins}W / ${w.losses}L`, ''],
    ['Win rate', w.win_rate != null ? Math.round(w.win_rate) + '%' : '—', prev?.n ? `prior week ${prev.win_rate != null ? Math.round(prev.win_rate) + '%' : '—'}` : '', ''],
    ['Total R', fmtR(w.sum_r), w.avg_r != null ? `${fmtR(w.avg_r)} per trade${dR != null ? ` · ${dR >= 0 ? '▲' : '▼'} ${Math.abs(dR).toFixed(2)} wk/wk` : ''}` : '', cls(w.sum_r)],
    ['Best trade', w.best ? fmtS$(w.best.pnl) : '—', w.best ? `${w.best.day.slice(5)} ${w.best.dir === 1 ? 'long' : 'short'} · ${esc(w.best.exit_reason)}` : '', 'up'],
    ['Worst trade', w.worst ? fmtS$(w.worst.pnl) : '—', w.worst ? `${w.worst.day.slice(5)} ${w.worst.dir === 1 ? 'long' : 'short'} · ${esc(w.worst.exit_reason)}` : '', 'dn'],
    ['Best day', w.best_day != null ? fmtS$(w.best_day) : '—', w.pnl > 0 && w.best_day > 0 ? `${Math.round(w.best_day / w.pnl * 100)}% of week profit` : '', ''],
    ['Worst day', w.worst_day != null ? fmtS$(w.worst_day) : '—', 'vs $1,000 daily stop', w.worst_day <= -800 ? 'dn' : ''],
  ];
  $('#rvKpis').innerHTML = k.map(([a, b, c, d]) => `<div class="kpi"><div class="k">${a}</div><div class="v ${d || ''}">${b}</div><div class="s">${c}</div></div>`).join('');
  // trades
  $('#rvTradesMeta').textContent = `${w.start} → ${w.end}`;
  $('#rvTrades').innerHTML = w.n ? `<div class="table-wrap"><table class="tbl"><tr><th>Day</th><th>Entry</th><th>Side</th><th>Grade</th><th>Trigger</th><th>Target</th><th>Exit</th><th>R</th><th>P&amp;L</th></tr>
    ${w.trades.map(t => `<tr><td class="mono">${t.day.slice(5)}</td><td class="mono">${etStr(t.entry_t)}</td><td><span class="dir ${t.dir === 1 ? 'L' : 'S'}">${t.dir === 1 ? 'LONG' : 'SHORT'}</span></td>
      <td><span class="grade g-${esc((t.grade || '').replace('+', 'p'))}" style="font-size:11px;padding:2px 7px">${esc(t.grade || '—')}</span></td><td>${esc(t.trigger)}</td><td class="small">${esc(t.target_label || '')}</td>
      <td class="small">${esc(t.exit_reason)}</td><td class="mono ${cls(t.pnl_r)}">${fmtR(t.pnl_r)}</td><td class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)}</td></tr>`).join('')}</table></div>`
    : '<div class="empty">No trades this week.</div>';
  // mixes
  const bars = (obj, tone) => { const tot = Object.values(obj).reduce((a, b) => a + b, 0) || 1; return Object.entries(obj).sort((a, b) => b[1] - a[1]).map(([kk, v]) => `<div class="rv-bar"><span>${esc(kk)}</span><div class="t"><i class="${tone(kk)}" style="width:${v / tot * 100}%"></i></div><b>${v}</b></div>`).join('') || '<div class="muted small">—</div>'; };
  const exitTone = (r) => /TARGET|POOL|LOCK/i.test(r) ? 'g' : /STOP|SL/i.test(r) && !/TIME/i.test(r) ? 'b' : /TIME|SIGNAL|BE/i.test(r) ? 'w' : '';
  const gradeTone = (g) => g === 'A+' || g === 'A' ? 'g' : g === 'B' ? '' : g === 'C' ? 'w' : 'b';
  $('#rvMix').innerHTML = `<div class="rv-mix"><div><h4>Exit reasons</h4>${bars(w.exits, exitTone)}</div><div><h4>Grades</h4>${bars(w.grades, gradeTone)}</div></div>
    <div class="rv-best"><div>Longs<b class="${cls(w.trades.filter(t => t.dir === 1).reduce((a, t) => a + t.pnl, 0))}">${fmtS$(w.trades.filter(t => t.dir === 1).reduce((a, t) => a + t.pnl, 0))}</b></div><div>Shorts<b class="${cls(w.trades.filter(t => t.dir === -1).reduce((a, t) => a + t.pnl, 0))}">${fmtS$(w.trades.filter(t => t.dir === -1).reduce((a, t) => a + t.pnl, 0))}</b></div></div>`;
  // takeaways
  const icon = { good: '✔', warn: '!', bad: '✖', '': '›' };
  $('#rvTakeaways').innerHTML = `<ul class="rv-take">${w.takeaways.map(t => `<li class="${t.tone}"><i>${icon[t.tone] || '›'}</i><span>${esc(t.text)}</span></li>`).join('')}</ul>`;
  renderCal(w);
}

function renderCal(w) {
  const [y, m] = month.split('-').map(Number);
  $('#rvMonth').textContent = new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  const byDate = Object.fromEntries(data.days.map(d => [d.date, d]));
  const maxAbs = Math.max(100, ...data.days.map(d => Math.abs(d.pnl || 0)));
  const first = new Date(Date.UTC(y, m - 1, 1)), last = new Date(Date.UTC(y, m, 0));
  let cur = monday(iso(first));
  const sel = new Set(w.days.map(d => d.date));
  let html = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].map(h => `<div class="h">${h}</div>`).join('');
  while (parse(cur) <= last) {
    for (let i = 0; i < 5; i++) {
      const ds = addDays(cur, i), inMonth = ds.slice(0, 7) === month, d = byDate[ds];
      if (!d || !inMonth) { html += `<div class="c off"><span class="n">${inMonth ? +ds.slice(8) : ''}</span></div>`; continue; }
      const p = d.pnl || 0, a = Math.min(1, Math.abs(p) / maxAbs);
      const bg = p === 0 ? 'var(--surface-2)' : `color-mix(in srgb, ${p > 0 ? 'var(--good)' : 'var(--bad)'} ${Math.round(12 + a * 70)}%, var(--surface-2))`;
      html += `<div class="c ${sel.has(ds) ? 'sel' : ''}" data-d="${ds}" style="background:${bg}" title="${ds} · ${fmtS$(p)} · ${d.trades || 0} trades"><span class="n">${+ds.slice(8)}</span>${d.trades ? `<span class="k">${d.trades}t</span>` : ''}<span class="p">${p ? fmtS$(p) : ''}</span></div>`;
    }
    cur = addDays(cur, 7);
  }
  $('#rvCal').innerHTML = `<div class="rv-cal">${html}</div><div class="muted small" style="margin-top:8px">Colour intensity = size of the day's P&L · outlined cells = the selected week · click a day to jump to its week.</div>`;
}

function reviewText() {
  const w = data?.weeks.find(x => x.key === week); if (!w) return '';
  const L = [`📅 ${S.sym} weekly review · ${w.key} (${w.start} → ${w.end})`,
    `P&L ${fmtS$(w.pnl)} · ${w.n} trades · win rate ${w.win_rate != null ? Math.round(w.win_rate) + '%' : '—'} · ${fmtR(w.sum_r)} total (${w.avg_r != null ? fmtR(w.avg_r) : '—'}/trade)`,
    `Best day ${w.best_day != null ? fmtS$(w.best_day) : '—'} · worst day ${w.worst_day != null ? fmtS$(w.worst_day) : '—'}`, ''];
  for (const t of w.trades) L.push(`${t.day} ${etStr(t.entry_t)} ${t.dir === 1 ? 'LONG' : 'SHORT'} ${t.grade || ''} ${t.trigger} → ${t.exit_reason} ${fmtR(t.pnl_r)} ${fmtS$(t.pnl)}`);
  if (w.n) L.push('', `Exits: ${Object.entries(w.exits).map(([k, v]) => `${k} ${v}`).join(', ')}`, `Grades: ${Object.entries(w.grades).map(([k, v]) => `${k} ${v}`).join(', ')}`);
  L.push('', 'Takeaways:', ...w.takeaways.map(t => `• ${t.text}`));
  return L.join('\n');
}

async function load(force = false) {
  if (S.res) { data = fromRes(S.res); render(); return; }
  if (loading && !force) return;
  loading = true; render();
  try { data = await fromServer(); } catch (e) { data = null; toast('Weekly review unavailable: ' + e.message); }
  loading = false; render();
}

export function init() {
  if (!$('#rvStyle')) { const st = document.createElement('style'); st.id = 'rvStyle'; st.textContent = CSS; document.head.appendChild(st); }
  $('#rvWeek').onchange = (e) => { week = e.target.value; month = data?.weeks.find(x => x.key === week)?.start.slice(0, 7) || month; render(); };
  $('#rvCopy').onclick = async () => { const txt = reviewText(); if (!txt) { toast('Nothing to copy yet'); return; } try { await navigator.clipboard.writeText(txt); toast('Weekly review copied'); } catch (e) { toast('Copy blocked by the browser'); } };
  const shift = (n) => { const [y, m] = month.split('-').map(Number); const d = new Date(Date.UTC(y, m - 1 + n, 1)); month = d.toISOString().slice(0, 7); render(); };
  $('#rvMonthPrev').onclick = () => shift(-1);
  $('#rvMonthNext').onclick = () => shift(1);
  $('#rvCal').onclick = (e) => { const c = e.target.closest('.c[data-d]'); if (!c) return; week = isoWeek(c.dataset.d); render(); };
  on(() => { if (S.res) { data = fromRes(S.res); if (S.page === 'review') render(); } });
}
export function show() { load(); }
