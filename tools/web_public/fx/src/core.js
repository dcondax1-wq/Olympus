// Core of the 3D layer: quality levels, one shared animation loop, a View base (canvas + renderer + resize +
// visibility + drag-to-orbit + tap picking), shared textures, theme colours and pointer / tilt parallax.
// Every view renders only while it is on screen, the tab is visible and effects are on, so a phone does not burn
// battery on things nobody is looking at.
import * as THREE from 'three';

export { THREE };

// ------------------------------------------------------------------ quality
// level: 'max' (default), 'lite' (fewer particles, 30 fps, lower resolution), 'off' (no WebGL at all)
export const Q = { level: 'max', dprScale: 1, fps: 60, phone: matchMedia('(max-width: 760px)').matches, reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
  fixed: /[?&]fxfixed\b/.test(location.search) };   // ?fxfixed keeps full resolution (screenshots in a software GPU)
export function setLevel(level) {
  Q.level = level;
  Q.fps = level === 'lite' ? 30 : 60;
  Q.dprScale = level === 'lite' ? 0.75 : 1;
  for (const v of views) v.resize?.();
}
export const count = (max, lite) => Q.level === 'lite' ? lite : max;

// ------------------------------------------------------------------ theme
const css = (n, d) => (getComputedStyle(document.documentElement).getPropertyValue(n).trim() || d);
export const theme = { accent: new THREE.Color('#6d7cff'), accent2: new THREE.Color('#3ee0c8'), good: new THREE.Color('#2ee59d'),
  bad: new THREE.Color('#ff5a7a'), magenta: new THREE.Color('#ff2bd6'), violet: new THREE.Color('#8b5cf6'), cyan: new THREE.Color('#22d3ee'),
  bsl: new THREE.Color('#ff9b5c'), ssl: new THREE.Color('#6d9bff'), page: new THREE.Color('#07080c') };
export function readTheme() {
  for (const [k, v] of [['accent', '--accent'], ['accent2', '--accent-2'], ['good', '--good'], ['bad', '--bad'], ['bsl', '--bsl'], ['ssl', '--ssl'], ['page', '--page']]) {
    try { theme[k].set(css(v, '#' + theme[k].getHexString())); } catch { }
  }
  for (const v of views) v.retheme?.();
}

// ------------------------------------------------------------------ parallax: pointer (desktop), device tilt (opt-in), scroll
export const par = { x: 0, y: 0, tx: 0, ty: 0, scroll: 0, gyro: false };
addEventListener('pointermove', (e) => {
  if (e.pointerType !== 'mouse' || par.gyro) return;
  par.tx = (e.clientX / innerWidth) * 2 - 1; par.ty = (e.clientY / innerHeight) * 2 - 1;
}, { passive: true });
addEventListener('scroll', () => { par.scroll = scrollY; }, { passive: true });
let g0 = null;
function onTilt(e) {
  if (e.beta == null || e.gamma == null) return;
  if (!g0) g0 = { b: e.beta, g: e.gamma };
  par.tx = Math.max(-1, Math.min(1, (e.gamma - g0.g) / 25));
  par.ty = Math.max(-1, Math.min(1, (e.beta - g0.b) / 25));
}
export async function enableGyro(on = true) {
  if (!on) { removeEventListener('deviceorientation', onTilt); par.gyro = false; par.tx = par.ty = 0; return false; }
  try {
    const D = window.DeviceOrientationEvent;
    if (D && typeof D.requestPermission === 'function' && (await D.requestPermission()) !== 'granted') return false;
    if (!D) return false;
    g0 = null; addEventListener('deviceorientation', onTilt, { passive: true }); par.gyro = true; return true;
  } catch { return false; }
}

// ------------------------------------------------------------------ shared textures
let _glow = null;
export function glowTexture() {
  if (_glow) return _glow;
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.18, 'rgba(255,255,255,0.75)'); gr.addColorStop(0.45, 'rgba(255,255,255,0.18)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  _glow = new THREE.CanvasTexture(c); _glow.colorSpace = THREE.SRGBColorSpace;
  return _glow;
}
// soft additive sprite (glow / flare); color can be a THREE.Color
export function glow(color, scale, opacity = 1) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false }));
  s.scale.set(scale, scale, 1); return s;
}
// additive neon material (unlit, can exceed 1 for a hotter core)
export const neon = (color, k = 1, opacity = 1) => new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(k), transparent: opacity < 1, opacity,
  blending: THREE.AdditiveBlending, depthWrite: false });
