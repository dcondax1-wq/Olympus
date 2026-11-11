// HELLAS scene: the Greek world above Athens. One renderer, two stages:
//   world   sea, land and hills in one batch, every polis as instanced markers (walls, houses, a gold acropolis), trade routes, ships
//   polis   ONE polis at a time, generated from its rows (hellas-plan.js planPolis); the one before is disposed first
// Budgets (measured every frame: calls / trisDrawn): world <= 30 draw calls; any view <= 45 calls / 160k triangles on phone-high,
// <= 28 / 80k in LITE. Warm AGORA light (3500 K sun), no neon, no bloom. READ ONLY scenery: no order, no trade.
import * as THREE from '../jarvis/three.module.min.js';
import { Batch, PAL, unit } from './athens-geo.js';
import { rng, hash32 } from './util.js';
import { walkStep, HOUSE_TINT, EYE } from './athens-world.js';
import { planPolis, polisCollider, polisNpcs, npcOnLoop, TIER } from './hellas-plan.js';

const lerp = (a, b, t) => a + (b - a) * t, clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const SKY_VS = `varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); gl_Position.z = gl_Position.w; }`;
const SKY_FS = `uniform vec3 uTop, uMid, uHor, uSun, uSunDir; varying vec3 vD;
void main(){ float h = clamp(vD.y, -.1, 1.); vec3 c = mix(uHor, uMid, smoothstep(0., .22, h)); c = mix(c, uTop, smoothstep(.15, .85, h));
  float s = max(dot(normalize(vD), uSunDir), 0.); c += uSun*(pow(s, 600.)*1.2 + pow(s, 14.)*.22); gl_FragColor = vec4(c, 1.);
  #include <colorspace_fragment>
}`;
const SEA_VS = `varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`;
const SEA_FS = `uniform float uTime, uFogD, uMove, uScale; uniform vec3 uDeep, uShallow, uSun, uSky, uFog, uSunDir; varying vec3 vW;
void main(){ float t = uTime*uMove; vec2 p = vW.xz*uScale;
  vec3 n = normalize(vec3(sin(p.x*.09+t*1.1)*.06+sin(p.y*.15-t*1.4)*.05+sin((p.x+p.y)*.31+t*2.)*.02, 1., cos(p.y*.11+t)*.05+sin(p.x*.2-t*1.7)*.03));
  vec3 v = normalize(cameraPosition - vW); float fres = pow(1. - clamp(dot(v, n), 0., 1.), 3.);
  vec3 h = normalize(uSunDir + v); float spec = pow(max(dot(n, h), 0.), 90.);
  vec3 c = mix(uDeep, uShallow, .5 + .5*sin(p.x*.013 + p.y*.017)); c = mix(c, uSky, clamp(fres*.8, 0., .85)) + uSun*spec*.7;
  float d = length(cameraPosition - vW); float f = 1. - exp(-d*d*uFogD*uFogD*3.);
  gl_FragColor = vec4(mix(c, uFog, clamp(f,0.,1.)), 1.);
  #include <colorspace_fragment>
}`;
const C = (h) => new THREE.Color(h);

