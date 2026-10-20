import { $, $$, api, busy, toast, seg, store, fmt$, fmtS$, fmtN, fmtR, cls, esc, etStr, etParts, css } from './util.js';
import { S, effective, emit, on, chartTheme, cj, baseOpts } from './state.js';
import * as chartPage from './page-chart.js';
import * as replayPage from './page-replay.js';
import * as btPage from './page-backtest.js';
import * as propPage from './page-prop.js';
import * as robustPage from './page-robust.js';
import * as livePage from './page-live.js';
import * as journalPage from './page-journal.js';
import * as confPage from './page-conf.js';
import * as newsPage from './page-news.js';
import * as settingsPage from './page-settings.js';
import * as briefingPage from './page-briefing.js';
import * as reportPage from './page-report.js';
import * as regimePage from './page-regime.js';
import * as tvPage from './page-tv.js';
import * as launchPage from './page-launch.js';
import { renderPlaybook } from './page-playbook.js';
import { A, applyAppearance, setAppearance, installSpotlight, countUp } from './skins.js';
import { chime, startSoundWatch } from './sound.js';
import * as reviewPage from './page-review.js';
import * as memoryPage from './page-memory.js';
import { initCommandExtras } from './page-command-extras.js';
import { initPalette } from './palette.js';
import { initVoice } from './voice.js';
import { addPaletteItems } from './palette.js';
import { startLive, L as LIVE } from './dash/live.js';
import { initHome } from './dash/home.js';
import { initAnalytics, showAnalytics } from './dash/analytics.js';
import { initOps, showOps } from './dash/ops.js';
import { initUX, paletteActions } from './dash/ux.js';
// redesigned shell (web_next/js/next): navigation, custom controls, new Trades / Data / Modules pages
import { TITLES as NX_TITLES, groupOf } from './next/routes.js';
import { initShell, onPage } from './next/shell.js';
import { initControls } from './next/controls.js';
import * as tradesPage from './next/trades.js';
import * as hub from './next/datahub.js';
import * as mods from './next/modpages.js';
import { initFX, fxWarp, fxScene } from './next/fx3d.js';
import * as lab from './next/lab.js';
import { strategy as strategyPage } from './next/strategy.js';
import { newshub as newshubPage } from './next/newshub.js';
import { evals as evalsPage, intraday as intradayPage } from './next/evals.js';
import { initToday } from './next/today.js';
import { archive as archivePage } from './next/archive.js';
import { litday, litlevels, litcockpit, initLitToday } from './next/litpages.js';
import * as pc from './next/pcpages.js';
import { botctl as botctlPage, initBotControl } from './next/botctl.js';
import * as hubp from './next/hubpages.js';

const TITLES_CLASSIC = { command: 'Command Center', briefing: 'Pre-market Briefing', chart: 'Chart', replay: 'Replay', backtest: 'Backtest Lab',
  prop: 'Prop Firms', robust: 'Robustness', conf: 'Confluence Lab', news: 'Markets & News', live: 'Live Bot', journal: 'Journal',
  playbook: 'Playbook', settings: 'Settings & Themes', report: 'Daily Reports', regime: 'Market Regimes', tv: 'TradingView', review: 'Weekly Review', memory: 'Trade Memory',
  launch: 'Launch Control', analytics: 'Deep Stats', ops: 'Ops & Data' };
const PAGES = { chart: chartPage, replay: replayPage, backtest: btPage, prop: propPage, robust: robustPage, conf: confPage, news: newsPage,
  live: livePage, journal: journalPage, settings: settingsPage, briefing: briefingPage, report: reportPage, regime: regimePage, tv: tvPage, review: reviewPage,
  memory: memoryPage, launch: launchPage, analytics: { show: showAnalytics }, ops: { show: () => showOps() },
  command: { show: () => requestAnimationFrame(() => window.dispatchEvent(new Event('resize'))) },
  trades: tradesPage, results: hub.results, variants: hub.variants, learned: hub.learned, study: hub.study,
  lab: lab.experiments, writeups: lab.writeups, evals: evalsPage, intraday: intradayPage,
  strategy: strategyPage, newshub: newshubPage, archive: archivePage, litday, litlevels, litcockpit,
  firms: hubp.firms, business: hubp.business, market: hubp.market, learn: hubp.learn, system: hubp.system,
  botctl: botctlPage, accounts: pc.accounts, evalhq: pc.evalhq, edge: pc.edge, pnlcal: pc.pnlcal, mffurules: pc.mffurules,
  rules: mods.rules, cold: mods.cold, risk: mods.risk, alerts: { show: () => settingsPage.show() }, modules: { show: () => {} },
  playbook: { show: () => {} } };
const TITLES = { ...TITLES_CLASSIC, ...NX_TITLES };

// installable home-screen app: register the service worker (no-op where unsupported, e.g. plain http on a LAN IP in some browsers).
// Registered after the boot backtest: while that runs the server answers slowly and the worker fetch can time out.
function registerSW() {
  if (/\bClaude\//.test(navigator.userAgent)) return;   // the Claude desktop app's preview pane cannot host service workers
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => null);
}

