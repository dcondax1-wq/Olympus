// Olympus Data City: the NQ data machine (tools/datacity) drawn as a night city. Reads ./city.json (written by
// `python -m tools.datacity`); without it, a demo city from ./fixture.json. Paper only: it shows research, never trades.
// Districts: Times, Confluences, While-states (one building per combination), Strategies (sized, with MFFU eval odds),
// Discoveries (monuments round the plaza) and the LIT tower in the middle. Height = $ per trade per micro after costs,
// colour = stability (gold: holds everywhere + FDR, green: both periods, amber: one, grey: noise), lit windows = sample
// size, pulsing roof beacon = rising. Pinch / drag to orbit, tap a building for its card.
import * as THREE from './three.module.min.js';

const $ = (s) => document.querySelector(s);
const COLORS = { gold: 0xffc94a, green: 0x39e59a, amber: 0xff9f43, grey: 0x5d6480, thin: 0x3a3f55, strat: 0xa68bff, lit: 0x3fd8ff };
const CLS_TXT = { gold: 'holds everywhere', green: 'both periods', amber: 'one period', grey: 'noise', thin: 'thin' };
const DNAME = { times: 'TIMES', confluences: 'CONFLUENCES', while: 'WHILE-STATES', strategies: 'STRATEGIES', discoveries: 'DISCOVERIES' };
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
};
const S = window.__city = { ready: false, mode: null, buildings: 0, quality: 'hq', fps: 0, errors: [] };

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}
const money = (v, d = 0) => (v === null || v === undefined || !isFinite(v)) ? '–' : (v < 0 ? '-' : '+') + '$' + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
const pct = (v) => (v === null || v === undefined || !isFinite(v)) ? '–' : `${(+v).toFixed(0)}%`;
const num = (v, d = 1) => (v === null || v === undefined || !isFinite(v)) ? '–' : (+v).toFixed(d);

// ------------------------------------------------------------------------------------------------ data
async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
async function loadData() {
  try {
    const d = await getJSON('./city.json');
    if (d && Array.isArray(d.buildings) && d.buildings.length) return { d, demo: !!d.demo };
  } catch (e) { /* no data yet: demo */ }
  const d = await getJSON('./fixture.json');
  return { d, demo: true };
}

// ------------------------------------------------------------------------------------------------ layout
const LOT = 2.5;
function districtGrid(list, cx, cz, kind, opt = {}) {
  const n = list.length;
  if (!n) return [];
  const cols = Math.max(1, Math.ceil(Math.sqrt(n * (opt.aspect || 1))));
  const rows = Math.ceil(n / cols);
  const cells = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const sx = c + Math.floor(c / 5) * 0.55 - (cols - 1 + Math.floor((cols - 1) / 5) * 0.55) / 2;
    const sz = r + Math.floor(r / 5) * 0.55 - (rows - 1 + Math.floor((rows - 1) / 5) * 0.55) / 2;
    cells.push([cx + sx * LOT, cz + sz * LOT]);
  }
  cells.sort((a, b) => Math.hypot(a[0] - cx, a[1] - cz) - Math.hypot(b[0] - cx, b[1] - cz));
  return list.map((b, i) => ({ kind, b, x: cells[i][0], z: cells[i][1] }));
}
function heightOf(e) { return e > 0 ? 0.7 + Math.pow(e, 0.85) * 0.22 : 0.45 + Math.max(-0.25, e * 0.004); }
function clsRank(c) { return { gold: 0, green: 1, amber: 2, grey: 3, thin: 4 }[c] ?? 5; }

function layout(d) {
  const by = { times: [], confluences: [], while: [] };
  for (const b of d.buildings) if (by[b.d]) by[b.d].push(b);
  for (const k in by) by[k].sort((a, b) => clsRank(a.cls) - clsRank(b.cls) || (b.e || 0) - (a.e || 0));
  const items = [];
  const centers = { times: [-52, -46], confluences: [46, -40], while: [0, 66], strategies: [-50, 18] };
  items.push(...districtGrid(by.times, ...centers.times, 'b'));
  items.push(...districtGrid(by.confluences, ...centers.confluences, 'b'));
  items.push(...districtGrid(by.while, ...centers.while, 'b', { aspect: 1.4 }));
  const strats = (d.strategies || []).map((s) => ({ ...s, cls: 'strat' }));
  items.push(...districtGrid(strats, ...centers.strategies, 's').map((it) => { it.x = centers.strategies[0] + (it.x - centers.strategies[0]) * 1.9; it.z = centers.strategies[1] + (it.z - centers.strategies[1]) * 1.9; return it; }));
  const byId = new Map(d.buildings.map((b) => [b.id, b]));
  const disc = (d.discoveries || []).map((x) => ({ ...(byId.get(x.id) || {}), ...x, text: x.text })).filter((x) => x.id);
  disc.forEach((x, i) => {
    const a = (i / Math.max(1, disc.length)) * Math.PI * 2 + 0.3;
    items.push({ kind: 'd', b: x, x: Math.cos(a) * 15, z: Math.sin(a) * 15 });
  });
  for (const it of items) {
    const b = it.b;
    if (it.kind === 'b') {
      it.h = heightOf(b.e || 0); it.w = 1.55; it.color = COLORS[b.cls] || COLORS.grey;
      it.lit = Math.min(1, Math.log10(Math.max(1, b.n || 1)) / 3); it.pulse = b.tr === 'rising' ? 1 : 0;
    } else if (it.kind === 's') {
      const pm = Math.max(0, ((b.spans || {})['2026'] || {}).per_month || 0);
      it.h = 3 + Math.sqrt(pm) * 0.32; it.w = 2.6; it.color = COLORS.strat; it.lit = 0.8; it.pulse = 0;
    } else {
      it.h = 7 + Math.max(0, b.e || 0) * 0.12; it.w = 1.9; it.color = b.cls === 'gold' ? COLORS.gold : 0xbff6dc; it.lit = 0.95;
      it.pulse = b.tr === 'rising' ? 1 : 0;
    }
    it.dim = 0;
  }
  return { items, centers };
}

