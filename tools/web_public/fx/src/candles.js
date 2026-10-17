// 3D candles for the Chart and Replay pages: glossy candles on a neon floor, liquidity pools as translucent glowing
// planes with "resting order" sparkles, killzones as soft volumes, a particle stream flowing along the price path,
// HTML price tags. Replay API: setCount(n) reveals the first n bars, event(kind, i, price) fires a particle burst.
// setData({ bars:[[t,o,h,l,c]], pools:[{price, side, label, strength}], price, marks:[{p, color, label}], follow, killzones:[[i0,i1]] })
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { THREE, View, Q, theme, par, glow, neon, POINT_FRAG, rng, count, toScreen } from './core.js';

const DX = 0.12;
const GRID_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const GRID_F = `uniform vec3 uC; uniform vec3 uT; varying vec3 vW;
void main(){ vec2 c = vW.xz * 1.6; vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c); float l = 1.0 - min(min(g.x, g.y), 1.0);
  float d = length(vW.xz - uT.xz); float fade = exp(-d * 0.12);
  gl_FragColor = vec4(uC * (l * 0.55 + 0.04) * fade, 1.0); }`;
const DUST_V = `attribute float aS; attribute float aSeed; uniform float uTime; uniform float uPix; varying vec3 vColor; varying float vAlpha; attribute vec3 aCol;
void main(){ vec3 p = position; p.y += sin(uTime * 1.3 + aSeed * 30.0) * 0.03; vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float tw = 0.5 + 0.5 * sin(uTime * (1.5 + aSeed * 3.0) + aSeed * 50.0); gl_PointSize = clamp(aS * uPix * (0.4 + tw) / -mv.z, 0.0, 22.0);
  gl_Position = projectionMatrix * mv; vColor = aCol; vAlpha = 0.35 + 0.65 * tw; }`;
const FLOW_V = `attribute float aS; varying vec3 vColor; varying float vAlpha; uniform float uPix; uniform vec3 uCol;
void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(aS * uPix / -mv.z, 0.0, 22.0); gl_Position = projectionMatrix * mv; vColor = uCol; vAlpha = 0.85; }`;
const BURST_V = `attribute vec3 aDir; attribute float aS; attribute float aSeed; uniform float uAge; uniform vec3 uO; uniform float uPix; uniform vec3 uCol;
varying vec3 vColor; varying float vAlpha;
void main(){ float a = uAge; vec3 p = uO + aDir * a * 1.9 * (1.0 - min(a, 1.4) * 0.3) + vec3(0.0, -0.6 * a * a, 0.0);
  vec4 mv = modelViewMatrix * vec4(p, 1.0); float life = clamp(1.0 - a / (0.8 + aSeed * 0.8), 0.0, 1.0);
  gl_PointSize = clamp(aS * uPix * (0.3 + life) / -mv.z, 0.0, 36.0); gl_Position = projectionMatrix * mv;
  vColor = mix(vec3(1.0), uCol, clamp(a * 2.0, 0.0, 1.0)) * 1.3; vAlpha = life * life; }`;

