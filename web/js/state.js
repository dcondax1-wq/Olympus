import { api, store, css } from './util.js';

export const S = {
  meta: null,
  sym: store.get('sym', 'NQ'),
  tf: '5m',
  plan: store.get('plan', 'builder_50k'),
  params: store.get('params', {}),
  res: null,
  bars: {},
  page: 'command',
  listeners: [],
};

export const WINDOW_PRESETS = {
  'AM + PM killzones': [[570, 690], [810, 930]],
  'NY AM 09:30-11:30': [[570, 690]],
  'Golden hour 09:30-11:00': [[570, 660]],
  'London + NY': [[180, 300], [570, 690], [810, 930]],
  'All day 03:00-15:30': [[180, 930]],
};

// parameter schema for the backtest form: [key, label, type, hint, extra]
export const PARAM_SCHEMA = [
  ['Risk & account', [
    ['risk_usd', 'Risk per trade ($)', 'num', 'sized in micros to this $ risk', { step: 25 }],
    ['dd_aware', 'Drawdown-aware sizing', 'bool', 'cap risk to a fraction of MLL cushion'],
    ['cushion_frac', 'Cushion fraction', 'num', '', { step: 0.05 }],
    ['risk_mode', 'Risk mode', 'sel', 'cushion = % of distance to MLL', { options: ['fixed', 'cushion'] }],
    ['lock_boost', 'Risk × after MLL locks', 'num', 'eval sprint lever · 1 = off', { step: 0.25 }],
    ['grade_sizing', 'Size by trade grade (A+…D)', 'bool', 'A+ ×1.5 · A ×1.25 · B ×1 · C ×0.75 · D ×0.5'],
    ['grade_skip', 'Skip grades', 'text', 'e.g. D (defensive)'],
    ['conviction_step', 'Conviction sizing step', 'num', 'used only when grade sizing is off', { step: 0.05 }],
    ['daily_max_loss', 'Daily loss stop ($)', 'num', 'MFFU soft DLL is $1,000', { step: 50 }],
    ['max_trades_day', 'Max trades / day', 'num', '', { step: 1 }],
    ['stop_after_win', 'Stop after a winner', 'bool', 'protects the 50% consistency rule'],
    ['contract', 'Contracts', 'sel', '', { options: ['auto', 'micro', 'mini'] }],
    ['max_micros', 'Max micros', 'num', 'MFFU 50K: 40 micros / 4 minis', { step: 1 }],
    ['slippage_ticks', 'Slippage (ticks/side)', 'num', '', { step: 1 }],
  ]],
  ['Model', [
    ['stop_mode', 'Stop placement', 'sel', 'beyond sweep or beyond IFVG', { options: ['swing', 'ifvg'] }],
    ['use_cisd', 'CISD fallback trigger', 'bool', 'when the leg has no FVG'],
    ['ifvg_pick', 'IFVG choice', 'sel', 'first inversion or outermost gap', { options: ['first', 'outer'] }],
    ['arm_minor', 'Minor swings arm setups', 'bool', '15m ITH/ITL sweeps'],
    ['arm_expiry_min', 'Setup expiry (min)', 'num', '', { step: 5 }],
    ['leg_lookback_min', 'Leg lookback (min)', 'num', '', { step: 10 }],
    ['long', 'Take longs', 'bool'],
    ['short', 'Take shorts', 'bool'],
  ]],
  ['Sessions', [
    ['entry_windows', 'Entry windows', 'win', ''],
    ['arm_start', 'Sweeps arm from (ET)', 'time', ''],
    ['flat_mod', 'Flatten at (ET)', 'time', 'MFFU: flat before close'],
  ]],
  ['Targets & exits', [
    ['target_mode', 'Target', 'sel', 'next DOL won the exit study', { options: ['dol_next', 'dol', 'fixed'] }],
    ['min_rr', 'Min R to DOL', 'num', 'skip if liquidity is closer', { step: 0.25 }],
    ['max_rr', 'Max R (cap)', 'num', '', { step: 0.5 }],
    ['be_at_r', 'Breakeven at (R)', 'num', '0 = off · study: 1R best', { step: 0.25 }],
    ['time_stop_min', 'Time stop (min)', 'num', 'exit if < +0.5R by then · 0 = off', { step: 5 }],
    ['trail_mode', 'Trailing stop', 'sel', 'study: trails cut runners', { options: ['none', 'r', 'swing'] }],
    ['trail_start_r', 'Trail starts at (R)', 'num', '', { step: 0.5 }],
    ['trail_r', 'R-trail distance', 'num', '', { step: 0.25 }],
    ['stop_buffer_mult', 'Stop buffer ×', 'num', 'beyond the sweep extreme', { step: 0.25 }],
    ['partial_at', 'Partial at', 'sel', '', { options: ['r', 'pool'] }],
    ['use_fallback', 'Fallback fixed R', 'bool', 'when no pool in range'],
    ['fallback_rr', 'Fallback R', 'num', '', { step: 0.25 }],
    ['amt_targets', 'AMT levels as targets', 'bool', 'prior POC / VAH / VAL'],
    ['partial_pct', 'Partial size (0-1)', 'num', '0 = all-in runner', { step: 0.25 }],
    ['partial_r', 'Partial at (R)', 'num', '', { step: 0.25 }],
    ['be_after_partial', 'Breakeven after partial', 'bool'],
    ['exit_rules', 'Exit-signal rules', 'text', 'giveback won on all 4 periods · others: opp_disp, trig_break, stall, zone_reentry, zone_fail, opp_fvg, m15_flip, two_against, vol_against'],
    ['exit_giveback_r', 'Giveback after (R)', 'num', 'reached this, then closed below entry · 0.5 best', { step: 0.25 }],
    ['exit_learn', 'Learn other exit signals', 'bool', 'walk-forward: act once proven'],
    ['exit_learn_min', 'Learner: min cases', 'num', '', { step: 2 }],
    ['exit_learn_threshold', 'Learner: min avg gain (R)', 'num', '', { step: 0.05 }],
    ['exit_stall_bars', 'Stall after (bars)', 'num', 'no new high-water mark', { step: 1 }],
    ['ifvg_fail_exit', 'Exit if IFVG fails', 'bool', 'close back through the gap · study: cut NQ profit'],
    ['lock_at_r', 'Lock profit once at (R)', 'num', '0 = off', { step: 0.5 }],
    ['lock_r', 'Locked amount (R)', 'num', '', { step: 0.25 }],
  ]],
  ['Regime & trend-day playbook', [
    ['regime_er10_max', 'Trending above (10-day eff.)', 'num', '0 = off · 0.45 default', { step: 0.05 }],
    ['regime_mode', 'Reversals on trending days', 'sel', 'half size won the regime study', { options: ['half', 'skip', 'full'] }],
    ['be_at_r_trending', 'Trend-day breakeven at (R)', 'num', '0 = same as normal', { step: 0.25 }],
    ['max_rr_trending', 'Trend-day target cap (R)', 'num', '0 = same as normal', { step: 0.5 }],
    ['trend_model', 'Trend-day continuation setup', 'bool', 'with-trend FVG retest · rescued CFD 2025, cost NQ 2026 · awaiting 2024 data'],
    ['trend_require_regime', 'Only on trending days', 'bool'],
    ['trend_require_dir5', 'Require 5-day direction', 'bool'],
    ['trend_fvg_lookback_min', 'FVG lookback (min)', 'num', '', { step: 15 }],
    ['trend_fvg_mult', 'Min gap × min FVG', 'num', '', { step: 0.25 }],
    ['trend_full_size', 'Continuations at full size', 'bool'],
    ['g_early', 'Grade: first-45m penalty', 'num', 'discovery scan · improved all periods', { step: 1 }],
    ['g_q3', 'Grade: Q3-entry penalty', 'num', 'discovery scan', { step: 1 }],
    ['g_h1sweep', 'Grade: 1H-swing raid penalty', 'num', 'discovery scan · leaning', { step: 1 }],
    ['g_stacked', 'Grade: stacked-raid penalty', 'num', 'discovery scan · leaning', { step: 1 }],
    ['g_pd', 'Grade: discount/premium weight', 'num', 'scan says negative, but 0 / flipped lost money over 4 periods', { step: 1 }],
    ['g_london', 'Grade: London-raid penalty', 'num', 'scan stable negative · no gain on taken trades', { step: 1 }],
    ['skip_london', 'Skip London H/L raids', 'bool', 'cuts frequency to ~2.5/wk · mixed'],
  ]],
  ['Confluence', [
    ['min_score', 'Min confluence score', 'num', '', { step: 1 }],
    ['w_htf', 'HTF trend weight', 'num', '', { step: 1 }],
    ['w_protected', 'Protected H/L weight', 'num', '', { step: 1 }],
    ['w_lrl', 'LRL / HRL weight', 'num', '', { step: 1 }],
    ['w_amt', 'AMT location weight', 'num', '', { step: 1 }],
    ['w_smt', 'SMT divergence weight', 'num', '', { step: 1 }],
    ['w_quality', 'Pool quality weight', 'num', '', { step: 1 }],
  ]],
  ['Multi-timeframe', [
    ['ifvg_tf', 'IFVG timeframe', 'sel', 'highest = wait for the 15m IFVG when the leg has one', { options: ['base', 'highest'] }],
    ['w_pd', 'Premium/discount weight', 'num', '1H dealing range', { step: 1 }],
    ['w_mtf', 'MTF order-flow weight', 'num', '1D/4H/1H/15m FVG respect', { step: 1 }],
    ['w_keylevel', 'HTF key-level weight', 'num', 'sweep into 1D/4H/1H FVG', { step: 1 }],
    ['w_midnight', 'Midnight-open weight', 'num', 'true day open', { step: 1 }],
    ['w_m15', '15m structure weight', 'num', '', { step: 1 }],
    ['mtf_gate', 'MTF alignment gate', 'num', 'min net alignment (-9 = off)', { step: 1 }],
    ['counter_rr_cap', 'Counter-HTF target cap (R)', 'num', '0 = off', { step: 0.5 }],
  ]],
  ['News & volatility guard', [
    ['news_filter', 'News blackout', 'bool', 'high-impact USD releases'],
    ['news_before_min', 'Minutes before', 'num', '', { step: 5 }],
    ['news_after_min', 'Minutes after', 'num', '', { step: 5 }],
    ['fomc_pm_off', 'No FOMC-day afternoons', 'bool'],
    ['news_flatten_min', 'Flatten before release (min)', 'num', '0 = off', { step: 1 }],
    ['news_day_skip', 'Skip whole days with', 'text', 'e.g. CPI,Payrolls,FOMC'],
    ['day_range_max', 'Day-range guard (× ADR)', 'num', 'no entries after a wild day · 0 = off', { step: 0.1 }],
    ['vix_max', 'Skip if prior VIX above', 'num', '0 = off', { step: 1 }],
    ['vix_min', 'Skip if prior VIX below', 'num', '0 = off', { step: 1 }],
  ]],
  ['Learner (experimental)', [
    ['learn', 'Walk-forward learner', 'bool', 'gate entries on predicted R'],
    ['learn_min', 'Min resolved shadows', 'num', '', { step: 5 }],
    ['learn_lambda', 'Ridge penalty', 'num', '', { step: 1 }],
    ['learn_threshold', 'Take if E[R] ≥', 'num', '', { step: 0.1 }],
  ]],
  ['Liquidity pools', [
    ['pools.PD', 'Prior day H/L', 'bool'], ['pools.PW', 'Prior week H/L', 'bool'], ['pools.ASIA', 'Asia H/L', 'bool'],
    ['pools.LON', 'London H/L', 'bool'], ['pools.ON', 'Overnight H/L', 'bool'], ['pools.H1', '1H swings', 'bool'],
    ['pools.M15', '15m ITH / ITL', 'bool'],
  ]],
];

