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
// Draw calls ~12 whatever the event count; particles: 1 blip + 1 shadow + 1 ring + 1 drop line per event + 800 dust (300 lite).
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
  c += hc * (hub * (0.07 + 0.12 * exp(-r * r * 20.0)) + hubEdge * 0.55) * beat * (0.4 + 0.6 * uAlert + 0.6 * (1.0 - uAlert));
  float sp = abs(fract(a * 24.0 + 0.5) - 0.5) / 24.0 * 6.2831853 * rw, sp4 = abs(fract(a * 4.0 + 0.5) - 0.5) / 4.0 * 6.2831853 * rw;
  float spoke = exp(-sp * sp * 2600.0) * 0.07 + exp(-sp4 * sp4 * 1800.0) * 0.15;
  c += uCol * spoke * outer * disc * reveal;
  float kz = 0.0;
  for (int i = 0; i < 4; i++) { if (i >= uKzN) break; kz = max(kz, arc(a, uKz[i], r)); }
  c += uKzCol * kz * (disc * outer * 0.035 + band(r, 1.0, 1.045) * 0.95) * reveal;
  c += uSesCol * uHasSes * arc(a, uSes, r) * band(r, 1.062, 1.082) * 0.6 * reveal;
  float tk = exp(-sp * sp * 3200.0) * band(r, 1.055, 1.09) * 0.35 + exp(-sp4 * sp4 * 2600.0) * band(r, 1.05, 1.115) * 0.7;
  c += uCol * tk * reveal;
  float ph = fract(uBeam - a + 1.0), head = exp(-pow(ph * 6.2831853 * rw / 0.03, 2.0)), trail = exp(-ph * 9.0) * smoothstep(0.0, 0.02, ph);
  float beamMask = disc * smoothstep(uHub * 0.3, uHub, r);
  c += uBeamCol * beamMask * (trail * 0.2 + head * 0.9) * reveal;
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
.fxn-cd{position:absolute;left:10px;bottom:9px;text-align:left;line-height:1;white-space:nowrap;max-width:calc(100% - 20px);overflow:hidden}
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
