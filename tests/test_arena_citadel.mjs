import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../tools/web_public/jarvis/three.module.min.js';
import { createCitadel } from '../tools/web_public/arena/citadel.js';

test('Arena citadel has deterministic full and LITE districts and disposes cleanly', () => {
  const scene = new THREE.Scene();
  const city = createCitadel(scene, false);
  assert.equal(city.stats().towers, 176);
  assert.equal(city.stats().windows, 1408);
  assert.equal(city.stats().causeways, 4);
  assert.equal(city.stats().routes, 112);
  assert.equal(city.stats().arcs, 36);
  assert.equal(scene.children.length, 1);
  const group = scene.children[0], routes = group.children.find((x) => x.isInstancedMesh && x.count === 112);
  assert.ok(routes, 'one batched circuit');
  assert.equal(group.children.filter((x) => x.isInstancedMesh).length, 5, 'three building batches, one route batch and one arc batch');
  const arcs = group.children.find((x) => x.isInstancedMesh && x.count === 36);
  assert.ok(arcs && arcs.instanceColor, 'one colored skybridge draw');
  assert.ok(arcs.instanceMatrix.array.every(Number.isFinite));
  assert.ok(arcs.geometry.index.count / 3 * arcs.count <= 432, 'bounded skybridge triangles');
  assert.ok(routes.instanceMatrix.array.every(Number.isFinite));
  // a street is its top face since 2026-11-16 (2 triangles, was a 12-triangle box 0.045 high): the budget is now 112 x 2
  assert.equal(routes.geometry.index.count / 3 * routes.count, 224, 'bounded route triangle budget');
  const towers = group.children.find((x) => x.isInstancedMesh && x.count === 176 && x.instanceColor);
  assert.ok(towers);
  for (let i = 0; i < 176; i++) if (i % 3 === 2) {
    const m = new THREE.Matrix4(), p = new THREE.Vector3();
    towers.getMatrixAt(i, m); p.setFromMatrixPosition(m);
    assert.ok(Math.hypot(p.x, p.z) >= 76 && Math.hypot(p.x, p.z) < 82, 'outer district clears the Colosseum 61-69 radius ring');
  }
  city.setLite(true);
  assert.equal(city.stats().towers, 80);
  assert.equal(city.stats().windows, 640);
  assert.equal(city.stats().routes, 64);
  assert.equal(city.stats().arcs, 12);
  // The first 48 segments form three closed 16-sided loops, and 16 spokes join them.
  const endpoints = (i) => {
    const m = new THREE.Matrix4(); routes.getMatrixAt(i, m);
    return [new THREE.Vector3(0, 0, -0.5).applyMatrix4(m), new THREE.Vector3(0, 0, 0.5).applyMatrix4(m)];
  };
  for (let ring = 0; ring < 3; ring++) {
    for (let sector = 0; sector < 16; sector++) {
      const idx = (s) => (s % 16) * 4 + (s % 16 % 2) + ring;
      assert.ok(endpoints(idx(sector))[1].distanceTo(endpoints(idx(sector + 1))[0]) < 0.0001,
        'the LITE district ring remains continuous');
    }
  }
  for (let sector = 0; sector < 16; sector += 2) {
    const i = sector * 4;
    assert.ok(endpoints(i + 0)[0].distanceTo(endpoints(i + 3)[0]) < 0.0001, 'spoke joins inner and middle rings');
    assert.ok(endpoints(i + 3)[1].distanceTo(endpoints(i + 4)[0]) < 0.0001, 'spoke joins middle and outer rings');
  }
  city.setLite(false);
  assert.equal(city.stats().towers, 176);
  assert.equal(city.stats().routes, 112);
  city.dispose();
  assert.equal(scene.children.length, 0);
});
