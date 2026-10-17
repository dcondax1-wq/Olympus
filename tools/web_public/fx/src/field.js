// The Liquidity Field: the living 3D background behind every page.
//  - a tilted particle galaxy with spiral arms and differential rotation (all motion on the GPU)
//  - space dust drifting toward the camera, a scrolling neon grid floor, soft nebula clouds
//  - a dashed cyan liquidity ring; every few seconds a comet sweeps through it and bursts (the bot's signature move)
// Mood (killzone, cold streak, P&L) changes speed and colour; page changes trigger a short warp; new data a pulse.
// Scenes (setScene / FX.scene): every page has its own palette, galaxy orientation and spin, blended in over ~1.5 s.
// Ripples (ripple / FX.ripple): a tap on empty background sends a wave through the grid floor or the galaxy disc,
// wherever the tap ray lands. Flinging the page scrolls the dust and the grid faster (a short hyperspace streak).
import { THREE, View, Q, theme, par, glowTexture, POINT_FRAG, rng, count } from './core.js';
import { Aura } from './aura.js';

const GALAXY_V = `attribute float aR; attribute float aT; attribute float aY; attribute float aS; attribute float aSeed; attribute vec3 aCol;
uniform float uTime; uniform float uSpin; uniform float uPix; uniform float uBright; uniform vec3 uTint; uniform float uTintK; uniform float uPulse; uniform float uPulseR;
uniform vec3 uScene; uniform float uSceneK; uniform vec4 uGRip; uniform float uRot;
varying vec3 vColor; varying float vAlpha;
void main(){
  float w = uSpin * 0.55 / (0.7 + aR * 0.2);
  float th = aT + uRot * w;
  vec3 p = vec3(cos(th) * aR, aY, sin(th) * aR);
  vec2 dq = p.xz - uGRip.xy; float dd = length(dq);
  float rp = uGRip.w * exp(-pow((dd - uGRip.z * 5.5) * 1.1, 2.0)) * clamp(1.0 - uGRip.z / 2.6, 0.0, 1.0);
  p.xz += dq / max(dd, 0.001) * rp * 0.45; p.y += rp * 0.2;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float tw = 0.72 + 0.28 * sin(uTime * (0.9 + aSeed * 2.2) + aSeed * 40.0);
  float pr = exp(-pow((aR - uPulseR) * 1.3, 2.0)) * uPulse;
  gl_PointSize = clamp(aS * uPix * tw * (1.0 + pr + rp * 1.3) / -mv.z, 0.0, 48.0);
  gl_Position = projectionMatrix * mv;
  vColor = mix(mix(aCol, uScene * dot(aCol, vec3(0.45)) * 2.2, uSceneK), uTint, uTintK) * uBright * (1.0 + pr * 1.6 + rp * 2.2);
  vAlpha = smoothstep(0.6, 3.0, -mv.z) * (0.5 + 0.5 * tw);
}`;
const DUST_V = `attribute vec3 aP; attribute float aS; attribute float aSeed;
uniform float uTime; uniform float uDrift; uniform float uPix; uniform vec3 uCol; uniform float uBright;
varying vec3 vColor; varying float vAlpha;
void main(){
  vec3 p = aP; p.z = mod(aP.z + uDrift + 40.0, 46.0) - 40.0;
  p.x += sin(uTime * 0.15 + aSeed * 30.0) * 0.4; p.y += cos(uTime * 0.12 + aSeed * 20.0) * 0.3;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp(aS * uPix / -mv.z, 0.0, 26.0);
  gl_Position = projectionMatrix * mv;
  vColor = uCol * uBright * (0.6 + 0.4 * sin(uTime * 1.7 + aSeed * 50.0));
  vAlpha = smoothstep(0.3, 2.5, -mv.z) * smoothstep(40.0, 18.0, -mv.z);
}`;
const BURST_V = `attribute vec3 aDir; attribute float aS; attribute float aSeed;
uniform float uAge; uniform vec3 uO; uniform float uPix; uniform vec3 uCol;
varying vec3 vColor; varying float vAlpha;
void main(){
  float a = uAge; vec3 p = uO + aDir * (a * 2.6) * (1.0 - min(a, 1.6) * 0.28) + vec3(0.0, -0.9 * a * a, 0.0);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float life = clamp(1.0 - a / (1.0 + aSeed * 0.9), 0.0, 1.0);
  gl_PointSize = clamp(aS * uPix * (0.4 + life) / -mv.z, 0.0, 40.0);
  gl_Position = projectionMatrix * mv;
  vColor = mix(vec3(1.0), uCol, clamp(a * 1.5, 0.0, 1.0)) * 1.4; vAlpha = life * life;
}`;
const TRAIL_V = `attribute float aI; uniform float uPix; uniform vec3 uCol; uniform float uOn;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); float k = 1.0 - aI;
  gl_PointSize = clamp((2.0 + 9.0 * k * k) * uPix / -mv.z, 0.0, 40.0); gl_Position = projectionMatrix * mv;
  vColor = mix(uCol, vec3(1.0), k * k) * 1.3; vAlpha = k * uOn; }`;
