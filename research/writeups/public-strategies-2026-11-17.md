---
title: Famous published strategies on CME NQ - none beats LIT, none passes an MFFU eval in a way we can trust
family: other
date: 2026-11-17
status: rejected - nothing adopted, nothing built, nothing live changed
summary: Owner 2026-11-17 - "find other people's strategies that are successful and replicate them." Seven famous strategies with published multi-year records, coded the way their authors describe them (no tuning), plus at most 2 variants each - 22 cells, each scored on 2021-25, 2026 H1 and 2026 H2 (66 span cells), costs in. Gao intraday momentum, pre-FOMC drift, turn of the month, overnight drift, Connors RSI(2), time-series momentum (12-month and 20/60-day), Crabel NR7 / NR4. None makes money in all three spans with a t-stat above 1.2 except chance-level cells. The four that look best on paper (pre-FOMC, RSI(2), 12-month trend, overnight drift) all hold positions overnight, which MFFU does not allow (flat by 16:10 ET), and every one of them lost money in 2026 H2 or in 2021-25. The MFFU-legal versions lose or are no better than random days (turn-of-month day trades: placebo p 0.12-0.24). Daily correlation with LIT is about 0 for all of them, but there is no money to diversify with. LIT stays the only strategy.
runs: (no rl runs) research/quant/pub_strats.json
---

## For the owner (plain words)

| idea (who published it) | $ a month, 2021-25 / 2026 H1 / 2026 H2 | passes an MFFU eval? | verdict |
|---|---|---|---|
| **LIT (ours, for reference)** | **+$25 / +$5,562 / +$2,670** | yes, about half in 2 weeks (2026) | keep |
| Intraday momentum, first 30 min -> last 30 min (Gao et al. 2018) | -$437 / +$122 / +$247 | no (2021-25: 97% fail) | dead: wrong way round on NQ |
| Long the day before a Fed decision (Lucca & Moench 2015) | +$98 / -$8 / -$47 (1 micro) | not allowed (holds overnight); day-only version loses | worked 2021-25, gone since |
| Turn of the month, last day to day +3 (Lakonishok & Smidt) | -$21 / +$521 / +$1,123 (1 micro) | not allowed (overnight) | only 2026, not proven |
| Turn of the month as day trades (09:30-16:00, MFFU-legal) | +$100 / +$825 / +$339 | slowly: ~46-266 trading days, 26% fail in 2021-25 | random days do as well (luck) |
| Overnight drift, long 16:00 -> 09:30 (Cliff/Cooper/Gulen, Lou/Polk/Skouras) | +$165 / +$673 / -$163 (1 micro) | not allowed (overnight) | lost in H2, $10k drawdown |
| Connors RSI(2) dip-buying above the 200-day | +$128 / +$451 / -$174 (1 micro) | not allowed (overnight); day-only version loses | 0.15 trades a week, lost in H2 |
| 12-month trend following (Moskowitz, Ooi & Pedersen 2012) | +$226 / +$1,564 / -$834 (1 micro) | not allowed (holds a month) | lost in H2, $7.8k drawdown on 1 micro |
| 20/60-day trend (fast version) | -$108 / -$444 / -$940 | day-only version: no (84% fail) | dead |
| Crabel NR7 / NR4 narrow-range breakout | +$37 / +$47 / +$222 (NR7) | no (pass takes over a year) | too small to matter |

**Bottom line: nothing here beats what we have.** The famous edges either stopped working on NQ in 2025-26, never worked on
NQ in 2021-26, or need overnight holds that MFFU forbids. "1 micro" rows are 1 MNQ ($2 a point); a mini is 10x the $ and 10x
the drawdown. Nothing was built and nothing live changed.

## What was tested

- **Tool:** `tools/pub_strats.py` (re-run: `python -X utf8 tools/pub_strats.py`, then `... pub_strats.py extra` for the
  turn-of-month checks). Numbers: `research/quant/pub_strats.json`.
