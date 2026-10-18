// Command Center cockpit: the mission strip (bot, price, today, week band, killzone, MFFU eval meters, launch T-minus, next
// blackout, data freshness, watchdog) and the live widgets. Prefers /api/dash/* (research/DASHBOARD_API.md) and falls back to
// the existing endpoints; anything with no source shows a waiting state instead of a number.
import { $, $$, esc, fmt$, fmtS$, fmtN, fmtR, cls, css, etStr, tradingDay } from '../util.js';
import { S, on, cj, baseOpts } from '../state.js';
import { L, onLive, notify } from './live.js';
import { widget, body, meta, buildGrid } from './widgets.js';
import { tickTo, ring, arcGauge, spark, bar, waiting, stat, getJSON, dash, pref, dur, ago, killzone, etNow, etToTs, LAUNCH_TS, marketOpen, tradingDate, weekOf } from './kit.js';

const PLAN = { start: 50000, target: 3000, mll: 2000, dll: 1000, lock: 50100, internal: 600 };
const FLOW = ['WAITING FOR SWEEP', 'ARMED - HUNTING IFVG', 'ORDER PENDING', 'IN TRADE', 'DONE FOR DAY'];   // previous engine (archive)
// LIT (live since 2026-10-18): levels -> sweep -> 5m CISD -> limit at the CISD level (30 min) -> 1m CISD -> trade -> done
const LIT_FLOW = ['LEVELS', 'SWEEP', 'CISD', 'LIMIT', '1m CISD', 'IN TRADE', 'DONE'];
function litIdx(st) {
  const ms = String(st.model_state || ''), su = Object.values(st.setups || {})[0];
  if (st.position) return 5;
  if (/done for today/i.test(ms)) return 6;
  if (su?.tapped_t || /tapped/i.test(ms)) return 4;
  if (su || /limit armed/i.test(ms)) return 3;
  if ((st.lit?.signals_today || []).length) return 2;
  return /closed/i.test(ms) ? -1 : 0;
}
function litNarrative(s, st0) {
  const ms = String(st0.model_state || '—').replace(/^LIT: /, ''), price = st0.price, out = [];
  if (!s.running) out.push('The paper bot is stopped, so nothing is being hunted.');
  out.push(ms.charAt(0).toUpperCase() + ms.slice(1) + '.');
  for (const [k, su] of Object.entries(st0.setups || {})) {
    if (!su) continue;
    out.push(`${k === 'long' ? 'Long' : 'Short'} limit ${fmtN(su.limit, 2)} after the sweep of ${esc((su.pools || []).join(', ') || 'a level')} (extreme ${fmtN(su.ext, 2)}): stop ${fmtN(su.stop, 2)}, target ${fmtN(su.target, 2)}${su.tapped_t ? ', limit touched, waiting for a 1m CISD' : ''}.`);
  }
  const pos = st0.position;
  if (pos) out.push(`Position: ${pos.dir === 1 ? 'LONG' : 'SHORT'} ${pos.qty} MNQ from ${fmtN(pos.entry, 2)}, stop ${fmtN(pos.stop, 2)}${pos.be ? ' (breakeven)' : ''}, target ${fmtN(pos.target, 2)} (${esc(pos.target_label || 'VIX band')}).`);
  const L0 = st0.lit || {};
  if (L0.open18 && L0.vix_move) out.push(`Target band: 18:00 open ${fmtN(L0.open18, 2)} ± ${fmtN(L0.vix_move, 1)} pts (VIX ${fmtN(L0.vix, 1)}).`);
  const R = st0.lit_rules || {};
  if (R.monday?.text) out.push(R.monday.text + '.');
  if (R.weekly_stop?.text) out.push('Weekly stop: ' + R.weekly_stop.text.replace(/^weekly stop /i, '') + '.');
  const pools = (st0.active_pools || []).filter(p => price != null && p.kind !== 'vix');
  const up = pools.filter(p => p.price > price).sort((a, b) => a.price - b.price)[0], dn = pools.filter(p => p.price < price).sort((a, b) => b.price - a.price)[0];
  if (up || dn) out.push(`Nearest LIT levels: ${up ? `${esc(up.label)} +${fmtN(up.price - price, 1)}` : 'none above'} · ${dn ? `${esc(dn.label)} −${fmtN(price - dn.price, 1)}` : 'none below'}.`);
  return { ms: LIT_FLOW[litIdx(st0)] || 'CLOSED', text: out.join(' ') };
}
const src = (live) => `<span class="src-pill ${live ? 'live' : 'fallback'}" title="${live ? 'served by /api/dash' : 'dash API not deployed yet: computed from existing endpoints'}">${live ? 'dash api' : 'fallback'}</span>`;
const st = () => L.live?.state || null;

// ------------------------------------------------------------------ derived live numbers
function liveBars() { return (L.live?.bars || []).map(b => ({ t: b.time, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume })); }
function dayBars() {
  const bars = liveBars(); if (!bars.length) return { bars: [], date: null, prevClose: null };
  let date = tradingDate();
  let cur = bars.filter(b => tradingDay(b.t) === date);
  if (!cur.length) { date = tradingDay(bars.at(-1).t); cur = bars.filter(b => tradingDay(b.t) === date); }
  const prev = bars.filter(b => tradingDay(b.t) < date);
  return { bars: cur, date, prevClose: prev.length ? prev.at(-1).c : null };
}
function priceInfo() {
  const p = L.ov?.price;
  if (p?.last != null) return { last: p.last, chg: p.chg, pct: p.chg_pct, hi: p.day_high, lo: p.day_low, t: p.t, api: true };
  const s = st(); if (!s) return null;
  const { bars, prevClose } = dayBars();
  const last = s.price;
  return { last, chg: prevClose != null ? last - prevClose : null, pct: prevClose ? (last - prevClose) / prevClose * 100 : null,
    hi: bars.length ? Math.max(...bars.map(b => b.h)) : null, lo: bars.length ? Math.min(...bars.map(b => b.l)) : null, t: s.t, api: false };
}
function weekInfo() {
  const w = L.ov?.week;
  if (w) return { n: w.trades, msg: w.message, bt: w.backtest_tpw, api: true };
  const rows = L.paper?.trades;
  if (!rows) return null;
  const wk = weekOf(tradingDate());
  const n = rows.filter(r => { const d = r.day || r.date || (r.entry_t ? tradingDay(r.entry_t) : null); return d && weekOf(d) === wk; }).length;
  return { n, msg: `${n} paper trade${n === 1 ? '' : 's'} this week`, bt: S.res?.stats?.trades_per_week, api: false };
}
// MFFU eval state: owner's real numbers (manual) > /api/dash/eval > overview > paper bot since launch
let evalApi = null;
async function pollEval() {
  const a = pref.get('acct', null);
  const q = a ? `?since=${a.since || '2026-10-18'}&balance=${a.balance}&peak_eod=${a.peak_eod ?? a.balance}&today_pnl=${a.today_pnl ?? 0}` : '';
  evalApi = await dash('/api/dash/eval' + q);
}
function evalInfo() {
  const a = pref.get('acct', null);
  if (evalApi?.state) {
    const e = evalApi;
    return { src: a ? 'real (manual)' : e.state.source, balance: e.state.balance, profit: e.state.profit, cushion: e.mll.cushion, mll: e.mll.level, locked: e.mll.locked,
      today: e.dll.today_pnl, days: e.state.trading_days, proj: e.projection, api: true };
  }
  if (a) {
    const bal = +a.balance, peak = +(a.peak_eod ?? a.balance);
    const mll = Math.min(Math.max(PLAN.start - PLAN.mll, peak - PLAN.mll), PLAN.lock);
    return { src: 'real (manual)', balance: bal, profit: bal - PLAN.start, cushion: bal - mll, mll, locked: mll >= PLAN.lock, today: +(a.today_pnl || 0), api: false };
  }
  const e = L.ov?.eval;
  if (e) return { src: e.source, balance: e.balance, profit: e.profit, cushion: e.cushion, mll: e.mll, locked: e.mll >= PLAN.lock, today: L.ov.today?.pnl_routed ?? 0, api: true };
  if (!L.live) return null;
  // before the dash API: the eval starts at launch, so the paper account begins at the plan start until routed trades land
  const today = L.live.day_pnl_routed ?? 0;
  return { src: Date.now() / 1000 < LAUNCH_TS ? 'starts at launch' : 'paper', balance: PLAN.start, profit: 0, cushion: PLAN.mll, mll: PLAN.start - PLAN.mll, locked: false, today, api: false, pre: true };
}
function nextBlackout() {
  const nb = L.ov?.next_blackout;
  if (nb?.t || nb?.start_t) { const s = nb.start_t ?? (nb.t - 15 * 60), e = nb.end_t ?? (nb.t + 30 * 60); return { event: nb.event, start: s, end: e, rel: nb.t ?? s + 900 }; }
  const ents = L.bo?.entries || [];
  const now = Date.now() / 1000;
  const p = S.meta?.defaults || {};
  const before = (p.news_before_min ?? 15) * 60, after = (p.news_after_min ?? 30) * 60;
  for (const e of ents) {
    const m = e.match(/(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d)/); if (!m) continue;
    const t = etToTs(+m[1], +m[2], +m[3], +m[4], +m[5]);
    if (t + after > now) return { event: 'High-impact USD release', start: t - before, end: t + after, rel: t };
  }
  return null;
}
function dataAge() {
  const d = L.ov?.data, h = L.live?.health;
  const base = d?.age_s ?? h?.data_age_s;
  if (base == null) return null;
  const since = L.liveAt ? Date.now() / 1000 - L.liveAt : 0;
  return { age: base + since, stale: d?.stale ?? h?.stale, open: d?.market_open ?? h?.market_open, src: d?.source ?? h?.data_source, last: d?.last_bar_t ?? h?.last_bar_t };
}
function sessionName(n = etNow()) {
  if (!marketOpen(n)) return n.mod >= 1020 && n.mod < 1080 && n.dow >= 1 && n.dow <= 4 ? 'CME maintenance' : 'Market closed';
  const S2 = [[0, 120, 'Asia'], [120, 180, 'Frankfurt hour'], [180, 240, 'London open'], [240, 480, 'Pre-market'], [480, 540, 'NY 08-09'], [540, 570, 'Pre-market'], [570, 930, 'NY cash session'], [930, 960, 'No new entries · flat 15:55'], [960, 1020, 'Post-close'], [1080, 1200, 'Globex open'], [1200, 1440, 'Asia 20-00 box']];
  return (S2.find(([a, b]) => n.mod >= a && n.mod < b) || [0, 0, ''])[2];
}

