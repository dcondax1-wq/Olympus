// SYMPOSIUM hall (ES module): a round marble hall at golden hour. Couches (klinai) in a ring around a low table with a krater; everyone sits there as a v2 person
// (../olympus/people3d.js). You stand at the table and look across it, so the people you see face you (nobody shows you their back). The few people in view are full
// close-up figures (blinking, glancing, a real face); everyone else is one GPU crowd. When someone talks they turn to you, gesture and move their mouth; the
// others look at them. Built on the OLYMPUS render core (three.js r160 from ../jarvis/). Warm light, bloom <= .2.
// Draw calls: floor, rug, table (2), krater, cups, columns (2), ring beam, couches (3), braziers (2) = 14, the crowd 2, each close-up 2 (at most 5) = at most 26.
//   createHall(canvas, { people: [spec], reduced, onPick(i) }) -> { ok, yaw(), setYaw(a), spin(dx), focus(i), active(i|-1), talking(i, on), mouth(i, viseme, amount),
//                                                                  project(i) -> {x, y, front}, pick(clientX, clientY), drawCalls(), triangles(), dispose() }
// The chat sheet's 'olympus:people:open' / 'close' make that person turn, wave and talk. Voice (optional): window events 'olympus:people:speak' {id, on} and 'olympus:people:viseme' {id, viseme, amount} move that person's mouth.
// For the people kit's say() (speech bubbles, work cards, walk with me): stageFor(i) -> { project() } (that person becomes the active close-up), release(), walk(i) -> Promise,
// speaking() -> seat | -1, focus(i, off) (off: the speaker a little to one side, room for a work card), and 'olympus:people:expression' {id, expr} sets their face.
// If WebGL, the render core or the tier (LITE / off) says no, ok is false and the page keeps its portrait grid.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { figureInstanced, figure, play, lookAt, setTalking, setMouth, setExpression, animate, POSE_NAMES } from '../olympus/people3d.js?v=p2';
import { seats, couchAt, turn, yawFor, front } from './symposiumcore.js';

