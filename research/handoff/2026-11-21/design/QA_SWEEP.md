# Visual QA sweep: every app from Home + the Jarvis switcher (DESIGN, day-arenas 2026-11-21)

Scope: the 51 apps in the Jarvis switcher + Zenith Home, NQ, the ZEUS hub, Jarvis, the Gate (55 pages). iPhone-13 width (390 x 844,
mobile, touch), dark AND light phone. Each page: shot at the top + scrolled one screen, plus an automatic probe: pure-black slabs (a large
box <= #0e0e0e on a lighter surface), brown / olive / marble cards (hue 15-70, dark), sideways scroll, text contrast, taps < 40 px,
stuck "Loading" / NaN text, page errors, sticky bars without safe-area padding. Home-screen (standalone) mode: Chromium cannot emulate
the notch (env(safe-area-inset-*) is 0 there), so only the files were checked: `viewport-fit=cover` on all 55; the kit bars use
`--ag-st` / `env(safe-area-inset-*)`. A per-bar notch check needs the real iPhone. The status bar colour (theme-color / manifest) was fixed
for all pages.

## Results (probe counts, all 55 pages)

| Defect | Dark phone before -> after | Light phone before -> after |
|---|---|---|
| Brown / olive / marble cards | **85 -> 0** | **175 -> 0** |
| Near-black slabs (sticky bars, boxes) | 9 -> 4 (by design: NQ chart, Settings 3D preview, Planner input, Tree's own bar) | 3 -> 4 (same) |
| Stuck text ('Loading the funded account...') | 3 pages -> 0 | 3 -> 0 |
| Sideways scroll | 0 | 0 |
| Page errors | 0 | 0 |
| Address bar / status bar brown (#14110e) | 112 pages + 67 home-screen manifests -> 0 | same |

Not defects (left): NQ's chart box is black on purpose (chart on black, violet edge); "Loading when you get here..." on NQ / Trading is a
lazy section's honest label; the widget page shows its script as code. Contrast and tap-size probes found nothing over the line.

## The fixes, by severity

| # | Severity | What the owner saw | Fix | Files |
|---|---|---|---|---|
| 1 | High | **The address bar / status bar** brown-black on 47 apps (and the home-screen splash) | theme-color `#000000` (was AGORA `#14110e`) on 115 pages, theme/background `#000000` in 67 manifests; the audit tool's rule + the icon tool follow | `*/index.html`, `*/manifest.webmanifest`, `tools/agora_audit.py`, `tools/make_app_icons.py` |
| 2 | High | **A light-mode iPhone got AGORA's brown everywhere** (every app; no app has a light mode) | a light phone gets OLYMPUS NIGHT; only a page with its own light mode steps aside (Zenith with its light choice `le.theme`, a `light dark` page: the widget) | `olympus/themes.js` (`ownLight()`), Zenith `index.html` first frame |
| 3 | High | **Black slabs: the bars** (Zenith's top bar + bottom tabs, every kit tab list, the scroll app bar) `rgba(4,3,5,.97)` | violet glass `rgba(22,13,42,.84)` + violet edge in OLYMPUS NIGHT | `olympus/agora.css`, `zenith_agora.css` |
| 4 | High | **Brown cards** in 15 apps (Archive, Pinakes, Kratos, Colosseum, Epilogue, Moirai, Sibyl, Pythia, Apollo, Argus, Forum, Labyrinth, Nemesis, Prometheus, Fates): hard-coded `#211c16 / #1d1914 / #26211b` | each card colour is the look's token with the old colour as fallback (OLYMPUS NIGHT = `#16141c` card) | 15 app sheets (`?v=…q`) |
| 5 | Medium | **Brown strip on top of 46 archived pages** ("Archived · data ...") | night card `#16131e` + violet edge; the builder writes the same | 46 pages, `tools/archive_banners.py` |
| 6 | Medium | **Cream marble card** (the Stoic tablet on Journal, Kronos, Aegis, Helios, Pythia, Colosseum, Zenith ...) | night card, lavender text, violet edge (no glow text) | `olympus/polis-life.js` (`?v=pl5`, 13 pages) |
| 7 | Medium | **Board's PC SILENT box terra-cotta on bronze** | red alert `#ef4444` on the night card | `board/board.css` (`?v=b3i`) |
| 8 | Medium | **"Loading the funded account..." forever** (Board, Hera, Ledger) when the site copy does not load | says "No account numbers yet ..." instead | `olympus/moneyfx.js` |
| 9 | Medium | **Things over the text at the bottom**: the Ask Jarvis button sat over the cards' left edge on every app | it steps out of the way while a finger scrolls, back 0.9 s after | `jarvis/ask.js` (`?v=7` in olympus.js) |
| 10 | Low | **The widget page** brown cards | its dark tokens follow the look (night fallbacks) | `widget/widget.css` (`?v=3`) |

Before / after shots: `qa/01..14_*.jpg` (pairs) and `qa/after_{dark,light}_sheet*.jpg` (every app after). 2.8 MB total.

## Tests

- New `tests/test_qa_sweep.py` 13/13: one guard per class above (static) + Chromium, dark and light phone, on 9 apps: no brown card, no
  near-black sticky bar, night on a light phone.
- Updated (the night default on a light phone): `tests/agora_kit.py` (the AGORA-look suites pick AGORA on purpose; they only saw it
  before because Playwright's default phone is light), `test_nemesis_page`, `test_olympus_themes` n., theme-color pins in 11 page tests,
  `test_new_app_icons`, `test_fates`, `test_jarvis_hub`, `test_agora_audit` label, `test_zenith_nq` (zenith_agora `a5dq`).
- Green: smoke 11/11, qa_sweep 13/13, archive_banners 9/9, polis_life 40/40, jarvis_ask 15/15, widget 56/56, fates 80/80, epilogue 55/55,
  labyrinth 39/39, apollo 40/40, colosseum 105/105, kratos 52/52, moirai 60/60, nemesis 62/62, sibyl 61/61.
- Same as plain origin/pc (not mine): archive 64/65 (stale archive build), argus 91/102 + prometheus 96/102 (their fixture sites lack
  jarvis/ask.js: 404), forum 42/47, pinakes 135/139, pythia 67/68 (events.json stale), board 62/63 (tools/board.py fetch_lite),
  new_app_icons sfx.js line, agora_audit hard FAILs.

## LEAD_WIRES (tags only you bump; sw.js)

| File | Tag in pages | Bump to | Pages |
|---|---|---|---|
| `olympus/agora.css` | `?v=a10` | `a11` | 98 (tests pin a10 in a few page tests: bump there too) |
| `olympus/themes.js` | `?v=o10` | `o11` | 105 + `jarvis/sw.js` SHELL `'../olympus/themes.js?v=o10'` |
| `olympus/olympus.js` | `?v=o22` | `o23` | 77 (it loads `jarvis/ask.js?v=7`) |
| `olympus/moneyfx.js` | `?v=3` | `4` | board, hera, ledger (+1) |
| `jarvis/sw.js` | SHELL `'./ask.js'` (no tag) | keep, bump CACHE | ask.js changed |

Already bumped here: `zenith_agora.css?v=a5dq`, `board.css?v=b3i`, `widget.css?v=3`, `polis-life.js?v=pl5`, the 15 app sheets (`…q`).
Root `sw.js` needs nothing (it caches by full URL). Optional: the 12-file first-frame line from 2026-11-20 LEAD_WIRES can drop its
`prefers-color-scheme: light` clause (a light phone gets night now); without it those pages show AGORA for one frame on a light phone.
