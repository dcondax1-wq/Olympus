// LIT Day Clock (Today / Day plan): the LIT trading day as a glowing 24-hour dial. 18:00 ET (the Globex open, where the
//   LIT target band is anchored) sits at 12 o'clock and the day runs clockwise to the 17:00 close; the 17:00-18:00 halt is
//   a dark hatched wedge just before the top. Rings, outside in:
//   - bezel: hour ticks, 3-hour majors, hour labels (18 21 00 03 06 09 12 15), a scanner glow at the hand
//   - session ring: the LIT boxes as coloured arcs (Asia 20:00-00:00 violet, Frankfurt / London cyan, premarket and the NY
//     boxes amber, the cash session a faint blue band); a box whose high AND low are taken dims, one side taken gets a
//     half-dim stripe; the arcs ahead of the hand wait as dim outlines
//   - entry ring: the bot's entry window (02:00-15:30) as a green energy band that flows while the clock is inside it,
//     the 15:55 flat as a red tick, news blackouts as magenta bars cutting through it, a tick at every news event
//   - trade track (inner): today's trade as an arc from entry to exit (green win, magenta loss, cyan while open) with a
//     pearl at the entry; an armed LIT limit as a pulsing amber arc from the signal to its expiry
//   - news blips: a pearl per USD event at its time (size by impact), the next one pings
//   The current moment is a clock hand from the hub to the bezel with a comet behind it. HTML centre readout: the phase
//   (Asia / London / NY / Closed), whether entries are open, the next milestone with a live countdown, and the 18:00 open
//   with the VIX band. Labels for the boxes around the ring. Tap a blip / box / trade -> opts.onPick(item) (the page's own
//   object: an event, a box, a trade, the setup); mouse hover shows the tooltip; drag to tilt.
//   First data: the hand sweeps from 18:00 to now and the rings light up behind it. New data: the hand eases, blips pop in
//   / fade, a changed box flashes; the same data twice does nothing. The clock keeps running from `now` in real time.
// setData({ now: epoch s, day: 'YYYY-MM-DD' (the trading date, optional), closed: bool (weekend: the dial shows the next
//   session, the hand parks at 18:00), windows: [[startMin, endMin]] (ET minutes, default [[120, 930]]), flat: 955,
//   boxes: [{ key, label, a, b (ET minutes), kind: 'asia'|'london'|'ny'|'pre'|'rth', hi, lo, hiTaken, loTaken }],
//   events: [{ t, title, impact: 'high'|'medium'|'low' }], blackouts: [[t0, t1]] (epoch s),
//   trades: [{ t (entry epoch s), exit_t, dir, pnl, r, open }], setup: { t, expires_t, dir, label } | null,
//   milestones: [{ m (ET minute), label }] (default: the LIT day), open18, vixMove, done: bool (the day's trade is taken) })
//   Missing boxes -> the LIT defaults (Asia, Frankfurt, London, NY 08-09, cash session) without prices. No `now` -> "No clock".
//   Under 250 px tall the readout is compact (phase and countdown only).
// Draw calls ~14 whatever the data; particles: 160 comet sparks (60 lite) + 420 dust (180 lite) + 1 per event / trade.
import { THREE, Q, theme, glowTexture, POINT_FRAG, count, rng, Hud, addBackdrop, addNebula, addDust, ringTexture, sprite, additive, attrs,
  paintBackdrop, clamp, smooth, outCubic, outBack, num, esc, hash, fmtUsd, fmtR, div, injectStyle } from './hud.js';
import { etParts } from './weekring.js';

const TAU = Math.PI * 2, TILT = -0.55;
const TR0 = 1.0, TR1 = 1.09, TRM = 1.045, W0 = 1.15, W1 = 1.27, S0 = 1.34, S1 = 1.57, SM = 1.455, BZ0 = 1.64, BZ1 = 1.74, RL = 1.95, NB = 1.21;
const MAXB = 10, MAXW = 3, MAXK = 8, MAXT = 4;
const KIND = { asia: 0, london: 1, pre: 2, ny: 3, rth: 4, other: 5 };
const KCOL = ['#8b5cf6', '#22d3ee', '#ffb347', '#ff9b5c', '#6d7cff', '#c3c6e6'];
const KCSS = ['#b49bff', '#67e8f9', '#ffc777', '#ffb27a', '#9aa5ff', '#d6d9f5'];
const GOOD = '#2ee59d', BAD = '#ff2bd6', OPEN = '#22d3ee', AMBER = '#ffb347', CSS_GOOD = '#4ef0b0', CSS_BAD = '#ff7ad9';
const IMPC = { high: '#ff5a7a', medium: '#ffb347', low: '#b9b4ff' };
const _v = new THREE.Vector3(), _w = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color();
const pad2 = (n) => String(n).padStart(2, '0');
const hm = (m) => `${pad2(Math.floor(((m % 1440) + 1440) % 1440 / 60))}:${pad2(Math.round(((m % 60) + 60) % 60))}`;
const turnOfMin = (m) => (((m - 1080) % 1440) + 1440) % 1440 / 1440;      // ET minute -> share of the dial from 18:00
const DEF_BOXES = [
  { key: 'asia', label: 'Asia', a: 1200, b: 1440, kind: 'asia' }, { key: 'fra', label: 'Frankfurt', a: 120, b: 180, kind: 'london' },
  { key: 'lon', label: 'London 03-04', a: 180, b: 240, kind: 'london' }, { key: 'ny89', label: 'NY 08-09', a: 480, b: 540, kind: 'ny' },
  { key: 'rth', label: 'Cash session', a: 570, b: 960, kind: 'rth' }];
const DEF_MILES = [[1080, 'Globex open'], [1200, 'Asia box'], [0, 'Asia box ends'], [120, 'Entries open'], [180, 'London box'], [240, 'London box ends'],
  [480, 'NY box'], [570, 'Cash open'], [930, 'Entries close'], [955, 'Flat by'], [1020, 'Close']].map(([m, label]) => ({ m, label }));
// the CME weekend: Friday 17:00 to Sunday 18:00 ET
export function weekend(unix) { const N = etParts(unix), m = N.frac * 1440; return (N.dow === 4 && m >= 1020) || N.dow === 5 || (N.dow === 6 && m < 1080); }
export function cdText(s) {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
  return h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : h ? `${h}h ${pad2(m)}m` : m >= 1 ? `${m}m ${pad2(s % 60)}s` : `${s % 60}s`;
}

