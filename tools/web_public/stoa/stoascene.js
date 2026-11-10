// STOA 3D scene (optional ES module): a row of six marble columns on a marble floor. A LIT column (something needs you) has a small warm brazier flame and a warm light on its capital;
// a calm column is plain marble in the shade. Warm sun, warm fog, no neon, no bloom. Registers window.STOA3D = { mount(box, cols), update(cols), dispose() } and fires 'stoa3d'.
// stoa.js draws the 2D columns first and hides them only when mount() returns true (WebGL present).
import * as THREE from '../jarvis/three.module.min.js';

const MARBLE = 0xd8cfbd, LIT = 0xf3e2b8, GOLD = 0xe0b060, TERRA = 0xc96a4a;
let R = null;

function webgl() { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (_) { return false; } }

function column(x) {
  const g = new THREE.Group(); g.position.x = x;
  const mat = new THREE.MeshStandardMaterial({ color: MARBLE, roughness: 0.55, metalness: 0.03 });
  const base = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.22, 1.2), mat); base.position.y = 0.11; g.add(base);
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.46, 3.4, 20), mat); shaft.position.y = 0.22 + 1.7; g.add(shaft);
  const cap = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.24, 1.1), new THREE.MeshStandardMaterial({ color: 0xbdb3a0, roughness: 0.5 })); cap.position.y = 0.22 + 3.4 + 0.12; g.add(cap);
  const flame = new THREE.Mesh(new THREE.ConeGeometry(0.2, 0.62, 12), new THREE.MeshBasicMaterial({ color: GOLD })); flame.position.y = 4.2; g.add(flame);
  const light = new THREE.PointLight(0xffc477, 0, 6); light.position.y = 4.1; g.add(light);
  g.userData = { mat, cap, flame, light, lit: false, k: 0, k0: 0 };
  return g;
}
function apply(g, c) {
  const u = g.userData; u.lit = !!c.lit;
  u.mat.color.setHex(u.lit ? LIT : MARBLE);
  u.flame.material.color.setHex(c.tone === 'bad' ? TERRA : GOLD);
  u.cap.material.color.setHex(u.lit ? GOLD : 0xbdb3a0);
}

function mount(box, cols) {
  if (R) dispose();
  if (!box || !webgl()) return false;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' }); } catch (_) { return false; }
  const reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  box.appendChild(renderer.domElement);
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x2a2016); scene.fog = new THREE.Fog(0x2a2016, 14, 30);
  const camera = new THREE.PerspectiveCamera(34, 2.2, 0.1, 80);
  scene.add(new THREE.HemisphereLight(0xffe2b8, 0x3a2a1c, 0.8));
  const sun = new THREE.DirectionalLight(0xffd9a0, 1.2); sun.position.set(5, 9, 7); scene.add(sun);
  const floor = new THREE.Mesh(new THREE.BoxGeometry(17, 0.3, 5), new THREE.MeshStandardMaterial({ color: 0xcfc4b2, roughness: 0.6 })); floor.position.y = -0.15; scene.add(floor);
  const groups = [], n = Math.min(6, (cols || []).length);
  (cols || []).slice(0, 6).forEach((c, i) => { const g = column((i - (n - 1) / 2) * 2.5); apply(g, c); scene.add(g); groups.push(g); });
  R = { renderer, scene, camera, groups, box, frames: 0, raf: 0, t0: performance.now(), reduce, ro: null, dead: false, r: 16, y: 4 };
  const size = () => {
    const w = Math.max(160, box.clientWidth || 320), h = Math.max(80, box.clientHeight || 140);
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    R.r = w / h < 2 ? 21 : 17; R.y = 4.4; camera.position.set(0, R.y, R.r); camera.lookAt(0, 2.2, 0);
  };
  size();
  if (typeof ResizeObserver === 'function') { R.ro = new ResizeObserver(() => { size(); frame(performance.now(), true); }); R.ro.observe(box); }
  const frame = (now, once) => {
    if (!R || R.dead) return;
    const t = (now - R.t0) / 1000;
    for (const g of groups) {
      const u = g.userData, want = u.lit ? 1 : 0;
      u.k += (want - u.k) * (reduce ? 1 : 0.1);
      u.flame.visible = u.k > 0.05; u.flame.scale.y = 0.6 + 0.4 * u.k + (reduce || !u.lit ? 0 : Math.sin(t * 2.2 + g.position.x) * 0.06);
      u.light.intensity = 1.6 * u.k;
    }
    if (!reduce) { const a = Math.sin(t * 0.15) * 0.1; camera.position.x = Math.sin(a) * R.r; camera.position.z = Math.cos(a) * R.r; camera.lookAt(0, 2.2, 0); }
    renderer.render(scene, camera); R.frames++;
    if (!once && !reduce) R.raf = requestAnimationFrame(frame);
  };
  R.frame = frame;
  const vis = () => { if (!R) return; cancelAnimationFrame(R.raf); if (!document.hidden) R.raf = requestAnimationFrame(frame); };
  document.addEventListener('visibilitychange', vis); R.vis = vis;
  R.raf = requestAnimationFrame(frame);
  return true;
}

function update(cols) {
  if (!R) return;
  (cols || []).slice(0, 6).forEach((c, i) => { if (R.groups[i]) apply(R.groups[i], c); });
  cancelAnimationFrame(R.raf); R.raf = requestAnimationFrame(R.frame);
}

function dispose() {
  if (!R) return;
  R.dead = true; cancelAnimationFrame(R.raf);
  try { document.removeEventListener('visibilitychange', R.vis); if (R.ro) R.ro.disconnect(); R.scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); R.renderer.dispose(); if (R.renderer.domElement.parentNode) R.renderer.domElement.parentNode.removeChild(R.renderer.domElement); } catch (_) { /* nothing */ }
  R = null;
}

window.STOA3D = { mount, update, dispose, frames: () => (R ? R.frames : 0), lit: () => (R ? R.groups.map((g) => (g.userData.lit ? 1 : 0)) : []) };
window.dispatchEvent(new Event('stoa3d'));