// ------------------------------------------------------------------ cockpit
function cockpitSkeleton(el) {
  el.className = 'cockpit';
  el.innerHTML = `<div class="ck-top">
      <div class="ck-cell ck-bot"><div class="orb off" id="ckOrb"><b>BOT</b></div><div style="min-width:0"><div class="ck-k">Paper bot</div><div class="ck-v" id="ckBotTxt">CONNECTING</div><div class="ck-s" id="ckBotSub">waiting for the server…</div><div class="ck-badges" id="ckBadges"></div></div></div>
      <div class="ck-cell ck-price"><div class="ck-k">NQ futures <span id="ckPxSrc"></span></div><div class="ck-v" id="ckPx">—</div><div class="ck-s" id="ckPxSub"></div><div id="ckSpark" style="height:30px;margin-top:4px"></div></div>
      <div class="ck-cell"><div class="ck-k">Today · paper routed</div><div class="ck-v" id="ckToday">—</div><div class="ck-s" id="ckTodaySub"></div></div>
      <div class="ck-cell"><div class="ck-k">This week · band 2–4</div><div class="ck-v sm" id="ckWeek">—</div><div class="ck-band" id="ckBand"></div><div class="ck-s" id="ckWeekSub"></div></div>
      <div class="ck-cell ck-kz"><div id="ckKzRing"></div><div style="min-width:0"><div class="ck-k" id="ckKzK">Entry window</div><div class="ck-v sm" id="ckKzT">—</div><div class="ck-s" id="ckKzS"></div></div></div>
    </div>
    <div class="ck-mid">
      <div class="ck-meter"><div class="ck-k">Profit target · $3,000 <span id="ckEvalSrc"></span></div><div class="row1"><b id="ckTgtV">—</b><span id="ckTgtS"></span></div><div id="ckTgtBar">${bar(0)}</div><div class="row2"><span id="ckTgtL"></span><span>$53,000</span></div></div>
      <div class="ck-meter"><div class="ck-k">EOD trailing max loss · $2,000</div><div class="row1"><b id="ckMllV">—</b><span id="ckMllS"></span></div><div id="ckMllBar">${bar(0)}</div><div class="row2"><span id="ckMllL"></span><span>locks at $50,100</span></div></div>
      <div class="ck-meter"><div class="ck-k">Soft daily loss · $1,000</div><div class="row1"><b id="ckDllV">—</b><span id="ckDllS"></span></div><div id="ckDllBar">${bar(0)}</div><div class="row2"><span>bot stop $600</span><span>$1,000</span></div></div>
    </div>
    <div class="ck-strip">
      <span class="ck-chip launch" id="ckLaunch">⏻ <span>Launch</span> <b>—</b></span>
      <span class="ck-chip click" id="ckNews" data-goto="news">⚡ <span>Next blackout</span> <b>—</b></span>
      <span class="ck-chip" id="ckData">● <span>Data</span> <b>—</b></span>
      <span class="ck-chip click" id="ckHealth" data-goto="ops">⛨ <span>Watchdog</span> <b>—</b></span>
      <span class="ck-chip" id="ckMarket">◷ <b>—</b></span>
      <button class="btn ghost sm ck-edit" id="ckEdit" title="Enter the real MFFU account numbers (TradingView trades the real account; this PC mirrors on paper)">✎ Real account</button>
    </div>`;
  $('#ckEdit').onclick = editAccount;
}

function renderCockpit() {
  if (!$('#ckOrb')) return;
  const s = L.live, now = Date.now() / 1000;
  // ---- bot
  const orb = $('#ckOrb');
  if (L.online === false) { orb.className = 'orb bad'; $('#ckBotTxt').textContent = 'OFFLINE'; $('#ckBotSub').textContent = 'server not reachable'; }
  else if (s) {
    const ad = s.cfg?.adapter || L.ov?.bot?.adapter || 'paper', armed = !!(s.cfg?.armed || L.ov?.bot?.armed_live);
    const issue = s.kill || (s.health && !s.health.ok) || s.health?.stale;
    orb.className = 'orb ' + (!s.running ? 'off' : s.kill ? 'bad' : issue ? 'warn' : 'run');
    orb.querySelector('b').textContent = ad === 'paper' ? 'PAPER' : ad.toUpperCase().slice(0, 5);
    $('#ckBotTxt').textContent = !s.running ? 'STOPPED' : s.kill ? 'KILLED' : (s.state?.model_state || 'RUNNING');
    const lp = s.last_poll ? ago(now - s.last_poll) : '—';
    $('#ckBotSub').textContent = `${s.cfg?.sym || 'NQ'} ${s.cfg?.tf || '5m'} · polled ${lp} · ${fmtN(s.health?.poll_ms ?? L.ov?.bot?.poll_ms, 0)} ms`;
    $('#ckBadges').innerHTML = [[ad === 'paper' ? 'paper' : ad, ad === 'paper' ? 'good' : 'warn'], [armed ? 'LIVE ARMED' : 'live not armed', armed ? 'bad' : ''],
      [s.kill ? 'kill on' : 'kill off', s.kill ? 'bad' : ''], [`${s.errors || 0} err`, s.errors ? 'warn' : '']].map(([t, c]) => `<span class="ck-badge ${c}">${esc(t)}</span>`).join('');
  }
  // ---- price
  const p = priceInfo();
  if (p) {
    tickTo($('#ckPx'), p.last, (x) => fmtN(x, 2));
    $('#ckPxSub').innerHTML = `${p.chg != null ? `<span class="${cls(p.chg)}">${p.chg > 0 ? '▲' : p.chg < 0 ? '▼' : ''} ${fmtN(Math.abs(p.chg), 2)} · ${p.pct > 0 ? '+' : ''}${fmtN(p.pct, 2)}%</span> · ` : ''}H ${fmtN(p.hi, 2)} · L ${fmtN(p.lo, 2)}`;
    $('#ckPxSrc').innerHTML = src(p.api);
    const db = dayBars().bars;
    $('#ckSpark').innerHTML = spark(db.map(b => b.c), { w: 200, h: 30, color: p.chg >= 0 ? css('--good') : css('--bad') });
  }
  // ---- today
  if (s || L.ov) {
    const today = L.ov?.today?.pnl_routed ?? s?.day_pnl_routed;
    const el = $('#ckToday');
    tickTo(el, today ?? null, (x) => fmtS$(x));
    el.className = 'ck-v ' + cls(today);
    const n = L.ov?.today?.trades ?? s?.trades_today ?? 0;
    $('#ckTodaySub').textContent = `${n} trade${n === 1 ? '' : 's'} · engine sim ${fmtS$(L.ov?.today?.engine_day_pnl ?? s?.state?.day_pnl)}`;
  }
  // ---- week band
  const w = weekInfo();
  if (w) {
    $('#ckWeek').innerHTML = `${w.n}<span class="muted" style="font-size:13px"> / 2–4</span>`;
    $('#ckBand').innerHTML = Array.from({ length: 6 }, (_, i) => `<i class="${i >= 1 && i <= 3 ? 'in' : ''} ${i < w.n ? 'on' : ''} ${i >= 4 && i < w.n ? 'over' : ''}" title="${i + 1}${i === 5 ? '+' : ''}"></i>`).join('');
    $('#ckWeekSub').textContent = `${w.n < 2 ? 'below band' : w.n > 4 ? 'above band' : 'in band'} · backtest ${fmtN(w.bt, 2)}/wk`;
  } else { $('#ckWeek').textContent = '—'; $('#ckWeekSub').textContent = 'waiting for paper trades'; }
  renderClockCells();
  // ---- eval meters
  const e = evalInfo();
  if (e) {
    $('#ckEvalSrc').innerHTML = `<span class="src-pill ${e.src === 'real (manual)' ? 'live' : ''}">${esc(e.src)}</span>`;
    tickTo($('#ckTgtV'), e.profit, (x) => fmtS$(x));
    const tf = Math.max(0, e.profit) / PLAN.target;
    $('#ckTgtBar').innerHTML = bar(tf, { color: tf >= 1 ? 'var(--good)' : 'var(--accent)', marks: [{ at: .5, label: 'halfway' }] });
    $('#ckTgtS').textContent = `${Math.round(tf * 100)}%`;
    const pj = evalApi?.projection;
    $('#ckTgtL').textContent = pj?.mc_pass_prob != null ? `MC ${Math.round(pj.mc_pass_prob)}% pass in ${pj.mc_horizon || 60}d · median ${pj.mc_median_days ?? '—'}d` : e.pre ? 'eval begins Sun 18:00 ET' : `${fmt$(Math.max(0, PLAN.target - e.profit))} to go · bal ${fmtN(e.balance, 0)}`;
    tickTo($('#ckMllV'), e.cushion, (x) => fmt$(x));
    const cf = e.cushion / PLAN.mll;
    $('#ckMllBar').innerHTML = bar(Math.min(1, cf), { color: e.locked ? 'var(--good)' : cf > .6 ? 'var(--good)' : cf > .3 ? 'var(--warn)' : 'var(--bad)' });
    $('#ckMllS').textContent = e.locked ? 'LOCKED' : `${Math.round(cf * 100)}% left`;
    $('#ckMllL').textContent = `MLL ${fmtN(e.mll, 0)}`;
    const used = Math.max(0, -(e.today || 0));
    tickTo($('#ckDllV'), used, (x) => fmt$(x));
    const df = used / PLAN.dll;
    $('#ckDllBar').innerHTML = bar(df, { color: df >= .8 ? 'var(--bad)' : df >= .5 ? 'var(--warn)' : 'var(--good)', marks: [{ at: PLAN.internal / PLAN.dll, label: 'bot daily stop $600' }] });
    $('#ckDllS').textContent = used ? `${Math.round(df * 100)}% used` : 'none used today';
  }
  // ---- strip chips
  const nb = nextBlackout();
  const nc = $('#ckNews');
  if (nb) {
    const active = now >= nb.start && now < nb.end;
    nc.className = 'ck-chip click ' + (active ? 'bad' : nb.start - now < 3 * 3600 ? 'warn' : '');
    nc.querySelector('span').textContent = active ? 'BLACKOUT ACTIVE' : 'Next blackout';
    nc.querySelector('b').textContent = active ? `ends ${dur(nb.end - now, { short: true })}` : `${etStr(nb.rel, true).slice(5)} ET · in ${dur(nb.start - now, { short: true })}`;
    nc.title = nb.event + ' · window ' + etStr(nb.start) + '–' + etStr(nb.end) + ' ET';
  } else if (L.bo || L.ov) { nc.className = 'ck-chip click good'; nc.querySelector('b').textContent = 'none listed'; }
  const da = dataAge(), dc = $('#ckData');
  if (da) {
    const open = da.open ?? marketOpen();
    const lvl = !open ? '' : da.stale || da.age > 1800 ? 'bad' : da.age > 900 ? 'warn' : 'good';
    dc.className = 'ck-chip ' + lvl;
    dc.querySelector('span').textContent = `Data · ${da.src || 'feed'}`;
    dc.querySelector('b').textContent = open ? `${dur(da.age, { short: true })} old` : `closed · last bar ${da.last ? etStr(da.last) : '—'}`;
    dc.title = 'Age of the last closed 5m bar the paper bot has seen. Yahoo NQ=F is delayed: up to ~10 min is normal in session.';
  }
  const wd = L.wd, hc = $('#ckHealth');
  if (wd) {
    const bad = !wd.ok || (wd.issues || []).length;
    hc.className = 'ck-chip click ' + (bad ? 'bad' : 'good');
    hc.querySelector('b').textContent = bad ? (wd.issues?.[0] || 'issue') : `OK · up ${dur(wd.uptime_s, { short: true })}${wd.keepawake?.held ? ' · awake' : ''}`;
  }
}
// once a second: countdowns only (killzone ring, launch T-minus, market chip)
function renderClockCells() {
  const now = Date.now() / 1000, kz = killzone(now), n = etNow(now);
  if (kz && $('#ckKzRing')) {
    const live = kz.state === 'live';
    const total = kz.end - kz.start;
    const frac = live ? (now - kz.start) / total : Math.max(.03, 1 - kz.secs / (6 * 3600));
    $('#ckKzRing').innerHTML = ring(frac, { size: 64, stroke: 7, color: live ? 'var(--good)' : kz.secs < 900 ? 'var(--warn)' : 'var(--accent)', value: live ? 'LIVE' : '', unit: '' });
    $('#ckKzK').textContent = live ? kz.kz.name : `Next · ${kz.kz.name}`;
    $('#ckKzT').textContent = live ? dur(kz.secs) : dur(kz.secs);
    $('#ckKzS').textContent = live ? 'hunting setups · ends ' + etStr(kz.end) : `opens ${['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][etNow(kz.start).dow]} ${etStr(kz.start)} ET`;
  }
  const lc = $('#ckLaunch');
  if (lc) {
    const t = LAUNCH_TS - now;
    lc.querySelector('span').textContent = t > 0 ? 'Launch T−' : 'LIVE since launch';
    lc.querySelector('b').textContent = t > 0 ? dur(t) : `day ${Math.floor(-t / 86400) + 1}`;
    lc.title = 'TradingView alerts go live Sun 2026-10-18 18:00 ET (CME Globex reopen). This PC stays on paper.';
  }
  const mc = $('#ckMarket');
  if (mc) { const open = marketOpen(n); mc.className = 'ck-chip ' + (open ? 'good' : ''); mc.querySelector('b').textContent = `${open ? 'OPEN' : 'CLOSED'} · ${sessionName(n)}`; }
}

