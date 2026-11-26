# Batch 5: fills, eval forecaster, health bands, BLITZ paper. Pre-registration (2026-11-26, BEFORE any number below)

PAPER RESEARCH ONLY. Nothing changes a live file, size or switch. Futures data only. Code: `research/batch5/fills.py`,
`tools/forecast.py`, `tools/health_bands.py`, `research/batch5/blitz_paper.py`; write-up `research/writeups/batch5-2026-11-26.md`.

## (A) ATLAS fill realism
Real fills available in the cloud = research/second/atlas_fills_why.json (+ data/pc_days fills.jsonl.gz). If there are fewer
than 10 real ATLAS fills, NO calibration is claimed: the measured entry slippage is reported as is and the cost is run as a
grid instead. ATLAS trades = tools/atlas.account_units(BASE) (the account path, stored fills). Order types (the live code):
entries = MARKET at the 5m open (every member); exits: STOP / BE / cut / T15 = stop-market (slips), TARGET = limit (no slip),
FLAT / HEDGE / time = market (slips). Extra cost per trade = k_entry ticks + k_exit ticks on market / stop exits, at
k_entry in {0, 2, 4, 6, 8, 10, 12} and k_exit in {0, 1, 2, 4}. Per member (EMA / MACD / S/R) and the book: PF, mean R, net $
at $250 risk a trade, for 2021-25, 2026 H1, 2026 Jul-Oct. The answer: the BREAK-EVEN entry ticks (PF = 1.00) per member per
span at k_exit = 2, set against the measured ~11.7 ticks. Verdict "the long-run edge survives realistic fills" only if 2021-25
PF > 1.0 at the measured entry ticks with k_exit = 2.

## (B) Eval pass forecaster (tools/forecast.py -> research/forecast/forecast.json; nightly-safe)
Per live account, from TODAY's state (tools/board.gather: balance, floor; sessions done from the eval start): research/plans/
rank.py's eval engine (the live two_week sizing, ATLAS lane, MFFU rules) started at that state, its strategy mix (Zlarior 50K /
25K #2 = LIT only; Rapid = LIT + ATLAS $250; ATLAS 25K funded = ATLAS, payout path), 1,000 paths of 5-session blocks from a
2026-like pool (Jan-Oct 2026) and a 2021-25-like pool: pass %, fail %, median sessions to pass, median sessions to the first
payout (pass + the funded payout path), P(first payout within 60 sessions). Funded ATLAS: P(first payout), median sessions,
P(loss). JSON shape documented in the file.

## (C) Strategy health bands (tools/health_bands.py -> research/health/bands.json)
Per bot (LIT = run lit_live units, ATLAS = account units, BLITZ = its live rule): every rolling 20-trade mean R in the
backtest, 2026 and 2021-25 pools separately: 5 / 50 / 95% band. Live: the last <= 20 live trades (data/pc_days ledger exits +
tools/web_public/trading/trades.json live rows; R = $ / the trade's planned $ risk) -> mean R and its percentile in each band;
fewer than 5 live trades -> "too few to judge".

## (D) BLITZ paper vs backtest
The PC's real paper ledger (data/blitz_state.json) is NOT in the cloud: stated. Instead: engine/blitz.replay_2026 (the live
paper code on the PC's bars) from 2026-10-19 (the PC bot's start, assumed) to the last bar = what the paper shadow should
have done, vs its 2026 backtest band from (C): n, win %, mean R, $ at $150, rolling-20 percentile. Verdict "behaving like the
backtest" when the rolling mean sits inside the 5-95% 2026 band.