// ------------------------------------------------------------------ navigation
export function go(page) {
  if (page === 'data') page = store.get('dataSub', 'results');
  if (!TITLES[page] || !document.getElementById('page-' + page)) page = 'command';
  if (groupOf(page) === 'data') store.set('dataSub', page);
  const prev = S.page;
  S.page = page;
  $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  $$('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + page));
  $('#pageTitle').textContent = TITLES[page];
  store.set('page', page);
  if (prev && prev !== page) fxWarp();
  fxScene(page);
  onPage(page);
  PAGES[page]?.show?.();
  const rb = $('#runBtn');
  if (rb) { rb.textContent = isArchive(page) ? '▶ Run engine backtest' : '⟳ Reload LIT'; rb.title = isArchive(page) ? 'Run the previous strategy (engine) backtest with the Archive settings' : 'Reload the LIT replay and the LIT state'; }
  if ($('#dataRange') && (S.res || S.eng)) $('#dataRange').textContent = rangeText();
  if (isArchive(page) && !S.eng && S.meta) runEngine();
}
$('#nav').onclick = (e) => { const a = e.target.closest('a[data-page]'); if (a) go(a.dataset.page); };
document.addEventListener('click', (e) => { const g = e.target.closest('[data-goto]'); if (g) go(g.dataset.goto); });
window.LE = { go };

// ------------------------------------------------------------------ backtest runner
// LIT is the live strategy: S.res is the LIT replay (/api/next/lit_backtest, research/lab/backtest_live.json + the LIT state)
// for every live page (Today widgets, Chart, Replays, Journal, Reports, Weekly Review). The previous strategy's engine
// backtest (/api/backtest) is S.eng, loaded only when an Archive page opens (state.js ENG()).
S.mode = 'lit';
S.litPeriod = store.get('litPeriod', '2026');
const isArchive = (p) => groupOf(p) === 'archive';
function rangeText() {
  const r = isArchive(S.page) ? S.eng : S.res;
  if (!r) return isArchive(S.page) ? 'Archive · engine backtest loading…' : 'loading…';
  return isArchive(S.page)
    ? `Archive · engine ${r.sym || S.sym} ${r.tf || S.tf} · ${r.range[0]} → ${r.range[1]} · ${r.days.length} sessions`
    : `LIT · NQ 5m${r.trades.some(t => t.trigger_tf === '1m') ? ' + 1m' : ''} · ${r.range[0]} → ${r.range[1]} · ${r.days.length} sessions`;
}
export async function run() {
  if (isArchive(S.page)) return runEngine();
  busy(true);
  $('#runBtn').disabled = true;
  try {
    S.res = await api(`/api/next/lit_backtest?period=${encodeURIComponent(S.litPeriod)}`);
    $('#dataRange').textContent = rangeText();
    emit();
  } catch (e) {
    toast('LIT backtest failed: ' + e.message, 4000);
    console.error(e);
  } finally {
    busy(false);
    $('#runBtn').disabled = false;
  }
}
let engBusy = null;
export async function runEngine() {
  if (engBusy) return engBusy;
  busy(true);
  $('#runBtn').disabled = true;
  engBusy = (async () => {
    try {
      S.eng = await api('/api/backtest', { sym: S.sym, tf: S.tf, params: S.params, plan: S.plan });
      $('#dataRange').textContent = rangeText();
      emit();
    } catch (e) {
      toast('Engine backtest failed: ' + e.message, 4000);
      console.error(e);
    } finally {
      busy(false);
      $('#runBtn').disabled = false;
      engBusy = null;
    }
  })();
  return engBusy;
}
window.LE.run = run;
window.LE.runEngine = runEngine;
$('#runBtn').onclick = run;

$('#refreshData').onclick = async () => {
  await api('/api/data/refresh', {});
  toast('Refreshing data from Yahoo Finance…');
  busy(true);
  const poll = setInterval(async () => {
    const s = await api('/api/data/refresh');
    if (!s.running) { clearInterval(poll); busy(false); S.bars = {}; toast('Data refreshed'); run(); }
  }, 2500);
};

$('#themeBtn').onclick = () => go('settings');
const soundIcon = () => { $('#soundBtn').textContent = A.sound ? '🔔' : '🔇'; $('#soundBtn').title = A.sound ? 'Sound alerts on' : 'Sound alerts off'; };
$('#soundBtn').onclick = () => { setAppearance({ sound: !A.sound }); if (A.sound) chime('test'); };
// any appearance change (skin, accent, candles...) re-themes every chart and redraws the pages
document.addEventListener('le-appearance', () => {
  chartTheme();
  emit();
  chartPage.retheme?.(); replayPage.retheme?.(); livePage.retheme?.();
  soundIcon();
});

// ------------------------------------------------------------------ clock
// the LIT day (ET minutes): session boxes LIT takes its levels from, the 02:00-15:30 entry window, flat at 15:55
const SESS = [[0, 120, 'Asia', 'asia'], [120, 180, 'Frankfurt hour', 'lon'], [180, 240, 'London open', 'lon'], [240, 480, 'Pre-market', 'pre'],
  [480, 540, 'NY 08-09', 'kz'], [540, 570, 'Pre-market', 'pre'], [570, 930, 'NY cash session', 'kz'], [930, 955, 'No new entries', 'close'],
  [955, 960, 'Flat by 15:55', 'close'], [960, 1020, 'Post-close', 'post'], [1020, 1080, 'CME maintenance', 'halt'], [1080, 1200, 'Globex open', 'asia'],
  [1200, 1440, 'Asia 20-00 box', 'asia']];
export function sessionAt(mod, dow) {
  if (dow === 6 || (dow === 5 && mod >= 1020) || (dow === 0 && mod < 1080)) return ['Market closed', 'halt'];
  const s = SESS.find(([a, b]) => mod >= a && mod < b);
  return s ? [s[2], s[3]] : ['', ''];
}
function tick() {
  const now = Date.now() / 1000;
  const p = etParts(now);
  const dow = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay();
  $('#clockEt').textContent = `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}:${String(p.s).padStart(2, '0')}`;
  const [name] = sessionAt(p.h * 60 + p.mi, dow);
  $('#clockSess').textContent = 'ET · ' + name;
  if (S.page === 'command') renderClock();
}
setInterval(tick, 1000);

// ------------------------------------------------------------------ COMMAND CENTER
// tiny inline sparkline (area + line + end dot) drawn to scale in a 100x34 box
function spark(vals, color) {
  if (!vals || vals.length < 2) return '';
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const pts = vals.map((v, i) => [i / (vals.length - 1) * 98 + 1, 31 - (v - lo) / span * 28]);
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  const id = 'sg' + Math.random().toString(36).slice(2, 8);
  const [ex, ey] = pts[pts.length - 1];
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">
    <defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <path d="${line} L99 34 L1 34 Z" fill="url(#${id})"/><path d="${line}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
    <circle cx="${ex}" cy="${ey}" r="2.2" fill="${color}"/></svg>`;
}

export function kpiTiles(el, s, res) {
  const tr = res.trades || [];
  let eq = 0, peak = 0;
  const eqs = [0], dds = [0], wrs = [];
  tr.forEach((t, i) => {
    eq += t.pnl; peak = Math.max(peak, eq); eqs.push(eq); dds.push(eq - peak);
    const w = tr.slice(Math.max(0, i - 9), i + 1); wrs.push(w.filter(x => x.pnl > 0).length / w.length);
  });
  const sparks = { 'Net P&L': spark(eqs, css('--accent')), 'Win rate': spark(wrs, css('--good')), 'Max drawdown': spark(dds, css('--bad')) };
  const tiles = [
    ['Net P&L', fmtS$(s.net), `${s.trades} trades · ${fmt$(s.commissions)} fees`, cls(s.net)],
    ['Win rate', s.win_rate + '%', `${s.longs}L / ${s.shorts}S`],
    ['Profit factor', fmtN(s.profit_factor), `gross ${fmt$(s.gross_profit)} / ${fmt$(s.gross_loss)}`, s.profit_factor >= 1 ? 'up' : 'dn'],
    ['Expectancy', fmtS$(s.expectancy), `${fmtR(s.avg_r)} per trade`, cls(s.expectancy)],
    ['Trades / week', fmtN(s.trades_per_week, 1), `${s.active_days} active of ${s.days} days`],
    ['Max drawdown', fmt$(s.max_dd), `MLL is ${fmt$(res.plan?.mll ?? 2000)}`, Math.abs(s.max_dd) < (res.plan?.mll ?? 2000) * .6 ? '' : 'dn'],
    ['Sharpe (daily)', fmtN(s.sharpe), `Sortino ${fmtN(s.sortino)}`],
    ['Eval pass rate', res.rolling?.pass_rate != null ? res.rolling.pass_rate + '%' : '—', res.rolling ? `${res.rolling.pass}/${res.rolling.completed} starts · ~${res.rolling.avg_days_to_pass ?? '—'}d` : ''],
  ];
  el.innerHTML = tiles.map(([k, v, sub, c]) => `<div class="kpi">${sparks[k] || ''}<div class="k">${k}</div><div class="v ${c || ''}">${v}</div><div class="s">${sub}</div></div>`).join('');
}

function renderCommand(res) {
  if (!res) return;
  const s = res.stats;
  kpiTiles($('#cmdKpis'), s, res);
  countUp($('#cmdKpis'));
  // equity: daily balance vs trailing MLL vs target (all $ balance - one axis)
  const days = res.days;
  cj('cmdEquity', {
    type: 'line',
    data: {
      labels: days.map(d => d.date.slice(5)),
      datasets: [
        { label: 'Balance', data: days.map(d => d.balance), borderColor: css('--accent'), borderWidth: 2.4, pointRadius: 0, tension: 0, fill: 'start',
          backgroundColor: (ctx) => {
            const a = ctx.chart.chartArea; if (!a) return 'transparent';
            const g = ctx.chart.ctx.createLinearGradient(0, a.top, 0, a.bottom);
            g.addColorStop(0, css('--glow')); g.addColorStop(1, 'transparent'); return g;
          } },
        { label: 'Trailing MLL', data: days.map(d => d.mll), borderColor: css('--bad'), borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0, stepped: true },
        { label: 'Eval target', data: days.map(() => res.plan.start + res.plan.target), borderColor: css('--good'), borderDash: [2, 3], borderWidth: 1.2, pointRadius: 0 },
      ],
    },
    options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'end' }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt$(c.parsed.y)}` } } },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } }, y: { grid: { color: css('--grid') }, ticks: { callback: v => '$' + (v / 1000).toFixed(1) + 'k' } } } }),
  });
  $('#cmdEqNote').textContent = `start ${fmt$(res.plan.start)} → ${fmt$(days.at(-1)?.balance)}`;

  // account card
  const ev = res.eval;
  const last = days.at(-1);
  const bal = last.balance, mll = last.mll;
  const cushion = bal - mll;
  const toTarget = res.plan.start + res.plan.target - bal;
  const statusCol = ev.result === 'PASS' ? 'up' : ev.result === 'FAIL' ? 'dn' : '';
  const bestPct = s.best_day_pct;
  $('#cmdAccount').innerHTML = `
    <div class="big-status ${statusCol}">${ev.result === 'PASS' ? '✔ PASSED' : ev.result === 'FAIL' ? '✖ FAILED' : '… IN PROGRESS'}</div>
    <div class="muted small">eval started ${days[0].date} · ${ev.result === 'OPEN' ? 'running' : 'decided'} after ${ev.days} trading days</div>
    <div class="acct-row"><span>Balance (full period)</span><b>${fmt$(bal)}</b></div>
    <div class="acct-row"><span>Trailing max-loss level</span><b>${fmt$(mll)}</b></div>
    <div class="meter"><div style="width:${Math.min(100, cushion / (res.plan.mll + res.plan.target) * 100)}%;background:var(--accent)"></div></div>
    <div class="acct-row"><span>Cushion above MLL</span><b>${fmt$(cushion)}</b></div>
    <div class="acct-row"><span>${toTarget > 0 ? 'To target' : 'Past target by'}</span><b class="${toTarget > 0 ? '' : 'up'}">${fmt$(Math.abs(toTarget))}</b></div>
    <div class="acct-row"><span>Worst day vs $1,000 DLL</span><b class="${s.worst_day < -800 ? 'dn' : ''}">${fmt$(s.worst_day)}</b></div>
    <div class="meter"><div style="width:${Math.min(100, Math.abs(s.worst_day) / 10)}%;background:${s.worst_day < -800 ? 'var(--bad)' : 'var(--warn)'}"></div></div>
    <div class="acct-row"><span>Best day share of profit</span><b class="${bestPct != null && bestPct <= 50 ? 'up' : 'dn'}">${bestPct != null ? bestPct + '%' : '—'}</b></div>
    <div class="muted small" style="margin-top:4px">Builder funded payouts need best day ≤ 50% of the cycle's profit.</div>`;

  const lit = res.model === 'lit';
  const st = lit ? litState(res) : res.state;
  renderState($('#cmdState'), st, res);
  $('#cmdStateTime').textContent = st?.t ? etStr(st.t, true) + ' ET' + (st.source === 'bot' ? ' · PC bot' : st.source === 'bars' ? ' · last bar' : '') : '—';
  renderLadder($('#cmdLadder'), st);
  if (lit) { renderBoxes($('#cmdMtf'), st); renderBand($('#cmdPd'), st, res); litTitles(res); }
  else { renderMtf($('#cmdMtf'), st); renderPd($('#cmdPd'), st); }
  renderClock();
  // feed
  feed($('#cmdFeed'), res.events.slice(-60).reverse());
  // trades
  const tr = res.trades.slice(-9).reverse();
  $('#cmdTrades').innerHTML = tradeMiniTable(tr);
  $$('#cmdTrades tr[data-i]').forEach(r => r.onclick = () => { chartPage.openTrade(+r.dataset.i); go('chart'); });
}

