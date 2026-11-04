// OLYMPUS Mind: the renderer (three.js r160, from ../jarvis/). One draw call per layer (the haze: one per galaxy):
//   stars       a twinkling shell far away
//   nebulae     layered cloud sprites per galaxy (nebula.js; light mode: two per galaxy)
//   haze        per galaxy a faint spiral disc in the cluster's plane (high quality only)
//   memory      Jarvis's memory ring around Me (memring.js)
//   filaments   every link as a thin additive line, coloured from end to end
//   flow        particles running along the links (none under reduced motion)
//   nodes       glowing spheres (point sprites with a lit core and a halo) sized by words and links
//   synapses    pulses along the links when a note opens or learns, and idle "thinking" (synapse.js)
//   sparks      "Jarvis learned" comets that fly from the ticker to their note; bursts are the rings when a note ignites
// Two views, eased into each other (uStar): galaxy (spheres, nebulae, flow) and constellation (crisp stars and bright lines).
// Positions come from the layout as targets; what is drawn eases toward them, so new notes fly in from the edge.
//   const b = new Brain(THREE, canvas, {quality, reduced}); b.setGraph(graph, {targets, start, normals}); b.setTargets(pos)
//   b.frame(dt, seconds, rig); b.setLook(emph, show, clusterEmph); b.ignite(i); b.spark(i); b.synapse(i); b.shiftTo(dx, dy)
//   b.setView('galaxy' | 'stars'); b.setBackground(colour)
//   b.pick(x, y) -> index | -1; b.screenOf(point); b.nodePoint(i); b.edgePoint(targets, i); b.centres (per cluster); b.ringInfo
import { Nebulae } from './nebula.js';
import { Synapses, SYNAPSE_VS } from './synapse.js';
import { MemoryRing, RING_COLOUR } from './memring.js';

const GLSL_FOG = `
uniform float uFogNear, uFogFar;
float fogOf(float d) { return mix(0.16, 1.0, smoothstep(uFogFar, uFogNear, d)); }`;

const NODE_VS = `
attribute vec3 aColor; attribute float aSize; attribute vec4 aFx;   // fx: ignite time, pulse, emphasis, shown
uniform float uTime, uScale, uMotion, uStar;
varying vec3 vColor; varying float vAlpha, vFlash, vFocus;
${GLSL_FOG}
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float dist = max(1.0, -mv.z);
  float age = uTime - aFx.x;
  float flash = (age >= 0.0 && age < 3.5) ? exp(-age * 1.5) : 0.0;
  float pulse = aFx.y * (0.5 + 0.5 * sin(uTime * 2.6 * uMotion + position.x * 0.05 + position.z * 0.03));
  float size = aSize * (0.8 + 0.2 * min(aFx.z, 1.6) + 0.5 * pulse + 2.0 * flash) * aFx.w * (1.0 + 0.35 * uStar);
  gl_PointSize = clamp(size * uScale / dist, 0.0, 420.0);
  vAlpha = fogOf(dist) * clamp(aFx.z, 0.0, 1.0) * aFx.w;
  vFlash = flash + 0.4 * pulse;
  vFocus = clamp(aFx.z - 1.0, 0.0, 1.0);
  vColor = aColor;
  gl_Position = projectionMatrix * mv;
}`;

const NODE_FS = `
uniform float uStar;
varying vec3 vColor; varying float vAlpha, vFlash, vFocus;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float r = length(p);
  if (r > 1.0 || vAlpha < 0.003) discard;
  const float R = 0.38;
  vec2 q = p / R;
  float z = sqrt(max(0.0, 1.0 - dot(q, q)));
  float core = smoothstep(R, R - 0.05, r);
  vec3 n = vec3(q, z), L = normalize(vec3(-0.45, 0.55, 0.7));
  float diff = max(0.0, dot(n, L));
  float spec = pow(max(0.0, reflect(-L, n).z), 22.0);
  vec3 sphere = vColor * (0.3 + 0.9 * diff) + vec3(spec * 0.9) + vColor * pow(1.0 - z, 2.0) * 0.8;
  float halo = (exp(-r * r * 7.0) * 0.5 + exp(-r * r * 26.0) * 0.4) * (1.0 + 2.4 * vFlash + 0.6 * vFocus);
  float ring = vFocus * smoothstep(0.05, 0.0, abs(r - 0.6));
  vec3 col = sphere * core + (vColor * halo + vec3(ring)) * (1.0 - core) + vec3(vFlash * 0.7) * core;
  float a = core + (halo + ring) * (1.0 - core);
  // the constellation view: a crisp star with four diffraction spikes
  float spikes = max(exp(-abs(p.x) * 26.0), exp(-abs(p.y) * 26.0)) * (1.0 - r) * 0.9;
  float star = (exp(-r * r * 60.0) * 1.6 + exp(-r * r * 9.0) * 0.25 + spikes) * (1.0 + 1.5 * vFlash + 0.8 * vFocus);
  col = mix(col, mix(vColor, vec3(1.0), 0.35) * star + vec3(ring) * 0.8, uStar);
  a = mix(a, min(1.0, star + ring), uStar);
  gl_FragColor = vec4(col, a * vAlpha);
}`;

