// PC dashboard: the bot's own account and status, plus the phone app's extras, in the web_next design.
//   Today header  (#pcStatus on #page-command)  TRADING YOUR EVAL / ON SIM / PAPER ONLY / DISABLED / FEED STALE from the bot's
//                 adapter state: account, live vs sim, orders enabled, feed age, last poll, LIT stage, setups seen today
//   Accounts      (#page-accounts)   eval card (balance incl. the -$100 before eval_start, trailing floor, room, progress to
//                 +$3,000, session N of 10, daily loss used), open position + live chart, today's order timeline, equity curve,
//                 P&L calendar, every routed trade with its chart and filters
//   Eval HQ       (#page-evalhq)     the 2-week pass path: $ to go, $ per session, what one winner pays (two_week sizing), odds
//   Edge          (#page-edge)       where LIT makes its money (backtest): R, exits, MFE / MAE, stop size, hour, weekday, levels
//   P&L calendar  (#page-pnlcal)     daily P&L month grid (backtest or the PC bot), streaks, this week vs the backtest
//   MFFU rules    (#page-mffurules)  the Builder 50K rulebook (research/lit/mffu_rules.json) and how LIT fits it
// Data (all read-only GETs): /api/next/pc/status, /api/next/pc/account, /api/next/pc/trade/<entry_t>, /api/next/extras (the phone's
// data.json "extras" shapes), /api/next/lit_extra, /api/next/results. Nothing on these pages starts, arms, routes or stops the bot.
import { $, $$, api, esc, fmt$, fmtS$, fmtN, fmtR, cls, etStr, store } from '../util.js';
import { lineChart } from './viz.js';
import { onLive } from '../dash/live.js';
import { icon } from './icons.js';

const TCV = '../tradechart.js?v=b1526d92';
let TCP = null;
const loadTC = () => TCP || (TCP = import(TCV).catch((e) => { TCP = null; throw e; }));

// ------------------------------------------------------------------ data
const D = { st: null, stAt: 0, ac: null, acAt: 0, x: null, lx: null, rs: null };
async function getStatus(force) {
  if (!force && D.st && Date.now() - D.stAt < 10000) return D.st;
  try { D.st = await api('/api/next/pc/status'); D.stAt = Date.now(); } catch (e) { D.st = D.st || { error: e.message }; }
  return D.st;
}
async function getAccount(force) {
  if (!force && D.ac && Date.now() - D.acAt < 10000) return D.ac;
  try { D.ac = await api('/api/next/pc/account'); D.acAt = Date.now(); } catch (e) { D.ac = D.ac || { error: e.message }; }
  return D.ac;
}
async function getStatic() {
  const jobs = [];
  if (!D.x) jobs.push(api('/api/next/extras').then((d) => { D.x = d; }).catch(() => { D.x = D.x || {}; }));
  if (!D.lx) jobs.push(api('/api/next/lit_extra').then((d) => { D.lx = d; }).catch(() => { D.lx = D.lx || {}; }));
  if (!D.rs) jobs.push(api('/api/next/results').then((d) => { D.rs = d; }).catch(() => { D.rs = D.rs || {}; }));
  await Promise.all(jobs);
}

