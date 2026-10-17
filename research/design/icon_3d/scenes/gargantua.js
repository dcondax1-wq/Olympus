// Concept: Gargantua. A 3D black hole: tilted accretion disk with Doppler-bright side, the lensed far side of the disk
// arching over and under the shadow, a photon ring, and polar jets as the candle's wicks. The lower jet pierces a cyan
// liquidity line and flares.
import { bgTexture, flareTexture, sprite, neon, stars } from './_lib.js';
const DISK_V = `varying vec2 vUv; varying vec3 vP; void main(){ vUv = uv; vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`;
const DISK_F = `uniform float rIn; uniform float rOut; uniform float gain; uniform float lens; varying vec3 vP;
float hash(float n){ return fract(sin(n)*43758.5453); }
void main(){
  float r = length(vP.xy); float a = atan(vP.y, vP.x);
  float t = clamp((r - rIn) / (rOut - rIn), 0.0, 1.0);
  vec3 hot = vec3(1.0, 0.96, 1.0), mag = vec3(1.0, 0.25, 0.85), vio = vec3(0.48, 0.25, 1.0), deep = vec3(0.12, 0.05, 0.35);
  vec3 c = mix(hot, mag, smoothstep(0.0, 0.18, t)); c = mix(c, vio, smoothstep(0.18, 0.55, t)); c = mix(c, deep, smoothstep(0.55, 1.0, t));
  float bands = 0.9 + 0.05 * sin(r * 61.0 + a * 1.5) + 0.06 * sin(r * 17.0 - a * 3.0) + 0.04 * sin(r * 7.0 + a * 9.0);
  float streak = 0.9 + 0.1 * sin(a * 41.0 + r * 17.0);
  float dopp = mix(1.75, 0.55, 0.5 + 0.5 * cos(a + 0.4));     // side moving toward us is brighter
  float fade = smoothstep(0.0, 0.04, t) * (1.0 - smoothstep(0.7, 1.0, t));
  float I = gain * bands * streak * dopp * fade * (1.0 - 0.6 * t);
  gl_FragColor = vec4(c * I, 1.0);
}`;
const JET_V = `varying float vy; varying float vr; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vy = w.y; vr = length(position.xz); gl_Position = projectionMatrix * viewMatrix * w; }`;
const JET_F = `uniform vec3 col; uniform float y0; uniform float len; varying float vy;
void main(){ float d = clamp((abs(vy) - y0) / len, 0.0, 1.0); float f = pow(1.0 - d, 1.6) * smoothstep(0.0, 0.06, d); gl_FragColor = vec4(col * f, 1.0); }`;
export default async ({ THREE, size }) => {
  const scene = new THREE.Scene();
  scene.background = bgTexture(THREE, '#1d0636', '#07020f', '#000000', 0.48);
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 200);
  camera.position.set(0, 0.72, 12.4); camera.lookAt(0, -0.32, 0);
  scene.add(stars(THREE, 1400, 45, 5));
  const rH = 1.08;
  const diskMat = (gain) => new THREE.ShaderMaterial({ vertexShader: DISK_V, fragmentShader: DISK_F, uniforms: { rIn: { value: 1.42 }, rOut: { value: 3.7 }, gain: { value: gain }, lens: { value: 0 } },
    side: THREE.DoubleSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
  // the main disk, tilted almost edge-on
  const disk = new THREE.Mesh(new THREE.RingGeometry(1.42, 3.7, 256, 8), diskMat(0.85));
  disk.rotation.x = -Math.PI / 2 + 0.1; disk.rotation.z = 0.08; scene.add(disk);
  // the lensed far side: same disk image bent into a ring facing the camera (behind the shadow)
  const lensRing = new THREE.Mesh(new THREE.RingGeometry(1.16, 1.95, 256, 4), diskMat(0.7));
  lensRing.material.uniforms.rIn.value = 1.16; lensRing.material.uniforms.rOut.value = 1.95; lensRing.scale.set(1.0, 0.96, 1); lensRing.position.z = -0.3; lensRing.rotation.z = 0.08; scene.add(lensRing);
  // the shadow + photon ring
  const shadow = new THREE.Mesh(new THREE.SphereGeometry(rH, 96, 64), new THREE.MeshBasicMaterial({ color: 0x000000 }));
  scene.add(shadow);
  const photon = new THREE.Mesh(new THREE.TorusGeometry(rH * 1.03, 0.016, 16, 256), neon(THREE, 0xfff0ff, 1.6)); photon.position.z = 0.02; scene.add(photon);
  const halo = new THREE.Mesh(new THREE.TorusGeometry(rH * 1.12, 0.09, 16, 256), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xff3fd8).multiplyScalar(1.2), transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
  scene.add(halo);
  // jets (wicks)
  const jetMat = (k, len) => new THREE.ShaderMaterial({ vertexShader: JET_V, fragmentShader: JET_F, uniforms: { col: { value: new THREE.Color(0xe7c6ff).multiplyScalar(k) }, y0: { value: rH * 0.9 }, len: { value: len } },
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
  const up = new THREE.Mesh(new THREE.ConeGeometry(0.18, 1.8, 32, 1, true), jetMat(0.38, 1.8)); up.position.y = rH + 0.8; up.rotation.x = Math.PI; scene.add(up);
  const upCore = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.045, 1.8, 16), jetMat(2.2, 1.8)); upCore.position.y = rH + 0.8; scene.add(upCore);
  const tipY = -(rH + 1.95);
  const dn = new THREE.Mesh(new THREE.ConeGeometry(0.22, 1.95, 32, 1, true), jetMat(0.45, 2.8)); dn.position.y = -(rH + 0.97); scene.add(dn);
  const dnCore = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.03, 1.95, 16), jetMat(2.6, 2.8)); dnCore.position.y = -(rH + 0.97); scene.add(dnCore);
  // liquidity line the lower jet pierces
  const lvl = tipY + 0.28;
  for (let i = -8; i <= 8; i++) { if (Math.abs(i) < 1) continue; const d = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.028, 0.028), neon(THREE, 0x22d3ee, 2.4)); d.position.set(i * 0.24, lvl, 0.3); scene.add(d); }
  const fl = flareTexture(THREE, 'rgba(255,255,255,1)', 'rgba(120,230,255,0.45)');
  scene.add(sprite(THREE, fl, 1.0, [0, tipY, 0.4], 1));
  scene.add(sprite(THREE, flareTexture(THREE, 'rgba(255,255,255,1)', 'rgba(200,240,255,0.25)'), 0.18, [0, tipY, 0.42], 0.9, 22));
  scene.add(sprite(THREE, flareTexture(THREE, 'rgba(160,90,255,0.6)', 'rgba(110,40,220,0.25)'), 8.5, [0, 0, -2], 0.22));
  return { scene, camera, bloom: { strength: 0.85, radius: 0.4, threshold: 0.85 }, sharp: { center: new THREE.Vector3(0, 0, 0), radius: rH * 0.99, soft: 0.006 } };
};
