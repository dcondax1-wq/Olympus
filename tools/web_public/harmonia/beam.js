// HARMONIA beam (ES module): a marble balance beam on a column, with gold weights. The left pan holds the money machines that depend on the NQ bots, the right pan the ones that do not; each weight is one stream,
// sized by its monthly estimate. The beam tilts toward the heavier side, slowly. Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm sun, bloom <= .2, about twenty meshes:
// light enough for a phone. createBeam(canvas) -> { ok, set({ left: [{usd}], right: [{usd}], tilt }), ... }. If WebGL or the render core is not there, ok is false and the page shows its flat balance.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';

const HALF = 2.3, DROP = 1.25;

export function createBeam(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1.3, 0.1, 60);
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
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.6); sun.position.set(3, 6, 6); scene.add(sun);          // about 3000 K afternoon sun
  const marble = new THREE.MeshStandardMaterial({ color: '#d9d2c3', roughness: 0.4, metalness: 0.02 });
  const bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.42, metalness: 0.7 });
  const gold = new THREE.MeshStandardMaterial({ color: '#e0b868', roughness: 0.32, metalness: 0.6, emissive: new THREE.Color('#6a5014'), emissiveIntensity: 0.5 });
  const olive = new THREE.MeshStandardMaterial({ color: '#8a9456', roughness: 0.4, metalness: 0.5 });
  const floor = new THREE.Mesh(new THREE.CircleGeometry(9, 48), new THREE.MeshStandardMaterial({ color: '#8f8574', roughness: 0.6 })); floor.rotation.x = -Math.PI / 2; floor.position.y = -0.02; scene.add(floor);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.3, 0.3, 36), marble); base.position.y = 0.13; scene.add(base);
  const column = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.26, 3.1, 24), marble); column.position.y = 1.7; scene.add(column);
  const hub = new THREE.Mesh(new THREE.SphereGeometry(0.3, 24, 16), bronze); hub.position.y = 3.3; scene.add(hub);
  const bar = new THREE.Mesh(new THREE.BoxGeometry(HALF * 2, 0.14, 0.2), bronze); bar.position.y = 3.3;
  const pivot = new THREE.Group(); pivot.position.y = 0; pivot.add(bar); scene.add(pivot);
  const panG = new THREE.CylinderGeometry(0.85, 0.7, 0.1, 32), wireG = new THREE.CylinderGeometry(0.012, 0.012, 1, 6);
  const mkPan = () => {
    const g = new THREE.Group(), pan = new THREE.Mesh(panG, bronze); g.add(pan);
    for (const s of [-1, 1]) { const w = new THREE.Mesh(wireG, bronze); w.scale.y = DROP; w.position.set(s * 0.225, DROP / 2, 0); w.rotation.z = s * 0.345; g.add(w); }
    const load = new THREE.Group(); load.position.y = 0.05; g.add(load); scene.add(g); return { g, load };
  };
  const L = mkPan(), R = mkPan();
  const wgeo = new THREE.CylinderGeometry(1, 1, 1, 24);
  let want = 0, shown = 0, yaw = 0, drag = null, settled = true, t = 0, count = [0, 0];
  function fill(pan, list, mat) {
    while (pan.load.children.length) pan.load.remove(pan.load.children[0]);
    const tot = list.reduce((s, x) => s + Math.max(0, x.usd || 0), 0) || 1; let y = 0;
    list.filter((x) => (x.usd || 0) > 0).forEach((x, i) => {
      const r = 0.22 + 0.4 * Math.sqrt(Math.max(0, x.usd) / tot), h = 0.16 + 0.22 * Math.sqrt(Math.max(0, x.usd) / tot);
      const m = new THREE.Mesh(wgeo, i % 2 ? mat : gold); m.scale.set(r, h, r); m.position.set((i % 2 ? 0.08 : -0.08), y + h / 2, 0); pan.load.add(m); y += h;
    });
    return pan.load.children.length;
  }
  function place() {
    const c = Math.cos(shown), sn = Math.sin(shown);
    bar.rotation.z = shown;                                                       // the bar turns about its own middle (the hub); the pans hang straight down from its ends
    L.g.position.set(-HALF * c, 3.3 - HALF * sn - DROP, 0); R.g.position.set(HALF * c, 3.3 + HALF * sn - DROP, 0);
  }
  const api = {
    ok: true, mode: '3d', rc,
    set(model) {
      if (!model) return;
      if (Array.isArray(model.left) && Array.isArray(model.right)) count = [fill(L, model.left, olive), fill(R, model.right, olive)];
      if (typeof model.tilt === 'number') want = Math.max(-0.45, Math.min(0.45, model.tilt));
      settled = false;
    },
    get settled() { return settled; }, get tilt() { return shown; }, get weights() { return count; },
    dispose() { try { rc.stop(); rc.dispose(); } catch (_) { /* nothing */ } },
  };
  const down = (e) => { drag = { x: e.clientX, yaw }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (drag) yaw = Math.max(-0.7, Math.min(0.7, drag.yaw + (e.clientX - drag.x) * 0.006)); };
  const up = () => { drag = null; };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
  place();
  rc.start((dt) => {
    t += dt;
    const k = reduced ? 1 : Math.min(1, dt * 1.8);                       // the beam swings slowly: about a second and a half
    shown += (want - shown) * k; if (Math.abs(want - shown) < 0.002) { shown = want; settled = true; }
    place();
    const sway = reduced || drag ? 0 : Math.sin(t * 0.4) * 0.12;
    camera.position.set(Math.sin(yaw + sway) * 10.5, 3.6, Math.cos(yaw + sway) * 10.5); camera.lookAt(0, 2.2, 0);
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix();
    rc.render();
  });
  return api;
}
