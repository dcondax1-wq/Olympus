import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../tools/web_public/oracle/fallback.js', import.meta.url), 'utf8');
const { FallbackCity } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
globalThis.devicePixelRatio = 1;

function fixture() {
  const calls = { arcs: 0, pads: 0, labels: [], fills: 0 };
  const gradient = { addColorStop() {} };
  const ctx = {
    setTransform() {}, createLinearGradient: () => gradient, createRadialGradient: () => gradient,
    fillRect() { calls.fills++; }, save() {}, translate() {}, restore() {}, beginPath() {},
    moveTo() {}, lineTo() {}, stroke() {}, closePath() {}, fill() {}, ellipse() { calls.pads++; },
    arc() { calls.arcs++; }, fillText(s) { calls.labels.push(s); },
  };
  const canvas = { clientWidth: 390, clientHeight: 844, width: 0, height: 0,
    getContext(kind) { assert.equal(kind, '2d'); return ctx; } };
  return { canvas, calls };
}

test('2D fallback paints a phone-sized Delphi city and only open level beacons', () => {
  const { canvas, calls } = fixture();
  const city = new FallbackCity(canvas, false);
  assert.equal(canvas.width, 390);
  assert.equal(canvas.height, 844);
  assert.ok(city.buildings.length > 280, 'the phone fallback has a dense decorative skyline');
  city.setWorld({ levels: [{ dist: 5, taken: false }, { dist: -8, taken: false },
    { dist: 1, taken: true }] });
  city.frame(0);
  assert.ok(calls.fills > 100, 'buildings and sky are drawn');
  assert.equal(calls.arcs, 2);
  assert.equal(calls.pads, 3, 'the observatory and two open level pads are connected');
  assert.deepEqual(calls.labels, ['ORACLE · DELPHI']);
});

test('reduced motion holds frames until the next quiet refresh', () => {
  const { canvas, calls } = fixture();
  const city = new FallbackCity(canvas, true);
  city.setWorld({ levels: [] });
  city.frame(0);
  const fills = calls.fills;
  city.frame(500);
  assert.equal(calls.fills, fills);
  city.frame(10000);
  assert.ok(calls.fills > fills);
});

