// PINAKES scene (ES module): a marble card-catalogue cabinet. Its five drawers are the districts (three r160, ../jarvis/three.module.min.js, no post passes).
//   the cabinet   a marble body on a plinth under a low pediment, five drawer fronts with a bronze label frame and a gold pull
//   a drawer      slides out when its district is chosen (400 ms ease-out, instant on reduced motion) and its ivory index cards fan up: the page then lists that district's tables
//   the light     a warm sun from the left and a soft hemisphere; no glow, no bloom
//   cost          it draws only while something moves (no idle spin), so a still cabinet costs nothing
// createCabinet(canvas, { O, districts: [{name, tables}], onPick(i) }) -> { select(i | -1), selected(), frames(), dispose() } or null when WebGL is not available (the page then draws its flat cabinet)
import * as THREE from '../jarvis/three.module.min.js';

const N = 5, DW = 1.06, DH = 1.5, GAP = 0.08, DEPTH = 1.5, OUT = 1.05, CARDS = 9;
const ease = (t) => 1 - Math.pow(1 - t, 3);

function labelTexture(name, sub) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 112;
  const g = c.getContext('2d');
  g.fillStyle = '#efe6d2'; g.fillRect(0, 0, 256, 112);
  g.fillStyle = '#2a2217'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.font = "600 44px 'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif"; g.fillText(name, 128, 44, 236);
  g.fillStyle = '#6b5a3c'; g.font = '600 26px -apple-system, system-ui, sans-serif'; g.fillText(sub, 128, 88, 236);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return t;
}

