// ARENA scene (ES module, three.js from ../jarvis/three.module.min.js): the colosseum.
//   the rank emblem   a laurel crown floating over the altar, glowing in the rank's colour
//   XP                a column of light rising from the altar; its height is the progress to the next rank
//   the 12 Labours    statues in a ring, stone until earned, then gold with a halo; a tap on one calls onPick(id)
//   level-up          lightning from the sky to the crown + a burst of gold particles (rank-up: more of both)
// createScene(canvas, { O }) -> { setState(s), levelUp({ rank }), onPick(cb), stats(), lite(), dispose() }
// Performance (docs/OLYMPUS_DESIGN.md): pixel ratio from O.dpr(), no frame while hidden, automatic LITE after slow frames when
// the owner chose no level, reduced motion = no drift (a still scene redrawn on input or data).
import * as THREE from '../jarvis/three.module.min.js';

const TAU = Math.PI * 2;
const GOLD = new THREE.Color('#ffcf5a');

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.25, 'rgba(255,240,200,.75)'); r.addColorStop(1, 'rgba(255,200,80,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function lightColumnMaterial(color) {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(color) }, uTime: { value: 0 }, uPower: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform vec3 uColor; uniform float uTime; uniform float uPower; varying vec2 vUv;' +
      'void main(){ float fade = pow(max(1.0 - vUv.y, 0.0001), 0.7);' +
      'float band = 0.75 + 0.25 * sin(uTime * 2.4 - vUv.y * 18.0);' +
      'gl_FragColor = vec4(uColor * (1.2 + 0.6 * band), fade * 0.42 * band * uPower); }',
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
}

