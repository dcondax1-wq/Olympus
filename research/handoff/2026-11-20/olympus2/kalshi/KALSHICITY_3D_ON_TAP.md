# Kalshi City: 3D on tap (2026-11-20, helper on day-kalshi)

## What changed
- The page opens on the 2D atlas + panels (archive banner, verdict, Best/Worst in $, Lab ticker, district switch, atlas map). No three.js, no WebGL at load.
- A 44 px **"Show the 3D city"** button (under the district switch) lazy-loads `cityscene.js` (dynamic `import()`, which pulls three.js, render core, rig, fx, skyline) and starts the scene. The atlas is removed (`cityAtlas().destroy()`), insights fold back as on the old 3D page.
- Opt-in **"Open in 3D next time"** box: stored per phone in `localStorage['kalshicity.v1'].city3d`; next visit starts 3D without a tap.
- In 3D a **"2D"** chip forgets the opt-in and reloads into 2D (frees the GPU and the frame loop).
- `prefers-reduced-motion`: always opens in 2D (even with the opt-in); the button still works. `?view=atlas` still forces 2D.
- No data / offline: the plain sentence stays; the 3D row is hidden. A tap before the data arrives starts 3D once it is in.
- Tall phones: the atlas caption now flows under the map (it was fixed over the district switch / the new button).

## Numbers (Chromium, 390x844, DPR 2, CDP CPU throttle x4, first 8 s, median of 3 loads, SwiftShader GL)
| | Before (3D at load) | After (2D first) |
|---|---|---|
| First contentful paint | 308 ms | 300 ms (272-400) |
| Long tasks, total in first 8 s | 7,936 ms (11 tasks) | 415 ms (3 tasks) |
| CLS | 0.128 | 0.000 |
| 3D modules fetched at load | 12 | 0 |
| WebGL contexts at load | 1 | 0 |
| After tapping "Show the 3D city" (8 s after tap) | - | 8,231 ms long tasks (9), CLS +0.0005 |

The 3D cost is unchanged when chosen (SwiftShader is software GL, so the absolute 3D figure overstates a real phone GPU); it is just no longer paid by everyone at load.

## Screenshots (390x844 @2x)
- `kalshicity-3dtap-before-old-page.png`: the old page at load (3D).
- `kalshicity-3dtap-before-tap.png`: the new first screen (2D + button).
- `kalshicity-3dtap-after-tap.png`: after the tap (3D city, "2D" chip).

## Files / versions
`tools/web_public/kalshicity/`: index.html (button row, 2D chip; kalshicity.js ?v=k28, agora-kalshicity.css ?v=g8), kalshicity.js (startAtlas / startScene on tap / opt-in), cityatlas.js (destroy(); imported as ?v=skyline9), agora-kalshicity.css (button, caption).
cityscene.js etc. unchanged (still imported as ?v=night11). No lead-only file needed.

## Tests
- `tests/test_kalshicity_page.py`: 105/105 (was 94/94). Old 3D checks now tap the button first; new: no 3D module/WebGL at load, 2D content + 44 px button on first screen, nothing covers the button, panels work in 2D, the tap starts 3D, nothing remembered unless asked, opt-in remembered -> 3D without a tap, 2D chip forgets + reloads 2D, reduced motion stays 2D, no-data starts no 3D, static source rules.
- `tests/test_kalshicity_network_switch.mjs`: pass (+4 asserts). `tests/test_kalshicity_freshness.py`: 1/1.
- `tests/test_kalshicity_skyline.py`: 4 tests, 1 fail + 1 error, the same pre-existing ones as before this change (atlas caption child order in the node stub; tier test) - untouched.
