// PEOPLE OF OLYMPUS v3: builds tools/web_public/assets/people/cast.glb from the KayKit Adventurers 1.0 pack (CC0, Kay Lousberg, docs/ASSETS_LICENSES.md).
// Not run by the site or the tests: a one-off build step, kept so the asset can be rebuilt and checked. The raw pack is never committed.
//
//   mkdir -p <scratch>/build && cd <scratch>/build && npm i @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions meshoptimizer pngjs
//   for f in Knight Barbarian Mage Rogue Rogue_Hooded; do curl -so <scratch>/kk/$f.glb \
//     https://cdn.jsdelivr.net/gh/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0@main/addons/kaykit_character_pack_adventures/Characters/gltf/$f.glb; done
//   NODE_PATH=<scratch>/build/node_modules node tools/people_cast_build.mjs <scratch>/kk tools/web_public/assets/people/cast.glb
//
// What it does: one skeleton (the 24 joints that move the mesh: the pack's five characters share the same rig), every body part of the five characters
// as its own skinned mesh "P_<part>" with the pack's colour atlas baked into vertex colours (COLOR_0, no texture: smaller and recolourable) and a _SLOT
// attribute (what each vertex is: skin, hair, eye, brow, outfit, outfit2, accent, leather, metal, boots, linen, fixed) so every person gets their own colours
// at run time; the props (helmet, shield, cup, book) as rigid parts on their hand / head joint; 22 of the 76 animations (idle, walk, run, cheer, sit,
// interact, chop, cast...) without the IK helpers. Then meshopt geometry + quantised animation (EXT_meshopt_compression, KHR_mesh_quantization).
import { createRequire } from 'module';
const require = createRequire(process.env.NODE_PATH ? process.env.NODE_PATH + '/' : import.meta.url);
const { NodeIO, Document } = require('@gltf-transform/core');
const { ALL_EXTENSIONS } = require('@gltf-transform/extensions');
const { resample, prune, dedup, quantize, meshopt, weld } = require('@gltf-transform/functions');
const { MeshoptEncoder, MeshoptDecoder } = require('meshoptimizer');
const { PNG } = require('pngjs');

const [SRC, OUT] = process.argv.slice(2);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
await MeshoptEncoder.ready; await MeshoptDecoder.ready;

export const SLOTS = ['fixed', 'skin', 'hair', 'eye', 'brow', 'outfit', 'outfit2', 'accent', 'leather', 'metal', 'boots', 'linen'];
const S = Object.fromEntries(SLOTS.map((s, i) => [s, i]));
// atlas cell "col,row" -> slot, per source texture (the pack's atlas: 8 x 4 swatches of 128 x 256, a light-to-dark gradient in each)
const CELLS = {
  common: { '0,0': 'skin', '1,0': 'hair', '2,0': 'eye' },
  Knight: { '3,0': 'metal', '7,0': 'metal', '4,0': 'metal', '6,0': 'leather', '7,1': 'outfit2', '2,1': 'metal', '0,1': 'accent', '1,1': 'linen', '3,1': 'metal', '5,1': 'leather', '6,1': 'leather', '2,2': 'accent' },
  Mage: { '0,1': 'outfit', '7,1': 'outfit2', '5,0': 'accent', '3,0': 'metal', '4,0': 'metal', '2,2': 'leather', '0,2': 'linen', '3,2': 'boots', '7,2': 'skin', '1,1': 'accent', '2,1': 'accent', '1,2': 'accent', '5,1': 'leather', '3,1': 'metal' },
  Rogue: { '0,1': 'outfit', '1,1': 'accent', '5,0': 'leather', '6,0': 'leather', '5,2': 'skin', '3,0': 'metal', '7,1': 'outfit2', '3,2': 'boots' },
  Barbarian: { '0,1': 'outfit', '1,1': 'outfit', '6,0': 'leather', '2,1': 'linen', '7,1': 'outfit2', '7,0': 'leather', '3,0': 'metal', '3,2': 'boots', '7,2': 'leather', '5,1': 'fixed', '3,1': 'metal', '1,3': 'fixed', '4,1': 'leather', '0,2': 'linen', '2,2': 'accent', '6,1': 'leather' },
};
CELLS.Rogue_Hooded = CELLS.Rogue;
const KEEP_JOINTS = ['root', 'hips', 'spine', 'chest', 'upperarm.l', 'lowerarm.l', 'wrist.l', 'hand.l', 'handslot.l', 'upperarm.r', 'lowerarm.r', 'wrist.r', 'hand.r', 'handslot.r', 'head',
  'upperleg.l', 'lowerleg.l', 'foot.l', 'toes.l', 'upperleg.r', 'lowerleg.r', 'foot.r', 'toes.r'];
