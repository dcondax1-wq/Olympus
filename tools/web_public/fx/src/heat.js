// Intraday Heat (Lab -> Intraday): a 3D bar heat map of entry hour x weekday.
//   7 hour columns (09:00-15:00 ET, left to right) x 5 weekday rows (Mon at the back, Fri in front) of glowing glass bars
//   standing on a floor grid. Height = trades (n), colour = average R (magenta at -1R, neutral violet at 0, green at +1R),
//   a thin cap at the top of every bar glows by net $ (gold when positive, red when negative, brighter the bigger). The
//   killzones (09:30-11:30, 13:30-15:30 ET) are lit green strips on the floor with a slow scan; the lunch hour stays dark.
//   An hour without trades is an empty socket in the floor (hover / tap: "no trades"). Trade-count ticks on the back-left
//   edge, hour labels along the front, weekday labels on the left. Legend: colour scale, cap, killzone, totals.
//   Tap a bar -> opts.onPick(cell) (the page's cell object); mouse hover shows the tooltip; drag to orbit.
//   First data: the bars rise out of the floor in a wave (left to right, back to front) while the killzone strips light up;
//   new data: bars morph (height, colour, cap), newcomers rise, leavers sink; the same data twice does nothing.
// setData({ cells: [{ dow: 0-4 (Mon-Fri), hour: 9-15 (ET entry hour), n, avg_r, net }], label: '2026' })
//   A missing cell, a cell with n <= 0 or a dow / hour outside the grid = an empty socket. A duplicate (dow, hour) keeps the
//   last one. avg_r missing -> neutral lavender; net missing or 0 -> a faint white cap. A bare array of cells works too.
// Draw calls ~11 (backdrop, 2 nebula, dust, floor, guides, pools, bars = one InstancedMesh, caps, reticle) whatever the data.
//   Particles: at most 35 bar instances + 35 floor pools + 35 cap glows, 800 dust (650 phone, 280 lite).
import { THREE, Q, theme, Hud, addBackdrop, addNebula, addDust, Guides, ringTexture, sprite, additive, attrs, count,
  paintBackdrop, clamp, smooth, outBack, num, esc, hash, fmtR, fmtUsd, corners, div, injectStyle } from './hud.js';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], H0 = 9, NH = 7, ND = 5, N = NH * ND;
const KZ = [[9.5, 11.5], [13.5, 15.5]];                  // killzones in ET hours
const RISE = 1, MOVE = 2, SINK = 4;
const C = { good: new THREE.Color('#2ee59d'), mid: new THREE.Color('#8b5cf6'), bad: new THREE.Color('#ff2bd6'),
  gold: new THREE.Color('#ffd98a'), red: new THREE.Color('#ff5a7a'), none: new THREE.Color('#c4b5fd') };
const CSS = { good: '#4ef0b0', bad: '#ff7ad9', gold: '#ffe7a8', red: '#ff8a9e', kz: '#5eead4', none: '#c4b5fd' };
const _v = new THREE.Vector3(), _v2 = new THREE.Vector2(), _m = new THREE.Matrix4(), _c = new THREE.Color(), _k = new THREE.Color();
const hhmm = (h) => String(h).padStart(2, '0') + ':00';
const kzOf = (h) => (h < 12 ? 'AM' : h >= 13 ? 'PM' : null);   // which killzone an hour column (9-15) belongs to; 12 = lunch
// average R -> colour: magenta (-1R) .. neutral violet (0) .. green (+1R), saturating beyond
function rColor(out, r) {
  if (!Number.isFinite(r)) return out.copy(C.none).multiplyScalar(0.6);
  const t = clamp(r, -1, 1);
  return t >= 0 ? out.copy(C.mid).lerp(C.good, t) : out.copy(C.mid).lerp(C.bad, -t);
}
// net $ -> cap colour (gold +, red -) and brightness 0..1
function capOf(out, net, netMax) {
  if (!Number.isFinite(net) || net === 0) { out.copy(C.none); return 0.18; }
  out.copy(net > 0 ? C.gold : C.red);
  return 0.3 + 0.7 * Math.sqrt(clamp(Math.abs(net) / netMax, 0, 1));
}

