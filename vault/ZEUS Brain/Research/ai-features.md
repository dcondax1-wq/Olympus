---
tags:
  - zeus/research
  - family/product
  - verdict/info
type: "research"
date: "2026-10-22"
status: "info"
source: "research/writeups/ai-features.md"
aliases:
  - "What an AI trading bot needs that ours lacked"
---

# What an AI trading bot needs that ours lacked

> [!note] Verdict: info
> info

**Full title:** What an AI trading bot needs that ours lacked - audit of 18 features, 6 built (anomaly watch, drift, both-accounts loss cap, rule-change log, readiness, restore)

## Summary

Owner (2026-10-22) - "add features that an AI trading bot needs to have". Code audit of 18 things a serious automated futures bot watches about itself; 11 were already there (often better than the docs said), 7 were missing or partial. Built 6, all for LIT and account B (ATLAS) - anomaly watch (bad tick / spike / jump, feed frozen in a trade = critical, slow route), drift monitor per strategy (LIT health band, account B bootstrap of its research run, execution), both-accounts daily / weekly loss (push on, block OFF), anomaly pause (OFF), rule-change log (git who / when / why + runtime change push), pre-session readiness + weekly self-review lines, backup restore. No trading change - LIT replay 120/120 identical.

## Links

- Family: [[Family product]]
- Day: [[Day 2026-10-22]]
- Source: `research/writeups/ai-features.md`
- Back to [[ZEUS Home]]
