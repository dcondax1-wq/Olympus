// Information architecture of the redesigned dashboard.
// Top level: Today · Chart · Trades · Data · Modules · Settings. Every other page lives under Data (tab strip) or
// Modules (tile grid). Page ids stay the same as the classic dashboard so every page module and go('x') call still works.
export const TOP = [
  { id: 'command', label: 'Today', icon: 'today' },
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
  { id: 'lab', label: 'Experiments', icon: 'variants', desc: 'Research run library: every LIT backtest with its data' },
  { id: 'writeups', label: 'Write-ups', icon: 'reports', desc: 'Plain-language research reports, LIT first' },
  { id: 'evals', label: 'Evals', icon: 'evals', desc: 'MFFU eval odds on LIT 2026: Monte Carlo paths, live vs fast-eval' },
  { id: 'intraday', label: 'Intraday', icon: 'heat', desc: 'Weekday × hour heat map of every LIT trade (01:00-16:00)' },
  { id: 'replay', label: 'Replays', icon: 'replay', desc: 'Step through a session bar by bar' },
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

export const MODULES = [
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

export const TITLES = { data: 'Data', command: 'Today', chart: 'Chart', trades: 'Trades', modules: 'Modules', settings: 'Settings' };
for (const p of [...DATA, ...MODULES]) TITLES[p.id] = p.label;
for (const p of ARCHIVE) TITLES[p.id] = p.label + ' · archive';

export const groupOf = (id) => DATA.some(p => p.id === id) ? 'data' : MODULES.some(p => p.id === id) ? 'modules' : ARCHIVE.some(p => p.id === id) ? 'archive' : id;