// ------------------------------------------------------------------ shaders
// bars: one InstancedMesh of unit boxes (base at y = 0); per instance colour, cap colour, (id, alpha, cap brightness)
const BAR_V = `attribute vec3 aCol; attribute vec3 aCap; attribute vec3 aMisc;
uniform float uSel; uniform float uHov;
varying vec3 vColor; varying vec3 vCap; varying vec2 vUv; varying float vY; varying float vTop; varying float vSide; varying float vHi; varying float vA; varying float vK; varying float vH;
void main(){
  vUv = uv; vY = position.y; vTop = step(0.5, normal.y); vSide = abs(normal.x);
  vH = instanceMatrix[1][1];
  vec4 w = instanceMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * modelViewMatrix * w;
  vColor = aCol; vCap = aCap; vA = aMisc.y; vK = aMisc.z;
  vHi = max(1.0 - step(0.5, abs(aMisc.x - uSel)), (1.0 - step(0.5, abs(aMisc.x - uHov))) * 0.7);
}`;
// glass fill brighter toward the top, a neon frame of constant pixel width on every face, a slow rising scan, the cap band
const BAR_F = `uniform float uTime; uniform float uMotion;
varying vec3 vColor; varying vec3 vCap; varying vec2 vUv; varying float vY; varying float vTop; varying float vSide; varying float vHi; varying float vA; varying float vK; varying float vH;
void main(){
  vec2 e = min(vUv, 1.0 - vUv); float edge = min(e.x, e.y);
  float px = edge / max(fwidth(edge), 1e-4);
  float frame = exp(-px * 0.38);
  float yw = vY * vH;
  float cap = max(vTop, smoothstep(vH - 0.07, vH - 0.035, yw));
  float fill = (0.07 + 0.17 * vY * vY) * (1.0 - vSide * 0.3) + vTop * 0.08;
  float t = uTime * uMotion;
  float scan = exp(-pow((vY - fract(t * 0.16 + vH * 0.37)) * 5.0, 2.0)) * 0.07 * uMotion * (1.0 - vTop);
  vec3 body = vColor * (fill + frame * 0.8 + scan + vHi * (0.3 + frame * 0.9));
  vec3 capc = vCap * (0.22 + vK * 0.78) * (0.7 + frame * 0.6 + vHi * 0.6);
  gl_FragColor = vec4(mix(body, capc, cap) * vA, 1.0);
}`;
// floor pools and cap glows: point sprites, squashed into ellipses (a pool lies flat on the floor, a cap is a lens)
const GLOW_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; uniform float uPix;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(aSize * uPix / -mv.z, 0.0, 180.0); gl_Position = projectionMatrix * mv; vColor = aCol; vAlpha = aAlpha; }`;
const POOL_F = `uniform float uSquash; varying vec3 vColor; varying float vAlpha;
void main(){ vec2 q = (gl_PointCoord - 0.5) * vec2(2.0, 2.0 / uSquash); float d = dot(q, q); if (d > 1.0) discard;
  float a = 1.0 - d; a = a * a; gl_FragColor = vec4(vColor * a * vAlpha, 1.0); }`;
const CAP_F = `varying vec3 vColor; varying float vAlpha;
void main(){ vec2 q = (gl_PointCoord - 0.5) * vec2(2.0, 4.2); float d = dot(q, q); if (d > 1.0) discard;
  float a = 1.0 - d; a = a * a; float core = exp(-d * 9.0); gl_FragColor = vec4(vColor * (a * 0.45 + core * 0.9) * vAlpha, 1.0); }`;
const WALL_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
// the floor: a socket plate per cell, fine cell borders, the two killzone strips (green, scanned) with glowing borders, a rim
const FLOOR_F = `uniform vec2 uX; uniform vec2 uZ; uniform vec2 uG0; uniform float uCs; uniform vec4 uKZ; uniform vec3 uBase; uniform vec3 uGood;
uniform float uTime; uniform float uMotion; uniform float uIn; varying vec3 vW;
void main(){
  vec2 p = vW.xz, lo = vec2(uX.x, uZ.x), hi = vec2(uX.y, uZ.y), e = min(p - lo, hi - p); float edge = min(e.x, e.y);
  if (edge < 0.0) discard;
  vec2 g = (p - uG0) / uCs, fw = fwidth(g);
  float inside = step(0.0, g.x) * step(g.x, ${NH}.0) * step(0.0, g.y) * step(g.y, ${ND}.0);
  vec2 f = fract(g) - 0.5;
  vec2 d = abs(f) - vec2(0.31); float sq = length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
  float sock = (1.0 - smoothstep(0.0, fw.x * 1.6, abs(sq))) * 0.6 + (1.0 - step(0.0, sq)) * 0.22;
  vec2 af = abs(f); float line = max(smoothstep(0.5 - fw.x * 1.4, 0.5, af.x), smoothstep(0.5 - fw.y * 1.4, 0.5, af.y));
  float kz = (step(uKZ.x, p.x) * step(p.x, uKZ.y) + step(uKZ.z, p.x) * step(p.x, uKZ.w)) * inside;
  float kd = min(min(abs(p.x - uKZ.x), abs(p.x - uKZ.y)), min(abs(p.x - uKZ.z), abs(p.x - uKZ.w)));
  float kzEdge = exp(-kd * 28.0) * inside;
  float t = uTime * uMotion;
  float scan = exp(-pow((g.y / ${ND}.0 - fract(t * 0.07)) * 6.0, 2.0)) * uMotion;
  vec2 c = (p - (lo + hi) * 0.5) / ((hi - lo) * 0.5);
  vec3 col = uBase * (0.05 + exp(-dot(c, c) * 1.5) * 0.05 + (sock * 0.15 + line * 0.14) * inside);
  col += uGood * (kz * (0.055 + 0.05 * scan) + kzEdge * 0.4) * uIn;
  col += uBase * (exp(-edge * 24.0) * 0.5 + exp(-edge * 5.0) * 0.04);
  gl_FragColor = vec4(col, 1.0);
}`;

const STYLE = `.fxh-heat .fxh-leg i.grad{width:26px;height:6px;border-radius:3px;background:linear-gradient(90deg,#ff2bd6,#8b5cf6,#2ee59d);box-shadow:0 0 6px rgba(139,92,246,.6)}
.fxh-heat .fxh-leg em{font-style:normal;font-weight:500;color:rgba(188,192,236,.5)}
.fxh-heat .fxh-leg .hint{margin-left:auto;font-weight:500;color:rgba(188,192,236,.55)}`;

// ------------------------------------------------------------------ the view
export class HeatCube extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'heat', fov: 36, empty: 'No trades in this period',
      orbit: { yaw: -0.42, pitch: 0.46, auto: 0.03, min: -0.95, max: 0.95, pitchMin: 0.2, pitchMax: 0.95 } });
    injectStyle('fxh-heat-css', STYLE);
    // grid: column i (hour 9 + i) -> x0 + (i + .5) cs, row j (Mon = 0, at the back) -> z0 + (j + .5) cs
    this.cs = 1; this.fp = 0.62; this.hmax = 2.3; this.x0 = -NH / 2; this.z0 = -ND / 2;
    this.slots = []; this.byKey = new Map(); this.animating = false; this.introDone = false; this.introAt = -1;
    this.nMax = 1; this.netMax = 1; this.total = 0; this.label = ''; this.sel = null; this.hov = null;
    Object.assign(this.u, { uSel: { value: -1 }, uHov: { value: -1 }, uSquash: { value: 0.45 }, uIn: { value: 1 } });
    this.ray = new THREE.Raycaster();
    this.build();
    this.legend = div('fxh-leg'); this.ui.prepend(this.legend);
  }
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.55]);
    addNebula(S, [['#6d28d9', -4, 3, -9, 15, 8, 0.1], ['#ff2bd6', 5, 0.5, -9, 11, 7, 0.045]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 650 : 800, 280), box: [6, 2.2, 4], cy: 1.3, seed: 43 });
    this.fU = { uX: { value: new THREE.Vector2() }, uZ: { value: new THREE.Vector2() }, uG0: { value: new THREE.Vector2() }, uCs: { value: 1 }, uKZ: { value: new THREE.Vector4() },
      uBase: { value: new THREE.Color('#5b3bd1') }, uGood: { value: theme.good.clone() }, uTime: u.uTime, uMotion: u.uMotion, uIn: u.uIn };
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(WALL_V, FLOOR_F, this.fU, { side: THREE.DoubleSide, extensions: { derivatives: true } }));
    this.floor.rotation.x = -Math.PI / 2; this.floor.renderOrder = 1; S.add(this.floor);
    this.guides = new Guides(S, 3);
    this.pools = new THREE.Points(attrs(N, { position: [3, 1], aCol: [3, 1], aSize: [1, 1], aAlpha: [1, 1] }), additive(GLOW_V, POOL_F, u)); this.pools.renderOrder = 2; S.add(this.pools);
    this.caps = new THREE.Points(attrs(N, { position: [3, 1], aCol: [3, 1], aSize: [1, 1], aAlpha: [1, 1] }), additive(GLOW_V, CAP_F, u)); this.caps.renderOrder = 6; S.add(this.caps);
    const box = new THREE.BoxGeometry(1, 1, 1); box.translate(0, 0.5, 0);
    for (const k of ['aCol', 'aCap', 'aMisc']) box.setAttribute(k, new THREE.InstancedBufferAttribute(new Float32Array(N * 3), 3).setUsage(THREE.DynamicDrawUsage));
    this.bars = new THREE.InstancedMesh(box, additive(BAR_V, BAR_F, u, { extensions: { derivatives: true } }), N);
    this.bars.instanceMatrix.setUsage(THREE.DynamicDrawUsage); this.bars.count = 0; this.bars.renderOrder = 5; S.add(this.bars);
    const ret = ringTexture(true); this.textures.push(ret);
    this.reticle = sprite(S, ret, '#ffffff', 12);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  retheme() { paintBackdrop(this.bgU); this.fU.uGood.value.copy(theme.good); }
  relayout() { this.regionFix(); if (!this.framed) { this.framed = true; this.frameScene(); } }
  regionFix() { const lh = this.legend?.isConnected ? this.legend.offsetHeight : 14; this.region = [-1, 1, -1 + 2 * 18 / this.h, 1 - 2 * (lh + 14) / this.h]; }
  attach(el) { super.attach(el); this.regionFix(); }
  xOfT(t) { return this.x0 + (t - H0) * this.cs; }                     // a time of day (hours, ET) -> x
  yOf(n) { return n > 0 ? Math.max(0.06, clamp(n / this.nMax, 0, 1) * this.hmax) : 0; }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' && !Array.isArray(d) ? d : { cells: Array.isArray(d) ? d : [] };
    const list = Array.isArray(src.cells) ? src.cells : [], label = src.label == null ? '' : String(src.label);
    const cells = new Map();
    for (const c of list) {
      if (!c || typeof c !== 'object') continue;
      const dow = Math.round(num(c.dow)), hour = Math.floor(num(c.hour)), n = num(c.n, 0);
      if (!(dow >= 0 && dow < ND) || !(hour >= H0 && hour < H0 + NH) || !(n > 0)) continue;
      const key = dow + '|' + hour;
      cells.set(key, { key, dow, hour, n, avg: num(c.avg_r), net: num(c.net), cell: c });
    }
    const items = [...cells.values()].sort((a, b) => a.hour - b.hour || a.dow - b.dow);
    const sig = label + '|' + items.map((it) => `${it.key}/${it.n}/${it.avg}/${it.net}`).join(',');
    if (sig === this.sig) { for (const it of items) { const s = this.byKey.get(it.key); if (s) s.it.cell = it.cell; } return; }
    this.sig = sig; this.label = label;
    this.nMax = Math.max(1, ...items.map((it) => it.n));
    this.netMax = Math.max(1, ...items.map((it) => Math.abs(it.net)).filter(Number.isFinite));
    this.total = items.reduce((s, it) => s + it.n, 0);
    const first = !this.slots.length && !this.introDone, now = this.lt, red = Q.reduced;
    const next = [], keep = new Set();
    for (const it of items) {
      let sl = this.byKey.get(it.key);
      const h1 = this.yOf(it.n); rColor(_c, it.avg); const k1 = capOf(_k, it.net, this.netMax);
      if (sl && !sl.dead) { sl.h0 = sl.h; sl.a0 = sl.a; sl.k0 = sl.k; sl.col0.copy(sl.col); sl.cap0.copy(sl.cap); sl.mode = MOVE; sl.t0 = now + (red ? 0 : sl.seed * 0.15); sl.dur = red ? 0 : 0.85; }
      else {
        const i = it.hour - H0, j = it.dow, seed = hash(it.key);
        sl = { key: it.key, i, j, x: this.x0 + (i + 0.5) * this.cs, z: this.z0 + (j + 0.5) * this.cs, h: 0, h0: 0, h1: 0, a: 0, a0: 0, k: 0, k0: 0, k1: 0, seed,
          col: new THREE.Color(), col0: new THREE.Color(), col1: new THREE.Color(), cap: new THREE.Color(), cap0: new THREE.Color(), cap1: new THREE.Color(), dead: false, done: false, idx: 0 };
        sl.mode = RISE; sl.t0 = now + (first ? 0.25 + (i / (NH - 1)) * 0.55 + (j / (ND - 1)) * 0.3 + seed * 0.12 : 0.05 + seed * 0.3); sl.dur = first ? 0.95 : 0.75;
        if (red) { sl.t0 = now; sl.dur = 0; }
        sl.col0.copy(_c); sl.cap0.copy(_k); sl.k0 = k1;
      }
      sl.it = it; sl.done = false; sl.h1 = h1; sl.k1 = k1; sl.col1.copy(_c); sl.cap1.copy(_k);
      keep.add(it.key); next.push(sl);
    }
    for (const sl of this.slots) {
      if (keep.has(sl.key) || sl.dead) continue;
      sl.dead = true; sl.done = false; sl.mode = SINK; sl.h0 = sl.h; sl.a0 = sl.a; sl.k0 = sl.k; sl.col0.copy(sl.col); sl.cap0.copy(sl.cap); sl.t0 = now; sl.dur = red ? 0 : 0.5;
      next.push(sl);
    }
    this.slots = next; this.byKey.clear();
    for (const sl of next) if (!sl.dead) this.byKey.set(sl.key, sl);
    if (this.sel && (this.sel.dead || (this.sel.empty && this.byKey.has(this.sel.key)))) this.select(null);
    if (this.hov && (this.hov.dead || (this.hov.empty && this.byKey.has(this.hov.key)))) this.hoverAt(null);
    this.animating = true; this.writeAll();
    if (first && items.length) { this.introAt = red ? -1 : now; this.introDone = true; this.u.uIn.value = red ? 1 : 0; }
    this.frameScene();
    this.empty.style.display = items.length ? 'none' : 'block';
    this.ui.classList.add('on');
    this.tipKey = null; this.tipFor(this.hov || this.sel);
  }
  animate() {
    const now = this.lt; let busy = false, dead = false;
    for (const sl of this.slots) {
      if (sl.done) { dead ||= sl.dead; continue; }
      const k = sl.dur > 0 ? clamp((now - sl.t0) / sl.dur, 0, 1) : 1;
      if (sl.mode === RISE) { sl.h = sl.h1 * Math.max(0, outBack(k)); sl.a = smooth(Math.min(1, k * 2.5)); sl.k = sl.k1 * smooth(k); sl.col.copy(sl.col1); sl.cap.copy(sl.cap1); }
      else if (sl.mode === MOVE) { const e = smooth(k); sl.h = sl.h0 + (sl.h1 - sl.h0) * e; sl.a = sl.a0 + (1 - sl.a0) * e; sl.k = sl.k0 + (sl.k1 - sl.k0) * e; sl.col.copy(sl.col0).lerp(sl.col1, e); sl.cap.copy(sl.cap0).lerp(sl.cap1, e); }
      else { const e = smooth(k); sl.h = sl.h0 * (1 - e); sl.a = sl.a0 * (1 - e); sl.k = sl.k0 * (1 - e); sl.col.copy(sl.col0); sl.cap.copy(sl.cap0); }
      if (k >= 1) { sl.done = true; dead ||= sl.dead; } else busy = true;
    }
    if (!busy && dead) this.slots = this.slots.filter((s) => !s.dead);
    this.writeAll();
    if (!busy) this.animating = false;
  }
  // every instance, pool and cap from the slots (35 at most: cheap enough to rewrite whole while anything moves)
  writeAll() {
    const n = this.slots.length, B = this.bars.geometry.attributes, P = this.pools.geometry.attributes, K = this.caps.geometry.attributes, fp = this.fp * this.cs, hm = this.hmax;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], h = Math.max(0.001, sl.h), rel = clamp(h / hm, 0, 1), c = sl.col, p = sl.cap; sl.idx = i;
      _m.makeScale(fp, h, fp); _m.setPosition(sl.x, 0, sl.z); this.bars.setMatrixAt(i, _m);
      B.aCol.setXYZ(i, c.r, c.g, c.b); B.aCap.setXYZ(i, p.r, p.g, p.b); B.aMisc.setXYZ(i, i, sl.a, sl.k);
      P.position.setXYZ(i, sl.x, 0.012, sl.z); P.aCol.setXYZ(i, c.r * 0.55, c.g * 0.55, c.b * 0.55); P.aSize.setX(i, fp * (1.6 + 1.0 * rel)); P.aAlpha.setX(i, sl.a * (0.45 + 0.55 * rel));
      K.position.setXYZ(i, sl.x, h + 0.02, sl.z); K.aCol.setXYZ(i, p.r, p.g, p.b); K.aSize.setX(i, fp * (0.9 + 1.5 * sl.k)); K.aAlpha.setX(i, sl.a * (0.12 + 0.6 * sl.k));
    }
    this.bars.count = n; this.bars.instanceMatrix.needsUpdate = true;
    for (const a of [B.aCol, B.aCap, B.aMisc, P.position, P.aCol, P.aSize, P.aAlpha, K.position, K.aCol, K.aSize, K.aAlpha]) a.needsUpdate = true;
    this.pools.geometry.setDrawRange(0, n); this.caps.geometry.setDrawRange(0, n);
    this.u.uSel.value = this.sel && !this.sel.empty ? this.sel.idx : -1; this.u.uHov.value = this.hov && !this.hov.empty ? this.hov.idx : -1;
  }

  // ---------------------------------------------------------------- floor, guides, labels, legend
  ticks() {
    const m = this.nMax, st = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000].find((s) => m / s <= 4.5) || 1000, out = [];
    for (let v = st; v <= m; v += st) out.push(v);
    if (!out.length || m - out[out.length - 1] > st * 0.4) out.push(m);
    return out;
  }
  frameScene() {
    const cs = this.cs, x0 = this.x0, z0 = this.z0, x1 = x0 + NH * cs, z1 = z0 + ND * cs, hm = this.hmax, M = 0.35, xl = x0 - M, zb = z0 - M, xr = x1 + M, zf = z1 + M;
    this.floor.position.set((x0 + x1) / 2, 0, (z0 + z1) / 2); this.floor.scale.set(xr - xl, zf - zb, 1);
    this.fU.uX.value.set(xl, xr); this.fU.uZ.value.set(zb, zf); this.fU.uG0.value.set(x0, z0); this.fU.uCs.value = cs;
    this.fU.uKZ.value.set(this.xOfT(KZ[0][0]), this.xOfT(KZ[0][1]), this.xOfT(KZ[1][0]), this.xOfT(KZ[1][1]));
    // guides: trade-count ticks across the back wall and down the left side, the height axis at the back-left corner
    const G = this.guides, vio = new THREE.Color('#8f86ff'), ticks = this.slots.length ? this.ticks() : [], top = hm + 0.15;
    for (const n of ticks) { const y = this.yOf(n); G.seg(xl, y, zb, xr, y, zb, vio, 0.09, 4).seg(xl, y, zb, xl, y, zf, vio, 0.06, 4).seg(xl - 0.08, y, zb, xl + 0.08, y, zb, vio, 0.55); }
    G.seg(xl, 0, zb, xl, top, zb, vio, 0.35).seg(xl, 0, zb, xr, 0, zb, vio, 0.2).seg(xl, 0, zb, xl, 0, zf, vio, 0.2);
    G.commit();
    this.anchors = new Float32Array(corners([], xl - 0.9, xr + 0.25, -0.15, top + 0.3, zb - 0.2, zf + 0.5));
    this.T.set((x0 + x1) / 2, hm * 0.38, (z0 + z1) / 2);
    const defs = [];
    for (let i = 0; i <= NH; i++) defs.push({ text: hhmm(H0 + i), p: new THREE.Vector3(x0 + i * cs, 0, zf + 0.05), ay: 0, dy: 3, tick: 'x', color: i < NH && kzOf(H0 + i) ? CSS.kz : null });
    defs.push({ text: 'entry hour (ET) →', p: new THREE.Vector3(xr + 0.12, 0, zf + 0.05), ax: 0, ay: 0, dy: 3, cls: 't', avoid: true });
    for (let j = 0; j < ND; j++) defs.push({ text: DAYS[j], p: new THREE.Vector3(xl - 0.1, 0, z0 + (j + 0.5) * cs), ax: 1, cls: 't', avoid: true });
    for (const n of ticks) defs.push({ text: String(n), p: new THREE.Vector3(xl - 0.12, this.yOf(n), zb), ax: 1, cls: 'h', avoid: true });
    if (ticks.length) defs.push({ text: 'trades ↑', p: new THREE.Vector3(xl, top, zb), ax: 1, dx: 8, ay: 1, dy: -4, cls: 't', avoid: true });
    for (const [a, b] of KZ) defs.push({ text: (a < 12 ? 'AM' : 'PM') + ' killzone', p: new THREE.Vector3(this.xOfT(a) + 0.08, top, zb), ax: 0, ay: 1, dy: -3, cls: 'h', color: CSS.kz, avoid: true,
      show: () => this.u.uIn.value > 0.4 });
    this.setLabels(defs);
    this.legendFor();
  }
  legendFor() {
    const n = this.total, cells = this.byKey.size, small = this.w < 520;
    const L = [`<span><i class="grad"></i>avg R <em>−1R → +1R</em></span>`,
      `<span><i style="background:${CSS.gold};box-shadow:0 0 6px ${CSS.gold}"></i>cap: net $${small ? '' : ' <em>(gold +, red −)</em>'}</span>`,
      `<span><i style="background:${CSS.good};box-shadow:0 0 6px ${CSS.good};border-radius:2px;width:10px"></i>killzone</span>`];
    if (!small) L.push('<span>height = trades</span>');
    if (n) L.push(`<span class="hint">${this.label ? esc(this.label) + ' · ' : ''}${n} trade${n === 1 ? '' : 's'}${small ? '' : ` · ${cells}/${N} hours`} · tap a bar</span>`);
    this.legend.innerHTML = L.join('');
    if (this.w > 10) this.regionFix();
  }

  // ---------------------------------------------------------------- picking + tooltip
  // what is under a card pixel: a live bar (slot), an empty socket ({ empty, key, dow, hour, i, j }) or nothing
  hit(px, py) {
    _v2.set(px / this.w * 2 - 1, -(py / this.h) * 2 + 1);
    this.ray.setFromCamera(_v2, this.camera);
    if (this.bars.count) {
      this.bars.computeBoundingSphere();
      for (const h of this.ray.intersectObject(this.bars, false)) { const sl = this.slots[h.instanceId]; if (sl && !sl.dead && sl.a > 0.3) return sl; }
    }
    const r = this.ray.ray;
    if (Math.abs(r.direction.y) > 1e-6) {
      const t = -r.origin.y / r.direction.y;
      if (t > 0) {
        _v.copy(r.direction).multiplyScalar(t).add(r.origin);
        const i = Math.floor((_v.x - this.x0) / this.cs), j = Math.floor((_v.z - this.z0) / this.cs);
        if (i >= 0 && i < NH && j >= 0 && j < ND) { const key = j + '|' + (H0 + i); return this.byKey.get(key) || { empty: true, key, dow: j, hour: H0 + i, i, j }; }
      }
    }
    return null;
  }
  pickAt(px, py) {
    const t = this.hit(px, py);
    this.select(t);
    if (t && !t.empty) this.emit(t.it.cell);
  }
  select(t) { this.sel = t; this.u.uSel.value = t && !t.empty ? t.idx : -1; this.tipFor(this.hov || t); }
  hoverAt(t) {
    if (t === this.hov || (t && this.hov && t.empty && this.hov.empty && t.key === this.hov.key)) return;
    this.hov = t; this.u.uHov.value = t && !t.empty ? t.idx : -1; this.canvas.style.cursor = t && !t.empty ? 'pointer' : 'grab';
    this.tipFor(t || this.sel);
  }
  tipFor(t) {
    if (!t) { this.showTip(null); return; }
    if (t.empty) { this.showTip('e' + t.key, `<b>${DAYS[t.dow]} ${hhmm(t.hour)}</b> <i>no trades</i>`); return; }
    const it = t.it, kz = kzOf(it.hour), rc = it.avg > 0.05 ? CSS.good : it.avg < -0.05 ? CSS.bad : CSS.none, nc = it.net > 0 ? CSS.gold : it.net < 0 ? CSS.red : '#eef0fb';
    this.showTip(t.key, `<b>${DAYS[it.dow]} ${hhmm(it.hour)}</b><u style="color:${kz ? CSS.kz : '#b9a6ff'}">${kz ? kz + ' killzone' : 'lunch'}</u><br>`
      + `<i>trades</i> <b>${it.n}</b> · <i>avg</i> <b style="color:${rc}">${fmtR(it.avg)}</b> · <i>net</i> <b style="color:${nc}">${fmtUsd(it.net)}</b>`);
  }
  tipAnchor(t) { if (t.empty) _v.set(this.x0 + (t.i + 0.5) * this.cs, 0, this.z0 + (t.j + 0.5) * this.cs); else _v.set(t.x, t.h + 0.05, t.z); return this.screen(_v); }
  devTapPoint() {
    const sl = this.slots.filter((s) => !s.dead && s.a > 0.5).sort((a, b) => b.h - a.h)[0]; if (!sl) return null;
    const p = this.screen(_v.set(sl.x, sl.h * 0.6, sl.z)); return [p.x, p.y];
  }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const moved = this.camStep(dt);
    u.uSquash.value = clamp(Math.sin(this.orbit.pitch), 0.25, 1);
    if (this.animating) this.animate();
    if (this.introAt >= 0) { const k = (lt - this.introAt) / 1.8; u.uIn.value = clamp(k * 1.25 - 0.1, 0, 1); if (k >= 1) { this.introAt = -1; this.camKey = ''; } }
    const s = this.sel;
    if (s && !s.empty && !s.dead) {
      const pulse = Q.reduced ? 1 : 1 + 0.07 * Math.sin(lt * 5);
      this.reticle.visible = true; this.reticle.position.set(s.x, s.h + 0.05, s.z); this.reticle.scale.setScalar(this.fp * this.cs * 1.5 * pulse);
      this.reticle.material.rotation = Q.reduced ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95; this.reticle.material.color.copy(s.col).lerp(_c.set('#ffffff'), 0.5);
    } else this.reticle.visible = false;
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.hit(hx, hy)); }
    if (moved || this.animating || this.introAt >= 0) this.placeLabels();
    const ts = this.hov || this.sel;
    if (ts && this.tipKey != null) { const p = this.tipAnchor(ts); this.placeTip(p.x, p.y, 14); }
  }
}
