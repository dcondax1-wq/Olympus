# OLYMPUS design kit

The nine 3D apps (Data City, Mind, Daphne, Oracle, Odeon, Fates, Hermes, Prometheus, Tyche) were each built by a different
agent. The kit in `tools/web_public/olympus/` makes them one product without rewriting them. Each app keeps its own colours
and scene; the kit unifies the structure: type, taps, the orb's corner, loading, quality and the performance rules.
Jarvis (`jarvis/`) is not changed. It already owns the same quality key and fonts.

- `olympus/olympus.css`: the tokens, Jarvis's fonts, the HUD type scale, the shared patterns, the veil and the error line.
- `olympus/olympus.js`: a classic script (no module, ES5, never throws). It sets `window.OLYMPUS`: one quality setting,
  the veil, the orb's seat, `hidden()` and `track(renderer)`.
- Test: `python -X utf8 -m tests.test_olympus_kit` (`--table` prints the perf table below). Each app's own test still runs.

## Wiring an app (three lines, before the app's own sheet and modules)

```html
<link rel="stylesheet" href="../olympus/olympus.css?v=o2">
<script src="../olympus/themes.js?v=o2"></script>
<script src="../olympus/olympus.js?v=o2" data-app="mind"></script>
<link rel="stylesheet" href="mind.css">
```

Every call site reads the kit defensively (`const O = window.OLYMPUS || null; O?.track(renderer)`), so an app still works
if `olympus/` is missing. In that case it falls back to its old per-app quality key.

