// Grows tools/web_public/cities/cities.json: the hand-made first 29 cities keep their entries (their continent and region are
// set here), and every slicing in SLICES below becomes one more city built from the SAME real datasets. Idempotent: a slice whose
// id exists is left alone, so running it twice changes nothing. Adding hundreds of cities = adding rows to SLICES.
//
//     node tools/cities_catalogue.mjs          (Node 22+; writes only cities.json)
//
// A row: [dataset, district_by, height_by, layout, extra?]. Names, mottos, landmark, sky, weather, sound, palette and scenery are
// derived deterministically from the row (hash of its id), so the catalogue never changes between runs.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), 'web_public', 'cities') + path.sep;
const { DATASETS } = await import(PAGE + 'datasets.js');
const { hash32 } = await import(PAGE + 'util.js');
const file = PAGE + 'cities.json';
const cfg = JSON.parse(fs.readFileSync(file, 'utf8'));

const NOUN = { trades: 'Trade', harbor: 'LIT', sessions: 'Day', months: 'Month', streaks: 'Streak', levels: 'Level', combos: 'Idea', vix: 'VIX Idea', tree: 'Tree', forge: 'Forge', gods: 'God',
  feeds: 'Feed', evals: 'Eval', evalspeed: 'Speed', arena: 'Arena', library: 'Library', workshop: 'Workshop', plans: 'Plan', kalshi: 'Kalshi', notes: 'Note' };
const CONT = { trades: 'trading', harbor: 'trading', sessions: 'trading', months: 'trading', streaks: 'trading', levels: 'trading', combos: 'research', vix: 'research', tree: 'research', forge: 'research',
  workshop: 'research', gods: 'research', feeds: 'research', evals: 'money', evalspeed: 'money', plans: 'money', kalshi: 'kalshi', arena: 'life', library: 'life', notes: 'obsidian' };
const REGION = { trades: 'Odeon reels', harbor: 'LIT replay', sessions: 'Trading days', months: 'Calendar', streaks: 'Streaks', levels: 'Liquidity levels', combos: 'Tested ideas', vix: 'Volatility', tree: 'Daphne',
  forge: 'Forge', workshop: 'Workshop', gods: 'Pantheon', feeds: 'Data feeds', evals: 'Simulated evals', evalspeed: 'Simulated evals', plans: 'Prop firms', kalshi: 'Kalshi bot', arena: 'Arena', library: 'Library', notes: 'The vault' };
const WORD = { month: 'Month', week: 'Week', weekday: 'Weekday', hour: 'Hour', year: 'Year', exit: 'Exit', side: 'Side', bot: 'Bot', src: 'Source', stopb: 'Stop band', qtyb: 'Size band', acct: 'Account', cls: 'Honesty',
  trig: 'Trigger', window: 'Window', dir: 'Direction', trend: 'Trend', district: 'Family', vix: 'VIX', root: 'Setup', level: 'Level', status: 'Status', depth: 'Depth', origin: 'Origin', gen: 'Generation', god: 'God',
  kind: 'Kind', outcome: 'Outcome', speed: 'Speed', scenario: 'Scenario', period: 'Period', plan: 'Plan', span: 'Span', asset: 'Asset', strategy: 'Strategy', state: 'State', folder: 'Folder', session: 'Session',
  family: 'Family', mon: 'Month', ok: 'Healthy', fast: 'Fast', pass: 'Passed', win: 'Win', now: 'On now', usd: 'Money', r: 'R', risk_pts: 'Risk', qty: 'Size', held_min: 'Hold', mfe_r: 'Best', mae_r: 'Pain',
  risk_usd: 'Risk $', n: 'Sample', e: 'Edge', e26: 'Edge 2026', eo: 'Edge 21-25', wr: 'Win rate', tpw: 'Pace', best: 'Best', worst: 'Worst', len: 'Length', excess: 'Excess', oos: 'Out of sample',
  fit: 'Fitness', pm_h2: '$ a month', pm_h1: '$ a month H1', pm_y: '$ a month 5y', pf_h2: 'PF', p10_h2: 'Pass 10', tpw_h2: 'Pace', days_on: 'Days on', pct: 'Share', runs: 'Runs', longest: 'Longest', rows: 'Rows',
  age: 'Age', days: 'Days', final: 'Final', low: 'Low', high: 'High', count: 'Count', cum: 'Cum', dd: 'Drawdown', xp: 'XP', links: 'Links', words: 'Words', shortw: 'Summary', per_month: 'Per month', net_6m: 'Net 6m',
  p10: 'Pass 10', price: 'Price', lost: 'Ruin', contracts: 'Contracts', pnl: 'Result', value: 'Value', net_h1: 'Net H1', net_h2: 'Net H2', f10_h2: 'Fail 10', winrate: 'Win rate', streak: 'Streak', plan_rr: 'Reward', nlev: 'Levels' };
