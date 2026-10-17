// Signal Pipeline (Liquidity Engine page): the steps of a setup as a glowing 3D track on a glass floor.
//   Sweep -> IFVG -> Order -> Trade -> Done: completed steps glow in their colour on pillars of light, the current one
//   pulses with sonar rings and an orbit of charging sparks, energy flows along the track and climbs into it, the steps
//   ahead wait as dim hollow rings. A step forward sends a comet along the track and a burst at the new node; going back
//   to idle fades the lights out from the far end. Idle (idx -1): every node dim, a slow drift along the whole track.
//   Calmer and dimmer outside the killzone; grey-violet and slow when the bot is not live.
//   Tap a node -> opts.onPick({ step, index, state: 'done' | 'current' | 'next' }); drag sideways to turn it a little.
// setData({ steps: ['Sweep','IFVG','Order','Trade','Done'], idx, live, killzone, desc? })   idx = current step, -1 = idle;
//   desc = one short line per step (defaults for the five standard steps). A card 230 px or taller also gets a hero
//   readout of the current step above the track.
// Draw calls ~12; particles: 140 flow + 40 charge sparks (60 + 20 lite) + 260 dust (110 lite).
import { THREE, Q, glowTexture, POINT_FRAG, count, rng, Hud, addBackdrop, addNebula, addDust, additive, attrs, paintBackdrop, ringTexture, sprite,
  clamp, lerp, smooth, outCubic, fract, num, esc, corners, div, injectStyle } from './hud.js';

const STEPS = ['Sweep', 'IFVG', 'Order', 'Trade', 'Done'];
const DESC = { sweep: 'a liquidity pool was run', ifvg: 'IFVG / CISD trigger in a killzone', order: 'limit order working', trade: 'managing the trade', done: 'one trade a day: finished' };
const COLS = ['#ff4fd8', '#a855f7', '#22d3ee', '#2ee59d', '#ffd36b'];
const YN = 0.5, M = 160;
const _v = new THREE.Vector3(), _c = new THREE.Color(), _c2 = new THREE.Color(), _m = new THREE.Matrix4(), GREY = new THREE.Color('#8a84b8');
// colour of step i of n: the five-colour ramp, sampled
function stepColor(i, n, out) { const f = n > 1 ? i / (n - 1) * (COLS.length - 1) : 0, a = Math.floor(f), b = Math.min(COLS.length - 1, a + 1); return out.set(COLS[a]).lerp(_c2.set(COLS[b]), f - a); }

