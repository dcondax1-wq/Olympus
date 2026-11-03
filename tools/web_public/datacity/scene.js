// The Data City's three.js world: the market-clock sky, the wet ground and streets, the skyline (tiles + LOD impostors,
// skyline.js), glow sprites, street trades, the LIT tower, district signs, the harbor, and the effects (fx.js). No DOM beyond
// the canvas and the billboards' canvases; city.js drives it.
import * as THREE from '../jarvis/three.module.min.js';
import { COLORS } from './util.js';
import * as SH from './shaders.js';
import { Skyline, pick } from './skyline.js';
import { Rays, FogLayers, Rain, Traffic, Beam, Billboards } from './fx.js';

const FOG = { night: 0x070a1c, day: 0x9fbbe2, dusk: 0x4a2a4a, storm: 0x2a3140 };
const DENSITY = { night: 0.0024, day: 0.0015 };
const FLOW = { hq: 1600, lq: 420 };
const STARS = { hq: 1800, lq: 450 };
const PINS = 64;

const golden = (i) => (i * 0.6180339) % 1;

function points(attrs, material) {
  const g = new THREE.BufferGeometry();
  for (const [name, [arr, size]] of Object.entries(attrs)) g.setAttribute(name, new THREE.BufferAttribute(arr, size));
  return new THREE.Points(g, material);
}

export function textSprite(text, color, size = 1) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 96;
  const g = c.getContext('2d');
  g.font = '800 44px Orbitron, Rajdhani, -apple-system, system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.shadowColor = color; g.shadowBlur = 18; g.fillStyle = color;
  g.fillText(text.split('').join(String.fromCharCode(8202)), 256, 50);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, fog: false }));
  s.scale.set(16 * size, 3 * size, 1);
  s.renderOrder = 10;
  return s;
}

