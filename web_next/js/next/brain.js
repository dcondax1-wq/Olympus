// Bot Brain (top-level page): what the LIT bot is thinking, exactly, with every number next to its rule.
// Data: /api/next/brain (the PC bot's last Brain, built after each poll by engine/brain.py), /api/next/brain/log (the day's
// thought log, data/brain/YYYY-MM-DD.jsonl), /api/next/brain/days + /api/next/brain/day/<date>?t= (any 2026 day replayed
// from the stored bars, the same Brain at any 5-minute close). Read-only: nothing here can start, size or route anything.
import { $, $$, esc, fmtN, fmtS$, cls } from '../util.js';
import { icon } from './icons.js';

const TABS = [['now', 'Now'], ['levels', 'Levels'], ['setups', 'Setups'], ['sizing', 'Sizing'], ['trade', 'Trade'], ['guards', 'Guards'],
  ['log', 'Thought log'], ['replay', 'Replay a day']];
const VIEW_TABS = TABS.filter(([k]) => k !== 'replay');
const S = { tab: 'now', sub: 'now', live: null, liveErr: null, at: 0, timer: null, help: null,
  days: null, day: null, frames: null, fi: 0, rb: null, rbErr: null, play: null, busy: false, fullLog: null };
const isActive = () => document.getElementById('page-brain')?.classList.contains('active');
const p2 = (x) => (x == null ? '—' : Number(x).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const sgn = (x, d = 1) => (x == null ? '—' : (x > 0 ? '+' : '') + fmtN(x, d));
const hmOf = (t) => new Date(t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false });
const seg = (id, items, cur) => `<div class="seg" id="${id}">${items.map(([v, l]) => `<button type="button" data-v="${esc(v)}" class="${v === cur ? 'on' : ''}">${esc(l)}</button>`).join('')}</div>`;
const onSeg = (id, fn) => { const s = $('#' + id); if (s) s.onclick = (e) => { const b = e.target.closest('button[data-v]'); if (b) fn(b.dataset.v); }; };
const card = (title, body, tools = '', extra = '') => `<section class="card nx-glass bb-card ${extra}"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</section>`;
const stat = (k, v, sub = '', c = '') => `<div class="nx-stat"><span>${k}</span><b class="${c}">${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const ok = (b) => `<span class="bb-ok ${b ? 'y' : 'n'}" aria-label="${b ? 'pass' : 'fail'}">${b ? '✓' : '✗'}</span>`;
const info = (k) => `<button type="button" class="bb-i" data-help="${esc(k)}" aria-label="What is this?">i</button>`;
const STATUS = { armed: ['Limit armed', 'gold'], tapped: ['Tapped, waiting 1m CISD', 'gold'], entering: ['Entering now', 'good'], filled: ['Filled', 'good'],
  no_fill: ['No fill', 'muted'], rejected: ['Rejected', 'bad'], blocked: ['Blocked', 'muted'] };
const KIND = { sweep: 'Sweep', cisd: '5m CISD', armed: 'Armed', rejected: 'Rejected', blocked: 'Blocked', expired: 'No fill', tap: 'Tapped', entry: 'Entry',
  exit: 'Exit', trade: 'Trade', stage: 'Stage', box: 'Box' };

// ------------------------------------------------------------------ data
async function getJ(u) { const r = await fetch(u); const d = await r.json().catch(() => ({})); if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status); return d; }
async function loadLive() {
  try { S.live = await getJ('/api/next/brain'); S.liveErr = null; S.at = Date.now(); if (S.live.help) S.help = S.live.help; }
  catch (e) { S.liveErr = e.message; }
}
async function loadFullLog(day) {
  try { const d = await getJ('/api/next/brain/log' + (day ? '?day=' + encodeURIComponent(day) : '')); S.fullLog = d; } catch { S.fullLog = null; }
}
async function loadDays() { if (!S.days) { try { S.days = (await getJ('/api/next/brain/days')).days || []; } catch (e) { S.days = []; S.rbErr = e.message; } } }
async function loadReplay(t) {
  if (!S.day) return;
  S.busy = true;
  try {
    const first = !S.frames;
    const d = await getJ(`/api/next/brain/day/${S.day}?${t ? 't=' + t : 'hm=16:00'}${first ? '&frames=1' : ''}`);
    if (first) { S.frames = d.frames || []; S.fi = Math.max(0, S.frames.length - 1); }
    S.rb = d; S.rbErr = null; if (d.help) S.help = d.help;
  } catch (e) { S.rbErr = e.message; }
  S.busy = false;
}

// ------------------------------------------------------------------ pieces
function pipeline(b) {
  const st = b.stages || [];
  return `<div class="bb-pipe" role="list" aria-label="LIT pipeline">${st.map((s, i) => `
    <div class="bb-node ${s.state}" role="listitem" title="${esc((S.help || {})[s.key] || '')}">
      <span class="bb-dot">${s.state === 'done' ? '✓' : s.state === 'skip' ? '–' : s.n}</span>
      <span class="bb-nl">${esc(s.label)}</span>${i < st.length - 1 ? '<span class="bb-link"></span>' : ''}</div>`).join('')}</div>`;
}
function waitingCard(b) {
  const s = b.stage || {};
  const blocked = (b.guards || {}).blocked;
  return `<section class="card nx-glass bb-wait ${blocked ? 'blk' : ''}">
    <div class="bb-eyebrow">What the bot is waiting for ${info(s.key && s.key !== 'closed' ? s.key : 'levels')}</div>
    <div class="bb-big">${esc(s.waiting || '—')}</div>
    <div class="bb-meta"><span class="nx-chip">${s.n ? `Stage ${s.n} of 10 · ` : ''}${esc(s.label || '')}</span>
      ${s.dir ? `<span class="nx-chip ${s.dir > 0 ? 'good' : 'bad'}">${s.dir > 0 ? 'LONG side' : 'SHORT side'}</span>` : ''}
      <span class="muted small">as of ${esc(b.at || '')} · last closed 5m bar ${esc(b.bar_hm || '')} · price ${p2(b.price)} · ATR ${fmtN(b.atr, 1)} pts</span></div>
    ${pipeline(b)}</section>`;
}
function watchCards(b) {
  const W = b.watch || [];
  if (!W.length) return '';
  return card(`The setup forming now ${info('sweep')}`, `<div class="bb-watch">${W.map((w) => {
    const sw = w.swept && w.swept.length;
    const rows = [
      [`Sweep ${info('depth')}`, sw ? w.depth_ok : null, sw ? `${esc(w.swept.slice(0, 3).join(', '))} by ${fmtN(w.depth_atr, 2)} ATR (${fmtN(w.depth_pts, 1)} pts; needs ≥ ${b.rules?.depth} ATR)` : 'no level swept in the last 2 hours'],
      [`Inducement ${info('idm')}`, sw ? w.idm_ok : null, sw ? `${w.idm_n} swing${w.idm_n === 1 ? '' : 's'} taken first within the rule` + (w.idm_best != null ? ` (nearest ${fmtN(w.idm_best, 2)} ATR, ${w.idm_age} bars)` : '') : '—'],
      [`Displacement ${info('disp')}`, sw ? w.disp_ok : null, sw ? `best body ${fmtN(w.disp, 2)} ATR (needs ≥ ${b.rules?.disp})` : '—'],
      [`5m CISD ${info('cisd5')}`, sw && w.cisd != null ? !!w.cisd_closed : null, w.cisd != null ? `close ${w.dir > 0 ? 'above' : 'below'} ${p2(w.cisd)} (${fmtN(Math.abs(w.cisd_dist), 1)} pts away)` : '—'],
    ];
    return `<div class="bb-w ${w.allowed === false ? 'off' : ''}"><div class="bb-wh"><b class="${w.dir > 0 ? 'up' : 'dn'}">${w.side}</b>
        <span class="muted small">leg extreme ${p2(w.ext)} at ${esc(w.ext_hm || '')}${w.allowed === false ? ' · Monday rule: this side is off today' : ''}</span></div>
      ${rows.map(([l, o, t]) => `<div class="bb-row">${o == null ? '<span class="bb-ok q">·</span>' : ok(o)}<span class="bb-rl">${l}</span><span class="bb-rt">${t}</span></div>`).join('')}
      ${w.text ? `<p class="bb-wt">${esc(w.text)}</p>` : ''}</div>`;
  }).join('')}</div>`);
}
function logList(rows, n = 400) {
  if (!rows || !rows.length) return '<div class="pc-empty"><b>Nothing logged yet today.</b></div>';
  return `<ol class="bb-log">${rows.slice(0, n).map((r) => `<li class="k-${esc(r.kind || '')}" ${r.t ? `data-t="${r.t}"` : ''}><span class="bb-lt mono">${esc(r.hm || '')}</span>
    <span class="bb-lk">${esc(KIND[r.kind] || r.kind || '')}</span><span class="bb-lx">${esc(r.text || '')}</span></li>`).join('')}</ol>`;
}

// ------------------------------------------------------------------ views (each takes a Brain)
function vNow(b) {
  const n = b.nearest || {};
  const lvl = (r) => `<div class="bb-nr"><span>${esc(r.label)}</span><b class="mono">${p2(r.price)}</b><em class="${cls(r.dist)}">${sgn(r.dist, 1)} pts · ${fmtN(Math.abs(r.dist_atr), 1)} ATR</em></div>`;
  const S2 = b.setups || [];
  const tr = b.trade;
  return waitingCard(b) + `<div class="nx-stats">
      ${stat('Price', p2(b.price), `last 5m close ${esc(b.bar_hm || '')}`)}${stat('ATR (5m)', fmtN(b.atr, 1) + ' pts', `0.5 ATR sweep = ${fmtN((b.atr || 0) * (b.rules?.depth || 0.5), 1)} pts`)}
      ${stat('Setups today', S2.length, `${S2.filter((s) => s.status === 'rejected').length} rejected · ${S2.filter((s) => s.status === 'no_fill').length} no fill`)}
      ${stat('Closed trades today', b.day_trades ?? 0, b.day_pnl ? fmtS$(b.day_pnl) : 'max 1 a day', cls(b.day_pnl))}
      ${tr ? stat('Open trade', `${tr.side} ${sgn(tr.r_now, 2)}R`, `${fmtS$(tr.usd_now)} · ${tr.qty} micros`, cls(tr.r_now)) : ''}</div>
    <div class="bb-grid2">${card(`Nearest levels ${info('levels')}`, `<div class="bb-near"><div><div class="bb-sub">Above (buy-side liquidity)</div>${(n.above || []).map(lvl).join('') || '<div class="muted">none</div>'}</div>
        <div><div class="bb-sub">Below (sell-side liquidity)</div>${(n.below || []).map(lvl).join('') || '<div class="muted">none</div>'}</div></div>`)}
      ${card('Latest thoughts', logList(b.log, 8), `<button class="nx-chipbtn" type="button" data-bbtab="log">${icon('reports')}<span>Full log</span></button>`)}</div>
    ${watchCards(b)}`;
}
function ladder(b) {
  const L = (b.levels || []).filter((r) => r.price != null);
  const g = b.guards?.vix || {};
  const price = b.price;
  if (!L.length || price == null) return '';
  const near = L.filter((r) => Math.abs(r.price - price) < Math.max(8 * (b.atr || 20), 300));
  const ps = [...near.map((r) => r.price), price, ...(g.up ? [g.up] : []), ...(g.dn ? [g.dn] : [])].filter((x) => Math.abs(x - price) < Math.max(8 * (b.atr || 20), 400));
  const lo = Math.min(...ps), hi = Math.max(...ps), pad = (hi - lo) * 0.06 + 1;
  const H = Math.max(360, Math.min(900, near.length * 26 + 80)), W = 900, X0 = 400;
  const y = (v) => 14 + (H - 28) * (1 - (v - (lo - pad)) / ((hi + pad) - (lo - pad)));
  const rows = near.slice().sort((a, b2) => b2.price - a.price);
  let lastY = -99;
  const marks = rows.map((r) => {
    let yy = y(r.price); const ly = Math.max(yy, lastY + 13); lastY = ly;
    const col = r.taken ? 'var(--muted)' : r.side === 'H' ? 'var(--bsl)' : 'var(--ssl)';
    return `<line x1="${X0}" x2="${W - 10}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}" stroke="${col}" stroke-width="${r.taken ? 1 : 1.6}" ${r.taken ? 'stroke-dasharray="4 4"' : ''} opacity="${r.taken ? 0.55 : 0.9}"/>
      <line x1="${X0 - 14}" x2="${X0}" y1="${ly.toFixed(1)}" y2="${yy.toFixed(1)}" stroke="${col}" opacity=".6"/>
      <text x="${X0 - 18}" y="${(ly + 4).toFixed(1)}" text-anchor="end" font-size="12" fill="${col}">${esc(r.label)} ${p2(r.price)}${r.taken ? ` · swept ${esc(r.taken_hm || '')}${r.depth_atr != null ? ' ' + fmtN(r.depth_atr, 2) + ' ATR' + (r.deep_ok ? ' ✓' : ' ✗') : ''}` : ''}</text>`;
  }).join('');
  const band = g.up && g.dn ? '' : '';
  const vx = [g.up, g.dn].filter((v) => v != null && v >= lo - pad && v <= hi + pad).map((v) => `<line x1="${X0}" x2="${W - 10}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--gold)" stroke-width="2"/>
      <text x="${W - 12}" y="${(y(v) - 5).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--gold)">VIX band (target) ${p2(v)}</text>`).join('');
  const py = y(price);
  return `<svg class="bb-ladder" viewBox="0 0 ${W} ${H}" role="img" aria-label="Price ladder: levels above and below the price">${band}${marks}${vx}
    <rect x="${X0}" y="${(py - 11).toFixed(1)}" width="${W - X0 - 10}" height="22" rx="6" fill="color-mix(in srgb, var(--accent) 22%, transparent)" stroke="var(--accent)"/>
    <text x="${(W + X0) / 2}" y="${(py + 4).toFixed(1)}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ink)">PRICE ${p2(price)}</text></svg>`;
}
function vLevels(b) {
  const L = b.levels || [];
  const g = b.guards?.vix || {};
  return card(`Price ladder ${info('levels')}`, `<div class="bb-tw">${ladder(b)}</div>` + `<p class="muted small">Orange = highs (buy-side liquidity), blue = lows (sell-side liquidity), dashed = already swept today, gold = the VIX-band target. A sweep counts for LIT when price trades through a level by at least ${b.rules?.depth} ATR (${fmtN((b.atr || 0) * (b.rules?.depth || 0.5), 1)} pts now).</p>`)
    + card(`Every level the bot watches today (${L.length})`, `<div class="bb-tw"><table class="tbl bb-tbl"><thead><tr><th>Level</th><th>Kind</th><th>Side</th><th style="text-align:right">Price</th><th style="text-align:right">From price</th><th style="text-align:right">ATR</th><th>Status</th></tr></thead>
      <tbody>${L.map((r) => `<tr class="${r.taken ? 'tk' : ''}"><td><b>${esc(r.label)}</b>${(r.also || []).length ? `<span class="muted small"> = ${esc(r.also.join(', '))}</span>` : ''}</td><td class="muted">${esc(r.kind_label || r.kind)}</td>
        <td>${r.side === 'H' ? '<span class="up">high</span>' : '<span class="dn">low</span>'}</td><td class="mono" style="text-align:right">${p2(r.price)}</td>
        <td class="mono ${cls(r.dist)}" style="text-align:right">${sgn(r.dist, 1)}</td><td class="mono" style="text-align:right">${fmtN(r.dist_atr, 1)}</td>
        <td>${r.taken ? `swept ${esc(r.taken_hm || '')} · ${fmtN(r.depth_atr, 2)} ATR (${fmtN(r.depth_pts, 1)} pts) ${ok(r.deep_ok)}` : '<span class="muted">untaken</span>'}</td></tr>`).join('')}</tbody></table></div>
      <p class="muted small">VIX ${fmtN(g.vix, 2)} · VXN ${fmtN(g.vxn, 2)} · one-day move ${fmtN(g.move, 1)} pts from the 18:00 open ${p2(g.open18)} → band ${p2(g.dn)} / ${p2(g.up)} ${info('vix')}</p>`);
}
function setupCard(s) {
  const [lab, c] = STATUS[s.status] || [s.status, ''];
  const pl = s.plan;
  return `<article class="bb-setup st-${esc(s.status)}"><header><span class="mono bb-st">${esc(s.hm)}</span><b class="${s.dir > 0 ? 'up' : 'dn'}">${esc(s.side)}</b>
      <span class="nx-chip ${c}">${esc(lab)}</span><span class="muted small">swept ${esc((s.swept || []).join(', '))}</span></header>
    <p class="bb-why">${esc(s.status_text || '')}</p>
    <ul class="bb-checks">${(s.checks || []).map((k) => `<li class="${k.ok ? '' : 'fail'}">${ok(k.ok)}<span class="bb-cl">${esc(k.label)} ${info(k.key)}</span><span class="bb-ct">${esc(k.text || '')}</span></li>`).join('')}</ul>
    ${pl ? `<div class="bb-plan"><span>Limit <b class="mono">${p2(pl.limit)}</b></span><span>Stop <b class="mono">${p2(pl.stop)}</b> (${fmtN(pl.stop_pts, 1)} pts)</span>
      <span>Target <b class="mono">${p2(pl.target)}</b> (${fmtN(pl.rr, 1)}R, ${esc(pl.target_label || '')})</span><span>Armed ${esc(pl.armed_hm || '')} → ${esc(pl.expires_hm || '')}</span>
      ${pl.tapped_hm ? `<span>Tapped ${esc(pl.tapped_hm)}, 1m CISD until ~${esc(pl.cisd_deadline_hm || '')}</span>` : ''}</div>` : ''}
    ${s.trade ? `<div class="bb-plan"><span>Entry ${esc(s.trade.entry_hm)} at <b class="mono">${p2(s.trade.entry)}</b> (${esc(s.trade.kind)})</span><span>${esc(s.trade.exit || '')} <b class="${cls(s.trade.r)}">${s.trade.r == null ? '' : sgn(s.trade.r, 2) + 'R'}</b> ${s.trade.pnl != null && s.trade.exit !== 'OPEN' ? fmtS$(s.trade.pnl) + ' (model micros)' : ''}</span></div>` : ''}
  </article>`;
}
function vSetups(b) {
  const A = b.setups || [];
  const main = A.filter((s) => s.status !== 'blocked'), blk = A.filter((s) => s.status === 'blocked');
  if (!A.length) return card('Setups today', `<div class="pc-empty"><b>No 5m CISD setup yet today.</b><span>A setup appears when a sweep is followed by a 5-minute close through the CISD level. The Now tab shows what is forming.</span></div>`);
  const counts = Object.entries(A.reduce((m, s) => { m[s.status] = (m[s.status] || 0) + 1; return m; }, {})).map(([k, n]) => `${n} ${(STATUS[k] || [k])[0].toLowerCase()}`).join(' · ');
  return `<div class="nx-hint muted small" style="margin:2px 2px 10px">${A.length} setups today: ${esc(counts)}. Every LIT rule is checked in the order the engine checks it; the first ✗ is why it did not trade. ${info('day')}</div>
    <div class="bb-setups">${main.map(setupCard).join('')}</div>
    ${blk.length ? `<details class="card nx-glass bb-card"><summary><b>${blk.length} later setup${blk.length > 1 ? 's' : ''} skipped: 1 trade a day</b> <span class="muted small">(tap to see their checks)</span></summary><div class="bb-setups">${blk.map(setupCard).join('')}</div></details>` : ''}`;
}
function vSizing(b) {
  const z = b.sizing || {};
  const ev = z.eval || {};
  const ws = z.weekly_stop;
  return `<div class="nx-stats">${stat('Micros', z.qty ?? '—', esc(z.mode || ''), 'up')}${stat('$ at risk', z.risk_usd != null ? '$' + fmtN(z.risk_usd, 0) : '—', `${fmtN(z.risk_pts, 1)}-pt stop + 1 tick + $1.90`)}
      ${stat('Target pays', z.win_usd != null ? '$' + fmtN(z.win_usd, 0) : '—', `${fmtN(z.tgt_pts, 1)} pts`)}${stat('Eval session', ev.session ? `${ev.session} of ${ev.limit || 10}` : '—', esc(ev.text || ''))}</div>
    ${card(`How the bot sizes ${esc(z.what || '')} ${info(z.mode === 'two_week' ? 'two_week' : 'stop')}`, `<ol class="bb-math">${(z.steps || []).map((s) => `<li><span class="bb-ml">${esc(s.label)}</span><b class="mono">${esc(s.value)}</b><span class="bb-mt">${esc(s.text)}</span></li>`).join('')}</ol>
      ${(z.reasons || []).length ? `<p class="muted small">Sizer: ${esc(z.reasons.join('; '))}</p>` : ''}${z.fallback ? `<p class="banner warn">${esc(z.fallback)}</p>` : ''}`)}
    <div class="bb-grid2">${card(`Weekly stop ${info('wk_stop')}`, ws ? `<p>${esc(ws.text || '')}</p><p class="muted small">${ws.stops} of ${ws.after} stop-outs this week; size x${ws.mult}</p>` : '<p class="muted">off</p>')}
      ${card('Eval', `<p>${esc(ev.text || 'eval state unknown')}</p>${ev.to_target != null ? `<p class="muted small">$${fmtN(ev.to_target, 0)} to the +$3,000 target · room to the trailing floor $${fmtN(ev.room, 0)}</p>` : ''}
        <p>${ev.lock ? '<span class="nx-chip bad">Pass / fail lock ON: no new trade on this eval</span>' : '<span class="nx-chip good">No pass lock: the eval is open</span>'}</p>${ev.life ? `<p class="muted small">${esc(ev.life)}</p>` : ''}`)}</div>`;
}
function vTrade(b) {
  const t = b.trade;
  const R = b.rules || {};
  const rulesList = `<ul class="bb-rules"><li>Breakeven at +${R.be_r}R: the stop moves to the entry + ${R.be_off} pts ${info('be')}</li>
    <li>15-minute check: ${R.t_check ? `at ${R.t_check.at} min, cut if the trade never reached +${R.t_check.mfe}R and closes more than ${R.t_check.x}R below the entry` : 'off'} ${info('t_check')}</li>
    <li>Target: the VIX band, at least ${R.min_rr}R away, banked at ${R.max_rr}R ${info('target')}</li><li>Flat at ${esc(R.flat || '15:55')} ET; ${R.max_per_day} trade a day</li></ul>`;
  if (!t) return card('Trade management', `<div class="pc-empty"><b>No open trade right now.</b><span>When a trade is open this shows its stop, breakeven trigger, 15-minute check, target and live R / $.</span></div>${rulesList}`);
  const d = t.dir, lo = Math.min(t.stop0, t.target, t.price), hi = Math.max(t.stop0, t.target, t.price);
  const x = (v) => (100 * (v - lo) / Math.max(1e-9, hi - lo)).toFixed(2);
  const tc = t.t_check || {};
  return `<div class="nx-stats">${stat('Side', `<span class="${d > 0 ? 'up' : 'dn'}">${t.side}</span>`, `${t.qty} micros · entry ${esc(t.entry_hm)}`)}${stat('Live R', sgn(t.r_now, 2) + 'R', fmtS$(t.usd_now), cls(t.r_now))}
      ${stat('Best so far', sgn(t.mfe_r, 2) + 'R', 'MFE')}${stat('$ at risk', '$' + fmtN(t.risk_usd, 0), `${fmtN(t.risk_pts, 1)} pts`)}</div>
    ${card('Where price is in the trade', `<div class="bb-bar"><div class="bb-track"></div>
      ${[['Stop', t.stop0, 'bad'], ['Entry', t.entry, ''], ['BE +1R', t.be.trigger, 'gold'], ['Target', t.target, 'good']].map(([l, v, c]) => `<span class="bb-tick ${c}" style="left:${x(v)}%"><i></i><em>${l}<br>${p2(v)}</em></span>`).join('')}
      <span class="bb-px" style="left:${x(t.price)}%"><i></i><em>now ${p2(t.price)}</em></span></div>`)}
    <div class="bb-grid2">${card(`Stop and breakeven ${info('be')}`, `<p>Stop now <b class="mono">${p2(t.stop)}</b>${t.stop !== t.stop0 ? ` (was ${p2(t.stop0)})` : ''}</p><p>${esc(t.be.text)}</p>`)}
      ${card(`15-minute check ${info('t_check')}`, `<p>${esc(tc.text || 'off')}</p>`)}
      ${card(`Target ${info('target')}`, `<p>Target <b class="mono">${p2(t.target)}</b> (${esc(t.target_label || '')}, ${fmtN(t.target_r, 2)}R)</p><p class="muted small">Bank at ${t.bank.r}R = ${p2(t.bank.price)}</p>`)}
      ${card('Flat time', `<p>${esc(t.flat.text)}</p>`)}</div>${rulesList}`;
}
function vGuards(b) {
  const g = b.guards || {};
  const f = g.feed || {};
  const m = g.market || {};
  const age = (s) => (s == null ? '—' : s < 120 ? Math.round(s) + ' s' : Math.round(s / 60) + ' min');
  return `${g.blocked ? `<div class="banner bad bb-ban"><b>Something is blocking new entries:</b> ${esc((g.blocking || []).join(' · '))}</div>` : '<div class="banner good bb-ban">Nothing is blocking new entries. Open positions are always managed.</div>'}
    <div class="nx-stats">${stat('Market', m.open ? 'open' : 'closed', esc(m.text || ''))}${stat('Entry window', m.entry_window ? 'open' : 'closed', esc(m.window || ''))}
      ${stat('1m bar age', age(f.age_1m_s), esc(f.source || 'no feed info'))}${stat('Clock drift', g.clock_drift_s == null ? '—' : fmtN(g.clock_drift_s, 1) + ' s', 'vs internet time, max 5 s')}</div>
    <div class="bb-grid2">${card('Safety guards', `<table class="tbl"><tbody>${(g.guards || []).map((x) => `<tr><td>${esc(x.label)}</td><td style="text-align:right">${x.on ? '<span class="nx-chip good">on</span>' : '<span class="nx-chip">off</span>'}</td></tr>`).join('')}</tbody></table>
        <p class="muted small">Guards can only block a new entry or close a position the bot does not hold; none sizes up or moves a stop.</p>`)}
      ${card('Today', `<p><b>News (high-impact USD):</b> ${(g.news || []).length ? esc(g.news.map((n) => `${n.time || ''} ${n.title}`).join(' · ')) : 'none'}</p>
        <p class="muted small">LIT does not pause for news (the MFFU Builder allows it); a sweep made by a release still counts.</p>
        <p><b>VIX band:</b> VIX ${fmtN(g.vix?.vix, 2)}, VXN ${fmtN(g.vix?.vxn, 2)}: ${p2(g.vix?.dn)} / ${p2(g.vix?.up)} ${info('vix')}</p>
        ${m.early_close ? `<p class="banner warn">CME early close at ${esc(m.early_close)} ET today</p>` : ''}
        <p class="muted small">Feed: 5m bar ${age(f.age_5m_s)} old, 1m bar ${age(f.age_1m_s)} old${f.no_yahoo ? ' · no Yahoo (NinjaTrader bars only)' : ''}; last poll ${age(g.poll?.age_s)} ago${g.poll?.ms ? `, ${g.poll.ms} ms` : ''}</p>`)}</div>`;
}
function vLog(b, full) {
  const rows = full && full.log && full.log.length && full.day === b.day ? full.log : b.log;
  return card(`Thought log · ${esc(b.day || '')}`, logList(rows), `<span class="muted small">${(rows || []).length} lines, newest first${b.mode === 'live' ? ' · updates every 15 s' : ''}</span>`);
}
const VIEWS = { now: vNow, levels: vLevels, setups: vSetups, sizing: vSizing, trade: vTrade, guards: vGuards, log: (b) => vLog(b, S.fullLog) };

// ------------------------------------------------------------------ replay tab
function vReplay() {
  const days = S.days || [];
  const pick = `<label class="nx-field"><span class="muted small">Day</span><select id="bbDay" class="inp">${days.map((d) => `<option value="${d.day}" ${d.day === S.day ? 'selected' : ''}>${d.day}${d.trade ? ` · ${d.trade.exit} ${d.trade.r > 0 ? '+' : ''}${d.trade.r}R` : ' · no trade'}</option>`).join('')}</select></label>`;
  const fr = S.frames || [];
  const t = fr[S.fi];
  const scrub = fr.length ? `<div class="bb-scrub"><button type="button" class="nx-chipbtn" id="bbPrev" aria-label="Previous 5 minutes">${icon('left')}</button>
      <button type="button" class="nx-chipbtn" id="bbPlay" aria-label="Play">${icon(S.play ? 'pause' : 'play')}</button>
      <input type="range" id="bbRange" min="0" max="${fr.length - 1}" value="${S.fi}" aria-label="Time of day">
      <button type="button" class="nx-chipbtn" id="bbNext" aria-label="Next 5 minutes">${icon('right')}</button><b class="mono bb-tl">${t ? hmOf(t) + ' ET' : ''}</b>
      ${S.busy ? '<span class="muted small">loading…</span>' : ''}</div>` : '';
  const b = S.rb;
  return `<div class="card nx-glass bb-card"><div class="bb-rhead">${pick}<p class="muted small">Pick any 2026 session: the Brain is rebuilt from the stored bars exactly as the PC bot would have seen them at each 5-minute close (same engine, no look-ahead). Drag the slider, or tap a log line to jump to it.</p></div>${scrub}</div>
    ${S.rbErr ? `<div class="banner warn">${esc(S.rbErr)}</div>` : ''}
    ${b && !b.error ? `<div class="nx-toolbar">${seg('bbSub', VIEW_TABS, S.sub)}</div><div id="bbRView">${VIEWS[S.sub](b)}</div>` : b && b.error ? `<div class="banner warn">${esc(b.error)}</div>` : '<div class="nx-skel"><i></i><i></i></div>'}`;
}

// ------------------------------------------------------------------ render
function render() {
  const el = $('#page-brain'); if (!el) return;
  const b = S.live;
  const live = b && !b.empty && !b.error;
  const src = live ? `<span class="nx-chip good">LIVE · PC bot${b.running ? '' : ' (stopped)'}</span> <span class="muted small">updated ${new Date(S.at).toLocaleTimeString()}</span>`
    : `<span class="nx-chip">${esc(b?.empty ? 'no live Brain' : S.liveErr ? 'offline' : 'loading')}</span>`;
  const head = `<div class="nx-hero"><div><div class="nx-eyebrow">${icon('brain')} Bot Brain · ${src}</div><h2>What the bot is thinking</h2>
    <p class="muted">Every step of the LIT strategy, live: what it waits for, every level it watches, every setup it saw today and the exact rule that stopped it, how it sizes, how it manages the trade and what could block it. Read-only: this page cannot change anything the bot does.</p></div></div>
    <div class="nx-toolbar bb-tabs">${seg('bbTab', TABS, S.tab)}</div>`;
  let body;
  if (S.tab === 'replay') body = vReplay();
  else if (!live) body = `<div class="card nx-glass nx-empty-hub"><span class="nx-tile-i">${icon('brain')}</span><h3>${esc(b?.reason || S.liveErr || 'Loading…')}</h3>
      <p class="muted">The live Brain fills in after the bot's first LIT poll. Meanwhile, replay any 2026 day to see what the bot thought.</p>
      <button type="button" class="btn primary" data-bbtab="replay">${icon('replay')}<span>Replay ${esc(b?.latest_day || 'a day')}</span></button></div>`;
  else body = `<div id="bbView">${VIEWS[S.tab](b)}</div>`;
  el.innerHTML = head + body;
  onSeg('bbTab', (v) => { setTab(v); });
  $$('[data-bbtab]', el).forEach((x) => x.addEventListener('click', () => {
    if (x.closest('#bbRView')) { S.sub = x.dataset.bbtab; render(); } else setTab(x.dataset.bbtab);
  }));
  if (S.tab === 'replay') bindReplay();
}
function setTab(v) {
  S.tab = v;
  if (v === 'replay' && !S.days) { render(); loadDays().then(() => { S.day = S.day || S.live?.latest_day || (S.days[0] || {}).day; return loadReplay(); }).then(render); return; }
  if (v === 'log' && S.live && !S.live.empty) loadFullLog(S.live.day).then(() => { if (S.tab === 'log') render(); });
  render();
}
function bindReplay() {
  const dsel = $('#bbDay');
  if (dsel) dsel.onchange = () => { S.day = dsel.value; S.frames = null; S.rb = null; stopPlay(); render(); loadReplay().then(render); };
  const go = (i) => { if (!S.frames) return; S.fi = Math.max(0, Math.min(S.frames.length - 1, i)); const rb = $('#bbRange'); if (rb) rb.value = S.fi; const tl = $('.bb-tl'); if (tl) tl.textContent = hmOf(S.frames[S.fi]) + ' ET'; };
  let deb = null;
  const fetchAt = () => { clearTimeout(deb); deb = setTimeout(() => loadReplay(S.frames[S.fi]).then(render), 120); };
  const r = $('#bbRange'); if (r) { r.oninput = () => { go(+r.value); fetchAt(); }; }
  const pv = $('#bbPrev'); if (pv) pv.onclick = () => { go(S.fi - 1); fetchAt(); };
  const nx = $('#bbNext'); if (nx) nx.onclick = () => { go(S.fi + 1); fetchAt(); };
  const pl = $('#bbPlay'); if (pl) pl.onclick = () => { if (S.play) stopPlay(); else startPlay(); render(); };
  onSeg('bbSub', (v) => { S.sub = v; render(); });
  $$('#bbRView .bb-log li[data-t]').forEach((li) => li.addEventListener('click', () => {
    const t = +li.dataset.t; if (!S.frames) return;
    let i = S.frames.findIndex((f) => f >= t); if (i < 0) i = S.frames.length - 1;
    S.fi = i; S.sub = 'now'; loadReplay(S.frames[i]).then(render);
  }));
}
function startPlay() {
  stopPlay();
  S.play = setInterval(async () => {
    if (!isActive() || S.tab !== 'replay' || !S.frames || S.busy) return;
    if (S.fi >= S.frames.length - 1) { stopPlay(); render(); return; }
    S.fi += 1; await loadReplay(S.frames[S.fi]); render();
  }, 900);
}
function stopPlay() { if (S.play) clearInterval(S.play); S.play = null; }

// the little "i" explainers: one floating tip
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('.bb-i');
  let tip = document.getElementById('bbTip');
  if (!b) { if (tip && !e.target.closest('#bbTip')) tip.remove(); return; }
  e.preventDefault(); e.stopPropagation();
  const txt = (S.help || {})[b.dataset.help] || 'No explainer for this yet.';
  if (!tip) { tip = document.createElement('div'); tip.id = 'bbTip'; tip.setAttribute('role', 'tooltip'); document.body.appendChild(tip); }
  tip.textContent = txt;
  const r = b.getBoundingClientRect();
  tip.style.left = Math.max(8, Math.min(innerWidth - 300, r.left - 140)) + 'px';
  tip.style.top = (r.bottom + 8 + scrollY) + 'px';
}, true);

const CSS = `
#page-brain .bb-tabs .seg{max-width:100%}
.bb-wait{padding:20px 22px}.bb-wait.blk{border-color:color-mix(in srgb,var(--bad) 60%,transparent)}
.bb-eyebrow{font:650 11px var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--accent-2);display:flex;align-items:center;gap:6px}
.bb-big{font:600 22px/1.4 var(--sans);color:var(--ink);margin:10px 0 12px}
.bb-meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:16px}
.bb-pipe{display:grid;grid-template-columns:repeat(10,1fr);gap:4px;margin-top:6px}
.bb-node{position:relative;display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center;min-width:0}
.bb-dot{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font:700 13px var(--sans);border:2px solid var(--axis);color:var(--muted);background:var(--surface-2,#11151f);z-index:1}
.bb-nl{font:600 11px/1.25 var(--sans);color:var(--muted)}
.bb-link{position:absolute;top:17px;left:calc(50% + 17px);right:calc(-50% + 17px);height:2px;background:var(--axis)}
.bb-node.done .bb-dot{border-color:var(--good);color:var(--good);background:color-mix(in srgb,var(--good) 14%,transparent)}.bb-node.done .bb-link{background:var(--good)}
.bb-node.done .bb-nl{color:var(--ink-2)}
.bb-node.now .bb-dot{border-color:var(--accent);color:#fff;background:var(--accent);box-shadow:0 0 0 6px color-mix(in srgb,var(--accent) 22%,transparent),0 0 22px var(--accent);animation:bbPulse 1.8s ease-in-out infinite}
.bb-node.now .bb-nl{color:var(--ink);font-weight:750}
.bb-node.skip .bb-dot{border-style:dashed;opacity:.6}
@keyframes bbPulse{50%{box-shadow:0 0 0 10px color-mix(in srgb,var(--accent) 10%,transparent),0 0 30px var(--accent)}}
@media (prefers-reduced-motion:reduce){.bb-node.now .bb-dot{animation:none}}
.bb-grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.bb-grid2>.card{margin:0}
.bb-near{display:grid;grid-template-columns:1fr 1fr;gap:14px}.bb-sub{font:650 11px var(--sans);text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:6px}
.bb-nr{display:grid;grid-template-columns:1fr auto;gap:0 8px;padding:6px 0;border-bottom:1px solid var(--nx-line)}.bb-nr em{grid-column:1/-1;font-style:normal;font-size:12px}
.bb-watch{display:grid;grid-template-columns:1fr 1fr;gap:14px}.bb-w{border:1px solid var(--nx-line);border-radius:14px;padding:12px 14px}.bb-w.off{opacity:.55}
.bb-wh{display:flex;gap:10px;align-items:baseline;margin-bottom:8px;flex-wrap:wrap}
.bb-row{display:grid;grid-template-columns:22px 130px 1fr;gap:6px;align-items:start;padding:4px 0;font-size:13px}.bb-rl{font-weight:650}.bb-rt{color:var(--ink-2)}
.bb-wt{margin:8px 0 0;font-size:13px;color:var(--ink-2)}
.bb-ok{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:6px;font:800 12px var(--sans)}
.bb-ok.y{color:var(--good);background:color-mix(in srgb,var(--good) 16%,transparent)}.bb-ok.n{color:var(--bad);background:color-mix(in srgb,var(--bad) 16%,transparent)}.bb-ok.q{color:var(--muted)}
.bb-i{display:inline-grid;place-items:center;width:17px;height:17px;border-radius:50%;border:1px solid var(--axis);background:none;color:var(--muted);font:700 10px var(--sans);cursor:pointer;vertical-align:middle;padding:0;margin-left:2px}
.bb-i:hover{color:var(--ink);border-color:var(--accent)}
#bbTip{position:absolute;z-index:200;max-width:290px;padding:10px 12px;border-radius:12px;background:var(--surface-2,#151a24);border:1px solid var(--accent);color:var(--ink);font:500 13px/1.45 var(--sans);box-shadow:0 10px 30px rgba(0,0,0,.4)}
.bb-log{list-style:none;margin:0;padding:0}.bb-log li{display:grid;grid-template-columns:48px 76px 1fr;gap:8px;padding:7px 2px;border-bottom:1px solid var(--nx-line);font-size:13px;line-height:1.45}
.bb-log li[data-t]{cursor:default}#bbRView .bb-log li[data-t]{cursor:pointer}#bbRView .bb-log li[data-t]:hover{background:var(--nx-hover)}
.bb-lt{color:var(--muted)}.bb-lk{font:650 10.5px var(--sans);text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding-top:2px}
.bb-log li.k-rejected .bb-lk{color:var(--bad)}.bb-log li.k-entry .bb-lk,.bb-log li.k-exit .bb-lk,.bb-log li.k-trade .bb-lk{color:var(--good)}.bb-log li.k-armed .bb-lk,.bb-log li.k-tap .bb-lk{color:var(--gold)}
.bb-log li.k-stage .bb-lk{color:var(--accent-2)}
.bb-ladder{width:100%;height:auto;max-width:1100px;display:block}
.bb-tw{overflow-x:auto}.bb-tbl tr.tk td{opacity:.62}
.bb-setups{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}
.bb-setup{border:1px solid var(--nx-line);border-radius:16px;padding:14px 16px;background:color-mix(in srgb,var(--surface-2,#11151f) 60%,transparent)}
.bb-setup.st-filled{border-color:color-mix(in srgb,var(--good) 55%,transparent)}.bb-setup.st-armed,.bb-setup.st-tapped{border-color:color-mix(in srgb,var(--gold) 60%,transparent)}
.bb-setup header{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.bb-st{font-size:15px;font-weight:700}
.bb-why{margin:8px 0;font-size:13.5px;color:var(--ink)}
.bb-checks{list-style:none;margin:0;padding:0}.bb-checks li{display:grid;grid-template-columns:24px 190px 1fr;gap:6px;padding:5px 0;border-top:1px solid var(--nx-line);font-size:12.5px;align-items:start}
.bb-checks li.fail .bb-cl{color:var(--bad)}.bb-cl{font-weight:650}.bb-ct{color:var(--ink-2)}
.bb-plan{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;font-size:12.5px;color:var(--ink-2)}
.bb-math{margin:0;padding-left:20px}.bb-math li{display:grid;grid-template-columns:200px 110px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--nx-line);font-size:13.5px}
.bb-ml{font-weight:650}.bb-mt{color:var(--ink-2)}
.bb-rules{margin:12px 0 0;padding-left:20px;font-size:13px;color:var(--ink-2);line-height:1.7}
.bb-bar{position:relative;height:92px;margin:8px 30px 4px}.bb-track{position:absolute;left:0;right:0;top:40px;height:6px;border-radius:3px;background:linear-gradient(90deg,var(--bad),var(--axis),var(--good))}
.bb-tick{position:absolute;top:28px;transform:translateX(-50%);text-align:center}.bb-tick i{display:block;width:2px;height:30px;margin:0 auto;background:var(--ink-2)}
.bb-tick em{display:block;font:600 11px/1.3 var(--sans);font-style:normal;color:var(--ink-2);margin-top:2px;white-space:nowrap}.bb-tick.bad i{background:var(--bad)}.bb-tick.good i{background:var(--good)}.bb-tick.gold i{background:var(--gold)}
.bb-px{position:absolute;top:0;transform:translateX(-50%);text-align:center}.bb-px i{display:block;width:14px;height:14px;margin:0 auto;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent)}
.bb-px em{display:block;font:700 11px var(--sans);font-style:normal;color:var(--ink);white-space:nowrap;margin-bottom:2px;position:absolute;top:-16px;left:50%;transform:translateX(-50%)}
.bb-ban{margin-bottom:14px}
.bb-rhead{display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap}.bb-rhead p{flex:1;min-width:240px;margin:0}
.bb-scrub{display:flex;align-items:center;gap:8px;margin-top:12px}.bb-scrub input[type=range]{flex:1;accent-color:var(--accent);min-width:0}.bb-tl{min-width:76px;text-align:right}
details.bb-card summary{cursor:pointer;padding:4px 0}details.bb-card[open] summary{margin-bottom:12px}
@media (max-width:900px){.bb-grid2,.bb-watch,.bb-near{grid-template-columns:1fr}.bb-setups{grid-template-columns:1fr}
  .bb-pipe{grid-template-columns:repeat(5,1fr);row-gap:14px}.bb-node:nth-child(5) .bb-link{display:none}
  .bb-big{font-size:19px}.bb-nl{font-size:10px}.bb-ladder{min-width:720px}.bb-checks li{grid-template-columns:24px 1fr}.bb-checks li .bb-ct{grid-column:2}
  .bb-math li{grid-template-columns:1fr auto}.bb-math li .bb-mt{grid-column:1/-1}.bb-row{grid-template-columns:22px 1fr}.bb-row .bb-rt{grid-column:2}
  .bb-log li{grid-template-columns:44px 1fr}.bb-log li .bb-lk{display:none}.bb-bar{margin:8px 22px 4px}}
`;
function installCss() { if (document.getElementById('bb-css')) return; const s = document.createElement('style'); s.id = 'bb-css'; s.textContent = CSS; document.head.appendChild(s); }

async function show() {
  installCss();
  if (!S.live && !S.liveErr) { render(); await loadLive(); }
  if (S.live?.empty && S.tab !== 'replay' && !S.days) { /* stay: the empty card offers the replay */ }
  render();
  clearInterval(S.timer);
  S.timer = setInterval(async () => {
    if (!isActive() || document.hidden) return;
    if (S.tab === 'replay') return;
    if (document.querySelector('#bbTip')) return;          // do not redraw under an open explainer
    await loadLive();
    if (S.tab === 'log' && S.live && !S.live.empty) await loadFullLog(S.live.day);
    if (isActive() && S.tab !== 'replay') render();
  }, 15000);
}
export const brain = { show };
