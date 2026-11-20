# Olympus app audit (2026-11-20)

Every app scored 1-5 on NEED (does a prop-eval futures trader on an iPhone need it) and LOOK (looks good / works on a phone). Scan: 390x844 mobile Chromium, 2.5 s, headless software rendering.
Verdict: KEEP (main) and KEEP stay visible; MERGE INTO <id> and ARCHIVE leave doors/launcher but stay reachable from More / Archive (files untouched).
Result: 24 visible apps of 76 (plus Jarvis, Gate, Hub which are not in the table). Longtask ms is inflated by software WebGL in headless, so treat it as relative only.

| app id | name | door | NEED | LOOK | verdict | why | errors/sideways/heavy flags |
|---|---|---|---|---|---|---|---|
| `aegis` | Aegis | zeus | 5 | 4 | KEEP (main) | Drawdown left and full-stop what-if | - |
| `board` | Board | zeus | 5 | 4 | KEEP (main) | Accounts, events, owner notes in one place | - |
| `business` | Business | money | 5 | 4 | KEEP (main) | Accounts, taxes, fleet plan, side work hub | 404:business/business.json |
| `ledger` | Ledger | money | 5 | 4 | KEEP (main) | Real fees, payouts, net profit | - |
| `nq` | NQ bots | zeus | 5 | 4 | KEEP (main) | Bots live status and drawdown left | - |
| `trading` | Trading | zeus | 5 | 4 | KEEP (main) | Trades, calendar, stats, payout rules | - |
| `zenith` | Zenith | zeus | 5 | 4 | KEEP (main) | Full bot dashboard, the home screen | - |
| `chrysos` | Chrysos | money | 4 | 4 | KEEP | Fleet fees vs payouts break-even | - |
| `compass` | Compass | more | 4 | 4 | KEEP | Next best actions; absorbs Stoa, Inbox, Hestia | - |
| `demeter` | Demeter | zeus | 4 | 4 | KEEP | Account health, drawdown dials, payout rules | - |
| `fates` | Fates | zeus | 4 | 4 | KEEP | Eval pass odds; absorbs Moirai | - |
| `helios` | Helios | more | 4 | 4 | KEEP | Morning brief; absorbs Forum, Delphi, Pythia | - |
| `hera` | Hera | money | 4 | 4 | KEEP | 12-month payout plan; absorbs Plutus | - |
| `jarvis` | Jarvis | more | 4 | 3 | KEEP | Assistant; 2.3MB JS, heavy | JS 2338KB; HTML 286KB; blur x7; anim x32; no agora.css |
| `journal` | Mnemosyne journal | zeus | 4 | 4 | KEEP | 10-second journal; absorbs Kratos, Nemesis, Apollo | blur x8; anim x32 |
| `kronos` | Kronos | zeus | 4 | 4 | KEEP | Daily P&L calendar, best weekday | - |
| `mercury` | Mercury | money | 4 | 4 | KEEP | Prop-firm sales, codes, free resets | - |
| `oikos` | Oikos | money | 4 | 4 | KEEP | Household, tax set-aside, leaks | - |
| `planner` | Planner | more | 4 | 4 | KEEP | His day and week, session windows | - |
| `pnyx` | Pnyx | zeus | 4 | 4 | KEEP | Prop rules and micros size calculator | - |
| `atlas` | Atlas | more | 3 | 4 | KEEP | Directory of everything; the More/Archive entry | no agora.css |
| `clio` | Clio | more | 3 | 4 | KEEP | Research library in plain words; absorbs Archive | 404:writeups/index.json |
| `dionysus` | Dionysus | kalshi | 3 | 4 | KEEP | Kalshi desk; absorbs Sibyl, Kalshi City | - |
| `gate` | Gate | hub | 3 | 4 | KEEP | Entry with four door tiles | - |
| `hub` | Hub | hub | 3 | 4 | KEEP | Doors, zeus landing, help pages | - |
| `kalshi` | Kalshi | kalshi | 3 | 3 | KEEP | Kalshi bot status; paused but live-fed | 404:kalshi/kit.json,kalshicity/forward.json,kalshicity/scan.json; no agora.css |
| `settings` | Settings | more | 3 | 4 | KEEP | Look, storage, tour; needed utility | - |
| `pc` | PC | more | 2 | 3 | KEEP | PC bot connect page; not in registry | no agora.css |
| `apollo` | Apollo | zeus | 3 | 4 | MERGE INTO journal | Weekly review; fold into journal | - |
| `ares` | Ares | zeus | 3 | 3 | MERGE INTO nq | GO/WAIT/HALT; NQ status covers | longtask 3040ms |
| `delphi` | Delphi | zeus | 3 | 4 | MERGE INTO helios | Plan/go-no-go briefing; duplicate | - |
| `epilogue` | Epilogue | zeus | 3 | 4 | MERGE INTO journal | Sunday review; duplicates Apollo | - |
| `forum` | Forum | zeus | 3 | 3 | MERGE INTO helios | Morning briefing duplicate of Helios | - |
| `kratos` | Kratos | zeus | 3 | 4 | MERGE INTO journal | Discipline score; journal habit costs | - |
| `labyrinth` | Labyrinth | zeus | 3 | 3 | MERGE INTO pnyx | Eval sizing; Pnyx calculator covers it | - |
| `moirai` | Moirai | zeus | 3 | 3 | MERGE INTO fates | Pass/bust simulator, same job as Fates | - |
| `nemesis` | Nemesis | zeus | 3 | 3 | MERGE INTO journal | Losing trades review; journal covers | longtask 3054ms |
| `odeon` | Odeon | zeus | 3 | 2 | MERGE INTO trading | 3D trade replay; trading page has trades | - |
| `plutus` | Plutus | money | 3 | 3 | MERGE INTO hera | Accounts and payouts plan; duplicate of Hera/Ledger | longtask 3502ms |
| `pythia` | Pythia | zeus | 3 | 3 | MERGE INTO helios | Risk calendar 14 days; useful inside brief | - |
| `why` | Why | zeus | 3 | 4 | MERGE INTO trading | Win/loss reasons per bot; fits stats | - |
| `archive` | Archive | more | 2 | 3 | MERGE INTO clio | Searchable tests library; same as Clio | - |
| `argo` | Argo | money | 2 | 3 | MERGE INTO hera | Money goals as islands; Hera plan covers | - |
| `chronos` | Chronos | zeus | 2 | 3 | MERGE INTO nq | Session clock; duplicate of planner/nq | - |
| `harmonia` | Harmonia | money | 2 | 3 | MERGE INTO business | Income balance; duplicates Business | - |
| `hestia` | Hestia | more | 2 | 4 | MERGE INTO compass | Today-at-home actions; duplicate | - |
| `inbox` | Inbox | more | 2 | 3 | MERGE INTO compass | Needs-a-look list; duplicate | anim x23 |
| `kairos` | Kairos | zeus | 2 | 3 | MERGE INTO nq | Bots day timeline; NQ page covers | - |
| `mint` | Mint | money | 2 | 3 | MERGE INTO business | Five streams estimate; duplicates Business | - |
| `sibyl` | Sibyl | kalshi | 2 | 3 | MERGE INTO dionysus | Kalshi paper picks; paused | - |
| `stoa` | Stoa | more | 2 | 3 | MERGE INTO compass | What needs you; duplicates Compass | 404:alerts.json |
| `kalshicity` | Kalshi City | kalshi | 1 | 2 | MERGE INTO dionysus | Night-city edges; gimmick, heavy blur | blur x12 |
| `agency` | Agency | money | 2 | 3 | ARCHIVE | Website agency leads; side work, rarely used | 404:agency/my_leads.json |
| `arbiter` | Arbiter | money | 2 | 3 | ARCHIVE | Paper spreads/funding; off-strategy lab | - |
| `argus` | Argus | zeus | 2 | 3 | ARCHIVE | What-to-fix list; heavy, dev-facing | 404:cronos/status.json; longtask 3331ms |
| `athena` | Athena | more | 2 | 3 | ARCHIVE | Strategy/rules quiz library | - |
| `hermes` | Hermes | money | 2 | 3 | ARCHIVE | Money Wrapped story; fun, not needed | 404:datacity/discoveries.json |
| `lyceum` | Lyceum | more | 2 | 3 | ARCHIVE | Daily rules quiz; duplicates Athena | - |
| `oracle` | Oracle | zeus | 2 | 3 | ARCHIVE | Market radar; heavy, duplicates Pantheon | longtask 3520ms |
| `pantheon` | Pantheon | zeus | 2 | 3 | ARCHIVE | Rates/liquidity data gods; reference only | longtask 3515ms |
| `pheme` | Pheme | zeus | 2 | 3 | ARCHIVE | Releases word-on-street; low value | - |
| `arena` | Arena | more | 1 | 3 | ARCHIVE | XP ranks; gamification | longtask 3518ms |
| `atlascity` | Atlas City | more | 1 | 3 | ARCHIVE | Atlas variant; duplicate of Atlas | no agora.css |
| `bridge` | Bridge | more | 1 | 3 | ARCHIVE | ChatGPT link; 51KB inline, niche | HTML 51KB; no agora.css |
| `cities` | Cities | more | 1 | 2 | ARCHIVE | City islands 3D world, 800KB JS | JS 809KB; blur x7 |
| `colosseum` | Colosseum | more | 1 | 3 | ARCHIVE | Strategies fight; game-like lab | - |
| `datacity` | Data City | more | 1 | 2 | ARCHIVE | Tested combos as city; lab, heavy | JS 464KB; blur x13 |
| `ergasterion` | Ergasterion | more | 1 | 3 | ARCHIVE | AI worker list; dev-facing, 250KB JS | 404:cronos/status.json |
| `gallery` | Agora Gallery | more | 1 | 2 | ARCHIVE | Showcase of 3D shapes; demo page | - |
| `hephaestus` | Hephaestus | more | 1 | 3 | ARCHIVE | Tune dials; lab | - |
| `herald` | Herald | more | 1 | 3 | ARCHIVE | Daily paper of who built what | - |
| `mind` | Mind | more | 1 | 2 | ARCHIVE | 3D brain of vault; gimmick, 460KB JS | JS 462KB; blur x10 |
| `mintcity` | Mint City | money | 1 | 2 | ARCHIVE | Marble city of Mint; 3D gimmick | longtask 3377ms |
| `nike` | Nike | more | 1 | 2 | ARCHIVE | Trophy hall; 44 animations, 9 canvases | anim x44; canvas x9 |
| `observatory` | Observatory | more | 1 | 3 | ARCHIVE | Data health evidence; lab page | 404:kalshicity/scan.json?observed=5983811 |
| `pinakes` | Pinakes | more | 1 | 3 | ARCHIVE | Table catalogue/query; dev tool | - |
| `polis` | Polis | more | 1 | 2 | ARCHIVE | App city 3D; duplicates Atlas | 404:polis/sky.json |
| `prometheus` | Prometheus | more | 1 | 3 | ARCHIVE | Strategies tested forge; lab | - |
| `symposium` | Symposium | more | 1 | 3 | ARCHIVE | Meet AI workers; gimmick | 404:cronos/status.json |
| `tree` | Daphne | more | 1 | 2 | ARCHIVE | Strategy tree search; 14 canvases, lab | canvas x14 |
| `tyche` | Tyche | kalshi | 1 | 2 | ARCHIVE | 3D fortune wheel; heaviest page | blur x14; longtask 4925ms |

