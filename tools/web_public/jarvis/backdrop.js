// Jarvis home backdrop (jarvis/backdrop.js, 2026-11-03; docs/OLYMPUS_RENDER.md): the 3D space behind the home screen, on the
// OLYMPUS render core. A deep nebula and a twinkling starfield, the temple of OLYMPUS on the horizon (marble columns, gold
// capitals, fading into the fog), a glossy obsidian floor that reflects the sky with a neon
// grid fading into fog, a light shaft where the core floats, two slow halo rings in the sky and drifting glass shards that
// catch the light. It replaces the flat 2D layers of .bgfx (stars canvas, SVG globe, CSS floor) once its first frame is drawn;
// without WebGL or the render core, those stay exactly as they were.
//   self-mounting: <script type="module" src="./backdrop.js"></script>; window.__jarvisBackdrop = its state (tests)
// Follows html[data-fx] (ultra / high / low / off: off = one still frame), the theme colours (--c / --c2 / --c3) and the
// home screen: no frame while an app is open, the tab is hidden or the page is not in Jarvis mode. 30 fps (it is a backdrop),
// pixel ratio <= 1.25 (soft by design), so the core in front keeps the GPU.

const root = document.documentElement;
const state = (window.__jarvisBackdrop = { state: 'loading', frames: 0, quality: '', passes: 0, error: '' });
const FPS = 30, STYLE_ID = 'jbackdrop-css';
const CSS = `
.bgfx canvas.jbackdrop { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; transition: opacity .9s ease; }
html[data-bg3d="on"] .bgfx canvas.jbackdrop { opacity: 1; }
html[data-bg3d="on"] .bgfx #stars, html[data-bg3d="on"] .bgfx .bgglobe, html[data-bg3d="on"] .bgfx .floor { display: none; }
html[data-bg3d="on"] .bgfx::before, html[data-bg3d="on"] .bgfx::after { display: none; }
`;

function cssVar(name, fallback) {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return /^#[0-9a-f]{3,8}$/i.test(v) ? v : fallback;
}
const colours = () => ({ c: cssVar('--c', '#a855f7'), c2: cssVar('--c2', '#7c3aed'), c3: cssVar('--c3', '#c084fc') });
const level = () => (['ultra', 'high', 'low', 'off'].indexOf(root.dataset.fx) >= 0 ? root.dataset.fx : 'high');
// the home screen is up and the backdrop layer is shown (the shell hides .bgfx outside Jarvis mode)
const onHome = () => { const h = document.getElementById('home'), b = document.querySelector('.bgfx'); return !!h && !h.hidden && !!b && b.getClientRects().length > 0; };

