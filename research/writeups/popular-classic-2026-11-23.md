# Popular classic NQ / ES strategies, as the textbook states them (2026-11-23)

Paper research only (branch `day-pop-classic`). Nothing armed and no `live_model*.json` touched. Tool: `tools/popular_classic.py`
(the rules are in its header, committed **before** the first run in commit "pre-registered rules"). Numbers:
`research/lab/popular_classic.json` (rows) + `popular_classic_detail.json`.

## Bottom line
**0 of 16 pass.** After the Holm correction for 16 tests, none has a 2021-25 edge (best: Crabel stretch, raw p 0.059, Holm 0.95).
Only Crabel stretch is positive in all three spans, and its Jul-Oct PF is 1.07 (bar 1.1) and ES loses Jul-Oct (-$763/mo). Each one adds
little or negative money as an add-on on a Rapid EOD 25K / 50K and never raises the 2026 40-session pass rate. The best any of them does is leave it unchanged
(RSI(2) 15m Jul-Oct, NR7-ID, Turnaround Tuesday). Most "2026 Jan-Jun winners" (Keltner, IB breakout, ORB 30) flip to losers in Jul-Oct: the same
regime-noise pattern as the earlier hunts. **No proposal. LIT / ATLAS unchanged.** Nearest miss to watch: Crabel stretch (paper lead only).

## Method (fixed before any run, no tuning)
- CME NQ1! 5m (TradingView export, back-adjusted), RTH 09:30-15:55 ET, flat at the 15:55 open (MFFU flat by 16:10). ES1! 5m exists
  only from 2025-04, so ES is a 2026 robustness column (same rules, MES).
- Costs: $1.90 a micro round turn, 1 tick slippage in and out (stops and time exits), targets need a trade-through, stop + target
  in one bar = stop.
- MFFU micro sizing: $400 risk a trade, micros = floor(400 / (stop x $2 + $1.90)), 1-40. If 1 micro costs more than $400 the trade is skipped. This
  removes most NR7-ID and Turnaround Tuesday trades in 2026 (median stops 93-173 pts), so their counts are tiny.
- Spans: 2026 Jan-Jun, 2026 Jul-Oct, 2021-25 (data from 2021-10).
- Multiple testing: a one-sided t-test of mean daily $ over 2021-25 for each strategy, with a Holm correction over all 16. A pass needs net > 0 and PF >= 1.1
  in all three spans (n >= 5 in each 2026 half) and Holm p < 0.05.
- Correlation: daily $ vs LIT (`research/lab/backtest_live.json`) and ATLAS (`research/runs/atlas_base.json`), up to 2026-10-16.
  Overlap = the share of the strategy's trade days that LIT / ATLAS also trade. The base rate is about 0.48 for both: LIT and ATLAS each trade
  about 48% of days, so overlap ~0.48 means no clustering.
- Rapid EOD add-on: a fresh account started on every session. 25K: $1,500 target, $1,000 EOD trail, LIT+ATLAS book x0.5, add-on
  at $200 a trade. 50K: $3,000 / $2,000, book x1, add-on $400. Pass / fail within 40 sessions and $/month vs the book alone.
  This is a simple combined-book model, not engine/rapid.py's lane sizing.

## Ranked table (NQ, MNQ, costs in)
Ranked by spans positive, then Holm p, then 2021-25 $/month. tpw = trades a week.

