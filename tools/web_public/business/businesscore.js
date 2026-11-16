// BUSINESS core (pure, node-tested): checks the published file and turns it into rows. No DOM, no network.
export const money = (n) => '$' + Math.round(+n || 0).toLocaleString('en-US');
export const range = (r) => (Array.isArray(r) && r.length === 2 ? `${money(r[0])}-${money(r[1]).slice(1)}` : '-');

const str = (v, n = 300) => (typeof v === 'string' ? v.slice(0, n) : '');
const pair = (v) => (Array.isArray(v) && v.length === 2 && v.every((x) => Number.isFinite(+x) && +x >= 0) ? [+v[0], +v[1]] : [0, 0]);
const list = (v, n = 12) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, n).map((x) => x.slice(0, 300)) : []);

// a business.json / fixture.json -> a safe doc, or null when it is not one
export function clean(doc) {
  if (!doc || typeof doc !== 'object' || doc.kind !== 'business' || !Array.isArray(doc.models)) return null;
  const models = doc.models.filter((m) => m && typeof m === 'object' && str(m.id, 40) && str(m.name, 60)).map((m) => ({
    id: str(m.id, 40), name: str(m.name, 60), what: str(m.what), next: str(m.next), why: str(m.why), doc: str(m.doc, 80),
    paused: !!m.paused, built: list(m.built), first_dollar: list(m.first_dollar), usd_m1: pair(m.usd_m1), usd_m3: pair(m.usd_m3),
    hours: pair(m.hours), real: Number.isFinite(+m.real_usd_month) ? +m.real_usd_month : 0,
  }));
  const t = doc.total || {};
  return {
    sample: !!doc.sample, asof: str(doc.asof, 40), note: str(doc.note), models,
    total: { usd_m1: pair(t.usd_m1), usd_m3: pair(t.usd_m3), hours: pair(t.hours), real: Number.isFinite(+t.real_usd_month) ? +t.real_usd_month : 0 },
    prices: (Array.isArray(doc.prices) ? doc.prices : []).filter((p) => p && str(p.name, 40)).map((p) => ({ name: str(p.name, 40), setup: +p.setup || 0, monthly: +p.monthly || 0 })),
    week: (Array.isArray(doc.week) ? doc.week : []).filter((d) => d && Number.isFinite(+d.day)).slice(0, 7).map((d) => ({ day: +d.day, title: str(d.title, 80), tasks: list(d.tasks, 6) })),
    rules: list(doc.rules, 8),
    prop: cleanProp(doc.prop),
  };
}

const num = (v) => (v === null || v === undefined || v === '' || !Number.isFinite(+v) ? null : +v);
const day = (v) => (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null);

// the prop accounts' payout plan (tools/money/payout_plan.py via biz_publish): null when absent or not one
export function cleanProp(p) {
  if (!p || typeof p !== 'object' || !Array.isArray(p.table)) return null;
  const table = p.table.filter((r) => r && Number.isFinite(+r.accounts) && +r.accounts > 0).slice(0, 8).map((r) => ({
    accounts: +r.accounts, y1: num(r.usd_month_y1), steady: num(r.usd_month_m7_12), worst: num(r.month_worst),
    empty: num(r.months_no_income_pct), p10: num(r.y1_p10), ref: num(r.ref_usd_month),
  }));
  if (!table.length) return null;
  const z = p.zlarior && typeof p.zlarior === 'object' ? p.zlarior : null;
  return {
    span: str(p.span, 80), table, rules: list(p.rules, 6), notes: list(p.notes, 6),
    plan: str((p.new_account || {}).plan, 60), price: num((p.new_account || {}).price),
    zlarior: z ? { pass_median: day(z.pass_median), pass_earliest: day(z.pass_earliest), pass_10: num(z.pass_10), fail_10: num(z.fail_10),
      pay_earliest: day(z.first_payout_earliest), pay_median: day(z.first_payout_median), bank_median: day(z.first_payout_in_bank_median),
      pay_usd: num(z.first_payout_usd_median) } : null,
    buy: (Array.isArray(p.buy) ? p.buy : []).filter((x) => x && str(x.n, 4)).slice(0, 6).map((x) => ({
      n: str(x.n, 4), median: day(x.median), p25: day(x.p25), p75: day(x.p75), pct: num(x.pct_12m) })),
  };
}

// "$1,049" / "-$227" / "-"
export function signed(n) { return n === null || n === undefined ? '-' : (n < 0 ? '-' + money(-n) : money(n)); }

// the first model that is not paused = what to do now
export function firstAction(doc) {
  const m = (doc && doc.models || []).find((x) => !x.paused && x.next);
  return m ? `${m.name}: ${m.next}` : 'Nothing to do.';
}

export function priceLine(p) {
  return p.setup > 0 ? `${money(p.setup)} + ${money(p.monthly)} a month` : `${money(p.monthly)} a month, no setup fee`;
}

export function taskKey(day, i) { return `d${day}t${i}`; }
