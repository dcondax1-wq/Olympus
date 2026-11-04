// Month City (Results page): every month of the replay is a glowing tower on a glass floor.
//   rows = years (newest in front), columns = Jan..Dec, height ~ month net / max |net|.
//   Profits rise cyan -> green from the floor; losses hang below it in magenta, seen through the glass like a reflection
//   world. Gradient bodies with neon edges, lit windows, scrolling energy bands and bright caps; sparks rise from the best
//   months, a light beam marks the best one, a dashed ring the current month; the floor glows under every tower.
//   Drag to orbit (slow ping-pong orbit when idle); tap a tower for its tooltip ("2026-09 · +$7,042 · 10 trades · 5 wins"),
//   mouse hover does the same. Towers grow in time order on first data and morph when the data changes.
// Draw calls ~14 (all towers are one InstancedMesh); particles: sparks 36 per best month (16 lite) + 700 dust (260 lite).
import { metal } from '../../olympus/materials.js';
import { THREE, View, Q, theme, glowTexture, POINT_FRAG, rng, count } from './core.js';

const MONTH_LETTERS = 'JFMAMJJASOND';
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const smooth = (t) => t * t * (3 - 2 * t);
const outBack = (t) => { const u = t - 1; return 1 + 2.2 * u * u * u + 1.2 * u * u; };
const fract = (v) => v - Math.floor(v);
const num = (v, d = 0) => { const n = typeof v === 'string' ? parseFloat(v) : v; return Number.isFinite(n) ? n : d; };
const MINUS = '−';
const fmtUsd = (v) => (v < 0 && Math.round(-v) ? MINUS : '+') + '$' + Math.round(Math.abs(v)).toLocaleString('en-US');
const fmtK = (v) => { const a = Math.abs(v), s = v < 0 && Math.round(a) ? MINUS : '+'; return s + '$' + (a >= 9950 ? Math.round(a / 1000) + 'k' : a >= 1000 ? (a / 1000).toFixed(1) + 'k' : Math.round(a)); };
const _v = new THREE.Vector3(), _w = new THREE.Vector3(), _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _c = new THREE.Color();
const _box = new THREE.Box3(), _ndc = new THREE.Vector2(), _ext = [0, 0, 0, 0];
// backdrop colours (output space): the page colour when the skin is dark (neon needs a dark stage), a purple/accent glow
function paintBackdrop(U) {
  const pg = theme.page.clone().convertLinearToSRGB(), ac = theme.accent.clone().convertLinearToSRGB();
  const base = 0.2126 * pg.r + 0.7152 * pg.g + 0.0722 * pg.b < 0.22 ? pg : new THREE.Color(0.027, 0.031, 0.047);
  U.uBot.value.set(base.r * 0.9 + 0.005, base.g * 0.9 + 0.004, base.b * 0.9 + 0.012);
  U.uTop.value.set(base.r + 0.028, base.g + 0.012, base.b + 0.06);
  U.uGlow.value.set(0.03 + ac.r * 0.045, 0.014 + ac.g * 0.03, 0.06 + ac.b * 0.065);
}

