# OLYMPUS performance and battery (2026-11-04, job 19)

Goal: every 3D / animated app fits an iPhone-class budget, sleeps when nothing is looking at it, and costs little battery.
Tests: `python -X utf8 -m tests.test_olympus_kit` (per-app budgets, the power layer), `... power` and `... more` run the new parts only,
`tests.test_olympus_render` (the render core, the tier step-down).

## What the kit does now (no per-app edits needed)

| Layer | Where | What |
|---|---|---|
| Pixel ratio caps | render core / `OLYMPUS.dpr()` | <= 2 on high / ultra, <= 1.5 on low, 1 on off (already there); **new: <= 1.5 in battery saver** |
| Hidden tab | `OLYMPUS.hidden()` | no frame while the tab is hidden (already there) |
| **Covered** (new) | `OLYMPUS.covered(true)` | a sheet / overlay hides the scene: `hidden()` answers true, so every loop that honours it sleeps and wakes on `covered(false)`. A parent frame (Jarvis) can post `{ olympus: 'covered', on: true }` (same origin only). `html[data-oly-covered]` |
| **Idle frame cap** (new) | `OLYMPUS.frameGap()` | the owner touches = every frame. No touch / key / scroll for 4 s: **30 fps on high / ultra, 15 fps on low, 2 fps on off**. Honoured by the render core's `start()` loop (skips the JS and the draw) and by `rc.render()` (returns false inside the gap), so every adopter gets it. A touch lifts it at once |
| **Battery saver** (new) | `OLYMPUS.saver()` | the owner's `olympus.saver` = `on` / `off` (Jarvis settings: Battery saver), else auto: Battery API (<= 20% and not charging; Chrome / Android) or the browser's Save-Data. Saver = 30 fps even while touching (15 idle), pixel ratio <= 1.5, ambience off unless the owner turned it on. `html[data-oly-saver]`, `OLYMPUS.onPower(cb)`. iPhone Safari has no Battery API: there the owner's switch is the control |
| Step-down on slow frames | render core `adapt()` | mean frame > 24 ms over a window: ultra -> high -> low, never stored. **Now judged against the cap**: a deliberate 30 fps cap is not "slow" (limit = gap + 9 ms), and the window restarts when the cap changes. Verified in the core's own test (`d.`) and in every app (see "step-down" below) |
| Ambience | `OLYMPUS.ambient()`, `sfx.js` | see `OLYMPUS_SFX.md`; off in saver, paused hidden / covered-by-tab, one `setInterval` (3 s) only while a bed is set |

## Audit: every 3D / animated app (390 x 844, dpr 3, SwiftShader, `?demo=1`)

Calls / triangles are the portable numbers (three.js `renderer.info`, one frame). **The kit holds software GL to LITE, so every row below is the
LITE scene (pixel ratio 1.5)**; Jarvis' phone default on a real GPU is high, with the same geometry plus bloom / MSAA. fps is **relative only**
(the machine ran at load ~55): "render fps" = `renderer.render` calls per second, "loops" = requestAnimationFrame callbacks per page frame
(1 = one loop, the minimum), "JS ms/s" = script time per second.

