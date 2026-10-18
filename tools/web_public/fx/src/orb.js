// The Live Oracle: the app icon, alive. A glass orb on a chrome-and-neon pedestal holds the latest real 5-minute bars as
// glossy 3D candles; the nearest liquidity pools are glowing discs slicing through the orb, the price is a ring of light.
// Particles orbit the orb and rise from the pedestal. Drag sideways to turn the candles; it sways by itself when idle.
// setData({ bars:[[t,o,h,l,c]...], pools:[{price, side:'H'|'L'}], price, mood:{ live, killzone, inTrade, side } })
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { THREE, View, Q, theme, par, glow, glowTexture, neon, rimMaterial, POINT_FRAG, rng, count } from './core.js';

const R = 1.5, OY = 0.35;
const RING_V = `attribute float aS; attribute float aSeed; attribute vec3 aCol; uniform float uTime; uniform float uPix; uniform float uBright;
varying vec3 vColor; varying float vAlpha;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); float tw = 0.7 + 0.3 * sin(uTime * (1.0 + aSeed * 3.0) + aSeed * 30.0);
  gl_PointSize = clamp(aS * uPix * tw / -mv.z, 0.0, 30.0); gl_Position = projectionMatrix * mv; vColor = aCol * uBright; vAlpha = tw; }`;
const MOTE_V = `attribute vec3 aP; attribute float aS; attribute float aSeed; uniform float uTime; uniform float uPix; uniform vec3 uCol;
varying vec3 vColor; varying float vAlpha;
void main(){ vec3 p = aP; float h = mod(aP.y + uTime * (0.18 + aSeed * 0.25), 3.4); p.y = h - 1.3;
  float a = uTime * 0.2 + aSeed * 6.28; p.x = aP.x * cos(a * 0.3) - aP.z * sin(a * 0.3); p.z = aP.x * sin(a * 0.3) + aP.z * cos(a * 0.3);
  vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_PointSize = clamp(aS * uPix / -mv.z, 0.0, 24.0); gl_Position = projectionMatrix * mv;
  vColor = uCol; vAlpha = smoothstep(0.0, 0.5, h) * (1.0 - smoothstep(2.4, 3.4, h)); }`;

