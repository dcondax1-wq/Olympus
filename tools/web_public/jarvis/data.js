// Jarvis data facade (ES module, no imports, no DOM): the one place that reads everything Jarvis shows or answers from.
//   getFacts() -> { now, market: {open, text, rth, session}, live, kalshi, kalshiState, kalshiRun, planner, apps }
//   refreshLive(), refreshKalshi() -> Promise (an in-flight call is shared) · refresh({ maxAge }) refreshes what is older
//   onChange(fn) -> off()   fn({ source: 'live' | 'kalshi' | 'planner' | 'apps' }) · the same 'change' event on `events`
//   setAppsSource(mod)      the apps list getFacts() reports (apps.js when it loaded, else fallbackApps below)
// Sources (read-only; nothing here ever writes to a bot):
//   live.json   the NQ bots (the PC's heartbeat publish, branch `live` of nq-dashboard): the GitHub API first (fresh), then
//               raw.githubusercontent (GitHub's CDN keeps it ~5 min); after a 403 / 429 the API rests 15 min.
//   kalshi.json the PC's Kalshi status (branch `kalshi`, engine/kalshi_publish.py): raw first, then the API; 404 = 'waiting'.
//   Planner     localStorage 'planner.today.v1' {day, events, tasks} when it is today's, else today computed from what the
//               Planner saved on this phone ('planner.v1' / 'planner.hosted.v1').
//   the market  CME NQ: Sunday 18:00 to Friday 17:00 ET, daily halt 17:00-18:00 (exchange holidays are not known here).

export const OWNER = 'demetrades2000-coder';
export const REPO = 'nq-dashboard';
export const URLS = {
  liveApi: `https://api.github.com/repos/${OWNER}/${REPO}/contents/live.json?ref=live`,
  liveRaw: `https://raw.githubusercontent.com/${OWNER}/${REPO}/live/live.json`,
  kalshiRaw: `https://raw.githubusercontent.com/${OWNER}/${REPO}/kalshi/kalshi.json`,
  kalshiApi: `https://api.github.com/repos/${OWNER}/${REPO}/contents/kalshi.json?ref=kalshi`,
};
const FETCH_MS = 9000;

// ------------------------------------------------------------------------------------------------ small helpers
export const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* private mode: nothing kept */ } },
  del(k) { try { localStorage.removeItem(k); } catch (_) { /* nothing kept */ } },
};
export const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const okUrl = (u) => { try { const x = new URL(u, location.href); return /^https?:$/.test(x.protocol) ? x.href : null; } catch (_) { return null; } };
export const sameSite = (u) => { try { return new URL(u, location.href).origin === location.origin; } catch (_) { return false; } };
export const usd = (v, sign) => (v == null || !Number.isFinite(+v)) ? '—' : (sign && +v > 0 ? '+' : (+v < 0 ? '−' : '')) + '$' + Math.abs(Math.round(+v)).toLocaleString('en-US');
export const usd2 = (v, sign) => {
  if (v == null || !Number.isFinite(+v)) return '—';
  const x = +v, a = Math.abs(x);
  return (sign && x > 0 ? '+' : x < 0 ? '−' : '') + '$' + a.toLocaleString('en-US', { minimumFractionDigits: a < 1000 ? 2 : 0, maximumFractionDigits: a < 1000 ? 2 : 0 });
};
export const ago = (t) => { if (!t) return ''; const s = Math.max(0, Date.now() / 1000 - +t); return s < 90 ? 'just now' : s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' d ago'; };
export const hm = (s) => { if (!s) return ''; const [h, m] = String(s).split(':').map(Number); if (!Number.isFinite(h)) return ''; return `${((h + 11) % 12) + 1}:${String(m || 0).padStart(2, '0')}${h < 12 ? ' AM' : ' PM'}`; };

async function get(url, opts) {                  // fetch with a time limit (a phone on a bad signal can hang for minutes)
  const ac = typeof AbortController === 'function' ? new AbortController() : null;
  const t = ac ? setTimeout(() => ac.abort(), FETCH_MS) : 0;
  try { return await fetch(url, ac ? { ...opts, signal: ac.signal } : opts); } finally { clearTimeout(t); }
}

// ------------------------------------------------------------------------------------------------ change events
export const events = new EventTarget();
function emit(source) { try { events.dispatchEvent(new CustomEvent('change', { detail: { source } })); } catch (_) { /* old browser */ } }
export function onChange(fn) {
  const h = (e) => { try { fn(e.detail || {}); } catch (_) { /* a listener's error stays its own */ } };
  events.addEventListener('change', h);
  return () => events.removeEventListener('change', h);
}

