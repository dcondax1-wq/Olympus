---
tags:
  - zeus/research
  - family/research
  - verdict/rejected
type: "research"
date: "2026-11-23"
status: "plan + proxy rejection; real test waits on tick data"
source: "research/writeups/orderflow-2026-11-23.md"
aliases:
  - "Order flow"
---

# Order flow

> [!failure] Verdict: rejected
> plan + proxy rejection; real test waits on tick data

**Full title:** Order flow - what we have, what we need, first (proxy) results

## Summary

We own zero tick / bid-ask / footprint data, only OHLCV bars. A read-only tick recorder (engine/tickrec.py + ninjatrader/LE_TickRec.cs, OFF by default) and an importer for NinjaTrader's free historical ticks are on branch day-orderflow for red-team. On a 5m bar-shape proxy of delta, none of the three proxy-testable setups holds in all of 2021-25, 2026 H1 and 2026 H2, so nothing changes in the live strategy. The real test runs by itself once 60+ days of NQ ticks are on disk.

## Links

- Family: [[Family research]]
- Day: [[Day 2026-11-23]]
- Runs: `research/orderflow/of_study.py -> research/orderflow/results.json`
- Source: `research/writeups/orderflow-2026-11-23.md`
- Back to [[ZEUS Home]]