const CLIPS = ['Idle', 'Unarmed_Idle', 'Walking_A', 'Walking_B', 'Walking_C', 'Running_A', 'Cheer', 'Interact', 'PickUp', 'Use_Item', 'Sit_Chair_Idle', 'Sit_Chair_Down',
  'Sit_Chair_StandUp', 'Sit_Floor_Idle', '1H_Melee_Attack_Chop', '2H_Melee_Attack_Chop', 'Spellcasting', 'Spellcast_Raise', 'Hit_A', 'Jump_Full_Short', '1H_Ranged_Aiming', 'Throw'];
// parts: [out name, source file, source node, filter] (filter: which triangles of a head go where)
const PARTS = [
  ['face_a', 'Knight', 'Knight_Head', 'face'], ['hair_swept', 'Knight', 'Knight_Head', 'hair'],
  ['face_b', 'Mage', 'Mage_Head', 'face'], ['hair_bob', 'Mage', 'Mage_Head', 'hair'],
  ['face_c', 'Barbarian', 'Barbarian_Head', 'face'], ['beard', 'Barbarian', 'Barbarian_Head', 'hair'],
  ['hair_long', 'Rogue', 'Rogue_Head', 'hair'], ['earring', 'Rogue', 'Rogue_Head', 'earring'],
  ['hood', 'Rogue_Hooded', 'Rogue_Head_Hooded', 'hood'],
  ['body_armour', 'Knight', 'Knight_Body'], ['arms_armour', 'Knight', ['Knight_ArmLeft', 'Knight_ArmRight']], ['legs_armour', 'Knight', ['Knight_LegLeft', 'Knight_LegRight']],
  ['body_robe', 'Mage', 'Mage_Body'], ['arms_robe', 'Mage', ['Mage_ArmLeft', 'Mage_ArmRight']], ['legs_robe', 'Mage', ['Mage_LegLeft', 'Mage_LegRight']],
  ['body_tunic', 'Rogue', 'Rogue_Body'], ['arms_tunic', 'Rogue', ['Rogue_ArmLeft', 'Rogue_ArmRight']], ['legs_tunic', 'Rogue', ['Rogue_LegLeft', 'Rogue_LegRight']],
  ['body_apron', 'Barbarian', 'Barbarian_Body'], ['arms_apron', 'Barbarian', ['Barbarian_ArmLeft', 'Barbarian_ArmRight']], ['legs_apron', 'Barbarian', ['Barbarian_LegLeft', 'Barbarian_LegRight']],
  ['cape', 'Rogue', 'Rogue_Cape'], ['helmet', 'Knight', 'Knight_Helmet'], ['shield', 'Knight', 'Round_Shield'], ['cup', 'Barbarian', 'Mug'], ['book', 'Mage', 'Spellbook_open'],
];

const srgb2lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const docs = {}, pngs = {};
for (const f of ['Knight', 'Barbarian', 'Mage', 'Rogue', 'Rogue_Hooded']) { docs[f] = await io.read(`${SRC}/${f}.glb`); pngs[f] = PNG.sync.read(Buffer.from(docs[f].getRoot().listTextures()[0].getImage())); }
const base = docs.Knight, baseSkin = base.getRoot().listSkins()[0], baseJoints = baseSkin.listJoints(), ibm = baseSkin.getInverseBindMatrices().getArray();

