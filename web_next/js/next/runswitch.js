// The Run / Stop switch (owner 2026-10-27: "a simple stop and run switch on the dashboard"): one big button at the top of
// every page of the PC dashboard. It is the only start control the owner needs; the Start page and Bot Control keep their
// detail views.
//   RUNNING   green  "Trading: Zlarior 50K + ATLAS 25K"      tap = Stop
//   STOPPED   grey   "Stopped"                               tap = Run
//   STARTING  amber  the running job's one-line say          (no tap while the steps run)
//   NEEDS YOU red    one plain sentence of what to do         tap = Run again
// Run  = POST /api/next/start/go (engine/start_api.r_go -> engine/go.step_auto: update, NinjaTrader, live bars, Sim test
//        once, start without the phrase when the auto-resume opt-in is valid). When status.need_phrase is true a dialog
//        asks the owner to type I ACCEPT LIVE RISK; it is sent once in the POST body, the field cleared and the dialog
//        removed at once: never kept in a variable, never in localStorage / sessionStorage, never shown, never prefilled.
// Stop = POST /api/live/stop (clears data/autostart.json: a reboot does not resume; the auto-resume opt-in stays, so the
//        next Run needs no phrase). The switch never calls /api/live/kill (HOLD TO KILL stays on Bot Control).
// The writes answer only a browser on this PC (engine/cloud_guard.local_only); off the PC (phone on the LAN, Tailscale)
// status.local is false and the switch is a read-only "PC: running / stopped" pill.
// Polls GET /api/next/start/status every 3 s while starting, else every 15 s.
import { esc, toast } from '../util.js';
import { icon } from './icons.js';

const R = { d: null, timer: null, tick: null, busy: false, offline: 0, retryAt: 0 };
const FAST_MS = 3000, SLOW_MS = 15000, MAX_TRIES = 30, FRESH_S = 2 * 3600;
const RUNNING_TEXT = 'Trading: Zlarior 50K + ATLAS 25K';
// shared with the Start page (start.js): the owner pressed Run in this tab, so a stop with retry_s is retried by itself
const SS = { get: (k) => { try { return sessionStorage.getItem('st.' + k); } catch { return null; } },
  set: (k, v) => { try { if (v == null) sessionStorage.removeItem('st.' + k); else sessionStorage.setItem('st.' + k, String(v)); } catch { /* private mode */ } } };
const startPageOpen = () => document.getElementById('page-start')?.classList.contains('active');

// ------------------------------------------------------------------ the state (pure: tests/test_run_switch.py runs it in node)
export function swState(d, nowS = Date.now() / 1000, pressed = false) {
  if (!d || d.error) return { k: 'offline', label: 'Bot server not reachable', sub: 'reconnecting…', can: null };
  const j = d.job || {};
  const auto = j.step === 'auto';
  const runStep = (d.steps || []).find((s) => s.key === 'running');
  if (j.running) return { k: 'starting', label: 'Starting…', sub: (auto && j.say) || 'working on the steps', can: null };
  if (d.running) {
    if (runStep && runStep.done === false) {
      return { k: 'need', label: 'Needs you', sub: 'The bot runs with the wrong set-up: press Stop, then Run.', can: 'stop' };
    }
    return { k: 'running', label: RUNNING_TEXT, sub: 'tap to stop', can: 'stop' };
  }
  const failed = auto && j.rc != null && j.rc !== 0;
  const fresh = pressed || (j.t1 && nowS - j.t1 < FRESH_S);
  if (failed && fresh && (j.need || j.retry_s || j.say)) {
    return { k: 'need', label: 'Needs you', sub: j.say || 'Open the Start page to see what stopped.', can: 'run', retry_s: j.retry_s || null, need: j.need || null };
  }
  return { k: 'stopped', label: 'Stopped', sub: d.need_phrase ? 'Run: type the phrase once' : 'tap Run to start trading', can: 'run' };
}

