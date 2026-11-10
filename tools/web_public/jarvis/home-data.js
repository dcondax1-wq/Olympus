// Jarvis home, the data (2026-11-10): ONE small adapter between the AGORA home cards (home-cards.js) and everything the home shows.
// It reads what Jarvis already has (window.__jarvis.facts() = data.js getFacts(), bots.js snapshot) and the published JSON of three apps
// (Mint ../money/index.json, Kairos' windows, Pythia ../pythia/events.json); when the 'Jarvis brain' API exists (window.JARVIS_API, see
// docs/JARVIS_API.md) its nudges / ask are used first. Every part is total: a missing source never throws, it gives plain words instead,
// and ?demo=1 (or no source at all) fills each part from FAKE so the home is never blank. Read only: nothing here trades, arms or sends.
//
//   buildHome({ facts, snap, api, money, events, kairos, now, demo, favs, recent, apps }) -> model (pure; runs in node, tests.test_jarvis_home_agora)
//   loadHome({ demo, api, win })  -> Promise<model>   fetches what it needs (timeouts 5 s), then buildHome
//   model = { demo, online, asof, today: { items: [{ id, text, tone, app?, say? }], more }, bots: [{ id, name, size, level, pnl, room, mll, text, app }],
//             money: { low, base, high, live, text, note }, day: { now: {label, text, until, entries}, next: { title, when, impact } | null },
//             asks: [string], favs: [{ id, name, glyph }], recent: [{ id, name, glyph }] }
// Plain ES2020, no imports (the optional kairoscore.js is imported dynamically), iPhone Safari 16.

const isObj = (x) => !!x && typeof x === 'object' && !Array.isArray(x);
const arr = (x) => (Array.isArray(x) ? x : []);
const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : typeof v === 'string' && v.trim() !== '' && Number.isFinite(+v) ? +v : null);
const str = (v, n) => (typeof v === 'string' ? v : typeof v === 'number' && Number.isFinite(v) ? String(v) : '').replace(/\s+/g, ' ').trim().slice(0, n || 200);
export const usd = (v, sign) => { const x = num(v); if (x == null) return null; const a = Math.abs(Math.round(x)); return (x < 0 && a ? '−' : sign && x > 0 && a ? '+' : '') + '$' + a.toLocaleString('en-US'); };

export const ASKS = ['What should I do today?', 'How are my bots?', 'How much drawdown is left?', "What's next on the market?"];
export const FAV_KEYS = ['oly.launcher.fav', 'jarvis.orb.fav'];
export const REC_KEY = 'jarvis.orb.recent';

// ------------------------------------------------------------------------------------------------ the fake provider (demo and offline)
export const FAKE = {
  facts: { system: { verdict: 'HEADS UP', level: 'warn', todo: '', todos: [{ id: 'atlas', level: 'warn', todo: 'ATLAS is close to its floor: $1,240 of room left', short: 'ATLAS near its floor', app: 'zenith' },
    { id: 'planner', level: 'warn', todo: 'Planner: 2 tasks are due today', short: '2 tasks due', app: 'planner' }] } },
  bots: [
    { id: 'lit', name: 'Zlarior', size: '50K', level: 'ok', pnl: 412, room: 1840, mll: 2000, text: 'Waiting for the London window', app: 'zenith' },
    { id: 'atlas', name: 'ATLAS', size: '25K', level: 'warn', pnl: -96, room: 1240, mll: 1500, text: 'Close to its floor: it sizes down by itself', app: 'zenith' },
  ],
  money: { low: -42, base: 1495, high: 2547, live: false, text: 'Example numbers until your money machines publish their own.', note: 'An estimate, not income.' },
  day: { now: { label: 'London entries', text: 'LIT looks for a sweep; most trades come here.', until: 'New York morning in 2 h 10 min', entries: true }, next: { title: 'Example: inflation report', when: 'Tue 8:30 AM ET', impact: 'high' } },
};

