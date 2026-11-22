---
tags:
  - zeus/research
  - family/product
  - verdict/research
type: "research"
date: "2026-10-21"
status: "research"
source: "research/writeups/competitor-features.md"
aliases:
  - "What other trading bots and trader tools do better than ours"
---

# What other trading bots and trader tools do better than ours

> [!abstract] Verdict: research
> research

**Full title:** What other trading bots and trader tools do better than ours - 40 features compared, the 15 worth building, and what not to copy

## Summary

A web scan (2025-2026 sources) of bridges (TradersPost, PickMyTrade, CrossTrade), platforms (NinjaTrader, Tradovate, TradeStation, Sierra Chart, QuantConnect / LEAN), retail AI and bot apps (Composer, Capitalise.ai, Trade Ideas Holly, TrendSpider, 3Commas, Cryptohopper, Collective2), prop-firm copiers and risk lockers (Replikanto, Tradovate Group Trade, Tradesyncer), journals (TradeZella, Tradervue, TraderSync, Edgewonk), alerting and status tools (PagerDuty, healthchecks, Upptime) and open-source bots (freqtrade, Jesse, Hummingbot, Nautilus Trader). Our bot already has more than most of them for a one-strategy prop trader: a backtest that matches the live loop, Monte Carlo eval odds, a fill audit, guards, an eval lifecycle, recap cards, trade intel and business tools. It is weaker in four areas. (1) It does not warn before a trade: there is no push when a setup arms, and nothing logs that the owner was present, which MFFU requires. (2) Alerts never escalate: a critical alert is sent once, cannot be acknowledged and has no levels. (3) Nothing checks the cloud monitor itself, or that the PC and the cloud run the same rules. (4) Nothing says whether live results are still inside the range the backtest expects. The ranked top 15 are mostly small (S) changes to engine/push.py, engine/ops_checks.py, engine/live.py and the phone app. Paid bridges and copiers, cloud order routing, auto re-optimisation, DCA / grid / trailing exits and plain-English AI strategy builders should not be copied.

## Links

- Family: [[Family product]]
- Day: [[Day 2026-10-21]]
- Refers to: [[leakage-check|Leakage check]], [[lit-adv-audit-smt|LIT advanced report ch.7 audit]], [[lit-adv-management|LIT advanced management]], [[lit-funded-firms|LIT on 3 funded accounts]], [[management|Managing the trade]], [[stress-tests|Stress tests of the locked strategy]]
- Source: `research/writeups/competitor-features.md`
- Back to [[ZEUS Home]]