async function mount() {
  const host = document.querySelector('.bgfx');
  if (!host) { state.state = 'off'; return; }
  const probe = document.createElement('canvas');
  if (!probe.getContext('webgl2')) { state.state = 'off'; return; }     // no WebGL2: the 2D layers stay
  const [T, RC, M] = await Promise.all([import('./three.module.min.js'), import('../olympus/render.js'), import('../olympus/materials.js')]);
  const style = document.createElement('style'); style.id = STYLE_ID; style.textContent = CSS; document.head.appendChild(style);
  probe.className = 'jbackdrop'; probe.setAttribute('aria-hidden', 'true');
  host.insertBefore(probe, host.firstChild);

  const scene = new T.Scene(), camera = new T.PerspectiveCamera(58, 1, 0.1, 400);
  camera.position.set(0, 1.5, 10); camera.lookAt(0, 1.6, 0);
  const fog = new T.FogExp2(0x0b0a24, 0.03); scene.fog = fog;      // a deep violet haze: far things fade into colour, not black
  const K = colours();
  const rc = RC.createRenderer({ canvas: probe, scene, camera, quality: level(), env: 'night', tint: K.c, maxDpr: 1.25, msaa: false, adapt: false, exposure: 0.8,
    theme: null, bloom: { strength: 0.75, radius: 0.7, threshold: 0.82 }, grade: { vignette: 0.42, grain: 0.035, aberration: 0.003 } });

  // sky: nebula + stars (both added light, no fog)
  const nebula = M.nebula({ colors: [K.c, K.c2, K.c3, '#2b1a6b'], count: 10, radius: 70, size: 85, opacity: 0.17 }); nebula.position.y = 12; scene.add(nebula);
  const stars = M.starfield({ count: level() === 'ultra' ? 2400 : level() === 'high' ? 1600 : 700, radius: 160, size: 2.4 }); scene.add(stars);

  // the floor: polished obsidian (env reflections), a neon grid fading into the fog, a pool of light under the core
  const floor = new T.Mesh(new T.PlaneGeometry(400, 400), M.metal({ kind: 'gunmetal', color: '#0c0b13', roughness: 0.3, clearcoat: 1, envMapIntensity: 0.5 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -2.6; scene.add(floor);
  const gridU = { uC: { value: new T.Color(K.c).multiplyScalar(1.6) }, uT: { value: 0 } };
  const grid = new T.Mesh(new T.PlaneGeometry(400, 400), new T.ShaderMaterial({ uniforms: gridU, transparent: true, depthWrite: false,
    blending: T.AdditiveBlending, extensions: { derivatives: true },
    vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }',
    fragmentShader: `uniform vec3 uC; uniform float uT; varying vec3 vW;
      void main(){ vec2 p = vW.xz / 2.4 + vec2(0.0, uT * 0.35); vec2 g = abs(fract(p - 0.5) - 0.5) / fwidth(p);
        float l = 1.0 - min(min(g.x, g.y), 1.0); float d = length(vW.xz);
        gl_FragColor = vec4(uC * l * 0.55 * exp(-d * 0.045) * smoothstep(1.5, 5.0, d), 1.0); }` }));
  grid.rotation.x = -Math.PI / 2; grid.position.y = -2.59; scene.add(grid);
  const pool = new T.Mesh(new T.CircleGeometry(16, 64), new T.ShaderMaterial({ uniforms: { uC: { value: new T.Color(K.c3).multiplyScalar(1.2) } },
    transparent: true, depthWrite: false, blending: T.AdditiveBlending,
    vertexShader: 'varying vec2 vU; void main(){ vU = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform vec3 uC; varying vec2 vU; void main(){ float d = length(vU - 0.5) * 2.0; gl_FragColor = vec4(uC * pow(max(0.0, 1.0 - d), 2.6), 1.0); }' }));
  pool.rotation.x = -Math.PI / 2; pool.position.set(0, -2.58, -30); scene.add(pool);   // far out: on screen it lies just under the core

  // the light shaft from above, two halo rings in the sky, a horizon ring
  const shaft = M.energyBeam({ color: K.c3, length: 40, radius: 5, taper: 0.3, intensity: 0.12, speed: 0.25 }); shaft.position.set(0, -2.6, -30); scene.add(shaft);
  const ringA = new T.Mesh(new T.TorusGeometry(9, 0.035, 8, 220), M.neon({ color: K.c, intensity: 3.5, fog: true }));
  ringA.position.set(0, 7.5, -14); ringA.rotation.set(1.25, 0, 0.12); scene.add(ringA);
  const ringB = new T.Mesh(new T.TorusGeometry(12.5, 0.02, 8, 260), M.neon({ color: K.c3, intensity: 2.2, fog: true }));
  ringB.position.set(0, 7.5, -14); ringB.rotation.set(1.4, 0.2, -0.3); scene.add(ringB);
  const horizon = new T.Mesh(new T.TorusGeometry(40, 0.08, 8, 320), M.neon({ color: K.c2, intensity: 2.5, fog: true }));
  horizon.rotation.x = Math.PI / 2; horizon.position.y = -2.55; scene.add(horizon);

  // the temple of OLYMPUS on the horizon: an arc of polished marble columns with gold capitals, fading into the fog
  const N = 14, colGeo = new T.CylinderGeometry(0.55, 0.62, 10, 20, 1), capGeo = new T.BoxGeometry(1.5, 0.35, 1.5);
  const columns = new T.InstancedMesh(colGeo, M.marble({ color: '#e8e4ee', vein: '#5b5470', gold: true, scale: 0.6 }), N);
  const capitals = new T.InstancedMesh(capGeo, M.metal({ kind: 'gold', roughness: 0.25 }), N * 2);
  const at = new T.Object3D();
  for (let i = 0; i < N; i++) {
    const a = Math.PI * (0.12 + 0.76 * i / (N - 1)), x = Math.cos(a) * 30, z = -Math.sin(a) * 30 - 8;
    at.position.set(x, 2.4, z); at.rotation.set(0, 0, 0); at.updateMatrix(); columns.setMatrixAt(i, at.matrix);
    at.position.set(x, 7.55, z); at.updateMatrix(); capitals.setMatrixAt(i * 2, at.matrix);
    at.position.set(x, -2.4, z); at.updateMatrix(); capitals.setMatrixAt(i * 2 + 1, at.matrix);
  }
  scene.add(columns, capitals);
  const moon = new T.DirectionalLight(0xe4dcff, 2.2); moon.position.set(4, 12, 10); scene.add(moon);   // the temple's key light

  // drifting glass shards (env reflections + iridescence: the light catches them as they turn)
  const shardMat = M.glass({ color: '#e9ddff', rim: K.c3, opacity: 0.22 }), chromeMat = M.metal({ kind: 'chrome' });
  const shards = [];
  for (let i = 0; i < 9; i++) {
    const m = new T.Mesh(new T.OctahedronGeometry(0.22 + (i % 3) * 0.12, 0), i % 3 ? shardMat : chromeMat);
    const a = i / 9 * Math.PI * 2;
    m.position.set(Math.cos(a) * (6 + (i % 4) * 1.5), 0.2 + (i % 5) * 1.2, -7 - Math.sin(a) * 4);
    m.userData.s = 0.2 + (i % 4) * 0.12; m.userData.y = m.position.y;
    scene.add(m); shards.push(m);
  }
  const lamp = new T.PointLight(new T.Color(K.c3), 22, 30, 2); lamp.position.set(0, 2.5, -3); scene.add(lamp);

  let themeKey = '';
  function theme() {
    const k = colours(), sig = k.c + k.c2 + k.c3;
    if (sig === themeKey) return;                         // the environment is rebuilt only when the colours change
    themeKey = sig;
    gridU.uC.value.set(k.c).multiplyScalar(1.6);
    pool.material.uniforms.uC.value.set(k.c3).multiplyScalar(1.2);
    shaft.material.uniforms.uColor.value.set(k.c3);
    ringA.material.color.set(k.c).multiplyScalar(3.5); ringB.material.color.set(k.c3).multiplyScalar(2.2);
    horizon.material.color.set(k.c2).multiplyScalar(2.5);
    lamp.color.set(k.c3);
    nebula.children.forEach((s, i) => s.material.color.set([k.c, k.c2, k.c3, '#2b1a6b'][i % 4]));
    if (shardMat.userData.rim) shardMat.userData.rim.uRim.value.set(k.c3).multiplyScalar(1.2);
    rc.setTheme({ sky: '#0d0620', fog: '#04050c', emissive: k.c, bloom: k.c3, accent: k.c });
  }
  theme();

  let raf = 0, last = 0, t = 0, drawn = false;
  const still = () => level() === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  function step(dt) {
    t += dt;
    nebula.update(t); stars.update(t, rc.renderer.getPixelRatio()); shaft.update(t);
    gridU.uT.value = t;
    ringA.rotation.z += dt * 0.05; ringB.rotation.z -= dt * 0.03;
    shards.forEach((m, i) => { m.rotation.x += dt * m.userData.s; m.rotation.y += dt * m.userData.s * 0.7; m.position.y = m.userData.y + Math.sin(t * 0.4 + i) * 0.25; });
    camera.position.x = Math.sin(t * 0.05) * 0.6; camera.lookAt(0, 1.6, 0);
  }
  function draw() {
    if (!rc.render()) return;
    state.frames++;
    if (!drawn) { drawn = true; root.dataset.bg3d = 'on'; state.state = 'on'; }
  }
  function frame(now) {
    raf = 0;
    if (!live()) return;
    raf = requestAnimationFrame(frame);
    if (now - last < 1000 / FPS - 2) return;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 1 / FPS;
    last = now;
    step(dt); draw();
  }
  const live = () => onHome() && !document.hidden && !still();
  // an app open over Jarvis (the home is hidden): release the composer's buffers and the environment, not just the loop
  function kick() {
    if (!onHome()) { if (raf) cancelAnimationFrame(raf); raf = 0; rc.suspend(); state.asleep = true; return; }
    if (rc.asleep()) { rc.resume(); state.asleep = false; themeKey = ''; theme(); }
    if (live()) { if (!raf) { last = 0; raf = requestAnimationFrame(frame); } return; }
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    if (onHome() && !document.hidden && still()) { step(0); draw(); }      // off / reduced motion: one still frame
  }
  // follow the effects level, the theme and the home screen (attributes the shell already sets)
  new MutationObserver(() => {
    const q = level();
    if (q !== rc.quality()) { rc.setQuality(q); state.quality = q; state.passes = rc.stats().passes; }
    theme(); kick();
  }).observe(root, { attributes: true, attributeFilter: ['data-fx', 'data-theme', 'data-oly-theme', 'data-mode', 'style'] });
  const home = document.getElementById('home');
  if (home) new MutationObserver(kick).observe(home, { attributes: true, attributeFilter: ['hidden'] });
  document.addEventListener('visibilitychange', kick);
  probe.addEventListener('webglcontextlost', (e) => { e.preventDefault(); delete root.dataset.bg3d; state.state = 'lost'; if (raf) cancelAnimationFrame(raf); raf = 0; });
  state.quality = rc.quality(); state.passes = rc.stats().passes; state.stats = () => rc.stats();
  kick();
}

// once Jarvis has booted (the boot log or the OLYMPUS intro gone) and the page is idle: compiling the shaders and the
// environment takes the main thread for a moment, and that must never hold up the boot screen or the intro
const start = () => mount().catch((e) => { state.state = 'off'; state.error = String((e && (e.stack || e.message)) || e); delete root.dataset.bg3d; });
const booted = () => !document.getElementById('bootfx') && (!window.__olyIntro || window.__olyIntro.done);
const idle = () => (window.requestIdleCallback ? requestIdleCallback(start, { timeout: 2500 }) : setTimeout(start, 600));
let waited = 0;
const whenBooted = () => { if (booted() || (waited += 250) > 15000) setTimeout(idle, 400); else setTimeout(whenBooted, 250); };
if (document.readyState === 'complete') whenBooted(); else window.addEventListener('load', whenBooted, { once: true });