// ------------------------------------------------------------------------------------------------ shaders
const BUILD_VS = `
attribute vec3 aColor; attribute vec4 aData; attribute float aSeed;
uniform float uMirror;
varying vec3 vColor; varying vec4 vData; varying vec3 vLocal; varying vec3 vN; varying float vFD; varying float vWy; varying float vSeed;
void main(){
  vColor=aColor; vData=aData; vLocal=position; vSeed=aSeed;
  vec4 wp = modelMatrix * instanceMatrix * vec4(position,1.0);
  if(uMirror>0.5) wp.y = -wp.y;
  vWy = wp.y;
  vN = normalize(mat3(modelMatrix*instanceMatrix)*normal);
  vec4 mv = viewMatrix*wp; vFD = -mv.z; gl_Position = projectionMatrix*mv;
}`;
const BUILD_FS = `
uniform float uTime; uniform vec3 uFog; uniform float uFogD; uniform float uMirror; uniform float uDay;
varying vec3 vColor; varying vec4 vData; varying vec3 vLocal; varying vec3 vN; varying float vFD; varying float vWy; varying float vSeed;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)) + vSeed*17.0)*43758.5453); }
void main(){
  vec3 n = abs(vN);
  float side = 1.0 - step(0.5, n.y);
  vec2 uv = n.x > 0.5 ? vec2(vLocal.z, vLocal.y) : vec2(vLocal.x, vLocal.y);
  vec2 g = vec2((uv.x + 0.5) * 3.0, uv.y * vData.x * 1.7);
  vec2 cell = floor(g); vec2 f = fract(g);
  float win = step(0.22,f.x)*step(f.x,0.78)*step(0.28,f.y)*step(f.y,0.72);
  float lit = step(hash(cell + n.xz*3.1), vData.y);
  float diff = 0.30 + 0.55*max(dot(normalize(vN), normalize(vec3(0.45,0.8,0.25))), 0.0);
  vec3 body = mix(vColor*0.16, vColor*0.55, uDay) * diff;
  vec3 warm = mix(vec3(1.0,0.86,0.58), vColor, 0.35);
  vec3 col = body + side*win*lit*warm*mix(1.25, 0.35, uDay);
  col += vColor * (1.0 - side) * 0.55;                                   // glowing roof
  col += vColor * smoothstep(0.93, 1.0, vLocal.y) * side * 0.9;          // roof edge
  col += vColor * vData.z * (0.5 + 0.5*sin(uTime*3.2 + vSeed*6.0)) * 0.45;
  col *= mix(1.0, 0.13, vData.w);
  float fog = 1.0 - exp(-uFogD*uFogD*vFD*vFD);
  col = mix(col, uFog, fog);
  float a = 1.0;
  if(uMirror>0.5) a = 0.26 * (1.0 - smoothstep(0.0, 7.0, -vWy)) * (1.0 - fog);
  gl_FragColor = vec4(col, a);
}`;
const GLOW_VS = `
attribute vec3 aColor; attribute float aSize; attribute float aPulse; attribute float aSeed;
uniform float uTime; uniform float uPR;
varying vec3 vColor; varying float vA;
void main(){
  vColor = aColor;
  float p = aPulse > 0.5 ? 0.55 + 0.45*sin(uTime*3.2 + aSeed*6.0) : 1.0;
  vA = p;
  vec4 mv = modelViewMatrix * vec4(position,1.0);
  gl_PointSize = aSize * p * uPR * (300.0 / max(1.0, -mv.z));
  gl_Position = projectionMatrix * mv;
}`;
const GLOW_FS = `
uniform float uDay; varying vec3 vColor; varying float vA;
void main(){
  vec2 d = gl_PointCoord - 0.5; float r = length(d);
  float a = exp(-r*r*14.0) + 0.35*exp(-r*r*60.0);
  gl_FragColor = vec4(vColor * a * vA * mix(1.0, 0.45, uDay), 1.0);
}`;
const FLOW_VS = `
attribute vec4 aSeg; attribute vec3 aColor; attribute vec2 aMove;
uniform float uTime; uniform float uPR;
varying vec3 vColor;
void main(){
  vColor = aColor;
  float t = fract(uTime * aMove.x + aMove.y);
  vec3 p = vec3(mix(aSeg.x, aSeg.z, t), 0.22, mix(aSeg.y, aSeg.w, t));
  vec4 mv = modelViewMatrix * vec4(p,1.0);
  gl_PointSize = 3.2 * uPR * (60.0 / max(1.0, -mv.z));
  gl_Position = projectionMatrix * mv;
}`;
const FLOW_FS = `
varying vec3 vColor; uniform float uDay;
void main(){ vec2 d = gl_PointCoord-0.5; float a = exp(-dot(d,d)*18.0); gl_FragColor = vec4(vColor*a*mix(1.0,0.5,uDay),1.0); }`;
const GROUND_VS = `varying vec3 vW; varying float vFD;
void main(){ vec4 wp = modelMatrix*vec4(position,1.0); vW = wp.xyz; vec4 mv = viewMatrix*wp; vFD = -mv.z; gl_Position = projectionMatrix*mv; }`;
const GROUND_FS = `
uniform vec3 uFog; uniform float uFogD; uniform float uDay; uniform float uTime;
varying vec3 vW; varying float vFD;
void main(){
  vec2 p = vW.xz / 2.5;
  vec2 g = abs(fract(p - 0.5) - 0.5) / fwidth(p);
  float line = 1.0 - min(min(g.x, g.y), 1.0);
  vec3 base = mix(vec3(0.012,0.016,0.04), vec3(0.42,0.47,0.55), uDay);
  vec3 col = base + line * mix(vec3(0.03,0.12,0.24), vec3(0.08,0.1,0.13), uDay) * 0.6;
  float r = length(vW.xz);
  col += mix(vec3(0.0,0.45,0.75), vec3(0.15,0.2,0.25), uDay) * 0.32 * exp(-r*0.055);
  col += vec3(0.0,0.5,0.8) * 0.18 * smoothstep(0.6, 0.0, abs(r - 15.0)) * (0.6 + 0.4*sin(uTime*1.5));
  float fog = 1.0 - exp(-uFogD*uFogD*vFD*vFD);
  gl_FragColor = vec4(mix(col, uFog, fog), 0.80);
}`;
const SKY_VS = `varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
const SKY_FS = `
uniform float uDay; varying vec3 vP;
void main(){
  float h = normalize(vP).y;
  vec3 nTop = vec3(0.005,0.008,0.03), nHor = vec3(0.06,0.05,0.16), nGlow = vec3(0.35,0.12,0.45);
  vec3 dTop = vec3(0.22,0.45,0.85), dHor = vec3(0.72,0.84,0.96), dGlow = vec3(1.0,0.85,0.7);
  vec3 top = mix(nTop, dTop, uDay), hor = mix(nHor, dHor, uDay), glow = mix(nGlow, dGlow, uDay);
  vec3 c = mix(hor, top, smoothstep(0.0, 0.55, h));
  c += glow * 0.35 * exp(-abs(h)*9.0);
  gl_FragColor = vec4(c, 1.0);
}`;
const TOWER_FS = `
uniform float uTime; uniform float uDay; varying vec3 vL; varying vec3 vN;
void main(){
  float band = smoothstep(0.92, 1.0, fract(vL.y*0.55 - uTime*0.35));
  float rib = smoothstep(0.85, 1.0, abs(sin(atan(vL.z, vL.x)*4.0)));
  vec3 c = vec3(0.02,0.07,0.12) + vec3(0.25,0.85,1.0)*(band*0.9 + rib*0.35) + vec3(0.25,0.85,1.0)*0.12;
  c = mix(c, c*0.6 + vec3(0.1,0.2,0.3), uDay);
  gl_FragColor = vec4(c, 1.0);
}`;
const TOWER_VS = `varying vec3 vL; varying vec3 vN; void main(){ vL = position; vN = normal; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;

// ------------------------------------------------------------------------------------------------ scene
let renderer, scene, camera, clock, U, mesh, mirror, glow, flow, stars, tower, data, L, labels = [];
const cam = { theta: -0.75, phi: 1.02, radius: 150, target: new THREE.Vector3(0, 0, 8), goal: null };
const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const view = calm ? { theta: cam.theta, phi: cam.phi, radius: cam.radius, target: cam.target.clone() }     // the intro swoop
                  : { theta: cam.theta - 0.9, phi: 0.55, radius: 330, target: cam.target.clone() };
let fly = null, lastInput = performance.now(), quality = store.get('dc.q', 'hq'), day = store.get('dc.day', '0') === '1';

function makeRenderer() {
  const canvas = $('#c');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: quality === 'hq', powerPreference: 'high-performance' });
  renderer.setPixelRatio(quality === 'hq' ? Math.min(window.devicePixelRatio || 1, 2) : 1);
  renderer.setSize(window.innerWidth, window.innerHeight, false);
}