export class CityScene {
  /** canvas; L: layout(); opts: { quality, winRate (street colours), billboards: [...] } */
  constructor(canvas, L, opts) {
    this.L = L;
    this.quality = opts.quality;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: opts.quality === 'hq', powerPreference: 'high-performance' });
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(FOG.night, DENSITY.night);        // the few built-in materials (piers, rings)
    this.camera = new THREE.PerspectiveCamera(52, 1, 0.5, 3200);
    const v3 = () => new THREE.Vector3();
    this.U = { uTime: { value: 0 }, uFog: { value: new THREE.Color(FOG.night) }, uFogD: { value: DENSITY.night }, uHaze: { value: 0.2 },
               uDay: { value: 0 }, uDusk: { value: 0 }, uToday: { value: 0 }, uWet: { value: 0.6 }, uRain: { value: 0 }, uPR: { value: 1 },
               uAccent: { value: new THREE.Color(0x3fd8ff) }, uSun: { value: v3().set(0, -1, 0) }, uCloud: { value: 0 }, uFlash: { value: 0 } };
    this.flash = 0;
    this.storm = false;
    this.resize();
    this._sky();
    this._ground();
    this.skyline = new Skyline(L, this.U, this.quality);
    this.scene.add(this.skyline.group);
    this._glow();
    this._streets(opts.winRate);
    this._tower();
    this._names();
    this._harbor();
    this._pins();
    this.rays = new Rays(L, this.U); this.scene.add(this.rays.mesh);
    this.fog = new FogLayers(this.U, this.quality); this.scene.add(this.fog.group);
    this.rain = new Rain(this.U, this.quality); this.scene.add(this.rain.lines);
    this.traffic = new Traffic(L, this.U, this.quality); this.scene.add(this.traffic.points);
    this.beam = new Beam(this.U); this.scene.add(this.beam.mesh, this.beam.ring);
    this.boards = new Billboards(this.U, opts.billboards || []); this.scene.add(this.boards.group);
    this.setQuality(opts.quality);
  }

  _sky() {
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(1500, 32, 16), new THREE.ShaderMaterial({ vertexShader: SH.SKY_VS,
      fragmentShader: SH.SKY_FS, uniforms: pick(this.U, 'uSun', 'uDay', 'uDusk', 'uCloud', 'uFlash', 'uAccent'), side: THREE.BackSide, depthWrite: false }));
    this.sky.renderOrder = -1;
    this.scene.add(this.sky);
    const n = STARS.hq, p = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, h = 0.08 + Math.random() * 0.9, r = 1400, flat = Math.sqrt(1 - h * h);
      p.set([Math.cos(a) * r * flat, h * r, Math.sin(a) * r * flat], i * 3);
    }
    this.stars = points({ position: [p, 3] }, new THREE.PointsMaterial({ color: 0xcfd8ff, size: 1.6, sizeAttenuation: false,
      transparent: true, opacity: 0.85, depthWrite: false, fog: false }));
    this.scene.add(this.stars);
  }

  _ground() {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(3000, 3000), new THREE.ShaderMaterial({ vertexShader: SH.GROUND_VS,
      fragmentShader: SH.GROUND_FS, uniforms: pick(this.U, 'uFog', 'uFogD', 'uHaze', 'uDay', 'uTime', 'uWet', 'uRain', 'uAccent'), transparent: true }));
    ground.rotation.x = -Math.PI / 2;
    ground.renderOrder = 0;
    this.scene.add(ground);
  }

  _glow() {
    const hq = this.quality === 'hq', items = this.L.items;
    const lit = [];
    items.forEach((it, i) => {
      const b = it.b || {};
      if (it.kind === 'ship') return;
      if (it.kind !== 'b' || b.cls === 'gold' || it.pulse || b.cls === 'green' || b.td) lit.push(i);
    });
    const n = lit.length, p = new Float32Array(n * 3), c = new Float32Array(n * 3), size = new Float32Array(n), pulse = new Float32Array(n),
          seed = new Float32Array(n), today = new Float32Array(n), col = new THREE.Color();
    lit.forEach((i, k) => {
      const it = items[i], b = it.b || {};
      const always = it.kind !== 'b' || b.cls === 'gold' || it.pulse || (hq && b.cls === 'green');
      p.set([it.x, it.h + 0.35, it.z], k * 3);
      col.setHex(it.color);
      c.set([col.r, col.g, col.b], k * 3);
      size[k] = it.kind === 'd' ? 9 : it.kind === 's' ? 8 : b.cls === 'gold' ? 7 : it.pulse ? 5 : always ? 2.6 : 3.2;
      pulse[k] = it.pulse;
      seed[k] = golden(i);
      today[k] = always ? 0 : b.td === 2 ? 2 : 1;               // 1 / 2: only with the Today layer on (2 = fired, cyan)
    });
    this.glowMat = new THREE.ShaderMaterial({ vertexShader: SH.GLOW_VS, fragmentShader: SH.GLOW_FS, uniforms: pick(this.U, 'uTime', 'uPR', 'uDay', 'uToday'),
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    const glow = points({ position: [p, 3], aColor: [c, 3], aSize: [size, 1], aPulse: [pulse, 1], aSeed: [seed, 1], aToday: [today, 1] }, this.glowMat);
    glow.renderOrder = 3;
    glow.frustumCulled = false;
    this.scene.add(glow);
  }

  _streets(winRate) {
    const segs = this.L.streets, m4 = new THREE.Matrix4(), up = new THREE.Vector3(0, 1, 0), col = new THREE.Color();
    const roadGeo = new THREE.PlaneGeometry(1, 1);
    roadGeo.rotateX(-Math.PI / 2);
    const roads = new THREE.InstancedMesh(roadGeo, new THREE.ShaderMaterial({ vertexShader: SH.ROAD_VS, fragmentShader: SH.ROAD_FS,
      uniforms: pick(this.U, 'uFog', 'uFogD', 'uHaze', 'uDay', 'uTime', 'uWet', 'uAccent'), transparent: true, depthWrite: false }), segs.length);
    const q = new THREE.Quaternion();
    segs.forEach(([x0, z0, x1, z1], i) => {
      q.setFromAxisAngle(up, -Math.atan2(z1 - z0, x1 - x0));
      m4.compose(new THREE.Vector3((x0 + x1) / 2, 0.03, (z0 + z1) / 2), q, new THREE.Vector3(Math.hypot(x1 - x0, z1 - z0), 1, 1.9));
      roads.setMatrixAt(i, m4);
    });
    roads.renderOrder = 1;
    roads.frustumCulled = false;
    this.scene.add(roads);
    const n = FLOW.hq, seg = new Float32Array(n * 4), c = new Float32Array(n * 3), move = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      let s = segs[i % segs.length];
      if (Math.random() < 0.5) s = [s[2], s[3], s[0], s[1]];
      const lane = (Math.random() - 0.5) * 1.2, dx = s[2] - s[0], dz = s[3] - s[1], len = Math.hypot(dx, dz) || 1;
      const nx = (-dz / len) * lane, nz = (dx / len) * lane;
      seg.set([s[0] + nx, s[1] + nz, s[2] + nx, s[3] + nz], i * 4);
      col.setHex(Math.random() < winRate ? COLORS.win : COLORS.loss);
      c.set([col.r, col.g, col.b], i * 3);
      move.set([((0.6 + Math.random() * 0.8) * 6) / len, Math.random()], i * 2);
    }
    this.flow = points({ position: [new Float32Array(n * 3), 3], aSeg: [seg, 4], aColor: [c, 3], aMove: [move, 2] },
      new THREE.ShaderMaterial({ vertexShader: SH.FLOW_VS, fragmentShader: SH.FLOW_FS, uniforms: pick(this.U, 'uTime', 'uPR', 'uDay'),
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.flow.frustumCulled = false;
    this.flow.renderOrder = 3;
    this.scene.add(this.flow);
  }

  _tower() {
    this.tower = new THREE.Group();
    const tm = new THREE.ShaderMaterial({ vertexShader: SH.TOWER_VS, fragmentShader: SH.TOWER_FS, uniforms: pick(this.U, 'uTime', 'uDay', 'uAccent') });
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 3.4, 40, 8, 1), tm);
    shaft.position.y = 20;
    const spire = new THREE.Mesh(new THREE.ConeGeometry(1.5, 9, 8), tm);
    spire.position.y = 44.5;
    this.tower.add(shaft, spire);
    const ringGeo = [[12, 5.5], [26, 4.4], [38, 3.3]].map(([y, r]) => { const g = new THREE.TorusGeometry(r, 0.09, 6, 64); g.rotateX(Math.PI / 2); g.translate(0, y, 0); return g; });
    const merged = mergeSimple(ringGeo);
    this.tower.add(new THREE.Mesh(merged, new THREE.MeshBasicMaterial({ color: COLORS.lit, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false })));
    const name = textSprite('LIT · ZLARIOR', '#7fe9ff', 0.9);
    name.position.set(0, 53, 0);
    this.tower.add(name);
    this.scene.add(this.tower);
    const beacon = points({ position: [new Float32Array([0, 49, 0]), 3], aColor: [new Float32Array([0.25, 0.85, 1.0]), 3], aSize: [new Float32Array([26]), 1],
                            aPulse: [new Float32Array([1]), 1], aSeed: [new Float32Array([0.2]), 1], aToday: [new Float32Array([0]), 1] }, this.glowMat);
    beacon.renderOrder = 3;
    this.scene.add(beacon);
  }

  _names() {
    this.signs = [];
    for (const d of this.L.districts) {
      const s = textSprite(d.name, d.css || '#e9ecf6', Math.max(0.9, Math.min(2.4, d.half / 34)));
      s.position.set(d.cx, d.kind === 'harbor' ? 8 : 16 + Math.min(30, d.half * 0.3), d.cz);
      this.scene.add(s);
      this.signs.push(s);
    }
    const disc = textSprite('DISCOVERIES', '#ffe08a', 0.8);
    disc.position.set(0, 6, -22);
    this.scene.add(disc);
  }

  _harbor() {
    const h = this.L.harbor;
    if (!h) return;
    const w = new THREE.Mesh(new THREE.PlaneGeometry(h.x1 - h.x0, h.z1 - h.z0 + 8), new THREE.ShaderMaterial({ vertexShader: SH.WATER_VS,
      fragmentShader: SH.WATER_FS, uniforms: pick(this.U, 'uFog', 'uFogD', 'uHaze', 'uTime', 'uDay', 'uAccent') }));
    w.rotation.x = -Math.PI / 2;
    w.position.set((h.x0 + h.x1) / 2, 0.05, (h.z0 + h.z1) / 2);
    w.renderOrder = 1;
    this.scene.add(w);
    const pier = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 0.3, 1.2), new THREE.MeshBasicMaterial({ color: 0x1c2442 }), h.piers);
    const m4 = new THREE.Matrix4();
    for (let k = 0; k < h.piers; k++) { m4.makeScale(h.x1 - h.x0 - 20, 1, 1).setPosition((h.x0 + h.x1) / 2, 0.15, h.z0 + 7 + k * 7 - 2.2); pier.setMatrixAt(k, m4); }
    pier.renderOrder = 2;
    this.scene.add(pier);
  }

  _pins() {
    const p = new Float32Array(PINS * 3), c = new Float32Array(PINS * 3), s = new Float32Array(PINS), z = new Float32Array(PINS);
    for (let i = 0; i < PINS; i++) { c.set([1, 0.85, 0.4], i * 3); s[i] = 10; }
    this.pins = points({ position: [p, 3], aColor: [c, 3], aSize: [s, 1], aPulse: [new Float32Array(PINS).fill(1), 1], aSeed: [z, 1], aToday: [z.slice(), 1] }, this.glowMat);
    this.pins.frustumCulled = false;
    this.pins.renderOrder = 6;
    this.pins.geometry.setDrawRange(0, 0);
    this.scene.add(this.pins);
  }

  /** Gold beacons over the watched buildings (item indices). */
  setPins(list) {
    const a = this.pins.geometry.getAttribute('position'), items = this.L.items;
    const k = Math.min(PINS, list.length);
    for (let i = 0; i < k; i++) { const it = items[list[i]]; a.array.set([it.x, it.h + 2.2, it.z], i * 3); }
    a.needsUpdate = true;
    this.pins.geometry.setDrawRange(0, k);
  }

  /** The market clock: sun from sky.sunOf(); weather from sky.weatherOf(). */
  setSun(sun, weather) {
    const U = this.U, w = weather || { haze: 0.2, rain: 0, storm: false };
    const el = sun.elev, az = sun.azim;
    U.uSun.value.set(-Math.cos(az), Math.max(-1, el), -Math.sin(az) * 0.6).normalize();
    U.uDay.value = sun.day * (1 - w.haze * 0.35);
    U.uDusk.value = sun.dusk * (1 - w.haze * 0.6);
    U.uCloud.value = w.storm ? 0.85 : w.rain > 0 ? 0.6 : w.haze * 0.4;
    U.uHaze.value = 0.15 + w.haze;
    U.uWet.value = Math.min(1, 0.45 + w.rain * 0.8);
    U.uRain.value = w.rain;
    const fog = new THREE.Color(FOG.night).lerp(new THREE.Color(FOG.day), sun.day).lerp(new THREE.Color(FOG.dusk), sun.dusk * 0.35 * (1 - sun.day));
    if (w.storm || w.rain > 0) fog.lerp(new THREE.Color(FOG.storm), 0.35 + w.rain * 0.2);
    U.uFog.value.copy(fog);
    U.uFogD.value = (DENSITY.night + (DENSITY.day - DENSITY.night) * sun.day) * (1 + w.haze * 0.5);
    this.scene.background = fog;
    this.scene.fog.color.copy(fog);
    this.scene.fog.density = U.uFogD.value;
    this.stars.material.opacity = 0.85 * (1 - sun.day) * (1 - U.uCloud.value * 0.8);
    this.stars.visible = this.stars.material.opacity > 0.02;
    this.rain.set(w.rain);
    this.fog.setHaze(w.haze);
    this.storm = !!w.storm;
    return '#' + fog.getHexString();
  }

  setToday(on) { this.U.uToday.value = on ? 1 : 0; }

  /** The theme's accent (olympus.theme or applyTheme): plaza glow, water and tower tint, the sky's city glow. */
  setAccent(hex) { try { this.U.uAccent.value.set(hex); } catch (e) { /* a bad token: keep the last */ } }

  setQuality(q) {
    this.quality = q;
    const O = window.OLYMPUS;
    this.renderer.setPixelRatio(O ? O.dpr(q === 'lq') : (q === 'hq' ? Math.min(window.devicePixelRatio || 1, 2) : 1));
    this.U.uPR.value = this.renderer.getPixelRatio();
    this.flow.geometry.setDrawRange(0, FLOW[q]);
    this.stars.geometry.setDrawRange(0, STARS[q]);
    this.skyline.setQuality(q);
    this.fog.setQuality(q);
    this.rain.setQuality(q);
    this.traffic.setQuality(q);
    this.resize();
  }

  resize() {
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight, false);
  }

  /** What is under a screen point: { item }, { block }, { lit: true } for the tower, or null. */
  pick(x, y) {
    const ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((x / window.innerWidth) * 2 - 1, -(y / window.innerHeight) * 2 + 1), this.camera);
    const t = ray.intersectObject(this.tower, true)[0];
    const s = this.skyline.pick(ray);
    if (t && (!s || t.distance < s.distance)) return { lit: true };
    return s;
  }

  render(dt) {
    const U = this.U;
    U.uTime.value += dt;
    this.tower.rotation.y += dt * 0.15;
    this.skyline.update(this.camera);
    this.rays.update(U.uTime.value);
    this.rain.update(this.camera);
    this.beam.update(dt);
    this.boards.update(dt);
    if (this.storm) {                                         // lightning: a flash now and then, decaying fast
      if (this.flash <= 0 && Math.random() < dt * 0.18) this.flash = 1;
      this.flash = Math.max(0, this.flash - dt * 3.2);
      U.uFlash.value = this.flash > 0 ? this.flash * (0.6 + 0.4 * Math.sin(U.uTime.value * 60)) : 0;
    } else U.uFlash.value = 0;
    this.renderer.render(this.scene, this.camera);
  }
}

/** Indexed geometries with the same attributes merged into one (three's BufferGeometryUtils is not in the core build). */
function mergeSimple(list) {
  const out = new THREE.BufferGeometry(), names = Object.keys(list[0].attributes), idx = [];
  let base = 0;
  for (const k of names) {
    const size = list[0].attributes[k].itemSize;
    const arr = new Float32Array(list.reduce((a, g) => a + g.attributes[k].array.length, 0));
    let o = 0;
    for (const g of list) { arr.set(g.attributes[k].array, o); o += g.attributes[k].array.length; }
    out.setAttribute(k, new THREE.BufferAttribute(arr, size));
  }
  for (const g of list) { for (const i of g.index.array) idx.push(base + i); base += g.attributes.position.count; }
  out.setIndex(idx);
  return out;
}
