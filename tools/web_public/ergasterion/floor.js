// ERGASTERION floor (ES module): the marble-and-bronze factory floor you walk in first person. One platform, one marble figure, one status lamp and one conveyor belt per worker,
// a Learning board on the back wall. Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm light (about 3000 K), bloom <= .2.
// Light by design: every repeated part is an InstancedMesh (platforms, rims, bodies, heads, arms, lamps, belts, belt items, columns), 15 label sprites and the board: about 25 draw calls.
// createFloor(canvas, { reduced, stations, eye, onPick }) -> { ok, set(workers, lessons), move({fwd,side}), look(dx,dy), follow(id|null), reset(), pos(), project(id), dispose() }
// If WebGL, the render core or the tier (LITE / off) says no, ok is false and the page keeps its flat plan view. Reduced motion: everything stands still and the camera jumps instead of gliding.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { walk, followCam, EYE, BOUNDS } from './ergasterioncore.js';

const LAMP = { working: '#8fa05a', idle: '#4b7a99', stale: '#e0b060', failed: '#c96a4a', sample: '#b8ad98' };
const SPEED = { working: 0.55, idle: 0.16, stale: 0, failed: 0, sample: 0.3 };

export function createFloor(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(62, 1.2, 0.1, 70);
    scene.background = new THREE.Color('#2a2118');
    scene.fog = new THREE.Fog('#2a2118', 16, 44);
    rc = createRenderer({ canvas, scene, camera, maxDpr: 2, tint: '#c8a24a', env: 'night',
      theme: { sky: '#5a3c22', fog: '#2a2118', emissive: '#c8a24a', bloom: '#e0b060', accent: '#c8a24a' }, bloom: { strength: 0.15, radius: 0.5, threshold: 1.0 } });
    const q = rc.quality();
    if (q === 'low' || q === 'off') { rc.dispose(); return { ok: false, mode: 'lite', reason: 'quality ' + q }; }
    return build(rc, scene, camera, canvas, o);
  } catch (e) {
    try { if (rc) rc.dispose(); } catch (_) { /* nothing */ }
    return { ok: false, mode: 'lite', reason: String(e && e.message ? e.message : e) };
  }
}

function labelTex(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return { c, t, g: c.getContext('2d') }; }
function wrap(g, text, x, y, maxW, lh, maxLines) {
  const words = String(text).split(' '); let line = '', n = 0;
  for (const w of words) {
    const t = line ? line + ' ' + w : w;
    if (g.measureText(t).width > maxW && line) { g.fillText(line, x, y + n * lh); n++; line = w; if (n >= maxLines) return n; } else line = t;
  }
  if (line && n < maxLines) { g.fillText(line, x, y + n * lh); n++; }
  return n;
}