export class Candles extends View {
  constructor(opts = {}) {
    super({ fov: 34, dprMax: 2, ...opts, orbit: { yaw: -0.42, pitch: 0.16, auto: 0, min: -1.0, max: 1.0, pitchMin: 0.02, pitchMax: 0.85 } });
    this.u = { uTime: { value: 0 }, uPix: { value: 300 } };
    this.scene.background = new THREE.Color(theme.page).lerp(new THREE.Color('#12052a'), 0.35);
    this.scene.fog = new THREE.Fog(this.scene.background, 14, 34);
    const env = this.scene;
    const l1 = new THREE.PointLight(0xff4fd8, 6, 14, 1.6); l1.position.set(2, 5, 4); env.add(l1);
    const l2 = new THREE.PointLight(0x5be7ff, 4, 14, 1.6); l2.position.set(-6, 3, 4); env.add(l2);
    env.add(new THREE.AmbientLight(0x6a4cff, 0.6));
    this.unitBody = new RoundedBoxGeometry(1, 1, 1, 2, 0.1); this.unitBox = new THREE.BoxGeometry(1, 1, 1);
    this.mUp = new THREE.MeshStandardMaterial({ color: new THREE.Color('#2ee5c8'), emissive: new THREE.Color('#14a58f'), emissiveIntensity: 0.55, roughness: 0.25, metalness: 0.35 });
    this.mDn = new THREE.MeshStandardMaterial({ color: new THREE.Color('#ff4fd8'), emissive: new THREE.Color('#b8159f'), emissiveIntensity: 0.5, roughness: 0.25, metalness: 0.35 });
    this.mWick = new THREE.MeshBasicMaterial({ color: 0xffffff });
    this.gU = { uC: { value: new THREE.Color('#7c3aed') }, uT: { value: new THREE.Vector3() } };
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 40), new THREE.ShaderMaterial({ uniforms: this.gU, vertexShader: GRID_V, fragmentShader: GRID_F, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, extensions: { derivatives: true } }));
    this.floor.rotation.x = -Math.PI / 2; this.floor.position.y = -0.25; env.add(this.floor);
    this.g = new THREE.Group(); env.add(this.g);
    this.target = new THREE.Vector3(); this.tgt = new THREE.Vector3(); this.dist = 9;
    this.labels = document.createElement('div'); this.labels.className = 'fx-labels';
    Object.assign(this.labels.style, { position: 'absolute', inset: '0', pointerEvents: 'none', overflow: 'hidden' });
    this.tags = []; this.n = 0; this.visibleN = 0; this.sig = '';
    // bursts: a small pool reused for sweep / entry / exit events
    const R = rng(3), BN = count(220, 120), aDir = new Float32Array(BN * 3), bS = new Float32Array(BN), bSeed = new Float32Array(BN);
    for (let i = 0; i < BN; i++) { const u = R() * 2 - 1, a = R() * Math.PI * 2, q = Math.sqrt(1 - u * u), sp = 0.3 + Math.pow(R(), 0.6); aDir.set([q * Math.cos(a) * sp, u * sp, q * Math.sin(a) * sp], i * 3); bS[i] = 1.4 + R() * 3; bSeed[i] = R(); }
    this.bursts = [];
    for (let k = 0; k < 3; k++) {
      const bg = new THREE.BufferGeometry(); bg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(BN * 3), 3));
      bg.setAttribute('aDir', new THREE.BufferAttribute(aDir, 3)); bg.setAttribute('aS', new THREE.BufferAttribute(bS, 1)); bg.setAttribute('aSeed', new THREE.BufferAttribute(bSeed, 1));
      bg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 50);
      const U = { uPix: this.u.uPix, uAge: { value: 99 }, uO: { value: new THREE.Vector3() }, uCol: { value: new THREE.Color() } };
      const pts = new THREE.Points(bg, new THREE.ShaderMaterial({ uniforms: U, vertexShader: BURST_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      pts.visible = false; env.add(pts);
      const fl = glow(new THREE.Color('#ffffff'), 1, 0); env.add(fl);
      this.bursts.push({ pts, U, fl, age: 99 });
    }
    // flow particles along the price path
    const FN = count(180, 80); this.flowS = new Float32Array(FN); this.flowPos = new Float32Array(FN * 3); const fS = new Float32Array(FN);
    for (let i = 0; i < FN; i++) { this.flowS[i] = R(); fS[i] = 1 + R() * 1.6; }
    const fg = new THREE.BufferGeometry(); fg.setAttribute('position', new THREE.BufferAttribute(this.flowPos, 3)); fg.setAttribute('aS', new THREE.BufferAttribute(fS, 1)); fg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 60);
    this.flowU = { uPix: this.u.uPix, uCol: { value: new THREE.Color('#e9c8ff') } };
    this.flow = new THREE.Points(fg, new THREE.ShaderMaterial({ uniforms: this.flowU, vertexShader: FLOW_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    env.add(this.flow);
    this.rand = R;
  }
  attach(el) { super.attach(el); if (getComputedStyle(el).position === 'static') el.style.position = 'relative'; el.appendChild(this.labels); }
  detach() { this.labels.remove(); super.detach(); }
  onResize(w, h) {
    this.u.uPix.value = h * this.renderer.getPixelRatio() / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))) * 0.02;
    if (this.n) this.setCount(this.visibleN || this.n, false);
  }
  X(i) { return (i - (this.n - 1)) * DX; }
  Y(p) { return (p - this.lo) / (this.hi - this.lo) * this.H; }

  setData(d = {}) {
    const bars = d.bars || [];
    const sig = bars.length + ':' + (bars[0]?.[0] || 0) + ':' + (bars.at(-1)?.[0] || 0) + ':' + (bars.at(-1)?.[4] || 0) + '|' + (d.pools || []).map(p => p.price).join(',') + '|' + (d.marks || []).map(m => m.p).join(',');
    this.follow = !!d.follow;
    if (sig === this.sig) return;
    this.sig = sig;
    for (const o of [...this.g.children]) { this.g.remove(o); o.dispose?.(); if (o.geometry && o.geometry !== this.unitBody && o.geometry !== this.unitBox) o.geometry.dispose(); if (o.material && ![this.mUp, this.mDn, this.mWick].includes(o.material)) o.material.dispose?.(); }
    this.tags.forEach(t => t.el.remove()); this.tags = [];
    this.n = bars.length; this.bars = bars;
    if (!bars.length) return;
    const pools = (d.pools || []);
    let lo = Math.min(...bars.map(b => b[3])), hi = Math.max(...bars.map(b => b[2]));
    for (const m of d.marks || []) { lo = Math.min(lo, m.p); hi = Math.max(hi, m.p); }
    // only the nearest two pools above and below price; ones far outside the bars' range get an edge tag only
    const px0 = d.price ?? bars.at(-1)[4], rg = hi - lo || 1;
    const nearest = [...pools.filter(p => p.price > px0).sort((a, b) => a.price - b.price).slice(0, 2), ...pools.filter(p => p.price < px0).sort((a, b) => b.price - a.price).slice(0, 2)];
    const near = nearest.filter(p => p.price > lo - rg * 0.12 && p.price < hi + rg * 0.12), far = nearest.filter(p => !near.includes(p));
    for (const p of near) { lo = Math.min(lo, p.price); hi = Math.max(hi, p.price); }
    const pad = (hi - lo) * 0.06 || 1; this.lo = lo - pad; this.hi = hi + pad;
    const n = bars.length, L = n * DX;
    // vertical scale: the bars in focus get about as tall as they are wide, so candles fill the view on a phone too
    this.focus = this._focusN(n);
    const fb = bars.slice(-this.focus), fr = Math.max(...fb.map(b => b[2])) - Math.min(...fb.map(b => b[3])) || rg;
    this.H = Math.max(4.6, Math.min(16, this.focus * DX * 0.95 * (this.hi - this.lo) / fr));
    // candles (instanced)
    const ups = [], dns = [];
    bars.forEach((b, i) => (b[4] >= b[1] ? ups : dns).push(i));
    this.mU = new THREE.InstancedMesh(this.unitBody, this.mUp, Math.max(1, ups.length)); this.mD = new THREE.InstancedMesh(this.unitBody, this.mDn, Math.max(1, dns.length));
    this.wk = new THREE.InstancedMesh(this.unitBox, this.mWick, n);
    this.order = { up: ups, dn: dns };
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3(), ps = new THREE.Vector3(), cUp = new THREE.Color('#9ffff0'), cDn = new THREE.Color('#ffc2f2');
    const bw = DX * 0.68;
    const put = (mesh, k, i) => { const [, o, , , c] = bars[i]; const yt = this.Y(Math.max(o, c)), yb = this.Y(Math.min(o, c)); ps.set(this.X(i), (yt + yb) / 2, 0); sc.set(bw, Math.max(0.025, yt - yb), bw); M.compose(ps, q, sc); mesh.setMatrixAt(k, M); };
    ups.forEach((i, k) => put(this.mU, k, i)); dns.forEach((i, k) => put(this.mD, k, i));
    bars.forEach((b, i) => { ps.set(this.X(i), (this.Y(b[2]) + this.Y(b[3])) / 2, 0); sc.set(0.018, Math.max(0.02, this.Y(b[2]) - this.Y(b[3])), 0.018); M.compose(ps, q, sc); this.wk.setMatrixAt(i, M); this.wk.setColorAt(i, b[4] >= b[1] ? cUp : cDn); });
    for (const m of [this.mU, this.mD, this.wk]) { m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true; m.frustumCulled = false; this.g.add(m); }
    if (!ups.length) this.mU.count = 0; if (!dns.length) this.mD.count = 0;
    // killzones (ET 09:30-11:30, 13:30-15:30) as soft volumes
    const kz = d.killzones || this._killzones(bars);
    for (const [a, b] of kz) {
      const w = (b - a + 1) * DX, cx = (this.X(a) + this.X(b)) / 2;
      const strip = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: new THREE.Color('#8b5cf6').multiplyScalar(0.06), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
      strip.rotation.x = -Math.PI / 2; strip.position.set(cx, -0.24, 0); strip.scale.set(w, 2.2, 1); this.g.add(strip);

    }
    // liquidity pools: translucent planes + bright front edge + resting-order sparkles + price tag
    const dust = [], dS = [], dSeed = [], dC = [];
    for (const p of near) {
      const y = this.Y(p.price), col = p.side === 'H' ? new THREE.Color('#ff9b5c') : new THREE.Color('#6d9bff'), strong = (p.strength || 1) >= 2;
      const plane = new THREE.Mesh(new THREE.PlaneGeometry(L + 1.2, 1.6), new THREE.MeshBasicMaterial({ color: col.clone().multiplyScalar(strong ? 0.085 : 0.055), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
      plane.rotation.x = -Math.PI / 2; plane.position.set(-L / 2 + DX / 2 + 0.3, y, 0); this.g.add(plane);
      const edge = new THREE.Mesh(this.unitBox, neon(col, strong ? 1.5 : 1.1, 0.95)); edge.position.set(-L / 2 + DX / 2 + 0.3, y, 0.8); edge.scale.set(L + 1.2, 0.018, 0.018); this.g.add(edge);
      for (let k = 0; k < Math.round(count(28, 12) * (strong ? 1.4 : 1)); k++) { dust.push(this.X(Math.floor(this.rand() * n)) + (this.rand() - 0.5) * 0.3, y + 0.02 + this.rand() * 0.05, (this.rand() - 0.5) * 1.5); dS.push(0.8 + this.rand() * 1.6); dSeed.push(this.rand()); dC.push(col.r, col.g, col.b); }
      this._tag(new THREE.Vector3(0.45, y, 0.8), `${p.side === 'H' ? 'BSL' : 'SSL'} ${p.label || ''} ${p.price.toLocaleString('en-US', { maximumFractionDigits: 2 })}`, '#' + col.getHexString());
    }
    for (const p of far) {
      const above = p.price > this.hi, col = p.side === 'H' ? '#ff9b5c' : '#6d9bff';
      this._tag(new THREE.Vector3(0.45, above ? this.H + 0.15 : -0.1, 0.8), `${above ? '↑' : '↓'} ${p.side === 'H' ? 'BSL' : 'SSL'} ${p.label || ''} ${p.price.toLocaleString('en-US', { maximumFractionDigits: 2 })}`, col);
    }
    if (dust.length) {
      const dg = new THREE.BufferGeometry(); dg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(dust), 3)); dg.setAttribute('aS', new THREE.BufferAttribute(new Float32Array(dS), 1));
      dg.setAttribute('aSeed', new THREE.BufferAttribute(new Float32Array(dSeed), 1)); dg.setAttribute('aCol', new THREE.BufferAttribute(new Float32Array(dC), 3)); dg.computeBoundingSphere();
      this.g.add(new THREE.Points(dg, new THREE.ShaderMaterial({ uniforms: this.u, vertexShader: DUST_V, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));
    }
    // marks (replay: entry / stop / target / sweep)
    for (const m of d.marks || []) {
      const y = this.Y(m.p), col = new THREE.Color(m.color);
      const from = m.i != null ? this.X(m.i) : this.X(0), len = this.X(n - 1) - from + 0.6;
      const bar = new THREE.Mesh(this.unitBox, neon(col, 1.4, 0.95)); bar.position.set(from + len / 2, y, 0.35); bar.scale.set(len, 0.03, 0.03); bar.visible = false; bar.userData.mark = m; this.g.add(bar);
      m._mesh = bar; m._tag = this._tag(new THREE.Vector3(0.75, y, 0.35), m.label, '#' + col.getHexString(), true);
    }
    this.marks = d.marks || [];
    // price line
    const px = d.price ?? bars.at(-1)[4];
    if (d.price != null) {
      const y = this.Y(px), pl = new THREE.Mesh(this.unitBox, neon('#c9b8ff', 1.3, 0.9)); pl.position.set(-L / 2 + 0.3, y, 0); pl.scale.set(L + 1.2, 0.022, 0.022); this.g.add(pl);
      this._tag(new THREE.Vector3(0.45, y, 0), px.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }), '#c9b8ff');
    }
    this.path = bars.map((b, i) => new THREE.Vector3(this.X(i), this.Y(b[4]), 0));
    this.setCount(d.count ?? n, true);
  }
  _killzones(bars) {
    const out = []; let a = null;
    const et = (t) => { const s = new Date(t * 1000).toLocaleString('en-US', { timeZone: 'America/New_York', hour12: false, hour: '2-digit', minute: '2-digit' }); const [h, m] = s.split(':').map(Number); return (h % 24) * 60 + m; };
    bars.forEach((b, i) => { const m = et(b[0]), k = (m >= 570 && m < 690) || (m >= 810 && m < 930); if (k && a == null) a = i; if (!k && a != null) { out.push([a, i - 1]); a = null; } });
    if (a != null) out.push([a, bars.length - 1]);
    return out;
  }
  _tag(pos, text, color, hidden = false) {
    const el = document.createElement('div'); el.textContent = text;
    Object.assign(el.style, { position: 'absolute', left: '0', top: '0', transform: 'translate(-9999px,0)', font: '600 10px var(--mono, monospace)', color: '#07080c', background: color,
      padding: '2px 6px', borderRadius: '6px', whiteSpace: 'nowrap', boxShadow: `0 0 12px ${color}`, opacity: '0.92' });
    this.labels.appendChild(el);
    const t = { el, pos, hidden }; this.tags.push(t); return t;
  }
  // replay: reveal the first n bars
  setCount(nVis, instant = false) {
    if (!this.n) return;
    nVis = Math.max(1, Math.min(this.n, nVis)); this.visibleN = nVis;
    const cu = this.order.up.filter(i => i < nVis).length, cd = this.order.dn.filter(i => i < nVis).length;
    this.mU.count = cu; this.mD.count = cd; this.wk.count = nVis;
    for (const m of this.marks || []) { const on = m.from == null || nVis - 1 >= m.from; if (m._mesh) m._mesh.visible = on; if (m._tag) m._tag.hidden = !on; }
    // frame the bars in focus: centre on their price band and pull back just enough to fit it
    this.focus = this._focusN(this.n);
    const f0 = Math.max(0, nVis - this.focus), fb = this.bars.slice(f0, nVis);
    const yl = this.Y(Math.min(...fb.map(b => b[3]))), yh = this.Y(Math.max(...fb.map(b => b[2])));
    const tx = this.follow ? this.X(nVis - 1) - this.focus * DX * 0.32 : this.X(this.n - 1) - this.focus * DX / 2 + 0.35;
    this.tgt.set(tx, (yl + yh) / 2 - 0.05, 0);
    const asp = this.camera.aspect || 1.6, tf = Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2));
    const wb = this.focus * DX * 0.92 + 0.9, hb = (yh - yl) * 1.3 + 0.7;
    this.distT = Math.max(4.2, Math.min(17, Math.max(hb / (2 * tf), wb / (2 * tf * asp))));
    if (instant || !this.dist) { this.target.copy(this.tgt); this.dist = this.distT; }
  }
  // bars in focus: fewer on a narrow screen so they stay big; older ones recede into the fog
  _focusN(n) {
    const base = this.follow ? 46 : 64, asp = this.camera.aspect || 1.6;
    return Math.max(10, Math.min(n, Math.round(base * Math.min(1, Math.max(0.42, asp / 1.9)))));
  }
  event(kind, i, price) {
    const b = this.bursts.find(x => x.age > 1.6) || this.bursts[0];
    const col = { sweep: theme.bsl, entry: theme.accent, win: theme.good, loss: theme.bad, exit: theme.accent2 }[kind] || theme.accent2;
    b.age = 0; b.U.uO.value.set(this.X(i), this.Y(price), 0.1); b.U.uCol.value.copy(col); b.pts.visible = true;
    b.fl.position.copy(b.U.uO.value); b.fl.material.color.copy(col).lerp(new THREE.Color('#ffffff'), 0.4);
  }
  update(t, dt) {
    const o = this.orbit; o.idle += dt;
    if (!o.dragging) { o.yaw += o.vyaw; o.pitch += o.vpitch; o.vyaw *= 0.92; o.vpitch *= 0.92;
      if (o.idle > 3 && !Q.reduced) { o.yaw += (-0.42 + Math.sin(t * 0.22) * 0.16 - o.yaw) * Math.min(1, dt * 0.5); o.pitch += (0.16 - o.pitch) * Math.min(1, dt * 0.5); } }
    o.yaw = Math.max(o.min, Math.min(o.max, o.yaw)); o.pitch = Math.max(o.pitchMin, Math.min(o.pitchMax, o.pitch));
    this.u.uTime.value = t;
    this.target.lerp(this.tgt, Math.min(1, dt * 3));
    this.dist += ((this.distT || this.dist) - this.dist) * Math.min(1, dt * 2.5);
    const D = this.dist, cp = Math.cos(o.pitch);
    this.camera.position.set(this.target.x + Math.sin(o.yaw) * cp * D + par.x * 0.3, this.target.y + Math.sin(o.pitch) * D + 0.4 - par.y * 0.2, this.target.z + Math.cos(o.yaw) * cp * D);
    this.camera.lookAt(this.target);
    this.gU.uT.value.copy(this.target);
    // flow along the visible price path
    const path = this.path, nv = this.visibleN;
    if (path && nv > 1) {
      const fp = this.flowPos;
      for (let k = 0; k < this.flowS.length; k++) {
        let s = this.flowS[k] + dt * 0.06; if (s > 1) s -= 1; this.flowS[k] = s;
        const f = s * (nv - 1), i = Math.floor(f), w = f - i, a = path[i], b = path[Math.min(nv - 1, i + 1)];
        fp[k * 3] = a.x + (b.x - a.x) * w; fp[k * 3 + 1] = a.y + (b.y - a.y) * w + Math.sin(t * 2 + k) * 0.03; fp[k * 3 + 2] = Math.cos(t * 1.3 + k * 1.7) * 0.08;
      }
      this.flow.geometry.attributes.position.needsUpdate = true; this.flow.visible = true;
    } else this.flow.visible = false;
    for (const b of this.bursts) {
      b.age += dt; b.U.uAge.value = b.age; if (b.age > 2) b.pts.visible = false;
      const k = Math.max(0, 1 - b.age / 0.7); b.fl.material.opacity = k; const s = 0.4 + (1 - k) * 2.2; b.fl.scale.set(s, s, 1);
    }
    // HTML tags follow their 3D anchors, nudged apart so they never overlap
    const shown = [];
    for (const tg of this.tags) {
      if (tg.hidden) { tg.el.style.transform = 'translate(-9999px,0)'; continue; }
      const p = toScreen(this, tg.pos); if (p.behind) { tg.el.style.transform = 'translate(-9999px,0)'; continue; }
      tg.w = tg.w || tg.el.offsetWidth || 90; shown.push({ tg, x: Math.min(this.w - tg.w - 4, Math.max(4, p.x)), y: p.y - 9 });
    }
    shown.sort((a, b) => a.y - b.y);
    for (let i = 1; i < shown.length; i++) if (shown[i].y - shown[i - 1].y < 18) shown[i].y = shown[i - 1].y + 18;
    for (const s of shown) s.tg.el.style.transform = `translate(${s.x}px, ${Math.max(2, Math.min(this.h - 18, s.y))}px)`;
  }
  dispose() { this.tags.forEach(t => t.el.remove()); this.labels.remove(); this.unitBody.dispose(); this.unitBox.dispose(); super.dispose(); }
}
