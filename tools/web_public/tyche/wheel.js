// TYCHE wheel: the golden Wheel of Fortune and the open bets orbiting it as coins.
// One coin per open bet:
//   height above the wheel = the bot's edge (its chance - the price), +10¢ = HEIGHT_PER_EDGE * 0.10 units; no `prob` = on the
//   wheel's plane, dimmed; size = the stake (cost); colour = the market category; spin = time to settlement (faster as it
//   nears); the halo ring = the Kelly stake at the chosen fraction (bigger than the coin = the bot bets under Kelly).
import { kellyStake } from './data.js';

export const HEIGHT_PER_EDGE = 22;
const WHEEL_R = 3;
const LANES = [3.75, 4.45, 5.15];
const GOLD = '#ffcf5a', MINT = '#5ef2c0';

/** Spin (rad/s) from the seconds left: a blur in the last minutes, a slow turn for bets days away. */
export const spinOf = (left) => (left == null ? 0.4 : left <= 0 ? 9 : 0.35 + 6 * Math.exp(-left / 2400) + 1.2 * Math.exp(-left / 43200));

export class Wheel {
  constructor(THREE, glow, opts = {}) {
    this.T = THREE;
    this.glow = glow;
    this.group = new THREE.Group();
    this.wheel = new THREE.Group();
    this.group.add(this.wheel);
    this.coins = new Map();                       // key -> coin record
    this.hits = [];                               // invisible hit spheres for taps
    this.kellyFrac = 0.25;
    this.halos = true;
    this.selected = null;
    this.buildWheel(opts.lite);
    this.coinGeo = new THREE.CylinderGeometry(1, 1, 0.14, 40, 1);
    this.hitGeo = new THREE.SphereGeometry(1, 8, 6);
    this.hitMat = new THREE.MeshBasicMaterial({ visible: false });
    // the stems: one segment per coin from the wheel's plane to the coin (reads its edge as a height)
    const sg = new THREE.BufferGeometry();
    sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(60 * 6), 3));
    sg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(60 * 6), 3));
    this.stems = new THREE.LineSegments(sg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.stems.frustumCulled = false;
    this.group.add(this.stems);
    // the edge rings: +5¢ and +10¢ above the plane
    this.levels = [0.05, 0.1].map((e) => {
      const pts = [];
      for (let i = 0; i <= 96; i++) { const a = (i / 96) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * 4.45, e * HEIGHT_PER_EDGE, Math.sin(a) * 4.45)); }
      const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineDashedMaterial({ color: MINT, dashSize: 0.18, gapSize: 0.22, transparent: true, opacity: 0.32, depthWrite: false }));
      l.computeLineDistances();
      this.group.add(l);
      return { e, line: l };
    });
  }

  buildWheel(lite) {
    const T = this.T, g = this.glow, w = this.wheel;
    const gold = g.coin(GOLD, { emissiveIntensity: 0.34, roughness: 0.26 });   // polished gold: the environment shines in it
    const rim = new T.Mesh(new T.TorusGeometry(WHEEL_R, 0.085, 14, lite ? 64 : 128), gold);
    rim.rotation.x = Math.PI / 2;
    w.add(rim);
    const outer = new T.Mesh(new T.TorusGeometry(WHEEL_R + 0.24, 0.022, 8, lite ? 64 : 128), g.light(GOLD, 0.8));
    outer.rotation.x = Math.PI / 2;
    w.add(outer);
    const inner = new T.Mesh(new T.TorusGeometry(1.15, 0.045, 10, 64), gold);
    inner.rotation.x = Math.PI / 2;
    w.add(inner);
    // twelve segments, gold and mint by turns: the wheel's face
    for (let i = 0; i < 12; i++) {
      const seg = new T.Mesh(new T.RingGeometry(0.62, WHEEL_R - 0.06, 6, 1, (i / 12) * Math.PI * 2, (Math.PI * 2) / 12 - 0.02),
        g.light(i % 2 ? MINT : GOLD, i % 2 ? 0.09 : 0.16, { side: T.DoubleSide }));
      seg.rotation.x = -Math.PI / 2;
      w.add(seg);
    }
    const spokeGeo = new T.CylinderGeometry(0.028, 0.028, WHEEL_R - 0.5, 6);
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2, s = new T.Mesh(spokeGeo, gold);
      s.position.set(Math.cos(a) * (WHEEL_R / 2 + 0.25), 0, Math.sin(a) * (WHEEL_R / 2 + 0.25));
      s.rotation.z = Math.PI / 2;
      s.rotation.y = -a;
      w.add(s);
    }
    const pegGeo = new T.SphereGeometry(0.075, 10, 8), pegMat = g.light('#fff1c4', 1);
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * Math.PI * 2, p = new T.Mesh(pegGeo, pegMat);
      p.position.set(Math.cos(a) * (WHEEL_R + 0.24), 0, Math.sin(a) * (WHEEL_R + 0.24));
      w.add(p);
    }
    const hub = new T.Mesh(new T.CylinderGeometry(0.55, 0.62, 0.28, 32), gold);
    w.add(hub);
    const cap = new T.Mesh(new T.SphereGeometry(0.32, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), g.metal('#fff0c0', 0.8));
    cap.position.y = 0.14;
    w.add(cap);
    const halo = g.sprite(GOLD, 3.4, 0.55);
    halo.position.y = 0.3;
    this.group.add(halo);
    const bloom = g.sprite(GOLD, 9.5, 0.12);
    this.group.add(bloom);
  }

  /** The open bets -> coins (kept by key, so a refresh does not restart their orbits). */
  setModel(model, colors) {
    const T = this.T, g = this.glow, open = model ? model.open.slice().sort((a, b) => (a.closes || 9e12) - (b.closes || 9e12)) : [];
    this.model = model;
    const maxCost = Math.max(1, ...open.map((o) => o.cost || 0));
    const keep = new Set(open.map((o) => o.key));
    this.coins.forEach((c, k) => { if (!keep.has(k)) this.removeCoin(c); });
    open.forEach((o, i) => {
      let c = this.coins.get(o.key);
      const color = colors.get(o.category) || GOLD;
      if (!c) {
        const side = g.coin(color, { bumpMap: g.reeds, bumpScale: 2.5 }), face = g.coin(color, { map: g.face, bumpMap: g.face, bumpScale: 1.6, roughness: 0.26 });   // minted: reeded edge, embossed face
        const mesh = new T.Mesh(this.coinGeo, [side, face, face]);
        const aura = g.sprite(color, 1, 0.5);
        const halo = g.sprite('#fff4d6', 1, 0.75, g.ring);
        const hit = new T.Mesh(this.hitGeo, this.hitMat);
        hit.userData.key = o.key;
        c = { key: o.key, mesh, aura, halo, hit, phase: i * 2.39996, angle: 0, spin: Math.random() * 6, y: 0 };
        this.group.add(mesh, aura, halo, hit);
        this.hits.push(hit);
        this.coins.set(o.key, c);
      }
      c.o = o;
      c.lane = i % LANES.length;
      c.r = 0.17 + 0.33 * Math.sqrt(Math.max(0, o.cost || 0) / maxCost);
      c.y = o.edge == null ? 0 : Math.max(-2.2, Math.min(3.3, o.edge * HEIGHT_PER_EDGE));
      c.color = color;
      c.mesh.material.forEach((m) => { m.color.set(color); m.emissive.set(color); m.opacity = o.edge == null ? 0.65 : 1; m.transparent = o.edge == null; });
      c.aura.material.color.set(color);
      c.mesh.scale.set(c.r, 1, c.r);
      c.hit.scale.setScalar(Math.max(0.5, c.r * 1.8));
      c.aura.scale.setScalar(c.r * 5.2);
    });
    this.setKelly(this.kellyFrac);
  }

  removeCoin(c) {
    this.group.remove(c.mesh, c.aura, c.halo, c.hit);
    c.mesh.material.forEach((m) => m.dispose());
    c.aura.material.dispose();
    c.halo.material.dispose();
    this.hits = this.hits.filter((h) => h !== c.hit);
    this.coins.delete(c.key);
  }

  /** The Kelly fraction (0.25 / 0.5 / 1): every halo is resized to that stake, capped at the max bet. */
  setKelly(frac) {
    this.kellyFrac = frac;
    const cfg = this.model ? this.model.kelly : null;
    this.coins.forEach((c) => {
      const o = c.o, k = kellyStake(o.prob, o.ref, frac, cfg);
      c.kelly = k;
      c.hasHalo = k.stake != null && !!o.cost;
      c.halo.visible = c.hasHalo && this.halos;
      if (!c.hasHalo) return;
      // area ~ stake: the halo's radius is the coin's times sqrt(Kelly stake / stake), kept on screen (x0.35 to x2.4);
      // no edge -> a small dim red ring
      const ratio = k.stake > 0 ? Math.sqrt(k.stake / o.cost) : 0.3;
      c.halo.scale.setScalar(c.r * 2.2 * Math.max(0.35, Math.min(2.4, ratio)));
      c.halo.material.color.set(k.stake > 0 ? '#fff4d6' : '#ff6b7f');
      c.halo.material.opacity = k.stake > 0 ? 0.7 : 0.4;
    });
  }

  select(key) { this.selected = key; }

  /** The Kelly halos belong to the Wheel view: hidden while the camera looks at the pools or the scales. */
  showHalos(on) {
    this.halos = on;
    this.coins.forEach((c) => { c.halo.visible = on && !!c.hasHalo; });
  }

  /** Move the coins: orbit, spin, the stems. `motion` false = still (reduced motion), placed where they are. */
  update(t, dt, now, motion) {
    if (motion) this.wheel.rotation.y += dt * 0.07;
    const pos = this.stems.geometry.attributes.position.array, col = this.stems.geometry.attributes.color.array;
    const tmp = new this.T.Color();
    let i = 0;
    this.coins.forEach((c) => {
      const o = c.o, left = o.closes != null ? o.closes - now : null, lane = LANES[c.lane];
      if (motion) {
        c.angle += dt * (0.11 - c.lane * 0.018);
        c.spin += dt * spinOf(left);
      }
      const a = c.phase + c.angle, x = Math.cos(a) * lane, z = Math.sin(a) * lane;
      const bob = motion ? Math.sin(t * 1.3 + c.phase) * 0.05 : 0;
      c.mesh.position.set(x, c.y + bob, z);
      c.mesh.rotation.set(Math.PI / 2, 0, 0);
      c.mesh.rotateZ(c.spin);
      c.aura.position.copy(c.mesh.position);
      c.halo.position.copy(c.mesh.position);
      c.hit.position.copy(c.mesh.position);
      const sel = this.selected === c.key, soon = left != null && left < 900;
      c.aura.material.opacity = (sel ? 0.95 : 0.45) + (soon && motion ? 0.25 * Math.sin(t * 8) : 0);
      if (i < 60) {
        pos.set([x, 0, z, x, c.y + bob, z], i * 6);
        tmp.set(c.color);
        col.set([tmp.r * 0.2, tmp.g * 0.2, tmp.b * 0.2, tmp.r, tmp.g, tmp.b], i * 6);
        i++;
      }
    });
    this.stems.geometry.setDrawRange(0, i * 2);
    this.stems.geometry.attributes.position.needsUpdate = true;
    this.stems.geometry.attributes.color.needsUpdate = true;
  }

  /** World anchors for the HUD's labels: a countdown on each coin (soonest first), the edge rings' names. */
  anchors(now, max) {
    const out = [];
    const coins = Array.from(this.coins.values()).sort((a, b) => (a.o.closes || 9e12) - (b.o.closes || 9e12));
    coins.slice(0, max).forEach((c) => {
      const p = c.mesh.position.clone();
      p.y += c.r + 0.28;
      out.push({ id: 'c:' + c.key, pos: p, kind: 'coin', key: c.key, left: c.o.closes != null ? c.o.closes - now : null, sel: this.selected === c.key });
    });
    this.levels.forEach((l) => out.push({ id: 'e:' + l.e, pos: new this.T.Vector3(-4.6, l.e * HEIGHT_PER_EDGE + 0.12, 0.6), kind: 'edge', text: `+${Math.round(l.e * 100)}¢ edge` }));
    return out;
  }
}
