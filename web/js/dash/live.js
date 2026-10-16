// Live hub: one poller for the paper bot (/api/live/state), the dash overview (/api/dash/overview when deployed), the watchdog
// and the Pine blackout list. New bot log rows become toast notifications (+ the notification centre); sound stays with sound.js.
import { $, esc, etStr } from '../util.js';
import { getJSON, pref, ago } from './kit.js';

export const L = {
  live: null, liveAt: 0, ov: null, wd: null, bo: null, paper: null, lat: [], online: null,
  log: [], dash: false, sse: null, sseOk: false, listeners: new Set(),
};
export const onLive = (fn) => { L.listeners.add(fn); if (L.live || L.ov) try { fn(L); } catch (e) { console.error(e); } };
const emit = () => { for (const f of L.listeners) { try { f(L); } catch (e) { console.error('live listener', e); } } };

// ------------------------------------------------------------------ notifications
const TYPE = {
  sweep: ['◆', 'var(--gold)', 'Liquidity sweep'], signal: ['◎', 'var(--accent)', 'Signal'], entry: ['▶', 'var(--accent)', 'Entry'],
  exit: ['■', 'var(--good)', 'Exit'], order: ['⇄', 'var(--amt)', 'Order'], risk: ['⛨', 'var(--bad)', 'Risk guard'], error: ['!', 'var(--bad)', 'Error'],
  news: ['⚡', 'var(--serious)', 'News'], tradingview: ['⇄', 'var(--accent-2)', 'TradingView'], daily: ['▦', 'var(--accent)', 'Daily report'],
  system: ['⚙', 'var(--muted)', 'System'], warn: ['▲', 'var(--warn)', 'Warning'], skip: ['○', 'var(--muted)', 'Passed'], kill: ['■', 'var(--bad)', 'Kill switch'],
  info: ['i', 'var(--accent)', 'Info'],
};
const TOASTABLE = new Set(['sweep', 'signal', 'entry', 'exit', 'order', 'risk', 'error', 'news', 'tradingview', 'daily', 'kill']);
let notes = pref.get('notes', []);
let unread = pref.get('unread', 0);

export function notify(type, text, { t = Date.now() / 1000, toast = true, life = 7000 } = {}) {
  const [ic, col, label] = TYPE[type] || TYPE.info;
  notes.unshift({ type, text, t });
  notes = notes.slice(0, 120);
  pref.set('notes', notes);
  unread++; pref.set('unread', unread);
  badge();
  if (!toast || pref.get('toasts', true) === false) return;
  let st = $('#nStack');
  if (!st) { st = document.createElement('div'); st.id = 'nStack'; st.setAttribute('aria-live', 'polite'); document.body.appendChild(st); }
  const el = document.createElement('div');
  el.className = 'ntoast';
  el.style.setProperty('--tc', col); el.style.setProperty('--life', life + 'ms');
  el.innerHTML = `<div class="ic">${ic}</div><div><b>${esc(label)}</b><p>${esc(text)}</p><small>${etStr(t)} ET</small></div><button class="x" aria-label="Dismiss">✕</button>`;
  const kill = () => { el.classList.add('out'); setTimeout(() => el.remove(), 260); };
  el.querySelector('.x').onclick = kill;
  el.onclick = (e) => { if (!e.target.closest('.x')) { kill(); openCenter(); } };
  st.prepend(el);
  while (st.children.length > 4) st.lastElementChild.remove();
  setTimeout(kill, life);
}
function badge() { const b = $('#bellBadge'); if (b) b.textContent = unread ? String(Math.min(99, unread)) : ''; }

