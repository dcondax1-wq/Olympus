# Wiring the six new AGORA apps (2026-11-09)

Apps: `hestia`, `demeter`, `apollo`, `hera`, `dionysus`, `clio` in `tools/web_public/<id>/`. Each is finished and tested on its own (`tests/test_<id>_page.py`, shared helper `tests/agora_kit.py`).
The agent did NOT touch `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`, the `olympus.js` APPS table, `intro-app.js` or `transitions.js`. The lead pastes the lines below (checklist order of CLAUDE_REFERENCE "Wiring checklist for a new app").

Dependency: the pages link `../olympus/agora.css?v=a1` and `data-theme="agora"`. `olympus/agora.css` and `docs/DESIGN_AGORA.md` come from commit a8cab8e (cherry-picked into this worktree unchanged), so merging both branches is clean.
The kit pin used is `?v=o3` (what `tests/test_olympus_kit.py` requires today; the brief said o2).

## 1. `jarvis/apps.js` BUILT_INS (after the `ledger` row; colours must equal the APPS rows below)
```js
  app('hestia', 'Hestia', 'trading', '#c8a24a', 'Today at home: what to do right now', { glyph: 'Η' }),
  app('demeter', 'Demeter', 'trading', '#9aa564', 'Account health: drawdown dials, payout rules', { glyph: 'Δ' }),
  app('apollo', 'Apollo', 'trading', '#e0b060', 'Your weekly review and the one rule for next week', { glyph: 'Α' }),
  app('hera', 'Hera', 'money', '#c96a4a', 'The 12-month money plan, payouts, what to buy next', { glyph: 'Ω' }),
  app('dionysus', 'Dionysus', 'money', '#b77a8a', 'The Kalshi desk: guard, what-if, scan. Suggestions only', { glyph: 'Σ' }),
  app('clio', 'Clio', 'trading', '#d8c9a8', 'The research library: every study in plain words', { glyph: 'Κ' }),
```
(purposes are 5-79 characters). The jarvis status overlay needs nothing: each folder has its static `jarvis.json`.

## 2. `olympus/olympus.js`
APPS table (name, glyph, colour equal the apps.js rows):
```js
hestia: ['Hestia', 'Η', '#c8a24a'], demeter: ['Demeter', 'Δ', '#9aa564'], apollo: ['Apollo', 'Α', '#e0b060'], hera: ['Hera', 'Ω', '#c96a4a'], dionysus: ['Dionysus', 'Σ', '#b77a8a'], clio: ['Clio', 'Κ', '#d8c9a8'],
```
AMBIENT (existing beds only):
```js
hestia: 'smithy', demeter: 'breeze', apollo: 'chimes', hera: 'coins', dionysus: 'sea', clio: 'scroll',
```

## 3. `tools/build_web_dashboard.py` app tuple (~line 1212)
Add after `"atlas"`: `"hestia", "demeter", "apollo", "hera", "dionysus", "clio"`.
Optional, makes Clio read a small file instead of the 4 MB data.json: after `_docs(...)` writes the write-ups, also write `<out>/writeups/index.json` = `{"writeups": [{k: d[k] for k in ("slug","title","family","date","status","summary","runs","words")} for d in docs["writeups"]]}` (about 60 KB). Clio already falls back to `docs.writeups` inside data.json, then to its demo.

## 4. Root `tools/web_public/sw.js`
`OTHER_APPS`: add `'hestia/', 'demeter/', 'apollo/', 'hera/', 'dionysus/', 'clio/'` and bump `CACHE` (`le-public-v61` today). Update the pinned strings in `tests/test_zenith_mode.py` (~66), `tests/test_jarvis_hub.py` (~273), `tests/test_zenith_shell.py`, `tests/test_phone_e2e.py` (~1090: every app folder must be in OTHER_APPS).

