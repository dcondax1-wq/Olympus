# Olympus organization audit + the clean structure (day-a11y, 2026-11-21)

Owner: "more organized". Base `olympus/pc` 7adf312d. Map: `docs/OLYMPUS_MAP.md` (generated). Tests: `tests.test_olympus_nav` (22 checks).

## What I found

| # | Problem | Evidence | Fixed now? |
|---|---|---|---|
| 1 | **Five ways to sort the same apps.** The 4 Doors (`olympus/doors.js`, hidden on Home but still in `hub/doors.html` and Atlas), the 9 hubs (`gate-catalog.js`, the hub pages, "Go to"), the 6 arenas + Everything else (Home), the Jarvis switcher's TRADING / LIFE / MONEY / MORE (`jarvis/apps.js`), and Atlas's old districts. The breadcrumb said "Bots & Evals" while Home said "NQ Bot". | `gate/index.html`, `gate-catalog.js` HUBS, `jarvis/apps.js` GROUPS, `atlas/atlas.js` zones | **Yes, for the pages:** the arenas are the one top level (data in `gate-catalog.js` ARENAS). Every page's breadcrumb reads Home > arena > app. **The switcher's groups: LEAD_WIRES #1.** Doors, Atlas and hubs stay reachable (old links work) but nothing points the owner to them first. |
| 2 | **83 of 142 pages had no way back to Home** (only AGORA-shell pages got the breadcrumb). Examples: Board, Ares, Fates, Odeon, Why, Widget, PC, Help, the hub help pages, every lab. | crawl of every `.html` for `gate-nav.js` / `agora-ui.js` | **Yes:** `a11y.js` (on nearly every page) loads `gate-nav.js` when the page has neither. 27 pages with no kit got the tag directly. Now 0 Olympus pages lack it. The public client pages (agency demos, audits, showcase, factory, caller portal, concept sites) never get it. |
| 3 | **The Home link could not be tapped on Fates:** its overlay has `pointer-events: none`, and the full-screen 3D canvas took the tap. | browser test: canvas intercepts the click | **Yes:** the breadcrumb row is `pointer-events: auto; z-index: 40` (gate-nav.js). |
| 4 | **28 retired apps still opened their old page,** reachable from old links and bookmarks: dead ends that look current. | `gate-catalog.js` RETIRED | **Yes:** each opens its replacement (`?from=<old>`). Before, day-archive's strip (`tools/archive_banners.py`) only *linked* to the live app. `?stay=1` keeps the old page, frames are never redirected (Cities embeds some), nothing is deleted. Table in the map. |
| 5 | **The same fact in many places, sometimes worded differently.** Accounts / drawdown left: NQ, Board, Aegis, Demeter, Widget, Trading, Zenith, Ledger, Hera, Fates, the Home "Right now". Payout: Business (18 files), NQ, Board, Widget, Trading, Hera, Demeter, Ledger, Chrysos. 7-day clocks: Business, NQ, Board, Aegis. | grep of the page code | **Linked:** the one place is **My MFFU Accounts** (`business/mffu.html`); Ledger keeps the real cash. Each page that repeats one shows a "Main copy" chip to it. The pages keep their numbers; merging them is per-team work (see "Next"). |
| 6 | **Greek names the owner won't know:** Aegis, Pnyx, Moirai, Labyrinth, Kratos, Nemesis, Pythia, Clio, Pinakes, Ergasterion... | page titles | **Partly:** the breadcrumb, the arena pages and the map use the plain names ("Risk guard", "Pass odds", "Losing trades"). The pages' own titles are still Greek (LEAD_WIRES #4 proposes the swap). |
| 7 | **Orphan pages** (no link from any reachable page): `agency/call.html`, `agency/factory/index.html`, `agency/outreach/index.html`, `agency/portal/index.html`, `datacity/jarvis/index.html`, `fx/dev.html`, `fx/space.html`, `hub/setup.html`, `jarvis/core-demo.html`, `jarvis/shortcuts.html`, `olympus/a11y-demo.html`, `olympus/brain3d-lab.html`, `olympus/dashfx-lab.html`, `olympus/kit.html`, `olympus/nqfx-lab.html`, `olympus/shapes-demo.html` | crawl | **Reported.** Labs and demos are fine as orphans (reached from Settings > Workshop or by URL). `agency/call.html` (the B2 call copilot) is superseded by the caller portal: retire it with a redirect (#5 below, the agency team's call). |
| 8 | **Broken links:** none in the repo. The only miss was `icons/` on the Zenith page, which `build_web_dashboard.py` copies at publish. | crawler | n/a (the crawler knows the published files) |
| 9 | **Live data with no "last updated":** Pnyx (the rules calculator reads the balances in home.json) and Clio. Every other page reading live feeds shows an age. | grep: pages reading home / data / live / pc_feed without age.js or an age word | **Reported** (the page teams: one `age.js` line). |
| 10 | **Two "front pages" for NQ:** the Zenith dashboard (`/`, "Full NQ dashboard") and NQ (`nq/`, "Bots right now"). | catalog | NQ is the arena's front (the Home tile). The dashboard is listed first under "Bots now" on the NQ arena page. |

## The structure now (as built)

- **Home:** the 6 arena tiles (unchanged) + Everything else + a new row "All apps in: NQ Bot · Kalshi · Business · Websites · Jarvis · Cities · Everything else" (in the Everything else card, so the 6 tiles still fit the first screen).
- **Arena page** `hub/arena.html?a=<arena>`: "Open <arena> (the front page)", then the arena's live apps grouped by job (plain name, one line, the Greek name small on the right), then the other arenas.
  - Counts: NQ Bot 30, Kalshi 4, Business 8, Websites 1, Jarvis 4, Cities 2, Everything else 11.
- **Every page:** "< Home › Arena › Plain name" + Go to. The Home link is always one tap. An arena's front page shows "Home › Arena".
- **Every app ≤ 2 taps from Home:** Home > arena page > app (or Home > the tile, for the 6 fronts).

## Tests
- `test_olympus_nav` 22/22 (new): crawler, structure (node), reachability, browser (crumbs, real taps, redirect, arena page, 390 px).
- `test_gate_page` 90/90: its crumb check now expects the arena.
- `test_olympus_map` 7/7: the column is Arena; the doc has the arenas, retired -> replacement and one place per fact.
- `test_delphi_page` 43/43: a retired page keeps working for its own test (automated browsers are never redirected).
- `test_hubs`: one failure, which fails on 7adf312d too (colour literals in gate.css from the night palette).
- `test_ares_page`: "every local file exists" fails on 7adf312d too (it wants the published `../home.json`).

## Next (not done today)
- One copy of the account cards: Board, Widget and NQ draw their own. They could all use `business/mffucenter.js` (the MFFU page's model), so the numbers can never disagree.
- "Go to" still lists the 9 hubs first. Swap to the 7 arenas (`gate-nav.js` openSheet + `tests.test_gate_page` part c "HUBS first").
