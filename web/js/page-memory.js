// Memory: the bot's persistent trade memory (data/memory.db). Lifetime paper vs live results, what the exit learner has
// learned from real trades, grade calibration (backtest vs realised, report only) and a trade log with notes.
import { $, $$, api, esc, fmtN, fmtS$, fmtR, cls, etStr, toast } from './util.js';
import { S, on, effective } from './state.js';

const CSS = `
.mem-note{width:100%;min-width:170px}
.mem-note-row{display:flex;gap:6px;align-items:center}
.mem-src{font:600 10px var(--mono);letter-spacing:.06em;text-transform:uppercase}
.mem-src.live{color:var(--bad)}.mem-src.paper{color:var(--accent)}.mem-src.backtest{color:var(--muted)}
.mem-sub{font-size:11.5px;color:var(--ink-2);margin:-2px 0 8px}
.mem-flag{font-size:12px;line-height:1.4;white-space:normal;min-width:180px}
.mem-learn td{vertical-align:top}
.mem-learn .muted.small{white-space:normal}
`;

// same wording as Engine.EXIT_SIGNALS (engine/model.py)
const XLABEL = {
  opp_disp: 'Displacement candle against the trade (body >= 1 ATR)',
  trig_break: "Close back through the trigger candle's extreme",
  giveback: 'Was +0.5R, now closing below entry',
  stall: 'No new high-water mark for 30 min while under +1R',
  zone_reentry: 'Close back inside the inverted FVG',
  zone_fail: 'Close through the far side of the inverted FVG',
  opp_fvg: 'Opposing FVG forms against the trade',
  m15_flip: '15m structure flips against the trade',
  two_against: 'Two consecutive momentum closes against',
  vol_against: 'Volume climax (2x) on a candle against',
};
const GRADES = ['A+', 'A', 'B', 'C', 'D'];
const FAR_BELOW_R = 0.5;     // realised avg R this far under the backtest's = flagged for the owner
const MIN_JUDGE = 5;         // fewer realised trades than this in a grade = too early to judge

let stats = null, trades = [], source = 'realised', loading = false;

export function init() {
  if (!$('#memStyle')) { const st = document.createElement('style'); st.id = 'memStyle'; st.textContent = CSS; document.head.appendChild(st); }
  on(() => { if (S.page === 'memory') renderCalib(); });
  $('#memSrc').onchange = (e) => { source = e.target.value; loadTrades(); };
  $('#memRefresh').onclick = () => load();
  $('#memTrades').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-save]');
    if (b) saveNote(+b.dataset.save);
  });
  $('#memTrades').addEventListener('keydown', (e) => {
    const inp = e.target.closest('input.mem-note');
    if (inp && e.key === 'Enter') { e.preventDefault(); saveNote(+inp.dataset.id); }
  });
}
export function show() { load(); }

async function load() {
  if (loading) return;
  loading = true;
  try {
    const p = effective();
    const q = new URLSearchParams({ learn_min: p.exit_learn_min ?? 20, threshold: p.exit_learn_threshold ?? 0.2, sym: S.sym || '' });
    stats = await api('/api/memory/stats?' + q.toString());
    renderKpis(); renderLearned(); renderCalib();
    await loadTrades();
  } catch (e) {
    $('#memKpis').innerHTML = `<div class="card"><div class="empty">Memory unavailable: ${esc(e.message)}</div></div>`;
  } finally {
    loading = false;
  }
}

async function loadTrades() {
  try {
    const r = await api(`/api/memory/trades?source=${encodeURIComponent(source)}&limit=300`);
    trades = r.trades || [];
  } catch (e) {
    trades = [];
    toast('Could not load the trade memory: ' + e.message, 3500);
  }
  renderTrades();
}

// ------------------------------------------------------------------ lifetime KPIs (paper and live kept apart)
const pf = (v) => v == null ? '—' : v >= 999 ? '∞' : fmtN(v);
function kpiBlock(title, s, tone) {
  if (!s || !s.trades) {
    return `<div class="card"><div class="card-h"><h3>${title}</h3><span class="pill">0 trades</span></div>
      <div class="empty">${tone === 'live' ? 'No live trades remembered yet. They appear here after the first completed real-money trade.' : 'No paper trades remembered yet. Completed routed paper trades are stored automatically.'}</div></div>`;
  }
  const k = [['Trades', String(s.trades), ''], ['Win rate', s.win_rate + '%', ''], ['Avg R', fmtR(s.avg_r), cls(s.avg_r)],
    ['Profit factor', pf(s.profit_factor), s.profit_factor >= 1 ? 'up' : 'dn'], ['Net', fmtS$(s.net), cls(s.net)]];
  return `<div class="card"><div class="card-h"><h3>${title}</h3><span class="pill ${tone === 'live' ? 'bad' : ''}">${s.first_day || ''} → ${s.last_day || ''}</span></div>
    <div class="grid kpis small" style="margin-bottom:0">${k.map(([a, b, c]) => `<div class="kpi"><div class="k">${a}</div><div class="v ${c}">${esc(b)}</div></div>`).join('')}</div>
    <div class="note">Total ${fmtR(s.total_r)} · avg win ${fmtS$(s.avg_win)} · avg loss ${fmtS$(s.avg_loss)} · expectancy ${fmtS$(s.expectancy)} per trade</div></div>`;
}
function renderKpis() {
  const c = stats.counts || {};
  $('#memMeta').textContent = `${stats.db} · ${c.paper || 0} paper · ${c.live || 0} live${c.backtest ? ` · ${c.backtest} backtest (not used for learning)` : ''}`;
  $('#memKpis').innerHTML = kpiBlock('Paper · lifetime', stats.paper, 'paper') + kpiBlock('Live · lifetime', stats.live, 'live');
}