// ------------------------------------------------------------------ shaders
const TRACK_V = `attribute float aU; attribute float aS; attribute vec3 aCol; varying float vU; varying float vS; varying vec3 vColor;
void main(){ vU = aU; vS = aS; vColor = aCol; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const TRACK_F = `uniform float uProg; uniform float uTime; uniform float uFlow; uniform float uE; uniform float uLead; uniform float uTail;
varying float vU; varying float vS; varying vec3 vColor;
void main(){
  float s = abs(vS), lit = smoothstep(uProg + 0.004, uProg - 0.004, vU);
  float ends = smoothstep(0.0, uLead, vU) * smoothstep(1.0, 1.0 - uTail, vU);
  float core = exp(-s * s * 14.0), rim = exp(-pow((s - 0.85) * 9.0, 2.0));
  float dash = exp(-pow((fract(vU * 26.0 - uFlow) - 0.5) * 5.0, 2.0));
  vec3 c = vColor * (lit * (core * (0.55 + dash * 0.9 * uE) + rim * 0.45) + (1.0 - lit) * (core * 0.07 + rim * 0.16)) * ends;
  gl_FragColor = vec4(c, 1.0);
}`;
const NODE_V = `attribute vec3 aCol; attribute float aSize; attribute float aState; attribute float aA; attribute float aId;
uniform float uTime; uniform float uPix; uniform float uMotion; uniform float uBeat; uniform float uHov;
varying vec3 vColor; varying float vState; varying float vAlpha; varying float vBeat; varying float vHi;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float cur = step(1.5, aState), b = cur * uBeat;
  vHi = 1.0 - step(0.5, abs(aId - uHov));
  gl_PointSize = clamp(aSize * uPix * (1.0 + b * 0.22 + vHi * 0.2) / -mv.z, 0.0, 160.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol; vState = aState; vAlpha = aA; vBeat = b;
}`;
const NODE_F = `varying vec3 vColor; varying float vState; varying float vAlpha; varying float vBeat; varying float vHi;
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2), halo = (1.0 - d2) * (1.0 - d2);
  float ring = exp(-pow((d - 0.5) * 13.0, 2.0)), core = exp(-d2 * 26.0), hi = vHi * exp(-pow((d - 0.82) * 11.0, 2.0));
  float a;
  if (vState < 0.5) a = ring * 0.55 + halo * 0.05 + core * 0.12;
  else if (vState < 1.5) a = halo * 0.35 + core * 0.95 + ring * 0.45;
  else a = halo * (0.45 + vBeat * 0.4) + core * (1.1 + vBeat * 0.5) + ring * 0.6 + exp(-pow((d - 0.3 - vBeat * 0.55) * 10.0, 2.0)) * 0.5;
  vec3 c = mix(vColor, vec3(1.0), clamp(core * 0.55, 0.0, 1.0));
  gl_FragColor = vec4(c * (a + hi * 0.8) * vAlpha, 1.0);
}`;
// flat glowing pads under the nodes (instanced quads on the floor)
const PAD_V = `attribute vec3 aAt; attribute vec3 aCol; attribute float aState; attribute float aA; uniform float uTime; uniform float uMotion;
varying vec2 vQ; varying vec3 vColor; varying float vState; varying float vA; varying float vPh;
void main(){ vQ = position.xy; vColor = aCol; vState = aState; vA = aA; vPh = fract(uTime * 0.5 * uMotion + aAt.x * 0.37);
  vec3 p = aAt + vec3(position.x, 0.0, -position.y) * 0.42; gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }`;
const PAD_F = `varying vec2 vQ; varying vec3 vColor; varying float vState; varying float vA; varying float vPh;
void main(){
  float r = length(vQ); if (r > 1.0) discard;
  float rim = exp(-pow((r - 0.72) * 16.0, 2.0)), fill = exp(-r * r * 5.0);
  float wave = vState > 1.5 ? exp(-pow((r - vPh) * 12.0, 2.0)) * (1.0 - vPh) : 0.0;
  float k = vState < 0.5 ? 0.25 : 1.0;
  gl_FragColor = vec4(vColor * (rim * 0.55 * k + fill * 0.22 * k + wave * 0.9) * vA, 1.0);
}`;
const LINE_V = `attribute vec3 aCol; varying vec3 vColor; void main(){ vColor = aCol; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const LINE_F = `varying vec3 vColor; void main(){ gl_FragColor = vec4(vColor, 1.0); }`;
const DOT_V = `attribute vec3 aCol; attribute float aSize; attribute float aA; uniform float uPix;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(aSize * uPix / -mv.z, 0.0, 64.0); gl_Position = projectionMatrix * mv; vColor = aCol; vAlpha = aA; }`;
const FLOOR_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const FLOOR_F = `uniform vec2 uHalf; uniform vec3 uC1; uniform vec3 uC2; uniform float uTime; uniform float uMotion; uniform float uE; varying vec3 vW;
float grid(vec2 p, float s){ vec2 c = p / s; vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c); return 1.0 - min(min(g.x, g.y), 1.0); }
void main(){
  vec2 p = vW.xz, n = p / uHalf; float fade = exp(-dot(n, n) * 2.2);
  float g = grid(p + vec2(0.0, uTime * 0.06 * uMotion * uE), 0.5);
  vec3 col = mix(uC1, uC2, clamp(0.5 + 0.5 * n.x, 0.0, 1.0));
  gl_FragColor = vec4(col * (g * 0.22 + 0.05) * fade, 1.0);
}`;

const CSS = `.fxh-pipeline .fxh-l.st{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.fxh-pipeline .fxh-l.st.cur{font-size:11px;font-weight:800;text-shadow:0 0 10px currentColor,0 0 4px #07080c}
.fxh-pipeline .fxh-l.st.next{color:rgba(188,192,236,.42)!important}
.fxp-st{position:absolute;left:10px;top:9px;display:flex;gap:7px;align-items:center;font-size:9px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}
.fxp-st i{width:7px;height:7px;border-radius:50%}
.fxp-hero{position:absolute;left:10px;right:10px;top:30px;text-align:center;display:none;line-height:1}
.fxh-pipeline.tall .fxp-hero{display:block}
.fxp-hero b{display:block;font-size:24px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;text-shadow:0 0 18px currentColor,0 0 5px #07080c;transition:color .6s}
.fxp-hero span{display:block;margin-top:7px;font-size:11px;font-weight:600;letter-spacing:.02em;color:rgba(214,218,250,.66);text-shadow:0 0 6px #07080c}`;

// ------------------------------------------------------------------ the view
export class Pipeline extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'pipeline', fov: 32, empty: 'No pipeline state',
      orbit: { yaw: 0, pitch: 0.7, auto: 0, min: -0.35, max: 0.35, pitchMin: 0.35, pitchMax: 0.95 } });
    injectStyle('fxh-pip-css', CSS);
    this.nodeK = 1; this.steps = []; this.idx = -1; this.prevIdx = -1; this.live = true; this.kz = true; this.nodes = []; this.Wt = 6;
    this.prog = 0; this.progTo = 0; this.e = 0.6; this.eTo = 1; this.sat = 1; this.satTo = 1; this.lit = []; this.flowT = 0; this.beatPh = 0;
    this.comet = null; this.burstAt = -9; this.burstNode = 0; this.hovI = -1; this.selI = -1;
    Object.assign(this.u, { uBeat: { value: 0 }, uHov: { value: -1 } });
    this.FN = count(140, 60); this.CN = count(40, 20);
    this.build();
    this.status = div('fxp-st', this.ui);
    this.hero = div('fxp-hero', this.ui, '<b></b><span></span>'); this.tall = false;
  }
  build() {
    const S = this.scene, u = this.u, R = rng(13);
    this.bgU = addBackdrop(S, [0.5, 0.6]);
    addNebula(S, [['#6d28d9', -4, 1.5, -6, 12, 5, 0.12], ['#22d3ee', 4.5, 1.2, -6, 9, 4, 0.05]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 220 : 260, 110), box: [6, 1, 2], cy: 0.6, seed: 51 });
    this.fU = { uHalf: { value: new THREE.Vector2(6, 2.5) }, uC1: { value: new THREE.Color('#5b3bd1') }, uC2: { value: new THREE.Color('#22d3ee') }, uTime: u.uTime, uMotion: u.uMotion, uE: { value: 1 } };
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), additive(FLOOR_V, FLOOR_F, this.fU, { extensions: { derivatives: true } }));
    this.floor.rotation.x = -Math.PI / 2; this.floor.position.y = -0.01; this.floor.renderOrder = 1; S.add(this.floor);
    this.tU = { uProg: { value: 0 }, uTime: u.uTime, uFlow: { value: 0 }, uE: { value: 1 }, uLead: { value: 0.08 }, uTail: { value: 0.08 } };
    this.track = new THREE.Mesh(new THREE.BufferGeometry(), additive(TRACK_V, TRACK_F, this.tU, { side: THREE.DoubleSide })); this.track.renderOrder = 2; S.add(this.track);
    const quad = new THREE.PlaneGeometry(2, 2), pg = new THREE.InstancedBufferGeometry(); pg.index = quad.index; pg.setAttribute('position', quad.attributes.position);
    attrs(8, { aAt: [3, 1], aCol: [3, 1], aState: [1, 1], aA: [1, 1] }, pg, THREE.InstancedBufferAttribute); pg.instanceCount = 0;
    this.pads = new THREE.Mesh(pg, additive(PAD_V, PAD_F, u, { side: THREE.DoubleSide })); this.pads.renderOrder = 3; S.add(this.pads);
    this.pillars = new THREE.LineSegments(attrs(16, { position: [3, 1], aCol: [3, 1] }), additive(LINE_V, LINE_F, {})); this.pillars.renderOrder = 4; S.add(this.pillars);
    this.nodePts = new THREE.Points(attrs(8, { position: [3, 1], aCol: [3, 1], aSize: [1, 1], aState: [1, 1], aA: [1, 1], aId: [1] }), additive(NODE_V, NODE_F, u)); this.nodePts.renderOrder = 7; S.add(this.nodePts);
    this.flow = new THREE.Points(attrs(this.FN + this.CN, { position: [3, 1], aCol: [3, 1], aSize: [1, 1], aA: [1, 1] }), additive(DOT_V, POINT_FRAG, u)); this.flow.renderOrder = 6; S.add(this.flow);
    this.sparks = Array.from({ length: this.FN }, () => ({ ph: R(), sp: 0.12 + R() * 0.14, sz: 0.03 + R() * 0.035, lat: (R() - 0.5) * 0.09, bob: R() }));
    this.charge = Array.from({ length: this.CN }, () => ({ a: R() * 6.283, sp: 1.2 + R() * 1.6, r: 0.24 + R() * 0.16, y: (R() - 0.5) * 0.3, tilt: (R() - 0.5) * 1.2, sz: 0.025 + R() * 0.03 }));
    const ring = ringTexture(false); this.textures.push(ring);
    this.sonar = sprite(S, ring, '#ffffff', 8); this.sonar2 = sprite(S, ring, '#ffffff', 8);
    this.cometS = sprite(S, glowTexture(), '#ffffff', 9); this.flash = sprite(S, glowTexture(), '#ffffff', 9);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  retheme() { paintBackdrop(this.bgU); }
  relayout(w, h) {
    const tall = h >= 230; this.ui.classList.toggle('tall', tall);
    const top = tall ? 30 + (this.hero.offsetHeight || 44) + 10 : 24;
    this.region = [-1, 1, -1 + 2 * 6 / h, 1 - 2 * top / h]; this.nodeK = clamp(1.5 - w / 1400, 1, 1.35);
    const W = clamp(5.2 * Math.pow(w / Math.min(h, tall ? h * 0.7 : h) / 2, 0.75), 4.6, 11), redo = tall !== this.tall || Math.abs(W - this.Wt) > 0.1;
    this.tall = tall; this.Wt = W;
    if (redo && this.steps.length) this.rebuild();
  }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' ? d : {};
    const steps = Array.isArray(src.steps) && src.steps.length ? src.steps.slice(0, 8).map((s) => String(s ?? '')) : STEPS;
    const n = steps.length, i0 = num(src.idx, -1), idx = Number.isFinite(i0) ? clamp(Math.round(i0), -1, n - 1) : -1;
    const live = src.live == null ? true : !!src.live, kz = !!src.killzone;
    this.desc = steps.map((s, i) => String((Array.isArray(src.desc) ? src.desc[i] : null) ?? DESC[s.toLowerCase()] ?? ''));
    const sig = steps.join('|') + '#' + idx + '#' + live + '#' + kz + '#' + this.desc.join('|');
    if (sig === this.sig) return;
    const first = this.sig == null; this.sig = sig;
    const shape = steps.join('|') !== this.steps.join('|');
    this.steps = steps; this.live = live; this.kz = kz;
    if (shape) { this.rebuild(); this.lit = steps.map(() => 0); }
    // a step forward: comet from the old current node to the new one, then a burst
    const old = this.idx; this.idx = idx;
    if (!first && idx > old && idx >= 0 && !Q.reduced) { this.comet = { from: Math.max(0, old), to: idx, t0: this.lt, dur: 0.75 }; }
    else if (!first && idx >= 0 && idx !== old && !Q.reduced) { this.burstAt = this.lt; this.burstNode = idx; }
    this.progTo = idx >= 0 ? this.nodeU(idx) : 0;
    if (first || Q.reduced) this.prog = this.comet ? this.prog : this.progTo;
    this.eTo = live ? (kz ? 1 : 0.55) : 0.28; this.satTo = live ? 1 : 0.35;
    if (first) { this.e = this.eTo; this.sat = this.satTo; }
    this.writeStatus();
    this.empty.style.display = 'none';
    this.ui.classList.add('on');
  }
  nodeU(i) { return (i + 1) / (this.steps.length + 1); }
  rebuild() {
    const n = this.steps.length, W = this.Wt, bow = Math.min(this.tall ? 1.9 : 1.3, W * (this.tall ? 0.24 : 0.16)), yn = this.tall ? YN * 1.4 : YN;
    this.nodes = this.steps.map((s, i) => { const t = n > 1 ? i / (n - 1) : 0.5, u2 = (2 * t - 1); return new THREE.Vector3((t - 0.5) * W, yn, bow * (1 - u2 * u2) - bow * 0.5); });
    const lead = W / Math.max(1, n - 1) * 0.75;
    const ctrl = [new THREE.Vector3(this.nodes[0].x - lead, 0, this.nodes[0].z - bow * 0.35), ...this.nodes.map((p) => new THREE.Vector3(p.x, 0, p.z)), new THREE.Vector3(this.nodes[n - 1].x + lead, 0, this.nodes[n - 1].z - bow * 0.35)];
    const curve = new THREE.CatmullRomCurve3(ctrl, false, 'centripetal');
    this.curve = curve;
    this.tU.uLead.value = this.tU.uTail.value = 0.5 / (n + 1);
    // track strip on the floor: aU = curve parameter (node i sits at (i + 1) / (n + 1))
    const g = attrs((M + 1) * 2, { position: [3], aU: [1], aS: [1], aCol: [3] }), A = g.attributes, idx = [], tan = new THREE.Vector3(), w = 0.1;
    for (let j = 0; j <= M; j++) {
      const t = j / M, p = curve.getPoint(t), tg = curve.getTangent(t, tan).normalize(), nx = -tg.z, nz = tg.x;
      const f = clamp(t * (n + 1) - 1, 0, n - 1); stepColor(f, n, _c);
      for (const s of [-1, 1]) { const k = j * 2 + (s > 0 ? 1 : 0); A.position.setXYZ(k, p.x + nx * w * s, 0.004, p.z + nz * w * s); A.aU.setX(k, t); A.aS.setX(k, s); A.aCol.setXYZ(k, _c.r, _c.g, _c.b); }
      if (j < M) { const b = j * 2; idx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2); }
    }
    g.setIndex(idx); this.track.geometry.dispose(); this.track.geometry = g;
    this.samples = Array.from({ length: M + 1 }, (_, j) => curve.getPoint(j / M));
    this.floor.scale.set(W + 4, 4.5, 1); this.fU.uHalf.value.set(W / 2 + 2, 2.25);
    this.pads.geometry.instanceCount = n; this.nodePts.geometry.setDrawRange(0, n); this.pillars.geometry.setDrawRange(0, n * 2);
    const zs = this.nodes.map((p) => p.z), z0 = Math.min(...zs), z1 = Math.max(...zs);
    this.anchors = new Float32Array(corners([], -W / 2 - 0.55, W / 2 + 0.55, -0.32, yn + 0.36, z0 - 0.3, z1 + 0.45));
    this.T.set(0, yn * 0.45, (z0 + z1) / 2);
    const defs = this.steps.map((s, i) => ({ text: s, p: new THREE.Vector3(this.nodes[i].x, 0, this.nodes[i].z + 0.08), ay: 0, dy: 6, cls: 'st', i }));
    this.setLabels(defs); this.styleLabels();
  }
  styleLabels() {
    const n = this.steps.length;
    for (const l of this.labels) {
      const st = this.state(l.i), c = stepColor(l.i, n, _c).clone().lerp(GREY, 1 - this.satTo);
      l.el.className = 'fxh-l st' + (st === 'current' ? ' cur' : st === 'next' ? ' next' : '');
      l.el.style.color = '#' + c.getHexString();
      l.wid = null;
    }
    this.camKey = '';
  }
  state(i) { return this.idx < 0 || i > this.idx ? 'next' : i === this.idx ? 'current' : 'done'; }
  writeStatus() {
    const [c, t] = !this.live ? ['#8a84b8', 'bot offline'] : this.kz ? ['#4ef0b0', 'killzone · live'] : ['#a78bfa', 'outside killzone'];
    const st = this.idx < 0 ? 'waiting for a sweep' : this.idx >= this.steps.length - 1 ? 'setup complete' : 'step ' + (this.idx + 1) + ' of ' + this.steps.length;
    this.status.innerHTML = `<i style="background:${c};box-shadow:0 0 8px ${c}"></i><span style="color:${c}">${t}</span><span style="color:rgba(188,192,236,.5)">· ${esc(st)}</span>`;
    const n = this.steps.length, i = this.idx, hc = i >= 0 ? '#' + stepColor(i, n, _c).lerp(GREY, 1 - this.satTo).getHexString() : '#8a84b8';
    this.hero.querySelector('b').textContent = i >= 0 ? this.steps[i] : 'Waiting';
    this.hero.querySelector('b').style.color = hc;
    this.hero.querySelector('span').textContent = i >= 0 ? (this.desc[i] || 'step ' + (i + 1) + ' of ' + n) : !this.live ? 'the bot is not running' : this.kz ? 'watching for a liquidity sweep' : 'setups only trigger inside the killzones';
    if (this.labels.length) this.styleLabels();
  }

  // ---------------------------------------------------------------- picking
  nearestNode(px, py, maxPx) {
    let best = -1, bd = maxPx * maxPx;
    this.nodes.forEach((p, i) => { const s = this.screen(p), dx = s.x - px, dy = s.y - py, d = dx * dx + dy * dy; if (d < bd) { bd = d; best = i; } });
    return best;
  }
  pickAt(px, py) {
    const i = this.nearestNode(px, py, 34); this.selI = i;
    if (i >= 0) { this.burstAt = this.lt; this.burstNode = i; this.emit({ step: this.steps[i], index: i, state: this.state(i) }); }
  }
  hoverAt(p) { if (!p) { this.hovI = -1; this.u.uHov.value = -1; this.canvas.style.cursor = 'grab'; } }
  devTapPoint() { const i = Math.max(0, this.idx), p = this.screen(this.nodes[i] || _v.set(0, 0, 0)); return [p.x, p.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u, red = Q.reduced, n = this.steps.length;
    u.uTime.value = lt;
    const o = this.orbit;
    if (!o.dragging && o.idle > 2.5 && !red) o.yaw += (Math.sin(lt * 0.21) * 0.07 - o.yaw) * Math.min(1, dt * 0.4);
    const moved = this.camStep(dt);
    if (!n) return;
    // mood easing
    const k = Math.min(1, dt * 1.5); this.e += (this.eTo - this.e) * k; this.sat += (this.satTo - this.sat) * k;
    const E = this.e;
    this.flowT += dt * (0.25 + 0.75 * E) * (red ? 0 : 1);
    this.tU.uFlow.value = this.flowT * 2.2; this.tU.uE.value = E; this.fU.uE.value = E;
    // progress: the comet carries it forward, otherwise ease
    let cometP = null;
    if (this.comet) {
      const c = this.comet, q = clamp((lt - c.t0) / c.dur, 0, 1), e = outCubic(q), u0 = this.nodeU(c.from), u1 = this.nodeU(c.to);
      this.prog = lerp(u0, u1, e); cometP = this.prog;
      if (q >= 1) { this.comet = null; this.burstAt = lt; this.burstNode = c.to; }
    } else this.prog += (this.progTo - this.prog) * Math.min(1, dt * (this.progTo < this.prog ? 2.2 : 4));
    this.tU.uProg.value = this.idx < 0 && this.prog < 0.01 ? 0 : this.prog;
    // node lights: on up to the current node; a reset fades them out from the far end
    for (let i = 0; i < n; i++) {
      const want = this.idx >= 0 && i <= this.idx && this.nodeU(i) <= this.prog + 0.002 ? 1 : 0;
      this.lit[i] += (want - this.lit[i]) * Math.min(1, dt * (want ? 6 : 2.5 + (n - i) * 0.3));
    }
    this.beatPh += dt * (0.7 + 1.3 * E) * (red ? 0 : 1);
    const beat = red ? 0.5 : Math.pow(0.5 + 0.5 * Math.sin(this.beatPh * Math.PI * 2), 2); u.uBeat.value = beat;
    // write nodes, pads, pillars
    const NA = this.nodePts.geometry.attributes, PA = this.pads.geometry.attributes, LA = this.pillars.geometry.attributes;
    for (let i = 0; i < n; i++) {
      const p = this.nodes[i], st = this.state(i), L = this.lit[i];
      stepColor(i, n, _c).lerp(GREY, 1 - this.sat);
      const cur = st === 'current' && L > 0.5, s = cur ? 2 : L > 0.5 ? 1 : 0, br = (0.55 + 0.45 * E) * (s ? 1 : 0.9);
      NA.position.setXYZ(i, p.x, p.y + (cur && !red ? Math.sin(lt * 2) * 0.03 : 0), p.z); NA.aCol.setXYZ(i, _c.r * br * 1.15, _c.g * br * 1.15, _c.b * br * 1.15);
      NA.aSize.setX(i, (cur ? 0.62 : s ? 0.44 : 0.38) * this.nodeK); NA.aState.setX(i, s); NA.aA.setX(i, s ? 0.4 + 0.6 * L : 0.75); NA.aId.setX(i, i);
      PA.aAt.setXYZ(i, p.x, 0.006, p.z); PA.aCol.setXYZ(i, _c.r * br, _c.g * br, _c.b * br); PA.aState.setX(i, s); PA.aA.setX(i, s ? 0.5 + 0.5 * L : 0.6);
      const pa = s ? 0.55 * L * br : 0.08;
      LA.position.setXYZ(i * 2, p.x, 0, p.z); LA.position.setXYZ(i * 2 + 1, p.x, p.y, p.z);
      LA.aCol.setXYZ(i * 2, _c.r * pa, _c.g * pa, _c.b * pa); LA.aCol.setXYZ(i * 2 + 1, _c.r * pa * 0.25, _c.g * pa * 0.25, _c.b * pa * 0.25);
    }
    for (const a of [NA.position, NA.aCol, NA.aSize, NA.aState, NA.aA, NA.aId, PA.aAt, PA.aCol, PA.aState, PA.aA, LA.position, LA.aCol]) a.needsUpdate = true;
    // flow sparks along the lit track, climbing into the current node; idle: a slow drift along everything
    const F = this.flow.geometry.attributes, FP = F.position.array, FC = F.aCol.array, FS = F.aSize.array, FA = F.aA.array, idle = this.idx < 0;
    const end = idle ? 1 : this.prog, top = this.idx >= 0 ? this.nodes[this.idx] : null;
    this.sparks.forEach((p, i) => {
      const ph = fract(p.ph + this.flowT * p.sp * (idle ? 0.35 : 1)), uu = ph * end, f = uu * M, j = Math.min(M - 1, Math.floor(f)), r = f - j;
      const a = this.samples[j], b = this.samples[j + 1];
      let x = a.x + (b.x - a.x) * r, y = 0.05 + Math.sin(p.bob * 20 + lt * 2) * 0.015, z = a.z + (b.z - a.z) * r + p.lat;
      if (top && !idle) { const c = smooth(clamp((ph - 0.9) / 0.1, 0, 1)); x = lerp(x, top.x, c); z = lerp(z, top.z, c); y = lerp(y, top.y, c); }
      stepColor(clamp(uu * (n + 1) - 1, 0, n - 1), n, _c).lerp(GREY, 1 - this.sat).lerp(_c2.set('#ffffff'), 0.3);
      FP[i * 3] = x; FP[i * 3 + 1] = y; FP[i * 3 + 2] = z; FC[i * 3] = _c.r; FC[i * 3 + 1] = _c.g; FC[i * 3 + 2] = _c.b; FS[i] = p.sz;
      FA[i] = (idle ? 0.35 : 0.95) * (0.35 + 0.65 * E) * Math.sin(ph * Math.PI) * (end > 0.02 ? 1 : 0);
    });
    // charge sparks orbiting the current node
    const cur = top && !idle && this.lit[this.idx] > 0.5;
    this.charge.forEach((c, k) => {
      const i = this.FN + k;
      if (!cur) { FA[i] = 0; return; }
      const a = c.a + lt * c.sp * (0.4 + 0.6 * E) * (red ? 0 : 1), ca = Math.cos(a), sa = Math.sin(a);
      FP[i * 3] = top.x + ca * c.r; FP[i * 3 + 1] = top.y + c.y * 0.5 + sa * c.r * Math.sin(c.tilt) * 0.6; FP[i * 3 + 2] = top.z + sa * c.r * Math.cos(c.tilt);
      stepColor(this.idx, n, _c).lerp(_c2.set('#ffffff'), 0.45); FC[i * 3] = _c.r; FC[i * 3 + 1] = _c.g; FC[i * 3 + 2] = _c.b; FS[i] = c.sz; FA[i] = 0.85 * (0.4 + 0.6 * E);
    });
    F.position.needsUpdate = F.aCol.needsUpdate = F.aSize.needsUpdate = F.aA.needsUpdate = true;
    // sonar rings around the current node, the comet, the arrival burst
    if (cur) {
      stepColor(this.idx, n, _c).lerp(GREY, 1 - this.sat);
      [this.sonar, this.sonar2].forEach((s, k) => {
        const ph = red ? 0.4 + k * 0.3 : fract(lt * (0.35 + 0.4 * E) + k * 0.5);
        s.visible = true; s.position.copy(top); s.scale.setScalar(0.35 + ph * 0.9); s.material.color.copy(_c); s.material.opacity = (1 - ph) * 0.65 * (0.5 + 0.5 * E);
      });
    } else this.sonar.visible = this.sonar2.visible = false;
    if (cometP != null) {
      const f = cometP * M, j = Math.min(M - 1, Math.floor(f)), r = f - j, a = this.samples[j], b = this.samples[j + 1];
      this.cometS.visible = true; this.cometS.position.set(a.x + (b.x - a.x) * r, 0.12, a.z + (b.z - a.z) * r); this.cometS.scale.setScalar(0.55);
      this.cometS.material.color.copy(stepColor(clamp(cometP * (n + 1) - 1, 0, n - 1), n, _c)).lerp(_c2.set('#ffffff'), 0.4); this.cometS.material.opacity = 1;
    } else this.cometS.visible = false;
    const bk = (lt - this.burstAt) / 0.9;
    if (bk >= 0 && bk < 1 && this.nodes[this.burstNode]) {
      this.flash.visible = true; this.flash.position.copy(this.nodes[this.burstNode]); this.flash.scale.setScalar(0.4 + outCubic(bk) * 1.6);
      this.flash.material.color.copy(stepColor(this.burstNode, n, _c)).lerp(_c2.set('#ffffff'), 0.5); this.flash.material.opacity = (1 - bk) * 0.9;
    } else this.flash.visible = false;
    // hover
    if (this._hoverAt) {
      const [hx, hy] = this._hoverAt; this._hoverAt = null; const i = this.nearestNode(hx, hy, 30);
      if (i !== this.hovI) { this.hovI = i; u.uHov.value = i; this.canvas.style.cursor = i >= 0 ? 'pointer' : 'grab'; }
    }
    if (moved) this.placeLabels();
  }
}