// ------------------------------------------------------------------ helpers
const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const pct = (v, d = 1) => (ok(v) ? (+v).toFixed(d).replace(/\.0$/, '') + '%' : '—');
const kusd = (v) => (!ok(v) ? '—' : (v < 0 ? '−' : '') + '$' + (Math.abs(v) >= 10000 ? (Math.abs(v) / 1000).toFixed(1) + 'k' : Math.round(Math.abs(v)).toLocaleString('en-US')));
const px = (v) => (ok(v) ? (+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const sum = (a, f) => a.reduce((s, x) => s + (f ? f(x) : x), 0);
const med = (a) => { const s = a.filter(ok).map(Number).sort((x, y) => x - y); return s.length ? (s.length % 2 ? s[s.length >> 1] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };
const fPF = (v) => (v == null ? '∞' : fmtN(v, 2));
const hm = (m) => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
const ago = (s) => (!ok(s) ? '—' : s < 90 ? `${Math.max(0, Math.round(s))} s` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${(s / 3600).toFixed(1)} h` : `${Math.round(s / 86400)} d`);
const dur = (s) => { if (!ok(s)) return '—'; const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return h ? `${h} h ${String(m).padStart(2, '0')} min` : `${m} min`; };
const WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const fDate = (d) => { if (!d) return '—'; const [y, m, dd] = String(d).slice(0, 10).split('-').map(Number); return `${MONTHS[m - 1].slice(0, 3)} ${dd}${y !== new Date().getFullYear() ? ', ' + y : ''}`; };
const card = (title, body, tools = '', extra = '') => `<div class="card nx-glass ${extra}"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</div>`;
const hero = (eyebrow, title, desc, side = '') => `<div class="nx-hero"><div><div class="nx-eyebrow">${eyebrow}</div><h2>${title}</h2>${desc ? `<p class="muted">${desc}</p>` : ''}</div>${side}</div>`;
const stat = (k, v, sub = '', c = '') => `<div class="nx-stat"><span>${k}</span><b class="${c}">${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const segH = (id, items, v) => `<div class="seg sm" id="${id}">${items.map(([k, l]) => `<button type="button" data-v="${esc(k)}" class="${k === v ? 'on' : ''}">${esc(l)}</button>`).join('')}</div>`;
const onSeg = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = (e) => { const b = e.target.closest('button[data-v]'); if (b) fn(b.dataset.v); }; };
const chip = (t, k = '') => `<span class="nx-chip ${k}">${t}</span>`;
const empty = (t, s = '') => `<div class="pc-empty"><b>${t}</b>${s ? `<span>${s}</span>` : ''}</div>`;
const src = (t) => `<p class="pc-src">${icon('info')}<span>${t}</span></p>`;
const meter = (f, k = '') => `<div class="pc-meter ${k}"><i style="width:${Math.max(0, Math.min(100, f * 100)).toFixed(1)}%"></i></div>`;
const isActive = (id) => document.getElementById('page-' + id)?.classList.contains('active');

// horizontal bars: [{label, v, sub, color}]; signed bars grow from the middle
function hbars(list, { fmt = kusd, signed = true } = {}) {
  if (!list.length) return empty('Nothing to show.');
  const mx = Math.max(1e-9, ...list.map((r) => Math.abs(r.v || 0)));
  return `<div class="pc-hb${signed ? ' sg' : ''}">${list.map((r) => {
    const w = Math.abs(r.v || 0) / mx * (signed ? 50 : 100), pos = (r.v || 0) >= 0, c = r.color || (pos ? 'var(--good)' : 'var(--bad)');
    return `<div class="r"><span class="l">${esc(r.label)}</span><span class="t"><i style="width:${w.toFixed(1)}%;${signed ? (pos ? 'left:50%' : `left:${(50 - w).toFixed(1)}%`) : 'left:0'};background:${c}"></i></span>
      <b class="${signed ? cls(r.v) : ''}">${fmt(r.v)}</b>${r.sub ? `<em>${esc(r.sub)}</em>` : ''}</div>`; }).join('')}</div>`;
}
// SVG scatter with a hover tooltip: pts [{x, y, color, tip}]
function scatter(el, pts, { h = 260, xlab = '', ylab = '', refY = null, xfmt = (v) => fmtN(v, 0), yfmt = (v) => fmtN(v, 0) } = {}) {
  if (!el) return;
  if (!pts.length) { el.innerHTML = empty('No trades in this span.'); return; }
  const W = Math.max(300, el.clientWidth || 600), H = h, L = 44, R = 12, T = 10, B = 34;
  let x0 = Math.min(...pts.map((p) => p.x)), x1 = Math.max(...pts.map((p) => p.x)), y0 = Math.min(...pts.map((p) => p.y), refY ?? Infinity), y1 = Math.max(...pts.map((p) => p.y), refY ?? -Infinity);
  const px_ = (x1 - x0) * 0.05 || 1, py = (y1 - y0) * 0.06 || 1; x0 -= px_; x1 += px_; y0 -= py; y1 += py;
  const X = (v) => L + (v - x0) / (x1 - x0) * (W - L - R), Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const tk = (a, b) => { const s = (b - a) / 4, m = Math.pow(10, Math.floor(Math.log10(s))), st = [1, 2, 2.5, 5, 10].map((q) => q * m).find((q) => q >= s) || s; const o = []; for (let v = Math.ceil(a / st) * st; v <= b; v += st) o.push(+v.toFixed(6)); return o; };
  el.innerHTML = `<div class="pc-sc" style="height:${H}px"><svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">
    ${tk(y0, y1).map((v) => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="nx-grid"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="nx-axis">${yfmt(v)}</text>`).join('')}
    ${tk(x0, x1).map((v) => `<text x="${X(v)}" y="${H - 18}" text-anchor="middle" class="nx-axis">${xfmt(v)}</text>`).join('')}
    ${refY != null ? `<line x1="${L}" x2="${W - R}" y1="${Y(refY)}" y2="${Y(refY)}" class="nx-zero"/>` : ''}
    <text x="${W - R}" y="${H - 3}" text-anchor="end" class="nx-axis">${esc(xlab)}</text><text x="${L}" y="${T + 2}" class="nx-axis" dx="4" dy="8">${esc(ylab)}</text>
    ${pts.map((p, i) => `<circle cx="${X(p.x).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="4.5" fill="${p.color}" fill-opacity=".72" stroke="${p.color}" stroke-opacity=".95" data-i="${i}"/>`).join('')}
  </svg><div class="nx-tip" hidden></div></div>`;
  const tip = el.querySelector('.nx-tip'), box = el.querySelector('.pc-sc');
  box.onmousemove = (e) => {
    const c = e.target.closest('circle[data-i]'); if (!c) { tip.hidden = true; return; }
    const r = box.getBoundingClientRect(); tip.innerHTML = pts[+c.dataset.i].tip || ''; tip.hidden = false;
    tip.style.left = Math.min(r.width - 200, Math.max(0, e.clientX - r.left + 12)) + 'px'; tip.style.top = Math.max(0, e.clientY - r.top - 10) + 'px';
  };
  box.onmouseleave = () => { tip.hidden = true; };
}

// P&L month grid (Mon-Fri): byDay Map(day -> {pnl, n, text}); returns html + the month's totals
function calGrid(byDay, month, today, scale = 2500) {
  const [Y, M] = month.split('-').map(Number), nd = new Date(Date.UTC(Y, M, 0)).getUTCDate();
  let cells = '', first = true, net = 0, n = 0, g = 0;
  for (let d = 1; d <= nd; d++) {
    const w = (new Date(Date.UTC(Y, M - 1, d)).getUTCDay() + 6) % 7; if (w > 4) continue;
    if (first) { cells += '<span class="e"></span>'.repeat(w); first = false; }
    const k = `${month}-${String(d).padStart(2, '0')}`, v = byDay.get(k), has = v && v.n;
    if (has) { net += v.pnl; n += v.n; if (v.pnl > 0) g++; }
    const a = has ? Math.min(1, Math.abs(v.pnl) / scale) : 0;
    const bg = has ? (v.pnl > 0 ? `color-mix(in srgb, var(--good) ${Math.round(14 + 52 * Math.sqrt(a))}%, transparent)` : v.pnl < 0 ? `color-mix(in srgb, var(--bad) ${Math.round(14 + 52 * Math.sqrt(a))}%, transparent)` : 'color-mix(in srgb, var(--ink) 12%, transparent)') : '';
    cells += `<button type="button" class="d${k === today ? ' now' : ''}${has ? '' : ' z'}" data-k="${k}" ${bg ? `style="background:${bg}"` : ''}><i>${d}</i>${has ? `<b>${kusd(v.pnl)}</b>` : ''}</button>`;
  }
  return { html: `<div class="pc-cal"><span class="h">Mon</span><span class="h">Tue</span><span class="h">Wed</span><span class="h">Thu</span><span class="h">Fri</span>${cells}</div>`, net, n, g };
}
const monKey = (day) => { const dt = new Date(day + 'T12:00:00Z'); return new Date(dt - ((dt.getUTCDay() + 6) % 7) * 864e5).toISOString().slice(0, 10); };

// ------------------------------------------------------------------ status header (Today)
const STAGES = [['levels', 'Levels'], ['sweep', 'Sweep'], ['inducement', 'Inducement'], ['cisd', '5m CISD'], ['limit', 'Limit'], ['cisd1m', '1m CISD'], ['trade', 'In trade'], ['done', 'Done']];
function stageRail(lit) {
  const i = lit?.stage === 'closed' ? -1 : +(lit?.i ?? 0);
  // the bot reports sweep + inducement + CISD together once the 5m CISD closed: a setup (limit) lights the first four
  return `<div class="pc-rail">${STAGES.map(([k, l], j) => `<span class="${j < i ? 'done' : j === i ? 'now' : ''}" title="${esc(l)}"><i></i><em>${esc(l)}</em></span>`).join('')}</div>`;
}
function feedAge(f, now) {
  const a1 = f.last_1m_t ? now - f.last_1m_t - 60 : null, a5 = f.last_5m_t ? now - f.last_5m_t - (f.tf === '1m' ? 60 : 300) : null;
  return { a1, a5 };
}
export async function renderStatus(force) {
  const el = $('#pcStatus'); if (!el) return;
  const s = await getStatus(force);
  if (!s || s.error) { el.className = 'pc-status lvl-bad'; el.innerHTML = `<div class="pc-st-main"><span class="pc-st-dot"></span><div><div class="pc-st-k">PC BOT</div><h2>NO ANSWER</h2><p>${esc(s?.error || '/api/next/pc/status failed')}</p></div></div>`; return; }
  const v = s.verdict || {}, h = s.health || {}, a = h.account || {}, f = h.feed || {}, p = h.poll || {}, lit = h.lit || {}, ec = s.eval_clock || {};
  const now = (s.t || Date.now() / 1000) + (Date.now() - D.stAt) / 1000;   // the bot's clock (ages stay right with a skewed PC clock)
  const { a1, a5 } = feedAge(f, now);
  const lvl = v.level || 'warn';
  const setups = s.setups_today || [];
  const last = setups[setups.length - 1];
  el.className = `pc-status lvl-${lvl}`;
  el.innerHTML = `<div class="pc-st-main"><span class="pc-st-dot"></span><div class="pc-st-txt">
        <div class="pc-st-k">PC bot · ${esc(a.name || a.adapter || 'paper')} · ${esc(a.label || '')}${h.running ? '' : ' · stopped'}</div>
        <h2>${esc(v.label || v.code || '—')}</h2><p>${esc(v.reason || '')}${s.model_state ? ` · ${esc(s.model_state)}` : ''}</p></div>
      <div class="pc-st-acts"><button type="button" class="btn ghost sm" data-goto="accounts">${icon('wallet')}<span>Accounts</span></button><button type="button" class="btn ghost sm" data-goto="evalhq">${icon('prop')}<span>Eval HQ</span></button></div></div>
    <div class="pc-st-grid">
      <div><span>Account</span><b>${esc(a.name || '—')}</b><em>${a.is_live ? 'LIVE account (your eval)' : a.label === 'SIM' ? 'Sim account: not your eval' : 'paper: no broker orders'}</em></div>
      <div class="${a.enabled === false || h.kill ? 'bad' : ''}"><span>Orders</span><b>${h.kill ? 'Kill switch ON' : a.enabled === false ? 'Disabled' : h.running ? 'Enabled' : 'Bot stopped'}</b><em>${esc(a.disabled || (h.nt?.connected === false ? 'NinjaTrader disconnected' : h.nt?.connected ? 'NinjaTrader connected' : a.adapter || ''))}</em></div>
      <div class="${f.stale || f.entries_blocked ? 'bad' : (a1 != null && a1 > 240 && f.market_open) ? 'warn' : ''}"><span>Feed · ${esc(f.used || f.source || '—')}${f.fallback ? ' (fallback)' : ''}</span><b>${a1 != null ? `1m ${ago(a1)} old` : a5 != null ? `5m ${ago(a5)} old` : 'no bars yet'}</b><em>${a5 != null && a1 != null ? `5m ${ago(a5)} old · ` : ''}${f.market_open === false ? 'market closed' : f.entries_blocked ? 'NEW ENTRIES BLOCKED' : f.stale ? 'stale' : 'fresh'}</em></div>
      <div class="${p.consecutive_errors ? 'warn' : ''}"><span>Last poll</span><b>${p.last_t ? ago(now - p.last_t) + ' ago' : 'never'}</b><em>${p.poll_ms != null ? `${p.poll_ms} ms · ` : ''}${p.errors ? `${p.errors} errors` : 'no errors'}${p.last_error ? ' · ' + esc(p.last_error) : ''}</em></div>
      <div><span>LIT stage</span><b>${esc((STAGES.find(([k]) => k === lit.stage) || [0, lit.stage === 'closed' ? 'Market closed' : '—'])[1])}</b><em>${lit.price ? 'NQ ' + px(lit.price) : ''}${s.rules?.monday ? ' · ' + esc(s.rules.monday) : ''}</em></div>
      <div><span>Setups today</span><b>${setups.length}</b><em>${last ? `${esc(last.side)} ${esc(last.level || '')} ${last.t ? '@ ' + etStr(last.t) : ''}${last.rr ? ` · ${fmtN(last.rr, 1)}R` : ''}` : (s.pending || []).length ? 'limit armed' : 'none yet'}</em></div>
      <div><span>Eval</span><b>${ec.session ? `Session ${ec.session} of ${ec.limit || 10}` : '—'}</b><em>${esc(ec.text || '')}</em></div>
    </div>${stageRail(lit)}`;
}

// ------------------------------------------------------------------ eval card + position (Accounts)
function evalCard(ev, acct) {
  if (!ev) return card('Eval', empty('No eval numbers.', 'live_model.json lit_sizing.eval_start sets the first session.'));
  const n = ev.sessions || 10, s = ev.session || 0;
  const dots = Array.from({ length: n }, (_, i) => `<i class="${i + 1 < s ? 'done' : i + 1 === s ? 'now' : ''}">${i + 1}</i>`).join('');
  const k = ev.status === 'passed' ? 'good' : ev.status === 'failed' ? 'bad' : '';
  return card(`${esc(acct.name || 'MFFU 50K Eval')} · ${esc(acct.plan || 'Builder 50K')}`, `
    <div class="pc-big"><b>${fmt$(ev.balance, 2)}</b><span class="${cls(ev.profit)}">${fmtS$(ev.profit, 2)} since the start${ev.prior ? ` (incl. ${fmtS$(ev.prior)} before ${fDate(ev.start)})` : ''}</span></div>
    <div class="pc-dots">${dots}</div><p class="muted small" style="margin:6px 0 14px">${esc(ev.clock_text || '')}</p>
    <div class="pc-prog"><div class="pc-prog-h"><span>To +${fmt$(3000)} (balance ${fmt$(ev.target_balance)})</span><b>${fmt$(ev.to_target)} to go</b></div>${meter(ev.progress, 'good')}</div>
    <div class="pc-prog"><div class="pc-prog-h"><span>Room above the trailing floor ${fmt$(ev.floor)}${ev.locked ? ' (locked)' : ''}</span><b>${fmt$(ev.room)}</b></div>${meter(ev.room / (ev.mll || 2000), ev.room < 600 ? 'bad' : ev.room < 1200 ? 'warn' : '')}</div>
    <div class="pc-prog"><div class="pc-prog-h"><span>Soft daily loss used today</span><b class="${ev.dll_used ? 'dn' : ''}">${fmt$(ev.dll_used)} of ${fmt$(ev.dll)}</b></div>${meter(ev.dll_used / (ev.dll || 1000), ev.dll_used > 700 ? 'bad' : 'warn')}</div>`,
  `${chip(esc(String(ev.status || 'open').toUpperCase()), k)}${chip(esc(acct.badge || ''), acct.badge === 'LIVE' ? 'good' : acct.badge === 'SIM' ? 'warn' : '')}`);
}
function posTrade(p, ac) {
  return { day: p.day, entry_t: +p.entry_t, side: p.side, dir: p.dir, entry: +p.entry, stop: +(p.stop0 ?? p.stop), target: +p.target, qty: p.qty,
    risk_usd: p.risk_usd, pnl: p.unrealized_usd || 0, exit: 'OPEN', id: 'pos_' + p.entry_t, target_label: p.target_label || '', be_t: p.be ? p.be_t : null };
}
function positionCard(ac) {
  const p = ac.position;
  if (!p) return card('Open position', empty('Flat: no routed position open.', esc(ac.model_state || 'The chart appears here while the bot is in a trade.')), '', 'pc-pos');
  if (!p.side) return card('Open position', empty(`Routed ${p.qty || ''} micros at ${p.entry_t ? etStr(p.entry_t) : '—'} ET`, esc(p.note || 'model view pending')), '', 'pc-pos');
  const moved = ok(p.stop) && ok(p.stop0) && Math.abs(p.stop - p.stop0) > 0.01;
  return card(`Open position · ${esc(p.side)} ${p.qty} MNQ`, `
    <div class="pc-pos-k">
      <div><span>Unrealized</span><b class="${cls(p.unrealized_usd)}">${fmtS$(p.unrealized_usd, 0)}</b><em>${p.unrealized_r_now != null ? fmtR(p.unrealized_r_now) : ''} · ${p.unrealized_pts != null ? fmtN(p.unrealized_pts, 2) + ' pts' : ''}</em></div>
      <div><span>Entry</span><b>${px(p.entry)}</b><em>${p.model_entry && Math.abs(p.model_entry - p.entry) > 0.01 ? 'model ' + px(p.model_entry) : etStr(p.entry_t) + ' ET'}</em></div>
      <div><span>Stop now</span><b class="dn">${px(p.stop)}</b><em>${p.be ? 'breakeven' : moved ? 'moved from ' + px(p.stop0) : `${fmtN(p.risk_pts, 2)} pts · ${fmt$(p.risk_usd)} at risk`}</em></div>
      <div><span>Target</span><b class="up">${px(p.target)}</b><em>${esc(p.target_label || '')}${p.target_usd ? ' · ' + fmtS$(p.target_usd) : ''}</em></div>
      <div><span>Breakeven</span><b>${p.be ? 'done' : px(p.be_trigger)}</b><em>${p.be ? 'stop at entry' : 'stop to entry at +1R'}</em></div>
      <div><span>Time in trade</span><b>${dur(p.time_in_s)}</b><em>flat by 15:55 ET</em></div>
    </div>
    <div class="nx-tcbox pc-tc" id="pcPosChart"></div>
    ${p.broker ? `<p class="muted small">Broker: ${esc(p.broker.instrument || '')} ${esc(p.broker.status || '')} · ${p.broker.filled ?? '—'} filled</p>` : ''}
    ${(p.size_why || []).length ? `<p class="muted small">Size: ${p.size_why.map(esc).join(' · ')}</p>` : ''}`,
  `<span class="muted small">NQ ${px(p.price)} · bot feed</span>`, 'pc-pos');
}
function mountPosition(ac) {
  const p = ac.position, box = $('#pcPosChart'); if (!p || !p.side || !box) return;
  if (!(ac.bars5 || []).length) { box.innerHTML = empty('No bars from the bot yet.'); return; }
  loadTC().then((TC) => {
    if (!box.isConnected) return;
    // the planned stop / target box; the stop now, breakeven trigger and $ sit in the panel above (levels would read as swept)
    const rec = TC.fromTrade(posTrade(p, ac), ac.bars5, { bars1: ac.bars1 });
    TC.mount(box, rec, { tf: ac.bars1 ? '1m' : '5m' });
  }).catch(() => { box.innerHTML = empty('Chart unavailable.'); });
}
function timelineCard(ac) {
  const rows = ac.orders || [];
  const KI = { entry: 'play', stop: 'scale', exit: 'stop', risk: 'warn', kill: 'power', error: 'warn' };
  return card(`Today’s orders · ${fDate(ac.today)}`, rows.length ? `<div class="pc-tl">${rows.map((r) => `
      <div class="pc-tl-r ${r.refused ? 'bad' : r.kind}"><span class="pc-tl-t mono">${r.t ? etStr(r.t) : '—'}</span><span class="pc-tl-i">${icon(KI[r.kind] || 'dot')}</span>
        <div><b>${esc({ entry: 'Entry', stop: 'Stop move', exit: 'Exit', risk: 'Risk guard', kill: 'Kill switch', error: 'Error' }[r.kind] || r.kind)}${r.refused ? ' · REFUSED' : ''}</b><span>${esc(r.text)}</span></div></div>`).join('')}</div>`
    : empty('No orders today.', 'Sent, filled, bracket, breakeven move and exit rows appear here as the bot routes them. Refused rows show in red.'),
  `<span class="muted small">${rows.filter((r) => r.refused).length ? rows.filter((r) => r.refused).length + ' refused' : 'ledger + risk log'}</span>`);
}

// ------------------------------------------------------------------ routed trades list
const F = { side: store.get('pc.f.side', 'all'), res: store.get('pc.f.res', 'all'), month: store.get('pc.f.month', 'all') };
function tradeRows(ac) {
  return (ac.trades || []).filter((t) => (F.side === 'all' || t.side === F.side.toUpperCase())
    && (F.res === 'all' || (F.res === 'win' ? t.pnl > 0 : F.res === 'loss' ? t.pnl < 0 : Math.abs(t.pnl || 0) < 1e-9 || t.exit === 'BE'))
    && (F.month === 'all' || String(t.day).startsWith(F.month)));
}
function tradesCard(ac) {
  const all = ac.trades || [], months = [...new Set(all.map((t) => String(t.day).slice(0, 7)))].sort().reverse();
  const rows = tradeRows(ac), net = sum(rows, (t) => +t.pnl || 0), won = rows.filter((t) => t.pnl > 0).length;
  return card('Routed trades', `
    <div class="pc-filters">${segH('pcFSide', [['all', 'All'], ['long', 'Long'], ['short', 'Short']], F.side)}${segH('pcFRes', [['all', 'All'], ['win', 'Won'], ['loss', 'Lost'], ['be', 'BE']], F.res)}
      <div class="seg sm pc-months" id="pcFMonth">${[['all', 'All months'], ...months.map((m) => [m, MONTHS[+m.slice(5) - 1].slice(0, 3) + ' ' + m.slice(2, 4)])].map(([k, l]) => `<button type="button" data-v="${k}" class="${k === F.month ? 'on' : ''}">${l}</button>`).join('')}</div></div>
    <p class="muted small" style="margin:8px 0 10px">${plural(rows.length, 'trade')} · ${won} won · <b class="${cls(net)}">${fmtS$(net)}</b>${rows.length ? ` · avg ${fmtR(sum(rows, (t) => +t.r || 0) / rows.length)}` : ''}</p>
    ${rows.length ? `<div class="pc-trades">${rows.map((t) => `
      <div class="pc-tr" data-et="${t.entry_t}"><button type="button" class="pc-tr-h">
        <span class="pc-tr-d"><b>${fDate(t.day)}</b><em>${t.entry_t ? etStr(t.entry_t) + ' ET' : ''}</em></span>
        <span class="pc-side ${t.side === 'LONG' ? 'up' : 'dn'}">${icon(t.side === 'LONG' ? 'long' : 'short')}${esc(t.side)}</span>
        <span class="pc-tr-m">${t.qty ?? '—'} micros · ${ok(t.risk_pts) ? fmtN(t.risk_pts, 2) + '-pt stop' : '—'}</span>
        <span class="pc-tr-x">${esc(t.exit || '')}</span><span class="pc-tr-r ${cls(t.r)}">${ok(t.r) ? fmtR(t.r) : '—'}</span><b class="pc-tr-p ${cls(t.pnl)}">${fmtS$(t.pnl)}</b>
        <span class="pc-tr-c">${icon('chart')}</span></button><div class="pc-tr-b" hidden></div></div>`).join('')}</div>`
      : empty(all.length ? 'No trade matches these filters.' : 'No routed trades yet.', all.length ? '' : 'Every trade the PC bot routes (and its LIT journal keeps) is listed here with its chart.')}`,
  `<span class="muted small">${all.length} routed · LIT journal + ledger</span>`);
}
function bindTrades(ac, rerender) {
  const set = (k, v) => { F[k] = v; store.set('pc.f.' + k, v); rerender(); };
  onSeg('pcFSide', (v) => set('side', v)); onSeg('pcFRes', (v) => set('res', v)); onSeg('pcFMonth', (v) => set('month', v));
  $$('.pc-tr').forEach((row) => {
    row.querySelector('.pc-tr-h').onclick = () => {
      const b = row.querySelector('.pc-tr-b'); b.hidden = !b.hidden; row.classList.toggle('open', !b.hidden);
      if (!b.hidden && !b.dataset.done) { b.dataset.done = '1'; b.innerHTML = '<div class="nx-tcbox pc-tc"><div class="muted small">Loading the chart…</div></div>'; tradeChart(+row.dataset.et, ac, b.firstElementChild); }
    };
  });
}
async function tradeChart(et, ac, box) {
  const t = (ac.trades || []).find((x) => x.entry_t === et);
  try {
    const TC = await loadTC();
    if (t?.chart) { const rec = await TC.load(t.chart, { base: '/api/next/tradechart/', ext: '' }); if (box.isConnected) TC.mount(box, rec, { tf: '1m' }); return; }
    const d = await api('/api/next/pc/trade/' + et);
    if (d.chart) { const rec = await TC.load(d.chart, { base: '/api/next/tradechart/', ext: '' }); if (box.isConnected) TC.mount(box, rec, { tf: '1m' }); return; }
    if (!(d.bars5 || []).length) { box.innerHTML = empty('No bars for this trade.', 'Neither the bot’s feed nor data/NQ_5m.csv covers it.'); return; }
    const tr = d.trade, rec = TC.fromTrade({ ...tr, exit_price: tr.exit_px }, d.bars5, { bars1: d.bars1 });
    if (box.isConnected) TC.mount(box, rec, { tf: d.bars1 ? '1m' : '5m' });
  } catch (e) { box.innerHTML = empty('Chart unavailable.', esc(e.message)); }
}

// ------------------------------------------------------------------ Accounts page
let acTimer = null;
async function showAccounts(force) {
  const el = $('#page-accounts'); if (!el) return;
  const ac = await getAccount(force);
  if (!isActive('accounts')) return;
  if (!ac || ac.error) { el.innerHTML = hero('Accounts', 'PC bot account', '') + card('Account', empty('No answer from the bot.', esc(ac?.error || ''))); return; }
  const a = ac.account || {}, ev = ac.eval, pn = ac.pnl || {}, sg = ac.stats || {};
  const sig = JSON.stringify([ac.t - (ac.t % 15), ac.position?.stop, (ac.orders || []).length, (ac.trades || []).length, F]);
  if (!force && el.dataset.sig === sig && el.querySelector('#pcPosChart, .pc-pos')) return;
  el.dataset.sig = sig;
  const open = $$('.pc-tr.open', el).map((r) => +r.dataset.et);
  el.innerHTML = hero(`Accounts · ${esc(a.firm || 'MFFU')} · ${esc(a.badge || '')}`, `${esc(a.name || 'MFFU 50K Eval')}${a.broker_account ? ` <span class="muted">· ${esc(a.broker_account)}</span>` : ''}`,
      `The PC bot’s own account from its live state (ledger, live_state.json, LIT journal). Read-only: this page never starts, arms or routes anything. ${a.running ? 'Bot running.' : 'Bot not running in this server.'}${a.kill ? ' KILL SWITCH ON.' : ''}`,
      `<div class="pc-hero-chips">${chip('mode ' + esc(ac.sizing?.mode || '—'))}${chip('eval from ' + fDate(ev?.start || ac.sizing?.eval_start))}</div>`)
    + `<div class="nx-stats">
        ${stat('Today', fmtS$(pn.today), ev ? `${fmt$(ev.dll_used)} of the ${fmt$(ev.dll)} daily loss used` : '', cls(pn.today))}
        ${stat('This week', fmtS$(pn.week), 'routed exits', cls(pn.week))}
        ${stat('Since eval start', fmtS$(pn.since_start), ev?.prior ? `incl. ${fmtS$(ev.prior)} before the bot` : '', cls(pn.since_start))}
        ${stat('Win rate', pct(sg.win_pct), `${sg.n || 0} trades · PF ${sg.n ? fPF(sg.pf) : '—'}`)}
        ${stat('Max drawdown', fmt$(sg.max_dd), sg.streak ? `streak ${sg.streak.n} ${sg.streak.kind}` : '', sg.max_dd < 0 ? 'dn' : '')}
      </div>
      <div class="pc-acc-top">${evalCard(ev, a)}${positionCard(ac)}</div>
      <div class="grid cols-2">${timelineCard(ac)}
        ${card('Equity · eval account', '<div id="pcEq"></div>', `<span class="muted small">${(ac.equity || []).length - 1} sessions with a trade</span>`)}</div>
      ${card('P&L calendar · routed', '<div id="pcCal"></div>', `<div class="pc-mnav" id="pcCalNav"><button class="nx-chipbtn" type="button" data-m="-1" aria-label="Previous month">${icon('left')}</button><button class="nx-chipbtn" type="button" data-m="1" aria-label="Next month">${icon('right')}</button></div>`)}
      ${tradesCard(ac)}`;
  mountPosition(ac);
  const eq = ac.equity || [];
  lineChart($('#pcEq'), eq.map(([d, v]) => ({ x: d === 'start' ? 'start' : fDate(d), y: v })), { h: 220, color: 'var(--accent)', ref: 3000 });
  // calendar of routed P&L per day
  // every routed trade by its trading day (also the days before eval_start)
  const by = new Map();
  for (const t of ac.trades || []) { if (!t.day) continue; const v = by.get(t.day) || { pnl: 0, n: 0 }; v.pnl += +t.pnl || 0; v.n += 1; by.set(t.day, v); }
  const months = [...new Set([...by.keys(), ac.today].map((k) => k.slice(0, 7)))].sort();
  let cm = store.get('pc.calm', ac.today.slice(0, 7)); if (!months.includes(cm)) cm = months[months.length - 1];
  const drawCal = () => { const g = calGrid(by, cm, ac.today, 1500); $('#pcCal').innerHTML = `<div class="pc-cal-h"><b>${MONTHS[+cm.slice(5) - 1]} ${cm.slice(0, 4)}</b><span class="muted small">${g.n ? `<b class="${cls(g.net)}">${fmtS$(g.net)}</b> · ${plural(g.n, 'day')} traded · ${g.g} green` : 'no routed trades this month'}</span></div>${g.html}`; };
  drawCal();
  $('#pcCalNav').onclick = (e) => { const b = e.target.closest('[data-m]'); if (!b) return; const i = months.indexOf(cm) + +b.dataset.m; if (i >= 0 && i < months.length) { cm = months[i]; store.set('pc.calm', cm); drawCal(); } };
  bindTrades(ac, () => showAccounts(true));
  for (const et of open) $(`.pc-tr[data-et="${et}"] .pc-tr-h`, el)?.click();
}

// ------------------------------------------------------------------ Eval HQ
const TW = { PV: 2, COMM: 1.9, SLIP: 0.25, DSLIP: 0.5 };
function twQty(stop, tgt, st) {           // engine/sizing.py two_week_qty, the phone's JS port
  const c = { need_buf: 1, room_f: 0.6, dll_cap: true, stop_at_target: true, ...(D.lx?.sizing?.two_week || {}) };
  const P = { target: 3000, dll: 1000, ...(D.lx?.plan || {}) }, maxq = D.lx?.sizing?.max_micros || 40;
  const need = P.target - st.profit;
  if (c.stop_at_target && need <= 0) return { q: 0, short: 'passed', risk: 0, win: 0 };
  let q = Math.max(1, Math.ceil(need * (c.need_buf || 1) / (tgt * TW.PV - TW.COMM) - 1e-9)), short = 'need';
  const caps = [];
  if (c.room_f && ok(st.room)) caps.push([Math.floor(c.room_f * Math.max(0, st.room) / (stop * TW.PV)), `${Math.round(c.room_f * 100)}% room`]);
  if (c.dll_cap) caps.push([Math.floor(Math.max(0, P.dll + (st.cum || 0)) / ((stop + TW.DSLIP) * TW.PV + TW.COMM)), 'daily loss']);
  for (const [cap, sh] of caps) if (cap < q) { q = Math.max(1, cap); short = sh; }
  if (q > maxq) { q = maxq; short = `max ${maxq}`; }
  return { q, short, risk: q * ((stop + TW.SLIP) * TW.PV + TW.COMM), win: q * (tgt * TW.PV - TW.COMM) };
}
const xRows = () => { const x = D.x; if (!x?.trades) return []; const c = x.tcols; return x.trades.map((r) => Object.fromEntries(c.map((k, i) => [k, r[i]]))); };
const inSpan = (sp, d) => (sp === '2026' ? d >= '2026' : sp === 'H1' ? d >= '2026' && d <= '2026-06-30' : sp === 'H2' ? d >= '2026-07-01' : d < '2026');
async function showEvalHQ() {
  const el = $('#page-evalhq'); if (!el) return;
  await Promise.all([getStatic(), getAccount()]);
  if (!isActive('evalhq')) return;
  const ac = D.ac || {}, ev = ac.eval || {}, P = { start: 50000, target: 3000, mll: 2000, dll: 1000, lock_at: 50100, ...(D.lx?.plan || {}) };
  const profit = ok(ev.profit) ? +ev.profit : -100, toGo = Math.max(0, P.target - profit), room = ok(ev.room) ? +ev.room : P.mll + profit;
  const limit = ev.sessions || 10, sess = ev.session || null, left = sess ? Math.max(0, limit - sess + 1) : null;
  const cum = +(ev.today || 0), traded = (ac.orders || []).some((r) => r.kind === 'entry' && !r.refused);
  const t26 = xRows().filter((t) => t.day >= '2026');
  const ty = { stop: med(t26.map((t) => t.risk_pts)) || 46, tgt: med(t26.filter((t) => ok(t.rr)).map((t) => t.rr * t.risk_pts)) || 230 };
  const next = traded ? { profit: profit + cum, cum: 0, room } : { profit, cum, room };
  const stops = [...new Set([15, 25, 35, Math.round(ty.stop), 60, 80])].sort((a, b) => a - b);
  const tbl = stops.map((s) => { const tg = Math.min(8 * s, Math.max(1.5 * s, ty.tgt)); return { s, tg, ...twQty(s, tg, next), typ: s === Math.round(ty.stop) }; });
  const tz = tbl.find((r) => r.typ), tw = D.x?.two_week, x = D.x || {};
  const ODDS = tw?.eval ? [['H2', 'H2 starts · the check (quote this)'], ['H1', 'H1 starts · picked on'], ['2026', 'All 2026 starts'], ['mc_H2', 'Monte Carlo · H2 days'], ['mc_H1', 'Monte Carlo · H1 days'], ['2021-25', '2021-25 · reference (5m bars)']].filter(([k]) => tw.eval[k]) : [];
  const dots = Array.from({ length: limit }, (_, i) => `<i class="${sess && i + 1 < sess ? 'done' : i + 1 === sess ? 'now' : ''}">${i + 1}</i>`).join('');
  const perSess = left ? toGo / left : null, h2 = tw?.eval?.H2;
  el.innerHTML = hero(`Eval HQ · MFFU Builder 50K · ${esc(ac.account?.badge || 'PAPER')} · sizing ${esc(ac.sizing?.mode || '—')}`, ev.status === 'passed' ? 'Eval passed' : `${fmt$(toGo)} to pass${left != null ? ` · ${plural(left, 'session')} left` : ''}`,
      'The owner’s rule: an eval is decided within 2 weeks (10 sessions), passed within 3 (15). Balance from the PC bot’s routed P&L since eval_start, plus the −$100 the eval had before the bot.')
    + `<div class="grid cols-2">${card('Pass path', `<div class="pc-big"><b>${fmt$(ev.balance ?? P.start + profit, 2)}</b><span class="${cls(profit)}">${fmtS$(profit, 2)} since the start (${fDate(ev.start)})</span></div>
        <div class="pc-dots">${dots}</div><p class="muted small" style="margin:6px 0 12px">${esc(ev.clock_text || '')} · no reset: after session 10 it keeps going in ${esc(ac.sizing?.after_mode || 'safe_eval')}</p>
        <div class="pc-prog"><div class="pc-prog-h"><span>To the +${fmt$(P.target)} target</span><b>${fmt$(toGo)} to go</b></div>${meter(profit / P.target, 'good')}</div>
        <div class="pc-prog"><div class="pc-prog-h"><span>Room above the floor ${fmt$(ev.floor)}${ev.locked ? ' (locked)' : ''}</span><b>${fmt$(room)}</b></div>${meter(room / P.mll)}</div>`, chip(esc(String(ev.status || 'open').toUpperCase()), ev.status === 'passed' ? 'good' : ev.status === 'failed' ? 'bad' : ''))}
      <div class="nx-stats pc-hq-stats">${stat('Needed / session', perSess != null ? fmt$(perSess) : '—', left != null ? `${fmt$(toGo)} over ${plural(left, 'session')}` : 'eval clock missing')}
        ${stat('Today', fmtS$(cum), traded ? 'traded (1 a day)' : 'no trade yet', cls(cum))}
        ${stat('Next winner', tz ? (tz.win >= toGo ? 'Passes' : fmtS$(tz.win)) : '—', tz ? `${tz.q} micros · ${tz.s}-pt stop · ${Math.round(tz.tg)}-pt target` : '', tz && tz.win >= toGo ? 'up' : '')}
        ${stat('Next full stop', tz ? fmt$(-tz.risk) : '—', tz ? `${pct(tz.risk / Math.max(1, room) * 100, 0)} of the room` : '', 'dn')}</div></div>`
    + card(`One winner passes · ${traded ? 'the next session' : 'the next trade'}`, `<div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Stop</th><th>Micros</th><th>Full stop</th><th>If it hits</th></tr></thead><tbody>
        ${tbl.map((r) => `<tr class="${r.typ ? 'on' : ''}"><td><b>${r.s} pts</b><span class="muted small"> ${Math.round(r.tg)} pts · ${fmtN(r.tg / r.s, 1)}R${r.typ ? ' · 2026 median' : ''}</span></td><td>${r.q} <span class="muted small">${esc(r.short)}</span></td>
          <td class="dn">${fmt$(-r.risk)}</td><td class="${r.win >= toGo ? 'up' : ''}">${fmtS$(r.win)} <span class="muted small">${r.win >= toGo ? 'passes' : fmt$(toGo - r.win) + ' left'}</span></td></tr>`).join('')}</tbody></table></div>
        <p class="muted small">Size follows the stop: the room cap (60% of ${fmt$(room)}) and the $1,000 soft daily loss shrink the micros as the stop grows, so a wide-stop winner may not pass in one go. Costs in: $1.90 a micro round trip, 1 tick of stop slippage.</p>`, '<span class="muted small">two_week sizing · from the balance now</span>')
    + (ODDS.length ? card('Odds of deciding in 2 weeks · live sizing', `<div class="pc-odds">${ODDS.map(([k, lab]) => { const o = tw.eval[k]; return `<div class="o"><div class="h"><span>${lab}</span><b>${pct(o.p10)} pass</b></div>
          <div class="bar"><i class="p" style="width:${o.p10}%"></i><i class="f" style="width:${o.f10}%"></i><i class="u" style="width:${Math.max(0, 100 - o.p10 - o.f10)}%"></i></div>
          <div class="muted small"><span class="dn">${pct(o.f10)} fail</span> · ${pct(o.o10)} still open after 10 · ${pct(o.p20)} pass in 20 · median ${fmtN(o.pass_med, 0)} sessions${ok(o.cost) ? ` · ${fmt$(o.cost)} per 2-week pass` : ''}</div></div>`; }).join('')}</div>
        <p class="muted small">Green = passed within 10 sessions, red = failed (trailing floor hit), grey = still open (it keeps going, no reset). $ per 2-week pass = $91.80 per eval ÷ the 2-week pass rate.${h2 ? ` Worst day ${fmt$(h2.worst_day)}, most at risk on one trade ${fmt$(h2.max_risk)} (H2).` : ''}</p>
        ${x.eventual ? `<div class="nx-kv sm" style="margin-top:12px">${['H2', 'MC H2', 'H1', 'MC H1'].filter((k) => x.eventual[k]).map((k) => `<div><span>Eventual pass · ${k}</span><b>${pct(x.eventual[k].pass)} <small class="muted">/ ${pct(x.eventual[k].fail)} fail</small></b></div>`).join('')}</div>` : ''}
        ${tw.money ? `<div class="nx-kv sm" style="margin-top:12px">${[['2026', '2026'], ['2021-25', '2021-25 ref']].filter(([k]) => tw.money[k]?.net != null).map(([k, l]) => { const m = tw.money[k]; return `<div><span>Back-to-back evals · ${l}</span><b class="${cls(m.net)}">${kusd(m.net)} <small class="muted">${kusd(m.per_month)}/mo · PF ${fPF(m.pf)}</small></b></div>`; }).join('')}</div>` : ''}
        ${src(esc(x.sources?.two_week || ''))}`, `<span class="muted small">run ${esc(tw.run)} · backtest</span>`) : card('Odds', empty('No two-week odds.', 'research/runs/lit_2wk_rec.json is missing.')))
    + (x.mc_normal?.prob ? card('For comparison · normal sizing', `<div class="nx-kv sm">${[['pass_2w', 'Pass in 2 wk'], ['fail_2w', 'Fail in 2 wk'], ['pass_4w', 'Pass in 4 wk'], ['pass_60', 'Pass in 60 sessions']].map(([k, l]) => `<div><span>${l}</span><b>${pct(x.mc_normal.prob[k])}</b></div>`).join('')}
        <div><span>Median sessions to pass</span><b>${fmtN(x.mc_normal.prob.pass_days_median, 0)}</b></div></div><p class="muted small">The plain LIT size ($800 up to a 20-pt stop) decides far fewer evals in 2 weeks: that is why the eval runs in two_week mode.</p>`, `<span class="muted small">Monte Carlo · ${esc(x.mc_normal.built || '')}</span>`) : '')
    + `<div class="pc-links">${[['accounts', 'wallet', 'Account & position'], ['litcockpit', 'prop', 'Eval cockpit'], ['evals', 'evals', 'Monte Carlo'], ['pnlcal', 'calendar', 'P&L calendar'], ['edge', 'heat', 'Edge'], ['mffurules', 'rules', 'MFFU rules']].map(([g, i, l]) => `<button type="button" class="nx-chipbtn" data-goto="${g}">${icon(i)}<span>${l}</span></button>`).join('')}</div>`;
}

// ------------------------------------------------------------------ Edge
const EXIT_C = { TARGET: 'var(--good)', STOP: 'var(--bad)', BE: 'var(--ink-2)', TIME: 'var(--warn)' };
const SPANS = [['2026', '2026'], ['H1', 'H1 · picked'], ['H2', 'H2 · check'], ['2021-25', '2021-25 · ref']];
const PERIOD_OF = { '2026': '2026 YTD', H1: '2026 H1 (picked on)', H2: '2026 H2 (check)', '2021-25': '2021-25 (reference)' };
function kp(t) { const won = sum(t.filter((x) => x.pnl > 0), (x) => x.pnl), lost = -sum(t.filter((x) => x.pnl < 0), (x) => x.pnl);
  return { n: t.length, win: t.length ? 100 * t.filter((x) => x.pnl > 0).length / t.length : null, avg: t.length ? sum(t, (x) => x.r) / t.length : null, netR: sum(t, (x) => x.r), net: sum(t, (x) => x.pnl), pf: lost > 0 ? won / lost : null }; }
async function showEdge() {
  const el = $('#page-edge'); if (!el) return;
  await getStatic(); if (!isActive('edge')) return;
  if (!D.x?.trades) { el.innerHTML = hero('Edge', 'Where LIT makes its money', '') + card('Edge', empty('No trade data.', 'research/lab/backtest_live.json is missing: python tools/export_backtest.py')); return; }
  const sp = store.get('pc.edge.span', '2026'), t = xRows().filter((q) => inSpan(sp, q.day)), K = kp(t), Pd = (D.rs?.periods || {})[PERIOD_OF[sp]] || {};
  const mo = Pd.from && Pd.to ? Math.max(1, (Date.parse(Pd.to) - Date.parse(Pd.from)) / (30.44 * 864e5)) : 1;
  const bins = [['Full stop', (r) => r <= -0.9], ['Part loss', (r) => r > -0.9 && r < -0.1], ['Breakeven', (r) => r >= -0.1 && r <= 0.1], ['0–1R', (r) => r > 0.1 && r <= 1], ['1–2R', (r) => r > 1 && r <= 2], ['2–4R', (r) => r > 2 && r <= 4], ['4–6R', (r) => r > 4 && r <= 6], ['6R+', (r) => r > 6]];
  const hist = bins.map(([l, f]) => { const g = t.filter((q) => f(q.r)); return { label: l, v: g.length, sub: `${kusd(sum(g, (q) => q.pnl))} · ${pct(t.length ? g.length / t.length * 100 : 0, 0)}`, color: l === 'Breakeven' ? 'var(--ink-2)' : /stop|loss/i.test(l) ? 'var(--bad)' : 'var(--good)' }; });
  const hrs = []; for (let h = 2; h <= 15; h++) { const g = t.filter((q) => Math.floor(q.min / 60) === h); if (g.length) hrs.push({ label: `${String(h).padStart(2, '0')}:00`, v: sum(g, (q) => q.pnl), sub: `${g.length} · ${fmtR(sum(g, (q) => q.r) / g.length)}` }); }
  const wds = [0, 1, 2, 3, 4].map((w) => { const g = t.filter((q) => q.wd === w); return { label: WD[w], v: sum(g, (q) => q.pnl), sub: g.length ? `${g.length} · ${fmtR(sum(g, (q) => q.r) / g.length)}` : '0' }; });
  const sb = [[0, 20], [20, 30], [30, 45], [45, 60], [60, 999]].map(([a, b]) => { const g = t.filter((q) => q.risk_pts > a && q.risk_pts <= b); return { a, b, g, k: kp(g), qty: med(g.map((q) => q.qty)) }; }).filter((r) => r.g.length);
  const ex = ['TARGET', 'STOP', 'BE', 'TIME'].map((e) => { const g = t.filter((q) => q.exit === e); return { label: e === 'BE' ? 'Breakeven' : e === 'TIME' ? 'Time (15:55)' : e[0] + e.slice(1).toLowerCase(), v: sum(g, (q) => q.pnl), sub: `${g.length} · ${fmtR(g.length ? sum(g, (q) => q.r) / g.length : 0)}` }; });
  const ls = [[1, 'Long'], [-1, 'Short']].map(([d, l]) => { const g = t.filter((q) => q.dir === d), k = kp(g); return { label: l, v: k.net, sub: `${g.length} · ${pct(k.win || 0, 0)} won · PF ${fPF(k.pf)}` }; });
  const lv = (D.x.levels || {})[sp] || [];
  el.innerHTML = hero(`Edge · LIT backtest · ${esc((SPANS.find((s) => s[0] === sp) || [])[1])}`, 'Where LIT makes its money', 'Backtest trades with the live rules at the normal size ($800 up to a 20-pt stop), costs in. 2026 is how LIT is judged: picked on H1 (Jan–Jun), checked on H2 (Jul–Oct); 2021-25 is a reference on 5m bars only.', segH('pcEdgeSpan', SPANS, sp))
    + `<div class="nx-stats">${stat('Trades', K.n, Pd.per_week ? `${fmtN(Pd.per_week, 2)} a week · ${Pd.weeks_2plus_pct ?? '—'}% weeks with 2+` : '')}${stat('Won', pct(K.win), `avg ${fmtR(K.avg)} a trade`)}
      ${stat('Net', kusd(K.net), `${kusd(K.net / mo)} a month · ${fmtR(K.netR)}`, cls(K.net))}${stat('Profit factor', fPF(K.pf), Pd.max_dd != null ? `max DD ${kusd(Pd.max_dd)}` : '')}</div>
    <div class="grid cols-2">${card('R multiples', hbars(hist, { fmt: (v) => String(v), signed: false }), '<span class="muted small">trades per result · $ in each</span>')}
      ${card('How each trade ended', hbars(ex) + '<div style="height:12px"></div>' + hbars(ls), '<span class="muted small">net $ · trades · avg R</span>')}</div>
    <div class="grid cols-2">${card('Best move vs worst move (MFE vs MAE)', `<div id="pcMM"></div><div class="pc-leg">${Object.entries(EXIT_C).map(([k, c]) => `<span><i style="background:${c}"></i>${k === 'BE' ? 'Breakeven' : k[0] + k.slice(1).toLowerCase()}</span>`).join('')}</div>`, '<span class="muted small">R · one dot a trade</span>')}
      ${card('Stop size vs result', `<div id="pcSR"></div>`, '<span class="muted small">stop in points · R</span>')}</div>
    ${card('Stop buckets', `<div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Stop</th><th>Trades</th><th>Won</th><th>Avg R</th><th>Net</th><th>Micros</th></tr></thead><tbody>
      ${sb.map((r) => `<tr><td>${r.b > 900 ? `${r.a}+ pts` : `${r.a}–${r.b} pts`}</td><td>${r.k.n}</td><td>${pct(r.k.win, 0)}</td><td class="${cls(r.k.avg)}">${fmtR(r.k.avg)}</td><td class="${cls(r.k.net)}">${kusd(r.k.net)}</td><td>${fmtN(r.qty, 0)}</td></tr>`).join('')}</tbody></table></div>
      <p class="muted small">Wide stop, fewer micros: size follows the stop, so a wide-stop loss costs about the same $ as a tight one.</p>`)}
    <div class="grid cols-2">${card('Entry hour (ET)', hbars(hrs), '<span class="muted small">net $ · trades · avg R</span>')}${card('Weekday', hbars(wds) + '<p class="muted small">Most LIT trades enter 02:00–08:00 ET: the PC and NinjaTrader must run from about 01:55 ET.</p>', '<span class="muted small">net $ · trades · avg R</span>')}</div>
    ${card('Which levels pay', lv.length ? `<div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Level swept</th><th>Trades</th><th>Won</th><th>Avg R</th><th>Net</th><th>PF</th></tr></thead><tbody>
      ${lv.map((r) => `<tr><td>${esc(r.name)}${r.n < 10 ? ' <span class="muted small">thin</span>' : ''}</td><td>${r.n}</td><td>${pct(r.win, 0)}</td><td class="${cls(r.avg_r)}">${fmtR(r.avg_r)}</td><td class="${cls(r.net)}">${kusd(r.net)}</td><td>${fPF(r.pf)}</td></tr>`).join('')}</tbody></table></div>
      <p class="muted small">A sweep often takes 2 levels at once, so a trade counts once for each level it took.</p>` : empty('No level data.'))}
    ${src(esc(D.x.sources?.trades || ''))}`;
  onSeg('pcEdgeSpan', (v) => { store.set('pc.edge.span', v); showEdge(); });
  const tip = (q) => `<b>${fDate(q.day)} ${hm(q.min)} · ${q.dir > 0 ? 'Long' : 'Short'}</b><br>${esc(q.exit)} ${fmtR(q.r)} · ${fmtS$(q.pnl)}<br>stop ${fmtN(q.risk_pts, 2)} pts · ${q.qty} micros`;
  scatter($('#pcMM'), t.filter((q) => ok(q.mae) && ok(q.mfe)).map((q) => ({ x: Math.min(1.3, +q.mae), y: Math.min(9, +q.mfe), color: EXIT_C[q.exit] || 'var(--ink-2)', tip: tip(q) })), { h: 280, xlab: 'MAE: worst point against (R)', ylab: 'MFE (R)', refY: 1, xfmt: (v) => fmtN(v, 1) });
  scatter($('#pcSR'), t.map((q) => ({ x: +q.risk_pts, y: Math.max(-1.3, Math.min(8.5, +q.r)), color: EXIT_C[q.exit] || 'var(--ink-2)', tip: tip(q) })), { h: 280, xlab: 'stop (points)', ylab: 'R', refY: 0 });
}

// ------------------------------------------------------------------ P&L calendar
async function showPnlCal() {
  const el = $('#page-pnlcal'); if (!el) return;
  await Promise.all([getStatic(), getAccount()]); if (!isActive('pnlcal')) return;
  const srcK = store.get('pc.cal.src', 'bt'), ac = D.ac || {}, today = ac.today || new Date().toISOString().slice(0, 10);
  const btDays = (D.rs?.days || []).filter((d) => d.trades > 0);
  const byDay = new Map(srcK === 'pc' ? (ac.days || []).map(([d, v]) => [d, { pnl: v, n: (ac.trades || []).filter((t) => t.day === d).length || 1 }]) : btDays.map((d) => [d.date, { pnl: d.pnl, n: d.trades }]));
  const keys = [...byDay.keys()].sort(), months = [...new Set(keys.map((k) => k.slice(0, 7)))];
  let cur = store.get('pc.cal.m.' + srcK, null); if (!cur || !months.includes(cur)) cur = months[months.length - 1] || today.slice(0, 7);
  const yr = cur.slice(0, 4), g = calGrid(byDay, cur, today, srcK === 'pc' ? 1500 : 2500);
  const yk = keys.filter((k) => k.startsWith(yr)), seq = yk.map((k) => byDay.get(k).pnl);
  let bw = 0, bl = 0, cw = 0, cl = 0; for (const v of seq) { if (v > 0) { cw++; cl = 0; } else if (v < 0) { cl++; cw = 0; } bw = Math.max(bw, cw); bl = Math.max(bl, cl); }
  const lastV = seq.length ? seq[seq.length - 1] : 0, best = yk.reduce((b, k) => (!b || byDay.get(k).pnl > byDay.get(b).pnl ? k : b), null), worst = yk.reduce((b, k) => (!b || byDay.get(k).pnl < byDay.get(b).pnl ? k : b), null);
  const weeks = {}; for (const k of yk) { const w = weeks[monKey(k)] || (weeks[monKey(k)] = 0); weeks[monKey(k)] = w + byDay.get(k).pnl; }
  const wv = Object.values(weeks), green = seq.filter((v) => v > 0).length;
  const H2 = (D.rs?.periods || {})['2026 H2 (check)'] || {}, mk = monKey(today), fk = new Date(Date.parse(mk + 'T12:00:00Z') + 4 * 864e5).toISOString().slice(0, 10);
  const wk = (ac.trades || []).filter((t) => t.day >= mk && t.day <= fk), wkR = sum(wk, (t) => +t.r || 0), wkUsd = sum(wk, (t) => +t.pnl || 0);
  const h2t = xRows().filter((q) => q.day >= '2026-07-01'), expT = H2.per_week || null, expR = h2t.length && expT ? sum(h2t, (q) => q.r) / h2t.length * expT : null;
  el.innerHTML = hero(`P&L calendar · ${srcK === 'pc' ? 'PC bot (routed)' : 'LIT backtest'}`, `${MONTHS[+cur.slice(5) - 1]} ${cur.slice(0, 4)}`, srcK === 'pc' ? 'Every routed exit of the PC bot by trading day, from eval_start.' : 'Every replay trading day: live rules, normal size ($800 up to a 20-pt stop), costs in.', segH('pcCalSrc', [['bt', 'Backtest'], ['pc', 'PC bot']], srcK))
    + card(`This week vs the backtest · ${fDate(mk)} – ${fDate(fk)}`, `<div class="pc-wk"><div><span>Trades routed</span><b>${wk.length} <small class="muted">of ~${fmtN(expT, 1)} expected</small></b>${meter(wk.length / 4)}<em class="muted small">owner’s band: 2–4 a week</em></div>
        <div><span>Result</span><b class="${cls(wkR)}">${fmtR(wkR)} <small class="${cls(wkUsd)}">${fmtS$(wkUsd)}</small></b><em class="muted small">backtest H2 average week ${expR != null ? fmtR(expR) : '—'} at normal size</em></div></div>`)
    + card(`${MONTHS[+cur.slice(5) - 1]} ${cur.slice(0, 4)}`, `${g.html}<div class="pc-cal-i muted small" id="pcCalI">${g.n ? `<b class="${cls(g.net)}">${fmtS$(g.net)}</b> this month · ${plural(g.n, 'trade')} · ${g.g} green days. Click a day.` : 'No trades this month.'}</div>`,
      `<div class="pc-mnav" id="pcCalNav2"><button class="nx-chipbtn" type="button" data-m="-1" aria-label="Previous month">${icon('left')}</button><button class="nx-chipbtn" type="button" data-m="1" aria-label="Next month">${icon('right')}</button></div>`)
    + card(`Streaks · ${yr}`, `<div class="nx-kv sm">
        <div><span>Green days</span><b>${seq.length ? pct(green / seq.length * 100, 0) : '—'} <small class="muted">${green} of ${seq.length}</small></b></div>
        <div><span>Now</span><b>${lastV > 0 ? cw + ' green' : lastV < 0 ? cl + ' red' : '—'}</b></div><div><span>Longest green run</span><b class="up">${bw} days</b></div><div><span>Longest red run</span><b class="dn">${bl} days</b></div>
        <div><span>Best day</span><b class="${best ? cls(byDay.get(best).pnl) : ''}">${best ? fmtS$(byDay.get(best).pnl) : '—'} <small class="muted">${best ? fDate(best) : ''}</small></b></div>
        <div><span>Worst day</span><b class="${worst ? cls(byDay.get(worst).pnl) : ''}">${worst ? fmtS$(byDay.get(worst).pnl) : '—'} <small class="muted">${worst ? fDate(worst) : ''}</small></b></div>
        <div><span>Green weeks</span><b>${wv.length ? pct(wv.filter((w) => w > 0).length / wv.length * 100, 0) : '—'}</b></div><div><span>Year so far</span><b class="${cls(sum(seq))}">${kusd(sum(seq))}</b></div></div>
      <p class="muted small">A red run of several days is part of LIT: about 1 trade in 4 wins, and the winners are large.</p>`, '<span class="muted small">trading days with a trade</span>');
  onSeg('pcCalSrc', (v) => { store.set('pc.cal.src', v); showPnlCal(); });
  $('#pcCalNav2').onclick = (e) => { const b = e.target.closest('[data-m]'); if (!b) return; const i = months.indexOf(cur) + +b.dataset.m; if (i >= 0 && i < months.length) { store.set('pc.cal.m.' + srcK, months[i]); showPnlCal(); } };
  const bt = new Map(xRows().map((q) => [q.day, q]));
  $('.pc-cal', el).onclick = (e) => {
    const c = e.target.closest('.d[data-k]'); if (!c) return; $$('.pc-cal .d.on', el).forEach((q) => q.classList.remove('on')); c.classList.add('on');
    const k = c.dataset.k, v = byDay.get(k), info = $('#pcCalI');
    if (!v || !v.n) { info.innerHTML = `<b>${fDate(k)}</b> · no trade`; return; }
    const q = srcK === 'bt' ? bt.get(k) : null, pr = srcK === 'pc' ? (ac.trades || []).filter((t) => t.day === k) : [];
    info.innerHTML = `<b>${fDate(k)}</b> · <b class="${cls(v.pnl)}">${fmtS$(v.pnl)}</b> · ${plural(v.n, 'trade')}` + (q ? ` · ${q.dir > 0 ? 'Long' : 'Short'} ${hm(q.min)} ET · ${esc(q.exit)} ${fmtR(q.r)} · ${fmtN(q.risk_pts, 2)}-pt stop, ${q.qty} micros` : '')
      + pr.map((t) => ` · ${esc(t.side)} ${t.entry_t ? etStr(t.entry_t) : ''} · ${esc(t.exit || '')} ${fmtR(t.r)} · ${t.qty} micros`).join('');
  };
}

// ------------------------------------------------------------------ MFFU rules
const RULE_NAMES = { price: 'Eval price', activation_fee: 'Activation fee', renewal: 'Renewal', reset_fee: 'Reset fee', profit_target: 'Profit target', max_loss: 'Max loss (trailing)', mll: 'Max loss (trailing)', daily_loss: 'Daily loss', dll: 'Daily loss', min_days: 'Minimum trading days', consistency: 'Consistency', max_contracts: 'Max contracts', news: 'News trading', close_time: 'Close time', payout: 'Payout' };
function fmtVal(v) {
  if (v == null) return '<span class="muted">not found</span>';
  if (typeof v === 'number') return Math.abs(v) >= 50 ? fmt$(v, v % 1 ? 2 : 0) : String(v);
  if (typeof v === 'string' || typeof v === 'boolean') return esc(String(v));
  if (Array.isArray(v)) return v.map(fmtVal).join(', ');
  return Object.entries(v).map(([k, x]) => `<span class="pc-rv"><i>${esc(k.replace(/_/g, ' '))}</i> ${fmtVal(x)}</span>`).join('');
}
async function showRules() {
  const el = $('#page-mffurules'); if (!el) return;
  await getStatic(); if (!isActive('mffurules')) return;
  const m = D.x?.mffu;
  if (!m) { el.innerHTML = hero('MFFU rules', 'Builder 50K rulebook', '') + card('Rules', empty('No rulebook.', 'research/lit/mffu_rules.json is missing.')); return; }
  const ST = { confirmed: 'good', conflict: 'warn', unconfirmed: '' };
  const STAGE = { eval: 'Evaluation', sim_funded: 'Sim funded', live: 'Live funded' };
  el.innerHTML = hero(`MFFU · ${esc(m.built || '')}`, esc(m.title || 'MFFU rulebook'), 'The Builder 50K rules with how sure each one is, and how LIT fits them. Re-check on MFFU’s own pages before the first live payout.')
    + card('How LIT fits the eval', `<div class="nx-kv one">
        <div><span>Profit target</span><b>+$3,000 · the two_week sizing aims to pass it with one winner</b></div>
        <div><span>Trailing max loss (end of day)</span><b>$2,000 · locks at $50,100 · size capped at 60% of the room</b></div>
        <div><span>Soft daily loss</span><b>$1,000 · a full stop never exceeds it</b></div>
        <div><span>Max size</span><b>40 micros (bot cap)</b></div><div><span>Trades a day</span><b>1 (LIT rule)</b></div>
        <div><span>Bot flat by</span><b>15:55 ET (MFFU closes 16:10 ET; CME half-days 5 min before the halt)</b></div>
        <div><span>Owner’s price</span><b>$91.80 one-time (discount code), $0 activation, no reset</b></div></div>`)
    + (m.stages || []).map((s) => card(STAGE[s.stage] || esc(s.stage), `<div class="pc-rules">${(s.items || []).map((it) => `<div class="pc-rule"><div class="pc-rule-h"><b>${esc(RULE_NAMES[it.k] || it.k.replace(/_/g, ' '))}</b>${chip(esc(it.status || '?'), ST[it.status] ?? '')}</div>
        <div class="pc-rule-v">${fmtVal(it.value)}</div>${it.note ? `<p class="muted small">${esc(it.note)}</p>` : ''}${it.checked ? `<em class="muted small">checked ${esc(it.checked)}</em>` : ''}</div>`).join('')}</div>`, `<span class="muted small">${(s.items || []).length} rules</span>`)).join('')
    + src(esc(m.method || ''));
}

// ------------------------------------------------------------------ wiring
export const accounts = { show: () => { showAccounts(true); clearInterval(acTimer); acTimer = setInterval(() => { if (!document.hidden && isActive('accounts')) showAccounts(); }, 15000); } };
export const evalhq = { show: showEvalHQ };
export const edge = { show: showEdge };
export const pnlcal = { show: showPnlCal };
export const mffurules = { show: showRules };
export function initPCStatus() {
  renderStatus(true);
  let at = 0;
  onLive(() => { if (Date.now() - at < 10000) return; at = Date.now(); if (isActive('command')) renderStatus(true); });
  // Today: re-draw the relative ages ("12 s ago") without a fetch
  setInterval(() => { if (!document.hidden && isActive('command') && D.st) renderStatus(); }, 5000);
}
