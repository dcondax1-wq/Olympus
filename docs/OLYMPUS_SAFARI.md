# OLYMPUS on Safari (iPhone): compatibility sweep, 2026-11-04

Everything else is tested in Chromium (SwiftShader); the owner is on an iPhone. This sweep ran every page in **WebKit** (Playwright
WebKit 27.2, iPhone 13 profile, WebGL2 through software) and read the code for constructs that fail on iOS Safari 16 / 17 / 26.
Run it again: `python -X utf8 -m tests.test_safari_smoke` (the static lint always runs; the WebKit part runs when WebKit is installed:
`PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright install webkit`, about 300 MB, delete it afterwards).

Honest limit: this WebKit is a Linux build of a newer Safari engine with a software GPU. It proves the pages parse, load, draw and have no
script error in WebKit; it cannot prove iPhone GPU speed, memory limits, the iOS toolbar, haptics or audio unlock. That is why the lint
below also bans what older iOS cannot parse.

## 1. The WebKit smoke (27 pages, 15 s each)

Loaded from a static server of `tools/web_public`: the dashboard (`index.html`), Jarvis and the 25 app folders (arena, ares, argus, athena,
bridge, chronos, cities, datacity, fates, forum, hephaestus, hermes, jarvis, kalshi, kalshicity, labyrinth, mind, nemesis, odeon, oracle,
pantheon, pc, plutus, prometheus, tree, tyche). Per page: console errors, page errors, failed requests, HTTP >= 400, WebGL2, a non blank
screenshot, sideways overflow.

| Check | Result |
|---|---|
| Page errors / console errors | **0 on all 27 pages** |
| Failed requests (aborted, refused) | 0 |
| WebGL2 context | yes on all 27 |
| Non blank screenshot | all 27 |
| Sideways scroll (iPhone 13, 390 px) | none |
| HTTP 404 | only `home.json`, `data.json`, `cronos/status.json`, other `*.json` data files and `/icons/*.png`: published by the site build, absent from a bare source tree (not an error; the pages show their DEMO / offline state) |
| Jarvis 10 s intro film, held at 6.9 s (WebGL1, the heaviest shader) | compiles and draws, no error |
| App intro (`/oracle/?intro=1`) | plays, no error |

## 2. Findings and fixes (static review of the code written tonight and the older tree)

