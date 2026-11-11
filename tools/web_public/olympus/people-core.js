// PEOPLE OF OLYMPUS, core (pure, node-tested; docs/PERSONA_API.md): who the people are, what they look like, and what each one can truthfully say.
//   roster      normRoster(json) / FIXTURE_ROSTER / resolve(roster, id) (aliases, bare ids, synthesized keepers and villagers: an id always gives a person)
//   the look    spec(person, override?) -> plain data (skin, hair, hairStyle, outfit, accent, accessory, height, build, face, mood), deterministic from the seed;
//               portraitTree(spec, opts) -> a small tree of SVG nodes (head and shoulders in a round frame); svgText(tree) for textures and tests
//   the facts   buildFacts(person, inputs, now) -> { status, doing, last, learned, blocked, numbers, metrics, asof, sample, sources, mood }
// A person speaks for one real worker and only from that worker's own published files (inputs = { '<url>': parsed json | null }). A missing file is said out loud
// ("no file yet"); with nothing at all the bundled SAMPLE is used and labelled sample. Nothing here trades, sends or stores anything. Safari 16 safe.

export const H = 3600000, D = 24 * H;
export const KINDS = ['builder', 'scanner', 'bot', 'mind', 'keeper', 'champion'];
export const TEMPERS = ['calm', 'blunt', 'curious', 'wry'];
export const STATUS_WORD = { working: 'Working', idle: 'Idle', stale: 'Stale', failed: 'Failed', sample: 'Sample data' };
export const STATUS_COLOUR = { working: '#8fa05a', idle: '#4b7a99', stale: '#e0b060', failed: '#c96a4a', sample: '#b8ad98' };

