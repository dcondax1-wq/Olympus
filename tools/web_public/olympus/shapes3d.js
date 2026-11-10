// AGORA 3D shapes (tools/web_public/olympus/shapes3d.js, 2026-11-10): one shared library of classical-Greek geometry for every OLYMPUS app.
// ES module, three r160 only (../jarvis/three.module.min.js). It builds plain THREE.Group objects, so any scene can use them with the render
// core (olympus/render.js createRenderer) exactly like any other mesh. No document / window / network: it also runs in node (tests).
//
//   import { build, SHAPES, materials, stats } from '../olympus/shapes3d.js';
//   import * as KIT from '../olympus/materials.js';                      // optional: veined marble + brushed metal on HD
//   const M = materials({ lite: false, kit: KIT });                      // share ONE material set between shapes (build() makes its own if you omit it)
//   const owl = build('owl', { lite: false, materials: M, size: 2 });    // size = the longest side after scaling (default: native, about 2 units)
//   scene.add(owl); rc.start((dt, t) => { if (owl.userData.update) owl.userData.update(t); });
//   dispose(owl);                                                        // frees geometries (and the materials build() made itself)
//
// 19 shapes (SHAPES[i] = { id, name, means, group, build }): doric, ionic, temple, amphora, laurel, owl, lyre, shield, helmet, trireme,
// lighthouse, obelisk, coinstack, scales, hourglass, sundial, brazier, scroll, pillarbar (a bar chart built from pillars: { values: [0..1] }).
//
// LOOK (docs/DESIGN_AGORA.md): marble, bronze, gold, olive, terracotta, warm and calm. Only warm colours (nothing cold or glowing); the only light-giving parts are
// fire and a lighthouse flame, and even those stay warm (orange, never above 1.6) so bloom <= .25 only ever touches fire and gold.
// PERF: every shape has an HD build and a low-poly LITE build ({ lite: true }): LITE <= BUDGET.lite.tris triangles and <= BUDGET.lite.draws draw calls,
// HD <= BUDGET.hd. Repeated parts (flutes of a colonnade, leaves, coins, oars, ticks) are THREE.InstancedMesh, one draw call per kind.
// Every shape stands on y = 0, centred on x / z, about 2 units tall (the temple and the ship are wider than tall), faces +z.

import * as THREE from '../jarvis/three.module.min.js';
export { THREE };

export const BUDGET = Object.freeze({ lite: { tris: 2400, draws: 26 }, hd: { tris: 32000, draws: 48 } });
const PI = Math.PI, TAU = Math.PI * 2;

// ------------------------------------------------------------------ materials
/** The warm AGORA material set. kit = the module olympus/materials.js (optional): HD marble gets procedural veins and metals get a brushed map. */
export function materials({ lite = false, kit = null } = {}) {
  const hd = !lite, list = [];
  const std = (c, rough, metal, extra) => { const m = new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: rough, metalness: metal || 0 }, extra)); list.push(m); return m; };
  const phys = (c, rough, metal, extra) => { const m = new THREE.MeshPhysicalMaterial(Object.assign({ color: c, roughness: rough, metalness: metal || 0 }, extra)); list.push(m); return m; };
  const own = (m) => { list.push(m); return m; };
  const M = {};
  M.marble = hd ? (kit && kit.marble ? own(kit.marble({ color: '#e9e3d5', vein: '#8d8272', gold: false, scale: 1.1 })) : phys('#e9e3d5', 0.34, 0, { clearcoat: 0.4, clearcoatRoughness: 0.2 })) : std('#d3cab6', 0.6);
  M.stone = hd ? phys('#b4ab98', 0.5, 0, { clearcoat: 0.15 }) : std('#a39a86', 0.75);
  M.bronze = hd ? (kit && kit.metal ? own(kit.metal({ kind: 'gold', color: '#b98147', roughness: 0.5, envMapIntensity: 2.4, clearcoat: 0.1 })) : phys('#b98147', 0.5, 1, { clearcoat: 0.1, envMapIntensity: 2.4 })) : std('#a8743c', 0.5, 0.45);
  M.gold = hd ? (kit && kit.metal ? own(kit.metal({ kind: 'gold', color: '#c8a24a', roughness: 0.32, envMapIntensity: 1.8 })) : phys('#c8a24a', 0.3, 1, { clearcoat: 0.4, envMapIntensity: 1.15 })) : std('#c8a24a', 0.4, 0.45);
  M.terra = hd ? phys('#a6573a', 0.62, 0, { clearcoat: 0.18, clearcoatRoughness: 0.5 }) : std('#b4552f', 0.7);
  M.bronze.side = THREE.DoubleSide; M.gold.side = THREE.DoubleSide;     // thin dishes, bowls and shells are seen from both sides
  M.ink = std('#2b2118', 0.7);                      // the dark of black-figure pottery, mortar lines and carved marks
  M.olive = std('#7f8a52', 0.7);
  M.wood = std('#7b5a3a', 0.72, 0, { side: THREE.DoubleSide });
  M.cloth = std('#e6d7b2', 0.85, 0, { side: THREE.DoubleSide });      // sails and parchment
  M.water = hd ? phys('#4b7a99', 0.22, 0, { clearcoat: 0.6 }) : std('#4b7a99', 0.45);
  M.glass = std('#d8e4e6', 0.12, 0, { transparent: true, opacity: 0.26, side: THREE.DoubleSide, depthWrite: false });
  M.sand = std('#d9b36a', 0.9);
  M.flame = own(new THREE.MeshBasicMaterial({ color: new THREE.Color('#ff9a3c').multiplyScalar(hd ? 1.5 : 1), side: THREE.DoubleSide }));
  M.flameCore = own(new THREE.MeshBasicMaterial({ color: new THREE.Color('#ffd78a').multiplyScalar(hd ? 1.6 : 1), side: THREE.DoubleSide }));
  M.coal = std('#4a2418', 0.9, 0, hd ? { emissive: new THREE.Color('#8a3410'), emissiveIntensity: 0.6 } : {});
  M.lite = lite;
  M.dispose = () => { list.forEach((m) => m.dispose()); list.length = 0; };
  return M;
}

