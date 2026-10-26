// Start & Accounts (2026-10-26): START BOT (engine/go.py) as one checklist, one button per red line, and the account panel.
// Reads GET /api/next/start/status; every button POSTs to /api/next/start/* (engine/start_api.py), which only answers a
// browser on this PC (the phone sees the same page read-only). Arming needs the owner's typed I ACCEPT LIVE RISK.
import { $, esc, toast } from '../util.js';
import { icon } from './icons.js';

const P = { d: null, timer: null, open: null, busy: false, offline: 0 };
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
  const name = j.step === 'arm' ? 'Arm and start' : 'Sim test';
  const st = j.running ? chip('running', 'warn') : j.rc === 0 ? chip('done', 'good') : chip(j.state === 'done' ? 'stopped (see the lines)' : 'stopped', 'bad');
  return `<div class="card nx-glass cc-card st-job"><div class="card-h"><h3>${esc(name)}</h3><div class="card-tools">${st}</div></div>
    ${j.running ? `<p class="muted">${j.step === 'sims' ? 'The dashboard restarts during the test (about 2 minutes): this page reconnects by itself.' : 'The bot server may restart once: this page reconnects by itself.'}</p>` : ''}
    <pre class="st-log">${esc((j.lines || []).join('\n'))}</pre></div>`;
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
  return `<div class="st-acct ${r.bot === 'ATLAS' ? 'atlas' : 'lit'}"><div class="st-a1">
      <div class="st-aname"><b>${esc(r.name)}</b><span>${chip(r.bot, r.bot === 'ATLAS' ? 'atlas' : 'lit')} ${esc(r.plan_label || r.plan)} ${state} ${armed}</span></div>
      <div class="st-amoney"><span>Balance <b>${usd(r.balance)}</b></span><span>Floor <b>${usd(r.floor)}</b></span><em>${esc(r.source || '')}${r.as_of ? ' · as of ' + esc(r.as_of) : ''}</em></div>
      ${btns}</div>${r.note ? `<p class="st-note">${icon('info')}<span>${esc(r.note)}</span></p>` : ''}${form}</div>`;
}

function addForm(d) {
  if (!d.local) return '';
  const dis = d.running ? 'disabled title="Stop the bot first"' : '';
  return `<div class="st-add"><h4>Add an account</h4><div class="st-grid four">
    <label>NinjaTrader Name<input id="stAName" list="stNames" autocomplete="off" placeholder="exactly as NinjaTrader shows it"></label>
    <label>Plan<span class="st-seg" data-seg="plan"><button type="button" class="on" data-v="builder50k">Builder 50K</button><button type="button" data-v="builder25k">Builder 25K</button></span></label>
    <label>Bot<span class="st-seg" data-seg="strategy"><button type="button" class="on" data-v="zlarior">Zlarior</button><button type="button" data-v="atlas">ATLAS</button></span></label>
    <label>Start day<input id="stAStart" type="date" value="${esc(d.accounts?.today || '')}"></label></div>
    <div class="st-acts"><button type="button" class="btn primary sm" data-do="add" ${dis}>Add</button><span class="muted">Never armed here: arming is the Start list's last step.</span></div></div>`;
}

// ------------------------------------------------------------------ draw
function draw() {
  const el = $('#page-start');
  const d = P.d;
  if (!el || !d) return;
  const keep = { lit: $('#stLit')?.value, atlas: $('#stAtlas')?.value, phrase: $('#stPhrase')?.value, aname: $('#stAName')?.value };
  const n = d.steps.filter((s) => s.done).length;
  const rows = d.accounts?.rows || [];
  el.innerHTML = `<div class="nx-hero cc-hero st-hero"><div><div class="nx-eyebrow">Start &amp; Accounts</div>
      <h2 class="st-say">${esc(d.say)}</h2>
      <p class="muted">${d.all_green ? 'Everything is done. Leave the PC on, plugged in, NinjaTrader open.' : `${n} of ${d.steps.length} done. Do the red lines from the top.`}</p></div>
      <div class="st-side">${d.local ? '' : `<div class="st-ro">${icon('phone')}<span>Read-only here: start and change accounts on the PC itself (http://localhost:8766).</span></div>`}
      ${P.offline ? `<div class="st-ro warn">${icon('refresh')}<span>Reconnecting to the bot server…</span></div>` : ''}</div></div>
    ${picks(d)}
    <div class="st-cols"><div class="card nx-glass cc-card st-list"><div class="card-h"><h3>Start</h3><div class="card-tools">${chip(`${n}/${d.steps.length}`, d.all_green ? 'good' : '')}</div></div>
      ${d.steps.map((s, i) => stepRow(s, d, i === d.steps.findIndex((x) => x.action === P.open && !x.done))).join('')}</div>
      ${jobCard(d.job)}</div>
    <div class="card nx-glass cc-card st-accts"><div class="card-h"><h3>Accounts</h3><div class="card-tools">${d.running ? chip('bot running: stop it to add or remove', 'warn') : ''}</div></div>
      ${rows.length ? rows.map((r) => acctRow(r, d)).join('') : '<div class="pc-empty"><b>No accounts yet</b><span>Add the 50K for Zlarior and the 25K for ATLAS.</span></div>'}
      ${addForm(d)}</div>`;
  if (keep.lit != null && $('#stLit')) $('#stLit').value = keep.lit;
  if (keep.atlas != null && $('#stAtlas')) $('#stAtlas').value = keep.atlas;
  if (keep.phrase && $('#stPhrase')) { $('#stPhrase').value = keep.phrase; armBtn(); }
  if (keep.aname && $('#stAName')) $('#stAName').value = keep.aname;
}

function armBtn() { const b = $('#stArmGo'); if (b) b.disabled = $('#stPhrase')?.value !== P.d?.phrase; }

async function load(fresh = false) {
  try {
    const r = await fetch('/api/next/start/status' + (fresh ? '?fresh=1' : ''));
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status);
    P.d = d; P.offline = 0;
  } catch (e) {
    P.offline += 1;
    if (!P.d) { const el = $('#page-start'); if (el) el.innerHTML = `<div class="card nx-glass cc-card"><div class="pc-empty"><b>Bot server not reachable</b><span>${esc(e.message)}. It may be restarting: this page tries again.</span></div></div>`; }
  }
  if (!P.busy && !document.activeElement?.closest?.('#page-start input')) draw();
  schedule();
}

function schedule() {
  clearTimeout(P.timer);
  if (!active()) return;
  P.timer = setTimeout(load, P.offline || P.d?.job?.running ? 3000 : 10000);
}

async function act(fn, done) {
  if (P.busy) return;
  P.busy = true;
  try { const r = await fn(); toast(r.say || done || 'Done', 4000); P.open = null; }
  catch (e) { toast(e.message, 7000); }
  finally { P.busy = false; await load(); }
}

function wire(el) {
  el.addEventListener('input', (e) => { if (e.target.id === 'stPhrase') armBtn(); });
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
      if (k === 'names') return act(() => post('names', { lit: $('#stLit').value, atlas: $('#stAtlas').value }));
      if (k === 'arm') return act(() => post('arm', { confirm: $('#stPhrase').value }), 'Arming and starting: watch the lines');
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
    if (el && !el.dataset.wired) { el.dataset.wired = '1'; wire(el); }
    if (!P.d && el) el.innerHTML = '<div class="empty">Loading the start list…</div>';
    load();
  },
};