// ---- the output document: the kept joints (same rest pose), one skin
const out = new Document(), buf = out.createBuffer(), scene = out.createScene('cast'), outRoot = out.getRoot();
const jmap = new Map(), jnodes = [];
function cloneJoint(src, parent) {
  const name = src.getName(); if (!KEEP_JOINTS.includes(name)) return;
  const n = out.createNode(name).setTranslation(src.getTranslation()).setRotation(src.getRotation()).setScale(src.getScale());
  jmap.set(name, n); if (parent) parent.addChild(n); else scene.addChild(n);
  for (const c of src.listChildren()) cloneJoint(c, n);
}
cloneJoint(baseJoints.find((j) => j.getName() === 'root'), null);
const skinIBM = new Float32Array(KEEP_JOINTS.length * 16);
KEEP_JOINTS.forEach((n, i) => { const k = baseJoints.findIndex((j) => j.getName() === n); skinIBM.set(ibm.slice(k * 16, k * 16 + 16), i * 16); jnodes.push(jmap.get(n)); });
const skin = out.createSkin('olympus').setSkeleton(jmap.get('root'));
jnodes.forEach((n) => skin.addJoint(n));
skin.setInverseBindMatrices(out.createAccessor().setType('MAT4').setArray(skinIBM).setBuffer(buf));
const oldToNew = baseJoints.map((j) => KEEP_JOINTS.indexOf(j.getName()));

// ---- helpers: world bind matrix of a source node (for the rigid props), matrix maths
const mul = (a, b) => { const o = new Array(16).fill(0); for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k]; return o; };
const trs = (t, q, s) => { const [x, y, z, w] = q, x2 = x + x, y2 = y + y, z2 = z + z, xx = x * x2, xy = x * y2, xz = x * z2, yy = y * y2, yz = y * z2, zz = z * z2, wx = w * x2, wy = w * y2, wz = w * z2;
  return [(1 - (yy + zz)) * s[0], (xy + wz) * s[0], (xz - wy) * s[0], 0, (xy - wz) * s[1], (1 - (xx + zz)) * s[1], (yz + wx) * s[1], 0, (xz + wy) * s[2], (yz - wx) * s[2], (1 - (xx + yy)) * s[2], 0, t[0], t[1], t[2], 1]; };
function world(doc, node) { const nodes = doc.getRoot().listNodes(); let m = trs(node.getTranslation(), node.getRotation(), node.getScale()), p = node; for (;;) { p = nodes.find((x) => x.listChildren().includes(p)); if (!p) return m; m = mul(trs(p.getTranslation(), p.getRotation(), p.getScale()), m); } }
const parentOf = (doc, node) => doc.getRoot().listNodes().find((x) => x.listChildren().includes(node));
const xf = (m, v, w) => [m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12] * w, m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13] * w, m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14] * w];

// ---- islands of a primitive (welded by position), to find the brows, the beard and the hair in a head
function islands(prim) {
  const pos = prim.getAttribute('POSITION'), ix = prim.getIndices().getArray(), n = pos.getCount();
  const par = new Int32Array(n).map((_, i) => i), find = (a) => { while (par[a] !== a) a = par[a] = par[par[a]]; return a; }, uni = (a, b) => { a = find(a); b = find(b); if (a !== b) par[a] = b; };
  const weld0 = new Map(); for (let i = 0; i < n; i++) { const k = pos.getElement(i, []).map((x) => x.toFixed(4)).join(','); if (weld0.has(k)) uni(i, weld0.get(k)); else weld0.set(k, i); }
  for (let t = 0; t < ix.length; t += 3) { uni(ix[t], ix[t + 1]); uni(ix[t], ix[t + 2]); }
  const size = new Map(); for (let i = 0; i < n; i++) { const r = find(i); size.set(r, (size.get(r) || 0) + 1); }
  return { of: (i) => find(i), size: (i) => size.get(find(i)) };
}

