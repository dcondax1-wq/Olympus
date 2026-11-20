---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected"
source: "research/writeups/lit-untested-stops.md"
aliases:
  - "LIT untested stop ideas"
---

# LIT untested stop ideas

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT untested stop ideas - close-based stops, stops behind the next liquidity, ATR buffers, time-based breakeven, profit locks

## Summary

Five stop ideas nobody had tested on LIT yet (plus two extra ones) were run on the exact live LIT signals with the live eval sizing, 44 variants in all. Each was picked on Jan-Jun 2026 and checked on Jul-Oct 2026. None made more money in both halves, so nothing changes in the bot. The live stop (1 tick past the sweep extreme, closed on a touch, breakeven at +1R) stays. LIT stop-outs are real: 52-53 of the 53 stop-outs in 2026 also closed a 1m candle past the stop, so waiting for a close only loses more. A wider stop behind the next swing or equal lows only buys a smaller size. A later breakeven turns scratches into full losses. A profit lock at 75-85% of the way almost never fires (1-3 trades in 2026); at 50-60% it cuts the runners. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-experiments|LIT experiments]]
- Runs: `lit_u_stops_base, lit_u_stops_close_5_emerg_size, lit_u_stops_close_5_live_size, lit_u_stops_close_10_emerg_size, lit_u_stops_close_10_live_size, lit_u_stops_close_15_emerg_size, lit_u_stops_close_15_live_size, lit_u_stops_close5m_10_emerg_size, lit_u_stops_close5m_10_live_size, lit_u_stops_close5m_`
- Source: `research/writeups/lit-untested-stops.md`
- Back to [[ZEUS Home]]
