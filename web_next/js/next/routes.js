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

export const DATA = [
  { id: 'results', label: 'Results', icon: 'results', desc: 'Live settings, 5-year replay: periods, months, eval odds' },
  { id: 'lab', label: 'Experiments', icon: 'variants', desc: 'Research run library: every backtest with its data' },
  { id: 'writeups', label: 'Write-ups', icon: 'reports', desc: 'Plain-language research reports' },
  { id: 'backtest', label: 'Backtests', icon: 'backtest', desc: 'Run the engine with any parameters' },
  { id: 'replay', label: 'Replays', icon: 'replay', desc: 'Step through a session bar by bar' },
  { id: 'variants', label: 'Tested Variants', icon: 'variants', desc: 'Every variant tested, 2026 vs 5 years' },
  { id: 'learned', label: 'What the Bot Learned', icon: 'learned', desc: 'Lessons that held in both periods' },
  { id: 'study', label: 'Study Trades', icon: 'study', desc: 'Trades under review, with charts' },
  { id: 'analytics', label: 'Deep Stats', icon: 'stats', desc: 'Distributions, streaks, MAE/MFE' },
  { id: 'ops', label: 'Data Sources', icon: 'sources', desc: 'Data files, coverage, health' },
];

export const MODULES = [
  { id: 'rules', label: 'Strategy Rules', icon: 'rules', desc: 'The exact locked strategy (STRATEGY.md)' },
  { id: 'live', label: 'Liquidity Engine', icon: 'engine', desc: 'Paper bot control, model state, ledger' },
  { id: 'cold', label: 'Cold-Streak Filter', icon: 'cold', desc: 'Half size when the last 15 signals ≤ 0R' },
  { id: 'risk', label: 'Risk & Sizing', icon: 'risk', desc: '$800 to a 20-pt stop, scaled down beyond' },
  { id: 'news', label: 'Markets & News', icon: 'news', desc: 'Calendar, headlines, cross-market, gamma' },
  { id: 'regime', label: 'Regimes', icon: 'regime', desc: 'Strategy result by market regime' },
  { id: 'conf', label: 'Confluence Lab', icon: 'conf', desc: 'Shadow trades and confluence edge' },
  { id: 'robust', label: 'Robustness', icon: 'robust', desc: 'Stress, placebo, heatmaps, out-of-sample' },
  { id: 'prop', label: 'Prop Firms', icon: 'prop', desc: 'MFFU eval paths, Monte Carlo, payouts' },
  { id: 'memory', label: 'Memory', icon: 'memory', desc: 'Every routed paper trade, with notes' },
  { id: 'briefing', label: 'Briefing', icon: 'briefing', desc: 'Pre-market game plan and levels' },
  { id: 'report', label: 'Reports', icon: 'reports', desc: 'Daily report for any session' },
  { id: 'review', label: 'Weekly Review', icon: 'review', desc: 'The week in trades and takeaways' },
  { id: 'journal', label: 'Journal', icon: 'journal', desc: 'Your notes on each trade' },
  { id: 'tv', label: 'TradingView', icon: 'tv', desc: 'Pine strategy, data import, webhooks' },
  { id: 'alerts', label: 'Alerts', icon: 'alerts', desc: 'Telegram / Discord / phone alerts' },
  { id: 'launch', label: 'Launch Control', icon: 'launch', desc: 'Readiness checklist and blackouts' },
  { id: 'playbook', label: 'Playbook', icon: 'playbook', desc: 'Setup cards and checklists' },
];

export const TITLES = { data: 'Data', command: 'Today', chart: 'Chart', trades: 'Trades', modules: 'Modules', settings: 'Settings' };
for (const p of [...DATA, ...MODULES]) TITLES[p.id] = p.label;

export const groupOf = (id) => DATA.some(p => p.id === id) ? 'data' : MODULES.some(p => p.id === id) ? 'modules' : id;
