// Agency > Expert, the pure part (team web-expert 2026-11-20, owner: "an expert expert on marketing 3D websites"). No DOM, no network:
// the page (expert.js), Jarvis (jarvis/biz.js 'web') and the node test (tests/test_web_expert.py) all read agency/expert/playbook.json through it.
//   diagnose(answers, P) -> { offer, price, monthly, total, script, why: [], addons: [], three_d, niche }      answers = { trade, site, reviews, visual, budget }
//   find(text, P)        -> { kind: 'niche' | 'card', item } | null      a free question ("what do I say to a roofer", "price a 3D site")
//   money(n)             -> '$1,500'
// Honest by design: ranges, never promises; the script slots stay [in brackets] for the owner to fill.

export const money = (n) => (typeof n === 'number' && Number.isFinite(n) ? '$' + Math.round(n).toLocaleString('en-US') : '');
export const range = (o) => (o ? `${money(o.usd_low)}-${money(o.usd_high)}${o.monthly ? ' a month' : ''}` : '');
const arr = (x) => (Array.isArray(x) ? x : []);
const byId = (list, id) => arr(list).find((x) => x && x.id === id) || null;

// the trade answer -> the niche whose words to use
export const TRADE_NICHE = { trades_fast: 'plumber', trades_big: 'roofer', health: 'dentist', places: 'venue', retail: 'furniture', food: 'restaurant', pro: 'lawyer' };
const VISUAL_TRADES = new Set(['trades_big', 'places', 'retail', 'health']);

export function diagnose(a, P) {
  const x = a || {}, offers = arr(P && P.offers), niches = arr(P && P.niches);
  let niche = byId(niches, TRADE_NICHE[x.trade] || 'roofer');
  if (x.trade === 'trades_big' && x.visual === 'yes') niche = byId(niches, x.budget === 'premium' ? 'builder' : 'landscaper') || niche;
  const why = [], addons = [];
  let offer = 'growth';
  const threeOk = x.visual === 'yes' && VISUAL_TRADES.has(x.trade) && x.budget !== 'tight';
  if (x.trade === 'food') { offer = 'gbp'; why.push('Restaurants are found on Google Maps first: fix the listing, then the site.'); addons.push('starter'); }
  else if (x.trade === 'trades_fast') { offer = x.budget === 'premium' || x.site === 'ok' ? 'growth' : 'starter'; why.push('An emergency trade wins on speed, a phone number at the top and reviews: no 3D.'); }
  else if (threeOk && x.site !== 'none' && x.budget === 'premium') { offer = 'immersive'; why.push('Customers buy what they can see, and the jobs are big: one extra sale pays for the 3D piece.'); }
  else if (x.visual === 'yes' && VISUAL_TRADES.has(x.trade) && x.budget === 'tight' && x.site !== 'ok') { offer = 'growth'; why.push('A visual business on a tight budget: the Growth site now, the 3D piece once it pays (+$2,500-$6,000).'); addons.push('3d-later'); }
  else if (threeOk) { offer = 'growth'; why.push('A visual business: start with the Growth site and offer the 3D piece as the next step (+$2,500-$6,000).'); addons.push('3d-later'); }
  else if (x.site === 'none') { offer = x.budget === 'tight' ? 'starter' : 'growth'; why.push('No website yet: the first site is the whole pitch.'); }
  else if (x.site === 'old') { offer = 'growth'; why.push('An old or slow site loses calls on phones: the Growth site fixes speed and adds a page per service.'); }
  else { offer = x.reviews === 'many' ? 'local' : 'gbp'; why.push('Their site is decent: sell results (the Google listing, reviews, town pages), not a new site.'); }
  if (x.reviews === 'few' && offer !== 'gbp') { addons.push('gbp'); why.push('Under 10 Google reviews: add the Google Business Profile fix and a review routine.'); }
  if (offer !== 'care' && offer !== 'local') addons.push('care');
  const o = byId(offers, offer), care = byId(offers, 'care');
  const extras = addons.map((id) => (id === '3d-later' ? { id, name: '3D piece later', range: '$2,500-$6,000' } : (() => { const ao = byId(offers, id); return ao ? { id, name: ao.name, range: range(ao) } : null; })())).filter(Boolean);
  const one = o && !o.monthly ? o : null;
  const total = one ? `${money(one.usd_low)}-${money(one.usd_high)}${care ? ` + ${range(care)}` : ''}` : o ? range(o) : '';
  return { offer: o, price: o ? range(o) : '', monthly: !!(o && o.monthly), total, script: niche ? niche.say : '', niche, three_d: niche ? niche.three_d : '', why, addons: extras };
}

