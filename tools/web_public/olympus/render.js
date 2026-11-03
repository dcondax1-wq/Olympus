// OLYMPUS render core (tools/web_public/olympus/render.js, 2026-11-03; docs/OLYMPUS_RENDER.md): one premium, phone-safe
// three.js pipeline for every OLYMPUS app and Jarvis. ES module, three r160 (../jarvis/three.module.min.js), the post passes
// vendored at the same version in ./three-addons/ (no CDN).
//
//   const rc = createRenderer({ canvas, scene, camera });          // quality and theme follow window.OLYMPUS by default
//   rc.start((dt, t) => { /* move things */ });                   // the frame loop: paused while the tab is hidden
//
// What it does for the scene:
//   - ACES filmic tone mapping, sRGB output, physically based lights (r160's default), HDR (half-float) buffers;
//   - an image-based environment (PMREM) so every Standard / Physical material reflects: 'night' (a procedural sky with
//     soft light strips in the theme's colours, the default) or 'room' (three's RoomEnvironment studio) or 'none';
//   - bloom on what is brighter than 1 (UnrealBloomPass at half resolution): emissive / neon parts glow, matte parts do not;
//   - anti-aliasing: 4x MSAA on HD (WebGL2), FXAA folded into the finishing pass on LITE;
//   - one finishing pass: tone mapping + sRGB + vignette + film grain + a touch of chromatic aberration (one draw);
//   - quality tiers from OLYMPUS.fx() (ultra / high / low / off), followed live, stepped down on slow frames when the owner has
//     not chosen a level; pixel ratio <= 2 (<= 1.5 on low, 1 when off); no frame while the tab is hidden.
//
// Passes per frame: ultra / high = 3 (scene, bloom, finish) · low = 2 (scene, finish + FXAA) · off = 1 (straight to screen).

import * as THREE from '../jarvis/three.module.min.js';
import { EffectComposer } from './three-addons/EffectComposer.js';
import { RenderPass } from './three-addons/RenderPass.js';
import { UnrealBloomPass } from './three-addons/UnrealBloomPass.js';
import { Pass, FullScreenQuad } from './three-addons/Pass.js';
import { RoomEnvironment } from './three-addons/RoomEnvironment.js';

export const TIERS = Object.freeze({
  ultra: { dpr: 2, samples: 4, fxaa: false, bloom: { strength: 0.95, radius: 0.62, threshold: 0.82 }, grade: { grain: 0.05, vignette: 0.34, aberration: 0.004, saturation: 1.1 } },
  high: { dpr: 2, samples: 4, fxaa: false, bloom: { strength: 0.85, radius: 0.55, threshold: 0.85 }, grade: { grain: 0.04, vignette: 0.3, aberration: 0.0025, saturation: 1.1 } },
  low: { dpr: 1.5, samples: 0, fxaa: true, bloom: null, grade: { grain: 0.03, vignette: 0.28, aberration: 0, saturation: 1.1 } },
  off: { dpr: 1, samples: 0, fxaa: false, bloom: null, grade: null },
});
export const LEVELS = Object.freeze(['ultra', 'high', 'low', 'off']);
const SLOW_MS = 24;            // a mean frame slower than this (~42 fps) over a window steps the quality down one tier
const WARM_FRAMES = 45, WINDOW = 60;

const kit = () => (typeof window !== 'undefined' && window.OLYMPUS) || null;
const prefersReduced = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } };
const pageHidden = () => { const O = kit(); return O ? O.hidden() : document.hidden === true; };
const levelOf = (q) => (LEVELS.indexOf(q) >= 0 ? q : null);

