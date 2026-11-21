---
tags:
  - zeus/apps
  - jarvis
type: "apps"
---

# ZEUS Apps (Olympus + Jarvis)

> [!info] 77 apps behind 4 doors
> Every app, behind one of the FOUR DOORS (ZEUS Trading, Money, Kalshi, More: `tools/web_public/olympus/doors.js`, `docs/ORGANIZATION.md`, 2026-11-18; the same lists as the Atlas command center `tools/web_public/atlas/`). The door is the way you find it (column District); the **group** column is the older registry group (`jarvis/apps.js`: trading / money / life) that the launcher and the Jarvis switcher use. **This file is generated: `python tools/olympus_map_build.py` (do not edit the table by hand; `tests.test_olympus_map` fails when it is stale).**

Finding things: Atlas has search (names and plain words), pinned rooms (long-press a room or tap the star), recent rooms, a "what needs me now" strip and an all-apps-on-one-screen view. The Zenith launcher button and the Jarvis orb have the same search, favourites (long-press a tile), recent apps and a MAP view.
Data: apps only read published JSON (and bundled `fixture.json` / demo fallbacks). No app places orders. Look: AGORA (`docs/DESIGN_AGORA.md`). Wiring a new app: `tools/wire_new_apps.py` + `tools/new_apps.json` (`docs/NEW_APPS_WIRING.md`).
77 apps. Rebuild the registry list after editing `jarvis/apps.js` or `olympus.js`: `python tools/apps_list_build.py`; recount: `python tools/apps_list_build.py --check`.

## Doors

- [[Apps ZEUS Trading|ZEUS Trading]]: 28 apps
- [[Apps Money|Money]]: 15 apps
- [[Apps Kalshi|Kalshi]]: 5 apps
- [[Apps More|More]]: 29 apps

## Where the organizing code lives

| Piece | File | Test |
|---|---|---|
| The four doors (ZEUS Trading, Money, Kalshi, More: each door's shortcuts in plain words + every app in exactly one door) | `tools/web_public/olympus/doors.js` (= `web_next/js/next/doors.js`); the page `hub/doors.html` + `hub/doors.js`; the Gate's four door tiles; docs/ORGANIZATION.md | `tests.test_apps_list` (part d) |
| Atlas command center (districts, search, pins, recent, needs-me strip, one-screen map) | `tools/web_public/atlas/` (`atlas.js`, `hub.js`, `atlas.css`) | `node --test tests/test_atlas_standalone_hub.mjs`, `tests/test_atlas_intro.mjs` |
| Zenith launcher sheet (favourites, search, recent, MAP) | `tools/web_public/launcher.js` = `web_next/js/next/launcher.js` (byte-identical) | `tests.test_apps_list` |
| Jarvis switcher (search, MAP, favourites, recent) | `tools/web_public/jarvis/switcher.js` | `tests.test_jarvis_hub` (parts n, p, s) |
| World-to-world jump (hyperspace out of the page you tap, each world's arrival signature through a View Transition; reduced motion = a fade) | `tools/web_public/olympus/warp.js` + `warp.css` (themes.js loads it and reads the arrival in `<head>`; agora.css / jarvis.css / kalshi.css / zenith_agora.css @import warp.css) | `tests.test_warp` |
| App registry | `tools/web_public/jarvis/apps.js` -> `olympus/apps-list.js` | `tests.test_apps_list` |
| This map | `tools/olympus_map_build.py` -> `docs/OLYMPUS_MAP.md` | `tests.test_olympus_map` |

Back to [[ZEUS Home]]
