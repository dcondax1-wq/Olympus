---
tags:
  - zeus/research
  - family/other
  - verdict/info
type: "research"
date: "2026-11-03"
status: "info - research tool, paper only; nothing proposed for the live bot (the 2021-24 picks lose money in 2025-26)"
source: "research/writeups/datacity.md"
aliases:
  - "Olympus Data City"
---

# Olympus Data City

> [!note] Verdict: info
> info - research tool, paper only; nothing proposed for the live bot (the 2021-24 picks lose money in 2025-26)

**Full title:** Olympus Data City - a nightly data machine that tests 114,200 time / confluence / while-state combinations on NQ, and a 32,000-building 3D city that shows them

## Summary

Owner orders 2026-11-02 ("a data center like a city of data") and 2026-11-03 ("make the city bigger ... insane"). tools/datacity turns CME NQ1! 5m 2021-11 -> 2026-10 plus the PC's NinjaTrader bars to 2026-11-02 into 375,079 events (sweeps of Asia / London / prior-day / prior-week / opening-range levels, breaks, FVG, IFVG, CISD, displacement, VWAP cross, gap fill, the news bar, plain 15-minute slots), each a mini-backtest (next-bar entry, structure stop, 2R or 2 hours, $1.90 + 2 ticks costs a micro). The 2026-11-03 pass adds 7 state families (opening-range width and position, RTH gap types, the VIX curve and the VIX trend, ES-NQ relative strength, turn of the month / OpEx week) and weekday x 15-minute slot - 114,200 combinations, 32,164 with 30+ trades, in 9 districts. 39 pass a Benjamini-Hochberg false-discovery guard (q 0.10, ~3.9 expected false); a sign-flip placebo passes 2. 5 are gold, all under 1 trade a week. Holdout - the 40 combinations picked on 2021-24 alone stay positive in 2025-26 only 25% of the time (-0.11R a trade), and as a one-a-day portfolio they go from PF 1.69-2.09 a year in 2021-24 to PF 0.93 in 2025 and 0.98 in 2026 (-$704, -$68 a month, 2-week eval pass/fail 3.7/6.9%). Learned confluences - an open gap in the trade's direction, NQ outpacing ES, VIX 25+ / VXN 28+, an inverted VIX curve and a trending day help a little; VIX < 15 and an ES-NQ SMT that agrees with the trade hurt. Nightly workflow publishes the JSON to the datacity branch; the 3D page is tools/web_public/datacity/.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-03]]
- Runs: `datacity_holdout_portfolio`
- Source: `research/writeups/datacity.md`
- Back to [[ZEUS Home]]
