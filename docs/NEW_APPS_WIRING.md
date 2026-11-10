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

# Wiring OIKOS, money machine #4 (2026-11-10)

App `oikos` in `tools/web_public/oikos/` (the household: leaks, tax set-aside, buckets, reinvest-or-withdraw, 3D marble amphora). Scanner `tools/money/oikos.py` (`--out DIR`, `--fixture`, `--ledger X.json`, `--selftest`) writes `<DIR>/oikos.json`; the page reads `../money/oikos.json` (optional), `../ledger/rules.json` and its own `fixture.json`. Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('oikos', 'Oikos', 'money', '#c8a24a', 'The household: where money leaks, tax set-aside, buckets, reinvest or withdraw', { glyph: 'O' }),`
2. `olympus/olympus.js` APPS: `oikos: ['Oikos', 'O', '#c8a24a'],` AMBIENT: `oikos: 'coins',`
3. `tools/build_web_dashboard.py` app tuple: add `"oikos"`. The cloud monitor / dashboard build should copy `<out>/oikos.json` to the published `money/oikos.json` (e.g. `python tools/money/oikos.py --out <site>/money`); the page works without it.
4. `sw.js`: `OTHER_APPS` add `'oikos/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
6. `olympus/intro-app.js` FLAVOUR: `oikos: ['coins', 'Keep what you make', 'tap'],`
   `jarvis/transitions.js` REGISTRY: `oikos: { kind: 'waves', ms: 1000 },`