// ------------------------------------------------------------------ shaders
const BG_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const BG_F = `uniform vec3 uTop; uniform vec3 uBot; uniform vec3 uGlow; uniform float uAsp; varying vec2 vUv;
void main(){
  vec3 c = mix(uBot, uTop, smoothstep(0.0, 1.0, vUv.y));
  vec2 q = (vUv - vec2(0.5, 0.6)) * vec2(min(uAsp, 1.5), 1.6); c += uGlow * exp(-dot(q, q) * 2.6);
  vec2 v = vUv - 0.5; c *= 1.0 - dot(v, v) * 0.85;
  c += (fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) - 0.5) / 255.0;
  gl_FragColor = vec4(c, 1.0);
}`;
const FLOOR_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
// glass floor: a light purple tint over the world below + cell grid + pads lit by the month under them + a sweep
const FLOOR_F = `uniform vec2 uHalf; uniform vec2 uCity; uniform vec2 uGrid; uniform vec2 uPitch; uniform sampler2D uCells; uniform float uTime; uniform float uMotion;
uniform float uIntro; uniform vec3 uGlass; uniform vec3 uLine; uniform vec3 uLine2;
varying vec3 vW;
void main(){
  vec2 p = vW.xz;
  vec2 cc = vec2(p.x / uPitch.x + uGrid.x * 0.5, p.y / uPitch.y + uGrid.y * 0.5);
  vec2 id = floor(cc), f = fract(cc), fw = max(fwidth(cc), vec2(1e-4));
  float inGrid = step(0.0, cc.x) * step(cc.x, uGrid.x) * step(0.0, cc.y) * step(cc.y, uGrid.y);
  vec2 dl = min(f, 1.0 - f) / fw;
  float lineAll = 1.0 - min(min(dl.x, dl.y), 1.0), line = lineAll * inGrid;
  float dOut = length(max(abs(p) - uCity, vec2(0.0))), world = exp(-dOut * 0.42) * (1.0 - inGrid);
  vec2 c2 = cc * 4.0, g2 = abs(fract(c2 - 0.5) - 0.5) / max(fwidth(c2), vec2(1e-4));
  float fine = (1.0 - min(min(g2.x, g2.y), 1.0)) * 0.12 * inGrid;
  vec4 cell = texture2D(uCells, (clamp(id, vec2(0.0), uGrid - 1.0) + 0.5) / uGrid) * inGrid;
  vec2 q = f - 0.5; float box = max(abs(q.x), abs(q.y));
  float has = step(0.002, cell.a);
  float padEdge = exp(-abs(box - 0.41) * 50.0) * has;
  float spill = exp(-dot(q, q) * 6.0) * cell.a;
  vec2 e = uHalf - abs(p); float fade = smoothstep(0.0, 1.5, min(e.x, e.y));
  float t = uTime * uMotion;
  float sweep = exp(-pow((p.y / uHalf.y) * 0.5 + 0.5 - fract(t * 0.055), 2.0) * 160.0) * uMotion;
  float r = length(p - vec2(0.0, uHalf.y)), R = uIntro * 18.0;
  float lit = mix(uIntro, 1.0, smoothstep(R, R - 2.5, r)), front = exp(-pow((r - R) * 1.4, 2.0)) * (1.0 - uIntro);
  vec3 lc = mix(uLine, uLine2, clamp(0.5 + 0.5 * sin(p.x * 0.35 + t * 0.3), 0.0, 1.0));
  vec3 col = uGlass + lc * ((line * (0.55 + sweep * 1.4) + fine * (1.0 + sweep) + lineAll * world * 0.5) * lit + front * 0.6)
    + cell.rgb * (spill * 0.7 + padEdge * 0.5) * lit;
  float a = clamp((0.3 + line * 0.35 + spill * 0.25 + padEdge * 0.3) * mix(1.0, world, 1.0 - inGrid) + lineAll * world * 0.3 + front * 0.3, 0.0, 1.0) * fade;
  gl_FragColor = vec4(col, a);
}`;
const TOWER_V = `attribute vec4 aInfo; attribute vec3 aCol;
uniform float uSel; uniform float uHov;
varying vec3 vCol; varying vec3 vL; varying vec3 vS; varying vec3 vN; varying float vT; varying float vHi; varying float vSeed; varying float vSign; varying float vV; varying float vY;
void main(){
  vec3 s = vec3(length(instanceMatrix[0].xyz), length(instanceMatrix[1].xyz), length(instanceMatrix[2].xyz));
  vec4 w = modelMatrix * instanceMatrix * vec4(position, 1.0);
  vL = position * s; vS = s; vN = normal; vSign = aInfo.x; vV = aInfo.y; vSeed = aInfo.w; vCol = aCol; vY = w.y;
  vT = aInfo.x > 0.0 ? position.y : 1.0 - position.y;
  vHi = max(1.0 - step(0.5, abs(aInfo.z - uSel)), (1.0 - step(0.5, abs(aInfo.z - uHov))) * 0.6);
  gl_Position = projectionMatrix * viewMatrix * w;
}`;
const TOWER_F = `uniform float uTime; uniform float uMotion; uniform float uCamY;
varying vec3 vCol; varying vec3 vL; varying vec3 vS; varying vec3 vN; varying float vT; varying float vHi; varying float vSeed; varying float vSign; varying float vV; varying float vY;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main(){
  vec3 hs = vS * 0.5;
  float dx = hs.x - abs(vL.x), dz = hs.z - abs(vL.z), dy = min(vL.y, vS.y - vL.y);
  float m1 = min(dx, min(dy, dz)), m3 = max(dx, max(dy, dz)), m2 = dx + dy + dz - m1 - m3;
  float aa = fwidth(m2) + 1e-4;
  float edge = 1.0 - smoothstep(0.008, 0.008 + aa * 1.5, m2);
  float eglow = exp(-m2 * 22.0);
  float tip = step(0.5, vN.y * vSign), side = 1.0 - abs(vN.y);
  float shade = abs(vN.z) + abs(vN.x) * 0.72 + abs(vN.y) * 0.9;
  float g = pow(vT, 1.2), d = vT * vS.y, t = uTime * uMotion;
  vec3 hot = mix(vCol, vec3(1.0), 0.4);
  vec3 body = vCol * mix(0.1, 0.62, g) * shade;
  // lit windows: two columns per face, a floor every 0.17 units, ~60 % lit, faded out when smaller than a pixel
  float u = (abs(vN.x) > 0.5 ? vL.z / vS.z : vL.x / vS.x) + 0.5;
  vec2 wc = vec2(u * 2.0, d / 0.17), wi = floor(wc), wf = fract(wc);
  vec2 ww = max(fwidth(wc), vec2(1e-4));
  float win = smoothstep(0.2, 0.2 + ww.x, wf.x) * smoothstep(0.8, 0.8 - ww.x, wf.x) * smoothstep(0.28, 0.28 + ww.y, wf.y) * smoothstep(0.78, 0.78 - ww.y, wf.y);
  float lod = clamp(1.6 - max(ww.x, ww.y) * 3.0, 0.0, 1.0);
  float hh = hash(wi + vec2(vSeed * 91.0, vN.x * 7.0 + vN.z * 13.0));
  float on = step(0.4, hh) * (0.75 + 0.25 * sin(t * (0.5 + hh * 2.0) + hh * 40.0));
  win = mix(0.22, win * on, lod) * side * step(0.12, d) * step(0.06, vS.y - d);
  float band = smoothstep(0.86, 1.0, fract(d * 1.6 - t * 0.45 + vSeed * 7.0)) * side;
  vec3 col = body + hot * win * (0.22 + 0.4 * g) + vCol * band * (0.15 + 0.3 * g)
    + hot * (edge * (0.3 + 0.75 * g) + eglow * 0.18 * g) + hot * tip * (0.5 + 0.45 * vV);
  col *= 1.0 + vHi * 0.6;
  col = mix(col, vec3(1.3), vHi * edge * 0.55);
  if (vY * uCamY < -0.001) col = col * 0.88 + vec3(0.02, 0.0, 0.05);  // seen through the glass
  gl_FragColor = vec4(min(col, vec3(1.4)), 1.0);
}`;
const CAP_V = `attribute vec3 aCol; attribute float aSize; attribute float aA;
uniform float uPix; uniform float uTime; uniform float uMotion; uniform float uCamY;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(aSize * uPix / -mv.z, 0.0, 160.0); gl_Position = projectionMatrix * mv;
  vColor = aCol * (position.y * uCamY < 0.0 ? 0.6 : 1.0); vAlpha = aA * (0.85 + 0.15 * sin(uTime * 2.0 * uMotion + position.x * 3.0)); }`;
