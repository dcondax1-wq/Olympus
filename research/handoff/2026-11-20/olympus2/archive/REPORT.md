# Archive team report (day-archive, 2026-11-20)

Scope: the 51 app folders no other team owns (the archived, hidden and merged apps: apollo ... why, plus agency, inbox, tyche, pc).
Files: INVENTORY.md (one row per app: data and its age, errors before -> after, KB on open before -> after, verdict),
LEAD_WIRES.md (retire 25 apps: exact lines; notes for the data owners), scan.py (the 390x844 scan), make_inventory.py.

## What changed

| What | Result |
|---|---|
| One "Archived" strip on all 46 archived pages (`tools/archive_banners.py`) | Top of the page: `Archived · data Oct 28, 23 days old` + `Journal ->` (the live app). The date is read from the page's own data file, never typed in, amber when older than 2 days. Full-screen 3D pages are pushed down under it (nothing covered); Mind floats it and moves its HUD. 44 px tap target, labelled note. Re-run is idempotent; `--check` / `--remove` |
| Forum showed a Nov 3 market read as "Good morning" news | A Pantheon read 2+ days old now says "Old: N days" on its 4 tablets and the news line says the calendar is old |
| Pantheon feed 17 days old (Forum, Cities, Datacity read it) | Rebuilt today from the 8 free sources (`python -m tools.pantheon --no-research`): VIX 28.44, council RISK-OFF 39, built 2026-11-20 |
| Epilogue said "+$272 on 0 trades" | Says the $ is the accounts' live week figure and the trade list ends earlier |
| Plutus and Ares downloaded the 8.8 MB `data.json` on every open | Plutus: about 10 MB -> about 1.3 MB on open (data.json only when Notes opens). Ares: account from the 150 KB `home.json` (the same feed NQ shows); data.json only as fallback / Rules tab |
| Agency asked for the owner's private `my_leads.json` on github.io (404) | Not asked on the public site (it only exists on the PC) |
| Atlas City: no icon (404) | Icon link added |
| Tests | New `tests.test_archive_banners` (olympus area, no browser) 9/9. Fixed tests that pinned stale data or the old behaviour: forum 47/47, pantheon 160/160, ares 91/92 (was 86/92 on pc; the 1 left fails on pc too), plutus 100/100, epilogue 55/55, olympus_kit mind 36/36. Full per-app run: see "Test results" below |

## What the scan found (51 apps, 390x844, live data)

- Page errors: 0. Sideways scroll: 0 px. Dead links: none (a static sweep of every href/src/import in the 51 folders).
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
- KEEP-ARCHIVED 22: reachable from the Archive fold, banner with the live app and the data age (journal-type reviews, sizing odds,
  research libraries, the data hosts odeon / pythia / pantheon / archive).
- RETIRE? 25 (proposal, nothing deleted): duplicates of a main app, 3D gimmicks, dev pages. Folders stay (other apps read their files,
  old links keep working). Exact lines: LEAD_WIRES.md 1.

## Test results (per-app suites, this branch)

(filled in at the end of the run)
