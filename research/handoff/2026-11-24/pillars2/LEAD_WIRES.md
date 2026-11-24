# day-pillars2: lead-only wiring (helpers never edit sw.js, build_web_dashboard.py, jarvis/apps.js, the olympus.js APPS table)

## Why the owner can't see the Four Pillars
https://dcondax1-wq.github.io/pillars/ returns 404: `tools/build_web_dashboard.py` copies only the app folders in its app tuple,
and `pillars` is not in it. The sw OTHER_APPS entry is there, but the folder never reaches the site.

## Wires (in this order)
1. DONE by lead (pc 03adb9cb4). Was: **publish the Pillars folder.** Add `"pillars"` to the app tuple in `tools/build_web_dashboard.py` (~line 1243, next to `"nq"`),
   build, then `gh_publish`. This also fixes `test_homescreen` (its build list expects `pillars`).
2. **Root service worker cache:** bump `CACHE` in the root `sw.js` from `le-public-v211` to `le-public-v212` (root `index.html` / Zenith
   changed; `python tools/bump_versions.py --check --base origin/pc` asks for it). Returning iPhones then load the new Home/Zenith on next open.
3. **Gate catalog row** (so Search and More list it; fixes the 2 `test_gate_page` catalog fails), in `olympus/gate-catalog.js` after the `'nq'` row:
   ```js
   ['pillars', 'pillars/', 'Four Pillars', 'The four pillars', 'LIT, ATLAS, BLITZ, ORDER FLOW: status, edge, next', 'bots', 'bots', 'four pillars lit zlarior atlas blitz order flow orderflow ticks edge strategy what is next', 'nq'],
   ```
   then `python tools/bump_versions.py --apply` (cascades gate-nav g11 -> g12 across ~50 apps and the Jarvis/Kalshi sw caches; I left it to you).
4. DONE in this branch: insights.json landed on pc; pillars-data.json is rebuilt from it (LIT 5, ATLAS 4, BLITZ 5 lessons, ORDER FLOW 'Waiting').
   After each market-learn run: `python tools/build_pillars.py` (`--check` says when it is stale).
   Home Screen kit for pillars/ (manifest, 180/192/512/maskable icons, capable, status bar, title, theme-color, viewport-fit) is in this branch: test_homescreen passes for pillars.
5. Optional: Jarvis `apps.js` / olympus.js APPS entry for Pillars (icon is `pillars/icon-192.png`; the folder has its own manifest + apple-touch-icon,
   so "Add to Home Screen" from /pillars/ already gives a "Pillars" icon).

## Design notes
- Home (gate/): the hero is a **header band** (4 live chips, 3D colonnade glowing behind them) in place of the one-line subtitle, so the
  owner's 6 dashboards + More stay on the first 390x844 screen (test_gate_page / home_six rule).
- Zenith (/): the big 3D hero sits at the top of Today only (hidden on other routes).
- NQ: frame-only markup after the banner, filled by `pillars/hero.js` after `load` (NQ blocking budget is 300 KB; now under). No toast on NQ
  (it covered the veil tap); no extra data file is read (uses `window.NQ.S`).
- The "What's new: The Four Pillars" toast shows once (localStorage `oly.new.pillars`) on Home and Zenith.
- Effects: `nightfx.js` particle field (<=90 motes, behind content, 30 fps when slow, off on reduced motion / low power / Save-Data),
  `livefx.js` glow on changed numbers (class only, never rewrites text), light shafts + tilt parallax in the 3D scenes.
  `?lite=1` forces flat, `?fx=3d` forces 3D.
- BLITZ stays hidden as a live bot: shown only as a pillar with research numbers.