// ------------------------------------------------------------------------------------------------ pure builders
export function nudgesFrom(facts, api) {
  const out = [];
  try {
    const n = api && typeof api.nudges === 'function' ? api.nudges() : null;
    for (const x of arr(n && n.then ? null : n)) if (isObj(x) && str(x.text)) out.push({ id: str(x.id, 40) || 'api' + out.length, text: str(x.text, 160), tone: /^(bad|warn|ok|info)$/.test(x.tone) ? x.tone : 'info', app: str(x.app, 40), say: str(x.say, 120) });
  } catch (_) { /* the API is optional */ }
  const sys = facts && isObj(facts.system) ? facts.system : null;
  for (const t of arr(sys && sys.todos)) if (isObj(t) && str(t.todo)) out.push({ id: str(t.id, 40), text: str(t.todo, 160), tone: t.level === 'bad' ? 'bad' : 'warn', app: str(t.app, 40) });
  const p = facts && isObj(facts.planner) ? facts.planner : null;
  const tasks = arr(p && p.tasks).filter(isObj);
  if (tasks.length) out.push({ id: 'tasks', text: `${tasks.length} ${tasks.length === 1 ? 'task is' : 'tasks are'} due today: ${str(tasks[0].title, 50)}${tasks.length > 1 ? ' and more' : ''}`, tone: 'info', app: 'planner' });
  const seen = new Set(), uniq = out.filter((x) => !seen.has(x.text) && seen.add(x.text));
  uniq.sort((a, b) => (a.tone === 'bad' ? 0 : a.tone === 'warn' ? 1 : 2) - (b.tone === 'bad' ? 0 : b.tone === 'warn' ? 1 : 2));
  return { items: uniq.slice(0, 3), more: Math.max(0, uniq.length - 3) };
}

export function botsFrom(snap, facts) {
  const bots = snap && snap.ok && isObj(snap.bots) ? snap.bots : null;
  if (!bots) return [];
  const rows = facts && facts.system ? arr(facts.system.rows) : [];
  const out = [];
  for (const key of ['lit', 'atlas']) {
    const b = bots[key]; if (!isObj(b)) continue;
    const row = rows.find((r) => r && (r.id === key)) || {};
    const rf = num(b.room_frac);
    const level = b.over ? '' : row.level === 'bad' || (rf != null && rf < 0.25) ? 'bad' : row.level === 'warn' || (rf != null && rf < 0.5) ? 'warn' : num(b.room) != null ? 'ok' : '';
    out.push({ id: key, name: key === 'lit' ? 'Zlarior' : 'ATLAS', size: str(b.size, 8), level, pnl: num(b.today_pnl), room: num(b.room), mll: num(b.mll),
      text: str(b.waiting, 80) || str(b.status, 40) || str(row.text, 80), app: 'zenith' });
  }
  return out;
}

/** "Drawdown left $X of $max loss": the owner's wording, with both numbers, never one without the other when the max is known. */
export function drawdownLine(b) {
  if (!b || num(b.room) == null) return 'No drawdown number yet';
  const r = usd(b.room), m = num(b.mll) != null && b.mll > 0 ? usd(b.mll) : null;
  return m ? `Drawdown left ${r} of ${m} max loss` : `Drawdown left ${r}`;
}

export function moneyFrom(j) {
  const t = isObj(j) && isObj(j.total) ? j.total : null;
  if (!t || num(t.base) == null) return null;
  const sample = !!(j && (j.mode === 'sample' || (isObj(j.counts) && j.counts.ok === 0 && j.counts.stale === 0) || /example/i.test(str(j.note, 200))));
  return { low: num(t.low), base: num(t.base), high: num(t.high), live: !sample, text: sample ? 'Example numbers until your money machines publish their own.' : 'From your money machines, paper only.', note: 'An estimate, not income.' };
}

const ETP = (ms) => {
  try {
    const p = {}; for (const x of new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', weekday: 'short' }).formatToParts(new Date(ms))) p[x.type] = x.value;
    return { ymd: `${p.year}-${p.month}-${p.day}`, hm: `${p.hour}:${p.minute}`, wd: p.weekday };
  } catch (_) { const d = new Date(ms); return { ymd: d.toISOString().slice(0, 10), hm: d.toISOString().slice(11, 16), wd: '' }; }
};
const ampm = (hm) => { const [h, m] = String(hm).split(':').map(Number); return Number.isFinite(h) ? `${((h + 11) % 12) + 1}:${String(m || 0).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}` : ''; };
/** The next market-moving event (Pythia's events.json) at or after `nowMs`, New York time, or null. Nothing is guessed: no file, no event. */
export function nextEvent(events, nowMs) {
  const list = isObj(events) && isObj(events.events) ? arr(events.events.events) : isObj(events) ? arr(events.events) : [];
  const now = ETP(nowMs), key = now.ymd + ' ' + now.hm;
  const up = list.filter((e) => isObj(e) && /^\d{4}-\d{2}-\d{2}$/.test(String(e.date)) && str(e.title)).map((e) => ({ e, k: e.date + ' ' + (/^\d{2}:\d{2}$/.test(String(e.time)) ? e.time : '23:59') }))
    .filter((x) => x.k >= key).sort((a, b) => (a.k < b.k ? -1 : 1));
  if (!up.length) return null;
  const e = up[0].e, d = new Date(e.date + 'T12:00:00Z'), wd = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getUTCDay()];
  const today = e.date === now.ymd;
  return { title: str(e.title, 60), when: `${today ? 'Today' : wd + ' ' + (d.getUTCMonth() + 1) + '/' + d.getUTCDate()}${/^\d{2}:\d{2}$/.test(String(e.time)) ? ' ' + ampm(e.time) + ' ET' : ''}`, impact: /^(high|med|low)$/.test(e.impact) ? e.impact : '' };
}

