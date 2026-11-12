// MINT CITY 3D scene (optional ES module): a marble city, five districts (one per money stream) round a central golden pillar. Buildings are INSTANCED (one draw call per kind per district),
// each district has a LOD (detail near, one single block far), the camera orbits by drag / pinch / wheel and flies on tours. Warm sun, warm fog, marble and bronze: no neon, no bloom.
// Registers window.MINTCITY3D = { mount, setPlan, flyTo, tour, stop, state, dispose } and fires 'mintcity3d'. mintcity.js draws the 2D map and list first and only hides the map when mount() returns true.
import * as THREE from '../jarvis/three.module.min.js';
import * as C from './mintcitycore.js';
import { dress } from '../olympus/hero-stage.js';
// QA Round 6 bug 8: plaster / marble / paving scans, the golden HDRI and a painted golden-hour sky (olympus/hero-stage.js dress), a gilded pillar.

const COLORS = { marble: 0xd8cfbd, gold: 0xc8a24a, bronze: 0x9c6b3c, terra: 0xb9694b, olive: 0x7f8a52, aegean: 0x4b7a99 };
let R = null;

function webgl() { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (_) { return false; } }
function prism() { const g = new THREE.CylinderGeometry(0.5, 0.5, 1, 3); g.rotateX(-Math.PI / 2); g.translate(0, -0.125, 0); g.scale(1 / 0.866, 1 / 0.75, 1); return g; }
function label(text, accent) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 64; const g = c.getContext('2d');
  g.fillStyle = 'rgba(20,17,14,.78)'; g.beginPath(); if (g.roundRect) g.roundRect(4, 8, 248, 48, 14); else g.rect(4, 8, 248, 48); g.fill();
  g.strokeStyle = accent; g.lineWidth = 2; g.stroke(); g.fillStyle = '#f3ece0'; g.font = '700 28px "Iowan Old Style", Palatino, Georgia, serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, 128, 33);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false })); s.scale.set(10, 2.5, 1); return s;
}

function instanced(list, geoms, mat) {
  const g = new THREE.Group(), by = { box: [], cyl: [], roof: [] };
  for (const b of list) (by[b.k] || by.box).push(b);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), p = new THREE.Vector3(), s = new THREE.Vector3(), col = new THREE.Color();
  let n = 0;
  for (const k of ['box', 'cyl', 'roof']) {
    const arr = by[k]; if (!arr.length) continue;
    const mesh = new THREE.InstancedMesh(geoms[k], mat, arr.length);
    arr.forEach((b, i) => { e.set(0, b.ry || 0, 0); q.setFromEuler(e); p.set(b.x, b.y, b.z); s.set(b.sx, b.sy, b.sz); m4.compose(p, q, s); mesh.setMatrixAt(i, m4); col.setHex(COLORS[b.c] || COLORS.marble); mesh.setColorAt(i, col); });
    mesh.instanceMatrix.needsUpdate = true; if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true; mesh.frustumCulled = false;
    g.add(mesh); n += arr.length;
  }
  g.userData.count = n; g.userData.draws = g.children.length;
  return g;
}

function build(plan) {
  const root = new THREE.Group(), tier = R.tier;
  const mat = R.mat;
  R.districts = plan.districts.map((d, i) => {
    const detail = instanced(d.parts, R.geoms, mat);
    const proxy = new THREE.Mesh(R.geoms.box, new THREE.MeshStandardMaterial({ color: 0xcfc4b2, roughness: 0.6 }));
    proxy.scale.set(11, Math.max(2, d.H * 0.8), 11); proxy.position.set(d.cx, Math.max(2, d.H * 0.8) / 2, d.cz); proxy.visible = false;
    const hit = new THREE.Mesh(new THREE.CylinderGeometry(10, 10, 24, 12), new THREE.MeshBasicMaterial({ visible: false })); hit.position.set(d.cx, 12, d.cz); hit.userData.id = d.id;
    const lab = label(C.DISTRICTS[d.id].name, C.DISTRICTS[d.id].accent); lab.position.set(d.cx, d.H + 5.5, d.cz);
    root.add(detail, proxy, hit, lab);
    return { id: d.id, cx: d.cx, cz: d.cz, detail, proxy, hit, lab, on: true, i };
  });
  R.filler = instanced(plan.filler, R.geoms, mat); root.add(R.filler);
  const ph = plan.pillar.h, gold = new THREE.MeshStandardMaterial({ color: 0xc8a24a, roughness: 0.28, metalness: 0.95, envMapIntensity: 1.8 });
  const pil = new THREE.Group();
  const base = new THREE.Mesh(new THREE.CylinderGeometry(3.4, 3.8, 0.8, 32), R.D.kit.mat('marble', { color: '#e6dccb' })); base.position.y = 0.4;
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.5, ph, 28), gold); shaft.position.y = 0.8 + ph / 2;
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(2.0, 1.4, 0.9, 28), gold); cap.position.y = 0.8 + ph + 0.45;
  const sun = new THREE.Mesh(new THREE.SphereGeometry(0.9, 20, 14), new THREE.MeshBasicMaterial({ color: 0xe0b060 })); sun.position.y = 0.8 + ph + 1.9;
  const lamp = new THREE.PointLight(0xffc477, 1.6, 40); lamp.position.y = 0.8 + ph + 2.4;
  pil.add(base, shaft, cap, sun, lamp); pil.userData = { ph }; root.add(pil); R.pillar = pil;
  R.root = root; R.scene.add(root); R.plan = plan;
}
function clearRoot() {
  if (!R.root) return;
  R.scene.remove(R.root);
  R.root.traverse((o) => { if (o.isInstancedMesh) o.dispose(); if (o.material && o.material.map) o.material.map.dispose(); if (o.material && o.material !== R.mat) o.material.dispose(); if (o.geometry && !Object.values(R.geoms).includes(o.geometry)) o.geometry.dispose(); });
  R.root = null;
}

