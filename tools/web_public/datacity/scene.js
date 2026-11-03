// The Data City's three.js world: sky, ground, every building in one InstancedMesh (+ its reflection), glow sprites,
// streets with flowing trades, the LIT tower and the district names. No DOM beyond the canvas; city.js drives it.
import * as THREE from '../jarvis/three.module.min.js';
import { COLORS } from './util.js';
import { streets } from './layout.js';
import * as SH from './shaders.js';

const NIGHT = { fog: 0x070a1c, density: 0.0065, theme: '#05060f' };
const DAY = { fog: 0xa9c4ea, density: 0.0045, theme: '#a9c4ea' };
const FLOW = { hq: 1400, lq: 380 };
const STARS = { hq: 1600, lq: 400 };
const NAMES = { times: 'TIMES', confluences: 'CONFLUENCES', while: 'WHILE-STATES', strategies: 'STRATEGIES' };

const golden = (i) => (i * 0.6180339) % 1;          // a stable per-instance seed

function points(attrs, material) {
  const g = new THREE.BufferGeometry();
  for (const [name, [arr, size]] of Object.entries(attrs)) g.setAttribute(name, new THREE.BufferAttribute(arr, size));
  return new THREE.Points(g, material);
}

function textSprite(text, color, size = 1) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 96;
  const g = c.getContext('2d');
  g.font = '800 46px -apple-system, system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.shadowColor = color; g.shadowBlur = 18; g.fillStyle = color;
  g.fillText(text.split('').join(String.fromCharCode(8202)), 256, 50);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, fog: false }));
  s.scale.set(16 * size, 3 * size, 1);
  s.renderOrder = 6;                                  // after the see-through ground, which would wash the name out
  return s;
}