| # | Where | Issue | Status |
|---|---|---|---|
| 1 | `athena/athenabrain.js` | Regex lookbehind `(?<=[.!?])` in a module: a SyntaxError before iOS 16.4 kills the whole Athena script | **Fixed**: a match-based splitter with the same results on the cases tried (decimals, `...`, `??`, trailing text) |
| 2 | `holo.css` (6 rules), `more.js` (1 rule) | `backdrop-filter` without `-webkit-backdrop-filter`: no glass on iOS 16 / 17 | **Fixed**: the prefixed twin added beside each |
| 3 | `index.html` (`.btn`, `th.sort`, summaries), `blitzcore.js`, `tree/tree.css`, `tradepics.js` | `user-select` without `-webkit-user-select`: text still selectable and the long-press callout fights drags on iOS | **Fixed**: the twin added (5 places) |
| 4 | `liveview.css`, `tradechart.js` (3 rules) | `appearance: none` without `-webkit-appearance` (buttons keep the iOS look on 15.3 and older) | **Fixed**: the twin added |
| 5 | `olympus/render.js`, `olympus/fx-surface.js` | Float render targets: iOS renders to half float only | **OK**: both use `HalfFloatType` (render.js falls back to 8-bit when neither `EXT_color_buffer_float` nor `_half_float` exists); no `FloatType` render target anywhere in our code |
| 6 | `olympus/render.js` | MSAA render target samples | **OK**: 4 samples on ultra / high only, 0 on low / off; three clamps to `MAX_SAMPLES` |
| 7 | `jarvis/kokoro-engine.js` | `import()` inside a worker | **OK**: the worker is `type: 'module'` (Safari 15+); the model library is imported dynamically inside it |
| 8 | `olympus/sfx.js`, `jarvis/index.html`, `jarvis/voice-out.js`, `voice-mode.js` | `AudioContext` needs the webkit prefix and a resume inside a gesture | **OK**: every `new AudioContext` has `webkitAudioContext` beside it (lint), resume is called from the tap path (and `interrupted` is handled in voice-out) |
| 9 | the intro film (`jarvis/index.html`) | Sound before a gesture | **OK**: the film synthesises sound only after a gesture (`navigator.userActivation` / a skip tap) |
| 10 | `olympus/olympus.js`, 9 files | `navigator.vibrate` and the Battery API are absent on iOS | **OK**: every call sits behind a guard or a try (lint); the iOS haptic fallback is the `switch` checkbox trick |
| 11 | `hermes/share.js`, `cities/app.js`, `tree/branchui.js`, `more.js`, `procore.js`, `ares/aresdesk.js`, `argus/extras.js` | Web Share with files | **OK**: all check `navigator.canShare({ files })` first and fall back to a download |
| 12 | `jarvis/sw.js`, `kalshi/sw.js` | `cache.addAll` fails on any 404 | **OK**: every entry of the Jarvis SHELL / CORE and the Kalshi SHELL exists (lint; `kalshi/kit.json` is written by the site build). The root `sw.js` tolerates a failed precache (`.catch`) and its icons come from the build |
| 13 | all `localStorage` / `sessionStorage` use | Throws in a private window or with site data blocked | **OK**: lint: every call sits in a try / catch |
| 14 | `kalshi/korb.js`, `jarvis/portal.js`, `jarvis/backdrop.js` | `requestIdleCallback` is absent on Safari | **OK**: each has a `setTimeout` fallback |
| 15 | `jarvis/voice-mode.js` | Wake Lock | **OK**: guarded (`navigator.wakeLock` may be absent) |
| 16 | `holocore.js`, `liveview.js`, `jarvis/index.html` | Fullscreen API (absent on iPhone for pages) | **OK**: the `webkit` form and a toast fallback |
| 17 | `jarvis/core-visual.js` | `matchMedia().addListener` | **OK**: only as the fallback after `addEventListener` |
| 18 | `holocore.js` | `Array.prototype.findLastIndex` (iOS 15.4+) | **OK**: used only if present, with a fallback |
| 19 | `fx.js` (the bundled three.js in two folders) | `OffscreenCanvas`, `ReadableStream`, `.union(` | **OK**: vendor code, guarded by its own feature checks; excluded from the lint |
| 20 | `.at(` in `holocore.js`, `cities/generator.js`, `fx/src/*` | `Array.prototype.at` (iOS 15.4+) | **OK on iOS 16+**; not banned (the kit's rule is Safari 16, which has it) |
| 21 | CSS `color-mix()` (39 files), `:has()` (4 files), `dvh` / `svh` (17 files), `inset`, `aspect-ratio`, `@property`, `text-wrap`, `scrollbar-width`, `accent-color` | Newer CSS | **OK on the owner's iOS** (color-mix 16.2+, :has 15.4+, dvh 15.4+, inset 14.1+, aspect-ratio 15+, @property 16.4+). Older iOS drops the declaration only. Pages that need a height keep a `vh` fallback before the `dvh` one |
| 22 | `<script type="module">` + `defer` | Ordering | **OK**: the kit's classic scripts (`olympus.js`, `intro-app.js`, `fx-core.js`) run before the app's modules; the WebKit smoke shows no ordering error |
| 23 | top-level `await`, `structuredClone`, `Object.groupBy`, `Array.prototype.toSorted` | Newer JS | **None in our code** (top-level await only in `fx/build.mjs`, a build script, not shipped; lint bans the rest) |
| 24 | `ResizeObserver` | Loops | **OK**: the observers only write CSS variables / a height (no read-after-write loop seen in the smoke) |
| 25 | Pointer events vs touch | Safari 13+ has pointer events | **OK**: the apps use pointer events with `touch-action`; the 3D views set `touch-action: none` |

Not verified here (needs the phone): GPU frame rate and memory of the four heavier scenes (Arena crowd, Nemesis, Chronos, Argus), the iOS
toolbar resizing, real haptics, audio unlock on the first tap, the service worker install on a slow network.

## 3. The lint (runs in Chromium-only environments too)

`tests/test_safari_smoke.py` fails when someone adds: a regex lookbehind, `Object.groupBy`, `toSorted` / `toReversed` / `toSpliced`,
`Array.fromAsync`, `Promise.withResolvers`, `AbortSignal.any`, Set algebra, iterator helpers, a float render target; a `backdrop-filter` or
`user-select` without its `-webkit-` twin; a `new AudioContext` without the webkit fallback; an unguarded `vibrate` / `getBattery`; a
`localStorage` call outside a try; a file missing from the Jarvis / Kalshi worker lists. The bundled `fx.js` and `three-addons` are skipped.

## Sweep 2026-11-04 (iPhone Safari, minimum iOS 15)

`tests/test_safari_smoke.py --lint` now also checks (all pass): a `100dvh` twin beside every `100vh` height, no form control under 16px
(iOS zooms on focus), `Notification.*` and `requestIdleCallback` only behind a feature test, no OffscreenCanvas / AudioWorklet / WebGPU /
file-system / USB / Bluetooth / orientation lock, touch / wheel listeners with `preventDefault` say `passive: false`, no `getContext('webgl2')`
dereferenced straight away, autoplay media muted + `playsinline` and every `.play()` handles its rejection, every page has `width=device-width`
and `viewport-fit=cover` where it uses the safe-area insets, and every script (334) parses as ES2021 (acorn; a classic script may not use
top-level await). Fixed: `100vh` without `100dvh` in `holo.css` (.hd-pc), `liveview.css` (.lv-root, maximised), `kalshi/kalshi.css`,
`pc/index.html`; the Chronos compare `<select>` was 12px (now 16px). Reviewed, fine on iOS 15.4+: `.at(`, `findLastIndex` (guarded),
`||=` / `??=`, top-level await in modules, `color-mix` (iOS 16.2+; the kit says to avoid it: 291 uses in 13 files, each a single declaration that an
older iOS just drops), `:has` (15.4), `inert` (15.5), `startViewTransition` (guarded), `roundRect` (guarded), canvas `filter` (ignored on iOS).

## The full iPhone walk: `test_safari_smoke --webkit` (2026-11-04)
Chromium misses WebKit-only bugs, so every app is walked in real WebKit with the `iPhone 13` profile (jfx=low, software GL, a local static server of
`tools/web_public`; the data files only the site build writes are 404 there, so the apps show their DEMO). Install once, in a scratch folder:
`PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright install webkit` (~300 MB; delete it when done; check `df -h /` first), then
`PLAYWRIGHT_BROWSERS_PATH=<dir> python -X utf8 -m tests.test_safari_smoke --webkit [id ...]` (about 10 minutes for all 30 apps + Jarvis; `--ready 60`,
`--no-offline`; `SAFARI_REPORT=<file>` writes the rows as JSON). Per app: loads without a page / console error; the veil lifts (`data-oly-state=ready`, or
no kit) within 60 s; one touch tap on the first control; the back seal / "Back to Olympus" link reaches Jarvis (Escape first if a sheet or the Settings tour
covers it). Then Jarvis and the root dashboard reload OFFLINE through their service worker (offline network errors for uncached data are expected and
ignored; the shell must render), and the first tap on Jarvis (the audio unlock) must throw nothing. Exit 77 = WebKit not installed = SKIP in
`tests/run_gate.py` (suite `safari_webkit`, not run by `--fast`). Harness notes: the dashboard registers its worker only on https, so the offline check
registers `sw.js` itself on http://127.0.0.1; Playwright's synthetic WebKit touch does not click a bare link on a page with no touch / click listener, so
the contexts carry a no-op `touchstart` listener (a real iPhone needs none).