function applyPose(p) { R.pose = p; const c = C.poseToCam(p); R.camera.position.set(c.pos[0], c.pos[1], c.pos[2]); R.camera.lookAt(c.look[0], c.look[1], c.look[2]); }
function frame(now) {
  if (!R || R.dead) return;
  const dt = Math.min(0.1, (now - (R.last || now)) / 1000); R.last = now;
  if (R.fly) { const t = (now - R.fly.t0) / R.fly.ms; applyPose(C.lerpPose(R.fly.from, R.fly.to, t)); if (t >= 1) R.fly = null; }
  else if (R.tourName) { applyPose(C.tourPose(R.tourName, now - R.tourT0, 5)); }
  else if (!R.reduce && !R.touched) applyPose(Object.assign({}, R.pose, { yaw: R.pose.yaw + dt * 0.03 }));
  const cam = R.camera.position;
  for (const d of R.districts) {
    const dist = Math.hypot(cam.x - d.cx, cam.y, cam.z - d.cz), near = C.lodDetail(dist, R.tier);
    if (near !== d.on) { d.on = near; d.detail.visible = near; d.proxy.visible = !near; }
  }
  R.renderer.render(R.scene, R.camera); R.frames++;
  if (!R.reduce || R.fly || R.tourName) R.raf = requestAnimationFrame(frame); else R.raf = 0;
}
function kick() { if (R && !R.raf && !R.dead) R.raf = requestAnimationFrame(frame); }

