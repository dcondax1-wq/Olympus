// AEGIS shield (ES module): a bronze shield with a gold rim. The rim is the drawdown you still have: it shrinks as the max loss is used (full rim = the whole max loss left, no rim = the floor).
// Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). One mesh, one tube, warm sun, bloom <= .2: light enough for a phone. createShield(canvas) -> { ok, set(model), ... }.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';

const SEG = 120, RAD = 8;

export function createShield(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1.3, 0.1, 60);
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

function outline() {
  const s = new THREE.Shape();
  s.moveTo(0, 1.55);
  s.bezierCurveTo(0.55, 1.35, 1.0, 1.3, 1.25, 1.3);
  s.bezierCurveTo(1.25, 0.2, 1.05, -0.75, 0, -1.65);
  s.bezierCurveTo(-1.05, -0.75, -1.25, 0.2, -1.25, 1.3);
  s.bezierCurveTo(-1.0, 1.3, -0.55, 1.35, 0, 1.55);
  return s;
}

function build(rc, scene, camera, canvas, o) {
  const reduced = !!o.reduced;
  scene.add(new THREE.HemisphereLight(0xf0dcb8, 0x4a3a28, 1.2));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.6); sun.position.set(3, 5, 6); scene.add(sun);          // about 3000 K afternoon sun
  const shape = outline();
  const body = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.22, bevelEnabled: true, bevelThickness: 0.06, bevelSize: 0.06, bevelSegments: 3, curveSegments: 24 }),
    new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.42, metalness: 0.75 }));
  body.position.z = -0.11;
  const pts = shape.getSpacedPoints(SEG).slice(0, SEG).map((p) => new THREE.Vector3(p.x, p.y, 0));
  const curve = new THREE.CatmullRomCurve3(pts, true);
  const tubeGeo = new THREE.TubeGeometry(curve, SEG, 0.075, RAD, true);
  const rimMat = new THREE.MeshStandardMaterial({ color: '#e0b868', roughness: 0.32, metalness: 0.6, emissive: new THREE.Color('#6a5014'), emissiveIntensity: 0.5 });
  const rim = new THREE.Mesh(tubeGeo, rimMat); rim.position.z = 0.2;
  const track = new THREE.Mesh(tubeGeo, new THREE.MeshStandardMaterial({ color: '#4a3a28', roughness: 0.7, metalness: 0.2 })); track.position.z = 0.19; track.scale.setScalar(0.995);
  const boss = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.32, 0.12, 32), new THREE.MeshStandardMaterial({ color: '#c8a24a', roughness: 0.35, metalness: 0.8 })); boss.rotation.x = Math.PI / 2; boss.position.set(0, 0.2, 0.3);
  const group = new THREE.Group(); group.add(body, track, rim, boss); scene.add(group);
  const total = tubeGeo.index.count;
  let want = 1, shown = 1, yaw = 0, drag = null, settled = true;
  function setRim(f) { const segs = Math.round(Math.max(0, Math.min(1, f)) * SEG); rim.visible = segs > 0; tubeGeo.setDrawRange(0, Math.min(total, segs * RAD * 6)); }
  setRim(1);
  camera.position.set(0, 0.1, 6.2); camera.lookAt(0, 0.05, 0);

  const api = {
    ok: true, mode: '3d', rc,
    set(model) { if (model && typeof model.rim === 'number') { want = Math.max(0, Math.min(1, model.rim)); settled = false; } },
    get settled() { return settled; }, get rim() { return shown; }, get yaw() { return yaw; },
    dispose() { try { rc.stop(); rc.dispose(); } catch (_) { /* nothing */ } },
  };
  const down = (e) => { drag = { x: e.clientX, yaw }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (drag) { yaw = Math.max(-0.9, Math.min(0.9, drag.yaw + (e.clientX - drag.x) * 0.008)); } };
  const up = () => { drag = null; };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);

  let t = 0;
  rc.start((dt) => {
    t += dt;
    const k = reduced ? 1 : Math.min(1, dt * 2.6);                       // the rim eases over about a second, slow and smooth
    shown += (want - shown) * k; if (Math.abs(want - shown) < 0.002) { shown = want; settled = true; }
    setRim(shown);
    group.rotation.y = yaw + (reduced || drag ? 0 : Math.sin(t * 0.5) * 0.22);
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix();
    rc.render();
  });
  return api;
}