function envMap(renderer) {
  const s = new THREE.Scene(); s.background = new THREE.Color(0x030208);
  const panel = (c, k, w, h, p, r) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(k), side: THREE.DoubleSide })); m.position.set(...p); m.rotation.set(...r); s.add(m); };
  panel('#8b5cf6', 4, 10, 2, [0, 6, -2], [Math.PI / 2, 0, 0]); panel('#ff2bd6', 5, 1.2, 8, [-6, 1, 0], [0, Math.PI / 2, 0]);
  panel('#22d3ee', 3.5, 1, 8, [6, 1, 1], [0, -Math.PI / 2, 0]); panel('#ffffff', 2.4, 4, 0.6, [0, 3, 6], [0, Math.PI, 0]);
  const pm = new THREE.PMREMGenerator(renderer), t = pm.fromScene(s, 0.03).texture; pm.dispose();
  s.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
  return t;
}
function bgTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 512; const g = c.getContext('2d');
  const gr = g.createRadialGradient(256, 210, 0, 256, 220, 380);
  gr.addColorStop(0, '#2c0a52'); gr.addColorStop(0.45, '#0e0420'); gr.addColorStop(1, '#030107');
  g.fillStyle = gr; g.fillRect(0, 0, 512, 512);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export class Orb extends View {
  constructor(opts = {}) {
    super({ fov: 30, dprMax: 2, ...opts, orbit: { yaw: 0, pitch: 0, auto: 0, min: -1.3, max: 1.3 } });
    const S = this.scene, rnd = rng(5);
    S.background = bgTexture();
    S.environment = envMap(this.renderer);
    this.camera.position.set(0, 0.5, 8.6);
    this.u = { uTime: { value: 0 }, uPix: { value: 300 }, uBright: { value: 1 } };
    this.mood = { live: false, killzone: false, inTrade: false, side: 0 };
    this.sig = '';

    // stars
    const SN = count(260, 140), sp = new Float32Array(SN * 3), sS = new Float32Array(SN), sSeed = new Float32Array(SN), sC = new Float32Array(SN * 3);
    for (let i = 0; i < SN; i++) { sp.set([(rnd() - 0.5) * 30, (rnd() - 0.5) * 18 + 2, -10 - rnd() * 12], i * 3); sS[i] = 0.8 + rnd() * 1.8; sSeed[i] = rnd(); sC.set([0.75, 0.7, 1], i * 3); }
    S.add(this._points(sp, sS, sSeed, sC, RING_V));

    // pedestal
    const chrome = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 1, roughness: 0.14, envMapIntensity: 1.2 });
    const py = OY - R * 0.93;
    const ped = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 1.12, 0.36, 72), chrome); ped.position.y = py - 0.18; S.add(ped);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(1.32, 1.42, 0.13, 72), new THREE.MeshStandardMaterial({ color: 0x120820, metalness: 0.9, roughness: 0.25 }));
    base.position.y = py - 0.43; S.add(base);
    this.band1 = new THREE.Mesh(new THREE.TorusGeometry(1.04, 0.035, 12, 120), neon(theme.violet, 1.5)); this.band1.rotation.x = Math.PI / 2; this.band1.position.y = py - 0.1; S.add(this.band1);
    this.band2 = new THREE.Mesh(new THREE.TorusGeometry(1.4, 0.03, 12, 140), neon(theme.magenta, 1.4)); this.band2.rotation.x = Math.PI / 2; this.band2.position.y = py - 0.38; S.add(this.band2);
    const pool = glow(new THREE.Color('#9d5cff'), 5.5, 0.35); pool.position.set(0, py - 0.5, -0.2); pool.scale.set(6.5, 1.6, 1); S.add(pool);

    // the orb: glass + fresnel rim + highlights + inner glow
    this.glass = new THREE.Mesh(new THREE.SphereGeometry(R, 72, 54), new THREE.MeshPhysicalMaterial({ color: 0xcdb8ff, roughness: 0, metalness: 0, transparent: true, opacity: 0.09,
      clearcoat: 1, clearcoatRoughness: 0, iridescence: 1, iridescenceIOR: 1.45, iridescenceThicknessRange: [300, 800], envMapIntensity: 0.55, specularIntensity: 0.35, depthWrite: false }));
    this.glass.position.y = OY; this.glass.renderOrder = 5; S.add(this.glass);
    this.rim = new THREE.Mesh(new THREE.SphereGeometry(R * 1.003, 72, 54), rimMaterial(theme.violet, theme.magenta, 3.2, 1.45)); this.rim.position.y = OY; this.rim.renderOrder = 6; S.add(this.rim);
    const hl = new THREE.Mesh(new THREE.TorusGeometry(R * 0.9, 0.03, 8, 64, 0.95), neon(0xffffff, 1.2, 0.5)); hl.position.set(0, OY, R * 0.42); hl.rotation.z = 1.75; S.add(hl);
    const hl2 = new THREE.Mesh(new THREE.TorusGeometry(R * 0.92, 0.018, 8, 64, 0.6), neon(0xe9b8ff, 1, 0.32)); hl2.position.set(0, OY, R * 0.4); hl2.rotation.z = -0.95; S.add(hl2);
    this.inner = glow(new THREE.Color('#7c3aed'), 3.4, 0.22); this.inner.position.set(0, OY, -0.3); S.add(this.inner);

    // candles + levels live in a group that sways / follows the drag
    this.g = new THREE.Group(); this.g.position.y = OY; S.add(this.g);
    this.unitBody = new RoundedBoxGeometry(1, 1, 1, 2, 0.12);
    this.unitWick = new THREE.BoxGeometry(1, 1, 1);
    this.mUp = new THREE.MeshStandardMaterial({ color: new THREE.Color('#2ee5c8'), emissive: new THREE.Color('#1fbfa6'), emissiveIntensity: 0.55, roughness: 0.18, metalness: 0.3, envMapIntensity: 1.3 });
    this.mDn = new THREE.MeshStandardMaterial({ color: new THREE.Color('#ff4fd8'), emissive: new THREE.Color('#d21fb8'), emissiveIntensity: 0.5, roughness: 0.18, metalness: 0.3, envMapIntensity: 1.3 });
    this.mWick = new THREE.MeshBasicMaterial({ color: 0xffffff });
    this.lastGlow = glow(new THREE.Color('#ffffff'), 0.6, 0.9); this.g.add(this.lastGlow);

    // orbiting particle ring
    const ON = count(Q.phone ? 760 : 1100, 380), op = new Float32Array(ON * 3), oS = new Float32Array(ON), oSeed = new Float32Array(ON), oC = new Float32Array(ON * 3);
    const cols = [new THREE.Color('#b47cff'), new THREE.Color('#ff4fd8'), new THREE.Color('#5be7ff'), new THREE.Color('#ffffff')];
    for (let i = 0; i < ON; i++) {
      const a = rnd() * Math.PI * 2, rr = 1.95 + Math.pow(rnd(), 1.5) * 0.55 * (rnd() < 0.5 ? 1 : -0.4);
      op.set([Math.cos(a) * rr, (rnd() - 0.5) * 0.12, Math.sin(a) * rr], i * 3); oS[i] = 0.9 + rnd() * 2.2; oSeed[i] = rnd();
      const c = cols[rnd() < 0.08 ? 3 : rnd() < 0.15 ? 2 : rnd() < 0.55 ? 0 : 1]; oC.set([c.r, c.g, c.b], i * 3);
    }
    this.ringG = new THREE.Group(); this.ringG.position.y = OY; this.ringG.rotation.set(1.28, 0, 0.22);
    this.ringSpin = new THREE.Group(); this.ringG.add(this.ringSpin); this.ringSpin.add(this._points(op, oS, oSeed, oC, RING_V)); S.add(this.ringG);

    // rising motes
    const MN = count(150, 70), mp = new Float32Array(MN * 3), mS = new Float32Array(MN), mSeed = new Float32Array(MN);
    for (let i = 0; i < MN; i++) { const a = rnd() * Math.PI * 2, rr = 0.25 + rnd() * 1.05; mp.set([Math.cos(a) * rr, rnd() * 3.4, Math.sin(a) * rr], i * 3); mS[i] = 0.9 + rnd() * 1.6; mSeed[i] = rnd(); }
    const mg = new THREE.BufferGeometry(); mg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(MN * 3), 3));
    mg.setAttribute('aP', new THREE.BufferAttribute(mp, 3)); mg.setAttribute('aS', new THREE.BufferAttribute(mS, 1)); mg.setAttribute('aSeed', new THREE.BufferAttribute(mSeed, 1));
    mg.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0.5, 0), 4);
    this.mU = { ...this.u, uCol: { value: new THREE.Color('#e9c8ff') } };
    const motes = new THREE.Points(mg, new THREE.ShaderMaterial({ uniforms: this.mU, vertexShader: MOTE_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    motes.position.y = OY; S.add(motes);

    // lights
    const l1 = new THREE.PointLight(0xff4fd8, 5, 7, 2); l1.position.set(2.5, 1.2, 2.4); S.add(l1);
    const l2 = new THREE.PointLight(0x22d3ee, 3.5, 7, 2); l2.position.set(-2.5, 0, 2.2); S.add(l2);
    const l3 = new THREE.PointLight(0xffffff, 2.2, 8, 2); l3.position.set(0.5, 3, 3); S.add(l3);
  }
  _points(pos, size, seed, col, vs) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aS', new THREE.BufferAttribute(size, 1));
    g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1)); g.setAttribute('aCol', new THREE.BufferAttribute(col, 3));
    g.computeBoundingSphere();
    return new THREE.Points(g, new THREE.ShaderMaterial({ uniforms: this.u, vertexShader: vs, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  }
  onResize(w, h) { this.u.uPix.value = h * this.renderer.getPixelRatio() / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))) * 0.02; }

  setData(d = {}) {
    this.mood = { ...this.mood, ...(d.mood || {}) };
    const bars = (d.bars || []).slice(-12), pools = d.pools || [];
    const sig = bars.map(b => b[0] + ':' + b[4]).join(',') + '|' + pools.map(p => p.price).join(',') + '|' + d.price;
    if (sig === this.sig) return;
    this.sig = sig;
    for (const o of [...this.g.children]) if (o !== this.lastGlow) { this.g.remove(o); o.dispose?.(); if (o.isMesh && o.geometry !== this.unitBody && o.geometry !== this.unitWick) o.geometry.dispose(); if (o.material && ![this.mUp, this.mDn, this.mWick].includes(o.material)) o.material.dispose(); }
    if (!bars.length) { this.lastGlow.visible = false; return; }
    let lo = Math.min(...bars.map(b => b[3])), hi = Math.max(...bars.map(b => b[2]));
    const span = hi - lo || 1; lo -= span * 0.06; hi += span * 0.06;
    const Y = (p) => -0.82 + (p - lo) / (hi - lo) * 1.64;
    const n = bars.length, x0 = -0.98, dx = n > 1 ? 1.96 / (n - 1) : 0, bw = Math.min(0.13, 1.5 / n);
    const up = bars.filter(b => b[4] >= b[1]).length, dn = n - up;
    const mU = new THREE.InstancedMesh(this.unitBody, this.mUp, Math.max(1, up)), mD = new THREE.InstancedMesh(this.unitBody, this.mDn, Math.max(1, dn));
    const wk = new THREE.InstancedMesh(this.unitWick, this.mWick, n);
    mU.count = up; mD.count = dn;
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3(), ps = new THREE.Vector3(), cUp = new THREE.Color('#9ffff0'), cDn = new THREE.Color('#ffc2f2');
    let iu = 0, id = 0;
    bars.forEach((b, i) => {
      const [, o, h, l, c] = b, x = x0 + i * dx, yt = Y(Math.max(o, c)), yb = Y(Math.min(o, c)), bull = c >= o;
      ps.set(x, (yt + yb) / 2, 0); sc.set(bw, Math.max(0.02, yt - yb), bw); M.compose(ps, q, sc);
      (bull ? mU : mD).setMatrixAt(bull ? iu++ : id++, M);
      ps.set(x, (Y(h) + Y(l)) / 2, 0); sc.set(0.016, Math.max(0.02, Y(h) - Y(l)), 0.016); M.compose(ps, q, sc); wk.setMatrixAt(i, M); wk.setColorAt(i, bull ? cUp : cDn);
    });
    for (const m of [mU, mD, wk]) { m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true; this.g.add(m); }
    const last = bars[n - 1];
    this.lastGlow.position.set(x0 + (n - 1) * dx, Y(last[4]), 0.06); this.lastGlow.visible = true;
    this.lastGlow.material.color.set(last[4] >= last[1] ? '#9ffff0' : '#ffc2f2');
    // the price ring: a band of light around the orb at the current price
    const pY = Y(d.price ?? last[4]), pr = Math.sqrt(Math.max(0.05, R * R - pY * pY));
    const ring = new THREE.Mesh(new THREE.TorusGeometry(pr, 0.012, 8, 120), neon('#ffffff', 1.1, 0.75)); ring.rotation.x = Math.PI / 2; ring.position.y = pY; this.g.add(ring);
    // liquidity pools: glowing discs slicing the orb + dashed edge, nearest two above and below price
    const px = d.price ?? last[4];
    const above = pools.filter(p => p.price > px).sort((a, b) => a.price - b.price).slice(0, 2);
    const below = pools.filter(p => p.price < px).sort((a, b) => b.price - a.price).slice(0, 2);
    for (const p of [...above, ...below]) {
      let y = Y(p.price); const clamped = Math.abs(y) > 1.18; y = Math.max(-1.18, Math.min(1.18, y));
      const rr = Math.sqrt(Math.max(0.05, R * R - y * y)) * 0.985, col = p.price > px ? new THREE.Color('#ff8a5c') : new THREE.Color('#5b9bff');
      const disc = new THREE.Mesh(new THREE.CircleGeometry(rr, 72), new THREE.MeshBasicMaterial({ color: col.clone().multiplyScalar(clamped ? 0.12 : 0.22), transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
      disc.rotation.x = -Math.PI / 2; disc.position.y = y; this.g.add(disc);
      const edge = new THREE.Mesh(new THREE.TorusGeometry(rr, 0.014, 6, 120), neon(col, clamped ? 0.7 : 1.3, 0.9)); edge.rotation.x = Math.PI / 2; edge.position.y = y; this.g.add(edge);
      const dashes = new THREE.InstancedMesh(this.unitWick, neon(col, 1.4), 16);
      for (let k = 0; k < 16; k++) { ps.set(-1.12 + k * 0.15, y, 0.02); sc.set(0.085, 0.014, 0.014); M.compose(ps, q, sc); dashes.setMatrixAt(k, M); }
      dashes.instanceMatrix.needsUpdate = true; this.g.add(dashes);
    }
  }
  update(t, dt) {
    const o = this.orbit; o.idle += dt;
    if (!o.dragging) {
      o.yaw += o.vyaw; o.vyaw *= 0.93;
      if (o.idle > 2.5 && !Q.reduced) o.yaw += (Math.sin(t * 0.32) * 0.5 - o.yaw) * Math.min(1, dt * 0.6);
    }
    o.yaw = Math.max(o.min, Math.min(o.max, o.yaw));
    this.g.rotation.y = o.yaw;
    const m = this.mood, hot = m.inTrade ? 1.6 : m.killzone ? 1.3 : 1;
    this.u.uTime.value = t; this.u.uBright.value = 0.85 + 0.25 * hot;
    this.ringSpin.rotation.y += dt * 0.22 * hot;
    this.band1.material.color.copy(theme.violet).multiplyScalar(1.3 + 0.35 * Math.sin(t * 1.4 * hot));
    this.band2.material.color.copy(theme.magenta).multiplyScalar(1.2 + 0.3 * Math.sin(t * 1.1 * hot + 1));
    const pulse = 0.75 + 0.25 * Math.sin(t * 3 * hot); this.lastGlow.material.opacity = 0.65 * pulse + 0.2; const s = 0.42 + 0.22 * pulse; this.lastGlow.scale.set(s, s, 1);
    this.inner.material.opacity = 0.18 + 0.06 * Math.sin(t * 0.8);
    this.camera.position.set(par.x * 0.35, 0.5 - par.y * 0.2, 8.6); this.camera.lookAt(0, 0.15, 0);
  }
  dispose() { this.unitBody.dispose(); this.unitWick.dispose(); this.scene.environment?.dispose(); this.scene.background?.dispose?.(); super.dispose(); }
}
