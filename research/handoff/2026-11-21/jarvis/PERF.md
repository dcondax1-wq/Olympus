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
