---
tags:
  - zeus/research
  - family/second
  - verdict/finding
  - bot/atlas
type: "research"
date: "2026-11-20"
status: "finding - no change. ATLAS stays (still earns in 2026-like markets at 10 ticks a side, and carries the Rapid 25K), but at real fills it has no long-run edge (2021-25 PF 0.80) and the funded 25K's ..."
source: "research/writeups/atlas-fills-2026-11-20.md"
aliases:
  - "ATLAS real fills"
---

# ATLAS real fills

> [!info] Verdict: finding
> finding - no change. ATLAS stays (still earns in 2026-like markets at 10 ticks a side, and carries the Rapid 25K), but at real fills it has no long-run edge (2021-25 PF 0.80) and the funded 25K's 6-month loss risk roughly doubles. 0 of 6 pre-registered fixes pass. Fill cost now on the ZEUS card data.

**Full title:** ATLAS real fills - why its NinjaTrader entries fill ~11 ticks worse than the backtest, what it costs at 3 / 6 / 10 ticks a side, 6 fixes tested

## Summary

ATLAS enters with a MARKET order at the 5m open right after its signal bar closes; the order leaves 3-5 s after the open. Its 3 real fills were 10 / 12 / 16 ticks past that open (the backtest counts 1). Not a timestamp mismatch (the backtest re-run on the PC's own bars has the bot's exact entries), not book depth (2 micros; the NY pre-market fill was as bad as the London ones), not a stop order. It is price moving in the first seconds after a 5m close, in the trade's direction, then coming back. At 10 ticks a side the funded 25K still makes $512 / $404 a month (Jan-Jun / Jul-Oct like; $588 / $494 at 1 tick) but the chance of losing it in 6 months from today's account goes 7.7 -> 17.7% / 9.5 -> 23.0%; 2021-25 PF 1.06 -> 0.80. Rapid 25K: LIT + ATLAS $1,878 / $753 a month at 10 ticks vs Zlarior alone $224 / $194. Limit entries, a 1-minute delay, fast-bar skips, member hours, a London pause: all fail.

## Links

- Family: [[Family second]]
- Day: [[Day 2026-11-20]]
- Strategies: [[ATLAS]]
- Runs: `tools/atlas_fills.py why / costs / fixes / posthoc -> research/second/atlas_fills_why.json, research/second/atlas_fills.json; design research/second/atlas_fills_design.md (committed d9ed3b2a before any run); tests/test_fill_cost.py`
- Source: `research/writeups/atlas-fills-2026-11-20.md`
- Back to [[ZEUS Home]]
