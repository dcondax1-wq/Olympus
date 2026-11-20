# Pre-registration: NQ live loop speed + fills (day-speed, 2026-11-20, written before any run)

## Questions
1. Where do the seconds go from bar close / first tick -> signal -> order -> fill, per bot (LIT = Zlarior, ATLAS)?
2. Does poll-on-tick (engine/fast_entry.py, OFF) give earlier entries / better prices on the real signals, at what risk?
3. Which read-only speed-ups (no trading decision changes) save the most poll time?
4. Slippage per order type per bot from every real fill; timing vs price part of the gap to the backtest twin.

## Harness (research/speed/replay_harness.py)
Real engine.live.LiveBot, paper adapter, frozen clock, data_source "ninjatrader", no_yahoo, the REAL read path:
- engine.live.DATA_DIR -> temp dir holding the TradingView history cut 10 days before the replay start (the PC's export lags).
- nt_folder -> temp dir with NQ_1m.csv / NQ_5m.csv in LE_BarFeed's format (no header, "t,o,h,l,c,v\n"), sized like the PC:
  up to 20,000 1m + 8,000 5m lines (+1000 trim slack). Before each poll the bars closed by then are appended and
  NQ_1m_open.csv is rewritten with the forming minute's open, exactly as LE_BarFeed does.
- nt_archive -> temp dir. live_model.json as shipped (LIT). engine.poll_timing installed for the stage split.
- Replay sessions: 2026-11-16, 11-17, 11-18 (the days of real fills), polls at minute + 2 s (today's offset) every minute
  01:30-12:00 ET, every 5 min otherwise.
Output: per-stage ms (median / p90), poll total, the signal -> order part (lit_ms), routed ledger rows.

## Speed-up acceptance (each candidate, monkeypatched in the harness only)
- Decisions identical: same ledger rows (side, qty, stop, target, entry_t, pnl) and same signal/route log lines as the
  unpatched run on the same sessions; plus the candidate's own equality test (frames identical, pandas.testing).
- Kept only if the median entry-path poll saves >= 20 ms on this machine. Ranked by ms saved.

## Fast entry decision rule
Measured quantity available: real fills (fill_px vs bar open, route delay 3-5 s), n = 4. No tick data exists in the repo
(futures-only rule, no paid data). The $ value is therefore an estimate band, not a measurement:
  ticks saved = slippage per second x seconds saved, with slippage per second from the real fills (linear lower/upper
  bounds stated). Decide card "turn on fast entry" ONLY IF: (a) the harness shows 0 decision differences ON vs OFF,
  (b) no double-order path is found, (c) the low end of the $ band is > $0. Otherwise: no card, a Sim measurement plan.

## Fills
Every fill with a price in the repo (night-nqlive table, research/second/atlas_fills*.json, data/pc_days if pulled).
Gap to the backtest twin split into timing (route delay x price drift) vs price (fill vs price at route). Small sample stated.
