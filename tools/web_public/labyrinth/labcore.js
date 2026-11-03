// LABYRINTH core (ES module, no DOM, no clock, no network): the risk maze of an MFFU eval, as plain functions.
// The maze is the corridor between two walls: the FLOOR (the trailing max-loss line; touch it and the eval is over) and the
// TARGET (reach it and the eval is passed). Your balance is a runner in the corridor; the size of every trade decides how
// fast it climbs and how close the floor wall gets.
//
//   parseTrades(doc)            -> [{ day, usd, risk, r, src }]   the LIT trades of ../odeon/trades.json, oldest first
//   rulesFrom(home)             -> { name, start, target, mll, lock, dll, balance?, floor?, session? }   the live eval of ../home.json, else the Builder 50K defaults
//   factor(t, mult, cap)        -> how much of the trade's size is kept: min(mult, cap / risk): the cap is a ceiling on $ risk per trade
//   walk(trades, mult, cap, rules) -> { steps, outcome: 'pass' | 'bust' | 'open', at }   one run, trade by trade
//   sim(pool, mult, cap, rules, o)  -> { pass, bust, open, n, medPass, medBust }   many runs: trades drawn from the pool at random (seeded)
//   sweep(pool, cap, rules, mults, o) -> [{ m, pass, bust, open, medPass }]
//   sweetSpot(rows, maxBust)    -> the size with the most passes while busting at most maxBust (else the best pass - bust)
//   ghosts(pool, mult, cap, rules, k, len, seed) -> k equity paths for the scene
//   march(trades, rules, since, len) -> the recent stretch of trades walked as one eval (the real order)
//   plain(row, rules)           -> the verdict in plain words
// MFFU Builder 50K as the page models it: start $50,000, target +$3,000, trailing max loss $2,000 that stops trailing once the
// floor reaches start + $100 (the live eval's own numbers win when ../home.json has them). Moves count per trade (an end-of-
// trade peak), so it is a what-if on the trades the site shows, never a forecast and never an order.

export const DEFAULT_RULES = Object.freeze({ name: 'MFFU Builder 50K', start: 50000, target: 3000, mll: 2000, lock: 100, dll: 1000 });
const isObj = (x) => !!x && typeof x === 'object' && !Array.isArray(x);
const num = (x) => (typeof x === 'number' && Number.isFinite(x) ? x : typeof x === 'string' && x.trim() && Number.isFinite(+x) ? +x : null);

export function parseTrades(doc) {
  const rows = isObj(doc) && Array.isArray(doc.trades) ? doc.trades : Array.isArray(doc) ? doc : [];
  const out = [];
  for (const t of rows) {
    if (!isObj(t)) continue;
    const usd = num(t.usd), day = typeof t.day === 'string' && /^\d{4}-\d{2}-\d{2}/.test(t.day) ? t.day.slice(0, 10) : '';
    if (usd == null || !day) continue;
    if (t.strat && t.strat !== 'LIT') continue;                       // the 50K runs LIT; ATLAS belongs to the 25K
    const r = num(t.r), risk = num(t.risk_usd != null ? t.risk_usd : t.risk);
    out.push({ day, usd, r: r == null ? 0 : r, risk: risk && risk > 0 ? risk : Math.max(1, Math.abs(usd)), src: String(t.src || 'trade') });
  }
  return out.map((t, i) => ({ t, i })).sort((a, b) => (a.t.day < b.t.day ? -1 : a.t.day > b.t.day ? 1 : a.i - b.i)).map((x) => x.t);
}

export function rulesFrom(home) {
  const accts = isObj(home) && Array.isArray(home.accounts) ? home.accounts : [];
  const a = accts.find((x) => isObj(x) && isObj(x.eval) && /50k/i.test(String(x.plan || x.id || '')) && x.kind !== 'paper') || null;
  if (!a) return { ...DEFAULT_RULES };
  const e = a.eval, start = num(e.start_balance), tb = num(e.target_balance), mll = num(e.mll);
  const o = { ...DEFAULT_RULES, name: String(a.plan || DEFAULT_RULES.name) };
  if (start) o.start = start;
  if (start && tb && tb > start) o.target = tb - start;
  if (mll && mll > 0) o.mll = mll;
  if (num(e.dll)) o.dll = num(e.dll);
  if (num(e.balance) != null) o.balance = num(e.balance);
  if (num(e.floor) != null) o.floor = num(e.floor);
  if (num(e.session) != null) o.session = num(e.session);
  if (typeof e.start === 'string') o.since = e.start;
  return o;
}

