// News Radar (News page hero): the USD events of the next 24 hours as blips on a 3D radar.
//   Bearing = time of day in ET (00:00 at the top, clockwise, like a 24-hour clock face), distance from the centre = how
//   far ahead: now is the hub, +24h is the rim (the first hours get the most room). An event that has happened sinks into
//   the hub and fades out over 6 hours; events 24-48h ahead wait dimly on the rim. A beam sweeps the disc and every blip
//   it crosses flashes and sends out an echo ring; with reduced motion the beam rests on the current time of day.
//   Blip size = impact (high ones get a cross flare), colour by kind: FOMC magenta, CPI/PCE amber, NFP/claims cyan, GDP
//   coral, auctions violet, speakers soft white, other lavender. The killzones (09:30-11:30, 13:30-15:30 ET) glow as
//   green arcs on the time ring with a faint sector over the disc; the session shows as a thin violet band outside them.
//   A thin white spoke marks the current time of day. An event within 15 minutes pulses (rings on the disc, the hub
//   throbs amber). The next event's countdown is a big HTML number (bottom-left; left column on a wide card) and the
//   next blip wears a ping ring and a tag. Legend by kind with counts: tap a chip to isolate that kind (tap again for all).
//   Tap a blip -> opts.onPick(event) (the page's event object); mouse hover shows the tooltip; drag to turn the radar.
//   First data: the beam starts at "now" and reveals the blips in time order; new data: newcomers pop in, leavers fade.
// setData({ now: unix seconds, events: [{ t: unix seconds, title, impact: 'high'|'medium'|'low',
//   kind: 'cpi'|'nfp'|'fomc'|'pce'|'gdp'|'claims'|'auction'|'speaker'|'other', source, actual?, forecast?, previous?, surprise? }],
//   killzones: [[startMin, endMin], ...] (ET minutes; default the two trading windows), session: { open: unix, close: unix } })
//   The clock keeps running from `now` (the countdown ticks and the blips drift inward in real time).
// Draw calls ~13 whatever the event count; particles: 1 blip + 1 shadow + 1 echo ring + 1 drop line per event + 800 dust (650 phone, 300 lite).
import { THREE, Q, glowTexture, POINT_FRAG, count, Hud, addBackdrop, addNebula, addDust, ringTexture, sprite, additive, attrs,
  paintBackdrop, clamp, smooth, fract, num, esc, hash, div, injectStyle } from './hud.js';

const KIND = {
  fomc: { col: '#ff2bd6', css: '#ff7ad9', label: 'FOMC' },
  cpi: { col: '#ffb347', css: '#ffc46b', label: 'CPI' },
  pce: { col: '#ffb347', css: '#ffc46b', label: 'PCE' },
  nfp: { col: '#22d3ee', css: '#67e8f9', label: 'NFP' },
  claims: { col: '#22d3ee', css: '#67e8f9', label: 'claims' },
  gdp: { col: '#ff7a59', css: '#ff9f85', label: 'GDP' },
  auction: { col: '#8b5cf6', css: '#b9a6ff', label: 'auction' },
  speaker: { col: '#e6e8ff', css: '#eef0fb', label: 'speaker' },
  other: { col: '#9aa0c8', css: '#c3c6e6', label: 'other' },
};
const KORDER = Object.keys(KIND);
const IMPACT = { high: 2, medium: 1, med: 1, low: 0 };
const IMPACT_TXT = ['low', 'medium', 'high'];
const KZ_DEFAULT = [[570, 690], [810, 930]];
const R = 2.2, HUB = 0.22, PERIOD = 7, PAST = 21600, AHEAD = 86400, FAR = 172800, IMM = 900;
const HOURS = [1, 2, 4, 8, 12, 24];
const DAY = 86400;
const _v = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color();
const ALTS = (dx, dy) => [{ ax: 1, ay: 1, dx: -dx, dy: -dy }, { ax: 0, ay: 0, dx, dy }, { ax: 1, ay: 0, dx: -dx, dy }];
const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s);
const pad2 = (v) => String(v).padStart(2, '0');
// seconds to add to UTC for an ET wall clock at that instant (DST-aware; a fixed guess if Intl has no zones)
function etOffset(unix) {
  try {
    const f = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric' });
    const P = {}; for (const { type, value } of f.formatToParts(new Date(unix * 1000))) P[type] = value;
    return Math.round(Date.UTC(+P.year, +P.month - 1, +P.day, +P.hour % 24, +P.minute, +P.second) / 1000 - unix);
  } catch { const m = new Date(unix * 1000).getUTCMonth(); return (m >= 2 && m <= 10 ? -4 : -5) * 3600; }
}
const etDay = (unix, off) => Math.floor((unix + off) / DAY);
const etTime = (unix, off) => { const s = ((unix + off) % DAY + DAY) % DAY; return pad2(Math.floor(s / 3600)) + ':' + pad2(Math.floor(s / 60) % 60); };
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const etWeekday = (unix, off) => WD[((etDay(unix, off) + 4) % 7 + 7) % 7];
// hours:minutes:seconds until t (or since, for the tooltip)
function countdown(dt) {
  const a = Math.abs(dt);
  if (a >= DAY) return Math.floor(a / DAY) + 'd ' + Math.floor(a % DAY / 3600) + 'h';
  const h = Math.floor(a / 3600), m = Math.floor(a / 60) % 60, s = Math.floor(a) % 60;
  return (h ? h + ':' + pad2(m) : String(m)) + ':' + pad2(s);
}
function ago(dt) {
  const a = Math.abs(dt);
  if (a < 60) return 'now';
  if (a < 3600) return Math.round(a / 60) + ' min';
  if (a < DAY) { const h = Math.floor(a / 3600), m = Math.round(a % 3600 / 60); return h + 'h' + (m ? ' ' + m + 'm' : ''); }
  return Math.floor(a / DAY) + 'd ' + Math.floor(a % DAY / 3600) + 'h';
}
const fmtVal = (v) => (v == null || v === '' ? null : typeof v === 'number' ? (Math.abs(v) >= 100 ? Math.round(v).toLocaleString('en-US') : String(+v.toFixed(2))) : String(v));
// normalised radius (1 = rim) of an event dt seconds away, the same curve the shaders use
const rOf = (dt) => (dt >= 0 ? HUB + (1 - HUB) * Math.pow(Math.min(dt, AHEAD) / AHEAD, 0.6) : HUB * (1 - Math.min(1, -dt / PAST)));

