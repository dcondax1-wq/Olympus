// FATES core (no DOM, no WebGL): the data model of the page. fates.js draws it; tests import it in the browser.
//   data   = fates.json (tools/fates/build.py, schema in tools/fates/export.py), or fixture.json for the demo
//   route  = { scen: 'zlarior' | 'atlas' | 'money', period: '2026' | '2021-25', accts: 1..6, span: '6m' | '12m' }

export const BOTS = { zlarior: 'Zlarior', atlas: 'ATLAS' };
export const PERIODS = ['2026', '2021-25'];
export const OUTCOME = {
  p: { key: 'pass', label: 'PASSED', color: 'gold' },
  f: { key: 'fail', label: 'FAILED at the floor', color: 'red' },
  s: { key: 'stuck', label: 'STUCK: too little room, the bot stops', color: 'red' },
  c: { key: 'closed', label: 'CLOSED: 7 days without a trade', color: 'red' },
  o: { key: 'open', label: 'Still open', color: 'violet' },
};
export const EV = { BUY: 0, PASS: 1, DEAD: 2, LOST: 3, PAY: 4, GRAD: 5 };
export const EV_TEXT = ['bought a new eval', 'eval PASSED', 'eval lost', 'funded account lost', 'payout', '5th payout: account done'];

// ------------------------------------------------------------------------------------------------ routes
export function parseRoute(hash) {
  const h = String(hash || '').replace(/^#/, '').toLowerCase();
  const [a = '', b = ''] = h.split('/');
  const m = /^money(?:-(\d))?$/.exec(a);
  const r = { scen: 'zlarior', period: '2026', accts: 2, span: '12m' };
  if (a === 'zlarior' || a === 'atlas') r.scen = a;
  else if (m) { r.scen = 'money'; if (m[1]) r.accts = Math.min(6, Math.max(1, +m[1])); }
  if (PERIODS.includes(b)) r.period = b;
  return r;
}
export function routeHash(r) {
  return '#' + (r.scen === 'money' ? `money-${r.accts}` : r.scen) + '/' + r.period;
}
export function scenKey(r) {
  return r.scen === 'money' ? `money:${r.period}` : `eval:${r.scen}:${r.period}`;
}

// ------------------------------------------------------------------------------------------------ formats
export const fmtPct = (x) => (x == null || !Number.isFinite(+x) ? '—' : `${Math.round(+x)}%`);
export function fmtUsd(x, sign = false) {
  if (x == null || !Number.isFinite(+x)) return '—';
  const v = Math.round(+x), s = v < 0 ? '−' : sign && v > 0 ? '+' : '';
  return `${s}$${Math.abs(v).toLocaleString('en-US')}`;
}
export function fmtK(x) {
  if (x == null || !Number.isFinite(+x)) return '—';
  const v = +x, a = Math.abs(v), s = v < 0 ? '−' : '';
  return a >= 10000 ? `${s}$${(a / 1000).toFixed(0)}K` : a >= 1000 ? `${s}$${(a / 1000).toFixed(1)}K` : `${s}$${Math.round(a)}`;
}
export const fmtDays = (x) => (x == null || !Number.isFinite(+x) ? '—' : `${Math.round(+x)} ${Math.round(+x) === 1 ? 'day' : 'days'}`);
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
export function fmtDate(iso) {
  const d = new Date(String(iso) + 'T12:00:00Z');
  return Number.isNaN(+d) ? String(iso) : `${WD[d.getUTCDay()]} ${MON[d.getUTCMonth()]} ${d.getUTCDate()}`;
}

// ------------------------------------------------------------------------------------------------ the HUD
// Every number on the HUD comes straight from the scenario's summary (the build computes them; the page only formats).
export function hud(data, r) {
  const s = data && data.scenarios && data.scenarios[scenKey(r)];
  if (!s) return null;
  const per = (data.periods && data.periods[r.period]) || {};
  const weak = r.period === '2021-25';
  if (s.kind === 'eval') {
    const m = s.summary, mm = (m.money && m.money[r.span]) || {}, st = s.start || {};
    return {
      mode: 'eval', title: `${s.name} · ${s.rules.name}`,
      tiles: [
        { id: 'pass', label: 'Pass', value: fmtPct(m.pass), sub: `${fmtPct(m.p10)} in 10 days`, tone: 'gold' },
        { id: 'fail', label: 'Fail', value: fmtPct(m.fail), sub: `${fmtPct(m.f10)} in 10 days`, tone: 'red' },
        { id: 'days', label: 'Days to pass', value: m.pass_med == null ? '—' : String(Math.round(m.pass_med)), sub: 'median, trading' },
        { id: 'money', label: `$ a month · ${r.span === '6m' ? '6' : '12'} mo`, value: `${fmtUsd(mm.pm_p50)}`,
          sub: `p10 ${fmtUsd(mm.pm_p10)} · p90 ${fmtUsd(mm.pm_p90)}`, p10: mm.pm_p10, p50: mm.pm_p50, p90: mm.pm_p90 },
        { id: 'pay30', label: 'Payout ≤ 30 days', value: fmtPct(m.money && m.money.pay30), sub: 'calendar days' },
      ],
      caption: `From today: session ${st.session + 1} · ${fmtUsd(st.to_target)} to go · room ${fmtUsd(st.room)} · ` +
        `${Number(data.paths).toLocaleString('en-US')} futures`,
      note: m.no_keepalive && m.no_keepalive.closed > 0 ?
        `Assumes your 1-MNQ keep-alive on quiet day 6; without it ${fmtPct(m.no_keepalive.closed)} close (7 quiet days).` : '',
      period: per.label || r.period, weak,
    };
  }
  const b = s.books && s.books[String(r.accts)];
  if (!b) return null;
  const mm = b[r.span] || {};
  return {
    mode: 'money', title: `${r.accts} account${r.accts > 1 ? 's' : ''} · eval → funded → payouts`,
    tiles: [
      { id: 'pass', label: 'Ahead · 12 mo', value: fmtPct(b.ahead), sub: `${fmtPct(b.goal_pct)} reach ${fmtK(b.goal)}`, tone: 'gold' },
      { id: 'fail', label: 'Behind · 12 mo', value: fmtPct(b.behind), sub: 'fees > payouts', tone: 'red' },
      { id: 'days', label: 'To 1st payout', value: b.first_pay_med == null ? '—' : String(Math.round(b.first_pay_med)), sub: 'median, trading' },
      { id: 'money', label: `$ a month · ${r.span === '6m' ? '6' : '12'} mo`, value: `${fmtUsd(mm.pm_p50)}`,
        sub: `p10 ${fmtUsd(mm.pm_p10)} · p90 ${fmtUsd(mm.pm_p90)}`, p10: mm.pm_p10, p50: mm.pm_p50, p90: mm.pm_p90 },
      { id: 'pay30', label: 'Payout ≤ 30 days', value: fmtPct(b.pay30), sub: 'any account' },
    ],
    caption: (s.slots || []).slice(0, r.accts).map((x) => x.label).join(' + '),
    note: 'Net of every eval bought; 80% of each payout to you; today\'s two evals already paid.',
    period: per.label || r.period, weak,
  };
}

// ------------------------------------------------------------------------------------------------ eval threads
// The trailing floor after each session, replayed from the balances (tools/fates/export.floors, same rule).
export function floorsOf(hist, start, rules) {
  let peak = +start.peak, floor = start.floor == null ? -rules.mll : +start.floor;
  return hist.map((b) => {
    if (b > floor + 1e-9) { peak = Math.max(peak, b); floor = Math.min(Math.max(floor, peak - rules.mll), rules.lock); }
    return floor;
  });
}
// progress: 0 = the floor (abyss), 1 = the target (golden gate)
export function evalThreads(s) {
  const t = s.threads || { o: '', b: [] }, st = s.start, R = s.rules;
  const f0 = st.floor == null ? -R.mll : +st.floor;
  const p0 = (st.profit - f0) / (R.target - f0);
  return t.b.map((hist, i) => {
    const fl = floorsOf(hist, st, R);
    const prog = [p0].concat(hist.map((b, k) => Math.max(0, (b - fl[k]) / Math.max(1e-9, R.target - fl[k]))));
    const o = t.o[i] || 'o';
    return { id: i, o, color: OUTCOME[o].color, hist, floors: fl, pts: prog.map((y, k) => [k, y]), end: hist.length };
  });
}

// ------------------------------------------------------------------------------------------------ money threads
// One thread = the book's $ to the owner (net of evals), a step at each money event of its first `accts` slots.
export function moneyEvents(flat, accts) {
  const ev = [];
  for (let i = 0; i + 3 < flat.length; i += 4) if (flat[i + 1] < accts) ev.push({ k: flat[i], slot: flat[i + 1], code: flat[i + 2], usd: flat[i + 3] });
  ev.sort((a, b) => a.k - b.k || a.slot - b.slot);
  return ev;
}
export function moneyThreads(s, accts) {
  const H = s.horizon, goal = s.goal;
  return s.threads.ev.map((flat, i) => {
    const ev = moneyEvents(flat, accts);
    const pts = [[0, 0]];
    let v = 0;
    for (const e of ev) {
      if (!e.usd) continue;
      const k = e.k + 1;                                 // the cash moves at the close of session e.k
      if (pts[pts.length - 1][0] < k - 0.6) pts.push([k - 0.6, v]);
      v += e.usd;
      pts.push([k, v]);
    }
    if (pts[pts.length - 1][0] < H) pts.push([H, v]);
    const peak = Math.max(...pts.map((p) => p[1]));
    const color = peak >= goal ? 'gold' : v < 0 ? 'red' : 'violet';
    return { id: i, o: color === 'gold' ? 'p' : color === 'red' ? 'f' : 'o', color, pts, end: H, net: v, ev };
  });
}

// ------------------------------------------------------------------------------------------------ follow one future
export function followEval(data, s, th) {
  const cal = data.calendar || [], R = s.rules, rows = [];
  let prev = s.start.profit;
  th.hist.forEach((b, k) => {
    const d = b - prev; prev = b;
    rows.push({ k, day: cal[k] || `session ${k + 1}`, text: fmtDate(cal[k]),
      move: Math.abs(d) < 0.5 ? 'no trade' : fmtUsd(d, true), tone: d > 0.5 ? 'up' : d < -0.5 ? 'dn' : '',
      bal: fmtUsd(b, true), room: fmtUsd(b - th.floors[k]) });
  });
  const o = OUTCOME[th.o];
  const n = th.hist.length;
  const end = th.o === 'p' ? `PASSED on day ${n} (${fmtDate(cal[n - 1])}): ${fmtUsd(R.target)} reached` :
    th.o === 'o' ? `Still open after ${n} trading days` : `${o.label} on day ${n} (${fmtDate(cal[n - 1])})`;
  return { title: `Future #${th.id + 1}`, end, tone: o.color, rows };
}
export function followMoney(data, s, th) {
  const cal = data.calendar || [], slots = s.slots || [];
  let v = 0;
  const rows = th.ev.map((e) => {
    v += e.usd;
    const what = e.code === EV.PAY ? `payout ${fmtUsd(e.usd, true)} to you` : EV_TEXT[e.code] + (e.usd ? ` (${fmtUsd(e.usd, true)})` : '');
    return { k: e.k, day: cal[e.k], text: fmtDate(cal[e.k]), move: `${(slots[e.slot] || {}).label || 'slot ' + (e.slot + 1)}: ${what}`,
      tone: e.code === EV.PAY ? 'up' : e.code === EV.PASS ? 'gold' : e.usd < 0 || e.code === EV.DEAD || e.code === EV.LOST ? 'dn' : '',
      bal: fmtUsd(v, true), room: '' };
  });
  const end = `${fmtUsd(th.net, true)} after 12 months` + (th.color === 'gold' ? ` · reached ${fmtK(s.goal)}` : th.color === 'red' ? ' · behind' : '');
  return { title: `Future #${th.id + 1}`, end, tone: th.color, rows };
}

// ------------------------------------------------------------------------------------------------ Jarvis
// docs/JARVIS_APPS.md: the card the page posts to Jarvis while it is open (jarvis.json carries the same at build time).
export function jarvisCard(data, nowS = Math.floor(Date.now() / 1000)) {
  const S = (data && data.scenarios) || {};
  const z = S['eval:zlarior:2026'], a = S['eval:atlas:2026'];
  if (!z || !a) return null;
  const zp = z.summary.pass, lvl = zp >= 50 ? 'ok' : zp >= 30 ? 'warn' : 'bad';
  const zr = S['eval:zlarior:2021-25'];
  return {
    v: 1, name: 'FATES', status: { level: lvl, label: `Zlarior pass odds ${Math.round(zp)}%` },
    kpis: [{ label: 'Zlarior pass', value: fmtPct(zp) }, { label: 'ATLAS pass', value: fmtPct(a.summary.pass) }],
    lines: [`Pass odds this eval: ${Math.round(zp)}% (Zlarior, 2026 sample${zr ? `; 2021-25: ${Math.round(zr.summary.pass)}%` : ''})`.slice(0, 120)],
    t: nowS, open: '#zlarior/2026', theme: '#07050f',
  };
}
