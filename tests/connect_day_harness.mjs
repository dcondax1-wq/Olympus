// tests/test_calendar_sync.py part k: olympus/day.js + the Jarvis copilot's Work line + the briefing's day lines, in node.
//   node tests/connect_day_harness.mjs <day.json> <inbox.json> <now ms>      -> one JSON line of results
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const imp = (p) => import(pathToFileURL(path.join(ROOT, 'tools', 'web_public', p)).href);
const Day = await imp('olympus/day.js');
const Cp = await imp('jarvis/copilot.js');
const Br = await imp('jarvis/briefing.js');
const dayJ = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const inbJ = JSON.parse(readFileSync(process.argv[3], 'utf8'));
const now = Number(process.argv[4]);
const out = {};
const D = Day.norm(dayJ);
out.norm = !!D && Object.keys(D.days).length;
out.normBad = [Day.norm(null), Day.norm({ kind: 'x', days: {} }), Day.norm({ kind: 'olympus-day' })].every((x) => x === null);
out.today = Day.today(dayJ, now);
out.missing = Day.today(null, now);
out.old = Day.today({ ...dayJ, t: Math.floor(now / 1000) - 40 * 3600 }, now).state;
out.late = Day.today({ ...dayJ, t: Math.floor(now / 1000) - 2 * 3600 }, now);
out.rows = { a: Day.copilotRow(dayJ, now, '01:45'), b: Day.copilotRow(dayJ, now, '10:45'), c: Day.copilotRow(dayJ, now, '16:05'), none: Day.copilotRow(null, now, '01:45') };
out.said = ['17:00', '12:30', '12:00', '09:30', '00:00', '24:00', 'x'].map(Day.said);
out.brief = Day.briefLine(dayJ, now);
out.weather = Day.weatherLine(dayJ, now);
out.heads = Day.headlines(dayJ, now, 3);
out.inbox = Day.inboxItems(inbJ);
out.inboxBad = [Day.inboxItems(null).length, Day.inboxItems({ kind: 'olympus-inbox', items: [{ id: 'x' }, 'junk', { id: 'y', text: '<b>hi</b>', type: 'note' }] })];
out.evil = Day.today({ ...dayJ, days: { [out.today.day]: { text: '<img src=x onerror=alert(1)>Hi', notes: ['<script>'], work: [{ start: '9am', end: '17:00' }], tone: 'evil' } } }, now);
out.eventsAllDay = Day.eventsOn(dayJ, '2026-11-21').map((e) => e.title);
// the copilot cards with and without the day file (home missing -> the 'missing' card has no Work line by design)
const home = JSON.parse(readFileSync(path.join(ROOT, 'tests', 'fixtures', 'argus', 'home_real.json'), 'utf8'));
const S = { home, day: dayJ, at: { home: now, day: now } };
const cp = Cp.createCopilot({ storage: null });
out.morning = Cp.morningCard(S, now, '01:45');
out.midday = Cp.morningCard(S, now + 9 * 3600e3, '10:45');
out.summary = Cp.dayCard(S, now + 14 * 3600e3);
out.noDay = Cp.morningCard({ home, at: { home: now } }, now, '01:45');
out.match = ["what's my day", 'what is my schedule today', 'do i work today', 'hours worked vs trading', 'when do i work', 'should i trade today'].map((q) => Cp.match(q));
out.answer = cp.ask("what's my day", S, now);
out.answerMissing = cp.ask("what's my day", { home, at: {} }, now);
// the morning briefing with the day lines (buildBrief is pure; the page hands it day = briefLine(...))
out.brf = Br.buildBrief({ accounts: [], plan: null, kalshi: { state: 'missing' } }, { now, day: Day.briefLine(dayJ, now) });
out.brfNone = Br.buildBrief({ accounts: [], plan: null, kalshi: { state: 'missing' } }, { now });
process.stdout.write(JSON.stringify(out) + '\n');
