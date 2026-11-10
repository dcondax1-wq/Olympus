// COMPASS rose (ES module): a bronze compass rose on a marble disc. Four gold points mark north (money at risk now), east (money to gain), south (habits) and west (feeds); the needle swings to the bearing of the top action.
// Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm sun, bloom <= .2, about ten meshes: light enough for a phone. createRose(canvas) -> { ok, set({ bearing }), ... }.
// If WebGL or the render core is not there, ok is false and the page shows its flat compass.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';

export function createRose(canvas, opts) {
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
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.6); sun.position.set(3, 7, 4); scene.add(sun);          // about 3000 K afternoon sun
  const marble = new THREE.MeshStandardMaterial({ color: '#d9d2c3', roughness: 0.4, metalness: 0.02 });
  const bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.42, metalness: 0.7 });
  const gold = new THREE.MeshStandardMaterial({ color: '#e0b868', roughness: 0.32, metalness: 0.6, emissive: new THREE.Color('#6a5014'), emissiveIntensity: 0.5 });
  const terra = new THREE.MeshStandardMaterial({ color: '#c96a4a', roughness: 0.5, metalness: 0.2 });
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.7, 0.2, 64), marble); scene.add(disc);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(2.25, 0.08, 10, 80), bronze); ring.rotation.x = Math.PI / 2; ring.position.y = 0.12; scene.add(ring);
  const ring2 = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.03, 8, 64), bronze); ring2.rotation.x = Math.PI / 2; ring2.position.y = 0.11; scene.add(ring2);
  // four points: a flat diamond each, lying on the disc, pointing outward (north is -z, east is +x)
  const pt = () => { const s = new THREE.Shape(); s.moveTo(0, 2.1); s.lineTo(0.28, 0.35); s.lineTo(0, 0); s.lineTo(-0.28, 0.35); s.closePath(); return new THREE.ExtrudeGeometry(s, { depth: 0.07, bevelEnabled: false }); };
  const geo = pt();
  [0, 90, 180, 270].forEach((deg) => {
    const m = new THREE.Mesh(geo, deg === 0 ? gold : bronze); m.rotation.x = -Math.PI / 2; m.position.y = 0.13;
    const g = new THREE.Group(); g.add(m); g.rotation.y = -deg * Math.PI / 180; scene.add(g);
  });
  // the needle: a long thin diamond, gold at the head, terracotta at the tail
  const needle = new THREE.Group();
  const head = new THREE.Mesh(new THREE.ConeGeometry(0.16, 1.9, 4), gold); head.rotation.x = -Math.PI / 2; head.position.set(0, 0.32, -0.95);
  const tail = new THREE.Mesh(new THREE.ConeGeometry(0.16, 1.3, 4), terra); tail.rotation.x = Math.PI / 2; tail.position.set(0, 0.32, 0.65);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.24, 0.16, 24), bronze); hub.position.y = 0.32;
  needle.add(head, tail, hub); scene.add(needle);
  let want = 45, shown = 45, drag = null, settled = true, t = 0, tilt = 0;
  const api = {
    ok: true, mode: '3d', rc,
    set(model) { if (model && typeof model.bearing === 'number') { want = ((model.bearing % 360) + 360) % 360; settled = false; } },
    get settled() { return settled; }, get bearing() { return shown; },
    dispose() { try { rc.stop(); rc.dispose(); } catch (_) { /* nothing */ } },
  };
  const down = (e) => { drag = { y: e.clientY, tilt }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (drag) tilt = Math.max(-0.35, Math.min(0.35, drag.tilt + (e.clientY - drag.y) * 0.004)); };
  const up = () => { drag = null; };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
  rc.start((dt) => {
    t += dt;
    // swing the short way round, slow and smooth (about a second)
    let d = ((want - shown + 540) % 360) - 180;
    const k = reduced ? 1 : Math.min(1, dt * 2.4);
    shown = (shown + d * k + 360) % 360; if (Math.abs(d) < 0.3) { shown = want; settled = true; }
    needle.rotation.y = -shown * Math.PI / 180 + (reduced || !settled ? 0 : Math.sin(t * 1.3) * 0.02);       // a tiny settle wobble once it has arrived
    camera.position.set(0, 7.6 - tilt * 6, 5.2 + tilt * 6); camera.lookAt(0, 0, 0);
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix();
    rc.render();
  });
  return api;
}
