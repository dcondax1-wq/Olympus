#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = fs.existsSync('tools/web_public/datacity') ? 'tools/web_public/datacity' : 'datacity';
const read = (name) => fs.readFileSync(path.join(root, name), 'utf8');

const formsSource = read('districtform.js');
const forms = await import('data:text/javascript;base64,' + Buffer.from(formsSource).toString('base64'));

// The skyline must have clear peaks and valleys rather than one random-height ring.
const samples = Array.from({ length: 280 }, (_, i) => forms.skylineForm(i / 280 * Math.PI * 2, 0.34, 0.82));
const heights = samples.map((s) => s.height);
assert.ok(Math.max(...heights) > 72, 'small-city crowns should be visible from the grand camera');
assert.ok(Math.max(...heights) - Math.min(...heights) > 50, 'outer skyline should form distinct clusters');
assert.ok(samples.some((s) => s.cluster > 0.95), 'cluster centers should exist');

const planned = forms.boulevardPlan(180, (x) => x > 175, 192);
assert.ok(planned.length > 150 && planned.length < 192, 'boulevard planning should preserve most of the ring and honor clearance');
assert.ok(planned.every((s) => s.length > 0 && Number.isFinite(s.angle)), 'boulevard segments must be usable transforms');

const outskirts = read('outskirts.js');
assert.match(outskirts, /skylineForm\(a, t, seed\)/, 'outskirts should use clustered skyline composition');
assert.match(outskirts, /R0 \+ 48, R0 \+ 124/, 'two connected orbital boulevards should surround the small cities');
assert.match(outskirts, /this\.boulevards\[1\]\.visible = q === 'hq'/, 'LITE must omit the second expensive boulevard');

const scene = read('scene.js');
assert.match(scene, /CylinderGeometry\(2\.4, 5\.4, 72/, 'central HQ should be the dominant capital tower');
assert.match(scene, /CITY CAPITAL/, 'capital label must remain explicit');
assert.match(scene, /outskirts\.js\?v=dcgfx2/, 'updated outskirts must bypass stale module caches');

const city = read('city.js');
assert.match(city, /scene\.js\?v=dcgfx2/, 'updated city scene must bypass stale module caches');
assert.match(city, /for \(let i = 0; i < 28; i\+\+\)/, 'no-WebGL recovery should retain a dense connected-city visual');
assert.match(city, /fallback-hq/, 'no-WebGL recovery should retain the central Data HQ');

const index = read('index.html');
assert.match(index, /city\.js\?v=dcgfx3/, 'updated city entry must bypass stale page caches');

const map = read('map.html');
assert.match(map, /class="hq"/, 'fallback needs a visible central HQ');
assert.match(map, /for \(let i = 0; i < 36; i\+\+\)/, 'fallback needs a dense ring of small-city clusters');
assert.match(map, /button\.addEventListener\('click'/, 'district switching must remain interactive');
assert.match(map, /aria-pressed/, 'district switching must expose selected state');
assert.doesNotMatch(map, /arm|order submit|place trade/i, 'map remains a read-only research surface');

console.log('Data City skyline checks passed: clustered outskirts, capital HQ, orbit roads, fallback towns, district switching.');
