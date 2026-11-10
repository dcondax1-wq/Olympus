// AGORA GALLERY stage (ES module): the 3D half of the page. It puts one shape of olympus/shapes3d.js on a marble pedestal and draws it with the kit's
// render core (olympus/render.js), warm light, bloom held under .25. It publishes window.GALLERY3D for gallery.js (the page) and tells the page about taps
// with a 'gallery:tap' event on window. If WebGL or the core cannot start, GALLERY3D.ok is false and the page keeps its 2D drawing (never blank).
// Drag turns the pedestal (with a little inertia), a tap asks the page to look closer, the camera glides in and out. Nothing is sent or stored.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import * as KIT from '../olympus/materials.js';
import * as SH from '../olympus/shapes3d.js';
import * as C from './gallerycore.js';

const O = window.OLYMPUS || null;
const q = new URLSearchParams(location.search);
const canvas = document.getElementById('stage');
const reduced = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (_) { return false; } };

function webglOK() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (_) { return false; }
}

function start() {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(34, 1, 0.1, 80);
    const forced = ['high', 'low'].indexOf(q.get('q')) >= 0 ? q.get('q') : undefined;
  const rc = createRenderer({ canvas, scene, camera, quality: forced, env: 'night', tint: '#c8a24a', alpha: true, exposure: 1, maxDpr: 2,
    bloom: { strength: 0.2, radius: 0.5, threshold: 0.95 }, onQuality: () => { if (api.mode === 'auto') swap(); } });
  let mode = q.get('mode') === 'high' || q.get('mode') === 'lite' ? q.get('mode') : 'auto';
  const mats = {};
  const matsFor = (lite) => mats[lite ? 'lite' : 'hd'] || (mats[lite ? 'lite' : 'hd'] = SH.materials({ lite, kit: lite ? null : KIT }));

  const turn = new THREE.Group(); scene.add(turn);
  SH.warmLights(scene, { lite: false });
  let ped = null, cur = null, curId = '', shapeLite = null, born = 0, yaw = 0.5, vel = 0, focus = false, dist = 6, lookY = 1, frames = 0, last = null;
  const cache = {};

  function isLite() { return C.modeFor(mode, rc.quality()).lite; }
  function clearShape() { if (cur) { SH.dispose(cur); cur = null; } }
  function place() {
    clearShape();
    if (!curId) return;
    const lite = isLite();
    if (ped) { ped.traverse((o) => { if (o.geometry) o.geometry.dispose(); }); turn.remove(ped); }
    ped = SH.pedestal({ lite, radius: 1.55, M: matsFor(lite) }); turn.add(ped);
    cur = SH.build(curId, { lite, materials: matsFor(lite), size: curId === 'pillarbar' || curId === 'temple' || curId === 'trireme' || curId === 'scroll' ? 2.9 : 2.3 });
    turn.add(cur);
    shapeLite = lite; born = performance.now();
    const st = SH.stats(cur);
    last = { id: curId, lite, tris: st.tris, draws: st.draws };
    if (O && O.mode) { try { O.mode(lite); } catch (_) { /* a mark only */ } }
    window.dispatchEvent(new CustomEvent('gallery:changed'));
  }
  function swap() { if (curId && shapeLite !== isLite()) place(); }
  function statsBoth(id) {
    if (cache[id]) return cache[id];
    const out = {};
    for (const lite of [false, true]) { const g = SH.build(id, { lite }); const s = SH.stats(g); out[lite ? 'lite' : 'hd'] = { tris: s.tris, draws: s.draws }; SH.dispose(g); }
    return (cache[id] = out);
  }

  // drag to turn, tap to look closer
  let drag = null;
  canvas.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, y: e.clientY, t: performance.now(), moved: 0, lx: e.clientX, lt: performance.now() }; vel = 0; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* fine */ } });
  canvas.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const now = performance.now(), dx = e.clientX - drag.lx, dt = Math.max(1, now - drag.lt) / 1000;
    drag.moved += Math.abs(dx) + Math.abs(e.clientY - drag.y) * 0; drag.moved = Math.max(drag.moved, Math.hypot(e.clientX - drag.x, e.clientY - drag.y));
    yaw += dx * 0.011; vel = (dx * 0.011) / dt; drag.lx = e.clientX; drag.lt = now;
  });
  const up = (e) => {
    if (!drag) return;
    const d = drag; drag = null;
    if (e.type === 'pointerup' && C.isTap(d.moved, performance.now() - d.t)) window.dispatchEvent(new CustomEvent('gallery:tap'));
    else if (performance.now() - d.lt > 120) vel = 0;
    vel = Math.max(-6, Math.min(6, vel));
  };
  canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
  canvas.addEventListener('keydown', (e) => { if (e.key === 'ArrowLeft') { yaw -= 0.3; e.preventDefault(); } else if (e.key === 'ArrowRight') { yaw += 0.3; e.preventDefault(); } });

  let firstFrame = false;
  rc.start((dt) => {
    const d = Math.min(0.1, dt || 0.016);
    if (!drag) {
      if (Math.abs(vel) > 0) { yaw += vel * d; vel = C.inertia(vel, d); }
      else if (!focus && !reduced()) yaw += 0.22 * d;
    }
    turn.rotation.y = yaw;
    if (cur && cur.userData.update && !reduced()) cur.userData.update(performance.now() / 1000);
    const age = Math.min(1, (performance.now() - born) / (reduced() ? 1 : 380)), ease = 1 - Math.pow(1 - age, 3);
    if (cur) cur.scale.setScalar(cur.userData.baseScale || (cur.userData.baseScale = cur.scale.x)), cur.scale.multiplyScalar(0.9 + 0.1 * ease);
    const w = canvas.clientWidth || 360, h = canvas.clientHeight || 360;
    const want = C.fitDistance(camera.fov, w / h, 1.7, 1.5, focus), wantY = focus ? 1.2 : 1.05;
    dist += (want - dist) * Math.min(1, d * (reduced() ? 40 : 5)); lookY += (wantY - lookY) * Math.min(1, d * (reduced() ? 40 : 5));
    camera.position.set(0, lookY + (focus ? 0.5 : 1.15), dist); camera.lookAt(0, lookY, 0);
    frames++;
    if (!firstFrame && cur) { firstFrame = true; document.getElementById('stageBox').classList.add('live'); window.dispatchEvent(new CustomEvent('gallery:live')); }
  });

  const api = {
    ok: true, THREE, SH, rc,
    get mode() { return mode; },
    show(id) { if (!SH.IDS.includes(id)) return false; curId = id; place(); return true; },
    setFocus(f) { focus = !!f; },
    setMode(m) { mode = C.MODES.indexOf(m) >= 0 ? m : 'auto'; const mm = C.modeFor(mode, rc.quality()); if (mm.level) rc.setQuality(mm.level); else rc.setQuality(O && O.fx ? O.fx() : 'high'); place(); return { mode, lite: isLite(), level: rc.quality() }; },
    info() { return { id: curId, lite: shapeLite, level: rc.quality(), mode, frames, yaw, focus, last, both: curId ? statsBoth(curId) : null, dist, passes: rc.stats().passes }; },
    stats: statsBoth,
    spin(a) { yaw += a; },
  };
  if (mode !== 'auto') { const mm = C.modeFor(mode, rc.quality()); if (mm.level) rc.setQuality(mm.level); }
  return api;
}

try {
  if (q.get('flat') === '1') window.GALLERY3D = { ok: false, reason: 'flat' };
  else if (!webglOK()) window.GALLERY3D = { ok: false, reason: 'no WebGL' };
  else window.GALLERY3D = start();
} catch (e) {
  window.GALLERY3D = { ok: false, reason: String(e && e.message ? e.message : e) };
}
window.dispatchEvent(new CustomEvent('gallery:stage'));