export function appsLookup(apps) {
  const m = new Map();
  for (const a of arr(apps)) if (isObj(a) && typeof a.id === 'string') m.set(a.id, { id: a.id, name: str(a.name, 24) || a.id, glyph: str(a.glyph, 2) || str(a.name || a.id, 1).toUpperCase() });
  return m;
}
const pickIds = (list, lookup, n) => arr(list).filter((id) => typeof id === 'string' && lookup.has(id)).slice(0, n).map((id) => lookup.get(id));

export function buildHome(o) {
  o = o || {};
  const now = num(o.now) != null ? +o.now : Date.now(), demo = !!o.demo, facts = isObj(o.facts) ? o.facts : null;
  const online = o.online !== false;
  const lookup = appsLookup(o.apps);
  const m = { demo, online, asof: now, today: { items: [], more: 0 }, bots: [], money: null, day: { now: null, next: null }, asks: ASKS.slice(), favs: [], recent: [] };
  // today: what needs you
  try { m.today = nudgesFrom(demo ? FAKE.facts : facts, demo ? null : o.api); } catch (_) { /* stays empty */ }
  // bots
  try { m.bots = demo ? FAKE.bots.slice() : botsFrom(o.snap, facts); } catch (_) { m.bots = []; }
  // money
  try { m.money = demo ? FAKE.money : moneyFrom(o.money) || (o.sampleMoney ? moneyFrom(o.sampleMoney) : null); } catch (_) { m.money = null; }
  // the market day
  try {
    const k = o.kairos;
    const nowS = k && isObj(k.now) ? k.now : null;
    m.day.now = demo ? FAKE.day.now : nowS ? { label: str(nowS.label, 40), text: str(nowS.text, 140), until: str(nowS.until, 60), entries: !!nowS.entries } : null;
    m.day.next = demo ? FAKE.day.next : nextEvent(o.events, now);
  } catch (_) { /* stays empty */ }
  // favourites and recent
  const favIds = arr(o.favs).length ? o.favs : [];
  m.favs = pickIds(favIds, lookup, 8);
  m.recent = pickIds(arr(o.recent).filter((id) => favIds.indexOf(id) < 0), lookup, 4);
  return m;
}

// ------------------------------------------------------------------------------------------------ the browser part
const lsRead = (k) => { try { const v = JSON.parse(localStorage.getItem(k) || 'null'); return Array.isArray(v) ? v : null; } catch (_) { return null; } };
async function getJSON(url, ms) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, t = setTimeout(() => { try { if (ac) ac.abort(); } catch (_) { /* fine */ } }, ms || 5000);
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(t); }
}
let kcore = null;
async function kairosNow(now) {
  try { kcore = kcore || (await import('../kairos/kairoscore.js')); return { now: kcore.nowState(new Date(now)) }; } catch (_) { return null; }
}
let cache = null;
/** Fetch what the home needs. The slow sources (Mint, Pythia) are cached for 5 minutes; everything else is read fresh from Jarvis. */
export async function loadHome(opts) {
  opts = opts || {};
  const win = opts.win || window, demo = !!opts.demo, now = Date.now();
  let facts = null, snap = null, apps = [];
  try { facts = win.__jarvis && typeof win.__jarvis.facts === 'function' ? win.__jarvis.facts() : null; } catch (_) { facts = null; }
  try { apps = facts && Array.isArray(facts.apps) ? facts.apps : []; } catch (_) { apps = []; }
  if (!apps.length && Array.isArray(win.OLYMPUS_APPS_LIST)) apps = win.OLYMPUS_APPS_LIST;
  if (!demo && facts && facts.live) { try { const B = await import('./bots.js'); snap = B.snapshot(facts.live, now); } catch (_) { snap = null; } }
  if (!cache || now - cache.t > 5 * 60e3) {
    const [money, sample, events] = demo ? [null, null, null] : await Promise.all([getJSON('../money/index.json'), getJSON('../mint/fixture.json'), getJSON('../pythia/events.json')]);
    cache = { t: now, money, sample, events };
  }
  const kairos = await kairosNow(now);
  let favs = null; for (const k of FAV_KEYS) { favs = lsRead(k); if (favs && favs.length) break; }
  const home = buildHome({ demo, facts, snap, api: win.JARVIS_API || null, money: cache.money, sampleMoney: cache.sample, events: cache.events, kairos, now, apps,
    favs: favs || [], recent: lsRead(REC_KEY) || [], online: win.navigator ? win.navigator.onLine !== false : true });
  return home;
}
export const _resetCache = () => { cache = null; };