export function createCabinet(canvas, { O = null, districts = [], onPick = null } = {}) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' }); } catch (_) { return null; }
  if (!renderer || !renderer.getContext || !renderer.getContext()) return null;
  const reduced = () => { try { return O ? O.reduced() : !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (_) { return false; } };
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1.3, 0.1, 80);
  scene.add(new THREE.HemisphereLight('#f0dcb4', '#3a2c1e', 0.9));
  const sun = new THREE.DirectionalLight('#ffd9a0', 1.7); sun.position.set(-5, 7, 8); scene.add(sun);
  const fill = new THREE.DirectionalLight('#9bb6c8', 0.3); fill.position.set(6, 2, 5); scene.add(fill);

  const marble = new THREE.MeshStandardMaterial({ color: '#d8cdb8', roughness: 0.42, metalness: 0.04 });
  const marbleDark = new THREE.MeshStandardMaterial({ color: '#b9ad96', roughness: 0.5, metalness: 0.04 });
  const front = new THREE.MeshStandardMaterial({ color: '#e6dcc6', roughness: 0.38, metalness: 0.04 });
  const frontOn = new THREE.MeshStandardMaterial({ color: '#f1e7cf', roughness: 0.34, metalness: 0.04, emissive: '#3a2a08', emissiveIntensity: 0.18 });
  const bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.45, metalness: 0.7 });
  const gold = new THREE.MeshStandardMaterial({ color: '#c8a24a', roughness: 0.32, metalness: 0.85 });
  const ivory = new THREE.MeshStandardMaterial({ color: '#efe6d2', roughness: 0.8, metalness: 0 });
  const wood = new THREE.MeshStandardMaterial({ color: '#4a3a26', roughness: 0.8, metalness: 0.05 });
  const W = N * DW + (N + 1) * GAP, H = DH + 2 * GAP;
  const made = [];
  const box = (w, h, d, mat, x, y, z, parent) => { const geo = new THREE.BoxGeometry(w, h, d); made.push(geo); const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); (parent || scene).add(m); return m; };
  // the carcass: back, top, bottom, sides and the dividers between drawers (so an open drawer leaves a dark slot, not a hole)
  box(W, H, 0.08, marbleDark, 0, 0, -DEPTH / 2);
  box(W + 0.16, 0.14, DEPTH + 0.1, marble, 0, H / 2 + 0.07, 0);
  box(W + 0.16, 0.14, DEPTH + 0.1, marble, 0, -H / 2 - 0.07, 0);
  for (let i = 0; i <= N; i++) box(GAP, H, DEPTH, marble, -W / 2 + GAP / 2 + i * (DW + GAP), 0, 0);
  box(W + 0.5, 0.22, DEPTH + 0.4, marbleDark, 0, -H / 2 - 0.25, 0);                              // plinth
  box(W + 0.36, 0.1, DEPTH + 0.26, marbleDark, 0, H / 2 + 0.19, 0);                               // cornice
  const ped = new THREE.Shape(); ped.moveTo(-W / 2 - 0.18, 0); ped.lineTo(W / 2 + 0.18, 0); ped.lineTo(0, 0.62); ped.closePath();
  const pedGeo = new THREE.ExtrudeGeometry(ped, { depth: DEPTH + 0.2, bevelEnabled: false }); made.push(pedGeo);
  const pedM = new THREE.Mesh(pedGeo, marble); pedM.position.set(0, H / 2 + 0.24, -(DEPTH + 0.2) / 2); scene.add(pedM);
  const disc = new THREE.CylinderGeometry(0.16, 0.16, 0.04, 28); made.push(disc);
  const medal = new THREE.Mesh(disc, gold); medal.rotation.x = Math.PI / 2; medal.position.set(0, H / 2 + 0.45, DEPTH / 2 + 0.12); scene.add(medal);

  const knobGeo = new THREE.SphereGeometry(0.075, 18, 12), cardGeo = new THREE.BoxGeometry(DW - 0.22, DH * 0.6, 0.02); made.push(knobGeo, cardGeo);
  const drawers = [], fronts = [], textures = [];
  for (let i = 0; i < N; i++) {
    const g = new THREE.Group(); g.position.set(-W / 2 + GAP + DW / 2 + i * (DW + GAP), 0, 0); scene.add(g);
    const f = box(DW, DH, 0.1, front, 0, 0, DEPTH / 2 + 0.02, g); f.userData.i = i; fronts.push(f);
    box(DW - 0.08, 0.06, DEPTH - 0.1, wood, 0, -DH / 2 + 0.05, 0, g);                             // the drawer's floor
    box(0.04, DH * 0.55, DEPTH - 0.1, wood, -DW / 2 + 0.06, -DH * 0.2, 0, g); box(0.04, DH * 0.55, DEPTH - 0.1, wood, DW / 2 - 0.06, -DH * 0.2, 0, g);
    box(DW * 0.74, 0.44, 0.03, bronze, 0, DH * 0.2, DEPTH / 2 + 0.08, g);                         // label frame
    const d = districts[i] || { name: '', tables: 0 }, tex = labelTexture(d.name, `${d.tables} ${d.tables === 1 ? 'table' : 'tables'}`); textures.push(tex);
    const lm = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }), lg = new THREE.PlaneGeometry(DW * 0.66, 0.36); made.push(lg);
    const label = new THREE.Mesh(lg, lm); label.position.set(0, DH * 0.2, DEPTH / 2 + 0.1); g.add(label);
    const knob = new THREE.Mesh(knobGeo, gold); knob.position.set(0, -DH * 0.22, DEPTH / 2 + 0.13); g.add(knob);
    const cards = [];
    for (let k = 0; k < CARDS; k++) { const c = new THREE.Mesh(cardGeo, ivory); c.position.set(0, -DH * 0.14, DEPTH / 2 - 0.2 - k * 0.13); g.add(c); cards.push(c); }
    drawers.push({ g, f, cards, pos: 0, to: 0 });
  }

  let sel = -1, raf = 0, stopped = false, frames = 0, dirty = true, last = 0, lift = 0, liftTo = 0;
  function size() {
    const w = canvas.clientWidth || 320, h = canvas.clientHeight || 260, dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { renderer.setPixelRatio(dpr); renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); dirty = true; }
  }
  function place() {
    const half = (W + 0.9) / 2, dist = half / (Math.tan((camera.fov * Math.PI / 180) / 2) * camera.aspect) + DEPTH;
    camera.position.set(0, 0.9 + lift * 2.4, dist + lift * 0.4); camera.lookAt(0, 0.12, lift * 0.5);
  }
  function step(dt) {
    let moving = false; const k = reduced() ? 1 : Math.min(1, dt / 0.4);
    for (const d of drawers) {
      if (d.pos !== d.to) { d.pos = Math.abs(d.to - d.pos) <= k ? d.to : d.pos + Math.sign(d.to - d.pos) * k; moving = true; }
      const e = ease(d.pos); d.g.position.z = e * OUT;
      d.cards.forEach((c, j) => { const up = Math.max(0, Math.min(1, e * 1.6 - j * 0.07)); c.position.y = -DH * 0.14 + up * 0.34 * (1 - j / (CARDS * 1.6)); c.rotation.x = -up * 0.38; });
    }
    if (lift !== liftTo) { lift = Math.abs(liftTo - lift) <= k ? liftTo : lift + Math.sign(liftTo - lift) * k; moving = true; }
    return moving;
  }
  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (stopped || document.hidden) return;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 0.016; last = now;
    size();
    const moving = step(dt);
    if (!moving && !dirty) return;
    place(); renderer.render(scene, camera); dirty = false; frames++;
  }
  raf = requestAnimationFrame(frame);

  const ray = new THREE.Raycaster(), v2 = new THREE.Vector2();
  let down = null;
  const onDown = (e) => { down = [e.clientX, e.clientY]; };
  const onUp = (e) => {
    if (!down || Math.abs(e.clientX - down[0]) + Math.abs(e.clientY - down[1]) > 12) { down = null; return; }
    down = null;
    const r = canvas.getBoundingClientRect(); v2.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(v2, camera);
    const hit = ray.intersectObjects(fronts, false)[0];
    if (hit && onPick) onPick(hit.object.userData.i);
  };
  canvas.addEventListener('pointerdown', onDown); canvas.addEventListener('pointerup', onUp);

  return {
    select(i) {
      sel = Number.isInteger(i) && i >= 0 && i < N ? i : -1;
      drawers.forEach((d, j) => { d.to = j === sel ? 1 : 0; d.f.material = j === sel ? frontOn : front; });
      liftTo = sel >= 0 ? 1 : 0; dirty = true;
      if (reduced()) { step(1); }
    },
    selected: () => sel, frames: () => frames, open: () => drawers.map((d) => d.pos),
    dispose() {
      stopped = true; cancelAnimationFrame(raf); canvas.removeEventListener('pointerdown', onDown); canvas.removeEventListener('pointerup', onUp);
      try { made.forEach((g) => g.dispose()); textures.forEach((t) => t.dispose()); renderer.dispose(); } catch (_) { /* gone */ }
    },
  };
}