| App | calls | tris | heap MB | pixel ratio | render fps (rel.) | rAF loops | JS ms/s | 2D draws/s |
|---|---|---|---|---|---|---|---|---|
| nemesis | 22 | 23,749 | 5.2 | 1.5 | 0.6 | 1 | 0 | 7 |
| athena | 80 | 2,205 | 6.5 | 1.5 | 1.4 | 1 | 2 | 51 |
| argus | 8 | 63,457 | 5.7 | 1.5 | 1.8 | 1 | 2 | 7 |
| chronos | 35 | 4,687 | 6.5 | 1.5 | 0.3 | 2 | 1 | 5 |
| datacity | 70 | 149,752 | **36.3** | 1.5 | 1.4 | 1 | 7 | 51 |
| cities | 7 | 37,733 | 6.0 | 1.5 | 2.1 | 1 | 3 | 7 |
| kalshicity | 60 | 18,825 | 6.1 | 1.5 | 0.3 | 1 | 3 | 8 |
| oracle | 115 | 11,065 | 7.0 | 1.5 | 1.2 | 1 | 3 | 66 |
| odeon | 22 | 27,389 | 4.8 | 1.5 | 0.1 | 1 | 0 | 1 |
| fates | 34 | 19,945 | 7.5 | 1.5 | 1.1 | 1 | 2 | 19 |
| labyrinth | 28 | 5,975 | 5.0 | 1.5 | 1.2 | 1 | 2 | 16 |
| hephaestus | 22 | 2,419 | 5.1 | 1.5 | 0.6 | 1 | 9 | 7 |
| prometheus | 18 | 3,817 | 5.7 | 1.5 | 0.6 | 1 | 3 | 5 |
| tyche | **217** | 23,114 | 7.9 | 2 (forced) | 2.8 | 1 | **33** | 40 |
| plutus | 19 | 4,720 | 6.0 | 2 | 1.9 | 2 | 11 | 36 |
| mind | 21 | 739 | 4.9 | 1.5 | 1.4 | 1 | 2 | 10 |
| tree (Daphne) | 54 | 6,700 | 15.7 | 1.5 | - | 1 | **90** | **1,125** |
| pantheon | 107 | 24,921 | 6.0 | 1.5 | 0.6 | 1 | 4 | 31 |
| arena | 101 | 63,831 | 7.3 | 1.5 | 0.3 | 1 | 3 | 16 |
| forum | 94 | 7,119 | 9.1 | 1.5 | 0.2 | 1 | 1 | 9 |
| ares (2D) | 13 | 2,904 | 4.4 | 2 | 11 (own loop) | 1 | 32 | 144 |
| hermes (2D) | - | - | 3.2 | - | own loop | **2** | **59** | **2,192** |
| kalshi (korb + DOM) | - | - | 6.5 | - | own, 30 fps cap | 1 | 26 | 517 |
| bridge (DOM) | - | - | 2.4 | - | none | 0 | 2 | 0 |

The 3D-effects **Off** tier, same machine: mind, arena, pantheon, argus draw nothing (one still frame, 0 draws/s, page idle at 52-56 fps: zero
power). **oracle (79 draws/s) and datacity (242) keep drawing at Off**; tyche kept a 1.5 pixel ratio (fixed in the own-loop pass below).

### Budgets (tests/test_olympus_kit.py)

`BUDGET` (the nine kit apps, 2026-11-03) and the new `MORE` table hold calls + triangles per app at measured +25%; JS heap <= 40 MB for all
(datacity 36 MB is the one close to it); layouts per frame <= 1.25. `python -X utf8 -m tests.test_olympus_kit more` runs the new apps, `power`
the power layer. Daphne's budget was 0 (no three.js when written); it is now 68 calls / 8,500 triangles. Re-measured after the own-loop pass: athena 62 / 8,000, cities 10 / 80,000 (grew with its new districts), kalshicity 90 / 24,000, ares 50 / 7,800.

### Verified: the step-down works in every app

Every 3D app above reported pixel ratio 1.5 at `jfx=high` under SwiftShader, i.e. the render core's tier policy / `adapt()` stepped it down to LITE by
itself (tyche, plutus and ares are the exceptions that keep their own pixel ratio, below). The core's own test (`test_olympus_render` d.) drives it with 32 ms
frames: ultra -> high -> low, never stored. With the new frame cap the step-down is still exercised (limit gap + 9 ms) and the test stays green.

## Findings and what was changed

