# PERF + OFFLINE asks to the other teams (ranked, biggest win first)

Measured with `python -X utf8 tools/perf_sweep.py --pages <app>` (phone: 390 px, CPU x4, Fast 3G, cold). Numbers: BASELINE.md.
Re-check after a change: `python -X utf8 tools/perf_sweep.py --pages <app> --check` (budgets: tools/perf_budgets.json; lower your app's
own line when you beat it). Shift sources per app: baseline.json "shifts".

## DESIGN (day-arenas): olympus/ kit + the money / main apps

1. **Reserve the header before agora-ui.js fills it** (every Agora app, CLS +0.06 at ~2.9 s): the back button `a.ag-navback` and the
   `div.ag-appbar` are inserted after load and push every card down ~50 px. Put `header.top{min-height:<filled height>}` (and the
   app-bar's space: `body{padding-top:...}` or a static placeholder `<div class="ag-appbar" aria-hidden="true"></div>`) in agora.css,
   so the script only fills reserved space.
2. **Reserve each data card's height** (CLS 0.3-0.95, the worst on the site): agency 0.95 (`#today` list rows `.lrow` arrive at 3.8 s),
   demeter 0.85 (`#dialCard`), kronos 0.83 (`#heroTiles` tiles at 5.6 s), chrysos 0.76 (`.pu-money` part), inbox 0.71 (`#mutes` and the
   `#hero .acts`), clio 0.71, compass 0.46 (cards at 7.8 s), aegis 0.36, planner 0.29 (`#qForm` / `section.pulse`), hera 0.24,
   pnyx 0.21, oikos 0.20, journal 0.20. Fix: `min-height` on the container = its filled height at 390 px (or a skeleton row of the
   same height), never insert a block above content that is already on screen.
3. **three.js for a decorative 3D header on text apps** (+163 KB gz / 654 KB parse, long tasks 0.3-1.4 s): ledger (ledgerscene.js,
   long task 1.3 s), helios (sun.js), aegis, chrysos, mercury (54 long tasks), oikos, compass, kronos (90 long tasks, 1.4 s),
   tyche (3.3 s). Load it through `olympus/lazy3d.js` (ledger / mercury / oikos / compass / kronos / tyche import it directly) and
   make lazy3d wait for `load` + `requestIdleCallback` (2 s timeout) and skip when `navigator.connection.saveData` or effectiveType
   is `2g`/`3g` or `deviceMemory <= 4` (the CSS backdrop stays). Expected: -163 KB and the long tasks gone on a phone.
4. **sfx.js (103 KB) is parser-loaded by 21 index.html files** although `olympus.js` already loads it on the first sound / ambience
   (`OLY.sfx`, a tap): drop the direct `<script src="../olympus/sfx.js...">` tags (or mark them `defer`): -31 KB gz on every open.
5. **themes.js (74 KB) is render-blocking on 24 pages**: split a tiny inline token boot (the colours the first paint needs) and load
   the rest with `defer`.
6. **Heavy data on open:** journal, kronos, compass fetch `odeon/trades.json` (477 KB, 128 KB gz) for a few numbers: read
   `trading/trades.json` (16 KB) or a slim summary; fates fetches `fates/fates.json` (772 KB, 171 KB gz, largest paint 9.5 s,
   long task 1.8 s): split per account / load the open account first.
7. **Register the root worker from the kit** (olympus.js, LEAD_WIRES 2): apps opened from a direct link get offline too.

## DATA TRUTH (day-nqdash3): nq/, trading/, board/

1. **nq first open 947 KB**: the optional 3D columns (nqscene.js via lazy3d) pull three.js 163 KB + `assets/tex/paving_c.webp`
   165 KB + `assets/env/hdri/dusk.hdr` 128 KB on open: add `data-near="#scene3d"` (only when scrolled near) and the saveData / 3G
   skip above; use the `_l.webp` LITE texture and no HDR on a phone. Largest paint 6.5 s, long task 0.8 s.
2. **nq CLS 0.58**: `#chartBox` and `#acctCard` resize when the chart and accounts arrive (0.38 at 6.4 s, 0.11 at 3.8 s): fixed
   `height` on `.chartbox` (e.g. 220 px at 390) and a min-height on `#acctCard`.
3. **board CLS 0.66**: `section.notebox` grows above `#edgeChip` / `#payReadyCard` at 5.6 s: reserve the notebox height or put it below.
4. **trading largest paint 5.8 s**: the table renders after all of trades.json: paint the first 20 rows first.
5. Offline age: nq shows its age offline (good); trading and board must show "as of <time>" from their data when offline.

## JARVIS: jarvis/

1. **1.6 MB on first open, 2.75 MB JS parsed, 58 long tasks up to 2.0 s, TBT 5.9 s, heap 19 MB** (the heaviest page): import the brain
   / skills / search modules on first use (the first question or tap), not at boot.
2. `odeon/trades.json` (128 KB gz) is fetched **twice** on open: one shared promise (or `trading/trades.json`).
3. three.js + the core visual start before the first answer is possible: start the orb after `load` + idle.

## HOME + CITIES (day-cities3): gate/, cities/, datacity/, widget/

1. **cities (world) long task 4.1 s, TBT 8.0 s** after the first paint: build the city in chunks (`requestIdleCallback` /
   `scheduler.yield()` per district) and show the poster.jpg until the first frame.
2. gate: fine (134 KB, CLS 0, long task 77 ms). widget: fine (15 KB).
3. Offline: gate and cities need LEAD_WIRES 1 (cities: also cache world.json + poster.jpg on first visit, the patch does it).

## KALSHI: kalshi/, dionysus/

1. **dionysus CLS 0.90**: its cards (`#app > section.ag-card`) fill at 4.6 s and push each other: reserve card heights (as DESIGN 2).
2. kalshi: good (179 KB, offline ok with age). CLS 0.23 from the header: DESIGN 1 fixes it.

## NAV (day-manual): hub/, warp, gate-catalog, search

1. `gate-nav.js` inserts the breadcrumbs `nav.gn-crumbs` into the header ~3.5 s after load (part of every app's header shift):
   render the crumb slot in the page or reserve its height in its CSS.
2. hub: good (116 KB, CLS 0.04, no long task).

## A11Y / ARCHIVE

No perf asks (archived apps are not opened by the Doors; not measured).
