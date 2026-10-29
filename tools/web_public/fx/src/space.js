// Deep space: the default background of both dashboards (owner 2026-10-29: "make it look cooler ... almost like 3D space").
// Inspired by a photo of the Moon's shadow on Earth during a solar eclipse; everything is procedural (no image files):
//  - Earth: continents, oceans, ice and city lights baked once from noise into two textures (GPU, at load), then per frame
//    only texture reads + lighting: day / night, ocean glint, twilight band, drifting clouds, the night side's city lights
//  - the eclipse: the Moon crosses the Sun (a real 3D sphere in front of the corona), its soft round shadow (dark umbra,
//    wide penumbra) slides across the lit side of the Earth; city lights come on inside the shadow
//  - a thin glowing atmosphere rim (analytic, per pixel) whose aurora tint follows today's P&L (green up, red down)
//  - the Sun: corona with streamers, glare and lens ghosts that dim when the Moon covers it
//  - stars in three depth layers (parallax), a baked Milky Way band with dust lanes, faint nebulae, a few spiked stars
//  - three satellites orbit the Earth, one per bot (Zlarior blue, ATLAS orange, BLITZ purple): dim when off, breathing
//    when waiting, pulsing with a ring when armed, bright with a beam to the ground while in a trade; a small HTML tag
//    rides next to each one ("Zlarior · IN TRADE"), hidden behind the planet (labels(); off in Lite)
//  - a shooting star when a trade closes (green win / red loss), star streaks on a page change (warp), a slow
//    cinematic camera drift, parallax from the pointer, the scroll position and (opt-in) the phone's tilt
// Cost: one canvas, ~10 draw calls; phones render at most 30 fps (the scene moves slowly), every device 30 fps after
// 20 s without input (core.js), nothing while the tab is hidden; prefers-reduced-motion = one still frame, redrawn only
// when the data changes. The same API as the old Field (setScene, setMood, warp, pulse, sweep, ripple, retheme) plus
// bots(), shoot(), pnl(); the card auras (aura.js) draw on top as before.
import { THREE, View, Q, theme, par, glowTexture, POINT_FRAG, rng, count, wake } from './core.js';
import { Aura } from './aura.js';

// ------------------------------------------------------------------ GLSL: 3D simplex noise (Ashima / Gustavson, MIT) + fbm
const NOISE = `
vec3 mod289(vec3 x){ return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x){ return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x){ return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r){ return 1.79284291400159 - 0.85373472095314 * r; }
float snoise(vec3 v){
  const vec2 C = vec2(1.0/6.0, 1.0/3.0); const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy)); vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz); vec3 l = 1.0 - g; vec3 i1 = min(g.xyz, l.zxy); vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx; vec3 x2 = x0 - i2 + C.yyy; vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857; vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z); vec4 x_ = floor(j * ns.z); vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy; vec4 y = y_ * ns.x + ns.yyyy; vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy); vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0; vec4 s1 = floor(b1) * 2.0 + 1.0; vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy; vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x); vec3 p1 = vec3(a0.zw, h.y); vec3 p2 = vec3(a1.xy, h.z); vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0); m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}
float fbm(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 6; i++) { s += a * snoise(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.5; } return s; }
float fbm3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 3; i++) { s += a * snoise(p); p = p * 2.07 + vec3(4.1, 1.3, 7.7); a *= 0.5; } return s; }
// the unit direction of an equirect texel, matching THREE.SphereGeometry's uv layout
vec3 dirOf(vec2 uv){ float ph = uv.x * 6.2831853; float th = (1.0 - uv.y) * 3.1415926; return vec3(-cos(ph) * sin(th), cos(th), sin(ph) * sin(th)); }
`;
const BAKE_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
// pass 0: albedo (rgb) + city lights (a); pass 1: clouds (r) + ocean mask (g); pass 2: the Milky Way sky; pass 3: the Moon
const BAKE_F = `precision highp float; varying vec2 vUv; uniform int uPass; uniform vec3 uGalN; uniform vec3 uGalC;
${NOISE}
float landH(vec3 p){ vec3 q = p * 0.95 + vec3(3.7, 1.1, 8.3); float w = fbm3(q * 1.1); return fbm(q * 1.3 + vec3(w * 0.7, w * 0.35, -w * 0.55)) + 0.11 * fbm3(p * 6.5); }
void main(){
  vec3 p = dirOf(vUv);
  if (uPass == 0 || uPass == 1) {
    float h = landH(p), sea = 0.075, lat = abs(p.y);
    float land = smoothstep(sea, sea + 0.012, h);
    if (uPass == 1) {
      float sw = fbm3(p * vec3(1.3, 2.2, 1.3) + vec3(11.0));
      float cl = fbm(p * vec3(2.0, 3.8, 2.0) + vec3(sw * 1.1, sw * 0.3, -sw * 0.8));
      float belt = 0.20 * exp(-pow((lat - 0.05) / 0.09, 2.0)) + 0.16 * exp(-pow((lat - 0.78) / 0.16, 2.0)) - 0.14 * exp(-pow((lat - 0.42) / 0.12, 2.0));
      float wisp = fbm3(p * vec3(9.0, 16.0, 9.0) + vec3(cl * 2.0));
      cl = smoothstep(-0.02, 0.5, cl + belt + 0.16 * wisp) * (0.75 + 0.25 * smoothstep(-0.4, 0.4, wisp));
      gl_FragColor = vec4(cl, 1.0 - smoothstep(sea - 0.01, sea + 0.035, h), 0.0, 1.0); return;
    }
    float shelf = smoothstep(sea - 0.13, sea, h) * (1.0 - land);
    vec3 ocean = mix(vec3(0.010, 0.05, 0.14), vec3(0.03, 0.21, 0.36), shelf * 0.85 + 0.06 * fbm3(p * 9.0));
    float hh = clamp((h - sea) * 2.6, 0.0, 1.0);
    float dry = smoothstep(0.05, 0.45, fbm3(p * 2.1 + vec3(7.0)) + 0.32 * exp(-pow((lat - 0.33) / 0.11, 2.0)) - 0.25 * exp(-pow(lat / 0.12, 2.0)));
    vec3 lc = mix(vec3(0.035, 0.10, 0.035), vec3(0.11, 0.14, 0.05), smoothstep(-0.3, 0.4, fbm3(p * 5.0)));
    lc = mix(lc, vec3(0.40, 0.30, 0.17), dry);
    lc = mix(lc, vec3(0.24, 0.22, 0.20), smoothstep(0.4, 0.85, hh));
    float ice = smoothstep(0.935, 0.965, lat + 0.03 * fbm3(p * 6.0)) + land * smoothstep(0.86, 0.92, lat + 0.04 * fbm3(p * 9.0)) * 0.8;
    vec3 col = mix(ocean, lc, land);
    col = mix(col, vec3(0.82, 0.88, 0.94), clamp(ice, 0.0, 1.0));
    // city lights: on land, clustered, more along the coasts, none on ice or deep desert
    float coast = 1.0 - smoothstep(0.0, 0.12, h - sea);
    float cl1 = smoothstep(0.12, 0.62, fbm3(p * 11.0 + vec3(5.0)) + coast * 0.25);
    float cl2 = smoothstep(0.25, 0.95, snoise(p * 70.0) * 0.5 + 0.5);
    float cities = land * (1.0 - clamp(ice * 1.6, 0.0, 1.0)) * (1.0 - dry * 0.8) * cl1 * (0.35 + 0.65 * cl2) * smoothstep(0.78, 0.4, lat);
    gl_FragColor = vec4(col, clamp(cities * 1.4, 0.0, 1.0)); return;
  }
  if (uPass == 2) {
    float b = dot(p, uGalN), l = dot(p, uGalC);
    float n1 = fbm(p * 3.1), n2 = fbm3(p * 7.3 + vec3(5.0)), n3 = fbm3(p * 15.0 + vec3(2.0));
    float band = exp(-b * b * 34.0);
    float bulge = exp(-b * b * 24.0) * pow(max(l, 0.0), 10.0);
    float lane = smoothstep(-0.05, 0.45, fbm(p * vec3(6.0, 9.0, 6.0) + vec3(2.0))) * exp(-pow(b + 0.012, 2.0) * 240.0);
    float mw = band * (0.45 + 0.55 * (n1 * 0.5 + 0.5)) * (0.65 + 0.35 * (n2 * 0.5 + 0.5)) * (1.0 - lane * 0.8);
    vec3 col = mix(vec3(0.34, 0.40, 0.62), vec3(0.92, 0.84, 0.72), clamp(bulge * 1.4 + 0.12 * n2, 0.0, 1.0)) * mw * 0.55;
    col += vec3(0.98, 0.88, 0.75) * bulge * (1.0 - lane * 0.75) * 0.2;
    col += vec3(0.9, 0.93, 1.0) * pow(snoise(p * 260.0) * 0.5 + 0.5, 26.0) * (0.25 + band * 1.6);
    col += vec3(0.75, 0.8, 1.0) * pow(max(n3, 0.0), 3.0) * band * 0.25;
    // faint nebulae: violet / teal clouds away from the band
    float nb = smoothstep(0.28, 0.85, fbm(p * 1.7 + vec3(20.0)));
    vec3 nc = mix(vec3(0.34, 0.06, 0.32), vec3(0.04, 0.20, 0.34), smoothstep(-0.25, 0.25, fbm3(p * 2.6 + vec3(40.0))));
    col += nc * nb * (0.15 + 0.10 * n2);
    col += vec3(0.006, 0.008, 0.016);
    gl_FragColor = vec4(col, 1.0); return;
  }
  // pass 3: the Moon (grey maria, craters)
  float m = fbm(p * 2.2 + vec3(9.0));
  float cr = 0.0;
  for (int i = 0; i < 3; i++) { float s = 6.0 + float(i) * 9.0; float c = snoise(p * s + vec3(float(i) * 3.3)); cr += smoothstep(0.55, 0.9, c) * (0.3 - float(i) * 0.07); }
  float g = 0.55 + 0.18 * fbm3(p * 12.0) - 0.22 * smoothstep(-0.1, 0.35, m) + cr;
  gl_FragColor = vec4(vec3(g) * vec3(1.0, 0.98, 0.95), 1.0);
}`;

