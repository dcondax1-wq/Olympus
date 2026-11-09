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
  app('hera', 'Hera', 'money', '#c0603f', 'The 12-month money plan, payouts, what to buy next', { glyph: 'Ω' }),
  app('dionysus', 'Dionysus', 'money', '#b77a8a', 'The Kalshi desk: guard, what-if, scan. Suggestions only', { glyph: 'Σ' }),
  app('clio', 'Clio', 'trading', '#d8c9a8', 'The research library: every study in plain words', { glyph: 'Κ' }),
```
(purposes are 5-79 characters). The jarvis status overlay needs nothing: each folder has its static `jarvis.json`.

## 2. `olympus/olympus.js`
APPS table (name, glyph, colour equal the apps.js rows):
```js
hestia: ['Hestia', 'Η', '#c8a24a'], demeter: ['Demeter', 'Δ', '#9aa564'], apollo: ['Apollo', 'Α', '#e0b060'], hera: ['Hera', 'Ω', '#c0603f'], dionysus: ['Dionysus', 'Σ', '#b77a8a'], clio: ['Clio', 'Κ', '#d8c9a8'],
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
