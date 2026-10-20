// Live pulse of the PC bot for every page: sound alerts, desktop notifications, live P&L + position in the tab title and a
// favicon badge. One read-only poll: GET /api/next/pc/pulse (engine/pcops_api.py) every 5 s.
//   Sound          Web Audio tones (no sound files) for entry, exit (win / loss), kill switch and FEED STALE. Mute = the top-bar
//                  sound button (#soundBtn, also the M key) = the "Sound" switch in Settings > Alerts on this PC.
//   Notifications  the browser's Notification API, opt-in (Settings > Alerts on this PC asks for permission), same events.
//   Tab            "▼ +$316 SHORT 8 · <page>" while in a trade, "FLAT +$293 · <page>" after one, "KILLED" / "FEED STALE"; the favicon
//                  turns into a coloured badge with an arrow (long / short), a dash (flat), ! (stale) or ■ (kill).
// Each event id fires once per browser tab (the first poll only marks today's history as seen). Nothing here sends orders.
import { $, api, toast } from '../util.js';
import { A, setAppearance } from '../skins.js';

const KEY = 'nx.alerts';
const DEF = { notify: false, title: true, ev: { entry: true, exit: true, kill: true, stale: true } };
function load() { try { const v = JSON.parse(localStorage.getItem(KEY) || 'null'); return v ? { ...DEF, ...v, ev: { ...DEF.ev, ...(v.ev || {}) } } : { ...DEF, ev: { ...DEF.ev } }; } catch { return { ...DEF, ev: { ...DEF.ev } }; } }
function save() { try { localStorage.setItem(KEY, JSON.stringify(P)); } catch { /* private mode */ } }
const P = load();
export const PULSE = { last: null, at: 0, seen: null, log: [], err: null };
const THROTTLE = { stale: 600, fresh: 600 };              // seconds between two sounds / notifications of the same kind
const lastFired = {};

// ------------------------------------------------------------------ sound (Web Audio)
let ctx = null;
function audio() {
  try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === 'suspended') ctx.resume(); } catch { ctx = null; }
  return ctx;
}
// [frequency Hz, seconds, wave, gap]
const TONES = {
  entry: [[523, 0.11, 'sine'], [659, 0.11, 'sine'], [784, 0.2, 'sine']],
  win: [[784, 0.1, 'sine'], [1047, 0.24, 'sine']],
  loss: [[523, 0.12, 'triangle'], [392, 0.26, 'triangle']],
  exit: [[659, 0.12, 'sine'], [523, 0.2, 'sine']],
  kill: [[220, 0.16, 'square'], [0, 0.06], [220, 0.16, 'square'], [0, 0.06], [165, 0.36, 'square']],
  stale: [[880, 0.14, 'triangle'], [0, 0.08], [660, 0.22, 'triangle']],
  fresh: [[660, 0.08, 'sine'], [880, 0.14, 'sine']],
  test: [[659, 0.1, 'sine'], [784, 0.1, 'sine'], [988, 0.18, 'sine']],
};
export function tone(kind, force = false) {
  if (!A.sound && !force) return false;
  const c = audio(); if (!c) return false;
  try {
    let t = c.currentTime + 0.02;
    for (const [f, d, w] of TONES[kind] || TONES.test) {
      if (f) {
        const o = c.createOscillator(), g = c.createGain();
        o.type = w || 'sine'; o.frequency.value = f;
        const peak = w === 'square' ? 0.08 : 0.2;
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(peak, t + 0.015);
        g.gain.exponentialRampToValueAtTime(0.0001, t + d);
        o.connect(g).connect(c.destination);
        o.start(t); o.stop(t + d + 0.03);
      }
      t += d;
    }
    PULSE.log.push({ at: Date.now(), what: 'sound', kind });
    return true;
  } catch { return false; }
}
// browsers only allow audio after a user gesture: unlock on the first click / key
const unlock = () => { if (A.sound) audio(); };
addEventListener('pointerdown', unlock, { once: true, capture: true });
addEventListener('keydown', unlock, { once: true, capture: true });

// ------------------------------------------------------------------ desktop notifications (opt-in)
const canNotify = () => typeof window.Notification === 'function';
export async function enableNotify(on) {
  if (!on) { P.notify = false; save(); return 'off'; }
  if (!canNotify()) { toast('This browser has no desktop notifications'); return 'unsupported'; }
  let perm = Notification.permission;
  if (perm === 'default') { try { perm = await Notification.requestPermission(); } catch { perm = 'denied'; } }
  P.notify = perm === 'granted'; save();
  if (perm === 'denied') toast('Notifications are blocked for this site: allow them in the browser\'s site settings', 5000);
  return perm;
}
function notify(e) {
  if (!P.notify || !canNotify() || Notification.permission !== 'granted') return false;
  try {
    const n = new Notification(e.title, { body: e.text || '', tag: e.id, renotify: false, requireInteraction: e.kind === 'kill', icon: '/icons/icon.svg' });
    n.onclick = () => { try { window.focus(); window.LE?.go?.(e.kind === 'stale' ? 'ntpanel' : 'botctl'); n.close(); } catch { /* closed */ } };
    PULSE.log.push({ at: Date.now(), what: 'notify', kind: e.kind, id: e.id });
    return true;
  } catch { return false; }
}

