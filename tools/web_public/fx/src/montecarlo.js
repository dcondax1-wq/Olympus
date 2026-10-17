// Monte Carlo Evals (Lab -> Evals): hundreds of simulated MFFU eval paths as thin glowing ribbons fanning out from the
//   start balance. x = session (0-60), y = balance, z = a small random spread that opens up over the first sessions (the
//   fan). Passes turn green toward their end and flare where they cross the target plane; fails turn magenta and burst
//   where they hit the trailing floor; open paths stay violet and end in a small dot at session 60. The target (green)
//   and the initial max-loss floor (magenta) are translucent glass planes; two marker walls at 2 and 3 weeks (10 / 15
//   sessions) carry the owner's rule: decided within 2 weeks, passed within 3. HTML overlay: counts per outcome (tap a
//   chip to isolate it, tap again for all) and the probabilities. Drag to orbit; tap a path -> opts.onPick(path) (the
//   page's path object); mouse hover shows the tooltip.
//   First data: the ribbons draw themselves left to right (2.4 s) and the flares pop as the draw passes them; new data
//   re-draws quickly; the same data twice does nothing.
// setData({ paths: [{ days: [balance per session, ...], result: 'PASS'|'FAIL'|'OPEN', days_n }], start: 50000, target: 53000,
//           maxLoss: 2000, prob: { pass_2w, fail_2w, pass_3w, pass_4w, pass_6w, open_60 } })
//   prob in percent; a missing field is computed from the paths (a week = 5 sessions). A missing result is derived from the
//   last balance (>= target PASS, <= start - maxLoss FAIL, else OPEN). days_n defaults to days.length.
// Draw calls ~12 whatever the path count; up to 300 paths (120 lite) in one strip mesh, 1 flare point per path, 800 dust (280 lite).
import { THREE, Q, glowTexture, POINT_FRAG, count, rng, Hud, addBackdrop, addNebula, addDust, Guides, ringTexture, sprite, additive, attrs,
  paintBackdrop, clamp, smooth, num, esc, hash, fmtK, fmtUsd, pct, corners, div, injectStyle } from './hud.js';

// outcome kinds (index = aMisc.y in the shaders)
const KIND = [
  { key: 'OPEN', col: '#a78bfa', css: '#b9a6ff', label: 'open', size: 0.16 },
  { key: 'PASS', col: '#2ee59d', css: '#4ef0b0', label: 'pass', size: 0.56 },
  { key: 'FAIL', col: '#ff2bd6', css: '#ff7ad9', label: 'fail', size: 0.42 },
];
const WK = 5, NX_MIN = 60, WALLS = [{ s: 2 * WK, text: '2 wk · decided?', col: '#ffd98a', css: '#ffe7a8' }, { s: 3 * WK, text: '3 wk · passed?', col: '#22d3ee', css: '#67e8f9' }];
const _v = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color();

