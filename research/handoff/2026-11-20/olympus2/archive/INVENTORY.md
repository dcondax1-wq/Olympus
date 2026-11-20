# Archive team inventory (day-archive 2026-11-20)

50 app folders owned by the archive team. Scan: 390x844 mobile Chromium, our code, data files from the live site (dcondax1-wq.github.io), 2.5 s after load (`scan.py`). KB = bytes the page pulled on open (JS, CSS, data, images).
Verdicts: VISIBLE 4 (not archived), KEEP-ARCHIVED 21 (reachable from the Archive fold, banner + fixes), RETIRE? 25 (proposal: drop from doors and search; the folder and URL stay, banner points to the live app; LEAD_WIRES.md).
Page errors: 0 before and after on every page. Sideways scroll: 0 px everywhere. Left 404s: kalshi.json (the Kalshi feed, not connected until Monday: by design); agency/my_leads.json shows here because this scan is not on github.io (on the site it is no longer asked); pc's favicon is fixed after the scan. Ares 'before' KB is low because the scan's 6 s abort cut its 8.8 MB data.json short; on a phone it was ~10 MB.

| app | live version (banner link) | data it shows (age) | errors / 404 before -> after | KB on open before -> after | verdict | why |
|---|---|---|---|---|---|---|
| `agency` | (not archived) | demo leads + owner's PC leads (local only) | 2 (agency/my_leads.json) -> 2 | 620 -> 620 | VISIBLE | side income page; fixed the my_leads.json 404 on github.io |
| `apollo` | Journal | odeon trades to Oct 28 | 0 -> 0 | 990 -> 993 | KEEP-ARCHIVED | weekly review view the journal lacks; data age now shown |
| `arbiter` | Business | demo spreads (labelled) | 0 -> 0 | 537 -> 540 | RETIRE? | off-strategy paper lab |
| `archive` | Clio | index.json today | 0 -> 0 | 2229 -> 2231 | KEEP-ARCHIVED | searchable test library; read by Cities/Colosseum |
| `arena` | Atlas | XP demo | 0 -> 0 | 1545 -> 1547 | RETIRE? | gamification |
| `ares` | NQ bots | home.json account (live) | 0 -> 0 | 1355 -> 1509 | KEEP-ARCHIVED | GO/WAIT/HALT sizing; no longer downloads 8.8 MB on open |
| `argo` | Hera | home.json payouts (none yet) | 0 -> 0 | 688 -> 691 | RETIRE? | goals as islands; Hera covers |
| `argus` | Board | home.json + checks (live) | 0 -> 0 | 1545 -> 1553 | KEEP-ARCHIVED | what-to-fix list; dev-facing but real |
| `athena` | Clio | 200 strategy notes (static) | 0 -> 0 | 1571 -> 1579 | KEEP-ARCHIVED | learning library; Clio covers research |
| `atlascity` | Atlas | home.json (live) | 1 -> 0 | 178 -> 181 | RETIRE? | duplicate of Atlas; no door lists it |
| `bridge` | Jarvis | jobs.json (static) | 0 -> 0 | 377 -> 380 | RETIRE? | ChatGPT link jobs; niche |
| `chronos` | NQ bots | odeon trades to Oct 28 ('2026-10 so far') | 0 -> 0 | 1924 -> 1927 | RETIRE? | day replay; duplicate of Odeon/NQ, data 23 days old |
| `colosseum` | Clio | extra.json Nov 15 | 0 -> 0 | 2813 -> 2816 | KEEP-ARCHIVED | strategies fight (research) |
| `delphi` | Morning brief | home.json (live) briefing | 0 -> 0 | 719 -> 721 | RETIRE? | go/no-go duplicate of Helios |
| `epilogue` | Journal | home.json week (live) | 0 -> 0 | 2497 -> 2500 | KEEP-ARCHIVED | Sunday review; Journal covers most |
| `ergasterion` | Board | demo AI workers | 2 (kalshi.json) -> 2 | 3203 -> 3206 | RETIRE? | dev-facing; queue.json read by Jarvis/Polis: folder must stay |
| `forum` | Morning brief | Pantheon read Nov 3 + live eval | 0 -> 0 | 1553 -> 1557 | KEEP-ARCHIVED | morning ritual; now labels the 17-day-old market read as old |
| `gallery` | Atlas | 3D shapes demo | 0 -> 0 | 1381 -> 1384 | RETIRE? | showcase page, no data |
| `harmonia` | Business | money/index.json estimate | 0 -> 0 | 1577 -> 1580 | RETIRE? | duplicate of Business |
| `hephaestus` | Clio | data.json Nov 4 | 0 -> 0 | 1265 -> 1267 | KEEP-ARCHIVED | tune dials research |
| `herald` | Board | edition Nov 11 | 0 -> 0 | 2159 -> 2162 | RETIRE? | daily paper of who built what; dev-facing, old |
| `hermes` | Ledger | demo 'Wrapped' (labelled) | 2 (kalshi.json) -> 2 | 602 -> 605 | RETIRE? | fun story; no decision value |
| `hestia` | Compass | home.json (live) | 0 -> 0 | 1149 -> 1151 | RETIRE? | duplicate of Compass |
| `inbox` | (not archived) | home.json alerts (live) | 2 (kalshi.json) -> 2 | 611 -> 611 | VISIBLE | alerts list; the kalshi.json 404 is the Kalshi feed not connected yet (Monday) |
| `kairos` | NQ bots | clock + odeon trades | 0 -> 0 | 2898 -> 2901 | RETIRE? | session clock; NQ + Planner show the window |
| `kratos` | Journal | odeon trades to Oct 28 | 0 -> 0 | 1897 -> 1900 | KEEP-ARCHIVED | discipline score; data age now shown |
| `labyrinth` | Pnyx | odeon trades + live room | 0 -> 0 | 1929 -> 1931 | KEEP-ARCHIVED | pass odds by size; Pnyx sizes but has no odds |
| `lyceum` | Clio | quiz (static) | 0 -> 0 | 3188 -> 3190 | RETIRE? | duplicates Athena |
| `mind` | Jarvis | demo vault (labelled) | 0 -> 0 | 1713 -> 1715 | RETIRE? | 3D brain demo; Jarvis has the memory |
| `mint` | Business | money/index.json (labelled example) | 0 -> 0 | 1845 -> 1848 | RETIRE? | duplicate of Business |
| `mintcity` | Business | money/index.json (labelled example) | 0 -> 0 | 2506 -> 2509 | RETIRE? | 3D marble city of Mint; gimmick |
| `moirai` | Fates | simulation (labelled) | 0 -> 0 | 1196 -> 1199 | KEEP-ARCHIVED | eval Monte Carlo; Fates covers |
| `nemesis` | Journal | odeon trades to Oct 28 + live balance | 0 -> 0 | 2039 -> 2042 | KEEP-ARCHIVED | loss review; data age now shown |
| `nike` | Journal | odeon trades to Oct 28 | 0 -> 0 | 1419 -> 1422 | RETIRE? | trophy hall, 44 animations; no money use |
| `observatory` | Clio | data health (demo parts) | 0 -> 0 | 749 -> 751 | RETIRE? | lab page |
| `odeon` | Trading | trades to Oct 28 | 0 -> 0 | 1850 -> 1852 | KEEP-ARCHIVED | 3D replay; its trades.json feeds Trading/Journal/Kronos/NQ: folder must stay |
| `oracle` | NQ bots | live NQ price (LAST SEEN shown) | 0 -> 0 | 1592 -> 1595 | KEEP-ARCHIVED | market radar with its own age; heavy |
| `pantheon` | Morning brief | pantheon.json Nov 3 (17 d old) | 0 -> 0 | 1390 -> 1393 | KEEP-ARCHIVED | builder stopped Nov 3 (lead/DATA team: rerun or retire); feeds Forum/Cities |
| `pc` | (not archived) | static PC connect page | 0 -> 0 | 7 -> 7 | VISIBLE | PC helper downloads; fine |
| `pheme` | Morning brief | stats.json Nov 10, bars to Oct 16 | 0 -> 0 | 1451 -> 1453 | RETIRE? | releases word-on-street; low value, old |
| `pinakes` | Clio | catalog.json today | 0 -> 0 | 2239 -> 2247 | KEEP-ARCHIVED | table catalogue (dev) |
| `plutus` | Hera | roadmap.json Nov 4 (16 d old) | 0 -> 0 | 10021 -> 1429 | RETIRE? | duplicate of Hera; roadmap.json feeds Hera/Demeter/Ledger: folder must stay; 8.8 MB fixed |
| `polis` | Atlas | home.json + people (live) | 2 (kalshi.json) -> 2 | 2821 -> 2824 | RETIRE? | 3D app city; Atlas is the directory |
| `prometheus` | Clio | forge.json Nov 17 | 0 -> 0 | 1581 -> 1584 | KEEP-ARCHIVED | strategy forge research |
| `pythia` | Morning brief | events.json Nov 10 (calendar ahead) | 0 -> 0 | 1738 -> 1740 | KEEP-ARCHIVED | events.json feeds Helios/Planner/Jarvis/Hub: folder must stay |
| `stoa` | Compass | home.json (live) | 2 (kalshi.json) -> 2 | 2393 -> 2396 | RETIRE? | duplicate of Compass |
| `symposium` | Board | demo AI workers | 2 (kalshi.json) -> 2 | 4078 -> 4081 | RETIRE? | gimmick, 4 MB on open |
| `tree` | Clio | research search snapshot | 0 -> 0 | 2139 -> 2142 | KEEP-ARCHIVED | strategy tree research (Clio links) |
| `tyche` | (not archived) | kalshi.json (not connected) -> demo wheel | 2 (kalshi.json) -> 2 | 1486 -> 1486 | VISIBLE | Kalshi door shortcut; demo until the Kalshi feed connects |
| `why` | Trading | why.json research to Oct 16 | 0 -> 0 | 248 -> 250 | KEEP-ARCHIVED | owner's win/loss study; Trading reads why.json |
