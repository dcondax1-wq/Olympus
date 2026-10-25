// Bot Control center (PC dashboard): one START button with an account picker and an automatic preflight checklist, the live
// status strip, the safety switches, and the live panels around it.
//   Today page   (#bcToday on #page-command)   the strip + START / STOP + account picker + preflight summary + eval meter
//   Bot Control  (#page-botctl)                everything: full checklist, safety (HOLD TO KILL, auto-update, auto-resume,
//                restart), eval meter + room gauge, open trade chart, rule checklist + why no trade, today's LIT plan,
//                radar + session clock, news, equity with target / floor, P&L calendar, replay, backtest vs live, execution
//                quality, extra accounts, strategy switches (READ-ONLY), alerts, health timeline, version + changelog
// API: GET /api/next/botctl/status|insights|plan|switches, /api/next/pc/account, /api/next/pc/execution, /api/next/pc/trade/<t>;
//      POST /api/next/botctl/start|stop|autoupdate|autoresume|restart|selftest, POST /api/live/kill (HOLD TO KILL).
// The confirm phrase: typed into a dialog for each real-account start (and to turn auto-resume on), sent once in the POST
// body, the field cleared and the dialog removed at once. Never kept in a variable, never in localStorage, never shown.
import { $, $$, api, esc, fmt$, fmtS$, fmtN, fmtR, cls, etStr, etParts, toast, store } from '../util.js';
import { icon } from './icons.js';
import { calGrid, posTrade, execBody, extraAccountsCard } from './pcpages.js';

const TCV = '../tradechart.js?v=b1526d92';
let TCP = null;
const loadTC = () => TCP || (TCP = import(TCV).catch((e) => { TCP = null; throw e; }));

const B = { st: null, stAt: 0, ins: null, insAt: 0, plan: null, planAt: 0, sw: null, ac: null, acAt: 0, ex: null, exAt: 0, busy: false };
let ACCT = store.get('bc.account', '');                 // the picked account NAME only (never anything secret)

