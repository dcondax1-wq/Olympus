// TYCHE scene: the renderer, the camera's three views, the air (fog, drifting gold dust, the floor) and the three parts:
// the Wheel (open bets), the Pools (settled bets + the bankroll), the Scales (calibration + ROI by price).
// The camera fits each view to the band of screen the HUD leaves free (setBand), in portrait and landscape alike.
// Quality: 'high' (HD) or 'low' (LITE: lower resolution, fewer particles, no antialias). Reduced motion: still life.
import { Wheel } from './wheel.js';
import { Pools, FLOOR_Y } from './pools.js';
import { Scales, SCALES_X } from './scales.js';
import { Glow } from './glow.js';

export const BG = '#07060b';
const INTRO_S = 2.6;                 // the intro camera move, seconds
// each view: what the camera looks at, how much must fit (radius), its height angle and turn
export const VIEWS = {
  wheel: { target: [0, 0.1, 0.3], r: 5.8, elev: 0.48, yaw: 0 },
  pools: { target: [0, -3.7, 0.5], r: 5.5, elev: 0.3, yaw: 0 },
  scales: { target: [SCALES_X, -0.9, 0.9], r: 5.0, elev: 0.36, yaw: 0 },
};

export class FortuneScene {
  constructor(THREE, canvas, opts = {}) {
    this.T = THREE;
    this.canvas = canvas;
    this.quality = opts.quality === 'low' ? 'low' : 'high';
    this.reduced = !!opts.reduced;
    this.renderer = this.makeRenderer();
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(BG);
    this.scene.fog = new THREE.FogExp2(BG, 0.026);
    this.camera = new THREE.PerspectiveCamera(46, 1, 0.1, 140);
    this.glow = new Glow(THREE);
    this.view = 'wheel';
    this.userYaw = 0;
    this.zoom = 1;
    this.look = new THREE.Vector3(...VIEWS.wheel.target);
    this.eye = new THREE.Vector3(0, 6, 14);
    this.band = { top: 0, bottom: 0, left: 0, right: 0 };
    this.lights();
    this.environment();
    this.build();
    this.resize();
    this.snap = true;
    this.intro = this.reduced ? 1 : 0;
  }

