// Liquidity Map (Today / Chart): the untaken liquidity pools around the current price as a 3D ladder of glowing plates.
//   The price is a bright horizontal beam through the middle (its number in HTML at the right end, tinted green / red for a
//   moment when it moves). Pools above are buy-side plates (orange), pools below sell-side plates (blue), stacked by distance
//   on a compressed price axis (asinh: the first ~30 pts are near-linear, far pools stay on screen). Width and glow follow
//   the pool's strength; the nearest pool on each side pulses. Each plate carries its label and price (PDH, ONL, 1H swing...).
//   An open position adds a red stop plane and a green target plane with their R distance, a thin white entry line and a
//   risk / reward ruler on the right. The last bars sit behind the ladder as a faint candle trail. "pts from price" ticks
//   on the left spine. Slow camera drift; drag to orbit; tap a plate -> opts.onPick(pool) (the page's pool object; stop /
//   target / entry only select and show the tooltip); mouse hover shows the tooltip.
//   First data: the beam ignites, then the plates slide out of it, nearest first; new data: plates glide to their new
//   distance, newcomers slide out of the beam, leavers fade; the same data twice does nothing.
// setData({ price, pools: [{ price, side: 'H'|'L', label, strength, dist }], bars: [[t,o,h,l,c], ...] (last ~40, optional),
//           position: { dir: 'long'|'short'|1|-1, entry, stop, target } | null })
//   price missing -> the last bar's close; no price at all -> "No price yet". side missing -> above / below the price.
//   dist missing -> price - current price. At most 8 pools per side (the nearest). strength 1..3 (default 1).
// Draw calls ~12 (backdrop, 3 nebula, dust, plates = one InstancedMesh, beam, sparkles, flare, trail = one InstancedMesh,
//   guides, reticle) whatever the data. Particles: <= 96 plate instances, <= 60 trail bars, 70 beam sparkles (24 lite),
//   800 dust (600 phone, 280 lite).
import { THREE, Q, theme, glowTexture, POINT_FRAG, count, Hud, addBackdrop, addNebula, addDust, Guides, ringTexture, sprite, additive,
  paintBackdrop, clamp, smooth, outCubic, outBack, num, esc, hash, corners, div, injectStyle } from './hud.js';

const S_NEAR = 30;                      // asinh scale (pts): the near-linear zone around the price
const MAX_SIDE = 8, MAX_BARS = 60, CAP = 48;   // pools per side, trail bars, plate slots (x2 instances: plate + halo)
const TICKS = [10, 25, 50, 100, 200, 400, 800, 1500, 3000];
const FLY = 1, MOVE = 2, SHRINK = 4;
const COL = { bsl: '#ff9b5c', ssl: '#6d9bff', beam: '#d9d2ff', stop: '#ff5a7a', target: '#2ee59d', entry: '#f4f1ff', up: '#2ee5c8', dn: '#ff4fd8' };
const CSS_C = { bsl: '#ffb27a', ssl: '#8fb3ff', beam: '#e6e0ff', stop: '#ff8aa4', target: '#4ef0b0', entry: '#f4f1ff' };
const Q_H = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0)), Q_V = new THREE.Quaternion();
const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _s = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color();
const MINUS = '−';
const fmtPx = (v) => (Number.isFinite(v) ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
const fmtPts = (v, plus = true) => (Number.isFinite(v) ? (v < 0 ? MINUS : plus && v > 0 ? '+' : '') + Math.round(Math.abs(v)) + ' pts' : '—');
const fmtRR = (v) => (Number.isFinite(v) ? (v < 0 ? MINUS : '+') + (Math.abs(v) >= 9.95 ? Math.round(Math.abs(v)) : Math.abs(v).toFixed(1)) + 'R' : '—');
const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s);