function editAccount() {
  $('#acctPop')?.remove(); $('#acctScrim')?.remove();
  const a = pref.get('acct', {}) || {};
  const scrim = document.createElement('div'); scrim.className = 'pop-scrim'; scrim.id = 'acctScrim';
  const pop = document.createElement('div'); pop.className = 'pop rc-panel'; pop.id = 'acctPop';
  pop.style.top = '90px'; pop.style.left = '50%'; pop.style.transform = 'translateX(-50%)';
  pop.innerHTML = `<h4>Real MFFU account <button class="btn ghost sm" id="acX">✕</button></h4>
    <div class="rc-note" style="margin:0 0 10px">TradingView trades the real account, so this PC cannot see it. Type the numbers from the MFFU dashboard to drive the eval meters. Saved only in this browser. Leave empty to follow the paper bot.</div>
    <div class="rc-in"><label>Balance ($)</label><input id="acBal" type="number" step="0.01" value="${a.balance ?? ''}" placeholder="50000">
      <label>Best end-of-day balance</label><input id="acPeak" type="number" step="0.01" value="${a.peak_eod ?? ''}" placeholder="same as balance">
      <label>Today's realised P&amp;L</label><input id="acToday" type="number" step="0.01" value="${a.today_pnl ?? ''}" placeholder="0">
      <label>Eval started</label><input id="acSince" type="date" value="${a.since || '2026-10-18'}"></div>
    <div class="row gap" style="margin-top:12px"><button class="btn primary sm" id="acSave">Save</button><button class="btn ghost sm" id="acClear">Follow paper bot</button></div>`;
  document.body.append(scrim, pop);
  const close = () => { pop.remove(); scrim.remove(); };
  scrim.onclick = close; $('#acX').onclick = close;
  $('#acClear').onclick = () => { pref.set('acct', null); evalApi = null; pollEval().then(renderCockpit); close(); };
  $('#acSave').onclick = () => {
    const bal = parseFloat($('#acBal').value);
    if (!isFinite(bal) || bal < 40000 || bal > 70000) { $('#acBal').focus(); return; }
    const pk = parseFloat($('#acPeak').value);
    pref.set('acct', { balance: bal, peak_eod: isFinite(pk) ? Math.max(pk, PLAN.start) : Math.max(bal, PLAN.start), today_pnl: parseFloat($('#acToday').value) || 0, since: $('#acSince').value || '2026-10-18' });
    evalApi = null; pollEval().then(renderCockpit); renderCockpit(); close();
  };
}

// ------------------------------------------------------------------ widget: what the bot is thinking
let lastSay = '';
function narrative(s, m) {
  const st0 = s.state || {};
  if ((st0.model || 'lit') === 'lit') return litNarrative(s, st0);
  const ms = m?.model_state || st0.model_state || '—';
  const price = st0.price;
  const out = [];
  const kz = killzone();
  const tr = (v) => v === 1 ? 'bullish' : v === -1 ? 'bearish' : 'neutral';
  if (!s.running) out.push('The paper bot is stopped, so nothing is being hunted.');
  else if (ms === 'OUTSIDE KILLZONE') out.push(`Standing by outside the entry windows${kz ? ` — the ${kz.kz.name} ${kz.state === 'live' ? 'is open' : 'opens in ' + dur(kz.secs, { short: true })}` : ''}. Sweeps from 08:00 ET can still arm a setup.`);
  else if (ms === 'WAITING FOR SWEEP') out.push('Inside an entry window, watching the untaken pools for a raid. Nothing is armed until a pool is swept.');
  else if (ms === 'ARMED - HUNTING IFVG') out.push('A pool was swept: hunting an inversion FVG (or CISD) that closes back inside the range to confirm the reversal.');
  else if (ms === 'ORDER PENDING') out.push('An entry order is working at the trigger level.');
  else if (ms === 'IN TRADE') out.push('In a position, managing it toward the draw on liquidity.');
  else if (ms === 'DONE FOR DAY') out.push('Done for the day (trade limit, stop-after-win or daily stop reached).');
  else out.push(`State: ${ms.toLowerCase()}.`);
  const setups = m?.setups || st0.setups || {};
  for (const [k, su] of Object.entries(setups)) {
    if (!su) continue;
    const pools = [...new Set(String(Array.isArray(su.pools) ? su.pools.join(' ') : su.pools || '').split(/[\s/]+/).filter(Boolean))].slice(0, 4).join('/');
    const d = price != null ? su.ext - price : null;
    out.push(`${k === 'long' ? 'Long' : 'Short'} setup armed after the sweep of ${pools || 'a pool'} at ${fmtN(su.ext, 2)}${d != null ? ` (${fmtN(Math.abs(d), 1)} pts ${d < 0 ? 'below' : 'above'} price)` : ''}${su.arm_t ? `, ${ago(Date.now() / 1000 - su.arm_t)}` : ''}; it stays valid while price holds ${k === 'long' ? 'above' : 'below'} that extreme.`);
  }
  const pos = m?.position || st0.position;
  if (pos) out.push(`Position: ${pos.dir === 1 ? 'LONG' : 'SHORT'} ${pos.qty_label || ''} from ${fmtN(pos.entry, 2)}, stop ${fmtN(pos.stop, 2)}, target ${fmtN(pos.target, 2)}${m?.position?.live_r != null ? ` · ${fmtR(m.position.live_r)} open` : ''}.`);
  const dr = st0.mtf?.dealing_range;
  const drTxt = !dr ? '' : dr.pos > 1 ? `; price is above the 1H dealing range (${fmtN(dr.high, 2)}), deep premium` : dr.pos < 0 ? `; price is below the 1H dealing range (${fmtN(dr.low, 2)}), deep discount`
    : `; price at ${Math.round(dr.pos * 100)}% of the 1H dealing range (${dr.pos >= .5 ? 'premium, favours shorts' : 'discount, favours longs'})`;
  out.push(`Structure: 1H ${tr(st0.h1_trend)}, 15m ${tr(st0.m15_trend)}${drTxt}.`);
  const pools = (st0.active_pools || []).filter(p => price != null);
  const up = pools.filter(p => p.price > price).sort((a, b) => a.price - b.price)[0], dn = pools.filter(p => p.price < price).sort((a, b) => b.price - a.price)[0];
  if (up || dn) out.push(`Nearest liquidity: ${up ? `buy stops ${esc(up.label)} +${fmtN(up.price - price, 1)}` : 'none above'} · ${dn ? `sell stops ${esc(dn.label)} −${fmtN(price - dn.price, 1)}` : 'none below'}.`);
  return { ms, text: out.join(' ') };
}
let modelApi = null;
function renderThink() {
  const el = body('think'); if (!el) return;
  const s = L.live;
  if (!s) { el.innerHTML = waiting('Waiting for the paper bot', 'Polling /api/live/state every 10 s.'); return; }
  const { ms, text } = narrative(s, modelApi);
  const isLit = (s.state?.model || 'lit') === 'lit';      // LIT is the live strategy: a stopped bot shows the LIT flow
  const flow = isLit ? LIT_FLOW : modelApi?.flow?.length ? modelApi.flow : FLOW;
  const SHORT = { 'OUTSIDE KILLZONE': 'OUTSIDE KZ', 'WAITING FOR SWEEP': 'WAIT SWEEP', 'ARMED - HUNTING IFVG': 'ARMED · IFVG', 'ORDER PENDING': 'ORDER', 'IN TRADE': 'IN TRADE', 'DONE FOR DAY': 'DONE' };
  const idx = isLit ? litIdx(s.state || {}) : flow.indexOf(ms);
  meta('think', `${src(!!modelApi)} <span class="pill">${esc(etStr(s.state?.t || s.last_poll || Date.now() / 1000))} ET bar</span>`);
  if (!el.querySelector('.think-say')) el.innerHTML = `<div class="think-flow" id="thFlow"></div><div class="think-say" id="thSay"></div><div class="think-grid" id="thCards"></div><div class="think-log" id="thLog"></div>`;
  $('#thFlow', el).innerHTML = (idx < 0 ? `<span class="idle">${esc(ms)}</span>` : '') + flow.map((f, i) => `<span class="${i === idx ? 'on' : i < idx ? 'done' : ''}" title="${esc(f)}">${esc(SHORT[f] || f)}</span>`).join('');
  if (text !== lastSay) {
    lastSay = text;
    const say = $('#thSay', el);
    if (document.documentElement.dataset.motion === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches) say.textContent = text;
    else {
      let i = 0; clearInterval(say._t);
      say._t = setInterval(() => { i = Math.min(text.length, i + Math.ceil(text.length / 45)); say.innerHTML = esc(text.slice(0, i)) + (i < text.length ? '<span class="cursor"></span>' : ''); if (i >= text.length) clearInterval(say._t); }, 16);
    }
  }
  const s0 = s.state || {}, price = s0.price;
  const card = (k, su) => {
    if (!su) return `<div class="setup-card none"><div class="h"><span>${k.toUpperCase()}</span><span>idle</span></div><div class="b muted">not armed</div><div class="d">waits for a ${k === 'long' ? 'sell-side' : 'buy-side'} sweep</div></div>`;
    if (isLit) return `<div class="setup-card ${k}"><div class="h"><span>${k.toUpperCase()} LIMIT</span><span>${su.arm_t ? etStr(su.arm_t) : ''}</span></div><div class="b">${fmtN(su.limit, 2)}</div><div class="d">stop ${fmtN(su.stop, 2)} · until ${su.expires_t ? etStr(su.expires_t) : '—'}${su.tapped_t ? ' · touched' : ''}</div></div>`;
    const d = price != null ? su.ext - price : null;
    return `<div class="setup-card ${k}"><div class="h"><span>${k.toUpperCase()} ARMED</span><span>${su.arm_t ? etStr(su.arm_t) : ''}</span></div><div class="b">${fmtN(su.ext, 2)}</div><div class="d">${d != null ? `${d > 0 ? '+' : ''}${fmtN(d, 1)} pts · ` : ''}${esc(String(Array.isArray(su.pools) ? su.pools.join(' ') : su.pools || '').split(/\s+/).slice(0, 3).join(' '))}</div></div>`;
  };
  const pos = s0.position;
  $('#thCards', el).innerHTML = card('long', s0.setups?.long) + card('short', s0.setups?.short) +
    `<div class="setup-card ${pos ? (pos.dir === 1 ? 'long' : 'short') : 'none'}"><div class="h"><span>POSITION</span><span>${s0.day_trades ?? 0} today</span></div><div class="b ${pos ? '' : 'muted'}">${pos ? `${pos.dir === 1 ? 'LONG' : 'SHORT'} @ ${fmtN(pos.entry, 2)}` : 'flat'}</div><div class="d">${pos ? `SL ${fmtN(pos.stop, 2)} · TP ${fmtN(pos.target, 2)}` : `day ${fmtS$(s0.day_pnl)}`}</div></div>` +
    (isLit ? `<div class="setup-card none"><div class="h"><span>TARGET BAND</span><span>VIX</span></div><div class="b" style="font-size:13px">${s0.lit?.open18 && s0.lit?.vix_move ? `${fmtN(s0.lit.open18 - s0.lit.vix_move, 0)} / ${fmtN(s0.lit.open18 + s0.lit.vix_move, 0)}` : '—'}</div><div class="d">18:00 open ± one VIX day</div></div>`
      : `<div class="setup-card none"><div class="h"><span>LEVELS</span><span>1H</span></div><div class="b" style="font-size:13px">${s0.h1_protected_high ? fmtN(s0.h1_protected_high, 2) : '—'} / ${s0.h1_protected_low ? fmtN(s0.h1_protected_low, 2) : '—'}</div><div class="d">protected high / low</div></div>`);
  const rows = (s.log || []).filter(r => r.type !== 'warn').slice(0, 5);
  $('#thLog', el).innerHTML = rows.map(r => `<div><span>${etStr(r.t)}</span><span>${esc(r.text)}</span></div>`).join('') || '';
}

