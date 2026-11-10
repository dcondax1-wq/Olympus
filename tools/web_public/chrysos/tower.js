// CHRYSOS tower (ES module): the 3D scene of the gold. Per account a marble plinth, a bronze column (the fees paid so far) and a stack of gold coins (the payouts received so far).
// A thin olive line at the top of the bronze column shows "fees paid back": when the coins climb past it, the account is in profit. The towers RISE when the month moves.
// Built on the OLYMPUS render core (../olympus/render.js, three.js r160 from ../jarvis/). Warm sun, marble floor, bloom <= .25. Draws nothing from data except heights.
// createTower(canvas) -> { ok, set(model), tick settled, dispose() }. If WebGL or the render core is not there, ok is false and the page shows its flat tower drawing instead.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';

const COIN_H = 0.16, MAX_COINS = 40, COL_R = 0.38, GAP = 1.9;

export function createTower(canvas, opts) {
  const o = opts || {};
  let rc = null;
  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1.4, 0.1, 80);
    scene.background = new THREE.Color('#2a2118');
    scene.fog = new THREE.Fog('#2a2118', 14, 34);
    rc = createRenderer({ canvas, scene, camera, maxDpr: 2, tint: '#c8a24a', env: 'night',
      theme: { sky: '#3a2c1c', fog: '#2a2118', emissive: '#c8a24a', bloom: '#e0b060', accent: '#c8a24a' }, bloom: { strength: 0.2, radius: 0.5, threshold: 1.0 } });
    const q = rc.quality();
    if (q === 'low' || q === 'off') { rc.dispose(); return { ok: false, mode: 'lite', reason: 'quality ' + q }; }
    return build(rc, scene, camera, canvas, o);
  } catch (e) {
    try { if (rc) rc.dispose(); } catch (_) { /* nothing */ }
    return { ok: false, mode: 'lite', reason: String(e && e.message ? e.message : e) };
  }
}

function build(rc, scene, camera, canvas, o) {
  const reduced = !!o.reduced;
  scene.add(new THREE.HemisphereLight(0xf0dcb8, 0x4a3a28, 1.1));
  const sun = new THREE.DirectionalLight(0xffd9a0, 2.4); sun.position.set(5, 9, 6); scene.add(sun);        // about 3000 K afternoon sun
  const fill = new THREE.PointLight(0xe0a060, 14, 18, 1.5); fill.position.set(-4, 3, 4); scene.add(fill);
  const marble = new THREE.MeshStandardMaterial({ color: '#d9d2c3', roughness: 0.42, metalness: 0.02 });
  const floor = new THREE.Mesh(new THREE.CircleGeometry(14, 64), new THREE.MeshStandardMaterial({ color: '#8f8574', roughness: 0.6, metalness: 0 })); floor.rotation.x = -Math.PI / 2; floor.position.y = -0.02; scene.add(floor);
  const bronzeM = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.45, metalness: 0.7 });
  const goldM = new THREE.MeshStandardMaterial({ color: '#e0b868', roughness: 0.35, metalness: 0.6, emissive: new THREE.Color('#6a5014'), emissiveIntensity: 0.5 });
  const oliveM = new THREE.MeshStandardMaterial({ color: '#7f8a52', roughness: 0.5, metalness: 0.1 });
  const coinG = new THREE.CylinderGeometry(COL_R, COL_R, COIN_H * 0.86, 28);
  const colG = new THREE.CylinderGeometry(COL_R, COL_R * 1.04, 1, 28);
  const plinthG = new THREE.CylinderGeometry(0.95, 1.05, 0.22, 36);
  const ringG = new THREE.TorusGeometry(COL_R * 1.5, 0.025, 8, 40);
  const group = new THREE.Group(); scene.add(group);
  let items = [], target = { unit: 100, towers: [] }, yaw = 0.35, drag = null, settled = true;

  function clear() { for (const it of items) { group.remove(it.g); } items = []; }
  function layout(n) {
    clear();
    const w = (n - 1) * GAP;
    for (let i = 0; i < n; i++) {
      const g = new THREE.Group(); g.position.set(i * GAP - w / 2, 0, 0);
      const plinth = new THREE.Mesh(plinthG, marble); plinth.position.set(0, 0.09, 0); g.add(plinth);
      const bronze = new THREE.Mesh(colG, bronzeM); bronze.position.set(-0.46, 0.2, 0); g.add(bronze);
      const coins = new THREE.InstancedMesh(coinG, goldM, MAX_COINS); coins.position.set(0.46, 0.2, 0); coins.count = 0; g.add(coins);
      const ring = new THREE.Mesh(ringG, oliveM); ring.rotation.x = Math.PI / 2; ring.position.set(-0.46, 0.2, 0); g.add(ring);
      group.add(g); items.push({ g, bronze, coins, ring, h: 0, c: 0, dummy: new THREE.Object3D() });
    }
    const span = Math.max(4.2, w + 3.2);
    camera.userData.dist = span * 1.25 + 2.5;
  }
  function frame() {
    const d = camera.userData.dist || 9;
    camera.position.set(Math.sin(yaw) * d, d * 0.42 + 1.2, Math.cos(yaw) * d);
    camera.lookAt(0, 1.7, 0);
  }

  const api = {
    ok: true, mode: '3d', rc,
    set(model) {
      if (!model || !Array.isArray(model.towers)) return;
      if (items.length !== model.towers.length) layout(model.towers.length);
      target = model; settled = false;
    },
    get settled() { return settled; },
    get towers() { return items.length; },
    get yaw() { return yaw; },
    dispose() { try { rc.stop(); rc.dispose(); } catch (_) { /* nothing */ } },
  };

  // drag to turn the plinths; the page still scrolls up and down (touch-action: pan-y)
  const down = (e) => { drag = { x: e.clientX, yaw }; try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* nothing */ } };
  const move = (e) => { if (drag) { yaw = drag.yaw - (e.clientX - drag.x) * 0.008; settled = false; } };
  const up = () => { drag = null; };
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);

  rc.start((dt) => {
    let moving = !!drag;
    const k = reduced ? 1 : Math.min(1, dt * 3.2);              // slow ease-out: the towers rise over about a second
    items.forEach((it, i) => {
      const t = target.towers[i]; if (!t) return;
      const hGoal = Math.max(0.05, Math.min(7, (t.fees / target.unit) * COIN_H)), cGoal = Math.min(MAX_COINS, t.coins);
      it.h += (hGoal - it.h) * k; it.c += (cGoal - it.c) * k;
      if (Math.abs(hGoal - it.h) > 0.004 || Math.abs(cGoal - it.c) > 0.04) moving = true; else { it.h = hGoal; it.c = cGoal; }
      it.bronze.scale.y = it.h; it.bronze.position.y = 0.2 + it.h / 2;
      it.ring.position.y = 0.2 + it.h; it.ring.visible = it.c > 0;
      const n = Math.round(it.c); it.coins.count = n;
      for (let j = 0; j < n; j++) { it.dummy.position.set(0, j * COIN_H + COIN_H / 2, 0); it.dummy.rotation.y = j * 0.7; it.dummy.updateMatrix(); it.coins.setMatrixAt(j, it.dummy.matrix); }
      it.coins.instanceMatrix.needsUpdate = true;
    });
    if (!reduced && !drag && !moving) yaw += dt * 0.12;
    if (reduced && !moving) { /* still */ }
    settled = !moving;
    frame();
    camera.aspect = (canvas.clientWidth || 1) / (canvas.clientHeight || 1); camera.updateProjectionMatrix();
    rc.render();
  });
  layout(1); frame();
  return api;
}