- **Data:** TradingView CME NQ1! 5m (`data/NQ_5m.csv`, additive back-adjusted so point moves are exact, sessions
  2021-11-08 to 2026-10-16) and ES1! 5m (`data/ES_5m.csv`, from 2025-04 only, so "2021-25" for ES = Apr-Dec 2025). Futures
  only, no Yahoo, no CFD. Daily "close" = the 15:55 price (so a rule can act on it before 16:00).
- **Costs:** $1.90 a micro round trip + 1 tick slippage each way (1.45 NQ points a micro a trade).
- **Size:** MFFU-legal day trades risk $500 against a volatility stop max(10, 1.5 x ATR20 x sqrt(hours held / 23)) points,
  1-40 micros (for a 6.5-hour hold this is 1 micro on 2026 NQ: a normal day already moves ~$600 a micro). No stop is
  placed unless the published rule has one (NR7: the far side of the narrow day). Strategies that hold overnight are shown
  at 1 micro: MFFU closes every position by 16:10 ET (`docs/CLAUDE_REFERENCE.md`, flat_by), so they cannot run on an MFFU
  account at all.
- **Evals:** a new MFFU 50K eval started on every session of the span with the strategy's daily $: Builder = $3,000 target,
  $2,000 end-of-day trailing floor (locks at +$100); Rapid EOD = the same + best day at most 30% of the profit when it
  passes. "1 month" = within 21 sessions; "ever" = before the data ends (late-H2 starts are unresolved).
- **LIT correlation:** daily $ against LIT's live-rule days (`research/lab/backtest_live.json`). All 22 cells sit at
  -0.04 to +0.04 over 2021-26 (2026 halves -0.17 to +0.21): uncorrelated, but uncorrelated with no edge is worth nothing.
- **Already done before** (`quant-anomalies.md`, 2026-10-23): Gao, overnight drift, turn of the month and pre-FOMC as point
  tests with placebos. The as-published cells here agree with it (same signs, same story). New here: the MFFU-legal
  versions, win % / PF / drawdown / eval speed, and the Connors RSI(2), time-series momentum and Crabel families.

## Results (all 22 cells x 3 spans)

t = t-stat of the points per trade (|t| < 2 is not evidence). Eval columns are pass % / fail %, median sessions to a pass.

