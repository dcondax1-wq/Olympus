---
title: Popular ICT / SMC strategies on CME NQ, run exactly as taught (Silver Bullet, Judas, Asia sweep, London breakout, PDH/PDL sweep, NY open FVG, PO3, ICT 2022, Turtle Soup, Unicorn)
family: other
date: 2026-11-23
status: rejected - 0 of 10 pass (PF > 1 in 2026 H1, 2026 H2 and 2021-25 AND Holm p < 0.05); best raw p 0.17, every Holm p = 1.0. Nothing adopted, nothing live changed; ICT 2022 is the only add-on that adds $ in both 2026 halves, but it loses 2021-25, doubles drawdown and is chance-level
summary: Ten famous ICT/SMC NQ day-trading setups coded once from their public textbook rules, pre-registered before any run (research/writeups/specs/popular-ict-2026-11-23.md), no tuning. TradingView CME NQ1! 5m, stop 1 tick beyond the swing, fixed 2R, flat 15:55, LIT's $800 sizing, $1.90/micro + 1-tick slippage. Scored on 2026 Jan-Jun, Jul-Oct and 2021-25 with trades/week, win %, PF, $/month, max DD, daily correlation and trade overlap with LIT, and as an add-on to LIT on a Rapid EOD 25K and 50K. None has an edge after a 10-way multiple-testing correction; 9 of 10 lose money in 2026 H1, the half LIT was picked on. Several add 2-4 trades a week to reach the 5+/week target, but every one that does so adds more drawdown than money.
runs: (no rl runs) research/lab/popular_ict.json, research/lab/popular_ict_full.json
---

## For the owner (plain words)

**None of the ten famous ICT setups makes money we can trust on NQ futures.** Coded exactly as taught, with costs in, 9 of 10
lose money in Jan-Jun 2026 and 6 of 10 lose in 2021-25. After allowing for the fact that we tested 10 things at once, not one
is better than a coin flip. Adding any of them to LIT does not make a Rapid account pay faster in a way that holds.

| setup (as taught) | $ a month alone: 2026 Jan-Jun / Jul-Oct / 2021-25 | trades a week | as a LIT add-on (Rapid 50K) | verdict |
|---|---|---:|---|---|
| **LIT (ours, reference)** | **+$5,562 / +$2,670 / +$25** | 2.4-3.1 | - | keep |
| Power of 3 / AMD | -$14 / +$79 / +$2 | 0.1-0.2 | changes nothing (too rare) | reject |
| Judas Swing | -$26 / +$223 / -$22 | 0.9-2.2 | +$196/mo in Jul-Oct, -$27 in Jan-Jun, eval fails 1.6% -> 20% in Jan-Jun | reject |
| London breakout | -$79 / +$41 / +$98 | 0.1-3.0 | almost nothing in 2026 (2026 stops too wide for 1 micro) | reject |
| Turtle Soup (20-day) | -$217 / +$311 / +$139 | 0.1-0.2 | too rare (13 trades in 2026) | reject |
| **ICT 2022 model** | **+$333 / +$505 / -$274** | 2.1-2.6 | **+$369 / +$681 a month in 2026, 5/wk, but max DD $2.2k -> $4.8k and Jan-Jun eval fails 1.6% -> 34%; loses 2021-25** | reject (paper-watch only) |
| NY open FVG retrace | -$568 / -$534 / -$350 | 1.7-2.4 | costs money every span | reject |
| Silver Bullet | -$1,029 / -$332 / +$88 | 2.0-3.0 | costs $1,000/mo in Jan-Jun | reject |
| Unicorn | -$1,057 / +$618 / -$704 | 1.8-2.1 | -$1,070/mo Jan-Jun, +$1,000/mo Jul-Oct: a coin flip | reject |
| Previous-day high/low sweep | -$1,750 / -$188 / -$325 | 1.3-2.3 | costs money every span | reject |
| Asian range sweep | -$3,994 / -$1,175 / -$1,279 | 4.2-4.3 | worst: eval fails 81% in Jan-Jun | reject |

**Bottom line:** keep LIT as it is. The "5+ trades a week" target cannot be bought with these setups: the only ones that add
2+ trades a week (ICT 2022, Silver Bullet, Unicorn, Asia sweep, NY open FVG, PDH/PDL) all raise the drawdown more than the
money, and none is better than chance. Nothing was built, nothing is armed, no live file changed.

