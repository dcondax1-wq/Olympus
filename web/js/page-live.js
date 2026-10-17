import { $, esc, fmtN, fmt$, fmtS$, cls, etStr, store, api, busy, toast, tradingDay, etParts } from './util.js';
import { S, effective } from './state.js';
import { TradeChart } from './chart.js';
import { feed, renderState } from './app.js';

let tc = null, timer = null, last = null;
// go-live state kept in page memory only (never localStorage): the typed phrase and the server's arm flag
const GL = { phrase: '', typed: '', armed: false, env: 'demo', adapters: [], present: false, check: null };

export function init() {
  const cfg = store.get('liveCfg', { sym: 'NQ', adapter: 'paper', poll_sec: 60, webhook_url: '', contract: '', data_source: 'tradovate' });
  if (cfg.adapter === 'tradovate') cfg.adapter = 'tradovate-demo';
  $('#liveCtl').innerHTML = `<div class="form-grid">
    <span>Instrument</span><select class="sel" id="lvSym"><option ${cfg.sym === 'NQ' ? 'selected' : ''}>NQ</option><option ${cfg.sym === 'ES' ? 'selected' : ''}>ES</option></select>
    <span>Execution</span><select class="sel" id="lvAdapter">
      <option value="paper" ${cfg.adapter === 'paper' ? 'selected' : ''}>Paper (simulated)</option>
      <option value="tradovate-demo" ${cfg.adapter === 'tradovate-demo' ? 'selected' : ''}>Tradovate DEMO</option>
      <option value="tradovate-live" ${cfg.adapter === 'tradovate-live' ? 'selected' : ''}>Tradovate LIVE (MFFU)</option>
      <option value="traderspost" ${cfg.adapter === 'traderspost' ? 'selected' : ''}>TradersPost webhook</option></select>
    <span>Bar source</span><select class="sel" id="lvData">
      <option value="tradovate" ${cfg.data_source !== 'yahoo' ? 'selected' : ''}>Tradovate market data (real-time)</option>
      <option value="yahoo" ${cfg.data_source === 'yahoo' ? 'selected' : ''}>Yahoo (~10 min delayed, paper only)</option></select>
    <span>Webhook URL</span><input class="inp" id="lvHook" placeholder="TradersPost webhook (kept in server memory)" value="">
    <span>Contract</span><input class="inp" id="lvContract" value="${esc(cfg.contract || '')}" placeholder="auto front month (e.g. MNQZ6)" title="Leave empty for the auto front month">
    <span>Poll every (s)</span><input class="inp" id="lvPoll" type="number" value="${cfg.poll_sec}" min="15"></div>
    <div class="row gap" style="margin-top:12px"><button class="btn primary" id="lvStart">▶ Start bot</button><button class="btn ghost" id="lvStop">■ Stop</button>
      <button class="btn ghost" id="lvPollNow">⟳ Poll now</button></div>
    <div class="note">The bot uses the <b>current Backtest Lab parameters</b> and re-runs the same engine on every closed ${S.tf} bar. Live execution needs the Tradovate bar source; Yahoo is for paper only. Tradovate credentials live in environment variables on this machine (README: Going live).</div>`;
  const save = () => store.set('liveCfg', { sym: $('#lvSym').value, adapter: $('#lvAdapter').value, poll_sec: +$('#lvPoll').value, contract: $('#lvContract').value, data_source: $('#lvData').value });
  $('#liveCtl').onchange = () => { save(); renderArm(); };
  $('#lvStart').onclick = startBot;
  $('#lvStop').onclick = async () => { await api('/api/live/stop', {}); toast('Bot stopped'); poll(); };
  $('#lvPollNow').onclick = async () => {
    busy(true);
    try { last = await api('/api/live/poll', {}); render(last); } catch (e) { toast('Poll failed: ' + e.message); }
    busy(false);
  };
  // ---- go-live panel
  $('#glRun').onclick = () => runChecklist(false);
  $('#glRoundtrip').onclick = async () => {
    if (GL.env !== 'demo') { toast('Round-trip test runs on DEMO only'); return; }
    if (!confirm('Place a 1-lot MNQ limit order far below the market on the DEMO account and cancel it?')) return;
    runChecklist(true);
  };
  renderArm();
  loadAdapters();
}