function textSprite(txt, color = '#e9ecf6', size = 1) {
  const c = document.createElement('canvas'); c.width = 512; c.height = 96;
  const g = c.getContext('2d');
  g.font = '800 46px -apple-system, system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.shadowColor = color; g.shadowBlur = 18; g.fillStyle = color;
  g.fillText(txt.split('').join(String.fromCharCode(8202)), 256, 50);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, fog: false }));
  s.scale.set(16 * size, 3 * size, 1);
  s.renderOrder = 6;                       // after the see-through ground, so the street never washes a name out
  return s;
}

function build() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(52, window.innerWidth / window.innerHeight, 0.5, 1600);
  clock = new THREE.Clock();
  U = { uTime: { value: 0 }, uFog: { value: new THREE.Color() }, uFogD: { value: 0.0065 }, uDay: { value: day ? 1 : 0 },
        uPR: { value: renderer.getPixelRatio() }, uMirror: { value: 0 } };
  const items = L.items;
  // sky + stars
  const sky = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), new THREE.ShaderMaterial({ vertexShader: SKY_VS, fragmentShader: SKY_FS,
    uniforms: { uDay: U.uDay }, side: THREE.BackSide, depthWrite: false }));
  scene.add(sky);
  const nStars = quality === 'hq' ? 1600 : 400, sp = new Float32Array(nStars * 3);
  for (let i = 0; i < nStars; i++) {
    const a = Math.random() * Math.PI * 2, h = 0.08 + Math.random() * 0.9, r = 800;
    sp[i * 3] = Math.cos(a) * r * Math.sqrt(1 - h * h); sp[i * 3 + 1] = h * r; sp[i * 3 + 2] = Math.sin(a) * r * Math.sqrt(1 - h * h);
  }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  stars = new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xcfd8ff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0.85, depthWrite: false, fog: false }));
  scene.add(stars);
  // ground
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(700, 700), new THREE.ShaderMaterial({ vertexShader: GROUND_VS, fragmentShader: GROUND_FS,
    uniforms: { uFog: U.uFog, uFogD: U.uFogD, uDay: U.uDay, uTime: U.uTime }, transparent: true, depthWrite: true }));
  ground.rotation.x = -Math.PI / 2; ground.renderOrder = 1; scene.add(ground);
  // buildings: one instanced mesh (+ its mirror image for the wet-street reflections)
  const geo = new THREE.BoxGeometry(1, 1, 1); geo.translate(0, 0.5, 0);
  const n = items.length;
  const aColor = new Float32Array(n * 3), aData = new Float32Array(n * 4), aSeed = new Float32Array(n);
  const mat = new THREE.ShaderMaterial({ vertexShader: BUILD_VS, fragmentShader: BUILD_FS,
    uniforms: { uTime: U.uTime, uFog: U.uFog, uFogD: U.uFogD, uDay: U.uDay, uMirror: { value: 0 } } });
  mesh = new THREE.InstancedMesh(geo, mat, n);
  const m4 = new THREE.Matrix4(), col = new THREE.Color();
  items.forEach((it, i) => {
    m4.makeScale(it.w, it.h, it.w); m4.setPosition(it.x, 0, it.z); mesh.setMatrixAt(i, m4);
    col.setHex(it.color); aColor.set([col.r, col.g, col.b], i * 3);
    aData.set([it.h, it.lit, it.pulse, 0], i * 4); aSeed[i] = (i * 0.6180339) % 1;
  });
  geo.setAttribute('aColor', new THREE.InstancedBufferAttribute(aColor, 3));
  geo.setAttribute('aData', new THREE.InstancedBufferAttribute(aData, 4));
  geo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(aSeed, 1));
  mesh.instanceMatrix.needsUpdate = true; mesh.renderOrder = 2;
  mesh.computeBoundingSphere();
  scene.add(mesh);
  const mmat = new THREE.ShaderMaterial({ vertexShader: BUILD_VS, fragmentShader: BUILD_FS, transparent: true, depthWrite: false,
    side: THREE.DoubleSide, uniforms: { uTime: U.uTime, uFog: U.uFog, uFogD: U.uFogD, uDay: U.uDay, uMirror: { value: 1 } } });
  mirror = new THREE.InstancedMesh(geo, mmat, n); mirror.instanceMatrix = mesh.instanceMatrix; mirror.renderOrder = 0;
  mirror.frustumCulled = false; mirror.visible = quality === 'hq';
  scene.add(mirror);
  // glow sprites (bloom-like): every gold / green roof, the monuments, the strategy towers, and rising beacons
  const gl = items.map((it, i) => [it, i]).filter(([it]) => quality === 'hq' ? (it.kind !== 'b' || it.b.cls === 'gold' || it.b.cls === 'green' || it.pulse)
                                                                             : (it.kind !== 'b' || it.b.cls === 'gold' || it.pulse));
  const gp = new Float32Array(gl.length * 3), gc = new Float32Array(gl.length * 3), gs = new Float32Array(gl.length),
        gpu = new Float32Array(gl.length), gse = new Float32Array(gl.length);
  gl.forEach(([it, i], k) => {
    gp.set([it.x, it.h + 0.35, it.z], k * 3); col.setHex(it.color); gc.set([col.r, col.g, col.b], k * 3);
    gs[k] = it.kind === 'd' ? 9 : it.kind === 's' ? 8 : it.b.cls === 'gold' ? 7 : it.pulse ? 5 : 2.6; gpu[k] = it.pulse; gse[k] = (i * 0.6180339) % 1;
  });
  const gg = new THREE.BufferGeometry();
  gg.setAttribute('position', new THREE.BufferAttribute(gp, 3)); gg.setAttribute('aColor', new THREE.BufferAttribute(gc, 3));
  gg.setAttribute('aSize', new THREE.BufferAttribute(gs, 1)); gg.setAttribute('aPulse', new THREE.BufferAttribute(gpu, 1));
  gg.setAttribute('aSeed', new THREE.BufferAttribute(gse, 1));
  glow = new THREE.Points(gg, new THREE.ShaderMaterial({ vertexShader: GLOW_VS, fragmentShader: GLOW_FS, uniforms: { uTime: U.uTime, uPR: U.uPR, uDay: U.uDay },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  glow.renderOrder = 3; scene.add(glow);
  // streets: roads from the plaza to every district + a ring, with flowing trades (green wins, red losses)
  const segs = [];
  const C = L.centers;
  for (const k of Object.keys(C)) segs.push([0, 0, C[k][0], C[k][1]]);
  for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2, b = (i + 1) / 24 * Math.PI * 2; segs.push([Math.cos(a) * 22, Math.sin(a) * 22, Math.cos(b) * 22, Math.sin(b) * 22]); }
  for (const k of ['times', 'confluences', 'while']) {
    const [cx, cz] = C[k], w = 30;
    segs.push([cx - w, cz, cx + w, cz], [cx, cz - w, cx, cz + w]);
  }
  const roadGeo = new THREE.PlaneGeometry(1, 1); roadGeo.rotateX(-Math.PI / 2);
  const roads = new THREE.InstancedMesh(roadGeo, new THREE.MeshBasicMaterial({ color: 0x0a1028, transparent: true, opacity: 0.85, depthWrite: false }), segs.length);
  segs.forEach((s, i) => {
    const dx = s[2] - s[0], dz = s[3] - s[1], len = Math.hypot(dx, dz);
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -Math.atan2(dz, dx));
    m4.compose(new THREE.Vector3((s[0] + s[2]) / 2, 0.02, (s[1] + s[3]) / 2), q, new THREE.Vector3(len, 1, 1.4));
    roads.setMatrixAt(i, m4);
  });
  roads.renderOrder = 1; scene.add(roads);
  const winRate = Math.max(0.3, Math.min(0.7, (data.buildings.reduce((a, b) => a + (b.w || 50), 0) / Math.max(1, data.buildings.length)) / 100));
  const nf = quality === 'hq' ? 1400 : 380, fs = new Float32Array(nf * 4), fc = new Float32Array(nf * 3), fm = new Float32Array(nf * 2), fp = new Float32Array(nf * 3);
  for (let i = 0; i < nf; i++) {
    let s = segs[i % segs.length]; if (Math.random() < 0.5) s = [s[2], s[3], s[0], s[1]];
    const off = (Math.random() - 0.5) * 0.9;
    const dx = s[2] - s[0], dz = s[3] - s[1], len = Math.hypot(dx, dz) || 1, nx = -dz / len * off, nz = dx / len * off;
    fs.set([s[0] + nx, s[1] + nz, s[2] + nx, s[3] + nz], i * 4);
    const win = Math.random() < winRate; col.setHex(win ? 0x39e59a : 0xff5d73); fc.set([col.r, col.g, col.b], i * 3);
    fm.set([(0.6 + Math.random() * 0.8) * 6 / len, Math.random()], i * 2);
  }
  const fg = new THREE.BufferGeometry();
  fg.setAttribute('position', new THREE.BufferAttribute(fp, 3)); fg.setAttribute('aSeg', new THREE.BufferAttribute(fs, 4));
  fg.setAttribute('aColor', new THREE.BufferAttribute(fc, 3)); fg.setAttribute('aMove', new THREE.BufferAttribute(fm, 2));
  flow = new THREE.Points(fg, new THREE.ShaderMaterial({ vertexShader: FLOW_VS, fragmentShader: FLOW_FS, uniforms: { uTime: U.uTime, uPR: U.uPR, uDay: U.uDay },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  flow.frustumCulled = false; flow.renderOrder = 3; scene.add(flow);
  // the LIT tower in the plaza
  tower = new THREE.Group();
  const tm = new THREE.ShaderMaterial({ vertexShader: TOWER_VS, fragmentShader: TOWER_FS, uniforms: { uTime: U.uTime, uDay: U.uDay } });
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 3.4, 40, 8, 1), tm); shaft.position.y = 20; tower.add(shaft);
  const spire = new THREE.Mesh(new THREE.ConeGeometry(1.5, 9, 8), tm); spire.position.y = 44.5; tower.add(spire);
  const ringM = new THREE.MeshBasicMaterial({ color: COLORS.lit, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false });
  for (const [y, r] of [[12, 5.5], [26, 4.4], [38, 3.3]]) { const ring = new THREE.Mesh(new THREE.TorusGeometry(r, 0.09, 6, 64), ringM); ring.rotation.x = Math.PI / 2; ring.position.y = y; tower.add(ring); }
  const beacon = textSprite('LIT · ZLARIOR', '#7fe9ff', 0.9); beacon.position.set(0, 53, 0); tower.add(beacon);
  tower.userData.pick = true;
  scene.add(tower);
  const tg = new THREE.BufferGeometry(); tg.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0, 49, 0]), 3));
  tg.setAttribute('aColor', new THREE.BufferAttribute(new Float32Array([0.25, 0.85, 1.0]), 3)); tg.setAttribute('aSize', new THREE.BufferAttribute(new Float32Array([26]), 1));
  tg.setAttribute('aPulse', new THREE.BufferAttribute(new Float32Array([1]), 1)); tg.setAttribute('aSeed', new THREE.BufferAttribute(new Float32Array([0.2]), 1));
  const tglow = new THREE.Points(tg, glow.material); tglow.renderOrder = 3; scene.add(tglow);
  // district names
  const lab = { times: L.centers.times, confluences: L.centers.confluences, while: L.centers.while, strategies: L.centers.strategies };
  for (const k in lab) { const s = textSprite(DNAME[k], k === 'strategies' ? '#c9b8ff' : '#e9ecf6', k === 'while' ? 1.3 : 1); s.position.set(lab[k][0], k === 'strategies' ? 22 : 18, lab[k][1]); scene.add(s); labels.push(s); }
  const dl = textSprite(DNAME.discoveries, '#ffe08a', 0.8); dl.position.set(0, 6, -22); scene.add(dl); labels.push(dl);
  applySky();
}

