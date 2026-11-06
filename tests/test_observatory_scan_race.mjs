import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../tools/web_public/observatory/app.js', import.meta.url), 'utf8');
const start = source.indexOf('  let scanning = false;');
const end = source.indexOf('  function exportReview()', start);
assert.ok(start >= 0 && end > start);
const elements = {
  refresh: { disabled: false, textContent: 'Scan sources' },
  updated: { textContent: '' }
};
let resolveLoad;
let calls = 0;
let renders = 0;
let failRender = false;
const load = () => { calls++; return new Promise((resolve) => { resolveLoad = resolve; }); };
const render = () => { renders++; if (failRender) throw new Error('render failed'); };
const factory = new Function('$','SOURCES','load','now','history','key','localStorage','render','stamp','window','latest',
  source.slice(start, end) + '; return { scan, getHistory: () => history };');
const { scan, getHistory } = factory((id) => elements[id], [{ id: 'one' }], load, () => 1000, [], 'test',
  { setItem() {} }, render, () => 'now', {}, []);
const first = scan();
const duplicate = scan();
assert.equal(calls, 1, 'scheduled scan must not overlap an in-flight manual scan');
assert.equal(elements.refresh.disabled, true);
resolveLoad({ id: 'one', ok: true, status: 'good', hash: 'abc' });
await Promise.all([first, duplicate]);
assert.equal(getHistory().length, 1, 'one scan should save one history record');
assert.equal(elements.refresh.disabled, false);
const next = scan();
assert.equal(calls, 2, 'a later scan may start after the first finishes');
resolveLoad({ id: 'one', ok: true, status: 'good', hash: 'def' });
await next;
failRender = true;
const failed = scan();
resolveLoad({ id: 'one', ok: true, status: 'good', hash: 'ghi' });
await failed;
assert.match(elements.updated.textContent, /Scan failed/);
assert.equal(elements.refresh.disabled, false, 'failure must restore the scan control');
console.log('Observatory scan overlap and recovery cases passed');