// ------------------------------------------------------------------ what the bot has learned (exit-signal learner)
function renderLearned() {
  const L = stats.learner;
  const p = effective();
  const rules = new Set(String(p.exit_rules || '').split(',').map(s => s.trim()).filter(Boolean));
  const by = Object.fromEntries((L.signals || []).map(x => [x.key, x]));
  const seedOn = p.memory_seed !== false;
  const seedN = Object.values(L.seedable || {}).reduce((a, b) => a + b, 0);
  const rows = Object.keys(XLABEL).map(key => {
    const x = by[key];
    let st;
    if (rules.has(key)) st = '<span class="pill ok">RULE · always acts</span>';
    else if (!p.exit_learn) st = '<span class="pill">learner off</span>';
    else if (!x) st = '<span class="pill">no cases yet</span>';
    else if (x.learned) st = '<span class="pill ok">LEARNED · acts now</span>';
    else if (x.n >= L.learn_min) st = '<span class="pill bad">rejected · leaving did not pay</span>';
    else st = `<span class="pill">learning · ${x.to_go} to go</span>`;
    return `<tr><td><b>${esc(key)}</b><div class="muted small">${esc(XLABEL[key])}</div></td><td>${st}</td>
      <td class="mono">${x ? x.n : 0}</td><td class="mono ${x ? cls(x.avg_gain) : ''}">${x ? fmtR(x.avg_gain) : '—'}</td>
      <td class="mono">${x ? Math.round(x.helped * 100) + '%' : '—'}</td><td class="mono">${x ? Math.round(x.hurt * 100) + '%' : '—'}</td>
      <td class="mono ${x ? cls(x.total_gain) : ''}">${x ? fmtR(x.total_gain) : '—'}</td></tr>`;
  }).join('');
  $('#memLearnState').textContent = seedOn ? `seeding on · ${seedN} cases` : 'seeding off';
  $('#memLearned').innerHTML = `<div class="table-wrap"><table class="tbl mem-learn"><tr><th>Signal</th><th>Status</th><th>Cases</th><th>Avg gain if left</th><th>Helped</th><th>Hurt</th><th>Total</th></tr>${rows}</table></div>
    <div class="note">Cases come from completed <b>paper + live</b> trades only (never backtests). A signal is acted on once it has
      <b>${L.learn_min}</b>+ cases averaging at least <b>${fmtR(L.threshold)}</b> from leaving (Exit-signal settings in the Backtest Lab).
      ${seedOn ? `Seeding is <b>on</b>: every run starts the learner from the remembered cases for this symbol that closed before the run's first bar.
      Trades inside the run's own window are re-learned from the bars, so nothing is counted twice and a backtest never sees its own future.`
      : 'Seeding is <b>off</b> (memory_seed = false): every run starts the learner from zero.'}
      Fixed rules (${[...rules].map(esc).join(', ') || 'none'}) always act, so they log no counterfactual.</div>`;
}

// ------------------------------------------------------------------ grade calibration (report only, never changes sizing)
function renderCalib() {
  const box = $('#memCalib');
  if (!box || !stats) return;
  const real = stats.calibration?.realised || {};
  const bt = {};
  for (const t of S.res?.trades || []) {
    const g = t.grade || '—';
    (bt[g] = bt[g] || []).push(t.pnl_r);
  }
  const mean = (a) => a && a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
  const rows = GRADES.map(g => {
    const b = mean(bt[g]), r = real[g];
    const rn = r?.trades || 0, ra = rn ? r.avg_r : null;
    let flag;
    if (b == null && !rn) flag = '<span class="muted">no trades at this grade</span>';
    else if (!rn) flag = '<span class="muted">no realised trades yet</span>';
    else if (b == null) flag = '<span class="muted">run a backtest to compare</span>';
    else if (rn < MIN_JUDGE) flag = `<span class="muted">only ${rn} realised trade${rn === 1 ? '' : 's'}: too early to judge</span>`;
    else if (ra <= b - FAR_BELOW_R) flag = `<span class="dn">Realised is ${fmtN(b - ra)}R per trade below the backtest${ra < 0 ? ' and losing money' : ''}. Worth reviewing this grade's size.</span>`;
    else if (ra >= b + FAR_BELOW_R) flag = '<span class="up">Doing better than the backtest.</span>';
    else flag = 'In line with the backtest.';
    return `<tr><td><span class="grade g-${g.replace('+', 'p')}" style="font-size:11px;padding:2px 7px">${g}</span></td>
      <td class="mono">${bt[g]?.length || 0}</td><td class="mono ${cls(b)}">${b == null ? '—' : fmtR(b)}</td>
      <td class="mono">${rn}</td><td class="mono ${cls(ra)}">${ra == null ? '—' : fmtR(ra)}</td><td class="mono">${rn ? r.win_rate + '%' : '—'}</td>
      <td class="mono ${b != null && ra != null ? cls(ra - b) : ''}">${b != null && ra != null ? fmtR(ra - b) : '—'}</td><td class="mem-flag">${flag}</td></tr>`;
  }).join('');
  box.innerHTML = `<div class="table-wrap"><table class="tbl"><tr><th>Grade</th><th>Backtest n</th><th>Backtest avg R</th><th>Realised n</th><th>Realised avg R</th><th>Win</th><th>Gap</th><th>Read</th></tr>${rows}</table></div>
    <div class="note">Backtest column = the current run in this dashboard (${S.res ? `${esc(S.sym)} ${esc(S.res.range?.[0] || '')} → ${esc(S.res.range?.[1] || '')}` : 'no backtest loaded yet'}).
      Realised = paper + live trades in memory. A grade is flagged when it has ${MIN_JUDGE}+ realised trades and averages ${FAR_BELOW_R}R or more below the backtest.
      <b>Sizing is never changed automatically.</b> Grade multipliers stay as set; you decide.</div>`;
}

