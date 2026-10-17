// Week Ring (Today): the trading week as a glowing ring. Monday starts at 12 o'clock and the week runs clockwise to
//   Friday's close (120 hours around the circle, 72° a day). Every day is a segment of the outer ring: lit green when the
//   day made money, magenta when it lost (brighter the bigger the $), a dim lavender when it finished without a trade, a
//   faint track with hourly dashes while it is still ahead. A pearl sits on the ring for every trade at its entry time
//   (size by |$|, colour by sign, a lavender pearl for a scratch); the inner ring carries the killzones (09:30-11:30 and
//   13:30-15:30 ET) as cyan arcs inside every day, today's pulsing while the clock is inside one, with a faint band for
//   the rest of the cash session. The current moment is a clock hand from the hub to the bezel with a comet trailing
//   behind it along the ring; the bezel has hour ticks, 6-hour marks and day majors, and a scanner glow at the hand.
//   HTML centre readout: the week's $ (counts to new values), a pill meter of trades this week against the 2-4 target
//   (target pills outlined, extra ones amber), and the days left. Day labels around the ring with each day's $.
//   Tap a pearl -> opts.onPick(trade) (the page's own trade object); mouse hover shows the tooltip; drag to tilt.
//   First data: the hand sweeps from Monday to now and lights the days as it passes, pearls drop onto the ring when it
//   reaches them. New data: pearls glide / drop in / fade out, a changed day flashes, the hand eases to the new time.
// setData({ days: [{ date: 'YYYY-MM-DD', dow: 0-4 (Mon-Fri), trades: [{ r, pnl, t (epoch s) }], pnl, sessions_done }],
//           now: epoch s, target_week_trades: [2, 4] })
//   Days are placed by dow (or by their date); missing days are shown as empty. An empty week (no trades) is a valid
//   week: $0, 0 of 2-4, the hand still runs. No days and no `now` -> "No week data yet". Under 250 px tall the centre
//   readout is compact ($ and trade count only).
// Draw calls ~13 (+1 while a pearl is selected); particles: 190 comet sparks (70 lite) + 500 dust (200 lite) + 1 per trade.
import { THREE, Q, theme, glowTexture, POINT_FRAG, count, rng, Hud, addBackdrop, addNebula, addDust, ringTexture, sprite, additive, attrs,
  paintBackdrop, clamp, smooth, outCubic, outBack, num, esc, hash, fmtUsd, fmtR, div, injectStyle } from './hud.js';

const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
const R0 = 1.4, R1 = 1.66, RM = 1.53, KZ0 = 1.19, KZ1 = 1.29, BZ0 = 1.75, BZ1 = 1.86, RL = 2.04, TILT = -0.72, TAU = Math.PI * 2;
const FLY = 1, MOVE = 2, SHRINK = 4;
const GOOD = '#2ee59d', BAD = '#ff2bd6', FLAT = '#c3c6e6', CSS_GOOD = '#4ef0b0', CSS_BAD = '#ff7ad9';
const _v = new THREE.Vector3(), _w = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color();

// ------------------------------------------------------------------ time helpers (everything on the ring is New York time)
let _fmt = null;
const pad2 = (n) => String(n).padStart(2, '0');
// epoch s -> { dow: 0 Mon .. 6 Sun, frac: share of the day gone, date: 'YYYY-MM-DD', hm: 'HH:MM' } in ET
export function etParts(unix) {
  const d = new Date(unix * 1000);
  try {
    _fmt ||= new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    const P = {}; for (const p of _fmt.formatToParts(d)) P[p.type] = p.value;
    const h = (+P.hour) % 24, m = +P.minute;
    return { dow: (Math.max(0, WD.indexOf(P.weekday)) + 6) % 7, frac: (h + m / 60) / 24, date: `${P.year}-${P.month}-${P.day}`, hm: `${pad2(h)}:${pad2(m)}` };
  } catch {
    const e = new Date(d.getTime() - 4 * 3600e3), h = e.getUTCHours(), m = e.getUTCMinutes();   // EDT fallback
    return { dow: (e.getUTCDay() + 6) % 7, frac: (h + m / 60) / 24, date: e.toISOString().slice(0, 10), hm: `${pad2(h)}:${pad2(m)}` };
  }
}
const parseDate = (s) => { const t = Date.parse(String(s ?? '').slice(0, 10) + 'T00:00:00Z'); return Number.isFinite(t) ? t / 1000 : NaN; };
const dayStr = (t) => new Date(t * 1000).toISOString().slice(0, 10);
const inKz = (h) => (h >= 9.5 && h < 11.5) || (h >= 13.5 && h < 15.5);

