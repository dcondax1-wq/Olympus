// Shared kit of the HUD views (constellation, ribbon, reactor, pipeline, losses):
//  - maths / number formatting helpers, a typed-array attribute builder, additive shader materials, CSS colour parsing
//  - the purple backdrop, nebula sprites and drifting dust every chart sits in (same stage as the galaxy and the city)
//  - framing(): the camera distance + lens shift that fits a set of anchor points into (a part of) the card
//  - class Hud: View + an HTML overlay (labels projected from 3D with collision culling, legend, tooltip, "no data" note),
//    tap picking that keeps the page's onPick(row) apart from the canvas handler, mouse hover, an orbit camera that
//    re-frames itself every frame (a gentle dolly while it turns).
import { THREE, View, Q, theme, glowTexture, POINT_FRAG, rng, count } from './core.js';

export { THREE, Q, theme, glowTexture, POINT_FRAG, rng, count };

// ------------------------------------------------------------------ helpers
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => t * t * (3 - 2 * t);
export const outCubic = (t) => 1 - (1 - t) ** 3;
export const outBack = (t) => { const u = t - 1; return 1 + 2.4 * u * u * u + 1.4 * u * u; };
export const fract = (v) => v - Math.floor(v);
export const num = (v, d = NaN) => { const n = typeof v === 'string' && v.trim() !== '' ? parseFloat(v) : v; return typeof n === 'number' && Number.isFinite(n) ? n : d; };
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export const hash = (s) => { let h = 2166136261; s = String(s); for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return ((h >>> 0) % 100000) / 100000; };
export const MINUS = '−';
const sgn = (v, plus) => (v < 0 ? MINUS : plus ? '+' : '');
export const fmtUsd = (v, plus = true) => (Number.isFinite(v) ? sgn(Math.round(v) ? v : 0, plus) + '$' + Math.round(Math.abs(v)).toLocaleString('en-US') : '—');
export const fmtK = (v, plus = true) => {
  if (!Number.isFinite(v)) return '—';
  const a = Math.abs(v), s = sgn(Math.round(a) ? v : 0, plus);
  return s + '$' + (a >= 99500 ? Math.round(a / 1000) + 'k' : a >= 950 ? (a / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : Math.round(a));
};
export const fmtR = (r, d = 2) => (Number.isFinite(r) ? sgn(Math.abs(r) >= 0.5 * 10 ** -d ? r : 0, true) + Math.abs(r).toFixed(d) + 'R' : '—');
export const fmtPf = (v) => (Number.isFinite(v) ? (v >= 9.995 ? v.toFixed(1) : v.toFixed(2)) : '—');
export const pct = (v) => (Number.isFinite(v) ? (Math.abs(v) < 9.95 && v % 1 ? v.toFixed(1) : Math.round(v)) + '%' : '—');

// any CSS colour (hex, rgb(), hsl(), a name) -> THREE.Color; falls back quietly instead of warning
let _cc = null;
export function cssColor(c, fallback = '#8b5cf6') {
  if (c && c.isColor) return c.clone();
  if (typeof c === 'number') return new THREE.Color(c);
  const s = typeof c === 'string' ? c.trim() : '';
  if (/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(s)) return new THREE.Color(s);
  if (s) {
    try {
      _cc ||= document.createElement('canvas').getContext('2d');
      _cc.fillStyle = '#010203'; _cc.fillStyle = s;
      const v = _cc.fillStyle;
      if (v !== '#010203' || s === '#010203') {
        if (v[0] === '#') return new THREE.Color(v);
        const m = v.match(/[\d.]+/g); if (m && m.length >= 3) return new THREE.Color().setRGB(m[0] / 255, m[1] / 255, m[2] / 255, THREE.SRGBColorSpace);
      }
    } catch { }
  }
  return new THREE.Color(fallback);
}
export const hex = (c) => '#' + c.getHexString();

export function attrs(n, spec, geo = new THREE.BufferGeometry(), Attr = THREE.BufferAttribute) {
  for (const k in spec) {
    const [size, dyn] = spec[k], a = new Attr(new Float32Array(Math.max(1, n) * size), size);
    if (dyn) a.setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute(k, a);
  }
  return geo;
}
export const additive = (vertexShader, fragmentShader, uniforms, extra = {}) => new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, ...extra });