export function show() {
  if (!tc) tc = new TradeChart($('#liveChart'), { minFvg: S.meta?.instruments?.NQ?.min_fvg ?? 3 });
  poll();
  loadAdapters();
  if (!GL.check) runChecklist(false);
  clearInterval(timer);
  timer = setInterval(() => { if (S.page === 'live') poll(); else clearInterval(timer); }, 5000);
}
export function retheme() { tc?.applyTheme(); }

async function poll() {
  try { last = await api('/api/live/state'); render(last); } catch (e) { /* server down */ }
}

async function loadAdapters() {
  try {
    const r = await api('/api/live/adapters');
    GL.adapters = r.adapters; GL.env = r.env; GL.phrase = r.phrase; GL.armed = r.armed;
    for (const a of r.adapters) {
      const o = $(`#lvAdapter option[value="${a.name}"]`);
      if (o) { o.disabled = !a.configured; o.textContent = a.label + (a.configured ? '' : ' (not configured)'); }
    }
    $('#glEnv').textContent = `TRADOVATE_ENV=${r.env}` + (r.account ? ` · ${r.account}` : '');
    $('#glEnv').className = 'pill ' + (r.env === 'live' ? 'bad' : 'good');
    renderArm();
  } catch (e) { /* server down */ }
}

function startConfig(adapter) {
  const sym = $('#lvSym').value, contract = $('#lvContract').value.trim();
  return { sym, tf: S.tf, adapter, poll_sec: Math.max(15, +$('#lvPoll').value), params: S.params, data_source: $('#lvData').value,
    webhook_url: $('#lvHook').value || undefined, contract_map: contract ? { [sym]: contract } : {}, present: GL.present };
}

async function startBot() {
  const adapter = $('#lvAdapter').value;
  const body = startConfig(adapter);
  if (adapter !== 'paper') {
    if (!GL.present) { toast('Tick "I will be present and monitoring" first (MFFU requires oversight)'); return; }
    body.armed = true;
    if (adapter === 'tradovate-live') {
      if (!GL.armed || GL.typed !== GL.phrase) { toast('Arm LIVE first: type the phrase and press ARM'); return; }
      if (GL.check && !GL.check.ok && !confirm('The go-live checklist has failing steps. Start LIVE anyway?')) return;
      body.confirm = GL.typed;
      if (!confirm('START LIVE TRADING on the MFFU account? Real orders will be sent. Stay at the screen.')) return;
    } else if (!confirm(`Start ${adapter.toUpperCase()}? Orders go to your ${adapter === 'tradovate-demo' ? 'Tradovate DEMO account' : 'webhook'}.`)) return;
    if (body.data_source === 'yahoo' && !confirm('Yahoo bars are ~10 minutes delayed. Really run a broker adapter on delayed data?')) return;
  }
  try { const r = await api('/api/live/start', body); r.ok ? toast('Bot started') : toast(r.error); } catch (e) { toast(e.message); }
  poll();
}

async function runChecklist(roundtrip) {
  const el = $('#golive');
  busy(true);
  el.innerHTML = '<div class="empty">Running checks…</div>';
  try {
    const adapter = $('#lvAdapter').value;
    const body = { ...startConfig(adapter), roundtrip, armed: GL.armed, confirm: GL.typed };
    GL.check = await api('/api/live/golive', body);
  } catch (e) { GL.check = { ok: false, steps: [{ step: 'Checklist', ok: false, detail: e.message, fix: 'Is the server running?' }] }; }
  busy(false);
  renderChecklist();
}

