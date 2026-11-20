# Planner + Business on a 390x844 iPhone (lead job 12:04 ET)

`python tools/a11y_sweep.py --apps planner,business,business/accounts.html,business/mffu.html,business/taxes.html,business/plan.html --quick` (6 screens each), before -> after:

| Page | Before | After | Change | Issues before | Issues after |
|---|---|---|---|---|---|
| business | 92 | 96 | +4 | 77 | 14 |
| business/accounts.html | 88 | 96 | +8 | 49 | 6 |
| business/mffu.html | 92 | 96 | +4 | 77 | 8 |
| business/plan.html | 92 | 96 | +4 | 46 | 10 |
| business/taxes.html | 81 | 96 | +15 | 33 | 4 |
| planner | 92 | 100 | +8 | 69 | 39 |

Average 90 -> 97.


Done: sentences 15 px and nothing under 12 px, in rem (business.css + planner.css, html:root over the AGORA app base); taxes .src links 44 px; taxes live list keeps its list role; layout reserved for the late cards (planner section.pulse 15.75rem, accounts cockpit/payday/list while empty); the pulse headline never cut; the planner subtitle no longer runs under the sundial. Left: accounts cockpit h3 after h1 (dashkit.js, heading order), pulse .pu-ts 12 px (kit, FOR_design K2), small table headers. Tests: business_pages 40/40, mffu_center 40/40, business_taxes 32/32, business 78/78, planner_page 170/170, planner_addons 9/9, planner_temple 16/16, smoke 9/9.
