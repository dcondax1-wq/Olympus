import { $, esc, fmtN, seg, store, api, css, etStr } from './util.js';
import { S, cj, baseOpts, on } from './state.js';

let N = null, timer = null, tick = null;
let ccy = store.get('calCcy', 'USD'), imp = store.get('calImp', 'high+'), hlMode = store.get('hlMode', 'all');

export function init() {
  seg($('#calCcy'), [['USD', 'USD'], ['all', 'All']], ccy, (v) => { ccy = v; store.set('calCcy', v); renderCal(); });
  seg($('#calImp'), [['high', 'High'], ['high+', 'High+Med'], ['all', 'All']], imp, (v) => { imp = v; store.set('calImp', v); renderCal(); });
  seg($('#hlFilter'), [['all', 'All'], ['hot', 'Market-moving']], hlMode, (v) => { hlMode = v; store.set('hlMode', v); renderHl(); });
  on(() => renderTicker());
  refresh();
  setInterval(refresh, 120000);          // keeps the top-bar chip current on every page
  setTimeout(loadGamma, 3000);           // gamma levels feed the chart overlay too
  setInterval(loadGamma, 900000);
  setInterval(renderChip, 1000);
}
export function show() { refresh(); }

async function refresh() {
  try { N = await api('/api/news', { params: S.params }); } catch (e) { return; }
  renderChip();
  renderTicker();
  if (S.page === 'news') renderAll();
}

// ---- live ticker tape under the top bar (market + guard + gamma + market-moving headlines)
export function renderTicker() {
  const el = $('#tickerTrack');
  if (!el) return;
  const parts = [];
  const item = (tag, val, cls = '') => parts.push(`<span class="ti ${cls}"><span class="tag">${esc(tag)}</span><b>${val}</b></span>`);
  const st = S.res?.state;
  if (st) item(S.sym + ' LAST', fmtN(st.price), '');
  const v = N?.volatility || {};
  for (const k of ['VIX', 'VXN']) if (v[k]) item(k, `${fmtN(v[k].last)} <span class="${v[k].chg_1d > 0 ? 'dn' : 'up'}">${v[k].chg_1d > 0 ? '▲' : '▼'}${fmtN(Math.abs(v[k].chg_1d))}</span>`);
  if (v.regime) item('VOL REGIME', esc(v.regime.toUpperCase()));
  if (N?.guard) item('GUARD', N.guard.allowed ? '<span class="up">CLEAR</span>' : `<span class="dn">${esc(N.guard.reasons[0])}</span>`);
  const nx = N?.guard?.next_high;
  if (nx) item('NEXT RED', `${esc(nx.event)} · ${esc(nx.time_et)}`);
  const gm = window.LE_GAMMA?.live;
  if (gm && !gm.error) item('GAMMA', `${gm.net_gex_bn > 0 ? '<span class="up">POS</span>' : '<span class="dn">NEG</span>'} · call ${fmtN(gm.call_wall.nq, 0)} · put ${fmtN(gm.put_wall.nq, 0)} · flip ${fmtN(gm.flip.nq, 0)}`);
  if (N?.nq_range?.ratio != null) item('NQ RANGE', `${fmtN(N.nq_range.ratio, 2)}× ADR`);
  if (st) item('MODEL', esc(st.model_state));
  for (const h of (N?.headlines || []).filter(x => x.hot).slice(0, 8)) parts.push(`<span class="ti hot">${esc(h.source)}: <b>${esc(h.title)}</b></span>`);
  if (!parts.length) return;
  const one = parts.join('<span class="sep"></span>');
  el.innerHTML = one + '<span class="sep"></span>' + one + '<span class="sep"></span>';   // doubled for a seamless loop
}

