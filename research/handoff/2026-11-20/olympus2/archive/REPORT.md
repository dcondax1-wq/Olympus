# Archive team report (day-archive, 2026-11-20)

Scope: the 50 app folders no other team owns (the archived, hidden and merged apps: apollo ... why, plus agency, inbox, tyche, pc).
Files: INVENTORY.md (one row per app: data and its age, errors before -> after, KB on open before -> after, verdict),
LEAD_WIRES.md (retire 25 apps: exact lines; notes for the data owners), scan.py (the 390x844 scan), make_inventory.py.

## What changed

| What | Result |
|---|---|
| One "Archived" strip on all 46 archived pages (`tools/archive_banners.py`) | Top of the page: `Archived · data Oct 28, 23 days old` + `Journal ->` (the live app). The date is read from the page's own data file, never typed in, amber when older than 2 days. On full-screen 3D pages the strip floats and the page's own top bar moves under it (via the kit's `--oly-st`, or Mind's `--st`); pages without that variable are pushed down instead. Exception: on Nemesis it floats over the title row (its 3D arena has only 11 px to spare under its panel, so any push hid a tappable figure). 44 px tap target, labelled note. Re-run is idempotent; `--check` / `--remove` |
| Forum showed a Nov 3 market read as "Good morning" news | A Pantheon read 2+ days old now says "Old: N days" on its 4 tablets and the news line says the calendar is old |
| Pantheon feed 17 days old (Forum, Cities, Datacity read it) | Rebuilt today from the 8 free sources (`python -m tools.pantheon --no-research`): VIX 28.44, council RISK-OFF 39, built 2026-11-20 |
| Epilogue said "+$272 on 0 trades" | Says the $ is the accounts' live week figure and the trade list ends earlier |
| Plutus and Ares downloaded the 8.8 MB `data.json` on every open | Plutus: 10.0 MB -> 1.4 MB on open (data.json only when Notes opens). Ares: account from the 150 KB `home.json` (the same feed NQ shows); data.json only as fallback / Rules tab |
| Pythia's calendar generator turned "FOMC minutes" rows into "FOMC decision" days | Fixed in `tools/money/pythia_dates.py` (+ a selftest guard): a regen would have painted Nov 18, Dec 30 and Feb 17 as red Fed days in Helios / Planner. The published events.json was already right and is unchanged |
| Built data in archive folders out of step with the repo (their own `--check` tests failed) | Rebuilt: Colosseum extra.json + card, Athena library, Ergasterion queue / lessons, Herald edition, Pinakes catalog. Pheme's rebuild moved numbers its test pins, so it stays as on pc |
| Agency asked for the owner's private `my_leads.json` on github.io (404) | Not asked on the public site (it only exists on the PC) |
| Atlas City: no icon (404) | Icon link added |
| Tests | New `tests.test_archive_banners` (olympus area, no browser) 9/9. Fixed tests that pinned stale data or the old behaviour: forum 47/47, pantheon 160/160, ares 91/92 (was 86/92 on pc; the 1 left fails on pc too), plutus 100/100, epilogue 55/55, olympus_kit mind 36/36. Full per-app run: see "Test results" below |

## What the scan found (50 apps, 390x844, live data)

- Page errors: 0. Sideways scroll: 0 px. Bytes on open, all 50 pages: 89.5 MB -> 81.2 MB (wire bytes; the strip's age check reads the browser's cached copy, so it adds no download). Dead links: none (a static sweep of every href/src/import in the 50 folders).
- Console 404s left: `kalshi.json` on Inbox, Stoa, Tyche, Polis, Hermes, Ergasterion, Symposium: the Kalshi bot's feed is not connected
  yet (Monday per STATE). By design, one line per page.
- Stale data: `odeon/trades.json` ends 2026-10-28 (Apollo, Kratos, Nemesis, Nike, Kairos, Chronos, Labyrinth, Odeon, and the main
  Trading / Journal / Kronos / NQ read it). It stays old because `research/lab/replays.json` was not rebuilt; `odeon_export.py` alone
  changes nothing. Every archived page that shows it now says its age in amber. `plutus/roadmap.json` (Nov 4) is a research model
  that still plans BLITZ and an ATLAS eval: re-running it would not make it true; the money owners should decide (LEAD_WIRES 3).
- Weight: most archived 3D pages pull 1.5-4 MB on open, two thirds of it the shared three.js (654 KB, cached once for all apps) and
  3D assets (people cast 485 KB, textures). Slimming them means rebuilding the 3D; retiring is cheaper (LEAD_WIRES 1).

## Verdicts

- VISIBLE 4 (agency, inbox, tyche, pc): fixed, no banner.
- KEEP-ARCHIVED 21: reachable from the Archive fold, banner with the live app and the data age (journal-type reviews, sizing odds,
  research libraries, the data hosts odeon / pythia / pantheon / archive).
- RETIRE? 25 (proposal, nothing deleted): duplicates of a main app, 3D gimmicks, dev pages. Folders stay (other apps read their files,
  old links keep working). Exact lines: LEAD_WIRES.md 1.

## Test results (every per-app suite of the 50 folders, this branch vs untouched pc)

Green on this branch: agency 118, apollo 40, arbiter 50, archive 65, arena 96, argo 59, atlascity, bridge 82, chronos 59, colosseum 105
(pc 103/105), delphi 43, epilogue 55, forum 47, harmonia 49, hephaestus 44, hermes 117, hestia 50, inbox 39, kairos 56, kratos 52,
labyrinth 39, lyceum 53, mind_page 208 (pc 207), mint 57, mintcity 57, moirai 60, nemesis 62, nike 56, oracle_page 102, plutus 100,
prometheus 102, stoa 50, symposium 90 (pc 89), tyche 112, why 50, pantheon 160, archive_banners 9, olympus_kit mind 36. smoke 9/9.

Not all green, and the same or better than pc (pre-existing, not from this branch): ares 91/92 (pc 86/92), argus 101/102 (= pc),
athena 131/132 (pc 130), ergasterion 160/163 (pc 158), herald 76/77 (pc 74), odeon 78/79 (= pc), pinakes 136/139 (pc 135),
polis 55/56 (= pc), pheme 58/60 (= pc), pythia 67/68 (pc 66; the left one is "events.json is not what the generator writes": kept on
purpose, LEAD_WIRES 3), olympus_kit oracle 31/35 (= pc), test_mind crashes the same way on pc, node_suites: an orphan
tests/test_jarvis_biz.mjs (another team's file).
The full `run_area.py olympus` did not finish inside the 30-minute background limit, so the suites were run one by one (above).