// ------------------------------------------------------------------------------------------------ time and the market
export function etParts(d = new Date()) {
  const p = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: 'numeric', hour12: false, month: 'short', day: 'numeric' }).formatToParts(d);
  const g = (k) => (p.find((x) => x.type === k) || {}).value;
  return { wd: g('weekday'), h: +g('hour') % 24, m: +g('minute'), mon: g('month'), day: g('day') };
}
export function market(d = new Date()) {
  const { wd, h, m } = etParts(d), t = h * 60 + m;
  const open = wd === 'Sat' ? false : wd === 'Sun' ? t >= 1080 : wd === 'Fri' ? t < 1020 : !(t >= 1020 && t < 1080);
  if (open) {
    const rth = !['Sat', 'Sun'].includes(wd) && t >= 570 && t < 960;
    return { open: true, rth, session: rth ? 'regular' : 'overnight', text: rth ? 'NQ market open · regular session' : 'NQ market open · overnight session' };
  }
  const when = wd === 'Fri' || wd === 'Sat' || (wd === 'Sun' && t < 1080) ? 'Sunday 6:00 PM ET' : 'today 6:00 PM ET';
  return { open: false, rth: false, session: 'closed', text: `NQ market closed · opens ${when}` };
}
export function greeting(d = new Date()) {
  const { h } = etParts(d);
  return h < 5 ? 'Late night' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}
export const clock = (d = new Date()) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }).format(d);
export const ymd = (d = new Date()) => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
export function whenLine(d = new Date()) {
  const { wd, mon, day } = etParts(d);
  return `${wd} ${mon} ${day} · ${clock(d)} ET · ${market(d).text}`;
}

// ------------------------------------------------------------------------------------------------ live.json: the NQ bots
const L = { j: null, at: 0, okAt: 0, err: null, busy: null, apiUntil: 0 };
function slim(j) {                          // what Jarvis needs, also kept for an offline start
  const b = (j && j.board) || {};
  // BLITZ: the board's card while account C is on, else live.json's own "blitz" (an "off" card while account C is off)
  const bz = b.blitz && !b.blitz.error ? b.blitz : j && j.blitz && !j.blitz.error ? j.blitz : null;
  return { lit: b.lit || null, atlas: b.atlas || null, blitz: bz, verdict: (j && j.pc_verdict) || null, running: b.running, t: j && j.t };
}
export function refreshLive() {
  if (L.busy) return L.busy;
  L.busy = (async () => {
    try {
      let j = null;
      if (Date.now() > L.apiUntil) {
        try {
          const r = await get(URLS.liveApi, { cache: 'no-cache', headers: { Accept: 'application/vnd.github.raw+json' } });
          if (r.ok) j = await r.json(); else if (r.status === 403 || r.status === 429) L.apiUntil = Date.now() + 15 * 60e3;
        } catch (_) { /* fall back to raw */ }
      }
      if (!j) { const r = await get(URLS.liveRaw + '?t=' + Math.floor(Date.now() / 60000), { cache: 'no-cache' }); if (r.ok) j = await r.json(); else throw new Error('live feed ' + r.status); }
      if (j && typeof j === 'object' && (!L.j || (+j.t || 0) >= (+L.j.t || 0))) { L.j = j; L.okAt = Date.now(); L.err = null; LS.set('jarvis.lastLive', { t: j.t, board: slim(j) }); }
    } catch (e) { L.err = String((e && e.message) || e); }
    L.at = Date.now(); L.busy = null;
    emit('live');
  })();
  return L.busy;
}
export function liveView() {                // today's numbers, or the last ones this phone saw (marked cached)
  if (L.j) return { ...slim(L.j), raw: L.j, err: L.err };
  const c = LS.get('jarvis.lastLive', null);
  return c && c.board ? { ...c.board, cached: true, raw: null, err: L.err } : null;
}
export const liveError = () => L.err;
export const liveLoading = () => !!L.busy;

