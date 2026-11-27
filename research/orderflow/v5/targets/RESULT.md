# v5 / targets: does lane A's edge live in the exit? (2026-11-27)

PAPER RESEARCH ONLY. Pre-registered first: `DESIGN.md` (6 variants, written before any variant was run). Code `study.py`,
numbers `results.json` (1m path) and `results_5m.json` (the same rules on the 5m summary bars). Frozen for OOS: `frozen.json`;
out-of-sample scorer: `oos.py` (scores T3R + TOPP + the 2R reference on any day not in the 51).
Data: 51 real NQ tick-summary days 2026-09-27..11-26, all on NinjaTrader 1m bars. Same 93 lane A signals, 40 taken, all 40 filled by
E5 (29 at the level, 11 market +18 ticks). Costs $1.90 rt per micro, stop fill +2 ticks, targets need 1 tick through, market exits -2 ticks.
These are the SAME days lane A was found on (look 1) and stress-tested on: nothing here is proof.

## Verdict
**Exits do NOT hold the edge. The entry does.** Every exit on the same 40 entries makes money and every one passes the absorption
placebo, because the placebo tests the absorbed-vs-not gate, and that gate works under any exit (skipped signals lose under all of them).
The only exit that beats today's 2R in both halves is **T3R (3R target)**: +$615 more over 51 days (+$284 / +$331 by half).
It is a **YES-candidate** by the pre-registered bar (placebo p 0.0003, Holm 0.0018, both halves positive, beats 2R both halves).
But the exit's own gain is not proven. On the same 40 trades, a paired sign-flip test of "3R minus 2R" gives p 0.22, so the gain
could be chance. The 5m-path check points the same way (+$1,076 over 2R). Call it **weak: worth scoring forward, not worth switching.**

## Table (taken trades, E5 entry, 1m path, 1 micro)
| variant | trades | /wk | win % | mean R | PF | net $ | $/month | max DD $ | halves mean R (n) | halves $ | skipped R | placebo p | Holm p | vs 2R $ (halves) | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B2R 2R (today's rule, reference) | 40 | 3.9 | 52.5 | +0.54 | 2.38 | +$2,834 | +$1,167 | $570 | +0.71 (22) / +0.32 (18) | +1,374 / +1,459 | -0.29 | 0.002 | - | - | reference |
| T1R 1R | 40 | 3.9 | 62.5 | +0.24 | 1.99 | +$1,492 | +$614 | $568 | +0.35 / +0.09 | +735 / +756 | -0.30 | 0.008 | 0.029 | -$1,342 (-639 / -703) | YES-cand., worse than 2R |
| T15R 1.5R | 40 | 3.9 | 60.0 | +0.49 | 2.59 | +$2,644 | +$1,089 | $526 | +0.58 / +0.37 | +1,049 / +1,595 | -0.21 | 0.006 | 0.029 | -$189 (-325 / +136) | YES-cand., no better |
| **T3R 3R** | 40 | 3.9 | 52.5 | **+0.85** | 2.68 | **+$3,448** | **+$1,420** | $629 | +1.14 / +0.50 | +1,658 / +1,790 | -0.49 | 0.0003 | 0.0018 | **+$615 (+284 / +331)** | **YES-cand. (exit gain, paired p 0.22)** |
| TOPP opposite level | 40 | 3.9 | 32.5 | +0.49 | 2.21 | +$2,842 | +$1,170 | $512 | +0.25 / +0.79 | +1,308 / +1,534 | -0.48 | 0.017 | 0.034 | +$9 (-66 / +75) | YES-cand., a tie |
| TRAIL behind absorbed bar | 40 | 3.9 | 35.0 | +0.37 | 1.79 | +$1,094 | +$450 | $450 | +0.56 / +0.14 | +896 / +198 | -0.21 | 0.031 | 0.034 | -$1,740 (-479 / -1,262) | YES-cand., much worse |
| TS60 2R + 60-min stop | 40 | 3.9 | 52.5 | +0.50 | 2.69 | +$2,667 | +$1,098 | **$314** | +0.64 / +0.33 | +1,049 / +1,618 | -0.20 | 0.006 | 0.029 | -$166 (-326 / +159) | YES-cand., no better |
| TS30 2R + 30-min (descriptive) | 40 | 3.9 | 55.0 | +0.52 | 3.45 | +$2,704 | +$1,113 | $313 | +0.73 / +0.25 | +1,293 / +1,411 | -0.15 | 0.005 | - | -$130 | not tested |

Paired "variant minus 2R" sign-flip p (same 40 trades, one-sided): T1R 0.90, T15R 0.56, **T3R 0.22**, TOPP 0.50, TRAIL 0.87, TS60 0.66.
5m-path check (`results_5m.json`): same ranking. T3R +$4,278 vs 2R +$3,202, both halves better. T1R fails the second half (-0.02R).

## Plain words
- **Tighter targets lose money.** At 1R you win more often (62%), but the lane earns half as much.
- **The trailing stop behind absorbed bars is the worst exit.** It gets shaken out early in 29 of 40 trades.
- **The opposite level is a tie with 2R.** It wins only 1 trade in 3. Only 1 of 40 had no level and fell back to 2R.
- **Time stops cost little money and halve the drawdown** (60 min: max DD $314 vs $570, -$166). That makes them a risk
  tool, not an edge.
- **3R makes the most money** (+$1,420 a month at 1 micro vs +$1,167). It has 5 of 40 trades flat at 15:55 and a slightly bigger
  drawdown ($629). Its gain over 2R is about one good trade's worth on 40 trades, so it is not proven.
- Skipped signals lose under every exit, and they lose more under 3R (-0.49R). Absorption is the edge.

## Frozen for the out-of-sample test (the ~260 new days)
`frozen.json` holds T3R and TOPP (picked by the pre-registered rule: T3R had the most $; TOPP was next and a different kind of
exit). It also stores the 51 in-sample day list. Run after the pull:
`python -X utf8 research/orderflow/v5/targets/oos.py`
It prints the same table for B2R / T3R / TOPP, plus each variant's paired p against 2R. Days without 1m bars (before 2025-12-28)
run on their own 5m bars, and each mode is also shown alone. The OOS bar for each frozen variant: n >= 30, mean R > 0 and $ > 0 in
both OOS halves, placebo p < 0.05, Holm (2 variants) < 0.10. An "exit edge" also needs more net $ than 2R in both OOS halves.
**Switch lane A's paper target from 2R to 3R only if T3R passes OOS and beats 2R in both OOS halves.**

## Limits
40 taken trades, all from one 2-month regime. Inside a 1m bar the order of moves is unknown, so when one bar touches both the stop
and the target, the stop is counted first. Stop fills are modelled at +2 ticks, with no real fill measured. The taken set keeps the
lane's own "one position at a time" chain from its 2R replay, so a shorter exit would really free the slot for a few more trades.
That effect is not counted here, by design: the entries are the same for every variant.