const cd = (s) => {
  if (s <= 0) return 'now';
  const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), ss = Math.floor(s % 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m ${String(ss).padStart(2, '0')}s`;
};

function renderChip() {
  const el = $('#newsChip');
  if (!el || !N) return;
  const g = N.guard, now = Date.now() / 1000, nx = g.next_high;
  el.className = 'pill news-chip ' + (g.allowed ? 'ok' : 'block');
  el.textContent = g.allowed ? (nx ? `● clear · ${shortName(nx.event)} in ${cd(nx.t - now)}` : '● clear to trade') : `⚠ ${g.reasons[0]}`;
  if (S.page === 'news') renderGuard();
}
const shortName = (s) => s.replace(/\s*(m\/m|y\/y|q\/q)$/i, '').slice(0, 34);

function renderAll() { renderGuard(); renderVol(); renderRange(); renderEarn(); renderCal(); renderHl(); loadGamma(); loadMarkets(); }

async function loadMarkets() {
  let m;
  try { m = await api('/api/markets'); } catch (e) { return; }
  const spark = (v, up) => {
    if (!v || v.length < 2) return '';
    const lo = Math.min(...v), hi = Math.max(...v), sp = hi - lo || 1;
    const pts = v.map((x, i) => `${(i / (v.length - 1) * 100).toFixed(1)},${(24 - (x - lo) / sp * 22).toFixed(1)}`).join(' ');
    return `<svg class="sp" viewBox="0 0 100 26" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${up ? css('--good') : css('--bad')}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
  };
  const corr = (c) => c == null ? '—' : `<span style="color:${c >= 0.6 ? css('--good') : c <= -0.4 ? css('--bad') : css('--ink-2')}">${c.toFixed(2)}</span>`;
  $('#mkOut').innerHTML = `<div class="mk mono small muted" style="border:0"><span>Asset</span><span>40 days</span><span style="text-align:right">Last</span><span style="text-align:right">Today</span><span style="text-align:right">ρ 20d</span><span style="text-align:right">ρ 60d</span></div>` +
    m.rows.map(r => `<div class="mk"><span><b>${esc(r.key)}</b><div class="nm">${esc(r.name)}</div></span>${spark(r.spark, (r.chg_5d ?? 0) >= 0)}
      <span class="mono" style="text-align:right">${fmtN(r.last, r.last > 1000 ? 0 : 2)}</span><span class="mono ${r.chg_pct > 0 ? 'up' : r.chg_pct < 0 ? 'dn' : ''}" style="text-align:right">${r.chg_pct > 0 ? '+' : ''}${fmtN(r.chg_pct, 2)}%</span>
      <span class="mono" style="text-align:right">${corr(r.corr20)}</span><span class="mono" style="text-align:right">${corr(r.corr60)}</span></div>`).join('');
  $('#mkAlerts').innerHTML = (m.alerts.length ? m.alerts.map(a => `<div class="alert-line ${a.level}">${esc(a.text)}</div>`).join('') : '<div class="empty">No cross-market divergences right now.</div>') +
    '<div class="note">ρ = correlation of daily returns with NQ. A strong negative correlation that weakens, or NQ moving without ES, warns that a move may not hold.</div>';
}

let G = null;
export async function loadGamma() {
  try { G = await api('/api/gamma'); } catch (e) { return; }
  window.LE_GAMMA = G;
  document.dispatchEvent(new CustomEvent('le-gamma', { detail: G }));
  renderTicker();
  if (S.page !== 'news') return;
  const L = G.live;
  if (!L || L.error) { $('#gxOut').innerHTML = `<div class="empty">Gamma unavailable: ${esc(L?.error || 'no option data')}</div>`; return; }
  const pos = L.net_gex_bn > 0;
  $('#gxRegime').textContent = pos ? 'POSITIVE GAMMA' : 'NEGATIVE GAMMA';
  $('#gxRegime').className = 'pill ' + (pos ? 'good' : 'bad');
  const lv = (k, x, c) => `<div class="st"><div class="k">${k}</div><div class="v" style="color:${c}">${x.nq ? fmtN(x.nq) : '—'}</div><div class="muted small">QQQ ${x.qqq ?? '—'}</div></div>`;
  $('#gxOut').innerHTML = `<div class="state-grid" style="grid-template-columns:repeat(3,1fr)">
      ${lv('Call wall · resistance', L.call_wall, 'var(--bad)')}${lv('Gamma flip', L.flip, 'var(--amt)')}${lv('Put wall · support', L.put_wall, 'var(--good-ink)')}</div>
    <div class="note">Net dealer gamma ${L.net_gex_bn > 0 ? '+' : ''}${fmtN(L.net_gex_bn, 2)}bn per 1% move: <b>${esc(L.regime)}</b>. Above the flip dealers dampen moves; below it they chase them.
      QQQ ${fmtN(L.qqq)} × ${L.nq_ratio} = NQ. Expiries 1–45 days (same-day excluded). Model estimate of dealer positioning.</div>`;
  const prof = (L.profile || []).filter(p => Math.abs(p.strike / L.qqq - 1) < 0.05);
  cj('gxChart', {
    type: 'bar',
    data: { labels: prof.map(p => fmtN(p.nq, 0)), datasets: [{ data: prof.map(p => p.net_bn), backgroundColor: prof.map(p => p.net_bn >= 0 ? css('--good') : css('--bad')), borderRadius: 3, borderSkipped: 'start' }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { title: c => `NQ ≈ ${c[0].label}`, label: c => `net gamma ${c.parsed.y.toFixed(3)}bn` } } },
      scales: { x: { title: { display: true, text: 'NQ level (from QQQ strikes)' }, grid: { display: false }, ticks: { maxTicksLimit: 9 } }, y: { title: { display: true, text: '$bn per 1%' } } } }),
  });
  const H = G.spx;
  if (H) {
    $('#gxHist').innerHTML = `<div class="acct-row"><span>Latest (${esc(H.date)})</span><b>${H.gex_bn > 0 ? '+' : ''}${fmtN(H.gex_bn, 2)}bn · ${H.gex_pct}th pct of past year</b></div>
      <div class="acct-row"><span>DIX (dark-pool buying)</span><b>${fmtN(H.dix * 100, 1)}%</b></div>`;
    cj('gxHistChart', {
      type: 'line',
      data: { labels: H.series.map(x => x.date.slice(5)), datasets: [{ data: H.series.map(x => x.gex_bn), borderColor: css('--amt'), borderWidth: 2, pointRadius: 0, tension: 0, fill: { target: { value: 0 }, above: 'rgba(12,163,12,.10)', below: 'rgba(208,59,59,.12)' } }] },
      options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `GEX ${c.parsed.y}bn` } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } }, y: { ticks: { callback: v => v + 'bn' } } } }),
    });
  }
}

