// Trade Galaxy (Trades page): every trade is a star in a 3D chart.
//   x = time (old -> new), y = R multiple (winners float above the glowing zero-R "liquidity plane", losers sink under it
//   and are seen dimmed through it), z = stop size (10 pt at the front -> 60 pt at the back).
//   Colour: win cyan -> green, loss magenta, breakeven violet; size ~ sqrt(|$|); big winners get diffraction spikes;
//   half-size (cold-streak) trades are dimmer and wear a ring. Every star hangs on a drop-line to the plane with energy
//   flowing along it and a ripple pool where it touches the plane; behind them an aurora curtain draws the cumulative-R
//   curve (tinted magenta in drawdowns).
//   Drag to orbit (slow ping-pong orbit when idle), tap a star -> page opts.onPick(row), mouse hover shows the tooltip.
//   First data: stars spiral in from the centre in time order; new data: survivors glide, newcomers grow, leavers shrink.
// Draw calls ~16 whatever the row count; particles: 1 star + 2 flow sparks (1 lite) per trade + 1500 dust (450 lite).
import { metal } from '../../olympus/materials.js';
import { THREE, View, Q, theme, glowTexture, rng, count } from './core.js';

const STOP_MIN = 10, STOP_MAX = 60, R_TOP = 5.6, R_BOT = -1.3, DEPTH = 3.4;
const FLY = 1, MOVE = 2, GROW = 3, SHRINK = 4;
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const smooth = (t) => t * t * (3 - 2 * t);
const outCubic = (t) => 1 - (1 - t) ** 3;
const outBack = (t) => { const u = t - 1; return 1 + 2.4 * u * u * u + 1.4 * u * u; };
const fract = (v) => v - Math.floor(v);
const num = (v, d = 0) => { const n = typeof v === 'string' ? parseFloat(v) : v; return Number.isFinite(n) ? n : d; };
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const MINUS = '−';
const fmtR = (r, d = 2) => (r < 0 && Math.abs(r) >= 0.5 * 10 ** -d ? MINUS : '+') + Math.abs(r).toFixed(d) + 'R';
const fmtUsd = (v) => (v < 0 && Math.round(-v) ? MINUS : '+') + '$' + Math.round(Math.abs(v)).toLocaleString('en-US');
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const CENTRE = new THREE.Vector3(0, 0.9, 0);
const _v = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color();
// backdrop colours (output space): the page colour when the skin is dark (neon needs a dark stage), a purple/accent glow
function paintBackdrop(U) {
  const pg = theme.page.clone().convertLinearToSRGB(), ac = theme.accent.clone().convertLinearToSRGB();
  const base = 0.2126 * pg.r + 0.7152 * pg.g + 0.0722 * pg.b < 0.22 ? pg : new THREE.Color(0.027, 0.031, 0.047);
  U.uBot.value.set(base.r * 0.9 + 0.006, base.g * 0.9 + 0.004, base.b * 0.9 + 0.014);
  U.uTop.value.set(base.r + 0.03, base.g + 0.012, base.b + 0.065);
  U.uGlow.value.set(0.035 + ac.r * 0.05, 0.012 + ac.g * 0.03, 0.06 + ac.b * 0.07);
}

// ------------------------------------------------------------------ shaders
const BG_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const BG_F = `uniform vec3 uTop; uniform vec3 uBot; uniform vec3 uGlow; uniform vec3 uGlow2; uniform float uAsp; varying vec2 vUv;
void main(){
  vec3 c = mix(uBot, uTop, smoothstep(0.0, 1.0, vUv.y));
  float a = min(uAsp, 1.5);
  vec2 q = (vUv - vec2(0.5, 0.46)) * vec2(a, 1.0); c += uGlow * exp(-dot(q, q) * 3.0);
  vec2 q2 = (vUv - vec2(0.85, 0.92)) * vec2(a, 1.0); c += uGlow2 * exp(-dot(q2, q2) * 5.0);
  vec2 v = vUv - 0.5; c *= 1.0 - dot(v, v) * 0.9;
  c += (fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) - 0.5) / 255.0;
  gl_FragColor = vec4(c, 1.0);
}`;
const DUST_V = `attribute vec3 aCol; attribute float aSize; attribute float aSeed;
uniform float uTime; uniform float uPix; uniform float uMotion;
varying vec3 vColor; varying float vAlpha;
void main(){
  float t = uTime * uMotion; vec3 p = position;
  p.x += sin(t * 0.07 + aSeed * 31.0) * 0.35; p.y += sin(t * 0.11 + aSeed * 17.0) * 0.22; p.z += cos(t * 0.09 + aSeed * 23.0) * 0.3;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp(aSize * uPix / -mv.z, 0.0, 64.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol; vAlpha = (0.65 + 0.35 * sin(t * (0.6 + aSeed) + aSeed * 40.0)) * smoothstep(0.4, 2.5, -mv.z);
}`;
const SOFT_F = `varying vec3 vColor; varying float vAlpha;
void main(){ vec2 q = gl_PointCoord - 0.5; float d = dot(q, q) * 4.0; if (d > 1.0) discard;
  float a = 1.0 - d; a *= a; gl_FragColor = vec4(vColor * (a * 0.6 + exp(-d * 16.0) * 0.8) * vAlpha, 1.0); }`;
