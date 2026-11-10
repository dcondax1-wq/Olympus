// KRONOS's marble sundial (three.js r160 from ../jarvis/, the OLYMPUS render core): a round marble dial with twelve gold hour marks and a bronze gnomon. The SHADOW is today's P&L against a typical day:
// strong day = the sun is high = a short shadow; a hard day = a long shadow (terracotta at the tip). Its direction follows the New York clock. Light by design: about 25 meshes, one canvas-free scene,
// bloom <= .25, a dpr cap of 1.5, no frame while hidden. If WebGL or the render core is missing, the page draws the flat twin.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { marble, metal } from '../olympus/materials.js';

const GOLD = '#c8a24a', BRONZE = '#9c6b3c';

function createDial(canvas, opts) {
  const o = opts || {}, O = window.OLYMPUS || null, RM = o.reduced === true;
  const scene = new THREE.Scene(); scene.background = new THREE.Color('#1a140e');
  const camera = new THREE.PerspectiveCamera(34, 1.4, 0.1, 40); camera.position.set(0, 4.6, 5.4); camera.lookAt(0, 0.2, 0);
  const rc = createRenderer({ canvas, scene, camera, maxDpr: 1.5, tint: GOLD, theme: { sky: '#2b2018', fog: '#2a2018', emissive: GOLD, bloom: '#e0b060', accent: GOLD }, bloom: { strength: 0.2, radius: 0.4, threshold: 1.0 } });
  const lite = rc.quality() === 'low' || rc.quality() === 'off';
  scene.add(new THREE.HemisphereLight(0xf0cf9a, 0x3a2a1a, 1.5));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.2); sun.position.set(-2.5, 5, 3); scene.add(sun);

  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(2.05, 2.25, 0.34, lite ? 32 : 64), metal({ kind: 'gold', color: BRONZE })); plinth.position.y = -0.2; scene.add(plinth);
  const dial = new THREE.Mesh(new THREE.CylinderGeometry(1.9, 1.9, 0.12, lite ? 40 : 72), marble({ color: '#e8e1d2', vein: '#6d6252', roughness: 0.25, clearcoat: 0.7 })); dial.position.y = -0.02; scene.add(dial);
  const goldMat = metal({ kind: 'gold' });
  for (let i = 0; i < 12; i++) {                                              // twelve hour marks
    const a = (i / 12) * Math.PI * 2, big = i % 3 === 0;
    const m = new THREE.Mesh(new THREE.BoxGeometry(big ? 0.09 : 0.05, 0.03, big ? 0.3 : 0.18), goldMat);
    m.position.set(Math.sin(a) * 1.62, 0.06, -Math.cos(a) * 1.62); m.rotation.y = a; scene.add(m);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1.9, 0.025, 8, lite ? 48 : 96), goldMat); ring.rotation.x = Math.PI / 2; ring.position.y = 0.05; scene.add(ring);
  const gn = new THREE.Mesh(new THREE.ConeGeometry(0.11, 1.25, 4), metal({ kind: 'gold', color: BRONZE })); gn.position.y = 0.66; scene.add(gn);
  const gnBase = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.26, 0.1, 16), goldMat); gnBase.position.y = 0.05; scene.add(gnBase);

  // the shadow: a flat dark bar that starts at the gnomon's foot; scale.x = length, a coloured tip says gain or loss
  const shMat = new THREE.MeshBasicMaterial({ color: '#0c0906', transparent: true, opacity: 0.6, depthWrite: false });
  const tipMat = new THREE.MeshBasicMaterial({ color: GOLD, transparent: true, opacity: 0.9, depthWrite: false });
  const pivot = new THREE.Group(); pivot.position.y = 0.075; scene.add(pivot);
  const bar = new THREE.Mesh(new THREE.BoxGeometry(1, 0.01, 0.2), shMat); bar.position.x = 0.5; pivot.add(bar);
  const tip = new THREE.Mesh(new THREE.CircleGeometry(0.11, 20), tipMat); tip.rotation.x = -Math.PI / 2; tip.position.set(1, 0.012, 0); pivot.add(tip);

  const S = { len: 1, want: 1, ang: 0, wantAng: 0, tone: 'none' };
  const COL = { gain: '#7f8a52', loss: '#c96a4a', flat: GOLD, none: GOLD };
  let dirty = true, disposed = false, t = 0;
  function apply() {
    pivot.rotation.y = S.ang - Math.PI / 2;                                  // noon: the shadow points at the viewer
    const L = S.len * 1.45; bar.scale.x = L; bar.position.x = L / 2; tip.position.x = L; tip.scale.setScalar(1 + (S.len > 1.4 ? 0.2 : 0));
    tipMat.color.set(COL[S.tone] || GOLD);
  }
  function resize() { const w = canvas.clientWidth || 320, h = canvas.clientHeight || 220; camera.aspect = w / h; camera.updateProjectionMatrix(); rc.resize(w, h); dirty = true; }
  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null; if (ro) ro.observe(canvas);
  resize(); apply();

  let last = performance.now(), lastTick = 0;
  function loop(now) {
    if (disposed) return;
    requestAnimationFrame(loop);
    const dt = Math.min(0.25, (now - last) / 1000); last = now;
    const gap = O && O.frameGap ? O.frameGap() : 0;
    if ((O ? O.hidden() : document.hidden) || (gap && now - lastTick < gap - 3)) return;
    lastTick = now;
    const moving = Math.abs(S.want - S.len) > 0.002 || Math.abs(S.wantAng - S.ang) > 0.002;
    if (moving) { const k = RM ? 1 : Math.min(1, dt * 3); S.len += (S.want - S.len) * k; S.ang += (S.wantAng - S.ang) * k; dirty = true; }
    if (!RM) { t += dt; gn.rotation.y = t * 0.2; dirty = true; }
    if (dirty) { apply(); rc.render(); dirty = !RM; }
  }
  requestAnimationFrame(loop);
  return {
    lite, quality: () => rc.quality(), passes: () => rc.passes(),
    set(shadow, angle, tone) { S.want = shadow; S.wantAng = angle; S.tone = tone; if (RM) { S.len = shadow; S.ang = angle; } dirty = true; },
    get shadow() { return S.want; }, get shown() { return S.len; }, get tone() { return S.tone; },
    dispose() { disposed = true; if (ro) ro.disconnect(); try { rc.dispose(); } catch (_) { /* gone */ } },
  };
}
window.KRONOS_DIAL = { createDial };   // read by kronos.js (a second module tag, so a failed 3D load never stops the page)
