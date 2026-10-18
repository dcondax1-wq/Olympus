# Home Screen app icon v2 (2026-10-17)

The owner's verdict on the shipped Oracle Orb was "it's ugly". This round starts again from what an icon has to do at
60 pt on an iPhone: one bold silhouette, high contrast, rich light, no clutter, on a dark base with vivid neon.

**Recommendation: ship `chrome_drop`.** `sweep` is the alternative if the owner wants the trading idea spelled out.
Both asset sets are ready in `final/`. Nothing in `web/icons/` or any HTML/manifest was changed.

- `contact_sheet.png`: all 8 concepts large, plus each at 180 / 120 / 60 px on dark and 60 px on light (ranked order).
- `homescreen_dark.png`, `homescreen_light.png`: an iPhone 15 Pro screen (1179 × 2556) at real size. Icons are 180 px
  (60 pt at 3x) with a 27% corner radius, in a 4-column grid among plain placeholder apps. Each concept appears once.
- `previews/<concept>_512.png`: the 8 concepts.
- `final/chrome_drop/`, `final/sweep/`: full asset sets. `final/small_sizes_check.png` shows both at 180/120/60/40 px.

## Why the old icon failed at 60 pt

Oracle Orb (`web/icons/icon-512.png`):
- **No silhouette.** The hero is clear glass, so its only edge is a 1–2 px pink rim. At 60 pt it reads as a pale
  lavender circle, not an object.
- **Low contrast.** Pastel pink glass and white haze sit on purple haze of about the same value, so the subject never
  separates from what is behind it. Only the corners are black, and no solid area is truly saturated.
- **The meaning is in specks.** The candles are about 3 px at 60 pt, and the liquidity line is a dotted hairline.
- **Clutter.** Two subjects (the orb and a chrome pedestal) plus a starfield and sparks that turn into grain.

The earlier concepts fail for the same reasons:
- `icon_3d/previews`:
  - monolith: a generic synthwave sunset whose "candle" is a dark slab.
  - gargantua: the white haze washes it out, and the jets are hairlines.
  - gyro: a tangle of thin rings.
  - crystal: a wireframe in pale cyan haze.
  - letters3d: two small letters. Letters are never iconic at 60 pt.
- `icon_concepts`:
  - hud_lock: the hairline reticle vanishes.
  - event_horizon: reads as Saturn.
  - hex_core: the most legible old one, but outline-only and thin.
  - neon_tube: thin neon letters.
  - holo_chip: the circuit traces turn into texture.
  - synth_horizon: four subjects; it reads as a sunset.

Common causes:
1. Hairlines that are 1–2 px at 60 pt.
2. Outlines and glass with no filled mass.
3. Pastel or white glow that lifts the background up to the subject's value.
4. Two to four subjects per icon.
5. A one-hue palette (magenta on purple) where cyan only appears in hairlines.
6. The meaningful element (the candle) covers under 10% of the tile.

Rules for v2:
- One subject filling 65–80% of the tile height.
- A near-black base.
- Magenta and cyan as large areas, not lines.
- White speculars as the brightest points.
- No structural line thinner than about 2 px at 180 px; only highlights and glow are finer.
- No stars, grids or text.

## The 8 concepts, ranked (judged on the Home Screen sims at 60 pt)

| # | Concept | Tool | Verdict at 60 pt |
|---|---|---|---|
| 1 | **Chrome Drop**: a drop of liquid chrome over a dark pool with a cyan ripple ring | three.js | The strongest silhouette: a teardrop reads even as a blur. It is the only real 3D object (neon reflections, white speculars), and it carries the name: liquidity hitting a pool. |
| 2 | **Sweep**: one glass candle whose lower wick pierces a cyan liquidity line, with a flare at the pierce | SVG (vector) | The most literal and legible: "a candle sweeping a level" reads in one glance. It is crisp at every size. It is less 3D, and candles are common in trading app icons. |
| 3 | Reactor: a thick chrome torus around a plasma core with a white-hot candle | numpy ray-shaded | A bold ring with the strongest colour punch, and it reads as "engine". The candle is too small, so it could be a power, camera or target app. |
| 4 | Eclipse: a black disc with a magenta corona and a diamond-ring flare on the liquidity line | numpy | Gorgeous and high contrast, but it has no trading meaning. It is also the black-hole family (Gargantua, Event Horizon) that was already passed over. |
| 5 | Hex Engine: the classic hexagon mark as a bevelled plate with a glowing candle slot | SVG | Keeps the old brand mark and reads at 120 px. At 60 px, plate + rim + slot + line is busy and looks like a game badge. |
| 6 | Prism: a faceted amethyst crystal as the candle, its point piercing the line | SVG | A pretty gem, but a thin vertical sliver with the least mass at 60 px. It echoes the old Crystal Core. |
| 7 | Glass Tile: a frosted-glass slab with the sweep glyph on its face | three.js | A rounded tile inside the rounded tile wastes a third of the area, and the frosted glass is invisible at 60 px. |
| 8 | Ribbon: one neon tube that dives through the line and shoots up to the target | three.js | The V reads as a check mark (a to-do app), not a sweep. |