export function openCenter() {
  unread = 0; pref.set('unread', 0); badge();
  let dr = $('#nCenter');
  if (!dr) { dr = document.createElement('aside'); dr.id = 'nCenter'; dr.className = 'w-drawer'; document.body.appendChild(dr); }
  const draw = () => {
    dr.innerHTML = `<div class="wd-h"><b>Notifications</b><div class="row gap"><button class="btn ghost sm" id="ncToasts">${pref.get('toasts', true) === false ? 'Pop-ups off' : 'Pop-ups on'}</button><button class="btn ghost sm" id="ncClear">Clear</button><button class="btn ghost sm" id="ncClose">✕</button></div></div>
      <div class="muted small" style="margin:0 0 10px">Paper-bot events as they happen (sweeps, signals, entries, exits, risk, news). Sound alerts follow the 🔔 button.</div>
      <div class="n-list">${notes.length ? notes.map(n => { const [, col, label] = TYPE[n.type] || TYPE.info;
        return `<div class="n-item" style="--tc:${col}"><i></i><div><b>${esc(label)}</b><p>${esc(n.text)}</p><small>${etStr(n.t, true)} ET · ${ago(Date.now() / 1000 - n.t)}</small></div></div>`; }).join('')
        : '<div class="empty">No notifications yet. They appear here as the paper bot logs events.</div>'}</div>`;
    $('#ncClose', dr).onclick = () => dr.classList.remove('on');
    $('#ncClear', dr).onclick = () => { notes = []; pref.set('notes', []); draw(); };
    $('#ncToasts', dr).onclick = () => { pref.set('toasts', pref.get('toasts', true) === false); draw(); };
  };
  draw();
  dr.classList.add('on');
}

// ------------------------------------------------------------------ log diffing (poll fallback when the SSE stream is not live)
const seen = new Set();
let primed = false;
function ingest(rows, { fromStream = false } = {}) {
  const fresh = [];
  for (const r of rows) {
    const k = `${r.t}|${r.type}|${r.text}`;
    if (seen.has(k)) continue;
    seen.add(k);
    fresh.push(r);
  }
  if (!primed && !fromStream) { primed = true; return; }   // the first snapshot is history, not news
  for (const r of fresh.sort((a, b) => a.t - b.t)) {
    if (Date.now() / 1000 - r.t > 900) continue;              // never toast anything older than 15 minutes
    const sysHot = r.type === 'system' && /kill|stopp|resum|start|crash|restart/i.test(r.text);
    if (TOASTABLE.has(r.type) || sysHot) notify(r.type, r.text, { t: r.t });
    else notify(r.type, r.text, { t: r.t, toast: false });
  }
}

// ------------------------------------------------------------------ polling
async function pollLive() {
  const t0 = performance.now();
  const s = await getJSON('/api/live/state', { ttl: 0 });
  const ms = performance.now() - t0;
  L.lat.push({ t: Date.now() / 1000, ms: s ? ms : null }); if (L.lat.length > 90) L.lat.shift();
  L.online = !!s;
  if (s) {
    L.live = s; L.liveAt = Date.now() / 1000;
    L.log = s.log || [];
    if (!L.sseOk) ingest(L.log);
  }
  emit();
}
async function pollOverview() {
  const o = await getJSON('/api/dash/overview', { ttl: 0 });
  L.ov = o && o.status !== 'computing' ? o : L.ov;
  L.dash = !!o;
  if (o && !L.sse) startStream();
  emit();
}
async function pollSlow() {
  const [wd, bo] = await Promise.all([getJSON('/api/health/watchdog', { ttl: 0 }), getJSON('/api/launch/blackouts', { ttl: 300000 })]);
  L.wd = wd; L.bo = bo;
  // fallback for the week count while /api/dash/overview is not deployed: paper rows from the trade memory
  if (!L.dash) L.paper = await getJSON('/api/memory/trades?source=paper&limit=200', { ttl: 60000 });
  emit();
}

// Server-Sent Events from /api/dash/stream (contract 18b). Falls back to polling on any error and retries later.
function startStream() {
  if (!('EventSource' in window) || L.sse) return;
  try {
    const es = new EventSource('/api/dash/stream');
    L.sse = es;
    es.addEventListener('log', (e) => { try { L.sseOk = true; ingest([JSON.parse(e.data)], { fromStream: true }); } catch { } });
    es.addEventListener('tick', (e) => { try { L.sseOk = true; L.tick = JSON.parse(e.data); emit(); } catch { } });
    es.onerror = () => { es.close(); L.sse = null; L.sseOk = false; setTimeout(() => { if (L.dash) startStream(); }, 60000); };
  } catch { L.sse = null; }
}

let started = false;
export function startLive() {
  if (started) return; started = true;
  badge();
  const every = (fn, ms) => { fn(); setInterval(() => { if (!document.hidden) fn(); }, ms); };
  every(pollLive, 10000);
  every(pollOverview, 15000);
  every(pollSlow, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { pollLive(); pollOverview(); } });
}
