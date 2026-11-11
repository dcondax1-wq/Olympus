// Operator pages of the PC dashboard (Modules): Morning report, Live chart with the LIT levels, Bot log, NinjaTrader panel,
// Session timeline, Live settings. Every page only READS (engine/pcops_api.py):
//   GET /api/next/pc/morning   /api/next/pc/chart?tf=   /api/next/pc/logs?cat=&q=&day=   /api/next/pc/nt
//   GET /api/next/pc/timeline  /api/next/pc/settings
// Nothing here starts, arms, routes or stops the bot; the kill switch stays HOLD TO KILL on Bot Control.
import { $, $$, api, esc, store } from '../util.js';
import { icon } from './icons.js';

const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const px = (v) => (ok(v) ? (+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
const usd = (v) => (!ok(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + '$' + Math.round(Math.abs(v)).toLocaleString('en-US'));
const ago = (s) => (!ok(s) ? '—' : s < 90 ? `${Math.max(0, Math.round(s))} s` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${(s / 3600).toFixed(1)} h` : `${Math.round(s / 86400)} d`);
const ET = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const ETS = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
const ETD = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', month: 'short', day: 'numeric' });
const hm = (t) => (ok(t) ? ET.format(new Date(t * 1000)) : '—');
const hms = (t) => (ok(t) ? ETS.format(new Date(t * 1000)) : '—');
const dday = (t) => (ok(t) ? ETD.format(new Date(t * 1000)) : '');
const card = (title, body, tools = '', extra = '') => `<div class="card nx-glass ${extra}"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</div>`;
const hero = (eyebrow, title, desc, side = '') => `<div class="nx-hero"><div><div class="nx-eyebrow">${eyebrow}</div><h2>${title}</h2>${desc ? `<p class="muted">${desc}</p>` : ''}</div>${side}</div>`;
const stat = (k, v, sub = '', c = '') => `<div class="nx-stat"><span>${k}</span><b class="${c}">${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const chip = (t, k = '') => `<span class="nx-chip ${k}">${t}</span>`;
const empty = (t, s = '') => `<div class="pc-empty"><b>${t}</b>${s ? `<span>${s}</span>` : ''}</div>`;
const src = (t) => `<p class="pc-src">${icon('info')}<span>${t}</span></p>`;
const isActive = (id) => document.getElementById('page-' + id)?.classList.contains('active');
const errBox = (e) => card('Could not load', empty(esc(e?.message || e?.error || String(e)), 'The server answers this page read-only; try again in a few seconds.'));
const dot = (okv) => `<span class="op-dot ${okv === true ? 'good' : okv === false ? 'bad' : 'warn'}"></span>`;

// ================================================================== 10. Morning report
const KIND_I = { entry: 'play', exit: 'stop', kill: 'power', stale: 'warn', fresh: 'check', restart: 'refresh', update: 'download', feed: 'warn', error: 'warn', signal: 'target', news: 'news' };
async function morning() {
  const el = $('#page-morning'); if (!el) return;
  let d;
  try { d = await api('/api/next/pc/morning'); } catch (e) { el.innerHTML = errBox(e); return; }
  if (d.error) { el.innerHTML = errBox(d); return; }
  const v = d.verdict || {};
  const lvl = v.level === 'good' ? 'good' : v.level === 'bad' ? 'bad' : 'warn';
  const tr = d.trades || [], gaps = d.gaps || [], rs = d.restarts || [], er = d.errors || [], al = d.alerts || [];
  const nEnt = (d.orders || []).filter((o) => o.side === 'buy' || o.side === 'sell').length;
  const list = (rows, fn, none) => rows.length ? `<ul class="op-list">${rows.map(fn).join('')}</ul>` : empty(none);
  const li = (t, k, txt, extra = '') => `<li><span class="op-t mono">${hm(t)}</span><span class="op-k ${k}">${icon(KIND_I[k] || 'dot')}</span><span class="op-x">${txt}</span>${extra}</li>`;
  el.innerHTML = hero(`Morning report · since ${dday(d.from)} ${hm(d.from)} ET`, esc(d.headline),
    `What the bot did while you were away. Your first look of the day: trades, alerts, feed gaps, restarts, then what is ahead.`,
    `<div class="op-verdict ${lvl}">${dot(lvl === 'good' ? true : lvl === 'bad' ? false : null)}<b>${esc(v.label || (d.running ? 'RUNNING' : 'STOPPED'))}</b><em>${esc(v.reason || d.model_state || '')}</em></div>`) +
    `<div class="nx-stats">${stat('Entries', nEnt, tr.length ? `${tr.length} trade(s) in the journal` : 'overnight')}${stat('Closed P&amp;L', usd(d.pnl), 'MNQ, routed', d.pnl > 0 ? 'up' : d.pnl < 0 ? 'dn' : '')}
      ${stat('Feed gaps', gaps.length, (d.feed_stale || []).length ? `${d.feed_stale.length} FEED STALE warning(s)` : 'while the market was open', gaps.length || (d.feed_stale || []).length ? 'dn' : '')}
      ${stat('Restarts', rs.length, (d.updates || []).length ? `${d.updates.length} update(s)` : 'server / bot')}${stat('Errors', er.filter((x) => !/STALE/i.test(x.text)).length, 'bot log', er.length ? 'dn' : '')}
      ${stat('Alerts sent', al.length, 'phone push')}</div>
    <div class="grid cols-2">
      ${card('Trades and orders', list(d.orders || [], (o) => li(o.t, o.side === 'exit' ? 'exit' : 'entry',
        `${esc(o.side === 'buy' ? 'BUY' : o.side === 'sell' ? 'SELL' : o.side === 'modify' ? 'Stop moved' : 'Exit')} ${esc(o.qty ?? '')}${o.reason ? ' · ' + esc(o.reason) : ''}${o.pnl != null ? ` · <b class="${o.pnl > 0 ? 'up' : 'dn'}">${usd(o.pnl)}</b>` : ''}${o.ok === false ? ` · <b class="dn">REFUSED</b> ${esc(o.error || '')}` : ''}`), 'No orders overnight.'),
        `<button type="button" class="nx-chipbtn" data-goto="accounts">${icon('wallet')}<span>Account</span></button>`)}
      ${card('Feed', list([...(d.feed_stale || []).map((x) => ({ t: x.t, k: 'stale', txt: esc(x.text) })), ...gaps.map((g) => ({ t: g.from, k: 'feed', txt: `${g.tf} bars missing ${hm(g.from)}-${hm(g.to)} ET (${g.missing} bars, ${g.minutes} min)` }))].sort((a, b) => a.t - b.t),
        (x) => li(x.t, x.k, x.txt), 'No feed gaps: NinjaTrader bars arrived the whole night.'),
        `<button type="button" class="nx-chipbtn" data-goto="ntpanel">${icon('sources')}<span>NinjaTrader</span></button>`)}
      ${card('Restarts and updates', list([...rs.map((r) => ({ ...r, k: 'restart' })), ...(d.updates || []).map((r) => ({ ...r, k: 'update' }))].sort((a, b) => a.t - b.t), (r) => li(r.t, r.k, esc(r.text)), 'No restarts overnight.'))}
      ${card('Alerts and errors', list([...al.map((a) => ({ t: a.t, k: 'news', txt: esc(a.title || a.key || a.kind) })), ...er.filter((x) => !/STALE/i.test(x.text)).map((x) => ({ t: x.t, k: 'error', txt: esc(x.text) }))].sort((a, b) => a.t - b.t),
        (x) => li(x.t, x.k, x.txt), 'No alerts, no errors.'), `<button type="button" class="nx-chipbtn" data-goto="botlog">${icon('reports')}<span>Bot log</span></button>`)}
    </div>
    ${card('Today ahead', `<div class="op-ahead">
      <div>${dot(d.running && !d.kill)}<b>Bot ${d.kill ? 'KILLED' : d.running ? 'running' : 'stopped'}</b><span class="muted">${esc(d.model_state || '')}</span></div>
      ${d.position ? `<div>${dot(true)}<b>In a trade: ${esc(d.position.side)} ${esc(d.position.qty)} @ ${px(d.position.entry)}</b><span class="muted">stop ${px(d.position.stop)} · target ${px(d.position.target)} · ${usd(d.position.unrealized_usd)} now</span></div>` : ''}
      ${d.eval_clock?.text ? `<div>${dot(null)}<b>Eval clock</b><span class="muted">${esc(d.eval_clock.text)}</span></div>` : ''}
      ${(d.setups || []).length ? `<div>${dot(null)}<b>${d.setups.length} setup(s) seen</b><span class="muted">${d.setups.map((s) => `${esc(s.side)} ${esc(s.level || '')} limit ${px(s.limit)}`).join(' · ')}</span></div>` : ''}
      <div>${dot((d.news?.events || []).some((e) => e.tier1) ? null : true)}<b>News today</b><span class="muted">${esc(d.news?.text || 'no high-impact USD events')}</span></div>
    </div>`, `<button type="button" class="nx-chipbtn" data-goto="timeline">${icon('clock')}<span>Timeline</span></button><button type="button" class="nx-chipbtn" data-goto="livechart">${icon('chart')}<span>Live chart</span></button>`)}
    ${src('Window: 16:00 ET yesterday (after the 15:55 flat) to now. From the bot\'s ledger, log and 1m / 5m bars, the journal and the push log; read-only.')}`;
}

// ================================================================== 4. Live chart with the LIT levels
const LC = { tf: store.get('nx.lc.tf', '5m'), d: null, busy: false, hover: null, offList: true };
const LVL_C = { H: 'var(--bsl, #ff5a7a)', L: 'var(--ssl, #7f8a52)' };
function chartSVG(d, W, H) {
  const bars = d.bars || [];
  if (!bars.length) return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="op-svg"><text x="${W / 2}" y="${H / 2}" text-anchor="middle" class="op-mut">no bars yet</text></svg>`;
  const small = W < 560, RA = small ? 92 : 176, BA = 20, T = 8, cw = W - RA;
  const lo0 = Math.min(...bars.map((b) => b[3])), hi0 = Math.max(...bars.map((b) => b[2]));
  const lines = (d.lines || []).filter((l) => ok(l.price));
  let lo = Math.min(lo0, ...lines.map((l) => +l.price)), hi = Math.max(hi0, ...lines.map((l) => +l.price));
  const span = Math.max(4, hi - lo), pad = span * 0.08;
  const near = (d.levels || []).filter((l) => ok(l.price) && +l.price >= lo - span * 0.35 && +l.price <= hi + span * 0.35);
  for (const l of near) { lo = Math.min(lo, +l.price); hi = Math.max(hi, +l.price); }
  lo -= pad; hi += pad;
  const n = bars.length, bw = cw / Math.max(n, 30);
  const X = (i) => i * bw + bw / 2, Y = (p) => T + (hi - p) / (hi - lo) * (H - T - BA);
  const secs = d.tf === '1m' ? 60 : 300;
  const T0 = bars[0][0];
  const xi = (t) => { let lo2 = 0, hi2 = n - 1; if (t <= bars[0][0]) return (t - T0) / secs; while (lo2 < hi2) { const m = (lo2 + hi2 + 1) >> 1; if (bars[m][0] <= t) lo2 = m; else hi2 = m - 1; } return lo2 + Math.min(1, (t - bars[lo2][0]) / secs); };
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="op-svg" data-n="${n}">`;
  // killzones (shaded)
  const day = d.day;
  for (const z of d.killzones || []) {
    const a = bars.findIndex((b) => etMin(b[0]) >= z.from && etMin(b[0]) < z.to && sameDay(b[0], day));
    if (a < 0) continue;
    let b2 = a; while (b2 + 1 < n && etMin(bars[b2 + 1][0]) < z.to && sameDay(bars[b2 + 1][0], day)) b2++;
    s += `<rect x="${(a * bw).toFixed(1)}" y="${T}" width="${((b2 - a + 1) * bw).toFixed(1)}" height="${H - T - BA}" class="op-kz"/><text x="${(a * bw + 4).toFixed(1)}" y="${T + 11}" class="op-kzt">${esc(z.label)}</text>`;
  }
  // price grid
  const step = nice((hi - lo) / 6);
  for (let p = Math.ceil(lo / step) * step; p <= hi; p += step) s += `<line x1="0" x2="${cw}" y1="${Y(p).toFixed(1)}" y2="${Y(p).toFixed(1)}" class="op-grid"/><text x="${cw + 4}" y="${(Y(p) + 3).toFixed(1)}" class="op-ax">${px(p)}</text>`;
  // time axis
  let lastH = -1;
  bars.forEach((b, i) => { const m = etMin(b[0]); if (m % 120 === 0 && m !== lastH) { lastH = m; s += `<text x="${X(i).toFixed(1)}" y="${H - 5}" class="op-ax" text-anchor="middle">${hm(b[0])}</text><line x1="${X(i).toFixed(1)}" x2="${X(i).toFixed(1)}" y1="${T}" y2="${H - BA}" class="op-grid"/>`; } });
  // levels
  const labels = [];
  for (const l of near) {
    const y = Y(+l.price), x0 = l.taken && l.taken_t ? Math.max(0, xi(l.taken_t) * bw) : 0;
    const c = LVL_C[l.side] || 'var(--gold)';
    s += `<line x1="${l.taken ? x0.toFixed(1) : 0}" x2="${cw}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${c}" class="op-lv ${l.taken ? 'taken' : ''}"/>`;
    labels.push({ y, text: `${l.label}${l.taken ? ' · swept' : ''}`, price: l.price, c, cls: l.taken ? 'taken' : '' });
  }
  // trade lines
  const LC_C = { entry: 'var(--accent)', stop: 'var(--bad)', target: 'var(--good)', be: 'var(--warn)', limit: 'var(--gold)' };
  for (const l of lines) {
    const y = Y(+l.price), c = LC_C[l.id] || 'var(--ink-2)';
    s += `<line x1="0" x2="${cw}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${c}" class="op-tl ${l.id}"/>`;
    labels.push({ y, text: l.label, price: l.price, c, cls: 'tl', strong: true });
  }
  // candles
  for (let i = 0; i < n; i++) {
    const [, o, h, l2, c] = bars[i], up = c >= o, x = X(i);
    s += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${Y(h).toFixed(1)}" y2="${Y(l2).toFixed(1)}" class="op-wick ${up ? 'up' : 'dn'}"/>` +
      `<rect x="${(x - bw * 0.36).toFixed(1)}" y="${Y(Math.max(o, c)).toFixed(1)}" width="${Math.max(1, bw * 0.72).toFixed(1)}" height="${Math.max(1, Math.abs(Y(o) - Y(c))).toFixed(1)}" class="op-body ${up ? 'up' : 'dn'}"/>`;
  }
  // entries / exits
  for (const m of d.marks || []) {
    const i = xi(m.t); if (i < 0 || i > n) continue;
    const bar = bars[Math.max(0, Math.min(n - 1, Math.floor(i)))];
    const p = ok(m.price) ? +m.price : bar[4];
    const x = X(Math.floor(i)), y = Y(p);
    if (m.kind === 'entry') s += m.side === 'buy' ? `<path d="M${x} ${y + 4} l6 10 h-12z" class="op-mk long"/>` : `<path d="M${x} ${y - 4} l6 -10 h-12z" class="op-mk short"/>`;
    else s += `<circle cx="${x}" cy="${y}" r="5" class="op-mk exit ${m.pnl > 0 ? 'win' : m.pnl < 0 ? 'loss' : ''}"/>`;
  }
  // last price
  const last = bars[n - 1][4];
  labels.push({ y: Y(last), text: 'Last', price: last, c: 'var(--ink)', cls: 'last', strong: true });
  s += `<line x1="0" x2="${cw}" y1="${Y(last).toFixed(1)}" y2="${Y(last).toFixed(1)}" class="op-last"/>`;
  // right-hand labels, pushed apart
  labels.sort((a, b) => a.y - b.y);
  const gap = small ? 12 : 13;
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < gap) labels[i].ly = (labels[i - 1].ly ?? labels[i - 1].y) + gap;
  for (const lb of labels) {
    const ly = Math.min(H - BA - 2, Math.max(T + 8, lb.ly ?? lb.y));
    const t = small ? lb.text.slice(0, 14) : lb.text.slice(0, 24);
    s += `<g class="op-lab ${lb.cls}"><rect x="${cw + 1}" y="${(ly - 6.5).toFixed(1)}" width="${RA - 2}" height="13" rx="3" class="op-labund"/><rect x="${cw + 1}" y="${(ly - 6.5).toFixed(1)}" width="${RA - 2}" height="13" rx="3" fill="${lb.c}" class="op-labbg"/><text x="${cw + 5}" y="${(ly + 3.5).toFixed(1)}" class="op-labt">${esc(t)} ${small ? '' : px(lb.price)}</text></g>`;
  }
  if (LC.hover != null && bars[LC.hover]) { const x = X(LC.hover); s += `<line x1="${x}" x2="${x}" y1="${T}" y2="${H - BA}" class="op-cross"/>`; }
  return s + '</svg>';
}
function nice(r) { const p = Math.pow(10, Math.floor(Math.log10(Math.max(r, 1e-6)))); for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= r) return m * p; return 10 * p; }
const ETM = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' });
const ETDAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' });
function etMin(t) { const [h, m] = ETM.format(new Date(t * 1000)).split(':').map(Number); return (h % 24) * 60 + m; }
function sameDay(t, day) { return ETDAY.format(new Date(t * 1000)) === day; }

async function livechart(force) {
  const el = $('#page-livechart'); if (!el) return;
  if (!el.dataset.ready) {
    el.dataset.ready = '1';
    el.innerHTML = hero('Live chart · read-only', 'Today\'s bars with the LIT levels the bot watches',
      'Levels from the live LIT plan (engine/lit_brief): untaken levels solid, swept levels dashed from the sweep. The open trade\'s entry, stop, target and breakeven trigger and any armed limit are drawn on top.',
      `<div class="seg sm" id="lcTf"><button type="button" data-v="5m">5m</button><button type="button" data-v="1m">1m</button></div>`) +
      `<div class="card nx-glass op-chartcard"><div class="op-chead" id="lcHead"></div><div class="op-chart" id="lcChart"></div><div class="op-legend" id="lcLegend"></div></div>
       <div class="grid cols-2"><div id="lcLevels"></div><div id="lcTrade"></div></div><div id="lcSrc"></div>`;
    $('#lcTf').onclick = (e) => { const b = e.target.closest('button[data-v]'); if (!b) return; LC.tf = b.dataset.v; store.set('nx.lc.tf', LC.tf); livechart(true); };
    const ch = $('#lcChart');
    ch.addEventListener('mousemove', (e) => { const svg = ch.querySelector('svg'); if (!svg || !LC.d?.bars?.length) return; const r = svg.getBoundingClientRect(); const small = r.width < 560; const cw = r.width - (small ? 92 : 176); const n = LC.d.bars.length; const bw = cw / Math.max(n, 30); const i = Math.floor((e.clientX - r.left) / bw); if (i >= 0 && i < n && i !== LC.hover) { LC.hover = i; drawChart(); } });
    ch.addEventListener('mouseleave', () => { LC.hover = null; drawChart(); });
    new ResizeObserver(() => drawChart()).observe(ch);
  }
  $$('#lcTf button').forEach((b) => b.classList.toggle('on', b.dataset.v === LC.tf));
  if (LC.busy && !force) return;
  LC.busy = true;
  try { LC.d = await api('/api/next/pc/chart?tf=' + LC.tf); } catch (e) { LC.d = { error: e.message }; } finally { LC.busy = false; }
  const d = LC.d;
  if (d.error) { $('#lcChart').innerHTML = empty('No chart', esc(d.error)); return; }
  drawChart();
  const lv = d.levels || [];
  const lp = ok(d.price) ? +d.price : null;
  const rows = lv.slice().sort((a, b) => (+b.price) - (+a.price)).map((l) => `<tr class="${l.taken ? 'muted' : ''}"><td><span class="op-sw" style="background:${LVL_C[l.side] || 'var(--gold)'}"></span>${esc(l.label)}</td><td class="mono r">${px(l.price)}</td>
    <td class="mono r">${lp != null ? (l.price - lp > 0 ? '+' : '') + (l.price - lp).toFixed(1) : '—'}</td><td>${l.taken ? chip('swept ' + hm(l.taken_t), '') : chip('watching', 'good')}</td></tr>`).join('');
  $('#lcLevels').innerHTML = card('LIT levels', lv.length ? `<div class="op-tw"><table class="op-tab"><thead><tr><th>Level</th><th class="r">Price</th><th class="r">Pts away</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>` : empty('No levels', esc(d.plan_error || 'The LIT plan has no levels for this session yet.')),
    `<span class="muted small">${lv.filter((l) => !l.taken).length} watched · ${lv.filter((l) => l.taken).length} swept</span>`);
  const L = d.lines || [];
  $('#lcTrade').innerHTML = card('Open trade and armed limits', L.length ? `<ul class="op-list">${L.map((l) => `<li><span class="op-k ${l.id}">${icon(l.id === 'stop' ? 'stop' : l.id === 'target' ? 'target' : l.id === 'limit' ? 'clock' : 'play')}</span><span class="op-x">${esc(l.label)}</span><b class="mono">${px(l.price)}</b></li>`).join('')}</ul>` : empty('Flat', 'No open trade and no armed limit right now.'),
    `<button type="button" class="nx-chipbtn" data-goto="accounts">${icon('wallet')}<span>Account</span></button>`);
  $('#lcSrc').innerHTML = src(`Bars: ${esc(d.source)}. Levels: LIT plan of ${esc(d.plan_day || d.day)}. ${esc(d.model_state || '')}`);
}
function drawChart() {
  const d = LC.d, ch = $('#lcChart'); if (!d || !ch || d.error) return;
  const W = Math.max(300, Math.floor(ch.clientWidth || 800)), H = W < 560 ? 320 : 460;
  ch.innerHTML = chartSVG(d, W, H);
  const b = d.bars?.[LC.hover ?? d.bars.length - 1];
  $('#lcHead').innerHTML = b ? `<span class="mono">${dday(b[0])} ${hm(b[0])} ET</span><span>O <b class="mono">${px(b[1])}</b></span><span>H <b class="mono">${px(b[2])}</b></span><span>L <b class="mono">${px(b[3])}</b></span><span>C <b class="mono">${px(b[4])}</b></span><span class="muted">${esc(d.tf)} · ${d.bars.length} bars</span>` : '';
  $('#lcLegend').innerHTML = `<span><i class="op-sw" style="background:${LVL_C.H}"></i>buy-side level (high)</span><span><i class="op-sw" style="background:${LVL_C.L}"></i>sell-side level (low)</span><span><i class="op-sw dash"></i>swept</span><span><i class="op-sw" style="background:var(--accent)"></i>entry</span><span><i class="op-sw" style="background:var(--bad)"></i>stop</span><span><i class="op-sw" style="background:var(--good)"></i>target</span><span><i class="op-sw" style="background:var(--warn)"></i>BE trigger</span><span><i class="op-kzsw"></i>killzone</span>`;
}

// ================================================================== 5. Log viewer
const LG = { cat: store.get('nx.lg.cat', ''), q: '', day: '', auto: true, timer: null };
const CAT_L = [['', 'All'], ['orders', 'Orders'], ['signals', 'Signals'], ['errors', 'Errors'], ['system', 'System']];
async function botlog() {
  const el = $('#page-botlog'); if (!el) return;
  if (!el.dataset.ready) {
    el.dataset.ready = '1';
    el.innerHTML = hero('Bot log · read-only', 'Everything the bot wrote today',
      'The bot\'s own log, its order ledger, the server log, every NinjaTrader order line (OIF), updates and ops checks, in one list. Filter by kind, search by word.',
      '') +
      `<div class="card nx-glass"><div class="op-lgbar">
         <div class="seg sm" id="lgCat"></div>
         <label class="nx-field op-q">${icon('search')}<input id="lgQ" class="inp" placeholder="Search the log (e.g. stale, BE, 1m CISD)" autocomplete="off" spellcheck="false"></label>
         <input type="date" id="lgDay" class="inp op-day" title="Trading day (18:00 ET the day before to 17:00)">
         <label class="nx-chip link"><input type="checkbox" id="lgAuto" checked> live</label>
       </div><div id="lgMeta" class="muted small op-meta"></div><div id="lgRows" class="op-log"></div></div>`;
    let tq = 0;
    $('#lgQ').oninput = (e) => { clearTimeout(tq); tq = setTimeout(() => { LG.q = e.target.value.trim(); botlog(); }, 250); };
    $('#lgDay').onchange = (e) => { LG.day = e.target.value; botlog(); };
    $('#lgAuto').onchange = (e) => { LG.auto = e.target.checked; };
    $('#lgCat').onclick = (e) => { const b = e.target.closest('button[data-v]'); if (!b) return; LG.cat = b.dataset.v; store.set('nx.lg.cat', LG.cat); botlog(); };
    LG.timer = setInterval(() => { if (LG.auto && isActive('botlog') && !document.hidden) botlog(); }, 10000);
  }
  let d;
  const qs = new URLSearchParams({ cat: LG.cat, q: LG.q, day: LG.day, limit: '800' });
  try { d = await api('/api/next/pc/logs?' + qs); } catch (e) { $('#lgRows').innerHTML = empty('Could not load the log', esc(e.message)); return; }
  if (d.error) { $('#lgRows').innerHTML = empty('Could not load the log', esc(d.error)); return; }
  if (!LG.day && $('#lgDay') && !$('#lgDay').value) $('#lgDay').value = d.day;
  $('#lgCat').innerHTML = CAT_L.map(([k, l]) => `<button type="button" data-v="${k}" class="${(d.cat === 'all' ? '' : d.cat) === k ? 'on' : ''}">${l}<em>${k ? d.counts[k] || 0 : d.total}</em></button>`).join('');
  $('#lgMeta').textContent = `${d.matched} of ${d.total} rows · trading day ${d.day}${d.files.length ? ' · files: ' + d.files.join(', ') : ' · no log files for this day on this PC'}${d.access_lines ? ` · ${d.access_lines} web requests hidden` : ''}`;
  const hl = (t) => { const s = esc(t || ''); if (!d.q) return s; const q = d.q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); return s.replace(new RegExp(q, 'ig'), (m) => `<mark>${m}</mark>`); };
  $('#lgRows').innerHTML = d.rows.length ? d.rows.map((r) => `<div class="op-lr ${r.cat}"><span class="mono op-t">${hms(r.t)}</span><span class="op-src">${esc(r.src)}</span><span class="op-cat ${r.cat}">${esc(r.cat)}</span><span class="op-txt mono">${hl(r.text)}</span></div>`).join('')
    : empty('Nothing matches', d.q ? 'Try another word, or All.' : 'The bot has not written anything for this day yet.');
}

// ================================================================== 6. NinjaTrader panel
async function ntpanel() {
  const el = $('#page-ntpanel'); if (!el) return;
  let d;
  try { d = await api('/api/next/pc/nt'); } catch (e) { el.innerHTML = errBox(e); return; }
  if (d.error) { el.innerHTML = errBox(d); return; }
  const rows = d.rows || [];
  const red = rows.filter((r) => r.ok === false);
  const b = d.bars || {};
  const ageC = (s, lim) => (!ok(s) ? '' : s <= lim ? 'up' : d.market_open ? 'dn' : '');
  el.innerHTML = hero('NinjaTrader · read-only', red.length ? `${red.length} thing${red.length > 1 ? 's' : ''} to fix` : 'NinjaTrader looks healthy',
    'Connection, the LE_BarFeed bar files, the order files the bot sent and NinjaTrader\'s reports. Every red row says what to do.',
    `<div class="op-verdict ${red.length ? 'bad' : 'good'}">${dot(!red.length)}<b>${esc(d.account?.name || '—')}</b><em>${esc(d.account?.label || '')} · ${esc(d.account?.adapter || '')}</em></div>`) +
    `<div class="nx-stats">${stat('Bot 5m bar', ago(b.bot_5m_age_s), 'old', ageC(b.bot_5m_age_s, 420))}${stat('Bot 1m bar', ago(b.bot_1m_age_s), 'old', ageC(b.bot_1m_age_s, 180))}
      ${stat('LE_BarFeed 5m', ago(b.file_5m_age_s), 'file', ageC(b.file_5m_age_s, 420))}${stat('LE_BarFeed 1m', ago(b.file_1m_age_s), 'file', ageC(b.file_1m_age_s, 180))}
      ${stat('Waiting order files', d.leftovers || 0, 'in incoming', d.leftovers ? 'dn' : '')}${stat('Market', d.market_open ? 'open' : 'closed', 'CME Globex')}</div>
    ${card('Checks', `<div class="op-checks">${rows.map((r) => `<div class="op-ck ${r.ok === true ? 'good' : r.ok === false ? 'bad' : 'warn'}">${dot(r.ok)}<div><b>${esc(r.label)}</b><span>${esc(r.detail)}</span>${r.fix ? `<p class="op-fix">${icon('info')}<span>${esc(r.fix)}</span></p>` : ''}</div></div>`).join('')}</div>`)}
    <div class="grid cols-2">
      ${card('Order files sent (OIF)', (d.sent || []).length ? `<div class="op-tw"><table class="op-tab"><thead><tr><th>ET</th><th>Action</th><th>File</th></tr></thead><tbody>${d.sent.map((r) => `<tr><td class="mono">${hms(r.t)}</td><td>${chip(esc(r.action))}</td><td class="mono small" title="${esc(r.lines.join('\n'))}">${esc(r.file)}</td></tr>`).join('')}</tbody></table></div>` : empty('None yet', 'logs/ninjatrader_oif.log has no order lines (no orders sent on this PC).'))}
      ${card('Reports received (outgoing)', (d.received || []).length ? `<div class="op-tw"><table class="op-tab"><thead><tr><th>Changed</th><th>Kind</th><th>File</th><th>Says</th></tr></thead><tbody>${d.received.map((r) => `<tr><td class="mono">${hms(r.t)}</td><td>${chip(esc(r.kind))}</td><td class="mono small">${esc(r.file)}</td><td class="mono small">${esc(r.content)}</td></tr>`).join('')}</tbody></table></div>` : empty('Nothing in outgoing', 'NinjaTrader writes order states, positions and connection changes here.'))}
      ${card('Account positions (NinjaTrader)', (d.positions || []).length ? `<div class="op-tw"><table class="op-tab"><thead><tr><th>Account</th><th>Instrument</th><th>Side</th><th class="r">Qty</th><th class="r">Avg</th></tr></thead><tbody>${d.positions.map((p) => `<tr><td>${esc(p.account)}</td><td>${esc(p.instrument)}</td><td>${chip(esc(p.side), p.side === 'FLAT' ? '' : 'warn')}</td><td class="r mono">${esc(p.qty ?? '—')}</td><td class="r mono">${px(p.avg)}</td></tr>`).join('')}</tbody></table></div>` : empty('No position files', 'They appear after an account\'s first order.'))}
      ${card('The bot\'s open brackets', (d.legs || []).length ? `<ul class="op-list">${d.legs.map((l) => `<li><span class="op-k entry">${icon('play')}</span><span class="op-x">${esc(l.instrument || '')} ${l.dir > 0 ? 'LONG' : 'SHORT'} ${esc(l.filled ?? '')} @ ${px(l.fill_px)} · ${esc(l.status || '')}</span><b class="mono">stop ${px(l.stop)} · tgt ${px(l.target)}</b></li>`).join('')}</ul>` : empty('None', 'No bracket open.'))}
    </div>
    ${src('Read from Documents\\NinjaTrader 8 (incoming / outgoing / le_feed), logs/ninjatrader_oif.log and the bot\'s adapter state. This page never writes an order file.')}`;
}

// ================================================================== 7. Session timeline
const TL_C = { entry: 'var(--accent)', exit: 'var(--good)', kill: 'var(--bad)', stale: 'var(--warn)', feed: 'var(--warn)', fresh: 'var(--good)', restart: 'var(--accent-2, #7f8a52)', update: 'var(--gold)', error: 'var(--bad)', signal: 'var(--gold)' };
const LANE = { entry: 0, exit: 0, kill: 0, signal: 1, stale: 2, feed: 2, fresh: 2, error: 2, restart: 3, update: 3 };
const LANES = ['Trades', 'Setups', 'Feed / errors', 'Restarts / updates'];
async function timeline() {
  const el = $('#page-timeline'); if (!el) return;
  let d;
  try { d = await api('/api/next/pc/timeline'); } catch (e) { el.innerHTML = errBox(e); return; }
  if (d.error) { el.innerHTML = errBox(d); return; }
  el.innerHTML = hero(`Session timeline · ${esc(d.day)}`, 'Today from 18:00 to 17:00 ET',
    'Killzones and the LIT entry window, the news, every setup, entry and exit, restarts, updates and feed problems on one line.', '') +
    `<div class="card nx-glass"><div id="tlSvg" class="op-tl"></div><div class="op-legend">${Object.entries({ entry: 'entry', exit: 'exit', signal: 'setup', stale: 'feed stale', restart: 'restart', update: 'update', kill: 'kill' }).map(([k, l]) => `<span><i class="op-sw" style="background:${TL_C[k]}"></i>${l}</span>`).join('')}<span><i class="op-sw" style="background:var(--bad)"></i>high-impact news</span><span><i class="op-kzsw"></i>killzone</span></div></div>
    ${card('Events', (d.events || []).length || (d.news || []).length ? `<ul class="op-list">${[...(d.events || []).map((e) => ({ t: e.t, k: e.kind, txt: esc(e.text) })), ...(d.news || []).map((n) => ({ t: n.t, k: 'news', txt: `${n.tier1 ? '<b>' : ''}${esc(n.title)}${n.tier1 ? '</b>' : ''}` }))].sort((a, b) => a.t - b.t).map((x) => `<li><span class="op-t mono">${hm(x.t)}</span><span class="op-k ${x.k}" style="color:${TL_C[x.k] || 'var(--bad)'}">${icon(KIND_I[x.k] || 'dot')}</span><span class="op-x">${x.txt}</span></li>`).join('')}</ul>` : empty('Nothing yet today', 'Events appear here as the session runs.'))}`;
  const box = $('#tlSvg');
  const draw = () => { box.innerHTML = tlSVG(d, Math.max(300, box.clientWidth || 800)); };
  draw();
  if (!box._ro) { box._ro = new ResizeObserver(draw); box._ro.observe(box); }
}
function tlSVG(d, W) {
  const small = W < 560, LW = small ? 0 : 118, top = 26, laneH = small ? 26 : 30, H = top + LANES.length * laneH + 26, cw = W - LW - 8;
  const X = (t) => LW + (t - d.t0) / (d.t1 - d.t0) * cw;
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="op-svg">`;
  for (const b of d.bands || []) {
    const x0 = X(b.t0), x1 = X(b.t1);
    if (b.kind === 'window') s += `<rect x="${x0}" y="${top - 4}" width="${x1 - x0}" height="${LANES.length * laneH + 8}" class="op-win"/>`;
    else s += `<rect x="${x0}" y="${top}" width="${x1 - x0}" height="${LANES.length * laneH}" class="${b.kind === 'close' ? 'op-close' : 'op-kz'}"/>${small ? '' : `<text x="${x0 + 4}" y="${top + 11}" class="op-kzt">${esc(b.label)}</text>`}`;
  }
  LANES.forEach((l, i) => { const y = top + i * laneH; s += `<line x1="${LW}" x2="${W - 8}" y1="${y + laneH}" y2="${y + laneH}" class="op-grid"/>${small ? '' : `<text x="4" y="${y + laneH / 2 + 4}" class="op-ax">${l}</text>`}`; });
  for (let t = d.t0; t <= d.t1; t += 3600) { const m = etMin(t); if (small ? m % 240 === 0 || m === 1080 : m % 120 === 0 || m === 1080) s += `<text x="${X(t)}" y="${H - 8}" text-anchor="middle" class="op-ax">${hm(t)}</text><line x1="${X(t)}" x2="${X(t)}" y1="${top}" y2="${top + LANES.length * laneH}" class="op-grid"/>`; }
  for (const n of d.news || []) s += `<line x1="${X(n.t)}" x2="${X(n.t)}" y1="${top - 10}" y2="${top + LANES.length * laneH}" class="op-news ${n.tier1 ? 'hi' : ''}"><title>${esc(hm(n.t) + ' ' + n.title)}</title></line><circle cx="${X(n.t)}" cy="${top - 12}" r="3" class="op-news-d ${n.tier1 ? 'hi' : ''}"/>`;
  for (const e of d.events || []) {
    const ln = LANE[e.kind] ?? 3, y = top + ln * laneH + laneH / 2, x = X(e.t);
    s += `<circle cx="${x.toFixed(1)}" cy="${y}" r="${small ? 4.5 : 5.5}" fill="${TL_C[e.kind] || 'var(--ink-2)'}" class="op-ev"><title>${esc(hm(e.t) + ' ' + e.text)}</title></circle>`;
  }
  const now = Math.min(d.t1, Math.max(d.t0, d.t));
  s += `<line x1="${X(now)}" x2="${X(now)}" y1="${top - 6}" y2="${top + LANES.length * laneH + 4}" class="op-now"/><text x="${X(now)}" y="${top - 12}" text-anchor="middle" class="op-nowt">now ${hm(d.t)}</text>`;
  return s + '</svg>';
}

// ================================================================== 9. Settings viewer
async function livesettings() {
  const el = $('#page-livesettings'); if (!el) return;
  let d;
  try { d = await api('/api/next/pc/settings'); } catch (e) { el.innerHTML = errBox(e); return; }
  if (d.error) { el.innerHTML = errBox(d); return; }
  const groups = {};
  for (const r of d.rows || []) (groups[r.group] = groups[r.group] || []).push(r);
  const order = ['switch', 'pack', 'eval', 'size', 'entry', 'risk', 'exit', 'core'];
  const val = (v) => esc(v === null ? 'null' : typeof v === 'object' ? JSON.stringify(v) : String(v));
  const R = d.results || {};
  el.innerHTML = hero('Live settings · read-only', esc(d.label || 'live_model.json'),
    `What every switch in live_model.json does, in plain words, with its tested numbers. ${d.locked ? `Locked ${esc(d.chosen || '')}.` : ''}`,
    `<div class="op-verdict warn">${icon('rules')}<b>Read-only</b><em>this page cannot change anything</em></div>`) +
    `${(d.drift || []).length ? `<div class="op-alert bad">${icon('warn')}<span><b>live_model.json and live_model_lit.json differ</b> on ${d.drift.map(esc).join(', ')}. Keep them identical.</span></div>` : ''}
    <div class="op-alert">${icon('edit')}<span><b>To change a setting:</b> ${esc(d.edit)}</span></div>
    ${card('Tested numbers of the live set', `<div class="op-res">${Object.entries(R).map(([k, v]) => `<div><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join('')}</div>`)}
    ${order.filter((g) => groups[g]).map((g) => card(esc(d.groups[g] || g), `<div class="op-set">${groups[g].map((r) => `<div class="op-sr">
        <div class="op-sn"><b>${esc(r.name)}</b>${r.on === true ? chip('ON', 'good') : r.on === false ? chip('OFF', '') : ''}<span class="mono op-val">${val(r.value)}</span></div>
        <p>${esc(r.what)}</p>${r.tested ? `<p class="op-tested">${icon('results')}<span>${esc(r.tested)}</span></p>` : ''}
        <span class="mono muted small">${esc(r.file)} › ${esc(r.path)}</span></div>`).join('')}</div>`)).join('')}
    ${(d.other || []).length ? card('Other keys (no plain-words entry yet)', `<div class="op-set">${d.other.map((o) => `<div class="op-sr"><div class="op-sn"><span class="mono">${esc(o.path)}</span><span class="mono op-val">${val(o.value)}</span></div></div>`).join('')}</div>`) : ''}
    ${src('Read from live_model.json and live_model_lit.json; switch numbers from research/lit/adopt_combo.json; the rest from the runs named (research/runs).')}`;
}

// ------------------------------------------------------------------ page objects + refresh
let tick = null;
function auto(id, fn, ms) { return { show: () => { fn(true); clearInterval(tick); tick = setInterval(() => { if (isActive(id) && !document.hidden) fn(); else clearInterval(tick); }, ms); } }; }
export const pages = {
  morning: auto('morning', morning, 60000),
  livechart: auto('livechart', livechart, 15000),
  botlog: { show: () => botlog() },
  ntpanel: auto('ntpanel', ntpanel, 10000),
  timeline: auto('timeline', timeline, 30000),
  livesettings: { show: () => livesettings() },
};
// a new entry / exit redraws the live chart at once (the trade lines move)
let lastPos = null;
document.addEventListener('le-pulse', (e) => {
  const k = JSON.stringify(e.detail?.position ? [e.detail.position.entry_t, e.detail.position.stop] : null);
  if (k !== lastPos) { const first = lastPos === null; lastPos = k; if (!first && isActive('livechart') && !LC.busy) livechart(); }
});