// ------------------------------------------------------------------ shaders
const RING_V = `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
// outer ring: five day segments. uDay[i] = (lit share of the day, P&L -1..1 of the week's biggest day, has trades, flash)
const DAY_F = `uniform float uR0; uniform float uR1; uniform float uTime; uniform float uMotion; uniform float uIn; uniform float uA;
uniform vec3 uGood; uniform vec3 uBad; uniform vec3 uTrack; uniform vec3 uFlat; uniform vec4 uDay[5];
varying vec2 vP;
void main(){
  float r = length(vP), rr = clamp((r - uR0) / (uR1 - uR0), 0.0, 1.0);
  float a = fract(atan(vP.x, vP.y) / 6.2831853 + 1.0);
  float a5 = a * 5.0, di = floor(a5), f = a5 - di;
  vec4 D = vec4(0.0);
  for (int k = 0; k < 5; k++) if (float(k) == di) D = uDay[k];
  float gap = smoothstep(0.0, 0.02, f) * smoothstep(1.0, 0.98, f);
  float prof = exp(-pow((rr - 0.5) * 3.0, 2.0)), edge = exp(-pow((rr - 0.5) * 9.0, 2.0));
  float rim = exp(-pow((abs(rr - 0.5) - 0.42) * 14.0, 2.0));
  float t = uTime * uMotion;
  float reveal = smoothstep(a, a + 0.012, uIn);
  float lit = smoothstep(D.x, D.x - 0.012, f) * step(0.0005, D.x) * reveal;
  float head = exp(-pow((f - D.x) * 45.0, 2.0)) * step(0.0005, D.x) * step(D.x, 0.9995) * reveal;
  float mag = abs(D.y), has = D.z;
  vec3 pc = mix(uBad, uGood, step(0.0, D.y));
  vec3 col = mix(uFlat * 0.42, pc * (0.5 + 0.8 * sqrt(mag)), has);
  float shimmer = exp(-pow((fract(a * 3.0 - t * 0.09) - 0.5) * 8.0, 2.0)) * 0.45 * has;
  float dash = step(0.55, fract(f * 24.0)) * 0.05 * (1.0 - lit);
  vec3 c = uTrack * (0.07 + 0.09 * edge + dash) * gap;
  c += col * lit * gap * (prof * 0.7 + edge * 0.55 + rim * 0.3) * (1.0 + shimmer);
  c += mix(pc, vec3(1.0), 0.6) * head * prof * 1.6 * gap * has;
  c += mix(uFlat, vec3(1.0), 0.5) * head * prof * 0.9 * gap * (1.0 - has);
  c += col * D.w * gap * (prof * 1.2 + edge);
  gl_FragColor = vec4(c * uA, 1.0);
}`;
// inner ring: the killzones of every day (today's pulse while the clock is inside one), the cash session as a faint band
const KZ_F = `uniform float uR0; uniform float uR1; uniform float uTime; uniform float uMotion; uniform float uIn; uniform float uA; uniform float uToday; uniform float uActive;
uniform vec3 uKz; uniform vec3 uRth; varying vec2 vP;
void main(){
  float r = length(vP), rr = clamp((r - uR0) / (uR1 - uR0), 0.0, 1.0);
  float a = fract(atan(vP.x, vP.y) / 6.2831853 + 1.0);
  float a5 = a * 5.0, di = floor(a5), h = (a5 - di) * 24.0;
  float kz = smoothstep(9.5, 9.6, h) * smoothstep(11.5, 11.4, h) + smoothstep(13.5, 13.6, h) * smoothstep(15.5, 15.4, h);
  float rth = smoothstep(9.5, 9.6, h) * smoothstep(16.0, 15.9, h);
  float pre = smoothstep(8.0, 8.1, h) * smoothstep(9.5, 9.4, h);
  float today = 1.0 - step(0.5, abs(di - uToday));
  float t = uTime * uMotion;
  float prof = exp(-pow((rr - 0.5) * 2.8, 2.0));
  float reveal = smoothstep(a, a + 0.012, uIn);
  float flow = 0.75 + 0.25 * sin(h * 6.0 - t * 2.5);
  float k = kz * (0.42 + today * (0.5 + uActive * (0.35 + 0.35 * sin(t * 3.2)))) * flow;
  vec3 c = uKz * k * prof + uRth * (rth * 0.1 + pre * 0.06) * prof;
  gl_FragColor = vec4(c * reveal * uA, 1.0);
}`;
// bezel: hour ticks, 6-hour marks, day majors, a scanner glow at the hand
const BEZEL_F = `uniform vec3 uCol; uniform float uTime; uniform float uMotion; uniform float uHand; uniform float uIn; varying vec2 vP;
float tk(float x, float w){ return step(1.0 - w, fract(x + 0.5 * w)); }
void main(){
  float r = length(vP), rr = clamp((r - ${BZ0.toFixed(3)}) / ${(BZ1 - BZ0).toFixed(3)}, 0.0, 1.0);
  float a = fract(atan(vP.x, vP.y) / 6.2831853 + 1.0);
  float hour = tk(a * 120.0, 0.18) * step(0.55, rr), six = tk(a * 20.0, 0.1) * step(0.3, rr), major = tk(a * 5.0, 0.018);
  float scan = exp(-pow((fract(a - uHand + 0.5) - 0.5) * 8.0, 2.0)) * 0.6;
  float line = exp(-pow((rr - 0.1) * 20.0, 2.0));
  float reveal = smoothstep(a, a + 0.012, uIn);
  gl_FragColor = vec4(uCol * (line * (0.3 + scan) + hour * 0.16 * (1.0 + scan * 2.5) + six * 0.25 + major * 0.9) * (0.35 + 0.65 * reveal), 1.0);
}`;
// comet: sparks flowing back along the ring behind the hand
const COMET_V = `attribute float aSeed; attribute float aS; attribute float aJ;
uniform float uTime; uniform float uMotion; uniform float uPix; uniform float uHand; uniform float uR; uniform float uTrail; uniform float uBright; uniform vec3 uCol;
varying vec3 vColor; varying float vAlpha;
void main(){
  float ph = fract(aSeed + uTime * uMotion * (0.22 + aJ * 0.3));
  float ang = (uHand - ph * uTrail) * 6.2831853;
  float r = uR + (aJ - 0.5) * 0.24 * (0.25 + ph);
  vec3 p = vec3(sin(ang) * r, cos(ang) * r, 0.07 + (aSeed - 0.5) * 0.14 * ph);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp(aS * uPix * (1.0 - ph * 0.7) / -mv.z, 0.0, 26.0);
  gl_Position = projectionMatrix * mv;
  vColor = mix(vec3(1.0), uCol, ph * 0.85) * uBright; vAlpha = (1.0 - ph) * (1.0 - ph) * smoothstep(0.0, 0.04, ph);
}`;
// pearls: a glossy bead with a soft halo; selected / hovered ones get a bright rim
const PEARL_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; attribute vec4 aMisc;
uniform float uTime; uniform float uPix; uniform float uMotion; uniform float uSel; uniform float uHov;
varying vec3 vColor; varying float vAlpha; varying float vHi;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float tw = 1.0 + 0.07 * sin(uTime * uMotion * (1.3 + aMisc.x * 2.0) + aMisc.x * 50.0);
  vHi = max(1.0 - step(0.5, abs(aMisc.y - uSel)), (1.0 - step(0.5, abs(aMisc.y - uHov))) * 0.75);
  gl_PointSize = clamp(aSize * uPix * tw * (1.0 + vHi * 0.5) / -mv.z, 0.0, 120.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol; vAlpha = aAlpha;
}`;
const PEARL_F = `varying vec3 vColor; varying float vAlpha; varying float vHi;
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2), halo = 1.0 - d2; halo = halo * halo * halo;
  float body = smoothstep(0.6, 0.48, d);
  vec2 s = q - vec2(-0.08, -0.1); float spec = exp(-dot(s, s) * 90.0);
  float rim = exp(-pow((d - 0.54) * 12.0, 2.0)) * 0.6;
  float hi = vHi * exp(-pow((d - 0.86) * 10.0, 2.0));
  vec3 c = vColor * (halo * 0.35 + body * 0.75 + rim) + vec3(1.0) * (spec * body * 0.9 + hi * 0.9);
  gl_FragColor = vec4(c * vAlpha, 1.0);
}`;