export function tradeMiniTable(trs) {
  if (!trs.length) return '<div class="empty">No trades yet.</div>';
  return `<div class="table-wrap"><table class="tbl"><tr><th>Day</th><th>Side</th><th>Trigger</th><th>Pools swept</th><th>Target</th><th>Exit</th><th>R</th><th>P&L</th></tr>` +
    trs.map(t => `<tr class="click" data-i="${S.res.trades.indexOf(t)}"><td class="mono">${t.day.slice(5)} ${etStr(t.entry_t)}</td><td><span class="dir ${t.dir === 1 ? 'L' : 'S'}">${t.dir === 1 ? 'LONG' : 'SHORT'}</span></td>
      <td>${t.trigger}</td><td class="small">${esc(t.pools.slice(0, 2).map(p => p.split('·').pop()).join(', '))}</td><td class="small">${esc(t.target_label)}</td><td class="small">${t.exit_reason}</td>
      <td class="mono ${cls(t.pnl_r)}">${fmtR(t.pnl_r)}</td><td class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)}</td></tr>`).join('') + '</table></div>';
}

export function feed(el, events, { newSince = null } = {}) {
  if (!events.length) { el.innerHTML = '<div class="empty">Quiet so far…</div>'; return; }
  el.innerHTML = events.map(e => {
    const w = e.type === 'exit' ? (e.pnl > 0 ? 'win' : 'loss') : '';
    const tag = { sweep: 'SWEEP', signal: 'SIGNAL', entry: 'ENTRY', exit: 'EXIT', skip: 'PASS', expire: 'EXPIRE', amt: 'AUCTION', risk: 'RISK', order: 'ORDER', system: 'SYS', error: 'ERR' }[e.type] || e.type.toUpperCase();
    const ts = e.bar_t ?? e.t;
    return `<div class="ev ${e.type} ${w} ${newSince != null && ts > newSince ? 'new' : ''}"><div class="t">${S.res && ts > 1e9 ? etStr(ts, false) : ''}<br>${ts > 1e9 ? (etStr(ts, true).slice(5, 10)) : ''}</div><div><span class="tag">${tag}</span>${esc(e.text)}</div></div>`;
  }).join('');
}

