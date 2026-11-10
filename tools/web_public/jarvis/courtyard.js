// The OLYMPUS courtyard (2026-11-10, AGORA): a small marble forecourt in the Jarvis home scene. Five doorways stand in a shallow arc, one for each
// district of the Atlas map (Market, Research, Money, Command, Life), each a marble frame with a soft warm light inside it; a paved floor and
// four short columns around them. Added by home3d.js to THAT scene (no renderer, composer or render target of its own: the GPU guard stays true).
//
//   attach(ext, home)   builds it and returns { doors, count, draws, lite }; also stored as ext.state.home.courtyard
//   DISTRICTS           the five districts and their soft tints (the same order and names as Atlas and the orb's ring menu)
//
// Cost: instanced meshes only (frames, lintels, lights, paving, columns: at most 6 draw calls). LITE (data-fx low / software GL): frames and lights only.
// Off / reduced motion: still (no per-frame work). Light is warm (about 3000 K) and additive at low strength: nothing here reaches the bloom threshold (0.9).
// iPhone Safari 16: plain ES2020, no optional chaining.

export const DISTRICTS = [
  { id: 'market', name: 'Market', tint: '#d9b25a' },
  { id: 'research', name: 'Research', tint: '#7fa3b8' },
  { id: 'money', name: 'Money', tint: '#a3ad6a' },
  { id: 'command', name: 'Command', tint: '#c98a6a' },
  { id: 'life', name: 'Life', tint: '#e0b060' },
];

