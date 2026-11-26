# day-site5 A + B (Money view, Strategy health): lead-only wiring

## Wires
1. `tools/build_web_dashboard.py`: run `python tools/build_money_health.py` before the copy. It writes `trading/bands.json` (PROVISIONAL band
   from the backtest trades in trading/trades.json until `research/health/bands.json` lands, then a copy of it) and, once
   `research/forecast/forecast.json` exists, `business/forecast.json`. `--check` exits 1 when stale. New files ship with their folders:
   `business/moneyview.js`, `trading/healthcore.js`, `trading/health.js`, `trading/bands.json`.
2. `sw.js` CACHE bump (as usual; bump_versions asks for it).
3. For the helpers building the data: the shapes the pages read are in the builder's docstring (`tools/build_money_health.py`):
   forecast.json `{v, made, market, runs, accounts: {<key|name>: {name, p_pass, p_fail, days_med, days_p25, days_p75, pass_by, p_payout,
   payout_by, payout_usd}}}` (p 0..1); bands.json `{v, made, bots: {lit|atlas: {window, avg_r: {p5,p25,p50,p75,p95}, streak_p75, streak_p95,
   n_backtest, span}}}`. A file with `"sample": true` shows SAMPLE.

## What changed
- **Money view** (`business/mffu.html` + `moneyview.js`, pure): per account card, under the 4 tiles: a gauge **To pass** (eval: $ left,
  % done, the forecast: pass %, most likely date, fail % — from the forecaster, else the payday plan's 1,000 runs, named) or **To payout**
  (sim funded: $ to the goal balance = buffer + the owner's ask, i.e. $1,350 on ATLAS's first-at-minimum $250, $2,100 for the $1,000 max;
  the first-payout estimate) with **when it can next request** (today with $; else the earliest date from the 48 h wait + the traded days
  left in the cycle (weekdays) + $ still needed), and a **risk distance** bar "$X from the floor" (open trade counted), red under $300,
  gold under half the max loss.
- **Strategy health** (`trading/` card before the filters; `healthcore.js`, pure): per bot (LIT, ATLAS; never BLITZ on that page) the last
  10 real trades vs every 10-trade stretch of the backtest: **normal** (middle half), **cold streak** (weaker quarter, or a losing run past
  the backtest's 75%), **outside the band** (beyond the 5% tails, or a streak past its 95%; above = "hot, do not size up"), **too few
  trades** (< 5). Today: LIT 2 and ATLAS 3 real trades -> "too few trades". A bar shows the band, its middle half and the live average.

## Tests
`tests.test_money_health` 22/22 (static, node: every gauge / request / floor / health case, the band = an independent count; browser:
both pages at 390). test_mffu_center 37/37 (script order list + moneyview.js), test_mffu_view 22/22, test_business_pages 32/32,
test_trading_page 55/55. Shots: shots/after/11_money_view.png, 12_strategy_health.png.