// the LIT state the Today widgets show: the PC bot's live state when it runs LIT, else the replay's (state at the last bar)
function litState(res) {
  const live = LIVE.live?.state;
  return live && live.model === 'lit' ? { ...live, source: 'bot' } : res.state;
}
// card titles of the Today widgets that change meaning under LIT (the HTML carries the previous strategy's titles)
function litTitles(res) {
  const set = (id, t, sub) => { const c = document.getElementById(id)?.closest('.card'); const h = c?.querySelector('.card-h h3'); if (h) h.textContent = t; const m = c?.querySelector('.card-h .muted.small'); if (m && sub != null) m.textContent = sub; };
  set('cmdEquity', 'Equity · LIT replay on a simulated MFFU account', null);
  set('cmdAccount', 'MFFU Builder 50K · evaluation', `LIT replay ${res.period === 'all' ? '2021-26' : '2026'}`);
  set('cmdState', 'LIT state · last bar', null);
  set('cmdLadder', 'LIT levels', 'untaken levels around price');
  set('cmdClock', 'LIT day clock', 'New York time');
  set('cmdMtf', 'Session boxes · today', 'the highs and lows LIT trades');
  set('cmdPd', 'Target band · today', '18:00 open ± one VIX day');
  set('cmdFeed', 'Bot brain · LIT replay', 'newest first');
  const a = document.querySelector('#cmdTrades')?.closest('.card')?.querySelector('a.link[data-goto]');
  if (a) a.dataset.goto = 'trades';
}
const LIT_STEPS = ['LEVELS', 'SWEEP', 'CISD', 'LIMIT', '1m CISD', 'TRADE', 'DONE'];
function litStep(st) {
  const ms = String(st.model_state || ''), su = Object.values(st.setups || {})[0];
  if (st.position) return 5;
  if (/done for today/i.test(ms)) return 6;
  if (su?.tapped_t || /tapped/i.test(ms)) return 4;
  if (su || /limit armed/i.test(ms)) return 3;
  if ((st.lit?.signals_today || []).length) return 2;
  return /closed/i.test(ms) ? -1 : 0;
}
function renderLitState(el, st) {
  const idx = litStep(st), L = st.lit || {}, R = st.lit_rules || {};
  const su = Object.entries(st.setups || {})[0], pos = st.position;
  const band = L.open18 && L.vix_move ? `${fmtN(L.open18 - L.vix_move, 0)} / ${fmtN(L.open18 + L.vix_move, 0)}` : '—';
  const wk = R.weekly_stop;
  el.innerHTML = `
    <div class="machine">${LIT_STEPS.map((s, i) => `<span class="${i === idx ? 'on' : i < idx ? 'done' : ''}">${s}</span>`).join('')}
      ${idx < 0 ? '<span class="on">CLOSED</span>' : ''}</div>
    <div class="state-grid">
      <div class="st"><div class="k">Price</div><div class="v">${st.price != null ? fmtN(st.price) : '—'}</div></div>
      <div class="st"><div class="k">Day P&L</div><div class="v ${cls(st.day_pnl)}">${fmtS$(st.day_pnl || 0)} · ${st.day_trades || 0}t</div></div>
      <div class="st"><div class="k">Trading day</div><div class="v small">${esc(L.today || '—')}</div></div>
      <div class="st"><div class="k">18:00 open</div><div class="v">${L.open18 ? fmtN(L.open18) : '—'}</div></div>
      <div class="st"><div class="k">VIX · one-day move</div><div class="v small">${L.vix ? fmtN(L.vix, 1) : '—'} · ${L.vix_move ? fmtN(L.vix_move, 0) + ' pts' : '—'}</div></div>
      <div class="st"><div class="k">Target band</div><div class="v small">${band}</div></div>
      <div class="st"><div class="k">Monday rule</div><div class="v small">${esc(R.monday?.text ? R.monday.text.replace(/^Monday: /, '') : R.monday?.on ? 'on (Mondays only)' : '—')}</div></div>
      <div class="st"><div class="k">Weekly stop</div><div class="v small ${wk && wk.mult < 1 ? 'dn' : ''}">${wk ? `${wk.stops ?? 0} of ${wk.after ?? 2} stop-outs${wk.mult < 1 ? ' · half size' : ''}` : 'full size'}</div></div>
    </div>
    <div class="note">${pos ? `In ${pos.dir === 1 ? 'LONG' : 'SHORT'} ${pos.qty} MNQ @ ${fmtN(pos.entry)} → target ${fmtN(pos.target)} / stop ${fmtN(pos.stop)}${pos.be ? ' (breakeven)' : ''}`
      : su ? `${su[0].toUpperCase()} limit ${fmtN(su[1].limit)} · stop ${fmtN(su[1].stop)} · target ${fmtN(su[1].target)} (swept ${esc((su[1].pools || []).join(', '))})`
      : esc(String(st.model_state || 'No setup armed.').replace(/^LIT: /, ''))}</div>`;
}
export function renderState(el, st, res) {
  if (!st) { el.innerHTML = '<div class="empty">No state</div>'; return; }
  if (st.model === 'lit') { renderLitState(el, st); return; }
  const steps = ['WAITING FOR SWEEP', 'ARMED - HUNTING IFVG', 'ORDER PENDING', 'IN TRADE', 'DONE FOR DAY'];
  const idx = steps.indexOf(st.model_state);
  const tr = (v) => v === 1 ? '<span class="up">▲ Bullish</span>' : v === -1 ? '<span class="dn">▼ Bearish</span>' : '<span class="muted">— Neutral</span>';
  const pf = st.profile;
  const armed = [st.setups?.long && `LONG after sweep of ${st.setups.long.pools.join(', ')} (ext ${fmtN(st.setups.long.ext)})`,
    st.setups?.short && `SHORT after sweep of ${st.setups.short.pools.join(', ')} (ext ${fmtN(st.setups.short.ext)})`].filter(Boolean);
  el.innerHTML = `
    <div class="machine">${['SWEEP', 'IFVG', 'ORDER', 'TRADE', 'DONE'].map((s, i) => `<span class="${i === idx ? 'on' : i < idx ? 'done' : ''}">${s}</span>`).join('')}
      ${idx < 0 ? `<span class="on">${st.model_state}</span>` : ''}</div>
    <div class="state-grid">
      <div class="st"><div class="k">Price</div><div class="v">${fmtN(st.price)}</div></div>
      <div class="st"><div class="k">Day P&L</div><div class="v ${cls(st.day_pnl)}">${fmtS$(st.day_pnl)} · ${st.day_trades}t</div></div>
      <div class="st"><div class="k">1H structure</div><div class="v">${tr(st.h1_trend)}</div></div>
      <div class="st"><div class="k">15m structure</div><div class="v">${tr(st.m15_trend)}</div></div>
      <div class="st"><div class="k">1H protected low</div><div class="v">${st.h1_protected_low ? fmtN(st.h1_protected_low) : '—'}</div></div>
      <div class="st"><div class="k">1H protected high</div><div class="v">${st.h1_protected_high ? fmtN(st.h1_protected_high) : '—'}</div></div>
      <div class="st"><div class="k">Open vs value</div><div class="v">${st.open_loc ? st.open_loc.toUpperCase() : '—'}</div></div>
      <div class="st"><div class="k">pPOC / VA</div><div class="v small">${pf ? `${fmtN(pf.poc, 0)} · ${fmtN(pf.val, 0)}–${fmtN(pf.vah, 0)}` : '—'}</div></div>
    </div>
    <div class="note">${armed.length ? '🎯 Armed: ' + armed.map(esc).join(' · ') : st.position ? `In ${st.position.dir === 1 ? 'LONG' : 'SHORT'} ${esc(st.position.qty_label)} @ ${fmtN(st.position.entry)} → TP ${fmtN(st.position.target)} / SL ${fmtN(st.position.stop)}` : 'No setup armed.'}</div>`;
}

