import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const city = fs.readFileSync('tools/web_public/datacity/city.js', 'utf8');
const helperStart = city.indexOf('function failCity(');
const helperEnd = city.indexOf('\n\n/** A usable, read-only data view', helperStart);
assert.ok(helperStart > 0 && helperEnd > helperStart);
const { failCity, watchContextLoss } = vm.runInNewContext(city.slice(helperStart, helperEnd) + '\n({ failCity, watchContextLoss })');

test('WebGL loss shows one readable fallback and marks the renderer stopped', () => {
  const listeners = new Map();
  const canvas = { addEventListener(name, fn) { listeners.set(name, fn); } };
  const app = {};
  const reasons = [];
  watchContextLoss(canvas, app, (reason) => reasons.push(reason.message));
  assert.equal(typeof listeners.get('webglcontextlost'), 'function');
  let prevented = 0;
  const event = { preventDefault() { prevented++; } };
  listeners.get('webglcontextlost')(event);
  listeners.get('webglcontextlost')(event);
  assert.equal(prevented, 2);
  assert.equal(app.contextLost, true);
  assert.deepEqual(reasons, ['WebGL context lost']);
});

test('one queued animation frame does not render or schedule another after loss', () => {
  const start = city.indexOf('  start() {\n');
  const end = city.indexOf('\n  }\n}', start);
  assert.ok(start > 0 && end > start);
  const scheduled = [];
  const context = {
    performance: { now: () => 0 },
    requestAnimationFrame: (fn) => scheduled.push(fn),
    location: { hash: '#keep' },
    P: { has: () => true },
    O: null,
    document: { hidden: false },
  };
  const method = vm.runInNewContext('({' + city.slice(start, end + 4) + '})', context).start;
  let renders = 0;
  const app = {
    contextLost: false, route() {}, checkGold() {},
    city: { render() { renders++; } },
  };
  method.call(app);
  assert.equal(scheduled.length, 1);
  app.contextLost = true;
  scheduled.shift()(16);
  assert.equal(scheduled.length, 0);
  assert.equal(renders, 0);
});

test('a render exception uses the same fallback and stops the next queued frame', () => {
  const start = city.indexOf('  start() {\n');
  const end = city.indexOf('\n  }\n}', start);
  const scheduled = [];
  const context = {
    performance: { now: () => 0 },
    requestAnimationFrame: (fn) => scheduled.push(fn),
    location: { hash: '#keep' },
    P: { has: () => true },
    O: null,
    document: { hidden: false },
  };
  const method = vm.runInNewContext('({' + city.slice(start, end + 4) + '})', context).start;
  const reasons = [];
  let renders = 0;
  const app = {
    contextLost: false, calm: true, quality: 'hq',
    route() {}, checkGold() {}, stepFlashes() {}, stepTimeline() {}, updateCam() {},
    orbit: { update() {} },
    city: { render() { renders++; throw new Error('GPU frame failed'); } },
    onRenderFailure(reason) { failCity(this, (error) => reasons.push(error.message), reason); },
  };
  method.call(app);
  scheduled.shift()(40);
  assert.equal(renders, 1);
  assert.deepEqual(reasons, ['GPU frame failed']);
  assert.equal(app.contextLost, true);
  assert.equal(scheduled.length, 1);
  scheduled.shift()(80);
  assert.equal(scheduled.length, 0);
  assert.equal(renders, 1);
});

test('cached clients fetch the context-loss handler', () => {
  const index = fs.readFileSync('tools/web_public/datacity/index.html', 'utf8');
  assert.ok(index.includes('city.js?v=dccontext1'));
});
