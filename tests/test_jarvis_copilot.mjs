// Jarvis money copilot (J1, 2026-11-13): node unit tests for tools/web_public/jarvis/copilot.js and its wiring in skills.js / brain.js.
// Offline: a fixed clock, fixture home.json / kalshi.json shapes, the real pythia/events.json, kalshicity/edges.json and fates/jarvis.json.
//   node tests/test_jarvis_copilot.mjs      (run by tests/test_jarvis_copilot.py, TZ=America/New_York)
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const WP = path.join(ROOT, 'tools', 'web_public');
const imp = (p) => import(pathToFileURL(path.join(WP, p)).href);
const rd = (p) => JSON.parse(fs.readFileSync(path.join(WP, p), 'utf8'));
const rq = createRequire(import.meta.url);
global.window = {};
const C = await imp('jarvis/copilot.js'), K = await imp('jarvis/skills.js'), B = await imp('jarvis/brain.js');
const apps = rq(path.join(WP, 'olympus', 'apps-list.js'));

let fails = 0, passes = 0;
const check = (name, ok, info) => { if (ok) passes++; else { fails++; console.log('FAIL ' + name + (info ? ' :: ' + String(info).slice(0, 900) : '')); } };
const et = (s) => Date.parse(s);                                   // ISO with offset, e.g. '2026-11-13T10:00:00-05:00'
const FRI10 = et('2026-11-13T10:00:00-05:00'), FRI0210 = et('2026-11-13T02:10:00-05:00'), FRI1100 = et('2026-11-13T11:00:00-05:00'), FRI1620 = et('2026-11-13T16:20:00-05:00');
const SAT = et('2026-11-14T10:00:00-05:00'), THX = et('2026-11-26T10:00:00-05:00'), FRI0100 = et('2026-11-13T01:00:00-05:00'), FRI1540 = et('2026-11-13T15:40:00-05:00');
const CPI = et('2026-11-10T09:00:00-05:00'), VET = et('2026-11-11T10:00:00-05:00'), MLK = et('2027-01-18T10:00:00-05:00');

// ------------------------------------------------------------------------------------------------ fixtures (the shapes engine/live_board.py publishes into home.json)
function home(now, over) {
  const T = Math.round(now / 1000), o = over || {};
  const lit = { room: 1133, mll: 2000, balance: 49133, floor: 48000, to_target: 3867, target_balance: 53000, profit: -867, today_pnl: 27, week_pnl: -410, dll: 1000, dll_used: 0, status: 'open', quiet_days: 2, trades_today: 1, max_day: 1, done_today: false, micros: { qty: 3, risk_usd: 450, win_usd: 1800 }, ...(o.lit || {}) };
  const atlas = { room: 746, mll: 1000, balance: 24746, to_target: 1754, profit: -254, today_pnl: 0, week_pnl: 0, status: 'open', ...(o.atlas || {}) };
  return { built: new Date(now - 300000).toISOString(),
    live: { pc: { t: T - (o.pcAge != null ? o.pcAge : 240), running: o.running !== false, present: true, mind: { plans: { lit: { t: T - 3000, headline: 'Zlarior game plan for today: structure favours longs (trend day odds 41%)' }, blitz: { t: T - 2000, headline: 'BLITZ game plan: day filter ON' } } } },
      notices: [{ t: T - 3600, kind: 'outcome', title: 'Zlarior closed +$27 (target banked)' }, { t: T - 400000, kind: 'fill', title: 'an old fill' }].concat(o.notices || []) },
    board: { t: T - 300, data_t: T - (o.pcAge != null ? o.pcAge : 240), running: o.running !== false, lit, atlas,
      progress: { lit: { session: 6, sessions: 10, sessions_left: 4, odds: { rows: { H2: { p10: 58.6, f10: 20.9, pass_med: 9 } }, src: 'research/lit/uprisk_eval.json (live two_week switches)' }, expected: { per_month: 2670, trades_per_week: 2.6 }, actual: { profit: -867, sessions: 6, per_month_pace: -3035 } },
        atlas: { session: 4, odds: { rows: { H2: { p10: 19.2, f10: 0, pass_med: 18 } } } } },
      real: { trades: [{ acct: 'lit', src: 'live', day: '2026-11-13', entry_t: T - 9000, side: 'LONG', qty: 3, usd: 27, r: 0.06 }, { acct: 'lit', src: 'live', day: '2026-11-10', entry_t: T - 300000, side: 'SHORT', qty: 3, usd: 1350, r: 3 }, { acct: 'lit', src: 'live', day: '2026-10-28', entry_t: T - 1400000, side: 'SHORT', qty: 5, usd: -437, r: -1 }].concat(o.realTrades || []) },
      trades: [{ acct: 'atlas', src: 'paper', day: '2026-11-12', entry_t: T - 90000, usd: 312, r: 1.2, side: 'SHORT' }],
      blocks: o.blocks || [], lines: o.lines || [] } };
}
const KAL = (now) => ({ t: Math.round(now / 1000) - 120, mode: 'live', running: true, status: 'Running', balance: 61.4, today_pnl: 4.1, week_pnl: -3.3, total_pnl: -75,
  positions: [{ title: 'BTC above 98k at 11am', ticker: 'KXBTC-1', side: 'yes', contracts: 10, avg_price: 92, pnl: 0.4 }, { title: 'NYC high above 50F', side: 'no', contracts: 5, avg_price: 0.8 }],
  trades: [{ t: Math.round(now / 1000) - 5000, pnl: 1.6, title: 'BTC hourly' }, { t: Math.round(now / 1000) - 4000, pnl: 2.5, title: 'ETH hourly' }, { t: Math.round(now / 1000) - 200000, pnl: -9, title: 'yesterday' }] });