const word = (e) => { const f = String(e).replace(/^-/, '').split(':').pop(); return WORD[f] || f; };

// [dataset, district_by, height_by, layout, extra]
const SLICES = [
  // ---- trading: the 60 reels
  ['trades', 'week', 'abs:usd', 'districts', { sort_by: 't' }], ['trades', 'weekday', 'abs:usd', 'districts'], ['trades', 'weekday', 'abs:r', 'clock'], ['trades', 'hour', 'abs:r', 'districts'],
  ['trades', 'hour', 'held_min', 'clock'], ['trades', 'hour', 'mfe_r', 'districts'], ['trades', 'side', 'abs:usd', 'districts'], ['trades', 'side', 'risk_pts', 'districts'], ['trades', 'bot', 'abs:usd', 'districts'],
  ['trades', 'bot', 'risk_pts', 'clock'], ['trades', 'src', 'abs:usd', 'districts'], ['trades', 'month', 'abs:r', 'districts', { sort_by: 't' }], ['trades', 'month', 'risk_pts', 'spiral'], ['trades', 'month', 'qty', 'districts'],
  ['trades', 'weekday', 'risk_pts', 'districts'], ['trades', 'weekday', 'held_min', 'clock'], ['trades', 'exit', 'held_min', 'clock'], ['trades', 'exit', 'risk_pts', 'districts'], ['trades', 'exit', 'mfe_r', 'districts'],
  ['trades', 'stopb', 'abs:r', 'districts'], ['trades', 'stopb', 'qty', 'clock'], ['trades', 'qtyb', 'abs:usd', 'districts'], ['trades', 'qtyb', 'mae_r', 'districts'], ['trades', 'acct', 'abs:r', 'clock'],
  ['trades', 'acct', 'held_min', 'districts'], ['trades', 'hour', 'qty', 'spiral'], ['trades', 'side', 'held_min', 'clock'],
  ['trades', 'weekday', 'abs:usd', 'calendar', { grid: { x: 'hour', z: 'weekday' }, tag: 'Hour x Weekday' }], ['trades', 'weekday', 'abs:r', 'calendar', { grid: { x: 'hour', z: 'weekday' }, tag: 'Hour x Weekday' }],
  ['trades', 'weekday', 'risk_pts', 'calendar', { grid: { x: 'hour', z: 'weekday' }, tag: 'Hour x Weekday' }],
  // ---- trading: the 631 LIT replay trades
  ['harbor', 'year', 'abs:usd', 'districts', { sort_by: 't' }], ['harbor', 'year', 'abs:r', 'clock'], ['harbor', 'month', 'abs:usd', 'districts', { sort_by: 't' }], ['harbor', 'weekday', 'abs:r', 'clock'],
  ['harbor', 'weekday', 'dd', 'districts'], ['harbor', 'exit', 'abs:usd', 'districts'], ['harbor', 'exit', 'abs:r', 'clock'], ['harbor', 'side', 'abs:usd', 'districts'], ['harbor', 'side', 'abs:r', 'districts'],
  ['harbor', 'year', 'abs:streak', 'spiral', { sort_by: 't' }], ['harbor', 'year', 'dd', 'terrain', { sort_by: 't', smooth: 1 }],
  ['harbor', 'weekday', 'abs:usd', 'calendar', { grid: { x: 'weekday', z: 'year' }, tag: 'Weekday x Year' }], ['harbor', 'weekday', 'abs:r', 'calendar', { grid: { x: 'weekday', z: 'year' }, tag: 'Weekday x Year' }],
  ['sessions', 'month', 'abs:usd', 'districts'], ['sessions', 'weekday', 'abs:usd', 'clock'], ['sessions', 'weekday', 'n', 'districts'], ['sessions', 'week', 'n', 'districts'], ['sessions', 'month', 'best', 'districts'],
  ['months', 'year', 'abs:r', 'districts'], ['months', 'mon', 'abs:usd', 'clock'], ['months', 'year', 'n', 'districts'], ['months', 'mon', 'winrate', 'clock'], ['months', 'year', 'winrate', 'districts'],
  ['streaks', 'year', 'len', 'districts'], ['streaks', 'kind', 'abs:usd', 'districts'], ['streaks', 'year', 'abs:usd', 'spiral'], ['streaks', 'kind', 'abs:worst', 'districts'],
  ['levels', 'session', 'abs:usd', 'districts'], ['levels', 'family', 'abs:r', 'districts', { district_order: 'size' }], ['levels', 'side', 'abs:usd', 'districts'], ['levels', 'hour', 'abs:usd', 'clock'], ['levels', 'level', 'abs:r', 'districts', { district_order: 'size' }],
  // ---- research: ideas, VIX, Daphne, the forge
  ['combos', 'window', 'abs:e', 'districts', { district_order: 'size' }], ['combos', 'dir', 'abs:e', 'districts'], ['combos', 'trend', 'abs:e', 'districts'], ['combos', 'district', 'abs:e26', 'districts', { district_order: 'size' }],
  ['combos', 'window', 'log:n', 'districts'], ['combos', 'trig', 'wr', 'districts', { district_order: 'size' }], ['combos', 'cls', 'abs:eo', 'districts'], ['combos', 'window', 'abs:eo', 'districts'],
  ['combos', 'trend', 'abs:e26', 'districts'], ['combos', 'district', 'wr', 'districts'], ['combos', 'cls', 'wr', 'districts'], ['combos', 'trig', 'log:n', 'districts', { district_order: 'size' }], ['combos', 'dir', 'abs:e26', 'spiral'],
  ['combos', 'district', 'tpw', 'districts'],
  ['vix', 'vix', 'abs:e26', 'districts'], ['vix', 'cls', 'abs:e', 'districts'], ['vix', 'window', 'abs:e', 'districts'], ['vix', 'dir', 'abs:e', 'districts'], ['vix', 'district', 'abs:e', 'districts'], ['vix', 'vix', 'log:n', 'clock'],
  ['tree', 'level', 'log:n', 'districts', { district_order: 'size' }], ['tree', 'status', 'log:n', 'districts'], ['tree', 'depth', 'abs:excess', 'districts'], ['tree', 'root', 'abs:excess', 'districts', { district_order: 'size' }],
  ['tree', 'level', 'abs:oos', 'districts'], ['tree', 'status', 'abs:oos', 'districts'], ['tree', 'root', 'abs:oos', 'districts', { district_order: 'size' }],
  ['forge', 'origin', 'pos:pm_h2', 'districts'], ['forge', 'gen', 'pf_h2', 'districts'], ['forge', 'gen', 'p10_h2', 'districts'], ['forge', 'origin', 'fit', 'clock'], ['forge', 'gen', 'tpw_h2', 'districts'], ['forge', 'origin', 'abs:pm_h1', 'districts'],
  ['forge', 'gen', 'pos:pm_y', 'districts'],
  ['workshop', 'kind', 'abs:net_h1', 'districts'], ['workshop', 'kind', 'pf_h2', 'districts'], ['workshop', 'kind', 'tpw_h2', 'districts'], ['workshop', 'kind', 'f10_h2', 'districts'],
  ['gods', 'god', 'pct', 'clock'], ['gods', 'god', 'runs', 'districts'], ['gods', 'god', 'longest', 'districts'], ['feeds', 'kind', 'age', 'districts'], ['feeds', 'ok', 'rows', 'districts'], ['feeds', 'kind', 'log:rows', 'clock'],
  // ---- money: simulated evals, prop-firm plans
  ['evals', 'outcome', 'days', 'districts'], ['evals', 'speed', 'abs:final', 'districts'], ['evals', 'outcome', 'abs:high', 'districts'], ['evals', 'speed', 'abs:low', 'districts'], ['evals', 'outcome', 'abs:low', 'terrain', { sort_by: 'final', smooth: 2 }],
  ['evals', 'pass', 'abs:final', 'spiral', { sort_by: 'days' }], ['evalspeed', 'bot', 'count', 'districts'], ['evalspeed', 'period', 'count', 'clock'], ['evalspeed', 'fast', 'count', 'districts'], ['evalspeed', 'scenario', 'cum', 'districts', { sort_by: 'session' }],
  ['plans', 'span', 'per_month', 'districts'], ['plans', 'plan', 'abs:net_6m', 'districts'], ['plans', 'span', 'p10', 'clock'], ['plans', 'plan', 'price', 'districts'], ['plans', 'plan', 'lost', 'districts'],
  // ---- kalshi
  ['kalshi', 'side', 'abs:pnl', 'districts'], ['kalshi', 'strategy', 'abs:pnl', 'districts'], ['kalshi', 'state', 'abs:value', 'districts'], ['kalshi', 'asset', 'contracts', 'clock'], ['kalshi', 'strategy', 'contracts', 'districts'],
  ['kalshi', 'side', 'price', 'districts'], ['kalshi', 'hour', 'abs:pnl', 'clock'], ['kalshi', 'asset', 'abs:value', 'districts'], ['kalshi', 'weekday', 'abs:pnl', 'clock'],
  ['kalshi', 'asset', 'abs:pnl', 'calendar', { grid: { x: 'hour', z: 'asset' }, tag: 'Hour x Asset' }],
  // ---- life + the vault
  ['arena', 'week', 'sqrt:xp', 'districts', { sort_by: 't' }], ['arena', 'src', 'sqrt:xp', 'districts'], ['arena', 'kind', 'xp', 'clock', { district_order: 'size' }],
  ['library', 'kind', 'links', 'districts'], ['library', 'kind', 'shortw', 'clock'], ['library', 'kind', 'tags', 'districts'],
  ['notes', 'kind', 'sqrt:words', 'districts'], ['notes', 'folder', 'links', 'districts'], ['notes', 'kind', 'links', 'clock'], ['notes', 'folder', 'age', 'districts'],
];

