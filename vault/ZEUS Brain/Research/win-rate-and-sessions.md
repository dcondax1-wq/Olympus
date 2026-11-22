---
tags:
  - zeus/research
  - family/winrate
  - verdict/adopt-candidate
  - bot/atlas
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/win-rate-and-sessions.md"
aliases:
  - "Win rate and more trades"
---

# Win rate and more trades

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** Win rate and more trades: new windows, second trades, partials, entries, filters

## Summary

More trades from new windows or second trades lose money in 2021-25 every time (London, Asia, pre-open, lunch, late PM, 2 a day), even at a quarter size. The things that raise the win rate (partials, a depth limit, HTF filters) earn less money or cut trades below 2 a week. One small change helps both periods with every trade kept: half size when the sweep ran 3.5+ ATR past the pool (2026 +$293, PF 3.94 to 4.11; 2021-25 +$1.5k, PF 1.27 to 1.32, max drawdown -$9.3k to -$7.5k, 1-month eval fails 5.2% to 3.5%).

## Links

- Family: [[Family winrate]]
- Day: [[Day 2026-10-18]]
- Strategies: [[ATLAS]]
- Refers to: [[bias-filters|Bias, filters and timing]], [[cross-market-context|Cross-market and regime context]], [[management|Managing the trade]]
- Runs: `baseline, ses_feat_base, ses_lon_alone, ses_pre_alone, ses_lunch_alone, ses_late_alone, ses_asia_alone, ses_lon_add1, ses_pre_add1, ses_lunch_add1, ses_late_add1, ses_asia_add1, ses_lon_add2, ses_pre_add2, ses_lunch_add2, ses_late_add2, ses_asia_add2, ses_lon_add2any, ses_pre_add2any, ses_lunch_add2`
- Source: `research/writeups/win-rate-and-sessions.md`
- Back to [[ZEUS Home]]