| cell | MFFU-legal | span | trades/wk | win % | PF | net $ | $/mo | max DD $ | t | corr LIT | Builder 1-mo pass/fail % | Builder ever pass/fail, median days | Rapid ever pass/fail, median days |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| gao_pub | yes | 2021-25 | 5.0 | 46.9 | 0.82 | -21,461 | -437 | -23,174 | -2.21 | -0.02 | 0.0/24.4 | 3.0/97.0, 67 | 2.0/98.0, 66 |
| gao_pub | yes | 2026H1 | 5.0 | 52.0 | 1.07 | 713 | 122 | -3,713 | 0.76 | 0.08 | 5.7/13.0 | 75.6/13.8, 54 | 75.6/13.8, 54 |
| gao_pub | yes | 2026H2 | 5.0 | 44.7 | 1.21 | 894 | 247 | -1,429 | 0.46 | -0.09 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| gao_r12 | yes | 2021-25 | 5.0 | 48.0 | 0.9 | -11,813 | -241 | -14,624 | -1.22 | -0.0 | 1.7/20.8 | 10.3/89.7, 54 | 4.5/95.5, 58 |
| gao_r12 | yes | 2026H1 | 5.0 | 51.2 | 1.05 | 548 | 94 | -4,184 | 0.93 | 0.09 | 12.2/13.0 | 78.9/14.6, 57 | 78.9/14.6, 57 |
| gao_r12 | yes | 2026H2 | 5.0 | 46.1 | 1.22 | 939 | 259 | -1,429 | 0.5 | -0.09 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| gao_fade | yes | 2021-25 | 5.0 | 49.3 | 0.98 | -2,649 | -54 | -16,901 | -0.19 | -0.0 | 0.9/19.0 | 32.2/67.8, 67 | 31.5/68.5, 78 |
| gao_fade | yes | 2026H1 | 5.0 | 45.5 | 1.14 | 1,431 | 244 | -1,895 | 0.14 | -0.16 | 2.4/0.0 | 5.7/94.3, 60 | 5.7/94.3, 60 |
| gao_fade | yes | 2026H2 | 5.0 | 55.3 | 1.01 | 24 | 7 | -2,030 | -0.38 | 0.02 | 0.0/0.0 | 0.0/18.4, - | 0.0/18.4, - |
| fomc_pub | no | 2021-25 | 0.16 | 66.7 | 3.32 | 4,790 | 98 | -924 | 2.43 | -0.02 | n/a | n/a | n/a |
| fomc_pub | no | 2026H1 | 0.16 | 50.0 | 0.87 | -49 | -8 | -475 | -0.1 | -0.17 | n/a | n/a | n/a |
| fomc_pub | no | 2026H2 | 0.13 | 50.0 | 0.68 | -168 | -47 | -551 | 0.0 | -0.0 | n/a | n/a | n/a |
| fomc_rth | yes | 2021-25 | 0.16 | 51.5 | 1.45 | 728 | 15 | -444 | 0.86 | -0.03 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| fomc_rth | yes | 2026H1 | 0.16 | 25.0 | 0.12 | -390 | -67 | -390 | -1.88 | -0.13 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| fomc_rth | yes | 2026H2 | 0.13 | 50.0 | 0.28 | -296 | -82 | -409 | 0.0 | 0.01 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| fomc_two | yes | 2021-25 | 0.32 | 51.5 | 1.0 | -20 | 0 | -1,338 | -0.01 | -0.0 | 0.0/0.0 | 0.0/100.0, - | 0.0/100.0, - |
| fomc_two | yes | 2026H1 | 0.33 | 50.0 | 0.18 | -1,186 | -202 | -1,369 | -1.14 | 0.01 | 0.0/0.0 | 0.0/42.3, - | 0.0/42.3, - |
| fomc_two | yes | 2026H2 | 0.26 | 25.0 | 0.14 | -700 | -193 | -814 | -1.44 | 0.08 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| tom_pub | no | 2021-25 | 0.24 | 53.1 | 0.94 | -1,024 | -21 | -5,309 | -0.18 | 0.03 | n/a | n/a | n/a |
| tom_pub | no | 2026H1 | 0.24 | 83.3 | 2.53 | 3,052 | 521 | -2,641 | 0.82 | 0.09 | n/a | n/a | n/a |
| tom_pub | no | 2026H2 | 0.26 | 75.0 | 21.96 | 4,064 | 1,123 | -1,952 | 1.49 | -0.08 | n/a | n/a | n/a |
| tom_rth | yes | 2021-25 | 0.96 | 57.4 | 1.18 | 4,918 | 100 | -4,240 | 0.91 | -0.01 | 0.0/0.0 | 74.1/25.9, 266 | 74.1/25.9, 269 |
| tom_rth | yes | 2026H1 | 0.98 | 70.8 | 2.51 | 4,830 | 825 | -1,822 | 1.88 | 0.05 | 0.0/0.0 | 67.5/0.0, 46 | 51.2/0.0, 54 |
| tom_rth | yes | 2026H2 | 0.99 | 53.3 | 1.45 | 1,228 | 339 | -1,516 | 0.52 | -0.09 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| tom_pub_es | no | 2025 (Apr-Dec) | 0.22 | 62.5 | 2.96 | 1,081 | 128 | -824 | 1.33 | - | n/a | n/a | n/a |
| tom_pub_es | no | 2026H1 | 0.24 | 50.0 | 2.92 | 1,380 | 236 | -964 | 0.88 | - | n/a | n/a | n/a |
| tom_pub_es | no | 2026H2 | 0.26 | 100.0 | - | 2,502 | 691 | -479 | 2.41 | - | n/a | n/a | n/a |
| on_pub | no | 2021-25 | 5.0 | 52.2 | 1.08 | 8,102 | 165 | -10,204 | 0.87 | 0.01 | n/a | n/a | n/a |
| on_pub | no | 2026H1 | 5.0 | 54.5 | 1.2 | 3,940 | 673 | -4,998 | 0.73 | 0.08 | n/a | n/a | n/a |
| on_pub | no | 2026H2 | 5.0 | 48.7 | 0.96 | -591 | -163 | -2,738 | -0.14 | -0.04 | n/a | n/a | n/a |
| on_ls | no | 2021-25 | 10.0 | 49.0 | 1.02 | 3,803 | 77 | -18,441 | 0.24 | 0.04 | n/a | n/a | n/a |
| on_ls | no | 2026H1 | 10.0 | 50.4 | 0.97 | -1,228 | -210 | -11,590 | -0.15 | 0.02 | n/a | n/a | n/a |
| on_ls | no | 2026H2 | 10.0 | 53.3 | 1.06 | 1,676 | 463 | -4,200 | 0.28 | 0.0 | n/a | n/a | n/a |
| on_dayshort | yes | 2021-25 | 5.0 | 45.9 | 0.97 | -4,299 | -88 | -14,896 | -0.33 | 0.04 | 6.4/23.2 | 21.7/78.3, 34 | 13.3/86.7, 33 |
| on_dayshort | yes | 2026H1 | 5.0 | 46.3 | 0.82 | -5,168 | -882 | -11,301 | -0.88 | -0.05 | 18.7/56.9 | 25.2/74.8, 13 | 21.1/76.4, 25 |
| on_dayshort | yes | 2026H2 | 5.0 | 57.9 | 1.17 | 2,267 | 626 | -3,859 | 0.54 | 0.05 | 11.8/40.8 | 11.8/61.8, 14 | 3.9/69.7, 19 |
| rsi2_pub | no | 2021-25 | 0.14 | 65.5 | 2.5 | 6,263 | 128 | -2,607 | 1.9 | -0.01 | n/a | n/a | n/a |
| rsi2_pub | no | 2026H1 | 0.16 | 100.0 | - | 2,642 | 451 | -1,854 | 3.62 | 0.01 | n/a | n/a | n/a |
| rsi2_pub | no | 2026H2 | 0.33 | 40.0 | 0.73 | -630 | -174 | -1,891 | -0.27 | 0.06 | n/a | n/a | n/a |
| rsi2_rth | yes | 2021-25 | 0.48 | 51.5 | 0.86 | -2,337 | -48 | -3,801 | -0.53 | -0.02 | 0.0/6.2 | 0.1/99.9, 122 | 0.1/99.9, 122 |
| rsi2_rth | yes | 2026H1 | 0.45 | 36.4 | 1.06 | 189 | 32 | -2,040 | 0.07 | -0.02 | 0.0/15.4 | 0.0/100.0, - | 0.0/100.0, - |
| rsi2_rth | yes | 2026H2 | 1.25 | 36.8 | 0.52 | -2,450 | -677 | -2,450 | -1.03 | -0.02 | 0.0/0.0 | 0.0/23.7, - | 0.0/23.7, - |
| rsi2_ls | no | 2021-25 | 0.18 | 64.9 | 2.53 | 8,461 | 172 | -3,196 | 2.2 | -0.03 | n/a | n/a | n/a |
| rsi2_ls | no | 2026H1 | 0.16 | 100.0 | - | 2,642 | 451 | -1,854 | 3.62 | 0.01 | n/a | n/a | n/a |
| rsi2_ls | no | 2026H2 | 0.33 | 40.0 | 0.73 | -630 | -174 | -1,891 | -0.27 | 0.06 | n/a | n/a | n/a |
| tsmom12_pub | no | 2021-25 | 0.18 | 57.9 | 1.54 | 11,101 | 226 | -7,846 | 1.09 | -0.02 | n/a | n/a | n/a |
| tsmom12_pub | no | 2026H1 | 0.24 | 50.0 | 3.19 | 9,158 | 1,564 | -6,463 | 0.93 | 0.09 | n/a | n/a | n/a |
| tsmom12_pub | no | 2026H2 | 0.26 | 50.0 | 0.56 | -3,017 | -834 | -6,352 | -0.48 | -0.06 | n/a | n/a | n/a |
| tsmom_fast | no | 2021-25 | 0.1 | 40.0 | 0.78 | -5,284 | -108 | -17,861 | -0.43 | 0.03 | n/a | n/a | n/a |
| tsmom_fast | no | 2026H1 | 0.16 | 50.0 | 0.27 | -2,599 | -444 | -7,888 | -0.85 | 0.04 | n/a | n/a | n/a |
| tsmom_fast | no | 2026H2 | 0.33 | 20.0 | 0.54 | -3,402 | -940 | -11,147 | -0.55 | 0.01 | n/a | n/a | n/a |
| tsmom_fast_rth | yes | 2021-25 | 4.78 | 49.4 | 0.86 | -22,031 | -449 | -28,788 | -1.75 | 0.01 | 2.5/33.8 | 16.2/83.8, 49 | 16.0/84.0, 51 |
| tsmom_fast_rth | yes | 2026H1 | 5.0 | 52.0 | 0.98 | -578 | -99 | -5,120 | -0.1 | 0.08 | 23.6/65.0 | 26.0/74.0, 15 | 25.2/74.0, 15 |
| tsmom_fast_rth | yes | 2026H2 | 5.0 | 52.6 | 0.9 | -1,568 | -433 | -2,898 | -0.37 | 0.01 | 2.6/28.9 | 2.6/68.4, 8 | 0.0/68.4, - |
| tsmom_fast_es | no | 2025 (Apr-Dec) | 0.0 | - | - | 0 | 0 | -1,846 | 0.0 | - | n/a | n/a | n/a |
| tsmom_fast_es | no | 2026H1 | 0.08 | 50.0 | 2.97 | 1,786 | 305 | -4,174 | 0.0 | - | n/a | n/a | n/a |
| tsmom_fast_es | no | 2026H2 | 0.2 | 33.3 | 0.75 | -459 | -127 | -2,651 | -0.2 | - | n/a | n/a | n/a |
| nr7_pub | yes | 2021-25 | 0.78 | 50.0 | 1.08 | 1,824 | 37 | -3,042 | 0.61 | -0.07 | 0.0/0.0 | 4.5/79.5, 361 | 3.4/80.3, 365 |
| nr7_pub | yes | 2026H1 | 0.53 | 46.2 | 1.14 | 277 | 47 | -1,181 | 0.2 | 0.21 | 0.0/0.0 | 0.8/0.0, 117 | 0.0/0.0, - |
| nr7_pub | yes | 2026H2 | 0.66 | 50.0 | 1.69 | 805 | 222 | -923 | 0.6 | -0.04 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| nr4 | yes | 2021-25 | 1.22 | 53.2 | 1.17 | 5,522 | 112 | -4,057 | 1.17 | -0.03 | 0.0/0.5 | 52.4/47.6, 188 | 51.4/48.6, 195 |
| nr4 | yes | 2026H1 | 1.06 | 53.8 | 1.06 | 284 | 49 | -2,254 | 0.12 | 0.19 | 0.0/3.3 | 17.1/22.8, 50 | 0.8/22.8, 78 |
| nr4 | yes | 2026H2 | 1.12 | 47.1 | 1.08 | 188 | 52 | -875 | 0.11 | -0.03 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| nr7_id | yes | 2021-25 | 0.14 | 41.4 | 0.55 | -2,686 | -55 | -3,836 | -1.26 | -0.05 | 0.0/0.0 | 0.0/29.4, - | 0.0/29.4, - |
| nr7_id | yes | 2026H1 | 0.04 | 0.0 | 0.0 | -19 | -3 | -19 | 0.0 | 0.03 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |
| nr7_id | yes | 2026H2 | 0.26 | 75.0 | 22.53 | 1,494 | 413 | -69 | 1.6 | -0.06 | 0.0/0.0 | 0.0/0.0, - | 0.0/0.0, - |

