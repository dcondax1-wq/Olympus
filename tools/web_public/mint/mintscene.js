// MINT 3D scene (optional ES module): five golden pillars on a marble floor, one per money stream, height = the stream's estimated dollars a month.
// Warm sun, warm fog, marble and bronze, no glow. It registers window.MINT3D = { mount(box, pillars), update(pillars), dispose() } and fires 'mint3d'.
// mint.js draws the 2D pillars first and only hides them when mount() returns true (WebGL present); any failure here leaves the 2D picture in place.
import * as THREE from '../jarvis/three.module.min.js';

const GOLD = 0xc8a24a, BRONZE = 0x9c6b3c, MARBLE = 0xcfc4b2, SUN = 0xffd9a0;
const MAXH = 4.2, MINH = 0.35;
let R = null;

function webgl() { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (_) { return false; } }
const colorFor = (st) => (st === 'ok' ? GOLD : st === 'stale' ? BRONZE : 0xb39345);

function pillar(x, mat) {
  const g = new THREE.Group(); g.position.x = x;
  const base = new THREE.Mesh(new THREE.BoxGeometry(1.15, 0.2, 1.15), new THREE.MeshStandardMaterial({ color: BRONZE, roughness: 0.5, metalness: 0.4 })); base.position.y = 0.1; g.add(base);
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.42, 1, 24), mat); g.add(shaft);
  const cap = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.16, 1.0), new THREE.MeshStandardMaterial({ color: 0xe0b060, roughness: 0.4, metalness: 0.5 })); g.add(cap);
  g.userData = { shaft, cap, h: MINH, to: MINH };
  return g;
}
function place(g) { const h = g.userData.h; g.userData.shaft.scale.y = h; g.userData.shaft.position.y = 0.2 + h / 2; g.userData.cap.position.y = 0.2 + h + 0.08; }
const target = (p) => MINH + Math.max(0.02, Math.min(1, p.h)) * MAXH;

function mount(box, pillars) {
  if (R) dispose();
  if (!box || !webgl()) return false;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' }); } catch (_) { return false; }
  const reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  box.appendChild(renderer.domElement);
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x2a2016); scene.fog = new THREE.Fog(0x2a2016, 12, 26);
  const camera = new THREE.PerspectiveCamera(36, 1.8, 0.1, 60);
  scene.add(new THREE.HemisphereLight(0xffe2b8, 0x3a2a1c, 0.85));
  const sun = new THREE.DirectionalLight(SUN, 1.5); sun.position.set(5, 9, 6); scene.add(sun);
  const warm = new THREE.PointLight(0xffc477, 0.9, 16); warm.position.set(0, 6, 3); scene.add(warm);
  const floor = new THREE.Mesh(new THREE.CylinderGeometry(7, 7.3, 0.3, 56), new THREE.MeshStandardMaterial({ color: MARBLE, roughness: 0.55, metalness: 0.05 })); floor.position.y = -0.15; scene.add(floor);
  const step = new THREE.Mesh(new THREE.CylinderGeometry(6.2, 6.3, 0.12, 56), new THREE.MeshStandardMaterial({ color: 0xe6dccb, roughness: 0.6 })); step.position.y = 0.06; scene.add(step);
  const groups = [], mats = [];
  (pillars || []).slice(0, 5).forEach((p, i, a) => {
    const m = new THREE.MeshStandardMaterial({ color: colorFor(p.status), roughness: 0.36, metalness: 0.55 }); mats.push(m);
    const g = pillar((i - (a.length - 1) / 2) * 2.1, m); g.userData.to = target(p); g.userData.h = reduce ? g.userData.to : MINH; place(g); scene.add(g); groups.push(g);
  });
  R = { renderer, scene, camera, groups, mats, box, frames: 0, raf: 0, t0: performance.now(), reduce, ro: null, dead: false };
  const size = () => {
    const w = Math.max(160, box.clientWidth || 320), h = Math.max(90, box.clientHeight || 180);
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    const k = w / h < 1.5 ? 1.35 : 1; R.r = 12.5 * k; R.y = 4.2 * k; camera.position.set(0, R.y, R.r); camera.lookAt(0, 1.5, 0);
  };
  size();
  if (typeof ResizeObserver === 'function') { R.ro = new ResizeObserver(() => { size(); frame(performance.now(), true); }); R.ro.observe(box); }
  const frame = (now, once) => {
    if (!R || R.dead) return;
    const t = (now - R.t0) / 1000;
    let moving = false;
    for (const g of groups) { const u = g.userData, d = u.to - u.h; if (Math.abs(d) > 0.004) { u.h += d * 0.08; moving = true; } else u.h = u.to; place(g); }
    if (!R.reduce) { const a = Math.sin(t * 0.18) * 0.28; camera.position.x = Math.sin(a) * R.r; camera.position.z = Math.cos(a) * R.r; camera.lookAt(0, 1.5, 0); }
    renderer.render(scene, camera); R.frames++;
    if (once) return;
    if (!R.reduce || moving) R.raf = requestAnimationFrame(frame);
  };
  R.frame = frame;
  const vis = () => { if (!R) return; cancelAnimationFrame(R.raf); if (!document.hidden) R.raf = requestAnimationFrame(frame); };
  document.addEventListener('visibilitychange', vis); R.vis = vis;
  R.raf = requestAnimationFrame(frame);
  return true;
}

function update(pillars) {
  if (!R) return;
  (pillars || []).slice(0, 5).forEach((p, i) => { const g = R.groups[i]; if (!g) return; g.userData.to = target(p); R.mats[i].color.setHex(colorFor(p.status)); });
  cancelAnimationFrame(R.raf); R.raf = requestAnimationFrame(R.frame);
}

function dispose() {
  if (!R) return;
  R.dead = true; cancelAnimationFrame(R.raf);
  try { document.removeEventListener('visibilitychange', R.vis); if (R.ro) R.ro.disconnect(); R.scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); R.renderer.dispose(); if (R.renderer.domElement.parentNode) R.renderer.domElement.parentNode.removeChild(R.renderer.domElement); } catch (_) { /* nothing */ }
  R = null;
}

window.MINT3D = { mount, update, dispose, frames: () => (R ? R.frames : 0), pillars: () => (R ? R.groups.map((g) => Math.round(g.userData.to * 100) / 100) : []) };
window.dispatchEvent(new Event('mint3d'));