// ------------------------------------------------------------------ widget: launch readiness
let launchApi = null, rdyOpen = false;
const MANUAL = [['tv_alert', 'TradingView alert on MNQ1! created and active'], ['bridge', 'Bridge connected to the MFFU Tradovate account'], ['pine_bo', 'Blackout list pasted into the Pine input'],
  ['phone', 'Phone alerts tested (Telegram / push)'], ['rules', 'MFFU rules re-read: $1k soft DLL, $2k EOD MLL, flat by close']];
function autoChecks() {
  const s = L.live, wd = L.wd, bo = L.bo, h = s?.health || {};
  const c = [];
  const add = (key, label, state, detail = '') => c.push({ key, label, state, detail });
  add('server', 'Dashboard server reachable', L.online ? 'pass' : L.online === false ? 'fail' : 'wait', L.online ? `${fmtN(L.lat.at(-1)?.ms, 0)} ms` : '');
  if (s) {
    const ad = s.cfg?.adapter || 'paper';
    add('bot', 'Paper bot running on this PC', s.running ? (ad === 'paper' ? 'pass' : 'warn') : 'fail', `adapter=${ad}`);
    add('armed', 'Live NOT armed on this PC', s.cfg?.armed ? 'fail' : 'pass', s.cfg?.armed ? 'armed!' : 'paper only');
    add('kill', 'Kill switch released', s.kill ? 'warn' : 'pass');
    const open = h.market_open ?? marketOpen();
    add('data', 'Futures feed fresh', !open ? 'info' : h.stale ? 'fail' : (h.data_age_s ?? 0) > 1200 ? 'warn' : 'pass', open ? `${dur(h.data_age_s, { short: true })} old · ${h.data_source || ''}` : 'market closed');
  }
  if (wd) {
    add('wd', 'Watchdog thread alive', wd.ok && wd.thread_alive ? 'pass' : 'fail', (wd.issues || [])[0] || '');
    add('awake', 'PC kept awake', wd.keepawake?.held ? 'pass' : 'warn');
    add('auto', 'Auto-resume record saved', wd.autostart_record ? 'pass' : 'warn', wd.autostart?.mode || '');
  }
  if (bo) {
    const m = (bo.text || '').match(/for (\d{4}-\d\d-\d\d) \.\. (\d{4}-\d\d-\d\d)/);
    const covers = m && m[1] <= '2026-10-19' && m[2] >= '2026-10-23';
    add('bo', 'Pine blackout list covers launch week', !bo.present ? 'fail' : covers ? 'pass' : 'warn', m ? `${m[1].slice(5)}..${m[2].slice(5)} · ${bo.lines} releases` : '');
  }
  return c;
}
function renderReady() {
  const el = body('ready'); if (!el) return;
  const now = Date.now() / 1000;
  let checks = launchApi?.checks ? launchApi.checks.map(c => ({ ...c })) : autoChecks();
  const man = pref.get('launchManual', {});
  checks = checks.concat(MANUAL.map(([k, l]) => ({ key: k, label: l, state: man[k] ? 'pass' : 'warn', detail: man[k] ? 'confirmed' : 'click to confirm', manual: true })));
  const graded = checks.filter(c => c.state !== 'info' && c.state !== 'wait');
  const pass = graded.filter(c => c.state === 'pass').length, fail = graded.filter(c => c.state === 'fail').length;
  const frac = graded.length ? pass / graded.length : 0;
  const t = LAUNCH_TS - now;
  meta('ready', src(!!launchApi));
  el.innerHTML = `<div class="rdy-head">${ring(frac, { size: 92, stroke: 9, color: fail ? 'var(--bad)' : frac >= .999 ? 'var(--good)' : 'var(--warn)', value: `${pass}/${graded.length}`, unit: 'ready' })}
      <div><div class="mini-label">${t > 0 ? 'T-minus to launch' : 'Launched'}</div><div class="ck-v sm mono" id="rdyT">${t > 0 ? dur(t) : 'LIVE'}</div>
      <div class="muted small">Sun 2026-10-18 18:00 ET · CME reopen</div><a class="link" data-goto="launch">Open Launch Control →</a></div></div>
    ${(() => {
      const row = (c) => `<div class="rdy ${c.state} ${c.manual ? 'manual' : ''}" ${c.manual ? `data-mk="${c.key}"` : ''}><span class="ic">${{ pass: '✔', warn: '!', fail: '✖', info: 'i', wait: '…' }[c.state] || '·'}</span><span>${esc(c.label)}</span><span class="dt" title="${esc(c.detail || '')}">${esc(c.detail || '')}</span></div>`;
      const rank = { fail: 0, warn: 1, wait: 2, info: 3, pass: 4 };
      const open = checks.filter(c => c.state !== 'pass' || c.manual).sort((a, b) => rank[a.state] - rank[b.state]);
      const ok = checks.filter(c => c.state === 'pass' && !c.manual);
      return `<div class="rdy-list">${open.map(row).join('')}</div>${ok.length ? `<details class="rdy-more" ${rdyOpen ? 'open' : ''}><summary>✔ ${ok.length} automatic check${ok.length > 1 ? 's' : ''} pass</summary><div class="rdy-list">${ok.map(row).join('')}</div></details>` : ''}`;
    })()}`;
  el.querySelectorAll('[data-mk]').forEach(r => r.onclick = () => { const m = pref.get('launchManual', {}); m[r.dataset.mk] = !m[r.dataset.mk]; pref.set('launchManual', m); renderReady(); });
  const det = el.querySelector('.rdy-more'); if (det) det.ontoggle = () => { rdyOpen = det.open; };
}

// ------------------------------------------------------------------ widget: session timeline (18:00 → 17:00 ET)
// minutes after 18:00 ET: the LIT session boxes; the gold strip above them is the 02:00-15:30 entry window
const SEGS = [[0, 120, 'Globex', 'var(--amt)'], [120, 360, 'Asia 20-00', 'var(--amt)'], [480, 540, 'Frankfurt', 'var(--ssl)'], [540, 600, 'London', 'var(--ssl)'], [600, 840, 'Pre-mkt', 'var(--surface-3)'],
  [840, 900, 'NY 08-09', 'var(--bsl)'], [900, 930, '', 'var(--surface-3)'], [930, 1290, 'NY cash', 'var(--ink-2)'], [1290, 1320, 'Flat 15:55', 'var(--bad)'], [1320, 1380, 'Post', 'var(--surface-3)']];
