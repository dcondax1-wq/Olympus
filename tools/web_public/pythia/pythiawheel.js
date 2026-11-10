// PYTHIA's marble wheel of days (three.js r160 from ../jarvis/, the OLYMPUS render core): a round marble dial with fourteen slots, one for each of the next 14 days, and an event pillar standing in each slot
// (tall = a big release, short = a light day, a bronze stub = a calm day, blue = the market is closed). Today's slot wears a gold ring; the selected day's pillar is lifted. Tap a pillar to open that day.
// Light by design: 14 cylinders, a marble disc, a bronze rim, bloom <= .25, a dpr cap of 1.5, no frame while hidden. If WebGL or the render core is missing, the page draws the flat twin.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { marble, metal } from '../olympus/materials.js';

const GOLD = '#c8a24a', BRONZE = '#9c6b3c';
const COL = { high: '#c96a4a', med: '#e0b060', low: '#7f8a52', calm: '#9c6b3c', closed: '#4b7a99' };
const HEIGHT = { high: 1.5, med: 0.95, low: 0.55, calm: 0.2, closed: 0.35 };

function createWheel(canvas, days, opts) {
  const o = opts || {}, O = window.OLYMPUS || null, RM = o.reduced === true;
  const scene = new THREE.Scene(); scene.background = new THREE.Color('#1a140e');
  const camera = new THREE.PerspectiveCamera(36, 1.5, 0.1, 40); camera.position.set(0, 4.3, 5.9); camera.lookAt(0, 0.35, 0);
  const rc = createRenderer({ canvas, scene, camera, maxDpr: 1.5, tint: GOLD, theme: { sky: '#2b2018', fog: '#2a2018', emissive: GOLD, bloom: '#e0b060', accent: GOLD }, bloom: { strength: 0.2, radius: 0.4, threshold: 1.0 } });
  const lite = rc.quality() === 'low' || rc.quality() === 'off';
  scene.add(new THREE.HemisphereLight(0xf0cf9a, 0x3a2a1a, 1.5));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.2); sun.position.set(-3, 5, 3); scene.add(sun);
  const root = new THREE.Group(); scene.add(root);

  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.8, 0.3, lite ? 40 : 72), metal({ kind: 'gold', color: BRONZE })); plinth.position.y = -0.22; root.add(plinth);
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(2.5, 2.5, 0.12, lite ? 40 : 72), marble({ color: '#e8e1d2', vein: '#6d6252', roughness: 0.25, clearcoat: 0.7 })); disc.position.y = -0.03; root.add(disc);
  const goldMat = metal({ kind: 'gold' });
  const rim = new THREE.Mesh(new THREE.TorusGeometry(2.5, 0.03, 8, lite ? 48 : 96), goldMat); rim.rotation.x = Math.PI / 2; rim.position.y = 0.04; root.add(rim);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.34, 0.16, 20), goldMat); hub.position.y = 0.06; root.add(hub);

  const N = days.length, R = 1.85, pillars = [];
  const base = new THREE.CylinderGeometry(0.2, 0.2, 1, lite ? 12 : 20);
  days.forEach((d, i) => {
    const a = (i / N) * Math.PI * 2, x = Math.sin(a) * R, z = -Math.cos(a) * R;
    const mat = new THREE.MeshStandardMaterial({ color: COL[d.risk] || COL.calm, roughness: 0.45, metalness: 0.25 });
    const m = new THREE.Mesh(base, mat); const h = HEIGHT[d.risk] || 0.2; m.scale.set(1, h, 1); m.position.set(x, 0.04 + h / 2, z); m.userData = { i, h, x, z };
    root.add(m); pillars.push(m);
    const foot = new THREE.Mesh(new THREE.RingGeometry(0.24, 0.3, 24), new THREE.MeshBasicMaterial({ color: i === 0 ? GOLD : '#6d6252', side: THREE.DoubleSide })); foot.rotation.x = -Math.PI / 2; foot.position.set(x, 0.045, z); root.add(foot);
  });

  let sel = -1, spin = 0, dirty = true, disposed = false;
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  function apply() { root.rotation.y = spin; for (const p of pillars) { const up = p.userData.i === sel ? 0.28 : 0; p.position.y += (0.04 + p.userData.h / 2 + up - p.position.y) * (RM ? 1 : 0.25); } }
  function resize() { const w = canvas.clientWidth || 320, h = canvas.clientHeight || 210; camera.aspect = w / h; camera.updateProjectionMatrix(); rc.resize(w, h); dirty = true; }
  function pick(ev) {
    const r = canvas.getBoundingClientRect(); ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -(((ev.clientY - r.top) / r.height) * 2 - 1)); ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(pillars, false)[0]; if (hit && o.onPick) o.onPick(hit.object.userData.i);
  }
  canvas.addEventListener('pointerup', pick);
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
    if (!RM) { spin += dt * 0.05; dirty = true; }
    apply(); if (dirty) { rc.render(); dirty = pillars.some((p) => Math.abs(p.position.y - (0.04 + p.userData.h / 2 + (p.userData.i === sel ? 0.28 : 0))) > 0.003) || !RM; }
  }
  requestAnimationFrame(loop);
  return {
    lite, count: pillars.length, quality: () => rc.quality(), passes: () => rc.passes(),
    select(i) { sel = i; dirty = true; }, get selected() { return sel; },
    screenOf(i) { const p = pillars.find((x) => x.userData.i === i); if (!p) return null; root.updateMatrixWorld(true); const v = p.getWorldPosition(new THREE.Vector3()); v.project(camera); const r = canvas.getBoundingClientRect(); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height, front: v.z < 1 }; },
    dispose() { disposed = true; canvas.removeEventListener('pointerup', pick); if (ro) ro.disconnect(); try { rc.dispose(); } catch (_) { /* gone */ } },
  };
}
window.PYTHIA_WHEEL = { createWheel };   // read by pythia.js (a second module tag, so a failed 3D load never stops the page)