| Call | What it does |
|---|---|
| `O.fx()` | `'ultra' \| 'high' \| 'low' \| 'off'`, read from Jarvis's `localStorage['jfx']` |
| `O.chosen()` | true when the owner picked a level, in Jarvis or in any app. An app's automatic LITE stays off. |
| `O.lite()` | true on `low` or `off`: fewer particles, no antialias, a smaller buffer |
| `O.reduced()` | `prefers-reduced-motion`, or `off`: no drift, no auto-play |
| `O.dpr()` | the pixel ratio to render at: at most 2, at most 1.5 on LITE, 1 when off |
| `O.setFx(level)` | the app's HD / LITE button. It is stored in `jfx`, so Jarvis and every app follow. |
| `O.mode(lite)` | the app's actual look, including its auto-LITE. Sets `html[data-oly-lite]`; never stored. |
| `O.hidden()` | the frame-loop guard: no frame while the tab is hidden |
| `O.track(renderer)` | wraps three.js's `render`. The first call lifts the veil, and `O.stats()` reads `renderer.info`. |
| `O.ready()` / `O.fail(msg)` | lifts the veil (2D apps, no-WebGL fallbacks) / swaps it for the error line |
| `O.theme()` | the OLYMPUS theme's tokens (`{ id, name, bg, glass, line, text, dim, accent, glow, fog, sky, emissive, bloom, mix, harmony, ... }`) |
| `O.onTheme(cb)` | `cb(tokens)` after every theme change (Jarvis's Look sheet, another tab, the frame around the app) |
| `O.tint(base, kind)` | an app colour (`0xrrggbb` or `'#rrggbb'`) blended toward the theme's `fog` / `sky` / `emissive` / `bloom` by its `mix` |
| `O.themeScene({ scene, renderer, clear?, fog?, emissive?, bloom?, redraw? })` | the one-line scene hook: fog, clear colour, background and the listed `THREE.Color`s follow the theme, from their own colours |

## One quality setting

The key is `localStorage['jfx']`, Jarvis's own 3D-effects key on the same origin (`jarvis/index.html`, ⋯ → 3D). It has the
same four levels: `ultra`, `high`, `low`, `off`. If it is not set, the level is `high`, or `low` under
`prefers-reduced-motion`.

| Level | Apps do |
|---|---|
| ultra / high | HD: antialias, every particle, pixel ratio up to 2 |
| low | LITE: no antialias, fewer particles, pixel ratio 1 to 1.5 |
| off | LITE + reduced motion: a still scene, redrawn only on input or data |

- An app's own HD / LITE button (Data City `HQ`, Mind, Oracle, Tyche) writes `jfx`, so the owner sets it once.
- The automatic LITE (slow frames on a weak phone) still works in every app, but only when nobody chose a level. It is
  never stored. This matches Jarvis's `fxAuto`.
- `?lite=1` / `?full=1` (Odeon, Fates, Prometheus) still win, for tests and screenshots.
- The old per-app keys (`dc.q`, `mind.quality`, `oracle.quality`, `tyche.quality`) are read only when the kit is missing.

## Tokens and type scale

| Token | Value | Use |
|---|---|---|
| `--oly-display` | Orbitron, Rajdhani, system | app names, big numbers, the veil |
| `--oly-ui` | Rajdhani, system | everything you read |
| `--oly-t-micro` / `-label` / `-body` / `-title` / `-name` / `-num` | 10.5 / 12 / 14 / 16 / 15 / 26 px | the HUD type scale |
| `--oly-track-label` / `-name` | .14em / .22em | letter spacing of labels / the app name |
| `--oly-tap` | 44px | every tap target |
| `--oly-r-chip` / `-btn` / `-card` | 999 / 12 / 16 px | radii |
| `--oly-st/sr/sb/sl` | `env(safe-area-inset-*)` | safe areas on every edge |
| `--oly-orb-w` × `--oly-orb-h` | 80 × 160 px | Jarvis's orb: the bottom-right corner stays free (96 px for anything fixed at the bottom) |
| `--oly-glass`, `--oly-line`, `--oly-text`, `--oly-dim`, `--oly-blur` | | the glass panels |
| `--oly-accent`, `--oly-accent-rgb` | per app (set by olympus.js) | the app's colour from Jarvis's switcher |
| `--oly-vh` | `100dvh`, falling back to `100vh` | full height that survives iOS Safari's toolbars |

The fonts are Jarvis's self-hosted woff2 files (`../jarvis/orbitron.woff2`, `rajdhani-400/500/600/700.woff2`): one
download, cached for Jarvis and all nine apps. Each app keeps its own colour identity and scene, and the type is shared:

| App | Accent | Glyph | Notes |
|---|---|---|---|
| Data City | `#4f8cff` | Δ | was system font: now Rajdhani with an Orbitron name and numbers |
| Mind | `#5eead4` | Ω | already used Jarvis's fonts |
| Daphne (tree) | `#34f5a0` | Ψ | UI moved to Rajdhani; the TOPOLOGY / RULE terminal readouts keep their mono |
| Oracle | `#7fe9ff` | Θ | already used Jarvis's fonts |
| Odeon | `#ff6b7f` | Ξ | already used Jarvis's fonts |
| Fates | `#ffcf5a` | Φ | already used Jarvis's fonts |
| Hermes | `#f7c948` | Η | stories moved from SF Pro to Rajdhani; Orbitron numbers |
| Prometheus | `#ff7a1a` | Π | already used Jarvis's fonts |
| Tyche | `#e879f9` | Τ | already used Jarvis's fonts |

## Patterns

- **Chip** `.oly-chip`: a 28 px pill in glass, Rajdhani 12 px.
- **Card** `.oly-card`: glass, a 16 px radius, blur 14.
- **Close** `.oly-close`: a 44 × 44 round button with ×. Every app's close button is now 44 px (Data City was 36, Tyche's
  sheet was 36).
