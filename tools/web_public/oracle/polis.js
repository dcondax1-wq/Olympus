// The city beyond Oracle's Delphi temple. All towers share three instanced draws;
// the six level beacons react to the current world, never to an order route.
import * as M from '../olympus/materials.js';

const FLOOR = -11.7, COUNT = 720, LITE_COUNT = 240, WINDOWS = 3, BEACONS = 6;
const NIGHT_BLOCKS = 960, LITE_BLOCKS = 320;
// The radar/clock fits inside about 9 world units. Keep the city in that camera
// composition: its authored 71–158-unit rings become an 8.5–19-unit horizon.
const CITY_SCALE = 0.12;
const hash = (n) => {
  const v = Math.sin(n * 127.1 + 78.233) * 43758.5453;
  return v - Math.floor(v);
};

export class Polis {
  constructor(T, scene, { quality = 'high', reduced = false } = {}) {
    this.T = T; this.reduced = reduced;
    this.group = new T.Group();
    this.group.name = 'delphi-city';
    this.group.scale.setScalar(CITY_SCALE);
    this.group.position.y = FLOOR * (1 - CITY_SCALE); // keep the terraces at their authored floor
    scene.add(this.group);
    const stone = M.marble({ color: '#171d2c', vein: '#3a4564', scale: 0.14, roughness: 0.56 });
    const metal = M.metal({ kind: 'gold', color: '#a88a5a', roughness: 0.33 });
    const light = M.neon({ color: '#fff4db', intensity: 2.5, fog: true });
    // Three stepped districts make the buildings sit on a visible piece of terrain.
    this.terraces = [0, 1, 2].map((i) => {
      const base = 71 + i * 31;
      const deck = new T.Mesh(new T.RingGeometry(base, base + 27, 96), M.marble({
        color: i % 2 ? '#171a2b' : '#202034', vein: '#544f73', scale: 0.055, roughness: 0.48
      }));
      deck.rotation.x = -Math.PI / 2;
      deck.position.y = FLOOR - 0.12 - i * 0.2;
      this.group.add(deck);
      return deck;
    });
    this.towers = new T.InstancedMesh(new T.BoxGeometry(1, 1, 1), stone, COUNT);
    this.roofs = new T.InstancedMesh(new T.CylinderGeometry(0.5, 0.7, 1, 6), metal, COUNT);
    this.windows = new T.InstancedMesh(new T.BoxGeometry(1, 1, 1), light, COUNT * WINDOWS);
    // Low, luminous parcels make the outer blocks legible at phone size.
    // They are fixed street lighting, never a market heatmap.
    this.parcels = new T.InstancedMesh(new T.BoxGeometry(1, 1, 1),
      M.neon({ color: '#ffffff', intensity: 1.25, fog: true }), COUNT);
    // Fixed low-rise neighborhood between the authored skyline and the camera.
    // Its lights are decorative and never encode a market row, level, or signal.
    this.nightBlocks = new T.InstancedMesh(new T.BoxGeometry(1, 1, 1), stone, NIGHT_BLOCKS);
    this.nightRoofs = new T.InstancedMesh(new T.BoxGeometry(1, 1, 1),
      M.neon({ color: '#ffffff', intensity: 1.65, fog: true }), NIGHT_BLOCKS);
    const o = new T.Object3D(), col = new T.Color();
    for (let i = 0; i < NIGHT_BLOCKS; i++) {
      const side = i % 4, k = Math.floor(i / 4), row = Math.floor(k / 26), slot = k % 26;
      const angle = side * Math.PI / 2, lane = (slot - 12.5) * 7.8;
      const radius = 72 + row * 7.8, jitter = (hash(i + 811) - 0.5) * 1.3;
      const x = lane * Math.cos(angle) - (radius + jitter) * Math.sin(angle);
      const z = lane * Math.sin(angle) + (radius + jitter) * Math.cos(angle);
      const w = 4.0 + hash(i + 101) * 1.2, d = 4.1 + hash(i + 203) * 1.2;
      const h = 3.5 + hash(i + 307) * 5.5;
      o.rotation.set(0, angle, 0); o.position.set(x, FLOOR + h / 2, z);
      o.scale.set(w, h, d); o.updateMatrix(); this.nightBlocks.setMatrixAt(i, o.matrix);
      o.position.y = FLOOR + h + 0.12; o.scale.set(w * 1.03, 0.24, d * 1.03);
      o.updateMatrix(); this.nightRoofs.setMatrixAt(i, o.matrix);
      const lit = hash(i + 401) < 0.22 ? '#28bb6d' : hash(i + 403) < 0.05 ? '#3b98c3' : '#e77c26';
      this.nightRoofs.setColorAt(i, new T.Color(lit));
    }
    this.nightBlocks.instanceMatrix.needsUpdate = this.nightRoofs.instanceMatrix.needsUpdate = true;
    this.nightRoofs.instanceColor.needsUpdate = true;
    this.nightBlocks.frustumCulled = this.nightRoofs.frustumCulled = false;
    this.group.add(this.nightBlocks, this.nightRoofs);
    for (let i = 0; i < COUNT; i++) {
      const district = Math.floor(i / LITE_COUNT), k = i % LITE_COUNT;
      const row = Math.floor(k / 80), slot = k % 80;
      const ring = 76 + district * 31 + row * 8 + hash(i + 7) * 3;
      const a = slot * Math.PI * 2 / 80 + row * 0.043 + (hash(i + 10) - 0.5) * 0.02;
      const x = Math.cos(a) * ring, z = Math.sin(a) * ring;
      const w = 3 + hash(i + 13) * 3.5;
      const h = (district === 0 ? 7 : 12) + hash(i + 20) * (district === 2 ? 40 : 27) + (i % 19 === 0 ? 17 : 0);
      o.rotation.set(0, -a, 0);
      o.position.set(x, FLOOR + 0.12, z);
      o.scale.set(w * 1.48, 0.24, w * 1.28); o.updateMatrix(); this.parcels.setMatrixAt(i, o.matrix);
      const lit = hash(i + 55) < 0.18 ? '#28ab61' : hash(i + 56) < 0.08 ? '#4688b9' : '#a94b16';
      this.parcels.setColorAt(i, new T.Color(lit));
      o.position.set(x, FLOOR + h / 2, z);
      o.scale.set(w, h, w * 0.82); o.updateMatrix(); this.towers.setMatrixAt(i, o.matrix);
      col.setHSL(0.64 + hash(i + 26) * 0.08, 0.18, 0.17 + hash(i + 23) * 0.13);
      this.towers.setColorAt(i, col);
      o.position.y = FLOOR + h + 0.9;
      o.scale.set(w * 0.8, 1.8, w * 0.8); o.updateMatrix(); this.roofs.setMatrixAt(i, o.matrix);
      // Three small lit floors read as a dense night city from the phone camera.
      // These are decorative: tower count and color never encode market results.
      const windowColor = new T.Color(hash(i + 31) < 0.18 ? '#50e59c' : hash(i + 32) < 0.08 ? '#8acaff' : '#ff9b42');
      for (let j = 0; j < WINDOWS; j++) {
        o.position.set(x + Math.cos(a) * w * 0.43, FLOOR + h * (0.28 + j * 0.22), z + Math.sin(a) * w * 0.43);
        o.scale.set(w * 0.44, 0.65, 0.16); o.updateMatrix();
        this.windows.setMatrixAt(i * WINDOWS + j, o.matrix);
        this.windows.setColorAt(i * WINDOWS + j, windowColor);
      }
    }
    for (const mesh of [this.parcels, this.towers, this.roofs, this.windows]) {
      mesh.instanceMatrix.needsUpdate = true;
      mesh.frustumCulled = false;
      this.group.add(mesh);
    }
    this.towers.instanceColor.needsUpdate = true;
    this.windows.instanceColor.needsUpdate = true;
    this.parcels.instanceColor.needsUpdate = true;
    this.beacons = [];
    this.activeBeacons = 0;
    const beaconMat = M.neon({ color: '#7fe9ff', intensity: 3, fog: true });
    for (let i = 0; i < BEACONS; i++) {
      const a = i * Math.PI * 2 / BEACONS + 0.32, r = 91;
      const column = new T.Mesh(new T.CylinderGeometry(0.18, 0.7, 43, 8), beaconMat.clone());
      column.position.set(Math.cos(a) * r, FLOOR + 21, Math.sin(a) * r);
      const crown = new T.Mesh(new T.OctahedronGeometry(2.2, 0), M.metal({ kind: 'gold', roughness: 0.16 }));
      crown.position.set(column.position.x, FLOOR + 44, column.position.z);
      // A restrained light route ties each open level pillar back to the city
      // observatory. It is visual context, never a signal or an order path.
      const route = new T.Line(new T.BufferGeometry().setFromPoints([
        new T.Vector3(0, FLOOR + 0.5, 0),
        new T.Vector3(Math.cos(a) * r * 0.55, FLOOR + 0.5, Math.sin(a) * r * 0.55),
        new T.Vector3(column.position.x, FLOOR + 0.5, column.position.z),
      ]), new T.LineBasicMaterial({ color: '#7fe9ff', transparent: true, opacity: 0.48, depthWrite: false }));
      const pad = new T.Mesh(new T.RingGeometry(2.6, 3.8, 24), M.neon({ color: '#7fe9ff', intensity: 1.8, opacity: 0.62, fog: true }));
      pad.rotation.x = -Math.PI / 2;
      pad.position.set(column.position.x, FLOOR + 0.18, column.position.z);
      this.group.add(column, crown, route, pad);
      this.beacons.push({ column, crown, route, pad });
    }
    const paths = [];
    for (let i = 0; i < 12; i++) {
      const a = i * Math.PI / 6;
      paths.push(new T.Vector3(Math.cos(a) * 62, FLOOR + 0.1, Math.sin(a) * 62));
      paths.push(new T.Vector3(Math.cos(a) * 158, FLOOR + 0.1, Math.sin(a) * 158));
    }
    const pathGeo = new T.BufferGeometry().setFromPoints(paths);
    this.paths = new T.LineSegments(pathGeo, new T.LineBasicMaterial({ color: '#8c7694', transparent: true, opacity: 0.38 }));
    this.group.add(this.paths);
    // Elevated district loops echo Data City's colored night routes. They are
    // decorative connections, never level, signal, or order paths.
    this.skyways = ['#ff9b42', '#50e59c', '#8acaff'].map((color, district) => {
      const r = 89 + district * 31, y = FLOOR + 20 + district * 4;
      const points = Array.from({ length: 96 }, (_, k) => {
        const a = k * Math.PI * 2 / 96;
        return new T.Vector3(Math.cos(a) * r, y, Math.sin(a) * r);
      });
      const loop = new T.LineLoop(new T.BufferGeometry().setFromPoints(points), new T.LineBasicMaterial({ color, transparent: true, opacity: 0.64, depthWrite: false }));
      this.group.add(loop); return loop;
    });
    this.setQuality(quality);
  }

