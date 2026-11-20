// Jarvis business answers (tools/web_public/jarvis/biz.js, day-jarvis 2026-11-20): the 8 owner questions answered from the real feeds,
// $ first, one source line with its age, offline from the saved copies. Node only (no browser):  node tests/test_jarvis_biz.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const WEB = path.join(ROOT, 'tools', 'web_public');
const B = await import(path.join(WEB, 'jarvis', 'biz.js'));
let fails = 0, n = 0;
const ok = (c, m) => { n++; if (!c) { fails++; console.log('FAIL', m); } else console.log('ok  ', m); };

// the live view the way data.js slim() hands it over: the PC lite post (tests/fixtures/jarvis_zeus_lite.json)
const lite = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests', 'fixtures', 'jarvis_zeus_lite.json'), 'utf8'));
const NOW = new Date('2026-11-20T15:00:00Z');                        // Fri 10:00 ET
const b = lite.board;
// the shapes of the real PC post on 2026-11-20 (ATLAS short open, stop moved past the entry; K8 on paper inside kalshi_live)
const live = { lit: { ...b.lit }, atlas: { ...b.atlas, balance: 24887.2, room: 887.2, position: { side: 'SHORT', qty: 1, entry: 26380.75, stop: 26379.5, target: 26122.75, entry_t: 1795164300 } }, t: NOW / 1000 - 300,
  price: 26290.25,
  trades: [{ acct: 'lit', side: 'LONG', usd: 812.5, exit: 'TARGET', day: '2026-11-20', open: false }, { acct: 'lit', side: 'SHORT', usd: -240, exit: 'STOP', day: '2026-11-18', open: false },
    { acct: 'atlas', side: 'SHORT', exit: 'OPEN', r: 2.73, day: '2026-11-20', open: true, member: 'EMA' }, { acct: 'atlas', side: 'LONG', usd: -441.6, exit: 'STOP', day: '2026-11-17', open: false, src: 'paper', member: 'S/R' }],
  raw: { t: NOW / 1000 - 300, pc: { running: true, adapter: 'ninjatrader', silent: false, age_s: 0, every_s: 300, model_state: 'LIT: watching for a sweep + inducement + CISD (entries until 15:30 ET)' },
    reporter: { t: NOW / 1000 - 290, server: true, nt: true, market_open: true, problems: [] }, pc_verdict: { code: 'TRADING', label: 'TRADING YOUR EVAL', level: 'good' },
    sh: { t: NOW / 1000 - 3000, ok: true, free: 53, line: 'Self-heal: all fine · fixed 1 this week · 53 GB free' },
    zl: { d: '2026-11-19', t: NOW / 1000 - 50000, s: 'Zlarior no trade, edge GREEN, nothing to change · ATLAS no trade, edge AMBER, nothing to change · K8 5 bets +$10 (paper), nothing to change' },
    at: { t: NOW / 1000 - 300, a: [{ id: 'mffu50k_eval', tr: [[1794400200, 1794403800, -1, 2, 26500, 26520, 26340, 'TARGET', 612.5, 7.9], [1794827760, 1794830400, 1, 1, 27799.5, 27735.25, 28174, 'STOP', -129.4, -1.01]] },
      { id: 'atlas', tr: [[1794995400, 1794996603, -1, 2, 27395.5, 27422.5, 27179.5, 'STOP', -112.8, -1.04], [1795164300, null, -1, 1, 26380.75, 26419.5, 26122.75, null, null, 2.73]] }] },
    board: { atlas: { ...b.atlas, balance: 24887.2, room: 887.2, status: 'funded', plan: 'MFFU Builder 25K funded' }, lit: { ...b.lit } }, accounts: lite.accounts,
    mf: { t: NOW / 1000 - 300, a: [{ id: 'atlas', nm: 'ATLAS 25K funded', f: { cp: -113, bd: -113, cd: 1, ef: '2026-11-20', pn: 0, mr: 0, st: 'building' } }] },
    kalshi_live: { kind: 'kalshi_live_pub', v: 1, st: 'paper', u: '2026-11-20T11:15:02+00:00', k8: { m: 'P', nx: 1795208400, b: 55, s: 2.5, td: [2, 0, -5.08], l: 'WWWLLLL', wk: [0, 13.75], dd: [35.73, 19.25], wr: [7, 43], lp: 1 } } },
  extra: [{ id: 'b25k_2', key: 'b25k_2', name: 'Zlarior 25K #2', plan: 'Builder 25K', size: '25K', stage: 'eval', balance: 25000, room: 1000, mll: 1000, to_target: 1500, today_pnl: 0, dll: 600, dll_used: 0 }],
  verdict: { label: 'Bots running' }, klive: null };