// LIT: today's session boxes (state.session: label -> [high, low]) with the distance from price
function renderBoxes(el, st) {
  if (!el) return;
  const ss = Object.entries(st?.session || {}), px = st?.price;
  if (!ss.length) { el.innerHTML = '<div class="empty">No session box closed yet today.</div>'; return; }
  const d = (v) => px != null ? `<span class="${v > px ? 'up' : 'dn'}">${v > px ? '+' : ''}${fmtN(v - px, 1)}</span>` : '';
  el.innerHTML = `<div class="table-wrap"><table class="tbl"><tr><th>Box</th><th>High</th><th>Low</th><th>Range</th></tr>` +
    ss.map(([k, [hi, lo]]) => `<tr><td><b>${esc(k)}</b></td><td class="mono">${fmtN(hi)} <span class="small">${d(hi)}</span></td><td class="mono">${fmtN(lo)} <span class="small">${d(lo)}</span></td><td class="mono small">${fmtN(hi - lo, 1)}</td></tr>`).join('') +
    `</table></div><div class="muted small" style="margin-top:6px">LIT takes its levels from these boxes plus the previous day, week and month highs and lows, the opening gaps and equal highs / lows. A trade needs one swept by at least half an ATR, an inducement swing taken first, a displacement candle and a 5-minute CISD close.</div>`;
}
// LIT: the target band (18:00 open +/- one VIX day) and today's rules (Monday rule, weekly stop)
function renderBand(el, st, res) {
  if (!el) return;
  const L = st?.lit || {}, R = st?.lit_rules || {}, px = st?.price;
  if (!L.open18 || !L.vix_move) { el.innerHTML = '<div class="empty">No VIX move for today yet.</div>'; return; }
  const lo = L.open18 - L.vix_move, hi = L.open18 + L.vix_move;
  const pos = px != null ? Math.max(-0.08, Math.min(1.08, (px - lo) / (hi - lo))) : null;
  const pct = (v) => ((v + 0.1) / 1.2 * 100).toFixed(1) + '%';
  const s26 = res?.periods?.['2026 H2 (check)'];
  el.innerHTML = `<div class="big-status" style="font-size:20px">${fmtN(lo, 0)} → ${fmtN(hi, 0)} <span class="muted" style="font-size:14px">± ${fmtN(L.vix_move, 0)} pts</span></div>
    <div style="position:relative;height:40px;margin:14px 0 6px;overflow:hidden">
      <div style="position:absolute;left:${pct(0)};width:calc(${pct(1)} - ${pct(0)});top:14px;height:14px;background:color-mix(in srgb,var(--accent) 22%,transparent);border-radius:6px"></div>
      <div style="position:absolute;left:${pct(0.5)};top:8px;height:26px;width:2px;background:var(--gold)" title="18:00 open"></div>
      ${pos != null ? `<div style="position:absolute;left:calc(${pct(pos)} - 7px);top:14px;width:14px;height:14px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--surface)"></div>` : ''}
    </div>
    <div class="acct-row"><span>18:00 open (gold)</span><b>${fmtN(L.open18)}</b></div>
    <div class="acct-row"><span>VIX ${L.vix ? fmtN(L.vix, 1) : '—'} → one-day move</span><b>${fmtN(L.vix_move, 1)} pts</b></div>
    <div class="acct-row"><span>Monday rule</span><b class="small">${esc(R.monday?.text || (R.monday?.on ? 'on' : 'off'))}</b></div>
    <div class="acct-row"><span>Weekly stop</span><b class="small">${esc(R.weekly_stop?.text || 'after 2 stop-outs in a week: half size')}</b></div>
    <div class="muted small" style="margin-top:8px">LIT targets the far side of this band (at least 1.5R, banked at 8R), breakeven at 1R, flat at 15:55 ET.${s26 ? ` 2026 H2 check: PF ${fmtN(s26.pf ?? s26.profit_factor, 2)}, ${fmtS$(s26.net)}.` : ''}</div>`;
}

