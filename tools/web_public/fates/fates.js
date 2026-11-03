// FATES: the page. Threads of fate spun from a spindle at "today", flowing away into the future.
// Gold threads reach the target (the golden gate above), red ones snap at the floor (the abyss below) with a spark,
// violet ones are still undecided. Data: fates.json, else fixture.json (DEMO). Model and numbers: fates-core.js.
// One draw call for all threads (screen-space glowing ribbons), one for the sparks, one for the dust.
import * as THREE from '../jarvis/three.module.min.js';
import * as C from './fates-core.js';

const O = window.OLYMPUS || null;   // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil
const $ = (id) => document.getElementById(id);
const Q = new URLSearchParams(location.search);
const RM = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : { matches: false, addEventListener() {} };
const COL = { gold: [1.0, 0.76, 0.28], red: [1.0, 0.26, 0.34], violet: [0.62, 0.46, 1.0] };
const BG = 0x07050f;
const Y1 = 3.0;            // the target's height (progress 1)
const LEN = 34;            // how far the future runs into the distance
const S = {
  data: null, demo: false, route: C.parseRoute(location.hash),
  // ?lite=1 / ?full=1 win (tests); else the owner's OLYMPUS choice (Jarvis ⋯ → 3D); auto LITE only when nobody chose
  lite: Q.get('lite') === '1' || (Q.get('full') !== '1' && !!(O && O.lite())), forcedFull: Q.get('full') === '1' || !!(O && O.chosen() && !O.lite()),
  reduced: O ? O.reduced() : RM.matches, threads: [], sel: -1, follow: null, ready: false, webgl: false, errors: [], hud: null, frames: 0,
};
window.__fates = S;                                 // read by tests/test_fates.py

// ------------------------------------------------------------------------------------------------ data
async function loadData() {
  for (const [file, demo] of [['fates.json', false], ['fixture.json', true]]) {
    try {
      const r = await fetch(file, { cache: 'no-cache' });
      if (!r.ok) continue;
      const j = await r.json();
      if (j && j.scenarios) return { j, demo };
    } catch (_) { /* next */ }
  }
  return null;
}

// ------------------------------------------------------------------------------------------------ the HUD and controls
function renderHud() {
  const h = C.hud(S.data, S.route);
  S.hud = h;
  if (!h) return;
  for (const t of h.tiles) {
    const el = document.querySelector(`.tile[data-id="${t.id}"]`);
    if (!el) continue;
    el.querySelector('.l').textContent = t.label;
    el.querySelector('.v').textContent = t.value;
    el.querySelector('.s').textContent = t.sub;
  }
  $('sub').textContent = h.title;
  $('cap').textContent = h.caption + (h.note ? ' · ' + h.note : '');
  $('weak').hidden = !h.weak;
  $('acctsRow').hidden = S.route.scen !== 'money';
  for (const b of document.querySelectorAll('#scen button')) b.setAttribute('aria-selected', String(b.dataset.scen === S.route.scen));
  for (const b of document.querySelectorAll('#period button')) b.setAttribute('aria-selected', String(b.dataset.period === S.route.period));
  for (const b of document.querySelectorAll('#accts button')) b.classList.toggle('on', +b.dataset.n === S.route.accts);
  for (const b of document.querySelectorAll('#span button')) b.classList.toggle('on', b.dataset.span === S.route.span);
}
function go(patch, respin = true) {
  S.route = { ...S.route, ...patch };
  const h = C.routeHash(S.route);
  if (location.hash !== h) history.replaceState(null, '', h);
  renderHud();
  resize();                                         // the HUD's height changes with the scenario: re-centre the scene
  if (respin) { closeFollow(); build(); spin(); }
}
function wire() {
  $('scen').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) go({ scen: b.dataset.scen }); });
  $('period').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) go({ period: b.dataset.period }); });
  $('accts').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) go({ accts: +b.dataset.n }); });
  $('span').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) go({ span: b.dataset.span }, false); });
  $('spin').addEventListener('click', () => { closeFollow(); reseed(); build(); spin(); });
  $('fClose').addEventListener('click', closeFollow);
  window.addEventListener('hashchange', () => { const r = C.parseRoute(location.hash); go({ scen: r.scen, period: r.period, accts: r.accts }); });
  RM.addEventListener && RM.addEventListener('change', (e) => { S.reduced = e.matches; spin(); });
}

