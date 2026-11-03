// ARES core (ES module, no DOM): the MFFU Builder rules as functions. Pure, so the test can call them in the page.
//   loadRules(url)            -> rules (rules.json; the embedded copy when it is missing) with .src 'file' | 'embedded'
//   planOf(rules, id)         -> the plan's numbers
//   floorOf(plan, peakEod)    -> the trailing floor: min(best end-of-day balance - max loss, start + lock), start - max loss at first
//   etClock(date)             -> { dow, mod, hm, label } in New York time
//   sessionState(date, rules) -> { state: 'open' | 'break' | 'closed' | 'late', note }
//   sizeTrade(rules, inp)     -> the contracts, the real cost of a stop-out, the room after, the stops you can survive
//   judge(rules, inp, now)    -> { level: 'go' | 'wait' | 'halt', reasons[], size, checks }  (the war-room verdict)
// Money: a stop-out costs (stop points + 2 ticks of slip) x point value + the round-turn commission, per contract.
// Nothing here talks to a broker or a bot. Paper rules, a calculator for the human.

export const EMBEDDED = {
  v: 1, kind: 'olympus-ares-rules', source: 'embedded copy of research/lit/mffu_rules.json (2026-10-18)',
  plans: {
    '50k': { name: 'Builder 50K', start: 50000, target: 3000, mll: 2000, lock: 100, dll: 1000, max_micros: 40, max_minis: 4, buffer: 2100,
      pay_min: 500, pay_max: 2000, split: 0.8, cons: 0.5, max_payouts: 5, price: 91.8, list_price: 153 },
    '25k': { name: 'Builder 25K', start: 25000, target: 1500, mll: 1000, lock: 100, dll: 600, max_micros: 20, max_minis: 2, buffer: 1100,
      pay_min: 250, pay_max: 1000, split: 0.8, cons: 0.5, max_payouts: 5, price: 63, list_price: 105 },
  },
  flat_by: '16:10', open: '18:00', break: ['17:00', '18:00'], comm_rt: { MNQ: 1.9, NQ: 4.68 }, slip_ticks: 2,
  point_value: { MNQ: 2, NQ: 20 }, tick: 0.25,
  bot: { entry_from: '02:00', entry_to: '15:30', stop_min_pts: 8, stop_max_pts: 80, max_trades_day: 1, room_f_eval: 0.8, room_f_funded: 0.6 },
  rules: [],
};

export const CHECKS = [
  { id: 'level', text: 'My stop sits 1 tick beyond a real level (the sweep extreme), not a random number of points.', must: true },
  { id: 'calm', text: 'I am calm. This is not revenge, not boredom, not catching up on a loss.', must: true },
  { id: 'plan', text: 'I wrote down my entry, stop and target before I clicked anything.', must: false },
  { id: 'target', text: 'One clear target. No greed: I take it or my stop takes me out.', must: false },
  { id: 'size', text: 'My size is the number above, not a feeling. A wide stop means fewer micros.', must: true },
  { id: 'news', text: 'I checked the news times. No surprise at 08:30 or 14:00 ET.', must: false },
  { id: 'flat', text: 'I can be flat before 16:10 ET without rushing.', must: false },
  { id: 'chase', text: 'I am entering at my level, not chasing a move that already ran.', must: false },
];

const isObj = (x) => !!x && typeof x === 'object' && !Array.isArray(x);
export const num = (x) => { const v = typeof x === 'string' ? parseFloat(x.replace(/[$,\s]/g, '')) : x; return Number.isFinite(v) ? v : null; };
export const usd = (v, d = 0) => (v == null || !Number.isFinite(v) ? '-' : (v < 0 ? '-$' : '$') + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }));
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hm = (s) => { const [h, m] = String(s).split(':').map(Number); return h * 60 + (m || 0); };

export async function loadRules(url = 'rules.json') {
  try {
    const r = await fetch(url, { cache: 'no-cache' });
    const j = r.ok ? await r.json() : null;
    if (isObj(j) && j.kind === 'olympus-ares-rules' && isObj(j.plans) && j.plans['50k'] && j.plans['25k']) return { ...j, src: 'file' };
  } catch (_) { /* the embedded copy */ }
  return { ...EMBEDDED, src: 'embedded' };
}

export const planOf = (rules, id) => rules.plans[id] || rules.plans['50k'];

export function floorOf(plan, peakEod) {
  const peak = Math.max(plan.start, num(peakEod) ?? plan.start);
  return Math.min(peak - plan.mll, plan.start + plan.lock);
}

