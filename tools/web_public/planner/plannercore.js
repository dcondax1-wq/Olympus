// PLANNER core (pure: no DOM, no storage, no network). The trader's day and week plan, 2026-11-10 (AGORA look).
// One state object { v, checklist, checks, tasks, habits, habitLog, notes, updated }; every function works on plain data so node can test it.
// Days are 'YYYY-MM-DD' strings in New York time; the day maths never uses the phone's time zone.

export const STORE_KEY = 'planner.agora.v1';
export const MAX = { text: 200, note: 4000, tasks: 600, habits: 24, checklist: 24, notes: 800 };
export const WINDOWS = [
  { id: 'entries', at: '02:00', label: 'Entries open', note: 'The bot may take one trade a day' },
  { id: 'last', at: '15:30', label: 'Last entry', note: 'No new trade after this' },
  { id: 'flat', at: '15:55', label: 'Bot flat', note: 'Everything is closed by the bot' },
  { id: 'mffu', at: '16:10', label: 'MFFU flat by', note: 'The prop firm needs you flat by now' },
];
const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
const pad = (n) => String(n).padStart(2, '0');
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// ------------------------------------------------------------------------------------------------ days
export function validDay(s) {
  if (typeof s !== 'string' || !DAY_RE.test(s)) return false;
  const [y, m, d] = s.split('-').map(Number), t = new Date(Date.UTC(y, m - 1, d));
  return t.getUTCFullYear() === y && t.getUTCMonth() === m - 1 && t.getUTCDate() === d;
}
export function addDays(day, n) {
  const [y, m, d] = day.split('-').map(Number), t = new Date(Date.UTC(y, m - 1, d + n));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}
export function dow(day) { const [y, m, d] = day.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d)).getUTCDay(); }
export function weekStart(day) { const w = dow(day); return addDays(day, w === 0 ? -6 : 1 - w); }
export function weekDays(day) { const s = weekStart(day); return [0, 1, 2, 3, 4, 5, 6].map((i) => addDays(s, i)); }
export function isWeekend(day) { const w = dow(day); return w === 0 || w === 6; }
export function dayLabel(day) { const [, m, d] = day.split('-').map(Number); return `${WD[dow(day)]} ${d} ${MON[m - 1]}`; }
export function shortDay(day) { return WD[dow(day)]; }
export function dayNum(day) { return Number(day.slice(8)); }

export function etParts(date) {
  const f = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  const p = {};
  for (const x of f.formatToParts(date)) p[x.type] = x.value;
  const h = Number(p.hour) % 24, m = Number(p.minute);
  return { day: `${p.year}-${p.month}-${p.day}`, hh: h, mm: m, mins: h * 60 + m, hhmm: `${pad(h)}:${pad(m)}` };
}
export function duration(mins) {
  if (mins == null || !Number.isFinite(mins) || mins < 0) return '';
  const m = Math.round(mins);
  if (m < 60) return `${m} min`;
  if (m < 1440) return `${Math.floor(m / 60)} h ${m % 60} min`;
  return `${Math.floor(m / 1440)} day${m >= 2880 ? 's' : ''} ${Math.floor((m % 1440) / 60)} h`;
}
const hm = (s) => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));

// where the trading day stands right now (New York time): prep, entries, wind-down, flat, done, or the weekend
export function sessionState(date) {
  const et = etParts(date), w = dow(et.day), t = et.mins;
  const E = hm('02:00'), L = hm('15:30'), F = hm('15:55'), M = hm('16:10');
  const base = { day: et.day, hhmm: et.hhmm, mins: t, weekend: w === 0 || w === 6, entries: false };
  if (base.weekend) return { ...base, id: 'closed', label: 'Weekend', next: null, nextText: 'The bot does not trade at the weekend. Plan the week.', pct: 0 };
  const pct = Math.max(0, Math.min(100, Math.round(((t - E) / (F - E)) * 100)));
  if (t < E) return { ...base, id: 'prep', label: 'Pre-session', next: 'Entries open', nextText: `Entries open at 02:00 ET, in ${duration(E - t)}.`, pct: 0 };
  if (t < L) return { ...base, id: 'entries', label: 'Entries open', entries: true, next: 'Last entry', nextText: `Last entry at 15:30 ET, in ${duration(L - t)}.`, pct };
  if (t < F) return { ...base, id: 'winddown', label: 'Wind-down', next: 'Bot flat', nextText: `No new trades. The bot is flat at 15:55 ET, in ${duration(F - t)}.`, pct };
  if (t < M) return { ...base, id: 'flat', label: 'Flat now', next: 'MFFU flat', nextText: `Check you are flat. MFFU needs it by 16:10 ET, in ${duration(M - t)}.`, pct: 100 };
  return { ...base, id: 'done', label: 'Day over', next: null, nextText: 'Trading is over for today. Review the day and plan tomorrow.', pct: 100 };
}

