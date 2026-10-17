// Loss Lab (Lab -> Losses): every losing trade of the baseline run as a glowing point in a 3D scatter.
//   x = MFE (the best point the trade reached, in R), y = result R (losses hang under the glowing 0R "break-even"
//   ceiling on drop lines), z = stop size in points (small stops in front). Clusters are coloured by kind ("never
//   worked" magenta, "gave back" amber, "wide stop" blue, "normal" violet, any other kind a neutral lavender); every
//   cluster has a nebula glow at its centre with its name and count and faint threads from its trades to it. A sheet of
//   light at MFE 1R marks where the live rules move the stop to breakeven; a dashed line marks a full -1R stop.
//   Legend with counts and share: tap a chip to isolate that kind (tap again for all). Tap a point -> opts.onPick(trade)
//   (the page's trade object); mouse hover shows the tooltip; drag to orbit.
//   First data: the trades rain down from the ceiling; new data: survivors glide, newcomers drop in, leavers fade.
// setData({ trades: [{ r, mfe, mae, risk_pts, day, kind }] })
// Draw calls ~16 whatever the trade count; particles: 1 point + 1 floor shadow per trade + 800 dust (280 lite).
import { THREE, Q, theme, POINT_FRAG, count, Hud, addBackdrop, addNebula, addDust, Guides, ringTexture, sprite, additive, attrs, paintBackdrop,
  clamp, smooth, outCubic, outBack, fract, num, esc, hash, fmtR, pct, corners, div, injectStyle } from './hud.js';

const KIND = {
  'never worked': { col: '#ff2bd6', css: '#ff6bd5' },
  'gave back': { col: '#ff9b3d', css: '#ffb36b' },
  'wide stop': { col: '#4f8bff', css: '#86aeff' },
  normal: { col: '#a78bfa', css: '#c4b5fd' },
};
const OTHER = { col: '#9aa0c8', css: '#c3c6e6' };
const FLY = 1, MOVE = 2, SHRINK = 4;
const _v = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color();
const ptsTxt = (v) => Math.round(v) + ' pt';
const rTxt = (v) => (v === 0 ? '0R' : (v < 0 ? '−' : '') + (Math.abs(v) % 1 ? Math.abs(v).toFixed(1) : Math.abs(v)) + 'R');

// ------------------------------------------------------------------ shaders
const PT_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; attribute vec4 aMisc;
uniform float uTime; uniform float uPix; uniform float uMotion; uniform float uSel; uniform float uHov; uniform float uIso; uniform float uFocus;
varying vec3 vColor; varying float vAlpha; varying float vHi;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float tw = 1.0 + 0.1 * sin(uTime * uMotion * (1.0 + aMisc.x * 2.0) + aMisc.x * 50.0);
  vHi = max(1.0 - step(0.5, abs(aMisc.y - uSel)), (1.0 - step(0.5, abs(aMisc.y - uHov))) * 0.75);
  float iso = uIso < -0.5 ? 1.0 : mix(0.12, 1.15, 1.0 - step(0.5, abs(aMisc.z - uIso)));
  gl_PointSize = clamp(aSize * uPix * tw * (1.0 + vHi * 0.6) / -mv.z, 0.0, 110.0);
  gl_Position = projectionMatrix * mv;
  float depth = clamp(1.15 - (-mv.z - uFocus) * 0.07, 0.7, 1.2);
  vColor = aCol * depth; vAlpha = aAlpha * iso;
}`;
const PT_F = `varying vec3 vColor; varying float vAlpha; varying float vHi;
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2), halo = 1.0 - d2; halo = halo * halo * halo;
  float core = exp(-d2 * 28.0), hi = vHi * exp(-pow((d - 0.84) * 10.0, 2.0));
  vec3 c = mix(vColor, vec3(1.0), clamp(core * 0.5 + hi * 0.3, 0.0, 1.0));
  gl_FragColor = vec4(c * (halo * 0.45 + core * 1.0 + hi * 0.9) * vAlpha, 1.0);
}`;
const SHADOW_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; attribute vec4 aMisc; uniform float uPix; uniform float uFloor; uniform float uIso;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position.x, uFloor + 0.004, position.z, 1.0);
  gl_PointSize = clamp(aSize * 0.55 * uPix / -mv.z, 0.0, 40.0); gl_Position = projectionMatrix * mv;
  float iso = uIso < -0.5 ? 1.0 : mix(0.1, 1.0, 1.0 - step(0.5, abs(aMisc.z - uIso)));
  vColor = aCol * 0.3; vAlpha = aAlpha * iso; }`;
