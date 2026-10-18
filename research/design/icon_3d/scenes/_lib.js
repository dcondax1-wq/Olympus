// Shared helpers for the 3D icon scenes (crystal, gargantua, orb).
export function bgTexture(THREE, inner = '#2a0b4d', mid = '#0d0419', outer = '#020106', cy = 0.46) {
  const c = document.createElement('canvas'); c.width = c.height = 1024;
  const g = c.getContext('2d'), gr = g.createRadialGradient(512, 1024 * cy, 0, 512, 1024 * cy, 760);
  gr.addColorStop(0, inner); gr.addColorStop(0.42, mid); gr.addColorStop(1, outer);
  g.fillStyle = gr; g.fillRect(0, 0, 1024, 1024);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
export function flareTexture(THREE, core = 'rgba(255,255,255,1)', mid = 'rgba(255,90,225,0.55)') {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d'), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, core); gr.addColorStop(0.12, 'rgba(255,230,252,0.95)'); gr.addColorStop(0.35, mid); gr.addColorStop(1, 'rgba(255,43,214,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
export function sprite(THREE, tex, scale, pos, opacity = 1, sx = 1) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity }));
  s.scale.set(scale * sx, scale, 1); s.position.set(...pos); return s;
}
export const neon = (THREE, hex, k = 2.4) => new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(k), toneMapped: false });
export function stars(THREE, n = 900, r = 40, seed = 3) {
  let s = seed; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const p = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { const u = rnd() * 2 - 1, a = rnd() * Math.PI * 2, q = Math.sqrt(1 - u * u); p.set([r * q * Math.cos(a), r * u, -Math.abs(r * q * Math.sin(a)) - 5], i * 3); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: 0xd9ccff, size: 0.09, sizeAttenuation: true, transparent: true, opacity: 0.75 }));
}
// a thin glowing rod between two points
export function rod(THREE, a, b, r, mat) {
  const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b), len = A.distanceTo(B);
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 12, 1), mat);
  m.position.copy(A).add(B).multiplyScalar(0.5);
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), B.clone().sub(A).normalize());
  return m;
}
// hexagon grid floor texture with a radial fade (use as map + additive)
export function hexGridTexture(THREE, color = 'rgba(170,110,255,1)', cell = 34) {
  const c = document.createElement('canvas'); c.width = c.height = 1024; const g = c.getContext('2d');
  g.strokeStyle = color; g.lineWidth = 2;
  const h = cell * Math.sqrt(3);
  for (let row = -1; row < 1024 / h * 2 + 2; row++) for (let col = -1; col < 1024 / (cell * 3) + 2; col++) {
    const x = col * cell * 3 + (row % 2 ? cell * 1.5 : 0), y = row * h / 2;
    g.beginPath(); for (let k = 0; k <= 6; k++) { const a = k * Math.PI / 3; g[k ? 'lineTo' : 'moveTo'](x + cell * Math.cos(a), y + cell * Math.sin(a)); } g.stroke();
  }
  g.globalCompositeOperation = 'destination-in';
  const gr = g.createRadialGradient(512, 512, 0, 512, 512, 512); gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(0.55, 'rgba(0,0,0,0.5)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 1024, 1024);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
export function sparks(THREE, n, box, color = 0xf5c2ff, size = 0.05, seed = 9) {
  let s = seed; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const p = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) p.set([(rnd() - .5) * box[0], box[3] + rnd() * box[1], (rnd() - .5) * box[2]], i * 3);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: new THREE.Color(color).multiplyScalar(2), size, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
}
// neon tube between two points: white-hot core + saturated additive sleeve
export function tube(THREE, a, b, r, hex, k = 1.0, core = 0.35) {
  const g = new THREE.Group();
  g.add(rod(THREE, a, b, r * 0.4, new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).lerp(new THREE.Color(0xffffff), core).multiplyScalar(1.35 * k), toneMapped: false })));
  g.add(rod(THREE, a, b, r, new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(0.7 * k), transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false })));
  return g;
}