function build(rc, scene, camera, canvas, o) {
  const reduced = !!o.reduced, S = o.stations || [], N = S.length, eye = o.eye || EYE;
  scene.add(new THREE.HemisphereLight(0xf0dcb8, 0x4a3a28, 1.05));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.1); sun.position.set(5, 12, 9); scene.add(sun);
  const mat = (c, r, m) => new THREE.MeshStandardMaterial({ color: c, roughness: r == null ? 0.5 : r, metalness: m || 0 });
  const marble = mat('#d9d2c3', 0.4, 0.02), bronze = mat('#9c6b3c', 0.38, 0.55), floorM = mat('#bdb29d', 0.55), wallM = mat('#a99f8d', 0.7), rugM = mat('#8f8574', 0.7);
  const dummy = new THREE.Object3D();
  const place = (im, i, x, y, z, sx, sy, sz, ry) => { dummy.position.set(x, y, z); dummy.scale.set(sx || 1, sy || 1, sz || 1); dummy.rotation.set(0, ry || 0, 0); dummy.updateMatrix(); im.setMatrixAt(i, dummy.matrix); };
  const box = (w, h, d, m, x, y, z) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); scene.add(b); return b; };

  // the room: floor, a bronze border, rugs for the four zones, a back wall, columns down both sides
  box(26, 0.2, 20.4, floorM, 0, -0.1, -0.2);
  box(26.4, 0.12, 0.3, bronze, 0, 0.02, -10.2); box(26.4, 0.12, 0.3, bronze, 0, 0.02, 9.8); box(0.3, 0.12, 20.4, bronze, -13.1, 0.02, -0.2); box(0.3, 0.12, 20.4, bronze, 13.1, 0.02, -0.2);
  box(22, 0.03, 4.2, rugM, 0, 0.012, -5.4); box(14, 0.03, 4.0, rugM, -2.2, 0.012, -0.4); box(14, 0.03, 4.0, rugM, -1.5, 0.012, 4.4);
  box(26, 5.6, 0.4, wallM, 0, 2.7, -10.4); box(26.4, 0.25, 0.7, marble, 0, 5.6, -10.3);
  const colG = new THREE.CylinderGeometry(0.3, 0.34, 4.9, 18), capG = new THREE.BoxGeometry(0.95, 0.22, 0.95), nCol = 14;
  const cols = new THREE.InstancedMesh(colG, marble, nCol), caps = new THREE.InstancedMesh(capG, marble, nCol);
  for (let i = 0; i < nCol; i++) { const x = i < 7 ? -12.6 : 12.6, z = -9 + (i % 7) * 3; place(cols, i, x, 2.45, z); place(caps, i, x, 5.0, z); }
  scene.add(cols, caps);

  // stations: platform + bronze rim + figure (body, head, two arms) + lamp post + belt
  const plat = new THREE.InstancedMesh(new THREE.CylinderGeometry(1.1, 1.2, 0.3, 28), marble, N);
  const rim = new THREE.InstancedMesh(new THREE.CylinderGeometry(1.24, 1.24, 0.08, 28), bronze, N);
  const body = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.17, 0.26, 0.95, 14), marble, N);
  const head = new THREE.InstancedMesh(new THREE.SphereGeometry(0.16, 14, 10), marble, N);
  const arm = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.05, 0.05, 0.5, 8), marble, N * 2);
  const post = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.04, 0.05, 1.5, 8), bronze, N);
  const lamp = new THREE.InstancedMesh(new THREE.SphereGeometry(0.15, 14, 10), new THREE.MeshBasicMaterial({ color: '#ffffff' }), N);
  const belt = new THREE.InstancedMesh(new THREE.BoxGeometry(2.7, 0.1, 0.5), bronze, N);
  const MAXI = 6, itemsM = new THREE.InstancedMesh(new THREE.BoxGeometry(0.22, 0.16, 0.22), new THREE.MeshBasicMaterial({ color: '#ffffff' }), N * MAXI);
  const colour = new THREE.Color();
  S.forEach((s, i) => {
    place(plat, i, s.x, 0.15, s.z); place(rim, i, s.x, 0.06, s.z); place(post, i, s.x + 0.85, 0.75, s.z - 0.55); place(lamp, i, s.x + 0.85, 1.58, s.z - 0.55); place(belt, i, s.x, 0.06, s.z + 1.75);
    lamp.setColorAt(i, colour.set(LAMP.stale));
  });
  [plat, rim, post, lamp, belt, body, head, arm, itemsM].forEach((m) => { m.instanceMatrix.setUsage(THREE.DynamicDrawUsage); m.frustumCulled = false; scene.add(m); });
  itemsM.setColorAt(0, colour.set('#ffffff'));

  // labels (sprites) and the Learning board on the back wall
  const sprites = S.map((s, i) => {
    const L = labelTex(320, 84), sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: L.t, transparent: true, depthWrite: false, fog: false }));
    sp.scale.set(2.4, 0.63, 1); sp.position.set(s.x, 2.45, s.z); scene.add(sp); return { sp, L, key: '' };
  });
  function drawLabel(i, w) {
    const L = sprites[i].L, g = L.g, key = w ? w.name + w.status : S[i].name;
    if (sprites[i].key === key) return; sprites[i].key = key;
    g.clearRect(0, 0, 320, 84);
    g.fillStyle = 'rgba(29,25,20,0.86)'; g.strokeStyle = '#9c6b3c'; g.lineWidth = 3;
    g.beginPath(); g.roundRect ? g.roundRect(4, 4, 312, 76, 14) : g.rect(4, 4, 312, 76); g.fill(); g.stroke();
    g.fillStyle = '#f3ece0'; g.font = '600 30px Georgia, serif'; g.textAlign = 'center'; g.fillText(S[i].name, 160, 38);
    g.fillStyle = w ? LAMP[w.status] : '#9a8f7d'; g.font = '600 22px -apple-system, sans-serif'; g.fillText(w ? ({ working: 'Working', idle: 'Idle', stale: 'Stale', failed: 'Failed', sample: 'Sample data' })[w.status] : '...', 160, 66);
    L.t.needsUpdate = true;
  }
  S.forEach((_, i) => drawLabel(i, null));
  const BW = 1024, BH = 560, B = labelTex(BW, BH);
  const boardMesh = new THREE.Mesh(new THREE.PlaneGeometry(9.6, 5.25), new THREE.MeshBasicMaterial({ map: B.t, fog: false }));
  boardMesh.position.set(0, 2.9, -10.18); scene.add(boardMesh);
  box(10.0, 5.65, 0.12, bronze, 0, 2.9, -10.25);
  function drawBoard(lessons) {
    const g = B.g; g.fillStyle = '#1d1914'; g.fillRect(0, 0, BW, BH);
    g.fillStyle = '#c8a24a'; g.font = '600 44px Georgia, serif'; g.textAlign = 'left'; g.fillText('Learning board', 32, 62); g.fillRect(32, 76, 120, 3);
    g.font = '500 26px -apple-system, sans-serif';
    const L = (lessons || []).slice(0, 6); let y = 124;
    if (!L.length) { g.fillStyle = '#cfc4b2'; g.fillText('No lessons recorded yet.', 32, y); }
    L.forEach((l) => {
      g.fillStyle = '#e0b060'; g.fillText(l.name + (l.d ? '  ' + l.d : ''), 32, y);
      g.fillStyle = '#f3ece0'; const n = wrap(g, l.text, 32, y + 32, BW - 64, 30, 2); y += 32 + n * 30 + 22;
    });
    B.t.needsUpdate = true;
  }
  drawBoard([]);

  // state
  let workers = [], cam = { x: 0, z: 7.4, yaw: 0, pitch: -0.08 }, mv = { fwd: 0, side: 0 }, following = null, t = 0, goal = null, ray = new THREE.Raycaster(), settled = true;
  const phase = S.map((_, i) => i * 1.7);
  const pos = () => ({ x: cam.x, z: cam.z, yaw: cam.yaw, following });
  function items(w) { return Math.max(0, Math.min(MAXI, w ? Math.max(w.items || 0, w.outputs ? w.outputs.length : 0) : 0)); }
  function frame(dt) {
    t += dt;
    const mot = reduced ? 0 : 1;
    S.forEach((s, i) => {
      const w = workers[i], st = w ? w.status : 'stale', sw = Math.sin(t * 3 + phase[i]) * mot, work = st === 'working' ? 1 : 0;
      const ox = work ? Math.sin(t * 0.6 + phase[i]) * 0.45 * mot : 0, bob = (work ? 0.03 : 0.012) * Math.sin(t * 2 + phase[i]) * mot;
      const fx = s.x + ox, fz = s.z, sink = st === 'failed' ? 0.02 : 0;
      place(body, i, fx, 0.3 + 0.475 + bob, fz, 1, 1, 1, ox * 0.4);
      place(head, i, fx, 1.38 + bob - sink, fz);
      for (let k = 0; k < 2; k++) { const a = (k ? 1 : -1); dummy.position.set(fx + a * 0.3, 1.0 + bob, fz + 0.12); dummy.scale.set(1, 1, 1); dummy.rotation.set(work ? -0.9 + sw * 0.4 * a : -0.15, 0, a * 0.25); dummy.updateMatrix(); arm.setMatrixAt(i * 2 + k, dummy.matrix); }
    });
    // belts: items drift left to right at the status speed; stopped belts hold still
    let c = 0;
    S.forEach((s, i) => {
      const w = workers[i], st = w ? w.status : 'stale', n = items(w), sp = reduced ? 0 : SPEED[st] || 0;
      for (let k = 0; k < MAXI; k++) {
        const idx = i * MAXI + k;
        if (k >= n) { place(itemsM, idx, s.x, -5, s.z); continue; }
        const f = (((k / Math.max(1, n)) + t * sp * 0.25) % 1 + 1) % 1;
        place(itemsM, idx, s.x - 1.2 + f * 2.4, 0.17, s.z + 1.75); c++;
        itemsM.setColorAt(idx, colour.set(LAMP[st] || LAMP.stale));
      }
    });
    [body, head, arm, itemsM].forEach((m) => { m.instanceMatrix.needsUpdate = true; });
    if (itemsM.instanceColor) itemsM.instanceColor.needsUpdate = true;
    // camera: walking, or following a worker
    if (following) {
      const i = S.findIndex((s) => s.id === following);
      if (i >= 0) {
        const fc = followCam({ x: S[i].x + (workers[i] && workers[i].status === 'working' ? Math.sin(t * 0.6 + phase[i]) * 0.45 * mot : 0), z: S[i].z }, t, reduced), k = reduced ? 1 : Math.min(1, dt * 2.2);
        camera.position.x += (fc.x - camera.position.x) * k; camera.position.y += (fc.y - camera.position.y) * k; camera.position.z += (fc.z - camera.position.z) * k;
        camera.lookAt(fc.look.x, fc.look.y, fc.look.z);
      }
    } else {
      if (mv.fwd || mv.side) { const p = walk({ x: cam.x, z: cam.z }, cam.yaw, mv, dt, S); cam.x = p.x; cam.z = p.z; }
      camera.position.set(cam.x, eye, cam.z); camera.rotation.order = 'YXZ'; camera.rotation.set(cam.pitch, cam.yaw, 0);
    }
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix();
    rc.render();
  }
  const api = {
    ok: true, mode: '3d', rc,
    set(ws, lessons) {
      workers = S.map((s) => (ws || []).find((w) => w.id === s.id) || null);
      workers.forEach((w, i) => { drawLabel(i, w); lamp.setColorAt(i, colour.set(LAMP[w ? w.status : 'stale'] || LAMP.stale)); });
      if (lamp.instanceColor) lamp.instanceColor.needsUpdate = true;
      drawBoard(lessons);
      if (reduced) frame(0.016);
    },
    move(m) { mv = { fwd: (m && m.fwd) || 0, side: (m && m.side) || 0 }; if (reduced && (mv.fwd || mv.side)) { /* still: the page steps the walk with step() */ } },
    step(dt) { const p = walk({ x: cam.x, z: cam.z }, cam.yaw, mv, dt || 0.1, S); cam.x = p.x; cam.z = p.z; frame(0.001); },
    look(dx, dy) { cam.yaw -= dx; cam.pitch = Math.max(-0.6, Math.min(0.5, cam.pitch - dy)); if (reduced) frame(0.001); },
    follow(id) { following = id || null; if (!following) { camera.position.set(cam.x, eye, cam.z); } if (reduced) frame(0.001); },
    teleport(x, z) { cam.x = Math.max(-BOUNDS.x, Math.min(BOUNDS.x, x)); cam.z = Math.max(-BOUNDS.z, Math.min(BOUNDS.z, z)); following = null; if (reduced) frame(0.001); },
    reset() { cam = { x: 0, z: 7.4, yaw: 0, pitch: -0.08 }; following = null; if (reduced) frame(0.001); },
    face(id) { const s = S.find((a) => a.id === id); if (s) { cam.yaw = Math.atan2(-(s.x - cam.x), -(s.z - cam.z)); if (reduced) frame(0.001); } },
    pos,
    project(id) { const s = S.find((a) => a.id === id); if (!s) return null; const v = new THREE.Vector3(s.x, 1.0, s.z).project(camera); if (v.z > 1) return null; return { x: (v.x * 0.5 + 0.5) * canvas.clientWidth, y: (-v.y * 0.5 + 0.5) * canvas.clientHeight }; },
    pick(cx, cy) {
      const r = canvas.getBoundingClientRect(), v = new THREE.Vector2(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(v, camera);
      const hp = ray.intersectObject(plat, false)[0];
      if (hp && S[hp.instanceId]) return S[hp.instanceId].id;
      let best = null, bd = 56;                    // forgiving: the nearest station on screen within 56 px (figure or lamp)
      S.forEach((s) => { const p = api.project(s.id); if (p) { const d = Math.hypot(p.x - (cx - r.left), p.y - (cy - r.top)); if (d < bd) { bd = d; best = s.id; } } });
      if (best) return best;
      return ray.intersectObject(boardMesh, false)[0] ? 'board' : null;
    },
    get settled() { return settled; },
    dispose() { try { rc.stop(); rc.dispose(); } catch (_) { /* nothing */ } },
  };
  // drag to look; a short tap with no drag picks a station
  let drag = null;
  const down = (e) => { drag = { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t0: performance.now() }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (!drag) return; api.look((e.clientX - drag.x) * 0.0055, (e.clientY - drag.y) * 0.0045); drag.x = e.clientX; drag.y = e.clientY; };
  const up = (e) => {
    if (drag && Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 8 && typeof o.onPick === 'function') { const id = api.pick(e.clientX, e.clientY); if (id) o.onPick(id); }
    drag = null;
  };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', () => { drag = null; });
  rc.start((dt) => { frame(dt); });
  if (reduced) frame(0.016);
  return api;
}