// ---- one part -> arrays
function extract(fileName, nodeNames, filter) {
  const doc = docs[fileName], png = pngs[fileName], table = { ...CELLS.common, ...CELLS[fileName] };
  const P = [], N = [], Cc = [], J = [], W = [], SL = [], I = [];
  for (const nn of [].concat(nodeNames)) {
    const node = doc.getRoot().listNodes().find((x) => x.getName() === nn); if (!node) throw new Error('no node ' + nn);
    const skinned = !!node.getSkin(), prim = node.getMesh().listPrimitives()[0];
    const pos = prim.getAttribute('POSITION'), nor = prim.getAttribute('NORMAL'), uv = prim.getAttribute('TEXCOORD_0'), ix = prim.getIndices().getArray(), n = pos.getCount();
    let M = null, joint = -1;
    if (!skinned) { M = world(doc, node); const par = parentOf(doc, node); joint = KEEP_JOINTS.indexOf(par.getName()); if (joint < 0) throw new Error('prop parent ' + par.getName()); }
    const isl = filter ? islands(prim) : null;
    const cellOf = (i) => { const [u, v] = uv.getElement(i, []); return Math.min(7, Math.floor(u * 8)) + ',' + Math.min(3, Math.floor(v * 4)); };
    const slotOf = (i) => {
      const c = cellOf(i); let s = table[c];
      if (s === 'hair' && isl && isl.size(i) <= 90) { const p = pos.getElement(i, []); if (p[2] > 0.2 && p[1] > 1.6) s = 'brow'; }
      if (!s) { console.warn('  unmapped cell', fileName, nn, c); s = 'fixed'; }
      return s;
    };
    const keepTri = (a, b, c) => {
      if (!filter) return true;
      const s = slotOf(a), cell = cellOf(a);
      if (filter === 'face') return s === 'skin' || s === 'eye' || s === 'brow';
      if (filter === 'hair') return s === 'hair' || (fileName === 'Mage' && cell === '1,1');
      if (filter === 'earring') return cell === '3,0';
      if (filter === 'hood') return cell === '1,1';
      return false;
    };
    const remap = new Map();
    const vert = (i) => {
      if (remap.has(i)) return remap.get(i);
      const k = P.length / 3; remap.set(i, k);
      let p = pos.getElement(i, []), q = nor.getElement(i, []);
      if (M) { p = xf(M, p, 1); q = xf(M, q, 0); const l = Math.hypot(...q) || 1; q = q.map((x) => x / l); }
      P.push(...p); N.push(...q);
      const [u, v] = uv.getElement(i, []), x = Math.min(png.width - 1, Math.max(0, Math.floor(u * png.width))), y = Math.min(png.height - 1, Math.max(0, Math.floor(v * png.height))), o = (y * png.width + x) * 4;
      Cc.push(srgb2lin(png.data[o]), srgb2lin(png.data[o + 1]), srgb2lin(png.data[o + 2]));
      if (skinned) {
        const jj = prim.getAttribute('JOINTS_0').getElement(i, []), ww = prim.getAttribute('WEIGHTS_0').getElement(i, []);
        const pairs = jj.map((j, t) => [oldToNew[j], ww[t]]).filter(([j, w]) => w > 0 && j >= 0).sort((a, b) => b[1] - a[1]).slice(0, 4);
        const sum = pairs.reduce((s, [, w]) => s + w, 0) || 1;
        for (let t = 0; t < 4; t++) { J.push(pairs[t] ? pairs[t][0] : 0); W.push(pairs[t] ? pairs[t][1] / sum : 0); }
      } else { J.push(joint, 0, 0, 0); W.push(1, 0, 0, 0); }
      SL.push(S[slotOf(i)]);
      return k;
    };
    for (let t = 0; t < ix.length; t += 3) if (keepTri(ix[t], ix[t + 1], ix[t + 2])) I.push(vert(ix[t]), vert(ix[t + 1]), vert(ix[t + 2]));
  }
  return { P, N, Cc, J, W, SL, I };
}