// ------------------------------------------------------------------------------------------------ state
export function defaultChecklist() {
  return [
    'Look at the news calendar for red-folder events',
    'Mark the levels: the 18:00 open and the VIX band',
    'Check the drawdown left on the account',
    'Check the bot is on and its feed is fresh',
    'Decide the one rule for today',
    'I am present: no live order without me',
  ].map((text, i) => ({ id: 'c' + (i + 1), text }));
}
export function defaultHabits() { return ['Journal the day', 'Review the trades', 'Move: walk or train'].map((name, i) => ({ id: 'h' + (i + 1), name })); }
export function blankState() { return { v: 1, checklist: defaultChecklist(), checks: {}, tasks: [], habits: defaultHabits(), habitLog: {}, notes: {}, updated: 0 }; }

const clip = (s, n) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim().slice(0, n);
const isObj = (o) => o && typeof o === 'object' && !Array.isArray(o);
const slotOk = (s) => typeof s === 'string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(s);

// junk-proof copy: anything that is not the right shape is dropped, never thrown on
export function normalise(raw) {
  if (!isObj(raw)) return null;
  const out = { v: 1, checklist: [], checks: {}, tasks: [], habits: [], habitLog: {}, notes: {}, updated: Number.isFinite(raw.updated) ? raw.updated : 0 };
  const used = { c: new Set(), h: new Set(), t: new Set() };
  const uniq = (id, pre) => {
    let s = clip(id, 40).replace(/[^\w-]/g, ''); const set = used[pre];
    if (!s || set.has(s)) { let n = set.size + 1; while (set.has(pre + n)) n++; s = pre + n; }
    set.add(s); return s;
  };
  for (const c of Array.isArray(raw.checklist) ? raw.checklist : []) if (isObj(c) && clip(c.text, MAX.text) && out.checklist.length < MAX.checklist) out.checklist.push({ id: uniq(c.id, 'c'), text: clip(c.text, MAX.text) });
  for (const h of Array.isArray(raw.habits) ? raw.habits : []) if (isObj(h) && clip(h.name, 80) && out.habits.length < MAX.habits) out.habits.push({ id: uniq(h.id, 'h'), name: clip(h.name, 80) });
  for (const t of Array.isArray(raw.tasks) ? raw.tasks : []) if (isObj(t) && clip(t.text, MAX.text) && validDay(t.day) && out.tasks.length < MAX.tasks) out.tasks.push({ id: uniq(t.id, 't'), text: clip(t.text, MAX.text), day: t.day, done: t.done === true, slot: slotOk(t.slot) ? t.slot : '' });
  const cid = new Set(out.checklist.map((c) => c.id)), hid = new Set(out.habits.map((h) => h.id));
  const keep = (src, ids, dst) => {
    if (!isObj(src)) return;
    for (const d of Object.keys(src)) {
      if (!validDay(d) || !isObj(src[d])) continue;
      const o = {};
      for (const k of Object.keys(src[d])) if (ids.has(k) && src[d][k] === true) o[k] = true;
      if (Object.keys(o).length) dst[d] = o;
    }
  };
  keep(raw.checks, cid, out.checks);
  keep(raw.habitLog, hid, out.habitLog);
  if (isObj(raw.notes)) for (const d of Object.keys(raw.notes)) if (validDay(d) && typeof raw.notes[d] === 'string' && raw.notes[d].trim() && Object.keys(out.notes).length < MAX.notes) out.notes[d] = raw.notes[d].slice(0, MAX.note);
  return out;
}
export function newId(pre, list) { const used = new Set(list.map((x) => x.id)); let n = list.length + 1; while (used.has(pre + n)) n++; return pre + n; }

// "Review levels 09:30" -> { text: 'Review levels', slot: '09:30' }
export function parseQuick(input) {
  let s = clip(input, MAX.text + 10), slot = '';
  const m = s.match(/(?:^|\s)@?([01]?\d|2[0-3]):([0-5]\d)(?=\s|$)/);
  if (m) { slot = `${pad(Number(m[1]))}:${m[2]}`; s = clip(s.replace(m[0], ' '), MAX.text); }
  return { text: s, slot };
}