// ------------------------------------------------------------------ shaders
// shared head of the blip shaders: the position of an event from its time and bearing
const BLIP_VARY = `varying vec3 vColor; varying float vAlpha; varying float vHi; varying float vSpike; varying float vFlash;`;
const BLIP_HEAD = BLIP_VARY + `
attribute vec3 aCol; attribute float aT; attribute float aAng; attribute float aImp; attribute vec4 aMisc; attribute float aBorn; attribute float aDie;
uniform float uNow; uniform float uTime; uniform float uPix; uniform float uMotion; uniform float uR; uniform float uHub; uniform float uBeam;
uniform float uSel; uniform float uHov; uniform float uIso; uniform float uFocus;
float rOf(float dt){ return dt >= 0.0 ? uHub + (1.0 - uHub) * pow(min(dt, 86400.0) / 86400.0, 0.6) : uHub * (1.0 - min(1.0, -dt / 21600.0)); }
float popOf(float since){ float k = clamp(since * 2.0, 0.0, 1.0), u = k - 1.0; return since < 0.0 ? 0.0 : 1.0 + 2.4 * u * u * u + 1.4 * u * u; }
void main(){
  float dt = aT - uNow;
  float r = rOf(dt) * uR, ang = aAng * 6.2831853, h = 0.1 + aImp * 0.09;
  vec3 p = vec3(sin(ang) * r, h, -cos(ang) * r);
  float since = uTime - aBorn, life = smoothstep(0.0, 0.45, since), pop = popOf(since);
  float die = aDie > 0.0 ? 1.0 - clamp((uTime - aDie) * 2.5, 0.0, 1.0) : 1.0;
  float past = dt < 0.0 ? 1.0 - min(1.0, -dt / 21600.0) : 1.0;
  float vis = dt < 0.0 ? past * past : (dt > 86400.0 ? 0.42 * (1.0 - smoothstep(86400.0, 172800.0, dt)) : 1.0);
  float ph = fract(uBeam - aAng + 1.0);
  float flash = exp(-ph * 12.0) * uMotion;
  float imm = step(0.0, dt) * step(dt, 900.0);
  float iso = uIso < -0.5 ? 1.0 : mix(0.1, 1.1, 1.0 - step(0.5, abs(aMisc.z - uIso)));
  float hi = max(1.0 - step(0.5, abs(aMisc.y - uSel)), (1.0 - step(0.5, abs(aMisc.y - uHov))) * 0.75);
  float base = life * die * vis * iso;`;
const BLIP_V = BLIP_HEAD + `
  float pulse = 1.0 + imm * 0.25 * (1.0 + sin(uTime * 7.0) * uMotion);
  float size = (0.17 + aImp * 0.075) * pop * die * pulse * (1.0 + flash * 0.45 + hi * 0.5);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp(size * uPix / -mv.z, 0.0, 130.0);
  gl_Position = projectionMatrix * mv;
  float depth = clamp(1.15 - (-mv.z - uFocus) * 0.06, 0.72, 1.2);
  vColor = mix(aCol, vec3(1.0), imm * 0.3) * depth * (1.0 + flash * 1.1 + imm * 0.35);
  vAlpha = base; vHi = hi; vSpike = step(1.5, aImp) * (0.6 + 0.4 * flash); vFlash = flash;
}`;
const BLIP_F = BLIP_VARY + `
void main(){
  vec2 q = gl_PointCoord - 0.5; float d2 = dot(q, q) * 4.0; if (d2 > 1.0) discard;
  float d = sqrt(d2), halo = 1.0 - d2; halo = halo * halo * halo;
  float core = exp(-d2 * 30.0);
  float spk = (exp(-abs(q.x) * 70.0) + exp(-abs(q.y) * 70.0)) * (1.0 - d) * vSpike;
  float hi = vHi * exp(-pow((d - 0.86) * 10.0, 2.0));
  float ring = exp(-pow((d - 0.62) * 14.0, 2.0)) * 0.35;
  vec3 c = mix(vColor, vec3(1.0), clamp(core * 0.55 + hi * 0.25 + vFlash * 0.2, 0.0, 1.0));
  gl_FragColor = vec4(c * (halo * 0.42 + core * 1.05 + spk * 0.8 + ring + hi * 0.9) * vAlpha, 1.0);
}`;
// echo rings on the disc: after the beam passes a blip (or, within 15 minutes of the event, a steady pulse)
const RING_V = BLIP_HEAD + `
  float eph = ph / 0.3, ipp = fract(uTime * 0.7 + aMisc.x * 3.0);
  float k = mix(eph, ipp, imm), on = mix(step(ph, 0.3) * uMotion, 1.0, imm);
  float rad = (0.3 + aImp * 0.12) * (0.5 + k * 2.6) * (1.0 + imm * 0.7);
  vec4 mv = modelViewMatrix * vec4(p.x, 0.012, p.z, 1.0);
  gl_PointSize = clamp(rad * uPix / -mv.z, 0.0, 200.0);
  gl_Position = projectionMatrix * mv;
  vColor = mix(aCol, vec3(1.0), 0.25); vAlpha = on * (1.0 - k) * (1.0 - k) * base * (0.55 + 0.45 * imm) * step(0.001, pop); vHi = 0.0; vSpike = 0.0; vFlash = 0.0;
}`;
const RING_F = BLIP_VARY + `
void main(){ vec2 q = gl_PointCoord - 0.5; float d = length(q) * 2.0; if (d > 1.0) discard;
  float ring = exp(-pow((d - 0.86) * 16.0, 2.0)); gl_FragColor = vec4(vColor * ring * vAlpha, 1.0); }`;
