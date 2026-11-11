// SYMPOSIUM hall (ES module): a round marble hall at golden hour. Couches (klinai) in a ring around a low table with a krater; everyone sits there as a small
// cartoon figure (../olympus/people3d.js, one instanced crowd). Built on the OLYMPUS render core (three.js r160 from ../jarvis/). Warm light, bloom <= .2.
// Draw calls: floor, rug, table (2), krater, cups, columns (2), ring beam, couches (3), braziers (2), the crowd (11) = about 25, whatever the number of people.
//   createHall(canvas, { people: [spec], reduced, onPick(i) }) -> { ok, yaw(), setYaw(a), spin(dx), focus(i), active(i|-1), project(i) -> {x, y, front}, pick(clientX, clientY), turntable?, dispose() }
// If WebGL, the render core or the tier (LITE / off) says no, ok is false and the page keeps its portrait grid.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { figureInstanced, figure } from '../olympus/people3d.js';
import { seats, couchAt, turn, yawFor } from './symposiumcore.js';

export function createHall(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(46, 1, 0.1, 80);
    scene.background = new THREE.Color('#3b2a1c'); scene.fog = new THREE.Fog('#3b2a1c', 14, 40);
    rc = createRenderer({ canvas, scene, camera, maxDpr: 2, tint: '#c8a24a', env: 'night', theme: { sky: '#6a4526', fog: '#3b2a1c', emissive: '#c8a24a', bloom: '#e0b060', accent: '#c8a24a' }, bloom: { strength: 0.16, radius: 0.5, threshold: 1.0 } });
    const q = rc.quality();
    if (q === 'low' || q === 'off') { rc.dispose(); return { ok: false, reason: 'quality ' + q }; }
    return build(rc, scene, camera, canvas, o);
  } catch (e) {
    try { if (rc) rc.dispose(); } catch (_) { /* nothing */ }
    return { ok: false, reason: String(e && e.message ? e.message : e) };
  }
}

