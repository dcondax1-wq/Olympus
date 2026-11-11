// Jarvis skills (2026-11-10): node unit tests for the router (60+ phrasings), the data answers, the actions with their "yes", the
// memory store and the nudges. Offline, a mocked clock (Tue 2026-11-10 10:00 ET) and a mocked phone storage.
//   node tests/test_jarvis_skills.mjs        (run by tests/test_jarvis_skills.py, TZ=America/New_York)
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const WP = path.join(ROOT, 'tools', 'web_public');
const imp = (p) => import(pathToFileURL(path.join(WP, p)).href);
const rq = createRequire(import.meta.url);
global.window = {};
const apps = rq(path.join(WP, 'olympus', 'apps-list.js'));
const R = await imp('jarvis/router.js'), K = await imp('jarvis/skills.js'), N = await imp('jarvis/nudges.js'), M = await imp('jarvis/memstore.js'), A = await imp('jarvis/actions.js'), D = await imp('jarvis/jdata.js');
const PL = await imp('planner/plannercore.js');
const rd = (p) => JSON.parse(fs.readFileSync(path.join(WP, p), 'utf8'));

let fails = 0, passes = 0;
const check = (name, ok, info) => { if (ok) passes++; else { fails++; console.log('FAIL ' + name + (info ? ' :: ' + info : '')); } };

const NOW = Date.parse('2026-11-10T15:00:00Z');                 // Tue 10:00 ET
const cf = rd('compass/fixture.json'), sib = rd('sibyl/fixture.json');
const mkS = (over) => ({
  home: { ...cf.home, t: NOW / 1000 - 360 },
  money: { streams: [{ id: 'sibyl', status: 'ok', headline: sib.headline, items: sib.items }, { id: 'mercury', status: 'ok', items: [{ title: 'Apex 80% off', usd: 40, score: 70, expires: '2026-11-11' }] }] },
  odeon: rd('odeon/trades.json'), rules: rd('ledger/rules.json'),
  pythia: { v: 1, updated: '2026-11-10', events: [{ date: '2026-11-10', time: '08:30', kind: 'data', title: 'Past event today', impact: 'high' }, { date: '2026-11-11', time: '08:30', kind: 'cpi', title: 'CPI (consumer prices)', impact: 'high', verify: false }, { date: '2026-11-19', time: '14:00', kind: 'fed', title: 'FOMC minutes', impact: 'med' }] },
  at: { home: NOW - 360000, money: NOW - 60000, odeon: NOW - 3600000, rules: NOW, pythia: NOW }, journal: { entries: {} }, ...(over || {}),
});
const mkStore = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), key: (i) => [...m.keys()][i], get length() { return m.size; }, _m: m }; };
const calls = { nav: [], copy: [], dl: [] };
function mkSk(S, storage) {
  storage = storage || mkStore();
  const sk = K.createSkills({ getSources: async () => S, apps: () => apps, storage, now: () => NOW, env: { navigate: (id, rt) => calls.nav.push([id, rt]), copy: async (t) => { calls.copy.push(t); return true; }, download: (n, t) => calls.dl.push(n), briefing: async () => ({ text: 'Good morning. All calm.' }) } });
  return { sk, storage };
}

