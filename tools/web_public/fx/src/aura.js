// Card auras: the background canvas also draws, behind each glass card on screen, a soft drifting glow and a stream
// of rising motes (green behind winning trades, magenta-violet behind the hero, accent colours behind stats and tiles).
// All in one draw call: card rects go to the GPU as uniforms, every mote finds its card by index and animates itself.
import { THREE, Q, theme, count, rng } from './core.js';

const MAXR = 32;
const AURA_V = `attribute float aIdx; attribute vec4 aSeed; attribute float aKind;
uniform vec4 uR[${MAXR}]; uniform vec4 uC[${MAXR}]; uniform vec2 uView; uniform float uDpr; uniform float uTime; uniform float uSpeed;
varying vec3 vColor; varying float vAlpha; varying float vKind;
void main(){
  int i = int(aIdx + 0.5); vec4 r = uR[i]; vec4 c = uC[i];
  vec2 p; float size; float a;
  if (aKind > 0.5) {
    p = r.xy + r.zw * vec2(0.5 + 0.34 * sin(uTime * 0.21 + aSeed.x * 6.28), 0.5 + 0.3 * cos(uTime * 0.17 + aSeed.y * 6.28));
    size = min(min(r.z, r.w) * 1.2, 340.0); a = 0.3 * clamp(c.a * 2.0, 0.0, 1.0);
  } else {
    float life = fract(aSeed.y + uTime * uSpeed * (0.03 + aSeed.z * 0.05));
    p = vec2(r.x + r.z * (0.04 + 0.92 * aSeed.x) + sin(uTime * (0.5 + aSeed.z) + aSeed.y * 30.0) * 6.0, r.y + r.w * (1.0 - life));
    size = 1.8 + aSeed.z * aSeed.z * 5.2;
    a = smoothstep(0.0, 0.14, life) * (1.0 - smoothstep(0.62, 1.0, life)) * (0.55 + 0.45 * sin(uTime * 2.6 + aSeed.x * 50.0)) * step(aSeed.w, c.a);
  }
  a *= step(4.0, r.z);
  gl_Position = vec4(p.x / uView.x * 2.0 - 1.0, 1.0 - p.y / uView.y * 2.0, 0.0, 1.0);
  gl_PointSize = size * uDpr;
  vColor = c.rgb; vAlpha = a; vKind = aKind;
}`;
const AURA_F = `varying vec3 vColor; varying float vAlpha; varying float vKind;
void main(){ if (vAlpha < 0.004) discard; vec2 q = gl_PointCoord - 0.5; float d = dot(q, q) * 4.0; if (d > 1.0) discard;
  float a = vKind > 0.5 ? exp(-d * 3.4) * (1.0 - d) : (1.0 - d) * (1.0 - d) * 0.6 + exp(-d * 16.0) * 0.9;
  gl_FragColor = vec4(vColor * a * vAlpha, 1.0); }`;

// what gets an aura, strongest first: [selector, colour, mote density 0..1]
const RULES = [
  ['.hero-card, .nx-oracle-t', 'hero', 1],
  ['.stat, .nx-stat, .kpi', 'cycle', 0.8],
  ['.tabs a.on, .nx-tab.on', 'accent', 1],
  ['.tile, .nx-tile', 'cycle', 0.65],
  ['.trade.win, .nx-trade.win', 'good', 0.55],
  ['.trade.loss, .nx-trade.loss', 'bad', 0.22],
  ['.lesson, .study .card, .evgrid > div', 'violet', 0.4],
  ['.card, .nx-card', 'card', 0.3],
];
const SEL = RULES.map(r => r[0]).join(', ');

