// Holodeck (owner 2026-10-29: "see exactly chart fills, very high quality and 3D, where I can see what every bot is thinking"):
// one day of NQ in 3D with every fill at its exact second and price, the trades as glass volumes, each LIT setup drawn as
// an annotated anatomy, the bots' thoughts as holographic panels, working orders, levels and market structure.
//   const v = FX.holo(el, { phone, lite, onPick(kind, id), onCam() });  v.setData(holoJson); v.setTime(T, { pop });
//   v.setLayers({ fills, trades, setup, thoughts, orders, levels, structure, volume, bots: { lit, atlas, blitz, sys } });
//   v.preset('flat' | '3d' | 'fly'); v.follow(true); v.focus('fill' | 'trade' | 'thought', id); v.setTF('1m' | '5m');
//   v.setQuality('max' | 'lite'); v.stats(); v.counts(); v.dispose()
// Data = the holo.json contract (kind le-holo; every field may be null / []). Time on x (DX world units a minute), price on
// y (one scale for the day, the camera frames the bars in view), depth on z. Candles are instanced (two meshes + wicks +
// volume); Max adds a mirrored floor reflection (+ bloom on the PC), Lite has neither. Its own animation loop (not the shared one):
// renders only while on screen and the tab is visible; prefers-reduced-motion = no camera motion. HTML labels (prices,
// times, fill cards, thought panels) follow their 3D anchors and are nudged apart so they never overlap.
import { THREE, View, Q, glowTexture } from './core.js';
import { tierFor, sizeCore } from './rcore.js';

const DX = 0.16;                 // world units per minute
const HMS = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const HM = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false });
export const etHMS = (t) => HMS.format(new Date(t * 1000)).replace(/^24/, '00');
export const etHM = (t) => HM.format(new Date(t * 1000)).replace(/^24/, '00');
export const fmtPx = (x) => x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtUsd = (x) => x == null || !isFinite(x) ? '—' : (x > 0 ? '+' : x < 0 ? '-' : '') + '$' + Math.abs(Math.round(x)).toLocaleString('en-US');
const ok = (v) => typeof v === 'number' && isFinite(v);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const BOTC = { lit: '#4f9bff', atlas: '#ff9a3d', blitz: '#b388ff', scalp: '#b388ff', sys: '#94a3b8' };
export const BOTN = { lit: 'Zlarior', atlas: 'ATLAS', blitz: 'BLITZ', scalp: 'BLITZ', sys: 'Bot' };
const botKey = (b) => (b === 'scalp' ? 'blitz' : b || 'sys');
// what a fill / trade is: SIM (NinjaTrader Sim account), REAL (a live account), MODEL (no broker price: a market close priced
// from the booked $, or the model twin), PAPER (the paper ledgers)
export const tagOf = (x) => (x && x.src === 'sim' ? 'SIM' : x && x.real ? 'REAL' : x && x.src === 'model' ? 'MODEL' : 'PAPER');
export const bookedNote = (f) => (f && f.src === 'model' && !f.real && f.kind !== 'entry' && f.kind !== 'add' ? ' · price from the booked $' : '');
export const botTag = (b) => (!b ? '' : b.real ? (/^sim/i.test(String(b.account || '')) ? 'SIM' : 'REAL') : 'PAPER');
export function fillText(f, bots) {
  const b = botKey(f.bot), nm = (bots?.[b]?.name) || BOTN[b] || b;
  const slip = ok(f.slip_ticks) && ok(f.model_px) && f.model_px !== f.px ? ` · slip ${f.slip_ticks > 0 ? '+' : ''}${f.slip_ticks} tick${Math.abs(f.slip_ticks) === 1 ? '' : 's'} (model ${fmtPx(f.model_px)})` : '';
  return `${f.side} ${f.qty ?? ''} MNQ @ ${fmtPx(f.px)} · ${etHMS(f.t)} ET · ${nm} · ${tagOf(f)}${slip}${bookedNote(f)}`;
}

// shaders: the floor grid, the back wall (price / time grid), dashed beams / lines
const FLOOR_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const FLOOR_F = `uniform vec3 uC; uniform vec3 uT; uniform float uSX; uniform float uOX; varying vec3 vW;
void main(){ vec2 c = vec2((vW.x - uOX) / uSX, vW.z * 1.25); vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c); float l = 1.0 - min(min(g.x, g.y), 1.0);
  float d = length((vW.xz - uT.xz) * vec2(0.55, 1.0)); float fade = exp(-d * 0.10);
  gl_FragColor = vec4(uC * (l * 0.65 + 0.035) * fade, (l * 0.7 + 0.55) * fade); }`;
const WALL_F = `uniform vec3 uC; uniform vec3 uT; uniform float uSY; uniform float uOY; uniform float uSX; uniform float uOX; varying vec3 vW;
void main(){ vec2 c = vec2((vW.x - uOX) / uSX, (vW.y - uOY) / uSY); vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c); float l = 1.0 - min(min(g.x, g.y), 1.0);
  float d = length((vW.xy - uT.xy) * vec2(0.45, 0.6)); float fade = exp(-d * 0.13);
  gl_FragColor = vec4(uC * (l * 0.42 + 0.012) * fade, 1.0); }`;
const DASH_V = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const DASH_F = `uniform vec3 uC; uniform float uO; uniform float uD; uniform float uAxis; varying vec3 vW;
void main(){ float s = uAxis > 0.5 ? vW.y : vW.x; if (uD > 0.0 && fract(s * uD) > 0.55) discard; gl_FragColor = vec4(uC * uO, 1.0); }`;

const LAYERS0 = { fills: true, trades: true, setup: true, thoughts: true, orders: true, levels: true, structure: false, volume: true, bots: { lit: true, atlas: true, blitz: true, sys: true } };

