// HELIOS sun (ES module): a marble sun-disc with a gold rim rising over a row of marble columns, with one gold ray for each good sign of the morning (0 to 6). The higher the sun, the more is in order.
// Reduced motion: the sun stands still at its height. Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm light (about 3000 K), bloom <= .2, about twenty meshes: light enough for a phone.
// createSun(canvas, { reduced }) -> { ok, set({ rise, rays }), ... }. If WebGL or the render core is not there, ok is false and the page shows its flat sunrise.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';

const MAX_RAYS = 6;

export function createSun(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1.3, 0.1, 60);
    scene.background = new THREE.Color('#3a2a1c');
    rc = createRenderer({ canvas, scene, camera, maxDpr: 2, tint: '#c8a24a', env: 'night',
      theme: { sky: '#5a3c22', fog: '#3a2a1c', emissive: '#c8a24a', bloom: '#e0b060', accent: '#c8a24a' }, bloom: { strength: 0.2, radius: 0.5, threshold: 1.0 } });
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
  scene.add(new THREE.HemisphereLight(0xf0dcb8, 0x4a3a28, 1.1));
  const sunLight = new THREE.DirectionalLight(0xffd9a0, 2.4); sunLight.position.set(0, 4, 8); scene.add(sunLight);
  const marble = new THREE.MeshStandardMaterial({ color: '#d9d2c3', roughness: 0.4, metalness: 0.02 });
  const gold = new THREE.MeshStandardMaterial({ color: '#e0b868', roughness: 0.32, metalness: 0.6, emissive: new THREE.Color('#6a5014'), emissiveIntensity: 0.55 });
  const floor = new THREE.Mesh(new THREE.BoxGeometry(14, 0.3, 5), new THREE.MeshStandardMaterial({ color: '#8f8574', roughness: 0.6 })); floor.position.set(0, -0.15, 0.6); scene.add(floor);
  const cg = new THREE.CylinderGeometry(0.28, 0.32, 2.3, 20), capG = new THREE.BoxGeometry(0.9, 0.16, 0.9), baseG = new THREE.BoxGeometry(0.85, 0.14, 0.85);
  [-4.4, -2.2, 0, 2.2, 4.4].forEach((x) => {
    const c = new THREE.Mesh(cg, marble); c.position.set(x, 1.3, 0); scene.add(c);
    const t = new THREE.Mesh(capG, marble); t.position.set(x, 2.52, 0); scene.add(t);
    const b = new THREE.Mesh(baseG, marble); b.position.set(x, 0.07, 0); scene.add(b);
  });
  const lintel = new THREE.Mesh(new THREE.BoxGeometry(10.2, 0.28, 0.9), marble); lintel.position.set(0, 2.74, 0); scene.add(lintel);
  // the sun: a marble disc with a gold rim, behind the columns
  const sun = new THREE.Group(); sun.position.z = -1.4; scene.add(sun);
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(1.05, 1.05, 0.14, 48), marble); disc.rotation.x = Math.PI / 2; sun.add(disc);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(1.05, 0.07, 10, 64), gold); sun.add(rim);
  const core = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.18, 32), gold); core.rotation.x = Math.PI / 2; sun.add(core);
  const rays = [];
  for (let i = 0; i < MAX_RAYS; i++) {
    const r = new THREE.Mesh(new THREE.BoxGeometry(0.16, 1.1, 0.06), gold), a = Math.PI * (0.12 + 0.76 * i / (MAX_RAYS - 1));     // a fan over the top half: 22 to 158 degrees
    const g = new THREE.Group(); g.rotation.z = a - Math.PI / 2; r.position.y = 1.05 + 0.65; g.add(r); g.visible = false; sun.add(g); rays.push(g);
  }
  let want = { rise: 0.5, rays: 0 }, shown = { rise: reduced ? 0.5 : 0, rays: 0 }, yaw = 0, drag = null, settled = true;
  function place() {
    sun.position.y = -1.0 + shown.rise * 3.6;                              // below the floor line at 0, fully up at 1
    const n = Math.round(shown.rays);
    rays.forEach((g, i) => { g.visible = i < n; });
  }
  place();
  const api = {
    ok: true, mode: '3d', rc,
    set(m) { if (m && typeof m.rise === 'number') { want = { rise: Math.max(0, Math.min(1, m.rise)), rays: Math.max(0, Math.min(MAX_RAYS, Math.round(m.rays || 0))) }; settled = false; if (reduced) { shown = { ...want }; place(); settled = true; } } },
    get settled() { return settled; }, get rise() { return shown.rise; }, get rays() { return Math.round(shown.rays); },
    dispose() { try { rc.stop(); rc.dispose(); } catch (_) { /* nothing */ } },
  };
  const down = (e) => { drag = { x: e.clientX, yaw }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (drag) yaw = Math.max(-0.5, Math.min(0.5, drag.yaw + (e.clientX - drag.x) * 0.005)); };
  const up = () => { drag = null; };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
  rc.start((dt) => {
    if (!reduced) {
      const k = Math.min(1, dt * 1.4);                                    // the sun rises slowly: about two seconds
      shown.rise += (want.rise - shown.rise) * k; shown.rays += (want.rays - shown.rays) * Math.min(1, dt * 3);
      if (Math.abs(want.rise - shown.rise) < 0.002 && Math.abs(want.rays - shown.rays) < 0.05) { shown = { ...want }; settled = true; }
      place();
    }
    camera.position.set(Math.sin(yaw) * 11, 2.6, Math.cos(yaw) * 11); camera.lookAt(0, 1.9, 0);
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix();
    rc.render();
  });
  return api;
}
