// Eval Reactor (MFFU eval gauge): the account as a reactor core.
//   Outer ring = progress from the start balance to the profit target (green energy arc from 12 o'clock, clockwise; a
//   magenta counter-arc while the balance is under the start), middle ring = cushion above the trailing max-loss floor
//   (magenta, full = the whole max-loss allowance), inner ring = today's loss-limit use (amber -> red; a green sliver on a
//   winning day). The plasma core's colour and heartbeat follow health: calm cyan-green when safe, violet, then a fast
//   red pulse near the floor or the daily limit. PASS turns it gold with shock waves; FAIL dims it to a slow red flicker.
//   Energy particles spiral into the core inside a rotating containment cage; a light column runs through it.
//   Big numbers in an HTML overlay: balance (counts to new values), profit vs start, status chip, one line per ring.
//   Drag to tilt (it sways by itself when idle); tap -> opts.onPick(data).
// setData({ balance, start: 50000, target: 53000, floor, locked, dayPnl, dayLimit: 1000, status, maxLoss: 2000 })
//   floor = trailing max-loss level (default start - maxLoss); locked = the floor stopped trailing; status: any word —
//   pass* (gold, shock waves), fail* / breach (dim red), stop* / halt / limit (daily limit hit: amber, low energy),
//   open / active / live (cyan). Under 250 px tall the overlay is compact: rings, balance and status only.
// Draw calls ~15; particles: 700 accretion sparks (260 lite) + 500 dust (200 lite).
import { THREE, Q, glowTexture, POINT_FRAG, count, rng, Hud, addBackdrop, addNebula, addDust, additive, attrs, paintBackdrop,
  clamp, lerp, outCubic, fract, num, esc, fmtUsd, pct, div, injectStyle } from './hud.js';

const RINGS = [{ r0: 1.5, r1: 1.66, seg: 40 }, { r0: 1.24, r1: 1.37, seg: 32 }, { r0: 1.0, r1: 1.08, seg: 24 }];
const HEALTH = [[0, '#ff2b55'], [0.35, '#ff8a3d'], [0.62, '#a855f7'], [1, '#2ee5c8']];
const GOLD = new THREE.Color('#ffd36b'), RED = new THREE.Color('#ff2b55');
const _c = new THREE.Color(), _c2 = new THREE.Color(), _v = new THREE.Vector3();
function healthColor(h, out) {
  for (let i = 1; i < HEALTH.length; i++) if (h <= HEALTH[i][0]) { const [a, ca] = HEALTH[i - 1], [b, cb] = HEALTH[i]; return out.set(ca).lerp(_c2.set(cb), (h - a) / (b - a)); }
  return out.set(HEALTH[HEALTH.length - 1][1]);
}