function build(rc, scene, camera, canvas, o) {
  const specs = o.people || [], N = specs.length, L = seats(N), r = L.r, reduced = !!o.reduced;
  const marble = new THREE.MeshStandardMaterial({ color: '#d9cfbb', roughness: 0.82 }), warm = new THREE.MeshStandardMaterial({ color: '#b9a888', roughness: 0.9 }), bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.5, metalness: 0.55 });
  const wood = new THREE.MeshStandardMaterial({ color: '#6b4a2a', roughness: 0.85 }), cloth = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.95 }), terra = new THREE.MeshStandardMaterial({ color: '#b5563c', roughness: 0.8 });
  const flame = new THREE.MeshBasicMaterial({ color: new THREE.Color('#ffb860').multiplyScalar(1.5) });
  scene.add(new THREE.HemisphereLight('#ffe6bf', '#4a3622', 1.25));
  const sun = new THREE.DirectionalLight('#ffd29a', 2.3); sun.position.set(6, 9, 5); scene.add(sun);
  const fill = new THREE.PointLight('#ffb060', 14, r * 3.2, 1.6); fill.position.set(0, 2.2, 0); scene.add(fill);
  const add = (m) => { scene.add(m); return m; };
  const floor = add(new THREE.Mesh(new THREE.CircleGeometry(r + 6.5, 56), marble)); floor.rotation.x = -Math.PI / 2;
  const rug = add(new THREE.Mesh(new THREE.RingGeometry(r - 1.25, r + 1.1, 56), new THREE.MeshStandardMaterial({ color: '#7d5a36', roughness: 1 }))); rug.rotation.x = -Math.PI / 2; rug.position.y = 0.006;
  const tr = Math.max(0.9, r * 0.36);
  const top = add(new THREE.Mesh(new THREE.CylinderGeometry(tr, tr, 0.07, 36), marble)); top.position.y = 0.42;
  const foot = add(new THREE.Mesh(new THREE.CylinderGeometry(tr * 0.3, tr * 0.42, 0.4, 20), warm)); foot.position.y = 0.2;
  const krater = add(new THREE.Mesh(new THREE.LatheGeometry([[0.1, 0], [0.16, 0.04], [0.09, 0.12], [0.2, 0.3], [0.3, 0.52], [0.34, 0.62], [0.3, 0.64]].map((p) => new THREE.Vector2(p[0], p[1])), 18), terra)); krater.position.y = 0.455;
  const nCup = Math.min(10, Math.max(4, Math.round(N / 4))), cups = add(new THREE.InstancedMesh(new THREE.CylinderGeometry(0.06, 0.035, 0.07, 10), bronze, nCup));
  const d = new THREE.Object3D(), put = (im, i, x, y, z, ry, sx, sy, sz) => { d.position.set(x, y, z); d.rotation.set(0, ry || 0, 0); d.scale.set(sx == null ? 1 : sx, sy == null ? 1 : sy, sz == null ? 1 : sz); d.updateMatrix(); im.setMatrixAt(i, d.matrix); };
  for (let i = 0; i < nCup; i++) { const a = (i / nCup) * Math.PI * 2 + 0.3; put(cups, i, Math.sin(a) * tr * 0.72, 0.49, Math.cos(a) * tr * 0.72); }
  // the colonnade
  const nCol = Math.max(10, Math.min(22, Math.round((r + 3.4) * 1.9))), R2 = r + 3.3;
  const shafts = add(new THREE.InstancedMesh(new THREE.CylinderGeometry(0.26, 0.31, 4.2, 12), marble, nCol)), caps = add(new THREE.InstancedMesh(new THREE.BoxGeometry(0.82, 0.22, 0.82), marble, nCol));
  for (let i = 0; i < nCol; i++) { const a = (i / nCol) * Math.PI * 2 + Math.PI / nCol; put(shafts, i, Math.sin(a) * R2, 2.1, Math.cos(a) * R2); put(caps, i, Math.sin(a) * R2, 4.31, Math.cos(a) * R2, a); }
  const beam = add(new THREE.Mesh(new THREE.TorusGeometry(R2, 0.3, 4, 48), warm)); beam.rotation.x = Math.PI / 2; beam.position.y = 4.72; beam.scale.z = 0.9;
  // couches: a wooden frame, a cushion in the pair's own colour, a headrest
  const nC = L.couches, frames = add(new THREE.InstancedMesh(new THREE.BoxGeometry(1.36, 0.2, 0.62), wood, nC)), cush = add(new THREE.InstancedMesh(new THREE.BoxGeometry(1.26, 0.09, 0.56), cloth, nC)), rests = add(new THREE.InstancedMesh(new THREE.BoxGeometry(1.36, 0.36, 0.1), wood, nC));
  const CUSH = ['#b5563c', '#7f8a52', '#4b7a99', '#c8a24a', '#a9764c'], col = new THREE.Color();
  for (let c = 0; c < nC; c++) {
    const k = couchAt(L, c), w = k.wide ? 1 : 0.56, ox = Math.sin(k.ry + Math.PI) * 0.0, oz = 0;
    put(frames, c, k.x + ox, 0.1, k.z + oz, k.ry, w, 1, 1); put(cush, c, k.x, 0.245, k.z, k.ry, w, 1, 1);
    put(rests, c, k.x - Math.sin(k.ry) * 0.3, 0.3, k.z - Math.cos(k.ry) * 0.3, k.ry, w, 1, 1);
    cush.setColorAt(c, col.set(CUSH[c % CUSH.length]));
  }
  if (cush.instanceColor) cush.instanceColor.needsUpdate = true;
  // braziers between the columns
  const nB = 4, bowls = add(new THREE.InstancedMesh(new THREE.CylinderGeometry(0.26, 0.1, 0.9, 10), bronze, nB)), fires = add(new THREE.InstancedMesh(new THREE.ConeGeometry(0.17, 0.4, 7), flame, nB));
  for (let i = 0; i < nB; i++) { const a = (i / nB) * Math.PI * 2 + Math.PI / 4; put(bowls, i, Math.sin(a) * (r + 1.9), 0.45, Math.cos(a) * (r + 1.9)); put(fires, i, Math.sin(a) * (r + 1.9), 1.08, Math.cos(a) * (r + 1.9)); }
  // the people
  const lite = N > 48, crowd = figureInstanced(THREE, specs, { seated: true, lite });
  const SC = 1.5;
  L.seats.forEach((s, i) => crowd.userData.place(i, s.x, 0.29 - 0.215 * SC, s.z, s.ry, SC));
  scene.add(crowd);

  const st = { yaw: 0, goal: null, vel: 0, auto: !reduced, active: -1, t: 0, idle: 0, w: 1, h: 1 };
  const ray = new THREE.Raycaster(), v = new THREE.Vector3(), ndc = new THREE.Vector2();
  function placeCam() {
    const portrait = st.w / st.h < 0.95, dist = r + (portrait ? 6.6 + r * 0.55 : 5.2 + r * 0.2), hgt = portrait ? 4.6 + r * 0.42 : 3.4 + r * 0.2;
    camera.position.set(Math.sin(st.yaw) * dist, hgt, Math.cos(st.yaw) * dist); camera.lookAt(-Math.sin(st.yaw) * r * 0.3, 0.55, -Math.cos(st.yaw) * r * 0.3);      // a little past the centre: the faces across the table read larger
  }
  function fit() { const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1; if (w === st.w && h === st.h) return; st.w = w; st.h = h; camera.aspect = w / h; camera.updateProjectionMatrix(); }
  function frame(dt) {
    st.t += dt; fit();
    if (st.goal != null) { const dlt = turn(st.yaw, st.goal); if (Math.abs(dlt) < 0.004 || reduced) { st.yaw = st.goal; st.goal = null; } else st.yaw += dlt * Math.min(1, dt * 4.5); }
    else if (Math.abs(st.vel) > 0.0004) { st.yaw += st.vel; st.vel *= Math.pow(0.04, dt); }
    else if (st.auto && st.active < 0) { st.idle += dt; if (st.idle > 2.5) st.yaw += dt * 0.045; }
    placeCam();
    if (!reduced) { crowd.userData.tick(st.t); for (let i = 0; i < nB; i++) { const a = (i / nB) * Math.PI * 2 + Math.PI / 4, k = 1 + Math.sin(st.t * 9 + i * 2) * 0.12; put(fires, i, Math.sin(a) * (r + 1.9), 1.08, Math.cos(a) * (r + 1.9), st.t * 2 + i, 1, k, 1); } fires.instanceMatrix.needsUpdate = true; }
    if (o.onFrame) o.onFrame();
  }
  fit(); placeCam();
  rc.start(frame);
  const api = {
    ok: true, layout: L, count: N,
    yaw: () => st.yaw,
    setYaw(a) { st.yaw = a; st.goal = null; st.vel = 0; placeCam(); },
    spin(dx) { st.goal = null; st.idle = 0; st.yaw -= dx * 0.008; st.vel = -dx * 0.008 * 0.5; },
    focus(i) { if (L.seats[i]) { st.goal = yawFor(L, i) + Math.PI; st.vel = 0; st.idle = 0; } },      // the camera goes to the far side, so this person faces it
    active(i) { if (st.active >= 0) crowd.userData.setActive(st.active, false); st.active = i == null ? -1 : i; if (st.active >= 0) crowd.userData.setActive(st.active, true); if (reduced) crowd.userData.tick(0); },
    project(i) { crowd.userData.headWorld(i, v); const behind = v.clone().sub(camera.position).dot(camera.getWorldDirection(new THREE.Vector3())) <= 0; v.project(camera); return { x: (v.x * 0.5 + 0.5) * st.w, y: (-v.y * 0.5 + 0.5) * st.h, z: v.z, front: !behind }; },
    pick(cx, cy) { const b = canvas.getBoundingClientRect(); ndc.set(((cx - b.left) / b.width) * 2 - 1, -((cy - b.top) / b.height) * 2 + 1); ray.setFromCamera(ndc, camera); return crowd.userData.pick(ray); },
    drawCalls: () => { let n = 0; scene.traverse((x) => { if (x.isMesh && x.visible) n++; }); return n; },      // one draw per mesh: every repeated thing is instanced
    dispose() { try { rc.dispose(); } catch (_) { /* gone */ } crowd.userData.dispose(); },
  };
  return api;
}

