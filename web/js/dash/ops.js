// Ops & Data page: system health, latency, data coverage (CME futures only), news + blackout timeline, paper-vs-backtest drift,
// background jobs and a searchable bot log. Plus the "next session prep" card on the Command Center.
import { $, $$, esc, fmt$, fmtS$, fmtN, fmtR, cls, css, etStr } from '../util.js';
import { S, on } from '../state.js';
import { L, onLive } from './live.js';
import { widget, body, meta, buildGrid, openLayout } from './widgets.js';
import { waiting, stat, spark, getJSON, dash, pref, dur, ago, etToTs, etNow, tradingDate, killzone, LAUNCH_TS } from './kit.js';

const isCfd = (s) => /^(NQX|ESX)$/i.test(s) || /X$/i.test(s);
const FUT = new Set(['NQ', 'ES', 'MNQ', 'MES', 'YM', 'RTY']);
const tile = (k, v, s, lvl = '') => `<div class="hl-tile ${lvl}"><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
const srcPill = (api) => `<span class="src-pill ${api ? 'live' : 'fallback'}">${api ? 'dash api' : 'fallback'}</span>`;

// ------------------------------------------------------------------ system health
let healthApi = null;
const pollHist = [];
function renderHealth() {
  const el = body('health'); if (!el) return;
  const s = L.live, wd = L.wd, h = s?.health || {}, hp = healthApi;
  if (!s && !wd) { el.innerHTML = waiting('Waiting for the server'); return; }
  meta('health', srcPill(!!hp));
  const age = h.data_age_s != null ? h.data_age_s + (L.liveAt ? Date.now() / 1000 - L.liveAt : 0) : null;
  const open = h.market_open;
  const t = [];
  t.push(tile('Server', L.online ? 'online' : 'offline', wd ? `up ${dur(wd.uptime_s, { short: true })}` : '', L.online ? 'ok' : 'bad'));
  t.push(tile('Paper bot', s?.running ? 'running' : 'stopped', `adapter ${s?.cfg?.adapter || '—'} · ${s?.cfg?.armed ? 'ARMED' : 'not armed'}`, s?.running ? 'ok' : 'bad'));
  t.push(tile('Bot poll', h.poll_ms != null ? fmtN(h.poll_ms, 0) + ' ms' : '—', s?.last_poll ? `last ${ago(Date.now() / 1000 - s.last_poll)}` : '', h.poll_ms > 8000 ? 'warn' : 'ok'));
  t.push(tile('Data age', age != null ? dur(age, { short: true }) : '—', `${h.data_source || ''}${h.fallback ? ' · fallback' : ''}${open === false ? ' · market closed' : ''}`, !open ? '' : h.stale ? 'bad' : age > 1200 ? 'warn' : 'ok'));
  t.push(tile('Errors', `${h.consecutive_errors ?? 0} / ${s?.errors ?? 0}`, h.last_error ? esc(String(h.last_error).slice(0, 60)) : 'consecutive / total', h.consecutive_errors ? 'bad' : 'ok'));
  t.push(tile('Feed hygiene', `${h.revisions ?? 0} rev`, h.dropped ? `dup ${h.dropped.duplicate ?? 0} · bad ${(h.dropped.malformed ?? 0) + (h.dropped.misaligned ?? 0)}` : '', h.desync ? 'bad' : 'ok'));
  t.push(tile('Entries', h.entries_blocked ? 'BLOCKED' : 'allowed', h.desync ? 'feed desync' : 'risk guard', h.entries_blocked ? 'warn' : 'ok'));
  if (wd) {
    t.push(tile('Watchdog', wd.ok ? 'OK' : 'ISSUE', (wd.issues || [])[0] || (wd.thread_alive ? 'thread alive' : 'thread dead'), wd.ok && wd.thread_alive ? 'ok' : 'bad'));
    t.push(tile('Keep-awake', wd.keepawake?.held ? 'held' : 'off', wd.keepawake?.since ? 'since ' + etStr(wd.keepawake.since) : (wd.keepawake?.last_error || ''), wd.keepawake?.held ? 'ok' : 'warn'));
    t.push(tile('Auto-resume', wd.autostart_record ? 'armed' : 'none', wd.autostart?.reason ? esc(wd.autostart.reason.slice(0, 48)) : '', wd.autostart_record ? 'ok' : 'warn'));
  }
  if (hp?.system) {
    const sy = hp.system, pr = hp.process || {};
    t.push(tile('CPU', fmtN(sy.cpu_pct, 0) + '%', `${sy.cpu_count} cores · server ${fmtN(pr.cpu_pct, 0)}%`, sy.cpu_pct > 85 ? 'warn' : 'ok'));
    t.push(tile('Memory', fmtN(sy.mem_pct, 0) + '%', `${fmtN(sy.mem_used_gb, 1)} / ${fmtN(sy.mem_total_gb, 0)} GB · rss ${fmtN(pr.rss_mb, 0)} MB`, sy.mem_pct > 90 ? 'warn' : 'ok'));
    t.push(tile('Disk', fmtN(sy.disk_pct, 0) + '%', `${fmtN(sy.disk_free_gb, 0)} GB free`, sy.disk_pct > 92 ? 'warn' : 'ok'));
    if (hp.supervisor) t.push(tile('Supervisor', hp.supervisor.alive ? 'alive' : 'down', `pid ${hp.supervisor.pid}`, hp.supervisor.alive ? 'ok' : 'bad'));
  }
  el.innerHTML = `<div class="hl-grid">${t.join('')}</div>${hp?.system ? '' : '<div class="muted small" style="margin-top:8px">CPU / RAM / disk tiles appear when /api/dash/health is live.</div>'}`;
}

function renderLatency() {
  const el = body('latency'); if (!el) return;
  const ms = L.lat.map(x => x.ms).filter(v => v != null);
  if (L.live?.health?.poll_ms != null) { const last = pollHist.at(-1); if (!last || last.t !== L.live.last_poll) pollHist.push({ t: L.live.last_poll, ms: L.live.health.poll_ms }); if (pollHist.length > 90) pollHist.shift(); }
  if (!ms.length) { el.innerHTML = waiting('Measuring…'); return; }
  const p = (q) => { const s = [...ms].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(s.length * q))]; };
  el.innerHTML = `<div class="kst-row">${stat('Dashboard API', fmtN(ms.at(-1), 0) + ' ms', `p50 ${fmtN(p(.5), 0)} · p95 ${fmtN(p(.95), 0)}`)}${stat('Bot poll', pollHist.length ? fmtN(pollHist.at(-1).ms, 0) + ' ms' : '—', 'fetch + model step')}${stat('Misses', L.lat.filter(x => x.ms == null).length, `of ${L.lat.length} polls`)}</div>
    <div class="lat-wrap"><div class="mini-label">/api/live/state round-trip · last ${ms.length} polls</div>${spark(ms, { w: 400, h: 40, color: css('--accent') })}</div>
    ${pollHist.length > 1 ? `<div class="lat-wrap"><div class="mini-label">Bot poll duration (ms)</div>${spark(pollHist.map(x => x.ms), { w: 400, h: 40, color: css('--gold') })}</div>` : ''}`;
}

// ------------------------------------------------------------------ data coverage (futures only)
async function renderCoverage() {
  const el = body('coverage'); if (!el) return;
  const api = await dash('/api/dash/coverage', { ttl: 300000 });
  const tv = api ? null : await getJSON('/api/tv/status', { ttl: 300000 });
  meta('coverage', srcPill(!!api));
  const avail = S.meta?.available || {};
  const syms = Object.keys(avail).filter(s => !isCfd(s) && s !== 'tv');
  const tfs = ['1m', '5m', '15m', '1h', '1d'];
  let files = [];
  if (api?.files) files = api.files.filter(f => !isCfd(f.sym));
  else if (tv?.data) files = Object.entries(tv.data).filter(([s]) => !isCfd(s)).map(([sym, d]) => ({ sym, tf: '5m', rows: d.bars, from: d.from, to: d.to, sessions: d.days, imported: d.imported_days }));
  const t0 = new Date('2021-10-01T00:00:00Z').getTime(), t1 = Date.now();
  const X = (d) => Math.max(0, Math.min(100, (new Date(d + 'T00:00:00Z').getTime() - t0) / (t1 - t0) * 100));
  el.innerHTML = `<div class="tfm" style="grid-template-columns:64px repeat(${tfs.length},minmax(0,1fr))"><div></div>${tfs.map(t => `<div class="ax" style="text-align:center">${t}</div>`).join('')}
      ${syms.map(s => `<div class="ax"><b>${s}</b>${FUT.has(s) ? '' : '<br><span style="font-size:9px">context</span>'}</div>${tfs.map(t => `<div class="c ${avail[s]?.includes(t) ? 'yes' : 'no'}">${avail[s]?.includes(t) ? '●' : '·'}</div>`).join('')}`).join('')}</div>
    <div class="mini-label" style="margin-top:12px">Intraday history · 2021-10 → today</div>
    ${files.length ? files.map(f => `<div class="cov-row"><b class="mono">${esc(f.sym)} ${esc(f.tf || '')}</b><div class="tr"><i style="left:${X(f.from)}%;width:${Math.max(.8, X(f.to) - X(f.from))}%"></i></div>
      <span class="mono small">${fmtN(f.sessions, 0)} sess · ${f.rows >= 1e6 ? (f.rows / 1e6).toFixed(2) + 'M' : fmtN(f.rows / 1000, 0) + 'k'} bars${f.missing_weekdays != null ? ` · ${f.missing_weekdays} gaps` : ''}</span></div>`).join('') : waiting('No coverage info')}
    <div class="muted small" style="margin-top:6px">Real CME futures only (back-adjusted NQ1! / ES history + live Yahoo NQ=F). VIX / VXN / GEX are daily context series, not traded. ${api?.manifest_generated ? 'Manifest ' + esc(api.manifest_generated) : ''}</div>`;
}

// ------------------------------------------------------------------ news + blackout timeline
let newsApi = null, newsFb = null, newsBusy = false, newsAt = 0;
async function loadNews() {
  if (newsBusy) return;
  newsBusy = true; newsAt = Date.now();
  try {
    newsApi = await dash('/api/dash/news?days=10&impact=medium', { ttl: 300000 });
    if (!newsApi && !newsFb) newsFb = await getJSON('/api/news', { ttl: 600000, body: { params: S.params || {} } });
  } finally { newsBusy = false; }
  renderNews();
}
function renderNews() {
  const el = body('newsline'); if (!el) return;
  const p = S.meta?.defaults || {};
  const before = (p.news_before_min ?? 15) * 60, after = (p.news_after_min ?? 30) * 60;
  let evs = [];
  if (newsApi?.events) evs = newsApi.events.map(e => ({ t: e.t, ev: e.event, imp: e.impact, bs: e.blackout_start, be: e.blackout_end }));
  else if (newsFb) {
    const seen = new Set();
    for (const e of [...(newsFb.upcoming || []), ...(newsFb.calendar || [])]) {
      if (e.currency && e.currency !== 'USD') continue;
      if (!['high', 'medium'].includes(e.impact)) continue;
      const k = e.t + e.event; if (seen.has(k)) continue; seen.add(k);
      evs.push({ t: e.t, ev: e.event, imp: e.impact, bs: e.impact === 'high' ? e.t - before : null, be: e.impact === 'high' ? e.t + after : null });
    }
  }
  // Pine blackout list (what the live TradingView strategy will actually use)
  for (const s of (L.bo?.entries || [])) {
    const m = s.match(/(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d)/); if (!m) continue;
    const t = etToTs(+m[1], +m[2], +m[3], +m[4], +m[5]);
    const hit = evs.find(e => Math.abs(e.t - t) < 120);
    if (hit) { hit.bs = t - before; hit.be = t + after; hit.pine = true; } else evs.push({ t, ev: 'Pine blackout entry', imp: 'high', bs: t - before, be: t + after, pine: true });
  }
  if (!newsApi && !newsFb && !L.bo) { el.innerHTML = waiting('Loading the economic calendar'); return; }
  meta('newsline', srcPill(!!newsApi));
  const now = Date.now() / 1000, n0 = etNow(now);
  // weekdays from today for 10 calendar days
  const days = [];
  for (let k = 0; k < 14 && days.length < 8; k++) {
    const d = new Date(Date.UTC(n0.p.y, n0.p.mo - 1, n0.p.d + k)); const w = d.getUTCDay(); if (w === 0 || w === 6) continue;
    days.push({ y: d.getUTCFullYear(), mo: d.getUTCMonth() + 1, d: d.getUTCDate(), w, key: d.toISOString().slice(0, 10) });
  }
  const A0 = 7 * 60, A1 = 17 * 60, span = A1 - A0;   // 07:00 → 17:00 ET window
  const pct = (mins) => ((mins - A0) / span * 100).toFixed(2);
  const rows = days.map(d => {
    const s0 = etToTs(d.y, d.mo, d.d, 7, 0), s1 = etToTs(d.y, d.mo, d.d, 17, 0);
    const ins = evs.filter(e => e.t >= s0 && e.t <= s1);
    const pre = evs.filter(e => e.t >= s0 - 11 * 3600 && e.t < s0 && e.imp === 'high');
    const mins = (t) => (t - s0) / 60 + A0;
    const kz = [[570, 690], [810, 930]].map(([a, b]) => `<div class="kz" style="left:${pct(a)}%;width:${pct(b) - pct(a)}%"></div>`).join('');
    const bo = ins.filter(e => e.bs).map(e => `<div class="bo" style="left:${pct(Math.max(A0, mins(e.bs)))}%;width:${Math.max(.5, pct(Math.min(A1, mins(e.be))) - pct(Math.max(A0, mins(e.bs))))}%" title="blackout ${etStr(e.bs)}–${etStr(e.be)} ET${e.pine ? ' · in the Pine list' : ''}"></div>`).join('');
    const ev = ins.map(e => `<span class="ev ${e.imp}" style="left:${pct(mins(e.t))}%" title="${etStr(e.t)} ET · ${esc(e.ev)} (${e.imp})${e.pine ? ' · Pine blackout' : ''}"></span>`).join('');
    const nowM = now >= s0 && now <= s1 ? `<div class="now" style="left:${pct(mins(now))}%"></div>` : '';
    const hi = ins.filter(e => e.imp === 'high').length;
    return `<div class="nt-day"><b>${['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.w]} ${d.key.slice(5)}<small>${hi ? hi + ' high' : ins.length ? ins.length + ' medium' : 'quiet'}${pre.length ? ' · overnight' : ''}</small></b><div class="nt-track">${kz}${bo}${ev}${nowM}</div></div>`;
  }).join('');
  const nextBo = evs.filter(e => e.be && e.be > now).sort((a, b) => a.bs - b.bs)[0];
  el.innerHTML = `${nextBo ? `<div class="acct-row" style="margin:0 0 8px"><span>Next blackout · ${esc(nextBo.ev)}</span><b>${etStr(nextBo.t, true).slice(5)} ET · ${now >= nextBo.bs ? '<span class="dn">ACTIVE</span>' : 'in ' + dur(nextBo.bs - now, { short: true })}</b></div>` : ''}
    <div class="nt">${rows}<div class="nt-axis"><span></span><div>${[8, 9.5, 11.5, 13.5, 15.5].map(h => `<span style="left:${pct(h * 60)}%">${String(Math.floor(h)).padStart(2, '0')}:${h % 1 ? '30' : '00'}</span>`).join('')}</div></div></div>
    <div class="tl-legend" style="margin-top:8px"><span><i style="background:color-mix(in srgb,var(--gold) 30%,transparent)"></i>killzones</span><span><i style="background:var(--bad)"></i>high</span><span><i style="background:var(--warn)"></i>medium</span><span><i style="background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--bad) 45%,transparent) 0 4px,transparent 4px 8px)"></i>blackout −${before / 60}/+${after / 60} min</span></div>`;
}

