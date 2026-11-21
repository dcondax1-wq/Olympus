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
| Websites (`agency`) | money | Website business HQ: next step, leads, audits, 3D | `fixture.json`, `my_leads.json`, `leads.json`, `callrules.json`, `callscript.json`, ... | `tests.test_agency` |
| Arbiter (`arbiter`) | money | Paper-only spreads and funding: net yearly return after | `fixture.json`, `../money/arbiter.json` | `tests.test_arbiter_page` |
| Argo (`argo`) | money | The voyage: your money goals as islands, honest | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_argo_page` |
| Business (`business`) | money | Every money model: next step, what is missing | `accounts.json`, `../home.json`, `business.json`, `fixture.json`, `dash.json`, ... | `tests.test_business` |
| Chrysos (`chrysos`) | money | Prop-firm fleet planner: fees against payouts, break-even (estimate) | `fixture.json`, `../money/chrysos.json` | `tests.test_chrysos_page` |
| Harmonia (`harmonia`) | money | The balance: what leans on the NQ bots | `fixture.json`, `../home.json`, `../money/index.json` | `tests.test_harmonia_page` |
| Hera (`hera`) | money | The 12-month money plan, payouts, what to buy | `../business/fleet_plan.json`, `fixture.json`, `../plutus/roadmap.json` | `tests.test_hera_page` |
| Hermes (`hermes`) | money | OLYMPUS Wrapped: your money | `jarvis.json`, `wrapped.json`, `demo.json`, `../fates/jarvis.json`, `../datacity/discoveries.json` | `tests.test_hermes` |
| Ledger (`ledger`) | money | Your real money: fees, payouts, net profit | `../home.json`, `rules.json`, `fixture.json`, `../plutus/roadmap.json`, `../money/scoreboard.json`, ... | `tests.test_ledger_page` |
| Mercury (`mercury`) | money | Deal watcher: sales, codes, free resets, rule changes | `fixture.json`, `../money/mercury.json` | `tests.test_mercury_page` |
| Mint (`mint`) | money | The money machine: five streams, one honest estimate | `fixture.json`, `../money/index.json` | `tests.test_mint_page` |
| Mint City (`mintcity`) | money | The five money machines as a marble city | `fixture.json`, `../money/index.json` | `tests.test_mintcity_page` |
| Oikos (`oikos`) | money | The household: where money leaks, tax set-aside, buckets | `../money/household.json`, `fixture.json`, `../money/oikos.json`, `../ledger/rules.json`, `oikos-${S.today}.json` | `tests.test_oikos_page` |
| Plutus (`plutus`) | money | The money plan: accounts and payouts | `../data.json`, `jarvis.json`, `plans.json` | `tests.test_plutus_page` |
| Widget (`widget`) | money | Your accounts as an iPhone widget + the | bundled fixture / its own files | `tests.test_widget` |

Back to [[ZEUS Apps]]