const CSS = `.fxw-c{position:absolute;left:0;top:0;text-align:center;white-space:nowrap;line-height:1}
.fxw-cap{font-size:8.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(214,218,250,.62);margin-bottom:5px;text-shadow:0 0 6px #07080c}
.fxw-pnl{font-size:26px;font-weight:800;letter-spacing:-.01em;color:#fff;text-shadow:0 0 16px rgba(5,3,14,.95),0 0 4px rgba(5,3,14,.95),0 0 26px rgba(0,0,0,.6)}
.fxw-meter{display:flex;justify-content:center;gap:4px;margin:7px 0 6px}
.fxw-meter i{display:block;width:13px;height:5px;border-radius:3px;background:rgba(150,140,220,.16);border:1px solid transparent;box-sizing:border-box}
.fxw-meter i.tgt{border-color:rgba(167,139,250,.5)}
.fxw-meter i.on{background:#2ee5c8;box-shadow:0 0 8px #2ee5c8}
.fxw-meter i.on.over{background:#ffb347;box-shadow:0 0 8px #ffb347}
.fxw-sub{font-size:11px;font-weight:700;color:rgba(214,218,250,.8);text-shadow:0 0 8px rgba(5,3,14,.95),0 0 3px rgba(5,3,14,.95)}
.fxw-sub b{color:#eef0fb}
.fxw-left{margin-top:4px;font-size:10px;font-weight:600;letter-spacing:.02em;color:rgba(188,192,236,.66);text-shadow:0 0 6px #07080c}
.fxh-weekring .fxh-l.dl{font-size:10px;font-weight:700;letter-spacing:.02em;color:rgba(214,218,250,.78);text-align:center;line-height:1.2;text-shadow:0 0 8px #07080c,0 0 3px #07080c}
.fxh-weekring .fxh-l.dl em{display:block;font-style:normal;font-size:9px;font-weight:700;color:rgba(188,192,236,.5)}
.fxh-weekring .fxh-l.dl.cur{color:#fff}
.fxh-weekring .fxh-l.dl.fut{color:rgba(188,192,236,.42)}
.fxh-weekring.compact .fxw-cap,.fxh-weekring.compact .fxw-meter,.fxh-weekring.compact .fxw-left{display:none}
.fxh-weekring.compact .fxw-pnl{font-size:20px}.fxh-weekring.compact .fxw-sub{font-size:10px}`;

