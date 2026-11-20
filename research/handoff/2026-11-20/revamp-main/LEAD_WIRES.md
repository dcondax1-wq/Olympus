# LEAD_WIRES: night-revamp-main (2026-11-20)

The lead-only files this branch needs touched. Nothing here was edited by the helper.

## 1. `tools/web_public/jarvis/sw.js`: new cache so phones get the faster Jarvis
- Line 48: `const CACHE = 'jarvis-v71';` -> `const CACHE = 'jarvis-v72';`
- Line 49: put `'jarvis-v71'` at the front of the `OLD` list.
- Why: `core-visual.js` and `home3d.js` are cached with no `?v=` (SHELL, line 53). They changed: the 3D orb and the constellation pause while you scroll.
  Without a new cache name the installed app keeps the old, laggy copies. (`backdrop.js` is now `?v=b5` in `jarvis/index.html`, so that one refreshes by itself.)
- No `shell.css` entry needed: Jarvis does not load `olympus/shell.css` (a link held its first paint on a slow site, jarvis_hub j).

## 2. `tools/web_public/sw.js` (the Zenith site worker)
- Line 94: `const CACHE = 'le-public-v157';` -> `'le-public-v158'`, so the root `index.html` with the new tab bar replaces the cached one.

## 3. `tools/web_public/jarvis/apps.js` and the `olympus.js` APPS table
- No change needed. The ids stay the same. The archive is a list in `olympus/doors.js` (`ARCHIVE`, `archived(id)`): every app is still in exactly
  one door, and `tests.test_apps_list` passes (44/44).
- Optional follow-up: `jarvis/switcher.js` (not lead-only) could fold the same `ARCHIVE` ids. I did not change it tonight because another helper
  may be working in Jarvis. The Doors page and the launcher fold them already.

## 4. `tools/build_web_dashboard.py`
- No change needed. `olympus/shell.css` is a static file in `tools/web_public/`, so it publishes like any other.
- Check: if the publisher copies `gate/index.html` to the site root as `olympus-live.html`, the new `<link>` builds its path from
  `GATE_BASE` like the others do, so it works at both paths.