// fresnel rim shell (glass edge glow)
export function rimMaterial(colorA, colorB, power = 3, k = 1.6) {
  return new THREE.ShaderMaterial({
    uniforms: { cA: { value: new THREE.Color(colorA) }, cB: { value: new THREE.Color(colorB) }, p: { value: power }, k: { value: k } },
    vertexShader: 'varying vec3 n; varying vec3 v; varying float yy; void main(){ vec4 w = modelViewMatrix * vec4(position,1.0); n = normalize(normalMatrix * normal); v = normalize(-w.xyz); yy = normal.y; gl_Position = projectionMatrix * w; }',
    fragmentShader: 'uniform vec3 cA; uniform vec3 cB; uniform float p; uniform float k; varying vec3 n; varying vec3 v; varying float yy; void main(){ float f = pow(1.0 - max(dot(n, v), 0.0), p); gl_FragColor = vec4(mix(cA, cB, clamp(yy*0.5+0.5,0.0,1.0)) * f * k, 1.0); }',
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
}
// soft round point sprites with per-point colour / size / alpha (fragment part shared by the particle systems)
export const POINT_FRAG = `varying vec3 vColor; varying float vAlpha;
void main(){ vec2 q = gl_PointCoord - 0.5; float d = dot(q, q) * 4.0; if (d > 1.0) discard;
  float a = (1.0 - d); a = a * a; float core = exp(-d * 18.0);
  gl_FragColor = vec4(vColor * (a * 0.55 + core * 0.9) * vAlpha, 1.0); }`;

// tiny deterministic RNG so scenes look the same on every load
export function rng(seed = 7) { let s = seed >>> 0 || 1; return () => (s = (s * 16807) % 2147483647) / 2147483647; }

// ------------------------------------------------------------------ the loop
const views = new Set();
let raf = 0, lastT = 0, acc = 0, frames = 0, slow = 0, lastInput = performance.now();
for (const ev of ['pointerdown', 'pointermove', 'wheel', 'scroll', 'keydown', 'touchstart']) addEventListener(ev, () => { lastInput = performance.now(); }, { passive: true, capture: true });
const clock = { t: 0 };
function tick(now) {
  raf = 0;
  const dt = Math.min(0.1, (now - lastT) / 1000 || 0.016);
  // battery: after 20 s without a touch, scroll or key the whole layer runs at 30 fps
  const fps = now - lastInput > 20000 ? Math.min(30, Q.fps) : Q.fps, minDt = 1 / fps - 0.002;
  if (dt < minDt) { raf = requestAnimationFrame(tick); return; }
  lastT = now; clock.t += dt;
  par.x += (par.tx - par.x) * Math.min(1, dt * 3); par.y += (par.ty - par.y) * Math.min(1, dt * 3);
  let any = false;
  const t0 = performance.now();
  for (const v of views) if (v.running()) { any = true; try { v.frame(clock.t, dt); } catch (e) { console.warn('fx view', e); v.broken = true; } }
  // adaptive quality: if frames take too long for a while, lower the resolution (biggest win on phones)
  const cost = performance.now() - t0;
  if (any && Q.level !== 'off' && !Q.fixed) {
    acc += dt; frames++;
    if (dt > 1.6 / fps || cost > 22) slow++;
    if (acc > 3) {
      if (slow / frames > 0.5 && Q.dprScale > 0.55) { Q.dprScale = Math.max(0.55, Q.dprScale - 0.2); for (const v of views) v.resize?.(); }
      acc = frames = slow = 0;
    }
  }
  if (any && !document.hidden) raf = requestAnimationFrame(tick);
}
export function wake() { if (!raf && !document.hidden && Q.level !== 'off') { lastT = performance.now(); raf = requestAnimationFrame(tick); } }
document.addEventListener('visibilitychange', () => { if (!document.hidden) wake(); });
export const now = () => clock.t;

// ------------------------------------------------------------------ View base
export class View {
  // opts: { alpha, antialias, dprMax, fov, orbit: { yaw, pitch, auto, min, max, pitchMin, pitchMax }, onPick(x, y) }
  constructor(opts = {}) {
    this.opts = opts;
    this.canvas = document.createElement('canvas');
    this.canvas.className = 'fx-canvas';
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, alpha: !!opts.alpha, antialias: opts.antialias !== false, powerPreference: 'high-performance' });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.NoToneMapping;
    if (!opts.alpha) this.renderer.setClearColor(theme.page, 1); else this.renderer.setClearColor(0x000000, 0);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(opts.fov || 40, 1, 0.05, 400);
    this.visible = false; this.attached = false; this.el = null; this.w = 1; this.h = 1;
    const o = opts.orbit || {};
    this.orbit = { yaw: o.yaw || 0, pitch: o.pitch || 0.25, vyaw: 0, vpitch: 0, auto: o.auto ?? 0.12, dragging: false, last: 0,
      min: o.min ?? -Infinity, max: o.max ?? Infinity, pitchMin: o.pitchMin ?? -0.2, pitchMax: o.pitchMax ?? 0.9, idle: 99 };
    this._io = new IntersectionObserver((es) => { for (const e of es) this.visible = e.isIntersecting; if (this.visible) wake(); }, { rootMargin: '80px' });
    this._ro = new ResizeObserver(() => this.resize());
    if (opts.orbit || opts.onPick) this._bindPointer();
    views.add(this);
  }
  attach(el) {
    if (this.el === el && this.attached) return;
    this.detach();
    this.el = el; el.appendChild(this.canvas); this.attached = true;
    this._io.observe(el); this._ro.observe(el); this.resize(); wake();
  }
  detach() {
    if (!this.attached) return;
    this._io.disconnect(); this._ro.disconnect(); this.canvas.remove(); this.attached = false; this.visible = false;
  }
  running() { return this.attached && this.visible && !this.broken && !document.hidden && Q.level !== 'off'; }
  resize() {
    if (!this.el) return;
    const r = this.el.getBoundingClientRect(), w = Math.max(10, Math.round(r.width)), h = Math.max(10, Math.round(r.height));
    this.w = w; this.h = h;
    this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, (this.opts.dprMax || 2)) * Q.dprScale);
    this.renderer.setSize(w, h, false);
    this.canvas.style.width = w + 'px'; this.canvas.style.height = h + 'px';
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    this.onResize?.(w, h);
  }
  // orbit state -> applied by the subclass in update() via orbitStep(dt)
  orbitStep(dt) {
    const o = this.orbit;
    o.idle += dt;
    if (!o.dragging) {
      o.yaw += o.vyaw; o.pitch += o.vpitch; o.vyaw *= 0.92; o.vpitch *= 0.92;
      if (o.idle > 2.5 && o.auto && !Q.reduced) o.yaw += o.auto * dt * Math.min(1, (o.idle - 2.5));
    }
    o.yaw = Math.max(o.min, Math.min(o.max, o.yaw)); o.pitch = Math.max(o.pitchMin, Math.min(o.pitchMax, o.pitch));
    if ((o.yaw <= o.min || o.yaw >= o.max) && o.auto) o.auto = -o.auto;
    return o;
  }
  _bindPointer() {
    const c = this.canvas, o = this.orbit;
    c.style.touchAction = 'pan-y';
    let down = null;
    c.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY, t: performance.now(), lx: e.clientX, ly: e.clientY }; o.dragging = true; o.idle = 0; o.vyaw = o.vpitch = 0; });
    c.addEventListener('pointermove', (e) => {
      if (!down || !this.opts.orbit) return;
      const dx = e.clientX - down.lx, dy = e.clientY - down.ly; down.lx = e.clientX; down.ly = e.clientY;
      o.vyaw = -dx * 0.006; o.yaw += o.vyaw;
      if (e.pointerType === 'mouse') { o.vpitch = dy * 0.004; o.pitch += o.vpitch; }
      o.idle = 0;
    });
    const up = (e) => {
      if (!down) return;
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y), dur = performance.now() - down.t;
      if (e.type === 'pointerup' && moved < 8 && dur < 450 && this.opts.onPick) {
        const r = c.getBoundingClientRect(); this.opts.onPick((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1, e);
      }
      down = null; o.dragging = false; o.idle = 0;
    };
    c.addEventListener('pointerup', up); c.addEventListener('pointercancel', up); c.addEventListener('pointerleave', up);
  }
  frame(t, dt) { this.update?.(t, dt); this.renderer.render(this.scene, this.camera); }
  dispose() {
    this.detach(); views.delete(this);
    this.scene.traverse((o) => { o.geometry?.dispose?.(); const m = o.material; (Array.isArray(m) ? m : m ? [m] : []).forEach(x => x.dispose?.()); });
    this.renderer.dispose(); try { this.renderer.forceContextLoss(); } catch { }
  }
}

// project a 3D point of a view to CSS pixels inside its element (for HTML labels / tests)
export function toScreen(view, v3) {
  const p = v3.clone().project(view.camera);
  return { x: (p.x * 0.5 + 0.5) * view.w, y: (-p.y * 0.5 + 0.5) * view.h, behind: p.z > 1 };
}