export class Aura {
  constructor() {
    this.scene = new THREE.Scene(); this.cam = new THREE.Camera();
    const per = count(26, 12), N = MAXR * (per + 1), R = rng(29);
    const aIdx = new Float32Array(N), aSeed = new Float32Array(N * 4), aKind = new Float32Array(N);
    let k = 0;
    for (let i = 0; i < MAXR; i++) {
      aIdx[k] = i; aKind[k] = 1; aSeed.set([R(), R(), R(), 0], k * 4); k++;
      for (let j = 0; j < per; j++, k++) { aIdx[k] = i; aSeed.set([R(), R(), R(), (j + 0.5) / per], k * 4); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    g.setAttribute('aIdx', new THREE.BufferAttribute(aIdx, 1)); g.setAttribute('aSeed', new THREE.BufferAttribute(aSeed, 4)); g.setAttribute('aKind', new THREE.BufferAttribute(aKind, 1));
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e6);
    this.U = { uR: { value: Array.from({ length: MAXR }, () => new THREE.Vector4()) }, uC: { value: Array.from({ length: MAXR }, () => new THREE.Vector4()) },
      uView: { value: new THREE.Vector2(1, 1) }, uDpr: { value: 1 }, uTime: { value: 0 }, uSpeed: { value: 1 } };
    const pts = new THREE.Points(g, new THREE.ShaderMaterial({ uniforms: this.U, vertexShader: AURA_V, fragmentShader: AURA_F, transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending }));
    pts.frustumCulled = false; this.scene.add(pts);
    this.slots = Array.from({ length: MAXR }, () => ({ el: null, fade: 0, want: 0, col: new THREE.Color(), dens: 0, cut: null }));
    this.scanT = 0; this.active = true; this.speed = 1;
  }
  // pick the cards on screen (every few frames); keep each card in the same slot so its motes do not jump
  scan(vh) {
    const found = [];
    let n = 0;
    for (const el of document.querySelectorAll(SEL)) {
      if (++n > 900) break;
      const r = el.getBoundingClientRect();
      if (r.bottom < -40 || r.top > vh + 40 || r.width < 40 || r.height < 30) continue;
      if (el.closest('.sheet, .modal, .menu, .dd-pop') || el.querySelector('.fx3d')) continue;
      const pri = RULES.findIndex(x => el.matches(x[0]));
      if (pri < 0) continue;
      // nested: a stat or trade inside a card already lights that part; keep the card faint
      found.push({ el, pri, area: r.width * r.height });
    }
    found.sort((a, b) => a.pri - b.pri || b.area - a.area);
    const keep = new Set(found.slice(0, MAXR).map(f => f.el));
    for (const s of this.slots) if (s.el && !keep.has(s.el)) s.want = 0;
    let ci = 0;
    for (const f of found.slice(0, MAXR)) {
      let s = this.slots.find(x => x.el === f.el);
      if (!s) { s = this.slots.find(x => !x.el) || this.slots.find(x => x.want === 0 && x.fade < 0.05); if (!s) continue; s.el = f.el; s.fade = 0; }
      const rule = RULES[f.pri];
      s.want = 1; s.dens = rule[2] * (f.el.closest('.card') && f.el.closest('.card') !== f.el ? 0.7 : 1);
      s.cut = f.el.querySelector(':scope > .hero3d');
      const pal = [theme.accent, theme.accent2, theme.violet, theme.magenta];
      s.col.copy(rule[1] === 'hero' ? theme.magenta : rule[1] === 'accent' ? theme.accent : rule[1] === 'good' ? theme.good : rule[1] === 'bad' ? theme.bad : rule[1] === 'violet' ? theme.violet
        : rule[1] === 'card' ? theme.violet : pal[ci++ % pal.length]);
      if (f.el.querySelector('b.up, .up b')) s.col.lerp(theme.good, 0.45);
      else if (f.el.querySelector('b.dn, .dn b')) s.col.lerp(theme.bad, 0.4);
    }
  }
  step(t, dt, w, h, dpr) {
    this.scanT -= dt;
    if (this.scanT <= 0) { this.scan(h); this.scanT = 0.4; }
    const U = this.U; U.uTime.value = t; U.uView.value.set(w, h); U.uDpr.value = dpr; U.uSpeed.value = this.speed;
    let any = false;
    this.slots.forEach((s, i) => {
      s.fade += (s.want - s.fade) * Math.min(1, dt * (s.want ? 1.6 : 4));
      const R = U.uR.value[i], C = U.uC.value[i];
      if (!s.el || !s.el.isConnected || s.fade < 0.01) { if (s.want === 0 || !s.el?.isConnected) { s.el = null; s.want = 0; } R.set(0, 0, 0, 0); C.set(0, 0, 0, 0); return; }
      const r = s.el.getBoundingClientRect();
      let top = r.top; if (s.cut) top = Math.max(top, s.cut.getBoundingClientRect().bottom);
      R.set(r.left, top, r.width, Math.max(0, r.bottom - top)); C.set(s.col.r, s.col.g, s.col.b, s.dens * s.fade);
      any = true;
    });
    return any;
  }
  dispose() { this.scene.traverse(o => { o.geometry?.dispose?.(); o.material?.dispose?.(); }); }
}
