// ATHENS scene: the giant Greek metropolis in three.js. One WebGL renderer, no post passes, no shadow maps.
// Draw calls on a phone: terrain 1, sky 1, sea 1, river 1, stone batch 1, metal batch 1, house chunks <= 16 (frustum culled, near / far LOD),
// trees 2, ships 1, stalls inside the stone batch, lamps 1, windows 1, beacon 2, selection 2: about 35 at most, usually fewer than 25.
// Scenery only: it draws no trade, no money value and places no order.
import * as THREE from '../jarvis/three.module.min.js';
import { planAthens, groundY, COAST, RIVER, RIVER_W, WALL, insideWall, ACROPOLIS, isSea, LOT, WORLD } from './athens-plan.js';
import { buildStatic } from './athens-build.js';
import { Batch, PAL, unit } from './athens-geo.js';
import { rng, hash32 } from './util.js';

export const TIERS = { // house cap, trees, lamps, windows
  low: { houses: 520, trees: 150, lamps: 120, windows: 100, dpr: 1.25, ships: false, fps: 30 },
  high: { houses: 1100, trees: 420, lamps: 360, windows: 260, dpr: 2, ships: true, fps: 60 },
  ultra: { houses: 1800, trees: 520, lamps: 420, windows: 400, dpr: 2, ships: true, fps: 60 },
};
// Colour temperatures, 3500 K by day and 2700 K at dusk (both warm, never blue-white).
const KELVIN = { 3500: [1, .769, .537], 3000: [1, .706, .42], 2700: [1, .663, .341] };
const lerp = (a, b, t) => a + (b - a) * t;
const mixC = (a, b, t) => new THREE.Color(a).lerp(new THREE.Color(b), t);
const SKY = { // zenith, mid, horizon
  day: ['#6f9bb8', '#cdbf9a', '#f3dba8'], dusk: ['#3a3452', '#9a5b62', '#f0a366'],
};

