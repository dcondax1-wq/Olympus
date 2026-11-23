---
tags:
  - zeus/apps
  - door/nq-bot
type: "apps"
door: "NQ Bot"
---

# NQ Bot

| App | Group | What it is | Data | Test |
|---|---|---|---|---|
| Aegis (`aegis`) | trading | Risk guard: drawdown left, a full-stop what-if, when | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_aegis_page` |
| Apollo (`apollo`) | trading | Your weekly review and the one rule for | `fixture.json`, `../odeon/trades.json` | `tests.test_apollo_page` |
| Ares (`ares`) | trading | The war room: GO, WAIT or HALT | `../data.json`, `jarvis.json`, `rules.json`, `../home.json` | `tests.test_ares_page` |
| Argus (`argus`) | trading | The hundred eyes: what to fix | bundled fixture / its own files | `tests.test_argus_page` |
| Board (`board`) | trading | What the bot, you and Claude know: accounts | `board.json`, `../business/accounts.json`, `fixture.json`, `../nq/fixture.json` | `tests.test_board` |
| Chronos (`chronos`) (retired) | trading | Time and the session clock | `../odeon/trades.json`, `fixture.json` | `tests.test_chronos_page` |
| Delphi (`delphi`) (retired) | trading | The oracle's briefing: plan, target, go / no-go | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_delphi_page` |
| Demeter (`demeter`) | trading | Account health: drawdown dials, payout rules | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../plutus/roadmap.json` | `tests.test_demeter_page` |
| Epilogue (`epilogue`) | life | Your week in 60 seconds: the Sunday review | `fixture.json`, `../home.json`, `../odeon/trades.json`, `../money/index.json` | `tests.test_epilogue_page` |
| Fates (`fates`) | trading | Pass odds for each eval | `fixture.json` | `tests.test_fates` |
| Forum (`forum`) | trading | Morning briefing at the real NY hour | `../pantheon/pantheon.json`, `../home.json`, `fixture.json` | `tests.test_forum_page` |
| Mnemosyne (`journal`) | trading | A 10-second trade journal: what your habits cost | `edge.json`, `../trading/trades.json`, `../odeon/trades_lite.json`, `../odeon/trades.json`, `fixture.json`, ... | `tests.test_journal_page` |
| Kairos (`kairos`) (retired) | trading | The right moment: the bots' day on a | `fixture.json`, `../odeon/trades.json`, `../home.json` | `tests.test_kairos_page` |
| Kratos (`kratos`) | trading | Discipline score 0-100 per day: plan, stop, size | `fixture.json`, `../odeon/trades.json` | `tests.test_kratos_page` |
| Kronos (`kronos`) | money | The calendar of money: daily P&L, best weekday | `fixture.json`, `../odeon/trades_lite.json`, `../odeon/trades.json` | `tests.test_kronos_page` |
| Labyrinth (`labyrinth`) | trading | The risk maze: size your eval | `../odeon/trades.json`, `../home.json`, `fixture.json` | `tests.test_labyrinth_page` |
| Moirai (`moirai`) | trading | The three fates: pass, bust and time of | `fixture.json`, `../ledger/rules.json` | `tests.test_moirai_page` |
| Nemesis (`nemesis`) | trading | The fallen trades: what went wrong | `../odeon/trades.json`, `../home.json`, `fixture.json` | `tests.test_nemesis_page` |
| NQ (`nq`) | trading | The NQ bots, right now: status, drawdown left | `../odeon/trades.json`, `../home.json`, `fixture.json`, `howto.json`, `news_week.json`, ... | `tests.test_nq_page` |
| Odeon (`odeon`) | trading | Every trade, replayed in 3D | `trades.json` | `tests.test_odeon_page` |
| Oracle (`oracle`) | trading | The market radar, live | bundled fixture / its own files | `tests.test_oracle_page` |
| Pantheon (`pantheon`) | trading | The data gods: rates, liquidity, fear | `jarvis.json`, `pantheon.json`, `fixture.json` | `tests.test_pantheon` |
| Pheme (`pheme`) (retired) | trading | The word on the street: releases, and NQ's | `fixture.json`, `stats.json` | `tests.test_pheme_page` |
| Pnyx (`pnyx`) | money | Prop-firm rules and risk calculator: stop to micros | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_pnyx_page` |
| Pythia (`pythia`) | trading | The risk calendar: the next 14 days, and | `fixture.json`, `events.json`, `../home.json` | `tests.test_pythia_page` |
| Trading (`trading`) | trading | Every trade: today, calendar, stats, payout rules | `../status_feed.json`, `../why/why.json`, `../odeon/trades.json`, `../home.json`, `fixture.json`, ... | `tests.test_trading_page` |
| Why (`why`) | trading | Why our trades win and lose, per bot | `why.json` | `tests.test_why_page` |
| Zenith (`zenith`) | trading | NQ bots · Zlarior · ATLAS | data.json, home.json, live.json (the bot feeds) | `tests.test_zenith_mode` |

Back to [[ZEUS Apps]]
