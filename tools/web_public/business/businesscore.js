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
  };
}

// the first model that is not paused = what to do now
export function firstAction(doc) {
  const m = (doc && doc.models || []).find((x) => !x.paused && x.next);
  return m ? `${m.name}: ${m.next}` : 'Nothing to do.';
}

export function priceLine(p) {
  return p.setup > 0 ? `${money(p.setup)} + ${money(p.monthly)} a month` : `${money(p.monthly)} a month, no setup fee`;
}

export function taskKey(day, i) { return `d${day}t${i}`; }