## Proposed ARCHIVE list (ids)

apollo, ares, delphi, epilogue, forum, kratos, labyrinth, moirai, nemesis, odeon, plutus, pythia, why, archive, argo, chronos, harmonia, hestia, inbox, kairos, mint, sibyl, stoa, kalshicity, agency, arbiter, argus, athena, hermes, lyceum, oracle, pantheon, pheme, arena, atlascity, bridge, cities, colosseum, datacity, ergasterion, gallery, hephaestus, herald, mind, mintcity, nike, observatory, pinakes, polis, prometheus, symposium, tree, tyche

## Proposed visible list per door

- zeus: zenith, nq, board, trading, aegis, pnyx, demeter, fates, kronos, journal
- money: ledger, business, hera, oikos, chrysos, mercury
- kalshi: kalshi, dionysus
- more: compass, planner, helios, jarvis, clio, settings, atlas

## Real bugs found

- Page errors / console errors: none in any of the 80 pages scanned.
- Sideways scroll: none (0 px on every page).
- Non-data 404s (files the page asks for that the server does not have; may be live-data files published only on the real site):
  - `agency`: agency/my_leads.json
  - `argus`: cronos/status.json
  - `business`: business/business.json
  - `clio`: writeups/index.json
  - `ergasterion`: cronos/status.json
  - `hermes`: datacity/discoveries.json
  - `kalshi`: kalshi/kit.json
  - `kalshi`: kalshicity/forward.json
  - `kalshi`: kalshicity/scan.json
  - `observatory`: kalshicity/scan.json?observed=5983811
  - `polis`: polis/sky.json
  - `stoa`: alerts.json
  - `symposium`: cronos/status.json