// ------------------------------------------------------------------ shaders
// plates: one InstancedMesh of unit planes. aMisc = (alpha, pulse, kind, slot): kind 0 plate (lit rims, a glowing front lip,
// a slow scan), 1 halo (a soft cloud under a plate / the beam), 2 ruler slab (vertical, fill + rims)
const PLATE_V = `attribute vec3 aCol; attribute vec4 aMisc;
uniform float uTime; uniform float uMotion; uniform float uSel; uniform float uHov;
varying vec2 vUv; varying vec3 vCol; varying float vA; varying float vHi; varying float vKind; varying float vSeed; varying vec2 vSz;
void main(){
  vec4 w = modelMatrix * instanceMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * viewMatrix * w;
  vUv = uv; vCol = aCol; vKind = aMisc.z; vSeed = fract(aMisc.w * 0.37);
  vSz = vec2(length(instanceMatrix[0].xyz), length(instanceMatrix[1].xyz));
  float pulse = aMisc.y * (0.5 + 0.5 * sin(uTime * 2.4 * uMotion + aMisc.w * 1.7));
  vA = aMisc.x * (1.0 + 0.55 * pulse);
  vHi = max(1.0 - step(0.5, abs(aMisc.w - uSel)), 0.7 * (1.0 - step(0.5, abs(aMisc.w - uHov))));
}`;
const PLATE_F = `uniform float uTime; uniform float uMotion;
varying vec2 vUv; varying vec3 vCol; varying float vA; varying float vHi; varying float vKind; varying float vSeed; varying vec2 vSz;
void main(){
  if (vA <= 0.001) discard;
  if (vKind > 0.5 && vKind < 1.5) {
    vec2 q = (vUv - 0.5) * 2.0; float g = exp(-dot(q, q) * 2.6) * (1.0 - vUv.y * 0.25);
    gl_FragColor = vec4(vCol * g * 0.42 * vA * (1.0 + vHi * 0.6), 1.0); return;
  }
  vec2 e = min(vUv, 1.0 - vUv) * vSz; float edge = min(e.x, e.y);
  float rim = exp(-edge * 34.0) * 0.85 + exp(-edge * 7.0) * 0.1;
  float slab = step(1.5, vKind);
  float front = exp(-vUv.y * vSz.y * 11.0) * 0.42 * (1.0 - slab);
  float fill = (0.085 + 0.06 * (1.0 - vUv.y)) * (1.0 + slab * 1.6);
  float scan = exp(-pow((vUv.x - fract(uTime * 0.06 * uMotion + vSeed)) * 9.0, 2.0)) * 0.09 * uMotion * (1.0 - slab);
  float hi = vHi * (0.3 + rim * 0.8);
  vec3 c = mix(vCol, vec3(1.0), clamp(vHi * 0.25 + rim * 0.1, 0.0, 1.0));
  gl_FragColor = vec4(c * (fill + rim + front + scan + hi) * vA, 1.0);
}`;
// sparkles travelling along the price beam
const SPARK_V = `attribute float aSeed; uniform float uTime; uniform float uPix; uniform float uMotion; uniform float uLen; uniform float uIn;
varying vec3 vColor; varying float vAlpha;
void main(){ float t = uTime * uMotion; float s = fract(aSeed + t * (0.04 + aSeed * 0.07));
  vec3 p = vec3((s - 0.5) * uLen * uIn, sin(t * 2.0 + aSeed * 40.0) * 0.03, cos(t * 1.7 + aSeed * 23.0) * 0.06);
  vec4 mv = modelViewMatrix * vec4(p, 1.0); float tw = 0.6 + 0.4 * sin(t * 3.0 + aSeed * 60.0);
  gl_PointSize = clamp((0.045 + aSeed * 0.07) * uPix * tw / -mv.z, 0.0, 26.0); gl_Position = projectionMatrix * mv;
  vColor = mix(vec3(0.84, 0.8, 1.0), vec3(1.0), aSeed) * 1.2;
  vAlpha = tw * uIn * smoothstep(0.0, 0.08, s) * (1.0 - smoothstep(0.92, 1.0, s)); }`;

const CSS = `.fxh-liqmap .fxh-l.px{font-size:15px;font-weight:800;letter-spacing:-.01em;color:#f1edff;text-shadow:0 0 14px rgba(170,150,255,.6),0 0 3px #07080c;transition:color .6s}
.fxh-liqmap .fxh-l.px i{font-style:normal;font-size:9px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:rgba(188,192,236,.62);margin-right:5px;vertical-align:2px}
.fxh-liqmap .fxh-l.px.up{color:#7ff5c9}.fxh-liqmap .fxh-l.px.dn{color:#ff8ab0}
.fxh-liqmap .fxh-l.pl{font-size:10px;font-weight:700;letter-spacing:.01em;text-shadow:0 0 8px #07080c,0 0 3px #07080c}
.fxh-liqmap .fxh-l.pl em{font-style:normal;font-weight:500;color:rgba(214,218,250,.7);margin-left:4px}
.fxh-liqmap .fxh-l.tag em{font-style:normal;font-weight:600;color:rgba(214,218,250,.78);margin-left:4px}
.fxh-liqmap .fxh-l.tag.pos{line-height:1.2;padding:2px 6px}
.fxh-liqmap .fxh-empty.up{top:30%}
@media (max-width:760px){.fxh-liqmap .fxh-l.px{font-size:13px}}`;