| # | Strategy | Already tested? | 2026 Jan-Jun: tpw / win / PF / $/mo / maxDD | 2026 Jul-Oct | 2021-25 | Holm p | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Crabel stretch | partly | 3.59 / 47.4% / 1.24 / $603 / $-3,387 | 3.28 / 45.8% / 1.07 / $147 / $-3,323 | 4.41 / 43.5% / 1.14 / $406 / $-8,467 | 0.9472 | rejected |
| 2 | Keltner channel breakout | partly | 5.81 / 47.1% / 1.35 / $890 / $-2,260 | 6.11 / 36.4% / 0.7 / $-895 / $-4,490 | 6.5 / 38.7% / 1.12 / $436 / $-10,131 | 1.0 | rejected |
| 3 | Initial Balance breakout | no (IB only as a scalp-mean-reversion level) | 3.37 / 48.4% / 1.25 / $482 / $-1,887 | 3.39 / 39.3% / 0.84 / $-334 / $-3,917 | 4.14 / 49.3% / 1.09 / $224 / $-6,101 | 1.0 | rejected |
| 4 | Opening Range Breakout 30 min | partly | 3.89 / 43.8% / 1.26 / $696 / $-2,016 | 4.06 / 34.2% / 0.79 / $-649 / $-3,752 | 4.39 / 40.2% / 1.0 / $9 / $-7,150 | 1.0 | rejected |
| 5 | Connors RSI(2) 15m | yes | 3.52 / 63.2% / 1.07 / $75 / $-1,694 | 4.28 / 68.8% / 1.14 / $154 / $-785 | 4.19 / 61.0% / 0.9 / $-169 / $-10,879 | 1.0 | rejected |
| 6 | Initial Balance fade | partly | 3.11 / 32.1% / 1.42 / $1,505 / $-6,348 | 3.0 / 31.5% / 1.24 / $780 / $-3,043 | 3.05 / 28.9% / 0.82 / $-642 / $-41,807 | 1.0 | rejected |
| 7 | Donchian 20/10 breakout | no (only turtle-soup fades were tested) | 7.26 / 40.3% / 0.88 / $-404 / $-4,775 | 8.11 / 37.7% / 0.66 / $-1,306 / $-7,099 | 9.11 / 40.9% / 1.04 / $143 / $-8,301 | 1.0 | rejected |
| 8 | Turnaround Tuesday | partly | 0.19 / 80.0% / 3.98 / $177 / $-349 | 0.22 / 25.0% / 0.34 / $-143 / $-891 | 0.3 / 47.7% / 1.0 / $0 / $-2,862 | 1.0 | rejected |
| 9 | 9/21 EMA pullback in trend | partly | 12.0 / 37.0% / 1.0 / $31 / $-9,438 | 13.67 / 26.0% / 0.62 / $-5,761 / $-24,363 | 13.05 / 35.5% / 0.96 / $-546 / $-59,593 | 1.0 | rejected |
| 10 | VWAP reversion (2 SD -> VWAP) | yes | 7.07 / 18.8% / 0.73 / $-2,592 / $-16,267 | 7.67 / 27.5% / 1.02 / $139 / $-9,690 | 7.67 / 22.9% / 0.79 / $-2,105 / $-111,639 | 1.0 | rejected |
| 11 | NR7 inside-day breakout | yes | 0.0 / -% / - / $0 / $0 | 0.11 / 50.0% / 0.01 / $-72 / $-295 | 0.12 / 34.6% / 0.62 / $-39 / $-3,066 | 1.0 | rejected |
| 12 | Bollinger squeeze breakout | partly | 2.0 / 33.3% / 0.88 / $-231 / $-3,546 | 1.67 / 23.3% / 0.41 / $-1,185 / $-5,348 | 1.79 / 36.6% / 0.95 / $-91 / $-18,426 | 1.0 | rejected |
| 13 | Opening gap fill | yes | 1.78 / 39.6% / 0.6 / $-645 / $-4,648 | 1.61 / 51.7% / 0.93 / $-71 / $-1,121 | 2.27 / 47.9% / 0.89 / $-198 / $-18,039 | 1.0 | rejected |
| 14 | End-of-day momentum (last 30 min) | yes | 4.48 / 46.3% / 0.85 / $-361 / $-3,738 | 4.78 / 43.0% / 0.91 / $-213 / $-2,125 | 4.73 / 46.0% / 0.83 / $-435 / $-29,834 | 1.0 | rejected |
| 15 | Connors RSI(2) 5m | yes | 12.41 / 61.5% / 0.9 / $-462 / $-5,566 | 12.5 / 61.3% / 0.9 / $-407 / $-2,242 | 12.3 / 60.7% / 0.83 / $-754 / $-40,611 | 1.0 | rejected |
| 16 | VWAP trend pullback | yes | 6.93 / 32.1% / 0.86 / $-1,062 / $-10,197 | 7.61 / 33.6% / 0.93 / $-541 / $-5,340 | 7.28 / 31.1% / 0.8 / $-1,656 / $-88,188 | 1.0 | rejected |

## Correlation / overlap with LIT and ATLAS, and ES check