// ------------------------------------------------------------------------------------------------ changes (they change the state you pass in and return what they made)
export function addTask(st, input, day) {
  const q = typeof input === 'string' ? parseQuick(input) : input;
  if (!q.text || !validDay(day) || st.tasks.length >= MAX.tasks) return null;
  const t = { id: newId('t', st.tasks), text: q.text, day, done: false, slot: slotOk(q.slot) ? q.slot : '' };
  st.tasks.push(t);
  return t;
}
export function toggleTask(st, id) { const t = st.tasks.find((x) => x.id === id); if (t) t.done = !t.done; return t || null; }
export function removeTask(st, id) { const n = st.tasks.length; st.tasks = st.tasks.filter((x) => x.id !== id); return st.tasks.length < n; }
export function moveTask(st, id, day) { const t = st.tasks.find((x) => x.id === id); if (t && validDay(day)) t.day = day; return t || null; }
function flip(log, day, id) {
  const o = log[day] || (log[day] = {});
  if (o[id]) delete o[id]; else o[id] = true;
  const on = !!o[id];
  if (!Object.keys(o).length) delete log[day];
  return on;
}
export function toggleCheck(st, day, id) { return st.checklist.some((c) => c.id === id) && validDay(day) ? flip(st.checks, day, id) : null; }
export function toggleHabit(st, day, id) { return st.habits.some((h) => h.id === id) && validDay(day) ? flip(st.habitLog, day, id) : null; }
export function setNote(st, day, text) { if (!validDay(day)) return; const s = String(text == null ? '' : text).slice(0, MAX.note); if (s.trim()) st.notes[day] = s; else delete st.notes[day]; }
export function addChecklist(st, text) { const t = clip(text, MAX.text); if (!t || st.checklist.length >= MAX.checklist) return null; const c = { id: newId('c', st.checklist), text: t }; st.checklist.push(c); return c; }
export function removeChecklist(st, id) {
  const n = st.checklist.length; st.checklist = st.checklist.filter((c) => c.id !== id);
  for (const d of Object.keys(st.checks)) { delete st.checks[d][id]; if (!Object.keys(st.checks[d]).length) delete st.checks[d]; }
  return st.checklist.length < n;
}
export function addHabit(st, name) { const t = clip(name, 80); if (!t || st.habits.length >= MAX.habits) return null; const h = { id: newId('h', st.habits), name: t }; st.habits.push(h); return h; }
export function removeHabit(st, id) {
  const n = st.habits.length; st.habits = st.habits.filter((h) => h.id !== id);
  for (const d of Object.keys(st.habitLog)) { delete st.habitLog[d][id]; if (!Object.keys(st.habitLog[d]).length) delete st.habitLog[d]; }
  return st.habits.length < n;
}

// ------------------------------------------------------------------------------------------------ views
const bySlot = (a, b) => (a.done - b.done) || (a.slot || '99:99').localeCompare(b.slot || '99:99') || a.id.localeCompare(b.id, 'en', { numeric: true });
export function streak(st, hid, day) {
  const has = (d) => !!(st.habitLog[d] && st.habitLog[d][hid]);
  let d = has(day) ? day : addDays(day, -1), n = 0;
  while (has(d) && n < 3650) { n++; d = addDays(d, -1); }
  return n;
}
export function dayView(st, day) {
  const tasks = st.tasks.filter((t) => t.day === day).sort(bySlot), ck = st.checks[day] || {}, hl = st.habitLog[day] || {};
  const check = st.checklist.map((c) => ({ id: c.id, text: c.text, done: ck[c.id] === true }));
  const habits = st.habits.map((h) => ({ id: h.id, name: h.name, done: hl[h.id] === true, streak: streak(st, h.id, day) }));
  return { day, tasks, tasksDone: tasks.filter((t) => t.done).length, check, checkDone: check.filter((c) => c.done).length, habits, habitsDone: habits.filter((h) => h.done).length, note: st.notes[day] || '' };
}
// share of everything planned for the day that is done (null when nothing is planned)
export function dayScore(st, day) {
  const v = dayView(st, day), total = v.tasks.length + v.check.length + v.habits.length;
  return total ? Math.round(((v.tasksDone + v.checkDone + v.habitsDone) / total) * 100) : null;
}
export function habitWeek(st, hid, day) { return weekDays(day).map((d) => ({ day: d, done: !!(st.habitLog[d] && st.habitLog[d][hid]) })); }
export function weekView(st, day, today) {
  return weekDays(day).map((d) => {
    const v = dayView(st, d);
    return { day: d, label: shortDay(d), num: dayNum(d), weekend: isWeekend(d), today: d === today, selected: d === day, tasks: v.tasks.length, tasksDone: v.tasksDone, check: v.check.length, checkDone: v.checkDone, habits: v.habits.length, habitsDone: v.habitsDone, hasNote: !!v.note, score: dayScore(st, d) };
  });
}
// the week in two numbers: tasks done / planned, and the average score of the days up to today
export function weekTotals(rows, today) {
  const tasks = rows.reduce((a, r) => a + r.tasks, 0), done = rows.reduce((a, r) => a + r.tasksDone, 0);
  const sc = rows.filter((r) => r.score != null && !r.weekend && r.day <= today);
  return { tasks, done, avg: sc.length ? Math.round(sc.reduce((s, r) => s + r.score, 0) / sc.length) : null };
}
export function recentNotes(st, n) { return Object.keys(st.notes).sort().reverse().slice(0, n || 10).map((d) => ({ day: d, text: st.notes[d] })); }
export function counts(st) { return { tasks: st.tasks.length, habits: st.habits.length, notes: Object.keys(st.notes).length, checklist: st.checklist.length }; }

