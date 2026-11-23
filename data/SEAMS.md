# Data seams (read before using these files across the dates below)

| File | From | What changes | Use |
|---|---|---|---|
| NQ_1m / NQ_5m / NQ_15m / NQ_1h / NQ_1d | after 2026-10-16 (the last TradingView NQ1! export) | the rows come from the PC's NinjaTrader chart (MNQ, the same price as NQ), so **volume is MNQ volume, about 5x NQ's** | price: fine across the seam. Volume: never compare or z-score across it; use one side, or rescale |
| NQ_1d / ES_1d | after 2026-10-16 | built from the 1h file by `data/import_futures.build_daily` (18:00 ET -> 17:00 ET, stamped that day 00:00 UTC, as TradingView) | a day the PC missed hours of is still written as one bar (its high / low / volume may be short); daily bars are append-only |
| ES_* | 2026-10-19 .. 2026-10-22 | missing on the PC (no ES bars those days) | a gap, not zeros |
| CBOE_vol_1d / GEX_1d | always | `tools/context_refresh.py` refreshes only the last 10 stored days from the source (CBOE completing a value, SqueezeMetrics revisions); older rows never change | a value for the last 10 days can still move; published after the close: use day D-1 for a decision on day D |