const FMT = typeof Intl !== 'undefined' ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) : null;
const DOW = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
export function etClock(date) {
  const d = date instanceof Date ? date : new Date(date);
  let dow = d.getUTCDay(), h = d.getUTCHours(), m = d.getUTCMinutes();
  if (FMT) {
    const p = Object.fromEntries(FMT.formatToParts(d).map((x) => [x.type, x.value]));
    dow = DOW[p.weekday]; h = +p.hour % 24; m = +p.minute;
  }
  return { dow, mod: h * 60 + m, hm: String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') };
}

/** CME equity futures week in ET: open Sun 18:00, daily break 17:00-18:00, closed Fri 17:00 -> Sun 18:00. 'late' = 16:00-17:00:
 *  MFFU flattens at 16:10, so a new trade then is a rule break. */
export function sessionState(date, rules) {
  const c = etClock(date), flat = hm(rules.flat_by), b0 = hm(rules.break[0]), b1 = hm(rules.break[1]);
  if (c.dow === 6 || (c.dow === 5 && c.mod >= b0) || (c.dow === 0 && c.mod < b1)) return { state: 'closed', note: 'The market is closed for the weekend (it opens Sunday 18:00 ET).', clock: c };
  if (c.mod >= b0 && c.mod < b1) return { state: 'break', note: 'The daily break (17:00-18:00 ET). Nothing trades.', clock: c };
  if (c.mod >= flat - 10 && c.mod < b0) return { state: 'late', note: `Too late: MFFU flattens every account at ${rules.flat_by} ET.`, clock: c };
  return { state: 'open', note: '', clock: c };
}

export function sizeTrade(rules, inp) {
  const plan = planOf(rules, inp.plan), inst = inp.inst === 'NQ' ? 'NQ' : 'MNQ';
  const pv = rules.point_value[inst], comm = rules.comm_rt[inst], slip = (rules.slip_ticks || 2) * (rules.tick || 0.25);
  const bal = num(inp.balance) ?? plan.start, floor = floorOf(plan, inp.peak);
  const today = num(inp.today) ?? 0;
  const room = bal - floor, dllLeft = plan.dll > 0 ? plan.dll - Math.max(0, -today) : Infinity;
  const entry = num(inp.entry), stop = num(inp.stop);
  const out = { plan, inst, pv, comm, slip, bal, floor, room, dllLeft, today, target_bal: plan.start + plan.target, valid: false, n: 0, why: '' };
  if (entry == null || stop == null || entry <= 0 || stop <= 0) { out.why = 'Enter your entry and your stop.'; return out; }
  const side = inp.side === 'short' ? 'short' : 'long';
  const pts = side === 'long' ? entry - stop : stop - entry;
  out.side = side;
  if (!(pts > 0)) { out.why = side === 'long' ? 'A long needs the stop BELOW the entry.' : 'A short needs the stop ABOVE the entry.'; return out; }
  out.valid = true; out.pts = pts;
  out.loss1 = (pts + slip) * pv + comm;                                   // one contract, stopped out, everything counted
  const frac = Math.min(1, Math.max(0.05, (num(inp.riskPct) ?? 40) / 100));
  const cap = num(inp.riskCap);
  out.budget = Math.max(0, Math.min(room * frac, dllLeft, cap != null && cap > 0 ? cap : Infinity));
  out.maxC = inst === 'NQ' ? Math.floor(plan.max_micros / 10) : plan.max_micros;
  out.by_budget = Math.floor(out.budget / out.loss1);
  out.n = Math.max(0, Math.min(out.by_budget, out.maxC));
  out.capped = out.by_budget > out.maxC;
  out.risk = out.n * out.loss1;
  out.nominal = out.n * pts * pv;                                          // the plain stop distance in dollars
  out.after = bal - out.risk;
  out.room_after = out.after - floor;
  out.stops_left = out.n > 0 ? Math.floor(room / out.risk) : 0;           // full stop-outs of this size until the floor
  out.rooms_pct = room > 0 ? out.risk / room : 1;
  out.R = [1, 2, 3].map((r) => ({ r, pts: pts * r, usd: out.n * pts * r * pv - out.n * comm }));
  out.to_target = Math.max(0, out.target_bal - bal);
  out.micros_hint = inst === 'NQ' && out.n === 0 ? Math.min(plan.max_micros, Math.floor(out.budget / ((pts + slip) * rules.point_value.MNQ + rules.comm_rt.MNQ))) : null;
  return out;
}

/** The verdict. 'halt' = the rules (or your own two-stops rule) say do not trade; 'wait' = allowed, but the list is not done;
 *  'go' = every box ticked and nothing in the way. Warnings never block, they are listed. */
export function judge(rules, inp, now = new Date()) {
  const r = sizeTrade(rules, inp), plan = r.plan, bot = rules.bot || {}, S = sessionState(now, rules);
  const reasons = [], halt = (id, text) => reasons.push({ id, level: 'halt', text }), warn = (id, text) => reasons.push({ id, level: 'warn', text });
  if (S.state !== 'open') halt('clock', S.note);
  else if (S.clock.mod >= hm(bot.entry_to || '15:30')) warn('late', `After ${bot.entry_to || '15:30'} ET the bot takes no new entries. Be flat by ${rules.flat_by}.`);
  if (r.room <= 0) halt('dead', 'The balance is at or under the floor. The account is over. Start a new evaluation.');
  else if (inp.stage === 'eval' && r.bal >= r.target_bal) halt('passed', `Target reached (${usd(r.target_bal)}). Stop trading this eval and ask MFFU for the funded account.`);
  if (plan.dll > 0 && r.today <= -plan.dll) halt('dll', `Daily loss limit hit (${usd(-r.today)} of ${usd(plan.dll)}). MFFU pauses the account for the day; so do you.`);
  const maxT = num(inp.maxTrades) ?? 2, tt = num(inp.tradesToday) ?? 0, ll = num(inp.lossesToday) ?? 0, stopAfter = num(inp.stopAfter) ?? 2;
  if (tt >= maxT) halt('count', `You set ${maxT} trade${maxT === 1 ? '' : 's'} a day and you have taken ${tt}. Done for today.`);
  if (ll >= stopAfter) halt('losses', `${ll} stop-outs today. Your own rule: close the screen. Tomorrow has the same edge.`);
  if (inp.hedge) halt('hedge', 'You hold the opposite side in another account. MFFU forbids long and short at once, also across accounts.');
  if (!r.valid) halt('input', r.why);
  else {
    if (r.n === 0 && r.room > 0 && !reasons.some((x) => x.id === 'dll' || x.id === 'passed')) {
      const need = r.loss1, have = r.budget;
      halt('wide', `The stop is too wide for the room: one ${r.inst} stop-out costs ${usd(need)}, your risk budget is ${usd(have)}.${r.micros_hint ? ` ${r.micros_hint} MNQ would fit.` : ' Skip it or wait for a closer level.'}`);
    }
    if (r.pts < (bot.stop_min_pts || 8)) warn('tight', `A ${r.pts.toFixed(2)}-point stop is tighter than the bot's 8-point minimum: noise can take it.`);
    if (r.pts > (bot.stop_max_pts || 80)) warn('far', `A ${r.pts.toFixed(1)}-point stop is wider than the bot's 80-point maximum.`);
    if (r.n > 0 && r.rooms_pct > 0.6) warn('big', `This stop-out eats ${Math.round(r.rooms_pct * 100)}% of the room you have left. The bot uses at most ${Math.round((inp.stage === 'funded' ? bot.room_f_funded : bot.room_f_eval) * 100) || 60}%.`);
    if (r.n > 0 && r.stops_left <= 2) warn('thin', `Only ${r.stops_left} full stop-out${r.stops_left === 1 ? '' : 's'} until the floor. Trade smaller.`);
    if (r.capped) warn('cap', `The budget allows more, but the account limit is ${r.maxC} ${r.inst === 'NQ' ? 'minis' : 'micros'}.`);
  }
  if (inp.news) warn('news', 'High-impact news is near. Spreads jump and stops slip. Half size or wait.');
  if (ll === 1) warn('loss1', 'One stop-out already today. The next trade must be your best level, not a make-up trade.');
  const done = CHECKS.filter((c) => inp.checks && inp.checks[c.id]).length;
  const mustMiss = CHECKS.filter((c) => c.must && !(inp.checks && inp.checks[c.id])).length;
  const level = reasons.some((x) => x.level === 'halt') ? 'halt' : done < CHECKS.length ? 'wait' : 'go';
  return { level, reasons, size: r, session: S, checks: { done, total: CHECKS.length, mustMiss } };
}

/** Prefill from the site's data.json: the first account with a numeric eval balance + floor. */
export function accountFromSite(site) {
  const list = Array.isArray(site && site.accounts) ? site.accounts : [];
  for (const a of list) {
    const e = a && a.eval;
    if (isObj(e) && Number.isFinite(+e.balance) && Number.isFinite(+e.floor)) {
      return { name: String(a.name || a.id || 'Eval').slice(0, 40), balance: +e.balance, floor: +e.floor, today: Number.isFinite(+e.today) ? +e.today : 0,
        start: Number.isFinite(+e.start_balance) ? +e.start_balance : null, mll: Number.isFinite(+e.mll) ? +e.mll : null };
    }
  }
  return null;
}

/** The bot's real stops (extras.trades rows: tcols names the columns): median / p25 / p75 of risk_pts. */
export function botStops(site) {
  const ex = site && site.extras;
  if (!isObj(ex) || !Array.isArray(ex.trades) || !Array.isArray(ex.tcols)) return null;
  const i = ex.tcols.indexOf('risk_pts'), q = ex.tcols.indexOf('qty');
  if (i < 0) return null;
  const v = ex.trades.map((t) => +t[i]).filter((x) => Number.isFinite(x) && x > 0).sort((a, b) => a - b);
  if (v.length < 5) return null;
  const at = (p) => v[Math.min(v.length - 1, Math.floor(p * (v.length - 1)))];
  const qs = q >= 0 ? ex.trades.map((t) => +t[q]).filter((x) => Number.isFinite(x) && x > 0).sort((a, b) => a - b) : [];
  return { n: v.length, p25: at(0.25), med: at(0.5), p75: at(0.75), max: v[v.length - 1], qty_med: qs.length ? qs[Math.floor(qs.length / 2)] : null };
}