- Heavy pages: jarvis (2.3 MB JS, 286 KB HTML), cities (809 KB JS), datacity, mind (460 KB JS) and tyche/kalshicity/datacity/mind/journal (7-14 backdrop-filter blurs) are the phone-slowdown risks; all but jarvis are in the ARCHIVE list.
- Not in the 76-app table but have index.html: `jarvis`, `gate`, `hub`, `atlascity`, `pc`.

## What was shipped (night-revamp-main, the lead's call on the proposals above)
Archived (folded under "Archive" at the end of their door, `olympus/doors.js` ARCHIVE; still in their door, still found by search, every URL works): 45 apps.
Kept visible, beyond the proposal: `why` (new, owner's win/loss page), `agency` (side income), `kalshicity` + `sibyl` + `tyche` (Kalshi is this week's focus,
and the Kalshi door needs its 5 shortcuts), `inbox` (alerts), `cities` (Olympus World, the More door's first shortcut, another helper is improving it tonight).
Visible now: ZEUS 11 (zenith, nq, board, why, trading, aegis, pnyx, demeter, fates, kronos, journal) · Money 7 (business, ledger, hera, chrysos, oikos, agency,
mercury) · Kalshi 5 · More 8 (compass, helios, inbox, planner, settings, atlas, cities, clio) = 31 of 76.
Fixed from the bug list: the 16 apps with no `icon.svg` (404 on the hub pages) got a monogram icon; `why` added to the Gate's search catalog.
Left: the data 404s (`business/business.json`, `cronos/status.json`, ...) are files the publisher writes; not checked on the live site tonight.
