// OLYMPUS Mind: the nebula clouds. Each galaxy wears a few layered, slowly turning cloud sprites in its own colour (some
// puffs tinted toward a neighbouring hue for depth): camera-facing quads built in the vertex shader, wisps from a cloud atlas
// baked once at start (cloudAtlas). Clouds are soft and big, so they are drawn into their own buffer at a quarter of the
// screen's resolution (1/16 of the pixels: the overdraw costs nothing on a phone) and laid over the scene as one additive
// full-screen quad. A puff fades as the camera gets inside it and in the constellation view (uStar). Light mode: fewer puffs.
//   const neb = new Nebulae(THREE, uniforms); neb.quad -> THREE.Mesh (put it in the scene)
//   neb.build(clusters, colours, quality); neb.place(centres, normals); neb.emphasis(perCluster) (focus mode)
//   neb.resize(w, h); neb.render(renderer, camera)   once per frame, before the scene

const VS = `
attribute vec2 aCorner; attribute vec4 aPuff;          // puff: size, seed, alpha, cluster
attribute vec3 aColor;
uniform float uTime, uMotion;
varying vec2 vUv; varying vec3 vColor; varying float vA, vSeed;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float a = aPuff.y * 6.2832 + uTime * 0.025 * (aPuff.y - 0.5) * uMotion;
  vec2 c = mat2(cos(a), -sin(a), sin(a), cos(a)) * aCorner;
  mv.xy += c * aPuff.x;
  float depth = -mv.z;
  vA = aPuff.z * smoothstep(aPuff.x * 0.35, aPuff.x * 1.6, depth);
  vUv = aCorner; vColor = aColor; vSeed = aPuff.y;
  gl_Position = projectionMatrix * mv;
}`;

const FS = `
uniform sampler2D uCloud; uniform float uTime, uStar, uMotion;
varying vec2 vUv; varying vec3 vColor; varying float vA, vSeed;
void main() {
  float r = length(vUv);
  if (r > 1.0 || vA * (1.0 - uStar) < 0.003) discard;
  float cell = floor(vSeed * 4.0);
  vec2 uv = (vUv * 0.5 + 0.5) * 0.5 + vec2(mod(cell, 2.0), floor(cell / 2.0)) * 0.5;
  float d = texture2D(uCloud, uv).r;
  float breathe = 0.85 + 0.15 * sin(uTime * 0.21 * uMotion + vSeed * 31.0);
  vec3 col = mix(vColor * 0.5, vColor * 1.3 + 0.08, d * d);
  gl_FragColor = vec4(col, d * vA * breathe * (1.0 - uStar));
}`;

/** Four cloud shapes baked once into a 2 x 2 atlas (value-noise fbm with a domain warp, faded to nothing at each cell's rim):
 * the clouds then cost one texture read per pixel on any GPU. */