// ------------------------------------------------------------------------------------------------ kalshi.json: the PC's Kalshi bot
const K = { j: null, at: 0, state: '', busy: null };      // state: '' not asked yet | ok | waiting (not published yet) | error
export function refreshKalshi() {
  if (K.busy) return K.busy;
  K.busy = (async () => {
    try {
      let r = null;
      try { r = await get(URLS.kalshiRaw + '?t=' + Math.floor(Date.now() / 60000), { cache: 'no-cache' }); } catch (_) { r = null; }
      if (!r || (!r.ok && r.status !== 404)) { try { r = await get(URLS.kalshiApi, { cache: 'no-cache', headers: { Accept: 'application/vnd.github.raw+json' } }); } catch (_) { r = null; } }
      if (r && r.ok) { const j = await r.json(); if (j && typeof j === 'object') { K.j = j; K.state = 'ok'; LS.set('jarvis.lastKalshi', j); } else K.state = 'error'; }
      else K.state = r && r.status === 404 ? 'waiting' : 'error';
    } catch (_) { K.state = 'error'; }
    K.at = Date.now(); K.busy = null;
    emit('kalshi');
  })();
  return K.busy;
}
export const kalshiView = () => K.j || (K.state === 'waiting' ? null : LS.get('jarvis.lastKalshi', null));
export const kalshiState = () => K.state;
export const kalshiLoading = () => !!K.busy;
// [level, label] of the Kalshi bot: stopped, running (updated in the last 15 min) or not updating
export const kalshiRun = (k) => (!k ? null : k.running === false ? ['bad', 'Stopped'] : k.t && Date.now() / 1000 - k.t < 15 * 60 ? ['ok', 'Running'] : ['warn', 'Not updating']);

// ------------------------------------------------------------------------------------------------ the Planner's day
function plannerState() {
  for (const k of ['planner.v1', 'planner.hosted.v1']) { const s = LS.get(k, null); if (s && (Array.isArray(s.events) || Array.isArray(s.tasks))) return s; }
  return null;
}
export function occursOn(e, day) {
  if (!e || !e.date) return false;
  if (Array.isArray(e.ex) && e.ex.includes(day)) return false;
  if (e.date === day) return true;
  if (!e.repeat || e.repeat === 'none' || day < e.date || (e.until && day > e.until)) return false;
  const a = new Date(e.date + 'T12:00:00Z'), b = new Date(day + 'T12:00:00Z'), dd = Math.round((b - a) / 864e5), wd = b.getUTCDay();
  switch (e.repeat) {
    case 'daily': return true;
    case 'weekdays': return wd >= 1 && wd <= 5;
    case 'weekly': return dd % 7 === 0;
    case 'biweekly': return dd % 14 === 0;
    case 'monthly': return a.getUTCDate() === b.getUTCDate();
    case 'yearly': return a.getUTCDate() === b.getUTCDate() && a.getUTCMonth() === b.getUTCMonth();
    default: return false;
  }
}
const hhmm = (s) => { const m = /(\d{1,2}):(\d{2})/.exec(String(s || '')); return m ? `${m[1].padStart(2, '0')}:${m[2]}` : ''; };
const byStart = (x, y) => (x.allDay ? -1 : 0) - (y.allDay ? -1 : 0) || String(x.start || '').localeCompare(String(y.start || ''));
export function plannerDay(d = new Date()) {
  const day = ymd(d);
  // 1. the Planner's own summary of today (written by the Planner on this phone), when it is today's
  const t = LS.get('planner.today.v1', null);
  if (t && t.day === day && (Array.isArray(t.events) || Array.isArray(t.tasks))) {
    const ev = (t.events || []).filter((e) => e && (e.title || e.name)).map((e) => ({ ...e, title: e.title || e.name, start: hhmm(e.start || e.time), allDay: !!e.allDay || !(e.start || e.time) })).sort(byStart);
    const tasks = (t.tasks || []).filter((x) => x && !x.done && (x.title || x.name)).map((x) => ({ ...x, title: x.title || x.name }));
    return { day, ev, tasks, projects: Array.isArray(t.projects) ? t.projects.filter((p) => p && p.name) : [], source: 'planner.today.v1' };
  }
  // 2. computed from what the Planner saved here
  const S = plannerState();
  if (!S) return null;
  const ev = (S.events || []).filter((e) => occursOn(e, day)).sort(byStart);
  const tasks = (S.tasks || []).filter((x) => x && !x.done && x.date && x.date <= day);
  const projects = (S.projects || []).filter((p) => p && p.name);
  return { day, ev, tasks, projects, source: 'planner' };
}