// ------------------------------------------------------------------ small helpers
const seg = (c, hd, lo) => (c.lite ? lo : hd);
function mesh(g, geo, mat, x, y, z, rx, ry, rz) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(x || 0, y || 0, z || 0);
  if (rx || ry || rz) m.rotation.set(rx || 0, ry || 0, rz || 0);
  g.add(m);
  return m;
}
const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
const cyl = (rt, rb, h, s, open) => new THREE.CylinderGeometry(rt, rb, h, s, 1, !!open);
const sph = (r, ws, hs, sx, sy, sz) => { const g = new THREE.SphereGeometry(r, ws, hs); if (sx || sy || sz) g.scale(sx || 1, sy || 1, sz || 1); return g; };
const lathe = (pts, s) => new THREE.LatheGeometry(pts.map((p) => new THREE.Vector2(p[0], p[1])), s);
const torus = (R, r, rs, ts, arc) => new THREE.TorusGeometry(R, r, rs, ts, arc || TAU);
const _o = new THREE.Object3D(), _c = new THREE.Color();
/** an InstancedMesh from [{ p:[x,y,z], r:[rx,ry,rz], s: n | [sx,sy,sz], c: colour }] : one draw call for the lot */
function instanced(g, geo, mat, list) {
  const im = new THREE.InstancedMesh(geo, mat, list.length);
  list.forEach((e, i) => {
    _o.position.set(e.p[0], e.p[1], e.p[2]);
    _o.rotation.set(e.r ? e.r[0] : 0, e.r ? e.r[1] : 0, e.r ? e.r[2] : 0);
    if (Array.isArray(e.s)) _o.scale.set(e.s[0], e.s[1], e.s[2]); else _o.scale.setScalar(e.s == null ? 1 : e.s);
    _o.updateMatrix();
    im.setMatrixAt(i, _o.matrix);
    if (e.c) im.setColorAt(i, _c.set(e.c));
  });
  im.instanceMatrix.needsUpdate = true;
  if (im.instanceColor) im.instanceColor.needsUpdate = true;
  g.add(im);
  return im;
}
/** a column shaft with real flutes: a tapered cylinder whose side vertices are pulled in between the ridges */
function flutedShaft(rt, rb, h, flutes, depth, lite) {
  const per = lite ? 1 : 4, geo = new THREE.CylinderGeometry(rt, rb, h, flutes * per, lite ? 1 : 8, true);
  if (!lite) {
    const p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i), a = Math.atan2(x, z), k = Math.pow(0.5 + 0.5 * Math.cos(a * flutes), 2.2);   // 1 on a ridge, 0 in a groove
      const s = 1 - depth * (1 - k);
      p.setX(i, x * s); p.setZ(i, z * s);
    }
    geo.computeVertexNormals();
  }
  return geo;
}
function steps(g, M, n, w, d, h0, dh) {
  for (let i = 0; i < n; i++) mesh(g, box(w - i * 0.1, dh, d - i * 0.1), M.stone, 0, h0 + dh * (i + 0.5), 0);
  return h0 + dh * n;
}
let _seed = 1;
const rnd = () => { _seed = (_seed * 16807) % 2147483647; return (_seed - 1) / 2147483646; };     // deterministic: the same shape every build

