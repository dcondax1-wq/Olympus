---
tags:
  - zeus/research
  - family/kalshi
  - verdict/research
  - bot/kalshi
type: "research"
date: "2026-11-18"
status: "NOT safe to go live. The rewards are real, but no net edge is shown for a small maker; the 2 best-looking series lost in the first 43 h of new data. Verifier built (research/kalshi_red_team/verify.py)"
source: "research/writeups/kalshi-red-team-2026-11-18.md"
aliases:
  - "Kalshi red team, the liquidity-rewards lead checked from raw data"
---

# Kalshi red team, the liquidity-rewards lead checked from raw data

> [!abstract] Verdict: research
> NOT safe to go live. The rewards are real, but no net edge is shown for a small maker; the 2 best-looking series lost in the first 43 h of new data. Verifier built (research/kalshi_red_team/verify.py)

**Full title:** Kalshi red team, the liquidity-rewards lead checked from raw data (paper test, tape backtest, Kalshi's filed rules)

## Summary

Kalshi really does pay people who leave orders waiting in the book ("liquidity rewards"). The Nov 17 programs the paper test watched have been paid out. The catch is the other half: a waiting order mostly gets filled when someone sweeps the book just before the price moves, and one such fill can wipe out a week of rewards. Nobody has shown that a small trader comes out ahead after those fills:

## Links

- Family: [[Family kalshi]]
- Day: [[Day 2026-11-18]]
- Strategies: [[Kalshi K8]]
- Source: `research/writeups/kalshi-red-team-2026-11-18.md`
- Back to [[ZEUS Home]]