// ------------------------------------------------------------------ shaders
const CORE_V = `varying vec3 vN; varying vec3 vV; varying vec3 vP;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); vP = position; gl_Position = projectionMatrix * mv; }`;
const CORE_F = `uniform vec3 uCol; uniform vec3 uCol2; uniform float uTime; uniform float uBeat; uniform float uMotion; uniform float uDim;
varying vec3 vN; varying vec3 vV; varying vec3 vP;
void main(){
  float t = uTime * uMotion; vec3 p = vP * 3.2;
  float n = sin(p.x * 1.7 + t * 1.1) * sin(p.y * 2.1 - t * 0.9) * sin(p.z * 1.9 + t * 0.7);
  n += 0.55 * sin(p.x * 4.3 - t * 1.7 + p.y * 2.0) * sin(p.z * 3.7 + t * 1.3);
  float bands = clamp(0.5 + 0.5 * n, 0.0, 1.0);
  float f = 1.0 - max(dot(vN, vV), 0.0), rim = pow(f, 2.2);
  vec3 c = mix(uCol2, uCol, bands) * (0.45 + 0.65 * uBeat) + uCol * rim * 1.5 + vec3(1.0) * pow(1.0 - f, 5.0) * 0.55 * uBeat;
  gl_FragColor = vec4(c * uDim, 1.0);
}`;
const RING_V = `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const RING_F = `uniform float uR0; uniform float uR1; uniform float uFrac; uniform float uNeg; uniform vec3 uCol; uniform vec3 uNegCol; uniform vec3 uTrack;
uniform float uSeg; uniform float uTime; uniform float uMotion; uniform float uFlash; uniform float uA;
varying vec2 vP;
void main(){
  float r = length(vP), rr = clamp((r - uR0) / (uR1 - uR0), 0.0, 1.0);
  float a = fract(atan(vP.x, vP.y) / 6.2831853 + 1.0);
  float seg = fract(a * uSeg), gap = smoothstep(0.0, 0.07, seg) * smoothstep(1.0, 0.88, seg);
  float prof = exp(-pow((rr - 0.5) * 3.0, 2.0)), edge = exp(-pow((rr - 0.5) * 9.0, 2.0));
  float lit = step(a, uFrac) * step(0.0005, uFrac), neg = step(1.0 - uNeg, a) * step(0.0005, uNeg);
  float t = uTime * uMotion;
  float shimmer = exp(-pow((fract(a * 1.5 - t * 0.14) - 0.5) * 9.0, 2.0)) * 0.6;
  float head = exp(-pow((a - uFrac) * 50.0, 2.0)) * step(0.0005, uFrac) * step(uFrac, 0.999);
  vec3 c = uTrack * (0.06 + 0.1 * edge) * gap;
  c += uCol * lit * gap * (prof * 0.75 + edge * 0.6) * (1.0 + shimmer) * (1.0 + uFlash);
  c += uNegCol * neg * gap * (prof * 0.65 + edge * 0.5) * (1.0 + uFlash);
  c += mix(uCol, vec3(1.0), 0.6) * head * prof * 1.8;
  gl_FragColor = vec4(c * uA, 1.0);
}`;
// outer bezel: fine ticks, majors at 25 / 50 / 75 %, a slowly turning scanner
const BEZEL_F = `uniform vec3 uCol; uniform float uTime; uniform float uMotion; varying vec2 vP;
void main(){
  float r = length(vP), rr = clamp((r - 1.76) / 0.1, 0.0, 1.0);
  float a = fract(atan(vP.x, vP.y) / 6.2831853 + 1.0);
  float tick = step(0.8, fract(a * 80.0)) * step(0.45, rr), major = step(0.985, fract(a * 4.0 + 0.0075));
  float scan = exp(-pow((fract(a - uTime * 0.05 * uMotion) - 0.5) * 6.0, 2.0)) * 0.5 * uMotion;
  float line = exp(-pow((rr - 0.08) * 22.0, 2.0));
  gl_FragColor = vec4(uCol * (line * (0.35 + scan) + tick * 0.22 * (1.0 + scan * 2.0) + major * 0.9), 1.0);
}`;
const SPIRAL_V = `attribute float aSeed; attribute float aR; attribute float aS;
uniform float uTime; uniform float uFlowT; uniform float uPix; uniform vec3 uCol; uniform float uMotion; uniform float uBright;
varying vec3 vColor; varying float vAlpha;
void main(){
  float t = uTime * uMotion;
  float ph = fract(aSeed * 7.31 + uFlowT * (0.6 + aR * 0.8));
  float r = mix(2.1, 0.6, pow(ph, 0.85));
  float ang = aSeed * 6.2831 + ph * (3.0 + aR * 3.5) + t * 0.08;
  vec3 p = vec3(sin(ang) * r, cos(ang) * r, sin(aSeed * 40.0 + t) * 0.07 * r);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp(aS * uPix * (0.55 + ph * 0.8) / -mv.z, 0.0, 22.0);
  gl_Position = projectionMatrix * mv;
  vColor = mix(uCol, vec3(1.0), ph * ph * 0.55) * uBright; vAlpha = smoothstep(0.0, 0.15, ph) * (1.0 - smoothstep(0.86, 1.0, ph));
}`;
const DOT_V = `attribute vec3 aCol; attribute float aSize; attribute float aA; uniform float uPix;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(aSize * uPix / -mv.z, 0.0, 90.0); gl_Position = projectionMatrix * mv; vColor = aCol; vAlpha = aA; }`;
const BEAM_V = `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`;
const BEAM_F = `uniform vec3 uCol; uniform float uTime; uniform float uMotion; uniform float uA; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
void main(){
  float f = 1.0 - abs(dot(vN, vV)); float y = abs(vUv.y - 0.5) * 2.0; float fade = pow(1.0 - y, 1.6);
  float stripes = 0.6 + 0.4 * sin(vUv.y * 46.0 - uTime * 3.0 * uMotion * sign(vUv.y - 0.5));
  gl_FragColor = vec4(uCol * (0.1 + f * f * 0.9) * fade * stripes * uA, 1.0);
}`;

const CSS = `.fxr-c{position:absolute;left:0;top:0;text-align:center;white-space:nowrap;line-height:1}
.fxr-bal{font-size:26px;font-weight:800;letter-spacing:-.01em;color:#fff;text-shadow:0 0 16px rgba(5,3,14,.95),0 0 4px rgba(5,3,14,.95),0 0 26px rgba(0,0,0,.6)}
.fxr-sub{margin-top:4px;font-size:11px;font-weight:700;letter-spacing:.01em;text-shadow:0 0 8px rgba(5,3,14,.95),0 0 3px rgba(5,3,14,.95)}
.fxr-cap{margin-bottom:5px;font-size:8.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(214,218,250,.62);text-shadow:0 0 6px #07080c}
.fxr-chip{position:absolute;right:10px;top:9px;display:flex;gap:6px;align-items:center}
.fxr-chip b{font-size:10px;font-weight:800;letter-spacing:.09em;padding:4px 9px;border-radius:999px;border:1px solid currentColor;background:rgba(10,8,24,.62);box-shadow:0 0 12px -2px currentColor}
.fxr-chip em{font-style:normal;font-size:9px;font-weight:700;letter-spacing:.04em;color:rgba(214,218,250,.66)}
.fxr-stats{position:absolute;left:10px;right:10px;bottom:9px;display:grid;gap:5px}
.fxr-row{display:flex;align-items:center;gap:7px;font-size:11px;font-weight:600;line-height:1.15;color:rgba(214,218,250,.72);white-space:nowrap;overflow:hidden}
.fxr-row i{flex:none;width:8px;height:8px;border-radius:50%}
.fxr-row span{flex:none;width:60px;font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:rgba(188,192,236,.6)}
.fxr-row b{font-weight:800;color:#eef0fb}.fxr-row em{font-style:normal;color:rgba(188,192,236,.62);overflow:hidden;text-overflow:ellipsis}
.fxr-row.warn b{color:#ff7a9a}
.fxh-reactor.wide .fxr-stats{left:auto;right:16px;top:50%;bottom:auto;transform:translateY(-50%);width:min(250px,40%);gap:9px}
.fxh-reactor.wide .fxr-row{font-size:12px}
.fxh-reactor .fxh-empty{top:auto;bottom:16px;transform:translateX(-50%)}
.fxh-reactor.compact .fxr-stats{display:none}.fxh-reactor.compact .fxr-bal{font-size:20px}.fxh-reactor.compact .fxr-cap{display:none}
.fxh-reactor.compact .fxr-sub{font-size:10px}.fxh-reactor.compact .fxr-chip{top:7px;right:8px}`;

// ------------------------------------------------------------------ the view
export class Reactor extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'reactor', fov: 34, empty: 'No eval data yet', orbit: { yaw: 0, pitch: 0.06, auto: 0, min: -0.55, max: 0.55, pitchMin: -0.25, pitchMax: 0.45 } });
    injectStyle('fxh-rct-css', CSS);
    this.d = null; this.cur = { prog: 0, neg: 0, cush: 0, day: 0, dayWin: 0, health: 0.75, bal: 0, pass: 0, fail: 0 }; this.want = { ...this.cur };
    this.balFrom = 0; this.balTo = 0; this.balAt = -9; this.beatPh = 0; this.waveAt = -9; this.waveCol = new THREE.Color('#2ee59d'); this.nextWave = 0;
    this.col = new THREE.Color('#2ee5c8'); this.sig = null; this.hasData = false;
    Object.assign(this.u, { uFlowT: { value: 0 }, uCol: { value: new THREE.Color('#2ee5c8') }, uBright: { value: 1 } });
    this.build();
    this.buildHtml();
  }
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.52]);
    addNebula(S, [['#6d28d9', -3.5, 2.2, -6, 9, 6, 0.1], ['#ff2bd6', 3.2, -1.6, -6, 8, 5, 0.05]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 420 : 500, 200), box: [4, 3, 2], cy: 0, seed: 41 });
    this.g = new THREE.Group(); this.g.rotation.x = -0.32; S.add(this.g);
    // light column through the core
    this.bmU = { uCol: { value: new THREE.Color('#a78bfa') }, uTime: u.uTime, uMotion: u.uMotion, uA: { value: 0.6 } };
    const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 5.2, 24, 1, true), additive(BEAM_V, BEAM_F, this.bmU, { side: THREE.DoubleSide }));
    beam.renderOrder = 2; this.g.add(beam);
    // core: plasma sphere + glow
    this.cU = { uCol: { value: new THREE.Color('#2ee5c8') }, uCol2: { value: new THREE.Color('#5b21b6') }, uTime: u.uTime, uBeat: { value: 0.5 }, uMotion: u.uMotion, uDim: { value: 1 } };
    this.core = new THREE.Mesh(new THREE.SphereGeometry(0.5, 48, 32), new THREE.ShaderMaterial({ uniforms: this.cU, vertexShader: CORE_V, fragmentShader: CORE_F }));
    this.core.renderOrder = 3; this.g.add(this.core);
    const spr = (scale, op, order) => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color('#2ee5c8'), transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false })); s.scale.setScalar(scale); s.renderOrder = order; this.g.add(s); return s; };
    this.glowIn = spr(1.9, 0.55, 9); this.glowOut = spr(5.2, 0.16, 1);
    // containment cage
    const cage = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(0.78, 1)), new THREE.LineBasicMaterial({ color: new THREE.Color('#8b5cf6'), transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    cage.renderOrder = 4; this.cage = cage; this.g.add(cage);
    // rings
    this.rings = RINGS.map((R, i) => {
      const U = { uR0: { value: R.r0 }, uR1: { value: R.r1 }, uFrac: { value: 0 }, uNeg: { value: 0 }, uCol: { value: new THREE.Color(['#2ee59d', '#ff2bd6', '#ffb347'][i]) },
        uNegCol: { value: new THREE.Color(['#ff2bd6', '#ff2bd6', '#2ee59d'][i]) }, uTrack: { value: new THREE.Color(['#5b8cff', '#a855f7', '#8b5cf6'][i]) }, uSeg: { value: R.seg },
        uTime: u.uTime, uMotion: u.uMotion, uFlash: { value: 0 }, uA: { value: 1 } };
      const m = new THREE.Mesh(new THREE.RingGeometry(R.r0, R.r1, 192, 1), additive(RING_V, RING_F, U, { side: THREE.DoubleSide })); m.renderOrder = 5 + i; m.userData.U = U; this.g.add(m); return m;
    });
    this.bzU = { uCol: { value: new THREE.Color('#7c6cff') }, uTime: u.uTime, uMotion: u.uMotion };
    const bezel = new THREE.Mesh(new THREE.RingGeometry(1.76, 1.86, 240, 1), additive(RING_V, BEZEL_F, this.bzU, { side: THREE.DoubleSide })); bezel.renderOrder = 4; this.g.add(bezel);
    // spiral sparks + ring heads
    const N = count(Q.phone ? 560 : 700, 260), sg = attrs(N, { position: [3], aSeed: [1], aR: [1], aS: [1] }), rnd = rng(99);
    for (let i = 0; i < N; i++) { sg.attributes.aSeed.setX(i, rnd()); sg.attributes.aR.setX(i, rnd()); sg.attributes.aS.setX(i, 0.018 + rnd() * 0.03); }
    this.spiral = new THREE.Points(sg, additive(SPIRAL_V, POINT_FRAG, u)); this.spiral.renderOrder = 8; this.g.add(this.spiral);
    const hg = attrs(4, { position: [3, 1], aCol: [3, 1], aSize: [1, 1], aA: [1, 1] });
    this.heads = new THREE.Points(hg, additive(DOT_V, POINT_FRAG, u)); this.heads.renderOrder = 10; this.g.add(this.heads);
    // shock wave
    this.wave = new THREE.Mesh(new THREE.RingGeometry(0.94, 1, 128, 1), new THREE.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    this.wave.renderOrder = 11; this.wave.visible = false; this.g.add(this.wave);
    S.traverse((o) => { o.frustumCulled = false; });
    // camera anchors: the bezel circle
    const P = [];
    for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2; _v.set(Math.sin(a) * 1.9, Math.cos(a) * 1.9, 0).applyEuler(this.g.rotation); P.push(_v.x, _v.y, _v.z); }
    P.push(0, 0, 0.6, 0, 0, -0.6);
    this.anchors = new Float32Array(P); this.T.set(0, 0, 0); this.fill = [0.9, 0.9];
  }
  buildHtml() {
    const ui = this.ui;
    this.cen = div('fxr-c', ui, '<div class="fxr-cap">balance</div><div class="fxr-bal">—</div><div class="fxr-sub"></div>');
    this.balEl = this.cen.querySelector('.fxr-bal'); this.subEl = this.cen.querySelector('.fxr-sub');
    this.chip = div('fxr-chip', ui);
    this.stats = div('fxr-stats', ui);
  }
  retheme() { paintBackdrop(this.bgU); }
  relayout(w, h) {
    // compact (a short card, e.g. a Today-page mini reactor): rings + balance + chip only, the page shows the numbers
    const compact = h < 250, wide = !compact && w / h > 1.45 && w > 520;
    this.ui.classList.toggle('wide', wide); this.ui.classList.toggle('compact', compact);
    const sh = this.stats.isConnected ? this.stats.offsetHeight : 64, sw = this.stats.isConnected ? this.stats.offsetWidth : 240;
    this.region = compact ? [-1, 1, -1 + 2 * 8 / h, 1 - 2 * 8 / h] : wide ? [-1, 1 - 2 * (sw + 30) / w, -1 + 2 * 12 / h, 1 - 2 * 12 / h] : [-1, 1, -1 + 2 * (sh + 14) / h, 1 - 2 * 30 / h];
    if (this.balTxt) { this.cenW = this.cen.offsetWidth; this.cenH = this.cen.offsetHeight; this.cenLast = null; }
    this.Lset = false;
  }
  attach(el) { super.attach(el); this.relayout(this.w, this.h); }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' ? d : {};
    const start = num(src.start, 50000), target = num(src.target, start + 3000), maxLoss = num(src.maxLoss ?? src.mll, 2000);
    const bal = num(src.balance), floor = num(src.floor, start - maxLoss), dayPnl = num(src.dayPnl, 0), dayLimit = Math.max(1, num(src.dayLimit, 1000));
    const status = String(src.status ?? '').trim(), locked = !!src.locked;
    const sig = [bal, start, target, floor, dayPnl, dayLimit, status, locked, maxLoss].join('|');
    this.d = d;
    if (sig === this.sig) return;
    this.sig = sig;
    const has = Number.isFinite(bal);
    const pass = /pass/i.test(status), fail = /fail|breach|blown|lost/i.test(status), stopped = !pass && !fail && /stop|halt|pause|limit/i.test(status);
    const prog = has ? clamp((bal - start) / Math.max(1, target - start), 0, 1) : 0, neg = has ? clamp((start - bal) / Math.max(1, maxLoss), 0, 1) : 0;
    const cush = has ? clamp((bal - floor) / Math.max(1, maxLoss), 0, 1) : 0, day = clamp(-dayPnl / dayLimit, 0, 1), dayWin = clamp(dayPnl / dayLimit, 0, 1);
    let health = !has ? 0.62 : pass ? 1 : fail ? 0 : clamp(Math.min(1, cush / 0.6) * (1 - 0.8 * clamp((day - 0.3) / 0.7, 0, 1)), 0, 1);
    if (stopped) health = Math.min(health, 0.36);   // daily limit hit: done for the day
    this.want = { prog, neg, cush, day, dayWin, health, pass: pass ? 1 : 0, fail: fail ? 1 : 0 };
    if (Q.reduced || !this.hasData) Object.assign(this.cur, this.want, { prog: Q.reduced ? prog : 0, cush: Q.reduced ? cush : 0, day: Q.reduced ? day : 0, neg: Q.reduced ? neg : 0, dayWin: Q.reduced ? dayWin : 0 });
    // balance counter + a shock wave on a change of balance
    if (has) {
      const fromBal = this.hasData && Number.isFinite(this.balTo) ? this.dispBal() : start;
      this.balFrom = fromBal; this.balTo = bal; this.balAt = this.lt;
      if (this.hasData && Math.abs(bal - fromBal) >= 1 && !Q.reduced) { this.waveAt = this.lt; this.waveCol.set(bal > fromBal ? '#2ee59d' : '#ff2bd6'); }
    }
    this.hasData = has; this.info = { start, target, maxLoss, bal, floor, dayPnl, dayLimit, status, locked, pass, fail, stopped };
    this.writeHtml();
    this.empty.style.display = has ? 'none' : 'block';
    this.cen.style.visibility = has ? 'visible' : 'hidden';
    this.ui.classList.add('on');
    this.relayout(this.w, this.h);
  }
  dispBal() { const k = Q.reduced ? 1 : clamp((this.lt - this.balAt) / 1.1, 0, 1); return this.balFrom + (this.balTo - this.balFrom) * outCubic(k); }
  writeHtml() {
    const I = this.info, W = this.want;
    if (!I || !Number.isFinite(I.bal)) { this.chip.innerHTML = ''; this.stats.innerHTML = ''; return; }
    const stCol = I.pass ? '#ffd36b' : I.fail ? '#ff5a7a' : I.stopped ? '#ffb347' : /open|live|active|running|progress/i.test(I.status) || !I.status ? '#67e8f9' : '#c4b5fd';
    this.chip.innerHTML = (I.locked ? '<em>floor locked</em>' : '') + `<b style="color:${stCol}">${esc((I.status || 'OPEN').toUpperCase().slice(0, 14))}</b>`;
    const prof = I.bal - I.start, toGo = Math.max(0, I.target - I.bal), cushion = I.bal - I.floor;
    this.subEl.innerHTML = I.pass ? '<span style="color:#ffd36b">target reached</span>'
      : `<span style="color:${prof >= 0 ? '#4ef0b0' : '#ff7ad9'}">${fmtUsd(prof)}</span> <span style="color:rgba(214,218,250,.6)">· ${pct(W.prog * 100)} to target</span>`;
    const dayTxt = I.dayPnl < 0 ? fmtUsd(I.dayPnl) : I.dayPnl > 0 ? fmtUsd(I.dayPnl) : '$0';
    this.stats.innerHTML = [
      ['#2ee59d', 'target', I.pass ? 'reached' : fmtUsd(toGo, false) + ' to go', 'of ' + fmtUsd(I.target, false), false],
      ['#ff2bd6', 'cushion', fmtUsd(cushion, false), 'above ' + fmtUsd(I.floor, false) + (I.locked ? ' (locked)' : ''), W.cush < 0.25 && !I.pass],
      [I.dayPnl > 0 ? '#2ee59d' : '#ffb347', 'today', dayTxt, I.dayPnl < 0 ? 'of ' + fmtUsd(-I.dayLimit) + ' limit' : 'limit ' + fmtUsd(-I.dayLimit), W.day > 0.7],
    ].map(([c, k, b, e, warn]) => `<div class="fxr-row${warn ? ' warn' : ''}"><i style="background:${c};box-shadow:0 0 8px ${c}"></i><span>${k}</span><b>${b}</b><em>${esc(e)}</em></div>`).join('');
  }

  // ---------------------------------------------------------------- picking
  pickAt() { if (this.d && this.hasData) { this.waveAt = this.lt; this.waveCol.copy(this.col); this.emit(this.d); } }
  devTapPoint() { const p = this.screen(_v.set(0, 0, 0)); return [p.x, p.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u, red = Q.reduced;
    u.uTime.value = lt;
    // idle sway + drag (yaw only, pitch on mouse), then frame
    const o = this.orbit;
    if (!o.dragging && o.idle > 2.5 && !red) { o.yaw += (Math.sin(lt * 0.27) * 0.16 - o.yaw) * Math.min(1, dt * 0.5); o.pitch += (0.06 + Math.sin(lt * 0.19) * 0.05 - o.pitch) * Math.min(1, dt * 0.5); }
    const moved = this.camStep(dt);
    // ease the arcs and health toward the data
    const c = this.cur, w = this.want, k = red ? 1 : Math.min(1, dt * 2.4);
    for (const key of ['prog', 'neg', 'cush', 'day', 'dayWin', 'health', 'pass', 'fail']) c[key] += (w[key] - c[key]) * k;
    const pass = c.pass, fail = c.fail;
    healthColor(clamp(c.health, 0, 1), this.col);
    if (pass > 0.01) this.col.lerp(GOLD, pass);
    if (fail > 0.01) this.col.lerp(RED, fail);
    // heartbeat: slow and soft when safe, quick and hard near the edge
    const rate = lerp(2.5, 0.55, clamp(c.health, 0, 1)) * (fail > 0.5 ? 0.4 : 1);
    this.beatPh += dt * rate * (red ? 0 : 1);
    const ph = fract(this.beatPh), beat = red ? 0.6 : Math.pow(Math.max(0, Math.sin(ph * Math.PI * 2)), 3) * 0.7 + Math.pow(Math.max(0, Math.sin((ph - 0.18) * Math.PI * 2)), 6) * 0.35 + 0.35;
    const flick = fail > 0.5 && !red ? 0.65 + 0.35 * (Math.sin(lt * 23) * Math.sin(lt * 7.3) > 0.2 ? 1 : 0.4) : 1;
    this.cU.uCol.value.copy(this.col).multiplyScalar(1.15); this.cU.uCol2.value.copy(this.col).lerp(_c.set('#3b0d7a'), 0.7);
    this.cU.uBeat.value = beat; this.cU.uDim.value = (this.hasData ? 1 : 0.55) * (1 - fail * 0.45) * flick;
    this.glowIn.material.color.copy(this.col); this.glowIn.material.opacity = (0.32 + 0.3 * beat) * (1 - fail * 0.5) * flick;
    const gs = 1.6 + 0.35 * beat; this.glowIn.scale.setScalar(gs);
    this.glowOut.material.color.copy(this.col); this.glowOut.material.opacity = 0.1 + 0.08 * beat;
    this.bmU.uCol.value.copy(this.col).lerp(_c.set('#a78bfa'), 0.5); this.bmU.uA.value = (this.hasData ? 0.55 : 0.25) * (1 - fail * 0.6);
    this.cage.rotation.y += dt * 0.18 * (red ? 0 : 1) * (0.6 + (1 - c.health)); this.cage.rotation.x += dt * 0.07 * (red ? 0 : 1);
    this.cage.material.color.copy(this.col).lerp(_c.set('#8b5cf6'), 0.55);
    u.uCol.value.copy(this.col); u.uFlowT.value += dt * lerp(0.42, 0.1, clamp(c.health, 0, 1)) * (fail > 0.5 ? 0.3 : 1) * (red ? 0 : 1); u.uBright.value = (this.hasData ? 1 : 0.5) * (1 - fail * 0.5);
    // rings
    const [r0, r1, r2] = this.rings.map((m) => m.userData.U);
    r0.uFrac.value = pass > 0.5 ? 1 : c.prog; r0.uNeg.value = 0;   // under the start: the cushion ring tells that story r0.uCol.value.set('#2ee59d').lerp(GOLD, pass);
    r1.uFrac.value = c.cush; r1.uCol.value.set('#ff2bd6').lerp(GOLD, pass * 0.6);
    const danger1 = c.cush < 0.25 && pass < 0.5 && this.hasData ? 1 : 0;
    r1.uFlash.value = danger1 && !red ? 0.6 * Math.max(0, Math.sin(lt * 6)) : 0;
    r2.uFrac.value = c.day; r2.uNeg.value = c.dayWin; r2.uCol.value.set('#ffb347').lerp(_c.set('#ff2b55'), clamp((c.day - 0.5) / 0.5, 0, 1));
    r2.uFlash.value = c.day > 0.7 && !red ? 0.6 * Math.max(0, Math.sin(lt * 7)) : 0;
    for (const U of [r0, r1, r2]) U.uA.value = (this.hasData ? 1 : 0.45) * (1 - fail * 0.5);
    // ring heads
    const H = this.heads.geometry.attributes;
    [[r0.uFrac.value, RINGS[0], r0.uCol.value], [r1.uFrac.value, RINGS[1], r1.uCol.value], [r2.uFrac.value, RINGS[2], r2.uCol.value]].forEach(([f, R, col], i) => {
      const a = f * Math.PI * 2, rr = (R.r0 + R.r1) / 2;
      H.position.setXYZ(i, Math.sin(a) * rr, Math.cos(a) * rr, 0.01); _c.copy(col).lerp(_c2.set('#ffffff'), 0.55); H.aCol.setXYZ(i, _c.r, _c.g, _c.b);
      H.aSize.setX(i, 0.32 + (red ? 0 : 0.06 * Math.sin(lt * 4 + i))); H.aA.setX(i, f > 0.004 && f < 0.996 && this.hasData ? 1 : 0);
    });
    H.position.needsUpdate = H.aCol.needsUpdate = H.aSize.needsUpdate = H.aA.needsUpdate = true;
    // shock waves: on a balance change, on tap, and every few seconds once passed
    if (pass > 0.5 && !red && lt > this.nextWave) { this.waveAt = lt; this.waveCol.copy(GOLD); this.nextWave = lt + 2.6; }
    const wk = (lt - this.waveAt) / 1.6;
    if (wk >= 0 && wk < 1) {
      this.wave.visible = true; const s = 0.55 + outCubic(wk) * 1.6; this.wave.scale.setScalar(s);
      this.wave.material.color.copy(this.waveCol); this.wave.material.opacity = (1 - wk) * 0.8;
    } else this.wave.visible = false;
    // html: balance counter on the core
    if (this.hasData) {
      const b = this.dispBal(), txt = '$' + Math.round(b).toLocaleString('en-US');
      if (txt !== this.balTxt) { this.balEl.textContent = txt; this.balTxt = txt; this.cenW = this.cen.offsetWidth; this.cenH = this.cen.offsetHeight; this.cenLast = null; }
      if (moved || this.cenLast == null) {
        const p = this.screen(_v.set(0, 0, 0));
        const tf = `translate3d(${(p.x - (this.cenW || 100) / 2).toFixed(1)}px,${(p.y - (this.cenH || 40) / 2 - 2).toFixed(1)}px,0)`;
        if (tf !== this.cenLast) { this.cen.style.transform = tf; this.cenLast = tf; }
      }
    }
  }
}
