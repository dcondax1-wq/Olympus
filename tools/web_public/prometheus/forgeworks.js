// THE FORGE works (2026-11-04): the smithy on the arena's rim. A bronze anvil with a hammer that strikes (a molten ingot flares and
// throws sparks), a soot-black stone hearth arch with a furnace mouth, a molten-metal shader (animated emissive noise, a dark crust
// that cracks open on the strike, vertex heat distortion), a chimney of light shafts. Real materials: bronze (metal, brushed) and soot
// (rough stone with grime streaks, drawn once on a canvas). Sparks, embers, smoke and the heat haze come from the OLYMPUS effects
// (olympus/fx-*.js: embers, heatShimmer, volumetricFog, godRays), each one optional.
//   const w = buildWorks(THREE, scene, { R, lite }) ;  w.update(t, still)  (uniform writes only) ;  w.strike  (count of hammer blows)
//   w.attachFx(window.OLYMPUS_FX)  -> Promise ; w.fxNames ; w.dispose()
const NOISE = `
float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y); }
float fbm(vec2 p) { return 0.5 * vn(p) + 0.27 * vn(p * 2.03 + 4.1) + 0.15 * vn(p * 4.1 + 9.7) + 0.08 * vn(p * 8.3 + 2.2); }
`;

function canvasTex(THREE, w, h, draw, repeat) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); }
  return t;
}
const mul = (a) => () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