function renderGuard() {
  const g = N.guard, now = Date.now() / 1000, nx = g.next_high;
  const box = $('#guardBox');
  box.className = 'guard ' + (g.allowed ? 'ok' : 'block');
  const r = N.rules;
  box.innerHTML = `<div class="light"></div>
    <div class="gt"><b>${g.allowed ? 'Clear to trade' : 'Stand down: no new entries'}</b>
      <div class="r">${g.allowed ? `Blackout ${r.news_before_min}m before → ${r.news_after_min}m after high-impact USD releases${r.fomc_pm_off ? ' · no afternoon trades on FOMC days' : ''}${r.news_flatten_min ? ` · flatten ${r.news_flatten_min}m before` : ''} · day-range guard ${r.day_range_max || 'off'}×`
        : g.reasons.map(esc).join(' · ')}</div>
      <div class="r">Volatility regime: <b>${esc(g.regime || '—')}</b>${r.news_filter ? '' : ' · <span class="dn">news filter is OFF in your settings</span>'}</div></div>
    <div class="cd">${nx ? `<div class="mini-label">Next high-impact</div><div class="mono">${cd(nx.t - now)}</div><div class="small">${esc(nx.event)} · ${esc(nx.time_et)} ET</div>` : '<div class="muted small">No high-impact USD events ahead this week</div>'}</div>`;
}