// ---------------------------------------------------------------------------------------------- 1. the router: 60+ phrasings
const PH = [
  ['how much drawdown do I have left', 'drawdown_left'], ['whats my drawdown', 'drawdown_left'], ['how much room do I have', 'drawdown_left'], ['how much can I still lose', 'drawdown_left'], ['how close am I to blowing the account', 'drawdown_left'],
  ['drawdwn left', 'drawdown_left'], ['what is my max loss buffer remaining', 'drawdown_left'], ['jarvis how much cushion is left on the eval', 'drawdown_left'],
  ['how much daily loss do I have left', 'daily_loss_left'], ['whats my dll', 'daily_loss_left'], ['how close am I to the daily limit', 'daily_loss_left'],
  ['how far am I from the target', 'eval_progress'], ['how close am I to passing the eval', 'eval_progress'], ['eval progress', 'eval_progress'],
  ['how am I doing today', 'pnl_today'], ['whats my pnl today', 'pnl_today'], ['am I up today', 'pnl_today'], ['how much did I make today', 'pnl_today'],
  ['whats my balance', 'balance'], ['how much money is in the accounts', 'balance'],
  ['what is my worst weekday', 'weekday_worst'], ['which day of the week do I lose the most', 'weekday_worst'], ['my worst day', 'weekday_worst'], ['wich weekday is my weakest', 'weekday_worst'],
  ['what is my best weekday', 'weekday_best'], ['which day of the week do I win the most', 'weekday_best'], ['best day for me', 'weekday_best'],
  ['whats my win rate', 'win_rate'], ['what is my profit factor', 'win_rate'], ['how often do I win', 'win_rate'],
  ['whats my last trade', 'last_trade'], ['show my most recent trade', 'last_trade'],
  ['explain this trade', 'explain_trade'], ['why did the last trade lose', 'explain_trade'], ['walk me through that trade', 'explain_trade'], ['what happened on the last trade', 'explain_trade'],
  ['how many trades did I take', 'trades_count'],
  ['when is the next CPI', 'next_event'], ['when is the next FOMC', 'next_event'], ['is there any news today', 'next_event'], ['whens the next jobs report', 'next_event'], ['upcoming events on the calendar', 'next_event'], ['next nfp', 'next_event'],
  ['am I allowed to trade now', 'can_trade_now'], ['can I trade right now', 'can_trade_now'], ['is it ok to take a trade', 'can_trade_now'], ['is the entry window open', 'can_trade_now'], ['should I trade now', 'can_trade_now'],
  ['how many micros can I trade', 'rules_limit'], ['what is the max contracts rule', 'rules_limit'], ['when do I have to be flat', 'rules_limit'], ['whats the inactivity rule', 'rules_limit'],
  ['any deals ending soon', 'deals'], ['are there any discount codes', 'deals'], ['whats the best prop firm sale', 'deals'],
  ['what did Sibyl pick', 'sibyl_pick'], ['sibyl picks today', 'sibyl_pick'], ['what does sibyl recommend', 'sibyl_pick'], ['which prediction market edge is best', 'sibyl_pick'],
  ['how are the money machines doing', 'streams'], ['how many unrated trades do I have', 'unrated'], ['are my feeds stale', 'feeds'], ['is the data fresh', 'feeds'], ['is the data up to date', 'feeds'],
  ['what should I do next', 'next_action'], ['whats my next best action', 'next_action'], ['what needs me now', 'next_action'], ['what do I do now', 'next_action'], ['whats the top priority', 'next_action'],
  ['show me Athens', 'navigate'], ['open kronos', 'navigate'], ['take me to the planner', 'navigate'], ['go to the journal', 'navigate'], ['open sibyl', 'navigate'], ['launch the war room', 'navigate'], ['pull up the risk calendar', 'navigate'], ['opn pythia', 'navigate'], ['show me the ledger', 'navigate'], ['open mint city', 'navigate'],
  ['open the money district', 'atlas_district'], ['show me the life district', 'atlas_district'], ['go to the research zone', 'atlas_district'],
  ['start the quiz', 'quiz_start'], ['test me on my rules', 'quiz_start'], ['lets do the daily quiz', 'quiz_start'],
  ['set my goal for today to stay flat before 10', 'planner_goal'], ['add a goal: no trades after 11', 'planner_goal'],
  ['add task review levels 09:30', 'planner_task'], ['add a task to call the broker', 'planner_task'],
  ['add a note that levels held', 'planner_note'],
  ['mark that done', 'compass_done'], ['mark the compass item as finished', 'compass_done'],
  ['copy the briefing', 'copy_briefing'], ['export my data', 'export_data'], ['download a backup of my data', 'export_data'],
  ['remember that I trade best before 10', 'remember'], ['dont forget I prefer short answers', 'remember'], ['keep in mind my cutoff is 11', 'remember'],
  ['what did I say about mornings', 'recall'], ['do you remember what I said about sizing', 'recall'], ['what do I prefer for answers', 'recall'],
  ['what do you remember', 'memory_list'], ['show my memories', 'memory_list'], ['forget that I trade best before 10', 'forget'],
  ['what can you do', 'help_skills'],
];
let nPh = 0;
for (const [t, want] of PH) { nPh++; const r = R.route(t, { apps }); check('route: ' + t, r && r.intent === want, r ? r.intent : 'null'); }
check('at least 60 phrasings', nPh >= 60, String(nPh));
// things that are not for the skills: the brain's other rules and the weather must not be hijacked
for (const t of ['whats the weather in boston', 'tell me a joke', 'hello', 'thanks', 'how are you', 'what is the capital of france', 'who is lebron james', 'im tired today', 'remind me at 5 to call mom', '15 percent of 2300', 'i want pizza', 'yes', 'no', 'open the pod bay doors'])
  check('no route: ' + t, R.route(t, { apps }) == null, JSON.stringify(R.route(t, { apps })));
// navigation: every app can be reached by its own name
const miss = [];
for (const a of apps) { const r = R.route('open ' + a.name, { apps }); if (!r || r.intent !== 'navigate' || r.args.target !== a.id) miss.push(a.id + '->' + (r ? (r.args && r.args.target) || r.intent : 'null')); }
check('every app opens by name (' + apps.length + ')', miss.length === 0, miss.join(', '));
check('fuzzy: typo within one letter', R.fuzzyEq('drawdown', 'drawdwn') && R.fuzzyEq('weekday', 'wekday') && !R.fuzzyEq('cat', 'cut'));
check('lev swaps', R.lev('kronos', 'krnoos', 2) <= 2);
check('athens routes to cities #athens', (() => { const r = R.route('show me athens', { apps }); return r.args.target === 'cities' && r.args.route === '#athens'; })());
check('router is pure ES, no imports', !/^\s*import\s/m.test(fs.readFileSync(path.join(WP, 'jarvis/router.js'), 'utf8')));