const PLANE_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const PLANE_F = `uniform float uTime; uniform float uMotion; uniform vec2 uHalf; uniform float uIntro; uniform vec3 uC1; uniform vec3 uC2;
varying vec3 vW;
float grid(vec2 p, float s){ vec2 c = p / s; vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c); return 1.0 - min(min(g.x, g.y), 1.0); }
void main(){
  vec2 p = vW.xz, e = uHalf - abs(p);
  float edge = min(e.x, e.y), inside = smoothstep(0.0, 0.8, edge);
  float t = uTime * uMotion;
  float major = grid(p, 0.5), minor = grid(p, 0.125) * 0.12;
  float sx = p.x / (2.0 * uHalf.x) + 0.5;
  float scan = exp(-pow((sx - fract(t * 0.04)) * 10.0, 2.0)) * uMotion;
  float r = length(p * vec2(0.65, 1.0));
  float rip = exp(-pow((r - uIntro * 7.5) * 5.0, 2.0)) * (1.0 - uIntro) * (1.0 - uIntro);
  float sh = 0.5 + 0.5 * sin(p.x * 2.6 + t * 0.5) * sin(p.y * 3.3 - t * 0.37);
  vec3 col = mix(uC1, uC2, clamp(0.15 + 0.3 * sh + scan * 0.55, 0.0, 1.0));
  vec2 nq = p / uHalf; float fill = exp(-dot(nq, nq) * 1.4) * 0.07;
  float a = ((major * 0.3 + minor) * (0.55 + 1.1 * scan) + fill + 0.02) * inside + rip * (0.25 + major * 1.2) * inside;
  float bx = exp(-max(e.y, 0.0) * 40.0) * step(e.x, 0.6), by = exp(-max(e.x, 0.0) * 40.0) * step(e.y, 0.6);
  a += max(bx, by) * step(0.0, edge) * 0.9 + exp(-max(edge, 0.0) * 22.0) * step(0.0, edge) * 0.12;
  gl_FragColor = vec4(col * a, 1.0);
}`;
const LINE_V = `attribute float aA; attribute float aU; uniform vec3 uCol; varying vec3 vColor; varying float vAlpha; varying float vU;
void main(){ vColor = uCol; vAlpha = aA; vU = aU; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const GUIDE_F = `varying vec3 vColor; varying float vAlpha; varying float vU;
void main(){ float dash = vU < 0.0 ? 1.0 : step(0.5, fract(vU)); gl_FragColor = vec4(vColor * vAlpha * dash, 1.0); }`;
const CURT_V = `attribute float aTop; attribute float aX; attribute float aDD;
varying float vY; varying float vTop; varying float vX; varying float vDD;
void main(){ vY = position.y; vTop = aTop; vX = aX; vDD = aDD; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const CURT_F = `uniform float uReveal; uniform float uTime; uniform float uMotion; uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
varying float vY; varying float vTop; varying float vX; varying float vDD;
void main(){
  if (vX > uReveal) discard;
  float top = abs(vTop) < 0.001 ? 0.001 : vTop;
  float k = clamp(vY / top, 0.0, 1.0);
  float edge = exp(-abs(vTop - vY) * 6.0);
  vec3 c = mix(mix(uC1, uC2, vX), uC3, vDD);
  float pulse = exp(-pow((vX - fract(uTime * 0.05 + 0.35)) * 16.0, 2.0)) * uMotion;
  float head = exp(-pow((vX - uReveal) * 40.0, 2.0)) * step(uReveal, 0.999);
  float a = k * k * 0.12 + edge * (0.2 + pulse * 0.55 + head * 1.4) + pulse * k * 0.06;
  gl_FragColor = vec4(c * a, 1.0);
}`;
const CREST_V = `attribute float aX; attribute float aDD; uniform float uTime; uniform float uMotion; uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
varying vec3 vColor; varying float vX;
void main(){ vX = aX; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  float pulse = exp(-pow((aX - fract(uTime * 0.05 + 0.35)) * 16.0, 2.0)) * uMotion;
  vColor = mix(mix(mix(uC1, uC2, aX), uC3, aDD), vec3(1.0), 0.2 + pulse * 0.45) * (0.85 + pulse * 0.6); }`;
const CREST_F = `uniform float uReveal; varying vec3 vColor; varying float vX; void main(){ if (vX > uReveal) discard; gl_FragColor = vec4(vColor, 1.0); }`;
const STAR_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; attribute vec4 aMisc;
uniform float uTime; uniform float uPix; uniform float uCamY; uniform float uMotion; uniform float uSel; uniform float uHov; uniform float uFocus;
varying vec3 vColor; varying float vAlpha; varying float vRing; varying float vSpike; varying float vHi;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float tw = 1.0 + 0.12 * sin(uTime * (1.1 + aMisc.z * 2.3) + aMisc.z * 61.0) * uMotion;
  vHi = max(1.0 - step(0.5, abs(aMisc.w - uSel)), (1.0 - step(0.5, abs(aMisc.w - uHov))) * 0.75);
  gl_PointSize = clamp(aSize * uPix * tw * (1.0 + vHi * 0.55) / -mv.z, 0.0, 120.0);
  gl_Position = projectionMatrix * mv;
  float under = position.y * uCamY < -0.001 ? 0.72 : 1.0;
  float depth = clamp(1.12 - (-mv.z - uFocus) * 0.07, 0.72, 1.2);
  vColor = aCol * under * depth; vAlpha = aAlpha; vRing = aMisc.x; vSpike = aMisc.y;
}`;
const STAR_F = `varying vec3 vColor; varying float vAlpha; varying float vRing; varying float vSpike; varying float vHi;
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2);
  float halo = 1.0 - d2; halo = halo * halo * halo;
  float core = exp(-d2 * 34.0);
  float spk = (exp(-abs(q.x) * 70.0) + exp(-abs(q.y) * 70.0)) * (1.0 - d) * vSpike;
  float ring = vRing * exp(-pow((d - 0.52) * 11.0, 2.0));
  float hi = vHi * exp(-pow((d - 0.84) * 10.0, 2.0));
  float a = halo * mix(0.42, 0.2, vRing) + core * mix(1.05, 0.62, vRing) + spk * 0.75 + ring * 0.85 + hi * 0.9;
  vec3 c = mix(vColor, vec3(1.0), clamp(core * 0.6 + hi * 0.25, 0.0, 1.0));
  gl_FragColor = vec4(c * a * vAlpha, 1.0);
}`;
const DROP_V = `attribute vec3 aCol; attribute float aT; attribute float aA; attribute float aId;
uniform float uSel; uniform float uHov; varying vec3 vColor; varying float vAlpha;
void main(){ gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  float hi = max(1.0 - step(0.5, abs(aId - uSel)), (1.0 - step(0.5, abs(aId - uHov))) * 0.6);
  vColor = aCol; vAlpha = aA * mix(0.6, 0.1, aT) * (1.0 + hi * 2.4); }`;
const FLAT_F = `varying vec3 vColor; varying float vAlpha; void main(){ gl_FragColor = vec4(vColor * vAlpha, 1.0); }`;
const FLOW_V = `attribute vec3 aCol; attribute float aSeed; attribute float aA;
uniform float uTime; uniform float uPix; uniform float uCamY; uniform float uMotion;
varying vec3 vColor; varying float vAlpha;
void main(){
  float ph = fract(uTime * (0.16 + aSeed * 0.22) * uMotion + aSeed * 17.0);
  vec3 p = mix(vec3(position.x, 0.0, position.z), position, ph);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float life = sin(ph * 3.14159);
  gl_PointSize = clamp((0.03 + 0.035 * life) * uPix / -mv.z, 0.0, 24.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol * (p.y * uCamY < -0.001 ? 0.6 : 1.15);
  vAlpha = aA * life * smoothstep(0.06, 0.35, abs(position.y));
}`;
// ripple pool where a trade touches the plane (instanced flat quads)
const POOL_V = `attribute vec3 aFoot; attribute vec3 aCol; attribute vec2 aPS; attribute float aA;
uniform float uTime; uniform float uMotion; uniform float uSel;
varying vec2 vQ; varying vec3 vColor; varying float vPh; varying float vA;
void main(){
  vQ = position.xy;
  vec3 p = aFoot + vec3(position.x, 0.0, -position.y) * aPS.y;
  vPh = fract(uTime * 0.3 * uMotion + aPS.x + (1.0 - uMotion) * 0.35);
  vColor = aCol; vA = aA;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
}`;
const POOL_F = `varying vec2 vQ; varying vec3 vColor; varying float vPh; varying float vA;
void main(){
  float r = length(vQ); if (r > 1.0) discard;
  float p2 = fract(vPh + 0.5);
  float ring = exp(-pow((r - vPh) * 14.0, 2.0)) * (1.0 - vPh) + exp(-pow((r - p2) * 14.0, 2.0)) * (1.0 - p2) * 0.55;
  float core = exp(-r * r * 26.0) * 0.9;
  gl_FragColor = vec4(vColor * (ring * 0.8 + core) * vA, 1.0);
}`;

// ------------------------------------------------------------------ html overlay
const CSS = `.fxg-ui{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:2;font-family:inherit;-webkit-user-select:none;user-select:none;opacity:0;transition:opacity .8s ease}
.fxg-ui.on{opacity:1}
.fxg-l{position:absolute;left:0;top:0;white-space:nowrap;font-size:9px;font-weight:600;letter-spacing:.04em;line-height:1;color:rgba(188,192,236,.64);text-shadow:0 0 6px #07080c,0 0 2px #07080c}
.fxg-l.h{color:rgba(188,192,236,.44);font-weight:500;letter-spacing:.05em}
.fxg-l.s{font-size:10px;font-weight:700;color:#67e8f9}
.fxg-l.fix{transform:none!important;left:auto;right:10px;top:auto;bottom:9px}
.fxg-leg{position:absolute;left:10px;top:9px;display:flex;flex-wrap:wrap;gap:4px 10px;font-size:9px;font-weight:600;letter-spacing:.03em;line-height:1;color:rgba(188,192,236,.6)}
.fxg-leg span{display:inline-flex;align-items:center;gap:4px}
.fxg-leg i{display:inline-block;width:6px;height:6px;border-radius:50%}
.fxg-tip{position:absolute;left:0;top:0;padding:6px 9px;border-radius:10px;background:rgba(13,10,28,.88);border:1px solid rgba(150,130,255,.3);color:#eef0fb;font-size:11px;font-weight:600;line-height:1.3;letter-spacing:0;white-space:nowrap;box-shadow:0 6px 22px rgba(0,0,0,.5),0 0 18px rgba(124,92,255,.22);opacity:0;transition:opacity .15s;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
.fxg-tip.on{opacity:1}.fxg-tip i{font-style:normal;color:rgba(188,192,236,.7)}
.fxg-empty{position:absolute;left:50%;top:46%;transform:translate(-50%,-50%);font-size:12px;color:rgba(188,192,236,.55);display:none}`;
const LEGEND = [['linear-gradient(135deg,#22d3ee,#2ee59d)', 'win', '0 0 6px #2ee59d'], ['#ff2bd6', 'loss', '0 0 6px #ff2bd6'], ['#8b5cf6', 'BE', '0 0 6px #8b5cf6'],
  ['transparent', '½ size', 'inset 0 0 0 1.5px rgba(230,232,255,.75)'], ['linear-gradient(90deg,#7c4dff,#22d3ee)', 'ΣR', 'none', 'width:12px;height:2px;border-radius:2px']];
function injectCss() {
  if (document.getElementById('fxg-css')) return;
  const s = document.createElement('style'); s.id = 'fxg-css'; s.textContent = CSS; document.head.appendChild(s);
}
function ringTexture(reticle) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'); g.strokeStyle = '#fff'; g.lineCap = 'round';
  if (reticle) {
    g.lineWidth = 5;
    for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; g.beginPath(); g.arc(64, 64, 52, a + 0.34, a + Math.PI / 2 - 0.34); g.stroke(); }
    g.lineWidth = 4;
    for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; g.beginPath(); g.moveTo(64 + Math.cos(a) * 58, 64 + Math.sin(a) * 58); g.lineTo(64 + Math.cos(a) * 44, 64 + Math.sin(a) * 44); g.stroke(); }
  } else { g.lineWidth = 3.5; g.beginPath(); g.arc(64, 64, 58, 0, Math.PI * 2); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
// year ticks for long ranges, month ticks otherwise; labels sit in the middle of each period
function timeTicks(t0, t1) {
  const span = t1 - t0, marks = [], labels = [];
  if (!(span > 0)) return { marks, labels };
  const d0 = new Date(t0 * 1000), y0 = d0.getUTCFullYear(), y1 = new Date(t1 * 1000).getUTCFullYear();
  if (span > 400 * 86400) {
    for (let y = y0; y <= y1; y++) {
      const s = Date.UTC(y, 0, 1) / 1000, a = Math.max(t0, s), b = Math.min(t1, Date.UTC(y + 1, 0, 1) / 1000);
      if (s > t0) marks.push(s);
      if ((b - a) / span > 0.06) labels.push({ t: (a + b) / 2, text: String(y) });
    }
  } else {
    for (let y = y0, m = d0.getUTCMonth(); ; m === 11 ? (m = 0, y++) : m++) {
      const s = Date.UTC(y, m, 1) / 1000; if (s >= t1) break;
      const a = Math.max(t0, s), b = Math.min(t1, Date.UTC(y, m + 1, 1) / 1000);
      if (s > t0) marks.push(s);
      if ((b - a) / span > 0.04) labels.push({ t: (a + b) / 2, text: MONTHS[m] });
    }
  }
  return { marks, labels };
}
const shader = (vertexShader, fragmentShader, uniforms, extra = {}) => new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader,
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
export class Galaxy extends View {
  constructor(opts = {}) {
    super({ fov: 38, dprMax: 2, env: 'night', ...opts,
      orbit: { yaw: -0.34, pitch: 0.34, auto: 0.05, min: -0.7, max: 0.7, pitchMin: 0.1, pitchMax: 0.7, ...(opts.orbit || {}) } });
    this.canvas.classList.add('fx-galaxy'); this.canvas.style.display = 'block'; // inline canvases leave a baseline gap that can grow auto-height cards
    this.lt = 0; this.W = 7; this.ys = 0.78; this.L = 13; this.T = new THREE.Vector3();
    this.userRange = !!(opts.orbit && (opts.orbit.min != null || opts.orbit.max != null)); this.Lset = false;
    this.slots = []; this.byKey = new Map(); this.items = []; this.sig = ''; this.cap = 0; this.animating = false; this.t0 = 0; this.t1 = 0;
    this.introAt = -1; this.introDone = false; this.reveal = 1; this.revealAt = 0; this.revealDur = 1.6; this.curve = null;
    this.sel = null; this.hov = null; this.newest = null; this.selAt = 0; this._hoverAt = null;
    this.K = count(2, 1);
    this.u = { uTime: { value: 0 }, uPix: { value: 500 }, uCamY: { value: 1 }, uMotion: { value: Q.reduced ? 0 : 1 }, uSel: { value: -1 }, uHov: { value: -1 }, uFocus: { value: 13 } };
    this.textures = [];
    this.buildWorld();
    this.ensureCap(64);
    this.buildUi();
    this.shape(1, 1);
    const c = this.canvas;
    c.style.cursor = 'grab';
    c.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse' || e.buttons) return;
      const r = c.getBoundingClientRect(); this._hoverAt = [e.clientX - r.left, e.clientY - r.top];
    });
    c.addEventListener('pointerleave', () => { this._hoverAt = null; this.setHover(null); });
  }
  // index.js does `view.opts = { ...view.opts, ...pageOpts }`: keep OUR screen-space pick wired to the canvas and remember
  // the page's onPick(row) callback separately.
  get opts() { return this._o; }
  set opts(o) {
    o = o || {};
    if (!this._pickFn) this._pickFn = (x, y, e) => this.pick(x, y, e);
    if (typeof o.onPick === 'function' && o.onPick !== this._pickFn) this._onRow = o.onPick;
    this._o = { ...o, onPick: this._pickFn };
  }

  // ---------------------------------------------------------------- scene
  buildWorld() {
    const S = this.scene, R = rng(29), u = this.u;
    // backdrop: deep purple gradient + soft glow (screen space, drawn first)
    this.bgU = { uTop: { value: new THREE.Vector3(0.05, 0.026, 0.095) }, uBot: { value: new THREE.Vector3(0.016, 0.013, 0.03) },
      uGlow: { value: new THREE.Vector3(0.07, 0.024, 0.12) }, uGlow2: { value: new THREE.Vector3(0.012, 0.03, 0.075) }, uAsp: { value: 1 } };
    paintBackdrop(this.bgU);
    const bg = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({ uniforms: this.bgU, vertexShader: BG_V, fragmentShader: BG_F, depthTest: false, depthWrite: false }));
    bg.renderOrder = -10; S.add(bg);
    // nebula clouds (world space, so they parallax while orbiting)
    for (const [c, x, y, z, s, o] of [['#6d28d9', -5, 3.6, -9, 15, 0.11], ['#ff2bd6', 5.5, 2, -10, 12, 0.05], ['#2b5cff', 1, 5.2, -12, 18, 0.07],
      ['#22d3ee', 7, -1.2, -7, 8, 0.025], ['#8b5cf6', -1, -2.2, -6, 13, 0.05]]) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(c), transparent: true, opacity: o, blending: THREE.AdditiveBlending, depthWrite: false }));
      sp.position.set(x, y, z); sp.scale.set(s, s * 0.65, 1); S.add(sp);
    }
    // dust: faint motes in the chart volume, a far star shell and a few big out-of-focus bokeh blobs
    const N = count(Q.phone ? 1000 : 1500, 450), dg = attrs(N, { position: [3], aCol: [3], aSize: [1], aSeed: [1] }), A = dg.attributes;
    const pal = ['#8b5cf6', '#4f6bff', '#ff2bd6', '#22d3ee', '#c4b5fd'].map((h) => new THREE.Color(h));
    for (let i = 0; i < N; i++) {
      const far = R() < 0.4, bokeh = !far && R() < 0.05;
      A.position.setXYZ(i, (R() - 0.5) * (far ? 34 : 15), -2.8 + R() * 9, far ? -6 - R() * 12 : -5 + R() * 12);
      _c.copy(pal[(R() * pal.length) | 0]).multiplyScalar(bokeh ? 0.07 + R() * 0.06 : (far ? 0.3 : 0.2) + R() * 0.32);
      A.aCol.setXYZ(i, _c.r, _c.g, _c.b);
      A.aSize.setX(i, bokeh ? 0.35 + R() * 0.45 : far ? 0.05 + R() * 0.07 : 0.025 + R() * 0.05);
      A.aSeed.setX(i, R());
    }
    this.dust = new THREE.Points(dg, shader(DUST_V, SOFT_F, u)); this.dust.renderOrder = 1; S.add(this.dust);
    // the zero-R liquidity plane
    this.pU = { uTime: u.uTime, uMotion: u.uMotion, uHalf: { value: new THREE.Vector2(4.4, 2.3) }, uIntro: { value: 1 },
      uC1: { value: new THREE.Color('#5b3bd1') }, uC2: { value: new THREE.Color('#22d3ee') } };
    this.plane = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), shader(PLANE_V, PLANE_F, this.pU, { side: THREE.DoubleSide, extensions: { derivatives: true } }));
    this.plane.rotation.x = -Math.PI / 2; this.plane.renderOrder = 2; S.add(this.plane);
    // guides: R levels on the back wall, R axis, time ticks (geometry rebuilt by frameLayout)
    this.guides = new THREE.LineSegments(new THREE.BufferGeometry(), shader(LINE_V, GUIDE_F, { uCol: { value: new THREE.Color('#8f86ff') } }));
    this.guides.renderOrder = 3; S.add(this.guides);
    // equity curtain + crest line (geometry rebuilt with the data)
    this.cU = { uTime: u.uTime, uMotion: u.uMotion, uReveal: { value: 1 }, uC1: { value: new THREE.Color('#7c4dff') },
      uC2: { value: new THREE.Color('#22d3ee') }, uC3: { value: new THREE.Color('#ff2bd6') } };
    this.curtain = new THREE.Mesh(new THREE.BufferGeometry(), shader(CURT_V, CURT_F, this.cU, { side: THREE.DoubleSide }));
    this.crest = new THREE.Line(new THREE.BufferGeometry(), shader(CREST_V, CREST_F, this.cU));
    this.curtain.renderOrder = 4; this.crest.renderOrder = 5; S.add(this.curtain, this.crest);
    // markers: selection reticle + foot ripple, newest-trade ping, intro flash, curve drawing head
    const ret = ringTexture(true), ring = ringTexture(false); this.textures.push(ret, ring);
    const spr = (map, color, order) => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map, color, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false })); s.renderOrder = order; s.visible = false; S.add(s); return s; };
    this.reticle = spr(ret, new THREE.Color('#e9fbff'), 11);
    this.beacon = spr(ring, new THREE.Color('#bdf4ff'), 10);
    this.flash = spr(glowTexture(), new THREE.Color('#d9c8ff'), 12);
    this.head = spr(glowTexture(), new THREE.Color('#c9fbff'), 12);
    this.tipGlow = spr(glowTexture(), new THREE.Color('#7df3ff'), 12);
    this.ripple = new THREE.Mesh(new THREE.RingGeometry(0.86, 1, 64), new THREE.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    this.ripple.rotation.x = -Math.PI / 2; this.ripple.renderOrder = 9; this.ripple.visible = false; S.add(this.ripple);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  // star / drop-line / flow / pool buffers sized for n trades (grown on demand)
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(64, Math.ceil(n * 1.25 / 64) * 64), K = this.K, u = this.u;
    const sg = attrs(cap, { position: [3, 1], aCol: [3], aSize: [1, 1], aAlpha: [1, 1], aMisc: [4] });
    const dg = attrs(cap * 2, { position: [3, 1], aCol: [3], aT: [1], aA: [1, 1], aId: [1] });
    const fg = attrs(cap * K, { position: [3, 1], aCol: [3], aSeed: [1], aA: [1, 1] });
    const quad = new THREE.PlaneGeometry(2, 2), pg = new THREE.InstancedBufferGeometry();
    pg.index = quad.index; pg.setAttribute('position', quad.attributes.position);
    attrs(cap, { aFoot: [3, 1], aCol: [3], aPS: [2], aA: [1, 1] }, pg, THREE.InstancedBufferAttribute); pg.instanceCount = 0;
    if (!this.stars) {
      this.pools = new THREE.Mesh(pg, shader(POOL_V, POOL_F, u, { side: THREE.DoubleSide }));
      this.drops = new THREE.LineSegments(dg, shader(DROP_V, FLAT_F, u));
      this.flows = new THREE.Points(fg, shader(FLOW_V, SOFT_F, u));
      this.stars = new THREE.Points(sg, shader(STAR_V, STAR_F, u));
      this.pools.renderOrder = 5; this.drops.renderOrder = 6; this.flows.renderOrder = 7; this.stars.renderOrder = 8;
      for (const o of [this.pools, this.drops, this.flows, this.stars]) { o.frustumCulled = false; this.scene.add(o); }
    } else {
      for (const [o, g] of [[this.stars, sg], [this.drops, dg], [this.flows, fg], [this.pools, pg]]) { o.geometry.dispose(); o.geometry = g; }
    }
    this.cap = cap;
  }
  buildUi() {
    injectCss();
    const ui = this.ui = document.createElement('div'); ui.className = 'fxg-ui'; ui.setAttribute('aria-hidden', 'true');
    this.tip = document.createElement('div'); this.tip.className = 'fxg-tip';
    this.empty = document.createElement('div'); this.empty.className = 'fxg-empty'; this.empty.textContent = 'No trades in this view';
    const hint = document.createElement('div'); hint.className = 'fxg-l h fix'; hint.textContent = 'older → newer';
    const leg = document.createElement('div'); leg.className = 'fxg-leg';
    leg.innerHTML = LEGEND.map(([bg, t, sh, st]) => `<span><i style="background:${bg};box-shadow:${sh};${st || ''}"></i>${t}</span>`).join('');
    ui.append(leg, hint, this.empty, this.tip);
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
  dispose() { this.ui?.remove(); for (const t of this.textures) t.dispose(); super.dispose(); }
  // chart proportions follow the card: a square phone card gets a taller R axis, a wide desktop card a longer time axis
  shape(w, h) {
    const asp = w / h, W = 6.6 * Math.pow(clamp(asp / 1.05, 1, 2.4), 0.88), ys = 0.56 * clamp(1.5 / asp, 1, 1.5);
    const changed = Math.abs(W - this.W) > 0.2 || Math.abs(ys - this.ys) > 0.02;
    this.W = W; this.ys = ys; this.T.set(0, (R_TOP + R_BOT) * ys / 2 - 0.15, 0);
    return changed;
  }
  onResize(w, h) {
    const dpr = this.renderer.getPixelRatio();
    this.u.uPix.value = h * dpr / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2));
    this.bgU.uAsp.value = w / h;
    if (this.shape(w, h) || !this.framed) {
      this.framed = true;
      if (this.items.length) { this.layout(); this.retarget(0.6); this.buildCurve(false); }
      this.frameLayout();
    }
    if (!this.userRange) { const r = 0.7 / clamp((w / h) / 1.4, 1, 1.45); this.orbit.min = -r; this.orbit.max = r; }
    this.Lset = false; this.camKey = '';
  }

  // ---------------------------------------------------------------- data
  setData(rows, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const list = Array.isArray(rows) ? rows : [];
    const items = [], seen = new Set();
    let sig = list.length + ':';
    for (let i = 0; i < list.length; i++) {
      const row = list[i]; if (!row) continue;
      const day = String(row.day || '');
      let t = num(row.entry_t, NaN); if (!Number.isFinite(t)) t = (Date.parse(day + 'T14:30:00Z') / 1000) || i * 86400;
      let key = row.entry_t != null ? 't' + row.entry_t : day + (row.side || '') + i; if (seen.has(key)) key += '#' + i; seen.add(key);
      const r = num(row.r), pnl = num(row.pnl), stop = num(row.risk_pts, 20);
      items.push({ key, row, t, r, pnl, stop, half: !!row.half, side: String(row.side || ''), day, seed: fract(Math.sin(t * 0.0001 + i * 0.37) * 43758.5453) });
      sig += key + (r * 1000 | 0) + ',';
    }
    items.sort((a, b) => a.t - b.t);
    if (sig === this.sig) { for (const it of items) { const s = this.byKey.get(it.key); if (s) s.it.row = it.row; } return; }
    this.sig = sig;
    const n = items.length, dens = clamp(1.2 - n / 1400, 0.74, 1.12);
    for (const it of items) {
      it.kind = it.r >= 0.1 ? 'win' : it.r <= -0.1 ? 'loss' : 'be';
      it.size = (0.11 + 0.0105 * Math.sqrt(Math.abs(it.pnl))) * dens;
      it.spike = it.r >= 1.8 ? clamp((it.r - 1.3) / 3, 0.3, 1) : 0;
    }
    this.items = items; this.layout();
    const first = !this.slots.length && !this.introDone, now = this.lt, red = Q.reduced;
    const next = [], keep = new Set();
    items.forEach((it, i) => {
      let sl = this.byKey.get(it.key);
      if (sl && !sl.dead) {
        sl.p0.copy(sl.p); sl.s0 = sl.s * sl.size / it.size; sl.a0 = sl.a; sl.mode = MOVE; sl.t0 = now; sl.dur = red ? 0 : 0.95;
      } else {
        sl = { key: it.key, p: new THREE.Vector3(), p0: new THREE.Vector3(), p1: new THREE.Vector3(), s: 0, s0: 0, a: 0, a0: 0, dead: false, done: false, col: new THREE.Color() };
        if (first) { sl.mode = FLY; sl.t0 = now + 0.15 + (i / Math.max(1, n - 1)) * 1.5; sl.dur = 1.25; sl.spin = 1.4 + it.seed * 1.2; sl.p.copy(CENTRE); }
        else { sl.mode = GROW; sl.t0 = now + 0.1 + ((it.tx / this.W) + 0.5) * 0.5; sl.dur = 0.75; }
        if (red) { sl.t0 = now; sl.dur = 0; }
      }
      sl.it = it; sl.done = false; sl.p1.set(it.tx, it.ty, it.tz);
      keep.add(it.key); next.push(sl);
    });
    for (const sl of this.slots) {
      if (keep.has(sl.key) || sl.dead) continue;
      sl.dead = true; sl.done = false; sl.mode = SHRINK; sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.t0 = now; sl.dur = red ? 0 : 0.5;
      next.push(sl);
    }
    this.slots = next; this.byKey.clear();
    for (const sl of next) if (!sl.dead) this.byKey.set(sl.key, sl);
    this.newest = n ? this.byKey.get(items[n - 1].key) : null;
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.setHover(null);
    this.recolor(); this.writeStatic(); this.animating = true;
    if (first && n) { this.introAt = red ? -1 : now; this.introDone = true; }
    this.buildCurve(true, first);
    this.frameLayout();
    this.empty.style.display = n ? 'none' : 'block';
    this.ui.classList.add('on');
  }
  // x from time (fit to the visible subset), y from R, z from stop size (small stops in front)
  layout() {
    const its = this.items, n = its.length, W = this.W, ys = this.ys;
    const t0 = n ? its[0].t : 0, t1 = n ? its[n - 1].t : 1, span = t1 - t0;
    for (const it of its) {
      it.tx = span > 0 ? (it.t - t0) / span * W - W / 2 : 0;
      it.ty = clamp(it.r, R_BOT + 0.05, R_TOP) * ys;
      it.tz = DEPTH / 2 - clamp((it.stop - STOP_MIN) / (STOP_MAX - STOP_MIN), 0, 1) * DEPTH + (it.seed - 0.5) * 0.08;
    }
    this.t0 = t0; this.t1 = t1;
  }
  retarget(dur) {
    const now = this.lt;
    for (const sl of this.slots) {
      if (sl.dead) continue;
      sl.p1.set(sl.it.tx, sl.it.ty, sl.it.tz);
      if (sl.mode === MOVE || sl.done) { sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.mode = MOVE; sl.t0 = now; sl.dur = Q.reduced ? 0 : dur; sl.done = false; }
    }
    this.animating = true;
  }
  recolor() {
    const lossLo = new THREE.Color('#b026ff'), n = this.items.length, poolK = clamp(1.3 - n / 700, 0.4, 1);
    for (const sl of this.slots) {
      const it = sl.it, r = it.r, c = sl.col;
      if (it.kind === 'win') c.copy(theme.cyan).lerp(theme.good, clamp((r - 0.1) / 2.6, 0, 1)).multiplyScalar(1.05 + 0.3 * clamp(r / 5, 0, 1));
      else if (it.kind === 'loss') c.copy(lossLo).lerp(theme.magenta, clamp((-r - 0.1) / 0.6, 0, 1));
      else c.copy(theme.violet).multiplyScalar(1.15);
      sl.size = it.size; sl.alpha = it.half ? 0.62 : 1;
      sl.lineA = it.kind === 'loss' ? 0.55 : it.kind === 'be' ? 0.4 : 0.85;
      sl.flowA = it.kind === 'be' ? 0 : (it.kind === 'win' ? 0.95 : 0.6) * (it.half ? 0.6 : 1);
      sl.poolA = (it.kind === 'win' ? 0.42 : it.kind === 'loss' ? 0.3 : 0.16) * (it.half ? 0.65 : 1) * poolK;
      sl.poolS = 0.13 + 0.075 * Math.sqrt(Math.min(Math.abs(r), 5));
    }
  }
  retheme() { paintBackdrop(this.bgU); if (this.slots.length) { this.recolor(); this.writeStatic(); this.writeDynamic(); } }
  writeStatic() {
    const n = this.slots.length; this.ensureCap(n);
    const K = this.K, S = this.stars.geometry.attributes, D = this.drops.geometry.attributes, F = this.flows.geometry.attributes, P = this.pools.geometry.attributes;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], c = sl.col, it = sl.it, lk = sl.lineA; sl.idx = i;
      S.aCol.setXYZ(i, c.r, c.g, c.b); S.aMisc.setXYZW(i, it.half ? 1 : 0, it.spike, it.seed, i);
      for (let j = 0; j < 2; j++) { D.aCol.setXYZ(i * 2 + j, c.r * lk, c.g * lk, c.b * lk); D.aT.setX(i * 2 + j, j); D.aId.setX(i * 2 + j, i); }
      for (let k = 0; k < K; k++) { F.aCol.setXYZ(i * K + k, c.r, c.g, c.b); F.aSeed.setX(i * K + k, fract(it.seed * 7.13 + k * 0.618)); }
      P.aCol.setXYZ(i, c.r, c.g, c.b); P.aPS.setXY(i, it.seed, sl.poolS);
    }
    for (const a of [S.aCol, S.aMisc, D.aCol, D.aT, D.aId, F.aCol, F.aSeed, P.aCol, P.aPS]) a.needsUpdate = true;
    this.stars.geometry.setDrawRange(0, n); this.drops.geometry.setDrawRange(0, n * 2); this.flows.geometry.setDrawRange(0, n * K);
    this.pools.geometry.instanceCount = n;
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
  }
  writeDynamic() {
    const n = this.slots.length, K = this.K, S = this.stars.geometry.attributes, D = this.drops.geometry.attributes, F = this.flows.geometry.attributes, PA = this.pools.geometry.attributes;
    const P = S.position.array, Z = S.aSize.array, A = S.aAlpha.array, DP = D.position.array, DA = D.aA.array, FP = F.position.array, FA = F.aA.array, OF = PA.aFoot.array, OA = PA.aA.array;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], p = sl.p, a = sl.a, la = sl.la ?? a, o = i * 6;
      P[i * 3] = p.x; P[i * 3 + 1] = p.y; P[i * 3 + 2] = p.z;
      Z[i] = sl.size * sl.s; A[i] = sl.alpha * a;
      DP[o] = DP[o + 3] = p.x; DP[o + 1] = p.y; DP[o + 4] = 0; DP[o + 2] = DP[o + 5] = p.z;
      DA[i * 2] = DA[i * 2 + 1] = la * sl.lineA * sl.alpha;
      for (let k = 0; k < K; k++) { const q = i * K + k; FP[q * 3] = p.x; FP[q * 3 + 1] = p.y; FP[q * 3 + 2] = p.z; FA[q] = la * sl.flowA; }
      OF[i * 3] = p.x; OF[i * 3 + 1] = 0.004; OF[i * 3 + 2] = p.z; OA[i] = la * sl.poolA;
    }
    for (const at of [S.position, S.aSize, S.aAlpha, D.position, D.aA, F.position, F.aA, PA.aFoot, PA.aA]) at.needsUpdate = true;
  }
  animate() {
    const now = this.lt; let busy = false, dead = false;
    for (const sl of this.slots) {
      if (sl.done) { dead ||= sl.dead; continue; }
      const k = sl.dur > 0 ? clamp((now - sl.t0) / sl.dur, 0, 1) : 1, p = sl.p, p1 = sl.p1;
      if (sl.mode === FLY) {
        const e = outCubic(k), ang = (1 - e) * sl.spin, ox = p1.x - CENTRE.x, oz = p1.z - CENTRE.z, ca = Math.cos(ang), sa = Math.sin(ang);
        p.set(CENTRE.x + (ox * ca - oz * sa) * e, CENTRE.y + (p1.y - CENTRE.y) * e + Math.sin(k * Math.PI) * 0.6, CENTRE.z + (ox * sa + oz * ca) * e);
        sl.s = k > 0 ? 0.55 + 0.45 * outBack(k) : 0; sl.a = smooth(Math.min(1, k * 4)); sl.la = k * k * k;
      } else if (sl.mode === MOVE) {
        const e = smooth(k); p.lerpVectors(sl.p0, p1, e); sl.s = sl.s0 + (1 - sl.s0) * e; sl.a = sl.a0 + (1 - sl.a0) * e;
      } else if (sl.mode === GROW) {
        p.set(p1.x, p1.y + 0.45 * (1 - outCubic(k)), p1.z); sl.s = k > 0 ? outBack(k) : 0; sl.a = smooth(k);
      } else {
        const e = smooth(k); p.set(sl.p0.x, sl.p0.y * (1 - e * 0.7), sl.p0.z); sl.s = sl.s0 * (1 - e); sl.a = sl.a0 * (1 - e);
      }
      if (sl.mode !== FLY) sl.la = sl.a;
      if (k >= 1) { sl.done = true; sl.la = sl.a; dead ||= sl.dead; } else busy = true;
    }
    if (!busy && dead) { // compact: drop the stars that finished shrinking
      this.slots = this.slots.filter((s) => !s.dead); this.writeStatic();
    }
    this.writeDynamic();
    if (!busy) this.animating = false;
  }

  // ---------------------------------------------------------------- frame: plane, guides, ticks, labels, curve
  frameLayout() {
    const W = this.W, ys = this.ys, hx = W / 2 + 0.6, hz = DEPTH / 2 + 0.6, zb = -DEPTH / 2 - 0.42, xa = -W / 2 - 0.35;
    this.pU.uHalf.value.set(hx, hz); this.plane.scale.set(hx, hz, 1);
    {   // OLYMPUS materials: a chrome rail round the plane + gold posts (2 draws, env reflections)
      if (!this.rail) {
        this.rail = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), metal({ kind: 'chrome', envMapIntensity: 3 }), 4);
        this.posts = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.5, 0.5, 1, 18), metal({ kind: 'gold', brushed: false, roughness: 0.2, envMapIntensity: 3 }), 4);
        this.rail.frustumCulled = this.posts.frustumCulled = false; this.scene.add(this.rail, this.posts); this._railO = new THREE.Object3D();
      }
      const o = this._railO, y = this.plane.position.y, X = hx + 0.02, Z = hz + 0.02;
      [[0, -Z, 2 * X, 0.05, 0.05], [0, Z, 2 * X, 0.05, 0.05], [-X, 0, 0.05, 0.05, 2 * Z], [X, 0, 0.05, 0.05, 2 * Z]].forEach((b, i) => { o.position.set(b[0], y, b[1]); o.scale.set(b[2], b[3], b[4]); o.updateMatrix(); this.rail.setMatrixAt(i, o.matrix); });
      [[-X, -Z], [X, -Z], [-X, Z], [X, Z]].forEach((c, i) => { o.position.set(c[0], y + 0.1, c[1]); o.scale.set(0.16, 0.26, 0.16); o.updateMatrix(); this.posts.setMatrixAt(i, o.matrix); });
      this.rail.instanceMatrix.needsUpdate = this.posts.instanceMatrix.needsUpdate = true;
    }
    this.dust.scale.set(W / 7, ys / 0.78, 1);
    const v = [], a = [], uu = [];
    const seg = (x0, y0, z0, x1, y1, z1, al, dash) => { v.push(x0, y0, z0, x1, y1, z1); a.push(al, al); uu.push(dash ? x0 * 4 : -1, dash ? x1 * 4 : -1); };
    for (const r of [-1, 1, 2, 3, 4, 5]) seg(xa, r * ys, zb, W / 2 + 0.4, r * ys, zb, r === 1 || r === 5 ? 0.2 : 0.1, true);
    seg(xa, R_BOT * ys, zb, xa, R_TOP * ys, zb, 0.35, false);
    for (const r of [-1, 0, 1, 2, 3, 4, 5]) seg(xa - 0.09, r * ys, zb, xa + 0.09, r * ys, zb, 0.6, false);
    seg(xa, 0, zb, xa, 0, hz, 0.25, false); // axis foot along the plane's left edge
    const { marks, labels } = timeTicks(this.t0, this.t1), span = this.t1 - this.t0, X = (t) => (span > 0 ? (t - this.t0) / span * W - W / 2 : 0);
    for (const t of marks) seg(X(t), 0, hz - 0.12, X(t), 0, hz + 0.12, 0.7, false);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3)); g.setAttribute('aA', new THREE.Float32BufferAttribute(a, 1)); g.setAttribute('aU', new THREE.Float32BufferAttribute(uu, 1));
    this.guides.geometry.dispose(); this.guides.geometry = g;
    // html labels (projected whenever the camera moves)
    const defs = [];
    for (const r of [5, 3, 1, 0, -1]) defs.push({ text: r === 0 ? '0R' : (r > 0 ? '+' : MINUS) + Math.abs(r) + 'R', p: new THREE.Vector3(xa - 0.14, r * ys, zb), ax: 1 });
    if (this.items.length) {
      for (const l of labels) defs.push({ text: l.text, p: new THREE.Vector3(X(l.t), 0, hz + 0.4), tick: true });
      defs.push({ text: 'stop 10 pt', p: new THREE.Vector3(W / 2 + 0.7, 0, DEPTH / 2), ax: 0, cls: 'h' });
      defs.push({ text: '60 pt', p: new THREE.Vector3(W / 2 + 0.7, 0, -DEPTH / 2), ax: 0, cls: 'h' });
      if (this.curve) defs.push({ text: 'Σ ' + fmtR(this.curve.sum, 1), p: this.curve.end, ax: 0, dx: 7, cls: 's', curve: true });
    }
    this.setLabels(defs);
  }
  setLabels(defs) {
    for (const l of this.labels) l.el.remove();
    this.labels = defs.map((d) => {
      const el = document.createElement('div'); el.className = 'fxg-l' + (d.cls ? ' ' + d.cls : ''); el.textContent = d.text;
      this.ui.insertBefore(el, this.tip); return { ...d, el, last: '', wid: null };
    });
    this.camKey = '';
  }
  // project the labels; keep them inside the card and drop time ticks that would collide
  placeLabels() {
    const cam = this.camera, w = this.w, h = this.h, live = this.ui.isConnected;
    let left = 1e9;
    for (let i = this.labels.length - 1; i >= 0; i--) {
      const l = this.labels[i];
      if (l.wid == null && live) l.wid = l.el.offsetWidth || 20;
      _v.copy(l.p).project(cam);
      const ax = l.ax ?? 0.5, wid = l.wid || 20;
      let x = (_v.x + 1) / 2 * w + (l.dx || 0) - ax * wid; const y = (1 - _v.y) / 2 * h + (l.dy || 0);
      x = clamp(x, 4, Math.max(4, w - wid - 4));
      let hidden = _v.z > 1 || y < 6 || y > h - 6 || (l.curve && this.reveal < 0.98);
      if (l.tick && !hidden) { if (x + wid > left - 6) hidden = true; else left = x; }
      const tf = hidden ? 'translate3d(-999px,-999px,0)' : `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0) translateY(-50%)`;
      if (tf !== l.last) { l.el.style.transform = tf; l.last = tf; }
    }
  }
  // cumulative-R curtain behind the stars: x = time, height = equity (normalised), magenta tint = drawdown depth
  buildCurve(animate, intro) {
    const its = this.items, n = its.length, zc = -DEPTH / 2 - 0.3;
    if (!n) { this.curtain.visible = this.crest.visible = false; this.curve = null; return; }
    const m = n + 1, xs = new Float32Array(m), cs = new Float32Array(m), dd = new Float32Array(m);
    xs[0] = n > 1 ? its[0].tx : its[0].tx - 0.5;
    let cum = 0, peak = 0, maxAbs = 0, maxDD = 0;
    for (let i = 0; i < n; i++) { cum += its[i].r; xs[i + 1] = its[i].tx; cs[i + 1] = cum; }
    for (let i = 0; i < m; i++) { peak = Math.max(peak, cs[i]); maxAbs = Math.max(maxAbs, Math.abs(cs[i])); dd[i] = peak - cs[i]; maxDD = Math.max(maxDD, dd[i]); }
    const k = (4.1 * this.ys) / Math.max(4, maxAbs), ddK = 1 / Math.max(5, maxDD), x0 = xs[0], xw = Math.max(1e-6, xs[m - 1] - x0);
    const P = new Float32Array(m * 6), TOP = new Float32Array(m * 2), AX = new Float32Array(m * 2), DD = new Float32Array(m * 2), idx = [];
    const CP = new Float32Array(m * 3), CX = new Float32Array(m), CD = new Float32Array(m), ys = new Float32Array(m);
    for (let i = 0; i < m; i++) {
      const y = cs[i] * k, X = (xs[i] - x0) / xw, d = clamp(dd[i] * ddK, 0, 1) * 0.85; ys[i] = y;
      P.set([xs[i], y, zc, xs[i], 0, zc], i * 6); TOP[i * 2] = TOP[i * 2 + 1] = y; AX[i * 2] = AX[i * 2 + 1] = X; DD[i * 2] = DD[i * 2 + 1] = d;
      CP.set([xs[i], y, zc + 0.002], i * 3); CX[i] = X; CD[i] = d;
      if (i < m - 1) { const b = i * 2; idx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setAttribute('aTop', new THREE.BufferAttribute(TOP, 1));
    g.setAttribute('aX', new THREE.BufferAttribute(AX, 1)); g.setAttribute('aDD', new THREE.BufferAttribute(DD, 1)); g.setIndex(idx);
    const cg = new THREE.BufferGeometry();
    cg.setAttribute('position', new THREE.BufferAttribute(CP, 3)); cg.setAttribute('aX', new THREE.BufferAttribute(CX, 1)); cg.setAttribute('aDD', new THREE.BufferAttribute(CD, 1));
    this.curtain.geometry.dispose(); this.curtain.geometry = g; this.crest.geometry.dispose(); this.crest.geometry = cg;
    this.curtain.visible = this.crest.visible = true;
    this.curve = { xs, ys, cx: CX, z: zc, sum: cum, end: new THREE.Vector3(xs[m - 1], ys[m - 1], zc) };
    if (animate && !Q.reduced) { this.reveal = 0; this.revealAt = this.lt + (intro ? 0.55 : 0.1); this.revealDur = intro ? 2.1 : 1.1; this.cU.uReveal.value = 0; }
    else { this.reveal = 1; this.cU.uReveal.value = 1.001; }
  }
  // camera distance that keeps the whole chart (plus label margins) inside the card for a given yaw / pitch; evaluated
  // every frame and eased, so the orbit doubles as a gentle dolly and wide desktop cards are filled too
  fitNeed(yaw, pitch) {
    const cam = this.camera, tan = Math.tan(THREE.MathUtils.degToRad(cam.fov) / 2), tv = tan * 0.9, th = tan * cam.aspect * 0.96;
    const hx = this.W / 2 + 0.6, y0 = R_BOT * this.ys - this.T.y, y1 = R_TOP * this.ys - this.T.y + 0.05, z0 = -DEPTH / 2 - 0.5, z1 = DEPTH / 2 + 0.85;
    const cp = Math.cos(pitch), zx = Math.sin(yaw) * cp, zy = Math.sin(pitch), zz = Math.cos(yaw) * cp;
    const xl = Math.hypot(zz, zx), xx = zz / xl, xz = -zx / xl, yx = zy * xz, yy = zz * xx - zx * xz, yz = -zy * xx;
    let need = 0;
    for (let i = 0; i < 8; i++) {
      const X = i & 1 ? hx : -hx, Y = i & 2 ? y1 : y0, Z = i & 4 ? z1 : z0;
      const cx = X * xx + Z * xz, cy = X * yx + Y * yy + Z * yz, cz = X * zx + Y * zy + Z * zz;
      need = Math.max(need, Math.abs(cx) / th + cz, Math.abs(cy) / tv + cz);
    }
    return need;
  }

  // ---------------------------------------------------------------- picking + tooltip
  nearest(px, py, maxPx) {
    const cam = this.camera; cam.updateMatrixWorld(); _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    let best = null, bd = maxPx * maxPx;
    for (const sl of this.slots) {
      if (sl.dead || sl.a < 0.3) continue;
      _v.copy(sl.p).applyMatrix4(_m); if (_v.z > 1) continue;
      const dx = (_v.x + 1) / 2 * this.w - px, dy = (1 - _v.y) / 2 * this.h - py, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = sl; }
    }
    return best;
  }
  pick(nx, ny) {
    const sl = this.nearest((nx + 1) / 2 * this.w, (1 - ny) / 2 * this.h, 24);
    this.select(sl);
    if (sl && this._onRow) { try { this._onRow(sl.it.row); } catch (e) { console.warn('galaxy onPick', e); } }
  }
  select(sl) {
    this.sel = sl; this.selAt = this.lt; this.u.uSel.value = sl ? sl.idx : -1;
    if (sl) this.ripple.material.color.copy(sl.col);
    this.showTip(this.hov || sl);
  }
  setHover(sl) {
    if (sl === this.hov) return;
    this.hov = sl; this.u.uHov.value = sl ? sl.idx : -1; this.canvas.style.cursor = sl ? 'pointer' : 'grab';
    this.showTip(sl || this.sel);
  }
  showTip(sl) {
    if (!sl) { this.tip.classList.remove('on'); this.tipFor = null; return; }
    if (sl !== this.tipFor) {
      const it = sl.it, col = it.kind === 'win' ? '#5eead4' : it.kind === 'loss' ? '#ff6bd5' : '#b9a6ff';
      this.tip.innerHTML = `${esc(it.day)} · ${esc(it.side)} · <b style="color:${col}">${fmtR(it.r)}</b> · <b style="color:${col}">${fmtUsd(it.pnl)}</b>${it.half ? ' · <i>½ size</i>' : ''}`;
      this.tipFor = sl; this.tipW = this.tip.offsetWidth; this.tipH = this.tip.offsetHeight; this.tipLast = '';
    }
    this.tip.classList.add('on'); this.placeTip();
  }
  placeTip() {
    const sl = this.tipFor; if (!sl) return;
    _v.copy(sl.p).project(this.camera);
    const sx = (_v.x + 1) / 2 * this.w, sy = (1 - _v.y) / 2 * this.h, tw = this.tipW || 160, th = this.tipH || 26;
    const x = clamp(sx - tw / 2, 6, Math.max(6, this.w - tw - 6)); let y = sy - th - 16; if (y < 6) y = sy + 16;
    const tf = `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0)`;
    if (tf !== this.tipLast) { this.tip.style.transform = tf; this.tipLast = tf; }
  }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const o = this.orbitStep(dt), T = this.T, cam = this.camera, cp = Math.cos(o.pitch), want = this.fitNeed(o.yaw, o.pitch);
    this.L = this.Lset ? this.L + (want - this.L) * Math.min(1, dt * 2) : want; this.Lset = true; u.uFocus.value = this.L;
    cam.position.set(T.x + Math.sin(o.yaw) * cp * this.L, T.y + Math.sin(o.pitch) * this.L, T.z + Math.cos(o.yaw) * cp * this.L);
    cam.lookAt(T); cam.updateMatrixWorld();
    u.uCamY.value = cam.position.y;
    if (this.animating) this.animate();
    // intro: shock ripple across the plane + a flash at the centre
    if (this.introAt >= 0) {
      const k = (lt - this.introAt) / 2.6;
      this.pU.uIntro.value = clamp(k, 0, 1);
      this.flash.visible = k < 0.5; this.flash.position.copy(CENTRE); this.flash.scale.setScalar(0.6 + k * 7); this.flash.material.opacity = Math.max(0, 1 - k * 2.2) * 0.8;
      if (k >= 1) this.introAt = -1;
    }
    // equity curtain drawing itself, with a bright head
    if (this.reveal < 1 && this.curve) {
      this.reveal = clamp((lt - this.revealAt) / this.revealDur, 0, 1);
      const rv = this.reveal, c = this.curve; this.cU.uReveal.value = rv >= 1 ? 1.001 : rv;
      let i = 1; while (i < c.cx.length - 1 && c.cx[i] < rv) i++;
      const f = clamp((rv - c.cx[i - 1]) / Math.max(1e-6, c.cx[i] - c.cx[i - 1]), 0, 1);
      this.head.visible = rv > 0 && rv < 1; this.head.position.set(c.xs[i - 1] + (c.xs[i] - c.xs[i - 1]) * f, c.ys[i - 1] + (c.ys[i] - c.ys[i - 1]) * f, c.z);
      this.head.scale.setScalar(0.55); this.head.material.opacity = 0.9;
      if (rv >= 1) this.camKey = '';
    } else this.head.visible = false;
    // "now" on the equity curve
    if (this.curve && this.reveal >= 1) {
      this.tipGlow.visible = true; this.tipGlow.position.copy(this.curve.end);
      this.tipGlow.scale.setScalar(0.42 + (Q.reduced ? 0 : 0.08 * Math.sin(lt * 3))); this.tipGlow.material.opacity = 0.85;
    } else this.tipGlow.visible = false;
    // newest trade: sonar ping
    const nb = this.newest;
    if (nb && !nb.dead && nb.a > 0.5) {
      const ph = Q.reduced ? 0.3 : fract(lt * 0.45);
      this.beacon.visible = true; this.beacon.position.copy(nb.p); this.beacon.scale.setScalar(Math.max(0.2, nb.size) * (0.9 + ph * 2.6));
      this.beacon.material.opacity = (1 - ph) * 0.75; this.beacon.material.color.copy(nb.col).lerp(_c.set('#ffffff'), 0.5);
    } else this.beacon.visible = false;
    // selection: lock-on reticle + ripple on the plane under the star
    const s = this.sel;
    if (s && !s.dead) {
      const pulse = Q.reduced ? 1 : 1 + 0.07 * Math.sin(lt * 5);
      this.reticle.visible = this.ripple.visible = true;
      this.reticle.position.copy(s.p); this.reticle.scale.setScalar(Math.max(0.42, s.size * 1.5) * pulse);
      this.reticle.material.rotation = Q.reduced ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95;
      const ph = Q.reduced ? 0.4 : fract((lt - this.selAt) * 0.75);
      this.ripple.position.set(s.p.x, 0.006, s.p.z); this.ripple.scale.setScalar(0.08 + ph * 0.55); this.ripple.material.opacity = (1 - ph) * 0.85;
    } else { this.reticle.visible = this.ripple.visible = false; }
    // html
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.setHover(this.nearest(hx, hy, 16)); }
    const key = o.yaw.toFixed(4) + '|' + o.pitch.toFixed(4) + '|' + this.L.toFixed(3) + '|' + this.w + 'x' + this.h;
    if (key !== this.camKey) { this.camKey = key; this.placeLabels(); }
    if (this.tipFor) this.placeTip();
  }
}
