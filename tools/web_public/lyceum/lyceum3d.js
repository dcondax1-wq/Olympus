// LYCEUM scene (ES module, optional): a marble lecture hall seen from the door. Eight column places stand in two rows; the hall starts with two columns and every rank adds one
// (the empty places show a bare bronze base), and from the fourth rank each new column gets an olive laurel. A lectern waits at the far end. Warm 3000 K light, warm fog, plain lit materials.
// If WebGL is missing the canvas is hidden and the page works without it. Reduced motion or LITE draws one still frame; a hidden tab draws nothing. three.js is Jarvis's copy.
import * as THREE from '../jarvis/three.module.min.js';

const O = window.OLYMPUS || null;
const cv = document.getElementById('stage'), box = cv ? cv.parentElement : null;
const st = { scene: null, renderer: null, camera: null, slots: [], beam: null, raf: 0, t0: performance.now(), still: false, dead: false, ready: false, columns: -1, laurels: 0, rise: [] };

function build() {
  const lite = !!(O && O.lite && O.lite()), reduced = !!(O && O.reduced && O.reduced());
  st.still = lite || reduced;
  const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: !lite, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lite ? 1 : 2)); renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene(); scene.fog = new THREE.Fog(0x1a1611, 9, 22);
  const camera = new THREE.PerspectiveCamera(46, 1.8, 0.1, 50); camera.position.set(0, 2.4, 9.5); camera.lookAt(0, 1.7, 0);
  const sun = new THREE.DirectionalLight(0xffd7a0, 2.3); sun.position.set(-5, 8, 6); scene.add(sun);
  scene.add(new THREE.HemisphereLight(0xffe6c4, 0x3a2e22, 0.95));
  const marble = new THREE.MeshStandardMaterial({ color: 0xf1e9db, roughness: 0.45 }), warm = new THREE.MeshStandardMaterial({ color: 0xd9cdb8, roughness: 0.6 });
  const bronze = new THREE.MeshStandardMaterial({ color: 0x9c6b3c, roughness: 0.45, metalness: 0.6 });
  // floor and steps
  const floor = new THREE.Mesh(new THREE.BoxGeometry(7.2, 0.2, 14), warm); floor.position.set(0, -0.1, -2); scene.add(floor);
  const step = new THREE.Mesh(new THREE.BoxGeometry(3.2, 0.14, 1.6), marble); step.position.set(0, 0.07, -7.4); scene.add(step);
  // the back wall: a plain marble panel with a gold band
  const wall = new THREE.Mesh(new THREE.BoxGeometry(7.2, 4.6, 0.2), new THREE.MeshStandardMaterial({ color: 0xcfc3ad, roughness: 0.8 })); wall.position.set(0, 2.3, -9.1); scene.add(wall);
  const band = new THREE.Mesh(new THREE.BoxGeometry(7.2, 0.12, 0.24), new THREE.MeshStandardMaterial({ color: 0xc8a24a, roughness: 0.4, metalness: 0.7 })); band.position.set(0, 3.3, -9.0); scene.add(band);
  // the lectern
  const lec = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1.1, 0.6), marble); lec.position.set(0, 0.69, -7.6); scene.add(lec);
  const top = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.08, 0.8), bronze); top.position.set(0, 1.28, -7.6); top.rotation.x = -0.18; scene.add(top);
  // eight column places: four rows deep, left and right; the order of the ranks goes front to back, left then right
  const H = 3.4, laurel = new THREE.MeshStandardMaterial({ color: 0x7f8a52, roughness: 0.7 });
  for (let n = 0; n < 8; n++) {
    const row = n >> 1, x = (n & 1 ? 1 : -1) * 2.5, z = 2.2 - row * 2.6, g = new THREE.Group(); g.position.set(x, 0, z);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.5, 0.18, 24), bronze); base.position.y = 0.09; g.add(base);
    const col = new THREE.Group();
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.36, H, 14), marble); shaft.position.y = 0.18 + H / 2; col.add(shaft);
    const cap = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.2, 0.85), marble); cap.position.y = 0.18 + H + 0.1; col.add(cap);
    const wreath = new THREE.Mesh(new THREE.TorusGeometry(0.36, 0.06, 8, 24), laurel); wreath.rotation.x = Math.PI / 2; wreath.position.y = 0.18 + H - 0.35; col.add(wreath);
    g.add(col); scene.add(g);
    st.slots.push({ g, col, wreath, k: 1 });
  }
  const beam = new THREE.Mesh(new THREE.BoxGeometry(6.2, 0.3, 0.7), marble); beam.position.set(0, 0.18 + H + 0.35, 2.2); scene.add(beam); st.beam = beam;
  Object.assign(st, { scene, renderer, camera });
  size();
}

