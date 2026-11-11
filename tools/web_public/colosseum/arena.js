// COLOSSEUM's marble amphitheatre (three.js r160 from ../jarvis/, the OLYMPUS render core, the shared AGORA shapes): seven instanced tiers of spectators round a sand oval, a top arcade with the
// champions' busts, banners in the two fighters' colours, a warm low sun. Two marble champions (helmet and shield from olympus/shapes3d.js, crest colour = the strategy family) clash once a round.
// Light by design: every repeated part is ONE InstancedMesh, each champion is three baked meshes; about 24 draw calls and 75,000 triangles (budget: <= 45 draws, <= 150,000 triangles), bloom <= .25,
// a dpr cap of 1.5, no shadow maps, no frame while hidden or off screen. Eases of 200-450 ms, nothing shines. It holds no data: the page tells it who fights and who took the round.
// LITE / no WebGL / a failed load: the page draws the flat SVG arena instead, so the stage is never blank.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { build, bake, materials, dispose as freeShape } from '../olympus/shapes3d.js';

export const BUDGET = Object.freeze({ draws: 45, tris: 150000 });
const RX = 7, RZ = 5, GAP = 0.78, TIERS = 7, WALL = 0.9, WALK = 0.3, DEPTH = 0.62, RISE = 0.5, TOP = WALL + TIERS * RISE, DMAX = WALK + TIERS * DEPTH, COL_H = 1.9, N_COL = 34;
const A0 = Math.PI / 2 + GAP, A1 = Math.PI / 2 - GAP + Math.PI * 2;       // the stands leave a gate open towards the camera
const CLOTH = ['#e9e3d5', '#e6d7b2', '#c96a4a', '#7f8a52', '#9c6b3c', '#c8a24a', '#b98a6a', '#d9c7a0', '#8c5a3c'], SKIN = ['#d9b08c', '#c49a76', '#b98a6a'];
const BASE_X = 2.0, HIT_X = 0.78, SCALE = 1.5;        // the champions are larger than life: marble statues that came to fight
const ease = (t) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3), inOut = (t) => { t = Math.min(1, Math.max(0, t)); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const ring = (a, d) => [Math.cos(a) * (RX + d), Math.sin(a) * (RZ + d)];

/** sweep a profile [[d, y], ...] (d = metres outside the sand's edge) round the oval from a0 to a1: one flat-shaded geometry */
function sweep(profile, a0, a1, seg, tones) {
  const pos = [], idx = [], n = profile.length;
  for (let i = 0; i <= seg; i++) { const a = a0 + ((a1 - a0) * i) / seg; for (const [d, y] of profile) { const [x, z] = ring(a, d); pos.push(x, y, z); } }
  for (let i = 0; i < seg; i++) for (let j = 0; j < n - 1; j++) { const p = i * n + j, q = p + n; idx.push(p, p + 1, q, p + 1, q + 1, q); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  const flat = g.toNonIndexed(); g.dispose(); flat.computeVertexNormals();
  if (tones) {                                           // one tone for each strip of the profile (risers darker than treads): 6 vertices a quad
    const col = [], c = new THREE.Color();
    for (let i = 0; i < seg; i++) for (let j = 0; j < n - 1; j++) { c.set(tones[j % tones.length]); for (let k = 0; k < 6; k++) col.push(c.r, c.g, c.b); }
    flat.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  }
  return flat;
}
function instances(geo, mat, list) {
  const im = new THREE.InstancedMesh(geo, mat, list.length), o = new THREE.Object3D(), c = new THREE.Color();
  list.forEach((e, i) => { o.position.set(e.p[0], e.p[1], e.p[2]); o.rotation.set(e.r ? e.r[0] : 0, e.r ? e.r[1] : 0, e.r ? e.r[2] : 0); if (Array.isArray(e.s)) o.scale.set(e.s[0], e.s[1], e.s[2]); else o.scale.setScalar(e.s == null ? 1 : e.s); o.updateMatrix(); im.setMatrixAt(i, o.matrix); if (e.c) im.setColorAt(i, c.set(e.c)); });
  im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true; im.frustumCulled = false;
  return im;
}
/** a shape of the shared library without its display stand (every part whose middle is below `cut`) */
function shapeNoStand(id, M, cut) {
  const g = build(id, { lite: false, materials: M }); g.updateMatrixWorld(true);
  const box = new THREE.Box3(), mid = new THREE.Vector3();
  for (const m of g.children.slice()) { box.setFromObject(m); box.getCenter(mid); if (mid.y < cut) { g.remove(m); if (m.geometry) m.geometry.dispose(); } }
  return g;
}

export function createArena(canvas, opts) {
  const o = opts || {}, O = window.OLYMPUS || null, RM = o.reduced === true;
  const scene = new THREE.Scene(); scene.background = new THREE.Color('#c9906a');
  const camera = new THREE.PerspectiveCamera(48, 1.15, 0.1, 200);
  const rc = createRenderer({ canvas, scene, camera, maxDpr: 1.5, tint: '#c8a24a', theme: { sky: '#c9906a', fog: '#d8a878', emissive: '#c8a24a', bloom: '#e0b060', accent: '#c8a24a' }, bloom: { strength: 0.18, radius: 0.4, threshold: 1.05 } });
  const q0 = rc.quality();
  if (q0 === 'low' || q0 === 'off') { try { rc.dispose(); } catch (_) { /* gone */ } return null; }        // LITE is the flat SVG arena
  scene.fog = new THREE.Fog('#d09a6c', 40, 150);
  const own = [];                                         // geometries and materials to free
  const G = (g) => { own.push(g); return g; }, std = (c, r, m, extra) => { const x = new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: r, metalness: m || 0 }, extra)); own.push(x); return x; };
  const add = (m) => { scene.add(m); return m; };

  // ---- light: a low warm sun from the camera's left, a soft sky fill (about 3000 K)
  scene.add(new THREE.HemisphereLight(0xffe2b8, 0x5a4128, 0.7));
  const sun = new THREE.DirectionalLight(0xffd29a, 2.9); sun.position.set(-9, 8, 5); scene.add(sun);
  const fill = new THREE.DirectionalLight(0xe9c9a8, 0.35); fill.position.set(6, 4, -5); scene.add(fill);

  // ---- sky: dusk indigo down to amber, and the sun
  const skyGeo = G(new THREE.SphereGeometry(150, 24, 14)), sc = [], top = new THREE.Color('#3f3c5c'), mid = new THREE.Color('#b9694f'), low = new THREE.Color('#f2bd7a'), tmp = new THREE.Color();
  for (let i = 0; i < skyGeo.attributes.position.count; i++) { const y = skyGeo.attributes.position.getY(i) / 150, t = Math.max(0, y); tmp.copy(low).lerp(mid, Math.min(1, t * 7)); if (t > 0.14) tmp.lerp(top, Math.min(1, (t - 0.14) / 0.45)); sc.push(tmp.r, tmp.g, tmp.b); }
  skyGeo.setAttribute('color', new THREE.Float32BufferAttribute(sc, 3));
  const skyMat = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, fog: false, depthWrite: false }); own.push(skyMat);
  add(new THREE.Mesh(skyGeo, skyMat));
  const sunMat = new THREE.MeshBasicMaterial({ color: '#ffe2b0', fog: false }); own.push(sunMat);
  const sunDisc = add(new THREE.Mesh(G(new THREE.CircleGeometry(7, 40)), sunMat)); sunDisc.position.set(-38, 26, -120); sunDisc.lookAt(0, 4, 0);
  const hazeMat = new THREE.MeshBasicMaterial({ color: '#ffd9a0', transparent: true, opacity: 0.16, fog: false, depthWrite: false }); own.push(hazeMat);
  const haze = add(new THREE.Mesh(G(new THREE.CircleGeometry(17, 40)), hazeMat)); haze.position.set(-38, 26, -119); haze.lookAt(0, 4, 0);

  // ---- the sand, the podium wall, the tiers, the arcade
  const marble = std('#ffffff', 0.55, 0, { flatShading: true, vertexColors: true }), marble2 = std('#d9cfba', 0.6), wallMat = std('#a65a3c', 0.8, 0, { flatShading: true }), bronze = std('#9c6b3c', 0.5, 0.55), sand = std('#cfa258', 0.95), sandDark = std('#a9803f', 0.95);
  const floor = add(new THREE.Mesh(G(new THREE.CircleGeometry(1, 72)), sand)); floor.rotation.x = -Math.PI / 2; floor.scale.set(RX, RZ, 1);
  const lane = add(new THREE.Mesh(G(new THREE.RingGeometry(0.56, 0.6, 72)), sandDark)); lane.rotation.x = -Math.PI / 2; lane.scale.set(RX, RZ, 1); lane.position.y = 0.01;
  add(new THREE.Mesh(sweep([[0, 0], [0, WALL - 0.14], [0, WALL], [WALK, WALL]], 0, Math.PI * 2, 96, ['#a65a3c', '#e4dccb', '#e4dccb']), marble));           // the podium wall, all the way round: terracotta with a marble coping
  own.push(scene.children[scene.children.length - 1].geometry);
  const prof = [[WALK, WALL]]; for (let k = 0; k < TIERS; k++) { prof.push([WALK + DEPTH * k, WALL + RISE * (k + 1)]); prof.push([WALK + DEPTH * (k + 1), WALL + RISE * (k + 1)]); }
  const tiers = add(new THREE.Mesh(G(sweep(prof, A0, A1, 96, ['#b3a68d', '#e9e1cf'])), marble));
  add(new THREE.Mesh(G(sweep([[DMAX - 0.2, TOP + COL_H], [DMAX - 0.2, TOP + COL_H + 0.36], [DMAX + 0.36, TOP + COL_H + 0.36], [DMAX + 0.36, TOP + COL_H]], A0, A1, 96, ['#d9cfba', '#efe8d8', '#cfc4ae'])), marble));   // the entablature

  // ---- the crowd: bodies and heads, two draw calls for everyone
  const R = rng(o.seed || 1107), bodies = [], heads = [];
  for (let k = 0; k < TIERS; k++) {
    const d = WALK + DEPTH * k + 0.34, y = WALL + RISE * (k + 1), step = 0.4 / ((RX + RZ) / 2 + d);
    for (let a = A0 + 0.02; a < A1 - 0.02; a += step) {
      if (R() < 0.1) continue;
      const aa = a + (R() - 0.5) * step * 0.4, [x, z] = ring(aa, d + (R() - 0.5) * 0.12), h = 0.86 + R() * 0.3, ry = Math.atan2(-x, -z);
      bodies.push({ p: [x, y + 0.19 * h, z], r: [0, ry, 0], s: [1, h, 1], c: CLOTH[Math.floor(R() * CLOTH.length)] });
      heads.push({ p: [x, y + 0.38 * h + 0.09, z], s: 1, c: SKIN[Math.floor(R() * SKIN.length)] });
    }
  }
  const cloth = std('#ffffff', 0.85), skin = std('#ffffff', 0.7);
  add(instances(G(new THREE.CylinderGeometry(0.11, 0.16, 0.38, 5)), cloth, bodies));
  add(instances(G(new THREE.IcosahedronGeometry(0.088, 0)), skin, heads));

  // ---- the arcade: columns, arches, the champions' busts, the banner poles and the banners (the left half wears A's colour, the right half B's)
  const cols = [], arches = [], poles = [], flags = [], bustAt = [];
  const colA = (i) => A0 + ((A1 - A0) * i) / (N_COL - 1);
  for (let i = 0; i < N_COL; i++) {
    const [x, z] = ring(colA(i), DMAX + 0.08); cols.push({ p: [x, TOP + COL_H / 2, z] });
    if (i < N_COL - 1) {
      const [x2, z2] = ring(colA(i + 1), DMAX + 0.08), mx = (x + x2) / 2, mz = (z + z2) / 2, L = Math.hypot(x2 - x, z2 - z) / 2;
      arches.push({ p: [mx, TOP + COL_H - L, mz], r: [0, -Math.atan2(z2 - z, x2 - x), 0], s: L });
      if (Math.abs(i + 0.5 - (N_COL - 1) / 2) < 4.6) bustAt.push({ p: [mx, TOP, mz], r: [0, Math.atan2(-mx, -mz), 0], s: 1 });
    }
    if (i % 3 === 1) { poles.push({ p: [x, TOP + COL_H + 0.36 + 0.75, z] }); flags.push({ x, z, ry: Math.atan2(-x, -z) }); }
  }
  add(instances(G(new THREE.CylinderGeometry(0.11, 0.13, COL_H, 8)), marble2, cols));
  add(instances(G(new THREE.TorusGeometry(1, 0.09, 4, 10, Math.PI)), marble2, arches));
  add(instances(G(new THREE.CylinderGeometry(0.025, 0.025, 1.5, 5)), bronze, poles));
  const flagGeo = G(new THREE.PlaneGeometry(0.55, 0.95, 1, 3)); flagGeo.translate(0.3, -0.42, 0);
  const flagMat = std('#ffffff', 0.85, 0, { side: THREE.DoubleSide });
  const banners = add(instances(flagGeo, flagMat, flags.map((f) => ({ p: [f.x, TOP + COL_H + 0.36 + 1.45, f.z], r: [0, f.ry, 0], c: '#c8a24a' }))));
  const M = materials({ lite: false });                 // the shared warm material set of the shape library (colours only: everything here is baked)
  const bustSrc = build('bust', { lite: true, materials: M, size: 1.3 }); const bustBaked = bake(bustSrc); freeShape(bustSrc);
  const bustMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6 }); own.push(bustMat, bustBaked.geometry);
  const busts = add(instances(bustBaked.geometry, bustMat, bustAt));

  // ---- the two champions: body + helmet (one baked mesh), shield arm (one), spear (one)
  const champMat = new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.42, metalness: 0.06, clearcoat: 0.35, clearcoatRoughness: 0.3 }); own.push(champMat);
  const sph = new THREE.SphereGeometry(1, 18, 12), cylG = new THREE.CylinderGeometry(1, 1, 1, 14);
  function champion(colour) {
    const mar = M.marble, crestM = new THREE.MeshStandardMaterial({ color: colour }), Mx = Object.assign({}, M, { terra: crestM });
    const part = (g, geo, mat, p, s, r) => { const m = new THREE.Mesh(geo, mat); m.position.set(p[0], p[1], p[2]); m.scale.set(s[0], s[1], s[2]); if (r) m.rotation.set(r[0], r[1], r[2]); g.add(m); return m; };
    const body = new THREE.Group();
    for (const sx of [-1, 1]) {
      part(body, sph, mar, [sx * 0.14, 0.05, 0.05], [0.085, 0.05, 0.16]); part(body, sph, mar, [sx * 0.14, 0.33, 0], [0.085, 0.27, 0.09]); part(body, sph, mar, [sx * 0.13, 0.78, 0], [0.115, 0.27, 0.115]);
    }
    part(body, cylG, crestM, [0, 0.9, 0], [0.27, 0.4, 0.2]);                        // the tunic, in the family colour
    part(body, sph, mar, [0, 1.3, 0], [0.25, 0.33, 0.17]);                          // the chest
    part(body, cylG, M.bronze, [0, 1.07, 0], [0.245, 0.07, 0.18]);                  // the belt
    part(body, cylG, mar, [0, 1.62, 0], [0.07, 0.14, 0.07]);
    part(body, sph, mar, [0, 1.8, 0], [0.15, 0.17, 0.16]);                          // the head
    part(body, sph, mar, [-0.31, 1.36, 0.02], [0.075, 0.2, 0.08], [0.25, 0, -0.18]);   // the spear arm
    part(body, sph, mar, [-0.36, 1.12, 0.14], [0.065, 0.17, 0.065], [0.9, 0, 0]);
    const helm = shapeNoStand('helmet', Mx, 0.5); helm.scale.setScalar(0.37); helm.position.set(0, 1.8 - 1.1 * 0.37 + 0.02, 0); body.add(helm);
    const bodyMesh = bake(body); bodyMesh.material = champMat;
    const arm = new THREE.Group();                                                  // pivot = the left shoulder
    part(arm, sph, mar, [0.02, -0.14, 0.1], [0.075, 0.2, 0.08], [0.9, 0, 0]);
    const sh = shapeNoStand('shield', Mx, 0.5); sh.scale.setScalar(0.5); sh.position.set(0.06, -0.2 - 1.12 * 0.5, 0.3); arm.add(sh);
    part(arm, new THREE.TorusGeometry(0.27, 0.035, 6, 28), crestM, [0.06, -0.2, 0.36], [1, 1, 1], [0.1, 0, 0]);   // a ring in the family colour on the shield
    const armMesh = bake(arm); armMesh.material = champMat; armMesh.position.set(0.3, 1.44, 0);
    const sp = new THREE.Group();                                                   // pivot = the right hand
    part(sp, cylG, M.bronze, [0, 0.35, 0], [0.018, 2.2, 0.018]); part(sp, new THREE.ConeGeometry(0.05, 0.22, 8), M.gold, [0, 1.56, 0], [1, 1, 1]);
    const spMesh = bake(sp); spMesh.material = champMat; spMesh.position.set(-0.38, 1.0, 0.22);
    for (const g of [body, arm, sp]) g.traverse((m) => { if (m.isMesh && m.geometry !== sph && m.geometry !== cylG) m.geometry.dispose(); });
    crestM.dispose();
    const root = new THREE.Group(); root.add(bodyMesh, armMesh, spMesh);
    return { root, body: bodyMesh, arm: armMesh, spear: spMesh };
  }
  const F = [null, null], colours = ['#c8a24a', '#c96a4a'];
  function setChampion(i, colour) {
    if (F[i]) { scene.remove(F[i].root); for (const k of ['body', 'arm', 'spear']) F[i][k].geometry.dispose(); }
    const c = champion(colour); c.root.scale.setScalar(SCALE); c.root.rotation.order = 'YXZ'; c.root.rotation.y =i === 0 ? Math.PI / 2 : -Math.PI / 2; c.root.position.set(i === 0 ? -BASE_X : BASE_X, 0, 0); scene.add(c.root); F[i] = c; colours[i] = colour;
    const col = new THREE.Color(); flags.forEach((f, k) => { const mine = f.x < -0.6 ? colours[0] : f.x > 0.6 ? colours[1] : '#c8a24a'; banners.setColorAt(k, col.set(mine)); }); banners.instanceColor.needsUpdate = true;
  }
  setChampion(0, colours[0]); setChampion(1, colours[1]);

  // ---- small extras: soft ground shadows, the dust of a clash, the laurel of the winner
  const shMat = new THREE.MeshBasicMaterial({ color: '#3a2a18', transparent: true, opacity: 0.3, depthWrite: false }); own.push(shMat);
  const shGeo = G(new THREE.CircleGeometry(0.5, 20)); shGeo.rotateX(-Math.PI / 2);
  const shadows = add(new THREE.InstancedMesh(shGeo, shMat, 2)); shadows.frustumCulled = false;
  const dustMat = std('#d9b36a', 1, 0, { transparent: true, opacity: 0.8, depthWrite: false });
  const dust = add(new THREE.InstancedMesh(G(new THREE.IcosahedronGeometry(0.12, 0)), dustMat, 12)); dust.visible = false; dust.frustumCulled = false;
  const dustDir = []; { const r2 = rng(7); for (let i = 0; i < 12; i++) dustDir.push([(r2() - 0.5) * 1.6, 0.3 + r2() * 1.1, (r2() - 0.5) * 1.6, 0.6 + r2() * 0.8]); }
  const lsrc = shapeNoStand('laurel', M, 0.2); const laurel = bake(lsrc); laurel.material = bustMat; freeShape(lsrc); own.push(laurel.geometry);
  laurel.scale.setScalar(0.6); laurel.visible = false; scene.add(laurel);
  sph.dispose(); cylG.dispose();

  // ---- the choreography (seconds). Every move is one 200-450 ms ease.
  let anim = null, pose = 'idle', won = null, t = 0, frames = 0, dirty = true, disposed = false, kick = 0;
  const obj = new THREE.Object3D();
  function applyPose(now) {
    const st = [{ x: BASE_X, tilt: 0, y: 0, thrust: 0, raise: 0 }, { x: BASE_X, tilt: 0, y: 0, thrust: 0, raise: 0 }];
    let dustK = -1;
    if (anim && anim.kind === 'clash') {
      const e = now - anim.t0, w = anim.w;
      for (let i = 0; i < 2; i++) {
        const mine = (i === 0 && w === 'a') || (i === 1 && w === 'b'), s = st[i];
        if (w === 'none') { const k = e < 0.3 ? ease(e / 0.3) : 1 - ease((e - 0.45) / 0.35); s.tilt = -0.12 * Math.max(0, k); continue; }     // no contest: both lower their shields, nobody strikes
        if (e < 0.32) { const k = ease(e / 0.32); s.x = BASE_X - (BASE_X - HIT_X) * k; s.thrust = k; }
        else if (e < 0.62) { const k = ease((e - 0.32) / 0.3); const back = w === 'draw' ? 1.8 : mine ? 0.95 : 2.8; s.x = HIT_X + (back - HIT_X) * k; s.thrust = 1 - k; s.tilt = (w === 'draw' ? 0.12 : mine ? -0.05 : 0.3) * Math.sin(k * Math.PI * (mine ? 1 : 0.5)); }
        else { const k = inOut((e - 0.62) / 0.43), back = w === 'draw' ? 1.8 : mine ? 0.95 : 2.8; s.x = back + (BASE_X - back) * k; s.tilt = (w === 'draw' || mine ? 0 : 0.3) * (1 - k); }
      }
      if (w !== 'none' && e >= 0.32 && e < 0.82) dustK = (e - 0.32) / 0.5;
      kick = w !== 'none' && e >= 0.32 && e < 0.72 ? Math.sin(((e - 0.32) / 0.4) * Math.PI) : 0;
      if (e > (w === 'none' ? 0.85 : 1.08)) { const cb = anim.done; anim = null; kick = 0; if (cb) cb(); }
    } else if (pose === 'verdict') {
      const e = anim && anim.kind === 'verdict' ? Math.min(1, (now - anim.t0) / 0.45) : 1, k = RM ? 1 : ease(e);
      for (let i = 0; i < 2; i++) { const mine = won === 'draw' || (i === 0 && won === 'a') || (i === 1 && won === 'b'); if (mine) st[i].raise = k; else { st[i].y = -0.22 * k; st[i].tilt = -0.42 * k; } }
      if (anim && e >= 1) anim = null;
      laurel.visible = won === 'a' || won === 'b';
      if (laurel.visible) { const i = won === 'a' ? 0 : 1; laurel.position.set((i === 0 ? -1 : 1) * BASE_X, 3.75 + (1 - k) * 1.5, 0); laurel.rotation.y = RM ? 0.5 : now * 0.6; }
    }
    if (pose !== 'verdict') laurel.visible = false;
    for (let i = 0; i < 2; i++) {
      const f = F[i], s = st[i], sgn = i === 0 ? -1 : 1, bob = RM || anim ? 0 : Math.sin(now * 1.4 + i * 1.7) * 0.012;
      f.root.position.set(sgn * s.x, s.y + bob, 0); f.root.rotation.x = -s.tilt;          // order YXZ: a lean back (+) or a bow forward (-) about the champion's own shoulders
      f.arm.position.z = 0.02 + s.thrust * 0.26; f.arm.rotation.x = -s.thrust * 0.25 - s.raise * 0.2;
      f.spear.rotation.x = s.thrust * 0.5; f.spear.position.y = 1.0 + s.raise * 0.5; f.spear.rotation.z = -s.raise * 0.12;
      obj.position.set(sgn * s.x, 0.02, 0); obj.rotation.set(0, 0, 0); obj.scale.set(SCALE, 1, SCALE * 0.8); obj.updateMatrix(); shadows.setMatrixAt(i, obj.matrix);
    }
    shadows.instanceMatrix.needsUpdate = true;
    dust.visible = dustK >= 0 && dustK < 1;
    if (dust.visible) { const k = ease(dustK); dustMat.opacity = 0.75 * (1 - dustK); dustDir.forEach((d, i) => { obj.position.set(d[0] * k * 1.3, 0.7 + d[1] * k * 1.4, d[2] * k); obj.scale.setScalar(d[3] * (0.7 + k * 1.3)); obj.updateMatrix(); dust.setMatrixAt(i, obj.matrix); }); dust.instanceMatrix.needsUpdate = true; }
  }
  function frameCamera(now) {
    const asp = camera.aspect || 1.15, dist = Math.max(9.6, 11 / asp), sway = RM ? 0 : Math.sin(now * 0.11) * 0.13, push = 1 - 0.035 * kick;
    camera.position.set(Math.sin(sway) * dist * push, 3.6, Math.cos(sway) * dist * push); camera.lookAt(0, 2.0, 0);
  }
  function resize() { const w = canvas.clientWidth || 320, h = canvas.clientHeight || 280; camera.aspect = w / h; camera.updateProjectionMatrix(); rc.resize(w, h); dirty = true; }
  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null; if (ro) ro.observe(canvas);
  resize();
  let last = performance.now(), lastTick = 0;
  function draw() { applyPose(t); frameCamera(t); rc.render(); dirty = false; frames++; }
  function loop(now) {
    if (disposed) return;
    requestAnimationFrame(loop);
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    const gap = O && O.frameGap ? O.frameGap() : 0;
    if ((O ? O.hidden() : document.hidden) || (gap && !anim && now - lastTick < gap - 3)) return;
    const r = canvas.getBoundingClientRect(); if (r.bottom < -40 || r.top > innerHeight + 40) { if (anim && anim.kind === 'clash') { const cb = anim.done; anim = null; kick = 0; if (cb) cb(); } return; }
    lastTick = now; t += dt;
    if (RM && !anim && !dirty) return;
    draw();
  }
  draw();
  requestAnimationFrame(loop);

  return {
    ok: true, quality: () => rc.quality(), frames: () => frames,
    /** who fights: { crest } for the left (a) and the right (b) champion; the banners follow */
    setFighters(a, b) { if (a && a.crest && a.crest !== colours[0]) setChampion(0, a.crest); if (b && b.crest && b.crest !== colours[1]) setChampion(1, b.crest); dirty = true; },
    /** one round: w = 'a' | 'b' | 'draw' | 'none' (no contest: nobody strikes). done() is called when the champions are back in place (at once on reduced motion). */
    clash(w, done) { pose = 'idle'; won = null; if (RM) { anim = null; dirty = true; if (done) done(); return; } anim = { kind: 'clash', w, t0: t, done }; },
    /** the end: the winner raises the spear under a laurel, the other kneels ('draw': both raise) */
    verdict(w) { pose = 'verdict'; won = w; anim = RM ? null : { kind: 'verdict', t0: t }; dirty = true; },
    reset() { pose = 'idle'; won = null; anim = null; kick = 0; dirty = true; },
    busy: () => !!anim, pose: () => pose, colours: () => colours.slice(),
    /** what one frame costs: visible meshes (one draw call each) and their triangles */
    stats() {
      let draws = 0, tris = 0;
      scene.traverse((m) => { if (!m.isMesh || !m.visible) return; draws++; const g = m.geometry, n = g.index ? g.index.count : g.attributes.position.count; tris += (n / 3) * (m.isInstancedMesh ? m.count : 1); });
      const laurelTris = (laurel.geometry.index ? laurel.geometry.index.count : laurel.geometry.attributes.position.count) / 3;
      return { draws: draws + (laurel.visible ? 0 : 1) + (dust.visible ? 0 : 1), tris: Math.round(tris + (laurel.visible ? 0 : laurelTris) + (dust.visible ? 0 : 12 * 20)), crowd: bodies.length, busts: bustAt.length, banners: flags.length, tiers: TIERS };
    },
    dispose() {
      disposed = true; if (ro) ro.disconnect();
      try { for (const f of F) if (f) for (const k of ['body', 'arm', 'spear']) f[k].geometry.dispose(); for (const x of own) x.dispose(); tiers.geometry.dispose(); busts.dispose(); banners.dispose(); shadows.dispose(); dust.dispose(); M.dispose(); rc.dispose(); } catch (_) { /* gone */ }
    },
  };
}
window.COLOSSEUM_ARENA = { createArena, BUDGET };      // read by colosseum.js (its own module tag, so a failed 3D load never stops the page)
