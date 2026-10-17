// Concept: Oracle Orb. A glass sphere on a chrome-and-neon pedestal holds a holographic candle chart: three candles
// falling into a liquidity line, the last one sweeping through it with a flare, then a big bullish reversal candle.
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { bgTexture, flareTexture, sprite, neon, stars, rod, sparks } from './_lib.js';
export default async ({ THREE, neonEnv }) => {
  const scene = new THREE.Scene();
  scene.background = bgTexture(THREE, '#300a58', '#0a0314', '#000000', 0.42);
  scene.environment = neonEnv();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 200);
  camera.position.set(0, 1.5, 11.6); camera.lookAt(0, -0.2, 0);
  scene.add(stars(THREE, 600, 45, 2));
  const R = 1.9, oy = 0.35;
  // candles inside (hologram: emissive + slightly transparent)
  const holo = (hex, k) => new THREE.MeshPhysicalMaterial({ color: new THREE.Color(hex), emissive: new THREE.Color(hex), emissiveIntensity: k * 0.5, roughness: 0.16, metalness: 0.3, clearcoat: 1, clearcoatRoughness: 0.04, envMapIntensity: 1.5 });
  const C = [ // x, open, close, high, low, bull
    [-1.02, 0.55, 0.15, 0.7, 0.02, false], [-0.5, 0.2, -0.22, 0.34, -0.32, false], [0.02, -0.15, -0.42, -0.05, -1.05, false], [0.6, -0.42, 0.78, 0.98, -0.5, true]];
  const lvlY = oy - 0.72;
  for (const [x, o, c, h, l, bull] of C) {
    const top = Math.max(o, c) + oy, bot = Math.min(o, c) + oy, col = bull ? 0x2ee5c8 : 0xff3fd8;
    const b = new THREE.Mesh(new RoundedBoxGeometry(0.42, top - bot, 0.42, 4, 0.06), holo(col, bull ? 1.25 : 1.05)); b.position.set(x, (top + bot) / 2, 0); b.rotation.y = 0.5; scene.add(b);
    scene.add(rod(THREE, [x, top, 0], [x, h + oy, 0], 0.028, neon(THREE, bull ? 0xb8fff4 : 0xffd0f6, 1.8)));
    scene.add(rod(THREE, [x, bot, 0], [x, l + oy, 0], 0.028, neon(THREE, bull ? 0xb8fff4 : 0xffd0f6, 1.8)));
  }
  // liquidity line inside the orb, swept by the third candle's wick
  for (let i = -6; i <= 6; i++) { if (i === 0) continue; const d = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.024, 0.024), neon(THREE, 0x22d3ee, 2.4)); d.position.set(i * 0.21 + 0.02, lvlY, 0.05); scene.add(d); }
  const fl = flareTexture(THREE, 'rgba(255,255,255,1)', 'rgba(120,230,255,0.45)');
  scene.add(sprite(THREE, fl, 0.9, [0.02, -1.05 + oy, 0.2], 1));
  scene.add(sprite(THREE, fl, 0.14, [0.02, -1.05 + oy, 0.22], 0.9, 18));
  // target arrow glow at the reversal candle top
  scene.add(sprite(THREE, flareTexture(THREE, 'rgba(220,255,250,1)', 'rgba(46,229,200,0.4)'), 0.7, [0.6, 0.98 + oy, 0.2], 0.9));
  // the glass orb
  const glass = new THREE.MeshPhysicalMaterial({ color: 0xcdb8ff, roughness: 0.0, metalness: 0.0, transparent: true, opacity: 0.09, clearcoat: 1, clearcoatRoughness: 0,
    iridescence: 1, iridescenceIOR: 1.45, iridescenceThicknessRange: [300, 800], envMapIntensity: 0.55, specularIntensity: 0.35, depthWrite: false, side: THREE.FrontSide });
  const orb = new THREE.Mesh(new THREE.SphereGeometry(R, 128, 96), glass); orb.position.y = oy; scene.add(orb);
  // fresnel rim on the orb
  const rim = new THREE.Mesh(new THREE.SphereGeometry(R * 1.002, 128, 96), new THREE.ShaderMaterial({
    vertexShader: 'varying vec3 n; varying vec3 v; void main(){ vec4 w = modelViewMatrix * vec4(position,1.0); n = normalize(normalMatrix * normal); v = normalize(-w.xyz); gl_Position = projectionMatrix * w; }',
    fragmentShader: 'varying vec3 n; varying vec3 v; void main(){ float f = pow(1.0 - max(dot(n, v), 0.0), 3.2); vec3 c = mix(vec3(0.55,0.3,1.0), vec3(1.0,0.3,0.85), clamp(n.y*0.5+0.5,0.0,1.0)); gl_FragColor = vec4(c * f * 1.5, 1.0); }',
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
  rim.position.y = oy; scene.add(rim);
  // glass highlights: a bright arc top-left and a soft one bottom-right
  const hl = new THREE.Mesh(new THREE.TorusGeometry(R * 0.9, 0.035, 8, 64, 0.95), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xffffff).multiplyScalar(1.3), transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
  hl.position.set(0, oy, R * 0.42); hl.rotation.z = 1.75; scene.add(hl);
  const hl2 = new THREE.Mesh(new THREE.TorusGeometry(R * 0.92, 0.02, 8, 64, 0.6), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xe9b8ff), transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
  hl2.position.set(0, oy, R * 0.4); hl2.rotation.z = -0.95; scene.add(hl2);
  // pedestal: chrome ring stack + neon band
  const chrome = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 1, roughness: 0.12, envMapIntensity: 1.4 });
  const py = oy - R * 0.93;
  const ped = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.35, 0.42, 96), chrome); ped.position.y = py - 0.2; scene.add(ped);
  const band = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.04, 16, 160), neon(THREE, 0xa76bff, 2.6)); band.rotation.x = Math.PI / 2; band.position.y = py - 0.12; scene.add(band);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.6, 0.16, 96), new THREE.MeshStandardMaterial({ color: 0x120820, metalness: 0.9, roughness: 0.25 })); base.position.y = py - 0.48; scene.add(base);
  const band2 = new THREE.Mesh(new THREE.TorusGeometry(1.56, 0.03, 16, 160), neon(THREE, 0xff3fd8, 2.4)); band2.rotation.x = Math.PI / 2; band2.position.y = py - 0.42; scene.add(band2);
  // floor glow + sparks
  const pool = new THREE.Mesh(new THREE.CircleGeometry(3.4, 64), new THREE.MeshBasicMaterial({ map: flareTexture(THREE, 'rgba(190,120,255,0.9)', 'rgba(130,60,255,0.3)'), transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending, depthWrite: false }));
  pool.rotation.x = -Math.PI / 2; pool.position.y = py - 0.56; scene.add(pool);
  scene.add(sparks(THREE, 120, [5, 4.5, 3, py - 0.4], 0xe9c8ff, 0.04));
  const l1 = new THREE.PointLight(0xffffff, 5, 6, 2); l1.position.set(1.6, 1.8, 2.4); scene.add(l1);
  const l2 = new THREE.PointLight(0x22d3ee, 4, 6, 2); l2.position.set(-2.4, -0.4, 2.0); scene.add(l2);
  return { scene, camera, bloom: { strength: 0.6, radius: 0.22, threshold: 0.92 } };
};