export const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
export const arr = (v) => (Array.isArray(v) ? v : []);
export const num = (v) => (typeof v === 'number' && isFinite(v) ? v : null);
export function clean(t, n) { const s = String(t == null ? '' : t).replace(/[<>]/g, '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s; }
export function money(v) { const n = num(v); if (n == null) return '$?'; return (n < 0 ? '-$' : '$') + Math.abs(Math.round(n)).toLocaleString('en-US'); }
export function moneyC(v) { const n = num(v); if (n == null) return '$?'; return Math.abs(n) >= 100 ? moneyS(n) : (n > 0 ? '+' : n < 0 ? '-' : '') + '$' + Math.abs(n).toFixed(2); }
export function moneyS(v) { const n = num(v); if (n == null) return '$?'; return (n > 0 ? '+' : '') + money(n); }
export function rText(r) { const n = num(r); return n == null ? '' : (n > 0 ? '+' : '') + (Math.round(n * 100) / 100) + 'R'; }
/** "$312 (+0.73R)": every dollar with its R when both exist */
export function usdR(usd, r) { return moneyS(usd) + (num(r) != null ? ' (' + rText(r) + ')' : ''); }
export function toMs(v) {
  if (typeof v === 'number' && isFinite(v) && v > 0) return v > 1e11 ? v : v * 1000;
  if (typeof v !== 'string' || !v) return null;
  const t = Date.parse(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(v) ? v.replace(' ', 'T') + ':00Z' : /^\d{4}-\d{2}-\d{2}$/.test(v) ? v + 'T12:00:00Z' : /^\d{2}-\d{2}-\d{2}$/.test(v) ? '20' + v + 'T12:00:00Z' : v);
  return isFinite(t) ? t : null;
}
export const dayOf = (ms) => (ms == null ? '' : new Date(ms).toISOString().slice(0, 10));
export function ageH(ms, now) { return ms == null || !isFinite(now) ? null : Math.max(0, (now - ms) / H); }
export function agoText(ms, now) {
  const a = ageH(ms, now);
  if (a == null) return 'no time on record';
  if (a < 1) return Math.max(1, Math.round(a * 60)) + ' min ago';
  if (a < 36) return Math.round(a) + ' h ago';
  return Math.round(a / 24) + ' days ago';
}

// ------------------------------------------------------------------------------------------------ seeds
/** FNV-1a 32 bit over UTF-8 (the same number tools/people_build.py writes as `seed`) */
export function seedOf(text) {
  let h = 2166136261; const s = unescape(encodeURIComponent(String(text)));
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}
export function rng(seed) { let a = (seed >>> 0) || 1; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// ------------------------------------------------------------------------------------------------ the roster
const P = (id, name, meaning, title, kind, area, app, temperament, sources, place, bio) => ({ id, name, meaning, title, kind, area, app, seed: seedOf(id), temperament, voice: voiceOf(seedOf(id)), sources, home: { scene: 'ergasterion', place }, bio, aliases: id.indexOf(':') > 0 ? [id.split(':')[1]] : [] });
export function voiceOf(seed) { return { pitch: Math.round((0.8 + (seed % 51) / 100) * 100) / 100, rate: Math.round((0.92 + ((seed >>> 8) % 17) / 100) * 100) / 100 }; }
/** the people who always exist, even with no people.json at all (never blank) */
export const FIXTURE_ROSTER = Object.freeze({ v: 1, asof: '', fixture: true, people: [
  P('scanner:chrysos', 'Chrysanthe', 'golden flower', 'Prop-firm planner', 'scanner', 'money', 'chrysos', 'calm', ['../money/index.json', '../money/chrysos.json'], 'chrysos', 'Counts what each eval account costs and what it could pay back. Estimates only.'),
  P('scanner:mercury', 'Hermolaos', 'of the people of Hermes', 'Deal finder', 'scanner', 'money', 'mercury', 'wry', ['../money/index.json', '../money/mercury.json'], 'mercury', 'Watches prop-firm sales and discount codes so you never pay list price.'),
  P('scanner:sibyl', 'Manto', 'the seer', 'Prediction-market pick finder', 'scanner', 'money', 'sibyl', 'curious', ['../money/index.json', '../money/sibyl.json'], 'sibyl', 'Reads public prediction markets and writes down paper picks, with what could go wrong.'),
  P('scanner:oikos', 'Pheidon', 'the thrifty one', 'Household savings finder', 'scanner', 'money', 'oikos', 'calm', ['../money/index.json', '../money/oikos.json'], 'oikos', 'Looks for money the household already has and is not keeping.'),
  P('scanner:arbiter', 'Dikaios', 'the fair one', 'Price-gap checker', 'scanner', 'money', 'arbiter', 'blunt', ['../money/index.json', '../money/arbiter.json'], 'arbiter', 'Checks price gaps after fees. Most gaps are not there once the costs are in.'),
  P('bot:lit', 'Phoibos', 'the bright one', 'The LIT bot (Zlarior 50K, paper)', 'bot', 'trading', 'hestia', 'calm', ['../home.json', '../odeon/trades.json'], 'lit', 'Trades the LIT plan on NQ: one trade a day, the stop behind the sweep, size follows the stop.'),
  P('bot:atlas', 'Telamon', 'the bearer', 'The ATLAS bot (25K, paper)', 'bot', 'trading', 'hestia', 'blunt', ['../home.json'], 'atlas', 'Carries the second NQ strategy on the 25K account. Paper only.'),
  P('bot:blitz', 'Asterope', 'lightning', 'The BLITZ bot (25K, paper)', 'bot', 'trading', 'hestia', 'wry', ['../home.json'], 'blitz', 'The quick third NQ strategy on its own 25K account. Paper only.'),
  P('bot:kalshi', 'Eutychos', 'the fortunate', 'The Kalshi bot (paper)', 'bot', 'money', 'kalshi', 'curious', ['../kalshi.json', '../kalshicity/learned.json'], 'kalshi', 'Paper-trades prediction markets and keeps score of what it learned.'),
  P('mind', 'Metis', 'wise counsel', 'The Mind: nightly self-research', 'mind', 'research', 'mind', 'curious', ['../ergasterion/queue.json'], 'mind', 'Thinks at night about recent trades and tests ideas. She only suggests; she never changes a rule.'),
  P('job:prometheus', 'Pyrrhos', 'flame-coloured', 'Prometheus: breeds LIT settings', 'mind', 'research', 'prometheus', 'blunt', ['../prometheus/forge.json', '../cronos/status.json'], 'prometheus', 'Breeds LIT settings on Jan-Jun and checks them on Jul-Oct. Says so when nothing holds.'),
  P('job:hephaestus', 'Chalkeus', 'the bronze-smith', 'Hephaestus: stored LIT results', 'mind', 'research', 'hephaestus', 'calm', ['../hephaestus/data.json'], 'hephaestus', 'Keeps the stored result of every LIT setting that was really run. Read-only.'),
  P('job:cronos', 'Horaios', 'the timely one', 'Cronos: the night clock', 'mind', 'research', 'kronos', 'blunt', ['../cronos/status.json'], 'cronos', 'Runs the nightly jobs and tells you which ones failed or are late.'),
  P('job:queue', 'Kalamos', 'the reed pen', 'Scribe of the task queue', 'mind', 'factory', 'ergasterion', 'wry', ['../ergasterion/queue.json'], 'queue', 'Keeps the list of open tasks and write-ups, and the ideas that were tested and rejected.'),
], villagers: [] });

const VILLAGER_NAMES = ['Alexios', 'Anthea', 'Charis', 'Damon', 'Daphne', 'Eleni', 'Galene', 'Hektor', 'Ione', 'Kyros', 'Leda', 'Linos', 'Maia', 'Nestor', 'Olympia', 'Orestes', 'Rhea', 'Sophia', 'Theron', 'Xanthe', 'Zenon', 'Phoebe', 'Markos', 'Dion', 'Kyra', 'Selene', 'Thais', 'Myrto', 'Nikon', 'Chloe', 'Evander', 'Helene'];
const KEEPER_NAMES = [['Phylax', 'the guard'], ['Oikistes', 'the founder'], ['Polites', 'the citizen'], ['Demarchos', 'head of the deme'], ['Astynomos', 'warden of the town'], ['Pylaios', 'of the gate'], ['Nomios', 'of the pastures'], ['Limenios', 'of the harbour']];

function normPerson(p) {
  if (!isObj(p) || typeof p.id !== 'string' || !p.id) return null;
  const seed = num(p.seed) != null ? p.seed >>> 0 : seedOf(p.id), kind = KINDS.indexOf(p.kind) >= 0 || p.kind === 'villager' ? p.kind : 'keeper';
  return { ...p, id: p.id, name: clean(p.name || p.id, 40), meaning: clean(p.meaning, 60), title: clean(p.title || '', 80), kind, area: clean(p.area, 24), app: clean(p.app, 24), seed,
    temperament: TEMPERS.indexOf(p.temperament) >= 0 ? p.temperament : TEMPERS[seed % 4], voice: isObj(p.voice) && num(p.voice.pitch) != null ? { pitch: p.voice.pitch, rate: num(p.voice.rate) || 1 } : voiceOf(seed),
    sources: arr(p.sources).filter((s) => typeof s === 'string').slice(0, 30), home: isObj(p.home) ? { scene: clean(p.home.scene, 20), place: clean(p.home.place, 40) } : { scene: '', place: '' },
    bio: clean(p.bio, 200), aliases: arr(p.aliases).filter((s) => typeof s === 'string') };
}
/** anything -> { people, villagers, asof, fixture }: a broken or missing people.json gives the bundled cast */
export function normRoster(json) {
  const people = isObj(json) ? arr(json.people).map(normPerson).filter(Boolean) : [];
  if (!people.length) return { asof: '', fixture: true, people: FIXTURE_ROSTER.people.map(normPerson), villagers: [] };
  const seen = new Set(), uniq = people.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));
  return { asof: clean(json.asof, 30), fixture: false, people: uniq, villagers: arr(json.villagers).map(normPerson).filter(Boolean) };
}
const slug = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
/** the person for an id. Exact id, an alias, the bare tail ('chrysos', 'lit'), a branch or its first letters; `keeper:<anything>` and `villager:<app>` are made up on the spot (stable). null only for nonsense. */
export function resolve(roster, id) {
  if (typeof id !== 'string' || !id.trim()) return null;
  const want = id.trim(), all = roster.people.concat(roster.villagers);
  let p = all.find((x) => x.id === want) || all.find((x) => x.aliases.indexOf(want) >= 0);
  if (p) return p;
  const low = want.toLowerCase(), tail = low.indexOf(':') >= 0 ? low.slice(low.indexOf(':') + 1) : low, ns = low.indexOf(':') >= 0 ? low.slice(0, low.indexOf(':')) : '';
  p = roster.people.find((x) => x.id.toLowerCase() === low) || roster.people.find((x) => (!ns || x.id.indexOf(ns + ':') === 0 || ns === 'worker' || ns === 'station') && (x.id.split(':').pop() === tail || x.aliases.some((a) => a.toLowerCase() === tail || a.toLowerCase() === low)));
  if (p) return p;
  if (ns === 'builder' || /^worktree-agent-/.test(low)) {
    const t = tail.replace(/^worktree-agent-/, '');
    p = roster.people.find((x) => x.kind === 'builder' && (x.id.split(':')[1].indexOf(t.slice(0, 8)) === 0 && t.length >= 6 || slug(x.agent) === slug(t) || String(x.branch || '').toLowerCase() === low));
    if (p) return p;
  }
  if (ns === 'worker' || ns === 'station') { if (tail === 'dev') return roster.people.find((x) => x.kind === 'builder') || null; return null; }
  if (ns === 'villager' && tail) {
    const s = seedOf('villager:' + tail), nm = tail.charAt(0).toUpperCase() + tail.slice(1);
    return normPerson({ id: 'villager:' + tail, name: VILLAGER_NAMES[s % VILLAGER_NAMES.length], title: 'Lives in ' + nm, kind: 'villager', area: '', app: tail, sources: ['../' + tail + '/jarvis.json'], home: { scene: 'athens', place: tail }, bio: 'Speaks for the ' + nm + ' app.', appName: nm, made: true });
  }
  if (ns === 'keeper' && tail) {
    const s = seedOf('keeper:' + tail), k = KEEPER_NAMES[s % KEEPER_NAMES.length], nm = tail.replace(/[-_]+/g, ' ').replace(/\b[a-z]/g, (c) => c.toUpperCase());
    return normPerson({ id: 'keeper:' + tail, name: k[0], meaning: k[1], title: 'Keeper of ' + clean(nm, 40), kind: 'keeper', area: tail, app: 'cities', sources: [], home: { scene: 'hellas', place: tail }, bio: 'Looks after ' + clean(nm, 40) + ' and tells you what its data says.', made: true });
  }
  if (ns === 'champion' && tail) return normPerson({ id: 'champion:' + tail, name: 'Aristos', meaning: 'the best', title: 'Run ' + clean(tail, 40), kind: 'champion', area: 'archive', app: 'archive', sources: ['../archive/index.json'], home: { scene: 'colosseum', place: tail }, bio: 'A stored run of the Archive. History, not a forecast.', made: true });
  return null;
}
export function filterPeople(list, f) {
  if (!f) return list.slice();
  if (typeof f === 'function') return list.filter(f);
  if (typeof f === 'string') return list.filter((p) => p.kind === f || p.area === f);
  return list.filter((p) => (!f.kind || p.kind === f.kind) && (!f.area || p.area === f.area) && (!f.scene || p.home.scene === f.scene) && (!f.place || p.home.place === f.place) && (!f.app || p.app === f.app));
}

// ------------------------------------------------------------------------------------------------ the look
export const SKINS = ['#f1cfa9', '#e8b98d', '#d9a273', '#c48a5c', '#a36d45', '#7d5233'];
export const HAIRS = ['#2a2019', '#4a3323', '#6f4a2c', '#8a4b2a', '#b98a4a', '#d9c08a', '#8c867c', '#e6e0d2'];
export const HAIR_STYLES = ['short', 'curly', 'bun', 'long', 'bob', 'wavy', 'topknot', 'bald'];
export const OUTFITS = ['#c8a24a', '#7f8a52', '#c96a4a', '#4b7a99', '#e9dfc9', '#9c6b3c', '#a9764c', '#8fa07a', '#d9b25a', '#b5563c'];
export const EYES = ['dot', 'oval', 'wide', 'smile'];
export const BROWS = ['flat', 'arched', 'slant', 'thick'];
export const MOUTHS = ['smile', 'grin', 'small', 'flat'];
export const BEARDS = ['none', 'none', 'none', 'short', 'full', 'moustache'];
export const BUILDS = ['slim', 'round', 'broad'];
export const MOODS = ['calm', 'proud', 'busy', 'worried', 'sheepish'];
export const ACCESSORY = { champion: 'laurel', builder: 'hammer', scanner: 'pouch', bot: 'helmet', mind: 'scroll', keeper: 'key', villager: 'none' };
const pickOf = (list, r) => list[Math.min(list.length - 1, Math.floor(r() * list.length))];
function shade(hex, k) { const n = parseInt(String(hex).slice(1), 16), f = (c) => Math.max(0, Math.min(255, Math.round(k < 0 ? c * (1 + k) : c + (255 - c) * k))); return '#' + ((1 << 24) | (f(n >> 16) << 16) | (f((n >> 8) & 255) << 8) | f(n & 255)).toString(16).slice(1); }
export { shade };
/** the character sheet of a person: plain data, the same every time for the same seed. `over` (the owner's own character, or a scene) may replace any field. */
export function spec(person, over) {
  const p = isObj(person) ? person : {}, seed = num(p.seed) != null ? p.seed >>> 0 : seedOf(p.id || 'someone'), r = rng(seed);
  const skin = pickOf(SKINS, r), hair = pickOf(HAIRS, r), hairStyle = pickOf(HAIR_STYLES, r), outfit = pickOf(OUTFITS, r);
  let accent = pickOf(OUTFITS, r); if (accent === outfit) accent = OUTFITS[(OUTFITS.indexOf(outfit) + 3) % OUTFITS.length];
  const face = { eyes: pickOf(EYES, r), brows: pickOf(BROWS, r), mouth: pickOf(MOUTHS, r), glasses: r() < 0.17, beard: pickOf(BEARDS, r), freckles: r() < 0.15 };
  const height = Math.round((0.9 + r() * 0.2) * 100) / 100, build = pickOf(BUILDS, r);
  let accessory = ACCESSORY[p.kind] || 'none';
  if (p.id === 'mind') accessory = 'owl';
  if (p.id === 'job:hephaestus') accessory = 'hammer';
  if (p.id === 'job:prometheus') accessory = 'torch';
  if (p.kind === 'champion' && p.fallen) accessory = 'none';
  const s = { seed, skin, hair, hairStyle: accessory === 'helmet' && hairStyle === 'bun' ? 'short' : hairStyle, outfit, accent, accessory, height, build, face, mood: 'calm' };
  if (isObj(over)) for (const k of Object.keys(s)) { if (k === 'face') { if (isObj(over.face)) s.face = { ...s.face, ...over.face }; } else if (over[k] != null) s[k] = over[k]; }
  if (MOODS.indexOf(s.mood) < 0) s.mood = 'calm';
  return s;
}

const N = (tag, attrs, children) => ({ tag, attrs: attrs || {}, children: children || [] });
const f1 = (v) => Math.round(v * 10) / 10;
/** head and shoulders in a round frame, viewBox 0 0 100 100. Bold enough to read at 44 px; no filters, no gradients, no images. */
export function portraitTree(sp, opts) {
  const o = opts || {}, s = sp, mood = o.mood || s.mood || 'calm', id = 'pp' + (s.seed >>> 0).toString(36) + (o.uid || '');
  const skinD = shade(s.skin, -0.16), hairD = shade(s.hair, -0.25), ink = '#2a2019', outD = shade(s.outfit, -0.2), bg = o.bg || mix(s.accent, '#2a231b', 0.72);
  const rx = s.build === 'round' ? 26 : s.build === 'slim' ? 22.5 : 24.5, cy = 43, hs = s.accessory === 'helmet' ? 'helmet' : s.hairStyle;
  const g = [];
  g.push(N('circle', { cx: 50, cy: 50, r: 50, fill: bg }));
  g.push(N('circle', { cx: 50, cy: 50, r: 43, fill: shade(bg, 0.07) }));
  // hair behind the head
  if (hs === 'long') g.push(N('path', { d: 'M22 44 C18 8 82 8 78 44 L81 80 C70 86 30 86 19 80 Z', fill: s.hair }));
  if (hs === 'bob') g.push(N('path', { d: 'M22 42 C19 10 81 10 78 42 L78 60 C72 66 28 66 22 60 Z', fill: s.hair }));
  if (hs === 'bun') g.push(N('circle', { cx: 50, cy: 12, r: 9, fill: s.hair }));
  if (hs === 'topknot') g.push(N('ellipse', { cx: 50, cy: 12, rx: 6, ry: 8, fill: s.hair }));
  // shoulders, neck
  const sw = s.build === 'broad' ? 40 : s.build === 'slim' ? 33 : 37;
  g.push(N('path', { d: `M${50 - sw} 101 C${50 - sw} 80 ${50 - sw / 2} 71 50 71 C${50 + sw / 2} 71 ${50 + sw} 80 ${50 + sw} 101 Z`, fill: s.outfit }));
  g.push(N('path', { d: `M${50 - sw} 101 C${50 - sw} 88 ${50 - sw / 2 - 4} 80 ${50 - sw / 2 + 2} 76 L${50 - sw / 2 + 8} 101 Z`, fill: outD, opacity: 0.45 }));
  g.push(N('rect', { x: 43, y: 60, width: 14, height: 15, rx: 5, fill: skinD }));
  g.push(N('path', { d: 'M37 72 Q50 88 63 72 Q50 77 37 72 Z', fill: s.skin }));
  g.push(N('path', { d: 'M36 72 Q50 89 64 72', fill: 'none', stroke: s.accent, 'stroke-width': 3.2, 'stroke-linecap': 'round' }));
  g.push(N('circle', { cx: 65, cy: 75, r: 3, fill: '#c8a24a', stroke: '#8a6a2a', 'stroke-width': 0.8 }));
  // ears, head
  g.push(N('circle', { cx: 50 - rx - 0.5, cy: cy + 3, r: 4.4, fill: skinD }));
  g.push(N('circle', { cx: 50 + rx + 0.5, cy: cy + 3, r: 4.4, fill: skinD }));
  g.push(N('ellipse', { cx: 50, cy, rx, ry: 25.5, fill: s.skin }));
  // beard under the face features
  const bd = s.face.beard;
  if (bd === 'short') g.push(N('path', { d: `M${50 - rx + 1} 47 C${50 - rx + 2} 71 ${50 + rx - 2} 71 ${50 + rx - 1} 47 C${50 + rx - 6} 58 60 60 50 60 C40 60 ${50 - rx + 6} 58 ${50 - rx + 1} 47 Z`, fill: s.hair, opacity: 0.92 }));
  if (bd === 'full') g.push(N('path', { d: `M${50 - rx + 1} 45 C${50 - rx - 1} 80 ${50 + rx + 1} 80 ${50 + rx - 1} 45 C${50 + rx - 6} 56 60 57 50 57 C40 57 ${50 - rx + 6} 56 ${50 - rx + 1} 45 Z`, fill: s.hair }));
  // cheeks
  g.push(N('circle', { cx: 50 - rx + 8, cy: cy + 9, r: 4.4, fill: '#c96a4a', opacity: mood === 'sheepish' ? 0.5 : 0.24 }));
  g.push(N('circle', { cx: 50 + rx - 8, cy: cy + 9, r: 4.4, fill: '#c96a4a', opacity: mood === 'sheepish' ? 0.5 : 0.24 }));
  if (s.face.freckles) for (const [x, y] of [[36, 50], [39, 52.5], [61, 52.5], [64, 50]]) g.push(N('circle', { cx: x, cy: y, r: 0.9, fill: skinD }));
  // hair on top
  const top = cy - 25.5;
  if (hs === 'short' || hs === 'bun' || hs === 'topknot') g.push(N('path', { d: `M${50 - rx - 1} ${cy - 2} C${50 - rx - 3} ${top - 6} ${50 + rx + 3} ${top - 6} ${50 + rx + 1} ${cy - 2} C${50 + rx - 6} ${top + 9} 60 ${top + 7} 50 ${top + 7} C40 ${top + 7} ${50 - rx + 6} ${top + 9} ${50 - rx - 1} ${cy - 2} Z`, fill: s.hair }));
  if (hs === 'wavy') g.push(N('path', { d: `M${50 - rx - 1} ${cy} C${50 - rx - 4} ${top - 8} ${50 + rx + 4} ${top - 9} ${50 + rx + 1} ${cy} C${50 + rx - 3} ${top + 12} 62 ${top + 13} 44 ${top + 5} C38 ${top + 10} ${50 - rx + 3} ${top + 13} ${50 - rx - 1} ${cy} Z`, fill: s.hair }));
  if (hs === 'long' || hs === 'bob') g.push(N('path', { d: `M${50 - rx - 1} ${cy + 2} C${50 - rx - 3} ${top - 6} ${50 + rx + 3} ${top - 6} ${50 + rx + 1} ${cy + 2} C${50 + rx - 4} ${top + 10} 58 ${top + 6} 50 ${top + 9} C42 ${top + 6} ${50 - rx + 4} ${top + 10} ${50 - rx - 1} ${cy + 2} Z`, fill: s.hair }));
  if (hs === 'curly') for (let i = 0; i < 8; i++) { const a = Math.PI * (1.04 + i * 0.132), cx = 50 + Math.cos(a) * (rx + 1), y = cy - 3 + Math.sin(a) * 25; g.push(N('circle', { cx: f1(cx), cy: f1(y), r: 7.6, fill: i % 2 ? s.hair : shade(s.hair, 0.06) })); }
  if (hs === 'bald') { g.push(N('path', { d: `M${50 - rx} ${cy - 4} q-2 6 1 10`, fill: 'none', stroke: s.hair, 'stroke-width': 3.4, 'stroke-linecap': 'round' })); g.push(N('path', { d: `M${50 + rx} ${cy - 4} q2 6 -1 10`, fill: 'none', stroke: s.hair, 'stroke-width': 3.4, 'stroke-linecap': 'round' })); }
  if (hs === 'helmet') {
    g.push(N('path', { d: 'M34 16 C38 0 62 0 66 16 C58 9 42 9 34 16 Z', fill: '#c96a4a' }));
    g.push(N('path', { d: `M${50 - rx - 2} ${cy + 1} C${50 - rx - 5} ${top - 7} ${50 + rx + 5} ${top - 7} ${50 + rx + 2} ${cy + 1} L${50 + rx + 2} ${cy - 5} C${50 + rx - 8} ${top + 12} ${50 - rx + 8} ${top + 12} ${50 - rx - 2} ${cy - 5} Z`, fill: '#b98a4a' }));
    g.push(N('path', { d: `M${50 - rx - 2} ${cy - 5} C${50 - rx + 8} ${top + 12} ${50 + rx - 8} ${top + 12} ${50 + rx + 2} ${cy - 5}`, fill: 'none', stroke: '#8a6a2a', 'stroke-width': 1.6 }));
    g.push(N('rect', { x: 48.2, y: top + 9, width: 3.6, height: 9, rx: 1.6, fill: '#b98a4a' }));
  }
  // brows
  const by = cy - 6.5 + (mood === 'worried' || mood === 'sheepish' ? -1.5 : 0), bw = s.face.brows === 'thick' ? 3 : 2.1, bc = s.hair === '#e6e0d2' || s.hair === '#d9c08a' ? '#8a7a5a' : hairD;
  const brow = (x, dir) => {
    const k = s.face.brows, tilt = mood === 'worried' || mood === 'sheepish' ? -2.2 : k === 'slant' ? 1.6 : 0, arch = k === 'arched' || mood === 'proud' ? -2.4 : -0.6;
    const yIn = f1(by + tilt * 0.6), yOut = f1(by - tilt * 0.5);
    return N('path', { d: `M${x - 4.6} ${dir < 0 ? yOut : yIn} Q${x} ${f1(by + arch)} ${x + 4.6} ${dir < 0 ? yIn : yOut}`, fill: 'none', stroke: bc, 'stroke-width': bw, 'stroke-linecap': 'round' });
  };
  g.push(brow(40, -1)); g.push(brow(60, 1));
  // eyes
  const eye = (x) => {
    const k = mood === 'proud' && s.face.eyes !== 'wide' ? 'smile' : s.face.eyes, y = cy + 1;
    if (o.blink) return [N('path', { d: `M${x - 3.6} ${y} L${x + 3.6} ${y}`, stroke: ink, 'stroke-width': 2.2, 'stroke-linecap': 'round', fill: 'none' })];
    if (k === 'smile') return [N('path', { d: `M${x - 3.8} ${y + 1.4} Q${x} ${y - 4} ${x + 3.8} ${y + 1.4}`, fill: 'none', stroke: ink, 'stroke-width': 2.4, 'stroke-linecap': 'round' })];
    if (k === 'wide') return [N('circle', { cx: x, cy: y, r: 5, fill: '#f6efe2' }), N('circle', { cx: x + (mood === 'sheepish' ? 1.2 : 0), cy: y + 0.4, r: 2.9, fill: ink }), N('circle', { cx: x + 1, cy: y - 1, r: 0.9, fill: '#f6efe2' })];
    if (k === 'oval') return [N('ellipse', { cx: x, cy: y, rx: 3, ry: 4.3, fill: ink }), N('circle', { cx: x + 0.9, cy: y - 1.5, r: 1, fill: '#f6efe2' })];
    return [N('circle', { cx: x, cy: y, r: 3.3, fill: ink }), N('circle', { cx: x + 0.9, cy: y - 1.1, r: 0.9, fill: '#f6efe2' })];
  };
  for (const e of eye(40).concat(eye(60))) g.push(e);
  if (s.face.glasses) {
    g.push(N('circle', { cx: 40, cy: cy + 1, r: 6.6, fill: 'none', stroke: '#6b4a2a', 'stroke-width': 1.7 })); g.push(N('circle', { cx: 60, cy: cy + 1, r: 6.6, fill: 'none', stroke: '#6b4a2a', 'stroke-width': 1.7 }));
    g.push(N('path', { d: `M46.6 ${cy + 0.4} Q50 ${cy - 1.6} 53.4 ${cy + 0.4}`, fill: 'none', stroke: '#6b4a2a', 'stroke-width': 1.7 }));
  }
  // nose, mouth
  g.push(N('path', { d: `M48.4 ${cy + 6.6} Q50 ${cy + 8.6} 51.6 ${cy + 6.6}`, fill: 'none', stroke: skinD, 'stroke-width': 1.7, 'stroke-linecap': 'round' }));
  if (bd === 'moustache') g.push(N('path', { d: `M41 ${cy + 11.5} Q45.5 ${cy + 8} 50 ${cy + 10.6} Q54.5 ${cy + 8} 59 ${cy + 11.5} Q54.5 ${cy + 13.6} 50 ${cy + 12} Q45.5 ${cy + 13.6} 41 ${cy + 11.5} Z`, fill: s.hair }));
  const my = cy + 13.2 + (bd === 'moustache' ? 1.6 : 0), mk = o.talk ? 'o' : mood === 'proud' ? 'grin' : mood === 'sheepish' ? 'wobble' : mood === 'worried' ? 'frown' : s.face.mouth;
  const mcol = bd === 'full' || bd === 'short' ? '#f6efe2' : ink;
  if (mk === 'grin') { g.push(N('path', { d: `M43 ${my - 1.4} Q50 ${my + 8.5} 57 ${my - 1.4} Z`, fill: '#5a2a22' })); g.push(N('path', { d: `M44.6 ${my - 0.8} Q50 ${my + 1.6} 55.4 ${my - 0.8} Z`, fill: '#f6efe2' })); }
  else if (mk === 'o') g.push(N('ellipse', { cx: 50, cy: my + 1, rx: 2.9, ry: 3.6, fill: '#5a2a22' }));
  else if (mk === 'wobble') g.push(N('path', { d: `M44 ${my + 1} Q47 ${my - 2} 50 ${my + 1} T56 ${my + 1}`, fill: 'none', stroke: mcol, 'stroke-width': 2.1, 'stroke-linecap': 'round' }));
  else if (mk === 'frown') g.push(N('path', { d: `M45 ${my + 2.4} Q50 ${my - 1.6} 55 ${my + 2.4}`, fill: 'none', stroke: mcol, 'stroke-width': 2.1, 'stroke-linecap': 'round' }));
  else if (mk === 'flat') g.push(N('path', { d: `M45.4 ${my + 0.6} Q50 ${my + 1.8} 54.6 ${my + 0.6}`, fill: 'none', stroke: mcol, 'stroke-width': 2.1, 'stroke-linecap': 'round' }));
  else if (mk === 'small') g.push(N('path', { d: `M46.6 ${my} Q50 ${my + 3.6} 53.4 ${my}`, fill: 'none', stroke: mcol, 'stroke-width': 2.1, 'stroke-linecap': 'round' }));
  else g.push(N('path', { d: `M43.6 ${my - 0.6} Q50 ${my + 6} 56.4 ${my - 0.6}`, fill: 'none', stroke: mcol, 'stroke-width': 2.2, 'stroke-linecap': 'round' }));
  if (mood === 'sheepish') g.push(N('path', { d: `M${50 + rx - 3} ${cy - 14} q3 5 0 7 q-3 -2 0 -7 Z`, fill: '#9fc3d6' }));
  // the accessory of the kind
  const ac = s.accessory;
  if (ac === 'laurel') for (let side = -1; side <= 1; side += 2) for (let i = 0; i < 5; i++) {
    const a = (Math.PI / 180) * (198 + i * 17), x = 50 + side * Math.cos(a) * -(rx + 2.5), y = cy - 4 + Math.sin(a) * 26;
    g.push(N('ellipse', { cx: f1(x), cy: f1(y), rx: 5.2, ry: 2.5, fill: i % 2 ? '#c8a24a' : '#8fa05a', transform: `rotate(${f1(side * (-62 + i * 17))} ${f1(x)} ${f1(y)})` }));
  }
  if (ac === 'owl') {
    g.push(N('ellipse', { cx: 80, cy: 73, rx: 8.5, ry: 10, fill: '#9c6b3c' })); g.push(N('ellipse', { cx: 80, cy: 76, rx: 5, ry: 6, fill: '#d9c08a' }));
    g.push(N('path', { d: 'M72.5 65 l3 -5 l3 4 Z M87.5 65 l-3 -5 l-3 4 Z', fill: '#9c6b3c' }));
    g.push(N('circle', { cx: 76.6, cy: 69.5, r: 3.1, fill: '#f6efe2' })); g.push(N('circle', { cx: 83.4, cy: 69.5, r: 3.1, fill: '#f6efe2' }));
    g.push(N('circle', { cx: 76.9, cy: 69.7, r: 1.5, fill: ink })); g.push(N('circle', { cx: 83.1, cy: 69.7, r: 1.5, fill: ink })); g.push(N('path', { d: 'M78.8 72.4 L81.2 72.4 L80 75 Z', fill: '#c8a24a' }));
  }
  if (ac === 'hammer') { g.push(N('rect', { x: 14, y: 68, width: 3.6, height: 26, rx: 1.6, fill: '#9c6b3c', transform: 'rotate(-18 16 80)' })); g.push(N('rect', { x: 5.5, y: 62.5, width: 17, height: 9, rx: 2.4, fill: '#8c867c', stroke: '#5c574f', 'stroke-width': 1, transform: 'rotate(-18 16 80)' })); }
  if (ac === 'pouch') { g.push(N('path', { d: 'M72 82 C68 96 92 96 88 82 C86 78 74 78 72 82 Z', fill: '#9c6b3c' })); g.push(N('path', { d: 'M74.5 80 L77 75 L83 75 L85.5 80 Z', fill: '#7a5230' })); g.push(N('path', { d: 'M74 80.2 L86 80.2', stroke: '#e9dfc9', 'stroke-width': 1.5, 'stroke-linecap': 'round' })); g.push(N('circle', { cx: 80, cy: 87, r: 3.4, fill: '#d9b25a', stroke: '#8a6a2a', 'stroke-width': 0.9 })); }
  if (ac === 'scroll') { g.push(N('rect', { x: 9, y: 76, width: 22, height: 13, rx: 2, fill: '#e9dfc9', transform: 'rotate(-12 20 82)' })); g.push(N('rect', { x: 6.5, y: 74.5, width: 4.6, height: 16, rx: 2.3, fill: '#cdbf9f', transform: 'rotate(-12 20 82)' })); g.push(N('rect', { x: 28.6, y: 74.5, width: 4.6, height: 16, rx: 2.3, fill: '#cdbf9f', transform: 'rotate(-12 20 82)' })); g.push(N('path', { d: 'M14 81 L26 78.6 M14.6 84.6 L24 82.8', stroke: '#9a8f7d', 'stroke-width': 1.1, 'stroke-linecap': 'round', fill: 'none' })); }
  if (ac === 'key') { g.push(N('circle', { cx: 80, cy: 79, r: 4.8, fill: 'none', stroke: '#d9b25a', 'stroke-width': 2.6 })); g.push(N('path', { d: 'M80 84 L80 97 M80 91 L84.5 91 M80 95 L83.5 95', fill: 'none', stroke: '#d9b25a', 'stroke-width': 2.6, 'stroke-linecap': 'round' })); }
  if (ac === 'torch') { g.push(N('rect', { x: 16, y: 74, width: 4.4, height: 24, rx: 2, fill: '#9c6b3c' })); g.push(N('path', { d: 'M18.2 60 C24 67 24.5 72 18.2 75.5 C11.9 72 12.4 67 18.2 60 Z', fill: '#e0b060' })); g.push(N('path', { d: 'M18.2 66 C21 69.5 21 72.4 18.2 74.4 C15.4 72.4 15.4 69.5 18.2 66 Z', fill: '#c96a4a' })); }
  return N('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 100 100', width: o.size || 44, height: o.size || 44, role: 'img', 'aria-label': o.label || 'portrait' },
    [N('defs', {}, [N('clipPath', { id }, [N('circle', { cx: 50, cy: 50, r: 50 })])]), N('g', { 'clip-path': `url(#${id})` }, g), N('circle', { cx: 50, cy: 50, r: 48.6, fill: 'none', stroke: o.ring || '#9c6b3c', 'stroke-width': 2.8 })]);
}
function mix(a, b, k) { const x = parseInt(a.slice(1), 16), y = parseInt(b.slice(1), 16), m = (s) => Math.round(((x >> s) & 255) * (1 - k) + ((y >> s) & 255) * k); return '#' + ((1 << 24) | (m(16) << 16) | (m(8) << 8) | m(0)).toString(16).slice(1); }
export { mix };
const esc = (v) => String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
/** the tree as SVG text (canvas textures, tests, share images). Attribute values are escaped; there is no text content. */
export function svgText(node) { return '<' + node.tag + Object.keys(node.attrs).map((k) => ' ' + k + '="' + esc(node.attrs[k]) + '"').join('') + (node.children.length ? '>' + node.children.map(svgText).join('') + '</' + node.tag + '>' : '/>'); }

