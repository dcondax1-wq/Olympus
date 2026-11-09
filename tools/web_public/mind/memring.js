// OLYMPUS Mind: Jarvis's memory ring. Jarvis's memories (notes of kind "memory") sit on a tilted ring around "Me" at the
// centre (layout.js seats them); this layer draws the ring itself: a fine cyan band of slowly orbiting motes plus a soft
// glowing orbit line, centred on Me and sized to where the memories actually are. Two draw calls.
//   const ring = new MemoryRing(THREE, uniforms, quality); ring.group -> THREE.Group
//   ring.place(centre {x, y, z}, radius)  ring.visible(bool)
import { RING_NORMAL } from './layout.js';

export const RING_COLOUR = 0xc8a24a;

const MOTE_VS = `
attribute float aAngle, aSeed;
uniform float uTime, uMotion, uScale, uRadius;
varying float vA;
void main() {
  float a = aAngle + uTime * (0.05 + aSeed * 0.04) * uMotion;
  float wob = (aSeed - 0.5) * 0.09;
  vec3 p = vec3(cos(a) * (1.0 + wob), sin(a) * (1.0 + wob), (fract(aSeed * 7.3) - 0.5) * 0.05);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = clamp((1.0 + aSeed * 1.8) * uRadius * 0.04 * uScale / max(1.0, -mv.z), 1.0, 14.0);
  vA = 0.35 + 0.65 * (0.5 + 0.5 * sin(uTime * (1.0 + aSeed * 2.0) * uMotion + aSeed * 30.0));
  gl_Position = projectionMatrix * mv;
}`;
const MOTE_FS = `
uniform vec3 uColor; uniform float uStrength;
varying float vA;
void main() { vec2 p = gl_PointCoord * 2.0 - 1.0; float r2 = dot(p, p); if (r2 > 1.0) discard;
  gl_FragColor = vec4(uColor * 1.2 + exp(-r2 * 10.0) * 0.4, exp(-r2 * 4.0) * vA * 0.5 * uStrength); }`;
const LINE_VS = `varying float vT; attribute float aT; void main() { vT = aT; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const LINE_FS = `
uniform vec3 uColor; uniform float uTime, uMotion, uStrength;
varying float vT;
void main() { float run = 0.5 + 0.5 * sin(vT * 6.2832 * 3.0 - uTime * 0.8 * uMotion);
  gl_FragColor = vec4(uColor, (0.22 + 0.3 * run) * uStrength); }`;

export class MemoryRing {
  constructor(THREE, uniforms, quality = 'high') {
    const T = THREE, n = quality === 'high' ? 420 : 160, seg = 160;
    this.T = T;
    this.uRadius = { value: 60 };
    this.uStrength = { value: 1 };
    const common = { ...uniforms, uColor: { value: new T.Color(RING_COLOUR) }, uRadius: this.uRadius, uStrength: this.uStrength };
    const mat = (vs, fs) => new T.ShaderMaterial({ uniforms: common, vertexShader: vs, fragmentShader: fs,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending });
    // the motes: a band of angles (the shader turns them)
    const ang = new Float32Array(n), seed = new Float32Array(n), dummy = new Float32Array(n * 3);
    let s = 7;
    for (let i = 0; i < n; i++) { ang[i] = (i / n) * Math.PI * 2; seed[i] = ((s = (s * 16807) % 2147483647) / 2147483647); }
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(dummy, 3));
    g.setAttribute('aAngle', new T.BufferAttribute(ang, 1));
    g.setAttribute('aSeed', new T.BufferAttribute(seed, 1));
    const motes = new T.Points(g, mat(MOTE_VS, MOTE_FS));
    // the orbit line, with a light running round it
    const lp = new Float32Array(seg * 3), lt = new Float32Array(seg);
    for (let i = 0; i < seg; i++) { const a = (i / seg) * Math.PI * 2; lp.set([Math.cos(a), Math.sin(a), 0], i * 3); lt[i] = i / seg; }
    const lg = new T.BufferGeometry();
    lg.setAttribute('position', new T.BufferAttribute(lp, 3));
    lg.setAttribute('aT', new T.BufferAttribute(lt, 1));
    const line = new T.LineLoop(lg, mat(LINE_VS, LINE_FS));
    motes.frustumCulled = line.frustumCulled = false;
    this.group = new T.Group();
    this.group.add(line, motes);
    // the ring's plane: local z onto the layout's ring normal
    this.group.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), new T.Vector3(...RING_NORMAL));
    this.group.visible = false;
  }

  place(centre, radius) {
    if (!centre || !(radius > 0)) { this.group.visible = false; return; }
    this.group.visible = true;
    this.group.position.set(centre.x, centre.y, centre.z);
    this.group.scale.setScalar(radius);
    this.uRadius.value = radius;
  }

  /** Focus mode and the constellation view dim it (0..1). */
  strength(v) { this.uStrength.value = v; }
}