// drop lines from the 0R ceiling (aT 0) to the trade (aT 1) and threads from a trade (aT 1) to its cluster centre (aT 0)
const LINE_V = `attribute vec3 aCol; attribute float aT; attribute float aA; attribute vec2 aId;
uniform float uSel; uniform float uHov; uniform float uIso; varying vec3 vColor; varying float vA; varying float vT; varying float vHi;
void main(){ gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); vColor = aCol; vT = aT;
  float iso = uIso < -0.5 ? 1.0 : mix(0.08, 1.2, 1.0 - step(0.5, abs(aId.y - uIso)));
  vA = aA * iso; vHi = max(1.0 - step(0.5, abs(aId.x - uSel)), (1.0 - step(0.5, abs(aId.x - uHov))) * 0.7); }`;
const LINE_F = `uniform float uK; varying vec3 vColor; varying float vA; varying float vT; varying float vHi;
void main(){ gl_FragColor = vec4(vColor * vA * (0.15 + 0.85 * vT) * uK * (1.0 + vHi * 3.0), 1.0); }`;
// cluster centres: big soft nebula glows
const NEB_V = `attribute vec3 aCol; attribute float aSize; attribute float aA; uniform float uPix; uniform float uTime; uniform float uMotion;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); float b = 1.0 + 0.08 * sin(uTime * uMotion * 0.9 + position.x * 3.0);
  gl_PointSize = clamp(aSize * b * uPix / -mv.z, 0.0, 420.0); gl_Position = projectionMatrix * mv; vColor = aCol; vAlpha = aA; }`;
const NEB_F = `varying vec3 vColor; varying float vAlpha;
void main(){ vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float a = exp(-d2 * 3.2) * (1.0 - d2) * 0.5 + exp(-d2 * 40.0) * 0.5; gl_FragColor = vec4(vColor * a * vAlpha, 1.0); }`;
const WALL_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
// the 0R ceiling: glass with a fine grid, a glowing rim and a slow scan
const CEIL_F = `uniform vec2 uX; uniform vec2 uZ; uniform vec3 uC1; uniform vec3 uC2; uniform float uTime; uniform float uMotion; uniform float uIn; varying vec3 vW;
float grid(vec2 p, vec2 s){ vec2 c = p / s; vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c); return 1.0 - min(min(g.x, g.y), 1.0); }
void main(){
  vec2 p = vW.xz, lo = vec2(uX.x, uZ.x), hi = vec2(uX.y, uZ.y), e = min(p - lo, hi - p); float edge = min(e.x, e.y);
  if (edge < 0.0) discard;
  vec2 c = (p - (lo + hi) * 0.5) / ((hi - lo) * 0.5); float sx = (p.x - lo.x) / (hi.x - lo.x);
  float t = uTime * uMotion, scan = exp(-pow((sx - fract(t * 0.05)) * 12.0, 2.0)) * uMotion;
  float g = grid(p - lo, (hi - lo) / vec2(8.0, 5.0));
  vec3 col = mix(uC1, uC2, clamp(sx * 0.8 + scan * 0.5, 0.0, 1.0));
  float a = (exp(-dot(c, c) * 1.3) * 0.08 + g * 0.1 * (0.6 + scan) + scan * 0.04) * uIn + exp(-edge * 30.0) * 0.55 + exp(-edge * 6.0) * 0.04;
  gl_FragColor = vec4(col * a, 1.0);
}`;
const SHEET_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const SHEET_F = `uniform vec3 uCol; uniform float uTime; uniform float uMotion; uniform float uA; varying vec2 vUv;
void main(){ vec2 e = min(vUv, 1.0 - vUv); float edge = min(e.x, e.y);
  float scan = exp(-pow((vUv.y - fract(uTime * 0.12 * uMotion)) * 10.0, 2.0)) * uMotion;
  gl_FragColor = vec4(uCol * (0.035 + exp(-edge * 50.0) * 0.35 + scan * 0.05) * uA, 1.0); }`;

