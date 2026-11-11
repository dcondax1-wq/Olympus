// PEOPLE OF OLYMPUS in 3D (docs/PERSONA_API.md "The look of a person"): the same friendly cartoon character as the round 2D portrait, as a small toy-like figure.
// Original design: a big round head, dot eyes, a small mouth, a short rounded body in a chiton, mitten hands, simple legs, one accessory by kind. Matte, warm, no glow.
//
//   import { spec, figure, figureInstanced } from '../olympus/people3d.js';      // THREE is passed in: this module imports no three.js of its own
//   const s = spec('scanner:sibyl');                         // plain data, the same every time (uses OLYMPUS_PEOPLE when it is on the page: roster + mood)
//   const f = figure(THREE, s, { lite, seated, scale });     // Object3D, about 1 unit tall, feet at y = 0, facing +z
//   f.userData.pose('idle' | 'wave' | 'talk' | 'cheer' | 'slump' | 'nod' | 'shrug');   f.userData.lookAt(vec3);   f.userData.tick(dt, t);   f.userData.dispose();
//   const crowd = figureInstanced(THREE, specs, { lite, seated });   // one Group, 11 draw calls for any number of people
//   crowd.userData.place(i, x, y, z, ry, scale); crowd.userData.setActive(i, on); crowd.userData.tick(t); crowd.userData.pick(raycaster) -> index | -1
//
// Budget (measured by tests/test_people.py): one figure = 7 meshes, one shared material, <= 900 triangles (<= 350 with lite). Geometries are baked once per figure with
// vertex colours; call dispose() when a figure leaves the scene. Without tick() a figure simply stands in its pose (reduced motion: do not call tick).
import * as C from './people-core.js';

/** the character sheet for an id, a person or a ready spec */
export function spec(id, over) {
  if (C.isObj(id) && id.hairStyle && id.skin) return over ? C.spec({ seed: id.seed }, { ...id, ...over }) : id;
  try { if (typeof window !== 'undefined' && window.OLYMPUS_PEOPLE && typeof window.OLYMPUS_PEOPLE.spec === 'function') return window.OLYMPUS_PEOPLE.spec(id, over); } catch (_) { /* fall through */ }
  return C.spec(C.isObj(id) ? id : { id: String(id || 'someone'), kind: String(id || '').split(':')[0] }, over);
}