// a dim pool of light under every blip (the disc is flat: it anchors the height)
const SHADOW_V = BLIP_HEAD + `
  vec4 mv = modelViewMatrix * vec4(p.x, 0.006, p.z, 1.0);
  gl_PointSize = clamp((0.14 + aImp * 0.06) * pop * die * uPix / -mv.z, 0.0, 50.0);
  gl_Position = projectionMatrix * mv;
  vColor = aCol * (0.35 + flash * 0.4); vAlpha = base * 0.8; vHi = 0.0; vSpike = 0.0; vFlash = 0.0;
}`;
// drop line from the disc (aEnd 0) up to the blip (aEnd 1)
const DROP_V = `attribute float aEnd;` + BLIP_HEAD + `
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p.x, mix(0.01, h, aEnd), p.z, 1.0);
  vColor = aCol * (0.2 + 0.5 * aEnd) * (1.0 + flash * 1.5); vAlpha = base * (0.35 + hi * 0.6) * step(0.001, pop); vHi = 0.0; vSpike = 0.0; vFlash = 0.0;
}`;
const DROP_F = BLIP_VARY + `void main(){ gl_FragColor = vec4(vColor * vAlpha, 1.0); }`;
// the disc: hour rings, spokes, the hub, the beam, killzone arcs + sectors, the session band, the "now" spoke, the rim
const DISC_V = `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const DISC_F = `uniform float uR; uniform float uHub; uniform float uBeam; uniform float uNowA; uniform float uTime; uniform float uMotion; uniform float uIn; uniform float uAlert;
uniform vec3 uCol; uniform vec3 uBeamCol; uniform vec3 uKzCol; uniform vec3 uSesCol; uniform vec3 uAlertCol;
uniform vec2 uKz[4]; uniform int uKzN; uniform vec2 uSes; uniform float uHasSes;
varying vec2 vP;
float rOf(float h){ return uHub + (1.0 - uHub) * pow(h / 24.0, 0.6); }
float ring(float r, float rr){ float d = (r - rr) * uR; return exp(-d * d * 2200.0); }
float band(float r, float a, float b){ return smoothstep(a - 0.004, a, r) * smoothstep(b + 0.004, b, r); }
float arc(float a, vec2 se, float r){ float len = fract(se.y - se.x + 1.0); if (len < 0.0005) len = 1.0; float x = fract(a - se.x + 1.0), w = 0.0025 / max(r, 0.2);
  return smoothstep(0.0, w, x) * smoothstep(len, len - w, x); }