export class Hellas {
  constructor(canvas, world, opts = {}) {
    this.canvas = canvas; this.world = world; this.tierName = TIER[opts.tier] ? opts.tier : 'high'; this.T = TIER[this.tierName]; this.reduced = !!opts.reduced; this.lite = this.tierName === 'low';
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: !this.lite, powerPreference: 'high-performance', alpha: false });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace; this.renderer.toneMapping = THREE.NoToneMapping;
    this.scene = new THREE.Scene(); this.camera = new THREE.PerspectiveCamera(52, 1, 2, 16000);
    this.u = { uTime: { value: 0 } }; this.keep = []; this.level = 'world'; this.polis = null; this.plan = null; this.fly = null; this.walk = null; this.sel = null; this.frameCount = 0; this.calls = 0; this.trisDrawn = 0; this.streams = 0;
    const B = world.bounds; this.home = { tx: B.cx, ty: 0, tz: B.cz + B.h * .04, yaw: 0, pitch: 1.02, dist: Math.max(B.w * 1.72, B.h * .98) };
    this.cam = { ...this.home }; this.wcam = { ...this.home };
    this.buildWorld();
    this.resize(); this.placeCamera();
  }
  own(o) { this.keep.push(o); return o; }

  buildWorld() {
    const W = this.world, T = this.T, scene = this.scene, own = (o) => this.own(o), sunDir = new THREE.Vector3(-.45, .62, .64).normalize();
    this.hemi = new THREE.HemisphereLight('#d6e2e6', '#8a7658', 1.05); this.sun = new THREE.DirectionalLight(new THREE.Color(1, .769, .537), 2.3); // 3500 K
    this.sun.position.copy(sunDir).multiplyScalar(100); scene.add(this.hemi, this.sun);
    scene.fog = new THREE.FogExp2('#e8d2a4', .00009);
    const skyU = { uTop: { value: C('#6f9bb8') }, uMid: { value: C('#cdbf9a') }, uHor: { value: C('#f3dba8') }, uSun: { value: C('#ffd9a0') }, uSunDir: { value: sunDir } };
    const sky = new THREE.Mesh(own(new THREE.SphereGeometry(9000, 20, 10)), own(new THREE.ShaderMaterial({ vertexShader: SKY_VS, fragmentShader: SKY_FS, uniforms: skyU, side: THREE.BackSide, depthWrite: false, fog: false })));
    sky.frustumCulled = false; sky.renderOrder = -10; scene.add(sky);
    this.seaU = { uTime: this.u.uTime, uDeep: { value: C('#2f5f78') }, uShallow: { value: C('#5c97a2') }, uSun: { value: C('#ffd9a0') }, uSky: { value: C('#d8c9a5') }, uFog: { value: C('#e8d2a4') }, uSunDir: { value: sunDir }, uFogD: { value: .00009 }, uMove: { value: this.reduced ? 0 : 1 }, uScale: { value: .12 } };
    const sea = new THREE.Mesh(own(new THREE.PlaneGeometry(30000, 30000).rotateX(-Math.PI / 2)), own(new THREE.ShaderMaterial({ vertexShader: SEA_VS, fragmentShader: SEA_FS, uniforms: this.seaU })));
    sea.position.y = -.3; sea.frustumCulled = false; scene.add(sea); this.sea = sea;
    this.matVC = own(new THREE.MeshLambertMaterial({ vertexColors: true })); this.matPlain = own(new THREE.MeshLambertMaterial({ color: '#ffffff' }));
    this.matRing = own(new THREE.MeshBasicMaterial({ color: '#e8bb55', transparent: true, opacity: .92, depthWrite: false, fog: false }));
    this.ring = new THREE.Mesh(own(new THREE.TorusGeometry(1, .05, 6, 44).rotateX(Math.PI / 2)), this.matRing); this.ring.visible = false; this.ring.frustumCulled = false; scene.add(this.ring);
    const G = this.wg = new THREE.Group(); scene.add(G);
    // land: sand under every disc, the land on top, hills: ONE draw call
    const b = new Batch(), seg = this.lite ? 8 : 14, tintOf = new Map(W.regions.map((R) => [R.key, C('#a8a070').lerp(C(R.tint), .2)]));
    for (const d of W.land) b.put(unit.cyl(seg, 1), d.x, -1.2, d.z, d.r + 7, 1.5, d.r + 7, PAL.sand, 0, 0, 0, .1);
    for (const d of W.land) b.put(unit.cyl(seg, .97), d.x, -1, d.z, d.r, 2.2, d.r, tintOf.get(d.region) || '#a8a070', 0, 0, 0, .1);
    W.hills.slice(0, T.hills).forEach((h, i) => { b.cone(h.x, 1.1, h.z, h.r, h.h, i % 3 ? '#9a9668' : '#b3a283', this.lite ? 5 : 7); if (!this.lite && h.h > 14) b.cone(h.x, 1.1 + h.h * .62, h.z, h.r * .4, h.h * .4, '#e6dcc4', 6); });
    G.add(new THREE.Mesh(own(b.geometry()), this.matVC)); this.landTris = b.tris;
    // markers: walls (the colour says adopted against rejected), little houses (the count says the size), a gold acropolis
    const P = W.poleis, n = P.length, d = new THREE.Object3D(), col = new THREE.Color(), bad = C('#c96a4a'), mid = C('#d9c7a0'), good = C('#7f8a52');
    this.base = new THREE.InstancedMesh(own(unit.cyl(this.lite ? 8 : 12, .92).clone()), this.matPlain, n);
    const nb = P.map((p) => (p.capital ? T.blocks + 6 : clamp(Math.round(1.5 + Math.sqrt(p.size) * 1.15), 2, T.blocks))), total = nb.reduce((s, x) => s + x, 0);
    this.blocks = new THREE.InstancedMesh(this.lite ? unit.houseFar() : unit.house(), this.matVC, total); this.blockAt = [];
    const golds = P.filter((p) => p.gold);
    const ab = new Batch(); ab.cyl(0, 0, 0, 1, .9, '#b3a283', this.lite ? 6 : 8, .7); ab.box(0, .9, 0, 1.15, .12, .8, PAL.marble); ab.box(0, 1.02, 0, .95, .5, .6, PAL.marbleD); ab.roof(0, 1.52, 0, .72, .32, 1.1, PAL.gold, Math.PI / 2);
    if (!this.lite) for (const sx of [-.42, -.14, .14, .42]) ab.cyl(sx, 1.02, .34, .05, .5, PAL.marble, 5);
    this.acro = new THREE.InstancedMesh(own(ab.geometry()), this.matVC, Math.max(1, golds.length)); this.acro.count = golds.length; this.acroTris = ab.tris;
    let bi = 0, gi = 0; this.markerInfo = [];
    P.forEach((p, i) => {
      const r = rng(hash32('mk:' + p.id)), share = clamp(p.share || 0, 0, 1);
      col.copy(share < .5 ? bad.clone().lerp(mid, share * 2) : mid.clone().lerp(good, (share - .5) * 2)); if (p.capital) col.set('#e8d9b8'); this.base.setColorAt(i, col);
      const info = { b0: bi, nb: nb[i], gi: p.gold ? gi : -1, items: [] };
      for (let k = 0; k < nb[i]; k++) { const th = k * 2.399963 + r() * .5, rr = p.mr * (p.gold ? .42 + .42 * Math.sqrt((k + .5) / nb[i]) : .82 * Math.sqrt((k + .5) / nb[i])), s = p.mr * (.2 + r() * .08) * (p.capital ? .7 : 1);
        info.items.push({ x: Math.cos(th) * rr, z: Math.sin(th) * rr, s, h: s * (.9 + r() * .7), ry: r() * 3.14 }); const t = .86 + r() * .14; col.setRGB(t, t * (.94 + r() * .06), t * (.84 + r() * .1)); this.blocks.setColorAt(bi + k, col); }
      bi += nb[i]; if (p.gold) { col.setRGB(1, 1, 1); this.acro.setColorAt(gi, col); gi++; }
      this.markerInfo.push(info);
    });
    this.markerScale = 0; this.setMarkerScale(1);
    for (const m of [this.base, this.blocks, this.acro]) { m.frustumCulled = false; if (m.instanceColor) m.instanceColor.needsUpdate = true; G.add(m); }
    // trade routes: one line set; ships sail them (none in LITE, still in reduced motion)
    const rp = []; for (const R of W.routes) { const a = P[R.a], q = P[R.b]; rp.push(a.x, 1.6, a.z, q.x, 1.6, q.z); }
    const rg = own(new THREE.BufferGeometry()); rg.setAttribute('position', new THREE.Float32BufferAttribute(rp, 3));
    this.routes = new THREE.LineSegments(rg, own(new THREE.LineBasicMaterial({ color: '#8a5a2c', transparent: true, opacity: .55 }))); this.routes.frustumCulled = false; G.add(this.routes);
    const ns = Math.min(T.ships, W.routes.length);
    if (ns) { const sb = new Batch(); sb.box(0, 0, 0, 1, .35, 2.6, PAL.timber); sb.box(0, .35, 0, .08, 2, .08, PAL.timber); sb.box(0, .9, .1, 1.5, 1.2, .06, '#f1e6cd');
      this.ships = new THREE.InstancedMesh(own(sb.geometry()), this.matVC, ns); this.ships.frustumCulled = false; G.add(this.ships);
      const r = rng(hash32('ships')); this.shipDef = Array.from({ length: ns }, (_, i) => ({ route: W.routes[Math.floor(i * W.routes.length / ns)], ph: r(), sp: .012 + r() * .012 })); this.shipsTick(0); }
  }
  /** far away the markers grow a little so a city is still a visible dot (LOD of the world level) */
  setMarkerScale(k) {
    k = Math.round(k * 4) / 4; if (k === this.markerScale) return; this.markerScale = k;
    const d = new THREE.Object3D(), P = this.world.poleis;
    P.forEach((p, i) => {
      const I = this.markerInfo[i]; d.rotation.set(0, 0, 0); d.position.set(p.x, 1.1, p.z); d.scale.set(p.mr * k, 1.3 * k, p.mr * k); d.updateMatrix(); this.base.setMatrixAt(i, d.matrix);
      I.items.forEach((it, j) => { d.position.set(p.x + it.x * k, 1.1 + 1.3 * k, p.z + it.z * k); d.rotation.set(0, it.ry, 0); d.scale.set(it.s * k, it.h * k * 1.2, it.s * k); d.updateMatrix(); this.blocks.setMatrixAt(I.b0 + j, d.matrix); });
      if (I.gi >= 0) { const s = p.mr * (p.capital ? .5 : .42) * k; d.position.set(p.x, 1.1 + 1.3 * k, p.z); d.rotation.set(0, 0, 0); d.scale.set(s, s * 1.25, s); d.updateMatrix(); this.acro.setMatrixAt(I.gi, d.matrix); }
    });
    for (const m of [this.base, this.blocks, this.acro]) m.instanceMatrix.needsUpdate = true;
  }
  shipsTick(t) {
    if (!this.ships) return; const d = this._d || (this._d = new THREE.Object3D()), P = this.world.poleis, k = this.markerScale || 1;
    this.shipDef.forEach((s, i) => { const a = P[s.route.a], b = P[s.route.b]; let u = (t * s.sp + s.ph) % 2; const back = u > 1; if (back) u = 2 - u; const e = .12 + .76 * u;
      d.position.set(lerp(a.x, b.x, e), 1.5, lerp(a.z, b.z, e)); d.rotation.set(0, Math.atan2(b.x - a.x, b.z - a.z) + (back ? Math.PI : 0), 0); d.scale.setScalar(2.2 * k); d.updateMatrix(); this.ships.setMatrixAt(i, d.matrix); });
    this.ships.instanceMatrix.needsUpdate = true;
  }

  // ------------------------------------------------------------------ one polis (streamed: the one before is disposed)
  disposePolis() {
    if (!this.pg) return; this.scene.remove(this.pg); for (const g of this.pKeep) g.dispose(); this.pg = null; this.pKeep = []; this.polis = null; this.plan = null; this.col = null; this.npcs = null; this.npcMesh = null; this.houseMesh = null;
  }
  buildPolis(p) {
    this.disposePolis(); const plan = planPolis(p), T = this.T, G = new THREE.Group(), keep = this.pKeep = [], own = (g) => { keep.push(g); return g; }, r = rng(hash32('look:' + p.id));
    this.polis = p; this.plan = plan; this.pg = G; this.streams++;
    const b = new Batch(), R = plan.R, A = plan.agoraR, seg = this.lite ? 20 : 36;
    b.put(unit.cyl(seg, 1), 0, -1.6, 0, R + 96, 1.5, R + 96, PAL.sand, 0, 0, 0, .1);
    b.put(unit.cyl(seg, .985), 0, -1.5, 0, R + 80, 1.5, R + 80, '#a8a070', 0, 0, 0, .1);
    b.put(unit.cyl(seg, 1), 0, -1.45, 0, R - 1, 1.5, R - 1, '#b9ab8a', 0, 0, 0, .05);                 // the city floor
    b.put(unit.cyl(this.lite ? 14 : 24, 1), 0, -1.4, 0, A, 1.5, A, PAL.paving, 0, 0, 0, .05);        // the agora
    for (const D of plan.districts) b.box(D.x, .02, D.z, D.w + 8, .06, D.h + 8, C('#c3b494').lerp(C(D.tint), .16));
    for (const V of plan.villages) b.box(V.x, .06, V.z, V.w + 2, .06, V.d + 2, '#cbbd9c');
    // the wall with towers and a south gate
    const N = clamp(Math.round(R / 7), 18, this.lite ? 28 : 48), step = Math.PI * 2 / N, len = 2 * R * Math.tan(step / 2) + .4;
    for (let i = 0; i < N; i++) { const a = i * step + step / 2, x = Math.cos(a) * R, z = Math.sin(a) * R, gate = Math.abs(a - Math.PI / 2) < step * .6; if (!gate) b.box(x, 0, z, 1.6, 6.2, len, PAL.lime, -a);
      if (i % 3 === 0 || gate) b.box(Math.cos(a - step / 2) * R, 0, Math.sin(a - step / 2) * R, 3.4, 8.6, 3.4, PAL.stone, -a + step / 2); }
    // the acropolis: a rock, a temple (gold roof when the polis has something adopted)
    const hr = plan.hillR, hh = 7 + Math.min(8, A * .12); b.put(unit.cyl(this.lite ? 8 : 12, .72), 0, 0, 0, hr, hh, hr, '#b3a283', 0, 0, 0, .3);
    const tw = hr * .95, td = hr * .6; b.box(0, hh, 0, tw + 1.6, .7, td + 1.6, PAL.marbleD); b.box(0, hh + .7, 0, tw * .78, tw * .34, td * .7, PAL.marble);
    const nc = this.lite ? 4 : 6; for (let i = 0; i < nc; i++) for (const s of [-1, 1]) b.col(-tw / 2 + .5 + i * (tw - 1) / (nc - 1), hh + .7, s * td / 2, .42, tw * .34, PAL.marble, this.lite);
    b.box(0, hh + .7 + tw * .34 + .2, 0, tw + .8, .6, td + .8, PAL.marbleD); b.roof(0, hh + 1.5 + tw * .34, 0, td + 1, tw * .16, tw + .8, plan.gold ? PAL.gold : PAL.terra, Math.PI / 2);
    for (const D of plan.districts) { const l = Math.hypot(D.x, D.z) || 1, x = D.x / l * (A - 3), z = D.z / l * (A - 3); b.cyl(x, 0, z, .55, 4.6, D.tint, 6, .8); b.box(x, 4.6, z, 1.5, .4, 1.5, PAL.marble); }
    G.add(new THREE.Mesh(own(b.geometry()), this.matVC)); this.polisTris = b.tris;
    // houses: one row each, ONE draw call
    const H = plan.houses, d = new THREE.Object3D(), col = new THREE.Color(), tones = [[1, 1, 1], [.96, .9, .8], [.98, .86, .68], [.96, .8, .72], [1, .94, .82]];
    if (H.length) { const m = this.houseMesh = new THREE.InstancedMesh(unit.house(), this.matVC, H.length);
      H.forEach((h, i) => { d.position.set(h.x, .1, h.z); d.rotation.set(0, h.rot ? Math.PI / 2 : 0, 0); d.scale.set(h.w, h.h, h.d); d.updateMatrix(); m.setMatrixAt(i, d.matrix);
        const t = tones[Math.floor(r() * tones.length)], k = HOUSE_TINT[h.tone] || HOUSE_TINT.plain; col.setRGB(t[0] * .35 + k[0] * .65, t[1] * .35 + k[1] * .65, t[2] * .35 + k[2] * .65); m.setColorAt(i, col); });
      m.instanceMatrix.needsUpdate = true; m.instanceColor.needsUpdate = true; m.frustumCulled = false; G.add(m); own(m); }
    // cypress and olive trees: in the agora ring and outside the wall
    const nt = Math.min(T.trees, 30 + Math.round(R * .9)), tb = new Batch(); tb.cone(0, 0, 0, .5, 1, PAL.cypress, this.lite ? 5 : 6);
    const tg = own(tb.geometry()), tm = new THREE.InstancedMesh(tg, this.matVC, nt);
    for (let i = 0; i < nt; i++) { const inner = i % 5 === 0, a = r() * 6.283, rr = inner ? lerp(hr + 3, A - 6, r()) : R + 8 + r() * 62, s = 1.6 + r() * 1.6; if (!inner && Math.abs(a - Math.PI / 2) < .09) { d.scale.setScalar(0); } else d.scale.set(s, s * (inner ? 3.6 : 2 + r() * 2.4), s);
      d.position.set(Math.cos(a) * rr, 0, Math.sin(a) * rr); d.rotation.set(0, 0, 0); d.updateMatrix(); tm.setMatrixAt(i, d.matrix); if (i % 3) col.setRGB(1.35, 1.4, 1.25); else col.setRGB(2.1, 1.85, 1.4); tm.setColorAt(i, col); }
    tm.instanceMatrix.needsUpdate = true; tm.instanceColor.needsUpdate = true; tm.frustumCulled = false; G.add(tm); own(tm); this.treeMesh = tm;
    // villagers on the streets around the village blocks (phone-high only)
    this.col = polisCollider(plan); this.npcs = T.npcs && !this.reduced ? polisNpcs(plan, Math.min(T.npcs, plan.villages.length * 3)) : [];
    if (this.npcs.length) { const nb2 = new Batch(); nb2.cyl(0, 0, 0, .28, 1.25, '#e9dcc0', 6, .7); nb2.put(unit.sphere(6, 4), 0, 1.25, 0, .2, .22, .2, '#c99a72');
      this.npcMesh = new THREE.InstancedMesh(own(nb2.geometry()), this.matVC, this.npcs.length); this.npcMesh.frustumCulled = false; const tints = ['#ffffff', '#e8c9a0', '#c9d6c0', '#e0b7a0', '#c8d2e0'];
      this.npcs.forEach((q, i) => { col.set(tints[i % tints.length]); this.npcMesh.setColorAt(i, col); }); this.npcMesh.instanceColor.needsUpdate = true; G.add(this.npcMesh); own(this.npcMesh); this.npcTick(0); }
    G.visible = false; this.scene.add(G); return plan;
  }
  npcTick(t) { if (!this.npcMesh) return; const d = this._d || (this._d = new THREE.Object3D()); this.npcs.forEach((n, i) => { const q = npcOnLoop(n, t); d.position.set(q.x, .1, q.z); d.rotation.set(0, -q.yaw, 0); d.scale.setScalar(1.35); d.updateMatrix(); this.npcMesh.setMatrixAt(i, d.matrix); }); this.npcMesh.instanceMatrix.needsUpdate = true; }

  setStage(level) {
    this.level = level; const world = level === 'world'; this.wg.visible = world; if (this.pg) this.pg.visible = !world;
    const fd = world ? .00009 : .0011; this.scene.fog.density = fd; this.seaU.uFogD.value = fd; this.seaU.uScale.value = world ? .12 : 1; this.select(null);
    this.camera.near = world ? 2 : 1; this.camera.far = world ? 16000 : 6000; this.camera.updateProjectionMatrix();
  }
  /** fly to the marker, swap the stage (onSwap lets the page dip a veil), come down over the new city. then() fires when the camera rests. */
  enterPolis(p, o = {}) {
    if (this.walk) this.stopWalk();
    const swap = () => { this.wcam = { ...(this.level === 'world' ? this.cam : this.wcam), tx: p.x, ty: 0, tz: p.z, dist: 420, pitch: .95 }; const plan = this.buildPolis(p); this.setStage('polis');
      const R = plan.R, to = { tx: 0, ty: 4, tz: 0, yaw: .5, pitch: .62, dist: clamp(R * 2.5, 150, 760) }; this.cam = { ...to, dist: to.dist * 2.4, pitch: 1.1, yaw: to.yaw - .7 }; o.onSwap && o.onSwap(plan);
      this.flyCam(to, { dur: 1.5, then: o.then }); };
    if (this.level === 'world' && !this.reduced && !o.instant) this.flyTo(p.x, p.z, { dist: 150, pitch: .8, dur: 1.15, then: swap }); else swap();
  }
  leavePolis(o = {}) { if (this.level !== 'polis') return; if (this.walk) this.stopWalk(); const back = { ...this.wcam }; this.setStage('world'); this.disposePolis(); this.cam = { ...back, dist: 150, pitch: .8 }; this.flyCam({ ...back, dist: o.dist || 520 }, { dur: 1.2, then: o.then }); }

  // ------------------------------------------------------------------ camera
  limits() { const B = this.world.bounds; return this.level === 'world' ? { x0: B.x0, x1: B.x1, z0: B.z0, z1: B.z1, d0: 90, d1: this.home.dist * 1.25 } : { x0: -this.plan.R, x1: this.plan.R, z0: -this.plan.R, z1: this.plan.R, d0: 16, d1: this.plan.R * 6 + 300 }; }
  placeCamera() { const c = this.cam, cp = Math.cos(c.pitch); this.camera.position.set(c.tx + Math.sin(c.yaw) * cp * c.dist, c.ty + Math.sin(c.pitch) * c.dist, c.tz + Math.cos(c.yaw) * cp * c.dist); if (this.camera.position.y < 3) this.camera.position.y = 3; this.camera.lookAt(c.tx, c.ty, c.tz); }
  orbit(dx, dy) { const c = this.cam; this.fly = null; c.yaw -= dx * .0062; c.pitch = clamp(c.pitch + dy * .0052, .12, 1.45); }
  zoom(f) { const c = this.cam, L = this.limits(); this.fly = null; c.dist = clamp(c.dist * f, L.d0, L.d1); }
  pan(dx, dy) { const c = this.cam, L = this.limits(), s = c.dist * .0019, rx = Math.cos(c.yaw), rz = -Math.sin(c.yaw), fx = -Math.sin(c.yaw), fz = -Math.cos(c.yaw); this.fly = null;
    c.tx = clamp(c.tx - (rx * dx + fx * -dy) * s, L.x0, L.x1); c.tz = clamp(c.tz - (rz * dx + fz * -dy) * s, L.z0, L.z1); }
  flyCam(to, o = {}) { const c = this.cam; let yaw = to.yaw ?? c.yaw; yaw = c.yaw + (((yaw - c.yaw + Math.PI * 3) % (Math.PI * 2)) - Math.PI); this.fly = { from: { ...c }, to: { ...c, ...to, yaw }, t: 0, dur: this.reduced ? .01 : o.dur ?? 1.4, then: o.then, arc: o.arc ?? .18 }; }
  flyTo(x, z, o = {}) { this.flyCam({ tx: x, tz: z, ty: o.y ?? (this.level === 'world' ? 0 : 3), dist: o.dist ?? 200, pitch: o.pitch ?? this.cam.pitch, yaw: o.yaw }, o); }
  goHome(o = {}) { this.flyCam(this.home, { dur: 1.5, ...o }); }
  resize() {
    const w = this.canvas.clientWidth || 390, h = this.canvas.clientHeight || 844, O = window.OLYMPUS, dpr = Math.min(this.T.dpr, O && O.dpr ? O.dpr(this.lite) : (window.devicePixelRatio || 1));
    this.renderer.setPixelRatio(dpr); this.renderer.setSize(w, h, false); this.camera.aspect = w / h; this.camera.fov = h > w ? 62 : 50; this.camera.updateProjectionMatrix(); this.w = w; this.h = h;
    const B = this.world.bounds, tv = Math.tan(this.camera.fov * Math.PI / 360), th = tv * this.camera.aspect; this.home.dist = Math.max(B.w / 2 / th, B.h / 2 / tv * .8) * 1.02; if (this.level === 'world' && !this.frameCount) this.cam.dist = this.home.dist;
  }
  project(x, y, z) { const v = (this._v || (this._v = new THREE.Vector3())).set(x, y, z).project(this.camera); return { x: (v.x * .5 + .5) * this.w, y: (-v.y * .5 + .5) * this.h, vis: v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1 }; }
  pickPolis(px, py, radius = 34) { let best = null, bd = radius; for (const p of this.world.poleis) { const q = this.project(p.x, 3, p.z); if (!q.vis) continue; const d = Math.hypot(q.x - px, q.y - py) - (p.capital ? 8 : 0); if (d < bd) { bd = d; best = p; } } return best; }
  pickHouse(px, py, radius = 30) { if (!this.plan) return null; let best = null, bd = radius; for (const h of this.plan.houses) { const q = this.project(h.x, h.h * .6, h.z); if (!q.vis) continue; const d = Math.hypot(q.x - px, q.y - py); if (d < bd) { bd = d; best = h; } } return best; }
  select(o) { this.sel = o; this.ring.visible = !!o; if (!o) return; const r = o.selR || 10; this.ring.position.set(o.x, this.level === 'world' ? 3 : .5, o.z); this.ring.scale.setScalar(r); }
  /** the labels the page draws: region names from far away, the nearest city names closer; districts then villages inside a polis */
  labels(max = 7) {
    const out = [], c = this.cam, near = (list, pos, n) => list.map((o) => [Math.hypot(pos(o)[0] - c.tx, pos(o)[1] - c.tz), o]).sort((a, b) => a[0] - b[0]).slice(0, n).map((e) => e[1]);
    const put = (x, y, z, text, kind, ref) => { const q = this.project(x, y, z); if (q.vis) out.push({ x: q.x, y: q.y, text, kind, ref }); };
    if (this.walk) return out;
    if (this.level === 'world') {
      if (c.dist > 1100) for (const R of this.world.regions) put(R.cx, 20, R.cz, R.name, 'region', R);
      else for (const p of near(this.world.poleis, (p) => [p.x, p.z], max)) put(p.x, 8 + p.mr * .5, p.z, p.name, p.capital ? 'capital' : 'polis', p);
    } else if (this.plan) {
      if (c.dist > this.plan.R * 1.1 || this.plan.villages.length <= 1) for (const D of this.plan.districts) put(D.x, 12, D.z, D.name, 'district', D);
      else for (const V of near(this.plan.villages, (v) => [v.x, v.z], max)) put(V.x, 11, V.z, V.name, 'village', V);
    }
    return out;
  }

  // ------------------------------------------------------------------ walking (the Athens walker: athens-world.js walkStep)
  startWalk(x, z, yaw = 0) { if (!this.col) return false; const s = this.plan.start; if (x == null || this.col.hits(x, z)) { x = s.x; z = s.z; yaw = s.yaw; } this.fly = null; this.camera.near = .35; this.camera.updateProjectionMatrix();
    this.walk = { x, z, yaw, pitch: -.03, input: { fwd: 0, side: 0, run: false }, bob: 0, y: EYE, dist: 0 }; this.select(null); return true; }
  stopWalk() { if (!this.walk) return; const w = this.walk; this.walk = null; this.camera.near = 1; this.camera.updateProjectionMatrix(); const c = this.cam; c.tx = w.x; c.tz = w.z; c.ty = 3; c.dist = 110; c.pitch = .6; c.yaw = w.yaw + Math.PI; }
  walkLook(dx, dy) { const w = this.walk; if (!w) return; w.yaw += dx * .0055; w.pitch = clamp(w.pitch - dy * .0045, -1, .9); }
  walkTick(dt) { const w = this.walk, r = walkStep(w, w.input, dt, this.col); w.x = r.x; w.z = r.z; w.dist += r.moved; w.bob += r.moved * 2.1; const bob = this.reduced ? 0 : Math.sin(w.bob) * .035, cp = Math.cos(w.pitch);
    this.camera.position.set(w.x, w.y + bob, w.z); this.camera.lookAt(w.x + Math.sin(w.yaw) * cp, w.y + bob + Math.sin(w.pitch), w.z - Math.cos(w.yaw) * cp); }
  get walking() { return !!this.walk; }

  frame(dt, t) {
    this.u.uTime.value = t; this.frameCount++;
    if (this.fly) { const f = this.fly, c = this.cam; f.t += dt / f.dur; const k = Math.min(1, f.t), e = k * k * (3 - 2 * k);
      for (const key of ['tx', 'ty', 'tz', 'yaw', 'pitch']) c[key] = lerp(f.from[key], f.to[key], e);
      c.dist = Math.exp(lerp(Math.log(f.from.dist), Math.log(f.to.dist), e)) * (1 + Math.sin(k * Math.PI) * f.arc);
      if (k >= 1) { this.fly = null; f.then && f.then(); } }
    if (this.walk) this.walkTick(dt); else this.placeCamera();
    this.camera.updateMatrixWorld();
    if (this.level === 'world') { this.setMarkerScale(clamp(this.cam.dist / 1100, 1, 1.75)); if (!this.reduced) this.shipsTick(t); if (this.ships) this.ships.visible = this.cam.dist < 2600; }
    else { const far = !this.walk && this.cam.dist > this.plan.R * 3.2; if (this.npcMesh) { this.npcMesh.visible = !far; if (!far) this.npcTick(t); } if (this.treeMesh) this.treeMesh.visible = !(this.lite && far); }
    if (this.sel && !this.reduced) this.ring.scale.setScalar((this.sel.selR || 10) * (1 + Math.sin(t * 3) * .04));
    this.renderer.render(this.scene, this.camera);
    this.calls = this.renderer.info.render.calls; this.trisDrawn = this.renderer.info.render.triangles;
  }
  dispose() { this.disposePolis(); for (const o of this.keep) o.dispose && o.dispose(); for (const m of [this.base, this.blocks, this.acro, this.ships]) m && m.dispose(); this.renderer.dispose(); }
}
