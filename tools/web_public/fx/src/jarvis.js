// The Jarvis core: the living centrepiece of the page where the owner talks to the bot. A breathing icosahedral nucleus
// (fresnel shell + plasma bands) inside three gyroscopic rings that counter-rotate slowly, a shell of a few thousand
// additive particles, a holographic floor grid and a soft halo. Four states, eased into each other over ~400 ms:
//   idle       slow breathing, accent -> accent2 palette, rings drift
//   listening  teal; the rings tilt toward the camera and contract with the level, the shell is pulled inward
//   thinking   magenta; the rings spin fast and desynchronise, sparks spiral out of the shell, the nucleus wobbles
//   speaking   warm white; rings and nucleus pulse outward with the level, a ripple travels down the shell's latitudes
// setData({ state: 'idle'|'listening'|'thinking'|'speaking', level: 0..1 | null (null = a synthetic envelope per state),
//           mood: { cold: bool (cooler blue, slower), pnl: number (>0 green rim, <0 red rim), live: bool (dim when off) },
//           text: string | null (a caption under the core; the state word sits above it) })
// Drag orbits a little (it sways by itself); a tap -> view.burst() (a short shock wave) and opts.onPick(state).
// Particles: 3200 (phone 2400, lite 1600). Draw calls ~12.
import { THREE, View, Q, theme, par, glowTexture, POINT_FRAG, rng, count } from './core.js';

const EASE = 7.5;      // 1/s: ~95 % of a transition in 400 ms
const STATES = ['idle', 'listening', 'thinking', 'speaking'];
const MAGENTA = '#ff2bd6', WARM = '#fff0d6', WARM2 = '#ffc98a', COLD = '#4f86ff', COLD2 = '#2bb8ff';
const _c = new THREE.Color(), _c2 = new THREE.Color(), _v = new THREE.Vector3();
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const fract = (v) => v - Math.floor(v);

// ------------------------------------------------------------------ shaders
const NUC_V = `uniform float uTime; uniform float uWobble; varying vec3 vN; varying vec3 vV; varying vec3 vP;
void main(){
  vec3 p = position + normal * uWobble * 0.06 * sin(position.x * 9.0 + uTime * 11.0) * sin(position.y * 7.0 - uTime * 9.0);
  vec4 mv = modelViewMatrix * vec4(p, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); vP = position;
  gl_Position = projectionMatrix * mv; }`;
const NUC_F = `uniform vec3 uCol; uniform vec3 uCol2; uniform vec3 uRim; uniform float uRimK; uniform float uTime; uniform float uBeat; uniform float uSpeed; uniform float uDim;
varying vec3 vN; varying vec3 vV; varying vec3 vP;
void main(){
  float t = uTime * uSpeed; vec3 p = vP * 4.0;
  float n = sin(p.x * 1.6 + t * 1.2) * sin(p.y * 2.2 - t * 0.8) * sin(p.z * 1.8 + t * 0.6);
  n += 0.5 * sin(p.x * 4.1 - t * 1.6 + p.y * 2.3) * sin(p.z * 3.6 + t * 1.1);
  float bands = clamp(0.5 + 0.5 * n, 0.0, 1.0);
  float f = 1.0 - max(dot(vN, vV), 0.0), rim = pow(f, 2.4), edge = pow(f, 6.0);
  // facets: a faint flat-shaded tint so the icosahedron reads as cut glass
  vec3 fw = normalize(cross(dFdx(vP), dFdy(vP))); float facet = 0.5 + 0.5 * dot(fw, normalize(vec3(0.4, 0.8, 0.5)));
  vec3 c = mix(uCol2, uCol, bands) * (0.22 + 0.5 * uBeat) * (0.7 + 0.5 * facet);
  c += uCol * rim * (1.1 + 0.6 * uBeat) + uRim * edge * uRimK * 2.2 + vec3(1.0) * pow(1.0 - f, 7.0) * 0.5 * uBeat;
  gl_FragColor = vec4(c * uDim, 1.0); }`;
