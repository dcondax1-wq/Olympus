// Start & Accounts (2026-10-26): START BOT (engine/go.py) as one checklist, one button per red line, and the account panel.
// Reads GET /api/next/start/status; every button POSTs to /api/next/start/* (engine/start_api.py), which only answers a
// browser on this PC (the phone sees the same page read-only). Arming needs the owner's typed I ACCEPT LIVE RISK.
// One button (2026-10-26 PM, owner: "automatic through the dashboard ONLY"): "Start trading" runs every step in one job
// (engine/go.step_auto: update, NinjaTrader, live bars, Sim test once, start); the phrase box shows only when arming is
// needed (no valid auto-resume for the 50K). A stop the page can retry by itself is retried (retry_s) while it is open.
import { $, esc, toast } from '../util.js';
import { icon } from './icons.js';

const P = { d: null, timer: null, open: null, busy: false, offline: 0, retryAt: 0, tick: null, clockMsg: null, cpf: null };
const SS = { get: (k) => { try { return sessionStorage.getItem('st.' + k); } catch { return null; } },
  set: (k, v) => { try { if (v == null) sessionStorage.removeItem('st.' + k); else sessionStorage.setItem('st.' + k, String(v)); } catch { /* private mode */ } } };
const MAX_TRIES = 30;
const norm = (s) => String(s || '').trim().replace(/\s+/g, ' ').toUpperCase();   // capitals do not matter (engine/go.typed_phrase)
const STAGES = [['update', 'Update'], ['accounts', 'Accounts'], ['setup', 'Setup'], ['nt', 'NinjaTrader'], ['feed', 'Live bars'],
  ['sims', 'Sim test'], ['start', 'Start'], ['running', 'Running']];