- **Taps**: 44 px everywhere. Where the look must stay smaller (Fates' 6M / 12M switch), an invisible `::after` hit area
  gives the 44 px.
- **Back to Jarvis**: inside Jarvis, the orb (bottom-right) switches apps. Opened alone (not framed), the OLYMPUS seal
  `.oly-home` sits in the orb's seat and goes to `../jarvis/`. The app tests' orb-corner checks skip it, because it *is*
  the orb's stand-in.
- **WebKit**: `-webkit-backdrop-filter` with every `backdrop-filter`; `dvh` after every `vh` panel height
  (`max-height: 58vh; max-height: 58dvh`); `touch-action: none` on every 3D canvas (orbiting never scrolls the page);
  `-webkit-touch-callout: none` and no text selection on canvases (a long press orbits instead of popping the callout);
  `-webkit-text-size-adjust: 100%`. The kit itself is Safari 16 safe: no `color-mix`, no `:has`, ES5 only.

## The loading veil

While the app's data and three.js load: a full-screen veil in the app's colour, with the OLYMPUS seal (the app's Greek
glyph in a ring), `OLYMPUS` and the app's name, and a thin scanning bar.

- It **never blocks**: `pointer-events: none`, and it lifts by itself after 12 s whatever happens.
- It lifts (0.42 s fade) on the **first rendered frame**: `track(renderer)` sees the first `render()`, or the 2D apps
  call `O.ready()` after their first draw.
- **Failure**: a script that fails to load, an uncaught error or a rejected promise before the first frame (or the app's
  own `O.fail(msg)`) removes the veil and shows **one line plus Retry**: "Mind could not load: …". Retry reloads the
  page. Images and fonts that fail are never fatal.
- Reduced motion or `off`: no breathing seal, no scanning bar.

## Performance budget (per app, Playwright Chromium, 390 × 844, device pixel ratio 3, HD)

The rules every app keeps:

1. **Pixel ratio capped**: at most 2, at most 1.5 on LITE (most apps use 1 to 1.25), 1 when off.
2. **No layout thrash per frame**: no layout read after a write inside the frame loop. HUD bands are measured on resize or
   by a `ResizeObserver`, never per frame. Tyche's 3D labels now do every DOM write first, then every read, then the
   transforms (1.22 → 0.4 layouts per frame). Mind's cluster-label band is measured on resize.
3. **Hidden tab = no frame**: each loop checks `O.hidden()`. Data City, Oracle, Odeon, Fates and Tyche did not pause before
   (they relied on the browser throttling rAF); now no draw call reaches the GPU while the tab is hidden. This is checked
   by counting WebGL and 2D draw calls with `document.hidden` true.
4. **One three.js**: every app imports `../jarvis/three.module.min.js` (Data City had its own 670 KB copy, now removed),
   cached once for the whole site.

Measured 2026-11-03 (`python -X utf8 -m tests.test_olympus_kit --table`), HD, after 2.5 s on screen. Per frame: draw calls
and triangles from three.js `renderer.info`. Mind and Tyche draw most of their scene as points, which are not counted as
triangles. Daphne (2D canvas) and Hermes (one raw-WebGL shader plus a 2D layer) have no three.js renderer. The heap is
Chrome's `JSHeapUsedSize`. Layouts per frame come from CDP `LayoutCount` / frames: 1.0 means one layout for a
changed HUD text, never a forced one in the loop.

| app | three.js | draw calls | triangles | geometries | textures | programs | pixel ratio | JS heap MB | layouts/frame | fps (headless) |
|---|---|---|---|---|---|---|---|---|---|---|
| datacity | yes | 19 | 34864 | 14 | 6 | 11 | 2 | 6.7 | 0.0 | 6.5 |
| mind | yes | 20 | 28 | 7 | 0 | 7 | 2 | 5.1 | 0.0 | 27.5 |
| tree | no | - | - | - | - | - | - | 11.0 | 0.11 | 61.0 |
| oracle | yes | 132 | 4032 | 50 | 37 | 11 | 2 | 8.9 | 0.95 | 10.0 |
| odeon | yes | 12 | 22382 | 10 | 1 | 8 | 2 | 5.0 | 1.0 | 9.0 |
| fates | yes | 15 | 16232 | 11 | 4 | 8 | 2 | 7.1 | 0.0 | 7.5 |
| hermes | no | - | - | - | - | - | - | 2.0 | 0.0 | 60.0 |
| prometheus | yes | 31 | 6054 | 17 | 17 | 20 | 1.75 | 5.1 | 0.5 | 1 |  <!-- render core, measured 2026-11-03, budget 40 calls / 7,500 tris -->
| tyche | yes | 216 | 24590 | 76 | 21 | 31 | 2 | 7.9 | 1.0 | - |  <!-- render core, glass coins, caustics; budget 270 calls / 30,000 tris -->

Update 2026-11-04 (apps on the render core, HD tier, 390 x 700, pixel ratio 1; the table above is the pre-core measure): odeon 41 draw
calls / 11.9k triangles, fates 47 / 7.2k (34 on LITE), oracle 77 / 9.9k. The post passes add about 15 calls. Budgets now: odeon 60 / 60k, fates 64 / 40k, oracle 170 / 10k.

Update 2026-11-04 (close-out after the night's merges; Playwright Chromium, 390 x 844, dpr 3, **HD tier forced with `?gpu=1`**, 3 s on screen;
`tests/test_olympus_kit.py` `BUDGET` and `EXTRA_BUDGET`, `python -X utf8 -m tests.test_olympus_kit <app>`). Without `?gpu=1` the render core holds
software GL (SwiftShader) to LITE (docs/OLYMPUS_RENDER.md), which hides the bloom and finish passes (about 12-15 draw calls) and the HD pixel ratio: the kit
test's HD checks now pass the flag. The box was at load 50+, so only the counts below are quoted, never the fps:

| app | measured calls / tris (HD) | heap MB | layouts/frame | budget (calls / tris) | verdict |
|---|---|---|---|---|---|
| tyche | 220 / 24,244 | 7.3 | 1.0 | 270 / 30,000 | within |
| plutus | 19 / 4,720 | 4.9 | 0.0 | 25 / 6,000 | within (new row) |
| hermes | no three.js (one raw-WebGL shader) | 4.1 | 0.0 | - | within |
| forum | 111 / 7,140 | 6.4 | 0.5 | 140 / 9,000 | within (new row) |
| daphne (`tree`) | 28 / 47,712 (the 3D laurel tree: one merged bark mesh of tapered tubes) | 12.2 | 0.0 | **35 / 60,000** | **budget was 0 / 0**: written when the app was a 2D canvas; set to the measure +25% |
| pantheon | **about 128 -> 86** / 25,222 | 5.1 | 0.0 | 108 / 31,500 | **over, fixed in the scene code**: the eight statues were six meshes each (48 draw calls); they are six instanced meshes for all gods now (ember colour per instance), same picture |
| athena | 130 / 4,788 | 7.0 | 0.0 | 163 / 6,000 | within (new row). Nine shelves of single book meshes: the 3 in view are drawn plus the effects; merging the book meshes would save about 40 calls and is the next cheap cut |
| ares | 40 / 6,184 | 5.5 | 0.0 | 50 / 7,800 | within (new row) |
| cities | 21 / 130,854 | 5.9 | 0.5 | 27 / 164,000 | within (new row): few calls, many triangles (one generated city); cutting triangles would need LOD, not done tonight |
| kalshicity | 71 / 41,634 | 5.7 | 0.5 | 89 / 52,000 | within (new row) |
| mind | 34 / 752 (+5,014 points) | 5.3 | 0.5 | **44 / 20,000** | **budget was 30**: 34 = 19 scene calls (including tonight's nebula sky and dust, 2 calls) + the bloom / finish passes; raised by 14 with that breakdown |
| prometheus | 53 / 7,186 (HD) | 6.0 | 1.0 | **66 / 9,000** | **budget was 40**: the smithy's twenty static parts are already merged into one mesh per material (50 -> 40 on LITE); on HD the owner-requested effects (embers, heat haze, smoke, light shafts) add about 13: 31 (forge) + 9 (smithy, hammer, ingot, furnace mouth) + 13 (effects); raised with that breakdown |

Pantheon and Prometheus were cut back before anything was raised; Daphne's and Mind's old numbers simply predated their 3D rework; the rest had no budget (new rows,
measure +25%). Hermes needed nothing. Not run again here (not touched tonight): datacity, oracle, odeon, fates.

Budgets (`tests/test_olympus_kit.py` `BUDGET`): draw calls / triangles per frame per app at about 1.25 × the measured
value, the JS heap ≤ 40 MB, layouts per frame ≤ 1.1. Headless fps is SwiftShader (software GL) and only shows relative
cost; an iPhone runs all nine at 60 fps on HD.

## Fixed in this pass

| Issue | Fix |
|---|---|
| Mind: galaxy names slid under the top HUD | Labels fade out within 28 px of the top HUD's bottom edge and the bottom stats' top edge; the band is measured on resize (`mind.labelBand()`). Tested while orbiting. |
| Tyche: slider focus outline changed after its last test | Retested. A new check covers it: a tap leaves no ring, the keyboard shows the 2 px gold ring, and the slider is a 44 px target. |
| Tyche: forced layouts per label per frame | Labels write, then read, then place: 0.4 layouts per frame |
| No hidden-tab pause in 5 apps | `O.hidden()` guard in every frame loop |
| Five quality keys, none shared with Jarvis | One key, `jfx` |
| Sub-44 px taps (Data City search filters, Mind "near" notes, Oracle levels toggle, Tyche close + slider, Fates 6M/12M) | 44 px |
| `vh` panel heights under iOS toolbars (Mind, Daphne, Fates) | `dvh` after the `vh` |
| Fates canvas `100vw` (sideways scroll with a scrollbar) | `100%` |
| Two copies of three.js on the site | Data City uses Jarvis's copy |

## Mind and Hermes, the day upgrade (2026-11-03)

Both apps now have **one top bar and one bottom sheet** (glass, the kit's tokens, the orb's corner free) and expose
`applyTheme(theme)` (`window.mind.applyTheme`, `window.HERMES.applyTheme`). A theme is a flat object of colour names
(`accent`, `bg`, `text`, ...) or CSS custom properties (`'--x': value`), or the same one level down (`{name, vars: {...}}`).
Unknown keys and values with `; { } < >` are ignored. When the kit has a theme API (`OLYMPUS.theme()` / `OLYMPUS.onTheme(cb)`,
or `window.Olympus`), each app applies it at load and on every change; without it nothing changes.

| App | What is new | Module |
|---|---|---|
| Mind | Nebula clouds per galaxy: layered sprites from a cloud atlas baked once, drawn at 1/4 resolution (1/16 of the pixels) | `mind/nebula.js` |
| Mind | Jarvis's memories seated on a tilted cyan ring around Me (the layout pulls them to their seats; the ring follows Me) | `mind/memring.js`, `mind/layout.js` |
| Mind | Synapse pulses along the links when a note opens or learns; quiet idle "thinking" pulses (none under reduced motion) | `mind/synapse.js` |
| Mind | Galaxy / constellation view (crisp stars, bright lines; kept in `mind.view`), focus mode (one galaxy lit, a pill, × / Escape) | `mind/render.js`, `mind/main.js` |
| Mind | The thought stream (lessons and edits, newest first, a tap flies there), an ambient camera when idle | `mind/ui.js`, `mind/controls.js` |
| Mind | The note card: a markdown-ish preview (headings, lists, tasks, quotes, code, `[[links]]` that fly, `#tags`, textContent only), links and backlinks apart; reads the optional `preview` field of `graphSnapshot()` notes, else `snippet` | `mind/markdown.js` |
| Hermes | A scene per card (aurora on a green week, horizon grid on the evals, warp on the hall), a light sweep, kinetic type (words flip up, a gold rule draws), parallax depth in the 3D tilt with a sheen (flat, not preserve-3d: Chromium mis-hit-tests buttons under a preserve-3d tilt, which had broken "Watch again") | `hermes/fx.js`, `hermes/hermes.css` |
| Hermes | Confetti cannons on a green week, gold glitter on the hall, paper confetti that flutters | `hermes/fx.js` |
| Hermes | The all-time hall card (lifetime $, best trade ever, best day, longest green run, win rate) | `hermes/cards.js` |
| Hermes | Pause / play, a tap on the progress bar jumps, the sheet names the story, "Share the week" (one PNG of the whole recap, OLYMPUS fonts) | `hermes/app.js`, `hermes/share.js` |

Perf: Mind stays inside its budget (17 draw calls, 110 triangles, 4.6 MB heap on the kit test); the nebula pass is one extra
small render each frame. LITE keeps two clouds per galaxy, fewer ring motes and no idle thinking; Hermes on LITE draws
its shader at 0.3 px per CSS px and caps particles at 90. Screenshots: `research/handoff/2026-11-03-day/mind_hermes/`.

## Themes (2026-11-03, owner: "whole themes for Olympus, a default (what it is now) and more")

The themes are **data** in `olympus/themes.js` (`window.OLYMPUS_THEMES`, ES5, never throws): seven palettes, each with every
token in `TOKENS` and, except the default, Jarvis's own palette (`--bg`, `--c`, `--neb1` ...). One key on the shared origin,
`localStorage['olympus.theme']` (unknown or missing = `olympus`). Jarvis's Look sheet writes it; every page reads it at start
and on the `storage` event, so an app framed in Jarvis changes live and the others on their next open.

| Theme | Greek | Look | 3D tint (fog) | Scheme |
|---|---|---|---|---|
| **Olympus** (default) | ΟΛΥΜΠΟΣ | today's violet + gold, pixel for pixel (nothing is painted) | each app's own | dark |
| Zeus Storm | ΖΕΥΣ | electric blue, white lightning | `#06142e` | dark |
| Poseidon | ΠΟΣΕΙΔΩΝ | deep ocean teal, aqua | `#03252e` | dark |
| Hades | ΑΙΔΗΣ | black, ember red | `#1a0403` | dark |
| Athena | ΑΘΗΝΑ | marble white, silver, olive (the light theme) | `#2a3027` (a dusk stage) | light |
| Apollo | ΑΠΟΛΛΩΝ | sunrise gold, orange | `#241004` | dark |
| Artemis | ΑΡΤΕΜΙΣ | moonlight silver, indigo night | `#0e1230` | dark |

- **Tokens** (`--oly-*` on `<html>`): `bg`, `bg2`, `glass`, `glass2`, `line`, `edge` (the lit glass rim), `text`, `dim`,
  `accent` (`--oly-tone`), `accent2` (`--oly-tone2`), `glow`, `ok` / `bad` / `warn`, `shadow`, `scheme`, `themeColor` (the
  status bar), and the 3D tints `fog`, `sky`, `emissive`, `bloom` with `mix` (how far an app's own scene colours lean toward
  them) and `harmony` (how far an app's identity colour turns toward the theme accent, at most 16 degrees of hue: Tyche stays
  gold, Oracle cyan).
- **The default paints nothing**: no inline variable, `mix` 0 and `harmony` 0, so every stylesheet value, accent and scene colour
  is exactly today's. `tests/test_olympus_themes.py` compares every computed CSS variable of Jarvis, the nine apps, Zenith and
  Kalshi with the baseline taken before the themes (`tests/fixtures/olympus_default_vars.json`).
- **Where**: `apply('page')` in Jarvis (the full palette; Athena is a marble page with ink text) and `apply('stage')` in the 3D
  apps, Zenith and Kalshi (surfaces that are dark by design: a light theme gives its dark `stage` variant there, because a light
  fog washes every additive glow out).
- **Apps**: `olympus.js` re-points each app's own CSS tokens (`APP_VARS`: `--bg` blended from the app's own page colour, its
  panel / glass, line, text, dim) and the theme-color meta, and harmonises `--oly-accent`. Each three.js app hooks its scene in
  one line (`O?.themeScene?.(...)`, Data City `O?.onTheme(...)` + `O.tint` in `setDay`). Daphne (2D) and Hermes (raw WebGL)
  take the CSS tokens only.
- **Zenith** (root `index.html`) and **Kalshi**: the engine loads async; Zenith's dark look blends `--page` / `--surface*` and
  takes `--line` / `--ink` (its own light look and its accent stay its own); Kalshi blends `--bg` / `--bg2` / `--pr` and keeps
  its mint.
- **Jarvis**: the engine loads async (never part of the start). It keeps a copy of what it painted (`olympus.theme.paint`), which
  Jarvis's `<head>` paints before the first frame, so a theme is there from the first paint, offline too. The Look sheet shows
  seven live tiles (a turning ring in the two accents, the glowing core, a scan line; still on Low / Off and reduce motion).
  The old Jarvis colours (Reactor ... Custom) are now "Jarvis colour": colours of the default theme, so picking one goes back
  to Olympus. Light themes get `html[data-oly-scheme="light"]` overrides in `jarvis.css` (white glass, ink text, the reactor in
  a dark lens).
- **Polish shared by all** (`olympus.css`): one set of motion curves (`--oly-ease`, `--oly-ease-in-out`, `--oly-spring`,
  `--oly-dur-1/2/3`), a keyboard focus ring with zero specificity (`:where(...)`: an app's own ring wins), glass with a lit
  edge (`.oly-glass`, `.oly-card`), and the **Scanlines** option (Look sheet; `localStorage['olympus.grain']`): one static
  composited layer of fine scanlines + SVG film grain, no animation, never a tap, so the perf budgets hold.
- **Adding a theme**: one entry in `THEMES` with every token (+ `jarvis`, + `stage` if light). The test lists any token
  missing and checks WCAG AA (4.5:1) for the text of every theme on its page and glass (the light one everywhere it is read).