// ------------------------------------------------------------------------------------------------ export / import
export function exportText(st, nowMs) {
  return JSON.stringify({ app: 'planner', v: 1, exported: new Date(nowMs || 0).toISOString(), data: st }, null, 2);
}
export function exportName(day) { return `planner-${day}.json`; }
export function parseImport(text) {
  let raw;
  try { raw = JSON.parse(String(text || '').replace(/^﻿/, '')); } catch (_) { return { ok: false, error: 'That is not a Planner file (it is not valid JSON).' }; }
  const data = isObj(raw) && isObj(raw.data) && raw.app === 'planner' ? raw.data : raw;
  if (!isObj(data) || !('tasks' in data || 'checklist' in data || 'habits' in data || 'notes' in data)) return { ok: false, error: 'That file has no Planner plan in it.' };
  const st = normalise(data);
  if (!st) return { ok: false, error: 'That file has no Planner plan in it.' };
  if (!st.checklist.length) st.checklist = defaultChecklist();
  return { ok: true, state: st, counts: counts(st) };
}

// ------------------------------------------------------------------------------------------------ demo
// fixture = { checklist: [text], checkedToday: [index], tasks: [{ text, off, done, slot }], habits: [{ name, hits: [days back from today] }], notes: [{ off, text }] }
export function buildDemo(fx, today) {
  if (!isObj(fx) || !validDay(today)) return blankState();
  const st = { v: 1, checklist: [], checks: {}, tasks: [], habits: [], habitLog: {}, notes: {}, updated: 0 };
  (Array.isArray(fx.checklist) ? fx.checklist : []).forEach((t, i) => { if (typeof t === 'string' && t.trim()) st.checklist.push({ id: 'c' + (i + 1), text: clip(t, MAX.text) }); });
  if (!st.checklist.length) st.checklist = defaultChecklist();
  (Array.isArray(fx.checkedToday) ? fx.checkedToday : []).forEach((i) => { const c = st.checklist[i]; if (c) (st.checks[today] || (st.checks[today] = {}))[c.id] = true; });
  (Array.isArray(fx.tasks) ? fx.tasks : []).forEach((t) => { if (isObj(t) && typeof t.text === 'string' && Number.isInteger(t.off)) st.tasks.push({ id: 't' + (st.tasks.length + 1), text: clip(t.text, MAX.text), day: addDays(today, t.off), done: t.done === true, slot: slotOk(t.slot) ? t.slot : '' }); });
  (Array.isArray(fx.habits) ? fx.habits : []).forEach((h) => {
    if (!isObj(h) || typeof h.name !== 'string') return;
    const id = 'h' + (st.habits.length + 1); st.habits.push({ id, name: clip(h.name, 80) });
    for (const o of Array.isArray(h.hits) ? h.hits : []) if (Number.isInteger(o)) { const d = addDays(today, -Math.abs(o)); (st.habitLog[d] || (st.habitLog[d] = {}))[id] = true; }
  });
  (Array.isArray(fx.notes) ? fx.notes : []).forEach((n) => { if (isObj(n) && typeof n.text === 'string' && Number.isInteger(n.off)) st.notes[addDays(today, n.off)] = n.text.slice(0, MAX.note); });
  if (!st.habits.length) st.habits = defaultHabits();
  return st;
}

// the small summary other OLYMPUS pages may read ('planner.today.v1')
export function todaySummary(st, day, nowMs) {
  const v = dayView(st, day);
  return {
    v: 1, day, events: isWeekend(day) ? [] : WINDOWS.map((w) => ({ title: w.label, start: w.at, end: '', allDay: false })),
    tasks: v.tasks.map((t) => ({ title: t.text, due: t.day, done: t.done })), updated: nowMs || 0,
  };
}