/** a small turntable for "Make my character": one figure on a marble disc, its own tiny renderer (no post passes). */
export function createTurntable(canvas, sp, opts) {
  const o = opts || {};
  try {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(30, 1, 0.1, 20);
    scene.add(new THREE.HemisphereLight('#ffe9c4', '#5a4630', 1.7)); const sun = new THREE.DirectionalLight('#ffd9a0', 2.4); sun.position.set(2, 4, 4); scene.add(sun);
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.56, 0.08, 28), new THREE.MeshStandardMaterial({ color: '#d9cfbb', roughness: 0.85 })); disc.position.y = -0.04; scene.add(disc);
    const holder = new THREE.Group(); scene.add(holder);
    let fig = null, raf = 0, t0 = performance.now(), last = t0, dead = false, angle = 0.5;
    function set(s) { if (fig) fig.userData.dispose(); fig = figure(THREE, s, {}); fig.userData.pose('wave'); holder.add(fig); if (o.reduced) draw(0); }
    function fit() { const w = canvas.clientWidth || 200, h = canvas.clientHeight || 220; renderer.setSize(w, h, false); cam.aspect = w / h; cam.position.set(0, 0.8, 3.5); cam.lookAt(0, 0.52, 0); cam.updateProjectionMatrix(); }
    function draw(dt) { holder.rotation.y = angle; if (fig && dt) fig.userData.tick(dt, (performance.now() - t0) / 1000); renderer.render(scene, cam); }
    function loop(now) { if (dead) return; const dt = Math.min(0.05, (now - last) / 1000); last = now; if (!document.hidden) { angle += dt * 0.7; draw(dt); } raf = requestAnimationFrame(loop); }
    fit(); set(sp);
    if (o.reduced) draw(0); else raf = requestAnimationFrame(loop);
    return { ok: true, set, fit, triangles: () => (fig ? fig.userData.triangles : 0), dispose() { dead = true; cancelAnimationFrame(raf); if (fig) fig.userData.dispose(); disc.geometry.dispose(); disc.material.dispose(); renderer.dispose(); } };
  } catch (e) { return { ok: false, reason: String(e && e.message ? e.message : e) }; }
}