const CSS = `.fxh-losses .fxh-leg span{pointer-events:auto;cursor:pointer;padding:3px 6px;margin:-3px -2px;border-radius:7px;border:1px solid transparent;transition:background .2s,border-color .2s,opacity .2s}
.fxh-losses .fxh-leg span.on{background:rgba(124,92,255,.18);border-color:rgba(167,139,250,.45)}
.fxh-losses .fxh-leg.iso span:not(.on){opacity:.45}
.fxh-losses .fxh-leg em{font-style:normal;font-weight:500;color:rgba(188,192,236,.5)}
.fxh-losses .fxh-l.cl{font-size:10px;font-weight:800;letter-spacing:.02em;text-shadow:0 0 8px #07080c,0 0 3px #07080c}`;

// ------------------------------------------------------------------ the view
export class Losses extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'losses', fov: 36, empty: 'No losing trades',
      orbit: { yaw: -0.3, pitch: 0.24, auto: 0.035, min: -0.8, max: 0.8, pitchMin: 0.05, pitchMax: 0.8 } });
    injectStyle('fxh-los-css', CSS);
    this.W = 6; this.H = 3.2; this.D = 3; this.slots = []; this.byKey = new Map(); this.items = []; this.cap = 0; this.animating = false;
    this.kinds = []; this.iso = -1; this.dropA = 0.4; this.introDone = false; this.introAt = -1; this.sel = null; this.hov = null;
    this.dom = { x1: 2, y0: -1.2, z0: 10, z1: 60 };
    Object.assign(this.u, { uSel: { value: -1 }, uHov: { value: -1 }, uIso: { value: -1 }, uFocus: { value: 12 }, uFloor: { value: -3.3 } });
    this.build(); this.ensureCap(128);
    this.legend = div('fxh-leg'); this.ui.prepend(this.legend);
    this.legend.addEventListener('click', (e) => {
      const s = e.target.closest('span[data-k]'); if (!s) return;
      const k = +s.dataset.k; this.setIso(this.iso === k ? -1 : k);
    });
    this.hint = div('fxh-l h fix', this.ui);
  }
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.5]);
    addNebula(S, [['#6d28d9', -5, 2.5, -9, 15, 8, 0.1], ['#ff2bd6', 5, -1, -9, 12, 7, 0.05]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 650 : 800, 280), box: [6.5, 2.5, 3.5], cy: -1.5, seed: 61 });
    this.cU = { uX: { value: new THREE.Vector2() }, uZ: { value: new THREE.Vector2() }, uC1: { value: new THREE.Color('#5b3bd1') }, uC2: { value: new THREE.Color('#22d3ee') }, uTime: u.uTime, uMotion: u.uMotion, uIn: { value: 1 } };
    this.ceil = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(WALL_V, CEIL_F, this.cU, { side: THREE.DoubleSide, extensions: { derivatives: true } }));
    this.ceil.rotation.x = -Math.PI / 2; this.ceil.renderOrder = 2; S.add(this.ceil);
    this.fU = { ...this.cU, uX: { value: new THREE.Vector2() }, uZ: { value: new THREE.Vector2() }, uC1: { value: new THREE.Color('#3b2a9a') }, uC2: { value: new THREE.Color('#5b3bd1') }, uIn: { value: 0.5 } };
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(WALL_V, CEIL_F, this.fU, { side: THREE.DoubleSide, extensions: { derivatives: true } }));
    this.floor.rotation.x = -Math.PI / 2; this.floor.renderOrder = 1; S.add(this.floor);
    this.sU = { uCol: { value: new THREE.Color('#2ee5c8') }, uTime: u.uTime, uMotion: u.uMotion, uA: { value: 1 } };
    this.sheet = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(SHEET_V, SHEET_F, this.sU, { side: THREE.DoubleSide })); this.sheet.rotation.y = Math.PI / 2; this.sheet.renderOrder = 3; S.add(this.sheet);
    this.guides = new Guides(S, 3);
    this.nebs = new THREE.Points(attrs(8, { position: [3, 1], aCol: [3, 1], aSize: [1, 1], aA: [1, 1] }), additive(NEB_V, NEB_F, u)); this.nebs.renderOrder = 4; S.add(this.nebs);
    const ret = ringTexture(true); this.textures.push(ret);
    this.reticle = sprite(S, ret, '#ffffff', 12);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(128, Math.ceil(n * 1.25 / 64) * 64), u = this.u;
    const pg = attrs(cap, { position: [3, 1], aCol: [3], aSize: [1, 1], aAlpha: [1, 1], aMisc: [4] });
    const lg = attrs(cap * 4, { position: [3, 1], aCol: [3], aT: [1], aA: [1, 1], aId: [2] });
    if (!this.pts) {
      this.dU = { ...u, uK: { value: 1 } };
      this.drops = new THREE.LineSegments(lg, additive(LINE_V, LINE_F, this.dU));
      this.shadows = new THREE.Points(pg, additive(SHADOW_V, POINT_FRAG, u));
      this.pts = new THREE.Points(pg, additive(PT_V, PT_F, u));
      this.drops.renderOrder = 5; this.shadows.renderOrder = 5; this.pts.renderOrder = 8;
      for (const o of [this.drops, this.shadows, this.pts]) { o.frustumCulled = false; this.scene.add(o); }
    } else { this.pts.geometry.dispose(); this.drops.geometry.dispose(); this.pts.geometry = pg; this.shadows.geometry = pg; this.drops.geometry = lg; }
    this.cap = cap;
  }
  retheme() { paintBackdrop(this.bgU); }
  shape(w, h) {
    const asp = w / h, W = 5.6 * Math.pow(clamp(asp / 1.1, 1, 2.4), 0.8), H = 3.0 * clamp(1.3 / asp, 0.85, 1.2), D = 3.0;
    const changed = Math.abs(W - this.W) > 0.15 || Math.abs(H - this.H) > 0.08;
    this.W = W; this.H = H; this.D = D; return changed;
  }
  relayout(w, h) {
    this.regionFix();
    if (this.shape(w, h) || !this.framed) { this.framed = true; if (this.items.length) { this.layout(); this.retarget(0.6); } this.frameScene(); }
  }
  regionFix() { const lh = this.legend?.isConnected ? this.legend.offsetHeight : 14; this.region = [-1, 1, -1 + 2 * 18 / this.h, 1 - 2 * (lh + 14) / this.h]; }
  attach(el) { super.attach(el); this.regionFix(); }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const list = d && Array.isArray(d.trades) ? d.trades : Array.isArray(d) ? d : [];
    const items = [], seen = new Set(), kinds = new Map();
    let sig = list.length + ':';
    for (let i = 0; i < list.length; i++) {
      const t = list[i]; if (!t || typeof t !== 'object') continue;
      const r = num(t.r), mfe = num(t.mfe, 0), stop = num(t.risk_pts, NaN), kind = String(t.kind ?? 'normal') || 'normal';
      if (!Number.isFinite(r)) continue;
      let key = String(t.day ?? '') + '|' + r + '|' + mfe + '|' + stop; if (seen.has(key)) key += '#' + i; seen.add(key);
      if (!kinds.has(kind)) kinds.set(kind, { name: kind, n: 0, ...(KIND[kind] || OTHER), sx: 0, sy: 0, sz: 0 });
      kinds.get(kind).n++;
      items.push({ key, t, r, mfe: Math.max(0, mfe), stop, kind, seed: hash(key) });
      sig += key + '/' + kind + ',';
    }
    if (sig === this.sig) { for (const it of items) { const s = this.byKey.get(it.key); if (s) s.it.t = it.t; } return; }
    this.sig = sig;
    // kinds: the four known ones first (fixed colours), then the rest by count
    const order = [...kinds.values()].sort((a, b) => ((KIND[a.name] ? 0 : 1) - (KIND[b.name] ? 0 : 1)) || b.n - a.n);
    order.forEach((k, i) => { k.i = i; });
    this.kinds = order; for (const it of items) it.ki = kinds.get(it.kind).i;
    if (this.iso >= order.length) this.iso = -1;
    this.items = items; this.layout();
    const first = !this.slots.length && !this.introDone, now = this.lt, red = Q.reduced, n = items.length;
    const next = [], keep = new Set();
    items.forEach((it, i) => {
      let sl = this.byKey.get(it.key);
      if (sl && !sl.dead) { sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.mode = MOVE; sl.t0 = now; sl.dur = red ? 0 : 0.9; }
      else {
        sl = { key: it.key, p: new THREE.Vector3(), p0: new THREE.Vector3(), p1: new THREE.Vector3(), s: 0, s0: 0, a: 0, a0: 0, dead: false, done: false, col: new THREE.Color() };
        sl.mode = FLY; sl.t0 = now + (first ? 0.3 + clamp(it.tx / this.W + 0.5, 0, 1) * 1.1 + it.seed * 0.35 : 0.05 + it.seed * 0.4); sl.dur = first ? 1.0 : 0.75;
        if (red) { sl.t0 = now; sl.dur = 0; }
      }
      sl.it = it; sl.done = false; sl.p1.set(it.tx, it.ty, it.tz); if (sl.mode === FLY) sl.p0.set(it.tx, 0.02, it.tz);
      keep.add(it.key); next.push(sl);
    });
    for (const sl of this.slots) {
      if (keep.has(sl.key) || sl.dead) continue;
      sl.dead = true; sl.done = false; sl.mode = SHRINK; sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.t0 = now; sl.dur = red ? 0 : 0.5;
      next.push(sl);
    }
    this.slots = next; this.byKey.clear();
    for (const sl of next) if (!sl.dead) this.byKey.set(sl.key, sl);
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.hoverAt(null);
    this.recolor(); this.writeStatic(); this.animating = true;
    if (first && n) { this.introAt = red ? -1 : now; this.introDone = true; }
    this.frameScene();
    this.empty.style.display = n ? 'none' : 'block';
    this.ui.classList.add('on');
    this.tipKey = null; this.tipFor(this.hov || this.sel);
  }
  layout() {
    const its = this.items, W = this.W, H = this.H, D = this.D;
    const mf = its.map((it) => it.mfe).sort((a, b) => a - b), q97 = mf.length ? mf[Math.floor(0.97 * (mf.length - 1))] : 1;
    const x1 = clamp(Math.max(1.6, q97 * 1.08), 1.6, 5);
    const rmin = its.length ? Math.min(...its.map((it) => it.r)) : -1;
    const y0 = clamp(Math.min(-1.15, rmin - 0.05), -2.6, -1.15);
    const st = its.map((it) => it.stop).filter(Number.isFinite), z0 = Math.min(10, ...st), z1 = Math.max(60, ...st.filter((v) => v <= 120));
    this.dom = { x1, y0, z0, z1 };
    for (const it of its) {
      it.tx = clamp(it.mfe / x1, 0, 1) * W - W / 2;
      it.ty = clamp(it.r, y0, 0.3) / -y0 * H;
      it.tz = D / 2 - clamp(((Number.isFinite(it.stop) ? it.stop : (z0 + z1) / 2) - z0) / (z1 - z0), 0, 1) * D + (it.seed - 0.5) * 0.06;
      it.off = it.mfe > x1 || it.r < y0;
    }
    // cluster centres
    for (const k of this.kinds) { k.sx = k.sy = k.sz = 0; k.m = 0; }
    for (const it of its) { const k = this.kinds[it.ki]; k.sx += it.tx; k.sy += it.ty; k.sz += it.tz; k.m++; }
    for (const k of this.kinds) { const m = Math.max(1, k.m); k.c = new THREE.Vector3(k.sx / m, k.sy / m, k.sz / m); }
  }
  X(v) { return clamp(v / this.dom.x1, 0, 1) * this.W - this.W / 2; }
  Y(v) { return v / -this.dom.y0 * this.H; }
  Z(v) { const d = this.dom; return this.D / 2 - clamp((v - d.z0) / (d.z1 - d.z0), 0, 1) * this.D; }
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
    const n = this.items.length, dens = clamp(1.15 - n / 900, 0.72, 1.08);
    this.dropA = clamp(0.5 - n / 900, 0.1, 0.42);   // dense clouds get faint lines
    for (const sl of this.slots) {
      const it = sl.it, k = this.kinds[it.ki] || OTHER;
      sl.col.set(k.col).multiplyScalar(it.kind === 'normal' ? 0.85 : 1.1);
      sl.size = (0.13 + 0.05 * clamp(-it.r, 0, 1.5)) * dens;
    }
  }
  writeStatic() {
    const n = this.slots.length; this.ensureCap(n);
    const P = this.pts.geometry.attributes, L = this.drops.geometry.attributes;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], c = sl.col, it = sl.it; sl.idx = i;
      P.aCol.setXYZ(i, c.r, c.g, c.b); P.aMisc.setXYZW(i, it.seed, i, it.ki, 0);
      for (let j = 0; j < 4; j++) { const q = i * 4 + j, k = j < 2 ? 0.55 : 0.6; L.aCol.setXYZ(q, c.r * k, c.g * k, c.b * k); L.aT.setX(q, j === 1 || j === 2 ? 1 : 0); L.aId.setXY(q, i, it.ki); }
    }
    for (const a of [P.aCol, P.aMisc, L.aCol, L.aT, L.aId]) a.needsUpdate = true;
    this.pts.geometry.setDrawRange(0, n); this.drops.geometry.setDrawRange(0, n * 4);
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
  }
  writeDynamic() {
    const n = this.slots.length, P = this.pts.geometry.attributes, L = this.drops.geometry.attributes, thr = Q.level !== 'lite';
    const PP = P.position.array, PZ = P.aSize.array, PA = P.aAlpha.array, LP = L.position.array, LA = L.aA.array;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], p = sl.p, o = i * 12, k = this.kinds[sl.it.ki], c = k?.c || p;
      PP[i * 3] = p.x; PP[i * 3 + 1] = p.y; PP[i * 3 + 2] = p.z; PZ[i] = sl.size * sl.s; PA[i] = sl.a;
      // drop line: ceiling -> trade; thread: trade -> cluster centre
      LP[o] = p.x; LP[o + 1] = 0; LP[o + 2] = p.z; LP[o + 3] = p.x; LP[o + 4] = p.y; LP[o + 5] = p.z;
      LP[o + 6] = p.x; LP[o + 7] = p.y; LP[o + 8] = p.z; LP[o + 9] = c.x; LP[o + 10] = c.y; LP[o + 11] = c.z;
      LA[i * 4] = LA[i * 4 + 1] = sl.a * this.dropA; LA[i * 4 + 2] = LA[i * 4 + 3] = thr ? sl.a * this.dropA * 0.5 : 0;
    }
    for (const at of [P.position, P.aSize, P.aAlpha, L.position, L.aA]) at.needsUpdate = true;
  }
  animate() {
    const now = this.lt; let busy = false, dead = false;
    for (const sl of this.slots) {
      if (sl.done) { dead ||= sl.dead; continue; }
      const k = sl.dur > 0 ? clamp((now - sl.t0) / sl.dur, 0, 1) : 1, p = sl.p;
      if (sl.mode === FLY) { const e = outCubic(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = k > 0 ? 0.4 + 0.6 * outBack(k) : 0; sl.a = smooth(Math.min(1, k * 3)); }
      else if (sl.mode === MOVE) { const e = smooth(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = sl.s0 + (1 - sl.s0) * e; sl.a = sl.a0 + (1 - sl.a0) * e; }
      else { const e = smooth(k); p.copy(sl.p0); sl.s = sl.s0 * (1 - e); sl.a = sl.a0 * (1 - e); }
      if (k >= 1) { sl.done = true; dead ||= sl.dead; } else busy = true;
    }
    if (!busy && dead) { this.slots = this.slots.filter((s) => !s.dead); this.writeStatic(); }
    this.writeDynamic();
    if (!busy) this.animating = false;
  }

  // ---------------------------------------------------------------- frame: ceiling, floor, sheet, guides, labels
  frameScene() {
    const W = this.W, H = this.H, D = this.D, d = this.dom, x0 = -W / 2 - 0.25, x1 = W / 2 + 0.25, zf = D / 2 + 0.3, zb = -D / 2 - 0.3, yb = -H - 0.12;
    this.ceil.position.set(0, 0, 0); this.ceil.scale.set(x1 - x0, zf - zb, 1); this.cU.uX.value.set(x0, x1); this.cU.uZ.value.set(zb, zf);
    this.floor.position.set(0, yb, 0); this.floor.scale.set(x1 - x0, zf - zb, 1); this.fU.uX.value.set(x0, x1); this.fU.uZ.value.set(zb, zf);
    this.u.uFloor.value = yb;
    const one = this.X(1);
    this.sheet.visible = d.x1 > 1.05; this.sheet.position.set(one, yb / 2, 0); this.sheet.scale.set(zf - zb, -yb, 1);
    const G = this.guides, vio = new THREE.Color('#8f86ff'), mag = new THREE.Color('#ff4fd8');
    const xt = [0, 0.5, 1, 1.5, 2, 3, 4, 5].filter((v) => v <= d.x1 + 1e-6), yt = [0, -0.5, -1, -1.5, -2, -2.5].filter((v) => v >= d.y0 - 1e-6), zt = [10, 20, 30, 40, 50, 60, 80, 100].filter((v) => v >= d.z0 && v <= d.z1);
    for (const v of xt) { const x = this.X(v); G.seg(x, yb, zb, x, 0, zb, vio, 0.08, 4).seg(x, yb, zb, x, yb, zf, vio, 0.07, 4); }
    for (const v of yt) { const y = this.Y(v); G.seg(x0, y, zb, x1, y, zb, v === -1 ? mag : vio, v === -1 ? 0.32 : 0.08, 4); G.seg(x0, y, zb, x0, y, zf, v === -1 ? mag : vio, v === -1 ? 0.2 : 0.06, 4); }
    for (const v of zt) { const z = this.Z(v); G.seg(x0, yb, z, x1, yb, z, vio, 0.06, 3); }
    G.seg(x0, yb, zb, x0, 0, zb, vio, 0.3).seg(x0, yb, zb, x1, yb, zb, vio, 0.25).seg(x1, yb, zb, x1, yb, zf, vio, 0.25);
    G.commit();
    this.anchors = new Float32Array(corners([], x0 - 0.4, x1 + 0.5, yb - 0.25, 0.25, zb, zf + 0.25));
    this.T.set(0, yb / 2, 0);
    // centre glows
    const NA = this.nebs.geometry.attributes, tot = Math.max(1, this.items.length), K = this.kinds.slice(0, 8);
    K.forEach((k, i) => {
      NA.position.setXYZ(i, k.c.x, k.c.y, k.c.z); _c.set(k.col).multiplyScalar(0.55); NA.aCol.setXYZ(i, _c.r, _c.g, _c.b);
      NA.aSize.setX(i, 0.9 + 1.6 * Math.sqrt(k.n / tot)); NA.aA.setX(i, 0.5 + 0.5 * Math.sqrt(k.n / tot));
    });
    for (const a of [NA.position, NA.aCol, NA.aSize, NA.aA]) a.needsUpdate = true;
    this.nebs.geometry.setDrawRange(0, K.length);
    // labels
    const defs = [];
    for (const k of K) defs.push({ html: `${esc(k.name)} <span style="opacity:.75">${k.n}</span>`, at: () => k.c, ay: 0.5, cls: 'cl', color: k.css, avoid: true, keep: true,
      show: () => this.introAt < 0 && (this.iso < 0 || this.iso === k.i) });
    for (const v of xt) defs.push({ text: rTxt(v), p: new THREE.Vector3(this.X(v), yb, zf), ay: 0, dy: 4, tick: 'x', color: v === 1 ? '#5eead4' : null });
    defs.push({ text: 'best point it reached (MFE) →', p: new THREE.Vector3(x1, yb, zf), ax: 1, ay: 0, dy: 17, cls: 't' });
    for (const v of yt) defs.push({ text: rTxt(v), p: new THREE.Vector3(x0 - 0.1, this.Y(v), zb), ax: 1, avoid: true, color: v === -1 ? '#ff8ae0' : null });
    defs.push({ text: 'result', p: new THREE.Vector3(x0, 0, zb), ax: 1, ay: 1, dy: -6, dx: -6, cls: 't', avoid: true });
    for (const v of zt.filter((v) => v === d.z0 || v === d.z1 || v === 30)) defs.push({ text: ptsTxt(v), p: new THREE.Vector3(x1 + 0.08, yb, this.Z(v)), ax: 0, cls: 'h', avoid: true });
    if (this.sheet.visible) defs.push({ text: 'stop to BE at 1R', p: new THREE.Vector3(one, 0, zb), ax: 0.5, ay: 1, dy: -5, cls: 'h', color: '#5eead4', avoid: true });
    this.setLabels(defs);
    this.legendFor();
    const n = this.items.length;
    this.hint.textContent = n ? `${n} losing trade${n === 1 ? '' : 's'} · tap a point` : '';
  }
  legendFor() {
    const tot = Math.max(1, this.items.length);
    this.legend.innerHTML = this.kinds.map((k) => `<span data-k="${k.i}" class="fx-tap${this.iso === k.i ? ' on' : ''}"><i style="background:${k.css};box-shadow:0 0 6px ${k.css}"></i>${esc(k.name)} <b>${k.n}</b> <em>${pct(k.n / tot * 100)}</em></span>`).join('');
    this.legend.classList.toggle('iso', this.iso >= 0);
    this.regionFix();
  }
  setIso(k) {
    this.iso = k; this.u.uIso.value = k;
    this.legendFor(); this.camKey = '';
    if (this.sel && k >= 0 && this.sel.it.ki !== k) this.select(null);
  }

  // ---------------------------------------------------------------- picking + tooltip
  nearest(px, py, maxPx) {
    const cam = this.camera; _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    let best = null, bd = maxPx * maxPx;
    for (const sl of this.slots) {
      if (sl.dead || sl.a < 0.3 || (this.iso >= 0 && sl.it.ki !== this.iso)) continue;
      _v.copy(sl.p).applyMatrix4(_m); if (_v.z > 1) continue;
      const dx = (_v.x + 1) / 2 * this.w - px, dy = (1 - _v.y) / 2 * this.h - py, dd = dx * dx + dy * dy;
      if (dd < bd) { bd = dd; best = sl; }
    }
    return best;
  }
  pickAt(px, py) { const sl = this.nearest(px, py, 22); this.select(sl); if (sl) this.emit(sl.it.t); }
  select(sl) { this.sel = sl; this.u.uSel.value = sl ? sl.idx : -1; this.tipFor(this.hov || sl); }
  hoverAt(sl) {
    if (sl === this.hov) return;
    this.hov = sl; this.u.uHov.value = sl ? sl.idx : -1; this.canvas.style.cursor = sl ? 'pointer' : 'grab';
    this.tipFor(sl || this.sel);
  }
  tipFor(sl) {
    if (!sl) { this.showTip(null); return; }
    const it = sl.it, t = it.t, k = this.kinds[it.ki] || OTHER, mae = num(t.mae);
    this.showTip(sl.key, `<b>${esc(t.day ?? '')}</b> <b style="color:#ff7ad9">${fmtR(it.r)}</b><u style="color:${k.css}">${esc(it.kind)}</u><br>`
      + `<i>best</i> <b style="color:#5eead4">${fmtR(it.mfe)}</b>${Number.isFinite(mae) ? ` · <i>worst</i> <b>${fmtR(-Math.abs(mae))}</b>` : ''} · <i>stop</i> <b>${Number.isFinite(it.stop) ? ptsTxt(it.stop) : '—'}</b>`);
  }
  devTapPoint() { const sl = this.slots.find((s) => !s.dead && s.a > 0.5); if (!sl) return null; const p = this.screen(sl.p); return [p.x, p.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const moved = this.camStep(dt); u.uFocus.value = this.L;
    if (this.animating) this.animate();
    if (this.introAt >= 0) { const k = (lt - this.introAt) / 2.2; this.cU.uIn.value = clamp(0.3 + k, 0, 1); if (k >= 1) { this.introAt = -1; this.camKey = ''; } }
    const s = this.sel;
    if (s && !s.dead) {
      const pulse = Q.reduced ? 1 : 1 + 0.07 * Math.sin(lt * 5);
      this.reticle.visible = true; this.reticle.position.copy(s.p); this.reticle.scale.setScalar(Math.max(0.36, s.size * 1.7) * pulse);
      this.reticle.material.rotation = Q.reduced ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95; this.reticle.material.color.copy(s.col).lerp(_c.set('#ffffff'), 0.5);
    } else this.reticle.visible = false;
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.nearest(hx, hy, 16)); }
    if (moved || this.animating) this.placeLabels();
    const ts = this.hov || this.sel;
    if (ts && this.tipKey != null) { const p = this.screen(ts.p); this.placeTip(p.x, p.y, 14); }
  }
}