const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const usd = (v) => (!ok(v) ? '—' : (v < 0 ? '−' : '') + '$' + Math.abs(+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const active = () => document.getElementById('page-start')?.classList.contains('active');
const chip = (t, k = '') => `<span class="nx-chip ${k}">${esc(t)}</span>`;
const dot = (v) => `<span class="op-dot ${v ? 'good' : 'bad'}"></span>`;

async function post(path, body = {}) {
  const r = await fetch('/api/next/start/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.ok === false) throw new Error(d.error || 'HTTP ' + r.status);
  return d;
}

// ------------------------------------------------------------------ the checklist
function stepRow(s, d, withPanel) {
  const lock = !d.local ? 'Only on the PC itself' : d.job?.running ? 'A step is running' : !s.ready ? `First: ${s.first}` : '';
  const btn = s.done ? '' : `<button type="button" class="btn ${s.key === 'armed' || s.key === 'running' ? 'primary' : ''} sm" data-act="${esc(s.action)}" ${lock ? `disabled title="${esc(lock)}"` : ''}>${esc(s.button)}</button>`;
  return `<div class="st-row ${s.done ? 'done' : 'red'}" data-key="${esc(s.key)}">
    ${dot(s.done)}<div class="st-txt"><b>${esc(s.label)}</b><span>${esc(s.detail || '')}</span>${!s.done && lock && d.local ? `<em>${esc(lock)}</em>` : ''}</div>
    <div class="st-btn">${s.done ? `<span class="st-ok">${icon('check')}</span>` : btn}</div></div>
    ${withPanel ? panel(s.action, d) : ''}`;
}

const picks = (d) => `<datalist id="stNames">${(d.accounts?.picks || []).map((p) => `<option value="${esc(p.name)}">${p.balance != null ? usd(p.balance) : esc(p.src)}</option>`).join('')}</datalist>`;

function panel(kind, d) {
  if (kind === 'names') {
    return `<div class="st-panel"><p class="muted">Exactly as NinjaTrader's Accounts tab shows them${(d.accounts?.picks || []).length ? ' (or pick one: the list comes from NinjaTrader)' : ''}.</p>
      <div class="st-grid"><label>50K · Zlarior<input id="stLit" list="stNames" value="${esc(d.lit || d.suggest_lit || '')}" placeholder="e.g. MFFUEV50K…" autocomplete="off"></label>
      <label>25K · ATLAS<input id="stAtlas" list="stNames" value="${esc(d.atlas || '')}" placeholder="e.g. MFFUEV25K…" autocomplete="off"></label></div>
      <div class="st-acts"><button type="button" class="btn primary sm" data-do="names">Save the names</button><button type="button" class="btn ghost sm" data-do="close">Cancel</button></div></div>`;
  }
  if (kind === 'arm') {
    return `<div class="st-panel st-arm"><p><b>Real money.</b> The bot will trade:</p>
      <div class="st-who"><span>Zlarior (LIT)</span><b>→ 50K ${esc(d.lit || '?')}</b><span>ATLAS</span><b>→ 25K ${esc(d.atlas || '?')}</b></div>
      <p class="muted">Check both names against NinjaTrader's Accounts tab (50K about $49,700, 25K about $25,000). Typing the line also lets the bot come back by itself after a restart (PC on + NinjaTrader connected); the kill switch or STOP BOT turns that off.</p>
      <label class="st-phrase">Type <b>${esc(d.phrase)}</b><input id="stPhrase" autocomplete="off" spellcheck="false" placeholder="${esc(d.phrase)}"></label>
      <div class="st-acts"><button type="button" class="btn primary" data-do="arm" id="stArmGo" disabled>Arm and start</button><button type="button" class="btn ghost sm" data-do="close">Cancel</button></div></div>`;
  }
  return '';
}

function jobCard(j) {
  if (!j || !j.step) return '';
  const name = j.step === 'arm' ? 'Arm and start' : j.step === 'auto' ? 'Start trading: the steps' : 'Sim test';
  const st = j.running ? chip('running', 'warn') : j.rc === 0 ? chip('done', 'good') : chip(j.state === 'done' ? 'stopped (see the lines)' : 'stopped', j.retry_s || j.need ? 'warn' : 'bad');
  return `<div class="card nx-glass cc-card st-job"><div class="card-h"><h3>${esc(name)}</h3><div class="card-tools">${st}</div></div>
    ${j.running ? `<p class="muted">${j.step === 'sims' ? 'The dashboard restarts during the test (about 2 minutes): this page reconnects by itself.' : 'The bot server may restart once: this page reconnects by itself.'}</p>` : ''}
    ${(j.lines || []).length ? `<pre class="st-log">${esc(j.lines.join('\n'))}</pre>` : ''}</div>`;
}

// ------------------------------------------------------------------ the one button: Start trading
function stageOf(j) {
  const s = j?.step === 'auto' ? (j.stage === 'arm' ? 'start' : j.stage) : null;
  const i = STAGES.findIndex(([k]) => k === s);
  return i < 0 ? null : i;
}

function goCard(d) {
  const j = d.job || {};
  const auto = j.step === 'auto';
  const runOk = d.running && d.steps.find((s) => s.key === 'running')?.done;
  const i = auto ? stageOf(j) : null;
  const failed = auto && !j.running && j.rc != null && j.rc !== 0;
  const pills = STAGES.map(([k, label], n) => {
    const st = runOk ? 'done' : i == null ? '' : n < i ? 'done' : n === i ? (j.running ? 'now' : failed ? 'bad' : 'done') : '';
    return `<span class="st-pill ${st}">${st === 'done' ? icon('check') : st === 'now' ? '<i class="st-spin"></i>' : ''}${esc(label)}</span>`;
  }).join('');
  const wait = P.retryAt ? Math.max(0, Math.round((P.retryAt - Date.now()) / 1000)) : 0;
  let say = runOk ? 'Running. Leave the PC on, plugged in, NinjaTrader open. First trades from 02:00 ET.'
    : auto && j.say ? j.say : d.running ? 'The bot runs with the wrong set-up: see the list below.'
      : 'Press Start trading (or Run in the switch at the top of every page: the same thing): the page does every step by itself.';
  const tone = runOk ? 'good' : failed ? (j.need || j.retry_s ? 'warn' : 'bad') : j.running ? 'now' : '';
  const needPhrase = !d.running && d.need_phrase;
  const lock = !d.local ? 'Only on the PC itself (http://localhost:8766)' : j.running ? 'Working…' : '';
  const label = needPhrase ? 'Arm and start trading' : 'Start trading';
  const btn = runOk || d.running ? '' : `<button type="button" class="btn primary st-go" data-do="go" id="stGo" ${lock || (needPhrase && !P.phraseOk) ? 'disabled' : ''}
      ${lock ? `title="${esc(lock)}"` : ''}>${icon('play')}<span>${j.running && auto ? 'Working…' : label}</span></button>`;
  const phrase = needPhrase && d.local && !j.running ? `<div class="st-gophrase"><p><b>Real money, once.</b> Zlarior → 50K ${esc(d.lit || '?')} · ATLAS → 25K ${esc(d.atlas || '?')}.
      Typing it also lets the bot come back by itself after a restart (the kill switch turns that off).</p>
      <label class="st-phrase">Type <b>${esc(d.phrase)}</b><input id="stGoPhrase" autocomplete="off" spellcheck="false" placeholder="${esc(d.phrase)}"></label></div>` : '';
  const retry = P.retryAt && SS.get('auto') ? `<span class="st-retry" id="stRetry">Trying again in ${wait} s</span>
      <button type="button" class="btn ghost sm" data-do="autooff">Stop trying</button>` : '';
  return `<div class="card nx-glass cc-card st-gocard ${tone}"><div class="st-pills">${pills}</div>
    <p class="st-gosay">${esc(say)}</p>${phrase}
    <div class="st-acts">${btn}${retry}${!d.local ? `<span class="muted">${esc(lock)}</span>` : ''}</div></div>`;
}

function clockRow(d) {
  const c = d.clock || {};
  const bad = c.known && !c.ok;
  const off = c.known && Math.abs(c.drift_s || 0) >= 1;
  const btn = d.local && (off || P.clockMsg) ? `<button type="button" class="btn ${bad ? 'primary' : 'ghost'} sm" data-do="clock">Sync the clock</button>` : '';
  return `<div class="st-row ${bad ? 'red' : 'done'}" data-key="clock">${dot(!bad)}<div class="st-txt"><b>PC clock</b><span>${esc(c.say || 'checking')}</span>
    ${P.clockMsg ? `<em>${esc(P.clockMsg)}</em>` : ''}</div><div class="st-btn">${btn || (c.known && !off ? `<span class="st-ok">${icon('check')}</span>` : '')}</div></div>`;
}

// the page retries a stopped "Start trading" by itself (retry_s) while it is open and the owner pressed the button
function autoTick() {
  const d = P.d;
  const j = d?.job || {};
  if (!d || !SS.get('auto')) { P.retryAt = 0; return; }
  if (d.running || (j.step === 'auto' && !j.running && j.rc === 0) || j.need === 'names' || j.need === 'phrase' || j.need === 'stop') {
    SS.set('auto', null); SS.set('tries', null); P.retryAt = 0; return;
  }
  if (j.running || !(j.step === 'auto' && j.rc) || !j.retry_s) { P.retryAt = 0; return; }
  const tries = +(SS.get('tries') || 0);
  if (tries >= MAX_TRIES) { SS.set('auto', null); P.retryAt = 0; return; }
  const at = (j.t1 || Date.now() / 1000) * 1000 + j.retry_s * 1000;
  P.retryAt = Math.max(at, Date.now() + 2000);
}

async function startGo() {
  const v = $('#stGoPhrase')?.value || '';
  SS.set('auto', 1);
  SS.set('tries', +(SS.get('tries') || 0) + 1);
  P.retryAt = 0;
  return post('go', norm(v) === norm(P.d?.phrase) && v ? { confirm: v } : {});
}

// the running bot's last poll, stage by stage (engine/poll_timing.py): where the time goes
function pollCard(ps) {
  if (!ps || !ps.stages?.length) return '';
  const s1 = (ms) => (ms / 1000).toFixed(ms >= 10000 ? 0 : 1) + ' s';
  const top = ps.stages.filter((s) => !s.name.includes(' > ')).sort((a, b) => b.ms - a.ms).slice(0, 8);
  const max = Math.max(1, ...top.map((s) => s.ms));
  const slow = ps.total_ms > 5000;
  return `<div class="card nx-glass cc-card st-poll"><div class="card-h"><h3>Bot loop</h3><div class="card-tools">${chip(s1(ps.total_ms) + ' a poll', slow ? 'warn' : 'good')}</div></div>
    <p class="muted">CPU ${s1(ps.cpu_ms || 0)} · waiting ${s1(ps.wait_ms || 0)}${(ps.threads || []).length ? ` · busy meanwhile: ${esc(ps.threads[0].name)} ${s1(ps.threads[0].cpu_ms)}` : ''}</p>
    ${top.map((s) => `<div class="st-prow"><span>${esc(s.name)}</span><i style="width:${Math.max(2, Math.round(100 * s.ms / max))}%"></i><b>${s1(s.ms)}</b></div>`).join('')}</div>`;
}

// ------------------------------------------------------------------ the accounts
function acctRow(r, d) {
  const can = d.local && !d.running;
  const state = r.state === 'funded' ? chip('funded', 'good') : chip(r.eval_status && r.eval_status !== 'active' ? `eval · ${r.eval_status}` : 'eval');
  const armed = r.armed === true ? chip('armed', 'bad') : r.armed === false ? chip('not armed') : '';
  const open = P.open === 'anchor:' + r.name ? 'anchor' : P.open === 'funded:' + r.name ? 'funded' : '';
  const form = open === 'anchor'
    ? `<div class="st-panel"><p class="muted">The numbers on the MFFU dashboard after a session.</p><div class="st-grid three">
        <label>Balance<input id="stBal" type="number" step="0.01" value="${ok(r.balance) ? (+r.balance).toFixed(2) : ''}"></label>
        <label>Floor<input id="stFloor" type="number" step="0.01" value="${ok(r.floor) ? (+r.floor).toFixed(2) : ''}"></label>
        <label>As of<input id="stAsOf" type="date" value="${esc(r.as_of || '')}"></label></div>
        <div class="st-acts"><button type="button" class="btn primary sm" data-do="anchor" data-name="${esc(r.name)}">Save</button><button type="button" class="btn ghost sm" data-do="close">Cancel</button></div></div>`
    : open === 'funded'
      ? `<div class="st-panel"><p class="muted">After the pass MFFU gives a new funded account: its Name in NinjaTrader and the first funded session.</p><div class="st-grid">
        <label>Funded account Name<input id="stFName" list="stNames" autocomplete="off"></label>
        <label>First funded day<input id="stFStart" type="date" value="${esc(d.accounts?.today || '')}"></label></div>
        <div class="st-acts"><button type="button" class="btn primary sm" data-do="funded" data-name="${esc(r.name)}">Switch to funded</button><button type="button" class="btn ghost sm" data-do="close">Cancel</button></div></div>` : '';
  const btns = !d.local ? '' : `<div class="st-rbtn">
      ${r.state === 'eval' ? `<button type="button" class="btn ghost sm" data-open="anchor:${esc(r.name)}">Change balance</button>` : ''}
      ${r.state === 'eval' ? `<button type="button" class="btn ghost sm" data-open="funded:${esc(r.name)}" ${can ? '' : 'disabled title="Stop the bot first"'}>Passed → funded</button>` : ''}
      <button type="button" class="btn ghost sm st-rm" data-rm="${esc(r.name)}" ${can ? '' : 'disabled title="Stop the bot first"'}>Remove</button></div>`;
  return `<div class="st-acct ${r.bot === 'ATLAS' ? 'atlas' : r.bot === 'BLITZ' ? 'blitz' : 'lit'}"><div class="st-a1">
      <div class="st-aname"><b>${esc(r.name)}</b><span>${chip(r.bot, r.bot === 'ATLAS' ? 'atlas' : r.bot === 'BLITZ' ? 'blitz' : 'lit')} ${esc(r.plan_label || r.plan)} ${state} ${armed}</span></div>
      <div class="st-amoney"><span>Balance <b>${usd(r.balance)}</b></span><span>Floor <b>${usd(r.floor)}</b></span><em>${esc(r.source || '')}${r.as_of ? ' · as of ' + esc(r.as_of) : ''}</em></div>
      ${btns}</div>${r.note ? `<p class="st-note">${icon('info')}<span>${esc(r.note)}</span></p>` : ''}${form}</div>`;
}

function addForm(d) {
  if (!d.local) return '';
  const dis = d.running ? 'disabled title="Stop the bot first"' : '';
  return `<div class="st-add"><h4>Add an account</h4><div class="st-grid four">
    <label>NinjaTrader Name<input id="stAName" list="stNames" autocomplete="off" placeholder="exactly as NinjaTrader shows it"></label>
    <label>Plan<span class="st-seg" data-seg="plan"><button type="button" class="on" data-v="builder50k">Builder 50K</button><button type="button" data-v="builder25k">Builder 25K</button></span></label>
    <label>Bot<span class="st-seg" data-seg="strategy"><button type="button" class="on" data-v="zlarior">Zlarior</button><button type="button" data-v="atlas">ATLAS</button><button type="button" data-v="blitz">BLITZ</button></span></label>
    <label>Start day<input id="stAStart" type="date" value="${esc(d.accounts?.today || '')}"></label></div>
    <div class="st-acts"><button type="button" class="btn primary sm" data-do="add" ${dis}>Add</button><span class="muted">Never armed here: arming is the Start list's last step.</span></div></div>`;
}

// ------------------------------------------------------------------ BLITZ · 25K (account C, engine/account_c.py; OFF by default)
// The third slot next to Zlarior · 50K and ATLAS · 25K: BLITZ's own account. Sim test = BLITZ on a NinjaTrader Sim account (the
// real route, no real money); a real MFFU 25K trades only after the owner arms it here with the typed phrase.
function blitzCard(d) {
  const b = d.blitz || {};
  const can = d.local;                                // a running bot picks a change up once BLITZ is flat
  const lock = !d.local ? 'Only on the PC itself' : '';
  const state = !b.on ? chip('off') : b.sim ? chip('Sim test', 'good') : b.armed ? chip('armed', 'bad') : chip('not armed');
  const arm = b.on && !b.sim && !b.armed && d.local ? `<div class="st-panel st-arm"><p><b>Real money.</b> BLITZ will trade the 25K <b>${esc(b.name)}</b> (its own account, next to Zlarior and ATLAS, never trading against them).</p>
      <label class="st-phrase">Type <b>${esc(b.phrase || d.phrase)}</b><input id="stCPhrase" autocomplete="off" spellcheck="false" placeholder="${esc(b.phrase || d.phrase)}"></label>
      <div class="st-acts"><button type="button" class="btn primary sm" data-do="carm" id="stCArm" disabled>Arm BLITZ</button></div></div>` : '';
  const form = d.local ? `<div class="st-grid three">
      <label>25K · BLITZ<input id="stCName" list="stNames" value="${esc(b.on ? b.name : '')}" placeholder="e.g. MFFUEVBLDR… or Sim101" autocomplete="off"></label>
      <label>Start day<input id="stCStart" type="date" value="${esc(b.start || d.accounts?.today || '')}"></label>
      <span class="st-acts"><button type="button" class="btn primary sm" data-do="cset" ${can ? '' : `disabled title="${esc(lock)}"`}>Set BLITZ's 25K</button>
      <button type="button" class="btn ghost sm" data-do="csim" ${can ? '' : `disabled title="${esc(lock)}"`}>Sim test (Sim101)</button>
      ${b.on ? `<button type="button" class="btn ghost sm" data-do="coff" ${can ? '' : `disabled title="${esc(lock)}"`}>Off</button>` : ''}</span></div>` : '';
  return `<div class="card nx-glass cc-card st-blitz"><div class="card-h"><h3>BLITZ · 25K</h3><div class="card-tools">${state}</div></div>
    <p>${esc(b.say || 'BLITZ · 25K is off')}</p>${b.problem ? `<p class="st-note">${icon('info')}<span>${esc(b.problem)}</span></p>` : ''}
    <p class="muted">The scalper on its own MFFU 25K: up to 6 trades a day, flat by 15:55, never opposite to Zlarior or ATLAS (they go first). Off = paper only. Every rule and what to expect: BLITZ_STRATEGY.md.</p>
    ${form}${arm}${b.on ? cpfBlock() : ''}</div>`;
}

function cArmBtn() { const b = $('#stCArm'); if (b) b.disabled = norm($('#stCPhrase')?.value) !== norm(P.d?.blitz?.phrase || P.d?.phrase); }

// BLITZ's go-live check (GET /api/next/start/blitz/preflight = engine/blitz_preflight.py; also
// `python -X utf8 -m engine.account_c --preflight`): one green / red line each, every red line with its one fix.
async function loadCpf(fresh = false) {
  try {
    const r = await fetch('/api/next/start/blitz/preflight' + (fresh ? '?fresh=1' : ''));
    const v = await r.json();
    P.cpf = r.ok && Array.isArray(v.items) ? v : null;
  } catch { P.cpf = null; }
}

function cpfBlock() {
  const v = P.cpf;
  if (!v) return '';
  const st = (s) => (s === 'good' ? 'good' : s === 'bad' ? 'bad' : s === 'wait' ? 'warn' : 'info');
  const rows = v.items.map((i) => `<div class="st-row ${i.state === 'good' ? 'done' : i.state === 'bad' ? 'red' : ''}" data-cpf="${esc(i.key)}">
      <span class="op-dot ${st(i.state)}"></span><div class="st-txt"><b>${esc(i.label)}</b><span>${esc(i.detail)}</span>${i.state !== 'good' && i.fix ? `<em>${esc(i.fix)}</em>` : ''}</div></div>`).join('');
  return `<div class="st-cpf"><p><b>Go-live check</b> ${chip(v.all_green ? 'all green' : `${v.n_red} red`, v.all_green ? 'good' : 'bad')}</p>${rows}
    <p class="muted">Same check in a console: <code>${esc(v.cmd || 'python -X utf8 -m engine.account_c --preflight')}</code></p></div>`;
}

// ------------------------------------------------------------------ new MFFU account Names (engine/new_accounts.py)
// 2026-10-29: after a pass / fail MFFU issues a new account Name; when NinjaTrader shows a Name no bot uses, one line per Name
// with one tap per role that fits its size. The tap only assigns the Name (POST /api/next/start/newacct): nothing is armed,
// the next Start trading asks for the live phrase. Kept in these two functions (the BLITZ slot lives elsewhere on the page).
function newAcctLine(d) {
  const rows = d.new_accounts?.new || [];
  if (!rows.length) return '';
  const can = d.local && !d.running;
  return rows.map((r) => `<div class="st-ro warn st-newacct" style="flex-wrap:wrap">${icon('info')}<span style="flex:1 1 220px;min-width:0">${esc(r.say)}</span>${!d.local ? '' : `<span class="st-acts">
      ${(r.options || []).map((o) => `<button type="button" class="btn primary sm" data-na-use="${esc(o.act)}" data-label="${esc(o.label)}" data-name="${esc(r.name)}" ${can ? '' : 'disabled title="Stop the bot first"'}>${esc(o.label)}</button>`).join('')}
      <button type="button" class="btn ghost sm" data-na-no="${esc(r.name)}">Not for the bot</button></span>`}</div>`).join('');
}

function wireNewAcct(el) {
  el.addEventListener('click', (e) => {
    const u = e.target.closest('[data-na-use]');
    if (u && !u.disabled) {
      if (!confirm(`${u.dataset.label}: ${u.dataset.name}?\n\nNothing is armed: Start trading runs the setup for it and asks for I ACCEPT LIVE RISK.`)) return;
      act(() => post('newacct', { name: u.dataset.name, act: u.dataset.naUse }));
      return;
    }
    const n = e.target.closest('[data-na-no]');
    if (n) act(() => post('newacct', { name: n.dataset.naNo, dismiss: true }));
  });
}

// ------------------------------------------------------------------ PC self-test (engine/pc_selftest.py, 2026-10-30)
// One line: the last result (Sunday 15:30 ET, after each update, or this button) + "Run self-test" (PC only, 1-3 min at
// low priority; read-only: it never arms, routes or stops anything). Kept in these two functions.
function selftestLine(d) {
  const t = d.selftest;
  if (!t) return '';
  const bad = t.failed > 0;
  const when = t.t ? new Date(t.t * 1000).toLocaleString('en-US', { weekday: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  const why = bad && t.first?.length ? ` · ${t.first.map((x) => `${x.label}: ${x.why || 'failed'}`).join(' · ')}` : '';
  return `<div class="st-ro ${bad ? 'warn' : ''} st-selftest" style="flex-wrap:wrap">${icon(bad ? 'info' : 'check')}<span style="flex:1 1 220px;min-width:0">PC self-test: ${esc(t.running ? 'running now (1-3 min)…' : t.say || 'not run yet')}${when && !t.running ? ` (${esc(when)})` : ''}${esc(why)}</span>${d.local ? `<span class="st-acts"><button type="button" class="btn ghost sm" data-st-selftest ${t.running ? 'disabled' : ''}>Run self-test</button></span>` : ''}</div>`;
}

function wireSelftest(el) {
  el.addEventListener('click', (e) => {
    const b = e.target.closest('[data-st-selftest]');
    if (!b || b.disabled) return;
    b.disabled = true;
    post('selftest').then(() => { toast('Self-test started (1-3 min, low priority)'); load(); }, (err) => { toast(err.message); b.disabled = false; });
  });
}

// ------------------------------------------------------------------ draw
function draw() {
  const el = $('#page-start');
  const d = P.d;
  if (!el || !d) return;
  const keep = { lit: $('#stLit')?.value, atlas: $('#stAtlas')?.value, phrase: $('#stPhrase')?.value, aname: $('#stAName')?.value,
    go: $('#stGoPhrase')?.value, cname: $('#stCName')?.value, cphrase: $('#stCPhrase')?.value };
  const n = d.steps.filter((s) => s.done).length;
  const rows = d.accounts?.rows || [];
  el.innerHTML = `<div class="nx-hero cc-hero st-hero"><div><div class="nx-eyebrow">Start &amp; Accounts</div>
      <h2 class="st-say">${esc(d.say)}</h2>
      <p class="muted">${d.all_green ? 'Everything is done. Leave the PC on, plugged in, NinjaTrader open.' : `${n} of ${d.steps.length} done. Start trading does the rest by itself.`}</p></div>
      <div class="st-side">${d.local ? '' : `<div class="st-ro">${icon('phone')}<span>Read-only here: start and change accounts on the PC itself (http://localhost:8766).</span></div>`}
      ${P.offline ? `<div class="st-ro warn">${icon('refresh')}<span>Reconnecting to the bot server…</span></div>` : ''}</div></div>
    ${goCard(d)}
    ${newAcctLine(d)}
    ${selftestLine(d)}
    ${picks(d)}
    <div class="st-cols"><div class="card nx-glass cc-card st-list"><div class="card-h"><h3>Checklist</h3><div class="card-tools">${chip(`${n}/${d.steps.length}`, d.all_green ? 'good' : '')}</div></div>
      ${d.steps.map((s, i) => stepRow(s, d, i === d.steps.findIndex((x) => x.action === P.open && !x.done))).join('')}
      ${clockRow(d)}</div>
      ${jobCard(d.job) + pollCard(d.poll) ? `<div class="st-col2">${jobCard(d.job)}${pollCard(d.poll)}</div>` : ''}</div>
    <div class="card nx-glass cc-card st-accts"><div class="card-h"><h3>Accounts</h3><div class="card-tools">${d.running ? chip('bot running: stop it to add or remove', 'warn') : ''}</div></div>
      ${rows.length ? rows.map((r) => acctRow(r, d)).join('') : '<div class="pc-empty"><b>No accounts yet</b><span>Add the 50K for Zlarior and the 25K for ATLAS.</span></div>'}
      ${addForm(d)}</div>
    ${blitzCard(d)}`;
  if (keep.lit != null && $('#stLit')) $('#stLit').value = keep.lit;
  if (keep.atlas != null && $('#stAtlas')) $('#stAtlas').value = keep.atlas;
  if (keep.phrase && $('#stPhrase')) { $('#stPhrase').value = keep.phrase; armBtn(); }
  if (keep.aname && $('#stAName')) $('#stAName').value = keep.aname;
  if (keep.go && $('#stGoPhrase')) { $('#stGoPhrase').value = keep.go; goBtn(); }
  if (keep.cname != null && $('#stCName')) $('#stCName').value = keep.cname;
  if (keep.cphrase && $('#stCPhrase')) { $('#stCPhrase').value = keep.cphrase; cArmBtn(); }
}

function armBtn() { const b = $('#stArmGo'); if (b) b.disabled = $('#stPhrase')?.value !== P.d?.phrase; }

function goBtn() {
  P.phraseOk = norm($('#stGoPhrase')?.value) === norm(P.d?.phrase);
  const b = $('#stGo');
  if (b && P.d?.local && !P.d?.job?.running) b.disabled = !!P.d?.need_phrase && !P.phraseOk;
}

async function load(fresh = false) {
  try {
    const r = await fetch('/api/next/start/status' + (fresh ? '?fresh=1' : ''));
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status);
    P.d = d; P.offline = 0;
    if (d.blitz?.on) await loadCpf(fresh); else P.cpf = null;
  } catch (e) {
    P.offline += 1;
    if (!P.d) { const el = $('#page-start'); if (el) el.innerHTML = `<div class="card nx-glass cc-card"><div class="pc-empty"><b>Bot server not reachable</b><span>${esc(e.message)}. It may be restarting: this page tries again.</span></div></div>`; }
  }
  autoTick();
  if (!P.busy && !document.activeElement?.closest?.('#page-start input')) draw();
  schedule();
}

function schedule() {
  clearTimeout(P.timer);
  if (!active()) { clearInterval(P.tick); P.tick = null; return; }
  P.timer = setTimeout(load, P.offline || P.d?.job?.running ? 3000 : 10000);
  if (!P.tick) {
    P.tick = setInterval(() => {                     // the retry countdown, then the retry itself
      if (!active()) { clearInterval(P.tick); P.tick = null; return; }
      if (!P.retryAt) return;
      const left = Math.round((P.retryAt - Date.now()) / 1000);
      const el = $('#stRetry');
      if (el) el.textContent = `Trying again in ${Math.max(0, left)} s`;
      if (left <= 0 && !P.busy && SS.get('auto') && P.d?.local && !P.d?.job?.running) {
        P.retryAt = 0;
        act(startGo, 'Trying again');
      }
    }, 1000);
  }
}

async function act(fn, done) {
  if (P.busy) return;
  P.busy = true;
  try { const r = await fn(); toast(r.say || done || 'Done', 4000); P.open = null; }
  catch (e) { toast(e.message, 7000); }
  finally { P.busy = false; await load(); }
}

function wire(el) {
  el.addEventListener('input', (e) => { if (e.target.id === 'stPhrase') armBtn(); if (e.target.id === 'stGoPhrase') goBtn(); if (e.target.id === 'stCPhrase') cArmBtn(); });
  el.addEventListener('click', (e) => {
    const seg = e.target.closest('.st-seg button');
    if (seg) { seg.parentElement.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b === seg)); return; }
    const o = e.target.closest('[data-open]');
    if (o) { P.open = P.open === o.dataset.open ? null : o.dataset.open; draw(); return; }
    const a = e.target.closest('[data-act]');
    if (a && !a.disabled) {
      const k = a.dataset.act;
      if (k === 'names' || k === 'arm') { P.open = P.open === k ? null : k; draw(); if (k === 'arm') $('#stPhrase')?.focus(); return; }
      if (k === 'recheck') { toast('Checking again…'); return load(true); }
      if (k === 'nt') return act(() => post('nt'), 'Opening NinjaTrader: log in, this line turns green by itself');
      if (k === 'setup') return act(() => post('setup'), 'Setup done');
      if (k === 'sims') { if (!confirm('Run the Sim101 test now?\n\nA 1-micro test order on Sim101 (not real money). The dashboard restarts during it (about 2 minutes).')) return; return act(() => post('sims'), 'Sim test started'); }
      if (k === 'stop') { if (!confirm('Stop the bot? (it is running with the wrong set-up)')) return; return act(async () => { const r = await fetch('/api/live/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); return r.json(); }, 'Bot stopped'); }
      return;
    }
    const d = e.target.closest('[data-do]');
    if (d && !d.disabled) {
      const k = d.dataset.do;
      if (k === 'close') { P.open = null; draw(); return; }
      if (k === 'go') { SS.set('tries', null); return act(startGo, 'Starting: the page does every step by itself'); }
      if (k === 'autooff') { SS.set('auto', null); P.retryAt = 0; draw(); return; }
      if (k === 'clock') {
        return act(async () => {
          try { const r = await post('clock'); P.clockMsg = null; return r; }
          catch (err) { P.clockMsg = err.message; throw err; }
        }, 'Clock synced');
      }
      if (k === 'names') return act(() => post('names', { lit: $('#stLit').value, atlas: $('#stAtlas').value }));
      if (k === 'arm') return act(() => post('arm', { confirm: $('#stPhrase').value }), 'Arming and starting: watch the lines');
      if (k === 'cset') return act(() => post('blitz', { name: $('#stCName').value, start: $('#stCStart').value }));
      if (k === 'csim') return act(() => post('blitz', { name: 'Sim101', start: $('#stCStart').value }));
      if (k === 'coff') { if (!confirm('Switch BLITZ\'s own account off? (BLITZ keeps running on paper only)')) return; return act(() => post('blitz', { name: 'off' })); }
      if (k === 'carm') return act(() => post('blitz/arm', { confirm: $('#stCPhrase').value }), 'BLITZ armed');
      if (k === 'anchor') return act(() => post('accounts/anchor', { name: d.dataset.name, balance: $('#stBal').value, floor: $('#stFloor').value, as_of: $('#stAsOf').value }));
      if (k === 'funded') return act(() => post('accounts/funded', { name: d.dataset.name, funded_name: $('#stFName').value, start: $('#stFStart').value }));
      if (k === 'add') {
        const v = (s) => el.querySelector(`.st-seg[data-seg="${s}"] .on`)?.dataset.v;
        return act(() => post('accounts/add', { name: $('#stAName').value, plan: v('plan'), strategy: v('strategy'), start: $('#stAStart').value }));
      }
    }
    const rm = e.target.closest('[data-rm]');
    if (rm && !rm.disabled) {
      if (!confirm(`Remove ${rm.dataset.rm}? The bot stops trading it (nothing in NinjaTrader changes).`)) return;
      act(() => post('accounts/remove', { name: rm.dataset.rm }));
    }
  });
}

export const start = {
  show() {
    const el = $('#page-start');
    if (el && !el.dataset.wired) { el.dataset.wired = '1'; wire(el); wireNewAcct(el); wireSelftest(el); }
    if (!P.d && el) el.innerHTML = '<div class="empty">Loading the start list…</div>';
    load();
  },
};