Cell rules (all fixed before the run):
- **gao_pub:** sign of prev 16:00 -> 10:00; trade 15:30 -> 16:00. **gao_r12:** sign of that return + the 15:00-15:30 return
  (the paper's second predictor). **gao_fade:** fade prev close -> 15:30 in the last half hour (pre-registered from the
  2025-26 lead in `quant-anomalies.md`; it was spotted on 2025-26, so 2021-25 is its real test: -$54 a month, dead).
- **fomc_pub:** long 14:00 the day before -> 13:55 on statement day. **fomc_rth:** 09:30 -> 13:55 statement day.
  **fomc_two:** day-before 09:30 -> 16:00 + statement day 09:30 -> 13:55.
- **tom_pub:** 16:00 of day -2 -> 16:00 of day +3. **tom_rth:** day-trade 09:30 -> 16:00 on days -1, +1, +2, +3.
  **tom_pub_es:** tom_pub on ES micros ($5 a point).
- **on_pub:** long 16:00 -> 09:30. **on_ls:** plus short 09:30 -> 16:00. **on_dayshort:** only the short day leg.
- **rsi2_pub:** RSI(2, Wilder) < 10 and close > 200-day SMA -> long at the close; out at the first close > 5-day SMA.
  **rsi2_rth:** the same days in the trade, but only 09:30 -> 15:55 of each. **rsi2_ls:** plus the mirror short (RSI(2)
  > 90 under the 200-day): it never fired in 2026.