export function renderMtf(el, st) {
  const m = st?.mtf;
  if (!el || !m || !m.tfs?.length) { if (el) el.innerHTML = '<div class="empty">No multi-timeframe data.</div>'; return; }
  const arrow = (v) => v === 1 ? '<span class="up">▲ bull</span>' : v === -1 ? '<span class="dn">▼ bear</span>' : '<span class="muted">— flat</span>';
  const net = m.net;
  const verdict = net >= 2 ? '<span class="up">Bullish alignment</span>' : net <= -2 ? '<span class="dn">Bearish alignment</span>' : '<span class="muted">Mixed / rotational</span>';
  el.innerHTML = `<div class="table-wrap"><table class="tbl"><tr><th>TF</th><th>FVG order flow</th><th>Last reaction</th><th>Nearest gap</th></tr>` +
    m.tfs.map(r => `<tr><td class="mono"><b>${r.tf}</b></td><td>${arrow(r.bias)}</td><td class="small">${esc(r.last || '—')}</td>
      <td class="small mono">${r.zones.slice(0, 1).map(z => `<span class="${z.dir === 1 ? 'up' : 'dn'}" title="${z.state}">${z.state === 'inverted' ? 'i' : ''}${fmtN(z.bot, 0)}–${fmtN(z.top, 0)}</span>`).join('') || '—'}</td></tr>`).join('') +
    `<tr><td class="mono"><b>STRUCT</b></td><td colspan="3">1H ${arrow(m.structure['1H'])} &nbsp; 15m ${arrow(m.structure['15m'])}</td></tr></table></div>
    <div class="acct-row"><span>Net alignment (−4 … +4)</span><b>${net > 0 ? '+' : ''}${net} · ${verdict}</b></div>
    <div class="muted small" style="margin-top:6px">Respected FVG = order flow continues; closed-through FVG (inverted) = order flow flipped. The model fades sweeps, so it reads alignment as context rather than requiring it.</div>`;
}

