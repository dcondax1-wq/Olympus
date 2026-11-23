---
tags:
  - zeus/apps
  - door/money
type: "apps"
door: "Money"
---

# Money

| App | Group | What it is | Data | Test |
|---|---|---|---|---|
| Arbiter (`arbiter`) (retired) | money | Paper-only spreads and funding: net yearly return after | `fixture.json`, `../money/arbiter.json` | `tests.test_arbiter_page` |
| Arena (`arena`) (retired) | life | Olympian ranks: XP for discipline | `rules.json`, `events.json` | `tests.test_arena` |
| Argo (`argo`) (retired) | money | The voyage: your money goals as islands, honest | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_argo_page` |
| Money (`business`) | money | Every money model: next step, what is missing | `accounts.json`, `../home.json`, `business.json`, `fixture.json`, `dash.json`, ... | `tests.test_business` |
| Chrysos (`chrysos`) | money | Prop-firm fleet planner: fees against payouts, break-even (estimate) | `fixture.json`, `../money/chrysos.json` | `tests.test_chrysos_page` |
| Harmonia (`harmonia`) (retired) | money | The balance: what leans on the NQ bots | `fixture.json`, `../home.json`, `../money/index.json` | `tests.test_harmonia_page` |
| Hera (`hera`) | money | The 12-month money plan, payouts, what to buy | `../business/fleet_plan.json`, `fixture.json`, `../plutus/roadmap.json`, `../home.json` | `tests.test_hera_page` |
| Hermes (`hermes`) (retired) | money | OLYMPUS Wrapped: your money | `jarvis.json`, `wrapped.json`, `demo.json`, `../fates/jarvis.json`, `../datacity/discoveries.json` | `tests.test_hermes` |
| Ledger (`ledger`) | money | Your real money: fees, payouts, net profit | `../home.json`, `rules.json`, `fixture.json`, `../plutus/roadmap.json`, `../money/scoreboard.json`, ... | `tests.test_ledger_page` |
| Lyceum (`lyceum`) (retired) | life | The school: daily rules quiz, ranks, habits costing | `fixture.json`, `../odeon/trades.json`, `../home.json` | `tests.test_lyceum_page` |
| Mercury (`mercury`) | money | Deal watcher: sales, codes, free resets, rule changes | `fixture.json`, `../money/mercury.json` | `tests.test_mercury_page` |
| Mind (`mind`) (retired) | life | Your vault as a living 3D brain | bundled fixture / its own files | `tests.test_mind_page` |
| Mint (`mint`) (retired) | money | The money machine: five streams, one honest estimate | `fixture.json`, `../money/index.json` | `tests.test_mint_page` |
| Nike (`nike`) (retired) | life | The trophy hall: milestones and wins from real | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../odeon/trades.json`, `../kalshicity/edges.json` | `tests.test_nike_page` |
| Oikos (`oikos`) | money | The household: where money leaks, tax set-aside, buckets | `../money/household.json`, `fixture.json`, `../money/oikos.json`, `../ledger/rules.json`, `oikos-${S.today}.json` | `tests.test_oikos_page` |
| Planner (`planner`) | life | Day and week plan: session windows, tasks, habits | `../pythia/events.json`, `../home.json`, `../day/day.json`, `../day/inbox.json`, `fixture.json` | `tests.test_planner_page` |
| Plutus (`plutus`) (retired) | money | The money plan: accounts and payouts | `../data.json`, `jarvis.json`, `plans.json` | `tests.test_plutus_page` |
| Widget (`widget`) | money | Your accounts as an iPhone widget + the | bundled fixture / its own files | `tests.test_widget` |

Back to [[ZEUS Apps]]
