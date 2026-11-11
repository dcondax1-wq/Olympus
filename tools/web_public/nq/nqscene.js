// NQ 3D scene (optional ES module): three marble columns on a stepped marble floor, one per bot, each with a bronze bowl on its capital.
// A gold flame burns in the bowl ONLY when that bot reported in the last 20 minutes; a silent bot's column stands in the shade with a cold bowl.
// Warm dusk light, warm fog, no bloom, nothing emissive but the flame itself. Registers window.NQ3D = { mount(box, cols), update(cols), dispose() } and fires 'nq3d'.
// nq.js draws the 2D columns first and hides them only when mount() returns true (WebGL present, not LITE).
import * as THREE from '../jarvis/three.module.min.js';

const MARBLE = 0xd8cfbd, WARM = 0xf3e2b8, SHADE = 0xa59c8b, GOLD = 0xe0b060, BRONZE = 0x9c6b3c, CAP = 0xbdb3a0;
let R = null;

function webgl() { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (_) { return false; } }

function column(x) {
  const g = new THREE.Group(); g.position.x = x;
  const mat = new THREE.MeshStandardMaterial({ color: MARBLE, roughness: 0.55, metalness: 0.03 });
  const capMat = new THREE.MeshStandardMaterial({ color: CAP, roughness: 0.5 });
  const base = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.26, 1.5), mat); base.position.y = 0.13; g.add(base);
  const torus = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.66, 0.16, 24), mat); torus.position.y = 0.34; g.add(torus);
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.54, 3.6, 24), mat); shaft.position.y = 0.42 + 1.8; g.add(shaft);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.46, 0.2, 24), capMat); neck.position.y = 4.12; g.add(neck);
  const cap = new THREE.Mesh(new THREE.BoxGeometry(1.36, 0.22, 1.36), capMat); cap.position.y = 4.33; g.add(cap);
  const bowl = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.22, 0.26, 20), new THREE.MeshStandardMaterial({ color: BRONZE, roughness: 0.45, metalness: 0.55 })); bowl.position.y = 4.57; g.add(bowl);
  const flame = new THREE.Group(); flame.position.y = 4.7;
  const outer = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.9, 14), new THREE.MeshBasicMaterial({ color: GOLD })); outer.position.y = 0.45; flame.add(outer);
  const inner = new THREE.Mesh(new THREE.ConeGeometry(0.14, 0.5, 10), new THREE.MeshBasicMaterial({ color: 0xf6dfa2 })); inner.position.y = 0.3; flame.add(inner);
  g.add(flame);
  const light = new THREE.PointLight(0xffc477, 0, 7); light.position.y = 5.1; g.add(light);
  g.userData = { mat, capMat, flame, light, lit: false, k: 0 };
  return g;
}
function apply(g, c) {
  const u = g.userData; u.lit = !!(c && c.lit);
  u.mat.color.setHex(u.lit ? WARM : SHADE);
  u.capMat.color.setHex(u.lit ? 0xd9c79c : 0x968d7d);
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
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x2a2016); scene.fog = new THREE.Fog(0x2a2016, 15, 34);
  const camera = new THREE.PerspectiveCamera(34, 2.2, 0.1, 80);
  scene.add(new THREE.HemisphereLight(0xffe2b8, 0x3a2a1c, 0.75));
  const sun = new THREE.DirectionalLight(0xffd9a0, 1.1); sun.position.set(5, 9, 7); scene.add(sun);
  const stone = new THREE.MeshStandardMaterial({ color: 0xcfc4b2, roughness: 0.6 });
  const step1 = new THREE.Mesh(new THREE.BoxGeometry(11.5, 0.3, 4.4), stone); step1.position.y = -0.15; scene.add(step1);
  const step2 = new THREE.Mesh(new THREE.BoxGeometry(13, 0.3, 5.6), new THREE.MeshStandardMaterial({ color: 0xb5ab99, roughness: 0.65 })); step2.position.y = -0.45; scene.add(step2);
  const groups = [], list = (cols || []).slice(0, 3), n = list.length;
  list.forEach((c, i) => { const g = column((i - (n - 1) / 2) * 3.4); apply(g, c); g.userData.k = g.userData.lit ? 1 : 0; scene.add(g); groups.push(g); });
  R = { renderer, scene, camera, groups, box, frames: 0, raf: 0, t0: performance.now(), reduce, ro: null, dead: false, r: 16 };
  const size = () => {
    const w = Math.max(160, box.clientWidth || 320), h = Math.max(80, box.clientHeight || 160);
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    R.r = w / h < 1.9 ? 17.5 : 14.5; camera.position.set(0, 4.2, R.r); camera.lookAt(0, 2.7, 0);
  };
  size();
  const frame = (now, once) => {
    if (!R || R.dead) return;
    const t = (now - R.t0) / 1000;
    for (const g of groups) {
      const u = g.userData, want = u.lit ? 1 : 0;
      u.k += (want - u.k) * (reduce ? 1 : 0.08);
      u.flame.visible = u.k > 0.05;
      const flick = reduce || !u.lit ? 0 : Math.sin(t * 2.3 + g.position.x) * 0.07 + Math.sin(t * 3.7 + g.position.x * 2) * 0.03;
      u.flame.scale.set(0.85 + 0.15 * u.k, 0.55 + 0.45 * u.k + flick, 0.85 + 0.15 * u.k);
      u.light.intensity = (1.7 + flick * 2) * u.k;
    }
    if (!reduce) { const a = Math.sin(t * 0.14) * 0.12; camera.position.x = Math.sin(a) * R.r; camera.position.z = Math.cos(a) * R.r; camera.lookAt(0, 2.7, 0); }
    renderer.render(scene, camera); R.frames++;
    if (!once && !reduce) R.raf = requestAnimationFrame(frame);
  };
  R.frame = frame;
  if (typeof ResizeObserver === 'function') { R.ro = new ResizeObserver(() => { size(); frame(performance.now(), true); }); R.ro.observe(box); }
  const vis = () => { if (!R) return; cancelAnimationFrame(R.raf); if (!document.hidden) R.raf = requestAnimationFrame(frame); };
  document.addEventListener('visibilitychange', vis); R.vis = vis;
  R.raf = requestAnimationFrame(frame);
  return true;
}

function update(cols) {
  if (!R) return;
  (cols || []).slice(0, 3).forEach((c, i) => { if (R.groups[i]) apply(R.groups[i], c); });
  cancelAnimationFrame(R.raf); R.raf = requestAnimationFrame(R.frame);
}

function dispose() {
  if (!R) return;
  R.dead = true; cancelAnimationFrame(R.raf);
  try { document.removeEventListener('visibilitychange', R.vis); if (R.ro) R.ro.disconnect(); R.scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); R.renderer.dispose(); if (R.renderer.domElement.parentNode) R.renderer.domElement.parentNode.removeChild(R.renderer.domElement); } catch (_) { /* nothing */ }
  R = null;
}

window.NQ3D = { mount, update, dispose, frames: () => (R ? R.frames : 0), lit: () => (R ? R.groups.map((g) => (g.userData.lit ? 1 : 0)) : []) };
window.dispatchEvent(new Event('nq3d'));