export function renderPd(el, st) {
  const m = st?.mtf, dr = m?.dealing_range;
  if (!el) return;
  if (!dr) { el.innerHTML = '<div class="empty">No 1H dealing range yet.</div>'; return; }
  const pos = Math.max(-0.08, Math.min(1.08, dr.pos));
  const pct = (v) => ((v + 0.1) / 1.2 * 100).toFixed(1) + '%';
  const mo = m.midnight_open;
  const moPos = mo != null ? (mo - dr.low) / (dr.high - dr.low) : null;
  const zone = dr.pos > 1 ? 'ABOVE RANGE' : dr.pos < 0 ? 'BELOW RANGE' : dr.pos >= 0.5 ? 'PREMIUM' : 'DISCOUNT';
  el.innerHTML = `<div class="big-status ${dr.pos >= 0.5 ? 'dn' : 'up'}" style="font-size:22px">${zone} <span class="muted" style="font-size:15px">${Math.round(dr.pos * 100)}% of range</span></div>
    <div style="position:relative;height:44px;margin:16px 0 8px;overflow:hidden">
      <div style="position:absolute;left:${pct(0)};width:calc(${pct(0.5)} - ${pct(0)});top:14px;height:16px;background:color-mix(in srgb,var(--good) 30%,transparent);border-radius:6px 0 0 6px"></div>
      <div style="position:absolute;left:${pct(0.5)};width:calc(${pct(1)} - ${pct(0.5)});top:14px;height:16px;background:color-mix(in srgb,var(--bad) 30%,transparent);border-radius:0 6px 6px 0"></div>
      <div style="position:absolute;left:${pct(0.5)};top:8px;height:28px;width:2px;background:var(--ink-2)"></div>
      ${moPos != null && moPos > -0.1 && moPos < 1.1 ? `<div title="midnight open" style="position:absolute;left:${pct(moPos)};top:6px;height:32px;width:2px;background:var(--gold)"></div>` : ''}
      <div style="position:absolute;left:calc(${pct(pos)} - 7px);top:15px;width:14px;height:14px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--surface)"></div>
    </div>
    <div class="row" style="justify-content:space-between" class="mono small"><span class="mono small">${fmtN(dr.low)}</span><span class="mono small muted">EQ ${fmtN(dr.eq)}</span><span class="mono small">${fmtN(dr.high)}</span></div>
    <div class="acct-row"><span>Midnight (true day) open</span><b>${mo != null ? fmtN(mo) : '—'} ${mo != null ? (st.price > mo ? '<span class="dn">price above</span>' : '<span class="up">price below</span>') : ''}</b></div>
    <div class="muted small" style="margin-top:8px">Longs are scored up when the sweep lands in discount (below EQ), shorts in premium. This location edge held on both sides of the split, in both NQ and ES. <span style="color:var(--gold)">▌</span> midnight open</div>`;
}

export function renderLadder(el, st) {
  if (!st) return;
  const price = st.price;
  const pools = (st.active_pools || []).filter(p => Math.abs(p.price - price) / price < 0.03);
  const above = pools.filter(p => p.price > price).sort((a, b) => a.price - b.price).slice(0, 6);
  const below = pools.filter(p => p.price < price).sort((a, b) => b.price - a.price).slice(0, 6);
  const list = [...above.reverse(), null, ...below];
  const W = 440, rowH = 22, H = list.length * rowH + 8;
  const maxD = Math.max(1, ...pools.map(p => Math.abs(p.price - price)));
  let y = 4, out = '';
  for (const p of list) {
    if (!p) {
      out += `<rect x="0" y="${y + 2}" width="${W}" height="${rowH - 4}" rx="5" fill="var(--accent)" opacity=".16"/>
        <text x="8" y="${y + 15}" font-size="12" font-weight="700" fill="var(--ink)">PRICE ${fmtN(price)}</text>`;
    } else {
      const d = p.price - price;
      const col = p.side === 'H' ? 'var(--bsl)' : 'var(--ssl)';
      const len = Math.max(4, Math.abs(d) / maxD * 100);
      out += `<rect x="${W - 105}" y="${y + 7}" width="${len}" height="8" rx="3" fill="${col}" opacity="${p.strength >= 2 ? .85 : .45}"/>
        <text x="8" y="${y + 15}" font-size="11.5" fill="${col}" font-weight="${p.strength >= 2 ? 700 : 500}">${p.side === 'H' ? 'BSL' : 'SSL'} ${esc(p.label.replace('·', ' '))}</text>
        <text x="${W - 190}" y="${y + 15}" font-size="11.5" text-anchor="end" fill="var(--ink-2)">${fmtN(p.price)}</text>
        <text x="${W - 112}" y="${y + 15}" font-size="11" text-anchor="end" fill="var(--muted)">${d > 0 ? '+' : ''}${fmtN(d, 1)}</text>`;
    }
    y += rowH;
  }
  el.innerHTML = `<div class="ladder"><svg viewBox="0 0 ${W} ${H}" width="100%">${out}</svg></div>
    <div class="muted small">${st.model === 'lit' ? 'LIT levels not traded through yet. BSL above = buy stops, SSL below = sell stops. The VIX band rows are the target, not a level to sweep.' : 'Draw on liquidity sits at the nearest quality pool. BSL above = buy stops, SSL below = sell stops.'}</div>`;
}