function renderVol() {
  const v = N.volatility || {};
  $('#volRegime').textContent = (v.regime || '—').toUpperCase();
  $('#volRegime').className = 'pill ' + ({ calm: 'good', normal: '', elevated: 'bad', extreme: 'bad' }[v.regime] || '');
  const row = (name, x) => x ? `<div class="row" style="justify-content:space-between"><b>${name}</b><span class="mono">${fmtN(x.last)} <span class="${x.chg_1d > 0 ? 'dn' : 'up'} small">${x.chg_1d > 0 ? '+' : ''}${fmtN(x.chg_1d)}</span></span></div>
    <div class="vbar" title="${x.pct_1y}th percentile of the last year"><div style="width:${x.pct_1y}%;background:${x.pct_1y >= 75 ? 'var(--bad)' : x.pct_1y <= 20 ? 'var(--good)' : 'var(--accent)'}"></div></div>
    <div class="muted small" style="margin:-6px 0 10px">${x.pct_1y}th percentile of the past year · 1y avg ${fmtN(x.avg_1y)} · as of ${esc(x.date)}</div>` : '';
  $('#volOut').innerHTML = row('VIX · S&P 500 volatility', v.VIX) + row('VXN · Nasdaq-100 volatility', v.VXN);
  const h = (v.VXN || v.VIX)?.history || [];
  cj('vixChart', {
    type: 'line',
    data: { labels: h.map(x => x.date.slice(5)), datasets: [{ data: h.map(x => x.close), borderColor: css('--accent'), borderWidth: 2, pointRadius: 0, tension: 0 }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${v.VXN ? 'VXN' : 'VIX'} ${c.parsed.y}` } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } }, y: {} } }),
  });
}

function renderRange() {
  const r = N.nq_range;
  if (!r) { $('#rangeOut').innerHTML = '<div class="empty">No NQ data.</div>'; return; }
  const lim = N.rules.day_range_max || 0;
  const pct = Math.min(100, r.ratio / Math.max(lim || 2, 2) * 100);
  const col = lim && r.ratio >= lim ? 'var(--bad)' : r.ratio >= 1 ? 'var(--warn)' : 'var(--good)';
  $('#rangeOut').innerHTML = `<div class="big-status" style="color:${col}">${fmtN(r.ratio, 2)}× normal</div>
    <div class="vbar" style="margin-top:12px"><div style="width:${pct}%;background:${col}"></div></div>
    <div class="acct-row"><span>Today's range (${esc(r.date)})</span><b>${fmtN(r.today_range, 2)} pts</b></div>
    <div class="acct-row"><span>20-day average range</span><b>${fmtN(r.adr20, 2)} pts</b></div>
    <div class="acct-row"><span>Guard stops new entries at</span><b>${lim ? lim + '×' : 'off'}</b></div>
    <div class="note">A day that has already run well past its usual range is usually a news or trend day, where sweep reversals tend to fail.</div>`;
}

function renderEarn() {
  const e = N.earnings || [];
  const today = new Date().toISOString().slice(0, 10);
  $('#earnOut').innerHTML = e.length ? `<table class="tbl">${e.map(x => {
    const days = Math.round((new Date(x.date) - new Date(today)) / 864e5);
    return `<tr><td><b>${esc(x.symbol)}</b></td><td class="mono">${esc(x.date)}</td><td class="small ${days <= 2 ? 'dn' : 'muted'}">${days < 0 ? 'reported' : days === 0 ? 'today' : `in ${days}d`}</td></tr>`;
  }).join('')}</table><div class="note">Most report after the close: expect a gap and a faster open the next morning.</div>` : '<div class="empty">No earnings dates available.</div>';
}

function renderCal() {
  if (!N) return;
  const now = Date.now() / 1000, r = N.rules;
  let rows = N.calendar.slice();
  if (ccy === 'USD') rows = rows.filter(e => e.currency === 'USD');
  if (imp === 'high') rows = rows.filter(e => e.impact === 'high');
  if (imp === 'high+') rows = rows.filter(e => e.impact === 'high' || e.impact === 'medium');
  $('#calTable').innerHTML = '<tr><th>Time ET</th><th>Ccy</th><th>Event</th><th>Actual</th><th>Forecast</th><th>Previous</th></tr>' +
    (rows.map(e => {
      const past = e.t < now - 1800;
      const blk = e.impact === 'high' && e.currency === 'USD' && now >= e.t - r.news_before_min * 60 && now <= e.t + r.news_after_min * 60;
      return `<tr class="${past ? 'past' : ''} ${blk ? 'blk' : ''}"><td class="mono">${esc(e.time_et)}</td><td class="mono">${esc(e.currency)}</td>
        <td><span class="imp ${esc(e.impact)}"></span>${esc(e.event)}</td><td class="mono">${esc(e.actual || '')}</td><td class="mono">${esc(e.forecast || '')}</td><td class="mono">${esc(e.previous || '')}</td></tr>`;
    }).join('') || '<tr><td colspan="6" class="empty">No events match.</td></tr>');
}

function renderHl() {
  if (!N) return;
  let h = N.headlines || [];
  if (hlMode === 'hot') h = h.filter(x => x.hot);
  const ago = (t) => { const s = Date.now() / 1000 - t; return !t ? '' : s < 3600 ? `${Math.round(s / 60)}m ago` : s < 86400 ? `${Math.round(s / 3600)}h ago` : etStr(t, true); };
  $('#hlTime').textContent = 'refreshes every 2 min';
  $('#hlOut').innerHTML = h.map(x => `<a class="hl ${x.hot ? 'hot' : ''}" href="${esc(x.link)}" target="_blank" rel="noopener">
    <div class="meta">${esc(x.source)} · ${ago(x.t)}${x.hot ? ' · <span style="color:var(--warn)">MARKET-MOVING</span>' : ''}</div><div>${esc(x.title)}</div></a>`).join('') || '<div class="empty">No headlines.</div>';
}
