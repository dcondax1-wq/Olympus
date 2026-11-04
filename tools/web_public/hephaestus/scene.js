// HEPHAESTUS scene (ES module): a forge and an anvil on the OLYMPUS render core.
//   the anvil     gunmetal base, chrome face, a horn; the ingot on it is the setting you are testing
//   the ingot     glows in the verdict's colour; its size follows the 2026 net $ against the live setting (the ghost outline is live)
//   the hammer    strikes (with sparks) every time a dial is turned
//   the furnace   embers behind, a quench barrel beside
// createForge(canvas, { O }) -> { setState({ color, scale, kind }), strike(), onQuality(cb), lite(), quality(), stats(), dispose() }
// Reduced motion: no frame is drawn while nothing changes; a strike is a single flash instead of an animation.
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import * as M from '../olympus/materials.js';

const hdr = (c, k) => new THREE.Color(c).multiplyScalar(k);

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.3, 'rgba(255,255,255,.55)'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export function createForge(canvas, { O = null } = {}) {
  const reduced = () => (O ? O.reduced() : !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#0b0608');
  scene.fog = new THREE.FogExp2(0x1a0a0c, 0.045);
  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
  let lastT = 0, lite = false, dirty = true, qcb = null, drawn = 0, frames = 0, stopped = false, raf = 0, strikes = 0;
  const rc = createRenderer({ canvas, scene, camera, env: 'night', tint: '#d96bff', exposure: 0.95, maxDpr: 1.75, bloom: { strength: 0.8, radius: 0.55, threshold: 0.9 },
    onQuality: (l) => { lite = l === 'low' || l === 'off'; setCounts(); dirty = true; if (qcb) qcb(l); } });
  lite = rc.quality() === 'low' || rc.quality() === 'off';
  const glow = glowTexture();

  // ---- light
  scene.add(new THREE.HemisphereLight('#8a7aa8', '#1a0c0a', 0.55));
  const key = new THREE.DirectionalLight('#ffe2c4', 1.1); key.position.set(3, 6, 5); scene.add(key);
  const rim = new THREE.DirectionalLight('#9fb4ff', 0.9); rim.position.set(-4, 3, -5); scene.add(rim);
  const fire = new THREE.PointLight('#ff7a30', 26, 14, 1.5); fire.position.set(-3.2, 1.6, -1.6); scene.add(fire);
  const ingotLight = new THREE.PointLight('#ffb547', 6, 6, 1.6); ingotLight.position.set(0, 2.3, 0.4); scene.add(ingotLight);

  // ---- floor: a round stone dais
  const dais = new THREE.Mesh(new THREE.CylinderGeometry(4.6, 4.8, 0.3, 48), M.marble({ color: '#3a3238', gold: false, scale: 0.5, roughness: 0.5 }));
  dais.position.y = -0.15; scene.add(dais);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(4.6, 0.04, 8, 96), M.neon({ color: '#d96bff', intensity: 2.2, fog: true }));
  ring.rotation.x = Math.PI / 2; ring.position.y = 0.02; scene.add(ring);

  // ---- the anvil
  const steel = M.metal({ kind: 'gunmetal', color: '#3c3a48', roughness: 0.38 }), chrome = M.metal({ kind: 'chrome', roughness: 0.18 });
  const anvil = new THREE.Group(); scene.add(anvil);
  const part = (geo, mat, x, y, z, rz = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.rotation.z = rz; anvil.add(m); return m; };
  part(new THREE.BoxGeometry(2.0, 0.45, 1.2), steel, 0, 0.225, 0);
  part(new THREE.BoxGeometry(1.2, 0.7, 0.8), steel, 0, 0.8, 0);
  part(new THREE.BoxGeometry(2.7, 0.34, 1.0), chrome, 0, 1.32, 0);
  part(new THREE.ConeGeometry(0.5, 1.3, 20), chrome, 1.95, 1.32, 0, -Math.PI / 2);
  part(new THREE.BoxGeometry(0.5, 0.3, 0.9), steel, -1.5, 1.28, 0);

  // ---- the ingot (this setting) and its ghost (live)
  const iMat = new THREE.MeshStandardMaterial({ color: '#ffb547', emissive: new THREE.Color('#ffb547'), emissiveIntensity: 1.0, roughness: 0.4, metalness: 0.2 });
  const ingot = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.3, 0.5), iMat);
  const ingotG = new THREE.Group(); ingotG.position.set(0, 1.64, 0); ingotG.add(ingot); ingot.position.y = 0.15 - 0.15; scene.add(ingotG);
  const ghost = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.0, 0.3, 0.5)), new THREE.LineBasicMaterial({ color: hdr('#cfd6ff', 1.4), transparent: true, opacity: 0.55 }));
  ghost.position.set(0, 1.64, 0); scene.add(ghost);
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: hdr('#ffb547', 1.8), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
  halo.scale.set(3.2, 2.0, 1); halo.position.set(0, 1.8, 0); scene.add(halo);

  // ---- the hammer (pivot at the right of the anvil)
  const hammer = new THREE.Group(); hammer.position.set(1.15, 2.05, 0.95); scene.add(hammer);
  const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, 1.9, 10), M.metal({ kind: 'gunmetal', color: '#5a3c28', roughness: 0.7 }));
  handle.position.y = 0.95; const head = new THREE.Mesh(new THREE.BoxGeometry(0.75, 0.38, 0.38), chrome); head.position.y = 1.9;
  hammer.add(handle, head);
  const REST = -0.95, HIT = 0.0;
  hammer.rotation.z = REST; hammer.rotation.x = 0;

  // ---- the furnace behind-left
  const furnace = new THREE.Group(); furnace.position.set(-3.4, 0, -2.2); furnace.rotation.y = 0.5; scene.add(furnace);
  const body = new THREE.Mesh(new THREE.BoxGeometry(2.4, 2.2, 1.5), M.marble({ color: '#4a3a38', gold: false, scale: 0.9, roughness: 0.8 }));
  body.position.y = 1.1; furnace.add(body);
  const mouth = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 0.85), new THREE.MeshBasicMaterial({ color: hdr('#ff6a1a', 2.6) }));
  mouth.position.set(0, 0.95, 0.76); furnace.add(mouth);
  const arch = new THREE.Mesh(new THREE.TorusGeometry(0.7, 0.07, 8, 24, Math.PI), steel); arch.position.set(0, 1.35, 0.77); furnace.add(arch);
  const chimney = new THREE.Mesh(new THREE.BoxGeometry(0.7, 1.6, 0.7), steel); chimney.position.set(0.4, 3.0, -0.2); furnace.add(chimney);
  const fGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: hdr('#ff7a30', 2.4), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
  fGlow.scale.set(3.4, 2.6, 1); fGlow.position.set(0, 1.0, 1.1); furnace.add(fGlow);

  // ---- the quench barrel (right-back)
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.6, 1.0, 20), M.metal({ kind: 'gunmetal', color: '#2c3548', roughness: 0.5 }));
  barrel.position.set(3.3, 0.5, -1.4); scene.add(barrel);
  const water = new THREE.Mesh(new THREE.CircleGeometry(0.5, 24), new THREE.MeshBasicMaterial({ color: hdr('#4aa8ff', 1.1) }));
  water.rotation.x = -Math.PI / 2; water.position.set(3.3, 0.96, -1.4); scene.add(water);

  // ---- sparks (a strike) and drifting embers
  const SPARKS = 140, EMBERS = 70;
  const mkPoints = (n, size, color) => {
    const pos = new Float32Array(n * 3), vel = new Float32Array(n * 3), g = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const pts = new THREE.Points(g, new THREE.PointsMaterial({ map: glow, color: hdr(color, 1.8), size, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0, sizeAttenuation: true }));
    pts.frustumCulled = false; scene.add(pts); return { pts, pos, vel, n };
  };
  const sparks = mkPoints(SPARKS, 0.16, '#ffd27a'), embers = mkPoints(EMBERS, 0.1, '#ff8a3a');
  sparks.t = -1; sparks.show = SPARKS; embers.show = EMBERS;
  const resetEmber = (i, spread) => {
    embers.pos[i * 3] = -3.4 + (Math.random() - 0.5) * 1.6; embers.pos[i * 3 + 1] = spread ? Math.random() * 4 : 0.8 + Math.random() * 0.6; embers.pos[i * 3 + 2] = -2.2 + (Math.random() - 0.5) * 1.2;
    embers.vel[i * 3] = (Math.random() - 0.3) * 0.25; embers.vel[i * 3 + 1] = 0.3 + Math.random() * 0.6; embers.vel[i * 3 + 2] = (Math.random() - 0.5) * 0.2;
  };
  for (let i = 0; i < EMBERS; i++) resetEmber(i, true);
  embers.pts.material.opacity = 0.85;
  function setCounts() { embers.show = lite ? 24 : EMBERS; sparks.show = lite ? 60 : SPARKS; embers.pts.geometry.setDrawRange(0, embers.show); sparks.pts.geometry.setDrawRange(0, sparks.show); }
  setCounts();

  // ---- state
  const st = { color: new THREE.Color('#ffb547'), target: new THREE.Color('#ffb547'), scale: 1, tScale: 1, kind: 'live', strikeT: -1, flash: 0, hitDone: false };
  function setState({ color, scale, kind }) {
    if (color) st.target.set(color);
    if (typeof scale === 'number' && isFinite(scale)) st.tScale = Math.max(0.5, Math.min(1.55, scale));
    if (kind) st.kind = kind;
    if (reduced()) { st.color.copy(st.target); st.scale = st.tScale; }
    dirty = true;
  }
  function burst() {
    const { pos, vel } = sparks;
    for (let i = 0; i < SPARKS; i++) {
      const a = Math.random() * Math.PI * 2, up = 1.2 + Math.random() * 3.2, s = 0.8 + Math.random() * 2.6;
      pos[i * 3] = (Math.random() - 0.5) * 0.7; pos[i * 3 + 1] = 1.85; pos[i * 3 + 2] = (Math.random() - 0.5) * 0.3;
      vel[i * 3] = Math.cos(a) * s; vel[i * 3 + 1] = up; vel[i * 3 + 2] = Math.sin(a) * s * 0.6;
    }
    sparks.pts.geometry.attributes.position.needsUpdate = true; sparks.t = 0; sparks.pts.material.opacity = 1;
  }
  function strike() {
    strikes++;
    if (reduced()) { st.flash = 1; dirty = true; return; }
    st.strikeT = 0; st.hitDone = false; dirty = true;
  }

  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (stopped) return;
    const live = !reduced(), t = now / 1000;
    const a = canvas.clientWidth / Math.max(1, canvas.clientHeight);
    camera.fov = a < 0.75 ? 56 : a < 1.2 ? 48 : 40; camera.updateProjectionMatrix();
    const dt = Math.min(0.12, Math.max(0.001, (now - lastT) / 1000)); lastT = now;
    const settling = (Math.pow(st.color.r - st.target.r, 2) + Math.pow(st.color.g - st.target.g, 2) + Math.pow(st.color.b - st.target.b, 2)) > 1e-5 || Math.abs(st.scale - st.tScale) > 0.002;
    const busy = st.strikeT >= 0 || sparks.t >= 0 || st.flash > 0.01;
    if (!live && !dirty && !settling && !busy) return;
    const k = live ? 0.12 : 1;
    st.color.lerp(st.target, k); st.scale += (st.tScale - st.scale) * k;
    // the hammer
    if (st.strikeT >= 0) {
      st.strikeT += dt;
      const u = st.strikeT / 0.42;
      const ang = u < 0.3 ? REST + (HIT - REST) * Math.pow(u / 0.3, 2) : HIT + (REST - HIT) * Math.min(1, (u - 0.3) / 0.7);
      hammer.rotation.z = ang;
      if (!st.hitDone && u >= 0.3) { st.hitDone = true; burst(); st.flash = 1; }
      if (u >= 1) { st.strikeT = -1; hammer.rotation.z = REST; }
    }
    st.flash *= 0.9;
    // the ingot
    const heat = 0.95 + st.flash * 1.6 + (live ? Math.sin(t * 2.2) * 0.1 : 0);
    iMat.color.copy(st.color); iMat.emissive.copy(st.color); iMat.emissiveIntensity = heat;
    ingotG.scale.set(st.scale, 1 + (st.scale - 1) * 0.6, 1 + (st.scale - 1) * 0.6);
    halo.material.color.copy(st.color).multiplyScalar(0.55 + st.flash * 0.9);
    halo.scale.set(1.8 + st.scale * 0.8, 1.0 + st.scale * 0.4, 1);
    ingotLight.color.copy(st.color); ingotLight.intensity = 3 + st.flash * 8;
    ghost.material.opacity = 0.45 + (live ? Math.sin(t * 1.6) * 0.1 : 0);
    // fire + embers + sparks
    fire.intensity = 24 + (live ? Math.sin(t * 9) * 4 + Math.sin(t * 13.7) * 3 : 0);
    fGlow.scale.set(3.2 + (live ? Math.sin(t * 7) * 0.25 : 0), 2.5 + (live ? Math.sin(t * 9) * 0.3 : 0), 1);
    if (live) {
      const arr = embers.pts.geometry.attributes.position.array;
      for (let i = 0; i < embers.show; i++) {
        arr[i * 3] += embers.vel[i * 3] * dt; arr[i * 3 + 1] += embers.vel[i * 3 + 1] * dt; arr[i * 3 + 2] += embers.vel[i * 3 + 2] * dt;
        if (arr[i * 3 + 1] > 4.4) resetEmber(i, false);
      }
      embers.pts.geometry.attributes.position.needsUpdate = true;
    }
    if (sparks.t >= 0) {
      sparks.t += dt;
      const arr = sparks.pts.geometry.attributes.position.array;
      for (let i = 0; i < sparks.show; i++) {
        arr[i * 3] += sparks.vel[i * 3] * dt; arr[i * 3 + 1] += sparks.vel[i * 3 + 1] * dt; arr[i * 3 + 2] += sparks.vel[i * 3 + 2] * dt;
        sparks.vel[i * 3 + 1] -= 7.5 * dt; if (arr[i * 3 + 1] < 0.05) { arr[i * 3 + 1] = 0.05; sparks.vel[i * 3 + 1] *= -0.25; sparks.vel[i * 3] *= 0.5; sparks.vel[i * 3 + 2] *= 0.5; }
      }
      sparks.pts.geometry.attributes.position.needsUpdate = true; sparks.pts.material.opacity = Math.max(0, 1 - sparks.t / 1.1);
      if (sparks.t > 1.15) { sparks.t = -1; sparks.pts.material.opacity = 0; }
    }
    // the camera: the anvil sits in the upper part of a portrait screen (the sheet covers the lower half)
    const sway = live ? Math.sin(t * 0.25) * 0.35 : 0;
    camera.position.set(0.5 + sway, 3.4, 10.6); camera.lookAt(0.2, -2.0, 0);
    if (rc.render()) drawn++;
    frames++; dirty = false;
  }
  hammer.rotation.z = REST;
  raf = requestAnimationFrame(frame);
  return {
    setState, strike, onQuality(cb) { qcb = typeof cb === 'function' ? cb : null; },
    lite: () => lite, quality: () => rc.quality(),
    stats: () => ({ frames, drawn, quality: rc.quality(), passes: rc.passes().length, strikes, kind: st.kind, scale: Math.round(st.tScale * 100) / 100, color: '#' + st.target.getHexString(),
      sparksLive: sparks.t >= 0 }),
    dispose() { stopped = true; cancelAnimationFrame(raf); rc.dispose(); },
  };
}
