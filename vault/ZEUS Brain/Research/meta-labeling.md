---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
type: "research"
date: "2026-10-23"
status: "rejected"
source: "research/writeups/meta-labeling.md"
aliases:
  - "Meta-labeling"
---

# Meta-labeling

> [!failure] Verdict: rejected
> rejected

**Full title:** Meta-labeling (quant / ML) - learn when a signal is likely to win, and size it x0.5 to x1.5

## Summary

Owner (2026-10-23) "What about quant, could you learn that?" - Lopez de Prado meta-labeling on LIT (630 trades), the three ATLAS members (1,395) and the two stop-hunt candidates (558 / 467, the negative control). From ~45-100 facts known at the fill (closed bars only, checked on data cut at the signal), small models (L2 logistic, depth-3 boosting and forest, calibrated; ridge / boosting for expected R) learn the chance of a win (R >= +0.5) in a purged, embargoed month-by-month walk-forward, and a model frozen before July 2026 predicts 2026 H2. The model only changes size (x0.5-x1.5, never a skip, trades per week unchanged). Result - the models do rank wins a little better than chance over the whole walk-forward (LIT AUC 0.60, ATLAS 0.67, permutation p 0.01), but almost all of it is mechanical - the R:R to the target alone (a far target is hit less often) scores 0.58 / 0.68. Expected R is not predictable at all (rank correlation ~0, negative in LIT H2). On 2026 H2 alone (40 LIT / 57 ATLAS trades) nothing beats shuffled labels once the 10 models are counted (p 0.75 / 0.19). As money - LIT size rule H2 +$8.5k vs flat +$9.5k (best of 13 sizings +$10.7k, but -$2.0k in H1); on the eval path every sizing passes fewer 2-week evals (H1 33-40% vs 57%, H2 46-51% vs 52%) because the two_week size is already at its caps; ATLAS 25K path - fewer dead evals in 2021-25 but fewer passes too. Stop-hunt control - no skill (AUC 0.52-0.53, p 0.54-0.61), as it should be. Strict bar (skill above shuffled in 95% AND better $ and eval odds in 2026 H2 AND 2021-25) - failed by every model on every strategy. Not built. Rerun when LIT has ~150 more 1m trades.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-23]]
- Runs: `ml_lit_lr_rank, ml_atlas_lr_rank, ml_sh_asia_lr_rank, ml_sh_trend_lr_rank`
- Source: `research/writeups/meta-labeling.md`
- Back to [[ZEUS Home]]
