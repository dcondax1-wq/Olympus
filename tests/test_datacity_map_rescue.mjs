import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const city = fs.readFileSync('tools/web_public/datacity/city.js', 'utf8');
const index = fs.readFileSync('tools/web_public/datacity/index.html', 'utf8');
const map = fs.readFileSync('tools/web_public/datacity/map.html', 'utf8');

test('readable fallback keeps its own map link visible when the camera rail is hidden', () => {
  const fallback = city.slice(city.indexOf('function readableFallback('), city.indexOf('\nasync function main()'));
  const hidden = fallback.match(/\.data-fallback #c,[^}]*\{display:none!important\}/)?.[0];
  assert.ok(hidden, 'fallback hides 3D-only controls');
  assert.match(hidden, /\.data-fallback \.cams/);
  assert.doesNotMatch(hidden, /\.readable-city|\.map-link/);
  assert.match(fallback, /const mapLink = add\(root, 'a', 'Open the 2D map', 'map-link'\)/);
  assert.match(fallback, /mapLink\.href = demo \? '\.\/map\.html\?demo=1' : '\.\/map\.html'/);
  assert.match(fallback, /\.readable-city \.map-link\{display:inline-flex;min-height:44px/);
  assert.match(fallback, /document\.body\.append\(root\)/);
});

test('the map remains reachable if the 3D module never loads', () => {
  assert.match(index, /id="loading"[^>]*><span>BUILDING THE CITY[^<]*<\/span><a href="\.\/map\.html">Open 2D map<\/a>/);
  assert.match(index, /\.loading a\{pointer-events:auto;display:inline-flex;min-height:44px/);
  assert.match(index, /city\.js\?v=dcmaprescue1/);
});

test('the standalone page identifies 2D mode and has a clear return', () => {
  assert.match(map, /DATA CITY · 2D MAP VIEW/);
  assert.match(map, /id="back3d">Try 3D city/);
  assert.doesNotMatch(map, /type=["']module|three\.module|import\s+.*from/);
});
