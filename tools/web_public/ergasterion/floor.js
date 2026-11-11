// ERGASTERION floor (ES module): the marble-and-bronze agent factory you walk in first person. Four halls (Money, Trading, Research, Library) around a cross of inner walls with a
// door in each; one platform per worker with a friendly cartoon PERSON (big round head, dot eyes, coloured tunic, mitten hands) DOING ITS JOB (turning the search wheel, writing at a desk, reading the tripod, hammering at the anvil, weighing on the
// scales), a status lamp, a speech bubble with its latest finding, and a conveyor carrying its last outputs as labelled crates you can tap. The Learning board and "what changed our
// mind" hang in the Library, the research pipeline wall in the Research hall. Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm light, bloom <= .2.
// Outside the front door lies THE BUILDERS' CAMP: a desert caravan camp with one tent per build agent (a worker at a marble table, a banner with its name and job, a scroll that cycles
// its latest commit messages, a stack of crates = commits today, brazier smoke only while it is working).
// LIGHT BY DESIGN: every repeated part lives in one of ten instanced batches (unit box / cylinder / sphere, coloured per instance), all 15 bubbles are ONE mesh on one canvas atlas, the camp's banners and scrolls another,
// all crate tags and hall signs are ONE mesh on a second atlas, plus three wall boards: about 15 draw calls and under 40k triangles for the whole factory.
// createFloor(canvas, { reduced, stations, onPick }) -> { ok, set(workers, extra), move({fwd,side}), look(dx,dy), follow(id|null), tour(on), pulse(ids), reset(), teleport(x,z),
//   face(id), pos(), project(id), pick(x,y), stats(), dispose() }
// If WebGL, the render core or the tier (LITE / off) says no, ok is false and the page keeps its flat plan. Reduced motion: everything stands still and the camera jumps instead of gliding.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { walk, followCam, tourCam, ease, hallOf, resolveCollision, EYE, START, HALLS, DOORS, CAMP, CAMP_SPOTS, personId, builderIds, lookOf } from './ergasterioncore.js';

const BUILD = { working: '#8fa05a', quiet: '#4b7a99', done: '#c8a24a', job: '#b8ad98' }, BWORD = { working: 'Working', quiet: 'Quiet', done: 'Done', job: 'Job only' }, NC = CAMP_SPOTS.length, CSTACK = 6, PUFF = 5;
const HS = 9;                                                                              // head-batch parts of one person: head, hair, 2 eyes, 2 hands, shoulders, 2 feet
const LAMP = { working: '#8fa05a', idle: '#4b7a99', stale: '#e0b060', failed: '#c96a4a', sample: '#b8ad98' };
const WORD = { working: 'Working', idle: 'Idle', stale: 'Stale', failed: 'Failed', sample: 'Sample data' };
const PACE = { working: 1, idle: 0.3, stale: 0, failed: 0, sample: 0.5 };          // how briskly a figure works (and its belt runs)
const MARBLE = '#d9d2c3', BRONZE = '#9c6b3c', GOLD = '#c8a24a', Y0 = 0.24, MAXC = 5;
const RUG = { money: '#8a7a55', trading: '#84684e', research: '#74795c', library: '#64727c' };

export function createFloor(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(72, 1.2, 0.1, 80);
    scene.background = new THREE.Color('#2a2118');
    scene.fog = new THREE.Fog('#5a4030', 26, 72);
    rc = createRenderer({ canvas, scene, camera, maxDpr: 2, tint: '#c8a24a', env: 'night',
      theme: { sky: '#5a3c22', fog: '#2a2118', emissive: '#c8a24a', bloom: '#e0b060', accent: '#c8a24a' }, bloom: { strength: 0.15, radius: 0.5, threshold: 1.0 } });
    const q = rc.quality();
    if (q === 'low' || q === 'off') { rc.dispose(); return { ok: false, mode: 'lite', reason: 'quality ' + q }; }
    return build(rc, scene, camera, canvas, o);
  } catch (e) {
    try { if (rc) rc.dispose(); } catch (_) { /* nothing */ }
    return { ok: false, mode: 'lite', reason: String(e && e.message ? e.message : e) };
  }
}

function atlas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.generateMipmaps = false; t.minFilter = THREE.LinearFilter; return { c, t, g: c.getContext('2d') }; }
function wrap(g, text, x, y, maxW, lh, maxLines) {
  const words = String(text).split(' '); let line = '', n = 0;
  for (let i = 0; i < words.length; i++) {
    const t = line ? line + ' ' + words[i] : words[i];
    if (g.measureText(t).width > maxW && line) {
      if (n === maxLines - 1) { let l = line + ' ' + words[i]; while (l.length > 3 && g.measureText(l + '…').width > maxW) l = l.slice(0, -1); g.fillText(l.trimEnd() + '…', x, y + n * lh); return n + 1; }
      g.fillText(line, x, y + n * lh); n++; line = words[i];
    } else line = t;
  }
  if (line && n < maxLines) { g.fillText(line, x, y + n * lh); n++; }
  return n;
}
function panel(g, x, y, w, h, r) { g.beginPath(); if (g.roundRect) g.roundRect(x, y, w, h, r); else g.rect(x, y, w, h); g.fill(); g.stroke(); }