function renderChecklist() {
  const c = GL.check; if (!c) return;
  $('#golive').innerHTML = `<table class="tbl">${c.steps.map(s => `<tr>
      <td style="width:22px">${s.ok ? `<span class="${s.warn ? '' : 'up'}" style="${s.warn ? 'color:var(--warn)' : ''}">●</span>` : '<span class="dn">●</span>'}</td>
      <td><b>${esc(s.step)}</b><div class="small muted">${esc(s.detail)}</div>${!s.ok || s.warn ? `<div class="small" style="color:var(--warn)">→ ${esc(s.fix)}</div>` : ''}</td>
      <td class="mono small" style="text-align:right">${s.ok ? (s.warn ? 'WARN' : 'OK') : 'FAIL'}</td></tr>`).join('')}</table>
    <div class="note">${c.ok ? '<span class="up">All checks passed.</span>' : '<span class="dn">Fix the red rows before arming.</span>'}${c.t ? ` Checked ${etStr(c.t)} ET · ${esc(c.symbols?.micro || '')} / ${esc(c.symbols?.mini || '')}` : ''}</div>`;
}

function renderArm() {
  const el = $('#armPanel'); if (!el) return;
  const adapter = $('#lvAdapter')?.value || 'paper';
  const pill = $('#armPill');
  pill.textContent = GL.armed ? 'LIVE ARMED' : adapter === 'paper' ? 'paper' : adapter === 'tradovate-demo' ? 'demo' : 'disarmed';
  pill.className = 'pill ' + (GL.armed ? 'bad' : adapter === 'paper' ? 'good' : '');
  const liveReady = GL.env === 'live' && GL.adapters.find(a => a.name === 'tradovate-live')?.configured;
  el.innerHTML = `
    <label class="row gap small" style="margin-bottom:10px"><input type="checkbox" id="glPresent" ${GL.present ? 'checked' : ''}> <span>I will be <b>present and monitoring</b> this session (MFFU: automation only with active oversight)</span></label>
    <div class="small muted" style="margin-bottom:6px">Arm LIVE: type exactly <span class="mono">${esc(GL.phrase || 'I ACCEPT LIVE RISK')}</span></div>
    <div class="row gap" style="margin-bottom:10px"><input class="inp" id="glPhrase" placeholder="type the phrase" value="${esc(GL.typed)}" autocomplete="off" ${GL.armed ? 'disabled' : ''} style="flex:1">
      ${GL.armed ? '<button class="btn ghost" id="glDisarm">Disarm</button>' : `<button class="btn danger" id="glArm" disabled style="font-weight:700;padding:10px 18px" title="${liveReady ? '' : 'TRADOVATE_ENV must be live and credentials set'}">ARM LIVE</button>`}</div>
    ${GL.armed ? `<div class="banner warn" style="margin-bottom:10px">LIVE ARMED${last?.running && last?.cfg?.adapter === 'tradovate-live' ? ' · bot running on the LIVE account' : ' · press Start bot with Tradovate LIVE selected'}</div>` : ''}
    <div class="small muted" style="margin:6px 0">KILL SWITCH: cancels every working order, liquidates every position, stops the bot. Hold for 1.5 s.</div>
    <button class="btn danger" id="lvKill" style="width:100%;padding:16px;font-size:15px;font-weight:800;letter-spacing:.06em;position:relative;overflow:hidden;user-select:none;touch-action:none">
      <span id="lvKillFill" style="position:absolute;left:0;top:0;bottom:0;width:0;background:rgba(0,0,0,.35)"></span><span style="position:relative">HOLD TO KILL</span></button>`;
  $('#glPresent').onchange = (e) => { GL.present = e.target.checked; };
  const inp = $('#glPhrase'), arm = $('#glArm');
  if (inp) inp.oninput = () => { GL.typed = inp.value; if (arm) arm.disabled = !(liveReady && GL.typed === GL.phrase); };
  if (arm) {
    arm.disabled = !(liveReady && GL.typed === GL.phrase);
    arm.onclick = async () => {
      if (!GL.present) { toast('Acknowledge "present and monitoring" first'); return; }
      if (!confirm('ARM LIVE TRADING? After this, starting the bot with "Tradovate LIVE" sends real orders to the MFFU account.')) return;
      try { const r = await api('/api/live/arm', { phrase: GL.typed }); GL.armed = !!r.armed; toast('LIVE ARMED'); } catch (e) { toast(e.message); }
      renderArm(); poll();
    };
  }
  const dis = $('#glDisarm');
  if (dis) dis.onclick = async () => { await api('/api/live/arm', { disarm: true }); GL.armed = false; GL.typed = ''; toast('Disarmed'); renderArm(); poll(); };
  holdToKill($('#lvKill'), $('#lvKillFill'));
}

