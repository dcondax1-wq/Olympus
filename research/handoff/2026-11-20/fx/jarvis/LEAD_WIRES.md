# JARVIS FX in OLYMPUS NIGHT: lead wires (day-jarvis)

Owner via lead 15:50 ET: "It needs some 3D, it needs some effects". Then 16:00 ET: the switcher's colours are the site palette
OLYMPUS NIGHT (black, violet outlines #3e255e / #462a6a / #4d2e76, violet ring #9d59ee, bright gold #f1c14b / #ebbf4f, mint #77db89).
The first pass (cyan, "no gold") is fully replaced: nothing cyan is left.

## What changed (helper files only)
- `jarvis/jfx.css?v=2` (new): ZEUS card = black glass, violet outline + violet top edge with a violet -> gold line, a light sweep every
  7 s, the title bright gold with a violet glow, gains mint / losses red with a soft glow; KALSHI / NQ tiles (+ bot cards, tiles):
  black glass, violet outline, a gold (Kalshi) / violet (NQ) side bar and glow layer that breathes, a 3D press. Ivory: light paper cards.
  Loaded `media=print` + onload swap: never holds the first paint.
- `jarvis/jfx.js?v=1` (new, deferred, starts when idle after `data-ready`): $ roll-ups on ZEUS balances / today, the tiles, #npnl
  (the real text is the final number all along; the rolling one is drawn over it); a 3D finger lean + glare on switcher cards.
  Reduced motion / `data-fx=low`: off.
- `jarvis/switcher.js`: colours exactly as before (the palette's source); one line: the carousel keeps the finger's lean (`data-lean`).
- index.html: the two links above; the business chips' text colour slot fixed (n10 -> n37, a dark slot in some looks).
- Classic Jarvis (default) and its 3D core untouched.

## Wires for the lead
1. `tools/web_public/jarvis/sw.js` SHELL: add `'./jfx.css?v=2', './jfx.js?v=1'`; bump CACHE (jarvis-v83 -> v84; switcher.js is
   untagged in SHELL, the bump refreshes it). Still from earlier today: `'./shortcuts.html', './shortcuts.js?v=2'`, `biz.js?v=b2` -> `b4`.
2. DESIGN's `olympus/dashfx.js` was not on day-arenas at 16:00 ET; jfx.js is self-contained. If it lands, it can take over the roll-up
   (selectors: `.zeus-b, .zeus-d, .hc-n, .tile .t-v > b, #npnl, #kusd`).
3. When DESIGN ships OLYMPUS NIGHT as kit tokens, jfx.css's `--jfx-*` (top of the file) can point at them.

## Tests
- `tests/test_jarvis_fx.py` 14/14 (in run_area jarvis): non-blocking load, OLYMPUS NIGHT hexes, switcher untouched but the lean hook,
  computed ZEUS / tile colours, roll-up keeps the real text and lands, finger lean + release, reduced motion = no roll, Ivory light cards.
- test_jarvis_home_agora 44/44 (unchanged from the base), test_jarvis_shortcuts 15/15. test_jarvis_hub: see the commit / message.

Shots (390 x 844 @2x): 1-2 before, 3-5 after (home, ZEUS + tiles, switcher), 6-7 Ivory before / after.
