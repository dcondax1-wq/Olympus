import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import vm from 'node:vm';
import test from 'node:test';

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, '../tools/web_public/datacity/city.js'), 'utf8');
const start = source.indexOf('function readableFallback(');
const end = source.indexOf('\nasync function main()', start);
assert.ok(start >= 0 && end > start, 'Data City fallback function exists');
const fallbackSource = source.slice(start, end);

function fixture(body = fallbackSource, kitPresent = true) {
  const events = [];
  const node = (tag, cls = '', text = '') => ({
    tag, cls, text, children: [], value: '', style: { setProperty() {} }, classList: { add(name) { events.push('class:' + name); }, toggle() {} },
    append(...children) { this.children.push(...children); if (this === document.body) events.push('append:body'); },
    replaceChildren(...children) { this.children = children; },
    addEventListener() {}, setAttribute() {}, querySelectorAll() { return []; }, remove() { events.push('remove:loading'); },
  });
  const document = { head: node('head'), body: node('body'), createElement: (tag) => node(tag) };
  let veil = true;
  const O = kitPresent ? { ready() {
    assert.ok(document.body.children.some((n) => n.cls === 'readable-city'), 'fallback appended before kit ready');
    events.push('ready');
    veil = false;
  } } : null;
  const state = {};
  const model = {
    buildings: [{ lab: 'NY sweep', d: 'ny', cls: 'green', e: 12, n: 30 }],
    sections: [{ name: 'New York', key: 'ny', items: [{ lab: 'NY sweep', d: 'ny' }] }],
    D: {},
  };
  const sandbox = { document, O, state, el: node, $: () => node('loading'),
    labelOf: (b) => b.lab, money: (n) => '$' + n, Number, String, Object };
  const run = vm.runInNewContext('(' + body + ')', sandbox);
  run(model, false, new Error('WebGL unavailable'));
  return { document, events, state, veil, model };
}

test('3D failure reveals the research immediately after the fallback enters the DOM', () => {
  const result = fixture();
  assert.deepEqual(result.events.filter((x) => x === 'append:body' || x === 'ready'), ['append:body', 'ready']);
  assert.equal(result.veil, false);
  assert.equal(result.state.ready, true);
  assert.equal(result.state.mode, 'live-fallback');
  assert.equal(result.state.buildings, 1);
  assert.match(result.state.fallbackReason, /WebGL unavailable/);
  const main = result.document.body.children.find((n) => n.cls === 'readable-city');
  assert.ok(main.children.some((n) => n.tag === 'h1' && n.text === 'The city is still here'));
  const map = main.children.find((n) => n.cls === 'city-map');
  assert.ok(map, 'city map is visible before the idea list');
  const districts = map.children.find((n) => n.cls === 'districts');
  assert.equal(districts.children.length, 1);
  assert.ok(districts.children[0].children.some((n) => n.cls === 'district-tower'));
  assert.match(result.document.head.children[0].textContent, /district-tower/);
});

test('the regression check detects a fallback that leaves the veil up', () => {
  const withoutReady = fallbackSource.replace(/\n  O\?\.ready\(\);[^\n]*/, '');
  assert.notEqual(withoutReady, fallbackSource);
  assert.equal(fixture(withoutReady).veil, true);
});

test('the readable fallback also works if the shared kit was unavailable', () => {
  const result = fixture(fallbackSource, false);
  assert.equal(result.state.ready, true);
  assert.ok(result.document.body.children.some((n) => n.cls === 'readable-city'));
});
