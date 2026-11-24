# day-pillars-cinema: the Four Pillars as an Olympus temple at night (lead-only wiring)

Owner (2026-11-24): "Dude c'mon, those can look WAY better." The flat neon tubes are now a cinematic 3D temple.
Branch `day-pillars-cinema` (from origin/pc 8e344c7e). Helpers never edit sw.js, build_web_dashboard.py, jarvis/apps.js, the olympus.js APPS table.

## Wires (lead)
1. **Root service worker cache:** bump `CACHE` in `tools/web_public/sw.js` `le-public-v213` -> `le-public-v214`
   (`python tools/bump_versions.py --check --base origin/pc` asks for exactly this one; every other file is already bumped).
2. **New folder to ship:** `tools/web_public/pillars/fonts/` (Cinzel latin woff2, 26 KB, SIL OFL; `OFL.txt` beside it). `build_web_dashboard.py`
   already copies the whole `pillars` app folder; if it copies by file list instead, add `fonts/`. Nothing else is new.
3. Publish as usual (`publish-site` skill) and open https://dcondax1-wq.github.io/pillars/ on the phone.

## What changed
- `pillars/pillars-scene.js` (rewrite, same API + `select(id, focus)`, `project(id, 'label'|'base')`): four fluted Doric columns
  (20 flutes, entasis, gold capitals, Attic bases) on a 3-step stylobate under an entablature with triglyphs and a pediment (gold hairlines,
  an emblem, acroteria), a dark cella with a soft glowing door; a glossy obsidian floor with the temple mirrored under it and wet-stone light
  streaks under each pillar; stars, a moon, nebula, god rays, drifting mist sprites.
  Each column = a pillar: liquid light rising up each flute to its level (LIVE full and breathing, OFF dim marble with a faint ember at the foot,
  ORDER FLOW = tick days / 60), a bright ring at the level, sparks up the flutes and a mote stream off each live capital.
- three.js r160 pinned on cdnjs, local `../jarvis/three.module.min.js` fallback (Home / NQ heroes load the local copy first: those pages load
  nothing off the site, and NQ already shares that module). **cdnjs hosts only the core module for r160** (no examples/jsm), so the add-ons are
  written on core three in the file: a RoomEnvironment-style PMREM light room, an UnrealBloom-style HDR bloom (bright pass + 4-level blur,
  ACES + vignette + film grain in the composite), baked AO in vertex colours, PCFSoft shadows rendered once (the temple never moves).
- Camera: 2.5 s intro (dolly in + rise + exposure fade-in), gentle idle sway, horizontal drag orbits with inertia (vertical drag still scrolls),
  tap a column = smooth camera move to it + its panel slides up (`.panel.rise`); tap it again or empty space = back to the wide shot.
  Tabs only light the column (no camera move).
- Performance: ~16 draw calls in the scene pass (instanced columns, one merged building). Quality tiers: hq (bloom, shadows, mirror, all motes)
  -> lower DPR -> no bloom -> low (Lambert materials, no shadows / mirror / point lights, fewer motes, DPR 1, 30 fps). Starts low on
  Save-Data, `?lite=1`, <= 2 cores / 2 GB, or a software GL renderer (SwiftShader / llvmpipe); steps down by itself on slow frames (a terrible
  frame time jumps straight to low). Shaders compile with `compileAsync` before the first frame (no frozen page). Paused off-screen and on a
  hidden tab. Reduced motion: no intro / sway / flow, draws only when touched. `?fx=hq` pins hq (screenshots). `?lite=2d` = the 2D fallback.
- 2D fallback (pillars page and heroes): a CSS temple (pediment, fluted columns filling with light, steps).
- Type: Cinzel (display serif, self-hosted, OFL) for titles, column plates, section heads, the hero.
- Heroes (`pillars/hero.css` + `hero.js`): a mini of the same temple with glass panels, gold hairline borders, depth shadows.
  NQ + Zenith: the temple under the title, glass chips floating over its reflection. Home (gate): the jewel temple stands right of the
  "Olympus" title where the line-drawn temple was (home-fx.js skips its sketch when `html[data-temple3d]`), its steps blurred behind the glass
  chips; no extra height (the 6 dashboards + More still fit 390 x 844).
- "What's new" toast lifted to bottom 172 px so it never sits in Jarvis's corner (test_gate_page c was only passing by timing).
- `fills()`: LIVE = full (it was 0.86 while the PC post was missing, which drew a level ring on a live pillar).

## Tests (all green on this branch)
test_pillars 71/71 (draw-call cap 8 -> 24: a whole temple now), test_pillars_hero 30/30, test_nq_page 71/71, test_gate_page 91/91,
test_perf_sweep 14/14, test_zenith_mode 70/70, smoke 11/11.
Versions: pillars.css/js `c1`, pillars-scene `c1`, hero.css/js `c1` (gate, Zenith, NQ), home-fx `x3` (test_gate_page list updated).

## Shots
`shots/before/` vs `shots/after/` (390 x 844 @2x, Node Playwright, SwiftShader; `shots.cjs` re-makes them:
`node shots.cjs <outdir>` from a folder with Node Playwright). After: 1 Pillars (hq), 2 tap ATLAS (camera move + panel), 4 Home,
5 NQ hero, 6 2D fallback, 7 low tier, 8 Zenith hero.