function applySky() {
  U.uDay.value = day ? 1 : 0;
  const fogc = new THREE.Color(day ? 0xa9c4ea : 0x070a1c);
  U.uFog.value.copy(fogc);
  scene.background = fogc;
  U.uFogD.value = day ? 0.0045 : 0.0065;
  stars.visible = !day;
  $('#skyB').classList.toggle('on', day);
  document.querySelector('meta[name=theme-color]').setAttribute('content', day ? '#a9c4ea' : '#05060f');
}

// ------------------------------------------------------------------------------------------------ camera + input
function applyCamera(dt) {
  const k = 1 - Math.pow(0.0015, dt);
  if (fly) {
    fly.t = (fly.t + dt * 0.012) % 1;
    const p = fly.curve.getPointAt(fly.t), q = fly.look.getPointAt(fly.t);
    camera.position.lerp(p, Math.min(1, k * 2)); fly.at.lerp(q, Math.min(1, k * 2)); camera.lookAt(fly.at);
    return;
  }
  if (cam.goal) {
    cam.target.lerp(cam.goal.target, k); cam.radius += (cam.goal.radius - cam.radius) * k;
    if (cam.target.distanceTo(cam.goal.target) < 0.05 && Math.abs(cam.radius - cam.goal.radius) < 0.1) cam.goal = null;
  }
  if (!calm && performance.now() - lastInput > 9000 && !cam.goal) cam.theta += dt * 0.035;
  view.theta += (cam.theta - view.theta) * k; view.phi += (cam.phi - view.phi) * k; view.radius += (cam.radius - view.radius) * k;
  view.target.lerp(cam.target, k);
  const sp = Math.sin(view.phi);
  camera.position.set(view.target.x + view.radius * sp * Math.cos(view.theta), view.target.y + view.radius * Math.cos(view.phi),
                      view.target.z + view.radius * sp * Math.sin(view.theta));
  camera.lookAt(view.target);
}
function stopFly() { if (fly) { fly = null; $('#flyB').classList.remove('on'); const p = camera.position; cam.radius = Math.max(20, Math.min(260, p.length())); } }
function startFly() {
  const C = L.centers;
  // camera path round each district, each point with what it looks at (same t on both curves)
  const T = C.times, F = C.confluences, W = C.while, G = C.strategies;
  const path = [[[0, 34, -34], [0, 18, 0]], [[F[0] - 10, 16, F[1] - 34], F], [[F[0] + 34, 12, F[1] + 6], F], [[30, 10, 26], [0, 10, 0]],
                [[W[0] + 44, 14, W[1] - 10], W], [[W[0] + 10, 18, W[1] + 46], W], [[W[0] - 44, 12, W[1] + 4], W], [[G[0] - 20, 10, G[1] + 14], G],
                [[T[0] - 34, 14, T[1] + 14], T], [[T[0] + 6, 18, T[1] - 36], T], [[-22, 12, -20], [0, 22, 0]], [[-14, 26, 22], [0, 16, 0]]];
  const v3 = (a) => new THREE.Vector3(a[0], a.length === 3 ? a[1] : 2, a.length === 3 ? a[2] : a[1]);
  fly = { t: 0, curve: new THREE.CatmullRomCurve3(path.map((x) => v3(x[0])), true, 'centripetal'),
          look: new THREE.CatmullRomCurve3(path.map((x) => v3(x[1])), true, 'centripetal'), at: view.target.clone() };
  $('#flyB').classList.add('on');
}
function clampCam() { cam.phi = Math.max(0.18, Math.min(1.45, cam.phi)); cam.radius = Math.max(8, Math.min(320, cam.radius)); }

