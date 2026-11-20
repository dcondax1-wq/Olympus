import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const app = await readFile(new URL('../tools/web_public/cities/app.js', import.meta.url), 'utf8');
const page = await readFile(new URL('../tools/web_public/cities/index.html', import.meta.url), 'utf8');
const start = app.indexOf("function openNetworkApps() {");
const end = app.indexOf("\nfunction syncNetwork()", start);
assert.ok(start >= 0 && end > start, 'City Network renderer is present');
const source = app.slice(start, end);

const links = [...source.matchAll(/\['([^']+)',\s*'([^']+)',\s*'([^']+)'(?:,\s*(true))?\]/g)]
  .map(([, label, detail, href, current]) => ({ label, detail, href, current: current === 'true' }));
assert.deepEqual(links.map(({ label, href }) => [label, href]), [
  ['Cities', './'],
  ['Data City', '../datacity/'],
  ['Kalshi City', '../kalshicity/'],
  ['Oracle', '../oracle/'],
  ['Atlas Hub', '../atlas/'],
]);
assert.equal(links.filter((link) => link.current).length, 1, 'only Cities is the current destination');
assert.ok(links.every((link) => link.href.startsWith('./') || link.href.startsWith('../')), 'all routes are project-relative');
assert.doesNotMatch(source, /https?:|iframe|blitz|atlas strategy/i);
assert.match(source, /aria-label', 'Verified city destinations'/);
assert.match(source, /aria-current', 'page'/);
assert.match(page, /id="networkApps"[^>]+aria-label="Open City Network"[^>]*>CITY<\/button>/);
assert.match(page, /city-network-grid/);
assert.match(page, /app\.js\?v=[\w.-]+/);

console.log('PASS: compact City Network exposes only the five verified project-relative destinations.');
