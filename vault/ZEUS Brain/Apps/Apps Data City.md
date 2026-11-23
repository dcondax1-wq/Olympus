---
tags:
  - zeus/apps
  - door/data-city
type: "apps"
door: "Data City"
---

# Data City

| App | Group | What it is | Data | Test |
|---|---|---|---|---|
| Archive (`archive`) | data | The library of everything we ever tested, searchable | `fixture.json`, `index.json` | `tests.test_archive_page` |
| Athena (`athena`) | data | The library: strategy, rules, quiz | `jarvis.json`, `library.json`, `drills.json` | `tests.test_athena_page` |
| Data City (`cities`) | data | The 3D city of everything: every app, every | `brain-data.json`, `fixture.json` | `tests.test_cities_page` |
| Clio (`clio`) | data | The research library: every study in plain words | `fixture.json`, `../writeups/index.json`, `hub.json`, `../data.json` | `tests.test_clio_page` |
| Colosseum (`colosseum`) | data | Where strategies fight: seven rounds on real stored | `extra.json`, `fixture.json`, `../archive/index.json`, `../home.json` | `tests.test_colosseum_page` |
| Data City (`datacity`) (retired) | data | Every combo tested, as a city | `fixture.json`, `city.json`, `jarvis.json`, `../data.json`, `../pantheon/pantheon.json` | `tests.test_datacity` |
| Hephaestus (`hephaestus`) (retired) | trading | The forge: tune the dials | `data.json`, `fixture.json` | `tests.test_hephaestus_page` |
| Mint City (`mintcity`) (retired) | money | The five money machines as a marble city | `fixture.json`, `../money/index.json` | `tests.test_mintcity_page` |
| Observatory (`observatory`) (retired) | trading | Data health and research evidence | bundled fixture / its own files | covered by `tests.test_olympus_kit` |
| Pinakes (`pinakes`) | data | The catalogue: browse and query every table OLYMPUS | `catalog.json`, `fixture.json`, `pinakes-views.json` | `tests.test_pinakes_page` |
| Polis (`polis`) (retired) | life | The city of OLYMPUS: every app a building | `../olympus/polis.json`, `../olympus/polis-demo.json`, `fixture.json`, `../home.json`, `../kalshi.json`, ... | `tests.test_polis_page` |
| Prometheus (`prometheus`) | data | The Forge: strategies tested | `jarvis.json`, `forge.json` | `tests.test_prometheus` |
| Daphne (`tree`) | data | The strategy tree search | `jarvis.json`, `tree.json` | `tests.test_strategytree` |

Back to [[ZEUS Apps]]