7. Tests: `python -X utf8 -m tests.test_oikos_page` (`--static` skips the browser), `python tools/money/oikos.py --selftest`, then `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

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

---
# Wiring STOA, the colonnade "what needs me now" (2026-11-10)

App `stoa` (`tools/web_public/stoa/`): reads `../home.json`, `../money/index.json`, the public `kalshi-feed` raw `kalshi.json` (same URL as Dionysus), `../alerts.json` (optional: `{"alerts":[{"text","level":"bad|warn"}]}`), falls back to `fixture.json` (DEMO). Done / Snooze in localStorage `stoa.state.v1`. Test `tests/test_stoa_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('stoa', 'Stoa', 'trading', '#c8a24a', 'The colonnade: what needs you right now', { glyph: 'Σ' }),`
2. `olympus/olympus.js` APPS: `stoa: ['Stoa', 'Σ', '#c8a24a'],` AMBIENT: `stoa: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"stoa"` (and `"mint"`); to publish the money files add the call `python tools/money_publish.py --site <site_dir>` after the site folder is built (copies `money_out/*.json` to `<site>/money/`, or a labelled sample when the engine has not run).
4. `sw.js` OTHER_APPS add `'stoa/'`, bump `CACHE`, update the pinned strings in the zenith / hub tests.
5. `python tools/apps_list_build.py` then `--check`.
6. `intro-app.js` FLAVOUR: `stoa: ['columns', 'Light the columns', 'tick'],` ; `transitions.js` REGISTRY: `stoa: { kind: 'columns', ms: 1000, n: 6 },`
7. Tests: `tests.test_stoa_page`, `tests.test_mint_page`, `tests.test_money_engine`, plus the shared list in section 7 above.

---
# Wiring LYCEUM, the school (2026-11-10)

App `lyceum` (`tools/web_public/lyceum/`): daily 5-question quiz on the owner's rules, XP + Greek ranks, review cards from Journal mistakes, 3 costliest habits ($ with R), weekly report card, 3D lecture hall (one column per rank). Reads `../odeon/trades.json`, `../home.json`, the Journal's `journal.v1` on the phone (READ ONLY), `fixture.json` (DEMO). Writes only its own `lyceum.v1` on the phone (never in the demo). Test `tests/test_lyceum_page.py`.
1. `jarvis/apps.js` BUILT_INS: `app('lyceum', 'Lyceum', 'life', '#c8a24a', 'The school: daily rules quiz, ranks, habits costing money', { glyph: 'Σ' }),`
2. `olympus/olympus.js` APPS: `lyceum: ['Lyceum', 'Σ', '#c8a24a'],` AMBIENT: `lyceum: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"lyceum"`.
4. `sw.js` OTHER_APPS: add `'lyceum/'`, bump `CACHE`; update the pinned strings in `test_zenith_mode`, `test_jarvis_hub`, `test_zenith_shell`, `test_phone_e2e`.
5. `python tools/apps_list_build.py` then `--check`.
6. `intro-app.js` FLAVOUR: `lyceum: ['columns', 'Learn your own rules', 'tap'],` `transitions.js` REGISTRY: `lyceum: { kind: 'columns', ms: 1000, n: 6 },`
7. Tests: `tests.test_lyceum_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

---
# Wiring NIKE, the trophy hall (2026-11-10)

App `nike` (`tools/web_public/nike/`) reads `../home.json` (accounts: `kind: funded` / `eval.passed` / `eval.progress` / `eval.to_target`, optional `passed_on`; `payouts[] {usd, date}` at the top or per account), `../ledger/rules.json` (target, payout rules), `../odeon/trades.json`, `../kalshicity/edges.json` (`book.total`, `book.days`) and the journal's ratings from this phone (`localStorage journal.v1`, read only); `fixture.json` is the labelled DEMO, used only when home.json is missing. Nothing unpublished is invented: a trophy without a real number is "Not yet". The 3D is four small meshes drawn on a 2D canvas (`nikescene.js`, no WebGL, `olympus/shapes3d.js` had not landed). Test `tests/test_nike_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

Data the lead may want to publish so the hall fills in: `payouts` (and `passed_on`) in `home.json`. Until then the payout trophies honestly say "No payout has been published".

1. `jarvis/apps.js` BUILT_INS: `app('nike', 'Nike', 'life', '#c8a24a', 'The trophy hall: milestones and wins from real numbers', { glyph: 'Ν' }),`
2. `olympus/olympus.js` APPS: `nike: ['Nike', 'Ν', '#c8a24a'],` AMBIENT: `nike: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"nike"`.
4. `sw.js` OTHER_APPS: `'nike/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`.
6. `olympus/intro-app.js` FLAVOUR: `nike: ['rings', 'Count your wins', 'tap'],` `jarvis/transitions.js` REGISTRY: `nike: { kind: 'sunburst', ms: 1000 },`
7. Tests: `tests.test_nike_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_app_intro`, `tests.test_jarvis_transitions`.

---
# Wiring AEGIS (the shield, risk guard, 2026-11-10)

App `aegis` in `tools/web_public/aegis/` (3D shield via the render core: `shield.js` + `shieldload.js`). Reads `../home.json` + `../ledger/rules.json`, falls back to `fixture.json` (DEMO). Warns only, never blocks an order. Test `tests/test_aegis_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('aegis', 'Aegis', 'trading', '#c8a24a', 'Risk guard: drawdown left, a full-stop what-if, when to stop for the day', { glyph: 'A' }),`
2. `olympus/olympus.js` APPS: `aegis: ['Aegis', 'A', '#c8a24a'],` AMBIENT: `aegis: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"aegis"` (no extra data file: it reads the published `home.json` and `ledger/rules.json`).
4. `sw.js` OTHER_APPS: `'aegis/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`.
6. `olympus/intro-app.js` FLAVOUR: `aegis: ['columns', 'Raise the shield', 'tap'],` and `jarvis/transitions.js` REGISTRY: `aegis: { kind: 'columns', ms: 1000, n: 3 },`
7. Tests: `tests.test_aegis_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

**Sibyl's own ledger (added 2026-11-10):** `tools/money/sibyl_ledger.py --sibyl <site>/money/sibyl.json --state <site>/money/sibyl_forward.json [--results results.json]` appends each day's picks once (frozen start day, only a fresh study, never back-filled), settles them from an optional results file and writes the summary into the same file. The cloud step must PERSIST `sibyl_forward.json` between runs (keep it on a state branch, like `forward_state.json`), or the start day restarts. The page reads `../money/sibyl_forward.json` (optional; without it the own-picks card says "Not started"). Net and win rate stay hidden until 30 bets are settled.

---
# KRONOS: the calendar of money (2026-11-10)

App `kronos` (`tools/web_public/kronos/`; the 3D marble sundial is `kronosdial.js`, its own module tag). Reads only `../odeon/trades.json` (real and paper trades; the backtest on a chip) and its `fixture.json` (DEMO, fixed today 2026-11-06). Test `tests/test_kronos_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

## 1. `jarvis/apps.js` BUILT_INS: `app('kronos', 'Kronos', 'money', '#c8a24a', 'The calendar of money: daily P&L, best weekday and hour, a normal bad week, a sundial', { glyph: 'K' }),`
## 2. `olympus/olympus.js`: APPS `kronos: ['Kronos', 'K', '#c8a24a'],` and AMBIENT `kronos: 'chimes',`
## 3. `tools/build_web_dashboard.py` app tuple (~line 1212): add `"kronos"` (it needs no new data file: `odeon/trades.json` is already published).
## 4. `tools/web_public/sw.js`: `OTHER_APPS` add `'kronos/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
## 5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
## 6. Shared lines
`olympus/intro-app.js` FLAVOUR: `kronos: ['rings', 'Read the shadow', 'tick'],`
`jarvis/transitions.js` REGISTRY: `kronos: { kind: 'sunburst', ms: 1000 },`
## 7. Tests after wiring: `tests.test_kronos_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, then `python -X utf8 tests/run_gate.py --fast`.

# Wiring MOIRAI, the three fates (2026-11-10)

App `moirai` in `tools/web_public/moirai/` (a seeded Monte-Carlo scenario lab for the MFFU Builder 50K eval; a simulation, not a forecast; marble spindle with three threads in 3D). Reads `fixture.json` (the bot's own 2026 numbers as defaults, never blank) and optionally `../ledger/rules.json`. Keeps only its sliders on the phone (`moirai.v1`). Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('moirai', 'Moirai', 'trading', '#c8a24a', 'The three fates: pass, bust and time of an eval, simulated', { glyph: 'M' }),`
2. `olympus/olympus.js` APPS: `moirai: ['Moirai', 'M', '#c8a24a'],` AMBIENT: `moirai: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"moirai"`.
4. `sw.js`: `OTHER_APPS` add `'moirai/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
6. `olympus/intro-app.js` FLAVOUR: `moirai: ['rings', 'Spin the threads', 'tick'],`
   `jarvis/transitions.js` REGISTRY: `moirai: { kind: 'waves', ms: 1000 },`
7. Tests: `python -X utf8 -m tests.test_moirai_page` (`--static` skips the browser), then `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

# Wiring EPILOGUE, the Sunday review "Oracle of Weeks" (2026-11-10)

App `epilogue` (`tools/web_public/epilogue/`): your week in 60 seconds: P&L in $ with R per account (50K, ATLAS, BLITZ), best / worst trade with the rule followed or broken, drawdown used / left, money-machine highlights, 3 lessons, one goal to tick, a Copy-the-summary button (clipboard only, no network), past weeks, a 3D marble scroll with a gold day timeline. Reads `../home.json`, `../odeon/trades.json` (paper + real only, backtests left out), `../money/index.json` (optional), the Journal's `journal.v1` on the phone (READ ONLY), `fixture.json` (DEMO). Writes only its own `epilogue.v1` on the phone (never in the demo). `?week=YYYY-MM-DD` shows another week. Test `tests/test_epilogue_page.py`.
1. `jarvis/apps.js` BUILT_INS: `app('epilogue', 'Epilogue', 'life', '#c8a24a', 'Your week in 60 seconds: the Sunday review', { glyph: 'Ω' }),`
2. `olympus/olympus.js` APPS: `epilogue: ['Epilogue', 'Ω', '#c8a24a'],` AMBIENT: `epilogue: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"epilogue"`. It also needs `money/index.json` published next to `home.json` to show the money machines; without it the card says "No money-machine report yet".
4. `sw.js` OTHER_APPS: add `'epilogue/'`, bump `CACHE`; update the pinned strings in `test_zenith_mode`, `test_jarvis_hub`, `test_zenith_shell`, `test_phone_e2e`.
5. `python tools/apps_list_build.py` then `--check`.
6. `intro-app.js` FLAVOUR: `epilogue: ['rings', 'Read the week', 'tick'],` `transitions.js` REGISTRY: `epilogue: { kind: 'tiles', ms: 800 },`
7. Tests: `tests.test_epilogue_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

---
# Wiring ARGO, the voyage (2026-11-10)

App `argo` (`tools/web_public/argo/`) reads `../home.json` (accounts with `kind: funded`; `payouts[] {usd, date}` at the top or per account) and `../ledger/rules.json` (payout rules); `fixture.json` is the labelled DEMO, used only when home.json is missing. Goals (islands) are the owner's own, kept in this browser (`localStorage argo.goals.v1`, export / import as JSON). Progress is computed only from published numbers; a date appears only with at least 2 full months of real payouts, always as a fastest / base / slowest range with n and "not a promise". 3D = a marble trireme on waves drawn on a 2D canvas (`argoscene.js`, no WebGL); the map is plain SVG. Test `tests/test_argo_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

As with Nike, publishing `payouts` (dated) in `home.json` is what makes the money islands and the ETA come alive.

1. `jarvis/apps.js` BUILT_INS: `app('argo', 'Argo', 'money', '#4b7a99', 'The voyage: your money goals as islands, honest ETA ranges', { glyph: 'Α' }),`
2. `olympus/olympus.js` APPS: `argo: ['Argo', 'Α', '#4b7a99'],` AMBIENT: `argo: 'sea',`
3. `tools/build_web_dashboard.py` app tuple: add `"argo"`.
4. `sw.js` OTHER_APPS: `'argo/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`.
6. `olympus/intro-app.js` FLAVOUR: `argo: ['waves', 'Set sail', 'tap'],` `jarvis/transitions.js` REGISTRY: `argo: { kind: 'waves', ms: 1000 },`
7. Tests: `tests.test_argo_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_app_intro`, `tests.test_jarvis_transitions`.

# Wiring MINT CITY, the money machines as a 3D city (2026-11-10)

App `mintcity` (`tools/web_public/mintcity/`): reads `../money/index.json`, falls back to `fixture.json` (DEMO). 3D is `mintcityscene.js` (optional module, instanced buildings + LOD); LITE / no WebGL keeps the 2D map and the list of five districts. A tap on a district selects it (camera flies there, a sheet opens); its Open button / the list links open `../chrysos/`, `../mercury/`, `../sibyl/`, `../oikos/`, `../arbiter/`. URL: `?district=<id>`, `?demo=1`, `?flat=1`, `?q=low`. Test `tests/test_mintcity_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('mintcity', 'Mint City', 'money', '#c8a24a', 'The five money machines as a marble city', { glyph: 'MC' }),`
2. `olympus/olympus.js` APPS: `mintcity: ['Mint City', 'MC', '#c8a24a'],` AMBIENT: `mintcity: 'coins',`
3. `tools/build_web_dashboard.py` app tuple: add `"mintcity"` (with `"mint"`, `"stoa"`); the money files come from `python tools/money_publish.py --site <site_dir>`.
4. `sw.js` OTHER_APPS add `'mintcity/'`, bump `CACHE`, update the pinned strings in the zenith / hub tests.
5. `python tools/apps_list_build.py` then `--check`.
6. `intro-app.js` FLAVOUR: `mintcity: ['columns', 'Raise the city', 'tick'],` ; `transitions.js` REGISTRY: `mintcity: { kind: 'columns', ms: 1000, n: 5 },`
7. Tests: `tests.test_mintcity_page`, `tests.test_mint_page`, `tests.test_stoa_page`, `tests.test_money_engine`, plus the shared list in section 7 above.

---
# Wiring KRATOS (the discipline score, 2026-11-10)

App `kratos` in `tools/web_public/kratos/` (3D column via the render core: `column.js` + `columnload.js`). Reads `../odeon/trades.json` and, on the phone, the journal ratings in localStorage `journal.v1` (read only, never written); falls back to `fixture.json` (DEMO). Test `tests/test_kratos_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('kratos', 'Kratos', 'trading', '#c8a24a', 'Discipline score 0-100 per day: plan, stop, size, hours, flat', { glyph: 'K' }),`
2. `olympus/olympus.js` APPS: `kratos: ['Kratos', 'K', '#c8a24a'],` AMBIENT: `kratos: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"kratos"` (no extra data file).
4. `sw.js` OTHER_APPS: `'kratos/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`.
6. `olympus/intro-app.js` FLAVOUR: `kratos: ['columns', 'Keep your own rules', 'tap'],` and `jarvis/transitions.js` REGISTRY: `kratos: { kind: 'columns', ms: 1000, n: 4 },`
7. Tests: `tests.test_kratos_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.
