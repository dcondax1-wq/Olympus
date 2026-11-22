---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
type: "research"
date: "2026-10-26"
status: "promising - the strategy holds as futures trading; on MFFU-type accounts only as a small add-on next to LIT on funded accounts (small gain, paper first)"
source: "research/writeups/diversifier-search.md"
aliases:
  - "A strategy uncorrelated with LIT"
---

# A strategy uncorrelated with LIT

> [!tip] Verdict: promising
> promising - the strategy holds as futures trading; on MFFU-type accounts only as a small add-on next to LIT on funded accounts (small gain, paper first)

**Full title:** A strategy uncorrelated with LIT - noise-area intraday momentum (Zarattini 2024) holds on NQ 2021-26, but prop accounts can only carry it as a small add-on

## Summary

Owner order 2026-10-26, item 1 - a strategy uncorrelated with LIT that holds in 2026 (H1 pick / H2 check) AND 2021-25 at 2-4 trades a week. After reading the rejected list (ORBs with R targets, Gao intraday momentum, gaps, EOD, calendar, fades, continuation), two untested families were built on CME NQ1! 5m - (1) the noise-area intraday momentum of Zarattini, Aziz & Barbon 2024 (trade a half-hour close outside the day's time-of-day noise band from the open, stop at the band / VWAP, flat 15:55) and (2) a VXN-normalised initial-balance breakout held for the day. The IB family is dead (0 of 24 settings positive in all four spans). The noise-area family is real - the paper's own rule, untouched, makes money in every span (H1 +$3.5k, H2 +$14.8k, 2025 +$2.7k, 2021-24 +$68.5k at $500 a trade) but trades 5.5 a week; the joint pick (H1 + 2021-24, band 1.25 sigma) makes H1 +$9.1k (PF 1.28), H2 +$16.1k (PF 2.01), 2025 +$12.1k (PF 1.21), 2021-24 +$52.3k (PF 1.25), 3.1-3.8 trades a week, $1,292 a month over 2021-25 and $2,659 in 2026; random-entry placebo p 0.007 in 2026, 0.07 in 2021-24, 0.02 over all (2025 no better than random); daily P&L correlation with LIT -0.08 (2026) / -0.01 (2021-25). But it is a trend strategy - 26-30% winners, 18-23R drawdowns, the 5 best trades carry each 2026 half - and the MFFU rules choke it - alone it passes 0-22% of evals in 2 weeks (LIT 51-57%) and a funded account pays it $13-117 a month (the 50% best-day rule and the $2,000 floor). As a small add-on on LIT's funded accounts (3-4% of the room, at most $150 a trade, never while LIT holds a position) it adds +$54 to +$83 a month per 50K in 2026 and +$7 to +$12 in 2021-25 (25K about neutral), and on a 7-account copied stack it lifts H2 from $4,772 to $5,080 a month and cuts the 12-month odds of 3 months in a row with no payout from 20% to 14% (13% to 10% with month-long blocks). In a 2021-25-like market every LIT stack still pays almost nothing, and NA cannot fix that through prop accounts. Paper only; nothing built, nothing live changed.

## Money first

**The strategy (noise-area momentum, "NA"),** joint pick `na_vm125_1000_n99_fixed`, $500 risk a trade, costs in ($1.90 a micro +
1 tick on every market fill), CME NQ1! 5m, regular hours only:

| Span | Trades | /week | Weeks with 2+ | Win % | PF | Net | **$ / month** | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 H1 (Jan-Jun, in sample) | 100 | 3.7 | 82% | 26.0 | 1.28 | +$9,115 | **+$1,556** | -$8,845 |
| **2026 H2 (Jul-Oct, untouched)** | 50 | 3.1 | 69% | 30.0 | **2.01** | **+$16,083** | **+$4,444** | -$5,832 |
| **2025 (untouched)** | 167 | 3.2 | 68% | 25.1 | 1.21 | **+$12,063** | **+$1,026** | -$11,320 |
| 2021-24 (in sample) | 630 | 3.8 | 82% | 29.0 | 1.25 | +$52,268 | +$1,374 | -$10,442 |
| 2026 | 150 | 3.6 | 79% | 27.3 | 1.52 | +$25,198 | +$2,659 | -$8,845 |
| 2021-25 | 797 | 3.6 | 78% | 28.2 | 1.24 | +$64,331 | +$1,292 | -$11,320 |

- By year: 2021 (Nov-Dec) +$7.2k, 2022 +$28.0k, 2023 -$1.7k, 2024 +$18.7k, 2025 +$12.1k, 2026 +$25.2k; 53% of 60 months
  positive. **It earns where LIT does not:** LIT made +$1.3k over 2021-25 (run `lit_live`, 5m-only there) and +$43.8k in 2026;
  NA made +$64k over 2021-25 and +$25k in 2026. It is not a mirror year by year (both made money in 2022, both were weak in
  2023), but in LIT's 24 losing months of 2021-25 NA made +$24,140 (about +$1,000 in each) at $500 a trade.
- **Correlation with LIT** (run `lit_live`): daily P&L -0.08 in 2026, -0.01 in 2021-25; monthly -0.22 / +0.27. It trades
  10:00-15:55 (428 of 947 entries in the 10:00 hour); LIT enters 02:00-08:00 in 95 of 120 2026 trades. Only 5% of NA trades
  overlap a LIT trade in time.
- **What it costs on a prop account is the problem** (section 4): 26-30% winners, a drawdown of 18-23R, and the 5 best trades
  carry each 2026 half (without them H1 -$12.7k, H2 -$5.9k, 2025 -$21.9k; 2021-24 stays +$21.3k). That is how trend following
  works, and it is exactly what the MFFU rules punish.

**On prop accounts (what the owner can actually trade):**

| Use | 2026 H1 | **2026 H2** | 2025 | 2021-24 |
|---|---:|---:|---:|---:|
| NA alone on a Builder 50K eval: pass / fail in 2 weeks (best size, 20% of the room a trade) | 7.8 / 0.4 | 17.6 / 0.4 | 9.4 / 0.0 | 9.8 / 0.6 |
| LIT alone, same eval (live two_week) | 50.6 / 20.2 | 57.0 / 21.0 | 12.4 / 17.6 | 19.2 / 30.8 |
| NA alone on a funded 50K, $ a month to you (best size) | $67 | $117 | $13 | $74 |
| LIT alone on a funded 50K (live funded sizing) | $929 | $915 | $72 | $58 |
| **LIT + NA on the funded 50K** (NA 3% of the room, <= $150 a trade) | **$993** | **$969** | **$81** | **$68** |
| LIT + NA, H1 pick (NA 4% of the room, <= $150) | $1,012 | $971 | $79 | $70 |
| 7 funded-account slots, all LIT (12 months, net of evals; section 5) | $5,016 | **$4,772** | $75 | $30 |
| **7 slots, LIT + NA on each funded account** | **$5,423** | **$5,080** | **$86** | **$63** |
| ... chance of 3 months in a row with no payout (months 4-12) | 18.8% -> 16.4% | **20.3% -> 14.2%** | 98.6% -> 98.7% | 98.9% -> 98.6% |

Eval and NA-alone funded rows: MC 500 paths (`tools/div_stack.py solo`); funded LIT / LIT + NA rows: 1,000 x 6 months; stack:
1,000 x 12 months, 5-session blocks.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-26]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[allday|NQ around the clock]], [[atlas-chatgpt-breakouts|ChatGPT's 10 ATLAS breakout templates]], [[atlas-funded|ATLAS's funded account]], [[hq-continuation|HQ continuation]], [[hq-reversion|High-probability mean reversion at exhaustion]], [[quant-anomalies|Quant anomalies on CME NQ]], [[retail-standalone|Retail strategies on their own]], [[uprisk|Uprisk]]
- Runs: `div_na_joint, div_na_paper, div_na_paper_1aday, div_na_h1pick, div_na_plateau_1030, div_ib_h1pick`
- Source: `research/writeups/diversifier-search.md`
- Back to [[ZEUS Home]]
