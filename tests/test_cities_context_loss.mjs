import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import vm from 'node:vm';
import test from 'node:test';

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, '../tools/web_public/cities/app.js'), 'utf8');
const start = source.indexOf('function recoverLostContext(');
const end = source.indexOf('\nasync function boot()', start);
assert.ok(start >= 0 && end > start, 'context-loss helper exists');
const body = source.slice(start, end);
assert.match(source, /canvas\.addEventListener\('webglcontextlost', \(event\) => recoverLostContext\(stage, event\), \{ once: true \}\)/);

function run(initial = 'true', throws = false) {
  const calls = [];
  const document = { body: { dataset: { ready: initial } } };
  const fallbackList = (reason) => { calls.push(reason); document.body.dataset.ready = 'fallback'; };
  const stage = { dispose() { calls.push('disposed'); if (throws) throw Error('device lost'); } };
  const event = { preventDefault() { calls.push('prevented'); } };
  const fn = vm.runInNewContext('(' + body + ')', { document, fallbackList });
  fn(stage, event);
  return { calls, ready: document.body.dataset.ready };
}

test('a silent GPU context loss switches to the usable atlas', () => {
  const r = run();
  assert.deepEqual(r.calls, ['prevented', 'disposed', 'The 3D graphics stopped on this device.']);
  assert.equal(r.ready, 'fallback');
});
test('a prior fallback is not mounted twice', () => {
  assert.deepEqual(run('fallback').calls, ['prevented']);
});
test('the atlas still appears when disposing a lost GPU throws', () => {
  const r = run('true', true);
  assert.equal(r.ready, 'fallback');
  assert.equal(r.calls.at(-1), 'The 3D graphics stopped on this device.');
});
