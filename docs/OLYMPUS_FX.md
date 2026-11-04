# OLYMPUS effects library

42 reusable, theme-aware, tier-aware visual effects for every OLYMPUS app and Jarvis: cards, buttons, numbers, text, bursts, and
sky / weather / surfaces for three.js scenes on the render core (`docs/OLYMPUS_RENDER.md`). They sit in `tools/web_public/olympus/`
as small modules. Every effect has the same shape:

```js
const fx = OLYMPUS_FX.<name>(el | scene, opts);   // -> { stop(), tier, stopped, set / strike / pulse ... }
fx.stop();                                         // undoes everything the effect made; calling it twice is harmless
```

Try them all: `olympus/fx-lab.html` (a tier switcher, every effect on its own sample or on the 3D stage). `?q=ultra|high|low|off` forces
the stage's render tier, `?bare=1` loads no fx script (only the zero-edit wiring).

| File | What it is |
|---|---|
| `fx-core.js` | classic script, no imports: the registry (`OLYMPUS_FX`), the ONE shared frame loop, the tier rules, canvas / particle caps, cleanup, the `data-oly-fx` wiring |
| `fx-ui.js` | cards and buttons: `gradientBorder shimmer glow tilt magnetic ripple glassSpecular neonPulse skeleton` |
| `fx-text.js` | numbers and text: `odometer countUp typewriter glitch progressRing` |
| `fx-burst.js` | one-shots: `confetti sparkleBurst toast` |
| `fx-three.js` | ES module helpers for the scene effects (GPU particle system, palette from `materials.js`, noise GLSL) |
| `fx-sky.js` | `godRays aurora nebulaDome volumetricFog heatShimmer starWarp lensFlare` |
| `fx-weather.js` | `lightning rain snow embers petals fireflies dust laurelFall fire` |
| `fx-surface.js` | `caustics marbleFloor waterSurface lavaCracks glassPanel hologram glowOutline shockwave lightTrails` |
| `fx-lab.html` | the lab page |

## Using it

```html
<script src="../olympus/olympus.js?v=o2" data-app="mind"></script>   <!-- the kit, already in every app -->
<script src="../olympus/fx-core.js?v=f1"></script>                   <!-- then the files you need (classic scripts) -->
<script src="../olympus/fx-ui.js?v=f1"></script>
```

The scene effects are ES modules and import the core's `OLYMPUS_FX`: `import '../olympus/fx-weather.js';` (after `fx-core.js` is on the page),
or `await OLYMPUS_FX.load('3d')` (also `'ui'`, `'text'`, `'burst'`, `'all'`). A scene effect takes a `THREE.Scene` or `{ scene, camera, renderer }`
(the camera gives `lensFlare` its ghosts, `starWarp` and `nebulaDome` their follow, `marbleFloor` its mirror). Positions and sizes come
from `opts` (`position`, `box`, `center`, `size`, `count`, `color` ...); the defaults suit a scene about 24 units wide.

## The rules every effect follows