## 5. Rebuild the list
`python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.

## 6. Shared lines
`olympus/intro-app.js` FLAVOUR (scenes that exist):
```js
hestia: ['embers', 'Warm the hearth', 'tick'], demeter: ['leaves', 'Know your ground', 'tick'], apollo: ['rings', 'The week, in light', 'tick'],
hera: ['columns', 'Plan the year', 'tap'], dionysus: ['coins', 'Odds, with a cool head', 'tap'], clio: ['smoke', 'Every study, remembered', 'tick'],
```
`jarvis/transitions.js` REGISTRY (kinds that exist):
```js
  hestia:     { kind: 'forge',    ms: 960 },
  demeter:    { kind: 'laurel',   ms: 1000 },
  apollo:     { kind: 'sunburst', ms: 1000 },
  hera:       { kind: 'columns',  ms: 1000, n: 7 },
  dionysus:   { kind: 'waves',    ms: 1000 },
  clio:       { kind: 'tiles',    ms: 800 },
```
The intro script tag and the a11y tags are already in each `index.html` (checked by the page tests).

## 7. Tests to run after wiring
`tests.test_<id>_page` for the six, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, `tests.test_zenith_mode`, `tests.test_jarvis_hub`, then `python -X utf8 tests/run_gate.py --fast`.
Then update CLAUDE_REFERENCE "OLYMPUS apps and tools" (36 apps) and the one OLYMPUS paragraph in CLAUDE.md.

## What each app reads (all published, read only)
| app | files | fallback |
|---|---|---|
| hestia | `../home.json`, `../odeon/trades.json` | `fixture.json` (DEMO) |
| demeter | `../home.json`, `../ledger/rules.json`, `../plutus/roadmap.json` | built-in MFFU limits (a test keeps them equal to `research/lit/mffu_rules.json`), `fixture.json` |
| apollo | `../odeon/trades.json`, localStorage `journal.card.v1` (read only) | `fixture.json` |
| hera | `../plutus/roadmap.json` | `fixture.json` (saved copy; a test fails when it goes stale) |
| dionysus | the public `kalshi-feed` raw `kalshi.json` (same as the Kalshi page), `../kalshicity/edges.json`, `../kalshicity/whatif.json` | the site's copy of the book, then `fixture.json` |
| clio | `../writeups/index.json` (optional, see 3), `../data.json` (docs list), `../writeups/<slug>.md` on tap | `fixture.json` |

---
# Wiring the two money pages DELPHI and PNYX (2026-11-10)

Apps: `delphi` (the oracle's briefing, reads `../home.json` live.brief + `../ledger/rules.json`) and `pnyx` (the assembly, MFFU rules / risk calculator, reads `../home.json` + `../ledger/rules.json`) in `tools/web_public/<id>/`. Tests `tests/test_delphi_page.py`, `tests/test_pnyx_page.py`. Same kit pins as the six above (`olympus.js?v=o4`, `agora.css?v=a1`, `intro-app.js?v=i5`). Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

## 1. `jarvis/apps.js` BUILT_INS (after the `clio` row; colours equal the APPS rows)
```js
  app('delphi', 'Delphi', 'trading', '#e0b060', 'The oracle\'s briefing: plan, target, go / no-go', { glyph: 'Φ' }),
  app('pnyx', 'Pnyx', 'money', '#c8a24a', 'Prop-firm rules and risk calculator: stop to micros', { glyph: 'Π' }),
```
## 2. `olympus/olympus.js`
APPS: `delphi: ['Delphi', 'Φ', '#e0b060'], pnyx: ['Pnyx', 'Π', '#c8a24a'],`
AMBIENT (existing beds): `delphi: 'chimes', pnyx: 'coins',`
## 3. `tools/build_web_dashboard.py` app tuple (~line 1212): add `"delphi", "pnyx"` after the AGORA six.
## 4. `tools/web_public/sw.js`: `OTHER_APPS` add `'delphi/', 'pnyx/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
## 5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
## 6. Shared lines
`olympus/intro-app.js` FLAVOUR: `delphi: ['rings', 'Read the omens', 'tick'], pnyx: ['columns', 'Count the risk', 'tap'],`
`jarvis/transitions.js` REGISTRY: `delphi: { kind: 'sunburst', ms: 1000 }, pnyx: { kind: 'columns', ms: 1000, n: 5 },`
## 7. Tests after wiring: `tests.test_delphi_page`, `tests.test_pnyx_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, then `python -X utf8 tests/run_gate.py --fast`. Then app count 38 in CLAUDE_REFERENCE / CLAUDE.md.