// ------------------------------------------------------------------------------------------------ the facts
/** tiny example inputs, used only when a person has none of its own files. Always labelled sample. */
export const SAMPLE = Object.freeze({
  '../home.json': { t_ago_h: 0.2, accounts: [
    { id: 'mffu50k_eval', name: 'Zlarior 50K', conn: { connected: true }, eval: { room: 1420, mll: 2000, to_target: 2580 }, pnl: { today: 312, week: 540 } },
    { id: 'acctb', name: 'ATLAS 25K', conn: { connected: true }, eval: { room: 840, mll: 1000, to_target: 1425 }, pnl: { today: -60, week: 140 } },
    { id: 'acct_c', name: 'BLITZ 25K', conn: { connected: true }, eval: { room: 560, mll: 1000, paused: true }, pnl: { today: 0, week: 0 }, paused: true }] },
  '../odeon/trades.json': { trades: [{ id: 's1', day_ago: 1, usd: 312, r: 0.73, side: 'long' }, { id: 's2', day_ago: 2, usd: -437, r: -1.03, side: 'short' }] },
  '../money/index.json': { streams: [
    { id: 'chrysos', status: 'sample', age_min: 30, headline: 'Example: the next buy looks best, about $5,400 over 12 months (an estimate).', usd_month: 450, items: [{ title: 'Next buy: the 50K plan', usd: 5439, score: 89, risk: 'low' }, { title: 'Buy: the 25K plan', usd: 2528, score: 71, risk: 'low' }], notes: ['Example: break-even is about 1.4 months in every case.'] },
    { id: 'mercury', status: 'sample', age_min: 90, headline: 'Example: one prop-firm sale found.', items: [{ title: 'Prop-firm sale on the 50K plan', usd: 28, score: 80, risk: 'low', expires: '2026-11-30' }], notes: ['Example: a code can end without notice.'] },
    { id: 'sibyl', status: 'sample', age_min: 60, headline: 'Example: two paper picks worth a look.', items: [{ title: 'Paper pick: rain in New York on Friday', usd: 6, score: 64, risk: 'med' }, { title: 'Paper pick: index closes inside its range', usd: 4, score: 58, risk: 'med' }], notes: ['Example: small samples, paper only.'] },
    { id: 'oikos', status: 'sample', age_min: 600, headline: 'Example: about $38 a month the household could keep.', usd_month: 38, items: [{ title: 'A subscription nobody uses', usd: 12, score: 77, risk: 'low' }], notes: ['Example: check each bill yourself before cancelling.'] },
    { id: 'arbiter', status: 'sample', age_min: 45, headline: 'Example: no gap survives the fees today.', items: [], notes: ['Example: most gaps close before a person can act.'] }] },
  '../kalshi.json': { t_ago_h: 0.4, running: true, today_pnl: 2.4, settled_n: 41, last_trades: [{ title: 'Paper: rain in New York', pnl: 1.8 }, { title: 'Paper: index range', pnl: -0.6 }] },
  '../ergasterion/queue.json': { asof_ago_d: 1, queue: { total: 12, open: 4, done: 8, tasks: [{ id: 'sample-task', text: 'Example task: check the phone layout of one app', section: 'P1' }] },
    writeups: { count: 9, latest: [{ date_ago_d: 2, title: 'Example write-up: a filter that did not hold', status: 'rejected', summary: 'Example: better in one period, worse in the other.' }] },
    rejected: [{ title: 'Example: a filter that did not hold', file: 'research/writeups/example.md', summary: 'Better in one period, worse in the other.' }],
    learnings: [{ d_ago: 2, who: 'lit', text: 'Example: wide stops mean fewer micros, so the dollar risk stays the same.', src: 'research/writeups/example.md', kind: 'info' }, { d_ago: 3, who: 'dev', text: 'Example: test the phone layout before calling a page done.', src: 'research/writeups/example.md', kind: 'info' }],
    mind: { tested: 22, t_ago_h: 20, observations: [{ text: 'Example: most recent losses came after a quiet open.', bot: 'lit', score: 0.7 }], source: 'research/mind/example.json' }, git: { available: false, commits: [], branches: [] } },
  '../cronos/status.json': { tasks: { archive: { last_run_ago_h: 9, ok: true, cadence: 'nightly' }, prometheus: { last_run_ago_h: 60, ok: true, cadence: 'weekly' }, mind: { last_run_ago_h: 20, ok: true, cadence: 'nightly' } } },
  '../prometheus/forge.json': { demo: true, built_ago_h: 60, gens_n: 12, pop: 40, verdict: { real_margin: false, h1_gain_pm: 310, h2_gain_pm: -45, survive_pct: 0 }, honesty: { genomes_checked: 480, beat_live_both: 3 } },
  '../hephaestus/data.json': { demo: true, built_ago_h: 100, dials: [{ label: 'Break-even trigger', options: [1, 2, 3] }, { label: 'Time cut', options: [1, 2] }] },
});
/** the SAMPLE with its "ago" fields turned into real times counted back from now */
export function sampleInputs(now) {
  const walk = (v) => {
    if (Array.isArray(v)) return v.map(walk);
    if (!isObj(v)) return v;
    const o = {};
    for (const k of Object.keys(v)) {
      const x = v[k];
      if (k === 't_ago_h') o.t = Math.round((now - x * H) / 1000);
      else if (k === 'built_ago_h') o.built = new Date(now - x * H).toISOString();
      else if (k === 'last_run_ago_h') o.last_run_t = Math.round((now - x * H) / 1000);
      else if (k === 'asof_ago_d') o.asof = dayOf(now - x * D);
      else if (k === 'date_ago_d') o.date = dayOf(now - x * D);
      else if (k === 'd_ago') o.d = dayOf(now - x * D);
      else if (k === 'day_ago') o.day = dayOf(now - x * D);
      else o[k] = walk(x);
    }
    return o;
  };
  return walk(SAMPLE);
}

