# Zenith with dashboard FX + OLYMPUS NIGHT (DESIGN, day-arenas 2026-11-20)

Screens (phone 390 x 844 @2x, laptop 1280 x 800, reduced motion): `phone_1_top.jpg`, `phone_2_scrolled.jpg`, `laptop_1_top.jpg`,
`phone_reduced_motion_1_top.jpg`.

## What Zenith wears now

- **Look**: OLYMPUS NIGHT (themes.js 'night', the kit default): black, near-black violet cards, deep violet outlines, bright gold accents
  only (ZEUS name, the NQ button, the selected tab), mint for profit, red for loss. No brown: faint gold washes (the selected side item, the
  kit's hero glow) are violet under this look.
- **Effects** (`zenith_fx.js` tags Home's cards for `olympus/dashfx.js`, after start-up): glass cards with a slow violet / gold edge light,
  the hero (balance curve) leans in 3D under the finger / mouse, cards below the fold rise in, an aurora + a few drifting dots behind
  everything (30 fps, paused off screen / hidden tab, none under reduced motion or Save-Data). Glass only where a card's `::before` is free.
- **No jumps** (`zenith_settle.js` + the NQ strip slot + home.json first): see `../../olympus2/design/ZENITH_SPEED.md`.

## Numbers (390 x 844, 4x CPU, 1.6 Mbps / 150 ms, gzip; 3 runs)

| | Before today | Now (with FX) |
|---|---|---|
| Layout shift (CLS) | 0.96 - 1.14 | **0.016 - 0.049** |
| First Home content | 4.2 - 4.4 s | **3.2 - 3.4 s** |
| LCP (the money card's big number) | 4.4 - 5.0 s | 5.8 - 7.0 s (it shows with the finished Home; FX start after start-up) |

The effects start only once Home has settled: with them running during start-up the shift went back to 0.12 (they competed with the
add-ons for the phone's CPU) and the slow-site check (open from the saved copy in < 5.5 s) failed while dashfx.css was a <head> link.

## Tests

`test_zenith_settle` 14/14 (FX tagged after start-up, glass / tilt / aurora, nothing animates inside the start-up copy), `run_area zenith`
11/12 (phone_e2e needs a GitHub login to clone the live site), `zenith_mode` 70/70, `test_dashfx` 18/18.