// ------------------------------------------------------------------ paper vs backtest drift
async function renderDrift() {
  const el = body('drift'); if (!el) return;
  const api = await dash('/api/dash/drift', { ttl: 60000, keep: true });
  if (api?.status === 'no_data') { meta('drift', srcPill(true)); el.innerHTML = waiting('No paper trades yet', esc(api.message || 'Drift appears after the first completed paper trade.')); return; }
  if (api?.status === 'ok') {
    meta('drift', srcPill(true));
    const s = api.summary;
    el.innerHTML = `<div class="kst-row">${stat('Matched', `${s.matched}/${Math.max(s.paper_trades, s.backtest_trades)}`, `${fmtN(s.match_rate, 0)}% match`, s.match_rate >= 80 ? 'up' : 'dn')}${stat('Paper only', s.paper_only, 'not in backtest')}${stat('Backtest only', s.backtest_only, 'missed live')}${stat('P&L gap', fmtS$(s.pnl_diff), 'paper − backtest', cls(s.pnl_diff))}${stat('Entry slip', fmtN(s.avg_entry_slip_min, 1) + ' min', 'avg')}</div>
      <div class="drift-row h" style="margin-top:10px"><span>Day</span><span>Paper</span><span>Backtest</span><span class="m">ΔR</span></div>
      ${api.pairs.slice(-12).reverse().map(p => `<div class="drift-row"><span class="mono">${esc(p.day)}</span><span class="mono">${p.paper ? `${p.paper.dir === 1 ? 'L' : 'S'} ${fmtR(p.paper.r)}` : '<span class="muted">—</span>'}</span><span class="mono">${p.backtest ? `${p.backtest.dir === 1 ? 'L' : 'S'} ${fmtR(p.backtest.r)}` : '<span class="muted">—</span>'}</span><span class="m ${cls(p.r_diff)}">${p.r_diff != null ? fmtR(p.r_diff) : esc(p.match)}</span></div>`).join('')}`;
    return;
  }
  // fallback: realised paper stats from the trade memory vs the loaded backtest
  const mem = await getJSON('/api/memory/stats', { ttl: 60000 });
  meta('drift', srcPill(false));
  const pp = mem?.paper, bt = S.res?.stats;
  if (!pp || !pp.trades) { el.innerHTML = waiting('No paper trades yet', 'Drift compares each completed paper trade with the backtest of the same day. It appears after the first paper trade (launch Sun 18:00 ET).'); return; }
  const rs = (S.res?.trades || []).map(t => t.pnl_r), m = rs.reduce((a, b) => a + b, 0) / rs.length;
  const sd = Math.sqrt(rs.reduce((a, b) => a + (b - m) ** 2, 0) / rs.length);
  const z = sd ? (pp.avg_r - m) / (sd / Math.sqrt(pp.trades)) : 0;
  const row = (k, a, b, f) => `<div class="drift-row"><span>${k}</span><span class="mono">${f(a)}</span><span class="mono">${f(b)}</span><span class="m ${cls(a - b)}">${a != null && b != null ? (a - b > 0 ? '+' : '') + fmtN(a - b, 2) : '—'}</span></div>`;
  el.innerHTML = `<div class="kst-row">${stat('Paper trades', pp.trades)}${stat('Drift z-score', fmtN(z, 2), Math.abs(z) < 2 ? 'within noise' : 'significant', Math.abs(z) < 2 ? 'up' : 'dn')}</div>
    <div class="drift-row h" style="margin-top:10px"><span>Metric</span><span>Paper</span><span>Backtest</span><span class="m">Δ</span></div>
    ${row('Avg R', pp.avg_r, bt?.avg_r, fmtR)}${row('Win rate %', pp.win_rate, bt?.win_rate, (v) => fmtN(v, 1))}${row('Profit factor', pp.profit_factor, bt?.profit_factor, (v) => fmtN(v, 2))}${row('Expectancy $', pp.expectancy, bt?.expectancy, (v) => fmtS$(v))}`;
}

