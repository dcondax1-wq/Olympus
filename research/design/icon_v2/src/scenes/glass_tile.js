// Liquidity Engine app icon, concept "Glass Tile". A thick frosted-glass slab floats in front of magenta / cyan light; the sweep glyph (candle
// whose wick pierces a level) glows on its face. iOS "Liquid Glass" feel: edge speculars, refracted colour.
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { makeEnv, glowSprite, present, col } from './_common.js';
export default async ({ THREE, renderer, size, q }) => {
  const P = (k, d) => +(q.get(k) ?? d);
  const scene = new THREE.Scene();
  // opaque painted light field behind the glass (transmission only refracts opaque objects)
  const c = document.createElement('canvas'); c.width = c.height = 1024; const g = c.getContext('2d');
  g.fillStyle = '#05010c'; g.fillRect(0, 0, 1024, 1024);
  const blob = (x, y, r, stops) => { const gr = g.createRadialGradient(x, y, 0, x, y, r); stops.forEach(([o, cc]) => gr.addColorStop(o, cc)); g.fillStyle = gr; g.fillRect(0, 0, 1024, 1024); };
  g.globalCompositeOperation = 'lighter';
  blob(512, 520, 520, [[0, 'rgba(70,20,140,0.9)'], [0.6, 'rgba(30,8,70,0.5)'], [1, 'rgba(0,0,0,0)']]);
  blob(360, 360, 300, [[0, 'rgba(255,43,214,1)'], [0.5, 'rgba(200,30,180,0.45)'], [1, 'rgba(0,0,0,0)']]);
  blob(680, 690, 280, [[0, 'rgba(34,211,238,0.95)'], [0.5, 'rgba(30,150,220,0.4)'], [1, 'rgba(0,0,0,0)']]);
  blob(650, 330, 200, [[0, 'rgba(139,92,246,0.8)'], [1, 'rgba(0,0,0,0)']]);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const bgPlane = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 3.2), new THREE.MeshBasicMaterial({ map: tex }));
  bgPlane.position.z = -1.2; scene.add(bgPlane);
  scene.environment = makeEnv(THREE, renderer, {
    top: 0x0a0318, bottom: 0x000000, horizon: 0x0c0420, res: 512,
    panels: [
      { c: 0xffffff, i: 12, w: 8, h: 0.7, pos: [-3, 7, 6], rz: 0.4 },
      { c: 0xff2bd6, i: 5, w: 2, h: 14, pos: [-8, 0, 2] },
      { c: 0x22d3ee, i: 5, w: 2, h: 14, pos: [8, 0, 2] },
      { c: 0x8b5cf6, i: 3, w: 12, h: 3, pos: [0, 9, -2] },
    ],
  });
  const G = new THREE.Group(); scene.add(G);
  const glass = new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 0, roughness: P('rough', 0.5), transmission: 1, thickness: 0.6, ior: 1.5,
    clearcoat: 1, clearcoatRoughness: 0.02, specularIntensity: 1, envMapIntensity: 1.5, attenuationColor: new THREE.Color(0xe6dcff), attenuationDistance: 3 });
  const W = P('w', 1.16), T = P('t', 0.2);
  const slab = new THREE.Mesh(new RoundedBoxGeometry(W, W, T, 8, 0.22), glass); G.add(slab);
  // glyph on the front face (transparent materials are left out of the transmission pass: no double image)
  const z = T / 2 + 0.01;
  const emis = (hex, k) => new THREE.MeshBasicMaterial({ color: col(THREE, hex, k), transparent: true, depthWrite: false });
  const add = (geo, m, x, y, zz = z) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, zz); o.renderOrder = 5; G.add(o); return o; };
  const bw = 0.2, bh = 0.32, by = 0.07;
  const white = emis(0xfff4fd, 1.25), cyan = emis(0x7cf0ff, 1.15);
  add(new THREE.PlaneGeometry(W * 0.8, 0.032), cyan, 0, by - bh / 2 - 0.19);
  add(new RoundedBoxGeometry(bw, bh, 0.004, 3, 0.002), white, 0, by);
  add(new THREE.PlaneGeometry(0.036, 0.12), white, 0, by + bh / 2 + 0.06);
  add(new THREE.PlaneGeometry(0.036, 0.3), white, 0, by - bh / 2 - 0.15);
  const gl = glowSprite(THREE, 0xff4fe0, 0.35, 0.6, 0.9); gl.position.set(0, by, z + 0.02); G.add(gl);
  const gl2 = glowSprite(THREE, 0x22d3ee, 0.5, 0.36, 0.2); gl2.position.set(0, by - bh / 2 - 0.19, z + 0.03); G.add(gl2);
  G.rotation.set(P('rx', -0.14), P('ry', 0.24), 0);
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0, P('dist', 3.3)); camera.lookAt(0, 0, 0);
  const out = present(THREE, renderer, scene, camera, size, { scale: 2, samples: 4, vignette: 0.3, grain: 0.006, ca: 0.1, frames: 3 });
  return { ...out, bloom: { strength: 0.45, radius: 0.4, threshold: 0.92 } };
};