const LANDMARKS = ['obelisk', 'beacon', 'ring', 'pyramid', 'dome', 'tree', 'anvil', 'crown', 'gate', 'crystal', 'helix', 'wheel', 'monolith', 'lighthouse'];
const SKIES = ['night', 'dusk', 'dawn', 'day', 'storm', 'void', 'aurora', 'ember'];
const WEATHERS = ['clear', 'rain', 'snow', 'embers', 'fireflies', 'dust', 'fog', 'storm', 'stars'];
const SOUNDS = ['tick', 'tap', 'portal', 'thunder', 'rankup', 'pad'];
const SCENERY = ['river', 'harbor', 'rail'];
const GREEK = ['Aegis', 'Borea', 'Cinder', 'Delta', 'Ember', 'Fjord', 'Glint', 'Harbor', 'Ion', 'Jade', 'Kestrel', 'Lumen', 'Mirage', 'Nova', 'Onyx', 'Prism'];

function hsl(h, s, l) {
  h = ((h % 360) + 360) % 360; s /= 100; l /= 100;
  const k = (n) => (n + h / 30) % 12, a = s * Math.min(l, 1 - l), f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return '#' + [f(0), f(8), f(4)].map((v) => Math.round(v * 255).toString(16).padStart(2, '0')).join('');
}
const palette = (h) => ({
  up: hsl(150 + (h % 20), 80, 56), down: hsl(352 - (h % 14), 85, 62), low: hsl(h - 25, 70, 30), mid: hsl(h + 5, 85, 52), high: hsl(h + 38, 95, 72), accent: hsl(h, 92, 62), ground: hsl(h, 45, 5), fog: hsl(h, 50, 7),
  districts: Array.from({ length: 8 }, (_, i) => hsl(h + i * 47 + (i % 2) * 8, 78 + (i % 3) * 6, 58 + (i % 4) * 3)),
});
const SKY = {
  night: (h) => ({ kind: 'night', top: hsl(h, 55, 3), mid: hsl(h, 55, 10), low: hsl(h + 15, 60, 24), stars: 0.9 }),
  dusk: (h) => ({ kind: 'dusk', top: hsl(h + 200, 40, 9), mid: hsl(h + 330, 55, 28), low: hsl(h + 15, 90, 58), stars: 0.35 }),
  dawn: (h) => ({ kind: 'dawn', top: hsl(h + 210, 45, 14), mid: hsl(h + 20, 60, 44), low: hsl(h + 30, 90, 74), stars: 0.2 }),
  day: (h) => ({ kind: 'day', top: hsl(214, 62, 44), mid: hsl(204, 66, 66), low: hsl(h, 55, 84), stars: 0 }),
  storm: (h) => ({ kind: 'storm', top: hsl(h, 20, 5), mid: hsl(h, 22, 14), low: hsl(h, 25, 26), stars: 0.1 }),
  void: (h) => ({ kind: 'void', top: hsl(h + 20, 70, 2), mid: hsl(h, 70, 8), low: hsl(h - 30, 80, 20), stars: 1 }),
  aurora: (h) => ({ kind: 'aurora', top: hsl(h + 240, 50, 3), mid: hsl(h + 200, 55, 9), low: hsl(h + 160, 60, 20), stars: 0.85 }),
  ember: (h) => ({ kind: 'ember', top: hsl(h, 50, 4), mid: hsl(18, 70, 16), low: hsl(24, 90, 40), stars: 0.3 }),
};

