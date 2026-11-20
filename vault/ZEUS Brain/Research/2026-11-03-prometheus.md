---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-11-03"
status: "rejected - nothing to switch (every seed's champion loses money on 2026 H2 and 2021-25 against live LIT)"
source: "research/writeups/2026-11-03-prometheus.md"
aliases:
  - "PROMETHEUS"
---

# PROMETHEUS

> [!failure] Verdict: rejected
> rejected - nothing to switch (every seed's champion loses money on 2026 H2 and 2021-25 against live LIT)

**Full title:** PROMETHEUS - a genetic algorithm evolves the live LIT's ten knobs on 2026 H1; does anything it breeds beat live on H2?

## Summary

A seeded genetic algorithm (24 creatures x 20 generations, 5 independent seeds, 1,875 distinct variants) evolved ten numeric knobs of the live LIT (live_model_lit.json - 1m CISD window, breakeven R and offset, the early-check minute, the target bank, the VIX target multiple, the minimum target, the displacement filter, the last entry time and the eval room share) with a fitness computed on 2026 H1 only - $ per month (LIT size rule, costs in) and MFFU 50K eval speed (p10 - f10 on the live two_week eval path), penalised under 2 trades a week. It found big H1 gains (champions +$738 to +$2,311 a month, 2-week passes 64-76% vs 57%), and none of it survives. On 2026 H2 every champion makes LESS than live (-$675 to -$1,566 a month; primary seed -$675, weekly-block bootstrap 5-95% -$1,622 to +$6), and on 2021-25 every champion is worse too (-$150 to -$576 a month). H1 rank predicts H2 rank only weakly (Spearman 0.28 on fitness, 0.14 on $ per month); 247 of 349 checked variants make more $ a month than live on H1, 3 on H2, none on both. Live LIT sits on a plateau; the GA's recurring "improvements" (a looser 0.65 ATR displacement for more trades, a smaller eval room share for fewer fails) are already-rejected ideas (lit-more-setups.md, uprisk.md). Research only; live_model*.json untouched.

## Money first

**Rejected: nothing to propose.** No variant beats live LIT on 2026 H2 by a real margin; every seed's champion is worse on H2
and on 2021-25. `live_model.json` / `live_model_lit.json` are unchanged. This is the same picture as every hand search since
2026-10-18: the live knobs sit on a plateau, and an optimiser on six months of data mostly fits that half's noise.

If the owner ever wants to rerun it on more data (e.g. after the Dec 2026 roll, with H2 grown): `python -X utf8 -m
tools.prometheus.forge` (5 seeds, ~10 minutes on one core), then read `research/prometheus/forge_results.json`.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-03]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-more-setups|LIT more setups a week]], [[uprisk|Uprisk]]
- Runs: `prometheus_s7, prometheus_s11, prometheus_s23, prometheus_s42, prometheus_s101`
- Source: `research/writeups/2026-11-03-prometheus.md`
- Back to [[ZEUS Home]]
