// ZEUS today (night-voice 2026-11-18): node tests for jarvis/zeus.js and its place in brain.js. The owner's six daily questions
// ("how are my accounts", "did ZEUS trade today", "how much to pass", "when is my payout", "is the PC on", "pause ZEUS") answered from
// the PC feed (a real lite live.json of 2026-11-17 20:44 ET, account ids replaced: tests/fixtures/jarvis_zeus_lite.json), the Board
// and business/accounts.json; the iPhone voice-mode defaults (hands-free again, hold to talk as the automatic fallback).
//   TZ=America/New_York node tests/test_jarvis_zeus.mjs        (run by tests/test_jarvis_skills.py)
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const WP = path.join(ROOT, 'tools', 'web_public');
const imp = (p) => import(pathToFileURL(path.join(WP, p)).href);
const rq = createRequire(import.meta.url);
global.window = {};
const F = rq(path.join(WP, 'pc_feed.js'));
const Z = await imp('jarvis/zeus.js'), B = await imp('jarvis/brain.js'), V = await imp('jarvis/voice-mode.js');
const LITE = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests', 'fixtures', 'jarvis_zeus_lite.json'), 'utf8'));
const PLAN = JSON.parse(fs.readFileSync(path.join(WP, 'business', 'accounts.json'), 'utf8'));

let fails = 0, passes = 0;
const check = (name, ok, info) => { if (ok) passes++; else { fails++; console.log('FAIL ' + name + (info ? ' :: ' + String(info).slice(0, 600) : '')); } };
const mkStore = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), key: (i) => [...m.keys()][i], get length() { return m.size; } }; };
const liveOf = (lite) => { const raw = { ...F.toLive(lite, null), src: 'pc_feed' }, b = raw.board || {}; return { lit: b.lit, atlas: b.atlas, verdict: raw.pc_verdict, running: b.running, t: raw.t, trades: b.trades || [], raw }; };
const T0 = (LITE.t + 180) * 1000;                                  // 3 minutes after the PC's report (Tue 20:47 ET = Wed's session)

// ---------------------------------------------------------------------------------------------- 1. what was asked
{
  const K = [['how are my accounts', 'accounts'], ['How are my accounts?', 'accounts'], ['my accounts', 'accounts'], ['accounts status', 'accounts'], ['how is zeus doing', 'accounts'], ['zeus', 'accounts'],
    ['did zeus trade today', 'traded'], ['did ZEUS trade today?', 'traded'], ['has zeus traded yet', 'traded'], ['any trades today', 'traded'],
    ['how much to pass', 'pass'], ['how much more to pass', 'pass'], ['how much do i need to pass', 'pass'], ['how much left to pass', 'pass'],
    ['when is my payout', 'payout'], ["when's my first payout", 'payout'], ['when do i get paid', 'payout'], ['next payout', 'payout'], ['payout', 'payout'],
    ['is the pc on', 'pc'], ['is my pc online', 'pc'], ['is the computer running', 'pc'], ['pc status', 'pc'],
    ['pause zeus', 'pause'], ['stop zeus', 'pause'], ['how do i pause the bot', 'pause'], ['where is the pause button', 'pause'], ['zeus off', 'pause']];
  for (const [q, k] of K) check(`kindOf("${q}") = ${k}`, Z.kindOf(q.toLowerCase()) === k, Z.kindOf(q.toLowerCase()));
  for (const q of ['mffu payout rules', 'what are the payout rules', 'how are the bots', 'did we trade today', 'how close am I to passing', 'where are my payouts', 'stop the bot', 'whats my balance', 'stop talking'])
    check(`kindOf("${q}") = none (the older answers keep it)`, Z.kindOf(q) === null, Z.kindOf(q));
  check('alias: zeus means the bots', Z.alias('arm ZEUS now') === 'arm the bots now' && Z.alias("zeus's room") === 'the bots room');
  check('scrubIds: an account id and its last digits never show', Z.scrubIds('routing to MFFUEVBLDR…1234 through NinjaTrader') === 'routing to your account through NinjaTrader' && Z.scrubIds('account 123456') === 'your account');
  check('tradingDay: the CME day starts 18:00 ET', Z.tradingDay(Date.parse('2026-11-17T23:30:00Z')) === '2026-11-18' && Z.tradingDay(Date.parse('2026-11-17T20:00:00Z')) === '2026-11-17');
}