- **tsmom12_pub:** at each month end, long (short) for a month if the 12-month change is up (down). **tsmom_fast:** long
  when SMA20 > SMA60, else short, close to close. **tsmom_fast_rth:** that signal traded 09:30 -> 15:55 each day.
  **tsmom_fast_es:** tsmom_fast on ES. (12-month on ES is impossible: ES data starts 2025-04.)
- **nr7_pub:** after the narrowest 09:30-16:00 range of 7 days, next day stop entry 1 tick past its high / low, stop 1 tick
  past the other side, out 16:00 (a bar touching both sides first = no trade). **nr4:** 4-day version. **nr7_id:** NR7
  that is also an inside day.

## The one cell that is positive everywhere: turn-of-month day trades (tom_rth)

It made +$100 / +$825 / +$339 a month (2021-25 / H1 / H2) at 1 micro, but:
- **Placebo:** long 09:30 -> 16:00 on random days (same count per month, same size), 1,000 draws: luck does at least as well
  23.5% (2021-25), 11.8% (H1), 22.2% (H2) of the time. It is NQ's upward drift, not the month turn.
- **Every-day long 09:30 -> 16:00** (the control): -$34 / +$761 / -$748 a month. 2026 H1 was simply an up half.
- **Eval:** at 1 micro it needs 46-266 trading days to pass. At 3x size the Builder passes 33% / 65% / 55% (2021-25 / H1 /
  H2) but fails 67% in 2021-25; the Rapid best-day rule passes 0% of H2 starts.
