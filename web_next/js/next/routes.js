// Information architecture of the redesigned dashboard.
// Top level (2026-10-25 PM): Home · Zlarior · ATLAS · Results · All tools (+ Settings, Advanced folded). Each bot has its
// own page with sections (BOTS below); every other page lives under Results (tab strip) or All tools (tile grid). Page
// ids stay the same as the classic dashboard so every page module and go('x') call still works.
// "Zlarior" is the display name of the LIT bot (owner 2026-10-25): every key, file and setting stays "lit".
export const TOP = [
  { id: 'cc', label: 'Command center', icon: 'command' },     // js/next/cc.js: both accounts, health lights, what the bot waits for
  { id: 'zlarior', label: 'Zlarior', icon: 'zlarior' },        // the LIT bot's sections (no page of its own: opens its last section page)
  { id: 'command', label: 'Today', icon: 'today' },
  { id: 'brain', label: 'Bot Brain', icon: 'brain' },          // js/next/brain.js: what the bot is thinking (read-only)
  { id: 'atlas', label: 'ATLAS', icon: 'atlas' },              // js/next/second.js: strategy 2 on the 25K (EMA + MACD + S/R)
  { id: 'blitz', label: 'BLITZ', icon: 'blitz' },              // js/next/blitz.js + blitzcore.js: strategy 3, the scalper (2026-10-29)
  { id: 'botctl', label: 'Bot', icon: 'power' },
  { id: 'accounts', label: 'Accounts', icon: 'wallet' },
  { id: 'chart', label: 'Chart', icon: 'chart' },
  { id: 'trades', label: 'Trades', icon: 'trades' },
  { id: 'data', label: 'Data', icon: 'data' },
  { id: 'modules', label: 'Modules', icon: 'modules' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
];

// LIT is the live strategy since 2026-10-18: Results, Lab, Evals, Intraday, Lessons, Strategy and Risk read LIT's files.
// The previous strategy's pages (Liquidity Engine, Oct 17: they run or read the old engine) live under Modules → Archive.
export const DATA = [
  { id: 'results', label: 'Results', icon: 'results', desc: 'LIT replay: 2026 (H1 picked, H2 check), 2021-25 reference, eval odds' },
  { id: 'perf', label: 'Performance', icon: 'robust', desc: 'Range (is live inside the expected band) · Live vs backtest · Exit efficiency · Robustness · Months · Status' },
  { id: 'scale', label: 'Scaling plan', icon: 'prop', desc: 'Step N of the ladder (2 -> 10 accounts, LIT + ATLAS), the next account, its trigger and progress, $ a month 2026-like vs 2025-like' },
  { id: 'intel', label: 'Trade intel', icon: 'stats', desc: 'Every trade (backtest, paper, live) with ~60 facts, the signs of winners vs losers, MFE / MAE' },
  { id: 'edge', label: 'Edge', icon: 'heat', desc: 'Where Zlarior makes its money: R, exits, MFE / MAE, stop size, hour, weekday, levels' },
  { id: 'pnlcal', label: 'P&L Calendar', icon: 'calendar', desc: 'Daily P&L month grid (backtest or the PC bot), streaks, this week vs the backtest' },
  { id: 'lab', label: 'Experiments', icon: 'variants', desc: 'Research run library: every LIT backtest with its data' },
  { id: 'writeups', label: 'Write-ups', icon: 'reports', desc: 'Plain-language research reports, LIT first' },
  { id: 'evals', label: 'Evals', icon: 'evals', desc: 'MFFU eval odds on LIT 2026: Monte Carlo paths, live vs fast-eval' },
  { id: 'intraday', label: 'Intraday', icon: 'heat', desc: 'Weekday × hour heat map of every LIT trade (01:00-16:00)' },
  { id: 'replay', label: 'Replays', icon: 'replay', desc: 'Step through a session bar by bar' },
  { id: 'setups', label: 'Rejected setups', icon: 'variants', desc: 'Every LIT 5m CISD and the first rule it failed: last 20 sessions, 2026 H1 / H2, 2021-25' },
  { id: 'sensitivity', label: 'Sensitivity', icon: 'robust', desc: 'Heat maps of the live LIT knobs: depth x displacement, stop range, 15-minute check, BE offset' },
  { id: 'learned', label: 'What the Bot Learned', icon: 'learned', desc: 'Lessons from the LIT replay trades' },
  { id: 'ops', label: 'Data Sources', icon: 'sources', desc: 'Data files, coverage, health' },
];

export const ARCHIVE_LABEL = 'Archive: previous strategy (Liquidity Engine, Oct 17)';
export const ARCHIVE = [
  { id: 'cold', label: 'Cold-Streak Filter', icon: 'cold', desc: 'Quarter size when the last 15 signals ≤ 0R (old engine)' },
  { id: 'prop', label: 'Prop Firms', icon: 'prop', desc: 'MFFU eval paths and Monte Carlo of the engine backtest' },
  { id: 'backtest', label: 'Backtests', icon: 'backtest', desc: 'Run the old engine with any parameters' },
  { id: 'variants', label: 'Tested Variants', icon: 'variants', desc: 'Every engine variant tested, 2026 vs 5 years' },
  { id: 'study', label: 'Study Trades', icon: 'study', desc: 'Engine trades reviewed before LIT' },
  { id: 'analytics', label: 'Deep Stats', icon: 'stats', desc: 'Distributions, streaks, MAE/MFE of the engine backtest' },
  { id: 'regime', label: 'Regimes', icon: 'regime', desc: 'Engine result by market regime' },
  { id: 'conf', label: 'Confluence Lab', icon: 'conf', desc: 'Engine shadow trades and confluence edge' },
  { id: 'robust', label: 'Robustness', icon: 'robust', desc: 'Engine stress, placebo, heatmaps, out-of-sample' },
  { id: 'playbook', label: 'Playbook', icon: 'playbook', desc: 'The engine’s setup cards and checklists' },
];

// Hub pages (js/next/hubpages.js): the business side and the context around the bot, grouped in five pages.
export const HUB = [
  { id: 'firms', label: 'Prop Firms', icon: 'prop', desc: 'Every plan compared: rules, prices, codes, payouts, bots, live accounts, Zlarior fit, what to buy next' },
  { id: 'business', label: 'Business', icon: 'wallet', desc: 'Eval odds now, floor gauge, MFFU rules check, payout calendar, fees and net P&L, tax, Z06 goal, planners' },
  { id: 'market', label: 'Market', icon: 'regime', desc: 'VIX regime + target band, overnight recap, levels map, week calendar, earnings, holidays, roll' },
  { id: 'learn', label: 'Learn', icon: 'learned', desc: 'LIT step by step, glossary, research library with verdicts, strategy versions, trade gallery' },
  { id: 'system', label: 'System', icon: 'sources', desc: 'Upgrades with vs without, PC uptime, discipline log, data quality' },
];

// Operator tools (js/next/pcops.js, read-only: engine/pcops_api.py)
export const OPS = [
  { id: 'morning', label: 'Morning report', icon: 'sun', desc: 'What happened overnight: trades, alerts, feed gaps, restarts, errors, then today ahead' },
  { id: 'livechart', label: 'Live chart', icon: 'chart', desc: 'Today\'s bars with the LIT levels the bot watches, swept levels and the open trade lines' },
  { id: 'botlog', label: 'Bot log', icon: 'reports', desc: 'Today\'s bot, order, NinjaTrader and server log with filters and search' },
  { id: 'ntpanel', label: 'NinjaTrader', icon: 'sources', desc: 'Connection, bar ages, order files sent / received, positions, a fix for every red row' },
  { id: 'timeline', label: 'Session timeline', icon: 'clock', desc: '18:00 → 17:00 ET: killzones, news, setups, entries / exits, restarts, updates' },
  { id: 'livesettings', label: 'Live settings', icon: 'settings', desc: 'Every live_model.json switch in plain words with its tested numbers (read-only)' },
];

export const MODULES = [
  ...OPS,
  ...HUB,
  { id: 'evalhq', label: 'Eval HQ', icon: 'prop', desc: 'The 2-week pass path: $ to go, $ per session, what one winner pays, the odds' },
  { id: 'mffurules', label: 'MFFU rules', icon: 'rules', desc: 'The Builder 50K rulebook with how sure each rule is, and how Zlarior fits it' },
  { id: 'litday', label: 'Day plan', icon: 'clock', desc: 'Day clock 18:00-17:00 ET, what happens next, pre-session checklist, week planner' },
  { id: 'litlevels', label: 'Levels', icon: 'target', desc: 'Setup tracker (sweep → CISD → limit → 1m CISD) and every LIT level with its distance' },
  { id: 'litcockpit', label: 'Eval cockpit', icon: 'wallet', desc: 'What one stop-out or winner does to the MFFU eval; pass / fail odds from this balance' },
  { id: 'strategy', label: 'Strategy', icon: 'strategy', desc: 'Zlarior (the LIT method), the locked rulebook in plain language, with the numbers' },
  { id: 'rules', label: 'Strategy Rules', icon: 'rules', desc: 'The exact locked strategy (STRATEGY.md)' },
  { id: 'live', label: 'Paper Bot · Zlarior', icon: 'engine', desc: 'Paper bot control, model state, ledger' },
  { id: 'risk', label: 'Risk & Sizing', icon: 'risk', desc: '$800 to a 20-pt stop, scaled down beyond; weekly stop' },
  { id: 'newshub', label: 'News hub', icon: 'radar', desc: 'Next high-impact event, blackouts, 7-day calendar, headlines' },
  { id: 'news', label: 'Markets & News', icon: 'news', desc: 'Calendar, headlines, cross-market, gamma' },
  { id: 'memory', label: 'Memory', icon: 'memory', desc: 'Every routed paper trade, with notes' },
  { id: 'briefing', label: 'Briefing', icon: 'briefing', desc: 'Pre-market game plan and levels' },
  { id: 'report', label: 'Reports', icon: 'reports', desc: 'Daily report for any session' },
  { id: 'review', label: 'Weekly Review', icon: 'review', desc: 'The week in trades and takeaways' },
  { id: 'journal', label: 'Journal', icon: 'journal', desc: 'Your notes on each trade' },
  { id: 'tv', label: 'TradingView', icon: 'tv', desc: 'Pine strategy, data import, webhooks' },
  { id: 'alerts', label: 'Alerts', icon: 'alerts', desc: 'Telegram / Discord / phone alerts' },
  { id: 'launch', label: 'Launch Control', icon: 'launch', desc: 'Readiness checklist and blackouts' },
  { id: 'archive', label: 'Archive', icon: 'archive', desc: 'Previous strategy: Liquidity Engine, Oct 17 (paper shadow), kept so it can come back' },
];

// PC upgrade 2026-10-25 (js/next/cc.js, engine/pc_cc_api.py, read-only): top-level pages without a sub bar
export const CC = [
  { id: 'real', label: 'Real results', icon: 'results', desc: 'Real money only (both MFFU accounts, never the paper run): running P&L, win rate, streaks, R distribution, $ by strategy, this week, incidents, live vs the backtest band, CSV' },
  { id: 'board', label: 'Live board', icon: 'radar', desc: 'Right now on both accounts (waiting for, next window, size now, what blocks entries), today\'s map, bot health, week and eval odds, every trade with its picture + CSV' },
  { id: 'start', label: 'Start & Accounts', icon: 'power', desc: 'START BOT as one checklist (NinjaTrader, accounts, setup, Sim test, arm, running) and every account: add, balance, funded, remove' },
  { id: 'goals', label: 'Goals', icon: 'target', desc: 'Eval progress per account, 2-4 trades a week, the ATLAS 20-trade scorecard, payout and scale' },
  { id: 'evaltl', label: 'Eval timeline', icon: 'calendar', desc: 'Session-by-session P&L of the eval with the 10 / 15 session marks and the days ahead' },
  { id: 'sesscal', label: 'Session calendar', icon: 'week', desc: 'The next 20 trading days: early closes, CME holidays, the clock change' },
  { id: 'tradelog', label: 'Trade log', icon: 'trades', desc: 'Zlarior replay or PC routed trades with filters, a summary and CSV export' },
  { id: 'atlassetups', label: 'ATLAS per setup', icon: 'atlas', desc: 'EMA / MACD / S-R setups H1 / H2 / ref, sortable, the 2026 ATLAS ledger, CSV' },
  { id: 'runbook', label: 'Runbook', icon: 'rules', desc: 'Emergency steps big, then start, check, shutdown and recovery with copy buttons' },
  { id: 'audit', label: 'Audit evidence', icon: 'check', desc: 'The 2026-10-25 pre-launch audit: verdict, EXECUTION_TEST_MATRIX, every file' },
  { id: 'features', label: 'All features', icon: 'modules', desc: 'Every PC feature grouped, with search and quick tools' },
];

// Sidebar (shell.js), cleaned up 2026-10-25: six clear top items, everything else under "Advanced" (folded by default,
// in four small sections). Each page appears once. Each id must be a page; 'data' opens the last Results tab.
// NAV_NAMES only renames the sidebar entry (the page title stays TITLES[id]).
// 2026-10-25 PM: Home · Zlarior · ATLAS · Results · All tools; the pages each bot page holds are in BOTS (not repeated here).
export const GROUPS = [
  { label: 'Main', ids: ['cc', 'start', 'zlarior', 'atlas', 'real', 'modules'] },   // 2026-10-28: Real results in, the backtest page under Advanced > Results
  { label: 'Advanced', advanced: true, sections: [
    { label: 'Accounts', ids: ['board', 'goals', 'sesscal'] },
    { label: 'Bot', ids: ['morning', 'ntpanel', 'botlog', 'timeline'] },
    { label: 'Results', ids: ['data', 'scale', 'lab', 'intel'] },
    { label: 'Help', ids: ['runbook', 'audit', 'features', 'archive'] },
  ] },
];
export const NAV_NAMES = { cc: 'Home', start: 'Start', real: 'Real results', data: 'Backtest & research', modules: 'All tools', command: 'Today (classic)', archive: 'Archive (old engine)' };

// The two bot pages (2026-10-25 PM): a segmented control on top picks the section; a section with several pages shows
// them as chips. "atlas:brain" = the one ATLAS page showing one part (second.js atlasPart). Each page belongs to one bot.
// 2026-10-30 (night 3, "organized, clean"): the three bots share ONE order and the same words as the phone:
//   Today · Brain · Trades · Results · Rules  (Zlarior's Plan & levels pages are chips under Today, its Strategy is Rules;
//   ATLAS's Setups is Rules; BLITZ's Go live is a chip under Rules). Every page keeps its id and link.
export const BOTS = {
  zlarior: { name: 'Zlarior', sub: 'LIT method · 50K', segs: [
    ['Today', ['botctl', 'accounts', 'evalhq', 'evaltl', 'litcockpit', 'litday', 'litlevels', 'livechart', 'briefing', 'chart', 'command']],
    ['Brain', ['brain']],
    ['Trades', ['trades', 'tradelog', 'journal', 'review', 'memory']],
    ['Results', ['perf', 'pnlcal', 'edge', 'learnlit']],
    ['Rules', ['strategy', 'rules', 'risk', 'mffurules', 'livesettings']],
  ] },
  atlas: { name: 'ATLAS', sub: '25K', segs: [
    ['Today', ['atlas']], ['Brain', ['atlas:brain']], ['Trades', ['atlas:trades']],
    ['Results', ['atlas:results', 'atlassetups', 'learnatlas']], ['Rules', ['atlas:setups']],
  ] },
  // BLITZ (2026-10-29): the one BLITZ page in parts ("blitz:brain" = blitz.js part, store nx.bzPart), like ATLAS
  blitz: { name: 'BLITZ', sub: 'scalper · 25K', segs: [
    ['Today', ['blitz']], ['Brain', ['blitz:brain']], ['Trades', ['blitz:trades']], ['Results', ['blitz:results']],
    ['Rules', ['blitz:rules', 'blitz:golive']],
  ] },
};
export const BOT_CHIP = { botctl: 'Bot control', accounts: '50K account', evalhq: 'Eval HQ', evaltl: 'Eval timeline', litcockpit: 'Eval cockpit', command: 'Today (classic)',
  trades: 'Trades', tradelog: 'Trade log', journal: 'Journal', review: 'Weekly review', memory: 'Memory', litday: 'Day plan', litlevels: 'Levels', livechart: 'Live chart',
  chart: 'Chart', briefing: 'Briefing', perf: 'Performance', pnlcal: 'P&L calendar', edge: 'Edge', strategy: 'Strategy', rules: 'Rules (STRATEGY.md)', risk: 'Risk & sizing',
  mffurules: 'MFFU rules', livesettings: 'Live settings', 'atlas:setups': 'Rules & members', atlassetups: 'Per setup',
  'atlas:results': 'Results', learnlit: 'Learning', learnatlas: 'Learning', 'blitz:rules': 'Rules', 'blitz:golive': 'Go live' };
export const botOf = (id) => Object.keys(BOTS).find((b) => BOTS[b].segs.some((s) => s[1].some((it) => it.split(':')[0] === id))) || null;
export const groupIds = (g) => g.ids || (g.sections || []).flatMap((s) => s.ids);
// phone tab bar (the PC sidebar shows the groups)
// 2026-10-28: 'real' (Real results, js/next/real.js) in Main; the backtest 'data' page is named "Backtest & research"
export const TABS = ['cc', 'zlarior', 'atlas', 'real', 'modules'];   // 2026-10-28: Real results replaces the backtest Results tab
// 2026-10-30 (night 3, "organized, clean"): the Main items in plain sections, the same words as the phone. Each id once;
// any Main id not listed here is drawn at the end (shell.js buildNav).
export const MAIN_SECTIONS = [['', ['cc', 'start']], ['Bots', ['zlarior', 'atlas', 'blitz']], ['Live', ['mission', 'liveview', 'holo']],
  ['Money', ['real']], ['Insight', ['mind', 'deck', 'insight']], ['', ['modules']]];

export const TITLES = { cc: 'Home', zlarior: 'Zlarior', data: 'Backtest & research', command: 'Today', brain: 'Bot Brain', atlas: 'ATLAS · strategy 2 (25K)', botctl: 'Bot Control', accounts: 'Accounts', chart: 'Chart', trades: 'Trades', modules: 'All tools', settings: 'Settings' };
for (const p of [...DATA, ...MODULES, ...CC]) TITLES[p.id] = p.label;
for (const p of ARCHIVE) TITLES[p.id] = p.label + ' · archive';
TITLES.learnlit = 'Zlarior · Learning';
TITLES.learnatlas = 'ATLAS · Learning';
TITLES.blitz = 'BLITZ · strategy 3 (25K)';

export const groupOf = (id) => id === 'zlarior' ? 'zlarior' : botOf(id) ? botOf(id) : DATA.some(p => p.id === id) ? 'data' : MODULES.some(p => p.id === id) ? 'modules' : ARCHIVE.some(p => p.id === id) ? 'archive' : id;

// AI Insights (js/next/insight.js, engine/insight_api.py; read-only): one entry under the main nav
export const INSIGHT = { id: 'insight', label: 'AI Insights', icon: 'brain', desc: 'Setup radar, next entry window, live vs backtest, drift alarm, setup grade, similar trades, market regime, LIT levels, ATLAS members, Strategy 3' };
CC.push(INSIGHT);
TITLES.insight = INSIGHT.label;
GROUPS.find((g) => g.label === 'Main')?.ids?.push('insight');

// Live View (js/next/liveview.js, engine/liveview_api.py; read-only): the big white full-screen chart, right after Home
export const LIVEVIEW = { id: 'liveview', label: 'Live View', icon: 'chart', desc: 'One big full-screen chart on white: Zlarior (blue), ATLAS (orange), Strategy 3 (purple) overlays with a switch each, what each bot is thinking, and the bot\'s running feed' };
CC.push(LIVEVIEW);
TITLES.liveview = LIVEVIEW.label;
{ const g = GROUPS.find((x) => x.label === 'Main'); if (g?.ids && !g.ids.includes('liveview')) g.ids.splice(Math.max(0, g.ids.indexOf('cc') + 1), 0, 'liveview'); }

// Holodeck (js/next/holo.js + holocore.js, fx.js holo.js, 2026-10-29; read-only): the day in 3D, right after Live View
export const HOLO = { id: 'holo', label: 'Holodeck', icon: 'chart', desc: 'The day in 3D: every fill at its exact second and price (real solid, paper hollow, slippage vs the model), trades as glass volumes, each setup drawn step by step, what every bot is thinking, replay 1x-120x' };
CC.push(HOLO);
TITLES.holo = HOLO.label;
{ const g = GROUPS.find((x) => x.label === 'Main'); if (g?.ids && !g.ids.includes('holo')) { const i = g.ids.indexOf('liveview'); g.ids.splice(i >= 0 ? i + 1 : Math.max(0, g.ids.indexOf('cc') + 1), 0, 'holo'); } }

// Mission Control (js/next/mission.js + missioncore.js, 2026-10-29; read-only): the three bots in orbit, right after Home
export const MISSION = { id: 'mission', label: 'Mission Control', icon: 'target', desc: 'The three bots in orbit (Zlarior 50K, ATLAS 25K, BLITZ 25K): every number, today\'s mission, if it stops out now, why no trade yet, session timeline, alerts center, health constellation' };
CC.push(MISSION);
TITLES.mission = MISSION.label;
{ const g = GROUPS.find((x) => x.label === 'Main'); if (g?.ids && !g.ids.includes('mission')) g.ids.splice(Math.max(0, g.ids.indexOf('cc') + 1), 0, 'mission'); }

// BLITZ, the Mind and Trader's deck (2026-10-29 night, js/next/blitz.js + blitzcore.js / mindcore.js / deckcore.js; read-only):
// BLITZ right after ATLAS in Main (its sections in BOTS.blitz); Mind and Trader's deck after Real results
export const MIND = { id: 'mind', label: 'Mind', icon: 'mind', desc: 'Brain v2: the market regime, each bot\'s if-then game plan, similar past setups (win %, avg R, $), A-F trade reviews, research ideas with evidence, alerts, IQ' };
export const DECK = { id: 'deck', label: 'Trader\'s deck', icon: 'deck', desc: 'Risk meter on all accounts, the next 24 h (windows, checks, news, early closes, the clock change), eval odds from today\'s balance, real P&L calendar, trade journal, notification center, since you last looked, Holodeck replays' };
CC.push(MIND, DECK);
TITLES.mind = MIND.label;
TITLES.deck = DECK.label;
{ const g = GROUPS.find((x) => x.label === 'Main');
  if (g && g.ids && !g.ids.includes('blitz')) { const i = g.ids.indexOf('atlas'); g.ids.splice(i >= 0 ? i + 1 : g.ids.length, 0, 'blitz'); }
  if (g && g.ids && !g.ids.includes('mind')) { const i = g.ids.indexOf('real'); g.ids.splice(i >= 0 ? i + 1 : g.ids.length, 0, 'mind', 'deck'); } }

// Fleet (js/next/fleet.js, 2026-10-30): copy trading to the follower accounts (engine/fleet.py, GET /api/next/fleet)
export const FLEET = { id: 'fleet', label: 'Fleet', icon: 'modules', desc: 'Copy trading: every follower account (prop firms, Sim, your LIVE account), room the firm\'s way, today, slippage vs the lead, rule warnings, the firm rules' };
MODULES.push(FLEET); TITLES.fleet = FLEET.label;   // All tools > More (a tile), Ctrl K