const out = (t, text) => ({ t: t == null ? null : t, text: clean(text, 170) });
const N2 = (label, text) => ({ label, text: String(text) });
function blank(p) { return { status: 'stale', doing: '', last: [], learned: [], blocked: '', numbers: [], metrics: {}, asof: null, sample: false, sources: [], mood: 'calm', missing: false, note: '' }; }
function learnedFrom(queue, who, extra) {
  const L = [];
  for (const l of arr(isObj(queue) ? queue.learnings : null)) if (isObj(l) && l.who === who && l.text) L.push({ t: toMs(l.d), text: clean(l.text, 190), src: clean(l.src || 'research/writeups', 90) });
  return (extra || []).concat(L);
}
const BOT_RE = { lit: /zlarior|\blit\b|mffu50k/i, atlas: /atlas|acctb/i, blitz: /blitz|acct_c/i };
const tailOf = (p) => p.id.split(':').pop();

function fScanner(p, I, now, f) {
  const id = tailOf(p), own = I['../money/' + id + '.json'], idx = I['../money/index.json'];
  const st = isObj(own) && own.id === id ? own : (isObj(idx) ? arr(idx.streams).find((x) => isObj(x) && x.id === id) : null);
  f.sources = [isObj(own) && own.id === id ? 'money/' + id + '.json' : 'money/index.json'];
  if (!st) { f.missing = true; f.doing = 'No file from my machine yet.'; f.blocked = 'money/' + id + '.json is not published (run RUN_MONEY.bat on the PC).'; return; }
  const last = toMs(st.asof) != null ? toMs(st.asof) : (num(st.age_min) != null ? now - st.age_min * 60000 : null), age = ageH(last, now), items = arr(st.items).filter(isObj);
  const head = isObj(st.headline) ? st.headline.text : st.headline, um = isObj(st.headline) && num(st.headline.usd_month) != null ? st.headline.usd_month : num(st.usd_month);
  f.asof = last; f.sample = st.status === 'sample';
  f.status = f.sample ? 'sample' : (st.status === 'error' || st.status === 'failed') ? 'failed' : st.status === 'stale' || (age != null && age > 36) ? 'stale' : age != null && age <= 6 ? 'working' : 'idle';
  f.doing = clean(head, 220) || (items.length ? 'Weighing the picks on my table.' : 'I looked and found nothing worth a card.');
  f.last = items.slice(0, 6).map((i) => out(last, clean(i.title, 90) + (num(i.usd) != null ? ': about ' + money(i.usd) + ' (an estimate)' : '') + (i.risk ? ', risk ' + clean(i.risk, 8) : '') + (i.expires ? ', ends ' + clean(i.expires, 10) : '')));
  f.details = items.slice(0, 6).map((i) => clean(i.detail, 220)).filter(Boolean);
  f.learned = learnedFrom(I['../ergasterion/queue.json'], id, arr(st.notes).slice(0, 4).map((t) => ({ t: last, text: clean(t, 190), src: f.sources[0] })));
  f.numbers.push(N2('Picks on the table', items.length));
  if (um != null) { f.numbers.push(N2('Estimate per month', money(um) + ' (an estimate, not a promise)')); f.metrics.usd_month = { label: 'estimate per month', v: um, text: money(um) }; }
  const best = items.slice().sort((a, b) => (num(b.score) || 0) - (num(a.score) || 0))[0];
  if (best) { f.numbers.push(N2('Top pick', clean(best.title, 70) + (num(best.usd) != null ? ', about ' + money(best.usd) + ' (an estimate)' : ''))); if (num(best.score) != null) { f.numbers.push(N2('Its score', best.score + ' of 100')); f.metrics.score = { label: 'best score', v: best.score, text: best.score + ' of 100' }; } }
  f.metrics.picks = { label: 'picks', v: items.length, text: String(items.length) };
  f.numbers.push(N2('Updated', agoText(last, now)));
  if (f.status === 'stale') f.blocked = 'My file is old (' + agoText(last, now) + '). Run RUN_MONEY.bat on the PC.';
  if (f.status === 'failed') f.blocked = 'My last scan failed.';
  f.risk = 'These are estimates from public data. Fees, rule changes and expiry dates can wipe out a pick.';
  f.mood = f.status === 'failed' ? 'sheepish' : f.status === 'stale' ? 'worried' : items.length && !f.sample ? 'proud' : items.length ? 'busy' : 'calm';
}