export const PRESETS = {
  'Robust default': {},
  'EVAL · Sprint ($450)': { risk_usd: 450 },
  'EVAL · Turbo (×1.5 after lock)': { risk_usd: 450, lock_boost: 1.5 },
  'FUNDED · Steady': { risk_usd: 350, stop_after_win: true },
  'Defensive (skip D grades)': { grade_skip: 'D' },
  'High conviction': { min_score: 3 },
  'Tight stops (≤40pt)': { spec: { max_stop: 40 } },
  'v1 (before studies)': { w_amt: 1, w_pd: 0, w_protected: 1, w_smt: 1, w_quality: 1, w_m15: 0, target_mode: 'dol', amt_targets: true, be_at_r: 0, time_stop_min: 0 },
  'More trades': { max_trades_day: 3, stop_after_win: false, min_score: 0 },
  'Golden hour': { entry_windows: [[570, 660]] },
  'Partials + BE': { partial_pct: 0.5, partial_r: 1, be_after_partial: true },
  'Blake strict (15m IFVG)': { ifvg_tf: 'highest' },
  'MTF aligned only': { mtf_gate: 1 },
  'Learner': { learn: true },
  'LIVE · Day 1 (conservative)': { risk_usd: 250, max_trades_day: 2, stop_after_win: true, daily_max_loss: 500, grade_skip: 'D', regime_mode: 'half' },
  'LIVE · Steady': { risk_usd: 350, max_trades_day: 2, stop_after_win: true, daily_max_loss: 600 },
  'Trend-day playbook ON': { trend_model: true },
  'Trend-day only (no reversals on trend days)': { trend_model: true, regime_mode: 'skip' },
  'Early breakeven (0.5R)': { be_at_r: 0.5 },
};