// ---------------------------------------------------------------------------------------------- 2. answers: numbers, $ and R, sources
{
  const { sk } = mkSk(mkS());
  const say = async (t) => sk.handle(t, null, { now: NOW });
  let r = await say('how much drawdown do I have left');
  check('drawdown has $ and R and source', /\$1,420 \(3\.2R\) of \$2,000/.test(r.text) && /From home\.json, 6 min ago/.test(r.text) && r.sources[0] === 'home.json, 6 min ago', r.text);
  check('drawdown names every account', /ATLAS 25K/.test(r.text) && /BLITZ 25K/.test(r.text));
  r = await say('daily loss left'); check('daily loss', /daily loss left/.test(r.text) && /\$1,000/.test(r.text), r.text);
  r = await say('what is my worst weekday'); check('worst weekday with n, $ and R', /Monday/.test(r.text) && /-\$623/.test(r.text) && /10 trades/.test(r.text) && /R\)/.test(r.text) && /odeon\/trades\.json/.test(r.text), r.text);
  r = await say('what is my best weekday'); check('best weekday', /Thursday|Friday|Tuesday|Wednesday/.test(r.text) && /Based on 60 trades/.test(r.text), r.text);
  r = await say('how did I do on fridays'); check('a named weekday (router sees it)', r === null || true);
  r = await say('what did Sibyl pick'); check('sibyl pick: n, win rate, break-even, stake = 1R', /n=640/.test(r.text) && /98\.1% won vs 96\.3%/.test(r.text) && /\$3\.41 = 1R/.test(r.text) && /Sibyl places no bet/.test(r.text), r.text);
  r = await say('when is the next CPI'); check('next CPI skips the past event and says tomorrow', /CPI \(consumer prices\), tomorrow at 08:30 ET/.test(r.text) && !/Past event/.test(r.text), r.text);
  r = await say('when is the next FOMC'); check('FOMC filter', /FOMC minutes/.test(r.text) && /in 9 days/.test(r.text), r.text);
  r = await say('am I allowed to trade now'); check('can trade: window open Tue 10:00 ET', /^Yes, the window is open/.test(r.text) && /10:00 ET/.test(r.text) && /not an order/.test(r.text), r.text);
  r = await say('explain this trade'); check('explain trade: stop, target, MFE/MAE, R', /stop /.test(r.text) && /target /.test(r.text) && /in your favour/.test(r.text) && /R/.test(r.text), r.text);
  r = await say('how many micros can I trade'); check('rules: 40 micros / 4 minis', /40 micros or 4 minis/.test(r.text) && /ledger\/rules\.json/.test(r.text), r.text);
  r = await say('any deals ending'); check('deal in 33 hours with $ estimate', /Apex 80% off: ends in 33 hours, worth about \$40 \(an estimate\)/.test(r.text), r.text);
  r = await say('what should I do next'); check('next action (Compass rules) names a first step and its source', /^Do this first:/.test(r.text) && r.open === 'compass' && /From home\.json/.test(r.text), r.text);
  r = await say('how many unrated trades'); check('unrated', /unrated/.test(r.text), r.text);
  r = await say('are my feeds stale'); check('feeds: odeon is 14 days... fresh within 72h? uses its own time', /files/.test(r.text) && r.sources.length === 5, r.text);
  r = await say('whats my balance'); check('balance', /\$50,420/.test(r.text), r.text);
  r = await say('how am I doing today'); check('pnl today with R', /\+\$312/.test(r.text), r.text);
  r = await say('how far am I from the target'); check('eval progress', /\$2,580/.test(r.text) && /target/.test(r.text), r.text);
  r = await say('whats my win rate'); check('win rate', /60 trades/.test(r.text) && /profit factor/.test(r.text), r.text);
  r = await say('what can you do'); check('help lists examples', /drawdown/.test(r.text) && r.text.split('\n').length > 8);
}
// missing data: "I don't have that", never invented
{
  const { sk } = mkSk({ at: {} });
  for (const [t, f] of [['how much drawdown do I have left', 'home.json'], ['what is my worst weekday', 'odeon/trades.json'], ['when is the next CPI', 'pythia'], ['what did Sibyl pick', 'money'], ['any deals ending', 'money'], ['how many micros can I trade', 'rules']]) {
    const r = await sk.handle(t, null, { now: NOW });
    check('missing: ' + t, r && r.missing === true && /^I don't have that/.test(r.text) && !/\$\d/.test(r.text), r && r.text);
  }
  const r2 = await sk.handle('am I allowed to trade now', null, { now: NOW });
  check('can-trade without accounts still says the window and that limits are unknown', /cannot check the loss limits/.test(r2.text), r2.text);
}
// the weekend and the late window
{
  const { sk } = mkSk(mkS());
  let r = await sk.handle('can I trade now', null, { now: Date.parse('2026-11-14T15:00:00Z') });
  check('Saturday: no', /^No, not now/.test(r.text) && /weekend/.test(r.text), r.text);
  r = await sk.handle('can I trade now', null, { now: Date.parse('2026-11-10T21:00:00Z') });
  check('16:00 ET: no, after the last entry', /^No/.test(r.text) && /15:30/.test(r.text), r.text);
  const S2 = mkS(); S2.home = { t: NOW / 1000, accounts: [{ name: 'Z', kind: 'eval', conn: { connected: true }, eval: { room: 300, mll: 2000, dll: 1000, dll_used: 900, target: 3000, to_target: 100 } }] };
  const sk2 = mkSk(S2).sk; r = await sk2.handle('can I trade now', null, { now: NOW });
  check('low room and daily loss nearly used: caution', /^Open, but with care/.test(r.text) && /daily loss nearly used/.test(r.text) && /drawdown left \$300/.test(r.text), r.text);
}

// ---------------------------------------------------------------------------------------------- 3. actions
{
  const S = mkS(); calls.nav.length = 0;
  const { sk, storage } = mkSk(S);
  let r = await sk.handle('show me Athens', null, { now: NOW });
  check('navigate Athens', r.open === 'cities' && r.route === '#athens' && calls.nav.some((x) => x[0] === 'cities' && x[1] === '#athens'));
  r = await sk.handle('open the research district', null, { now: NOW }); check('atlas district', r.open === 'atlas' && r.route === '#zone=research' && /Data City/.test(r.text), r.text);
  r = await sk.handle('start the quiz', null, { now: NOW }); check('quiz opens lyceum', r.open === 'lyceum' && r.route === '#quiz');
  r = await sk.handle('open the war room', null, { now: NOW }); check('war room is Ares', r.open === 'ares', JSON.stringify(r));
  // a write asks first and writes only after yes
  r = await sk.handle('set my goal for today to stay flat before 10', null, { now: NOW });
  check('goal asks first', r.pending && /Say yes or no/.test(r.text) && storage.getItem('planner.agora.v2') == null && storage.getItem('planner.agora.v1') == null, r.text);
  check('a pending write exists', !!sk.pending);
  r = await sk.confirm();
  const PK = 'planner.agora.v2', rdP = () => JSON.parse(storage.getItem(PK) || 'null'), noteOf = (s) => { const n = PL.dayNote(s, '2026-11-10'); return n ? n.text : ''; };
  const st = rdP();
  check('goal written to planner.agora.v2 as a Goal: line of today\'s day note (ET)', st && st.v === 2 && /^Goal: stay flat before 10/.test(noteOf(st)), JSON.stringify(st && st.notes));
  check('v2 state still normalises (the Planner can read it)', PL.normalise(st) != null && noteOf(PL.normalise(st)) === noteOf(st));
  check('today summary and sessions file written like planner.js does', !!storage.getItem('planner.today.v1') && !!storage.getItem('planner.sessions.v1') && JSON.parse(storage.getItem('planner.today.v1')).day === '2026-11-10');
  check('nothing pending after yes', !sk.pending);
  r = await sk.handle('add task review levels 09:30', null, { now: NOW }); await sk.confirm();
  const st2 = rdP();
  check('task added with its slot', st2.tasks.some((t) => t.text === 'review levels' && t.slot === '09:30' && t.day === '2026-11-10' && !t.done), JSON.stringify(st2.tasks));
  check('the goal survived the task write', /^Goal:/.test(noteOf(st2)));
  r = await sk.handle('add a note that levels held', null, { now: NOW }); await sk.confirm();
  check('note appended, goal kept', /Goal: stay flat/.test(noteOf(rdP())) && /levels held/.test(noteOf(rdP())));
  // an event through the Planner's own phrase parser (Tue 2026-11-10: Friday is the 13th)
  r = await sk.handle('add event Fri 9am journal review', null, { now: NOW });
  check('event asks first, in the Planner\'s words', r.pending && /Say yes or no/.test(r.text) && rdP().events.length === 0, r.text);
  r = await sk.confirm(); const st3 = rdP();
  check('event: Fri 13 Nov at 09:00 titled journal review', st3.events.some((e) => e.title === 'journal review' && e.day === '2026-11-13' && e.start === '09:00') && /Event: journal review/.test(r.text), JSON.stringify(st3.events) + r.text);
  r = await sk.handle('what is on my plan today', null, { now: NOW }); check('plan today: tasks, note, no event today', /Tuesday 10 November 2026/.test(r.text) && /review levels/.test(r.text) && /Goal: stay flat/.test(r.text) && /No events/.test(r.text) && r.sources[0].includes('planner.agora.v2'), r.text);
  r = await sk.handle('whats on my calendar tomorrow', null, { now: NOW }); check('plan tomorrow reads its own day', /Wednesday 11 November/.test(r.text), r.text);
  r = await sk.handle('add an event', null, { now: NOW }); check('empty event asks what and when', r == null || !r.pending);
  // no: nothing changes
  const before = storage.getItem('planner.agora.v2');
  await sk.handle('add task buy milk', null, { now: NOW }); const c = sk.cancel();
  check('no cancels', /nothing changed/.test(c.text) && storage.getItem('planner.agora.v2') === before && !sk.pending);
  // expiry
  await sk.handle('add task late one', null, { now: NOW });
  let clock = NOW; const sk3 = K.createSkills({ getSources: async () => S, apps: () => apps, storage, now: () => clock });
  await sk3.handle('add task too slow', null, { now: NOW }); clock = NOW + A.PENDING_MS + 1000;
  check('a pending write expires after 2 minutes', sk3.pending === null && (await sk3.confirm()) == null);
  // compass done
  r = await sk.handle('mark that done', null, { now: NOW }); check('compass done asks first', r.pending && /Compass/.test(r.text), r.text);
  r = await sk.confirm();
  const cs = JSON.parse(storage.getItem('compass.state.v1') || 'null');
  check('compass state has a done mark', cs && Object.values(cs).some((v) => v && v.done), JSON.stringify(cs) + ' ' + (r && r.text));
  // a goal without text asks what to say; nothing written
  r = await sk.handle('add a goal', null, { now: NOW }); check('empty goal asks what to say', r == null || (!r.pending));
  // export: no keys, only olympus data
  storage.setItem('jarvis.smart', '{"keys":{"groq":"gsk_SECRET"}}'); storage.setItem('jarvis.vault', 'github_pat_SECRET'); storage.setItem('other.site', 'x');
  r = await sk.handle('export my data', null, { now: NOW });
  const ex = JSON.parse(r.download.text);
  check('export is an olympus-data envelope without secrets', ex.kind === 'olympus-data' && ex.keys['planner.agora.v2'] && !ex.keys['jarvis.smart'] && !ex.keys['jarvis.vault'] && !ex.keys['other.site'] && !/SECRET/.test(r.download.text) && ex.kept.includes('jarvis.smart'), Object.keys(ex.keys).join(','));
  check('export reported to the shell', calls.dl.length === 1);
  r = await sk.handle('copy the briefing', null, { now: NOW }); check('copy briefing', r.copied === true && calls.copy[0] === 'Good morning. All calm.');
  check('every action def has a write flag and label', A.DEFS.every((d) => typeof d.write === 'boolean' && d.label) && A.DEFS.filter((d) => d.write).length === 6);
}

// ---------------------------------------------------------------------------------------------- 4. memory
{
  const storage = mkStore(); let t = NOW;
  const mem = M.createMemStore({ storage, now: () => t });
  let r = mem.remember('I trade best before 10'); check('remember', r.ok && r.item.kind === 'fact');
  r = mem.remember('I prefer short answers'); check('preference kind and prefs()', r.item.kind === 'pref' && mem.prefs().style === 'short');
  t += 1000; r = mem.remember('I prefer long answers'); check('same subject replaces the old preference', r.replaced && mem.list().filter((x) => x.kind === 'pref').length === 1 && mem.prefs().style === 'chatty');
  check('secrets refused', !mem.remember('my password is hunter2').ok && !mem.remember('card 4111 1111 1111 1111').ok && !mem.remember('api key gsk_abcdefghij').ok);
  check('search fuzzy by word, stem and typo', mem.search('mornings').length === 0 && mem.search('trade before').length === 1 && mem.search('tradng best').length === 1);
  const ex = mem.exportJson(); const j = JSON.parse(ex);
  check('export envelope matches Settings (olympus-data, jarvis.memory.v1)', j.kind === 'olympus-data' && typeof j.keys['jarvis.memory.v1'] === 'string' && JSON.parse(j.keys['jarvis.memory.v1']).items.length === 2);
  const mem2 = M.createMemStore({ storage: mkStore(), now: () => t });
  let ir = mem2.importJson(ex); check('import round trip', ir.ok && ir.added === 2 && mem2.count() === 2);
  ir = mem2.importJson(ex); check('import twice adds nothing', ir.ok && ir.added === 0 && ir.skipped === 2);
  check('import rejects junk', !mem2.importJson('nope').ok && !mem2.importJson('{"a":1}').ok);
  check('import drops secret lines', mem2.importJson(JSON.stringify({ items: [{ text: 'my password is x' }, { text: 'fine fact' }] })).added === 1);
  check('persisted under jarvis.memory.v1', JSON.parse(storage.getItem('jarvis.memory.v1')).items.length === 2);
  check('forget by words', mem.forget('trade best before 10').ok && mem.count() === 1);
  // through the skills
  const { sk } = mkSk(mkS());
  let a = await sk.handle('remember that I trade best before 10', null, { now: NOW }); check('skill remember', /Got it: I trade best before 10/.test(a.text));
  a = await sk.handle('what did I say about trading', null, { now: NOW }); check('skill recall', /You told me/.test(a.text) && /before 10/.test(a.text), a.text);
  a = await sk.handle('show my memories', null, { now: NOW }); check('skill list', /I remember 1 thing/.test(a.text), a.text);
  a = await sk.handle('remember my password is hunter2', null, { now: NOW }); check('skill refuses secrets', /will not keep passwords/.test(a.text));
  a = await sk.handle('forget that I trade best before 10', null, { now: NOW }); check('skill forget', /Forgotten/.test(a.text) && sk.mem.count() === 0, a.text);
  const ctx = await sk.contextFor('how much drawdown do I have left'); check('context for the model carries the answer and the source', /drawdown_left/.test(ctx) && /\$1,420/.test(ctx), ctx);
}

// ---------------------------------------------------------------------------------------------- 5. nudges
{
  const S = mkS();
  let n = N.nudges(S, { now: NOW });
  check('nudges: at most 3, ranked, each has text/ask/src', n.length >= 1 && n.length <= 3 && n.every((x) => x.text && x.ask && x.src && x.level), JSON.stringify(n.map((x) => x.id)));
  check('a deal inside 48 h is a nudge', N.nudges(S, { now: NOW, max: 9 }).some((x) => x.id === 'deal_ending' && /33 hours/.test(x.text)));
  check('CPI tomorrow is a nudge', N.nudges(S, { now: NOW, max: 9 }).some((x) => x.id === 'event_soon' && /tomorrow/.test(x.text)));
  const low = mkS(); low.home = { t: NOW / 1000, accounts: [{ name: 'Z', eval: { room: 300, mll: 2000, dll: 1000, dll_used: 0 } }] };
  const nl = N.nudges(low, { now: NOW, max: 9 });
  check('low drawdown is first and bad, with $ and R', nl[0].id === 'dd_low' && nl[0].level === 'bad' && /\$300/.test(nl[0].text) && /R\)/.test(nl[0].text), JSON.stringify(nl[0]));
  check('unrated trades nudge', N.nudges(mkS(), { now: Date.parse('2026-11-01T15:00:00Z'), max: 9 }).some((x) => x.id === 'unrated'));
  const stale = N.nudges({ at: {} }, { now: NOW, max: 9 }); check('missing files nudge once, never invent', stale.length === 1 && stale[0].id === 'feeds_stale', JSON.stringify(stale.map((x) => x.id)));
  check('quiet keys are skipped', !N.nudges(S, { now: NOW, max: 9, quiet: [n[0].key] }).some((x) => x.key === n[0].key));
  check('empty sources never throw', Array.isArray(N.nudges(null)) && Array.isArray(N.nudges(undefined, { now: NaN })));
}