// ------------------------------------------------------------------ the view
export class WeekRing extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'weekring', fov: 34, empty: 'No week data yet', orbit: { yaw: 0, pitch: 0.1, auto: 0, min: -0.6, max: 0.6, pitchMin: -0.15, pitchMax: 0.55 } });
    injectStyle('fxh-wr-css', CSS);
    this.days = []; this.slots = []; this.byKey = new Map(); this.cap = 0; this.animating = false; this.hasData = false; this.sig = null; this.nowKey = ''; this.info = null;
    this.hand = 0; this.handTo = 0; this.introAt = -1; this.sel = null; this.hov = null; this.flash = new Float32Array(5);
    this.pnlFrom = 0; this.pnlTo = 0; this.pnlAt = -9; this.pnlTxt = ''; this.cenLast = null;
    Object.assign(this.u, { uSel: { value: -1 }, uHov: { value: -1 }, uHand: { value: 0 }, uIn: { value: 2 }, uBright: { value: 1 }, uR: { value: RM }, uTrail: { value: 0.07 },
      uCol: { value: new THREE.Color('#8fe3ff') } });
    this.build(); this.ensureCap(32); this.buildHtml();
  }
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.52]);
    addNebula(S, [['#6d28d9', -3.5, 2.2, -6, 9, 6, 0.1], ['#ff2bd6', 3.2, -1.6, -6, 8, 5, 0.05]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 420 : 500, 200), box: [4, 3, 2], cy: 0, seed: 77 });
    const g = this.g = new THREE.Group(); g.rotation.x = TILT; S.add(g);
    const spr = (col, scale, op, order) => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(col), transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false })); s.scale.setScalar(scale); s.renderOrder = order; g.add(s); return s; };
    this.hub = spr('#5b3bd1', 2.7, 0.22, 1);
    // rings
    this.dayU = Array.from({ length: 5 }, () => new THREE.Vector4());
    this.dU = { uR0: { value: R0 }, uR1: { value: R1 }, uTime: u.uTime, uMotion: u.uMotion, uIn: u.uIn, uA: { value: 1 }, uGood: { value: theme.good.clone() }, uBad: { value: new THREE.Color(BAD) },
      uTrack: { value: new THREE.Color('#5b6cff') }, uFlat: { value: new THREE.Color('#9a94d8') }, uDay: { value: this.dayU } };
    this.dayRing = new THREE.Mesh(new THREE.RingGeometry(R0 - 0.02, R1 + 0.02, 240, 1), additive(RING_V, DAY_F, this.dU, { side: THREE.DoubleSide })); this.dayRing.renderOrder = 5; g.add(this.dayRing);
    this.kU = { uR0: { value: KZ0 }, uR1: { value: KZ1 }, uTime: u.uTime, uMotion: u.uMotion, uIn: u.uIn, uA: { value: 1 }, uToday: { value: -1 }, uActive: { value: 0 },
      uKz: { value: new THREE.Color('#22d3ee') }, uRth: { value: new THREE.Color('#6d7cff') } };
    this.kzRing = new THREE.Mesh(new THREE.RingGeometry(KZ0 - 0.02, KZ1 + 0.02, 200, 1), additive(RING_V, KZ_F, this.kU, { side: THREE.DoubleSide })); this.kzRing.renderOrder = 4; g.add(this.kzRing);
    this.bU = { uCol: { value: new THREE.Color('#7c6cff') }, uTime: u.uTime, uMotion: u.uMotion, uHand: u.uHand, uIn: u.uIn };
    this.bezel = new THREE.Mesh(new THREE.RingGeometry(BZ0, BZ1, 240, 1), additive(RING_V, BEZEL_F, this.bU, { side: THREE.DoubleSide })); this.bezel.renderOrder = 3; g.add(this.bezel);
    // the hand: hub -> ring (dim to bright), ring -> past the bezel (bright to dim)
    const hg = new THREE.BufferGeometry();
    hg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(12), 3).setUsage(THREE.DynamicDrawUsage));
    hg.setAttribute('color', new THREE.BufferAttribute(new Float32Array([0.12, 0.2, 0.28, 0.55, 0.85, 1, 0.75, 1, 1.1, 0.1, 0.18, 0.22]), 3));
    this.handLine = new THREE.LineSegments(hg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.handLine.renderOrder = 7; this.handLine.visible = false; g.add(this.handLine);
    this.head = spr('#dffaff', 0.42, 0.9, 10); this.head.visible = false;
    // comet sparks
    const N = count(Q.phone ? 150 : 190, 70), cg = attrs(N, { position: [3], aSeed: [1], aS: [1], aJ: [1] }), R = rng(5);
    for (let i = 0; i < N; i++) { cg.attributes.aSeed.setX(i, R()); cg.attributes.aS.setX(i, 0.03 + R() * 0.05); cg.attributes.aJ.setX(i, R()); }
    this.comet = new THREE.Points(cg, additive(COMET_V, POINT_FRAG, u)); this.comet.renderOrder = 9; this.comet.visible = false; g.add(this.comet);
    // selection reticle (a child of the tilted group so it lives in ring space)
    const ret = ringTexture(true); this.textures.push(ret);
    this.reticle = sprite(S, ret, '#ffffff', 12); g.add(this.reticle);
    S.traverse((o) => { o.frustumCulled = false; });
    // camera anchors: a circle with room for the day labels, a little depth
    const P = [];
    for (let i = 0; i < 24; i++) { const a = i / 24 * TAU; this.world(a, 2.22, 0, _w); P.push(_w.x, _w.y, _w.z); }
    _v.set(0, 0, 0.5).applyEuler(g.rotation); P.push(_v.x, _v.y, _v.z, -_v.x, -_v.y, -_v.z);
    this.anchors = new Float32Array(P); this.T.set(0, 0, 0); this.fill = [0.92, 0.9];
  }
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(32, Math.ceil(n * 1.25 / 16) * 16);
    const pg = attrs(cap, { position: [3, 1], aCol: [3], aSize: [1, 1], aAlpha: [1, 1], aMisc: [4] });
    if (!this.pearls) { this.pearls = new THREE.Points(pg, additive(PEARL_V, PEARL_F, this.u)); this.pearls.renderOrder = 8; this.pearls.frustumCulled = false; this.g.add(this.pearls); }
    else { this.pearls.geometry.dispose(); this.pearls.geometry = pg; }
    this.cap = cap;
  }
  buildHtml() {
    this.cen = div('fxw-c', this.ui, '<div class="fxw-cap">this week</div><div class="fxw-pnl">—</div><div class="fxw-meter"></div><div class="fxw-sub"></div><div class="fxw-left"></div>');
    this.cen.style.visibility = 'hidden';
    this.pnlEl = this.cen.querySelector('.fxw-pnl'); this.meterEl = this.cen.querySelector('.fxw-meter'); this.subEl = this.cen.querySelector('.fxw-sub'); this.leftEl = this.cen.querySelector('.fxw-left');
    this.legend = div('fxh-leg'); this.ui.prepend(this.legend);
    this.hint = div('fxh-l h fix', this.ui);
  }
  // ring space (angle in radians from 12 o'clock clockwise, radius, height) -> world
  world(ang, r, z, out = _w) { return out.set(Math.sin(ang) * r, Math.cos(ang) * r, z).applyEuler(this.g.rotation); }
  retheme() { paintBackdrop(this.bgU); this.dU.uGood.value.copy(theme.good); }
  relayout(w, h) {
    const compact = h < 250; this.ui.classList.toggle('compact', compact);
    const lh = this.legend.isConnected ? this.legend.offsetHeight : 14;
    this.region = compact ? [-1, 1, -1 + 2 * 8 / h, 1 - 2 * 8 / h] : [-1, 1, -1 + 2 * 18 / h, 1 - 2 * (lh + 12) / h];
    this.cenW = this.cen.offsetWidth; this.cenH = this.cen.offsetHeight; this.cenLast = null;
    this.Lset = false;
  }
  attach(el) { super.attach(el); this.relayout(this.w, this.h); }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' ? (Array.isArray(d) ? { days: d } : d) : null;
    const list = src && Array.isArray(src.days) ? src.days : [];
    let nowS = src ? num(src.now, NaN) : NaN; if (nowS > 1e11) nowS /= 1000;
    const hasNow = Number.isFinite(nowS); if (!hasNow) nowS = Date.now() / 1000;
    const tgt = src && Array.isArray(src.target_week_trades) ? src.target_week_trades.map((v) => num(v, NaN)) : [];
    const lo = Number.isFinite(tgt[0]) ? Math.max(0, Math.round(tgt[0])) : 2, hi = Number.isFinite(tgt[1]) ? Math.max(lo, Math.round(tgt[1])) : Math.max(lo, 4);
    const has = !!src && (list.length > 0 || hasNow);
    // the five days, placed by dow (or by date)
    const days = DOW.map((name, i) => ({ i, name, date: '', dom: '', trades: [], pnl: 0, done: false, has: false, raw: null }));
    list.forEach((r, idx) => {
      if (!r || typeof r !== 'object') return;
      let w = num(r.dow, NaN);
      if (!(w >= 0 && w <= 4)) { const p = parseDate(r.date); w = Number.isFinite(p) ? (new Date(p * 1000).getUTCDay() + 6) % 7 : idx; }
      w = Math.round(w); if (!(w >= 0 && w <= 4)) return;
      const D = days[w]; D.raw = r; D.done = !!r.sessions_done;
      if (typeof r.date === 'string' && r.date.length >= 10) D.date = r.date.slice(0, 10);
      const tr = Array.isArray(r.trades) ? r.trades : [];
      tr.forEach((t, j) => {
        if (!t || typeof t !== 'object') return;
        let ts = num(t.t, NaN); if (ts > 1e11) ts /= 1000;
        D.trades.push({ t, pnl: num(t.pnl, 0), r: num(t.r, NaN), ts, j });
      });
      const p = num(r.pnl, NaN); D.pnl = Number.isFinite(p) ? p : D.trades.reduce((s, x) => s + x.pnl, 0);
      D.has = D.trades.length > 0 || (Number.isFinite(p) && Math.abs(p) >= 0.5);
    });
    const known = days.find((D) => D.date), base = known ? parseDate(known.date) : NaN;
    for (const D of days) { if (!D.date && Number.isFinite(base)) D.date = dayStr(base + (D.i - known.i) * 86400); D.dom = D.date ? String(+D.date.slice(8, 10) || '') : ''; }
    // now -> the hand (turns, 0 = Monday 00:00 ET, 1 = Friday 24:00)
    const N = etParts(nowS), dates = days.map((D) => D.date).filter(Boolean);
    let today = -1, hand;
    const m = days.find((D) => D.date && D.date === N.date);
    if (m) { today = m.i; hand = (m.i + N.frac) / 5; }
    else if (dates.length && N.date > dates[dates.length - 1]) hand = 1;
    else if (dates.length && N.date < dates[0]) hand = 0;
    else if (N.dow < 5) { today = N.dow; hand = (N.dow + N.frac) / 5; }
    else hand = 1;
    const hour = N.frac * 24, active = today >= 0 && inKz(hour) ? 1 : 0;
    for (const D of days) {
      D.state = D.done || D.has || D.i < today || (today < 0 && hand >= 1) ? 'done' : D.i === today ? 'cur' : 'fut';
      if (D.i === today && !D.done) D.state = 'cur';
    }
    let left;
    if (today < 0) left = hand >= 1 ? 'week done' : 'starts Monday';
    else { const n = 4 - today; left = n <= 0 ? (hour < 16 ? 'last day' : 'week done') : `${n} day${n > 1 ? 's' : ''} left`; }
    const n = days.reduce((s, D) => s + D.trades.length, 0), pnl = days.reduce((s, D) => s + D.pnl, 0);
    const maxAbs = Math.max(1, ...days.map((D) => Math.abs(D.pnl)));
    const sig = (has ? 1 : 0) + '|' + lo + '-' + hi + '|' + JSON.stringify(days.map((D) => [D.date, D.done, Math.round(D.pnl * 100), D.trades.map((x) => [x.ts, Math.round(x.pnl * 100), x.r])]));
    const nowKey = hand.toFixed(4) + '|' + today + '|' + left + '|' + active + '|' + N.hm;
    const info = { n, pnl, lo, hi, has, left, today, hand, active, N, maxAbs };
    if (sig === this.sig) {
      // the same week: keep the page's trade objects fresh, move the hand if the clock moved
      for (const D of days) for (const x of D.trades) { const sl = this.byKey.get(this.keyOf(D, x)); if (sl) sl.it.t = x.t; }
      if (nowKey !== this.nowKey) { this.nowKey = nowKey; this.days = days; this.info = info; this.applyNow(); this.labelsFor(); this.writeHtml(); }
      return;
    }
    const first = !this.hasData, red = Q.reduced, now = this.lt, prev = this.days;
    if (this.hasData && !red) days.forEach((D, i) => { if (prev[i] && Math.abs(D.pnl - prev[i].pnl) >= 0.5) this.flash[i] = 1; });
    this.sig = sig; this.nowKey = nowKey; this.days = days; this.info = info;
    // pearls
    const items = [];
    let maxT = 1;
    for (const D of days) for (const x of D.trades) maxT = Math.max(maxT, Math.abs(x.pnl));
    for (const D of days) D.trades.forEach((x, j) => {
      const frac = Number.isFinite(x.ts) ? etParts(x.ts).frac : (10.5 + j * 1.5) / 24;
      const key = this.keyOf(D, x);
      items.push({ key, t: x.t, pnl: x.pnl, r: x.r, ts: x.ts, day: D, ang: (D.i + frac) / 5, rad: RM, seed: hash(key), size: 0.15 + 0.2 * Math.sqrt(Math.abs(x.pnl) / maxT),
        scratch: Math.abs(x.pnl) < 0.03 * maxT || (Number.isFinite(x.r) && Math.abs(x.r) < 0.1) });
    });
    items.sort((a, b) => a.ang - b.ang);
    for (let i = 1, k = 0; i < items.length; i++) { if (items[i].ang - items[i - 1].ang < 0.006) { k++; items[i].rad = RM + (k % 2 ? 0.15 : -0.15) * Math.ceil(k / 2); } else k = 0; }
    const next = [], keep = new Set();
    for (const it of items) {
      let sl = this.byKey.get(it.key);
      if (sl && !sl.dead) { sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.mode = MOVE; sl.t0 = now; sl.dur = red ? 0 : 0.8; sl.wait = false; }
      else {
        sl = { key: it.key, p: new THREE.Vector3(), p0: new THREE.Vector3(), p1: new THREE.Vector3(), s: 0, s0: 0, a: 0, a0: 0, dead: false, done: false, col: new THREE.Color(), wait: false };
        sl.mode = FLY; sl.dur = red ? 0 : 0.7;
        if (first && !red) { sl.wait = true; sl.t0 = Infinity; } else sl.t0 = red ? now : now + 0.05 + it.seed * 0.3;
      }
      sl.it = it; sl.ang = it.ang; sl.done = false;
      const x = Math.sin(it.ang * TAU) * it.rad, y = Math.cos(it.ang * TAU) * it.rad;
      sl.p1.set(x, y, 0.1); if (sl.mode === FLY) { sl.p0.set(x, y, 0.8); sl.p.copy(sl.p0); }
      keep.add(it.key); next.push(sl);
    }
    for (const sl of this.slots) {
      if (keep.has(sl.key) || sl.dead) continue;
      sl.dead = true; sl.done = false; sl.mode = SHRINK; sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.t0 = now; sl.dur = red ? 0 : 0.45; sl.wait = false; next.push(sl);
    }
    this.slots = next; this.byKey.clear();
    for (const sl of next) if (!sl.dead) this.byKey.set(sl.key, sl);
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.hoverAt(null);
    this.recolor(); this.writeStatic(); this.animating = true;
    // the hand: a sweep from Monday on the first data, an ease afterwards
    this.handTo = hand;
    if (first && has) { if (red) { this.hand = hand; this.u.uIn.value = 2; } else { this.hand = 0; this.u.uIn.value = 0; this.introAt = now; } }
    // the $ counter
    this.pnlFrom = first ? 0 : this.dispPnl(); this.pnlTo = pnl; this.pnlAt = first && !red ? now + 0.25 : now;
    this.hasData = has;
    this.applyNow(); this.labelsFor(); this.writeHtml(); this.legendFor();
    this.empty.style.display = has ? 'none' : 'block';
    this.cen.style.visibility = has ? 'visible' : 'hidden';
    this.handLine.visible = this.head.visible = this.comet.visible = has;
    this.ui.classList.add('on');
    this.relayout(this.w, this.h);
    this.tipKey = null; this.tipFor(this.hov || this.sel);
  }
  keyOf(D, x) { return D.i + '|' + (Number.isFinite(x.ts) ? x.ts : 'j' + x.j) + '|' + Math.round(x.pnl * 100) + '|' + x.r; }
  applyNow() {
    const I = this.info; if (!I) return;
    this.handTo = I.hand;
    if (Q.reduced || !this.hasData) this.hand = I.hand;
    if (Math.abs(I.hand - this.hand) > 0.5 && this.introAt < 0) this.hand = I.hand;   // a new week: no backwards sweep
    this.kU.uToday.value = I.today; this.kU.uActive.value = I.active;
  }
  recolor() {
    for (const sl of this.slots) {
      const it = sl.it;
      sl.col.set(it.scratch ? FLAT : it.pnl >= 0 ? GOOD : BAD).multiplyScalar(it.scratch ? 0.8 : 1.1);
      sl.css = it.scratch ? FLAT : it.pnl >= 0 ? CSS_GOOD : CSS_BAD;
    }
  }
  writeStatic() {
    const n = this.slots.length; this.ensureCap(n);
    const P = this.pearls.geometry.attributes;
    for (let i = 0; i < n; i++) { const sl = this.slots[i], c = sl.col; sl.idx = i; P.aCol.setXYZ(i, c.r, c.g, c.b); P.aMisc.setXYZW(i, sl.it.seed, i, 0, 0); }
    P.aCol.needsUpdate = P.aMisc.needsUpdate = true;
    this.pearls.geometry.setDrawRange(0, n);
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
  }
  writeDynamic() {
    const n = this.slots.length, P = this.pearls.geometry.attributes, PP = P.position.array, PZ = P.aSize.array, PA = P.aAlpha.array;
    for (let i = 0; i < n; i++) { const sl = this.slots[i], p = sl.p; PP[i * 3] = p.x; PP[i * 3 + 1] = p.y; PP[i * 3 + 2] = p.z; PZ[i] = sl.it.size * sl.s; PA[i] = sl.a; }
    P.position.needsUpdate = P.aSize.needsUpdate = P.aAlpha.needsUpdate = true;
  }
  animate() {
    const now = this.lt; let busy = false, dead = false;
    for (const sl of this.slots) {
      if (sl.done) { dead ||= sl.dead; continue; }
      if (sl.wait) { busy = true; continue; }
      const k = sl.dur > 0 ? clamp((now - sl.t0) / sl.dur, 0, 1) : 1, p = sl.p;
      if (sl.mode === FLY) { const e = outCubic(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = k > 0 ? 0.3 + 0.7 * outBack(k) : 0; sl.a = smooth(Math.min(1, k * 3)); }
      else if (sl.mode === MOVE) { const e = smooth(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = sl.s0 + (1 - sl.s0) * e; sl.a = sl.a0 + (1 - sl.a0) * e; }
      else { const e = smooth(k); p.copy(sl.p0); sl.s = sl.s0 * (1 - e); sl.a = sl.a0 * (1 - e); }
      if (k >= 1) { sl.done = true; dead ||= sl.dead; } else busy = true;
    }
    if (!busy && dead) { this.slots = this.slots.filter((s) => !s.dead); this.writeStatic(); }
    this.writeDynamic();
    if (!busy) this.animating = false;
  }

  // ---------------------------------------------------------------- html: centre readout, legend, hint, day labels
  dispPnl() { const k = Q.reduced ? 1 : clamp((this.lt - this.pnlAt) / 1.1, 0, 1); return this.pnlFrom + (this.pnlTo - this.pnlFrom) * outCubic(k); }
  writeHtml() {
    const I = this.info;
    if (!I || !I.has) { this.meterEl.innerHTML = ''; this.subEl.innerHTML = ''; this.leftEl.textContent = ''; this.hint.textContent = ''; return; }
    const { n, lo, hi } = I, pills = Math.min(8, Math.max(hi, n, 1));
    this.meterEl.innerHTML = Array.from({ length: pills }, (_, k) => `<i class="${k < n ? 'on' : ''}${k + 1 >= lo && k + 1 <= hi ? ' tgt' : ''}${k + 1 > hi ? ' over' : ''}"></i>`).join('');
    const st = n < lo ? ['rgba(214,218,250,.7)', `${lo - n} to go`] : n <= hi ? [CSS_GOOD, 'on target'] : ['#ffb347', 'over target'];
    this.subEl.innerHTML = `<b>${n}</b> of ${lo}-${hi} trades · <span style="color:${st[0]}">${st[1]}</span>`;
    this.leftEl.textContent = (I.today >= 0 ? DOW[I.today] + ' · ' : '') + I.left;
    this.hint.textContent = n ? `${n} trade${n === 1 ? '' : 's'} this week · tap a pearl` : 'no trades yet this week';
    this.cenW = this.cen.offsetWidth; this.cenH = this.cen.offsetHeight; this.cenLast = null;
  }
  legendFor() {
    this.legend.innerHTML = [[CSS_GOOD, 'win'], [CSS_BAD, 'loss'], ['#67e8f9', 'killzones'], ['#ffffff', 'now']]
      .map(([c, t]) => `<span><i style="background:${c};box-shadow:0 0 6px ${c}"></i>${t}</span>`).join('');
  }
  labelsFor() {
    const defs = [], I = this.info;
    for (const D of this.days) {
      const ang = (D.i + 0.5) / 5 * TAU, p = this.world(ang, RL, 0.02, new THREE.Vector3());
      const col = D.pnl >= 0 ? CSS_GOOD : CSS_BAD;
      const em = D.has ? `<em style="color:${col}">${fmtUsd(D.pnl)}${D.trades.length > 1 ? ' · ' + D.trades.length : ''}</em>` : D.state === 'done' ? '<em>no trade</em>' : '';
      defs.push({ html: `${D.name}${D.dom ? ' ' + D.dom : ''}${em}`, p, ax: 0.5 - Math.sin(ang) * 0.5, ay: 0.5 + Math.cos(ang) * 0.5, cls: 'dl ' + D.state, keep: true });
    }
    if (I && I.has) {
      const ang = I.hand * TAU, txt = I.today >= 0 ? `${DOW[I.today]} ${I.N.hm} ET` : I.left;
      defs.push({ text: txt, at: () => (this.introAt < 0 ? this.world(this.hand * TAU, BZ1 + 0.1, 0.05) : null), ax: 0.5 - Math.sin(ang) * 0.5, ay: 0.5 + Math.cos(ang) * 0.5,
        cls: 'tag', color: '#dffaff', avoid: true, keep: true });
    }
    this.setLabels(defs);
  }

  // ---------------------------------------------------------------- picking + tooltip
  nearest(px, py, maxPx) {
    const cam = this.camera; _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    let best = null, bd = maxPx * maxPx;
    for (const sl of this.slots) {
      if (sl.dead || sl.a < 0.3) continue;
      _v.copy(sl.p).applyEuler(this.g.rotation).applyMatrix4(_m); if (_v.z > 1) continue;
      const dx = (_v.x + 1) / 2 * this.w - px, dy = (1 - _v.y) / 2 * this.h - py, dd = dx * dx + dy * dy;
      if (dd < bd) { bd = dd; best = sl; }
    }
    return best;
  }
  pickAt(px, py) { const sl = this.nearest(px, py, 24); this.select(sl); if (sl) this.emit(sl.it.t); }
  select(sl) { this.sel = sl; this.u.uSel.value = sl ? sl.idx : -1; this.tipFor(this.hov || sl); }
  hoverAt(sl) {
    if (sl === this.hov) return;
    this.hov = sl; this.u.uHov.value = sl ? sl.idx : -1; this.canvas.style.cursor = sl ? 'pointer' : 'grab';
    this.tipFor(sl || this.sel);
  }
  tipFor(sl) {
    if (!sl) { this.showTip(null); return; }
    const it = sl.it, t = it.t || {}, D = it.day, when = Number.isFinite(it.ts) ? etParts(it.ts).hm + ' ET' : '';
    const side = typeof t.side === 'string' ? t.side.toUpperCase() : '', exit = typeof t.exit === 'string' ? t.exit : '';
    let html = `<b>${D.name}${D.dom ? ' ' + D.dom : ''}${when ? ' · ' + when : ''}</b> <b style="color:${sl.css}">${fmtUsd(it.pnl)}</b>${Number.isFinite(it.r) ? `<u style="color:${sl.css}">${fmtR(it.r, 1)}</u>` : ''}`;
    if (side || exit) html += `<br><i>${esc([side, exit].filter(Boolean).join(' · '))}</i>`;
    this.showTip(sl.key, html);
  }
  devTapPoint() { const sl = this.slots.find((s) => !s.dead && s.a > 0.5); if (!sl) return null; const p = this.screen(_v.copy(sl.p).applyEuler(this.g.rotation)); return [p.x, p.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u, red = Q.reduced;
    u.uTime.value = lt;
    const o = this.orbit;
    if (!o.dragging && o.idle > 2.5 && !red) { o.yaw += (Math.sin(lt * 0.27) * 0.14 - o.yaw) * Math.min(1, dt * 0.5); o.pitch += (0.1 + Math.sin(lt * 0.19) * 0.05 - o.pitch) * Math.min(1, dt * 0.5); }
    const moved = this.camStep(dt);
    // the hand: intro sweep (pearls drop as it passes them), then an ease to the current time
    if (this.introAt >= 0) {
      const dur = 1.5 * Math.max(0.4, this.handTo), k = clamp((lt - this.introAt) / dur, 0, 1);
      this.hand = this.handTo * outCubic(k); u.uIn.value = this.handTo < 0.02 ? 2 * outCubic(k) : this.hand + 0.008;   // before Monday: reveal the track instead
      for (const sl of this.slots) if (sl.wait && this.hand >= sl.ang - 0.001) { sl.wait = false; sl.t0 = lt; }
      if (k >= 1) { this.introAt = -1; u.uIn.value = 2; for (const sl of this.slots) if (sl.wait) { sl.wait = false; sl.t0 = lt; } this.camKey = ''; }
    } else {
      this.hand += (this.handTo - this.hand) * (red ? 1 : Math.min(1, dt * 3));
      if (Math.abs(this.handTo - this.hand) < 1e-5) this.hand = this.handTo;
    }
    u.uHand.value = this.hand;
    const ang = this.hand * TAU, sn = Math.sin(ang), cs = Math.cos(ang);
    const HP = this.handLine.geometry.attributes.position;
    HP.setXYZ(0, sn * 0.45, cs * 0.45, 0.03); HP.setXYZ(1, sn * R0, cs * R0, 0.03); HP.setXYZ(2, sn * R1, cs * R1, 0.04); HP.setXYZ(3, sn * (BZ1 + 0.07), cs * (BZ1 + 0.07), 0.04);
    HP.needsUpdate = true;
    const beat = red ? 0.5 : 0.5 + 0.5 * Math.sin(lt * 2.6);
    this.head.position.set(sn * RM, cs * RM, 0.09); this.head.scale.setScalar(0.38 + 0.08 * beat); this.head.material.opacity = 0.75 + 0.2 * beat;
    u.uBright.value = 0.9 + 0.3 * beat;
    // the days: lit share follows the hand, flashes decay
    const I = this.info;
    for (let i = 0; i < 5; i++) {
      const D = this.days[i], V = this.dayU[i];
      if (!D || !I) { V.set(0, 0, 0, 0); continue; }
      const lit = D.state === 'done' ? 1 : D.state === 'cur' ? clamp(this.hand * 5 - i, 0, 1) : 0;
      V.set(lit, clamp(D.pnl / I.maxAbs, -1, 1), D.has ? 1 : 0, this.flash[i]);
      if (this.flash[i] > 0) this.flash[i] = Math.max(0, this.flash[i] - dt / 1.2);
    }
    this.dU.uA.value = this.kU.uA.value = this.hasData ? 1 : 0.5;
    if (this.animating) this.animate();
    // selection reticle
    const s = this.sel;
    if (s && !s.dead) {
      const pulse = red ? 1 : 1 + 0.07 * Math.sin(lt * 5);
      this.reticle.visible = true; this.reticle.position.copy(s.p); this.reticle.scale.setScalar(Math.max(0.4, s.it.size * 1.7) * pulse);
      this.reticle.material.rotation = red ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95; this.reticle.material.color.copy(s.col).lerp(_c.set('#ffffff'), 0.5);
    } else this.reticle.visible = false;
    // html
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.nearest(hx, hy, 16)); }
    if (moved || this.animating || this.introAt >= 0) this.placeLabels();
    const ts = this.hov || this.sel;
    if (ts && this.tipKey != null) { const p = this.screen(_v.copy(ts.p).applyEuler(this.g.rotation)); this.placeTip(p.x, p.y, 14); }
    if (this.hasData) {
      const v = this.dispPnl(), txt = fmtUsd(Math.abs(v) < 0.5 ? 0 : v);
      if (txt !== this.pnlTxt) {
        this.pnlEl.textContent = txt; this.pnlTxt = txt; this.pnlEl.style.color = v > 0.5 ? CSS_GOOD : v < -0.5 ? CSS_BAD : '#fff';
        this.cenW = this.cen.offsetWidth; this.cenH = this.cen.offsetHeight; this.cenLast = null;
      }
      if (moved || this.cenLast == null) {
        const p = this.screen(_v.set(0, 0, 0));
        const tf = `translate3d(${(p.x - (this.cenW || 100) / 2).toFixed(1)}px,${(p.y - (this.cenH || 40) / 2 - 2).toFixed(1)}px,0)`;
        if (tf !== this.cenLast) { this.cen.style.transform = tf; this.cenLast = tf; }
      }
    }
  }
}