---
# Wiring MERCURY, money machine #2 DEALS (2026-11-10)

App `mercury` (`tools/web_public/mercury/`, reads `../money/mercury.json`, falls back to its `fixture.json` = DEMO) + scanner `tools/money/mercury.py` (`--out DIR`, `--fixture`, `--selftest`; writes `DIR/mercury.json` and `DIR/mercury_state.json`). Test `tests/test_mercury_page.py`.
1. `jarvis/apps.js` BUILT_INS: `app('mercury', 'Mercury', 'money', '#c8a24a', 'Deal watcher: sales, codes, free resets, rule changes', { glyph: '☿' }),`
2. `olympus/olympus.js` APPS: `mercury: ['Mercury', '☿', '#c8a24a'],` AMBIENT: `mercury: 'coins',`
3. `tools/build_web_dashboard.py` app tuple: add `"mercury"`; to publish the scanner file, run `python tools/money/mercury.py --out <site>/money` in the cloud monitor / build step (no secrets, public pages only; one GET per page, at most every 30 min; the state file `mercury_state.json` must be kept between runs or every deal shows "new").
4. `sw.js` OTHER_APPS: add `'mercury/'`, bump `CACHE`; update the pinned strings in `test_zenith_mode`, `test_jarvis_hub`, `test_zenith_shell`, `test_phone_e2e`.
5. `python tools/apps_list_build.py` then `--check`.
6. `intro-app.js` FLAVOUR: `mercury: ['coins', 'Find the saving', 'tap'],` `transitions.js` REGISTRY: `mercury: { kind: 'tiles', ms: 800 },`
7. Tests: `tests.test_mercury_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

# Wiring MINT, the money machine hub (2026-11-10)

App `mint` in `tools/web_public/mint/` (reads `../money/index.json`, falls back to `fixture.json`). Engine `tools/money_engine.py` (writes `money_out/<id>.json` + `index.json`), runner `RUN_MONEY.bat`, workflow `.github/workflows/money-engine.yml` (schedule / dispatch only, artifact `money-out`). Tests `tests/test_mint_page.py`, `tests/test_money_engine.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('mint', 'Mint', 'money', '#c8a24a', 'The money machine: five streams, one honest estimate', { glyph: 'M' }),`
2. `olympus/olympus.js` APPS: `mint: ['Mint', 'M', '#c8a24a'],` AMBIENT: `mint: 'coins',`
3. `tools/build_web_dashboard.py` app tuple: add `"mint"`; the site build must also copy `money_out/*.json` (or the published money JSON) to `money/` so `../money/index.json` exists (until then the page shows its DEMO fixture).
4. `sw.js` OTHER_APPS add `'mint/'`, bump `CACHE`, update the pinned strings in the zenith / hub tests.
5. `python tools/apps_list_build.py` then `--check`.
6. `intro-app.js` FLAVOUR: `mint: ['columns', 'Strike the coin', 'tap'],` ; `transitions.js` REGISTRY: `mint: { kind: 'columns', ms: 1000, n: 5 },`
7. Tests: `tests.test_mint_page`, `tests.test_money_engine`, plus the shared list in section 7 above.
Scanners to land in `tools/money/<id>.py` (chrysos, mercury, sibyl, oikos, arbiter): `--out DIR`, `--fixture`, `--selftest`; the engine skips missing ones and uses `tools/money/fixtures/<id>.json`.

# Wiring ARBITER (money machine #5, 2026-11-10)

App `arbiter` (`tools/web_public/arbiter/`, paper-only spread / funding finder) reads `../money/arbiter.json` (written by `python tools/money/arbiter.py --out <site>/money`, stdlib, `--fixture` offline, `--selftest`), falls back to its own `fixture.json` (regenerate: `python tools/money/arbiter.py --fixture --out tools/web_public/arbiter && mv tools/web_public/arbiter/arbiter.json tools/web_public/arbiter/fixture.json`). Test `tests/test_arbiter_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('arbiter', 'Arbiter', 'money', '#c8a24a', 'Paper-only spreads and funding: net yearly return after costs', { glyph: 'Ξ' }),`
2. `olympus/olympus.js` APPS: `arbiter: ['Arbiter', 'Ξ', '#c8a24a'],` AMBIENT: `arbiter: 'coins',`
3. `tools/build_web_dashboard.py` app tuple: add `"arbiter"`; also publish `money/arbiter.json` (run the scanner with `--out <site>/money`, soft-fail to nothing).
4. `sw.js` OTHER_APPS: `'arbiter/'`, bump `CACHE`; update pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`.
6. `olympus/intro-app.js` FLAVOUR: `arbiter: ['coins', 'Weigh the spread', 'tap'],` `jarvis/transitions.js` REGISTRY: `arbiter: { kind: 'tiles', ms: 800 },`
7. Tests: `tests.test_arbiter_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_app_intro`, `tests.test_jarvis_transitions`.

# Wiring CHRYSOS (money machine #1, 2026-11-10)

App `chrysos` in `tools/web_public/chrysos/` (3D tower via the render core: `tower.js` + `towerload.js`), data tool `tools/money/chrysos.py` (`--out <dir>`, `--fixture`, `--selftest`; writes `<dir>/chrysos.json`). Page reads `../money/chrysos.json`, falls back to `fixture.json` (equals `chrysos.py --fixture`, a test keeps it fresh). Test `tests/test_chrysos_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('chrysos', 'Chrysos', 'money', '#c8a24a', 'Prop-firm fleet planner: fees against payouts, break-even (estimate)', { glyph: 'X' }),`
2. `olympus/olympus.js` APPS: `chrysos: ['Chrysos', 'X', '#c8a24a'],` AMBIENT: `chrysos: 'coins',`
3. `tools/build_web_dashboard.py` app tuple: add `"chrysos"`; and in the publish step run `python tools/money/chrysos.py --out <site>/money` (writes `money/chrysos.json`); add `chrysos.py` output to the site copy list.
4. `sw.js` OTHER_APPS: `'chrysos/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`.
6. `olympus/intro-app.js` FLAVOUR: `chrysos: ['coins', 'Count the gold', 'tap'],` and `jarvis/transitions.js` REGISTRY: `chrysos: { kind: 'columns', ms: 1000, n: 4 },`
7. Tests: `tests.test_chrysos_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

# SIBYL: money machine #3, the prediction-market edge scanner (2026-11-10)

App `sibyl` (`tools/web_public/sibyl/`, 3D marble ball in `sibylball.js`, its own module tag) + scanner `tools/money/sibyl.py` (stdlib, `--out <dir>`, `--fixture`, `--selftest`; writes `<dir>/sibyl.json`). Tests `tests/test_sibyl_page.py` (+ `python tools/money/sibyl.py --selftest`). Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`, the Kalshi bot, `engine/`.

## 1. `jarvis/apps.js` BUILT_INS: `app('sibyl', 'Sibyl', 'money', '#c8a24a', 'Prediction-market edges after fees: paper picks, ruin odds, what could go wrong', { glyph: 'Σ' }),`
## 2. `olympus/olympus.js`: APPS `sibyl: ['Sibyl', 'Σ', '#c8a24a'],` and AMBIENT `sibyl: 'chimes',`
## 3. `tools/build_web_dashboard.py` app tuple (~line 1212): add `"sibyl"`. The page reads `../money/sibyl.json`: have the build run `python tools/money/sibyl.py --out <site>/money` (cloud monitor / build step); without that file the page shows its labelled DEMO.
## 4. `tools/web_public/sw.js`: `OTHER_APPS` add `'sibyl/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
## 5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
## 6. Shared lines
`olympus/intro-app.js` FLAVOUR: `sibyl: ['rings', 'Read the odds', 'tick'],`
`jarvis/transitions.js` REGISTRY: `sibyl: { kind: 'sunburst', ms: 1000 },`
## 7. Tests after wiring: `tests.test_sibyl_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, then `python -X utf8 tests/run_gate.py --fast`.
Reads (all published, read only): `../money/sibyl.json` (the scanner's file); fallback `fixture.json` (DEMO, exactly `sibyl.py --fixture`). The scanner reads `kalshicity/edges.json`, `whatif.json`, `forward.json` (when present) and never the network.