| Finding | Action |
|---|---|
| Nothing slowed down when the owner stopped touching; a phone left on an app drew 60 fps | **kit: idle cap** (30 / 15 / 2 fps), lifted by any touch |
| No battery awareness | **kit: saver** (Battery API, Save-Data, the owner's switch in Jarvis settings), pixel ratio <= 1.5, 30 fps |
| A sheet over an app kept the scene drawing | **kit: `covered()`** (+ postMessage from Jarvis) |
| Software-GL step-down fine, but a deliberate cap would have counted as "slow" | `adapt()` judged against the cap |
| kalshi `korb.js`: already 30 fps, hidden / off-screen pause | no change needed |
| mind: hidden pause, one loop | no change needed |

### Own-loop pass (2026-11-04): applied in the apps nobody was rewriting

Every own frame loop now sleeps on `OLYMPUS.hidden()` (hidden tab or covered) and keeps `OLYMPUS.frameGap()` (idle 30 / 15 fps, battery saver, Off 2 fps;
a touch = full rate). Minimal diffs, one block per loop:

| App | Change | Before -> after (same machine, relative) |
|---|---|---|
| tree (Daphne) | the LITE 30 fps cap became `max(LITE cap, frameGap())`; the loop was already hidden-aware | at 3D Off 1,125 -> **41** 2D draws/s, 90 -> 4 ms/s of script; at high 1,125 -> ~840 |
| hermes | the effects loop (`fx.js`) and the card progress loop (`app.js`) keep the gap and use `OLYMPUS.hidden()` | high 2,192 -> ~1,200 draws/s, 59 -> 3 ms/s; Off **0** draws |
| tyche | 3D Off is now the core's `off` tier (pixel ratio 1, direct draw) instead of `low` at 1.5; the frame keeps the gap | Off: pixel ratio 1.5 -> **1**, page responsive (task time 1000 -> 343 ms/s); high JS 33 -> 2 ms/s idle. Draw calls unchanged (217): the wheel's coins are separate transparent meshes, an instancing rewrite was not attempted |
| athena | **shelves instanced**: books, glowing spines, scrolls and caps are 4 `InstancedMesh` per shelf (one leather material, per-book tint through `instanceColor`) instead of ~30 meshes; frame gap | **80 -> 48 calls** (triangles 2.2k -> 6.2k because culling is now per shelf, not per book: irrelevant next to the calls); Off 0 draws |
| ares / plutus / pantheon | the shared `tick()` keeps the gap | ares at Off 0 draws; budgets re-measured |
| forum / kalshicity | `frame()` returns before any JS when hidden / covered and inside the gap | |
| mind | the gap; the slow-frame meter only counts uncapped frames (a deliberate 30 fps is not "slow", it would have stepped Mind down to LITE) | |
| cities | already on the core's `stage.start`, which honours the gap | |

Jarvis now posts `{ olympus: 'covered', on }` to every framed app when a sheet (Add, Settings, Look, Voice, palette) or the ⋯ keys open over it, and `on: false`
when they close or Jarvis goes home (a delimited block in `jarvis/index.html`: `==== OLYMPUS covered`). Test: `tests.test_jarvis_transitions` (g.).

Measurement caveat: the `rAF loops` column of the first audit is a ratio of rAF callbacks to compositor frames; below ~10 fps (this machine) it is
inflated and not comparable between runs. Use calls, triangles, 2D draws/s and script ms/s.

### Still open: the apps other agents are rewriting (apply the snippet below; nothing was edited there)

| App | What to apply |
|---|---|
| oracle (115 calls) | own loop: `OLYMPUS.hidden()` + `frameGap()`; honour `OLYMPUS.dpr()` / the `off` tier (still 1.5 pixel ratio at Off); merge static meshes |
| datacity (150k tris, 36 MB heap vs 40) | gap in its two loops; LOD for far districts; at Off it still draws (242/s): make Off a still frame like mind / arena |
| odeon, fates, labyrinth, hephaestus, prometheus, arena, nemesis, chronos, argus | gap + hidden/covered in each own loop (check `grep requestAnimationFrame`: 2-4 loops each); arena (64k tris, 100 calls): merge static meshes |
| any new app | `OLYMPUS.hidden()` + `OLYMPUS.frameGap()` in every loop, 3D Off = still frame, never a slow-frame meter that counts capped frames |

1. **tree (Daphne)**: 1,125 2D draws/s and 90 ms/s of script (6.5 fps headless) from the label / link canvas: cache the static layers, draw only when
   the camera moves. Heap 16-19 MB.
2. **hermes**: 2 rAF loops, 2,192 2D draws/s, 59 ms/s: one loop, pause when no card animates (`OLYMPUS.hidden()` / `frameGap()`).
3. **tyche**: 217 draw calls and 33 ms/s of script, the heaviest 3D app: instance the wheel segments / slices, merge static meshes. At Off it keeps
   drawing (297/s) and holds a pixel ratio of 1.5-2: honour `OLYMPUS.dpr()` and stop its loop on Off like mind / arena do.
4. **oracle**: 115 calls; at Off it still draws (79/s) at 1.5.
5. **datacity**: see "Data City v3: the phone-safe preset" below (caps table, 25 MB heap); at Off it still draws (242/s) at the kit's 2 fps idle cap.
6. **athena**: 80 calls for 2,205 triangles (many tiny meshes): `InstancedMesh` or merged geometry would cut it by ~5x.
7. **pantheon / arena / forum**: ~100 calls each; arena 64k triangles. Fine for an iPhone 13+, worth merging static meshes for older phones.
8. **ares**: own 2D loop, 144 draws/s and 32 ms/s at an unthrottled 11 fps: use the kit's `frameGap()` in its loop (`if (g && now - last < g) return;`).
9. Any app with its own loop: add the same two lines the render core uses (`OLYMPUS.hidden()` and `OLYMPUS.frameGap()`).

```js
// an own requestAnimationFrame loop, in the kit's rules (2 lines)
function loop(now) { raf = requestAnimationFrame(loop); const g = O && O.frameGap ? O.frameGap() : 0;
  if ((O ? O.hidden() : document.hidden) || (g && now - last < g - 3)) return; last = now; draw(now); }
```

## Data City v3: the phone-safe preset (2026-11-04, job 2 follow-up)

Data City v3 (traffic, monorail, river, ships, neon signs, fireworks, the kit's effects) measured 100-110 calls / 350-480k triangles at the high tier:
too much for an iPhone. `tools/web_public/datacity/caps.js` is now **the one table** of the city's density caps, three profiles chosen by
`profileOf(level, phone, saver)`: `lite` (OLYMPUS low / off, unchanged), `phone` (a phone, i.e. a viewport of 520 px or less, a coarse pointer or iOS, at
**high**; or the kit's battery saver at high) and `full` (ultra, or a PC at high). `?phone=1` / `?phone=0` force the hint (tests), `?q=` forces the tier.
The render core's pixel ratio cap is 1.5 on a phone (1.75 otherwise).

| Cap | full (PC) | phone-high | lite |
|---|---|---|---|
| cars / flying taxis | 520 / 90 | 160 / 28 | 160 / 28 |
| airships | 3 | 0 | 3 |
| monorail trains x cars | 3 x 6 | 2 x 4 | 1 x 6 |
| sailing ships / cranes | 9 / 8 | 5 / 4 | 4 / 8 |
| neon boards | 2 per district | 1 per district | 2 |
| tiles in full / near-tower tiles / reflected tiles | 22 / 70 units / 4 | 7 / none / 1 | 12 / none / 0 |
| scenery towers | 2,600 | 800 | 900 |
| fireworks shells x sparks | 8 x all | 3 x half | 8 x all |
| lens flare, aurora, fireflies | on | off | on |
| temple + Pharos detail | always | hidden beyond 330 units | always |
| rain drops / data pulses / street trades | 7,000 / 34 / 1,600 | 3,000 / 12 / 600 | 1,800 / 11 / 420 |
| pixel ratio cap | 1.75 | 1.5 | 1.5 |

Measured (390 x 844, dpr 3, SwiftShader, `?q=` forced; `python -X utf8 -m tests.test_olympus_kit tiers`, `tests.test_datacity --only v3`):

| | calls | triangles | JS heap |
|---|---|---|---|
| before the preset, high (v3 as first landed) | 106-108 overview, 100-110 close-up | 352k / 477k | 58 MB (42.7 MB on v2) |
| **phone-high**, far overview | 84 | 167k | 25 MB |
| **phone-high**, close-up of the densest district | 62 | 202k | 25 MB |
| ultra, worst of overview / close-up | 113 | 509k | 25 MB |

Budgets (`DATACITY_TIERS` in `tests/test_olympus_kit.py`, `PHONE_BUDGET` in `tests/test_datacity.py`): phone-high 95 calls / 250k triangles and heap <= 40 MB;
ultra 130 calls / 700k. The far overview of a phone is 84 calls, not the 60 asked for: about 70 of them are the fixed scene (sky, ground, the forum
and its 11 gates, the streams, fog, billboards, the post passes add about 15); merging the landmark meshes is the next cut.

Heap: the compact skyline rows (about 30,000 small arrays) are dropped as soon as they are decoded (`data.js`), which took 58 MB to 25 MB (the neon-sign
atlas is 640 x 100 px per row). The city loop honours `OLYMPUS.frameGap()` (the kit's idle cap and battery saver) and `OLYMPUS.hidden()`; the `city` ambient bed
comes from the kit's table (`AMBIENT.datacity`) and starts after the first touch (checked in `test_datacity` section k). `?demo=1` reads only `fixture.json`
(nothing off-origin, no `city.json`).

## Jarvis settings

Settings -> Look: **App ambience** (the sound beds) and **Battery saver** (`olympus.saver` = `on`; off = auto). Both are read by every OLYMPUS page
(the saver through the `storage` event, the ambience through `olympus.sfx`).

## Proof that the tree failures are load, not the kit change

`tests.test_olympus_kit tree` (and `mind`) fail intermittently on this machine (load ~55): the readiness check (veil lifted) and the LITE / reduced-motion
checks that depend on it. The same checks were run against a temp copy of the site from the commit **before** the kit change (`e75ca7b`, old
`olympus.js` / `render.js` / `sfx.js` and old apps) and against the current tree: **OLD 9/10, 6/10, 6/10; NEW 9/10, 7/10, 9/10** passing, the same
checks failing in both (`c. veil lifted`, `b. jfx=low`, `b. reduced motion`, `c. Retry`). Mind: OLD 7/11 failing the same two checks the current code fails.
Tree reaches `ready` in 1.9 s when loaded alone.
