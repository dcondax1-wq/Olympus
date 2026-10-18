// Equity Ribbon (run detail): the equity of a run vs the baseline as glowing neon ribbons along a 3D time axis.
//   x = time, y = cumulative $ (daily P&L accumulated, one $ scale for every series), z = series, depth-staggered (the
//   first series in front). Each ribbon is a constant-pixel-width neon tube with energy flowing along it; the area under
//   it glows in its colour (magenta below $0); drawdowns are magenta valleys shaded under the running peak (dashed
//   high-water line), the deepest one marked and labelled. Year ticks (month ticks for spans under ~13 months) at the
//   front, $ ticks on the back wall, the final $ at the end of every ribbon, a legend with each series' final $ and max DD.
//   Drag to orbit. Mouse hover (or a tap) scans a date: a gate of light across the ribbons + a readout of every series;
//   a tap also calls opts.onPick({ date, values: [{ label, equity, dd }] }).
//   First data: the ribbons draw themselves from left to right (staggered); new data re-draws them quickly.
// setData({ series: [{ label, color, days: [[date, pnl], ...] }] })   date 'YYYY-MM-DD' (or epoch s / ms), up to 6 series
// Draw calls ~13; particles: 36 flow sparks per series (16 lite) + 900 dust (300 lite).
import { THREE, Q, POINT_FRAG, count, rng, Hud, addBackdrop, addNebula, addDust, Guides, additive, attrs, paintBackdrop, cssColor, hex,
  clamp, smooth, fract, num, esc, fmtK, fmtUsd, corners, div, injectStyle } from './hud.js';

const PAL = ['#22d3ee', '#ffd98a', '#ff4fd8', '#2ee59d', '#8b5cf6', '#ff9b5c'];
const MAXS = 6, MAXP = 2400;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const parseT = (d) => {
  if (typeof d === 'number') return d > 1e11 ? d / 1000 : d;
  const t = Date.parse(String(d ?? '').slice(0, 10) + 'T00:00:00Z'); return Number.isFinite(t) ? t / 1000 : NaN;
};
const dayStr = (t) => new Date(t * 1000).toISOString().slice(0, 10);
const _v = new THREE.Vector3(), _r = new THREE.Ray(), _pl = new THREE.Plane(), _ndc = new THREE.Vector2(), _c = new THREE.Color();