function fBot(p, I, now, f) {
  const id = tailOf(p), home = I['../home.json'], accts = isObj(home) ? arr(home.accounts).filter(isObj) : [];
  const a = accts.find((x) => BOT_RE[id].test(String(x.name || '') + ' ' + String(x.id || '') + ' ' + String(x.strategy || '')));
  f.sources = ['home.json'];
  f.learned = learnedFrom(I['../ergasterion/queue.json'], id, []);
  f.risk = 'Paper only. A losing streak can use up the drawdown; size follows the stop, so a wide stop means fewer micros.';
  if (!a) { f.missing = true; f.doing = 'I have no account in home.json yet.'; f.blocked = 'home.json has no account for me (the PC publishes it).'; return; }
  const ev = isObj(a.eval) ? a.eval : {}, pnl = isObj(a.pnl) ? a.pnl : {}, conn = isObj(a.conn) ? a.conn : {}, last = home.t != null ? toMs(home.t) : toMs(home.asof);
  const today = num(pnl.today) != null ? pnl.today : num(ev.today), paused = !!(a.paused || ev.paused);
  f.asof = last;
  f.status = conn.connected === false ? 'stale' : paused ? 'idle' : 'working';
  const dd = num(ev.room) != null && num(ev.mll) != null ? 'Drawdown left ' + money(ev.room) + ' of ' + money(ev.mll) + ' max loss' : '';
  f.doing = 'Paper account ' + clean(a.name || id, 30) + ': ' + (today != null ? moneyS(today) + ' today' : 'no P&L yet today') + (dd ? '. ' + dd : '') + (paused ? '. I am paused' : '') + '.';
  if (today != null) { f.numbers.push(N2('Today', moneyS(today))); f.metrics.today = { label: 'today', v: today, text: moneyS(today) }; }
  if (dd) { f.numbers.push(N2('Drawdown', dd)); f.metrics.room = { label: 'drawdown left', v: ev.room, text: money(ev.room) + ' of ' + money(ev.mll) + ' max loss' }; }
  if (num(pnl.week) != null) { f.numbers.push(N2('This week', moneyS(pnl.week))); f.metrics.week = { label: 'this week', v: pnl.week, text: moneyS(pnl.week) }; }
  if (num(ev.to_target) != null) f.numbers.push(N2('To the eval target', money(ev.to_target)));
  f.last.push(out(last, 'This session so far: ' + (today != null ? moneyS(today) : 'no P&L yet')));
  const tr = I['../odeon/trades.json'];
  if (id === 'lit' && isObj(tr)) {
    const T = arr(tr.trades).filter((t) => isObj(t) && num(t.usd) != null && typeof t.day === 'string').sort((x, y) => (x.day < y.day ? 1 : -1)).slice(0, 5);
    for (const t of T) f.last.push(out(toMs(t.day), 'Trade on ' + t.day + (t.side ? ', ' + clean(String(t.side).toLowerCase(), 6) : '') + ': ' + usdR(t.usd, t.r)));
    if (T.length) { f.numbers.push(N2('Last trade', usdR(T[0].usd, T[0].r) + ' on ' + T[0].day)); f.sources.push('odeon/trades.json'); }
  }
  f.numbers.push(N2('Updated', agoText(last, now)));
  if (conn.connected === false) f.blocked = 'I am not connected right now (NinjaTrader or the PC is off).';
  else if (num(ev.room) != null && num(ev.mll) != null && ev.room < ev.mll * 0.25) f.blocked = 'Not blocked, but close to the limit: ' + dd + '.';
  f.mood = conn.connected === false ? 'worried' : today != null && today > 0 ? 'proud' : today != null && today < 0 ? 'sheepish' : paused ? 'calm' : 'busy';
}