const INK = '#2a2019', IVORY = '#f6efe2', BRONZE = '#b98a4a', GOLD = '#d9b25a', TERRA = '#c96a4a', SANDAL = '#6b4a2a';
const R = 0.21;                     // head radius
const HEAD_Y = 0.77, NECK_Y = 0.56, SHOULDER_Y = 0.5, SHOULDER_X = 0.175;
const MATS = new WeakMap();
function material(THREE) {
  let m = MATS.get(THREE);
  if (!m) { m = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0 }); m.name = 'olympus-person'; MATS.set(THREE, m); }
  return m;
}
function M(THREE, x, y, z, rx, ry, rz, sx, sy, sz) {
  const m = new THREE.Matrix4(), q = new THREE.Quaternion().setFromEuler(new THREE.Euler(rx || 0, ry || 0, rz || 0, 'YXZ'));
  return m.compose(new THREE.Vector3(x || 0, y || 0, z || 0), q, new THREE.Vector3(sx == null ? 1 : sx, sy == null ? (sx == null ? 1 : sx) : sy, sz == null ? (sx == null ? 1 : sx) : sz));
}
/** a matrix that puts a flat +z-facing plate on the head sphere, looking outward. yaw: left/right, pitch: up/down (radians), k: distance factor */
function onHead(THREE, yaw, pitch, k, roll, s, sy) {
  const dir = new THREE.Vector3(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch));
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir);
  if (roll) q.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), roll));
  return new THREE.Matrix4().compose(dir.multiplyScalar(R * (k || 1.01)), q, new THREE.Vector3(s == null ? 1 : s, sy == null ? (s == null ? 1 : s) : sy, 1));
}
/** parts = [[geometry, '#colour' | null (white, for instancing), Matrix4]] -> one BufferGeometry with position / normal / color. The part geometries are disposed. */
function bake(THREE, parts) {
  const pos = [], nor = [], col = [], c = new THREE.Color();
  for (const [g0, colour, m] of parts) {
    const g = g0.index ? g0.toNonIndexed() : g0;
    if (m) g.applyMatrix4(m);
    const p = g.getAttribute('position'), n = g.getAttribute('normal');
    c.set(colour || '#ffffff');
    for (let i = 0; i < p.count; i++) { pos.push(p.getX(i), p.getY(i), p.getZ(i)); nor.push(n.getX(i), n.getY(i), n.getZ(i)); col.push(c.r, c.g, c.b); }
    if (g !== g0) g.dispose();
    g0.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  out.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  out.computeBoundingSphere();
  out.userData.triangles = pos.length / 9;
  return out;
}

// ------------------------------------------------------------------------------------------------ the parts (shared by figure and figureInstanced)
function headParts(THREE, s, lite, tint) {
  const P = [], w = lite ? 8 : 12, hh = lite ? 5 : 7, col = (c) => (tint ? null : c);
  const wide = s.build === 'round' ? 1.07 : s.build === 'slim' ? 0.95 : 1;
  P.push([new THREE.SphereGeometry(R, w, hh), col(s.skin), M(THREE, 0, 0, 0, 0, 0, 0, wide, 1.02, 0.98)]);
  if (!lite) {
    for (const sx of [-1, 1]) P.push([new THREE.IcosahedronGeometry(0.042, 0), col(C.shade(s.skin, -0.14)), M(THREE, sx * R * wide * 0.98, -0.01, 0, 0, 0, 0, 0.6, 1, 0.8)]);
    P.push([new THREE.IcosahedronGeometry(0.024, 0), col(C.shade(s.skin, -0.14)), onHead(THREE, 0, -0.1, 1.02)]);
  }
  return P;
}
function hairParts(THREE, s, lite, which) {
  const P = [], w = lite ? 8 : 12, hs = s.accessory === 'helmet' ? 'none' : s.hairStyle, h = s.hair, top = which !== 'back' && which !== 'knot', back = !which || which === 'back', knot = !which || which === 'knot';
  if (hs === 'none' || hs === 'bald') return P;
  if (top) {
    const tilt = hs === 'wavy' ? [-0.42, 0, 0.3] : [-0.38, 0, 0];
    P.push([new THREE.SphereGeometry(R * 1.055, w, lite ? 3 : 4, 0, Math.PI * 2, 0, Math.PI * (hs === 'curly' ? 0.4 : 0.47)), which ? null : h, M(THREE, 0, 0.004, -0.004, tilt[0], tilt[1], tilt[2], s.build === 'round' ? 1.07 : 1, 1.03, 1)]);
    if (hs === 'curly' && !lite && !which) for (let i = 0; i < 6; i++) { const a = Math.PI * (0.08 + i * 0.168); P.push([new THREE.IcosahedronGeometry(0.062, 0), i % 2 ? h : C.shade(h, 0.07), M(THREE, Math.cos(a) * R * 0.92, 0.1 + Math.sin(a) * R * 0.62, 0.05)]); }
  }
  if (back && (hs === 'long' || hs === 'bob')) P.push([new THREE.SphereGeometry(R * 1.07, lite ? 5 : 7, lite ? 3 : 4, Math.PI * 1.02, Math.PI * 0.96, Math.PI * 0.2, Math.PI * (hs === 'long' ? 0.62 : 0.48)), which ? null : h, M(THREE, 0, 0, 0, 0, 0, 0, 1.03, hs === 'long' ? 1.32 : 1.08, 1.02)]);
  if (knot && (hs === 'bun' || hs === 'topknot')) P.push([new THREE.IcosahedronGeometry(hs === 'bun' ? 0.085 : 0.06, lite ? 0 : 1), which ? null : h, hs === 'bun' ? M(THREE, 0, R * 0.92, -R * 0.42) : M(THREE, 0, R * 1.16, -0.02, 0, 0, 0, 0.85, 1.25, 0.85)]);
  return P;
}
function faceExtras(THREE, s, lite) {
  const P = [], bd = s.face.beard;
  if (!lite) for (const sx of [-1, 1]) P.push([new THREE.CircleGeometry(0.034, 6), C.mix(s.skin, TERRA, 0.36), onHead(THREE, sx * 0.62, -0.2, 1.006)]);
  if (bd === 'short' || bd === 'full') P.push([new THREE.SphereGeometry(R * 1.035, lite ? 6 : 8, lite ? 2 : 3, Math.PI / 2 - 1.15, 2.3, Math.PI * 0.6, Math.PI * (bd === 'full' ? 0.4 : 0.3)), s.hair, M(THREE, 0, bd === 'full' ? -0.012 : 0, 0.004, 0, 0, 0, s.build === 'round' ? 1.07 : 1, bd === 'full' ? 1.12 : 1.02, 1)]);
  if (bd === 'moustache') P.push([new THREE.BoxGeometry(0.1, 0.022, 0.012), s.hair, onHead(THREE, 0, -0.27, 1.03)]);
  if (s.face.glasses && !lite) { for (const sx of [-1, 1]) P.push([new THREE.RingGeometry(0.047, 0.058, 10), SANDAL, onHead(THREE, sx * 0.36, 0.03, 1.045)]); P.push([new THREE.BoxGeometry(0.05, 0.01, 0.006), SANDAL, onHead(THREE, 0, 0.04, 1.05)]); }
  if (!lite) { const bc = s.hair === '#e6e0d2' || s.hair === '#d9c08a' ? '#8a7a5a' : C.shade(s.hair, -0.25), k = s.face.brows, worried = s.mood === 'worried' || s.mood === 'sheepish';
    for (const sx of [-1, 1]) P.push([new THREE.BoxGeometry(0.058, k === 'thick' ? 0.02 : 0.013, 0.006), bc, onHead(THREE, sx * 0.36, 0.3 + (s.mood === 'proud' ? 0.03 : 0), 1.012, sx * (worried ? 0.3 : k === 'slant' ? -0.22 : k === 'arched' ? 0.1 : 0))]); }
  return P;
}
function headAccessory(THREE, s, lite, tint) {
  const P = [];
  if (s.accessory === 'laurel') P.push([new THREE.TorusGeometry(R * 1.03, 0.022, 3, lite ? 8 : 10, Math.PI * 1.5), tint ? null : GOLD, M(THREE, 0, 0.05, -0.01, Math.PI / 2 - 0.3, 0, Math.PI * 0.75)]);
  if (s.accessory === 'helmet') {
    P.push([new THREE.SphereGeometry(R * 1.07, lite ? 8 : 12, lite ? 3 : 4, 0, Math.PI * 2, 0, Math.PI * 0.5), tint ? null : BRONZE, M(THREE, 0, 0.012, -0.006, -0.3, 0, 0, s.build === 'round' ? 1.07 : 1, 1.03, 1)]);
    P.push([new THREE.TorusGeometry(R * 0.98, 0.032, 3, lite ? 5 : 7, Math.PI * 0.9), tint ? null : TERRA, M(THREE, 0, 0.085, -0.02, 0, Math.PI / 2, 0.16, 1, 1, 0.6)]);
  }
  return P;
}
function eyeParts(THREE, s, lite) {
  const P = [], k = s.mood === 'proud' && s.face.eyes !== 'wide' ? 'smile' : s.face.eyes, seg = lite ? 6 : 10;
  for (const sx of [-1, 1]) {
    if (k === 'smile') P.push([new THREE.RingGeometry(0.022, 0.036, lite ? 4 : 6, 1, 0, Math.PI), INK, onHead(THREE, sx * 0.36, 0.04, 1.012)]);
    else if (k === 'wide') { P.push([new THREE.CircleGeometry(0.046, seg), IVORY, onHead(THREE, sx * 0.36, 0.05, 1.012)]); P.push([new THREE.CircleGeometry(0.027, seg), INK, onHead(THREE, sx * 0.36, 0.045, 1.022)]); }
    else P.push([new THREE.CircleGeometry(0.031, seg), INK, onHead(THREE, sx * 0.36, 0.05, 1.012, 0, 1, k === 'oval' ? 1.35 : 1)]);
    if (!lite && k !== 'smile') P.push([new THREE.CircleGeometry(0.009, 5), IVORY, onHead(THREE, sx * 0.36 + 0.035, 0.085, 1.03)]);
  }
  return P;
}
function mouthParts(THREE, s, lite) {
  const mood = s.mood, k = mood === 'proud' ? 'grin' : mood === 'sheepish' ? 'flat' : mood === 'worried' ? 'frown' : s.face.mouth, seg = lite ? 4 : 6, bearded = s.face.beard === 'full' || s.face.beard === 'short';
  const col = bearded ? IVORY : INK, at = (roll, sx, sy) => onHead(THREE, 0, -0.42, bearded ? 1.05 : 1.014, roll, sx, sy);
  if (k === 'grin') return [[new THREE.CircleGeometry(0.05, seg + 2, Math.PI, Math.PI), '#5a2a22', at(0, 1, 1)]];
  if (k === 'frown') return [[new THREE.RingGeometry(0.03, 0.043, seg, 1, 0, Math.PI), col, at(0, 1, 0.7)]];
  if (k === 'flat') return [[new THREE.BoxGeometry(0.06, 0.012, 0.004), col, at(0, 1, 1)]];
  return [[new THREE.RingGeometry(k === 'small' ? 0.018 : 0.034, k === 'small' ? 0.03 : 0.047, seg, 1, Math.PI, Math.PI), col, at(0, 1, k === 'small' ? 1 : 0.85)]];
}
function bodyParts(THREE, s, lite, tint) {
  const P = [], w = lite ? 6 : 10, fat = s.build === 'round' ? 1.14 : s.build === 'slim' ? 0.9 : s.build === 'broad' ? 1.06 : 1, o = tint ? null : s.outfit;
  P.push([new THREE.CylinderGeometry(0.125, 0.19, 0.34, w, 1, lite), o, M(THREE, 0, 0.37, 0, 0, 0, 0, fat, 1, fat * 0.92)]);
  P.push([new THREE.SphereGeometry(0.125, w, lite ? 2 : 3, 0, Math.PI * 2, 0, Math.PI / 2), o, M(THREE, 0, 0.54, 0, 0, 0, 0, fat * (s.build === 'broad' ? 1.12 : 1), 0.5, fat * 0.92)]);
  return P;
}
function trimParts(THREE, s, lite, tint) {
  const w = lite ? 6 : 10, fat = s.build === 'round' ? 1.14 : s.build === 'slim' ? 0.9 : s.build === 'broad' ? 1.06 : 1, a = tint ? null : s.accent, P = [];
  if (!lite || tint) P.push([new THREE.CylinderGeometry(0.19, 0.196, 0.035, w, 1, true), a, M(THREE, 0, 0.218, 0, 0, 0, 0, fat * 1.01, 1, fat * 0.93)]);
  if (!lite) P.push([new THREE.BoxGeometry(0.05, 0.3, 0.012), a, M(THREE, 0.045, 0.4, 0.158 * fat * 0.92, -0.18, 0, 0.5)]);
  return P;
}
function bodyAccessory(THREE, s, lite) {
  const P = [], a = s.accessory;
  if (a === 'owl') {
    P.push([new THREE.SphereGeometry(0.06, lite ? 5 : 6, lite ? 3 : 4), '#9c6b3c', M(THREE, -0.17, 0.62, 0.02, 0, 0, 0, 0.85, 1.1, 0.85)]);
    if (!lite) { for (const sx of [-1, 1]) { P.push([new THREE.CircleGeometry(0.019, 6), IVORY, M(THREE, -0.17 + sx * 0.022, 0.64, 0.071)]); P.push([new THREE.CircleGeometry(0.008, 5), INK, M(THREE, -0.17 + sx * 0.022, 0.64, 0.074)]); } P.push([new THREE.ConeGeometry(0.012, 0.024, 3), GOLD, M(THREE, -0.17, 0.618, 0.07, Math.PI / 2)]); }
  }
  if (a === 'pouch') { P.push([new THREE.SphereGeometry(0.055, lite ? 5 : 6, lite ? 3 : 4), '#9c6b3c', M(THREE, 0.16, 0.27, 0.1, 0, 0, 0, 1, 1.1, 0.8)]); if (!lite) P.push([new THREE.CircleGeometry(0.022, 8), GOLD, M(THREE, 0.16, 0.27, 0.146)]); }
  if (a === 'key') { if (!lite) P.push([new THREE.TorusGeometry(0.034, 0.011, 3, 8), GOLD, M(THREE, 0.1, 0.29, 0.172)]); P.push([new THREE.BoxGeometry(0.014, 0.075, 0.012), GOLD, M(THREE, 0.1, 0.225, 0.172)]); }
  return P;
}
function armParts(THREE, s, lite, side, tint) {
  const P = [], o = tint === 'outfit' ? null : s.outfit, sk = tint === 'skin' ? null : s.skin, both = !tint;
  if (both || tint === 'outfit') P.push([new THREE.CylinderGeometry(0.045, 0.04, 0.19, lite ? 4 : 6, 1, true), o, M(THREE, 0, -0.095, 0)]);
  if (both || tint === 'skin') P.push([lite ? new THREE.IcosahedronGeometry(0.052, 0) : new THREE.SphereGeometry(0.052, 6, 4), sk, M(THREE, 0, -0.215, 0, 0, 0, 0, 0.9, 1.05, 1)]);
  if (both) {
    const a = s.accessory;
    if (a === 'hammer' && side > 0) { P.push([new THREE.CylinderGeometry(0.012, 0.012, 0.2, 5), '#9c6b3c', M(THREE, 0, -0.215, 0.06, Math.PI / 2)]); P.push([new THREE.BoxGeometry(0.1, 0.055, 0.05), '#8c867c', M(THREE, 0, -0.215, 0.16)]); }
    if (a === 'torch' && side > 0) { P.push([new THREE.CylinderGeometry(0.014, 0.01, 0.2, 5), '#9c6b3c', M(THREE, 0, -0.215, 0.06, Math.PI / 2)]); P.push([new THREE.ConeGeometry(0.035, 0.09, 5), '#e0b060', M(THREE, 0, -0.215, 0.2, Math.PI / 2)]); }
    if (a === 'scroll' && side < 0) { P.push([new THREE.CylinderGeometry(0.026, 0.026, 0.17, 6), '#e9dfc9', M(THREE, 0, -0.215, 0.02, 0, 0, Math.PI / 2)]); }
  }
  return P;
}
function legParts(THREE, s, lite, seated, tint) {
  const P = [], sk = tint === 'skin' ? null : s.skin, both = !tint;
  for (const sx of [-1, 1]) {
    if (seated) {
      if (both || tint === 'skin') P.push([lite ? new THREE.BoxGeometry(0.09, 0.09, 0.2) : new THREE.CylinderGeometry(0.05, 0.048, 0.2, 5, 1, true), sk, lite ? M(THREE, sx * 0.08, 0.24, 0.2) : M(THREE, sx * 0.08, 0.24, 0.2, Math.PI / 2)]);
      if ((both && !lite) || tint === 'dark') P.push([lite ? new THREE.BoxGeometry(0.1, 0.07, 0.1) : new THREE.SphereGeometry(0.058, 5, 3), tint ? null : SANDAL, M(THREE, sx * 0.08, 0.235, 0.32, 0, 0, 0, 1, 0.9, 1.1)]);
    } else {
      if (both || tint === 'skin') P.push([lite ? new THREE.BoxGeometry(0.09, 0.2, 0.09) : new THREE.CylinderGeometry(0.052, 0.046, 0.2, 5, 1, true), sk, M(THREE, sx * 0.08, 0.12, 0)]);
      if ((both && !lite) || tint === 'dark') P.push([lite ? new THREE.BoxGeometry(0.1, 0.05, 0.14) : new THREE.SphereGeometry(0.06, 5, 3), tint ? null : SANDAL, M(THREE, sx * 0.08, 0.03, 0.025, 0, 0, 0, 1, 0.55, 1.4)]);
    }
  }
  return P;
}

const POSES = {
  idle: { aL: [0, -0.2], aR: [0, 0.2], head: [0, 0], lean: 0, bounce: 0 },
  wave: { aL: [0, -0.2], aR: [0, 2.55], head: [-0.05, 0], lean: 0, bounce: 0, wave: 1 },
  talk: { aL: [-0.5, -0.3], aR: [-0.7, 0.35], head: [0, 0], lean: 0, bounce: 0, talk: 1 },
  cheer: { aL: [0, -2.6], aR: [0, 2.6], head: [-0.2, 0], lean: -0.04, bounce: 1 },
  slump: { aL: [0.15, -0.08], aR: [0.15, 0.08], head: [0.42, 0], lean: 0.16, bounce: 0 },
  nod: { aL: [0, -0.2], aR: [0, 0.2], head: [0, 0], lean: 0, bounce: 0, nod: 1 },
  shrug: { aL: [0, -0.75], aR: [0, 0.75], head: [0, 0.2], lean: 0, bounce: 0, shrug: 1 },
};
export const POSE_NAMES = Object.keys(POSES);

/** one character as a small rig: root > [legs, torso > [body, armL, armR, head > [skull, eyes, mouth]]] */
export function figure(THREE, sp, opts) {
  const o = opts || {}, s = spec(sp), lite = !!o.lite, mat = o.material || material(THREE);
  const root = new THREE.Group(); root.name = 'person';
  const torso = new THREE.Group(), head = new THREE.Group(), pivL = new THREE.Group(), pivR = new THREE.Group();
  const geos = [];
  const mesh = (parts, name) => { const g = bake(THREE, parts); geos.push(g); const m = new THREE.Mesh(g, mat); m.name = name; return m; };
  const legs = mesh(legParts(THREE, s, lite, !!o.seated), 'legs');
  const body = mesh(bodyParts(THREE, s, lite).concat(trimParts(THREE, s, lite), bodyAccessory(THREE, s, lite)), 'body');
  const armL = mesh(armParts(THREE, s, lite, -1), 'armL'), armR = mesh(armParts(THREE, s, lite, 1), 'armR');
  const skull = mesh(headParts(THREE, s, lite).concat(hairParts(THREE, s, lite), faceExtras(THREE, s, lite), headAccessory(THREE, s, lite)), 'head');
  const eyes = mesh(eyeParts(THREE, s, lite), 'eyes'), mouth = mesh(mouthParts(THREE, s, lite), 'mouth');
  pivL.position.set(-SHOULDER_X, SHOULDER_Y, 0); pivR.position.set(SHOULDER_X, SHOULDER_Y, 0); pivL.add(armL); pivR.add(armR);
  head.position.set(0, HEAD_Y, 0); head.add(skull, eyes, mouth);
  const mouthY = -R * Math.sin(0.42);
  torso.add(body, pivL, pivR, head);
  if (o.seated) torso.position.y = -0.02;
  root.add(legs, torso);
  const k = (o.scale || 1) * (s.height || 1);
  root.scale.setScalar(k);
  const st = { name: 'idle', cur: { aLx: 0, aLz: -0.2, aRx: 0, aRz: 0.2, hx: 0, hy: 0, lean: 0 }, look: null, phase: ((s.seed >>> 0) % 628) / 100, t: 0 };
  function apply(extra) {
    const c = st.cur, e = extra || {};
    pivL.rotation.set(c.aLx + (e.aLx || 0), 0, c.aLz + (e.aLz || 0)); pivR.rotation.set(c.aRx + (e.aRx || 0), 0, c.aRz + (e.aRz || 0));
    head.rotation.set(c.hx + (e.hx || 0), c.hy + (e.hy || 0), 0, 'YXZ'); torso.rotation.x = c.lean;
    torso.position.y = (o.seated ? -0.02 : 0) + (e.y || 0); torso.scale.y = 1 + (e.breathe || 0);
  }
  function target() { const p = POSES[st.name] || POSES.idle, L = st.look; return { aLx: p.aL[0], aLz: p.aL[1], aRx: p.aR[0], aRz: p.aR[1], hx: p.head[0] + (L ? L[0] : 0), hy: p.head[1] + (L ? L[1] : 0), lean: p.lean }; }
  function pose(name, instant) { st.name = POSES[name] ? name : 'idle'; if (instant !== false && !st.ticked) { st.cur = target(); apply(); } return root; }
  function lookAt(v) {
    if (!v) { st.look = null; return; }
    root.updateWorldMatrix(true, false);
    const l = root.worldToLocal(v.clone ? v.clone() : new THREE.Vector3(v.x, v.y, v.z)), dy = l.y - HEAD_Y, d = Math.hypot(l.x, l.z) || 1e-6;
    st.look = [Math.max(-0.45, Math.min(0.45, -Math.atan2(dy, d))), Math.max(-1.0, Math.min(1.0, Math.atan2(l.x, l.z)))];
    if (!st.ticked) { st.cur = target(); apply(); }
  }
  function tick(dt, t) {
    st.ticked = true; st.t = t == null ? st.t + dt : t;
    const T = st.t + st.phase, a = 1 - Math.exp(-Math.min(0.1, Math.max(0, dt || 0.016)) * 9), tg = target(), c = st.cur, p = POSES[st.name] || POSES.idle, e = {};
    for (const key in tg) c[key] += (tg[key] - c[key]) * a;
    e.breathe = Math.sin(T * (st.name === 'slump' ? 1.3 : 2.1)) * 0.012;
    if (!st.look && !p.talk) e.hy = Math.sin(T * 0.5) * 0.16;
    if (p.wave) e.aRz = Math.sin(T * 7) * 0.32;
    if (p.talk) { e.hx = Math.sin(T * 5.2) * 0.05; e.aRx = Math.sin(T * 3.1) * 0.18; e.aLx = Math.sin(T * 2.6 + 1) * 0.12; }
    if (p.bounce) e.y = Math.abs(Math.sin(T * 6)) * 0.05;
    if (p.nod) e.hx = Math.max(0, Math.sin(T * 6)) * 0.3;
    if (p.shrug) e.y = 0.012;
    apply(e);
    const blink = ((T * 0.27) % 1) < 0.035; eyes.scale.y = blink ? 0.12 : 1; eyes.position.y = blink ? R * Math.sin(0.05) * 0.88 : 0;
    const open = p.talk ? 0.75 + Math.abs(Math.sin(T * 9)) * 0.9 : 1; mouth.scale.y = open; mouth.position.y = mouthY * (1 - open);
  }
  function dispose() { for (const g of geos) g.dispose(); if (root.parent) root.parent.remove(root); }
  root.userData = { spec: s, pose, lookAt, tick, dispose, parts: { torso, head, armL: pivL, armR: pivR, eyes, mouth }, meshes: 7, triangles: geos.reduce((n, g) => n + g.userData.triangles, 0), height: k * (HEAD_Y + R * 1.1), headY: k * HEAD_Y, lite };
  pose(s.mood === 'sheepish' ? 'slump' : 'idle');
  return root;
}

// ------------------------------------------------------------------------------------------------ crowds
const PROP = { hammer: '#8c867c', scroll: '#e9dfc9', pouch: '#9c6b3c', key: '#d9b25a', owl: '#9c6b3c', torch: '#e0b060' };
/** many people in few draw calls: one InstancedMesh per part, coloured per person. Faces are the shared dot-eyed smile; hair, helmets, laurels and one small prop differ. */
export function figureInstanced(THREE, specs, opts) {
  const o = opts || {}, lite = !!o.lite, seated = !!o.seated, n = specs.length, S0 = C.spec({ seed: 7 }, { build: 'slim', hairStyle: 'short', accessory: 'none', mood: 'calm', face: { eyes: 'dot', brows: 'flat', mouth: 'smile', beard: 'none', glasses: false, freckles: false } });
  S0.build = 'average';
  const at = (parts, x, y, z) => parts.map(([g, c, m]) => [g, c, new THREE.Matrix4().makeTranslation(x, y, z).multiply(m || new THREE.Matrix4())]);
  const ty = seated ? -0.02 : 0, armPose = (side) => { const q = new THREE.Matrix4().makeRotationZ(side * 0.2); return (parts) => parts.map(([g, c, m]) => [g, c, new THREE.Matrix4().makeTranslation(side * SHOULDER_X, SHOULDER_Y + ty, 0).multiply(q).multiply(m || new THREE.Matrix4())]); };
  const longS = { ...S0, hairStyle: 'long' }, bunS = { ...S0, hairStyle: 'bun' }, helmS = { ...S0, accessory: 'helmet' }, laurS = { ...S0, accessory: 'laurel' };
  const G = {
    skin: bake(THREE, at(headParts(THREE, S0, lite, true), 0, HEAD_Y + ty, 0).concat(armPose(-1)(armParts(THREE, S0, lite, -1, 'skin')), armPose(1)(armParts(THREE, S0, lite, 1, 'skin')), legParts(THREE, S0, lite, seated, 'skin'))),
    outfit: bake(THREE, at(bodyParts(THREE, S0, lite, true), 0, ty, 0).concat(armPose(-1)(armParts(THREE, S0, lite, -1, 'outfit')), armPose(1)(armParts(THREE, S0, lite, 1, 'outfit')))),
    trim: bake(THREE, at(trimParts(THREE, S0, lite, true), 0, ty, 0)),
    ink: bake(THREE, at(eyeParts(THREE, S0, lite).concat(mouthParts(THREE, S0, lite)), 0, HEAD_Y + ty, 0).map(([g, c, m]) => [g, c, m]).concat(legParts(THREE, S0, lite, seated, 'dark').map(([g, c, m]) => [g, SANDAL, m]))),
    hair: bake(THREE, at(hairParts(THREE, S0, lite, 'top'), 0, HEAD_Y + ty, 0)),
    back: bake(THREE, at(hairParts(THREE, longS, lite, 'back'), 0, HEAD_Y + ty, 0)),
    knot: bake(THREE, at(hairParts(THREE, bunS, lite, 'knot'), 0, HEAD_Y + ty, 0)),
    helmet: bake(THREE, at(headAccessory(THREE, helmS, lite, false), 0, HEAD_Y + ty, 0)),
    laurel: bake(THREE, at(headAccessory(THREE, laurS, lite, false), 0, HEAD_Y + ty, 0)),
    prop: bake(THREE, [[new THREE.IcosahedronGeometry(0.05, 0), null, M(THREE, SHOULDER_X + 0.07, SHOULDER_Y - 0.22 + ty, 0.07)]]),
    cheek: bake(THREE, [-1, 1].map((sx) => [new THREE.CircleGeometry(0.034, 6), TERRA, new THREE.Matrix4().makeTranslation(0, HEAD_Y + ty, 0).multiply(onHead(THREE, sx * 0.62, -0.2, 1.006))])),
  };
  const group = new THREE.Group(); group.name = 'people';
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0 });
  const cheekMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, metalness: 0, transparent: true, opacity: 0.4, depthWrite: false });
  const IM = {}, col = new THREE.Color();
  for (const k of Object.keys(G)) { const im = new THREE.InstancedMesh(G[k], k === 'cheek' ? cheekMat : mat, Math.max(1, n)); im.count = n; im.name = 'people-' + k; im.frustumCulled = false; IM[k] = im; group.add(im); }
  const uses = (s, k) => {
    const hs = s.accessory === 'helmet' ? 'none' : s.hairStyle;
    if (k === 'hair') return hs !== 'none' && hs !== 'bald'; if (k === 'back') return hs === 'long' || hs === 'bob'; if (k === 'knot') return hs === 'bun' || hs === 'topknot';
    if (k === 'helmet') return s.accessory === 'helmet'; if (k === 'laurel') return s.accessory === 'laurel'; if (k === 'prop') return !!PROP[s.accessory];
    return true;
  };
  const SP = specs.map((x) => spec(x)), slots = SP.map((s, i) => ({ x: 0, y: 0, z: 0, ry: 0, k: s.height || 1, active: false, phase: ((s.seed >>> 0) % 628) / 100 }));
  SP.forEach((s, i) => {
    IM.skin.setColorAt(i, col.set(s.skin)); IM.outfit.setColorAt(i, col.set(s.outfit)); IM.trim.setColorAt(i, col.set(s.accent)); IM.ink.setColorAt(i, col.set('#ffffff'));
    IM.hair.setColorAt(i, col.set(s.hair)); IM.back.setColorAt(i, col.set(s.hair)); IM.knot.setColorAt(i, col.set(s.hair)); IM.helmet.setColorAt(i, col.set('#ffffff')); IM.laurel.setColorAt(i, col.set('#ffffff'));
    IM.prop.setColorAt(i, col.set(PROP[s.accessory] || '#ffffff')); IM.cheek.setColorAt(i, col.set('#ffffff'));
  });
  for (const k in IM) if (IM[k].instanceColor) IM[k].instanceColor.needsUpdate = true;
  const m4 = new THREE.Matrix4(), zero = new THREE.Matrix4().makeScale(0, 0, 0), q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), sc = new THREE.Vector3();
  function write(i, dy, lean) {
    const sl = slots[i]; e.set(lean || 0, sl.ry, 0, 'YXZ'); q.setFromEuler(e); m4.compose(v.set(sl.x, sl.y + (dy || 0), sl.z), q, sc.setScalar(sl.k));
    for (const k in IM) IM[k].setMatrixAt(i, uses(SP[i], k) ? m4 : zero);
  }
  function flush() { for (const k in IM) { IM[k].instanceMatrix.needsUpdate = true; } }
  function place(i, x, y, z, ry, scale) { const sl = slots[i]; if (!sl) return; sl.x = x; sl.y = y; sl.z = z; sl.ry = ry || 0; sl.k = (scale || 1) * (SP[i].height || 1); write(i, 0, 0); flush(); for (const k in IM) IM[k].computeBoundingSphere && (IM[k].boundingSphere = null); }
  function setActive(i, on) { if (slots[i]) slots[i].active = !!on; }
  function tick(t) { for (let i = 0; i < n; i++) { const sl = slots[i], T = t + sl.phase; write(i, sl.active ? Math.abs(Math.sin(T * 5)) * 0.045 * sl.k : Math.sin(T * 2) * 0.004, sl.active ? Math.sin(T * 5) * 0.05 : SP[i].mood === 'sheepish' ? 0.14 : 0); } flush(); }
  function pick(raycaster) { let best = -1, d = Infinity; for (const k of ['outfit', 'skin']) { const hits = raycaster.intersectObject(IM[k], false); if (hits.length && hits[0].distance < d && hits[0].instanceId != null) { d = hits[0].distance; best = hits[0].instanceId; } } return best; }
  function headWorld(i, out) { const sl = slots[i], o2 = out || new THREE.Vector3(); o2.set(sl.x, sl.y + (HEAD_Y + R * 1.25) * sl.k, sl.z); return group.localToWorld(o2); }
  function dispose() { for (const k in G) G[k].dispose(); mat.dispose(); cheekMat.dispose(); if (group.parent) group.parent.remove(group); }
  for (let i = 0; i < n; i++) write(i, 0, 0);
  flush();
  group.userData = { count: n, specs: SP, place, setActive, tick, pick, headWorld, dispose, drawCalls: Object.keys(IM).length, triangles: Object.keys(G).reduce((a, k) => a + G[k].userData.triangles, 0) };
  return group;
}
