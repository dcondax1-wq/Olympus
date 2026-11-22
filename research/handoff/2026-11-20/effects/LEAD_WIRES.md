# night-effects: what the lead wires (2026-11-20)

Branch `night-effects`. Nothing here touches sw.js, build_web_dashboard.py, jarvis/, the APPS table, olympus/doors.js, warp.*, cities/, datacity/ or engine/.

1. **No sw.js bump needed.** The new files live in `olympus/` and are loaded only by `gate/` and `hub/doors.html`; all three folders are in the root
   sw.js `OTHER_APPS` list (never cached there) and every URL carries a version (`home-fx.css?v=x1`, `home-fx.js?v=x1`, `gate.js?v=g9`).
2. **Add the new test to an area** in `tests/run_area.py` (olympus): `"home_fx"` (tests/test_home_fx.py, 18 checks, ~40 s, browser).
3. **olympus-live.html** (the Gate copied to the site root by the build): nothing to do; home-fx loads from `GATE_BASE` like the rest.
4. **Pre-existing, not mine:** `tests/test_gate_page.py` b. fails twice on the app folder `widget/` (in apps-list.js and on disk, not in
   `olympus/gate-catalog.js`). The widget landing should add it to the catalog (or mark it workshop). I also corrected that test's
   expected script list to the Gate's real one (it said `gate-catalog.js?v=nv4`, the page loads `nv3`).
5. **Switches** (no UI yet; Settings could offer them later): `localStorage['oly.homefx']` = `still` (one still frame) or `off` (the plain
   revamp look). 3D effects Off (`jfx` = off) and reduced motion already give the still frame; 3D effects Low gives fewer motes, 1.5x pixels.
6. **Sound on the home** plays only if Sound is switched ON in Settings (`olympus.sfx` s = true, not muted). With no choice the home does not
   load the sound engine at all: its first-tap start was a 217 ms task at 4x CPU.
7. **Doors under a light look:** hub/doors.html loads no olympus/themes.js, so it stays dark when the owner picks Ivory (true before this branch too). Loading themes.js there is a one-line change if wanted.
8. **Measure again:** `python tools/fx_home_perf.py --tag after --json FILE` (long tasks at 4x CPU, dark + Ivory); `python tools/fx_home_shots.py DIR` (screenshots + 6 s video with live fixture numbers).
