# nqdash2: what the lead wires (helpers do not touch these files)

1. **sw.js precache** (if the pages are precached): add `nqdeep.js?v=1`, `nqdeep.css?v=1`, `business/payday.json`, `nq/news_week.json`;
   bump the cache for `trading/trading.js?v=5`, `trading/index.html`, `nq/nq.js?v=r12`, `nq/index.html`, `business/mffu.js?v=5`, `business/mffu.html`.
2. **Build hook** (`tools/build_web_dashboard.py` or the nightly job): run `python tools/nqdash_export.py` before publishing, so
   `business/payday.json` follows `research/lab/payday_plan.json` and `nq/news_week.json` keeps "this week" current (it is a 7-days-back /
   28-days-ahead window of `data/news/events.csv`; the copy in the repo is from Nov 20). `--check` exits 1 when either is stale.
3. **Tests**: add `tests/test_nqdeep.py` to the `nq` / `money` areas in `tests/run_area.py`.
4. Nothing to do for `olympus.js` APPS / doors / jarvis: no new app, only new sections inside trading/, nq/ and business/mffu.html.

Notes
- Pre-existing, not mine: `tests.test_trading_page --static` has 2 Odeon reel FAILs on pc too (49/51 before and after this branch).
- nq/?demo=1 still shows the BLITZ card (paper, existing nqcore behaviour); the hidden-bot rule may want it gone there too.