const ptrs = new Map();
let gesture = null;
function onDown(e) {
  if (e.target !== renderer.domElement) return;
  renderer.domElement.setPointerCapture?.(e.pointerId);
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
  lastInput = performance.now(); cam.goal = null;
  if (ptrs.size === 1) gesture = { x0: e.clientX, y0: e.clientY, t0: performance.now(), moved: 0 };
  else gesture = gesture ? { ...gesture, moved: 99 } : null;
}
function onMove(e) {
  if (!ptrs.has(e.pointerId)) return;
  const prev = ptrs.get(e.pointerId), cur = { x: e.clientX, y: e.clientY };
  lastInput = performance.now();
  if (ptrs.size === 1) {
    const dx = cur.x - prev.x, dy = cur.y - prev.y;
    if (gesture) gesture.moved += Math.abs(dx) + Math.abs(dy);
    if (gesture && gesture.moved > 6) { stopFly(); cam.theta += dx * 0.006; cam.phi -= dy * 0.005; clampCam(); }
  } else if (ptrs.size === 2) {
    stopFly();
    const ids = [...ptrs.keys()], other = ptrs.get(ids[0] === e.pointerId ? ids[1] : ids[0]);
    const d0 = Math.hypot(prev.x - other.x, prev.y - other.y), d1 = Math.hypot(cur.x - other.x, cur.y - other.y);
    if (d0 > 0 && d1 > 0) cam.radius *= d0 / d1;
    const mx = (cur.x - prev.x) / 2, my = (cur.y - prev.y) / 2, s = cam.radius * 0.0022;
    const st = Math.sin(cam.theta), ct = Math.cos(cam.theta);   // right = (sin, 0, -cos), forward = (-cos, 0, -sin)
    cam.target.x += (-st * mx - ct * my) * s; cam.target.z += (ct * mx - st * my) * s;
    clampCam();
  }
  ptrs.set(e.pointerId, cur);
}
function onUp(e) {
  if (!ptrs.has(e.pointerId)) return;
  ptrs.delete(e.pointerId);
  if (gesture && ptrs.size === 0 && gesture.moved <= 6 && performance.now() - gesture.t0 < 450) pick(e.clientX, e.clientY);
  if (ptrs.size === 0) gesture = null;
}
function onWheel(e) { e.preventDefault(); stopFly(); lastInput = performance.now(); cam.radius *= Math.exp(e.deltaY * 0.0012); clampCam(); }

const ray = new THREE.Raycaster();
function pick(x, y) {
  const v = new THREE.Vector2((x / window.innerWidth) * 2 - 1, -(y / window.innerHeight) * 2 + 1);
  ray.setFromCamera(v, camera);
  const hits = ray.intersectObjects([mesh, tower], true);
  if (!hits.length) { closeAll(); return; }
  const h = hits[0];
  if (h.object === mesh && h.instanceId !== undefined) { openItem(L.items[h.instanceId]); return; }
  openLit();
}
function focus(it) {
  stopFly();
  cam.goal = { target: new THREE.Vector3(it.x, Math.min(it.h * 0.5, 6), it.z), radius: 40 + it.h * 2 };
  cam.phi = Math.min(cam.phi, 0.95);
}

