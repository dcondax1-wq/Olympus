---
tags:
  - zeus/research
  - family/other
  - verdict/research
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-25"
source: "research/writeups/more-trades-2026-11-25.md"
aliases:
  - "More trades"
---

# More trades

> [!abstract] Verdict: research
> (no status line)

**Full title:** More trades: can Zlarior / ATLAS trade more without losing the edge? (2026-11-25)

## Summary

Owner: "we have not traded at all this week". PAPER RESEARCH ONLY: no live_model*.json change. Grid pre-registered before any run (`research/moretrades/DESIGN.md`, commit before the code). Code `research/moretrades/moretrades.py` -> `lit.json`, `atlas.json`. Same engine the bot runs (engine/lit.py run_x, engine/second.run), futures bars only, costs in, stops / size / target unchanged. Sessions 2021-11-08 .. 2026-11-20 (the fresh Oct 19 - Nov 20 weeks included).

## Money first

0 of 19 LIT variants and 0 of 7 ATLAS variants meet the pre-registered rule (>= +25% trades, 2-week eval pass >= today in
BOTH 2026 halves, 2021-25 not worse, walk-forward >= half the windows). No owner card.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-25]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Source: `research/writeups/more-trades-2026-11-25.md`
- Back to [[ZEUS Home]]