function cloudAtlas(THREE, size = 128) {
  const c = document.createElement('canvas');
  c.width = c.height = size * 2;
  const ctx = c.getContext('2d'), img = ctx.createImageData(size * 2, size * 2), D = img.data;
  const hash = (x, y, s) => { const h = Math.sin(x * 127.1 + y * 311.7 + s * 74.7) * 43758.5453; return h - Math.floor(h); };
  const noise = (x, y, s) => {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi, u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c2 = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
    return a + (b - a) * u + (c2 - a) * v + (a - b - c2 + d) * u * v;
  };
  const fbm = (x, y, s) => { let t = 0, amp = 0.5; for (let o = 0; o < 5; o++) { t += amp * noise(x, y, s); x = x * 2.03 + 3.1; y = y * 2.03 + 1.7; amp *= 0.5; } return t; };
  for (let cell = 0; cell < 4; cell++) {
    const ox = (cell % 2) * size, oy = Math.floor(cell / 2) * size, seed = cell * 13.7 + 1;
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const u = ((x + 0.5) / size) * 2 - 1, v = ((y + 0.5) / size) * 2 - 1, r = Math.hypot(u, v);
      let val = 0;
      if (r < 1) {
        const px = u * 2.2 + seed, py = v * 2.2 - seed;
        const w = fbm(px + 1.4 * fbm(px * 0.7, py * 0.7, seed), py + 1.4 * fbm(px * 0.7 + 5.2, py * 0.7 + 1.3, seed), seed);
        const body = Math.pow(1 - r, 1.6), wisps = Math.min(1, Math.max(0, (w - 0.3) / 0.5));
        val = Math.min(1, body * (0.22 + 1.15 * wisps * wisps));
      }
      const k = ((oy + y) * size * 2 + ox + x) * 4;
      D[k] = D[k + 1] = D[k + 2] = Math.round(val * 255); D[k + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.generateMipmaps = false; tex.minFilter = tex.magFilter = THREE.LinearFilter;
  return tex;
}

const COMPOSE_VS = `varying vec2 vUv; void main() { vUv = position.xy * 0.5 + 0.5; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const COMPOSE_FS = `uniform sampler2D uMap; uniform float uStar; varying vec2 vUv;
void main() { vec4 c = texture2D(uMap, vUv); gl_FragColor = vec4(c.rgb, 1.0) * (1.0 - uStar); }`;
const DOWNSCALE = 4;                                       // cloud buffer pixels per screen pixel, per axis

export class Nebulae {
  constructor(THREE, uniforms) {
    const T = THREE;
    this.T = THREE; this.u = uniforms; this.mesh = null; this.puffs = [];
    this.cloud = { value: null };
    this.scene = new T.Scene();
    this.rt = new T.WebGLRenderTarget(4, 4, { depthBuffer: false, stencilBuffer: false });
    this.map = { value: this.rt.texture };
    this.quad = new T.Mesh(new T.PlaneGeometry(2, 2), new T.ShaderMaterial({
      uniforms: { uMap: this.map, uStar: uniforms.uStar }, vertexShader: COMPOSE_VS, fragmentShader: COMPOSE_FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
    }));
    this.quad.frustumCulled = false;
    this._clear = new T.Color();
  }

  /** The cloud buffer follows the drawing buffer (in device pixels). */
  resize(w, h) { this.rt.setSize(Math.max(2, Math.round(w / DOWNSCALE)), Math.max(2, Math.round(h / DOWNSCALE))); }

  /** Draw the clouds into their small buffer (nothing to draw: the quad hides). */
  render(renderer, camera) {
    const on = !!this.mesh && this.u.uStar.value < 0.999;
    this.quad.visible = on;
    if (!on) return;
    renderer.getClearColor(this._clear);
    const alpha = renderer.getClearAlpha();
    renderer.setRenderTarget(this.rt);
    renderer.setClearColor(0x000000, 0);
    renderer.clear(true, false, false);
    renderer.render(this.scene, camera);
    renderer.setRenderTarget(null);
    renderer.setClearColor(this._clear, alpha);
  }

  /** New clouds for a graph's clusters (colours: THREE.Color per cluster). Returns the mesh (null: no clouds on this look). */
  build(clusters, colours, quality) {
    const T = this.T, lite = quality !== 'high';
    const per = (c) => (c.count < 3 || c.key === 'me' || c.key === 'memory' ? 0 : lite ? 2 : Math.min(8, 3 + Math.round(Math.log2(c.count))));
    if (this.mesh) { this.scene.remove(this.mesh); this.mesh.geometry.dispose(); this.mesh.material.dispose(); this.mesh = null; }
    this.puffs = [];
    clusters.forEach((c, k) => {
      let s = hash(c.key);
      const rnd = () => ((s = Math.imul(s ^ (s >>> 15), 2246822519) >>> 0) / 4294967296);
      for (let j = 0, m = per(c); j < m; j++) {
        const a = rnd() * Math.PI * 2, d = j === 0 ? 0 : 0.25 + rnd() * 0.65;
        const tint = colours[k].clone().offsetHSL(j % 3 === 2 ? 0.08 : j % 3 === 1 ? -0.05 : 0, j ? 0.05 : 0, j % 2 ? -0.06 : 0.02);
        this.puffs.push({ k, a, d, h: (rnd() - 0.5) * 0.25, size: (j === 0 ? 1.25 : 0.55 + rnd() * 0.6), seed: rnd(),
          alpha: (j === 0 ? 0.2 : 0.28 + rnd() * 0.16) * (lite ? 1.25 : 1), colour: tint });
      }
    });
    const P = this.puffs.length;
    if (!P) return (this.mesh = null);
    const pos = new Float32Array(P * 12), corner = new Float32Array(P * 8), puff = new Float32Array(P * 16), col = new Float32Array(P * 12);
    const idx = new Uint16Array(P * 6), C = [-1, -1, 1, -1, 1, 1, -1, 1];
    this.puffs.forEach((p, i) => {
      corner.set(C, i * 8);
      for (let v = 0; v < 4; v++) {
        puff.set([1, p.seed, p.alpha, p.k], (i * 4 + v) * 4);
        col.set([p.colour.r, p.colour.g, p.colour.b], (i * 4 + v) * 3);
      }
      idx.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3], i * 6);
    });
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(pos, 3).setUsage(T.DynamicDrawUsage));
    g.setAttribute('aCorner', new T.BufferAttribute(corner, 2));
    g.setAttribute('aPuff', new T.BufferAttribute(puff, 4).setUsage(T.DynamicDrawUsage));
    g.setAttribute('aColor', new T.BufferAttribute(col, 3));
    g.setIndex(new T.BufferAttribute(idx, 1));
    if (!this.cloud.value) this.cloud.value = cloudAtlas(T);
    const mat = new T.ShaderMaterial({
      uniforms: { ...this.u, uCloud: this.cloud }, vertexShader: VS, fragmentShader: FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
    });
    this.pos = pos; this.puff = puff; this.emph = new Float32Array(clusters.length).fill(1);
    this.mesh = new T.Mesh(g, mat);
    this.mesh.frustumCulled = false;
    this.scene.add(this.mesh);
    return this.mesh;
  }

  /** Seat every puff in its galaxy's disc (centres: [{x, y, z, r}] per cluster; normals: 3 floats per cluster). */
  place(centres, normals) {
    if (!this.mesh) return;
    const v = new this.T.Vector3(), u = new this.T.Vector3(), w = new this.T.Vector3(), nrm = new this.T.Vector3();
    this.puffs.forEach((p, i) => {
      const c = centres[p.k];
      if (!c) return;
      const r = Math.max(24, c.r * 1.15);
      nrm.set(normals[p.k * 3], normals[p.k * 3 + 1], normals[p.k * 3 + 2]);
      u.set(1, 0, 0).cross(nrm).normalize();
      w.copy(nrm).cross(u);
      v.set(c.x, c.y, c.z).addScaledVector(u, Math.cos(p.a) * p.d * r).addScaledVector(w, Math.sin(p.a) * p.d * r).addScaledVector(nrm, p.h * r);
      for (let q = 0; q < 4; q++) { this.pos.set([v.x, v.y, v.z], (i * 4 + q) * 3); this.puff[(i * 4 + q) * 4] = p.size * r; }
      this._alpha(p, i);
    });
    this.mesh.geometry.attributes.position.needsUpdate = true;
    this.mesh.geometry.attributes.aPuff.needsUpdate = true;
  }

  /** Focus mode: the per-cluster brightness (1 = as built, ~0 = gone). */
  emphasis(perCluster) {
    if (!this.mesh) return;
    this.emph = Float32Array.from(perCluster);
    this.puffs.forEach((p, i) => this._alpha(p, i));
    this.mesh.geometry.attributes.aPuff.needsUpdate = true;
  }

  _alpha(p, i) {
    const a = p.alpha * (this.emph[p.k] ?? 1);
    for (let q = 0; q < 4; q++) this.puff[(i * 4 + q) * 4 + 2] = a;
  }
}

function hash(s) {
  let h = 2166136261;
  for (let k = 0; k < s.length; k++) h = Math.imul(h ^ s.charCodeAt(k), 16777619);
  return h >>> 0;
}