// ------------------------------------------------------------------ the shapes
function doric(c) {
  const { g, M, lite } = c;
  let y = steps(g, M, 2, 1.0, 1.0, 0, 0.08);
  const h = 1.7;
  mesh(g, flutedShaft(0.2, 0.27, h, 20, 0.07, lite), M.marble, 0, y + h / 2, 0);
  y += h;
  mesh(g, cyl(0.3, 0.2, 0.1, seg(c, 32, 10)), M.marble, 0, y + 0.05, 0);
  if (!lite) mesh(g, torus(0.205, 0.012, 6, 28), M.stone, 0, y + 0.01, 0, PI / 2);
  y += 0.1;
  mesh(g, box(0.64, 0.1, 0.64), M.marble, 0, y + 0.05, 0);
  y += 0.1;
  mesh(g, box(0.7, 0.2, 0.7), M.marble, 0, y + 0.1, 0);
  if (!lite) for (let i = 0; i < 3; i++) mesh(g, box(0.07, 0.15, 0.02), M.ink, -0.2 + i * 0.2, y + 0.1, 0.355);   // three triglyph marks on the front
}
function ionic(c) {
  const { g, M, lite } = c, s = seg(c, 28, 10);
  let y = steps(g, M, 2, 0.95, 0.95, 0, 0.08);
  mesh(g, cyl(0.31, 0.34, 0.1, s), M.marble, 0, y + 0.05, 0);                // attic base: two tori around a hollow
  if (!lite) { mesh(g, torus(0.3, 0.045, 8, 32), M.marble, 0, y + 0.09, 0, PI / 2); mesh(g, torus(0.25, 0.03, 8, 32), M.marble, 0, y + 0.17, 0, PI / 2); }
  y += 0.2;
  const h = 1.6;
  mesh(g, flutedShaft(0.17, 0.22, h, 24, 0.1, lite), M.marble, 0, y + h / 2, 0);
  y += h;
  mesh(g, cyl(0.2, 0.17, 0.08, s), M.marble, 0, y + 0.04, 0);
  y += 0.08;
  mesh(g, box(0.66, 0.06, 0.34), M.marble, 0, y + 0.03, 0);                  // the bolster between the scrolls
  mesh(g, cyl(0.075, 0.075, 0.66, seg(c, 14, 6)), M.marble, 0, y + 0.09, 0, 0, 0, PI / 2);
  for (const sx of [-1, 1]) {
    mesh(g, cyl(0.15, 0.15, 0.36, seg(c, 28, 10)), M.marble, sx * 0.33, y + 0.09, 0, PI / 2);          // the volute disc
    if (!lite) { mesh(g, torus(0.095, 0.02, 6, 24), M.stone, sx * 0.33, y + 0.09, 0.185); mesh(g, torus(0.095, 0.02, 6, 24), M.stone, sx * 0.33, y + 0.09, -0.185); }
    mesh(g, sph(0.035, seg(c, 10, 5), seg(c, 8, 4)), M.gold, sx * 0.33, y + 0.09, 0.19);
    mesh(g, sph(0.035, seg(c, 10, 5), seg(c, 8, 4)), M.gold, sx * 0.33, y + 0.09, -0.19);
  }
  y += 0.2;
  mesh(g, box(0.78, 0.06, 0.4), M.marble, 0, y + 0.03, 0);
  mesh(g, box(0.8, 0.14, 0.42), M.marble, 0, y + 0.13, 0);
}
function temple(c) {
  const { g, M, lite } = c;
  let y = steps(g, M, 3, 2.7, 1.6, 0, 0.07);
  mesh(g, box(1.5, 0.78, 0.8), M.marble, 0, y + 0.39, 0);
  if (!lite) mesh(g, box(0.22, 0.46, 0.04), M.ink, 0, y + 0.23, 0.41);                 // the door
  const cols = [], caps = [], rowsX = lite ? [-1, -0.33, 0.33, 1] : [-1.0, -0.6, -0.2, 0.2, 0.6, 1.0];
  for (const x of rowsX) for (const z of [-0.62, 0.62]) cols.push({ p: [x, y + 0.4, z] });
  for (const z of lite ? [] : [-0.31, 0, 0.31]) for (const x of [-1.05, 1.05]) cols.push({ p: [x, y + 0.4, z] });
  const shaft = cyl(0.075, 0.1, 0.8, seg(c, 14, 6));
  instanced(g, shaft, M.marble, cols);
  cols.forEach((e) => caps.push({ p: [e.p[0], y + 0.83, e.p[2]] }));
  instanced(g, box(0.25, 0.06, 0.25), M.marble, caps);
  y += 0.86;
  mesh(g, box(2.4, 0.14, 1.44), M.marble, 0, y + 0.07, 0);                             // architrave
  y += 0.14;
  mesh(g, box(2.46, 0.14, 1.5), M.stone, 0, y + 0.07, 0);                              // frieze
  if (!lite) {
    const tri = [];
    for (let i = 0; i < 14; i++) { const x = -1.12 + i * 0.1723; tri.push({ p: [x, y + 0.07, 0.755] }, { p: [x, y + 0.07, -0.755] }); }
    instanced(g, box(0.07, 0.11, 0.02), M.ink, tri);
  }
  y += 0.14;
  const sh = new THREE.Shape([new THREE.Vector2(-1.25, 0), new THREE.Vector2(1.25, 0), new THREE.Vector2(0, 0.42)]);
  const roof = new THREE.ExtrudeGeometry(sh, { depth: 1.5, bevelEnabled: false });
  roof.translate(0, 0, -0.75);
  mesh(g, roof, M.marble, 0, y, 0);
  if (!lite) {
    mesh(g, box(1.46, 0.04, 1.62), M.terra, -0.61, y + 0.22, 0, 0, 0, 0.3);
    mesh(g, box(1.46, 0.04, 1.62), M.terra, 0.61, y + 0.22, 0, 0, 0, -0.3);
    mesh(g, cone(0.05, 0.14, 8), M.gold, 0, y + 0.47, 0);
  } else {
    mesh(g, box(1.3, 0.04, 1.58), M.terra, -0.6, y + 0.2, 0, 0, 0, 0.3);
    mesh(g, box(1.3, 0.04, 1.58), M.terra, 0.6, y + 0.2, 0, 0, 0, -0.3);
  }
}
function cone(r, h, s) { return new THREE.ConeGeometry(r, h, s); }
function amphora(c) {
  const { g, M, lite } = c, s = seg(c, 48, 14);
  const prof = [[0.001, 0], [0.13, 0], [0.15, 0.04], [0.11, 0.1], [0.2, 0.3], [0.34, 0.6], [0.42, 0.85], [0.4, 1.05], [0.3, 1.25], [0.17, 1.42], [0.14, 1.52], [0.17, 1.6], [0.23, 1.66], [0.2, 1.7], [0.13, 1.68]];
  mesh(g, lathe(prof, s), M.terra, 0, 0.05, 0);
  if (!lite) {
    const band = prof.filter((p) => p[1] >= 0.6 && p[1] <= 1.05).map((p) => [p[0] * 1.012, p[1]]);
    mesh(g, lathe(band, s), M.ink, 0, 0.05, 0);
    const meander = [];
    for (let i = 0; i < 18; i++) { const a = (i / 18) * TAU; meander.push({ p: [Math.sin(a) * 0.434, 0.05 + 0.82, Math.cos(a) * 0.434], r: [0, a, 0] }); }
    instanced(g, box(0.07, 0.05, 0.012), M.gold, meander);
  }
  for (const sx of [-1, 1]) {
    const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(sx * 0.15, 1.55, 0), new THREE.Vector3(sx * 0.36, 1.47, 0), new THREE.Vector3(sx * 0.44, 1.25, 0), new THREE.Vector3(sx * 0.38, 1.02, 0)]);
    mesh(g, new THREE.TubeGeometry(curve, seg(c, 18, 7), 0.036, seg(c, 8, 4), false), M.terra, 0, 0.05, 0);
  }
  mesh(g, cyl(0.2, 0.24, 0.05, seg(c, 24, 8)), M.stone, 0, 0.025, 0);                  // a little plinth
}
function laurel(c) {
  const { g, M, lite } = c, R = 0.78, cy = 1.0, n = lite ? 7 : 14;
  mesh(g, torus(R, 0.03, seg(c, 6, 3), seg(c, 64, 20)), M.gold, 0, cy, 0);
  const leaves = [], berries = [];
  for (const side of [-1, 1]) {
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1), th = -PI / 2 + side * (0.14 + t * (PI * 0.93)), pairs = lite ? [0] : [-1, 1];
      for (const k of pairs) {
        const rr = R + (lite ? 0 : k * 0.06), px = Math.cos(th) * rr, py = cy + Math.sin(th) * rr, tan = th + side * PI / 2;
        leaves.push({ p: [px, py, 0.012], r: [0, 0, tan + (lite ? 0 : k * 0.55 * side)], s: [0.25 - t * 0.04, 0.085, 0.06] });
      }
      if (!lite && i % 3 === 1) berries.push({ p: [Math.cos(th) * (R - 0.09), cy + Math.sin(th) * (R - 0.09), 0.02], s: 0.03 });
    }
  }
  instanced(g, sph(1, seg(c, 8, 4), seg(c, 6, 3)), M.olive, leaves);
  if (berries.length) instanced(g, sph(1, 8, 6), M.gold, berries);
  const tie = [{ p: [-0.09, cy - R - 0.12, 0.01], r: [0, 0, 0.4] }, { p: [0.09, cy - R - 0.12, 0.01], r: [0, 0, -0.4] }];
  instanced(g, box(0.07, 0.3, 0.012), M.terra, tie);
  mesh(g, sph(0.05, seg(c, 12, 6), seg(c, 8, 4)), M.terra, 0, cy - R - 0.01, 0.02);
  mesh(g, cyl(0.04, 0.05, cy - R - 0.1, seg(c, 10, 6)), M.bronze, 0, (cy - R - 0.1) / 2 + 0.05, 0);       // the stand
  mesh(g, cyl(0.34, 0.4, 0.07, seg(c, 32, 12)), M.stone, 0, 0.035, 0);
}
function owl(c) {
  const { g, M, lite } = c, s = seg(c, 28, 10), sh = seg(c, 20, 8);
  mesh(g, cyl(0.42, 0.48, 0.12, seg(c, 32, 12)), M.stone, 0, 0.06, 0);
  mesh(g, cyl(0.04, 0.04, 0.8, 8), M.wood, 0, 0.5, -0.02, 0, 0, PI / 2);                                // the perch
  mesh(g, cyl(0.04, 0.05, 0.4, 8), M.wood, -0.38, 0.32, -0.02);
  mesh(g, cyl(0.04, 0.05, 0.4, 8), M.wood, 0.38, 0.32, -0.02);
  mesh(g, sph(0.42, s, sh, 0.95, 1.4, 0.82), M.bronze, 0, 1.0, 0);                                      // body
  mesh(g, sph(0.34, s, sh, 1.18, 0.98, 0.95), M.bronze, 0, 1.58, 0.02);                                 // head
  for (const sx of [-1, 1]) {
    mesh(g, cone(0.07, 0.2, seg(c, 8, 4)), M.bronze, sx * 0.27, 1.9, 0.0, 0, 0, -sx * 0.25);           // ear tufts
    mesh(g, cyl(0.17, 0.17, 0.03, seg(c, 24, 10)), M.marble, sx * 0.18, 1.6, 0.31, PI / 2);             // the facial discs
    mesh(g, cyl(0.1, 0.1, 0.034, seg(c, 20, 8)), M.gold, sx * 0.18, 1.6, 0.318, PI / 2);
    mesh(g, sph(0.055, seg(c, 12, 6), seg(c, 10, 5)), M.ink, sx * 0.18, 1.6, 0.34);
    mesh(g, sph(0.28, sh, seg(c, 14, 6), 0.32, 1.0, 0.78), M.stone, sx * 0.44, 0.98, -0.04, 0, 0, sx * -0.14);         // folded wings
    mesh(g, box(0.07, 0.04, 0.12), M.gold, sx * 0.14, 0.58, 0.14);                                      // claws
    mesh(g, box(0.07, 0.04, 0.12), M.gold, sx * 0.14, 0.58, 0.14);
  }
  mesh(g, cone(0.06, 0.16, seg(c, 8, 4)), M.gold, 0, 1.52, 0.38, PI / 2);                                // beak
  if (!lite) {
    const f = [];
    for (let r = 0; r < 4; r++) for (let i = 0; i < 5 - (r % 2); i++) f.push({ p: [(i - (4 - (r % 2)) / 2) * 0.14, 1.28 - r * 0.15, 0.31 - r * 0.012], s: [0.07, 0.06, 0.03], c: r % 2 ? '#d8cdb6' : '#e9e3d5' });
    instanced(g, sph(1, 8, 6), M.marble, f);
  }
}
function lyre(c) {
  const { g, M, lite } = c;
  mesh(g, cyl(0.45, 0.52, 0.12, seg(c, 32, 12)), M.stone, 0, 0.06, 0);
  mesh(g, sph(0.4, seg(c, 28, 10), seg(c, 20, 8), 0.95, 1.0, 0.55), M.terra, 0, 0.62, 0);             // the sound box
  mesh(g, cyl(0.22, 0.28, 0.05, seg(c, 16, 8)), M.gold, 0, 0.9, 0.2, PI / 2);
  for (const sx of [-1, 1]) {
    const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(sx * 0.3, 0.75, 0), new THREE.Vector3(sx * 0.56, 1.05, 0), new THREE.Vector3(sx * 0.58, 1.45, 0), new THREE.Vector3(sx * 0.4, 1.78, 0)]);
    mesh(g, new THREE.TubeGeometry(curve, seg(c, 24, 8), 0.04, seg(c, 8, 4), false), M.bronze, 0, 0, 0);
    mesh(g, sph(0.065, seg(c, 12, 6), seg(c, 10, 5)), M.gold, sx * 0.4, 1.78, 0);
  }
  mesh(g, cyl(0.035, 0.035, 0.92, seg(c, 10, 6)), M.gold, 0, 1.68, 0, 0, 0, PI / 2);                    // the yoke
  mesh(g, box(0.7, 0.05, 0.07), M.bronze, 0, 0.9, 0.03);                                                // the bridge
  const n = lite ? 5 : 7, strings = [];
  for (let i = 0; i < n; i++) { const x = -0.32 + (0.64 * i) / (n - 1); strings.push({ p: [x, 1.29, 0.03], s: [1, 1, 1] }); }
  instanced(g, cyl(0.007, 0.007, 0.78, 4), M.gold, strings);
}
function shield(c) {
  const { g, M, lite } = c, s = seg(c, 56, 18);
  const dish = lathe([[0.001, 0.2], [0.25, 0.185], [0.5, 0.14], [0.72, 0.07], [0.86, 0]], s);
  const m = mesh(g, dish, M.bronze, 0, 1.12, 0, PI / 2 + 0.1);
  m.material = M.bronze; m.userData.dish = true;
  mesh(g, torus(0.86, 0.04, seg(c, 8, 4), seg(c, 64, 20)), M.gold, 0, 1.12, 0.0).rotation.x = 0.1;
  mesh(g, sph(0.13, seg(c, 20, 8), seg(c, 14, 6)), M.gold, 0, 1.12 - 0.045, 0.21);
  if (!lite) {
    const ring = mesh(g, torus(0.52, 0.018, 6, 56), M.gold, 0, 1.12 - 0.01, 0.12); ring.rotation.x = 0.1;
    const rays = [];
    for (let i = 0; i < 8; i++) { const a = (i / 8) * TAU; rays.push({ p: [Math.sin(a) * 0.32, 1.12 + Math.cos(a) * 0.32 * 0.995 - 0.03, 0.17], r: [0, 0, -a], s: 1 }); }
    instanced(g, cone(0.04, 0.22, 4), M.gold, rays);
  }
  mesh(g, cyl(0.05, 0.06, 0.34, seg(c, 12, 6)), M.bronze, 0, 0.27, -0.05);
  mesh(g, cyl(0.38, 0.44, 0.12, seg(c, 32, 12)), M.stone, 0, 0.06, -0.02);
}
function helmet(c) {
  const { g, M, lite } = c, s = seg(c, 32, 12);
  mesh(g, cyl(0.34, 0.42, 0.16, seg(c, 32, 12)), M.stone, 0, 0.08, 0);
  mesh(g, cyl(0.07, 0.1, 0.3, seg(c, 12, 6)), M.bronze, 0, 0.3, 0);
  mesh(g, new THREE.SphereGeometry(0.52, s, seg(c, 20, 8), 0, TAU, 0, PI * 0.58), M.bronze, 0, 1.1, 0).material = M.bronze;
  const cheek = (a, b) => new THREE.CylinderGeometry(0.5, 0.4, 0.62, seg(c, 14, 5), 1, true, a, b - a);
  mesh(g, cheek(0.38, 2.15), M.bronze, 0, 0.78, 0);
  mesh(g, cheek(-2.15, -0.38), M.bronze, 0, 0.78, 0);
  mesh(g, box(0.09, 0.5, 0.06), M.bronze, 0, 0.98, 0.5);                                                // the nasal bar
  mesh(g, torus(0.5, 0.025, 6, seg(c, 40, 14)), M.gold, 0, 1.1, 0, PI / 2);
  mesh(g, box(0.06, 0.05, 0.9), M.gold, 0, 1.64, 0);                                                    // the crest holder
  const n = lite ? 8 : 20, crest = [];
  for (let i = 0; i < n; i++) { const a = PI * 0.08 + (i / (n - 1)) * PI * 0.86, rr = 0.58 + Math.sin((i / (n - 1)) * PI) * 0.16; crest.push({ p: [0, 1.1 + Math.sin(a) * rr, Math.cos(a) * rr * 0.9], r: [a - PI / 2 + PI, 0, 0], s: 1 }); }
  instanced(g, box(0.08, lite ? 0.14 : 0.18, 0.05), M.terra, crest);
}
function trireme(c) {
  const { g, M, lite } = c;
  const water = mesh(g, cyl(1.65, 1.7, 0.15, seg(c, 40, 14)), M.water, 0, 0.375, 0);
  if (!lite) for (const r of [1.1, 1.35, 1.6]) mesh(g, torus(r, 0.012, 4, 64), M.marble, 0, 0.455, 0, PI / 2);
  const hull = new THREE.SphereGeometry(1, seg(c, 32, 12), seg(c, 12, 4), 0, TAU, PI / 2, PI / 2);
  hull.scale(1.25, 0.42, 0.42);
  const hm = mesh(g, hull, M.wood, 0, 0.6, 0);
  hm.material = M.wood;
  const deck = new THREE.CircleGeometry(1, seg(c, 32, 12)); deck.rotateX(-PI / 2); deck.scale(1.25, 1, 0.42);
  mesh(g, deck, M.stone, 0, 0.58, 0);
  mesh(g, cone(0.06, 0.36, seg(c, 10, 5)), M.bronze, 1.27, 0.5, 0, 0, 0, -PI / 2);                    // the ram
  mesh(g, torus(0.42, 0.045, 6, seg(c, 16, 6), PI / 2), M.terra, -0.85, 0.6, 0, 0, 0, PI / 2);   // the curved stern
  mesh(g, sph(0.065, seg(c, 10, 5), seg(c, 8, 4)), M.gold, -0.85, 1.02, 0);
  mesh(g, sph(0.05, seg(c, 10, 5), seg(c, 8, 4)), M.gold, 1.17, 0.7, 0.36);
  mesh(g, sph(0.05, seg(c, 10, 5), seg(c, 8, 4)), M.gold, 1.17, 0.7, -0.36);
  mesh(g, cyl(0.03, 0.04, 1.35, seg(c, 8, 5)), M.wood, 0.1, 1.2, 0);                                  // mast
  mesh(g, cyl(0.02, 0.02, 1.05, seg(c, 8, 5)), M.wood, 0.1, 1.75, 0, PI / 2);                         // yard
  const sail = mesh(g, new THREE.PlaneGeometry(0.86, 0.9, 1, 1), M.cloth, 0.1, 1.28, 0);
  sail.rotation.y = PI / 2;
  const oars = [], nO = lite ? 4 : 9;
  for (let i = 0; i < nO; i++) { const x = -0.85 + (1.7 * i) / (nO - 1); for (const sz of [-1, 1]) oars.push({ p: [x, 0.52, sz * 0.58], r: [sz * (PI / 2 - 0.6), 0, 0] }); }
  instanced(g, cyl(0.012, 0.012, 0.72, 5), M.wood, oars);
  g.children.forEach((ch) => { ch.position.y -= 0.3; });                                              // stand the sea on y = 0
  const t0 = g.children.map((ch) => ch.position.y);
  g.userData.update = (t) => { g.children.forEach((ch, i) => { if (ch !== water) ch.position.y = t0[i] + Math.sin(t * 0.9) * 0.015; }); };
}
function lighthouse(c) {
  const { g, M, lite } = c;
  mesh(g, cyl(1.05, 1.3, 0.28, seg(c, 9, 7)), M.stone, 0, 0.14, 0);
  if (!lite) for (let i = 0; i < 5; i++) mesh(g, sph(0.22, 8, 6, 1, 0.7, 1), M.stone, Math.cos(i * 1.25 + 0.4) * 1.1, 0.1, Math.sin(i * 1.25 + 0.4) * 1.1);
  const sq = cyl(0.36, 0.5, 0.82, 4); sq.rotateY(PI / 4);
  mesh(g, sq, M.marble, 0, 0.28 + 0.41, 0);
  mesh(g, cyl(0.28, 0.33, 0.6, seg(c, 8, 8)), M.marble, 0, 1.1 + 0.3, 0, 0, PI / 8, 0);
  mesh(g, cyl(0.19, 0.26, 0.4, seg(c, 20, 10)), M.marble, 0, 1.7 + 0.2, 0);
  mesh(g, cyl(0.34, 0.3, 0.06, seg(c, 24, 10)), M.gold, 0, 2.12, 0);
  mesh(g, cyl(0.15, 0.15, 0.3, seg(c, 14, 8), true), M.glass, 0, 2.3, 0);
  mesh(g, sph(0.1, seg(c, 14, 6), seg(c, 10, 5), 1, 1.3, 1), M.flame, 0, 2.3, 0);
  mesh(g, cone(0.22, 0.24, seg(c, 14, 8)), M.bronze, 0, 2.57, 0);
  mesh(g, sph(0.04, 8, 6), M.gold, 0, 2.72, 0);
  mesh(g, box(0.16, 0.26, 0.02), M.ink, 0, 0.28 + 0.13, 0.43);
  if (!lite) {
    const w = [];
    for (let i = 0; i < 4; i++) w.push({ p: [Math.sin(i * PI / 2 + PI / 4) * 0.0, 1.0, 0], s: 0 });
    const win = [];
    for (let i = 0; i < 8; i++) { const a = (i / 8) * TAU + PI / 8; win.push({ p: [Math.sin(a) * 0.3, 1.4, Math.cos(a) * 0.3], r: [0, a, 0] }); }
    instanced(g, box(0.06, 0.16, 0.03), M.ink, win);
  }
  g.userData.update = (t) => { M.flame.color.setScalar(1); M.flame.color.set('#ff9a3c').multiplyScalar((M.lite ? 1 : 1.5) * (0.97 + 0.03 * Math.sin(t * 1.3))); };
}
function obelisk(c) {
  const { g, M, lite } = c;
  let y = steps(g, M, 2, 1.0, 1.0, 0, 0.1);
  const h = 1.7, shaft = cyl(0.12, 0.22, h, 4); shaft.rotateY(PI / 4);
  mesh(g, shaft, M.marble, 0, y + h / 2, 0);
  const tip = cone(0.12, 0.28, 4); tip.rotateY(PI / 4);
  mesh(g, tip, M.gold, 0, y + h + 0.14, 0);
  if (!lite) {
    const marks = [];
    for (let f = 0; f < 4; f++) {
      const a = f * PI / 2, nx = Math.sin(a), nz = Math.cos(a);
      for (let col = -1; col <= 1; col++) for (let r = 0; r < 6; r++) {
        const u = 0.12 + r * 0.12, apo = (0.22 + (0.12 - 0.22) * u) / Math.SQRT2 + 0.003, wid = apo * 0.5;
        marks.push({ p: [nx * apo + nz * col * wid * 0.5, y + u * h, nz * apo - nx * col * wid * 0.5], r: [0, a, 0], s: [1, 0.7 + 0.3 * ((r + col + 3) % 3), 1] });
      }
    }
    instanced(g, box(0.034, 0.07, 0.012), M.ink, marks);
    mesh(g, torus(0.19, 0.012, 6, 4), M.gold, 0, y + 0.02, 0, PI / 2, 0, PI / 4);
  }
}
function coinstack(c) {
  const { g, M, lite } = c, s = seg(c, 32, 10);
  mesh(g, cyl(0.8, 0.85, 0.1, seg(c, 40, 14)), M.stone, 0, 0.05, 0);
  const coinGeo = lite ? cyl(0.3, 0.3, 0.06, s) : lathe([[0.001, 0], [0.3, 0], [0.3, 0.062], [0.255, 0.062], [0.245, 0.05], [0.001, 0.05]], s);
  const coins = [], stacks = [[-0.42, 0.1, lite ? 6 : 9], [0.36, 0.32, lite ? 4 : 6], [-0.05, -0.5, lite ? 2 : 3]];
  _seed = 7;
  for (const [x, z, n] of stacks) for (let i = 0; i < n; i++) coins.push({ p: [x + (rnd() - 0.5) * 0.025, 0.1 + i * 0.062, z + (rnd() - 0.5) * 0.025], r: [0, rnd() * PI, 0] });
  instanced(g, coinGeo, M.gold, coins);
  const lean = mesh(g, coinGeo, M.gold, 0.1, 0.34, 0.16, PI / 2, 0, 0);
  lean.rotation.set(PI / 2 - 0.0, 0, 0); lean.position.set(0.2, 0.4, 0.46); lean.rotation.x = PI / 2; lean.rotation.y = 0.2;
}
function scales(c) {
  const { g, M, lite } = c, tilt = c.o.tilt == null ? 0.12 : c.o.tilt;
  mesh(g, cyl(0.4, 0.5, 0.14, seg(c, 32, 12)), M.stone, 0, 0.07, 0);
  mesh(g, cyl(0.07, 0.11, 1.5, seg(c, 14, 8)), M.bronze, 0, 0.9, 0);
  mesh(g, sph(0.1, seg(c, 14, 6), seg(c, 10, 5)), M.gold, 0, 1.68, 0);
  const beam = new THREE.Group(); beam.position.y = 1.68; g.add(beam);
  beam.add(new THREE.Mesh(box(1.74, 0.06, 0.06), M.bronze));
  const parts = [];
  for (const sx of [-1, 1]) {
    const hang = new THREE.Group(); hang.position.set(sx * 0.82, 0, 0); beam.add(hang); parts.push(hang);
    hang.add(Object.assign(new THREE.Mesh(sph(0.045, seg(c, 10, 5), seg(c, 8, 4)), M.gold)));
    for (let k = 0; k < 3; k++) {
      const a = (k / 3) * TAU, ch = new THREE.Mesh(cyl(0.008, 0.008, 0.62, 4), M.gold);
      ch.position.set(Math.sin(a) * 0.13, -0.31, Math.cos(a) * 0.13); ch.rotation.set(-Math.cos(a) * 0.2, 0, Math.sin(a) * 0.2); hang.add(ch);
    }
    const pan = new THREE.Mesh(lathe([[0.001, 0], [0.18, 0.01], [0.33, 0.07], [0.35, 0.09], [0.33, 0.09], [0.16, 0.03], [0.001, 0.03]], seg(c, 28, 10)), M.gold);
    pan.position.y = -0.64; pan.material = M.gold; hang.add(pan);
  }
  const load = new THREE.Group(); parts[0].add(load); load.position.y = -0.58;                          // a few coins on the left pan
  for (let i = 0; i < (lite ? 2 : 4); i++) { const cn = new THREE.Mesh(cyl(0.11, 0.11, 0.04, seg(c, 14, 8)), M.gold); cn.position.set((i % 2) * 0.08 - 0.04, i * 0.042, 0); load.add(cn); }
  const grain = new THREE.Mesh(sph(0.09, seg(c, 12, 6), seg(c, 10, 5)), M.olive); grain.position.y = 0.09; parts[1].add(grain); grain.position.y = -0.52;
  const set = (a) => { beam.rotation.z = a; parts.forEach((p) => { p.rotation.z = -a; }); };
  set(tilt);
  g.userData.update = (t) => set(tilt + Math.sin(t * 0.8) * 0.04);
}
function hourglass(c) {
  const { g, M, lite } = c, s = seg(c, 36, 12);
  const prof = [[0.001, 0.12], [0.2, 0.14], [0.37, 0.28], [0.4, 0.6], [0.32, 0.98], [0.12, 1.2], [0.04, 1.26], [0.04, 1.34], [0.12, 1.4], [0.32, 1.62], [0.4, 1.98], [0.37, 2.3], [0.2, 2.44], [0.001, 2.46]];
  mesh(g, lathe(prof, s), M.glass, 0, 0, 0);
  mesh(g, lathe([[0.001, 0.14], [0.3, 0.16], [0.34, 0.3], [0.27, 0.42], [0.1, 0.62], [0.001, 0.7]], s), M.sand, 0, 0, 0);           // the heap below
  mesh(g, lathe([[0.001, 1.9], [0.2, 1.96], [0.34, 2.12], [0.31, 2.22], [0.001, 2.28]], s), M.sand, 0, 0, 0);                       // what is left above
  if (!lite) mesh(g, cyl(0.012, 0.012, 0.66, 6), M.sand, 0, 0.98, 0);                                                              // the thin stream
  for (const y of [0.04, 2.5]) { mesh(g, cyl(0.52, 0.52, 0.08, seg(c, 36, 12)), M.bronze, 0, y, 0); mesh(g, torus(0.5, 0.025, 6, seg(c, 36, 12)), M.gold, 0, y + (y < 1 ? 0.04 : -0.04), 0, PI / 2); }
  for (let i = 0; i < 3; i++) { const a = (i / 3) * TAU + 0.5; mesh(g, cyl(0.025, 0.025, 2.46, 8), M.bronze, Math.sin(a) * 0.46, 1.27, Math.cos(a) * 0.46); }
  mesh(g, cyl(0.62, 0.7, 0.1, seg(c, 36, 12)), M.stone, 0, -0.05, 0);
}
function sundial(c) {
  const { g, M, lite } = c, s = seg(c, 32, 12);
  mesh(g, lathe([[0.001, 0], [0.5, 0], [0.5, 0.1], [0.34, 0.16], [0.24, 0.3], [0.2, 0.5], [0.2, 0.8], [0.3, 0.9], [0.001, 0.9]], s), M.marble, 0, 0, 0);
  mesh(g, cyl(0.95, 0.95, 0.1, seg(c, 48, 16)), M.marble, 0, 0.95, 0);
  mesh(g, torus(0.93, 0.03, 6, seg(c, 56, 18)), M.bronze, 0, 1.0, 0, PI / 2);
  const ticks = [], n = lite ? 8 : 13;
  for (let i = 0; i < n; i++) { const a = -PI / 2 + (i / (n - 1)) * PI - PI / 2; ticks.push({ p: [Math.cos(a) * 0.74, 1.005, Math.sin(a) * 0.74], r: [0, -a + PI / 2, 0], s: [1, 1, i % 3 === 0 ? 1.6 : 1] }); }
  instanced(g, box(0.035, 0.016, 0.1), M.gold, ticks);
  const sh = new THREE.Shape([new THREE.Vector2(0, 0), new THREE.Vector2(0.7, 0), new THREE.Vector2(0, 0.46)]);
  const gn = new THREE.ExtrudeGeometry(sh, { depth: 0.035, bevelEnabled: false }); gn.translate(0, 0, -0.0175); gn.rotateY(-PI / 2);
  mesh(g, gn, M.bronze, 0, 1.0, -0.35);
  if (!lite) mesh(g, box(0.05, 0.012, 0.66), M.ink, 0.26, 1.006, 0.02, 0, -0.7, 0);                // the shadow it casts
}
function brazier(c) {
  const { g, M, lite } = c;
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * TAU + 0.3, leg = mesh(g, cyl(0.035, 0.05, 1.12, seg(c, 8, 5)), M.bronze, Math.sin(a) * 0.3, 0.52, Math.cos(a) * 0.3);
    leg.rotation.set(-Math.cos(a) * 0.3, 0, Math.sin(a) * 0.3);
  }
  mesh(g, torus(0.19, 0.022, 6, seg(c, 24, 10)), M.gold, 0, 0.72, 0, PI / 2);
  mesh(g, lathe([[0.001, 0], [0.14, 0.02], [0.3, 0.14], [0.44, 0.3], [0.46, 0.34], [0.42, 0.34], [0.3, 0.2], [0.001, 0.08]], seg(c, 32, 12)), M.bronze, 0, 1.0, 0);
  mesh(g, torus(0.45, 0.025, 6, seg(c, 32, 12)), M.gold, 0, 1.34, 0, PI / 2);
  mesh(g, sph(0.3, seg(c, 14, 6), seg(c, 8, 4), 1, 0.35, 1), M.coal, 0, 1.28, 0);
  const f1 = mesh(g, cone(0.22, 0.66, seg(c, 12, 6)), M.flame, 0, 1.64, 0);
  const f2 = mesh(g, cone(0.12, 0.44, seg(c, 10, 5)), M.flameCore, 0, 1.58, 0.0);
  if (!lite) { mesh(g, cone(0.11, 0.42, 8), M.flame, 0.14, 1.55, 0.05, 0, 0, -0.35); mesh(g, cone(0.1, 0.36, 8), M.flame, -0.15, 1.52, -0.04, 0, 0, 0.4); }
  g.userData.update = (t) => { const k = 1 + 0.04 * Math.sin(t * 1.6); f1.scale.set(1 / k, k, 1 / k); f2.scale.set(1 / k, 1 + 0.06 * Math.sin(t * 1.9 + 1), 1 / k); };
}
function scroll(c) {
  const { g, M, lite } = c, s = seg(c, 20, 8);
  mesh(g, box(2.0, 0.08, 1.2), M.stone, 0, 0.04, 0);
  const sheet = new THREE.PlaneGeometry(1.46, 0.98, seg(c, 24, 6), 1);
  sheet.rotateX(-PI / 2);
  const p = sheet.attributes.position;
  for (let i = 0; i < p.count; i++) p.setY(i, 0.04 - 0.07 * (1 - Math.pow(p.getX(i) / 0.73, 2)) + 0.17);
  sheet.computeVertexNormals();
  mesh(g, sheet, M.cloth, 0, 0.08, 0);
  for (const sx of [-1, 1]) {
    mesh(g, cyl(0.17, 0.17, 1.0, s), M.cloth, sx * 0.84, 0.25, 0, PI / 2);
    mesh(g, cyl(0.085, 0.085, 1.0, seg(c, 12, 6)), M.wood, sx * 0.84, 0.25, 0, PI / 2);
    for (const sz of [-1, 1]) mesh(g, cyl(0.12, 0.09, 0.06, seg(c, 14, 6)), M.gold, sx * 0.84, 0.25, sz * 0.55, PI / 2);
    if (!lite) mesh(g, torus(0.15, 0.012, 4, 24), M.stone, sx * 0.84, 0.25, 0.3, 0, PI / 2);
  }
  if (!lite) {
    const lines = [];
    for (let i = 0; i < 8; i++) { const w = 0.9 - ((i * 37) % 5) * 0.08; lines.push({ p: [-0.62 + w / 2, 0.205, -0.36 + i * 0.1], s: [w, 1, 1] }); }
    instanced(g, box(1, 0.004, 0.028), M.ink, lines);
  }
  mesh(g, box(0.07, 0.01, 0.98), M.terra, 0.35, 0.205, 0);                                          // the tie
  mesh(g, cyl(0.08, 0.08, 0.025, seg(c, 16, 8)), M.gold, 0.35, 0.215, 0.1);
}
function pillarbar(c) {
  const { g, M, lite } = c, vals = (Array.isArray(c.o.values) && c.o.values.length ? c.o.values : [0.35, 0.62, 0.48, 0.8, 1]).slice(0, 12).map((v) => Math.max(0.04, Math.min(1, Number(v) || 0)));
  const tones = Array.isArray(c.o.tones) ? c.o.tones : [], n = vals.length, W = Math.max(2.2, n * 0.42), step = W / n, r = Math.min(0.15, step * 0.34), H = 1.7;
  mesh(g, box(W + 0.3, 0.1, 0.9), M.stone, 0, 0.05, 0);
  mesh(g, box(W + 0.18, 0.06, 0.78), M.marble, 0, 0.13, 0);
  const x0 = -W / 2 + step / 2, shafts = [], bases = [], caps = [];
  vals.forEach((v, i) => {
    const h = v * H, x = x0 + i * step, tone = tones[i], col = tone === 'gain' ? '#cdd8a8' : tone === 'loss' ? '#e3b09c' : '#ffffff';
    shafts.push({ p: [x, 0.16 + h / 2, 0], s: [1, h, 1], c: col });
    bases.push({ p: [x, 0.18, 0] });
    caps.push({ p: [x, 0.16 + h + 0.03, 0] });
  });
  instanced(g, cyl(r * 0.88, r, 1, seg(c, 24, 10)), M.marble, shafts);
  instanced(g, cyl(r * 1.35, r * 1.4, 0.05, seg(c, 24, 10)), M.marble, bases);
  instanced(g, cyl(r * 1.5, r * 1.2, 0.06, seg(c, 24, 10)), M.gold, caps);
  g.userData.bars = n;
}

