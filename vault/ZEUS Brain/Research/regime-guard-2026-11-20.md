---
tags:
  - zeus/research
  - family/filters
  - verdict/rejected
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-20"
status: "rejected (no change, no Decide card). live_model*.json, second_model.json, accounts and every engine file untouched."
source: "research/writeups/regime-guard-2026-11-20.md"
aliases:
  - "Regime guard"
---

# Regime guard

> [!failure] Verdict: rejected
> rejected (no change, no Decide card). live_model*.json, second_model.json, accounts and every engine file untouched.

**Full title:** Regime guard - can a pre-session market signal (volatility risk premium, 1-year ATR percentile, 1-year trend-efficiency percentile, a 2-of-3 vote) tell 2026-like days from 2021-25-like days so LIT and ATLAS size down? No; nothing changed

## Summary

Lead round 2 (day-newstrat) - protect the accounts in a 2021-25-like market (LIT about $40 a month there, ATLAS funded 25K lost 94.5% of the time in 6 months). Four causal signals from the prior close, cuts fixed before the run (research/regime_guard/RULES.md) - G1 NQ 20-day realized vol above the prior VIX close, G2 NQ 20-day ATR in the bottom third of its last year, G3 NQ 20-day trend efficiency in the bottom third of its last year (chop), G4 2 of the 3 - each as half size or sit out for BOTH bots, 8 versions, judged on fixed $ (LIT $350 / ATLAS $250, costs in), the LIT Builder 50K eval (live two_week sizing, 600 paths) and the ATLAS funded Builder 25K Monte Carlo with the live stuck stop (600 paths; the no-guard row reproduces atlas-health's 8.5 / 9.2 / 94.5% exactly). 0 of 8 pass. None of the signals is more common in 2021-25 than in 2026 (bad-day share 2021-25 25-40% vs 2026 13-65%): the 2021-25 vs 2026 gap is not a market weather these signals see. Each one hurts LIT somewhere (2021-25 LIT goes from +$2,065 to -$1,801..-$5,933 under G1/G3/G4: LIT made its 2021-25 money on exactly the flagged days). One lead for later (post-hoc, not eligible): on chop days (G3) ATLAS's trades are worse in all three periods (H1 +0.49R vs +0.84R, H2 +0.32R vs +0.51R, 2021-25 -0.09R vs +0.10R), but sitting them out costs $778 a month of ATLAS fixed $ in Jan-Jun and $105 a month funded in Jul-Oct and still leaves 85.7% of 2021-25-like funded accounts lost.

## Links

- Family: [[Family filters]]
- Day: [[Day 2026-11-20]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[edge-health-2026-11-17|Edge health, 2026-11-17]], [[lit-regime-sizing-2026-11-17|LIT regime sizing]]
- Runs: `none (research/regime_guard/results.json; research/regime_guard/guard.py)`
- Source: `research/writeups/regime-guard-2026-11-20.md`
- Back to [[ZEUS Home]]