const pythia = rd('pythia/events.json'), edges = rd('kalshicity/edges.json'), fatesCard = rd('fates/jarvis.json');
const SRC = (now, over) => { const o = over || {}; const S = { home: o.home === null ? null : (o.home || home(now, o)), pythia: o.pythia === null ? null : (o.pythia || pythia), fatesCard, at: { home: now - 300000, pythia: now - 3600000, fatesCard: now - 60000 } };
  if (o.kalshi) { S.kalshi = o.kalshi; S.at.kalshi = now - 120000; } if (o.edges) { S.kalshiEdges = o.edges; S.at.kalshiEdges = now - 600000; } return S; };
const mkStore = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), _m: m }; };

// ------------------------------------------------------------------------------------------------ 1. what a phrase asks (and what it must leave alone)
const PH = [
  ['should I trade today', 'trade_today'], ['Should I trade today?', 'trade_today'], ['jarvis should we trade today', 'trade_today'], ['should I let the bot trade today', 'trade_today'], ['is today a good day to trade', 'trade_today'],
  ['go or no go today', 'trade_today'], ['should I sit out today', 'trade_today'], ['can I trade today', 'trade_today'], ['should zlarior trade today', 'trade_today'], ['trade today?', 'trade_today'], ['should I trade', 'trade_today'],
  ['how much can I lose today', 'loss_budget'], ['how much can I lose this week', 'loss_budget'], ['how much can I lose before the eval fails', 'loss_budget'], ['how much more can I lose', 'loss_budget'], ['how much can atlas lose', 'loss_budget'],
  ['whats my loss budget', 'loss_budget'], ['how much room do I have today', 'loss_budget'], ['how much can I still lose', 'loss_budget'], ['how much can we drop before we fail', 'loss_budget'],
  ['how close am I to passing', 'pass_close'], ['how close am I to passing the eval', 'pass_close'], ['when will I pass', 'pass_close'], ['what are my odds of passing', 'pass_close'], ['chance to pass the eval', 'pass_close'],
  ['how many trades do I need to pass', 'pass_close'], ['how many more wins until I pass', 'pass_close'], ['am i going to pass', 'pass_close'], ['how close is atlas to passing', 'pass_close'],
  ["what's my P&L", 'pnl_report'], ['whats my pnl', 'pnl_report'], ['my p&l', 'pnl_report'], ['best and worst trade', 'pnl_report'], ['what was my best trade', 'pnl_report'], ['worst trade', 'pnl_report'], ['biggest loss', 'pnl_report'],
  ['how much do I make per month', 'pnl_report'], ['dollars per month', 'pnl_report'], ['what is my monthly pace', 'pnl_report'], ['p&l this week', 'pnl_report'], ['p&l this month', 'pnl_report'], ['how am I doing overall', 'pnl_report'], ['money report', 'pnl_report'],
  ['what changed since yesterday', 'changed'], ['what has changed since yesterday?', 'changed'], ['anything new since yesterday', 'changed'], ['what happened overnight', 'changed'], ['what changed', 'changed'], ["what's new", 'changed'],
  ['kalshi exposure', 'kalshi_day'], ['how much is at risk on kalshi', 'kalshi_day'], ["kalshi today's bets", 'kalshi_day'], ['kalshi bets today', 'kalshi_day'], ['kalshi day', 'kalshi_day'], ['what is my open risk on kalshi', 'kalshi_day'],
];
for (const [t, want] of PH) check('match: ' + t, C.match(t) === want, C.match(t));
check('at least 50 phrasings', PH.length >= 50, PH.length);
const LEAVE = ['am I allowed to trade now', 'should I trade now', 'can I trade right now', 'how many micros can I trade', 'whats my win rate', 'how far am I from the target', 'whats my pnl today', 'how am I doing today',
  'how is kalshi doing', 'kalshi balance', 'what is my worst weekday', 'what is my best weekday', 'hello', 'did we trade today', 'what did the bot do yesterday', 'how much drawdown do I have left', 'whats my balance', 'buy 2 micros now',
  'explain this trade', 'what is drawdown', 'tell me a joke', 'whats the weather', 'brief me', 'what should I do next', 'open kronos', ''];
