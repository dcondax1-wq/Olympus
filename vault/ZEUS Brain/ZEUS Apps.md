---
tags:
  - zeus/apps
  - jarvis
type: "apps"
---

# ZEUS Apps (Olympus + Jarvis)

> [!info] 80 apps behind 7 doors
> **How Olympus is organized (2026-11-21, owner: "more organized").** One structure, everywhere:

1. **Home** (`gate/`, where the Olympus app opens) shows **the 6 main dashboards** in the owner's order (2026-11-22): **NQ Bot** (ZEUS: accounts, trades, brain), **Jarvis**, **Websites** (agency, factory, caller portal), **Data City** (+ the Research hub), **Money** (My MFFU Accounts, payouts, Decide, taxes), **Kalshi**. Each tile opens its dashboard and has at most 2 short links. Everything else is one tap away under **More** (never the landing page: nothing remembers it). Under More, "All apps in ..." opens each arena's page `hub/arena.html?a=<arena>`: every live app grouped by job, so ...
The arenas, the retired list and the fact owners are DATA in `tools/web_public/olympus/gate-catalog.js` (ARENAS, REPLACE, FACTS). **This file is generated: `python tools/olympus_map_build.py` (do not edit by hand; `tests.test_olympus_map` fails when it is stale).** The link crawler and the nav checks: `tests.test_olympus_nav`.
Data: apps only read published JSON (and bundled `fixture.json` / demo fallbacks). No app places orders. Look: OLYMPUS NIGHT (`docs/DESIGN_AGORA.md`).

## Doors

- [[Apps NQ Bot|NQ Bot]]: 31 apps
- [[Apps Jarvis|Jarvis]]: 9 apps
- [[Apps Websites|Websites]]: 1 apps
- [[Apps Data City|Data City]]: 13 apps
- [[Apps Money|Money]]: 18 apps
- [[Apps Kalshi|Kalshi]]: 5 apps
- [[Apps Everything else|Everything else]]: 3 apps

## Where the organizing code lives

| Piece | File | Test |
|---|---|---|
| The arenas, retired -> replacement, one place per fact, every app's plain name and hub | `tools/web_public/olympus/gate-catalog.js` (ARENAS, REPLACE, FACTS, R) | `tests.test_olympus_nav`, `tests.test_gate_page`, `tests.test_hubs` |
| The breadcrumb Home > arena > app, Go to, the retired redirect, the Main copy chips | `tools/web_public/olympus/gate-nav.js` (loaded by `agora-ui.js`, `a11y.js` or the page) | `tests.test_olympus_nav` |
| The arena pages | `tools/web_public/hub/arena.html` + `arena.js` + `arena.css` | `tests.test_olympus_nav` |
| Home: the 6 arenas, Everything else, the All apps row | `tools/web_public/gate/index.html`, `gate/arenas.js`, `gate/gate.js` | `tests.test_gate_page` |
| The hubs (an older grouping; their tabs still show in search) | `tools/web_public/hub/` | `tests.test_hubs` |
| App registry (Jarvis switcher, launcher) | `tools/web_public/jarvis/apps.js` -> `olympus/apps-list.js` | `tests.test_apps_list` |
| The four doors (2026-11-18; hidden on Home since the arenas, kept for old links) | `tools/web_public/olympus/doors.js`, `hub/doors.html` | `tests.test_apps_list` (part d) |
| This map | `tools/olympus_map_build.py` -> `docs/OLYMPUS_MAP.md` | `tests.test_olympus_map` |

Back to [[ZEUS Home]]