export class Holo extends View {
  constructor(opts = {}) {
    super({ fov: 38, dprMax: opts.phone ? 1.5 : 2, env: 'night', tierCap: 'low', coreBloom: { strength: 0.62, radius: 0.42, threshold: 0.58 }, ...opts, alpha: false });
    this.phone = !!opts.phone;
    this.lite = !!opts.lite || Q.level === 'lite';
    const R = this.renderer;
    R.localClippingEnabled = true; R.info.autoReset = false;      // draw calls counted over every pass of a frame (stats)
    R.setClearColor(new THREE.Color('#03050f'), 1);
    this.scene.background = new THREE.Color('#03050f');
    this.scene.fog = new THREE.Fog(0x03050f, 26, 70);
    const env = this.scene;
    env.add(new THREE.AmbientLight(0x6b7cff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.25); key.position.set(-3, 9, 7); env.add(key);
    this.l1 = new THREE.PointLight(0x38bdf8, 7, 30, 1.4); env.add(this.l1);
    this.l2 = new THREE.PointLight(0xff2bd6, 5, 30, 1.4); env.add(this.l2);
    this.unit = new THREE.BoxGeometry(1, 1, 1);
    this.unitCyl = new THREE.CylinderGeometry(0.5, 0.5, 1, 6, 1, true);
    this.orbG = new THREE.SphereGeometry(1, 20, 14);
    this.icoG = new THREE.IcosahedronGeometry(1, 1);
    this.octG = new THREE.OctahedronGeometry(1, 0);
    this.coneG = new THREE.ConeGeometry(1, 2.2, 14);
    this.edgeG = new THREE.EdgesGeometry(this.unit);
    this.clipUp = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);       // candles above the floor
    this.clipDn = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);      // the reflection below it
    const glass = (c, e) => new THREE.MeshStandardMaterial({ color: new THREE.Color(c), emissive: new THREE.Color(e), emissiveIntensity: 0.75, roughness: 0.14, metalness: 0.32,
      transparent: true, opacity: 0.93, clippingPlanes: [this.clipUp] });
    this.mUp = glass('#22f0a6', '#0c9a64'); this.mDn = glass('#ff3d71', '#a3123d');
    this.mWick = new THREE.MeshBasicMaterial({ color: 0xffffff, clippingPlanes: [this.clipUp] });
    this.mMirUp = new THREE.MeshBasicMaterial({ color: new THREE.Color('#22f0a6').multiplyScalar(0.5), transparent: true, opacity: 0.6, depthWrite: false, clippingPlanes: [this.clipDn] });
    this.mMirDn = new THREE.MeshBasicMaterial({ color: new THREE.Color('#ff3d71').multiplyScalar(0.5), transparent: true, opacity: 0.6, depthWrite: false, clippingPlanes: [this.clipDn] });
    this.mVol = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false });
    // floor: dark glossy glass + neon grid; the back wall: the price / time grid
    this.fU = { uC: { value: new THREE.Color('#3b5bff') }, uT: { value: new THREE.Vector3() }, uSX: { value: DX * 15 }, uOX: { value: 0 } };
    this.floorBase = new THREE.Mesh(new THREE.PlaneGeometry(400, 60), new THREE.MeshStandardMaterial({ color: 0x050816, roughness: 0.25, metalness: 0.6, transparent: true, opacity: 0.66, depthWrite: false }));
    this.floorBase.rotation.x = -Math.PI / 2; this.floorBase.renderOrder = -2; env.add(this.floorBase);
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(400, 60), new THREE.ShaderMaterial({ uniforms: this.fU, vertexShader: FLOOR_V, fragmentShader: FLOOR_F, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, extensions: { derivatives: true } }));
    this.floor.rotation.x = -Math.PI / 2; this.floor.renderOrder = -1; env.add(this.floor);
    this.wU = { uC: { value: new THREE.Color('#5b7bff') }, uT: { value: new THREE.Vector3() }, uSY: { value: 1 }, uOY: { value: 0 }, uSX: { value: DX * 15 }, uOX: { value: 0 } };
    this.wall = new THREE.Mesh(new THREE.PlaneGeometry(400, 120), new THREE.ShaderMaterial({ uniforms: this.wU, vertexShader: FLOOR_V, fragmentShader: WALL_F, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, extensions: { derivatives: true } }));
    this.wall.position.z = -2.2; env.add(this.wall);
    this.G = {};
    for (const k of ['candles', 'mirror', 'vol', 'levels', 'struct', 'orders', 'trades', 'setup', 'fills', 'thoughts', 'now']) { this.G[k] = new THREE.Group(); env.add(this.G[k]); }
    this.G.mirror.scale.y = -1; this.G.mirror.renderOrder = -3;
    // the current price line + its glow
    this.pxLine = new THREE.Mesh(this.unit, new THREE.MeshBasicMaterial({ color: new THREE.Color('#e9f0ff').multiplyScalar(1.4), transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.pxGlow = this._sprite('#9fd3ff', 0.7, 0.9); this.G.now.add(this.pxLine, this.pxGlow);
    // HTML overlay: axes + labels
    this.ov = document.createElement('div'); this.ov.className = 'hd-ov';
    Object.assign(this.ov.style, { position: 'absolute', inset: '0', pointerEvents: 'none', overflow: 'hidden' });
    this.axY = document.createElement('div'); this.axY.className = 'hd-axy'; this.axX = document.createElement('div'); this.axX.className = 'hd-axx';
    this.lab = document.createElement('div'); this.lab.className = 'hd-labs';
    this.ov.append(this.axY, this.axX, this.lab);
    this.pxTag = this._el('hd-pxtag', ''); this.ov.appendChild(this.pxTag);
    this.items = []; this.fills = []; this.trades = []; this.thoughts = []; this.orders = []; this.levels = []; this.n = 0; this.d = null; this.T = Infinity; this.tf = opts.tf || '1m'; this.layers = JSON.parse(JSON.stringify(LAYERS0));
    this.cam = { tx: 0, ty: 0, yaw: -0.5, pitch: 0.3, dist: 14, fov: 38 };
    this.goal = { ...this.cam }; this.mode = 'follow'; this.presetName = '3d'; this.fly = null; this.dirty = true;
    this.st = { frames: 0, ms: 0, msAvg: 0, fps: 0, last: 0, n: 0, acc: 0 };
    this.pops = [];
    this._initComposer();
    this._bindInput();
    this._loop = this._loop.bind(this); this._raf = 0;
    this._vis = () => { if (!document.hidden) this._wake(); };
    document.addEventListener('visibilitychange', this._vis);
  }
  running() { return false; }                       // the shared loop never renders this view: it has its own (_loop)
  _wake() { if (!this._raf && this.attached && !document.hidden) this._raf = requestAnimationFrame(this._loop); }
  _loop(now) {
    this._raf = 0;
    if (!this.attached || document.hidden || this.broken) return;
    const dt = Math.min(0.1, (now - (this._lt || now)) / 1000 || 0.016); this._lt = now;
    if (!this.visible) return;                 // off screen (another page, scrolled away): the loop sleeps until it shows again
    {
      const t0 = performance.now();
      try {
        this.renderer.info.reset(); this.update(now / 1000, dt); const t1 = performance.now();
        this._render(); if (this.measure) this.renderer.getContext().finish(); this._errs = 0;
        const S = this.st; (S.ring || (S.ring = [])).push([t1 - t0, performance.now() - t1]); if (S.ring.length > 90) S.ring.shift();
      }
      catch (e) { console.warn('holo frame', e); if ((this._errs = (this._errs || 0) + 1) > 30) { this.broken = true; return; } }
      const ms = performance.now() - t0, S = this.st;
      S.frames++; S.ms = ms; S.msAvg = S.msAvg ? S.msAvg * 0.92 + ms * 0.08 : ms; S.acc += dt; S.n++;
      if (S.acc > 1) { S.fps = Math.round(S.n / S.acc); S.acc = 0; S.n = 0; if (S.frames > 90 && S.msAvg > 36 && !Q.fixed && this.rc.quality() !== 'low') { this.rc.cap = 'low'; this.rc.setQuality('low'); this.resize(); } }   // a slow GPU: drop bloom + MSAA
    }
    this._raf = requestAnimationFrame(this._loop);
  }
  attach(el) {
    super.attach(el);
    this._io2?.disconnect();
    this._io2 = new IntersectionObserver((es) => { for (const e of es) if (e.isIntersecting) { this.visible = true; this._wake(); } }, { rootMargin: '80px' });
    this._io2.observe(el);
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
    el.appendChild(this.ov); this.dirty = true; this._wake();
  }
  detach() { this._io2?.disconnect(); this.ov.remove(); cancelAnimationFrame(this._raf); this._raf = 0; super.detach(); }
  _initComposer() { /* the OLYMPUS render core (rcore.js) draws the bloom, MSAA and the film finish */ }
  setQuality(q) {
    const lite = q === 'lite';
    if (lite === this.lite) return;
    this.lite = lite;
    this.rc.cap = 'low'; this.rc.setQuality(tierFor(this.rc.cap));
    this.G.mirror.visible = !lite; this.resize();
  }
  resize() {
    // layout size (clientWidth / Height), not the bounding box: a page's warp-in animation scales it while the view mounts
    if (!this.el) return;
    const w = Math.max(10, this.el.clientWidth || 0), h = Math.max(10, this.el.clientHeight || 0);
    this.w = w; this.h = h;
    sizeCore(this.rc, w, h);
    this.canvas.style.width = w + 'px'; this.canvas.style.height = h + 'px';
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    this.dirty = true;
  }
  _render() { this.rc.render(); }

  // ------------------------------------------------------------------ helpers
  _el(cls, html) { const e = document.createElement('div'); e.className = cls; e.innerHTML = html; return e; }
  _sprite(color, scale, opacity = 1) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(color), transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false }));
    s.scale.set(scale, scale, 1); return s;
  }
  _neon(color, k = 1.3, op = 0.95) { return new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(k), transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false }); }
  _dash(color, op = 0.9, dash = 0, axis = 0) {
    return new THREE.ShaderMaterial({ uniforms: { uC: { value: new THREE.Color(color) }, uO: { value: op }, uD: { value: dash }, uAxis: { value: axis } }, vertexShader: DASH_V, fragmentShader: DASH_F,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  }
  // a horizontal bar (line) from x0 to x1 at y (world), z, thickness th
  _hbar(group, mat, x0, x1, y, z, th = 0.02) { const m = new THREE.Mesh(this.unit, mat); this._setH(m, x0, x1, y, z, th); group.add(m); return m; }
  _setH(m, x0, x1, y, z, th = 0.02) { const w = Math.max(0.001, x1 - x0); m.position.set(x0 + w / 2, y, z); m.scale.set(w, th, th); m.visible = x1 > x0; }
  _vbar(group, mat, x, y0, y1, z, th = 0.014) { const m = new THREE.Mesh(this.unit, mat); this._setV(m, x, y0, y1, z, th); group.add(m); return m; }
  _setV(m, x, y0, y1, z, th = 0.014) { const a = Math.min(y0, y1), h = Math.max(0.001, Math.abs(y1 - y0)); m.position.set(x, a + h / 2, z); m.scale.set(th, h, th); }
  // a label item: an HTML element that follows a 3D anchor; kind = 'fill' | 'trade' | 'thought' | 'order' | 'level' | 'setup' | 'struct'
  _label(kind, html, cls, anchor, o = {}) {
    const el = this._el('hd-lab hd-' + kind + (cls ? ' ' + cls : ''), html);
    el.style.transform = 'translate(-9999px,0)';
    if (o.color) el.style.setProperty('--c', o.color);
    if (o.id != null) { el.dataset.id = o.id; el.dataset.kind = kind; }
    if (o.title) el.title = o.title;
    this.lab.appendChild(el);
    const it = { kind, el, anchor, t: o.t ?? -Infinity, t1: o.t1, bot: o.bot, layer: o.layer || kind, pri: o.pri || 1, lift: o.lift || 0, id: o.id, show: true, above: !!o.above, data: o.data, w: 0, h: 0 };
    if (o.click !== false && o.id != null) { el.style.pointerEvents = 'auto'; el.addEventListener('click', (e) => { e.stopPropagation(); this.opts.onPick?.(kind, o.id, o.data); }); }
    this.items.push(it); return it;
  }
  X(t) { return (t - this.t0) / 60 * DX; }
  Y(p) { return (p - this.p0) * this.ys; }
  tAt(x) { return this.t0 + x / DX * 60; }
  pAt(y) { return this.p0 + y / this.ys; }
  bars() { const B = this.d?.bars || {}; const b = B[this.tf]?.length ? B[this.tf] : (B['1m']?.length ? B['1m'] : B['5m'] || []); return b; }
  secs() { const b = this.bars(); return b.length > 1 ? Math.max(60, Math.min(...b.slice(0, 6).map((x, i, a) => i ? x[0] - a[i - 1][0] : 1e9))) : 60; }
  barAt(t) {                            // index of the last bar starting at or before t
    const b = this.bars(); let lo = 0, hi = b.length - 1; if (!b.length || t < b[0][0]) return -1;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (b[m][0] <= t) lo = m; else hi = m - 1; }
    return lo;
  }
  pxAt(t) { const b = this.bars(), i = this.barAt(t); return i < 0 ? b[0]?.[1] : b[i][4]; }
  on(bot) { const k = botKey(bot); return this.layers.bots[k] !== false; }

  // ------------------------------------------------------------------ data
  setData(d, o = {}) {
    const day0 = this.d?.day;
    this.d = d || {};
    const b = this.bars();
    this._clear();
    if (!b.length) { this.n = 0; this.dirty = true; return; }
    this.t0 = b[0][0]; this.secs_ = this.secs();
    this.tEnd = b.at(-1)[0] + this.secs_;
    // one price scale for the day: the median range of a focus window ~ the window's height
    this.focusN = this._focusBars();
    const W = this.focusN, rs = [];
    for (let i = 0; i + 4 < b.length; i += Math.max(4, W >> 1)) { let hi = -Infinity, lo = Infinity; for (let k = i; k < Math.min(b.length, i + W); k++) { hi = Math.max(hi, b[k][2]); lo = Math.min(lo, b[k][3]); } rs.push(hi - lo); }
    rs.sort((a, c) => a - c);
    const med = rs[rs.length >> 1] || 40;
    const winW = W * this.secs_ / 60 * DX;
    this.ys = (winW * (this.phone ? 0.95 : 0.5)) / Math.max(8, med);
    this.p0 = b[0][1];
    this._buildCandles();
    this._buildLevels(); this._buildStruct(); this._buildOrders(); this._buildTrades(); this._buildFills(); this._buildThoughts();
    this.fU.uSX.value = this.wU.uSX.value = DX * (this.phone ? 30 : 15); this.fU.uOX.value = this.wU.uOX.value = this.X(Math.ceil(this.t0 / 900) * 900);
    this._applyLayers();
    if (o.keepTime && day0 === this.d.day) this.setTime(this.T, { pop: false }); else this.setTime(o.T ?? Infinity, { pop: false });
    if (day0 !== this.d.day || !this._framed) { this._framed = true; this._frameNow(true); }
    this.dirty = true; this._wake();
  }
  setTF(tf) { if (tf === this.tf) return; this.tf = tf; if (this.d) this.setData(this.d, { keepTime: true }); }
  _focusBars() { const asp = this.w / Math.max(1, this.h); const base = this.secs() >= 300 ? 60 : 110; return Math.round(base * Math.max(0.42, Math.min(1.25, asp / 1.6))); }
  _clear() {
    for (const k of Object.keys(this.G)) {
      if (k === 'now') continue;
      const g = this.G[k];
      for (const o of [...g.children]) { g.remove(o); o.traverse?.((x) => { if (x.geometry && ![this.unit, this.unitCyl, this.orbG, this.icoG, this.octG, this.coneG, this.edgeG].includes(x.geometry)) x.geometry.dispose(); const m = x.material; if (m && ![this.mUp, this.mDn, this.mWick, this.mMirUp, this.mMirDn, this.mVol].includes(m)) m.dispose?.(); }); }
    }
    for (const it of this.items) it.el.remove();
    this.items = []; this.fills = []; this.trades = []; this.thoughts = []; this.orders = []; this.levels = []; this.setups = []; this.pops = [];
  }
  _buildCandles() {
    const b = this.bars(), n = b.length, sec = this.secs_, bw = sec / 60 * DX * 0.68;
    const ups = [], dns = [];
    b.forEach((x, i) => (x[4] >= x[1] ? ups : dns).push(i));
    this.order = { up: ups, dn: dns, slot: new Int32Array(n) };
    ups.forEach((i, k) => { this.order.slot[i] = k; }); dns.forEach((i, k) => { this.order.slot[i] = k; });
    const mk = (geo, mat, cnt) => { const m = new THREE.InstancedMesh(geo, mat, Math.max(1, cnt)); m.frustumCulled = false; return m; };
    this.mU = mk(this.unit, this.mUp, ups.length); this.mD = mk(this.unit, this.mDn, dns.length);
    this.wk = mk(this.unitCyl, this.mWick, n);
    this.vol = mk(this.unit, this.mVol, n);
    this.mirU = mk(this.unit, this.mMirUp, ups.length); this.mirD = mk(this.unit, this.mMirDn, dns.length); this.mirU.renderOrder = this.mirD.renderOrder = -3;
    this.bw = bw;
    const vmax = Math.max(1, ...b.map((x) => x[5] || 0));
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    const cU = new THREE.Color('#9fffe0'), cD = new THREE.Color('#ffb3c8'), vU = new THREE.Color('#22f0a6').multiplyScalar(0.9), vD = new THREE.Color('#ff3d71').multiplyScalar(0.9);
    for (let i = 0; i < n; i++) {
      const x = b[i], up = x[4] >= x[1], cx = this.X(x[0] + sec / 2);
      this._putBar(i, x[1], x[2], x[3], x[4]);
      const vh = (x[5] || 0) / vmax * 1.3;
      p.set(cx, vh / 2, -1.5); s.set(bw * 0.9, Math.max(0.002, vh), 0.12); M.compose(p, q, s); this.vol.setMatrixAt(i, M); this.vol.setColorAt(i, up ? vU : vD);
      this.wk.setColorAt(i, up ? cU : cD);
    }
    for (const m of [this.mU, this.mD, this.wk, this.vol, this.mirU, this.mirD]) { m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true; }
    this.G.candles.add(this.mU, this.mD, this.wk); this.G.vol.add(this.vol); this.G.mirror.add(this.mirU, this.mirD);
    this.G.mirror.visible = !this.lite;
    this.n = n;
  }
  _putBar(i, o, h, l, c) {
    const b = this.bars(), x = b[i], up = x[4] >= x[1], k = this.order.slot[i], cx = this.X(x[0] + this.secs_ / 2), bw = this.bw;
    const M = this._M || (this._M = new THREE.Matrix4()), q = this._q || (this._q = new THREE.Quaternion()), s = this._s || (this._s = new THREE.Vector3()), p = this._p || (this._p = new THREE.Vector3());
    const yt = this.Y(Math.max(o, c)), yb = this.Y(Math.min(o, c));
    p.set(cx, (yt + yb) / 2, 0); s.set(bw, Math.max(0.018, yt - yb), bw); M.compose(p, q, s);
    (up ? this.mU : this.mD).setMatrixAt(k, M); (up ? this.mirU : this.mirD).setMatrixAt(k, M);
    p.set(cx, (this.Y(h) + this.Y(l)) / 2, 0); s.set(0.022, Math.max(0.02, this.Y(h) - this.Y(l)), 0.022); M.compose(p, q, s); this.wk.setMatrixAt(i, M);
  }
  _buildLevels() {
    const end = this.tEnd;
    for (const L of this.d.levels || []) {
      if (!ok(L.px)) continue;
      const b = botKey(L.bot), col = BOTC[b] || '#cbd5e1', y = this.Y(L.px), ta = L.t1 || L.t0 || this.t0;
      const live = this._hbar(this.G.levels, this._neon(col, 1.2, 0.85), this.X(ta), this.X(L.taken_t || end), y, 0.05, 0.016);
      const after = L.taken_t ? this._hbar(this.G.levels, this._dash(col, 0.35, 6), this.X(L.taken_t), this.X(end), y, 0.05, 0.01) : null;
      const it = this._label('level', `<b>${esc(L.label || '')}</b> ${fmtPx(L.px)}${L.taken_t ? ' <i>✓ taken ' + etHM(L.taken_t) + '</i>' : ''}`, b, { x: this.X(L.taken_t || end), y, z: 0.05, clampR: true },
        { color: col, t: ta, bot: b, layer: 'levels', pri: 0.4, click: false });
      this.levels.push({ L, b, live, after, it, ta });
    }
  }
  _buildStruct() {
    const S = this.d.structure; if (!S || typeof S !== 'object') return;
    const end = this.tEnd, g = this.G.struct;
    const z = S.zone;
    if (z && ok(z.lo) && ok(z.hi) && z.hi > z.lo) {
      const eq = ok(z.eq) ? z.eq : (z.lo + z.hi) / 2, x0 = this.X(this.t0), x1 = this.X(end);
      for (const [a, c, col] of [[eq, z.hi, '#ff3d71'], [z.lo, eq, '#22f0a6']]) {
        const m = new THREE.Mesh(this.unit, new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(0.07), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
        m.position.set((x0 + x1) / 2, (this.Y(a) + this.Y(c)) / 2, -2.0); m.scale.set(x1 - x0, Math.abs(this.Y(c) - this.Y(a)), 0.05); g.add(m);
      }
      this._hbar(g, this._dash('#e2e8f0', 0.5, 5), x0, x1, this.Y(eq), -1.9, 0.012);
      this._label('struct', `equilibrium ${fmtPx(eq)}`, '', { x: x1, y: this.Y(eq), z: -1.9, clampR: true }, { color: '#e2e8f0', layer: 'structure', pri: 0.2, click: false });
    }
    for (const p of S.pools || []) {
      if (!p || !ok(p.price)) continue;
      const bs = /^b/i.test(p.side || ''), col = bs ? '#38e1ff' : '#ff5fd2', y = this.Y(p.price), x0 = this.X(p.t0 || this.t0), x1 = this.X(end);
      const pl = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(p.swept ? 0.04 : 0.12), transparent: true, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
      pl.rotation.x = -Math.PI / 2; pl.position.set((x0 + x1) / 2, y, -0.3); pl.scale.set(Math.max(0.1, x1 - x0), 2.6, 1); g.add(pl);
      this._hbar(g, this._neon(col, p.swept ? 0.5 : 1.2, 0.8), x0, x1, y, 1.0, 0.012);
      this._label('struct', `${bs ? 'BSL' : 'SSL'} ${esc(p.label || '')} ${fmtPx(p.price)}${p.swept ? ' ✓' : ''}`, '', { x: x1, y, z: 1.0, clampR: true }, { color: col, t: p.t0, layer: 'structure', pri: 0.3, click: false });
    }
    const F = S.frames || {};
    for (const [tf, sz] of [['5m', 1], ['15m', 1.2], ['1h', 1.4]]) {
      const fr = F[tf]; if (!fr) continue;
      for (const sw of (fr.swings || []).slice(-14)) {
        if (!ok(sw.price) || !ok(sw.t) || sw.t < this.t0) continue;
        const hiS = /H$/.test(sw.kind || '') && /^(HH|LH)$/.test(sw.kind);
        this._label('struct', `${esc(sw.kind)}${tf !== '5m' ? '<sub>' + tf + '</sub>' : ''}`, 'sw' + (hiS ? ' hi' : ' lo'), { x: this.X(sw.t + 150), y: this.Y(sw.price) + (hiS ? 0.18 : -0.18) * sz, z: 0.2 },
          { color: hiS ? '#ffb4c6' : '#9fffe0', t: sw.t, layer: 'structure', pri: 0.25, click: false });
      }
      const e = fr.last_event;
      if (e && ok(e.price) && ok(e.t) && e.t >= this.t0) {
        const col = e.dir === 1 || /up/i.test(String(e.dir)) ? '#22f0a6' : '#ff3d71';
        this._hbar(g, this._dash(col, 0.9, 7), this.X(e.t - 1800), this.X(e.t), this.Y(e.price), 0.3, 0.016);
        this._label('struct', `${esc(e.kind || 'BOS')} ${tf} ${e.dir === 1 ? '▲' : '▼'}`, 'ev', { x: this.X(e.t - 900), y: this.Y(e.price) + 0.12, z: 0.3 }, { color: col, t: e.t, layer: 'structure', pri: 0.5, click: false });
      }
    }
  }
  _buildOrders() {
    for (const [k, o] of (this.d.orders || []).entries()) {
      if (!ok(o.px) || !ok(o.t)) continue;
      const b = botKey(o.bot), col = BOTC[b], y = this.Y(o.px);
      // a model order (the LIT model's limit, never sent to the broker) is a ghost: dim dashed, labelled MODEL
      const mat = o.model ? this._dash(new THREE.Color(col).lerp(new THREE.Color('#ffffff'), 0.5), 0.5, 4) : o.type === 'STOP' ? this._dash(col, 1.1, 9) : this._neon(col, 1.5, 0.95);
      const line = this._hbar(this.G.orders, mat, this.X(o.t), this.X(o.t + 60), y, 0.25, 0.028);
      const gl = this._sprite(col, 0.32, 0.8); gl.position.set(this.X(o.t), y, 0.25); this.G.orders.add(gl);
      const id = 'o' + k;
      const it = this._label('order', `<b>${o.model ? 'MODEL ' : ''}${esc(o.type)} ${esc(o.side || '')} ${o.qty ?? ''}</b> @ ${fmtPx(o.px)} <i>${esc(o.state || '')}</i>`, b + (o.model ? ' model' : ''), { x: this.X(o.t), y, z: 0.25 },
        { color: col, t: o.t, t1: o.t_end, bot: b, layer: 'orders', pri: 0.6, id, data: o, title: o.why || '' });
      this.orders.push({ o, b, line, gl, it, id });
    }
  }
  _buildTrades() {
    for (const tr of this.d.trades || []) {
      if (!tr || !tr.entry || !ok(tr.entry.t) || !ok(tr.entry.px)) continue;
      const b = botKey(tr.bot), col = BOTC[b], long = tr.side !== 'SHORT', g = new THREE.Group(); this.G.trades.add(g);
      const ex = tr.exit && ok(tr.exit.t) ? tr.exit : null, E = tr.entry.px, yE = this.Y(E), z = 0, dep = 1.1;
      const boxMat = (c, op) => new THREE.MeshStandardMaterial({ color: new THREE.Color(c), emissive: new THREE.Color(c), emissiveIntensity: 0.55, transparent: true, opacity: op, depthWrite: false, side: THREE.DoubleSide, roughness: 0.1, metalness: 0.1 });
      const edgeMat = (c) => new THREE.LineBasicMaterial({ color: new THREE.Color(c).multiplyScalar(1.4), transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false });
      const mkBox = (c, op) => { const m = new THREE.Mesh(this.unit, boxMat(c, op)); const e = new THREE.LineSegments(this.edgeG, edgeMat(c)); m.add(e); m.userData.pick = { kind: 'trade', id: tr.id }; g.add(m); return m; };
      const steps = (Array.isArray(tr.stop_path) && tr.stop_path.length ? tr.stop_path : []).filter((s) => ok(s[0]) && ok(s[1]));
      const risk = steps.map((s) => ({ t: s[0], px: s[1], m: mkBox(((long && s[1] >= E) || (!long && s[1] <= E)) ? '#22f0a6' : '#ff3d71', 0.15) }));
      const reward = ok(tr.target) ? mkBox('#22f0a6', 0.075) : null;
      // the stop path as a neon step line
      const sp = steps.map((s) => ({ t: s[0], px: s[1], h: this._hbar(g, this._neon('#ff7a59', 1.5, 1), 0, 0, this.Y(s[1]), dep / 2 + 0.01, 0.03) }));
      const vSteps = sp.slice(1).map((s, i) => this._vbar(g, this._neon('#ffb347', 1.6, 1), this.X(s.t), this.Y(sp[i].px), this.Y(s.px), dep / 2 + 0.01, 0.03));
      const tgtLine = ok(tr.target) ? this._hbar(g, this._neon('#22f0a6', 1.4, 0.95), 0, 0, this.Y(tr.target), dep / 2 + 0.01, 0.028) : null;
      // exit marker + the trade's $ / R
      let exM = null;
      if (ex && ok(ex.px)) {
        const win = (tr.usd ?? 0) >= 0;
        exM = new THREE.Mesh(this.octG, this._neon(win ? '#22f0a6' : '#ff3d71', 1.6, 1)); exM.scale.setScalar(0.09); exM.position.set(this.X(ex.t), this.Y(ex.px), dep / 2 + 0.05); g.add(exM);
        exM.userData.pick = { kind: 'trade', id: tr.id };
      }
      // the model twin: a ghost line entry -> exit
      let twin = null;
      if (tr.model && ok(tr.model.entry_t) && ok(tr.model.entry) && ok(tr.model.exit_t) && ok(tr.model.exit)) {
        const a = new THREE.Vector3(this.X(tr.model.entry_t), this.Y(tr.model.entry), dep / 2 + 0.12), c = new THREE.Vector3(this.X(tr.model.exit_t), this.Y(tr.model.exit), dep / 2 + 0.12);
        const geo = new THREE.BufferGeometry().setFromPoints([a, c]);
        twin = new THREE.Line(geo, new THREE.LineDashedMaterial({ color: 0xdbe7ff, dashSize: 0.12, gapSize: 0.09, transparent: true, opacity: 0.55 })); twin.computeLineDistances(); g.add(twin);
      }
      const hiY = Math.max(yE, ok(tr.target) ? this.Y(tr.target) : yE, ...steps.map((s) => this.Y(s[1])));
      const loY = Math.min(yE, ok(tr.target) ? this.Y(tr.target) : yE, ...steps.map((s) => this.Y(s[1])));
      const nm = this.d.bots?.[b]?.name || BOTN[b];
      const it = this._label('trade', `<b>${esc(nm)} ${esc(tr.side)} ${tr.qty ?? ''}</b> <span class="${(tr.usd ?? 0) >= 0 ? 'up' : 'dn'}">${fmtUsd(tr.usd)}${ok(tr.r) ? ' · ' + (tr.r >= 0 ? '+' : '') + tr.r.toFixed(2) + 'R' : ''}</span> <i>${tagOf(tr)}${ex ? ' · ' + esc(ex.reason || '') : ' · open'}</i>`, b,
        { x: this.X(tr.entry.t), y: long ? hiY : hiY, z: dep / 2, up: true }, { color: col, t: tr.entry.t, bot: b, layer: 'trades', pri: 1.6, id: tr.id, data: tr, lift: 0.16 });
      const setup = this._buildSetup(tr, b, col);
      this.trades.push({ tr, b, g, risk, reward, sp, vSteps, tgtLine, exM, twin, it, ex, setup, E, long, dep, hiY, loY, t0: tr.entry.t });
    }
  }
  _buildSetup(tr, b, col) {
    const S = tr.setup; if (!S || !ok(S.t_sweep) || !ok(S.sweep_ext)) return null;
    const g = new THREE.Group(); this.G.setup.add(g);
    const short = tr.side === 'SHORT', z = 0.62, out = { g, parts: [] };
    const add = (t, obj, lab) => out.parts.push({ t, obj, lab });
    const px = (t, hi) => { const B = this.bars(), i = this.barAt(t); return i < 0 ? null : hi ? B[i][2] : B[i][3]; };
    // 1 sweep: a cone pointing at the extreme (t_ext when the data has it: the bar that made it) + the swept level lines
    const tS = ok(S.t_ext) ? S.t_ext : S.t_sweep;
    const yS = this.Y(S.sweep_ext);
    const cone = new THREE.Mesh(this.coneG, this._neon('#ffd166', 1.6, 1)); cone.scale.setScalar(0.07); cone.rotation.z = short ? Math.PI : 0;
    cone.position.set(this.X(tS), yS + (short ? 0.2 : -0.2), z); g.add(cone);
    const ring = this._sprite('#ffd166', 0.5, 0.9); ring.position.set(this.X(tS), yS, z); g.add(ring);
    add(tS, cone, this._label('setup', `<em>1</em> Sweep ${fmtPx(S.sweep_ext)}`, 'step', { x: this.X(tS), y: yS + (short ? 0.38 : -0.38), z }, { color: '#ffd166', t: tS, bot: b, layer: 'setup', pri: 1.3, id: tr.id, data: tr }));
    add(tS, ring, null);
    // the swept levels (nearest the extreme first, 3 at most): a line up to the moment each one was taken
    const sws = (S.swept || []).filter((x) => ok(x.px)).sort((p, q) => Math.abs(p.px - S.sweep_ext) - Math.abs(q.px - S.sweep_ext)).slice(0, 3);
    for (const sw of sws) {
      const te = ok(sw.t) ? sw.t : tS, y = this.Y(sw.px), m = this._hbar(g, this._neon('#ffd166', 1.1, 0.8), this.X(te - 5400), this.X(te), y, z, 0.016);
      add(te - 5400, m, this._label('setup', `swept: ${esc(sw.label || '')} ${fmtPx(sw.px)}`, 'lvl', { x: this.X(te - 5400), y, z, left: true }, { color: '#ffd166', t: te - 600, bot: b, layer: 'setup', pri: 0.9, click: false }));
    }
    // 2 inducement
    const pts = [];
    if (ok(S.t_idm)) {
      const p = px(S.t_idm, short), y = this.Y(p ?? S.sweep_ext);
      const d = new THREE.Mesh(this.octG, this._neon('#c084fc', 1.6, 1)); d.scale.setScalar(0.06); d.position.set(this.X(S.t_idm), y, z); g.add(d);
      add(S.t_idm, d, this._label('setup', '<em>2</em> Inducement', 'step', { x: this.X(S.t_idm), y: y + (short ? 0.26 : -0.26), z }, { color: '#c084fc', t: S.t_idm, bot: b, layer: 'setup', pri: 1.1, id: tr.id, data: tr }));
      pts.push(new THREE.Vector3(this.X(S.t_idm), y, z));
    }
    pts.push(new THREE.Vector3(this.X(tS), yS, z));
    // 3 displacement: an arrow from the sweep down / up to the displacement bar's close
    if (ok(S.t_disp)) {
      const B = this.bars(), i = this.barAt(S.t_disp), p = i >= 0 ? B[i][4] : null;
      if (p != null) {
        const a = new THREE.Vector3(this.X(Math.min(tS, S.t_disp - 60)), yS, z), c = new THREE.Vector3(this.X(S.t_disp), this.Y(p), z);
        const tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.LineCurve3(a, c), 8, 0.022, 6, false), this._neon('#38e1ff', 1.6, 0.95)); g.add(tube);
        const head = new THREE.Mesh(this.coneG, this._neon('#38e1ff', 1.8, 1)); head.scale.setScalar(0.05); head.position.copy(c);
        head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), c.clone().sub(a).normalize()); g.add(head);
        add(S.t_disp, tube, this._label('setup', '<em>3</em> Displacement', 'step', { x: (a.x + c.x) / 2 + 0.15, y: (a.y + c.y) / 2, z }, { color: '#38e1ff', t: S.t_disp, bot: b, layer: 'setup', pri: 1.1, id: tr.id, data: tr }));
        add(S.t_disp, head, null);
        pts.push(c);
      }
    }
    // 4 CISD level
    if (ok(S.cisd)) {
      const tc = ok(S.t_cisd) ? S.t_cisd : tr.entry.t, y = this.Y(S.cisd);
      const m = this._hbar(g, this._neon('#38e1ff', 1.3, 0.9), this.X(tc - 1500), this.X(tr.entry.t + 600), y, z, 0.02);
      add(tc, m, this._label('setup', `<em>4</em> CISD ${fmtPx(S.cisd)}`, 'step', { x: this.X(tc), y: y + (short ? -0.2 : 0.2), z }, { color: '#38e1ff', t: tc, bot: b, layer: 'setup', pri: 1.1, id: tr.id, data: tr }));
      pts.push(new THREE.Vector3(this.X(tc), y, z));
    }
    // 5 entry, stop, target
    const yE = this.Y(tr.entry.px);
    pts.push(new THREE.Vector3(this.X(tr.entry.t), yE, z));
    add(tr.entry.t, null, this._label('setup', `<em>5</em> Entry ${fmtPx(tr.entry.px)}`, 'step', { x: this.X(tr.entry.t), y: yE + (short ? 0.3 : -0.3), z }, { color: col, t: tr.entry.t, bot: b, layer: 'setup', pri: 1.2, id: tr.id, data: tr }));
    const st0 = tr.stop_path?.[0]?.[1];
    if (ok(st0)) add(tr.entry.t, null, this._label('setup', `Stop ${fmtPx(st0)} · 1 tick beyond the sweep`, 'lvl', { x: this.X(tr.entry.t), y: this.Y(st0), z, left: true }, { color: '#ff7a59', t: tr.entry.t, bot: b, layer: 'setup', pri: 0.8, click: false }));
    if (ok(tr.target)) add(tr.entry.t, null, this._label('setup', `Target ${fmtPx(tr.target)}`, 'lvl', { x: this.X(tr.entry.t), y: this.Y(tr.target), z, left: true }, { color: '#22f0a6', t: tr.entry.t, bot: b, layer: 'setup', pri: 0.8, click: false }));
    // the anatomy path through the steps (time order)
    pts.sort((p, q) => p.x - q.x);
    if (pts.length >= 2) {
      const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal', 0.3);
      const path = new THREE.Mesh(new THREE.TubeGeometry(curve, 60, 0.008, 5, false), this._neon('#fff1b8', 1.2, 0.55)); g.add(path);
      add(tr.entry.t, path, null);
    }
    return out;
  }
  _buildFills() {
    for (const f of this.d.fills || []) {
      if (!f || !ok(f.t) || !ok(f.px)) continue;
      const b = botKey(f.bot), col = BOTC[b], g = new THREE.Group(); this.G.fills.add(g);
      const x = this.X(f.t), y = this.Y(f.px), z = 0.7, r = this.phone ? 0.075 : 0.065, real = !!f.real;
      const orb = real ? new THREE.Mesh(this.orbG, new THREE.MeshStandardMaterial({ color: new THREE.Color(col), emissive: new THREE.Color(col), emissiveIntensity: 1.3, roughness: 0.2, metalness: 0.1 }))
        : new THREE.Mesh(this.icoG, new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(1.5), wireframe: true, transparent: true, opacity: 0.95 }));
      orb.scale.setScalar(r); orb.userData.pick = { kind: 'fill', id: f.id };
      const halo = this._sprite(col, real ? 0.55 : 0.36, real ? 0.9 : 0.55);
      const beam = new THREE.Mesh(this.unit, real ? this._neon(col, 1.1, 0.55) : this._dash(col, 0.8, 7, 1));
      g.add(orb, halo, beam); g.position.set(x, y, z);
      let ghost = null, link = null;
      if (ok(f.model_px) && Math.abs(f.model_px - f.px) > 1e-9) {
        ghost = new THREE.Mesh(this.orbG, new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.45, depthWrite: false })); ghost.scale.setScalar(r * 0.55);
        ghost.position.set(0.09, this.Y(f.model_px) - y, 0.05); g.add(ghost);
        link = this._vbar(g, this._neon('#ffffff', 1, 0.6), 0.09, 0, this.Y(f.model_px) - y, 0.05, 0.006);
      }
      const side = f.side === 'BUY' ? '▲' : '▼';
      const it = this._label('fill', `<b>${side} ${esc(f.side)} ${f.qty ?? ''}</b> @ <span class="px">${fmtPx(f.px)}</span> · <span class="tm">${etHMS(f.t)}</span> <i class="${real ? 'real' : 'paper'}">${tagOf(f)}</i><span class="more"> · ${esc(this.d.bots?.[b]?.name || BOTN[b])}${ok(f.slip_ticks) && ok(f.model_px) && f.model_px !== f.px ? ` · slip ${f.slip_ticks > 0 ? '+' : ''}${f.slip_ticks} tick (model ${fmtPx(f.model_px)})` : ''}${bookedNote(f)}</span>`,
        b + (real ? ' real' : ' paper'), { x, y, z, fill: true }, { color: col, t: f.t, bot: b, layer: 'fills', pri: 2, id: f.id, data: f, title: fillText(f, this.d.bots), lift: 0.12 });
      it.el.dataset.px = f.px; it.el.dataset.t = f.t;
      this.fills.push({ f, b, g, orb, halo, beam, ghost, link, it, real, shown: false });
    }
  }
  _buildThoughts() {
    const T = (this.d.thoughts || []).filter((x) => x && ok(x.t)).sort((a, c) => a.t - c.t);
    T.forEach((th, k) => {
      const b = botKey(th.bot), col = BOTC[b] || BOTC.sys, x = this.X(th.t);
      const p = ok(th.px) ? th.px : this.pxAt(th.t);
      if (!ok(p)) return;
      const y = this.Y(p), lift = 0.75 + (k % 3) * 0.42;
      const g = new THREE.Group(); this.G.thoughts.add(g); g.position.set(x, y, 0.9);
      const dia = new THREE.Mesh(this.octG, this._neon(col, 1.5, 1)); dia.scale.setScalar(0.045); dia.userData.pick = { kind: 'thought', id: 'th' + k }; g.add(dia);
      const teth = this._vbar(g, this._neon(col, 1, 0.45), 0, 0, lift, 0, 0.006);
      const id = 'th' + k;
      const it = this._label('thought', `<header><i></i><b>${esc(this.d.bots?.[b]?.name || BOTN[b])}</b><span>${etHMS(th.t)}</span></header><h4>${esc(th.title || th.stage || '')}</h4><p>${esc(th.text || '')}</p>`,
        `${b} lv-${th.level || 'info'}`, { x, y: y + lift, z: 0.9, up: true }, { color: col, t: th.t, bot: b, layer: 'thoughts', pri: 1.2, id, data: th });
      this.thoughts.push({ th, b, g, dia, teth, it, id, k });
    });
  }

  // ------------------------------------------------------------------ time + layers
  setTime(T, o = {}) {
    if (!this.n) { this.T = T; return; }
    const b = this.bars(), sec = this.secs_;
    T = Math.min(T, this.tEnd); if (!(T >= this.t0)) T = this.t0;
    this.T = T;
    // candles: every bar that started by T; the bar in progress grows from its open toward its close
    const k = this.barAt(T);
    const cu = this._cnt(this.order.up, k), cd = this._cnt(this.order.dn, k);
    this.mU.count = this.mirU.count = cu; this.mD.count = this.mirD.count = cd; this.wk.count = this.vol.count = k + 1;
    if (this._grow != null && this._grow !== k && this._grow < b.length) { const x = b[this._grow]; this._putBar(this._grow, x[1], x[2], x[3], x[4]); this._touch(); this._grow = null; }
    if (k >= 0) {
      const x = b[k], f = Math.max(0, Math.min(1, (T - x[0]) / sec));
      if (f < 1) {
        const c = x[1] + (x[4] - x[1]) * f, top = Math.max(x[1], c), bot = Math.min(x[1], c);
        this._putBar(k, x[1], top + (x[2] - Math.max(x[1], x[4])) * f, bot - (Math.min(x[1], x[4]) - x[3]) * f, c); this._touch(); this._grow = k;
      } else if (this._grow === k) { this._putBar(k, x[1], x[2], x[3], x[4]); this._touch(); this._grow = null; }
      this.price = f < 1 ? Math.round((x[1] + (x[4] - x[1]) * f) * 4) / 4 : x[4];      // the forming bar's price, on the tick
    }
    // fills pop exactly when they happened
    for (const F of this.fills) {
      const on = F.f.t <= T;
      if (on && !F.shown && o.pop) this.pops.push({ F, age: 0 });
      if (!on) F.g.scale.setScalar(1);
      F.shown = on; F.g.visible = on && this.on(F.b);
    }
    for (const O of this.orders) {
      const t1 = Math.min(T, O.o.t_end ?? T), on = O.o.t <= T;
      this._setH(O.line, this.X(O.o.t), this.X(Math.max(O.o.t + 30, t1)), this.Y(O.o.px), 0.25, 0.028);
      const bo = this.on(O.b); O.line.visible = on && bo; O.gl.visible = bo && on && (O.o.t_end == null || T < O.o.t_end);
      O.gl.position.x = this.X(Math.max(O.o.t + 30, t1));
      O.working = on && (O.o.t_end == null || T < O.o.t_end);
      O.it.el.classList.toggle('working', O.working);
      O.it.el.querySelector('i').textContent = O.working ? 'WORKING' : (O.o.state || '');
    }
    for (const Tr of this.trades) this._trTime(Tr, T);
    for (const L of this.levels) {
      const on = T >= L.ta, te = Math.min(T, L.L.taken_t || T);
      const bo = this.on(L.b);
      if (L.live) { this._setH(L.live, this.X(L.ta), this.X(Math.max(L.ta + 60, te)), this.Y(L.L.px), 0.05, 0.016); L.live.visible = on && bo; }
      if (L.after) { L.after.visible = bo && on && L.L.taken_t != null && T > L.L.taken_t; if (L.after.visible) this._setH(L.after, this.X(L.L.taken_t), this.X(T), this.Y(L.L.px), 0.05, 0.01); }
      L.it.anchor.x = this.X(Math.max(L.ta + 60, te));
      L.it.el.querySelector('i')?.classList.toggle('hid', !(L.L.taken_t && T >= L.L.taken_t));
    }
    // thoughts: the newest ones get the full holographic panel
    const vis = this.thoughts.filter((x) => x.th.t <= T && this.on(x.b));
    for (const x of this.thoughts) x.g.visible = x.th.t <= T && this.on(x.b);
    this.lastThought = vis.at(-1) || null;
    this.dirty = true; this._wake();
  }
  _cnt(list, k) { let lo = 0, hi = list.length; while (lo < hi) { const m = (lo + hi) >> 1; if (list[m] <= k) lo = m + 1; else hi = m; } return lo; }
  _touch() { for (const m of [this.mU, this.mD, this.wk, this.mirU, this.mirD]) m.instanceMatrix.needsUpdate = true; }
  _trTime(Tr, T) {
    const { tr, E, dep } = Tr, on = tr.entry.t <= T && this.on(Tr.b);
    Tr.g.visible = on;
    const tEnd = Math.min(T, Tr.ex ? Tr.ex.t : T), yE = this.Y(E);
    const steps = Tr.risk;
    steps.forEach((s, i) => {
      const a = Math.max(s.t, tr.entry.t), c = Math.min(tEnd, i + 1 < steps.length ? steps[i + 1].t : tEnd), vis = on && c > a;
      s.m.visible = vis;
      if (vis) { const y1 = this.Y(s.px), x0 = this.X(a), x1 = this.X(c); s.m.position.set((x0 + x1) / 2, (yE + y1) / 2, 0); s.m.scale.set(Math.max(0.01, x1 - x0), Math.max(0.01, Math.abs(y1 - yE)), dep); }
      const h = Tr.sp[i]; if (h) { this._setH(h.h, this.X(a), this.X(Math.max(a + 30, c)), this.Y(s.px), dep / 2 + 0.01, 0.03); h.h.visible = vis; }
    });
    Tr.vSteps.forEach((v, i) => { v.visible = on && T >= steps[i + 1].t; });
    if (Tr.reward) { const x0 = this.X(tr.entry.t), x1 = this.X(Math.max(tr.entry.t + 60, tEnd)), yT = this.Y(tr.target); Tr.reward.position.set((x0 + x1) / 2, (yE + yT) / 2, 0); Tr.reward.scale.set(x1 - x0, Math.max(0.01, Math.abs(yT - yE)), dep); }
    if (Tr.tgtLine) this._setH(Tr.tgtLine, this.X(tr.entry.t), this.X(Math.max(tr.entry.t + 60, tEnd)), this.Y(tr.target), dep / 2 + 0.01, 0.028);
    if (Tr.exM) Tr.exM.visible = !!Tr.ex && T >= Tr.ex.t;
    if (Tr.twin) Tr.twin.visible = !!Tr.ex && T >= Tr.ex.t;
    Tr.done = !!Tr.ex && T >= Tr.ex.t;
    Tr.it.el.classList.toggle('open', on && !Tr.done);
    if (Tr.setup) for (const p of Tr.setup.parts) { const v = T >= p.t && this.on(Tr.b); if (p.obj) p.obj.visible = v; if (p.lab) p.lab.gate = v; }
  }
  setLayers(L = {}) {
    this.layers = { ...this.layers, ...L, bots: { ...this.layers.bots, ...(L.bots || {}) } };
    this._applyLayers(); if (this.n) this.setTime(this.T); this.dirty = true;
  }
  _applyLayers() {
    const L = this.layers;
    this.G.fills.visible = L.fills; this.G.trades.visible = L.trades; this.G.setup.visible = L.setup && L.trades !== false; this.G.thoughts.visible = L.thoughts;
    this.G.orders.visible = L.orders; this.G.levels.visible = L.levels; this.G.struct.visible = L.structure; this.G.vol.visible = L.volume;
    for (const Tr of this.trades || []) if (Tr.setup) Tr.setup.g.visible = this.on(Tr.b);
  }

  // ------------------------------------------------------------------ camera
  _fitDist(winW, fov) { const asp = this.w / Math.max(1, this.h), tf = Math.tan(THREE.MathUtils.degToRad(fov / 2)); return Math.max(2, (winW * 0.5) / (tf * asp) * 1.08); }
  _winW() { return this.focusN * this.secs_ / 60 * DX; }
  _frameNow(instant) {
    const P = this.presetName === 'flat' ? { yaw: 0, pitch: 0.015, fov: 22 } : { yaw: this.phone ? -0.32 : -0.5, pitch: this.phone ? 0.2 : 0.3, fov: 38 };
    Object.assign(this.goal, P); this.goal.dist = this._fitDist(this._winW(), P.fov) * (this.presetName === 'flat' ? 1 : 0.92);
    this._followGoal();
    if (instant) Object.assign(this.cam, this.goal);
  }
  _followGoal() {
    if (!this.n) return;
    const T = Math.min(this.T, this.tEnd), W = this._winW(), xT = this.X(T);
    const tx = xT - W * 0.2;
    const t0 = this.tAt(tx - W / 2), t1 = T, b = this.bars();
    let lo = Infinity, hi = -Infinity;
    for (let i = Math.max(0, this.barAt(t0)); i <= Math.max(0, this.barAt(t1)) && i < b.length; i++) { lo = Math.min(lo, b[i][3]); hi = Math.max(hi, b[i][2]); }
    if (!isFinite(lo)) { lo = hi = b[0][4]; }
    this.goal.tx = tx; this.goal.ty = (this.Y(lo) + this.Y(hi)) / 2;
    const needH = (this.Y(hi) - this.Y(lo)) * 1.25 + 0.8, tf = Math.tan(THREE.MathUtils.degToRad(this.goal.fov / 2));
    if (this.mode === 'follow') this.goal.dist = Math.max(this.goal.dist0 || 0, this._fitDist(W, this.goal.fov) * (this.presetName === 'flat' ? 1 : 0.92), needH / (2 * tf));
  }
  preset(name) {
    this.presetName = name === 'flat' ? 'flat' : name === 'fly' ? 'fly' : '3d';
    if (this.presetName === 'fly') {
      if (Q.reduced) { this.presetName = '3d'; this._frameNow(false); return; }
      this.fly = { age: 0, dur: 26, from: this.X(this.t0 + 3600), to: this.X(Math.min(this.T, this.tEnd)) };
      this.mode = 'fly'; return;
    }
    this.fly = null; this.mode = 'follow'; this._frameNow(false);
  }
  follow(on = true) { this.mode = on ? 'follow' : 'free'; if (on) this._frameNow(false); }
  focus(kind, id, o = {}) {
    let x = null, y = null;
    if (kind === 'fill') { const F = this.fills.find((q) => q.f.id === id); if (F) { x = this.X(F.f.t); y = this.Y(F.f.px); this._focusIt = F.it; } }
    let wTr = 0;
    if (kind === 'trade') { const Tr = this.trades.find((q) => q.tr.id === id); if (Tr) { const cap = (this.phone ? 70 : 240) * 60, t0 = Tr.tr.setup && ok(Tr.tr.setup.t_sweep) ? Math.max(Tr.tr.setup.t_sweep - 600, Tr.tr.entry.t - cap / 2) : Tr.tr.entry.t - 900, t1 = Math.min(Tr.ex ? Tr.ex.t : Tr.tr.entry.t + 1800, t0 + cap);
      x = (this.X(t0) + this.X(t1)) / 2; wTr = this.X(t1) - this.X(t0) + 1.2;
      const b = this.bars(); let lo = Infinity, hi = -Infinity; for (let i = Math.max(0, this.barAt(t0)); i <= Math.max(0, this.barAt(t1)) && i < b.length; i++) { lo = Math.min(lo, b[i][3]); hi = Math.max(hi, b[i][2]); }
      const yl = Math.min(this.Y(lo), Tr.loY), yh = Math.max(this.Y(hi), this.phone ? Math.min(Tr.hiY, this.Y(hi) + 2) : Tr.hiY); y = (yl + yh) / 2; this._trH = yh - yl; this._focusIt = Tr.it; } }
    if (kind === 'thought') { const th = this.thoughts.find((q) => q.id === id); if (th) { x = th.g.position.x; y = th.g.position.y + 0.4; this._focusIt = th.it; } }
    if (x == null) return false;
    if (o.keepCam) { for (const it of this.items) it.el.classList.toggle('focus', it === this._focusIt); this.dirty = true; return true; }
    this.mode = 'free'; this.fly = null;
    Object.assign(this.goal, { tx: x, ty: y, dist: kind === 'trade' ? Math.max(3, this._fitDist(this._winW(), this.goal.fov) * 0.55) : (this.phone ? 3.4 : 3.8), yaw: this.presetName === 'flat' ? 0 : -0.38, pitch: this.presetName === 'flat' ? 0.02 : 0.2 });
    // phone: the detail card covers the lower part of the stage, so the picked fill / thought sits in the upper part
    if (this.phone && kind !== 'trade') this.goal.ty = y - this.goal.dist * Math.tan(THREE.MathUtils.degToRad(this.goal.fov / 2)) * 0.5;
    if (kind === 'trade') this.goal.dist = Math.max(3, this._fitDist(wTr, this.goal.fov) * 0.9, (this._trH || 1) * 1.25 / (2 * Math.tan(THREE.MathUtils.degToRad(this.goal.fov / 2))));
    for (const it of this.items) it.el.classList.toggle('focus', it === this._focusIt && !o.quiet);
    this.dirty = true; return true;
  }
  _bindInput() {
    const c = this.canvas; c.style.touchAction = 'none';
    const P = new Map(); let pinch = null, down = null;
    const user = () => { if (this.mode !== 'free') { this.mode = 'free'; this.fly = null; this.opts.onCam?.(); } };
    c.addEventListener('contextmenu', (e) => e.preventDefault());
    c.addEventListener('pointerdown', (e) => {
      c.setPointerCapture?.(e.pointerId); P.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (P.size === 1) down = { x: e.clientX, y: e.clientY, t: performance.now(), b: e.button, sh: e.shiftKey, touch: e.pointerType !== 'mouse' };
      if (P.size === 2) { const [a, b] = [...P.values()]; pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, dist: this.goal.dist, yaw: this.goal.yaw }; down = null; }
    });
    c.addEventListener('pointermove', (e) => {
      const p = P.get(e.pointerId); if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y; p.x = e.clientX; p.y = e.clientY;
      if (pinch && P.size === 2) {
        const [a, b] = [...P.values()], d = Math.hypot(a.x - b.x, a.y - b.y), cx = (a.x + b.x) / 2;
        this.goal.dist = Math.max(1.2, Math.min(80, pinch.dist * pinch.d / Math.max(20, d)));
        this.goal.yaw = pinch.yaw - (cx - pinch.cx) * 0.006; user(); return;
      }
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) < 4) return;
      user();
      const k = this.cam.dist / Math.max(200, this.h) * 1.1;
      if (down.touch || down.b === 2 || down.sh) {           // pan in time (and price); a finger's vertical move tilts
        this.goal.tx -= dx * k * Math.cos(this.cam.yaw); this.goal.tx = Math.max(this.X(this.t0) - 4, Math.min(this.X(this.tEnd) + 4, this.goal.tx));
        if (down.touch) this.goal.pitch = Math.max(0, Math.min(1.1, this.goal.pitch + dy * 0.004)); else this.goal.ty += dy * k;
      } else { this.goal.yaw -= dx * 0.005; this.goal.pitch = Math.max(-0.05, Math.min(1.2, this.goal.pitch + dy * 0.004)); }
    });
    const up = (e) => {
      const was = P.get(e.pointerId); P.delete(e.pointerId);
      if (P.size < 2) pinch = null;
      if (down && was && e.type === 'pointerup' && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 8 && performance.now() - down.t < 450) this._pick(e);
      if (!P.size) down = null;
    };
    c.addEventListener('pointerup', up); c.addEventListener('pointercancel', up);
    c.addEventListener('wheel', (e) => { e.preventDefault(); user(); this.goal.dist = Math.max(1.2, Math.min(80, this.goal.dist * Math.exp(e.deltaY * 0.0012))); }, { passive: false });
  }
  _pick(e) {
    const r = this.canvas.getBoundingClientRect(), v = new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    const ray = this._ray || (this._ray = new THREE.Raycaster()); ray.setFromCamera(v, this.camera);
    const objs = [];
    for (const F of this.fills) if (F.g.visible && F.shown && this.layers.fills) objs.push(F.orb);
    for (const th of this.thoughts) if (th.g.visible && this.layers.thoughts) objs.push(th.dia);
    for (const Tr of this.trades) if (Tr.g.visible && this.layers.trades) { for (const s of Tr.risk) objs.push(s.m); if (Tr.reward) objs.push(Tr.reward); if (Tr.exM) objs.push(Tr.exM); }
    // small things first: fills and thoughts win over the trade boxes around them
    const hit = ray.intersectObjects(objs, false).sort((a, b) => (a.object.userData.pick?.kind === 'trade') - (b.object.userData.pick?.kind === 'trade') || a.distance - b.distance)[0];
    const pk = hit?.object.userData.pick;
    if (pk) this.opts.onPick?.(pk.kind, pk.id, pk.kind === 'fill' ? this.fills.find((q) => q.f.id === pk.id)?.f : pk.kind === 'trade' ? this.trades.find((q) => q.tr.id === pk.id)?.tr : this.thoughts.find((q) => q.id === pk.id)?.th);
    else this.opts.onPick?.(null, null, null);
  }

  // ------------------------------------------------------------------ frame
  update(t, dt) {
    const C = this.cam, G = this.goal;
    if (this.n) {
      if (this.mode === 'follow') this._followGoal();
      if (this.mode === 'fly' && this.fly) {
        const F = this.fly; F.age += dt; const u = Math.min(1, F.age / F.dur), e = u * u * (3 - 2 * u);
        const x = F.from + (F.to - F.from) * e, tt = this.tAt(x), b = this.bars(), i = Math.max(0, this.barAt(tt));
        G.tx = x; G.ty = this.Y(b[i][4]); G.yaw = -0.9 + Math.sin(u * Math.PI * 2) * 0.55; G.pitch = 0.1 + Math.sin(u * Math.PI) * 0.32; G.fov = 44;
        G.dist = this._fitDist(this._winW(), 44) * (0.42 + 0.25 * Math.cos(u * Math.PI * 3) ** 2);
        if (u >= 1) { this.fly = null; this.presetName = '3d'; this.mode = 'follow'; this._frameNow(false); this.opts.onCam?.('fly-end'); }
      }
    }
    const k = Q.reduced ? 1 : Math.min(1, dt * (this.mode === 'fly' ? 2.2 : 4));
    let moved = false;
    for (const key of ['tx', 'ty', 'yaw', 'pitch', 'dist', 'fov']) { const d = G[key] - C[key]; if (Math.abs(d) > 1e-5) { C[key] += d * k; moved = true; } }
    if (moved || this.dirty) {
      const cp = Math.cos(C.pitch);
      this.camera.fov = C.fov; this.camera.updateProjectionMatrix();
      this.camera.position.set(C.tx + Math.sin(C.yaw) * cp * C.dist, C.ty + Math.sin(C.pitch) * C.dist, Math.cos(C.yaw) * cp * C.dist);
      this.camera.lookAt(C.tx, C.ty, 0);
      this.camera.updateMatrixWorld();
      // floor follows the low of the bars in view; the reflection mirrors around it
      const b = this.bars();
      if (b.length) {
        const W = this._winW(), i0 = Math.max(0, this.barAt(this.tAt(C.tx - W * 0.6))), i1 = Math.max(0, Math.min(this.barAt(Math.min(this.T, this.tAt(C.tx + W * 0.6))), b.length - 1));
        let lo = Infinity; for (let i = i0; i <= i1; i++) lo = Math.min(lo, b[i][3]);
        if (isFinite(lo)) { const fy = this.Y(lo) - 0.55; this.floorY = this.floorY == null ? fy : this.floorY + (fy - this.floorY) * Math.min(1, dt * 3); }
      }
      const fy = this.floorY ?? -1;
      this.floor.position.y = fy; this.floorBase.position.y = fy - 0.002; this.G.vol.position.y = fy; this.G.mirror.position.y = 2 * fy;
      this.clipUp.constant = -fy; this.clipDn.constant = fy;
      this.fU.uT.value.set(C.tx, fy, 0); this.wU.uT.value.set(C.tx, C.ty, -2.2);
      this.wall.position.y = C.ty; this.floor.position.x = this.floorBase.position.x = this.wall.position.x = C.tx;
      this.l1.position.set(C.tx - 6, C.ty + 5, 5); this.l2.position.set(C.tx + 5, C.ty + 3, 4);
    }
    // the live / replay price line pulses; fills pop; the newest thought breathes
    if (this.n && this.price != null) {
      const W = this._winW(), y = this.Y(this.price), x1 = this.X(Math.min(this.T, this.tEnd)) + 0.5;
      this._setH(this.pxLine, x1 - W * 1.4, x1, y, 0.05, 0.02);
      const pul = Q.reduced ? 0.8 : 0.55 + 0.45 * Math.sin(t * 3.2);
      this.pxLine.material.opacity = 0.45 + 0.5 * pul; this.pxGlow.position.set(x1, y, 0.05); this.pxGlow.material.opacity = 0.5 + 0.5 * pul;
      const s = 0.45 + 0.25 * pul; this.pxGlow.scale.set(s, s, 1);
    }
    for (let i = this.pops.length - 1; i >= 0; i--) {
      const P = this.pops[i]; P.age += dt;
      const u = Math.min(1, P.age / 0.55), s = u < 1 ? 1 + 1.6 * Math.sin(u * Math.PI) * (1 - u) + (u < 0.15 ? -0.6 : 0) : 1;
      P.F.g.scale.setScalar(Math.max(0.2, s)); P.F.halo.material.opacity = P.F.real ? 0.9 + 1.5 * (1 - u) : 0.55 + (1 - u);
      if (u >= 1) { P.F.g.scale.setScalar(1); this.pops.splice(i, 1); }
    }
    for (const F of this.fills) {                // beams from the floor to the orb
      const fy = this.floorY ?? -1, y = F.g.position.y;
      F.beam.position.set(0, (fy - y) / 2, 0); F.beam.scale.set(0.012, Math.max(0.01, y - fy), 0.012);
      if (!Q.reduced && F.real) F.orb.rotation.y += dt;
      else if (!Q.reduced) F.orb.rotation.y -= dt * 0.6;
    }
    if (moved || this.dirty || this.pops.length || this.mode !== 'free') this._labels(t);
    this.dirty = false;
  }
  _labels(t) {
    const W = this.w, H = this.h, cam = this.camera, v = this._v || (this._v = new THREE.Vector3());
    const proj = (x, y, z) => { v.set(x, y, z).project(cam); return { x: (v.x * 0.5 + 0.5) * W, y: (-v.y * 0.5 + 0.5) * H, behind: v.z > 1 || v.z < -1 }; };
    const L = this.layers, T = this.T, shown = [];
    const C = this.cam, Wv = this._winW() * 0.75;
    // thoughts: of those in view (and already said by the replay time) the newest few keep a label, the very newest get the
    // full holographic panel (1 on a phone, 3 on the PC); the rest stay glowing diamonds in the scene
    const ta = this.tAt(C.tx - Wv * 1.6), tb = this.tAt(C.tx + Wv * 1.6);
    const inWin = this.thoughts.filter((x) => x.th.t <= T && x.th.t >= ta && x.th.t <= tb && this.on(x.b));
    const keep = new Set(inWin.slice(this.phone ? -6 : -14).map((x) => x.id)), full = new Set(inWin.slice(this.phone ? -1 : -3).map((x) => x.id));
    for (const x of this.thoughts) { x.it.gate = keep.has(x.id) || x.it === this._focusIt; x.it.el.classList.toggle('newest', full.has(x.id)); x.it.el.classList.toggle('old', !full.has(x.id)); }
    for (const it of this.items) {
      let vis = it.t <= T && (it.gate !== false);
      if (vis && it.layer && L[it.layer] === false) vis = false;
      if (vis && it.layer === 'setup' && (L.trades === false)) vis = false;
      if (vis && it.bot && !this.on(it.bot)) vis = false;
      if (vis && it.kind === 'order') { const O = this.orders.find((o) => o.it === it); vis = !!O && (O.working || it.el.classList.contains('focus')); }
      if (vis && it.kind === 'struct' && !L.structure) vis = false;
      if (vis) { const a = it.anchor; if (a.x < C.tx - Wv * 2.2 || a.x > C.tx + Wv * 2.2) vis = false; }
      if (!vis) { if (it.on !== false) { it.el.style.transform = 'translate(-9999px,0)'; it.el.style.visibility = 'hidden'; it.on = false; } continue; }
      const a = it.anchor, p = proj(a.x, a.y + (it.lift || 0), a.z);
      if (p.behind || p.x < -260 || p.x > W + 260 || p.y < -200 || p.y > H + 200) { if (it.on !== false) { it.el.style.transform = 'translate(-9999px,0)'; it.el.style.visibility = 'hidden'; it.on = false; } continue; }
      if (!it.w || it.el.dataset.m !== it.el.className) { it.w = it.el.offsetWidth || 80; it.h = it.el.offsetHeight || 18; it.el.dataset.m = it.el.className; }
      let x = a.clampR ? Math.min(W - it.w - 70, p.x + 6) : a.left ? p.x - it.w - 10 : a.fill ? p.x + 12 : p.x - it.w / 2, y = a.fill ? p.y - it.h / 2 : a.up ? p.y - it.h : p.y - it.h / 2;
      if (a.fill && x + it.w > W - 4) x = p.x - 12 - it.w;          // no room on the right: the card goes left of its orb
      const pri = it.pri + (it.el.classList.contains('focus') ? 10 : 0) + (it.el.classList.contains('newest') ? 1 : 0);
      shown.push({ it, x, y, pri });
    }
    // nudge apart: higher priority first, each moves up / down until it is free (or hides when it cannot be placed)
    shown.sort((a, b) => b.pri - a.pri);
    const res = this.opts.reserve?.() || [];
    const placed = res.map((r) => ({ x: r.x, y: r.y, it: { w: r.w, h: r.h } }));      // the page's HUD / legend / card
    // labels stay between the HUD row at the top and the legend row at the bottom
    const yTop = res.filter((r) => r.y < 24).reduce((m, r) => Math.max(m, r.y + r.h), 0) + 2, yBot = res.filter((r) => r.y > H - 90).reduce((m, r) => Math.min(m, r.y), H) - 2;
    const hit = (s) => placed.some((q) => s.x < q.x + q.it.w + 4 && s.x + s.it.w + 4 > q.x && s.y < q.y + q.it.h + 3 && s.y + s.it.h + 3 > q.y);
    for (const s of shown) {
      const y0 = s.y; let okP = !hit(s);
      for (let k = 1; !okP && k <= 6; k++) { s.y = y0 + (k % 2 ? -1 : 1) * Math.ceil(k / 2) * (s.it.h + 4); okP = !hit(s); }
      if (!okP && s.pri < 1.5) { s.y = y0; s.hide = true; }
      if (!okP && !s.hide) s.y = y0;
      if (!s.hide) placed.push(s);
    }
    for (const s of shown) {
      const el = s.it.el;
      if (s.hide) { if (s.it.on !== false) { el.style.transform = 'translate(-9999px,0)'; el.style.visibility = 'hidden'; s.it.on = false; } continue; }
      el.style.transform = `translate(${Math.round(Math.max(2, Math.min(W - 40, s.x)))}px,${Math.round(Math.max(yTop, Math.min(yBot - s.it.h, s.y)))}px)`;
      if (s.it.on !== true) { el.style.visibility = 'visible'; s.it.on = true; }
    }
    this._axes(proj);
    if (this.price != null) {
      const p = proj(this.X(Math.min(this.T, this.tEnd)) + 0.5, this.Y(this.price), 0.05);
      this.pxTag.textContent = fmtPx(this.price);
      this.pxTag.style.transform = `translate(${Math.round(Math.min(W - 78, Math.max(2, p.x + 8)))}px,${Math.round(Math.max(2, Math.min(H - 20, p.y - 10)))}px)`;
    }
  }
  _axes(proj) {
    if (!this.n) return;
    const C = this.cam, W = this.w, H = this.h;
    // price ticks across the band in view
    const pTop = this.pAt(C.ty + C.dist * Math.tan(THREE.MathUtils.degToRad(C.fov / 2))), pBot = this.pAt(C.ty - C.dist * Math.tan(THREE.MathUtils.degToRad(C.fov / 2)));
    const span = Math.abs(pTop - pBot) || 50, want = this.phone ? 5 : 7;
    const step = [1, 2, 5, 10, 25, 50, 100, 250, 500].find((s) => span / s <= want) || 1000;
    const p0 = Math.ceil(Math.min(pTop, pBot) / step) * step, out = [];
    for (let p = p0; p <= Math.max(pTop, pBot) && out.length < 14; p += step) {
      const q = proj(C.tx, this.Y(p), -2.2);
      if (q.y > 18 && q.y < H - 26 && !q.behind) out.push(`<span style="transform:translate(0,${Math.round(q.y - 8)}px)">${p.toLocaleString('en-US')}</span>`);
    }
    const kY = out.join('');
    if (kY !== this._kY) { this.axY.innerHTML = kY; this._kY = kY; }
    this.wU.uSY.value = step * this.ys; this.wU.uOY.value = this.Y(p0);
    // time ticks along the floor
    const Wv = this._winW(), fy0 = this.floorY ?? 0, gap = this.phone ? 62 : 74;
    const px1 = (m) => { const a = proj(C.tx, fy0, 1.2), c = proj(C.tx + m * DX, fy0, 1.2); return Math.hypot(c.x - a.x, c.y - a.y); };
    const tstep = [5, 10, 15, 30, 60, 120, 240].find((s) => px1(s) >= gap) || 480;
    const spanX = Math.max(Wv, C.dist * 1.6);
    const ta = this.tAt(C.tx - spanX * 1.2), tb = this.tAt(C.tx + spanX * 1.2), ts = tstep * 60, xs = [];
    for (let t = Math.ceil(ta / ts) * ts; t <= tb && xs.length < 24; t += ts) {
      if (t < this.t0 || t > this.tEnd) continue;
      const q = proj(this.X(t), this.floorY ?? 0, 1.2);
      if (q.x > 10 && q.x < W - 50 && !q.behind && q.y < H + 10) xs.push(`<span style="transform:translate(${Math.round(q.x - 18)}px,${Math.round(Math.min(H - 18, q.y + 4))}px)">${etHM(t)}</span>`);
    }
    const kX = xs.join('');
    if (kX !== this._kX) { this.axX.innerHTML = kX; this._kX = kX; }
    this.fU.uSX.value = this.wU.uSX.value = ts / 60 * DX;
  }
  stats() {
    const i = this.renderer.info.render, R = this.st.ring || [], q = (k, p) => { const a = R.map((x) => k < 0 ? x[0] + x[1] : x[k]).sort((m, n) => m - n); return a.length ? +a[Math.min(a.length - 1, Math.floor(a.length * p))].toFixed(2) : 0; };
    return { frames: this.st.frames, ms: +this.st.ms.toFixed(2), msAvg: +this.st.msAvg.toFixed(2), p50: q(-1, 0.5), p95: q(-1, 0.95), update50: q(0, 0.5), render50: q(1, 0.5), fps: this.st.fps, calls: i.calls, tris: i.triangles, dpr: this.renderer.getPixelRatio(), lite: this.lite, bloom: this.rc.passes().includes('bloom'), passes: this.rc.passes().length, tier: this.rc.quality() }; }
  counts() {
    const T = this.T;
    return { bars: this.n, barsShown: this.wk ? this.wk.count : 0, fills: this.fills.length, fillsShown: this.fills.filter((F) => F.f.t <= T && F.g.visible).length, trades: this.trades.length,
      tradesShown: this.trades.filter((x) => x.g.visible).length, thoughts: this.thoughts.length, thoughtsShown: this.thoughts.filter((x) => x.th.t <= T).length, orders: this.orders.length,
      ordersWorking: this.orders.filter((o) => o.working).length, levels: this.levels.length, setups: this.trades.filter((x) => x.setup).length, T, mode: this.mode, preset: this.presetName };
  }
  dispose() { document.removeEventListener('visibilitychange', this._vis); cancelAnimationFrame(this._raf); this._clear(); this.ov.remove(); super.dispose(); }
}
