# AGORA audit (2026-11-11, one-theme pass finished)
Tool: `python tools/agora_audit.py [--app id] [--render] [--headers]`; test `tests.test_agora_audit` (static, no browser; it now also pins one accent per app and sees `#rrggbbaa` colours).

| Area | agora-release | This branch |
|---|---|---|
| Hard FAILs (static) | 260 | **0** |
| All hits incl. JS warnings | 1,739 | 991 (left: web_next PC pages, root pages, optional cool themes in olympus/themes.js, jarvis/zenith-mode.js) |
| Rendered scan, 390x844 `?demo=1&q=low`, 67 apps | not run before | 0 apps over 30% cool colour (worst: argo 0.7%) |
| Accents | 24 legacy apps neon or hot (#a855f7, #7fe9ff, #2ef2d0, #ff3b30 ...) | one warm accent per app; apps.js = olympus.js APPS = page pre-paint = Athens plan; only the six palette colours are shared |

## Accent table (legacy apps; the newer apps keep the gold palette colours)
| App | Old | New | Family |
|---|---|---|---|
| zenith | #a855f7 | #9c6b3c | bronze |
| oracle | #7fe9ff | #7fb0a3 | sea-glass |
| datacity | #4f8cff | #5f8ea6 | aegean |
| observatory | #6eeaff | #a9bfd0 | pale aegean |
| tree (Daphne) | #34f5a0 | #6b9068 | laurel |
| argus | #3ad7ff | #3f8a8a | deep teal |
| nemesis | #8a6bff | #b55c66 | wine |
| hephaestus | #d96bff | #c7773f | forge copper |
| cities | #a68bff | #b88a50 | ochre |
| kalshicity | #2ef2d0 | #b5a642 | old gold |
| journal | #f09bd8 | #e08a6b | light terracotta |
| inbox | #7fd0ff | #9aa3a8 | slate marble |
| settings | #b79bff | #a39883 | stone |
| bridge | #34d399 | #8c7a5a | umber |
| mind | #5eead4 | #d9b8a8 | rose marble |
| athena | #5ea8ff | #7f8a52 | olive |
| kalshi | #2ef2d0 | #8fa07a | sage |
| tyche | #e879f9 | #cf8f7a | clay |
| ledger | #ffcf5a | #c2b280 | parchment |
| ares | #ff3b30 | #c8402e | war red |
| plutus | #9be84a | #a9b84f | green gold |
| forum | #b8e04a | #8f9f3c | moss |
| labyrinth | #ff4d57 | #a8765a | brick |
| odeon | #ff6b7f | #d77a7a | rose clay |

Each new accent is at least 9 CIELAB dE from every other app's; none is neon by the audit's rule.

## Per app
Baseline note = the same test on a clean agora-release checkout (Round 3 baseline rule). "not run" = no browser test of that app this round (only its accent row changed, covered by the static tests).

| App | Accent before -> after | Before: hard / all hits | After: hard / all hits | Rendered cool % | Test (this branch) | Baseline note |
|---|---|---|---|---|---|---|
| aegis | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| apollo | #e0b060 | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| arbiter | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| archive | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| arena | #ffb547 | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| ares | #ff3b30 -> #c8402e | 1 / 1 | 0 / 0 | 0.0 | ares_page: PASS (92 checks) | - |
| argo | #4b7a99 | 0 / 0 | 0 / 0 | 0.7 | not run | - |
| argus | #3ad7ff -> #3f8a8a | 12 / 12 | 0 / 0 | 0.0 | argus_page: 2 FAIL of 102 | agora-release: the same 2 FAIL (render core runs 2 passes, test wants 3) |
| athena | #5ea8ff -> #7f8a52 | 2 / 2 | 0 / 0 | 0.2 | athena_page: PASS (132 checks) | - |
| atlas | #efc979 | 0 / 3 | 0 / 0 | 0.0 | no own test | - |
| atlascity | - | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| bridge | #34d399 -> #8c7a5a | 0 / 0 | 0 / 0 | 0.0 | bridge_page: PASS (82 checks) | - |
| chronos | #d4a574 | 0 / 1 | 0 / 0 | 0.0 | chronos_page: PASS (lead trial on theme-trial, before the accent pass) | - |
| chrysos | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| cities | #a68bff -> #b88a50 | 29 / 71 | 0 / 0 | 0.0 | not run | - |
| clio | #d8c9a8 | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| compass | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| datacity | #4f8cff -> #5f8ea6 | 37 / 157 | 0 / 0 | 0.0 | not run | - |
| delphi | #e0b060 | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| demeter | #9aa564 | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| dionysus | #b77a8a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| epilogue | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| ergasterion | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| fates | #ffcf5a | 2 / 4 | 0 / 0 | 0.0 | not run | - |
| forum | #b8e04a -> #8f9f3c | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| gallery | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | no own test | - |
| harmonia | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| helios | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| hephaestus | #d96bff -> #c7773f | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| hera | #c96a4a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| hermes | #f7c948 | 1 / 1 | 0 / 0 | 0.0 | hermes: stopped early (exit 1, no FAIL line) | agora-release: the same stop (line 386, Copy as text click times out) |
| hestia | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| inbox | #7fd0ff -> #9aa3a8 | 1 / 1 | 0 / 0 | 0.0 | inbox_page: PASS (39 checks) | - |
| jarvis | - | 20 / 70 | 0 / 12 | 0.0 | no own test | - |
| journal | #f09bd8 -> #e08a6b | 1 / 1 | 0 / 0 | 0.0 | journal_page: PASS (86 checks) | - |
| kairos | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| kalshi | #2ef2d0 -> #8fa07a | 16 / 61 | 0 / 0 | 0.0 | kalshi_page: 1 FAIL of 319 | agora-release: 2 FAIL (Performance glide, 430px odometer fit); both are timing checks that come and go (lead trial 3, this branch 1); not from the recolour |
| kalshicity | #2ef2d0 -> #b5a642 | 24 / 41 | 0 / 0 | 0.0 | not run | - |
| kratos | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| kronos | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| labyrinth | #ff4d57 -> #a8765a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| ledger | #ffcf5a -> #c2b280 | 0 / 1 | 0 / 0 | 0.0 | ledger_page: PASS (88 checks) | - |
| lyceum | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| mercury | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| mind | #5eead4 -> #d9b8a8 | 1 / 1 | 0 / 0 | 0.0 | mind_page: PASS (208 checks) | - |
| mint | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| mintcity | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| moirai | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| nemesis | #8a6bff -> #b55c66 | 1 / 1 | 0 / 0 | 0.0 | nemesis_page: stopped early (exit 1, no FAIL line) | agora-release: the same stop (line 291, tap on a figure times out after 120 s). The accent check was the recolour's: fixed |
| nike | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| observatory | #6eeaff -> #a9bfd0 | 0 / 0 | 0 / 0 | 0.0 | no own test | - |
| odeon | #ff6b7f -> #d77a7a | 15 / 32 | 0 / 0 | 0.0 | odeon_page: PASS (79 checks) | agora-release: 1 FAIL of 79 |
| oikos | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| olympus | - | 14 / 88 | 0 / 17 | - | no own test | test_olympus_themes on agora-release: the same stop (line 309, Jarvis More -> Theme tap times out; 35 PASS before it) |
| oracle | #7fe9ff -> #7fb0a3 | 0 / 3 | 0 / 0 | 0.0 | oracle_page: 3 FAIL of 101 | agora-release: 4 FAIL of 101 |
| pantheon | #f2d68a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| pc | - | 0 / 0 | 0 / 0 | 0.0 | no own test | - |
| pheme | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| planner | #7fa7c2 | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| plutus | #9be84a -> #a9b84f | 5 / 5 | 0 / 0 | 0.0 | plutus_page: PASS (99 checks) | - |
| pnyx | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| prometheus | #ff7a1a | 5 / 5 | 0 / 0 | 0.0 | prometheus: 3 FAIL of 60 | agora-release: the same 3 FAIL + the same stop (line 340) |
| pythia | #e0b060 | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| settings | #b79bff -> #a39883 | 1 / 1 | 0 / 0 | 0.0 | settings_page: PASS (91 checks) | - |
| sibyl | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| stoa | #c8a24a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| tree | #34f5a0 -> #6b9068 | 1 / 1 | 0 / 0 | 0.0 | no own test | - |
| tyche | #e879f9 -> #cf8f7a | 0 / 0 | 0 / 0 | 0.0 | not run | - |
| (root pages) | - | 32 / 574 | 0 / 540 | - | no own test | - |
| web_next | - | 39 / 601 | 0 / 422 | - | no own test | - |

## Tests that pinned old neon (updated with the page)
test_apps_list (Oracle tile colour), test_bridge_page (Bridge row), test_olympus_themes (Oracle accent in Jarvis), test_odeon_page (Odeon's own accent has been gold #c8a24a since agora-release: the test was already stale there), test_oracle_page (Oracle's own accent #ebc775).

## Left (same on agora-release, not from the recolour)
argus 2 FAIL (render passes 2 vs 3); oracle 3 FAIL (dead exports, theme-color meta check, Jarvis card); prometheus 3 FAIL + stop at line 340; hermes stop at line 386; nemesis stop at line 291; olympus_themes stop at line 309 (Jarvis More -> Theme tap); kalshi 1-2 timing checks that come and go.
Static warnings only: web_next PC pages, olympus/themes.js cool themes, jarvis/zenith-mode.js violet (test_zenith_mode asserts it).

Cache bumps for the lead: jarvis/apps.js, jarvis/index.html, jarvis/jarvis.css, jarvis/portal.js, olympus/olympus.js, olympus/apps-list.js, web_next/js/next/apps-list.js, cities/athens-plan.js, cities/world.css, cities/district-world.css, datacity/city.js, datacity/map.html, and the page pre-paints of argus, athena, inbox, kalshicity, ledger, nemesis, settings, journal, ares, plutus, forum, arena, argo, pythia.
