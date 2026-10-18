// Run Constellation (Lab overview): every backtest run of the research library is a star in a 3D space.
//   x = profit factor 2021-25, y = profit factor 2026 (both log scale), z = the run's family lane (risk, stops, ...).
//   The baseline (the live strategy) is a white-gold star with a halo and a sonar ping; glowing crosshair planes run
//   through its two PFs so the "better in both periods" quadrant (right of it and above it) glows green on the back wall.
//   Size ~ trades/week, a broken ring = under 2 trades a week (the rules need 2+). Colour by status: adopt-candidate green
//   (pulsing), promising cyan, rejected dim magenta, info violet. A faint link runs from every run to the baseline with
//   energy flowing out along it. PF below 1 (losing money) is shaded magenta.
//   Tap a star -> opts.onPick(run) (the page's run object); mouse hover shows the tooltip; drag to orbit.
//   First data: the baseline flashes and every run bursts out of it to its place; new data: survivors glide, newcomers
//   fly out of the baseline, leavers fade.
// setData({ runs: [{ id, title, family, status, pf26, pf21, net26, net21, tpw26, tpw21, dd21, p20_21, f20_21 }], baseline: 'baseline' })
// Draw calls ~17 whatever the run count; particles: 1 star + 1 floor shadow per run + 1000 dust (300 lite).
import { THREE, Q, theme, glowTexture, POINT_FRAG, Hud, addBackdrop, addNebula, addDust, Guides, ringTexture, sprite, additive, attrs,
  paintBackdrop, clamp, smooth, outCubic, outBack, fract, num, esc, hash, fmtK, fmtPf, pct, corners, div } from './hud.js';

const LANES = ['risk', 'stops', 'targets', 'management', 'bias', 'filters', 'timing', 'other'];   // front -> back
const ST = {
  baseline: { col: '#ffe3a0', k: 1.55, css: '#ffe7a8', label: 'baseline' },
  'adopt-candidate': { col: '#2ee59d', k: 1.3, css: '#4ef0b0', label: 'adopt?', pulse: 1 },
  promising: { col: '#22d3ee', k: 1.15, css: '#67e8f9', label: 'promising' },
  rejected: { col: '#ff2bd6', k: 0.52, css: '#ff7ad9', label: 'rejected' },
  info: { col: '#8b5cf6', k: 1.0, css: '#b9a6ff', label: 'info' },
};
const ORDER = ['baseline', 'adopt-candidate', 'promising', 'info', 'rejected'];
const FLY = 1, MOVE = 2, SHRINK = 4;
const FLOOR = -0.32, M = 0.3;    // floor height under the lowest PF 2026, margin of the walls around the data box
const NICE = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10, 12, 15, 20];
const lg = (v) => Math.log(clamp(v, 0.25, 20));
// fallback spots for a tag next to a star: up-left, down-right, down-left
const ALTS = (dx, dy) => [{ ax: 1, ay: 1, dx: -dx, dy: -dy }, { ax: 0, ay: 0, dx, dy }, { ax: 1, ay: 0, dx: -dx, dy }];
const tickTxt = (v) => (v >= 2 && Number.isInteger(v) ? String(v) : v.toFixed(1));
const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s);
const _v = new THREE.Vector3(), _m = new THREE.Matrix4();

// ------------------------------------------------------------------ shaders
const STAR_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; attribute vec4 aMisc; attribute float aSpike;
uniform float uTime; uniform float uPix; uniform float uMotion; uniform float uSel; uniform float uHov; uniform float uFocus;
varying vec3 vColor; varying float vAlpha; varying float vRing; varying float vSpike; varying float vHi; varying float vPulse;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float t = uTime * uMotion;
  float tw = 1.0 + 0.1 * sin(t * (1.1 + aMisc.z * 2.3) + aMisc.z * 61.0);
  float pul = aMisc.y * mix(0.5, 0.5 + 0.5 * sin(t * 3.4 + aMisc.z * 6.2831), uMotion);
  vHi = max(1.0 - step(0.5, abs(aMisc.w - uSel)), (1.0 - step(0.5, abs(aMisc.w - uHov))) * 0.75);
  gl_PointSize = clamp(aSize * uPix * tw * (1.0 + vHi * 0.5 + pul * 0.3) / -mv.z, 0.0, 150.0);
  gl_Position = projectionMatrix * mv;
  float depth = clamp(1.15 - (-mv.z - uFocus) * 0.06, 0.72, 1.2);
  vColor = aCol * depth * (1.0 + pul * 0.6); vAlpha = aAlpha; vRing = aMisc.x; vSpike = aSpike; vPulse = pul;
}`;
const STAR_F = `varying vec3 vColor; varying float vAlpha; varying float vRing; varying float vSpike; varying float vHi; varying float vPulse;
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2);
  float halo = 1.0 - d2; halo = halo * halo * halo;
  float core = exp(-d2 * 30.0);
  float spk = (exp(-abs(q.x) * 70.0) + exp(-abs(q.y) * 70.0)) * (1.0 - d) * vSpike;
  float dash = step(0.42, fract(atan(q.y, q.x) * 1.2732395));
  float ring = vRing * exp(-pow((d - 0.6) * 12.0, 2.0)) * dash;
  float hi = vHi * exp(-pow((d - 0.86) * 10.0, 2.0));
  float pr = vPulse * exp(-pow((d - 0.72) * 8.0, 2.0)) * 0.7;
  float a = halo * 0.42 + core * 1.05 + spk * 0.8 + ring * 0.85 + hi * 0.9 + pr;
  vec3 c = mix(vColor, vec3(1.0), clamp(core * 0.55 + hi * 0.25, 0.0, 1.0));
  gl_FragColor = vec4(c * a * vAlpha, 1.0);
}`;
// a dim dot on the floor under every star (depth cue)
const SHADOW_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; uniform float uPix; uniform float uFloor;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position.x, uFloor + 0.004, position.z, 1.0);
  gl_PointSize = clamp(aSize * 0.5 * uPix / -mv.z, 0.0, 40.0); gl_Position = projectionMatrix * mv;
  vColor = aCol * 0.32; vAlpha = aAlpha * smoothstep(0.02, 0.4, position.y - uFloor); }`;
