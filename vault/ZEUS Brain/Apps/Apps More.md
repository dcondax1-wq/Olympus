---
tags:
  - zeus/apps
  - door/more
type: "apps"
door: "More"
---

# More

| App | Group | What it is | Data | Test |
|---|---|---|---|---|
| Archive (`archive`) | trading | The library of everything we ever tested, searchable | `fixture.json`, `index.json` | `tests.test_archive_page` |
| Arena (`arena`) | life | Olympian ranks: XP for discipline | `rules.json`, `events.json` | `tests.test_arena` |
| Athena (`athena`) | life | The library: strategy, rules, quiz | `jarvis.json`, `library.json`, `drills.json` | `tests.test_athena_page` |
| Atlas (`atlas`) | life | A fast map of every Olympus dashboard | bundled fixture / its own files | `tests.test_atlas_armed` |
| Bridge (`bridge`) | trading | Link ChatGPT: 3 steps, live job status | `status.json`, `jobs.json`, `deliveries.json` | `tests.test_bridge_page` |
| Cities (`cities`) | trading | The 3D city of everything: every app, every | `fixture.json` | `tests.test_cities_page` |
| Clio (`clio`) | trading | The research library: every study in plain words | `fixture.json`, `../writeups/index.json`, `../data.json` | `tests.test_clio_page` |
| Colosseum (`colosseum`) | trading | Where strategies fight: seven rounds on real stored | `extra.json`, `fixture.json`, `../archive/index.json`, `../home.json` | `tests.test_colosseum_page` |
| Compass (`compass`) | trading | The next best action: at most five things | `fixture.json`, `../home.json`, `../money/index.json`, `../ledger/rules.json`, `../odeon/trades.json` | `tests.test_compass_page` |
| Data City (`datacity`) | trading | Every combo tested, as a city | `fixture.json`, `city.json`, `jarvis.json`, `../data.json`, `../pantheon/pantheon.json` | `tests.test_datacity` |
| Ergasterion (`ergasterion`) | trading | The workshop: every AI worker, what it does | `builders.json`, `fixture.json`, `queue.json`, `../home.json`, `../money/index.json`, ... | `tests.test_ergasterion_page` |
| Agora Gallery (`gallery`) | life | Every 3D shape of the Agora on a | `fixture.json` | covered by `tests.test_olympus_kit` |
| Helios (`helios`) | trading | The morning briefing: today, drawdown, deals, plan | `fixture.json`, `../pythia/events.json`, `../home.json`, `../money/index.json` | `tests.test_helios_page` |
| Hephaestus (`hephaestus`) | trading | The forge: tune the dials | `data.json`, `fixture.json` | `tests.test_hephaestus_page` |
| Herald (`herald`) | life | The daily paper: who built what, the day | `edition.json`, `editions/index.json`, `fixture.json`, `editions/${date}.json` | `tests.test_herald_page` |
| Hestia (`hestia`) | trading | Today at home: what to do right now | `fixture.json`, `../home.json`, `../odeon/trades.json` | `tests.test_hestia_page` |
| Inbox (`inbox`) | life | Everything that needs a look, in one place | bundled fixture / its own files | `tests.test_inbox_page` |
| Lyceum (`lyceum`) | life | The school: daily rules quiz, ranks, habits costing | `fixture.json`, `../odeon/trades.json`, `../home.json` | `tests.test_lyceum_page` |
| Mind (`mind`) | life | Your vault as a living 3D brain | bundled fixture / its own files | `tests.test_mind_page` |
| Nike (`nike`) | life | The trophy hall: milestones and wins from real | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../odeon/trades.json`, `../kalshicity/edges.json` | `tests.test_nike_page` |
| Observatory (`observatory`) | trading | Data health and research evidence | bundled fixture / its own files | covered by `tests.test_olympus_kit` |
| Pinakes (`pinakes`) | trading | The catalogue: browse and query every table OLYMPUS | `catalog.json`, `fixture.json`, `pinakes-views.json` | `tests.test_pinakes_page` |
| Planner (`planner`) | life | Day and week plan: session windows, tasks, habits | `../pythia/events.json`, `../home.json`, `../day/day.json`, `../day/inbox.json`, `fixture.json` | `tests.test_planner_page` |
| Polis (`polis`) | life | The city of OLYMPUS: every app a building | `../olympus/polis.json`, `../olympus/polis-demo.json`, `fixture.json`, `../home.json`, `../kalshi.json`, ... | `tests.test_polis_page` |
| Prometheus (`prometheus`) | trading | The Forge: strategies tested | `jarvis.json`, `forge.json` | `tests.test_prometheus` |
| Settings (`settings`) | life | Look, voice, storage and the tour | bundled fixture / its own files | `tests.test_settings_page` |
| Stoa (`stoa`) | trading | The colonnade: what needs you right now | `fixture.json`, `../home.json`, `../money/index.json`, `../alerts.json` | `tests.test_stoa_page` |
| Symposium (`symposium`) | life | Meet everyone who works for you, and talk | `fixture.json` | `tests.test_symposium_page` |
| Daphne (`tree`) | trading | The strategy tree search | `jarvis.json`, `tree.json` | `tests.test_strategytree` |

Back to [[ZEUS Apps]]
