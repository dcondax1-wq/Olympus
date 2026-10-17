// Liquidity Engine app icon, concept "Chrome Drop": one drop of liquid chrome (liquidity) hovering over a dark pool,
// a neon studio reflected in it (magenta left, cyan right, white key top-left, a violet front softbox with a dark
// horizon band), and a cyan ripple ring on the pool where it is about to land.
// Params (URL query): zoom (camera pull-back, maskable icon), s (drop scale), dy, gap, el (camera elevation), ly (look-at y),
// mag / cya / front (softbox intensities), hz (horizon band position 0..1), ring (ripple radius), bounce, bk (bloom)
import { makeEnv, backdrop, glowSprite, present, col } from './_common.js';
export default async ({ THREE, renderer, size, q }) => {
  const P = (k, d) => +(q.get(k) ?? d);
  const scene = new THREE.Scene();
  scene.add(backdrop(THREE, { inner: P('bgi', 0x2c0b5e), outer: 0x030108, center: [0.5, 0.6], radius: 0.8, k: 1,
    glow: { c: 0x6d28d9, i: 0.22, pos: [0.5, 0.2], size: [0.42, 0.08] } }));
  const S = P('s', 0.8), dy = P('dy', 0.2), gap = P('gap', 0.11);
  const floorY = dy - S - gap;
  const env = makeEnv(THREE, renderer, {
    top: 0x020006, bottom: 0x000000, horizon: 0x030008, res: 1024,
    panels: [
      { c: 0xff2bd6, i: P('mag', 2.0), w: 6, h: 20, pos: [-8, 0.5, 1.5] },          // big magenta softbox, left
      { c: 0x0fc7e6, i: P('cya', 0.9), w: 5, h: 20, pos: [8, 0, 1.5] },             // big cyan softbox, right
      { c: 0xff2bd6, i: 6, w: 1.4, h: 20, pos: [-8, 0.5, -3.2] },                   // hot rims
      { c: 0x22d3ee, i: P('cyr', 4.5), w: 1.2, h: 20, pos: [8, 0, -3.2] },
      { c: 0xffffff, i: P('key', 16), w: 4.5, h: 0.42, pos: [-4.5, 6.5, 7], rz: 0.5 },   // white key streak
      { c: 0xffffff, i: 4, w: 0.25, h: 3.0, pos: [5.5, 3.5, 7] },
      { c: 0xc4b5fd, i: 2.6, w: 10, h: 2.4, pos: [0, 11, -1] },
    ],
    extra: (s) => {
      // front softbox behind the camera: violet gradient with a dark horizon band (fills the drop's centre)
      const c = document.createElement('canvas'); c.width = 16; c.height = 512; const g = c.getContext('2d');
      const hz = P('hz', 0.52), gr = g.createLinearGradient(0, 0, 0, 512);
      gr.addColorStop(0, '#b39dff'); gr.addColorStop(Math.max(0, hz - 0.2), '#7c3aed'); gr.addColorStop(hz - 0.03, '#3b1584');
      gr.addColorStop(hz, '#12052e'); gr.addColorStop(hz + 0.05, '#2a0f6a'); gr.addColorStop(Math.min(1, hz + 0.25), '#5b21b6'); gr.addColorStop(1, '#4c1d95');
      g.fillStyle = gr; g.fillRect(0, 0, 16, 512);
      const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
      const fp = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ map: t, color: col(THREE, 0xffffff, P('front', 1.0)), side: THREE.DoubleSide }));
      fp.position.set(0, 0.5, 9); fp.lookAt(0, 0.5, 0); s.add(fp);
    },
  });
  scene.environment = env;
  // teardrop lathe: x = sin t * cos(t/2)^m, y = -cos t   (round bottom, sharp tip)
  const pts = [], N = 200, m = P('m', 1.0), wx = P('wx', 0.92);
  for (let i = 0; i <= N; i++) { const t = (i / N) * Math.PI; pts.push(new THREE.Vector2(Math.max(1e-4, Math.sin(t) * Math.pow(Math.cos(t / 2), m) * wx), -Math.cos(t))); }
  const geo = new THREE.LatheGeometry(pts, 256);
  const chrome = new THREE.MeshPhysicalMaterial({ color: P('tint', 0xf2eeff), metalness: 1, roughness: P('rough', 0.035), envMapIntensity: P('envk', 1.15), clearcoat: 1, clearcoatRoughness: 0.02 });
  const drop = new THREE.Mesh(geo, chrome); drop.scale.setScalar(S); drop.position.set(0, dy, 0); scene.add(drop);
  // bounce light from the glowing pool: additive Fresnel shell, strongest on the underside
  const shell = new THREE.Mesh(geo, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { k: { value: P('bounce', 1.0) }, c1: { value: col(THREE, 0x22d3ee, 1) }, c2: { value: col(THREE, 0x8b5cf6, 1) } },
    vertexShader: 'varying vec3 vN; varying vec3 vV; void main(){ vec4 w = modelMatrix*vec4(position,1.); vN = normalize(mat3(modelMatrix)*normal); vV = normalize(cameraPosition - w.xyz); gl_Position = projectionMatrix*viewMatrix*w; }',
    fragmentShader: `uniform float k; uniform vec3 c1, c2; varying vec3 vN; varying vec3 vV;
      void main(){ vec3 n = normalize(vN); float b = smoothstep(0.05, -0.95, n.y); float f = pow(1.-max(dot(n, normalize(vV)),0.), 2.2);
        vec3 c = mix(c2, c1, smoothstep(-0.3, -0.9, n.y)) * b * (0.18 + 1.1*f) * k; gl_FragColor = vec4(c, 1.); }` }));
  shell.scale.setScalar(S * 1.002); shell.position.copy(drop.position); scene.add(shell);
  // pool: dark liquid disc fading into the void (no horizon line)
  const pc = document.createElement('canvas'); pc.width = pc.height = 512; const pg = pc.getContext('2d');
  const gr = pg.createRadialGradient(256, 256, 0, 256, 256, 256);
  gr.addColorStop(0, 'rgba(4,1,10,0.55)'); gr.addColorStop(0.45, 'rgba(4,1,10,0.8)'); gr.addColorStop(0.8, 'rgba(4,1,10,0.55)'); gr.addColorStop(1, 'rgba(4,1,10,0)');
  pg.fillStyle = gr; pg.fillRect(0, 0, 512, 512);
  const pt = new THREE.CanvasTexture(pc); pt.colorSpace = THREE.SRGBColorSpace;
  const pool = new THREE.Mesh(new THREE.CircleGeometry(2.6, 128), new THREE.MeshBasicMaterial({ map: pt, transparent: true, depthWrite: false }));
  pool.rotation.x = -Math.PI / 2; pool.position.y = floorY; pool.renderOrder = 2; scene.add(pool);
  // ripple rings (neon, additive)
  const ring = (r, w, hex, k) => {
    const mm = new THREE.Mesh(new THREE.RingGeometry(r - w, r + w, 384), new THREE.MeshBasicMaterial({ color: col(THREE, hex, k), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    mm.rotation.x = -Math.PI / 2; mm.position.y = floorY + 0.003; mm.renderOrder = 3; scene.add(mm);
  };
  const r1 = P('ring', 0.5), r2 = r1 * P('r2', 1.55);
  ring(r1, 0.022, 0xd9fbff, P('rk', 2.2)); ring(r1, 0.05, 0x22d3ee, 0.9); ring(r1, 0.13, 0x22d3ee, 0.16);
  ring(r2, 0.014, 0x8b5cf6, 1.1); ring(r2, 0.05, 0x7c3aed, 0.14);
  const g1 = glowSprite(THREE, 0x22d3ee, 0.35, 1.0, 0.18); g1.position.set(0, floorY + 0.02, 0.3); g1.renderOrder = 4; scene.add(g1);
  const zoom = P('zoom', 1);
  const camera = new THREE.PerspectiveCamera(P('fov', 28), 1, 0.1, 100);
  const el = P('el', 0.2), dist = P('dist', 5.1) * zoom;
  camera.position.set(0, Math.sin(el) * dist + 0.02, Math.cos(el) * dist); camera.lookAt(0, P('ly', -0.04), 0);
  const out = present(THREE, renderer, scene, camera, size, { scale: 2, samples: 4, vignette: 0.3, grain: 0.005, ca: 0.08 });
  return { ...out, bloom: { strength: P('bk', 0.42), radius: 0.32, threshold: 0.9 } };
};