const RING_V = `attribute float aA; uniform float uR; uniform float uPix; uniform vec3 uCol; uniform float uFlash; uniform float uTime;
varying vec3 vColor; varying float vAlpha;
void main(){ vec3 p = vec3(cos(aA) * uR, 0.0, sin(aA) * uR); vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float dash = step(0.45, fract(aA * 18.0 / 6.2831853 * 6.0 + uTime * 0.25));
  gl_PointSize = clamp((2.2 + uFlash * 3.0) * uPix / -mv.z, 0.0, 30.0) * dash; gl_Position = projectionMatrix * mv;
  vColor = uCol * (1.0 + uFlash * 2.5); vAlpha = (0.55 + uFlash * 0.45) * smoothstep(0.6, 3.0, -mv.z); }`;
const GRID_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const GRID_F = `uniform float uTime; uniform float uScroll; uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uCam; uniform float uBright; uniform vec4 uRip[4]; varying vec3 vW;
void main(){
  vec2 c = vW.xz * 0.55 + vec2(0.0, uScroll);
  vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c);
  float l = 1.0 - min(min(g.x, g.y), 1.0);
  float glow = exp(-min(g.x, g.y) * 0.35) * 0.35;
  float d = length(vW.xz - uCam.xz);
  float fade = exp(-d * 0.055) * smoothstep(60.0, 8.0, d);
  vec3 col = mix(uC1, uC2, smoothstep(4.0, 30.0, d));
  float rip = 0.0;
  for (int i = 0; i < 4; i++) {
    vec4 r = uRip[i];
    if (r.w > 0.0) { float e = length(vW.xz - r.xy) - r.z * 9.0; rip += exp(-e * e * 1.6) * r.w * clamp(1.0 - r.z / 2.2, 0.0, 1.0); }
  }
  gl_FragColor = vec4(col * ((l * 0.9 + glow) * (1.0 + rip * 2.6) + rip * 0.22) * fade * uBright, 1.0);
}`;
// page scenes: palette, galaxy orientation / place, spin and brightness (aliases map every page id of both dashboards)
const SCENES = {
  today: { tint: '#ff4fd8', k: 0, core: '#ff7be6', ring: '#22d3ee', grid: ['#ff2bd6', '#5b3bd1'], hor: '#ff3fd8', clouds: ['#7c3aed', '#ff2bd6', '#2b6cff', '#3ee0c8', '#a855f7'], rot: [0.52, 0, 0.1], pos: [0, 2.4, -13], spin: 1, bright: 1 },
  chart: { tint: '#5be7ff', k: 0.34, core: '#9ff6ff', ring: '#22d3ee', grid: ['#22d3ee', '#3b5bdb'], hor: '#3ee0c8', clouds: ['#1e40af', '#22d3ee', '#2b6cff', '#3ee0c8', '#6366f1'], rot: [0.92, 0, -0.16], pos: [2.4, 2.1, -14], spin: 1.1, bright: 1 },
  trades: { tint: '#ff4fd8', k: 0.24, core: '#ff8ae8', ring: '#f9a8d4', grid: ['#ff2bd6', '#7c3aed'], hor: '#ff3fd8', clouds: ['#9d174d', '#ff2bd6', '#7c3aed', '#f472b6', '#a855f7'], rot: [0.4, 0, 0.26], pos: [-2.2, 2.6, -13], spin: 1, bright: 1 },
  results: { tint: '#2ee59d', k: 0.24, core: '#8dffd6', ring: '#2ee59d', grid: ['#2ee59d', '#5b3bd1'], hor: '#22d3ee', clouds: ['#065f46', '#2ee59d', '#2b6cff', '#3ee0c8', '#7c3aed'], rot: [0.64, 0, -0.08], pos: [1.6, 2.4, -13], spin: 0.95, bright: 1 },
  lab: { tint: '#8b5cf6', k: 0.32, core: '#d8ccff', ring: '#a78bfa', grid: ['#7c3aed', '#3b2a9a'], hor: '#8b5cf6', clouds: ['#4c1d95', '#6d28d9', '#2b6cff', '#22d3ee', '#a855f7'], rot: [1.12, 0, 0.3], pos: [0, 3.1, -15], spin: 0.7, bright: 1.02 },
  losses: { tint: '#ff2b55', k: 0.26, core: '#ff7a95', ring: '#ff4fd8', grid: ['#ff2b6b', '#5b1d6d'], hor: '#ff2b55', clouds: ['#7f1d1d', '#ff2bd6', '#4c1d95', '#f43f5e', '#a855f7'], rot: [0.72, 0, -0.26], pos: [-1.6, 2.2, -13], spin: 0.6, bright: 0.9 },
  eval: { tint: '#ffd36b', k: 0.24, core: '#ffe9b0', ring: '#ffd36b', grid: ['#ffb347', '#5b3bd1'], hor: '#ffb347', clouds: ['#78350f', '#ff9b5c', '#7c3aed', '#2ee59d', '#a855f7'], rot: [0.48, 0, 0], pos: [0, 2.2, -12], spin: 0.9, bright: 1 },
  engine: { tint: '#3ee0c8', k: 0.26, core: '#b5fbff', ring: '#3ee0c8', grid: ['#3ee0c8', '#3b5bdb'], hor: '#22d3ee', clouds: ['#134e4a', '#3ee0c8', '#2b6cff', '#22d3ee', '#7c3aed'], rot: [0.8, 0, 0.18], pos: [2, 2.6, -13.5], spin: 1.3, bright: 1 },
  settings: { tint: '#8b8bb8', k: 0.3, core: '#c9c4ee', ring: '#8f86ff', grid: ['#5b3bd1', '#2a2350'], hor: '#7c3aed', clouds: ['#312e81', '#6d28d9', '#1e3a8a', '#334155', '#6d28d9'], rot: [0.52, 0, 0.1], pos: [0, 2.4, -13], spin: 0.5, bright: 0.78 },
};
const SCENE_ALIAS = { home: 'today', replays: 'trades', replay: 'trades', stops: 'trades', experiments: 'lab', writeups: 'lab', writeup: 'lab', run: 'lab', compare: 'lab',
  learned: 'lab', lessons: 'lab', study: 'lab', variants: 'lab', overview: 'lab', loss: 'losses', mffu: 'eval', prop: 'eval', system: 'engine', modules: 'engine',
  cold: 'engine', sources: 'engine', data: 'results', bot: 'engine' };