// ------------------------------------------------------------------------------------------------ the scene
let R, scene, cam, clock0 = 0, H = 60;
const G = {};                                      // meshes of the current scenario
S.probe = () => ({ k: G.threads ? G.threads.material.uniforms.uTime.value : null, calls: R ? R.info.render.calls : 0,
  tris: R ? R.info.render.triangles : 0, verts: G.threads ? G.threads.geometry.attributes.position.count : 0 });
let seedBase = 1;
const rnd = (i, s = 0) => { const x = Math.sin((i + 1) * 127.1 + (s + seedBase) * 311.7) * 43758.5453; return x - Math.floor(x); };
function reseed() { seedBase = (seedBase * 9301 + 49297) % 233280 || 7; }

const FOG = `
  uniform float uFog;
  float fogOf(vec4 mv) { float d = -mv.z; return 1.0 - exp(-uFog * uFog * d * d); }`;

function initGL() {
  const canvas = $('scene');
  try {
    R = new THREE.WebGLRenderer({ canvas, antialias: !S.lite, alpha: false, powerPreference: 'high-performance' });
  } catch (e) {
    $('nogl').hidden = false;
    canvas.hidden = true;
    return false;
  }
  R.setClearColor(BG, 1);
  O?.track(R);
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(BG, 0.045);
  cam = new THREE.PerspectiveCamera(56, 1, 0.1, 120);
  resize();
  window.addEventListener('resize', resize);
  makeStatic();
  canvas.addEventListener('pointerup', onTap);
  S.webgl = true;
  return true;
}
function resize() {
  if (!R) return;
  const w = window.innerWidth, h = window.innerHeight;
  R.setPixelRatio(Math.min(window.devicePixelRatio || 1, S.lite ? 1.25 : 2));
  O?.mode(S.lite);
  R.setSize(w, h, false);
  cam.aspect = w / h;
  // keep the vanishing point in the free band between the HUD (top) and the controls (bottom)
  const top = ($('cap').getBoundingClientRect().bottom || h * 0.35) + 8, bot = h - ($('spin').getBoundingClientRect().top || h * 0.92);
  const shift = Math.max(-h * 0.3, Math.min(h * 0.3, (top - bot) / 2));
  cam.setViewOffset(w, h, 0, -shift, w, h);
  cam.updateProjectionMatrix();
}

