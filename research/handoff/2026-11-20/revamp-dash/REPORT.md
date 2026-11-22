# night-revamp-dash REPORT (2026-11-20): branch night-revamp-dash, tests green
1. Widget: `widget/olympus-widget.js` (Scriptable, free iOS app) in small / medium / large: each account's balance, today's $, $ to pass or $ to payout, room, PC status, next Kalshi clock window, refresh time, tap = site. Reads the PC's public 15-min post (LIVE), else home.json (PAPER), else its last copy (CACHED). Read only.
2. `widget/` page: 3 install steps + Copy / Download buttons. `widget/glance.html`: the big "Add to Home Screen" glance (rings = room left, bars = way to pass), refreshes every minute.
3. Money pages: new live cockpit (Goals, Accounts, Business home), payday calendar + 6-month money fan (Goals, Accounts; ESTIMATE), edge health over time, $ per month 2026 / 2021-25, 2026 equity, wins / losses / best / worst trade (Week; BACKTEST), Lab scoreboard + why ideas failed (Lab). Every card shows LIVE / STALE / PAPER / BACKTEST / ESTIMATE + its age, has a table view, tap tooltips.
4. Brain (All bots): new "Each bot, in one line" card: ON / OFF, today's $, room bar, what it waits for.
5. Data: `tools/money/dash_build.py` -> `business/dash.json` (23 KB, from research/lab only; no new numbers invented).
6. Fixed on the way: a browser has its own `Request`, so the widget code now detects Scriptable by ListWidget (the Glance page was blank before the fix).
7. Tests: test_widget 34/34 (parsing with a sample payload + a fake Scriptable drawing all 3 sizes), test_money_dash 28/28, public_build_privacy --fast 56/56, business_pages 40/40, money area 10/13 (the 3 reds also fail on pc: see LEAD_WIRES 5), shots_brain phone demo 0 console errors.
8. Lead to wire: apps.js row, sw.js list, build copy + dash_build run (LEAD_WIRES.md).
Screenshots (390x844, here): widget_glance_html_dark / _light, widget_index_html_dark / _light, business_goals / _week / _lab / _accounts _html_dark, brain_all_bots_dark.
Business pages are dark by design (Olympus "stage" palette), so their light shots matched the dark ones and were dropped.