// ------------------------------------------------------------------ the view
export class LiquidityMap extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'liqmap', fov: 36, empty: 'No price yet',
      orbit: { yaw: -0.32, pitch: 0.3, auto: 0.03, min: -0.78, max: 0.78, pitchMin: 0.08, pitchMax: 0.72 } });
    injectStyle('fxh-liq-css', CSS);
    this.W = 4.2; this.H = 3.4; this.D = 1.3; this.yA = 1.7; this.yB = 1.7; this.k = 1;
    this.price = NaN; this.bars = []; this.pos = null; this.pools = []; this.items = []; this.slots = []; this.byKey = new Map();
    this.animating = false; this.introDone = false; this.beamAt = -1; this.beamS = 0; this.flashAt = -1;
    this.sel = null; this.hov = null; this.beamR = new THREE.Vector3(); this.labelRoom = 1.6;
    Object.assign(this.u, { uSel: { value: -1 }, uHov: { value: -1 } });
    this.build();
    this.legend = div('fxh-leg'); this.ui.prepend(this.legend);
    this.hint = div('fxh-l h fix', this.ui);
  }

  // ---------------------------------------------------------------- scene
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.5]);
    addNebula(S, [['#6d28d9', -4, 2, -8, 13, 8, 0.1], ['#ff9b5c', 4.5, 2.6, -9, 9, 6, 0.035], ['#3b6bff', 3.5, -2.6, -9, 9, 6, 0.045]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 600 : 800, 280), box: [5, 2.6, 3], cy: 0, seed: 41 });
    // plates
    const pg = new THREE.PlaneGeometry(1, 1);
    pg.setAttribute('aCol', new THREE.InstancedBufferAttribute(new Float32Array(CAP * 2 * 3), 3));
    pg.setAttribute('aMisc', new THREE.InstancedBufferAttribute(new Float32Array(CAP * 2 * 4), 4).setUsage(THREE.DynamicDrawUsage));
    this.plates = new THREE.InstancedMesh(pg, additive(PLATE_V, PLATE_F, u, { side: THREE.DoubleSide }), CAP * 2);
    this.plates.instanceMatrix.setUsage(THREE.DynamicDrawUsage); this.plates.count = 0; this.plates.renderOrder = 4; S.add(this.plates);
    // price beam: neon core, sparkles, a flare at the label end
    this.beam = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: new THREE.Color(COL.beam).multiplyScalar(1.55), transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.beam.renderOrder = 6; this.beam.visible = false; S.add(this.beam);
    const SN = count(70, 24), sg = new THREE.BufferGeometry(), seeds = new Float32Array(SN);
    for (let i = 0; i < SN; i++) seeds[i] = hash('spark' + i);
    sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(SN * 3), 3)); sg.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
    this.spU = { ...u, uLen: { value: 5 }, uIn: { value: 0 } };
    this.sparks = new THREE.Points(sg, additive(SPARK_V, POINT_FRAG, this.spU)); this.sparks.renderOrder = 7; S.add(this.sparks);
    this.flare = sprite(S, glowTexture(), COL.beam, 8);
    // candle trail: one InstancedMesh of unit boxes (wicks live in the guides)
    this.trail = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }), MAX_BARS);
    this.trail.count = 0; this.trail.renderOrder = 2; S.add(this.trail);
    for (let i = 0; i < MAX_BARS; i++) this.trail.setColorAt(i, _c.set(0x000000));   // allocates instanceColor
    this.guides = new Guides(S, 3);
    const ring = ringTexture(false); this.textures.push(ring);
    this.reticle = sprite(S, ring, '#ffffff', 12);
    S.traverse((o) => { o.frustumCulled = false; });
  }
  retheme() { paintBackdrop(this.bgU); }
  dispose() { this.plates.dispose(); this.trail.dispose(); super.dispose(); }
  shape(w, h) {
    const asp = w / h, W = 4.2 * Math.pow(clamp(asp / 1.15, 1, 1.9), 0.75);
    const room = W * (asp < 1.4 ? 0.5 : 0.36), changed = Math.abs(W - this.W) > 0.12;
    this.W = W; this.labelRoom = room; return changed;
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
    d = d && typeof d === 'object' && !Array.isArray(d) ? d : {};
    const bars = (Array.isArray(d.bars) ? d.bars : []).filter((b) => Array.isArray(b) && b.length >= 5 && [1, 2, 3, 4].every((j) => Number.isFinite(num(b[j])))).slice(-MAX_BARS)
      .map((b) => [num(b[0], 0), num(b[1]), num(b[2]), num(b[3]), num(b[4])]);
    const price = num(d.price, bars.length ? bars[bars.length - 1][4] : NaN), has = Number.isFinite(price);
    // pools: finite price, side inferred when missing, the nearest MAX_SIDE on each side
    const raw = Array.isArray(d.pools) ? d.pools : [], all = [];
    for (let i = 0; i < raw.length; i++) {
      const p = raw[i]; if (!p || typeof p !== 'object') continue;
      const pp = num(p.price); if (!Number.isFinite(pp)) continue;
      const side = p.side === 'H' || p.side === 'L' ? p.side : pp >= price ? 'H' : 'L';
      const dist = Number.isFinite(num(p.dist)) ? num(p.dist) : has ? pp - price : NaN;
      all.push({ row: p, price: pp, side, label: String(p.label ?? (side === 'H' ? 'BSL' : 'SSL')), strength: clamp(num(p.strength, 1), 0.5, 3), dist, i });
    }
    const above = has ? all.filter((p) => p.price >= price).sort((a, b) => a.price - b.price).slice(0, MAX_SIDE) : [];
    const below = has ? all.filter((p) => p.price < price).sort((a, b) => b.price - a.price).slice(0, MAX_SIDE) : [];
    above.forEach((p, i) => { p.rank = i; }); below.forEach((p, i) => { p.rank = i; });
    const pools = [...above, ...below];
    // position
    let pos = null;
    const P = d.position && typeof d.position === 'object' ? d.position : null;
    if (P && has) {
      const entry = num(P.entry), stop = num(P.stop), target = num(P.target), ds = String(P.dir ?? '');
      if (Number.isFinite(entry) && Number.isFinite(stop) && stop !== entry) {
        const dir = typeof P.dir === 'number' ? (P.dir < 0 ? -1 : 1) : /^(s|sell|-)/i.test(ds) ? -1 : /^(l|long|buy|\+)/i.test(ds) ? 1 : stop < entry ? 1 : -1;
        const R = Math.abs(entry - stop), tgt = Number.isFinite(target) ? target : NaN;
        pos = { row: P, dir, entry, stop, target: tgt, R, tr: Number.isFinite(tgt) ? (tgt - entry) * dir / R : NaN };
      }
    }
    const sig = (has ? price : 'x') + '|' + pools.map((p) => p.side + '/' + p.label + '/' + p.price + '/' + p.strength + '/' + p.dist).join(',')
      + '|' + bars.length + ':' + (bars[0]?.[0] ?? '') + ':' + (bars.at(-1)?.[0] ?? '') + ':' + (bars.at(-1)?.[4] ?? '')
      + '|' + (pos ? pos.dir + '/' + pos.entry + '/' + pos.stop + '/' + pos.target : '');
    if (sig === this.sig) {   // same data: keep the page's current row objects, nothing else
      for (const p of pools) { const s = this.byKey.get(this.keyOf(p)); if (s) s.it.pool = p.row; }
      if (pos && this.pos) this.pos.row = pos.row;
      return;
    }
    this.sig = sig;
    if (Number.isFinite(this.price) && has && price !== this.price && !Q.reduced) { this.flashAt = this.lt; this.flashDir = price > this.price ? 'up' : 'dn'; }
    this.price = price; this.bars = bars; this.pos = pos; this.pools = pools;
    // items: plates (pools, stop, target, entry), the ruler slabs and the beam's halo
    const items = [], seen = new Set();
    for (const p of pools) {
      let key = this.keyOf(p); if (seen.has(key)) key += '#' + p.i; seen.add(key);
      items.push({ key, kind: 'pool', pool: p.row, p, side: p.side, label: p.label, price: p.price, strength: p.strength, dist: p.dist, rank: p.rank,
        col: new THREE.Color(p.side === 'H' ? COL.bsl : COL.ssl).multiplyScalar(0.8 + 0.22 * p.strength), css: p.side === 'H' ? CSS_C.bsl : CSS_C.ssl,
        pulse: p.rank === 0 ? 1 : 0, halo: 1, haloA: 0.5 + 0.2 * p.strength, alpha: 0.78 + 0.08 * p.strength, rot: 'h', seed: hash(key) });
    }
    if (pos) {
      const mk = (kind, pr, col, css, alpha, dptK, halo) => items.push({ key: '__' + kind, kind, price: pr, col: new THREE.Color(col).multiplyScalar(1.2), css, alpha, dptK, halo, haloA: 0.45, rot: 'h', pulse: 0, seed: hash(kind), rank: 0 });
      mk('entry', pos.entry, COL.entry, CSS_C.entry, 0.6, 0.22, 0);
      mk('stop', pos.stop, COL.stop, CSS_C.stop, 0.95, 0.9, 1);
      if (Number.isFinite(pos.target)) mk('target', pos.target, COL.target, CSS_C.target, 0.95, 0.9, 1);
      items.push({ key: '__risk', kind: 'slab', from: pos.entry, to: pos.stop, col: new THREE.Color(COL.stop), alpha: 0.55, rot: 'v', pulse: 0, halo: 0, seed: 0.3, rank: 0 });
      if (Number.isFinite(pos.target)) items.push({ key: '__reward', kind: 'slab', from: pos.entry, to: pos.target, col: new THREE.Color(COL.target), alpha: 0.5, rot: 'v', pulse: 0, halo: 0, seed: 0.6, rank: 0 });
    }
    if (has) items.push({ key: '__beam', kind: 'beam', price, col: new THREE.Color(COL.beam).multiplyScalar(0.75), alpha: 0, halo: 1, haloA: 0.6, rot: 'h', pulse: 0, seed: 0.1, rank: 0 });
    this.items = items.slice(0, CAP - 8);   // (never reached: <= 16 pools + 6 position items + beam)
    this.layout();
    // slots: survivors glide, newcomers slide out of the beam, leavers fade
    const first = !this.slots.length && !this.introDone, now = this.lt, red = Q.reduced;
    const next = [], keep = new Set();
    for (const it of this.items) {
      let sl = this.byKey.get(it.key);
      if (sl && !sl.dead) { sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.mode = MOVE; sl.t0 = now; sl.dur = red ? 0 : 0.9; }
      else {
        sl = { key: it.key, p: new THREE.Vector3(), p0: new THREE.Vector3(), p1: new THREE.Vector3(), pr: new THREE.Vector3(), s: 0, s0: 0, a: 0, a0: 0, dead: false, done: false };
        sl.mode = FLY; sl.p0.set(it.tx, it.kind === 'slab' ? it.ty : 0, it.tz); sl.p.copy(sl.p0);
        sl.t0 = now + (first ? 0.45 + it.rank * 0.13 + it.seed * 0.08 : 0.05 + it.rank * 0.06); sl.dur = first ? 0.9 : 0.7;
        if (it.kind === 'beam') { sl.t0 = now; sl.dur = first ? 0.6 : 0.3; }
        if (red) { sl.t0 = now; sl.dur = 0; }
      }
      sl.it = it; sl.done = false; sl.p1.set(it.tx, it.ty, it.tz);
      keep.add(it.key); next.push(sl);
    }
    for (const sl of this.slots) {
      if (keep.has(sl.key) || sl.dead) continue;
      sl.dead = true; sl.done = false; sl.mode = SHRINK; sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.t0 = now; sl.dur = red ? 0 : 0.45;
      next.push(sl);
    }
    this.slots = next.slice(0, CAP); this.byKey.clear();
    for (const sl of this.slots) if (!sl.dead) this.byKey.set(sl.key, sl);
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.hoverAt(null);
    this.writeStatic(); this.animating = true;
    if (first && has) { this.introDone = true; this.beamAt = red ? -1 : now; this.beamS = red ? 1 : 0; }
    if (!has) this.beamS = 0; else if (this.beamAt < 0) this.beamS = 1;
    this.frameScene();
    this.empty.textContent = has ? 'No untaken pools nearby' : 'No price yet';
    this.empty.classList.toggle('up', has);
    this.empty.style.display = has && pools.length ? 'none' : 'block';
    this.ui.classList.add('on');
    this.tipKey = null; this.tipFor(this.hov || this.sel);
  }
  keyOf(p) { return 'P|' + p.side + '|' + p.label + '|' + p.price; }
  // the compressed price axis: y = k * asinh((price - current) / S_NEAR), fitted so the ladder is H tall
  F(v) { return Math.asinh((v - this.price) / S_NEAR); }
  Y(v) { return this.k * this.F(v); }
  layout() {
    const W = this.W, D = this.D;
    let hA = 0.5, hB = 0.5;
    const ext = (v) => { if (!Number.isFinite(v)) return; const y = this.F(v); if (y > 0) hA = Math.max(hA, y); else hB = Math.max(hB, -y); };
    for (const p of this.pools) ext(p.price);
    if (this.pos) { ext(this.pos.entry); ext(this.pos.stop); ext(this.pos.target); }
    for (const b of this.bars) { ext(b[2]); ext(b[3]); }
    this.k = this.H / (hA + hB); this.yA = this.k * hA; this.yB = this.k * hB;
    for (const it of this.items) {
      it.tx = 0; it.tz = 0;
      if (it.kind === 'pool') { it.ty = this.Y(it.price); it.w = W * clamp(0.5 + 0.17 * it.strength, 0.55, 1); it.dpt = D * clamp(0.72 + 0.1 * it.strength, 0.8, 1.05); }
      else if (it.kind === 'beam') { it.ty = 0; it.w = W + 0.9; it.dpt = D * 1.5; }
      else if (it.kind === 'slab') { const y0 = this.Y(it.from), y1 = this.Y(it.to); it.ty = (y0 + y1) / 2; it.tx = W / 2 + 0.14; it.w = 0.11; it.dpt = Math.max(0.02, Math.abs(y1 - y0)); }
      else { it.ty = this.Y(it.price); it.w = W * 0.98; it.dpt = D * it.dptK; }
    }
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
  writeStatic() {
    const n = this.slots.length, A = this.plates.geometry.attributes;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], c = sl.it.col; sl.idx = i;
      A.aCol.setXYZ(i * 2, c.r, c.g, c.b); A.aCol.setXYZ(i * 2 + 1, c.r, c.g, c.b);
    }
    A.aCol.needsUpdate = true;
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
  }
  writeDynamic() {
    const n = this.slots.length, A = this.plates.geometry.attributes.aMisc, M = this.plates;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], it = sl.it, p = sl.p, s = sl.s, j = i * 2;
      if (it.rot === 'v') { _m.compose(p, Q_V, _s.set(it.w, it.dpt * s, 1)); A.setXYZW(j, sl.a * it.alpha, 0, 2, i); sl.pr.set(p.x, p.y + it.dpt / 2, p.z); }
      else { _m.compose(p, Q_H, _s.set(it.w * s, it.dpt * s, 1)); A.setXYZW(j, it.kind === 'beam' ? 0 : sl.a * it.alpha, it.pulse, 0, i); sl.pr.set(p.x + it.w / 2 * s, p.y, p.z); }
      M.setMatrixAt(j, _m);
      if (it.halo) { _m.compose(p, Q_H, _s.set(it.w * 1.3 * s, it.dpt * 2.4 * s, 1)); A.setXYZW(j + 1, sl.a * it.haloA, it.pulse, 1, i); }
      else { _m.makeScale(0, 0, 0); A.setXYZW(j + 1, 0, 0, 1, i); }
      M.setMatrixAt(j + 1, _m);
    }
    M.count = n * 2; M.instanceMatrix.needsUpdate = true; A.needsUpdate = true;
  }
  animate() {
    const now = this.lt; let busy = false, dead = false;
    for (const sl of this.slots) {
      if (sl.done) { dead ||= sl.dead; continue; }
      const k = sl.dur > 0 ? clamp((now - sl.t0) / sl.dur, 0, 1) : 1, p = sl.p;
      if (sl.mode === FLY) { const e = outCubic(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = k > 0 ? 0.55 + 0.45 * outBack(k) : 0; sl.a = smooth(Math.min(1, k * 2.5)); }
      else if (sl.mode === MOVE) { const e = smooth(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = sl.s0 + (1 - sl.s0) * e; sl.a = sl.a0 + (1 - sl.a0) * e; }
      else { const e = smooth(k); p.copy(sl.p0); sl.s = sl.s0 * (1 - e * 0.4); sl.a = sl.a0 * (1 - e); }
      if (k >= 1) { sl.done = true; dead ||= sl.dead; } else busy = true;
    }
    if (!busy && dead) { this.slots = this.slots.filter((s) => !s.dead); this.writeStatic(); }
    this.writeDynamic();
    if (!busy) this.animating = false;
  }

  // ---------------------------------------------------------------- beam, trail, guides, labels
  frameScene() {
    const W = this.W, D = this.D, yA = this.yA, yB = this.yB, has = Number.isFinite(this.price), pos = this.pos;
    const x0 = -W / 2 - 0.5, xr = W / 2 + 0.14, zt = -D / 2 - 0.5;
    this.beamLen = W + 0.7; this.beam.visible = has; this.beam.position.set(0, 0, 0);
    this.spU.uLen.value = this.beamLen; this.sparks.visible = has;
    this.flare.visible = has; this.flare.position.set(W / 2 + 0.3, 0, 0);
    this.beamR.set(W / 2 + 0.34, 0, 0);
    // candle trail behind the ladder
    const bars = this.bars, n = has ? bars.length : 0, G = this.guides;
    const xl = -W / 2 + 0.1, dx = n ? (W - 0.5) / n : 0;
    const cUp = new THREE.Color(COL.up).multiplyScalar(0.42), cDn = new THREE.Color(COL.dn).multiplyScalar(0.42);
    for (let i = 0; i < n; i++) {
      const b = bars[i], up = b[4] >= b[1], x = xl + (i + 0.5) * dx, yo = this.Y(b[1]), yc = this.Y(b[4]), yh = this.Y(b[2]), yl = this.Y(b[3]);
      _m.compose(_v.set(x, (yo + yc) / 2, zt), Q_V, _s.set(dx * 0.6, Math.max(0.012, Math.abs(yc - yo)), 0.035));
      this.trail.setMatrixAt(i, _m); this.trail.setColorAt(i, up ? cUp : cDn);
      G.seg(x, yl, zt, x, yh, zt, up ? cUp : cDn, 0.55);
    }
    this.trail.count = n; this.trail.instanceMatrix.needsUpdate = true; if (this.trail.instanceColor) this.trail.instanceColor.needsUpdate = true;
    // the spine with "pts from price" ticks
    const vio = new THREE.Color('#8f86ff'), ticks = [];
    if (has) {
      G.seg(x0, -yB - 0.1, 0, x0, yA + 0.1, 0, vio, 0.3);
      G.seg(x0 - 0.12, 0, 0, x0 + 0.12, 0, 0, _c.set(COL.beam), 0.6);
      for (const sgn of [1, -1]) {
        let last = 0;
        for (const v of TICKS) {
          const y = this.k * Math.asinh(v / S_NEAR); if (y > (sgn > 0 ? yA : yB) + 0.02) break;
          if (y - last < 0.27) continue; last = y;
          G.seg(x0 - 0.08, sgn * y, 0, x0 + 0.08, sgn * y, 0, vio, 0.55); G.seg(x0, sgn * y, 0, -W / 2 + 0.1, sgn * y, 0, vio, 0.07, 4);
          ticks.push([v * sgn, sgn * y]);
        }
      }
    }
    G.commit();
    // camera anchors: the ladder box + room for the tick labels (left) and the plate labels (right)
    this.anchors = new Float32Array(corners([], x0 - 0.75, W / 2 + this.labelRoom, -yB - 0.35, yA + 0.4, zt - 0.2, D / 2 + 0.3));
    this.T.set(this.labelRoom * 0.2 - 0.2, (yA - yB) / 2, -0.15);
    // labels
    const defs = [], small = this.w < 520;
    if (has) defs.push({ html: `<i>price</i>${fmtPx(this.price)}`, at: () => this.beamR, ax: 0, dx: 8, cls: 'px', keep: true, show: () => this.beamS > 0.6 });
    const at = (sl) => () => (sl && !sl.dead && sl.a > 0.45 ? sl.pr : null);
    if (pos) {
      const R = pos.R, dirTxt = pos.dir > 0 ? 'long' : 'short';
      const posDef = (key, title, css, body) => defs.push({ html: `<b style="color:${css}">${title}</b><em>${body}</em>`, at: at(this.byKey.get(key)), ax: 0, dx: 8, cls: 'tag pos', avoid: true, keep: true,
        alts: [{ ax: 0, ay: 1, dx: 8, dy: -4 }, { ax: 0, ay: 0, dx: 8, dy: 4 }] });
      posDef('__stop', 'stop', CSS_C.stop, `${MINUS}1R · ${fmtPx(pos.stop)}`);
      if (Number.isFinite(pos.target)) posDef('__target', 'target', CSS_C.target, `${fmtRR(pos.tr)} · ${fmtPx(pos.target)}`);
      posDef('__entry', dirTxt, CSS_C.entry, `${fmtPx(pos.entry)} · 1R = ${Math.round(R)} pts`);
    }
    for (const it of this.items) {
      if (it.kind !== 'pool') continue;
      const sl = this.byKey.get(it.key);
      defs.push({ html: `${esc(trunc(it.label, small ? 14 : 22))}<em>${fmtPx(it.price)}</em>`, at: at(sl), ax: 0, dx: 8, cls: 'pl', color: it.css, avoid: true,
        alts: [{ ax: 1, dx: -6 }, { ax: 0, ay: 1, dx: 8, dy: -3 }] });
    }
    for (const [v, y] of ticks) defs.push({ text: (v < 0 ? MINUS : '+') + Math.abs(v), p: new THREE.Vector3(x0 - 0.1, y, 0), ax: 1, cls: 'h', avoid: true });
    if (has) defs.push({ text: 'pts from price', p: new THREE.Vector3(x0, yA + 0.12, 0), ax: 0.5, ay: 1, dy: -4, cls: 'h', avoid: true, keep: true });
    this.setLabels(defs);
    this.legendFor();
    const nA = this.pools.filter((p) => p.side === 'H').length, nB = this.pools.length - nA, up = this.pools.find((p) => p.rank === 0 && p.price >= this.price), dn = this.pools.find((p) => p.rank === 0 && p.price < this.price);
    this.hint.textContent = !has ? '' : !this.pools.length ? 'no untaken pools in range' : `${nA}↑ ${nB}↓ · nearest ${up ? fmtPts(up.dist, false) : '—'} up · ${dn ? fmtPts(dn.dist, false) : '—'} down${small ? '' : ' · tap a plate'}`;
  }
  legendFor() {
    const has = Number.isFinite(this.price), pos = this.pos;
    if (!has) { this.legend.innerHTML = ''; this.regionFix(); return; }
    const nA = this.pools.filter((p) => p.side === 'H').length, nB = this.pools.length - nA, dot = (c) => `<i style="background:${c};box-shadow:0 0 6px ${c}"></i>`;
    let h = `<span>${dot(CSS_C.bsl)}buy-side above <b>${nA}</b></span><span>${dot(CSS_C.ssl)}sell-side below <b>${nB}</b></span>`
      + `<span><i style="width:12px;height:3px;border-radius:2px;background:${CSS_C.beam};box-shadow:0 0 6px ${CSS_C.beam}"></i>price</span>`;
    if (pos) h += `<span>${dot(CSS_C.stop)}stop</span>` + (Number.isFinite(pos.target) ? `<span>${dot(CSS_C.target)}target <b>${fmtRR(pos.tr)}</b></span>` : '');
    this.legend.innerHTML = h;
    this.regionFix();
  }

  // ---------------------------------------------------------------- picking + tooltip
  // the plate whose centre line (left end -> right end, on screen) is nearest the point, within maxPx + half its depth
  nearest(px, py, maxPx) {
    const cam = this.camera; _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    let best = null, bd = Infinity;
    const scr = (x, y, z, out) => { out.set(x, y, z).applyMatrix4(_m); out.x = (out.x + 1) / 2 * this.w; out.y = (1 - out.y) / 2 * this.h; return out.z <= 1; };
    for (const sl of this.slots) {
      const it = sl.it;
      if (sl.dead || sl.a < 0.3 || it.kind === 'beam' || it.kind === 'slab') continue;
      const p = sl.p, hw = it.w / 2 * sl.s;
      if (!scr(p.x - hw, p.y, p.z, _v) || !scr(p.x + hw, p.y, p.z, _v2)) continue;
      const ax = _v.x, ay = _v.y, bx = _v2.x - ax, by = _v2.y - ay, L2 = bx * bx + by * by || 1;
      const t = clamp(((px - ax) * bx + (py - ay) * by) / L2, 0, 1), dx = ax + bx * t - px, dy = ay + by * t - py;
      scr(p.x, p.y, p.z + it.dpt / 2 * sl.s, _v); scr(p.x, p.y, p.z - it.dpt / 2 * sl.s, _v2);
      const half = Math.hypot(_v.x - _v2.x, _v.y - _v2.y) / 2, lim = maxPx + half, dd = dx * dx + dy * dy;
      if (dd < lim * lim && dd < bd) { bd = dd; best = sl; }
    }
    return best;
  }
  pickAt(px, py) { const sl = this.nearest(px, py, 18); this.select(sl); if (sl && sl.it.kind === 'pool') this.emit(sl.it.pool); }
  select(sl) { this.sel = sl; this.u.uSel.value = sl ? sl.idx : -1; this.tipFor(this.hov || sl); }
  hoverAt(sl) {
    if (sl === this.hov) return;
    this.hov = sl; this.u.uHov.value = sl ? sl.idx : -1; this.canvas.style.cursor = sl ? 'pointer' : 'grab';
    this.tipFor(sl || this.sel);
  }
  tipFor(sl) {
    if (!sl) { this.showTip(null); return; }
    const it = sl.it, pos = this.pos, inR = (pts) => (pos ? ` · <b>${fmtRR(pts / pos.R)}</b>` : '');
    let html;
    if (it.kind === 'pool') {
      const above = it.price >= this.price;
      html = `<b>${esc(it.label)}</b><u style="color:${it.css}">${it.side === 'H' ? 'buy-side' : 'sell-side'}</u><br><i>at</i> <b>${fmtPx(it.price)}</b> · <i>${above ? 'above' : 'below'}</i> <b>${fmtPts(Math.abs(it.dist), false)}</b>${inR(Math.abs(it.dist))}`
        + (it.strength !== 1 ? ` · <i>strength</i> <b>${+it.strength.toFixed(1)}</b>` : '');
    } else if (it.kind === 'stop') html = `<b style="color:${CSS_C.stop}">stop</b> <b>${fmtPx(pos.stop)}</b> · ${MINUS}1R <i>(${Math.round(pos.R)} pts)</i>`;
    else if (it.kind === 'target') html = `<b style="color:${CSS_C.target}">target</b> <b>${fmtPx(pos.target)}</b> · ${fmtRR(pos.tr)} <i>(${fmtPts(Math.abs(pos.target - pos.entry), false)})</i>`;
    else html = `<b>${pos.dir > 0 ? 'long' : 'short'}</b> <i>entry</i> <b>${fmtPx(pos.entry)}</b> · <i>now</i> <b>${fmtRR((this.price - pos.entry) * pos.dir / pos.R)}</b>`;
    this.showTip(sl.key, html);
  }
  devTapPoint() { const sl = this.slots.find((s) => !s.dead && s.a > 0.5 && s.it.kind === 'pool'); if (!sl) return null; const p = this.screen(sl.p); return [p.x, p.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u, o = this.orbit;
    u.uTime.value = lt;
    // slow drift: the pitch breathes while nobody touches it (the yaw drift comes from the shared orbit)
    if (!o.dragging && o.idle > 2.5 && !Q.reduced) o.pitch += (0.3 + 0.06 * Math.sin(lt * 0.23) - o.pitch) * Math.min(1, dt * 0.25);
    const moved = this.camStep(dt);
    if (this.animating) this.animate();
    // beam: ignites on the first data, then breathes
    let beamBusy = false;
    if (this.beamAt >= 0) { const k = clamp((lt - this.beamAt) / 0.7, 0, 1); this.beamS = outCubic(k); beamBusy = true; if (k >= 1) { this.beamAt = -1; this.camKey = ''; } }
    if (this.beam.visible) {
      const br = Q.reduced ? 1 : 1 + 0.08 * Math.sin(lt * 1.7), s = this.beamS;
      this.beam.scale.set(Math.max(0.001, this.beamLen * s), 0.026 * br, 0.026 * br);
      this.spU.uIn.value = s;
      this.flare.visible = s > 0.2; this.flare.scale.setScalar(0.55 * br * s); this.flare.material.opacity = 0.55 * s;
    }
    // price flash (HTML)
    const px = this.labels.find((l) => l.cls === 'px');
    if (px) { const on = this.flashAt >= 0 && lt - this.flashAt < 1.4; px.el.classList.toggle('up', on && this.flashDir === 'up'); px.el.classList.toggle('dn', on && this.flashDir === 'dn'); if (!on) this.flashAt = -1; }
    // selection ring at the plate's label end
    const s = this.sel;
    if (s && !s.dead) {
      const pulse = Q.reduced ? 1 : 1 + 0.08 * Math.sin(lt * 5);
      this.reticle.visible = true; this.reticle.position.copy(s.pr); this.reticle.scale.setScalar(0.22 * pulse);
      this.reticle.material.rotation = Q.reduced ? 0 : lt * 0.8; this.reticle.material.opacity = 0.9; this.reticle.material.color.copy(s.it.col).lerp(_c.set('#ffffff'), 0.6);
    } else this.reticle.visible = false;
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.nearest(hx, hy, 12)); }
    if (moved || this.animating || beamBusy) this.placeLabels();
    const ts = this.hov || this.sel;
    if (ts && this.tipKey != null) { const p = this.screen(ts.pr); this.placeTip(p.x, p.y, 14); }
  }
}