export function createHall(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(48, 1, 0.1, 80);
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

const CLOSE = 4;            // close-up figures for the people nearest the middle of the view (+ the one who talks)
const SEAT_Y = 0.29, BUTT = 0.226, SC = 1.5;

function build(rc, scene, camera, canvas, o) {
  const specs = o.people || [], N = specs.length, L = seats(N), r = L.r, reduced = !!o.reduced;
  const marble = new THREE.MeshStandardMaterial({ color: '#d9cfbb', roughness: 0.82 }), warm = new THREE.MeshStandardMaterial({ color: '#b9a888', roughness: 0.9 }), bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.5, metalness: 0.55 });
  const wood = new THREE.MeshStandardMaterial({ color: '#6b4a2a', roughness: 0.85 }), cloth = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.95 }), terra = new THREE.MeshStandardMaterial({ color: '#b5563c', roughness: 0.8 });
  const flame = new THREE.MeshBasicMaterial({ color: new THREE.Color('#ffb860').multiplyScalar(1.5) });
  // characters v3 (2026-11-11): calmer, more neutral light so skin reads as skin (no orange cast): an ivory sky, a warm-white sun, a small fire glow,
  // a soft key light from where you stand (faces always read) and a cool rim from behind the people
  scene.add(new THREE.HemisphereLight('#fbf3e6', '#5a4a3a', 0.95));
  const sun = new THREE.DirectionalLight('#ffeedd', 1.45); sun.position.set(6, 9, 5); scene.add(sun);
  const fill = new THREE.PointLight('#ffc888', 5, r * 3.2, 1.6); fill.position.set(0, 2.2, 0); scene.add(fill);
  const face = new THREE.DirectionalLight('#fff6ec', 1.05); scene.add(face); scene.add(face.target);
  const rimL = new THREE.DirectionalLight('#e4ecff', 0.55); scene.add(rimL); scene.add(rimL.target);
  const add = (m) => { scene.add(m); return m; };
  const floor = add(new THREE.Mesh(new THREE.CircleGeometry(r + 6.5, 56), marble)); floor.rotation.x = -Math.PI / 2;
  const rug = add(new THREE.Mesh(new THREE.RingGeometry(r - 1.25, r + 1.1, 56), new THREE.MeshStandardMaterial({ color: '#7d5a36', roughness: 1 }))); rug.rotation.x = -Math.PI / 2; rug.position.y = 0.006;
  const tr = Math.max(0.9, r * 0.32);
  const top = add(new THREE.Mesh(new THREE.CylinderGeometry(tr, tr, 0.07, 36), marble)); top.position.y = 0.42;
  const foot = add(new THREE.Mesh(new THREE.CylinderGeometry(tr * 0.3, tr * 0.42, 0.4, 20), warm)); foot.position.y = 0.2;
  const krater = add(new THREE.Mesh(new THREE.LatheGeometry([[0.1, 0], [0.16, 0.04], [0.09, 0.12], [0.2, 0.3], [0.3, 0.52], [0.34, 0.62], [0.3, 0.64]].map((p) => new THREE.Vector2(p[0], p[1])), 18), terra)); krater.position.y = 0.455; krater.scale.setScalar(0.55);      // small: you stand right behind it
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
    const k = couchAt(L, c), w = k.wide ? 1 : 0.56;
    put(frames, c, k.x, 0.1, k.z, k.ry, w, 1, 1); put(cush, c, k.x, 0.245, k.z, k.ry, w, 1, 1);
    put(rests, c, k.x - Math.sin(k.ry) * 0.3, 0.3, k.z - Math.cos(k.ry) * 0.3, k.ry, w, 1, 1);
    cush.setColorAt(c, col.set(CUSH[c % CUSH.length]));
  }
  if (cush.instanceColor) cush.instanceColor.needsUpdate = true;
  // braziers between the columns
  const nB = 4, bowls = add(new THREE.InstancedMesh(new THREE.CylinderGeometry(0.26, 0.1, 0.9, 10), bronze, nB)), fires = add(new THREE.InstancedMesh(new THREE.ConeGeometry(0.17, 0.4, 7), flame, nB));
  for (let i = 0; i < nB; i++) { const a = (i / nB) * Math.PI * 2 + Math.PI / 4; put(bowls, i, Math.sin(a) * (r + 1.9), 0.45, Math.cos(a) * (r + 1.9)); put(fires, i, Math.sin(a) * (r + 1.9), 1.08, Math.cos(a) * (r + 1.9)); }
  // the people: one crowd for everyone, close-up figures for the few in view
  const crowd = figureInstanced(THREE, specs, { seated: true, lite: N > 24, impostorTint: '#f4e7d6' });
  const seatY = (i) => SEAT_Y - BUTT * SC * ((specs[i] && specs[i].height) || 1);
  L.seats.forEach((s, i) => crowd.userData.place(i, s.x, seatY(i), s.z, s.ry, SC));
  scene.add(crowd);
  const close = new Map();      // seat -> figure
  function closeUp(i) {
    let f = close.get(i); if (f) return f;
    const s = L.seats[i]; f = figure(THREE, specs[i], { seated: true });
    f.position.set(s.x, seatY(i), s.z); f.rotation.y = s.ry; f.scale.multiplyScalar(SC); f.userData.seat = i;
    scene.add(f); close.set(i, f); crowd.userData.setVisible(i, false);
    if (reduced) f.userData.tick(0, 1);
    return f;
  }
  function dropClose(i) { const f = close.get(i); if (!f) return; f.userData.dispose(); close.delete(i); crowd.userData.setVisible(i, true); }

  const st = { yaw: 0, goal: null, vel: 0, auto: !reduced, active: -1, activeT: 0, voice: false, t: 0, idle: 0, w: 1, h: 1, walk: null };
  const ray = new THREE.Raycaster(), v = new THREE.Vector3(), ndc = new THREE.Vector2(), look = new THREE.Vector3(), camPos = new THREE.Vector3();
  const camLook = new THREE.Vector3(), camAt = new THREE.Vector3(), headV = new THREE.Vector3();
  function placeCam() {
    // you stand just past the middle of the table and look across it: the people over there face you, big enough to see their faces.
    // When someone talks the camera dollies in on them (a cinematic close-up), and back out when they are done.
    const portrait = st.w / st.h < 0.95, off = r * (portrait ? 0.02 : 0.2), hgt = portrait ? 1.3 : 1.36;
    camera.fov = portrait ? 46 : 40;
    camAt.set(Math.sin(st.yaw) * off, hgt, Math.cos(st.yaw) * off); camLook.set(-Math.sin(st.yaw) * r, 0.92, -Math.cos(st.yaw) * r);
    const z = st.zoom || 0;
    if (z > 0.001 && st.active >= 0 && L.seats[st.active]) {
      const s = L.seats[st.active], f = close.get(st.active);
      headV.set(s.x, seatY(st.active) + 1.08 * SC * ((specs[st.active] && specs[st.active].height) || 1) * 0.66, s.z);
      if (f) { f.updateWorldMatrix(true, true); const hb = f.userData.parts && f.userData.parts.head; if (hb && hb.getWorldPosition) hb.getWorldPosition(headV); }
      const dx = -s.x, dz = -s.z, dl = Math.hypot(dx, dz) || 1, side = st.cardOff || 0;
      const nearX = s.x + (dx / dl) * 1.55 + (-dz / dl) * side * 0.9, nearZ = s.z + (dz / dl) * 1.55 + (dx / dl) * side * 0.9;
      const e = z * z * (3 - 2 * z) * 0.85;
      camAt.lerp(v.set(nearX, headV.y + 0.08, nearZ), e); camLook.lerp(headV.clone().add(v.set((-dz / dl) * side * 0.35, -0.06, (dx / dl) * side * 0.35)), e);
      camera.fov += (34 - camera.fov) * e;
    }
    camera.updateProjectionMatrix();
    camera.position.copy(camAt); camera.lookAt(camLook);
    face.position.copy(camera.position).add(v.set(0.6, 1.2, 0)); face.target.position.copy(camLook);
    rimL.position.copy(camLook).add(v.set(-camLook.x * 0.6, 2.5, -camLook.z * 0.6)); rimL.target.position.copy(camLook);
  }
  function fit() { const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1; if (w === st.w && h === st.h) return; st.w = w; st.h = h; camera.aspect = w / h; camera.updateProjectionMatrix(); }
  function want() { const k = new Set(front(L, st.yaw + Math.PI, Math.min(CLOSE, N))); if (st.active >= 0) k.add(st.active); return k; }
  function syncClose() { const k = want(); for (const i of [...close.keys()]) if (!k.has(i)) dropClose(i); for (const i of k) closeUp(i); }
  function frame(dt) {
    st.t += dt; fit();
    if (st.goal != null) { const dlt = turn(st.yaw, st.goal); if (Math.abs(dlt) < 0.004 || reduced) { st.yaw = st.goal; st.goal = null; } else st.yaw += dlt * Math.min(1, dt * 4.5); }
    else if (Math.abs(st.vel) > 0.0004) { st.yaw += st.vel; st.vel *= Math.pow(0.04, dt); }
    else if (st.auto && st.active < 0) { st.idle += dt; if (st.idle > 2.5) st.yaw += dt * 0.045; }
    const zGoal = st.active >= 0 && !reduced && st.activeT > 0.6 ? 1 : 0; st.zoom = (st.zoom || 0) + (zGoal - (st.zoom || 0)) * Math.min(1, dt * 1.6); if (reduced) st.zoom = 0;
    placeCam(); syncClose(); camPos.copy(camera.position);
    // who looks where: everyone looks at the one who talks; with nobody talking the close-ups notice you, the crowd looks around
    const talker = st.active >= 0 ? crowd.userData.headWorld(st.active, look) : null;
    crowd.userData.lookAll(talker);
    for (const [i, f] of close) {
      if (i === st.active) {
        lookAt(f, camPos);
        const s = L.seats[i], want2 = Math.atan2(camPos.x - s.x, camPos.z - s.z), dy = turn(f.rotation.y, want2);
        f.rotation.y += Math.max(-0.5, Math.min(0.5, dy)) * Math.min(1, dt * 3);       // turn on the couch towards you
        st.activeT += dt;
        if (!st.voice) { const talking = st.activeT > 1.2 && (st.activeT % 7) < 3.6; setTalking(f, talking); }
      } else { lookAt(f, talker || camPos); const s = L.seats[i]; f.rotation.y += turn(f.rotation.y, s.ry) * Math.min(1, dt * 2); }
      if (st.walk && st.walk.i === i) {                                   // walk with me: they get up and walk out between the columns
        const w = st.walk, k = Math.min(1, (st.t - w.t0) / w.dur), e = k * k * (3 - 2 * k);
        f.position.set(w.x0 + (w.x1 - w.x0) * e, w.y0 * (1 - Math.min(1, k * 4)), w.z0 + (w.z1 - w.z0) * e); f.rotation.y = w.ry;
        if (k >= 1 && w.done) { const d = w.done; w.done = null; d(true); }
      }
      if (!reduced) animate(f, dt);
    }
    if (!reduced) { crowd.userData.tick(st.t); for (let i = 0; i < nB; i++) { const a = (i / nB) * Math.PI * 2 + Math.PI / 4, k = 1 + Math.sin(st.t * 9 + i * 2) * 0.12; put(fires, i, Math.sin(a) * (r + 1.9), 1.08, Math.cos(a) * (r + 1.9), st.t * 2 + i, 1, k, 1); } fires.instanceMatrix.needsUpdate = true; }
    if (o.onFrame) o.onFrame();
  }
  // voice: the chat sheet (or Jarvis) may say who is speaking and which mouth shape
  const bySeed = new Map(); specs.forEach((s, i) => bySeed.set(s && s.seed >>> 0, i));
  const idx = (id) => { try { const P = window.OLYMPUS_PEOPLE; const s = P && P.spec ? P.spec(id) : null; return s ? (bySeed.has(s.seed >>> 0) ? bySeed.get(s.seed >>> 0) : -1) : -1; } catch (_) { return -1; } };
  const onSpeak = (e) => { const dd = e && e.detail || {}, i = idx(dd.id); if (i >= 0) api.talking(i, dd.on !== false); };
  const onViseme = (e) => { const dd = e && e.detail || {}, i = idx(dd.id); if (i >= 0) api.mouth(i, dd.viseme, dd.amount); };
  const onExpr = (e) => { const dd = e && e.detail || {}, i = idx(dd.id), f = close.get(i); if (f && dd.expr) setExpression(f, dd.expr, 1); };
  window.addEventListener('olympus:people:expression', onExpr);
  const onOpen = (e) => { const i = idx(e && e.detail && e.detail.id); if (i >= 0) { api.focus(i); api.active(i); } }, onClose = () => api.active(-1);      // the 1:1 chat sheet
  window.addEventListener('olympus:people:speak', onSpeak); window.addEventListener('olympus:people:viseme', onViseme);
  window.addEventListener('olympus:people:open', onOpen); window.addEventListener('olympus:people:close', onClose);
  fit(); placeCam(); syncClose();
  rc.start(frame);
  // FX HOOK (olympus/fx-cine.js, optional; 2026-11-11 effects pass): the clock's light, a sky over the open ring, sun shafts, dust, brazier
  // embers + smoke + a breathing fire light, soft shadows on high (contact blobs on LITE), the speaker focus. The hall is the same without it.
  let cine = null, gone = false; const fHead = new THREE.Vector3();
  if (o.cinema !== false) import('../olympus/fx-cine.js').then((C) => { if (gone) return; cine = C.cinema(rc, { time: 'clock', sky: true, fog: 0.4, neutral: 0.45, fireLight: 2.2,
    rays: { to: [0, 0, 0], spread: [r * 1.5, 0, r * 1.5], length: 15, width: 1.8 }, dust: { box: [r * 2 + 6, 4, r * 2 + 6], center: [0, 2, 0] },
    fires: [0, 1, 2, 3].map((i) => { const a = (i / nB) * Math.PI * 2 + Math.PI / 4; return [Math.sin(a) * (r + 1.9), 1.15, Math.cos(a) * (r + 1.9)]; }), fireRange: r * 1.6,
    shadows: { casters: [shafts, frames], receivers: [floor, rug], box: r + 5 },      // the crowd: soft contact blobs (budget)
    blobs: L.seats.map((x) => [x.x, x.z, 0.42]), blobsAlways: true, blobY: 0.006 }); }).catch(() => {});
  const api = {
    ok: true, layout: L, count: N,
    yaw: () => st.yaw,
    setYaw(a) { st.yaw = a; st.goal = null; st.vel = 0; placeCam(); },
    spin(dx) { st.goal = null; st.idle = 0; st.yaw -= dx * 0.008; st.vel = -dx * 0.008 * 0.5; },
    focus(i, off) { if (L.seats[i]) { st.goal = yawFor(L, i) + Math.PI + (off || 0); st.vel = 0; st.idle = 0; st.cardOff = off ? Math.sign(off) : 0; } },      // turn so this person sits across the table, facing you
    active(i) {
      const prev = st.active; st.active = i == null || !L.seats[i] ? -1 : i; st.activeT = 0; st.voice = false;
      if (prev >= 0 && close.has(prev)) { const f = close.get(prev); setTalking(f, false); play(f, 'idle'); }
      crowd.userData.setActive(prev, false);
      if (st.active >= 0) { const f = closeUp(st.active); play(f, 'wave', { then: 'talk' }); }
      if (reduced) { syncClose(); crowd.userData.tick(0); }
      const k = st.active; if (cine) cine.focus(k >= 0 ? () => crowd.userData.headWorld(k, fHead) : null, { r: 0.2, amount: 4 });      // FX HOOK: focus on the speaker
    },
    talking(i, on) { if (i !== st.active) api.active(i); st.voice = true; const f = close.get(i); if (f) { setTalking(f, !!on); if (on) play(f, 'talk'); } },
    mouth(i, vis, amount) { const f = close.get(i); if (f) { st.voice = true; setMouth(f, vis, amount); } },
    project(i) { crowd.userData.headWorld(i, v); const behind = v.clone().sub(camera.position).dot(camera.getWorldDirection(new THREE.Vector3())) <= 0; v.project(camera); return { x: (v.x * 0.5 + 0.5) * st.w, y: (-v.y * 0.5 + 0.5) * st.h, z: v.z, front: !behind }; },
    pick(cx, cy) { const b = canvas.getBoundingClientRect(); ndc.set(((cx - b.left) / b.width) * 2 - 1, -((cy - b.top) / b.height) * 2 + 1); ray.setFromCamera(ndc, camera); return crowd.userData.pick(ray, true); },
    drawCalls: () => { let n = 0; scene.traverse((x) => { if (x.isMesh && x.visible) n++; }); return n; },      // one draw per mesh: every repeated thing is instanced
    triangles: () => { let n = 0; scene.traverse((x) => { if (x.isMesh && x.visible && x.geometry) { const g = x.geometry, c = g.index ? g.index.count : g.getAttribute('position').count; n += (c / 3) * (x.isInstancedMesh ? x.count : 1); } }); return Math.round(n); },
    closeUps: () => [...close.keys()],
    stageFor(i) { if (!L.seats[i]) return null; if (st.active !== i) { api.focus(i); api.active(i); } closeUp(i); return { seat: i, project: () => api.project(i) }; },
    release() { if (st.walk) { const w = st.walk; st.walk = null; if (w.done) w.done(false); } api.active(-1); },
    speaking: () => st.active,
    walk(i) {
      if (!L.seats[i]) return Promise.resolve(false);
      if (st.active !== i) api.active(i);
      const f = closeUp(i), s = L.seats[i], out = Math.hypot(s.x, s.z) || 1, k = (r + 3) / out;
      play(f, POSE_NAMES.indexOf('walk') >= 0 ? 'walk' : 'wave');
      if (reduced) return Promise.resolve(true);
      return new Promise((ok) => { st.walk = { i, t0: st.t, dur: 1.6, x0: f.position.x, y0: f.position.y, z0: f.position.z, x1: s.x * k, z1: s.z * k, ry: Math.atan2(s.x, s.z), done: ok }; });
    },
    speaker: () => (st.active >= 0 && close.has(st.active) ? { seat: st.active, ...close.get(st.active).userData.state() } : null),
    cine: () => cine,
    dispose() { gone = true; if (cine) cine.dispose(); window.removeEventListener('olympus:people:expression', onExpr); window.removeEventListener('olympus:people:open', onOpen); window.removeEventListener('olympus:people:close', onClose); window.removeEventListener('olympus:people:speak', onSpeak); window.removeEventListener('olympus:people:viseme', onViseme); try { rc.dispose(); } catch (_) { /* gone */ } for (const i of [...close.keys()]) dropClose(i); crowd.userData.dispose(); },
  };
  try { window.SYMPOSIUM_HALL = api; } catch (_) { /* no window */ }      // read-only hook for the page test
  return api;
}

