# LEAD_WIRES: day-arenas (2026-11-20)

Lead-only files this branch needs touched. Nothing below was edited by the helper.

## 1. `tools/web_public/sw.js` (the Zenith site worker): one cache bump
- Line 94: `const CACHE = 'le-public-v167';` -> `const CACHE = 'le-public-v168';`
- Why: the root `index.html` now loads `zenith_nq.js?v=4` (was `?v=3`): Home no longer jumps when the PC's status arrives (layout shift 0.30 -> 0).
  The worker answers `index.html` from its saved copy first, so without a new cache name a phone keeps the old `?v=3` page for a while.
- Nothing else: every app folder I changed (aegis, business, compass, demeter, fates, helios, hera, journal, ledger, olympus/) is already in
  `OTHER_APPS` (line 99), so the worker never touches them; their own `?v=` tags are bumped (see REPORT.md).

## 2. `tools/web_public/jarvis/sw.js`, `kalshi/sw.js`
- No change: neither caches the apps or the olympus/ files I changed.

## 3. `tools/web_public/jarvis/apps.js` and the `olympus.js` APPS table
- No change. No new app and no new id. The two new files are kit files (`olympus/pulse.js`, `olympus/pulse.css`) and one app file
  (`helios/riskweek.js`); `python tools/apps_list_build.py --check` stays in step.

## 4. `tools/build_web_dashboard.py`
- No change: the new files are static files under `tools/web_public/` and publish like the rest. Checked with a local build
  (`--out <scratch>/site`): `olympus/pulse.*` and `helios/riskweek.js` land in the site.

## 5. Optional (not lead-only, left for whoever owns them)
- `tests/run_area.py` now lists `pulse` in the `olympus` area (one line, done here).

## Round 3 (the Decide view, business/plan.html)
- Door shortcut: if a door / hub tile says "Answer 3 cards" (or similar) and should land on the new ranked view, point it at
  `business/plan.html#decide` (the section id is `decide`). I did not find such a tile in my folders; the Board and ZEUS keep their own Decide box.
- Optional: `board/index.html` line 73 and `hub/zeus.html` line 131 load `../business/decide.js?v=2`; bump both to `?v=4` so phones get the
  same file as plan.html. Nothing changes on those two pages (the ranked look only turns on with `data-decide-mode="rank"`; the tap and its
  POST are byte-for-byte the same), so this is housekeeping, not required. I did not edit them (board/ and hub/ are not mine).