The two finalists were then polished:
- `chrome_drop` went through more than 20 renders:
  - It started with a milky environment that washed the chrome grey, and a hard pool reflection that looked like a cup.
  - The final version uses a black studio with large magenta and cyan softboxes, a violet front fill with a dark horizon
    band, and a Fresnel bounce light from the pool.
  - The drop is plumper, and the framing is measured: an 8% top margin, with art filling 79% of the height.
- `sweep` was rebuilt as a fuller glass candle, with cylinder shading, a specular streak, a cyan bounce from the line
  and a faint reflection below it.

## Final asset sets

`final/chrome_drop/` and `final/sweep/` each contain:

| File | Description |
|---|---|
| `icon-1024.png` | The master: full bleed, opaque. |
| `icon-512.png` | 512 px. |
| `icon-192.png` | 192 px. |
| `apple-touch-icon.png` | 180 px. |
| `icon-maskable-512.png` | The background stays full bleed and the artwork sits inside the central 80% circle. The drop's camera is pulled back 1.2×, so the bright art reaches 39% of the size from the centre. The sweep artwork is scaled 0.8 about the centre; only the fading ends of the line go outside the circle. |
| `icon.svg` | For the sweep, the real vector icon. For the drop, an SVG that embeds `icon-512.png` as base64. |

All PNGs are RGB with no transparency, downscaled with LANCZOS. The 192 px and 180 px files get a light unsharp mask
(radius 0.8, 45%) so the neon rims stay crisp at Home Screen size.

To ship one, copy these files into `web/icons/`; the public dashboard copies from there:
- `apple-touch-icon.png`
- `icon-192.png`
- `icon-512.png`
- `icon-maskable-512.png`
- `icon.svg`

Then bump `?v=orb1` everywhere it appears so phones fetch the new icon:
- `web/index.html`, `web/manifest.webmanifest`
- `web_next/index.html`, `web_next/manifest.webmanifest`, `web_next/sw.js`
- `tools/web_public/index.html`, `tools/web_public/manifest.webmanifest`, `tools/web_public/sw.js`

iOS caches Home Screen icons: re-add the app to see the change.

## How to re-render

```
cd research/design/icon_v2/src
npm install              # three@0.160.0 (node_modules/ and out/ are gitignored)
python3 build.py all     # masters -> previews + sheets -> final assets, about 5-10 min on 4 cores
python3 build.py masters chrome_drop chrome_drop_mask   # or re-render just some masters, then: build.py sheets / assets
```

Requirements:
- Playwright with Chromium (cloud sessions have it: `npm root -g` supplies NODE_PATH), numpy and Pillow.
- `build.py` serves `src/` on 127.0.0.1:8799 for the three.js scenes and stops the server when it finishes.

Where each concept comes from:
- `scenes/*.js`: the three.js scenes (`chrome_drop`, `glass_tile`, `ribbon`).
  - They are rendered through `render.html` and `shot.js`, with `?ss=N` for N×N supersampling.
  - The drop's look is tuned by URL parameters at the top of `chrome_drop.js`, for example `zoom`, `s`, `ring`, `mag`,
    `cya`, `front` and `hz`.
- `svg/*.svg`: hand-written SVG (`sweep`, `prism`, `hex_engine`), rendered by Chromium via `svg2png.js`.
- `py/*.py`: numpy renders (`reactor`, `eclipse`) using `iconlib.py`, which provides an FFT bloom and an ACES tone map.
- `py/sheets.py`: the contact sheet, the Home Screen sims and the 1:1 size strips.