| Strategy | corr LIT H1 / H2 / 21-25 | corr ATLAS H1 / H2 / 21-25 | overlap LIT / ATLAS (21-25) | ES 2026 H1 / H2 $/mo |
|---|---|---|---|---|
| Crabel stretch | 0.039 / -0.084 / 0.018 | -0.034 / -0.08 / -0.007 | 0.49 / 0.5 | $488 / $-763 |
| Keltner channel breakout | -0.063 / -0.143 / -0.049 | -0.019 / 0.235 / -0.04 | 0.47 / 0.47 | $357 / $-459 |
| Initial Balance breakout | -0.12 / -0.177 / -0.043 | 0.002 / 0.051 / 0.041 | 0.48 / 0.48 | $419 / $-457 |
| Opening Range Breakout 30 min | -0.066 / 0.014 / -0.032 | -0.033 / 0.05 / -0.002 | 0.48 / 0.48 | $375 / $-187 |
| Connors RSI(2) 15m | 0.071 / -0.091 / 0.061 | -0.054 / -0.221 / 0.006 | 0.49 / 0.48 | $201 / $-330 |
| Initial Balance fade | -0.021 / -0.001 / -0.031 | -0.043 / 0.282 / 0.024 | 0.49 / 0.47 | $-373 / $-2960 |
| Donchian 20/10 breakout | -0.069 / -0.118 / -0.011 | -0.168 / 0.012 / -0.025 | 0.48 / 0.48 | $-317 / $-666 |
| Turnaround Tuesday | -0.019 / 0.229 / -0.092 | 0.047 / 0.023 / -0.017 | 0.57 / 0.51 | $5 / $-396 |
| 9/21 EMA pullback in trend | 0.017 / -0.121 / -0.006 | -0.093 / 0.187 / 0.009 | 0.48 / 0.47 | $-3143 / $-1848 |
| VWAP reversion (2 SD -> VWAP) | 0.068 / 0.023 / -0.042 | 0.036 / -0.024 / 0.014 | 0.47 / 0.48 | $-6169 / $-5945 |
| NR7 inside-day breakout | None / 0.052 / -0.065 | None / 0.023 / 0.011 | 0.35 / 0.31 | $-149 / $-200 |
| Bollinger squeeze breakout | 0.028 / 0.187 / 0.036 | -0.123 / -0.057 / -0.012 | 0.48 / 0.47 | $-832 / $-475 |
| Opening gap fill | -0.065 / 0.143 / -0.042 | 0.049 / -0.019 / 0.027 | 0.47 / 0.48 | $-201 / $-1170 |
| End-of-day momentum (last 30 min) | 0.075 / 0.048 / -0.021 | 0.024 / -0.069 / -0.019 | 0.48 / 0.47 | $-476 / $-1291 |
| Connors RSI(2) 5m | -0.141 / -0.166 / -0.002 | 0.091 / -0.006 / 0.055 | 0.47 / 0.47 | $-549 / $-2748 |
| VWAP trend pullback | -0.086 / -0.122 / -0.005 | -0.085 / 0.046 / 0.032 | 0.49 / 0.49 | $-1901 / $-4321 |

All correlations are within ±0.3 (mostly ±0.1), so these would diversify. But diversifying a strategy that has no edge adds noise, not money.

## Value as an ADD-ON in a multi-strategy Rapid EOD book (5+ trades/week target)