function build(rc, scene, camera, canvas, o) {
  const reduced = !!o.reduced, S = o.stations || [], N = S.length, eye = o.eye || EYE;
  const mot = reduced ? 0 : 1;
  scene.add(new THREE.HemisphereLight(0xf0dcb8, 0x4a3a28, 1.05));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.1); sun.position.set(6, 14, 9); scene.add(sun);
  const skyG = new THREE.SphereGeometry(70, 20, 10), skyC = new Float32Array(skyG.attributes.position.count * 3), top = new THREE.Color('#23233f'), mid = new THREE.Color('#6b4a3a'), low = new THREE.Color('#c08a4e');
  for (let i = 0; i < skyG.attributes.position.count; i++) { const hgt = Math.max(0, skyG.attributes.position.getY(i) / 70), c = hgt < 0.25 ? low.clone().lerp(mid, hgt / 0.25) : mid.clone().lerp(top, Math.min(1, (hgt - 0.25) / 0.5)); skyC[i * 3] = c.r; skyC[i * 3 + 1] = c.g; skyC[i * 3 + 2] = c.b; }
  skyG.setAttribute('color', new THREE.BufferAttribute(skyC, 3));
  const sky = new THREE.Mesh(skyG, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, fog: false, depthWrite: false })); sky.frustumCulled = false; sky.renderOrder = -1; scene.add(sky);
  const std = (r, m) => new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: r, metalness: m });
  const stone = std(0.5, 0.02), metal = std(0.38, 0.55);
  const colour = new THREE.Color(), M4 = new THREE.Matrix4(), Q = new THREE.Quaternion(), EU = new THREE.Euler(), P = new THREE.Vector3(), SC = new THREE.Vector3();
  const put = (im, i, x, y, z, sx, sy, sz, rx, ry, rz) => { EU.set(rx || 0, ry || 0, rz || 0, 'XYZ'); Q.setFromEuler(EU); M4.compose(P.set(x, y, z), Q, SC.set(sx, sy, sz)); im.setMatrixAt(i, M4); };
  // a batch = one InstancedMesh (one draw call): list the parts, then build it once; dynamic batches are rewritten every frame
  const batches = [];
  function batch(geo, mat, dynamic) {
    const L = [], b = { im: null, n: 0,
      add(x, y, z, sx, sy, sz, col, rx, ry, rz) { L.push([x, y, z, sx, sy, sz, rx || 0, ry || 0, rz || 0, col]); return L.length - 1; },
      make() {
        const im = new THREE.InstancedMesh(geo, mat, Math.max(1, L.length)); b.im = im; b.n = L.length;
        L.forEach((a, i) => { put(im, i, a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8]); im.setColorAt(i, colour.set(a[9] || '#ffffff')); });
        if (dynamic) im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        im.frustumCulled = false; scene.add(im); return im;
      } };
    batches.push(b); return b;
  }
  const boxG = new THREE.BoxGeometry(1, 1, 1), cylG = new THREE.CylinderGeometry(1, 1, 1, 20), robeG = new THREE.CylinderGeometry(0.72, 1, 1, 12), ballG = new THREE.SphereGeometry(1, 16, 12);
  const sBox = batch(boxG, stone), bBox = batch(boxG, metal), sCyl = batch(cylG, stone), bCyl = batch(cylG, metal);                     // static: the building and the furniture
  const pplG = new THREE.SphereGeometry(1, 12, 8), toy = std(0.82, 0);
  const fig = batch(robeG, toy, true), head = batch(pplG, toy, true), dBox = batch(boxG, metal, true), dCyl = batch(cylG, metal, true);   // moving: the figures and their tools
  const lamp = batch(ballG, new THREE.MeshBasicMaterial({ color: '#ffffff' }), true), crate = batch(boxG, std(0.7, 0.05), true);
  const tentG = new THREE.ConeGeometry(1, 1, 4); tentG.rotateY(Math.PI / 4);
  const tent = batch(tentG, std(0.85, 0), false), dune = batch(ballG, std(0.95, 0), false);                                          // the camp: tents and dunes

  // ---- the building: floor, four rugs (one tone per hall), outer walls, the cross of inner walls with a bronze door frame in each, columns along the outer walls
  sBox.add(0, -0.1, 0, 26.8, 0.2, 20.8, '#bdb29d');
  for (const h of HALLS) sBox.add((h.x0 + h.x1) / 2, 0.012, (h.z0 + h.z1) / 2, 11.2, 0.03, 8.2, RUG[h.id]);
  const WALL = '#a99f8d', WH = 3.4, IH = 3.0;
  sBox.add(0, WH / 2, -10.2, 26.8, WH, 0.4, WALL); sBox.add(-4.075, WH / 2, 10.2, 18.65, WH, 0.4, WALL); sBox.add(10.575, WH / 2, 10.2, 5.65, WH, 0.4, WALL); sBox.add(START.x, 3.05, 10.2, 2.5, 0.7, 0.4, WALL); sBox.add(-13.2, WH / 2, 0, 0.4, WH, 20.8, WALL); sBox.add(13.2, WH / 2, 0, 0.4, WH, 20.8, WALL);
  for (const ax of ['x', 'z']) {
    const len = ax === 'x' ? 10 : 13, ds = DOORS.filter((d) => d.axis === ax).sort((a, b) => a.c - b.c); let from = -len;
    const seg = (a, b) => { if (b - a < 0.05) return; if (ax === 'x') sBox.add(0, IH / 2, (a + b) / 2, 0.3, IH, b - a, WALL); else sBox.add((a + b) / 2, IH / 2, 0, b - a, IH, 0.3, WALL); };
    for (const d of ds) {
      seg(from, d.c - d.half); from = d.c + d.half;
      if (ax === 'x') { bBox.add(0, 2.8, d.c, 0.38, 0.4, d.half * 2 + 0.3, BRONZE); bBox.add(0, 1.3, d.c - d.half, 0.4, 2.6, 0.14, BRONZE); bBox.add(0, 1.3, d.c + d.half, 0.4, 2.6, 0.14, BRONZE); }
      else { bBox.add(d.c, 2.8, 0, d.half * 2 + 0.3, 0.4, 0.38, BRONZE); bBox.add(d.c - d.half, 1.3, 0, 0.14, 2.6, 0.4, BRONZE); bBox.add(d.c + d.half, 1.3, 0, 0.14, 2.6, 0.4, BRONZE); }
    }
    seg(from, len);
  }
  bBox.add(0, 0.02, -9.95, 26.4, 0.1, 0.16, BRONZE); bBox.add(-4.0, 0.02, 9.95, 18.4, 0.1, 0.16, BRONZE); bBox.add(10.5, 0.02, 9.95, 5.4, 0.1, 0.16, BRONZE); bBox.add(-12.95, 0.02, 0, 0.16, 0.1, 20, BRONZE); bBox.add(12.95, 0.02, 0, 0.16, 0.1, 20, BRONZE);
  bBox.add(START.x - 1.25, 1.3, 9.95, 0.16, 2.6, 0.2, BRONZE); bBox.add(START.x + 1.25, 1.3, 9.95, 0.16, 2.6, 0.2, BRONZE); bBox.add(START.x, 2.7, 9.95, 2.66, 0.22, 0.2, BRONZE);   // the front door behind you
  const colAt = (x, z) => { sCyl.add(x, WH / 2, z, 0.27, WH, 0.27, MARBLE); sBox.add(x, WH + 0.1, z, 0.8, 0.2, 0.8, MARBLE); sBox.add(x, 0.1, z, 0.74, 0.2, 0.74, MARBLE); };
  for (const x of [-11, -6.5, -2, 2, 11]) { colAt(x, -9.7); colAt(x, 9.7); }
  colAt(6.5, -9.7);
  for (const z of [-5, 5]) { colAt(-12.7, z); colAt(12.7, z); }

  // ---- stations: platform, bronze rim, lamp post, conveyor belt, and the furniture of the job
  const figAt = S.map((s) => ({ x: s.x, z: s.z - 0.12 }));
  const platIdx = [];
  S.forEach((s, i) => {
    platIdx.push(sCyl.add(s.x, Y0 / 2, s.z, 1.15, Y0, 1.15, MARBLE));
    bCyl.add(s.x, 0.04, s.z, 1.27, 0.08, 1.27, BRONZE);
    bCyl.add(s.x + 0.95, 0.85, s.z - 0.62, 0.045, 1.7, 0.045, BRONZE);
    bBox.add(s.x, 0.1, s.z + 1.75, 2.7, 0.12, 0.5, BRONZE); bBox.add(s.x - 1.2, 0.03, s.z + 1.75, 0.1, 0.06, 0.6, '#6f4c2b'); bBox.add(s.x + 1.2, 0.03, s.z + 1.75, 0.1, 0.06, 0.6, '#6f4c2b');
    const px = s.x, pz = s.z + 0.5;
    if (s.job === 'scribe') { sBox.add(px, Y0 + 0.5, pz, 0.95, 0.06, 0.5, MARBLE); bBox.add(px - 0.4, Y0 + 0.24, pz, 0.06, 0.48, 0.42, BRONZE); bBox.add(px + 0.4, Y0 + 0.24, pz, 0.06, 0.48, 0.42, BRONZE); sBox.add(px - 0.05, Y0 + 0.545, pz, 0.5, 0.025, 0.32, '#efe6d2'); }
    else if (s.job === 'oracle') { for (let k = 0; k < 3; k++) { const a = k * 2.094 + 0.5; bCyl.add(px + Math.sin(a) * 0.15, Y0 + 0.33, pz + Math.cos(a) * 0.15, 0.022, 0.7, 0.022, BRONZE, Math.cos(a) * 0.36, 0, -Math.sin(a) * 0.36); } bCyl.add(px, Y0 + 0.68, pz, 0.26, 0.1, 0.26, GOLD); }
    else if (s.job === 'smith') { sBox.add(px, Y0 + 0.2, pz, 0.34, 0.4, 0.3, MARBLE); bBox.add(px, Y0 + 0.47, pz, 0.6, 0.16, 0.26, '#7a5631'); }
    else if (s.job === 'scales') { bCyl.add(px, Y0 + 0.43, pz, 0.03, 0.86, 0.03, BRONZE); bCyl.add(px, Y0 + 0.03, pz, 0.2, 0.06, 0.2, BRONZE); }
    else { bBox.add(px + 0.62, Y0 + 0.28, pz - 0.04, 0.08, 0.56, 0.08, BRONZE); bBox.add(px + 0.62, Y0 + 0.03, pz - 0.04, 0.5, 0.06, 0.34, BRONZE); }
  });
  // ---- THE BUILDERS' CAMP outside the front door: sand, a path, dunes, the hearth, and for each build agent a tent, a banner pole, a marble work table and a small brazier
  const SAND = '#c9a66b', cz0 = (CAMP.z0 + CAMP.z1) / 2;
  sBox.add(6.5, -0.12, cz0, 30, 0.2, CAMP.z1 - CAMP.z0 + 6, SAND); sBox.add(START.x, 0.0, 11.4, 2.2, 0.04, 3.4, '#dcc391'); sBox.add(START.x, 0.0, 16.9, 1.5, 0.04, 7.6, '#d6bb85');
  [[-6, 13, 4.5], [-7.5, 20, 6], [19.5, 14, 5], [20.5, 21, 6.5], [1, 25.5, 6], [8, 26.5, 7], [15, 25.5, 5.5], [-4.5, 25, 4.5]].forEach((dn) => dune.add(dn[0], -0.25, dn[1], dn[2], dn[2] * 0.3, dn[2] * 0.8, '#bf9a5e'));
  dune.add(-2.6, 0, 12.2, 0.5, 0.32, 0.45, '#a89a80'); dune.add(15.6, 0, 12.6, 0.6, 0.36, 0.5, '#a89a80'); dune.add(15.9, 0, 17.8, 0.4, 0.26, 0.4, '#a89a80');
  bCyl.add(CAMP.fire.x, 0.5, CAMP.fire.z, 0.36, 0.14, 0.36, BRONZE); for (let k = 0; k < 3; k++) { const a = k * 2.094; bCyl.add(CAMP.fire.x + Math.sin(a) * 0.28, 0.24, CAMP.fire.z + Math.cos(a) * 0.28, 0.03, 0.52, 0.03, BRONZE, Math.cos(a) * 0.4, 0, -Math.sin(a) * 0.4); }
  const TENT = ['#e6d9bd', '#c98f6a', '#d8c9a3', '#a9b07a', '#e0cfa8'];
  CAMP_SPOTS.forEach((c, j) => {
    tent.add(c.x, 1.0, c.z, 1.55, 2.0, 1.55, TENT[j % TENT.length]); tent.add(c.x, 2.12, c.z, 0.5, 0.5, 0.5, j % 2 ? '#9c6b3c' : '#c8a24a');
    sBox.add(c.x, 0.55, c.z - 1.02, 0.66, 1.1, 0.3, '#3a2c1c'); bCyl.add(c.x, 2.5, c.z, 0.025, 0.5, 0.025, GOLD);
    bCyl.add(c.x - 1.25, 1.3, c.z - 1.0, 0.035, 2.6, 0.035, BRONZE);
    sBox.add(c.x, 0.5, c.z - 2.45, 0.95, 0.06, 0.5, MARBLE); bBox.add(c.x - 0.4, 0.24, c.z - 2.45, 0.06, 0.48, 0.42, BRONZE); bBox.add(c.x + 0.4, 0.24, c.z - 2.45, 0.06, 0.48, 0.42, BRONZE);
    if (c.job === 'smith') bBox.add(c.x, 0.47, c.z - 2.45, 0.6, 0.16, 0.26, '#7a5631'); else sBox.add(c.x - 0.05, 0.545, c.z - 2.45, 0.5, 0.025, 0.32, '#efe6d2');
    bCyl.add(c.x + 1.15, 0.5, c.z - 1.7, 0.2, 0.12, 0.2, BRONZE); bCyl.add(c.x + 1.15, 0.22, c.z - 1.7, 0.03, 0.44, 0.03, BRONZE);
  });
  // moving parts: fixed slots per station (and per camp builder) so nothing is allocated while drawing
  for (let i = 0; i < N + NC; i++) { const lk = lookOf(i); for (let q = 0; q < 3; q++) fig.add(0, -9, 0, 1, 1, 1, lk.outfit);
    [lk.skin, lk.hair, '#2a2018', '#2a2018', lk.skin, lk.skin, lk.outfit, '#5a4030', '#5a4030'].forEach((c) => head.add(0, -9, 0, 1, 1, 1, c));
    for (let k = 0; k < 3; k++) { dBox.add(0, -9, 0, 1, 1, 1, k === 2 ? GOLD : BRONZE); dCyl.add(0, -9, 0, 1, 1, 1, BRONZE); } }
  S.forEach(() => { lamp.add(0, -9, 0, 1, 1, 1, LAMP.stale); for (let k = 0; k < MAXC; k++) crate.add(0, -9, 0, 1, 1, 1, '#b08a52'); });
  const EMBER0 = N, PUFF0 = N + 1 + NC, CR0 = N * MAXC;
  lamp.add(CAMP.fire.x, 0.64, CAMP.fire.z, 0.22, 0.15, 0.22, '#e89a3c');
  CAMP_SPOTS.forEach((c) => lamp.add(c.x + 1.15, 0.6, c.z - 1.7, 0.13, 0.09, 0.13, '#4a3a28'));
  CAMP_SPOTS.forEach(() => { for (let k = 0; k < PUFF; k++) lamp.add(0, -9, 0, 1, 1, 1, '#b3a58e'); });
  CAMP_SPOTS.forEach(() => { for (let k = 0; k < CSTACK; k++) crate.add(0, -9, 0, 1, 1, 1, '#b08a52'); });
  const SPOT = N + 1 + NC + NC * PUFF; lamp.add(0, -9, 0, 1, 1, 1, '#efe6d2');                              // the soft marble disc under the person you are talking to
  // board frames (the boards themselves are three canvases)
  const BOARDS = { board: { x: 10.35, y: 1.85, z: 0.17, w: 4.5, h: 2.5, ry: 0 }, changed: { x: 2.75, y: 1.85, z: 0.17, w: 4.5, h: 2.5, ry: 0 }, pipe: { x: -6.5, y: 1.85, z: 9.98, w: 9.2, h: 2.6, ry: Math.PI } };
  for (const k in BOARDS) { const b = BOARDS[k]; bBox.add(b.x, b.y, b.z - (b.ry ? -0.04 : 0.04), b.w + 0.24, b.h + 0.24, 0.06, BRONZE); }
  batches.forEach((b) => b.make());

  // ---- one canvas atlas for the 15 speech bubbles (name, status, what it says): ONE mesh, turned to the camera on the CPU
  const BW = 512, BH = 256, A = atlas(2048, 1024), quads = (n) => { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 12), 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(n * 8), 2)); const idx = []; for (let i = 0; i < n; i++) idx.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3); g.setIndex(idx); return g; };
  const flat = (tex) => new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, fog: false, toneMapped: false });
  const setUV = (g, i, u0, v0, u1, v1) => { const a = g.attributes.uv.array, k = i * 8; a[k] = u0; a[k + 1] = v0; a[k + 2] = u1; a[k + 3] = v0; a[k + 4] = u1; a[k + 5] = v1; a[k + 6] = u0; a[k + 7] = v1; g.attributes.uv.needsUpdate = true; };
  const RT = new THREE.Vector3(), UP = new THREE.Vector3();
  const setQuad = (g, i, x, y, z, w, h) => { const a = g.attributes.position.array, k = i * 12, rx = RT.x * w / 2, ry = RT.y * w / 2, rz = RT.z * w / 2, ux = UP.x * h / 2, uy = UP.y * h / 2, uz = UP.z * h / 2;
    a[k] = x - rx - ux; a[k + 1] = y - ry - uy; a[k + 2] = z - rz - uz; a[k + 3] = x + rx - ux; a[k + 4] = y + ry - uy; a[k + 5] = z + rz - uz; a[k + 6] = x + rx + ux; a[k + 7] = y + ry + uy; a[k + 8] = z + rz + uz; a[k + 9] = x - rx + ux; a[k + 10] = y - ry + uy; a[k + 11] = z - rz + uz; };
  const bubG = quads(N), bubbles = new THREE.Mesh(bubG, flat(A.t)); bubbles.frustumCulled = false; bubbles.renderOrder = 5; scene.add(bubbles);
  S.forEach((_, i) => { const cx = (i % 4) * BW, cy = Math.floor(i / 4) * BH; setUV(bubG, i, cx / 2048, 1 - (cy + BH) / 1024, (cx + BW) / 2048, 1 - cy / 1024); });
  const bubKey = S.map(() => '');
  function drawBubble(i, w) {
    const key = w ? w.name + '|' + w.status + '|' + w.say : S[i].name;
    if (bubKey[i] === key) return; bubKey[i] = key;
    const g = A.g, x = (i % 4) * BW, y = Math.floor(i / 4) * BH, st = w ? w.status : 'stale';
    g.clearRect(x, y, BW, BH);
    g.fillStyle = 'rgba(29,25,20,0.9)'; g.strokeStyle = BRONZE; g.lineWidth = 4; panel(g, x + 6, y + 6, BW - 12, BH - 40, 22);
    g.beginPath(); g.moveTo(x + BW / 2 - 18, y + BH - 36); g.lineTo(x + BW / 2, y + BH - 8); g.lineTo(x + BW / 2 + 18, y + BH - 36); g.closePath(); g.fillStyle = 'rgba(29,25,20,0.9)'; g.fill(); g.stroke();
    g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.fillStyle = '#f3ece0'; g.font = '600 38px Georgia, serif'; g.fillText(S[i].name, x + 26, y + 54);
    g.fillStyle = LAMP[st] || LAMP.stale; g.font = '700 26px -apple-system, "Segoe UI", sans-serif'; g.textAlign = 'right'; g.fillText(w ? WORD[st] : '...', x + BW - 26, y + 52); g.textAlign = 'left';
    g.fillStyle = BRONZE; g.fillRect(x + 26, y + 68, BW - 52, 2);
    g.fillStyle = '#e8dfcf'; g.font = '500 30px -apple-system, "Segoe UI", sans-serif'; wrap(g, w ? w.say || w.doing || '' : 'Waiting for its file...', x + 26, y + 108, BW - 52, 38, 3);
    A.t.needsUpdate = true;
  }
  S.forEach((_, i) => drawBubble(i, null));

  // ---- a second atlas: the crate tags (15 x 5) and the four hall signs: ONE mesh
  const TW = 256, TH = 64, T = atlas(2048, 1024), NT = N * MAXC, tagG = quads(NT + HALLS.length), tags = new THREE.Mesh(tagG, flat(T.t)); tags.frustumCulled = false; tags.renderOrder = 4; scene.add(tags);
  for (let i = 0; i < NT; i++) { const cx = (i % 8) * TW, cy = Math.floor(i / 8) * TH; setUV(tagG, i, cx / 2048, 1 - (cy + TH) / 1024, (cx + TW) / 2048, 1 - cy / 1024); }
  HALLS.forEach((h, k) => { const cx = k * 512, cy = 1024 - 128; setUV(tagG, NT + k, cx / 2048, 0, (cx + 512) / 2048, 128 / 1024);
    const g = T.g; g.fillStyle = 'rgba(29,25,20,0.88)'; g.strokeStyle = GOLD; g.lineWidth = 4; panel(g, cx + 6, cy + 14, 500, 100, 20); g.fillStyle = '#e0b060'; g.font = '600 54px Georgia, serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(h.name, cx + 256, cy + 66); });
  const tagKey = new Array(NT).fill('');
  function drawTag(i, text, st) {
    const key = text + '|' + st; if (tagKey[i] === key) return; tagKey[i] = key;
    const g = T.g, x = (i % 8) * TW, y = Math.floor(i / 8) * TH; g.clearRect(x, y, TW, TH);
    if (!text) { T.t.needsUpdate = true; return; }
    g.fillStyle = 'rgba(38,33,27,0.92)'; g.strokeStyle = st === 'failed' ? LAMP.failed : BRONZE; g.lineWidth = 3; panel(g, x + 3, y + 5, TW - 6, TH - 10, 12);
    g.fillStyle = '#f3ece0'; g.font = '600 28px -apple-system, "Segoe UI", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    let t = String(text); while (t.length > 3 && g.measureText(t).width > TW - 22) t = t.slice(0, -1); g.fillText(t, x + TW / 2, y + TH / 2 + 1);
    T.t.needsUpdate = true;
  }

  // ---- the camp's atlas: for each builder a banner (name, job, status) and a parchment scroll that cycles its latest commit messages: ONE mesh
  const CA = atlas(2048, 1024), campG = quads(NC), campM = new THREE.Mesh(campG, flat(CA.t)); campM.frustumCulled = false; campM.renderOrder = 5; scene.add(campM);
  CAMP_SPOTS.forEach((_, j) => { const cx = (j % 4) * BW, cy = Math.floor(j / 4) * BH; setUV(campG, j, cx / 2048, 1 - (cy + BH) / 1024, (cx + BW) / 2048, 1 - cy / 1024); });
  let camp = []; const campKey = CAMP_SPOTS.map(() => '');
  function drawCamp(j, line) {
    const b = camp[j], key = b ? b.name + '|' + b.status + '|' + line + '|' + b.mins : '-';
    if (campKey[j] === key) return; campKey[j] = key;
    const g = CA.g, x = (j % 4) * BW, y = Math.floor(j / 4) * BH; g.clearRect(x, y, BW, BH);
    if (!b) { CA.t.needsUpdate = true; return; }
    g.textBaseline = 'alphabetic'; g.textAlign = 'left';
    g.fillStyle = '#7a4a2c'; g.strokeStyle = GOLD; g.lineWidth = 4; panel(g, x + 6, y + 6, BW - 12, 92, 14);                       // the banner
    g.fillStyle = '#f6ecd6'; g.font = '600 36px Georgia, serif'; let nm = b.name; while (nm.length > 4 && g.measureText(nm).width > BW - 190) nm = nm.slice(0, -1); g.fillText(nm, x + 24, y + 48);
    g.fillStyle = BUILD[b.status]; g.beginPath(); g.arc(x + BW - 150, y + 37, 9, 0, 6.3); g.fill(); g.fillStyle = '#f6ecd6'; g.font = '700 24px -apple-system, "Segoe UI", sans-serif'; g.fillText(BWORD[b.status], x + BW - 134, y + 46);
    g.fillStyle = '#ecd9b4'; g.font = '500 22px -apple-system, "Segoe UI", sans-serif'; let jb = b.job; while (jb.length > 4 && g.measureText(jb).width > BW - 48) jb = jb.slice(0, -2); g.fillText(jb === b.job ? jb : jb + '…', x + 24, y + 82);
    g.fillStyle = '#eadcbc'; g.strokeStyle = '#9c6b3c'; g.lineWidth = 3; panel(g, x + 18, y + 106, BW - 36, 140, 10);                 // the scroll
    g.fillStyle = '#9c6b3c'; g.fillRect(x + 10, y + 102, BW - 20, 8); g.fillRect(x + 10, y + 242, BW - 20, 8);
    g.fillStyle = '#3a2c1c'; g.font = '600 28px -apple-system, "Segoe UI", sans-serif'; wrap(g, line, x + 34, y + 148, BW - 68, 34, 2);
    g.fillStyle = '#7a5631'; g.font = '500 22px -apple-system, "Segoe UI", sans-serif'; g.fillText((b.sample ? 'example · ' : '') + (b.status === 'job' ? 'no live activity' : b.mins == null ? '' : 'last commit ' + (b.mins < 90 ? b.mins + ' min ago' : Math.round(b.mins / 60) + ' h ago')), x + 34, y + 228);
    CA.t.needsUpdate = true;
  }

  // ---- three wall boards: the Learning board and "what changed our mind" (Library), the research pipeline (Research hall)
  const mkBoard = (b, cw, ch) => { const C = atlas(cw, ch), m = new THREE.Mesh(new THREE.PlaneGeometry(b.w, b.h), new THREE.MeshBasicMaterial({ map: C.t, fog: false, toneMapped: false })); m.position.set(b.x, b.y, b.z); m.rotation.y = b.ry; scene.add(m); return { C, m, cw, ch }; };
  const bLearn = mkBoard(BOARDS.board, 1024, 568), bFlip = mkBoard(BOARDS.changed, 1024, 568), bPipe = mkBoard(BOARDS.pipe, 1536, 434);
  function boardHead(B, title, sub) { const g = B.C.g; g.fillStyle = '#1d1914'; g.fillRect(0, 0, B.cw, B.ch); g.textAlign = 'left'; g.textBaseline = 'alphabetic'; g.fillStyle = GOLD; g.font = '600 46px Georgia, serif'; g.fillText(title, 34, 64); g.fillRect(34, 78, 130, 3);
    if (sub) { g.fillStyle = '#9a8f7d'; g.font = '500 24px -apple-system, "Segoe UI", sans-serif'; g.textAlign = 'right'; g.fillText(sub, B.cw - 34, 60); g.textAlign = 'left'; } return g; }
  function drawLearn(bd) {
    const L = bd ? (bd.week && bd.week.length ? bd.week : bd.top || []) : [], g = boardHead(bLearn, 'Learning board', bd && bd.week && bd.week.length ? 'top lessons of the week' : L.length ? 'strongest lessons' : ''); let y = 126;
    if (!L.length) { g.fillStyle = '#cfc4b2'; g.font = '500 28px -apple-system, sans-serif'; g.fillText('No lessons are written down yet.', 34, y); }
    for (const l of L.slice(0, 4)) {
      if (y > bLearn.ch - 70) break;
      g.fillStyle = '#e0b060'; g.font = '600 24px -apple-system, "Segoe UI", sans-serif'; g.fillText(l.cat + '  ·  ' + (l.d || 'undated') + '  ·  ' + l.strength + (l.strength === 1 ? ' file' : ' files agree') + (l.sample ? '  ·  example' : ''), 34, y);
      g.fillStyle = '#f3ece0'; g.font = '500 28px -apple-system, "Segoe UI", sans-serif'; const n = wrap(g, l.text, 34, y + 34, bLearn.cw - 68, 33, 2); y += 34 + n * 33 + 26;
    }
    bLearn.C.t.needsUpdate = true;
  }
  function drawFlip(bd) {
    const L = bd ? bd.changed || [] : [], g = boardHead(bFlip, 'What changed our mind', L.length ? 'beliefs that did not hold' : ''); let y = 126;
    if (!L.length) { g.fillStyle = '#cfc4b2'; g.font = '500 28px -apple-system, sans-serif'; g.fillText('Nothing has overturned an earlier belief yet.', 34, y); }
    for (const c of L.slice(0, 3)) {
      if (y > bFlip.ch - 70) break;
      g.fillStyle = '#c96a4a'; g.font = '600 24px -apple-system, "Segoe UI", sans-serif'; g.fillText(c.cat + '  ·  ' + (c.d || 'undated') + (c.sample ? '  ·  example' : ''), 34, y);
      g.fillStyle = '#f3ece0'; g.font = '500 28px -apple-system, "Segoe UI", sans-serif'; const n = wrap(g, c.text, 34, y + 34, bFlip.cw - 68, 33, 3); y += 34 + n * 33 + 26;
    }
    bFlip.C.t.needsUpdate = true;
  }
  function drawPipe(pp) {
    const g = boardHead(bPipe, 'Research pipeline', pp && pp.ok ? 'idea  →  testing  →  verdict' + (pp.sample ? '  ·  example' : '') : ''), W = bPipe.cw;
    if (!pp || !pp.ok) { g.fillStyle = '#cfc4b2'; g.font = '500 28px -apple-system, sans-serif'; g.fillText('No pipeline counts are published yet.', 34, 130); bPipe.C.t.needsUpdate = true; return; }
    const tone = { ideas: GOLD, testing: '#4b7a99', adopted: '#8fa05a', rejected: '#c96a4a' }, cw = (W - 68 - 3 * 28) / 4;
    pp.lanes.forEach((l, i) => { const x = 34 + i * (cw + 28); g.fillStyle = '#26211b'; g.strokeStyle = tone[l.id]; g.lineWidth = 3; panel(g, x, 104, cw, 112, 14);
      g.fillStyle = tone[l.id]; g.font = '600 28px Georgia, serif'; g.textAlign = 'left'; g.fillText(l.label, x + 18, 142); g.fillStyle = '#f3ece0'; g.font = '700 52px -apple-system, "Segoe UI", sans-serif'; g.fillText(l.n.toLocaleString('en-US'), x + 18, 198);
      if (i < 3) { g.fillStyle = '#9a8f7d'; g.font = '600 30px sans-serif'; g.fillText(i === 0 ? '→' : i === 1 ? '→' : '·', x + cw + 2, 170); } });
    let y = 258; const fams = pp.families.slice(0, 5), bw = W - 68 - 330;
    for (const f of fams) { g.fillStyle = '#cfc4b2'; g.font = '500 24px -apple-system, "Segoe UI", sans-serif'; g.textAlign = 'left'; g.fillText(f.name + '  ' + f.runs, 34, y + 20);
      let x = 34 + 330; g.fillStyle = tone.adopted; g.fillRect(x, y, Math.max(f.adopted ? 3 : 0, bw * f.pa), 22); x += bw * f.pa; g.fillStyle = tone.rejected; g.fillRect(x, y, bw * f.pr, 22); x += bw * f.pr; g.fillStyle = tone.testing; g.fillRect(x, y, bw * f.po, 22); y += 34; }
    bPipe.C.t.needsUpdate = true;
  }
  drawLearn(null); drawFlip(null); drawPipe(null);

  // ---- state
  let workers = [], cam = { x: START.x, z: START.z, yaw: START.yaw, pitch: -0.06 }, yawT = cam.yaw, pitchT = cam.pitch, mv = { fwd: 0, side: 0 }, mvT = { fwd: 0, side: 0 }, mode = 'walk', following = null, t = 0, tourT = 0;
  const ray = new THREE.Raycaster(), ang = S.map((_, i) => i * 1.7).concat(CAMP_SPOTS.map((_, j) => j * 2.3)), COLL = S.concat(CAMP_SPOTS, CAMP_SPOTS.map((c) => ({ x: c.x, z: c.z - 2.1 }))), hot = {}, cratePos = new Float32Array(N * MAXC * 3);
  const pos = () => ({ x: cam.x, z: cam.z, yaw: cam.yaw, following, mode, hall: hallOf(mode === 'tour' ? { x: camera.position.x, z: camera.position.z } : cam).id });
  const nCrates = (w) => Math.max(0, Math.min(MAXC, w && w.crates ? w.crates.length : 0));
  // an arm: a cylinder from the shoulder, swung forward by `a` radians (0 = hanging down, 1.57 = straight ahead) and outward by `out`; returns the hand position
  // ---- A PERSON (the look of docs/PERSONA_API.md, our own instanced version): a friendly cartoon character with a big round head, dot eyes that blink, a cap of hair, a short rounded
  // body in a coloured tunic, mitten hands and feet. Every part is an instance of the shared batches. A person does its job, waves when you come near, turns to face you and talks
  // while you chat with it (a soft marble disc on the floor marks it: no glow), cheers when its work is merged and slumps when its run failed.
  const hand = { x: 0, y: 0, z: 0 }, AXY = new THREE.Vector3(0, 1, 0), qT = new THREE.Quaternion(), thA = new Float32Array(N + NC), nearT = new Float32Array(N + NC).fill(-99), wasNear = new Uint8Array(N + NC);
  let oX = 0, oZ = 0, cT = 1, sT = 0, focusKey = '';
  for (let j = 0; j < NC; j++) thA[N + j] = Math.PI;
  const pl = (im, slot, lx, ly, lz, sx, sy, sz, rx, ry, rz) => { EU.set(rx || 0, ry || 0, rz || 0, 'XYZ'); Q.setFromEuler(EU).premultiply(qT); M4.compose(P.set(oX + lx * cT + lz * sT, ly, oZ - lx * sT + lz * cT), Q, SC.set(sx, sy, sz)); im.setMatrixAt(slot, M4); };
  const gone = (im, j) => put(im, j, 0, -9, 0, 0.001, 0.001, 0.001);
  // when the shared people kit's 3D module is there (olympus/people3d.js, optional), each person takes the colours of its own spec(id): the same character as in the chat. Without it the seeded look above stays.
  let specFn = null;
  function dress() {
    if (!specFn) return;
    const paint = (i, id) => { try { const sp = id && specFn(id); if (!sp) return; const ok = (c) => typeof c === 'string' && /^#[0-9a-f]{6}$/i.test(c);
      if (ok(sp.outfit)) { for (let q = 0; q < 3; q++) fig.im.setColorAt(i * 3 + q, colour.set(sp.outfit)); head.im.setColorAt(i * HS + 6, colour.set(sp.outfit)); }
      if (ok(sp.skin)) [0, 4, 5].forEach((q) => head.im.setColorAt(i * HS + q, colour.set(sp.skin))); if (ok(sp.hair)) head.im.setColorAt(i * HS + 1, colour.set(sp.hair)); } catch (_) { /* its seeded look stays */ } };
    S.forEach((st, i) => paint(i, personId(st.id))); camp.forEach((b, j) => { if (b) paint(N + j, builderIds(b.branch)[0]); });
    fig.im.instanceColor.needsUpdate = true; head.im.instanceColor.needsUpdate = true;
  }
  import('../olympus/people3d.js').then((m) => { specFn = m && typeof m.spec === 'function' ? m.spec : null; dress(); }).catch(() => { /* optional */ });
  function hideActor(i) { for (let q = 0; q < 3; q++) { gone(fig.im, i * 3 + q); gone(dBox.im, i * 3 + q); gone(dCyl.im, i * 3 + q); } for (let q = 0; q < HS; q++) gone(head.im, i * HS + q); }
  // an arm from the shoulder (local x = sxl), swung forward by `a` (0 hangs down, 1.57 straight ahead, 3 overhead) and outward by `out`, ending in a mitten hand
  function arm(i, side, sy, a, out) {
    const AL = 0.4, sxl = side * 0.23, dx = Math.sin(out), dy = -Math.cos(a) * Math.cos(out), dz = Math.sin(a) * Math.cos(out);
    pl(fig.im, i * 3 + (side > 0 ? 1 : 2), sxl + dx * AL / 2, sy + dy * AL / 2, 0.02 + dz * AL / 2, 0.055, AL, 0.055, -a, 0, out);
    hand.x = sxl + dx * AL; hand.y = sy + dy * AL; hand.z = 0.02 + dz * AL;
    pl(head.im, i * HS + (side > 0 ? 4 : 5), hand.x, hand.y, hand.z, 0.07, 0.07, 0.07);
  }
  function actor(i, job, fx, fz, yb, th0, pz, k, mood, key, dt, camP) {
    const a = ang[i], b3 = i * 3, h0 = i * HS, dC = Math.hypot(camP.x - fx, camP.z - fz), talking = focusKey === key, close = mode === 'walk' && dC < 3.4;
    if (close && !wasNear[i]) nearT[i] = t; wasNear[i] = close ? 1 : 0;
    const pose = talking ? 'talk' : close && t - nearT[i] < 2.6 ? 'wave' : mood;
    // turn: toward you while waving or talking, back to the work otherwise (eased; reduced motion turns at once)
    let want = pose === 'talk' || pose === 'wave' ? Math.atan2(camP.x - fx, camP.z - fz) : th0, dth = want - thA[i]; while (dth > Math.PI) dth -= Math.PI * 2; while (dth < -Math.PI) dth += Math.PI * 2;
    thA[i] = reduced ? want : thA[i] + dth * Math.min(1, dt * 6);
    oX = fx; oZ = fz; cT = Math.cos(thA[i]); sT = Math.sin(thA[i]); qT.setFromAxisAngle(AXY, thA[i]);
    const live = k > 0 || pose === 'talk' || pose === 'wave' || pose === 'cheer', bob = mot * (pose === 'cheer' ? Math.abs(Math.sin(t * 3 + i)) * 0.07 : live ? 0.012 * Math.sin(a * 2.1 + t * 1.3) : 0.006 * Math.sin(t * 1.1 + i));
    const sl = pose === 'slump' ? 1 : 0, y = yb + bob, shY = y + 0.66 - sl * 0.04, hy = y + 1.0 - sl * 0.07 + (pose === 'talk' ? 0.012 * Math.sin(t * 5) * mot : 0), hz = sl * 0.07;
    pl(fig.im, b3, 0, y + 0.3, 0, 0.23, 0.5, 0.21);                                                                 // the tunic
    pl(head.im, h0 + 6, 0, y + 0.58, 0, 0.235 + 0.006 * Math.sin(t * 1.6 + i) * mot, 0.19, 0.2);                    // rounded shoulders (it breathes)
    pl(head.im, h0, 0, hy, hz, 0.25, 0.24, 0.245, sl * 0.3, 0, 0);                                                  // the big round head
    pl(head.im, h0 + 1, 0, hy + 0.055, hz - 0.05, 0.262, 0.235, 0.25, sl * 0.3, 0, 0);                              // hair
    const blink = mot && ((t * 0.31 + i * 0.37) % 1) < 0.035 ? 0.006 : 0.042, look = pose === 'talk' || pose === 'wave' ? 0 : Math.sin(t * 0.5 + i * 2.1) * 0.02 * mot;
    pl(head.im, h0 + 2, 0.085 + look, hy + 0.015 - sl * 0.02, hz + 0.228, 0.03, sl ? 0.012 : blink, 0.02); pl(head.im, h0 + 3, -0.085 + look, hy + 0.015 - sl * 0.02, hz + 0.228, 0.03, sl ? 0.012 : blink, 0.02);
    pl(head.im, h0 + 7, 0.1, yb + 0.04, 0.05, 0.085, 0.05, 0.13); pl(head.im, h0 + 8, -0.1, yb + 0.04, 0.05, 0.085, 0.05, 0.13);   // feet
    const toolsOff = () => { for (let q = 0; q < 3; q++) { gone(dBox.im, b3 + q); gone(dCyl.im, b3 + q); } };
    if (pose === 'talk') { arm(i, 1, shY, 1.15 + 0.28 * Math.sin(t * 3.1) * mot, 0.25); arm(i, -1, shY, 0.5 + 0.12 * Math.sin(t * 2.3 + 1) * mot, -0.2); toolsOff(); return; }
    if (pose === 'wave') { arm(i, 1, shY, 2.75, 0.45 + 0.4 * Math.sin(t * 8) * mot); arm(i, -1, shY, 0.2, -0.15); toolsOff(); return; }
    if (pose === 'cheer') { arm(i, 1, shY, 2.8, 0.45 + 0.1 * Math.sin(t * 6) * mot); arm(i, -1, shY, 2.8, -0.45 - 0.1 * Math.sin(t * 6) * mot); toolsOff(); return; }
    if (pose === 'slump') { arm(i, 1, shY, 0.08, 0.1); arm(i, -1, shY, 0.08, -0.1); toolsOff(); return; }
    const ty = yb;                                                                                                   // the furniture stands on the same base as the person
    if (job === 'wheel') {
      const sp = a * 2.2, wy = ty + 0.56, wx = 0.62, wz = pz + 0.06;
      pl(dCyl.im, b3, wx, wy, wz, 0.36, 0.05, 0.36, Math.PI / 2, sp, 0);
      pl(dBox.im, b3, wx, wy, wz + 0.035, 0.7, 0.05, 0.03, 0, 0, sp); pl(dBox.im, b3 + 1, wx, wy, wz + 0.035, 0.7, 0.05, 0.03, 0, 0, sp + Math.PI / 2);
      pl(dBox.im, b3 + 2, wx + Math.cos(sp) * 0.3, wy + Math.sin(sp) * 0.3, wz + 0.09, 0.07, 0.07, 0.12);
      arm(i, 1, shY, 1.5 + Math.sin(sp) * 0.3, 0.75 + Math.cos(sp) * 0.2); arm(i, -1, shY, 0.35, -0.1);
      gone(dCyl.im, b3 + 1); gone(dCyl.im, b3 + 2);
    } else if (job === 'scribe') {
      const wr = Math.sin(a * 5) * 0.16, dip = Math.sin(a * 10) * 0.03;
      arm(i, 1, shY, 1.5 + dip, -0.2 + wr); pl(dCyl.im, b3, hand.x, hand.y + 0.06, hand.z + 0.04, 0.012, 0.24, 0.012, -0.5, 0, 0.3);
      arm(i, -1, shY, 1.45, 0.2);
      gone(dCyl.im, b3 + 1); gone(dCyl.im, b3 + 2); gone(dBox.im, b3); gone(dBox.im, b3 + 1); gone(dBox.im, b3 + 2);
    } else if (job === 'oracle') {
      const sw = Math.sin(a * 1.4) * 0.22;
      arm(i, 1, shY, 2.3 + sw, 0.45); arm(i, -1, shY, 2.3 - sw, -0.45);
      const fl = 0.07 + 0.025 * Math.sin(a * 6) * (k ? 1 : 0);
      if (k <= 0) gone(dBox.im, b3 + 2); else pl(dBox.im, b3 + 2, 0, ty + 0.76 + fl, pz, fl, fl * 1.6, fl, 0, a * 1.5, 0.78);
      gone(dBox.im, b3); gone(dBox.im, b3 + 1); gone(dCyl.im, b3); gone(dCyl.im, b3 + 1); gone(dCyl.im, b3 + 2);
    } else if (job === 'smith') {
      const c = Math.cos(a * 4), up = 1.6 + 0.45 * Math.max(-1, Math.min(1, c * 1.6));        // a quick blow, a slower lift
      arm(i, 1, shY, up, 0.05);
      const ha = Math.PI - (up + 1.2), hdy = Math.cos(ha), hdz = Math.sin(ha);                    // the hammer carries on past the hand, bent forward of the forearm
      pl(dCyl.im, b3, hand.x, hand.y + hdy * 0.16, hand.z + hdz * 0.16, 0.02, 0.34, 0.02, ha, 0, 0);
      pl(dBox.im, b3, hand.x, hand.y + hdy * 0.32, hand.z + hdz * 0.32, 0.2, 0.11, 0.11, ha, 0, 0);
      arm(i, -1, shY, 1.3, 0.12);
      pl(dBox.im, b3 + 2, -0.12, ty + 0.57, pz, 0.22, 0.03, 0.08);                                 // the gold piece on the anvil
      gone(dBox.im, b3 + 1); gone(dCyl.im, b3 + 1); gone(dCyl.im, b3 + 2);
    } else {
      const tilt = Math.sin(a * 1.3) * 0.2 * (k ? 1 : 0), by = ty + 0.86, c = Math.cos(tilt), sn = Math.sin(tilt);
      pl(dBox.im, b3, 0, by, pz, 0.92, 0.035, 0.045, 0, 0, tilt);
      pl(dCyl.im, b3, -0.45 * c, by - 0.45 * sn - 0.24, pz, 0.15, 0.025, 0.15); pl(dCyl.im, b3 + 1, 0.45 * c, by + 0.45 * sn - 0.24, pz, 0.15, 0.025, 0.15);
      pl(dBox.im, b3 + 1, -0.45 * c, by - 0.45 * sn - 0.12, pz, 0.012, 0.24, 0.012); pl(dBox.im, b3 + 2, 0.45 * c, by + 0.45 * sn - 0.12, pz, 0.012, 0.24, 0.012);
      arm(i, 1, shY, 1.35 + sn * 0.5, 0.3); arm(i, -1, shY, 1.35 - sn * 0.5, -0.3);
      gone(dCyl.im, b3 + 2);
    }
  }
  // a camp builder: the same marble figure, facing north (toward the door you come from), writing or hammering at its table
  function campFrame(dt, camP) {
    const hide = (im, j) => put(im, j, 0, -9, 0, 0.001, 0.001, 0.001);
    CAMP_SPOTS.forEach((c, j) => {
      const b = camp[j], i = N + j, b3 = i * 3, st = b ? b.status : 'job', k = (st === 'working' ? 1 : st === 'quiet' ? 0.22 : 0) * mot;
      ang[i] += dt * k;
      if (!b) { hideActor(i); for (let q = 0; q < PUFF; q++) hide(lamp.im, PUFF0 + j * PUFF + q); for (let q = 0; q < CSTACK; q++) hide(crate.im, CR0 + j * CSTACK + q); setQuad(campG, j, 0, -9, 0, 0, 0); return; }
      actor(i, c.job, c.x, c.z - 1.9, 0, Math.PI, 0.55, k, st === 'done' ? 'cheer' : '', 'b:' + b.id, dt, camP);
      // brazier smoke only while it is working; the ember glows then
      for (let q = 0; q < PUFF; q++) { const ph = ((t * 0.3 * (mot || 0) + q / PUFF + j * 0.37) % 1 + 1) % 1; if (st !== 'working') hide(lamp.im, PUFF0 + j * PUFF + q); else put(lamp.im, PUFF0 + j * PUFF + q, c.x + 1.15 + Math.sin(ph * 5 + j) * 0.18 * ph, 0.75 + ph * 2.0, c.z - 1.7, 0.05 + 0.11 * ph, 0.05 + 0.11 * ph, 0.05 + 0.11 * ph); }
      const eg = st === 'working' ? 1 + 0.15 * Math.sin(t * 7 + j) * mot : 0.8; put(lamp.im, EMBER0 + 1 + j, c.x + 1.15, 0.6, c.z - 1.7, 0.13 * eg, 0.09 * eg, 0.13 * eg);
      // its stack of crates = commits today
      for (let q = 0; q < CSTACK; q++) { if (q >= b.crates) hide(crate.im, CR0 + j * CSTACK + q); else put(crate.im, CR0 + j * CSTACK + q, c.x - 1.05 + (q % 3) * 0.3 + (q > 2 ? 0.15 : 0), 0.13 + (q > 2 ? 0.26 : 0), c.z - 2.5, 0.27, 0.25, 0.27, 0, (j + q) * 0.4, 0); }
      // the banner and the scroll, over the tent; the scroll moves on to the next commit message every few seconds
      const n = b.scroll.length, idx = mot ? Math.floor((t + j * 1.7) / 5.5) % n : 0; drawCamp(j, b.scroll[idx]);
      const d = Math.hypot(camP.x - c.x, camP.z - c.z), sc = (mode === 'tour' ? 1.15 : 1) * (0.62 + 0.38 * Math.min(1, d / 6.5));
      setQuad(campG, j, c.x, 2.85 + sc * 0.75 + (mot ? Math.sin(t * 0.9 + j) * 0.03 : 0), c.z - 0.9, 2.7 * sc, 1.35 * sc);
    });
    const fp = 1 + 0.1 * Math.sin(t * 6) * mot; put(lamp.im, EMBER0, CAMP.fire.x, 0.64, CAMP.fire.z, 0.22 * fp, 0.15 * fp, 0.22 * fp);
    campG.attributes.position.needsUpdate = true;
  }
  function frame(dt) {
    t += dt;
    const camP = camera.position;
    S.forEach((s, i) => {
      const w = workers[i], st = w ? w.status : 'stale', isHot = (hot[s.id] || 0) > t, k = Math.max(PACE[st] || 0, isHot ? 1 : 0) * mot;
      ang[i] += dt * k;
      actor(i, s.job, figAt[i].x, figAt[i].z, Y0, 0, 0.62, k, st === 'failed' ? 'slump' : '', 'w:' + s.id, dt, camP);
      const pulse = isHot && mot ? 1.25 + 0.2 * Math.sin(t * 6) : 1;
      put(lamp.im, i, s.x + 0.95, 1.78, s.z - 0.62, 0.15 * pulse, 0.15 * pulse, 0.15 * pulse);
      // the conveyor: crates drift left to right at the worker's pace; a stopped worker's belt stands still
      const n = nCrates(w), near = Math.hypot(camP.x - s.x, camP.z - s.z) < 10 || following === s.id;
      for (let c = 0; c < MAXC; c++) {
        const idx = i * MAXC + c;
        if (c >= n) { put(crate.im, idx, 0, -9, 0, 0.001, 0.001, 0.001); setQuad(tagG, idx, 0, -9, 0, 0, 0); cratePos[idx * 3 + 1] = -9; continue; }
        const fr = (((c / n) + ang[i] * 0.06) % 1 + 1) % 1, cx = s.x - 1.15 + fr * 2.3, cz = s.z + 1.75;
        put(crate.im, idx, cx, 0.3, cz, 0.3, 0.26, 0.3); cratePos[idx * 3] = cx; cratePos[idx * 3 + 1] = 0.3; cratePos[idx * 3 + 2] = cz;
        const td = Math.min(1, Math.hypot(camP.x - cx, camP.z - cz) / 4.5), ts = 0.45 + 0.55 * td;
        if (near) setQuad(tagG, idx, cx, 0.6 + (c % 2) * 0.17 * ts + 0.1 * ts, cz, 0.84 * ts, 0.21 * ts); else setQuad(tagG, idx, 0, -9, 0, 0, 0);
      }
    });
    [fig, head, dBox, dCyl, lamp, crate].forEach((b) => { b.im.instanceMatrix.needsUpdate = true; });
    const campLater = () => campFrame(dt, camP);
    // the camera: walking (eased joystick and look), following a worker, or the calm tour above the halls
    const rate = reduced ? 0 : 1;
    if (mode === 'tour') {
      tourT += dt * mot;
      const tc = tourCam(tourT, reduced), k = reduced ? 1 : Math.min(1, dt * 1.6);
      camP.x += (tc.x - camP.x) * k; camP.y += (tc.y - camP.y) * k; camP.z += (tc.z - camP.z) * k; camera.lookAt(tc.look.x, tc.look.y, tc.look.z);
    } else if (mode === 'follow' && following) {
      const i = S.findIndex((s) => s.id === following);
      if (i >= 0) { const fc = followCam({ x: figAt[i].x, z: figAt[i].z }, t, reduced), k = reduced ? 1 : Math.min(1, dt * 2.2);
        camP.x += (fc.x - camP.x) * k; camP.y += (fc.y - camP.y) * k; camP.z += (fc.z - camP.z) * k; camera.lookAt(fc.look.x, fc.look.y + 0.35, fc.look.z); }
    } else {
      mv.fwd = ease(mv.fwd, mvT.fwd, dt, rate * 9); mv.side = ease(mv.side, mvT.side, dt, rate * 9);
      if (Math.abs(mv.fwd) > 0.004 || Math.abs(mv.side) > 0.004) { const p = walk({ x: cam.x, z: cam.z }, cam.yaw, mv, dt, COLL); cam.x = p.x; cam.z = p.z; }
      cam.yaw = ease(cam.yaw, yawT, dt, rate * 18); cam.pitch = ease(cam.pitch, pitchT, dt, rate * 18);
      const k = reduced ? 1 : Math.min(1, dt * 7);
      camP.x += (cam.x - camP.x) * k; camP.y += (eye - camP.y) * k; camP.z += (cam.z - camP.z) * k;
      camera.rotation.order = 'YXZ'; camera.rotation.set(cam.pitch, cam.yaw, 0);
    }
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
    // bubbles, tags and hall signs face the camera
    RT.setFromMatrixColumn(camera.matrixWorld, 0); UP.setFromMatrixColumn(camera.matrixWorld, 1);
    const big = mode === 'tour' ? 1.2 : 1;
    S.forEach((s, i) => { const d = Math.hypot(camP.x - s.x, camP.z - s.z), sc = big * (0.6 + 0.4 * Math.min(1, d / 6)); setQuad(bubG, i, figAt[i].x, Y0 + 1.95 + sc * 0.3, figAt[i].z, 2.5 * sc, 1.25 * sc); });
    const inHall = mode === 'tour' ? '' : hallOf({ x: camP.x, z: camP.z }).id;
    HALLS.forEach((h, k) => { if (h.id === inHall) setQuad(tagG, NT + k, 0, -9, 0, 0, 0); else setQuad(tagG, NT + k, (h.x0 + h.x1) / 2, mode === 'tour' ? 4.6 : 4.1, (h.z0 + h.z1) / 2, 3.4 * big, 0.85 * big); });
    campLater();
    { let fx = null, fz = 0, fy = 0; if (focusKey) { const si = S.findIndex((x) => 'w:' + x.id === focusKey), ci = camp.findIndex((b) => b && 'b:' + b.id === focusKey); if (si >= 0) { fx = figAt[si].x; fz = figAt[si].z; fy = Y0; } else if (ci >= 0) { fx = CAMP_SPOTS[ci].x; fz = CAMP_SPOTS[ci].z - 1.9; } }
      if (fx == null) gone(lamp.im, SPOT); else put(lamp.im, SPOT, fx, fy + 0.012, fz, 0.78, 0.008, 0.78); } [fig, head, dBox, dCyl, lamp, crate].forEach((b) => { b.im.instanceMatrix.needsUpdate = true; });
    bubG.attributes.position.needsUpdate = true; tagG.attributes.position.needsUpdate = true;
    rc.render();
  }
  const snapCam = () => { camera.position.set(cam.x, eye, cam.z); };
  const still = () => { if (reduced) frame(0.001); };
  const api = {
    ok: true, mode: '3d', rc,
    /** workers = the page's worker rows; extra = { board (week / top / changed), pipe } for the wall boards */
    set(ws, extra) {
      workers = S.map((s) => (ws || []).find((w) => w.id === s.id) || null);
      workers.forEach((w, i) => {
        drawBubble(i, w); lamp.im.setColorAt(i, colour.set(LAMP[w ? w.status : 'stale'] || LAMP.stale));
        for (let c = 0; c < MAXC; c++) { const cr = w && w.crates && w.crates[c]; drawTag(i * MAXC + c, cr ? cr.tag : '', w ? w.status : 'stale'); crate.im.setColorAt(i * MAXC + c, colour.set(w && w.status === 'failed' ? '#a8573d' : w && w.status === 'sample' ? '#a39a88' : '#b08a52')); }
      });
      if (lamp.im.instanceColor) lamp.im.instanceColor.needsUpdate = true; if (crate.im.instanceColor) crate.im.instanceColor.needsUpdate = true;
      if (extra) { drawLearn(extra.board || null); drawFlip(extra.board || null); drawPipe(extra.pipe || null); if (extra.camp) { camp = CAMP_SPOTS.map((_, j) => extra.camp[j] || null); lamp.im.setColorAt(EMBER0, colour.set('#e89a3c'));
        camp.forEach((b, j) => { lamp.im.setColorAt(EMBER0 + 1 + j, colour.set(b && b.status === 'working' ? '#e8923a' : '#4a3a28')); for (let q = 0; q < CSTACK; q++) crate.im.setColorAt(CR0 + j * CSTACK + q, colour.set(q % 2 ? '#b08a52' : '#c49a5c')); }); lamp.im.instanceColor.needsUpdate = true; crate.im.instanceColor.needsUpdate = true; dress(); } }
      if (reduced) frame(0.016);
    },
    move(m) { mvT = { fwd: (m && m.fwd) || 0, side: (m && m.side) || 0 }; if (mode !== 'walk' && (mvT.fwd || mvT.side)) api.follow(null); },
    step(dt) { const p = walk({ x: cam.x, z: cam.z }, cam.yaw, mvT, dt || 0.1, COLL); cam.x = p.x; cam.z = p.z; snapCam(); frame(0.001); },
    look(dx, dy) { yawT -= dx; pitchT = Math.max(-0.6, Math.min(0.5, pitchT - dy)); still(); },
    follow(id) { following = id || null; mode = following ? 'follow' : 'walk'; still(); },
    tour(on) { mode = on ? 'tour' : 'walk'; following = null; if (on) tourT = 0; still(); return mode === 'tour'; },
    /** the day replay lights up who was busy at the cursor: their lamps pulse and their figures work for a moment */
    /** the person you are chatting with ('w:<station id>' | 'b:<builder id>' | null): it turns to face you, talks, and a soft marble disc marks it */
    focus(key) { focusKey = key || ''; still(); },
    focused() { return focusKey; },
    facing(key) { const si = S.findIndex((x) => 'w:' + x.id === key), ci = camp.findIndex((b) => b && 'b:' + b.id === key); return si >= 0 ? thA[si] : ci >= 0 ? thA[N + ci] : null; },
    pulse(ids) { for (const id of ids || []) hot[id] = t + 1.6; still(); },
    teleport(x, z, yaw) { const q = resolveCollision(x, z, []); cam.x = q.x; cam.z = q.z; if (yaw != null) { cam.yaw = yaw; yawT = yaw; } following = null; mode = 'walk'; mv = { fwd: 0, side: 0 }; snapCam(); still(); },
    reset() { cam = { x: START.x, z: START.z, yaw: START.yaw, pitch: -0.06 }; yawT = cam.yaw; pitchT = cam.pitch; following = null; mode = 'walk'; mv = { fwd: 0, side: 0 }; mvT = { fwd: 0, side: 0 }; snapCam(); still(); },
    face(id) { const s = S.find((a) => a.id === id); if (s) { let y = Math.atan2(-(s.x - cam.x), -(s.z - cam.z)); while (y - cam.yaw > Math.PI) y -= Math.PI * 2; while (y - cam.yaw < -Math.PI) y += Math.PI * 2; yawT = y; pitchT = -0.16; still(); } },
    pos,
    stats() { const st = rc.stats(); return { calls: st.calls, triangles: st.triangles, quality: st.quality, batches: batches.length }; },
    projectCamp(j) { const c = CAMP_SPOTS[j]; if (!c) return null; const v = new THREE.Vector3(c.x, 1.3, c.z - 1.2).project(camera); if (v.z > 1) return null; return { x: (v.x * 0.5 + 0.5) * canvas.clientWidth, y: (-v.y * 0.5 + 0.5) * canvas.clientHeight }; },
    project(id) { const s = S.find((a) => a.id === id); if (!s) return null; const v = new THREE.Vector3(s.x, 1.0, s.z).project(camera); if (v.z > 1) return null; return { x: (v.x * 0.5 + 0.5) * canvas.clientWidth, y: (-v.y * 0.5 + 0.5) * canvas.clientHeight }; },
    projectCrate(id, c) { const i = S.findIndex((a) => a.id === id), k = (i * MAXC + c) * 3; if (i < 0 || cratePos[k + 1] < 0) return null; const v = new THREE.Vector3(cratePos[k], cratePos[k + 1], cratePos[k + 2]).project(camera); if (v.z > 1) return null; return { x: (v.x * 0.5 + 0.5) * canvas.clientWidth, y: (-v.y * 0.5 + 0.5) * canvas.clientHeight }; },
    /** what is under a tap: { id, crate } for a crate, { id } for a worker, or 'board' / 'changed' / 'pipe' for a wall board */
    pick(cx, cy) {
      const r = canvas.getBoundingClientRect(), v = new THREE.Vector2(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1), lx = cx - r.left, ly = cy - r.top;
      ray.setFromCamera(v, camera);
      let best = null, bd = 26;                    // a crate first: the nearest one on screen within 26 px
      for (let i = 0; i < N; i++) for (let c = 0; c < nCrates(workers[i]); c++) { const p = api.projectCrate(S[i].id, c); if (p) { const d = Math.hypot(p.x - lx, p.y - ly); if (d < bd) { bd = d; best = { id: S[i].id, crate: c }; } } }
      if (best) return best;
      const hp = ray.intersectObject(sCyl.im, false)[0], pi = hp ? platIdx.indexOf(hp.instanceId) : -1;
      if (pi >= 0) return { id: S[pi].id };
      bd = 56;                                      // forgiving: the nearest station on screen within 56 px (figure or lamp)
      S.forEach((s) => { const p = api.project(s.id); if (p) { const d = Math.hypot(p.x - lx, p.y - ly); if (d < bd) { bd = d; best = { id: s.id }; } } });
      if (best) return best;
      bd = 64; CAMP_SPOTS.forEach((c, j) => { if (!camp[j]) return; const v3 = new THREE.Vector3(c.x, 1.3, c.z - 1.2).project(camera); if (v3.z > 1) return; const d = Math.hypot((v3.x * 0.5 + 0.5) * canvas.clientWidth - lx, (-v3.y * 0.5 + 0.5) * canvas.clientHeight - ly); if (d < bd) { bd = d; best = { id: 'camp:' + camp[j].id }; } });
      if (best) return best;
      if (ray.intersectObject(bLearn.m, false)[0]) return { id: 'board' };
      if (ray.intersectObject(bFlip.m, false)[0]) return { id: 'changed' };
      if (ray.intersectObject(bPipe.m, false)[0]) return { id: 'pipe' };
      return null;
    },
    dispose() { try { rc.stop(); rc.dispose(); A.t.dispose(); T.t.dispose(); CA.t.dispose(); [bLearn, bFlip, bPipe].forEach((b) => b.C.t.dispose()); } catch (_) { /* nothing */ } },
  };
  // drag to look; a short tap with no drag picks a crate, a station or a board
  let drag = null;
  const down = (e) => { drag = { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (!drag) return; if (mode === 'walk') api.look((e.clientX - drag.x) * 0.0055, (e.clientY - drag.y) * 0.0045); drag.x = e.clientX; drag.y = e.clientY; };
  const up = (e) => {
    if (drag && Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 8 && typeof o.onPick === 'function') { const hit = api.pick(e.clientX, e.clientY); if (hit) o.onPick(hit.id, hit.crate); }
    drag = null;
  };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', () => { drag = null; });
  // FX HOOK (olympus/fx-cine.js, optional; 2026-11-11 effects pass): the clock's light, sun shafts and dust in the halls, the camp hearth's
  // embers + smoke + firelight, sand blowing over the camp, birds over the desert, sparks off a WORKING smith's anvil. Same floor without it.
  let cine = null, cineOff = false, sparkAt = 2, sparkJ = 0;
  if (o.cinema !== false) import('../olympus/fx-cine.js').then((C) => { if (cineOff) return; cine = C.cinema(rc, { time: 'clock', fog: 0.3,
    rays: { to: [0, 0, 0], spread: [22, 0, 16], length: 16, width: 2 }, dust: { box: [24, 4, 18], center: [0, 2, 0] },
    fires: [[CAMP.fire.x, 0.7, CAMP.fire.z]], fireRange: 7, sand: { box: [26, 2, 14], center: [CAMP.fire.x, 0.4, 17], vel: [3.2, 0.1, 0.8], count: 260 },
    birds: { center: [CAMP.fire.x, 0, 18], radius: 14, height: 12, count: 10 }, blobs: [[CAMP.fire.x, CAMP.fire.z, 0.9]] });
    rc.onFrame((dt, t) => { if (!cine || reduced || t < sparkAt) return; sparkAt = t + 0.9 + Math.random() * 0.9;
      for (let n = 0; n < CAMP_SPOTS.length; n++) { const j = (sparkJ++) % CAMP_SPOTS.length, c = CAMP_SPOTS[j], b = camp[j];
        if (c.job === 'smith' && b && b.status === 'working') { cine.burst('sparks', [c.x, 0.85, c.z - 2.45], { count: 12 }); break; } } }); }).catch(() => {});
  api.cine = () => cine;
  const dispose0 = api.dispose; api.dispose = () => { cineOff = true; if (cine) cine.dispose(); dispose0(); };
  snapCam();
  rc.start((dt) => { frame(Math.min(dt, 0.1)); });
  if (reduced) frame(0.016);
  return api;
}