// ------------------------------------------------------------------ shaders
const RING_V = `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const COMMON = `float turnOf(vec2 p){ return fract(atan(p.x, p.y) / 6.2831853 + 1.0); }
float arcMask(float a, float a0, float a1, float soft){ float d = fract(a - a0), L = fract(a1 - a0 + 1.0) ; if (L < 0.0005) L = 1.0;
  return smoothstep(0.0, soft, d) * smoothstep(L, L - soft, d); }`;
// session ring: up to 10 boxes uBox[i] = (a0, a1, kind, taken: 0 none, 0.5 one side, 1 both); uFl[i] flash
const SESS_F = `uniform float uR0; uniform float uR1; uniform float uTime; uniform float uMotion; uniform float uIn; uniform float uHand; uniform float uA;
uniform vec4 uBox[${MAXB}]; uniform float uFl[${MAXB}]; uniform vec3 uKc[6]; uniform vec3 uTrack; uniform vec3 uHalt; varying vec2 vP;
${COMMON}
void main(){
  float r = length(vP), rr = clamp((r - uR0) / (uR1 - uR0), 0.0, 1.0), a = turnOf(vP), t = uTime * uMotion;
  float prof = exp(-pow((rr - 0.5) * 2.6, 2.0)), edge = exp(-pow((abs(rr - 0.5) - 0.44) * 16.0, 2.0));
  float past = step(a, uHand), reveal = smoothstep(a, a + 0.01, uIn);
  float dash = step(0.6, fract(a * 96.0)) * 0.05;
  vec3 c = uTrack * (0.05 + 0.06 * edge + dash) ;
  float halt = arcMask(a, 0.9583, 0.99995, 0.002); float hatch = step(0.5, fract((vP.x + vP.y) * 14.0));
  c += uHalt * halt * (0.05 + 0.08 * hatch) * prof;
  for (int i = 0; i < ${MAXB}; i++) {
    vec4 B = uBox[i]; if (B.z < -0.5) continue;
    float m = arcMask(a, B.x, B.y, 0.0025); if (m <= 0.0) continue;
    int k = int(B.z + 0.5); vec3 kc = uKc[0];
    for (int j = 0; j < 6; j++) if (j == k) kc = uKc[j];
    bool band = k == 4 || k == 2;
    float lvl = k == 4 ? 0.3 : band ? 0.55 : 1.0;
    float take = B.w > 0.75 ? 0.35 : B.w > 0.25 ? (rr > 0.5 ? 0.4 : 1.0) : 1.0;
    float flow = 0.8 + 0.2 * sin(a * 160.0 - t * 2.2);
    float lit = mix(0.32, 1.0, past) * take;
    float body = band ? exp(-pow((rr - 0.18) * 7.0, 2.0)) : prof;
    c += kc * m * lvl * (body * 0.75 * flow + edge * 0.6) * lit;
    c += kc * m * uFl[i] * (prof * 1.2 + edge);
  }
  gl_FragColor = vec4(c * reveal * uA, 1.0);
}`;
// entry ring: windows uWin[i] = (a0, a1, on), flat tick, blackouts uBlk[i] = (a0, a1, on), news ticks share the blip pass
const WIN_F = `uniform float uR0; uniform float uR1; uniform float uTime; uniform float uMotion; uniform float uIn; uniform float uHand; uniform float uA; uniform float uActive;
uniform vec3 uWin[${MAXW}]; uniform vec3 uBlk[${MAXK}]; uniform float uFlat; uniform vec3 uGo; uniform vec3 uBad; uniform vec3 uMag; uniform vec3 uTrack; varying vec2 vP;
${COMMON}
void main(){
  float r = length(vP), rr = clamp((r - uR0) / (uR1 - uR0), 0.0, 1.0), a = turnOf(vP), t = uTime * uMotion;
  float prof = exp(-pow((rr - 0.5) * 2.8, 2.0)), edge = exp(-pow((abs(rr - 0.5) - 0.42) * 16.0, 2.0));
  float past = step(a, uHand), reveal = smoothstep(a, a + 0.01, uIn);
  vec3 c = uTrack * (0.04 + 0.05 * edge);
  for (int i = 0; i < ${MAXW}; i++) {
    vec3 W = uWin[i]; if (W.z < 0.5) continue;
    float m = arcMask(a, W.x, W.y, 0.002); if (m <= 0.0) continue;
    float flow = 0.7 + 0.3 * sin(a * 220.0 - t * 3.0 * (0.4 + uActive));
    float here = exp(-pow((a - uHand) * 60.0, 2.0)) * uActive;
    c += uGo * m * (prof * (0.45 + 0.35 * past) * flow + edge * 0.5 + here * 1.2);
  }
  for (int i = 0; i < ${MAXK}; i++) {
    vec3 K = uBlk[i]; if (K.z < 0.5) continue;
    float m = arcMask(a, K.x, K.y, 0.0015); if (m <= 0.0) continue;
    float st = 0.6 + 0.4 * step(0.5, fract(a * 900.0 - t * 0.6));
    c = mix(c, uMag * (prof * 0.9 + edge * 0.8) * st, m * 0.85);
  }
  float fl = exp(-pow(fract(a - uFlat + 0.5) - 0.5, 2.0) * 2.0e5);
  c += uBad * fl * (0.6 + rr * 0.8) * 1.6;
  gl_FragColor = vec4(c * reveal * uA, 1.0);
}`;
// trade track: uTr[i] = (a0, a1, sign: 1 win / -1 loss / 0 open, on); the setup arc uSet = (a0, a1, on, dir)
const TRK_F = `uniform float uR0; uniform float uR1; uniform float uTime; uniform float uMotion; uniform float uIn; uniform float uA;
uniform vec4 uTr[${MAXT}]; uniform vec4 uSet; uniform vec3 uGood; uniform vec3 uBad; uniform vec3 uOpen; uniform vec3 uAmber; uniform vec3 uTrack; varying vec2 vP;
${COMMON}
void main(){
  float r = length(vP), rr = clamp((r - uR0) / (uR1 - uR0), 0.0, 1.0), a = turnOf(vP), t = uTime * uMotion;
  float prof = exp(-pow((rr - 0.5) * 3.0, 2.0)), reveal = smoothstep(a, a + 0.01, uIn);
  vec3 c = uTrack * 0.035 * prof;
  for (int i = 0; i < ${MAXT}; i++) {
    vec4 T = uTr[i]; if (T.w < 0.5) continue;
    float m = arcMask(a, T.x, T.y, 0.0015); if (m <= 0.0) continue;
    vec3 col = T.z > 0.5 ? uGood : T.z < -0.5 ? uBad : uOpen;
    float flow = 0.75 + 0.25 * sin(a * 400.0 - t * 4.0);
    c += col * m * prof * 1.25 * flow;
  }
  if (uSet.z > 0.5) {
    float m = arcMask(a, uSet.x, uSet.y, 0.0015);
    float st = step(0.45, fract(a * 300.0 - t * 1.4)), pu = 0.65 + 0.35 * sin(t * 4.0);
    c += uAmber * m * prof * (0.5 + 0.8 * st) * pu;
  }
  gl_FragColor = vec4(c * reveal * uA, 1.0);
}`;
// bezel: hour ticks, 3-hour majors, a scanner glow at the hand
const BEZEL_F = `uniform vec3 uCol; uniform float uHand; uniform float uIn; varying vec2 vP;
float tk(float x, float w){ return step(1.0 - w, fract(x + 0.5 * w)); }
void main(){
  float r = length(vP), rr = clamp((r - ${BZ0.toFixed(3)}) / ${(BZ1 - BZ0).toFixed(3)}, 0.0, 1.0);
  float a = fract(atan(vP.x, vP.y) / 6.2831853 + 1.0);
  float q = tk(a * 96.0, 0.16) * step(0.62, rr), hour = tk(a * 24.0, 0.07) * step(0.35, rr), major = tk(a * 8.0, 0.012);
  float scan = exp(-pow((fract(a - uHand + 0.5) - 0.5) * 9.0, 2.0)) * 0.6;
  float line = exp(-pow((rr - 0.1) * 20.0, 2.0));
  float reveal = smoothstep(a, a + 0.01, uIn);
  gl_FragColor = vec4(uCol * (line * (0.3 + scan) + q * 0.12 * (1.0 + scan * 2.0) + hour * 0.32 + major * 0.95) * (0.35 + 0.65 * reveal), 1.0);
}`;
const COMET_V = `attribute float aSeed; attribute float aS; attribute float aJ;
uniform float uTime; uniform float uMotion; uniform float uPix; uniform float uHand; uniform float uR; uniform float uTrail; uniform float uBright; uniform vec3 uCol;
varying vec3 vColor; varying float vAlpha;
void main(){
  float ph = fract(aSeed + uTime * uMotion * (0.2 + aJ * 0.3));
  float ang = (uHand - ph * uTrail) * 6.2831853;
  float r = uR + (aJ - 0.5) * 0.5 * (0.25 + ph);
  vec3 p = vec3(sin(ang) * r, cos(ang) * r, 0.06 + (aSeed - 0.5) * 0.14 * ph);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp(aS * uPix * (1.0 - ph * 0.7) / -mv.z, 0.0, 26.0);
  gl_Position = projectionMatrix * mv;
  vColor = mix(vec3(1.0), uCol, ph * 0.85) * uBright; vAlpha = (1.0 - ph) * (1.0 - ph) * smoothstep(0.0, 0.04, ph);
}`;
// pearls (news blips, trade entries, the setup): a glossy bead with a halo; aMisc = (seed, index, ping)
const PEARL_V = `attribute vec3 aCol; attribute float aSize; attribute float aAlpha; attribute vec4 aMisc;
uniform float uTime; uniform float uPix; uniform float uMotion; uniform float uSel; uniform float uHov;
varying vec3 vColor; varying float vAlpha; varying float vHi; varying float vPing;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float tw = 1.0 + 0.07 * sin(uTime * uMotion * (1.3 + aMisc.x * 2.0) + aMisc.x * 50.0);
  vHi = max(1.0 - step(0.5, abs(aMisc.y - uSel)), (1.0 - step(0.5, abs(aMisc.y - uHov))) * 0.75);
  vPing = aMisc.z > 0.5 ? fract(uTime * uMotion * 0.6) : -1.0;
  float grow = vPing >= 0.0 ? 2.2 : 1.0;
  gl_PointSize = clamp(aSize * grow * uPix * tw * (1.0 + vHi * 0.5) / -mv.z, 0.0, 160.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol; vAlpha = aAlpha;
}`;
const PEARL_F = `varying vec3 vColor; varying float vAlpha; varying float vHi; varying float vPing;
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2), k = vPing >= 0.0 ? 2.2 : 1.0, dd = d * k;
  float halo = max(0.0, 1.0 - dd * dd); halo = halo * halo * halo;
  float body = smoothstep(0.6, 0.48, dd);
  vec2 s = q * k - vec2(-0.08, -0.1); float spec = exp(-dot(s, s) * 90.0);
  float rim = exp(-pow((dd - 0.54) * 12.0, 2.0)) * 0.6;
  float hi = vHi * exp(-pow((dd - 0.86) * 10.0, 2.0));
  float ping = vPing >= 0.0 ? exp(-pow((d - vPing * 0.95) * 18.0, 2.0)) * (1.0 - vPing) * 0.9 : 0.0;
  vec3 c = mix(vColor, vec3(1.0), 0.22) * (halo * 0.35 + body * 0.85 + rim) + vec3(1.0) * (spec * body * 0.9 + hi * 0.9) + vColor * ping;
  gl_FragColor = vec4(c * vAlpha, 1.0);
}`;

const CSS = `.fxd-c{position:absolute;left:0;top:0;text-align:center;white-space:nowrap;line-height:1}
.fxd-ph{font-size:20px;font-weight:800;letter-spacing:-.01em;color:#fff;text-shadow:0 0 16px rgba(5,3,14,.95),0 0 4px rgba(5,3,14,.95)}
.fxd-sub{margin-top:3px;font-size:9.5px;font-weight:700;letter-spacing:.03em;color:rgba(214,218,250,.66);text-shadow:0 0 6px #07080c}
.fxd-win{display:inline-block;margin:6px 0 6px;font-size:9px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;padding:3px 7px;border-radius:99px;border:1px solid currentColor;text-shadow:none;background:rgba(7,8,12,.45)}
.fxd-win.on{color:#4ef0b0;box-shadow:0 0 12px rgba(46,229,157,.35)}.fxd-win.off{color:rgba(188,192,236,.7)}.fxd-win.done{color:#ffc777}
.fxd-next{font-size:10.5px;font-weight:700;color:rgba(214,218,250,.82);text-shadow:0 0 8px rgba(5,3,14,.95),0 0 3px rgba(5,3,14,.95)}
.fxd-cd{margin-top:3px;font-size:15px;font-weight:800;color:#fff;font-variant-numeric:tabular-nums;text-shadow:0 0 12px rgba(5,3,14,.95),0 0 3px rgba(5,3,14,.95)}
.fxh-dayclock .fxh-l.fixl{transform:none!important;left:10px;right:auto;top:auto;bottom:12px}.fxh-dayclock .fxh-l.fix{bottom:12px}
.fxh-dayclock .fxh-l.hr{font-size:9px;font-weight:700;color:rgba(188,192,236,.55)}
.fxh-dayclock .fxh-l.hr.t18{color:#dffaff}
.fxh-dayclock .fxh-l.bx{font-size:9.5px;font-weight:700;letter-spacing:.02em;text-shadow:0 0 8px #07080c,0 0 3px #07080c;text-align:center;line-height:1.15}
.fxh-dayclock .fxh-l.bx em{display:block;font-style:normal;font-size:8.5px;font-weight:600;color:rgba(214,218,250,.62)}
.fxh-dayclock.compact .fxd-sub,.fxh-dayclock.compact .fxh-leg,.fxh-dayclock.compact .fxh-l.bx em,.fxh-dayclock.compact .fxh-l.fix,.fxh-dayclock.compact .fxh-l.fixl,.fxh-dayclock.compact .fxh-l.hr{display:none}
.fxh-dayclock.compact .fxd-ph{font-size:15px}.fxh-dayclock.compact .fxd-next{font-size:9.5px}.fxh-dayclock.compact .fxd-cd{font-size:12px}.fxh-dayclock.compact .fxd-win{margin:3px 0 3px;font-size:8px;padding:2px 5px}`;

// ------------------------------------------------------------------ the view
export class DayClock extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'dayclock', fov: 34, empty: 'No clock data', orbit: { yaw: 0, pitch: 0.1, auto: 0, min: -0.6, max: 0.6, pitchMin: -0.15, pitchMax: 0.55 } });
    injectStyle('fxh-dc-css', CSS);
    this.items = []; this.slots = []; this.byKey = new Map(); this.cap = 0; this.animating = false; this.hasData = false; this.sig = null; this.info = null;
    this.hand = 0; this.handTo = 0; this.introAt = -1; this.sel = null; this.hov = null; this.flash = new Float32Array(MAXB);
    this.now0 = 0; this.set0 = 0; this.txtAt = -9; this.cenLast = null; this.lastBoxes = new Map();
    Object.assign(this.u, { uSel: { value: -1 }, uHov: { value: -1 }, uHand: { value: 0 }, uIn: { value: 2 }, uBright: { value: 1 }, uR: { value: SM }, uTrail: { value: 0.06 },
      uCol: { value: new THREE.Color('#8fe3ff') } });
    this.build(); this.ensureCap(24); this.buildHtml();
  }
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.52]);
    addNebula(S, [['#6d28d9', -3.4, 2.1, -6, 9, 6, 0.1], ['#22d3ee', 3.2, -1.7, -6, 8, 5, 0.04]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 360 : 420, 180), box: [4, 3, 2], cy: 0, seed: 83 });
    const g = this.g = new THREE.Group(); g.rotation.x = TILT; S.add(g);
    const spr = (col, scale, op, order) => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(col), transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false })); s.scale.setScalar(scale); s.renderOrder = order; g.add(s); return s; };
    this.hub = spr('#4b2fc0', 2.3, 0.2, 1);
    const ring = (r0, r1, seg, F, U, order) => { const m = new THREE.Mesh(new THREE.RingGeometry(r0 - 0.02, r1 + 0.02, seg, 1), additive(RING_V, F, U, { side: THREE.DoubleSide })); m.renderOrder = order; g.add(m); return m; };
    this.boxU = Array.from({ length: MAXB }, () => new THREE.Vector4(0, 0, -1, 0));
    this.sU = { uR0: { value: S0 }, uR1: { value: S1 }, uTime: u.uTime, uMotion: u.uMotion, uIn: u.uIn, uHand: u.uHand, uA: { value: 1 }, uBox: { value: this.boxU },
      uFl: { value: this.flash }, uKc: { value: KCOL.map((c) => new THREE.Color(c)) }, uTrack: { value: new THREE.Color('#5b6cff') }, uHalt: { value: new THREE.Color('#ff5a7a') } };
    ring(S0, S1, 288, SESS_F, this.sU, 5);
    this.winU = Array.from({ length: MAXW }, () => new THREE.Vector3()); this.blkU = Array.from({ length: MAXK }, () => new THREE.Vector3());
    this.wU = { uR0: { value: W0 }, uR1: { value: W1 }, uTime: u.uTime, uMotion: u.uMotion, uIn: u.uIn, uHand: u.uHand, uA: { value: 1 }, uActive: { value: 0 },
      uWin: { value: this.winU }, uBlk: { value: this.blkU }, uFlat: { value: turnOfMin(955) }, uGo: { value: theme.good.clone() }, uBad: { value: new THREE.Color('#ff5a7a') },
      uMag: { value: new THREE.Color('#ff2bd6') }, uTrack: { value: new THREE.Color('#5b6cff') } };
    ring(W0, W1, 288, WIN_F, this.wU, 4);
    this.trU = Array.from({ length: MAXT }, () => new THREE.Vector4());
    this.tU = { uR0: { value: TR0 }, uR1: { value: TR1 }, uTime: u.uTime, uMotion: u.uMotion, uIn: u.uIn, uA: { value: 1 }, uTr: { value: this.trU }, uSet: { value: new THREE.Vector4() },
      uGood: { value: theme.good.clone() }, uBad: { value: new THREE.Color(BAD) }, uOpen: { value: new THREE.Color(OPEN) }, uAmber: { value: new THREE.Color(AMBER) }, uTrack: { value: new THREE.Color('#5b6cff') } };
    ring(TR0, TR1, 240, TRK_F, this.tU, 4);
    this.bU = { uCol: { value: new THREE.Color('#7c6cff') }, uHand: u.uHand, uIn: u.uIn };
    ring(BZ0, BZ1, 288, BEZEL_F, this.bU, 3);
    // hand
    const hg = new THREE.BufferGeometry();
    hg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(12), 3).setUsage(THREE.DynamicDrawUsage));
    hg.setAttribute('color', new THREE.BufferAttribute(new Float32Array([0.12, 0.2, 0.28, 0.55, 0.85, 1, 0.75, 1, 1.1, 0.1, 0.18, 0.22]), 3));
    this.handLine = new THREE.LineSegments(hg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.handLine.renderOrder = 7; this.handLine.visible = false; g.add(this.handLine);
    this.head = spr('#dffaff', 0.36, 0.9, 10); this.head.visible = false;
    const N = count(Q.phone ? 130 : 160, 60), cg = attrs(N, { position: [3], aSeed: [1], aS: [1], aJ: [1] }), R = rng(9);
    for (let i = 0; i < N; i++) { cg.attributes.aSeed.setX(i, R()); cg.attributes.aS.setX(i, 0.03 + R() * 0.05); cg.attributes.aJ.setX(i, R()); }
    this.comet = new THREE.Points(cg, additive(COMET_V, POINT_FRAG, u)); this.comet.renderOrder = 9; this.comet.visible = false; g.add(this.comet);
    const ret = ringTexture(true); this.textures.push(ret);
    this.reticle = sprite(S, ret, '#ffffff', 12); g.add(this.reticle);
    S.traverse((o) => { o.frustumCulled = false; });
    const P = [];
    for (let i = 0; i < 24; i++) { const a = i / 24 * TAU; this.world(a, 2.12, 0, _w); P.push(_w.x, _w.y, _w.z); }
    _v.set(0, 0, 0.45).applyEuler(g.rotation); P.push(_v.x, _v.y, _v.z, -_v.x, -_v.y, -_v.z);
    this.anchors = new Float32Array(P); this.T.set(0, 0, 0); this.fill = [0.92, 0.9];
  }
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(24, Math.ceil(n * 1.25 / 8) * 8);
    const pg = attrs(cap, { position: [3, 1], aCol: [3], aSize: [1, 1], aAlpha: [1, 1], aMisc: [4] });
    if (!this.pearls) { this.pearls = new THREE.Points(pg, additive(PEARL_V, PEARL_F, this.u)); this.pearls.renderOrder = 8; this.pearls.frustumCulled = false; this.g.add(this.pearls); }
    else { this.pearls.geometry.dispose(); this.pearls.geometry = pg; }
    this.cap = cap;
  }
  buildHtml() {
    this.cen = div('fxd-c', this.ui, '<div class="fxd-ph">—</div><div class="fxd-sub"></div><div class="fxd-win"></div><div class="fxd-next"></div><div class="fxd-cd"></div>');
    this.cen.style.visibility = 'hidden';
    [this.phEl, this.subEl, this.winEl, this.nextEl, this.cdEl] = this.cen.children;
    this.legend = div('fxh-leg'); this.ui.prepend(this.legend);
    this.hint = div('fxh-l h fix', this.ui);
    this.foot = div('fxh-l h fixl', this.ui);
  }
  world(ang, r, z, out = _w) { return out.set(Math.sin(ang) * r, Math.cos(ang) * r, z).applyEuler(this.g.rotation); }
  retheme() { paintBackdrop(this.bgU); this.wU.uGo.value.copy(theme.good); this.tU.uGood.value.copy(theme.good); }
  relayout(w, h) {
    const compact = h < 250; this.ui.classList.toggle('compact', compact);
    const lh = this.legend.isConnected ? this.legend.offsetHeight : 14;
    this.region = compact ? [-1, 1, -1 + 2 * 6 / h, 1 - 2 * 6 / h] : [-1, 1, -1 + 2 * 22 / h, 1 - 2 * (lh + 14) / h];
    this.cenW = this.cen.offsetWidth; this.cenH = this.cen.offsetHeight; this.cenLast = null; this.Lset = false;
  }
  attach(el) { super.attach(el); this.relayout(this.w, this.h); }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' ? d : null;
    let nowS = src ? num(src.now, NaN) : NaN; if (nowS > 1e11) nowS /= 1000;
    const has = Number.isFinite(nowS);
    if (!has) nowS = Date.now() / 1000;
    const wins = (src && Array.isArray(src.windows) && src.windows.length ? src.windows : [[120, 930]]).slice(0, MAXW)
      .map((w) => [num(w?.[0], NaN), num(w?.[1], NaN)]).filter((w) => Number.isFinite(w[0]) && Number.isFinite(w[1]));
    const flat = num(src?.flat, 955);
    const boxes = (src && Array.isArray(src.boxes) && src.boxes.length ? src.boxes : DEF_BOXES).slice(0, MAXB).map((b, i) => ({
      raw: b, key: String(b?.key ?? b?.label ?? i), label: String(b?.label ?? ''), a: num(b?.a, NaN), b: num(b?.b, NaN), kind: KIND[b?.kind] ?? KIND.other,
      hi: num(b?.hi, NaN), lo: num(b?.lo, NaN), hiT: !!b?.hiTaken, loT: !!b?.loTaken })).filter((b) => Number.isFinite(b.a) && Number.isFinite(b.b));
    const miles = (src && Array.isArray(src.milestones) && src.milestones.length ? src.milestones : DEF_MILES)
      .map((x) => ({ m: num(x?.m, NaN), label: String(x?.label ?? '') })).filter((x) => Number.isFinite(x.m));
    const closed = src && src.closed != null ? !!src.closed : weekend(nowS), S = this.sessionStart(nowS, closed);
    const sig = JSON.stringify([has, closed, S, src?.done, src?.day, wins, flat, boxes.map((b) => [b.key, b.a, b.b, b.kind, b.hi, b.lo, b.hiT, b.loT]),
      (src?.events || []).map((e) => [e?.t, e?.title, e?.impact]), src?.blackouts, (src?.trades || []).map((t) => [t?.t, t?.exit_t, t?.pnl, t?.open]),
      src?.setup ? [src.setup.t, src.setup.expires_t, src.setup.dir] : null, miles.map((x) => [x.m, x.label]), src?.open18, src?.vixMove]);
    this.now0 = nowS; this.set0 = performance.now() / 1000;
    if (sig === this.sig) { this.refreshRows(src); return; }
    const first = !this.hasData, red = Q.reduced, now = this.lt;
    // the session this dial shows: from 18:00 ET of the day before the trading date (the weekend shows the next one)
    this.sig = sig; this.src = src; this.wins = wins; this.flatM = flat; this.boxes = boxes; this.miles = miles; this.closed = closed; this.S = S;
    // rings
    boxes.forEach((b, i) => {
      const V = this.boxU[i]; V.set(turnOfMin(b.a), turnOfMin(b.b === 1440 ? 1439.99 : b.b), b.kind, b.hiT && b.loT ? 1 : b.hiT || b.loT ? 0.5 : 0);
      const prev = this.lastBoxes.get(b.key); if (prev != null && prev !== V.w && !red) this.flash[i] = 1;
      this.lastBoxes.set(b.key, V.w);
    });
    for (let i = boxes.length; i < MAXB; i++) this.boxU[i].set(0, 0, -1, 0);
    for (let i = 0; i < MAXW; i++) { const w = wins[i]; if (w) this.winU[i].set(turnOfMin(w[0]), turnOfMin(w[1]), 1); else this.winU[i].set(0, 0, 0); }
    this.wU.uFlat.value = turnOfMin(flat);
    const blk = (src?.blackouts || []).map((x) => [this.turn(num(x?.[0], NaN)), this.turn(num(x?.[1], NaN))]).filter((x) => x[0] != null || x[1] != null)
      .map(([a, b]) => [a ?? 0, b ?? 0.9999]).slice(0, MAXK);
    for (let i = 0; i < MAXK; i++) { const k = blk[i]; if (k) this.blkU[i].set(k[0], k[1], 1); else this.blkU[i].set(0, 0, 0); }
    // trades + setup on the inner track
    const trades = (src?.trades || []).filter(Boolean).map((t, j) => ({ t, j, a0: this.turn(num(t.t, NaN)), a1: this.turn(num(t.exit_t, NaN)), pnl: num(t.pnl, 0), r: num(t.r, NaN), open: !!t.open || !Number.isFinite(num(t.exit_t, NaN)) }))
      .filter((x) => x.a0 != null).slice(0, MAXT);
    for (let i = 0; i < MAXT; i++) {
      const x = trades[i]; if (!x) { this.trU[i].set(0, 0, 0, 0); continue; }
      const a1 = x.a1 ?? (x.open ? this.turn(nowS) ?? x.a0 + 0.003 : x.a0 + 0.003);
      this.trU[i].set(x.a0, Math.max(a1, x.a0 + 0.002), x.open ? 0 : x.pnl >= 0 ? 1 : -1, 1);
    }
    const st = src?.setup, sa = st ? this.turn(num(st.t, NaN)) : null, sb = st ? this.turn(num(st.expires_t, NaN)) : null;
    if (sa != null) this.tU.uSet.value.set(sa, Math.max(sb ?? sa + 30 / 1440, sa + 0.002), 1, num(st.dir, 0)); else this.tU.uSet.value.set(0, 0, 0, 0);
    // pearls: news blips, trade entries, the setup
    const items = [];
    const evs = (src?.events || []).filter(Boolean).map((e) => ({ e, a: this.turn(num(e.t, NaN)) })).filter((x) => x.a != null).sort((x, y) => x.a - y.a);
    let maxP = 1; for (const x of trades) maxP = Math.max(maxP, Math.abs(x.pnl));
    evs.forEach((x, i) => {
      const imp = ['high', 'medium', 'low'].includes(x.e.impact) ? x.e.impact : 'low';
      const near = evs.filter((y, k) => k < i && Math.abs(y.a - x.a) < 0.008).length;
      items.push({ key: 'e|' + x.e.t + '|' + x.e.title, kind: 'event', row: x.e, ang: x.a, rad: NB + 0.0 + near * 0.0, z: 0.12 + near * 0.12, size: imp === 'high' ? 0.2 : imp === 'medium' ? 0.15 : 0.11,
        col: IMPC[imp], css: IMPC[imp], imp, t: num(x.e.t, NaN) });
    });
    for (const x of trades) items.push({ key: 't|' + x.t.t, kind: 'trade', row: x.t, ang: x.a0, rad: TRM, z: 0.1, size: 0.16 + 0.16 * Math.sqrt(Math.abs(x.pnl) / maxP),
      col: x.open ? OPEN : x.pnl >= 0 ? GOOD : BAD, css: x.open ? '#67e8f9' : x.pnl >= 0 ? CSS_GOOD : CSS_BAD, x });
    if (sa != null) items.push({ key: 's|' + st.t, kind: 'setup', row: st, ang: sa, rad: TRM, z: 0.14, size: 0.17, col: AMBER, css: '#ffc777' });
    for (const b of boxes) items.push({ key: 'b|' + b.key, kind: 'box', row: b.raw, box: b, ang: (turnOfMin(b.a) + this.arcLen(b) / 2) % 1, rad: SM, z: 0.02, size: 0, col: KCOL[b.kind], css: KCSS[b.kind], pickOnly: true });
    this.items = items;
    const next = [], keep = new Set();
    for (const it of items) {
      if (it.pickOnly) continue;
      it.seed = hash(it.key);
      let sl = this.byKey.get(it.key);
      if (sl && !sl.dead) { sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.mode = 2; sl.t0 = now; sl.dur = red ? 0 : 0.7; sl.wait = false; }
      else {
        sl = { key: it.key, p: new THREE.Vector3(), p0: new THREE.Vector3(), p1: new THREE.Vector3(), s: 0, s0: 0, a: 0, a0: 0, dead: false, done: false, col: new THREE.Color(), wait: false, mode: 1, dur: red ? 0 : 0.65 };
        if (first && !red) { sl.wait = true; sl.t0 = Infinity; } else sl.t0 = red ? now : now + 0.05 + it.seed * 0.3;
      }
      sl.it = it; sl.ang = it.ang; sl.done = false; sl.col.set(it.col);
      const x = Math.sin(it.ang * TAU) * it.rad, y = Math.cos(it.ang * TAU) * it.rad;
      sl.p1.set(x, y, it.z); if (sl.mode === 1) { sl.p0.set(x, y, 0.8); sl.p.copy(sl.p0); }
      keep.add(it.key); next.push(sl);
    }
    for (const sl of this.slots) { if (keep.has(sl.key) || sl.dead) continue; sl.dead = true; sl.done = false; sl.mode = 4; sl.p0.copy(sl.p); sl.s0 = sl.s; sl.a0 = sl.a; sl.t0 = now; sl.dur = red ? 0 : 0.4; sl.wait = false; next.push(sl); }
    this.slots = next; this.byKey.clear();
    for (const sl of next) if (!sl.dead) this.byKey.set(sl.key, sl);
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.hoverAt(null);
    this.writeStatic(); this.animating = true;
    const hand = this.handAt(nowS);
    this.handTo = hand;
    if (first && has) { if (red) { this.hand = hand; this.u.uIn.value = 2; } else { this.hand = 0; this.u.uIn.value = 0; this.introAt = now; } }
    this.hasData = has;
    this.labelsFor(); this.legendFor(); this.writeHtml(true);
    this.empty.style.display = has ? 'none' : 'block';
    this.cen.style.visibility = has ? 'visible' : 'hidden';
    this.handLine.visible = this.head.visible = this.comet.visible = has;
    this.ui.classList.add('on');
    this.relayout(this.w, this.h);
    this.tipKey = null; this.tipFor(this.hov || this.sel);
  }
  // keep the page's objects fresh when the data did not change
  refreshRows(src) {
    const byT = new Map((src?.events || []).filter(Boolean).map((e) => ['e|' + e.t + '|' + e.title, e]));
    for (const sl of this.slots) if (byT.has(sl.key)) sl.it.row = byT.get(sl.key);
  }
  arcLen(b) { const L = turnOfMin(b.b === 1440 ? 1439.99 : b.b) - turnOfMin(b.a); return L <= 0 ? L + 1 : L; }
  sessionStart(nowS, closed) {
    const N = etParts(nowS), min = Math.round(N.frac * 1440), mm = ((min - 1080) % 1440 + 1440) % 1440;
    let S = Math.round(nowS / 60) * 60 - mm * 60;          // the latest 18:00 ET
    if (closed) {                                             // the weekend: the next session opens Sunday 18:00
      const sdow = min >= 1080 ? N.dow : (N.dow + 6) % 7;     // weekday of that 18:00 (0 Mon .. 6 Sun)
      S += ((6 - sdow + 7) % 7) * 86400;
    }
    return S;
  }
  turn(t) { if (!Number.isFinite(t)) return null; const x = (t - this.S) / 86400; return x >= 0 && x < 1 ? x : null; }
  clockNow() { return this.now0 + (Q.reduced ? 0 : performance.now() / 1000 - this.set0); }
  handAt(t) { const x = (t - this.S) / 86400; return this.closed || x < 0 ? 0 : x >= 1 ? 0.99999 : x; }
  writeStatic() {
    const n = this.slots.length; this.ensureCap(n);
    const P = this.pearls.geometry.attributes;
    for (let i = 0; i < n; i++) { const sl = this.slots[i], c = sl.col; sl.idx = i; P.aCol.setXYZ(i, c.r, c.g, c.b); P.aMisc.setXYZW(i, sl.it.seed, i, 0, 0); }
    P.aCol.needsUpdate = P.aMisc.needsUpdate = true;
    this.pearls.geometry.setDrawRange(0, n);
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
    this.pingKey = null;
  }
  writeDynamic() {
    const n = this.slots.length, P = this.pearls.geometry.attributes, PP = P.position.array, PZ = P.aSize.array, PA = P.aAlpha.array;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], p = sl.p, it = sl.it, past = it.kind === 'event' && Number.isFinite(it.t) && it.t < this.clockNow() - 900;
      PP[i * 3] = p.x; PP[i * 3 + 1] = p.y; PP[i * 3 + 2] = p.z; PZ[i] = it.size * sl.s; PA[i] = sl.a * (past ? 0.45 : 1);
    }
    P.position.needsUpdate = P.aSize.needsUpdate = P.aAlpha.needsUpdate = true;
  }
  animate() {
    const now = this.lt; let busy = false, dead = false;
    for (const sl of this.slots) {
      if (sl.done) { dead ||= sl.dead; continue; }
      if (sl.wait) { busy = true; continue; }
      const k = sl.dur > 0 ? clamp((now - sl.t0) / sl.dur, 0, 1) : 1, p = sl.p;
      if (sl.mode === 1) { p.lerpVectors(sl.p0, sl.p1, outCubic(k)); sl.s = k > 0 ? 0.3 + 0.7 * outBack(k) : 0; sl.a = smooth(Math.min(1, k * 3)); }
      else if (sl.mode === 2) { const e = smooth(k); p.lerpVectors(sl.p0, sl.p1, e); sl.s = sl.s0 + (1 - sl.s0) * e; sl.a = sl.a0 + (1 - sl.a0) * e; }
      else { const e = smooth(k); p.copy(sl.p0); sl.s = sl.s0 * (1 - e); sl.a = sl.a0 * (1 - e); }
      if (k >= 1) { sl.done = true; dead ||= sl.dead; } else busy = true;
    }
    if (!busy && dead) { this.slots = this.slots.filter((s) => !s.dead); this.writeStatic(); }
    this.writeDynamic();
    if (!busy) this.animating = false;
  }

  // ---------------------------------------------------------------- the readout: phase, window, next milestone
  phaseOf(t) {
    const N = etParts(t), min = N.frac * 1440;
    if (this.closed) return { ph: 'Closed', sub: 'weekend', win: 'off', winTxt: 'market closed' };
    if (this.handAt(t) >= 0.9583) return { ph: 'Halt', sub: 'daily halt 17:00-18:00', win: 'off', winTxt: 'market closed' };
    const inBox = (a, b) => (a <= b ? min >= a && min < b : min >= a || min < b);
    let ph = min >= 1080 || min < 120 ? 'Asia' : min < 300 ? 'London' : min < 570 ? 'Pre-market' : min < 690 ? 'NY AM' : min < 810 ? 'NY lunch' : min < 960 ? 'NY PM' : 'After hours';
    let box = this.boxes.filter((b) => b.kind !== KIND.rth && inBox(b.a, b.b)).sort((x, y) => this.arcLen(x) - this.arcLen(y))[0];
    const inWin = this.wins.some(([a, b]) => inBox(a, b));
    const afterWin = this.wins.length && this.wins.every(([a, b]) => a < b && min >= b && min < 1080);
    if (box && box.kind === KIND.pre && ph === 'Pre-market') box = null;
    if (this.src?.done && !this.closed) return { ph, sub: box ? box.label + ' box' : '', win: 'done', winTxt: 'done for today' };
    return { ph, sub: box ? box.label + ' box' : '', win: inWin ? 'on' : afterWin ? 'done' : 'off',
      winTxt: inWin ? `entries open → ${hm(this.wins.find(([a, b]) => inBox(a, b))[1])}` : afterWin ? (min < this.flatM ? `flat by ${hm(this.flatM)}` : 'entries closed') : `entries from ${hm(this.wins[0]?.[0] ?? 120)}` };
  }
  nextMilestone(t) {
    let best = null;
    for (const M of this.miles) {
      let at = this.S + turnOfMin(M.m) * 86400;
      if (at <= t) at += 86400;
      if (!best || at < best.at) best = { at, label: M.label, m: M.m };
    }
    // the next news event inside the dial beats a milestone when it comes first
    for (const it of this.items) if (it.kind === 'event' && it.t > t && (!best || it.t < best.at) && it.imp !== 'low') best = { at: it.t, label: it.row.title, m: null, ev: true };
    return best;
  }
  writeHtml(force) {
    if (!this.hasData) return;
    const t = this.clockNow(), P = this.phaseOf(t), nx = this.nextMilestone(t), src = this.src || {};
    const key = P.ph + P.sub + P.win + P.winTxt + (nx ? nx.label + Math.round(nx.at - t) : '');
    if (!force && key === this.htmlKey) return;
    this.htmlKey = key;
    const day = src.day ? new Date(src.day + 'T12:00:00Z').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }) : '';
    this.phEl.textContent = P.ph;
    this.subEl.textContent = P.sub ? (P.sub === 'weekend' ? 'weekend' : 'in the ' + P.sub) : `${etParts(t).hm} ET`;
    this.winEl.className = 'fxd-win ' + P.win; this.winEl.textContent = P.winTxt;
    this.nextEl.textContent = nx ? `${nx.label.length > 22 ? nx.label.slice(0, 21) + '…' : nx.label}${nx.m != null ? ' ' + hm(nx.m) : ''}` : '';
    this.cdEl.textContent = nx ? 'in ' + cdText(nx.at - t) : '';
    const o18 = num(src.open18, NaN), vm = num(src.vixMove, NaN);
    this.foot.textContent = Number.isFinite(o18) ? `open ${o18.toLocaleString('en-US', { maximumFractionDigits: 2 })}${Number.isFinite(vm) ? ` · VIX ±${Math.round(vm)}` : ''}` : '';
    const n = this.items.filter((x) => x.kind === 'event').length;
    this.hint.textContent = `${etParts(t).hm} ET · ${n ? n + ' USD event' + (n === 1 ? '' : 's') : 'no USD events'}`;
    this.cenW = this.cen.offsetWidth; this.cenH = this.cen.offsetHeight; this.cenLast = null;
  }
  legendFor() {
    this.legend.innerHTML = [[KCSS[0], 'Asia'], [KCSS[1], 'London'], [KCSS[3], 'NY'], [CSS_GOOD, 'entry window'], ['#ff7ad9', 'high-impact news'], ['#ffffff', 'now']]
      .map(([c, t]) => `<span><i style="background:${c};box-shadow:0 0 6px ${c}"></i>${t}</span>`).join('');
  }
  labelsFor() {
    const defs = [];
    for (let h = 18, k = 0; k < 8; k++, h = (h + 3) % 24) {
      const ang = turnOfMin(h * 60) * TAU, p = this.world(ang, RL - 0.06, 0.02, new THREE.Vector3());
      defs.push({ text: pad2(h), p, ax: 0.5 - Math.sin(ang) * 0.5, ay: 0.5 + Math.cos(ang) * 0.5, cls: 'hr' + (h === 18 ? ' t18' : ''), keep: true });
    }
    for (const b of this.boxes) {
      if (b.kind === KIND.rth) continue;
      const mid = (turnOfMin(b.a) + this.arcLen(b) / 2) % 1, ang = mid * TAU, p = this.world(ang, (S0 + S1) / 2, 0.03, new THREE.Vector3());
      const tk = b.hiT && b.loT ? 'both taken' : b.hiT ? 'high taken' : b.loT ? 'low taken' : Number.isFinite(b.hi) ? 'untaken' : '';
      defs.push({ html: `${esc(b.label.replace(/ box$/, ''))}${tk ? `<em>${tk}</em>` : ''}`, p, cls: 'bx', color: KCSS[b.kind], avoid: true });
    }
    this.setLabels(defs);
  }

  // ---------------------------------------------------------------- picking + tooltip
  nearest(px, py, maxPx) {
    const cam = this.camera; _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    let best = null, bd = maxPx * maxPx;
    const test = (p, o) => { _v.copy(p).applyEuler(this.g.rotation).applyMatrix4(_m); if (_v.z > 1) return; const dx = (_v.x + 1) / 2 * this.w - px, dy = (1 - _v.y) / 2 * this.h - py, dd = dx * dx + dy * dy; if (dd < bd) { bd = dd; best = o; } };
    for (const sl of this.slots) if (!sl.dead && sl.a > 0.3) test(sl.p, sl);
    if (!best) for (const it of this.items) if (it.pickOnly) { const b = it.box, L = this.arcLen(b); for (let k = 0; k <= 4; k++) { const a = (turnOfMin(b.a) + L * k / 4) % 1; test(_w.set(Math.sin(a * TAU) * SM, Math.cos(a * TAU) * SM, 0), { it, p: new THREE.Vector3(Math.sin(it.ang * TAU) * SM, Math.cos(it.ang * TAU) * SM, 0.02), box: true, key: it.key, idx: -1, col: new THREE.Color(it.col) }); } }
    return best;
  }
  pickAt(px, py) { const sl = this.nearest(px, py, 26); this.select(sl); if (sl) this.emit(sl.it.row); }
  select(sl) { this.sel = sl; this.u.uSel.value = sl && sl.idx >= 0 ? sl.idx : -1; this.tipFor(this.hov || sl); }
  hoverAt(sl) {
    if (sl === this.hov || (sl && this.hov && sl.key === this.hov.key)) return;
    this.hov = sl; this.u.uHov.value = sl && sl.idx >= 0 ? sl.idx : -1; this.canvas.style.cursor = sl ? 'pointer' : 'grab';
    this.tipFor(sl || this.sel);
  }
  tipFor(sl) {
    if (!sl) { this.showTip(null); return; }
    const it = sl.it, r = it.row || {}, fmtP = (v) => (Number.isFinite(v) ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
    const when = (t) => (Number.isFinite(num(t, NaN)) ? etParts(num(t, NaN)).hm + ' ET' : '');
    let html;
    if (it.kind === 'event') html = `<b>${esc(r.title || 'event')}</b> <u style="color:${it.css}">${esc(it.imp)}</u><br><i>${when(r.t)}${it.imp === 'high' ? ' · ±15/30 min window' : ''}</i>`;
    else if (it.kind === 'trade') { const x = it.x; html = `<b>${num(r.dir, 0) === 1 || /long/i.test(r.side || '') ? 'LONG' : 'SHORT'} · ${when(r.t)}</b>${x.open ? ' <u style="color:#67e8f9">open</u>' : ` <b style="color:${it.css}">${fmtUsd(x.pnl)}</b>${Number.isFinite(x.r) ? `<u style="color:${it.css}">${fmtR(x.r, 1)}</u>` : ''}`}${Number.isFinite(num(r.exit_t, NaN)) ? `<br><i>exit ${when(r.exit_t)}${r.exit ? ' · ' + esc(r.exit) : ''}</i>` : ''}`; }
    else if (it.kind === 'setup') html = `<b>LIT ${num(r.dir, 0) === 1 ? 'LONG' : 'SHORT'} limit armed · ${when(r.t)}</b>${r.label ? `<br><i>${esc(r.label)}</i>` : ''}${Number.isFinite(num(r.expires_t, NaN)) ? `<br><i>expires ${when(r.expires_t)}</i>` : ''}`;
    else { const b = it.box; html = `<b style="color:${it.css}">${esc(b.label)}</b> <i>${hm(b.a)}-${hm(b.b)} ET</i>${Number.isFinite(b.hi) ? `<br>high <b>${fmtP(b.hi)}</b>${b.hiT ? ' <i>taken</i>' : ''} · low <b>${fmtP(b.lo)}</b>${b.loT ? ' <i>taken</i>' : ''}` : ''}`; }
    this.showTip(sl.key, html);
  }
  devTapPoint() { const sl = this.slots.find((s) => !s.dead && s.a > 0.5); if (!sl) return null; const p = this.screen(_v.copy(sl.p).applyEuler(this.g.rotation)); return [p.x, p.y]; }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u, red = Q.reduced;
    u.uTime.value = lt;
    const o = this.orbit;
    if (!o.dragging && o.idle > 2.5 && !red) { o.yaw += (Math.sin(lt * 0.25) * 0.13 - o.yaw) * Math.min(1, dt * 0.5); o.pitch += (0.1 + Math.sin(lt * 0.17) * 0.05 - o.pitch) * Math.min(1, dt * 0.5); }
    const moved = this.camStep(dt);
    if (this.hasData && this.introAt < 0) this.handTo = this.handAt(this.clockNow());
    if (this.introAt >= 0) {
      const dur = 1.5 * Math.max(0.4, this.handTo), k = clamp((lt - this.introAt) / dur, 0, 1);
      this.hand = this.handTo * outCubic(k); u.uIn.value = this.handTo < 0.02 ? 2 * outCubic(k) : this.hand + 0.008;
      for (const sl of this.slots) if (sl.wait && (sl.ang <= this.hand + 0.001 || (sl.ang > this.handTo && k >= 0.5))) { sl.wait = false; sl.t0 = lt; }
      if (k >= 1) { this.introAt = -1; u.uIn.value = 2; for (const sl of this.slots) if (sl.wait) { sl.wait = false; sl.t0 = lt; } this.camKey = ''; }
      this.animating = true;
    } else {
      this.hand += (this.handTo - this.hand) * (red ? 1 : Math.min(1, dt * 3));
      if (Math.abs(this.handTo - this.hand) < 1e-6) this.hand = this.handTo;
    }
    u.uHand.value = this.hand;
    const ang = this.hand * TAU, sn = Math.sin(ang), cs = Math.cos(ang);
    const HP = this.handLine.geometry.attributes.position;
    HP.setXYZ(0, sn * 0.3, cs * 0.3, 0.03); HP.setXYZ(1, sn * TR0, cs * TR0, 0.03); HP.setXYZ(2, sn * S1, cs * S1, 0.04); HP.setXYZ(3, sn * (BZ1 + 0.07), cs * (BZ1 + 0.07), 0.04);
    HP.needsUpdate = true;
    const beat = red ? 0.5 : 0.5 + 0.5 * Math.sin(lt * 2.6);
    this.head.position.set(sn * SM, cs * SM, 0.08); this.head.scale.setScalar(0.3 + 0.06 * beat); this.head.material.opacity = 0.75 + 0.2 * beat;
    u.uBright.value = 0.9 + 0.3 * beat;
    // inside the entry window now?
    const N = etParts(this.clockNow()), min = N.frac * 1440;
    this.wU.uActive.value = this.hasData && !this.closed && this.wins.some(([a, b]) => (a <= b ? min >= a && min < b : min >= a || min < b)) ? 1 : 0;
    for (let i = 0; i < MAXB; i++) if (this.flash[i] > 0) this.flash[i] = Math.max(0, this.flash[i] - dt / 1.2);
    this.sU.uA.value = this.wU.uA.value = this.tU.uA.value = this.hasData ? 1 : 0.5;
    // the next high / medium event pings
    if (this.hasData) {
      const nowS = this.clockNow(); let ping = null;
      for (const sl of this.slots) if (!sl.dead && sl.it.kind === 'event' && sl.it.imp !== 'low' && sl.it.t > nowS && (!ping || sl.it.t < ping.it.t)) ping = sl;
      const pk = ping ? ping.key : '';
      if (pk !== this.pingKey) { const A = this.pearls.geometry.attributes.aMisc; for (const sl of this.slots) A.setZ(sl.idx, sl === ping ? 1 : 0); A.needsUpdate = true; this.pingKey = pk; }
    }
    if (this.animating) this.animate(); else if (this.hasData && lt - (this._dynAt || 0) > 5) { this._dynAt = lt; this.writeDynamic(); }
    const s = this.sel;
    if (s && !s.dead) {
      const pulse = red ? 1 : 1 + 0.07 * Math.sin(lt * 5);
      this.reticle.visible = true; this.reticle.position.copy(s.p); this.reticle.scale.setScalar(Math.max(0.36, (s.it.size || 0.2) * 1.8) * pulse);
      this.reticle.material.rotation = red ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95; this.reticle.material.color.copy(s.col).lerp(_c.set('#ffffff'), 0.5);
    } else this.reticle.visible = false;
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.nearest(hx, hy, 16)); }
    if (moved || this.animating || this.introAt >= 0) this.placeLabels();
    const ts = this.hov || this.sel;
    if (ts && this.tipKey != null) { const p = this.screen(_v.copy(ts.p).applyEuler(this.g.rotation)); this.placeTip(p.x, p.y, 14); }
    if (this.hasData) {
      if (lt - this.txtAt > 0.5) { this.txtAt = lt; this.writeHtml(false); }
      if (moved || this.cenLast == null) {
        const p = this.screen(_v.set(0, 0, 0));
        const tf = `translate3d(${(p.x - (this.cenW || 100) / 2).toFixed(1)}px,${(p.y - (this.cenH || 40) / 2 - 2).toFixed(1)}px,0)`;
        if (tf !== this.cenLast) { this.cen.style.transform = tf; this.cenLast = tf; }
      }
    }
  }
}
