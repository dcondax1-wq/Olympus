# LEAD WIRES (night-revamp-dash, 2026-11-20): what only the lead may change

1. **jarvis/apps.js**: add one row for the new folder `widget` (test_apps_list a. now lists `widget` next to the pre-existing
   atlascity / gate / hub / pc misses). Suggested: `app('widget', 'Widget', 'money', '#c8a24a', 'Your accounts as an iPhone widget + the big Glance page', { glyph: '▣' })`,
   index = `widget/index.html`; the Glance page is `widget/glance.html` (has its own manifest, start_url glance.html).
2. **sw.js** (any precache / version list): new files
   `business/dashkit.js`, `business/dashkit.css`, `business/dash.json`,
   `widget/index.html`, `widget/glance.html`, `widget/glance.js`, `widget/widget.css`, `widget/olympus-widget.js`, `widget/icon.svg`, `widget/manifest.webmanifest`.
   Changed: `brain.js` (index.html now loads `brain.js?v=8`), business `goals/accounts/week/lab/index.html`.
3. **tools/build_web_dashboard.py**: make sure `tools/web_public/widget/` is copied like every app folder, and run
   `python tools/money/dash_build.py` before the copy (or in the PC's nightly after edge_health / money_plan / the backtest refresh),
   so `business/dash.json` follows the research files. It reads only research/lab/{edge_health,backtest_live,money_plan}.json, < 60 KB.
4. **run_area**: I added `AREAS["money"] += ["widget", "money_dash"]` (own line in tests/run_area.py).
5. Not mine, seen while testing (also fail on `pc`): test_biz_models a. (fixture stale: rerun `biz_publish --fixture`),
   test_weekly_review a. (planned accounts in week.json), test_money_plan (needs numba in the cloud).