const meshes = [];
for (const [name, file, nodes, filter] of PARTS) {
  const d = extract(file, nodes, filter);
  if (!d.I.length) throw new Error('empty part ' + name);
  const acc = (type, arr) => out.createAccessor().setType(type).setArray(arr).setBuffer(buf);
  const prim = out.createPrimitive()
    .setAttribute('POSITION', acc('VEC3', new Float32Array(d.P))).setAttribute('NORMAL', acc('VEC3', new Float32Array(d.N)))
    .setAttribute('COLOR_0', acc('VEC3', new Float32Array(d.Cc))).setAttribute('JOINTS_0', acc('VEC4', new Uint8Array(d.J)))
    .setAttribute('WEIGHTS_0', acc('VEC4', new Float32Array(d.W))).setAttribute('_SLOT', acc('SCALAR', new Uint8Array(d.SL)))
    .setIndices(acc('SCALAR', d.P.length / 3 > 65535 ? new Uint32Array(d.I) : new Uint16Array(d.I)));
  const mesh = out.createMesh('P_' + name).addPrimitive(prim);
  scene.addChild(out.createNode('P_' + name).setMesh(mesh).setSkin(skin));
  meshes.push([name, d.P.length / 3, d.I.length / 3]);
}

// ---- animations: the kept clips, kept joints only, rotation everywhere + the hips' translation (no scale, no IK helpers)
for (const a of base.getRoot().listAnimations()) {
  if (!CLIPS.includes(a.getName())) continue;
  const na = out.createAnimation(a.getName());
  for (const ch of a.listChannels()) {
    const tn = ch.getTargetNode(), path = ch.getTargetPath(), name = tn && tn.getName();
    if (!jmap.has(name) || path === 'scale' || (path === 'translation' && name !== 'hips')) continue;
    const s = ch.getSampler();
    const ns = out.createAnimationSampler().setInterpolation(s.getInterpolation())
      .setInput(out.createAccessor().setType('SCALAR').setArray(new Float32Array(s.getInput().getArray())).setBuffer(buf))
      .setOutput(out.createAccessor().setType(s.getOutput().getType()).setArray(new Float32Array(s.getOutput().getArray())).setBuffer(buf));
    na.addSampler(ns).addChannel(out.createAnimationChannel().setTargetNode(jmap.get(name)).setTargetPath(path).setSampler(ns));
  }
}
const missing = CLIPS.filter((c) => !outRoot.listAnimations().some((a) => a.getName() === c)); if (missing.length) throw new Error('missing clips ' + missing);
outRoot.getAsset().generator = 'olympus people_cast_build.mjs (KayKit Adventurers 1.0, CC0)';
outRoot.setExtras({ olympus: { v: 3, slots: SLOTS, joints: KEEP_JOINTS, source: 'KayKit Character Pack: Adventurers 1.0 by Kay Lousberg (CC0)', parts: meshes.map((m) => m[0]) } });

await out.transform(resample({ tolerance: 1e-4 }), dedup(), prune({ keepAttributes: true, keepLeaves: true }),
  quantize({ pattern: /^(POSITION|NORMAL|COLOR_0|WEIGHTS_0)$/, quantizationVolume: 'scene', quantizePosition: 14, quantizeNormal: 8, quantizeColor: 8, quantizeWeight: 8 }),
  meshopt({ encoder: MeshoptEncoder, level: 'high' }));
await io.write(OUT, out);
const fs = await import('fs');
console.log(JSON.stringify({ out: OUT, bytes: fs.statSync(OUT).size, parts: meshes.length, verts: meshes.reduce((s, m) => s + m[1], 0), tris: meshes.reduce((s, m) => s + m[2], 0), clips: outRoot.listAnimations().length }));
for (const m of meshes) console.log('  ', m.join(' '));
