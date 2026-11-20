# cities3: what the lead must wire (helpers may not edit these files)

**Nothing is required.** Every changed file is behind its own new `?v=` tag set inside my folders, and `gate/`, `cities/`, `datacity/`,
`widget/` are in `sw.js` OTHER_APPS (never cached by the root worker), so phones pick the new files up on the next open.

Optional, one line each:

1. `tools/web_public/hub/doors.html` (not my folder, not lead-only): `olympus/home-fx.css?v=x1` -> `?v=x2` and `olympus/home-fx.js?v=x1` -> `?v=x2`
   so the Doors page gets the faster intro + tap-to-skip (it still works on x1; the file is the same path).
2. `tools/web_public/sw.js` line 94: `le-public-v167` -> the next free number, only if you bump it anyway for another branch
   (belt and braces for phones that cached the root shell).
3. The root copy of the Home (`olympus-live.html`, if your build copies `gate/index.html` there): rebuild so it carries `gate.js?v=g11`,
   `gate.css?v=g13`, `home-fx ?v=x2`.

Tags I moved (all inside my folders, tests updated with them):
- gate/index.html: gate.js g9 -> g11, gate.css g11 -> g13, home-fx.js/css x1 -> x2 (round 4) (pins in tests/test_gate_page.py)
- cities/world: ow-main/ow-core/ow-scene/ow-shaders w3 -> w4, world.css w2 -> w3 (pin in tests/test_world_page.py)
- widget: olympus-widget.js w1 -> w2, glance.js 1 -> 2
- new files: cities/frame-safe.js?v=1 (World + Cities), datacity/frame-safe.js?v=1 (Data City's own copy: it is also served from live/ and demo/)
