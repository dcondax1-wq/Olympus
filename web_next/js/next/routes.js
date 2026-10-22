// Information architecture of the redesigned dashboard.
// Top level: Today · Chart · Trades · Data · Modules · Settings. Every other page lives under Data (tab strip) or
// Modules (tile grid). Page ids stay the same as the classic dashboard so every page module and go('x') call still works.
export const TOP = [
  { id: 'command', label: 'Today', icon: 'today' },
  { id: 'brain', label: 'Bot Brain', icon: 'brain' },          // js/next/brain.js: what the bot is thinking (read-only)
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
  { id: 'second', label: 'Second strategies', icon: 'variants', desc: 'PAPER: EMA London pullback, MACD sweep divergence, S/R NY reclaim next to LIT: rules, today, paper trades, backtest' },
  { id: 'intel', label: 'Trade intel', icon: 'stats', desc: 'Every trade (backtest, paper, live) with ~60 facts, the signs of winners vs losers, MFE / MAE' },
  { id: 'edge', label: 'Edge', icon: 'heat', desc: 'Where LIT makes its money: R, exits, MFE / MAE, stop size, hour, weekday, levels' },
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
  { id: 'firms', label: 'Prop Firms', icon: 'prop', desc: 'Every plan compared: rules, prices, codes, payouts, bots, live accounts, LIT fit, what to buy next' },
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
  { id: 'mffurules', label: 'MFFU rules', icon: 'rules', desc: 'The Builder 50K rulebook with how sure each rule is, and how LIT fits it' },
  { id: 'litday', label: 'LIT Day plan', icon: 'clock', desc: 'Day clock 18:00-17:00 ET, what happens next, pre-session checklist, week planner' },
  { id: 'litlevels', label: 'LIT Levels', icon: 'target', desc: 'Setup tracker (sweep → CISD → limit → 1m CISD) and every LIT level with its distance' },
  { id: 'litcockpit', label: 'Eval cockpit', icon: 'wallet', desc: 'What one stop-out or winner does to the MFFU eval; pass / fail odds from this balance' },
  { id: 'strategy', label: 'Strategy', icon: 'strategy', desc: 'LIT, the locked rulebook in plain language, with the numbers' },
  { id: 'rules', label: 'Strategy Rules', icon: 'rules', desc: 'The exact locked strategy (STRATEGY.md)' },
  { id: 'live', label: 'Paper Bot · LIT', icon: 'engine', desc: 'Paper bot control, model state, ledger' },
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

export const TITLES = { data: 'Data', command: 'Today', brain: 'Bot Brain', botctl: 'Bot Control', accounts: 'Accounts', chart: 'Chart', trades: 'Trades', modules: 'Modules', settings: 'Settings' };
for (const p of [...DATA, ...MODULES]) TITLES[p.id] = p.label;
for (const p of ARCHIVE) TITLES[p.id] = p.label + ' · archive';

export const groupOf = (id) => DATA.some(p => p.id === id) ? 'data' : MODULES.some(p => p.id === id) ? 'modules' : ARCHIVE.some(p => p.id === id) ? 'archive' : id;
