// ERGASTERION floor (ES module): the marble-and-bronze agent factory you walk in first person. Four halls (Money, Trading, Research, Library) around a cross of inner walls with a
// door in each; one platform per worker with a marble figure DOING ITS JOB (turning the search wheel, writing at a desk, reading the tripod, hammering at the anvil, weighing on the
// scales), a status lamp, a speech bubble with its latest finding, and a conveyor carrying its last outputs as labelled crates you can tap. The Learning board and "what changed our
// mind" hang in the Library, the research pipeline wall in the Research hall. Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm light, bloom <= .2.
// LIGHT BY DESIGN: every repeated part lives in one of ten instanced batches (unit box / cylinder / sphere, coloured per instance), all 15 bubbles are ONE mesh on one canvas atlas,
// all crate tags and hall signs are ONE mesh on a second atlas, plus three wall boards: about 15 draw calls and under 40k triangles for the whole factory.
// createFloor(canvas, { reduced, stations, onPick }) -> { ok, set(workers, extra), move({fwd,side}), look(dx,dy), follow(id|null), tour(on), pulse(ids), reset(), teleport(x,z),
//   face(id), pos(), project(id), pick(x,y), stats(), dispose() }
// If WebGL, the render core or the tier (LITE / off) says no, ok is false and the page keeps its flat plan. Reduced motion: everything stands still and the camera jumps instead of gliding.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { walk, followCam, tourCam, ease, hallOf, EYE, BOUNDS, START, HALLS, DOORS } from './ergasterioncore.js';

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
    scene.fog = new THREE.Fog('#2a2118', 22, 60);
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
  const fig = batch(robeG, stone, true), head = batch(ballG, stone, true), dBox = batch(boxG, metal, true), dCyl = batch(cylG, metal, true);   // moving: the figures and their tools
  const lamp = batch(ballG, new THREE.MeshBasicMaterial({ color: '#ffffff' }), true), crate = batch(boxG, std(0.7, 0.05), true);

  // ---- the building: floor, four rugs (one tone per hall), outer walls, the cross of inner walls with a bronze door frame in each, columns along the outer walls
  sBox.add(0, -0.1, 0, 26.8, 0.2, 20.8, '#bdb29d');
  for (const h of HALLS) sBox.add((h.x0 + h.x1) / 2, 0.012, (h.z0 + h.z1) / 2, 11.2, 0.03, 8.2, RUG[h.id]);
  const WALL = '#a99f8d', WH = 3.4, IH = 3.0;
  sBox.add(0, WH / 2, -10.2, 26.8, WH, 0.4, WALL); sBox.add(0, WH / 2, 10.2, 26.8, WH, 0.4, WALL); sBox.add(-13.2, WH / 2, 0, 0.4, WH, 20.8, WALL); sBox.add(13.2, WH / 2, 0, 0.4, WH, 20.8, WALL);
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
  bBox.add(0, 0.02, -9.95, 26.4, 0.1, 0.16, BRONZE); bBox.add(0, 0.02, 9.95, 26.4, 0.1, 0.16, BRONZE); bBox.add(-12.95, 0.02, 0, 0.16, 0.1, 20, BRONZE); bBox.add(12.95, 0.02, 0, 0.16, 0.1, 20, BRONZE);
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
    if (s.job === 'scribe') { sBox.add(px, Y0 + 0.62, pz, 0.95, 0.06, 0.5, MARBLE); bBox.add(px - 0.4, Y0 + 0.3, pz, 0.06, 0.6, 0.42, BRONZE); bBox.add(px + 0.4, Y0 + 0.3, pz, 0.06, 0.6, 0.42, BRONZE); sBox.add(px - 0.05, Y0 + 0.665, pz, 0.5, 0.025, 0.32, '#efe6d2'); }
    else if (s.job === 'oracle') { for (let k = 0; k < 3; k++) { const a = k * 2.094 + 0.5; bCyl.add(px + Math.sin(a) * 0.17, Y0 + 0.42, pz + Math.cos(a) * 0.17, 0.022, 0.9, 0.022, BRONZE, Math.cos(a) * 0.36, 0, -Math.sin(a) * 0.36); } bCyl.add(px, Y0 + 0.88, pz, 0.27, 0.1, 0.27, GOLD); }
    else if (s.job === 'smith') { sBox.add(px, Y0 + 0.3, pz, 0.34, 0.6, 0.3, MARBLE); bBox.add(px, Y0 + 0.69, pz, 0.6, 0.18, 0.26, '#7a5631'); }
    else if (s.job === 'scales') { bCyl.add(px, Y0 + 0.55, pz, 0.03, 1.1, 0.03, BRONZE); bCyl.add(px, Y0 + 0.03, pz, 0.2, 0.06, 0.2, BRONZE); }
    else { bBox.add(px + 0.62, Y0 + 0.36, pz - 0.04, 0.08, 0.72, 0.08, BRONZE); bBox.add(px + 0.62, Y0 + 0.03, pz - 0.04, 0.5, 0.06, 0.34, BRONZE); }
  });
  // moving parts: fixed slots per station so nothing is allocated while drawing
  S.forEach(() => { fig.add(0, -9, 0, 1, 1, 1, MARBLE); fig.add(0, -9, 0, 1, 1, 1, MARBLE); fig.add(0, -9, 0, 1, 1, 1, MARBLE); head.add(0, -9, 0, 1, 1, 1, MARBLE); lamp.add(0, -9, 0, 1, 1, 1, LAMP.stale);
    for (let k = 0; k < 3; k++) { dBox.add(0, -9, 0, 1, 1, 1, k === 2 ? GOLD : BRONZE); dCyl.add(0, -9, 0, 1, 1, 1, BRONZE); }
    for (let k = 0; k < MAXC; k++) crate.add(0, -9, 0, 1, 1, 1, '#b08a52'); });
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
  const ray = new THREE.Raycaster(), ang = S.map((_, i) => i * 1.7), hot = {}, cratePos = new Float32Array(N * MAXC * 3);
  const pos = () => ({ x: cam.x, z: cam.z, yaw: cam.yaw, following, mode, hall: hallOf(mode === 'tour' ? { x: camera.position.x, z: camera.position.z } : cam).id });
  const nCrates = (w) => Math.max(0, Math.min(MAXC, w && w.crates ? w.crates.length : 0));
  // an arm: a cylinder from the shoulder, swung forward by `a` radians (0 = hanging down, 1.57 = straight ahead) and outward by `out`; returns the hand position
  const hand = { x: 0, y: 0, z: 0 };
  function arm(slot, sx, sy, sz, a, out) {
    const L = 0.5, dx = Math.sin(out), dy = -Math.cos(a) * Math.cos(out), dz = Math.sin(a) * Math.cos(out);
    put(fig.im, slot, sx + dx * L / 2, sy + dy * L / 2, sz + dz * L / 2, 0.06, L, 0.06, -a, 0, out);
    hand.x = sx + dx * L; hand.y = sy + dy * L; hand.z = sz + dz * L;
  }
  function frame(dt) {
    t += dt;
    const camP = camera.position;
    S.forEach((s, i) => {
      const w = workers[i], st = w ? w.status : 'stale', isHot = (hot[s.id] || 0) > t, k = Math.max(PACE[st] || 0, isHot ? 1 : 0) * mot;
      ang[i] += dt * k;
      const a = ang[i], f = figAt[i], bob = 0.012 * Math.sin(a * 2.1) * (k ? 1 : 0), bow = st === 'failed' ? 0.07 : 0, px = s.x, pz = s.z + 0.5, b3 = i * 3;
      put(fig.im, b3, f.x, Y0 + 0.5 + bob, f.z, 0.24, 1.0, 0.24);
      put(head.im, i, f.x, Y0 + 1.19 + bob - bow, f.z + (s.job === 'scribe' ? 0.05 : 0) + bow, 0.165, 0.175, 0.165);
      const shY = Y0 + 0.93 + bob, hide = (im, j) => put(im, j, 0, -9, 0, 0.001, 0.001, 0.001);
      if (s.job === 'wheel') {
        const sp = a * 2.2, wy = Y0 + 0.8, wx = px + 0.62, wz = pz + 0.06;
        put(dCyl.im, b3, wx, wy, wz, 0.36, 0.05, 0.36, Math.PI / 2, sp, 0);
        put(dBox.im, b3, wx, wy, wz + 0.035, 0.7, 0.05, 0.03, 0, 0, sp); put(dBox.im, b3 + 1, wx, wy, wz + 0.035, 0.7, 0.05, 0.03, 0, 0, sp + Math.PI / 2);
        put(dBox.im, b3 + 2, wx + Math.cos(sp) * 0.3, wy + Math.sin(sp) * 0.3, wz + 0.09, 0.07, 0.07, 0.12);
        arm(b3 + 1, f.x + 0.25, shY, f.z + 0.04, 1.0 + Math.sin(sp) * 0.3, 0.5 + Math.cos(sp) * 0.2); arm(b3 + 2, f.x - 0.25, shY, f.z + 0.04, 0.35, -0.1);
        hide(dCyl.im, b3 + 1); hide(dCyl.im, b3 + 2);
      } else if (s.job === 'scribe') {
        const wr = Math.sin(a * 5) * 0.16, dip = Math.sin(a * 10) * 0.03;
        arm(b3 + 1, f.x + 0.25, shY, f.z + 0.04, 1.0 + dip, -0.22 + wr); put(dCyl.im, b3, hand.x, hand.y + 0.05, hand.z + 0.02, 0.012, 0.24, 0.012, -0.5, 0, 0.3);
        arm(b3 + 2, f.x - 0.25, shY, f.z + 0.04, 0.95, 0.2);
        hide(dCyl.im, b3 + 1); hide(dCyl.im, b3 + 2); hide(dBox.im, b3); hide(dBox.im, b3 + 1); hide(dBox.im, b3 + 2);
      } else if (s.job === 'oracle') {
        const sw = Math.sin(a * 1.4) * 0.22;
        arm(b3 + 1, f.x + 0.25, shY, f.z + 0.04, 2.15 + sw, 0.45); arm(b3 + 2, f.x - 0.25, shY, f.z + 0.04, 2.15 - sw, -0.45);
        const fl = 0.07 + 0.025 * Math.sin(a * 6) * (k ? 1 : 0);
        if (st === 'failed' || st === 'stale') hide(dBox.im, b3 + 2); else put(dBox.im, b3 + 2, px, Y0 + 1.0 + fl, pz, fl, fl * 1.6, fl, 0, a * 1.5, 0.78);
        hide(dBox.im, b3); hide(dBox.im, b3 + 1); hide(dCyl.im, b3); hide(dCyl.im, b3 + 1); hide(dCyl.im, b3 + 2);
      } else if (s.job === 'smith') {
        const c = Math.cos(a * 4), up = 1.45 + 0.55 * Math.max(-1, Math.min(1, c * 1.6));        // a quick blow, a slower lift
        arm(b3 + 1, f.x + 0.25, shY, f.z + 0.04, up, 0.05);
        const ha = Math.PI - (up + 1.2), hdy = Math.cos(ha), hdz = Math.sin(ha);                    // the hammer carries on past the hand, bent forward of the forearm
        put(dCyl.im, b3, hand.x, hand.y + hdy * 0.18, hand.z + hdz * 0.18, 0.02, 0.38, 0.02, ha, 0, 0);
        put(dBox.im, b3, hand.x, hand.y + hdy * 0.36, hand.z + hdz * 0.36, 0.2, 0.11, 0.11, ha, 0, 0);
        arm(b3 + 2, f.x - 0.25, shY, f.z + 0.04, 0.85, 0.12);
        put(dBox.im, b3 + 2, px - 0.12, Y0 + 0.8, pz, 0.22, 0.03, 0.08);                                 // the gold piece on the anvil
        hide(dBox.im, b3 + 1); hide(dCyl.im, b3 + 1); hide(dCyl.im, b3 + 2);
      } else {
        const tilt = Math.sin(a * 1.3) * 0.2 * (k ? 1 : 0) + (st === 'failed' ? 0.26 : 0), ty = Y0 + 1.1, c = Math.cos(tilt), sn = Math.sin(tilt);
        put(dBox.im, b3, px, ty, pz, 0.92, 0.035, 0.045, 0, 0, tilt);
        put(dCyl.im, b3, px - 0.45 * c, ty - 0.45 * sn - 0.24, pz, 0.15, 0.025, 0.15); put(dCyl.im, b3 + 1, px + 0.45 * c, ty + 0.45 * sn - 0.24, pz, 0.15, 0.025, 0.15);
        put(dBox.im, b3 + 1, px - 0.45 * c, ty - 0.45 * sn - 0.12, pz, 0.012, 0.24, 0.012); put(dBox.im, b3 + 2, px + 0.45 * c, ty + 0.45 * sn - 0.12, pz, 0.012, 0.24, 0.012);
        arm(b3 + 1, f.x + 0.25, shY, f.z + 0.04, 0.95 + sn * 0.5, 0.3); arm(b3 + 2, f.x - 0.25, shY, f.z + 0.04, 0.95 - sn * 0.5, -0.3);
        hide(dCyl.im, b3 + 2);
      }
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
      if (Math.abs(mv.fwd) > 0.004 || Math.abs(mv.side) > 0.004) { const p = walk({ x: cam.x, z: cam.z }, cam.yaw, mv, dt, S); cam.x = p.x; cam.z = p.z; }
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
      if (extra) { drawLearn(extra.board || null); drawFlip(extra.board || null); drawPipe(extra.pipe || null); }
      if (reduced) frame(0.016);
    },
    move(m) { mvT = { fwd: (m && m.fwd) || 0, side: (m && m.side) || 0 }; if (mode !== 'walk' && (mvT.fwd || mvT.side)) api.follow(null); },
    step(dt) { const p = walk({ x: cam.x, z: cam.z }, cam.yaw, mvT, dt || 0.1, S); cam.x = p.x; cam.z = p.z; snapCam(); frame(0.001); },
    look(dx, dy) { yawT -= dx; pitchT = Math.max(-0.6, Math.min(0.5, pitchT - dy)); still(); },
    follow(id) { following = id || null; mode = following ? 'follow' : 'walk'; still(); },
    tour(on) { mode = on ? 'tour' : 'walk'; following = null; if (on) tourT = 0; still(); return mode === 'tour'; },
    /** the day replay lights up who was busy at the cursor: their lamps pulse and their figures work for a moment */
    pulse(ids) { for (const id of ids || []) hot[id] = t + 1.6; still(); },
    teleport(x, z) { cam.x = Math.max(-BOUNDS.x, Math.min(BOUNDS.x, x)); cam.z = Math.max(-BOUNDS.z, Math.min(BOUNDS.z, z)); following = null; mode = 'walk'; mv = { fwd: 0, side: 0 }; snapCam(); still(); },
    reset() { cam = { x: START.x, z: START.z, yaw: START.yaw, pitch: -0.06 }; yawT = cam.yaw; pitchT = cam.pitch; following = null; mode = 'walk'; mv = { fwd: 0, side: 0 }; mvT = { fwd: 0, side: 0 }; snapCam(); still(); },
    face(id) { const s = S.find((a) => a.id === id); if (s) { let y = Math.atan2(-(s.x - cam.x), -(s.z - cam.z)); while (y - cam.yaw > Math.PI) y -= Math.PI * 2; while (y - cam.yaw < -Math.PI) y += Math.PI * 2; yawT = y; pitchT = -0.16; still(); } },
    pos,
    stats() { const st = rc.stats(); return { calls: st.calls, triangles: st.triangles, quality: st.quality, batches: batches.length }; },
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
      if (ray.intersectObject(bLearn.m, false)[0]) return { id: 'board' };
      if (ray.intersectObject(bFlip.m, false)[0]) return { id: 'changed' };
      if (ray.intersectObject(bPipe.m, false)[0]) return { id: 'pipe' };
      return null;
    },
    dispose() { try { rc.stop(); rc.dispose(); A.t.dispose(); T.t.dispose(); [bLearn, bFlip, bPipe].forEach((b) => b.C.t.dispose()); } catch (_) { /* nothing */ } },
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
  snapCam();
  rc.start((dt) => { frame(Math.min(dt, 0.1)); });
  if (reduced) frame(0.016);
  return api;
}
