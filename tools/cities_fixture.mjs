// Rebuilds tools/web_public/cities/fixture.json: a small deterministic sample of every dataset the Cities hub reads (real rows,
// strided out of the published files), plus clearly marked made-up rows for the two private feeds (Kalshi, the Obsidian vault).
// The page shows this sample (marked SAMPLE) whenever a live file does not answer.
//
//     node tools/cities_fixture.mjs            (Node 22+; read-only on the data files, writes only fixture.json)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), 'web_public', 'cities') + path.sep;
const { DATASETS, DATASET_IDS, loadDataset } = await import(PAGE + 'datasets.js');
const { rng } = await import(PAGE + 'util.js');
const env = { get: async (url) => { if (/^https?:/.test(url)) throw new Error('remote'); return JSON.parse(fs.readFileSync(path.resolve(PAGE, url), 'utf8')); }, fixture: {} };
const N = 44;
const out = {};
const round = (f) => Object.fromEntries(Object.entries(f).map(([k, v]) => [k, typeof v === 'number' ? Math.round(v * 1000) / 1000 : v]));
for (const id of DATASET_IDS) {
  const D = DATASETS[id];
  if (D.remote || D.vault) continue;
  const ds = await loadDataset(id, env);
  if (!ds.items.length) throw new Error('no data for ' + id);
  const step = ds.items.length / Math.min(N, ds.items.length);
  const items = [];
  for (let k = 0; k < Math.min(N, ds.items.length); k++) {
    const it = ds.items[Math.floor(k * step)];
    items.push({ id: it.id, label: String(ds.label(it)).slice(0, 90), f: round(it.f) });
  }
  out[id] = { note: `A small sample of ${D.source}: the full file did not answer.`, items };
}
// the two private feeds: made up, and said so
const r = rng(20261104);
const pick = (a) => a[Math.floor(r() * a.length)];
const kal = [];
for (let i = 0; i < 40; i++) {
  const asset = pick(['BTC', 'BTC', 'BTC', 'ETH', 'ETH', 'SOL', 'XRP', 'GOLD']), win = r() < 0.64, c = 1 + Math.floor(r() * 18), price = 0.55 + r() * 0.4;
  const pnl = win ? +(c * (1 - price)).toFixed(2) : -+(c * price).toFixed(2);
  kal.push({ id: `sample${i}`, label: `${asset} 15-minute market ${i + 1}`, f: { asset, side: r() < 0.55 ? 'yes' : 'no', state: i > 32 ? 'open' : 'settled', contracts: c, price: +price.toFixed(2),
    pnl, value: +(c * price).toFixed(2), strategy: pick(['15-min favourites', 'Late favourite', 'Gold 5 PM']), t: 1793000000 + i * 3600 } });
}
out.kalshi = { note: 'A made-up sample: the Kalshi feed did not answer, so these bets are not real.', items: kal };
const notes = [];
const FOLD = { Trading: ['LIT strategy', 'NY open playbook', 'Eval pass plan', 'Stop beyond the sweep', 'Weekly review', 'Risk of ruin', 'Killzones', 'Journal'], Goals: ['2027 goals', 'Q1 plan', 'Morning routine', 'Habit tracker', 'Vision board'],
  Health: ['Push day', 'Pull day', 'Leg day', 'Sleep 8 hours', 'Protein 180 g', 'Mobility'], Kalshi: ['Kalshi bot', 'BTC 15-minute markets', 'Edge log', 'Settlement rules'], Business: ['OLYMPUS', 'Jarvis roadmap', 'Pricing', 'Content plan', 'Tools stack'],
  Daily: ['2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01', '2026-11-02'] };
for (const [folder, names] of Object.entries(FOLD)) {
  names.forEach((nm, i) => notes.push({ id: `sample-${folder}-${i}`, label: nm, f: { kind: folder === 'Daily' ? 'daily' : 'note', folder, words: 80 + Math.floor(r() * 900), links: Math.floor(r() * 9), tags: Math.floor(r() * 4), age: Math.floor(r() * 60) } }));
}
out.notes = { note: 'A made-up sample: your vault is not connected on this phone (open Jarvis and connect Obsidian).', items: notes };
fs.writeFileSync(PAGE + 'fixture.json', JSON.stringify({ v: 1, ...out }));
console.log(Object.keys(out).length, 'datasets', fs.statSync(PAGE + 'fixture.json').size, 'bytes');
