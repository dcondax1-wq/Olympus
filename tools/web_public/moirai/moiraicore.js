// MOIRAI core (ES module, no DOM, no network): the three fates, a seeded Monte-Carlo of the MFFU Builder 50K eval. Pure, so tests/test_moirai_page.py runs it in node.
// SIMULATION, NOT A FORECAST. Each session (one trading day) has a chance of one trade (trades a week / 5, the bot takes at most one a day). A trade is a win (average win R),
// a break-even (0R) or a loss (average loss R). 1R = risk % of the $50,000 account, never more than the daily loss limit. The path passes when equity reaches start + target
// and busts when it touches the trailing floor (highest end-of-day balance minus the max loss, locking at start + $100). Costs are already inside the R's; the consistency rule
// and intraday swings are not modelled, so reality can be slower or worse. Same seed, same numbers: every path has its own seed, so chunking never changes a result.

export const RULES = { plan: 'Builder 50K', start: 50000, target: 3000, mll: 2000, lock: 100, dll: 1000, price: 91.8, horizon: 30 };
export const DEFAULTS = { win: 0.267, scratch: 0.292, avg_win_r: 4.49, avg_loss_r: 0.88, tpw: 3.08, risk_pct: 0.6, seed: 2026, paths: 1000 };
export const NOTE = 'A simulation, not a forecast: it replays a coin-flip with the odds you set. Real trading has slippage, streaks and rules this does not model.';

export const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
export const num = (v) => { const x = typeof v === 'string' ? parseFloat(v.replace(/[$,%\s]/g, '')) : v; return typeof x === 'number' && Number.isFinite(x) ? x : null; };
const r2 = (x) => Math.floor(x * 100 + 0.5) / 100;
export const money = (v) => { const x = r2(v), s = Math.abs(x).toLocaleString('en-US', x === Math.trunc(x) ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 2, maximumFractionDigits: 2 }); return (x < 0 ? '-$' : '$') + s; };
export const moneyS = (v) => (r2(v) > 0 ? '+' : '') + money(v);
export const pct = (x, d) => (x * 100).toFixed(d == null ? 0 : d) + '%';
export const rS = (r) => { const x = Math.round(r * 10) / 10; return (x > 0 ? '+' : '') + x.toFixed(1) + 'R'; };
/** every R next to its dollars: "+4.5R (+$1,347)" */
export const both = (r, oneR) => `${rS(r)} (${moneyS(r * oneR)})`;

export function rules(r) {
  const o = { ...RULES };
  if (r && typeof r === 'object') for (const k of ['start', 'target', 'mll', 'lock', 'dll', 'price', 'horizon']) { const v = num(r[k]); if (v != null && v > 0) o[k] = v; }
  o.horizon = Math.trunc(clamp(Math.floor(o.horizon), 5, 60));
  return o;
}
/** clamp every input; win + break-even never exceed 100% */
export function clean(inp, rl) {
  const R = rules(rl), d = { ...DEFAULTS };
  if (inp && typeof inp === 'object') for (const k of Object.keys(d)) { const v = num(inp[k]); if (v != null) d[k] = v; }
  d.win = clamp(d.win, 0, 0.95); d.scratch = clamp(d.scratch, 0, 0.95 - d.win);
  d.avg_win_r = clamp(d.avg_win_r, 0.1, 20); d.avg_loss_r = clamp(d.avg_loss_r, 0.1, 3); d.tpw = clamp(d.tpw, 0.1, 5);
  d.risk_pct = clamp(d.risk_pct, 0.05, 5); d.seed = Math.trunc(clamp(Math.floor(d.seed), 0, 2147483647)); d.paths = Math.trunc(clamp(Math.floor(d.paths), 10, 5000));
  d.loss = r2(1 - d.win - d.scratch) < 0 ? 0 : 1 - d.win - d.scratch;
  d.oneR = Math.max(1, Math.min(R.dll, r2(d.risk_pct / 100 * R.start)));        // 1R in dollars, never more than the daily loss limit
  d.perDay = Math.min(1, d.tpw / 5);
  d.rules = R;
  d.expR = d.win * d.avg_win_r - d.loss * d.avg_loss_r;
  return d;
}