// ------------------------------------------------------------------------------------------------ UI
function closeAll() { document.querySelectorAll('.panel.on').forEach((p) => p.classList.remove('on')); }
function openPanel(id) { closeAll(); $('#' + id).classList.add('on'); }
function badge(cls, txt) { return el('span', 'badge b-' + cls, txt); }
function sparkSVG(sp) {
  if (!sp || sp.length < 2) return null;
  const NS = 'http://www.w3.org/2000/svg', w = 300, h = 56, lo = Math.min(0, ...sp), hi = Math.max(0, ...sp), rng = (hi - lo) || 1;
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('class', 'spark'); svg.setAttribute('preserveAspectRatio', 'none');
  const y = (v) => h - 4 - ((v - lo) / rng) * (h - 8);
  const z = document.createElementNS(NS, 'line'); z.setAttribute('x1', 0); z.setAttribute('x2', w); z.setAttribute('y1', y(0)); z.setAttribute('y2', y(0));
  z.setAttribute('stroke', 'rgba(255,255,255,.18)'); z.setAttribute('stroke-dasharray', '3 3'); svg.appendChild(z);
  const p = document.createElementNS(NS, 'polyline');
  p.setAttribute('points', sp.map((v, i) => `${(i / (sp.length - 1)) * w},${y(v)}`).join(' '));
  p.setAttribute('fill', 'none'); p.setAttribute('stroke', sp[sp.length - 1] >= 0 ? '#39e59a' : '#ff6b7f'); p.setAttribute('stroke-width', '2');
  p.setAttribute('vector-effect', 'non-scaling-stroke'); svg.appendChild(p);
  return svg;
}
function kv(grid, label, value, cls) { const d = el('div'); d.appendChild(el('small', null, label)); const b = el('b', cls || null, value); d.appendChild(b); grid.appendChild(d); }
function spanTable(rows, cols) {
  const t = el('table'), hr = el('tr'); hr.appendChild(el('th', null, ''));
  for (const c of cols) hr.appendChild(el('th', null, c[0]));
  t.appendChild(hr);
  for (const [name, o] of rows) {
    const tr = el('tr'); tr.appendChild(el('td', null, name));
    for (const c of cols) tr.appendChild(el('td', null, c[1](o || {})));
    t.appendChild(tr);
  }
  return t;
}

function openItem(it) {
  if (!it) return;
  if (it.kind === 's') return openStrategy(it.b, it);
  const b = it.b, body = $('#cardBody');
  body.replaceChildren();
  body.appendChild(el('h2', null, b.lab || b.id));
  const tags = el('div');
  tags.appendChild(badge(b.cls || 'grey', CLS_TXT[b.cls] || b.cls));
  if (b.fdr) tags.appendChild(badge('fdr', 'passes FDR'));
  if (b.tr === 'rising' || b.tr === 'decaying') tags.appendChild(badge(b.tr, b.tr));
  if (it.kind === 'd') tags.appendChild(badge('fdr', 'discovery'));
  body.appendChild(tags);
  const big = el('div', 'big');
  const v = el('span', 'v ' + ((b.e || 0) >= 0 ? 'pos' : 'neg'), money(b.e)); big.appendChild(v);
  big.appendChild(el('span', 'u', 'per trade per MNQ micro, after $2.90 costs'));
  body.appendChild(big);
  const g = el('div', 'grid4');
  kv(g, 'win rate', pct(b.w)); kv(g, 'hit 2R', pct(b.h2)); kv(g, 'trades/week', num(b.tpw, 2)); kv(g, 'R/trade', (b.r >= 0 ? '+' : '') + num(b.r, 2));
  body.appendChild(g);
  if (b.h1 !== undefined) {
    const g2 = el('div', 'grid4');
    kv(g2, 'hit 1R', pct(b.h1)); kv(g2, 'hit 3R', pct(b.h3)); kv(g2, '30-min pts', num(b.f30, 1)); kv(g2, '60-min pts', num(b.f60, 1));
    body.appendChild(g2);
  }
  body.appendChild(spanTable([['2026', { e: b.e26, w: b.w26, n: b.n26, t: b.tpw26 }], ['2021-25', { e: b.eo, w: b.wo, n: b.no, t: b.tpwo }]],
    [['$/trade', (o) => money(o.e)], ['win', (o) => pct(o.w)], ['trades', (o) => o.n ?? '–'], ['/week', (o) => num(o.t, 2)]]));
  const sp = sparkSVG(b.sp);
  if (sp) { body.appendChild(el('div', 'note', 'Cumulative $ per micro, quarter by quarter')); body.appendChild(sp); }
  if (b.yrs) {
    const yrs = Object.entries(b.yrs).map(([y, v]) => `${y}: ${money(v[1])} (${v[0]})`).join(' · ');
    body.appendChild(el('div', 'note', 'Per year ($/trade, trades): ' + yrs));
  }
  body.appendChild(el('div', 'note', b.text || `Median stop ${num(b.stop, 1)} pts · ${b.n} trades · one trade a day at most.`));
  body.appendChild(el('div', 'note', 'Paper only: the data city proposes, it never changes the bot.'));
  openPanel('card');
  focus(it);
  try { history.replaceState(null, '', '#b=' + encodeURIComponent(b.id)); } catch (e) { /* file:// */ }
}
const SPAN_COLS = [['trades', (o) => o.n ?? '–'], ['/wk', (o) => num(o.tpw, 2)], ['win', (o) => pct(o.win)], ['PF', (o) => num(o.pf, 2)],
                   ['net', (o) => money(o.net)], ['$/mo', (o) => money(o.per_month)], ['2wk pass/fail', (o) => `${num(o.p10, 0)}/${num(o.f10, 0)}%`]];
