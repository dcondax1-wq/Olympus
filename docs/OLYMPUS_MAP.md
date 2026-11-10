# OLYMPUS map (2026-11-10)

Every app, in the five districts of the Atlas command center (`tools/web_public/atlas/`). The district is the way you find it; the **group** column is the older registry group (`jarvis/apps.js`: trading / money / life) that the launcher and the Jarvis switcher use.

Finding things: Atlas has search (names and plain words), pinned rooms (long-press a room or tap the star), recent rooms, a "what needs me now" strip and an all-apps-on-one-screen view. The Zenith launcher button and the Jarvis orb have the same search, favourites (long-press a tile), recent apps and a MAP view.

Data: apps only read published JSON (and bundled `fixture.json` / demo fallbacks). No app places orders.

| App (id) | District | Group | What it is | Data it reads | Test |
|---|---|---|---|---|---|
| Ares (`ares`) | Market | trading | War room: GO, WAIT or HALT today | `../data.json`, `../home.json`, `rules.json` | `tests.test_ares_page` |
| Chronos (`chronos`) | Market | trading | Session clock: what time it is, what is open | `../odeon/trades.json`, `chronos-reel-${d.day}.json`, `fixture.json` | `tests.test_chronos_page` |
| Cities (`cities`) | Market | trading | City-island world of every data view | `../arena/events.json`, `../athena/library.json`, `../datacity/city.json`, `../fates/fates.json` | `tests.test_cities_page` |
| Delphi (`delphi`) | Market | trading | Pre-market plan: target, go or no-go | `../home.json`, `../ledger/rules.json`, `fixture.json` | `tests.test_delphi_page` |
| Forum (`forum`) | Market | trading | Morning briefing at the real New York hour | `../home.json`, `../pantheon/pantheon.json`, `fixture.json` | `tests.test_forum_page` |
| Odeon (`odeon`) | Market | trading | Every trade replayed in 3D | `trades.json` | `tests.test_odeon_page` |
| Oracle (`oracle`) | Market | trading | Live market radar for the NQ session | `data.json`, `demo_day.json`, `home.json`, `prophecy.json` | `tests.test_oracle_odeon_fx` |
| Pantheon (`pantheon`) | Market | trading | Rates, liquidity and fear, as gods | `fixture.json`, `pantheon.json` | `tests.test_pantheon` |
| Zenith (`zenith`) | Market | trading | The NQ bots: live trades, results, accounts | data.json, home.json, live.json (the bot feeds) | `tests.test_zenith_mode` |
| Clio (`clio`) | Research | trading | Library of every study in plain words | `../data.json`, `../writeups/index.json`, `fixture.json` | `tests.test_clio_page` |
| Data City (`datacity`) | Research | trading | Every strategy combination tested, as a city | `../data.json`, `../pantheon/pantheon.json`, `city.json`, `fixture.json` | `tests.test_datacity` |
| Fates (`fates`) | Research | trading | Pass odds for each prop-firm eval | `fates.json`, `fixture.json` | `tests.test_fates` |
| Hephaestus (`hephaestus`) | Research | trading | Tune the dials and see the result | `data.json`, `fixture.json` | `tests.test_hephaestus_page` |
| Nemesis (`nemesis`) | Research | trading | The losing trades and what went wrong | `../home.json`, `../odeon/trades.json`, `fixture.json` | `tests.test_nemesis_page` |
| Observatory (`observatory`) | Research | trading | Data health and the research evidence | `../arena/events.json`, `../cities/cities.json`, `../kalshicity/learning_log.json`, `../kalshicity/scan.json` | `node --test tests/test_observatory_lesson_clock.mjs` |
| Prometheus (`prometheus`) | Research | trading | The forge: strategies tested against history | `forge.json` | `tests.test_prometheus` |
| Daphne (`tree`) | Research | trading | Strategy tree search and its winners | `demo.json`, `tree.json` | covered by `tests.test_olympus_kit` |
| Demeter (`demeter`) | Money | trading | Account health: drawdown left and payout rules | `../home.json`, `../ledger/rules.json`, `../plutus/roadmap.json`, `fixture.json` | `tests.test_demeter_page` |
| Dionysus (`dionysus`) | Money | money | Kalshi desk: guard, what-if, scan (suggestions) | `../kalshicity/edges.json`, `../kalshicity/whatif.json`, `fixture.json` | `tests.test_dionysus_page` |
| Hera (`hera`) | Money | money | Twelve-month money plan and what to buy | `../plutus/roadmap.json`, `fixture.json` | `tests.test_hera_page` |
| Hermes (`hermes`) | Money | money | Wrapped: your money year in review | `../datacity/discoveries.json`, `demo.json`, `wrapped.json` | `tests.test_hermes` |
| Kalshi (`kalshi`) | Money | money | Kalshi bot status from your PC | `../kalshicity/forward.json`, `../kalshicity/scan.json`, `kit.json` | `tests.test_kalshi_edges` |
| Kalshi City (`kalshicity`) | Money | money | Kalshi bot edges drawn as a city | `edges.json`, `fixture.json`, `hypotheses.json`, `learned.json` | `tests.test_kalshicity_freshness` |
| Labyrinth (`labyrinth`) | Money | trading | Risk maze: how much size per eval | `../home.json`, `../odeon/trades.json`, `fixture.json` | `tests.test_labyrinth_page` |
| Ledger (`ledger`) | Money | money | Real money: fees, payouts, net profit | `../home.json`, `../plutus/roadmap.json`, `fixture.json`, `ledger-${S.model.today}.json` | `tests.test_ledger_freeze` |
| Plutus (`plutus`) | Money | money | Account and payout plan, step by step | `../data.json`, `plans.json`, `roadmap.json` | `tests.test_plutus_page` |
| Pnyx (`pnyx`) | Money | money | Prop-firm rules and stop-to-micros calculator | `../home.json`, `../ledger/rules.json`, `fixture.json` | `tests.test_pnyx_page` |
| Tyche (`tyche`) | Money | money | Kalshi bets as a 3D fortune wheel | bundled fixture / its own files | `tests.test_tyche_page` |
| Argus (`argus`) | Command | trading | The hundred eyes: what to fix next | `../cronos/status.json`, `../data.json`, `../home.json` | `tests.test_argus_page` |
| Atlas (`atlas`) | Command | life | This map: search and pin every room | `../home.json` | `tests.test_atlas_armed` |
| Bridge (`bridge`) | Command | trading | Link ChatGPT to Olympus in three steps | `deliveries.json`, `jobs.json`, `status.json` | `tests.test_bridge_courier_portal` |
| Hestia (`hestia`) | Command | trading | Today at home: what to do right now | `../home.json`, `../odeon/trades.json`, `fixture.json` | `tests.test_hestia_page` |
| Inbox (`inbox`) | Command | life | Everything that needs a look, one list | `../bridge/status.json`, `../kalshicity/learning_log.json` | `tests.test_inbox_page` |
| Settings (`settings`) | Command | life | Look, voice, storage and the tour | bundled fixture / its own files | `tests.test_settings_page` |
| Apollo (`apollo`) | Life | trading | Weekly review and one rule for next week | `../odeon/trades.json`, `fixture.json` | `tests.test_apollo_page` |
| Arena (`arena`) | Life | life | Ranks and XP for trading discipline | `arena-progress-${S.today}.json`, `events.json`, `rules.json` | `tests.test_arena` |
| Athena (`athena`) | Life | life | Library: strategy, rules and a quiz | `drills.json`, `library.json` | `tests.test_athena_page` |
| Mnemosyne (`journal`) | Life | trading | Ten-second trade journal, habits priced in dollars | `../odeon/trades.json`, `fixture.json`, `mnemosyne-journal.json` | `tests.test_journal_page` |
| Mind (`mind`) | Life | life | Your notes vault as a living 3D brain | bundled fixture / its own files | `tests.test_mind` |
| Planner (`planner`) | Life | life | Day and week plan, tasks, habits, notes | `fixture.json`, `planner-${day}.json` | `tests.test_planner_addons` |

40 apps. Rebuild the registry list after editing `jarvis/apps.js` or `olympus.js`: `python tools/apps_list_build.py`; recount: `python tools/apps_list_build.py --check`.

## Where the organizing code lives

| Piece | File | Test |
|---|---|---|
| Atlas command center (districts, search, pins, recent, needs-me strip, one-screen map) | `tools/web_public/atlas/` (`atlas.js`, `hub.js`, `atlas.css`) | `node --test tests/test_atlas_standalone_hub.mjs`, `tests/test_atlas_intro.mjs` (these read `atlas/` at the repo root: copy or link `tools/web_public/atlas` there to run them) |
| Zenith launcher sheet (favourites, search, recent, MAP) | `tools/web_public/launcher.js` = `web_next/js/next/launcher.js` (byte-identical) | `tests.test_apps_list` |
| Jarvis switcher (search, MAP, favourites, recent) | `tools/web_public/jarvis/switcher.js` | `tests.test_jarvis_hub` (parts n, p, s) |
| App registry | `tools/web_public/jarvis/apps.js` -> `olympus/apps-list.js` | `tests.test_apps_list` |