const EVCOL = { sweep: 'var(--gold)', signal: 'var(--accent)', entry: 'var(--accent)', exit: 'var(--good)', order: 'var(--amt)', risk: 'var(--bad)', error: 'var(--bad)', news: 'var(--serious)', tradingview: 'var(--accent-2)' };
function renderTimeline() {
  const el = body('timeline'); if (!el) return;
  if (!L.live) { el.innerHTML = waiting('Waiting for live bars'); return; }
  const { bars, date } = dayBars();
  if (!date) { el.innerHTML = waiting('No bars yet', 'The paper bot has not loaded any 5m bars.'); return; }
  const [y, mo, d] = date.split('-').map(Number);
  const prev = new Date(Date.UTC(y, mo - 1, d) - 86400000);
  const t0 = etToTs(prev.getUTCFullYear(), prev.getUTCMonth() + 1, prev.getUTCDate(), 18, 0);
  const span = 1380 * 60;
  const W = Math.max(300, Math.round(el.clientWidth || 1000)), PH = 74, X = (t) => Math.max(0, Math.min(W, (t - t0) / span * W));
  let svg = '';
  // price path
  if (bars.length > 1) {
    const hi = Math.max(...bars.map(b => b.h)), lo = Math.min(...bars.map(b => b.l)), sp = hi - lo || 1;
    const Y = (v) => 6 + (hi - v) / sp * (PH - 12);
    const line = bars.map((b, i) => `${i ? 'L' : 'M'}${X(b.t + 300).toFixed(1)} ${Y(b.c).toFixed(1)}`).join(' ');
    svg += `<defs><linearGradient id="tlG" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${css('--accent')}" stop-opacity=".28"/><stop offset="1" stop-color="${css('--accent')}" stop-opacity="0"/></linearGradient></defs>
      <path d="${line} L${X(bars.at(-1).t + 300)} ${PH} L${X(bars[0].t + 300)} ${PH} Z" fill="url(#tlG)"/><path d="${line}" fill="none" stroke="var(--accent)" stroke-width="1.6" vector-effect="non-scaling-stroke"/>
      <text x="4" y="12" font-size="10" fill="var(--muted)">H ${fmtN(hi, 2)}</text><text x="4" y="${PH - 3}" font-size="10" fill="var(--muted)">L ${fmtN(lo, 2)}</text>`;
    // events on the path
    for (const r of (L.log || [])) {
      if (!EVCOL[r.type] || r.t < t0 || r.t > t0 + span) continue;
      const bb = bars.reduce((best, b) => Math.abs(b.t - r.t) < Math.abs(best.t - r.t) ? b : best, bars[0]);
      svg += `<g><title>${esc(etStr(r.t))} ${esc(r.text)}</title><line x1="${X(r.t)}" x2="${X(r.t)}" y1="${Y(bb.c)}" y2="${PH}" stroke="${EVCOL[r.type]}" stroke-width="1" opacity=".55"/><circle cx="${X(r.t)}" cy="${Y(bb.c)}" r="4" fill="${EVCOL[r.type]}" stroke="var(--surface)" stroke-width="1.5"/></g>`;
    }
  } else svg += `<text x="${W / 2}" y="${PH / 2}" text-anchor="middle" font-size="12" fill="var(--muted)">no bars yet for this session</text>`;
  // session bands
  for (const [a, b, name, col] of SEGS) {
    svg += `<rect x="${a / 1380 * W}" y="${PH + 6}" width="${(b - a) / 1380 * W - 1}" height="16" rx="3" fill="${col}" opacity="${col.includes('surface') ? .9 : .45}"/>
      ${(b - a) >= 100 ? `<text x="${(a + b) / 2 / 1380 * W}" y="${PH + 18}" text-anchor="middle" font-size="9.5" fill="var(--ink)" font-weight="600">${name}</text>` : ''}`;
  }
  svg += `<rect x="${480 / 1380 * W}" y="${PH + 1}" width="${(1290 - 480) / 1380 * W}" height="4" rx="2" fill="var(--gold)" opacity=".85"><title>LIT entry window 02:00-15:30 ET</title></rect>`;
  // blackout windows today
  const p = S.meta?.defaults || {};
  for (const e of (L.bo?.entries || [])) {
    const m = e.match(/(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d)/); if (!m) continue;
    const t = etToTs(+m[1], +m[2], +m[3], +m[4], +m[5]);
    if (t < t0 || t > t0 + span) continue;
    const a = t - (p.news_before_min ?? 15) * 60, b = t + (p.news_after_min ?? 30) * 60;
    svg += `<rect x="${X(a)}" y="0" width="${X(b) - X(a)}" height="${PH + 22}" fill="var(--bad)" opacity=".14"><title>news blackout ${etStr(a)}–${etStr(b)} ET</title></rect>`;
  }
  // hour ticks + now cursor
  const step = W < 600 ? 4 : 2;
  for (let h = 0; h <= 23; h += step) { const mm = h * 60; const x = mm / 1380 * W; if (mm > 1380) break; const hh = (18 + h) % 24; svg += `<text x="${x}" y="${PH + 36}" text-anchor="${h === 0 ? 'start' : 'middle'}" font-size="9.5" fill="var(--muted)">${String(hh).padStart(2, '0')}</text>`; }
  const now = Date.now() / 1000;
  if (now > t0 && now < t0 + span) svg += `<line class="now-line" x1="${X(now)}" x2="${X(now)}" y1="0" y2="${PH + 24}" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="3 2"/><text x="${X(now)}" y="${PH + 48}" text-anchor="middle" font-size="9.5" font-weight="700" fill="var(--ink)">NOW</text>`;
  const cur = date === tradingDate();
  meta('timeline', `<span class="pill">${cur ? 'today' : 'last session'} · ${esc(date)}</span>`);
  el.innerHTML = `<div class="tl"><svg viewBox="0 0 ${W} ${PH + 52}" width="${W}" height="${PH + 52}" style="width:100%;height:auto">${svg}</svg></div>
    <div class="tl-legend"><span><i style="background:var(--gold)"></i>sweep · entry window 02:00-15:30</span><span><i style="background:var(--accent)"></i>signal / entry</span><span><i style="background:var(--good)"></i>exit</span><span><i style="background:color-mix(in srgb,var(--bad) 40%,transparent)"></i>news blackout</span><span><i style="background:var(--amt)"></i>Asia</span><span><i style="background:var(--ssl)"></i>London</span></div>`;
}

// ------------------------------------------------------------------ widget: live liquidity map
let liqApi = null;
function renderLmap() {
  const el = body('lmap'); if (!el) return;
  const s0 = st();
  let price, pools, adr = liqApi?.adr20 ?? null;
  if (liqApi?.pools) {
    price = liqApi.price;
    pools = [...(liqApi.levels || []).map(l => ({ ...l, key: true })), ...liqApi.pools].map(p => ({ label: p.label, price: p.price, side: p.side, strength: p.strength ?? 2, key: p.key, swept: p.swept }));
  } else if (s0) { price = s0.price; pools = (s0.active_pools || []).map(p => ({ label: p.label, price: p.price, side: p.side, strength: p.strength })); }
  else { el.innerHTML = waiting('Waiting for the engine pools'); return; }
  meta('lmap', src(!!liqApi));
  const above = pools.filter(p => p.price > price && !p.swept).sort((a, b) => a.price - b.price).slice(0, 6);
  const below = pools.filter(p => p.price < price && !p.swept).sort((a, b) => b.price - a.price).slice(0, 6);
  if (!above.length && !below.length) { el.innerHTML = waiting('No untaken pools near price'); return; }
  const rows = [...above.reverse(), { now: true }, ...below];
  const W = 420, rh = 25, H = rows.length * rh + 8;
  const maxD = Math.max(1, ...[...above, ...below].map(p => Math.abs(p.price - price)));
  let y = 4, out = '';
  const setups = s0?.setups || {};
  for (const p of rows) {
    if (p.now) {
      out += `<rect x="0" y="${y + 1}" width="${W}" height="${rh - 2}" rx="6" fill="var(--accent)" opacity=".18"/><line class="now-line" x1="0" x2="${W}" y1="${y + rh / 2}" y2="${y + rh / 2}" stroke="var(--accent)" stroke-width="1.5"/>
        <text x="8" y="${y + 16}" font-size="12" font-weight="700" fill="var(--ink)">NQ ${fmtN(price, 2)}</text>
        <text x="${W - 6}" y="${y + 16}" font-size="10.5" text-anchor="end" fill="var(--ink-2)">${['long', 'short'].filter(k => setups[k]).map(k => `${k} armed @ ${fmtN(setups[k].ext, 0)}`).join(' · ') || 'no setup armed'}</text>`;
    } else {
      const d = p.price - price, col = p.side === 'H' ? 'var(--bsl)' : 'var(--ssl)';
      const len = Math.max(6, Math.abs(d) / maxD * 120), heatOp = 1 - Math.min(.65, Math.abs(d) / maxD * .65);
      out += `<g opacity="${heatOp.toFixed(2)}"><rect x="0" y="${y + 3}" width="3" height="${rh - 6}" rx="1.5" fill="${col}"/>
        <text x="10" y="${y + 16}" font-size="11.5" fill="${col}" font-weight="${p.strength >= 2 || p.key ? 700 : 500}">${p.side === 'H' ? 'BSL' : 'SSL'} ${esc(String(p.label).replace(/·/g, ' ').slice(0, 22))}</text>
        <text x="${W - 182}" y="${y + 16}" font-size="11.5" text-anchor="end" fill="var(--ink-2)">${fmtN(p.price, 2)}</text>
        <rect x="${W - 170}" y="${y + 8}" width="${len}" height="9" rx="3" fill="${col}" opacity="${p.strength >= 2 ? .85 : .5}"/>
        <text x="${W - 4}" y="${y + 16}" font-size="11" text-anchor="end" fill="var(--muted)">${d > 0 ? '+' : ''}${fmtN(d, 1)}${adr ? ` · ${fmtN(Math.abs(d) / adr, 2)}×` : ''}</text></g>`;
    }
    y += rh;
  }
  el.innerHTML = `<div class="lmap"><svg viewBox="0 0 ${W} ${H}">${out}</svg></div><div class="muted small">Untaken pools the engine tracks, nearest first. Brighter = closer. ${adr ? `× = distance in ADR20 (${fmtN(adr, 0)} pts).` : 'Distance in NQ points.'}</div>`;
}