- Verdict: chance level. Rejected.

## Not proven (works in one period only)

- **Pre-FOMC drift:** t 2.4 in 2021-25 (+$4,790 on 33 meetings, 1 micro), -$217 on the 6 meetings of 2026. Same as the
  October study. Also not MFFU-legal.
- **Connors RSI(2):** +$6,263 on 29 trades 2021-25 (t 1.9), 4 of 4 winners in H1, lost in H2 (2 of 5). 0.15 trades a week.
  Not MFFU-legal; the day-only version loses in all three spans.
- **12-month trend:** +$11.1k 2021-25, +$9.2k H1, -$3.0k H2, drawdowns of $6-8k on ONE micro. Not MFFU-legal.
- **Turn of the month as published** and on ES: lost in 2021-25 on NQ, won 2025-26 on both (10-16 month ends).

## Count

22 cells x 3 spans = 66 span cells, plus 1 control (every-day long RTH), 1 placebo (1,000 draws x 3 spans) and 2 eval
sizings for tom_rth. At |t| >= 2 we would expect about 3 of 66 by luck; we got 5 (gao_pub 2021-25 at t -2.2 with the WRONG
sign, fomc_pub 2021-25, rsi2_ls 2021-25, rsi2_pub and rsi2_ls 2026 H1 = the same 4 trades), none repeated in another span. Paper research
only: no engine, model, live or UI file was touched.
