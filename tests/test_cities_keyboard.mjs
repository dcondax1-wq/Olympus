// Regression: W flies into the city (away from the camera), D strafes right.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../tools/web_public/cities/rig.js', import.meta.url), 'utf8')
  .replace(/^import .*;\n/gm, '')
  .replace('export class Rig', 'class Rig')
  .replace('export function makePath', 'function makePath') + '\nthis.Rig = Rig;';

class Vector3 {
  constructor(x = 0, y = 0, z = 0) { this.set(x, y, z); }
  set(x, y, z) { Object.assign(this, { x, y, z }); return this; }
}
const handlers = {};
const window = { addEventListener(type, fn) { (handlers[type] ||= []).push(fn); } };
const camera = { position: new Vector3(), lookAt() {} };
const canvas = { addEventListener() {} };
const context = { THREE: { Vector3 }, clamp: (x, a, b) => Math.max(a, Math.min(b, x)), smooth: (x) => x,
  matchMedia: () => ({ matches: false }), window, performance: { now: () => 0 }, Math, Set, Map };
vm.runInNewContext(source, context);
const rig = new context.Rig(camera, canvas);
rig.auto = 0;
rig.yaw = 0;
rig.dist = 100;
const press = (key, target = { closest: () => null }) => handlers.keydown.forEach((fn) => fn({ key, target, preventDefault() {}, altKey: false, ctrlKey: false, metaKey: false }));
const release = (key) => handlers.keyup.forEach((fn) => fn({ key }));
press('w'); rig.update(0.05);
assert.ok(rig.t.z < 0, 'W must move away from camera at yaw zero');
assert.equal(rig.t.x, 0);
release('w');
press('d'); rig.update(0.05);
assert.ok(rig.t.x > 0, 'D must strafe toward screen right');
release('d');
const before = [rig.t.x, rig.t.z];
press('w', { closest: () => ({ tagName: 'INPUT' }) }); rig.update(0.05);
assert.deepEqual([rig.t.x, rig.t.z], before, 'typing in search must not fly');
console.log('Cities keyboard direction: PASS');