const SPARK_V = `attribute vec3 aCol; attribute float aSeed; attribute float aK;
uniform float uPix; uniform float uTime; uniform float uMotion;
varying vec3 vColor; varying float vAlpha;
void main(){
  float t = uTime * uMotion;
  float ph = fract(t * (0.2 + aSeed * 0.25) + aSeed * 9.7);
  float ang = aSeed * 50.0 + t * (0.8 + aSeed);
  float rad = 0.04 + 0.32 * ph * (0.4 + aSeed);
  vec3 p = position + vec3(cos(ang) * rad, 0.06 + ph * (1.0 + 1.6 * aK), sin(ang) * rad);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp((0.06 + 0.09 * (1.0 - ph)) * uPix / -mv.z, 0.0, 40.0);
  gl_Position = projectionMatrix * mv;
  vColor = mix(vec3(1.0), aCol, clamp(ph * 1.4, 0.0, 1.0)) * 1.4;
  vAlpha = aK * pow(1.0 - ph, 1.3) * smoothstep(0.0, 0.07, ph);
}`;
const DUST_V = `attribute vec3 aCol; attribute float aSize; attribute float aSeed;
uniform float uTime; uniform float uPix; uniform float uMotion; uniform vec2 uSpan;
varying vec3 vColor; varying float vAlpha;
void main(){
  float t = uTime * uMotion; vec3 p = position;
  p.y = mod(p.y - uSpan.x + t * (0.07 + aSeed * 0.12), uSpan.y) + uSpan.x;
  p.x += sin(t * 0.2 + aSeed * 30.0) * 0.25; p.z += cos(t * 0.17 + aSeed * 21.0) * 0.25;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp(aSize * uPix / -mv.z, 0.0, 48.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol * (p.y < 0.0 ? 0.55 : 1.0);
  vAlpha = smoothstep(uSpan.x, uSpan.x + 0.8, p.y) * smoothstep(uSpan.x + uSpan.y, uSpan.x + uSpan.y - 1.2, p.y) * (0.6 + 0.4 * sin(t + aSeed * 40.0));
}`;
// light traffic running along the streets between the cells (3 points per car = a short comet trail)
const CAR_V = `attribute vec4 aLane; attribute vec3 aCol; attribute float aK;
uniform float uTime; uniform float uPix; uniform float uMotion; uniform vec2 uGrid; uniform vec2 uPitch; uniform float uOn;
varying vec3 vColor; varying float vAlpha;
void main(){
  float s = fract(aLane.w + uTime * aLane.z - aK * 0.011 * sign(aLane.z));
  vec3 p;
  if (aLane.x < 0.5) { float k = floor(aLane.y * (uGrid.y + 1.0)); p = vec3((s - 0.5) * uGrid.x * uPitch.x, 0.025, (k - uGrid.y * 0.5) * uPitch.y); }
  else { float k = floor(aLane.y * (uGrid.x + 1.0)); p = vec3((k - uGrid.x * 0.5) * uPitch.x, 0.025, (s - 0.5) * uGrid.y * uPitch.y); }
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp((0.1 - aK * 0.028) * uPix / -mv.z, 0.0, 24.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol * (1.25 - aK * 0.35); vAlpha = smoothstep(0.0, 0.05, s) * smoothstep(1.0, 0.95, s) * uOn;
}`;
const BEAM_V = `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`;
const BEAM_F = `uniform vec3 uCol; uniform float uTime; uniform float uMotion; uniform float uA; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){
  float f = 1.0 - abs(dot(vN, vV)); float fade = pow(1.0 - vUv.y, 1.5);
  float t = uTime * uMotion;
  float stripes = 0.65 + 0.35 * sin(vUv.y * 40.0 - t * 4.0);
  gl_FragColor = vec4(uCol * (0.16 + f * f * 1.1) * fade * stripes * uA, 1.0);
}`;
const RING_V = `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const RING_F = `uniform vec3 uCol; uniform float uTime; uniform float uA; uniform float uDash; varying vec2 vP;
void main(){ float a = atan(vP.y, vP.x) / 6.2831853; float d = uDash > 0.0 ? step(0.45, fract(a * uDash + uTime * 0.12)) : 1.0;
  gl_FragColor = vec4(uCol * uA * d, 1.0); }`;

// ------------------------------------------------------------------ html overlay
const CSS = `.fxc-ui{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:2;font-family:inherit;-webkit-user-select:none;user-select:none;opacity:0;transition:opacity .8s ease}
.fxc-ui.on{opacity:1}
.fxc-l{position:absolute;left:0;top:0;white-space:nowrap;font-size:9px;font-weight:600;letter-spacing:.04em;line-height:1;color:rgba(188,192,236,.62);text-shadow:0 0 6px #07080c,0 0 2px #07080c}
.fxc-l.y{font-size:10px;font-weight:700;color:rgba(200,204,244,.74)}
.fxc-l.now{color:#a5f3fc}
.fxc-l.m{color:rgba(188,192,236,.5)}
.fxc-l.pos{color:#5eead4}.fxc-l.neg{color:#ff7ad9}
.fxc-l.big{font-size:10px;font-weight:700;padding:2px 5px;border-radius:6px;background:rgba(10,8,24,.6);text-shadow:none}
.fxc-leg{position:absolute;left:10px;top:9px;display:flex;flex-wrap:wrap;gap:4px 10px;font-size:9px;font-weight:600;letter-spacing:.03em;line-height:1;color:rgba(188,192,236,.6)}
.fxc-leg span{display:inline-flex;align-items:center;gap:4px}
.fxc-leg i{display:inline-block;width:5px;height:9px;border-radius:1.5px}
.fxc-tip{position:absolute;left:0;top:0;padding:6px 9px;border-radius:10px;background:rgba(13,10,28,.88);border:1px solid rgba(150,130,255,.3);color:#eef0fb;font-size:11px;font-weight:600;line-height:1.3;letter-spacing:0;white-space:nowrap;box-shadow:0 6px 22px rgba(0,0,0,.5),0 0 18px rgba(124,92,255,.22);opacity:0;transition:opacity .15s;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
.fxc-tip.on{opacity:1}.fxc-tip i{font-style:normal;color:rgba(188,192,236,.72)}
.fxc-empty{position:absolute;left:50%;top:46%;transform:translate(-50%,-50%);font-size:12px;color:rgba(188,192,236,.55);display:none}`;
function injectCss() {
  if (document.getElementById('fxc-css')) return;
  const s = document.createElement('style'); s.id = 'fxc-css'; s.textContent = CSS; document.head.appendChild(s);
}
const additive = (vertexShader, fragmentShader, uniforms, extra = {}) => new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, ...extra });
function attrs(n, spec, geo = new THREE.BufferGeometry(), Attr = THREE.BufferAttribute) {
  for (const k in spec) {
    const [size, dyn] = spec[k], a = new Attr(new Float32Array(Math.max(1, n) * size), size);
    if (dyn) a.setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute(k, a);
  }
  return geo;
}

// ------------------------------------------------------------------ the view
export class City extends View {
  constructor(opts = {}) {
    super({ fov: 36, dprMax: 2, env: 'night', ...opts,
      orbit: { yaw: -0.3, pitch: 0.6, auto: 0.045, min: -0.6, max: 0.6, pitchMin: 0.3, pitchMax: 1.0, ...(opts.orbit || {}) } });
    this.canvas.classList.add('fx-city'); this.canvas.style.display = 'block'; // inline canvases leave a baseline gap that can grow auto-height cards
    this.lt = 0; this.L = 18; this.sx = 0; this.sy = 0; this.Lset = false; this.T = new THREE.Vector3(0, 0.6, 0);
    this.PX = 0.86; this.PZ = 1.75; this.FW = 0.56; this.HMAX = 3; this.years = []; this.towers = []; this.byKey = new Map(); this.fitPts = new Float32Array(0);
    this.sig = ''; this.cap = 0; this.animating = false; this.introAt = -1; this.introDone = false; this.maxAbs = 1;
    this.sel = null; this.hov = null; this.selAt = 0; this._hoverAt = null; this.best = null; this.worst = null; this.latest = null;
    this.userRange = !!(opts.orbit && (opts.orbit.min != null || opts.orbit.max != null)); this.userPitch = !!(opts.orbit && opts.orbit.pitch != null);
    this.SP = count(36, 16);
    this.u = { uTime: { value: 0 }, uPix: { value: 500 }, uMotion: { value: Q.reduced ? 0 : 1 }, uCamY: { value: 1 }, uSel: { value: -1 }, uHov: { value: -1 } };
    this.ray = new THREE.Raycaster();
    this.buildWorld();
    this.ensureCap(80);
    this.buildUi();
    const c = this.canvas;
    c.style.cursor = 'grab';
    c.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse' || e.buttons) return;
      const r = c.getBoundingClientRect(); this._hoverAt = [e.clientX - r.left, e.clientY - r.top];
    });
    c.addEventListener('pointerleave', () => { this._hoverAt = null; this.setHover(null); });
  }
  // index.js does `view.opts = { ...view.opts, ...pageOpts }`: keep OUR screen-space pick wired to the canvas; a page
  // onPick is optional here and gets the tapped month ({ month, net, trades, wins })
  get opts() { return this._o; }
  set opts(o) {
    o = o || {};
    if (!this._pickFn) this._pickFn = (x, y, e) => this.pick(x, y, e);
    if (typeof o.onPick === 'function' && o.onPick !== this._pickFn) this._onRow = o.onPick;
    this._o = { ...o, onPick: this._pickFn };
  }

  // ---------------------------------------------------------------- scene
  buildWorld() {
    const S = this.scene, R = rng(41), u = this.u;
    this.bgU = { uTop: { value: new THREE.Vector3(0.045, 0.024, 0.09) }, uBot: { value: new THREE.Vector3(0.014, 0.012, 0.028) },
      uGlow: { value: new THREE.Vector3(0.06, 0.03, 0.12) }, uAsp: { value: 1 } };
    paintBackdrop(this.bgU);
    const bg = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({ uniforms: this.bgU, vertexShader: BG_V, fragmentShader: BG_F, depthTest: false, depthWrite: false }));
    bg.renderOrder = -10; S.add(bg);
    for (const [c, x, y, z, s, sy, o] of [['#6d28d9', -6, 4.5, -10, 18, 10, 0.12], ['#2b5cff', 6, 5, -11, 16, 9, 0.08], ['#ff2bd6', 0, -3.4, -5, 18, 6, 0.07],
      ['#8b5cf6', 0, 0.8, -10, 32, 3.2, 0.12]]) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(c), transparent: true, opacity: o, blending: THREE.AdditiveBlending, depthWrite: false }));
      sp.position.set(x, y, z); sp.scale.set(s, sy, 1); S.add(sp);
    }
    // dust motes drifting up through the city (dimmer under the floor)
    const N = count(Q.phone ? 600 : 700, 260), dg = attrs(N, { position: [3], aCol: [3], aSize: [1], aSeed: [1] }), A = dg.attributes;
    const pal = ['#22d3ee', '#8b5cf6', '#c4b5fd', '#2ee59d', '#ff2bd6'].map((h) => new THREE.Color(h));
    for (let i = 0; i < N; i++) {
      const far = R() < 0.3;
      A.position.setXYZ(i, (R() - 0.5) * (far ? 30 : 15), -2 + R() * 7, far ? -7 - R() * 8 : (R() - 0.5) * 10);
      _c.copy(pal[(R() * pal.length) | 0]).multiplyScalar((far ? 0.3 : 0.22) + R() * 0.3); A.aCol.setXYZ(i, _c.r, _c.g, _c.b);
      A.aSize.setX(i, far ? 0.05 + R() * 0.06 : 0.025 + R() * 0.045); A.aSeed.setX(i, R());
    }
    this.dU = { ...u, uSpan: { value: new THREE.Vector2(-2.2, 7.5) } };
    this.dust = new THREE.Points(dg, additive(DUST_V, POINT_FRAG, this.dU)); this.dust.renderOrder = 3; S.add(this.dust);
    // glass floor (normal blending, light tint: the losses below stay readable through it)
    this.cellTex = null;
    this.fU = { uTime: u.uTime, uMotion: u.uMotion, uHalf: { value: new THREE.Vector2(6, 4) }, uCity: { value: new THREE.Vector2(6, 4) }, uGrid: { value: new THREE.Vector2(12, 6) },
      uPitch: { value: new THREE.Vector2(1, 1.4) }, uCells: { value: null }, uIntro: { value: 1 },
      uGlass: { value: new THREE.Vector3(0.05, 0.035, 0.11) }, uLine: { value: new THREE.Color('#6d5cff') }, uLine2: { value: new THREE.Color('#22d3ee') } };
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({ uniforms: this.fU, vertexShader: FLOOR_V, fragmentShader: FLOOR_F,
      transparent: true, depthWrite: false, side: THREE.DoubleSide, extensions: { derivatives: true } }));
    this.floor.rotation.x = -Math.PI / 2; this.floor.renderOrder = 1; S.add(this.floor);
    // OLYMPUS materials: a chrome frame round the plot with gold corner posts (2 draws, env reflections)
    this.frameBars = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), metal({ kind: 'chrome', envMapIntensity: 3 }), 4);
    this.frameCorners = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.5, 0.5, 1, 20), metal({ kind: 'gold', brushed: false, roughness: 0.2, envMapIntensity: 3 }), 4);
    this.frameBars.frustumCulled = this.frameCorners.frustumCulled = false; S.add(this.frameBars, this.frameCorners);
    // street traffic
    const NC = Q.reduced ? 0 : count(Q.phone ? 110 : 150, 50), cg = attrs(NC * 3, { position: [3], aLane: [4], aCol: [3], aK: [1] }), CA = cg.attributes;
    const cpal = ['#22d3ee', '#7df3ff', '#8b5cf6', '#ff2bd6', '#2ee59d'].map((h) => new THREE.Color(h));
    for (let i = 0; i < NC; i++) {
      const lane = [R() < 0.55 ? 0 : 1, R(), (0.025 + R() * 0.045) * (R() < 0.5 ? -1 : 1), R()], c = cpal[R() < 0.6 ? (R() * 2) | 0 : 2 + ((R() * 3) | 0)];
      for (let k = 0; k < 3; k++) { CA.aLane.setXYZW(i * 3 + k, ...lane); CA.aCol.setXYZ(i * 3 + k, c.r, c.g, c.b); CA.aK.setX(i * 3 + k, k); }
    }
    this.carU = { uTime: u.uTime, uPix: u.uPix, uMotion: u.uMotion, uGrid: this.fU.uGrid, uPitch: this.fU.uPitch, uOn: { value: 0 } };
    this.cars = new THREE.Points(cg, additive(CAR_V, POINT_FRAG, this.carU)); this.cars.renderOrder = 2; S.add(this.cars);
    // caps, sparks (geometry sized with the data)
    this.caps = new THREE.Points(new THREE.BufferGeometry(), additive(CAP_V, POINT_FRAG, u)); this.caps.renderOrder = 4; S.add(this.caps);
    this.sparks = new THREE.Points(new THREE.BufferGeometry(), additive(SPARK_V, POINT_FRAG, u)); this.sparks.renderOrder = 5; S.add(this.sparks);
    // beam over the best month, dashed ring on the current month, selection ring
    const cyl = new THREE.CylinderGeometry(0.3, 0.3, 1, 28, 1, true); cyl.translate(0, 0.5, 0);
    this.bU = { uTime: u.uTime, uMotion: u.uMotion, uCol: { value: new THREE.Color('#3df5b4') }, uA: { value: 0 } };
    this.beam = new THREE.Mesh(cyl, additive(BEAM_V, BEAM_F, this.bU, { side: THREE.DoubleSide })); this.beam.renderOrder = 6; this.beam.visible = false; S.add(this.beam);
    const ring = (dash, col, order) => {
      const U = { uTime: u.uTime, uCol: { value: new THREE.Color(col) }, uA: { value: 0 }, uDash: { value: dash } };
      const m = new THREE.Mesh(new THREE.RingGeometry(0.9, 1, 64), additive(RING_V, RING_F, U, { side: THREE.DoubleSide }));
      m.rotation.x = -Math.PI / 2; m.renderOrder = order; m.visible = false; m.userData.U = U; S.add(m); return m;
    };
    this.nowRing = ring(16, '#7df3ff', 2);
    this.selRing = ring(0, '#ffffff', 2);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(80, Math.ceil(n * 1.25 / 16) * 16);
    const box = new THREE.BoxGeometry(1, 1, 1); box.translate(0, 0.5, 0);
    attrs(cap, { aInfo: [4], aCol: [3] }, box, THREE.InstancedBufferAttribute);
    const mat = this.towersMesh?.material || new THREE.ShaderMaterial({ uniforms: this.u, vertexShader: TOWER_V, fragmentShader: TOWER_F, extensions: { derivatives: true } });
    if (this.towersMesh) { this.scene.remove(this.towersMesh); this.towersMesh.geometry.dispose(); this.towersMesh.dispose?.(); }
    const mesh = new THREE.InstancedMesh(box, mat, cap); mesh.count = 0; mesh.frustumCulled = false; mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.scene.add(mesh); this.towersMesh = mesh; this.cap = cap;
  }
  buildUi() {
    injectCss();
    const ui = this.ui = document.createElement('div'); ui.className = 'fxc-ui'; ui.setAttribute('aria-hidden', 'true');
    this.tip = document.createElement('div'); this.tip.className = 'fxc-tip';
    this.empty = document.createElement('div'); this.empty.className = 'fxc-empty'; this.empty.textContent = 'No months yet';
    const leg = document.createElement('div'); leg.className = 'fxc-leg';
    leg.innerHTML = '<span><i style="background:linear-gradient(#2ee59d,#22d3ee);box-shadow:0 0 6px #2ee59d"></i>profit month</span>'
      + '<span><i style="background:linear-gradient(#b026ff,#ff2bd6);box-shadow:0 0 6px #ff2bd6"></i>loss month (under the glass)</span>';
    ui.append(leg, this.empty, this.tip);
    this.labels = []; this.tipFor = null; this.tipLast = ''; this.camKey = '';
  }
  attach(el) {
    super.attach(el);
    if (!el) return;
    try { if (getComputedStyle(el).position === 'static') el.style.position = 'relative'; } catch { }
    if (this.ui.parentNode !== el) el.appendChild(this.ui);
    for (const l of this.labels) l.wid = null;
    this.camKey = '';
  }
  detach() { super.detach(); this.ui?.remove(); }
  dispose() { this.ui?.remove(); this.cellTex?.dispose(); super.dispose(); }
  // proportions follow the card: narrower streets and taller towers on a square phone card, wider avenues on desktop
  shape(w, h) {
    const asp = w / h, PX = 0.86 * Math.pow(clamp(asp / 1.05, 1, 2.2), 0.55), PZ = 1.4 * clamp(1.75 / asp, 1, 1.25), HMAX = 3.6 * clamp(1.2 / asp, 0.72, 1);
    const changed = Math.abs(PX - this.PX) > 0.02 || Math.abs(PZ - this.PZ) > 0.02 || Math.abs(HMAX - this.HMAX) > 0.02;
    this.PX = PX; this.PZ = PZ; this.FW = Math.min(0.62, 0.56 * Math.sqrt(PX / 0.86)); this.HMAX = HMAX;
    return changed;
  }
  onResize(w, h) {
    const dpr = this.renderer.getPixelRatio();
    this.u.uPix.value = h * dpr / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2));
    this.bgU.uAsp.value = w / h;
    if ((this.shape(w, h) || !this.framed) && this.towers.length) { this.layout(true); this.writeStatic(); this.frameLayout(); }
    this.framed = true;
    if (!this.userRange) { const r = 0.6 / clamp((w / h) / 1.4, 1, 1.35); this.orbit.min = -r; this.orbit.max = r; }
    if (!this.userPitch && this.orbit.idle > 50) this.orbit.pitch = w / h < 1.4 ? 0.74 : 0.6;
    this.Lset = false; this.camKey = '';
  }

  // ---------------------------------------------------------------- data
  setData(months, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    let src = months;
    if (Array.isArray(src)) src = Object.fromEntries(src.filter(Boolean).map((m) => [m.month || m.key || m.ym, m]));
    if (!src || typeof src !== 'object') src = {};
    const keys = Object.keys(src).filter((k) => /^\d{4}-\d{2}$/.test(k) && src[k]).sort();
    let sig = keys.length + ':';
    const rows = keys.map((k) => { const m = src[k]; const r = { key: k, year: +k.slice(0, 4), month: clamp(+k.slice(5, 7) - 1, 0, 11), net: num(m.net), trades: num(m.trades), wins: num(m.wins), src: m }; sig += k + (r.net | 0) + '/' + r.trades + ','; return r; });
    if (sig === this.sig) { for (const r of rows) { const t = this.byKey.get(r.key); if (t) t.src = r.src; } return; }
    this.sig = sig;
    this.years = [...new Set(rows.map((r) => r.year))].sort((a, b) => a - b);
    this.maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.net)));
    const first = !this.towers.length && !this.introDone, now = this.lt, red = Q.reduced, n = rows.length;
    const next = [], keep = new Set();
    rows.forEach((r, i) => {
      let t = this.byKey.get(r.key);
      if (t && !t.dead) { t.h0 = t.hs; t.col0.copy(t.col); t.x0 = t.x; t.z0 = t.z; t.t0 = now; t.dur = red ? 0 : 0.9; t.ease = 0; }
      else {
        t = { key: r.key, h: 0, hs: 0, h0: 0, cs: 0, x: 0, z: 0, x0: null, z0: null, dead: false, col: new THREE.Color(), col0: new THREE.Color(), idx: 0 };
        t.t0 = now + (first ? 0.25 + (i / Math.max(1, n - 1)) * 1.7 : 0.1 + (r.month / 11) * 0.35); t.dur = first ? 0.95 : 0.7; t.ease = 1;
        if (red) { t.t0 = now; t.dur = 0; }
      }
      Object.assign(t, { year: r.year, month: r.month, net: r.net, trades: r.trades, wins: r.wins, src: r.src, done: false });
      t.sign = r.net >= 0 ? 1 : -1; t.v = Math.abs(r.net) / this.maxAbs; if (!t.cs) t.cs = t.sign;
      t.seed = fract(Math.sin(i * 12.9898 + r.year) * 43758.5453);
      keep.add(r.key); next.push(t);
    });
    for (const t of this.towers) {
      if (keep.has(t.key) || t.dead) continue;
      t.dead = true; t.done = false; t.h0 = t.hs; t.x0 = t.x; t.z0 = t.z; t.t0 = now; t.dur = red ? 0 : 0.5; t.ease = 0;
      next.push(t);
    }
    this.towers = next; this.byKey.clear();
    for (const t of next) if (!t.dead) this.byKey.set(t.key, t);
    const live = next.filter((t) => !t.dead);
    this.best = live.reduce((b, t) => (t.net > 0 && (!b || t.net > b.net) ? t : b), null);
    this.worst = live.reduce((b, t) => (t.net < 0 && (!b || t.net < b.net) ? t : b), null);
    this.latest = live.length ? live.reduce((b, t) => (t.key > b.key ? t : b)) : null;
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.setHover(null);
    this.layout(false);
    this.recolor(); this.writeStatic(); this.buildCells(); this.buildSparks();
    if (first && n) { this.introAt = red ? -1 : now; this.introDone = true; }
    this.frameLayout();
    this.empty.style.display = n ? 'none' : 'block';
    this.ui.classList.add('on');
  }
  // grid positions (rows = years, newest in front) and target heights; `glide` re-animates towers already standing
  layout(glide) {
    const rows = this.years.length, PX = this.PX, now = this.lt;
    for (const t of this.towers) {
      const r = this.years.indexOf(t.year), x1 = (t.month - 5.5) * PX, z1 = (r < 0 ? t.z : (r - (rows - 1) / 2) * this.PZ);
      t.h1 = t.dead ? 0 : t.sign * (t.net === 0 ? 0.02 : Math.max(0.035, t.v * this.HMAX));
      if (t.x0 == null || t.dur === 0) { t.x = t.x0 = x1; t.z = t.z0 = z1; }
      else if (glide) { t.x0 = t.x; t.z0 = t.z; t.h0 = t.hs; t.col0.copy(t.col); t.t0 = now; t.dur = Q.reduced ? 0 : 0.6; t.done = false; t.ease = 0; }
      t.x1 = x1; t.z1 = z1;
    }
    this.animating = true;
  }
  recolor() {
    const lossLo = new THREE.Color('#b026ff');
    for (const t of this.towers) {
      if (t.sign > 0) t.col.copy(theme.cyan).lerp(theme.good, clamp(t.v * 1.4, 0, 1)).multiplyScalar(1.05 + 0.25 * t.v);
      else t.col.copy(lossLo).lerp(theme.magenta, clamp(0.35 + t.v * 1.6, 0, 1)).multiplyScalar(1.3);
    }
  }
  retheme() { paintBackdrop(this.bgU); if (this.towers.length) { this.recolor(); this.writeStatic(); this.buildCells(); this.buildSparks(); } }
  writeStatic() {
    const n = this.towers.length; this.ensureCap(n);
    const g = this.towersMesh.geometry, I = g.attributes.aInfo, C = g.attributes.aCol;
    for (let i = 0; i < n; i++) { const t = this.towers[i], c = t.col; t.idx = i; I.setXYZW(i, t.sign, t.v, i, t.seed); C.setXYZ(i, c.r, c.g, c.b); }
    I.needsUpdate = C.needsUpdate = true; this.towersMesh.count = n;
    // cap glows: one per tower
    const cg = attrs(n, { position: [3, 1], aCol: [3], aSize: [1], aA: [1] }), A = cg.attributes;
    for (let i = 0; i < n; i++) {
      const t = this.towers[i], c = t.col;
      A.aCol.setXYZ(i, c.r, c.g, c.b); A.aSize.setX(i, (0.42 + 1.25 * Math.sqrt(t.v)) * this.FW / 0.56); A.aA.setX(i, t.dead ? 0 : 0.2 + 0.6 * t.v);
    }
    this.caps.geometry.dispose(); this.caps.geometry = cg;
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
    // camera anchors: the four top corners of every tower (at its final height) - see frame()
    const FW = this.FW / 2, live = this.towers.filter((t) => !t.dead), P = new Float32Array(live.length * 12 + 24);
    live.forEach((t, i) => { const y = t.h1; P.set([t.x1 - FW, y, t.z1 - FW, t.x1 + FW, y, t.z1 - FW, t.x1 - FW, y, t.z1 + FW, t.x1 + FW, y, t.z1 + FW], i * 12); });
    const rows = Math.max(1, this.years.length), hl = 6 * this.PX + 0.95, hr = 6 * this.PX + 1.0, hz = rows * this.PZ / 2, o = live.length * 12;
    const top = this.best ? Math.abs(this.best.h1) + 0.75 : 0.5;
    P.set([-hl, 0, -hz - 0.35, hr, 0, -hz - 0.35, -hl, 0, hz + 0.8, hr, 0, hz + 0.8, this.best ? this.best.x1 : 0, top, this.best ? this.best.z1 : 0, 0, -0.6, 0], o);
    this.fitPts = P;
    this.animating = true; // positions / matrices are (re)written by the next animate()
  }
  // floor light: per-cell colour + intensity texture sampled by the glass shader
  buildCells() {
    const rows = Math.max(1, this.years.length), data = new Uint8Array(12 * rows * 4);
    for (const t of this.towers) {
      if (t.dead) continue;
      const r = this.years.indexOf(t.year); if (r < 0) continue;
      const o = (r * 12 + t.month) * 4, k = 0.4 + 0.6 * t.v;
      data[o] = clamp(t.col.r * k, 0, 1) * 255; data[o + 1] = clamp(t.col.g * k, 0, 1) * 255; data[o + 2] = clamp(t.col.b * k, 0, 1) * 255;
      data[o + 3] = Math.max(10, (0.3 + 0.7 * t.v) * 255);
    }
    if (!this.cellTex || this.cellTex.image.height !== rows) {
      this.cellTex?.dispose();
      this.cellTex = new THREE.DataTexture(data, 12, rows, THREE.RGBAFormat);
      this.cellTex.magFilter = this.cellTex.minFilter = THREE.NearestFilter;
    } else this.cellTex.image.data.set(data);
    this.cellTex.needsUpdate = true;
    this.fU.uCells.value = this.cellTex; this.fU.uGrid.value.set(12, rows);
  }
  // sparks rise from the best months (top 5 profits, at least 35 % of the best)
  buildSparks() {
    const live = this.towers.filter((t) => !t.dead && t.sign > 0 && t.v >= 0.35).sort((a, b) => b.net - a.net).slice(0, 5);
    const n = live.length * this.SP, g = attrs(n, { position: [3, 1], aCol: [3], aSeed: [1], aK: [1] }), A = g.attributes, R = rng(77);
    this.sparkOf = [];
    live.forEach((t, j) => {
      for (let k = 0; k < this.SP; k++) {
        const i = j * this.SP + k; this.sparkOf[i] = t;
        A.aCol.setXYZ(i, t.col.r, t.col.g, t.col.b); A.aSeed.setX(i, R()); A.aK.setX(i, 0.4 + 0.6 * t.v);
      }
    });
    g.setDrawRange(0, n); this.sparks.geometry.dispose(); this.sparks.geometry = g;
    this.animating = true;
  }
  // per-frame tower animation -> instance matrices, cap glow and spark anchors
  animate() {
    const now = this.lt, FW = this.FW; let busy = false, dead = false;
    for (const t of this.towers) {
      if (!t.done) {
        const k = t.dur > 0 ? clamp((now - t.t0) / t.dur, 0, 1) : 1, e = t.ease ? (k > 0 ? outBack(k) : 0) : smooth(k);
        t.hs = t.h0 + (t.h1 - t.h0) * e; t.h = Math.abs(t.hs); t.cs = t.hs > 1e-4 ? 1 : t.hs < -1e-4 ? -1 : (t.h1 >= 0 ? 1 : -1);
        const ke = smooth(k); t.x = t.x0 + (t.x1 - t.x0) * ke; t.z = t.z0 + (t.z1 - t.z0) * ke;
        if (k >= 1) { t.done = true; t.x0 = t.x = t.x1; t.z0 = t.z = t.z1; } else busy = true;
      }
      dead ||= t.dead && t.done;
    }
    if (!busy && dead) { this.towers = this.towers.filter((t) => !t.dead); this.writeStatic(); this.buildSparks(); }
    const mesh = this.towersMesh, caps = this.caps.geometry.attributes, I = mesh.geometry.attributes.aInfo, C = mesh.geometry.attributes.aCol;
    for (let i = 0; i < this.towers.length; i++) {
      const t = this.towers[i], h = Math.max(t.h, 1e-4), c = t.cs === t.sign ? t.col : t.col0;
      _w.set(t.x, t.cs > 0 ? 0 : -h, t.z); _s.set(FW, h, FW);
      mesh.setMatrixAt(i, _m.compose(_w, _q, _s));
      I.setX(i, t.cs); C.setXYZ(i, c.r, c.g, c.b); caps.aCol.setXYZ(i, c.r, c.g, c.b);
      caps.position.setXYZ(i, t.x, t.cs > 0 ? h + 0.06 : -h - 0.06, t.z);
    }
    mesh.instanceMatrix.needsUpdate = I.needsUpdate = C.needsUpdate = caps.position.needsUpdate = caps.aCol.needsUpdate = true;
    const sp = this.sparks.geometry.attributes.position;
    if (sp && this.sparkOf) { for (let i = 0; i < this.sparkOf.length; i++) { const t = this.sparkOf[i]; sp.setXYZ(i, t.x, t.h, t.z); } sp.needsUpdate = true; }
    this.animating = busy;
  }

  // ---------------------------------------------------------------- floor size + labels
  frameLayout() {
    const rows = Math.max(1, this.years.length), PX = this.PX, hx = 6 * PX, hz = rows * this.PZ / 2;
    this.fU.uHalf.value.set(hx + 7, hz + 7); this.fU.uCity.value.set(hx + 0.12, hz + 0.12); this.fU.uPitch.value.set(PX, this.PZ); this.floor.scale.set(hx + 7, hz + 7, 1);
    { const o = this._fo || (this._fo = new THREE.Object3D()), X = hx + 0.34, Z = hz + 0.34, bars = [[0, -Z, 2 * X, 0.07, 0.07], [0, Z, 2 * X, 0.07, 0.07], [-X, 0, 0.07, 0.07, 2 * Z], [X, 0, 0.07, 0.07, 2 * Z]];
      bars.forEach((b, i) => { o.position.set(b[0], 0.02, b[1]); o.scale.set(b[2], b[3], b[4]); o.updateMatrix(); this.frameBars.setMatrixAt(i, o.matrix); });
      [[-X, -Z], [X, -Z], [-X, Z], [X, Z]].forEach((c, i) => { o.position.set(c[0], 0.17, c[1]); o.scale.set(0.24, 0.34, 0.24); o.updateMatrix(); this.frameCorners.setMatrixAt(i, o.matrix); });
      this.frameBars.instanceMatrix.needsUpdate = this.frameCorners.instanceMatrix.needsUpdate = true; }
    this.dust.scale.set(PX / 0.86, 1, 1);
    const defs = [], latestYear = this.years[this.years.length - 1];
    this.years.forEach((y, r) => {
      const z = (r - (rows - 1) / 2) * this.PZ;
      const tot = this.towers.reduce((s, t) => (t.dead || t.year !== y ? s : s + t.net), 0);
      defs.push({ text: String(y), p: new THREE.Vector3(-hx - 0.16, 0, z), ax: 1, cls: 'y' + (y === latestYear ? ' now' : '') });
      defs.push({ text: fmtK(tot), p: new THREE.Vector3(hx + 0.16, 0, z), ax: 0, cls: tot >= 0 ? 'pos' : 'neg' });
    });
    if (this.towers.length) for (let j = 0; j < 12; j++) defs.push({ text: MONTH_LETTERS[j], p: new THREE.Vector3((j - 5.5) * PX, 0, hz + 0.42), cls: 'm' });
    if (this.best) defs.push({ text: 'best ' + fmtK(this.best.net), tower: this.best, up: 0.45, cls: 'pos big', p: new THREE.Vector3() });
    if (this.worst) defs.push({ text: 'worst ' + fmtK(this.worst.net), tower: this.worst, floor: true, cls: 'neg big', p: new THREE.Vector3() });
    for (const l of this.labels) l.el.remove();
    this.labels = defs.map((d) => {
      const el = document.createElement('div'); el.className = 'fxc-l' + (d.cls ? ' ' + d.cls : ''); if (d.html) el.innerHTML = d.html; else el.textContent = d.text;
      this.ui.insertBefore(el, this.tip); return { ...d, el, last: '', wid: null };
    });
    this.camKey = '';
  }
  placeLabels() {
    const cam = this.camera, w = this.w, h = this.h, live = this.ui.isConnected;
    for (const l of this.labels) {
      if (l.wid == null && live) l.wid = l.el.offsetWidth || 20;
      if (l.tower) { const t = l.tower; l.p.set(t.x, l.floor ? 0 : t.cs > 0 ? t.h + l.up : -t.h + l.up, t.z + (l.floor ? this.PZ * 0.36 : 0)); }
      _v.copy(l.p).project(cam);
      const ax = l.ax ?? 0.5, wid = l.wid || 20;
      const x = clamp((_v.x + 1) / 2 * w - ax * wid, 4, Math.max(4, w - wid - 4)), y = (1 - _v.y) / 2 * h;
      const hidden = _v.z > 1 || y < 8 || y > h - 6 || (l.tower && l.tower.h < 0.05);
      const tf = hidden ? 'translate3d(-999px,-999px,0)' : `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0) translateY(-50%)`;
      if (tf !== l.last) { l.el.style.transform = tf; l.last = tf; }
    }
  }
  // camera framing for the current yaw / pitch: the smallest distance at which every anchor (tower tops, floor corners with
  // label margins) fits the card, plus an off-axis lens shift that centres them; eased every frame -> a gentle dolly
  framing(yaw, pitch) {
    const cam = this.camera, P = this.fitPts, n = P.length / 3, T = this.T;
    const tan = Math.tan(THREE.MathUtils.degToRad(cam.fov) / 2), mx = tan * cam.aspect * 0.93, my = tan * 0.86;
    const cp = Math.cos(pitch), zx = Math.sin(yaw) * cp, zy = Math.sin(pitch), zz = Math.cos(yaw) * cp;
    const xl = Math.hypot(zz, zx), xx = zz / xl, xz = -zx / xl, yx = zy * xz, yy = zz * xx - zx * xz, yz = -zy * xx;
    if (!this._cs || this._cs.length < P.length) this._cs = new Float32Array(P.length);
    const C = this._cs;
    for (let i = 0; i < n; i++) {
      const X = P[i * 3] - T.x, Y = P[i * 3 + 1] - T.y, Z = P[i * 3 + 2] - T.z;
      C[i * 3] = X * xx + Z * xz; C[i * 3 + 1] = X * yx + Y * yy + Z * yz; C[i * 3 + 2] = X * zx + Y * zy + Z * zz;
    }
    const ext = (L) => {
      let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
      for (let i = 0; i < n; i++) {
        const d = L - C[i * 3 + 2]; if (d < 0.5) return false;
        const X = C[i * 3] / d, Y = C[i * 3 + 1] / d;
        if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
      }
      _ext[0] = x0; _ext[1] = x1; _ext[2] = y0; _ext[3] = y1;
      return x1 - x0 <= 2 * mx && y1 - y0 <= 2 * my;
    };
    let lo = 2, hi = 120;
    if (!n) return [18, 0, 0];
    for (let k = 0; k < 20; k++) { const mid = (lo + hi) / 2; if (ext(mid)) hi = mid; else lo = mid; }
    ext(hi);
    return [hi, (_ext[0] + _ext[1]) / 2 / (tan * cam.aspect), (_ext[2] + _ext[3]) / 2 / tan];
  }

  // ---------------------------------------------------------------- picking + tooltip
  hit(px, py, slack) {
    const cam = this.camera; cam.updateMatrixWorld();
    _ndc.set(px / this.w * 2 - 1, -(py / this.h) * 2 + 1); this.ray.setFromCamera(_ndc, cam);
    const ray = this.ray.ray, hw = this.FW / 2;
    let best = null, bd = Infinity;
    for (const t of this.towers) {
      if (t.dead || t.h < 0.005) continue;
      _box.min.set(t.x - hw, t.cs > 0 ? 0 : -t.h, t.z - hw); _box.max.set(t.x + hw, t.cs > 0 ? t.h : 0, t.z + hw);
      if (ray.intersectBox(_box, _v)) { const d = _v.distanceToSquared(ray.origin); if (d < bd) { bd = d; best = t; } }
    }
    if (best) return best;
    // nothing under the finger: nearest tower (tip or base) within the slack radius, so small months stay tappable
    _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    let bp = slack * slack;
    for (const t of this.towers) {
      if (t.dead) continue;
      for (const y of [0, t.cs > 0 ? t.h : -t.h]) {
        _v.set(t.x, y, t.z).applyMatrix4(_m); if (_v.z > 1) continue;
        const dx = (_v.x + 1) / 2 * this.w - px, dy = (1 - _v.y) / 2 * this.h - py, d = dx * dx + dy * dy;
        if (d < bp) { bp = d; best = t; }
      }
    }
    return best;
  }
  pick(nx, ny) {
    const t = this.hit((nx + 1) / 2 * this.w, (1 - ny) / 2 * this.h, 22);
    this.select(t === this.sel ? null : t);
    if (t && this._onRow) { try { this._onRow({ ...(t.src || {}), month: t.key, net: t.net, trades: t.trades, wins: t.wins }); } catch (e) { console.warn('city onPick', e); } }
  }
  select(t) {
    this.sel = t; this.selAt = this.lt; this.u.uSel.value = t ? t.idx : -1;
    this.showTip(this.hov || t);
  }
  setHover(t) {
    if (t === this.hov) return;
    this.hov = t; this.u.uHov.value = t ? t.idx : -1; this.canvas.style.cursor = t ? 'pointer' : 'grab';
    this.showTip(t || this.sel);
  }
  showTip(t) {
    if (!t) { this.tip.classList.remove('on'); this.tipFor = null; return; }
    if (t !== this.tipFor) {
      const col = t.net >= 0 ? '#5eead4' : '#ff7ad9', tr = Math.round(t.trades), wn = Math.round(t.wins);
      this.tip.innerHTML = `${t.key} · <b style="color:${col}">${fmtUsd(t.net)}</b> · ${tr} trade${tr === 1 ? '' : 's'} · ${wn} win${wn === 1 ? '' : 's'}`;
      this.tipFor = t; this.tipW = this.tip.offsetWidth; this.tipH = this.tip.offsetHeight; this.tipLast = '';
    }
    this.tip.classList.add('on'); this.placeTip();
  }
  placeTip() {
    const t = this.tipFor; if (!t) return;
    _v.set(t.x, t.cs > 0 ? t.h : 0, t.z).project(this.camera);
    const sx = (_v.x + 1) / 2 * this.w, sy = (1 - _v.y) / 2 * this.h, tw = this.tipW || 200, th = this.tipH || 26;
    const x = clamp(sx - tw / 2, 6, Math.max(6, this.w - tw - 6)); let y = sy - th - 14; if (y < 6) y = sy + 14;
    const tf = `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0)`;
    if (tf !== this.tipLast) { this.tip.style.transform = tf; this.tipLast = tf; }
  }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const o = this.orbitStep(dt), T = this.T, cam = this.camera, cp = Math.cos(o.pitch), [L, sx, sy] = this.framing(o.yaw, o.pitch);
    const k = this.Lset ? Math.min(1, dt * 2) : 1; this.Lset = true;
    this.L += (L - this.L) * k; this.sx += (sx - this.sx) * k; this.sy += (sy - this.sy) * k;
    cam.position.set(T.x + Math.sin(o.yaw) * cp * this.L, T.y + Math.sin(o.pitch) * this.L, T.z + Math.cos(o.yaw) * cp * this.L);
    cam.lookAt(T); cam.updateMatrixWorld();
    cam.updateProjectionMatrix(); // re-derive, then apply the lens shift
    const pe = cam.projectionMatrix.elements; pe[8] += this.sx; pe[9] += this.sy; cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
    u.uCamY.value = cam.position.y;
    if (this.animating) this.animate();
    if (this.introAt >= 0) { const q = (lt - this.introAt) / 2.2; this.fU.uIntro.value = clamp(q, 0, 1); if (q >= 1) this.introAt = -1; }
    this.carU.uOn.value = Math.min(this.towers.length ? 1 : 0, this.carU.uOn.value + dt * 0.5) * this.fU.uIntro.value;
    // beam over the best month
    const b = this.best;
    if (b && !b.dead && b.h > 0.05) {
      this.beam.visible = true; this.beam.position.set(b.x, b.h, b.z); this.beam.scale.set(this.FW * 1.75, 3.6, this.FW * 1.75);
      this.bU.uA.value = clamp(b.h / b.h1, 0, 1) * (Q.reduced ? 0.7 : 0.8 + 0.2 * Math.sin(lt * 1.7)); this.bU.uCol.value.copy(b.col);
    } else this.beam.visible = false;
    // dashed ring around the current month, pulsing ring under the selection
    const nw = this.latest, cell = Math.min(this.PX, this.PZ) * 0.47;
    if (nw && !nw.dead) { this.nowRing.visible = true; this.nowRing.position.set(nw.x, 0.012, nw.z); this.nowRing.scale.setScalar(cell); this.nowRing.userData.U.uA.value = 0.6 + (Q.reduced ? 0 : 0.25 * Math.sin(lt * 2.4)); }
    else this.nowRing.visible = false;
    const s = this.sel;
    if (s && !s.dead) {
      const ph = Q.reduced ? 0.5 : fract((lt - this.selAt) * 0.9);
      this.selRing.visible = true; this.selRing.position.set(s.x, 0.014, s.z); this.selRing.scale.setScalar(cell * (0.75 + ph * 0.6)); this.selRing.userData.U.uA.value = (1 - ph) * 0.9;
    } else this.selRing.visible = false;
    // html
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.setHover(this.hit(hx, hy, 10)); }
    const key = o.yaw.toFixed(4) + '|' + o.pitch.toFixed(4) + '|' + this.L.toFixed(3) + '|' + this.sy.toFixed(4) + '|' + this.w + 'x' + this.h + (this.animating ? lt : '');
    if (key !== this.camKey) { this.camKey = key; this.placeLabels(); }
    if (this.tipFor) this.placeTip();
  }
}
