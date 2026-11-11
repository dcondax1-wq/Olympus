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
6. `olympus/intro-app.js` FLAVOUR: `argo: ['rings', 'Set sail', 'tap'],` (the intro scene `waves` does not exist: the list uses `rings`) `jarvis/transitions.js` REGISTRY: `argo: { kind: 'waves', ms: 1000 },`

6. `olympus/intro-app.js` FLAVOUR: `argo: ['rings', 'Set sail', 'tap'],` `jarvis/transitions.js` REGISTRY: `argo: { kind: 'waves', ms: 1000 },`
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

# Wiring the Agora Gallery and the 3D shapes library (2026-11-10)

New shared library `olympus/shapes3d.js` (19 AGORA shapes, HD + LITE, instanced; any app: `import { build, materials, SHAPES } from '../olympus/shapes3d.js'` and add the group to a scene on the render core) and the app `gallery` (`tools/web_public/gallery/`, name "Agora Gallery": a rotating pedestal, the shelf of all 19 shapes with what each stands for, drag to turn, tap to look closer, Auto / High / Lite, 2D drawing fallback). Reads only its own `fixture.json` (the shelf; a test keeps it equal to `shapes3d.js`, regenerate it when a shape changes). Test `tests/test_shapes3d.py` (`--static` skips the one browser smoke). Same kit pins as the other AGORA apps (`olympus.js?v=o4`, `agora.css?v=a1`, `intro-app.js?v=i5`). Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `apps-list.js`, `intro-app.js`, `transitions.js`.

## 1. `jarvis/apps.js` BUILT_INS (after the `pnyx` row)
```js
  app('gallery', 'Agora Gallery', 'life', '#c8a24a', 'Every 3D shape of the Agora on a turning pedestal', { glyph: 'Γ' }),
```
## 2. `olympus/olympus.js`
APPS: `gallery: ['Agora Gallery', 'Γ', '#c8a24a'],`
AMBIENT (existing bed): `gallery: 'chimes',`
## 3. `tools/build_web_dashboard.py` app tuple (~line 1212): add `"gallery"` after `"pnyx"`.
## 4. `tools/web_public/sw.js`: `OTHER_APPS` add `'gallery/'`, bump `CACHE`; the precache list should also hold `olympus/shapes3d.js`, `olympus/render.js`, `olympus/materials.js` and `olympus/three-addons/*` if not already there; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
## 5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
## 6. Shared lines
`olympus/intro-app.js` FLAVOUR: `gallery: ['columns', 'Walk the Agora', 'tap'],`
`jarvis/transitions.js` REGISTRY: `gallery: { kind: 'columns', ms: 1000, n: 5 },`
## 7. Tests after wiring: `tests.test_shapes3d`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, then `python -X utf8 tests/run_gate.py --fast`. Then the app count goes up by one in CLAUDE_REFERENCE / CLAUDE.md.
## 8. Using a shape in another app (no wiring)
```js
import { createRenderer } from '../olympus/render.js';
import * as KIT from '../olympus/materials.js';
import { build, materials, warmLights } from '../olympus/shapes3d.js';
const lite = OLYMPUS.lite(), M = materials({ lite, kit: lite ? null : KIT });   // one material set for all shapes of the scene
warmLights(scene, { lite });
const owl = build('owl', { lite, materials: M, size: 1.6 }); scene.add(owl);     // pillarbar takes { values: [0..1], tones: ['gain', 'loss'] }
rc.start((dt, t) => { if (owl.userData.update) owl.userData.update(t); });
```
Keep bloom at 0.25 or less (`createRenderer({ bloom: { strength: 0.2, threshold: 0.95 } })`): only fire and gold may catch it.

---
# PYTHIA: the risk calendar (2026-11-10)