function terrain(tier) {
  const edges = []; for (let x = WORLD.x0; x < WORLD.x1;) { edges.push(x); const ax = Math.abs(x); x += ax < 640 ? (tier === 'low' ? 24 : 16) : ax < 820 ? (tier === 'low' ? 80 : 40) : 130; } edges.push(WORLD.x1);
  const nx = edges.length, pos = new Float32Array(nx * nx * 3), col = new Float32Array(nx * nx * 3), idx = [];
  const C = (h) => new THREE.Color(h);
  const paved = C('#b6a687'), dust = C('#a49c6a'), olive = C('#8d9158'), rock = C('#9a8d76'), top = C('#d0c2a2'), sand = C('#d9c796'), sea = C('#7a9892'), farRock = C('#8a7c68'), hill = C('#a79a78');
  const tmp = new THREE.Color(), r = rng(hash32('terrain'));
  for (let j = 0; j < nx; j++) for (let i = 0; i < nx; i++) {
    const x = edges[i], z = edges[j], y = groundY(x, z), k = (j * nx + i) * 3;
    pos[k] = x; pos[k + 1] = y; pos[k + 2] = z;
    const n = .94 + .12 * r(), rr = Math.hypot(x, z);
    if (y < -.6) tmp.copy(sea);
    else if (y < .2 && z > COAST(x) - 30) tmp.copy(sand);
    else if (Math.hypot(x - ACROPOLIS.x, z - ACROPOLIS.z) < ACROPOLIS.base + 4) tmp.copy(y > 44 ? top : y > 8 ? hill : rock).lerp(rock, Math.max(0, 1 - y / 40) * .25);
    else if (insideWall(x, z, 1.0)) tmp.copy(paved);
    else if (y > 30) tmp.copy(farRock).lerp(rock, Math.max(0, 1 - y / 150));
    else tmp.copy(dust).lerp(olive, .5 + .5 * Math.sin(x * .02 + z * .013));
    if (rr > 900) tmp.lerp(farRock, Math.min(1, (rr - 900) / 400));
    col[k] = tmp.r * n; col[k + 1] = tmp.g * n; col[k + 2] = tmp.b * n;
  }
  for (let j = 0; j < nx - 1; j++) for (let i = 0; i < nx - 1; i++) { const a = j * nx + i, b = a + 1, d = a + nx, c = d + 1; idx.push(a, d, b, b, d, c); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.setIndex(idx); g.computeVertexNormals();
  return g;
}

const WATER_VS = `varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`;
const WATER_FS = `uniform float uTime; uniform vec3 uDeep, uShallow, uSun, uSky, uFog; uniform vec3 uSunDir; uniform float uFogD, uMove;
varying vec3 vW;
void main(){
  float t = uTime*uMove;
  vec3 n = normalize(vec3(sin(vW.x*.09+t*1.1)*.06+sin(vW.z*.15-t*1.4)*.05+sin((vW.x+vW.z)*.31+t*2.)*.02, 1., cos(vW.z*.11+t)*.05+sin(vW.x*.2-t*1.7)*.03));
  vec3 v = normalize(cameraPosition - vW);
  float fres = pow(1. - clamp(dot(v, n), 0., 1.), 3.);
  vec3 h = normalize(uSunDir + v); float spec = pow(max(dot(n, h), 0.), 90.);
  vec3 c = mix(uDeep, uShallow, .5 + .5*sin(vW.x*.013 + vW.z*.017)) ;
  c = mix(c, uSky, clamp(fres*.8, 0., .85)) + uSun*spec*.8;
  float d = length(cameraPosition - vW); float f = 1. - exp(-d*d*uFogD*uFogD);
  gl_FragColor = vec4(mix(c, uFog, clamp(f,0.,1.)), .93);
  #include <colorspace_fragment>
}`;
const SKY_VS = `varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); gl_Position.z = gl_Position.w; }`;
const SKY_FS = `uniform vec3 uTop, uMid, uHor, uSun, uSunDir; varying vec3 vD;
void main(){
  float h = clamp(vD.y, -.1, 1.);
  vec3 c = mix(uHor, uMid, smoothstep(0., .22, h)); c = mix(c, uTop, smoothstep(.15, .85, h));
  float s = max(dot(normalize(vD), uSunDir), 0.);
  c += uSun*(pow(s, 600.)*1.3 + pow(s, 14.)*.28);
  gl_FragColor = vec4(c, 1.);
  #include <colorspace_fragment>
}`;

export class Athens {
  constructor(canvas, opts = {}) {
    this.canvas = canvas; this.tierName = opts.tier || 'high'; this.T = TIERS[this.tierName] || TIERS.high;
    this.reduced = !!opts.reduced; this.time = opts.dusk ? 1 : 0; this.target = this.time;
    this.plan = planAthens();
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: this.tierName !== 'low', powerPreference: 'high-performance', alpha: false });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace; this.renderer.toneMapping = THREE.NoToneMapping;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(52, 1, 1.5, 4200);
    this.u = { uTime: { value: 0 } };
    this.hemi = new THREE.HemisphereLight('#cfe0ea', '#8a7658', 1.0); this.sun = new THREE.DirectionalLight('#ffc489', 2.4);
    this.scene.add(this.hemi, this.sun, this.sun.target);
    this.scene.fog = new THREE.FogExp2('#e8d2a4', .0004);
    this.cam = { tx: -20, ty: 8, tz: 40, yaw: 2.55, pitch: .5, dist: 980 };
    this.fly = null; this.tour = null; this.anchors = []; this.sel = null; this.frameCount = 0; this.calls = 0;
    this.build();
    this.applyTime(); this.placeCamera();
  }

  build() {
    const plan = this.plan, T = this.T, scene = this.scene;
    this.dispose_ = [];
    const own = (o) => { this.dispose_.push(o); return o; };
    // sky
    this.skyU = { uTop: { value: new THREE.Color() }, uMid: { value: new THREE.Color() }, uHor: { value: new THREE.Color() }, uSun: { value: new THREE.Color() }, uSunDir: { value: new THREE.Vector3(0, .5, -.8) } };
    const sky = new THREE.Mesh(own(new THREE.SphereGeometry(3000, 24, 12)), own(new THREE.ShaderMaterial({ vertexShader: SKY_VS, fragmentShader: SKY_FS, uniforms: this.skyU, side: THREE.BackSide, depthWrite: false, fog: false })));
    sky.frustumCulled = false; sky.renderOrder = -10; scene.add(sky); this.sky = sky;
    // terrain
    const tm = own(new THREE.MeshLambertMaterial({ vertexColors: true })); const ter = new THREE.Mesh(own(terrain(this.tierName)), tm); scene.add(ter);
    // water: the sea and the river share one material
    this.wU = { uTime: this.u.uTime, uDeep: { value: new THREE.Color('#2f5f78') }, uShallow: { value: new THREE.Color('#5c97a2') }, uSun: { value: new THREE.Color('#ffd9a0') }, uSky: { value: new THREE.Color('#d8c9a5') }, uFog: { value: new THREE.Color('#e8d2a4') }, uSunDir: { value: new THREE.Vector3(0, .5, -.8) }, uFogD: { value: .0004 }, uMove: { value: this.reduced ? 0 : 1 } };
    const wm = own(new THREE.ShaderMaterial({ vertexShader: WATER_VS, fragmentShader: WATER_FS, uniforms: this.wU, transparent: true }));
    const sea = new THREE.Mesh(own(new THREE.PlaneGeometry(2600, 1100).rotateX(-Math.PI / 2)), wm); sea.position.set(0, -.25, 790); scene.add(sea);
    const curve = new THREE.CatmullRomCurve3(RIVER.map(([x, z]) => new THREE.Vector3(x, 0, z)), false, 'centripetal'), N = 90, rp = [], ri = [];
    for (let i = 0; i <= N; i++) { const p = curve.getPoint(i / N), t = curve.getTangent(i / N), nx = -t.z, nz = t.x, l = Math.hypot(nx, nz) || 1; const w = RIVER_W * .5 * (.85 + .3 * (i / N)); rp.push(p.x + nx / l * w, -.55, p.z + nz / l * w, p.x - nx / l * w, -.55, p.z - nz / l * w); if (i < N) { const a = i * 2; ri.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } }
    const rg = own(new THREE.BufferGeometry()); rg.setAttribute('position', new THREE.Float32BufferAttribute(rp, 3)); rg.setIndex(ri); scene.add(new THREE.Mesh(rg, wm));
    // monuments in two draws
    const built = buildStatic(plan, this.tierName === 'low'); this.tris = built.tris;
    const sm = own(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }));
    const mm = own(this.tierName === 'low' ? new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }) : new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 70, specular: new THREE.Color('#f0d9a0'), side: THREE.DoubleSide }));
    scene.add(new THREE.Mesh(own(built.stone), sm), new THREE.Mesh(own(built.metal), mm));
    this.houses(own, sm);
    this.trees(own, sm);
    this.shipsInit(own, sm);
    this.lights(own);
    // anchors: every app temple and every monument can be tapped
    for (const a of plan.apps) this.anchors.push({ kind: 'app', id: a.id, appId: a.id, name: a.name, group: a.group, x: a.x, y: a.top || 12, z: a.z, colour: a.colour, blurb: a.blurb });
    for (const l of plan.landmarks) this.anchors.push({ kind: 'landmark', id: l.id, appId: l.app || null, name: l.name, group: l.group, x: l.x, y: l.top || 14, z: l.z, blurb: l.blurb, major: true });
    // selection ring + beam
    const rm = new THREE.MeshBasicMaterial({ color: '#e8bb55', transparent: true, opacity: .9, depthWrite: false, fog: false }), bm = new THREE.MeshBasicMaterial({ color: '#e8bb55', transparent: true, opacity: .22, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
    this.ring = new THREE.Mesh(own(new THREE.TorusGeometry(1, .04, 6, 40).rotateX(Math.PI / 2)), rm); this.beam = new THREE.Mesh(own(new THREE.CylinderGeometry(1, 1, 1, 12, 1, true).translate(0, .5, 0)), bm);
    this.ring.visible = this.beam.visible = false; this.ring.frustumCulled = this.beam.frustumCulled = false; scene.add(this.ring, this.beam); own(rm); own(bm);
  }

  houses(own, sm) {
    const cap = this.T.houses, rows = this.plan.houses.slice(0, cap), size = 280, chunks = new Map(), tones = [[1, 1, 1], [.96, .9, .8], [.98, .86, .68], [.96, .8, .72], [.88, .93, .97], [1, .94, .82]];
    const tint = { trading: [1.02, .98, .86], research: [.94, .98, 1.04], money: [1.04, .94, .84], life: [.98, 1.02, .88] };
    for (const h of rows) { const key = `${Math.floor(h.x / size)}:${Math.floor(h.z / size)}`; (chunks.get(key) || chunks.set(key, []).get(key)).push(h); }
    const near = unit.house(), far = unit.houseFar(), mat = own(new THREE.MeshLambertMaterial({ vertexColors: true })), farMat = mat;
    const d = new THREE.Object3D(), color = new THREE.Color(); this.chunks = [];
    for (const [, list] of chunks) {
      const mk = (geo) => { const m = new THREE.InstancedMesh(geo, mat, list.length); m.frustumCulled = true; return m; };
      const a = mk(near), b = mk(far); let cx = 0, cz = 0;
      list.forEach((h, i) => {
        d.position.set(h.x, h.y, h.z); d.rotation.set(0, h.tone > .5 ? 0 : Math.PI / 2, 0); d.scale.set(h.w, h.h, h.d); d.updateMatrix(); a.setMatrixAt(i, d.matrix); b.setMatrixAt(i, d.matrix);
        const t = tones[Math.floor(h.tone * 6) % 6], g = tint[h.dist] || [1, 1, 1]; color.setRGB(t[0] * g[0], t[1] * g[1], t[2] * g[2]); a.setColorAt(i, color); b.setColorAt(i, color); cx += h.x; cz += h.z;
      });
      for (const m of [a, b]) { m.instanceMatrix.needsUpdate = true; m.instanceColor.needsUpdate = true; m.computeBoundingSphere(); }
      b.visible = false; this.scene.add(a, b); this.chunks.push({ a, b, cx: cx / list.length, cz: cz / list.length });
    }
    void sm; void farMat; this.houseCount = rows.length;
  }

  trees(own, sm) {
    const B = new Batch(), O = new Batch();
    B.put(unit.cyl(5, .7), 0, 0, 0, .35, 2.2, .35, PAL.timber); B.put(unit.ico(), 0, 1.7, 0, 2.6, 2.6, 2.6, PAL.olive, 0, 0, 0, .3);
    O.put(unit.cyl(4, .6), 0, 0, 0, .3, 1.2, .3, PAL.timber); O.put(unit.cone(6), 0, .8, 0, 1.4, 9, 1.4, PAL.cypress, 0, 0, 0, .35);
    const list = this.plan.trees.slice(0, this.T.trees), oliveL = list.filter((t) => !t.cypress), cyp = list.filter((t) => t.cypress), d = new THREE.Object3D();
    const mat = own(new THREE.MeshLambertMaterial({ vertexColors: true }));
    for (const [batch, arr] of [[B, oliveL], [O, cyp]]) {
      if (!arr.length) continue;
      const m = new THREE.InstancedMesh(own(batch.geometry()), mat, arr.length); m.frustumCulled = false;
      arr.forEach((t, i) => { d.position.set(t.x, t.y, t.z); d.rotation.set(0, i * 2.4, 0); d.scale.setScalar(t.s); d.updateMatrix(); m.setMatrixAt(i, d.matrix); }); m.instanceMatrix.needsUpdate = true; this.scene.add(m);
    }
    void sm;
  }

  shipsInit(own) {
    const S = new Batch();
    S.box(0, 0, 0, 3.2, 1.7, 12, PAL.timber); S.put(unit.cone(5), 0, .6, 6, 1.6, 4, 1.1, PAL.timber, 0, Math.PI / 2); S.box(0, 1.3, -6.4, 2.6, 2.4, 1.1, PAL.timberD || PAL.timber);
    S.box(0, 1.7, 0, 2.6, .35, 10.5, PAL.sand); S.cyl(0, 1.7, 1.5, .18, 9.4, PAL.bronzeD, 5); S.box(0, 6.8, 1.5, 6.2, .22, .22, PAL.timber);
    S.box(0, 3.1, 1.5, 5.6, 3.8, .14, '#efe5cf'); S.box(0, 4.6, 1.56, 5.6, .5, .14, PAL.terra);
    for (let i = 0; i < 5; i++) for (const e of [-1, 1]) S.put(unit.box(), e * 1.9, .7, -3.6 + i * 1.8, .14, .14, 3, PAL.timber, 0, 0, e * .5);
    S.cone(0, 1.7, 7.7, .4, 1.2, PAL.gold, 5);
    this.shipGeo = own(S.geometry()); const n = this.plan.ships.length;
    this.shipMesh = new THREE.InstancedMesh(this.shipGeo, own(new THREE.MeshLambertMaterial({ vertexColors: true })), n); this.shipMesh.frustumCulled = false; this.scene.add(this.shipMesh);
    this.shipD = new THREE.Object3D(); this.shipsTick(0);
  }
  shipsTick(t) {
    const move = this.T.ships && !this.reduced; this.plan.ships.forEach((s, i) => {
      const d = this.shipD; let x = s.x, z = s.z, yaw = Math.PI * .5 + Math.sin(s.ph) * .3;
      if (move && s.speed) { const a = t * .03 + s.ph; x = 40 + Math.cos(a) * 190; z = 420 + Math.sin(a) * 52 + 40; yaw = Math.atan2(-Math.sin(a) * 190, Math.cos(a) * 52) ; }
      else if (move) { yaw += Math.sin(t * .4 + s.ph) * .05; z += Math.sin(t * .6 + s.ph) * .35; }
      d.position.set(x, -.2 + (move ? Math.sin(t * 1.3 + s.ph) * .18 : 0), z); d.rotation.set(0, yaw, move ? Math.sin(t * .9 + s.ph) * .04 : 0); d.scale.setScalar(s.scale); d.updateMatrix(); this.shipMesh.setMatrixAt(i, d.matrix);
    }); this.shipMesh.instanceMatrix.needsUpdate = true;
  }

  lights(own) {
    const r = rng(hash32('athens:lamps')), lp = [], wp = [], plan = this.plan;
    for (let i = -17; i <= 17; i++) for (let j = -14; j <= 10; j++) {
      const x = i * LOT, z = j * LOT;
      if (!(i % 5 === 0 && j % 5 === 0) && !(i % 5 === 0 && j % 2 === 0) && !(j % 5 === 0 && i % 2 === 0)) continue;
      if (!insideWall(x, z, .94) || isSea(x, z + 20) || Math.hypot(x - ACROPOLIS.x, z - ACROPOLIS.z) < ACROPOLIS.base) continue;
      lp.push(x + 8, 3.4, z + 8);
    }
    for (const a of plan.apps) lp.push(a.x - 8.6, 3, a.z + 9.4, a.x + 8.6, 3, a.z + 9.4);
    for (const h of plan.houses.slice(0, this.T.houses)) if (r() < .34) wp.push(h.x + (r() - .5) * h.w * .6, h.y + 1.8, h.z + h.d / 2 + .25);
    const c = document.createElement('canvas'); c.width = c.height = 64; const cx = c.getContext('2d'), gr = cx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(.35, 'rgba(255,255,255,.55)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); cx.fillStyle = gr; cx.fillRect(0, 0, 64, 64);
    const tex = own(new THREE.CanvasTexture(c)); tex.colorSpace = THREE.SRGBColorSpace;
    const pt = (arr, cap, size, op) => {
      const g = own(new THREE.BufferGeometry()); g.setAttribute('position', new THREE.Float32BufferAttribute(arr.slice(0, cap * 3), 3));
      const m = own(new THREE.PointsMaterial({ map: tex, color: '#ffb35c', size, sizeAttenuation: true, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
      const p = new THREE.Points(g, m); p.frustumCulled = false; p.userData.max = op; this.scene.add(p); return p;
    };
    this.lamps = pt(lp, this.T.lamps, 4.5, .95); this.windows = pt(wp, this.T.windows, 2.4, .9);
    // the lighthouse beacon: a warm glow and a slow turning beam, visible at dusk
    const L = plan.landmarks.find((l) => l.id === 'lighthouse'), b = L.beacon || [L.x, 55, L.z];
    const bm = own(new THREE.MeshBasicMaterial({ color: '#ffc46a', transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false }));
    this.beacon = new THREE.Mesh(own(new THREE.ConeGeometry(16, 150, 14, 1, true).rotateZ(Math.PI / 2).translate(75, 0, 0)), bm); this.beacon.position.set(...b); this.beacon.frustumCulled = false; this.beacon.userData.max = .22; this.scene.add(this.beacon);
    const gm = own(new THREE.PointsMaterial({ map: tex, color: '#ffd27a', size: 30, sizeAttenuation: true, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
    const gg = own(new THREE.BufferGeometry()); gg.setAttribute('position', new THREE.Float32BufferAttribute(b, 3)); this.glow = new THREE.Points(gg, gm); this.glow.userData.max = .8; this.scene.add(this.glow);
  }

  // ------------------------------------------------------------------ light and sky (day 3500 K, dusk 2700 K)
  setDusk(on) { this.target = on ? 1 : 0; this.fade = { from: this.time, t0: performance.now() }; if (this.reduced) { this.time = this.target; this.applyTime(); this.fade = null; } }
  applyTime() {
    const t = this.time, k = (a) => new THREE.Color().setRGB(...a);
    const sunC = k(KELVIN[3500]).lerp(k(KELVIN[2700]), t), elev = lerp(.82, .17, t), az = lerp(-.5, -1.1, t);
    const dir = new THREE.Vector3(Math.sin(az) * Math.cos(elev), Math.sin(elev), -Math.cos(az) * Math.cos(elev)).normalize();
    this.sun.color.copy(sunC); this.sun.intensity = lerp(2.9, 2.2, t); this.sun.position.copy(dir).multiplyScalar(900); this.sun.target.position.set(0, 0, 0);
    this.hemi.color.copy(mixC('#dfe6e8', '#8a7aa0', t)); this.hemi.groundColor.copy(mixC('#9a8566', '#4a3a34', t)); this.hemi.intensity = lerp(1.25, .85, t);
    const top = mixC(SKY.day[0], SKY.dusk[0], t), mid = mixC(SKY.day[1], SKY.dusk[1], t), hor = mixC(SKY.day[2], SKY.dusk[2], t);
    this.skyU.uTop.value.copy(top); this.skyU.uMid.value.copy(mid); this.skyU.uHor.value.copy(hor); this.skyU.uSun.value.copy(sunC); this.skyU.uSunDir.value.copy(dir);
    this.scene.fog.color.copy(mixC('#e8d2a4', '#c88a68', t)); this.scene.fog.density = lerp(.00042, .00052, t);
    const w = this.wU; w.uFog.value.copy(this.scene.fog.color); w.uFogD.value = this.scene.fog.density; w.uSky.value.copy(hor.clone().lerp(mid, .3)); w.uSun.value.copy(sunC); w.uSunDir.value.copy(dir);
    w.uDeep.value.copy(mixC('#2f5f78', '#2a3a58', t)); w.uShallow.value.copy(mixC('#5c97a2', '#5a6f86', t));
    const night = Math.max(0, (t - .25) / .75);
    for (const o of [this.lamps, this.windows, this.beacon, this.glow]) if (o) o.material.opacity = o.userData.max * night;
  }

  // ------------------------------------------------------------------ camera
  placeCamera() {
    const c = this.cam, cp = Math.cos(c.pitch);
    this.camera.position.set(c.tx + Math.sin(c.yaw) * cp * c.dist, c.ty + Math.sin(c.pitch) * c.dist, c.tz + Math.cos(c.yaw) * cp * c.dist);
    const floor = groundY(this.camera.position.x, this.camera.position.z); if (this.camera.position.y < floor + 4) this.camera.position.y = floor + 4;
    this.camera.lookAt(c.tx, c.ty, c.tz);
  }
  orbit(dx, dy) { const c = this.cam; c.yaw -= dx * .0062; c.pitch = Math.max(.06, Math.min(1.45, c.pitch + dy * .0052)); }
  zoom(f) { const c = this.cam; c.dist = Math.max(22, Math.min(1500, c.dist * f)); }
  pan(dx, dy) {
    const c = this.cam, s = c.dist * .0017, rx = Math.cos(c.yaw), rz = -Math.sin(c.yaw), fx = -Math.sin(c.yaw), fz = -Math.cos(c.yaw);
    c.tx = Math.max(-760, Math.min(760, c.tx - (rx * dx + fx * -dy) * s)); c.tz = Math.max(-700, Math.min(660, c.tz - (rz * dx + fz * -dy) * s)); c.ty = Math.max(0, groundY(c.tx, c.tz));
  }
  flyTo(x, z, o = {}) {
    this.tour = null; const c = this.cam, y = o.y ?? Math.max(0, groundY(x, z));
    let yaw = o.yaw ?? c.yaw; const dy = ((yaw - c.yaw + Math.PI * 3) % (Math.PI * 2)) - Math.PI; yaw = c.yaw + dy;
    this.fly = { from: { ...c }, to: { tx: x, ty: y + (o.lift || 0), tz: z, yaw, pitch: o.pitch ?? Math.max(.38, Math.min(.7, c.pitch)), dist: o.dist ?? 130 }, t: 0, dur: o.dur ?? 1.5 };
    if (this.reduced) this.fly.dur = .01;
  }
  startTour(tour) {
    this.fly = null; const V = (a) => a.map((p) => new THREE.Vector3(...p));
    this.tour = { def: tour, cam: new THREE.CatmullRomCurve3(V(tour.cam), false, 'catmullrom', .4), look: new THREE.CatmullRomCurve3(V(tour.look), false, 'catmullrom', .4), t: 0 };
  }
  stopTour() { if (!this.tour) return; const T = this.tour; this.tour = null; this.syncFromCamera(T.look.getPoint(Math.min(1, T.t / T.def.secs))); }
  syncFromCamera(look) {
    const p = this.camera.position, c = this.cam, dx = p.x - look.x, dy = p.y - look.y, dz = p.z - look.z;
    c.tx = look.x; c.ty = look.y; c.tz = look.z; c.dist = Math.max(30, Math.hypot(dx, dy, dz)); c.yaw = Math.atan2(dx, dz); c.pitch = Math.max(.06, Math.min(1.45, Math.asin(dy / c.dist)));
  }
  get touring() { return !!this.tour; }
  get progress() { return this.tour ? this.tour.t / this.tour.def.secs : 0; }

  resize() {
    const w = this.canvas.clientWidth || 390, h = this.canvas.clientHeight || 844, O = window.OLYMPUS, dpr = Math.min(this.T.dpr, O && O.dpr ? O.dpr(this.tierName === 'low') : (window.devicePixelRatio || 1));
    this.renderer.setPixelRatio(dpr); this.renderer.setSize(w, h, false); this.camera.aspect = w / h; this.camera.fov = h > w ? 62 : 50; this.camera.updateProjectionMatrix(); this.w = w; this.h = h;
  }

  /** screen position of a world point; z < 0 or off-screen means not visible */
  project(x, y, z) {
    const v = new THREE.Vector3(x, y, z).project(this.camera);
    return { x: (v.x * .5 + .5) * this.w, y: (-v.y * .5 + .5) * this.h, vis: v.z < 1 && Math.abs(v.x) < 1.15 && Math.abs(v.y) < 1.15 };
  }
  pick(px, py, radius = 40) {
    let best = null, bd = radius;
    for (const a of this.anchors) { const p = this.project(a.x, a.y * .6, a.z); if (!p.vis) continue; const d = Math.hypot(p.x - px, p.y - py) - (a.major ? 6 : 0); if (d < bd) { bd = d; best = a; } }
    return best;
  }
  select(a) {
    this.sel = a; this.ring.visible = this.beam.visible = !!a; if (!a) return;
    const gy = groundY(a.x, a.z), r = a.major ? 16 : 11; this.ring.position.set(a.x, gy + .6, a.z); this.ring.scale.setScalar(r);
    this.beam.position.set(a.x, gy, a.z); this.beam.scale.set(.5, a.y + 40 - gy, .5);
  }

  frame(dt, t) {
    this.u.uTime.value = t;
    if (this.fade) { const k = Math.min(1, (performance.now() - this.fade.t0) / 1600), e = k * k * (3 - 2 * k); this.time = lerp(this.fade.from, this.target, e); this.applyTime(); if (k >= 1) this.fade = null; }
    const cam = this.cam;
    if (this.fly) {
      const f = this.fly; f.t += dt / f.dur; const k = Math.min(1, f.t), e = k * k * (3 - 2 * k);
      for (const key of ['tx', 'ty', 'tz', 'yaw', 'pitch']) cam[key] = lerp(f.from[key], f.to[key], e);
      cam.dist = Math.exp(lerp(Math.log(f.from.dist), Math.log(f.to.dist), e)) * (1 + Math.sin(k * Math.PI) * .35);
      if (k >= 1) this.fly = null;
    }
    if (this.tour) {
      const T = this.tour; T.t += dt; const u = Math.min(1, T.t / T.def.secs), e = u * u * (3 - 2 * u) * .35 + u * .65;
      const p = T.cam.getPoint(e), l = T.look.getPoint(e); this.camera.position.copy(p); const fl = groundY(p.x, p.z) + 4; if (p.y < fl) this.camera.position.y = fl; this.camera.lookAt(l);
      if (u >= 1) { this.tour = null; this.syncFromCamera(l); this.onTourEnd && this.onTourEnd(); }
    } else this.placeCamera();
    this.camera.updateMatrixWorld();
    // LOD: far chunks swap to plain blocks, the lantern pass and the ships pause far away
    const cp = this.camera.position;
    for (const c of this.chunks) { const far = Math.hypot(c.cx - cp.x, c.cz - cp.z) > (this.tierName === 'low' ? 520 : 760); c.a.visible = !far; c.b.visible = far; }
    this.shipsTick(t);
    if (this.beacon) this.beacon.rotation.y = t * .5;
    if (this.sel) { const s = 1 + Math.sin(t * 3) * .04; this.ring.scale.setScalar((this.sel.major ? 16 : 11) * s); }
    this.renderer.render(this.scene, this.camera);
    this.calls = this.renderer.info.render.calls; this.trisDrawn = this.renderer.info.render.triangles;
  }

  dispose() { for (const o of this.dispose_) o.dispose && o.dispose(); this.renderer.dispose(); }
}