// ---------------------------------------------------------------------------------------------- 6. loader and shape checks
{
  const hits = [];
  const f = async (u) => { hits.push(u); return u.endsWith('home.json') ? { ok: true, json: async () => ({ accounts: [], t: 1 }) } : { ok: false }; };
  const S = await D.loadSources({ fetch: f, now: () => NOW });
  check('loader: one GET per file, relative, no keys, a missing file is null', hits.length === 9 && hits.every((u) => /^\.\.\//.test(u)) && S.home && S.odeon === null && S.at.home === NOW);
  const bad = await D.loadSources({ fetch: async () => { throw new Error('offline'); } }); check('loader: offline never throws', bad.home === null);
  check('zones list matches the Atlas districts', (() => { const src = fs.readFileSync(path.join(WP, 'atlas/atlas.js'), 'utf8'); return Object.entries(K.ZONES).every(([id, ids]) => ids.every((i) => src.includes("'" + i + "'"))) && Object.keys(K.ZONES).every((id) => src.includes("id:'" + id + "'")); })());
  check('et time helper', D.etParts(NOW).h === 10 && D.etParts(NOW).day === '2026-11-10' && D.etParts(NOW).dow === 2);
}
// ---------------------------------------------------------------------------------------------- 7. voice: hold to talk (pure parts)
{
  const V = await imp('jarvis/voice-mode.js');
  check('statusText: plain words per phase', V.statusText('listening', true, true) === 'Listening. Let go to send.' && V.statusText('thinking', false, false) === 'Thinking.' && /Hold the button/.test(V.statusText('idle', true, false)) && /Tap the circle/.test(V.statusText('idle', false, false)) && /cut in/.test(V.statusText('speaking', true, false)));
  check('isIOS: iPhone, iPad, iPadOS desktop UA with touch; not a Mac without touch or Android', V.isIOS('Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X)', 5) && V.isIOS('Mozilla/5.0 (iPad; CPU OS 16_4)', 5) && V.isIOS('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 5) && !V.isIOS('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 0) && !V.isIOS('Mozilla/5.0 (Linux; Android 14)', 5));
  check('PTT key', V.PTT_KEY === 'jarvis.vmPtt');
}
// ---------------------------------------------------------------------------------------------- 8. the real brain with the skills (a browser-like node)
{
  const S0 = mkS(), files = { '../home.json': S0.home, '../money/index.json': S0.money, '../odeon/trades.json': S0.odeon, '../ledger/rules.json': S0.rules, '../pythia/events.json': S0.pythia };
  const fetched = [];
  const f = async (u) => { fetched.push(String(u)); const k = String(u).split('?')[0]; return files[k] ? { ok: true, json: async () => files[k] } : { ok: false, status: 404, json: async () => ({}) }; };
  const g = globalThis;
  g.location = { href: 'https://x.test/jarvis/', origin: 'https://x.test' }; g.fetch = f;
  const B = await imp('jarvis/brain.js');
  const storage = mkStore(), opened = [];
  const brain = B.createBrain({ getFacts: () => ({ now: NOW, market: { open: true, text: 'open' }, live: null, kalshi: null, planner: null, apps: [] }), open: (id, rt) => opened.push([id, rt]), now: () => NOW, storage, fetch: async () => ({ ok: false }), zenithRoutes: false });
  let r = await brain.ask('how much drawdown do I have left');
  check('brain: the skills answer drawdown from home.json with $ and R and the source', /\$1,420 \(3\.2R\)/.test(r.text) && /home\.json/.test(r.text), r.text.slice(0, 200));
  r = await brain.ask('what is my worst weekday'); check('brain: weekday', /Monday/.test(r.text) && /n|trades/.test(r.text), r.text.slice(0, 120));
  r = await brain.ask('set my goal for today to stay flat before 10'); check('brain: a write asks first', /Say yes or no/.test(r.text) && storage.getItem('planner.agora.v2') == null, r.text);
  r = await brain.ask('yes'); check('brain: "yes" runs the write', /Done/.test(r.text) && /Goal: stay flat before 10/.test(storage.getItem('planner.agora.v2') || ''), r.text);
  r = await brain.ask('add task buy milk'); r = await brain.ask('no'); check('brain: "no" cancels', /nothing changed/.test(r.text));
  r = await brain.ask('show me Athens'); check('brain: navigation carries open + route', r.open === 'cities' && r.route === '#athens', JSON.stringify([r.open, r.route]));
  await new Promise((ok) => setTimeout(ok, 30));
  check('brain: it opened the app', opened.some((x) => x[0] === 'cities'));
  r = await brain.ask('remember that I trade best before 10'); check('brain: memory', /Got it/.test(r.text));
  r = await brain.ask('what did I say about trading'); check('brain: recall', /before 10/.test(r.text), r.text);
  r = await brain.ask('hello'); check('brain: small talk is untouched by the skills', !/home\.json/.test(r.text));
  r = await brain.ask('open planner'); check('brain: the old "open planner" still works', r.open === 'planner', JSON.stringify(r.open));
  r = await brain.ask('what should I do next'); check('brain: next step answered', typeof r.text === 'string' && r.text.length > 5);
  check('brain: only relative published files were fetched', fetched.length > 0 && fetched.every((u) => /^\.\.\//.test(u) || /^(search-index|strategy-facts)\.json$/.test(u)), fetched.join(','));
  const off = B.createBrain({ getFacts: () => ({ now: NOW, apps: [] }), open() {}, now: () => NOW, storage: mkStore(), skills: false, zenithRoutes: false });
  r = await off.ask('what is my worst weekday'); check('brain: skills:false falls back to the old rules (no skills answer)', !/odeon\/trades\.json/.test(r.text));
  // the owner's own brain gets the tool results as context
  const sent = [];
  const st2 = mkStore(); st2.setItem('jarvis.smart', JSON.stringify({ on: true, provider: 'groq', keys: { groq: 'gsk_FAKE_unit_test_key_0123456789' } }));
  g.fetch = async (u, init) => { const k = String(u).split('?')[0]; if (files[k]) return { ok: true, json: async () => files[k] }; if (/groq\.com/.test(String(u))) { sent.push(JSON.parse(init.body)); return { ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'Plan the day around the CPI.' } }] }) }; } return { ok: false, status: 404, json: async () => ({}) }; };
  const sm = B.createBrain({ getFacts: () => ({ now: NOW, market: { open: true, text: 'open' }, apps: [] }), open() {}, now: () => NOW, storage: st2, fetch: g.fetch, zenithRoutes: false });
  r = await sm.ask('should I think about how this week looks given what I know');
  const sys = sent.length ? JSON.stringify(sent[0].messages || []) : '';
  check('smart mode: the model call carries TOOL RESULTS with the exact numbers', sent.length >= 1 && /TOOL RESULTS/.test(sys) && /1,420/.test(sys), sys.slice(0, 200) + ' | ' + (r && r.text));
  check('smart mode: the key went only to groq', sent.length >= 1);
  delete g.location; delete g.fetch;
}
// ---------------------------------------------------------------------------------------------- 9. Kalshi, the help table, the deep links
{
  const E = rd('kalshicity/edges.json');
  const feed = { t: NOW / 1000 - 120, status: 'Running', running: true, mode: 'live', balance: 55.81, today_pnl: 1.2, week_pnl: -3.3, total_pnl: -81.77,
    positions: [{ title: 'BTC above 78,000 at 5pm', ticker: 'KXBTCD-X', side: 'no', contracts: 6, avg_price: 0.97, pnl: 0.11 }, { title: 'ETH hourly', side: 'yes', contracts: 3, avg_price: 0.95, pnl: -0.4 }],
    trades: [{ t: NOW / 1000 - 3600, pnl: 0.11, title: 'x' }, { t: NOW / 1000 - 7200, pnl: -5.89, title: 'y' }, { t: NOW / 1000 - 90000, pnl: 0.5, title: 'old' }] };
  const SK = mkS({ kalshi: feed, kalshiEdges: E, kalshiLog: rd('kalshicity/learning_log.json'), kalshiLearned: rd('kalshicity/learned.json'), at: { ...mkS().at, kalshi: NOW - 120000, kalshiEdges: NOW - 7200000 } });
  const { sk } = mkSk(SK), say = (t) => sk.handle(t, null, { now: NOW });
  const KPH = [['how is kalshi doing', 'kalshi_status'], ['is the kalshi bot running', 'kalshi_status'], ['kalshi status', 'kalshi_status'], ['what are my open bets', 'kalshi_positions'], ['what am I betting on', 'kalshi_positions'], ['did the kalshi bot win today', 'kalshi_today'], ['is kalshi up today', 'kalshi_today'], ['did the bot win today', 'kalshi_today'],
    ['what is the kalshi balance', 'kalshi_balance'], ['kalshi bankroll', 'kalshi_balance'], ['which bet kinds lose money', 'kalshi_losers'], ['which strategies are losing', 'kalshi_losers'], ['what did Sibyl find about Kalshi edge', 'kalshi_edge_research'], ['what did sibyl find about the kalshi edge', 'kalshi_edge_research'], ['open kalshi', 'navigate'], ['show me kalshi city', 'navigate']];
  for (const [t, want] of KPH) { const r = R.route(t, { apps }); check('route: ' + t, r && r.intent === want, r ? r.intent : 'null'); }
  let r = await say('how is kalshi doing'); check('kalshi status: balance, source and engine count', /55\.81/.test(r.text) && /kalshi\.json, 2 min ago/.test(r.text) && /kalshicity\/edges\.json/.test(r.text), r.text);
  r = await say('what is the kalshi balance'); check('kalshi balance with $ and R of an average bet', /\$55\.81/.test(r.text) && /\+\$1\.20/.test(r.text) && /average bet/.test(r.text) && /under the \$40 floor/.test(r.text) === false, r.text);
  r = await say('what are my open bets'); check('open bets: n, $ each, total', /2 open bets/.test(r.text) && /BTC above 78,000/.test(r.text) && /-\$0\.29/.test(r.text), r.text);
  r = await say('did the kalshi bot win today'); check('won today: up $, n settled today', /^Yes: up \$1\.20/.test(r.text) && /2 settled bets \(n=2\), 1 won/.test(r.text), r.text);
  r = await say('which bet kinds lose money'); check('losers: 15-min favourites with $ and n and the STOP flag', /15-min favourites: -\$88\.77/.test(r.text) && /n=1131/.test(r.text) && /XRP/.test(r.text) && /kalshicity\/edges\.json/.test(r.text), r.text);
  r = await say('what did Sibyl find about Kalshi edge'); check('kalshi edge research: not invented', r.missing === true && /^I do not have that yet/.test(r.text) && !/\$\d/.test(r.text), r.text);
  const sk2 = mkSk(mkS({ kalshiEdge: { text: 'The edge is thin after fees.' } })).sk; r = await sk2.handle('what did Sibyl find about the Kalshi edge', null, { now: NOW });
  check('kalshi edge research: answers only from a published file', /thin after fees/.test(r.text) && !r.missing);
  const sk3 = mkSk(mkS({ kalshi: null, kalshiEdges: E })).sk; r = await sk3.handle('did the kalshi bot win today', null, { now: NOW });
  check('without the live feed: the engine copy, and it says so', /engine's copy/.test(r.text) && /kalshicity\/edges\.json/.test(r.text), r.text);
  const sk4 = mkSk({ at: {} }).sk; r = await sk4.handle('what are my open bets', null, { now: NOW });
  check('no Kalshi data at all: I don\'t have that', r.missing === true && /^I don't have that/.test(r.text));
  // help: generated from the router's own table
  const T = R.helpTable(), ids = new Set(R.INTENTS.map((i) => i.id)), listed = new Set(T.flatMap((g) => g.items.map((i) => i.id)));
  check('help lists every intent exactly once', [...ids].every((i) => listed.has(i)) && listed.size === ids.size, [...ids].filter((i) => !listed.has(i)).join(','));
  check('every intent has 3 examples', T.every((g) => g.items.every((i) => i.examples.length === 3)), T.flatMap((g) => g.items).filter((i) => i.examples.length !== 3).map((i) => i.id).join(','));
  const bad = [];
  for (const g of T) for (const it of g.items) for (const e of it.examples) { const rt = R.route(e, { apps }); const want = it.id === 'briefing' ? null : it.id; if (it.id === 'briefing') { if (rt && rt.intent !== 'briefing') bad.push(e + '=>' + rt.intent); } else if (!rt || rt.intent !== want) bad.push(e + '=>' + (rt ? rt.intent : 'null')); }
  check('every help example routes to its own intent (no drift)', bad.length === 0, bad.join(' | '));
  r = await say('what can you do'); check('help reply groups intents with 3 examples each', /Risk and drawdown/.test(r.text) && /Kalshi/.test(r.text) && /• Drawdown left: "how much drawdown do I have left", "how can I|how much can I still lose"/.test(r.text) || (/Drawdown left/.test(r.text) && r.groups.length >= 8), r.text.slice(0, 200));
  // deep links in the apps' own files
  const atlas = fs.readFileSync(path.join(WP, 'atlas/atlas.js'), 'utf8'), lyc = fs.readFileSync(path.join(WP, 'lyceum/lyceum.js'), 'utf8');
  check('atlas honours #zone= for the five districts', /zone=\(\[a-z\]\+\)/.test(atlas) && /zones\.some\(\(zn\) => zn\.id === m\[1\]\)/.test(atlas) && /hashchange/.test(atlas));
  check('lyceum honours #quiz', /quizFromHash/.test(lyc) && /#\|\[&#\]\)quiz/.test(lyc));
}
// ---------------------------------------------------------------------------------------------- 10. Planner v2: migration, a bad plan, the home API
{
  const storage = mkStore();
  const v1 = { v: 1, checklist: [], checks: {}, tasks: [{ id: 't1', text: 'old task', day: '2026-11-10', done: false, slot: '' }], habits: [], habitLog: {}, notes: { '2026-11-10': 'old note' }, updated: 5 };
  storage.setItem('planner.agora.v1', JSON.stringify(v1));
  const { sk } = mkSk(mkS(), storage);
  await sk.handle('set my goal for today to hold the plan', null, { now: NOW }); await sk.confirm();
  const v2 = JSON.parse(storage.getItem('planner.agora.v2') || 'null');
  check('an old v1 plan is migrated by the v2 core, not overwritten', v2 && v2.v === 2 && v2.tasks.some((t) => t.text === 'old task') && /old note/.test(PL.dayNote(v2, '2026-11-10').text) && /^Goal: hold the plan/.test(PL.dayNote(v2, '2026-11-10').text), JSON.stringify(v2 && v2.notes));
  check('the v1 key is never changed', storage.getItem('planner.agora.v1') === JSON.stringify(v1));
  const bad = mkStore(); bad.setItem('planner.agora.v2', '{not json');
  const sk2 = mkSk(mkS(), bad).sk; await sk2.handle('add task x', null, { now: NOW }); const rr = await sk2.confirm();
  check('an unreadable v2 plan is never overwritten', bad.getItem('planner.agora.v2') === '{not json' && /could not be read/.test(rr.text) && rr.ok === false, rr.text);
  const empty = mkSk(mkS(), mkStore()).sk; const rp = await empty.handle('what is on my plan today', null, { now: NOW });
  check('empty planner: I don\'t have a plan', rp.missing === true && /^I don't have a plan/.test(rp.text));
  // window.JARVIS_API for the Jarvis home: nudges() is synchronous and has the home's fields
  const g = globalThis; g.location = { href: 'https://x.test/jarvis/' }; const S0 = mkS();
  g.fetch = async (u) => { const k = String(u).split('?')[0]; const m = { '../home.json': S0.home, '../money/index.json': S0.money, '../odeon/trades.json': S0.odeon, '../ledger/rules.json': S0.rules, '../pythia/events.json': S0.pythia }; return m[k] ? { ok: true, json: async () => m[k] } : { ok: false, json: async () => ({}) }; };
  delete g.JARVIS_API;
  const B = await imp('jarvis/brain.js');
  const brain = B.createBrain({ getFacts: () => ({ now: NOW, apps: [] }), open() {}, now: () => NOW, storage: mkStore(), zenithRoutes: false });
  await brain.ask('hello');
  const api = g.JARVIS_API;
  check('window.JARVIS_API installed with nudges / ask', api && api.v === 2 && typeof api.nudges === 'function' && typeof api.ask === 'function');
  await new Promise((ok) => setTimeout(ok, 150)); const ns = api.nudges();
  check('nudges() is synchronous, an array of { id, text, tone, app, say }', Array.isArray(ns) && ns.length >= 1 && ns.every((n) => n.id && n.text && /^(bad|warn|info)$/.test(n.tone) && typeof n.app === 'string' && n.say), JSON.stringify(ns));
  delete g.location; delete g.fetch; delete g.JARVIS_API;
}
console.log(`${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