export const factor = (t, mult, cap) => Math.min(mult, cap > 0 ? cap / Math.max(1, t.risk) : Infinity);
export const floorAt = (peak, R) => Math.min(R.start + R.lock, peak - R.mll);

export function walk(trades, mult, cap, R) {
  const steps = [{ i: 0, day: '', usd: 0, bal: R.start, peak: R.start, floor: R.start - R.mll }];
  let bal = R.start, peak = R.start, outcome = 'open', at = -1;
  for (let k = 0; k < trades.length; k++) {
    const t = trades[k], usd = Math.round(t.usd * factor(t, mult, cap) * 100) / 100;
    bal += usd; peak = Math.max(peak, bal);
    const floor = floorAt(peak, R);
    steps.push({ i: k + 1, day: t.day, usd, bal, peak, floor, risk: Math.round(t.risk * factor(t, mult, cap)) });
    if (bal <= floor) { outcome = 'bust'; at = k + 1; break; }
    if (bal >= R.start + R.target) { outcome = 'pass'; at = k + 1; break; }
  }
  return { steps, outcome, at };
}

export function mulberry32(a) {
  return function () { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const median = (a) => { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

function draw(pool, len, rnd) { const o = []; for (let i = 0; i < len; i++) o.push(pool[Math.floor(rnd() * pool.length)]); return o; }

export function sim(pool, mult, cap, R, o = {}) {
  const n = o.n || 500, len = o.len || 15, rnd = mulberry32(o.seed || 7);
  let pass = 0, bust = 0, open = 0; const pt = [], bt = [];
  if (!pool.length) return { pass: 0, bust: 0, open: 1, n: 0, medPass: null, medBust: null };
  for (let s = 0; s < n; s++) {
    const w = walk(draw(pool, len, rnd), mult, cap, R);
    if (w.outcome === 'pass') { pass++; pt.push(w.at); } else if (w.outcome === 'bust') { bust++; bt.push(w.at); } else open++;
  }
  return { pass: pass / n, bust: bust / n, open: open / n, n, medPass: median(pt), medBust: median(bt) };
}

export function sweep(pool, cap, R, mults, o = {}) {
  return mults.map((m) => ({ m, ...sim(pool, m, cap, R, o) }));
}

export function sweetSpot(rows, maxBust = 0.3) {
  const ok = rows.filter((r) => r.bust <= maxBust);
  const pick = ok.length ? ok.reduce((a, b) => (b.pass > a.pass || (b.pass === a.pass && b.m < a.m) ? b : a)) : rows.reduce((a, b) => (b.pass - b.bust > a.pass - a.bust ? b : a));
  return { m: pick.m, pass: pick.pass, bust: pick.bust, safe: ok.length > 0 };
}

export function ghosts(pool, mult, cap, R, k = 24, len = 15, seed = 11) {
  const rnd = mulberry32(seed), out = [];
  if (!pool.length) return out;
  for (let g = 0; g < k; g++) { const w = walk(draw(pool, len, rnd), mult, cap, R); out.push({ bal: w.steps.map((s) => s.bal), outcome: w.outcome }); }
  return out;
}

/** the real order: the last `len` trades (or, with a start day, the trades since it) walked as one eval */
export function march(trades, R, len = 15) {
  const since = R.since && trades.filter((t) => t.day >= R.since).length >= 6 ? trades.filter((t) => t.day >= R.since) : trades.slice(-len);
  return since.slice(0, len);
}

const pct = (x) => `${Math.round(x * 100)}%`;
export function plain(row, R, horizon) {
  const days = horizon <= 8 ? 'about 2 weeks' : horizon <= 15 ? 'about 4 weeks' : 'about 8 weeks';
  const clock = `${horizon} trades (${days} at 2-4 a week)`;
  if (row.bust >= 0.5) return `Too big: in ${pct(row.bust)} of the runs the floor wall catches you within ${clock}.`;
  if (row.bust > 0.3) return `Risky: ${pct(row.bust)} of runs end at the floor and ${pct(row.pass)} reach the target within ${clock}.`;
  if (row.pass < 0.25) return `Safe but slow: only ${pct(row.pass)} reach the target within ${clock}, ${pct(row.bust)} hit the floor.`;
  return `A good size: ${pct(row.pass)} reach the target within ${clock}, ${pct(row.bust)} hit the floor.`;
}

export const usd = (x) => { const v = Math.round(+x || 0), s = '$' + Math.abs(v).toLocaleString('en-US'); return v < 0 ? '-' + s : s; };
