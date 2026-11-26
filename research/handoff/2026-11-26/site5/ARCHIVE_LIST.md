# Archive list (day-site5 C1, 2026-11-26)

Lead: "Olympus has ~80 apps; list the ones nobody opens (no links in, retired, duplicates) and move them to an Archive door (no deletions)."

**Census:** `inbound.cjs` (this folder) crawls every .html/.js/.json/.css under tools/web_public and counts, for each of the 91 catalog apps, the files outside
the app's own folder that point at it. Not counted as "someone opens it": registry files that list every app (catalog, apps lists, sw.js, nav / search /
intro / help / doors), data files (people.json, pinakes catalog, cities datasets, search index, athena library, mind starter pack, herald editions) and pages of
apps that are already retired. 91 apps = 28 already retired + 63 live; after this change 52 live (Home's A to Z: 63 -> 52 rows).

**What "archived" does** (olympus/gate-catalog.js ARCHIVED / ARCHIVE_INTO): off Home search, A to Z and the arena lists, like retired apps; listed on the
**Archive door** `hub/arena.html?a=archive` with where its content lives now ("Now on: ..."); a chip to the door on every arena page. Unlike retired apps it
does **not** redirect: the page it was folded into still links it, every old URL opens as before. Typing its words in search lands on the page that holds
its content now ("weekly review" -> Journal, "size your eval" -> Rules and risk calculator). Nothing deleted, no file moved.

## Archived now (11)

| App | Live links in (outside registries) | Why | Its content lives on |
|---|---|---|---|
| Market morning notes (`forum`) | 1: `helios/index.html` | merged into the Morning briefing (helios) on 2026-11-21 (OLYMPUS_MAP "Merged earlier"); catalog fold = helios | `helios` |
| Your week in 60 seconds (`epilogue`) | 1: `journal/index.html` | merged into the Journal ("the week in 60 seconds"); catalog fold = apollo, itself folded | `journal` |
| Weekly review (`apollo`) | 1: `journal/index.html` | merged into the Journal ("the week review") | `journal` |
| Discipline score (`kratos`) | 1: `journal/index.html` | merged into the Journal ("habits and what they cost") | `journal` |
| Losing trades (`nemesis`) | 1: `journal/index.html` | merged into the Journal ("losing trades") | `journal` |
| Size your eval (`labyrinth`) | 2: `fates/index.html`, `pnyx/index.html` | merged into Rules and size calculator (pnyx, "eval sizing") | `pnyx` |
| Why we win and lose (`why`) | 2: `trading/index.html`, `trading/trading.js` | merged into Trading (#whyCard) | `trading` |
| Prediction-market picks (`sibyl`) | 3: `dionysus/dionysuscore.js`, `dionysus/index.html`, `kalshi/index.html` | merged into the Kalshi desk (dionysus, paper picks); catalog fold = dionysus | `dionysus` |
| Account health (`demeter`) | 1: `olympus/pulse.js` | duplicate of the Risk guard (aegis): catalog fold = aegis; its only live link is olympus/pulse.js (a status line) | `aegis` |
| Strategy library (`athena`) | 0 | no live page links it (only data / registry files); static library.json, no live data | `archive` |
| Strategy duels (`colosseum`) | 0 | no live page links it; reads the research archive (archive/index.json), no live data | `archive` |

## Already retired (28, unchanged)

Redirect to their replacement (`?stay=1` keeps the old page); the Archive door lists them too, opened with `?stay=1`:
`arbiter`, `arena`, `argo`, `atlascity`, `bridge`, `chronos`, `datacity`, `delphi`, `ergasterion`, `gallery`, `harmonia`, `hephaestus`, `herald`, `hermes`, `hestia`, `kairos`, `kalshicity`, `lyceum`, `mind`, `mint`, `mintcity`, `nike`, `observatory`, `pheme`, `plutus`, `polis`, `stoa`, `symposium`

## Looked at and KEPT (conservative: real inbound links or live data)

| App | Live links in | Why it stays |
|---|---|---|
| P&L calendar (`kronos`) | 0 | 0 live links, but it reads the real trades (odeon/trades.json): the only P&L calendar. Candidate if Trading gets a calendar. |
| Prop-firm planner (`chrysos`) | 0 | 0 live links; reads money/chrysos.json written by a job (prop-firm fees vs payouts). Candidate for the next pass. |
| Deals and codes (`mercury`) | 0 | 0 live links; reads money/mercury.json written by a job (deals, codes). Candidate for the next pass. |
| Fortune wheel (`tyche`) | 1: `kalshi/kalshi.js` | linked from the Kalshi page (kalshi/kalshi.js) |
| Eval simulator (`moirai`) | 1: `fates/index.html` | linked from Pass odds (fates) |
| Household money (`oikos`) | 1: `business/index.html` | linked from All my businesses |
| Every data table (`pinakes`) | 1: `clio/index.html` | linked from Clio |
| Rules and risk calculator (`pnyx`) | 2: `business/index.html`, `labyrinth/index.html` | linked from All my businesses + absorbs Labyrinth |
| Strategy forge (`prometheus`) | 2: `jarvis/modes.js`, `olympus/people-core.js` | linked from Jarvis modes (already off the Home list in gate.js) |

## Live links in, every live app (for the record)

| App | arena | live links in |
|---|---|---|
| `kronos` | nq | 0 |
| `chrysos` | money | 0 |
| `mercury` | money | 0 |
| `athena` | data | 0 |
| `colosseum` | data | 0 |
| `forum` | nq | 1 |
| `demeter` | nq | 1 |
| `moirai` | nq | 1 |
| `nemesis` | nq | 1 |
| `apollo` | nq | 1 |
| `kratos` | nq | 1 |
| `epilogue` | nq | 1 |
| `oikos` | money | 1 |
| `pinakes` | data | 1 |
| `tyche` | kalshi | 1 |
| `compass` | jarvis | 2 |
| `pnyx` | nq | 2 |
| `labyrinth` | nq | 2 |
| `why` | nq | 2 |
| `hera` | money | 2 |
| `prometheus` | data | 2 |
| `tree` | data | 2 |
| `ares` | nq | 3 |
| `oracle` | nq | 3 |
| `aegis` | nq | 3 |
| `fates` | nq | 3 |
| `dionysus` | kalshi | 3 |
| `sibyl` | kalshi | 3 |
| `pc` | else | 3 |
| `pantheon` | nq | 4 |
| `argus` | nq | 4 |
| `helios` | jarvis | 6 |
| `warroom` | nq | 6 |
| `today` | nq | 6 |
| `journal` | nq | 6 |
| `widget` | money | 6 |
| `settings` | else | 6 |
| `archive` | data | 8 |
| `inbox` | jarvis | 9 |
| `brain` | nq | 9 |
| `planner` | money | 9 |
| `clio` | data | 9 |
| `agency` | agency | 15 |
| `pillars` | nq | 16 |
| `cities` | data | 16 |
| `pythia` | nq | 17 |
| `atlas` | else | 19 |
| `board` | nq | 21 |
| `kalshi` | kalshi | 23 |
| `ledger` | money | 26 |
| `trading` | nq | 28 |
| `odeon` | nq | 45 |
| `nq` | nq | 49 |
| `business` | money | 57 |
| `jarvis` | jarvis | 174 |
| `agora-lab` | else | 266 |
| `env-lab` | else | 266 |
| `fx-lab` | else | 266 |
| `sfx-lab` | else | 266 |
| `people-lab` | else | 266 |
| `polis-lab` | else | 266 |
| `polis-life-lab` | else | 266 |
| `render-lab` | else | 266 |