function fKalshi(p, I, now, f) {
  const k = I['../kalshi.json'], lr = I['../kalshicity/learned.json'];
  f.sources = ['kalshi.json'];
  f.learned = learnedFrom(I['../ergasterion/queue.json'], 'kalshi', []);
  if (isObj(lr)) {
    const src = isObj(lr.source) ? lr.source : {};
    if (num(src.bets) != null && num(src.total_pnl) != null) { f.learned.unshift({ t: toMs(src.generated_utc), text: 'Over ' + src.bets + ' settled paper bets my total is ' + moneyC(src.total_pnl) + ' after fees.', src: 'kalshicity/learned.json' }); f.sources.push('kalshicity/learned.json'); }
  }
  f.risk = 'Paper only. Prediction markets charge fees and most patterns vanish out of sample.';
  if (!isObj(k)) { f.missing = true; f.doing = 'My feed is not reachable.'; f.blocked = 'kalshi.json was not read (the PC publishes it).'; f.status = 'stale'; return; }
  const last = k.t != null ? toMs(k.t) : null, age = ageH(last, now), tr = arr(Array.isArray(k.last_trades) ? k.last_trades : k.trades).filter(isObj);
  f.asof = last;
  f.status = k.running === false ? 'failed' : age != null && age > 36 ? 'stale' : k.running ? 'working' : 'idle';
  f.doing = (k.running === false ? 'I am not running. ' : k.running ? 'Running on paper. ' : '') + (num(k.today_pnl) != null ? 'Today ' + moneyC(k.today_pnl) + '.' : 'No P&L today.');
  f.last = tr.slice(0, 5).map((x) => out(toMs(x.t != null ? x.t : x.ts), clean(x.title || x.ticker || x.market || 'trade', 70) + (num(x.pnl) != null ? ' ' + moneyC(x.pnl) : '')));
  if (num(k.today_pnl) != null) { f.numbers.push(N2('Today', moneyC(k.today_pnl))); f.metrics.today = { label: 'today', v: k.today_pnl, text: moneyC(k.today_pnl) }; }
  const sn = num(k.settled_n) != null ? k.settled_n : num(k.n_settled);
  if (sn != null) f.numbers.push(N2('Settled paper bets', sn));
  if (num(k.balance) != null) f.numbers.push(N2('Paper balance', moneyC(k.balance).replace('+', '')));
  f.numbers.push(N2('Updated', agoText(last, now)));
  if (k.running === false) f.blocked = 'I am not running: check the Oracle VM.';
  else if (f.status === 'stale') f.blocked = 'My feed is old (' + agoText(last, now) + ').';
  f.mood = k.running === false ? 'sheepish' : f.status === 'stale' ? 'worried' : num(k.today_pnl) > 0 ? 'proud' : num(k.today_pnl) < 0 ? 'sheepish' : 'busy';
}

function fMind(p, I, now, f) {
  const q = I['../ergasterion/queue.json'], m = isObj(q) && isObj(q.mind) ? q.mind : null;
  f.sources = [m && m.source ? clean(m.source, 80) : 'ergasterion/queue.json'];
  f.risk = 'My notes are context only. Similar-setup memory is not predictive out of sample.';
  if (!m) { f.missing = true; f.doing = 'I have no research file yet.'; f.blocked = 'ergasterion/queue.json has no Mind block (python tools/ergasterion_build.py).'; return; }
  const t = m.t ? toMs(m.t) : null, age = ageH(t, now), obs = arr(m.observations).filter(isObj);
  f.asof = t;
  f.status = age != null && age <= 48 ? 'working' : 'stale';
  f.doing = 'Nightly self-research: ' + (num(m.tested) || 0) + ' ideas tested so far. I only suggest; I never change a rule.';
  f.last = obs.slice(0, 6).map((o) => out(t, o.text));
  f.learned = learnedFrom(q, 'mind', [{ t: null, text: 'Similar-setup memory is context only: it is not predictive out of sample.', src: 'docs/CLAUDE_REFERENCE.md (Mind)' }]);
  f.numbers.push(N2('Ideas tested', num(m.tested) || 0)); f.numbers.push(N2('Notes on recent trades', obs.length)); f.numbers.push(N2('Last research', agoText(t, now)));
  f.metrics.tested = { label: 'ideas tested', v: num(m.tested) || 0, text: String(num(m.tested) || 0) };
  if (f.status === 'stale') f.blocked = 'My nightly run is overdue (last research ' + agoText(t, now) + '), or only the seed file is here.';
  f.mood = f.status === 'stale' ? 'worried' : obs.length ? 'busy' : 'calm';
}