// ------------------------------------------------------------------ jobs
async function renderJobs() {
  const el = body('jobs'); if (!el) return;
  const [jobs, conf, refresh] = await Promise.all([dash('/api/dash/jobs', { ttl: 0 }), getJSON('/api/confluence/status', { ttl: 0 }), getJSON('/api/data/refresh', { ttl: 0 })]);
  const rows = [];
  for (const j of (jobs?.jobs || [])) rows.push([j.key, j.state, j.state === 'running' ? `${j.step ?? '?'}/${j.steps ?? '?'} ${j.msg || ''}` : j.secs != null ? `${fmtN(j.secs, 1)} s` : (j.error || '')]);
  if (conf) rows.push(['confluence learning cycle', conf.running ? 'running' : conf.rc === 0 ? 'done' : conf.started ? 'idle' : 'never run', conf.running ? `${conf.step}/${conf.steps} ${conf.msg || ''}` : conf.elapsed_s ? `${conf.elapsed_s}s · ${conf.msg || ''}` : '']);
  if (refresh) rows.push(['data refresh (Yahoo NQ=F)', refresh.running ? 'running' : 'idle', refresh.last ? `last ${esc(String(refresh.last))}` : '']);
  meta('jobs', srcPill(!!jobs));
  el.innerHTML = rows.length ? rows.map(([k, s2, d]) => `<div class="rdy ${s2 === 'running' ? 'warn' : s2 === 'done' ? 'pass' : s2 === 'error' || s2 === 'failed' ? 'fail' : 'info'}"><span class="ic">${s2 === 'running' ? '⟳' : s2 === 'done' ? '✔' : '·'}</span><span>${esc(k)}</span><span class="dt" title="${esc(d)}">${esc(s2)} ${esc(d)}</span></div>`).join('') : waiting('No background jobs');
}