/** a small turntable for "Make my character": one v2 figure on a marble disc, its own tiny renderer (no post passes). It waves, then shows a few faces. */
export function createTurntable(canvas, sp, opts) {
  const o = opts || {};
  try {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(30, 1, 0.1, 20);
    scene.add(new THREE.HemisphereLight('#ffe9c4', '#5a4630', 1.5)); const sun = new THREE.DirectionalLight('#ffd9a0', 2.3); sun.position.set(2, 4, 4); scene.add(sun);
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.56, 0.08, 28), new THREE.MeshStandardMaterial({ color: '#d9cfbb', roughness: 0.85 })); disc.position.y = -0.04; scene.add(disc);
    const holder = new THREE.Group(); scene.add(holder);
    let fig = null, raf = 0, t0 = performance.now(), last = t0, dead = false, angle = 0.5;
    function set(s) { if (fig) fig.userData.dispose(); fig = figure(THREE, s, {}); play(fig, 'wave', { then: 'idle' }); holder.add(fig); if (o.reduced) draw(0); }
    function fit() { const w = canvas.clientWidth || 200, h = canvas.clientHeight || 220; renderer.setSize(w, h, false); cam.aspect = w / h; cam.position.set(0, 0.8, 3.5); cam.lookAt(0, 0.52, 0); cam.updateProjectionMatrix(); }
    function draw(dt) { holder.rotation.y = angle; if (fig) { lookAt(fig, cam.position); if (dt) fig.userData.tick(dt, (performance.now() - t0) / 1000); } renderer.render(scene, cam); }
    function loop(now) { if (dead) return; const dt = Math.min(0.05, (now - last) / 1000); last = now; if (!document.hidden) { angle = 0.5 * Math.sin((now - t0) / 2600); draw(dt); } raf = requestAnimationFrame(loop); }
    fit(); set(sp);
    if (o.reduced) draw(0); else raf = requestAnimationFrame(loop);
    return { ok: true, set, fit, triangles: () => (fig ? fig.userData.triangles : 0), dispose() { dead = true; cancelAnimationFrame(raf); if (fig) fig.userData.dispose(); disc.geometry.dispose(); disc.material.dispose(); renderer.dispose(); } };
  } catch (e) { return { ok: false, reason: String(e && e.message ? e.message : e) }; }
}