// ------------------------------------------------------------------ widget: session ranges
let sessApi = null;
function renderSessions() {
  const el = body('sessions'); if (!el) return;
  let rows, day, api = false;
  if (sessApi?.sessions && S.res?.model !== 'lit') { api = true; rows = sessApi.sessions.map(s => ({ name: s.name, sub: `${s.start_et}–${s.end_et}`, hi: s.high, lo: s.low, rng: s.range, pct: s.pct_of_avg, state: s.state })); day = sessApi.day; }
  else {
    const { bars, date } = dayBars();
    if (!bars.length) { el.innerHTML = waiting('Waiting for today\'s bars'); return; }
    const [y, mo, d] = date.split('-').map(Number);
    const pd = new Date(Date.UTC(y, mo - 1, d) - 86400000);
    const at = (dd, h, m) => etToTs(dd.y, dd.mo, dd.d, h, m);
    const P = { y: pd.getUTCFullYear(), mo: pd.getUTCMonth() + 1, d: pd.getUTCDate() }, D = { y, mo, d };
    // the LIT session boxes (engine/lit.py SESSIONS): their highs and lows are LIT levels
    const defs = [['Asia', '20:00–00:00', at(P, 20, 0), at(D, 0, 0)], ['Frankfurt', '02:00–03:00', at(D, 2, 0), at(D, 3, 0)], ['London', '03:00–04:00', at(D, 3, 0), at(D, 4, 0)],
      ['Premarket', '04:00–09:30', at(D, 4, 0), at(D, 9, 30)], ['NY 08-09', '08:00–09:00', at(D, 8, 0), at(D, 9, 0)], ['NY cash', '09:30–16:00', at(D, 9, 30), at(D, 16, 0)]];
    const now = Date.now() / 1000;
    rows = defs.map(([name, sub, a, b]) => {
      const bb = bars.filter(x => x.t >= a && x.t < b);
      return { name, sub, hi: bb.length ? Math.max(...bb.map(x => x.h)) : null, lo: bb.length ? Math.min(...bb.map(x => x.l)) : null, state: now >= b ? 'done' : now >= a ? 'active' : 'upcoming' };
    }).map(r => ({ ...r, rng: r.hi != null ? r.hi - r.lo : null }));
    day = { high: Math.max(...bars.map(x => x.h)), low: Math.min(...bars.map(x => x.l)) }; day.range = day.high - day.low;
  }
  meta('sessions', src(api));
  const lo = day.low, hi = day.high, sp = (hi - lo) || 1, price = st()?.price;
  const X = (v) => ((v - lo) / sp * 100).toFixed(2);
  const col = { Asia: 'var(--amt)', London: 'var(--ssl)', Overnight: 'var(--muted)', 'NY AM': 'var(--gold)', Lunch: 'var(--ink-2)', 'NY PM': 'var(--gold)' };
  el.innerHTML = rows.map(r => `<div class="sr-row"><div class="n">${esc(r.name)}<small>${esc(r.sub || '')}</small></div>
      <div class="sr-track">${r.hi != null ? `<div class="sr-rng ${r.state === 'active' ? 'active' : ''}" style="left:${X(r.lo)}%;width:${Math.max(.6, (r.hi - r.lo) / sp * 100).toFixed(2)}%;--c:${col[r.name] || 'var(--accent)'}" title="${fmtN(r.lo, 2)} – ${fmtN(r.hi, 2)}"></div>` : ''}
        ${price != null && price >= lo && price <= hi ? `<div class="sr-px" style="left:${X(price)}%"></div>` : ''}</div>
      <div class="r">${r.rng != null ? fmtN(r.rng, 1) : r.state === 'upcoming' ? '<span class="muted">later</span>' : '—'}<small>${r.pct != null ? Math.round(r.pct) + '% avg' : r.state}</small></div></div>`).join('') +
    `<div class="acct-row"><span>Day range</span><b>${fmtN(day.range, 2)} pts · ${fmtN(lo, 2)} – ${fmtN(hi, 2)}</b></div>${api ? '' : '<div class="muted small" style="margin-top:6px">20-day session averages appear when /api/dash/sessions is live.</div>'}`;
}

// ------------------------------------------------------------------ widget: regime & volatility gauges
let regApi = null, mkts = null;
function renderRegime() {
  const el = body('regime'); if (!el) return;
  let er10, regime, rangePct, vix, series, api = !!regApi, thr = 0.45, guard = null;
  if (regApi?.daily) {
    const d = regApi.daily; er10 = d.er10; regime = d.regime; thr = d.regime_threshold ?? .45; rangePct = d.today_pct_adr; vix = regApi.vix?.VIX?.last ?? regApi.vix?.VIX?.close ?? null;
    series = (regApi.series || []).map(x => x.er10); guard = d.day_range_guard;
  } else {
    const days = S.res?.days || [];
    const last = days.at(-1);
    if (!last && !mkts) { el.innerHTML = waiting('Waiting for the backtest', 'Regime comes from the latest session of the backtest.'); return; }
    er10 = last?.er10; regime = last?.regime; series = days.slice(-60).map(x => x.er10);
    vix = mkts?.rows?.find(r => r.key === 'VIX')?.last;
    rangePct = last?.vol_expansion != null ? last.vol_expansion * 100 : null;
  }
  meta('regime', `${src(api)} <span class="pill ${regime === 'trending' ? 'bad' : 'good'}">${esc(regime || '—')}</span>`);
  const gEr = arcGauge(er10 != null ? Math.min(1, er10 / .9) : 0, { color: er10 > thr ? 'var(--warn)' : 'var(--good)', value: er10 != null ? fmtN(er10, 2) : '—', unit: 'trend eff.', mark: thr / .9, w: 140 });
  const gR = arcGauge(rangePct != null ? Math.min(1, rangePct / 200) : 0, { color: rangePct > 160 ? 'var(--bad)' : rangePct > 120 ? 'var(--warn)' : 'var(--accent)', value: rangePct != null ? Math.round(rangePct) + '%' : '—', unit: api ? 'range / ADR' : 'vol expansion', mark: api ? .8 : null, w: 140 });
  const gV = arcGauge(vix != null ? Math.min(1, Math.max(0, (vix - 10) / 30)) : 0, { color: vix > 25 ? 'var(--bad)' : vix > 20 ? 'var(--warn)' : 'var(--good)', value: vix != null ? fmtN(vix, 1) : '—', unit: 'VIX', mark: (20 - 10) / 30, w: 140 });
  el.innerHTML = `<div class="gauge3"><div>${gEr}<div class="gl">Trendiness</div><div class="gs">ER10 · trending &gt; ${thr}</div></div><div>${gR}<div class="gl">${api ? 'Day range' : 'Volatility'}</div><div class="gs">${guard ? `guard ${fmtN(guard.used_x_adr, 2)}× of ${guard.limit_x_adr}×` : api ? 'vs 20-day ADR' : 'vs 20-day norm'}</div></div><div>${gV}<div class="gl">Fear gauge</div><div class="gs">VIX · 20 = caution</div></div></div>
    ${series?.length > 2 ? `<div class="mini-label" style="margin-top:8px">ER10 · last ${series.length} sessions</div>${spark(series, { w: 300, h: 34, color: css('--warn') })}` : ''}
    ${guard?.blocks_entries ? `<div class="rdy fail" style="margin-top:8px"><span class="ic">✖</span><span>Day-range guard is <b>blocking new entries</b>: today ran ${fmtN(guard.used_x_adr, 2)}× ADR (limit ${guard.limit_x_adr}×)</span><span></span></div>` : ''}
    <div class="muted small" style="margin-top:6px">${S.res?.model === 'lit' ? 'Context only: LIT has no regime or day-range rule. Its target is the VIX one-day move from the 18:00 open, so a higher VIX means a wider target band.' : `Trending days (ER10 &gt; ${thr}) take reversals at half size; the day-range guard blocks entries after 1.6× ADR.`}</div>`;
}

// ------------------------------------------------------------------ widget: live event feed
let feedFilter = pref.get('feedFilter', 'all'), feedMaxT = 0;
const FF = { all: null, trades: ['signal', 'entry', 'exit', 'order'], liquidity: ['sweep', 'skip', 'expire'], risk: ['risk', 'news', 'error', 'warn'], system: ['system', 'tradingview', 'daily'] };
function renderFeed() {
  const el = body('lfeed'); if (!el) return;
  if (!el.querySelector('.lfeed')) {
    el.innerHTML = `<div class="seg sm" id="lfSeg" style="margin-bottom:8px">${Object.keys(FF).map(k => `<button data-v="${k}" class="${k === feedFilter ? 'on' : ''}">${k}</button>`).join('')}</div><div class="lfeed" id="lfList"></div>`;
    $('#lfSeg', el).onclick = (e) => { const b = e.target.closest('button'); if (!b) return; feedFilter = b.dataset.v; pref.set('feedFilter', feedFilter); $$('#lfSeg button', el).forEach(x => x.classList.toggle('on', x === b)); feedMaxT = 0; renderFeed(); };
  }
  const rows = [];
  for (const r of (L.log || []).filter(r => !FF[feedFilter] || FF[feedFilter].includes(r.type))) {
    const last = rows.at(-1);
    if (last && last.type === r.type && last.text === r.text) { last.n = (last.n || 1) + 1; continue; }   // repeated feed warnings collapse to one row
    rows.push({ ...r });
    if (rows.length >= 80) break;
  }
  meta('lfeed', `<span class="dot-live ${L.online ? '' : 'bad'}"></span> ${L.sseOk ? 'stream' : 'poll 10s'} · ${(L.log || []).length} rows`);
  const prevMax = feedMaxT;
  feedMaxT = Math.max(feedMaxT, ...rows.map(r => r.t), 0);
  const TAG = { sweep: 'SWEEP', signal: 'SIGNAL', entry: 'ENTRY', exit: 'EXIT', skip: 'PASS', expire: 'EXPIRE', risk: 'RISK', order: 'ORDER', system: 'SYS', error: 'ERR', warn: 'WARN', news: 'NEWS', tradingview: 'TV', daily: 'DAILY' };
  $('#lfList', el).innerHTML = rows.length ? rows.map(r => `<div class="ev ${r.type} ${prevMax && r.t > prevMax ? 'new' : ''}"><div class="t">${etStr(r.t)}<br>${etStr(r.t, true).slice(5, 10)}</div><div><span class="tag">${TAG[r.type] || esc(String(r.type).toUpperCase())}</span>${esc(r.text)}${r.n ? ` <span class="pill">×${r.n}</span>` : ''}</div></div>`).join('')
    : `<div class="empty">No ${feedFilter === 'all' ? '' : feedFilter + ' '}events in the bot log yet.</div>`;
}

