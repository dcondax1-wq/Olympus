---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
type: "research"
date: "2026-11-17"
status: "rejected - 0 of 354 cells hold in 2026 H1, H2, 2025 and 2021-24 (coin-flip directions give 3.7); no H1 pick exists at 2-4 trades a week; nothing built, nothing live changed"
source: "research/writeups/new-strategy-hunt-2026-11-17.md"
aliases:
  - "New-strategy hunt"
---

# New-strategy hunt

> [!failure] Verdict: rejected
> rejected - 0 of 354 cells hold in 2026 H1, H2, 2025 and 2021-24 (coin-flip directions give 3.7); no H1 pick exists at 2-4 trades a week; nothing built, nothing live changed

**Full title:** New-strategy hunt - a third NQ strategy for more winning days (lunch squeeze, PM continuation, value-area failed auction, 80% rule, London extension fade) - nothing passes

## Summary

Lead order 2026-11-17 - MFFU payouts need many winning days (Rapid 30% best-day rule, Builder funded 50% consistency) and LIT trades ~2.5 times a week, so find a third strategy that wins on days LIT and ATLAS don't. Four new families on CME NQ1! 5m RTH (costs in, stops 1 tick beyond structure, $500 a trade, one trade a day), 354 cells counted, hypotheses fixed before the run - LSQ lunch-range squeeze -> PM break (with / against / any AM trend; covers the 14:00-15:30 continuation idea), FAV failed auction at the prior session's value-area edge (volume profile from 5m bars), D80 Dalton's 80% rule, LXF London 02:00 -> 09:30 extension fade at the NY open. The first pullback after a 2-sigma opening drive was discarded as already covered (hq-continuation, BLITZ opening drive). Result - 0 cells hold in all four spans vs 3.7 with coin-flip directions; only 24 cells trade 2-4 a week in H1 and none of them has PF >= 1.2 there, so there is no H1 pick. Correlation with LIT is ~0 everywhere (-0.11..+0.12 daily), but none makes money that holds; an own Builder 50K at $400 a trade passes 0% within 40 sessions. The PM continuation WITH the AM trend is positive in 71 of 72 cells in 2021-24 and 0 of 72 in 2026 H1 (the E2 "late break" pattern again). Nothing adopted.

## Money first

Nothing passes. No third strategy, no new account, nothing built; LIT and ATLAS unchanged. The ideas in this hunt (lunch
squeeze, 14:00-15:30 continuation, value-area failed auction, 80% rule, London extension fade) go on the "Tested and
rejected" list. Not done: 1m execution (the 1m file starts 2025-12-29, so it could not check 2021-25; with no 5m survivor
there was nothing to confirm), ES context (ES 5m only from 2025-04).

Reproduce: `python -X utf8 tools/new_hunt.py grid` (~5 min) -> `research/second/new_hunt.json` (every cell's spans).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-17]]
- Refers to: [[blitz-25k|BLITZ on its own MFFU Builder 25K]], [[hq-continuation|HQ continuation]], [[nq-new-strategies-2026-11-13|New NQ strategies for more eval accounts]], [[public-strategies-2026-11-17|Famous published strategies on CME NQ]], [[vwap-volume-profile|VWAP and volume profile as confluence]]
- Runs: `(no rl runs) research/second/new_hunt.json, tools/new_hunt.py`
- Source: `research/writeups/new-strategy-hunt-2026-11-17.md`
- Back to [[ZEUS Home]]