const LINK_V = `attribute vec3 aCol; attribute float aT; attribute float aA; attribute float aSeed; attribute float aId;
uniform float uSel; uniform float uHov; varying vec3 vColor; varying float vA; varying float vT; varying float vSeed; varying float vHi;
void main(){ gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); vColor = aCol; vA = aA; vT = aT; vSeed = aSeed;
  vHi = max(1.0 - step(0.5, abs(aId - uSel)), (1.0 - step(0.5, abs(aId - uHov))) * 0.7); }`;
const LINK_F = `uniform float uTime; uniform float uMotion; uniform float uLink;
varying vec3 vColor; varying float vA; varying float vT; varying float vSeed; varying float vHi;
void main(){ float ph = fract(uTime * 0.2 * uMotion + vSeed);
  float pulse = exp(-pow((vT - ph) * 9.0, 2.0)) * uMotion;
  float a = vA * (0.06 + 0.2 * vT + pulse * 0.4) * (1.0 + vHi * 4.0) * uLink;
  gl_FragColor = vec4(vColor * a, 1.0); }`;
const WALL_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
// back wall: the better-in-both quadrant glows green (brightest next to the baseline), PF < 1 is shaded magenta
const WALL_F = `uniform vec2 uX; uniform vec2 uY; uniform vec2 uB; uniform float uHasB; uniform vec2 uOne;
uniform vec3 uGood; uniform vec3 uBad; uniform vec3 uBase; uniform float uTime; uniform float uMotion; uniform float uIn;
varying vec3 vW;
void main(){
  vec2 p = vW.xy, e = min(p - vec2(uX.x, uY.x), vec2(uX.y, uY.y) - p); float edge = min(e.x, e.y);
  if (edge < 0.0) discard;
  float t = uTime * uMotion, breathe = 0.82 + 0.18 * sin(t * 1.2);
  vec2 c = (p - vec2((uX.x + uX.y) * 0.5, (uY.x + uY.y) * 0.5)) / vec2(uX.y - uX.x, uY.y - uY.x);
  vec3 col = uBase * (0.03 + 0.05 * exp(-dot(c, c) * 3.0));
  vec2 q = p - uB;
  float better = uHasB * step(0.0, q.x) * step(0.0, q.y);
  col += uGood * better * (0.035 + 0.16 * exp(-length(q) * 0.6)) * breathe * uIn;
  float rim = uHasB * (exp(-abs(q.x) * 26.0) * step(0.0, q.y) + exp(-abs(q.y) * 26.0) * step(0.0, q.x));
  col += uGood * rim * 0.5 * breathe * uIn;
  float cross = uHasB * (exp(-abs(q.x) * 40.0) + exp(-abs(q.y) * 40.0)) * (1.0 - better);
  col += uBase * cross * 0.35 * uIn;
  float lose = max(step(p.x, uOne.x), step(p.y, uOne.y));
  col += uBad * lose * 0.045;
  col += uBase * (exp(-edge * 24.0) * 0.55 + exp(-edge * 5.0) * 0.04);
  gl_FragColor = vec4(col, 1.0);
}`;
const FLOOR_F = `uniform vec2 uX; uniform vec2 uZ; uniform vec3 uC1; uniform vec3 uC2; uniform float uTime; uniform float uMotion; uniform float uBx; uniform float uHasB; uniform vec3 uGood;
varying vec3 vW;
void main(){
  vec2 p = vW.xz, lo = vec2(uX.x, uZ.x), hi = vec2(uX.y, uZ.y), e = min(p - lo, hi - p); float edge = min(e.x, e.y);
  if (edge < 0.0) discard;
  vec2 c = (p - (lo + hi) * 0.5) / ((hi - lo) * 0.5);
  float t = uTime * uMotion, sx = (p.x - lo.x) / (hi.x - lo.x);
  float scan = exp(-pow((sx - fract(t * 0.045)) * 12.0, 2.0)) * uMotion;
  vec3 col = mix(uC1, uC2, clamp(sx * 0.7 + scan * 0.5, 0.0, 1.0));
  float a = exp(-dot(c, c) * 1.3) * 0.08 + scan * 0.05 + exp(-edge * 30.0) * 0.55 + exp(-edge * 6.0) * 0.04;
  vec3 g = uGood * uHasB * step(uBx, p.x) * 0.025;
  gl_FragColor = vec4(col * a + g, 1.0);
}`;
// a crosshair plane through the baseline; the half that borders the better quadrant is brighter and green
const PLANE_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const PLANE_F = `uniform float uSplit; uniform float uAxis; uniform vec3 uCol; uniform vec3 uGood; uniform float uTime; uniform float uMotion; uniform float uA;
varying vec2 vUv;
void main(){
  float s = uAxis < 0.5 ? vUv.y : vUv.x, o = uAxis < 0.5 ? vUv.x : vUv.y;
  float better = step(uSplit, s);
  vec2 e = min(vUv, 1.0 - vUv); float edge = min(e.x, e.y);
  float scan = exp(-pow((o - fract(uTime * 0.07 * uMotion + uAxis * 0.5)) * 12.0, 2.0)) * uMotion;
  vec3 c = mix(uCol, uGood, better);
  float a = (0.03 + better * 0.035 + exp(-edge * 50.0) * 0.4 + scan * 0.045 * (0.6 + better)) * uA;
  gl_FragColor = vec4(c * a, 1.0);
}`;