const RING_V = `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`;
const RING_F = `uniform vec3 uCol; uniform float uTime; uniform float uPhase; uniform float uA; uniform float uSeg; uniform float uHeat;
varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){
  float f = max(dot(vN, vV), 0.0);
  float dash = smoothstep(0.08, 0.18, fract(vUv.x * uSeg)) * smoothstep(0.98, 0.9, fract(vUv.x * uSeg));
  float run = exp(-pow((fract(vUv.x - uPhase) - 0.5) * 7.0, 2.0));          // a bright runner going round
  float run2 = exp(-pow((fract(vUv.x + uPhase * 0.6 + 0.37) - 0.5) * 12.0, 2.0)) * 0.6;
  vec3 c = uCol * (0.18 + 0.32 * dash + (run + run2) * (0.9 + uHeat)) * (0.35 + 0.65 * f);
  c += vec3(1.0) * run * run * 0.35 * (0.5 + uHeat);
  gl_FragColor = vec4(c * uA, 1.0); }`;
const SHELL_V = `attribute vec3 aDir; attribute float aSeed; attribute float aS;
uniform float uTime; uniform float uPix; uniform vec4 uW; uniform float uLevel; uniform float uWave; uniform float uSpin; uniform float uBurst;
uniform vec3 uCol; uniform vec3 uCol2; uniform float uBright; uniform float uSpeed;
varying vec3 vColor; varying float vAlpha;
void main(){
  float t = uTime * uSpeed, R0 = 1.12;
  // idle: a slow breath with a little per-particle shimmer
  float r = R0 * (1.0 + 0.045 * sin(t * 0.9 + aSeed * 2.5) + 0.012 * sin(t * 3.0 + aSeed * 40.0));
  // listening: pulled inward by the level (tense, jittery)
  r -= uW.y * (0.08 + 0.38 * uLevel) * (0.75 + 0.25 * sin(t * 9.0 + aSeed * 31.0));
  // speaking: a ripple travelling down the latitudes, thrown outward by the level
  float lat = asin(clamp(aDir.y, -1.0, 1.0));
  float rip = 0.5 + 0.5 * sin(lat * 4.0 - uWave * 6.2831 + aSeed * 0.6);
  r += uW.w * (0.05 + 0.6 * uLevel) * rip * rip;
  // burst: a shock wave from a tap
  r += uBurst * 0.9 * (0.6 + 0.4 * sin(aSeed * 50.0));
  vec3 p = aDir * r;
  // thinking: a third of the shell becomes sparks spiralling out and fading
  float spark = step(aSeed, 0.34) * uW.z;
  float ph = fract(aSeed * 13.7 + uSpin * (0.5 + aSeed * 0.9));
  float ang = ph * 5.5 + aSeed * 6.2831, rs = R0 + ph * 1.9;
  vec3 d2 = vec3(aDir.x * cos(ang) - aDir.z * sin(ang), aDir.y * (1.0 - ph * 0.5), aDir.x * sin(ang) + aDir.z * cos(ang));
  p = mix(p, normalize(d2) * rs, spark);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float sz = aS * (1.0 + uW.y * uLevel * 0.6 + uW.w * uLevel * 0.5 + spark * ph * 1.5);
  gl_PointSize = clamp(sz * uPix / -mv.z, 0.0, 26.0); gl_Position = projectionMatrix * mv;
  vec3 col = mix(uCol2, uCol, smoothstep(0.2, 0.8, aSeed));
  col = mix(col, vec3(1.0), spark * ph * ph * 0.7 + uW.w * rip * uLevel * 0.35);
  vColor = col * uBright;
  float tw = 0.65 + 0.35 * sin(t * (1.5 + aSeed * 4.0) + aSeed * 30.0);
  vAlpha = tw * mix(1.0, smoothstep(0.0, 0.1, ph) * (1.0 - smoothstep(0.7, 1.0, ph)), spark); }`;
