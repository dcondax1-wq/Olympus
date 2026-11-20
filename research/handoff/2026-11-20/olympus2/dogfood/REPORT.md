# Dogfood: Olympus through its own audit (day-quality, 2026-11-20 evening)

## 1. The live site, as a customer's phone sees it (tools/site_audit.py, https://dcondax1-wq.github.io, 390 x 844, CPU x4, slow 4G)

| App | Grade | Main content | Layout jumps | Accessibility |
|---|---|---:|---:|---:|
| Zenith (home of the dashboard) | D | 10.8 s | **1.08** | 94 |
| NQ | D | 7.4 s | 0.00 | 100 |
| Planner | D | 6.3 s | 0.00 | 100 |
| Gate | C | 5.4 s | 0.07 | 100 |
| Business | C | 5.2 s | 0.03 | 100 |
| Trading | C | 5.1 s | 0.00 | 100 |
| Agency | B | 3.8 s | 0.00 | 100 |
| Board | B | 3.2 s | 0.06 | 100 |
| Kalshi | B | 3.0 s | 0.09 | 100 |
| Cities | A | 2.5 s | 0.02 | 100 |
| Jarvis | A | 2.0 s | 0.04 | 100 |

Screenshots: live-<app>.png in this folder. (Offline after one visit: ok on all of them since sw-offline landed.)

## 2. Fixed tonight (files nobody else owns tonight), measured before -> after (perf_sweep, same phone line, back to back)

| App | KB on first open | Largest paint | Blocking time | Layout shift | What changed |
|---|---|---|---|---|---|
| Compass | 602 -> **481** | 7.9 -> **7.1 s** | 258 -> 165 ms | 0 | reads `odeon/trades_lite.json` (7 KB gz) instead of the 489 KB (131 KB gz) `odeon/trades.json` |
| Mnemosyne (journal) | 356 -> **234** | 5.0 -> **4.4 s** | 70 -> 61 ms | 0 | same (journal.js + the edge page edge.js) |
| Kronos | 660 -> **538** | 8.1 -> **7.8 s** | 6.2 -> **4.8 s** | 0 | same |
| NQ | 352 -> 352 | 5.2 -> **4.8 s** | 306 -> 303 ms | 0.022 -> 0.002 | sfx.js no longer fetched during the first paint |
| Trading | 356 -> 356 | 4.8 -> 4.6 s | 313 -> 144 ms | 0.001 | (kit change) |
| Business / Planner | = | -0.1 s | = | = | (kit change) |
| Zenith | = | = | = | 0.31 -> 0.31 (repo tree) | the data.json redraw of Home is skipped when it is the same build as home.json (live: the jump at ~16 s) |

1. **Slim trades file:** `tools/odeon_export.py` now writes `odeon/trades_lite.json` next to `trades.json` every time (the same trades minus
   their chart data `bars / events / levels`; Odeon's theater keeps the full file). Compass, Mnemosyne (+ its edge page) and Kronos read
   the slim one first and fall back to the full one. 131 KB -> 7 KB over the wire on each of those first opens.
2. **sfx.js off the first paint:** 41 pages carried their own `<script src="../olympus/sfx.js" defer>` (31 KB gz, downloaded while the page
   paints, for a sound engine that is silent until the first tap). Removed; the kit (olympus.js) now loads it after `load` at idle (2 s cap)
   on every kit page, so cues and beds work as before and the first tap still unlocks audio. Kept on the pages whose own code calls the
   engine directly (cities, settings, symposium, ergasterion, kalshicity, jarvis) and on agency/ (being built tonight).
3. **Zenith Home redraw:** when data.json lands (16 s on a phone line) and Home was already drawn from home.json OF THE SAME BUILD, the
   full animated redraw is skipped (every Home part reads `D || HOMEJ`). A newer build, another page, live.json and the minute refresh
   still redraw.

Tests: every changed app's page suite re-run (aegis ... stoa, journal_edge, olympus_kit, odeon); the reds that remain are pre-existing,
listed below. The shared test kit learned the slim file (an override of `/odeon/trades.json` is mirrored to `trades_lite.json`).

## 3. Not fixed (with the cause and the exact way)

- **Zenith Home still jumps (~1.0 live):** measured: Home draws from home.json at 5.3 s, then a dozen add-ons insert cards 8.9-10.5 s
  (zenith_hero.js `section.zh-hero` before `su-sun`, olympus/zeus_core.js `#zeusCardBox` at the TOP at 10.4 s, polish `pl-home`, more.js
  `#moStrip`, `#znNq`, `#mnCard`, `#sdCard`). Hiding Home until they settle was tried and dropped: +5 s of skeleton on a phone. The fix is
  slots: Home's first draw (hub.js VIEWS.today) renders empty placeholders with the final min-height for each late card
  (`<div id="zeusSlot" style="min-height:240px">`, a hero slot ~155 px, the strip 119 px), and each add-on fills its slot instead of
  inserting before existing cards. Owner of those files: DESIGN / lead.
- **themes.js render-blocking (24 pages):** it is synchronous on purpose (paints the chosen look before the first frame); deferring it needs
  the tested FIRST-PAINT inline snippet per page (tests/test_olympus_themes.py checks it letter for letter). Not done tonight.
- **live.js polls a repo that does not exist** on the live site (`dcondax1-wq/nq-dashboard` live.json every 45 s, 2 x 404): on the
  github.io user site skip the GitHub poll (the PC's numbers come from the ntfy feed already). DATA's file.
- Planner 6.3 s / NQ 7.4 s live main content: their largest element is drawn after their data fetch; reserve + draw from the cached copy.

## 4. Pre-existing reds seen while re-testing (not touched)

pheme_page (stats.json stale: `python tools/pheme_build.py`), pythia_page (events.json stale: `python tools/money/pythia_dates.py`),
polis_page (the night-sky check at a fixed time), herald_page (the dated real edition), dionysus / hera (c: corner / sideways check),
odeon_page (a github.io address in the page), olympus_kit (3 Oracle checks), cold_calls (d: corner / sideways): each re-run on the code
BEFORE tonight's change too, with the identical failure, so none is from this change. Every suite of a changed app is green otherwise
(aegis ... stoa, compass 57/57, journal 86/86, kronos 54/54, journal_edge 42/42, agency 118/118, smoke 10/10).