function cronTasks(I) { const c = I['../cronos/status.json']; return isObj(c) && isObj(c.tasks) ? c.tasks : null; }
function fProm(p, I, now, f) {
  const fg = I['../prometheus/forge.json'], ct = cronTasks(I), mine = ct && isObj(ct.prometheus) ? ct.prometheus : null;
  f.sources = ['prometheus/forge.json'];
  f.learned = learnedFrom(I['../ergasterion/queue.json'], 'prometheus', []);
  f.risk = 'A setting that only wins on the months it was fitted on is not an edge. I check on later months for that reason.';
  if (!isObj(fg)) { f.missing = true; f.doing = 'I have no forge file yet.'; f.blocked = 'prometheus/forge.json is not published.'; return; }
  const last = toMs(fg.built), age = ageH(last, now), v = isObj(fg.verdict) ? fg.verdict : {}, hn = isObj(fg.honesty) ? fg.honesty : {};
  f.asof = last; f.sample = fg.demo === true;
  f.status = f.sample ? 'sample' : mine && mine.ok === false ? 'failed' : age != null && age > 8 * 24 ? 'stale' : 'idle';
  f.doing = 'I breed LIT settings: ' + (fg.gens_n || '?') + ' generations of ' + (fg.pop || '?') + ' candidates, fitted on Jan-Jun only, then checked on Jul-Oct. ' + (v.real_margin === false ? 'No real margin over live.' : v.real_margin ? 'One candidate holds a margin.' : '');
  if (num(v.h1_gain_pm) != null) { f.last.push(out(last, 'Best candidate: ' + moneyS(v.h1_gain_pm) + ' a month on the fit half, ' + moneyS(v.h2_gain_pm) + ' a month on the check half.')); f.numbers.push(N2('Best candidate, fit half', moneyS(v.h1_gain_pm) + ' a month')); f.numbers.push(N2('Best candidate, check half', moneyS(v.h2_gain_pm) + ' a month')); f.metrics.check = { label: 'check half, per month', v: v.h2_gain_pm, text: moneyS(v.h2_gain_pm) }; }
  if (num(hn.genomes_checked) != null) { f.last.push(out(last, num(hn.beat_live_both) + ' of ' + hn.genomes_checked + ' candidates beat live on both halves.')); f.numbers.push(N2('Beat live on both halves', num(hn.beat_live_both) + ' of ' + hn.genomes_checked)); f.learned.unshift({ t: last, text: 'Only ' + num(hn.beat_live_both) + ' of ' + hn.genomes_checked + ' bred candidates beat live LIT on both halves' + (v.real_margin === false ? '; no real margin, nothing to switch.' : '.'), src: 'prometheus/forge.json' }); }
  if (num(v.survive_pct) != null) f.numbers.push(N2('Fit gain that survived the check', v.survive_pct + '%'));
  f.numbers.push(N2('Built', agoText(last, now)));
  if (mine && mine.ok === false) f.blocked = 'My last run failed' + (mine.error ? ': ' + clean(mine.error, 80) : '.');
  f.mood = f.status === 'failed' ? 'sheepish' : v.real_margin ? 'proud' : v.real_margin === false ? 'sheepish' : 'calm';
}
function fHeph(p, I, now, f) {
  const d = I['../hephaestus/data.json'];
  f.sources = ['hephaestus/data.json'];
  f.learned = learnedFrom(I['../ergasterion/queue.json'], 'hephaestus', []);
  f.risk = 'Stored results are history. They say what happened in 2026, not what will happen.';
  if (!isObj(d)) { f.missing = true; f.doing = 'I have no results file yet.'; f.blocked = 'hephaestus/data.json is not published.'; return; }
  const last = toMs(d.built), age = ageH(last, now), dials = arr(d.dials).filter(isObj);
  f.asof = last; f.sample = d.demo === true;
  f.status = f.sample ? 'sample' : age != null && age > 30 * 24 ? 'stale' : 'idle';
  f.doing = 'I keep the stored result of every LIT setting that was really run, Jan-Jun against Jul-Oct. I never run the strategy and I change nothing.';
  f.last = dials.slice(0, 6).map((x) => out(last, 'Dial: ' + clean(x.label, 60) + ' (' + arr(x.options).length + ' settings stored)'));
  f.numbers.push(N2('Dials', dials.length)); f.numbers.push(N2('Stored', agoText(last, now)));
  f.metrics.dials = { label: 'dials', v: dials.length, text: String(dials.length) };
}
function fCron(p, I, now, f) {
  const c = cronTasks(I);
  f.sources = ['cronos/status.json'];
  f.learned = learnedFrom(I['../ergasterion/queue.json'], 'cronos', []);
  f.risk = 'If the PC is off at night the jobs do not run and every research page goes stale.';
  if (!c) { f.missing = true; f.doing = 'I have no job log yet.'; f.blocked = 'cronos/status.json is not published (the nightly jobs write it).'; return; }
  const rows = Object.keys(c).filter((k) => isObj(c[k])).map((k) => ({ k, e: c[k], t: toMs(c[k].last_run_t) })).sort((a, b) => (b.t || 0) - (a.t || 0));
  const failed = rows.filter((r) => r.e.ok === false), old = rows.filter((r) => r.e.ok !== false && r.t != null && ageH(r.t, now) > (r.e.cadence === 'weekly' ? 8 * 24 : 80));
  f.asof = rows.length ? rows[0].t : null;
  f.status = failed.length ? 'failed' : old.length ? 'stale' : rows.length ? 'working' : 'idle';
  const fine = rows.length - failed.length - old.length;
  f.doing = 'I run ' + rows.length + ' scheduled jobs: ' + fine + ' fine' + (old.length ? ', ' + old.length + ' overdue' : '') + (failed.length ? ', ' + failed.length + ' failed' : '') + '.';
  f.last = rows.slice(0, 6).map((r) => out(r.t, r.k + ': ' + (r.e.ok === false ? 'failed, ' + clean(r.e.error || 'no reason on file', 70) : 'ok') + (r.e.note && r.e.ok !== false ? ' (' + clean(r.e.note, 60) + ')' : '')));
  f.numbers.push(N2('Jobs', rows.length)); f.numbers.push(N2('Fine', fine)); f.numbers.push(N2('Overdue', old.length)); f.numbers.push(N2('Failed', failed.length)); f.numbers.push(N2('Newest run', agoText(f.asof, now)));
  f.metrics.failed = { label: 'failed jobs', v: failed.length, text: String(failed.length) };
  if (failed.length) f.blocked = 'Failed: ' + failed.map((r) => r.k).join(', ') + '.'; else if (old.length) f.blocked = 'Overdue: ' + old.map((r) => r.k).join(', ') + '.';
  f.mood = failed.length ? 'sheepish' : old.length ? 'worried' : rows.length ? 'proud' : 'calm';
}
function fQueue(p, I, now, f) {
  const qj = I['../ergasterion/queue.json'], q = isObj(qj) && isObj(qj.queue) ? qj.queue : null;
  f.sources = ['handoff/QUEUE.md (ergasterion/queue.json)'];
  f.risk = 'A task list is only as true as the last person who ticked it.';
  if (!q) { f.missing = true; f.doing = 'I have no queue file yet.'; f.blocked = 'ergasterion/queue.json is not published (python tools/ergasterion_build.py).'; return; }
  const tasks = arr(q.tasks).filter(isObj), last = toMs(qj.asof), wu = isObj(qj.writeups) ? qj.writeups : {}, rej = arr(qj.rejected).filter(isObj);
  f.asof = last; f.status = (num(q.open) || 0) > 0 ? 'working' : 'idle';
  f.doing = (num(q.open) || 0) + ' open task' + (q.open === 1 ? '' : 's') + ', ' + (num(q.done) || 0) + ' done.' + (tasks[0] ? ' Next: ' + clean(tasks[0].id, 40) + '.' : '');
  f.last = tasks.slice(0, 6).map((t) => out(last, clean(t.id, 30) + ': ' + clean(t.text, 110)));
  f.learned = rej.slice(0, 5).map((r) => ({ t: toMs(r.date), text: 'Tested and rejected: ' + clean(r.title, 120), src: clean(r.file, 90) }));
  f.numbers.push(N2('Open tasks', num(q.open) || 0)); f.numbers.push(N2('Done tasks', num(q.done) || 0));
  if (num(wu.count) != null) f.numbers.push(N2('Write-ups', wu.count));
  f.numbers.push(N2('Rejected ideas on file', rej.length)); f.numbers.push(N2('List as of', dayOf(last) || 'an unknown day'));
  f.metrics.open = { label: 'open tasks', v: num(q.open) || 0, text: String(num(q.open) || 0) };
  f.mood = (num(q.open) || 0) > 20 ? 'worried' : 'busy';
}

function fBuilder(p, I, now, f) {
  const bj = I['../ergasterion/builders.json'], qj = I['../ergasterion/queue.json'];
  const rows = Array.isArray(bj) ? bj : isObj(bj) ? arr(bj.builders || bj.agents || bj.people) : [];
  const short = p.id.split(':')[1] || '', b = rows.find((x) => isObj(x) && (String(x.branch || '').indexOf(short) >= 0 || String(x.id || '').indexOf(short) >= 0 || (p.agent && x.name === p.agent)));
  f.risk = 'My work is on a local branch until the lead merges it. Until then nothing of mine is on the site.';
  f.doing = (p.job ? 'My job: ' + clean(p.job, 150) + '.' : 'I am a build agent of this project.');
  f.status = 'idle';
  f.learned = learnedFrom(qj, 'dev', []).slice(0, 3);
  if (isObj(b)) {
    f.sources = ['ergasterion/builders.json'];
    const t = toMs(b.t != null ? b.t : b.last_t != null ? b.last_t : b.updated), commits = arr(b.commits).filter((c) => isObj(c) || typeof c === 'string');
    f.asof = t;
    if (typeof b.doing === 'string' && b.doing) f.doing = clean(b.doing, 200);
    for (const c of commits.slice(0, 5)) f.last.push(out(isObj(c) ? toMs(c.t) : t, 'Commit: ' + clean(isObj(c) ? c.s || c.subject || c.text : c, 110)));
    if (!f.last.length && (b.last || b.subject || b.s)) f.last.push(out(t, 'Commit: ' + clean(b.last || b.subject || b.s, 110)));
    const n = num(b.n) != null ? b.n : num(b.commits_n) != null ? b.commits_n : commits.length || null;
    if (n != null) { f.numbers.push(N2('Commits on my branch', n)); f.metrics.commits = { label: 'commits', v: n, text: String(n) }; }
    if (num(b.files) != null) f.numbers.push(N2('Files touched', b.files));
    for (const l of arr(b.learned).slice(0, 4)) f.learned.unshift({ t: toMs(isObj(l) ? l.d || l.t : null), text: clean(isObj(l) ? l.text : l, 190), src: 'ergasterion/builders.json' });
    if (typeof b.blocked === 'string' && b.blocked) f.blocked = clean(b.blocked, 160);
    const st = String(b.status || '').toLowerCase();
    f.status = STATUS_WORD[st] ? st : t != null && ageH(t, now) <= 6 ? 'working' : t != null && ageH(t, now) > 72 ? 'stale' : 'idle';
  } else if (isObj(p.git)) {
    f.sources = ['git (snapshot at build time)'];
    const t = toMs(p.git.t);
    f.asof = t; f.note = 'snapshot at build time';
    f.last.push(out(t, 'Commit: ' + clean(p.git.s, 110)));
    f.status = t != null && ageH(t, now) <= 6 ? 'working' : t != null && ageH(t, now) > 72 ? 'stale' : 'idle';
  } else { f.sources = ['handoff/agents_now.json']; f.note = 'I only have my job description on file: no commits were published with the site.'; }
  const lj = I['../ergasterion/lessons.json'];
  for (const l of arr(Array.isArray(lj) ? lj : isObj(lj) ? lj.lessons : null).filter(isObj)) {
    if (String(l.who || l.branch || '').indexOf(short) >= 0 || (p.agent && l.who === p.agent)) f.learned.unshift({ t: toMs(l.d || l.t), text: clean(l.text || l.lesson, 190), src: clean(l.src || 'ergasterion/lessons.json', 90) });
  }
  if (p.branch) f.numbers.push(N2('Branch', p.branch));
  if (f.asof != null) f.numbers.push(N2('Last commit', agoText(f.asof, now)));
  f.mood = f.blocked ? 'worried' : f.status === 'working' ? 'busy' : f.last.length ? 'proud' : 'calm';
}