const GRID_V = `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const GRID_F = `uniform vec3 uCol; uniform float uTime; uniform float uPulse; uniform float uA; varying vec2 vP;
void main(){
  float d = length(vP);
  vec2 g = abs(fract(vP * 1.6 - 0.5) - 0.5) / fwidth(vP * 1.6);
  float line = 1.0 - min(min(g.x, g.y), 1.0);
  float ring = exp(-pow((d - uPulse * 4.2) * 3.0, 2.0)) * step(0.001, uPulse) * (1.0 - uPulse);
  float fade = exp(-d * d * 0.16);
  float scan = 0.7 + 0.3 * sin(d * 3.0 - uTime * 1.2);
  vec3 c = uCol * (line * 0.5 * scan + ring * 1.6 + exp(-d * d * 1.8) * 0.25) * fade;
  gl_FragColor = vec4(c * uA, 1.0); }`;

const CSS = `.fxj-ui{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:2;font-family:inherit;-webkit-user-select:none;user-select:none;color:#eef0fb}
.fxj-state{position:absolute;left:0;right:0;top:12px;text-align:center;font-size:9px;font-weight:800;letter-spacing:.22em;text-transform:uppercase;color:rgba(214,218,250,.62);text-shadow:0 0 8px #07080c;transition:color .4s}
.fxj-text{position:absolute;left:12%;right:12%;bottom:14px;text-align:center;font-size:12px;font-weight:600;line-height:1.4;color:rgba(238,240,251,.88);text-shadow:0 0 10px rgba(5,3,14,.95),0 0 3px rgba(5,3,14,.95);opacity:0;transform:translateY(6px);transition:opacity .4s ease,transform .4s ease;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.fxj-text.on{opacity:1;transform:none}`;
function injectStyle() {
  if (document.getElementById('fxj-css')) return;
  const s = document.createElement('style'); s.id = 'fxj-css'; s.textContent = CSS; document.head.appendChild(s);
}
function backdrop(page) {
  const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
  const p = '#' + page.getHexString(), gr = g.createRadialGradient(128, 118, 0, 128, 128, 190);
  gr.addColorStop(0, '#1a1538'); gr.addColorStop(0.5, '#0c0a1e'); gr.addColorStop(1, p);
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// ------------------------------------------------------------------ the view
export class Jarvis extends View {
  constructor(opts = {}) {
    super({ fov: 32, dprMax: 2, ...opts, orbit: { yaw: 0, pitch: 0.12, auto: 0, min: -0.7, max: 0.7, pitchMin: -0.1, pitchMax: 0.55, ...(opts.orbit || {}) } });
    injectStyle();
    this.canvas.style.display = 'block'; this.canvas.style.cursor = 'grab';
    const S = this.scene, rnd = rng(42);
    if (!opts.alpha) S.background = backdrop(theme.page);
    this.lt = 0; this.state = 'idle'; this.want = [1, 0, 0, 0]; this.W = [1, 0, 0, 0];
    this.level = 0; this.lvl = 0; this.lvlIn = null; this.mood = { cold: false, pnl: 0, live: true }; this.text = null; this.sig = null;
    this.col = new THREE.Color(theme.accent); this.col2 = new THREE.Color(theme.accent2); this.rim = new THREE.Color(0x000000); this.rimK = 0;
    this.speed = 1; this.dim = 1; this.burstAt = -9; this.wave = 0; this.spin = 0; this.phase = 0; this.beatPh = 0;
    this.u = { uTime: { value: 0 }, uPix: { value: 400 }, uW: { value: new THREE.Vector4(1, 0, 0, 0) }, uLevel: { value: 0 }, uWave: { value: 0 }, uSpin: { value: 0 },
      uBurst: { value: 0 }, uCol: { value: new THREE.Color(theme.accent) }, uCol2: { value: new THREE.Color(theme.accent2) }, uBright: { value: 1 }, uSpeed: { value: 1 } };
    const u = this.u;
    this.g = new THREE.Group(); S.add(this.g);

    // halo (behind) + core glow (in front)
    const spr = (scale, op, order) => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(theme.accent), transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false })); s.scale.setScalar(scale); s.renderOrder = order; this.g.add(s); return s; };
    this.halo = spr(6.4, 0.16, 1); this.haloIn = spr(2.3, 0.4, 9);

    // nucleus: icosahedron with the fresnel / plasma shader + a wire cage counter-rotating around it
    this.nU = { uCol: u.uCol, uCol2: u.uCol2, uRim: { value: this.rim }, uRimK: { value: 0 }, uTime: u.uTime, uBeat: { value: 0.5 }, uSpeed: u.uSpeed, uDim: { value: 1 }, uWobble: { value: 0 } };
    this.nuc = new THREE.Mesh(new THREE.IcosahedronGeometry(0.58, 2), new THREE.ShaderMaterial({ uniforms: this.nU, vertexShader: NUC_V, fragmentShader: NUC_F, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.nuc.renderOrder = 5; this.g.add(this.nuc);
    this.cage = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(0.74, 1)), new THREE.LineBasicMaterial({ color: new THREE.Color(theme.accent), transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.cage.renderOrder = 6; this.g.add(this.cage);

    // gyroscopic rings: a tilt pivot per ring, the torus spins inside it
    this.rings = [[1.02, 0.03, 0.62, 0.0, 0.28, 0.26, 14], [1.3, 0.022, -0.46, 0.55, 0.0, -0.19, 20], [1.58, 0.017, 0.24, -0.35, 1.08, 0.13, 28]].map(([r, tube, tx, ty, tz, spd, seg], i) => {
      const U = { uCol: u.uCol, uTime: u.uTime, uPhase: { value: i * 0.33 }, uA: { value: 1 }, uSeg: { value: seg }, uHeat: { value: 0 } };
      const m = new THREE.Mesh(new THREE.TorusGeometry(r, tube, 10, 160), new THREE.ShaderMaterial({ uniforms: U, vertexShader: RING_V, fragmentShader: RING_F, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
      m.renderOrder = 7; const piv = new THREE.Group(); piv.add(m); this.g.add(piv);
      return { piv, m, U, tilt: [tx, ty, tz], spd, cur: [tx, ty, tz], ph: i * 2.1, sc: 1 };
    });

    // particle shell
    const N = count(Q.phone ? 2400 : 3200, 1600), dir = new Float32Array(N * 3), seed = new Float32Array(N), sz = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const z = rnd() * 2 - 1, a = rnd() * Math.PI * 2, rr = Math.sqrt(1 - z * z);
      dir.set([rr * Math.cos(a), z, rr * Math.sin(a)], i * 3); seed[i] = rnd(); sz[i] = (0.5 + rnd() * 1.4) * (Q.level === 'lite' ? 1.25 : 1);
    }
    const sg = new THREE.BufferGeometry();
    sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3)); sg.setAttribute('aDir', new THREE.BufferAttribute(dir, 3));
    sg.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1)); sg.setAttribute('aS', new THREE.BufferAttribute(sz, 1));
    sg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 4);
    this.shell = new THREE.Points(sg, new THREE.ShaderMaterial({ uniforms: u, vertexShader: SHELL_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.shell.renderOrder = 8; this.g.add(this.shell);

    // holographic floor grid
    this.gU = { uCol: u.uCol, uTime: u.uTime, uPulse: { value: 0 }, uA: { value: 0.55 } };
    this.grid = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.ShaderMaterial({ uniforms: this.gU, vertexShader: GRID_V, fragmentShader: GRID_F, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    this.grid.rotation.x = -Math.PI / 2; this.grid.position.y = -1.85; this.grid.renderOrder = 2; S.add(this.grid);
    const pool = spr(5, 0.12, 1); pool.position.set(0, -1.8, 0); pool.scale.set(6, 1.4, 1); this.pool = pool;
    S.traverse((o) => { o.frustumCulled = false; });

    // HTML: state word + caption
    this.ui = document.createElement('div'); this.ui.className = 'fxj-ui'; this.ui.setAttribute('aria-hidden', 'true');
    this.stEl = document.createElement('div'); this.stEl.className = 'fxj-state'; this.txEl = document.createElement('div'); this.txEl.className = 'fxj-text';
    this.ui.append(this.stEl, this.txEl);
    // index.js does `view.opts = { ...view.opts, ...pageOpts }`: keep our tap -> burst wired, remember the page's onPick apart
    this._pick = () => { this.burst(); if (this._onPick) { try { this._onPick(this.state); } catch (e) { console.warn('fx onPick', e); } } };
    this.opts = this.opts;
    this.camera.position.set(0, 0.5, 6.4);
  }
  get opts() { return this._o; }
  set opts(o) {
    o = o || {};
    if (typeof o.onPick === 'function' && o.onPick !== this._pick) this._onPick = o.onPick;
    this._o = { ...o, onPick: this._pick || o.onPick };
  }
  attach(el) {
    super.attach(el);
    if (!el) return;
    try { if (getComputedStyle(el).position === 'static') el.style.position = 'relative'; } catch { }
    if (this.ui.parentNode !== el) el.appendChild(this.ui);
  }
  detach() { super.detach(); this.ui?.remove(); }
  onResize(w, h) { this.u.uPix.value = h * this.renderer.getPixelRatio() / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))) * 0.02; }
  retheme() { if (this.scene.background) { this.scene.background.dispose(); this.scene.background = backdrop(theme.page); } }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pick) this._onPick = opts.onPick;
    const src = d && typeof d === 'object' ? d : {};
    const st = STATES.includes(src.state) ? src.state : 'idle';
    this.state = st; this.want = STATES.map((s) => (s === st ? 1 : 0));
    this.lvlIn = typeof src.level === 'number' && Number.isFinite(src.level) ? clamp(src.level, 0, 1) : null;
    if (src.mood && typeof src.mood === 'object') this.mood = { ...this.mood, ...src.mood };
    const text = typeof src.text === 'string' && src.text.trim() ? src.text.trim() : null;
    const sig = st + '|' + text + '|' + JSON.stringify(this.mood);
    if (sig !== this.sig) {
      this.sig = sig; this.text = text;
      if (text) { this.txEl.textContent = text; this.txEl.classList.add('on'); } else this.txEl.classList.remove('on');
      this.stEl.textContent = st === 'idle' ? (this.mood.live ? 'online' : 'standby') : st;
    }
    // react within one frame: the first setData snaps, later ones ease
    if (!this.started || Q.reduced) { this.W = [...this.want]; this.started = true; this.applyColors(1); }
  }
  burst() { this.burstAt = this.lt; }

  // target palette for the current state + mood, eased by k
  applyColors(k) {
    const m = this.mood, W = this.W;
    _c.set(0, 0, 0).add(_c2.copy(theme.accent).multiplyScalar(W[0])).add(_c2.copy(theme.accent2).multiplyScalar(W[1])).add(_c2.set(MAGENTA).multiplyScalar(W[2])).add(_c2.set(WARM).multiplyScalar(W[3]));
    if (m.cold) _c.lerp(_c2.set(COLD), 0.45);
    this.col.lerp(_c, k);
    _c.set(0, 0, 0).add(_c2.copy(theme.accent2).multiplyScalar(W[0])).add(_c2.copy(theme.cyan).multiplyScalar(W[1])).add(_c2.copy(theme.violet).multiplyScalar(W[2])).add(_c2.set(WARM2).multiplyScalar(W[3]));
    if (m.cold) _c.lerp(_c2.set(COLD2), 0.45);
    this.col2.lerp(_c, k);
    const pnl = +m.pnl || 0, rk = pnl === 0 ? 0 : clamp(Math.abs(pnl) / 800, 0.35, 1) * 0.5;
    this.rim.lerp(_c.copy(pnl >= 0 ? theme.good : theme.bad), k); this.rimK += (rk - this.rimK) * k;
    this.speed += ((m.cold ? 0.6 : 1) * (m.live ? 1 : 0.8) - this.speed) * k;
    this.dim += ((m.live === false ? 0.62 : 1) - this.dim) * k;
  }
  // a synthetic amplitude when the page sends none: calm breath, a nervous listen, a steady think, a speech envelope
  synth(t) {
    const W = this.W, sp = this.speed;
    const idle = 0.08 + 0.06 * Math.sin(t * 0.9 * sp);
    const listen = 0.22 + 0.14 * Math.sin(t * 5.1) * Math.sin(t * 2.3) + 0.06 * Math.sin(t * 13.0);
    const think = 0.5 + 0.12 * Math.sin(t * 2.2);
    const syl = Math.max(0, Math.sin(t * 7.3)) * (0.6 + 0.4 * Math.sin(t * 1.7)), pause = Math.sin(t * 0.6) > -0.6 ? 1 : 0.1;
    const speak = (0.12 + 0.75 * syl * pause) * (0.85 + 0.15 * Math.sin(t * 23));
    return clamp(W[0] * idle + W[1] * listen + W[2] * think + W[3] * speak, 0, 1);
  }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u, red = Q.reduced, k = red ? 1 : Math.min(1, dt * EASE);
    // state weights, palette, level (eased toward the input or the synthetic envelope)
    const W = this.W; let sum = 0;
    for (let i = 0; i < 4; i++) { W[i] += (this.want[i] - W[i]) * k; sum += W[i]; }
    for (let i = 0; i < 4; i++) W[i] /= sum || 1;
    this.applyColors(k);
    const lvIn = this.lvlIn != null ? this.lvlIn : this.synth(lt);
    this.lvl += (lvIn - this.lvl) * (red ? 1 : Math.min(1, dt * (lvIn > this.lvl ? 18 : 7)));
    const L = this.lvl, sp = this.speed, mo = red ? 0 : 1;
    const wI = W[0], wL = W[1], wT = W[2], wS = W[3];
    u.uTime.value = lt; u.uW.value.set(wI, wL, wT, wS); u.uLevel.value = L; u.uSpeed.value = sp;
    u.uCol.value.copy(this.col); u.uCol2.value.copy(this.col2);
    this.wave += dt * (0.25 + 1.6 * L) * sp * mo; u.uWave.value = this.wave;
    this.spin += dt * (0.35 + 0.5 * wT) * sp * mo; u.uSpin.value = this.spin;
    const bk = (lt - this.burstAt) / 0.9, burst = bk >= 0 && bk < 1 ? Math.sin(bk * Math.PI) * (1 - bk * 0.4) : 0;
    u.uBurst.value = burst; u.uBright.value = (0.85 + 0.35 * L * (wL + wS) + 0.15 * wT + burst * 0.6) * this.dim;
    // heartbeat: slow in idle, quick while thinking, follows the voice while speaking
    this.beatPh += dt * (0.55 + 1.6 * wT + 0.4 * wL) * sp * mo;
    const beat = red ? 0.6 : 0.45 + 0.35 * Math.pow(Math.max(0, Math.sin(this.beatPh * Math.PI * 2)), 3) + L * (0.25 * wS + 0.25 * wL) + burst * 0.5;
    // nucleus
    const nU = this.nU; nU.uBeat.value = beat; nU.uDim.value = this.dim; nU.uRimK.value = this.rimK; nU.uWobble.value = wT * (0.6 + 0.4 * Math.sin(lt * 3)) + burst * 0.5;
    const ns = (1 + 0.035 * Math.sin(lt * 1.2 * sp)) * (1 + 0.14 * L * wL + 0.2 * L * wS + 0.03 * wT * Math.sin(lt * 9) + burst * 0.18);
    this.nuc.scale.setScalar(ns); this.nuc.rotation.y += dt * (0.12 + 0.9 * wT) * sp * mo; this.nuc.rotation.x += dt * 0.05 * sp * mo;
    this.cage.rotation.y -= dt * (0.18 + 2.2 * wT) * sp * mo; this.cage.rotation.z += dt * (0.06 + 0.8 * wT) * sp * mo;
    this.cage.scale.setScalar(1 + 0.08 * L * wS - 0.06 * L * wL + burst * 0.2);
    this.cage.material.color.copy(this.col).lerp(_c.set('#ffffff'), 0.2); this.cage.material.opacity = (0.3 + 0.35 * wT + 0.2 * L) * this.dim;
    // rings: tilt (toward the camera while listening, wobbling while thinking), spin, scale
    this.rings.forEach((R, i) => {
      const wob = wT * 0.45 * Math.sin(lt * (2.1 + i * 0.7) + R.ph);
      const tx = (R.tilt[0] + wob) * (1 - wL) + Math.sin(lt * 0.9 + i) * 0.04 * wL, ty = (R.tilt[1] + wob * 0.6) * (1 - wL), tz = (R.tilt[2] - wob) * (1 - wL) + Math.cos(lt * 0.7 + i) * 0.04 * wL;
      R.cur[0] += (tx - R.cur[0]) * k; R.cur[1] += (ty - R.cur[1]) * k; R.cur[2] += (tz - R.cur[2]) * k;
      R.piv.rotation.set(R.cur[0], R.cur[1] + lt * 0.05 * sp * mo * (1 - wL), R.cur[2]);
      const spin = R.spd * (1 + 5.5 * wT * (1 + 0.5 * Math.sin(lt * (1.3 + i)))) * sp * mo;
      R.m.rotation.z += dt * spin * 2;
      const sc = 1 - 0.22 * L * wL + wS * L * (0.2 + 0.06 * Math.sin(lt * 6 - i * 0.9)) + burst * 0.2 * (1 + i * 0.3);
      R.sc += (sc - R.sc) * Math.min(1, dt * 12); R.m.scale.setScalar(R.sc);
      R.U.uPhase.value += dt * (0.12 + 1.4 * wT + 0.4 * L * wS) * sp * mo * (i % 2 ? -1 : 1);
      R.U.uHeat.value = wT * 0.8 + L * wS * 0.6 + burst; R.U.uA.value = (0.75 + 0.25 * L) * this.dim;
    });
    // shell drift, halo, grid
    this.shell.rotation.y += dt * (0.06 + 0.25 * wT) * sp * mo; this.shell.rotation.z = 0.12 * Math.sin(lt * 0.3);
    this.halo.material.color.copy(this.col); this.halo.material.opacity = (0.12 + 0.1 * beat + 0.12 * L * (wS + wL * 0.5)) * this.dim;
    this.halo.scale.setScalar(6 + 1.4 * L * wS + burst * 1.5);
    this.haloIn.material.color.copy(this.col).lerp(_c.set('#ffffff'), 0.35 + 0.4 * wS); this.haloIn.material.opacity = (0.22 + 0.2 * beat - 0.1 * wS) * this.dim;
    this.haloIn.scale.setScalar(2 + 0.5 * L * (wS + wL) + burst * 0.6);
    this.pool.material.color.copy(this.col); this.pool.material.opacity = (0.08 + 0.08 * beat) * this.dim;
    this.gU.uPulse.value = bk >= 0 && bk < 1 ? bk : wS * L > 0.55 ? fract(this.wave * 0.5) : 0; this.gU.uA.value = (0.45 + 0.25 * L) * this.dim;
    // camera: a small drag orbit, a slow sway when idle, pointer parallax
    const o = this.orbit; o.idle += dt;
    if (!o.dragging) {
      o.yaw += o.vyaw; o.pitch += o.vpitch; o.vyaw *= 0.92; o.vpitch *= 0.92;
      if (o.idle > 2.5 && !red) { o.yaw += (Math.sin(lt * 0.21) * 0.18 - o.yaw) * Math.min(1, dt * 0.5); o.pitch += (0.12 + Math.sin(lt * 0.17) * 0.05 - o.pitch) * Math.min(1, dt * 0.5); }
    }
    o.yaw = clamp(o.yaw, o.min, o.max); o.pitch = clamp(o.pitch, o.pitchMin, o.pitchMax);
    const D = 6.4 - 0.25 * L * wL, cp = Math.cos(o.pitch), yaw = o.yaw + par.x * 0.06, pitch = o.pitch - par.y * 0.04;
    this.camera.position.set(Math.sin(yaw) * cp * D, Math.sin(pitch) * D - 0.1, Math.cos(yaw) * cp * D);
    this.camera.lookAt(_v.set(0, -0.15, 0));
  }
  dispose() { this.scene.background?.dispose?.(); this.ui?.remove(); super.dispose(); }
}
