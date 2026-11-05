// Status from a saved Kalshi feed is a timestamped observation, not a perpetual bot state.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../tools/web_public/kalshi/kalshi.js', import.meta.url), 'utf8');
const fn = source.match(/const stateOf = \(k\) => \{[\s\S]*?\n  \};/)?.[0];
assert.ok(fn, 'Kalshi stateOf is present');
const now = 1800000000;
const ctx = { parseT: (v) => typeof v === 'number' ? v : null, nowS: () => now, STALE_S: 15 * 60 };
vm.runInNewContext(fn + '\nthis.stateOf = stateOf;', ctx);
const state = (v) => Array.from(ctx.stateOf(v));
assert.deepEqual(state({ t: now - 60, running: false, status: 'Paused' }), ['warn', 'Paused']);
assert.deepEqual(state({ t: now - 60, running: true, status: 'Running' }), ['ok', 'Running']);
assert.deepEqual(state({ t: now - 901, running: false, status: 'Paused' }), ['warn', 'Not updating']);
assert.deepEqual(state({ t: now - 901, running: true, status: 'Running' }), ['warn', 'Not updating']);
assert.deepEqual(state({ t: null, running: false, status: 'Paused' }), ['warn', 'Not updating']);
assert.deepEqual(state({ t: now - 60, status: 'Running' }), ['warn', 'Status unverified']);
assert.deepEqual(state({ t: now + 301, running: true, status: 'Running' }), ['warn', 'Not updating']);
console.log('Kalshi status freshness: PASS');