// ------------------------------------------------------------------ shaders
// every path in one strip, expanded in screen space (constant pixel width); colour runs from violet to the outcome colour
// toward the path's end; a selection brightens one path and dims the rest
const PATH_V = `attribute vec3 aPrev; attribute vec3 aNext; attribute float aSide; attribute float aX; attribute vec3 aCol; attribute vec4 aMisc;
uniform vec2 uRes; uniform float uPix; uniform float uDpr; uniform float uSel; uniform float uHov; uniform float uIso; uniform float uAlpha; uniform vec3 uOpen;
varying vec3 vColor; varying float vSide; varying float vX; varying float vEnd; varying float vSeed; varying float vHi; varying float vA; varying float vKind;
void main(){
  mat4 pm = projectionMatrix * modelViewMatrix;
  vec4 c = pm * vec4(position, 1.0), p = pm * vec4(aPrev, 1.0), n = pm * vec4(aNext, 1.0);
  vec2 sp = p.xy / p.w * uRes, sn = n.xy / n.w * uRes;
  vec2 dir = sn - sp; float L = length(dir); dir = L > 1e-5 ? dir / L : vec2(1.0, 0.0);
  vec2 nrm = vec2(-dir.y, dir.x);
  float id = aMisc.x, kind = aMisc.y;
  float sel = 1.0 - step(0.5, abs(id - uSel)), hov = 1.0 - step(0.5, abs(id - uHov));
  vHi = max(sel, hov * 0.7);
  float wpx = clamp(0.018 * uPix / c.w, 1.0 * uDpr, 2.4 * uDpr) * (1.0 + vHi * 1.8);
  c.xy += nrm * aSide * wpx / uRes * c.w;
  gl_Position = c;
  float f = clamp(aX / max(aMisc.z, 1e-4), 0.0, 1.0); f = f * f * (3.0 - 2.0 * f); f = pow(f, 1.7);
  vec3 base = uOpen * (0.8 + 0.35 * aMisc.w);
  vColor = kind < 0.5 ? base : mix(base, aCol, f);
  float iso = uIso < -0.5 ? 1.0 : mix(0.06, 1.0, 1.0 - step(0.5, abs(kind - uIso)));
  float dim = uSel < -0.5 ? 1.0 : mix(0.28, 1.0, sel);
  vA = uAlpha * iso * dim * (1.0 + vHi * 2.2);
  vSide = aSide; vX = aX; vEnd = aMisc.z; vSeed = aMisc.w; vKind = kind;
}`;
const PATH_F = `uniform float uTime; uniform float uMotion; uniform float uRev;
varying vec3 vColor; varying float vSide; varying float vX; varying float vEnd; varying float vSeed; varying float vHi; varying float vA; varying float vKind;
void main(){
  if (vX > uRev) discard;
  float s = abs(vSide);
  float core = exp(-s * s * 8.0), glow = (1.0 - s) * (1.0 - s) * 0.35;
  float head = exp(-pow((vX - uRev) * 60.0, 2.0)) * step(uRev, 0.999) * 2.5;
  float flow = exp(-pow((fract(vX * 3.0 - uTime * 0.08 * uMotion + vSeed) - 0.5) * 6.0, 2.0)) * 0.5 * uMotion;
  float endGlow = exp(-pow((vEnd - vX) * 28.0, 2.0)) * step(0.5, vKind) * 1.3;
  vec3 c = mix(vColor, vec3(1.0), core * (0.22 + vHi * 0.3)) * (core * (1.0 + flow + head + endGlow) + glow * (1.0 + head));
  gl_FragColor = vec4(c * vA, 1.0);
}`;
// one flare per path at its end: a starburst where a pass crosses the target, an expanding ring where a fail hits the
// floor, a small dot for an open path; it pops when the draw-in passes it
const FLARE_V = `attribute vec3 aCol; attribute float aSize; attribute vec4 aMisc;
uniform float uPix; uniform float uRev; uniform float uTime; uniform float uMotion; uniform float uSel; uniform float uHov; uniform float uIso;
varying vec3 vColor; varying float vAlpha; varying float vKind; varying float vHi; varying float vPop;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float k = clamp((uRev - aMisc.z) * 10.0, 0.0, 1.0);
  float pop = k < 1.0 ? k * (1.0 + 1.4 * sin(k * 3.14159)) : 1.0;
  float tw = 1.0 + 0.12 * sin(uTime * uMotion * (1.5 + aMisc.w * 2.0) + aMisc.w * 40.0);
  float sel = 1.0 - step(0.5, abs(aMisc.x - uSel)), hov = 1.0 - step(0.5, abs(aMisc.x - uHov));
  vHi = max(sel, hov * 0.7);
  gl_PointSize = clamp(aSize * uPix * pop * tw * (1.0 + vHi * 0.6) / -mv.z, 0.0, 130.0);
  gl_Position = projectionMatrix * mv;
  float iso = uIso < -0.5 ? 1.0 : mix(0.06, 1.0, 1.0 - step(0.5, abs(aMisc.y - uIso)));
  float dim = uSel < -0.5 ? 1.0 : mix(0.35, 1.0, sel);
  vColor = aCol; vAlpha = step(0.001, k) * iso * dim; vKind = aMisc.y; vPop = 1.0 - k;
}`;
const FLARE_F = `varying vec3 vColor; varying float vAlpha; varying float vKind; varying float vHi; varying float vPop;
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2);
  float halo = 1.0 - d2; halo = halo * halo * halo;
  float core = exp(-d2 * 26.0);
  float spk = (exp(-abs(q.x) * 60.0) + exp(-abs(q.y) * 60.0)) * (1.0 - d);
  float ring = exp(-pow((d - 0.5 - vPop * 0.35) * 9.0, 2.0));
  float isPass = step(0.5, vKind) * (1.0 - step(1.5, vKind)), isFail = step(1.5, vKind);
  float hi = vHi * exp(-pow((d - 0.86) * 10.0, 2.0)) * 0.9;
  float a = halo * 0.4 + core * 1.0 + spk * 1.1 * isPass + ring * 0.85 * isFail + hi;
  vec3 c = mix(vColor, vec3(1.0), clamp(core * 0.6 + hi * 0.3, 0.0, 1.0));
  gl_FragColor = vec4(c * a * vAlpha, 1.0);
}`;
// glass planes (target / floor): a fine grid, a glowing rim, a slow scan
const PLANE_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const PLANE_F = `uniform vec2 uX; uniform vec2 uZ; uniform vec3 uC1; uniform vec3 uC2; uniform float uTime; uniform float uMotion; uniform float uIn; uniform float uK; varying vec3 vW;
float grid(vec2 p, vec2 s){ vec2 c = p / s; vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c); return 1.0 - min(min(g.x, g.y), 1.0); }
void main(){
  vec2 p = vW.xz, lo = vec2(uX.x, uZ.x), hi = vec2(uX.y, uZ.y), e = min(p - lo, hi - p); float edge = min(e.x, e.y);
  if (edge < 0.0) discard;
  vec2 c = (p - (lo + hi) * 0.5) / ((hi - lo) * 0.5); float sx = (p.x - lo.x) / (hi.x - lo.x);
  float t = uTime * uMotion, scan = exp(-pow((sx - fract(t * 0.05)) * 12.0, 2.0)) * uMotion;
  float g = grid(p - lo, (hi - lo) / vec2(12.0, 4.0));
  vec3 col = mix(uC1, uC2, clamp(sx * 0.7 + scan * 0.5, 0.0, 1.0));
  float a = (exp(-dot(c, c) * 1.1) * 0.1 + g * 0.12 * (0.6 + scan) + scan * 0.05) * uIn + exp(-edge * 30.0) * 0.6 + exp(-edge * 6.0) * 0.05;
  gl_FragColor = vec4(col * a * uK, 1.0);
}`;
// the two marker walls (one mesh): a soft sheet brighter at the top, glowing edges, a slow vertical scan
const WALL_V = `attribute float aK; varying vec2 vUv; varying float vK; void main(){ vUv = uv; vK = aK; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const WALL_F = `uniform vec3 uCA; uniform vec3 uCB; uniform float uTime; uniform float uMotion; uniform float uIn; varying vec2 vUv; varying float vK;
void main(){
  vec3 col = vK < 0.5 ? uCA : uCB;
  vec2 e = min(vUv, 1.0 - vUv); float edge = min(e.x, e.y);
  float scan = exp(-pow((vUv.y - fract(uTime * 0.09 * uMotion + vK * 0.5)) * 10.0, 2.0)) * uMotion;
  float a = (0.025 + 0.05 * vUv.y + exp(-edge * 45.0) * 0.42 + scan * 0.05) * uIn;
  gl_FragColor = vec4(col * a, 1.0);
}`;

const CSS = `.fxh-montecarlo .mc-top{position:absolute;left:10px;top:9px;right:10px;display:flex;flex-direction:column;gap:6px;pointer-events:none}
.fxh-montecarlo .fxh-leg{position:static;left:auto;top:auto;right:auto}
.fxh-montecarlo .fxh-leg span{pointer-events:auto;cursor:pointer;padding:3px 6px;margin:-3px -2px;border-radius:7px;border:1px solid transparent;transition:background .2s,border-color .2s,opacity .2s}
.fxh-montecarlo .fxh-leg span.on{background:rgba(124,92,255,.18);border-color:rgba(167,139,250,.45)}
.fxh-montecarlo .fxh-leg.iso span:not(.on){opacity:.45}
.fxh-montecarlo .fxh-leg em{font-style:normal;font-weight:500;color:rgba(188,192,236,.5)}
.fxh-montecarlo .mc-top{gap:4px}
.fxh-montecarlo .mc-prob{display:flex;flex-wrap:wrap;gap:3px 4px;font-size:9px;font-weight:600;letter-spacing:.02em;line-height:1;color:rgba(188,192,236,.72)}
.fxh-montecarlo .mc-prob span{display:inline-flex;align-items:center;gap:3px;padding:2px 5px;border-radius:6px;background:rgba(10,8,24,.58);border:1px solid rgba(150,130,255,.22);white-space:nowrap}
.fxh-montecarlo .mc-prob em{font-style:normal;font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:8px;color:rgba(214,218,250,.62);margin-right:2px}
.fxh-montecarlo .mc-prob b{font-weight:800;color:#eef0fb}.fxh-montecarlo .mc-prob b.g{color:#4ef0b0}.fxh-montecarlo .mc-prob b.m{color:#ff7ad9}.fxh-montecarlo .mc-prob b.v{color:#b9a6ff}
.fxh-montecarlo .fxh-l.wall{font-size:9px;font-weight:700;letter-spacing:.03em}`;

const kindIdx = (s) => { const k = String(s ?? '').trim().toUpperCase(); return k.startsWith('PASS') ? 1 : k.startsWith('FAIL') || k.startsWith('BREACH') ? 2 : k ? 0 : -1; };
function dollarTicks(lo, hi) {
  const span = Math.max(1, hi - lo), raw = span / 5, p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw) || 10 * p, out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-6; v += step) out.push(Math.round(v));
  return out;
}

// ------------------------------------------------------------------ the view
export class MonteCarlo extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'montecarlo', fov: 36, empty: 'No simulated evals yet',
      orbit: { yaw: -0.3, pitch: 0.2, auto: 0.03, min: -0.75, max: 0.75, pitchMin: 0.02, pitchMax: 0.7 } });
    injectStyle('fxh-mc-css', CSS);
    this.W = 5.8; this.H = 3; this.D = 1.5; this.NX = NX_MIN; this.paths = []; this.cnt = [0, 0, 0]; this.nAll = 0; this.cap = 0;
    this.start = 50000; this.target = 53000; this.maxLoss = 2000; this.lo = 47000; this.hi = 54000; this.prob = null; this.box = null;
    this.sel = -1; this.hov = -1; this.iso = -1; this.revAt = -99; this.revDur = 1; this.revving = false; this.introAt = -1; this.introDone = false;
    this.maxPaths = count(300, 120);
    Object.assign(this.u, { uRes: { value: new THREE.Vector2(1, 1) }, uDpr: { value: 1 }, uSel: { value: -1 }, uHov: { value: -1 }, uIso: { value: -1 },
      uAlpha: { value: 0.5 }, uRev: { value: 1.02 }, uOpen: { value: new THREE.Color(KIND[0].col) } });
    this.build(); this.ensureCap(128);
    this.top = div('mc-top'); this.ui.prepend(this.top);
    this.legend = div('fxh-leg', this.top); this.probEl = div('mc-prob', this.top);
    this.legend.addEventListener('click', (e) => {
      const s = e.target.closest('span[data-k]'); if (!s) return;
      const k = +s.dataset.k; this.setIso(this.iso === k ? -1 : k);
    });
    this.hint = div('fxh-l h fix', this.ui);
  }
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.45, 0.5]);
    addNebula(S, [['#6d28d9', -5, 2.5, -9, 15, 8, 0.1], ['#ff2bd6', 5, -1, -9, 12, 7, 0.045]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 650 : 800, 280), box: [6.5, 2.5, 3], cy: 1.5, seed: 43 });
    const plane = (c1, c2, k) => {
      const U = { uX: { value: new THREE.Vector2() }, uZ: { value: new THREE.Vector2() }, uC1: { value: new THREE.Color(c1) }, uC2: { value: new THREE.Color(c2) }, uTime: u.uTime, uMotion: u.uMotion, uIn: { value: 1 }, uK: { value: k } };
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(PLANE_V, PLANE_F, U, { side: THREE.DoubleSide, extensions: { derivatives: true } }));
      m.rotation.x = -Math.PI / 2; m.renderOrder = 2; m.userData.U = U; S.add(m); return m;
    };
    this.tgt = plane('#1fb982', '#5eead4', 1); this.flr = plane('#b02aa0', '#ff4fd8', 0.85);
    this.wU = { uCA: { value: new THREE.Color(WALLS[0].col) }, uCB: { value: new THREE.Color(WALLS[1].col) }, uTime: u.uTime, uMotion: u.uMotion, uIn: { value: 1 } };
    this.walls = new THREE.Mesh(new THREE.BufferGeometry(), additive(WALL_V, WALL_F, this.wU, { side: THREE.DoubleSide })); this.walls.renderOrder = 3; S.add(this.walls);
    this.guides = new Guides(S, 3);
    this.lines = new THREE.Mesh(new THREE.BufferGeometry(), additive(PATH_V, PATH_F, u, { side: THREE.DoubleSide })); this.lines.renderOrder = 6; S.add(this.lines);
    this.origin = sprite(S, glowTexture(), '#d9ccff', 5, 0.7); this.origin.visible = true;
    const ret = ringTexture(true); this.textures.push(ret);
    this.reticle = sprite(S, ret, '#ffffff', 12);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(128, Math.ceil(n * 1.25 / 64) * 64);
    const fg = attrs(cap, { position: [3], aCol: [3], aSize: [1], aMisc: [4] });
    if (!this.flares) { this.flares = new THREE.Points(fg, additive(FLARE_V, FLARE_F, this.u)); this.flares.renderOrder = 8; this.flares.frustumCulled = false; this.scene.add(this.flares); }
    else { this.flares.geometry.dispose(); this.flares.geometry = fg; }
    this.cap = cap;
  }
  retheme() { paintBackdrop(this.bgU); }
  shape(w, h) {
    const asp = w / h, W = 5.8 * Math.pow(clamp(asp / 1.1, 1, 2.4), 0.8), H = 3.0 * clamp(1.3 / asp, 0.85, 1.2);
    const changed = Math.abs(W - this.W) > 0.15 || Math.abs(H - this.H) > 0.08;
    this.W = W; this.H = H; return changed;
  }
  relayout(w, h) {
    const dpr = this.renderer.getPixelRatio(); this.u.uRes.value.set(w * dpr / 2, h * dpr / 2); this.u.uDpr.value = dpr;
    this.regionFix();
    if (this.shape(w, h) || !this.framed) { this.framed = true; if (this.paths.length) this.rebuild(false); else this.frameScene(); }
  }
  regionFix() { const th = this.top?.isConnected ? this.top.offsetHeight : 14; this.region = [-1, 1, -1 + 2 * 18 / this.h, 1 - 2 * (th + 14) / this.h]; }
  attach(el) { super.attach(el); this.regionFix(); }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' && !Array.isArray(d) ? d : { paths: Array.isArray(d) ? d : [] };
    const list = Array.isArray(src.paths) ? src.paths : [];
    const start = num(src.start, 50000), target = num(src.target, start + 3000), maxLoss = Math.abs(num(src.maxLoss, 2000)) || 2000, floor = start - maxLoss;
    const probIn = src.prob && typeof src.prob === 'object' ? src.prob : {};
    const all = [];
    let sig = list.length + '|' + start + '|' + target + '|' + maxLoss + '|' + JSON.stringify(probIn) + ':';
    for (let i = 0; i < list.length; i++) {
      const p = list[i]; if (!p || typeof p !== 'object') continue;
      const raw = Array.isArray(p.days) ? p.days : [], b = [];
      let mn = Infinity, mx = -Infinity;
      for (const v of raw) { const x = num(v); if (!Number.isFinite(x)) break; b.push(x); if (x < mn) mn = x; if (x > mx) mx = x; }
      if (!b.length) continue;
      const last = b[b.length - 1];
      let ki = kindIdx(p.result); if (ki < 0) ki = last >= target ? 1 : last <= floor ? 2 : 0;
      const m = Math.max(1, Math.min(b.length, Math.round(num(p.days_n, b.length)) || b.length));
      all.push({ src: p, b: b.length > m ? b.slice(0, m) : b, m, ki, last, min: Math.min(mn, start), max: Math.max(mx, start), seed: hash(i + ':' + m + ':' + last) });
      sig += ki + '/' + m + '/' + Math.round(last) + '/' + Math.round(mn) + '/' + Math.round(mx) + ',';
    }
    if (sig === this.sig) { if (all.length === this.nAll) for (const q of this.paths) q.src = all[q.ai].src; return; }
    this.sig = sig;
    this.start = start; this.target = target; this.maxLoss = maxLoss; this.nAll = all.length;
    // probabilities: the page's numbers, missing ones from every path
    const nA = Math.max(1, all.length), share = (fn) => Math.round(all.filter(fn).length / nA * 1000) / 10;
    const calc = { pass_2w: share((p) => p.ki === 1 && p.m <= 2 * WK), fail_2w: share((p) => p.ki === 2 && p.m <= 2 * WK), pass_3w: share((p) => p.ki === 1 && p.m <= 3 * WK),
      pass_4w: share((p) => p.ki === 1 && p.m <= 4 * WK), pass_6w: share((p) => p.ki === 1 && p.m <= 6 * WK), open_60: share((p) => p.ki === 0) };
    this.prob = {}; for (const k in calc) { const v = num(probIn[k]); this.prob[k] = Number.isFinite(v) ? v : calc[k]; }
    this.cnt = [0, 0, 0]; for (const p of all) this.cnt[p.ki]++;
    // up to maxPaths of them, sampled evenly so the mix of outcomes stays honest
    const capN = this.maxPaths, step = all.length / capN, pick = all.length > capN ? Array.from({ length: capN }, (_, i) => all[Math.floor(i * step)]) : all;
    pick.forEach((p, i) => { p.ai = all.indexOf(p); p.id = i; p.zr = (hash('z' + p.seed) - 0.5); });
    this.paths = pick;
    this.NX = Math.max(NX_MIN, ...pick.map((p) => p.m));
    // balance range: floor and target with margins, stretched for the bulk of the paths (2nd..98th percentile), capped
    const sortNum = (a) => a.sort((x, y) => x - y), mins = sortNum(pick.map((p) => p.min)), maxs = sortNum(pick.map((p) => p.max)), q = (a, f) => (a.length ? a[Math.floor(f * (a.length - 1))] : NaN);
    let lo = floor - maxLoss * 0.3, hi = target + (target - start) * 0.35;
    if (pick.length) { lo = Math.min(lo, q(mins, 0.02)); hi = Math.max(hi, q(maxs, 0.98)); }
    lo = Math.max(lo, floor - 2 * maxLoss); hi = Math.min(hi, target + 2 * (target - start));
    this.lo = lo; this.hi = hi;
    if (this.sel >= 0 && this.sel >= pick.length) this.select(-1);
    if (this.hov >= 0) this.hoverAt(-1);
    this.u.uAlpha.value = clamp(1.0 - pick.length / 330, 0.2, 0.75);
    const n = pick.length, first = !this.introDone && n > 0;
    this.rebuild(true, first);
    if (first) { this.introDone = true; this.introAt = Q.reduced ? -1 : this.lt; this.setIn(Q.reduced ? 1 : 0); }
    this.empty.textContent = list.length && !n ? 'No usable eval paths' : 'No simulated evals yet';
    this.empty.style.display = n ? 'none' : 'block';
    this.ui.classList.add('on');
    this.tipKey = null; this.tipFor(this.hov >= 0 ? this.hov : this.sel);
  }
  setIn(v) { this.tgt.userData.U.uIn.value = this.flr.userData.U.uIn.value = this.wU.uIn.value = v; }
  X(s) { return s / this.NX * this.W - this.W / 2; }
  Y(b) { return (clamp(b, this.lo, this.hi) - this.lo) / (this.hi - this.lo) * this.H; }
  // geometry for the current card shape (and a fresh draw-in when the data changed)
  rebuild(redraw, intro) {
    const P = this.paths, n = P.length, NX = this.NX, D = this.D, start = this.start, target = this.target;
    let nv = 0, idx = [];
    for (const p of P) nv += (p.m + 1) * 2;
    const G = attrs(nv, { position: [3], aPrev: [3], aNext: [3], aSide: [1], aX: [1], aCol: [3], aMisc: [4] }), A = G.attributes;
    this.ensureCap(n);
    const F = this.flares.geometry.attributes;
    let v = 0;
    P.forEach((p, i) => {
      const m = p.m, k = KIND[p.ki];
      // a pass ends where it crosses the target plane (the eval is over there): session jc at fraction t into it
      let cut = null;
      if (p.ki === 1) for (let j = 1; j <= m; j++) { const a = j === 1 ? start : p.b[j - 2], b = p.b[j - 1]; if (b >= target && a < target) { cut = { j, t: (target - a) / (b - a) }; break; } }
      const np = p.np = cut ? cut.j + 1 : m + 1, last = np - 1, pts = p.P = new Float32Array(np * 3);
      for (let j = 0; j < np; j++) {
        const x = cut && j === last ? j - 1 + cut.t : j, bal = cut && j === last ? target : j ? p.b[j - 1] : start;
        pts[j * 3] = this.X(x); pts[j * 3 + 1] = this.Y(bal); pts[j * 3 + 2] = p.zr * D * Math.min(1, x / 6);
      }
      const endX = (cut ? cut.j - 1 + cut.t : m) / NX, c = _c.set(k.col).multiplyScalar(1.25), base = v;
      for (let j = 0; j < np; j++) {
        const jp = Math.max(0, j - 1), jn = Math.min(last, j + 1), ax = (cut && j === last ? endX * NX : j) / NX;
        for (const side of [-1, 1]) {
          A.position.setXYZ(v, pts[j * 3], pts[j * 3 + 1], pts[j * 3 + 2]); A.aPrev.setXYZ(v, pts[jp * 3], pts[jp * 3 + 1], pts[jp * 3 + 2]);
          A.aNext.setXYZ(v, pts[jn * 3], pts[jn * 3 + 1], pts[jn * 3 + 2]); A.aSide.setX(v, side); A.aX.setX(v, ax);
          A.aCol.setXYZ(v, c.r, c.g, c.b); A.aMisc.setXYZW(v, i, p.ki, endX, p.seed); v++;
        }
        if (j < last) { const b2 = base + j * 2; idx.push(b2, b2 + 1, b2 + 2, b2 + 1, b2 + 3, b2 + 2); }
      }
      // flare at the end: on the target plane for a pass, where the fail hit its trailing floor, at session 60 for an open path
      p.F = [pts[last * 3], pts[last * 3 + 1], pts[last * 3 + 2]]; p.endX = endX;
      F.position.setXYZ(i, p.F[0], p.F[1], p.F[2]); _c.set(k.col).lerp(new THREE.Color(1, 1, 1), p.ki ? 0.15 : 0); F.aCol.setXYZ(i, _c.r, _c.g, _c.b);
      F.aSize.setX(i, k.size * (p.ki ? clamp(1.1 - n / 500, 0.7, 1) : 1)); F.aMisc.setXYZW(i, i, p.ki, endX, p.seed);
    });
    G.setIndex(idx);
    this.lines.geometry.dispose(); this.lines.geometry = G;
    for (const a of [F.position, F.aCol, F.aSize, F.aMisc]) a.needsUpdate = true;
    this.flares.geometry.setDrawRange(0, n);
    this.lines.visible = this.flares.visible = this.guides.obj.visible = this.tgt.visible = this.flr.visible = this.walls.visible = this.origin.visible = n > 0;
    // draw-in
    if (redraw && n) {
      if (Q.reduced) { this.revAt = -99; this.u.uRev.value = 1.02; }
      else { this.revAt = this.lt + (intro ? 0.35 : 0.05); this.revDur = intro ? 2.4 : 1.1; this.revving = true; this.u.uRev.value = 0; }
    }
    this.frameScene();
  }
  revK() { return this.revAt < 0 ? 1 : clamp((this.lt - this.revAt) / this.revDur, 0, 1); }
  revealed(x) { return this.u.uRev.value >= x; }

  // ---------------------------------------------------------------- planes, walls, guides, labels, legend
  frameScene() {
    const W = this.W, H = this.H, D = this.D, n = this.paths.length, start = this.start, target = this.target, floor = start - this.maxLoss;
    const x0 = -W / 2 - 0.25, x1 = W / 2 + 0.25, yb = -0.1, yt = H + 0.1, zb = -D / 2 - 0.35, zf = D / 2 + 0.35;
    this.box = { x0, x1, yb, yt, zb, zf };
    const yT = this.Y(target), yF = this.Y(floor), yS = this.Y(start);
    for (const [m, y] of [[this.tgt, yT], [this.flr, yF]]) { m.position.set(0, y, (zb + zf) / 2); m.scale.set(x1 - x0, zf - zb, 1); m.userData.U.uX.value.set(x0, x1); m.userData.U.uZ.value.set(zb, zf); }
    // walls
    const wp = [], wu = [], wk = [], wi = [];
    WALLS.forEach((w, k) => {
      const x = this.X(w.s), b = k * 4;
      wp.push(x, yb, zb, x, yb, zf, x, yt, zf, x, yt, zb); wu.push(0, 0, 1, 0, 1, 1, 0, 1); wk.push(k, k, k, k); wi.push(b, b + 1, b + 2, b, b + 2, b + 3);
    });
    const WG = new THREE.BufferGeometry();
    WG.setAttribute('position', new THREE.Float32BufferAttribute(wp, 3)); WG.setAttribute('uv', new THREE.Float32BufferAttribute(wu, 2)); WG.setAttribute('aK', new THREE.Float32BufferAttribute(wk, 1)); WG.setIndex(wi);
    this.walls.geometry.dispose(); this.walls.geometry = WG;
    // guides
    const G = this.guides, vio = new THREE.Color('#8f86ff'), yt2 = dollarTicks(this.lo, this.hi);
    const xt = []; for (let s = 0; s <= this.NX; s += 10) xt.push(s);
    for (const s of xt) { const x = this.X(s); G.seg(x, yb, zb, x, yt, zb, vio, 0.08, 4).seg(x, yb, zb, x, yb, zf, vio, 0.07, 4); }
    for (const v of yt2) { const y = this.Y(v); G.seg(x0, y, zb, x1, y, zb, vio, 0.08, 4); G.seg(x0 - 0.08, y, zb, x0 + 0.06, y, zb, vio, 0.5); }
    G.seg(x0, yb, zb, x0, yt, zb, vio, 0.3).seg(x0, yb, zb, x1, yb, zb, vio, 0.25).seg(x1, yb, zb, x1, yb, zf, vio, 0.25).seg(x0, yb, zf, x1, yb, zf, vio, 0.12);
    G.seg(x0, yS, zb, x1, yS, zb, new THREE.Color('#d9ccff'), 0.2, 6);
    G.commit();
    this.origin.position.set(this.X(0), yS, 0); this.origin.scale.setScalar(0.55);
    this.anchors = new Float32Array(corners([], x0 - 0.45, x1 + 0.3, yb - 0.25, yt + 0.2, zb, zf + 0.2));
    this.T.set(0, (yb + yt) / 2, 0);
    // labels
    const defs = [];
    if (n) {
      for (const s of xt) defs.push({ text: String(s), p: new THREE.Vector3(this.X(s), yb, zf), ay: 0, dy: 4, tick: 'x' });
      defs.push({ text: 'sessions →', p: new THREE.Vector3(x1, yb, zf), ax: 1, ay: 0, dy: 17, cls: 't' });
      for (const v of yt2) defs.push({ text: fmtK(v, false), p: new THREE.Vector3(x0 - 0.12, this.Y(v), zb), ax: 1, avoid: true });
      defs.push({ text: 'target ' + fmtK(target, false), p: new THREE.Vector3(x1, yT, zf), ax: 1, ay: 1, dy: -4, cls: 't', color: KIND[1].css, avoid: true, keep: true });
      defs.push({ text: 'max-loss floor ' + fmtK(floor, false) + ' · trails', p: new THREE.Vector3(x1, yF, zf), ax: 1, ay: 0, dy: 4, cls: 't', color: KIND[2].css, avoid: true, keep: true });
      defs.push({ text: 'start ' + fmtK(start, false), p: new THREE.Vector3(this.X(0), yS, zf), ax: 0, ay: 1, dx: 4, dy: -6, cls: 't', color: '#d9ccff', avoid: true });
      WALLS.forEach((w, k) => defs.push({ text: w.text, p: new THREE.Vector3(this.X(w.s), yt, zf), ax: k ? 0 : 1, ay: 1, dx: k ? 3 : -3, dy: -4, cls: 'wall', color: w.css, avoid: true, keep: true,
        alts: [{ ax: 0.5, ay: 1, dy: -4 }, { ax: k ? 0 : 1, ay: 0, dx: k ? 3 : -3, dy: 4 }] }));
    }
    this.setLabels(defs);
    this.legendFor();
    this.hint.textContent = n ? `${n}${this.nAll > n ? ' of ' + this.nAll : ''} simulated evals · tap a path` : '';
  }
  legendFor() {
    const n = this.nAll, tot = Math.max(1, n), P = this.prob;
    this.legend.innerHTML = n ? KIND.map((k, i) => `<span data-k="${i}" class="fx-tap${this.iso === i ? ' on' : ''}"><i style="background:${k.css};box-shadow:0 0 6px ${k.css}"></i>${k.label} <b>${this.cnt[i]}</b> <em>${pct(this.cnt[i] / tot * 100)}</em></span>`).join('') : '';
    this.legend.classList.toggle('iso', this.iso >= 0);
    this.probEl.innerHTML = n && P ? [
      `<em>2 wk</em> <b class="g">${pct(P.pass_2w)}</b> pass · <b class="m">${pct(P.fail_2w)}</b> fail`,
      `<em>3 wk</em> <b class="g">${pct(P.pass_3w)}</b> pass`,
      `<em>4 wk</em> <b class="g">${pct(P.pass_4w)}</b> · <em>6 wk</em> <b class="g">${pct(P.pass_6w)}</b>`,
      `<em>60 sessions</em> <b class="v">${pct(P.open_60)}</b> still open`,
    ].map((s) => `<span>${s}</span>`).join('') : '';
    this.regionFix();
  }
  setIso(k) {
    this.iso = k; this.u.uIso.value = k;
    this.legendFor(); this.camKey = '';
    if (this.sel >= 0 && k >= 0 && this.paths[this.sel]?.ki !== k) this.select(-1);
  }

  // ---------------------------------------------------------------- picking + tooltip
  // the path whose drawn points come closest to a screen point (css px)
  nearest(px, py, maxPx) {
    const cam = this.camera; _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse); const e = _m.elements;
    const rev = this.u.uRev.value, NX = this.NX, w2 = this.w / 2, h2 = this.h / 2;
    let best = -1, bd = maxPx * maxPx;
    for (let i = 0; i < this.paths.length; i++) {
      const p = this.paths[i]; if (this.iso >= 0 && p.ki !== this.iso) continue;
      const P = p.P, last = p.np - 1;
      for (let j = 0; j <= last; j++) {
        if ((j === last ? p.endX : j / NX) > rev) break;
        const x = P[j * 3], y = P[j * 3 + 1], z = P[j * 3 + 2];
        const cw = e[3] * x + e[7] * y + e[11] * z + e[15]; if (cw <= 0) continue;
        const sx = ((e[0] * x + e[4] * y + e[8] * z + e[12]) / cw + 1) * w2 - px, sy = (1 - (e[1] * x + e[5] * y + e[9] * z + e[13]) / cw) * h2 - py;
        const dd = sx * sx + sy * sy; if (dd < bd) { bd = dd; best = i; }
      }
    }
    return best;
  }
  pickAt(px, py) { const i = this.nearest(px, py, 14); this.select(i); if (i >= 0) this.emit(this.paths[i].src); }
  select(i) { this.sel = i; this.u.uSel.value = i; this.tipFor(this.hov >= 0 ? this.hov : i); }
  hoverAt(i) {
    if (i == null) i = -1;
    if (i === this.hov) return;
    this.hov = i; this.u.uHov.value = i; this.canvas.style.cursor = i >= 0 ? 'pointer' : 'grab';
    this.tipFor(i >= 0 ? i : this.sel);
  }
  tipFor(i) {
    const p = i >= 0 ? this.paths[i] : null;
    if (!p) { this.showTip(null); return; }
    const k = KIND[p.ki], wk = (p.m / WK).toFixed(p.m % WK ? 1 : 0) + ' wk', pnl = p.last - this.start;
    const when = p.ki === 1 ? `passed in <b>${p.m}</b> sessions` : p.ki === 2 ? `failed on session <b>${p.m}</b>` : `still open after <b>${p.m}</b> sessions`;
    this.showTip('p' + p.id + '/' + p.m + '/' + p.last, `<b style="color:${k.css}">${k.key}</b> <i>·</i> ${when} <i>(${wk})</i><br>`
      + `<i>final</i> <b>${fmtUsd(p.last, false)}</b> <b style="color:${pnl >= 0 ? KIND[1].css : KIND[2].css}">${fmtUsd(pnl)}</b> · <i>low</i> ${fmtUsd(p.min, false)} · <i>high</i> ${fmtUsd(p.max, false)}`);
  }
  devTapPoint() { const p = this.paths.find((q) => q.ki === 1) || this.paths[0]; if (!p) return null; const j = Math.max(1, Math.floor((p.np - 1) * 0.6)); const s = this.screen(_v.set(p.P[j * 3], p.P[j * 3 + 1], p.P[j * 3 + 2])); return [s.x, s.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const moved = this.camStep(dt);
    // draw-in
    let busy = false;
    if (this.revving) { const k = this.revK(); u.uRev.value = k >= 1 ? 1.02 : smooth(k) * 1.02; busy = k < 1; if (!busy) { this.revving = false; this.camKey = ''; } }
    // intro: the planes and walls light up
    if (this.introAt >= 0) { const k = clamp((lt - this.introAt) / 1.4, 0, 1); this.setIn(smooth(k)); if (k >= 1) this.introAt = -1; busy = true; }
    // origin glow breathes
    if (this.origin.visible) { const br = Q.reduced ? 1 : 1 + 0.08 * Math.sin(lt * 1.6); this.origin.scale.setScalar(0.55 * br); this.origin.material.opacity = 0.55 + 0.15 * (br - 1) * 6; }
    // selection reticle on the path's flare
    const s = this.sel >= 0 ? this.paths[this.sel] : null;
    if (s) {
      const pulse = Q.reduced ? 1 : 1 + 0.07 * Math.sin(lt * 5), k = KIND[s.ki];
      this.reticle.visible = this.revealed(s.endX); this.reticle.position.set(s.F[0], s.F[1], s.F[2]); this.reticle.scale.setScalar(0.42 * pulse);
      this.reticle.material.rotation = Q.reduced ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95; this.reticle.material.color.set(k.col).lerp(_c.set('#ffffff'), 0.5);
    } else this.reticle.visible = false;
    // html
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.nearest(hx, hy, 12)); }
    if (moved || busy) this.placeLabels();
    const ti = this.hov >= 0 ? this.hov : this.sel, tp = ti >= 0 ? this.paths[ti] : null;
    if (tp && this.tipKey != null) { const p = this.screen(_v.set(tp.F[0], tp.F[1], tp.F[2])); this.placeTip(p.x, p.y, 16); }
  }
}