export function attach(ext, home) {
  const T = ext.T, M = ext.M, scene = ext.scene, root = ext.root;
  const lite = !!(home && home.soft) || root.dataset.fx === 'low' || root.dataset.fx === 'off';
  const FLOOR_Y = -2.6, Z = -9, N = DISTRICTS.length;
  const moving = () => root.dataset.fx !== 'off' && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  const marble = M && typeof M.marble === 'function' ? M.marble({ color: '#efe6d4', vein: '#8a7a60', scale: 0.6 }) : new T.MeshStandardMaterial({ color: '#e6dccb', roughness: 0.5 });
  const gold = M && typeof M.metal === 'function' ? M.metal({ kind: 'gold', roughness: 0.3 }) : new T.MeshStandardMaterial({ color: '#c8a24a', metalness: 0.8, roughness: 0.35 });
  const group = new T.Group(); group.name = 'courtyard'; scene.add(group);
  const at = new T.Object3D(), warm = new T.Color('#ffd9a0'), tmp = new T.Color();
  const W = 1.25, H = 2.7, SP = 1.85;                  // a doorway: opening width and height, the spacing between doorways
  const xs = []; for (let i = 0; i < N; i++) xs.push((i - (N - 1) / 2) * SP);
  const zOf = (i) => Z - Math.abs(i - (N - 1) / 2) * 0.25;   // the outer doorways stand a little farther back: a shallow arc
  let draws = 0;
  const inst = (geo, mat, n, order) => { const m = new T.InstancedMesh(geo, mat, n); m.frustumCulled = false; if (order != null) m.renderOrder = order; group.add(m); draws++; return m; };

  // jambs (two per doorway) and the lintel with its gold fillet
  const jambs = inst(new T.BoxGeometry(0.24, H, 0.4), marble, N * 2);
  const lintels = inst(new T.BoxGeometry(W + 0.74, 0.3, 0.46), marble, N);
  const fillets = inst(new T.BoxGeometry(W + 0.5, 0.06, 0.5), gold, N);
  for (let i = 0; i < N; i++) {
    const x = xs[i], z = zOf(i);
    at.rotation.set(0, 0, 0); at.scale.set(1, 1, 1);
    at.position.set(x - (W / 2 + 0.12), FLOOR_Y + H / 2, z); at.updateMatrix(); jambs.setMatrixAt(i * 2, at.matrix);
    at.position.set(x + (W / 2 + 0.12), FLOOR_Y + H / 2, z); at.updateMatrix(); jambs.setMatrixAt(i * 2 + 1, at.matrix);
    at.position.set(x, FLOOR_Y + H + 0.15, z); at.updateMatrix(); lintels.setMatrixAt(i, at.matrix);
    at.position.set(x, FLOOR_Y + H + 0.33, z); at.updateMatrix(); fillets.setMatrixAt(i, at.matrix);
  }
  // the light inside each doorway: a soft warm panel that is brightest low and fades upward, tinted a little by the district (mostly warm white)
  const lightMat = new T.ShaderMaterial({
    uniforms: { uI: { value: 0.16 } }, transparent: true, depthWrite: false, blending: T.AdditiveBlending, fog: false,
    vertexShader: 'attribute vec3 iCol; varying vec2 vU; varying vec3 vC; void main(){ vU = uv; vC = iCol; gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform float uI; varying vec2 vU; varying vec3 vC; void main(){ float x = abs(vU.x - 0.5) * 2.0; float a = (1.0 - pow(x, 3.0)) * (0.35 + 0.65 * pow(1.0 - vU.y, 1.4)); gl_FragColor = vec4(vC * a * uI, 1.0); }',
  });
  const lights = inst(new T.PlaneGeometry(W, H), lightMat, N, 5);
  const iCol = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    tmp.set(DISTRICTS[i].tint).lerp(warm, 0.55); iCol.set([tmp.r, tmp.g, tmp.b], i * 3);
    at.position.set(xs[i], FLOOR_Y + H / 2, zOf(i) - 0.05); at.updateMatrix(); lights.setMatrixAt(i, at.matrix);
  }
  lights.geometry.setAttribute('iCol', new T.InstancedBufferAttribute(iCol, 3));

  // the paving and the four short columns: skipped in LITE
  if (!lite) {
    const COLS = 9, ROWS = 3, slabs = inst(new T.BoxGeometry(1.4, 0.05, 1.4), marble, COLS * ROWS);
    let k = 0;
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
      at.position.set((c - (COLS - 1) / 2) * 1.46, FLOOR_Y + 0.03, Z + 1.2 - r * 1.46); at.updateMatrix(); slabs.setMatrixAt(k, at.matrix);
      tmp.set('#e8dec9').multiplyScalar(0.82 + 0.18 * (((c * 7 + r * 13) % 5) / 4)); slabs.setColorAt(k, tmp); k++;
    }
    slabs.instanceColor.needsUpdate = true;
    const colGeo = new T.CylinderGeometry(0.26, 0.3, 4.2, 20, 1), capGeo = new T.BoxGeometry(0.8, 0.2, 0.8);
    const cols = inst(colGeo, marble, 4), caps = inst(capGeo, gold, 4);
    [[-4.4, Z + 1.6], [4.4, Z + 1.6], [-4.9, Z - 1.4], [4.9, Z - 1.4]].forEach((p, i) => {
      at.position.set(p[0], FLOOR_Y + 2.1, p[1]); at.updateMatrix(); cols.setMatrixAt(i, at.matrix);
      at.position.set(p[0], FLOOR_Y + 4.3, p[1]); at.updateMatrix(); caps.setMatrixAt(i, at.matrix);
    });
  }
  for (const m of [jambs, lintels, fillets, lights]) m.instanceMatrix.needsUpdate = true;

  // slow breathing of the doorway light (0.9 to 1.0 of its strength): still when motion is off
  let t0 = 0;
  const hook = (dt, t) => { if (!moving()) { lightMat.uniforms.uI.value = 0.16; return; } t0 = t; lightMat.uniforms.uI.value = 0.16 * (0.95 + 0.05 * Math.sin(t0 * 0.35)); };
  ext.onStep.push(hook);
  const out = { doors: DISTRICTS.map((d, i) => ({ id: d.id, name: d.name, x: xs[i] })), count: N, draws, lite, group };
  if (home) home.courtyard = out;
  return out;
}