// ------------------------------------------------------------------ widget: eval pass odds (Monte Carlo)
let mcRes = null, mcKey = '';
// LIT (web_next, S.res.model 'lit'): bootstrap of the LIT replay days through the MFFU rules, here in the browser
// (the /api/dash and /api/montecarlo backtests run the previous engine)
function litOdds(res, runs = 3000, horizon = 60) {
  const plan = res.plan, days = res.days;
  if (!plan || !days?.length) return null;
  let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  let pass = 0, fail = 0; const dtp = [], fin = [];
  for (let k = 0; k < runs; k++) {
    let bal = plan.start, peak = bal, mll = bal - plan.mll, res0 = 'OPEN';
    const lock = plan.start + (plan.lock_above ?? 1e9);
    for (let j = 0; j < horizon; j++) {
      const d = days[Math.floor(rnd() * days.length)];
      const low = bal + Math.min(0, d.low_intraday ?? Math.min(0, d.pnl));
      bal += d.pnl;
      if (low <= mll || bal <= mll) { res0 = 'FAIL'; break; }
      peak = Math.max(peak, bal); mll = Math.min(Math.max(mll, peak - plan.mll), lock);
      if (bal - plan.start >= plan.target) { res0 = 'PASS'; dtp.push(j + 1); break; }
    }
    if (res0 === 'PASS') pass++; else if (res0 === 'FAIL') fail++;
    fin.push(bal);
  }
  dtp.sort((a, b) => a - b); fin.sort((a, b) => a - b);
  const q = (a, f) => a.length ? a[Math.min(a.length - 1, Math.floor(f * a.length))] : null;
  const pp = pass / runs * 100, fp = fail / runs * 100;
  return { pass_prob: Math.round(pp * 10) / 10, fail_prob: Math.round(fp * 10) / 10, open_prob: Math.round((100 - pp - fp) * 10) / 10,
    days_to_pass: { median: q(dtp, .5), p90: q(dtp, .9) }, final: { p5: q(fin, .05), p50: q(fin, .5), p95: q(fin, .95) }, api: false,
    basis: `bootstrap of the ${days.length} LIT replay sessions ${res.range?.[0] || ''} → ${res.range?.[1] || ''}` };
}
async function loadOdds() {
  if (S.res?.model === 'lit') { mcRes = litOdds(S.res); renderOdds(); return; }
  const api = await dash('/api/dash/montecarlo?n=3000&horizon=60', { ttl: 120000 });
  if (api) { mcRes = { ...api, api: true, basis: `${api.meta?.source || 'backtest'} · ${api.meta?.sessions ?? '?'} sessions` }; renderOdds(); return; }
  if (!S.res) return;
  const key = JSON.stringify([S.sym, S.params]);
  if (key === mcKey && mcRes) return;
  mcKey = key;
  const r = await getJSON('/api/montecarlo', { ttl: 600000, body: { sym: S.sym, tf: S.tf, plan: S.plan, params: S.params, runs: 3000, horizon: 60 } });
  if (r) { mcRes = { pass_prob: r.pass_prob, fail_prob: r.fail_prob, open_prob: r.open_prob ?? Math.max(0, 100 - r.pass_prob - r.fail_prob), days_to_pass: { median: r.median_days_to_pass, p90: r.p90_days_to_pass }, final: { p5: r.final_p5, p50: r.final_p50, p95: r.final_p95 }, api: false, basis: `bootstrap of all ${S.res.days.length} backtest days` }; renderOdds(); }
}
function renderOdds() {
  const el = body('odds'); if (!el) return;
  if (!mcRes) { el.innerHTML = waiting('Simulating 3,000 evals…', 'Bootstrap of daily P&L through the MFFU rules.'); return; }
  const m = mcRes;
  meta('odds', src(m.api));
  el.innerHTML = `<div class="rdy-head">${ring(m.pass_prob / 100, { size: 96, stroke: 10, color: m.pass_prob >= 50 ? 'var(--good)' : m.pass_prob >= 25 ? 'var(--warn)' : 'var(--bad)', value: Math.round(m.pass_prob) + '%', unit: 'pass' })}
      <div style="min-width:0"><div class="mini-label">Within 60 trading days</div><div class="small" style="margin-top:4px;line-height:1.6">Median pass in <b>${m.days_to_pass?.median != null ? Math.round(m.days_to_pass.median) + ' days' : '—'}</b>${m.days_to_pass?.p90 != null ? ` · 90% by ${Math.round(m.days_to_pass.p90)}` : ''}<br>Fail ${fmtN(m.fail_prob, 1)}% · still open ${fmtN(m.open_prob, 1)}%</div></div></div>
    <div class="mc-stack"><div style="width:${m.pass_prob}%;background:var(--good)"></div><div style="width:${m.open_prob}%;background:var(--accent);opacity:.55"></div><div style="width:${m.fail_prob}%;background:var(--bad)"></div></div>
    <div class="mc-legend"><span><i style="background:var(--good)"></i>pass</span><span><i style="background:var(--accent);opacity:.55"></i>open</span><span><i style="background:var(--bad)"></i>fail</span></div>
    <div class="muted small" style="margin-top:6px">Basis: ${esc(m.basis)}. History, not a promise.</div>`;
}

// ------------------------------------------------------------------ widget: NQ vs ES relative strength
let imApi = null;
function renderRS() {
  const el = body('rs'); if (!el) return;
  let nqP, esP, today, c20, c60, beta, api = false, leader;
  if (imApi?.rs_series) {
    api = true; nqP = imApi.rs_series.map(x => x.nq); esP = imApi.rs_series.map(x => x.es);
    today = imApi.today; c20 = imApi.corr?.d20; c60 = imApi.corr?.d60; beta = imApi.beta_60d; leader = today?.leader;
  } else if (mkts?.rows) {
    const nq = mkts.rows.find(r => r.key === 'NQ'), es = mkts.rows.find(r => r.key === 'ES');
    if (!nq || !es) { el.innerHTML = waiting('No ES futures row in /api/markets'); return; }
    nqP = nq.spark.map(v => 100 + v); esP = es.spark.map(v => 100 + v);
    today = { nq_chg_pct: nq.chg_pct, es_chg_pct: es.chg_pct, spread_pct: nq.chg_pct - es.chg_pct }; c20 = es.corr20; c60 = es.corr60;
    leader = today.spread_pct > 0 ? 'NQ' : 'ES';
  } else { el.innerHTML = waiting('Waiting for NQ / ES futures'); return; }
  meta('rs', src(api));
  const rs = nqP.map((v, i) => v / esP[i] * 100);
  const W = 300, H = 90;
  const all = [...nqP, ...esP], lo = Math.min(...all), hi = Math.max(...all), sp = hi - lo || 1;
  const path = (arr) => arr.map((v, i) => `${i ? 'L' : 'M'}${(i / (arr.length - 1) * W).toFixed(1)} ${(4 + (hi - v) / sp * (H - 8)).toFixed(1)}`).join(' ');
  const rsTxt = rs.at(-1) - rs[0];
  el.innerHTML = `<div class="kst-row"><div class="kst"><div class="k">NQ today</div><div class="v ${cls(today.nq_chg_pct)}">${today.nq_chg_pct > 0 ? '+' : ''}${fmtN(today.nq_chg_pct, 2)}%</div></div>
      <div class="kst"><div class="k">ES today</div><div class="v ${cls(today.es_chg_pct)}">${today.es_chg_pct > 0 ? '+' : ''}${fmtN(today.es_chg_pct, 2)}%</div></div>
      <div class="kst"><div class="k">Leader</div><div class="v">${esc(leader || '—')}</div><div class="s">spread ${fmtN(today.spread_pct, 2)}%</div></div></div>
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="width:100%;height:96px;margin-top:8px"><path d="${path(esP)}" fill="none" stroke="var(--muted)" stroke-width="1.4" vector-effect="non-scaling-stroke"/><path d="${path(nqP)}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>
    <div class="tl-legend"><span><i style="background:var(--accent)"></i>NQ</span><span><i style="background:var(--muted)"></i>ES</span><span>${nqP.length}-day path · NQ/ES ${rsTxt >= 0 ? '+' : ''}${fmtN(rsTxt, 2)}%</span></div>
    <div class="acct-row"><span>Correlation 20d / 60d</span><b>${fmtN(c20, 2)} / ${fmtN(c60, 2)}${beta != null ? ` · β ${fmtN(beta, 2)}` : ''}</b></div>
    ${imApi?.smt?.today?.length ? `<div class="mini-label" style="margin-top:8px">SMT · levels swept today (NQ / ES)</div><div class="smt-grid">${imApi.smt.today.map(x => `<span class="smt ${x.divergence ? 'div' : x.nq_swept && x.es_swept ? 'both' : 'none'}" title="${esc(x.note || (x.divergence ? 'divergence' : x.nq_swept ? 'both swept' : 'untouched'))}">${esc(x.level)} <i>${x.nq_swept ? '●' : '○'}${x.es_swept ? '●' : '○'}</i></span>`).join('')}</div>${imApi.smt.today.some(x => x.divergence) ? `<div class="note">${imApi.smt.today.filter(x => x.divergence).map(x => esc(x.note || x.level + ' divergence')).join('<br>')}</div>` : '<div class="muted small">No SMT divergence: NQ and ES took the same levels.</div>'}` : ''}`;
}

