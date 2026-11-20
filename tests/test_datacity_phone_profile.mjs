// Data City must keep a 3D skyline on phones while staying inside the measured phone render budget.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync('tools/web_public/datacity/caps.js', 'utf8').replace(/^export /gm, '');
function choose({ search = '', width = 1363, coarse = false, ua = 'Desktop', level = 'high', saver = false } = {}) {
  const context = vm.createContext({
    URLSearchParams, location: { search }, innerWidth: width, innerHeight: 844,
    matchMedia: () => ({ matches: coarse }),
    navigator: { userAgent: ua, platform: '', maxTouchPoints: 0 },
  });
  vm.runInContext(source, context);
  const phone = context.phoneHint();
  return { phone, profile: context.profileOf(level, phone, saver) };
}

test('phone high keeps a 3D phone profile', () => {
  assert.equal(choose({ width: 390 }).profile, 'phone');
  assert.equal(choose({ width: 1363, coarse: true }).profile, 'phone');
  assert.equal(choose({ width: 1363, ua: 'iPhone' }).profile, 'phone');
});
test('phone ultra keeps the phone 3D budget; desktop ultra retains full detail', () => {
  assert.equal(choose().profile, 'full');
  assert.equal(choose({ width: 390, level: 'ultra' }).profile, 'phone');
  assert.equal(choose({ coarse: true, level: 'ultra' }).profile, 'phone');
  assert.equal(choose({ level: 'ultra' }).profile, 'full');
  assert.equal(choose({ level: 'ultra', saver: true }).profile, 'full');
});
test('explicit phone=0 opts a phone into full; phone=1 previews smaller 3D profile', () => {
  assert.deepEqual(choose({ search: '?phone=0', width: 390 }), { phone: false, profile: 'full' });
  assert.deepEqual(choose({ search: '?phone=0', width: 390, level: 'ultra' }), { phone: false, profile: 'full' });
  assert.deepEqual(choose({ search: '?phone=1' }), { phone: true, profile: 'phone' });
});
test('battery saver reduces high and low/off remain LITE', () => {
  assert.equal(choose({ saver: true }).profile, 'phone');
  assert.equal(choose({ width: 390, level: 'low' }).profile, 'lite');
  assert.equal(choose({ width: 390, level: 'off', search: '?phone=0' }).profile, 'lite');
});

test('versioned module chain brings the phone profile to cached clients', () => {
  const index = fs.readFileSync('tools/web_public/datacity/index.html', 'utf8');
  const city = fs.readFileSync('tools/web_public/datacity/city.js', 'utf8');
  const scene = fs.readFileSync('tools/web_public/datacity/scene.js', 'utf8');
  const layout = fs.readFileSync('tools/web_public/datacity/layout.js', 'utf8');
  const towns = fs.readFileSync('tools/web_public/datacity/towns.js', 'utf8');
  assert.match(index, /city\.js\?v=[\w.-]+/);
  assert.match(city, /scene\.js\?v=[\w.-]+/);
  assert.match(city, /layout\.js\?v=[\w.-]+/);
  assert.match(city, /minimap\.js\?v=[\w.-]+/);
  assert.match(scene, /caps\.js\?v=[\w.-]+/);
  assert.match(scene, /towns\.js\?v=[\w.-]+/);
  assert.match(scene, /streams\.js\?v=[\w.-]+/);
  assert.match(layout, /satellites\.js\?v=[\w.-]+/);
  assert.match(towns, /caps\.js\?v=[\w.-]+/);
  assert.match(towns, /satellites\.js\?v=[\w.-]+/);
});

