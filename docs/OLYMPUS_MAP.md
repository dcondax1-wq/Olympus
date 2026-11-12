# OLYMPUS map

Every app, in the five districts of the Atlas command center (`tools/web_public/atlas/`). The district is the way you find it; the **group** column is the older registry group (`jarvis/apps.js`: trading / money / life) that the launcher and the Jarvis switcher use. **This file is generated: `python tools/olympus_map_build.py` (do not edit the table by hand; `tests.test_olympus_map` fails when it is stale).**

Finding things: Atlas has search (names and plain words), pinned rooms (long-press a room or tap the star), recent rooms, a "what needs me now" strip and an all-apps-on-one-screen view. The Zenith launcher button and the Jarvis orb have the same search, favourites (long-press a tile), recent apps and a MAP view.

Data: apps only read published JSON (and bundled `fixture.json` / demo fallbacks). No app places orders. Look: AGORA (`docs/DESIGN_AGORA.md`). Wiring a new app: `tools/wire_new_apps.py` + `tools/new_apps.json` (`docs/NEW_APPS_WIRING.md`).

| App (id) | District | Group | What it is | Data it reads | Test |
|---|---|---|---|---|---|
| Archive (`archive`) | Market | trading | The library of everything we ever tested, searchable | `fixture.json`, `index.json` | `tests.test_archive_page` |
| Ares (`ares`) | Market | trading | The war room: GO, WAIT or HALT | `../data.json`, `jarvis.json`, `rules.json`, `../home.json` | `tests.test_ares_page` |
| Chronos (`chronos`) | Market | trading | Time and the session clock | `../odeon/trades.json`, `fixture.json` | `tests.test_chronos_page` |
| Cities (`cities`) | Market | trading | A world of city islands | `fixture.json` | `tests.test_cities_page` |
| Colosseum (`colosseum`) | Market | trading | Where strategies fight: seven rounds on real stored | `extra.json`, `fixture.json`, `../archive/index.json`, `../home.json` | `tests.test_colosseum_page` |
| Compass (`compass`) | Market | trading | The next best action: at most five things | `fixture.json`, `../home.json`, `../money/index.json`, `../ledger/rules.json`, `../odeon/trades.json` | `tests.test_compass_page` |
| Delphi (`delphi`) | Market | trading | The oracle's briefing: plan, target, go / no-go | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_delphi_page` |
| Ergasterion (`ergasterion`) | Market | trading | The workshop: every AI worker, what it does | `builders.json`, `fixture.json`, `queue.json`, `../home.json`, `../money/index.json`, ... | `tests.test_ergasterion_page` |
| Forum (`forum`) | Market | trading | Morning briefing at the real NY hour | `../pantheon/pantheon.json`, `../home.json`, `fixture.json` | `tests.test_forum_page` |
| Helios (`helios`) | Market | trading | The morning briefing: today, drawdown, deals, plan | `fixture.json`, `../pythia/events.json`, `../home.json`, `../money/index.json` | `tests.test_helios_page` |
| Kairos (`kairos`) | Market | trading | The right moment: the bots' day on a | `fixture.json`, `../odeon/trades.json`, `../home.json` | `tests.test_kairos_page` |
| Kronos (`kronos`) | Market | money | The calendar of money: daily P&L, best weekday | `fixture.json`, `../odeon/trades.json` | `tests.test_kronos_page` |
| NQ (`nq`) | Market | trading | The NQ bots, right now: status, drawdown left | `../home.json`, `fixture.json`, `howto.json` | `tests.test_nq_page` |
| Odeon (`odeon`) | Market | trading | Every trade, replayed in 3D | `trades.json` | `tests.test_odeon_page` |
| Oracle (`oracle`) | Market | trading | The market radar, live | bundled fixture / its own files | `tests.test_oracle_page` |
| Pantheon (`pantheon`) | Market | trading | The data gods: rates, liquidity, fear | `jarvis.json`, `pantheon.json`, `fixture.json` | `tests.test_pantheon` |
| Pheme (`pheme`) | Market | trading | The word on the street: releases, and NQ's | `fixture.json`, `stats.json` | `tests.test_pheme_page` |
| Pinakes (`pinakes`) | Market | trading | The catalogue: browse and query every table OLYMPUS | `catalog.json`, `fixture.json`, `pinakes-views.json` | `tests.test_pinakes_page` |
| Pythia (`pythia`) | Market | trading | The risk calendar: the next 14 days, and | `fixture.json`, `events.json`, `../home.json` | `tests.test_pythia_page` |
| Zenith (`zenith`) | Market | trading | NQ bots · Zlarior · ATLAS · BLITZ | data.json, home.json, live.json (the bot feeds) | `tests.test_zenith_mode` |
| Clio (`clio`) | Research | trading | The research library: every study in plain words | `fixture.json`, `../writeups/index.json`, `../data.json` | `tests.test_clio_page` |
| Data City (`datacity`) | Research | trading | Every combo tested, as a city | `fixture.json`, `city.json`, `jarvis.json`, `../data.json`, `../pantheon/pantheon.json` | `tests.test_datacity` |
| Fates (`fates`) | Research | trading | Pass odds for each eval | `fixture.json` | `tests.test_fates` |
| Hephaestus (`hephaestus`) | Research | trading | The forge: tune the dials | `data.json`, `fixture.json` | `tests.test_hephaestus_page` |
| Moirai (`moirai`) | Research | trading | The three fates: pass, bust and time of | `fixture.json`, `../ledger/rules.json` | `tests.test_moirai_page` |
| Nemesis (`nemesis`) | Research | trading | The fallen trades: what went wrong | `../odeon/trades.json`, `../home.json`, `fixture.json` | `tests.test_nemesis_page` |
| Observatory (`observatory`) | Research | trading | Data health and research evidence | bundled fixture / its own files | covered by `tests.test_olympus_kit` |
| Prometheus (`prometheus`) | Research | trading | The Forge: strategies tested | `jarvis.json`, `forge.json` | `tests.test_prometheus` |
| Daphne (`tree`) | Research | trading | The strategy tree search | `jarvis.json`, `tree.json` | `tests.test_strategytree` |
| Aegis (`aegis`) | Money | trading | Risk guard: drawdown left, a full-stop what-if, when | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_aegis_page` |
| Arbiter (`arbiter`) | Money | money | Paper-only spreads and funding: net yearly return after | `fixture.json`, `../money/arbiter.json` | `tests.test_arbiter_page` |
| Chrysos (`chrysos`) | Money | money | Prop-firm fleet planner: fees against payouts, break-even (estimate) | `fixture.json`, `../money/chrysos.json` | `tests.test_chrysos_page` |
| Demeter (`demeter`) | Money | trading | Account health: drawdown dials, payout rules | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../plutus/roadmap.json` | `tests.test_demeter_page` |
| Dionysus (`dionysus`) | Money | money | The Kalshi desk: guard, what-if, scan. Suggestions only | `fixture.json`, `../kalshicity/edges.json`, `../kalshicity/whatif.json` | `tests.test_dionysus_page` |
| Harmonia (`harmonia`) | Money | money | The balance: what leans on the NQ bots | `fixture.json`, `../home.json`, `../money/index.json` | `tests.test_harmonia_page` |
| Hera (`hera`) | Money | money | The 12-month money plan, payouts, what to buy | `fixture.json`, `../plutus/roadmap.json` | `tests.test_hera_page` |
| Hermes (`hermes`) | Money | money | OLYMPUS Wrapped: your money | `jarvis.json`, `wrapped.json`, `demo.json`, `../fates/jarvis.json`, `../datacity/discoveries.json` | `tests.test_hermes` |
| Kalshi (`kalshi`) | Money | money | Kalshi bot · from your PC | `../kalshicity/forward.json`, `../kalshicity/scan.json` | `tests.test_kalshi_page` |
| Kalshi City (`kalshicity`) | Money | money | The Kalshi bot's edges as a night city | `fixture.json`, `edges.json`, `learning_log.json`, `hypotheses.json`, `learned.json` | `tests.test_kalshicity_page` |
| Labyrinth (`labyrinth`) | Money | trading | The risk maze: size your eval | `../odeon/trades.json`, `../home.json`, `fixture.json` | `tests.test_labyrinth_page` |
| Ledger (`ledger`) | Money | money | Your real money: fees, payouts, net profit | `../home.json`, `rules.json`, `fixture.json`, `../plutus/roadmap.json`, `ledger-${S.model.today}.json` | `tests.test_ledger_page` |
| Mercury (`mercury`) | Money | money | Deal watcher: sales, codes, free resets, rule changes | `fixture.json`, `../money/mercury.json` | `tests.test_mercury_page` |
| Mint (`mint`) | Money | money | The money machine: five streams, one honest estimate | `fixture.json`, `../money/index.json` | `tests.test_mint_page` |
| Mint City (`mintcity`) | Money | money | The five money machines as a marble city | `fixture.json`, `../money/index.json` | `tests.test_mintcity_page` |
| Oikos (`oikos`) | Money | money | The household: where money leaks, tax set-aside, buckets | `fixture.json`, `../money/oikos.json`, `../ledger/rules.json`, `oikos-${S.today}.json` | `tests.test_oikos_page` |
| Plutus (`plutus`) | Money | money | The money plan: accounts and payouts | `../data.json`, `jarvis.json`, `plans.json` | `tests.test_plutus_page` |
| Pnyx (`pnyx`) | Money | money | Prop-firm rules and risk calculator: stop to micros | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_pnyx_page` |
| Sibyl (`sibyl`) | Money | money | Prediction-market edges after fees: paper picks, ruin odds | `fixture.json`, `../money/sibyl.json`, `../money/sibyl_forward.json`, `../kalshicity/suggestions.json`, `suggestions_fixture.json` | `tests.test_sibyl_page` |
| Tyche (`tyche`) | Money | money | The Kalshi bets as a 3D fortune wheel | bundled fixture / its own files | `tests.test_tyche_page` |
| Argo (`argo`) | Command | money | The voyage: your money goals as islands, honest | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_argo_page` |
| Argus (`argus`) | Command | trading | The hundred eyes: what to fix | bundled fixture / its own files | `tests.test_argus_page` |
| Atlas (`atlas`) | Command | life | A fast map of every Olympus dashboard | bundled fixture / its own files | `tests.test_atlas_armed` |
| Bridge (`bridge`) | Command | trading | Link ChatGPT: 3 steps, live job status | `status.json`, `jobs.json`, `deliveries.json` | `tests.test_bridge_page` |
| Hestia (`hestia`) | Command | trading | Today at home: what to do right now | `fixture.json`, `../home.json`, `../odeon/trades.json` | `tests.test_hestia_page` |
| Inbox (`inbox`) | Command | life | Everything that needs a look, in one place | bundled fixture / its own files | `tests.test_inbox_page` |
| Kratos (`kratos`) | Command | trading | Discipline score 0-100 per day: plan, stop, size | `fixture.json`, `../odeon/trades.json` | `tests.test_kratos_page` |
| Settings (`settings`) | Command | life | Look, voice, storage and the tour | bundled fixture / its own files | `tests.test_settings_page` |
| Stoa (`stoa`) | Command | trading | The colonnade: what needs you right now | `fixture.json`, `../home.json`, `../money/index.json`, `../alerts.json` | `tests.test_stoa_page` |
| Apollo (`apollo`) | Life | trading | Your weekly review and the one rule for | `fixture.json`, `../odeon/trades.json` | `tests.test_apollo_page` |
| Arena (`arena`) | Life | life | Olympian ranks: XP for discipline | `rules.json`, `events.json` | `tests.test_arena` |
| Athena (`athena`) | Life | life | The library: strategy, rules, quiz | `jarvis.json`, `library.json`, `drills.json` | `tests.test_athena_page` |
| Epilogue (`epilogue`) | Life | life | Your week in 60 seconds: the Sunday review | `fixture.json`, `../home.json`, `../odeon/trades.json`, `../money/index.json` | `tests.test_epilogue_page` |
| Agora Gallery (`gallery`) | Life | life | Every 3D shape of the Agora on a | `fixture.json` | covered by `tests.test_olympus_kit` |
| Herald (`herald`) | Life | life | The daily paper: who built what, the day | `edition.json`, `editions/index.json`, `fixture.json`, `editions/${date}.json` | `tests.test_herald_page` |
| Mnemosyne (`journal`) | Life | trading | A 10-second trade journal: what your habits cost | `../odeon/trades.json`, `fixture.json`, `mnemosyne-journal.json` | `tests.test_journal_page` |
| Lyceum (`lyceum`) | Life | life | The school: daily rules quiz, ranks, habits costing | `fixture.json`, `../odeon/trades.json`, `../home.json` | `tests.test_lyceum_page` |
| Mind (`mind`) | Life | life | Your vault as a living 3D brain | bundled fixture / its own files | `tests.test_mind_page` |
| Nike (`nike`) | Life | life | The trophy hall: milestones and wins from real | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../odeon/trades.json`, `../kalshicity/edges.json` | `tests.test_nike_page` |
| Planner (`planner`) | Life | life | Day and week plan: session windows, tasks, habits | `../pythia/events.json`, `../home.json`, `fixture.json` | `tests.test_planner_page` |
| Polis (`polis`) | Life | life | The city of OLYMPUS: every app a building | `../olympus/polis.json`, `../olympus/polis-demo.json`, `fixture.json`, `../home.json`, `../kalshi.json`, ... | `tests.test_polis_page` |
| Symposium (`symposium`) | Life | life | Meet everyone who works for you, and talk | `fixture.json` | `tests.test_symposium_page` |

71 apps. Rebuild the registry list after editing `jarvis/apps.js` or `olympus.js`: `python tools/apps_list_build.py`; recount: `python tools/apps_list_build.py --check`.

## Where the organizing code lives

| Piece | File | Test |
|---|---|---|
| Atlas command center (districts, search, pins, recent, needs-me strip, one-screen map) | `tools/web_public/atlas/` (`atlas.js`, `hub.js`, `atlas.css`) | `node --test tests/test_atlas_standalone_hub.mjs`, `tests/test_atlas_intro.mjs` |
| Zenith launcher sheet (favourites, search, recent, MAP) | `tools/web_public/launcher.js` = `web_next/js/next/launcher.js` (byte-identical) | `tests.test_apps_list` |
| Jarvis switcher (search, MAP, favourites, recent) | `tools/web_public/jarvis/switcher.js` | `tests.test_jarvis_hub` (parts n, p, s) |
| App registry | `tools/web_public/jarvis/apps.js` -> `olympus/apps-list.js` | `tests.test_apps_list` |
| This map | `tools/olympus_map_build.py` -> `docs/OLYMPUS_MAP.md` | `tests.test_olympus_map` |