export const SHAPES = Object.freeze([
  { id: 'doric', name: 'Doric column', group: 'Temples and monuments', means: 'Strength and discipline. The plain, sturdy column: one simple rule that holds the whole roof up.', build: doric },
  { id: 'ionic', name: 'Ionic column', group: 'Temples and monuments', means: 'Learning and balance. The scrolled column: a plan that is both strong and graceful.', build: ionic },
  { id: 'temple', name: 'Temple', group: 'Temples and monuments', means: 'A place of trust. Every part of the system standing together under one roof.', build: temple },
  { id: 'lighthouse', name: 'Lighthouse of Pharos', group: 'Temples and monuments', means: 'Guidance in the dark. A steady light to steer by: the levels the bot watches.', build: lighthouse },
  { id: 'obelisk', name: 'Obelisk', group: 'Temples and monuments', means: 'Permanence. A record carved to last: the long, honest track record.', build: obelisk },
  { id: 'sundial', name: 'Sundial', group: 'Time and counsel', means: 'Timing. Reading the session by the light of day: when to trade and when to wait.', build: sundial },
  { id: 'hourglass', name: 'Hourglass', group: 'Time and counsel', means: 'Time running. The eval clock and the trading day: sand falls, patience pays.', build: hourglass },
  { id: 'owl', name: "Athena's owl", group: 'Time and counsel', means: 'Wisdom. Look carefully, then act: analysis before every decision.', build: owl },
  { id: 'scroll', name: 'Scroll', group: 'Time and counsel', means: 'The written plan. Rules and records kept on paper so nothing is left to memory.', build: scroll },
  { id: 'amphora', name: 'Amphora', group: 'Wealth and trade', means: 'Savings. A store of value kept safe for later: payouts put away.', build: amphora },
  { id: 'coinstack', name: 'Coin stacks', group: 'Wealth and trade', means: 'Capital. The money itself, built coin by coin and counted in dollars.', build: coinstack },
  { id: 'scales', name: 'Scales', group: 'Wealth and trade', means: 'Risk against reward. Every R weighed next to its dollars.', build: scales },
  { id: 'pillarbar', name: 'Pillar chart', group: 'Wealth and trade', means: 'Results at a glance. A bar chart built as pillars: taller means more.', build: pillarbar },
  { id: 'trireme', name: 'Trireme', group: 'Wealth and trade', means: 'Reach and trade. Capital sailing out to markets and coming home.', build: trireme },
  { id: 'laurel', name: 'Laurel wreath', group: 'War and glory', means: 'Victory. A goal reached: a passed eval, a good week.', build: laurel },
  { id: 'shield', name: 'Hoplon shield', group: 'War and glory', means: 'Defence. Protecting the account: the drawdown limit that is never crossed.', build: shield },
  { id: 'helmet', name: 'Corinthian helmet', group: 'War and glory', means: 'Readiness. Focus put on before the open: calm, covered, ready.', build: helmet },
  { id: 'lyre', name: 'Lyre of Apollo', group: 'War and glory', means: 'Harmony. Many strings in tune: entries, stops and targets playing one plan.', build: lyre },
  { id: 'brazier', name: 'Brazier', group: 'War and glory', means: "Hestia's fire. The steady daily routine that keeps the home warm.", build: brazier },
]);
export const IDS = Object.freeze(SHAPES.map((s) => s.id));
export const GROUPS = Object.freeze(['Temples and monuments', 'Time and counsel', 'Wealth and trade', 'War and glory']);
const BY_ID = Object.freeze(Object.fromEntries(SHAPES.map((s) => [s.id, s])));