// ------------------------------------------------------------------ the finishing pass (one draw)
const FINISH_VS = `precision highp float;
uniform mat4 modelViewMatrix; uniform mat4 projectionMatrix; attribute vec3 position; attribute vec2 uv; varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const FINISH_FS = `precision highp float;
uniform sampler2D tDiffuse; uniform vec2 uTexel; uniform float uTime, uGrain, uVignette, uAberration, uSaturation;
varying vec2 vUv;
#include <tonemapping_pars_fragment>
#include <colorspace_pars_fragment>
float luma(vec3 c) { c = c / (1.0 + c); return dot(c, vec3(0.299, 0.587, 0.114)); }   // on a cheap tone curve: HDR-safe
vec4 tap(vec2 uv) { return texture2D(tDiffuse, uv); }
#ifdef FXAA
vec4 fxaa(vec2 uv) {                     // FXAA 3.11 "lite" (5 + 4 taps): an edge-directed blur on contrast edges only
  vec2 p = uTexel;
  float nw = luma(tap(uv + vec2(-1.0, -1.0) * p).rgb), ne = luma(tap(uv + vec2(1.0, -1.0) * p).rgb);
  float sw = luma(tap(uv + vec2(-1.0, 1.0) * p).rgb), se = luma(tap(uv + vec2(1.0, 1.0) * p).rgb);
  vec4 m = tap(uv); float lm = luma(m.rgb);
  float lo = min(lm, min(min(nw, ne), min(sw, se))), hi = max(lm, max(max(nw, ne), max(sw, se)));
  vec2 dir = vec2(-((nw + ne) - (sw + se)), (nw + sw) - (ne + se));
  float reduce = max((nw + ne + sw + se) * 0.03125, 1.0 / 128.0);
  dir = clamp(dir / (min(abs(dir.x), abs(dir.y)) + reduce), -8.0, 8.0) * p;
  vec4 a = 0.5 * (tap(uv + dir * (1.0 / 3.0 - 0.5)) + tap(uv + dir * (2.0 / 3.0 - 0.5)));
  vec4 b = a * 0.5 + 0.25 * (tap(uv - dir * 0.5) + tap(uv + dir * 0.5));
  float lb = luma(b.rgb);
  return (lb < lo || lb > hi) ? a : b;
}
#endif
float hash(vec2 p) { p = fract(p * vec2(443.897, 441.423)); p += dot(p, p.yx + 19.19); return fract((p.x + p.y) * p.x); }
void main() {
  vec2 d = vUv - 0.5;
#ifdef FXAA
  vec4 c = fxaa(vUv);
#else
  vec4 c = tap(vUv);
#endif
#ifdef ABERRATION
  vec2 o = d * uAberration * (0.5 + 2.0 * dot(d, d));     // grows toward the corners, zero in the middle
  c.r = tap(vUv - o).r; c.b = tap(vUv + o).b;
#endif
#ifdef ACES_FILMIC_TONE_MAPPING
  c.rgb = ACESFilmicToneMapping(c.rgb);
#endif
#ifdef SRGB_TRANSFER
  c = sRGBTransferOETF(c);
#endif
  c.rgb = max(mix(vec3(dot(c.rgb, vec3(0.299, 0.587, 0.114))), c.rgb, uSaturation), 0.0);   // ACES greys bright colours: give some back
  c.rgb *= 1.0 - uVignette * smoothstep(0.12, 0.62, dot(d, d) * 1.6);
  float l = dot(c.rgb, vec3(0.299, 0.587, 0.114));
  c.rgb += (hash(gl_FragCoord.xy + fract(uTime) * vec2(97.0, 57.0)) - 0.5) * uGrain * (0.35 + 0.65 * (1.0 - l));
  gl_FragColor = c;
}`;

class FinishPass extends Pass {
  constructor() {
    super();
    this.needsSwap = false;                         // it draws to the screen: the scene buffer stays the composer's read buffer
    this.uniforms = { tDiffuse: { value: null }, toneMappingExposure: { value: 1 }, uTexel: { value: new THREE.Vector2(1, 1) },
      uTime: { value: 0 }, uGrain: { value: 0 }, uVignette: { value: 0 }, uAberration: { value: 0 }, uSaturation: { value: 1 } };
    this.material = new THREE.RawShaderMaterial({ name: 'OlympusFinish', uniforms: this.uniforms, vertexShader: FINISH_VS,
      fragmentShader: FINISH_FS, depthTest: false, depthWrite: false });
    this.quad = new FullScreenQuad(this.material);
    this.key = '';
  }
  configure(renderer, grade, fxaa, display) {
    const u = this.uniforms, g = grade || { grain: 0, vignette: 0, aberration: 0, saturation: 1 };
    u.uGrain.value = g.grain; u.uVignette.value = g.vignette; u.uAberration.value = g.aberration; u.uSaturation.value = g.saturation;
    const defines = {};
    if (fxaa) defines.FXAA = '';
    else if (g.aberration > 0) defines.ABERRATION = '';
    if (!display && renderer.toneMapping === THREE.ACESFilmicToneMapping) defines.ACES_FILMIC_TONE_MAPPING = '';
    if (!display && THREE.ColorManagement.getTransfer(renderer.outputColorSpace) === THREE.SRGBTransfer) defines.SRGB_TRANSFER = '';
    const key = Object.keys(defines).join();
    if (key !== this.key) { this.key = key; this.material.defines = defines; this.material.needsUpdate = true; }
  }
  setSize(w, h) { this.uniforms.uTexel.value.set(1 / Math.max(1, w), 1 / Math.max(1, h)); }
  render(renderer, writeBuffer, readBuffer) {
    this.uniforms.tDiffuse.value = readBuffer.texture;
    this.uniforms.toneMappingExposure.value = renderer.toneMappingExposure;
    renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    this.quad.render(renderer);
  }
  dispose() { this.material.dispose(); this.quad.dispose(); }
}

// ------------------------------------------------------------------ environments (image-based light for reflections)
/** the theme's 3D colours, or the defaults of the OLYMPUS violet night (an app's own tint leads when the theme is default) */
export function palette(theme, tint) {
  const t = theme || {};
  return { sky: t.sky || '#0d0620', fog: t.fog || '#04050c', emissive: t.emissive || tint || '#a855f7', bloom: t.bloom || '#c084fc',
    accent: t.accent || tint || '#a855f7' };
}

const SKY_FS = `uniform vec3 top, mid, low; varying vec3 vDir;
void main() { float y = normalize(vDir).y; vec3 c = y > 0.0 ? mix(mid, top, pow(y, 0.6)) : mix(mid, low, pow(-y, 0.5)); gl_FragColor = vec4(c, 1.0); }`;
const SKY_VS = 'varying vec3 vDir; void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';

/** a procedural night studio: a deep sky gradient and soft light strips (a white key, two coloured rims, a floor bounce) */
function nightScene(pal) {
  const s = new THREE.Scene(), c = (h, k) => new THREE.Color(h).multiplyScalar(k);
  s.add(new THREE.Mesh(new THREE.SphereGeometry(40, 32, 16), new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false,
    uniforms: { top: { value: c(pal.sky, 1.6) }, mid: { value: c(pal.emissive, 0.12).add(c(pal.fog, 0.8)) }, low: { value: c(pal.fog, 0.25) } },
    vertexShader: SKY_VS, fragmentShader: SKY_FS })));
  const strip = (w, h, col, x, y, z) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: col, side: THREE.DoubleSide }));
    m.position.set(x, y, z); m.lookAt(0, 0, 0); s.add(m);
  };
  strip(16, 1.2, c('#ffffff', 7), 0, 12, 4);             // the key: a long soft box overhead, slightly in front
  strip(1.4, 14, c(pal.emissive, 5), -13, 1, -3);       // the rims, in the theme's colours: chrome edges pick them up
  strip(1.4, 14, c(pal.bloom, 4), 13, 2, -4);
  strip(10, 4, c('#ffffff', 1.4), 0, 2, 14);            // a faint fill behind the camera
  strip(20, 6, c(pal.emissive, 0.6), 0, -12, 0);        // the floor bounce
  return s;
}

/** a PMREM environment texture ('night' | 'room'); the caller owns (disposes) it */
export function makeEnvironment(renderer, kind, pal) {
  const pm = new THREE.PMREMGenerator(renderer);
  let src = null, tex = null;
  try {
    src = kind === 'room' ? new RoomEnvironment(renderer) : nightScene(pal || palette());
    tex = pm.fromScene(src, kind === 'room' ? 0.04 : 0.02).texture;
  } finally {
    pm.dispose();
    if (src) src.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
  }
  return tex;
}

// ------------------------------------------------------------------ the pipeline
/**
 * createRenderer({ canvas, scene, camera, quality?, theme?, ...options })
 *   canvas / context / renderer   draw into this canvas (and this WebGL context), or reuse a WebGLRenderer you made
 *   quality   'ultra' | 'high' | 'low' | 'off' (default: OLYMPUS.fx(), followed live via OLYMPUS.onFx)
 *   theme     OLYMPUS theme tokens (default: OLYMPUS.theme(), followed live); tint = the app's colour on the default theme
 *   env       'night' (default) | 'room' | 'none'      background  true: the environment is also the visible sky
 *   alpha     a transparent canvas (glows add light to the page behind); exposure (default 1)
 *   space     'linear' (default: light adds up in linear HDR, tone mapped once at the end) | 'display' (each material tone maps
 *             and encodes itself, additive glows add up on screen colours, as a scene tuned for a plain renderer looks; bloom
 *             thresholds are then 0..1 screen values)
 *   bloom     { strength, radius, threshold } overrides of the tier's values; grade { grain, vignette, aberration } likewise
 *   adapt     step down on slow frames: true (default: only when the owner has not chosen a level) | 'always' | false
 *   maxDpr    a lower pixel-ratio cap than the tier's; autoSize (default true) sizes from the canvas's CSS box
 *   onQuality(level)   told after every tier change (the owner's choice or the automatic step down)
 * -> { renderer, composer, scene, camera, render(), resize(w?, h?), setQuality(level), quality(), passes(), setTheme(t),
 *      addPass(pass), start(cb), stop(), stats(), dispose() }
 */
export function createRenderer(opts) {
  const o = Object.assign({ env: 'night', alpha: false, exposure: 1, adapt: true, autoSize: true, space: 'linear' }, opts || {});
  const display = o.space === 'display';
  const { scene, camera } = o;
  if (!scene || !camera) throw new TypeError('createRenderer: scene and camera are required');
  const O = kit();
  const owned = !o.renderer;
  const renderer = o.renderer || new THREE.WebGLRenderer({ canvas: o.canvas, context: o.context, alpha: !!o.alpha, antialias: false,
    stencil: false, powerPreference: 'high-performance', premultipliedAlpha: true });
  const canvas = renderer.domElement;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = o.exposure;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.info.autoReset = false;                 // the composer draws many times a frame: count the whole frame
  if (o.alpha) renderer.setClearColor(0x000000, 0);
  const gl2 = renderer.capabilities.isWebGL2;
  const floatOK = gl2 && (renderer.extensions.has('EXT_color_buffer_float') || renderer.extensions.has('EXT_color_buffer_half_float'));
  const bufferType = floatOK ? THREE.HalfFloatType : THREE.UnsignedByteType;

  let level = levelOf(o.quality) || (O ? O.fx() : prefersReduced() ? 'low' : 'high');
  let theme = o.theme !== undefined ? o.theme : O ? O.theme() : null;
  let composer = null, bloom = null, finish = null, envTex = null, dead = false, extra = [];
  let width = 0, height = 0, dpr = 1, raf = 0, loop = null, tPrev = 0, firstFrame = true;
  const perf = { last: 0, n: 0, sum: 0, warm: 0, fps: 0, steps: 0 };
  const reduced = prefersReduced();
  const t0 = performance.now();

  function tierOf(l) {
    const base = TIERS[l];
    return { dpr: base.dpr, samples: gl2 ? base.samples : 0, fxaa: base.fxaa,
      bloom: base.bloom && Object.assign({}, base.bloom, o.bloom), grade: base.grade && Object.assign({}, base.grade, o.grade) };
  }
  let tier = tierOf(level);

  function environment() {
    if (envTex) { envTex.dispose(); envTex = null; }
    if (o.env === 'none') return;
    envTex = makeEnvironment(renderer, o.env, palette(theme, o.tint));
    scene.environment = envTex;
    if (o.background) scene.background = envTex;
  }

  function target(samples) {
    const rt = new THREE.WebGLRenderTarget(1, 1, { type: bufferType, samples });
    rt.texture.name = 'olympus.scene';
    if (display) {
      // three r160 tone maps and encodes materials into a target flagged as an XR target (as it does for the screen), and
      // keeps its storage linear: the buffer then holds screen colours, and HDR above 1 where additive glows pile up
      rt.isXRRenderTarget = true;
      rt.texture.colorSpace = THREE.SRGBColorSpace;
    }
    return rt;
  }
  function freeComposer() {
    if (!composer) return;
    composer.passes.forEach((p) => { if (extra.indexOf(p) < 0) p.dispose(); });
    composer.dispose();                              // both buffers and its copy pass
    composer = bloom = finish = null;
  }
  // the composer per tier: the scene goes into renderTarget2 (multisampled on HD), bloom adds onto it, finish reads it
  function build() {
    freeComposer();
    if (level === 'off') return;
    composer = new EffectComposer(renderer, target(0));
    composer.renderTarget2.dispose();
    composer.renderTarget2 = composer.readBuffer = target(tier.samples);
    composer.addPass(new RenderPass(scene, camera));
    if (tier.bloom) {
      const b = tier.bloom;
      bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), b.strength, b.radius, b.threshold);
      // pure additive (one, one) and alpha untouched: a transparent canvas stays transparent, glows light what is behind
      Object.assign(bloom.blendMaterial, { blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
        blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneFactor });
      composer.addPass(bloom);
    }
    extra.forEach((p) => composer.addPass(p));
    finish = new FinishPass();
    finish.configure(renderer, tier.grade, tier.fxaa, display);
    composer.addPass(finish);
    size(true);
  }

  function size(force) {
    const w = o.autoSize ? canvas.clientWidth || canvas.width || 1 : width || canvas.width || 1;
    const h = o.autoSize ? canvas.clientHeight || canvas.height || 1 : height || canvas.height || 1;
    const d = Math.min(window.devicePixelRatio || 1, tier.dpr, o.maxDpr || 2);
    if (!force && w === width && h === height && d === dpr) return;
    width = w; height = h; dpr = d;
    renderer.setPixelRatio(d);
    renderer.setSize(w, h, false);
    if (camera.isPerspectiveCamera && o.fitCamera !== false) { camera.aspect = w / h; camera.updateProjectionMatrix(); }
    if (composer) { composer.setPixelRatio(d); composer.setSize(w, h); }   // every pass gets the buffer size (finish: its texel)
  }

  // slow frames step the quality down one tier (never below low, never stored: the owner's choice stays theirs)
  function adapt(now) {
    const ms = perf.last ? now - perf.last : 0;
    perf.last = now;
    if (!ms || ms > 1000) return;                   // the first frame, or back from a hidden tab
    if (perf.warm < WARM_FRAMES) { perf.warm++; return; }
    perf.sum += ms; perf.n++;
    if (perf.n < WINDOW) return;
    const avg = perf.sum / perf.n;
    perf.fps = Math.round(1000 / avg); perf.sum = perf.n = 0;
    const may = o.adapt === 'always' || (o.adapt && !(O && O.chosen()));
    if (may && avg > SLOW_MS && (level === 'ultra' || level === 'high')) {
      perf.steps++;
      apply(level === 'ultra' ? 'high' : 'low');
      if (O) O.mode(level === 'low');
    }
  }

  function apply(l) {
    level = l; tier = tierOf(l); perf.warm = 0; perf.sum = perf.n = 0;
    build(); size(true);
    if (typeof o.onQuality === 'function') o.onQuality(l);
  }

  /** draw one frame (nothing while the tab is hidden); returns true when it drew */
  function render() {
    if (dead || pageHidden()) return false;
    const now = performance.now();
    adapt(now);
    if (o.autoSize) size(false);
    renderer.info.reset();
    if (composer) {
      composer.readBuffer = composer.renderTarget2; composer.writeBuffer = composer.renderTarget1;   // an app pass may swap
      finish.uniforms.uTime.value = reduced ? 0 : (now - t0) / 1000;
      composer.render();
    } else {
      renderer.setRenderTarget(null);
      renderer.render(scene, camera);
    }
    if (firstFrame) { firstFrame = false; if (O && !renderer.__oly) O.ready(); }
    return true;
  }

  function tick(now) {
    raf = 0;
    if (dead || !loop || pageHidden()) return;          // hidden: no new frame is asked for until the tab is back
    const dt = tPrev ? Math.min(0.1, (now - tPrev) / 1000) : 1 / 60;
    tPrev = now;
    loop(dt, (now - t0) / 1000);
    render();
    raf = requestAnimationFrame(tick);
  }
  const onVisible = () => { if (!pageHidden() && loop && !raf && !dead) { tPrev = 0; perf.last = 0; raf = requestAnimationFrame(tick); } };
  document.addEventListener('visibilitychange', onVisible);

  const followFx = (l) => { if (!dead && levelOf(l) && l !== level) apply(l); };
  const followTheme = (t) => { if (!dead) api.setTheme(t); };
  const backToDefault = () => followTheme(null);
  if (O && !levelOf(o.quality)) O.onFx(followFx);
  if (O && o.theme === undefined) { O.onTheme(followTheme); window.addEventListener('olympus:theme-default', backToDefault); }

  const api = {
    renderer, scene, camera,
    get composer() { return composer; },
    render,
    /** re-measure (or set a fixed size when autoSize is false) */
    resize(w, h) { if (w && h) { width = w; height = h; } size(true); },
    /** 'ultra' | 'high' | 'low' | 'off': the pipeline is rebuilt for that tier */
    setQuality(l) { if (levelOf(l) && l !== level) apply(l); return level; },
    quality: () => level,
    /** the pass names this frame runs, e.g. ['scene', 'bloom', 'finish'] */
    passes: () => (composer ? composer.passes.map((p) => (p === bloom ? 'bloom' : p === finish ? 'finish' : p instanceof RenderPass ? 'scene' : 'app'))
      : ['direct']),
    setTheme(t) { theme = t || null; environment(); },
    /** an app's own pass, run after bloom and before the finish */
    addPass(p) { if (p && extra.indexOf(p) < 0) { extra.push(p); build(); } return p; },
    start(cb) { loop = typeof cb === 'function' ? cb : () => {}; onVisible(); return api; },
    stop() { loop = null; if (raf) cancelAnimationFrame(raf); raf = 0; },
    stats() {
      const i = renderer.info;
      return { quality: level, passes: api.passes().length, names: api.passes(), dpr, samples: composer ? tier.samples : 0,
        bloom: !!bloom, fxaa: !!(composer && tier.fxaa), hdr: bufferType === THREE.HalfFloatType, fps: perf.fps, steps: perf.steps,
        calls: i.render.calls, triangles: i.render.triangles, programs: (i.programs || []).length, env: envTex ? o.env : 'none' };
    },
    dispose() {
      if (dead) return;
      dead = true; api.stop();
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('olympus:theme-default', backToDefault);
      freeComposer(); extra.forEach((p) => p.dispose && p.dispose());
      if (envTex) { if (scene.environment === envTex) scene.environment = null; if (scene.background === envTex) scene.background = null; envTex.dispose(); }
      if (owned) renderer.dispose();
    },
  };

  environment();
  build();
  size(true);
  if (O && O.track && owned) O.track(renderer);
  return api;
}
