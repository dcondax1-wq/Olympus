// PHEME's marble scroll rack (three.js r160 from ../jarvis/, the OLYMPUS render core): a bronze rack holding up to eight marble columns, each topped with a rolled scroll. A column's height is how far NQ travelled on one past
// release day (oldest on the left); the gold bar behind them is an ordinary day, so a tall column rose above it. HISTORY, not a forecast. Tap a column to open that day's row.
// Light by design: 8 columns, a bronze base, bloom <= .25, a dpr cap of 1.5, no frame while hidden. If WebGL or the render core is missing, the page draws the flat twin.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { marble, metal } from '../olympus/materials.js';

const GOLD = '#c8a24a', BRONZE = '#9c6b3c';
const MAXH = 2.3;

function createRack(canvas, opts) {
  const o = opts || {}, O = window.OLYMPUS || null, RM = o.reduced === true;
  const scene = new THREE.Scene(); scene.background = new THREE.Color('#1a140e');
  const camera = new THREE.PerspectiveCamera(34, 1.6, 0.1, 40); camera.position.set(0, 2.4, 7.4); camera.lookAt(0, 1.0, 0);
  const rc = createRenderer({ canvas, scene, camera, maxDpr: 1.5, tint: GOLD, theme: { sky: '#2b2018', fog: '#2a2018', emissive: GOLD, bloom: '#e0b060', accent: GOLD }, bloom: { strength: 0.2, radius: 0.4, threshold: 1.0 } });
  const lite = rc.quality() === 'low' || rc.quality() === 'off';
  scene.add(new THREE.HemisphereLight(0xf0cf9a, 0x3a2a1a, 1.5));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.2); sun.position.set(-3, 5, 4); scene.add(sun);
  const N = 8, GAP = 0.92, x0 = -((N - 1) * GAP) / 2;
  const base = new THREE.Mesh(new THREE.BoxGeometry(N * GAP + 0.7, 0.28, 1.5), metal({ kind: 'gold', color: BRONZE })); base.position.y = -0.14; scene.add(base);
  const marbleMat = marble({ color: '#e8e1d2', vein: '#6d6252', roughness: 0.25, clearcoat: 0.6 });
  const scrollMat = new THREE.MeshStandardMaterial({ color: '#d6c08a', roughness: 0.6, metalness: 0.05 });
  const capMat = metal({ kind: 'gold' });
  const colGeo = new THREE.CylinderGeometry(0.3, 0.34, 1, lite ? 14 : 24), scrollGeo = new THREE.CylinderGeometry(0.16, 0.16, 0.66, lite ? 10 : 16), capGeo = new THREE.CylinderGeometry(0.4, 0.4, 0.07, lite ? 14 : 24);
  const cols = [];
  for (let i = 0; i < N; i++) {
    const g = new THREE.Group(); g.position.set(x0 + i * GAP, 0, 0);
    const col = new THREE.Mesh(colGeo, marbleMat); g.add(col);
    const cap = new THREE.Mesh(capGeo, capMat); g.add(cap);
    const sc = new THREE.Mesh(scrollGeo, scrollMat); sc.rotation.z = Math.PI / 2; g.add(sc);
    g.visible = false; g.userData = { i, h: 0, want: 0, col, cap, sc }; scene.add(g); cols.push(g);
  }
  const line = new THREE.Mesh(new THREE.BoxGeometry(N * GAP + 0.5, 0.05, 0.05), new THREE.MeshBasicMaterial({ color: GOLD })); line.position.set(0, 0.5, -0.7); scene.add(line);
  const lineBack = new THREE.Mesh(new THREE.BoxGeometry(N * GAP + 0.5, 1.2, 0.02), new THREE.MeshBasicMaterial({ color: '#2a2218', transparent: true, opacity: 0.55 })); lineBack.position.set(0, 0.6, -0.75); scene.add(lineBack);

  let sel = -1, dirty = true, disposed = false, lineWant = 0.5, lineH = 0.5;
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  function layout() {
    for (const g of cols) {
      const u = g.userData, h = Math.max(0.05, u.h); u.col.scale.y = h; u.col.position.y = h / 2; u.cap.position.y = h + 0.035; u.sc.position.y = h + 0.17;
      u.col.material = marbleMat; g.scale.setScalar(u.i === sel ? 1.08 : 1);
    }
    line.position.y = lineH;
  }
  function resize() { const w = canvas.clientWidth || 320, h = canvas.clientHeight || 200; camera.aspect = w / h; camera.updateProjectionMatrix(); rc.resize(w, h); dirty = true; }
  function pick(ev) {
    const r = canvas.getBoundingClientRect(); ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -(((ev.clientY - r.top) / r.height) * 2 - 1)); ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(cols.filter((g) => g.visible), true)[0]; if (!hit) return;
    let g = hit.object; while (g && !(g.userData && g.userData.col)) g = g.parent;
    if (g && o.onPick) o.onPick(g.userData.i);
  }
  canvas.addEventListener('pointerup', pick);
  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null; if (ro) ro.observe(canvas);
  resize(); layout();

  let last = performance.now(), lastTick = 0;
  function loop(now) {
    if (disposed) return;
    requestAnimationFrame(loop);
    const dt = Math.min(0.25, (now - last) / 1000); last = now;
    const gap = O && O.frameGap ? O.frameGap() : 0;
    if ((O ? O.hidden() : document.hidden) || (gap && now - lastTick < gap - 3)) return;
    lastTick = now;
    let moving = false; const k = RM ? 1 : Math.min(1, dt * 4);
    for (const g of cols) { const u = g.userData; if (Math.abs(u.want - u.h) > 0.002) { u.h += (u.want - u.h) * k; moving = true; } }
    if (Math.abs(lineWant - lineH) > 0.002) { lineH += (lineWant - lineH) * k; moving = true; }
    if (moving || dirty) { layout(); rc.render(); dirty = false; }
  }
  requestAnimationFrame(loop);
  return {
    lite, count: () => cols.filter((g) => g.visible).length, quality: () => rc.quality(), passes: () => rc.passes(),
    /** values = the day ranges oldest first (up to 8), typical = an ordinary day: both in points */
    set(values, typical) {
      const v = (values || []).slice(-N), top = Math.max(1, ...v, typical || 0), scale = MAXH / top;
      cols.forEach((g, i) => { const slot = i - (N - v.length); g.visible = slot >= 0; if (slot >= 0) { g.userData.want = v[slot] * scale; g.userData.src = slot; if (RM) g.userData.h = g.userData.want; } g.userData.i = slot >= 0 ? slot : -1; });
      lineWant = Math.max(0.05, (typical || 0) * scale); if (RM) lineH = lineWant; dirty = true;
    },
    select(i) { sel = i; dirty = true; }, get selected() { return sel; },
    heights() { return cols.filter((g) => g.visible).map((g) => Math.round(g.userData.want * 1000) / 1000); },
    line() { return Math.round(lineWant * 1000) / 1000; },
    screenOf(i) { const g = cols.find((x) => x.visible && x.userData.i === i); if (!g) return null; const v = new THREE.Vector3(g.position.x, g.userData.want / 2, 0).project(camera); const r = canvas.getBoundingClientRect(); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height, front: v.z < 1 }; },
    dispose() { disposed = true; canvas.removeEventListener('pointerup', pick); if (ro) ro.disconnect(); try { rc.dispose(); } catch (_) { /* gone */ } },
  };
}
window.PHEME_RACK = { createRack };   // read by pheme.js (a second module tag, so a failed 3D load never stops the page)