// the first 29: their continent, region and scenery
const old = new Map(cfg.cities.map((c) => [c.id, c]));
for (const c of cfg.cities) {
  c.group = CONT[c.dataset]; c.region = REGION[c.dataset];
  if (!c.scenery) c.scenery = SCENERY[hash32('scene:' + c.id) % 3];
}
const have = new Set(cfg.cities.map((c) => c.id));
const sigs = new Set(cfg.cities.map((c) => [c.dataset, c.district_by, c.height_by, c.layout].join('|')));
const names = new Set(cfg.cities.map((c) => c.name)), lms = new Set(cfg.cities.map((c) => c.landmark.label)), accents = new Set(cfg.cities.map((c) => c.palette.accent));
const mottos = new Set(cfg.cities.map((c) => c.motto));
let added = 0;
for (const [ds, dist, height, layout, ex = {}] of SLICES) {
  const sig = [ds, dist, height, layout].join('|');
  if (sigs.has(sig)) continue;
  const D = DATASETS[ds], fm = Object.fromEntries(D.fields.map((f) => [f.key, f]));
  const hf = String(height).replace(/^-/, '').split(':').pop(), df = dist;
  if (!fm[hf] || !fm[df]) throw new Error(`bad slice ${sig}`);
  const id = `${ds}-${df}-${hf}-${layout}`.replace(/_/g, '').toLowerCase();
  if (have.has(id)) continue;
  const h = hash32(id);
  const seed = h % 360;
  let hue = (cfg.cities.length * 137.508 + seed * 0.37) % 360, acc = palette(hue);
  while (accents.has(acc.accent)) { hue += 3; acc = palette(hue); }
  const tag = ex.tag || word(df);
  let name = `${NOUN[ds]} ${word(height)} · ${tag}`;
  if (name.length > 28) name = `${NOUN[ds]} ${word(height)} · ${tag}`.slice(0, 28);
  let n = 2; while (names.has(name)) name = `${name.slice(0, 24)} #${n++}`;
  let motto = `${D.title}: towers tall by ${String(fm[hf].label).toLowerCase()}, grouped by ${String(fm[df].label).toLowerCase()}.`.slice(0, 90);
  if (mottos.has(motto)) motto = (motto.slice(0, 80) + ` (${layout})`).slice(0, 90);
  mottos.add(motto);
  const kind = LANDMARKS[(h >>> 3) % LANDMARKS.length], sky = SKIES[(h >>> 7) % SKIES.length], weather = WEATHERS[(h >>> 11) % WEATHERS.length];
  let label = `The ${GREEK[(h >>> 5) % GREEK.length]} ${kind[0].toUpperCase() + kind.slice(1)}`;
  n = 2; while (lms.has(label)) label = `${label.replace(/ #\d+$/, '')} #${n++}`;
  const numericDistrict = ['numeric'].includes('x');
  void numericDistrict;
  const cities = {
    id, name, motto, group: CONT[ds], region: REGION[ds], dataset: ds, layout, district_by: df, height_by: height,
    glow_by: ['win', 'pass', 'fdr', 'champion', 'best', 'now', 'ok', 'fast'].find((k) => fm[k]) ? ['win', 'pass', 'fdr', 'champion', 'best', 'now', 'ok', 'fast'].find((k) => fm[k]) : String(height).replace(/^-/, ''),
    window_by: `rank:${hf}`, color_by: layout === 'terrain' ? `ramp:${hf}` : fm.usd && ds !== 'sessions' ? 'sign:usd' : (D.fields.find((f) => f.key === 'pnl') ? 'sign:pnl' : 'district'),
    ...ex, palette: acc, landmark: { kind, at: 'front', label }, sky: SKY[sky](hue), weather, sound: SOUNDS[(h >>> 14) % SOUNDS.length],
    scenery: SCENERY[(h >>> 17) % 3],
    card: D.fields.filter((f) => f.key !== hf && f.key !== df && f.key !== 't').slice(0, 5).map((f) => f.key).concat([hf]).filter((v, i, a) => a.indexOf(v) === i).slice(0, 6),
  };
  delete cities.tag;
  if (layout === 'calendar' && !cities.grid) throw new Error('calendar needs a grid ' + id);
  if (cities.color_by === 'sign:usd' && !fm.usd) cities.color_by = 'district';
  if (layout === 'terrain' || layout === 'spiral') cities.arrange = 'grid';
  else cities.arrange = 'peak';
  if (ex.district_order === undefined && layout !== 'calendar') cities.district_order = 'key';
  cities.height_range = ds === 'combos' || ds === 'tree' || ds === 'vix' ? [2, 62] : [3, 70];
  sigs.add(sig); names.add(name); lms.add(label); accents.add(acc.accent); have.add(id);
  cfg.cities.push(cities); added++;
}
void old;
cfg.note = 'City specs of the Cities hub. Add a city = add one entry (or one row in tools/cities_catalogue.mjs); the generator and the tests need nothing else.';
fs.writeFileSync(file, JSON.stringify(cfg, null, 1) + '\n');
console.log(cfg.cities.length, 'cities (+' + added + ')', fs.statSync(file).size, 'bytes');
