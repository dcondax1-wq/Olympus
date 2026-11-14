# OLYMPUS information architecture v2: nine hubs

Written 2026-11-14 (team O2). Owner, many times: *"Make it very organized. I keep saying this but it always looks the same: 'Trading', 'Money', 'Life'
subcategories. I want something more organized. Lock in."*

## The problem in one line

The front door listed **82 entries** (Gate catalog v1: Trading 33, Money 16, Life 12, Worlds 11, Workshop 8, Start 2) over about 70 separate apps.
Renaming the groups never helped because **a list of 70 apps is the problem, not the labels**: several apps answer the same question (four morning
briefs, three "what do I do now" pages, three risk views, three money plans, two clocks, two news pages), and nothing said which one to use.

## The fix

1. **Hubs named after the owner's jobs**, not after topics. Nine of them; each answers one question in his own words.
2. **One page per hub** (`hub/?h=<hub>&t=<tab>`) with **one tab per job**. Every tab shows **the best app for that job first** (a big card with its
   live status, "Open", and "Show it here" = the app embedded in a frame), the other apps for the job below, and the **duplicates folded** under
   "Other views of the same" (closed by default, each saying which app it duplicates). Nothing is deleted.
3. **The home is a command center** (`gate/`, also `olympus-live.html`): *Right now* first (bots on/off and how old the numbers are, drawdown left
   per eval, today's $, the trade window, Kalshi, my shift), each a tap to its app; then the nine hub tiles, each with a live one-line status
   ("2 evals active, $1,145 / $822 left"); then the search.
4. **Breadcrumbs everywhere**: `Home > Hub > app` on every AGORA app (olympus/gate-nav.js, loaded by olympus/agora-ui.js), plus the 11 pages that
   carry the gate-nav tag. "Go to" shows the nine hubs first, then Recent, then Home.
5. **Every old app URL still works.** Hubs only link to or embed the apps. The old Gate deep links `gate/?d=trading|money|life|worlds|workshop`
   open the matching hub (Bots & Evals, My Money, Plan & Day, Worlds, Settings & Help > Workshop).

## The nine hubs

| Hub | The question it answers | Tabs (one per job) | Apps | Live line on the home tile |
|---|---|---|---|---|
| **Today** | What is happening, and what do I do now? | Do now · Morning brief · News and market | 15 | the trade window + my shift |
| **Bots & Evals** | Are my bots on, and how is each eval doing? | Bots now · Risk · Pass odds · Trades · Review | 16 | "2 evals active, $1,145 / $822 left" (+ "Quiet / Old numbers" with the age) |
| **Kalshi** | How is the Kalshi bot doing, and where is an edge? | The bot · Edges | 3 | balance, today, open bets (`kalshi.json`) |
| **My Money** | What have I really made and spent, and what is next? | Real money · Plan and payouts · Household · Ideas and deals | 11 | this month / all time, cash only (`money/scoreboard.json`) |
| **Plan & Day** | What is on my calendar and my list? | Calendar and tasks · Habits and progress | 5 | shift, next event, tasks done (the Planner's `planner.today.v1`, this phone) |
| **Research** | What have we tested, and what works? | Library · Strategy search · Data | 8 | the live LIT numbers from Hephaestus's card |
| **Jarvis** | Ask anything. Who works for me? | Ask · Your AI team | 4 | "Ask anything · your AI team" |
| **Worlds** | The 3D places (optional, for fun) | Most visited · Numbers as places | 8 | (static) |
| **Settings & Help** | Change the look, start the PC, find any app | Settings · Help and every app (A to Z list of all 82) · Workshop | 12 | the current theme |

82 entries, each in exactly one hub (checked by `tests/test_hubs.py`). A few also appear as "Also useful here, from other hubs" (for example Kalshi City
and Tyche on the Kalshi hub, Aegis and NQ on Today), so the 3D views and cross-job tools are one tap from where you need them.

## Duplicates folded (the best version first)

| Job | Best version (shown first) | Folded under "Other views of the same" | Why this one |
|---|---|---|---|
| What do I do now | Compass (What to do next) | Stoa (Needs you now), Hestia (Today at home) | Compass ranks at most five actions by urgency and dollars, with a why; Stoa and Hestia answer the same with less. The home's Right-now card now does Hestia's job. |
| The morning brief | Helios (Morning briefing) | Delphi (Go or no-go), Forum (Market morning notes) | Helios is one scroll for 01:45 / 07:00 / 10:45 ET with drawdown, deals and the plan; Delphi and Forum repeat parts of it. |
| News days | Pythia (Risk calendar) | Pheme (News days) | Pythia says what the bots do on each event; Pheme is the history behind it. |
| The bots' clock | Kairos (The bots' day) | Chronos (Session clock) | same 24-hour question; Kairos shows the bots' windows. |
| Risk / drawdown | Aegis (Risk guard) | Demeter (Account health) | Aegis = drawdown left + when to stop; Demeter's dials repeat it. Pnyx (calculator) and Labyrinth (sizing) stay as separate jobs in the same tab. |
| Weekly review | Apollo (Weekly review) | Epilogue (Your week in 60 seconds) | Apollo ends with one rule for next week. |
| Real money | Ledger (Your real money, with the Scoreboard card) | Hermes (Money, wrapped) | the Ledger is the cash record; Hermes is a story view of it. |
| The money plan | Hera (12-month money plan) | Plutus (Accounts and payouts) | Hera is the newer plan on the same `plutus/roadmap.json`. |
| Kalshi edges | Dionysus (Kalshi desk) | Sibyl (Prediction-market picks) | Dionysus holds the guard, what-if and scan; Sibyl's picks are the same edges. |
| Habits game | Lyceum (Daily rules quiz) | Arena (Ranks and XP) | the quiz is the daily habit; XP is its score. |
| Your AI team | Ergasterion (Your AI workers) | Symposium (Meet your workers) | Ergasterion says what each worker does and learns. |
| Kalshi as a place | Kalshi City | Tyche (Fortune wheel) | same feed, Kalshi City shows the edges. |

Kept separate on purpose (they look alike but answer different questions): NQ (bots right now) vs the full Zenith dashboard; Ares (pre-trade GO / WAIT /
HALT) vs Compass; Inbox (a feed of events) vs Compass (ranked actions); Fates (odds) vs Moirai (simulator); Mint (side-income estimate) vs Ledger (cash).

## Every app: hub, tab, role, the question it answers, the data it reads

"best" = shown first in its tab; "also" = a separate job in the same tab; "folded into X" = a duplicate of X, kept under "Other views of the same".
The data column is from `docs/OLYMPUS_MAP.md` (generated); the hub columns are `olympus/gate-catalog.js` (the source of truth: edit it, not this table).

### Today (`hub/?h=today`): What is happening, and what do I do now?

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Do now | What to do next (Compass, `compass`) | **best** | At most five things for today, with why | `fixture.json`, `../home.json`, `../money/index.json`, `../ledger/rules.json`, `../odeon/trades.json` |
|  | Go, wait or halt (Ares, `ares`) | also | The pre-trade check: GO, WAIT or HALT | `../data.json`, `jarvis.json`, `rules.json`, `../home.json` |
|  | Inbox (Inbox, `inbox`) | also | Everything that needs a look, in one place | bundled fixture / its own files |
|  | Needs you now (Stoa, `stoa`) | folded into What to do next | What needs a look right now | `fixture.json`, `../home.json`, `../money/index.json`, `../alerts.json` |
|  | Today at home (Hestia, `hestia`) | folded into What to do next | What to do right now, at home | `fixture.json`, `../home.json`, `../odeon/trades.json` |
| Morning brief | Morning briefing (Helios, `helios`) | **best** | Today in one scroll: drawdown, deals, the plan | `fixture.json`, `../pythia/events.json`, `../home.json`, `../money/index.json` |
|  | Daily paper (Herald, `herald`) | also | Who built what, the day, the verdicts | `edition.json`, `editions/index.json`, `fixture.json`, `editions/${date}.json` |
|  | Go or no-go (Delphi, `delphi`) | folded into Morning briefing | The plan, the target and go / no-go for today | `fixture.json`, `../home.json`, `../ledger/rules.json` |
|  | Market morning notes (Forum, `forum`) | folded into Morning briefing | The briefing at the real New York hour | `../pantheon/pantheon.json`, `../home.json`, `fixture.json` |
| News and market | Risk calendar (Pythia, `pythia`) | **best** | The next 14 days of news, and what the bots do | `fixture.json`, `events.json`, `../home.json` |
|  | The bots' day (Kairos, `kairos`) | also | A 24-hour ring: what the bots do now | `fixture.json`, `../odeon/trades.json`, `../home.json` |
|  | Market radar (Oracle, `oracle`) | also | The market, live | bundled fixture / its own files |
|  | Market mood (Pantheon, `pantheon`) | also | Rates, liquidity and fear | `jarvis.json`, `pantheon.json`, `fixture.json` |
|  | News days (Pheme, `pheme`) | folded into Risk calendar | Releases, and NQ's past moves on them | `fixture.json`, `stats.json` |
|  | Session clock (Chronos, `chronos`) | folded into The bots' day | Time and the trading sessions | `../odeon/trades.json`, `fixture.json` |

Also shown here (they live in another hub): Bots right now (`nq`), Risk guard (`aegis`), Day and week plan (`planner`).

### Bots & Evals (`hub/?h=bots`): Are my bots on, and how is each eval doing?

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Bots now | Bots right now (NQ, `nq`) | **best** | Is each bot on, drawdown left, the last trades | `../home.json`, `fixture.json`, `howto.json` |
|  | Full NQ dashboard (Dashboard, `today`) | also | The full NQ dashboard: today, trades, results | data.json, home.json, live.json (the bot feeds) |
|  | What to fix (Argus, `argus`) | also | The hundred eyes: problems worth fixing | bundled fixture / its own files |
| Risk | Risk guard (Aegis, `aegis`) | **best** | Drawdown left, and when to stop for the day | `fixture.json`, `../home.json`, `../ledger/rules.json` |
|  | Rules and risk calculator (Pnyx, `pnyx`) | also | Prop-firm rules, and stop to micros | `fixture.json`, `../home.json`, `../ledger/rules.json` |
|  | Size your eval (Labyrinth, `labyrinth`) | also | The risk maze: how big to trade | `../odeon/trades.json`, `../home.json`, `fixture.json` |
|  | Account health (Demeter, `demeter`) | folded into Risk guard | Drawdown dials and payout rules | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../plutus/roadmap.json` |
| Pass odds | Pass odds (Fates, `fates`) | **best** | The odds each eval passes | `fixture.json` |
|  | Eval simulator (Moirai, `moirai`) | also | Pass, bust and time of an eval, simulated | `fixture.json`, `../ledger/rules.json` |
| Trades | Trade replays (Odeon, `odeon`) | **best** | Every trade, replayed in 3D | `trades.json` |
|  | Losing trades (Nemesis, `nemesis`) | also | What went wrong, trade by trade | `../odeon/trades.json`, `../home.json`, `fixture.json` |
|  | P&L calendar (Kronos, `kronos`) | also | Daily P&L, best weekday and hour | `fixture.json`, `../odeon/trades.json` |
| Review | Weekly review (Apollo, `apollo`) | **best** | The week's review and one rule for next week | `fixture.json`, `../odeon/trades.json` |
|  | Trade journal (Mnemosyne, `journal`) | also | A 10-second journal: what your habits cost | `../odeon/trades.json`, `fixture.json`, `mnemosyne-journal.json` |
|  | Discipline score (Kratos, `kratos`) | also | A 0-100 score a day: plan, stop, size, hours | `fixture.json`, `../odeon/trades.json` |
|  | Your week in 60 seconds (Epilogue, `epilogue`) | folded into Weekly review | The Sunday review | `fixture.json`, `../home.json`, `../odeon/trades.json`, `../money/index.json` |

Also shown here (they live in another hub): Risk calendar (`pythia`), Your real money (`ledger`).

### Kalshi (`hub/?h=kalshi`): How is the Kalshi bot doing, and where is an edge?

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| The bot | Kalshi bot (Kalshi, `kalshi`) | **best** | Balance, open bets and P&L, from your PC | `../kalshicity/forward.json`, `../kalshicity/scan.json` |
| Edges | Kalshi desk (Dionysus, `dionysus`) | **best** | Guard, what-if and scan (suggestions only) | `fixture.json`, `../kalshicity/edges.json`, `../kalshicity/whatif.json` |
|  | Prediction-market picks (Sibyl, `sibyl`) | folded into Kalshi desk | Edges after fees, paper picks only | `fixture.json`, `../money/sibyl.json`, `../money/sibyl_forward.json`, `../kalshicity/suggestions.json`, `suggestions_fixture.json` |

Also shown here (they live in another hub): Kalshi City (`kalshicity`), Fortune wheel (`tyche`).

### My Money (`hub/?h=money`): What have I really made and spent, and what is next?

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Real money | Your real money (Ledger, `ledger`) | **best** | Fees, payouts and net profit | `../home.json`, `rules.json`, `fixture.json`, `../plutus/roadmap.json`, `ledger-${S.model.today}.json` |
|  | Balance check (Harmonia, `harmonia`) | also | What leans on the NQ bots, and what is left | `fixture.json`, `../home.json`, `../money/index.json` |
|  | Money, wrapped (Hermes, `hermes`) | folded into Your real money | Your money story, wrapped | `jarvis.json`, `wrapped.json`, `demo.json`, `../fates/jarvis.json`, `../datacity/discoveries.json` |
| Plan and payouts | 12-month money plan (Hera, `hera`) | **best** | Payouts, and what to buy next | `fixture.json`, `../plutus/roadmap.json` |
|  | Prop-firm planner (Chrysos, `chrysos`) | also | Fees against payouts, break-even | `fixture.json`, `../money/chrysos.json` |
|  | Money goals (Argo, `argo`) | also | Your goals as islands, honest ETAs | `fixture.json`, `../home.json`, `../ledger/rules.json` |
|  | Accounts and payouts (Plutus, `plutus`) | folded into 12-month money plan | The money plan: accounts and payouts | `../data.json`, `jarvis.json`, `plans.json` |
| Household | Household money (Oikos, `oikos`) | **best** | Leaks, tax set-aside and buckets | `fixture.json`, `../money/oikos.json`, `../ledger/rules.json`, `oikos-${S.today}.json` |
| Ideas and deals | Money machine (Mint, `mint`) | **best** | Five money streams, one honest estimate | `fixture.json`, `../money/index.json` |
|  | Deals and codes (Mercury, `mercury`) | also | Sales, discount codes, free resets | `fixture.json`, `../money/mercury.json` |
|  | Spreads and funding (Arbiter, `arbiter`) | also | Paper-only spreads: net yearly return | `fixture.json`, `../money/arbiter.json` |

Also shown here (they live in another hub): Kalshi bot (`kalshi`), Mint City (`mintcity`).

### Plan & Day (`hub/?h=plan`): What is on my calendar and my list?

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Calendar and tasks | Day and week plan (Planner, `planner`) | **best** | Sessions, shifts, tasks, habits and notes | `../pythia/events.json`, `../home.json`, `fixture.json` |
|  | Your notes as a brain (Mind, `mind`) | also | Your vault as a living 3D brain | bundled fixture / its own files |
| Habits and progress | Daily rules quiz (Lyceum, `lyceum`) | **best** | Quiz, ranks and the habits that cost money | `fixture.json`, `../odeon/trades.json`, `../home.json` |
|  | Trophy hall (Nike, `nike`) | also | Milestones and wins from real numbers | `fixture.json`, `../home.json`, `../ledger/rules.json`, `../odeon/trades.json`, `../kalshicity/edges.json` |
|  | Ranks and XP (Arena, `arena`) | folded into Daily rules quiz | XP for discipline | `rules.json`, `events.json` |

Also shown here (they live in another hub): Risk calendar (`pythia`), Discipline score (`kratos`).

### Research (`hub/?h=research`): What have we tested, and what works?

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Library | Everything we tested (Archive, `archive`) | **best** | The searchable library of every test | `fixture.json`, `index.json` |
|  | Research in plain words (Clio, `clio`) | also | Every study, explained | `fixture.json`, `../writeups/index.json`, `../data.json` |
|  | Strategy library (Athena, `athena`) | also | The strategy, the rules and a quiz | `jarvis.json`, `library.json`, `drills.json` |
| Strategy search | Tune the dials (Hephaestus, `hephaestus`) | **best** | Try the settings and see the result | `data.json`, `fixture.json` |
|  | Strategy forge (Prometheus, `prometheus`) | also | Strategies tested in the forge | `jarvis.json`, `forge.json` |
|  | Strategy search (Daphne, `tree`) | also | The strategy tree search | `jarvis.json`, `tree.json` |
| Data | Data health (Observatory, `observatory`) | **best** | Data health and research evidence | bundled fixture / its own files |
|  | Every data table (Pinakes, `pinakes`) | also | Browse and query every table OLYMPUS keeps | `catalog.json`, `fixture.json`, `pinakes-views.json` |

Also shown here (they live in another hub): Strategy duels (`colosseum`), Data City (`datacity`), ATLAS City (`atlascity`).

### Jarvis (`hub/?h=jarvis`): Ask anything. Who works for me?

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Ask | Jarvis (Jarvis, `jarvis`) | **best** | Ask anything: your home screen and the orb | its own files / bundled fixture |
|  | Link ChatGPT (Bridge, `bridge`) | also | 3 steps to link ChatGPT, and live job status | `status.json`, `jobs.json`, `deliveries.json` |
| Your AI team | Your AI workers (Ergasterion, `ergasterion`) | **best** | Every AI worker, what it does and learns | `builders.json`, `fixture.json`, `queue.json`, `../home.json`, `../money/index.json`, ... |
|  | Meet your workers (Symposium, `symposium`) | folded into Your AI workers | Everyone who works for you; talk to them | `fixture.json` |

Also shown here (they live in another hub): Your notes as a brain (`mind`).

### Worlds (`hub/?h=worlds`): The 3D places (optional, for fun)

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Most visited | The city (Polis, `polis`) | **best** | Every app a building under the real sky | `../olympus/polis.json`, `../olympus/polis-demo.json`, `fixture.json`, `../home.json`, `../kalshi.json`, ... |
|  | Cities and Hellas (Cities, `cities`) | also | Athens and the city islands of your research | `fixture.json` |
|  | Strategy duels (Colosseum, `colosseum`) | also | Strategies fight on real stored numbers | `extra.json`, `fixture.json`, `../archive/index.json`, `../home.json` |
| Numbers as places | Kalshi City (Kalshi City, `kalshicity`) | **best** | The Kalshi bot's edges as a night city | `fixture.json`, `edges.json`, `learning_log.json`, `hypotheses.json`, `learned.json` |
|  | Mint City (Mint City, `mintcity`) | also | The money machines as a marble city | `fixture.json`, `../money/index.json` |
|  | Data City (Data City, `datacity`) | also | Every combo tested, as a city | `fixture.json`, `city.json`, `jarvis.json`, `../data.json`, `../pantheon/pantheon.json` |
|  | ATLAS City (ATLAS City, `atlascity`) | also | ATLAS's three strategies as a city | its own files / bundled fixture |
|  | Fortune wheel (Tyche, `tyche`) | folded into Kalshi City | The Kalshi bets as a 3D wheel | bundled fixture / its own files |

Also shown here (they live in another hub): Trade replays (`odeon`), Meet your workers (`symposium`).

### Settings & Help (`hub/?h=settings`): Change the look, start the PC, find any app

| Tab (job) | App (id) | Role | Answers | Data it reads |
|---|---|---|---|---|
| Settings | Settings (Settings, `settings`) | **best** | Look, voice, storage and the tour | bundled fixture / its own files |
|  | Start the bot on this PC (PC, `pc`) | also | The steps to start the bot on your PC | its own files / bundled fixture |
| Help and every app | The old map of apps (Atlas, `atlas`) | **best** | Every OLYMPUS app by the old districts | bundled fixture / its own files |
| Workshop | Agora Gallery (Agora Gallery, `gallery`) | **best** | Every 3D shape on a turning pedestal | `fixture.json` |
|  | Design Lab (Design Lab, `agora-lab`) | also | The look every app shares | its own files / bundled fixture |
|  | Places Lab (Places Lab, `env-lab`) | also | Marble, stone, bronze, golden light | its own files / bundled fixture |
|  | Effects Lab (Effects Lab, `fx-lab`) | also | Every light, sky, sea, fire and burst | its own files / bundled fixture |
|  | Sound Lab (Sound Lab, `sfx-lab`) | also | Every sound, place and harp tune | its own files / bundled fixture |
|  | People Lab (People Lab, `people-lab`) | also | Every character, faces and poses | its own files / bundled fixture |
|  | Greek Look Kit (Greek Look Kit, `polis-lab`) | also | Greek key, columns, pottery, coins | its own files / bundled fixture |
|  | Polis Life Lab (Polis Life Lab, `polis-life-lab`) | also | People walking the city | its own files / bundled fixture |
|  | Render Lab (Render Lab, `render-lab`) | also | The 3D render core on test | its own files / bundled fixture |


## Where it lives (code)

| Piece | File | Test |
|---|---|---|
| The hubs, their tabs, every app's hub / tab / fold, the search | `tools/web_public/olympus/gate-catalog.js` (v2: `hubs` = `districts`, `layout(hub)`, `crumbOf(app)`, `hub(id)`, `hubOf(app)`, `mixOf(app)`) | `tests/test_hubs.py` (b), `tests/test_gate_page.py` (b) |
| The live one-line status per hub (pure + two loaders) | `tools/web_public/olympus/hub-status.js` (`window.OLYMPUS_HUB_STATUS`) | `tests/test_hubs.py` (b, node) |
| The home (command center) | `tools/web_public/gate/` (`index.html`, `gate.js`, `gate.css`) | `tests/test_gate_page.py`, `tests/test_live_link.py` (8, 9) |
| The hub page | `tools/web_public/hub/` (`index.html`, `hub.js`, `hub.css`, `icon.svg`) | `tests/test_hubs.py` (c) |
| Breadcrumbs + Go to (hubs first) | `tools/web_public/olympus/gate-nav.js` (v=g2); `olympus/agora-ui.js` (v=2) adds it to every AGORA app | `tests/test_gate_page.py` (c), `tests/test_hubs.py` (c) |
| Screenshots at 390 x 844 | `docs/shots/ia_v2/` | read back by eye |

**Theme mix.** The theme engine's per-district "mix" should key on the hub: the catalog's `districts` are now the nine hubs (`C.mixOf(appId)` = the app's
hub id), the hub page sets `<html data-oly-district="<hub>">`, and each home tile carries `data-hub`. Each hub keeps a `legacy` field (trading / money /
life / worlds) for a theme that still knows only the old four. All new CSS uses `--ag-*` tokens only (fallback values at zero specificity, `:where(:root)`).

**Wiring the lead does** (agents never edit these): `'hub/'` in `OTHER_APPS` of `tools/web_public/sw.js`; `"hub"` in the copy tuple of
`tools/build_web_dashboard.py` (next to `"gate"`), then bump the workers. Optional, to finish the job beyond the front door: the Jarvis switcher and the
Zenith launcher still group by `jarvis/apps.js` groups (Trading / Money / Life); regrouping them by `OLYMPUS_GATE.hubOf(id)` would make every list say the same nine hubs.