/** soot: dark stone with grime streaks that run down and a warm glow near the bottom (the furnace side) */
const sootTex = (THREE, size) => canvasTex(THREE, size, size, (x, w, h) => {
  const r = mul(11); x.fillStyle = '#2a2420'; x.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) { x.fillStyle = `rgba(${r() > 0.5 ? '70,60,52' : '8,6,5'},${(0.04 + r() * 0.12).toFixed(3)})`; x.fillRect(r() * w, r() * h, 1 + r() * 6, 1 + r() * 4); }
  for (let i = 0; i < 60; i++) { const gx = r() * w, gy = r() * h * 0.6, len = 20 + r() * h * 0.5; const g = x.createLinearGradient(0, gy, 0, gy + len); g.addColorStop(0, 'rgba(0,0,0,.35)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(gx, gy, 1 + r() * 3, len); }
  const glow = x.createLinearGradient(0, h * 0.6, 0, h); glow.addColorStop(0, 'rgba(255,110,30,0)'); glow.addColorStop(1, 'rgba(255,110,30,.22)'); x.fillStyle = glow; x.fillRect(0, 0, w, h);
}, [1, 1]);

/** bronze: a warm green-brown patina on a brushed metal, scratches along the length */
const bronzeTex = (THREE, size) => canvasTex(THREE, size, size, (x, w, h) => {
  const r = mul(23); x.fillStyle = '#9a6a38'; x.fillRect(0, 0, w, h);
  for (let i = 0; i < h; i += 2) { x.fillStyle = `rgba(${r() > 0.5 ? '255,220,160' : '40,20,6'},${(0.03 + r() * 0.07).toFixed(3)})`; x.fillRect(0, i, w, 1 + r() * 2); }
  for (let i = 0; i < 140; i++) { x.fillStyle = `rgba(70,120,90,${(0.05 + r() * 0.1).toFixed(2)})`; x.beginPath(); x.arc(r() * w, r() * h, 1 + r() * 5, 0, 7); x.fill(); }
}, [1, 1]);

export function buildWorks(THREE, scene, o) {
  const R = o.R, lite = !!o.lite, U = { uT: { value: 0 }, uHeat: { value: 0.35 }, uStrike: { value: 0 } }, group = new THREE.Group();
  const soot = new THREE.MeshStandardMaterial({ map: sootTex(THREE, lite ? 128 : 256), color: 0xb8aca0, roughness: 0.92, metalness: 0.04 });
  const bronze = new THREE.MeshStandardMaterial({ map: bronzeTex(THREE, lite ? 128 : 256), color: 0xe0b884, roughness: 0.4, metalness: 0.88, envMapIntensity: 1.1 });
  const iron = new THREE.MeshStandardMaterial({ color: 0x241d1a, roughness: 0.55, metalness: 0.8 });
  // the molten metal: emissive fbm that flows and boils, a dark crust where the noise is low, white-gold where it is high, vertices pushed by the heat
  const molten = new THREE.ShaderMaterial({ uniforms: U, fog: false,
    vertexShader: `uniform float uT; uniform float uHeat; varying vec2 vUv; varying vec3 vN; varying float vD;
      ${NOISE}
      void main() { vUv = uv; vN = normalize(normalMatrix * normal);
        float d = fbm(position.xz * 3.0 + uT * 0.35) - 0.5; vD = d;
        vec3 p = position + normal * d * 0.05 * (0.5 + uHeat);                        // the surface boils
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }`,
    fragmentShader: `uniform float uT; uniform float uHeat; uniform float uStrike; varying vec2 vUv; varying vec3 vN; varying float vD;
      ${NOISE}
      void main() { vec2 q = vUv * vec2(6.0, 3.0) + vec2(uT * 0.18, 0.0);
        float n = fbm(q + vec2(fbm(q * 1.3 - uT * 0.25) * 2.2, fbm(q * 0.9 + uT * 0.2) * 1.4));
        float crust = smoothstep(0.34 - 0.2 * uStrike, 0.62, n);                         // low = cool dark crust, high = open metal
        vec3 cool = vec3(0.10, 0.03, 0.02), mid = vec3(1.0, 0.28, 0.04), hot = vec3(1.0, 0.82, 0.38), white = vec3(1.0, 0.97, 0.8);
        vec3 c = mix(cool, mid, crust); c = mix(c, hot, smoothstep(0.55, 0.8, n + uStrike * 0.25)); c = mix(c, white, smoothstep(0.8, 1.0, n + uStrike * 0.5));
        float rim = pow(1.0 - abs(vN.z), 2.0);
        gl_FragColor = vec4(c * (0.5 + 2.4 * crust * (0.6 + uHeat) + 1.6 * uStrike) + vec3(1.0, 0.4, 0.1) * rim * 0.5 * crust, 1.0); }` });

  // ---- where it stands: on the rim, opposite the first brazier, facing the middle
  const ang = Math.PI * 0.82, dist = R + 5.6, px = Math.cos(ang) * dist, pz = Math.sin(ang) * dist;
  group.position.set(px, 0, pz); group.rotation.y = -ang + Math.PI / 2; group.scale.setScalar(1.4); scene.add(group);

  // ---- the anvil (bronze): base, waist, face, horn
  const anvil = new THREE.Group(); anvil.position.set(0, 0, 0.4); group.add(anvil);
  const box = (w, h, d, m, x, y, z) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); anvil.add(b); return b; };
  box(1.7, 0.42, 1.0, iron, 0, 0.21, 0);                                  // the block it sits on
  box(1.1, 0.5, 0.62, bronze, 0, 0.67, 0);                                // the waist
  box(1.9, 0.3, 0.8, bronze, 0, 1.07, 0);                                 // the face
  const horn = new THREE.Mesh(new THREE.ConeGeometry(0.34, 1.0, lite ? 10 : 16), bronze); horn.rotation.z = Math.PI / 2; horn.position.set(-1.45, 1.07, 0); anvil.add(horn);
  box(0.5, 0.26, 0.74, bronze, 1.1, 1.0, 0).rotation.z = -0.35;           // the heel
  // ---- the molten ingot on the face
  const ingot = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.2, 0.42, lite ? 6 : 14, 3, lite ? 3 : 6), molten); ingot.position.set(0.1, 1.33, 0); anvil.add(ingot);
  // ---- the hammer: a handle on a pivot behind the anvil, an iron head with a bronze band
  const pivot = new THREE.Group(); pivot.position.set(1.3, 2.3, 0.15); anvil.add(pivot);
  const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.065, 1.8, 10), new THREE.MeshStandardMaterial({ color: 0x4a2c16, roughness: 0.7, metalness: 0.05 }));
  handle.rotation.z = Math.PI / 2; handle.position.set(-0.85, 0, 0); pivot.add(handle);
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.36, 0.36), iron); head.position.set(-1.8, 0, 0); pivot.add(head);
  const band = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.4, 0.4), bronze); band.position.set(-1.8, 0, 0); pivot.add(band);

  // ---- the hearth arch behind it (soot stone): two piers, a lintel, a keystone, the furnace mouth
  const arch = new THREE.Group(); arch.position.set(0, 0, -2.4); group.add(arch);
  const pier = (x) => { const p = new THREE.Mesh(new THREE.BoxGeometry(0.9, 4.4, 0.9), soot); p.position.set(x, 2.2, 0); arch.add(p); const cap = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.25, 1.1), bronze); cap.position.set(x, 4.45, 0); arch.add(cap); };
  pier(-2.2); pier(2.2);
  const lintel = new THREE.Mesh(new THREE.BoxGeometry(5.8, 0.8, 1.0), soot); lintel.position.set(0, 4.95, 0); arch.add(lintel);
  const key = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1.2, 1.1), bronze); key.position.set(0, 4.95, 0); arch.add(key);
  const wall = new THREE.Mesh(new THREE.BoxGeometry(3.6, 4.0, 0.6), soot); wall.position.set(0, 2.1, -0.5); arch.add(wall);
  const mouth = new THREE.Mesh(new THREE.PlaneGeometry(2.7, 2.2, 1, 1), new THREE.ShaderMaterial({ uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform float uT; uniform float uHeat; varying vec2 vUv; ${NOISE}
      void main(){ float n = fbm(vec2(vUv.x * 4.0, vUv.y * 3.0 - uT * 0.9)); float up = 1.0 - vUv.y;
        float arc = smoothstep(0.0, 0.12, vUv.x) * smoothstep(1.0, 0.88, vUv.x) * smoothstep(0.0, 0.1, vUv.y);
        vec3 c = mix(vec3(1.0, 0.2, 0.03), vec3(1.0, 0.8, 0.35), pow(up, 1.6) * n * 1.6);
        gl_FragColor = vec4(c * (0.6 + 1.7 * n) * (0.7 + uHeat) * arc * (0.35 + 0.65 * up), 1.0); }` }));
  mouth.position.set(0, 1.5, 0.12); arch.add(mouth);
  const fire = new THREE.PointLight(0xff7a22, lite ? 0 : 16, 14, 1.7); fire.position.set(0, 1.6, 0.8); arch.add(fire);
  const strikeLight = new THREE.PointLight(0xffc070, 0, 9, 1.8); strikeLight.position.set(0.1, 1.9, 0.4); anvil.add(strikeLight);
  // ---- a tapered chimney of dark stone above the lintel
  const chim = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.6, 3.4, 4, 1, true), soot); chim.rotation.y = Math.PI / 4; chim.position.set(0, 6.9, -0.3); arch.add(chim);

  // ---- the beat: the hammer lifts for 1.7 s, falls fast, rests; the ingot flares and the light kicks on the blow
  const CYCLE = 3.6;
  let strikes = 0, lastPhase = 0, fxNames = [], fxList = [], sparks = null;
  const world = (v) => group.localToWorld(v.clone());
  function update(t, still) {
    U.uT.value = t;
    const ph = still ? 0.15 : (t % CYCLE) / CYCLE, sm = (u) => u * u * (3 - 2 * u);
    // a = 0 raised .. 1 on the ingot: it falls in 0.12 of the beat (the blow lands at 0.12), rests, then lifts slowly and holds
    const a = ph < 0.12 ? (ph / 0.12) ** 2 : ph < 0.2 ? 1 : ph < 0.75 ? 1 - sm((ph - 0.2) / 0.55) : 0;
    pivot.rotation.z = -0.9 + 1.29 * a;                                      // the head hangs on the -x side: negative = up
    if (!still && lastPhase < 0.12 && ph >= 0.12) { strikes++; U.uStrike.value = 1; sparkBurst(); }
    lastPhase = ph;
    U.uStrike.value *= still ? 0 : 0.93;
    U.uHeat.value = 0.4 + 0.15 * Math.sin(t * 0.7);
    strikeLight.intensity = lite ? 0 : U.uStrike.value * 26;
    fire.intensity = lite ? 0 : 14 + 3 * Math.sin(t * 7.1) + 2 * Math.sin(t * 13.3);
  }
  function sparkBurst() {
    const FX = window.OLYMPUS_FX;
    if (!FX || !FX.sparkleBurst || lite) return;
    try { const v = world(new THREE.Vector3(0.1, 1.5, 0.4)); const e = FX.sparkleBurst(scene, { position: [v.x, v.y, v.z], color: '#ffb44a' }); if (e && e.stop) setTimeout(() => { try { e.stop(); } catch (_) { /* gone */ } }, 1200); } catch (_) { /* optional */ }
  }

  /** the OLYMPUS effects, each optional: embers rising from the furnace mouth and the ingot, the heat haze over the hearth, smoke along the floor, light shafts */
  async function attachFx(FX) {
    if (!FX) return [];
    try { await FX.load('3d'); } catch (_) { return []; }
    const add = (name, target, opts) => { try { if (typeof FX[name] === 'function') { const e = FX[name](target, opts); fxList.push(e); fxNames.push(name); } } catch (_) { /* an effect failing never stops the forge */ } };
    const m = world(new THREE.Vector3(0, 1.6, -2.4)), a = world(new THREE.Vector3(0.1, 1.4, 0.4));
    add('embers', scene, { center: [m.x, m.y, m.z], count: lite ? 80 : 220 });
    add('heatShimmer', scene, { position: [m.x, 0.2, m.z], height: 4 });
    add('volumetricFog', scene, { size: R * 2.6, density: 0.35 });
    add('godRays', scene, { position: [px * 0.3, 14, pz * 0.3], intensity: 0.45 });
    void a;
    return fxNames;
  }
  function dispose() { for (const e of fxList) { try { e.stop(); } catch (_) { /* gone */ } } scene.remove(group); }
  return { group, update, attachFx, dispose, get strikes() { return strikes; }, get fxNames() { return fxNames.slice(); }, uniforms: U, pos: [px, pz] };
}
