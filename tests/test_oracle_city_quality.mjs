import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Exercise the real prototype methods without constructing a WebGL renderer.
// Their imports are only needed by constructors and other scene methods.
const loadClass = async (path, name) => {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8').replace(/^import .*;\n/gm, '');
  return (await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64')))[name];
};
const Scene = await loadClass('../tools/web_public/oracle/scene.js', 'Scene');
const Polis = await loadClass('../tools/web_public/oracle/polis.js', 'Polis');

test('Delphi skyline follows the effective render tier across global Off, LITE, and HD', () => {
  const city = Object.create(Polis.prototype);
  city.towers = { count: 720 }; city.roofs = { count: 720, visible: true };
  city.parcels = { count: 720, visible: true };
  city.windows = { count: 2160 }; city.paths = { visible: true };
  city.skyways = Array.from({ length: 3 }, () => ({ visible: true }));
  city.terraces = Array.from({ length: 3 }, () => ({ visible: true }));
  city.activeBeacons = 4;
  city.beacons = Array.from({ length: 6 }, () => ({ route: { visible: true }, pad: { visible: true } }));
  const rc = { tier: 'off', quality() { return this.tier; } };
  const scene = { rc, polis: city };

  Scene.prototype.syncCityQuality.call(scene);
  assert.equal(city.towers.count, 240);
  assert.equal(city.parcels.count, 240);
  assert.equal(city.parcels.visible, false);
  assert.equal(city.windows.count, 720);
  assert.equal(city.roofs.visible, false);
  assert.deepEqual(city.skyways.map(loop => loop.visible), [false, false, false]);
  assert.deepEqual(city.beacons.map((b) => b.route.visible), [false, false, false, false, false, false]);

  rc.tier = 'low'; Scene.prototype.syncCityQuality.call(scene);
  assert.equal(city.towers.count, 240);
  assert.equal(city.parcels.count, 240);
  assert.equal(city.parcels.visible, true);
  assert.equal(city.windows.count, 720);
  assert.deepEqual(city.skyways.map(loop => loop.visible), [true, false, false]);
  assert.deepEqual(city.beacons.map((b) => b.pad.visible), [true, true, true, false, false, false]);

  rc.tier = 'high'; Scene.prototype.syncCityQuality.call(scene);
  assert.equal(city.towers.count, 720);
  assert.equal(city.parcels.count, 720);
  assert.equal(city.windows.count, 2160);
  assert.equal(city.roofs.visible, true);
  assert.deepEqual(city.skyways.map(loop => loop.visible), [true, true, true]);
  assert.deepEqual(city.beacons.map((b) => b.route.visible), [true, true, true, true, false, false]);
});