const EDGE_VS = `
attribute vec3 aColor; attribute float aAlpha;
varying vec3 vColor; varying float vA;
${GLSL_FOG}
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vA = aAlpha * fogOf(-mv.z);
  vColor = aColor;
  gl_Position = projectionMatrix * mv;
}`;
const EDGE_FS = `uniform float uStar; varying vec3 vColor; varying float vA;
void main() { gl_FragColor = vec4(mix(vColor, vec3(0.8, 0.9, 1.0), uStar * 0.5), vA * (1.0 + 1.3 * uStar)); }`;

const FLOW_VS = `
attribute vec3 aB, aColor; attribute vec2 aSeed; attribute float aAlpha;
uniform float uTime, uScale, uStar;
varying vec3 vColor; varying float vA;
${GLSL_FOG}
void main() {
  float t = fract(aSeed.x + uTime * aSeed.y);
  vec4 mv = modelViewMatrix * vec4(mix(position, aB, t), 1.0);
  float dist = max(1.0, -mv.z);
  gl_PointSize = clamp(2.6 * uScale / dist, 1.5, 12.0);
  vA = aAlpha * sin(3.14159 * t) * fogOf(dist) * (1.0 - uStar);
  vColor = aColor;
  gl_Position = projectionMatrix * mv;
}`;
const GLOW_FS = `
varying vec3 vColor; varying float vA;
void main() { vec2 p = gl_PointCoord * 2.0 - 1.0; float r2 = dot(p, p); if (r2 > 1.0) discard;
  gl_FragColor = vec4(vColor * 1.3 + exp(-r2 * 12.0) * 0.5, exp(-r2 * 4.5) * vA); }`;

const STAR_VS = `
attribute float aSize, aSeed; attribute vec3 aColor;
uniform float uTime, uDpr, uMotion;
varying vec3 vColor; varying float vA;
void main() {
  vA = 0.55 + 0.45 * sin(uTime * (0.4 + aSeed) * uMotion + aSeed * 40.0);
  vColor = aColor;
  gl_PointSize = aSize * uDpr;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const STAR_FS = `
