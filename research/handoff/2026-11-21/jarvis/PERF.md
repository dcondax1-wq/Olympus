# Jarvis speed + payout (QA 2026-11-21), day-jarvis

## 1. Speed (Fast-3G line, x4 CPU, 390 x 844; tools/perf_sweep.py --pages jarvis, 3 runs each)

| | before (trades.json) | after (trades_lite.json) |
|---|---|---|
| bytes on open | 1,323-1,327 KB | 1,184-1,216 KB (-125 KB) |
| data files | 184-188 KB | 60-77 KB |
| total blocking time | 7.2-8.4 s | 4.5-8.4 s (noise; the lite file saves bytes, not CPU) |
| longest task | 2.0-2.5 s | 1.3-2.6 s |

Where the blocking time is (CPU profile, 15 s after open, x4 CPU):
- `jarvis/backdrop.js` (the 3D sky behind the home, on `olympus/render.js`): ONE task of ~2.7 s = scene build + the first
  frame compiling every shader synchronously, then a frame every ~250 ms (20 fps on a phone) that is a 200-500 ms long task each.
  render.js compiles in the background only where the browser has KHR_parallel_shader_compile (a real GPU); the lab's software GL
  has none, so the lab sees the worst case. Whether an iPhone's Safari has it decides the real cost: **your / DESIGN's call**
  (options: start the sky only where parallel compile exists, or a still frame until the first tap).
- With backdrop.js blocked: TBT 1.9-2.6 s, before and after alike (the 2D star canvas drawStars ~0.4 s / 15 s, renderBar ~0.2 s,
  data.js etParts ~0.1 s, jfx.js scan ~0.08 s).
- jfx.js / dashfx: no long task; blocking both changes TBT by noise only (7.3-8.4 s with the sky on).
- Same harness on yesterday's pc 3aaa1d69 (before the FX work): TBT 8.2 / 8.6 s vs today 6.7 / 8.0 s: no regression from the FX.

## 2. Payout in MFFU terms (jarvis/zeus.js)
"ATLAS 25K (funded): at +$401 (MFFU counts from $0); the $1,000 ask comes at +$2,100 ($1,699 to go), $800 to you, $560 after the
30% tax pot. Earliest: $250 at +$1,350 ($949 to go), but the goal is the full $1,000 (only 5 sim payouts)." Accounts and trading answers
show the funded balance from $0 too. PC_FEED.mffuView when the page has it, else balance - start.

## Tests
jarvis_skills 85/85, jarvis_zeus 125/125 (+ the +$401 example pinned), jarvis_hub 272/272, smoke 11/11.

## 3. The 3D sky made cheap at start (lead's decision, jarvis/backdrop.js only; render.js untouched)
- Poster: `.bgfx`'s CSS sky (jarvis.css) is there from the first frame; the 3D fades in over it (no layout shift, no new image).
- Not before Jarvis's own start is done (data-ready) + 1.5 s, and 2.5 s without a tap / key / scroll, on any screen (a phone: 6 s at
  least, as before); each compile slice also waits 1.5 s after the last input (a slice must never land on the owner's tap).
- Shaders: one top-level object per idle slice (`renderer.compile` + each new program's `getUniforms()`, so the driver's link wait
  lands in that slice, not on the first frame; lights stay on so the programs match). `__jarvisBackdrop.compiled` = 8 objects.
- First frames at the low tier (no bloom); the chosen tier after 30 fast frames in a row.
- Cap: a frame over 50 ms (its own work, or the gap after it) twice -> 15 fps + low; twice more -> still: the last frame stays and a fresh
  one every 3 s (it keeps following the New York clock, the VIX weather, the mode colour). Back from an app it draws again.
- `__jarvisBackdrop.ms` = what each step took ({renderer, scene, first}).

perf_sweep --pages jarvis --cpu 4 (Fast-3G), 3 runs each:

| | before (yesterday's head) | trades_lite only | + the sky changes |
|---|---|---|---|
| total blocking time | 7.2 / 7.8 / 8.4 s | 4.5 / 7.0 / 8.4 s | 4.3 / 4.8 / 5.3 s (final: starts after input calms) |
| longest task | 2.0 / 2.4 / 2.5 s | 1.3 / 2.4 / 2.6 s | 1.24 / 1.32 / 1.69 s |
| bytes | 1,323-1,327 KB | 1,184-1,216 KB | 1,189-1,192 KB |
| first paint | 1.6-2.0 s | 1.6-1.7 s | 1.6-1.7 s |

What is left of the 1.2 s: the browser putting the first 3D frame on screen (software GL here: "(program)" in the profile, not JS;
our JS for that frame is 20-60 ms). A real GPU does this in a fraction.

Tests (final head): test_olympus_render 56/56 (g: the low start tier 2 passes or high 3; i: in still mode its frame is drawn again on
return), test_jarvis_home 66/66, jarvis_hub 272/272 (b / h now wait for the live feed instead of a fixed 0.7 s: a race, old and new sky alike), jarvis_fx 14/14, jarvis_skills 85/85, jarvis_zeus 125/125, smoke 11/11. test_jarvis_home_v2 40/41: 'e. reduced motion ... no
transitions on the tiles' fails the SAME on origin/pc (olympus/a11y.css sets transition-duration .001s !important under reduced motion;
the test wants 0s): not Jarvis, for the a11y kit owner or the test.