// ------------------------------------------------------------------ searchable bot log
let logQ = '';
function renderLog() {
  const el = body('rawlog'); if (!el) return;
  if (!el.querySelector('#rlQ')) {
    el.innerHTML = `<input class="inp sm" id="rlQ" placeholder="filter text or type (e.g. sweep, exit, 10:3)" style="width:100%;margin-bottom:8px"><div class="lfeed" id="rlList" style="max-height:420px"></div>`;
    $('#rlQ', el).oninput = (e) => { logQ = e.target.value.toLowerCase(); renderLog(); };
  }
  const rows = (L.log || []).filter(r => !logQ || `${r.type} ${r.text} ${etStr(r.t)}`.toLowerCase().includes(logQ));
  meta('rawlog', `<span class="mono small">${rows.length}/${(L.log || []).length}</span>`);
  $('#rlList', el).innerHTML = rows.slice(0, 300).map(r => `<div class="ev ${r.type}"><div class="t">${etStr(r.t)}<br>${etStr(r.t, true).slice(5, 10)}</div><div><span class="tag">${esc(String(r.type).toUpperCase())}</span>${esc(r.text)}</div></div>`).join('') || '<div class="empty">Nothing matches.</div>';
}

// ------------------------------------------------------------------ next session prep (Command Center card)
async function renderPrep() {
  const el = body('prep'); if (!el) return;
  const api = await dash('/api/dash/prep', { ttl: 120000 });
  meta('prep', srcPill(!!api));
  if (api) {
    el.innerHTML = `<div class="rdy-head"><div><div class="mini-label">${esc(api.weekday)} ${esc(api.date)}</div><div class="ck-v sm">${esc(api.risk)} RISK</div><div class="muted small">${esc(api.action)}</div></div></div>
      <div class="kst-row" style="margin-top:8px">${stat('Regime', esc(api.regime || '—'), `ER10 ${fmtN(api.er10, 2)}`)}${stat('ADR20', fmtN(api.adr20, 0), 'points')}${stat('Flat by', esc(api.flat_et || '15:55'), 'ET')}</div>
      ${api.events?.length ? `<div class="mini-label" style="margin-top:8px">Events</div>${api.events.map(e => `<div class="acct-row"><span>${esc(e.time_et || '')} ${esc(e.event || '')}</span><b>${esc(e.impact || '')}</b></div>`).join('')}` : ''}
      ${api.levels?.length ? `<div class="mini-label" style="margin-top:8px">Levels</div><div class="kst-row">${api.levels.slice(0, 6).map(l => stat(esc(l.label), fmtN(l.price, 2))).join('')}</div>` : ''}
      ${api.notes ? `<div class="note">${esc(api.notes)}</div>` : ''}
      ${api.checklist?.length ? `<ul class="check small">${api.checklist.map(c => `<li>${esc(c)}</li>`).join('')}</ul>` : ''}`;
    return;
  }
  // fallback: next trading day, its killzones, blackout entries that day, regime from the backtest, nearest pools
  const date = tradingDate();
  const [y, mo, d] = date.split('-').map(Number);
  const wd = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(Date.UTC(y, mo - 1, d)).getUTCDay()];
  const bos = (L.bo?.entries || []).filter(e => e.startsWith(date));
  const last = S.res?.days?.at(-1);
  const st = L.live?.state, price = st?.price;
  const pools = (st?.active_pools || []).filter(p => price != null);
  const up = pools.filter(p => p.price > price).sort((a, b) => a.price - b.price).slice(0, 2), dn = pools.filter(p => p.price < price).sort((a, b) => b.price - a.price).slice(0, 2);
  const risk = bos.length ? 'HIGH' : 'NORMAL';
  el.innerHTML = `<div class="rdy-head"><div><div class="mini-label">Next session · ${wd} ${date}</div><div class="ck-v sm ${bos.length ? 'dn' : 'up'}">${risk}</div><div class="muted small">${bos.length ? `${bos.length} Pine blackout${bos.length > 1 ? 's' : ''}: ${bos.map(b => b.slice(11)).join(', ')} ET` : 'no high-impact USD release in the Pine list'}</div></div></div>
    <div class="kst-row" style="margin-top:8px">${stat('Killzones', '09:30 · 13:30', 'ET · flat 15:55')}${stat('Regime', esc(last?.regime || '—'), last?.er10 != null ? `ER10 ${fmtN(last.er10, 2)}` : '')}${stat('Launch', Date.now() / 1000 < LAUNCH_TS ? 'Sun 18:00' : 'live', 'ET · alerts on')}</div>
    ${up.length || dn.length ? `<div class="mini-label" style="margin-top:8px">Draws on liquidity</div>${up.reverse().map(p => `<div class="acct-row"><span style="color:var(--bsl)">BSL ${esc(p.label)}</span><b>${fmtN(p.price, 2)} · +${fmtN(p.price - price, 1)}</b></div>`).join('')}${dn.map(p => `<div class="acct-row"><span style="color:var(--ssl)">SSL ${esc(p.label)}</span><b>${fmtN(p.price, 2)} · −${fmtN(price - p.price, 1)}</b></div>`).join('')}` : ''}
    <ul class="check small" style="margin-bottom:0"><li>Paper bot running, adapter=paper</li><li>TradingView alert active on MNQ1!</li><li>Max 2 trades, stop after a winner, $600 bot daily stop</li></ul>`;
}