// ------------------------------------------------------------------ widget: underwater drawdown (backtest)
function renderUW(res) {
  const el = body('uw'); if (!el) return;
  if (!res?.days?.length) { el.innerHTML = waiting('Waiting for the backtest'); return; }
  if (!el.querySelector('canvas')) el.innerHTML = `<div class="kst-row" id="uwStats"></div><div class="chart-box h200" style="margin-top:8px"><canvas id="dashUW"></canvas></div>`;
  // cumulative strategy P&L (the simulated account balance resets after an MLL breach, so it would read as never recovering)
  let eq = 0, peak = 0, cur = 0, longest = 0, run = 0, under = 0, maxDD = 0, maxDate = '';
  const dd = res.days.map(d => { eq += d.pnl || 0; peak = Math.max(peak, eq); const v = eq - peak; if (v < -0.5) { run++; under++; } else run = 0; longest = Math.max(longest, run); if (v < maxDD) { maxDD = v; maxDate = d.date; } cur = v; return +v.toFixed(2); });
  $('#uwStats', el).innerHTML = stat('Max drawdown', fmt$(maxDD), maxDate, 'dn') + stat('Current', fmt$(cur), cur < 0 ? `${run} days under` : 'at a high', cur < 0 ? 'dn' : 'up') +
    stat('Longest under', `${longest}d`, 'trading days') + stat('Time under water', Math.round(under / dd.length * 100) + '%', `${res.days.length} sessions`);
  cj('dashUW', { type: 'line', data: { labels: res.days.map(d => d.date), datasets: [
    { label: 'Drawdown', data: dd, borderColor: css('--bad'), borderWidth: 1.4, pointRadius: 0, fill: 'origin', backgroundColor: (ctx) => { const a = ctx.chart.chartArea; if (!a) return 'transparent'; const g = ctx.chart.ctx.createLinearGradient(0, a.top, 0, a.bottom); g.addColorStop(0, 'transparent'); g.addColorStop(1, css('--bad') + '66'); return g; } },
    { label: 'MLL ($2,000)', data: dd.map(() => -2000), borderColor: css('--warn'), borderDash: [5, 4], borderWidth: 1.2, pointRadius: 0 }] },
    options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'end' }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt$(c.parsed.y)}` } } },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 7, callback(v) { return String(this.getLabelForValue(v)).slice(0, 7); } } }, y: { grid: { color: css('--grid') }, ticks: { callback: v => '$' + (v / 1000).toFixed(1) + 'k' } } } }) });
}

// ------------------------------------------------------------------ widget: confluence leaderboard
let confData = null;
async function loadConf() {
  const api = await dash('/api/dash/confluence?sort=lift', { ttl: 300000 });
  if (api?.items) { confData = { api: true, items: api.items.map(i => ({ name: i.name, status: i.status, lift: i.lift_pooled, verdict: i.verdict, n: i.n_on })), gen: api.generated }; renderConf(); return; }
  const r = await getJSON('/api/confluence/registry', { ttl: 300000 });
  if (r?.data?.items) confData = { api: false, items: Object.values(r.data.items).filter(i => !i.stale).map(i => ({ name: i.name, status: i.status, lift: i.evidence?.candidates?.pooled, verdict: i.scan?.verdict, n: i.evidence?.candidates?.n_on })), gen: r.data.generated };
  renderConf();
}
let confTab = 'ACTIVE';
function renderConf() {
  const el = body('conflb'); if (!el) return;
  if (!confData) { el.innerHTML = waiting('Loading the confluence registry'); return; }
  meta('conflb', src(confData.api));
  const rows = confData.items.filter(i => confTab === 'ALL' || i.status === confTab).filter(i => i.lift != null).sort((a, b) => b.lift - a.lift).slice(0, 8);
  const max = Math.max(.3, ...rows.map(r => Math.abs(r.lift)));
  el.innerHTML = `<div class="seg sm" id="clSeg" style="margin-bottom:6px">${['ACTIVE', 'PROBATION', 'CANDIDATE', 'ALL'].map(k => `<button data-v="${k}" class="${k === confTab ? 'on' : ''}">${k.toLowerCase()}</button>`).join('')}</div>
    ${rows.length ? rows.map((r, i) => `<div class="lb-row"><span class="rk">${i + 1}</span><span class="nm">${esc(r.name)}<small>${esc(r.status)} · ${esc(r.verdict || '')} · n ${r.n ?? '—'}</small></span>
      <div class="dbar"><span class="${r.lift >= 0 ? 'pos' : 'neg'}" style="${r.lift >= 0 ? 'left:50%' : `left:${50 - Math.abs(r.lift) / max * 50}%`};width:${Math.abs(r.lift) / max * 50}%"></span></div><span class="lift ${cls(r.lift)}">${fmtR(r.lift)}</span></div>`).join('') : '<div class="empty">Nothing in this group.</div>'}
    <div class="muted small" style="margin-top:6px">Pooled lift on NQ futures candidates (avg R with − without). Registry ${esc(confData.gen || '')}. <a class="link" data-goto="conf">Confluence Lab →</a></div>`;
  $('#clSeg', el).onclick = (e) => { const b = e.target.closest('button'); if (b) { confTab = b.dataset.v; renderConf(); } };
}

// ------------------------------------------------------------------ widget: memory insights
async function renderMemory() {
  const el = body('meminsight'); if (!el) return;
  const api = await dash('/api/dash/memory', { ttl: 60000 });
  const fb = api ? null : await getJSON('/api/memory/stats', { ttl: 60000 });
  if (!api && !fb) { el.innerHTML = waiting('Trade memory unavailable'); return; }
  meta('meminsight', src(!!api));
  const counts = api?.counts || fb?.counts || {};
  const real = api?.realised || fb?.realised || {};
  const sigs = api?.signals || (fb?.learner?.signals || []).map(s => ({ key: s.key || s.signal, n: s.n, avg_gain: s.avg_gain, learned: s.learned, to_go: Math.max(0, (fb.learner.learn_min || 20) - (s.n || 0)) }));
  const cond = api?.conditions;
  el.innerHTML = `<div class="kst-row">${stat('Paper', counts.paper ?? 0, 'trades')}${stat('Live', counts.live ?? 0, 'trades')}${stat('Realised', real.trades ? fmtS$(real.net) : '—', real.trades ? `${fmtN(real.win_rate, 0)}% · ${fmtR(real.avg_r)}` : 'no trades yet', cls(real.net))}</div>
    ${real.trades ? '' : `<div class="note">${esc(api?.message || 'No paper trades in memory yet. The memory fills after the first paper trade; an exit signal is learned after 20 cases averaging +0.2R.')}</div>`}
    ${sigs.length ? `<div class="mini-label" style="margin-top:10px">Exit signals being learned</div>${sigs.slice(0, 6).map(s => `<div class="acct-row"><span>${esc(s.key)}</span><b>${s.learned ? '<span class="up">learned</span>' : `${s.n || 0} / 20 · ${s.to_go ?? '—'} to go`}</b></div>`).join('')}` : ''}
    ${cond ? `<div class="mini-label" style="margin-top:10px">Best / worst conditions · ${esc(cond.source)}</div>${(cond.best || []).slice(0, 2).map(c => `<div class="acct-row"><span>${esc(c.dim)}: ${esc(c.key)}</span><b class="up">${fmtR(c.avg_r)} · n ${c.n}</b></div>`).join('')}${(cond.worst || []).slice(0, 2).map(c => `<div class="acct-row"><span>${esc(c.dim)}: ${esc(c.key)}</span><b class="dn">${fmtR(c.avg_r)} · n ${c.n}</b></div>`).join('')}` : ''}
    <a class="link" data-goto="memory">Trade memory →</a>`;
}

// ------------------------------------------------------------------ registration
const ADOPT = [['kpis', 'Backtest KPIs', 'xl', 'cmdKpis'], ['equity', 'Equity · simulated MFFU account', 'w'], ['account', 'MFFU eval · backtest', 'm'], ['state', 'Model state · last backtest bar', 'm'],
  ['ladder', 'Liquidity ladder · backtest', 'm'], ['clock', 'Session clock', 'm'], ['mtf', 'Multi-timeframe alignment', 'l'], ['pd', 'Premium / discount', 'l'], ['brain', 'Bot brain · backtest', 'l'],
  ['trades', 'Recent trades', 'l'], ['whatif', 'What-if', 'm', 'cmdWhatIf'], ['edge', 'Edge decay', 'm', 'cmdEdge'], ['rules', 'MFFU rules gauges', 'l', 'cmdRules']];

export function initHome() {
  const page = $('#page-command'); if (!page) return;
  const ck = $('#cockpit'); if (ck) cockpitSkeleton(ck);
  // new live widgets
  widget({ id: 'think', page: 'command', title: 'What the bot is thinking', size: 'w' });
  widget({ id: 'ready', page: 'command', title: 'Launch readiness', size: 'm' });
  widget({ id: 'timeline', page: 'command', title: 'Session timeline · 18:00 → 17:00 ET', size: 'xl', csv: () => ({ name: 'session_events', rows: (L.log || []).map(r => ({ t: r.t, et: etStr(r.t, true), type: r.type, text: r.text })) }) });
  widget({ id: 'lmap', page: 'command', title: 'Live liquidity map', size: 'm', csv: () => ({ name: 'liquidity_pools', rows: (st()?.active_pools || []).map(p => ({ label: p.label, side: p.side, price: p.price, dist: +(p.price - st().price).toFixed(2), strength: p.strength })) }) });
  widget({ id: 'sessions', page: 'command', title: 'Session ranges · today', size: 'm' });
  widget({ id: 'regime', page: 'command', title: 'Regime & volatility', size: 'm' });
  widget({ id: 'lfeed', page: 'command', title: 'Live event feed', size: 'm', csv: () => ({ name: 'bot_log', rows: (L.log || []).map(r => ({ t: r.t, et: etStr(r.t, true), type: r.type, text: r.text })) }) });
  widget({ id: 'odds', page: 'command', title: 'Eval pass odds · Monte Carlo', size: 'm' });
  widget({ id: 'rs', page: 'command', title: 'NQ vs ES · relative strength', size: 'm' });
  // adopted existing cards follow, then the remaining new ones
  for (const [id, title, size, inner] of ADOPT) {
    const el = inner ? $('#' + inner)?.closest('.card, .grid') : page.querySelector(`[data-adopt="${id}"]`);
    if (!el) continue;
    if (id === 'kpis') { const wrap = document.createElement('div'); wrap.className = 'card w-bare'; el.replaceWith(wrap); wrap.appendChild(el); widget({ id, page: 'command', title, size, el: wrap }); continue; }
    el.classList.add('w-adopt');
    widget({ id, page: 'command', title, size, el });
  }
  widget({ id: 'uw', page: 'command', title: 'Underwater · drawdown from peak', size: 'l', csv: () => { let eq = 0, pk = 0; return { name: 'drawdown', rows: (S.res?.days || []).map(d => { eq += d.pnl || 0; pk = Math.max(pk, eq); return { date: d.date, pnl: d.pnl, cum_pnl: +eq.toFixed(2), dd: +(eq - pk).toFixed(2) }; }) }; } });
  widget({ id: 'conflb', page: 'command', title: 'Confluence leaderboard · previous engine (archive)', size: 'm', csv: () => confData ? { name: 'confluence', rows: confData.items } : null });
  widget({ id: 'meminsight', page: 'command', title: 'Memory insights', size: 'm' });
  buildGrid('command', $('#cmdGrid'), ['think', 'ready', 'timeline', 'prep', 'lmap', 'sessions', 'lfeed', 'odds', 'rs', 'regime', 'conflb', 'meminsight',
    'kpis', 'equity', 'account', 'uw', 'rules', 'state', 'ladder', 'clock', 'mtf', 'pd', 'brain', 'trades', 'whatif', 'edge']);

  onLive(() => { renderCockpit(); renderThink(); renderReady(); renderTimeline(); renderLmap(); renderSessions(); renderFeed(); });
  on((res) => { renderUW(res); renderRegime(); loadOdds(); });
  setInterval(() => { if (S.page === 'command' && !document.hidden) { renderClockCells(); const r = $('#rdyT'); if (r) { const t = LAUNCH_TS - Date.now() / 1000; r.textContent = t > 0 ? dur(t) : 'LIVE'; } } }, 1000);
  // slower dash-api sources (each falls back silently while the endpoint is planned)
  const slow = async () => {
    [modelApi, liqApi, sessApi, regApi, imApi, launchApi] = await Promise.all([
      dash('/api/dash/model'), dash('/api/dash/liquidity'), dash('/api/dash/sessions'),
      dash('/api/dash/regime', { ttl: 120000 }), dash('/api/dash/intermarket', { ttl: 120000 }), dash('/api/dash/launch')]);
    if (!imApi || !regApi) mkts = await getJSON('/api/markets', { ttl: 300000 });
    await pollEval();
    renderCockpit(); renderThink(); renderLmap(); renderSessions(); renderRegime(); renderRS(); renderReady();
  };
  slow(); setInterval(() => { if (!document.hidden) slow(); }, 20000);
  let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(renderTimeline, 200); });
  loadConf(); renderMemory();
  setInterval(() => { if (!document.hidden && S.page === 'command') renderMemory(); }, 120000);
  renderOdds();
}
export { notify };