export const sceneNames = Object.keys(SCENES);
export const resolveScene = (n) => { const k = String(n || 'today').toLowerCase(); return SCENES[k] ? k : SCENE_ALIAS[k] || 'today'; };
const _ray = new THREE.Raycaster(), _ndc = new THREE.Vector2(), _inv = new THREE.Matrix4(), _r = new THREE.Ray();

export class Field extends View {
  constructor() {
    super({ alpha: false, antialias: false, dprMax: Q.phone ? 1.5 : 1.75, fov: 58 });
    this.canvas.classList.add('fx-field');
    const S = this.scene, R = rng(11);
    this.camera.position.set(0, 0.6, 9);
    this.target = new THREE.Vector3(0, 0.2, -6);
    this.mood = { spin: 1, bright: 1, tint: theme.accent2.clone(), tintK: 0, speed: 1 };
    this.moodT = { spin: 1, bright: 1, tintK: 0, speed: 1 };
    this.warpV = 0; this.pulseAge = 99; this.burstAge = 99; this.nextComet = 3.5; this.comet = null; this.flash = 0;
    this.u = { uTime: { value: 0 }, uPix: { value: 300 } };

    // ---- galaxy
    const N = count(Q.phone ? 6200 : 9000, Q.phone ? 2600 : 4200);
    const aR = new Float32Array(N), aT = new Float32Array(N), aY = new Float32Array(N), aS = new Float32Array(N), aSeed = new Float32Array(N), aCol = new Float32Array(N * 3);
    const cHot = new THREE.Color('#fff1fb'), cPink = new THREE.Color('#ff4fd8'), cVio = new THREE.Color('#8b5cf6'), cDeep = new THREE.Color('#3b2a9a'), cCyan = new THREE.Color('#5be7ff'), tmp = new THREE.Color();
    for (let i = 0; i < N; i++) {
      const haze = R() < 0.22, arm = i % 3;
      const r = haze ? 0.8 + Math.pow(R(), 0.9) * 15 : 0.9 + Math.pow(R(), 1.55) * 13.5;
      const spread = (R() - 0.5 + R() - 0.5) * (haze ? 3.1 : 0.42 + 0.9 / (r + 0.5));
      aR[i] = r; aT[i] = arm * 2.0944 + Math.log(r + 0.3) * 2.35 + spread;
      aY[i] = (R() - 0.5 + R() - 0.5 + R() - 0.5) * (0.12 + r * 0.035) * (haze ? 1.8 : 1);
      const sparkle = R() < 0.05;
      aS[i] = sparkle ? 3.2 + R() * 2.6 : (0.8 + R() * 1.6) * (r < 2.2 ? 1.5 : 1);
      aSeed[i] = R();
      if (sparkle) tmp.copy(R() < 0.5 ? cCyan : cHot);
      else if (r < 2.4) tmp.copy(cHot).lerp(cPink, r / 2.4 * 0.7);
      else tmp.copy(cPink).lerp(cVio, Math.min(1, (r - 2.4) / 6 + R() * 0.35)).lerp(cDeep, Math.max(0, (r - 8) / 7));
      tmp.multiplyScalar(haze ? 0.42 : sparkle ? 1.2 : 0.85);
      aCol.set([tmp.r, tmp.g, tmp.b], i * 3);
    }
    const gg = new THREE.BufferGeometry();
    gg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    for (const [k, a, n] of [['aR', aR, 1], ['aT', aT, 1], ['aY', aY, 1], ['aS', aS, 1], ['aSeed', aSeed, 1], ['aCol', aCol, 3]]) gg.setAttribute(k, new THREE.BufferAttribute(a, n));
    gg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 20);
    this.gU = { ...this.u, uSpin: { value: 1 }, uBright: { value: 1 }, uTint: { value: this.mood.tint }, uTintK: { value: 0 }, uPulse: { value: 0 }, uPulseR: { value: 0 },
      uScene: { value: new THREE.Color('#ff4fd8') }, uSceneK: { value: 0 }, uGRip: { value: new THREE.Vector4(0, 0, 9, 0) }, uRot: { value: 0 } };
    this.rot = 0; this.scrollV = 0; this.lastScroll = par.scroll; this.scroll = 0; this.ripAge = 9;
    const galaxy = new THREE.Points(gg, new THREE.ShaderMaterial({ uniforms: this.gU, vertexShader: GALAXY_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.gal = new THREE.Group(); this.gal.add(galaxy);
    this.gal.position.set(0, 2.4, -13); this.gal.rotation.set(0.52, 0, 0.1);
    S.add(this.gal);
    // bright core glow
    this.core = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color('#ff7be6'), transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.core.scale.set(7, 4.2, 1); this.gal.add(this.core);

    // ---- liquidity ring (dashed, in the galaxy plane) + comet + burst
    const RN = 540, aA = new Float32Array(RN); for (let i = 0; i < RN; i++) aA[i] = i / RN * Math.PI * 2;
    const rg = new THREE.BufferGeometry(); rg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(RN * 3), 3)); rg.setAttribute('aA', new THREE.BufferAttribute(aA, 1));
    rg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 10);
    this.rU = { ...this.u, uR: { value: 6.2 }, uCol: { value: theme.cyan.clone() }, uFlash: { value: 0 } };
    this.gal.add(new THREE.Points(rg, new THREE.ShaderMaterial({ uniforms: this.rU, vertexShader: RING_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));
    const TN = 46;
    const tg = new THREE.BufferGeometry(); this.trailPos = new Float32Array(TN * 3); const aI = new Float32Array(TN); for (let i = 0; i < TN; i++) aI[i] = i / (TN - 1);
    tg.setAttribute('position', new THREE.BufferAttribute(this.trailPos, 3)); tg.setAttribute('aI', new THREE.BufferAttribute(aI, 1)); tg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 30);
    this.tU = { ...this.u, uCol: { value: new THREE.Color('#ff5ce1') }, uOn: { value: 0 } };
    this.trail = new THREE.Points(tg, new THREE.ShaderMaterial({ uniforms: this.tU, vertexShader: TRAIL_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.gal.add(this.trail);
    this.head = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color('#ffd6fb'), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.head.scale.set(1.3, 1.3, 1); this.gal.add(this.head);
    const BN = count(320, 160), aDir = new Float32Array(BN * 3), bS = new Float32Array(BN), bSeed = new Float32Array(BN);
    for (let i = 0; i < BN; i++) {
      const u = R() * 2 - 1, a = R() * Math.PI * 2, q = Math.sqrt(1 - u * u), sp = 0.4 + Math.pow(R(), 0.6) * 1.4;
      aDir.set([q * Math.cos(a) * sp, Math.abs(u) * sp * 0.9, q * Math.sin(a) * sp], i * 3); bS[i] = 1.5 + R() * 3.5; bSeed[i] = R();
    }
    const bg = new THREE.BufferGeometry(); bg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(BN * 3), 3));
    bg.setAttribute('aDir', new THREE.BufferAttribute(aDir, 3)); bg.setAttribute('aS', new THREE.BufferAttribute(bS, 1)); bg.setAttribute('aSeed', new THREE.BufferAttribute(bSeed, 1));
    bg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 30);
    this.bU = { ...this.u, uAge: { value: 99 }, uO: { value: new THREE.Vector3() }, uCol: { value: theme.cyan.clone() } };
    this.burst = new THREE.Points(bg, new THREE.ShaderMaterial({ uniforms: this.bU, vertexShader: BURST_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.burst.visible = false; this.gal.add(this.burst);
    this.flare = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color('#bff6ff'), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.gal.add(this.flare);

    // ---- dust
    const M = count(Q.phone ? 900 : 1500, 420), aP = new Float32Array(M * 3), dS = new Float32Array(M), dSeed = new Float32Array(M);
    for (let i = 0; i < M; i++) { aP.set([(R() - 0.5) * 26, (R() - 0.5) * 16 + 1, R() * 46 - 40], i * 3); dS[i] = 0.6 + R() * 1.6; dSeed[i] = R(); }
    const dg = new THREE.BufferGeometry(); dg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(M * 3), 3));
    dg.setAttribute('aP', new THREE.BufferAttribute(aP, 3)); dg.setAttribute('aS', new THREE.BufferAttribute(dS, 1)); dg.setAttribute('aSeed', new THREE.BufferAttribute(dSeed, 1));
    dg.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, -15), 50);
    this.dU = { ...this.u, uDrift: { value: 0 }, uCol: { value: new THREE.Color('#c9b8ff') }, uBright: { value: 1 } };
    S.add(new THREE.Points(dg, new THREE.ShaderMaterial({ uniforms: this.dU, vertexShader: DUST_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));

    // ---- nebula clouds
    this.clouds = [];
    for (const [c, x, y, z, s, o] of [['#7c3aed', -6, 4, -20, 22, 0.11], ['#ff2bd6', 7, 3, -22, 18, 0.07], ['#2b6cff', -2, 7, -26, 26, 0.08], ['#3ee0c8', 9, -1, -18, 12, 0.035], ['#a855f7', 0, -1.5, -14, 14, 0.05]]) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(c), transparent: true, opacity: o, blending: THREE.AdditiveBlending, depthWrite: false }));
      sp.position.set(x, y, z); sp.scale.set(s, s * 0.7, 1); sp.userData = { x, y, s, o }; S.add(sp); this.clouds.push(sp);
    }

    // ---- neon grid floor
    this.fU = { ...this.u, uScroll: { value: 0 }, uC1: { value: new THREE.Color('#ff2bd6') }, uC2: { value: new THREE.Color('#5b3bd1') }, uCam: { value: this.camera.position }, uBright: { value: 0.75 },
      uRip: { value: Array.from({ length: 4 }, () => new THREE.Vector4(0, 0, 9, 0)) } };
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(140, 140), new THREE.ShaderMaterial({ uniforms: this.fU, vertexShader: GRID_V, fragmentShader: GRID_F, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, extensions: { derivatives: true } }));
    floor.rotation.x = -Math.PI / 2; floor.position.set(0, -3.4, -40); S.add(floor);
    const horizon = this.horizon = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color('#ff3fd8'), transparent: true, opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false }));
    horizon.position.set(0, -3.2, -60); horizon.scale.set(140, 9, 1); S.add(horizon);
    // ---- card auras (screen space, second pass)
    this.aura = new Aura();
    // ---- scene: current values (blended toward the preset every frame)
    this.scn = { name: 'today', tint: new THREE.Color('#ff4fd8'), k: 0, core: new THREE.Color('#ff7be6'), ring: theme.cyan.clone(), g1: new THREE.Color('#ff2bd6'), g2: new THREE.Color('#5b3bd1'),
      hor: new THREE.Color('#ff3fd8'), clouds: this.clouds.map((c) => c.material.color.clone()), rot: new THREE.Vector3(0.52, 0, 0.1), pos: new THREE.Vector3(0, 2.4, -13), spin: 1, bright: 1 };
    this.setScene('today', true);
  }
  // ---- scenes
  setScene(name, now = false) {
    const key = resolveScene(name), P = SCENES[key], T = this.scnT ||= {};
    T.name = key; T.tint = new THREE.Color(P.tint); T.k = P.k; T.core = new THREE.Color(P.core); T.ring = new THREE.Color(P.ring);
    T.g1 = new THREE.Color(P.grid[0]); T.g2 = new THREE.Color(P.grid[1]); T.hor = new THREE.Color(P.hor); T.clouds = P.clouds.map((c) => new THREE.Color(c));
    T.rot = new THREE.Vector3(...P.rot); T.pos = new THREE.Vector3(...P.pos); T.spin = P.spin; T.bright = P.bright;
    if (now || Q.reduced) this.sceneStep(1);
    return key;
  }
  sceneStep(k) {
    const S = this.scn, T = this.scnT; if (!T) return;
    S.name = T.name; S.tint.lerp(T.tint, k); S.k += (T.k - S.k) * k; S.core.lerp(T.core, k); S.ring.lerp(T.ring, k); S.g1.lerp(T.g1, k); S.g2.lerp(T.g2, k); S.hor.lerp(T.hor, k);
    S.clouds.forEach((c, i) => c.lerp(T.clouds[i] || c, k)); S.rot.lerp(T.rot, k); S.pos.lerp(T.pos, k); S.spin += (T.spin - S.spin) * k; S.bright += (T.bright - S.bright) * k;
    this.gU.uScene.value.copy(S.tint); this.gU.uSceneK.value = S.k;
    this.core.material.color.copy(S.core); this.rU.uCol.value.copy(S.ring); this.fU.uC1.value.copy(S.g1); this.fU.uC2.value.copy(S.g2); this.horizon.material.color.copy(S.hor);
    this.clouds.forEach((c, i) => c.material.color.copy(S.clouds[i]));
    this.gal.rotation.set(S.rot.x, S.rot.y, S.rot.z); this.gal.position.copy(S.pos);
  }
  // ---- ripples: client px of a tap on empty background -> a wave in the galaxy disc (upper screen) or the grid floor
  ripple(cx, cy) {
    if (Q.reduced || Q.level === 'off') return false;
    _ndc.set(cx / innerWidth * 2 - 1, -(cy / innerHeight) * 2 + 1); _ray.setFromCamera(_ndc, this.camera);
    const sky = cy < innerHeight * 0.55;
    const disc = () => {
      this.gal.updateMatrixWorld(); _inv.copy(this.gal.matrixWorld).invert(); _r.copy(_ray.ray).applyMatrix4(_inv);
      if (Math.abs(_r.direction.y) < 1e-4) return false;
      const t = -_r.origin.y / _r.direction.y; if (t <= 0) return false;
      const x = _r.origin.x + _r.direction.x * t, z = _r.origin.z + _r.direction.z * t;
      if (Math.hypot(x, z) > 15) return false;
      this.gU.uGRip.value.set(x, z, 0, 1); this.ripAge = 0; return true;
    };
    const grid = () => {
      const o = _ray.ray.origin, d = _ray.ray.direction; if (d.y > -1e-4) return false;
      const t = (-3.4 - o.y) / d.y; if (t <= 0 || t > 70) return false;
      const R = this.fU.uRip.value, slot = R.reduce((b, r, i) => (r.z > R[b].z ? i : b), 0);
      R[slot].set(o.x + d.x * t, o.z + d.z * t, 0, 1); return true;
    };
    return sky ? disc() || grid() : grid() || disc();
  }
  frame(t, dt) {
    this.update(t, dt);
    const r = this.renderer;
    r.render(this.scene, this.camera);
    if (this.aura && Q.level !== 'off' && this.aura.step(t, dt, this.w, this.h, r.getPixelRatio())) {
      r.autoClear = false; r.render(this.aura.scene, this.aura.cam); r.autoClear = true;
    }
  }
  dispose() { this.aura?.dispose(); super.dispose(); }
  onResize(w, h) {
    const dpr = this.renderer.getPixelRatio();
    this.u.uPix.value = h * dpr / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))) * 0.022;
  }
  running() { return this.attached && !document.hidden && Q.level !== 'off' && !this.broken; }
  // ---- API
  setMood({ killzone = false, cold = false, pnl = 0, live = false } = {}) {
    this.moodT.spin = killzone ? 1.9 : live ? 1.2 : 0.8;
    this.moodT.speed = killzone ? 1.0 : 0.35;
    this.moodT.bright = live || killzone ? 1.05 : 0.9;
    if (this.aura) this.aura.speed = killzone ? 1.7 : live ? 1.25 : 1;
    if (pnl > 0) { this.mood.tint.copy(theme.good); this.moodT.tintK = 0.22; }
    else if (cold || pnl < 0) { this.mood.tint.copy(theme.magenta); this.moodT.tintK = 0.2; }
    else { this.moodT.tintK = 0; }
  }
  warp() { this.warpV = 1; }
  pulse() { this.pulseAge = 0; }
  sweep() { this.nextComet = 0; }
  // ---- frame
  update(t, dt) {
    const m = this.mood, mt = this.moodT, k = Math.min(1, dt * 1.5);
    m.spin += (mt.spin - m.spin) * k; m.bright += (mt.bright - m.bright) * k; m.tintK += (mt.tintK - m.tintK) * k; m.speed += (mt.speed - m.speed) * k;
    this.warpV = Math.max(0, this.warpV - dt * 1.6);
    const w = this.warpV * this.warpV;
    this.u.uTime.value = t;
    this.sceneStep(1 - Math.exp(-dt * 1.7));
    const sc0 = this.scn;
    // page fling: scroll speed drives the dust and the grid for a moment
    const sv = Math.abs(par.scroll - this.lastScroll) / Math.max(dt, 1e-3); this.lastScroll = par.scroll;
    this.scrollV += (Math.min(sv, 5000) - this.scrollV) * Math.min(1, dt * 5);
    const fl = Q.reduced ? 0 : Math.min(1, this.scrollV / 2500);
    // spin is integrated (not time x speed) so a scene / mood change never makes the arms jump
    this.rot += dt * m.spin * sc0.spin * (1 + w * 5 + fl * 0.8); this.gU.uRot.value = this.rot;
    this.gU.uSpin.value = 1; this.gU.uBright.value = m.bright * sc0.bright * (1 + w * 0.6 + fl * 0.15); this.gU.uTintK.value = m.tintK;
    this.dU.uDrift.value += dt * (0.55 + w * 22 + fl * 9) * (Q.reduced ? 0.2 : 1); this.dU.uBright.value = 0.9 + w + fl * 0.4;
    this.scroll += dt * (m.speed + fl * 1.6); this.fU.uScroll.value = this.scroll; this.fU.uBright.value = 0.75 * m.bright * sc0.bright;
    // ripples age out
    for (const r of this.fU.uRip.value) if (r.w > 0) { r.z += dt; if (r.z > 2.3) r.w = 0; }
    const gr = this.gU.uGRip.value; if (gr.w > 0) { gr.z += dt; if (gr.z > 2.7) gr.w = 0; }
    // pulse ring on new data
    this.pulseAge += dt; this.gU.uPulse.value = Math.max(0, 1 - this.pulseAge / 2.2); this.gU.uPulseR.value = this.pulseAge * 7;
    // comet sweeping the liquidity ring
    if (!Q.reduced) this.cometStep(t, dt);
    for (const c of this.clouds) { const d = c.userData; c.position.x = d.x + Math.sin(t * 0.03 + d.s) * 1.2; c.material.opacity = d.o * (0.85 + 0.15 * Math.sin(t * 0.2 + d.s)); }
    this.core.material.opacity = 0.5 + 0.1 * Math.sin(t * 0.7);
    // camera: pointer / tilt parallax, scroll depth, warp kick
    const cam = this.camera, sc = Math.min(par.scroll, 2600);
    cam.position.set(par.x * 0.9, 0.6 - par.y * 0.45 - sc * 0.0011, 9 - w * 1.5);
    this.target.set(par.x * 0.3, 0.2 - sc * 0.0007, -6);
    cam.lookAt(this.target);
    const fov = 58 + w * 9;
    if (Math.abs(cam.fov - fov) > 0.01) { cam.fov = fov; cam.updateProjectionMatrix(); }
  }
  cometStep(t, dt) {
    const tU = this.tU;
    if (!this.comet) {
      this.nextComet -= dt;
      if (this.nextComet > 0) { tU.uOn.value = Math.max(0, tU.uOn.value - dt * 2); this.head.material.opacity = 0; this.flashStep(dt); return; }
      // pick a point on the ring and fly in from above, curving
      const a = Math.random() * Math.PI * 2, R = this.rU.uR.value;
      const hit = new THREE.Vector3(Math.cos(a) * R, 0, Math.sin(a) * R);
      const from = hit.clone().add(new THREE.Vector3((Math.random() - 0.5) * 10, 6 + Math.random() * 3, (Math.random() - 0.5) * 6));
      const to = hit.clone().add(hit.clone().sub(from).setLength(3.5));
      this.comet = { hit, from, to, s: 0, dur: 2.2, crossed: false, hist: [] };
      this.trailPos.fill(0);
      for (let i = 0; i < this.trailPos.length; i += 3) this.trailPos.set([from.x, from.y, from.z], i);
    }
    const c = this.comet;
    c.s += dt / c.dur;
    const s = Math.min(1, c.s), e = s * s * (3 - 2 * s), sw = Math.sin(s * Math.PI) * 1.6;
    const p = new THREE.Vector3().lerpVectors(c.from, c.to, e); p.x += sw; p.z -= sw * 0.4;
    this.head.position.copy(p); this.head.material.opacity = Math.min(1, s * 4) * (1 - Math.max(0, (s - 0.8) / 0.2));
    // trail history
    const tp = this.trailPos; tp.copyWithin(3, 0, tp.length - 3); tp.set([p.x, p.y, p.z], 0);
    this.trail.geometry.attributes.position.needsUpdate = true; tU.uOn.value = Math.min(1, tU.uOn.value + dt * 3) * (1 - Math.max(0, (s - 0.85) / 0.15));
    if (!c.crossed && p.y <= 0) { c.crossed = true; this.triggerBurst(p); }
    if (c.s >= 1) { this.comet = null; this.nextComet = Q.level === 'lite' ? 16 + Math.random() * 6 : 8 + Math.random() * 6; }
    this.flashStep(dt);
  }
  triggerBurst(p) {
    this.burstAge = 0; this.bU.uO.value.copy(p); this.burst.visible = true; this.flash = 1;
    this.flare.position.copy(p); this.bU.uCol.value.copy(Math.random() < 0.5 ? theme.cyan : theme.magenta);
  }
  flashStep(dt) {
    this.burstAge += dt; this.bU.uAge.value = this.burstAge; if (this.burstAge > 2.6) this.burst.visible = false;
    this.flash = Math.max(0, this.flash - dt * 1.4); this.rU.uFlash.value = this.flash;
    this.flare.material.opacity = this.flash * 0.9; const s = 1.5 + (1 - this.flash) * 5; this.flare.scale.set(s * 2.2, s * 0.5, 1);
  }
  retheme() { if (this.scnT && this.scnT.name === 'today') this.scnT.ring.copy(theme.cyan); }
}