// static set pieces: the abyss, the golden gate, the spindle, the dust
function makeStatic() {
  const abyss = new THREE.Mesh(new THREE.PlaneGeometry(60, 80, 1, 1), new THREE.ShaderMaterial({
    uniforms: { uT: { value: 0 }, uFog: { value: 0.045 } },
    vertexShader: `varying vec3 vW; varying float vF; ${FOG}
      void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vec4 mv = viewMatrix * w; vF = fogOf(mv); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `varying vec3 vW; varying float vF; uniform float uT;
      float line(float x, float w) { float f = abs(fract(x) - 0.5); return smoothstep(w, 0.0, 0.5 - f); }
      void main() {
        float g = max(line(vW.x * 0.5, 0.04), line((vW.z - uT * 0.6) * 0.5, 0.04));
        float glow = exp(-length(vW.xz * vec2(0.12, 0.05)));
        vec3 c = vec3(0.05, 0.0, 0.03) + vec3(0.55, 0.06, 0.12) * g * 0.35 * (0.4 + glow) + vec3(0.28, 0.02, 0.08) * glow * 0.5;
        c = mix(c, vec3(0.027, 0.02, 0.059), vF);
        gl_FragColor = vec4(c, 1.0);
      }`,
    depthWrite: true,
  }));
  abyss.rotation.x = -Math.PI / 2;
  abyss.position.set(0, 0, -LEN / 2 + 4);
  abyss.renderOrder = -2;
  scene.add(abyss);
  G.abyss = abyss;

  const gate = new THREE.Mesh(new THREE.PlaneGeometry(60, 80, 1, 1), new THREE.ShaderMaterial({
    uniforms: { uT: { value: 0 }, uFog: { value: 0.045 } },
    vertexShader: `varying vec3 vW; varying float vF; ${FOG}
      void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vec4 mv = viewMatrix * w; vF = fogOf(mv); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `varying vec3 vW; varying float vF; uniform float uT;
      float line(float x, float w) { float f = abs(fract(x) - 0.5); return smoothstep(w, 0.0, 0.5 - f); }
      void main() {
        float g = max(line(vW.x * 0.35 + sin(vW.z * 0.15 + uT) * 0.1, 0.03), line(vW.z * 0.35 + uT * 0.25, 0.03));
        float shimmer = 0.5 + 0.5 * sin(vW.x * 0.6 + vW.z * 0.4 + uT * 1.7);
        float a = (0.045 + g * 0.42 * (0.55 + 0.45 * shimmer)) * (1.0 - vF);
        gl_FragColor = vec4(vec3(1.0, 0.78, 0.32) * a, 1.0);
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  }));
  gate.rotation.x = -Math.PI / 2;
  gate.position.set(0, Y1, -LEN / 2 + 4);
  scene.add(gate);
  G.gate = gate;
  // the gate's rim: a golden line across the near edge, so the target reads as a door
  const rim = new THREE.Mesh(new THREE.BoxGeometry(12, 0.03, 0.03), new THREE.MeshBasicMaterial({ color: 0xffd36a, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false }));
  rim.position.set(0, Y1, -1.6);
  scene.add(rim);
  G.rim = rim;
  const floorRim = new THREE.Mesh(new THREE.BoxGeometry(12, 0.025, 0.025), new THREE.MeshBasicMaterial({ color: 0xff4d64, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending, depthWrite: false }));
  floorRim.position.set(0, 0.01, -1.6);
  scene.add(floorRim);
  G.floorRim = floorRim;

  // the spindle: a glowing distaff at today, a slowly turning whorl around it
  const sp = new THREE.Group();
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.5, 12), new THREE.MeshBasicMaterial({ color: 0xffe2a0, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }));
  const whorl = new THREE.Mesh(new THREE.TorusGeometry(0.26, 0.022, 8, 48), new THREE.MeshBasicMaterial({ color: 0xc9a8ff, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }));
  whorl.rotation.x = Math.PI / 2;
  const whorl2 = whorl.clone();
  whorl2.scale.setScalar(1.6);
  whorl2.material = whorl.material.clone();
  whorl2.material.opacity = 0.35;
  shaft.position.y = 0.4;                          // the distaff rises from the whorl
  sp.add(shaft, whorl, whorl2);
  scene.add(sp);
  G.spindle = sp; G.whorl = whorl; G.whorl2 = whorl2;

  G.labels = new THREE.Group();
  scene.add(G.labels);
  makeDust();
}

function label(text, color, h = 0.32) {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  const fs = 64;
  ctx.font = `700 ${fs}px Orbitron, Rajdhani, system-ui, sans-serif`;
  const w = Math.ceil(ctx.measureText(text).width) + 40;
  c.width = w; c.height = fs + 32;
  ctx.font = `700 ${fs}px Orbitron, Rajdhani, system-ui, sans-serif`;
  ctx.textBaseline = 'middle';
  ctx.shadowColor = color; ctx.shadowBlur = 18;
  ctx.fillStyle = color;
  ctx.fillText(text, 20, c.height / 2);
  const tex = new THREE.CanvasTexture(c);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending }));
  s.scale.set(h * w / c.height, h, 1);
  return s;
}

function makeDust() {
  const n = S.lite ? 0 : 700;
  if (G.dust) { scene.remove(G.dust); G.dust.geometry.dispose(); G.dust = null; }
  if (!n) return;
  const pos = new Float32Array(n * 3), seed = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 18; pos[i * 3 + 1] = Math.random() * Y1 * 1.4 - 0.4; pos[i * 3 + 2] = 4 - Math.random() * LEN;
    seed[i] = Math.random();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
  G.dust = new THREE.Points(g, new THREE.ShaderMaterial({
    uniforms: { uT: { value: 0 }, uPx: { value: 1 }, uFog: { value: 0.045 }, uMove: { value: 1 } },
    vertexShader: `attribute float aSeed; uniform float uT, uPx, uMove; varying float vA; varying vec3 vC; ${FOG}
      void main() { vec3 p = position; float t = uT * uMove;
        p.y += mod(t * (0.05 + aSeed * 0.08) + aSeed * 7.0, 4.6) - 1.0; p.x += sin(t * 0.3 + aSeed * 40.0) * 0.25;
        vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
        gl_PointSize = uPx * (1.0 + aSeed * 2.0) * 18.0 / max(1.0, -mv.z);
        vA = (0.25 + 0.35 * sin(t * 1.3 + aSeed * 30.0) * sin(t * 1.3 + aSeed * 30.0)) * (1.0 - fogOf(mv));
        vC = mix(vec3(0.7, 0.55, 1.0), vec3(1.0, 0.82, 0.45), step(0.7, aSeed)); }`,
    fragmentShader: `varying float vA; varying vec3 vC; void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d) * vA; gl_FragColor = vec4(vC * a, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  scene.add(G.dust);
}

// ------------------------------------------------------------------------------------------------ the scenario's threads
let MAP = null;                                    // world mapping of the current scenario
function mapping(s) {
  if (s.kind === 'eval') {
    const yOf = (p) => Math.min(1.12, p) * Y1;
    return { H: s.horizon, tPow: 0.62, yOf, gateY: Y1, abyssY: 0, gateText: `TARGET ${C.fmtUsd(s.rules.target, true)}`, abyssText: 'FLOOR', spread: 4.6 };
  }
  const b = s.books[String(S.route.accts)];
  const bandTop = s.bands[String(S.route.accts)].v[4];
  const top = Math.max(s.goal * 1.15, bandTop[bandTop.length - 1] * 1.05, 1);
  const yOf = (v) => 0.55 + (v / top) * (Y1 - 0.55);         // $0 a little above the floor, so the spindle sits higher
  return { H: s.horizon, tPow: 0.85, yOf, gateY: yOf(s.goal), abyssY: null, gateText: C.fmtK(s.goal), abyssText: '$0', spread: 4.8, book: b };
}
const zOf = (k) => 1.2 - LEN * Math.pow(Math.max(0, k) / MAP.H, MAP.tPow);
function xOf(id, k) {
  const s = Math.pow(Math.max(0, k) / MAP.H, 0.4);
  const a = (rnd(id) - 0.5) * 2, b = rnd(id, 3) - 0.5;
  return (a * MAP.spread + b * 0.6 * Math.sin(k * 0.25 + id)) * s;
}
function worldPts(th) {
  const out = th.pts.map(([k, v]) => new THREE.Vector3(xOf(th.id, k), MAP.yOf(v), zOf(k)));
  const last = th.pts[th.pts.length - 1];
  if (S.route.scen !== 'money' && th.o !== 'o') {                  // the end: into the abyss, or up through the gate
    const k = last[0] + 0.5, up = th.o === 'p';
    out.push(new THREE.Vector3(xOf(th.id, k), up ? Y1 * 1.16 : -0.6, zOf(k)));
  }
  return out;
}

function build() {
  if (!S.webgl) { S.threads = currentThreads(); return; }
  for (const k of ['threads', 'sparks', 'bead']) if (G[k]) { scene.remove(G[k]); G[k].geometry.dispose(); G[k].material.dispose(); G[k] = null; }
  G.labels.clear();
  const s = S.data.scenarios[C.scenKey(S.route)];
  MAP = mapping(s);
  H = MAP.H;
  const all = currentThreads();
  const cap = S.lite ? 160 : all.length;
  S.threads = all.slice(0, cap);
  // ribbons: 2 vertices a point, one draw call
  let nv = 0, ni = 0;
  const W = S.threads.map((th) => { const p = worldPts(th); nv += p.length * 2; ni += (p.length - 1) * 6; return p; });
  const pos = new Float32Array(nv * 3), prv = new Float32Array(nv * 3), nxt = new Float32Array(nv * 3);
  const side = new Float32Array(nv), kk = new Float32Array(nv), id = new Float32Array(nv), col = new Float32Array(nv * 3), end = new Float32Array(nv);
  const idx = new Uint32Array(ni);
  let v = 0, ii = 0;
  S.threads.forEach((th, t) => {
    const P = W[t], c = COL[th.color] || COL.violet;
    const ks = th.pts.map((p) => p[0]);
    if (P.length > ks.length) ks.push(ks[ks.length - 1] + 0.5);
    const kEnd = ks[ks.length - 1];
    const base = v;
    for (let i = 0; i < P.length; i++) {
      const a = P[Math.max(0, i - 1)], b = P[i], n = P[Math.min(P.length - 1, i + 1)];
      for (const sd of [-1, 1]) {
        pos.set([b.x, b.y, b.z], v * 3); prv.set([a.x, a.y, a.z], v * 3); nxt.set([n.x, n.y, n.z], v * 3);
        side[v] = sd; kk[v] = ks[i]; id[v] = t; col.set(c, v * 3); end[v] = kEnd;
        v++;
      }
      if (i < P.length - 1) { const q = base + i * 2; idx.set([q, q + 1, q + 2, q + 1, q + 3, q + 2], ii); ii += 6; }
    }
    th.world = P; th.ks = ks;
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aPrev', new THREE.BufferAttribute(prv, 3));
  g.setAttribute('aNext', new THREE.BufferAttribute(nxt, 3));
  g.setAttribute('aSide', new THREE.BufferAttribute(side, 1));
  g.setAttribute('aK', new THREE.BufferAttribute(kk, 1));
  g.setAttribute('aId', new THREE.BufferAttribute(id, 1));
  g.setAttribute('aCol', new THREE.BufferAttribute(col, 3));
  g.setAttribute('aEnd', new THREE.BufferAttribute(end, 1));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  const gain = Math.min(0.5, 3.4 / Math.sqrt(S.threads.length));
  G.threads = new THREE.Mesh(g, new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uAspect: { value: 1 }, uPx: { value: 0.003 }, uW: { value: S.lite ? 2.0 : 2.4 }, uSel: { value: -1 },
      uGain: { value: gain }, uFog: { value: 0.045 } },
    vertexShader: `attribute vec3 aPrev, aNext, aCol; attribute float aSide, aK, aId, aEnd;
      uniform float uAspect, uPx, uW, uSel; varying float vSide, vK, vEnd, vSel, vF; varying vec3 vCol; ${FOG}
      vec2 scr(vec4 c) { vec2 p = c.xy / c.w; p.x *= uAspect; return p; }
      void main() {
        mat4 m = projectionMatrix * modelViewMatrix;
        vec4 c = m * vec4(position, 1.0); vec2 sc = scr(c), sp = scr(m * vec4(aPrev, 1.0)), sn = scr(m * vec4(aNext, 1.0));
        vec2 d1 = sc - sp, d2 = sn - sc;
        vec2 dir = length(d1) < 1e-6 ? d2 : length(d2) < 1e-6 ? d1 : normalize(d1) + normalize(d2);
        dir = length(dir) < 1e-6 ? vec2(1.0, 0.0) : normalize(dir);
        vec2 nrm = vec2(-dir.y, dir.x); nrm.x /= uAspect;
        float sel = uSel < -0.5 ? 0.0 : (abs(aId - uSel) < 0.5 ? 1.0 : -1.0);
        float w = uW * (sel > 0.5 ? 2.6 : 1.0);
        c.xy += nrm * aSide * w * uPx * c.w;
        gl_Position = c;
        vSide = aSide; vK = aK; vEnd = aEnd; vSel = sel; vCol = aCol; vF = fogOf(modelViewMatrix * vec4(position, 1.0));
      }`,
    fragmentShader: `uniform float uTime, uGain; varying float vSide, vK, vEnd, vSel, vF; varying vec3 vCol;
      void main() {
        if (vK > uTime) discard;
        float core = exp(-vSide * vSide * 4.5);
        float head = uTime < vEnd + 0.4 ? exp(-(uTime - vK) * 1.8) : 0.0;
        float dim = vSel < -0.5 ? 0.12 : vSel > 0.5 ? 2.2 : 1.0;
        vec3 col = vCol * (0.75 + 2.2 * head) + vec3(1.0) * pow(core, 8.0) * (0.25 + head);
        float a = core * uGain * dim * (1.0 - vF * 0.8);
        gl_FragColor = vec4(col * a, 1.0);
      }`,
    transparent: true, depthWrite: false, depthTest: true, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  }));
  G.threads.frustumCulled = false;
  scene.add(G.threads);
  makeSparks();
  makeBead();
  // set pieces for this scenario
  const startY = S.threads.length ? MAP.yOf(S.threads[0].pts[0][1]) : 0;
  G.spindle.position.set(0, startY, zOf(0) + 0.05);
  G.gate.position.y = MAP.gateY; G.rim.position.y = MAP.gateY;
  const minY = Math.min(0, ...W.map((p) => Math.min(...p.map((q) => q.y))));
  const ay = MAP.abyssY != null ? MAP.abyssY : minY - 0.08;
  G.abyss.position.y = ay; G.floorRim.position.y = ay + 0.01;
  const gl = label(MAP.gateText, '#ffd36a', 0.3); gl.position.set(-1.75 + gl.scale.x / 2, MAP.gateY + 0.2, -1.6); G.labels.add(gl);
  const al = label(MAP.abyssText, '#ff5a6e', 0.26); al.position.set(-1.75 + al.scale.x / 2, (MAP.abyssY != null ? ay : MAP.yOf(0)) + 0.2, -1.6); G.labels.add(al);
  const tl = label('TODAY', '#e5d6ff', 0.17); tl.position.set(0, startY - 0.42, zOf(0)); G.labels.add(tl);
  const far = label(S.route.scen === 'money' ? '12 MONTHS' : `DAY ${MAP.H}`, '#9b8cc4', 0.5); far.position.set(0, MAP.gateY * 0.5, zOf(MAP.H) - 1); G.labels.add(far);
}
function currentThreads() {
  const s = S.data.scenarios[C.scenKey(S.route)];
  return s.kind === 'eval' ? C.evalThreads(s) : C.moneyThreads(s, S.route.accts);
}

// sparks: a burst where a thread snaps (red, falling into the abyss) or passes (gold, rising through the gate)
const DUR = () => (S.route.scen === 'money' ? 6.5 : 5.0);
const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 2.2);
function kAt(sec) { return MAP.H * ease(sec / DUR()); }
function secAt(k) { let lo = 0, hi = DUR(); for (let i = 0; i < 30; i++) { const m = (lo + hi) / 2; if (kAt(m) < k) lo = m; else hi = m; } return hi; }
function makeSparks() {
  const per = S.lite ? 4 : 12, list = [];
  for (const th of S.threads) {
    if (S.route.scen === 'money') {
      for (const e of th.ev) {
        if (e.code !== C.EV.PAY && e.code !== C.EV.LOST && e.code !== C.EV.DEAD) continue;
        if (rnd(th.id, e.k) > (S.lite ? 0.25 : 0.6)) continue;
        const k = e.k + 1, i = th.ks.findIndex((x) => x >= k);
        const p = th.world[Math.max(0, i)];
        list.push([p, k, e.code === C.EV.PAY ? 'gold' : 'red']);
      }
    } else if (th.o !== 'o') {
      const p = th.world[th.pts.length - 1];
      list.push([p, th.pts[th.pts.length - 1][0], th.color]);
    }
  }
  const n = list.length * per;
  const o = new Float32Array(n * 3), vel = new Float32Array(n * 3), birth = new Float32Array(n), col = new Float32Array(n * 3), sd = new Float32Array(n);
  let j = 0;
  list.forEach(([p, k, c], b) => {
    const bs = secAt(k), up = c === 'gold';
    for (let i = 0; i < per; i++, j++) {
      const th = rnd(b * 31 + i, 1) * Math.PI * 2, r = 0.4 + rnd(b * 17 + i, 2) * 1.1;
      o.set([p.x, p.y, p.z], j * 3);
      vel.set([Math.cos(th) * r * 0.6, (up ? 1.4 : 0.9) * (0.5 + rnd(b + i, 5)), Math.sin(th) * r * 0.6], j * 3);
      birth[j] = bs; col.set(COL[c] || COL.violet, j * 3); sd[j] = rnd(b * 7 + i, 9);
    }
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(o, 3));
  g.setAttribute('aVel', new THREE.BufferAttribute(vel, 3));
  g.setAttribute('aBirth', new THREE.BufferAttribute(birth, 1));
  g.setAttribute('aCol', new THREE.BufferAttribute(col, 3));
  g.setAttribute('aSeed', new THREE.BufferAttribute(sd, 1));
  G.sparks = new THREE.Points(g, new THREE.ShaderMaterial({
    uniforms: { uClock: { value: 0 }, uPx: { value: 1 }, uFog: { value: 0.045 }, uOn: { value: 1 } },
    vertexShader: `attribute vec3 aVel, aCol; attribute float aBirth, aSeed; uniform float uClock, uPx, uOn; varying vec3 vC; varying float vA; ${FOG}
      void main() { float age = uClock - aBirth; float life = 0.9 + aSeed * 0.7;
        if (uOn < 0.5 || age < 0.0 || age > life) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; vA = 0.0; return; }
        float up = aCol.g > 0.5 ? 1.0 : -1.0;
        vec3 p = position + aVel * age * vec3(1.0, up, 1.0) + vec3(0.0, -up * 1.2 * age * age * (up > 0.0 ? 0.2 : 1.0), 0.0);
        vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
        float f = 1.0 - age / life;
        gl_PointSize = uPx * (2.0 + 4.0 * f) * 14.0 / max(1.0, -mv.z);
        vC = aCol; vA = f * f * (1.0 - fogOf(mv)); }`,
    fragmentShader: `varying vec3 vC; varying float vA; void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d) * vA;
        gl_FragColor = vec4((vC + vec3(0.6) * smoothstep(0.25, 0.0, d)) * a, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  G.sparks.frustumCulled = false;
  scene.add(G.sparks);
}
function makeBead() {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
  G.bead = new THREE.Points(g, new THREE.ShaderMaterial({
    uniforms: { uPx: { value: 1 }, uOn: { value: 0 }, uC: { value: new THREE.Color(1, 1, 1) } },
    vertexShader: `uniform float uPx, uOn; void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv; gl_PointSize = uOn * uPx * 220.0 / max(1.0, -mv.z); }`,
    fragmentShader: `uniform vec3 uC; void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d); gl_FragColor = vec4((uC + vec3(0.8) * smoothstep(0.18, 0.0, d)) * a, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  G.bead.frustumCulled = false;
  scene.add(G.bead);
}

// ------------------------------------------------------------------------------------------------ animation
function spin() {
  clock0 = performance.now();
  S.spinning = true;
  S.perf = [];
  if (S.reduced) clock0 -= 1e6;
}
function frame(now) {
  requestAnimationFrame(frame);
  if (!S.webgl || !G.threads || (O ? O.hidden() : document.hidden)) return;     // hidden tab: no frame (the battery)
  const sec = (now - clock0) / 1000, tg = now / 1000;
  const k = S.reduced ? MAP.H + 1 : Math.min(MAP.H + 1, kAt(sec) + (sec >= DUR() ? 1 : 0));
  const px = R.getPixelRatio();
  const vh = R.domElement.height;
  const U = G.threads.material.uniforms;
  U.uTime.value = k; U.uAspect.value = cam.aspect; U.uPx.value = 2 / Math.max(1, vh) * px; U.uSel.value = S.sel;
  G.sparks.material.uniforms.uClock.value = sec; G.sparks.material.uniforms.uPx.value = px; G.sparks.material.uniforms.uOn.value = S.reduced ? 0 : 1;
  G.abyss.material.uniforms.uT.value = S.reduced ? 0 : tg; G.gate.material.uniforms.uT.value = S.reduced ? 0 : tg;
  if (G.dust) { G.dust.material.uniforms.uT.value = tg; G.dust.material.uniforms.uPx.value = px; G.dust.material.uniforms.uMove.value = S.reduced ? 0 : 1; }
  if (!S.reduced) { G.whorl.rotation.z = tg * 1.4; G.whorl2.rotation.z = -tg * 0.7; G.spindle.rotation.y = tg * 0.5; }
  const sway = S.reduced ? 0 : Math.sin(tg * 0.17) * 0.45;
  cam.position.set(sway, 1.55 + (S.reduced ? 0 : Math.sin(tg * 0.23) * 0.1), 7.4);
  cam.lookAt(sway * 0.2, 1.45, -14);
  // the followed future: a bead travels along it day by day
  if (S.follow) stepFollow(now);
  R.render(scene, cam);
  S.frames++;
  // auto LITE: a slow first spin on this device -> fewer threads, no dust, a smaller canvas
  if (S.spinning && !S.lite && !S.forcedFull && !S.reduced) {
    S.perf.push(now);
    if (S.perf.length === 90) {
      const dt = (S.perf[89] - S.perf[30]) / 59;
      if (dt > 21) { S.lite = true; $('lite').hidden = false; resize(); makeDust(); build(); spin(); return; }
    }
  }
  if (sec > DUR() + 2) S.spinning = false;
}

// ------------------------------------------------------------------------------------------------ tap a thread, follow it
function onTap(e) {
  if (!S.webgl || !S.threads.length) return;
  const rect = R.domElement.getBoundingClientRect(), x = e.clientX - rect.left, y = e.clientY - rect.top;
  const kNow = G.threads.material.uniforms.uTime.value;
  const v = new THREE.Vector3();
  let best = -1, bd = 26 * 26;
  for (const th of S.threads) {
    let px = null;
    for (let i = 0; i < th.world.length; i++) {
      if (th.ks[i] > kNow + 0.01) break;
      v.copy(th.world[i]).project(cam);
      if (v.z > 1) { px = null; continue; }
      const sx = (v.x + 1) / 2 * rect.width, sy = (1 - v.y) / 2 * rect.height;
      if (px) {
        const dx = sx - px.x, dy = sy - px.y, L = dx * dx + dy * dy;
        const t = L > 0 ? Math.max(0, Math.min(1, ((x - px.x) * dx + (y - px.y) * dy) / L)) : 0;
        const ex = px.x + t * dx - x, ey = px.y + t * dy - y, d = ex * ex + ey * ey;
        if (d < bd) { bd = d; best = th.id; }
      }
      px = { x: sx, y: sy };
    }
  }
  if (best >= 0) openFollow(best);
  else if (S.sel >= 0) closeFollow();
}
function openFollow(i) {
  const th = S.threads.find((t) => t.id === i);
  if (!th) return;
  const s = S.data.scenarios[C.scenKey(S.route)];
  const f = s.kind === 'eval' ? C.followEval(S.data, s, th) : C.followMoney(S.data, s, th);
  S.sel = i;
  S.follow = { th, f, t0: performance.now(), row: -1 };
  $('fTitle').textContent = f.title;
  $('fEnd').textContent = f.end;
  const ol = $('fRows');
  ol.textContent = '';
  for (const r of f.rows) {
    const li = document.createElement('li');
    li.className = r.tone || '';
    li.dataset.k = r.k;
    const d = document.createElement('span'); d.className = 'd'; d.textContent = r.text;
    const m = document.createElement('span'); m.className = 'm'; m.textContent = r.move;
    const b = document.createElement('span'); b.className = 'b'; b.textContent = r.bal;
    if (r.room) { const sm = document.createElement('small'); sm.textContent = `room ${r.room}`; b.appendChild(sm); }
    li.append(d, m, b);
    ol.appendChild(li);
  }
  const box = $('follow');
  box.className = 'follow ' + f.tone;
  box.hidden = false;
  $('hint').hidden = true;
  if (G.bead) { G.bead.material.uniforms.uOn.value = 1; G.bead.material.uniforms.uC.value.setRGB(...(COL[th.color] || COL.violet)); }
}
function stepFollow(now) {
  const F = S.follow, th = F.th;
  const rate = S.route.scen === 'money' ? 24 : 5;                 // sessions a second
  const kEnd = th.pts[th.pts.length - 1][0];
  const k = S.reduced ? kEnd : Math.min(kEnd, (now - F.t0) / 1000 * rate);
  // position along the thread at session k
  let i = 0;
  while (i < th.ks.length - 1 && th.ks[i + 1] <= k) i++;
  const a = th.world[i], b = th.world[Math.min(i + 1, th.world.length - 1)];
  const ka = th.ks[i], kb = th.ks[Math.min(i + 1, th.ks.length - 1)];
  const t = kb > ka ? Math.min(1, (k - ka) / (kb - ka)) : 0;
  const p = G.bead.geometry.attributes.position;
  p.setXYZ(0, a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t);
  p.needsUpdate = true;
  G.bead.material.uniforms.uPx.value = R.getPixelRatio();
  // highlight the day in the list
  const rows = F.f.rows;
  let r = -1;
  for (let j = 0; j < rows.length; j++) if (rows[j].k <= k - (S.route.scen === 'money' ? 0 : 1)) r = j;
  if (r !== F.row) {
    F.row = r;
    const lis = $('fRows').children;
    for (let j = 0; j < lis.length; j++) lis[j].classList.toggle('now', j === r);
    if (r >= 0 && lis[r] && !S.reduced) lis[r].scrollIntoView({ block: 'nearest' });
  }
}
// where thread `id` is on screen (CSS px) at its i-th point, for the page test's tap
S.pointOf = (id, i = 2) => {
  const th = S.threads.find((t) => t.id === id);
  if (!th || !th.world) return null;
  const v = th.world[Math.min(i, th.world.length - 1)].clone().project(cam), rect = R.domElement.getBoundingClientRect();
  return { x: rect.left + (v.x + 1) / 2 * rect.width, y: rect.top + (1 - v.y) / 2 * rect.height };
};
function closeFollow() {
  S.sel = -1;
  S.follow = null;
  $('follow').hidden = true;
  $('hint').hidden = false;
  if (G.bead) G.bead.material.uniforms.uOn.value = 0;
}

// ------------------------------------------------------------------------------------------------ Jarvis's live card
function postCard() {
  try {
    const card = C.jarvisCard(S.data);
    if (card && !S.demo && window.parent !== window) window.parent.postMessage({ jarvis: 1, href: location.href, card }, 'https://demetrades2000-coder.github.io');
  } catch (_) { /* outside Jarvis */ }
}

// ------------------------------------------------------------------------------------------------ start
window.addEventListener('error', (e) => S.errors.push(String(e.message || e)));
(async function main() {
  wire();
  const got = await loadData();
  if (!got) { $('sub').textContent = 'No data yet: run python -X utf8 -m tools.fates.build'; S.ready = true; O?.fail('no data yet'); return; }
  S.data = got.j; S.demo = got.demo;
  $('demo').hidden = !S.demo;
  if (S.lite) $('lite').hidden = false;
  renderHud();
  if (initGL()) {
    build();
    spin();
    requestAnimationFrame(frame);
  } else {
    S.threads = currentThreads();
    O?.ready();                                    // no 3D on this device: the numbers are the page
  }
  postCard();
  S.ready = true;
})();