// ------------------------------------------------------------------ stage: backdrop, nebula, dust
const BG_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const BG_F = `uniform vec3 uTop; uniform vec3 uBot; uniform vec3 uGlow; uniform vec3 uGlow2; uniform float uAsp; uniform vec2 uAt; varying vec2 vUv;
void main(){
  vec3 c = mix(uBot, uTop, smoothstep(0.0, 1.0, vUv.y));
  float a = min(uAsp, 1.6);
  vec2 q = (vUv - uAt) * vec2(a, 1.0); c += uGlow * exp(-dot(q, q) * 3.0);
  vec2 q2 = (vUv - vec2(0.86, 0.9)) * vec2(a, 1.0); c += uGlow2 * exp(-dot(q2, q2) * 5.0);
  vec2 v = vUv - 0.5; c *= 1.0 - dot(v, v) * 0.9;
  c += (fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) - 0.5) / 255.0;
  gl_FragColor = vec4(c, 1.0);
}`;
// backdrop colours (output space): the page colour when the skin is dark (neon needs a dark stage), a purple/accent glow
export function paintBackdrop(U, tint) {
  const pg = theme.page.clone().convertLinearToSRGB(), ac = (tint || theme.accent).clone().convertLinearToSRGB();
  const base = 0.2126 * pg.r + 0.7152 * pg.g + 0.0722 * pg.b < 0.22 ? pg : new THREE.Color(0.027, 0.031, 0.047);
  U.uBot.value.set(base.r * 0.9 + 0.006, base.g * 0.9 + 0.004, base.b * 0.9 + 0.014);
  U.uTop.value.set(base.r + 0.03, base.g + 0.012, base.b + 0.065);
  U.uGlow.value.set(0.035 + ac.r * 0.05, 0.012 + ac.g * 0.03, 0.06 + ac.b * 0.07);
}
export function addBackdrop(scene, at = [0.5, 0.48]) {
  const U = { uTop: { value: new THREE.Vector3() }, uBot: { value: new THREE.Vector3() }, uGlow: { value: new THREE.Vector3() },
    uGlow2: { value: new THREE.Vector3(0.012, 0.03, 0.075) }, uAsp: { value: 1 }, uAt: { value: new THREE.Vector2(...at) } };
  paintBackdrop(U);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({ uniforms: U, vertexShader: BG_V, fragmentShader: BG_F, depthTest: false, depthWrite: false }));
  m.renderOrder = -10; m.frustumCulled = false; scene.add(m);
  return U;
}
// soft world-space glow clouds (they parallax while the camera orbits): [[colour, x, y, z, w, h, opacity], ...]
export function addNebula(scene, defs) {
  return defs.map(([c, x, y, z, w, h, o]) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(c), transparent: true, opacity: o, blending: THREE.AdditiveBlending, depthWrite: false }));
    s.position.set(x, y, z); s.scale.set(w, h, 1); s.renderOrder = 0; scene.add(s); return s;
  });
}
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
// motes in (and a far shell around) a box of half-size [sx, sy, sz] centred on (0, cy, 0)
export function addDust(scene, u, { n = count(Q.phone ? 700 : 1000, 300), box = [7, 4, 5], cy = 1, seed = 17, pal = ['#8b5cf6', '#4f6bff', '#ff2bd6', '#22d3ee', '#c4b5fd'] } = {}) {
  const R = rng(seed), g = attrs(n, { position: [3], aCol: [3], aSize: [1], aSeed: [1] }), A = g.attributes, P = pal.map((h) => new THREE.Color(h)), c = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const far = R() < 0.4, bokeh = !far && R() < 0.05;
    A.position.setXYZ(i, (R() - 0.5) * box[0] * (far ? 4.5 : 2), cy + (R() - 0.5) * box[1] * (far ? 3 : 2), far ? -box[2] - 2 - R() * 12 : (R() - 0.5) * box[2] * 2.4);
    c.copy(P[(R() * P.length) | 0]).multiplyScalar(bokeh ? 0.07 + R() * 0.06 : (far ? 0.3 : 0.2) + R() * 0.32);
    A.aCol.setXYZ(i, c.r, c.g, c.b);
    A.aSize.setX(i, bokeh ? 0.35 + R() * 0.45 : far ? 0.05 + R() * 0.07 : 0.025 + R() * 0.05);
    A.aSeed.setX(i, R());
  }
  const p = new THREE.Points(g, additive(DUST_V, POINT_FRAG, u)); p.renderOrder = 1; p.frustumCulled = false; scene.add(p);
  return p;
}
// marker textures: a lock-on reticle (four arcs + ticks) or a plain ring
export function ringTexture(reticle) {
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
export function sprite(scene, map, color, order, opacity = 0) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map, color: new THREE.Color(color), transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false }));
  s.renderOrder = order; s.visible = false; s.frustumCulled = false; scene.add(s); return s;
}
// guide lines with per-vertex colour (premultiplied by alpha) and optional dashes (aU >= 0: dash coordinate)
const GUIDE_V = `attribute vec3 aCol; attribute float aU; varying vec3 vColor; varying float vU;
void main(){ vColor = aCol; vU = aU; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const GUIDE_F = `varying vec3 vColor; varying float vU; void main(){ float d = vU < 0.0 ? 1.0 : step(0.5, fract(vU)); gl_FragColor = vec4(vColor * d, 1.0); }`;
export class Guides {
  constructor(scene, order = 3) { this.obj = new THREE.LineSegments(new THREE.BufferGeometry(), additive(GUIDE_V, GUIDE_F, {})); this.obj.renderOrder = order; this.obj.frustumCulled = false; scene.add(this.obj); this.reset(); }
  reset() { this.v = []; this.c = []; this.u = []; return this; }
  // segment a -> b, colour (THREE.Color or hex) x alpha, dash: dashes per world unit (0 = solid)
  seg(x0, y0, z0, x1, y1, z1, col, a, dash = 0) {
    const c = col.isColor ? col : _gc.set(col);
    this.v.push(x0, y0, z0, x1, y1, z1); this.c.push(c.r * a, c.g * a, c.b * a, c.r * a, c.g * a, c.b * a);
    const L = Math.hypot(x1 - x0, y1 - y0, z1 - z0); this.u.push(dash ? 0 : -1, dash ? L * dash : -1);
    return this;
  }
  commit() {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.v, 3)); g.setAttribute('aCol', new THREE.Float32BufferAttribute(this.c, 3)); g.setAttribute('aU', new THREE.Float32BufferAttribute(this.u, 1));
    this.obj.geometry.dispose(); this.obj.geometry = g; this.reset();
  }
}
const _gc = new THREE.Color();

// ------------------------------------------------------------------ camera framing
// The smallest camera distance at which every anchor point (Float32Array xyz) fits the free part of the card, for this
// yaw / pitch around target T, plus the off-axis lens shift that centres the anchors in that part.
// reg = [x0, x1, y0, y1] in NDC (-1..1) of the free area; m = [mx, my] the share of it to fill.
const FULL = [-1, 1, -1, 1], _ext = [0, 0, 0, 0];
let _cs = new Float32Array(0);
export function framing(cam, P, T, yaw, pitch, reg = FULL, m = [0.94, 0.9]) {
  const n = P.length / 3; if (!n) return [12, 0, 0];
  const tan = Math.tan(THREE.MathUtils.degToRad(cam.fov) / 2), ta = tan * cam.aspect;
  const mx = (reg[1] - reg[0]) / 2 * ta * m[0], my = (reg[3] - reg[2]) / 2 * tan * m[1];
  const cp = Math.cos(pitch), zx = Math.sin(yaw) * cp, zy = Math.sin(pitch), zz = Math.cos(yaw) * cp;
  const xl = Math.hypot(zz, zx), xx = zz / xl, xz = -zx / xl, yx = zy * xz, yy = zz * xx - zx * xz, yz = -zy * xx;
  if (_cs.length < P.length) _cs = new Float32Array(P.length);
  const C = _cs;
  for (let i = 0; i < n; i++) {
    const X = P[i * 3] - T.x, Y = P[i * 3 + 1] - T.y, Z = P[i * 3 + 2] - T.z;
    C[i * 3] = X * xx + Z * xz; C[i * 3 + 1] = X * yx + Y * yy + Z * yz; C[i * 3 + 2] = X * zx + Y * zy + Z * zz;
  }
  const ext = (L) => {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (let i = 0; i < n; i++) {
      const d = L - C[i * 3 + 2]; if (d < 0.4) return false;
      const X = C[i * 3] / d, Y = C[i * 3 + 1] / d;
      if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
    }
    _ext[0] = x0; _ext[1] = x1; _ext[2] = y0; _ext[3] = y1;
    return x1 - x0 <= 2 * mx && y1 - y0 <= 2 * my;
  };
  let lo = 1, hi = 200;
  for (let k = 0; k < 22; k++) { const mid = (lo + hi) / 2; if (ext(mid)) hi = mid; else lo = mid; }
  ext(hi);
  return [hi, (_ext[0] + _ext[1]) / 2 / ta - (reg[0] + reg[1]) / 2, (_ext[2] + _ext[3]) / 2 / tan - (reg[2] + reg[3]) / 2];
}
// the 8 corners of a box, appended to an anchor list
export const corners = (out, x0, x1, y0, y1, z0, z1) => { for (let i = 0; i < 8; i++) out.push(i & 1 ? x1 : x0, i & 2 ? y1 : y0, i & 4 ? z1 : z0); return out; };

// ------------------------------------------------------------------ html overlay
const CSS = `.fxh-ui{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:2;font-family:inherit;-webkit-user-select:none;user-select:none;opacity:0;transition:opacity .8s ease;color:#eef0fb;font-variant-numeric:tabular-nums}
.fxh-ui.on{opacity:1}
.fxh-l{position:absolute;left:0;top:0;white-space:nowrap;font-size:9px;font-weight:600;letter-spacing:.04em;line-height:1.1;color:rgba(188,192,236,.64);text-shadow:0 0 6px #07080c,0 0 2px #07080c}
.fxh-l.h{color:rgba(188,192,236,.44);font-weight:500;letter-spacing:.05em}
.fxh-l.t{font-size:10px;font-weight:700;letter-spacing:.02em;color:rgba(232,234,255,.92)}
.fxh-l.tag{font-size:10px;font-weight:700;letter-spacing:.01em;padding:3px 6px;border-radius:7px;background:rgba(10,8,24,.66);border:1px solid rgba(150,130,255,.24);text-shadow:none}
.fxh-l.fix{transform:none!important;left:auto;right:10px;top:auto;bottom:9px}
.fxh-leg{position:absolute;left:10px;top:9px;right:10px;display:flex;flex-wrap:wrap;gap:5px 10px;font-size:9px;font-weight:600;letter-spacing:.03em;line-height:1;color:rgba(188,192,236,.64)}
.fxh-leg span{display:inline-flex;align-items:center;gap:4px}
.fxh-leg i{display:inline-block;width:6px;height:6px;border-radius:50%;flex:none}
.fxh-leg b{color:rgba(232,234,255,.92);font-weight:700}
.fxh-tip{position:absolute;left:0;top:0;padding:6px 9px;border-radius:10px;background:rgba(13,10,28,.9);border:1px solid rgba(150,130,255,.3);color:#eef0fb;font-size:11px;font-weight:600;line-height:1.38;letter-spacing:0;white-space:nowrap;box-shadow:0 6px 22px rgba(0,0,0,.5),0 0 18px rgba(124,92,255,.22);opacity:0;transition:opacity .15s;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
.fxh-tip.on{opacity:1}.fxh-tip i{font-style:normal;color:rgba(188,192,236,.72);font-weight:500}.fxh-tip b{font-weight:700}
.fxh-tip u{text-decoration:none;font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:1px 5px;border-radius:5px;border:1px solid currentColor;margin-left:6px;vertical-align:1px}
.fxh-empty{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-size:12px;line-height:1.5;color:rgba(188,192,236,.62);display:none;text-align:center;white-space:nowrap;text-shadow:0 0 8px #07080c}`;
function injectCss() {
  if (document.getElementById('fxh-css')) return;
  const s = document.createElement('style'); s.id = 'fxh-css'; s.textContent = CSS; document.head.appendChild(s);
}
export function div(cls, parent, html) { const e = document.createElement('div'); e.className = cls; if (html != null) e.innerHTML = html; parent?.appendChild(e); return e; }
export function injectStyle(id, css) {
  if (document.getElementById(id)) return;
  const s = document.createElement('style'); s.id = id; s.textContent = css; document.head.appendChild(s);
}

const _v = new THREE.Vector3();
export class Hud extends View {
  // def: { name, fov, orbit, empty }
  constructor(opts = {}, def = {}) {
    super({ fov: def.fov || 38, dprMax: 2, ...opts, orbit: { ...(def.orbit || {}), ...(opts.orbit || {}) } });
    this.userRange = !!(opts.orbit && (opts.orbit.min != null || opts.orbit.max != null));
    this.canvas.classList.add('fx-' + (def.name || 'hud')); this.canvas.style.display = 'block'; // inline canvases leave a baseline gap
    this.canvas.style.cursor = 'grab';
    this.lt = 0; this.L = 12; this.Lset = false; this.sx = 0; this.sy = 0; this.T = new THREE.Vector3();
    this.anchors = new Float32Array(0); this.region = FULL; this.fill = [0.94, 0.9];
    this.textures = []; this.labels = []; this.camKey = ''; this.tipKey = null; this.tipLast = ''; this.sig = null;
    this._hoverAt = null;
    this.u = { uTime: { value: 0 }, uPix: { value: 500 }, uMotion: { value: Q.reduced ? 0 : 1 } };
    injectCss();
    const ui = this.ui = div('fxh-ui fxh-' + (def.name || 'hud')); ui.setAttribute('aria-hidden', 'true');
    this.tip = div('fxh-tip'); this.empty = div('fxh-empty'); this.empty.textContent = def.empty || 'No data yet';
    ui.append(this.empty, this.tip);
    const c = this.canvas;
    c.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse' || e.buttons) return;
      const r = c.getBoundingClientRect(); this._hoverAt = [e.clientX - r.left, e.clientY - r.top];
    });
    c.addEventListener('pointerleave', () => { this._hoverAt = null; this.hoverAt?.(null); });
  }
  // index.js does `view.opts = { ...view.opts, ...pageOpts }`: keep OUR screen-space pick wired to the canvas and remember
  // the page's onPick(row) callback separately
  get opts() { return this._o; }
  set opts(o) {
    o = o || {};
    if (!this._pickFn) this._pickFn = (x, y, e) => this.pickAt?.((x + 1) / 2 * this.w, (1 - y) / 2 * this.h, e);
    if (typeof o.onPick === 'function' && o.onPick !== this._pickFn) this._onRow = o.onPick;
    this._o = { ...o, onPick: this._pickFn };
  }
  emit(row) { if (this._onRow) { try { this._onRow(row); } catch (e) { console.warn('fx onPick', e); } } }
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
  onResize(w, h) {
    this.u.uPix.value = h * this.renderer.getPixelRatio() / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2));
    if (this.bgU) this.bgU.uAsp.value = w / h;
    this.Lset = false; this.camKey = '';
    this.relayout?.(w, h);
  }
  // camera: orbit around T at the distance that frames the anchors (eased -> a gentle dolly), lens shift applied
  camStep(dt) {
    const o = this.orbitStep(dt), T = this.T, cam = this.camera, cp = Math.cos(o.pitch);
    const [L, sx, sy] = framing(cam, this.anchors, T, o.yaw, o.pitch, this.region, this.fill);
    const k = this.Lset ? Math.min(1, dt * 2.2) : 1; this.Lset = true;
    this.L += (L - this.L) * k; this.sx += (sx - this.sx) * k; this.sy += (sy - this.sy) * k;
    cam.position.set(T.x + Math.sin(o.yaw) * cp * this.L, T.y + Math.sin(o.pitch) * this.L, T.z + Math.cos(o.yaw) * cp * this.L);
    cam.lookAt(T); cam.updateMatrixWorld(); cam.updateProjectionMatrix();
    const pe = cam.projectionMatrix.elements; pe[8] += this.sx; pe[9] += this.sy; cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
    const key = o.yaw.toFixed(4) + '|' + o.pitch.toFixed(4) + '|' + this.L.toFixed(3) + '|' + this.sx.toFixed(4) + '|' + this.sy.toFixed(4) + '|' + this.w + 'x' + this.h;
    const moved = key !== this.camKey; this.camKey = key;
    return moved;
  }
  // screen position of a world point (css px inside the card)
  screen(p, out = { x: 0, y: 0, z: 0 }) { _v.copy(p).project(this.camera); out.x = (_v.x + 1) / 2 * this.w; out.y = (1 - _v.y) / 2 * this.h; out.z = _v.z; return out; }

  // ---------------------------------------------------------------- labels
  // def: { text | html, p: Vector3 | at(): Vector3|null, ax, ay (anchor 0..1, default .5), dx, dy, cls, color,
  //        tick: group name (ticks of a group that would overlap are dropped), avoid: true (dropped when it overlaps an
  //        earlier avoid label), show(): bool, keep: true (clamped into the card instead of hidden at the edges) }
  setLabels(defs) {
    for (const l of this.labels) l.el.remove();
    this.labels = defs.filter(Boolean).map((d) => {
      const e = div('fxh-l' + (d.cls ? ' ' + d.cls : '')); if (d.html != null) e.innerHTML = d.html; else e.textContent = d.text;
      if (d.color) e.style.color = d.color;
      this.ui.insertBefore(e, this.tip); return { ...d, el: e, last: '', wid: null, hgt: 0 };
    });
    this.camKey = '';
  }
  placeLabels() {
    const w = this.w, h = this.h, live = this.ui.isConnected, groups = new Map(), boxes = [];
    for (const l of this.labels) {
      if (l.wid == null && live) { l.wid = l.el.offsetWidth || 20; l.hgt = l.el.offsetHeight || 10; }
      const p = l.at ? l.at() : l.p;
      l.hidden = !p || (l.show && !l.show());
      if (l.hidden) continue;
      _v.copy(p).project(this.camera);
      l.px = (_v.x + 1) / 2 * w; l.py = (1 - _v.y) / 2 * h;
      const [x, y] = this.labelAt(l, l);
      l.hidden = _v.z > 1 || y < 2 || y > h - (l.hgt || 10) - 2;
      l.x = x; l.y = y;
      if (!l.hidden && l.tick) { if (!groups.has(l.tick)) groups.set(l.tick, []); groups.get(l.tick).push(l); }
    }
    for (const g of groups.values()) {
      g.sort((a, b) => a.x - b.x); let right = -1e9;
      for (const l of g) { if (l.x < right + 6) l.hidden = true; else right = l.x + (l.wid || 20); }
    }
    this.adjustLabels?.(this.labels);
    for (const g of groups.values()) for (const l of g) if (!l.hidden) boxes.push([l.x - 2, l.y - 1, l.x + (l.wid || 20) + 2, l.y + (l.hgt || 10) + 1]);
    const hits = (x, y, l) => { const x0 = x - 2, y0 = y - 1, x1 = x + (l.wid || 20) + 2, y1 = y + (l.hgt || 10) + 1; return boxes.some((b) => x0 < b[2] && x1 > b[0] && y0 < b[3] && y1 > b[1]); };
    for (const l of this.labels) {
      if (!l.hidden && l.avoid) {
        // the primary spot, then the fallback spots (alts: [{ ax, ay, dx, dy }]) before giving up
        let ok = !hits(l.x, l.y, l);
        for (const a of l.alts || []) { if (ok) break; const [x, y] = this.labelAt(l, a); if (!hits(x, y, l) && y >= 2 && y <= this.h - (l.hgt || 10) - 2) { l.x = x; l.y = y; ok = true; } }
        if (ok) boxes.push([l.x - 2, l.y - 1, l.x + (l.wid || 20) + 2, l.y + (l.hgt || 10) + 1]); else l.hidden = true;
      }
      const tf = l.hidden ? 'translate3d(-999px,-999px,0)' : `translate3d(${l.x.toFixed(1)}px,${l.y.toFixed(1)}px,0)`;
      if (tf !== l.last) { l.el.style.transform = tf; l.last = tf; }
    }
  }

  labelAt(l, a) {
    const wid = l.wid || 20, hg = l.hgt || 10;
    const x = clamp(l.px + (a.dx || 0) - (a.ax ?? 0.5) * wid, 4, Math.max(4, this.w - wid - 4));
    let y = l.py + (a.dy || 0) - (a.ay ?? 0.5) * hg; if (l.keep) y = clamp(y, 4, Math.max(4, this.h - hg - 4));
    return [x, y];
  }

  // ---------------------------------------------------------------- tooltip
  showTip(key, html) {
    if (key == null) { this.tip.classList.remove('on'); this.tipKey = null; return; }
    if (key !== this.tipKey) { this.tip.innerHTML = html; this.tipKey = key; this.tipW = this.tip.offsetWidth; this.tipH = this.tip.offsetHeight; this.tipLast = ''; }
    this.tip.classList.add('on');
  }
  placeTip(sx, sy, gap = 14) {
    if (this.tipKey == null) return;
    const tw = this.tipW || 160, th = this.tipH || 26;
    const x = clamp(sx - tw / 2, 6, Math.max(6, this.w - tw - 6)); let y = sy - th - gap; if (y < 6) y = Math.min(sy + gap, this.h - th - 4);
    const tf = `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0)`;
    if (tf !== this.tipLast) { this.tip.style.transform = tf; this.tipLast = tf; }
  }
}