function cardOf(j) { return isObj(j) && isObj(j.status) ? j : null; }
function fKeeper(p, I, now, f) {
  const apps = isObj(p.district) ? arr(p.district.apps) : [];
  f.risk = 'A status card is only as fresh as its last build. An old card can look fine and be wrong.';
  if (!apps.length) { f.doing = 'I keep this place. I only know what its own page shows you; I have no files of my own.'; f.status = 'idle'; f.sources = []; f.note = 'This keeper has no data file: ask the scene for details.'; return; }
  let ok = 0, warn = 0, off = 0, newest = null; const bad = [], seen = [];
  for (const a of apps) {
    const c = cardOf(I['../' + a + '/jarvis.json']);
    if (!c) continue;
    seen.push(a);
    const lv = c.status.level, t = toMs(c.t);
    if (t != null && (newest == null || t > newest)) newest = t;
    if (lv === 'ok') ok++; else if (lv === 'off') off++; else { warn++; bad.push(clean(c.name || a, 24) + ' (' + clean(c.status.label, 40) + ')'); }
    if (f.last.length < 6 && arr(c.lines)[0]) f.last.push(out(t, clean(c.name || a, 24) + ': ' + clean(c.lines[0], 110)));
  }
  f.sources = seen.slice(0, 6).map((a) => a + '/jarvis.json');
  if (!seen.length) { f.missing = true; f.doing = 'None of my apps has published a status card yet.'; f.blocked = 'No jarvis.json card was readable in my district.'; return; }
  f.asof = newest; f.status = warn ? 'stale' : ok ? 'working' : 'idle';
  f.doing = 'I look after the ' + clean(p.district.title, 20) + ' district: ' + seen.length + ' apps report in. ' + ok + ' fine, ' + warn + ' need a look, ' + off + ' showing demo or switched off.';
  f.numbers.push(N2('Apps reporting', seen.length)); f.numbers.push(N2('Fine', ok)); f.numbers.push(N2('Need a look', warn)); f.numbers.push(N2('Demo or off', off));
  f.metrics.warn = { label: 'apps that need a look', v: warn, text: String(warn) };
  if (bad.length) f.blocked = 'These need a look: ' + bad.slice(0, 4).join(', ') + '.';
  f.mood = warn ? 'worried' : ok ? 'proud' : 'calm';
}
function fVillager(p, I, now, f) {
  const c = cardOf(I[p.sources[0]]);
  f.sources = p.sources.map((s) => s.replace(/^\.\.\//, ''));
  f.risk = 'I only know what my app wrote on its own status card.';
  if (!c) { f.doing = 'I live in ' + clean(p.appName || p.app, 30) + (p.bio ? ': ' + p.bio : '.') + ' It has no status card I can read.'; f.status = 'idle'; f.note = 'No status card on file.'; return; }
  const t = toMs(c.t), lv = c.status.level;
  f.asof = t; f.status = lv === 'ok' ? 'working' : lv === 'off' ? 'sample' : lv === 'bad' ? 'failed' : 'stale'; f.sample = lv === 'off';
  f.doing = clean(c.name || p.app, 30) + ' says: ' + clean(c.status.label, 60) + '.' + (arr(c.lines)[0] ? ' ' + clean(c.lines[0], 130) : '');
  f.last = arr(c.lines).slice(0, 3).map((l) => out(t, l));
  for (const k of arr(c.kpis).filter(isObj).slice(0, 3)) f.numbers.push(N2(clean(k.label, 24), clean(k.value, 30)));
  if (lv === 'bad' || lv === 'warn') f.blocked = clean(c.status.label, 80);
  f.mood = lv === 'bad' ? 'sheepish' : lv === 'warn' ? 'worried' : lv === 'ok' ? 'proud' : 'calm';
}

const METRIC_WORD = { n: 'trades', tpw: 'trades a week', pf: 'profit factor', net: 'net', per_month: 'per month', p10: 'evals passed within ten sessions', f10: 'evals failed within ten sessions' };
function fChampion(p, I, now, f) {
  let run = isObj(p.run) ? p.run : null, live = false;
  const idx = I['../archive/index.json'];
  if (isObj(idx) && Array.isArray(idx.cols) && Array.isArray(idx.runs)) {
    const ix = {}; idx.cols.forEach((c, i) => { ix[c] = i; });
    const rid = p.id.split(':').slice(1).join(':'), row = idx.runs.find((r) => Array.isArray(r) && r[ix.id] === rid), mc = arr(idx.metric_cols), V = arr(idx.verdicts);
    const mm = (a) => { if (!Array.isArray(a)) return null; const o = {}; mc.forEach((k, i) => { if (num(a[i]) != null) o[k] = a[i]; }); return o; };
    if (row) { run = { id: rid, title: clean(row[ix.title], 120), family: clean(row[ix.family], 40), verdict: V[row[ix.verdict]] || '', status: String(row[ix.status] || ''), built: String(row[ix.built] || ''), m26: mm(row[ix.m26]), mold: mm(row[ix.mold]), note: clean(row[ix.note], 200) }; live = true; }
  }
  f.sources = [live ? 'archive/index.json' : 'archive/index.json (snapshot at build time)'];
  f.risk = 'History, not a forecast. Money figures are after costs, on stored data.';
  if (!run) { f.missing = true; f.doing = 'My run is not in the Archive index I can read.'; f.blocked = 'archive/index.json has no run with my id.'; return; }
  const a = isObj(run.m26) ? run.m26 : null, b = isObj(run.mold) ? run.mold : null, t = toMs(run.built);
  f.asof = t; f.note = live ? '' : 'snapshot at build time';
  f.status = 'idle';
  const rejected = run.verdict === 'rejected';
  f.doing = 'I am the run "' + clean(run.title, 110) + '" (' + clean(run.family, 30) + '). Verdict: ' + (run.verdict || 'none on file') + (run.status && run.status !== run.verdict ? ' (' + clean(run.status, 24) + ')' : '') + '.';
  const line = (m) => (num(m.n) != null ? m.n + ' trades' : '') + (num(m.tpw) != null ? ', ' + m.tpw + ' a week' : '') + (num(m.pf) != null ? ', profit factor ' + m.pf : '') + (num(m.net) != null ? ', net ' + moneyS(m.net) : '') + (num(m.per_month) != null ? ' (' + moneyS(m.per_month) + ' a month)' : '');
  if (a) {
    f.last.push(out(t, 'In 2026: ' + line(a) + '.'));
    for (const k of ['n', 'tpw', 'pf']) if (num(a[k]) != null) f.numbers.push(N2('2026 ' + METRIC_WORD[k], a[k]));
    if (num(a.net) != null) f.numbers.push(N2('2026 net', moneyS(a.net) + (num(a.per_month) != null ? ', ' + moneyS(a.per_month) + ' a month' : '')));
    if (num(a.p10) != null) f.numbers.push(N2('2026 evals passed within ten sessions', a.p10 + '%'));
    if (num(a.f10) != null) f.numbers.push(N2('2026 evals failed within ten sessions', a.f10 + '%'));
    for (const k of ['pf', 'per_month', 'tpw', 'p10', 'f10', 'net']) if (num(a[k]) != null) f.metrics[k] = { label: '2026 ' + METRIC_WORD[k], v: a[k], text: (k === 'net' || k === 'per_month' ? moneyS(a[k]) : a[k] + (k === 'p10' || k === 'f10' ? '%' : '')) };
  }
  if (b) {
    f.last.push(out(t, 'In the five years before: ' + line(b) + '.'));
    if (num(b.pf) != null) { f.numbers.push(N2('Earlier years, profit factor', b.pf)); f.metrics.pf_old = { label: 'earlier years, profit factor', v: b.pf, text: String(b.pf) }; }
    if (num(b.net) != null) f.numbers.push(N2('Earlier years, net', moneyS(b.net) + (num(b.per_month) != null ? ', ' + moneyS(b.per_month) + ' a month' : '')));
  } else f.last.push(out(t, 'I have no numbers for the years before 2026 on file.'));
  if (run.note) f.learned.push({ t, text: clean(run.note, 190), src: f.sources[0] });
  if (rejected) {
    const why = b && num(b.pf) != null && b.pf < 1.1 ? 'In the earlier years my profit factor was ' + b.pf + ': the gain did not hold outside 2026.' : 'I was rejected by the rule: a change must hold in 2026 and in the earlier years, and keep the trade count.';
    f.learned.unshift({ t, text: why, src: f.sources[0] }); f.failed = why;
  }
  f.numbers.push(N2('Stored on', dayOf(t) || 'an unknown day'));
  f.mood = rejected ? 'sheepish' : run.verdict === 'adopted' ? 'proud' : 'calm';
}

/** what this person can truthfully say right now. inputs = { '<relative url>': parsed json | null }. Never throws. */
export function buildFacts(person, inputs, now) {
  const p = person, f = blank(p), I0 = isObj(inputs) ? inputs : {};
  const run = (I) => {
    if (p.kind === 'scanner') fScanner(p, I, now, f);
    else if (p.kind === 'bot' && BOT_RE[tailOf(p)]) fBot(p, I, now, f);
    else if (p.id === 'bot:kalshi') fKalshi(p, I, now, f);
    else if (p.id === 'mind') fMind(p, I, now, f);
    else if (p.id === 'job:prometheus') fProm(p, I, now, f);
    else if (p.id === 'job:hephaestus') fHeph(p, I, now, f);
    else if (p.id === 'job:cronos') fCron(p, I, now, f);
    else if (p.id === 'job:queue') fQueue(p, I, now, f);
    else if (p.kind === 'builder') fBuilder(p, I, now, f);
    else if (p.kind === 'champion') fChampion(p, I, now, f);
    else if (p.kind === 'villager') fVillager(p, I, now, f);
    else fKeeper(p, I, now, f);
  };
  try {
    run(I0);
    if (f.missing && p.kind !== 'builder' && p.kind !== 'champion' && p.kind !== 'keeper' && p.kind !== 'villager') {      // nothing of its own: the labelled SAMPLE, so the person is never blank
      const keep = f.blocked, S = sampleInputs(now);
      Object.assign(f, blank(p)); run(S);
      f.sample = true; f.status = 'sample'; f.missing = true; f.blocked = keep; f.note = 'These are example numbers, not real: ' + keep;
      f.mood = 'calm';
    }
  } catch (e) { f.status = 'failed'; f.doing = 'I could not read my own file.'; f.blocked = 'My file is there but I could not read it.'; f.mood = 'sheepish'; }
  if (f.sample && !f.note) f.note = 'These are example numbers, not real.';
  f.last = f.last.slice(0, 6); f.learned = f.learned.slice(0, 8);
  if (!f.blocked) delete f.blocked;
  f.asof = f.asof == null ? null : new Date(f.asof).toISOString();
  return f;
}
/** extra facts a scene passes in (ctx.facts): they are shown as given, marked as coming from the scene */
export function mergeSceneFacts(f, extra) {
  if (!isObj(extra)) return f;
  const g = { ...f, last: f.last.slice(), learned: f.learned.slice(), numbers: f.numbers.slice(), sources: f.sources.slice() };
  if (typeof extra.doing === 'string' && extra.doing) g.doing = clean(extra.doing, 240);
  if (typeof extra.status === 'string' && STATUS_WORD[extra.status]) g.status = extra.status;
  if (typeof extra.blocked === 'string' && extra.blocked) g.blocked = clean(extra.blocked, 200);
  for (const x of arr(extra.last)) if (isObj(x) && x.text) g.last.unshift(out(toMs(x.t), x.text));
  for (const x of arr(extra.learned)) if (isObj(x) && x.text) g.learned.unshift({ t: toMs(x.t), text: clean(x.text, 190), src: clean(x.src || 'the scene', 80) });
  for (const x of arr(extra.numbers)) if (isObj(x) && x.label) g.numbers.unshift(N2(clean(x.label, 40), clean(x.text, 80)));
  if (extra.sample === true) { g.sample = true; g.status = 'sample'; }
  if (typeof extra.source === 'string') g.sources.unshift(clean(extra.source, 80));
  if (MOODS.indexOf(extra.mood) >= 0) g.mood = extra.mood;
  g.note = '';
  return g;
}