for (const t of LEAVE) check('left to the other skills: ' + JSON.stringify(t), C.match(t) === null, C.match(t));

// ------------------------------------------------------------------------------------------------ 2. GO / CAREFUL / SIT OUT
{
  let v = C.verdict(SRC(FRI10), FRI10);
  check('GO on a normal Friday 10:00 ET (PPI is medium impact: mentioned, not a downgrade)', v.verdict === 'GO' && v.why.some((w) => /PPI/.test(w)) && v.per.length === 2, JSON.stringify(v));
  check('GO: each account with its drawdown and full losses at the live size', v.per[0].text === 'Zlarior 50K: GO. Drawdown left $1,133 of $2,000 (2 full losses at $450); about 4 sessions left of the 2-week goal.', v.per[0].text);
  v = C.verdict(SRC(CPI), CPI);
  check('CAREFUL on a CPI morning (high impact, with its time)', v.verdict === 'CAREFUL' && v.why.some((w) => /CPI/.test(w) && /08:30 ET/.test(w) && /high impact/.test(w)), JSON.stringify(v.why));
  v = C.verdict(SRC(VET), VET); check('Veterans Day (stocks trade, bonds closed) is not a closed day', v.verdict === 'GO', JSON.stringify(v.why));
  v = C.verdict(SRC(MLK), MLK); check('MLK day (CME holiday hours) is CAREFUL', v.verdict === 'CAREFUL' && v.why.some((w) => /holiday hours/.test(w)), JSON.stringify(v.why));
  v = C.verdict(SRC(SAT), SAT); check('SIT OUT on Saturday', v.verdict === 'SIT OUT' && /Saturday/.test(v.global) && /Monday from 02:00 ET/.test(v.global), v.global);
  v = C.verdict(SRC(THX), THX); check('SIT OUT on Thanksgiving (Pythia: markets closed)', v.verdict === 'SIT OUT' && /Thanksgiving/.test(v.global), v.global);
  v = C.verdict(SRC(FRI1540), FRI1540); check('SIT OUT after the last entry (15:30 ET)', v.verdict === 'SIT OUT' && /15:30 ET/.test(v.global) && /15:40 ET/.test(v.global), v.global);
  v = C.verdict(SRC(FRI10, { pcAge: 3 * 86400 }), FRI10); check('SIT OUT when the bot\'s report is days old', v.verdict === 'SIT OUT' && v.why.some((w) => /3 days/.test(w) && /STATUS\.bat/.test(w)), JSON.stringify(v.why));
  v = C.verdict(SRC(FRI10, { pcAge: 3600 }), FRI10); check('CAREFUL when the PC is quiet during trading hours', v.verdict === 'CAREFUL' && v.why.some((w) => /quiet for 1 hour/.test(w)), JSON.stringify(v.why));
  v = C.verdict(SRC(FRI10, { running: false }), FRI10); check('CAREFUL when the bot says it is stopped', v.verdict === 'CAREFUL' && v.why.some((w) => /stopped/.test(w)), JSON.stringify(v.why));
  v = C.verdict(SRC(FRI10, { lit: { room: 400 } }), FRI10); check('CAREFUL when the room is under one full loss', v.verdict === 'CAREFUL' && /less than one full loss/.test(v.per[0].text), v.per[0].text);
  v = C.verdict(SRC(FRI10, { lit: { dll_used: 850 } }), FRI10); check('CAREFUL when 80% of the daily loss is used', v.verdict === 'CAREFUL' && /only \$150 of today's \$1,000 daily loss left/i.test(v.per[0].text), v.per[0].text);
  v = C.verdict(SRC(FRI10, { lit: { dll_used: 1000 } }), FRI10); check('one account out (daily loss used up), the other fine: CAREFUL overall, SIT OUT for that account', v.verdict === 'CAREFUL' && v.per[0].level === 'SIT OUT' && /daily loss used up/i.test(v.per[0].text), JSON.stringify(v.per));
  v = C.verdict(SRC(FRI10, { lit: { dll_used: 1000 }, atlas: { status: 'failed', room: 0 } }), FRI10); check('every real account out: SIT OUT', v.verdict === 'SIT OUT' && /eval failed/i.test(v.per[1].text), JSON.stringify(v.per));
  v = C.verdict(SRC(FRI10, { lit: { done_today: true } }), FRI10); check('the 1 trade a day is taken: that account SITs OUT', v.per[0].level === 'SIT OUT' && /one trade today/.test(v.per[0].text), v.per[0].text);
  v = C.verdict(SRC(FRI10, { lit: { quiet_days: 6 } }), FRI10); check('6 quiet days: says a trade is needed now (MFFU 7 days)', /6 quiet days: MFFU closes the account after 7/.test(v.per[0].text), v.per[0].text);
  v = C.verdict(SRC(FRI10, { blocks: [{ text: 'Feed stale: no NinjaTrader bars', fix: 'restart LE_BarFeed', kind: 'feed' }] }), FRI10); check('a board block (FEED STALE) is a CAREFUL with its fix', v.verdict === 'CAREFUL' && v.why.some((w) => /Feed stale/.test(w) && /Fix: restart LE_BarFeed/.test(w)), JSON.stringify(v.why));
  v = C.verdict(SRC(FRI10, { home: null }), FRI10); check('no home.json: CAREFUL and says it cannot see the accounts', v.verdict === 'CAREFUL' && v.why.some((w) => /do not have home\.json/.test(w)) && !v.per.length, JSON.stringify(v));
  v = C.verdict(SRC(FRI10, { home: { accounts: [{ id: 'mffu50k_eval', name: 'Zlarior 50K', kind: 'eval', eval: { balance: 50420, room: 1420, mll: 2000, dll: 1000, dll_used: 0, target: 3000, to_target: 2580 }, pnl: { today: 312 } }] } }), FRI10);
  check('older home.json (accounts rows only) is read through truth.js', v.per.length === 1 && /Zlarior 50K: .*\$1,420 of \$2,000/.test(v.per[0].text), JSON.stringify(v.per));
}
// ------------------------------------------------------------------------------------------------ 3. the answers: numbers, sources with their age, plain speech
{
  const st = mkStore(), cp = C.createCopilot({ storage: st, now: () => FRI10 }), S = SRC(FRI10, { kalshi: KAL(FRI10) });
  let r = cp.ask('should I trade today', S, FRI10);
  check('trade today: verdict first, reasons, per account, not an order, sources with age', r.intent === 'copilot_trade_today' && r.verdict === 'GO' && /^GO: a normal day/.test(r.text) && /not an order/.test(r.text)
    && /From home\.json, 5 min ago \(PC report 4 minutes old\); pythia\/events\.json, \d+ (?:days|h|min) ago\./.test(r.text) && r.sources.length === 2 && r.app === 'ares' && r.open === undefined, r.text);
  check('speech has no $ sign and no bullets', !/[$•]/.test(r.speak) && /^GO/.test(r.speak), r.speak);
  r = cp.ask('how much can I lose today', S, FRI10);
  check('loss budget: today = the daily limit left, week/total = drawdown left, full losses at the live size', /Zlarior 50K: today \$1,000 before the daily limit \(\$1,000, \$0 used; MFFU's daily loss ends the day, not the eval\); this week and in total \$1,133 before the eval fails \(drawdown left \$1,133 of \$2,000 max loss; there is no weekly limit\)\. That is 2 full losses at \$450 \(the live sizing\)\./.test(r.text)
    && /ATLAS 25K: today \$600/.test(r.text) && /Tightest: Zlarior 50K\./.test(r.text) && /From home\.json/.test(r.text), r.text);
  check('loss budget speech in words ("1,000 dollars")', /1,000 dollars/.test(r.speak) && !/\$/.test(r.speak), r.speak);
  const L = C.lossBudget(SRC(FRI10, { lit: { room: 300, dll_used: 100 } }), FRI10)[0];
  check('loss budget: a room smaller than the daily limit caps today', L.today === 300 && L.todayCapped === true && L.losses === 0, JSON.stringify(L));
  r = cp.ask('how close am I to passing', S, FRI10);
  check('pass: $ to go, profit so far, wins at the live win size, H2 odds and Fates\' %', /Zlarior 50K: \$3,867 to go to the \$3,000 profit target \(profit so far -\$867, 0% done\)\. At \$1,800 a win \(the live sizing\) that is 3 winning trades/.test(r.text)
    && /58\.6% pass within 10 sessions, 20\.9% fail, median pass after 9 sessions/.test(r.text) && /Fates' simulation from today: 67% pass/.test(r.text) && /fates\/jarvis\.json/.test(r.text) && /not a promise/.test(r.text), r.text);
  const P = C.passClose(SRC(FRI10, { lit: { to_target: 500, profit: 2500 } }), FRI10)[0];
  check('pass maths: $500 to go at $1,800 a win = 1 win; 83% done', P.wins === 1 && Math.round(P.done * 100) === 83, JSON.stringify(P));
  r = cp.ask('what was my best trade', S, FRI10);
  check('P&L: per account today / week / since start, real trades only, best and worst, win rate, PF, $ a month pace and the backtest', /Zlarior 50K: today \+\$27, this week -\$410, since the eval started -\$867\./.test(r.text)
    && /3 real trades in the files: 2 won, 1 lost \(67% win rate\), net \+\$940, profit factor 3\.15\./.test(r.text) && /Best trade: Zlarior 2026-11-10 short 3 micros: \+\$1,350 \(\+3R\)\./.test(r.text) && /Worst trade: Zlarior 2026-10-28 short 5 micros: -\$437 \(-1R\)\./.test(r.text)
    && /too few to judge/.test(r.text) && /about -\$3,035 a month \(over 6 sessions\)/.test(r.text) && /backtest expects about \+\$2,670 a month at the live settings \(2\.6 trades a week\)/.test(r.text), r.text);
  check('P&L: the paper ATLAS trade is not counted with the real ones', !/ATLAS 2026-11-12/.test(r.text));
  const P2 = C.pnlReport(SRC(FRI10, { home: { ...home(FRI10), board: { ...home(FRI10).board, real: { trades: [] } } } }), FRI10);
  check('P&L: with no real trade the paper ones are used and called paper', P2.kind === 'paper' && P2.n === 1, JSON.stringify([P2.kind, P2.n]));
  r = cp.ask('kalshi exposure today', S, FRI10);
  check('Kalshi: today, balance, settled today, open exposure from contracts x price (cents or dollars)', /Kalshi today: \+\$4\.10, balance \$61, this week -\$3\.30\./.test(r.text) && /Settled today: 2 bets, 2 won, \+\$4\.10 together\./.test(r.text)
    && /Open: 2 bets, \$13 at risk \(the most they can lose\)/.test(r.text) && /never places a Kalshi bet/.test(r.text) && /From kalshi\.json, 2 min ago\./.test(r.text), r.text);
  const k = C.kalshiDay(SRC(FRI10, { kalshi: KAL(FRI10) }), FRI10);
  check('Kalshi exposure maths: 10 x 92c + 5 x $0.80 = $13.20', Math.abs(k.exposure - 13.2) < 1e-9, k.exposure);
  r = cp.ask('kalshi exposure', SRC(FRI10, { edges }), FRI10);
  check('Kalshi from the engine copy: says the live feed is not answering', /engine's copy/.test(r.text) && /kalshicity\/edges\.json/.test(r.text) && !r.missing, r.text);
  r = cp.ask('kalshi exposure', SRC(FRI10), FRI10);
  check('Kalshi with no feed at all: says so plainly, no number', r.missing === true && /don't have the Kalshi numbers/.test(r.text) && !/\$\d/.test(r.text), r.text);
  for (const q of ['should I trade today', 'how much can I lose today', 'how close am I to passing', 'whats my pnl', 'what changed since yesterday']) {
    const m = cp.ask(q, SRC(FRI10, { home: null }), FRI10);
    if (q === 'should I trade today') check('missing home: trade today still answers, CAREFUL, without numbers', m.verdict === 'CAREFUL' && !/\$\d/.test(m.text), m.text);
    else check('missing home: ' + q + ' says it is missing, never a number', m.missing === true && /^I don't have that/.test(m.text) && !/\$\d/.test(m.text), m.text);
  }
}
// ------------------------------------------------------------------------------------------------ 4. what changed since yesterday (one snapshot per ET day on this phone)
{
  const st = mkStore(), cp = C.createCopilot({ storage: st });
  let r = cp.ask('what changed since yesterday', SRC(FRI10), FRI10);
  check('no snapshot yet: from the published files, says the phone starts keeping one', /from the published files/.test(r.text) && /New trades: Zlarior 2026-11-13 long 3 micros: \+\$27/.test(r.text) && /ATLAS 2026-11-12 short: \+\$312 \(\+1\.2R\) \(paper\)/.test(r.text)
    && /Alerts: Zlarior closed \+\$27 \(target banked\) \(60 min ago\)/.test(r.text) && !/an old fill/.test(r.text), r.text);
  check('the snapshot is kept under jarvis.copilot.v1', st._m.has(C.STORE_KEY) && JSON.parse(st._m.get(C.STORE_KEY)).days['2026-11-13'].acc.lit.room === 1133);
  const st2 = mkStore(), cp2 = C.createCopilot({ storage: st2 }), THU = et('2026-11-12T16:30:00-05:00');
  cp2.remember(SRC(THU, { lit: { room: 1300 }, realTrades: [] }), THU);
  const after = SRC(FRI10, { lit: { room: 1133 }, notices: [{ t: Math.round(FRI10 / 1000) - 600, kind: 'pc', title: 'PC back online' }], lines: [{ level: 'bad', text: 'Zlarior: Eval: weekly stop' }] });
  r = cp2.ask('what changed since yesterday', after, FRI10);
  check('with yesterday\'s snapshot: drawdown move in $ (was / now), only trades and alerts after it, open alerts flagged', /since yesterday \(18 h ago, the last time this phone looked\)/.test(r.text) && /Zlarior 50K: drawdown left \$1,133 of \$2,000, down \$167 \(was \$1,300\)\./.test(r.text)
    && /PC back online \(10 min ago\)/.test(r.text) && /weekly stop \(still open\)/.test(r.text), r.text);
  const st3 = { getItem() { throw new Error('private'); }, setItem() { throw new Error('private'); } };
  r = C.createCopilot({ storage: st3 }).ask('what changed since yesterday', SRC(FRI10), FRI10);
  check('private mode (storage throws): still answers from the files', r && /from the published files/.test(r.text), r && r.text);
  const st4 = mkStore(), cp4 = C.createCopilot({ storage: st4 });
  for (let d = 2; d <= 20; d++) cp4.remember(SRC(FRI10), et(`2026-11-${String(d).padStart(2, '0')}T12:00:00-05:00`));
  check('keeps the last 5 days only', Object.keys(JSON.parse(st4._m.get(C.STORE_KEY)).days).length === 5);
}
// ------------------------------------------------------------------------------------------------ 5. the home cards: 01:45 / 10:45 / 16:05 ET
{
  const S = SRC(FRI0210, { kalshi: KAL(FRI0210) });
  check('slots by the New York clock', [FRI0100, FRI0210, FRI1100, FRI1620, SAT].map((t) => C.slotAt(t).id).join(',') === '16:05,01:45,10:45,16:05,16:05' && C.slotAt(FRI0100).day === '2026-11-12', [FRI0100, FRI0210, FRI1100, FRI1620, SAT].map((t) => JSON.stringify(C.slotAt(t))));
  let c = C.cardFor(S, FRI0210);
  check('01:45 card: Morning plan, the verdict chip, what each account can lose, the LIT game plan, news, Kalshi', c.slot === '01:45' && c.title === 'Morning plan' && c.verdict === 'GO' && /^GO · /.test(c.rows[0].text)
    && c.rows.some((x) => /^Zlarior 50K: can lose \$1,000 today; \$1,133 before the eval fails \(2 full losses\)\.$/.test(x.text)) && c.rows.some((x) => /Zlarior game plan/.test(x.text)) && c.rows.some((x) => /^News: PPI/.test(x.text)) && c.rows.some((x) => /^Kalshi: \+\$4\.10 today, 2 open bets \(\$13 at risk\)\.$/.test(x.text)), JSON.stringify(c));
  check('every card line asks Jarvis a full question on a tap; at most 6 lines; the foot names the files and their age', c.rows.length <= 6 && c.rows.every((x) => x.say && /\?$|today$/.test(x.say)) && /^From home\.json, .* \(PC report .* old\); pythia\/events\.json, .*; kalshi\.json, .*\.$/.test(c.foot), JSON.stringify(c));
  check('no "session X of 10" counter on the card (owner 2026-11-03)', !c.rows.some((x) => /session \d+ of|of 10\b/i.test(x.text)), JSON.stringify(c.rows));
  c = C.cardFor(SRC(FRI1100), FRI1100);
  check('10:45 card: Midday plan, the BLITZ / LIT plans, news after 10:45 only', c.slot === '10:45' && c.title === 'Midday plan' && c.rows.some((x) => /game plan/.test(x.text)) && !c.rows.some((x) => /PPI/.test(x.text)), JSON.stringify(c.rows));
  c = C.cardFor(SRC(FRI1620, { kalshi: KAL(FRI1620) }), FRI1620);
  check('16:05 card: Day summary with today\'s $ per account, drawdown left, the trades, Kalshi', c.slot === '16:05' && c.kind === 'summary' && c.title === 'Day summary' && c.total === 27
    && c.rows.some((x) => /^Zlarior 50K: \+\$27 today; drawdown left \$1,133 of \$2,000; \$3,867 to the target\.$/.test(x.text)) && c.rows.some((x) => /^1 trade today: Zlarior 2026-11-13 long 3 micros: \+\$27/.test(x.text)) && c.rows.some((x) => /^Kalshi: \+\$4\.10 today, 2 bets settled, 2 still open\.$/.test(x.text)), JSON.stringify(c));
  c = C.cardFor(SRC(FRI0100), FRI0100); check('before 01:45: the last session stands (yesterday)', c.title === 'Last session' && /2026-11-12/.test(c.kicker), JSON.stringify(c));
  const WED = et('2026-11-25T16:20:00-05:00'); c = C.cardFor(SRC(WED), WED); check('the day summary warns about tomorrow (Thanksgiving closed)', c.rows.some((x) => /^Tomorrow: Thanksgiving/.test(x.text)), JSON.stringify(c.rows));
  c = C.cardFor({ at: {} }, FRI0210); check('no home.json: a waiting card, nothing guessed', c.kind === 'missing' && !/\$\d/.test(JSON.stringify(c)), JSON.stringify(c));
  const st = mkStore(); C.createCopilot({ storage: st }).card(SRC(FRI1620), FRI1620); check('drawing the card keeps today\'s snapshot', st._m.has(C.STORE_KEY));
}
// ------------------------------------------------------------------------------------------------ 6. junk never throws
{
  const cp = C.createCopilot({});
  const junk = [null, undefined, 5, 'x', [], {}, { home: 7 }, { home: { board: 'x', accounts: 'y', live: { pc: 9, notices: 'z' } } }, { home: { board: { lit: { room: 'abc' }, real: { trades: [null, 5, { usd: 'x' }] }, trades: 'q' } }, pythia: { events: [null, { date: 'bad' }] }, kalshi: { positions: [null, { contracts: 'x' }], trades: 'y' } }];
  let ok = true, err = '';
  for (const S of junk) for (const id of cp.ids) { try { const r = cp.answer(id, S, FRI10); if (r && typeof r.text !== 'string') { ok = false; err = id; } } catch (e) { ok = false; err = id + ': ' + e.message; } }
  for (const S of junk) { try { const c = cp.card(S, FRI10); if (c && !Array.isArray(c.rows)) { ok = false; err = 'card'; } } catch (e) { ok = false; err = 'card: ' + e.message; } }
  check('junk sources never throw (every answer and the card)', ok, err);
  check('match never throws on junk', [null, undefined, 5, {}, 'x'.repeat(500)].every((t) => C.match(t) === null));
}
// ------------------------------------------------------------------------------------------------ 7. the wiring: skills.js asks the copilot after the safety guard; the brain asks the skills before bots.js / Kalshi
{
  const S = SRC(FRI10, { kalshi: KAL(FRI10) }), storage = mkStore();
  const sk = K.createSkills({ getSources: async () => S, apps: () => apps, storage, now: () => FRI10 });
  let r = await sk.handle('should I trade today', null, { now: FRI10 });
  check('skills.handle: "should I trade today" is the copilot', r && r.intent === 'copilot_trade_today' && r.copilot === true && r.verdict === 'GO', r && r.intent);
  r = await sk.early('how much can I lose today', { now: FRI10 }); check('skills.early: the copilot (the brain asks early first)', r && r.intent === 'copilot_loss_budget', r && r.intent);
  r = await sk.handle('am I allowed to trade now', null, { now: FRI10 }); check('skills: "am I allowed to trade now" is still the window rule', r && r.intent === 'can_trade_now', r && r.intent);
  r = await sk.handle('buy 2 micros now', null, { now: FRI10 }); check('skills: the safety guard still answers first', r && /refuse|never|not place|won't|will not/i.test(r.text) && !/copilot/.test(r.intent), r && (r.intent + ' ' + r.text));
  r = await sk.handle('open it', null, { now: FRI10 }); check('follow-up "open it" after a copilot answer opens its app', r && (r.open === 'ares' || (r.pending && /ares/i.test(JSON.stringify(r)))), r && JSON.stringify(r).slice(0, 300));
  r = await sk.handle('what can you do', null, { now: FRI10 }); check('help lists the money copilot', /Money copilot/.test(r.text) && /should I trade today/.test(r.text), r.text.slice(0, 400));
  const ctx = await sk.contextFor('should I trade today'); check('smart mode context carries the copilot answer', /copilot_trade_today: GO/.test(ctx), ctx.slice(0, 300));
  const card = await sk.card(FRI0210); check('skills.card(): the home card from the same sources', card && card.slot === '01:45' && card.rows.length >= 3, JSON.stringify(card).slice(0, 200));
  const brain = B.createBrain({ getFacts: () => ({ now: FRI10, live: null, kalshi: null, apps: [] }), skills: sk, now: () => FRI10, autoOpen: false, storage: mkStore() });
  r = await brain.ask('should I trade today');
  check('brain.ask: the copilot answers before the bots and the modes', r && r.intent === 'copilot_trade_today' && /^GO/.test(r.text), r && (r.intent + ' ' + String(r.text).slice(0, 200)));
  r = await brain.ask('kalshi exposure today'); check('brain.ask: Kalshi\'s day from the copilot, not the Kalshi brain', r && r.intent === 'copilot_kalshi_day', r && r.intent);
  r = await brain.ask('what changed since yesterday'); check('brain.ask: what changed', r && r.intent === 'copilot_changed' && /What changed/.test(r.text), r && r.intent);
}

console.log(`${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