// ------------------------------------------------------------------ per-frame materials
const EARTH_V = `varying vec2 vUv; varying vec3 vN; varying vec3 vW;
void main(){ vUv = uv; vN = normalize(mat3(modelMatrix) * normal); vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const EARTH_F = `uniform sampler2D tA; uniform sampler2D tC; uniform vec3 uSun; uniform vec3 uCam; uniform vec3 uShC; uniform float uShR; uniform float uShU;
uniform float uCloud; uniform float uTime; uniform vec3 uAur; uniform float uAurK; uniform vec3 uAxis; uniform vec3 uE1; uniform vec3 uE2; uniform float uBright; uniform float uPing; uniform float uShK;
varying vec2 vUv; varying vec3 vN; varying vec3 vW;
void main(){
  vec3 n = normalize(vN), v = normalize(uCam - vW);
  vec4 A = texture2D(tA, vUv);
  float cl = texture2D(tC, vec2(vUv.x + uCloud, vUv.y)).r, ocean = texture2D(tC, vUv).g;
  float cs = texture2D(tC, vec2(vUv.x + uCloud + 0.006, vUv.y + 0.003)).r;      // the clouds' shadows on the ground
  float ndl = dot(n, uSun);
  float day = smoothstep(-0.10, 0.28, ndl);
  // the Moon's shadow: angular distance from its centre on the sphere -> umbra (dark core) .. penumbra (soft edge)
  float sd = acos(clamp(dot(n, uShC), -1.0, 1.0));
  float pen = smoothstep(uShU, uShR, sd);
  float shade = mix(1.0, mix(0.03, 1.0, pow(pen, 1.6)), uShK);
  float lit = day * shade * uBright;
  vec3 penC = mix(vec3(0.55, 0.36, 0.22), vec3(1.0), smoothstep(0.35, 1.0, pen));
  float dif = max(ndl, 0.0) * 0.85 + 0.15;
  vec3 col = A.rgb * (0.025 + 1.35 * lit * dif * (1.0 - cs * 0.38)) * mix(vec3(1.0), penC, uShK);
  col += vec3(0.035, 0.085, 0.17) * lit * dif * (1.0 - cl * 0.5);        // the day side's blue haze (the shadow takes it away)
  col = mix(col, vec3(0.93, 0.95, 1.0) * mix(vec3(1.0), penC, uShK) * (0.018 + 1.12 * lit * dif), cl * 0.82);
  vec3 h = normalize(uSun + v);
  col += vec3(1.0, 0.9, 0.72) * pow(max(dot(n, h), 0.0), 70.0) * ocean * (1.0 - cl) * lit * 1.1;
  float tw = exp(-pow((ndl - 0.03) / 0.07, 2.0)) * smoothstep(-0.1, 0.06, ndl);
  col += vec3(0.55, 0.22, 0.07) * tw * 0.08 * (1.0 - cl * 0.4) * shade;
  // city lights: the night side, and inside the eclipse shadow (street lights switch on)
  float night = 1.0 - smoothstep(-0.18, 0.06, ndl);
  float dark = max(night, (1.0 - pen) * day * 0.85 * uShK);
  col += vec3(1.0, 0.70, 0.36) * A.a * A.a * dark * (1.0 - cl * 0.8) * 1.9;
  // lightning: rare, brief flashes inside the night side's thick clouds
  vec2 cell = floor(vec2(vUv.x + uCloud, vUv.y) * vec2(110.0, 55.0));
  float hs = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);
  float bolt = step(0.985, hs) * step(fract(uTime * (0.21 + hs * 0.3) + hs * 17.0), 0.012) * smoothstep(0.55, 0.85, cl) * night;
  col += vec3(0.75, 0.82, 1.0) * bolt * 0.9;
  // aurora oval on the night side, coloured by today's P&L
  float sl = abs(dot(n, uAxis));
  float lon = atan(dot(n, uE1), dot(n, uE2));
  float band = exp(-pow((sl - 0.91) / (0.028 + 0.012 * sin(lon * 3.0 + uTime * 0.2)), 2.0));
  float curtain = 0.45 + 0.55 * sin(lon * 17.0 + uTime * 0.9 + sin(lon * 5.0 - uTime * 0.4) * 2.0);
  col += uAur * band * curtain * uAurK * (0.25 + night) * 0.9;
  // atmospheric haze toward the limb
  float fr = pow(1.0 - max(dot(n, v), 0.0), 2.6);
  vec3 sky = mix(vec3(0.16, 0.42, 1.0), uAur, uAurK * 0.3);
  col += sky * fr * (0.05 + 0.85 * smoothstep(-0.3, 0.5, ndl) * mix(0.3, 1.0, pen)) * (1.0 + uPing * 0.8);
  gl_FragColor = vec4(col, 1.0);
}`;
const ATMO_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const ATMO_F = `uniform vec3 uCam; uniform vec3 uC; uniform vec3 uSun; uniform vec3 uTint; uniform float uTintK; uniform float uR; uniform float uPing; uniform float uBright;
varying vec3 vW;
void main(){
  vec3 d = normalize(vW - uCam), oc = uCam - uC;
  float t = -dot(oc, d);
  vec3 pp = oc + d * t;
  float r = length(pp), hgt = (r - uR) / uR;
  vec3 pn = pp / max(r, 1e-4);
  float sl = dot(pn, uSun);
  float g = hgt > 0.0 ? exp(-hgt * 34.0) : exp(hgt * 10.0) * 0.5;
  float lit = smoothstep(-0.45, 0.55, sl);
  float fwd = pow(max(dot(d, uSun), 0.0), 5.0);
  vec3 blue = mix(vec3(0.26, 0.56, 1.0), uTint, uTintK);
  vec3 col = blue * g * (0.16 + 1.25 * lit + 1.6 * fwd) * uBright * (1.0 + uPing);
  col += vec3(1.0, 0.5, 0.22) * g * exp(-pow((sl + 0.04) / 0.16, 2.0)) * 0.45;
  col += uTint * uTintK * exp(-pow(hgt - 0.03, 2.0) * 900.0) * (1.0 - lit) * 0.35;
  gl_FragColor = vec4(col, 1.0);
}`;
const MOON_F = `uniform sampler2D tM; uniform vec3 uSun; uniform vec3 uEarth;
varying vec2 vUv; varying vec3 vN; varying vec3 vW;
void main(){ vec3 n = normalize(vN); float a = texture2D(tM, vUv).r;
  float sun = max(dot(n, uSun), 0.0); float es = max(dot(n, normalize(uEarth - vW)), 0.0);
  gl_FragColor = vec4(vec3(a) * (sun * 1.1 + es * 0.07) + vec3(0.010, 0.014, 0.024) * es, 1.0); }`;
const SKY_F = `uniform sampler2D tS; uniform float uBright; uniform vec3 uTint; uniform float uTintK; varying vec2 vUv;
void main(){ vec3 c = texture2D(tS, vUv).rgb; c = mix(c, uTint * dot(c, vec3(0.6)), uTintK); gl_FragColor = vec4(c * uBright, 1.0); }`;
const SKY_V = `varying vec2 vUv; void main(){ vUv = uv; vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = p.xyww; }`;
// stars: three depth layers; twinkle + warp streaks share the positions
const STAR_V = `attribute float aS; attribute float aSeed; attribute vec3 aCol;
uniform float uTime; uniform float uPix; uniform float uBright; uniform float uTw;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float tw = 1.0 - uTw * (0.5 + 0.5 * sin(uTime * (1.3 + aSeed * 3.1) + aSeed * 60.0)) * step(0.35, aSeed);
  gl_PointSize = clamp(aS * uPix * (0.75 + 0.25 * tw), 1.0, 9.0);
  gl_Position = projectionMatrix * mv; vColor = aCol * uBright * (0.55 + 0.45 * tw); vAlpha = 1.0; }`;
const WARP_V = `attribute float aEnd; attribute vec3 aCol; uniform vec3 uCam; uniform vec3 uFwd; uniform float uWarp; varying vec3 vC;
void main(){ vec3 w = (modelMatrix * vec4(position, 1.0)).xyz; float z = dot(w - uCam, uFwd);
  vec3 p = w - uFwd * aEnd * uWarp * max(z, 0.0) * 0.55; vC = aCol * uWarp * (1.0 - aEnd * 0.9) * step(0.0, z);
  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0); }`;
const WARP_F = `varying vec3 vC; void main(){ gl_FragColor = vec4(vC, 1.0); }`;
// the Sun: photosphere, corona streamers and a warm halo (a camera-facing quad)
const SUN_V = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const SUN_F = `uniform float uTime; uniform float uVis; varying vec2 vUv;
void main(){ vec2 p = vUv * 2.0 - 1.0; float r = length(p), a = atan(p.y, p.x);
  float disc = smoothstep(0.112, 0.098, r);
  float ring = exp(-max(r - 0.1, 0.0) * 13.0) * step(0.096, r);
  float st = pow(0.5 + 0.5 * sin(a * 7.0 + 1.3 * sin(a * 3.0 + uTime * 0.05)), 4.0) * 0.8 + pow(0.5 + 0.5 * sin(a * 23.0 - uTime * 0.03), 8.0) * 0.4;
  float streamers = st * exp(-max(r - 0.1, 0.0) * 3.6) * smoothstep(0.09, 0.14, r);
  float halo = exp(-r * 4.2) * 0.55;
  vec3 c = vec3(1.0, 0.97, 0.92) * disc * 3.5 + vec3(0.95, 0.93, 1.0) * (ring * 1.15 + streamers * 0.55) + vec3(1.0, 0.78, 0.52) * halo * (0.35 + 0.65 * uVis);
  gl_FragColor = vec4(c * smoothstep(1.0, 0.7, r), 1.0); }`;
// satellites: the trail is a stream of points along the orbit behind the satellite (all on the GPU)
const TRAIL_V = `attribute float aK; uniform float uA; uniform float uLen; uniform vec3 uU; uniform vec3 uV; uniform vec3 uC; uniform float uRad; uniform float uPix; uniform vec3 uCol; uniform float uOn;
varying vec3 vColor; varying float vAlpha;
void main(){ float a = uA - aK * uLen; vec3 p = uC + (uU * cos(a) + uV * sin(a)) * uRad; vec4 mv = viewMatrix * vec4(p, 1.0);
  float k = 1.0 - aK; gl_PointSize = clamp((1.6 + 3.6 * k * k) * uPix / -mv.z, 0.0, 16.0); gl_Position = projectionMatrix * mv;
  vColor = mix(uCol, vec3(1.0), k * k * 0.5) * (0.35 + 0.8 * uOn); vAlpha = k * k * (0.25 + 0.75 * uOn); }`;
const ORBIT_V = `attribute float aA; uniform float uA; uniform vec3 uU; uniform vec3 uV; uniform vec3 uC; uniform float uRad; uniform vec3 uCol; uniform float uOn; varying vec3 vC;
void main(){ vec3 p = uC + (uU * cos(aA) + uV * sin(aA)) * uRad; float da = mod(uA - aA, 6.2831853);
  vC = uCol * (0.05 + 0.10 * uOn + 0.35 * exp(-da * 1.4) * (0.4 + uOn)); gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0); }`;
const LINE_F = `varying vec3 vC; void main(){ gl_FragColor = vec4(vC, 1.0); }`;
const METEOR_V = `attribute float aI; uniform float uPix; uniform vec3 uCol; uniform float uOn; varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); float k = 1.0 - aI;
  gl_PointSize = clamp((2.5 + 16.0 * k * k) * uPix / -mv.z, 1.0, 26.0); gl_Position = projectionMatrix * mv;
  vColor = mix(uCol, vec3(1.0), k * k * k) * 1.5; vAlpha = k * uOn; }`;

// ------------------------------------------------------------------ helpers
// key, colour, orbit radius (Earth radii), turn in the screen plane (rad), openness (0 = seen edge-on), angular speed (rad / s),
// start angle. Each orbit's long axis points from the Earth toward the open sky of the layout (layout()), so a satellite
// spends half its orbit in view and passes behind the planet on the far side.
const BOTS = [
  { key: 'lit', color: '#4f9bff', r: 1.27, turn: -0.32, open: 0.48, w: 0.10, ph: 0.25 },
  { key: 'atlas', color: '#ff9a3d', r: 1.44, turn: 0.10, open: 0.66, w: 0.078, ph: -0.95 },
  { key: 'scalp', color: '#b388ff', r: 1.62, turn: 0.46, open: 0.86, w: 0.062, ph: 1.15 },
];
const TF = Math.tan(THREE.MathUtils.degToRad(45 / 2));   // the camera's resting field of view (45 degrees)
const STATE_ON = { off: 0.0, idle: 0.35, armed: 0.7, trade: 1.0 };
const NAMES = { lit: 'Zlarior', atlas: 'ATLAS', scalp: 'BLITZ' };
const TAGS = { trade: 'IN TRADE', armed: 'ARMED', idle: 'watching', off: 'off' };
// per-page shots: Earth's face (spin offset), sky turn, light warmth; blended over ~2 s with the warp
const SHOTS = { today: [0, 0], chart: [1.2, 0.35], trades: [2.3, -0.4], results: [3.1, 0.6], lab: [4.0, -0.25], losses: [4.8, 0.5], eval: [5.5, -0.6], engine: [0.7, 0.8], settings: [1.8, -0.8] };
function ringTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 40, 64, 64, 63);
  gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.72, 'rgba(255,255,255,0.9)'); gr.addColorStop(0.86, 'rgba(255,255,255,0.25)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function spikeTexture() {      // a bright star with four diffraction spikes
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'); g.translate(64, 64);
  const gr = g.createRadialGradient(0, 0, 0, 0, 0, 9); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.3, 'rgba(255,255,255,0.45)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.beginPath(); g.arc(0, 0, 9, 0, Math.PI * 2); g.fill();
  for (const [w, l, a] of [[1.6, 62, 0.85], [1.0, 40, 0.35]]) {
    for (let i = 0; i < (a > 0.5 ? 2 : 2); i++) {
      g.save(); g.rotate(i * Math.PI / 2 + (a > 0.5 ? 0 : Math.PI / 4));
      const lg = g.createLinearGradient(-l, 0, l, 0); lg.addColorStop(0, 'rgba(255,255,255,0)'); lg.addColorStop(0.5, `rgba(255,255,255,${a})`); lg.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = lg; g.fillRect(-l, -w / 2, l * 2, w); g.restore();
    }
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const additive = (o = {}) => ({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, ...o });
const sprite = (map, color, opacity = 1, depthTest = true) => new THREE.Sprite(new THREE.SpriteMaterial({ map, color: new THREE.Color(color), opacity, depthTest, ...additive() }));
// overlap area of two circles (radii a, b, centre distance d) -> how much of the Sun the Moon hides
function lens(a, b, d) {
  if (d >= a + b) return 0;
  if (d <= Math.abs(a - b)) return Math.PI * Math.min(a, b) ** 2;
  const x = (d * d + a * a - b * b) / (2 * d), y = Math.sqrt(Math.max(0, a * a - x * x));
  return a * a * Math.acos(Math.min(1, x / a)) + b * b * Math.acos(Math.min(1, (d - x) / b)) - d * y;
}
const _v = new THREE.Vector3(), _w = new THREE.Vector3(), _p = new THREE.Vector3(), _m = new THREE.Vector3(), _s = new THREE.Vector3(), _q = new THREE.Quaternion(), _ray = new THREE.Ray(), _sph = new THREE.Sphere();

export class Space extends View {
  constructor() {
    super({ alpha: false, antialias: false, dprMax: Q.phone ? 1.5 : 2, fov: 45 });
    this.canvas.classList.add('fx-field', 'fx-space');
    const S = this.scene, R = rng(23), lite = Q.level === 'lite';
    this.soft = /swiftshader|llvmpipe|software/i.test(this.gpuName()) && !Q.fixed;   // software GPU (CI, VMs): smaller bakes
    this.stats = { frames: 0, ms: 0, last: 0, bakeMs: 0, fps: 0, skipped: 0 };
    this.dirty = true; this.lastDraw = -1;
    this.u = { uTime: { value: 0 }, uPix: { value: 300 } };
    this.mood = { aurK: 0.15, aurKT: 0.15, aur: new THREE.Color('#38d6ff'), aurT: new THREE.Color('#38d6ff'), bright: 1, brightT: 1, speed: 1 };
    this.warpV = 0; this.pingV = 0; this.t0 = 0; this.flashV = 0; this.flashCol = new THREE.Color();
    this.shot = { spin: 0, sky: 0, spinT: 0, skyT: 0 };
    this.spin = 0.9;
    this.cfg = { x: 0, y: -1, r: 0.9, sx: 0.55, sy: 0.6, shx: 0.3, shy: -0.4 };

    // ---- baked textures (once)
    const t0 = performance.now();
    const big = !Q.phone && !lite && !this.soft;
    const cap = +((location.search.match(/[?&]fxbake=(\d+)/) || [])[1] || 0);          // ?fxbake=1024: cap the bakes (screenshots in a slow software GPU)
    const eW = Math.min(cap || 4096, this.soft ? 512 : big ? 2048 : 1024), sW = Math.min(cap || 4096, this.soft ? 512 : big ? 2048 : 1024);
    this.tA = this.bake(0, eW, eW / 2, true); this.tC = this.bake(1, eW / 2, eW / 4, true);
    this.tS = this.bake(2, sW, sW / 2, true); this.tM = this.bake(3, 256, 128, true);
    this.stats.bakeMs = Math.round(performance.now() - t0);

    // ---- sky sphere (Milky Way + nebulae), drawn first, never writes depth
    this.skyU = { tS: { value: this.tS.texture }, uBright: { value: 1 }, uTint: { value: new THREE.Color('#9fb7ff') }, uTintK: { value: 0 } };
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(300, 48, 24), new THREE.ShaderMaterial({ uniforms: this.skyU, vertexShader: SKY_V, fragmentShader: SKY_F, side: THREE.BackSide, depthWrite: false }));
    this.sky.renderOrder = -10; this.sky.frustumCulled = false;
    this.skyG = new THREE.Group(); this.skyG.add(this.sky); S.add(this.skyG);

    // ---- stars: three shells for parallax; the warp streaks reuse the near ones
    const N = count(Q.phone ? 2200 : 3600, Q.phone ? 900 : 1500);
    const pos = new Float32Array(N * 3), aS = new Float32Array(N), aSeed = new Float32Array(N), aCol = new Float32Array(N * 3), tmp = new THREE.Color();
    const temps = ['#9db4ff', '#aabfff', '#cad7ff', '#f8f7ff', '#fff4ea', '#ffe4c4', '#ffc58f'];
    for (let i = 0; i < N; i++) {
      const u = R() * 2 - 1, a = R() * Math.PI * 2, q = Math.sqrt(1 - u * u), layer = R(), d = layer < 0.25 ? 40 + R() * 30 : layer < 0.6 ? 90 + R() * 40 : 170 + R() * 60;
      pos.set([q * Math.cos(a) * d, u * d, q * Math.sin(a) * d], i * 3);
      const m = Math.pow(R(), 5.5);                       // most stars faint, a few bright
      aS[i] = 0.9 + m * 3.8; aSeed[i] = R();
      tmp.set(temps[Math.min(temps.length - 1, Math.floor(R() * temps.length))]).multiplyScalar(0.35 + m * 1.1 + R() * 0.25);
      aCol.set([tmp.r, tmp.g, tmp.b], i * 3);
    }
    const sg = new THREE.BufferGeometry();
    sg.setAttribute('position', new THREE.BufferAttribute(pos, 3)); sg.setAttribute('aS', new THREE.BufferAttribute(aS, 1));
    sg.setAttribute('aSeed', new THREE.BufferAttribute(aSeed, 1)); sg.setAttribute('aCol', new THREE.BufferAttribute(aCol, 3));
    this.starU = { uTime: this.u.uTime, uPix: { value: 1 }, uBright: { value: 1 }, uTw: { value: Q.reduced ? 0 : 0.5 } };
    this.stars = new THREE.Points(sg, new THREE.ShaderMaterial({ uniforms: this.starU, vertexShader: STAR_V, fragmentShader: POINT_FRAG, ...additive() }));
    this.stars.frustumCulled = false; this.skyG.add(this.stars);
    const W = Math.min(N, count(900, 360)), wp = new Float32Array(W * 6), we = new Float32Array(W * 2), wc = new Float32Array(W * 6);
    for (let i = 0; i < W; i++) {
      const j = i * 3, d = 0.25 + R() * 0.75;
      for (const e of [0, 1]) { wp.set([pos[j], pos[j + 1], pos[j + 2]], (i * 2 + e) * 3); we[i * 2 + e] = e; wc.set([0.7 * d, 0.85 * d, 1.25 * d], (i * 2 + e) * 3); }
    }
    const wg = new THREE.BufferGeometry();
    wg.setAttribute('position', new THREE.BufferAttribute(wp, 3)); wg.setAttribute('aEnd', new THREE.BufferAttribute(we, 1)); wg.setAttribute('aCol', new THREE.BufferAttribute(wc, 3));
    this.warpU = { uCam: { value: new THREE.Vector3() }, uFwd: { value: new THREE.Vector3(0, 0, -1) }, uWarp: { value: 0 } };
    this.warpL = new THREE.LineSegments(wg, new THREE.ShaderMaterial({ uniforms: this.warpU, vertexShader: WARP_V, fragmentShader: WARP_F, ...additive() }));
    this.warpL.frustumCulled = false; this.warpL.visible = false; this.skyG.add(this.warpL);
    // a few hero stars with diffraction spikes
    const spk = spikeTexture();
    this.spikes = [];
    for (let i = 0; i < count(14, 6); i++) {
      const sp = sprite(spk, temps[Math.floor(R() * temps.length)], 0.8);
      const u = R() * 1.4 - 0.4, a = R() * Math.PI * 2, q = Math.sqrt(1 - u * u);
      sp.position.set(q * Math.cos(a) * 150, u * 150, q * Math.sin(a) * 150); const s = 2.6 + R() * 3.4; sp.scale.set(s, s, 1);
      sp.userData = { s, seed: R() * 10 }; this.skyG.add(sp); this.spikes.push(sp);
    }

    // ---- Earth: surface, clouds and lights in one shader; tilted 23.4 degrees, turning slowly
    const segW = lite || Q.phone ? 96 : 128, segH = lite || Q.phone ? 64 : 96;
    this.earthU = { tA: { value: this.tA.texture }, tC: { value: this.tC.texture }, uSun: { value: new THREE.Vector3(1, 0.4, 0).normalize() }, uCam: { value: this.camera.position },
      uShC: { value: new THREE.Vector3(0, 0, 1) }, uShR: { value: 0.62 }, uShU: { value: 0.12 }, uCloud: { value: 0 }, uTime: this.u.uTime,
      uAur: { value: this.mood.aur }, uAurK: { value: 0.15 }, uAxis: { value: new THREE.Vector3(0, 1, 0) }, uE1: { value: new THREE.Vector3(1, 0, 0) }, uE2: { value: new THREE.Vector3(0, 0, 1) },
      uBright: { value: 1 }, uPing: { value: 0 }, uShK: { value: 1 } };
    this.earthG = new THREE.Group(); S.add(this.earthG);
    this.tilt = new THREE.Group(); this.tilt.rotation.z = 0.41; this.earthG.add(this.tilt);
    this.earth = new THREE.Mesh(new THREE.SphereGeometry(1, segW, segH), new THREE.ShaderMaterial({ uniforms: this.earthU, vertexShader: EARTH_V, fragmentShader: EARTH_F }));
    this.tilt.add(this.earth);
    this.atmoU = { uCam: { value: this.camera.position }, uC: { value: new THREE.Vector3() }, uSun: this.earthU.uSun, uTint: { value: this.mood.aur }, uTintK: { value: 0.1 }, uR: { value: 1 },
      uPing: { value: 0 }, uBright: { value: 1 } };
    this.atmo = new THREE.Mesh(new THREE.SphereGeometry(1.14, 72, 48), new THREE.ShaderMaterial({ uniforms: this.atmoU, vertexShader: ATMO_V, fragmentShader: ATMO_F, ...additive() }));
    this.earthG.add(this.atmo);

    // ---- the Sun (corona quad + glare + streak) and the Moon in front of it
    this.sunU = { uTime: this.u.uTime, uVis: { value: 1 } };
    this.sun = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.ShaderMaterial({ uniforms: this.sunU, vertexShader: SUN_V, fragmentShader: SUN_F, ...additive() }));
    this.sun.renderOrder = 2; S.add(this.sun);
    this.glare = sprite(glowTexture(), '#ffe2b8', 0.6, true); this.glare.renderOrder = 20; S.add(this.glare);   // depth-tested: the Moon's disc stays black
    this.streak = sprite(glowTexture(), '#9cc4ff', 0.35, false); this.streak.renderOrder = 21; S.add(this.streak);
    this.moonU = { tM: { value: this.tM.texture }, uSun: { value: new THREE.Vector3() }, uEarth: { value: new THREE.Vector3() } };
    this.moon = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 24), new THREE.ShaderMaterial({ uniforms: this.moonU, vertexShader: EARTH_V, fragmentShader: MOON_F }));
    S.add(this.moon);
    // lens ghosts (screen space, drawn in a second pass)
    this.ov = new THREE.Scene(); this.ovCam = new THREE.OrthographicCamera(-1, 1, 1, -1, -1, 1);
    this.ghosts = [];
    if (!lite) {
      for (const [k, s, c, o] of [[0.45, 0.07, '#7fb6ff', 0.16], [0.75, 0.035, '#ffd27f', 0.22], [1.15, 0.12, '#8cf0c8', 0.08], [1.45, 0.05, '#c3a0ff', 0.16], [1.8, 0.2, '#7fb6ff', 0.05]]) {
        const g = sprite(glowTexture(), c, o, false); g.userData = { k, s, o }; this.ov.add(g); this.ghosts.push(g);
      }
    }
    this.ripples = Array.from({ length: 3 }, () => { const r = sprite(ringTexture(), '#9fd0ff', 0, false); r.visible = false; r.userData = { age: 9 }; this.ov.add(r); return r; });

    // ---- satellites (one per bot): orbit line, GPU trail, glow, ping ring, beam to the ground when in a trade
    const ringT = ringTexture();
    this.sats = BOTS.map((b) => {
      const col = new THREE.Color(b.color), U = new THREE.Vector3(1, 0, 0), V = new THREE.Vector3(0, 0, 1);
      const su = { uA: { value: b.ph }, uLen: { value: 1.1 }, uU: { value: U }, uV: { value: V }, uC: { value: new THREE.Vector3() }, uRad: { value: b.r }, uPix: this.u.uPix, uCol: { value: col }, uOn: { value: 0.35 } };
      const OA = 160, oa = new Float32Array(OA + 1); for (let i = 0; i <= OA; i++) oa[i] = i / OA * Math.PI * 2;
      const og = new THREE.BufferGeometry(); og.setAttribute('position', new THREE.BufferAttribute(new Float32Array((OA + 1) * 3), 3)); og.setAttribute('aA', new THREE.BufferAttribute(oa, 1));
      const orbit = new THREE.Line(og, new THREE.ShaderMaterial({ uniforms: su, vertexShader: ORBIT_V, fragmentShader: LINE_F, ...additive() })); orbit.frustumCulled = false;
      const TN = count(110, 50), tk = new Float32Array(TN); for (let i = 0; i < TN; i++) tk[i] = i / (TN - 1);
      const tg = new THREE.BufferGeometry(); tg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(TN * 3), 3)); tg.setAttribute('aK', new THREE.BufferAttribute(tk, 1));
      const trail = new THREE.Points(tg, new THREE.ShaderMaterial({ uniforms: su, vertexShader: TRAIL_V, fragmentShader: POINT_FRAG, ...additive() })); trail.frustumCulled = false;
      const glow = sprite(glowTexture(), col, 0.9), core = sprite(glowTexture(), '#ffffff', 1), ping = sprite(ringT, col, 0);
      const bg = new THREE.BufferGeometry(); bg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
      const beam = new THREE.Line(bg, new THREE.LineBasicMaterial({ color: col, ...additive({ opacity: 0 }) })); beam.frustumCulled = false; beam.visible = false;
      S.add(orbit, trail, glow, core, ping, beam);
      return { ...b, col, U, V, su, orbit, trail, glow, core, ping, beam, a: b.ph, on: STATE_ON.idle, onT: STATE_ON.idle, state: 'idle', pingAge: 9, pos: new THREE.Vector3() };
    });

    // ---- shooting stars (closed trades) + the occasional quiet meteor
    const MN = 40, mi = new Float32Array(MN); for (let i = 0; i < MN; i++) mi[i] = i / (MN - 1);
    const mg = new THREE.BufferGeometry(); this.mPos = new Float32Array(MN * 3);
    mg.setAttribute('position', new THREE.BufferAttribute(this.mPos, 3)); mg.setAttribute('aI', new THREE.BufferAttribute(mi, 1));
    this.mU = { uPix: this.u.uPix, uCol: { value: new THREE.Color('#ffffff') }, uOn: { value: 0 } };
    this.meteorP = new THREE.Points(mg, new THREE.ShaderMaterial({ uniforms: this.mU, vertexShader: METEOR_V, fragmentShader: POINT_FRAG, ...additive() }));
    this.meteorP.frustumCulled = false; S.add(this.meteorP);
    this.mHead = sprite(glowTexture(), '#ffffff', 0); S.add(this.mHead);
    this.mStreak = sprite(glowTexture(), '#ffffff', 0); S.add(this.mStreak);
    this.meteor = null; this.queue = []; this.nextQuiet = 25 + R() * 20;

    this.aura = new Aura();
    this.base = new THREE.Vector3();
    this.layout(1, 1);
  }
  gpuName() {
    try { const gl = this.renderer.getContext(), x = gl.getExtension('WEBGL_debug_renderer_info'); return String(x ? gl.getParameter(x.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)); } catch { return ''; }
  }
  bake(pass, w, h, mip) {
    const rt = new THREE.WebGLRenderTarget(w, h, { depthBuffer: false, generateMipmaps: !!mip, minFilter: mip ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter, magFilter: THREE.LinearFilter,
      wrapS: THREE.RepeatWrapping, wrapT: THREE.ClampToEdgeWrapping });
    rt.texture.wrapS = THREE.RepeatWrapping;
    // the Milky Way: its bulge up-left of the view, the band running diagonally across the screen (sky group at rest)
    const gC = new THREE.Vector3(-0.5, 0.32, -1).normalize(), gN = new THREE.Vector3().crossVectors(gC, new THREE.Vector3(1, -0.62, 0.1)).normalize();
    const m = new THREE.ShaderMaterial({ uniforms: { uPass: { value: pass }, uGalN: { value: gN }, uGalC: { value: gC } }, vertexShader: BAKE_V, fragmentShader: BAKE_F, depthTest: false, depthWrite: false });
    const q = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), m), sc = new THREE.Scene(); q.frustumCulled = false; sc.add(q);
    const r = this.renderer, prev = r.getRenderTarget();
    r.setRenderTarget(rt); r.render(sc, new THREE.Camera()); r.setRenderTarget(prev);
    q.geometry.dispose(); m.dispose();
    return rt;
  }
  // ---- composition: where the Earth, the Sun and the eclipse sit on screen for this aspect ratio
  layout(w, h) {
    const a = w / h;
    // x / y / r: the Earth's centre and radius on screen (NDC); sx / sy: the Sun; shx / shy: the eclipse shadow; l: the light (right, up, toward us)
    this.cfg = a < 0.8 ? { x: 0.1, y: -1.02, r: 0.9, sx: 0.5, sy: 0.62, shx: 0.42, shy: -0.5, sun: 0.085, l: [0.95, 0.1, 0.5] }    // phone portrait: a big arc at the bottom
      : a < 1.3 ? { x: 0.3, y: -0.85, r: 0.82, sx: 0.62, sy: 0.6, shx: 0.5, shy: -0.42, sun: 0.1, l: [0.9, 0.2, 0.5] }
        : a < 1.95 ? { x: 0.5, y: -0.56, r: 0.76, sx: 0.8, sy: 0.64, shx: 0.8, shy: -0.3, sun: 0.11, l: [0.85, 0.3, 0.55] }   // PC
          : { x: 0.55, y: -0.78, r: 0.9, sx: 0.84, sy: 0.6, shx: 0.66, shy: -0.4, sun: 0.12, l: [0.9, 0.15, 0.5] };             // phone sideways
    const c = this.cfg, tf = TF;
    const D = 1 / Math.sin(Math.atan(c.r * tf));
    this.earthG.position.set(c.x * tf * a * D, c.y * tf * D, -D);
    this.earthD = D; this.aspect = a;
    // the Sun far away up in the corner, the Moon on the same line of sight (1/3 of the way), sized like the Sun's disc
    this.sunDir = new THREE.Vector3(c.sx * tf * a, c.sy * tf, -1).normalize();
    const sunDist = 140, sz = c.sun * sunDist * 2.6;
    this.sunBase = this.sunDir.clone().multiplyScalar(sunDist);
    this.sun.scale.set(sz, sz, 1);
    this.sunR = sz * 0.105 / sunDist;                        // angular radius of the photosphere (rad)
    this.moonDist = 46; this.moonR = this.sunR * 1.06 * this.moonDist;
    this.moon.scale.setScalar(this.moonR);
    // light: from the Sun's side, turned toward the camera so the lit half of the Earth faces us
    const toCam = _v.copy(this.earthG.position).negate().normalize();
    const right = new THREE.Vector3(1, 0, 0), up = new THREE.Vector3(0, 1, 0);
    this.light = new THREE.Vector3().addScaledVector(right, c.l[0]).addScaledVector(up, c.l[1]).addScaledVector(toCam, c.l[2]).addScaledVector(this.sunDir, 0.15).normalize();
    this.earthU.uSun.value.copy(this.light);
    this.atmoU.uC.value.copy(this.earthG.position);
    // satellite orbits: long axis toward the open sky (from the Earth's centre on screen toward the screen centre)
    const free = new THREE.Vector3(-c.x * a, -c.y, 0).normalize(), view = this.earthG.position.clone().normalize();
    this.sats.forEach((s) => {
      s.su.uC.value.copy(this.earthG.position);
      s.U.copy(free).applyAxisAngle(view, s.turn);
      const P = new THREE.Vector3().crossVectors(s.U, view).normalize();
      s.V.copy(view).multiplyScalar(Math.cos(s.open)).addScaledVector(P, Math.sin(s.open)).normalize();
    });
    this.dirty = true;
  }
  onResize(w, h) {
    const dpr = this.renderer.getPixelRatio();
    this.u.uPix.value = h * dpr / (2 * TF) * 0.022;
    this.starU.uPix.value = Math.max(1, dpr);
    this.layout(w, h); this.dirty = true; wake();
  }
  running() { return this.attached && !document.hidden && Q.level !== 'off' && !this.broken && (!Q.reduced || this.dirty); }

  // ------------------------------------------------------------------ API (same names as the old Field, plus bots / shoot / pnl)
  setScene(name, now = false) {
    const k = String(name || 'today').toLowerCase(), S = SHOTS[k] || SHOTS.today;
    this.shot.spinT = S[0]; this.shot.skyT = S[1];
    if (now || Q.reduced) { this.shot.spin = S[0]; this.shot.sky = S[1]; }
    this.dirty = true; wake();
    return k;
  }
  setMood({ killzone = false, cold = false, pnl = 0, live = false, inTrade = false } = {}) {
    this.mood.speed = killzone ? 1.25 : 1;
    this.mood.brightT = live || killzone ? 1.05 : 0.95;
    this.pnl(pnl, cold);
  }
  pnl(usd = 0, cold = false) {
    const m = this.mood, v = +usd || 0;
    if (v > 0) { m.aurT.set(theme.good); m.aurKT = Math.min(1.2, 0.45 + v / 1200); }
    else if (v < 0) { m.aurT.set('#ff4d6d'); m.aurKT = Math.min(1.2, 0.45 + -v / 1000); }
    else if (cold) { m.aurT.set('#b06bff'); m.aurKT = 0.3; }
    else { m.aurT.set('#38d6ff'); m.aurKT = 0.18; }
    this.dirty = true; wake();
  }
  // states: { lit: 'trade' | 'armed' | 'idle' | 'off', atlas: ..., scalp: ... }
  attach(el) {
    super.attach(el);
    if (this.labOn !== false && Q.level !== 'lite' && !this.labEl) {
      this.labEl = document.createElement('div'); this.labEl.className = 'fx-labels'; this.labEl.setAttribute('aria-hidden', 'true');
      for (const s of this.sats) {
        const d = document.createElement('div'); d.className = 'fx-lab hid'; d.style.setProperty('--c', s.color);
        d.innerHTML = `<i></i><b>${NAMES[s.key] || s.key}</b><span></span>`; s.lab = d; s.labTxt = null; this.labEl.appendChild(d);
      }
    }
    if (this.labEl && this.labEl.parentElement !== el) el.appendChild(this.labEl);
  }
  labels(on) { this.labOn = !!on; if (this.labEl) this.labEl.style.display = on ? '' : 'none'; if (on && !this.labEl && this.el) this.attach(this.el); this.dirty = true; wake(); }
  // the tag next to each satellite: projected every drawn frame, hidden behind the planet or off screen
  labelStep() {
    if (!this.labEl || this.labOn === false) return;
    const cam = this.camera, E = this.earthG.position, w = this.w, h = this.h;
    for (const s of this.sats) {
      const d = s.lab; if (!d) continue;
      const txt = s.key === 'scalp' && s.state === 'off' ? 'paper' : TAGS[s.state] || '';
      if (txt !== s.labTxt) { d.lastElementChild.textContent = txt; d.dataset.st = s.state; s.labTxt = txt; }
      _v.copy(s.pos).project(cam);
      _ray.set(cam.position, _w.copy(s.pos).sub(cam.position).normalize()); _sph.set(E, 1.0);
      const hit = _ray.intersectSphere(_sph, _p), behind = hit && hit.distanceTo(cam.position) < s.pos.distanceTo(cam.position) - 0.05;
      const x = (_v.x * 0.5 + 0.5) * w, y = (-_v.y * 0.5 + 0.5) * h, off = _v.z > 1 || x < 8 || x > w - 8 || y < 8 || y > h - 8;
      const hide = behind || off || (s.state === 'off' && s.key !== 'scalp');
      if (hide !== s.labHid) { d.classList.toggle('hid', hide); s.labHid = hide; }
      if (!hide) d.style.transform = `translate3d(${(x + 12).toFixed(1)}px, ${(y - 9).toFixed(1)}px, 0)`;
    }
  }
  bots(st = {}) {
    for (const s of this.sats) {
      const v = st[s.key] || st[s.key === 'scalp' ? 'blitz' : s.key];
      if (!v) continue;
      const k = STATE_ON[v] != null ? v : 'idle';
      if (k !== s.state && (k === 'armed' || k === 'trade')) s.pingAge = 0;
      s.state = k; s.onT = STATE_ON[k];
    }
    this.dirty = true; wake();
  }
  // a shooting star across the sky: kind 'win' (green) | 'loss' (red) | 'quiet' (white, the occasional one)
  shoot(kind = 'win') {
    if (Q.reduced) return false;
    this.queue.push(kind); if (this.queue.length > 3) this.queue.shift();
    if (kind !== 'quiet') { this.flashCol = kind === 'win' ? theme.good.clone() : new THREE.Color('#ff4d6d'); this.flashV = 1; }   // the atmosphere flashes with it
    wake(); return true;
  }
  warp() { if (!Q.reduced) this.warpV = 1; wake(); }
  pulse() { this.pingV = 1; this.dirty = true; wake(); }
  sweep() { this.shoot('quiet'); }
  ripple(cx, cy) {
    if (Q.reduced || Q.level === 'off') return false;
    const r = this.ripples.reduce((b, x) => (x.userData.age > b.userData.age ? x : b), this.ripples[0]);
    r.userData = { age: 0, x: cx / innerWidth * 2 - 1, y: -(cy / innerHeight) * 2 + 1 }; r.visible = true;
    this.pingV = Math.max(this.pingV, 0.5); wake();
    return true;
  }
  retheme() { this.dirty = true; }

  // ------------------------------------------------------------------ frame
  frame(t, dt) {
    // phones: at most ~30 fps (the scene moves slowly); the state still advances every tick
    if (Q.phone && !this.dirty && t - this.lastDraw < 1 / 31 && this.warpV <= 0 && !this.meteor) { this.stats.skipped++; return; }
    const step = this.lastDraw < 0 ? dt : Math.min(0.1, t - this.lastDraw);
    this.lastDraw = t;
    const c0 = performance.now();
    this.update(t, step);
    const r = this.renderer;
    r.render(this.scene, this.camera);
    r.autoClear = false;
    if (this.ovOn) r.render(this.ov, this.ovCam);
    if (this.aura && Q.level !== 'off' && this.aura.step(t, step, this.w, this.h, r.getPixelRatio())) r.render(this.aura.scene, this.aura.cam);
    r.autoClear = true;
    const ms = performance.now() - c0, S = this.stats;
    S.frames++; S.last = ms; if (S.frames === 3) S.ms = ms; else if (S.frames > 3) S.ms = S.ms * 0.9 + ms * 0.1;   // the first frames compile the shaders
    S.fps = S.fps ? S.fps * 0.95 + (1 / Math.max(step, 1e-3)) * 0.05 : 1 / Math.max(step, 1e-3);
    if (!this.canvas.classList.contains('on')) this.canvas.classList.add('on');
    this.dirty = false;
  }
  update(t, dt) {
    const m = this.mood, k = Math.min(1, dt * 1.2), still = Q.reduced;
    m.aurK += (m.aurKT - m.aurK) * (still ? 1 : k); m.aur.lerp(m.aurT, still ? 1 : k); m.bright += (m.brightT - m.bright) * (still ? 1 : k);
    this.warpV = Math.max(0, this.warpV - dt * 1.25); const w = this.warpV * this.warpV * (3 - 2 * this.warpV);
    this.pingV = Math.max(0, this.pingV - dt * 0.8);
    if (this.flashV > 0) { this.flashV = Math.max(0, this.flashV - dt * 0.5); this.pingV = Math.max(this.pingV, this.flashV * 0.8); }
    const sh = this.shot, ks = still ? 1 : 1 - Math.exp(-dt * 1.6);
    sh.spin += (sh.spinT - sh.spin) * ks; sh.sky += (sh.skyT - sh.sky) * ks;
    this.u.uTime.value = t;
    // camera: slow cinematic drift + pointer / tilt / scroll parallax + the warp's push
    const cam = this.camera, sc = Math.min(par.scroll || 0, 3000), drift = still ? 0 : 1;
    const dx = Math.sin(t * 0.045) * 0.10 * drift + par.x * 0.16, dy = Math.cos(t * 0.037) * 0.07 * drift - par.y * 0.11 + sc * 0.00009;
    cam.position.set(dx, dy, -w * 0.35);
    cam.rotation.set(Math.sin(t * 0.031) * 0.012 * drift - par.y * 0.01 - sc * 0.000035, Math.sin(t * 0.026) * 0.016 * drift - par.x * 0.014, Math.sin(t * 0.019) * 0.006 * drift);
    const fov = 45 + w * 10; if (Math.abs(cam.fov - fov) > 0.01) { cam.fov = fov; cam.updateProjectionMatrix(); }
    cam.updateMatrixWorld();
    // the sky turns very slowly (and to the page's shot)
    this.skyG.rotation.set(sh.sky * 0.25, t * 0.0016 * drift + sh.sky, 0);
    this.skyU.uBright.value = 0.95 + w * 0.4;
    this.starU.uBright.value = 1 + w * 0.8;
    this.warpU.uWarp.value = w; this.warpL.visible = w > 0.01; this.warpU.uCam.value.copy(cam.position); cam.getWorldDirection(this.warpU.uFwd.value);
    for (const spk of this.spikes) spk.material.opacity = 0.55 + 0.3 * Math.sin(t * 0.8 + spk.userData.seed) * drift;
    // Earth: spin, clouds, aurora, the eclipse shadow
    this.spin += dt * 0.018 * drift;
    this.earth.rotation.y = this.spin + sh.spin;
    this.earthU.uCloud.value = (t * 0.0022 * drift) % 1;
    this.earthU.uAurK.value = m.aurK; this.atmoU.uTintK.value = Math.min(0.75, m.aurK * 0.55);
    if (this.flashV > 0) { this.atmoU.uTint.value = this._fl || (this._fl = new THREE.Color()); this._fl.copy(m.aur).lerp(this.flashCol, this.flashV); this.atmoU.uTintK.value = Math.max(this.atmoU.uTintK.value, this.flashV * 0.85); }
    else if (this.atmoU.uTint.value !== m.aur) this.atmoU.uTint.value = m.aur;
    this.earthU.uBright.value = m.bright; this.atmoU.uBright.value = m.bright;
    this.earthU.uPing.value = this.pingV; this.atmoU.uPing.value = this.pingV * 0.9;
    this.tilt.updateMatrixWorld();
    const ax = this.earthU.uAxis.value.set(0, 1, 0).applyQuaternion(this.tilt.getWorldQuaternion(_q));
    this.earthU.uE1.value.set(1, 0, 0).applyQuaternion(_q); this.earthU.uE2.value.crossVectors(this.earthU.uE1.value, ax).normalize();
    // the eclipse: phase -1..1 over ~4 minutes (ping-pong); totality at 0. The Moon slides across the Sun, its shadow across the Earth
    const ph = this.hold != null ? this.hold : still ? 0.12 : Math.sin(t * 2 * Math.PI / 240 + 0.9);
    const c = this.cfg;
    this.shadowAt(c.shx + ph * 0.18, c.shy - ph * 0.05);
    // Sun and Moon follow the camera (they are "at infinity"), the Moon slightly off the Sun's line by the phase
    this.sun.position.copy(cam.position).add(this.sunBase); this.sun.quaternion.copy(cam.quaternion);
    const perp = _p.set(-this.sunDir.y, this.sunDir.x, 0).normalize();
    const off = ph * this.sunR * 0.8, mdir = _m.copy(this.sunDir).addScaledVector(perp, off).normalize();
    this.moon.position.copy(cam.position).addScaledVector(mdir, this.moonDist);
    this.moonU.uSun.value.copy(this.sunDir); this.moonU.uEarth.value.copy(this.earthG.position);
    // how much of the Sun is visible -> glare, streak and ghosts dim during totality
    const vis = 1 - lens(this.sunR, this.moonR / this.moonDist, Math.abs(off)) / (Math.PI * this.sunR * this.sunR);
    this.sunU.uVis.value = vis; this.earthU.uShK.value = 0.4 + 0.6 * (1 - vis); this.eclipse = 1 - vis;
    const sp = _s.copy(this.sun.position).project(cam), onS = sp.z < 1 && Math.abs(sp.x) < 1.4 && Math.abs(sp.y) < 1.4 ? 1 : 0;
    this.glare.position.copy(this.sun.position); const gs = this.sun.scale.x * (2.6 + 1.4 * vis); this.glare.scale.set(gs, gs, 1); this.glare.material.opacity = (0.08 + 0.55 * vis * vis) * onS;
    this.streak.position.copy(this.sun.position); this.streak.scale.set(this.sun.scale.x * 9, this.sun.scale.x * 0.22, 1); this.streak.material.opacity = (0.06 + 0.42 * vis * vis) * onS;
    this.ovOn = false;
    const a = this.aspect;
    for (const g of this.ghosts) {
      const d = g.userData; g.position.set(sp.x * (1 - d.k * 2) , sp.y * (1 - d.k * 2), 0);
      g.scale.set(d.s * 2 / a, d.s * 2, 1); g.material.opacity = d.o * vis * vis * onS; if (g.material.opacity > 0.003) this.ovOn = true;
    }
    for (const rp of this.ripples) {
      const d = rp.userData; if (d.age > 1.6) { rp.visible = false; continue; }
      d.age += dt; const s = 0.05 + d.age * 0.5; rp.position.set(d.x, d.y, 0); rp.scale.set(s / a, s, 1); rp.material.opacity = Math.max(0, 1 - d.age / 1.6) * 0.5; this.ovOn = true;
    }
    // satellites
    for (const s of this.sats) this.satStep(s, t, dt, still);
    this.labelStep();
    this.meteorStep(t, dt);
  }
  // put the shadow centre where the line of sight through screen point (nx, ny) meets the Earth (or the nearest limb point)
  shadowAt(nx, ny) {
    const cam = this.camera, E = this.earthG.position;
    _v.set(nx, ny, 0.5).unproject(cam).sub(cam.position).normalize();
    _ray.set(cam.position, _v); _sph.set(E, 1);
    const hit = _ray.intersectSphere(_sph, _w);
    const n = hit ? _w.sub(E).normalize() : _ray.closestPointToPoint(E, _w).sub(E).normalize();
    this.earthU.uShC.value.lerp(n, this.stats.frames < 2 || Q.reduced ? 1 : 0.35).normalize();
  }
  satStep(s, t, dt, still) {
    s.on += (s.onT - s.on) * Math.min(1, dt * 2.5);
    const sp = (still ? 0 : 1) * s.w * this.mood.speed * (s.state === 'trade' ? 1.35 : 1);
    s.a += dt * sp;
    const E = this.earthG.position;
    s.pos.copy(E).addScaledVector(s.U, Math.cos(s.a) * s.r).addScaledVector(s.V, Math.sin(s.a) * s.r);
    s.su.uA.value = s.a; s.su.uOn.value = s.on; s.su.uLen.value = 0.7 + s.on * 0.9;
    const beat = s.state === 'trade' ? 0.5 + 0.5 * Math.sin(t * 6.0) : s.state === 'armed' ? 0.5 + 0.5 * Math.sin(t * 3.2) : 0.5 + 0.5 * Math.sin(t * 1.1 + s.ph);
    const g = 0.09 + s.on * 0.13 + beat * s.on * 0.08;
    s.glow.position.copy(s.pos); s.glow.scale.set(g, g, 1); s.glow.material.opacity = 0.25 + s.on * 0.75;
    s.core.position.copy(s.pos); const cs = 0.025 + s.on * 0.02; s.core.scale.set(cs, cs, 1); s.core.material.opacity = 0.35 + s.on * 0.65;
    // ping ring on armed / trade (repeats while armed or in a trade)
    s.pingAge += dt;
    if ((s.state === 'armed' && s.pingAge > 2.4) || (s.state === 'trade' && s.pingAge > 1.4)) s.pingAge = 0;
    const pa = s.pingAge, pv = pa < 1.3 && (s.state === 'armed' || s.state === 'trade');
    s.ping.visible = pv; if (pv) { s.ping.position.copy(s.pos); const ps = 0.05 + pa * 0.32; s.ping.scale.set(ps, ps, 1); s.ping.material.opacity = (1 - pa / 1.3) * 0.8; }
    // beam to the ground while in a trade
    const inT = s.state === 'trade';
    s.beam.visible = inT || s.beam.material.opacity > 0.01;
    s.beam.material.opacity += ((inT ? 0.55 + 0.25 * Math.sin(t * 9) : 0) - s.beam.material.opacity) * Math.min(1, dt * 4);
    if (s.beam.visible) {
      const p = s.beam.geometry.attributes.position, gnd = _v.copy(s.pos).sub(E).normalize().multiplyScalar(1.0).add(E);
      p.setXYZ(0, s.pos.x, s.pos.y, s.pos.z); p.setXYZ(1, gnd.x, gnd.y, gnd.z); p.needsUpdate = true;
    }
  }
  meteorStep(t, dt) {
    const U = this.mU;
    if (!this.meteor) {
      this.nextQuiet -= dt;
      let kind = this.queue.shift();
      if (!kind && this.nextQuiet <= 0 && !Q.reduced && Q.level === 'max') { kind = 'quiet'; }
      if (!kind) { U.uOn.value = Math.max(0, U.uOn.value - dt * 3); this.mHead.material.opacity = 0; this.mStreak.material.opacity = 0; this.meteorP.visible = U.uOn.value > 0.01; return; }
      if (kind === 'quiet') this.nextQuiet = 35 + Math.random() * 40;
      // across the upper sky, 30 units in front of the camera, diagonal down
      const cam = this.camera, dir = Math.random() < 0.5 ? 1 : -1, yTop = 0.55 + Math.random() * 0.3;
      const from = new THREE.Vector3(-dir * (0.15 + Math.random() * 0.5), yTop, 0.5).unproject(cam), to = new THREE.Vector3(dir * (0.55 + Math.random() * 0.4), yTop - 0.35 - Math.random() * 0.25, 0.5).unproject(cam);
      const o = cam.position, f = (p) => p.sub(o).normalize().multiplyScalar(30).add(o);
      f(from); f(to);
      const col = kind === 'win' ? theme.good : kind === 'loss' ? new THREE.Color('#ff4d6d') : new THREE.Color('#dfe8ff');
      U.uCol.value.copy(col); this.mHead.material.color.copy(col).lerp(new THREE.Color('#ffffff'), 0.5); this.mStreak.material.color.copy(col);
      const a = from.clone().project(cam), b2 = to.clone().project(cam);
      this.mStreak.material.rotation = Math.atan2((b2.y - a.y), (b2.x - a.x) * this.aspect);
      this.meteor = { from, to, s: 0, dur: kind === 'quiet' ? 0.9 : 1.6, kind };
      for (let i = 0; i < this.mPos.length; i += 3) this.mPos.set([from.x, from.y, from.z], i);
      this.meteorP.visible = true; this.lastKind = kind; this.shots = (this.shots || 0) + 1;
    }
    const M = this.meteor; M.s += dt / M.dur;
    const s = Math.min(1, M.s), e = 1 - Math.pow(1 - s, 2);
    const p = _v.lerpVectors(M.from, M.to, e);
    this.mPos.copyWithin(3, 0, this.mPos.length - 3); this.mPos.set([p.x, p.y, p.z], 0);
    this.meteorP.geometry.attributes.position.needsUpdate = true;
    const fade = Math.min(1, s * 5) * (1 - Math.max(0, (s - 0.75) / 0.25));
    U.uOn.value = fade; this.mHead.position.copy(p); const hs = M.kind === 'quiet' ? 0.8 : 1.8; this.mHead.scale.set(hs, hs, 1); this.mHead.material.opacity = fade;
    // the streak: a long thin glow behind the head, along the motion
    const back = _w.copy(M.to).sub(M.from).normalize();
    this.mStreak.position.copy(p).addScaledVector(back, -(M.kind === 'quiet' ? 1.9 : 3.6) * Math.min(1, s * 3));
    this.mStreak.scale.set((M.kind === 'quiet' ? 4.2 : 8.5) * Math.min(1, s * 3), M.kind === 'quiet' ? 0.14 : 0.3, 1); this.mStreak.material.opacity = fade;
    if (M.s >= 1) this.meteor = null;
  }
  dispose() { this.labEl?.remove(); this.aura?.dispose(); for (const rt of [this.tA, this.tC, this.tS, this.tM]) rt?.dispose(); this.ov.traverse((o) => o.material?.dispose?.()); super.dispose(); }
}
