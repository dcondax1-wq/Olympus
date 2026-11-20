---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
type: "research"
date: "2026-11-19"
status: "rejected - 0 of 172 cells hold in 2026 H1, H2, 2025 and 2021-24 (coin-flip sides give 0.4); the two Jan-Jun picks lose Jul-Oct; no Decide proposal; nothing live changed"
source: "research/writeups/third-strategy-2026-11-18.md"
aliases:
  - "Third strategy hunt"
---

# Third strategy hunt

> [!failure] Verdict: rejected
> rejected - 0 of 172 cells hold in 2026 H1, H2, 2025 and 2021-24 (coin-flip sides give 0.4); the two Jan-Jun picks lose Jul-Oct; no Decide proposal; nothing live changed

**Full title:** Third strategy hunt (2026-11-18/19 night) - post-close move into the 18:00 reopen, Camarilla / floor pivots, TD Sequential 9-count - nothing passes; one paper lead (follow the post-close move) fails 2025 and trades ~1 a week

## Summary

Lead order - a NEW third NQ strategy that adds money without overlapping Zlarior (LIT, London / NY sweep reversals) or ATLAS (NY EMA / MACD / S-R), ideally at other times or in another way, high win rate and good PF. After reading the rejected list (ORBs, gap fades, every VWAP / band / RSI / turtle-soup fade, level sweep-reclaims in all 9 windows, the lunch squeeze / value-area / 80% rule / London fade, the famous published edges, draw-on-liquidity bias, BLITZ) three untested families were pre-declared - PCM the 16:00-17:00 post-close move (mega-cap earnings hour, MFFU must be flat) traded at the 18:00 Globex reopen, with it or against it (80 cells); CAM the classic Camarilla H3/L3 fade, H4/L4 breakout and floor-trader R1/S1 fade (44 cells); TDS DeMark's TD Sequential 9-count exhaustion fade on 15m / 1h bars of the whole CME day (48 cells). CME NQ1! 5m 2021-10 -> 2026-10-16, costs in ($1.90 a micro + 1 tick), stops 1 tick beyond the structure, $500 a trade, flat by 15:55. Result - 0 of 172 hold in all four spans vs 0.4 with coin-flip directions. The Jan-Jun picks (Camarilla H4 breakout, 2.4/wk, H1 +$9,856 PF 1.58; TD 1h 9-count to bar 1, 2.1/wk, H1 +$19,125 PF 1.98) both lose Jul-Oct (-$3,187 / -$1,379) and 2025; placebo p 0.90 / 0.74 in H2. Win rates are low (21-44%), not high. The one consistent pattern - FOLLOW a big post-close move at the reopen - is positive in H1, H2 and 2021-24 in 14 of its 32 cells (coin-flip: 0 hold), placebo p 0.005 over 2021-25, but it loses 2025 in every cell and trades 0.2-1.4 a week, and added to LIT's 50K at $250 it raises 40-session eval fails (H2 0 -> 13.7%). Paper lead only. All three families registered in the ZEUS Lab (kind new_strategy, Rejected).

## Money first

Nothing passes: no third strategy, no new account, no Decide proposal, nothing built for live; Zlarior, ATLAS and BLITZ
unchanged. Paper lead only (not proposed): "follow a big post-close move at the 18:00 reopen" - re-check when 2026 Nov-Dec
bars are in (it needs 2025-like years to stop losing and more than ~1 trade a week). Registered in the ZEUS Lab as kind
`new_strategy` (bot "third"): `third_pcm`, `third_cam`, `third_tds`, all Rejected, 172 cells counted in the many-tests bar.
Not done: 1m execution (1m starts 2025-12-29; no 5m survivor to confirm), ES (5m only from 2025-04).

Reproduce: `python -X utf8 tools/third_strategy.py grid` (~30 s) -> `research/second/third_strategy.json`;
`python -X utf8 tools/third_strategy.py register`.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-19]]
- Runs: `(no rl runs) research/second/third_strategy.json, tools/third_strategy.py`
- Source: `research/writeups/third-strategy-2026-11-18.md`
- Back to [[ZEUS Home]]
