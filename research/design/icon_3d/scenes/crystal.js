// Concept: Crystal Core. A hexagonal glass prism with neon edges; a glowing candle floats inside and its lower wick
// pierces a holographic cyan liquidity ring, flaring white-hot. Mirror floor underneath.
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { bgTexture, flareTexture, sprite, neon, stars, rod, hexGridTexture, sparks, tube } from './_lib.js';
export default async ({ THREE, neonEnv, size, renderer }) => {
  renderer.toneMapping = THREE.NoToneMapping; renderer.toneMappingExposure = 1.0;   // keeps neon saturated (ACES bleaches it to white)
  const scene = new THREE.Scene();
  scene.background = bgTexture(THREE, '#33095e', '#0b0316', '#000000', 0.44);
  scene.environment = neonEnv();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 200);
  camera.position.set(0, 3.7, 11.6); camera.lookAt(0, -0.05, 0);
  scene.add(stars(THREE, 700, 45));
  const R = 1.5, H = 3.1, yb = -1.35;
  // glass prism
  const prismG = new THREE.CylinderGeometry(R, R, H, 6, 1, false, Math.PI / 6);
  const glass = new THREE.MeshPhysicalMaterial({ color: 0xb9a3ff, metalness: 0.1, roughness: 0.02, transparent: true, opacity: 0.16, side: THREE.FrontSide,
    iridescence: 1, iridescenceIOR: 1.4, iridescenceThicknessRange: [250, 700], clearcoat: 1, clearcoatRoughness: 0.0, envMapIntensity: 1.4, depthWrite: false, specularIntensity: 0.25 });
  const prism = new THREE.Mesh(prismG, glass); prism.position.y = yb + H / 2; scene.add(prism);
  // neon edges: top ring cyan->violet, bottom ring magenta, verticals violet
  const pts = (y) => Array.from({ length: 6 }, (_, i) => { const a = i * Math.PI / 3; return [R * Math.cos(a), y, R * Math.sin(a)]; });
  const top = pts(yb + H), bot = pts(yb);
  const mTop = neon(THREE, 0x9b7bff, 1.9), mBot = neon(THREE, 0xff3fd8, 2.3), mV = neon(THREE, 0xb27bff, 1.7);
  for (let i = 0; i < 6; i++) {
    scene.add(tube(THREE, top[i], top[(i + 1) % 6], 0.07, 0x8a5cff));
    scene.add(tube(THREE, bot[i], bot[(i + 1) % 6], 0.075, 0xff2bd6));
    scene.add(tube(THREE, bot[i], top[i], 0.055, 0xb44dff, 0.9));
  }
  for (const p of [...top, ...bot]) { const s = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 16), neon(THREE, 0xf3e8ff, 1.25)); s.position.set(...p); scene.add(s); }
  // candle inside
  const cy = 0.62;
  const bodyM = new THREE.MeshPhysicalMaterial({ color: 0xff5ad8, emissive: new THREE.Color(0xd21fb8), emissiveIntensity: 0.62, roughness: 0.18, metalness: 0.35, clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 1.6 });
  const body = new THREE.Mesh(new RoundedBoxGeometry(0.74, 1.6, 0.74, 5, 0.1), bodyM); body.position.y = cy; body.rotation.y = 0.6; scene.add(body);
  const shine = new THREE.Mesh(new RoundedBoxGeometry(0.82, 1.68, 0.82, 5, 0.12), new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0, clearcoat: 1, transparent: true, opacity: 0.18, envMapIntensity: 2.5, depthWrite: false }));
  shine.position.copy(body.position); shine.rotation.y = 0.6;
  const wick = neon(THREE, 0xfff0ff, 2.2);
  scene.add(rod(THREE, [0, cy + 0.8, 0], [0, cy + 1.42, 0], 0.045, wick));
  const tipY = -0.98;
  scene.add(rod(THREE, [0, cy - 0.8, 0], [0, tipY, 0], 0.05, wick));
  // liquidity level: holographic ring + dashes + faint disc, just above the prism floor
  const ly = -0.7;
  const ring = new THREE.Mesh(new THREE.TorusGeometry(2.25, 0.032, 12, 256), neon(THREE, 0x22d3ee, 2.6)); ring.rotation.x = Math.PI / 2; ring.position.y = ly; scene.add(ring);
  for (let i = 0; i < 40; i++) { const a0 = i / 40 * Math.PI * 2; const d = new THREE.Mesh(new THREE.TorusGeometry(2.55, 0.014, 8, 12, Math.PI * 2 / 40 * 0.55), neon(THREE, 0x22d3ee, 1.8)); d.rotation.x = Math.PI / 2; d.rotation.z = a0; d.position.y = ly; scene.add(d); }
  const disc = new THREE.Mesh(new THREE.CircleGeometry(2.25, 96), new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.07, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false }));
  disc.rotation.x = -Math.PI / 2; disc.position.y = ly; scene.add(disc);
  // flare at the sweep
  const fl = flareTexture(THREE);
  scene.add(sprite(THREE, fl, 1.5, [0, tipY, 0.05], 1));
  scene.add(sprite(THREE, fl, 0.7, [0, tipY, 0.05], 0.9, 9));
  scene.add(sprite(THREE, fl, 3.0, [0, cy, -0.4], 0.16));
  const rimL = new THREE.PointLight(0x22d3ee, 3.5, 3.2, 2); rimL.position.set(-1.3, cy + 0.5, -0.1); scene.add(rimL);
  const rimR = new THREE.PointLight(0xff3fd8, 4, 3.2, 2); rimR.position.set(1.3, cy - 0.1, -0.1); scene.add(rimR);

  // energy beam rising from the top wick, sparks drifting up
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.14, 2.6, 24, 1, true), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xc9a6ff).multiplyScalar(1.6), transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
  beam.position.y = cy + 1.42 + 1.3; scene.add(beam);
  scene.add(sparks(THREE, 160, [3.2, 4.6, 3.2, yb + 0.1], 0xf0c4ff, 0.045));
  // hex-grid floor glow
  const hg = new THREE.Mesh(new THREE.PlaneGeometry(13, 13), new THREE.MeshBasicMaterial({ map: hexGridTexture(THREE), transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
  hg.rotation.x = -Math.PI / 2; hg.position.y = yb - 0.73; scene.add(hg);
  const pl2 = new THREE.PointLight(0x22d3ee, 2, 3, 2); pl2.position.set(0, ly, 1.6); scene.add(pl2);
  // glossy dark floor (env reflections only) + a glow pool under the prism
  const floor = new THREE.Mesh(new THREE.CircleGeometry(14, 96), new THREE.MeshStandardMaterial({ color: 0x0b0614, metalness: 0.85, roughness: 0.32, envMapIntensity: 0.22 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = yb - 0.75; scene.add(floor);
  const pool = new THREE.Mesh(new THREE.CircleGeometry(3.2, 64), new THREE.MeshBasicMaterial({ map: flareTexture(THREE, 'rgba(200,120,255,0.9)', 'rgba(140,60,255,0.35)'), transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false }));
  pool.rotation.x = -Math.PI / 2; pool.position.y = yb - 0.74; scene.add(pool);
  return { scene, camera, bloom: { strength: 0.75, radius: 0.24, threshold: 0.9 } };
};