  setQuality(q) {
    this.quality = q;
    const lite = q === 'low' || q === 'off';
    // The first 240 towers form the nearest, most visible district.
    this.towers.count = this.roofs.count = lite ? LITE_COUNT : COUNT;
    this.parcels.count = this.towers.count;
    this.parcels.visible = q !== 'off';
    this.nightBlocks.count = this.nightRoofs.count = lite ? LITE_BLOCKS : NIGHT_BLOCKS;
    this.nightRoofs.visible = q !== 'off';
    this.windows.count = this.towers.count * WINDOWS;
    this.roofs.visible = q !== 'off';
    this.paths.visible = q !== 'off';
    this.skyways.forEach((loop, i) => { loop.visible = q !== 'off' && (!lite || i === 0); });
    this.terraces.forEach((deck, i) => { deck.visible = !lite || i === 0; });
    this.beacons.forEach(({ route, pad }, i) => {
      route.visible = pad.visible = i < this.activeBeacons && q !== 'off' && (!lite || i < 3);
    });
  }

  setWorld(w) {
    const levels = (w && w.levels || []).filter(l => !l.taken).slice(0, BEACONS);
    this.activeBeacons = levels.length;
    this.beacons.forEach(({ column, crown, route, pad }, i) => {
      const active = i < levels.length;
      column.visible = crown.visible = active;
      route.visible = pad.visible = active && this.quality !== 'off' && (this.quality !== 'low' || i < 3);
      if (active) {
        const side = levels[i].dist >= 0 ? 1 : -1;
        column.scale.y = 0.48 + Math.min(0.52, Math.abs(levels[i].dist || 0) / 150);
        column.material.color.set(side > 0 ? '#7fe9ff' : '#e1a5ff').multiplyScalar(3);
        route.material.color.set(side > 0 ? '#7fe9ff' : '#e1a5ff');
        pad.material.color.set(side > 0 ? '#7fe9ff' : '#e1a5ff').multiplyScalar(1.8);
      }
    });
  }

  applyTheme() {
    // Keep the fixed amber / green district lights when the user's accent
    // changes. Oracle's data beacons carry the themed, world-driven color.
  }

  frame(t) {
    if (this.reduced) return;
    this.beacons.forEach(({ crown }, i) => {
      crown.rotation.y = t * 0.22 + i;
      crown.position.y = FLOOR + 44 + Math.sin(t * 0.9 + i) * 0.7;
    });
    if (this.quality !== 'low' && this.quality !== 'off') this.beacons.forEach(({ route }, i) => {
      if (route.visible) route.material.opacity = 0.38 + Math.sin(t * 1.1 + i * 0.9) * 0.1;
    });
  }
}