// ------------------------------------------------------------------ tab title + favicon badge
const usd = (v) => (v == null || Number.isNaN(+v)) ? '' : (v > 0 ? '+' : v < 0 ? '−' : '') + '$' + Math.round(Math.abs(v)).toLocaleString('en-US');
export function titlePrefix(p) {
  if (!p || p.error) return '';
  if (p.kill) return '■ KILLED · ';
  if (p.feed?.stale) return '⚠ FEED STALE · ' + (p.position ? `${p.position.side} ${p.position.qty} ${usd(p.position.unrealized_usd)} · ` : '');
  if (p.position) return `${p.position.side === 'LONG' ? '▲' : '▼'} ${usd(p.position.unrealized_usd) || '$0'} ${p.position.side} ${p.position.qty} · `;
  if (p.realized) return `FLAT ${usd(p.day_pnl)} · `;
  return '';
}
let origIcon = null, prefix = '', titleObs = null;
const BASE_RX = /^(■ KILLED · |⚠ FEED STALE · ([A-Z]+ \d+ [^·]*· )?|[▲▼] [^·]*· |FLAT [^·]*· )/;
function applyTitle() {
  const base = document.title.replace(BASE_RX, '');
  const want = (P.title ? prefix : '') + base;
  if (document.title !== want) document.title = want;
}
function badge(p) {
  const link = document.querySelector('link[rel="icon"]');
  if (!link) return;
  if (origIcon == null) origIcon = link.getAttribute('href');
  if (!P.title || !p || p.error || (!p.position && !p.kill && !p.feed?.stale && !p.realized)) { if (link.getAttribute('href') !== origIcon) link.setAttribute('href', origIcon); return; }
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  const pnl = p.position ? +p.position.unrealized_usd || 0 : +p.day_pnl || 0;
  const col = p.kill ? '#ff5a7a' : p.feed?.stale ? '#f7b955' : pnl > 0 ? '#2ee59d' : pnl < 0 ? '#ff5a7a' : '#8a93a8';
  g.fillStyle = '#10131c'; g.beginPath(); g.roundRect ? g.roundRect(2, 2, 60, 60, 14) : g.rect(2, 2, 60, 60); g.fill();
  g.lineWidth = 6; g.strokeStyle = col; g.beginPath(); g.roundRect ? g.roundRect(5, 5, 54, 54, 12) : g.rect(5, 5, 54, 54); g.stroke();
  g.fillStyle = col; g.textAlign = 'center'; g.textBaseline = 'middle'; g.font = 'bold 34px system-ui, sans-serif';
  if (p.kill) g.fillRect(20, 20, 24, 24);
  else if (p.feed?.stale) g.fillText('!', 32, 34);
  else if (p.position) { g.beginPath(); if (p.position.side === 'LONG') { g.moveTo(32, 14); g.lineTo(50, 44); g.lineTo(14, 44); } else { g.moveTo(32, 50); g.lineTo(50, 20); g.lineTo(14, 20); } g.closePath(); g.fill(); }
  else g.fillRect(16, 29, 32, 7);
  try { link.setAttribute('href', c.toDataURL('image/png')); } catch { /* tainted */ }
}

// ------------------------------------------------------------------ events
function fire(e) {
  if (e.kind in P.ev && !P.ev[e.kind]) return;
  const th = THROTTLE[e.kind];
  const now = Date.now() / 1000;
  if (th && lastFired[e.kind] && now - lastFired[e.kind] < th) return;
  lastFired[e.kind] = now;
  const k = e.kind === 'exit' ? (e.pnl > 0.5 ? 'win' : e.pnl < -0.5 ? 'loss' : 'exit') : e.kind;
  tone(k);
  notify(e);
  if (e.kind !== 'fresh') toast(`${e.title}${e.text ? ' · ' + e.text : ''}`, e.kind === 'kill' ? 8000 : 5000);
  PULSE.log.push({ at: Date.now(), what: 'event', kind: e.kind, id: e.id });
}
const seenKey = () => 'nx.pulse.seen.' + new Date().toISOString().slice(0, 10);
function loadSeen() { try { return new Set(JSON.parse(sessionStorage.getItem(seenKey()) || '[]')); } catch { return null; } }
function saveSeen() { try { sessionStorage.setItem(seenKey(), JSON.stringify([...PULSE.seen].slice(-300))); } catch { /* full */ } }
let prevStale = null, prevKill = null;
function handle(p) {
  const ev = p.events || [];
  if (PULSE.seen == null) {                       // first poll: today's history is already known, nothing rings
    const s = loadSeen();
    PULSE.seen = s || new Set();
    if (!s) ev.forEach((e) => PULSE.seen.add(e.id));
  }
  for (const e of ev) {
    if (PULSE.seen.has(e.id)) continue;
    PULSE.seen.add(e.id);
    fire(e);
  }
  // the flags themselves (a stale feed the log did not mention, a kill from another tab)
  if (prevStale === false && p.feed?.stale) fire({ id: 'flag-stale:' + p.t, kind: 'stale', title: 'FEED STALE: entries blocked', text: p.feed.why || 'NinjaTrader bars are old' });
  if (prevKill === false && p.kill && !ev.some((e) => e.kind === 'kill' && !PULSE.seen.has(e.id))) fire({ id: 'flag-kill:' + p.t, kind: 'kill', title: 'KILL SWITCH is on', text: 'flattened and stopped' });
  prevStale = !!p.feed?.stale; prevKill = !!p.kill;
  saveSeen();
}

