# NAV team (day-manual), 2026-11-20: getting anywhere in Olympus

Owner: "Launch a giant team making Olympus as a whole better." NAV = finding things fast on the iPhone.

| What | Before | After |
|---|---|---|
| Home search / every Go to sheet: 67 real phrasings ("how much can I lose", "is atlas in a trade", "stop the bot", "kalshi today") | **13/67** open the right place; **42 find nothing** (every typed word had to match: "how", "much", "is", "a" killed the search) | **67/67** (tests.test_nav_search). Little words dropped, owner words mapped (lose -> room, paid -> payout, notifications -> alerts), "what does X mean" -> the manual's line for X, a fallback that keeps the words it knows |
| The owner's 10 most-checked things | 1 of 10 reachable by a plain question | 10 of 10: one search, one tap (table below) |
| Hub pages under a light look (Ivory, Stocks Light) | Help, Your steps, ZEUS, Owner manual stayed dark (only Doors + hubs followed) | All follow the look from the first frame (tests.test_nav_pages: 10 page x look checks) |
| Top row of the hub pages | 4 different rows (Help: Home/ZEUS/All doors; Steps: Home/ZEUS/How do I; ...) | One rule: Home first, then ZEUS, then the other help pages (Help / Steps / Manual) |
| ZEUS account cards: room | not shown (the #1 thing he checks) | zeus.js draws "$1,025 room before the floor" (red under $500) as soon as zeus_core adds one field (ASKS.md #1) |
| Tests | - | nav_search 4/4 (node, 1 s, area olympus), nav_pages 13/13 (area board), help 35/35, zeus 52/52, owner_manual 29/29, steps 12/12 |

## The 10 things: what search opens now (from Home: tap the box, type, tap the first row = 2 taps)

| He types | Before (first result) | After |
|---|---|---|
| how much room do I have | nothing found | My accounts (MFFU view): $ left to each floor |
| what did I make today | nothing found | ZEUS: today's $ per account |
| is atlas in a trade | nothing found | MFFU view: Right now card (open trades, live $) |
| when is my next payout | nothing found | Payout coach (business/accounts.html#coach) |
| decisions waiting | nothing found | Board > Decide cards (#decide) |
| turn off alerts | nothing found | Jarvis > Allow notifications card (#pushCard) |
| kalshi today | nothing found | Kalshi > K8 card (#k8d) |
| tax pot | Taxes | Taxes (same) |
| emergency | nothing found | Owner manual > SOS (10 cards) |
| is the pc on | nothing found | ZEUS (PC reported X min ago / PC SILENT) |

Without search (door taps, measured from the page links): room 3 (ZEUS tile -> Doors#zeus -> Open ZEUS -> My accounts), today's $ 2,
open trade 2, payout 3, Decide 2 + scroll, alerts 3+, K8 2 + scroll, taxes 2, SOS 3 (More -> Help -> Owner manual), PC status 0 (Right now) / 2.
LEAD_WIRES #1 (the ZEUS tile straight to ZEUS) cuts 1 tap off 5 of them.

## All 67 phrasings, before -> after (first result)

| Phrase | Before | After |
|---|---|---|
| room | aegis/index.html | business/mffu.html |
| how much room do I have | nothing found | business/mffu.html |
| how much can I lose | nothing found | business/mffu.html |
| drawdown | aegis/index.html | business/mffu.html |
| max loss | aegis/index.html | business/mffu.html |
| how close am I to failing | nothing found | business/mffu.html |
| today's pnl | nq/index.html | hub/zeus.html |
| what did I make today | nothing found | hub/zeus.html |
| how much did zlarior make | nothing found | hub/zeus.html |
| money made today | nq/index.html | hub/zeus.html |
| is atlas in a trade | nothing found | business/mffu.html |
| am I in a trade | nothing found | business/mffu.html |
| open trade | kairos/index.html | business/mffu.html |
| open position | nothing found | business/mffu.html |
| payout | ledger/index.html | business/accounts.html#coach |
| when is my next payout | nothing found | business/accounts.html#coach |
| can I get paid | nothing found | business/accounts.html#coach |
| withdraw | ledger/index.html | business/accounts.html#coach |
| decide | nothing found | board/index.html#decide |
| decisions waiting | nothing found | board/index.html#decide |
| questions for me | nothing found | board/index.html#decide |
| notifications | inbox/ | jarvis/index.html#pushCard |
| turn off alerts | nothing found | jarvis/index.html#pushCard |
| phone alerts | nothing found | jarvis/index.html#pushCard |
| kalshi today | nothing found | kalshi/index.html#k8d |
| k8 | nothing found | kalshi/index.html#k8d |
| gold bets | nothing found | kalshi/index.html#k8d |
| taxes | business/taxes.html | business/taxes.html |
| tax pot | business/taxes.html | business/taxes.html |
| how much tax do I owe | nothing found | business/taxes.html |
| emergency | nothing found | hub/manual.html#sos |
| something is wrong | nothing found | hub/manual.html#sos |
| panic | nothing found | hub/manual.html#sos |
| ninjatrader disconnected | nothing found | hub/manual.html#sos |
| stop the bot | nq/index.html?howto=1 | hub/manual.html#sos-8 |
| kill switch | nothing found | hub/manual.html#sos-8 |
| flatten everything | nothing found | hub/manual.html#sos-8 |
| stop everything | nothing found | hub/manual.html#sos-8 |
| is the pc on | nothing found | hub/zeus.html |
| pc silent | nothing found | hub/zeus.html |
| bot down | nq/ | hub/zeus.html |
| is the bot running | nothing found | hub/zeus.html |
| manual | nothing found | hub/manual.html |
| glossary | nothing found | hub/manual.html |
| what does dll mean | nothing found | hub/manual.html#g-dll |
| what is a twin | nothing found | hub/manual.html#g-twin |
| what is room | nothing found | hub/manual.html#g-room |
| what does eod mean | nothing found | hub/manual.html#g-eod |
| my steps | nothing found | hub/steps.html |
| what do I need to do | nothing found | hub/steps.html |
| help | hub/help.html | hub/help.html |
| add an account | nothing found | hub/manual.html#sos-9 |
| eval passed | nothing found | hub/help.html#eval-passed |
| restart the bot | nq/index.html?howto=1 | hub/help.html#restart |
| update the pc | nothing found | hub/help.html#update |
| holidays | nothing found | hub/help.html#holidays |
| my accounts | business/accounts.html | business/accounts.html |
| zeus | hub/zeus.html | hub/zeus.html |
| board | board/ | board/ |
| kalshi | kalshi/ | kalshi/ |
| journal | journal/ | journal/ |
| news today | pheme/ | pheme/ |
| how many micros | pnyx/index.html | pnyx/index.html |
| change theme | gate/index.html#lookSec | gate/index.html#lookSec |
| dark mode | nothing found | gate/index.html#lookSec |
| all apps | gate/index.html#az | gate/index.html#az |
| weekly review | apollo/ | apollo/ |

## Files (all in the NAV slice)
- tools/web_public/olympus/gate-catalog.js: STOP / SYN / toksOf / tokIn, scored findActions, GLOSS + glossAction, findAll fallback,
  15 new actions (act-open, act-pcstatus, act-decide, act-alerts, act-k8, act-sos, act-kill, act-manual, act-steps, act-add, act-passed,
  act-restart, act-update, act-holidays, act-paid); act-payout -> the Payout coach, act-pnl -> ZEUS, act-dd -> MFFU view. Old pins kept
  (kalshi -> Kalshi bot first, theme, payout ids, micros, all apps, health -> Me, money -> Mint + Ledger).
- hub/help.html, steps.html, zeus.html, manual.html (+ manual.css m2, manual-sw.js m2): the OLYMPUS look, one top row.
- hub/zeus.js (v=7): the room line. tests: test_nav_search.py, test_nav_pages.py (new); test_help_page / test_zeus_hub: themes.js allowed.
- Shots: before/ and after/ (390x844, deviceScaleFactor 2, dark + light).

## Follow-up (lead, 15:03 UTC)

| What | Result |
|---|---|
| What's new page | `hub/whatsnew.html` + `whatsnew.json` (24 lines: today + this week, newest first) + `whatsnew.js`: each line = status (On the site now / Comes with the PC's next update / Needs your yes / Your step / Tested: nothing changed), the $ first where it is money, plain words, one "where to tap" button. "Needs me" filter (4 lines today). Linked from Help ("What's new") and the search ("what's new", "what changed"). No security details on the public page (the security report's holes are left out on purpose). |
| docs/OLYMPUS_MAP.md | Still generated (`tools/olympus_map_build.py`): + "What each door opens first, and what is folded under Archive" (29 open first, 48 archived, from doors.js ARCHIVE) + "Merged: where a folded app lives now" (Ares / Kairos / Chronos -> NQ cards, Odeon / Why -> Trading cards, Sibyl / Kalshi City -> Dionysus, Apollo / Epilogue / Kratos / Nemesis -> Journal, Pythia / Delphi / Forum -> Helios, Plutus / Argo -> Hera, Labyrinth -> Pnyx; every anchor checked). tests.test_olympus_map 7/7 (it was 6/7: the doc was stale). |
| Accessibility (own pass while day-a11y's list is pending) | axe-core 4.10.2 WCAG A + AA on help, steps, manual, zeus, doors, whatsnew, the bots hub, in the default look and Ivory: 0 violations, after fixing 3 contrast fails on ZEUS under Ivory (Passed chip, the open-window text: now through the look tokens). |
| Tests | nav_pages 22/22 (+ whatsnew: content, links, privacy, the filter, both looks), nav_search 4/4 (70 phrasings), help 35/35, zeus 52/52, olympus_map 7/7 |

## Not done (honest)
- Gate search UI (gate/gate.js, Home team) is unchanged: it already draws actions first and opens the first row on Enter, so the catalog fix
  reaches it as is. A "?find=words" deep link is an ask (ASKS.md #2).
- A bottom bar on the hub pages: none of them has one today (only the Gate / Zenith), so nothing sits under a bar; not added.

## PERF ask: gate-nav breadcrumbs shift the page (15:28 UTC)

Measured at 390 px, 4x CPU, ~1.6 Mbps / 150 ms (gate-nav lands at ~1.6-3.9 s there):
| Page | Before (CLS) | After |
|---|---|---|
| hub/index.html?h=bots | 0.50 (0.03 gate-nav row + 0.26 tabs/panel above the visible "All hubs" + 0.21 Right now facts) | 0.000 |
| hub/?h=settings / me / list | 0.03-0.05 | 0.000 |
| Agora apps (aegis, helios, demeter) | 0.058 at the moment gate-nav lands | unchanged here: the SAME 0.058 happens with gate-nav blocked, so it is agora-ui.js filling the header (PERF's DESIGN ask #1); once settled gate-nav changes the header height by 0 px (135 -> 135) |

Fix: hub/index.html reserves the Home / Go to row (`<div class="gn-row" data-gn-slot>`); gate-nav.js (g7) fills a `[data-gn-slot]` in place
instead of inserting a row (any page can use it); hub.css (h6) holds each hub's Right now height while its numbers load and keeps the blocks
below (All hubs, Also useful, the footer) invisible until hub.js (h5) marks hb-done (a 6 s failsafe). tests.test_nav_pages 26/26 (+ 4 slow-phone
CLS checks). Pins moved: test_hubs (h6/g7/h5), test_me_hub + test_gate_page (catalog nv6 in gate-nav: my earlier bump).