export class CityScene {
  /** canvas: the <canvas>; L: layout(); opts: { quality: 'hq' | 'lq', day: bool, winRate: 0..1 (street colours) } */
  constructor(canvas, L, opts) {
    this.L = L;
    this.quality = opts.quality;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: opts.quality === 'hq', powerPreference: 'high-performance' });
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(52, 1, 0.5, 1600);
    this.U = { uTime: { value: 0 }, uFog: { value: new THREE.Color() }, uFogD: { value: NIGHT.density }, uDay: { value: 0 },
               uPR: { value: 1 } };
    this.resize();
    this._sky();
    this._ground();
    this._buildings();
    this._glow();
    this._streets(opts.winRate);
    this._tower();
    this._names();
    this.setDay(opts.day);
    this.setQuality(opts.quality);
  }

  _uniforms(...names) { return Object.fromEntries(names.map((n) => [n, this.U[n]])); }

  _sky() {
    this.scene.add(new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), new THREE.ShaderMaterial({
      vertexShader: SH.SKY_VS, fragmentShader: SH.SKY_FS, uniforms: this._uniforms('uDay'), side: THREE.BackSide, depthWrite: false })));
    const n = STARS[this.quality], p = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, h = 0.08 + Math.random() * 0.9, r = 800, flat = Math.sqrt(1 - h * h);
      p.set([Math.cos(a) * r * flat, h * r, Math.sin(a) * r * flat], i * 3);
    }
    this.stars = points({ position: [p, 3] }, new THREE.PointsMaterial({ color: 0xcfd8ff, size: 1.6, sizeAttenuation: false,
      transparent: true, opacity: 0.85, depthWrite: false, fog: false }));
    this.scene.add(this.stars);
  }

  _ground() {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(700, 700), new THREE.ShaderMaterial({ vertexShader: SH.GROUND_VS,
      fragmentShader: SH.GROUND_FS, uniforms: this._uniforms('uFog', 'uFogD', 'uDay', 'uTime'), transparent: true }));
    ground.rotation.x = -Math.PI / 2;
    ground.renderOrder = 1;
    this.scene.add(ground);
  }

  _buildings() {
    const items = this.L.items, n = items.length;
    const geo = new THREE.BoxGeometry(1, 1, 1);
    geo.translate(0, 0.5, 0);
    const aColor = new Float32Array(n * 3), aData = new Float32Array(n * 4), aSeed = new Float32Array(n);
    const m4 = new THREE.Matrix4(), col = new THREE.Color();
    const mat = (mirror) => new THREE.ShaderMaterial({ vertexShader: SH.BUILD_VS, fragmentShader: SH.BUILD_FS,
      uniforms: { ...this._uniforms('uTime', 'uFog', 'uFogD', 'uDay'), uMirror: { value: mirror ? 1 : 0 } },
      ...(mirror ? { transparent: true, depthWrite: false, side: THREE.DoubleSide } : {}) });
    this.mesh = new THREE.InstancedMesh(geo, mat(false), n);
    items.forEach((it, i) => {
      m4.makeScale(it.w, it.h, it.w).setPosition(it.x, 0, it.z);
      this.mesh.setMatrixAt(i, m4);
      col.setHex(it.color);
      aColor.set([col.r, col.g, col.b], i * 3);
      aData.set([it.h, it.lit, it.pulse, 0], i * 4);
      aSeed[i] = golden(i);
    });
    geo.setAttribute('aColor', new THREE.InstancedBufferAttribute(aColor, 3));
    geo.setAttribute('aData', new THREE.InstancedBufferAttribute(aData, 4));
    geo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(aSeed, 1));
    this.mesh.renderOrder = 2;
    this.mesh.computeBoundingSphere();
    this.scene.add(this.mesh);
    this.mirror = new THREE.InstancedMesh(geo, mat(true), n);        // the wet-street reflection (HQ only)
    this.mirror.instanceMatrix = this.mesh.instanceMatrix;
    this.mirror.frustumCulled = false;
    this.scene.add(this.mirror);
  }

  _glow() {
    const hq = this.quality === 'hq';
    const lit = this.L.items.map((it, i) => [it, i]).filter(([it]) => it.kind !== 'b' || it.b.cls === 'gold' || it.pulse || (hq && it.b.cls === 'green'));
    const p = new Float32Array(lit.length * 3), c = new Float32Array(lit.length * 3), size = new Float32Array(lit.length),
          pulse = new Float32Array(lit.length), seed = new Float32Array(lit.length), col = new THREE.Color();
    lit.forEach(([it, i], k) => {
      p.set([it.x, it.h + 0.35, it.z], k * 3);
      col.setHex(it.color);
      c.set([col.r, col.g, col.b], k * 3);
      size[k] = it.kind === 'd' ? 9 : it.kind === 's' ? 8 : it.b.cls === 'gold' ? 7 : it.pulse ? 5 : 2.6;
      pulse[k] = it.pulse;
      seed[k] = golden(i);
    });
    this.glowMat = new THREE.ShaderMaterial({ vertexShader: SH.GLOW_VS, fragmentShader: SH.GLOW_FS, uniforms: this._uniforms('uTime', 'uPR', 'uDay'),
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    const glow = points({ position: [p, 3], aColor: [c, 3], aSize: [size, 1], aPulse: [pulse, 1], aSeed: [seed, 1] }, this.glowMat);
    glow.renderOrder = 3;
    this.scene.add(glow);
  }

  _streets(winRate) {
    const segs = streets(this.L.centers), m4 = new THREE.Matrix4(), up = new THREE.Vector3(0, 1, 0), col = new THREE.Color();
    const roadGeo = new THREE.PlaneGeometry(1, 1);
    roadGeo.rotateX(-Math.PI / 2);
    const roads = new THREE.InstancedMesh(roadGeo, new THREE.MeshBasicMaterial({ color: 0x0a1028, transparent: true, opacity: 0.85, depthWrite: false }), segs.length);
    segs.forEach(([x0, z0, x1, z1], i) => {
      const q = new THREE.Quaternion().setFromAxisAngle(up, -Math.atan2(z1 - z0, x1 - x0));
      m4.compose(new THREE.Vector3((x0 + x1) / 2, 0.02, (z0 + z1) / 2), q, new THREE.Vector3(Math.hypot(x1 - x0, z1 - z0), 1, 1.4));
      roads.setMatrixAt(i, m4);
    });
    roads.renderOrder = 1;
    this.scene.add(roads);
    const n = FLOW.hq, seg = new Float32Array(n * 4), c = new Float32Array(n * 3), move = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      let s = segs[i % segs.length];
      if (Math.random() < 0.5) s = [s[2], s[3], s[0], s[1]];
      const lane = (Math.random() - 0.5) * 0.9, dx = s[2] - s[0], dz = s[3] - s[1], len = Math.hypot(dx, dz) || 1;
      const nx = (-dz / len) * lane, nz = (dx / len) * lane;
      seg.set([s[0] + nx, s[1] + nz, s[2] + nx, s[3] + nz], i * 4);
      col.setHex(Math.random() < winRate ? COLORS.win : COLORS.loss);
      c.set([col.r, col.g, col.b], i * 3);
      move.set([((0.6 + Math.random() * 0.8) * 6) / len, Math.random()], i * 2);
    }
    this.flow = points({ position: [new Float32Array(n * 3), 3], aSeg: [seg, 4], aColor: [c, 3], aMove: [move, 2] },
      new THREE.ShaderMaterial({ vertexShader: SH.FLOW_VS, fragmentShader: SH.FLOW_FS, uniforms: this._uniforms('uTime', 'uPR', 'uDay'),
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.flow.frustumCulled = false;
    this.flow.renderOrder = 3;
    this.scene.add(this.flow);
  }

  _tower() {
    this.tower = new THREE.Group();
    const tm = new THREE.ShaderMaterial({ vertexShader: SH.TOWER_VS, fragmentShader: SH.TOWER_FS, uniforms: this._uniforms('uTime', 'uDay') });
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 3.4, 40, 8, 1), tm);
    shaft.position.y = 20;
    const spire = new THREE.Mesh(new THREE.ConeGeometry(1.5, 9, 8), tm);
    spire.position.y = 44.5;
    this.tower.add(shaft, spire);
    const ringMat = new THREE.MeshBasicMaterial({ color: COLORS.lit, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false });
    for (const [y, r] of [[12, 5.5], [26, 4.4], [38, 3.3]]) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r, 0.09, 6, 64), ringMat);
      ring.rotation.x = Math.PI / 2;
      ring.position.y = y;
      this.tower.add(ring);
    }
    const name = textSprite('LIT · ZLARIOR', '#7fe9ff', 0.9);
    name.position.set(0, 53, 0);
    this.tower.add(name);
    this.scene.add(this.tower);
    const beacon = points({ position: [new Float32Array([0, 49, 0]), 3], aColor: [new Float32Array([0.25, 0.85, 1.0]), 3],
                            aSize: [new Float32Array([26]), 1], aPulse: [new Float32Array([1]), 1], aSeed: [new Float32Array([0.2]), 1] }, this.glowMat);
    beacon.renderOrder = 3;
    this.scene.add(beacon);
  }

  _names() {
    for (const [k, [x, z]] of Object.entries(this.L.centers)) {
      const s = textSprite(NAMES[k], k === 'strategies' ? '#c9b8ff' : '#e9ecf6', k === 'while' ? 1.3 : 1);
      s.position.set(x, k === 'strategies' ? 22 : 18, z);
      this.scene.add(s);
    }
    const d = textSprite('DISCOVERIES', '#ffe08a', 0.8);
    d.position.set(0, 6, -22);
    this.scene.add(d);
  }

  /** Night or day; returns the theme colour for the status bar. */
  setDay(day) {
    const mode = day ? DAY : NIGHT;
    this.U.uDay.value = day ? 1 : 0;
    this.U.uFog.value.setHex(mode.fog);
    this.U.uFogD.value = mode.density;
    this.scene.background = new THREE.Color(mode.fog);
    this.stars.visible = !day;
    return mode.theme;
  }

  setQuality(q) {
    this.quality = q;
    this.renderer.setPixelRatio(q === 'hq' ? Math.min(window.devicePixelRatio || 1, 2) : 1);
    this.U.uPR.value = this.renderer.getPixelRatio();
    this.mirror.visible = q === 'hq';
    this.flow.geometry.setDrawRange(0, FLOW[q]);
    this.resize();
  }

  resize() {
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight, false);
  }

  /** Dim every building whose index fails keep(i) (search); keep = null shows all. */
  dim(keep) {
    const a = this.mesh.geometry.getAttribute('aData');
    for (let i = 0; i < a.count; i++) a.setW(i, keep && !keep(i) ? 1 : 0);
    a.needsUpdate = true;
  }

  /** What is under a screen point: { index } of a building, { lit: true } for the tower, or null. */
  pick(x, y) {
    const ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((x / window.innerWidth) * 2 - 1, -(y / window.innerHeight) * 2 + 1), this.camera);
    const hit = ray.intersectObjects([this.mesh, this.tower], true)[0];
    if (!hit) return null;
    return hit.object === this.mesh ? { index: hit.instanceId } : { lit: true };
  }

  render(dt) {
    this.U.uTime.value += dt;
    this.tower.rotation.y += dt * 0.15;
    this.renderer.render(this.scene, this.camera);
  }
}
