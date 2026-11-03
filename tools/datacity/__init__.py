"""OLYMPUS DATA CITY: the NQ data machine (research only, paper only).

It turns the CME NQ1! 5m history (TradingView exports in data/, 2021-11 -> today) plus the bars the PC pushes to the
`heartbeat` branch into one big, honest table of "what tends to happen when":

  bars.py      the bar store: data/NQ_5m.csv + every new NinjaTrader 5m bar the PC pushed (incremental, never Yahoo)
  features.py  past-only features of every bar (levels, sessions, VWAP, EMA, ATR regime, VIX/VXN, SMT, day type, news, DST)
               and the event table: every trigger (sweeps, breaks, FVG, IFVG, CISD, displacement, VWAP cross, gap fill,
               news bar, plain 15-minute slots) with its mini-backtest (entry next bar open, structure stop, 1R/2R/3R hits,
               2R-or-time exit, 15/30/60-minute forward moves, $ per MNQ micro after costs)
  store.py     the cached event table: incremental (only new days are built; incremental == full is a test)
  grid.py      the combinations: time x confluence x "while" states, scored per year, 2026 vs 2021-25, Benjamini-Hochberg
               FDR, a sign-flip placebo and a 2021-24 -> 2025-26 holdout
  report.py    what it says: plain-language labels, leaderboard (rising / decaying), discoveries, confluence lift, sized
               strategies with MFFU eval speed, today's fired setups, the Jarvis card
  learn.py     one run: new bars -> table -> grid -> report -> research/datacity/*.json (+ the page's copy) and a run in
               research/runs/ (tools/runlib.py)

    python -m tools.datacity                 # incremental run -> research/datacity/*.json (+ the page's copy)
    python -m tools.datacity --full          # rebuild the event table from scratch
    python -m tools.datacity --heartbeat     # also append the PC's NinjaTrader bars from the heartbeat branch first

It never touches live_model*.json or any trading behaviour: it only proposes.
"""
