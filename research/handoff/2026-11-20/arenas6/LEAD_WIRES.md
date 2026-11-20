# Lead wires for the 6 arenas (files helpers may not touch)

1. **sw.js**: nothing needed. `gate/` and `olympus/` are in its OTHER_APPS list (never cached there); the new files ride on
   version pins: `gate/arenas.js?v=2`, `gate.css?v=g22`, `navfx.css?v=5`, `navfx.js?v=2`, `olympus/doors.js?v=d12`,
   `hub/doors.js?v=d5`, catalog `nv10`, `olympus/dashfx.css?v=d1` / `dashfx.js?v=d1` (now also on Home).
2. **jarvis/apps.js / olympus.js APPS**: untouched. Jarvis has no row in the generated app list, so the launcher's Arenas row makes
   its Jarvis tile from doors.js ARENAS (`jarvis/`). If you want it from the list instead, add a `jarvis` row there and rebuild
   `olympus/apps-list.js` (`python tools/apps_list_build.py`).
3. Optional, same order elsewhere (JARVIS / DESIGN owned files): the Jarvis switcher's FIRST (`jarvis/switcher.js`) and the Atlas
   zones (`atlas.js`) could lead with cities, kalshi, nq, jarvis, agency, business.
4. Business page "Planner at its top": Home's Business tile carries the Planner link; a Planner link inside `business/index.html`
   itself is DESIGN's page.
5. test_warp a./b. fail on pc too (from the merged Zenith page), not from this branch.
6. **web_next/sw.js** (smoke's site_checks fault until done): its precache entry `/js/next/doors.js?v=d11` -> `?v=d12` (the
   launcher now loads d12, which has ARENAS), and bump that worker's version. Or run `python tools/bump_versions.py --apply`.
7. smoke perf_sweep "nq block 301 KB > 300" is not from this branch (nq/ untouched here).