  makeRenderer() {
    const T = this.T, hd = this.quality === 'high';
    const r = new T.WebGLRenderer({ canvas: this.canvas, antialias: hd, alpha: false, powerPreference: 'high-performance' });
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, hd ? 2 : 1.25));
    r.toneMapping = T.ACESFilmicToneMapping;
    r.toneMappingExposure = 1.1;
    return r;
  }

  lights() {
    const T = this.T;
    this.scene.add(new T.HemisphereLight('#fff1d0', '#120c1c', 1.5));
    const key = new T.DirectionalLight('#ffe2a0', 2.4);
    key.position.set(4, 10, 8);
    this.scene.add(key);
    const hub = new T.PointLight('#ffcf5a', 40, 16, 1.6);
    hub.position.set(0, 1.2, 0);
    this.scene.add(hub);
    const mint = new T.PointLight('#5ef2c0', 26, 18, 1.6);
    mint.position.set(-6, 2, 4);
    this.scene.add(mint);
    const scl = new T.PointLight('#ffe7b0', 30, 16, 1.6);
    scl.position.set(SCALES_X, 4, 4);
    this.scene.add(scl);
  }

  /** Reflections for the metals: a tiny room of gold, mint and warm-white light, blurred once into an environment map. */
  environment() {
    const T = this.T, room = new T.Scene(), box = new T.BoxGeometry(1, 1, 1);
    const panel = (c, x, y, z, s) => { const m = new T.Mesh(box, new T.MeshBasicMaterial({ color: c })); m.position.set(x, y, z); m.scale.set(...s); room.add(m); };
    room.background = new T.Color('#0c0a10');
    panel('#ffcf5a', 0, 6, 0, [10, 0.2, 10]);
    panel('#fff3d8', -6, 1, -2, [0.2, 4, 6]);
    panel('#5ef2c0', 6, 0, 2, [0.2, 3, 5]);
    panel('#ffa53d', 0, -1, -6, [8, 2, 0.2]);
    panel('#2a1c08', 0, -5, 0, [12, 0.2, 12]);
    // a ring of eight warm softboxes overhead and two cool strips: the coins and the wheel's gold catch moving highlights
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      panel(i % 2 ? '#fff6e0' : '#ffd88a', Math.cos(a) * 4.2, 4.4, Math.sin(a) * 4.2, [1.4, 0.12, 0.5]);
    }
    panel('#9ff7dc', -4.5, 2.5, 4.5, [0.12, 0.35, 5]);
    panel('#e8a8ff', 4.8, -0.5, -4, [0.12, 0.25, 4]);
    const pm = new T.PMREMGenerator(this.renderer);
    this.scene.environment = pm.fromScene(room, 0.04).texture;
    pm.dispose();
    box.dispose();
  }

  build() {
    const T = this.T, g = this.glow, lite = this.quality === 'low';
    this.wheel = new Wheel(T, g, { lite });
    this.pools = new Pools(T, g, { lite });
    this.scales = new Scales(T, g);
    this.scene.add(this.wheel.group, this.pools.group, this.scales.group);
    const floor = new T.Mesh(new T.CircleGeometry(30, 64), new T.MeshBasicMaterial({ map: g.floor, transparent: true, depthWrite: false, blending: T.AdditiveBlending }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(5, FLOOR_Y - 0.3, -1);
    this.scene.add(floor);
    this.dust = g.points(lite ? 380 : 1100, lite ? 0.09 : 0.07, 0.8);
    const p = this.dust.geometry.attributes.position.array, c = this.dust.geometry.attributes.color.array;
    const tones = ['#ffcf5a', '#5ef2c0', '#fff3cf', '#ffa53d'].map((x) => new T.Color(x));
    for (let i = 0; i < p.length / 3; i++) {
      p.set([-14 + Math.random() * 42, -8 + Math.random() * 17, -14 + Math.random() * 22], i * 3);
      const k = tones[i % 7 === 0 ? 1 : i % 5 === 0 ? 2 : i % 3 === 0 ? 3 : 0];
      c.set([k.r, k.g, k.b], i * 3);
    }
    this.scene.add(this.dust);
  }

  setQuality(q) {
    if (q === this.quality) return;
    this.quality = q;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, q === 'high' ? 2 : 1.25));
    this.dust.geometry.setDrawRange(0, q === 'high' ? Infinity : 380);
    this.pools.jet.geometry.setDrawRange(0, q === 'high' ? Infinity : 260);
    this.resize();
  }

  setModel(model, colors) {
    this.model = model;
    this.wheel.setModel(model, colors);
    this.pools.setModel(model, colors);
    this.scales.setModel(model);
  }

  setKelly(f) { this.wheel.setKelly(f); }
  select(key) { this.wheel.select(key); }

  setView(v, instant) {
    if (!VIEWS[v]) return;
    this.view = v;
    this.wheel.showHalos(v === 'wheel');
    this.userYaw = 0;
    this.zoom = 1;
    if (instant || this.reduced) this.snap = true;
  }

  /** The px the HUD covers on each side: the camera centres the view in the rest (and fits it there). */
  setBand(b) { this.band = { top: b.top || 0, bottom: b.bottom || 0, left: b.left || 0, right: b.right || 0 }; this.resize(); }

  resize() {
    const w = Math.max(1, this.canvas.clientWidth || window.innerWidth), h = Math.max(1, this.canvas.clientHeight || window.innerHeight);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    const b = this.band, dy = (b.top - b.bottom) / 2, dx = (b.left - b.right) / 2;   // the free band's centre off the screen's
    this.camera.setViewOffset(w, h, -dx, -dy, w, h);
    this.camera.updateProjectionMatrix();
    this.size = { w, h };
  }

  /** Where the camera wants to be for the view: far enough that the view's radius fits the free band, both ways. */
  goal() {
    const v = VIEWS[this.view], T = this.T, { w, h } = this.size;
    const b = this.band, bh = Math.max(120, h - b.top - b.bottom), bw = Math.max(120, w - b.left - b.right);
    const tan = Math.tan((this.camera.fov * Math.PI) / 360);
    const vf = 2 * Math.atan(tan * (bh / h)), hf = 2 * Math.atan(tan * (bw / h));
    const d = (v.r / Math.sin(Math.min(vf, hf) / 2)) * this.zoom;
    const yaw = v.yaw + this.userYaw, t = new T.Vector3(...v.target);
    return { look: t, eye: new T.Vector3(t.x + Math.sin(yaw) * Math.cos(v.elev) * d, t.y + Math.sin(v.elev) * d, t.z + Math.cos(yaw) * Math.cos(v.elev) * d) };
  }

  /** The intro (once, on the first frames with data): the camera starts high above the wheel, a quarter turn round, and
   *  glides down into the view in INTRO_S, eased. A drag or a pinch ends it at once; reduced motion skips it. */
  introMove(g, dt) {
    this.intro = Math.min(1, this.intro + dt / INTRO_S);
    const e = 1 - Math.pow(1 - this.intro, 3), off = 1 - e, T = this.T;
    const rel = g.eye.clone().sub(g.look), d = rel.length();
    const yaw = Math.atan2(rel.x, rel.z) + off * 1.35, elev = Math.asin(Math.max(-1, Math.min(1, rel.y / d))) + off * 0.62, dist = d * (1 + off * 0.9);
    this.eye.copy(new T.Vector3(g.look.x + Math.sin(yaw) * Math.cos(elev) * dist, g.look.y + Math.sin(elev) * dist, g.look.z + Math.cos(yaw) * Math.cos(elev) * dist));
    this.look.copy(g.look);
  }

  drag(dx) { this.intro = 1; this.userYaw = Math.max(-1.1, Math.min(1.1, this.userYaw - dx * 0.006)); }
  pinch(k) { this.intro = 1; this.zoom = Math.max(0.6, Math.min(1.5, this.zoom / k)); }
  reset() { this.userYaw = 0; this.zoom = 1; }

  /** A tap at client (x, y) -> the key of the coin under it, or null. The hit spheres are generous (a fingertip), so when
   *  several are under the finger the coin whose centre is nearest the tap's ray wins, not merely the front one. */
  pick(x, y) {
    const T = this.T, r = this.canvas.getBoundingClientRect();
    const ndc = new T.Vector2(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    const ray = new T.Raycaster();
    ray.setFromCamera(ndc, this.camera);
    const hits = ray.intersectObjects(this.wheel.hits, false);
    if (!hits.length) return null;
    const near = (h) => ray.ray.distanceToPoint(h.object.position) / h.object.scale.x;
    return hits.reduce((a, b) => (near(b) < near(a) ? b : a)).object.userData.key;
  }

  /** One frame: move everything, glide the camera, draw. `now` = unix s (countdowns), dt = s since the last frame. */
  frame(t, dt, now) {
    const motion = !this.reduced;
    this.wheel.update(t, dt, now, motion);
    this.pools.update(t, dt, motion);
    this.scales.update(t, dt, motion);
    if (motion) {
      const p = this.dust.geometry.attributes.position.array;
      for (let i = 1; i < p.length; i += 3) { p[i] += dt * 0.12; if (p[i] > 9) p[i] = -8; }
      this.dust.geometry.attributes.position.needsUpdate = true;
    }
    const g = this.goal(), k = this.snap ? 1 : 1 - Math.exp(-dt * 3.2);
    this.snap = false;
    this.eye.lerp(g.eye, k);
    this.look.lerp(g.look, k);
    if (this.intro < 1) this.introMove(g, dt);
    this.camera.position.copy(this.eye);
    this.camera.lookAt(this.look);
    this.renderer.render(this.scene, this.camera);
  }

  /** The labels for the HUD: every anchor of the parts, projected to client px; those behind the camera are dropped. */
  labels(now, maxCoins) {
    const list = [
      ...this.wheel.anchors(now, maxCoins).map((a) => ({ ...a, view: 'wheel' })),
      ...this.pools.anchors(this.model).map((a) => ({ ...a, view: 'pools' })),
      ...this.scales.anchors().map((a) => ({ ...a, view: 'scales' })),
    ];
    const { w, h } = this.size, out = [];
    this.camera.updateMatrixWorld();
    list.forEach((a) => {
      const v = a.pos.clone().project(this.camera);
      if (v.z > 1 || v.z < -1) return;
      out.push({ ...a, x: ((v.x + 1) / 2) * w, y: ((1 - v.y) / 2) * h });
    });
    return out;
  }
}