## Already tested before? (checked before the run; all retested here untuned)

| strategy | before |
|---|---|
| Power of 3 / AMD | partly - ICT_REPORT 2026-10-16 as a LIT filter / gate / size (noise, slightly negative); never standalone |
| Judas Swing (London, midnight open) | no - only named as a concept in the LIT report coverage notes |
| London breakout (19:00-02:00 box) | partly - DAPHNE tree London 02:00-05:00 break roots (RTH entries); not the 02:00 OCO box |
| Turtle Soup (20-day false breakout) | partly - ICT_REPORT 2026-10-16 as a LIT trap feature (-0.17R shadows); never standalone |
| 2022 ICT model (sweep + MSS + FVG) | yes - 'Published models as taught' (TESTED_AND_REJECTED): PF ~1 |
| NY open FVG retrace (09:30-10:00) | partly - Mech/IFVG and the opening-drive tests; not the first-FVG 09:30-10:00 rule |
| Silver Bullet (10-11 ET FVG) | yes - 'Published models as taught' (TESTED_AND_REJECTED): 0.2-1.5 trades/wk, PF ~1 |
| Unicorn (breaker + FVG) | no - only named as a concept in the LIT report coverage notes |
| Previous-day high/low sweep and reversal | partly - E2 2026-11-13 (PDH/PDL sweep + climax volume) and the DAPHNE tree roots (fade 09:50-15:00) |
| Asian range sweep and reversal | partly - DAPHNE tree roots (Asia fade, RTH entries only); not the 00:00-11:00 version |

Same story as before where it overlaps: "Published models as taught" (Silver Bullet, ICT 2022) had PF ~1; PO3 and Turtle Soup
as LIT filters were noise to slightly negative; the DAPHNE tree's Asia / London / PDH-PDL roots held out of sample at chance.

## How it was tested (fixed before the first run)

- **Rules:** one version each, written and committed before any run: `research/writeups/specs/popular-ict-2026-11-23.md`
  (commit "pre-registered rules"). Tool `tools/popular_ict.py` (re-run: `python -X utf8 tools/popular_ict.py`, 7 s).
- **Data:** TradingView CME NQ1! 5-minute bars (`data/NQ_5m.csv`, back-adjusted, futures only). 5m everywhere (1m exists only
  from 2025-12-29, so 5m keeps 2021-25 and 2026 comparable). ET clock with DST; session = 18:00-17:00.
- **Spans:** 2026 H1 = Jan 1 - Jun 30; 2026 H2 = Jul 1 - Oct 31 (the spec said "to Oct 16, data end"; the bars actually run to
  Nov 19, so H2 is the full Jul-Oct the order asked for; no rule changed). LIT comparisons stop at 2026-10-16, where the LIT
  replay (`research/lab/backtest_live.json`) ends. 2021-25 = 2021-11-08 .. 2025-12-31.
- **Trade rules shared by all:** stop 1 tick beyond the named swing / sweep extreme; fixed 2R target (none of the ten public
  write-ups gives a single mechanical target, so 2R per the order); one trade a day; flat 15:55 ET; FVG entries are limits at
  the near edge of the gap.
- **Fills:** conservative: if one 5m bar holds both stop and target, the stop counts (this hit 0-1.9% of trades, so it moves
  nothing). **Costs:** $1.90 a micro round trip, 1 tick slippage on market / stop entries and on stop and 15:55 exits.
- **Size like LIT:** $800 risk up to a 20-pt stop, then 800 x 20 / stop; micros rounded down, max 40; under 1 micro = no
  trade. On 2026 NQ (~25-30k) this skips every stop above ~89 pts: that is why London breakout, PO3 and Turtle Soup trade
  almost never in 2026 (the "skipped" column).
- **Multiple testing:** one-sided t-test that the mean R per trade > 0, pooled over all spans and on 2026 alone; Holm
  (family-wise) and Benjamini-Hochberg (false discovery) across the 10. Keep rule: PF > 1 in all three spans AND Holm < 0.05.
