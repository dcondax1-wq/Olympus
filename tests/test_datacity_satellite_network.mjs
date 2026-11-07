import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { decode } from '../tools/web_public/datacity/data.js';
import { layout } from '../tools/web_public/datacity/layout.js';
import { satellitePlan, SATELLITE_TOWNS } from '../tools/web_public/datacity/satellites.js';

const fixture = JSON.parse(fs.readFileSync('tools/web_public/datacity/fixture.json', 'utf8'));

test('the scenic network is deterministic, connected, and never adds research records', () => {
  const model = decode(structuredClone(fixture));
  const recordsBefore = model.buildings.length;
  const L = layout(model), again = satellitePlan(L.districts, L.plazaR);
  assert.equal(L.satellites.towns.length, SATELLITE_TOWNS);
  assert.equal(SATELLITE_TOWNS, 48);
  assert.equal(L.satellites.links.filter((x) => x.kind === 'ring').length, SATELLITE_TOWNS);
  assert.equal(L.satellites.links.filter((x) => x.kind === 'district').length, SATELLITE_TOWNS);
  assert.deepEqual(L.satellites.towns, again.towns);
  assert.ok(L.satellites.streets.every((s) => s.length === 4 && s.every(Number.isFinite)));
  assert.ok(L.satellites.towns.every((t) => Number.isFinite(t.x) && Number.isFinite(t.z) && t.radius <= L.worldRadius));
  assert.equal(model.buildings.length, recordsBefore);
  assert.ok(L.items.every((item) => !item.town && !String(item.b?.id || '').startsWith('satellite:')));
});

test('each quality tier keeps every town visible with a bounded tower count', () => {
  const source = fs.readFileSync('tools/web_public/datacity/caps.js', 'utf8').replace(/^export /gm, '');
  const caps = Function(source + '\nreturn PROFILES;')();
  for (const [name, perTown] of [['full',12],['phone',8],['lite',5]]) {
    assert.equal(caps[name].townTowers / SATELLITE_TOWNS, perTown, name);
    assert.ok(caps[name].townTowers <= 576, name);
  }
  const renderer = fs.readFileSync('tools/web_public/datacity/towns.js', 'utf8');
  assert.match(renderer, /new THREE\.InstancedMesh\(towerGeo\(4\)/);
  assert.match(renderer, /this\.mesh\.count = Math\.min\(this\.total, caps\?\.townTowers/);
  assert.match(renderer, /mesh\.userData\.decor = true/);
});

test('the city network switch remains in the WebGL view, readable fallback, and 2D map at phone width', () => {
  const index = fs.readFileSync('tools/web_public/datacity/index.html', 'utf8');
  const city = fs.readFileSync('tools/web_public/datacity/city.js', 'utf8');
  const map = fs.readFileSync('tools/web_public/datacity/map.html', 'utf8');
  for (const page of [index, city, map]) {
    assert.match(page, /CITY NETWORK/i);
    assert.match(page, /\/cities\//);
    assert.match(page, /\/datacity\//);
    assert.match(page, /\/kalshicity\//);
  }
  assert.match(index, /aria-current="page">DATA CITY/);
  assert.match(index, /@media\s*\(max-width:430px\)[\s\S]*?\.city-network/);
  assert.match(city, /if \(current\) link\.setAttribute\('aria-current', 'page'\)/);
  assert.match(map, /\/datacity\/" aria-current="page"/);
  assert.match(index, /\.city-network a\{[^}]*min-height:44px/);
  assert.match(index, /@media \(orientation:landscape\) and \(max-height:520px\)\{\s*:root\{--top-h:110px\}/);
  assert.match(city, /\.readable-city \.city-network a\{[^}]*min-height:44px/);
  assert.match(map, /\.city-network a\{[^}]*min-height:44px/);
});
