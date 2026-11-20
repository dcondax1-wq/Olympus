// Real Three.js CPU regressions: visual density stays inside the phone scene budget.
import assert from 'node:assert/strict';
import * as THREE from '../tools/web_public/jarvis/three.module.min.js';
import { citadel, CITADEL_LIMITS } from '../tools/web_public/arena/colosseum.js';
import { illustratedColosseum } from '../tools/web_public/arena/illustration.js';

const scene = new THREE.Scene();
const city = citadel(scene);
const high = city.stats();
assert.ok(high.calls <= CITADEL_LIMITS.calls);
assert.ok(high.triangles <= CITADEL_LIMITS.triangles);
assert.equal(high.instances, 232);
assert.equal(high.calls, 6);
assert.equal(high.triangles, 4608);
assert.equal(scene.children.length, 1, 'one removable group');
city.group.children.forEach((mesh) => {
  assert.equal(mesh.isInstancedMesh, true, 'all repeated architecture is batched');
  const matrices = mesh.instanceMatrix.array;
  assert.ok(matrices.every(Number.isFinite), 'all placements remain finite');
});
city.setLite(true);
const low = city.stats();
assert.equal(low.calls, 5);
assert.equal(low.triangles, 3216);
assert.ok(low.triangles < high.triangles);
city.setLite(false); assert.deepEqual(city.stats(), high, 'switching restores architecture without allocating a new scene');
const disposed = [];
city.group.children.forEach((x) => x.geometry.addEventListener('dispose', () => disposed.push(x)));
city.dispose();
assert.equal(scene.children.length, 0);
assert.equal(disposed.length, 6, 'all six geometries disposed');

const svg = illustratedColosseum();
assert.equal(svg, illustratedColosseum(), 'artwork is deterministic');
assert.ok(svg.length < 18000, 'illustration remains a small inline asset');
assert.equal((svg.match(/href="#arena-arch"/g) || []).length, 66, 'three complete vaulted galleries');
assert.equal((svg.match(/<path d="M-15 0H15V78L0 92 -15 78Z"/g) || []).length, 4, 'imperial banners');   // palette moved to the house bronze/gold (2026-11)
assert.equal((svg.match(/fill="url\(#arena-fire-pool\)"/g) || []).length, 4, 'torch towers');
assert.ok(!/https?:|<script|<foreignObject|\bon\w+=/i.test(svg.replace('xmlns="http://www.w3.org/2000/svg"', '')), 'art is self-contained and inert');
console.log(`Arena citadel PASS: HD ${high.calls} calls/${high.triangles} triangles; LITE ${low.calls}/${low.triangles}; fallback ${svg.length} bytes.`);