void main(){
  vec2 p = vP; float rw = length(p), r = rw / uR;
  if (r > 1.26) discard;
  float a = fract(atan(p.x, p.y) / 6.2831853 + 1.0), t = uTime * uMotion;
  float reveal = smoothstep(r - 0.1, r + 0.02, uIn * 1.15), disc = step(r, 1.0), outer = step(uHub, r);
  vec3 c = uCol * disc * (0.04 + 0.05 * exp(-r * r * 2.5)) * reveal;
  float rings = ring(r, rOf(1.0)) * 0.7 + ring(r, rOf(2.0)) * 0.6 + ring(r, rOf(4.0)) * 0.7 + ring(r, rOf(8.0)) * 0.7 + ring(r, rOf(12.0)) * 1.0 + ring(r, 1.0) * 1.7;
  c += uCol * rings * 0.24 * reveal;
  float hub = smoothstep(uHub + 0.01, uHub - 0.04, r), hubEdge = exp(-pow((r - uHub) * uR * 45.0, 2.0));
  float beat = 1.0 + uAlert * 0.4 * sin(t * 7.0);
  vec3 hc = mix(uCol, uAlertCol, uAlert);
  c += hc * (hub * (0.08 + 0.14 * exp(-r * r * 20.0)) + hubEdge * 0.6) * beat * (1.0 + uAlert * 0.7);
  float sp = abs(fract(a * 24.0 + 0.5) - 0.5) / 24.0 * 6.2831853 * rw, sp4 = abs(fract(a * 4.0 + 0.5) - 0.5) / 4.0 * 6.2831853 * rw;
  float spoke = exp(-sp * sp * 2600.0) * 0.07 + exp(-sp4 * sp4 * 1800.0) * 0.15;
  c += uCol * spoke * outer * disc * reveal;
  float kz = 0.0;
  for (int i = 0; i < 4; i++) { if (i >= uKzN) break; kz = max(kz, arc(a, uKz[i], r)); }
  c += uKzCol * kz * (disc * outer * 0.035 + band(r, 1.0, 1.045) * 0.95) * reveal;
  c += uSesCol * uHasSes * arc(a, uSes, r) * band(r, 1.062, 1.082) * 0.6 * reveal;
  float tk = exp(-sp * sp * 3200.0) * band(r, 1.055, 1.09) * 0.35 + exp(-sp4 * sp4 * 2600.0) * band(r, 1.05, 1.115) * 0.7;
  c += uCol * tk * reveal;
  float ph = fract(uBeam - a + 1.0), head = exp(-pow(ph * 6.2831853 * rw / 0.03, 2.0)), trail = exp(-ph * 7.0) * smoothstep(0.0, 0.015, ph);
  float beamMask = disc * smoothstep(uHub * 0.3, uHub, r);
  c += uBeamCol * beamMask * (trail * 0.3 * (0.6 + 0.4 * r) + head * 0.9) * reveal;
  float dn = abs(fract(a - uNowA + 0.5) - 0.5) * 6.2831853 * rw;
  c += vec3(0.9, 0.94, 1.0) * exp(-dn * dn * 5000.0) * outer * step(r, 1.1) * 0.45 * reveal;
  c *= 1.0 - smoothstep(1.1, 1.26, r);
  gl_FragColor = vec4(c, 1.0);
}`;

const CSS = `.fxh-newsradar .fxh-leg span{pointer-events:auto;cursor:pointer;padding:3px 6px;margin:-3px -2px;border-radius:7px;border:1px solid transparent;transition:background .2s,border-color .2s,opacity .2s}
.fxh-newsradar .fxh-leg span.on{background:rgba(124,92,255,.18);border-color:rgba(167,139,250,.45)}
.fxh-newsradar .fxh-leg.iso span:not(.on):not(.kz){opacity:.45}
.fxh-newsradar .fxh-leg span.kz{pointer-events:none;cursor:default}
.fxh-newsradar .fxh-leg i.arc{width:12px;height:6px;border-radius:0 0 6px 6px;background:transparent;border:1.5px solid #4ef0b0;border-top:0}
.fxn-cd{position:absolute;left:10px;bottom:9px;text-align:left;line-height:1;white-space:nowrap;max-width:64%;overflow:hidden}
.fxn-cap{font-size:8.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(214,218,250,.62);text-shadow:0 0 6px #07080c}
.fxn-cap b{color:inherit;font-weight:800}
.fxn-big{margin-top:4px;font-size:30px;font-weight:800;letter-spacing:-.01em;color:#fff;font-variant-numeric:tabular-nums;text-shadow:0 0 16px rgba(5,3,14,.95),0 0 4px rgba(5,3,14,.95),0 0 26px rgba(0,0,0,.6)}
.fxn-big.now{color:#ffd36b;text-shadow:0 0 18px rgba(255,180,60,.55),0 0 4px rgba(5,3,14,.95)}
.fxn-big.none{font-size:22px;color:rgba(214,218,250,.55)}
.fxn-sub{margin-top:5px;font-size:11px;font-weight:700;color:rgba(232,234,255,.92);text-shadow:0 0 8px rgba(5,3,14,.95),0 0 3px rgba(5,3,14,.95);overflow:hidden;text-overflow:ellipsis}
.fxn-sub em{font-style:normal;font-weight:600;color:rgba(188,192,236,.66)}
.fxh-newsradar.wide .fxn-cd{left:16px;top:50%;bottom:auto;transform:translateY(-50%);width:min(250px,34%);white-space:normal}
.fxh-newsradar.wide .fxn-big{font-size:40px}.fxh-newsradar.wide .fxn-sub{font-size:12px;white-space:nowrap}
.fxh-newsradar .fxh-l.tag{line-height:1.25}.fxh-newsradar .fxh-l.tag em{font-style:normal;font-weight:600;color:rgba(214,218,250,.72)}
.fxh-newsradar .fxh-empty{top:auto;bottom:16px;transform:translateX(-50%)}
.fxh-newsradar.wide .fxh-empty{left:auto;right:12%;bottom:14px;transform:none}`;

// ------------------------------------------------------------------ the view
export class NewsRadar extends Hud {
  constructor(opts = {}) {
    super(opts, { name: 'newsradar', fov: 36, empty: 'No USD events in the next 24h',
      orbit: { yaw: 0, pitch: 0.95, auto: 0.03, min: -0.6, max: 0.6, pitchMin: 0.55, pitchMax: 1.3 } });
    injectStyle('fxh-nr-css', CSS);
    this.slots = []; this.byKey = new Map(); this.items = []; this.cap = 0; this.kinds = []; this.iso = -1; this.hasDead = false;
    this.sel = null; this.hov = null; this.sig = null; this.introAt = -1; this.introDone = false; this.busyUntil = 0; this.lt = 0;
    this.off = etOffset(Date.now() / 1000); this.clockOff = 0; this.base = Math.floor(Date.now() / 1000); this.nowU = this.base;
    this.beamTurn = 0; this.alert = 0; this.alertWant = 0; this.next = null; this.nextSlot = null; this.cdSec = -1; this.cdFor = null; this.labelAcc = 0;
    this.kz = KZ_DEFAULT; this.ses = null;
    Object.assign(this.u, { uNow: { value: 0 }, uR: { value: R }, uHub: { value: HUB }, uBeam: { value: 0 }, uSel: { value: -1 }, uHov: { value: -1 }, uIso: { value: -1 }, uFocus: { value: 12 } });
    this.build(); this.ensureCap(64); this.buildHtml();
  }

  // ---------------------------------------------------------------- scene
  build() {
    const S = this.scene, u = this.u;
    this.bgU = addBackdrop(S, [0.5, 0.5]);
    addNebula(S, [['#6d28d9', -4, 2, -8, 14, 8, 0.1], ['#22d3ee', 4.5, 0.5, -8, 10, 6, 0.04], ['#ff2bd6', 3, -1.5, -7, 9, 6, 0.04]]);
    this.dust = addDust(S, u, { n: count(Q.phone ? 650 : 800, 300), box: [4, 2, 3], cy: 0.6, seed: 77 });
    this.dU = { uR: u.uR, uHub: u.uHub, uBeam: u.uBeam, uNowA: { value: 0 }, uTime: u.uTime, uMotion: u.uMotion, uIn: { value: 0 }, uAlert: { value: 0 },
      uCol: { value: new THREE.Color('#6f7cff') }, uBeamCol: { value: new THREE.Color('#5ee8ff') }, uKzCol: { value: new THREE.Color('#2ee59d') },
      uSesCol: { value: new THREE.Color('#8b5cf6') }, uAlertCol: { value: new THREE.Color('#ffb347') },
      uKz: { value: [new THREE.Vector2(), new THREE.Vector2(), new THREE.Vector2(), new THREE.Vector2()] }, uKzN: { value: 0 }, uSes: { value: new THREE.Vector2() }, uHasSes: { value: 0 } };
    this.disc = new THREE.Mesh(new THREE.PlaneGeometry(R * 2.6, R * 2.6), additive(DISC_V, DISC_F, this.dU, { side: THREE.DoubleSide }));
    this.disc.rotation.x = -Math.PI / 2; this.disc.renderOrder = 2; S.add(this.disc);
    this.hubGlow = sprite(S, glowTexture(), '#6f7cff', 3, 0.4); this.hubGlow.visible = true; this.hubGlow.position.set(0, 0.02, 0); this.hubGlow.scale.setScalar(1.3);
    this.flare = sprite(S, glowTexture(), '#5ee8ff', 9, 0.6); this.flare.visible = true; this.flare.scale.setScalar(0.55);
    const ret = ringTexture(true), ring = ringTexture(false); this.textures.push(ret, ring);
    this.reticle = sprite(S, ret, '#ffffff', 12);
    this.ping = sprite(S, ring, '#ffffff', 11);
    S.traverse((o) => { o.frustumCulled = false; });
    const P = [];
    for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2; P.push(Math.sin(a) * R * 1.16, 0, -Math.cos(a) * R * 1.16, Math.sin(a) * R * 0.8, 0.42, -Math.cos(a) * R * 0.8); }
    this.anchors = new Float32Array(P); this.T.set(0, 0.08, 0); this.fill = [0.93, 0.9];
  }
  ensureCap(n) {
    if (n <= this.cap) return;
    const cap = Math.max(64, Math.ceil(n * 1.25 / 32) * 32), u = this.u;
    const spec = { position: [3], aCol: [3], aT: [1], aAng: [1], aImp: [1], aMisc: [4], aBorn: [1, 1], aDie: [1, 1] };
    const bg = attrs(cap, spec), lg = attrs(cap * 2, { ...spec, aEnd: [1] });
    if (!this.blips) {
      this.blips = new THREE.Points(bg, additive(BLIP_V, BLIP_F, u)); this.blips.renderOrder = 8;
      this.rings = new THREE.Points(bg, additive(RING_V, RING_F, u)); this.rings.renderOrder = 6;
      this.shadows = new THREE.Points(bg, additive(SHADOW_V, POINT_FRAG, u)); this.shadows.renderOrder = 5;
      this.drops = new THREE.LineSegments(lg, additive(DROP_V, DROP_F, u)); this.drops.renderOrder = 7;
      for (const o of [this.blips, this.rings, this.shadows, this.drops]) { o.frustumCulled = false; this.scene.add(o); }
    } else { this.blips.geometry.dispose(); this.drops.geometry.dispose(); for (const o of [this.blips, this.rings, this.shadows]) o.geometry = bg; this.drops.geometry = lg; }
    this.cap = cap;
  }
  buildHtml() {
    this.legend = div('fxh-leg'); this.ui.prepend(this.legend);
    this.legend.addEventListener('click', (e) => { const s = e.target.closest('span[data-k]'); if (!s) return; const k = +s.dataset.k; this.setIso(this.iso === k ? -1 : k); });
    this.cd = div('fxn-cd', this.ui, '<div class="fxn-cap"></div><div class="fxn-big none">—</div><div class="fxn-sub"></div>');
    this.cdCap = this.cd.children[0]; this.cdBig = this.cd.children[1]; this.cdSub = this.cd.children[2];
    this.hint = div('fxh-l h fix', this.ui);
  }
  retheme() { paintBackdrop(this.bgU); }
  // phone: legend on top, the countdown bottom-left; wide card: the countdown as a left column, the radar to its right
  relayout(w, h) {
    const wide = w / h > 1.45 && w > 560; this.ui.classList.toggle('wide', wide);
    const live = this.cd.isConnected, lh = this.legend.isConnected ? this.legend.offsetHeight : 14, ch = live ? this.cd.offsetHeight : 62, cw = live ? this.cd.offsetWidth : 240;
    this.region = wide ? [-1 + 2 * (cw + 36) / w, 1, -1 + 2 * 20 / h, 1 - 2 * (lh + 14) / h] : [-1, 1, -1 + 2 * (ch + 16) / h, 1 - 2 * (lh + 12) / h];
    if (!this.userRange) { const r = wide ? 0.75 : 0.55; this.orbit.min = -r; this.orbit.max = r; }
  }
  attach(el) { super.attach(el); this.relayout(this.w, this.h); }

  // ---------------------------------------------------------------- data
  setData(d, opts) {
    if (opts && typeof opts.onPick === 'function' && opts.onPick !== this._pickFn) this._onRow = opts.onPick;
    const src = d && typeof d === 'object' && !Array.isArray(d) ? d : { events: Array.isArray(d) ? d : [] };
    const list = Array.isArray(src.events) ? src.events : [];
    const nowU = num(src.now, Date.now() / 1000);
    this.clockOff = nowU - Date.now() / 1000; this.base = Math.floor(nowU); this.off = etOffset(nowU);
    const kz = (Array.isArray(src.killzones) ? src.killzones : KZ_DEFAULT).map((z) => [num(z?.[0]), num(z?.[1])]).filter((z) => Number.isFinite(z[0]) && Number.isFinite(z[1])).slice(0, 4);
    const so = num(src.session?.open), sc = num(src.session?.close), ses = Number.isFinite(so) && Number.isFinite(sc) ? { open: so, close: sc } : null;
    const items = [], seen = new Set(), kinds = new Map();
    let sig = JSON.stringify(kz) + '|' + (ses ? ses.open + '-' + ses.close : '') + '|' + list.length + ':', dropped = 0;
    for (let i = 0; i < list.length; i++) {
      const e = list[i]; if (!e || typeof e !== 'object') continue;
      const t = num(e.t); if (!Number.isFinite(t)) continue;
      if (t < nowU - PAST || t > nowU + FAR) { dropped++; continue; }          // out of the radar's window
      const kind = KIND[String(e.kind || '').toLowerCase()] ? String(e.kind).toLowerCase() : 'other';
      const imp = IMPACT[String(e.impact || '').toLowerCase()] ?? 1;
      const title = String(e.title ?? KIND[kind].label);
      let key = t + '|' + title + '|' + kind; if (seen.has(key)) key += '#' + i; seen.add(key);
      kinds.set(kind, (kinds.get(kind) || 0) + 1);
      items.push({ key, e, t, title, kind, imp, source: e.source != null ? String(e.source) : '', seed: hash(key), ang: fract((t + this.off) / DAY) });
      sig += key + '/' + imp + '/' + (e.source ?? '') + '/' + (e.actual ?? '') + '/' + (e.forecast ?? '') + '/' + (e.previous ?? '') + '/' + (e.surprise ?? '') + ',';
    }
    items.sort((a, b) => a.t - b.t);
    if (sig === this.sig) { for (const it of items) { const s = this.byKey.get(it.key); if (s) s.it.e = it.e; } this.syncNow(true); return; }
    this.sig = sig; this.kz = kz; this.ses = ses; this.dropped = dropped;
    this.kinds = KORDER.filter((k) => kinds.has(k)).map((k, i) => ({ key: k, i, n: kinds.get(k), ...KIND[k] }));
    const ki = new Map(this.kinds.map((k) => [k.key, k.i]));
    if (this.iso >= this.kinds.length) this.setIso(-1);
    for (const it of items) it.ki = ki.get(it.kind);
    this.items = items;
    const first = !this.introDone, now = this.lt, red = Q.reduced, n = items.length, nowA = this.nowAngle(nowU);
    const next = [], keep = new Set(); let busy = now;
    for (const it of items) {
      let sl = this.byKey.get(it.key);
      if (!sl || sl.dead) {
        sl = { key: it.key, p: new THREE.Vector3(), dead: false, born: now, die: 0 };
        // the first data: the beam starts at "now" and reveals the blips as it passes them (= in time order)
        if (!red) sl.born = first ? now + 0.35 + fract(it.ang - nowA) * PERIOD : now + 0.05 + it.seed * 0.4;
        busy = Math.max(busy, sl.born + 0.6);
      }
      sl.it = it; keep.add(it.key); next.push(sl);
    }
    for (const sl of this.slots) {
      if (keep.has(sl.key) || sl.dead) continue;
      sl.dead = true; sl.die = red ? Math.max(0.001, now - 1) : Math.max(0.001, now); next.push(sl); busy = Math.max(busy, now + 0.5); this.hasDead = true;
    }
    this.slots = next; this.byKey.clear();
    for (const sl of next) if (!sl.dead) this.byKey.set(sl.key, sl);
    this.busyUntil = busy + 0.2;
    if (this.sel?.dead) this.select(null);
    if (this.hov?.dead) this.hoverAt(null);
    if (first) { this.introDone = true; this.introAt = red ? -1 : now; this.dU.uIn.value = red ? 1 : 0; this.beamTurn = nowA; }
    this.writeStatic(); this.next = undefined; this.syncNow(true); this.frameScene();
    this.empty.textContent = list.length && !n ? 'No events in the last 6h or next 48h' : 'No USD events in the next 24h';
    this.empty.style.display = n ? 'none' : 'block';
    this.ui.classList.add('on');
    this.tipKey = null; this.tipFor(this.hov || this.sel);
  }
  writeStatic() {
    const n = this.slots.length; this.ensureCap(n);
    const B = this.blips.geometry.attributes, L = this.drops.geometry.attributes, base = this.base;
    for (let i = 0; i < n; i++) {
      const sl = this.slots[i], it = sl.it, c = _c.set(KIND[it.kind].col), die = sl.dead ? sl.die : 0; sl.idx = i;
      B.aCol.setXYZ(i, c.r, c.g, c.b); B.aT.setX(i, it.t - base); B.aAng.setX(i, it.ang); B.aImp.setX(i, it.imp); B.aMisc.setXYZW(i, it.seed, i, it.ki ?? 0, 0); B.aBorn.setX(i, sl.born); B.aDie.setX(i, die);
      for (let j = 0; j < 2; j++) {
        const q = i * 2 + j;
        L.aCol.setXYZ(q, c.r, c.g, c.b); L.aT.setX(q, it.t - base); L.aAng.setX(q, it.ang); L.aImp.setX(q, it.imp); L.aMisc.setXYZW(q, it.seed, i, it.ki ?? 0, 0); L.aBorn.setX(q, sl.born); L.aDie.setX(q, die); L.aEnd.setX(q, j);
      }
    }
    for (const g of [B, L]) for (const k in g) g[k].needsUpdate = true;
    this.blips.geometry.setDrawRange(0, n); this.drops.geometry.setDrawRange(0, n * 2);
    this.u.uSel.value = this.sel ? this.sel.idx : -1; this.u.uHov.value = this.hov ? this.hov.idx : -1;
  }
  nowAngle(u) { return fract((u + this.off) / DAY); }
  // world position of an event right now (the same curve as the shaders)
  posOf(it, out = _v) { const r = rOf(it.t - this.nowU) * R, a = it.ang * Math.PI * 2; return out.set(Math.sin(a) * r, 0.1 + it.imp * 0.09, -Math.cos(a) * r); }
  slotPos(it) { const sl = this.byKey.get(it.key); return !sl || sl.dead || this.lt < sl.born + 0.3 || it.t - this.nowU > AHEAD * 1.02 ? null : this.posOf(it, sl.p); }
  // the clock: real time from the data's `now`; the next event, the alert state and the countdown text (once a second)
  syncNow(force) {
    const nowU = Date.now() / 1000 + this.clockOff; this.nowU = nowU; this.u.uNow.value = nowU - this.base;
    this.dU.uNowA.value = this.nowAngle(nowU);
    let nx = null; for (const it of this.items) if (it.t >= nowU - 60) { nx = it; break; }
    this.alertWant = nx && nx.t - nowU <= IMM ? 1 : 0;
    const changed = nx !== this.next;
    if (changed) { this.next = nx; this.nextSlot = nx ? this.byKey.get(nx.key) : null; }
    const sec = Math.floor(nowU);
    if (sec !== this.cdSec || changed || force) { this.cdSec = sec; this.writeCountdown(nx, nowU, changed || force); }
    if (changed && !force) { this.labelsFor(); this.camKey = ''; }
  }
  writeCountdown(nx, nowU, full) {
    if (!nx) {
      if (!full) return;
      this.cdCap.textContent = this.items.length ? 'nothing else ahead' : 'next event'; this.cdBig.textContent = '—'; this.cdBig.className = 'fxn-big none'; this.cdSub.innerHTML = '';
      return;
    }
    const dt = nx.t - nowU, k = KIND[nx.kind], live = dt <= 0, off = this.off;
    if (full) {
      this.cdCap.innerHTML = `next · <b style="color:${k.css}">${esc(k.label)}</b> · ${etTime(nx.t, off)} ET${etDay(nx.t, off) !== etDay(nowU, off) ? ' ' + etWeekday(nx.t, off) : ''}`;
      this.cdSub.innerHTML = `${esc(trunc(nx.title, this.w < 480 ? 30 : 42))} <em>· ${IMPACT_TXT[nx.imp]} impact${nx.source ? ' · ' + esc(nx.source) : ''}</em>`;
    }
    this.cdBig.textContent = live ? 'NOW' : countdown(dt); this.cdBig.className = 'fxn-big' + (live ? ' now' : '');
    if (full && this.w > 10) this.relayout(this.w, this.h);
  }

  // ---------------------------------------------------------------- disc uniforms, labels, legend
  frameScene() {
    const U = this.dU; U.uKzN.value = this.kz.length;
    this.kz.forEach((z, i) => U.uKz.value[i].set(fract(z[0] / 1440), fract(z[1] / 1440)));
    if (this.ses) { U.uHasSes.value = 1; U.uSes.value.set(this.nowAngle(this.ses.open), this.ses.close - this.ses.open >= DAY ? this.nowAngle(this.ses.open) : this.nowAngle(this.ses.close)); }
    else U.uHasSes.value = 0;
    this.labelsFor(); this.legendFor();
  }
  labelsFor() {
    const defs = [], off = this.off, small = this.w < 520, nx = this.next;
    const at = (turn, rn, y = 0) => new THREE.Vector3(Math.sin(turn * Math.PI * 2) * rn * R, y, -Math.cos(turn * Math.PI * 2) * rn * R);
    for (const h of [0, 6, 12, 18]) defs.push({ text: pad2(h) + ':00', p: at(h / 24, 1.17), cls: 'h', avoid: true });
    for (const h of [1, 4, 12, 24]) defs.push({ text: h + 'h', p: at(0.125, rOf(h * 3600)), cls: 'h', dy: -1, avoid: true, show: () => this.dU.uIn.value > 0.6 });
    const kzName = (z) => (z[0] === 570 && z[1] === 690 ? 'AM killzone' : z[0] === 810 && z[1] === 930 ? 'PM killzone' : `${pad2(Math.floor(z[0] / 60))}:${pad2(z[0] % 60)}–${pad2(Math.floor(z[1] / 60))}:${pad2(z[1] % 60)}`);
    for (const z of this.kz) defs.push({ text: kzName(z), p: at(fract((z[0] + z[1]) / 2 / 1440), 1.2), cls: 'h', color: '#4ef0b0', avoid: true, show: () => this.dU.uIn.value > 0.8 });
    const tag = (it, lead, dx, dy) => ({ html: `${esc(trunc(it.title, small ? 18 : 26))}<br><em>${lead}${etTime(it.t, off)} ET</em>`, at: () => this.slotPos(it), ax: 0, ay: 1, dx, dy: -dy,
      cls: 'tag', color: KIND[it.kind].css, avoid: true, keep: true, alts: ALTS(dx, dy) });
    if (nx) defs.push(tag(nx, 'next · ', 12, 10));
    let m = 0;
    for (const it of this.items) { if (m >= (small ? 2 : 4)) break; if (it === nx || it.imp < 2 || it.t < this.nowU - 600) continue; m++; defs.push(tag(it, '', 10, 8)); }
    this.setLabels(defs);
    const n = this.items.length;
    this.hint.textContent = n ? `${n} event${n === 1 ? '' : 's'}${this.dropped ? ` · ${this.dropped} out of range` : ''} · tap a blip` : '';
  }
  legendFor() {
    this.legend.innerHTML = !this.items.length ? '' : this.kinds.map((k) => `<span data-k="${k.i}" class="fx-tap${this.iso === k.i ? ' on' : ''}"><i style="background:${k.css};box-shadow:0 0 6px ${k.css}"></i>${esc(k.label)} <b>${k.n}</b></span>`).join('')
      + (this.kz.length ? '<span class="kz"><i class="arc"></i>killzone</span>' : '');
    this.legend.classList.toggle('iso', this.iso >= 0);
    if (this.w > 10) this.relayout(this.w, this.h);
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
      if (sl.dead || this.lt < sl.born + 0.2 || (this.iso >= 0 && sl.it.ki !== this.iso)) continue;
      const dt = sl.it.t - this.nowU; if (dt < -PAST * 0.9 || dt > FAR) continue;
      this.posOf(sl.it, _v).applyMatrix4(_m); if (_v.z > 1) continue;
      const dx = (_v.x + 1) / 2 * this.w - px, dy = (1 - _v.y) / 2 * this.h - py, dd = dx * dx + dy * dy;
      if (dd < bd) { bd = dd; best = sl; }
    }
    return best;
  }
  pickAt(px, py) { const sl = this.nearest(px, py, 24); this.select(sl); if (sl) this.emit(sl.it.e); }
  select(sl) { this.sel = sl; this.u.uSel.value = sl ? sl.idx : -1; this.tipFor(this.hov || sl); }
  hoverAt(sl) {
    if (sl === this.hov) return;
    this.hov = sl; this.u.uHov.value = sl ? sl.idx : -1; this.canvas.style.cursor = sl ? 'pointer' : 'grab';
    this.tipFor(sl || this.sel);
  }
  tipFor(sl) {
    if (!sl) { this.showTip(null); return; }
    const it = sl.it, e = it.e, k = KIND[it.kind], dt = it.t - this.nowU, off = this.off;
    const when = dt > 60 ? 'in ' + ago(dt) : dt < -60 ? ago(dt) + ' ago' : 'now';
    const day = etDay(it.t, off) !== etDay(this.nowU, off) ? etWeekday(it.t, off) + ' ' : '';
    let html = `<b>${esc(trunc(it.title, this.w < 480 ? 30 : 44))}</b><u style="color:${k.css}">${esc(k.label)}</u><br><i>${day}${etTime(it.t, off)} ET · ${when}</i> · ${IMPACT_TXT[it.imp]} impact${it.source ? ` · <i>${esc(it.source)}</i>` : ''}`;
    const vals = [['actual', fmtVal(e.actual)], ['forecast', fmtVal(e.forecast)], ['previous', fmtVal(e.previous)]].filter((x) => x[1] != null), sp = num(e.surprise);
    if (vals.length || Number.isFinite(sp)) {
      html += '<br>' + vals.map(([l, v]) => `<i>${l}</i> <b>${esc(v)}</b>`).join(' · ');
      if (Number.isFinite(sp)) html += `${vals.length ? ' · ' : ''}<i>surprise</i> <b style="color:${sp > 0 ? '#4ef0b0' : sp < 0 ? '#ff7ad9' : '#eef0fb'}">${sp > 0 ? '+' : ''}${esc(fmtVal(sp))}</b>`;
    }
    this.showTip(sl.key, html);
  }
  devTapPoint() {
    const sl = this.nextSlot && !this.nextSlot.dead ? this.nextSlot : this.slots.find((s) => !s.dead);
    if (!sl) return null; const p = this.screen(this.posOf(sl.it, _v)); return [p.x, p.y];
  }

  // ---------------------------------------------------------------- per frame
  update(t, dt) {
    this.lt += dt; const lt = this.lt, u = this.u;
    u.uTime.value = lt;
    const moved = this.camStep(dt); u.uFocus.value = this.L;
    const sec0 = this.cdSec; this.syncNow(false);
    // the beam: one turn every PERIOD seconds; with reduced motion it rests on the current time of day
    if (Q.reduced) this.beamTurn = this.dU.uNowA.value; else this.beamTurn += dt / PERIOD;
    u.uBeam.value = fract(this.beamTurn);
    if (this.introAt >= 0) { const k = (lt - this.introAt) / 1.6; this.dU.uIn.value = clamp(k, 0, 1); if (k >= 1) { this.introAt = -1; this.camKey = ''; } }
    this.alert += (this.alertWant - this.alert) * Math.min(1, dt * 3); this.dU.uAlert.value = this.alert;
    const uin = this.dU.uIn.value, bt = u.uBeam.value * Math.PI * 2, red = Q.reduced;
    this.flare.position.set(Math.sin(bt) * R, 0.03, -Math.cos(bt) * R); this.flare.material.opacity = (0.45 + (red ? 0 : 0.2 * Math.sin(lt * 3))) * uin;
    this.hubGlow.material.color.copy(this.dU.uCol.value).lerp(this.dU.uAlertCol.value, this.alert);
    this.hubGlow.material.opacity = (0.32 + this.alert * 0.22 * (1 + (red ? 0 : Math.sin(lt * 7)))) * uin; this.hubGlow.scale.setScalar(1.25 + this.alert * 0.45);
    const nx = this.nextSlot && !this.nextSlot.dead && lt > this.nextSlot.born ? this.nextSlot : null;
    if (nx) {
      const p = this.posOf(nx.it, _v), ph = red ? 0.4 : fract(lt * 0.5);
      this.ping.visible = true; this.ping.position.set(p.x, 0.02, p.z); this.ping.scale.setScalar(0.35 + ph * 0.95); this.ping.material.opacity = (1 - ph) * 0.5;
      this.ping.material.color.set(KIND[nx.it.kind].col).lerp(_c.set('#ffffff'), 0.4);
    } else this.ping.visible = false;
    const s = this.sel;
    if (s && !s.dead) {
      const p = this.posOf(s.it, _v), pulse = red ? 1 : 1 + 0.07 * Math.sin(lt * 5);
      this.reticle.visible = true; this.reticle.position.copy(p); this.reticle.scale.setScalar((0.44 + s.it.imp * 0.06) * pulse);
      this.reticle.material.rotation = red ? 0 : lt * 0.8; this.reticle.material.opacity = 0.95;
    } else this.reticle.visible = false;
    if (this.hasDead && lt > this.busyUntil) { this.hasDead = false; this.slots = this.slots.filter((x) => !x.dead); this.writeStatic(); }
    // html
    if (this._hoverAt) { const [hx, hy] = this._hoverAt; this._hoverAt = null; this.hoverAt(this.nearest(hx, hy, 16)); }
    this.labelAcc += dt;
    if (moved || lt < this.busyUntil || this.introAt >= 0 || this.labelAcc > 0.5) { this.labelAcc = 0; this.placeLabels(); }
    const ts = this.hov || this.sel;
    if (ts && !ts.dead) {
      if (this.cdSec !== sec0 && this.tipKey != null) { this.tipKey = null; this.tipFor(ts); }
      const p = this.screen(this.posOf(ts.it, _v)); this.placeTip(p.x, p.y, 16);
    }
  }
}