// ------------------------------------------------------------------ helpers
const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const ago = (s) => (!ok(s) ? '—' : s < 90 ? `${Math.max(0, Math.round(s))} s` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${(s / 3600).toFixed(1)} h` : `${Math.round(s / 86400)} d`);
const inS = (s) => { if (!ok(s)) return '—'; s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return h ? `${h}h ${String(m).padStart(2, '0')}m` : m ? `${m}m ${String(x).padStart(2, '0')}s` : `${x}s`; };
const px = (v) => (ok(v) ? (+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
const isActive = (id) => document.getElementById('page-' + id)?.classList.contains('active');
const card = (title, body, tools = '', extra = '') => `<section class="card nx-glass bc-card ${extra}"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</section>`;
const empty = (t, s = '') => `<div class="pc-empty"><b>${t}</b>${s ? `<span>${s}</span>` : ''}</div>`;
const chip = (t, k = '') => `<span class="nx-chip ${k}">${t}</span>`;
const dot = (okv) => `<span class="bc-dot ${okv === true ? 'g' : okv === false ? 'r' : 'a'}"></span>`;
const meter = (f, k = '') => `<div class="pc-meter ${k}"><i style="width:${Math.max(0, Math.min(100, f * 100)).toFixed(1)}%"></i></div>`;
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const fDate = (d) => { if (!d) return '—'; const [, m, dd] = String(d).slice(0, 10).split('-').map(Number); return `${MON[m - 1]} ${dd}`; };

// ------------------------------------------------------------------ data
async function getStatus(force) {
  if (!force && B.st && Date.now() - B.stAt < 4000) return B.st;
  try { B.st = await api('/api/next/botctl/status' + (ACCT ? '?account=' + encodeURIComponent(ACCT) : '')); B.stAt = Date.now(); } catch (e) { B.st = B.st || { error: e.message }; }
  if (!ACCT && B.st?.preflight?.account) ACCT = B.st.preflight.account;
  return B.st;
}
async function getInsights(force) {
  if (!force && B.ins && Date.now() - B.insAt < 20000) return B.ins;
  try { B.ins = await api('/api/next/botctl/insights'); B.insAt = Date.now(); } catch (e) { B.ins = B.ins || { error: e.message }; }
  return B.ins;
}
async function getPlan(force) {
  if (!force && B.plan && Date.now() - B.planAt < 60000) return B.plan;
  try { B.plan = await api('/api/next/botctl/plan'); B.planAt = Date.now(); } catch (e) { B.plan = B.plan || { error: e.message }; }
  return B.plan;
}
async function getAccount(force) {
  if (!force && B.ac && Date.now() - B.acAt < 10000) return B.ac;
  try { B.ac = await api('/api/next/pc/account'); B.acAt = Date.now(); } catch (e) { B.ac = B.ac || { error: e.message }; }
  return B.ac;
}
async function getExec() {
  if (B.ex && Date.now() - B.exAt < 120000) return B.ex;
  try { B.ex = await api('/api/next/pc/execution'); B.exAt = Date.now(); } catch (e) { B.ex = B.ex || { error: e.message }; }
  return B.ex;
}
async function getSwitches() {
  if (B.sw) return B.sw;
  try { B.sw = await api('/api/next/botctl/switches'); } catch (e) { B.sw = { error: e.message }; }
  return B.sw;
}

// ------------------------------------------------------------------ status strip
function stripHTML(s) {
  const x = s.strip || {}, f = x.feed || {}, p = x.position, w = x.window || {}, hb = x.heartbeat || {};
  const live = x.is_live, badge = x.label || (x.adapter === 'paper' ? 'PAPER' : 'SIM');
  const fAge = f.age_1m_s ?? f.age_5m_s;
  const fk = f.blocked || f.stale ? 'bad' : (fAge != null && fAge > 240 && f.market_open) ? 'warn' : '';
  const sig = x.last_signal;
  return `<div class="bc-strip">
    <div class="bc-s bc-run ${x.running ? (x.kill ? 'bad' : 'good') : 'off'}"><span class="bc-pulse"></span><div><span>Bot</span><b>${x.kill ? 'KILLED' : x.running ? 'RUNNING' : 'STOPPED'}</b><em>${x.running && ok(x.uptime_s) ? 'up ' + inS(x.uptime_s) : esc(x.stage_text || '')}</em></div></div>
    <div class="bc-s ${x.running && x.enabled === false ? 'bad' : ''}"><div><span>Account</span>${x.running
      ? `<b>${esc(x.account || '—')} <i class="bc-badge ${live ? 'live' : badge === 'SIM' ? 'sim' : 'paper'}">${esc(live ? 'LIVE' : badge)}</i></b><em>${x.enabled === false ? 'orders DISABLED' : 'orders enabled'}</em>`
      : `<b>${esc(s.preflight?.account || '—')} <i class="bc-badge ${s.preflight?.sim === false ? 'live' : 'sim'}">${s.preflight?.sim === false ? 'LIVE' : 'SIM'}</i></b><em>picked · not started</em>`}</div></div>
    <div class="bc-s"><div><span>Position</span><b class="${p ? (p.side === 'LONG' ? 'up' : 'dn') : ''}">${p ? `${esc(p.side)} ${p.qty ?? ''} MNQ` : 'Flat'}</b><em>${p ? `${px(p.entry)} · <span class="${cls(p.unrealized_usd)}">${fmtS$(p.unrealized_usd)}</span>` : 'no open trade'}</em></div></div>
    <div class="bc-s"><div><span>Today P&amp;L</span><b class="${cls(x.day_pnl)}">${fmtS$(x.day_pnl)}</b><em>${x.trades_today ?? 0} entr${x.trades_today === 1 ? 'y' : 'ies'} · 1 a day max</em></div></div>
    <div class="bc-s"><div><span>Last signal</span><b>${sig ? `${esc(sig.side)} ${esc(sig.level || '')}` : 'none today'}</b><em>${sig?.t ? etStr(sig.t) + ' ET' : ''}${sig?.rr ? ` · ${fmtN(sig.rr, 1)}R` : ''}</em></div></div>
    <div class="bc-s ${w.open ? 'good' : ''}"><div><span>Entry window</span><b>${w.open ? 'OPEN' : w.in_s != null ? 'in ' + inS(w.in_s - (Date.now() - B.stAt) / 1000) : '—'}</b><em>${esc(w.text || '')}</em></div></div>
    <div class="bc-s ${fk}"><div><span>Feed</span><b>${fAge != null ? ago(fAge) + ' old' : 'no bars'}</b><em>${f.blocked ? 'NEW ENTRIES BLOCKED' : f.market_open === false ? 'market closed' : esc(f.source || 'ninjatrader')}</em></div></div>
    <div class="bc-s ${hb.enabled && hb.ok === false ? 'warn' : ''}"><div><span>Heartbeat</span><b>${hb.at ? ago(hb.age_s) + ' ago' : hb.enabled ? 'not yet' : 'off'}</b><em>${hb.at ? (hb.ok ? 'pushed to the cloud' : 'push failed') : hb.enabled ? 'first push soon' : 'LE_HEARTBEAT=1 on the PC'}</em></div></div>
  </div>`;
}

// ------------------------------------------------------------------ start panel
function pickerHTML(s) {
  const rows = s.accounts || [], cur = s.preflight?.account || ACCT;
  return `<div class="bc-pick" role="radiogroup" aria-label="Account">${rows.map((a) => `<button type="button" role="radio" aria-checked="${a.name === cur}" class="bc-acct ${a.name === cur ? 'on' : ''} ${a.sim ? 'sim' : 'live'}" data-acct="${esc(a.name)}">
      <i class="bc-badge ${a.sim ? 'sim' : 'live'}">${a.sim ? 'SIM' : 'LIVE'}</i><b>${esc(a.name)}</b><em>${esc(a.running ? 'running now' : a.extra ? 'extra account' + (a.extra_name ? ' · ' + a.extra_name : '') : a.sources.includes('NinjaTrader') ? 'NinjaTrader reports it' : a.sim ? 'practice money' : a.sources.join(', '))}</em></button>`).join('')}
    <button type="button" class="bc-acct add" data-acct-add><i class="bc-badge">+</i><b>Other…</b><em>type the Name</em></button></div>`;
}
function checklistHTML(pf, compact = false) {
  const rows = (pf.rows || []).filter((r) => !compact || r.ok !== true || ['connection', 'feed5m', 'feed1m'].includes(r.id));
  return `<div class="bc-checks ${compact ? 'compact' : ''}">${rows.map((r) => `<div class="bc-ck ${r.ok === true ? 'g' : r.ok === false ? 'r' : 'a'}">${dot(r.ok)}
      <div><b>${esc(r.label)}</b><span>${esc(r.detail || '')}</span>${r.ok === false && r.fix ? `<em>${icon('right')}${esc(r.fix)}</em>` : r.ok == null && r.fix ? `<em class="a">${esc(r.fix)}</em>` : ''}</div></div>`).join('')}</div>`;
}
function startHTML(s, compact = false) {
  const pf = s.preflight || {}, x = s.strip || {};
  const running = x.running;
  const live = !pf.sim;
  const can = !running && pf.ok;
  const head = `<div class="bc-sum"><span class="g">${pf.green || 0} green</span><span class="a">${pf.amber || 0} amber</span><span class="r">${pf.red || 0} red</span>
    <button type="button" class="btn ghost sm" data-bc="selftest" ${s.selftest?.running ? 'disabled' : ''}>${icon('refresh')}<span>${s.selftest?.running ? 'Self-test…' : 'Run self-test'}</span></button></div>`;
  const btn = running
    ? `<button type="button" class="bc-go stop" data-bc="stop">${icon('stop')}<span><b>STOP</b><em>stops the bot · stays stopped</em></span></button>`
    : `<button type="button" class="bc-go ${live ? 'live' : ''}" data-bc="start" ${can ? '' : 'disabled'}>${icon('play')}<span><b>START${live ? ' LIVE' : ''}</b><em>${!pf.ok ? `fix the ${pf.red} red row${pf.red === 1 ? '' : 's'} first` : live ? 'real account: you type the confirm phrase' : `on ${esc(pf.account)} · one click`}</em></span></button>`;
  return `<div class="bc-start">${pickerHTML(s)}<div class="bc-go-row">${btn}${head}</div>${checklistHTML(pf, compact)}
    ${live && !running ? `<p class="bc-warn">${icon('warn')}<span><b>${esc(pf.account)} is a real account.</b> MFFU: live trading only with you at the PC. Every live lock stays: armed + the exact phrase + NINJATRADER_LIVE on this server, then NinjaTrader's own gate.</span></p>` : ''}</div>`;
}

// ------------------------------------------------------------------ phrase dialog (memory of the DOM only, cleared at once)
function askPhrase({ title, account, present = true, cta = 'Start' }) {
  return new Promise((resolve) => {
    const m = document.createElement('div');
    m.className = 'bc-modal';
    m.innerHTML = `<form class="bc-dlg" autocomplete="off" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <div class="bc-dlg-h">${icon('warn')}<b>${esc(title)}</b></div>
      <p>Account <b>${esc(account)}</b> is a <b>REAL</b> account. Type the live confirm phrase (the one in docs/GO_LIVE_TONIGHT.md). It is sent once and never saved or shown.</p>
      <input type="password" name="bcp" autocomplete="off" autocapitalize="off" spellcheck="false" data-lpignore="true" placeholder="confirm phrase" class="inp" aria-label="confirm phrase">
      ${present ? '<label class="bc-pres"><input type="checkbox" name="bcpres"> <span>I am at the PC and watching this session</span></label>' : ''}
      <div class="bc-dlg-a"><button type="button" class="btn ghost" data-x>Cancel</button><button type="submit" class="btn danger">${esc(cta)}</button></div></form>`;
    document.body.appendChild(m);
    const f = m.querySelector('form'), inp = f.querySelector('input[name=bcp]');
    const done = (v) => { inp.value = ''; m.remove(); resolve(v); };
    f.onsubmit = (e) => { e.preventDefault(); const v = { phrase: inp.value, present: !!f.querySelector('input[name=bcpres]')?.checked }; done(v); };
    f.querySelector('[data-x]').onclick = () => done(null);
    m.onclick = (e) => { if (e.target === m) done(null); };
    m.onkeydown = (e) => { if (e.key === 'Escape') done(null); };
    setTimeout(() => inp.focus(), 30);
  });
}
function askName() {
  return new Promise((resolve) => {
    const m = document.createElement('div');
    m.className = 'bc-modal';
    m.innerHTML = `<form class="bc-dlg"><div class="bc-dlg-h">${icon('wallet')}<b>Account Name</b></div><p>Exactly as NinjaTrader's Accounts tab shows it (Sim101, or your eval's Name).</p>
      <input name="n" class="inp" autocomplete="off" spellcheck="false" placeholder="e.g. Sim101"><div class="bc-dlg-a"><button type="button" class="btn ghost" data-x>Cancel</button><button type="submit" class="btn primary">Use it</button></div></form>`;
    document.body.appendChild(m);
    const f = m.querySelector('form');
    f.onsubmit = (e) => { e.preventDefault(); const v = f.n.value.trim(); m.remove(); resolve(v || null); };
    f.querySelector('[data-x]').onclick = () => { m.remove(); resolve(null); };
    setTimeout(() => f.n.focus(), 30);
  });
}

// ------------------------------------------------------------------ actions
async function act(kind, el) {
  if (B.busy) return;
  const s = B.st || {};
  try {
    B.busy = true; el?.classList.add('busy');
    if (kind === 'start') {
      const pf = s.preflight || {};
      let body = { account: pf.account };
      if (!pf.sim) {
        const a = await askPhrase({ title: 'Start on a REAL account', account: pf.account, cta: 'START LIVE' });
        if (!a) return;
        body = { account: pf.account, confirm: a.phrase, present: a.present };
        a.phrase = '';
      }
      let r;
      try { r = await fetch('/api/next/botctl/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then((x) => x.json()); }
      finally { body = null; }
      toast(r.ok ? `Bot started on ${r.account}${r.warning ? ' · ' + r.warning : ''}` : `Not started: ${r.error}`, r.ok ? 3500 : 7000);
    } else if (kind === 'stop') {
      const r = await api('/api/next/botctl/stop', {}); toast(r.ok ? 'Bot stopped (stays stopped)' : 'Stop failed: ' + r.error);
    } else if (kind === 'selftest') {
      await api('/api/next/botctl/selftest', {}); toast('Self-test running (about 2 s)'); setTimeout(() => refresh(true), 2600);
    } else if (kind === 'au-on' || kind === 'au-off') {
      const r = await api('/api/next/botctl/autoupdate', { on: kind === 'au-on' }); toast(`Auto-update ${r.on ? 'ON: daily in the 17:00 ET halt, only when flat' : 'OFF'}`);
    } else if (kind === 'ar-off') {
      const r = await api('/api/next/botctl/autoresume', { on: false }); toast(r.was_on ? 'Auto-resume turned OFF' : 'Auto-resume was already off');
    } else if (kind === 'ar-on') {
      const acct = (s.strip?.is_live && s.strip?.account) || (!s.preflight?.sim && s.preflight?.account);
      if (!acct) { toast('Pick your real eval account first (Sim accounts resume by themselves)', 5000); return; }
      const a = await askPhrase({ title: 'Turn auto-resume ON', account: acct, present: false, cta: 'Turn ON' });
      if (!a) return;
      let body = { on: true, account: acct, confirm: a.phrase };
      a.phrase = '';
      let r;
      try { r = await fetch('/api/next/botctl/autoresume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then((x) => x.json()); }
      finally { body = null; }
      toast(r.ok ? `Auto-resume ON for ${r.account}${r.start && !r.start.ok ? ' · start: ' + r.start.error : ''}` : r.error, 7000);
    } else if (kind === 'restart') {
      if (!window.confirm('Restart the server now? It comes back in about 10 s.')) return;
      const r = await fetch('/api/next/botctl/restart', { method: 'POST' }).then((x) => x.json());
      toast(r.ok ? r.note : 'Not restarted: ' + r.error, 7000);
    }
  } catch (e) { toast(e.message, 6000); }
  finally { B.busy = false; el?.classList.remove('busy'); refresh(true); }
}
function holdToKill(btn) {
  const fill = btn.querySelector('.bc-kill-fill'); let t0 = 0, raf = 0; const HOLD = 1500;
  const stop = () => { cancelAnimationFrame(raf); t0 = 0; fill.style.width = '0'; };
  const step = () => { if (!t0) return; const p = Math.min(1, (performance.now() - t0) / HOLD); fill.style.width = (p * 100) + '%'; if (p >= 1) { stop(); fire(); return; } raf = requestAnimationFrame(step); };
  const fire = async () => { try { await api('/api/live/kill', {}); toast('KILL SWITCH fired: flattened, stopped, auto-resume off', 5000); } catch (e) { toast('Kill failed: ' + e.message, 6000); } refresh(true); };
  btn.onpointerdown = (e) => { e.preventDefault(); btn.setPointerCapture?.(e.pointerId); t0 = performance.now(); raf = requestAnimationFrame(step); };
  btn.onpointerup = btn.onpointercancel = btn.onpointerleave = stop;
  btn.oncontextmenu = (e) => e.preventDefault();
}
function bind(root) {
  $$('[data-bc]', root).forEach((b) => { b.onclick = () => act(b.dataset.bc, b); });
  $$('[data-acct]', root).forEach((b) => { b.onclick = () => { ACCT = b.dataset.acct; store.set('bc.account', ACCT); refresh(true); }; });
  $$('[data-acct-add]', root).forEach((b) => { b.onclick = async () => { const n = await askName(); if (n) { ACCT = n; store.set('bc.account', ACCT); refresh(true); } }; });
  $$('.bc-kill', root).forEach(holdToKill);
}

// ------------------------------------------------------------------ safety
function safetyHTML(s) {
  const au = s.auto?.update || {}, ar = s.auto?.resume || {}, rs = s.restart || {};
  return `<div class="bc-safe">
    <button type="button" class="bc-kill"><span class="bc-kill-fill"></span><span class="bc-kill-t">${icon('power')}<b>HOLD TO KILL</b><em>flatten everything · stop · auto-resume off</em></span></button>
    <div class="bc-sw"><div><b>Auto-update</b><span>${au.on ? 'ON · daily 17:02-17:50 ET when flat, fast-forward of main only' : 'OFF'}${au.result ? ` · last: ${esc(au.result)}` : ''}</span></div>
      <button type="button" class="bc-tog ${au.on ? 'on' : ''}" data-bc="${au.on ? 'au-off' : 'au-on'}" aria-pressed="${!!au.on}" aria-label="Auto-update"><i></i></button></div>
    <div class="bc-sw"><div><b>Auto-resume (real account)</b><span>${ar.on ? `ON for ${esc(ar.account)} · comes back after a crash / update / reboot` : `OFF${ar.off_reason ? ' · ' + esc(ar.off_reason) : ''} · Sim accounts resume by themselves`}</span></div>
      <button type="button" class="bc-tog ${ar.on ? 'on' : ''}" data-bc="${ar.on ? 'ar-off' : 'ar-on'}" aria-pressed="${!!ar.on}" aria-label="Auto-resume"><i></i></button></div>
    <div class="bc-sw"><div><b>Restart server</b><span>${rs.why_not ? esc(rs.why_not) : 'run_bot.ps1 brings it back in ~10 s'}</span></div>
      <button type="button" class="btn ghost sm" data-bc="restart" ${rs.why_not ? 'disabled' : ''}>${icon('refresh')}<span>Restart</span></button></div>
    <p class="muted small">Version <b class="mono">${esc(au.sha || '—')}</b> on ${esc(au.branch || '?')}</p></div>`;
}

// ------------------------------------------------------------------ eval meter + room gauge
function gauge(f, label, sub, k) {
  const a0 = Math.PI, v = Math.max(0, Math.min(1, f || 0)), a1 = Math.PI * (1 - v);
  const P = (a, r = 52) => [60 + r * Math.cos(a), 62 - r * Math.sin(a)];
  const [x0, y0] = P(a0), [x1, y1] = P(a1), [xe, ye] = P(0);
  return `<svg viewBox="0 0 120 74" class="bc-gauge ${k}"><path d="M${x0} ${y0} A52 52 0 0 1 ${xe} ${ye}" class="bg"/>${v > 0.001 ? `<path d="M${x0} ${y0} A52 52 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}" class="fg"/>` : ''}
    <text x="60" y="54" text-anchor="middle" class="v">${label}</text><text x="60" y="70" text-anchor="middle" class="s">${sub}</text></svg>`;
}
function evalHTML(ev, compact = false) {
  if (!ev || ev.error) return empty('No eval numbers yet.', esc(ev?.error || 'live_model.json lit_sizing.eval_start sets the first session.'));
  const n = ev.sessions || 10, s = ev.session || 0, mll = ev.mll || 2000, roomF = (ev.room || 0) / mll;
  const dots = Array.from({ length: n }, (_, i) => `<i class="${i + 1 < s ? 'done' : i + 1 === s ? 'now' : ''}">${i + 1}</i>`).join('');
  return `<div class="bc-eval ${compact ? 'compact' : ''}">
    <div class="bc-eval-l"><div class="bc-big"><span>Balance</span><b>${fmt$(ev.balance)}</b><em class="${cls(ev.profit)}">${fmtS$(ev.profit)} since the start</em></div>
      <div class="pc-prog"><div class="pc-prog-h"><span>To the target ${fmt$(ev.target_balance)}</span><b>${fmt$(ev.to_target)} to go</b></div>${meter(ev.progress, 'good')}</div>
      <div class="pc-prog"><div class="pc-prog-h"><span>Daily loss used (soft ${fmt$(ev.dll)})</span><b>${fmt$(ev.dll_used)}</b></div>${meter((ev.dll_used || 0) / (ev.dll || 1000), (ev.dll_used || 0) > 700 ? 'bad' : 'warn')}</div>
      <div class="pc-dots">${dots}</div><p class="muted small">${esc(ev.clock_text || '')}${ev.sessions_left != null ? ` · ${ev.sessions_left} session${ev.sessions_left === 1 ? '' : 's'} left of the 2-week plan` : ''}</p></div>
    <div class="bc-eval-g">${gauge(roomF, fmt$(ev.room), 'room to the floor', roomF < 0.3 ? 'bad' : roomF < 0.6 ? 'warn' : 'good')}
      <p class="muted small">Floor ${fmt$(ev.floor)}${ev.locked ? ' (locked)' : ' trailing'} · max loss ${fmt$(mll)}</p></div></div>`;
}

// ------------------------------------------------------------------ open trade chart
async function mountTrade(box, ac) {
  const p = ac?.position;
  if (!box) return;
  if (!p || !p.side) { box.innerHTML = empty('Flat: no open trade.', esc(ac?.model_state || 'The live chart with entry / stop / target / breakeven appears here while the bot is in a trade.')); return; }
  if (!(ac.bars5 || []).length) { box.innerHTML = empty('No bars from the bot yet.'); return; }
  const sig = `${p.entry_t}:${p.stop}:${(ac.bars5 || []).length}`;
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  box.innerHTML = `<div class="bc-pos-k"><div><span>${esc(p.side)} ${p.qty} MNQ</span><b class="${cls(p.unrealized_usd)}">${fmtS$(p.unrealized_usd)}</b><em>${p.unrealized_r_now != null ? fmtR(p.unrealized_r_now) : ''}</em></div>
    <div><span>Entry</span><b>${px(p.entry)}</b><em>${etStr(p.entry_t)} ET</em></div><div><span>Stop</span><b class="dn">${px(p.stop)}</b><em>${p.be ? 'breakeven' : fmt$(p.risk_usd) + ' at risk'}</em></div>
    <div><span>Target</span><b class="up">${px(p.target)}</b><em>${esc(p.target_label || '')}</em></div><div><span>BE at +1R</span><b>${p.be ? 'done' : px(p.be_trigger)}</b><em>flat 15:55 ET</em></div></div><div class="nx-tcbox bc-tc"></div>`;
  try {
    const TC = await loadTC();
    const rec = TC.fromTrade(posTrade(p, ac), ac.bars5, { bars1: ac.bars1 });
    TC.mount(box.querySelector('.bc-tc'), rec, { tf: ac.bars1 ? '1m' : '5m' });
  } catch { box.querySelector('.bc-tc').innerHTML = empty('Chart unavailable.'); }
}

// ------------------------------------------------------------------ rule checklist + why no trade
function rulesHTML(ins) {
  if (!ins || ins.error) return empty('No live model state.', esc(ins?.error || ''));
  const w = ins.why || {};
  return `<div class="bc-why ${w.trading ? 'good' : ''}"><b>${esc(w.headline || '')}</b>${w.model_state ? `<span>${esc(w.model_state)}</span>` : ''}</div>
    <ol class="bc-steps">${(ins.checklist || []).map((r, i) => `<li class="${r.met ? 'met' : ''}"><i>${r.met ? icon('check') : i + 1}</i><div><b>${esc(r.label)}</b><span>${esc(r.detail || '')}</span></div></li>`).join('')}</ol>
    ${(w.reasons || []).length ? `<div class="bc-reasons">${w.reasons.map((r) => `<div>${dot(r.ok)}<span>${r.t ? `<b class="mono">${etStr(r.t)}</b> ` : ''}${esc(r.text)}</span></div>`).join('')}</div>` : ''}`;
}

// ------------------------------------------------------------------ session clock + radar
const KZ_COL = { london: 'var(--ssl)', nyam: 'var(--bsl)', nypm: 'var(--amt)' };
function clockHTML(ins) {
  const kz = ins?.killzones || [], cut = ins?.cutoffs || [];
  const p = etParts(Date.now() / 1000);
  // 18:00 ET opens the next trading day: from then on the clock counts down to tomorrow's killzones
  const eve = p.h >= 18, mod = p.h * 60 + p.mi + p.s / 60 - (eve ? 1440 : 0);
  const dow = (new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay() + (eve ? 1 : 0)) % 7;
  const A = 0, Z = 1020, X = (m) => ((m - A) / (Z - A) * 100).toFixed(2) + '%', wk = dow >= 1 && dow <= 5;
  const rows = [];
  for (const z of kz) {
    const st = mod < z.from ? `starts in ${inS((z.from - mod) * 60)}` : mod < z.to ? `<b class="up">LIVE</b> · ends in ${inS((z.to - mod) * 60)}` : 'done';
    rows.push(`<div class="bc-kz"><i style="background:${KZ_COL[z.id] || 'var(--accent)'}"></i><b>${esc(z.label)}</b><span class="mono">${String(z.from / 60 | 0).padStart(2, '0')}:${String(z.from % 60).padStart(2, '0')}-${String(z.to / 60 | 0).padStart(2, '0')}:${String(z.to % 60).padStart(2, '0')}</span><em>${wk ? st : 'weekend'}</em></div>`);
  }
  for (const c of cut) rows.push(`<div class="bc-kz"><i class="cut"></i><b>${esc(c.label)}</b><span class="mono">${String(c.at / 60 | 0).padStart(2, '0')}:${String(c.at % 60).padStart(2, '0')}</span><em>${wk ? (mod < c.at ? 'in ' + inS((c.at - mod) * 60) : 'passed') : ''}</em></div>`);
  return `<div class="bc-day"><div class="bc-day-t">${kz.map((z) => `<span style="left:${X(z.from)};width:calc(${X(z.to)} - ${X(z.from)});background:${KZ_COL[z.id]}" title="${esc(z.label)}"></span>`).join('')}
      ${cut.map((c) => `<em class="cut" style="left:${X(c.at)}"></em>`).join('')}${mod >= A && mod <= Z ? `<b class="now" style="left:${X(mod)}"></b>` : ''}</div>
    <div class="bc-day-ax"><span>00</span><span>04</span><span>08</span><span>12</span><span>16</span></div></div>
    <div class="bc-kzs">${rows.join('')}</div><p class="muted small">New York time · now ${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}:${String(p.s).padStart(2, '0')} ET · 95 of 120 LIT trades of 2026 entered 02:00-08:00.</p>`;
}
function radarHTML(ins) {
  const r = ins?.radar || {};
  const L = r.levels || [];
  if (!L.length) return empty('No levels yet.', 'Built from the 5m bars once the session has printed.');
  const mx = Math.max(...L.map((x) => Math.abs(x.dist_pts)), 1);
  const kz = r.killzone;
  return `${kz ? `<p class="bc-next">${icon('clock')}<span>${kz.now ? `<b>${esc(kz.label)}</b> is live · ends in ${inS(kz.ends_in_s)}` : `Next killzone <b>${esc(kz.label)}</b> in ${inS(kz.starts_in_s)}`}</span></p>` : ''}
    <div class="bc-radar">${L.map((x) => `<div class="${x.above ? 'up' : 'dn'}"><b>${esc(x.label)}</b><span class="mono">${px(x.price)}</span>
      <i><u style="width:${(Math.abs(x.dist_pts) / mx * 100).toFixed(1)}%"></u></i><em class="mono">${x.dist_pts > 0 ? '+' : ''}${fmtN(x.dist_pts, 1)} pts</em></div>`).join('')}</div>
    <p class="muted small">Untaken LIT levels nearest NQ ${px(r.price)} · a sweep of one by 0.5 ATR, then a 5m CISD, is the setup.</p>`;
}
function planHTML(pl) {
  if (!pl || pl.error) return empty('No LIT plan yet.', esc(pl?.error || ''));
  const sw = (pl.swept || []).slice(-8);
  return `<p class="bc-plan">${esc(pl.plan || pl.waiting || 'The plan is written at 01:30 ET.')}</p>
    ${(pl.armed || []).length ? `<div class="bc-armed">${pl.armed.map((a) => `<div class="${a.side === 'LONG' ? 'up' : 'dn'}">${icon(a.side === 'LONG' ? 'long' : 'short')}<b>${esc(a.side)} limit ${px(a.limit)}</b><span>stop ${px(a.stop)} · target ${px(a.target)}${a.expires_t ? ` · until ${etStr(a.expires_t)}` : ''}${a.tapped ? ' · tapped' : ''}</span></div>`).join('')}</div>` : ''}
    <div class="bc-lv"><span class="k">Watched</span>${(pl.watched || []).slice(0, 8).map((l) => chip(`${esc(l.label)} <b class="mono">${px(l.price)}</b>`, l.side === 'H' ? 'warn' : '')).join('') || '<span class="muted">—</span>'}</div>
    <div class="bc-lv"><span class="k">Swept</span>${sw.map((l) => chip(`${esc(l.label)}${l.depth_atr != null ? ` · ${fmtN(l.depth_atr, 2)} ATR` : ''}`, 'good')).join('') || '<span class="muted">none yet</span>'}</div>
    ${pl.news_text ? `<p class="muted small">${esc(pl.news_text)}</p>` : ''}<p class="muted small">Plan of ${esc(pl.day || '—')} · ${esc(pl.at || '')} · ${esc(pl.source || '')}</p>`;
}
function newsHTML(ins) {
  const n = ins?.news || {};
  const ev = n.events || [];
  return ev.length ? `<div class="bc-news">${ev.map((e) => `<div class="${e.tier1 ? 't1' : ''}"><span class="mono">${esc(e.time || '—')}</span><b>${esc(e.title)}</b>${e.tier1 ? chip('Tier 1', 'bad') : chip('high')}${e.blackout ? `<em>${esc(e.blackout)}</em>` : ''}</div>`).join('')}</div><p class="muted small">${esc(n.text || '')}</p>`
    : empty('No high-impact USD news today.', esc(n.source ? 'source: ' + n.source : ''));
}

// ------------------------------------------------------------------ equity with target + floor
function equityHTML(ac) {
  const eq = (ac?.equity || []).map(([d, v]) => [d, 50000 + (+v || 0)]);
  const ev = ac?.eval || {};
  if (eq.length < 2) return empty('The equity curve starts with the first routed trade.', 'Target ' + fmt$(ev.target_balance || 53000) + ' · floor ' + fmt$(ev.floor || 48000));
  const tgt = ev.target_balance || 53000, flo = ev.floor || 48000;
  const W = 640, H = 220, L = 54, R = 12, T = 12, Bm = 26;
  const vals = [...eq.map((x) => x[1]), tgt, flo], lo = Math.min(...vals) - 150, hi = Math.max(...vals) + 150;
  const x = (i) => L + i / (eq.length - 1) * (W - L - R), y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - Bm);
  const path = eq.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p[1]).toFixed(1)}`).join('');
  const area = path + `L${x(eq.length - 1).toFixed(1)} ${H - Bm}L${L} ${H - Bm}Z`;
  const ln = (v, k, t) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="bc-eq-${k}"/><text x="${W - R}" y="${y(v) - 4}" text-anchor="end" class="bc-eq-t ${k}">${t} ${fmt$(v)}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" class="bc-eq" preserveAspectRatio="none" width="100%" height="${H}">
    <defs><linearGradient id="bcEqG" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity=".32"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>
    ${ln(tgt, 'tgt', 'target')}${ln(flo, 'flo', 'floor')}${ln(50000, 'start', 'start')}
    <path d="${area}" fill="url(#bcEqG)"/><path d="${path}" class="bc-eq-l"/>
    ${eq.map((p, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(p[1]).toFixed(1)}" r="3" class="bc-eq-d"><title>${esc(p[0])} ${fmt$(p[1])}</title></circle>`).join('')}
    <text x="${L}" y="${H - 8}" class="bc-eq-t">${esc(eq[0][0])}</text><text x="${W - R}" y="${H - 8}" text-anchor="end" class="bc-eq-t">${esc(eq[eq.length - 1][0])}</text></svg>`;
}
function calHTML(ac) {
  const days = ac?.days || [];
  const today = ac?.today || new Date().toISOString().slice(0, 10), month = String(today).slice(0, 7);
  const byDay = new Map(days.map(([d, v]) => [d, { pnl: v, n: (ac.trades || []).filter((t) => t.day === d).length || 1 }]));
  const g = calGrid(byDay, month, today, 2000);
  return `${g.html}<p class="muted small" style="margin-top:8px">${MON[+month.slice(5) - 1]} ${month.slice(0, 4)} · ${g.n ? `<b class="${cls(g.net)}">${fmtS$(g.net)}</b> · ${g.n} trade${g.n === 1 ? '' : 's'} · ${g.g} green day${g.g === 1 ? '' : 's'}` : 'no routed trades this month'}</p>`;
}

// ------------------------------------------------------------------ bar-by-bar replay
const RP = { rec: null, i: 0, tf: '1m', timer: null, id: null };
function replayShell(ac) {
  const tr = (ac?.trades || []).slice(0, 40);
  const opts = [...(ac?.position?.side ? [{ v: 'pos', l: `Open now · ${ac.position.side}` }] : []), ...tr.map((t) => ({ v: String(t.entry_t), l: `${fDate(t.day)} ${t.entry_t ? etStr(t.entry_t) : ''} · ${t.side} · ${fmtS$(t.pnl)}` }))];
  if (!opts.length) return empty('No trade to replay yet.', 'Every routed trade (and the open one) can be stepped through bar by bar here.');
  return `<div class="bc-rp-bar"><div class="seg sm bc-rp-pick">${opts.slice(0, 6).map((o, k) => `<button type="button" data-rp="${esc(o.v)}" class="${(RP.id || opts[0].v) === o.v ? 'on' : ''}">${esc(o.l)}</button>`).join('')}</div></div>
    <div class="bc-rp-ctl"><button type="button" class="btn ghost sm" data-rpc="back">${icon('first')}</button><button type="button" class="btn primary sm" data-rpc="play">${icon('play')}<span>Play</span></button><button type="button" class="btn ghost sm" data-rpc="step">${icon('next')}</button>
      <input type="range" min="1" max="2" value="1" class="bc-rp-r" aria-label="replay position"><span class="mono small bc-rp-t">—</span></div><div class="bc-rp-plot nx-tcbox"></div>`;
}
async function loadReplay(box, ac, id) {
  RP.id = id; clearInterval(RP.timer); RP.timer = null;
  const plot = box.querySelector('.bc-rp-plot'); if (!plot) return;
  plot.innerHTML = '<div class="muted small">Loading…</div>';
  try {
    const TC = await loadTC();
    let rec;
    if (id === 'pos') rec = TC.fromTrade(posTrade(ac.position, ac), ac.bars5, { bars1: ac.bars1 });
    else {
      const t = (ac.trades || []).find((x) => String(x.entry_t) === id);
      if (t?.chart) rec = await TC.load(t.chart, { base: '/api/next/tradechart/', ext: '' });
      else {
        const d = await api('/api/next/pc/trade/' + id);
        rec = d.chart ? await TC.load(d.chart, { base: '/api/next/tradechart/', ext: '' }) : TC.fromTrade({ ...d.trade, exit_price: d.trade.exit_px }, d.bars5, { bars1: d.bars1 });
      }
    }
    RP.rec = rec; RP.tf = rec._bars1?.length ? '1m' : '5m';
    const bars = RP.tf === '1m' ? rec._bars1 : rec._bars5;
    const e = Math.max(1, bars.findIndex((b) => b.t >= rec.entry.t));
    RP.i = Math.max(5, e - (RP.tf === '1m' ? 20 : 6));
    const r = box.querySelector('.bc-rp-r'); r.max = bars.length; r.value = RP.i;
    drawReplay(box);
  } catch (err) { plot.innerHTML = empty('Replay unavailable.', esc(err.message)); }
}
function drawReplay(box) {
  const rec = RP.rec, plot = box.querySelector('.bc-rp-plot'); if (!rec || !plot) return;
  loadTC().then((TC) => {
    const one = RP.tf === '1m', bars = one ? rec._bars1 : rec._bars5, n = Math.max(1, Math.min(bars.length, RP.i));
    const cut = bars[n - 1].t;
    const r2 = { ...rec, _bars1: one ? rec._bars1.slice(0, n) : rec._bars1.filter((b) => b.t <= cut), _bars5: one ? rec._bars5.filter((b) => b.t <= cut) : rec._bars5.slice(0, n) };
    if (!r2._bars5.length) r2._bars5 = rec._bars5.slice(0, 1);
    const W = Math.max(280, Math.floor(plot.clientWidth || 600)), H = Math.round(Math.max(240, Math.min(420, W * (W < 520 ? 0.75 : 0.42))));
    plot.innerHTML = TC.svg(r2, { width: W, height: H, tf: RP.tf, view: { i0: Math.max(-2, n - (one ? 90 : 60)), i1: n + 6 } });
    const t = box.querySelector('.bc-rp-t');
    if (t) t.textContent = `${etStr(cut)} ET · bar ${n}/${bars.length}${cut >= rec.entry.t ? (rec.exit && cut >= rec.exit.t ? ` · ${rec.exit_kind} ${fmtS$(rec.pnl)}` : ' · in trade') : ' · before entry'}`;
    const r = box.querySelector('.bc-rp-r'); if (r) r.value = n;
  });
}
function bindReplay(box, ac) {
  if (!box) return;
  $$('[data-rp]', box).forEach((b) => { b.onclick = () => { $$('[data-rp]', box).forEach((x) => x.classList.toggle('on', x === b)); loadReplay(box, ac, b.dataset.rp); }; });
  const r = box.querySelector('.bc-rp-r'); if (r) r.oninput = () => { RP.i = +r.value; drawReplay(box); };
  $$('[data-rpc]', box).forEach((b) => {
    b.onclick = () => {
      const bars = RP.rec ? (RP.tf === '1m' ? RP.rec._bars1 : RP.rec._bars5) : [];
      if (b.dataset.rpc === 'back') { RP.i = Math.max(5, RP.i - 10); drawReplay(box); }
      if (b.dataset.rpc === 'step') { RP.i = Math.min(bars.length, RP.i + 1); drawReplay(box); }
      if (b.dataset.rpc === 'play') {
        if (RP.timer) { clearInterval(RP.timer); RP.timer = null; b.lastChild.textContent = 'Play'; return; }
        b.lastChild.textContent = 'Pause';
        RP.timer = setInterval(() => { if (!box.isConnected || RP.i >= bars.length) { clearInterval(RP.timer); RP.timer = null; b.lastChild.textContent = 'Play'; return; } RP.i += 1; drawReplay(box); }, 140);
      }
    };
  });
  const first = $('[data-rp].on', box) || $('[data-rp]', box);
  if (first && (!RP.rec || RP.id !== first.dataset.rp)) loadReplay(box, ac, first.dataset.rp); else drawReplay(box);
}

// ------------------------------------------------------------------ backtest vs live overlay
function overlayHTML(xd) {
  const rows = (xd?.rows || []).filter((r) => r.status !== 'extra').slice().sort((a, b) => a.entry_t - b.entry_t);
  if (!rows.length) return empty('No live trades to compare yet.', 'After the first routed trade, its live P&L is drawn against the LIT backtest on the same bars (engine/fill_audit.py).');
  let cl = 0, cb = 0; const pts = rows.map((r) => { cl += +(r.live_pnl || 0); cb += +(r.bt_pnl || 0); return [r.day, cl, cb, r.status]; });
  const W = 640, H = 200, L = 54, R = 12, T = 12, Bm = 22, n = pts.length;
  const all = pts.flatMap((p) => [p[1], p[2]]).concat([0]), lo = Math.min(...all) - 50, hi = Math.max(...all) + 50;
  const x = (i) => L + (n === 1 ? 0.5 : i / (n - 1)) * (W - L - R), y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - Bm);
  const pl = (k) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p[k]).toFixed(1)}`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" class="bc-eq" preserveAspectRatio="none" width="100%" height="${H}"><line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" class="bc-eq-start"/>
    <path d="${pl(2)}" class="bc-ov-bt"/><path d="${pl(1)}" class="bc-eq-l"/>${pts.map((p, i) => p[3] === 'missed' ? `<circle cx="${x(i)}" cy="${y(p[1])}" r="4" class="bc-ov-miss"><title>missed ${esc(p[0])}</title></circle>` : '').join('')}</svg>
    <p class="small"><span class="bc-key l"></span> live ${fmtS$(cl)} &nbsp; <span class="bc-key b"></span> backtest ${fmtS$(cb)} &nbsp; <span class="muted">gap ${fmtS$(cl - cb)} over ${n} trade${n === 1 ? '' : 's'} · red dots = missed</span></p>`;
}

// ------------------------------------------------------------------ switches (read-only), alerts, timeline, changelog
function switchesHTML(sw) {
  if (!sw || sw.error) return empty('No adopt-candidate numbers.', esc(sw?.error || ''));
  const b = sw.base?.rule || {};
  const cell = (r, k) => (r?.[k] ? `<b class="${cls((r[k].net || 0) - (b[k]?.net || 0))}">${fmtS$((r[k].net || 0) - (b[k]?.net || 0))}</b><em>PF ${fmtN(r[k].pf, 2)} · ${fmt$(r[k].per_month)}/mo</em>` : '—');
  return `<div class="bc-sws">${sw.switches.map((s) => `<div class="bc-swr"><div class="bc-swr-h"><b>${esc(s.name)}</b>${chip(s.on ? 'ON' : s.waiting ? 'OFF · waiting for the Sim check' : 'OFF', s.on ? 'good' : s.waiting ? 'warn' : '')}<span class="muted small mono">${esc(s.key)}</span></div>
      <p>${esc(s.what)}</p><div class="bc-swn"><div><span>H1 2026 (picked)</span>${cell(s.rule, 'H1')}</div><div><span>H2 2026 (check)</span>${cell(s.rule, 'H2')}</div>
      <div><span>2-week pass H2</span><b>${s.eval?.H2?.p10 != null ? fmtN(s.eval.H2.p10, 1) + '%' : '—'}</b><em>base ${sw.base?.eval?.H2?.p10 != null ? fmtN(sw.base.eval.H2.p10, 1) + '%' : '—'}</em></div></div>
      <p class="muted small">${icon('info')} ${esc(s.note)} · ${esc(s.writeup)}</p></div>`).join('')}</div>
    ${sw.live?.rule?.H1 ? `<p class="small"><b>Live now (${esc(sw.switches.filter((s) => s.on).map((s) => s.key).join(' + ') || 'none')}):</b> H1 ${fmtS$(sw.live.rule.H1.net)} PF ${fmtN(sw.live.rule.H1.pf, 2)} · H2 ${fmtS$(sw.live.rule.H2?.net)} PF ${fmtN(sw.live.rule.H2?.pf, 2)} · eval 2-week pass/fail H1 ${fmtN(sw.live.eval?.H1?.p10, 1)}/${fmtN(sw.live.eval?.H1?.f10, 1)} · H2 ${fmtN(sw.live.eval?.H2?.p10, 1)}/${fmtN(sw.live.eval?.H2?.f10, 1)}</p>` : ''}
    <p class="muted small">Net vs the 2026-10-18 LIT without upgrades (base H1 ${fmtS$(b.H1?.net)} / H2 ${fmtS$(b.H2?.net)}). Read-only: ${esc(sw.how)}.</p>`;
}
function alertsHTML(ins) {
  const rows = ins?.alerts?.rows || [];
  return rows.length ? `<div class="bc-log">${rows.map((r) => `<div><span class="mono">${r.t ? etStr(r.t, true).slice(5) : '—'}</span>${chip(esc(r.kind || 'push'))}<b>${esc(r.title || r.key || '')}</b></div>`).join('')}</div>`
    : empty('No push sent by this server yet.', 'Entries, outcomes and PC warnings appear here once they go to the phone.');
}
const TL_I = { start: 'power', feed: 'warn', update: 'download', heartbeat: 'send', risk: 'warn', error: 'warn', warn: 'warn', system: 'info', kill: 'power' };
function timelineHTML(ins) {
  const rows = ins?.timeline || [];
  return rows.length ? `<div class="bc-tl">${rows.slice(0, 24).map((r) => `<div class="k-${esc(r.kind)}"><span class="mono">${etStr(r.t, true).slice(5)}</span><i>${icon(TL_I[r.kind] || 'dot')}</i><b>${esc(r.text)}</b></div>`).join('')}</div>` : empty('No events yet.');
}
function changelogHTML(ins) {
  const c = ins?.changelog || {};
  const rows = (c.commits || []).filter((r) => !r.error);
  return `<p class="small">Running <b class="mono">${esc(c.version?.sha || '—')}</b> on ${esc(c.version?.branch || '?')}${c.since ? ` · changes since ${esc(String(c.since).slice(0, 7))}` : ' · latest changes'}</p>
    <div class="bc-log">${rows.map((r) => `<div><span class="mono">${esc(r.sha)}</span>${r.wip ? chip('in progress', 'warn') : ''}<b>${esc(r.title)}</b><em>${etStr(r.t, true).slice(0, 10)}</em></div>`).join('') || '<span class="muted">—</span>'}</div>`;
}

// ------------------------------------------------------------------ render: Today
export async function renderToday(force) {
  const el = $('#bcToday'); if (!el) return;
  const s = await getStatus(force);
  if (!s || s.error) { el.innerHTML = card('Bot Control', empty('No answer from the server.', esc(s?.error || ''))); return; }
  const html = `<div class="bc-hero nx-glass">${stripHTML(s)}
    <div class="bc-today">${startHTML(s, true)}<div class="bc-today-r"><div class="card-h"><h3>Eval</h3><button type="button" class="btn ghost sm" data-goto="botctl">${icon('engine')}<span>Bot Control</span></button></div>${evalHTML(s.eval, true)}</div></div></div>`;
  if (el._h === html) return;              // nothing changed: keep the DOM (no flicker, hover state kept)
  el._h = html;
  el.innerHTML = html;
  bind(el);
}

// ------------------------------------------------------------------ render: Bot Control page
async function renderPage(force) {
  const el = $('#page-botctl'); if (!el || !isActive('botctl')) return;
  const [s, ins] = await Promise.all([getStatus(force), getInsights(force)]);
  if (!s || s.error) { el.innerHTML = card('Bot Control', empty('No answer from the server.', esc(s?.error || ''))); return; }
  if (!el.querySelector('.bc-page')) {
    el.innerHTML = `<div class="bc-page">
      <div class="nx-hero"><div><div class="nx-eyebrow">Bot Control · Zlarior · NinjaTrader</div><h2>Start, watch, stop</h2><p class="muted">Pick the account, let the checklist go green, press START. Sim starts with one click; a real account needs the confirm phrase you type each time. Paper and Sim by default.</p></div></div>
      <div id="bcStrip"></div>
      <div class="bc-grid2"><div id="bcStart"></div><div id="bcRight"></div></div>
      <div class="bc-sec">You · presence and hands-off</div>
      <div id="bcPresence"></div>
      <div class="bc-sec">Live</div>
      <div class="bc-grid2"><div id="bcTrade"></div><div id="bcRules"></div></div>
      <div class="bc-sec">Today</div>
      <div class="bc-grid3"><div id="bcPlan"></div><div id="bcRadar"></div><div id="bcClock"></div></div>
      <div class="bc-grid2"><div id="bcNews"></div><div id="bcReplayW"></div></div>
      <div class="bc-sec">Performance</div>
      <div class="bc-grid2"><div id="bcEquity"></div><div id="bcCal"></div></div>
      <div class="bc-grid2"><div id="bcOverlay"></div><div id="bcExec"></div></div>
      <div id="bcExtra"></div>
      <div class="bc-sec">System</div>
      <div id="bcSwitches"></div>
      <div class="bc-grid3"><div id="bcAlerts"></div><div id="bcTimeline"></div><div id="bcChangelog"></div></div></div>`;
  }
  const put = (id, html) => { const b = document.getElementById(id); if (b && b._h !== html) { b._h = html; b.innerHTML = html; return true; } return false; };
  put('bcStrip', stripHTML(s));
  if (put('bcStart', card('Start the bot', startHTML(s), `<span class="muted small">checked ${etStr(s.t)} ET</span>`))) bind($('#bcStart'));
  if (put('bcRight', card('Safety', safetyHTML(s)) + card('MFFU 50K eval', evalHTML(s.eval)))) bind($('#bcRight'));
  if (ins && !ins.error) {
    put('bcRules', card('LIT rule checklist · now', rulesHTML(ins), '<span class="muted small">why no trade today</span>'));
    put('bcRadar', card('Next-setup radar', radarHTML(ins)));
    put('bcClock', card('Session clock', clockHTML(ins), '<span class="muted small">killzones · cutoff</span>'));
    put('bcNews', card('Economic calendar · today', newsHTML(ins)));
    put('bcAlerts', card('Alerts sent', alertsHTML(ins)));
    put('bcTimeline', card('System health', timelineHTML(ins)));
    put('bcChangelog', card('Version + changes', changelogHTML(ins)));
  }
  import('./presence.js').then((m) => m.mount(document.getElementById('bcPresence'), force)).catch(() => null);
  getPlan(force).then((pl) => put('bcPlan', card('Today’s LIT plan', planHTML(pl))));
  getAccount(force).then((ac) => {
    if (!ac || ac.error) return;
    if (!document.getElementById('bcTradeBox')) put('bcTrade', card('Open trade · live chart', '<div id="bcTradeBox"></div>'));
    mountTrade(document.getElementById('bcTradeBox'), ac);
    put('bcEquity', card('Equity · eval target and floor', equityHTML(ac)));
    put('bcCal', card('Daily P&amp;L', calHTML(ac), '<button type="button" class="btn ghost sm" data-goto="pnlcal">all months</button>'));
    if (put('bcReplayW', card('Replay a trade · bar by bar', `<div id="bcReplay">${replayShell(ac)}</div>`))) bindReplay(document.getElementById('bcReplay'), ac);
    put('bcExtra', extraAccountsCard(ac));
  });
  getExec().then((x) => { put('bcOverlay', card('Backtest vs live', overlayHTML(x))); put('bcExec', card('Execution quality', execBody(x))); });
  getSwitches().then((sw) => put('bcSwitches', card('Strategy switches · adopt-candidates (read-only)', switchesHTML(sw))));
}

async function refresh(force) {
  if (isActive('botctl')) await renderPage(force);
  if (isActive('command')) await renderToday(force);
}

export const botctl = { show: () => renderPage(true) };
export function initBotControl() {
  renderToday(true);
  setInterval(() => { if (!document.hidden) refresh(false); }, 5000);
  setInterval(() => { if (!document.hidden && isActive('botctl') && B.ins) { const b = document.getElementById('bcClock'); if (b) { const h = card('Session clock', clockHTML(B.ins), '<span class="muted small">killzones · cutoff</span>'); b.innerHTML = h; b._h = h; } } }, 1000);
}