| Strategy | 25K +$/mo H1 / H2 / 21-25 | 25K pass-in-40 H1 / H2 / 21-25 (book alone 91 / 100 / 28) | 50K +$/mo H1 / H2 / 21-25 | 50K pass-in-40 (book 93 / 100 / 28) | book+addon trades/wk H1 |
|---|---|---|---|---|---|
| Crabel stretch | $302 / $40 / $203 | 83.0 / 97.3 / 26.6 | $603 / $80 / $406 | 83.0 / 97.3 / 27.1 | 8.33 |
| Keltner channel breakout | $445 / $-427 / $218 | 75.9 / 58.6 / 21.6 | $890 / $-854 / $437 | 75.9 / 58.6 / 21.7 | 10.56 |
| Initial Balance breakout | $241 / $-341 / $112 | 89.3 / 86.3 / 28.2 | $482 / $-680 / $225 | 89.3 / 86.3 / 28.3 | 8.11 |
| Opening Range Breakout 30 min | $348 / $-321 / $5 | 84.8 / 65.8 / 20.3 | $696 / $-642 / $9 | 84.8 / 68.5 / 20.4 | 8.63 |
| Connors RSI(2) 15m | $38 / $24 / $-84 | 72.3 / 100.0 / 21.3 | $75 / $49 / $-168 | 72.3 / 100.0 / 21.3 | 8.26 |
| Initial Balance fade | $753 / $570 / $-321 | 79.0 / 77.1 / 22.0 | $1505 / $1140 / $-641 | 79.0 / 78.6 / 22.4 | 7.85 |
| Donchian 20/10 breakout | $-202 / $-762 / $72 | 76.8 / 49.3 / 27.2 | $-404 / $-1523 / $144 | 76.8 / 49.3 / 27.3 | 12.0 |
| Turnaround Tuesday | $89 / $-81 / $0 | 91.1 / 100.0 / 27.5 | $177 / $-161 / $0 | 91.1 / 100.0 / 27.5 | 4.93 |
| 9/21 EMA pullback in trend | $16 / $-2905 / $-273 | 34.5 / 18.1 / 18.2 | $31 / $-5810 / $-546 | 34.5 / 18.1 / 18.6 | 16.74 |
| VWAP reversion (2 SD -> VWAP) | $-1296 / $-646 / $-1052 | 24.4 / 45.9 / 14.6 | $-2592 / $-1291 / $-2104 | 25.4 / 45.9 / 14.7 | 11.81 |
| NR7 inside-day breakout | $0 / $-41 / $-20 | 91.1 / 100.0 / 26.5 | $0 / $-81 / $-39 | 92.9 / 100.0 / 26.5 | 4.74 |
| Bollinger squeeze breakout | $-115 / $-583 / $-45 | 67.0 / 75.4 / 31.0 | $-231 / $-1165 / $-90 | 67.0 / 75.4 / 31.0 | 6.74 |
| Opening gap fill | $-322 / $-43 / $-99 | 75.0 / 100.0 / 24.8 | $-645 / $-84 / $-197 | 75.0 / 100.0 / 25.0 | 6.52 |
| End-of-day momentum (last 30 min) | $-180 / $53 / $-217 | 69.6 / 84.7 / 21.6 | $-361 / $108 / $-435 | 69.6 / 84.7 / 21.6 | 9.22 |
| Connors RSI(2) 5m | $-231 / $-165 / $-377 | 68.7 / 64.4 / 13.3 | $-462 / $-330 / $-753 | 69.6 / 64.4 / 13.7 | 17.15 |
| VWAP trend pullback | $-531 / $-458 / $-828 | 31.9 / 46.6 / 16.1 | $-1062 / $-915 / $-1656 | 32.7 / 46.6 / 16.2 | 11.67 |


LIT + ATLAS alone run 4.7 trades a week (H1) / 3.9 (H2) / 5.0 (2021-25). Every add-on gets the book past 5 a week. Only Crabel stretch,
IB fade and RSI(2) 15m add money in both 2026 halves, and all three lose 2021-25 money or fail the PF bar.
IB fade shows the trap: +$753 / +$570 a month on the 25K in 2026, but -$321 a month over 2021-25 (PF 0.82, max DD -$41.8k at $400).
It also drops the 2026 pass-in-40 from 91% / 100% to 79% / 77%.

## Already in TESTED_AND_REJECTED (checked before the run)
- Opening Range Breakout 30 min: partly: ORB 2nd side after a failed break (E2 2026-11-13), OR high/low roots (strategy tree), allday
- VWAP reversion (2 SD -> VWAP): yes: VWAP reversion on low-VIX days (E2 2026-11-13), VWAP/band fades (scalp-mean-reversion)
- VWAP trend pullback: yes: VWAP pullback with trend (ATLAS new members 2026-11-18)
- Connors RSI(2) 5m: yes: Connors RSI(2) (famous published 2026-11-17; daily) + RSI fades (scalp-mean-reversion)
- Connors RSI(2) 15m: yes: Connors RSI(2) (famous published 2026-11-17)
- Donchian 20/10 breakout: no (only turtle-soup fades were tested)
- NR7 inside-day breakout: yes: Crabel NR7 / NR4 / NR7-ID (famous published 2026-11-17)
- Bollinger squeeze breakout: partly: 15m Keltner squeeze (ATLAS members), lunch-box squeeze (new-strategy hunt)
- Opening gap fill: yes: plain gap fade loses (E2 2026-11-13; G1 gap fade paper lead only)
- Initial Balance breakout: no (IB only as a scalp-mean-reversion level)
- Initial Balance fade: partly: IB as a scalp-mean-reversion fade level
- 9/21 EMA pullback in trend: partly: ATLAS's own EMA member is an EMA trend strategy (overlap expected)
- Keltner channel breakout: partly: 15m Keltner squeeze (ATLAS members)
- Crabel stretch: partly: ATR-stretch fades (scalp-mean-reversion)
- End-of-day momentum (last 30 min): yes: Gao intraday momentum (famous published 2026-11-17), last-half-hour (E2)
- Turnaround Tuesday: partly: weekday as a strategy-tree condition

## Verdict
All 16 are rejected. Added to `docs/TESTED_AND_REJECTED.md`. Crabel stretch stays a paper lead only: it is the one that is positive in all 3 spans,
and it could be re-checked when Nov-Dec 2026 data arrives (untouched, same rule). Nothing goes live.