// ------------------------------------------------------------------ shaders
// neon tube: a strip expanded in screen space (constant pixel width, thinner in the distance); kind 1 = dashed high-water line
const LINE_V = `attribute vec3 aPrev; attribute vec3 aNext; attribute float aSide; attribute float aX; attribute float aSer; attribute vec3 aCol; attribute float aKind; attribute float aA;
uniform float uRev[${MAXS}]; uniform vec2 uRes; uniform float uPix; uniform float uDpr;
varying vec3 vColor; varying float vSide; varying float vX; varying float vRev; varying float vKind; varying float vA;
void main(){
  mat4 pm = projectionMatrix * modelViewMatrix;
  vec4 c = pm * vec4(position, 1.0), p = pm * vec4(aPrev, 1.0), n = pm * vec4(aNext, 1.0);
  vec2 sp = p.xy / p.w * uRes, sn = n.xy / n.w * uRes;
  vec2 dir = sn - sp; float L = length(dir); dir = L > 1e-5 ? dir / L : vec2(1.0, 0.0);
  vec2 nrm = vec2(-dir.y, dir.x);
  float wpx = aKind > 0.5 ? clamp(0.01 * uPix / c.w, 0.6 * uDpr, 1.3 * uDpr) : clamp(0.055 * uPix / c.w, 2.4 * uDpr, 7.5 * uDpr);
  c.xy += nrm * aSide * wpx / uRes * c.w;
  gl_Position = c;
  vColor = aCol; vSide = aSide; vX = aX; vKind = aKind; vA = aA; vRev = uRev[int(aSer + 0.5)];
}`;
const LINE_F = `uniform float uTime; uniform float uMotion;
varying vec3 vColor; varying float vSide; varying float vX; varying float vRev; varying float vKind; varying float vA;
void main(){
  if (vX > vRev) discard;
  float s = abs(vSide);
  if (vKind > 0.5) { float dash = step(0.45, fract(vX * 160.0)); gl_FragColor = vec4(vColor * (1.0 - s * s) * 0.55 * dash * vA, 1.0); return; }
  float core = exp(-s * s * 10.0), glow = (1.0 - s) * (1.0 - s) * 0.32;
  float head = exp(-pow((vX - vRev) * 70.0, 2.0)) * step(vRev, 0.999);
  float flow = exp(-pow((fract(vX * 2.5 - uTime * 0.09 * uMotion) - 0.5) * 7.0, 2.0)) * 0.45 * uMotion;
  vec3 c = mix(vColor, vec3(1.0), core * 0.5) * (core * (1.0 + flow + head * 2.5) + glow * (1.0 + head));
  gl_FragColor = vec4(c, 1.0);
}`;
// kind 0: glow under the curve down to $0; kind 1: drawdown valley between the curve and the running peak
const FILL_V = `attribute float aTop; attribute float aX; attribute float aSer; attribute vec3 aCol; attribute float aKind; attribute float aDD;
uniform float uRev[${MAXS}];
varying float vY; varying float vTop; varying float vX; varying float vRev; varying vec3 vColor; varying float vKind; varying float vDD; varying float vXw;
void main(){ vY = position.y; vTop = aTop; vX = aX; vKind = aKind; vDD = aDD; vColor = aCol; vRev = uRev[int(aSer + 0.5)]; vXw = position.x;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const FILL_F = `uniform vec3 uBad; uniform float uTime; uniform float uMotion;
varying float vY; varying float vTop; varying float vX; varying float vRev; varying vec3 vColor; varying float vKind; varying float vDD; varying float vXw;
void main(){
  if (vX > vRev) discard;
  if (vKind < 0.5) {
    float top = abs(vTop) < 1e-4 ? 1e-4 : vTop;
    float k = clamp(vY / top, 0.0, 1.0);
    vec3 col = vTop >= 0.0 ? vColor : mix(vColor, uBad, 0.75);
    gl_FragColor = vec4(col * (k * k * 0.15 + 0.012), 1.0);
  } else {
    float hatch = 0.55 + 0.45 * step(0.55, fract((vXw + vY) * 7.0));
    gl_FragColor = vec4(uBad * (0.04 + 0.2 * vDD) * hatch, 1.0);
  }
}`;
const DOT_V = `attribute vec3 aCol; attribute float aSize; attribute float aA; uniform float uPix;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(aSize * uPix / -mv.z, 0.0, 90.0); gl_Position = projectionMatrix * mv; vColor = aCol; vAlpha = aA; }`;
const PLANE_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
// the $0 plane: soft fill, glowing rim, a slow scan
const PLANE_F = `uniform vec2 uX; uniform vec2 uZ; uniform vec3 uC1; uniform vec3 uC2; uniform float uTime; uniform float uMotion; varying vec3 vW;
void main(){
  vec2 p = vW.xz, lo = vec2(uX.x, uZ.x), hi = vec2(uX.y, uZ.y), e = min(p - lo, hi - p); float edge = min(e.x, e.y);
  if (edge < 0.0) discard;
  vec2 c = (p - (lo + hi) * 0.5) / ((hi - lo) * 0.5); float sx = (p.x - lo.x) / (hi.x - lo.x);
  float scan = exp(-pow((sx - fract(uTime * 0.04 * uMotion)) * 14.0, 2.0)) * uMotion;
  vec3 col = mix(uC1, uC2, clamp(sx * 0.8 + scan * 0.4, 0.0, 1.0));
  gl_FragColor = vec4(col * (exp(-dot(c, c) * 1.2) * 0.07 + scan * 0.05 + exp(-edge * 28.0) * 0.5 + exp(-edge * 5.0) * 0.03), 1.0);
}`;
// hover / tap gate: a thin vertical sheet of light across every ribbon at one date
const GATE_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const GATE_F = `uniform vec3 uCol; uniform float uA; varying vec2 vUv;
void main(){ float e = min(vUv.y, 1.0 - vUv.y); gl_FragColor = vec4(uCol * uA * (0.1 + 0.25 * smoothstep(0.0, 0.3, e)) * (0.6 + 0.4 * vUv.x), 1.0); }`;

const CSS = `.fxh-ribbon .fxh-leg{gap:5px 12px}.fxh-ribbon .fxh-leg i{width:12px;height:3px;border-radius:2px}.fxh-ribbon .fxh-leg em{font-style:normal;color:rgba(255,122,217,.85);font-weight:600}
.fxh-ribbon .fxh-l.end{font-size:11px;font-weight:800;letter-spacing:0}`;

// year ticks for long ranges, month ticks otherwise; labels sit in the middle of each period
function timeTicks(t0, t1) {
  const span = t1 - t0, marks = [], labels = [];
  if (!(span > 0)) return { marks, labels };
  const d0 = new Date(t0 * 1000), y0 = d0.getUTCFullYear(), y1 = new Date(t1 * 1000).getUTCFullYear();
  if (span > 400 * 86400) {
    for (let y = y0; y <= y1; y++) {
      const s = Date.UTC(y, 0, 1) / 1000, a = Math.max(t0, s), b = Math.min(t1, Date.UTC(y + 1, 0, 1) / 1000);
      if (s > t0) marks.push(s);
      if ((b - a) / span > 0.05) labels.push({ t: (a + b) / 2, text: String(y) });
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
function dollarTicks(lo, hi) {
  const span = Math.max(1, hi - lo), raw = span / 4, p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw) || 10 * p, out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-6; v += step) out.push(Math.abs(v) < step * 1e-6 ? 0 : v);
  return out;
}

// ------------------------------------------------------------------ the view
export class Ribbon extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'ribbon', fov: 34, empty: 'No equity data yet',
      orbit: { yaw: -0.3, pitch: 0.2, auto: 0.03, min: -0.7, max: 0.7, pitchMin: 0.02, pitchMax: 0.72 } });
    injectStyle('fxh-rib-css', CSS);
    this.W = 7; this.H = 3.2; this.ser = []; this.t0 = 0; this.t1 = 1; this.k = 1; this.lo = 0; this.hi = 1; this.box = null;
    this.revAt = []; this.revDur = 2; this.revving = false; this.scan = null; this.pinned = false; this.introDone = false;
    this.SP = count(36, 16);
    Object.assign(this.u, { uRev: { value: new Array(MAXS).fill(1) }, uRes: { value: new THREE.Vector2(1, 1) }, uDpr: { value: 1 }, uBad: { value: new THREE.Color('#ff2bd6') } });
    this.build();
    this.legend = div('fxh-leg'); this.ui.prepend(this.legend);
    this.readout = null;
  }
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.52]);
    addNebula(S, [['#6d28d9', -6, 4, -10, 16, 9, 0.1], ['#22d3ee', 6, 3, -10, 12, 7, 0.04], ['#ff2bd6', 1, -2.5, -8, 16, 6, 0.04]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 650 : 900, 300), box: [7.5, 2.5, 3], cy: 1.4, seed: 31 });
    this.pU = { uX: { value: new THREE.Vector2() }, uZ: { value: new THREE.Vector2() }, uC1: { value: new THREE.Color('#5b3bd1') }, uC2: { value: new THREE.Color('#22d3ee') }, uTime: u.uTime, uMotion: u.uMotion };
    this.plane = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(PLANE_V, PLANE_F, this.pU, { side: THREE.DoubleSide })); this.plane.rotation.x = -Math.PI / 2; this.plane.renderOrder = 2; S.add(this.plane);
    this.guides = new Guides(S, 3);
    this.fills = new THREE.Mesh(new THREE.BufferGeometry(), additive(FILL_V, FILL_F, u, { side: THREE.DoubleSide })); this.fills.renderOrder = 4; S.add(this.fills);
    this.lines = new THREE.Mesh(new THREE.BufferGeometry(), additive(LINE_V, LINE_F, u, { side: THREE.DoubleSide })); this.lines.renderOrder = 6; S.add(this.lines);
    // flow sparks + markers (per series: head while drawing, end beacon, deepest drawdown, scan dot)
    const fg = attrs(MAXS * this.SP, { position: [3, 1], aCol: [3], aSize: [1], aA: [1, 1] }); fg.setDrawRange(0, 0);
    this.flow = new THREE.Points(fg, additive(DOT_V, POINT_FRAG, u)); this.flow.renderOrder = 7; S.add(this.flow);
    const mg = attrs(MAXS * 4, { position: [3, 1], aCol: [3, 1], aSize: [1, 1], aA: [1, 1] }); mg.setDrawRange(0, 0);
    this.marks = new THREE.Points(mg, additive(DOT_V, POINT_FRAG, u)); this.marks.renderOrder = 8; S.add(this.marks);
    this.gU = { uCol: { value: new THREE.Color('#d9d4ff') }, uA: { value: 0 } };
    this.gate = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(GATE_V, GATE_F, this.gU, { side: THREE.DoubleSide })); this.gate.rotation.y = Math.PI / 2; this.gate.renderOrder = 5; this.gate.visible = false; S.add(this.gate);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  retheme() { paintBackdrop(this.bgU); }
  shape(w, h) {
    const asp = w / h, W = 5.6 * Math.pow(clamp(asp / 1.1, 1, 2.8), 0.9), H = 3.3 * clamp(1.6 / asp, 0.85, 1.4);
    const changed = Math.abs(W - this.W) > 0.15 || Math.abs(H - this.H) > 0.08;
    this.W = W; this.H = H; return changed;
  }
  relayout(w, h) {
    const dpr = this.renderer.getPixelRatio(); this.u.uRes.value.set(w * dpr / 2, h * dpr / 2); this.u.uDpr.value = dpr;
    this.region = this.regionFor(w, h);
    if (this.shape(w, h) || !this.framed) { this.framed = true; if (this.ser.length) this.rebuild(false); }
  }
  regionFor(w, h) { const lh = this.legend?.isConnected ? this.legend.offsetHeight : 14; return [-1, 1 - 2 * 62 / w, -1 + 2 * 22 / h, 1 - 2 * (lh + 12) / h]; }
  attach(el) { super.attach(el); this.region = this.regionFor(this.w, this.h); }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const list = (d && Array.isArray(d.series) ? d.series : Array.isArray(d) ? d : []).filter((s) => s && typeof s === 'object').slice(0, MAXS);
    let sig = list.length + ':';
    const ser = [];
    list.forEach((s, i) => {
      const raw = Array.isArray(s.days) ? s.days : [], pts = [];
      let chk = 0;
      for (const r of raw) {
        const dt = Array.isArray(r) ? r[0] : r?.date ?? r?.day, p = num(Array.isArray(r) ? r[1] : r?.pnl, 0), t = parseT(dt);
        if (!Number.isFinite(t)) continue;
        pts.push([t, p]); chk += p * (pts.length % 97 + 1);
      }
      pts.sort((a, b) => a[0] - b[0]);
      const label = String(s.label ?? `Series ${i + 1}`), color = s.color ?? PAL[i % PAL.length];
      sig += label + '/' + color + '/' + pts.length + '/' + (pts[0]?.[0] ?? '') + '/' + (pts.at(-1)?.[0] ?? '') + '/' + chk.toFixed(2) + ',';
      if (!pts.length) return;
      // accumulate; running peak and drawdown
      let cum = 0, peak = 0, mdd = 0, mddAt = 0;
      const t = new Float64Array(pts.length), c = new Float32Array(pts.length), pk = new Float32Array(pts.length);
      pts.forEach(([tt, p], j) => { cum += p; peak = Math.max(peak, cum); t[j] = tt; c[j] = cum; pk[j] = peak; if (peak - cum > mdd) { mdd = peak - cum; mddAt = j; } });
      ser.push({ label, col: cssColor(color, PAL[i % PAL.length]), css: '', t, c, pk, mdd, mddAt, final: cum, idx: ser.length });
    });
    if (sig === this.sig) return;
    this.sig = sig;
    for (const s of ser) s.css = hex(s.col);
    this.ser = ser;
    const first = !this.introDone && ser.length;
    this.rebuild(true, first);
    if (first) this.introDone = true;
    this.empty.style.display = ser.length ? 'none' : 'block';
    this.ui.classList.add('on');
    this.setScan(this.scan ? this.scan.t : null);
  }
  // geometry for the current card shape (and a fresh draw-in when the data changed)
  rebuild(redraw, intro) {
    const S = this.ser, n = S.length, W = this.W, H = this.H;
    let t0 = Infinity, t1 = -Infinity, lo = 0, hi = 0;
    for (const s of S) { t0 = Math.min(t0, s.t[0]); t1 = Math.max(t1, s.t[s.t.length - 1]); for (let j = 0; j < s.c.length; j++) { lo = Math.min(lo, s.c[j]); hi = Math.max(hi, s.pk[j]); } }
    if (!n) { t0 = 0; t1 = 1; }
    if (t1 <= t0) { t0 -= 86400 * 3; t1 += 86400 * 3; }
    if (hi - lo < 1) hi = lo + 1000;
    hi += (hi - lo) * 0.06;
    this.t0 = t0; this.t1 = t1; this.lo = lo; this.hi = hi; this.k = H / (hi - lo);
    const DZ = n > 1 ? Math.min(1.0, 2.6 / (n - 1)) : 0;
    S.forEach((s, i) => { s.z = ((n - 1) / 2 - i) * DZ; });
    const zf = (n - 1) / 2 * DZ + 0.45, zb = -(n - 1) / 2 * DZ - 0.55, yb = this.Y(lo) - 0.12, yt = this.Y(hi) + 0.05, x0 = -W / 2 - 0.25, x1 = W / 2 + 0.25;
    this.box = { zf, zb, yb, yt, x0, x1 };
    // ---- lines (tube + high-water) and fills (area + valleys), all series in one geometry each
    let nl = 0, nf = 0;
    for (const s of S) { const m = Math.min(s.t.length, MAXP); s.m = m; nl += m * 4; nf += m * 4; }
    const LG = attrs(nl, { position: [3], aPrev: [3], aNext: [3], aSide: [1], aX: [1], aSer: [1], aCol: [3], aKind: [1], aA: [1] }), LA = LG.attributes, li = [];
    const FG = attrs(nf, { position: [3], aTop: [1], aX: [1], aSer: [1], aCol: [3], aKind: [1], aDD: [1] }), FA = FG.attributes, fi = [];
    let lv = 0, fv = 0;
    for (const s of S) {
      const m = s.m, step = s.t.length / m, P = [], K = [];
      s.px = new Float32Array(m); s.py = new Float32Array(m); s.pt = new Float64Array(m); s.pc = new Float32Array(m); s.pp = new Float32Array(m);
      for (let j = 0; j < m; j++) {
        // more points than MAXP: keep the worst equity of each bucket so drawdowns stay honest
        let a = Math.floor(j * step), b = Math.max(a + 1, Math.floor((j + 1) * step)), w = a;
        if (step > 1) for (let q = a; q < b && q < s.t.length; q++) if (s.c[q] < s.c[w]) w = q;
        if (j === m - 1) w = s.t.length - 1;
        s.pt[j] = s.t[w]; s.pc[j] = s.c[w]; s.pp[j] = s.pk[w];
        s.px[j] = this.X(s.t[w]); s.py[j] = this.Y(s.c[w]);
        P.push(s.px[j], s.py[j], s.z); K.push(s.px[j], this.Y(s.pk[w]), s.z - 0.003);
      }
      const mdd = Math.max(1, s.mdd);
      for (const [kind, arr] of [[0, P], [1, K]]) {
        const base = lv;
        for (let j = 0; j < m; j++) {
          const jp = Math.max(0, j - 1), jn = Math.min(m - 1, j + 1), ax = (s.pt[j] - t0) / (t1 - t0);
          const on = kind ? ((s.pp[j] - s.pc[j]) > mdd * 0.02 || (s.pp[jn] - s.pc[jn]) > mdd * 0.02 ? 1 : 0) : 1;
          for (const side of [-1, 1]) {
            LA.position.setXYZ(lv, arr[j * 3], arr[j * 3 + 1], arr[j * 3 + 2]); LA.aPrev.setXYZ(lv, arr[jp * 3], arr[jp * 3 + 1], arr[jp * 3 + 2]);
            LA.aNext.setXYZ(lv, arr[jn * 3], arr[jn * 3 + 1], arr[jn * 3 + 2]); LA.aSide.setX(lv, side); LA.aX.setX(lv, ax); LA.aSer.setX(lv, s.idx);
            const k = kind ? 0.9 : 1.15; LA.aCol.setXYZ(lv, s.col.r * k, s.col.g * k, s.col.b * k); LA.aKind.setX(lv, kind); LA.aA.setX(lv, on); lv++;
          }
          if (j < m - 1) { const b2 = base + j * 2; li.push(b2, b2 + 1, b2 + 2, b2 + 1, b2 + 3, b2 + 2); }
        }
        const fb = fv;
        for (let j = 0; j < m; j++) {
          const ax = (s.pt[j] - t0) / (t1 - t0), y = s.py[j], yp = this.Y(s.pp[j]);
          const verts = kind ? [[y, yp], [yp, yp]] : [[y, y], [0, y]];   // [vertex y, aTop]
          for (const [vy, top] of verts) {
            FA.position.setXYZ(fv, s.px[j], vy, s.z + (kind ? 0.002 : 0)); FA.aTop.setX(fv, top); FA.aX.setX(fv, ax); FA.aSer.setX(fv, s.idx);
            FA.aCol.setXYZ(fv, s.col.r, s.col.g, s.col.b); FA.aKind.setX(fv, kind); FA.aDD.setX(fv, clamp((s.pp[j] - s.pc[j]) / mdd, 0, 1)); fv++;
          }
          if (j < m - 1) { const b2 = fb + j * 2; fi.push(b2, b2 + 1, b2 + 2, b2 + 1, b2 + 3, b2 + 2); }
        }
      }
    }
    LG.setIndex(li); FG.setIndex(fi);
    this.lines.geometry.dispose(); this.lines.geometry = LG; this.fills.geometry.dispose(); this.fills.geometry = FG;
    this.lines.visible = this.fills.visible = this.guides.obj.visible = this.plane.visible = n > 0;
    // ---- flow sparks
    const R = rng(5); this.sparks = [];
    for (const s of S) for (let k = 0; k < this.SP; k++) this.sparks.push({ s, ph: R(), sp: 0.035 + R() * 0.05, sz: 0.035 + R() * 0.035 });
    this.flow.geometry.setDrawRange(0, this.sparks.length);
    const FA2 = this.flow.geometry.attributes;
    this.sparks.forEach((p, i) => { _c.copy(p.s.col).lerp(new THREE.Color(1, 1, 1), 0.35).multiplyScalar(1.3); FA2.aCol.setXYZ(i, _c.r, _c.g, _c.b); FA2.aSize.setX(i, p.sz); });
    FA2.aCol.needsUpdate = FA2.aSize.needsUpdate = true;
    this.marks.geometry.setDrawRange(0, n * 4);
    // ---- draw-in
    const now = this.lt;
    if (redraw && !Q.reduced) { this.revAt = S.map((s, i) => now + (intro ? 0.35 : 0.05) + i * (intro ? 0.3 : 0.12)); this.revDur = intro ? 2.1 : 1.1; this.revving = true; }
    else if (!this.revving) { this.revAt = S.map(() => -99); this.revDur = 1; }
    this.frameScene();
  }
  X(t) { return (t - this.t0) / (this.t1 - this.t0) * this.W - this.W / 2; }
  Y(v) { return v * this.k; }
  frameScene() {
    const b = this.box, S = this.ser; if (!b) return;
    const { zf, zb, yb, yt, x0, x1 } = b;
    this.plane.position.set(0, 0, (zf + zb) / 2); this.plane.scale.set(x1 - x0, zf - zb, 1);
    this.pU.uX.value.set(x0, x1); this.pU.uZ.value.set(zb, zf);
    const G = this.guides, vio = new THREE.Color('#8f86ff'), { marks, labels } = timeTicks(this.t0, this.t1), dt = dollarTicks(this.lo, this.hi);
    for (const t of marks) { const x = this.X(t), y0 = Math.min(0, yb); G.seg(x, yb, zb, x, yt, zb, vio, 0.08, 4).seg(x, y0, zf - 0.12, x, y0, zf + 0.1, vio, 0.6); }
    for (const v of dt) { const y = this.Y(v); if (v) G.seg(x0, y, zb, x1, y, zb, vio, 0.09, 4); G.seg(x0 - 0.08, y, zb, x0 + 0.06, y, zb, vio, 0.55); }
    G.seg(x0, yb, zb, x0, yt, zb, vio, 0.3).seg(x0, 0, zb, x1, 0, zb, vio, 0.22);
    for (const s of S) G.seg(x0, 0, s.z, x1, 0, s.z, s.col, 0.12, 3);
    G.commit();
    this.anchors = new Float32Array(corners([], x0 - 0.3, x1 + 0.1, Math.min(yb, -0.1) - 0.15, yt + 0.15, zb, zf + 0.35));
    this.T.set(0, (yb + yt) / 2, (zb + zf) / 2);
    this.gate.position.set(0, (yb + yt) / 2, (zb + zf) / 2); this.gate.scale.set(zf - zb + 0.1, yt - yb, 1);
    // labels: time ticks, $ ticks, end values, deepest drawdowns
    const defs = [];
    if (!S.length) { this.setLabels([]); this.legend.innerHTML = ''; return; }
    for (const l of labels) defs.push({ text: l.text, p: new THREE.Vector3(this.X(l.t), Math.min(0, yb), zf + 0.12), ay: 0, dy: 3, tick: 'x' });
    for (const v of dt) defs.push({ text: v ? fmtK(v) : '$0', p: new THREE.Vector3(x0 - 0.12, this.Y(v), zb), ax: 1, avoid: true });
    for (const s of S) {
      const j = s.m - 1, p = new THREE.Vector3(s.px[j], s.py[j], s.z);
      defs.push({ html: fmtK(s.final), p, ax: 0, dx: 9, cls: 't end', color: s.css, end: true, show: () => this.revDone(s) });
    }
    for (const s of S.slice(0, 1)) {   // the subject's deepest drawdown in 3D (every series has its DD in the legend)
      if (s.mdd < 1) continue;
      const j = this.mIdx(s, s.mddAt);
      defs.push({ text: 'max DD ' + fmtK(-s.mdd), p: new THREE.Vector3(s.px[j], s.py[j], s.z), ay: 0, dy: 9, cls: 'h', color: 'rgba(255,138,224,.78)', avoid: true, show: () => this.revDone(s) });
    }
    this.setLabels(defs);
    this.legend.innerHTML = S.map((s) => `<span><i style="background:${s.css};box-shadow:0 0 6px ${s.css}"></i>${esc(s.label)} <b style="color:${s.css}">${fmtK(s.final)}</b>${s.mdd >= 1 ? ` <em>DD ${fmtK(-s.mdd)}</em>` : ''}</span>`).join('')
      + (S.length ? '<span><i style="background:repeating-linear-gradient(90deg,#ff2bd6 0 3px,transparent 3px 5px);height:6px;border-radius:1px;opacity:.75"></i>drawdown</span>' : '');
    this.region = this.regionFor(this.w, this.h);
  }
  mIdx(s, raw) { if (s.m === s.t.length) return raw; let j = 0; while (j < s.m - 1 && s.pt[j] < s.t[raw]) j++; return j; }
  revK(s) { const a = this.revAt[s.idx] ?? -99; return clamp((this.lt - a) / this.revDur, 0, 1); }
  revDone(s) { return this.revK(s) >= 1; }
  // stack the end values so two ribbons that finish close together stay readable
  adjustLabels(ls) {
    const ends = ls.filter((l) => l.end && !l.hidden).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) { const a = ends[i - 1], b = ends[i], need = a.y + (a.hgt || 12) + 2; if (b.y < need && Math.abs(a.x - b.x) < 70) b.y = need; }
  }

  // ---------------------------------------------------------------- scan (hover / tap)
  dateAt(px, py) {
    const b = this.box; if (!b || !this.ser.length) return null;
    _ndc.set(px / this.w * 2 - 1, -(py / this.h) * 2 + 1);
    _r.origin.setFromMatrixPosition(this.camera.matrixWorld);
    _r.direction.set(_ndc.x, _ndc.y, 0.5).unproject(this.camera).sub(_r.origin).normalize();
    _pl.set(new THREE.Vector3(0, 0, 1), -this.ser[0].z);
    if (!_r.intersectPlane(_pl, _v)) return null;
    if (_v.x < b.x0 - 0.2 || _v.x > b.x1 + 0.2 || _v.y < b.yb - 0.6 || _v.y > b.yt + 0.6) return null;
    return this.t0 + clamp((_v.x + this.W / 2) / this.W, 0, 1) * (this.t1 - this.t0);
  }
  valuesAt(t) {
    return this.ser.map((s) => {
      let lo = 0, hi = s.t.length - 1;
      if (t < s.t[0]) return { s, j: -1, label: s.label, equity: 0, dd: 0 };
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (s.t[mid] <= t) lo = mid; else hi = mid - 1; }
      return { s, j: lo, label: s.label, equity: Math.round(s.c[lo] * 100) / 100, dd: Math.round((s.c[lo] - s.pk[lo]) * 100) / 100, date: dayStr(s.t[lo]) };
    });
  }
  setScan(t) {
    if (t == null || !this.ser.length) { this.scan = null; this.gate.visible = false; this.showTip(null); return; }
    const vals = this.valuesAt(t), date = dayStr(t);
    this.scan = { t, vals };
    const html = `<b>${date}</b>` + vals.map((v) => `<br><b style="color:${v.s.css}">●</b> ${esc(v.label)} <b>${fmtUsd(v.equity)}</b>${v.dd < -0.5 ? ` <i>DD ${fmtUsd(v.dd)}</i>` : ''}`).join('');
    this.showTip('scan' + date, html);
  }
  pickAt(px, py) {
    const t = this.dateAt(px, py);
    if (t == null) { this.pinned = false; this.setScan(null); return; }
    this.pinned = true; this.setScan(t);
    this.emit({ date: dayStr(t), values: this.scan.vals.map(({ label, equity, dd }) => ({ label, equity, dd })) });
  }
  hoverAt(p) { if (!p && !this.pinned) this.setScan(null); }
  devTapPoint() { const s = this.ser[0]; if (!s) return null; const j = Math.floor(s.m * 0.6); const p = this.screen(new THREE.Vector3(s.px[j], s.py[j], s.z)); return [p.x, p.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const moved = this.camStep(dt);
    const S = this.ser, n = S.length;
    // draw-in progress per series
    let busy = false;
    for (const s of S) { const k = this.revK(s), e = k >= 1 ? 1.001 : smooth(k); u.uRev.value[s.idx] = e; if (k < 1) busy = true; }
    if (this.revving && !busy) { this.revving = false; this.camKey = ''; }
    // flow sparks along each ribbon (inside the drawn part)
    if (n) {
      const F = this.flow.geometry.attributes, P = F.position.array, A = F.aA.array, mot = Q.reduced ? 0 : 1;
      this.sparks.forEach((p, i) => {
        const s = p.s, rv = Math.min(1, u.uRev.value[s.idx]);
        const ph = fract(p.ph + lt * p.sp * mot), x = ph * rv, f = x * (s.m - 1), j = Math.min(s.m - 2, Math.floor(f)), r = f - j;
        if (s.m < 2) { P[i * 3] = s.px[0]; P[i * 3 + 1] = s.py[0]; P[i * 3 + 2] = s.z; A[i] = 0; return; }
        P[i * 3] = s.px[j] + (s.px[j + 1] - s.px[j]) * r; P[i * 3 + 1] = s.py[j] + (s.py[j + 1] - s.py[j]) * r; P[i * 3 + 2] = s.z;
        A[i] = Math.sin(ph * Math.PI) * 0.9 * (rv > 0.02 ? 1 : 0);
      });
      F.position.needsUpdate = F.aA.needsUpdate = true;
      // markers: head (while drawing), end beacon, deepest drawdown, scan dot
      const M = this.marks.geometry.attributes, MP = M.position.array, MC = M.aCol.array, MZ = M.aSize.array, MA = M.aA.array;
      const pulse = Q.reduced ? 0.8 : 0.75 + 0.25 * Math.sin(lt * 3);
      S.forEach((s, i) => {
        const k = this.revK(s), f = smooth(Math.min(1, k)) * (s.m - 1), j = Math.min(s.m - 1, Math.floor(f)), j2 = Math.min(s.m - 1, j + 1), r = f - j, o = i * 4;
        const set = (q, x, y, z, c, sz, a) => { MP[q * 3] = x; MP[q * 3 + 1] = y; MP[q * 3 + 2] = z; MC[q * 3] = c.r; MC[q * 3 + 1] = c.g; MC[q * 3 + 2] = c.b; MZ[q] = sz; MA[q] = a; };
        set(o, s.px[j] + (s.px[j2] - s.px[j]) * r, s.py[j] + (s.py[j2] - s.py[j]) * r, s.z, _c.copy(s.col).lerp(new THREE.Color(1, 1, 1), 0.5), 0.34, k > 0 && k < 1 ? 1 : 0);
        set(o + 1, s.px[s.m - 1], s.py[s.m - 1], s.z, s.col, 0.3 * pulse + 0.06, k >= 1 ? 1 : 0);
        const jd = this.mIdx(s, s.mddAt);
        set(o + 2, s.px[jd], s.py[jd], s.z, u.uBad.value, 0.2, k >= 1 && s.mdd >= 1 ? 0.9 : 0);
        const sv = this.scan?.vals?.[i], sj = sv && sv.j >= 0 ? sv.j : -1;
        if (sj >= 0) set(o + 3, this.X(s.t[sj]), this.Y(s.c[sj]), s.z, _c.copy(s.col).lerp(new THREE.Color(1, 1, 1), 0.6), 0.26, 1); else MA[o + 3] = 0;
      });
      M.position.needsUpdate = M.aCol.needsUpdate = M.aSize.needsUpdate = M.aA.needsUpdate = true;
    }
    // hover scan
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; if (!this.pinned) this.setScan(this.dateAt(hx, hy)); }
    if (this.scan) {
      this.gate.visible = true; this.gate.position.x = this.X(this.scan.t); this.gU.uA.value = 1;
      const s0 = this.scan.vals.find((v) => v.j >= 0);
      if (s0) { const p = this.screen(_v.set(this.X(s0.s.t[s0.j]), this.Y(Math.max(...this.scan.vals.filter((v) => v.j >= 0).map((v) => v.s.c[v.j]))), s0.s.z)); this.placeTip(p.x, p.y, 18); }
    }
    if (moved || busy) this.placeLabels();
  }
}
