# day-weekreview: LEAD WIRES (Week in Review)

New files (mine): tools/week_review.py, tools/web_public/nq/week.html + week.js + weekcore.js + week.css, tools/web_public/nq/week_review.json
(a built sample; the site build rewrites it), tests/test_nq_week.py (48 checks), this file. One line in tests/run_area.py (`AREAS["nq"].append("nq_week")`).
Not touched: sw.js, tools/build_web_dashboard.py, jarvis/apps.js, the olympus.js APPS table, nqnav.js.

1. **Data, in the site build / hourly pull** (needs the live feed for balances, waiting-for, 7-day clock, payout; works without it and says what is missing):
   `python -X utf8 tools/week_review.py` -> tools/web_public/nq/week_review.json (~35 KB). Run it AFTER tools/build_replay.py (it reads nq/replay/<day>.json:
   the twins + rejected setups + order-flow notes) and AFTER research/livegap/daily.json is refreshed. Publish the JSON with the site; keep it network-first.
   It merges the feed's "glog" (last 3 rejected setups per bot) into the PREVIOUS week_review.json, so the build must start from the published/committed copy.
2. **NQ nav**: add a button next to Order Flow in tools/web_public/nq/index.html (`.tags` row):
   `<a class="btn brainlink" href="week.html" aria-label="Open the Week in Review: $ per account, every trade, missed trades, grade">Week</a>`
   and (optional) a dock tab in nqnav.js: id 'week', label 'Week', page 'week.html' (the page already loads nqnav.js v3, so the dock shows once the tab exists).
3. **Cache / sw.js**: nq/ has no own worker (OTHER_APPS lists 'nq/'): nothing to add. If nq/ ever gets a precache list add week.html/.js/.css and weekcore.js; week_review.json must stay network-first.
4. **bump_versions**: week.css?v=1, weekcore.js?v=1, week.js?v=1 are the first versions.
5. **Privacy note**: the JSON carries the owner's real $ per account (like business/week.json), account NAMES only, no account numbers (masked in the builder, checked in the test), no keys.
6. **Browser tests in this container**: python playwright was not installed (pip install playwright worked) and the shared kit looks for chrome-linux/chrome while this image has
   chrome-linux64/: I added a local symlink (not in the repo). tests/browser_kit.chrome_exe could also try chrome-linux64.

What it shows (this week, built from real files): Quiet week: 0 trades on all 4 accounts, the twins found none either, 25 LIT setups formed and stopped at a rule (never filled 12, no inducement 6, outside hours 3, sweep too shallow 3).
Last week (Nov 16-20): ATLAS 25K 3 live trades (+$2,193 incl. the Nov 17 eval-passing winner), Zlarior 50K -$129 (matches the twin to the cent), Rapid EOD 25K missed the Nov 20 ATLAS trade (not armed). Nov 9-13: the PC-off week (7 twin trades missed).
Known limits: per-trade fills for Zlarior need the PC ledger (cards for older Zlarior / ATLAS trades are built from the twin and tagged "prices from the backtest twin"; $ are the audited live $);
BLITZ has no paper trades in the repo (the page says so); the twin $ are at the twin's size (50K size for LIT).