function size() {
  if (!st.renderer || !box) return;
  const w = Math.max(160, box.clientWidth || 340), hh = Math.max(110, box.clientHeight || 200);
  st.renderer.setSize(w, hh, false); st.camera.aspect = w / hh; st.camera.updateProjectionMatrix();
}

/** columns = how many stand (2..8), laurels = how many of them wear a laurel */
function setHall(columns, laurels) {
  if (!st.scene) return;
  const first = st.columns < 0, was = st.columns;
  st.columns = Math.max(0, Math.min(8, columns | 0)); st.laurels = Math.max(0, Math.min(8, laurels | 0));
  st.slots.forEach((s, n) => {
    const on = n < st.columns;
    s.col.visible = on; s.wreath.visible = on && n < st.laurels;
    if (on && !first && n >= was && !st.still) { s.k = 0; st.rise.push(s); } else s.k = 1;
    s.col.scale.y = s.k || 0.01;
  });
  // the architrave spans the front pairs that are complete
  const rows = Math.floor(st.columns / 2); st.beam.visible = rows >= 1; st.beam.scale.set(1, 1, 1);
  if (st.still) frame(0); else if (!st.raf) st.raf = requestAnimationFrame(frame);
}

function frame(ts) {
  if (st.dead || !st.renderer) return;
  const t = st.still ? 0 : (ts - st.t0) / 1000;
  for (const s of st.rise) { s.k = Math.min(1, s.k + 0.025); s.col.scale.y = Math.max(0.01, s.k); }
  st.rise = st.rise.filter((s) => s.k < 1);
  st.camera.position.x = Math.sin(t * 0.12) * 0.9; st.camera.lookAt(0, 1.7, 0);
  st.renderer.render(st.scene, st.camera);
  if (!st.ready) { st.ready = true; document.documentElement.setAttribute('data-stage', 'on'); }
  if (!st.still) st.raf = requestAnimationFrame(frame);
}

function start() {
  if (!cv || !box) return;
  try { build(); } catch (_) { box.classList.add('off'); return; }
  window.addEventListener('lyceum:model', (e) => { try { const d = e.detail || {}; setHall(d.columns, d.laurels); if (!st.still && !st.raf) st.raf = requestAnimationFrame(frame); } catch (_) { /* keep the last picture */ } });
  window.addEventListener('resize', () => { size(); if (st.still) frame(0); });
  document.addEventListener('visibilitychange', () => { cancelAnimationFrame(st.raf); st.raf = 0; if (!document.hidden && !st.still) st.raf = requestAnimationFrame(frame); });
  window.addEventListener('pagehide', () => { st.dead = true; cancelAnimationFrame(st.raf); try { st.renderer.dispose(); } catch (_) { /* gone */ } });
  const m = window.LYCEUM;
  if (m && m.S && m.S.ready) { const hall = m.C.hallFor(m.C.rankFor(m.C.totalXp(m.S.prog)).index); setHall(hall.columns, hall.laurels); } else setHall(2, 0);
  if (!st.still) st.raf = requestAnimationFrame(frame);
  window.LYCEUM3D = { ready: () => st.ready, columns: () => st.columns, laurels: () => st.laurels, still: () => st.still };
}
start();
