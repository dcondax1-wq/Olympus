// OLYMPUS Mind: the ambient layers of the 3D view.
//   sky   a nebula sky on a sphere that follows the camera (three soft colours, slow drift, a brighter band like a galaxy's
//         plane), drawn first; dimmed in the constellation view. One cheap shader: a few sines, no texture, no loop.
//   dust  drifting motes around the brain (wrapped in a box, twinkling, fading at the box's edge); none moving under reduced motion.
//   const a = new Ambient(THREE, uniforms, {quality, reduced}); a.sky / a.dust -> THREE objects (the Brain adds them)
//   a.rebuild(quality) -> new dust; a.fit(centre, extent); a.follow(camera); a.colours(sky3, base); a.show({sky, dust})
const SKY_VS = `
varying vec3 vDir;
void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

const SKY_FS = `
uniform vec3 uA, uB, uC, uBase;
uniform float uTime, uStar, uAmt, uMotion;
varying vec3 vDir;
float w(vec3 p) { return sin(p.x * 1.9 + sin(p.y * 2.7 + uTime * 0.03 * uMotion)) * sin(p.y * 1.5 + sin(p.z * 2.1)) * sin(p.z * 1.7 + sin(p.x * 2.3)); }
void main() {
  vec3 d = normalize(vDir);
  float a = w(d * 1.4) * 0.5 + 0.5, b = w(d * 2.6 + 3.7) * 0.5 + 0.5, c = w(d * 5.2 + 8.1) * 0.5 + 0.5;
  float band = exp(-pow(d.y * 1.8, 2.0));
  vec3 col = uBase + uA * pow(a, 3.0) * 0.45 + uB * pow(b, 3.4) * 0.4 * (0.4 + band) + uC * pow(c * a, 2.4) * 0.38;
  col *= uAmt * (1.0 - 0.6 * uStar);
  gl_FragColor = vec4(col, 1.0);
}`;

const DUST_VS = `
attribute vec3 aSeed; attribute float aSize;
uniform float uTime, uScale, uMotion, uStar, uBox;
uniform vec3 uCentre, uTint;
varying vec3 vColor; varying float vA;
void main() {
  vec3 p = fract(aSeed + vec3(0.013, 0.021, 0.009) * uTime * uMotion * (0.5 + aSeed.zxy)) - 0.5;
  vec4 mv = modelViewMatrix * vec4(uCentre + p * uBox, 1.0);
  float dist = max(1.0, -mv.z);
  gl_PointSize = clamp(aSize * uScale / dist, 1.0, 14.0);
  float tw = 0.5 + 0.5 * sin(uTime * uMotion * (0.6 + aSeed.x * 1.4) + aSeed.y * 40.0);
  float edge = 1.0 - smoothstep(0.36, 0.5, max(max(abs(p.x), abs(p.y)), abs(p.z)));
  vA = (0.3 + 0.7 * tw) * edge * (1.0 - 0.6 * uStar);
  vColor = mix(uTint, vec3(1.0), aSeed.z * 0.55);
  gl_Position = projectionMatrix * mv;
}`;
const DUST_FS = `
varying vec3 vColor; varying float vA;
void main() { vec2 p = gl_PointCoord * 2.0 - 1.0; float r2 = dot(p, p); if (r2 > 1.0) discard; gl_FragColor = vec4(vColor, exp(-r2 * 4.0) * vA * 0.7); }`;

export class Ambient {
  constructor(THREE, u, { quality = 'high', reduced = false } = {}) {
    this.T = THREE;
    this.u = u;
    this.reduced = reduced;
    this.dustU = { uBox: { value: 600 }, uCentre: { value: new THREE.Vector3() }, uTint: { value: new THREE.Color() } };
    this.skyU = {
      uTime: u.uTime, uStar: u.uStar, uMotion: u.uMotion,
      uA: { value: new THREE.Color() }, uB: { value: new THREE.Color() }, uC: { value: new THREE.Color() },
      uBase: { value: new THREE.Color() }, uAmt: { value: 0.62 },
    };
    this.colours(['#3a2c3e', '#5a3a2a', '#6b4a28'], '#14110e');
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(6000, 24, 16), new THREE.ShaderMaterial({
      uniforms: this.skyU, vertexShader: SKY_VS, fragmentShader: SKY_FS, side: THREE.BackSide, depthWrite: false, depthTest: false,
    }));
    this.dust = null;
    this.rebuild(quality);
  }

  /** New dust for a quality level (high: 1,100 motes, light: 320). Returns the Points (the Brain swaps it in). */
  rebuild(quality) {
    const T = this.T, n = quality === 'high' ? 1100 : 320, seed = new Float32Array(n * 3), size = new Float32Array(n);
    let s = 4242;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < n; i++) { seed.set([rnd(), rnd(), rnd()], i * 3); size[i] = 0.5 + rnd() * rnd() * 2.2; }
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(new Float32Array(n * 3), 3));        // the shader places them; this only counts
    g.setAttribute('aSeed', new T.BufferAttribute(seed, 3));
    g.setAttribute('aSize', new T.BufferAttribute(size, 1));
    const mat = new T.ShaderMaterial({
      uniforms: { ...this.u, ...this.dustU }, vertexShader: DUST_VS, fragmentShader: DUST_FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
    });
    const keep = this.dust ? this.dust.visible : true;
    this.dust = new T.Points(g, mat);
    this.dust.visible = keep;
    return this.dust;
  }

  fit(centre, extent) {
    this.dustU.uCentre.value.copy(centre);
    this.dustU.uBox.value = Math.max(400, extent * 3.2);
  }

  follow(camera) { this.sky.position.copy(camera.position); }

  /** The sky's three colours and the page colour, as the screen colours they are written in (no colour-space conversion). */
  colours(sky, base) {
    const T = this.T, raw = (c, hex) => c.setHex(parseInt(String(hex).replace('#', ''), 16), T.LinearSRGBColorSpace);
    try {
      raw(this.skyU.uA.value, sky[0]); raw(this.skyU.uB.value, sky[1]); raw(this.skyU.uC.value, sky[2]);
      raw(this.dustU.uTint.value, sky[2]).lerp(new T.Color(1, 1, 1), 0.55);
      if (base) raw(this.skyU.uBase.value, base);
    } catch (_) { /* a bad colour: keep the last */ }
  }

  show({ sky, dust }) {
    if (typeof sky === 'boolean') this.sky.visible = sky;
    if (typeof dust === 'boolean' && this.dust) this.dust.visible = dust;
  }
}
