import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync('tools/web_public/pantheon/pantheon.js', 'utf8');
const page = fs.readFileSync('tools/web_public/pantheon/index.html', 'utf8');
const begin = source.indexOf('function recoverHall(');
const end = source.indexOf('\nasync function main()', begin);
assert.ok(begin >= 0 && end > begin);
function harness(throws = false) {
  const calls = [], STATE = { d: { gods: [] }, hall: { frame() { if (throws) throw Error('GPU frame failed'); } }, errors: [] };
  const context = { STATE, renderNoGl: (d) => calls.push(d), O: { ready() { calls.push('ready'); }, frameGap: () => 0, hidden: () => false }, document: { hidden: false }, requestAnimationFrame: () => calls.push('next') };
  const funcs = vm.runInNewContext(source.slice(begin, end) + '\n({ recoverHall, watchHallCanvas, tick })', context);
  return { ...funcs, STATE, calls };
}
test('a lost GPU context opens the independent data controls only once', () => {
  const h = harness();
  let prevented = 0;
  h.recoverHall('WebGL lost', { preventDefault() { prevented++; } });
  h.recoverHall('WebGL lost', { preventDefault() { prevented++; } });
  assert.equal(prevented, 2);
  assert.equal(h.STATE.hall, null);
  assert.deepEqual(h.calls, [h.STATE.d, 'ready']);
  assert.equal(h.STATE.errors.length, 1);
});
test('a thrown render falls back and the next animation frame continues', () => {
  const h = harness(true);
  h.tick(16);
  assert.equal(h.STATE.hall, null);
  assert.match(h.STATE.errors[0], /GPU frame failed/);
  assert.deepEqual(h.calls, [h.STATE.d, 'ready', 'next']);
  h.tick(32);
  assert.deepEqual(h.calls, [h.STATE.d, 'ready', 'next', 'next']);
});
test('loss on the actual renderer canvas triggers the independent fallback', () => {
  const h = harness();
  const parentListeners = Object.create(null);
  let parentCalls = 0;
  const parent = { addEventListener(type, fn) { parentListeners[type] = fn; } };
  parent.addEventListener('webglcontextlost', () => { parentCalls++; });
  const canvasListeners = Object.create(null);
  const canvas = {
    parent,
    addEventListener(type, fn) { canvasListeners[type] = fn; },
    dispatchEvent(event) {
      event.target = this;
      canvasListeners[event.type]?.(event);
      if (event.bubbles) parentListeners[event.type]?.(event);
      return !event.defaultPrevented;
    },
  };
  h.STATE.hall = { renderer: { domElement: canvas }, frame() {} };
  let prevented = 0;
  const registered = h.watchHallCanvas(h.STATE.hall);
  assert.equal(registered, canvas, 'the actual renderer.domElement receives the listener');
  assert.equal(typeof canvasListeners.webglcontextlost, 'function');
  const event = {
    type: 'webglcontextlost', bubbles: false,
    preventDefault() { prevented++; this.defaultPrevented = true; },
  };
  canvas.dispatchEvent(event);
  assert.equal(prevented, 1);
  assert.equal(parentCalls, 0, 'the non-bubbling event is handled on the canvas, not its container');
  assert.equal(h.STATE.hall, null, 'context loss stops the 3D hall');
  assert.deepEqual(h.calls, [h.STATE.d, 'ready'], 'the readable no-GPU controls are mounted and signalled ready');
  assert.equal(h.STATE.errors.length, 1);
});

test('page registers the renderer canvas listener and imports the new module version', () => {
  assert.ok(source.includes('watchHallCanvas(STATE.hall)'));
  assert.ok(source.includes('const canvas = hall?.renderer?.domElement'));
  assert.ok(page.includes('pantheon.js?v=p6'));
});

test('explicit q=low starts the hall in LITE before assets are allocated', () => {
  const start = source.indexOf('constructor(canvas, d)');
  const end = source.indexOf('\n\n  build()', start);
  const constructor = source.slice(start, end);
  assert.match(constructor, /quality === 'low'/);
  assert.match(constructor, /quality === 'off'/);
  assert.match(constructor, /\['ultra', 'high', 'low', 'off'\]\.includes\(quality\)/);
});