export function createScene(canvas, { O = null } = {}) {
  const lite0 = O ? O.lite() : false;
  const reduced = () => (O ? O.reduced() : !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches));
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !lite0, alpha: false, powerPreference: 'high-performance' });
  if (O) O.track(renderer);
  renderer.setPixelRatio(O ? O.dpr() : Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#07050c');
  scene.fog = new THREE.Fog('#07050c', 16, 34);
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 80);
  const glow = glowTexture();
  let lite = lite0, dirty = true;

  // ---- light
  scene.add(new THREE.HemisphereLight('#8c7cff', '#1a1208', 0.55));
  const moon = new THREE.DirectionalLight('#c9d4ff', 0.9); moon.position.set(-6, 12, 8); scene.add(moon);
  const crownLight = new THREE.PointLight('#ffcf5a', 7, 14, 1.6); crownLight.position.set(0, 3.2, 0); scene.add(crownLight);

  // ---- the arena: sand floor, the ring of columns, three tiers of seats
  const floor = new THREE.Mesh(new THREE.CircleGeometry(10.2, 64), new THREE.MeshStandardMaterial({ color: '#2a2016', roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; scene.add(floor);
  const ring = new THREE.Mesh(new THREE.RingGeometry(3.6, 3.75, 64), new THREE.MeshBasicMaterial({ color: '#7a5a22', transparent: true, opacity: 0.6 }));
  ring.rotation.x = -Math.PI / 2; ring.position.y = 0.01; scene.add(ring);
  const stone = new THREE.MeshStandardMaterial({ color: '#4b4655', roughness: 0.85, metalness: 0.05 });
  const NCOL = 28;
  const cols = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.2, 0.24, 3.4, 10), stone, NCOL);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < NCOL; i++) { const a = (i / NCOL) * TAU; m4.makeTranslation(Math.cos(a) * 10.6, 1.7, Math.sin(a) * 10.6); cols.setMatrixAt(i, m4); }
  scene.add(cols);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(10.9, 10.9, 0.35, 64, 1, true), new THREE.MeshStandardMaterial({ color: '#5b5466', roughness: 0.8, side: THREE.DoubleSide }));
  beam.position.y = 3.55; scene.add(beam);
  for (let k = 0; k < 3; k++) {
    const tier = new THREE.Mesh(new THREE.CylinderGeometry(11.8 + k * 1.3, 11.8 + k * 1.3, 1.1, 64, 1, true),
      new THREE.MeshStandardMaterial({ color: k % 2 ? '#3a3442' : '#443d4e', roughness: 0.9, side: THREE.BackSide }));
    tier.position.y = 0.9 + k * 1.15; scene.add(tier);
  }
  // stars
  const NST = lite ? 200 : 600, sp = new Float32Array(NST * 3);
  for (let i = 0; i < NST; i++) {
    const a = Math.random() * TAU, e = 0.15 + Math.random() * 1.2, r = 30;
    sp[i * 3] = Math.cos(a) * Math.cos(e) * r; sp[i * 3 + 1] = Math.sin(e) * r; sp[i * 3 + 2] = Math.sin(a) * Math.cos(e) * r;
  }
  const stars = new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(sp, 3)),
    new THREE.PointsMaterial({ color: '#d9d4ff', size: 0.09, transparent: true, opacity: 0.8, fog: false }));
  scene.add(stars);

  // ---- the altar, the crown and the column of light
  const altar = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.1, 0.8, 24), new THREE.MeshStandardMaterial({ color: '#5a5262', roughness: 0.7 }));
  altar.position.y = 0.4; scene.add(altar);
  const crown = new THREE.Group(); crown.position.set(0, 2.7, 0); crown.rotation.x = 0.55; scene.add(crown);
  const gold = new THREE.MeshStandardMaterial({ color: '#e8b04a', metalness: 0.85, roughness: 0.28, emissive: '#ffcf5a', emissiveIntensity: 0.28 });
  const NL = 15, leafGeo = new THREE.SphereGeometry(1, 10, 6); leafGeo.scale(0.07, 0.022, 0.2);
  const leaves = new THREE.InstancedMesh(leafGeo, gold, NL * 4);
  const q = new THREE.Quaternion(), e3 = new THREE.Euler(), s3 = new THREE.Vector3(1, 1, 1), p3 = new THREE.Vector3();
  let li = 0;
  for (const side of [-1, 1]) for (let i = 0; i < NL; i++) for (const row of [0, 1]) {
    const a = Math.PI / 2 + side * (0.22 + (i / (NL - 1)) * 2.7), r = 0.95 + (row ? 0.1 : -0.08);    // two branches meeting at the back
    p3.set(Math.cos(a) * r, (row ? 0.05 : -0.03), Math.sin(a) * r);
    e3.set(0, -a + (row ? 0.75 : -0.75) * side + Math.PI / 2, row ? 0.25 : -0.25);
    q.setFromEuler(e3); m4.compose(p3, q, s3); leaves.setMatrixAt(li++, m4);
  }
  crown.add(leaves);
  const band = new THREE.Mesh(new THREE.TorusGeometry(0.95, 0.025, 6, 64, TAU - 0.44), gold);
  band.rotation.x = Math.PI / 2; band.rotation.z = Math.PI / 2 + 0.22; crown.add(band);
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: '#ffcf5a', transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
  halo.scale.set(4.2, 4.2, 1); halo.position.copy(crown.position); scene.add(halo);
  const colMat = lightColumnMaterial('#ffcf5a'), coreMat = lightColumnMaterial('#fff4d6');
  const colGeo = new THREE.CylinderGeometry(0.5, 0.5, 1, 32, 1, true); colGeo.translate(0, 0.5, 0);
  const column = new THREE.Mesh(colGeo, colMat), core = new THREE.Mesh(colGeo, coreMat);
  column.position.y = core.position.y = 0.8; core.scale.set(0.35, 1, 0.35); scene.add(column); scene.add(core);
  // the ghost: the full height of the rank, faint, so the column reads as "how far to the next rank"
  const ghostMat = lightColumnMaterial('#ffcf5a'); ghostMat.uniforms.uPower.value = 0.16;
  const ghost = new THREE.Mesh(colGeo, ghostMat); ghost.position.y = 0.8; ghost.scale.set(1.02, 9.9, 1.02); scene.add(ghost);
  const NM = lite ? 40 : 140, mp = new Float32Array(NM * 3), mv = new Float32Array(NM);
  for (let i = 0; i < NM; i++) { const a = Math.random() * TAU, r = Math.random() * 0.45; mp[i * 3] = Math.cos(a) * r; mp[i * 3 + 1] = Math.random() * 8; mp[i * 3 + 2] = Math.sin(a) * r; mv[i] = 0.6 + Math.random() * 1.4; }
  const motes = new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(mp, 3)),
    new THREE.PointsMaterial({ map: glow, color: '#ffe3a0', size: 0.16, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  motes.position.y = 0.8; scene.add(motes);

  // ---- the 12 statues
  const profile = [[0, 0], [0.26, 0], [0.3, 0.12], [0.2, 0.25], [0.17, 0.85], [0.27, 1.12], [0.2, 1.28], [0.07, 1.34], [0, 1.35]].map(([x, y]) => new THREE.Vector2(x, y));
  const bodyGeo = new THREE.LatheGeometry(profile, 14), headGeo = new THREE.SphereGeometry(0.15, 12, 10), baseGeo = new THREE.BoxGeometry(0.8, 0.5, 0.8);
  const stoneStatue = new THREE.MeshStandardMaterial({ color: '#5d5867', roughness: 0.92 });
  const statues = [];
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * TAU - Math.PI / 2, g = new THREE.Group();
    g.position.set(Math.cos(a) * 7, 0, Math.sin(a) * 7);
    g.lookAt(0, 0, 0);
    const base = new THREE.Mesh(baseGeo, stone); base.position.y = 0.25;
    const body = new THREE.Mesh(bodyGeo, stoneStatue); body.position.y = 0.5;
    const head = new THREE.Mesh(headGeo, stoneStatue); head.position.y = 2.0;
    const h = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: '#ffcf5a', transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    h.scale.set(2.4, 3.2, 1); h.position.y = 1.4;
    g.add(base, body, head, h);
    scene.add(g);
    statues.push({ g, body, head, halo: h, id: null, earned: false, i });
  }
  const goldStatue = new THREE.MeshStandardMaterial({ color: '#d9a441', metalness: 0.9, roughness: 0.3, emissive: '#ffb547', emissiveIntensity: 0.35 });

  // ---- effects: lightning and the gold burst
  const fx = { bolts: [], burst: null, until: 0 };
  function bolt(x0, z0) {
    const pts = [], n = 16, top = new THREE.Vector3(x0, 15, z0), end = new THREE.Vector3(0, 2.8, 0);
    for (let i = 0; i <= n; i++) {
      const f = i / n, p = top.clone().lerp(end, f);
      if (i && i < n) { p.x += (Math.random() - 0.5) * 1.3; p.z += (Math.random() - 0.5) * 1.3; }
      pts.push(p);
    }
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: '#d6ecff', transparent: true, opacity: 1, blending: THREE.AdditiveBlending, fog: false }));
    scene.add(line);
    return line;
  }
  function burst(n) {
    const pos = new Float32Array(n * 3), vel = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU, u = Math.random() * 0.9 + 0.1, s = 2 + Math.random() * 5;
      pos[i * 3] = 0; pos[i * 3 + 1] = 2.8; pos[i * 3 + 2] = 0;
      vel[i * 3] = Math.cos(a) * s * u; vel[i * 3 + 1] = 3 + Math.random() * 6; vel[i * 3 + 2] = Math.sin(a) * s * u;
    }
    const pts = new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(pos, 3)),
      new THREE.PointsMaterial({ map: glow, color: GOLD, size: 0.32, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    scene.add(pts);
    return { pts, vel, age: 0, n };
  }
  function clearFx() {
    for (const b of fx.bolts) { scene.remove(b); b.geometry.dispose(); b.material.dispose(); }
    fx.bolts = [];
    if (fx.burst) { scene.remove(fx.burst.pts); fx.burst.pts.geometry.dispose(); fx.burst.pts.material.dispose(); fx.burst = null; }
  }

  // ---- state
  const st = { progress: 0, shown: 0, color: new THREE.Color('#ffcf5a'), labours: [] };
  let pick = null, levelups = 0;
  function setState(s) {
    st.progress = Math.max(0.03, Math.min(1, +s.progress || 0));
    st.color.set(s.color || '#ffcf5a');
    gold.emissive.copy(st.color); halo.material.color.copy(st.color); crownLight.color.copy(st.color);
    (s.labours || []).forEach((l, i) => {
      const x = statues[i]; if (!x) return;
      x.id = l.id; x.earned = !!l.earned;
      x.body.material = x.head.material = x.earned ? goldStatue : stoneStatue;
      x.halo.material.opacity = x.earned ? 0.5 : 0;
      x.body.userData.labour = x.head.userData.labour = l.id;
    });
    if (reduced()) st.shown = st.progress;
    dirty = true;
  }
  function levelUp({ rank = false } = {}) {
    levelups++;
    clearFx();
    const nb = reduced() ? 1 : rank ? 5 : 3;
    for (let i = 0; i < nb; i++) { const a = Math.random() * TAU; fx.bolts.push(bolt(Math.cos(a) * 4, Math.sin(a) * 4)); }
    fx.burst = burst((lite ? 160 : 420) * (rank ? 1.5 : 1) | 0);
    fx.t0 = performance.now(); fx.rank = rank;
    dirty = true;
  }

  // ---- camera: a slow orbit (none under reduced motion), drag to turn, tap a statue
  const cam = { theta: 0.35, phi: 0.78, dist: 15.5, drag: null };
  function placeCamera() {
    const r = cam.dist;
    camera.position.set(Math.sin(cam.theta) * Math.cos(cam.phi) * r, 1.6 + Math.sin(cam.phi) * r, Math.cos(cam.theta) * Math.cos(cam.phi) * r);
    camera.lookAt(0, 2.4, 0);                    // above the altar: the ring sits low, under the HUD
  }
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  canvas.addEventListener('pointerdown', (e) => { cam.drag = { x: e.clientX, y: e.clientY, t: cam.theta, p: cam.phi, moved: 0 }; });
  canvas.addEventListener('pointermove', (e) => {
    if (!cam.drag) return;
    const dx = e.clientX - cam.drag.x, dy = e.clientY - cam.drag.y;
    cam.drag.moved = Math.max(cam.drag.moved, Math.abs(dx) + Math.abs(dy));
    cam.theta = cam.drag.t - dx * 0.008;
    cam.phi = Math.max(0.25, Math.min(1.05, cam.drag.p + dy * 0.004));
    dirty = true;
  });
  const up = (e) => {
    const d = cam.drag; cam.drag = null;
    if (!d || d.moved > 8) return;
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(statues.flatMap((s) => [s.body, s.head]), false)[0];
    if (pick) pick((hit && hit.object.userData.labour) || null);
  };
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', () => { cam.drag = null; });

  function resize() {
    const w = canvas.clientWidth || innerWidth, h = canvas.clientHeight || innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    cam.dist = w / h < 0.6 ? 25 : 17;                         // a tall phone needs the camera further back to fit the ring
    camera.updateProjectionMatrix();
    dirty = true;
  }
  addEventListener('resize', resize);
  resize();

  // ---- the frame loop
  let last = performance.now(), slow = 0, frames = 0, raf = 0, stopped = false;
  function setLite(v) {
    lite = !!v;
    renderer.setPixelRatio(O ? O.dpr(lite) : lite ? 1 : Math.min(devicePixelRatio || 1, 2));
    motes.geometry.setDrawRange(0, lite ? Math.min(40, NM) : NM);
    stars.geometry.setDrawRange(0, lite ? 200 : NST);
    if (O) O.mode(lite);
    resize();
  }
  if (O) O.mode(lite);
  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (stopped || (O && O.hidden())) { last = now; return; }
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    frames++;
    if (frames > 30 && frames < 150 && !lite && !(O && O.chosen())) { slow = dt > 0.034 ? slow + 1 : Math.max(0, slow - 1); if (slow > 40) setLite(true); }
    const still = reduced();
    const busy = fx.bolts.length || fx.burst || Math.abs(st.shown - st.progress) > 0.001;
    if (still && !busy && !dirty) return;
    const t = now / 1000;
    if (!still) { cam.theta += cam.drag ? 0 : dt * 0.06; crown.rotation.z = Math.sin(t * 0.5) * 0.08; crown.rotation.y += dt * 0.25; }
    st.shown += (st.progress - st.shown) * Math.min(1, dt * (still ? 60 : 1.6));
    column.scale.y = core.scale.y = 0.4 + st.shown * 9.5;
    colMat.uniforms.uTime.value = coreMat.uniforms.uTime.value = ghostMat.uniforms.uTime.value = t;
    halo.material.opacity = 0.45 + (still ? 0 : Math.sin(t * 2) * 0.1);
    if (!still) {
      const arr = motes.geometry.attributes.position.array, top = 0.4 + st.shown * 9.5;
      for (let i = 0; i < NM; i++) { arr[i * 3 + 1] += mv[i] * dt; if (arr[i * 3 + 1] > top) arr[i * 3 + 1] = 0; }
      motes.geometry.attributes.position.needsUpdate = true;
      statues.forEach((s) => { if (s.earned) s.halo.material.opacity = 0.42 + Math.sin(t * 1.5 + s.i) * 0.1; });
    }
    if (fx.bolts.length || fx.burst) {
      const age = (now - fx.t0) / 1000;
      for (const b of fx.bolts) b.material.opacity = age < 0.9 ? (Math.sin(age * 40) > -0.2 ? 1 : 0.15) * (1 - age / 0.9) : 0;
      crownLight.intensity = 7 + (age < 0.9 ? 60 * (1 - age / 0.9) : 0);
      if (fx.burst) {
        const B = fx.burst, a = B.pts.geometry.attributes.position.array;
        B.age += dt;
        for (let i = 0; i < B.n; i++) { a[i * 3] += B.vel[i * 3] * dt; a[i * 3 + 1] += B.vel[i * 3 + 1] * dt; a[i * 3 + 2] += B.vel[i * 3 + 2] * dt; B.vel[i * 3 + 1] -= 6 * dt; }
        B.pts.geometry.attributes.position.needsUpdate = true;
        B.pts.material.opacity = Math.max(0, 1 - B.age / 2.6);
      }
      if (age > 2.8) { clearFx(); crownLight.intensity = 7; }
    }
    placeCamera();
    renderer.render(scene, camera);
    dirty = false;
  }
  placeCamera();
  raf = requestAnimationFrame(frame);

  return {
    setState, levelUp, setLite,
    onPick(cb) { pick = typeof cb === 'function' ? cb : null; },
    lite: () => lite,
    stats: () => ({ levelups, lite, bolts: fx.bolts.length, burst: !!fx.burst, frames, statues: statues.filter((s) => s.earned).length }),
    dispose() { stopped = true; cancelAnimationFrame(raf); clearFx(); renderer.dispose(); },
  };
}