function mount(box, plan, opts) {
  if (R) dispose();
  if (!box || !webgl()) return false;
  opts = opts || {};
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' }); } catch (_) { return false; }
  const reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const tier = opts.tier || ((navigator.hardwareConcurrency || 4) <= 4 ? 'mid' : 'high');
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, tier === 'high' ? 2 : 1.5)); renderer.outputColorSpace = THREE.SRGBColorSpace;
  box.appendChild(renderer.domElement); renderer.domElement.style.touchAction = 'none';
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x3b2c1e); scene.fog = new THREE.Fog(0x3b2c1e, 90, 230);
  const camera = new THREE.PerspectiveCamera(46, 1.2, 0.5, 400);
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  const D = dress({ renderer, scene, camera, tier: tier === 'low' ? 'low' : 'high', palette: 'golden', hdri: 'golden', envI: 0.8, sunDir: [0.5, 0.7, 0.4], key: 2.4, hemi: 0.6, shadows: false, sky: { sunX: 0.78, sunY: 0.75, templeX: 0.15, horizon: 0.45 }, fogNear: 120, fogFar: 300 });
  const ground = new THREE.Mesh(new THREE.CircleGeometry(150, 64), D.kit.mat('paving', { color: '#b8aa92' })); ground.rotation.x = -Math.PI / 2; scene.add(ground);
  const plaza = new THREE.Mesh(new THREE.CylinderGeometry(9, 9.4, 0.3, 48), D.kit.mat('marble', { color: '#e6dccb' })); plaza.position.y = 0.15; scene.add(plaza);
  for (let i = 0; i < 5; i++) { const c = C.districtCenter(i, 5), len = C.RING - 12, road = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.12, len), new THREE.MeshStandardMaterial({ color: 0xb8ad98, roughness: 0.8 })); road.position.set(c.x * 0.5, 0.06, c.z * 0.5); road.rotation.y = Math.atan2(c.x, c.z); scene.add(road); }
  const geoms = { box: new THREE.BoxGeometry(1, 1, 1), cyl: new THREE.CylinderGeometry(0.5, 0.5, 1, tier === 'low' ? 8 : 14), roof: prism() };
  R = { renderer, scene, camera, box, geoms, mat: D.kit.mat('plaster', { color: '#ffffff' }), D, tier, reduce, frames: 0, raf: 0, dead: false, districts: [], root: null, pose: Object.assign({}, C.OVERVIEW), onPick: opts.onPick || null, touched: false, fly: null, tourName: null, ptr: new Map(), last: 0 };
  build(plan);
  const size = () => { const w = Math.max(200, box.clientWidth || 320), h = Math.max(160, box.clientHeight || 300); renderer.setSize(w, h, false); D.backdrop(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); if (!R.raf) { applyPose(R.pose); renderer.render(scene, camera); } };
  applyPose(R.pose); size();
  if (typeof ResizeObserver === 'function') { R.ro = new ResizeObserver(size); R.ro.observe(box); }
  // drag = turn, two fingers / wheel = zoom, a short tap on a district = pick it
  const el = renderer.domElement, ray = new THREE.Raycaster(), v2 = new THREE.Vector2();
  const clampPose = () => { const p = R.pose; p.pitch = Math.max(0.12, Math.min(1.3, p.pitch)); p.dist = Math.max(14, Math.min(110, p.dist)); };
  const down = (e) => { R.ptr.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t0: performance.now() }); el.setPointerCapture && el.setPointerCapture(e.pointerId); };
  const move = (e) => {
    const p = R.ptr.get(e.pointerId); if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y; p.x = e.clientX; p.y = e.clientY;
    if (R.ptr.size === 2) { const [a, b] = [...R.ptr.values()]; const d = Math.hypot(a.x - b.x, a.y - b.y); if (R.pinch) R.pose.dist *= R.pinch / d; R.pinch = d; }
    else { if (Math.hypot(p.x - p.x0, p.y - p.y0) > 6) { R.touched = true; R.tourName = null; R.fly = null; } R.pose.yaw -= dx * 0.006; R.pose.pitch += dy * 0.004; }
    clampPose(); applyPose(R.pose); kick(); if (!R.raf) R.renderer.render(R.scene, R.camera);
  };
  const up = (e) => {
    const p = R.ptr.get(e.pointerId); R.ptr.delete(e.pointerId); R.pinch = 0; if (!p) return;
    if (Math.hypot(e.clientX - p.x0, e.clientY - p.y0) < 8 && performance.now() - p.t0 < 500) {
      const r = el.getBoundingClientRect(); v2.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(v2, camera);
      const hit = ray.intersectObjects(R.districts.map((d) => d.hit), false)[0];
      if (hit && R.onPick) R.onPick(hit.object.userData.id);
    }
  };
  const wheel = (e) => { e.preventDefault(); R.pose.dist *= e.deltaY > 0 ? 1.08 : 0.92; clampPose(); R.touched = true; applyPose(R.pose); kick(); if (!R.raf) R.renderer.render(R.scene, R.camera); };
  el.addEventListener('pointerdown', down); el.addEventListener('pointermove', move); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up); el.addEventListener('wheel', wheel, { passive: false });
  R.listeners = [['pointerdown', down], ['pointermove', move], ['pointerup', up], ['pointercancel', up], ['wheel', wheel]];
  const vis = () => { if (!R) return; if (document.hidden) { cancelAnimationFrame(R.raf); R.raf = 0; } else kick(); };
  document.addEventListener('visibilitychange', vis); R.vis = vis;
  kick();
  return true;
}

function setPlan(plan) { if (!R) return; clearRoot(); build(plan); kick(); }
function flyTo(pose, ms) { if (!R) return; R.tourName = null; R.touched = true; if (R.reduce || !ms) { applyPose(pose); R.fly = null; R.renderer.render(R.scene, R.camera); return; } R.fly = { from: Object.assign({}, R.pose), to: pose, t0: performance.now(), ms: ms || 1000 }; kick(); }
function tour(name) { if (!R) return; R.fly = null; R.touched = true; if (R.reduce) { applyPose(C.tourPose(name, 0, 5)); R.renderer.render(R.scene, R.camera); return; } R.tourName = name; R.tourT0 = performance.now(); kick(); }
function stop() { if (!R) return; R.tourName = null; R.fly = null; }
function state() {
  if (!R) return { on: false };
  const inst = R.districts.reduce((n, d) => n + d.detail.userData.count, 0) + R.filler.userData.count, draws = R.districts.reduce((n, d) => n + d.detail.userData.draws, 0) + R.filler.userData.draws + R.districts.length * 2 + 8;
  return { on: true, frames: R.frames, tier: R.tier, instances: inst, drawsApprox: draws, lod: R.districts.map((d) => (d.on ? 1 : 0)), pillar: R.plan.pillar.h, tour: R.tourName, pose: R.pose, heights: R.plan.districts.map((d) => d.H) };
}
function dispose() {
  if (!R) return;
  R.dead = true; cancelAnimationFrame(R.raf);
  try {
    document.removeEventListener('visibilitychange', R.vis); if (R.ro) R.ro.disconnect();
    if (R.D) R.D.dispose();
    const el = R.renderer.domElement; for (const [k, f] of R.listeners || []) el.removeEventListener(k, f);
    clearRoot(); R.scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material && o.material.dispose) o.material.dispose(); });
    R.renderer.dispose(); if (el.parentNode) el.parentNode.removeChild(el);
  } catch (_) { /* nothing */ }
  R = null;
}

window.MINTCITY3D = { mount, setPlan, flyTo, tour, stop, state, dispose };
window.__heroStats = () => (R && R.D ? Object.assign(R.D.stats(), { calls: R.renderer.info.render.calls }) : null);
window.dispatchEvent(new Event('mintcity3d'));
