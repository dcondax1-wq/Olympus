// PLANNER v2 core tests in node (no browser): node tests/planner_core_harness.cjs [path to plannercore.js]
// Prints one JSON array of [name, ok, info] per check; tests/test_planner_page.py runs it and reports each line. Exit code 1 when a check fails.
const fs = require('fs'), os = require('os'), path = require('path');
const here = path.resolve(__dirname, '..', 'tools', 'web_public', 'planner');
let corePath = process.argv[2] || path.join(here, 'plannercore.js');
if (!corePath.endsWith('.mjs')) { const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'planner-core-')); const dst = path.join(tmp, 'plannercore.mjs'); fs.copyFileSync(corePath, dst); corePath = dst; }
const R = [];
const T = (name, ok, info) => R.push([name, !!ok, ok ? '' : JSON.stringify(info === undefined ? null : info).slice(0, 600)]);
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
import(corePath).then((C) => {
  const D = (s) => Date.parse(s);
  // ---------------------------------------------------------------- 1. New York time and the clock change of Nov 1 2026
  T('1. New York time by rule: EDT until 06:00Z on Sun 1 Nov 2026, EST after; the spring change is Sun 8 Mar 2026', C.etOffsetMin(D('2026-11-01T05:59:00Z')) === -240 && C.etOffsetMin(D('2026-11-01T06:00:00Z')) === -300 && C.etOffsetMin(D('2026-03-08T06:59:00Z')) === -300 && C.etOffsetMin(D('2026-03-08T07:00:00Z')) === -240);
  const p1 = C.etParts(new Date('2026-11-01T05:30:00Z')), p2 = C.etParts(new Date('2026-11-01T06:30:00Z')), p3 = C.etParts(new Date('2026-11-09T14:41:00Z'));
  T('1. 01:30 happens twice on Nov 1 (05:30Z in EDT, 06:30Z in EST); 14:41Z on Nov 9 is 09:41', p1.hhmm === '01:30' && p1.offset === -240 && p2.hhmm === '01:30' && p2.offset === -300 && p3.hhmm === '09:41' && p3.day === '2026-11-09', [p1, p2, p3]);
  T('1. wall clock to real moment: Oct 31 09:00 = 13:00Z, Nov 1 09:00 = 14:00Z, Nov 1 01:30 = the first one (05:30Z), the missing 02:30 of Mar 8 lands at 03:30 EDT (07:30Z)',
    C.etEpoch('2026-10-31', '09:00') === D('2026-10-31T13:00:00Z') && C.etEpoch('2026-11-01', '09:00') === D('2026-11-01T14:00:00Z') && C.etEpoch('2026-11-01', '01:30') === D('2026-11-01T05:30:00Z') && C.etEpoch('2026-03-08', '02:30') === D('2026-03-08T07:30:00Z'));
  T('1. the day lengths: Nov 1 has 25 hours, Mar 8 has 23, an ordinary day 24', C.dayHours('2026-11-01') === 25 && C.dayHours('2026-03-08') === 23 && C.dayHours('2026-11-09') === 24);
  const at = (s) => { const x = C.sessionState(new Date(s)); return [x.id, x.hhmm, x.entries, x.day, x.pct]; };
  T('1. the trading clock: 01:59 pre-session, 02:00 entries, 15:30 wind-down, 15:55 flat, 16:10 over, the weekend closed, through the clock change',
    at('2026-11-09T06:59:00Z')[0] === 'prep' && at('2026-11-09T07:00:00Z')[0] === 'entries' && at('2026-11-09T20:30:00Z')[0] === 'winddown' && at('2026-11-09T21:00:00Z')[0] === 'flat' && at('2026-11-09T21:10:00Z')[0] === 'done' && at('2026-11-14T15:00:00Z')[0] === 'closed' && at('2026-03-09T06:00:00Z').slice(0, 2).join() === 'entries,02:00');
  T('1. day maths: add, between, weekday, Monday of a week, month helpers, labels, validation',
    C.addDays('2026-02-28', 1) === '2026-03-01' && C.addDays('2028-02-28', 1) === '2028-02-29' && C.daysBetween('2026-10-30', '2026-11-02') === 3 && C.dow('2026-11-09') === 1 && C.weekStart('2026-11-15') === '2026-11-09' && C.addMonths('2026-12', 2) === '2027-02' && C.daysInMonth('2028-02') === 29 &&
    C.dayLabel('2026-11-09') === 'Mon 9 Nov' && C.dayLong('2026-11-01') === 'Sunday 1 November 2026' && !C.validDay('2026-02-30') && C.validDay('2028-02-29') && C.timeWord('13:05') === '1:05 pm' && C.timeWord('00:00') === '12 am');

  // ---------------------------------------------------------------- 2. recurrence across the clock change
  const mk = (o) => C.normalise({ events: [{ id: 'e1', title: 'x', day: '2026-10-30', start: '09:00', ...o }] }).events[0];
  const daily = mk({ repeat: 'daily' }), occ = C.expand([daily], '2026-10-30', '2026-11-03');
  T('2. a daily 09:00 event stays 09:00 on the wall clock through Nov 1: the real moments are 13Z, 13Z, 14Z, 14Z, 14Z and the gap over the change is 25 hours',
    occ.length === 5 && occ.every((o) => o.start === '09:00') && eq(occ.map((o) => new Date(o.ms).getUTCHours()), [13, 13, 14, 14, 14]) && (occ[2].ms - occ[1].ms) === 25 * 3600000, occ.map((o) => o.day + ' ' + new Date(o.ms).toISOString()));
  const wk = C.expand([mk({ day: '2026-10-25', repeat: 'weekly' })], '2026-10-25', '2026-11-08');
  T('2. a weekly Sunday 09:00 event: Oct 25 (13Z), Nov 1 (14Z), Nov 8 (14Z)', eq(wk.map((o) => o.day), ['2026-10-25', '2026-11-01', '2026-11-08']) && eq(wk.map((o) => new Date(o.ms).getUTCHours()), [13, 14, 14]));
  T('2. weekdays skip the weekend (Fri 30 Oct, Mon 2, Tue 3), biweekly hits every 14th day, an end day is the last day, an exception is skipped',
    eq(C.expand([mk({ repeat: 'weekdays' })], '2026-10-30', '2026-11-03').map((o) => o.day), ['2026-10-30', '2026-11-02', '2026-11-03']) && C.occursOn(mk({ day: '2026-11-02', repeat: 'biweekly' }), '2026-11-16') && !C.occursOn(mk({ day: '2026-11-02', repeat: 'biweekly' }), '2026-11-09') &&
    C.occursOn(mk({ day: '2026-11-01', repeat: 'daily', until: '2026-11-03' }), '2026-11-03') && !C.occursOn(mk({ day: '2026-11-01', repeat: 'daily', until: '2026-11-03' }), '2026-11-04') && !C.occursOn(mk({ repeat: 'daily', ex: ['2026-11-01'] }), '2026-11-01'));
  const m31 = mk({ day: '2026-01-31', repeat: 'monthly' }), y29 = mk({ day: '2024-02-29', repeat: 'yearly' });
  T('2. a monthly event on the 31st lands on the last day of short months (Feb 28, Mar 31, Apr 30); a yearly Feb 29 lands on Feb 28 and Feb 29', C.occursOn(m31, '2026-02-28') && !C.occursOn(m31, '2026-02-27') && C.occursOn(m31, '2026-03-31') && C.occursOn(m31, '2026-04-30') && !C.occursOn(m31, '2026-04-29') && C.occursOn(y29, '2027-02-28') && C.occursOn(y29, '2028-02-29') && !C.occursOn(y29, '2027-03-01'));
  T('2. nothing before the first day; an unknown repeat is a one-off', !C.occursOn(daily, '2026-10-29') && C.occursOn(C.normalise({ events: [{ title: 'x', day: '2026-11-02', repeat: 'hourly' }] }).events[0], '2026-11-02') && !C.occursOn(C.normalise({ events: [{ title: 'x', day: '2026-11-02', repeat: 'hourly' }] }).events[0], '2026-11-03'));
  const st0 = C.blankState(); const ev = C.addEvent(st0, { title: 'Weekly review', day: '2026-11-01', start: '16:30', repeat: 'weekly' });
  C.skipOccurrence(st0, ev.id, '2026-11-08');
  T('2. "skip this day" drops one repeat only; skipping the first day moves the start to the next one; a one-off event is deleted',
    eq(C.expand(st0.events, '2026-11-01', '2026-11-15').map((o) => o.day), ['2026-11-01', '2026-11-15']) && (C.skipOccurrence(st0, ev.id, '2026-11-01'), st0.events[0].day === '2026-11-15') && (() => { const s = C.blankState(); const e = C.addEvent(s, { title: 'a', day: '2026-11-02' }); return C.skipOccurrence(s, e.id, '2026-11-02') && s.events.length === 0; })());
  // reminders
  const sr = C.blankState(); C.addEvent(sr, { title: 'Call', day: '2026-11-09', start: '10:00', remind: 15 }); C.addEvent(sr, { title: 'Later', day: '2026-11-09', start: '15:00', remind: 15 }); C.addEvent(sr, { title: 'No bell', day: '2026-11-09', start: '10:05' });
  const ms = (hm) => C.etEpoch('2026-11-09', hm);
  T('2. reminders: a badge 15 minutes before ("soon"), "now" once it started (for 15 minutes), nothing earlier, nothing for events without a reminder',
    eq(C.reminders(sr, ms('09:44')).length, 0) && eq(C.reminders(sr, ms('09:45')).map((r) => [r.title, r.state, r.mins]), [['Call', 'soon', 15]]) && eq(C.reminders(sr, ms('10:03')).map((r) => [r.state, r.mins]), [['now', -3]]) && C.reminders(sr, ms('10:16')).length === 0);

  // ---------------------------------------------------------------- 3. natural phrases (40+)
  const TODAY = '2026-11-09', PROJ = [{ id: 'p1', name: 'Trading' }];
  const P = [
    ['Fri 9am journal review', 'event', '2026-11-13', '09:00', '', 'none', 0, 'journal review'],
    ['every Sunday weekly review', 'event', '2026-11-15', '', '', 'weekly', 0, 'weekly review'],
    ['tomorrow call broker', 'task', '2026-11-10', '', '', 'none', 0, 'call broker'],
    ['Pay data subscription on 20 Nov', 'task', '2026-11-20', '', '', 'none', 0, 'Pay data subscription'],
    ['lunch with Sam today 12:30-1:30pm', 'event', '2026-11-09', '12:30', '13:30', 'none', 0, 'lunch with Sam'],
    ['standup every weekday 8:30', 'event', '2026-11-09', '08:30', '', 'weekdays', 0, 'standup'],
    ['Review trades daily', 'event', '2026-11-09', '', '', 'daily', 0, 'Review trades'],
    ['read report someday', 'task', '', '', '', 'none', 0, 'read report'],
    ['submit report by Friday !!', 'task', '2026-11-13', '', '', 'none', 2, 'submit report'],
    ['dentist next Tue 3pm', 'event', '2026-11-17', '15:00', '', 'none', 0, 'dentist'],
    ['gym 6am for 1h', 'event', '2026-11-09', '06:00', '07:00', 'none', 0, 'gym'],
    ['meeting 9-10am Thursday', 'event', '2026-11-12', '09:00', '10:00', 'none', 0, 'meeting'],
    ['task: call at 9am', 'task', '2026-11-09', '09:00', '', 'none', 0, 'call'],
    ['event: Team dinner Saturday', 'event', '2026-11-14', '', '', 'none', 0, 'Team dinner'],
    ['pay rent on the 1st', 'task', '2026-12-01', '', '', 'none', 0, 'pay rent'],
    ['call mom in 3 days', 'task', '2026-11-12', '', '', 'none', 0, 'call mom'],
    ['Plan the quarter next week', 'task', '2026-11-16', '', '', 'none', 0, 'Plan the quarter'],
    ['buy ticket Dec 4', 'task', '2026-12-04', '', '', 'none', 0, 'buy ticket'],
    ['ticket 12/4', 'task', '2026-12-04', '', '', 'none', 0, 'ticket'],
    ['ticket 4 Dec 2027', 'task', '2027-12-04', '', '', 'none', 0, 'ticket'],
    ['2026-12-24 wrap gifts', 'task', '2026-12-24', '', '', 'none', 0, 'wrap gifts'],
    ['call at 3', 'event', '2026-11-09', '15:00', '', 'none', 0, 'call'],
    ['review noon', 'event', '2026-11-09', '12:00', '', 'none', 0, 'review'],
    ['nothing here', 'task', '', '', '', 'none', 0, 'nothing here'],
    ['!!! fix bug #trading', 'task', '', '', '', 'none', 3, 'fix bug'],
    ['@trading pre-session at 02:00 remind 10m', 'event', '2026-11-09', '02:00', '', 'none', 0, 'pre-session'],
    ['yoga every 2 weeks', 'event', '2026-11-09', '', '', 'biweekly', 0, 'yoga'],
    ['tax day Apr 15', 'task', '2027-04-15', '', '', 'none', 0, 'tax day'],
    ['Weekly review monthly', 'event', '2026-11-09', '', '', 'monthly', 0, 'Weekly review'],
    ['budget every month', 'event', '2026-11-09', '', '', 'monthly', 0, 'budget'],
    ['lunch tonight', 'event', '2026-11-09', '19:00', '', 'none', 0, 'lunch'],
    ['dinner this weekend', 'task', '2026-11-14', '', '', 'none', 0, 'dinner'],
    ['monday standup', 'task', '2026-11-09', '', '', 'none', 0, 'standup'],
    ['meet 25:00', 'task', '', '', '', 'none', 0, 'meet 25:00'],
    ['ratio 3:99', 'task', '', '', '', 'none', 0, 'ratio 3:99'],
    ['buy milk p1', 'task', '', '', '', 'none', 3, 'buy milk'],
    ['call at 9 pm', 'event', '2026-11-09', '21:00', '', 'none', 0, 'call'],
    ['drink water every day', 'event', '2026-11-09', '', '', 'daily', 0, 'drink water'],
    ['finish report asap', 'task', '2026-11-09', '', '', 'none', 3, 'finish report'],
    ['review in 2 weeks', 'task', '2026-11-23', '', '', 'none', 0, 'review'],
    ['birthday jan 5', 'task', '2027-01-05', '', '', 'none', 0, 'birthday'],
    ['Fri 14:00-15:30 workshop', 'event', '2026-11-13', '14:00', '15:30', 'none', 0, 'workshop'],
    ['every Mon 7:30am gym remind 30m', 'event', '2026-11-09', '07:30', '', 'weekly', 0, 'gym'],
    ['day after tomorrow dentist', 'task', '2026-11-11', '', '', 'none', 0, 'dentist'],
    ['next month pay card', 'task', '2026-12-01', '', '', 'none', 0, 'pay card'],
    ['11-12 is not a date but 9am is', 'event', '2026-11-09', '09:00', '', 'none', 0, '11-12 is not a date but is'],
  ];
  const bad = [];
  for (const [s, kind, day, start, end, rep, prio, text] of P) { const r = C.parseQuick(s, TODAY, { projects: PROJ }); const got = [r.kind, r.day, r.start, r.end, r.repeat, r.prio, r.text]; if (!eq(got, [kind, day, start, end, rep, prio, text])) bad.push([s, got]); }
  T(`3. the phrase parser understands ${P.length} phrases (day words, weekdays, next Tue, dates, times, ranges, durations, repeats, priority, someday, asap, task:/event: prefixes)`, P.length >= 40 && bad.length === 0, bad);
  const pj = C.parseQuick('!!! fix bug #trading', TODAY, { projects: PROJ }), pc = C.parseQuick('@trading pre-session at 02:00 remind 10m', TODAY, {}), pn = C.parseQuick('call #brokers', TODAY, { projects: PROJ }), pm = C.parseQuick('every Mon 7:30am gym remind 30m', TODAY, {});
  T('3. #project picks a known project, an unknown one is offered as new; @category and "remind 10m" are read; the result lists what it understood', pj.project === 'p1' && pn.projectName === 'brokers' && pn.project === '' && pc.cat === 'trading' && pc.remind === 10 && pm.remind === 30 && pj.found.length >= 2, [pj.found, pc]);
  T('3. forcing the kind: "task" turns "Fri 9am call" into a task with a time; "event" turns "buy milk" into an all-day event today', C.parseQuick('Fri 9am call', TODAY, { kind: 'task' }).kind === 'task' && C.parseQuick('Fri 9am call', TODAY, { kind: 'task' }).start === '09:00' && C.parseQuick('buy milk', TODAY, { kind: 'event' }).kind === 'event' && C.parseQuick('buy milk', TODAY, { kind: 'event' }).day === TODAY);
  T('3. a weekday on a Friday means today, a "next" weekday means that day of NEXT week (Fri 13 Nov asked on Fri 13 Nov: today; next Fri: Fri 20 Nov)', C.parseQuick('Fri call', '2026-11-13', {}).day === '2026-11-13' && C.parseQuick('next Fri call', '2026-11-13', {}).day === '2026-11-20' && C.parseQuick('next Mon call', '2026-11-13', {}).day === '2026-11-16');
  T('3. a date that already passed this year means next year (Jan 5 on Nov 9 is 2027); junk input never throws', C.parseQuick('x jan 5', TODAY, {}).day === '2027-01-05' && C.parseQuick(null, TODAY, {}).text === '' && C.parseQuick('   ', TODAY, {}).text === '' && C.parseQuick('9am', 'bad', {}).kind === 'event' && C.describeQuick(C.parseQuick('Fri 9am journal review', TODAY, {})) === 'Event: journal review (Fri 13 Nov at 9 am)');

  // ---------------------------------------------------------------- 4. migrations
  const v1 = { v: 1, checklist: [{ id: 'c1', text: 'Look' }, { id: 'c2', text: 'Check' }], checks: { '2026-11-09': { c1: true } }, tasks: [{ id: 't1', text: 'Review', day: '2026-11-09', done: true, slot: '08:30' }, { id: 't2', text: 'Call', day: '2026-11-10', done: false, slot: '' }, { text: 'bad day', day: '2026-02-30' }],
    habits: [{ id: 'h1', name: 'Journal' }], habitLog: { '2026-11-09': { h1: true }, '2026-11-08': { h1: true } }, notes: { '2026-11-09': 'One rule today', '2026-11-08': 'Quiet day' }, updated: 123 };
  const m1 = C.migrateAgora1(v1);
  T('4. planner.agora.v1 -> v2 keeps every task (id, day, time, done), the checklist and its ticks, habits and their log, and turns each day note into a note tagged daily on its day; the version is 2',
    m1.v === 2 && m1.from === 'agora.v1' && eq(m1.tasks.map((t) => [t.id, t.text, t.day, t.slot, t.done]), [['t1', 'Review', '2026-11-09', '08:30', true], ['t2', 'Call', '2026-11-10', '', false]]) && eq(m1.checklist.map((c) => c.id), ['c1', 'c2']) && eq(m1.checks, v1.checks) && eq(m1.habitLog, v1.habitLog) && m1.habits[0].name === 'Journal' && m1.habits[0].perWeek === 7 &&
    eq(m1.notes.map((n) => [n.day, n.text, n.tags.join()]), [['2026-11-08', 'Quiet day', 'daily'], ['2026-11-09', 'One rule today', 'daily']]) && m1.updated === 123 && C.dayNote(m1, '2026-11-09').text === 'One rule today', m1);
  T('4. the dropped junk row of v1 (a task on 30 Feb) is the only thing not carried; the v1 source object is not changed', m1.tasks.length === 2 && v1.tasks.length === 3 && v1.v === 1 && Object.keys(v1.notes).length === 2);
  const leg = { events: [{ id: 'a', title: 'Dentist', date: '2026-11-12', start: '09:30', end: '10:15', repeat: 'weekly', ex: ['2026-11-19'], until: '2026-12-31', category: 'health', reminder: 15 }, { title: 'No date' }, { title: 'All day', date: '2026-11-13' }],
    tasks: [{ id: 'x', title: 'Pay bill', date: '2026-11-11', done: false, priority: 'high', project: 'Money' }, { title: 'Undated', done: true, notes: 'n' }], projects: [{ id: 'pm', name: 'Money' }, { name: 'Health' }] };
  const ml = C.migrateLegacy(leg);
  T('4. the first Planner (planner.v1: events with date / start / repeat / exceptions, tasks with title / date / priority, projects) -> v2 with the repeat, exception, end day, category, reminder, high priority and project link kept',
    ml.from === 'planner.v1' && ml.events.length === 2 && ml.events[0].title === 'Dentist' && ml.events[0].day === '2026-11-12' && ml.events[0].start === '09:30' && ml.events[0].end === '10:15' && ml.events[0].repeat === 'weekly' && eq(ml.events[0].ex, ['2026-11-19']) && ml.events[0].until === '2026-12-31' && ml.events[0].cat === 'health' && ml.events[0].remind === 15 &&
    ml.events[1].start === '' && ml.tasks.length === 2 && ml.tasks[0].text === 'Pay bill' && ml.tasks[0].prio === 3 && ml.tasks[0].day === '2026-11-11' && ml.tasks[0].project === 'pm' && ml.tasks[1].done === true && ml.tasks[1].day === '' && ml.projects.length === 2, ml);
  const la = C.loadAll(null, JSON.stringify(v1), JSON.stringify(leg));
  T('4. loadAll with both old keys merges them: the v1 plan and the first Planner\'s events, tasks and projects together, ids never clash, nothing dropped',
    la.state && eq(la.from, ['agora.v1', 'planner.v1']) && la.state.tasks.length === 4 && la.state.events.length === 2 && la.state.projects.length === 2 && new Set(la.state.tasks.map((t) => t.id)).size === 4 && la.state.notes.length === 2 && la.state.habits.length === 1 && la.state.tasks.some((t) => t.text === 'Pay bill' && t.project === 'pm'), la);
  const l2 = C.loadAll(JSON.stringify(m1), JSON.stringify(v1), JSON.stringify(leg)), lb = C.loadAll('{not json', JSON.stringify(v1), null), ln = C.loadAll(null, null, null), l1o = C.loadAll(null, JSON.stringify(v1), null);
  T('4. a saved v2 plan always wins (the old keys are not read again); a corrupt v2 text is reported bad and never replaced by an older copy silently; nothing saved gives no plan (the demo); only v1 gives the migrated plan',
    eq(l2.from, ['v2']) && l2.state.tasks.length === 2 && lb.bad === true && lb.state === null && ln.state === null && !ln.bad && eq(l1o.from, ['agora.v1']) && l1o.state.tasks.length === 2);
  const again = C.normalise(JSON.parse(JSON.stringify(m1)));
  T('4. a migrated plan is stable: normalising it again changes nothing (migrate once, save, load forever)', eq(again, m1));
  T('4. an empty or hostile old plan never throws: {} , [], a string, nulls, the wrong types', C.migrateAny({}) === null && C.migrateAny([]) === null && C.migrateAny('x') === null && C.migrateAny(null) === null && C.migrateAgora1({ checklist: 5, tasks: 'x', habits: [null, 3], notes: [] }).tasks.length === 0 && C.migrateLegacy({ events: [null, 4, {}], tasks: [{}, { title: 5 }], projects: 7 }).tasks.length === 1);
  const imp = C.parseImport(JSON.stringify({ app: 'planner', v: 1, data: v1 })), imp2 = C.parseImport(JSON.stringify(leg)), imp3 = C.parseImport(JSON.stringify(m1));
  T('4. Import accepts an old Planner export (v1 wrapped), the first Planner\'s raw data and a v2 file; bad files are refused with a plain sentence', imp.ok && imp.from === 'agora1' && imp.state.tasks.length === 2 && imp2.ok && imp2.state.events.length === 2 && imp3.ok && imp3.from === 'v2' && !C.parseImport('nope').ok && /not a Planner file/.test(C.parseImport('nope').error) && /no Planner plan/.test(C.parseImport('{"a":1}').error) && !C.parseImport('').ok && !C.parseImport('[1]').ok);

  // ---------------------------------------------------------------- 5. .ics
  const si = C.blankState();
  C.addEvent(si, { title: 'Weekly review, with "notes"; ok', day: '2026-11-01', start: '16:30', end: '17:15', repeat: 'weekly', cat: 'trading', remind: 15, note: 'Line one\nLine two' });
  C.addEvent(si, { title: 'All day thing', day: '2026-11-05', repeat: 'daily', until: '2026-11-07' });
  const e3 = C.addEvent(si, { title: 'Daily walk', day: '2026-10-30', start: '17:30', repeat: 'daily' }); C.skipOccurrence(si, e3.id, '2026-11-02');
  C.addEvent(si, { title: 'Pre-session with a very long title that goes on and on and on to force the line folding of the calendar file past 75 octets, with accents é ü and a dash', day: '2026-11-02', start: '01:45' });
  const ics = C.toICS(si, D('2026-11-10T12:00:00Z')), lines = ics.split('\r\n');
  T('5. the .ics text: CRLF lines, VCALENDAR with a New York VTIMEZONE (both clock-change rules), one VEVENT per event, an alarm for the reminder',
    ics.startsWith('BEGIN:VCALENDAR\r\nVERSION:2.0\r\n') && ics.endsWith('END:VCALENDAR\r\n') && !/[^\r]\n/.test(ics) && /BEGIN:VTIMEZONE/.test(ics) && /RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU/.test(ics) && /RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU/.test(ics) && lines.filter((l) => l === 'BEGIN:VEVENT').length === 4 && lines.filter((l) => l === 'END:VEVENT').length === 4 && /BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:[^\r]*\r\nTRIGGER:-PT15M\r\nEND:VALARM/.test(ics));
  T('5. timed events carry TZID=America/New_York (so 09:00 stays 09:00 through Nov 1), repeats become RRULE, an end day becomes UNTIL, the skipped day is an EXDATE, all-day events use VALUE=DATE with the next day as the end',
    lines.includes('DTSTART;TZID=America/New_York:20261101T163000') && lines.includes('DTEND;TZID=America/New_York:20261101T171500') && lines.includes('RRULE:FREQ=WEEKLY') && lines.includes('RRULE:FREQ=DAILY;UNTIL=20261107') && lines.includes('EXDATE;TZID=America/New_York:20261102T173000') && lines.includes('DTSTART;VALUE=DATE:20261105') && lines.includes('DTEND;VALUE=DATE:20261106') && lines.some((l) => l === 'DTEND;TZID=America/New_York:20261102T024500'), lines.filter((l) => /DT|RRULE|EXDATE/.test(l)));
  const unfolded = ics.replace(/\r\n /g, '');
  T('5. text is escaped (comma, semicolon, new line) and long lines are folded under 75 bytes and unfold to the original; no lost characters',
    unfolded.includes('SUMMARY:Weekly review\\, with "notes"\\; ok') && unfolded.includes('DESCRIPTION:Line one\\nLine two') && lines.every((l) => Buffer.byteLength(l) <= 75) && unfolded.includes('accents é ü and a dash'), lines.filter((l) => Buffer.byteLength(l) > 75));
  const nowStamp = lines.find((l) => l.startsWith('DTSTAMP:'));
  T('5. DTSTAMP is the given moment in UTC, UIDs are unique, an empty plan still gives a valid calendar', nowStamp === 'DTSTAMP:20261110T120000Z' && new Set(lines.filter((l) => l.startsWith('UID:'))).size === 4 && C.toICS(C.blankState(), 0).endsWith('END:VCALENDAR\r\n') && C.icsName('2026-11-09') === 'planner-2026-11-09.ics');
  const icsu = C.toICS((() => { const s = C.blankState(); C.addEvent(s, { title: 'Timed until', day: '2026-11-02', start: '09:00', repeat: 'daily', until: '2026-11-05' }); return s; })(), 0);
  T('5. a timed repeat with an end day uses a UTC UNTIL at the end of that New York day', /RRULE:FREQ=DAILY;UNTIL=20261106T045900Z/.test(icsu), icsu.split('\r\n').filter((l) => l.startsWith('RRULE')));

  // ---------------------------------------------------------------- 6. search
  const ss = C.blankState(); const pr = C.addProject(ss, 'Money and bills'); C.addTask(ss, { text: 'Pay the data subscription', day: '2026-11-10', project: pr.id }, TODAY); C.addTask(ss, { text: 'Read the weekly report', day: '' }, TODAY); C.addEvent(ss, { title: 'Weekly review', day: '2026-11-15', note: 'bring the journal' });
  C.addNote(ss, { title: 'Stop rule', text: 'The stop goes beyond the sweep extreme.', tags: ['rules', 'Strategy'] }); C.addNote(ss, { text: 'Weekly idea for the book', tags: ['ideas'] }); C.addGoal(ss, 'Pass the eval'); C.setReview(ss, '2026-11-09', { lesson: 'Waited for the sweep', rating: 'plan' });
  const sr1 = C.search(ss, 'weekly'), sr2 = C.search(ss, 'stop sweep'), sr3 = C.search(ss, '#rules'), sr4 = C.search(ss, 'money'), sr5 = C.search(ss, 'sweep #strategy'), sr6 = C.search(ss, 'journal');
  T('6. search finds across tasks, events, notes, goals, reviews and projects: "weekly" (task, event, note), "stop sweep" (the note), "#rules" (tag), "money" (the project and its task), "journal" (the event note); every word must match',
    sr1.length === 3 && new Set(sr1.map((r) => r.kind)).size === 3 && sr2.length === 1 && sr2[0].kind === 'note' && sr3.length === 1 && sr3[0].title === 'Stop rule' && sr4.map((r) => r.kind).sort().join() === 'project,task' && sr5.length === 1 && sr6.some((r) => r.kind === 'event') && C.search(ss, 'nothing like this').length === 0 && C.search(ss, 'pass eval').length === 1 && C.search(ss, 'waited').some((r) => r.kind === 'review'), [sr1, sr2, sr3]);
  T('6. search ranks a title match above a body match, is case-blind, ignores empty input, and never throws on odd text', C.search(ss, 'WEEKLY')[0].title.toLowerCase().startsWith('weekly') && C.search(ss, '   ').length === 0 && C.search(ss, '#').length === 0 && C.search(ss, '[(*').length === 0 && C.search(ss, 'x'.repeat(500)).length === 0);

  // ---------------------------------------------------------------- 7. the rest of the core
  const bad1 = C.normalise({ events: [null, 5, { title: ' ', day: '2026-11-09' }, { title: 'ok', day: '2026-02-30' }, { id: 'a b!', title: 'E', day: '2026-11-09', start: '9:30', end: '08:00', repeat: 'hourly', remind: 7, cat: 'zzz' }, { id: 'a b!', title: 'dup', day: '2026-11-09' }],
    tasks: [{ id: 't1', text: 'A', parent: 't2' }, { id: 't2', text: 'B', parent: 't1' }, { id: 't3', text: 'C', parent: 'nope', prio: 9, lane: 'x', project: 'zz' }, { text: 'y'.repeat(500) }], habits: [{ name: 'H', perWeek: 9 }], notes: [{ text: '' }, { text: 'n', tags: ['A b', '#ok', 'ok', '<x>'] }], post: { '2026-11-09': { rating: 'bad', mood: 'calm' }, x: {} }, prefs: 5, updated: 'soon' });
  T('7. hostile input never throws: junk rows dropped, ids unique and safe, a bad time or day removed, an end before the start removed, unknown repeat / category / reminder fall back, step loops and missing parents cleared, tags cleaned, long text trimmed',
    bad1.events.length === 2 && bad1.events[0].id === 'ab' && bad1.events[0].start === '' && bad1.events[0].end === '' && bad1.events[0].repeat === 'none' && bad1.events[0].remind === 0 && bad1.events[0].cat === 'other' && bad1.events[1].id !== 'ab' && bad1.tasks.length === 4 && bad1.tasks[0].parent === 't2' === false &&
    bad1.tasks.every((t) => !t.parent || bad1.tasks.some((p) => p.id === t.parent && !p.parent)) && bad1.tasks[2].prio === 0 && bad1.tasks[2].lane === 'next' && bad1.tasks[2].project === '' && bad1.tasks[3].text.length === 200 && bad1.habits[0].perWeek === 7 && bad1.notes.length === 1 && eq(bad1.notes[0].tags, ['ab', 'ok', 'x']) && bad1.post['2026-11-09'].mood === 'calm' && bad1.post['2026-11-09'].rating === '' && bad1.updated === 0 && bad1.prefs.windows === true, bad1);
  T('7. normalise(null / [] / a string) is null; an empty object gives an empty plan', C.normalise(null) === null && C.normalise([]) === null && C.normalise('x') === null && C.normalise({}).tasks.length === 0 && C.normalise({}).v === 2);
  const s7 = C.blankState(); const p7 = C.addProject(s7, 'Trading routine'), g7 = C.addGoal(s7, 'First payout', 'g1');
  const ta = C.addTask(s7, { text: 'Reply to support', day: '2026-11-09', start: '10:00', prio: 3, project: p7.id, goal: g7.id }, TODAY), tb = C.addTask(s7, { text: 'Find ticket', day: '' }, TODAY, { parent: ta.id }), tc = C.addTask(s7, { text: 'Send', day: '' }, TODAY, { parent: ta.id });
  const td = C.addTask(s7, 'Read the book someday', TODAY); td.lane = 'someday'; const te = C.addTask(s7, { text: 'Next week thing', day: '2026-11-16' }, TODAY), tf = C.addTask(s7, { text: 'Old thing', day: '2026-11-02' }, TODAY), tg = C.addTask(s7, { text: 'Parked and dated', day: '2026-11-20', lane: 'someday' }, TODAY);
  C.toggleTask(s7, tb.id); C.toggleTask(s7, te.id);
  const L = C.lanes(s7, TODAY);
  T('7. lanes: due today or earlier (and late ones) are Today, a later due day is Next, Someday stays Someday even when dated, done tasks go to Done; steps ride with their parent and inherit its project and goal; sorted by priority then day',
    eq(L.today.map((t) => t.text), ['Reply to support', 'Old thing']) && L.today[0].subs.length === 2 && L.today[0].subsDone === 1 && L.today[1].late === true && L.next.length === 0 && eq(L.someday.map((t) => t.text), ['Parked and dated', 'Read the book']) && eq(L.done.map((t) => t.text), ['Next week thing']) && tb.project === p7.id && tb.goal === g7.id, L);
  T('7. a step cannot have steps; deleting a task deletes its steps; the lane filter by project; moving a task keeps its lane; setLane changes only the lane',
    C.addTask(s7, { text: 'deep', day: '' }, TODAY, { parent: tb.id }).parent === '' && (() => { const n = s7.tasks.length; C.removeTask(s7, tg.id); return s7.tasks.length === n - 1; })() && C.lanes(s7, TODAY, { project: p7.id }).today.length === 1 && (() => { C.moveTask(s7, tf.id, '2026-11-12'); return C.laneOf(s7.tasks.find((t) => t.id === tf.id), TODAY) === 'next'; })() && C.setLane(s7, td.id, 'next').lane === 'next');
  const ps = C.projectStats(s7, p7.id, TODAY), gp = C.goalProgress(s7, g7);
  T('7. a project says done / open / late / next due and a percent; a goal follows its linked tasks (1 of 1 steps are not counted: only top-level tasks) or a hand-set percent',
    ps.total === 1 && ps.open === 1 && ps.pct === 0 && ps.nextDue === '2026-11-09' && gp.from === 'tasks' && gp.total === 1 && gp.pct === 0 && (() => { C.toggleTask(s7, ta.id); return C.goalProgress(s7, g7).pct === 100; })() && C.goalProgress(C.blankState(), { id: 'g9', pct: 40 }).pct === 40 && C.updateGoal(s7, g7.id, { pct: 250 }).pct === 100);
  const ag = C.argoGoals([{ id: 'g1', name: 'First payout', type: 'payouts', target: 1 }, { id: 'g2', name: '$5,000 paid out', type: 'paid', target: 5000 }, { id: 'g3', name: '', type: 'paid', target: 5 }, { id: 'g4', name: 'x', type: 'month', target: 0 }, null]);
  T('7. Argo goals are read in Argo\'s own format (id, name, type, target) read-only: plain words per type, junk rows dropped, nothing usable gives null', ag.length === 2 && ag[0].text === '1 payout' && ag[1].text === '$5,000 paid out' && C.argoGoals([]) === null && C.argoGoals('x') === null && C.argoGoals({ goals: [{ id: 'a', name: 'n', type: 'funded', target: 3 }] })[0].text === '3 funded accounts' && C.ARGO_STARTERS.length === 5);
  // habits
  const sh = C.blankState(); for (const d of ['2026-11-09', '2026-11-08', '2026-11-07', '2026-11-05', '2026-11-04', '2026-11-03', '2026-11-02', '2026-10-30']) C.toggleHabit(sh, d, 'h1');
  const hm = C.heatmap(sh, TODAY, 12);
  T('7. habits: streak counts back from today (or yesterday; from Fri 6 Nov back only Thu 5 to Mon 2 count = 4), best streak, a weekly heatmap of 12 weeks (oldest first, this week last) with levels against the habit\'s goal per week',
    C.streak(sh, 'h1', '2026-11-09') === 3 && C.streak(sh, 'h1', '2026-11-10') === 3 && C.streak(sh, 'h1', '2026-11-06') === 4 && C.bestStreak(sh, 'h1') === 4 && C.streak(sh, 'h2', TODAY) === 0 && hm.weeks.length === 12 && hm.weeks[11] === '2026-11-09' && hm.weeks[0] === '2026-08-24' &&
    hm.rows[0].cells[11].n === 1 && hm.rows[0].cells[10].n === 6 && hm.rows[0].cells[10].level === 3 && hm.rows[0].cells[9].n === 1 && hm.rows[0].cells[9].level === 1 && hm.rows[0].cells[8].level === 0 && hm.rows[1].cells[10].level === 0, hm.rows[0].cells.slice(8).map((c) => [c.n, c.level]));
  // checklists, review, notes, focus
  const sc = C.blankState(); C.toggleCheck(sc, '2026-11-09', 'c1'); C.toggleCheck(sc, '2026-11-09', 'c2'); C.togglePost(sc, '2026-11-09', 'q1'); C.setReview(sc, '2026-11-09', { rating: 'plan', mood: 'calm', lesson: 'Waited', rule: 'No revenge' }); C.setReview(sc, '2026-11-08', { rating: 'nope' });
  const se = C.sessionsExport(sc, '2026-11-09', 77);
  T('7. the pre-session checklist and post-session review feed Epilogue / Lyceum through planner.sessions.v1: { v:1, days: { day: { pre: {done,total}, post: {rating, mood, lesson, rule, done, total} } } } with the Journal\'s own words; an invalid rating is dropped; nothing older than 90 days',
    se.v === 1 && se.updated === 77 && eq(se.days['2026-11-09'], { pre: { done: 2, total: 6 }, post: { rating: 'plan', mood: 'calm', lesson: 'Waited', rule: 'No revenge', done: 1, total: 4 } }) && !se.days['2026-11-08'] && C.sessionsExport(sc, '2027-03-01', 1).days['2026-11-09'] === undefined && C.RATINGS.map((r) => r[0]).join() === 'plan,hesitated,interfered' && C.MOODS.map((r) => r[0]).join() === 'calm,fomo,revenge,bored,tired', se);
  C.removeChecklist(sc, 'c1', 'checklist'); C.removeChecklist(sc, 'q1', 'postlist');
  T('7. removing a checklist line also clears its ticks; a review with nothing left is removed', sc.checks['2026-11-09'].c2 === true && !sc.checks['2026-11-09'].c1 && !sc.postChecks['2026-11-09'] && (C.setReview(sc, '2026-11-09', { rating: '', mood: '', lesson: '', rule: '' }), sc.post['2026-11-09'] === undefined));
  const sn = C.blankState(); C.setDayNote(sn, '2026-11-09', 'My rule'); C.setDayNote(sn, '2026-11-09', 'My rule 2'); C.setDayNote(sn, '2026-11-08', '  '); const nn = C.addNote(sn, { title: 'T', text: 'body', tags: 'a, #b c', pin: true });
  T('7. one note per day (tagged daily) is edited in place, a blank day note is not created and an emptied one is removed; notes have a title, text, cleaned tags and a pin; tag counts', sn.notes.length === 2 && C.dayNote(sn, '2026-11-09').text === 'My rule 2' && eq(nn.tags, ['a', 'b', 'c']) && nn.pin && C.allTags(sn).length === 4 && (C.setDayNote(sn, '2026-11-09', ''), sn.notes.length === 1) && C.removeNote(sn, nn.id) && sn.notes.length === 0);
  let f = C.focusStart(1000, 'work', 1, 't1');
  T('7. focus timer: 25 minutes of work, 5 off, a 15 minute break after the 4th round, then round 1 again; pause keeps the time left, resume continues; clock text mm:ss',
    f.mins === 25 && C.focusLeft(f, 1000) === 1500 && C.focusLeft(f, 1000 + 25 * 60000) === 0 && C.focusNext(f, 5).phase === 'short' && C.focusNext(f, 5).mins === 5 && C.focusNext(C.focusStart(0, 'work', 4), 0).phase === 'long' && C.focusNext(C.focusStart(0, 'long', 4), 0).round === 1 && C.focusNext(C.focusStart(0, 'short', 2), 0).round === 3 &&
    (() => { const p = C.focusPause(f, 1000 + 600000); return C.focusLeft(p, 99999999) === 900 && C.focusLeft(C.focusResume(p, 5000000), 5000000 + 100000) === 800; })() && C.clockText(1500) === '25:00' && C.clockText(65) === '01:05' && C.cleanFocus({ phase: 'work', endsAt: 5, mins: 25 }).round === 1 && C.cleanFocus({ phase: 'nope', endsAt: 5 }) === null && C.cleanFocus(null) === null);
  const sf = C.blankState(); C.logFocus(sf, '2026-11-09', 25); C.logFocus(sf, '2026-11-09', 25); C.logFocus(sf, 'bad', 25);
  T('7. focus rounds are counted per day (2 rounds, 50 minutes)', eq(sf.focus, { '2026-11-09': { n: 2, min: 50 } }));
  // views
  const sv = C.blankState(); C.addEvent(sv, { title: 'Walk', day: '2026-11-02', start: '17:30', repeat: 'daily', cat: 'health' }); C.addEvent(sv, { title: 'Renews', day: '2026-11-12', cat: 'money' }); C.addTask(sv, { text: 'Timed task', day: '2026-11-12', start: '08:00' }, TODAY);
  const ag2 = C.agenda(sv, '2026-11-12'), mg = C.monthGrid(sv, '2026-11', TODAY, C.normMarket({ events: [{ date: '2026-11-12', time: '08:30', title: 'CPI', impact: 'high', kind: 'cpi' }] }));
  T('7. the day agenda lists all-day items first, then by time, events and timed tasks together; the month grid is 6 weeks Monday to Sunday with category dots, a task count and the market risk of each day',
    eq(ag2.map((a) => a.title), ['Renews', 'Timed task', 'Walk']) && mg.length === 6 && mg.every((r) => r.length === 7) && mg[0][0].day === '2026-10-26' && mg[0][0].inMonth === false && mg[2][3].day === '2026-11-12' && mg[2][3].risk === 'high' && eq(mg[2][3].cats, ['money', 'health']) && mg[2][3].tasks === 1 && mg.flat().filter((c) => c.today).length === 1);
  const sm = C.normMarket({ updated: '2026-11-10', events: [{ date: '2026-11-11', time: '08:30', kind: 'cpi', title: 'CPI', impact: 'high' }, { date: 'x', title: 'bad' }, { date: '2026-11-12', title: 'Holiday', kind: 'holiday', closed: true }], weekly: [{ kind: 'claims', title: 'Jobless claims', dow: 4, time: '08:30', impact: 'low', skip: ['2026-11-26', 'zz'] }, { title: 'bad', dow: 9 }] });
  T('7. Pythia\'s events.json is read in its own shape: dated events, weekly rules with skips, a closed day, a risk colour per day; junk rows dropped; the 14 day lookahead leaves quiet days out',
    sm.events.length === 2 && sm.weekly.length === 1 && C.marketOn(sm, '2026-11-12').length === 2 && C.marketRisk(C.marketOn(sm, '2026-11-12')) === 'closed' && C.marketOn(sm, '2026-11-26').length === 0 && C.marketOn(sm, '2026-11-19')[0].weekly === true && C.marketRisk(C.marketOn(sm, '2026-11-11')) === 'high' && C.marketRisk([]) === 'calm' && C.normMarket({}) === null && C.normMarket(null) === null && C.marketAhead(sm, '2026-11-09', 14).length >= 3);
  const bvr = C.botsView({ live: { model_state: 'LIT is watching <b>levels</b>' }, accounts: [{ id: 'zlarior', eval: { room: 1420, mll: 2000 } }, { name: 'ATLAS', room: 5000, mll: 1000 }, { name: 'BLITZ 25K', room: 960 }, { name: 'other' }] }, null), bvf = C.botsView(null, { line: 'Example', accounts: [{ key: 'zlarior', room: 1420, mll: 2000 }] });
  T('7. the bots\' status and the drawdown left come from home.json (read only): "Drawdown left $1,420 of $2,000 max loss", markup stripped, the room clamped to the max loss; without it the labelled example is used',
    bvr.real && bvr.bot === 'LIT is watching levels' && bvr.accounts.length === 3 && bvr.accounts[0].text === 'Zlarior (MFFU 50K): drawdown left $1,420 of $2,000 max loss' && bvr.accounts[1].room === 1000 && bvr.accounts[2].room === 960 && !bvf.real && bvf.accounts.length === 1 && bvf.bot === 'Example' && C.botsView(undefined, undefined).accounts.length === 0, bvr);
  const sb = C.sessionBlocks('2026-11-09'), sbf = C.sessionBlocks('2026-11-13');
  T('7. the session windows are Kairos\' (London 02:00, New York morning, afternoon to 15:30, no new trades, flat 15:55, CME break 17:00 to 18:00; none at the weekend; no break line on Friday)', sb.length === 7 && sb[1].from === '02:00' && sb.find((w) => w.id === 'nypm').to === '15:30' && sb.find((w) => w.id === 'flat').to === '16:10' && sbf.every((w) => w.id !== 'break') && C.sessionBlocks('2026-11-14').length === 0 && C.sessionBlocks('x').length === 0 && C.MARKS.map((m) => m.at).join() === '02:00,15:30,15:55,16:10');
  const sj = C.blankState(); C.addEvent(sj, { title: 'Call', day: '2026-11-09', start: '10:00', end: '10:30' }); C.addTask(sj, { text: 'Open', day: '2026-11-05' }, TODAY); C.addTask(sj, { text: 'Today', day: '2026-11-09' }, TODAY); C.addProject(sj, 'P');
  const js = C.todaySummary(sj, '2026-11-09', 5);
  T('7. the Jarvis summary (planner.today.v1): the four trading marks then your events, the day\'s tasks and the open late ones, the projects with open and late counts; none of the marks at the weekend', js.v === 1 && js.events.length === 5 && js.events[4].title === 'Call' && js.tasks.length === 2 && js.tasks[1].due === '2026-11-05' && js.projects[0].name === 'P' && C.todaySummary(sj, '2026-11-14', 5).events.length === 0);
  // export / import
  const sx = C.blankState(); C.addEvent(sx, { title: 'E', day: '2026-11-09', start: '10:00', repeat: 'weekly' }); C.addTask(sx, 'Buy milk tomorrow', TODAY); C.addNote(sx, { text: 'hello', tags: ['a'] });
  const text = C.exportText(sx, 1793394000000), back = C.parseImport(text);
  T('7. export is a wrapped file (app planner, v 2, date) and importing it gives back exactly the same plan; a bare plan and a file with a BOM import too; the file name is planner-DAY.json',
    back.ok && eq(back.state, C.normalise(sx)) && JSON.parse(text).app === 'planner' && JSON.parse(text).v === 2 && JSON.parse(text).exported.startsWith('2026-') && C.exportName('2026-11-09') === 'planner-2026-11-09.json' && C.parseImport(JSON.stringify(sx)).ok && C.parseImport('﻿' + text).ok);
  // demo and the fixture
  const fx = JSON.parse(fs.readFileSync(path.join(here, 'fixture.json'), 'utf8')), dm = C.buildDemo(fx, TODAY), mf = C.marketFromFixture(fx, TODAY);
  T('7. the demo plan from fixture.json is never blank: events (with repeats), projects, tasks with steps and priorities in every lane, habits with a history, goals, notes with tags, a past review, a checklist ticked three times, example market events and bot numbers',
    dm.events.length >= 5 && dm.events.some((e) => e.repeat === 'weekly') && dm.projects.length === 3 && dm.tasks.some((t) => t.parent) && dm.tasks.some((t) => t.lane === 'someday') && dm.tasks.some((t) => t.prio === 3) && C.lanes(dm, TODAY).today.length >= 2 && C.lanes(dm, TODAY).next.length >= 2 && dm.habits.length === 3 && Object.keys(dm.habitLog).length > 15 && dm.goals.length === 2 && dm.notes.length === 4 && C.allTags(dm).length >= 5 && Object.keys(dm.post).length === 1 && Object.keys(dm.checks[TODAY]).length === 3 && mf.events.length === 6 && C.botsView(null, fx.bots).accounts.length === 3 && C.buildDemo(null, TODAY).tasks.length === 0 && C.buildDemo({}, 'bad').v === 2 && !!C.normalise(dm), dm);
  T('7. the whole demo survives normalise unchanged (a saved demo would load back identical)', eq(C.normalise(JSON.parse(JSON.stringify(dm))), dm));
  console.log(JSON.stringify(R));
  process.exit(R.some((r) => !r[1]) ? 1 : 0);
}).catch((e) => { console.log(JSON.stringify([['harness error', false, String(e && e.stack || e).slice(0, 600)]])); process.exit(1); });