function renderClock() {
  const el = $('#cmdClock');
  if (!el) return;
  const now = Date.now() / 1000, p = etParts(now), mod = p.h * 60 + p.mi + p.s / 60;
  const R = 78, cx = 100, cy = 100;
  const ang = (m) => (m / 1440) * Math.PI * 2 - Math.PI / 2;
  const arc = (a, b, r, w, col, op = 1) => {
    const x0 = cx + r * Math.cos(ang(a)), y0 = cy + r * Math.sin(ang(a)), x1 = cx + r * Math.cos(ang(b)), y1 = cy + r * Math.sin(ang(b));
    return `<path d="M${x0} ${y0} A${r} ${r} 0 ${b - a > 720 ? 1 : 0} 1 ${x1} ${y1}" stroke="${col}" stroke-width="${w}" fill="none" opacity="${op}" stroke-linecap="butt"/>`;
  };
  // LIT day: the session boxes (inner ring) and the 02:00-15:30 entry window (outer gold arc)
  const segs = [[1200, 1440, 'var(--amt)', 'Asia'], [120, 180, 'var(--ssl)', 'Frankfurt'], [180, 240, 'var(--ssl)', 'London'], [240, 570, 'var(--ink-2)', 'Pre-market'],
    [480, 540, 'var(--bsl)', 'NY 08-09'], [570, 960, 'var(--ink-2)', 'NY cash'], [1020, 1080, 'var(--bad)', 'Halt']];
  const win = [[120, 930]];
  let svg = `<circle cx="${cx}" cy="${cy}" r="${R}" stroke="var(--surface-3)" stroke-width="14" fill="none"/>`;
  for (const [a, b, c] of segs) svg += arc(a, b, R, 14, c, .55);
  for (const [a, b] of win) svg += arc(a, b, R + 13, 5, 'var(--gold)', .95);
  svg += arc(955, 960, R + 13, 5, 'var(--bad)', 1);
  for (let hh = 0; hh < 24; hh += 3) {
    const a = ang(hh * 60), x = cx + (R - 20) * Math.cos(a), y = cy + (R - 20) * Math.sin(a);
    svg += `<text x="${x}" y="${y + 3}" text-anchor="middle" font-size="8.5" fill="var(--muted)" font-family="JetBrains Mono">${hh}</text>`;
  }
  const a = ang(mod);
  svg += `<line x1="${cx}" y1="${cy}" x2="${cx + (R + 6) * Math.cos(a)}" y2="${cy + (R + 6) * Math.sin(a)}" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round"/><circle cx="${cx}" cy="${cy}" r="4" fill="var(--accent)"/>`;
  const dow = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay();
  const [name] = sessionAt(Math.floor(mod), dow);
  const closed = name === 'Market closed';
  const inWin = !closed && mod >= 120 && mod < 930;
  const mins = mod < 120 ? 120 - mod : 1440 - mod + 120;
  el.innerHTML = `<div style="display:flex;align-items:center;gap:14px">
    <svg viewBox="0 0 200 200" width="190" height="190">${svg}</svg>
    <div><div class="mini-label">Now</div><div style="font-weight:700;font-size:15px">${name}</div>
      <div class="mini-label" style="margin-top:10px">${inWin ? 'Entry window' : 'Entry window opens'}</div>
      <div class="mono" style="font-size:20px;font-weight:700">${inWin ? 'OPEN' : closed ? 'Sun 18:00' : `${Math.floor(mins / 60)}h ${String(Math.floor(mins % 60)).padStart(2, '0')}m`}</div>
      <div class="muted small">${inWin ? `closes 15:30 ET · ${Math.floor((930 - mod) / 60)}h ${String(Math.floor((930 - mod) % 60)).padStart(2, '0')}m left` : 'LIT enters 02:00-15:30 ET'}</div>
      <div class="small" style="margin-top:10px;line-height:1.7"><span style="color:var(--gold)">■</span> entry window&nbsp; <span style="color:var(--amt)">■</span> Asia&nbsp; <span style="color:var(--ssl)">■</span> Frankfurt / London<br><span style="color:var(--bsl)">■</span> NY 08-09&nbsp; <span style="color:var(--ink-2)">■</span> NY&nbsp; <span style="color:var(--bad)">■</span> flat 15:55 · halt</div></div></div>`;
}

// ------------------------------------------------------------------ boot
async function boot() {
  initShell();
  initControls();
  initFX();
  applyAppearance();
  installSpotlight();
  startSoundWatch();
  soundIcon();
  chartTheme();
  try {
    S.meta = await api('/api/meta');
  } catch (e) {
    toast('Server not reachable — start it with: python server.py', 8000);
    return;
  }
  // futures only: CME symbols with 5m data; CFD proxies (NQX / ESX, any *X) are never offered
  const isCfd = (s) => /^(NQX|ESX)$/i.test(s) || /X$/i.test(s);
  const syms = Object.keys(S.meta.available).filter(s => S.meta.available[s].includes('5m') && !isCfd(s));
  if (!syms.length) syms.push('NQ');
  if (!syms.includes(S.sym)) { S.sym = syms.includes('NQ') ? 'NQ' : syms[0]; store.set('sym', S.sym); }
  seg($('#symSeg'), syms.map(s => [s, s]), S.sym, (v) => { if (isCfd(v)) return; S.sym = v; store.set('sym', v); run(); });
  on(renderCommand);
  for (const p of Object.values(PAGES)) p.init?.();
  initCommandExtras(); initPalette(); initVoice();
  // dashboard layer: ops registers the command 'prep' widget, so it runs before the command grid is built
  initOps(); initHome(); initAnalytics(); initUX(go); addPaletteItems(paletteActions); startLive(); initToday(); initLitToday(); pc.initPCStatus(); initBotControl();
  renderPlaybook($('#playbook'));
  const want = new URLSearchParams(location.search).get('page');
  go(want && TITLES[want] ? want : store.get('page', 'command'));
  await run();
  setTimeout(registerSW, 3000);
}
boot();
