# OLYMPUS render core

One premium three.js pipeline for every OLYMPUS app and Jarvis, so no scene looks like "Play-Doh" (flat materials, no
environment light, no tone mapping, no bloom, no anti-aliasing). It lives in `tools/web_public/olympus/`:

| File | What it is |
|---|---|
| `render.js` | `createRenderer()`: tone mapping, environment light, bloom, anti-aliasing, grain / vignette / aberration, quality tiers, the hidden-tab pause |
| `materials.js` | procedural, theme-aware surfaces: marble, gold / chrome / gunmetal, holographic glass, neon, a fresnel rim, nebula, starfield, energy beam |
| `three-addons/` | the three.js addons the core uses (composer, render pass, bloom, studio environment), vendored from `three@0.160.0` (the same r160 as `jarvis/three.module.min.js`, see `VERSION`, MIT `LICENSE`); imports rewritten to `../../jarvis/three.module.min.js`. No CDN. FXAA and the output transform are folded into the core's own finish pass, so SMAA / FXAA / OutputPass are not vendored. |
| `render-lab.html` | every material on the pipeline. `?q=ultra\|high\|low\|off` picks the tier, `?flat=1` draws the old flat look, `?still=1` draws one frame |

Test: `python -X utf8 -m tests.test_olympus_render` (the build, the pass count per tier, tier switching, the automatic
step down, the hidden-tab pause, every material compiling, no console error, no request off the site).

## Adopting it in an app (about 10 lines)

```js
import * as THREE from '../jarvis/three.module.min.js';
import { createRenderer } from '../olympus/render.js';
import { marble, metal, glass, neon, starfield } from '../olympus/materials.js';

const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200);
const rc = createRenderer({ canvas: document.querySelector('#view'), scene, camera });   // quality + theme follow OLYMPUS
scene.add(new THREE.Mesh(new THREE.SphereGeometry(1, 64, 32), glass({ rim: '#7fe9ff' })));
const stars = starfield(); scene.add(stars);
rc.start((dt, t) => { stars.update(t, rc.renderer.getPixelRatio()); });          // no frame while the tab is hidden
```

That replaces the app's `new WebGLRenderer(...)`, its `setPixelRatio` / `setSize` / resize handler, its quality switch
and its frame loop. If the app keeps its own loop, call `rc.render()` in it instead of `renderer.render(scene, camera)`;
it returns `false` and draws nothing while the tab is hidden. `createRenderer` also calls `OLYMPUS.track(renderer)`, so
the loading veil lifts on the first frame and `OLYMPUS.stats()` keeps working.

### Options

