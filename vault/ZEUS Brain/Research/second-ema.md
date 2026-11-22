---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-10-22"
status: "promising"
source: "research/writeups/second-ema.md"
aliases:
  - "Second strategy next to LIT"
---

# Second strategy next to LIT

> [!tip] Verdict: promising
> promising

**Full title:** Second strategy next to LIT - the London EMA trend pullback (sweep + 5m CISD, VIX-band target)

## Summary

Owner's order (2026-10-22) was to find an EMA strategy to trade alongside LIT and make it profitable by tuning on 2026, the way LIT was tuned. 192,776 versions of an EMA trend pullback with LIT's tools (sweep, 5m CISD, VIX-band target, BE + costs, 15-minute check) were tested on CME NQ1! 5m bars, with costs ($1.90 a micro + 1 tick). Parameters were picked on 2026 H1 and checked untouched on H2. The best version trades London hours (03:00-09:30 ET) when the 15m and 1h EMA 21 are above the 50, after a pullback to the 5m EMA 50 that sweeps a swing low and then closes back up (CISD). Stop 1 tick beyond the sweep wick, target = LIT's VIX band, BE + 1.25 at 1R. At $500 risk a trade it made H1 +$19.8k (PF 2.72, $3,280/mo) and H2 +$8.1k (PF 3.10, $2,191/mo) at about 2 trades a week, and it also stayed positive in 2025 (+$6.2k, PF 1.18) and 2021-24 (+$5.5k, PF 1.05). Daily correlation with LIT is 0.19. On LIT's account (LIT first, max 2 trades a day) 2026 goes from +$43.4k to +$66.8k, with max DD -$3.5k instead of -$2.2k. On the eval path the 2-week pass/fail goes from 57.1/5.9 to 61.3/5.0 in H1 and from 52.2/0.0 to 69.6/2.9 in H2. All 13 one-step neighbours are positive in H1 and H2. Verdict - paper-trade it next to LIT; not live until it shows on paper.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Runs: `ema2_lon_vix, ema2_lon_vix_with_lit, ema2_lon_3r, ema2_lon_3r_with_lit, lit_live, lit_adopt_t15_be_off_eval`
- Source: `research/writeups/second-ema.md`
- Back to [[ZEUS Home]]