- **LIT relation:** daily $ correlation on LIT's replay days; overlap = share of the strategy's trades on a day LIT traded,
  open at the same time as a LIT trade, and same side at the same time.
- **Add-on:** LIT's replay daily $ (live rules, $800 sizing) plus the add-on's daily $. Rapid EOD 50K: both full size, add-on
  max 30 micros, $3,000 target, $2,000 EOD trailing (locks at +$100), best day <= 30% of the profit, min 4 days. Rapid EOD
  25K: LIT trades at half the micros (rounded down), add-on at half risk, max 20 micros, $1,500 / $1,000. An eval is started on
  every session of the span and run to pass / fail / data end. **Caveat:** this is flat research sizing, not the bot's
  room-sized Rapid preset (`tools/money/rapid25.py`), so the absolute pass % is low (LIT's big days hit the 30% best-day rule)
  and late-H2 starts run out of data; read the columns as "with vs without", not as the real pass rate.

## Results

### A. Each strategy alone (1 trade a day max, LIT sizing, costs in)

| rank | strategy | span | trades/wk | win % | PF | $/month | max DD $ | avg R | t | skipped (stop > ~89 pts) |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Power of 3 / AMD | 2026H1 | 0.12 | 33.3 | 0.75 | -14 | -342 | 0.18 | 0.2 | 14 |
|  |  | 2026H2 | 0.11 | 50.0 | 3.16 | 79 | -152 | 0.484 | 0.0 | 10 |
|  |  | 2021-25 | 0.17 | 44.4 | 1.02 | 2 | -1,352 | 0.191 | 0.83 | 30 |
| 2 | Judas Swing (London, midnight open) | 2026H1 | 1.33 | 35.3 | 0.98 | -26 | -2,939 | 0.031 | 0.12 | 17 |
|  |  | 2026H2 | 0.85 | 46.7 | 1.36 | 223 | -1,107 | 0.376 | 0.94 | 11 |
|  |  | 2021-25 | 2.17 | 36.3 | 0.99 | -22 | -12,765 | 0.028 | 0.43 | 36 |
| 3 | London breakout (19:00-02:00 box) | 2026H1 | 0.51 | 23.1 | 0.72 | -79 | -1,298 | -0.323 | -0.89 | 87 |
|  |  | 2026H2 | 0.11 | 50.0 | 1.95 | 41 | -179 | 0.488 | 0.0 | 70 |
|  |  | 2021-25 | 3.02 | 35.5 | 1.04 | 98 | -15,626 | 0.016 | 0.3 | 274 |
| 4 | Turtle Soup (20-day false breakout) | 2026H1 | 0.12 | 0.0 | 0.0 | -217 | -1,321 | -1.033 | -74.0 | 3 |
|  |  | 2026H2 | 0.06 | 100.0 | no loss | 311 | 0 | 1.96 | 0.0 | 6 |
|  |  | 2021-25 | 0.23 | 42.0 | 1.48 | 139 | -4,566 | 0.219 | 1.05 | 21 |
| 5 | 2022 ICT model (sweep + MSS + FVG) | 2026H1 | 2.07 | 37.7 | 1.12 | 333 | -6,326 | 0.069 | 0.34 | 17 |
|  |  | 2026H2 | 2.39 | 31.0 | 1.26 | 505 | -2,399 | -0.097 | -0.45 | 11 |
|  |  | 2021-25 | 2.64 | 34.8 | 0.94 | -274 | -26,149 | -0.032 | -0.55 | 33 |
| 6 | NY open FVG retrace (09:30-10:00) | 2026H1 | 1.8 | 26.1 | 0.68 | -568 | -5,533 | -0.243 | -1.24 | 20 |
|  |  | 2026H2 | 1.65 | 27.6 | 0.66 | -534 | -2,812 | -0.288 | -1.23 | 13 |
|  |  | 2021-25 | 2.43 | 33.1 | 0.89 | -350 | -22,966 | -0.075 | -1.25 | 38 |
| 7 | Silver Bullet (10-11 ET FVG) | 2026H1 | 2.34 | 23.3 | 0.47 | -1,029 | -7,464 | -0.357 | -2.28 | 24 |
|  |  | 2026H2 | 1.99 | 31.4 | 0.8 | -332 | -3,807 | -0.124 | -0.55 | 21 |
|  |  | 2021-25 | 2.96 | 38.2 | 1.03 | 88 | -15,908 | 0.055 | 0.99 | 72 |
| 8 | Unicorn (breaker + FVG) | 2026H1 | 2.03 | 25.0 | 0.66 | -1,057 | -7,941 | -0.279 | -1.57 | 6 |
|  |  | 2026H2 | 1.76 | 45.2 | 1.31 | 618 | -2,583 | 0.158 | 0.62 | 4 |
|  |  | 2021-25 | 2.09 | 31.8 | 0.82 | -704 | -45,441 | -0.113 | -1.73 | 16 |
| 9 | Previous-day high/low sweep and reversal | 2026H1 | 1.64 | 26.2 | 0.34 | -1,750 | -10,949 | -0.238 | -1.14 | 26 |
|  |  | 2026H2 | 1.31 | 30.4 | 0.89 | -188 | -4,057 | -0.124 | -0.42 | 18 |
|  |  | 2021-25 | 2.28 | 35.8 | 0.89 | -325 | -34,466 | -0.042 | -0.67 | 90 |
| 10 | Asian range sweep and reversal | 2026H1 | 4.3 | 22.7 | 0.54 | -3,994 | -24,345 | -0.443 | -3.61 | 1 |
|  |  | 2026H2 | 4.26 | 33.3 | 0.84 | -1,175 | -9,292 | -0.085 | -0.51 | 2 |
|  |  | 2021-25 | 4.16 | 32.1 | 0.82 | -1,279 | -75,859 | -0.212 | -4.42 | 6 |

### B. Multiple-testing correction (10 strategies; one-sided test that the mean R a trade > 0)

| strategy | p (all spans pooled) | Holm | BH (FDR) | p (2026 only) | Holm (2026) | tested before? | verdict |
|---|---:|---:|---:|---:|---:|---|---|
| Power of 3 / AMD | 0.1716 | 1.0 | 0.8386 | 0.3324 | 1.0 | partly - ICT_REPORT 2026-10-16 as a LIT filter / gate / size (noise, slightly negative); never standalone | reject - loses in 2026H1 |
| Judas Swing (London, midnight open) | 0.2707 | 1.0 | 0.8386 | 0.2593 | 1.0 | no - only named as a concept in the LIT report coverage notes | reject - loses in 2026H1, 2021-25 |
| London breakout (19:00-02:00 box) | 0.4193 | 1.0 | 0.8386 | 0.7277 | 1.0 | partly - DAPHNE tree London 02:00-05:00 break roots (RTH entries); not the 02:00 OCO box | reject - loses in 2026H1 |
| Turtle Soup (20-day false breakout) | 0.1812 | 1.0 | 0.8386 | 0.6482 | 1.0 | partly - ICT_REPORT 2026-10-16 as a LIT trap feature (-0.17R shadows); never standalone | reject - loses in 2026H1 |
| 2022 ICT model (sweep + MSS + FVG) | 0.698 | 1.0 | 1.0 | 0.5129 | 1.0 | yes - 'Published models as taught' (TESTED_AND_REJECTED): PF ~1 | reject - loses in 2021-25 |
| NY open FVG retrace (09:30-10:00) | 0.961 | 1.0 | 1.0 | 0.9587 | 1.0 | partly - Mech/IFVG and the opening-drive tests; not the first-FVG 09:30-10:00 rule | reject - loses in 2026H1, 2026H2, 2021-25 |
| Silver Bullet (10-11 ET FVG) | 0.4056 | 1.0 | 0.8386 | 0.9821 | 1.0 | yes - 'Published models as taught' (TESTED_AND_REJECTED): 0.2-1.5 trades/wk, PF ~1 | reject - loses in 2026H1, 2026H2 |
| Unicorn (breaker + FVG) | 0.9714 | 1.0 | 1.0 | 0.7835 | 1.0 | no - only named as a concept in the LIT report coverage notes | reject - loses in 2026H1, 2021-25 |
| Previous-day high/low sweep and reversal | 0.8487 | 1.0 | 1.0 | 0.8788 | 1.0 | partly - E2 2026-11-13 (PDH/PDL sweep + climax volume) and the DAPHNE tree roots (fade 09:50-15:00) | reject - loses in 2026H1, 2026H2, 2021-25 |
| Asian range sweep and reversal | 1.0 | 1.0 | 1.0 | 0.9986 | 1.0 | partly - DAPHNE tree roots (Asia fade, RTH entries only); not the 00:00-11:00 version | reject - loses in 2026H1, 2026H2, 2021-25 |

### C. Relation to LIT (daily $ correlation; trade overlap, spans H1 / H2 / 2021-25)

| strategy | daily corr with LIT | on a LIT trade day % | in a trade at the same time as LIT % | same side at the same time % |
|---|---|---|---|---|
| Power of 3 / AMD | 0.25 / 0.02 / -0.0 | 66.7 / 0.0 / 41.7 | 66.7 / 0.0 / 13.9 | 66.7 / 0.0 / 8.3 |
| Judas Swing (London, midnight open) | 0.38 / 0.13 / 0.04 | 73.5 / 53.3 / 50.9 | 41.2 / 26.7 / 26.0 | 29.4 / 20.0 / 15.2 |
| London breakout (19:00-02:00 box) | 0.25 / -0.06 / -0.05 | 69.2 / 100.0 / 50.7 | 61.5 / 50.0 / 33.7 | 23.1 / 0.0 / 12.1 |
| Turtle Soup (20-day false breakout) | 0.03 / -0.11 / -0.02 | 33.3 / 100.0 / 42.0 | 0.0 / 0.0 / 6.0 | 0.0 / 0.0 / 0.0 |
| 2022 ICT model (sweep + MSS + FVG) | -0.06 / -0.06 / 0.02 | 69.8 / 50.0 / 49.3 | 24.5 / 26.2 / 14.0 | 9.4 / 16.7 / 7.6 |
| NY open FVG retrace (09:30-10:00) | 0.14 / 0.1 / -0.0 | 67.4 / 51.7 / 46.7 | 10.9 / 6.9 / 10.0 | 6.5 / 0.0 / 8.3 |
| Silver Bullet (10-11 ET FVG) | 0.11 / -0.01 / 0.01 | 61.7 / 37.1 / 48.4 | 3.3 / 5.7 / 6.3 | 3.3 / 2.9 / 3.6 |
| Unicorn (breaker + FVG) | 0.04 / 0.09 / -0.04 | 53.8 / 51.6 / 50.1 | 15.4 / 12.9 / 13.4 | 11.5 / 9.7 / 8.0 |
| Previous-day high/low sweep and reversal | 0.0 / -0.02 / 0.02 | 73.8 / 47.8 / 51.3 | 7.1 / 4.3 / 10.2 | 4.8 / 4.3 / 3.9 |
| Asian range sweep and reversal | 0.06 / 0.11 / -0.05 | 65.5 / 48.0 / 49.1 | 4.5 / 4.0 / 5.2 | 3.6 / 4.0 / 2.2 |

### D. Add-on to LIT on a Rapid EOD 50K (both full LIT size, max 30 micros; $3,000 target, $2,000 EOD trailing, best day <= 30%)

Each cell: trades/wk, $/month, max DD, eval started on every session -> pass % / fail % ever (median sessions to pass).

| book | 2026 H1 | 2026 H2 (to Oct 16) | 2021-25 |
|---|---|---|---|
| **LIT alone** | 3.12/wk, $5,562/mo, DD $-2,196, 86.7/1.6 (96) | 2.56/wk, $2,670/mo, DD $-1,396, 12.8/0.0 (67) | 2.38/wk, $25/mo, DD $-19,426, 18.7/81.3 (183) |
| + Power of 3 / AMD | 3.24/wk, $5,548/mo, DD $-2,196, 85.2/1.6 (97) | 2.63/wk, $2,629/mo, DD $-1,548, 2.6/0.0 (63) | 2.55/wk, $32/mo, DD $-19,733, 17.0/83.0 (178) |
| + Judas Swing (London, midnight open) | 4.45/wk, $5,535/mo, DD $-3,308, 77.3/20.3 (107) | 3.33/wk, $2,866/mo, DD $-1,690, 28.2/0.0 (65) | 4.56/wk, $25/mo, DD $-20,562, 13.2/86.8 (108) |
| + London breakout (19:00-02:00 box) | 3.63/wk, $5,483/mo, DD $-2,521, 89.1/5.5 (99) | 2.69/wk, $2,716/mo, DD $-1,396, 17.9/0.0 (65) | 5.4/wk, $123/mo, DD $-21,142, 21.5/78.5 (90) |
| + Turtle Soup (20-day false breakout) | 3.24/wk, $5,345/mo, DD $-2,196, 98.4/1.6 (94) | 2.63/wk, $3,021/mo, DD $-1,396, 41.0/0.0 (50) | 2.62/wk, $171/mo, DD $-21,208, 29.2/70.8 (146) |
| + 2022 ICT model (sweep + MSS + FVG) | 5.2/wk, $5,931/mo, DD $-4,772, 66.4/33.6 (62) | 4.87/wk, $3,351/mo, DD $-2,001, 64.1/1.3 (36) | 5.02/wk, $-156/mo, DD $-31,876, 9.5/90.5 (69) |
| + NY open FVG retrace (09:30-10:00) | 4.92/wk, $4,994/mo, DD $-4,503, 56.2/43.8 (111) | 4.23/wk, $2,280/mo, DD $-2,143, 2.6/1.3 (63) | 4.81/wk, $-343/mo, DD $-36,628, 18.2/81.8 (90) |
| + Silver Bullet (10-11 ET FVG) | 5.47/wk, $4,533/mo, DD $-4,355, 43.8/32.8 (148) | 4.74/wk, $2,334/mo, DD $-2,514, 0.0/56.4 (None) | 5.34/wk, $110/mo, DD $-27,679, 22.4/77.6 (76) |
| + Unicorn (breaker + FVG) | 5.16/wk, $4,492/mo, DD $-5,706, 50.0/50.0 (83) | 4.29/wk, $3,670/mo, DD $-1,771, 24.4/0.0 (68) | 4.48/wk, $-634/mo, DD $-48,913, 8.9/91.1 (102) |
| + Previous-day high/low sweep and reversal | 4.77/wk, $3,926/mo, DD $-5,173, 25.8/54.7 (144) | 3.78/wk, $2,028/mo, DD $-1,908, 12.8/0.0 (42) | 4.66/wk, $-249/mo, DD $-40,905, 13.9/86.1 (98) |
| + Asian range sweep and reversal | 7.42/wk, $1,944/mo, DD $-11,537, 0.0/81.2 (None) | 6.79/wk, $1,838/mo, DD $-8,575, 29.5/53.8 (12) | 6.54/wk, $-842/mo, DD $-65,887, 5.8/94.2 (19) |

### E. Add-on to LIT on a Rapid EOD 25K (both at half risk, max 20 micros; $1,500 target, $1,000 EOD trailing, best day <= 30%)

Each cell: trades/wk, $/month, max DD, eval started on every session -> pass % / fail % ever (median sessions to pass).

| book | 2026 H1 | 2026 H2 (to Oct 16) | 2021-25 |
|---|---|---|---|
| **LIT alone** | 3.12/wk, $2,614/mo, DD $-889, 86.7/0.0 (99) | 2.56/wk, $1,136/mo, DD $-563, 0.0/0.0 (None) | 2.38/wk, $15/mo, DD $-9,178, 17.4/82.6 (197) |
| + Power of 3 / AMD | 3.2/wk, $2,586/mo, DD $-889, 86.7/0.0 (101) | 2.56/wk, $1,136/mo, DD $-563, 0.0/0.0 (None) | 2.48/wk, $14/mo, DD $-9,625, 17.4/82.6 (183) |
| + Judas Swing (London, midnight open) | 4.22/wk, $2,581/mo, DD $-1,525, 51.6/19.5 (115) | 2.88/wk, $1,076/mo, DD $-842, 0.0/0.0 (None) | 4.28/wk, $-10/mo, DD $-9,734, 11.3/88.7 (124) |
| + London breakout (19:00-02:00 box) | 3.24/wk, $2,671/mo, DD $-889, 86.7/0.0 (102) | 2.56/wk, $1,136/mo, DD $-563, 0.0/0.0 (None) | 4.32/wk, $25/mo, DD $-9,877, 21.0/79.0 (104) |
| + Turtle Soup (20-day false breakout) | 3.2/wk, $2,528/mo, DD $-889, 100.0/0.0 (96) | 2.63/wk, $1,312/mo, DD $-514, 38.5/0.0 (36) | 2.58/wk, $80/mo, DD $-10,288, 28.1/71.9 (187) |
| + 2022 ICT model (sweep + MSS + FVG) | 4.77/wk, $2,835/mo, DD $-2,591, 75.8/24.2 (72) | 4.36/wk, $1,484/mo, DD $-769, 65.4/0.0 (34) | 4.81/wk, $-132/mo, DD $-17,270, 7.9/92.1 (75) |
| + NY open FVG retrace (09:30-10:00) | 4.26/wk, $2,379/mo, DD $-2,012, 60.9/25.0 (111) | 3.65/wk, $1,042/mo, DD $-730, 0.0/0.0 (None) | 4.48/wk, $-147/mo, DD $-18,078, 21.3/78.7 (111) |
| + Silver Bullet (10-11 ET FVG) | 4.38/wk, $2,216/mo, DD $-1,908, 62.5/18.0 (151) | 3.85/wk, $1,077/mo, DD $-1,060, 0.0/30.8 (None) | 4.77/wk, $-6/mo, DD $-14,556, 21.4/78.6 (85) |
| + Unicorn (breaker + FVG) | 4.77/wk, $2,179/mo, DD $-2,922, 61.7/38.3 (85) | 4.1/wk, $1,557/mo, DD $-877, 20.5/0.0 (69) | 4.41/wk, $-328/mo, DD $-24,685, 9.8/90.2 (50) |
| + Previous-day high/low sweep and reversal | 4.41/wk, $1,767/mo, DD $-2,413, 28.1/38.3 (107) | 3.59/wk, $801/mo, DD $-796, 12.8/0.0 (32) | 4.17/wk, $-153/mo, DD $-20,869, 11.6/88.4 (103) |
| + Asian range sweep and reversal | 7.34/wk, $658/mo, DD $-6,439, 0.0/88.3 (None) | 6.67/wk, $578/mo, DD $-4,440, 17.9/62.8 (12) | 6.48/wk, $-629/mo, DD $-42,018, 3.8/96.2 (15) |

## What it means

1. **No edge after the correction.** The smallest raw p is 0.17 (PO3, 42 trades in five years); Holm makes every one 1.0
   and BH at best 0.84. Positive spans exist (ICT 2022 both 2026 halves, Unicorn Jul-Oct, Judas Jul-Oct, Turtle Soup Jul-Oct)
   but each is paired with a losing span, which is what ten coin flips on three spans look like.
2. **Win rates of mostly 23-38% at 2R are below break-even** (~35-36% once costs are in), so the setups mostly lose by construction.
   The sweep-and-reverse family (Asia, PDH/PDL) does worst: on 5m NQ, the first sweep of a level more often continues.
3. **Overlap with LIT is low but not zero.** Daily correlation is -0.06 to +0.38 in 2026 (Judas Swing 0.38 in H1: it is a
   London sweep reversal like LIT and is in a trade at the same time as LIT 26-41% of the time). The FVG and sweep setups trade at the same
   moment as LIT 4-26% of the time (London breakout and PO3 more, on very few trades): diversification is real, but there is no money in it to diversify with.
4. **The add-on question.** Only ICT 2022 adds money to LIT in both 2026 halves on both books (50K +$369 / +$681 a month;
   25K +$221 / +$348) and gets the book to ~5 trades a week, but its max drawdown on the 50K goes $2,196 -> $4,772 in Jan-Jun,
   eval fails rise 1.6% -> 33.6%, and it loses $274 a month in 2021-25 with a $26k standalone drawdown. Not adopted; it fails
   the 2021-25 gate and the multiple-testing gate. It could be paper-watched at most.

## Not done / limits

- 5m bars only; ICT teaches several of these on 1m. A 1m version is possible for 2026 only (1m starts 2025-12-29), which would
  make it a second, post-hoc test; not run, so the result stays pre-registered.
- Textbooks leave room (which FVG, which swing definition, bias filters). One reading was fixed in advance; other readings are
  other strategies and would need their own correction.
- No 25K/50K Monte Carlo with the bot's room sizing; see the caveat above.
