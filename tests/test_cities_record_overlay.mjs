import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const src = readFileSync(new URL('../tools/web_public/cities/app.js', import.meta.url), 'utf8');
const code = src.match(/function celebrate\(k, auto\) \{[\s\S]*?\n\}\n\n\/\/ ambient sound/)?.[0]?.replace(/\n\n\/\/ ambient sound$/, '');
assert.ok(code, 'record celebration must remain present');

const calls = { fireworks: 0, sparkle: 0, toast: 0, sound: 0 };
const S = { cur: {
  city: { n: 1, x: [0], h: [20], z: [0], item: [0] },
  spec: { palette: { accent: '#ffcf5a' } },
  ds: { items: [{ id: 'source record' }], label: () => 'source record' },
}, stage: { fireworks: () => calls.fireworks++, project: () => ({ x: 200, y: 100, on: true }) } };
const win = { OLYMPUS_FX: { sparkleBurst: () => calls.sparkle++, toast: () => calls.toast++ } };
const celebrate = new Function('S', 'window', 'canvas', 'reduced', 'sfx', 'document', `${code}; return celebrate;`)(
  S, win, { clientWidth: 390, clientHeight: 844 }, () => false, () => calls.sound++, {},
);
celebrate(0, true);
assert.equal(calls.fireworks, 1);
assert.equal(calls.sparkle, 1);
assert.equal(calls.toast, 0, 'automatic record effects must not cover the phone minimap');
assert.equal(calls.sound, 0, 'automatic entry remains quiet');
celebrate(0, false);
assert.equal(calls.fireworks, 2);
assert.equal(calls.sparkle, 2);
assert.equal(calls.sound, 1, 'explicit interaction retains the rank-up sound');
console.log('Cities record celebration clears minimap: PASS');
