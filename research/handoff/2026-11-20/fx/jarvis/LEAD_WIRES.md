# JARVIS FX, no gold: lead wires (day-jarvis)

Owner via lead 15:50 ET: "It needs some 3D, it needs some effects ... NO GOLD". Jarvis home + ZEUS / accounts cards + the switcher.

## What changed (helper files only)
- `jarvis/jfx.css` (new): ZEUS card = navy glass, cyan top edge (cyan -> blue -> violet line), light sweep every 7 s, cyan -> violet
  title, glowing gains / losses; KALSHI / NQ tiles + bot cards + tiles: glass with cyan / violet glow that breathes, 3D press;
  the AGORA look's colour slots redefined (Midnight navy + violet -> blue -> cyan accents, same lightness = same contrast);
  Ivory gets blue / violet ink instead of gold. Loaded `media=print` + onload swap: never holds the first paint.
- `jarvis/jfx.js` (new, deferred, starts when idle after `data-ready`): $ roll-ups on ZEUS balances / today, the tiles, #npnl
  (the real text is the final number all along, the rolling one is drawn over it); 3D finger tilt + glare on switcher cards.
  Reduced motion / `data-fx=low`: off.
- `jarvis/mark.svg` (new): the Home Screen temple icon in cyan / violet (title + footer marks).
- `jarvis/switcher.js`: CSS accents gold -> `--nx-hi` cyan / `--nx-vi` violet on every app (warnings stay amber); group colours
  (GCOL) cyan / blue / violet; the doors keep `olympus/doors.js` colours (test-pinned) and are swapped on screen (NOGOLD map);
  the carousel keeps the finger's lean (`data-lean`).
- Classic Jarvis (the default, violet) unchanged: `--c` #a855f7 (test-pinned). Jarvis's 3D core untouched.

## Wires for the lead
1. `tools/web_public/jarvis/sw.js` SHELL: add `'./jfx.css?v=1', './jfx.js?v=1', './mark.svg?v=1'`; bump CACHE (jarvis-v83 -> v84).
   switcher.js is in SHELL without a tag: the CACHE bump refreshes it.
   (Still from earlier today: `'./shortcuts.html', './shortcuts.js?v=2'`, `biz.js?v=b2` -> `b4`.)
2. `olympus/doors.js` (DESIGN / doors owner): its door colours are still gold / bronze / olive (#c8a24a, #b5a642, #9c6b3c, #7f8a52).
   If DESIGN recolours them, switcher.js DIST must follow (test_jarvis_home_agora pins equality); NOGOLD then becomes a no-op.
3. `olympus/zeus_core.js` (shared ZEUS card) still gold on other pages (hub/zeus.html): jfx.css overrides it on Jarvis only.
4. DESIGN's `olympus/dashfx.js` was not on day-arenas yet (checked 16:00 ET); jfx.js is self-contained. When it lands, it can
   replace the roll-up (same selectors: `.zeus-b, .zeus-d, .hc-n, .tile .t-v > b, #npnl, #kusd`).

## Tests
- `tests/test_jarvis_fx.py` 16/16 (new, in run_area jarvis): non-blocking load, no gold in files / switcher CSS / mark, computed
  colours of ZEUS / tiles / orb ring, roll-up keeps the real text and lands, finger tilt + release, reduced motion = no roll, Ivory ink.
- test_jarvis_home_agora 44/44 (the "neon hex" rule now allows cyan #22d3ee: the owner's new accent).
- test_jarvis_hub: 272/272 before the last switcher tweak (carousel keeps the lean); rerun pending at this commit. test_jarvis_shortcuts 15/15.
- Pre-existing, not mine: tests/test_cities_network_switcher.mjs fails the same on the base (a city page's CITY button).

Shots (390 x 844 @2x): 1-2 before, 3-5 after (home, ZEUS + tiles, switcher), 6-7 Ivory before / after.