export function effective() {
  const d = S.meta?.defaults || {};
  const p = { ...d, ...S.params, pools: { ...(d.pools || {}), ...(S.params.pools || {}) } };
  return p;
}
export function getParam(key) {
  const p = effective();
  if (key.startsWith('pools.')) return p.pools[key.slice(6)];
  return p[key];
}
export function setParam(key, val) {
  if (key.startsWith('pools.')) {
    S.params.pools = { ...(S.params.pools || {}), [key.slice(6)]: val };
  } else S.params[key] = val;
  store.set('params', S.params);
}

export async function loadBars(sym, tf) {
  const k = sym + tf;
  if (S.bars[k]) return S.bars[k];
  const r = await api(`/api/bars?sym=${sym}&tf=${tf}`);
  const out = r.t.map((t, i) => ({ t, o: r.o[i], h: r.h[i], l: r.l[i], c: r.c[i], v: r.v[i], d: r.d[i], mod: r.mod[i] }));
  S.bars[k] = out;
  return out;
}

export function on(fn) { S.listeners.push(fn); }
export function emit() { for (const f of S.listeners) { try { f(S.res); } catch (e) { console.error(e); } } }

// ---- Chart.js theme
export function chartTheme() {
  if (!window.Chart) return;
  Chart.defaults.font.family = '"Space Grotesk", system-ui, sans-serif';
  Chart.defaults.font.size = 11;
  Chart.defaults.color = css('--muted');
  Chart.defaults.borderColor = css('--grid');
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = css('--surface-3');
  Chart.defaults.plugins.tooltip.titleColor = css('--ink');
  Chart.defaults.plugins.tooltip.bodyColor = css('--ink-2');
  Chart.defaults.plugins.tooltip.borderColor = css('--border');
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 9;
  Chart.defaults.animation = { duration: 300 };
  Chart.defaults.animations.colors = false;   // gradient fills can't be color-tweened (Chart.js throws "_fn is not a function")
}
const charts = {};
export function cj(id, cfg) {
  if (charts[id]) charts[id].destroy();
  const el = document.getElementById(id);
  if (!el) return null;
  charts[id] = new Chart(el, cfg);
  return charts[id];
}
export const baseOpts = (extra = {}) => ({
  responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
  plugins: { legend: { display: false } },
  scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } }, y: { grid: { color: css('--grid') }, border: { display: false } } },
  ...extra,
});
