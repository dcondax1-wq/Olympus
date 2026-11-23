---
tags:
  - zeus/apps
  - door/jarvis
type: "apps"
door: "Jarvis"
---

# Jarvis

| App | Group | What it is | Data | Test |
|---|---|---|---|---|
| Bridge (`bridge`) (retired) | trading | Link ChatGPT: 3 steps, live job status | `status.json`, `jobs.json`, `deliveries.json` | `tests.test_bridge_page` |
| Compass (`compass`) | trading | The next best action: at most five things | `fixture.json`, `../home.json`, `../money/index.json`, `../ledger/rules.json`, `../odeon/trades_lite.json`, ... | `tests.test_compass_page` |
| Ergasterion (`ergasterion`) (retired) | trading | The workshop: every AI worker, what it does | `builders.json`, `fixture.json`, `queue.json`, `../home.json`, `../money/index.json`, ... | `tests.test_ergasterion_page` |
| Helios (`helios`) | trading | The morning briefing: today, drawdown, deals, plan | `../nq/brief.json`, `fixture.json`, `../pythia/events.json`, `../home.json`, `../money/index.json` | `tests.test_helios_page` |
| Herald (`herald`) (retired) | life | The daily paper: who built what, the day | `edition.json`, `editions/index.json`, `fixture.json`, `editions/${date}.json` | `tests.test_herald_page` |
| Hestia (`hestia`) (retired) | trading | Today at home: what to do right now | `fixture.json`, `../home.json`, `../odeon/trades.json` | `tests.test_hestia_page` |
| Inbox (`inbox`) | life | Everything that needs a look, in one place | bundled fixture / its own files | `tests.test_inbox_page` |
| Stoa (`stoa`) (retired) | trading | The colonnade: what needs you right now | `fixture.json`, `../home.json`, `../money/index.json`, `../alerts.json` | `tests.test_stoa_page` |
| Symposium (`symposium`) (retired) | life | Meet everyone who works for you, and talk | `fixture.json` | `tests.test_symposium_page` |

Back to [[ZEUS Apps]]