// ------------------------------------------------------------------ the random numbers
export function mulberry32(a) {
  return function () { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
export const pathSeed = (seed, i) => (Math.imul(seed ^ 0x9E3779B9, 0x85EBCA6B) + Math.imul(i + 1, 0xC2B2AE35)) | 0;

/** one path: equity after every session until it passes or busts (then frozen). end = 'pass' | 'bust' | 'open'; day = the session it was decided on */
export function simPath(p, i) {
  const R = p.rules, rnd = mulberry32(pathSeed(p.seed, i)), H = R.horizon, top = R.start + R.target;
  let eq = R.start, hwm = R.start, end = 'open', day = null, trades = 0;
  const path = [eq];
  for (let d = 1; d <= H; d++) {
    if (end === 'open') {
      if (rnd() < p.perDay) {
        trades++;
        const u = rnd(), r = u < p.win ? p.avg_win_r : u < p.win + p.scratch ? 0 : -p.avg_loss_r;
        eq += r * p.oneR;
        hwm = Math.max(hwm, eq);
        const floor = Math.min(R.start + R.lock, hwm - R.mll);
        if (eq >= top) { end = 'pass'; day = d; eq = Math.min(eq, top + p.oneR * p.avg_win_r); } else if (eq <= floor) { end = 'bust'; day = d; eq = floor; }
      }
    }
    path.push(r2(eq));
  }
  return { eq: path, end, day, trades };
}
export function simChunk(p, from, to) { const out = []; for (let i = from; i < to; i++) out.push(simPath(p, i)); return out; }

const quant = (sorted, q) => { const k = (sorted.length - 1) * q, lo = Math.floor(k), hi = Math.ceil(k); return sorted[lo] + (sorted[hi] - sorted[lo]) * (k - lo); };
/** every number the page shows, from the path results */
export function summarize(results, p) {
  const n = results.length, H = p.rules.horizon, share = (f) => (n ? results.filter(f).length / n : 0);
  const passDay = results.filter((r) => r.end === 'pass').map((r) => r.day).sort((a, b) => a - b);
  const S = { n, horizon: H };
  for (const k of [10, 15]) { S['p' + k] = share((r) => r.end === 'pass' && r.day <= k); S['f' + k] = share((r) => r.end === 'bust' && r.day <= k); S['dec' + k] = S['p' + k] + S['f' + k]; }
  S.pass = share((r) => r.end === 'pass'); S.bust = share((r) => r.end === 'bust'); S.open = share((r) => r.end === 'open');
  S.slow_pass = passDay.length ? passDay.filter((d) => d > 15).length / passDay.length : 0;       // share of the passes that took longer than 15 sessions
  S.pass_med = passDay.length ? quant(passDay, 0.5) : null;
  S.trades_med = n ? quant(results.map((r) => r.trades).sort((a, b) => a - b), 0.5) : 0;
  S.bands = [];
  for (let d = 0; d <= H; d++) {
    const col = results.map((r) => r.eq[d]).sort((a, b) => a - b);
    S.bands.push(n ? [0.1, 0.25, 0.5, 0.75, 0.9].map((q) => r2(quant(col, q))) : [p.rules.start, p.rules.start, p.rules.start, p.rules.start, p.rules.start]);
  }
  S.sample = results.slice(0, 24).map((r) => r.eq);
  S.expected = { r: p.expR, usd: p.expR * p.oneR, week: p.expR * p.oneR * p.tpw, month: p.expR * p.oneR * p.tpw * 52 / 12 };
  S.fees = S.pass > 0 ? p.rules.price / S.pass : null;      // expected eval fees to land one pass if every failed try is bought again (estimate)
  return S;
}
export function runAll(p) { return summarize(simChunk(p, 0, p.paths), p); }
/** the same run in small chunks so a phone never freezes: defer(fn) schedules the next chunk, onProgress(0..1), cancel() stops it. Resolves with the same summary as runAll. */
export function runChunked(p, { chunk = 100, defer = (f) => setTimeout(f, 0), onProgress = null } = {}) {
  let stop = false;
  const out = [];
  const promise = new Promise((resolve) => {
    const step = () => {
      if (stop) { resolve(null); return; }
      const from = out.length, to = Math.min(p.paths, from + chunk);
      for (const r of simChunk(p, from, to)) out.push(r);
      if (onProgress) onProgress(out.length / p.paths);
      if (out.length >= p.paths) resolve(summarize(out, p)); else defer(step);
    };
    defer(step);
  });
  return { promise, cancel() { stop = true; } };
}
export const fates = (S) => [{ id: 'pass', label: 'Pass', share: S.pass }, { id: 'bust', label: 'Bust', share: S.bust }, { id: 'open', label: 'Still open', share: S.open }];

export function jarvisCard(S, p, nowSec) {
  return { v: 1, name: 'Moirai', status: { level: 'off', label: 'Simulation' }, kpis: [{ label: 'Pass in 15', value: pct(S.p15) }, { label: 'Bust in 15', value: pct(S.f15) }, { label: 'Median', value: S.pass_med == null ? '-' : Math.round(S.pass_med) + ' sessions' }],
    lines: ['A simulation, not a forecast.', `1R = ${money(p.oneR)}; ${rS(p.expR)} (${moneyS(p.expR * p.oneR)}) a trade on these odds.`], t: nowSec | 0, open: '#', theme: '#14110e', stale_after: 604800 };
}
