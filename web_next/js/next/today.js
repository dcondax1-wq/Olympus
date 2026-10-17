// Today page extras: two cards above the command grid, each a 3D view with a 2D fallback that stays when 3D is off.
//   Week ring   mount3d('today-week', el, 'weekring', { days, now, target_week_trades: [2, 4] })  from the paper ledger (/api/live/state)
//   Liquidity   mount3d('today-liqmap', el, 'liqmap', { price, pools, bars, position })             from /api/dash/liquidity + /api/live/state
import { $, api, esc, fmt$, fmtS$, fmtN, etParts, etStr, cls } from '../util.js';
import { L, onLive } from '../dash/live.js';
import { icon } from './icons.js';
import { mount3d } from './fx3d.js';

const DN = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
const TARGET = [2, 4];
let lq = null, lqAt = 0, lastWeekSig = '', lastMapSig = '';

const pad = (n) => String(n).padStart(2, '0');
const etDate = (ts) => { const p = etParts(ts); return `${p.y}-${pad(p.mo)}-${pad(p.d)}`; };
function addDays(date, n) { const d = new Date(date + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
function weekDays() {
  // Mon..Fri of the current ET week; on Saturday / Sunday the week that just finished
  const now = Date.now() / 1000, p = etParts(now), today = etDate(now);
  const dow = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay();          // 0 Sun .. 6 Sat
  const back = dow === 0 ? 6 : dow - 1;
  const mon = addDays(today, -back);
  return { today, nowMin: p.h * 60 + p.mi, dow, days: DN.map((label, i) => ({ date: addDays(mon, i), label, dow: i })) };
}
function weekData() {
  const w = weekDays(), rows = (L.live?.ledger || []).filter(r => r.side === 'exit' && r.t);
  const days = w.days.map(d => {
    const ex = rows.filter(r => etDate(r.t) === d.date).map(r => ({ t: r.t, pnl: +(r.pnl || 0), reason: r.reason || '' }));
    const pnl = ex.reduce((s, x) => s + x.pnl, 0);
    return { ...d, trades: ex.length, pnl, wins: ex.filter(x => x.pnl > 0).length, losses: ex.filter(x => x.pnl < 0).length, exits: ex, today: d.date === w.today, past: d.date < w.today };
  });
  return { days, now: { date: w.today, dow: w.dow, minutes: w.nowMin }, target_week_trades: TARGET, running: !!L.live?.running, loaded: !!L.live };
}

// ------------------------------------------------------------------ week ring (2D)
function arc(cx, cy, r, a0, a1) {
  const p = (a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}
function ringSvg(d) {
  const n = d.days.reduce((s, x) => s + x.trades, 0), net = d.days.reduce((s, x) => s + x.pnl, 0);
  // ring of five day segments (labels outside the ring), the week's count and net in the middle
  const cx = 100, cy = 100, R = 64, gap = 0.1, seg = Math.PI * 2 / 5;
  let svg = `<circle cx="${cx}" cy="${cy}" r="${R}" stroke="var(--surface-3)" stroke-width="13" fill="none"/>`;
  d.days.forEach((x, i) => {
    const a0 = -Math.PI / 2 + i * seg + gap / 2, a1 = a0 + seg - gap;
    const col = !x.trades ? (x.past ? 'color-mix(in srgb, var(--ink) 14%, transparent)' : 'var(--surface-3)') : x.pnl > 0 ? 'var(--good)' : x.pnl < 0 ? 'var(--bad)' : 'var(--ink-2)';
    svg += `<path d="${arc(cx, cy, R, a0, a1)}" stroke="${col}" stroke-width="${x.trades ? 13 : 9}" fill="none" stroke-linecap="butt" opacity="${x.trades ? .95 : .9}"/>`;
    if (x.today) svg += `<path d="${arc(cx, cy, R + 11, a0, a1)}" stroke="var(--accent)" stroke-width="2.5" fill="none" opacity=".95"/>`;
    const am = (a0 + a1) / 2, lx = cx + (R + 23) * Math.cos(am), ly = cy + (R + 23) * Math.sin(am);
    svg += `<text x="${lx.toFixed(1)}" y="${(ly + 3.5).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="650" fill="${x.today ? 'var(--accent)' : x.trades ? 'var(--ink-2)' : 'var(--muted)'}" font-family="Inter, system-ui">${x.label}${x.trades ? ' · ' + x.trades : ''}</text>`;
  });
  const band = n < TARGET[0] ? 'below' : n > TARGET[1] ? 'above' : 'in';
  svg += `<text x="${cx}" y="${cy + 2}" text-anchor="middle" font-size="34" font-weight="750" fill="var(--ink)" font-family="Inter, system-ui" letter-spacing="-1">${n}</text>
    <text x="${cx}" y="${cy + 18}" text-anchor="middle" font-size="8.5" font-weight="650" fill="var(--muted)" font-family="Inter, system-ui" letter-spacing=".6">AIM ${TARGET[0]}–${TARGET[1]} A WEEK</text>
    <text x="${cx}" y="${cy + 33}" text-anchor="middle" font-size="11.5" font-weight="650" fill="${net > 0 ? 'var(--good-ink)' : net < 0 ? 'var(--bad)' : 'var(--ink-2)'}" font-family="JetBrains Mono, monospace">${n ? fmtS$(net) : '—'}</text>`;
  return { svg: `<svg viewBox="0 0 200 200" width="190" height="190" class="nx-ring">${svg}</svg>`, n, net, band };
}
function renderWeek() {
  const el = $('#nxWeek2d'), fx = $('#nxWeek3d'); if (!el) return;
  const d = weekData();
  const sig = JSON.stringify(d.days.map(x => [x.trades, x.pnl])) + d.now.date + d.running + d.loaded;
  if (sig !== lastWeekSig) {
    lastWeekSig = sig;
    const { svg, n, net, band } = ringSvg(d);
    const left = Math.max(0, TARGET[0] - n), remaining = d.days.filter(x => !x.past && !(x.today && d.now.minutes >= 960)).length;
    const verdict = !d.loaded ? 'Waiting for the paper bot' : band === 'in' ? 'On pace: 2–4 trades a week' : band === 'above' ? 'Busy week: above the 2–4 aim'
      : remaining === 0 ? `Week over: ${n} trade${n === 1 ? '' : 's'} (aim 2–4)` : n === 0 && remaining === 5 ? 'Fresh week' : left ? `${left} more for the 2-a-week floor · ${remaining} session${remaining === 1 ? '' : 's'} left` : 'Below the aim';
    el.innerHTML = `<div class="nx-week"><div class="nx-week-ring">${svg}</div>
      <div class="nx-week-side"><div class="nx-eyebrow">Paper ledger · week of ${esc(d.days[0].date)}</div><h3>${esc(verdict)}</h3>
        <div class="nx-week-days">${d.days.map(x => `<div class="nx-wd ${x.today ? 'today' : ''} ${x.trades ? (x.pnl > 0 ? 'win' : x.pnl < 0 ? 'loss' : 'flat') : ''}"><span>${x.label}</span><b>${x.trades || (x.past || x.today ? '0' : '·')}</b><em class="${cls(x.pnl)}">${x.trades ? fmtS$(x.pnl) : ''}</em></div>`).join('')}</div>
        <p class="muted small">${d.running ? 'PC paper bot running · exits counted by ET trading day' : d.loaded ? 'PC paper bot stopped · last ledger rows only' : 'No answer from /api/live/state yet'} · ${n} trade${n === 1 ? '' : 's'}, ${fmtS$(net)} this week</p></div></div>`;
  }
  mount3d('today-week', fx, 'weekring', { days: d.days, now: d.now, target_week_trades: TARGET });
}

// ------------------------------------------------------------------ liquidity map (2D)
async function liquidity() {
  if (Date.now() - lqAt < 300000) return lq; lqAt = Date.now();
  try { const r = await api('/api/dash/liquidity'); lq = r?.status === 'ok' ? r : lq; } catch { }
  return lq;
}
function mapSvg(price, pools, pos) {
  const W = 420, H = 300, L = 8, R = 8, T = 16, B = 16;
  // pools within 2.5% of price; when the bot is not polling only a few key levels exist, so keep at least 3 each side
  let near = pools.filter(p => price && Math.abs(p.price - price) / price < 0.025);
  if (near.length < 6) { const up = pools.filter(p => p.price > price).sort((a, b) => a.price - b.price).slice(0, 3), dn = pools.filter(p => p.price < price).sort((a, b) => b.price - a.price).slice(0, 3); near = [...new Set([...near, ...up, ...dn])]; }
  near = near.sort((a, b) => b.price - a.price);
  const ys = near.map(p => p.price).concat([price], pos ? [pos.entry, pos.stop, pos.target].filter(Number.isFinite) : []);
  let lo = Math.min(...ys), hi = Math.max(...ys); const pad = (hi - lo) * 0.08 || 20; lo -= pad; hi += pad;
  const Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const maxS = Math.max(1, ...near.map(p => p.strength || 1));
  let out = '';
  // premium / discount wash around price
  out += `<rect x="${L}" y="${T}" width="${W - L - R}" height="${Math.max(0, Y(price) - T)}" fill="var(--bsl)" opacity=".05"/><rect x="${L}" y="${Y(price)}" width="${W - L - R}" height="${Math.max(0, H - B - Y(price))}" fill="var(--ssl)" opacity=".05"/>`;
  let lastY = -99;
  for (const p of near) {
    const y = Y(p.price), col = p.side === 'H' ? 'var(--bsl)' : 'var(--ssl)', k = (p.strength || 1) / maxS;
    const x1 = L + 118 + (1 - k) * 90;
    out += `<line x1="${x1}" x2="${W - R}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${col}" stroke-width="${(1 + 2 * k).toFixed(1)}" opacity="${(.45 + .5 * k).toFixed(2)}"/>`;
    if (Math.abs(y - lastY) > 11) {
      out += `<text x="${L}" y="${(y + 3.5).toFixed(1)}" font-size="10.5" fill="${col}" font-weight="${k > .6 ? 700 : 500}" font-family="Inter, system-ui">${p.side === 'H' ? 'BSL' : 'SSL'} ${esc(String(p.label || '').replace('·', ' ').slice(0, 18))}</text>`;
      out += `<text x="${W - R}" y="${(y - 3).toFixed(1)}" text-anchor="end" font-size="10" fill="var(--ink-2)" font-family="JetBrains Mono, monospace">${fmtN(p.price, 0)} <tspan fill="var(--muted)">${p.price > price ? '+' : ''}${fmtN(p.price - price, 0)}</tspan></text>`;
      lastY = y;
    }
  }
  if (pos) {
    const ln = (v, col, lbl) => Number.isFinite(v) ? `<line x1="${L + 60}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${col}" stroke-dasharray="4 4" stroke-width="1.4"/><text x="${L + 60}" y="${Y(v) - 3}" font-size="9.5" fill="${col}" font-family="Inter, system-ui" font-weight="650">${lbl} ${fmtN(v, 0)}</text>` : '';
    out += ln(pos.target, 'var(--good)', 'TP') + ln(pos.stop, 'var(--bad)', 'SL') + ln(pos.entry, 'var(--accent)', pos.dir === 1 ? 'LONG' : 'SHORT');
  }
  const py = Y(price);
  out += `<rect x="${L}" y="${(py - 10).toFixed(1)}" width="${W - L - R}" height="20" rx="6" fill="var(--accent)" opacity=".14"/><line x1="${L}" x2="${W - R}" y1="${py.toFixed(1)}" y2="${py.toFixed(1)}" stroke="var(--accent)" stroke-width="1.6"/>
    <text x="${L + 6}" y="${(py + 4).toFixed(1)}" font-size="11.5" font-weight="750" fill="var(--ink)" font-family="JetBrains Mono, monospace">${fmtN(price, 2)}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none" class="nx-liq-svg">${out}</svg>`;
}
async function renderMap() {
  const el = $('#nxLiq2d'), fx = $('#nxLiq3d'); if (!el) return;
  const s = L.live?.state || {}, lv = L.live || {};
  let price = s.price, pools = (s.active_pools || []).map(p => ({ price: p.price, side: p.side, label: p.label, strength: p.strength, dist: price != null ? p.price - price : null }));
  let bars = (lv.bars || []).slice(-40).map(b => [b.time, b.open, b.high, b.low, b.close]);
  const q = await liquidity();
  let src = lv.running && pools.length ? 'live engine pools' : '';
  if (q) {
    if (!pools.length) { pools = (q.pools || []).map(p => ({ price: p.price, side: p.side, label: p.label, strength: p.strength, dist: p.dist })); src = 'engine pools + levels from the data file'; }
    if (!pools.length) { pools = (q.levels || []).filter(x => x.kind !== 'open' && (x.side === 'H' || x.side === 'L') && !x.swept).map(x => ({ price: x.price, side: x.side, label: x.label, strength: x.strength || 1, dist: x.dist })); src = 'levels computed from the data file (bot not polling)'; }
    if (price == null) price = q.price;
  }
  const pos = s.position || null;
  const sig = [price, pools.length, pos?.entry, bars.length, src].join('|');
  if (sig !== lastMapSig) {
    lastMapSig = sig;
    if (price == null || !pools.length) {
      el.innerHTML = `<div class="empty">No liquidity map yet: ${price == null ? 'no price' : 'no pools'} from the bot or the data file.</div>`;
    } else {
      const above = pools.filter(p => p.price > price).sort((a, b) => a.price - b.price)[0], below = pools.filter(p => p.price < price).sort((a, b) => b.price - a.price)[0];
      el.innerHTML = `<div class="nx-liq"><div class="nx-liq-map">${mapSvg(price, pools, pos)}</div>
        <div class="nx-liq-side">
          <div class="nx-kv one">
            <div><span>Price</span><b class="mono">${fmtN(price, 2)}</b></div>
            <div><span>Draw above</span><b style="color:var(--bsl)">${above ? `${esc(String(above.label || '').replace('·', ' '))} · +${fmtN(above.price - price, 1)}` : '—'}</b></div>
            <div><span>Draw below</span><b style="color:var(--ssl)">${below ? `${esc(String(below.label || '').replace('·', ' '))} · ${fmtN(below.price - price, 1)}` : '—'}</b></div>
            <div><span>Position</span><b>${pos ? `${pos.dir === 1 ? 'LONG' : 'SHORT'} @ ${fmtN(pos.entry)} → TP ${fmtN(pos.target)} / SL ${fmtN(pos.stop)}` : 'flat'}</b></div>
            ${q?.adr20 ? `<div><span>20-day range</span><b class="mono">${fmtN(q.adr20, 0)} pts</b></div>` : ''}
          </div>
          <p class="muted small">${esc(src)}${bars.length ? ` · last bar ${etStr(bars.at(-1)[0])} ET` : ''}. BSL = buy stops above, SSL = sell stops below; thicker = stronger pool.</p>
        </div></div>`;
    }
  }
  if (price != null) mount3d('today-liqmap', fx, 'liqmap', { price, pools, bars, position: pos });
}

export function initToday() {
  const host = $('#nxToday3'); if (!host) return;
  host.innerHTML = `
    <div class="card nx-glass nx-t3"><div class="card-h"><h3>${icon('week')} This week</h3><div class="card-tools"><span class="muted small">aim 2–4 trades</span><button class="btn ghost sm" data-goto="strategy">${icon('strategy')}Strategy</button></div></div>
      <div class="nx-fxwrap"><div class="fx3d weekring" id="nxWeek3d"></div><div class="nx-2d" id="nxWeek2d"><div class="empty">Waiting for the paper bot…</div></div></div></div>
    <div class="card nx-glass nx-t3"><div class="card-h"><h3>${icon('map')} Liquidity map</h3><span class="muted small">untaken pools around price</span></div>
      <div class="nx-fxwrap"><div class="fx3d liqmap" id="nxLiq3d"></div><div class="nx-2d" id="nxLiq2d"><div class="empty">Loading pools…</div></div></div></div>`;
  renderWeek(); renderMap();
  onLive(() => { renderWeek(); renderMap(); });
  setInterval(() => { if (!document.hidden) { renderWeek(); renderMap(); } }, 60000);
}