varying vec3 vColor; varying float vA;
void main() { vec2 p = gl_PointCoord * 2.0 - 1.0; float r2 = dot(p, p); if (r2 > 1.0) discard; gl_FragColor = vec4(vColor, exp(-r2 * 4.0) * vA); }`;

const SPARK_VS = `
attribute float aSize, aAlpha;
uniform float uScale; uniform vec3 uColor;
varying vec3 vColor; varying float vA;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = clamp(aSize * uScale / max(1.0, -mv.z), 2.0, 90.0) * step(0.001, aAlpha);
  vA = aAlpha; vColor = uColor;
  gl_Position = projectionMatrix * mv;
}`;

const BURST_VS = `
attribute float aT0, aSize; attribute vec3 aColor;
uniform float uTime, uScale;
varying vec3 vColor; varying float vA, vR;
void main() {
  float age = uTime - aT0;
  float live = step(0.0, age) * step(age, 1.6);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = clamp(aSize * (1.0 + age * 2.2) * uScale / max(1.0, -mv.z), 0.0, 320.0) * live;
  vA = (1.0 - age / 1.6) * live; vR = age; vColor = aColor;
  gl_Position = projectionMatrix * mv;
}`;
const BURST_FS = `
varying vec3 vColor; varying float vA, vR;
void main() { float r = length(gl_PointCoord * 2.0 - 1.0); if (r > 1.0) discard;
  float ring = smoothstep(0.78, 0.92, r) * smoothstep(1.0, 0.93, r) + 0.25 * smoothstep(1.0, 0.0, r) * exp(-vR * 3.0);
  gl_FragColor = vec4(vColor * 1.4, ring * vA); }`;

const HAZE_VS = `varying vec2 vUv; void main() { vUv = uv * 2.0 - 1.0; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const HAZE_FS = `
uniform vec3 uColor; uniform float uAlpha, uTime, uSpiral, uStar;
varying vec2 vUv;
void main() {
  float r = length(vUv);
  if (r > 1.0) discard;
  float arms = 0.5 + 0.5 * sin(atan(vUv.y, vUv.x) * 2.0 - r * 9.0 + uTime * 0.05);
  float a = exp(-r * r * 3.4) * (1.0 - uSpiral + uSpiral * (0.35 + 0.9 * arms * smoothstep(0.0, 0.25, r)));
  gl_FragColor = vec4(uColor, a * uAlpha * (1.0 - uStar));
}`;

const SPARKS = 16, TRAIL = 24, TRAIL_GAP = 0.014, BURSTS = 24, SPARK_SECONDS = 2.4;
const SPARK_COLOUR = RING_COLOUR;                        // Jarvis's cyan: the sparks, the memory ring, the synapses of learning
const VIEW_SECONDS = 0.9;                                // galaxy <-> constellation

export class Brain {
  constructor(THREE, canvas, { quality = 'high', reduced = false } = {}) {
    this.T = THREE;
    this.canvas = canvas;
    this.reduced = reduced;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setClearColor(0x03040a, 1);
    this.view = 'galaxy';
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(52, 1, 1, 12000);
    this.u = {
      uTime: { value: 0 }, uScale: { value: 1 }, uDpr: { value: 1 }, uMotion: { value: reduced ? 0 : 1 },
      uFogNear: { value: 300 }, uFogFar: { value: 1500 }, uStar: { value: 0 },
    };
    this.nebulae = new Nebulae(THREE, this.u);
    this.clusterEmph = [];
    this.n = 0; this.graph = null; this.extent = 300; this.centre = new THREE.Vector3();
    this.layers = {};
    this.sparks = []; this.burstNext = 0; this.launched = 0;   // launched: every spark ever sent (tests)
    this.shift = { x: 0, y: 0, tx: 0, ty: 0 };
    this._v = new THREE.Vector3();
    this._buildSparks();
    this._swap('nebulae', this.nebulae.quad, 1);
    this.synapses = new Synapses(THREE, this._material(SYNAPSE_VS, GLOW_FS));
    this._swap('synapses', this.synapses.points, 7);
    this.rc = null;                                  // the OLYMPUS render core (bloom, MSAA, film finish), when it loaded
    this.setQuality(quality);
  }

  /** Put the scene on the OLYMPUS render core (../olympus/render.js): real bloom on the glowing nodes and links, 4x MSAA on HD,
   *  FXAA on LITE, a film finish. 'display' space: the shaders here are tuned in screen colours, so bloom takes 0..1 values.
   *  Without the core (or on failure) the plain renderer keeps drawing as before. Returns true when the core took over. */
  useCore(createRenderer, { followKit = true } = {}) {
    if (this.rc || typeof createRenderer !== 'function') return !!this.rc;
    try {
      const o = {
        renderer: this.renderer, scene: this.scene, camera: this.camera, space: 'display', env: 'none', autoSize: false, adapt: false,
        maxDpr: this.quality === 'high' ? 2 : 1.25, onQuality: () => this.resize(),
        bloom: { strength: 0.62, radius: 0.78, threshold: 0.42 }, grade: { grain: 0.03, vignette: 0.26, aberration: 0.0018, saturation: 1.06 },
      };
      const forced = new URLSearchParams(location.search).get('q');                 // ?q=ultra|high|low|off: pin a tier (tests, software GPUs)
      if (['ultra', 'high', 'low', 'off'].includes(forced)) o.quality = forced;
      else if (!followKit) o.quality = this.quality === 'high' ? 'high' : 'low';
      this.rc = createRenderer(o);
      this.resize();
    } catch (_) { this.rc = null; }
    return !!this.rc;
  }

  // ------------------------------------------------------------------ setup
  _material(vs, fs, extra = {}) {
    return new this.T.ShaderMaterial({
      uniforms: { ...this.u, ...extra }, vertexShader: vs, fragmentShader: fs,
      transparent: true, depthWrite: false, depthTest: false, blending: this.T.AdditiveBlending,
    });
  }

  _swap(name, obj, order) {
    const old = this.layers[name];
    if (old) {
      this.scene.remove(old);
      old.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
    }
    this.layers[name] = obj;
    if (obj) { obj.frustumCulled = false; obj.renderOrder = order; this.scene.add(obj); }
  }

  _geometry(attrs) {
    const T = this.T, g = new T.BufferGeometry();
    for (const [k, [arr, size, dynamic]] of Object.entries(attrs)) {
      const a = new T.BufferAttribute(arr, size);
      if (dynamic) a.setUsage(T.DynamicDrawUsage);
      g.setAttribute(k, a);
    }
    return g;
  }

  setQuality(q) {
    this.quality = q;
    if (this.rc && !window.OLYMPUS) this.rc.setQuality(q === 'high' ? 'high' : 'low');
    if (!this.rc) this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, q === 'high' ? 2 : 1));
    this._buildStars(q === 'high' ? 2200 : 700);
    this.ring = new MemoryRing(this.T, this.u, q);
    this._swap('memory', this.ring.group, 2);
    if (this.graph) this._buildGraphLayers();
    this.resize();
  }

  resize() {
    const w = this.canvas.clientWidth || window.innerWidth, h = this.canvas.clientHeight || window.innerHeight;
    if (this.rc) this.rc.resize(w, h); else this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    const dpr = this.renderer.getPixelRatio();
    this.u.uDpr.value = dpr;
    this.u.uScale.value = (h * dpr) / (2 * Math.tan((this.camera.fov * Math.PI) / 360));
    this.nebulae.resize(w * dpr, h * dpr);
    this.width = w; this.height = h;
    if (this.shift.x || this.shift.y) this.camera.setViewOffset(w, h, -this.shift.x, -this.shift.y, w, h);
  }

  _buildStars(count) {
    const T = this.T, pos = new Float32Array(count * 3), col = new Float32Array(count * 3), size = new Float32Array(count), seed = new Float32Array(count);
    const tints = [[0.75, 0.82, 1], [1, 1, 1], [1, 0.9, 0.72], [0.7, 0.95, 1]];
    let s = 99;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < count; i++) {
      const u = rnd() * 2 - 1, a = rnd() * Math.PI * 2, r = 3500 + rnd() * 3500, q = Math.sqrt(1 - u * u);
      pos.set([Math.cos(a) * q * r, u * r, Math.sin(a) * q * r], i * 3);
      const t = tints[i % 4], b = 0.35 + rnd() * 0.65;
      col.set([t[0] * b, t[1] * b, t[2] * b], i * 3);
      size[i] = rnd() < 0.04 ? 2.6 + rnd() * 1.4 : 0.8 + rnd() * 1.3;
      seed[i] = rnd();
    }
    const g = this._geometry({ position: [pos, 3], aColor: [col, 3], aSize: [size, 1], aSeed: [seed, 1] });
    this._swap('stars', new T.Points(g, this._material(STAR_VS, STAR_FS)), 0);
  }

  _buildSparks() {
    const T = this.T, P = SPARKS * TRAIL;
    this.sparkPos = new Float32Array(P * 3); this.sparkSize = new Float32Array(P); this.sparkAlpha = new Float32Array(P);
    const g = this._geometry({ position: [this.sparkPos, 3, true], aSize: [this.sparkSize, 1, true], aAlpha: [this.sparkAlpha, 1, true] });
    this._swap('sparks', new T.Points(g, this._material(SPARK_VS, GLOW_FS, { uColor: { value: new T.Color(SPARK_COLOUR) } })), 6);
    this.burstPos = new Float32Array(BURSTS * 3); this.burstT0 = new Float32Array(BURSTS).fill(-99);
    this.burstSize = new Float32Array(BURSTS); this.burstCol = new Float32Array(BURSTS * 3);
    const b = this._geometry({ position: [this.burstPos, 3, true], aT0: [this.burstT0, 1, true], aSize: [this.burstSize, 1, true], aColor: [this.burstCol, 3, true] });
    this._swap('bursts', new T.Points(b, this._material(BURST_VS, BURST_FS)), 5);
  }

  /** A new graph. targets: layout positions; start: where each note is drawn now (new notes: far out); normals: disc per cluster. */
  setGraph(graph, { targets, start, normals }) {
    const T = this.T, n = graph.nodes.length;
    this.graph = graph; this.n = n; this.normals = normals;
    this.target = Float32Array.from(targets);
    this.disp = Float32Array.from(start);
    this.colour = new Float32Array(n * 3);
    const c = new T.Color();
    this.clusterColours = graph.clusters.map((k) => new T.Color(k.colour));
    for (const node of graph.nodes) {
      c.copy(this.clusterColours[node.cluster]).offsetHSL(0, 0, ((hash(node.id) % 1000) / 1000 - 0.5) * 0.14);
      this.colour.set([c.r, c.g, c.b], node.i * 3);
    }
    this.emph = new Float32Array(n).fill(1);
    this.show = new Float32Array(n).fill(1);
    this.ignited = new Float32Array(n).fill(-99);
    this.sparks = this.sparks.filter((s) => s.id && graph.index.has(s.id)).map((s) => ({ ...s, i: graph.index.get(s.id) }));
    this.synapses.live = [];                               // pulses ran on the old indices
    this._buildGraphLayers();
    this._measure();
  }

  _buildGraphLayers() {
    const T = this.T, g = this.graph, n = this.n, E = g.edges, m = E.length / 2;
    const size = new Float32Array(n), fx = new Float32Array(n * 4);
    for (const node of g.nodes) {
      size[node.i] = node.size;
      fx.set([this.ignited[node.i], node.pulse, this.emph[node.i], this.show[node.i]], node.i * 4);
    }
    this.fx = fx;
    const nodes = new T.Points(this._geometry({ position: [this.disp, 3, true], aColor: [this.colour, 3], aSize: [size, 1], aFx: [fx, 4, true] }),
      this._material(NODE_VS, NODE_FS));
    // filaments
    this.edgePos = new Float32Array(m * 6); this.edgeAlpha = new Float32Array(m * 2);
    const ec = new Float32Array(m * 6);
    for (let e = 0; e < m; e++) {
      const a = E[e * 2] * 3, b = E[e * 2 + 1] * 3;
      ec.set([this.colour[a], this.colour[a + 1], this.colour[a + 2], this.colour[b], this.colour[b + 1], this.colour[b + 2]], e * 6);
    }
    const lines = new T.LineSegments(this._geometry({ position: [this.edgePos, 3, true], aColor: [ec, 3], aAlpha: [this.edgeAlpha, 1, true] }),
      this._material(EDGE_VS, EDGE_FS));
    // flow: one particle per link, evenly thinned past the cap
    const cap = this.reduced ? 0 : this.quality === 'high' ? 3000 : 700;
    const stride = Math.max(1, m / Math.max(1, cap)), count = Math.min(m, cap);
    this.flowEdge = new Uint32Array(count);
    this.flowA = new Float32Array(count * 3); this.flowB = new Float32Array(count * 3); this.flowAlpha = new Float32Array(count);
    const fc = new Float32Array(count * 3), seed = new Float32Array(count * 2);
    for (let k = 0; k < count; k++) {
      const e = Math.floor(k * stride), forward = (hash(String(e)) & 1) === 0;
      this.flowEdge[k] = forward ? e * 2 : e * 2 + 1;                   // which end it starts from
      const b = E[forward ? e * 2 + 1 : e * 2] * 3;
      fc.set([this.colour[b] * 0.5 + 0.5, this.colour[b + 1] * 0.5 + 0.5, this.colour[b + 2] * 0.5 + 0.5], k * 3);
      seed.set([((k * 0.618034) % 1), 0.12 + ((k * 0.414) % 1) * 0.22], k * 2);
    }
    const flow = count ? new T.Points(this._geometry({ position: [this.flowA, 3, true], aB: [this.flowB, 3, true], aColor: [fc, 3], aSeed: [seed, 2], aAlpha: [this.flowAlpha, 1, true] }),
      this._material(FLOW_VS, GLOW_FS)) : null;
    this._swap('lines', lines, 2);
    this._swap('flow', flow, 3);
    this._swap('nodes', nodes, 4);
    this._buildHaze();
    this._applyLook();
    this._syncPositions();
  }

  _buildHaze() {
    const T = this.T, g = this.graph;
    this.nebulae.build(g.clusters, this.clusterColours, this.quality);
    if (this.quality !== 'high' || !g.clusters.length) { this._swap('haze', null); this.hazes = []; return; }
    const group = new T.Group(), plane = new T.PlaneGeometry(2, 2);
    this.hazes = g.clusters.map((c, k) => {
      const alpha = { value: c.key === 'me' || c.key === 'memory' ? 0 : 0.12 };
      const disc = new T.Mesh(plane, new T.ShaderMaterial({
        uniforms: { uTime: this.u.uTime, uStar: this.u.uStar, uColor: { value: this.clusterColours[k] }, uAlpha: alpha, uSpiral: { value: 1 } },
        vertexShader: HAZE_VS, fragmentShader: HAZE_FS, transparent: true, depthWrite: false, depthTest: false,
        blending: T.AdditiveBlending, side: T.DoubleSide,
      }));
      group.add(disc);
      return { disc, alpha, base: alpha.value, count: c.count };
    });
    this._swap('haze', group, 1);
  }

  // ------------------------------------------------------------------ positions
  setTargets(pos) {
    if (pos.length !== this.n * 3) return;
    this.target.set(pos);
    this._measure();
  }

  _measure() {
    const t = this.target, n = this.n;
    let x = 0, y = 0, z = 0;
    for (let i = 0; i < n; i++) { x += t[i * 3]; y += t[i * 3 + 1]; z += t[i * 3 + 2]; }
    if (n) this.centre.set(x / n, y / n, z / n);
    let r2 = 0;
    for (let i = 0; i < n; i++) {
      const dx = t[i * 3] - this.centre.x, dy = t[i * 3 + 1] - this.centre.y, dz = t[i * 3 + 2] - this.centre.z;
      r2 = Math.max(r2, dx * dx + dy * dy + dz * dz);
    }
    this.extent = Math.max(80, Math.sqrt(r2));
  }

  /** Where node i is heading (its settled place): the point to fly to. */
  nodePoint(i) { return { x: this.target[i * 3], y: this.target[i * 3 + 1], z: this.target[i * 3 + 2] }; }

  /** A far point on the node's own bearing: where a new note enters from. */
  edgePoint(t, i) {
    const x = t[i * 3] - this.centre.x, y = t[i * 3 + 1] - this.centre.y, z = t[i * 3 + 2] - this.centre.z, l = Math.hypot(x, y, z) || 1;
    const r = this.extent * 2.6;
    return [this.centre.x + (x / l) * r, this.centre.y + (y / l) * r, this.centre.z + (z / l) * r];
  }

  _ease(dt) {
    const d = this.disp, t = this.target, k = this.reduced ? 1 : 1 - Math.exp(-dt * 2.6);
    let moved = 0;
    for (let i = 0; i < d.length; i++) {
      const delta = t[i] - d[i];
      if (delta > 0.02 || delta < -0.02) { d[i] += delta * k; moved = 1; } else d[i] = t[i];
    }
    if (moved) this._syncPositions();
    return moved;
  }

  _syncPositions() {
    const d = this.disp, E = this.graph.edges;
    for (let e = 0; e < E.length; e += 2) {
      const a = E[e] * 3, b = E[e + 1] * 3, o = e * 3;
      this.edgePos[o] = d[a]; this.edgePos[o + 1] = d[a + 1]; this.edgePos[o + 2] = d[a + 2];
      this.edgePos[o + 3] = d[b]; this.edgePos[o + 4] = d[b + 1]; this.edgePos[o + 5] = d[b + 2];
    }
    for (let k = 0; k < this.flowEdge.length; k++) {
      const end = this.flowEdge[k], a = E[end] * 3, b = E[end ^ 1] * 3;
      this.flowA[k * 3] = d[a]; this.flowA[k * 3 + 1] = d[a + 1]; this.flowA[k * 3 + 2] = d[a + 2];
      this.flowB[k * 3] = d[b]; this.flowB[k * 3 + 1] = d[b + 1]; this.flowB[k * 3 + 2] = d[b + 2];
    }
    this._dirty('nodes', 'position'); this._dirty('lines', 'position'); this._dirty('flow', 'position', 'aB');
    this.centres = this._clusterCentres();
    this._placeHaze();
  }

  _dirty(layer, ...names) {
    const o = this.layers[layer];
    if (o) for (const k of names) o.geometry.attributes[k].needsUpdate = true;
  }

  /** Cluster centres and spreads from what is drawn (for the haze and the galaxy labels; kept in this.centres). */
  _clusterCentres() {
    const g = this.graph, d = this.disp, k = g.clusters.length;
    const sum = new Float32Array(k * 4), out = [];
    for (const node of g.nodes) {
      const c = node.cluster * 4, i = node.i * 3;
      sum[c] += d[i]; sum[c + 1] += d[i + 1]; sum[c + 2] += d[i + 2]; sum[c + 3]++;
    }
    for (let c = 0; c < k; c++) {
      const m = sum[c * 4 + 3] || 1;
      out.push({ x: sum[c * 4] / m, y: sum[c * 4 + 1] / m, z: sum[c * 4 + 2] / m, r: 0 });
    }
    for (const node of g.nodes) {
      const o = out[node.cluster], i = node.i * 3;
      o.r = Math.max(o.r, Math.hypot(d[i] - o.x, d[i + 1] - o.y, d[i + 2] - o.z));
    }
    return out;
  }

  _placeHaze() {
    this.nebulae.place(this.centres, this.normals);
    this._placeRing();
    if (!this.hazes || !this.hazes.length) return;
    this.hazes.forEach((h, k) => {
      const c = this.centres[k], r = Math.max(24, c.r * 1.25), nm = this.normals;
      h.disc.position.set(c.x, c.y, c.z);
      h.disc.lookAt(c.x + nm[k * 3], c.y + nm[k * 3 + 1], c.z + nm[k * 3 + 2]);
      h.disc.scale.setScalar(r);
      h.disc.visible = h.count > 2;
    });
  }

  /** The memory ring: centred on Me, as wide as the memories sit from it (this.ringInfo for the label and the tests). */
  _placeRing() {
    const g = this.graph, me = g.clusters.findIndex((c) => c.key === 'me'), mem = g.clusters.findIndex((c) => c.key === 'memory');
    if (me < 0 || mem < 0 || !this.centres[me]) { this.ring.place(null); this.ringInfo = null; return; }
    const c = this.centres[me], d = this.disp;
    let sum = 0, k = 0;
    for (const node of g.nodes) {
      if (node.cluster !== mem) continue;
      sum += Math.hypot(d[node.i * 3] - c.x, d[node.i * 3 + 1] - c.y, d[node.i * 3 + 2] - c.z); k++;
    }
    const r = k ? sum / k : 0;
    this.ring.place(k ? c : null, r);
    this.ringInfo = k ? { x: c.x, y: c.y, z: c.z, r, count: k } : null;
  }

  // ------------------------------------------------------------------ look: emphasis (filters, search, focus) and time-lapse
  setLook(emph, show, clusterEmph = null) {
    this.emph.set(emph);
    this.show.set(show);
    this.clusterEmph = clusterEmph || this.graph.clusters.map(() => 1);
    this._applyLook();
  }

  _applyLook() {
    const { fx, emph, show, graph: g } = this, E = g.edges;
    for (let i = 0; i < this.n; i++) { fx[i * 4 + 2] = emph[i]; fx[i * 4 + 3] = show[i]; }
    const base = this.quality === 'high' ? 0.2 : 0.26;
    for (let e = 0; e < E.length; e += 2) {
      const a = E[e], b = E[e + 1], k = Math.min(emph[a], emph[b]), s = Math.min(show[a], show[b]);
      this.edgeAlpha[e] = this.edgeAlpha[e + 1] = base * k * k * s;
    }
    for (let k = 0; k < this.flowEdge.length; k++) this.flowAlpha[k] = this.edgeAlpha[this.flowEdge[k]] * 3.2;
    this._dirty('nodes', 'aFx'); this._dirty('lines', 'aAlpha'); this._dirty('flow', 'aAlpha');
    // focus mode: the clouds, the discs and the memory ring of the other galaxies fade with them
    const ce = this.clusterEmph.length === g.clusters.length ? this.clusterEmph : g.clusters.map(() => 1);
    this.nebulae.emphasis(ce);
    if (this.hazes) this.hazes.forEach((h, k) => { h.alpha.value = h.base * ce[k]; });
    const mem = g.clusters.findIndex((c) => c.key === 'memory');
    this.ring.strength(mem >= 0 ? Math.max(0.08, ce[mem]) : 1);
  }

  /** 'galaxy' (spheres, nebulae, flow) or 'stars' (the constellation view); eased over VIEW_SECONDS. */
  setView(v) { this.view = v === 'stars' ? 'stars' : 'galaxy'; }

  setBackground(colour) { try { this.renderer.setClearColor(new this.T.Color(colour), 1); } catch (_) { /* a bad colour: keep the last */ } }

  /** A synapse burst from note i (opened, or learned something): pulses run out along its links. */
  synapse(i, colour = null) {
    if (this.reduced || !this.graph || i < 0 || i >= this.n) return;
    this.synapses.fire(i, this.graph, this.u.uTime.value, colour);
  }

  // ------------------------------------------------------------------ events: ignite, bursts, sparks
  /** Flash note i (and, with burst, send a ring out from it). */
  ignite(i, colour, burst = true) {
    const t = this.u.uTime.value;
    this.ignited[i] = t;
    this.fx[i * 4] = t;
    this._dirty('nodes', 'aFx');
    if (!burst) return;
    const b = this.burstNext++ % BURSTS, d = this.disp;
    this.burstPos.set([d[i * 3], d[i * 3 + 1], d[i * 3 + 2]], b * 3);
    this.burstT0[b] = t;
    this.burstSize[b] = this.graph.nodes[i].size * 1.1;
    const c = colour ? new this.T.Color(colour) : this.clusterColours[this.graph.nodes[i].cluster];
    this.burstCol.set([c.r, c.g, c.b], b * 3);
    this._dirty('bursts', 'position', 'aT0', 'aSize', 'aColor');
  }

  /** A "Jarvis learned" comet from the bottom sheet's ticker to note i (a synapse burst where it lands). */
  spark(i) {
    if (this.reduced) { this.ignite(i, SPARK_COLOUR); return; }
    const T = this.T, cam = this.camera, end = this._v.set(this.disp[i * 3], this.disp[i * 3 + 1], this.disp[i * 3 + 2]);
    const dist = cam.position.distanceTo(end);
    const dir = new T.Vector3(-0.35, -0.6, 0.5).unproject(cam).sub(cam.position).normalize();
    const from = cam.position.clone().addScaledVector(dir, Math.max(20, dist * 0.5));      // above the ticker, mid-depth
    const side = new T.Vector3().crossVectors(dir, end.clone().sub(from)).normalize().multiplyScalar(dist * 0.08);
    const ctrl = from.clone().add(end).multiplyScalar(0.5).add(side).addScaledVector(cam.up, dist * 0.06);   // a gentle arc, on screen
    if (this.sparks.length >= SPARKS) this.sparks.shift();
    this.launched++;
    this.sparks.push({ i, id: this.graph.nodes[i].id, t0: this.u.uTime.value, from: from.toArray(), ctrl: ctrl.toArray() });
  }

  _updateSparks() {
    const now = this.u.uTime.value, d = this.disp;
    this.sparkAlpha.fill(0);
    this.sparks = this.sparks.filter((s) => {
      const u = (now - s.t0) / SPARK_SECONDS;
      if (u >= 1) { this.ignite(s.i, SPARK_COLOUR); this.synapse(s.i, SPARK_COLOUR); return false; }
      return true;
    });
    this.sparks.forEach((s, slot) => {
      const u = (now - s.t0) / SPARK_SECONDS, P2 = [d[s.i * 3], d[s.i * 3 + 1], d[s.i * 3 + 2]];
      for (let k = 0; k < TRAIL; k++) {
        const q = Math.max(0, u - k * TRAIL_GAP), e = q * q * (3 - 2 * q), w = 1 - e, o = (slot * TRAIL + k) * 3;
        for (let a = 0; a < 3; a++) this.sparkPos[o + a] = w * w * s.from[a] + 2 * w * e * s.ctrl[a] + e * e * P2[a];
        this.sparkSize[slot * TRAIL + k] = (k === 0 ? 8 : 5) * (1 - k / TRAIL) ** 0.7;
        this.sparkAlpha[slot * TRAIL + k] = u - k * TRAIL_GAP > 0 ? (1 - k / TRAIL) * Math.min(1, u * 8) : 0;
      }
    });
    this._dirty('sparks', 'position', 'aSize', 'aAlpha');
  }

  /** Move the picture's centre by (dx, dy) CSS px (the focused note stays in view beside or above its card). */
  shiftTo(dx, dy) { this.shift.tx = dx; this.shift.ty = dy; }

  _easeShift(dt) {
    const s = this.shift, k = this.reduced ? 1 : 1 - Math.exp(-dt * 6);
    if (Math.abs(s.tx - s.x) + Math.abs(s.ty - s.y) < 0.3) { if (s.x === s.tx && s.y === s.ty) return false; s.x = s.tx; s.y = s.ty; }
    else { s.x += (s.tx - s.x) * k; s.y += (s.ty - s.y) * k; }
    if (s.x || s.y) this.camera.setViewOffset(this.width, this.height, -s.x, -s.y, this.width, this.height);
    else this.camera.clearViewOffset();
    return true;
  }

  get busy() {
    return this.moving || this.shift.x !== this.shift.tx || this.shift.y !== this.shift.ty || this.sparks.length > 0 || this.synapses.count > 0
      || this.u.uStar.value !== (this.view === 'stars' ? 1 : 0) || this.u.uTime.value - Math.max(...this.burstT0) < 1.7;
  }

  // ------------------------------------------------------------------ the frame
  frame(dt, seconds, rig) {
    this.u.uTime.value = seconds;
    this.moving = this.n ? this._ease(dt) : 0;
    if (this.sparks.length || this.sparkAlpha[0]) this._updateSparks();
    const star = this.u.uStar, want = this.view === 'stars' ? 1 : 0;
    star.value = this.reduced ? want : want > star.value ? Math.min(1, star.value + dt / VIEW_SECONDS) : Math.max(0, star.value - dt / VIEW_SECONDS);
    if (this.n) {
      if (!this.reduced && this.quality === 'high') this.synapses.think(this.graph, seconds);
      if (this.synapses.count || this._synapsesShown) {        // one more pass after the last pulse clears the layer
        this._synapsesShown = this.synapses.update(seconds, this.disp, this.colour, this.graph, (i, quiet) => { if (!quiet) this.ignite(i, null, false); }) > 0;
      }
    }
    rig.update(dt);
    this._easeShift(dt);
    const near = rig.radius - this.extent * 0.15, far = rig.radius + this.extent * 1.25;
    this.u.uFogNear.value = Math.max(1, near); this.u.uFogFar.value = Math.max(near + 50, far);
    this.nebulae.render(this.renderer, this.camera);
    if (this.rc) this.rc.render(); else this.renderer.render(this.scene, this.camera);
  }

  // ------------------------------------------------------------------ screen space
  /** CSS pixel position of a world point; front = in front of the camera. */
  screenOf(p) {
    const v = this._v.set(p.x, p.y, p.z).project(this.camera);
    return { x: ((v.x + 1) / 2) * this.width, y: ((1 - v.y) / 2) * this.height, front: v.z < 1 && v.z > -1 };
  }

  /** The note under a tap (CSS pixels relative to the canvas), or -1. */
  pick(x, y) {
    const d = this.disp, cam = this.camera.position, scale = this.u.uScale.value / this.u.uDpr.value;
    let best = -1, bestScore = Infinity;
    for (let i = 0; i < this.n; i++) {
      if (this.show[i] < 0.5 || this.emph[i] < 0.2) continue;
      const p = { x: d[i * 3], y: d[i * 3 + 1], z: d[i * 3 + 2] }, s = this.screenOf(p);
      if (!s.front) continue;
      const dist = Math.hypot(cam.x - p.x, cam.y - p.y, cam.z - p.z);
      const radius = Math.max(18, (this.graph.nodes[i].size * 0.38 * scale) / dist + 8);
      const off = Math.hypot(s.x - x, s.y - y);
      if (off < radius && off / radius + dist * 1e-5 < bestScore) { best = i; bestScore = off / radius + dist * 1e-5; }
    }
    return best;
  }
}

function hash(s) {
  let h = 2166136261;
  for (let k = 0; k < s.length; k++) h = Math.imul(h ^ s.charCodeAt(k), 16777619);
  return h >>> 0;
}
