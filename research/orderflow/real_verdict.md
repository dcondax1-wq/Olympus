# Order flow on REAL NQ ticks: the verdict (2026-11-27)

Research only, paper. Rules frozen before the data: research/orderflow/DESIGN.md (battery), DESIGN_paper.md (paper bot).
Built by `python -X utf8 tools/of_realday_verdict.py`.

**Days:** 51 real tick days, 2026-09-27 to 2026-11-26 (0 forward days from 2026-11-27; the rest are history days the rules never saw). Sides: quote-rule sides (real bid/ask at each trade).

## 1. Does absorption separate winners from losers? (lane A, the pillar's level fade)

| | trades | mean R | won | $ at 1 micro |
|---|---|---|---|---|
| TAKEN (absorbed) | 40 | +0.49R | 50% | $+1,582 |
| SKIPPED (not absorbed / busy) | 53 | -0.31R | 24% | $-1,930 |

Shuffle p = 0.0065 (bar < 0.1); older / newer half difference in R: [1.399, 0.114]. Bar: >= 40 resolved signals, taken > skipped, both halves, taken $ > 0 after costs.

**YES: absorption separated winners from losers (a candidate: forward days decide)**

## 2. Does OF1 improve LIT?

**The decider = the battery's pre-registered OF1 (gain in BOTH halves, keeps >= 50%, placebo): TOO FEW.** The paper lane B lines below are the same filter over all days pooled (a weaker view).

## 2a. Paper lane B on the LIT replay

18 trades: all $+5,682 vs only-absorbed $+2,746 (gain $-2,936; kept 15, won 6 of 15 kept vs 1 of 3 skipped); skip-placebo p = 0.8551.

**TOO FEW: 18 of 20 LIT trades**

## 2b. Paper lane B on Zlarior's REAL trades

**TOO FEW: 0 of 20 LIT trades with an OF read**

## 3. The pre-registered battery (OF1-OF6)

State: ran, look 1.

- OF1 LIT only when absorbed: TOO FEW
- OF2 LIT skip blocks against: TOO FEW
- OF4 ATLAS MD only when absorbed: TOO FEW
- OF3A LVN rejection + delta: TOO FEW
- OF5 absorption reversal at PD/Globex levels: REJECTED
- OF6 CVD divergence at new RTH high/low: TOO FEW

Forward score (lane A taken trades on days from 2026-11-27): 0 of 20, +0.0R.

Nothing here changes a bot. A YES is a candidate for the forward test and then the owner's decision.