// a free question -> the niche or the card that answers it
const TOPIC_WORDS = [
  ['price3d', /\b(price|pricing|charge|cost|quote)\b.*\b(3d|three d|immersive|webgl)\b|\b(3d|immersive)\b.*\b(price|pricing|charge|cost|worth)\b/],
  ['when3d', /\b(3d|immersive|three d)\b.*\b(niche|sell|gimmick|worth|when|best|who)\b|\b(best|which|what) (niche|trade|business(es)?)\b.*\b(3d|immersive)\b/],
  ['pricing', /\b(price|pricing|charge|how much|cost|quote|packages?)\b/],
  ['objections', /\b(objection|too expensive|not interested|nephew|already have|send me an email|they say)\b/],
  ['outreach', /\b(cold call|opener|outreach|pitch|first call|what do i say|script)\b/],
  ['gbp', /\b(google business|gbp|google (profile|listing|maps))\b/],
  ['localseo', /\b(seo|rank|near me|search)\b/],
  ['reviews', /\breviews?\b/],
  ['conversion', /\b(conversion|convert|more calls|leads from (the|my) site)\b/],
  ['ads', /\b(ads|advertis|ppc|local services)\b/],
  ['retainers', /\b(retainer|monthly|recurring|care plan|maintenance)\b/],
  ['upsells', /\b(upsell|add-?ons?|more from a client)\b/],
  ['positioning', /\b(niche|position|who should i (target|sell)|specialis|speciali[sz]e)\b/],
  ['process', /\b(process|timeline|how long|deposit|deliver)\b/],
];
const NICHE_WORDS = { roofer: /\broof/, plumber: /\b(plumb|hvac|electric)/, landscaper: /\b(landscap|pool|yard|garden)/, builder: /\b(builder|remodel|contractor|construction)/,
  dentist: /\b(dentist|dental|med ?spa|clinic|doctor)/, restaurant: /\b(restaurant|cafe|bar|bakery|pizza)/, venue: /\b(venue|wedding|event|hotel)/, realestate: /\b(real estate|realtor|realty|property|agent)/,
  auto: /\b(car|auto|dealer|mechanic)/, furniture: /\b(furniture|product|maker|showroom)/, gym: /\b(gym|fitness|studio|yoga|pilates)/, lawyer: /\b(lawyer|attorney|law firm|accountant|cpa)/ };
export function find(text, P) {
  const q = ' ' + String(text || '').toLowerCase() + ' ';
  const niches = arr(P && P.niches), cards = arr(P && P.cards);
  for (const [id, rx] of TOPIC_WORDS) if ((id === 'price3d' || id === 'when3d') && rx.test(q)) return { kind: 'card', item: byId(cards, id) };
  for (const [id, rx] of Object.entries(NICHE_WORDS)) if (rx.test(q)) { const n = byId(niches, id); if (n) return { kind: 'niche', item: n }; }
  for (const [id, rx] of TOPIC_WORDS) if (rx.test(q)) { const c = byId(cards, id); if (c) return { kind: 'card', item: c }; }
  return null;
}
export const sells3d = (P) => arr(P && P.niches).filter((n) => n.three_d === 'sells');