function openStrategy(s, it) {
  const body = $('#cardBody'); body.replaceChildren();
  body.appendChild(el('h2', null, s.lab));
  const tags = el('div'); tags.appendChild(badge('fdr', 'sized strategy')); body.appendChild(tags);
  body.appendChild(el('div', 'note', `$500 at risk a trade, size follows the stop (1-40 micros), costs in, MFFU Builder 50K evals started every session.`));
  body.appendChild(spanTable([['2026', s.spans?.['2026']], ['2021-25', s.spans?.['2021-25']]], SPAN_COLS));
  if (s.oos_2025_26) body.appendChild(el('div', 'note', `Picked on 2021-24 only. 2025-26 (never seen): ${s.oos_2025_26.n} trades, ${num(s.oos_2025_26.r, 3)} R a trade after costs.`));
  if (s.member_text) { const ul = el('ul', 'list'); s.member_text.forEach((t) => ul.appendChild(el('li', null, t))); body.appendChild(ul); }
  body.appendChild(el('div', 'note', 'Paper only: never routed to an account.'));
  openPanel('card');
  if (it) focus(it);
}
function openLit() {
  const lit = data.lit; const body = $('#cardBody'); body.replaceChildren();
  body.appendChild(el('h2', null, lit ? lit.title : 'LIT (Zlarior)'));
  const tags = el('div'); tags.appendChild(badge('fdr', 'live strategy')); body.appendChild(tags);
  if (lit) {
    const rows = [['2026', lit.spans['2026']], ['2026 H2 (check)', lit.spans['2026 H2']], ['2021-25', lit.spans['2021-25']]].filter((r) => r[1]);
    body.appendChild(spanTable(rows, SPAN_COLS));
    body.appendChild(el('div', 'note', lit.note));
  } else body.appendChild(el('div', 'note', 'Run lit_live not found.'));
  openPanel('card');
  cam.goal = { target: new THREE.Vector3(0, 16, 0), radius: 80 };
}

function itemById(id) { return L.items.find((it) => it.b && it.b.id === id && it.kind !== 'd') || L.items.find((it) => it.b && it.b.id === id); }
function listRow(ul, k, color, title, sub, right, onClick) {
  const li = el('li'); const kk = el('span', 'k', k); kk.style.background = color; li.appendChild(kk);
  const t = el('span', 't'); t.appendChild(el('div', null, title)); if (sub) t.appendChild(el('small', null, sub)); li.appendChild(t);
  if (right !== undefined) { const m = el('span', 'm ' + (String(right).startsWith('-') ? 'neg' : 'pos'), right); li.appendChild(m); }
  li.addEventListener('click', onClick); ul.appendChild(li);
}
const hex = (c) => '#' + (COLORS[c] ?? COLORS.grey).toString(16).padStart(6, '0');
function fillTop() {
  const body = $('#topBody'); body.replaceChildren();
  body.appendChild(el('h2', null, 'Top 10: what holds in 2026 and 2021-25'));
  body.appendChild(el('div', 'note', 'Ranked by the weaker of the two periods. Gold = also positive in every year with 8+ trades and passes the noise guard.'));
  const ul = el('ul', 'list');
  (data.top10 || []).forEach((t, i) => listRow(ul, i + 1, hex(t.cls), t.lab, `${pct(t.w)} win · ${num(t.tpw, 2)}/wk${t.tr !== 'steady' ? ' · ' + t.tr : ''}`, money(t.e), () => openItem(itemById(t.id))));
  if (!(data.top10 || []).length) ul.appendChild(el('li', null, 'Nothing holds in both periods yet.'));
  body.appendChild(ul);
}
function fillToday() {
  const body = $('#todayBody'); body.replaceChildren();
  body.appendChild(el('h2', null, "Today's discoveries"));
  body.appendChild(el('div', 'note', `Data to ${data.last_day || '–'}. New or rising findings, then the top setups that fired on that day.`));
  const ul = el('ul', 'list');
  (data.discoveries || []).forEach((d, i) => listRow(ul, d.new ? 'N' : i + 1, hex(d.cls), d.text, d.new ? 'new on the board' : (d.tr !== 'steady' ? d.tr : ''), undefined, () => openItem(itemById(d.id))));
  body.appendChild(ul);
  if ((data.today || []).length) {
    body.appendChild(el('div', 'note', `Fired on ${data.last_day}:`));
    const u2 = el('ul', 'list');
    data.today.forEach((t) => listRow(u2, '•', '#3fd8ff', t.lab, `entered ${t.at} ET · ${num(t.R, 2)} R`, money(t.pnl), () => openItem(itemById(t.id))));
    body.appendChild(u2);
  }
}
function fillAbout() {
  const g = data.summary?.guard || {}, body = $('#aboutBody'); body.replaceChildren();
  body.appendChild(el('h2', null, 'How to read the city'));
  const p = (t) => body.appendChild(el('div', 'note', t));
  p('Every building is one combination: a time, a confluence (sweep, FVG, IFVG, CISD, displacement, VWAP, gap fill, news) and up to two "while" states (VWAP side, EMA trend, ATR, VIX, London vs Asia, day type, gap, ES-NQ SMT, weekday, DST, news day).');
  p('Each is a mini-backtest on CME NQ1! 5m bars: one trade a day, entry at the next bar, stop 1 tick beyond the structure, target 2R or the close after 2 hours, $1.90 commission + 2 ticks slippage per micro.');
  p('Height = $ per trade per micro. Gold = positive in 2026, in 2021-25 and in every year with 8+ trades AND passes the Benjamini-Hochberg false-discovery guard. Green = positive in both periods. Amber = one period only. Grey = noise or a loser. Lit windows = sample size. A pulsing roof = rising lately.');
  p(`Honesty: ${(g.tried || 0).toLocaleString()} combinations tried, ${(g.tested || 0).toLocaleString()} with 30+ trades, ${g.fdr_pos ?? '–'} pass the FDR guard (a shuffled-sign placebo passes ${g.placebo_fdr ?? '–'}). Picked on 2021-24 only, ${g.holdout?.picked_2021_24 ?? '–'} combinations; ${g.holdout?.pct_positive ?? '–'}% stayed positive in 2025-26. Most of the city is noise, and the city says so.`);
  p('The middle tower is LIT (Zlarior), the live strategy. Paper only: nothing here changes the bot.');
  const lift = data.lift || [];
  if (!lift.length) return;
  body.appendChild(el('h2', 'sub', 'What the city learned about confluences'));
  p('What one "while" state adds to the same trigger and window, in R per trade after costs (median over every base with 30+ trades). "Both" = share of bases where it helps in 2026 AND in 2021-25.');
  const top = Math.max(...lift.map((x) => Math.abs(x.med_r))) || 1, ul = el('ul', 'lift');
  for (const x of lift) {
    const li = el('li'); li.appendChild(el('span', 'ln', x.lab));
    const bar = el('span', 'lb'); const fill = el('i', x.med_r >= 0 ? 'up' : 'dn');
    fill.style.width = `${Math.round(50 * Math.abs(x.med_r) / top)}%`; bar.appendChild(fill); li.appendChild(bar);
    li.appendChild(el('span', 'lv ' + (x.med_r >= 0 ? 'pos' : 'neg'), `${x.med_r >= 0 ? '+' : ''}${x.med_r.toFixed(2)}R`));
    li.appendChild(el('span', 'lp', `both ${Math.round(x.both_pct)}%`));
    ul.appendChild(li);
  }
  body.appendChild(ul);
}
let segCls = 'all';
function runFind() {
  const q = $('#q').value.trim().toLowerCase(), words = q.split(/\s+/).filter(Boolean);
  const ul = $('#findList'); ul.replaceChildren();
  const match = (it) => it.b && (segCls === 'all' || it.b.cls === segCls) && words.every((w) => (it.b.lab || '').toLowerCase().includes(w) || (it.b.id || '').toLowerCase().includes(w));
  const aData = mesh.geometry.getAttribute('aData');
  let shown = 0;
  const filtering = words.length > 0 || segCls !== 'all';
  const hits = [];
  L.items.forEach((it, i) => { const m = match(it); aData.setW(i, filtering && !m ? 1 : 0); if (m && it.kind !== 's') hits.push(it); });
  aData.needsUpdate = true;
  hits.sort((a, b) => clsRank(a.b.cls) - clsRank(b.b.cls) || (b.b.e || 0) - (a.b.e || 0));
  for (const it of hits) { if (shown++ >= 25) break; listRow(ul, '', hex(it.b.cls), it.b.lab, `${pct(it.b.w)} win · ${num(it.b.tpw, 2)}/wk · ${it.b.n} trades`, money(it.b.e), () => openItem(it)); }
  if (!hits.length) ul.appendChild(el('li', null, 'No building matches.'));
  S.found = hits.length;
}
function toast(t) { const e = $('#toast'); e.textContent = t; e.style.display = 'block'; clearTimeout(toast.h); toast.h = setTimeout(() => { e.style.display = 'none'; }, 2400); }