| Rule | How |
|---|---|
| **Tiers** | `ultra / high / low / off` from `OLYMPUS.fx()` (the one quality setting Jarvis and every app share, key `jfx`), followed live: a running effect is rebuilt for the new tier (fewer particles, cheaper shaders, no blur on low, nothing on off). The lab's switch pins the tier for the page only (`OLYMPUS_FX.setTier(t)`, never stored). `opts.tier` pins one call |
| **Reduced motion** | `prefers-reduced-motion: reduce` = `off` for every effect, whatever the setting. Effects that carry information give a still version (toast, a number's final value); decoration draws nothing. Lightning never flashes on off / reduced motion |
| **One loop** | one `requestAnimationFrame` for all effects (`ctx.tick`). No frame while the tab is hidden, and the loop sleeps when nothing runs. Low runs at 30 fps. An element effect also sleeps while its element is off screen |
| **Caps** | canvases: pixel ratio <= 2 / 1.5 / 1 (ultra / high / low) and <= 1.6 / 1.1 / 0.52 million backing pixels; particles per effect <= 2000 / 1200 / 400, in one fixed buffer (GPU effects animate in the vertex shader: no per-frame JS work, no allocation); bursts (`confetti`, `sparkleBurst`, `toast`) keep at most 3-4 alive |
| **Cleanup** | everything an effect makes (listeners, timers, canvases, nodes, classes, inline styles, scene objects, geometries, materials, textures) is registered with its context and undone by `stop()`. A page error inside an effect stops that effect only |
| **Theme** | colours come from the OLYMPUS theme (`--oly-accent-rgb`, `materials.js` `colors()`); a theme change rebuilds the 3D effects, the CSS ones follow by themselves |

Cost on an iPhone: the 2D / UI part (core + ui + text + burst, about 60 KB, 18 KB gzipped) loads no three.js; the 3D files add about 55 KB (16 KB gzipped) over the render core.
Rough price per effect (draw calls): the particle effects are 1 call, `rain` 1, `godRays` 3-9 cones, `volumetricFog` 3-7 sheets, `marbleFloor` 2 + a half-resolution
mirror pass (ultra / high only), `lightning` 1 + two lights (they make the scene's lit materials compile once).

## Zero-edit wiring: `data-oly-fx`

Any element in any app gets an effect from an attribute, no code and no edit in the app folder:

```html
<div class="card" data-oly-fx="shimmer">...</div>        <!-- CSS only: a light sweep -->
<button data-oly-fx="ripple">Buy</button>                  <!-- a ring from the tap point -->
<div class="card" data-oly-fx="tilt">...</div>             <!-- leans toward the finger -->
<b class="pnl" data-oly-fx="odometer">+$1,284</b>          <!-- digits roll whenever the app writes a new number -->
<span class="chip" data-oly-fx="glow">LIVE</span>          <!-- CSS only: a breathing accent glow -->
```

`olympus.css` styles `shimmer`, `glow` and `ripple` (zero specificity, so an app's own rule always wins; shimmer draws on `::after` and ripple on `::before`,
so leave those two off an element whose pseudo-elements the app already uses). `olympus.js` loads `fx-core.js` plus the file that holds the others
(`fx-ui.js` for `tilt magnetic ripple gradientBorder glassSpecular neonPulse skeleton`, `fx-text.js` for `odometer countUp typewriter glitch progressRing`)
on the first use, wires elements added later, stops the effect of a removed element, follows the tier (low = a still sheen, off = nothing) and
`prefers-reduced-motion`. A page without the attribute, or with effects off, loads nothing. Options go in `data-oly-fx-opts='{"max":6}'`; several effects in one
attribute: `data-oly-fx="tilt ripple"`.

**Opt out**

| Scope | How |
|---|---|
| one element, or a whole subtree | `data-oly-fx-off` on the element or any ancestor |
| the whole page | `<html data-oly-fx-ui="off">`, `<meta name="olympus-fx-ui" content="off">`, or `OLYMPUS.fxUI(false)` (`true` brings it back) |
| everything animated | Jarvis's 3D effects level `off` (or reduced motion) |

## Writing a new effect

```js
OLYMPUS_FX.define('name', { kind: 'el' | 'scene', group, desc, global?, max?, make(target, opts, ctx) { ...; return { stop?, set? ... }; }, still?(target, opts, ctx) });
// ctx: tier, pick(u, h, l), count(u, h, l) (a particle count under the cap), tick(fn(dt, t)), ticker(fn), on(target, ev, fn), timeout(fn, ms),
//      node(tag, cls, parent), cls(el, c), style(el, props), canvas(host, { fixed, rect }), scene(scene, obj), free(obj), add(cleanup), finish()
```

`make` runs for ultra / high / low; `still` (optional) runs for off and reduced motion, and without it the effect simply does nothing there.
Register every side effect through `ctx` and `stop()` takes care of the rest; `tests/test_olympus_fx.py` checks it for every effect.

## Test

`python -X utf8 -m tests.test_olympus_fx`: every effect on every tier starts and stops without a leak (no ticker, canvas, node, scene object,
geometry or texture left), caps hold, reduced motion = off, the hidden-tab pause, live tier changes through `OLYMPUS.setFx()`, the scene effects are
visible, the lightning flashes, the wiring and its opt-outs, and a page without `data-oly-fx` loads no fx file.

# The effects

## Cards (6)

### `gradientBorder`
An animated conic-gradient border that turns around the element. (element)

```js
const fx = OLYMPUS_FX.gradientBorder(card, { colors: ['#a855f7', '#7fe9ff', '#ffcf5a'], width: 2, seconds: 4 });
// the ring turns by itself; low = still ring
fx.stop();
```

### `shimmer`
A soft light sweep across the element (CSS only). (element)

```js
const fx = OLYMPUS_FX.shimmer(card);   // or just <div data-oly-fx="shimmer"> (no script)
// CSS only: olympus.css draws the sweep on ::after
fx.stop();
```

### `glow`
A breathing accent glow around the element (CSS only). (element)

```js
const fx = OLYMPUS_FX.glow(chip);   // or <span data-oly-fx="glow"> (no script)
// CSS only: a drop-shadow that breathes in the accent colour
fx.stop();
```

### `tilt`
The card leans toward the finger / pointer; children with data-oly-depth shift for parallax. (element)

```js
const fx = OLYMPUS_FX.tilt(card, { max: 10 });   // children with data-oly-depth="2" shift for parallax
// leans toward the finger; eases back on release
fx.stop();
```

### `glassSpecular`
Frosted glass with a lit edge: the highlight follows the pointer (and drifts by itself on ultra). (element)

```js
const fx = OLYMPUS_FX.glassSpecular(panel);
// frosted glass; the lit edge follows the pointer (drifts on ultra, blur 18 / 12 / 0 px by tier)
fx.stop();
```

### `skeleton`
A loading placeholder: the content hides behind a moving sheen until stop(). (element)

```js
const fx = OLYMPUS_FX.skeleton(card);   // the content hides behind a moving sheen
// when the data is in:
fx.stop();
```

## Buttons (3)

### `magnetic`
The button leans toward a nearby pointer and presses in on tap. (element)

```js
const fx = OLYMPUS_FX.magnetic(button, { strength: 0.3, radius: 80 });
// mouse / pen only; a tap presses the button in
fx.stop();
```

### `ripple`
A light ring grows from the tap point. (element)

```js
const fx = OLYMPUS_FX.ripple(button);   // or <button data-oly-fx="ripple">
// the ring starts at the tap point; fx.pulse() fires one from code
fx.stop();
```

### `neonPulse`
A neon edge that breathes (static on low). (element)

```js
const fx = OLYMPUS_FX.neonPulse(button, { color: '#ff4d6d', seconds: 2.4 });
// no colour = the theme's accent; low = a steady glow
fx.stop();
```

## Numbers (3)

### `odometer`
Digits roll like an odometer whenever the element's number changes (watches the text, so app code needs no change). (element)

```js
const fx = OLYMPUS_FX.odometer(numberEl);   // or <b data-oly-fx="odometer">
numberEl.textContent = '1,291';   // the app's normal write: the digits roll to it
fx.stop();
```

### `countUp`
The number counts up from 0 (or opts.from) to its value with an ease-out; set(v) counts on to a new value. (element)

```js
const fx = OLYMPUS_FX.countUp(el, { to: 12840, duration: 1.2 });   // from 0, keeps $ , . % in the text
fx.set(15200);   // counts on to a new value
fx.stop();
```

### `progressRing`
A ring that fills to opts.value (0..1) with a glowing comet tip; set(v) animates to a new value. (element)

```js
const fx = OLYMPUS_FX.progressRing(host, { value: 0.4, stroke: 6 });   // host: a sized element
fx.set(0.9);   // glides there, the comet tip leads
fx.stop();
```

## Text (2)

### `typewriter`
Types its text out with a blinking caret (opts.text, opts.cps, opts.loop). (element)

```js
const fx = OLYMPUS_FX.typewriter(el, { text: 'Good evening.', cps: 30, loop: false });
fx.set('Next line');   // types a new line
fx.stop();
```

### `glitch`
Short RGB-split glitch bursts at random moments (opts.every in seconds, pulse() for one now). (element)

```js
const fx = OLYMPUS_FX.glitch(title, { every: 3 });   // a burst every ~3 s
fx.pulse();   // one now
fx.stop();
```

## Bursts (3)

### `confetti`
A burst of confetti from the element (or the top of the screen); it falls, fades and removes itself. (element)

```js
const fx = OLYMPUS_FX.confetti(button, { count: 160 });   // bursts from the element, removes itself
// colours = the theme's accent + a party palette; opts.colors to change
fx.stop();
```

### `sparkleBurst`
A quick burst of four-point sparks from the element or from opts.x / opts.y. (element)

```js
const fx = OLYMPUS_FX.sparkleBurst(el);   // or { x, y } for a point
// four-point sparks, ~0.75 s, removes itself
fx.stop();
```

### `toast`
A glass toast that drops in from the top with a spark on its icon, then leaves by itself (opts.text, kind ok|bad|warn, seconds). (element)

```js
const fx = OLYMPUS_FX.toast(document.body, { text: 'Order filled: +2.4R', kind: 'ok', seconds: 3.2 });
// kind: ok | bad | warn | (none); max 3 on screen; shown plain (no motion) when effects are off
fx.stop();
```

## Sky and light (7)

### `godRays`
Volumetric light shafts falling from a source (soft additive cones that sway). (3D scene)

```js
const fx = OLYMPUS_FX.godRays(scene, { position: [3, 11, -3], intensity: 0.7 });
// soft shaft cones that sway; the render core's bloom lifts them
fx.stop();
```

### `aurora`
Aurora borealis curtains rippling across the sky, in the theme's colours. (3D scene)

```js
const fx = OLYMPUS_FX.aurora(scene, { position: [0, 17, -40] });
// curtains in the theme's colours; opts.colors = 3 colours
fx.stop();
```

### `nebulaDome`
A full sky dome of drifting nebula clouds (procedural, follows the camera). (3D scene)

```js
const fx = OLYMPUS_FX.nebulaDome({ scene, camera });
// a sky dome that follows the camera; give it the camera or it stays put
fx.stop();
```

### `volumetricFog`
Layers of drifting ground fog (stacked noise sheets, themed). (3D scene)

```js
const fx = OLYMPUS_FX.volumetricFog(scene, { size: 30, density: 0.5 });
// stacked drifting noise sheets near the floor (7 / 5 / 3 layers)
fx.stop();
```

### `heatShimmer`
Rising heat haze: wavering warm wisps above a hot surface (a drawn haze, not a refraction pass). (3D scene)

```js
const fx = OLYMPUS_FX.heatShimmer(scene, { position: [-3, 0, 2], height: 4 });
// rising warm haze above a hot spot (a drawn haze, not a refraction pass)
fx.stop();
```

### `starWarp`
Stars stream past the camera as streaks (hyperspace); speed() changes the rush. (3D scene)

```js
const fx = OLYMPUS_FX.starWarp({ scene, camera }, { speed: 30 });
fx.set(80);   // faster; streaks follow the camera
fx.stop();
```

### `lensFlare`
A bright glare with a chain of ghost rings across the screen (pass opts.camera or a { scene, camera } target for the ghosts). (3D scene)

```js
const fx = OLYMPUS_FX.lensFlare({ scene, camera }, { position: [6, 6.5, -6] });
// glare + streak + ghost rings across the screen (ghosts need the camera)
fx.stop();
```

## Weather and particles (9)

### `snow`
Soft snow flakes drifting down through a box around the scene (GPU, one buffer). (3D scene)

```js
const fx = OLYMPUS_FX.snow(scene, { count: 1400 });
// soft flakes, drifting; opts.size is the flake width in world units
fx.stop();
```

### `dust`
Slow glittering dust motes floating in the air (GPU, one buffer). (3D scene)

```js
const fx = OLYMPUS_FX.dust(scene);
// slow glittering motes in the air
fx.stop();
```

### `fireflies`
Glowing fireflies that wander and pulse (HDR, so they bloom). (3D scene)

```js
const fx = OLYMPUS_FX.fireflies(scene, { count: 90 });
// wandering, pulsing glows (HDR: they bloom)
fx.stop();
```

### `embers`
Glowing embers rising and cooling from orange to red. (3D scene)

```js
const fx = OLYMPUS_FX.embers(scene, { center: [0, 5, 0] });
// glowing sparks rise and cool from orange to red
fx.stop();
```

### `petals`
Rose petals tumbling down on the breeze. (3D scene)

```js
const fx = OLYMPUS_FX.petals(scene, { color: '#ff9bb5', color2: '#ffe3ec' });
// tumbling petals (normal blending, so they read on bright scenes)
fx.stop();
```

### `laurelFall`
Gold laurel leaves falling for a win (victory moments). (3D scene)

```js
const fx = OLYMPUS_FX.laurelFall(scene);   // for a win
// gold laurel leaves with a midrib, tumbling down
fx.stop();
```

### `fire`
A flame: rising, cooling particles with a flickering light. (3D scene)

```js
const fx = OLYMPUS_FX.fire(scene, { position: [-3, 0, 2], height: 2.6 });
// rising, cooling flame particles + a flickering light (opts.light = 0 for no light)
fx.stop();
```

### `rain`
Slanted rain streaks falling through a box around the scene (GPU line segments). (3D scene)

```js
const fx = OLYMPUS_FX.rain(scene, { count: 1500, color: '#9fc4ff' });
// streaks fall through a box (opts.box, opts.center, opts.vel to shape it)
fx.stop();
```

### `lightning`
A branching bolt every few seconds with a real flash of light on the scene (never on off/reduced motion); strike() fires one now. (3D scene)

```js
const fx = OLYMPUS_FX.lightning(scene, { every: [4, 9], sound: true, onFlash: (f) => {} });
fx.strike();   // one now; flashes the scene (never on off / reduced motion)
fx.stop();
```

## Surfaces and panels (9)

### `caustics`
Rippling water-light caustics dancing on a floor (additive, themed). (3D scene)

```js
const fx = OLYMPUS_FX.caustics(scene, { size: 26 });
// water-light caustics on a floor (5 / 4 / 3 iterations by tier)
fx.stop();
```

### `marbleFloor`
A polished veined-marble floor; on ultra / high it also mirrors the scene (planar reflection, needs opts.renderer or a { scene, camera, renderer } target). (3D scene)

```js
const fx = OLYMPUS_FX.marbleFloor({ scene, camera, renderer }, { size: 24, reflect: 0.5 });
// veined marble; ultra / high also mirror the scene (planar reflection, 512 / 384 px)
fx.stop();
```

### `waterSurface`
A rolling water surface with wave normals, sky reflection and a sun glint. (3D scene)

```js
const fx = OLYMPUS_FX.waterSurface(scene, { size: 26, amplitude: 0.35 });
// rolling waves with sky reflection and a sun glint (160 / 110 / 50 segments)
fx.stop();
```

### `lavaCracks`
A dark crust with glowing lava cracks that flow and pulse (HDR, so the cracks bloom). (3D scene)

```js
const fx = OLYMPUS_FX.lavaCracks(scene, { size: 20 });
// dark crust, flowing glowing cracks (HDR: they bloom)
fx.stop();
```

### `glassPanel`
A thick glass pane that refracts what is behind it (transmission on ultra only, a tinted reflective pane on high and low) with a lit edge. (3D scene)

```js
const fx = OLYMPUS_FX.glassPanel({ scene, camera }, { position: [3.6, 2.4, 2], width: 4, height: 2.6 });
// refracting glass (transmission on ultra only, a tinted pane below) with a lit edge
fx.stop();
```

### `hologram`
Scanlines, a rolling light band, fresnel glow and flicker: on opts.target (any Object3D) or as a small hologram projector. (3D scene)

```js
const fx = OLYMPUS_FX.hologram(scene, { target: someMesh });   // or no target: a small projector
// scanlines, a rolling band, fresnel glow, flicker
fx.stop();
```

### `glowOutline`
A pulsing glow outline around opts.target (any Object3D), drawn as a shell behind it so it blooms. (3D scene)

```js
const fx = OLYMPUS_FX.glowOutline(scene, { target: someMesh, color: '#7fe9ff' });
// a pulsing shell behind the target (needs opts.target)
fx.stop();
```

### `shockwave`
An expanding ring of light with a fading wake (a win, a hit, a portal); pulse() fires another, opts.every repeats it. (3D scene)

```js
const fx = OLYMPUS_FX.shockwave(scene, { position: [0, 2, 0], radius: 5, vertical: true });
fx.pulse();   // another ring; opts.every repeats; one-shot otherwise
fx.stop();
```

### Used by the main dashboard's 3D scenes (2026-11-04)
`tools/web_public/fx/src/ambient.js` bundles `fx-core.js`, `fx-three.js` and `fx-sky.js` into `fx.js` (the build's `one-three` alias
points their three import at the bundle's own three) and gives the **Trade Galaxy, Month City and Eval Reactor** dust motes,
fireflies, light shafts and a faint aurora (`FX.sceneAmbient` = the motes, `FX.godRays`, `FX.aurora`, each pinned to the view's own
tier). They exist only while the view is on screen: ultra = motes + fireflies + 3 shafts + 4 aurora curtains (+8 draw calls), high =
motes + fireflies + 3 curtains (+5), low = a few motes (+1); reduced motion = none. The Holodeck (capped at low) and the space
background do not use it.

### `lightTrails`
Streaks of light sliding past like traffic or data (GPU quads, themed colours). (3D scene)

```js
const fx = OLYMPUS_FX.lightTrails(scene, { count: 70, area: [44, 7, 14] });
// streaks of light sliding past like traffic or data
fx.stop();
```
