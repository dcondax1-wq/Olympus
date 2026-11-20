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
source: "research/writeups/second-md.md"
aliases:
  - "Second strategy next to LIT"
---

# Second strategy next to LIT

> [!tip] Verdict: promising
> promising

**Full title:** Second strategy next to LIT - MACD divergence at a liquidity sweep (works, thin) and supply/demand zone retests (does not)

## Summary

Owner's overnight order - find a strategy to trade next to LIT and tune it on 2026 like LIT. 221,184 versions of two families were tested on CME NQ1! (5m, 1m trade path in 2026), costs $1.90 a micro + 1 tick, structural stops, picked on 2026 H1 only and checked untouched on H2. MACD divergence at a LIT liquidity sweep with a 5m CISD (London 02:00-05:00 + NY 09:30-11:00, VIX-band target banked at 8R, LIT's 15-minute check) is positive in all four periods at $500 risk - H1 +$22,087 (PF 3.78), H2 +$2,569 (PF 1.75), 2025 +$8,183, 2021-24 +$11,982 - at about 1.1 trades a week, daily correlation with LIT -0.08 to +0.23. Picking on H1 did predict H2 better than chance for this family (top H1 versions 66-70% positive in H2 vs 34% for all). But it lives on a few big winners (H2 without its best 3 trades is -5.5R) and the 2021-25 drawdown is large (-$22.6k at $500). Next to LIT on one account (LIT first, max 2 trades a day) it adds +$14.1k in H1 and +$1.6k in H2 and lifts 2-week eval passes. Supply/demand - no version holds: the H1 picks lose in H2 (worse than chance). Verdict - paper-trade the MACD sweep next to LIT, no real money yet.

## Money first

- **MACD divergence at a liquidity sweep: promising, not proven.** Positive in every period, low correlation with LIT,
  helps LIT's 2-week eval odds on one account, H1 selection beat chance. But H2 is small (+$2.6k at $500 in 3.5 months),
  depends on a few trades, and 2021-25 had a deep drawdown. Paper-trade it next to LIT (way (a), $300-$500 risk) and judge
  it on its first 20-30 live paper trades before real money.
- **Supply/demand: rejected** as a standalone strategy.
- Nothing changes in `live_model.json`; there is no live switch for it yet (it would be a separate module in the live loop).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[lit-retail-entries|LIT retail entries]]
- Runs: `md2_best, md2_combo_lit, md2_md_plateau, md2_md_best, md2_md_best_ref, md2_sd_best, md2_sd_plateau, md2_sd_best_ref, md2_sd_plateau_ref`
- Source: `research/writeups/second-md.md`
- Back to [[ZEUS Home]]