const store = new Map();
const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) };
const files = { '../business/payday.json': 'business/payday.json', '../hub/steps.json': 'hub/steps.json', '../business/decisions.json': 'business/decisions.json',
  '../nq/news_week.json': 'nq/news_week.json', '../pythia/events.json': 'pythia/events.json', '../business/dash.json': 'business/dash.json', '../agency/expert/playbook.json': 'agency/expert/playbook.json' };
let offline = false;
const DECIDE = { v: 1, updated: '2026-11-20', items: [
  { id: 'q1', status: 'open', question: 'Funded 25K: ask for the full $1,000 payout?', recommend: 'no', recommend_why: 'Keep the $750 ping.', usd_month: -9 },
  { id: 'q2', status: 'yes', question: 'ATLAS on the Rapid?', recommend: 'yes' }, { id: 'q3', status: 'later', question: 'Zlarior + ATLAS on the 50K?', recommend: 'yes' }] };
let decide = DECIDE;
const fakeFetch = async (u) => {
  if (offline) throw new Error('offline');
  const k = String(u).split('?')[0];
  if (k === '../business/decisions.json') return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(decide)), text: async () => JSON.stringify(decide) };
  if (!files[k]) return { ok: false, status: 404, json: async () => null, text: async () => '' };
  const body = fs.readFileSync(path.join(WEB, files[k]), 'utf8');
  return { ok: true, status: 200, json: async () => JSON.parse(body), text: async () => body };
};
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const FEED = require(path.join(WEB, 'pc_feed.js')), COACH = require(path.join(WEB, 'business', 'payoutcoach.js'));
const deps = { facts: () => ({ live }), now: () => NOW, fetch: fakeFetch, storage, feed: FEED, coach: COACH };

const Q = {
  'How are my accounts?': 'accounts', 'Is ATLAS in a trade?': 'intrade', 'How much room does Zlarior have?': 'room', 'When is my first payout?': 'payout',
  'What did the bots do today?': 'bots', 'What did the bots do this week?': 'bots', "What's on the news today?": 'news', 'What should I do today?': 'steps', "How's Kalshi?": 'kalshi',
  'open kalshi': null, 'hide my balance': null, 'show my balance': null, 'how is blitz': null, 'explain the strategy': null, 'hello': null,
};
for (const [q, id] of Object.entries(Q)) ok(B.match(q) === id, `match "${q}" -> ${id}`);
// the owner's own phrasings (team JARVIS 2026-11-20): 40+ ways he asks, each to the right answer
const OWNER = {
  accounts: ['how are my accounts', 'account balances', 'how am I doing', 'how is zlarior', 'how are my evals', 'money status'],
  intrade: ['is atlas in a trade', 'any trades open', 'open positions?', 'are we in the market right now', 'is zlarior in a trade'],
  room: ['how much room does zlarior have', 'atlas drawdown', 'room left on each account', 'how much can atlas lose'],
  payout: ['when is my first payout', 'when do I get paid', 'payday?', 'first check'],
  payoutnow: ['can I ask for a payout', 'how much more until a payout', 'when can atlas get paid', 'payout today?'],
  bots: ['what did the bots do today', 'what did the bots do this week', 'last week?', 'how much did I make today', 'am I up today', "today's trades", 'recap'],
  news: ["what's on the news today", 'any cpi this week', 'economic calendar', 'big releases'],
  steps: ['what should I do today', 'my to-do list', 'anything for me', 'what is waiting on me'],
  kalshi: ["how's kalshi", 'kalshi today', 'k8 status'],
  pc: ['is the pc ok', 'is the bot running', 'pc status', 'is the computer on', 'is ninjatrader connected'],
  decide: ['what do you recommend', 'decide card', 'any decisions for me'],
  taxes: ['how much for taxes', 'taxes on a $1,000 payout', 'when is the next estimated payment'],
  review: ['how did yesterday go', 'daily review'],
  window: ['when do the bots trade', 'is the window open', 'trading hours'],
  month: ['how much will I make a month', 'monthly income'],
  pass: ['how far to pass', 'when will zlarior pass', 'how much left to pass the 25k'],
  edge: ['is the edge ok', 'is zlarior still working', 'edge health'],
};
let nq = 0; for (const [id, qs] of Object.entries(OWNER)) for (const q of qs) { nq++; ok(B.match(q) === id, `owner asks "${q}" -> ${id} (got ${B.match(q)})`); }
ok(nq >= 60, `${nq} owner phrasings`);
for (const q of ['is everything ok', 'and yesterday?', 'why?', 'what about atlas?', 'open it', 'explain the strategy', 'how far to target', 'how much room do I have', 'hide my balance']) ok(B.match(q) === null, `left to the brain: "${q}"`);