// ------------------------------------------------------------------ draw
function html(d) {
  const s = swState(d, Date.now() / 1000, !!SS.get('auto'));
  if (d && !d.error && !d.local) {               // off the PC: read only
    const on = s.k === 'running';
    return `<div class="rsw ro ${on ? 'running' : 'stopped'}" title="Start and stop on the PC itself (http://localhost:8766)">
      <span class="rsw-dot"></span><span class="rsw-t"><b>PC: ${on ? 'running' : s.k === 'starting' ? 'starting' : 'stopped'}</b></span></div>`;
  }
  const wait = R.retryAt ? Math.max(0, Math.round((R.retryAt - Date.now()) / 1000)) : 0;
  const sub = s.k === 'need' && R.retryAt ? `${s.sub} Trying again in ${wait} s.` : s.sub;
  const verb = s.can === 'stop' ? 'Stop' : s.can === 'run' ? 'Run' : '';
  const ico = s.can === 'stop' ? icon('stop') : s.can === 'run' ? icon('play') : '<i class="rsw-spin"></i>';
  return `<button type="button" class="rsw ${s.k}" id="runSwBtn" data-can="${esc(s.can || '')}" ${s.can && !R.busy ? '' : 'disabled'}
      aria-label="${esc(verb ? verb + ': ' : '')}${esc(s.label)}" title="${esc(sub)}">
    <span class="rsw-knob">${ico}</span>
    <span class="rsw-t"><b>${esc(s.label)}</b><em id="runSwSub">${esc(sub)}</em></span>
    ${verb ? `<span class="rsw-verb">${verb}</span>` : ''}</button>`;
}

function draw() {
  const el = document.getElementById('runSw'); if (!el) return;
  const h = html(R.d);
  if (el._h === h) return;
  el._h = h;
  el.innerHTML = h;
  const b = el.querySelector('#runSwBtn');
  if (b) b.onclick = () => (b.dataset.can === 'stop' ? stop() : b.dataset.can === 'run' ? run() : null);
}

// ------------------------------------------------------------------ the phrase dialog (memory of the DOM only, cleared at once)
function askPhrase() {
  return new Promise((resolve) => {
    const m = document.createElement('div');
    m.className = 'bc-modal';
    m.innerHTML = `<form class="bc-dlg" autocomplete="off" role="dialog" aria-modal="true" aria-label="Start on the real accounts">
      <div class="bc-dlg-h">${icon('warn')}<b>Start on the real accounts</b></div>
      <p>Zlarior trades the 50K and ATLAS the 25K: <b>real money</b>. Type <b class="mono">I ACCEPT LIVE RISK</b> (capitals do not matter).
        It is sent once and never saved or shown. After this once, Run needs no phrase and the bot comes back by itself after a restart.</p>
      <input type="password" name="rswp" autocomplete="off" autocapitalize="off" spellcheck="false" data-lpignore="true" placeholder="type the phrase" class="inp" aria-label="confirm phrase">
      <div class="bc-dlg-a"><button type="button" class="btn ghost" data-x>Cancel</button><button type="submit" class="btn danger">Run</button></div></form>`;
    document.body.appendChild(m);
    const f = m.querySelector('form'), inp = f.querySelector('input[name=rswp]');
    const done = (v) => { inp.value = ''; m.remove(); resolve(v); };
    f.onsubmit = (e) => { e.preventDefault(); done(inp.value ? { phrase: inp.value } : null); };
    f.querySelector('[data-x]').onclick = () => done(null);
    m.onclick = (e) => { if (e.target === m) done(null); };
    m.onkeydown = (e) => { if (e.key === 'Escape') done(null); };
    setTimeout(() => inp.focus(), 30);
  });
}

// ------------------------------------------------------------------ actions
async function postJSON(path, body) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.ok === false) throw new Error(d.error || 'HTTP ' + r.status);
  return d;
}

