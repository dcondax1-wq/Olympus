import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { DATASETS, loadDataset } from '../tools/web_public/cities/datasets.js';
import { generate, validateSpec } from '../tools/web_public/cities/generator.js';

const cfg = JSON.parse(await readFile(new URL('../tools/web_public/cities/cities.json', import.meta.url), 'utf8'));
const members = [
  ['atlas-ema-city', 'atlas_ema', 'EMA', 5],
  ['atlas-macd-city', 'atlas_macd', 'MACD', 5],
  ['atlas-sr-city', 'atlas_sr', 'S/R', 4],
];
const trade = (bot, strat, src, i, usd) => ({
  id: `${bot}-${strat}-${src}-${i}`, bot, strat, src, side: i % 2 ? 'LONG' : 'SHORT',
  day: `2026-10-${String(i + 1).padStart(2, '0')}`,
  entry: { t: 1790800000 + i * 86400 }, exit: { kind: usd < 0 ? 'STOP' : 'TIME' },
  usd, r: usd / 100, qty: 1, risk_pts: 20, risk_usd: 40,
});
const rows = members.flatMap(([, , strat, count]) => Array.from({ length: count }, (_, i) => trade('ATLAS', strat, 'backtest', i, i ? i * 100 : -100)));
rows.push(trade('ATLAS', 'EMA', 'paper', 7, 9999), trade('LIT', 'EMA', 'backtest', 8, 9999), trade('ATLAS', 'OTHER', 'backtest', 9, 9999));
const env = { fixture: {}, get: async () => ({ trades: rows }) }, cache = new Map();
const base = await loadDataset('trades', env, cache);
assert.equal(base.items.length, 17);

for (const [id, dataset, strategy, count] of members) {
  const spec = cfg.cities.find(s => s.id === id);
  assert.ok(spec && spec.dataset === dataset && !validateSpec(spec, DATASETS).length);
  assert.equal(spec.sky.kind, 'night', 'each ATLAS strategy has a true night skyline');
  assert.match(spec.motto, /Historical .* backtest/);
  const ds = await loadDataset(dataset, env, cache);
  assert.equal(ds.demo, false);
  assert.equal(ds.historical, true);
  assert.equal(ds.items.length, count);
  assert.match(ds.source, /backtest rows/);
  assert.equal(ds.fields.find(f => f.key === 'cum').label, 'Strategy backtest cumulative');
  assert.equal(ds.fields.find(f => f.key === 'dd').label, 'Strategy backtest drawdown');
  assert.ok(ds.items.every(it => it.f.bot === 'ATLAS' && it.f.strat === strategy && it.f.src === 'backtest'));
  assert.ok(ds.items.every(it => ds.label(it).includes('backtest')));
  // A filtered strategy starts its own equity/drawdown series, not the mixed Odeon curve.
  assert.equal(ds.items[0].f.cum, ds.items[0].f.usd);
  assert.equal(ds.items[0].f.idx, 1);
  assert.equal(ds.items.at(-1).f.cum, ds.items.reduce((n, it) => n + it.f.usd, 0));
  assert.equal(base.items.find(it => it.f.strat === strategy).f.cum === ds.items[0].f.cum, strategy === 'EMA');
  const city = generate(spec, ds);
  assert.equal(city.n, count);
  assert.equal(city.districts.reduce((n, d) => n + d.count, 0), count);
  const unavailable = await loadDataset(dataset, { fixture: {}, get: async () => ({ trades: [] }) }, new Map());
  assert.equal(unavailable.demo, true);
  assert.equal(unavailable.items.length, 0, 'no fabricated strategy sample');
  const empty = generate(spec, unavailable);
  assert.equal(empty.n, 0);
  assert.ok(Number.isFinite(empty.bounds.r));
  const withoutThisSetup = await loadDataset(dataset, { fixture: {}, get: async () => ({ trades: [trade('LIT', 'LIT', 'backtest', 1, 30)] }) }, new Map());
  assert.equal(withoutThisSetup.demo, false, 'a successful feed is not a missing feed');
  assert.equal(withoutThisSetup.items.length, 0, 'no fixture performance when the source has no setup rows');
}
// Exercise the checked-in Odeon research file too. Its history can grow, so
// derive expected membership from each row's independent source attributes.
const odeon = JSON.parse(await readFile(new URL('../tools/web_public/odeon/trades.json', import.meta.url), 'utf8'));
const published = { fixture: {}, get: async () => odeon }, publishedCache = new Map();
for (const [, dataset, strategy] of members) {
  const expected = odeon.trades.filter(row => row.bot === 'ATLAS' && row.strat === strategy && row.src === 'backtest');
  const actual = await loadDataset(dataset, published, publishedCache);
  assert.ok(expected.length > 0, `${strategy} has source-backed rows`);
  assert.deepEqual(actual.items.map(it => it.id).sort(), expected.map(row => row.id).sort());
  assert.ok(actual.items.every(it => it.f.src === 'backtest' && it.f.strat === strategy));
}
console.log('PASS: three isolated ATLAS backtest Cities and honest empty data.');
