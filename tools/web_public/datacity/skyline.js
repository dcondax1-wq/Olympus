// The Data City's buildings, built to scale to 25-40k: one InstancedMesh per tile (TILE x TILE blocks of one district,
// frustum-culled by three.js with its bounding sphere), its wet-street reflection when near, and far away one impostor per
// block (a 3 x 3 cluster of towers with the block's heights, all blocks in ONE instanced draw). Monuments and ships are
// "landmarks", always drawn in full. Per-building state (search dim, the Today layer, watch / selected) lives in instanced
// attributes, written only when it changes, never per frame.
import * as THREE from '../jarvis/three.module.min.js';
import * as SH from './shaders.js';

export const LOD = { hq: 200, lq: 125 };        // a tile nearer than this (to its edge) draws every building
const MIRROR_NEAR = { hq: 120, lq: 0 };        // and its reflection when nearer than this (HQ only)
const golden = (i) => (i * 0.6180339) % 1;

function shared(geo) {
  const g = new THREE.BufferGeometry();
  g.setIndex(geo.index);
  for (const k of ['position', 'normal', 'uv']) g.setAttribute(k, geo.getAttribute(k));
  g.boundingBox = geo.boundingBox; g.boundingSphere = geo.boundingSphere;
  return g;
}

/** Nine thin boxes in a unit square, each vertex tagged with its box (aSub): the impostor of one block. */
function clusterGeo() {
  const pos = [], nor = [], uv = [], sub = [], idx = [];
  for (let i = 0; i < 9; i++) {
    const g = new THREE.BoxGeometry(0.29, 1, 0.29);
    g.translate(-0.333 + (i % 3) * 0.333, 0.5, -0.333 + Math.floor(i / 3) * 0.333);
    const base = pos.length / 3;
    pos.push(...g.attributes.position.array); nor.push(...g.attributes.normal.array); uv.push(...g.attributes.uv.array);
    for (let k = 0; k < g.attributes.position.count; k++) sub.push(i);
    for (const k of g.index.array) idx.push(base + k);
    g.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  out.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  out.setAttribute('aSub', new THREE.Float32BufferAttribute(sub, 1));
  out.setIndex(idx);
  out.computeBoundingBox(); out.computeBoundingSphere();
  return out;
}

export class Skyline {
  /** L: layout(); U: the scene's shared uniforms; quality 'hq' | 'lq' */
  constructor(L, U, quality) {
    this.L = L; this.U = U; this.quality = quality;
    this.group = new THREE.Group();
    const box = new THREE.BoxGeometry(1, 1, 1);
    box.translate(0, 0.5, 0);
    box.computeBoundingBox(); box.computeBoundingSphere();
    this.box = box;
    const mat = (mirror) => new THREE.ShaderMaterial({ vertexShader: SH.BUILD_VS, fragmentShader: SH.BUILD_FS,
      uniforms: { ...pick(U, 'uTime', 'uFog', 'uFogD', 'uHaze', 'uDay', 'uToday', 'uWet', 'uGrow'), uMirror: { value: mirror ? 1 : 0 } },
      ...(mirror ? { transparent: true, depthWrite: false, side: THREE.DoubleSide } : {}) });
    this.mat = mat(false); this.mirrorMat = mat(true);
    this.where = new Int32Array(L.items.length * 2).fill(-1);       // item -> [mesh index, local index]
    this.meshes = [];
    const landmarks = [];
    L.items.forEach((it, i) => { if (it.tile < 0) landmarks.push(i); });
    this.tiles = L.tiles.map((t) => this._mesh(t.items, t));
    this.landmarks = landmarks.length ? this._mesh(landmarks, null) : null;
    this._impostors();
    this.lodDirty = true;
  }

  _mesh(list, tile) {
    const L = this.L, n = list.length, g = shared(this.box);
    const aColor = new Float32Array(n * 3), aData = new Float32Array(n * 4), aState = new Float32Array(n * 4), aSeed = new Float32Array(n);
    const m4 = new THREE.Matrix4(), col = new THREE.Color();
    const mesh = new THREE.InstancedMesh(g, this.mat, n);
    list.forEach((i, k) => {
      const it = L.items[i];
      m4.makeScale(it.kind === 'ship' ? 0.9 : it.w, it.h, it.w).setPosition(it.x, 0, it.z);
      mesh.setMatrixAt(k, m4);
      col.setHex(it.color);
      aColor.set([col.r, col.g, col.b], k * 3);
      aData.set([it.h, it.lit, it.pulse, 0], k * 4);
      aSeed[k] = golden(i);
      this.where[i * 2] = this.meshes.length; this.where[i * 2 + 1] = k;
    });
    g.setAttribute('aColor', new THREE.InstancedBufferAttribute(aColor, 3));
    g.setAttribute('aData', new THREE.InstancedBufferAttribute(aData, 4));
    g.setAttribute('aState', new THREE.InstancedBufferAttribute(aState, 4));
    g.setAttribute('aSeed', new THREE.InstancedBufferAttribute(aSeed, 1));
    mesh.computeBoundingSphere();
    mesh.renderOrder = 2;
    const mirror = new THREE.InstancedMesh(g, this.mirrorMat, n);
    mirror.instanceMatrix = mesh.instanceMatrix;
    mirror.frustumCulled = false;
    mirror.visible = false;
    mirror.renderOrder = 1;
    const rec = { mesh, mirror, list, tile, detail: true, near: false };
    mesh.userData.rec = this.meshes.length;
    this.meshes.push(rec);
    this.group.add(mesh, mirror);
    return rec;
  }

  _impostors() {
    const L = this.L, B = L.blocks, n = B.length;
    if (!n) { this.imp = null; return; }
    const geo = clusterGeo();
    const ha = new Float32Array(n * 4), hb = new Float32Array(n * 4), hc = new Float32Array(n), color = new Float32Array(n * 3);
    this.impMeta = new Float32Array(n * 4);
    const m4 = new THREE.Matrix4(), c = new THREE.Color();
    this.imp = new THREE.InstancedMesh(geo, new THREE.ShaderMaterial({ vertexShader: SH.IMP_VS, fragmentShader: SH.IMP_FS,
      uniforms: pick(this.U, 'uTime', 'uFog', 'uFogD', 'uHaze', 'uDay', 'uToday', 'uGrow') }), n);
    B.forEach((b, k) => {
      const hs = new Array(9).fill(0.05), w = Math.max(1e-6, b.x1 - b.x0), d = Math.max(1e-6, b.z1 - b.z0);
      let r = 0, g = 0, bl = 0, wt = 0, lit = 0;
      for (const i of b.items) {
        const it = L.items[i];
        const sx = Math.min(2, Math.floor((3 * (it.x - b.x0)) / w)), sz = Math.min(2, Math.floor((3 * (it.z - b.z0)) / d));
        hs[sz * 3 + sx] = Math.max(hs[sz * 3 + sx], it.h);
        c.setHex(it.color);
        const q = it.h * it.h;
        r += c.r * q; g += c.g * q; bl += c.b * q; wt += q; lit += it.lit;
      }
      ha.set(hs.slice(0, 4), k * 4); hb.set(hs.slice(4, 8), k * 4); hc[k] = hs[8];
      color.set([r / wt, g / wt, bl / wt], k * 3);
      this.impMeta.set([lit / b.items.length, 0, 0, 0], k * 4);
      m4.makeScale(w + 0.4, 1, d + 0.4).setPosition((b.x0 + b.x1) / 2, 0, (b.z0 + b.z1) / 2);
      this.imp.setMatrixAt(k, m4);
    });
    geo.setAttribute('aHa', new THREE.InstancedBufferAttribute(ha, 4));
    geo.setAttribute('aHb', new THREE.InstancedBufferAttribute(hb, 4));
    geo.setAttribute('aHc', new THREE.InstancedBufferAttribute(hc, 1));
    geo.setAttribute('aColor', new THREE.InstancedBufferAttribute(color, 3));
    this.impAttr = new THREE.InstancedBufferAttribute(this.impMeta, 4);
    geo.setAttribute('aMeta', this.impAttr);
    this.imp.frustumCulled = false;                 // one draw for the whole far city
    this.imp.renderOrder = 2;
    this.group.add(this.imp);
  }

  setQuality(q) { this.quality = q; this.lodDirty = true; }

  /** LOD: each tile in full near the camera, as impostor blocks far away. Cheap: ~100 distance tests a frame. */
  update(camera) {
    const p = camera.position, lod = LOD[this.quality], near = MIRROR_NEAR[this.quality];
    let changed = this.lodDirty;
    for (const rec of this.tiles) {
      const t = rec.tile, dist = Math.hypot(p.x - t.cx, p.y - t.hmax * 0.4, p.z - t.cz) - t.r;
      const detail = dist < lod;
      if (detail !== rec.detail || this.lodDirty) {
        rec.detail = detail;
        rec.mesh.visible = detail;
        for (const b of t.blocks) this.impMeta[b * 4 + 3] = detail ? 0 : 1;
        changed = true;
      }
      rec.mirror.visible = detail && dist < near;
    }
    if (this.landmarks) this.landmarks.mirror.visible = near > 0;
    if (changed && this.imp) this.impAttr.needsUpdate = true;
    this.lodDirty = false;
  }

  /** Per-building state: dim(i) (search), today(i) 0 / 1 armed / 2 fired, mark(i) 0 / 1 watched / 2 selected. */
  apply(dim, today, mark) {
    const L = this.L, agg = this.imp ? new Float32Array(L.blocks.length * 3) : null;      // block: today max, dim count
    for (const rec of this.meshes) {
      const data = rec.mesh.geometry.getAttribute('aData'), st = rec.mesh.geometry.getAttribute('aState');
      rec.list.forEach((i, k) => {
        const dm = dim ? (dim(i) ? 1 : 0) : 0, td = today(i), mk = mark(i);
        data.array[k * 4 + 3] = dm;
        st.array[k * 4] = td; st.array[k * 4 + 1] = mk;
        const b = L.items[i].block;
        if (agg && b >= 0) { agg[b * 3] = Math.max(agg[b * 3], td); agg[b * 3 + 1] += dm; agg[b * 3 + 2]++; }
      });
      data.needsUpdate = true; st.needsUpdate = true;
    }
    if (agg) {
      for (let b = 0; b < L.blocks.length; b++) {
        this.impMeta[b * 4 + 1] = agg[b * 3];
        this.impMeta[b * 4 + 2] = agg[b * 3 + 2] && agg[b * 3 + 1] === agg[b * 3 + 2] ? 1 : 0;
      }
      this.impAttr.needsUpdate = true;
    }
  }

  /** The building (or far block) under a ray: { item } / { block } / null. */
  pick(ray) {
    const vis = this.meshes.filter((r) => r.mesh.visible).map((r) => r.mesh);
    const hit = ray.intersectObjects(vis, false)[0];
    let best = hit ? { item: this.meshes[hit.object.userData.rec].list[hit.instanceId], distance: hit.distance } : null;
    if (this.imp) {
      for (const h of ray.intersectObject(this.imp, false)) {
        if (this.impMeta[h.instanceId * 4 + 3] < 0.5) continue;          // that block is drawn in full right now
        if (!best || h.distance < best.distance) best = { block: h.instanceId, distance: h.distance };
        break;
      }
    }
    return best;
  }

  /** What the camera sees now: tiles in full, impostor blocks shown (for the HUD and the tests). */
  info() {
    const full = this.tiles.filter((r) => r.detail).length;
    let blocks = 0;
    if (this.imp) for (let b = 0; b < this.L.blocks.length; b++) blocks += this.impMeta[b * 4 + 3] > 0.5 ? 1 : 0;
    return { tiles: this.tiles.length, tilesFull: full, blocks: this.L.blocks.length, impostors: blocks,
             mirrors: this.meshes.filter((r) => r.mirror.visible).length };
  }
}

export function pick(U, ...names) { return Object.fromEntries(names.map((n) => [n, U[n]])); }