export async function pollPulse() {
  try {
    const p = await api('/api/next/pc/pulse');
    PULSE.last = p; PULSE.at = Date.now(); PULSE.err = null;
    if (!p.error) handle(p);
    prefix = titlePrefix(p);
    applyTitle(); badge(p);
    document.dispatchEvent(new CustomEvent('le-pulse', { detail: p }));
  } catch (e) { PULSE.err = e.message; }
  return PULSE.last;
}

// ------------------------------------------------------------------ Settings card
export function alertsCard() {
  const el = document.getElementById('nxAlerts'); if (!el) return;
  const perm = canNotify() ? Notification.permission : 'unsupported';
  const row = (id, label, sub, on, dis = false) => `<label class="nx-switch-row"><span><b>${label}</b><span class="muted small">${sub}</span></span>
    <input type="checkbox" class="nx-switch" id="${id}" ${on ? 'checked' : ''} ${dis ? 'disabled' : ''}></label>`;
  el.innerHTML = row('nxAlSound', 'Sound', 'Tones for entry, exit, kill switch, feed stale (no sound files). Same as the speaker button and the M key.', A.sound) +
    row('nxAlNotify', 'Desktop notifications', perm === 'unsupported' ? 'Not available in this browser' : perm === 'denied' ? 'Blocked: allow notifications for this site in the browser settings' : 'Opt-in: the browser asks once', P.notify && perm === 'granted', perm === 'unsupported') +
    row('nxAlTitle', 'P&L in the tab title + favicon badge', 'Position and live $ in the browser tab while you work in other tabs', P.title) +
    `<div class="op-evsel"><span class="muted small">Alert on</span>${[['entry', 'Entries'], ['exit', 'Exits'], ['kill', 'Kill switch'], ['stale', 'Feed stale']].map(([k, l]) =>
      `<label class="nx-chip link"><input type="checkbox" data-ev="${k}" ${P.ev[k] ? 'checked' : ''}> ${l}</label>`).join('')}</div>
    <div class="op-evsel"><span class="muted small">Test</span>${[['entry', 'Entry'], ['win', 'Exit win'], ['loss', 'Exit loss'], ['kill', 'Kill'], ['stale', 'Stale']].map(([k, l]) =>
      `<button type="button" class="btn ghost sm" data-test="${k}">${l}</button>`).join('')}</div>
    <div class="note">Read-only: alerts watch <span class="mono">/api/next/pc/pulse</span> every 5 s. They never touch the bot. The phone app's push notifications are under Modules &rsaquo; Alerts.</div>`;
  $('#nxAlSound').onchange = (e) => { setAppearance({ sound: e.target.checked }); if (e.target.checked) tone('test', true); };
  $('#nxAlNotify').onchange = async (e) => { const r = await enableNotify(e.target.checked); e.target.checked = r === 'granted'; if (r === 'granted') notify({ id: 'test', kind: 'test', title: 'LIT bot alerts on', text: 'You will see entries, exits, kill and feed stale here.' }); };
  $('#nxAlTitle').onchange = (e) => { P.title = e.target.checked; save(); applyTitle(); badge(PULSE.last); };
  el.querySelectorAll('input[data-ev]').forEach((c) => { c.onchange = () => { P.ev[c.dataset.ev] = c.checked; save(); }; });
  el.querySelectorAll('button[data-test]').forEach((b) => { b.onclick = () => tone(b.dataset.test, true); });
}

export function initPulse() {
  const t = document.querySelector('title');
  if (t && !titleObs) { titleObs = new MutationObserver(() => { if (P.title && prefix && !document.title.startsWith(prefix)) applyTitle(); }); titleObs.observe(t, { childList: true, characterData: true, subtree: true }); }
  document.addEventListener('le-appearance', () => { const s = document.getElementById('nxAlSound'); if (s) s.checked = !!A.sound; });
  alertsCard();
  pollPulse();
  setInterval(pollPulse, 5000);
  window.LE = Object.assign(window.LE || {}, { pulse: PULSE, tone });
}
