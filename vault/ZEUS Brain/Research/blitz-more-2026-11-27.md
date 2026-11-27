---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/blitz
type: "research"
date: "2026-11-27"
status: "rejected (no change) - research only, nothing live touched"
source: "research/writeups/blitz-more-2026-11-27.md"
aliases:
  - "BLITZ more tests"
---

# BLITZ more tests

> [!failure] Verdict: rejected
> rejected (no change) - research only, nothing live touched

**Full title:** BLITZ more tests (2026-11-27 night) - 12 pre-registered variants + 1 combination; 0 picked on Jan-Jun, nothing makes 2021-25 hold up

## Summary

Owner - "BLITZ, I want more tests". 12 single changes to today's BLITZ (fewer trades a day, loss-streak pause, time cutoffs, morning / afternoon only, daily-trend filter, VIX filter, stop cap, tighter / wider stop, 2R target, 60-minute hold) written down in research/blitzmore/DESIGN.md before the first run, judged pick Jan-Jun 2026, check Jul-Nov 2026 + 2021-25, costs in, Holm-corrected. 0 of 12 beat today on Jan-Jun, so none was picked; the best 2021-25 numbers cost 2026 money and are not significant (Holm p 1.0).

## Money first

**Nothing makes 2021-25 hold up.** The two changes that lift 2021-25 the most (60-minute hold $160, afternoon only $150 a month) are still PF 1.10 / 1.16 with
2024 negative, Holm p = 1.0, and each gives back $450-650 a month of Jan-Jun. The 2021-25 weakness is the market (a bet on trending years: blitzv2), not a setting.
Keep BLITZ paper only (the forward gate stands), no Decide card. Re-test only with new data.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-27]]
- Strategies: [[BLITZ (paper)]]
- Runs: `none (research/blitzmore/results.json, explore.json); code research/blitzmore/{blitzmore,explore,evals}.py on research/blitzv2 (parity 397/397 on 2026 1m, 2,304/2,304 on 5m)`
- Source: `research/writeups/blitz-more-2026-11-27.md`
- Back to [[ZEUS Home]]
