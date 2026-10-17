// Shared helpers for the Liquidity Engine 3D icon scenes.
// Key trick: the harness composer has no MSAA, so each scene renders itself into a
// supersampled + multisampled HDR target and hands the harness a single full-screen
// quad (vignette, film grain, faint chromatic aberration baked in). Bloom/ACES still
// come from the harness.

export const C = {
  magenta: 0xff2bd6, hotpink: 0xff5ce1, violet: 0x8b5cf6, purple: 0x6d28d9,
  deep: 0x12031f, cyan: 0x22d3ee, ice: 0xbff6ff,
};

export const col = (THREE, hex, k = 1) => new THREE.Color(hex).multiplyScalar(k);

// Studio environment for chrome / glass: dark gradient dome + narrow neon strip softboxes.
export function makeEnv(THREE, renderer, { panels = [], top = 0x1a0830, bottom = 0x020104, horizon = 0x2a0b45, extra = null, res = 256 } = {}) {
  const s = new THREE.Scene();
  const dome = new THREE.Mesh(new THREE.SphereGeometry(50, 32, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: { top: { value: new THREE.Color(top) }, bottom: { value: new THREE.Color(bottom) }, horizon: { value: new THREE.Color(horizon) } },
    vertexShader: 'varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform vec3 top, bottom, horizon; varying vec3 vP;
      void main(){ float y = vP.y; vec3 c = y > 0. ? mix(horizon, top, smoothstep(0., .8, y)) : mix(horizon, bottom, smoothstep(0., .35, -y));
      gl_FragColor = vec4(c, 1.); }`,
  }));
  s.add(dome);
  for (const p of panels) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(p.w, p.h), new THREE.MeshBasicMaterial({ color: col(THREE, p.c, p.i), side: THREE.DoubleSide }));
    m.position.set(...p.pos); m.lookAt(0, 0, 0); if (p.rz) m.rotateZ(p.rz); s.add(m);
  }
  if (extra) extra(s);
  const pm = new THREE.PMREMGenerator(renderer); let t;
  if (res > 256) { // sharper reflections: capture at higher res, then prefilter
    const crt = new THREE.WebGLCubeRenderTarget(res, { type: THREE.HalfFloatType });
    new THREE.CubeCamera(0.1, 100, crt).update(renderer, s);
    t = pm.fromCubemap(crt.texture).texture; crt.dispose();
  } else t = pm.fromScene(s, 0.015).texture;
  pm.dispose();
  return t;
}

// Full-screen background drawn behind everything (float precision, dithered: no banding).
export function backdrop(THREE, { inner = 0x2a0a4a, outer = 0x020005, center = [0.5, 0.55], radius = 0.75, k = 1, glow = null } = {}) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
    depthTest: false, depthWrite: false,
    uniforms: {
      inner: { value: col(THREE, inner, k) }, outer: { value: new THREE.Color(outer) }, ctr: { value: new THREE.Vector2(...center) }, rad: { value: radius },
      gcol: { value: glow ? col(THREE, glow.c, glow.i) : new THREE.Color(0) }, gpos: { value: new THREE.Vector2(...(glow?.pos || [0.5, 0.5])) }, gsz: { value: new THREE.Vector2(...(glow?.size || [0.3, 0.1])) },
    },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 1., 1.); }',
    fragmentShader: `uniform vec3 inner, outer, gcol; uniform vec2 ctr, gpos, gsz; uniform float rad; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }
      void main(){ float r = length(vUv-ctr)/rad; vec3 c = mix(inner, outer, smoothstep(0., 1., r));
        vec2 g = (vUv-gpos)/gsz; c += gcol*exp(-dot(g,g));
        c += (h(vUv*1024.)-.5)*0.004; gl_FragColor = vec4(max(c, 0.), 1.); }`,
  }));
  m.frustumCulled = false; m.renderOrder = -1000;
  return m;
}

// Soft radial glow texture (for flares / bokeh). Linear-ish falloff baked in a float canvas.
let _glowTex = null;
export function glowTexture(THREE) {
  if (_glowTex) return _glowTex;
  const n = 128, data = new Float32Array(n * n * 4);
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const dx = (x + 0.5) / n * 2 - 1, dy = (y + 0.5) / n * 2 - 1, r = Math.sqrt(dx * dx + dy * dy);
    const v = r >= 1 ? 0 : Math.pow(1 - r, 2.2) * 0.75 + Math.exp(-r * r * 60) * 0.6;
    const i = (y * n + x) * 4; data[i] = data[i + 1] = data[i + 2] = 1; data[i + 3] = Math.min(1, v);
  }
  const t = new THREE.DataTexture(data, n, n, THREE.RGBAFormat, THREE.FloatType);
  t.magFilter = t.minFilter = THREE.LinearFilter; t.needsUpdate = true; _glowTex = t; return t;
}

export function glowSprite(THREE, hex, k, sx, sy = sx) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(THREE), color: col(THREE, hex, k), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false }));
  s.scale.set(sx, sy, 1); return s;
}

// A lens-flare burst: hot core, soft halo, anamorphic streak, thin cross spikes.
export function flare(THREE, { core = 0xffffff, tint = 0x22d3ee, k = 1, scale = 1, streak = 1, spikes = true } = {}) {
  const g = new THREE.Group();
  g.add(glowSprite(THREE, tint, 0.9 * k, 1.3 * scale));
  g.add(glowSprite(THREE, tint, 1.6 * k, 0.55 * scale));
  g.add(glowSprite(THREE, core, 3.2 * k, 0.16 * scale));
  if (streak) {
    g.add(glowSprite(THREE, tint, 1.2 * k * streak, 3.2 * scale * streak, 0.045 * scale));
    g.add(glowSprite(THREE, core, 1.4 * k * streak, 1.1 * scale * streak, 0.02 * scale));
  }
  if (spikes) {
    const v = glowSprite(THREE, core, 1.0 * k, 0.025 * scale, 0.9 * scale); g.add(v);
  }
  return g;
}

// Render the real scene supersampled into HDR, return a quad scene for the harness.
// scale = supersampling factor (URL ?ss= overrides it); integer scales use an N x N box filter on texel centres.
export function present(THREE, renderer, scene, camera, size, { scale = 2, samples = 4, frames = 2, vignette = 0.45, grain = 0.01, ca = 0.6, lift = 0 } = {}) {
  const qs = new URLSearchParams(location.search);
  if (qs.get('ss')) { scale = +qs.get('ss'); if (scale >= 3) samples = 0; }
  const W = Math.round(size * scale), NT = Math.max(1, Math.round(scale));
  const rt = new THREE.WebGLRenderTarget(W, W, { type: THREE.HalfFloatType, samples });
  rt.texture.minFilter = rt.texture.magFilter = THREE.LinearFilter;
  for (let i = 0; i < frames; i++) { renderer.setRenderTarget(rt); renderer.clear(); renderer.render(scene, camera); }
  renderer.setRenderTarget(null);
  const q = new THREE.Scene();
  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
    depthTest: false, depthWrite: false, defines: { NT },
    uniforms: { t: { value: rt.texture }, px: { value: 1 / size }, vig: { value: vignette }, grain: { value: grain }, ca: { value: ca }, lift: { value: lift } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }',
    fragmentShader: `uniform sampler2D t; uniform float px, vig, grain, ca, lift; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }
      vec3 S(vec2 uv){ vec3 a = vec3(0.);
        for (int i = 0; i < NT; i++) for (int j = 0; j < NT; j++) {
          vec2 o = (vec2(float(i), float(j)) + 0.5) / float(NT) - 0.5;
          a += texture2D(t, uv + o*px).rgb; }
        return a / float(NT*NT); }
      void main(){
        vec2 d = vUv-.5; float r2 = dot(d,d);
        vec2 off = d*r2*ca*px*40.;
        vec3 c = ca > 0. ? vec3(S(vUv-off).r, S(vUv).g, S(vUv+off).b) : S(vUv);
        c *= mix(1., smoothstep(0.95, 0.15, sqrt(r2)*1.414), vig);
        c += lift*vec3(0.010,0.004,0.018);
        c += (h(vUv*vec2(1733.,1931.))-.5)*grain*(0.25+c);
        gl_FragColor = vec4(max(c,0.), 1.); }`,
  }));
  quad.frustumCulled = false; q.add(quad);
  return { scene: q, camera: cam };
}