const CSS = `.fxh-constellation .fxh-l.tag{line-height:1.25}.fxh-constellation .fxh-l.tag em{font-style:normal;font-weight:600;color:rgba(214,218,250,.72)}`;

// ------------------------------------------------------------------ the view
export class Constellation extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'constellation', fov: 36, empty: 'No runs in the library yet',
      orbit: { yaw: -0.24, pitch: 0.17, auto: 0.035, min: -0.7, max: 0.7, pitchMin: 0.02, pitchMax: 0.75 } });
    const st = document.getElementById('fxh-cst-css') || Object.assign(document.createElement('style'), { id: 'fxh-cst-css', textContent: CSS });
    if (!st.isConnected) document.head.appendChild(st);
    this.W = 6.4; this.H = 4.2; this.slots = []; this.byKey = new Map(); this.items = []; this.cap = 0; this.animating = false;
    this.base = null; this.baseSlot = null; this.lanes = []; this.laneZ = new Map(); this.introDone = false; this.introAt = -1; this.unscored = 0;
    this.dom = { x0: -0.3, x1: 0.3, y0: -0.3, y1: 0.3 }; this.box = { zf: 0.6, zb: -0.8 };
    this.sel = null; this.hov = null; this.selAt = 0; this.best = [];
    Object.assign(this.u, { uSel: { value: -1 }, uHov: { value: -1 }, uFocus: { value: 12 }, uFloor: { value: FLOOR }, uLink: { value: 1 } });
    this.build();
    this.ensureCap(64);
    this.legend = div('fxh-leg', null); this.ui.prepend(this.legend);
    this.hint = div('fxh-l h fix', this.ui); this.hint.textContent = '';
  }

  // ---------------------------------------------------------------- scene
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.55, 0.55]);
    addNebula(S, [['#6d28d9', -5, 4.4, -9, 15, 9.5, 0.1], ['#ff2bd6', 5.5, 1.5, -10, 12, 7.5, 0.045], ['#22d3ee', 6.5, 5, -9, 9, 6, 0.035]]);
    this.dust = addDust(S, u, { box: [7, 3, 4], cy: 2, seed: 23 });
    const good = theme.good.clone(), base = new THREE.Color('#6d5cff');
    this.wU = { uX: { value: new THREE.Vector2() }, uY: { value: new THREE.Vector2() }, uB: { value: new THREE.Vector2() }, uHasB: { value: 0 }, uOne: { value: new THREE.Vector2(-1e3, -1e3) },
      uGood: { value: good }, uBad: { value: new THREE.Color('#ff2bd6') }, uBase: { value: base }, uTime: u.uTime, uMotion: u.uMotion, uIn: { value: 0 } };
    this.wall = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(WALL_V, WALL_F, this.wU)); this.wall.renderOrder = 2; S.add(this.wall);
    this.fU = { uX: { value: new THREE.Vector2() }, uZ: { value: new THREE.Vector2() }, uC1: { value: new THREE.Color('#5b3bd1') }, uC2: { value: new THREE.Color('#22d3ee') },
      uTime: u.uTime, uMotion: u.uMotion, uBx: { value: 0 }, uHasB: this.wU.uHasB, uGood: { value: good } };
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(WALL_V, FLOOR_F, this.fU, { side: THREE.DoubleSide }));
    this.floor.rotation.x = -Math.PI / 2; this.floor.renderOrder = 2; S.add(this.floor);
    const plane = (axis) => {
      const U = { uSplit: { value: 0.5 }, uAxis: { value: axis }, uCol: { value: new THREE.Color('#8f86ff') }, uGood: { value: good }, uTime: u.uTime, uMotion: u.uMotion, uA: { value: 0 } };
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(PLANE_V, PLANE_F, U, { side: THREE.DoubleSide })); m.renderOrder = 3; m.userData.U = U; m.visible = false; S.add(m); return m;
    };
    this.vPlane = plane(0); this.vPlane.rotation.y = Math.PI / 2;
    this.hPlane = plane(1); this.hPlane.rotation.x = -Math.PI / 2;
    this.guides = new Guides(S, 4);
    // baseline decorations + markers
    const ret = ringTexture(true), ring = ringTexture(false); this.textures.push(ret, ring);
    this.halo = sprite(S, glowTexture(), '#ffd98a', 9);
    this.crown = sprite(S, ret, '#ffe7a8', 10);
    this.ping = sprite(S, ring, '#ffe7a8', 10);
    this.reticle = sprite(S, ret, '#e9fbff', 12);
    this.flash = sprite(S, glowTexture(), '#fff1c9', 13);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(64, Math.ceil(n * 1.25 / 32) * 32), u = this.u;
    const sg = attrs(cap, { position: [3, 1], aCol: [3], aSize: [1, 1], aAlpha: [1, 1], aMisc: [4], aSpike: [1] });
    const lg2 = attrs(cap * 2, { position: [3, 1], aCol: [3], aT: [1], aA: [1, 1], aSeed: [1], aId: [1] });
    if (!this.stars) {
      this.links = new THREE.LineSegments(lg2, additive(LINK_V, LINK_F, u));
      this.shadows = new THREE.Points(sg, additive(SHADOW_V, POINT_FRAG, u));
      this.stars = new THREE.Points(sg, additive(STAR_V, STAR_F, u));
      this.links.renderOrder = 5; this.shadows.renderOrder = 5; this.stars.renderOrder = 8;
      for (const o of [this.links, this.shadows, this.stars]) { o.frustumCulled = false; this.scene.add(o); }
    } else {
      this.stars.geometry.dispose(); this.links.geometry.dispose();
      this.stars.geometry = sg; this.shadows.geometry = sg; this.links.geometry = lg2;
    }
    this.cap = cap;
  }
  retheme() { paintBackdrop(this.bgU); this.wU.uGood.value.copy(theme.good); }
  // the data box follows the card: a wide desktop card gets a longer PF 2021-25 axis, a phone card a taller PF 2026 one
  shape(w, h) {
    const asp = w / h, W = 6.2 * Math.pow(clamp(asp / 1.1, 1, 2.4), 0.85), H = 4.3 * clamp(1.3 / asp, 0.85, 1.12);
    const changed = Math.abs(W - this.W) > 0.15 || Math.abs(H - this.H) > 0.1;
    this.W = W; this.H = H; return changed;
  }
  relayout(w, h) {
    const lh = this.legend.isConnected ? this.legend.offsetHeight : 14;
    this.region = [-1, 1, -1 + 2 * 18 / h, 1 - 2 * (lh + 14) / h];
    if (!this.userRange) { const r = 0.62 / clamp((w / h) / 1.4, 1, 1.4); this.orbit.min = -r; this.orbit.max = r; }
    if (this.shape(w, h) || !this.framed) {
      this.framed = true;
      if (this.items.length) { this.layout(); this.retarget(0.6); }
      this.frameScene();
    }
  }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' && !Array.isArray(d) ? d : { runs: Array.isArray(d) ? d : [] };
    const list = Array.isArray(src.runs) ? src.runs : [], baseId = src.baseline == null ? 'baseline' : String(src.baseline);
    const items = [], seen = new Set();
    let sig = baseId + '|' + list.length + ':', unscored = 0, baseIdx = -1;
    for (let i = 0; i < list.length; i++) {
      const r = list[i]; if (!r || typeof r !== 'object') continue;
      const pf26 = num(r.pf26), pf21 = num(r.pf21);
      let key = String(r.id ?? r.title ?? 'run' + i); if (seen.has(key)) key += '#' + i; seen.add(key);
      const status = ST[r.status] ? r.status : 'info', fam = LANES.includes(r.family) ? r.family : r.family === 'baseline' ? 'baseline' : 'other';
      const tpw = [num(r.tpw26), num(r.tpw21)].filter(Number.isFinite), tp = tpw.length ? tpw.reduce((a, b) => a + b, 0) / tpw.length : NaN;
      sig += key + '/' + status + '/' + fam + '/' + pf26 + '/' + pf21 + '/' + tp + '/' + (r.title || '') + ',';
      if (!(pf26 > 0) || !(pf21 > 0)) { unscored++; continue; }
      const it = { key, run: r, title: String(r.title || r.id || 'run'), status, fam, pf26, pf21, tpw: tp, slow: tpw.some((v) => v < 2), seed: hash(key) };
      if (String(r.id) === baseId) baseIdx = items.length;
      items.push(it);
    }
    if (baseIdx < 0) baseIdx = items.findIndex((it) => it.status === 'baseline');
    if (sig === this.sig) { for (const it of items) { const s = this.byKey.get(it.key); if (s) s.it.run = it.run; } return; }
    this.sig = sig;
    const base = baseIdx >= 0 ? items[baseIdx] : null;
    for (const it of items) { it.isBase = it === base; if (it.isBase) { it.status = 'baseline'; it.fam = 'baseline'; } }
    this.items = items; this.base = base; this.unscored = unscored;
    // lanes: the families present, in the fixed order (the baseline sits in the middle)
    const fams = new Set(items.filter((it) => !it.isBase).map((it) => it.fam));
    this.lanes = LANES.filter((f) => fams.has(f));
    // best few: the biggest improvement in BOTH periods (the weaker of the two PF ratios vs the baseline)
    const score = (it) => base ? Math.min(Math.log(it.pf26 / base.pf26), Math.log(it.pf21 / base.pf21)) : Math.min(Math.log(it.pf26), Math.log(it.pf21));
    this.layout();
    // (labels only for runs inside the scale that keep 2+ trades a week)
    this.best = items.filter((it) => !it.isBase && !it.off && !it.slow).sort((a, b) => score(b) - score(a)).slice(0, 3).filter((it, i) => i === 0 || score(it) > -0.08);
    const first = !this.slots.length && !this.introDone, now = this.lt, red = Q.reduced, n = items.length;
    const B = base ? new THREE.Vector3(base.tx, base.ty, base.tz) : new THREE.Vector3(0, this.H / 2, 0);
    const rank = items.map((it, i) => [i, Math.hypot(it.tx - B.x, it.ty - B.y, it.tz - B.z)]).sort((a, b) => a[1] - b[1]);
    const order = new Map(rank.map(([i], k) => [i, k]));
    const next = [], keep = new Set();
    items.forEach((it, i) => {
      let sl = this.byKey.get(it.key);
      if (sl && !sl.dead) { sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.mode = MOVE; sl.t0 = now; sl.dur = red ? 0 : 0.95; }
      else {
        sl = { key: it.key, p: new THREE.Vector3(), p0: new THREE.Vector3(), p1: new THREE.Vector3(), s: 0, s0: 0, a: 0, a0: 0, dead: false, done: false, col: new THREE.Color() };
        sl.mode = FLY; sl.p0.copy(this.baseSlot && !this.baseSlot.dead ? this.baseSlot.p : B); sl.p.copy(sl.p0);
        sl.t0 = now + (first ? (it.isBase ? 0.1 : 0.55 + (order.get(i) / Math.max(1, n - 1)) * 1.3) : 0.1 + (order.get(i) / Math.max(1, n)) * 0.4);
        sl.dur = it.isBase ? 0.8 : first ? 1.15 : 0.9;
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
    this.baseSlot = base ? this.byKey.get(base.key) : null;
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.hoverAt(null);
    this.recolor(); this.writeStatic(); this.animating = true;
    if (first && n) { this.introAt = red ? -1 : now; this.introDone = true; this.wU.uIn.value = red ? 1 : 0; }
    this.frameScene();
    this.empty.textContent = list.length && !n ? 'No scored runs yet' : 'No runs in the library yet';
    this.empty.style.display = n ? 'none' : 'block';
    this.ui.classList.add('on');
    this.tipKey = null; this.tipFor(this.hov || this.sel);
  }
  // log-PF domain: every run + the baseline, at least x1.5 (2021-25) / x1.8 (2026) wide, padded
  layout() {
    const its = this.items;
    // robust range: outliers (a PF of 15 from a handful of trades) are pinned to the edge instead of squashing the rest
    const q = (arr, keep) => { const v = [...arr].sort((a, b) => a - b), n = v.length; if (!n) return [0, 0];
      let a = v[0], c = v[n - 1];
      if (n >= 6) {   // Tukey fences in log space
        const at = (f) => { const i = f * (n - 1), j = Math.floor(i); return v[j] + (v[Math.min(n - 1, j + 1)] - v[j]) * (i - j); };
        const q1 = at(0.25), q3 = at(0.75), iqr = Math.max(0.08, q3 - q1); a = Math.max(a, q1 - 1.5 * iqr); c = Math.min(c, q3 + 1.5 * iqr);
      }
      if (keep != null) { a = Math.min(a, keep); c = Math.max(c, keep); } return [a, c]; };
    // and a sane PF window: 0.5-3 for five years, 0.5-6 for 2026 (beyond that it is a tiny sample, not an edge)
    const cap = ([a, c], lo, hi) => [clamp(a, lo, hi), clamp(c, lo, hi)];
    let [x0, x1] = cap(q(its.map((it) => lg(it.pf21)), this.base ? lg(this.base.pf21) : null), Math.log(0.5), Math.log(3));
    let [y0, y1] = cap(q(its.map((it) => lg(it.pf26)), this.base ? lg(this.base.pf26) : null), Math.log(0.5), Math.log(6));
    const minS = (a, c, s) => (c - a < s ? [(a + c) / 2 - s / 2, (a + c) / 2 + s / 2] : [a, c]);
    [x0, x1] = minS(x0, x1, 0.42); [y0, y1] = minS(y0, y1, 0.6);
    const px = (x1 - x0) * 0.09, py = (y1 - y0) * 0.08; x0 -= px; x1 += px; y0 -= py; y1 += py;
    this.dom = { x0, x1, y0, y1 };
    const nl = this.lanes.length, dz = nl > 1 ? Math.min(0.62, 3.4 / (nl - 1)) : 0;
    this.laneZ = new Map(this.lanes.map((f, i) => [f, ((nl - 1) / 2 - i) * dz]));
    const zf = Math.max(0.55, (nl - 1) / 2 * dz + 0.45); this.box = { zf, zb: -zf - 0.2 };
    const ex = (v, a, b) => Math.exp(clamp(lg(v), a, b));
    for (const it of its) {
      it.off = lg(it.pf21) < x0 || lg(it.pf21) > x1 || lg(it.pf26) < y0 || lg(it.pf26) > y1;
      it.tx = this.X(ex(it.pf21, x0, x1)); it.ty = this.Y(ex(it.pf26, y0, y1));
      it.tz = it.isBase ? 0 : (this.laneZ.get(it.fam) ?? 0) + (it.seed - 0.5) * Math.min(0.16, dz * 0.4 || 0.16);
    }
  }
  X(pf) { const d = this.dom; return (lg(pf) - d.x0) / (d.x1 - d.x0) * this.W - this.W / 2; }
  Y(pf) { const d = this.dom; return (lg(pf) - d.y0) / (d.y1 - d.y0) * this.H; }
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
    const n = this.items.length, dens = clamp(1.12 - n / 500, 0.78, 1.08);
    for (const sl of this.slots) {
      const it = sl.it, st = ST[it.status];
      sl.col.set(st.col).multiplyScalar(st.k);
      sl.size = it.isBase ? 0.5 : (0.17 + 0.07 * Math.sqrt(clamp(Number.isFinite(it.tpw) ? it.tpw : 2, 0.2, 9))) * dens;
      sl.alpha = it.status === 'rejected' ? 0.72 : 1;
      sl.linkA = it.isBase ? 0 : it.status === 'rejected' ? 0.45 : 1;
    }
  }
  writeStatic() {
    const n = this.slots.length; this.ensureCap(n);
    const S = this.stars.geometry.attributes, L = this.links.geometry.attributes;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], c = sl.col, it = sl.it, st = ST[it.status]; sl.idx = i;
      S.aCol.setXYZ(i, c.r, c.g, c.b); S.aMisc.setXYZW(i, it.slow && !it.isBase ? 1 : 0, st.pulse ? 1 : 0, it.seed, i); S.aSpike.setX(i, it.isBase ? 1 : st.pulse ? 0.45 : 0);
      for (let j = 0; j < 2; j++) { const k = i * 2 + j; L.aCol.setXYZ(k, c.r, c.g, c.b); L.aT.setX(k, j); L.aSeed.setX(k, it.seed); L.aId.setX(k, i); }
    }
    for (const a of [S.aCol, S.aMisc, S.aSpike, L.aCol, L.aT, L.aSeed, L.aId]) a.needsUpdate = true;
    this.stars.geometry.setDrawRange(0, n); this.links.geometry.setDrawRange(0, n * 2);
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
  }
  writeDynamic() {
    const n = this.slots.length, S = this.stars.geometry.attributes, L = this.links.geometry.attributes;
    const P = S.position.array, Z = S.aSize.array, A = S.aAlpha.array, LP = L.position.array, LA = L.aA.array;
    const b = this.baseSlot && !this.baseSlot.dead ? this.baseSlot.p : null;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], p = sl.p, o = i * 6;
      P[i * 3] = p.x; P[i * 3 + 1] = p.y; P[i * 3 + 2] = p.z;
      Z[i] = sl.size * sl.s; A[i] = sl.alpha * sl.a;
      LP[o + 3] = p.x; LP[o + 4] = p.y; LP[o + 5] = p.z;
      if (b) { LP[o] = b.x; LP[o + 1] = b.y; LP[o + 2] = b.z; } else { LP[o] = p.x; LP[o + 1] = p.y; LP[o + 2] = p.z; }
      LA[i * 2] = LA[i * 2 + 1] = b ? sl.linkA * sl.a : 0;
    }
    for (const at of [S.position, S.aSize, S.aAlpha, L.position, L.aA]) at.needsUpdate = true;
  }
  animate() {
    const now = this.lt; let busy = false, dead = false;
    for (const sl of this.slots) {
      if (sl.done) { dead ||= sl.dead; continue; }
      const k = sl.dur > 0 ? clamp((now - sl.t0) / sl.dur, 0, 1) : 1, p = sl.p;
      if (sl.mode === FLY) {
        if (sl.it.isBase) { p.copy(sl.p1); sl.s = k > 0 ? outBack(k) : 0; sl.a = smooth(Math.min(1, k * 2)); }
        else {
          const e = outCubic(k); p.lerpVectors(sl.p0, sl.p1, e); p.y += Math.sin(k * Math.PI) * 0.35;
          sl.s = k > 0 ? 0.5 + 0.5 * outBack(k) : 0; sl.a = smooth(Math.min(1, k * 3));
        }
      } else if (sl.mode === MOVE) {
        const e = smooth(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = sl.s0 + (1 - sl.s0) * e; sl.a = sl.a0 + (1 - sl.a0) * e;
      } else { const e = smooth(k); p.copy(sl.p0); sl.s = sl.s0 * (1 - e); sl.a = sl.a0 * (1 - e); }
      if (k >= 1) { sl.done = true; dead ||= sl.dead; } else busy = true;
    }
    if (!busy && dead) { this.slots = this.slots.filter((s) => !s.dead); this.writeStatic(); }
    this.writeDynamic();
    if (!busy) this.animating = false;
  }

  // ---------------------------------------------------------------- walls, planes, guides, labels
  frameScene() {
    const W = this.W, H = this.H, { zf, zb } = this.box, b = this.base, d = this.dom;
    const x0 = -W / 2 - M, x1 = W / 2 + M, top = H + 0.15, zF = zf + 0.25;
    this.wall.position.set(0, (FLOOR + top) / 2, zb); this.wall.scale.set(x1 - x0, top - FLOOR, 1);
    this.wU.uX.value.set(x0, x1); this.wU.uY.value.set(FLOOR, top);
    this.floor.position.set(0, FLOOR, (zb + zF) / 2); this.floor.scale.set(x1 - x0, zF - zb, 1);
    this.fU.uX.value.set(x0, x1); this.fU.uZ.value.set(zb, zF);
    const one = new THREE.Vector2(lg(1) > d.x0 && lg(1) < d.x1 ? this.X(1) : -1e3, lg(1) > d.y0 && lg(1) < d.y1 ? this.Y(1) : -1e3);
    if (lg(1) >= d.x1) one.x = 1e3; if (lg(1) >= d.y1) one.y = 1e3;
    this.wU.uOne.value.copy(one);
    const hasB = !!b; this.wU.uHasB.value = hasB ? 1 : 0;
    const bx = hasB ? b.tx : 0, by = hasB ? b.ty : 0; this.bx = bx; this.by = by;
    this.wU.uB.value.set(bx, by); this.fU.uBx.value = bx;
    this.vPlane.visible = this.hPlane.visible = hasB;
    if (hasB) {
      this.vPlane.position.set(bx, (FLOOR + top) / 2, (zb + zF) / 2); this.vPlane.scale.set(zF - zb, top - FLOOR, 1);
      this.vPlane.userData.U.uSplit.value = (by - FLOOR) / (top - FLOOR);
      this.hPlane.position.set(0, by, (zb + zF) / 2); this.hPlane.scale.set(x1 - x0, zF - zb, 1);
      this.hPlane.userData.U.uSplit.value = (bx - x0) / (x1 - x0);
    }
    // guides: PF ticks on the back wall + floor, family lanes, the baseline axis line through the depth, PF 1 lines
    const G = this.guides, vio = new THREE.Color('#8f86ff'), gold = new THREE.Color('#ffd98a'), mag = new THREE.Color('#ff4fd8');
    const xt = this.ticks(d.x0, d.x1, this.w > 560 ? 7 : 5), yt = this.ticks(d.y0, d.y1, this.h > 420 ? 6 : 5);
    for (const v of xt) { const x = this.X(v); G.seg(x, FLOOR, zb, x, top, zb, vio, v === 1 ? 0 : 0.09, 4).seg(x, FLOOR, zb, x, FLOOR, zF, vio, v === 1 ? 0 : 0.07, 4); }
    for (const v of yt) { const y = this.Y(v); G.seg(x0, y, zb, x1, y, zb, vio, v === 1 ? 0 : 0.09, 4); }
    G.seg(x0, FLOOR, zb, x0, top, zb, vio, 0.32); G.seg(x0, FLOOR, zb, x0, FLOOR, zF, vio, 0.22);
    for (const v of yt) { const y = this.Y(v); G.seg(x0 - 0.08, y, zb, x0 + 0.08, y, zb, vio, 0.6); }
    for (const [, z] of this.laneZ) G.seg(x0, FLOOR, z, x1, FLOOR, z, vio, 0.13, 3);
    if (one.x > -1e3 && one.x < 1e3) { G.seg(one.x, FLOOR, zb, one.x, top, zb, mag, 0.3, 5).seg(one.x, FLOOR, zb, one.x, FLOOR, zF, mag, 0.2, 5); }
    if (one.y > -1e3 && one.y < 1e3) G.seg(x0, one.y, zb, x1, one.y, zb, mag, 0.3, 5);
    if (hasB) { G.seg(bx, by, zb, bx, by, zF, gold, 0.55).seg(bx, FLOOR, zb, bx, FLOOR, zF, gold, 0.25).seg(bx, FLOOR, 0, bx, by, 0, gold, 0.18, 6); }
    G.commit();
    // camera anchors: the walls' corners + room for the labels
    this.anchors = new Float32Array(corners([], x0 - 0.35, x1 + 0.5, FLOOR - 0.2, top + 0.25, zb, zF + 0.3));
    this.T.set(0, (FLOOR + top) / 2, (zb + zF) / 2);
    this.labelsFor(xt, yt, x0, x1, top, zb, zF);
    this.legendFor();
  }
  ticks(l0, l1, maxN) {
    const cand = NICE.filter((v) => lg(v) >= l0 && lg(v) <= l1), gap = (l1 - l0) / maxN, kept = cand.includes(1) ? [1] : [];
    for (const v of cand) if (kept.every((k) => Math.abs(lg(v) - lg(k)) >= gap * 0.98)) kept.push(v);
    return kept.sort((a, b) => a - b);
  }
  labelsFor(xt, yt, x0, x1, top, zb, zF) {
    const defs = [], b = this.base, gold = '#ffe7a8';
    for (const v of xt) defs.push({ text: tickTxt(v), p: new THREE.Vector3(this.X(v), FLOOR, zF + 0.05), ay: 0, dy: 4, tick: 'x', color: v === 1 ? '#ff8ae0' : null });
    defs.push({ text: 'PF 2021-25 →', p: new THREE.Vector3(x1, FLOOR, zF + 0.05), ax: 1, ay: 0, dy: 17, cls: 't' });
    for (const v of yt) defs.push({ text: tickTxt(v), p: new THREE.Vector3(x0 - 0.12, this.Y(v), zb), ax: 1, avoid: true, color: v === 1 ? '#ff8ae0' : null });
    defs.push({ text: 'PF 2026 ↑', p: new THREE.Vector3(x0, top, zb), ax: 0, ay: 1, dy: -4, dx: -2, cls: 't', avoid: true });
    if (b) {
      defs.push({ html: `${esc(trunc(b.title, 26))}<br><em>PF ${fmtPf(b.pf26)} · ${fmtPf(b.pf21)}</em>`, at: () => (this.baseSlot && this.baseSlot.a > 0.5 ? this.baseSlot.p : null),
        ax: 0, ay: 1, dx: 14, dy: -10, cls: 'tag', color: gold, avoid: true, keep: true, alts: ALTS(14, 10) });
      defs.push({ text: 'better in both ↗', p: new THREE.Vector3(x1 - 0.06, top - 0.06, zb), ax: 1, ay: 0, dy: 2, cls: 't', color: '#4ef0b0', avoid: true,
        show: () => this.wU.uIn.value > 0.5 });
    }
    this.best.forEach((it, i) => {
      if (i >= (this.w < 520 ? 2 : 3)) return;
      const sl = this.byKey.get(it.key), st = ST[it.status];
      defs.push({ html: `${esc(trunc(it.title, this.w < 520 ? 20 : 28))}<br><em>PF ${fmtPf(it.pf26)} · ${fmtPf(it.pf21)}</em>`, at: () => (sl && !sl.dead && sl.a > 0.6 ? sl.p : null),
        ax: 0, ay: 1, dx: 10, dy: -8, cls: 'tag', color: st.css, avoid: true, keep: true, alts: ALTS(10, 8) });
    });
    for (const [f, z] of this.laneZ) defs.push({ text: f, p: new THREE.Vector3(x1 + 0.08, FLOOR, z), ax: 0, cls: 'h', avoid: true });
    this.setLabels(defs);
    const n = this.items.length;
    this.hint.textContent = n ? `${n} run${n === 1 ? '' : 's'}${this.unscored ? ` · ${this.unscored} not scored` : ''}` + (n === 1 ? ' · new experiments land here' : ' · tap a star') : '';
  }
  legendFor() {
    if (!this.items.length) { this.legend.innerHTML = ''; return; }
    const cnt = {}; for (const it of this.items) cnt[it.status] = (cnt[it.status] || 0) + 1;
    const slow = this.items.some((it) => it.slow && !it.isBase);
    this.legend.innerHTML = ORDER.filter((s) => cnt[s] || s === 'baseline').map((s) => {
      const st = ST[s], c = st.css;
      return `<span><i style="background:${c};box-shadow:0 0 6px ${c}${s === 'rejected' ? ';opacity:.7' : ''}"></i>${st.label}${s === 'baseline' ? '' : ' <b>' + (cnt[s] || 0) + '</b>'}</span>`;
    }).join('') + (slow ? '<span><i style="background:transparent;box-shadow:inset 0 0 0 1.5px rgba(230,232,255,.75)"></i>under 2/wk</span>' : '')
      + (this.base ? '<span><i style="width:12px;height:6px;border-radius:2px;background:linear-gradient(90deg,rgba(46,229,157,.15),rgba(46,229,157,.7))"></i>better in both</span>' : '');
    if (this.w > 10) this.relayoutRegion();
  }
  relayoutRegion() { const lh = this.legend.isConnected ? this.legend.offsetHeight : 14; this.region = [-1, 1, -1 + 2 * 18 / this.h, 1 - 2 * (lh + 14) / this.h]; }
  attach(el) { super.attach(el); this.relayoutRegion(); }

  // ---------------------------------------------------------------- picking + tooltip
  nearest(px, py, maxPx) {
    const cam = this.camera; _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    let best = null, bd = maxPx * maxPx;
    for (const sl of this.slots) {
      if (sl.dead || sl.a < 0.3) continue;
      _v.copy(sl.p).applyMatrix4(_m); if (_v.z > 1) continue;
      const dx = (_v.x + 1) / 2 * this.w - px, dy = (1 - _v.y) / 2 * this.h - py, d = dx * dx + dy * dy - (sl.it.isBase ? 60 : 0);
      if (d < bd) { bd = d; best = sl; }
    }
    return best;
  }
  pickAt(px, py) {
    const sl = this.nearest(px, py, 24);
    this.select(sl);
    if (sl) this.emit(sl.it.run);
  }
  devTapPoint() { const sl = this.slots.find((s) => !s.dead && s.a > 0.5 && !s.it.isBase) || this.baseSlot; if (!sl) return null; const p = this.screen(sl.p); return [p.x, p.y]; }
  select(sl) { this.sel = sl; this.selAt = this.lt; this.u.uSel.value = sl ? sl.idx : -1; this.tipFor(this.hov || sl); }
  hoverAt(sl) {
    if (sl === this.hov) return;
    this.hov = sl; this.u.uHov.value = sl ? sl.idx : -1; this.canvas.style.cursor = sl ? 'pointer' : 'grab';
    this.tipFor(sl || this.sel);
  }
  tipFor(sl) {
    if (!sl) { this.showTip(null); return; }
    const it = sl.it, r = it.run, st = ST[it.status];
    const tpw = (v) => (Number.isFinite(num(v)) ? num(v).toFixed(1) + '/wk' : '—');
    const row = (lbl, pf, net, tp) => `<i>${lbl}</i> PF <b>${fmtPf(pf)}</b> · ${fmtK(num(net))} · ${tpw(tp)}`;
    const small = this.w < 480;
    let html = `<b>${esc(trunc(it.title, small ? 30 : 38))}</b><u style="color:${st.css}">${st.label}</u>${it.off && !small ? ' <i>(off the scale, pinned to the edge)</i>' : ''}<br>`;
    if (small) html += `<i>PF</i> <b>${fmtPf(it.pf26)}</b> <i>2026 ·</i> <b>${fmtPf(it.pf21)}</b> <i>21-25 ·</i> ${tpw(Number.isFinite(it.tpw) ? it.tpw : NaN)}`;
    else {
      html += `${row('2026', it.pf26, r.net26, r.tpw26)}<br>${row('2021-25', it.pf21, r.net21, r.tpw21)}`;
      if (Number.isFinite(num(r.dd21))) html += ` · DD ${fmtK(num(r.dd21))}`;
      if (Number.isFinite(num(r.p20_21))) html += `<br><i>eval in 1 month</i> <b style="color:#5eead4">${pct(num(r.p20_21))}</b> pass · <b style="color:#ff7ad9">${pct(num(r.f20_21))}</b> fail`;
    }
    if (this.base && !it.isBase) {
      const b = this.base, up = it.pf26 > b.pf26 && it.pf21 > b.pf21;
      html += `<br><i>vs baseline</i> ${up ? '<b style="color:#4ef0b0">better in both periods</b>' : it.pf26 > b.pf26 ? 'better in 2026 only' : it.pf21 > b.pf21 ? 'better in 2021-25 only' : 'worse in both'}`;
    }
    this.showTip(sl.key, html);
  }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const moved = this.camStep(dt); u.uFocus.value = this.L;
    if (this.animating) this.animate();
    // intro: flash on the baseline, then the quadrant and planes light up
    const b = this.baseSlot && !this.baseSlot.dead ? this.baseSlot : null;
    if (this.introAt >= 0) {
      const k = (lt - this.introAt) / 2.4;
      this.flash.visible = k < 0.6 && !!b; if (b) { this.flash.position.copy(b.p); this.flash.scale.setScalar(0.5 + k * 6); this.flash.material.opacity = Math.max(0, 1 - k * 1.8) * 0.85; }
      this.wU.uIn.value = clamp((k - 0.35) * 1.6, 0, 1);
      if (k >= 1) { this.introAt = -1; this.flash.visible = false; this.camKey = ''; }
    } else if (!this.introDone) this.wU.uIn.value = 1;
    const pa = this.base ? this.wU.uIn.value : 0;
    this.vPlane.userData.U.uA.value = this.hPlane.userData.U.uA.value = pa;
    // baseline: halo, slow crown, sonar ping
    if (b && b.a > 0.05) {
      const br = Q.reduced ? 1 : 1 + 0.06 * Math.sin(lt * 2.2);
      this.halo.visible = this.crown.visible = this.ping.visible = true;
      this.halo.position.copy(b.p); this.halo.scale.setScalar(1.25 * b.s * br); this.halo.material.opacity = 0.32 * b.a;
      this.crown.position.copy(b.p); this.crown.scale.setScalar(0.58 * b.s); this.crown.material.rotation = Q.reduced ? 0 : -lt * 0.35; this.crown.material.opacity = 0.55 * b.a;
      const ph = Q.reduced ? 0.35 : fract(lt * 0.4);
      this.ping.position.copy(b.p); this.ping.scale.setScalar(0.4 + ph * 1.5); this.ping.material.opacity = (1 - ph) * 0.5 * b.a;
    } else this.halo.visible = this.crown.visible = this.ping.visible = false;
    // selection reticle
    const s = this.sel;
    if (s && !s.dead) {
      const pulse = Q.reduced ? 1 : 1 + 0.07 * Math.sin(lt * 5);
      this.reticle.visible = true; this.reticle.position.copy(s.p); this.reticle.scale.setScalar(Math.max(0.42, s.size * 1.6) * pulse);
      this.reticle.material.rotation = Q.reduced ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95;
    } else this.reticle.visible = false;
    // html
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.nearest(hx, hy, 16)); }
    if (moved || this.animating || this.introAt >= 0) this.placeLabels();
    const ts = this.hov || this.sel;
    if (ts && this.tipKey != null) { const p = this.screen(ts.p); this.placeTip(p.x, p.y, 16); }
  }
}