function hud(demo) {
  const g = data.summary?.guard || {}, c = $('#chips'); c.replaceChildren();
  const chip = (html) => { const s = el('span', 'chip'); for (const [b, t] of html) { if (b) s.appendChild(el('b', null, t)); else s.appendChild(document.createTextNode(t)); } c.appendChild(s); return s; };
  if (demo) { const s = el('span', 'chip demo', 'DEMO CITY'); c.appendChild(s); }
  chip([[1, (g.tried || 0).toLocaleString()], [0, ' tried']]);
  chip([[1, (g.tested || 0).toLocaleString()], [0, ' tested']]);
  chip([[1, String(g.fdr_pos ?? 0)], [0, ' pass FDR'], [0, ` · placebo ${g.placebo_fdr ?? 0}`]]);
  chip([[0, 'data to '], [1, data.last_day || '–']]);
}

// ------------------------------------------------------------------------------------------------ loop
let frames = 0, acc = 0, slowSecs = 0;
function frame() {
  const dt = Math.min(0.1, clock.getDelta());
  U.uTime.value += dt;
  applyCamera(dt);
  tower.rotation.y += dt * 0.15;
  renderer.render(scene, camera);
  frames++; acc += dt;
  if (acc >= 1) {
    S.fps = Math.round(frames / acc); frames = 0; acc = 0;
    if (quality === 'hq' && S.fps < 40 && !document.hidden) { if (++slowSecs >= 3 && !store.get('dc.q', null)) setQuality('lq', true); } else slowSecs = 0;
  }
  requestAnimationFrame(frame);
}
function setQuality(q, auto) {
  quality = q; S.quality = q; $('#qB').textContent = q === 'hq' ? 'HQ' : 'LQ';
  if (!auto) store.set('dc.q', q);
  renderer.setPixelRatio(q === 'hq' ? Math.min(window.devicePixelRatio || 1, 2) : 1);
  U.uPR.value = renderer.getPixelRatio();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  mirror.visible = q === 'hq';
  flow.geometry.setDrawRange(0, q === 'hq' ? Infinity : 380);
  if (auto) toast('Low-quality mode on for a smoother city (tap HQ to switch back)');
}
function resize() {
  camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
}
function route() {
  const h = decodeURIComponent(location.hash || '');
  if (h === '#top') { fillTop(); openPanel('topP'); }
  else if (h === '#today' || h === '#discoveries') { fillToday(); openPanel('todayP'); }
  else if (h.startsWith('#b=')) openItem(itemById(h.slice(3)));
}

async function main() {
  const { d, demo } = await loadData();
  data = d; S.mode = demo ? 'demo' : 'live';
  L = layout(d);
  makeRenderer();
  build();
  S.buildings = L.items.length; S.quality = quality; $('#qB').textContent = quality === 'hq' ? 'HQ' : 'LQ';
  hud(demo);
  fillTop(); fillToday(); fillAbout();
  const seg = $('#seg');
  for (const [k, t] of [['all', 'All'], ['gold', 'Gold'], ['green', 'Both periods'], ['amber', 'One period'], ['grey', 'Noise']]) {
    const b = el('button', k === segCls ? 'on' : '', t);
    b.addEventListener('click', () => { segCls = k; seg.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); runFind(); });
    seg.appendChild(b);
  }
  $('#q').addEventListener('input', runFind);
  document.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => {
    const id = b.dataset.open; const on = $('#' + id).classList.contains('on');
    if (on) { closeAll(); return; }
    if (id === 'findP') runFind();
    openPanel(id);
  }));
  document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => {
    $('#' + b.dataset.close).classList.remove('on');
    if (b.dataset.close === 'findP') { $('#q').value = ''; segCls = 'all'; runFind(); }
  }));
  $('#flyB').addEventListener('click', () => { if (fly) stopFly(); else { closeAll(); startFly(); } });
  $('#skyB').addEventListener('click', () => { day = !day; store.set('dc.day', day ? '1' : '0'); applySky(); });
  $('#qB').addEventListener('click', () => setQuality(quality === 'hq' ? 'lq' : 'hq'));
  const cv = renderer.domElement;
  cv.addEventListener('pointerdown', onDown); window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp); window.addEventListener('pointercancel', onUp);
  cv.addEventListener('wheel', onWheel, { passive: false });
  window.addEventListener('resize', resize);
  window.addEventListener('hashchange', route);
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAll(); });
  $('#loading').remove();
  requestAnimationFrame(frame);
  route();
  S.ready = true;
  if (window.parent !== window) {
    try {
      const card = await getJSON('./jarvis.json');
      window.parent.postMessage({ jarvis: 1, href: location.href, card }, location.origin);
    } catch (e) { /* no card */ }
  }
}
window.addEventListener('error', (e) => S.errors.push(String(e.message || e)));
main().catch((e) => {
  S.errors.push(String(e && e.message || e));
  const m = el('div', 'err', 'The city could not be drawn on this device (' + (e && e.message ? e.message : 'error') + ').');
  document.body.appendChild(m);
  const l = $('#loading'); if (l) l.remove();
});