| Option | Default | Use |
|---|---|---|
| `canvas`, `context` | | the canvas (and an existing WebGL context) to draw into |
| `renderer` | | reuse a `WebGLRenderer` you made instead (Jarvis's core does this) |
| `quality` | `OLYMPUS.fx()`, followed live | force a tier: `'ultra' \| 'high' \| 'low' \| 'off'` |
| `theme` | `OLYMPUS.theme()`, followed live | the tokens for the environment's colours; `tint` = the app's colour on the default theme |
| `env` | `'night'` | `'night'` (a procedural sky + soft light strips in the theme colours), `'room'` (three's studio), `'none'` |
| `background` | false | the environment is also the visible sky |
| `alpha` | false | a transparent canvas; glows add light to the page behind it |
| `exposure` | 1 | tone-mapping exposure |
| `space` | `'linear'` | `'linear'`: light adds up in linear HDR and is tone-mapped once, at the end (physically right: use it for new scenes). `'display'`: every material tone-maps itself and additive glows add up on screen colours, the way a scene tuned for a plain renderer looks (Jarvis's reactor); bloom thresholds are then 0..1 screen values |
| `bloom` | the tier's | `{ strength, radius, threshold }` overrides |
| `grade` | the tier's | `{ grain, vignette, aberration, saturation }` overrides (0 turns one off; saturation 1 = none, the tiers use 1.1 to give back what ACES greys) |
| `adapt` | true | step down on slow frames when the owner has not chosen a level; `'always'`; `false` |
| `maxDpr` | 2 | a lower pixel-ratio cap (a soft backdrop can use 1) |
| `autoSize` | true | size from the canvas's CSS box every frame (cheap: only a change resizes); false = `resize(w, h)` |
| `fitCamera` | true | keep a perspective camera's aspect in step with the canvas |
| `onQuality(level)` | | told after every tier change |

### The object it returns

`renderer`, `composer` (null on `off`), `scene`, `camera`, `render()`, `resize(w?, h?)`, `setQuality(level)`,
`quality()`, `passes()` (e.g. `['scene', 'bloom', 'finish']`), `setTheme(tokens)`, `setBloom({ strength, radius,
threshold, tint })` (live, no rebuild; a per-frame `tint` is cheap: the reactor tints its glow with the state's colour),
`addPass(pass)` (runs after bloom, before the finish), `start(cb)` / `stop()`, `stats()` and `dispose()`.

## Tier policy: `?q=`, software GL

| Rule | What it does |
|---|---|
| `?q=ultra\|high\|low\|off` in the page address | forces that tier over the kit (tests, screenshots, perf probes); `rc.forced` holds it. `render-lab.html` and every app that uses `createRenderer` honour it |
| software GL (SwiftShader, llvmpipe: no GPU) | held to LITE when the tier comes from the kit (4x MSAA + bloom is a slideshow there); `rc.software` says so. `?gpu=1` lifts the cap (tests that need the kit's HD tier) |
| `quality:` option | an app's own forced tier, as before (nothing capped) |

Apps that switch tiers themselves (a LITE toggle) use `rc.forced || (rc.software ? 'low' : ...)`. `forcedTier()` and
`softwareGL(gl)` are exported for pages without a core. Oracle, Odeon and Fates use it; the other apps are unchanged.

## The tiers

| Tier | Passes per frame | Anti-aliasing | Bloom | Grade | Pixel ratio |
|---|---|---|---|---|---|
| ultra | 3: scene, bloom, finish | 4x MSAA (WebGL2) | half resolution, strength 0.95 | grain, vignette, aberration | ≤ 2 |
| high | 3: scene, bloom, finish | 4x MSAA (WebGL2) | half resolution, strength 0.85 | grain, vignette, light aberration | ≤ 2 |
| low | 2: scene, finish | FXAA inside the finish pass | none | grain, vignette | ≤ 1.5 |
| off | 1: straight to the screen | none | none | none | 1 |

- Every tier tone-maps with ACES filmic, outputs sRGB and lights Standard / Physical materials from the PMREM
  environment. Lights are physically based (r160's default).
- The **finish pass** is one draw: tone mapping, sRGB, vignette, film grain and chromatic aberration (or FXAA on low).
- **Bloom is selective by brightness:** only what is brighter than about 0.85 in linear HDR blooms. Use `neon()`
  (colour × intensity > 1) or `emissiveIntensity > 1` for things that should glow, and keep matte things under 1.
- **Automatic step down:** a mean frame slower than 24 ms over 60 frames (after 45 warm-up frames) steps ultra → high →
  low, never lower, never stored in `jfx`. It only runs when the owner has not chosen a level (the kit's rule).
- **Hidden tab:** `render()` draws nothing and `start()` asks for no frame until the tab is visible again.
- `prefers-reduced-motion` with no choice starts on low (the kit), and the grain stops moving.

## Budgets (iPhone 13, 60 fps on high)

- At most **3 full-screen passes** on high (scene + half-resolution bloom + finish), 2 on low.
- **MSAA memory:** only the scene buffer is multisampled. A full-screen app at pixel ratio 2 on an iPhone 13 costs about
  60 MB for it; a smaller canvas (Jarvis's core) much less. If an app is full screen and heavy, pass `maxDpr: 1.5`.
- **No transmission by default.** `glass()` is reflections + iridescence + a fresnel rim (no extra scene render).
  `glass({ transmission: true })` re-renders the scene behind it: one hero object at most, high and ultra only.
- **Textures:** everything is procedural; the only generated textures are a 128 px brushed-metal map and a 128 px cloud
  puff, shared by every material.
- Draw calls go up by the post passes (UnrealBloomPass is ~12 small draws): the kit's per-app budget in
  `tests/test_olympus_kit.py` needs about +15 draw calls for an app that adopts the core.

## Do / don't

| Do | Don't |
|---|---|
| One `createRenderer` per canvas, `dispose()` it when the view goes | Make a second `WebGLRenderer` or `EffectComposer` yourself |
| Let quality and theme come from `OLYMPUS` | Write `localStorage['jfx']` or keep a per-app quality key |
| `MeshStandardMaterial` / `MeshPhysicalMaterial` or `materials.js` for solids | `MeshBasicMaterial` / `MeshLambertMaterial` for solids (flat: no reflections) |
| Vary roughness: polished 0.05-0.2, satin 0.3-0.5, matte 0.7+ | Give everything the same roughness |
| Glow = HDR colour (`neon()`, `emissiveIntensity` 2-6) | Fake glow with big additive sprites on top of bloom |
| `import` from `../olympus/three-addons/` | Load anything from a CDN |
| `rc.render()` or `rc.start()` | `renderer.render()` straight to the screen (no tone mapping, no AA, no bloom) |
| Test with `?q=low` too: LITE must still look good | Rely on bloom for legibility (low has none) |

## Jarvis on the core

| Piece | File | What it does |
|---|---|---|
| The reactor | `jarvis/core-visual.js` | its own renderer through `createRenderer({ renderer, alpha: true, space: 'display', env: 'none' })`: real bloom tinted by the state's colour (violet idle, red listening), 4x MSAA, the film finish. Its tiers follow its own adapt (`setQuality`). If `../olympus/render.js` cannot load, it draws as before. |
| The home backdrop | `jarvis/backdrop.js` | a full-screen 3D space behind the home screen: nebula, starfield, obsidian floor with a neon grid fading into fog, a light shaft and pool on the horizon under the core, halo rings, glass and chrome shards. 30 fps, pixel ratio ≤ 1.25, no frame while an app is open or the tab is hidden, one still frame on `off` / reduced motion. It replaces the flat 2D layers (stars canvas, SVG globe, CSS floor) once its first frame is drawn (`html[data-bg3d="on"]`); without WebGL2 they stay. Loads after the page is idle. |
| The living home | `jarvis/home3d.js` + `home3d.css` | loaded by `backdrop.js` (a dynamic import; it adds objects to the backdrop's own scene and composer, never a renderer, composer or render target). A sky dome by the New York clock (night, pre-market dawn 4:00-9:30, the open, the close and dusk 15:30-18:00, the evening) with a sun and a moon crossing behind the temple; volumetric light shafts (7, 3 on LITE) and dust motes; the floor is glass over a mirrored temple, rings, shards and sun; weather from the VIX (`live.json` `lit.vix`: haze 18+, rain 22+, storm with lightning 28+, severe 35+; none = clear; LITE has no rain); the reactor (state, voice level and the mode's colour move the light, beams, rings and a shockwave); parallax (DeviceOrientation when Tilt is on, else the mouse); animated constellation lines from the core to its orbs with a live status badge on each. Tests: `tests/test_jarvis_home.py`. |
| The portal jump | `jarvis/portal.js` | every time Jarvis opens an app (orb, tile, quick row, voice: they all go through `show()`): tunnel streaks in the app's colour, a ring portal opening, a flash, the app revealed through the ring. 820 ms, a tap or Esc skips, one raw-WebGL shader (no three.js, compiled at idle). Reduced motion or 3D off: a 0.2 s fade. It never delays the app: `show()` opens the frame first. |
| Arena-to-arena transitions | `jarvis/transitions.js` | (2026-11-04) the portal jump hands every app change to this file: each of the 24 apps has its own signature (Oracle lightning, Tyche sea surge, Prometheus fire sweep, Pantheon marble columns, Mind constellation, Daphne laurel, Plutus coins, Athena glyph from particles ...), in the app's colour and glyph, 0.6-1.1 s, over the loading app, tap / Esc skips. The app -> transition table is data (`REGISTRY`: kind, ms, sound cues; an app with no line gets the warp). One reused 2D canvas (1 x 1 after), no WebGL / render target. LITE (3D Low / Off) = a 250 ms colour fade, reduced motion = a 200 ms flat fade. `show()` passes the app we leave (`from`). Test: `tests/test_jarvis_transitions.py`. |

`jarvis/briefing.js` is not part of the render core (the 7 AM ET spoken briefing card and Settings → Jarvis alerts); `index.html` has one hook line in `show()` and the two `<script type="module">` lines before `</body>`.

## Shipping

`tools/build_web_dashboard.py` publishes `olympus/` with its subfolder `three-addons/` (the build now copies an app
folder's subfolders too; before, it copied only top-level files).

## The Jarvis service worker

The new files are part of the Jarvis shell: `./backdrop.js?v=b1`, `./home3d.js`, `./home3d.css`, `./briefing.js`, `./portal.js?v=p1`, `./transitions.js?v=t1`, and (outside `jarvis/`)
`../olympus/render.js`, `../olympus/materials.js` and the nine files of `../olympus/three-addons/` (`EffectComposer.js`,
`RenderPass.js`, `ShaderPass.js`, `MaskPass.js`, `Pass.js`, `CopyShader.js`, `UnrealBloomPass.js`,
`LuminosityHighPassShader.js`, `RoomEnvironment.js`).

## The atmosphere kit: `olympus/fx-atmos.js` (2026-11-04, JOB 4+5)

The materials in `materials.js` make a surface; this file makes the room around it. All shader or tiny generated textures, no files.
Each factory returns `{ object, update(t, pixelRatio), setQuality(level) }` and costs **one draw call**.

| Factory | What it is |
|---|---|
| `dust({ count, box, color, size })` | motes drifting through a box, soft round, twinkling (Points) |
| `embers({ count, origin, spread, rise, colors })` | sparks rising from a point or line, white-hot to dark (Points) |
| `shafts({ count, from, to, width, color, strength })` | god rays: soft additive light shafts through the haze (one merged mesh) |
| `contactAO({ radius, strength })` | a round contact shadow plane to lay under an object |
| `polishedFloor({ size, color, y, roughness })` | a clear-coated, environment-reflecting stone floor with faint scuffs |
| `bronze(o)`, `forgedIron(o)` | the metals the kit lacked (bronze with pitted roughness; iron whose `userData.heat(0..1)` glows) |
| `threadGlow({ color })` | fibre-glow material for ribbons: fresnel + a travelling pulse |

`QUALITY` says what each tier keeps: ultra 100% of the particles, high 80%, low 35% and no shafts, off none (contact shadows stay except off).
`setQuality(list, level)` and `update(list, t, pr)` apply one tier / one frame to a list of effects. Reduced motion: call `update(list, 0)`.
Used by Fates (shafts, dust, spindle sparks, contact shadows, bronze plinth), Labyrinth (polished floor, bronze walls, shafts, dust, gate
embers, bust embers, contact shadows, the danger heat strip) and Hephaestus (polished floor, bevelled forged anvil / ingot / hammer, bronze hoops,
shafts, dust, furnace embers, contact shadows). Draw budget: +6 to +9 calls per scene (Fates stays under 64). Offline: the Jarvis worker and each
app's worker need `../olympus/fx-atmos.js` in their asset list (without it the scene import fails and the page shows its numbers only).

Additive light and transparent canvases (2026-11-04): `fx-atmos.js` draws its additive layers with a custom blend (`SRC_ALPHA, ONE` for colour, `ZERO, ONE`
for alpha), so a scene on a transparent canvas (Plutus, Ares, which set `alpha: true`) shows light and not dark halos where the particles' alpha builds up.
Opaque canvases look the same as before.