App `pythia` (`tools/web_public/pythia/`; the 3D marble wheel of days is `pythiawheel.js`, its own module tag). Reads the BUNDLED `events.json` (hand-maintained; edit it, then update `updated`), `../home.json` (today's live brief, optional) and `fixture.json` (DEMO, only if events.json cannot be read). Test `tests/test_pythia_page.py` (it checks every rule date and the roll against `docs/ROLL_DEC_2026.md`). Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

## 1. `jarvis/apps.js` BUILT_INS: `app('pythia', 'Pythia', 'trading', '#e0b060', 'The risk calendar: the next 14 days of Fed, inflation, jobs, expiries, holidays and the roll, with what the bots do', { glyph: 'Ψ' }),`
## 2. `olympus/olympus.js`: APPS `pythia: ['Pythia', 'Ψ', '#e0b060'],` and AMBIENT `pythia: 'chimes',`
## 3. `tools/build_web_dashboard.py` app tuple (~line 1212): add `"pythia"`. The build must copy `pythia/events.json` with the rest of the folder (it is a plain static file).
## 4. `tools/web_public/sw.js`: `OTHER_APPS` add `'pythia/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
## 5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
## 6. Shared lines
`olympus/intro-app.js` FLAVOUR: `pythia: ['rings', 'Read the calendar', 'tick'],`
`jarvis/transitions.js` REGISTRY: `pythia: { kind: 'sunburst', ms: 1000 },`
## 7. Tests after wiring: `tests.test_pythia_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, then `python -X utf8 tests/run_gate.py --fast`.
Keep `events.json` current: add the next months' FOMC / jobs / CPI dates when the agencies publish them (CPI, PPI and retail sales are in `undated` until then). Never guess a date: leave it undated or set `"verify": true`.

---
# Wiring KAIROS, the right moment (2026-11-10)

App `kairos` in `tools/web_public/kairos/` (the New York trading day on a 24 h ring and a marble sundial: bot windows, what the bots do now, today's trades with $ and R, dollars by hour with no claim below 3 trades; tested across the clock change of Sun 1 Nov 2026). Reads `../odeon/trades.json` (the bot's trades), `../home.json` (the bot's own state line, optional) and `fixture.json` (DEMO). Read only, keeps nothing. `?at=<ISO UTC>` fixes the clock for links and tests. Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('kairos', 'Kairos', 'trading', '#c8a24a', 'The right moment: bot windows, what the bots do now, trades on the clock', { glyph: 'K' }),`
2. `olympus/olympus.js` APPS: `kairos: ['Kairos', 'K', '#c8a24a'],` AMBIENT: `kairos: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"kairos"`.
4. `sw.js`: `OTHER_APPS` add `'kairos/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
6. `olympus/intro-app.js` FLAVOUR: `kairos: ['rings', 'Find the right moment', 'tick'],`
   `jarvis/transitions.js` REGISTRY: `kairos: { kind: 'sunburst', ms: 1000 },`
7. Tests: `python -X utf8 -m tests.test_kairos_page` (`--static` skips the browser), then `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

(Moirai needs no new wiring for the honesty upgrade; it is the same app folder.)

`events.json` is GENERATED: `python tools/money/pythia_dates.py` rebuilds it from rules (claims, option expiry, quad witching, the roll, holidays, the NFP rule) and from the repo's saved calendar `data/news/events.csv` (FOMC, CPI, PPI, ...; refresh that with `data/build_news.py` / the news hub, then rerun the script). The range and as-of date live in the file's `generated` block (edit them to extend the window). `--check` (run by `tests.test_pythia_page`) fails when the file is out of step. Dates the repo does not carry stay in `undated` with the name of the official calendar (text only). Never hand-edit a date into `events.json`.

---
# Wiring COMPASS (the next best action, 2026-11-10)

App `compass` in `tools/web_public/compass/` (3D rose via the render core: `rose.js` + `needleload.js`). Reads `../home.json`, `../money/index.json`, `../ledger/rules.json`, `../odeon/trades.json`; on the phone it READS `journal.v1` and `ledger.v1` and writes only `compass.state.v1` (Done / Snooze). Falls back to `fixture.json` (DEMO). Test `tests/test_compass_page.py`. Not touched: `sw.js`, `build_web_dashboard.py`, `apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

1. `jarvis/apps.js` BUILT_INS: `app('compass', 'Compass', 'trading', '#c8a24a', 'The next best action: up to five, ranked, with a $ or free tag', { glyph: 'C' }),`
2. `olympus/olympus.js` APPS: `compass: ['Compass', 'C', '#c8a24a'],` AMBIENT: `compass: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"compass"` (no extra data file).
4. `sw.js` OTHER_APPS: `'compass/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
5. `python tools/apps_list_build.py` then `--check`.
6. `olympus/intro-app.js` FLAVOUR: `compass: ['rings', 'Find your bearing', 'tap'],` and `jarvis/transitions.js` REGISTRY: `compass: { kind: 'sunburst', ms: 1000 },`
7. Tests: `tests.test_compass_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

Optional, outside this app: the Ledger page can store `lastExport` (ISO text or epoch) in `ledger.v1` when Export JSON is tapped; until then Compass says "no export on record".

# PHEME: the word on the street (2026-11-10)

App `pheme` (`tools/web_public/pheme/`; the 3D marble scroll rack is `phemerack.js`, its own module tag). Reads only `./stats.json` (built OFFLINE by `python tools/pheme_build.py` from `data/news/events.csv`, `data/news/hub.json` when newer, and the 5m NQ file `data/NQ_5m.csv`; stdlib, `--check`, `--selftest`) and its `fixture.json` (DEMO). HISTORY ONLY: how far NQ travelled on the last 8 CPI / jobs / PPI / FOMC days (points and $ for one MNQ micro, n shown), never a forecast. Test `tests/test_pheme_page.py` (it re-reads the raw 5m file to check real rows). Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`. The row is already in `tools/new_apps.json` (the lead runs `python tools/wire_new_apps.py --apply`).

## 1. `jarvis/apps.js` BUILT_INS: `app('pheme', 'Pheme', 'trading', '#c8a24a', 'The word on the street: releases, and NQ\'s past moves on them', { glyph: 'Ξ' }),`
## 2. `olympus/olympus.js`: APPS `pheme: ['Pheme', 'Ξ', '#c8a24a'],` and AMBIENT `pheme: 'chimes',`
## 3. `tools/build_web_dashboard.py` app tuple (~line 1212): add `"pheme"`. The build must copy `pheme/stats.json` with the folder (a plain static file). Rebuild it with `python tools/pheme_build.py` after `data/news/events.csv` or `data/NQ_5m.csv` change (`--check` fails when it is stale; the test runs it).
## 4. `tools/web_public/sw.js`: `OTHER_APPS` add `'pheme/'`, bump `CACHE`; update the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`.
## 5. `python tools/apps_list_build.py` then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js`.
## 6. Shared lines
`olympus/intro-app.js` FLAVOUR: `pheme: ['threads', 'Hear the word', 'tick'],`
`jarvis/transitions.js` REGISTRY: `pheme: { kind: 'tiles', ms: 800 },`
## 7. Tests after wiring: `tests.test_pheme_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, then `python -X utf8 tests/run_gate.py --fast`.

---
# Wiring HARMONIA (the balance, 2026-11-10)

App `harmonia` in `tools/web_public/harmonia/` (3D balance beam via the render core: `beam.js` + `beamload.js`). Reads `../home.json` and `../money/index.json`; falls back to `fixture.json` (DEMO). Test `tests/test_harmonia_page.py`.
The row is already in `tools/new_apps.json` (group money, accent `#c8a24a`, glyph `H`, ambient `coins`, flavour `['bars', 'Weigh it up', 'tap']`, transition `{ kind: 'waves', ms: 1000 }`): the lead runs `python tools/wire_new_apps.py --apply`, which writes the six files:

1. `jarvis/apps.js` BUILT_INS row  2. `olympus/olympus.js` APPS + AMBIENT  3. `tools/build_web_dashboard.py` app tuple  4. `sw.js` OTHER_APPS  5. `olympus/intro-app.js` FLAVOUR  6. `jarvis/transitions.js` REGISTRY.
Then bump `sw.js` CACHE and the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`, and run `python tools/apps_list_build.py --check`.
Tests after wiring: `tests.test_harmonia_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

## 9. Second batch (2026-11-10): 41 shapes, scene builder, collection, `OLYMPUS_SHAPES.mount`
- `olympus/shapes3d.js` now holds **41 shapes in five categories** (Architecture, Objects, Beasts, Money, Sea): the first 19 plus olivetree, chariot, cornucopia, kylix, redvase, bust, anchor, stele, tetradrachm (spinning), harp, caduceus, pegasus, sandal, bow, swordspear, trophy, goldbars, vaultdoor, fountain, stoa, dolphin, mosaic. The owl and the lyre were redrawn. Same contract: HD + LITE, instanced, warm only, `build(id, { lite, materials, size })`. `SHAPES[i].group` is now the category.
- New in the library: `bake(group)` / `bakedShape(id, { size })` merge a whole LITE shape into ONE mesh with vertex colours (one draw call), used by the collection (41 shapes, under 40,000 triangles, 42 draw calls).
- New `olympus/shapes2d.js` (pure data, one 64 x 64 line drawing per shape) and `olympus/shapes-mount.js`: after `<script type="module" src="../olympus/shapes-mount.js"></script>` any page has
  `OLYMPUS_SHAPES.mount(canvasOrElement, 'owl', { lite, spin, size, quality, label, values, tones })` -> `{ ok, id, flat, set(id), stop() }`. It uses the render core and warm light; with no WebGL (or `?flat=1`) the element gets the shape's drawing and name instead, so the spot is never blank. `OLYMPUS_SHAPES.ids / shapes` list what exists. Demo page: `olympus/shapes-demo.html`.
- Gallery: category chips (Architecture, Objects, Beasts, Money, Sea), tabs Shelf / Build / Collection. **Scene builder**: in Build, tap up to 6 shapes on the shelf, they stand on a ring of one big pedestal; Share copies `...gallery/#b=owl,temple,lyre` and opening that link restores the layout (`?view=collection` opens the collection). **Collection**: all 41 at once in rings (LITE, baked), tap one to name it and open it on the pedestal.
- Wiring is unchanged by the second batch (same `gallery` rows as sections 1 to 7). `sw.js` precache: also add `olympus/shapes3d.js`, `shapes2d.js`, `shapes-mount.js`, `gallery/stage.js`, `gallery/gallerycore.js`.

---
# Wiring HELIOS (the morning briefing, 2026-11-10)

App `helios` in `tools/web_public/helios/` (3D sun over columns via the render core: `sun.js` + `sunload.js`). Reads `../pythia/events.json`, `../home.json`, `../money/index.json`; on the phone it READS the quiz progress `lyceum.v1` (never written); falls back to `fixture.json` (DEMO). Test `tests/test_helios_page.py`
(its light copies of Pythia's day rules and Compass's urgent rules are checked against the real `pythiacore.js` and `compasscore.js`: if either changes, that test tells you).
The row is already in `tools/new_apps.json` (group trading, accent `#c8a24a`, glyph `S`, ambient `chimes`, flavour `['rings', 'Rise and plan', 'tick']`, transition `{ kind: 'sunburst', ms: 1000 }`): the lead runs `python tools/wire_new_apps.py --apply` (six files), then bumps `sw.js` CACHE and the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`, and runs `python tools/apps_list_build.py --check`.
Tests after wiring: `tests.test_helios_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

---
# Wiring ERGASTERION (the AI agent factory, 2026-11-10)

App `ergasterion` in `tools/web_public/ergasterion/` ("the workshop where every worker is visible"): a marble-and-bronze 3D factory floor (`floor.js` on the render core, loaded by its own `floorload.js` tag; LITE / no WebGL / `?flat=1` = a flat plan with the same 15 buttons; reduced motion = still) with one station per real worker: the 5 money machines (`../money/index.json`), LIT / ATLAS / BLITZ (`../home.json`), Mind, the Kalshi bot (public feed), Prometheus (`../prometheus/forge.json`), Hephaestus (`../hephaestus/data.json`), Cronos (`../cronos/status.json`), the task queue and the dev agents (both from `queue.json`). Each has a status lamp (working / idle / stale / failed / sample), a conveyor, and a card: doing now, last 5 outputs, what it learned (dated, with its source file), health. First person: joystick + drag look + collision, minimap, follow a worker, tap a platform; event ticker; Learning board (12 lessons, the week flagged); "What should we research next?" (ranked data gaps). Falls back to `fixture.json` (DEMO, labelled) when no worker file is published. Test `tests/test_ergasterion_page.py`.

**The builder (new, needs one line in the site build):** `tools/ergasterion_build.py` (stdlib, `--selftest`, `--check`) indexes `handoff/QUEUE.md`, `research/writeups/*.md`, the Mind's proposals and (when a git repo is there, never required) the newest commits / agent branches into `ergasterion/queue.json`. The site build must run, after the folder copy:
`python tools/ergasterion_build.py --out <site>/ergasterion/queue.json`
(the committed `tools/web_public/ergasterion/queue.json` is the fallback; rebuild it with `python tools/ergasterion_build.py` when QUEUE.md or a write-up changes, `--check` fails when it is stale). Not touched: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`. The row is already in `tools/new_apps.json` (group trading, accent `#c8a24a`, glyph `E`, ambient `chimes`, flavour `['columns', 'Walk the workshop', 'tap']`, transition `{ kind: 'columns', ms: 1000, n: 5 }`): the lead runs `python tools/wire_new_apps.py --apply` (six files), adds `"ergasterion"` to the `build_web_dashboard.py` app tuple (that copies the folder, `queue.json` included), then bumps `sw.js` CACHE and the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`, and runs `python tools/apps_list_build.py --check`.
Tests after wiring: `tests.test_ergasterion_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

**ERGASTERION people (2026-11-11):** `index.html` loads the shared kit as an optional module (`../olympus/people.js?v=p1`) and `floor.js` tries `import('../olympus/people3d.js')` for `spec(id)` colours; both may be absent (404 is fine: built-in chat and seeded cartoon look). Person ids used: `scanner:<chrysos|mercury|sibyl|oikos|arbiter>`, `bot:<lit|atlas|blitz|kalshi>`, `mind`, `villager:<prometheus|hephaestus|cronos|queue|dev>`, `builder:<branch without worktree-agent->` (also tried: its first 8 characters). If the People roster spells any of these differently, `kit.get(id)` returns null and Ergasterion quietly uses its own chat for that person: tell the People agent the ids above or change `personId()` / `builderIds()` in `ergasterioncore.js`. The 3D persons are Ergasterion's own instanced version (25 people in 2 batches); `people3d.figure()` is not used because 25 separate figures would break the draw-call budget.

**ERGASTERION Builders' camp (2026-11-11):** the same build line also writes `<site>/ergasterion/builders.json` = `handoff/agents_now.json` joined with git (`git log agora-release..<branch>`: last 8 commits with times, files, folders, merged work). It needs the local agent branches, so run it where they exist (this machine); on a machine without git or the branches every agent is honestly 'job only, no live activity'. The committed `builders.json` is a snapshot of build time: rerun `python tools/ergasterion_build.py` right before publishing so 'working' (a commit in the last 15 minutes) is fresh. `--check` does not compare it (it is git). Keep `handoff/agents_now.json` current: the camp shows at most 10 tents.

**ERGASTERION v2 (2026-11-11), wiring for the lead:** no new row and NO new build line: the existing `python tools/ergasterion_build.py --out <site>/ergasterion/queue.json` now also writes `<site>/ergasterion/lessons.json` next to it (Jarvis: "what did we learn this week" = its `say` sentence, `week`, `top`, `changed`) and reads `<site>/money/<id>.json` asof times when they are there, so run it AFTER the money files are copied into the site. Rebuild the committed pair with `python tools/ergasterion_build.py` when QUEUE.md, a write-up, a research run or `archive/index.json` changes (run it after `tools/archive_build.py`; `--check` covers both files). New page assets are only versions of files that already exist (`ergasterion.js`, `ergasterioncore.js`, `floor.js`, `ergasterion.css`, `?v=a2`): bump the `sw.js` CACHE. Optional, in the lead's files: add `ergasterion/lessons.json` where Jarvis reads app cards; the Archive only understands `?find=<text>` today, so the pipeline lanes link with `?find=open|adopt|rejected|<family>`: a real `?family=` / `?verdict=` parameter in `archive/archive.js` would make those links exact.

# Wiring ARCHIVE (the library of everything we ever tested, 2026-11-10)

App `archive` in `tools/web_public/archive/` (3D marble bookcases via the render core: `archivestage.js`, its own module tag; flat twin without WebGL). Reads `./index.json` (first load about 300 KB: facets, write-ups, the rejected list, datasets, every adopted / open run) and, after the first paint, `./runs-0.json` .. `runs-3.json` (the rejected runs); falls back to `fixture.json` (DEMO). Built OFFLINE by `python tools/archive_build.py` (stdlib; `--check`, `--selftest`) from `research/runs/*.json`, `research/writeups/*.md`, the "Tested and rejected" section of `docs/CLAUDE_REFERENCE.md` and `data/`. Test `tests/test_archive_page.py`.
The row is already in `tools/new_apps.json` (group trading, accent `#c8a24a`, glyph `B`, ambient `chimes`, flavour `['columns', 'Open the shelves', 'tap']`, transition `{ kind: 'tiles', ms: 800 }`): the lead runs `python tools/wire_new_apps.py --apply` (six files), then bumps `sw.js` CACHE and the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`, and runs `python tools/apps_list_build.py --check`.

## Site build lines (needed, otherwise `archive/index.json` is stale on the site)
1. `tools/build_web_dashboard.py`: the app tuple gets `"archive"` (the folder is copied whole, so `index.json` and `runs-*.json` ride along; `runs-*.json` must NOT be filtered out as "private").
2. `.github/workflows/cloud-monitor.yml`, step "Publish web dashboard" (line ~225): add this line directly ABOVE `python tools/build_web_dashboard.py --state dash/state.json --chart dash/chart.png --out site`:
   `          python tools/archive_build.py   # the Archive library index (stdlib, ~3 s)`
   (rewrites `tools/web_public/archive/*.json` from the repo; about 3 s; it needs `research/runs/`, `research/writeups/`, `docs/CLAUDE_REFERENCE.md`, `data/*.csv`). If the checkout is shallow or lacks those, skip it: the committed `archive/index.json` is still valid.
3. `tools/web_public/sw.js`: `OTHER_APPS` add `'archive/'`; do NOT precache `archive/runs-*.json` (about 540 KB together), only `archive/index.json` if at all.
Tests after wiring: `tests.test_archive_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

## The six rows (what `wire_new_apps.py --apply` writes for Archive)
1. `jarvis/apps.js` BUILT_INS: `app('archive', 'Archive', 'trading', '#c8a24a', 'The library of everything we ever tested, searchable', { glyph: 'B' }),`
2. `olympus/olympus.js`: APPS `archive: ['Archive', 'B', '#c8a24a'],` and AMBIENT `archive: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"archive"`.  4. `sw.js` OTHER_APPS: `'archive/'`.
5. `olympus/intro-app.js` FLAVOUR: `archive: ['columns', 'Open the shelves', 'tap'],`
6. `jarvis/transitions.js` REGISTRY: `archive: { kind: 'tiles', ms: 800 },`

---
# Wiring PINAKES (the catalogue of every table, 2026-11-11)

App `pinakes` in `tools/web_public/pinakes/` ("the catalogue": a universal data browser). A marble card cabinet whose five drawers are the districts (Market, Research, Money, Command, Life; three.js direct in `pinakesscene.js`, flat SVG cabinet on LITE / no WebGL / `?flat=1`, draws only while a drawer moves). Search the catalogue, open any table in a windowed grid (only the rows in view exist: 37,000 rows scroll like 30), sort, plain-word filters, quick stats, bar / line / histogram chart with group-by, list picker for nested files, saved views (this phone only, `pinakes.v1`, export / import), CSV + JSON export, share link (`#v=...` restores table + filters + sort + chart), and "Ask": 4 built-in questions that join known tables with the query in plain words. Reads `./catalog.json` (about 105 KB: one card per table, never the rows), then each table from its own URL when opened; falls back to `fixture.json` (DEMO with its tables inside). Test `tests/test_pinakes_page.py`.

**The builder (new):** `tools/pinakes_build.py` (stdlib, `--check`, `--selftest`) walks the site folder and writes `pinakes/catalog.json` + `pinakes/jarvis.json` (and, for the repo copy, the demo `fixture.json`). The committed catalogue covers the files in `tools/web_public/` and lists the build-only files (`home.json`, `data.json`, `intel.json`, `kalshi.json`, `alerts.json`, `money/*.json`, `cronos/status.json`, `datacity/discoveries.json`, `kalshicity/forward.json`, `kalshicity/scan.json`, `writeups/index.json`) as "Site build: measured when opened". Research CSVs under `data/` are listed with span and rows only (no URL, not downloadable).

## The exact build line (needed so the published catalogue also measures the build-only files)
In `.github/workflows/cloud-monitor.yml`, step "Publish web dashboard", add this line directly BELOW `python tools/build_web_dashboard.py --state dash/state.json --chart dash/chart.png --out site` (it must run after every other file is in `site/`):
`          python tools/pinakes_build.py --web site   # Pinakes: catalogue every table in the built site (stdlib, ~2 s)`
(or call the same thing as the last step inside `build_web_dashboard.py`: `subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pinakes_build.py"), "--web", out])`). It reads `site/**.json` + `data/*.csv`, writes only `site/pinakes/catalog.json` and `site/pinakes/jarvis.json`. If it is skipped, the committed `catalog.json` is still valid (build-only tables are then measured when the owner opens them). After adding or changing any app's JSON in the repo: `python tools/pinakes_build.py` (and `--check` fails when the committed catalogue is stale).

## The six rows (what `wire_new_apps.py --apply` writes for Pinakes; the row is already in `tools/new_apps.json`)
1. `jarvis/apps.js` BUILT_INS: `app('pinakes', 'Pinakes', 'trading', '#c8a24a', 'The catalogue: browse and query every table OLYMPUS keeps', { glyph: 'Κ' }),`
2. `olympus/olympus.js`: APPS `pinakes: ['Pinakes', 'Κ', '#c8a24a'],` and AMBIENT `pinakes: 'scroll',`
3. `tools/build_web_dashboard.py` app tuple: add `"pinakes"` (the folder is copied whole: `catalog.json`, `fixture.json`, `jarvis.json` ride along).  4. `sw.js` OTHER_APPS: `'pinakes/'` (precache `pinakes/catalog.json` if wanted; never the tables it points at).
5. `olympus/intro-app.js` FLAVOUR: `pinakes: ['columns', 'Open the drawers', 'tap'],`
6. `jarvis/transitions.js` REGISTRY: `pinakes: { kind: 'tiles', ms: 800 },`
Then bump `sw.js` CACHE and the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`, run `python tools/apps_list_build.py --check`, and `python tools/make_app_icons.py pinakes` is already done (PNG icons are in the folder).
Tests after wiring: `tests.test_pinakes_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

# Wiring COLOSSEUM (where strategies fight, 2026-11-11)

App `colosseum` in `tools/web_public/colosseum/`: a marble amphitheatre in 3D (`arena.js` on the render core + `olympus/shapes3d.js`, its own module tag; LITE / no WebGL / `?flat=1` = a flat SVG arena) where two stored runs duel over seven rounds on their real numbers (net $, $ a month, PF, max drawdown $, trades a week, MFFU eval speed, holds in both periods). A number that is not stored makes the round "no contest". Plus a seeded tournament of the top 16 adopted runs, the league of LIT / ATLAS / BLITZ, the hall of champions and the fallen. Deep link `colosseum/#a=<runId>&b=<runId>`.
Reads `../archive/index.json` (+ `../archive/runs-<k>.json` after the first paint), `./extra.json`, `../home.json`; falls back to `fixture.json` (DEMO). Sends nothing, stores nothing. Test `tests/test_colosseum_page.py` (`--static` = no browser).
The row is already in `tools/new_apps.json` (group trading, accent `#c8a24a`, glyph `C`, ambient `chimes`, flavour `['torches', 'Enter the arena', 'tap']`, transition `{ kind: 'columns', ms: 1000, n: 5 }`): the lead runs `python tools/wire_new_apps.py --apply` (six files), then bumps `sw.js` CACHE and the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`, and runs `python tools/apps_list_build.py --check`.

## Site build lines (needed, otherwise `colosseum/extra.json` goes stale on the site)
1. `tools/build_web_dashboard.py`: the app tuple gets `"colosseum"` (the folder is copied whole, so `extra.json` rides along). The Archive must be on the site too (it already is): Colosseum reads `archive/index.json` and `archive/runs-*.json`.
2. `.github/workflows/cloud-monitor.yml`, step "Publish web dashboard": directly BELOW the `python tools/archive_build.py` line add
   `          python tools/colosseum_build.py   # Colosseum extras: max drawdown, dec10, pass_med per run (stdlib, ~2 s)`
   (rewrites `tools/web_public/colosseum/extra.json` from `research/runs/`; `--check` fails when it is stale, `--selftest` needs nothing). If the checkout lacks `research/runs/`, skip it: the committed file is still valid.
3. `tools/web_public/sw.js`: `OTHER_APPS` add `'colosseum/'`; do NOT precache `colosseum/extra.json` (about 130 KB).
4. Home Screen PNG icons: `flock -w 2400 /tmp/olympus_browser.lock python tools/make_app_icons.py colosseum` (already run; add `colosseum` to its `APPS` list if you want `--check` to cover it).
5. People kit (docs/PERSONA_API.md): once `tools/web_public/olympus/people.js` exists, add `<script type="module" src="../olympus/people.js?v=p1"></script>` to `colosseum/index.html` directly above the `arena.js` tag. The Talk button then calls `window.OLYMPUS_PEOPLE.open('champion:<run-id>' | 'bot:lit' | 'bot:atlas' | 'bot:blitz', { anchor })`; until then the page's own five-question card answers. (The tag is NOT in the page yet: a missing file makes the kit show "could not load".) The 3D champions are the app's own toy-like figures; `olympus/people3d.js` can replace `champion()` in `arena.js` later.
Tests after wiring: `tests.test_colosseum_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

## The six rows (what `wire_new_apps.py --apply` writes for Colosseum)
1. `jarvis/apps.js` BUILT_INS: `app('colosseum', 'Colosseum', 'trading', '#c8a24a', 'Where strategies fight: seven rounds on real stored numbers', { glyph: 'C' }),`
2. `olympus/olympus.js`: APPS `colosseum: ['Colosseum', 'C', '#c8a24a'],` and AMBIENT `colosseum: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"colosseum"`.  4. `sw.js` OTHER_APPS: `'colosseum/'`.
5. `olympus/intro-app.js` FLAVOUR: `colosseum: ['torches', 'Enter the arena', 'tap'],`
6. `jarvis/transitions.js` REGISTRY: `colosseum: { kind: 'columns', ms: 1000, n: 5 },`

# Wiring NQ (the NQ bots, right now, 2026-11-11)

App `nq` in `tools/web_public/nq/` ("the NQ bots, right now": Zlarior / LIT 50K, ATLAS 25K, BLITZ 25K; status with the exact age of the last report, drawdown left, the day's P&L in $ with R, eval progress, the last 10 trades and the rule that closed each, the plan, the backtest facts, the honest banner, the 5-step sheet). 3D: `nqscene.js`, its own module tag (three marble columns, a flame only for a bot that reported in the last 20 minutes; 2D columns without WebGL / in LITE). Reads `../home.json` only (never the 8 MB `data.json`), `./howto.json` and `./fixture.json` (DEMO).
The row is already in `tools/new_apps.json` (group trading, accent `#c8a24a`, glyph `Ν` (Greek Nu), ambient `chimes`, flavour `['columns', 'The bots, right now', 'tick']`, transition `{ kind: 'columns', ms: 1000, n: 3 }`): the lead runs `python tools/wire_new_apps.py --apply` (six files; dry run checked, `tests.test_apps_list --static` is 14/14 with it applied), then bumps `sw.js` CACHE and the pinned strings in `tests/test_zenith_mode.py`, `test_jarvis_hub.py`, `test_zenith_shell.py`, `test_phone_e2e.py`. Not touched by the agent: `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`.

## Site build lines
1. `tools/build_web_dashboard.py`: the app tuple gets `"nq"` (the folder is copied whole, `howto.json` rides along). Nothing else: the page reads the build's own `home.json`.
2. `nq/howto.json` is `docs/NQ_BOT_BACK.md` bundled: after editing that doc run `python tools/nq_howto_build.py` (`--check` exits 1 when stale; `tests.test_nq_page` runs it). Worth one line in the release gate next to the other `--check` builders.
3. Optional, for a live Jarvis card: the build may write `nq/jarvis.json` from `home.json` (status level + "Last report N ago"); the committed card is a static "open for the live status".

## Root page (Zenith) changes that ride with it (already in the tree, no wiring, but the worker must be bumped)
- `index.html` now loads `zenith_nq.js?v=1` (after `zenith_pages.js`, before `embed.js`), `zenith_hero.js?v=3`, `zenith_money.js?v=3`, `zenith_agora.css?v=a2`: bump `sw.js` `CACHE` (`le-public-v78` today) so phones take the new `index.html`.
- New root file `tools/web_public/zenith_nq.js` (the build copies every root file; `sw.js` precaches only SHELL, so nothing to add there).

## PC update kit (no wiring in the site)
- New owner files: `UPDATE_FROM_ZIP.bat`, `UNDO_UPDATE.bat`, `tools/update_from_zip.py`. Add both `.bat` names to `BATS` in `tests/test_win_scripts.py` (the agent did not edit that shared test; `tests/test_update_from_zip.py` lints them with the same `lint_bat`) and, if wanted, to `scripts/make_shortcuts.ps1`.
- `docs/CLAUDE_REFERENCE.md` "Infrastructure" and "PC tools" should get one line each (update from zip; `UPDATE.bat` / `engine.autoupdate` need GitHub and no longer work).

## The six rows (what `wire_new_apps.py --apply` writes for NQ)
1. `jarvis/apps.js` BUILT_INS: `app('nq', 'NQ', 'trading', '#c8a24a', 'The NQ bots, right now: status, drawdown left, last trades', { glyph: 'Ν' }),`
2. `olympus/olympus.js`: APPS `nq: ['NQ', 'Ν', '#c8a24a'],` and AMBIENT `nq: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"nq"`.  4. `sw.js` OTHER_APPS: `'nq/'`.
5. `olympus/intro-app.js` FLAVOUR: `nq: ['columns', 'The bots, right now', 'tick'],`
6. `jarvis/transitions.js` REGISTRY: `nq: { kind: 'columns', ms: 1000, n: 3 },`
Tests after wiring: `tests.test_nq_page`, `tests.test_zenith_nq`, `tests.test_update_from_zip`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`, `tests.test_zenith_shell`, `tests.test_zenith_pages`, `tests.test_zenith_mode`.

# Wiring SYMPOSIUM and the PEOPLE kit (talk to any worker, 2026-11-11)

Two things land together: the shared **people kit** in `tools/web_public/olympus/` (contract: `docs/PERSONA_API.md`) and the app `symposium` in `tools/web_public/symposium/` (the hall where you meet everyone).
Nothing in `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js`, `olympus.js`, `intro-app.js`, `transitions.js`, Jarvis, Ergasterion or Cities was touched.

## 1. The roster builder (new, needs ONE line in the site build)
`tools/people_build.py` (stdlib, `--selftest`, `--check`, `--no-git`) turns every real worker into a named person: the build agents of `handoff/agents_now.json` (+ their git branch when git is there, never required,
never part of `--check`), the five money scanners, LIT / ATLAS / BLITZ / Kalshi, the Mind, Prometheus / Hephaestus / Cronos / the task queue, one keeper per district of `jarvis/districts.js`, the top adopted runs of
`archive/index.json` (+ two rejected runs for debates) and one villager per app of `olympus/apps-list.js`. The exact build line (put it AFTER `python tools/archive_build.py` and `python tools/apps_list_build.py`, because it reads their files):

`python tools/people_build.py --out <site>/olympus/people.json`

The committed `tools/web_public/olympus/people.json` is the fallback (rebuild with `python tools/people_build.py` when `agents_now.json`, the Archive or the app list changes; `--check` fails when it is stale).
Without any `people.json` the kit still shows its built-in cast of 14 (never blank).

## 2. Files for `sw.js`
- precache (small, needed offline for every page that shows a person): `olympus/people.js`, `olympus/people-core.js`, `olympus/people-talk.js`, `olympus/people-data.js`, `olympus/people-brain.js`, `olympus/people.css`, `olympus/people.json`
- precache only if the 3D scenes are precached: `olympus/people3d.js`
- `OTHER_APPS`: `'symposium/'` (its files: `index.html`, `symposium.css`, `symposium.js`, `symposiumcore.js`, `hall.js`, `hallload.js`, `fixture.json`, `icon.svg`, the PNG icons, `manifest.webmanifest`, `jarvis.json`)
- `olympus/people-lab.html` is a checking page (every portrait and 3D figure); it does not need to be precached.
- `people.json` changes with the build: serve it network-first (or bump CACHE with the build), like `ergasterion/queue.json`.

## 3. The six rows (what `python tools/wire_new_apps.py --apply` writes for Symposium; the row is already in `tools/new_apps.json`)
1. `jarvis/apps.js` BUILT_INS: `app('symposium', 'Symposium', 'life', '#d9b25a', 'Meet everyone who works for you, and talk to them', { glyph: 'Σ' }),`
2. `olympus/olympus.js`: APPS `symposium: ['Symposium', 'Σ', '#d9b25a'],` and AMBIENT `symposium: 'chimes',`
3. `tools/build_web_dashboard.py` app tuple: add `"symposium"`.  4. `sw.js` OTHER_APPS: `'symposium/'`.
5. `olympus/intro-app.js` FLAVOUR: `symposium: ['torches', 'Take a seat', 'tap'],`
6. `jarvis/transitions.js` REGISTRY: `symposium: { kind: 'curtain', ms: 900 },`
Also: `jarvis/districts.js` / `atlas/atlas.js` district lists: add `'symposium'` to **Command** (it is where you talk to your workers); `python tools/make_app_icons.py symposium` if the PNG icons are regenerated.

## 4. How any page or 3D scene uses a person (for the Ergasterion, Hellas, Athens and Colosseum agents)
- `<script type="module" src="../olympus/people.js?v=p1"></script>` then `if (window.OLYMPUS_PEOPLE) OLYMPUS_PEOPLE.open(id, { anchor, facts })`. The kit loads its own stylesheet.
- Ids: `scanner:chrysos|mercury|sibyl|oikos|arbiter`, `bot:lit|atlas|blitz|kalshi`, `mind`, `job:prometheus|hephaestus|cronos|queue`, `keeper:market|research|money|command|life`, `builder:<first 8 of the branch>`,
  `champion:<run-id>`, `villager:<app-id>`. `get()` is forgiving: the bare name (`'chrysos'`, `'lit'`), `worker:<station>` / `station:<station>` (the Ergasterion station ids), a whole branch name, `builder:<agent-name-slug>`.
  ANY `keeper:<polis-id>` and `villager:<app-id>` gives a stable person even when it is not in the roster; give such a person something to say with `OLYMPUS_PEOPLE.provide(id, { doing, numbers: [{label, text}], last: [{t, text}], blocked, source })`
  or `open(id, { facts: {...} })`. Without it a made-up keeper honestly says it only knows what the scene shows.
- 2D: `OLYMPUS_PEOPLE.portrait(id, 44)` (SVG element; the ring colour is the status), `portraitText(id, 128)` (SVG text for a canvas texture).
- 3D: `import { spec, figure, figureInstanced } from '../olympus/people3d.js'` (THREE is passed in). `figure(THREE, spec(id), { lite, seated, scale })` = 7 meshes, one shared material, <= 900 triangles (<= 350 lite), about 1 unit tall, feet at y = 0, facing +z;
  `.userData.pose('idle'|'wave'|'talk'|'cheer'|'slump'|'nod'|'shrug')`, `.userData.lookAt(vec3)`, `.userData.tick(dt, t)` each frame (skip it under reduced motion), `.userData.dispose()`.
  `figureInstanced(THREE, specs, { lite, seated })` = any crowd in 11 draw calls: `.userData.place(i, x, y, z, ry, scale)`, `.setActive(i, on)`, `.tick(t)`, `.pick(raycaster)`, `.headWorld(i)`.
- ME: `OLYMPUS_PEOPLE.me()` -> `{ name, made, spec }` (the owner's own character, made in Symposium, stored in `olympus.me.v1`); `figure(THREE, OLYMPUS_PEOPLE.me().spec)` is his body in first person. Event `olympus:people:me` when he changes it.
- Events on `window`: `olympus:people:open` / `close` / `request` / `me` / `ready`. Requests live in `localStorage` `olympus.requests.v1`; Symposium's Request box has "Copy for Claude".
- "Connect my brain": the kit only READS Jarvis's `jarvis.smart`; when smart mode is on, a question the offline engine cannot answer goes to the owner's own provider with the persona + facts, and a reply containing a number that is not in the facts is dropped.

Tests: `python -X utf8 -m tests.test_people` (node only, 83 checks) and `flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_symposium_page` (`--static` needs no browser).
After wiring also: `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

## Hellas (inside Cities, 2026-11-11): the world of 300+ cities above Athens, the desert, the people
Not a new app: everything is in `tools/web_public/cities/` (`hellas*.js`, `hellas*.css`, `hellas-fixture.json`, `hellas-builders.json`, `people-talk.js`, `people-fig.js`, `people.css`), opened by the "Enter Hellas" button, `#hellas` or `?hellas=1`.
1. `sw.js`: bump the worker version so phones fetch the new Cities files (no new OTHER_APPS row; no precache entry needed).
2. Optional, at site build: refresh the caravan snapshot with `python -c "import json;a=json.load(open('handoff/agents_now.json'));json.dump({'v':1,'asof':a['asof'],'label':'Snapshot at build time: the build agents that were working when this page was built. Not live.','agents':[{k:x[k] for k in ('name','job','area','branch')} for x in a['agents']]},open('tools/web_public/cities/hellas-builders.json','w'),indent=1)"` (today it is a committed copy, labelled "Snapshot at build time").
3. People kit: nothing to wire. When `olympus/people.js` / `people3d.js` land, Hellas and Athens load them by themselves (optional import, at most 1.5 s); until then they use their own chat card and figures.
---
# Wiring HERALD (the daily newspaper, 2026-11-11)

App `herald` in `tools/web_public/herald/` ("The Olympus Herald"): a broadsheet in the AGORA palette written ONLY from published files. A small marble newsstand whose scroll unrolls the lead headline (three.js direct in `heraldscene.js`, flat SVG scroll on LITE / no WebGL / `?flat=1`, draws only while the scroll moves). Lead + up to 10 stories (drop caps, column rules; one column on a phone, 3 on a wide screen), tap a story to read it with "where every number comes from", share as text, "Read it to me" (speechSynthesis, off by default), Older / Newer and swipe between the last 14 editions, boxes: by the numbers, market weather (calm / busy / careful from Pythia), corrections (flipped beliefs), classifieds (Mercury), a mini quiz (Lyceum's bank), 3 interviews (persona ids, portraits via the optional `../olympus/people.js`, initials otherwise), "just shipped" (git) and "not in today's paper" (stories skipped because a file is missing). Reads `./edition.json`, `./editions/index.json`, `./editions/<date>.json`, falls back to `fixture.json` (DEMO edition). Test `tests/test_herald_page.py`.

**The builder (new):** `tools/herald_build.py` (stdlib, `--check`, `--selftest`, `--date YYYY-MM-DD`, `--web <site>`). Deterministic for a given date (the clock only picks today's date). Every number in a story is a "fact" read from a named file (value at a path, a quote, or a recount); a story whose file is missing is NOT written and is listed under `skipped`. Sources: `handoff/agents_now.json`, `research/writeups/kalshi_edge_*.md`, and in the site folder `ergasterion/queue.json`, `kalshicity/suggestions.json`, `pythia/events.json`, `archive/index.json`, `money/index.json`, `money/mercury.json` (else `mercury/fixture.json`, marked sample), `home.json`, `jarvis/apps.js` (new apps since the last edition), `lyceum/lyceumcore.js`. Writes `herald/edition.json`, `herald/editions/<date>.json` (last 14 kept) + `editions/index.json`, `herald/jarvis.json`.

## The exact build line
In `.github/workflows/cloud-monitor.yml`, step "Publish web dashboard", directly BELOW the `python tools/build_web_dashboard.py ... --out site` line and below the Pinakes line:
`          python tools/herald_build.py --web site   # The Olympus Herald: today's edition from the built site (stdlib, ~1 s)`
It reads the built `site/` (so `home.json` and `money/*.json` stories appear) and writes only `site/herald/`. To keep the 14-edition archive across publishes, copy the previous `herald/editions/` from the published `dashboard` branch into `site/herald/editions/` before that line if the workflow has it (`cp -r dash_prev/herald/editions site/herald/ 2>/dev/null || true`); without it each publish starts the archive again from the committed copy (no error). Repo copy: `python tools/herald_build.py --date <date>`; `--check` fails when it is stale.

## The six rows (what `wire_new_apps.py --apply` writes for Herald; the row is already in `tools/new_apps.json`)
1. `jarvis/apps.js` BUILT_INS: `app('herald', 'Herald', 'life', '#c8a24a', 'The daily paper: who built what, the day, the verdicts, all sourced', { glyph: 'Η' }),`
2. `olympus/olympus.js`: APPS `herald: ['Herald', 'Η', '#c8a24a'],` and AMBIENT `herald: 'scroll',`
3. `tools/build_web_dashboard.py` app tuple: add `"herald"` (folder copied whole).  4. `sw.js` OTHER_APPS: `'herald/'` (do not precache `herald/editions/*`).
5. `olympus/intro-app.js` FLAVOUR: `herald: ['columns', 'Unroll the news', 'tap'],`
6. `jarvis/transitions.js` REGISTRY: `herald: { kind: 'tiles', ms: 800 },`
Then bump `sw.js` CACHE and the pinned strings, run `python tools/apps_list_build.py --check`, and `python tools/make_app_icons.py herald` (PNG icons are committed). After wiring, re-run `python tools/herald_build.py --date <today>` so the 'new apps' story compares against the new list.
Tests after wiring: `tests.test_herald_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`, `tests.test_app_intro`.

## Jarvis home v2 (2026-11-11)

No new files: every file the new home loads is already in `jarvis/sw.js` SHELL (`./jarvis.css?v=j16`, `./home-cards.js?v=hc1`,
`./home-data.js`, `./districts.js`, `./courtyard.js?v=c1`, `./home3d.js`, `./switcher.js`, `./welcome.js?v=w1`).
What changed inside them: `index.html`, `jarvis.css`, `home-cards.js`, `home-data.js`, `courtyard.js`, `home3d.js`, `switcher.js`.

Wiring needed (lead only):
- `tools/web_public/jarvis/sw.js`: bump the worker so phones pick the new home up: `const CACHE = 'jarvis-v32'` and add
  `'jarvis-v31'` to the front of `OLD` (SHELL installs with `cache: 'reload'`, so the version strings can stay as they are).
- Optional, same bump: `jarvis.css?v=j17`, `home-cards.js?v=hc2`, `courtyard.js?v=c2` in both `index.html` / `home3d.js` and SHELL
  (then also update the `jarvis.css?v=j16` pin in `tests/test_jarvis_home_agora.py` part e).
- Nothing for `apps.js`, `olympus.js` or the build.

Tests: `tests.test_jarvis_home_agora` (static, 41 checks), `tests.test_jarvis_home_v2` (browser, under the lock),
`tools/phone_fit_audit.py --apps jarvis` (+ `--iphone`).

## People v2 (characters, 2026-11-11, Round 4)
No new app. Changed shared files: `olympus/people3d.js` (figure v2 + GPU crowd), `olympus/people-core.js` (portrait v2, `drawLook`, shared face tables), `olympus/people-lab.html`, `symposium/hall.js`.
- Cache bumps for the lead: `sw.js` cache version (people3d.js, people-core.js, people-lab.html, symposium/hall.js changed). `hall.js` and the lab import `people3d.js?v=p2`; `people.js` still imports `./people-core.js` with no query (bump its importers' `?v=p1` -> `?v=p2` if the SW serves stale copies).
- Optional for the people/voice agent: `people.js portrait()` could pass `opts.expr` / `opts.mouth` through to `portraitTree` (portraitText already does) so chat portraits can show expressions and mouth shapes; the hall listens to `olympus:people:speak {id, on}` and `olympus:people:viseme {id, viseme, amount}`.
## Effects pass: fx-cine (2026-11-11, the visual effects agent)
No new app. Wiring for the lead:
- `tools/web_public/jarvis/sw.js` precache: add `'../olympus/fx-cine.js'` (the Jarvis home imports it), keep `'../olympus/render.js'`, bump `'./transitions.js?v=t2'` -> `?v=t3` and `'./home3d.js'` (changed); bump the worker's cache name.
- `tools/web_public/jarvis/index.html`: `./transitions.js?v=t2` -> `?v=t3` (door / scroll / flythrough kinds + `level()`).
- `tools/web_public/sw.js`: bump `CACHE` (render.js, fx-cine.js, fx-ui.js, fx-text.js, fx-lab.html, symposium/hall.js, ergasterion/floor.js, colosseum/arena.js, cities/athens.js, cities/hellas.js changed).
- `olympus/olympus.js` FXMAP (zero-edit wiring of the new UI effects): `press: 'ui', stagger: 'ui', goldFlash: 'text'`.

## Characters v3 (the rigged cast, People kit; 2026-11-11)
No new app. Wiring for the lead:
- `tools/web_public/sw.js`: bump `CACHE` (people3d.js, people.js, people-lab.html, symposium/hall.js changed; new olympus/people-rig.js, olympus/people-studio.js,
  olympus/three-addons/{GLTFLoader,SkeletonUtils,BufferGeometryUtils,meshopt_decoder.module}.js, assets/people/cast.glb). `assets/` is not in OTHER_APPS, so
  `assets/people/cast.glb?v=3` (497 KB, versioned) is kept cache-first after the first visit (offline OK). Optional: precache it in SHELL for offline-first.
- Any app service worker that precaches `olympus/people3d.js` should also list `olympus/people-rig.js`, `olympus/people-studio.js`, the four three-addons
  files and `assets/people/cast.glb?v=3` (`olympus/` is an OTHER_APPS folder with its own caching).
- Nothing to add to apps.js / olympus.js APPS / build_web_dashboard.py.