// Run: the one flow (POST /api/next/start/go). retry = the switch's own retry of a stop with retry_s (no dialog then).
export async function run(retry = false) {
  if (R.busy) return;
  const d = R.d || {};
  if (!d.local) { toast('Run works only on the PC itself (http://localhost:8766)', 5000); return; }
  R.busy = true; draw();
  try {
    let body = '{}';
    if (d.need_phrase && !d.running) {
      if (retry) { SS.set('auto', null); return; }   // never re-send a phrase: the owner presses Run again
      const a = await askPhrase();
      if (!a) return;
      body = JSON.stringify({ confirm: a.phrase });
      a.phrase = '';
    }
    SS.set('auto', 1);
    SS.set('tries', retry ? +(SS.get('tries') || 0) + 1 : 1);
    R.retryAt = 0;
    let r;
    try { r = await postJSON('/api/next/start/go', body); }
    finally { body = null; }
    toast(retry ? 'Trying again' : (r.say || 'Starting: every step runs by itself'), 4000);
  } catch (e) { toast('Not started: ' + e.message, 7000); }
  finally { R.busy = false; load(); }
}

export async function stop() {
  if (R.busy) return;
  if (!window.confirm('Stop trading? It stays stopped (also after a restart) until you press Run.')) return;
  R.busy = true; draw();
  try {
    SS.set('auto', null); SS.set('tries', null); R.retryAt = 0;
    const r = await postJSON('/api/live/stop', '{}');
    toast(r.ok === false ? 'Stop failed: ' + r.error : 'Stopped. It stays stopped until you press Run.', 5000);
  } catch (e) { toast('Stop failed: ' + e.message, 7000); }
  finally { R.busy = false; load(); }
}

// a stop the server can retry (retry_s) is retried while this tab is open and the owner pressed Run (as the Start page does)
function autoTick() {
  const d = R.d, j = d?.job || {};
  if (!d || !SS.get('auto')) { R.retryAt = 0; return; }
  if (d.running || (j.step === 'auto' && !j.running && j.rc === 0) || ['names', 'phrase', 'stop'].includes(j.need)) {
    SS.set('auto', null); SS.set('tries', null); R.retryAt = 0; return;
  }
  if (j.running || !(j.step === 'auto' && j.rc) || !j.retry_s || +(SS.get('tries') || 0) >= MAX_TRIES) { R.retryAt = 0; return; }
  R.retryAt = Math.max((j.t1 || Date.now() / 1000) * 1000 + j.retry_s * 1000, Date.now() + 2000);
}

async function load() {
  clearTimeout(R.timer);
  try {
    const r = await fetch('/api/next/start/status');
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status);
    R.d = d; R.offline = 0;
  } catch (e) {
    R.offline += 1;
    if (R.offline > 1 || !R.d) R.d = { error: e.message };
  }
  autoTick();
  draw();
  const fast = R.offline || R.d?.job?.running || R.busy;
  R.timer = setTimeout(load, fast ? FAST_MS : SLOW_MS);
}

export function refreshSwitch() { load(); }

export function initRunSwitch() {
  const tb = document.querySelector('.nx-top .tb-right'); if (!tb || document.getElementById('runSw')) return;
  const el = document.createElement('div');
  el.id = 'runSw'; el.className = 'rsw-wrap';
  tb.parentElement.insertBefore(el, tb);         // in the shared top bar, just left of its buttons (own row on a phone)
  el.innerHTML = '<div class="rsw offline"><span class="rsw-knob"><i class="rsw-spin"></i></span><span class="rsw-t"><b>Checking the bot…</b></span></div>';
  window.LE = window.LE || {};
  window.LE.runSwitch = { run: () => run(false), stop, refresh: refreshSwitch };
  load();
  R.tick = setInterval(() => {                     // the retry countdown, then the retry itself
    if (!R.retryAt || document.hidden) return;
    const left = Math.round((R.retryAt - Date.now()) / 1000);
    const sub = document.getElementById('runSwSub');
    if (sub && left > 0) { const s = swState(R.d, Date.now() / 1000, true); sub.textContent = `${s.sub} Trying again in ${left} s.`; }
    if (left <= 0 && !R.busy && R.d?.local && !R.d?.job?.running && !startPageOpen()) { R.retryAt = 0; run(true); }
  }, 1000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
}
