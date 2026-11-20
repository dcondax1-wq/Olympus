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
  raw: { kalshi_live: { kind: 'kalshi_live_pub', v: 1, st: 'paper', u: '2026-11-20T11:15:02+00:00', k8: { m: 'P', nx: 1795208400, b: 55, s: 2.5, td: [2, 0, -5.08], l: 'WWWLLLL', wk: [0, 13.75], dd: [35.73, 19.25], wr: [7, 43], lp: 1 } } },
  extra: [{ id: 'b25k_2', key: 'b25k_2', name: 'Zlarior 25K #2', plan: 'Builder 25K', size: '25K', stage: 'eval', balance: 25000, room: 1000, mll: 1000, to_target: 1500, today_pnl: 0, dll: 600, dll_used: 0 }],
  verdict: { label: 'Bots running' }, klive: null };
const store = new Map();
const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) };
const files = { '../business/payday.json': 'business/payday.json', '../hub/steps.json': 'hub/steps.json', '../business/decisions.json': 'business/decisions.json',
  '../nq/news_week.json': 'nq/news_week.json', '../pythia/events.json': 'pythia/events.json' };
let offline = false;
const fakeFetch = async (u) => {
  if (offline) throw new Error('offline');
  const k = String(u).split('?')[0];
  if (!files[k]) return { ok: false, status: 404, json: async () => null, text: async () => '' };
  const body = fs.readFileSync(path.join(WEB, files[k]), 'utf8');
  return { ok: true, status: 200, json: async () => JSON.parse(body), text: async () => body };
};
const deps = { facts: () => ({ live }), now: () => NOW, fetch: fakeFetch, storage };

const Q = {
  'How are my accounts?': 'accounts', 'Is ATLAS in a trade?': 'intrade', 'How much room does Zlarior have?': 'room', 'When is my first payout?': 'payout',
  'What did the bots do today?': 'bots', 'What did the bots do this week?': 'bots', "What's on the news today?": 'news', 'What should I do today?': 'steps', "How's Kalshi?": 'kalshi',
  'open kalshi': null, 'how is blitz': null, 'explain the strategy': null, 'hello': null,
};
for (const [q, id] of Object.entries(Q)) ok(B.match(q) === id, `match "${q}" -> ${id}`);

const say = {};
for (const q of Object.keys(Q).filter((q) => Q[q])) { const r = await B.ask(q, deps); say[q] = r; console.log('   > ' + r.text.replace(/\n/g, '\n     ')); }
const T = (q) => say[q].text;
ok(/3 accounts/.test(T('How are my accounts?')) && /\$24,887/.test(T('How are my accounts?')) && /\$49,193/.test(T('How are my accounts?')) && /Zlarior 25K #2/.test(T('How are my accounts?')), 'accounts: 3 accounts with $ balances');
ok(/Source: PC report, 5 min ago/.test(T('How are my accounts?')), 'accounts: source + age line');
ok(/ATLAS 25K: YES, short 1 micro from 26,380\.75, about \+\$181 open right now \(\+2\.7R\)/.test(T('Is ATLAS in a trade?')) && /can no longer lose/.test(T('Is ATLAS in a trade?')) && !/Zlarior/.test(T('Is ATLAS in a trade?')), 'in a trade: ATLAS position in $, locked stop, ATLAS only');
ok(/Zlarior 50K: \$1,025 of \$2,000 drawdown left/.test(T('How much room does Zlarior have?')) && /Zlarior 25K #2: \$1,000 of \$1,000/.test(T('How much room does Zlarior have?')) && !/ATLAS/.test(T('How much room does Zlarior have?')), 'room: both Zlarior accounts, not ATLAS');
ok(/First payout most likely ATLAS 25K \(funded\): about \$800 around Mon Jan 4 2027/.test(T('When is my first payout?')) && /payday\.json \(2026-11-20\)/.test(T('When is my first payout?')), 'payout: ATLAS first, $ + date + source');
ok(/Today: 1 closed trade for \+\$813, 1 still open/.test(T('What did the bots do today?')) && /ATLAS EMA short today: still open/.test(T('What did the bots do today?')), 'bots today: $ + the open ATLAS trade');
ok(/This week: 3 closed trades for \+\$573 real money/.test(T('What did the bots do this week?')) && /S\/R long Tue Nov 17: -\$442 \(stop\), paper/.test(T('What did the bots do this week?')), 'bots week: Monday onward, paper trades labelled, not in the $');
ok(/Nothing big today|No US data|big release/.test(T("What's on the news today?")) && /Next big one: Non-Farm Payrolls/.test(T("What's on the news today?")), 'news: today + next big one');
ok(/things? waiting on you\. First: Add the Rapid EOD 25K/.test(T('What should I do today?')) && /Decide card/.test(T('What should I do today?')), 'steps: first to-do + decisions');
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
// no K8 card anywhere: not this module's answer (the brain answers from kalshi.json, or says it is not connected)
const nok = await B2.ask("How's Kalshi?", { ...deps, facts: () => ({ live: { ...live, raw: null, klive: null } }), storage: { getItem: () => null, setItem: () => {} } });
ok(nok === null, 'kalshi without a K8 card: left to the brain');
ok(B.match('how much room do I have') === null && B.match('how far to target') === null, 'generic room / target questions stay with the brain (BLITZ rules)');
// size of the saved copies stays small
let bytes = 0; for (const [k, v] of store) if (k.startsWith('jarvis.biz.')) bytes += v.length;
ok(bytes < 40000, `saved copies small (${bytes} bytes)`);
console.log(`${n - fails}/${n} passed`);
process.exit(fails ? 1 : 0);
