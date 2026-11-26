# OLYMPUS map

**How Olympus is organized (2026-11-21, owner: "more organized").** One structure, everywhere:

1. **Home** (`gate/`, where the Olympus app opens) shows **the 6 main dashboards** in the owner's order (2026-11-22): **NQ Bot** (ZEUS: accounts,
   trades, brain), **Jarvis**, **Websites** (agency, factory, caller portal), **Data City** (+ the Research hub), **Money** (My MFFU Accounts, payouts,
   Decide, taxes), **Kalshi**. Each tile opens its dashboard and has at most 2 short links. Everything else is one tap away under **More** (never the
   landing page: nothing remembers it). Under More, "All apps in ..." opens each arena's page `hub/arena.html?a=<arena>`: every live app grouped by job,
   so **every app is at most 2 taps from Home** (3 for the rare ones behind More).
   A fresh launch of the installed app always lands on Home: the Jarvis page (where the owner's icon was saved) sends a launch there, once per launch.
2. **Every page has the same way back:** `Home > arena > app` at the top (plain names, not Greek ones), plus "Go to" (search, then the same 7 arenas). One tap on Home goes Home.
   It comes from `olympus/gate-nav.js`, loaded by the AGORA shell (`agora-ui.js`), by the a11y kit (`a11y.js`) or directly; the public client pages
   (agency demos, audits, showcase, factory, caller portal, concept sites) never get it.
3. **Retired apps redirect** to their replacement (`?stay=1` keeps the old page; nothing is deleted). Table below.
4. **One place per fact:** every account, its payout and its 7-day clocks live on **My MFFU Accounts** (`business/mffu.html`); Ledger keeps the real cash.
   A page that repeats one of them shows a "Main copy" chip linking there.

The arenas, the retired list and the fact owners are DATA in `tools/web_public/olympus/gate-catalog.js` (ARENAS, REPLACE, FACTS). **This file is generated:
`python tools/olympus_map_build.py` (do not edit by hand; `tests.test_olympus_map` fails when it is stale).** The link crawler and the nav checks:
`tests.test_olympus_nav`.

Data: apps only read published JSON (and bundled `fixture.json` / demo fallbacks). No app places orders. Look: OLYMPUS NIGHT (`docs/DESIGN_AGORA.md`).

## The arenas

| Arena | Front page (the Home tile) | Live apps | Its page |
|---|---|---|---|
| **NQ Bot** | Bots right now (`nq/`) | 27 | `hub/arena.html?a=nq` |
| **Jarvis** | Jarvis (`jarvis/`) | 4 | `hub/arena.html?a=jarvis` |
| **Websites** | Website business (`agency/`) | 1 | `hub/arena.html?a=agency` |
| **Data City** | Cities and Hellas (`cities/`) | 8 | `hub/arena.html?a=data` |
| **Money** | All my businesses (`business/`) | 8 | `hub/arena.html?a=money` |
| **Kalshi** | Kalshi bot (`kalshi/`) | 4 | `hub/arena.html?a=kalshi` |
| **Everything else** | - | 11 | `hub/arena.html?a=else` |

## Retired: where each old app sends you now

Retired apps are not on Home, in search or in A to Z. Their old links open the replacement (`?stay=1` keeps the old page).

| Retired | Opens |
|---|---|
| Arbiter (`arbiter`) | All my businesses (`business`) |
| Arena (`arena`) | Day and week plan (`planner`) |
| Argo (`argo`) | 12-month money plan (`hera`) |
| atlascity (`atlascity`) | Cities and Hellas (`cities`) |
| Bridge (`bridge`) | Jarvis (`jarvis`) |
| Chronos (`chronos`) | Bots right now (`nq`) |
| Data City (`datacity`) | Cities and Hellas (`cities`) |
| Delphi (`delphi`) | Morning briefing (`helios`) |
| Ergasterion (`ergasterion`) | Jarvis (`jarvis`) |
| Agora Gallery (`gallery`) | Settings (`settings`) |
| Harmonia (`harmonia`) | Your real money (`ledger`) |
| Hephaestus (`hephaestus`) | Everything we tested (`archive`) |
| Herald (`herald`) | Morning briefing (`helios`) |
| Hermes (`hermes`) | Your real money (`ledger`) |
| Hestia (`hestia`) | What to do next (`compass`) |
| Kairos (`kairos`) | Bots right now (`nq`) |
| Kalshi City (`kalshicity`) | Kalshi desk (`dionysus`) |
| Lyceum (`lyceum`) | Day and week plan (`planner`) |
| Mind (`mind`) | Jarvis (`jarvis`) |
| Mint (`mint`) | All my businesses (`business`) |
| Mint City (`mintcity`) | Cities and Hellas (`cities`) |
| Nike (`nike`) | Day and week plan (`planner`) |
| Observatory (`observatory`) | Everything we tested (`archive`) |
| Pheme (`pheme`) | Risk calendar (`pythia`) |
| Plutus (`plutus`) | 12-month money plan (`hera`) |
| Polis (`polis`) | Cities and Hellas (`cities`) |
| Stoa (`stoa`) | What to do next (`compass`) |
| Symposium (`symposium`) | Jarvis (`jarvis`) |

## One place per fact

| Fact | The one place | Also shown on (a 'Main copy' chip links back) |
|---|---|---|
| Accounts | My MFFU Accounts (`business/mffu.html`) | aegis, board, demeter, fates, hera, ledger, nq, today, trading, widget |
| Payouts | My MFFU Accounts (`business/mffu.html`) | board, chrysos, demeter, hera, ledger, nq, trading, widget |
| 7-day clocks | My MFFU Accounts (`business/mffu.html`) | aegis, board, nq |

## Merged earlier: where a folded app's content lives now

| Old app | Now on | What is there |
|---|---|---|
| Ares | nq/#gateCard | NQ page: GO / WAIT / HALT per account |
| Kairos | nq/#dayCard | NQ page: the bots' day strip (windows, now line, trades) |
| Chronos | nq/#pastCard | NQ page: the last 8 trading days, each opens its replay |
| Odeon | trading/#reelsCard | Trading: 8 trade reels, live first |
| Why | trading/#whyCard | Trading: why trades win and lose, per bot |
| Sibyl | dionysus/ | Kalshi desk: paper picks |
| Kalshi City | dionysus/ | Kalshi desk: the edges map |
| Apollo | journal/ | Journal: the week review |
| Epilogue | journal/ | Journal: the week in 60 seconds |
| Kratos | journal/ | Journal: habits and what they cost |
| Nemesis | journal/ | Journal: losing trades |
| Pythia | helios/ | Morning brief: the market-risk calendar, next 5 days |
| Delphi | helios/ | Morning brief: the plan and go / no-go |
| Forum | helios/ | Morning brief: the market morning notes |
| Plutus | hera/ | Payout plan |
| Argo | hera/ | Payout plan |
| Labyrinth | pnyx/ | Rules and size calculator: eval sizing |

## Every app

| App (id) | Arena | Group | What it is | Data it reads | Test |
|---|---|---|---|---|---|
| Aegis (`aegis`) | NQ Bot | trading | Risk guard: drawdown left, a full-stop what-if, when | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_aegis_page` |
| Apollo (`apollo`) | NQ Bot | trading | Your weekly review and the one rule for | `fixture.json`, `../odeon/trades.json` | `tests.test_apollo_page` |
| Ares (`ares`) | NQ Bot | trading | The war room: GO, WAIT or HALT | `../data.json`, `jarvis.json`, `rules.json`, `../home.json` | `tests.test_ares_page` |
| Argus (`argus`) | NQ Bot | trading | The hundred eyes: what to fix | bundled fixture / its own files | `tests.test_argus_page` |
| Board (`board`) | NQ Bot | trading | What the bot, you and Claude know: accounts | `board.json`, `../business/accounts.json`, `fixture.json`, `../nq/fixture.json` | `tests.test_board` |
| The Brain (`brain`) | NQ Bot | trading | Every bot as one 3D brain: next trade | `fixture.json` | `tests.test_brain` |
| Chronos (`chronos`) (retired) | NQ Bot | trading | Time and the session clock | `../odeon/trades.json`, `fixture.json` | `tests.test_chronos_page` |
| Delphi (`delphi`) (retired) | NQ Bot | trading | The oracle's briefing: plan, target, go / no-go | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_delphi_page` |
| Demeter (`demeter`) | NQ Bot | trading | Account health: drawdown dials, payout rules | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../plutus/roadmap.json` | `tests.test_demeter_page` |
| Epilogue (`epilogue`) | NQ Bot | life | Your week in 60 seconds: the Sunday review | `fixture.json`, `../home.json`, `../odeon/trades.json`, `../money/index.json` | `tests.test_epilogue_page` |
| Fates (`fates`) | NQ Bot | trading | Pass odds for each eval | `fixture.json` | `tests.test_fates` |
| Forum (`forum`) | NQ Bot | trading | Morning briefing at the real NY hour | `../pantheon/pantheon.json`, `../home.json`, `fixture.json` | `tests.test_forum_page` |
| Mnemosyne (`journal`) | NQ Bot | trading | A 10-second trade journal: what your habits cost | `edge.json`, `../trading/trades.json`, `../odeon/trades_lite.json`, `../odeon/trades.json`, `fixture.json`, ... | `tests.test_journal_page` |
| Kairos (`kairos`) (retired) | NQ Bot | trading | The right moment: the bots' day on a | `fixture.json`, `../odeon/trades.json`, `../home.json` | `tests.test_kairos_page` |
| Kratos (`kratos`) | NQ Bot | trading | Discipline score 0-100 per day: plan, stop, size | `fixture.json`, `../odeon/trades.json` | `tests.test_kratos_page` |
| Kronos (`kronos`) | NQ Bot | money | The calendar of money: daily P&L, best weekday | `fixture.json`, `../odeon/trades_lite.json`, `../odeon/trades.json` | `tests.test_kronos_page` |
| Labyrinth (`labyrinth`) | NQ Bot | trading | The risk maze: size your eval | `../odeon/trades.json`, `../home.json`, `fixture.json` | `tests.test_labyrinth_page` |
| Moirai (`moirai`) | NQ Bot | trading | The three fates: pass, bust and time of | `fixture.json`, `../ledger/rules.json` | `tests.test_moirai_page` |
| Nemesis (`nemesis`) | NQ Bot | trading | The fallen trades: what went wrong | `../odeon/trades.json`, `../home.json`, `fixture.json` | `tests.test_nemesis_page` |
| NQ (`nq`) | NQ Bot | trading | The NQ bots, right now: status, drawdown left | `../home.json`, `../business/accounts.json`, `../business/payday.json`, `../status_feed.json`, `../odeon/trades.json`, ... | `tests.test_nq_page` |
| Odeon (`odeon`) | NQ Bot | trading | Every trade, replayed in 3D | `trades.json` | `tests.test_odeon_page` |
| Oracle (`oracle`) | NQ Bot | trading | The market radar, live | bundled fixture / its own files | `tests.test_oracle_page` |
| Pantheon (`pantheon`) | NQ Bot | trading | The data gods: rates, liquidity, fear | `jarvis.json`, `pantheon.json`, `fixture.json` | `tests.test_pantheon` |
| Pheme (`pheme`) (retired) | NQ Bot | trading | The word on the street: releases, and NQ's | `fixture.json`, `stats.json` | `tests.test_pheme_page` |
| Four Pillars (`pillars`) | NQ Bot | trading | LIT, ATLAS, BLITZ, ORDER FLOW: status, accounts, edge | `pillars-data.json`, `../home.json`, `../business/accounts.json`, `../business/payday.json`, `../odeon/trades.json` | `tests.test_pillars` |
| Pnyx (`pnyx`) | NQ Bot | money | Prop-firm rules and risk calculator: stop to micros | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_pnyx_page` |
| Pythia (`pythia`) | NQ Bot | trading | The risk calendar: the next 14 days, and | `fixture.json`, `events.json`, `../home.json` | `tests.test_pythia_page` |
| Trading (`trading`) | NQ Bot | trading | Every trade: today, calendar, stats, payout rules | `../status_feed.json`, `../why/why.json`, `../odeon/trades.json`, `../home.json`, `fixture.json`, ... | `tests.test_trading_page` |
| War Room (`warroom`) | NQ Bot | trading | Every NQ bot, every step, live: what it | bundled fixture / its own files | `tests.test_warroom` |
| Why (`why`) | NQ Bot | trading | Why our trades win and lose, per bot | `why.json` | `tests.test_why_page` |
| Zenith (`zenith`) | NQ Bot | trading | NQ bots · Zlarior · ATLAS | data.json, home.json, live.json (the bot feeds) | `tests.test_zenith_mode` |
| Bridge (`bridge`) (retired) | Jarvis | trading | Link ChatGPT: 3 steps, live job status | `status.json`, `jobs.json`, `deliveries.json` | `tests.test_bridge_page` |
| Compass (`compass`) | Jarvis | trading | The next best action: at most five things | `fixture.json`, `../home.json`, `../money/index.json`, `../ledger/rules.json`, `../odeon/trades_lite.json`, ... | `tests.test_compass_page` |
| Ergasterion (`ergasterion`) (retired) | Jarvis | trading | The workshop: every AI worker, what it does | `builders.json`, `fixture.json`, `queue.json`, `../home.json`, `../money/index.json`, ... | `tests.test_ergasterion_page` |
| Helios (`helios`) | Jarvis | trading | The morning briefing: today, drawdown, deals, plan | `../nq/brief.json`, `fixture.json`, `../pythia/events.json`, `../home.json`, `../money/index.json` | `tests.test_helios_page` |
| Herald (`herald`) (retired) | Jarvis | life | The daily paper: who built what, the day | `edition.json`, `editions/index.json`, `fixture.json`, `editions/${date}.json` | `tests.test_herald_page` |
| Hestia (`hestia`) (retired) | Jarvis | trading | Today at home: what to do right now | `fixture.json`, `../home.json`, `../odeon/trades.json` | `tests.test_hestia_page` |
| Inbox (`inbox`) | Jarvis | life | Everything that needs a look, in one place | bundled fixture / its own files | `tests.test_inbox_page` |
| Stoa (`stoa`) (retired) | Jarvis | trading | The colonnade: what needs you right now | `fixture.json`, `../home.json`, `../money/index.json`, `../alerts.json` | `tests.test_stoa_page` |
| Symposium (`symposium`) (retired) | Jarvis | life | Meet everyone who works for you, and talk | `fixture.json` | `tests.test_symposium_page` |
| Websites (`agency`) | Websites | web | Website business HQ: next step, leads, audits, 3D | `fixture.json`, `my_leads.json`, `leads.json`, `callrules.json`, `callscript.json`, ... | `tests.test_agency` |
| Archive (`archive`) | Data City | data | The library of everything we ever tested, searchable | `fixture.json`, `index.json` | `tests.test_archive_page` |
| Athena (`athena`) | Data City | data | The library: strategy, rules, quiz | `jarvis.json`, `library.json`, `drills.json` | `tests.test_athena_page` |
| Data City (`cities`) | Data City | data | The 3D city of everything: every app, every | `brain-data.json`, `lab-data.json`, `hub-data.json`, `fixture.json` | `tests.test_cities_page` |
| Clio (`clio`) | Data City | data | The research library: every study in plain words | `fixture.json`, `../writeups/index.json`, `hub.json`, `../data.json` | `tests.test_clio_page` |
| Colosseum (`colosseum`) | Data City | data | Where strategies fight: seven rounds on real stored | `extra.json`, `fixture.json`, `../archive/index.json`, `../home.json` | `tests.test_colosseum_page` |
| Data City (`datacity`) (retired) | Data City | data | Every combo tested, as a city | `fixture.json`, `city.json`, `jarvis.json`, `../data.json`, `../pantheon/pantheon.json` | `tests.test_datacity` |
| Hephaestus (`hephaestus`) (retired) | Data City | trading | The forge: tune the dials | `data.json`, `fixture.json` | `tests.test_hephaestus_page` |
| Mint City (`mintcity`) (retired) | Data City | money | The five money machines as a marble city | `fixture.json`, `../money/index.json` | `tests.test_mintcity_page` |
| Observatory (`observatory`) (retired) | Data City | trading | Data health and research evidence | bundled fixture / its own files | covered by `tests.test_olympus_kit` |
| Pinakes (`pinakes`) | Data City | data | The catalogue: browse and query every table OLYMPUS | `catalog.json`, `fixture.json`, `pinakes-views.json` | `tests.test_pinakes_page` |
| Polis (`polis`) (retired) | Data City | life | The city of OLYMPUS: every app a building | `../olympus/polis.json`, `../olympus/polis-demo.json`, `fixture.json`, `../home.json`, `../kalshi.json`, ... | `tests.test_polis_page` |
| Prometheus (`prometheus`) | Data City | data | The Forge: strategies tested | `jarvis.json`, `forge.json` | `tests.test_prometheus` |
| Daphne (`tree`) | Data City | data | The strategy tree search | `jarvis.json`, `tree.json` | `tests.test_strategytree` |
| Arbiter (`arbiter`) (retired) | Money | money | Paper-only spreads and funding: net yearly return after | `fixture.json`, `../money/arbiter.json` | `tests.test_arbiter_page` |
| Arena (`arena`) (retired) | Money | life | Olympian ranks: XP for discipline | `rules.json`, `events.json` | `tests.test_arena` |
| Argo (`argo`) (retired) | Money | money | The voyage: your money goals as islands, honest | `fixture.json`, `../home.json`, `../ledger/rules.json` | `tests.test_argo_page` |
| Money (`business`) | Money | money | Every money model: next step, what is missing | `accounts.json`, `../home.json`, `business.json`, `fixture.json`, `dash.json`, ... | `tests.test_business` |
| Chrysos (`chrysos`) | Money | money | Prop-firm fleet planner: fees against payouts, break-even (estimate) | `fixture.json`, `../money/chrysos.json` | `tests.test_chrysos_page` |
| Harmonia (`harmonia`) (retired) | Money | money | The balance: what leans on the NQ bots | `fixture.json`, `../home.json`, `../money/index.json` | `tests.test_harmonia_page` |
| Hera (`hera`) | Money | money | The 12-month money plan, payouts, what to buy | `../business/fleet_plan.json`, `fixture.json`, `../plutus/roadmap.json`, `../home.json` | `tests.test_hera_page` |
| Hermes (`hermes`) (retired) | Money | money | OLYMPUS Wrapped: your money | `jarvis.json`, `wrapped.json`, `demo.json`, `../fates/jarvis.json`, `../datacity/discoveries.json` | `tests.test_hermes` |
| Ledger (`ledger`) | Money | money | Your real money: fees, payouts, net profit | `../home.json`, `rules.json`, `fixture.json`, `../plutus/roadmap.json`, `../money/scoreboard.json`, ... | `tests.test_ledger_page` |
| Lyceum (`lyceum`) (retired) | Money | life | The school: daily rules quiz, ranks, habits costing | `fixture.json`, `../odeon/trades.json`, `../home.json` | `tests.test_lyceum_page` |
| Mercury (`mercury`) | Money | money | Deal watcher: sales, codes, free resets, rule changes | `fixture.json`, `../money/mercury.json` | `tests.test_mercury_page` |
| Mind (`mind`) (retired) | Money | life | Your vault as a living 3D brain | bundled fixture / its own files | `tests.test_mind_page` |
| Mint (`mint`) (retired) | Money | money | The money machine: five streams, one honest estimate | `fixture.json`, `../money/index.json` | `tests.test_mint_page` |
| Nike (`nike`) (retired) | Money | life | The trophy hall: milestones and wins from real | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../odeon/trades.json`, `../kalshicity/edges.json` | `tests.test_nike_page` |
| Oikos (`oikos`) | Money | money | The household: where money leaks, tax set-aside, buckets | `../money/household.json`, `fixture.json`, `../money/oikos.json`, `../ledger/rules.json`, `oikos-${S.today}.json` | `tests.test_oikos_page` |
| Planner (`planner`) | Money | life | Day and week plan: session windows, tasks, habits | `../pythia/events.json`, `../home.json`, `../day/day.json`, `../day/inbox.json`, `fixture.json` | `tests.test_planner_page` |
| Plutus (`plutus`) (retired) | Money | money | The money plan: accounts and payouts | `../data.json`, `jarvis.json`, `plans.json` | `tests.test_plutus_page` |
| Widget (`widget`) | Money | money | Your accounts as an iPhone widget + the | bundled fixture / its own files | `tests.test_widget` |
| Dionysus (`dionysus`) | Kalshi | kalshi | The Kalshi desk: guard, what-if, scan. Suggestions only | `fixture.json`, `../kalshicity/edges.json`, `../kalshicity/whatif.json`, `../kalshi/k8.json`, `../kalshicity/learned.json`, ... | `tests.test_dionysus_page` |
| Kalshi (`kalshi`) | Kalshi | kalshi | Kalshi bot · from your PC | bundled fixture / its own files | `tests.test_kalshi_page` |
| Kalshi City (`kalshicity`) (retired) | Kalshi | kalshi | The Kalshi bot's edges as a night city | `fixture.json`, `edges.json`, `learning_log.json`, `hypotheses.json`, `learned.json` | `tests.test_kalshicity_page` |
| Sibyl (`sibyl`) | Kalshi | kalshi | Prediction-market edges after fees: paper picks, ruin odds | `fixture.json`, `../money/sibyl.json`, `../money/sibyl_forward.json`, `../kalshicity/suggestions.json`, `suggestions_fixture.json` | `tests.test_sibyl_page` |
| Tyche (`tyche`) | Kalshi | kalshi | The Kalshi bets as a 3D fortune wheel | bundled fixture / its own files | `tests.test_tyche_page` |
| Atlas (`atlas`) | Everything else | life | A fast map of every Olympus dashboard | bundled fixture / its own files | `tests.test_atlas_armed` |
| Agora Gallery (`gallery`) (retired) | Everything else | life | Every 3D shape of the Agora on a | `fixture.json` | covered by `tests.test_olympus_kit` |
| Settings (`settings`) | Everything else | life | Look, voice, storage and the tour | bundled fixture / its own files | `tests.test_settings_page` |

80 apps. Rebuild the registry list after editing `jarvis/apps.js` or `olympus.js`: `python tools/apps_list_build.py`; recount: `python tools/apps_list_build.py --check`.

## Where the organizing code lives

| Piece | File | Test |
|---|---|---|
| The arenas, retired -> replacement, one place per fact, every app's plain name and hub | `tools/web_public/olympus/gate-catalog.js` (ARENAS, REPLACE, FACTS, R) | `tests.test_olympus_nav`, `tests.test_gate_page`, `tests.test_hubs` |
| The breadcrumb Home > arena > app, Go to, the retired redirect, the Main copy chips | `tools/web_public/olympus/gate-nav.js` (loaded by `agora-ui.js`, `a11y.js` or the page) | `tests.test_olympus_nav` |
| The arena pages | `tools/web_public/hub/arena.html` + `arena.js` + `arena.css` | `tests.test_olympus_nav` |
| Home: the 6 arenas, Everything else, the All apps row | `tools/web_public/gate/index.html`, `gate/arenas.js`, `gate/gate.js` | `tests.test_gate_page` |
| The hubs (an older grouping; their tabs still show in search) | `tools/web_public/hub/` | `tests.test_hubs` |
| App registry (Jarvis switcher, launcher) | `tools/web_public/jarvis/apps.js` -> `olympus/apps-list.js` | `tests.test_apps_list` |
| The four doors (2026-11-18; hidden on Home since the arenas, kept for old links) | `tools/web_public/olympus/doors.js`, `hub/doors.html` | `tests.test_apps_list` (part d) |
| This map | `tools/olympus_map_build.py` -> `docs/OLYMPUS_MAP.md` | `tests.test_olympus_map` |
