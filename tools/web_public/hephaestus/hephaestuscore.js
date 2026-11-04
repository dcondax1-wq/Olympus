// HEPHAESTUS core (pure: no DOM, no network, no clock, no storage). The page hands it data.json (built by tools/hephaestus_build.py from the
// STORED backtest runs) and the dial settings; it answers which stored setting that is, which dial values exist ("not tested" for the rest),
// the plain verdict against the live setting, and the rows of the numbers table. It never computes a strategy result.

export const HALVES = ['h1', 'h2'];
export const HALF_NAME = { h1: 'Jan-Jun', h2: 'Jul-Oct' };

export function dialIds(data) { return ((data && data.dials) || []).map((d) => d.id); }

/** the selectable stored setting whose dials equal `dials` (all of them), or null */
export function find(data, dials) {
  if (!data || !Array.isArray(data.scenarios)) return null;
  const ids = dialIds(data);
  return data.scenarios.find((s) => s.selectable && ids.every((k) => s.dials && s.dials[k] === dials[k])) || null;
}
export const byId = (data, id) => ((data && data.scenarios) || []).find((s) => s.id === id) || null;

/** is the option v of dial `id` reachable with the OTHER dials as they are now (a stored run exists)? */
export function tested(data, dials, id, v) { return !!find(data, { ...dials, [id]: v }); }

/** the dial values present in at least one stored setting at all (for the "never tested" wording) */
export function anyTested(data, id, v) { return ((data && data.scenarios) || []).some((s) => s.selectable && s.dials && s.dials[id] === v); }

const num = (x) => (typeof x === 'number' && isFinite(x) ? x : null);
export function usd(v, sign = false) {
  const n = num(v); if (n == null) return '-';
  const a = Math.abs(Math.round(n)).toLocaleString('en-US');
  return (n < 0 ? '-$' : sign && n > 0 ? '+$' : '$') + a;
}
export const dec = (v, d = 2) => (num(v) == null ? '-' : v.toFixed(d));
export const pct = (v) => (num(v) == null ? '-' : v.toFixed(1) + '%');

/** the table rows: key in the stored half object, label, formatter, which way is better (+1 higher, -1 lower, 0 neutral) */
export const ROWS = [
  { k: 'net', label: 'Net $', f: (v) => usd(v), good: 1 },
  { k: 'per_month', label: '$ / month', f: (v) => usd(v), good: 1 },
  { k: 'pf', label: 'Profit factor', f: (v) => dec(v), good: 1 },
  { k: 'dd', label: 'Max drawdown', f: (v) => usd(v), good: 1 },
  { k: 'p10', label: 'Eval pass in 2 wks', f: pct, good: 1 },
  { k: 'f10', label: 'Eval fail in 2 wks', f: pct, good: -1 },
  { k: 'tpw', label: 'Trades / week', f: (v) => dec(v), good: 0 },
];

function win(a, b) { return num(a.net) != null && num(b.net) != null && a.net > b.net && (a.pf || 0) > (b.pf || 0); }

/** the plain verdict of setting `sc` against what it is judged on. kind: live | beats | tradeoff | mixed | still */
export function verdict(data, sc) {
  if (!sc) return { kind: 'none', head: 'NOT TESTED', plain: 'No stored run has this exact mix of dials, so there is no number to show.', flags: [], ref: null, halves: {} };
  if (sc.id === data.live_id) return { kind: 'live', head: 'THIS IS THE LIVE SETTING', plain: 'This is what the bot runs. Turn a dial to see what the stored tests say about a change.', flags: [], ref: sc, halves: {} };
  const ref = byId(data, sc.ref) || byId(data, data.live_id);
  const halves = {}, flags = [];
  for (const h of HALVES) {
    const a = sc[h] || {}, b = ref[h] || {};
    halves[h] = { win: win(a, b), netUp: num(a.net) != null && a.net > b.net, dNet: num(a.net) != null && num(b.net) != null ? a.net - b.net : null, dPf: num(a.pf) != null && num(b.pf) != null ? a.pf - b.pf : null };
  }
  const wins = HALVES.filter((h) => halves[h].win).length, netUp = HALVES.every((h) => halves[h].netUp);
  const tpwOk = HALVES.every((h) => (sc[h].tpw || 0) >= 2);
  if (!tpwOk) flags.push('Fewer than 2 trades a week in a half.');
  if (HALVES.some((h) => (sc[h].f10 || 0) > (ref[h].f10 || 0) + 2)) flags.push('More evals fail inside 2 weeks.');
  if (sc.base_confirm && ref.id !== data.live_id) flags.push(`Judged against its own twin run (confirm window ${sc.base_confirm}), not today's.`);
  let kind, head, plain;
  if (wins === 2 && tpwOk) { kind = 'beats'; head = 'THIS BEATS LIVE ON BOTH HALVES'; plain = 'More money and a better profit factor than live in Jan-Jun and in Jul-Oct. A lead to study, not a change: nothing here touches the bot.'; }
  else if (wins === 2) { kind = 'mixed'; head = 'BEATS LIVE, BUT BREAKS THE RULES'; plain = 'Better numbers in both halves, but it does not keep 2 or more trades a week.'; }
  else if (wins === 0 && netUp) { kind = 'tradeoff'; head = 'MORE MONEY, WEAKER EDGE'; plain = 'It makes more dollars than live in both halves but with a lower profit factor. Live keeps the better edge.'; }
  else if (wins === 0) { kind = 'still'; head = 'LIVE SETTING IS STILL BEST'; plain = 'Not better than live in either half. Live stays.'; }
  else { kind = 'mixed'; head = 'MIXED: WINS ONE HALF'; plain = `Better than live only in ${HALF_NAME[HALVES.find((h) => halves[h].win)]}. The rule: pick on Jan-Jun, it must hold in Jul-Oct. Live stays.`; }
  return { kind, head, plain, flags, ref, halves };
}

/** the table: for each row [label, {h1:{v,ref,d}, h2:{...}}] with already formatted text and the colour class of the difference */
export function table(data, sc) {
  const ref = (sc && byId(data, sc.ref)) || byId(data, data.live_id) || sc;
  if (!sc) return [];
  return ROWS.map((r) => {
    const cells = {};
    for (const h of HALVES) {
      const a = sc[h] ? sc[h][r.k] : null, b = ref && ref[h] ? ref[h][r.k] : null;
      let cls = '';
      if (r.good && num(a) != null && num(b) != null && a !== b) cls = (a - b) * r.good > 0 ? 'up' : 'down';
      cells[h] = { v: r.f(a), ref: r.f(b), cls, same: ref === sc || a === b };
    }
    return { k: r.k, label: r.label, cells };
  });
}

/** the one-line summary the Jarvis card and the verdict dock use */
export function summary(data, sc) {
  if (!sc) return 'Not tested';
  const y = sc.y26 || {};
  return `${usd(y.net)} · PF ${dec(y.pf)} · ${usd(sc.h2 && sc.h2.per_month)}/mo H2`;
}

/** colour per verdict kind (the page and the scene share it) */
export const KIND_COLOR = { live: '#ffb547', beats: '#5cf2a0', tradeoff: '#7fb4ff', mixed: '#ffd24a', still: '#9aa4bd', none: '#7a7f92' };
