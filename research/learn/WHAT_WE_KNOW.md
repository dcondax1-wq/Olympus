# What each pillar has learned so far

Built 2026-11-24 11:49 UTC by `engine/market_learn.py` from 4184 backtest trades (the repo's own backtests on NQ futures data, costs in) + live / paper rows. Research only: nothing live changes.

How to read it: a lesson is a context bucket where the pillar did worse (or better) than its own average in ALL THREE spans (Jan-Jun 2026, Jul-Oct 2026, 2021-25). The chance line says how many such lessons you get with the results shuffled at random - if the real count is not clearly above it, the lessons are hints, not an edge.

**Now** (for 2026-11-21): trend regime (5-day ER 0.962), prior day big, VIX 25+ (VIX 35.89 on 2026-11-20).

## LIT (Zlarior)
- Losses Jan-Jun 2026 (33 trades, -$8,524): never worked 60.8%, worked then turned 33.5%, shaken out 0.0%, news 5.7%
- Losses Jul-Oct 2026 (20 trades, -$5,202): never worked 64.6%, worked then turned 31.0%, shaken out 4.3%, news 0.0%
- Losses 2021-25 (236 trades, -$98,882): never worked 67.1%, worked then turned 27.3%, shaken out 4.4%, news 1.2%
- Strong lessons (same side in all 3 spans, |z| >= 2.0): 0 found vs 0.5 with the results shuffled (p 1.0) - no better than chance, read them as hints
- By regime (avg R Jan-Jun / Jul-Oct / 2021-25): mixed 0.792 / 0.471 / -0.043; range 1.373 / 0.06 / -0.043; trend 0.658 / 1.631 / 0.095
- By VIX (avg R Jan-Jun / Jul-Oct / 2021-25): VIX 15-20 0.489 / 0.738 / -0.023; VIX 20-25 0.715 / None / -0.085; VIX 25+ 2.82 / None / 0.336; VIX <15 2.766 / 0.765 / -0.022
- LIT (Zlarior) does worse when: VIX 15-20. Avg R 0.489 / 0.738 / -0.023 (Jan-Jun / Jul-Oct / 2021-25, 297 trades), -$13,997 vs a normal trade, z -0.86 (weak)
- LIT (Zlarior) does worse when: London late 05-08. Avg R 0.701 / 0.425 / -0.044 (Jan-Jun / Jul-Oct / 2021-25, 164 trades), -$1,016 vs a normal trade, z -0.64 (weak)
- LIT (Zlarior) does worse when: range weeks (choppy 5 days) + VIX 15-20. Avg R 0.816 / 0.131 / -0.045 (Jan-Jun / Jul-Oct / 2021-25, 74 trades), -$6,066 vs a normal trade, z -0.64 (weak)
- LIT (Zlarior) does best when: trending weeks + London 02-05. Avg R 0.902 / 2.094 / 0.054 (Jan-Jun / Jul-Oct / 2021-25, 119 trades), +$10,320 vs a normal trade, z 0.84 (weak)
- LIT (Zlarior) does best when: a big overnight range. Avg R 0.875 / 1.478 / 0.035 (Jan-Jun / Jul-Oct / 2021-25, 136 trades), +$344 vs a normal trade, z 0.59 (weak)
- Today's read: trending weeks + VIX 25+: 25 past trades, avg R 0.495 vs 0.166 overall

## ATLAS
- Losses Jan-Jun 2026 (51 trades, -$12,724): never worked 60.3%, worked then turned 30.7%, shaken out 7.0%, news 2.1%
- Losses Jul-Oct 2026 (22 trades, -$4,746): never worked 50.1%, worked then turned 49.9%, shaken out 0.0%, news 0.0%
- Losses 2021-25 (707 trades, -$171,071): never worked 56.0%, worked then turned 36.4%, shaken out 7.0%, news 0.6%
- Strong lessons (same side in all 3 spans, |z| >= 2.0): 1 found vs 0.5 with the results shuffled (p 0.337) - no better than chance, read them as hints
- By regime (avg R Jan-Jun / Jul-Oct / 2021-25): mixed 0.958 / 0.813 / 0.046; range 0.988 / 0.399 / 0.015; trend 0.859 / 0.557 / 0.081
- By VIX (avg R Jan-Jun / Jul-Oct / 2021-25): VIX 15-20 1.128 / 0.868 / 0.142; VIX 20-25 0.172 / 0.994 / 0.007; VIX 25+ 0.888 / None / 0.137; VIX <15 -0.299 / -0.583 / -0.078
- ATLAS does worse when: Tuesdays. Avg R 0.248 / 0.593 / 0.002 (Jan-Jun / Jul-Oct / 2021-25, 290 trades), -$7,171 vs a normal trade, z -0.81 (weak)
- ATLAS does worse when: NY AM 09:30-11:30. Avg R 0.771 / 0.634 / 0.044 (Jan-Jun / Jul-Oct / 2021-25, 412 trades), -$2,053 vs a normal trade, z -0.2 (weak)
- ATLAS does best when: VIX 15-20 + London 02-05. Avg R 1.698 / 0.95 / 0.439 (Jan-Jun / Jul-Oct / 2021-25, 266 trades), +$29,694 vs a normal trade, z 3.4
- ATLAS does best when: mixed weeks + London 02-05. Avg R 0.999 / 1.156 / 0.303 (Jan-Jun / Jul-Oct / 2021-25, 226 trades), +$13,770 vs a normal trade, z 1.74 (weak)
- Today's read: trending weeks + VIX 25+: 52 past trades, avg R 0.085 vs 0.153 overall

## BLITZ
- Losses Jan-Jun 2026 (98 trades, -$8,815): never worked 70.6%, worked then turned 18.8%, shaken out 10.6%, news 0.0%
- Losses Jul-Oct 2026 (82 trades, -$8,295): never worked 71.7%, worked then turned 20.7%, shaken out 5.5%, news 2.1%
- Losses 2021-25 (929 trades, -$81,497): never worked 67.0%, worked then turned 16.1%, shaken out 16.2%, news 0.7%
- Strong lessons (same side in all 3 spans, |z| >= 2.0): 2 found vs 1.3 with the results shuffled (p 0.307) - no better than chance, read them as hints
- By regime (avg R Jan-Jun / Jul-Oct / 2021-25): mixed 0.041 / 0.164 / 0.035; range 0.233 / 0.035 / -0.001; trend 0.17 / 0.149 / 0.012
- By VIX (avg R Jan-Jun / Jul-Oct / 2021-25): VIX 15-20 0.188 / 0.054 / 0.018; VIX 20-25 0.031 / -0.157 / 0.031; VIX 25+ 0.093 / 0.892 / 0.053; VIX <15 None / 0.339 / -0.032
- BLITZ loses when: trending weeks + NY AM 09:30-11:30. Avg R -0.082 / -0.271 / -0.095 (Jan-Jun / Jul-Oct / 2021-25, 159 trades), -$4,611 vs a normal trade, z -2.19
- BLITZ loses when: after a big day + Tuesdays. Avg R -0.017 / -0.238 / -0.115 (Jan-Jun / Jul-Oct / 2021-25, 123 trades), -$2,449 vs a normal trade, z -2.04
- BLITZ does worse when: Tuesdays. Avg R 0.059 / 0.016 / -0.042 (Jan-Jun / Jul-Oct / 2021-25, 413 trades), -$3,809 vs a normal trade, z -1.53 (weak)
- BLITZ does best when: with the daily trend. Avg R 0.169 / 0.22 / 0.042 (Jan-Jun / Jul-Oct / 2021-25, 1189 trades), +$3,633 vs a normal trade, z 1.21 (weak)
- BLITZ does best when: trending weeks + NY PM 13:30-16. Avg R 0.189 / 0.41 / 0.041 (Jan-Jun / Jul-Oct / 2021-25, 429 trades), +$5,240 vs a normal trade, z 1.06 (weak)
- Today's read: trending weeks + VIX 25+: 185 past trades, avg R 0.153 vs 0.037 overall

## ORDER FLOW
- ORDER FLOW: knows nothing yet. Not ready: the tick recorder (NinjaTrader AddOn) is built, never compiled, OFF. 0 tick days verified.
- Prior from bar proxies: No tick data yet, so no OF numbers. Bar-proxy prior for OF3 (LVN rejection, stand-alone): 2021-25 155 trades PF 1.26 +$11,556 (0.71 a week, about $230 a month); 2026 H1 12 trades PF 1.10 +$326; H2 10 trades PF 4.56 +$4,990. 43 pre-registered bar tests, 0 pass.

## Shared (cross-pillar)
- ATLAS and BLITZ both do worse in Tuesdays (z ATLAS -0.81, BLITZ -1.53)
- LIT (Zlarior) and BLITZ both do better in a big overnight range (z LIT (Zlarior) 0.59, BLITZ 0.84)
- LIT (Zlarior) + ATLAS: 439 days both traded, both lost on 126 (123.7 if unrelated), daily $ correlation 0.297
- LIT (Zlarior) + BLITZ: 297 days both traded, both lost on 76 (73.3 if unrelated), daily $ correlation 0.006
- ATLAS + BLITZ: 406 days both traded, both lost on 128 (129.6 if unrelated), daily $ correlation 0.004

## Fixes tried (1 ever registered; bar = 0.05 / that count)
- 2026-11-24 BLITZ half the prior-day level 4R+ ahead: **rejected** (hold-out weeks -$633; 2021-25 net -$1,112; 2021-25 PF 1.06 -> 1.05)
