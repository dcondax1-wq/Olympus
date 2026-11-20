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
source: "research/writeups/second-sr.md"
aliases:
  - "A second strategy next to LIT"
---

# A second strategy next to LIT

> [!tip] Verdict: promising
> promising

**Full title:** A second strategy next to LIT - support/resistance (sweep-and-reclaim of the day's levels in NY hours)

## Summary

Owner's order (2026-10-22) to find a strategy to trade alongside LIT and tune it the way LIT was tuned (pick on 2026 H1, check untouched on 2026 H2). In the support/resistance family 201,908 versions were scored (costs $1.90 a micro + 1 tick, structural stops, no look-ahead). One survives - the NY sweep-and-reclaim of the day's levels (prior-day, overnight, Asia, London, prior-week, opening range; 09:30-12:00; inducement first; reclaim close with a 0.3 ATR body; stop beyond the sweep extreme; 2R; LIT's 15-minute check). At $500 risk a trade - 2026 H1 +$12.2k (PF 3.72), H2 (untouched) +$2.9k (PF 1.89), 2025 +$5.0k (PF 1.26), 2021-24 +$4.8k (PF 1.06); about 1.1-1.6 trades a week; daily correlation with LIT -0.05 in 2026. On one account with LIT (LIT priority, max 2 a day) 2026 goes from +$43.4k to +$58.0k with a smaller max DD (-$1,767 vs -$2,196). The edge outside 2026 is thin and leans on a few winners; the break-and-retest family did not survive. Also found - the earlier retail study's S/R level targets used the overnight high/low before 09:30 (look-ahead); fixed here.

## Money first

- **Paper-trade the NY sweep-and-reclaim next to LIT** on its own ledger (or a second, funded-style account at $300-$500
  risk). It is uncorrelated with LIT, trades other hours, made money in all four periods with costs in, and lifts 2026 from
  +$43.4k to +$58.0k on one account with a smaller drawdown.
- **Do not add it to the LIT eval account** (eval odds in H2 get slightly worse) and do not expect much before 2026:
  +$124 / month in 2021-24 and +$408 / month in 2025 at $500 risk.
- Nothing in LIT changes; `engine/lit.py`, `live_model*.json` and the live loop are untouched. Integrator: the rules and
  every trade are in `research/second/sr_best.json` (setup "nyreclaim"); the code is `tools/second_sr.py`.

Files: `tools/second_sr.py` (grid / pick / refine / stage2 / final / look-ahead), `research/second/sr_grid.json.gz` (all
stage-1 scores), `sr_refine.json.gz`, `sr_picks.json`, `sr_refine_picks.json`, `sr_stage2.json`, `sr_final.json`,
`sr_best.json`.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[retail-standalone|Retail strategies on their own]]
- Runs: `sr2_nyreclaim_usd500, sr2_nyreclaim_usd300, sr2_nyreclaim_lit, sr2_nyreclaim_with_lit, sr2_stage1_reclaim_h1, sr2_stage1_reclaim_ref, sr2_stage1_break_h1, sr2_stage1_break_ref`
- Source: `research/writeups/second-sr.md`
- Back to [[ZEUS Home]]