function holdToKill(btn, fill) {
  let t0 = 0, raf = 0;
  const HOLD = 1500;
  const stop = () => { cancelAnimationFrame(raf); t0 = 0; fill.style.width = '0'; };
  const step = () => {
    if (!t0) return;
    const p = Math.min(1, (performance.now() - t0) / HOLD);
    fill.style.width = (p * 100) + '%';
    if (p >= 1) { stop(); fire(); return; }
    raf = requestAnimationFrame(step);
  };
  const fire = async () => {
    try { await api('/api/live/kill', {}); toast('KILL SWITCH fired: flattened and stopped'); } catch (e) { toast('Kill failed: ' + e.message); }
    poll();
  };
  btn.onpointerdown = (e) => { e.preventDefault(); btn.setPointerCapture?.(e.pointerId); t0 = performance.now(); raf = requestAnimationFrame(step); };
  btn.onpointerup = btn.onpointercancel = btn.onpointerleave = stop;
  btn.oncontextmenu = (e) => e.preventDefault();
}

function render(snap) {
  const run = $('#liveRun');
  const liveArmed = GL.armed && (!snap.running || snap.cfg.adapter === 'tradovate-live');
  run.textContent = liveArmed ? (snap.running ? '● LIVE ARMED · running' : 'LIVE ARMED') : snap.running ? `● running · ${snap.cfg.adapter}` : 'stopped';
  run.className = 'pill ' + (liveArmed ? 'bad' : snap.running ? 'good' : '');
  $('#livePoll').textContent = snap.last_poll ? 'last poll ' + etStr(snap.last_poll) + ' ET' : 'not polled yet';
  renderState($('#liveState'), snap.state, null);
  const st = snap.state;
  const p = effective();
  if (st) {
    const pos = st.position;
    const cushion = st.balance - st.mll;
    const guards = [
      ['Daily loss stop', `${fmtS$(st.day_pnl)} / -${fmt$(p.daily_max_loss)}`, st.day_pnl > -p.daily_max_loss],
      ['Trades today', `${st.day_trades} / ${st.strategy?.params?.max_trades_day ?? p.max_trades_day}`,
        st.day_trades < (st.strategy?.params?.max_trades_day ?? p.max_trades_day)],
      ['MLL cushion (sim)', fmt$(cushion), cushion > p.risk_usd * 2],
      ['Session', st.model_state, !['DONE FOR DAY'].includes(st.model_state)],
    ];
    const ef = st.equity_filter;
    if (ef?.enabled) guards.push(['Cold-streak filter', `${ef.on ? 'TRADING' : 'SITTING OUT'} · last ${ef.n} ${ef.sum_r > 0 ? '+' : ''}${fmtN(ef.sum_r, 2)}R`, ef.on]);
    if (st.strategy?.label) guards.unshift(['Strategy', String(st.strategy.label).split(' (')[0], true]);
    const h = snap.health;
    if (h) {
      const age = h.data_age_s == null ? '—' : h.data_age_s >= 120 ? `${Math.round(h.data_age_s / 60)} min` : `${Math.round(h.data_age_s)} s`;
      guards.push(['Data feed', `${h.data_source || snap.cfg?.data_source || 'yahoo'} · age ${age}${h.fallback ? ' · FALLBACK' : ''}`, !h.stale && !h.fallback]);
      guards.push(['Feed integrity', `${h.revisions || 0} revised bars${h.desync ? ' · DESYNC' : ''}${h.entries_blocked ? ' · entries blocked' : ''}`, !h.desync && !h.entries_blocked]);
      if (h.last_error) guards.push(['Last error', String(h.last_error).slice(0, 60), false]);
    }
    $('#livePos').innerHTML = (pos ? `<div class="card" style="box-shadow:none;background:var(--surface-2);margin-bottom:10px">
        <div class="card-h"><span class="dir ${pos.dir === 1 ? 'L' : 'S'}">${pos.dir === 1 ? 'LONG' : 'SHORT'} ${esc(pos.qty_label)}</span><b class="mono ${cls((st.price - pos.entry) * pos.dir)}">${fmtN((st.price - pos.entry) * pos.dir / pos.risk_pts, 2)}R</b></div>
        <div class="state-grid"><div class="st"><div class="k">Entry</div><div class="v">${fmtN(pos.entry)}</div></div><div class="st"><div class="k">Stop</div><div class="v dn">${fmtN(pos.stop)}</div></div>
        <div class="st"><div class="k">Target</div><div class="v up">${fmtN(pos.target)}</div></div><div class="st"><div class="k">DOL</div><div class="v small">${esc(pos.target_label)}</div></div></div>
        ${pos.checklist ? `<div class="grade-row"><span class="grade g-${esc(pos.grade).replace('+', 'p')}">${esc(pos.grade)}</span><span class="small muted">${pos.grade_points} pts · size ×${pos.grade_mult}</span></div>
          <div class="checklist">${pos.checklist.filter(c => c.weight).map(c => `<div class="ck ${c.state > 0 ? 'yes' : c.state < 0 ? 'no' : 'na'}"><span class="ic">${c.state > 0 ? '✓' : c.state < 0 ? '✗' : '–'}</span><span>${esc(c.label)}</span><span class="w">${c.weight}</span></div>`).join('')}</div>` : ''}</div>`
      : '<div class="note" style="margin-bottom:10px">Flat, no open position.</div>') +
      `<table class="tbl">${guards.map(([k, v, ok]) => `<tr><td>${ok ? '<span class="up">●</span>' : '<span class="dn">●</span>'} ${k}</td><td class="mono" style="text-align:right">${esc(v)}</td></tr>`).join('')}</table>`;
    // chart
    if (snap.bars?.length) {
      const bars = snap.bars.map(b => { const pp = etParts(b.time); return { t: b.time, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume, d: tradingDay(b.time), mod: pp.h * 60 + pp.mi }; });
      const first = !tc.bars.length;
      tc.setBars(bars, 300);
      const trades = pos ? [{ ...pos, exit_t: 4e9, pnl: 0, pnl_r: 0, exit_reason: 'OPEN', stop0: pos.stop0 ?? pos.stop }] : [];
      const profiles = st.profile ? { [bars.at(-1).d]: st.profile } : {};
      tc.setAnnotations({ pools: st.active_pools, trades, profiles, ifvgs: [] });
      if (first) tc.scrollToEnd(150);
    }
  } else {
    $('#livePos').innerHTML = '<div class="empty">Start the bot or press "Poll now" to evaluate the latest market data.</div>';
  }
  feed($('#liveLog'), (snap.log || []).map(l => ({ ...l, t: l.bar_t || l.t })));
  $('#ledger').innerHTML = '<tr><th>Time</th><th>Side</th><th>Qty</th><th>Stop</th><th>Target</th><th>Adapter result</th></tr>' +
    (snap.ledger || []).slice().reverse().map(o => `<tr><td class="mono">${etStr(o.t, true)}</td><td>${esc(o.side.toUpperCase())}</td><td>${o.qty ?? ''}</td><td>${o.stop ? fmtN(o.stop) : ''}</td><td>${o.target ? fmtN(o.target) : ''}</td><td class="small">${esc(JSON.stringify(o.result).slice(0, 90))}</td></tr>`).join('');
}
