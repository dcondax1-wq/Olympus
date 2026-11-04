// The outskirts: a ring of decorative towers round the data districts so the city has no edge (about 2,600 towers, ONE instanced
// draw, the same neon-window shader as the data buildings). They are scenery, not data: no tap, no card, no result behind them.
// Tall spires stand nearer the districts, a few gold-lit megatowers mark the ring, everything fades into the fog.
import * as THREE from '../jarvis/three.module.min.js';
import * as SH from './shaders.js';

const COUNT = { hq: 2600, lq: 900 };
const PALETTE = [0x3a5fb5, 0x4f8cff, 0x7fe9ff, 0xa68bff, 0x6a7bd8, 0xc9b8ff, 0xffc94a];
const mulberry = (a) => () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

export class Outskirts {
  /** L: layout(); U: the scene uniforms; avoid: [{ x, z, r }] places to keep clear (the acropolis); quality */
  constructor(L, U, quality, avoid = []) {
    const rnd = mulberry(23), ds = L.districts.filter((d) => d.kind !== 'harbor');
    const R0 = Math.max(120, ...ds.map((d) => Math.hypot(Math.abs(d.cx) + d.half, Math.abs(d.cz) + d.half))) + 26, R1 = R0 + 210;
    const hb = L.harbor, cell = 3.6, seen = new Set(), list = [];
    for (let tries = 0; tries < COUNT.hq * 4 && list.length < COUNT.hq; tries++) {
      const a = rnd() * Math.PI * 2, r = R0 + (R1 - R0) * Math.pow(rnd(), 0.8);
      const x = Math.round((Math.cos(a) * r) / cell) * cell, z = Math.round((Math.sin(a) * r) / cell) * cell, key = x + ',' + z;
      if (seen.has(key)) continue;
      if (hb && x > hb.x0 - 24 && x < hb.x1 + 24 && z > hb.z0 - 24 && z < hb.z1 + 30) continue;
      if (avoid.some((p) => Math.hypot(x - p.x, z - p.z) < p.r)) continue;
      if (ds.some((d) => Math.abs(x - d.cx) < d.half + 14 && Math.abs(z - d.cz) < d.half + 14)) continue;
      seen.add(key);
      const t = (Math.hypot(x, z) - R0) / (R1 - R0), spire = rnd() < 0.05;
      const h = (spire ? 34 + rnd() * 34 : 3.5 + Math.pow(rnd(), 2.2) * 24) * (1 - t * 0.45), w = 1.4 + rnd() * 1.6;
      list.push({ x, z, h, w, color: spire && rnd() < 0.5 ? 0xffc94a : PALETTE[Math.floor(rnd() * 6)], lit: 0.45 + rnd() * 0.5, seed: rnd() });
    }
    const n = list.length, box = new THREE.BoxGeometry(1, 1, 1);
    box.translate(0, 0.5, 0);
    const aColor = new Float32Array(n * 3), aData = new Float32Array(n * 4), aState = new Float32Array(n * 4), aSeed = new Float32Array(n);
    const m4 = new THREE.Matrix4(), c = new THREE.Color();
    const g = new THREE.BufferGeometry();
    for (const k of ['position', 'normal', 'uv']) g.setAttribute(k, box.getAttribute(k));
    g.setIndex(box.index);
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), R1 + 80);
    this.mesh = new THREE.InstancedMesh(g, new THREE.ShaderMaterial({ vertexShader: SH.BUILD_VS, fragmentShader: SH.BUILD_FS,
      uniforms: { uTime: U.uTime, uFog: U.uFog, uFogD: U.uFogD, uHaze: U.uHaze, uDay: U.uDay, uToday: { value: 0 }, uWet: U.uWet, uGrow: U.uGrow, uMirror: { value: 0 } } }), n);
    list.forEach((b, i) => {
      m4.makeScale(b.w, b.h, b.w).setPosition(b.x, 0, b.z);
      this.mesh.setMatrixAt(i, m4);
      c.setHex(b.color); aColor.set([c.r, c.g, c.b], i * 3);
      aData.set([b.h, b.lit, b.h > 34 ? 1 : 0, 0], i * 4);
      aSeed[i] = b.seed;
    });
    g.setAttribute('aColor', new THREE.InstancedBufferAttribute(aColor, 3));
    g.setAttribute('aData', new THREE.InstancedBufferAttribute(aData, 4));
    g.setAttribute('aState', new THREE.InstancedBufferAttribute(aState, 4));
    g.setAttribute('aSeed', new THREE.InstancedBufferAttribute(aSeed, 1));
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 2;
    this.mesh.userData.decor = true;
    this.total = n;
    this.radius = [R0, R1];
    this.group = new THREE.Group();
    this.group.add(this.mesh);
    this.setQuality(quality);
  }

  setQuality(q) { this.mesh.count = Math.min(this.total, COUNT[q] ?? COUNT.hq); }
}
