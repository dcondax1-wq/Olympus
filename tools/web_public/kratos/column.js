// KRATOS column (ES module): a marble base and a bronze column whose height is the day's discipline score (0-100), with a gold capital on top and two thin marks at 55 and 75.
// The column rises slowly when the score changes. Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm sun, bloom <= .2, a handful of meshes: light enough for a phone.
// createColumn(canvas) -> { ok, set({ score }), ... }. If WebGL or the render core is not there, ok is false and the page shows its flat column.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';

const H = 4.2;     // the column's height at a score of 100

export function createColumn(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1.3, 0.1, 60);
    scene.background = new THREE.Color('#2a2118');
    rc = createRenderer({ canvas, scene, camera, maxDpr: 2, tint: '#c8a24a', env: 'night',
      theme: { sky: '#3a2c1c', fog: '#2a2118', emissive: '#c8a24a', bloom: '#e0b060', accent: '#c8a24a' }, bloom: { strength: 0.2, radius: 0.5, threshold: 1.0 } });
    const q = rc.quality();
    if (q === 'low' || q === 'off') { rc.dispose(); return { ok: false, mode: 'lite', reason: 'quality ' + q }; }
    return build(rc, scene, camera, canvas, o);
  } catch (e) {
    try { if (rc) rc.dispose(); } catch (_) { /* nothing */ }
    return { ok: false, mode: 'lite', reason: String(e && e.message ? e.message : e) };
  }
}

function build(rc, scene, camera, canvas, o) {
  const reduced = !!o.reduced;
  scene.add(new THREE.HemisphereLight(0xf0dcb8, 0x4a3a28, 1.2));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.6); sun.position.set(4, 6, 5); scene.add(sun);          // about 3000 K afternoon sun
  const marble = new THREE.MeshStandardMaterial({ color: '#d9d2c3', roughness: 0.4, metalness: 0.02 });
  const bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.42, metalness: 0.7 });
  const gold = new THREE.MeshStandardMaterial({ color: '#e0b868', roughness: 0.32, metalness: 0.6, emissive: new THREE.Color('#6a5014'), emissiveIntensity: 0.5 });
  const floor = new THREE.Mesh(new THREE.CircleGeometry(9, 48), new THREE.MeshStandardMaterial({ color: '#8f8574', roughness: 0.6 })); floor.rotation.x = -Math.PI / 2; floor.position.y = -0.02; scene.add(floor);
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(1.25, 1.4, 0.3, 40), marble); plinth.position.y = 0.13; scene.add(plinth);
  const step = new THREE.Mesh(new THREE.CylinderGeometry(0.95, 1.05, 0.16, 40), marble); step.position.y = 0.36; scene.add(step);
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.58, 1, 32), bronze); scene.add(shaft);
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.82, 0.62, 0.22, 32), gold); scene.add(cap);
  const ringG = new THREE.TorusGeometry(0.66, 0.018, 8, 48);
  const marks = [55, 75].map((s) => { const m = new THREE.Mesh(ringG, new THREE.MeshStandardMaterial({ color: '#7f8a52', roughness: 0.5 })); m.rotation.x = Math.PI / 2; m.position.y = 0.44 + (s / 100) * H; scene.add(m); return m; });
  let want = 0, shown = 0, yaw = 0.4, drag = null, settled = true, t = 0;
  function place(score) {
    const h = Math.max(0.05, (score / 100) * H);
    shaft.scale.y = h; shaft.position.y = 0.44 + h / 2; cap.position.y = 0.44 + h + 0.11;
  }
  place(0);
  const api = {
    ok: true, mode: '3d', rc,
    set(model) { if (model && typeof model.score === 'number') { want = Math.max(0, Math.min(100, model.score)); settled = false; } },
    get settled() { return settled; }, get score() { return shown; }, get yaw() { return yaw; },
    dispose() { try { rc.stop(); rc.dispose(); } catch (_) { /* nothing */ } },
  };
  const down = (e) => { drag = { x: e.clientX, yaw }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (drag) yaw = drag.yaw - (e.clientX - drag.x) * 0.008; };
  const up = () => { drag = null; };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
  rc.start((dt) => {
    t += dt;
    const k = reduced ? 1 : Math.min(1, dt * 2.2);                       // slow ease-out: the column rises over about a second
    shown += (want - shown) * k; if (Math.abs(want - shown) < 0.05) { shown = want; settled = true; }
    place(shown);
    if (!reduced && !drag) yaw += dt * 0.12;
    camera.position.set(Math.sin(yaw) * 9.5, 4.6, Math.cos(yaw) * 9.5); camera.lookAt(0, 2.5, 0);
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix();
    rc.render();
  });
  return api;
}
