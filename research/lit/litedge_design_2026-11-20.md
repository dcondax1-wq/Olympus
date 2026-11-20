# Zlarior (LIT) edge 2026-11-20: pre-registered design (written and committed BEFORE any run)

Base: the live LIT trades (tools/lit_edge ctx()["T"], 631 trades, = run lit_live), re-walked by
tools/lit_more_money.manage_v (options off = live, `check` 0 differ). Scoring and gate G1-G6 exactly as
research/lit/more_money_design_batch2.md (LIT size, live two_week eval path room 0.4 to session 80, funded 50K,
week-block bootstrap <= 0.10, 2021-25 >= -$600, 2-4 trades a week). Plus a 10-tick cost stress on the base and on
any idea that passes. One fixed version per idea; no second version is run if it fails.

Read first and NOT redone (docs/TESTED_AND_REJECTED.md): limit at the CISD close / zone / pullback limits / chase,
buy-stop, entry delays 5-15 min, 2m/3m CISD, 1m BOS; displacement speed (extreme -> CISD bars); entry windows;
12 bias methods incl. PDH/PDL draw, premium/discount, Po3, Asia/London direction, 1H/4H/daily structure, day range so
far vs VIX moves, level in the way; news blackout 15/30/60, news-after-release, news exits/BE/tilts; ES SMT
filter / pick / tilt / ES filler / ES fail cut; every BE trigger 0.5-2R, on a close, by ATR, stair stops, partials,
time stops, 15m trails, CHoCH exits.

## The 5 new ideas (one version each)

1. **fill_better2 (job a, fills):** rest a LIMIT 2 ticks better than the model's market fill (model = next 1m open +
   1 tick; limit = that open - 1 tick in direction space) for the entry 1m bar only. Fills only if the bar trades
   1 tick through it (low <= L - 1 tick); the fill bar gets no target / BE credit. Not filled -> market at the next
   1m open + 1 tick (chase). Same stop, same target level. (Different from the CISD-close limit: the price is tied
   to the live fill, not the candle close, so it measures pure queue / price improvement.)
   Descriptive add-on (not a rule): fill probability and $ of missed winners for a limit 1/2/4/8 ticks and
   10/25/50% of the risk better than the model fill, resting 1/3/5 minutes, on 2026 trades.
2. **stale_sweep60 (job b, timing):** skip a setup whose 1m entry comes more than 60 minutes after the SWEEP bar
   (sweep_i, the bar that took the level), day left free (engine skip_keys). (Speed was extreme -> CISD bars as a
   size tilt; this is sweep age at entry as a filter.)
3. **news_tgt4 (job d, news):** on Tier-1 days (data/news/events.csv impact high), the target is capped at
   entry + 4R (planned R) if the band target is farther. Nothing else changes.
4. **es_room (job e, ES vs NQ):** when ES data exists and the MES trade (tools/lit_more_money.es_trade_for: ES stop
   1 tick beyond ES's sweep-window extreme, ES VIX band target) offers a planned target R >= 1.25 x NQ's planned
   target R, trade MES instead of MNQ; else NQ. (smt_pick used SMT presence; this uses the room per risk = the
   "cleaner" market.) Only 2025-04..2026-10-16 has ES bars; 2021-24 is unchanged by construction.
5. **be_after10 (job f, management):** the +1R breakeven move is not allowed in the first 10 minutes after the fill
   (if +1R is reached before minute 10, BE is set at the first 1m bar at / after minute 10 IF the trade is still
   >= +1R at that bar's high; else wait for the next +1R touch). Everything else live.

## Job c (daily bias) and the rest of job d: no new cell
Every bias input the lead listed (prior-day high/low, overnight range, 1h structure, VIX band) and news skip / size
down / wait N minutes were already run as filters, tilts and targets (sources above). Their results are reported,
not re-run.

## Not ideas (descriptive, reported only)
- Entry-minute map (R a trade by ET hour and by minutes after the sweep), both 2026 halves.
- Cold-run anatomy: the twin trades since the eval start (Oct 19); how often the backtest has a 7-trade run this bad
  at the same size (all 7-trade windows 2021-26, and 2026 only), longest losing runs, and what separated losers from
  winners (exit kind, hour, stop pts, planned R, MFE).
- "ATM model ICT": no codable definition in the repo or the owner's reports; not tested.
