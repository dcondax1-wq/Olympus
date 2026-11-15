# Look QA matrix (32 looks x 30 pages = 960 cells): 218 pass, 742 fixed, 0 known issue.

Each cell is one look on one page (390 x 844; `-desk` = 1440 x 900), measured by `tools/theme_shots.py --qa` (`tools/theme_qa.js`): text contrast on the page's real pixels (AA), AGORA colours left, +$ green / -$ red, the status bar, the first frame (no flash), the keyboard focus ring, and on NQ / Mint / My Money the Go to sheet, a toast and a sheet. pass = clean before and after, fixed = an issue before, clean now, known = still open (listed below). An issue the default (Agora) has on the same page is the default's own (listed last), not a look's.

| Look | home | hub-today | hub-bots | hub-kalshi | hub-money | hub-plan | hub-research | hub-jarvis | hub-worlds | hub-settings | dash-home | dash-zlarior | dash-atlas | dash-blitz | dash-money | dash-more | jarvis | nq | aegis | helios | kalshi | mint | oikos | ledger | planner | polis | cities | symposium | home-desk | dash-desk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agora | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| ivory | fixed | fixed | pass | fixed | fixed | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| midnight | fixed | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| terminal | fixed | fixed | pass | pass | pass | fixed | fixed | pass | pass | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| carbon | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| royal | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| aurora | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| amber | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | pass | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| lime | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| stocks | fixed | pass | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| editorial | fixed | pass | pass | pass | fixed | fixed | pass | pass | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| brutal | fixed | pass | fixed | pass | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| noir | fixed | pass | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| sunset | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| ocean | fixed | pass | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| carbonred | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | pass | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| forest | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| rosegold | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| swiss | fixed | pass | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| paperdark | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| solarized | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| nord | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| cyber | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| deco | fixed | pass | pass | pass | fixed | fixed | fixed | fixed | pass | pass | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| zen | fixed | pass | pass | fixed | fixed | fixed | pass | fixed | pass | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed |
| desert | fixed | fixed | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| monoblack | fixed | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| monowhite | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| vapor | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| bullion | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | pass | fixed | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| wallstreet | fixed | pass | fixed | fixed | pass | fixed | fixed | pass | pass | fixed | fixed | pass | pass | pass | fixed | pass | fixed | pass | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |
| marble | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | fixed | pass | fixed | fixed | fixed | fixed |

## Known issues (none)

None.

## The default's own issues (Agora, kept byte for byte; not part of the look work)

- **Dashboard: Home**: contrast: e > button.card.hd-home > span.hd-home-i '3D' #ffffff on #539afd 2.82:1 (+12)
- **Dashboard: ATLAS**: contrast: div.at-top > div > span.sc-pill 'PAPER' #efeeeb on #deae5e 1.75:1
- **Dashboard: BLITZ**: contrast: .bl-hero-h > div.bl-chips > span.bl-chip 'NOT RUNNING YET' #9a8f7d on #3c3340 3.76:1 (+3)
- **Dashboard: Money**: contrast: div.rc-kpis > div.rc-kpi.rc-tilt > span 'Real net' #9a8f7d on #2e2a24 4.45:1 (+13)
- **Dashboard: More**: focus ring: div.cl-search > label > input#clQ no ring None 0:1
- **Kalshi**: contrast: div.l3d > a.lnk3d.city > b 'Kalshi City ›' #4b7a99 on #1e1c19 3.64:1
- **Dashboard 1440**: contrast: e > button.card.hd-home > span.hd-home-i '3D' #ffffff on #539afd 2.82:1 (+12)
