// EPILOGUE scene (ES module, optional): a marble scroll that unrolls across the card, with a gold ribbon running along it and seven knots, one for each day of the week
// (olive = a winning day, terracotta = a losing day, bronze = no trade). Warm 3000 K key light, warm fog, plain lit materials, no bloom. If WebGL is missing the canvas is hidden and the page
// works without it. Reduced motion or LITE draws the scroll already unrolled as one still frame; a hidden tab draws nothing. three.js is Jarvis's copy.
import * as THREE from '../jarvis/three.module.min.js';

const O = window.OLYMPUS || null;
const cv = document.getElementById('stage'), box = cv ? cv.parentElement : null;
const W = 5.2, H = 2.6, R = 0.34;                      // paper width and height, roll radius
const st = { renderer: null, scene: null, camera: null, paper: null, ribbon: null, rollL: null, rollR: null, knots: [], k: 0, raf: 0, t0: 0, still: false, dead: false, ready: false, days: 0 };

function build() {
  const lite = !!(O && O.lite && O.lite()), reduced = !!(O && O.reduced && O.reduced());
  st.still = lite || reduced;
  const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: !lite, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lite ? 1 : 2)); renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene(); scene.fog = new THREE.Fog(0x1a1611, 9, 20);
  const camera = new THREE.PerspectiveCamera(36, 1.8, 0.1, 40); camera.position.set(0, 0.5, 8.2); camera.lookAt(0, 0, 0);
  const sun = new THREE.DirectionalLight(0xffd7a0, 2.3); sun.position.set(-3, 5, 6); scene.add(sun);
  scene.add(new THREE.HemisphereLight(0xffe6c4, 0x3a2e22, 1.0));
  const marble = new THREE.MeshStandardMaterial({ color: 0xf1e9db, roughness: 0.42 }), bronze = new THREE.MeshStandardMaterial({ color: 0x9c6b3c, roughness: 0.45, metalness: 0.6 });
  const gold = new THREE.MeshStandardMaterial({ color: 0xc8a24a, roughness: 0.35, metalness: 0.8 }), sheet = new THREE.MeshStandardMaterial({ color: 0xe8dcc4, roughness: 0.7, side: THREE.DoubleSide });
  // the paper: a plane that grows from the left roll to the right
  const paper = new THREE.Mesh(new THREE.PlaneGeometry(1, H), sheet); paper.position.z = 0; scene.add(paper); st.paper = paper;
  // two rolls with bronze caps
  const roll = () => { const g = new THREE.Group(); const cyl = new THREE.Mesh(new THREE.CylinderGeometry(R, R, H + 0.3, 28), marble); g.add(cyl);
    for (const s of [-1, 1]) { const cap = new THREE.Mesh(new THREE.CylinderGeometry(R + 0.07, R + 0.07, 0.08, 28), bronze); cap.position.y = s * (H / 2 + 0.2); g.add(cap); } scene.add(g); return g; };
  st.rollL = roll(); st.rollR = roll();
  // the gold ribbon along the middle and seven day knots
  const ribbon = new THREE.Mesh(new THREE.BoxGeometry(1, 0.07, 0.04), gold); scene.add(ribbon); st.ribbon = ribbon;
  const tones = { up: new THREE.MeshStandardMaterial({ color: 0x7f8a52, roughness: 0.5 }), down: new THREE.MeshStandardMaterial({ color: 0xc96a4a, roughness: 0.5 }), none: bronze };
  for (let i = 0; i < 7; i++) { const m = new THREE.Mesh(new THREE.SphereGeometry(0.16, 20, 14), tones.none); scene.add(m); st.knots.push(m); }
  st.tones = tones;
  Object.assign(st, { renderer, scene, camera });
  size(); layout(1);
}

function size() {
  if (!st.renderer || !box) return;
  const w = Math.max(160, box.clientWidth || 340), hh = Math.max(110, box.clientHeight || 200);
  st.renderer.setSize(w, hh, false); st.camera.aspect = w / hh; st.camera.updateProjectionMatrix();
  st.camera.position.z = w / hh < 1.5 ? 10 : 8.2;
}

/** k = how much of the scroll is unrolled (0..1) */
function layout(k) {
  const e = k * k * (3 - 2 * k), half = W / 2;
  st.rollL.position.set(-half - 0.05, 0, 0); st.rollR.position.set(-half + W * e + 0.05, 0, 0);
  st.paper.scale.x = Math.max(0.001, W * e); st.paper.position.x = -half + (W * e) / 2;
  st.ribbon.scale.x = Math.max(0.001, W * e * 0.94); st.ribbon.position.set(-half + (W * e) / 2, 0, 0.03);
  st.knots.forEach((m, i) => { const x = -half + W * 0.06 + (W * 0.88 * i) / 6; m.visible = x <= -half + W * e - 0.05; m.position.set(x, 0, 0.1); });
}

function paint(days) {
  if (!st.scene) return;
  const d = Array.isArray(days && days.perDay) ? days.perDay : [], tr = Array.isArray(days && days.traded) ? days.traded : [];
  st.knots.forEach((m, i) => { m.material = !tr[i] ? st.tones.none : d[i] > 0 ? st.tones.up : d[i] < 0 ? st.tones.down : st.tones.none; m.scale.setScalar(tr[i] ? 1.15 : 0.8); });
}

function frame(ts) {
  if (st.dead || !st.renderer) return;
  if (!st.t0) st.t0 = ts;
  const t = (ts - st.t0) / 1000;
  st.k = st.still ? 1 : Math.min(1, t / 2.6);
  layout(st.k);
  if (!st.still) { st.camera.position.x = Math.sin(t * 0.15) * 0.5; st.camera.lookAt(0, 0, 0); }
  st.renderer.render(st.scene, st.camera);
  if (!st.ready) { st.ready = true; document.documentElement.setAttribute('data-stage', 'on'); }
  if (!st.still) st.raf = requestAnimationFrame(frame);
}

function start() {
  if (!cv || !box) return;
  try { build(); } catch (_) { box.classList.add('off'); return; }
  window.addEventListener('epilogue:model', (e) => { try { st.days = (e.detail && e.detail.traded || []).filter(Boolean).length; paint(e.detail); if (st.still) frame(0); } catch (_) { /* keep the last picture */ } });
  window.addEventListener('resize', () => { size(); if (st.still) frame(0); });
  document.addEventListener('visibilitychange', () => { cancelAnimationFrame(st.raf); st.raf = 0; if (!document.hidden && !st.still) st.raf = requestAnimationFrame(frame); });
  window.addEventListener('pagehide', () => { st.dead = true; cancelAnimationFrame(st.raf); try { st.renderer.dispose(); } catch (_) { /* gone */ } });
  const m = window.EPILOGUE;
  if (m && m.S && m.S.model) paint({ perDay: m.S.model.perDay, traded: m.S.model.traded });
  if (st.still) frame(0); else st.raf = requestAnimationFrame(frame);
  window.EPILOGUE3D = { ready: () => st.ready, unrolled: () => st.k, days: () => st.days, still: () => st.still };
}
start();
