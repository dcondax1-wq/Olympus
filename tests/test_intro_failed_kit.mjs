// Run with: node --test tests/test_intro_failed_kit.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(fileURLToPath(new URL('../tools/web_public/olympus/intro-app.js', import.meta.url)), 'utf8');

test('an already failed kit never mounts a cinematic over Retry', () => {
  const cutoff = source.indexOf('// ------------------------------------------------------------------ the per-app flavour');
  assert.ok(cutoff > 0);
  const window = { OLYMPUS: { app: 'oracle', state: () => 'failed' } };
  const document = { documentElement: {} };
  vm.runInNewContext(source.slice(0, cutoff) + '}());', { window, document });
  assert.equal(window.__olyAppIntro.state, 'off');
  assert.equal(window.__olyAppIntro.why, 'app failed');
});

test('a load failure during a frame ends the intro before drawing another frame', () => {
  const start = source.indexOf('function frame()'), end = source.indexOf('// ------------------------------------------------------------------ start', start);
  assert.ok(start > 0 && end > start);
  const frame = source.slice(start, end);
  const finishes = [];
  const sandbox = {
    raf: 7, done: false, skipping: false, c: {},
    O: { state: () => 'failed' },
    finish: (reason) => finishes.push(reason),
    fail: (error) => { throw error; },
  };
  vm.runInNewContext(frame + '\nframe();', sandbox);
  assert.deepEqual(finishes, ['app failed']);
  assert.equal(sandbox.raf, 0);
});

test('the frame guard leaves a ready app to its normal intro lifecycle', () => {
  const guard = source.match(/if \(O\.state && O\.state\(\) === 'failed'\) \{ finish\('app failed'\); return; \}/)?.[0];
  assert.ok(guard);
  let finished = false;
  vm.runInNewContext('(function(){' + guard + '})();', {
    O: { state: () => 'ready' },
    finish: () => { finished = true; },
  });
  assert.equal(finished, false);
});