// ------------------------------------------------------------------------------------------------ the apps (fallback for apps.js)
export const KALSHI_URL = '../kalshi/';   // the Kalshi page (tools/web_public/kalshi/): the PC's kalshi.json
export const BUILT_IN = [
  { id: 'zenith', name: 'Zenith', sub: 'NQ bots · Zlarior · ATLAS · BLITZ', url: '../', icon: '../icons/icon-192.png?v=p111030', builtIn: true },
  { id: 'planner', name: 'Planner', sub: 'Calendar, tasks and projects', url: '../planner/', icon: '../planner/icon-192.png', builtIn: true },
  { id: 'kalshi', name: 'Kalshi', sub: 'Kalshi bot · from your PC', url: KALSHI_URL, glyph: 'K', builtIn: true },
];
// The same calls as apps.js: listApps(), addApp({name, url}), removeApp(id), appStatus(app). Kept on this phone:
// 'jarvis.extra' (added dashboards) and 'jarvis.links' (a pasted link for a built-in one without its own).
export const fallbackApps = {
  fallback: true,
  listApps() {
    const links = LS.get('jarvis.links', {}) || {};
    const extra = LS.get('jarvis.extra', []);
    const out = BUILT_IN.map((a) => ({ ...a, url: a.url || links[a.id] || '' }));
    for (const x of Array.isArray(extra) ? extra : []) if (x && x.id && x.name && okUrl(x.url)) out.push({ id: x.id, name: x.name, url: x.url, glyph: x.name[0], extra: true });
    return out;
  },
  addApp({ name, url }) {
    name = String(name || '').trim().slice(0, 24); url = okUrl(String(url || '').trim());
    if (!name) throw new Error('Give it a name.');
    if (!url) throw new Error('Paste a full link that starts with https://');
    const pre = BUILT_IN.find((b) => b.name.toLowerCase() === name.toLowerCase() && !b.url);
    if (pre) { const l = LS.get('jarvis.links', {}) || {}; l[pre.id] = url; LS.set('jarvis.links', l); emit('apps'); return { ...pre, url }; }
    const id = 'x-' + (name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 20) || 'app');
    LS.set('jarvis.extra', [...(LS.get('jarvis.extra', []) || []).filter((x) => x && x.id !== id), { id, name, url }]);
    emit('apps');
    return { id, name, url, glyph: name[0], extra: true };
  },
  removeApp(id) {
    const l = LS.get('jarvis.links', {}) || {};
    if (l[id]) { delete l[id]; LS.set('jarvis.links', l); }
    LS.set('jarvis.extra', (LS.get('jarvis.extra', []) || []).filter((x) => x && x.id !== id));
    emit('apps');
  },
  setLink(id, url) {
    const u = okUrl(url); if (!u) return false;
    const l = LS.get('jarvis.links', {}) || {}; l[id] = u; LS.set('jarvis.links', l); emit('apps'); return true;
  },
  async appStatus() { return null; },     // the built-in cards come from getFacts(); an added link has no status feed
};
let appsSrc = fallbackApps, appsCache = null;
export function setAppsSource(mod) { appsSrc = mod && typeof mod.listApps === 'function' ? mod : fallbackApps; appsCache = null; emit('apps'); }
export const appsSource = () => appsSrc;
export function listApps() {
  let r = null;
  try { r = appsSrc.listApps(); } catch (_) { r = null; }
  if (r && typeof r.then === 'function') {        // an async list: answer with the last one, update when it lands
    r.then((x) => { if (Array.isArray(x)) { appsCache = x; emit('apps'); } }).catch(() => null);
    r = appsCache;
  }
  if (!Array.isArray(r)) r = appsSrc === fallbackApps ? [] : fallbackApps.listApps();
  else appsCache = r;
  return r.filter((a) => a && a.id && a.id !== 'home' && a.id !== 'jarvis');
}

// ------------------------------------------------------------------------------------------------ the facts
export function getFacts() {
  const now = new Date(), k = kalshiView();
  return {
    now,
    market: market(now),
    live: liveView(),
    liveError: L.err,
    kalshi: k,
    kalshiState: K.state,
    kalshiRun: kalshiRun(k),
    planner: plannerDay(now),
    apps: listApps(),
  };
}
export function refresh({ maxAge = 50e3 } = {}) {
  const jobs = [];
  if (Date.now() - L.at > maxAge) jobs.push(refreshLive());
  if (Date.now() - K.at > maxAge) jobs.push(refreshKalshi());
  return Promise.all(jobs).then(() => getFacts());
}
// the Planner saves in another frame of this site: its writes reach Jarvis as storage events
if (typeof window !== 'undefined') window.addEventListener('storage', (e) => { if (/^planner\./.test(e.key || '')) emit('planner'); else if (/^jarvis\.(extra|links)$/.test(e.key || '')) emit('apps'); });
