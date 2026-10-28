// Real accounts renderer (2026-10-28, owner: "improve dashboard, clarity, features, organization"; both MFFU accounts
// trade for real since today). Shared by the phone app (tools/web_public/real.js: the Home "Today" cards + #/real) and the
// PC dashboard (web_next/js/next/real.js: the Home "Today" cards + the "Real results" page); web_next/js/next/realcore.js
// is a byte-identical copy of tools/web_public/realcore.js (tests/test_real_ui.py checks it).
// Data: the live board (engine/live_board.py: PC GET /api/next/board, phone data.json / live.json "board"), its "real"
// block = the REAL account trades only (PC ledger + exits, never the paper run), the ledger check and Zlarior's backtest
// cone. Every $ on these cards is the account's own; a paper figure is always labelled PAPER next to its REAL twin.
// Read-only: nothing here talks to the bot; the buttons filter, expand a row or export a CSV.
//   RealUI.today(B, o)      Home: one card per REAL account (state, today's real trades, balance, room to the floor,
//                           $ to the target, daily loss, eval day N of 10 + pass ETA, next window, health score) + the
//                           Strategy 3 slot, ledger-check banners, the LIT vs ATLAS conflict line, "What happened today"
//   RealUI.safety(B, o)     Home: one safety card (floor + daily loss of both, orders confirmed, refused orders, feed,
//                           NinjaTrader, clock, conflict, kill switch link)
//   RealUI.results(B, o)    the Real results page: KPIs, vs backtest (cone / pace / odds), equity curves, daily P&L,
//                           R distribution, streaks, $ by strategy, this week's report card, incidents, the real trade log
//                           with running P&L, a timeline per trade and a CSV export
//   RealUI.wire(root, B, o) filters, row timelines, CSV
//   RealUI.realOf(row, B)   the REAL twin of a paper trade: "REAL: 3 micros, +$1,662" or "REAL: no order on the account"
//   RealUI.csv(rows)        the real trades as CSV text
// opts: {go: (id) => 'data-goto="id"' | 'data-go="id"', where: 'pc' | 'phone', download: (name, text) => void}
(function () {
  'use strict';
  if (typeof window === 'undefined') return;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ok = (v) => v != null && v !== '' && !isNaN(v);
  const nowS = () => Date.now() / 1000;
  const usd = (v, d = 0) => !ok(v) ? '—' : (v < 0 ? '−' : '') + '$' + Math.abs(+v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const susd = (v, d = 0) => !ok(v) ? '—' : (v > 0 ? '+' : '') + usd(v, d);
  const px = (v) => ok(v) ? (+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const pct = (v) => ok(v) ? (+v).toFixed(0) + '%' : '—';
  const fR = (v) => !ok(v) ? '—' : (v > 0 ? '+' : '') + (+v).toFixed(2) + 'R';
  const cl = (v) => !ok(v) ? '' : v > 0 ? 'up' : v < 0 ? 'dn' : '';
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const ETF = { timeZone: 'America/New_York', hour12: false };
  const hm = (t) => { if (!ok(t)) return '—'; try { return new Date(t * 1000).toLocaleTimeString('en-US', { ...ETF, hour: '2-digit', minute: '2-digit' }); } catch (e) { return '—'; } };
  const dhm = (t) => { if (!ok(t)) return ''; try { return new Date(t * 1000).toLocaleString('en-US', { ...ETF, weekday: 'short', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); } catch (e) { return ''; } };
  const etDay = (t) => { try { return new Date(t * 1000).toLocaleDateString('en-CA', { timeZone: 'America/New_York' }); } catch (e) { return ''; } };
  const dur = (s) => { s = Math.max(0, Math.round(s)); if (s < 90) return s + ' s'; const m = Math.round(s / 60); if (m < 90) return m + ' min'; const h = Math.floor(m / 60); return h < 48 ? h + ' h ' + (m % 60) + ' min' : Math.round(h / 24) + ' d'; };
  const NAMES = { lit: 'Zlarior', atlas: 'ATLAS' };
  const PLAN = { lit: { start: 50000, target: 3000, mll: 2000, dll: 1000, size: '50K' }, atlas: { start: 25000, target: 1500, mll: 1000, dll: 600, size: '25K' } };
  const KIND = { TARGET: 'target', STOP: 'stop', BE: 'breakeven', EOD: 'flat 15:55', FLAT: 'flat', CUT_T15: '15-min cut', CUT: '15-min cut', T15: '15-min cut', OPEN: 'open' };
  const how = (r) => r.open ? 'open' : KIND[String(r.exit || '').toUpperCase()] || String(r.exit || '').toLowerCase() || '—';
  const chip = (t, k) => `<span class="rc-chip ${k || ''}">${esc(t)}</span>`;
  // plain-language glossary: every term gets a tap / hover explanation
  const GLOSS = {
    'Room to floor': 'How much the account can still lose before MFFU closes the eval (the trailing max-loss floor). Below 25% the bot sizes down.',
    'To target': 'Profit still needed to pass the eval (50K: +$3,000, 25K: +$1,500).',
    'Daily loss': 'Today\'s losses against the daily loss limit (50K $1,000, 25K $600). At the limit no new trade today.',
    'Eval day': 'Trading sessions used on this eval. Goal: pass within 10 sessions (2 weeks), never more than 15.',
    'R': 'Result in units of the risk: -1R = a full stop-out, +2R = twice the risk won.',
    'Real': 'What happened on the MFFU account itself (the PC bot\'s ledger + NinjaTrader fills).',
    'Paper': 'What the strategy did in its own simulation on the same bars. Its size and $ are NOT the account\'s.',
    'Health score': 'One number for the account: 100 = all good. Points come off for a thin room to the floor, a guard that blocks entries, a red bot light or old data.',
    'Pass ETA': 'Sessions still needed at the 2026 H2 backtest pace ($ per session on the eval sizing). A guide, not a promise.',
    'Backtest band': 'Where 90% of 4,000 simulated 2026 H2 paths were after the same number of sessions (p5-p95; the darker band p25-p75).',
  };
  const tip = (t, label) => `<abbr class="rc-tip" tabindex="0" title="${esc(GLOSS[t] || '')}">${esc(label || t)}</abbr>`;
  const goA = (o, id) => (o && o.go ? o.go(id) : `data-goto="${id}"`);
  const short = (n) => { const s = String(n || ''); const m = s.match(/(\d{3,})$/); return m ? '…' + m[1].slice(-4) : s; };

  // ---------------------------------------------------------------- data helpers
  const accOf = (B, k) => (B && B[k] && !B[k].error ? B[k] : null);
  function realRows(B) {
    const R = B && B.real && Array.isArray(B.real.trades) ? B.real.trades : (B && Array.isArray(B.trades) ? B.trades.filter((r) => r.src === 'live') : []);
    return R.slice().sort((x, y) => (+x.entry_t || 0) - (+y.entry_t || 0));
  }
  const today = (B) => (B && B.today) || etDay(nowS());
  const checksOf = (B, k) => ((B && B.real && B.real.checks) || []).filter((c) => !k || c.acct === k);
  function refused(a) {
    const O = (a && a.orders) || [];
    const filled = new Set(O.filter((o) => o.side === 'exit' || (o.ok === true && o.side !== 'exit')).map((o) => o.entry_t));
    return O.filter((o) => o.ok === false && o.side !== 'exit' && !filled.has(o.entry_t));
  }
  // the REAL twin of a paper trade (same account, same side, entry within 30 min)
  function realOf(r, B) {
    if (!r || r.src === 'live') return null;
    const R = realRows(B).filter((x) => x.acct === r.acct && x.side === r.side && ok(x.entry_t) && ok(r.entry_t) && Math.abs(x.entry_t - r.entry_t) <= 1800);
    if (R.length) { const x = R[0]; return { real: x, text: `REAL: ${x.qty ?? '?'} micros, ${x.open ? 'open' : susd(x.usd)}` }; }
    const acc = accOf(B, r.acct), start = acc && acc.eval_start;
    if (start && String(r.day || '') >= String(start)) return { real: null, text: 'REAL: no order on the account' };
    return { real: null, text: 'REAL: before the real account started' };
  }
  function sessionsBetween(a, b) {               // weekday sessions from day a to day b, both included
    if (!a || !b || b < a) return 0;
    let n = 0; const d = new Date(a + 'T12:00:00Z'), z = new Date(b + 'T12:00:00Z');
    for (let i = 0; i < 400 && d <= z; i++) { const w = d.getUTCDay(); if (w > 0 && w < 6) n++; d.setUTCDate(d.getUTCDate() + 1); }
    return n;
  }
  function perSession(B, k) {
    const E = (((B && B.progress) || {})[k] || {}).expected || {};
    return ok(E.per_session) ? +E.per_session : ok(E.per_month) ? +E.per_month / 21 : null;
  }
  function eta(B, a) {
    const ps = perSession(B, a.id);
    if (!ok(a.to_target) || a.to_target <= 0 || !ps || ps <= 0) return null;
    const n = Math.ceil(a.to_target / ps), at = (ok(a.session) ? +a.session : 0) + n;
    return { n, at, ps, k: at <= 10 ? 'good' : at <= 15 ? 'warn' : 'bad' };
  }
  function score(B, a) {
    if (!a) return { n: 0, why: ['no data'], k: 'bad' };
    const why = []; let n = 100;
    const st = String(a.status || '').toLowerCase();
    if (/fail|lost/.test(st)) return { n: 0, why: ['eval ' + st], k: 'bad' };
    const chk = checksOf(B, a.id);
    const rf = ok(a.room_frac) ? +a.room_frac : null;
    if (rf != null && rf < 0.25) { n -= chk.length ? 15 : 35; why.push(chk.length ? 'room thin by the ledger (may be a ledger error)' : 'room to the floor under 25%'); }
    else if (rf != null && rf < 0.5) { n -= 15; why.push('room to the floor under 50%'); }
    // the 50K's floor alert is global ("both") on the board: it does not cost ATLAS points
    const blk = (B.blocks || []).filter((b) => a.id === 'lit' || !/near the floor/i.test(b.text || '')).length + (a.blocks || []).length;
    if (blk) { n -= Math.min(40, 20 * blk); why.push(`${blk} guard${blk > 1 ? 's' : ''} blocking entries`); }
    const bad = ((B.health || {}).items || []).filter((x) => x.ok === false);
    if (bad.length) { n -= Math.min(30, 10 * bad.length); why.push(bad.map((x) => x.label).join(', ') + ' red'); }
    const warn = ((B.health || {}).items || []).filter((x) => x.warn);
    if (warn.length) { n -= 5; why.push(warn.map((x) => x.label).join(', ') + ' to watch'); }
    if (ok(B.data_t) && nowS() - B.data_t > 900) { n -= 15; why.push('data ' + dur(nowS() - B.data_t) + ' old'); }
    if (refused(a).length) { n -= 10; why.push(`${refused(a).length} refused order${refused(a).length > 1 ? 's' : ''}`); }
    if (chk.length) why.push('ledger check open');
    if (B.running === false) { n -= 20; why.push('bot stopped'); }
    n = Math.max(0, Math.min(100, n));
    return { n, why: why.length ? why : ['all good'], k: n >= 80 ? 'good' : n >= 55 ? 'warn' : 'bad' };
  }

  // ---------------------------------------------------------------- small parts
  const bar = (f, k) => `<div class="rc-bar ${k || ''}"><i style="width:${(clamp(f || 0) * 100).toFixed(1)}%"></i></div>`;
  function gauge(label, val, f, k, sub) {
    return `<div class="rc-g"><div class="rc-gh"><span>${label}</span><b class="${k === 'bad' ? 'dn' : ''}">${val}</b></div>${bar(f, k)}${sub ? `<div class="rc-gs">${sub}</div>` : ''}</div>`;
  }
  function win(w) {
    if (!w) return '—';
    if (ok(w.open_t)) {
      const n = nowS(), t = n < w.open_t ? `opens in ${dur(w.open_t - n)}` : n < w.close_t ? `open · closes in ${dur(w.close_t - n)}` : 'closed';
      return `<b class="rc-cd" data-bd-open="${w.open_t}" data-bd-close="${w.close_t}">${esc(t)}</b> <em>${esc(w.who ? w.who + ' · ' : '')}${esc(w.hours || '')}</em>`;
    }
    return `<b>${esc(w.text || '—')}</b>`;
  }
  function stateChips(B, a) {
    const badge = String(a.badge || '').toUpperCase();
    const live = /LIVE|EVAL|REAL/.test(badge) && !/SIM\b|PAPER/.test(badge);
    const out = [chip(live ? 'REAL ACCOUNT' : badge || 'PAPER', live ? 'good' : badge ? 'warn' : '')];
    out.push(B.running === false ? chip('bot stopped', 'bad') : B.running ? chip('bot running', 'good') : '');
    if (a.position) out.push(chip('in a trade', 'acc'));
    return out.join('');
  }
  function posLine(p, acct) {
    if (!p) return '';
    const side = p.side || (+p.dir > 0 ? 'LONG' : 'SHORT'), d = side === 'LONG' ? 1 : -1, q = +p.qty || 0;
    const toStop = ok(p.stop) && ok(p.entry) ? (p.stop - p.entry) * d * 2 * q : null;
    const toTgt = ok(p.target) && ok(p.entry) ? (p.target - p.entry) * d * 2 * q : null;
    const rNow = ok(p.unrealized_r) ? p.unrealized_r : ok(p.unrealized_usd) && toStop ? p.unrealized_usd / Math.abs(toStop) : null;
    return `<div class="rc-pos">${chip(side, d > 0 ? 'good' : 'bad')}<span><b>${esc(q || '?')} micros</b> at ${px(p.entry)}${p.strategy ? ' · ' + esc(p.strategy) : ''}${p.be ? ' · at breakeven' : ''}</span>
      <div class="rc-posg"><span>now <b class="${cl(p.unrealized_usd)}">${susd(p.unrealized_usd)}</b> ${ok(rNow) ? `<em>${fR(rNow)}</em>` : ''}</span><span>to stop <b class="dn">${susd(toStop)}</b> <em>${px(p.stop)}</em></span><span>to target <b class="up">${susd(toTgt)}</b> <em>${px(p.target)}</em></span></div></div>`;
  }
  function tradeLine(r) {
    return `<li class="rc-tr">${chip(r.side || '', r.side === 'LONG' ? 'good' : 'bad')}<span class="rc-trm"><b>${esc(r.qty ?? '?')} micros</b>${r.member ? ' · ' + esc(r.member) : ''} <em class="mono">${hm(r.entry_t)} ${px(r.entry)} → ${r.open ? 'open' : px(r.exit_px)}</em></span>
      <span class="rc-trh">${esc(how(r))} <em class="${cl(r.r)}">${fR(r.r)}</em></span><b class="rc-tru mono ${cl(r.usd)}">${r.open ? 'open' : susd(r.usd, 2)}</b></li>`;
  }
  function whyNone(B, a) {
    const blk = (B.blocks || []).filter((b) => a.id === 'lit' || !/near the floor/i.test(b.text || '')).concat(a.blocks || []);
    if (blk.length) return `Blocked: ${blk[0].text}`;
    if (a.done_today) return 'Done for today (its daily trade limit).';
    return a.waiting || 'Watching for a setup.';
  }

  // ---------------------------------------------------------------- Today: one real account
  function card(B, k, o) {
    const a = accOf(B, k), P = PLAN[k];
    if (!a) return `<section class="rc-card rc-acct ${k}"><div class="rc-h"><div class="rc-eye">${NAMES[k]} · ${P.size}</div></div><p class="rc-note">No data for this account yet. It appears after the PC bot reports.</p></section>`;
    if (k === 'atlas' && a.configured === false) return `<section class="rc-card rc-acct atlas"><div class="rc-h"><div class="rc-eye">ATLAS · 25K</div>${chip('not set up', 'warn')}</div><p class="rc-note">Account B is not on in the PC bot.</p></section>`;
    const td = today(B), R = realRows(B).filter((r) => r.acct === k && String(r.day) === td);
    const closed = R.filter((r) => !r.open && ok(r.usd)), realToday = closed.reduce((s, r) => s + +r.usd, 0) + (a.position && ok(a.position.unrealized_usd) ? +a.position.unrealized_usd : 0);
    const dayPnl = ok(a.today_pnl) ? +a.today_pnl : realToday;
    const mll = a.mll || P.mll, room = a.room, rf = ok(a.room_frac) ? a.room_frac : ok(room) ? room / mll : null;
    const chk = checksOf(B, k);
    const roomK = rf == null ? '' : rf < 0.25 ? 'bad' : rf < 0.5 ? 'warn' : 'good';
    const tgt = ok(a.target_balance) ? a.target_balance - P.start : P.target, prof = ok(a.profit) ? +a.profit : null;
    const dll = a.dll || P.dll, used = ok(a.dll_used) ? +a.dll_used : Math.max(0, -Math.min(0, dayPnl));
    const E = eta(B, a), S = score(B, a), funded = a.stage === 'funded';
    const sess = ok(a.session) ? +a.session : null;
    const altRoom = chk.length && ok(chk[0].room_if_error) ? `<div class="rc-gs warn">about <b>${usd(chk[0].room_if_error)}</b> if the ${esc(chk[0].day)} ${susd(chk[0].usd)} is a ledger error (no real trade that day)</div>` : '';
    return `<section class="rc-card rc-acct ${k}${S.k === 'bad' ? ' bad' : ''}" aria-label="${NAMES[k]} today">
      <div class="rc-h"><div class="rc-eye">${NAMES[k]} · ${P.size}<em>${esc(a.method || '')}${a.broker ? ' · ' + esc(short(a.broker)) : ''}</em></div><div class="rc-chips">${stateChips(B, a)}</div></div>
      <div class="rc-top"><div class="rc-big"><span>Today · ${tip('Real', 'real')}</span><b class="${cl(dayPnl)}">${susd(dayPnl, 2)}</b><em>${R.length} of ${a.max_day || (k === 'lit' ? 1 : 2)} trade${(a.max_day || 1) === 1 ? '' : 's'} today</em></div>
        <div class="rc-score ${S.k}" title="${esc(S.why.join(' · '))}"><b>${S.n}</b><span>${tip('Health score', 'health')}</span></div></div>
      ${posLine(a.position, k)}
      ${R.filter((r) => !r.open).length ? `<ul class="rc-trs">${R.filter((r) => !r.open).map(tradeLine).join('')}</ul>` : a.position ? '' : `<p class="rc-why"><b>No trade yet today.</b> ${esc(whyNone(B, a))}</p>`}
      <div class="rc-kv"><div><span>Balance</span><b>${usd(a.balance, 2)}</b></div><div><span>${tip('Eval day')}</span><b>${funded ? 'funded' : sess != null ? `${sess} of ${a.sessions || 10}` : '—'}</b>${E && !funded ? `<em class="${E.k}">${tip('Pass ETA', `pass ≈ day ${E.at}`)}</em>` : ''}</div>
        <div><span>Next window</span>${win(a.window)}</div></div>
      ${gauge(tip('Room to floor'), usd(room), rf, roomK, `floor ${usd(a.floor, 2)} · of ${usd(mll)}${rf != null && rf < 0.25 && !chk.length ? ' · thin: the bot sizes down' : ''}`)}${altRoom}
      ${gauge(tip('To target'), ok(a.to_target) ? (a.to_target <= 0 ? 'reached' : usd(a.to_target)) : '—', prof != null && tgt ? prof / tgt : 0, 'acc', `${susd(prof)} of +${usd(tgt)}${E ? ` · ≈ ${E.n} more session${E.n > 1 ? 's' : ''} at the backtest pace (${usd(E.ps)} a session)` : ''}`)}
      ${gauge(tip('Daily loss'), `${usd(used)} of ${usd(dll)}`, used / dll, used / dll > 0.75 ? 'bad' : used / dll > 0.4 ? 'warn' : 'good', used >= dll ? 'limit reached: no new trade today' : `${usd(dll - used)} left today`)}
      ${S.n < 100 ? `<p class="rc-scw">${esc(S.why.join(' · '))}</p>` : ''}
      <div class="rc-f"><button type="button" class="rc-btn" ${goA(o, k === 'lit' ? 'zlarior' : 'atlas')}>Open ${NAMES[k]}</button><button type="button" class="rc-btn" ${goA(o, 'real')}>Real results</button></div>
    </section>`;
  }
  function slot3(o) {
    return `<section class="rc-card rc-slot" aria-label="Strategy 3 (research)"><div class="rc-h"><div class="rc-eye">Strategy 3 (research)<em>free slot · paper only</em></div>${chip('no account', '')}</div>
      <p class="rc-note">Room for a third strategy. It gets a real account only after the research proves it (better in 2026 and in 2021-25, 2-4 trades a week, a 2-week eval pass rate) and you buy the account. Until then nothing routes here.</p>
      <div class="rc-f"><button type="button" class="rc-btn" ${goA(o, 'lab')}>See the research</button></div></section>`;
  }
  function conflict(B) {
    const L = accOf(B, 'lit'), A = accOf(B, 'atlas');
    const d = (p) => (p ? ((p.side || '') === 'LONG' || +p.dir > 0 ? 1 : -1) : 0);
    if (L && A && L.position && A.position && d(L.position) !== d(A.position)) return { k: 'bad', t: `Opposite positions now: Zlarior ${L.position.side || ''} and ATLAS ${A.position.side || ''}. They cancel each other out; check Bot Control.` };
    const td = today(B), R = realRows(B).filter((r) => String(r.day) === td);
    const sides = (k) => new Set(R.filter((r) => r.acct === k).map((r) => r.side));
    const ls = sides('lit'), as = sides('atlas');
    if ([...ls].some((s) => as.size && !as.has(s))) return { k: 'warn', t: `Today Zlarior traded ${[...ls].join('/')} and ATLAS ${[...as].join('/')}: opposite directions on the same day (not at the same time).` };
    return { k: 'good', t: 'No conflict: the accounts are not on opposite sides (ATLAS never enters against an open Zlarior trade).' };
  }
  function events(B) {
    const td = today(B), ev = [];
    for (const k of ['lit', 'atlas']) {
      const a = accOf(B, k); if (!a) continue;
      for (const o of a.orders || []) {
        if (!ok(o.t) || etDay(o.t) !== td) continue;
        const who = NAMES[k] + (o.src ? ' · ' + ({ ema_lon_vix: 'EMA', macd_sweep: 'MACD', sr_nyreclaim: 'S/R' }[o.src] || o.src) : '');
        if (o.side === 'exit') ev.push({ t: o.t, k: cl(o.pnl) === 'up' ? 'good' : 'bad', who, text: `exit ${KIND[String(o.reason || '').toUpperCase()] || o.reason || ''}: ${susd(o.pnl, 2)} (${o.qty ?? '?'} micros)` });
        else if (o.side === 'modify') ev.push({ t: o.t, k: '', who, text: 'stop moved (breakeven)' });
        else if (o.ok === false) ev.push({ t: o.t, k: refused(a).includes(o) ? 'bad' : 'warn', who, text: `${o.side} ${o.qty ?? '?'} micros: ${refused(a).includes(o) ? 'REFUSED' : 'sent, fill came later'}${o.error ? ' · ' + o.error : ''}` });
        else ev.push({ t: o.t, k: 'acc', who, text: `${o.side === 'buy' ? 'BUY' : 'SELL'} ${o.qty ?? '?'} micros sent and accepted` });
      }
    }
    for (const c of checksOf(B)) ev.push({ t: null, k: 'warn', who: NAMES[c.acct], text: 'Ledger check: ' + c.text });
    return ev.sort((x, y) => (+y.t || 9e12) - (+x.t || 9e12));
  }
  function eventsCard(B) {
    const E = events(B);
    return `<section class="rc-card rc-ev" aria-label="What happened today"><div class="rc-h"><div class="rc-eye">What happened today<em>orders, fills, exits, checks · newest first</em></div></div>
      ${E.length ? `<ul class="rc-evl">${E.slice(0, 14).map((e) => `<li class="${e.k}"><span class="mono">${e.t ? hm(e.t) : '!'}</span><b>${esc(e.who)}</b><span>${esc(e.text)}</span></li>`).join('')}</ul>` : '<p class="rc-note">Nothing yet today: no order sent on either account.</p>'}</section>`;
  }
  function checkBanners(B) {
    return checksOf(B).map((c) => `<div class="rc-ban warn"><i></i><span><b>Ledger check (${esc(NAMES[c.acct] || c.acct)}):</b> ${esc(c.text)}</span></div>`).join('');
  }
  function today_(B, o) {
    css(); o = o || {};
    if (!B || B.error) return `<section class="rc-wrap"><p class="rc-note">${esc((B && B.error) || 'Waiting for the PC bot\'s first report.')}</p></section>`;
    const C = conflict(B), age = ok(B.data_t) ? nowS() - B.data_t : null;
    return `<section class="rc-wrap rc-today" aria-label="Today on the real accounts">
      <div class="rc-hd"><div><div class="rc-eyeb">Today · real accounts</div><h2>${esc(new Date(today(B) + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' }))}</h2></div>
        <span class="rc-age ${age != null && age > 900 ? 'warn' : ''}">data <b data-bd-age="${esc(B.data_t || '')}">${age != null ? esc(dur(age)) : '—'}</b> old · real $ only</span></div>
      ${checkBanners(B)}
      <div class="rc-grid">${card(B, 'lit', o)}${card(B, 'atlas', o)}${slot3(o)}</div>
      <div class="rc-ban ${C.k}"><i></i><span><b>LIT vs ATLAS:</b> ${esc(C.t)}</span></div>
      ${eventsCard(B)}
    </section>`;
  }

  // ---------------------------------------------------------------- Safety card (Home)
  function safety(B, o) {
    css(); o = o || {};
    if (!B || B.error) return '';
    const H = {}; for (const x of ((B.health || {}).items || [])) H[x.key] = x;
    const row = (lv, k, v, sub) => `<div class="rc-sr ${lv}"><i></i><span>${k}</span><b>${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
    const lvOf = (x) => (!x ? 'idle' : x.ok === false ? 'bad' : x.warn ? 'warn' : x.ok ? 'good' : 'idle');
    const rows = [];
    for (const k of ['lit', 'atlas']) {
      const a = accOf(B, k); if (!a) continue;
      const P = PLAN[k], rf = ok(a.room_frac) ? a.room_frac : null, chk = checksOf(B, k);
      rows.push(row(rf == null ? 'idle' : rf < 0.25 ? (chk.length ? 'warn' : 'bad') : rf < 0.5 ? 'warn' : 'good', `${NAMES[k]} floor`, usd(a.room) + ' left', chk.length ? 'ledger check open' : `floor ${usd(a.floor)}`));
      const used = ok(a.dll_used) ? +a.dll_used : Math.max(0, -Math.min(0, +a.today_pnl || 0)), dll = a.dll || P.dll;
      rows.push(row(used >= dll ? 'bad' : used / dll > 0.5 ? 'warn' : 'good', `${NAMES[k]} daily loss`, `${usd(used)} / ${usd(dll)}`));
      const O = (a.orders || []).filter((x) => ok(x.t) && etDay(x.t) === today(B) && x.side !== 'exit' && x.side !== 'modify'), rf2 = refused(a).filter((x) => etDay(x.t) === today(B));
      rows.push(row(rf2.length ? 'bad' : 'good', `${NAMES[k]} orders`, O.length ? `${O.length - rf2.length} of ${O.length} confirmed` : 'none today', rf2.length ? esc(rf2[0].error || 'refused') : ''));
    }
    const C = conflict(B);
    rows.push(row(C.k, 'LIT vs ATLAS', C.k === 'good' ? 'no conflict' : C.k === 'bad' ? 'opposite now' : 'opposite today'));
    for (const [k, lab] of [['nt', 'NinjaTrader'], ['age_1m_s', 'Feed (1m bars)'], ['clock', 'PC clock'], ['heartbeat', 'Check-in'], ['error', 'Last error'], ['poll_ms', 'Poll time']]) if (H[k]) rows.push(row(lvOf(H[k]), lab, esc(H[k].value), esc(H[k].fix || '')));
    const bad = rows.filter((r) => r.includes('rc-sr bad')).length, warn = rows.filter((r) => r.includes('rc-sr warn')).length;
    return `<section class="rc-wrap"><section class="rc-card rc-safe" aria-label="Safety"><div class="rc-h"><div class="rc-eye">Safety<em>floors, daily loss, orders, NinjaTrader, feed, clock</em></div>${chip(bad ? `${bad} red` : warn ? `${warn} to watch` : 'all green', bad ? 'bad' : warn ? 'warn' : 'good')}</div>
      <div class="rc-srs">${rows.join('')}</div>
      <div class="rc-f">${o.where === 'pc' ? `<button type="button" class="rc-btn bad" ${goA(o, 'botctl')}>Kill switch (Bot Control)</button>` : '<span class="rc-note">Kill switch: on the PC, Bot Control > HOLD TO KILL (this app is read-only).</span>'}<button type="button" class="rc-btn" ${goA(o, 'board')}>Live board</button></div></section></section>`;
  }

  // ---------------------------------------------------------------- Results page
  const F = { acct: 'all', open: null };
  function stats(R) {
    const C = R.filter((r) => !r.open && ok(r.usd));
    const w = C.filter((r) => r.usd > 0), l = C.filter((r) => r.usd < 0);
    const gw = w.reduce((s, r) => s + +r.usd, 0), gl = -l.reduce((s, r) => s + +r.usd, 0);
    let cur = 0, curK = '', maxL = 0, maxW = 0, run = 0, runK = '';
    for (const r of C) { const k = r.usd > 0 ? 'W' : r.usd < 0 ? 'L' : 'B'; if (k === runK) run++; else { runK = k; run = 1; } if (k === 'L') maxL = Math.max(maxL, run); if (k === 'W') maxW = Math.max(maxW, run); }
    cur = run; curK = runK;
    const Rs = C.filter((r) => ok(r.r)).map((r) => +r.r);
    return { n: C.length, open: R.length - C.length, wins: w.length, losses: l.length, win: C.length ? 100 * w.length / C.length : null, net: gw - gl,
      pf: gl ? gw / gl : w.length ? Infinity : null, avgW: w.length ? gw / w.length : null, avgL: l.length ? -gl / l.length : null,
      avgR: Rs.length ? Rs.reduce((s, x) => s + x, 0) / Rs.length : null, best: C.reduce((b, r) => (!b || r.usd > b.usd ? r : b), null),
      worst: C.reduce((b, r) => (!b || r.usd < b.usd ? r : b), null), cur, curK, maxL, maxW, Rs };
  }
  const kpi = (k, v, sub, c) => `<div class="rc-kpi"><span>${k}</span><b class="${c || ''}">${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
  function kpis(S) {
    return `<div class="rc-kpis">${kpi('Real net', susd(S.net, 2), `${S.n} closed trade${S.n === 1 ? '' : 's'}${S.open ? ' + ' + S.open + ' open' : ''}`, cl(S.net))}
      ${kpi('Win rate', S.win == null ? '—' : pct(S.win), `${S.wins} won · ${S.losses} lost`)}${kpi('Profit factor', S.pf == null ? '—' : S.pf === Infinity ? '∞' : S.pf.toFixed(2))}
      ${kpi(tip('R', 'Average R'), fR(S.avgR))}${kpi('Avg win / loss', `${susd(S.avgW)} / ${susd(S.avgL)}`)}
      ${kpi('Streak now', S.curK ? `${S.cur} ${S.curK === 'W' ? 'win' : S.curK === 'L' ? 'loss' : 'BE'}${S.cur > 1 ? (S.curK === 'L' ? 'es' : 's') : ''}` : '—', `longest: ${S.maxW} won · ${S.maxL} lost in a row`)}
      ${kpi('Best / worst', `${susd(S.best && S.best.usd)} / ${susd(S.worst && S.worst.usd)}`)}</div>`;
  }
  // equity by eval session: the real line (the eval's booked days for Zlarior, its real trades for ATLAS) over the backtest
  function curve(B, k) {
    const a = accOf(B, k); if (!a) return '';
    const start = a.eval_start || (realRows(B).find((r) => r.acct === k) || {}).day;
    let pts = [[0, 0]];
    if (k === 'lit' && (a.days || []).length) {
      let c = 0; for (const [d, v] of a.days) { if (d === '0000-00-00' || (start && d < start)) continue; c += +v || 0; pts.push([sessionsBetween(start, d), c]); }
    } else {
      let c = 0; for (const r of realRows(B).filter((x) => x.acct === k && !x.open && ok(x.usd))) { c += +r.usd; pts.push([sessionsBetween(start, String(r.day)), c]); }
    }
    const nowN = Math.max(1, sessionsBetween(start, today(B)));
    const cone = k === 'lit' && B.real && B.real.cone && B.real.cone.rows ? B.real.cone.rows : null;
    const ps = perSession(B, k);
    const nMax = Math.max(10, nowN + 2, ...pts.map((p) => p[0]));
    const rows = cone ? cone.filter((r) => r[0] <= nMax) : null;
    const ys = pts.map((p) => p[1]).concat(rows ? rows.flatMap((r) => [r[1], r[5]]) : []).concat(ps ? [ps * nMax, 0] : [0]);
    const tgt = (a.target_balance || PLAN[k].start + PLAN[k].target) - PLAN[k].start, flo = -(a.mll || PLAN[k].mll);
    let lo = Math.min(...ys, flo * 0.6), hi = Math.max(...ys, tgt * 0.6); const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    const W = 520, Hh = 230, L = 62, Rr = 10, T = 12, Bt = 24;
    const X = (n) => L + (W - L - Rr) * (n / nMax), Y = (v) => T + (Hh - T - Bt) * (1 - (v - lo) / (hi - lo || 1));
    const area = (i, j) => rows ? `M${rows.map((r) => `${X(r[0]).toFixed(1)},${Y(r[i]).toFixed(1)}`).join('L')}L${rows.slice().reverse().map((r) => `${X(r[0]).toFixed(1)},${Y(r[j]).toFixed(1)}`).join('L')}Z` : '';
    const line = (P) => P.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');
    const hl = (v, c, t) => v >= lo && v <= hi ? `<line x1="${L}" x2="${W - Rr}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" class="${c}"/><text x="${W - Rr - 4}" y="${(Y(v) - 4).toFixed(1)}" text-anchor="end" class="rc-ax ${c}">${t}</text>` : '';
    const ticks = [flo, 0, tgt].filter((v) => v >= lo && v <= hi).map((v) => `<text x="${L - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end" class="rc-ax">${esc(susd(v))}</text>`).join('');
    const xt = [0, 5, 10, 15, 20].filter((n) => n <= nMax).map((n) => `<text x="${X(n).toFixed(1)}" y="${Hh - 6}" text-anchor="middle" class="rc-ax">${n}</text>`).join('');
    const last = pts[pts.length - 1];
    let verdict = '';
    if (rows && last[0] >= 1) {
      const r = rows.find((x) => x[0] === last[0]) || rows[rows.length - 1];
      verdict = last[1] < r[1] ? ['bad', `below the backtest band (under p5 after ${last[0]} sessions): investigate`] : last[1] < r[2] ? ['warn', `in the lower part of the band (p5-p25 after ${last[0]} sessions): a normal bad stretch, watch it`] : last[1] > r[4] ? ['good', `above the middle of the band (over p75)`] : ['good', `inside the middle of the backtest band (p25-p75)`];
    } else if (ps && last[0] >= 1) {
      const e = ps * last[0];
      verdict = last[1] >= e ? ['good', `at or above the backtest pace (${susd(e)} expected after ${last[0]} sessions)`] : ['warn', `under the backtest pace (${susd(e)} expected after ${last[0]} sessions); few trades so far, so this says little yet`];
    }
    return `<figure class="rc-fig"><svg viewBox="0 0 ${W} ${Hh}" role="img" aria-label="${NAMES[k]} real equity by session vs the backtest">
      ${rows ? `<path d="${area(1, 5)}" class="rc-b1"/><path d="${area(2, 4)}" class="rc-b2"/><path d="${line(rows.map((r) => [r[0], r[3]]))}" class="rc-p50"/>` : ''}
      ${!rows && ps ? `<path d="M${X(0)},${Y(0)}L${X(nMax)},${Y(ps * nMax)}" class="rc-p50"/>` : ''}
      ${hl(0, 'rc-zero', '')}${hl(tgt, 'rc-tgt', 'target')}${hl(flo, 'rc-flo', 'floor')}
      <path d="${line(pts)}" class="rc-real"/>${pts.map((p) => `<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="3" class="rc-dot"/>`).join('')}
      ${ticks}${xt}</svg>
      <figcaption><span class="rc-ax-l">x: eval session · y: $ since the eval start</span><span class="rc-lg real"></span>real ${susd(last[1], 2)} after ${last[0]} session${last[0] === 1 ? '' : 's'} ${rows ? `<span class="rc-lg band"></span>${tip('Backtest band', 'backtest band')}` : ps ? '<span class="rc-lg pace"></span>backtest pace' : ''}
        ${verdict ? `<b class="rc-vd ${verdict[0]}">${esc(verdict[1])}</b>` : ''}</figcaption></figure>`;
  }
  function vsBacktest(B, k, S) {
    const P = ((B.progress || {})[k]) || {}, E = P.expected || {}, A = P.actual || {}, O = ((P.odds || {}).rows || {}).H2;
    const a = accOf(B, k) || {};
    const wk = Math.max(1, sessionsBetween(a.eval_start || today(B), today(B))) / 5;
    const tpw = S.n / wk;
    return `<div class="rc-vs">${kpi('Backtest $ / month', usd(E.per_month), esc(E.src ? E.src.split(',')[0] : '2026 H2'))}${kpi('Real pace $ / month', susd(A.per_month_pace), `${A.sessions ?? '—'} session${A.sessions === 1 ? '' : 's'} so far`, cl(A.per_month_pace))}
      ${kpi('Trades a week', `${ok(tpw) ? tpw.toFixed(1) : '—'} real`, `backtest ${E.trades_per_week ?? '—'} · goal ${k === 'lit' ? '2-4' : '3-4'}`)}${O ? kpi('2-week eval odds', `${O.p10}% pass`, `${O.f10}% fail in 10 sessions · median ${O.pass_med}`) : ''}</div>`;
  }
  function daily(B, R) {
    const by = new Map();
    for (const r of R) if (!r.open && ok(r.usd)) by.set(String(r.day), (by.get(String(r.day)) || 0) + +r.usd);
    const D = [...by.entries()].sort((x, y) => (x[0] < y[0] ? -1 : 1)).slice(-20);
    if (!D.length) return '<p class="rc-note">No closed real trade yet.</p>';
    const m = Math.max(...D.map((d) => Math.abs(d[1])), 1);
    return `<div class="rc-days">${D.map(([d, v]) => `<div class="rc-day" title="${esc(d)} ${esc(susd(v, 2))}"><div class="rc-dcol"><i class="${v >= 0 ? 'up' : 'dn'}" style="height:${(Math.abs(v) / m * 100).toFixed(0)}%"></i></div><b class="${cl(v)}">${esc(susd(v))}</b><em>${esc(new Date(d + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', day: 'numeric' }))}</em></div>`).join('')}</div>`;
  }
  function rdist(S) {
    const bins = [['≤ −1R', (x) => x <= -0.95], ['−1 to 0', (x) => x > -0.95 && x < -0.05], ['BE', (x) => Math.abs(x) <= 0.05], ['0 to 2R', (x) => x > 0.05 && x < 2], ['2 to 6R', (x) => x >= 2 && x < 6], ['≥ 6R', (x) => x >= 6]];
    const n = bins.map(([, f]) => S.Rs.filter(f).length), m = Math.max(1, ...n);
    return `<div class="rc-rd">${bins.map(([l], i) => `<div><span>${l}</span><div class="rc-rdb"><i class="${i < 2 ? 'dn' : i > 2 ? 'up' : ''}" style="width:${(n[i] / m * 100).toFixed(0)}%"></i></div><b>${n[i]}</b></div>`).join('')}</div>`;
  }
  function byStrat(R) {
    const g = new Map();
    for (const r of R) { if (r.open || !ok(r.usd)) continue; const k = NAMES[r.acct] + (r.member ? ' · ' + r.member : ''); const x = g.get(k) || { n: 0, w: 0, net: 0 }; x.n++; if (r.usd > 0) x.w++; x.net += +r.usd; g.set(k, x); }
    if (!g.size) return '<p class="rc-note">No closed real trade yet.</p>';
    return `<table class="rc-t"><thead><tr><th>Strategy</th><th class="r">Trades</th><th class="r">Win</th><th class="r">Net (real)</th></tr></thead><tbody>${[...g.entries()].sort((x, y) => y[1].net - x[1].net).map(([k, x]) => `<tr><td>${esc(k)}</td><td class="r">${x.n}</td><td class="r">${pct(100 * x.w / x.n)}</td><td class="r mono ${cl(x.net)}">${susd(x.net, 2)}</td></tr>`).join('')}</tbody></table>`;
  }
  function weekCard(B, R) {
    const td = today(B), d = new Date(td + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    const mon = d.toISOString().slice(0, 10), W = R.filter((r) => String(r.day) >= mon), S = stats(W);
    const G = (B.progress || {});
    const line = (k) => { const w = (G[k] || {}).week || {}; const n = W.filter((r) => r.acct === k).length; return `${NAMES[k]} ${n} trade${n === 1 ? '' : 's'} (goal ${w.lo ?? 2}-${w.hi ?? 4})`; };
    const grade = S.n === 0 ? ['—', 'no real trade yet this week'] : S.net > 0 && S.win >= 40 ? ['A', 'green week'] : S.net > 0 ? ['B', 'green, few wins'] : S.losses <= 2 ? ['C', 'small red: normal for 1-2 stop-outs'] : ['D', 'red week: read the trade reviews'];
    return `<div class="rc-week"><div class="rc-grade ${S.net > 0 ? 'good' : S.n ? 'warn' : ''}"><b>${grade[0]}</b><span>${esc(grade[1])}</span></div>
      <div class="rc-wk">${kpi('This week (real)', susd(S.net, 2), `since Mon ${esc(mon.slice(5))}`, cl(S.net))}${kpi('Trades', String(S.n), esc(line('lit') + ' · ' + line('atlas')))}${kpi('Win rate', S.win == null ? '—' : pct(S.win))}</div></div>`;
  }
  function incidents(B) {
    const out = [];
    for (const k of ['lit', 'atlas']) { const a = accOf(B, k); if (!a) continue; for (const o of refused(a)) out.push({ t: o.t, k, text: `${o.side} ${o.qty ?? '?'} micros REFUSED${o.error ? ': ' + o.error : ''}` }); }
    for (const c of checksOf(B)) out.push({ t: null, k: c.acct, text: 'Ledger check: ' + c.text });
    if (!out.length) return '<p class="rc-note">No refused order and no ledger question. Restarts and NinjaTrader messages are in the Bot log (PC).</p>';
    return `<ul class="rc-evl">${out.map((e) => `<li class="bad"><span class="mono">${e.t ? dhm(e.t) : '!'}</span><b>${esc(NAMES[e.k])}</b><span>${esc(e.text)}</span></li>`).join('')}</ul>`;
  }
  function timeline(B, r) {
    const a = accOf(B, r.acct) || {};
    const O = (a.orders || []).filter((o) => o.entry_t === r.entry_t).sort((x, y) => x.t - y.t);
    const st = [['Signal (bar)', r.entry_t]];
    for (const o of O) st.push([o.side === 'exit' ? `Exit booked (${how({ exit: o.reason })})` : o.side === 'modify' ? 'Stop to breakeven' : `${o.side === 'buy' ? 'Buy' : 'Sell'} order sent${o.ok === false ? ' (fill reported later)' : ''}`, o.t]);
    if (ok(r.exit_t) && !O.some((o) => o.side === 'exit')) st.push([`Exit (${how(r)})`, r.exit_t]);
    st.sort((x, y) => x[1] - y[1]);
    return `<ol class="rc-tl">${st.map(([l, t], i) => `<li><b>${esc(l)}</b><span class="mono">${hm(t)} ET</span>${i ? `<em>+${esc(dur(t - st[i - 1][1]))}</em>` : ''}</li>`).join('')}</ol>
      <p class="rc-note">Held ${ok(r.exit_t) ? esc(dur(r.exit_t - r.entry_t)) : 'open'} · stop ${px(r.stop)} · target ${px(r.target)}${ok(r.stop) && ok(r.entry) ? ` · risk ${Math.abs(r.entry - r.stop).toFixed(2)} pts = ${usd(Math.abs(r.entry - r.stop) * 2 * (+r.qty || 0))}` : ''}</p>`;
  }
  function log(B, R) {
    if (!R.length) return '<p class="rc-note">No real trade yet. The first one shows here the moment the bot closes it.</p>';
    let run = 0;
    const rows = R.map((r) => { if (!r.open && ok(r.usd)) run += +r.usd; return { ...r, run }; }).reverse();
    return `<div class="rc-log">${rows.map((r, i) => `<div class="rc-lr${F.open === i ? ' on' : ''}"><button type="button" class="rc-lrh" data-rc-row="${i}" aria-expanded="${F.open === i}">
        <span class="mono rc-ld">${esc(dhm(r.entry_t) || r.day)}</span><span class="rc-la"><b>${esc(NAMES[r.acct] || r.acct)}${r.member ? ' · ' + esc(r.member) : ''}</b> ${chip(r.side || '', r.side === 'LONG' ? 'good' : 'bad')}</span>
        <span class="mono rc-lq">${esc(r.qty ?? '?')} × ${px(r.entry)} → ${r.open ? 'open' : px(r.exit_px)}</span><span class="rc-lh">${esc(how(r))} <em class="${cl(r.r)}">${fR(r.r)}</em></span>
        <b class="mono rc-lu ${cl(r.usd)}">${r.open ? 'open' : susd(r.usd, 2)}</b><span class="mono rc-lrun ${cl(r.run)}">${susd(r.run, 2)}</span></button>
        ${F.open === i ? `<div class="rc-lrb">${timeline(B, r)}</div>` : ''}</div>`).join('')}</div>`;
  }
  const H3 = (t, s) => `<h3 class="rc-sec">${esc(t)}${s ? ` <span>${esc(s)}</span>` : ''}</h3>`;
  function results(B, o) {
    css(); o = o || {};
    if (!B || B.error) return `<section class="rc-wrap"><p class="rc-note">${esc((B && B.error) || 'No data yet.')}</p></section>`;
    const all = realRows(B), R = all.filter((r) => F.acct === 'all' || r.acct === F.acct), S = stats(R);
    const seg = `<div class="rc-seg" role="tablist">${[['all', 'Both accounts'], ['lit', 'Zlarior 50K'], ['atlas', 'ATLAS 25K']].map(([v, l]) => `<button type="button" role="tab" data-rc-acct="${v}" aria-selected="${F.acct === v}" class="${F.acct === v ? 'on' : ''}">${l}</button>`).join('')}</div>`;
    const ks = F.acct === 'all' ? ['lit', 'atlas'] : [F.acct];
    return `<section class="rc-wrap rc-res">${checkBanners(B)}
      <div class="rc-tb">${seg}<button type="button" class="rc-btn" data-rc-csv="1">Export real trades (CSV)</button></div>
      ${kpis(S)}
      ${H3('This week', 'report card')}<section class="rc-card">${weekCard(B, R)}</section>
      ${H3('Live vs backtest', 'is the real account on track?')}<div class="rc-grid2">${ks.map((k) => `<section class="rc-card"><div class="rc-h"><div class="rc-eye">${NAMES[k]} · ${PLAN[k].size}</div></div>${vsBacktest(B, k, stats(all.filter((r) => r.acct === k)))}${curve(B, k)}</section>`).join('')}</div>
      <div class="rc-grid2"><section class="rc-card"><div class="rc-h"><div class="rc-eye">Daily P&L (real)<em>last 20 trading days with a trade</em></div></div>${daily(B, R)}</section>
        <section class="rc-card"><div class="rc-h"><div class="rc-eye">${tip('R', 'R')} distribution<em>closed real trades</em></div></div>${rdist(S)}</section></div>
      <div class="rc-grid2"><section class="rc-card"><div class="rc-h"><div class="rc-eye">$ by strategy<em>real money only</em></div></div>${byStrat(R)}</section>
        <section class="rc-card"><div class="rc-h"><div class="rc-eye">Incidents<em>refused orders, ledger questions</em></div></div>${incidents(B)}</section></div>
      ${H3('Real trade log', 'newest first · tap a trade for its timeline · running P&L on the right')}<section class="rc-card">${log(B, R)}</section>
      <p class="rc-src">Real = the PC bot's ledger and NinjaTrader's fills on the MFFU accounts (engine/live_board.py "real"). Paper runs are never mixed in. Backtest: ${esc(((B.real || {}).cone || {}).src || '2026 H2')}; ATLAS research/second/atlas.json.</p></section>`;
  }

  // ---------------------------------------------------------------- CSV + wiring
  const COLS = ['day', 'entry_et', 'exit_et', 'account', 'member', 'side', 'qty', 'entry', 'stop', 'target', 'exit_px', 'exit', 'r', 'usd', 'running_usd'];
  function csv(rows) {
    const q = (v) => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    let run = 0;
    const out = (rows || []).map((r) => { if (!r.open && ok(r.usd)) run += +r.usd; return { ...r, entry_et: dhm(r.entry_t), exit_et: dhm(r.exit_t), account: NAMES[r.acct] || r.acct, running_usd: run.toFixed(2) }; });
    return [COLS.join(','), ...out.map((r) => COLS.map((c) => q(r[c])).join(','))].join('\n');
  }
  function download(name, text, o) {
    if (o && o.download) return o.download(name, text);
    try { const b = new Blob([text], { type: 'text/csv' }), u = URL.createObjectURL(b), a = document.createElement('a'); a.href = u; a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(u); a.remove(); }, 1500); } catch (e) { /* nothing more to try */ }
  }
  function wire(root, B, o) {
    if (!root || !B) return;
    o = o || {};
    root.querySelectorAll('[data-rc-acct]').forEach((b) => { b.onclick = () => { F.acct = b.dataset.rcAcct; F.open = null; redraw(root, B, o); }; });
    root.querySelectorAll('[data-rc-row]').forEach((b) => { b.onclick = () => { const i = +b.dataset.rcRow; F.open = F.open === i ? null : i; redraw(root, B, o); }; });
    root.querySelectorAll('[data-rc-csv]').forEach((b) => { b.onclick = () => download(`real_trades_${today(B)}.csv`, csv(realRows(B).filter((r) => F.acct === 'all' || r.acct === F.acct)), o); });
    if (window.BoardUI && window.BoardUI.tick) window.BoardUI.tick(root);
  }
  function redraw(root, B, o) {
    const host = root.classList && root.classList.contains('rc-host') ? root : root.querySelector('.rc-host') || root;
    const y = window.scrollY;
    host.innerHTML = results(B, o); wire(host, B, o); window.scrollTo(0, y);
  }

  // ---------------------------------------------------------------- the trade pictures say REAL next to a paper figure
  let LAST = null;
  function hookPics() {
    if (!window.TradePics || window.TradePics.realOf) return;
    window.TradePics.realOf = (x) => {
      if (!LAST || !x || x.src === 'live' || x.example) return '';
      const acct = /^(ema_lon_vix|macd_sweep|sr_nyreclaim)$/.test(x.key || '') ? 'atlas' : x.key === 'lit' ? 'lit' : null;
      if (!acct) return '';
      const m = realOf({ acct, side: x.side, entry_t: x.entry_t, day: etDay(x.entry_t), src: 'paper' }, LAST);
      return m ? m.text : '';
    };
  }
  function remember(B) { if (B && !B.error) LAST = B; hookPics(); }
  hookPics();

  const CSS = `.rc-wrap{--rc-line:var(--line,var(--nx-line,rgba(160,170,220,.16)));--rc-s2:var(--surface-2,rgba(127,127,127,.08));--rc-s3:var(--surface-3,rgba(127,127,127,.15));
--rc-ink:var(--ink,var(--text,inherit));--rc-ink2:var(--ink-2,var(--text-2,#a9b1c3));--rc-mut:var(--muted,#7a8396);--rc-good:var(--good,#22c58b);--rc-bad:var(--bad,#f0506e);--rc-warn:var(--warn,#e8a93a);--rc-acc:var(--accent,#6d7cff);
display:flex;flex-direction:column;gap:12px;min-width:0;color:var(--rc-ink)}
.rc-wrap *{box-sizing:border-box}.rc-wrap .mono{font-family:var(--mono,ui-monospace,monospace);font-variant-numeric:tabular-nums}.rc-wrap .up{color:var(--rc-good)}.rc-wrap .dn{color:var(--rc-bad)}
.rc-hd{display:flex;justify-content:space-between;align-items:flex-end;gap:8px;flex-wrap:wrap}.rc-hd h2{margin:2px 0 0;font-size:22px;line-height:1.2;font-weight:700}
.rc-eyeb{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--rc-acc)}.rc-age{font-size:12.5px;color:var(--rc-mut)}.rc-age.warn b{color:var(--rc-warn)}
.rc-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,.62fr);gap:12px;align-items:start}
@media (max-width:1180px){.rc-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.rc-slot{grid-column:1 / -1}}
@media (max-width:720px){.rc-grid{grid-template-columns:minmax(0,1fr)}}
.rc-grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:12px}
.rc-card{min-width:0;border:1px solid var(--rc-line);border-radius:16px;padding:14px 16px;background:var(--surface,var(--card,transparent));display:flex;flex-direction:column;gap:10px}
.rc-acct.bad{border-color:color-mix(in srgb,var(--rc-bad) 45%,var(--rc-line))}.rc-acct{border-top:3px solid var(--rc-acc)}.rc-acct.atlas{border-top-color:#a78bfa}
.rc-slot{border-style:dashed;background:transparent;opacity:.9}
.rc-h{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}.rc-eye{font-size:13px;font-weight:700;letter-spacing:.02em}.rc-eye em{display:block;font-style:normal;font-weight:500;font-size:11.5px;color:var(--rc-mut);margin-top:1px}
.rc-chips{display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end}
.rc-chip{display:inline-flex;align-items:center;height:22px;padding:0 9px;border-radius:99px;font-size:11px;font-weight:700;letter-spacing:.02em;background:var(--rc-s3);color:var(--rc-ink2);white-space:nowrap}
.rc-chip.good{background:color-mix(in srgb,var(--rc-good) 16%,transparent);color:var(--rc-good)}.rc-chip.bad{background:color-mix(in srgb,var(--rc-bad) 16%,transparent);color:var(--rc-bad)}
.rc-chip.warn{background:color-mix(in srgb,var(--rc-warn) 18%,transparent);color:var(--rc-warn)}.rc-chip.acc{background:color-mix(in srgb,var(--rc-acc) 18%,transparent);color:var(--rc-acc)}
.rc-top{display:flex;justify-content:space-between;align-items:center;gap:10px}
.rc-big span{display:block;font-size:12px;color:var(--rc-mut)}.rc-big b{display:block;font-size:30px;line-height:1.1;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.01em}.rc-big em{font-style:normal;font-size:12px;color:var(--rc-ink2)}
.rc-score{flex:none;width:62px;height:62px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;border:3px solid var(--rc-mut);cursor:help}
.rc-score b{font-size:19px;line-height:1}.rc-score span{font-size:10px;color:var(--rc-mut)}.rc-score.good{border-color:var(--rc-good)}.rc-score.warn{border-color:var(--rc-warn)}.rc-score.bad{border-color:var(--rc-bad)}
.rc-trs{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.rc-tr{display:grid;grid-template-columns:auto minmax(0,1fr) auto;grid-template-areas:"s m u" "s h u";gap:1px 8px;align-items:center;padding:8px 10px;border-radius:12px;background:var(--rc-s2);font-size:13px}
.rc-tr>.rc-chip{grid-area:s}.rc-trm{grid-area:m;min-width:0}.rc-trm em{font-style:normal;color:var(--rc-mut);font-size:12px;margin-left:4px}.rc-trh{grid-area:h;font-size:12px;color:var(--rc-ink2)}.rc-trh em{font-style:normal}.rc-tru{grid-area:u;font-size:15px}
.rc-why{margin:0;padding:8px 10px;border-radius:12px;background:var(--rc-s2);font-size:13px;line-height:1.45;color:var(--rc-ink2)}.rc-why b{color:var(--rc-ink)}
.rc-pos{padding:9px 10px;border-radius:12px;border:1px solid color-mix(in srgb,var(--rc-acc) 45%,transparent);background:color-mix(in srgb,var(--rc-acc) 8%,transparent);font-size:13px;display:flex;flex-wrap:wrap;gap:6px 8px;align-items:center}
.rc-posg{display:flex;flex-wrap:wrap;gap:4px 14px;width:100%;font-size:12.5px;color:var(--rc-ink2)}.rc-posg b{font-variant-numeric:tabular-nums}.rc-posg em{font-style:normal;color:var(--rc-mut)}
.rc-kv{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.rc-kv>div{padding:8px 10px;border-radius:12px;background:var(--rc-s2);min-width:0}
.rc-kv span{display:block;font-size:11.5px;color:var(--rc-mut)}.rc-kv b{display:block;font-size:15px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.rc-kv em{display:block;font-style:normal;font-size:11.5px;color:var(--rc-ink2)}
.rc-kv em.good{color:var(--rc-good)}.rc-kv em.warn{color:var(--rc-warn)}.rc-kv em.bad{color:var(--rc-bad)}
@media (max-width:420px){.rc-kv{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.rc-kv>div:last-child{grid-column:1 / -1}}
.rc-g{display:flex;flex-direction:column;gap:4px}.rc-gh{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;color:var(--rc-ink2)}.rc-gh b{color:var(--rc-ink);font-variant-numeric:tabular-nums}.rc-gh b.dn{color:var(--rc-bad)}
.rc-gs{font-size:11.5px;color:var(--rc-mut);line-height:1.35}.rc-gs.warn{color:var(--rc-warn)}.rc-gs.warn b{color:var(--rc-warn)}
.rc-bar{height:8px;border-radius:99px;background:var(--rc-s3);overflow:hidden}.rc-bar i{display:block;height:100%;border-radius:99px;background:var(--rc-mut)}
.rc-bar.good i{background:var(--rc-good)}.rc-bar.warn i{background:var(--rc-warn)}.rc-bar.bad i{background:var(--rc-bad)}.rc-bar.acc i{background:var(--rc-acc)}
.rc-scw{margin:0;font-size:11.5px;color:var(--rc-mut)}
.rc-f{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.rc-btn{min-height:40px;padding:0 14px;border-radius:11px;border:1px solid var(--rc-line);background:var(--rc-s2);color:var(--rc-ink);font:600 13px var(--sans,system-ui);cursor:pointer}
.rc-btn:hover{border-color:color-mix(in srgb,var(--rc-acc) 50%,var(--rc-line))}.rc-btn.bad{color:var(--rc-bad);border-color:color-mix(in srgb,var(--rc-bad) 40%,var(--rc-line))}
.rc-note{margin:0;font-size:12.5px;line-height:1.45;color:var(--rc-ink2)}.rc-src{margin:2px;font-size:11.5px;color:var(--rc-mut);line-height:1.4}
.rc-ban{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:12px;font-size:13.5px;line-height:1.45;border:1px solid var(--rc-line);background:var(--rc-s2)}
.rc-ban i{flex:none;width:9px;height:9px;border-radius:50%;margin-top:6px;background:var(--rc-mut)}.rc-ban.good i{background:var(--rc-good)}.rc-ban.bad i{background:var(--rc-bad)}.rc-ban.warn i{background:var(--rc-warn)}
.rc-ban.warn{border-color:color-mix(in srgb,var(--rc-warn) 45%,transparent);background:color-mix(in srgb,var(--rc-warn) 8%,transparent)}.rc-ban.bad{border-color:color-mix(in srgb,var(--rc-bad) 45%,transparent);background:color-mix(in srgb,var(--rc-bad) 9%,transparent)}
.rc-evl{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}.rc-evl li{display:grid;grid-template-columns:52px minmax(70px,auto) minmax(0,1fr);gap:8px;padding:7px 2px;border-top:1px solid var(--rc-line);font-size:12.5px;align-items:baseline}
.rc-evl li:first-child{border-top:0}.rc-evl li .mono{color:var(--rc-mut)}.rc-evl li span:last-child{color:var(--rc-ink2);overflow-wrap:anywhere}.rc-evl li.bad b{color:var(--rc-bad)}.rc-evl li.good b{color:var(--rc-good)}.rc-evl li.warn b{color:var(--rc-warn)}
@media (max-width:520px){.rc-evl li{grid-template-columns:44px minmax(0,1fr)}.rc-evl li span:last-child{grid-column:2}}
.rc-srs{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,240px),1fr));gap:6px}
.rc-sr{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:2px 8px;align-items:center;padding:7px 10px;border-radius:11px;background:var(--rc-s2);font-size:12.5px}
.rc-sr i{width:8px;height:8px;border-radius:50%;background:var(--rc-mut)}.rc-sr.good i{background:var(--rc-good)}.rc-sr.bad i{background:var(--rc-bad)}.rc-sr.warn i{background:var(--rc-warn)}
.rc-sr span{color:var(--rc-ink2)}.rc-sr b{font-variant-numeric:tabular-nums;text-align:right}.rc-sr.bad b{color:var(--rc-bad)}.rc-sr em{grid-column:2 / -1;font-style:normal;font-size:11px;color:var(--rc-mut);overflow-wrap:anywhere}
.rc-tip{text-decoration:underline dotted color-mix(in srgb,var(--rc-mut) 70%,transparent);text-underline-offset:3px;cursor:help}
.rc-tb{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}
.rc-seg{display:inline-flex;gap:2px;padding:3px;border-radius:12px;background:var(--rc-s2);border:1px solid var(--rc-line);max-width:100%;overflow-x:auto}
.rc-seg button{min-height:36px;padding:0 12px;border:0;border-radius:9px;background:none;color:var(--rc-ink2);font:600 13px var(--sans,system-ui);cursor:pointer;white-space:nowrap}.rc-seg button.on{background:var(--surface,var(--card,#1a1f2b));color:var(--rc-ink);box-shadow:0 0 0 1px var(--rc-line)}
.rc-kpis,.rc-vs,.rc-wk{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,140px),1fr));gap:8px}
.rc-kpi{padding:9px 11px;border-radius:12px;background:var(--rc-s2);min-width:0}.rc-kpi span{display:block;font-size:11.5px;color:var(--rc-mut)}.rc-kpi b{display:block;font-size:18px;font-variant-numeric:tabular-nums}.rc-kpi em{display:block;font-style:normal;font-size:11.5px;color:var(--rc-ink2);line-height:1.35}
.rc-sec{margin:8px 2px 0;font-size:13px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--rc-ink2)}.rc-sec span{text-transform:none;letter-spacing:0;font-weight:500;color:var(--rc-mut);margin-left:6px}
.rc-fig{margin:0}.rc-fig svg{width:100%;height:auto;display:block}.rc-fig figcaption{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;font-size:12px;color:var(--rc-ink2)}
.rc-b1{fill:color-mix(in srgb,var(--rc-acc) 12%,transparent)}.rc-b2{fill:color-mix(in srgb,var(--rc-acc) 22%,transparent)}.rc-p50{fill:none;stroke:var(--rc-acc);stroke-width:1.5;stroke-dasharray:4 4}
.rc-real{fill:none;stroke:var(--rc-ink);stroke-width:2.5;stroke-linejoin:round}.rc-dot{fill:var(--rc-ink)}.rc-zero{stroke:var(--rc-line);stroke-width:1}.rc-tgt{stroke:var(--rc-good);stroke-width:1;stroke-dasharray:2 3}.rc-flo{stroke:var(--rc-bad);stroke-width:1;stroke-dasharray:2 3}
.rc-ax{fill:var(--rc-mut);font-size:13px;font-family:var(--sans,system-ui)}.rc-ax-l{width:100%;font-size:11px;color:var(--rc-mut)}.rc-ax.rc-tgt{fill:var(--rc-good);stroke:none}.rc-ax.rc-flo{fill:var(--rc-bad);stroke:none}
.rc-lg{display:inline-block;width:14px;height:4px;border-radius:2px;vertical-align:middle}.rc-lg.real{background:var(--rc-ink)}.rc-lg.band{background:color-mix(in srgb,var(--rc-acc) 35%,transparent);height:8px}.rc-lg.pace{background:var(--rc-acc)}
.rc-vd{font-weight:600;font-size:12px}.rc-vd.good{color:var(--rc-good)}.rc-vd.warn{color:var(--rc-warn)}.rc-vd.bad{color:var(--rc-bad)}
.rc-days{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px}.rc-day{flex:0 0 58px;display:flex;flex-direction:column;align-items:center;gap:3px;font-size:11px}.rc-day em{font-style:normal;color:var(--rc-mut)}
.rc-dcol{height:70px;width:22px;display:flex;align-items:flex-end;background:var(--rc-s2);border-radius:6px;overflow:hidden}.rc-dcol i{display:block;width:100%;border-radius:6px 6px 0 0}.rc-dcol i.up{background:var(--rc-good)}.rc-dcol i.dn{background:var(--rc-bad)}
.rc-rd{display:flex;flex-direction:column;gap:5px}.rc-rd>div{display:grid;grid-template-columns:70px minmax(0,1fr) 26px;gap:8px;align-items:center;font-size:12.5px}.rc-rd span{color:var(--rc-ink2)}.rc-rd b{text-align:right}
.rc-rdb{height:12px;border-radius:6px;background:var(--rc-s2);overflow:hidden}.rc-rdb i{display:block;height:100%;background:var(--rc-mut);border-radius:6px}.rc-rdb i.up{background:var(--rc-good)}.rc-rdb i.dn{background:var(--rc-bad)}
.rc-t{width:100%;border-collapse:collapse;font-size:13px}.rc-t th{text-align:left;color:var(--rc-mut);font-weight:600;padding:6px;border-bottom:1px solid var(--rc-line)}.rc-t td{padding:7px 6px;border-top:1px solid var(--rc-line)}.rc-t .r{text-align:right}
.rc-week{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.rc-grade{flex:none;width:86px;height:86px;border-radius:18px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:var(--rc-s2);text-align:center}
.rc-grade b{font-size:34px;line-height:1}.rc-grade span{font-size:10.5px;color:var(--rc-mut);padding:0 4px}.rc-grade.good b{color:var(--rc-good)}.rc-grade.warn b{color:var(--rc-warn)}.rc-wk{flex:1 1 260px}
.rc-log{display:flex;flex-direction:column}.rc-lr{border-top:1px solid var(--rc-line)}.rc-lr:first-child{border-top:0}
.rc-lrh{width:100%;display:grid;grid-template-columns:130px minmax(120px,1fr) minmax(150px,1.2fr) 110px 100px 100px;gap:8px;align-items:center;padding:9px 4px;border:0;background:none;color:var(--rc-ink);font:inherit;font-size:13px;text-align:left;cursor:pointer}
.rc-lrh:hover{background:var(--rc-s2)}.rc-ld{color:var(--rc-mut);font-size:12px}.rc-lq{color:var(--rc-ink2);font-size:12.5px}.rc-lh{font-size:12.5px;color:var(--rc-ink2)}.rc-lh em{font-style:normal}.rc-lu{text-align:right}.rc-lrun{text-align:right;font-size:12px;opacity:.85}
.rc-lr.on{background:var(--rc-s2);border-radius:12px}.rc-lrb{padding:4px 10px 12px}
@media (max-width:760px){.rc-lrh{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"a u" "d run" "q q" "h h";gap:2px 8px}.rc-la{grid-area:a}.rc-lu{grid-area:u}.rc-ld{grid-area:d}.rc-lrun{grid-area:run}.rc-lq{grid-area:q}.rc-lh{grid-area:h}}
.rc-tl{list-style:none;margin:6px 0;padding:0 0 0 14px;border-left:2px solid var(--rc-line);display:flex;flex-direction:column;gap:6px}.rc-tl li{position:relative;display:flex;flex-wrap:wrap;gap:4px 10px;font-size:12.5px}
.rc-tl li::before{content:'';position:absolute;left:-20px;top:4px;width:10px;height:10px;border-radius:50%;background:var(--rc-acc)}.rc-tl li .mono{color:var(--rc-ink2)}.rc-tl li em{font-style:normal;color:var(--rc-mut)}`;
  function css() {
    if (typeof document === 'undefined' || document.getElementById('rc-css')) return;
    const s = document.createElement('style'); s.id = 'rc-css'; s.textContent = CSS; document.head.appendChild(s);
  }
  window.RealUI = {
    today: (B, o) => { remember(B); return today_(B, o); }, safety: (B, o) => { remember(B); return safety(B, o); },
    results: (B, o) => { remember(B); return results(B, o); }, wire, realOf, csv, score, stats, realRows, remember, css, version: 1,
  };
})();