// ------------------------------------------------------------------ init
export function initOps() {
  const page = $('#page-ops'); if (!page) return;
  page.innerHTML = `<div class="page-tools"><span class="lbl">Ops &amp; data</span><span class="spacer"></span><button class="btn ghost sm" id="opsRefresh">⟳ Refresh</button><button class="btn ghost sm" id="opsLayout">⚙ Layout</button></div><div id="opsGrid"></div>`;
  widget({ id: 'health', page: 'ops', title: 'System health', size: 'w' });
  widget({ id: 'latency', page: 'ops', title: 'Latency', size: 'm', csv: () => ({ name: 'latency', rows: L.lat }) });
  widget({ id: 'newsline', page: 'ops', title: 'News &amp; blackout timeline · ET', size: 'xl' });
  widget({ id: 'coverage', page: 'ops', title: 'Data coverage · CME futures', size: 'l' });
  widget({ id: 'drift', page: 'ops', title: 'Paper vs backtest drift', size: 'l' });
  widget({ id: 'rawlog', page: 'ops', title: 'Bot log · search', size: 'l', csv: () => ({ name: 'bot_log_full', rows: (L.log || []).map(r => ({ t: r.t, et: etStr(r.t, true), type: r.type, text: r.text })) }) });
  widget({ id: 'jobs', page: 'ops', title: 'Background jobs', size: 'l' });
  buildGrid('ops', $('#opsGrid'));
  $('#opsLayout').onclick = () => openLayout('ops');
  $('#opsRefresh').onclick = () => showOps(true);
  // next session prep lives on the Command Center
  widget({ id: 'prep', page: 'command', title: 'Next session prep', size: 'm' });
  onLive(() => { renderHealth(); renderLatency(); if (S.page === 'ops') renderLog(); renderNews(); });
  on(() => renderPrep());
  setInterval(() => { if (!document.hidden && S.page === 'command') renderPrep(); }, 60000);
}
export async function showOps(force) {
  const hp = await dash('/api/dash/health', { ttl: force ? 0 : 15000 });
  healthApi = hp;
  renderHealth(); renderLatency(); renderLog(); renderCoverage(); loadNews(); renderDrift(); renderJobs();
}
export { renderPrep };