// ------------------------------------------------------------------ public API
/** build('owl', { lite, materials, kit, size, values, tones, tilt }) -> THREE.Group (userData: id, lite, update?(t) for gentle motion) */
export function build(id, o) {
  o = o || {};
  const def = BY_ID[id];
  if (!def) throw new RangeError('shapes3d: unknown shape ' + id);
  const lite = !!o.lite, own = !o.materials, M = o.materials || materials({ lite, kit: o.kit });
  const g = new THREE.Group();
  g.name = 'agora:' + id;
  def.build({ g, M, lite, o });
  g.userData.id = id; g.userData.lite = lite; g.userData.ownMaterials = own ? M : null;
  if (o.size) fit(g, o.size);
  return g;
}
/** scale the group (and stand it on y = 0, centred) so its longest side is `size` */
export function fit(g, size) {
  g.scale.setScalar(1); g.position.set(0, 0, 0);
  const b = new THREE.Box3().setFromObject(g), v = b.getSize(new THREE.Vector3()), k = size / Math.max(v.x, v.y, v.z, 1e-6);
  g.scale.setScalar(k);
  const b2 = new THREE.Box3().setFromObject(g), cc = b2.getCenter(new THREE.Vector3());
  g.position.set(-cc.x, -b2.min.y, -cc.z);
  return g;
}
/** { meshes, draws, tris, instances, size: [x, y, z] } for a built group (draws = one per Mesh / InstancedMesh) */
export function stats(g) {
  let draws = 0, tris = 0, inst = 0;
  g.traverse((o) => {
    if (!o.isMesh) return;
    draws++;
    const geo = o.geometry, n = geo.index ? geo.index.count : geo.attributes.position.count;
    const k = o.isInstancedMesh ? o.count : 1;
    tris += (n / 3) * k;
    if (o.isInstancedMesh) inst += o.count;
  });
  const sz = new THREE.Box3().setFromObject(g).getSize(new THREE.Vector3());
  return { draws, tris: Math.round(tris), instances: inst, size: [sz.x, sz.y, sz.z].map((v) => Math.round(v * 1000) / 1000) };
}
export function dispose(g) {
  g.traverse((o) => { if (o.isMesh && o.geometry) o.geometry.dispose(); if (o.isInstancedMesh) o.dispose(); });
  const own = g.userData && g.userData.ownMaterials;
  if (own) own.dispose();
  if (g.parent) g.parent.remove(g);
}
/** a marble drum with a gold ring: the rotating pedestal of the gallery, handy for any display of a shape */
export function pedestal({ lite = false, radius = 1.5, M = null } = {}) {
  const g = new THREE.Group(), mm = M || materials({ lite });
  mesh(g, cyl(radius, radius * 1.06, 0.3, lite ? 28 : 64), mm.marble, 0, -0.15, 0);
  mesh(g, torus(radius * 1.005, 0.025, lite ? 4 : 8, lite ? 28 : 96), mm.gold, 0, -0.02, 0, PI / 2, 0, 0);
  g.userData.ownMaterials = M ? null : mm;
  return g;
}
/** warm light for a shape scene (colour temperature about 3000 K): a sun-side key, a soft fill, no coloured rim lights */
export function warmLights(scene, { lite = false } = {}) {
  const hemi = new THREE.HemisphereLight(0xfff0d8, 0x4a3a2a, lite ? 1.1 : 0.55), key = new THREE.DirectionalLight(0xffd9a6, lite ? 1.8 : 2.6), fill = new THREE.DirectionalLight(0xe9d6bd, 0.55);
  key.position.set(3.2, 5.5, 4); fill.position.set(-4, 2, -3);
  scene.add(hemi, key, fill);
  return { hemi, key, fill, remove() { scene.remove(hemi, key, fill); } };
}