// ---------------------------------------------------------------------------------------------- 2. the six answers (zeus.js alone)
const z = Z.createZeus({ getPlan: async () => PLAN, getBoard: async () => null, hidden: () => true });
const A = {};
for (const q of ['how are my accounts', 'did zeus trade today', 'how much to pass', 'when is my payout', 'is the pc on', 'pause zeus']) A[q] = await z.answer(q, q, liveOf(LITE), T0);
{
  const a = A['how are my accounts'].text;
  check('accounts: the source and its age first', /^Your accounts \(PC, 3 min ago\):/.test(a), a);
  check('accounts: Zlarior 50K eval with balance, today, $ to pass, room', a.includes('Zlarior 50K eval: $49,193, today $0, $3,807 to pass, $1,025 room.'), a);
  check('accounts: ATLAS is FUNDED (no "to target"): $ to the first $1,000 payout', a.includes('ATLAS 25K funded: $25,000, today $0, $2,100 to the first $1,000 payout, $1,000 room.') && !/ATLAS[^\n]*to pass/.test(a), a);
  check('accounts: the new 25K eval from the PC feed, named as in the plan', a.includes('Zlarior 25K #2 eval: $25,000, today $0, $1,500 to pass, $1,000 room.'), a);
  check('accounts: what ZEUS waits for', /ZEUS: Zlarior waiting for London sweep/.test(a), a);
  check('accounts: spoken in dollars, "number 2"', /3,807 dollars to pass/.test(A['how are my accounts'].speak) && /number 2/.test(A['how are my accounts'].speak), A['how are my accounts'].speak);
  const t = A['did zeus trade today'].text;
  check('traded: no trade this session (Wed Nov 18), the last ones named with $', /^No: ZEUS has not traded yet this session \(Wed Nov 18\)\./.test(t) && /Last trades, Tue Nov 17: ATLAS long 4 micros, stop, −\$442; ATLAS short 3 micros, target, \+\$2,688\./.test(t), t);
  const p = A['how much to pass'].text;
  check('pass: each eval, target and room; ATLAS already passed', p.includes('Zlarior 50K: $3,807 to pass (target $53,000), $1,025 of room left.') && p.includes('Zlarior 25K #2: $1,500 to pass (target $26,500)') && p.includes('ATLAS 25K: already passed, funded now.'), p);
  const y = A['when is my payout'].text;
  check('payout: ATLAS first, the $27,100 line, the full $1,000 ($800 to you, $560 after tax)', /^ATLAS 25K \(funded\): first payout when the balance reaches \$27,100 \(\$2,100 to go\), then ask the full \$1,000 \(\$800 to you, \$560 after the 30% tax pot\)/.test(y), y);
  check('payout: the evals pass first, with the plan\'s estimate', y.includes('Zlarior 50K (eval): pass first ($3,807 to go); about early Jan') && y.includes('Zlarior 25K #2 (eval): pass first ($1,500 to go)'), y);
  const c = A['is the pc on'].text;
  check('pc: yes, its check-in age, running LIVE, NinjaTrader, no open trade', c === 'Yes: the PC checked in 3 min ago. ZEUS is running (LIVE), NinjaTrader connected, no open trade.', c);
  const u = A['pause zeus'];
  check('pause: never acts, says where the buttons are', u.refused === true && /can't pause ZEUS/.test(u.text) && /Pause until tomorrow/.test(u.text) && /LE STOP BOT/.test(u.text) && u.intent === 'zeus_pause', u.text);
  check('no answer shows an account id', Object.values(A).every((r) => !/1234|MFFUEV/.test(r.text + r.speak)));
}
// the PC goes quiet: the answers say how old the numbers are; the PC answer says so plainly
{
  const late = await z.answer('is the pc on', 'is the pc on', liveOf(LITE), T0 + 50 * 60e3);
  check('pc 53 min old: not sure, last check-in', /^Not sure: its last check-in was 53 min ago/.test(late.text), late.text);
  const off = await z.answer('is the pc on', 'is the pc on', liveOf(LITE), T0 + 9 * 3600e3);
  check('pc 9 h old: no, silent, PC_DOCTOR', /^No: the PC has been silent for 9 h/.test(off.text) && /PC_DOCTOR/.test(off.text), off.text);
  const acc = await z.answer('how are my accounts', 'how are my accounts', liveOf(LITE), T0 + 9 * 3600e3);
  check('accounts 9 h old: "may be old"', /PC last report 9 h ago: may be old/.test(acc.text), acc.text);
  const stopped = await z.answer('is the pc on', 'is the pc on', liveOf({ ...LITE, reporter: { ...LITE.reporter, server: false } }), T0);
  check('pc on, bot server down: open LE START', /bot server is not answering: on the PC, open LE START/.test(stopped.text), stopped.text);
  const noFeed = await z.answer('is the pc on', 'is the pc on', null, T0);
  check('no PC feed: the older rules answer "is the pc on"', noFeed === null);
}
// a trade this session, and no PC feed at all (the Board's rows)
{
  const L2 = JSON.parse(JSON.stringify(LITE));
  L2.board.trades.push({ acct: 'lit', day: '2026-11-18', entry_t: LITE.t + 7 * 3600, side: 'SHORT', qty: 2, exit: 'TARGET', usd: 1840, open: false });
  L2.board.lit.trades_today = 1;
  const r = await z.answer('did zeus trade today', 'did zeus trade today', liveOf(L2), (LITE.t + 8 * 3600) * 1000);
  check('traded: yes, this session, $ and the trade', /^Yes: ZEUS took 1 trade this session \(Wed Nov 18\), \+\$1,840/.test(r.text) && /Zlarior: short 2 micros, target, \+\$1,840\./.test(r.text), r.text);
  const board = { t: LITE.t, accounts: [{ key: 'zlarior', name: 'Zlarior', plan: 'MFFU Builder 50K', stage: 'eval', balance: 49192.78, room: 1025, to_pass: 3807.22, src: 'PLAN (owner, Nov 17)' }, { key: 'blitz', name: 'BLITZ', plan: 'MFFU 25K', stage: 'eval', balance: 25000 }] };
  const zb = Z.createZeus({ getPlan: async () => PLAN, getBoard: async () => board, hidden: () => true });
  const b = await zb.answer('how much to pass', 'how much to pass', null, T0);
  check('no PC feed: the Board\'s rows; hidden BLITZ left out', b && /Zlarior 50K: \$3,807 to pass/.test(b.text) && !/BLITZ/.test(b.text), b && b.text);
}

// ---------------------------------------------------------------------------------------------- 3. in the brain: before the older rules, ZEUS = the bots elsewhere
{
  const live = liveOf(LITE);
  const fetchMock = async (u) => { u = String(u); if (/accounts\.json/.test(u)) return { ok: true, json: async () => PLAN }; return { ok: false, status: 404, json: async () => null }; };
  const brain = B.createBrain({ getFacts: () => ({ now: new Date(T0), market: { open: true, text: 'open' }, live, kalshi: null, apps: [] }), open() {}, now: () => T0, storage: mkStore(), zenithRoutes: false, autoOpen: false, fetch: fetchMock, zeus: true });
  const r1 = await brain.ask('how are my accounts');
  check('brain: "how are my accounts" is ZEUS today', r1.intent === 'zeus_accounts' && /Zlarior 25K #2/.test(r1.text), r1.intent + ' ' + r1.text);
  const r2 = await brain.ask('Jarvis, did ZEUS trade today?');
  check('brain: "Jarvis, did ZEUS trade today?"', r2.intent === 'zeus_traded', r2.intent + ' ' + r2.text);
  const r3 = await brain.ask('pause ZEUS');
  check('brain: "pause ZEUS" explains, never acts', r3.intent === 'zeus_pause' && !r3.control && !r3.action, JSON.stringify(r3).slice(0, 300));
  const SF = await imp('jarvis/safety.js'), sk = { handle: async () => null, guard: (t) => SF.guard(t) };
  const gb = B.createBrain({ getFacts: () => ({ now: new Date(T0), live, apps: [] }), open() {}, now: () => T0, storage: mkStore(), zenithRoutes: false, autoOpen: false, fetch: fetchMock, zeus: true, skills: sk });
  for (const q of ['arm zeus', 'turn on zeus', 'unpause zeus', 'start zeus']) { const r4 = await gb.ask(q); check(`brain: "${q}" is refused by the guard (zeus = the bots)`, r4.intent === 'refuse_trade' || r4.intent === 'refuse', r4.intent + ' ' + r4.text); }
  const r5 = await brain.ask('how are the bots');
  check('brain: "how are the bots" keeps its own answer, with no account id', r5.intent !== 'zeus_accounts' && !/1234|MFFUEV/.test(r5.text), r5.intent + ' ' + r5.text);
  await brain.ask('hide my balance');
  const r6 = await brain.ask('how much to pass');
  check('brain: hidden balances hide ZEUS $ too', r6.intent === 'zeus_pass' && !/\$\d/.test(r6.text) && /\$•••/.test(r6.text), r6.text);
  const off = B.createBrain({ getFacts: () => ({ now: new Date(T0), live, apps: [] }), open() {}, now: () => T0, storage: mkStore(), zenithRoutes: false, zeus: false });
  const r7 = await off.ask('how are my accounts');
  check('brain: zeus false = the older answers', r7.intent !== 'zeus_accounts');
}

// ---------------------------------------------------------------------------------------------- 3b. night-zask: what's trading, trades per week, health
{
  const EDGE = JSON.parse(fs.readFileSync(path.join(WP, 'edge.json'), 'utf8'));
  const K = [["what's trading", 'trading'], ["what's on what account", 'trading'], ['which bot is on which account', 'trading'], ['what is each account trading', 'trading'], ['what bots are on my accounts', 'trading'],
    ['trades per week', 'perf'], ['average trades a week', 'perf'], ['how many trades a week', 'perf'], ['trades week', 'perf'], ['how is it doing', 'perf'], ['how is atlas doing', 'perf'], ['zlarior stats', 'perf'], ['win rate of zlarior', 'perf'],
    ['health', 'health'], ['zeus health', 'health'], ['edge health', 'health'], ['is the edge ok', 'health'], ["how's the edge", 'health']];
  for (const [q, k] of K) check(`kindOf("${q}") = ${k}`, Z.kindOf(q) === k, Z.kindOf(q));
  for (const q of ['whats my win rate', 'what is my profit factor', 'how often do i win', 'how am i doing today', 'health check', 'how are the bots', 'how are the bots doing', 'is the kalshi bot running', 'what did i say about trading', 'arm live trading'])
    check(`kindOf("${q}") = none (other answers keep it)`, Z.kindOf(q) === null, Z.kindOf(q));
  check('kindOf: "how is zeus doing" stays the accounts answer', Z.kindOf('how is zeus doing') === 'accounts');
  const ze = Z.createZeus({ getPlan: async () => PLAN, getBoard: async () => null, getEdge: async () => EDGE, hidden: () => true });
  const t = await ze.answer("what's trading", "what's trading", liveOf(LITE), T0);
  check('trading: each account -> its bot, stage, balance, $ to pass / payout line, room', t.intent === 'zeus_trading' && /^What each account trades \(PC, 3 min ago\):/.test(t.text)
    && t.text.includes('Zlarior 50K eval → Zlarior (LIT), LIVE: $49,193, $3,807 to pass, $1,025 room.') && t.text.includes('ATLAS 25K funded → ATLAS, LIVE: $25,000, $2,100 to the first $1,000 payout, $1,000 room.')
    && t.text.includes('Zlarior 25K #2 eval → Zlarior (LIT)') && /\$1,500 to pass/.test(t.text), t.text);
  check('trading: spoken short', /Zlarior 50K eval runs Zlarior, at 49,193 dollars/.test(t.speak) && /ATLAS 25K funded runs ATLAS/.test(t.speak), t.speak);
  const p = await ze.answer('trades per week', 'trades per week', liveOf(LITE), T0);
  const BL = EDGE.bots.lit, BA = EDGE.bots.atlas;
  check('perf: per bot, last 40 sessions, trades/week, win %, PF, $/month from edge.json', p.intent === 'zeus_perf' && p.text.includes('Zlarior (LIT): ' + BL.tpw + ' trades/week, ' + Math.round(BL.win) + '% win, PF 3.8, about $3,440/month. Edge GREEN. Data to Nov 6')
    && p.text.includes('ATLAS: 3 trades/week, 58% win, PF 1.4, about $411/month (eval size). Edge AMBER. Data to Oct 16') && BA.tpw === 3, p.text);
  check('perf: says how old and what the numbers are (not the accounts\' fills)', /11 days old/.test(p.text) && /not your accounts' fills/.test(p.text) && /up to 32 days old/.test(p.speak), p.text + ' | ' + p.speak);
  const h = await ze.answer('health', 'health', liveOf(LITE), T0);
  check('health: the edge light for both bots + "PC reported 3 min ago"', h.intent === 'zeus_health' && /Zlarior edge: GREEN/.test(h.text) && /ATLAS edge: AMBER/.test(h.text) && /PC reported 3 min ago: ZEUS running \(LIVE\), NinjaTrader connected\./.test(h.text) && /The edge data is old/.test(h.text), h.text);
  const L3 = { ...LITE, eh: { d: '2026-11-17', z: ['R', 0.8, 3.9], a: ['G', 3.1, 2.8, '2026-11-17'], t: LITE.t } };
  const h2 = await ze.answer('edge health', 'edge health', liveOf(L3), T0);
  check('health: the PC\'s newer "eh" wins over edge.json', /Zlarior edge: RED/.test(h2.text) && /data to Nov 17\./.test(h2.text) && !/edge data is old/.test(h2.text), h2.text);
  check('pickEdge: newer day wins, else site', Z.pickEdge(EDGE, liveOf(L3)).src === 'PC' && Z.pickEdge(EDGE, liveOf(LITE)).src === 'site' && Z.pickEdge(null, null) === null);
  const h3 = await ze.answer('health', 'health', null, T0);
  check('health with no PC feed: says the PC report is missing (no invented age)', /PC: no report loaded/.test(h3.text) && /Zlarior edge: GREEN/.test(h3.text), h3.text);
  const zn = Z.createZeus({ getPlan: async () => PLAN, getBoard: async () => null, getEdge: async () => null, hidden: () => true });
  const m1 = await zn.answer('trades per week', 'trades per week', liveOf(LITE), T0);
  check('perf with no edge.json: says what is missing, no numbers', m1.missing === true && /edge\.json\) did not load/.test(m1.text) && !/\d+(\.\d)? trades\/week/.test(m1.text), m1.text);
  const zo = Z.createZeus({ getPlan: async () => PLAN, getBoard: async () => null, getEdge: async () => ({ kind: 'le-edge', eh: EDGE.eh }), hidden: () => true });
  const m2 = await zo.answer('how is it doing', 'how is it doing', liveOf(LITE), T0);
  check('perf with an old edge.json (no bots): says so', /no per-bot numbers yet/.test(m2.text), m2.text);
  const m3 = await zn.answer('health', 'health', liveOf(LITE), T0);
  check('health with no edge at all: "Edge light: missing", still the PC age', /Edge light: missing/.test(m3.text) && /PC reported 3 min ago/.test(m3.text), m3.text);
  const empty = await zn.answer("what's trading", "what's trading", null, T0);
  check('trading with no data: says it has no numbers', /I have no account numbers right now/.test(empty.text), empty.text);
  check('no new answer shows an account id', [t, p, h, h2, h3, m1, m2, m3].every((r) => !/1234|MFFUEV|b25k_2|mffu50k/.test(r.text + r.speak)));
  // in the brain: edge.json through its fetch, before the older rules
  const live = liveOf(LITE);
  const fm = async (u) => { u = String(u); if (/accounts\.json/.test(u)) return { ok: true, json: async () => PLAN }; if (/edge\.json/.test(u)) return { ok: true, json: async () => EDGE }; return { ok: false, status: 404, json: async () => null }; };
  const br = B.createBrain({ getFacts: () => ({ now: new Date(T0), market: { open: true, text: 'open' }, live, kalshi: null, apps: [] }), open() {}, now: () => T0, storage: mkStore(), zenithRoutes: false, autoOpen: false, fetch: fm, zeus: true });
  const b1 = await br.ask('Jarvis, what is trading on which account?'), b2 = await br.ask('average trades per week?'), b3 = await br.ask('health');
  check('brain: "what is trading on which account" -> zeus_trading', b1.intent === 'zeus_trading', b1.intent + ' ' + b1.text);
  check('brain: "average trades per week" -> zeus_perf from ../edge.json', b2.intent === 'zeus_perf' && /2\.5 trades\/week/.test(b2.text), b2.intent + ' ' + b2.text);
  check('brain: "health" -> zeus_health', b3.intent === 'zeus_health' && /PC reported/.test(b3.text), b3.intent + ' ' + b3.text);
  check('brain.js hands zeus.js ../edge.json', fs.readFileSync(path.join(WP, 'jarvis', 'brain.js'), 'utf8').includes("getEdge: getJ('../edge.json')"));
}

// ---------------------------------------------------------------------------------------------- 4. voice mode: hands-free again, hold to talk as the iPhone's fallback
{
  check('voice mode: hands-free by default everywhere (the 2026-11-06 conversation)', V.defaultPtt(null) === false && V.defaultPtt(undefined) === false);
  check('voice mode: his saved choice wins', V.defaultPtt(true) === true && V.defaultPtt(false) === false);
  check('iPhone: an automatic listen refused -> hold to talk', V.shouldFallBack({ ios: true, auto: true, ptt: false, error: 'not-allowed' }) && V.shouldFallBack({ ios: true, auto: true, ptt: false, error: 'service-not-allowed' }));
  check('iPhone: nothing heard twice -> hold to talk; once is fine', V.shouldFallBack({ ios: true, auto: true, ptt: false, error: 'no-speech', silent: 2 }) && !V.shouldFallBack({ ios: true, auto: true, ptt: false, error: 'no-speech', silent: 1 }));
  check('no fallback: not an iPhone, a tap, or already hold to talk', !V.shouldFallBack({ ios: false, auto: true, ptt: false, error: 'not-allowed' }) && !V.shouldFallBack({ ios: true, auto: false, ptt: false, error: 'not-allowed' }) && !V.shouldFallBack({ ios: true, auto: true, ptt: true, error: 'not-allowed' }));
  const VC = await imp('jarvis/voice-classic.js'), src = fs.readFileSync(path.join(WP, 'jarvis', 'voice-mode.js'), 'utf8');
  check('voice mode: the Classic Jarvis look gets the old violet screen (voice-classic.js, appended to the sheet)', /html\[data-jlook=classic\] \.vm\{/.test(VC.CLASSIC_VM_CSS) && /Orbitron/.test(VC.CLASSIC_VM_CSS) && VC.CLASSIC_SPEC === '#c084fc' && src.includes("import('./voice-classic.js')"));
  check('every Classic rule is scoped to the Classic look (AGORA untouched)', VC.CLASSIC_VM_CSS.split('\n').filter(Boolean).every((l) => l.startsWith('html[data-jlook=classic]')));
}

console.log(`${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