const say = {};
for (const q of Object.keys(Q).filter((q) => Q[q])) { const r = await B.ask(q, deps); say[q] = r; console.log('   > ' + r.text.replace(/\n/g, '\n     ')); }
const T = (q) => say[q].text;
ok(/3 accounts/.test(T('How are my accounts?')) && /ATLAS 25K funded: -\$113, today \$0, floor -\$1,000 \(\$887 room left\)\. Earliest payout at \$1,350 \(\$1,463 to go\); goal \$1,000 at \$2,100 \(you get \$800\)/.test(T('How are my accounts?')) && !/\$24,887/.test(T('How are my accounts?')) && /\$49,193/.test(T('How are my accounts?')) && /Zlarior 25K #2/.test(T('How are my accounts?')), 'accounts: 3 accounts with $ balances, the funded one from $0 the way MFFU shows it (owner 2026-11-20)');
ok(/Source: PC report, 5 min ago/.test(T('How are my accounts?')), 'accounts: source + age line');
ok(/ATLAS 25K: YES, short 1 micro from 26,380\.75, about \+\$181 open right now \(\+2\.7R\)/.test(T('Is ATLAS in a trade?')) && /can no longer lose/.test(T('Is ATLAS in a trade?')) && !/Zlarior/.test(T('Is ATLAS in a trade?')), 'in a trade: ATLAS position in $, locked stop, ATLAS only');
ok(/Zlarior 50K: \$1,025 of \$2,000 drawdown left/.test(T('How much room does Zlarior have?')) && /Zlarior 25K #2: \$1,000 of \$1,000/.test(T('How much room does Zlarior have?')) && !/ATLAS/.test(T('How much room does Zlarior have?')), 'room: both Zlarior accounts, not ATLAS');
ok(/First payout most likely ATLAS 25K \(funded\): about \$800 around Mon Jan 4 2027/.test(T('When is my first payout?')) && /payday\.json \(2026-11-20\)/.test(T('When is my first payout?')), 'payout: ATLAS first, $ + date + source');
ok(/Today: no trades yet|Today: 0 closed trades/.test(T('What did the bots do today?')) || /ATLAS 25K short today: still open \(\+2\.7R\)/.test(T('What did the bots do today?')), 'bots today: the open ATLAS trade from the PC list');
ok(/This week: 2 closed trades for -\$242 \(\+ 1 paper\), 1 still open/.test(T('What did the bots do this week?')) && /S\/R long Tue Nov 17: -\$442 \(stop\), paper/.test(T('What did the bots do this week?')), 'bots week: the PC\'s per-account trades, paper labelled and out of the $');
ok(/Nothing big today|No US data|big release/.test(T("What's on the news today?")) && /Next big one: Non-Farm Payrolls/.test(T("What's on the news today?")), 'news: today + next big one');
ok(/things? waiting on you\. First: Add the Rapid EOD 25K/.test(T('What should I do today?')) && /1 yes\/no question on the Decide card/.test(T('What should I do today?')), 'steps: first to-do + the open decision');
ok(/K8 is on PAPER/.test(T("How's Kalshi?")) && /Today: 2 bets, 0 won, -\$5\.08/.test(T("How's Kalshi?")) && /7 bets, 43% won/.test(T("How's Kalshi?")) && /next window today 4:00 PM ET/.test(T("How's Kalshi?")), 'kalshi: the K8 card from the PC report');
storage.setItem('oly-steps-done-v1', JSON.stringify({ 'rapid-add': true }));
ok(!/First: Add the Rapid/.test((await B.ask('What should I do today?', deps)).text), 'steps: a Done tick from hub/steps skips that step');
// offline: no network, fresh module memory: the saved copies answer with their age
offline = true;
const B2 = await import(path.join(WEB, 'jarvis', 'biz.js') + '?fresh=1');
const off = await B2.ask('When is my first payout?', { ...deps, now: () => new Date(+NOW + 3 * 3600e3) });
ok(/First payout most likely ATLAS/.test(off.text) && /saved copy from/.test(off.text) && off.offline, 'offline: payout from the saved copy, says so');
const none = await B2.ask('When is my first payout?', { ...deps, storage: { getItem: () => null, setItem: () => {} } });
ok(/cannot read the payout plan/.test(none.text), 'offline, no saved copy: says it cannot read it');
const nolive = await B2.ask('How are my accounts?', { ...deps, facts: () => ({ live: null }) });
ok(/no account numbers from the PC yet/.test(nolive.text), 'no PC report: says so, no made-up numbers');
// the new answers (team JARVIS)
ok(/about \+\$181 open at the PC's last report/.test((await B.ask('Is ATLAS in a trade?', { ...deps, facts: () => ({ live: { ...live, t: NOW / 1000 - 3600 } }) })).text), 'in a trade: an hour-old report never says "right now"');
offline = false;
const ask = async (q) => (await B.ask(q, deps)).text;
const pcA = await ask('is the pc ok'); console.log('   > ' + pcA.replace(/\n/g, '\n     '));
ok(/^Yes: the PC reported 5 min ago and the bot is running, NinjaTrader connected/.test(pcA) && /53 GB free/.test(pcA) && !/MFFU|6016/.test(pcA), 'pc: yes + NinjaTrader + self-check, never an account number');
const stale = await B.ask('is the pc ok', { ...deps, facts: () => ({ live: { ...live, t: NOW / 1000 - 3 * 3600 } }) });
ok(/^Not sure: the PC's last report is 3 h ago/.test(stale.text), 'pc: an old report says not sure, with its age');
const dA = await ask('what do you recommend'); console.log('   > ' + dA.replace(/\n/g, '\n     '));
ok(/1 yes\/no question waiting/.test(dA) && /My advice: NO \(-\$9 a month\)/.test(dA) && /Parked for later: Zlarior \+ ATLAS on the 50K\? My advice: YES/.test(dA), 'decide: open question with advice and $, the parked one');
decide = { ...DECIDE, items: DECIDE.items.filter((i) => i.status !== 'open') };
const B3 = await import(path.join(WEB, 'jarvis', 'biz.js') + '?d=2');
ok(/^Nothing waiting: all 2 answered \(1 yes, 0 no, 1 later\)/.test((await B3.ask('decide card', { ...deps, storage: { getItem: () => null, setItem: () => {} } })).text), 'decide: all answered');
decide = DECIDE;
const pn = await ask('can I ask for a payout'); console.log('   > ' + pn.replace(/\n/g, '\n     '));
ok(/^ATLAS 25K funded: -\$113,.*goal \$1,000 at \$2,100 \(you get \$800\)/.test(pn) && /\nATLAS 25K: Not yet: need \$1,463 more/.test(pn) && !/\$24,887/.test(pn) && /\$800 to you \(80%\); set \$240 aside for taxes \(30%\), \$560 is yours/.test(pn) && /payoutcoach/.test(pn), 'payout now: the ZEUS card coach line + the tax pot');
const tx = await ask('taxes on a $1,000 payout'); console.log('   > ' + tx.replace(/\n/g, '\n     '));
ok(/put \$300 in the tax pot \(30%\), \$700 is yours/.test(tx) && /Next estimated-tax date: Fri Jan 15 2027/.test(tx) && /not tax advice/.test(tx), 'taxes: the amount asked, the next IRS date, not advice');
ok(B.nextTaxDate('2026-11-20') === '2027-01-15' && B.nextTaxDate('2026-04-16') === '2026-06-15' && B.nextTaxDate('2027-05-20') === '2027-06-15', 'next IRS dates (weekends move to Monday)');
const rv = await ask('how did yesterday go'); ok(/^Yesterday's review: Zlarior no trade, edge GREEN/.test(rv), 'review: yesterday from the PC');
const lw = await ask('what did the bots do last week'); console.log('   > ' + lw.replace(/\n/g, '\n     '));
ok(/^Last week: 1 closed trade for \+\$613/.test(lw) && /Zlarior 50K short Wed Nov 11: \+\$613 \(target\)/.test(lw) && !/Nov 16/.test(lw), 'last week: Monday to Sunday before this one');
const mo = await ask('how much will I make a month'); console.log('   > ' + mo.replace(/\n/g, '\n     '));
ok(/^About \$[\d,]+ a month to you from the \d accounts you have/.test(mo) && /Not bought yet: Rapid EOD 50K/.test(mo) && /BACKTEST/.test(mo), 'month: estimate + backtest, labelled');
const ps = await ask('how far to pass'); ok(/Zlarior 50K: \$3,807 to pass/.test(ps) && /Zlarior 25K #2: \$1,500 to pass/.test(ps) && !/ATLAS/.test(ps), 'pass: the two evals');
const ed = await ask('is the edge ok'); ok(/^Zlarior \(LIT\): (GREEN|AMBER|RED)/.test(ed) && /ATLAS: /.test(ed) && /warning light only/.test(ed), 'edge: both lights, a warning only');
const wn = await ask('when do the bots trade'); ok(/Zlarior 50K: /.test(wn), 'window: from the cards');
// offline: the PC's own state comes from the saved copy
const offPc = await B.ask('is the pc ok', { ...deps, facts: () => ({ live: { ...live, raw: null, cached: true } }) });
ok(/saved copy, offline/.test(offPc.text) && /53 GB free/.test(offPc.text), 'pc offline: the saved PC state with its age');
// the website business (team web-expert): the same playbook as Agency > Expert
for (const q of ['how do I price a 3D site', 'what do I say to a roofer', 'best niche for 3D', 'how do I handle objections', 'how do I get more website clients', 'what should I charge for a website']) ok(B.match(q) === 'web', `web: "${q}" -> web`);
const w1 = await ask('how do I price a 3D site'); console.log('   > ' + w1.replace(/\n/g, '\n     '));
ok(/^Pricing a 3D \/ immersive site\./.test(w1) && /\$500 \+ \$25 a month/.test(w1) && /\$2,500 for 5-10 products/.test(w1) && /agency\/expert\/playbook\.json/.test(w1), 'web: pricing a 3D site from the playbook (the research numbers), $ + source');
const w2 = await ask('what do I say to a roofer'); console.log('   > ' + w2.replace(/\n/g, '\n     '));
ok(/^For a roofer: lead with the Growth site \(\$2,500-\$5,000 \+ \$49-\$99 a month\)/.test(w2) && /Say: "Most homeowners/.test(w2) && /3D: maybe/.test(w2), 'web: the roofer opener + offer + 3D verdict');
const w3 = await ask('best niche for 3D');
ok(/best trades are the ones where the customer buys a place or an object: Landscaper/.test(w3) && /Skip 3D for Plumber \/ HVAC/.test(w3), 'web: best niches for 3D and the ones to skip');
// no K8 card anywhere: not this module's answer (the brain answers from kalshi.json, or says it is not connected)
const nok = await B2.ask("How's Kalshi?", { ...deps, facts: () => ({ live: { ...live, raw: null, klive: null } }), storage: { getItem: () => null, setItem: () => {} } });
ok(nok === null, 'kalshi without a K8 card: left to the brain');
ok(B.match('how much room do I have') === null && B.match('how far to target') === null, 'generic room / target questions stay with the brain (BLITZ rules)');
// size of the saved copies stays small
let bytes = 0; for (const [k, v] of store) if (k.startsWith('jarvis.biz.')) bytes += v.length;
ok(bytes < 40000, `saved copies small (${bytes} bytes)`);
console.log(`${n - fails}/${n} passed`);
process.exit(fails ? 1 : 0);