// ------------------------------------------------------------------ trade log with notes
function renderTrades() {
  const box = $('#memTrades');
  if (!trades.length) {
    box.innerHTML = `<div class="empty">No remembered trades for this filter yet. Completed routed paper / live trades are stored automatically;
      today's paper ledger can be backfilled with <span class="mono">python -m engine.memory --import-live-state</span>.</div>`;
    return;
  }
  const sig = (t) => {
    const xs = Object.entries(t.xsig || {}).sort((a, b) => (a[1].k ?? 0) - (b[1].k ?? 0));
    if (!xs.length) return '<span class="muted small">none</span>';
    return xs.map(([n, x]) => `<span class="pill ${t.exit_signal === n ? 'bad' : ''}" title="bar +${x.k ?? '?'} · ${x.r != null ? fmtR(x.r) : '?'} at the time${x.gain != null ? ` · leaving would have made ${fmtR(x.gain)} more` : ''}">${t.exit_signal === n ? '✕ ' : ''}${esc(n)}</span>`).join(' ');
  };
  box.innerHTML = `<div class="table-wrap" style="max-height:620px"><table class="tbl"><tr><th>Day</th><th>Entry</th><th>Source</th><th>Side</th><th>Grade</th><th>Trigger</th><th>Exit</th><th>Warning signs</th><th>R</th><th>P&amp;L</th><th>Note</th></tr>
    ${trades.map(t => `<tr><td class="mono">${esc(t.day || '')}</td><td class="mono">${t.entry_t ? etStr(t.entry_t) : ''}</td>
      <td><span class="mem-src ${esc(t.source)}">${esc(t.source)}</span> <span class="muted small">${esc(t.sym)}</span></td>
      <td><span class="dir ${t.dir === 1 ? 'L' : 'S'}">${t.dir === 1 ? 'LONG' : 'SHORT'}</span></td>
      <td>${t.grade ? `<span class="grade g-${esc(t.grade).replace('+', 'p')}" style="font-size:11px;padding:2px 7px">${esc(t.grade)}</span>` : '<span class="muted">—</span>'}</td>
      <td>${esc(t.trigger || '—')}</td><td class="small" title="${esc(t.memory_note || '')}">${esc(t.exit_reason || '—')}${t.memory_note ? ' *' : ''}</td><td class="small">${sig(t)}</td>
      <td class="mono ${cls(t.pnl_r)}">${fmtR(t.pnl_r)}</td><td class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)}</td>
      <td><div class="mem-note-row"><input class="inp sm mem-note" data-id="${t.id}" value="${esc(t.note || '')}" placeholder="add a note…" maxlength="2000">
        <button class="btn ghost sm" data-save="${t.id}">Save</button></div></td></tr>`).join('')}</table></div>`;
}

async function saveNote(id) {
  const inp = $$('#memTrades input.mem-note').find(x => +x.dataset.id === id);
  if (!inp) return;
  try {
    const r = await api('/api/memory/note', { trade_id: id, text: inp.value });
    const t = trades.find(x => x.id === id);
    if (t) t.note = r.text;
    toast(r.text ? 'Note saved to memory' : 'Note cleared');
  } catch (e) {
    toast('Note not saved: ' + e.message, 3500);
  }
}
