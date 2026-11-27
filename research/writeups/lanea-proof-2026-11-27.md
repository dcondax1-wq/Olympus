# Lane A (absorbed level fade) stress test, 2026-11-27

PAPER RESEARCH ONLY: nothing here changes a bot, a size or an arming. Pre-registered first: `research/orderflow/DESIGN_lanea_proof.md`
(commit 9ed922a5, pushed before any result). Code `research/orderflow/lanea_proof/proof.py`, numbers `research/orderflow/lanea_proof/results.json`.
Data: 51 real NQ tick-summary days 2026-09-27..11-26 (PC, quote-rule sides). The re-simulator reproduces the paper bot's R on 93 of 93
signals. Costs $1.90 round trip per micro in everything. These are the SAME days look 1 found the candidate on: a stress test, not proof.

## Plain words
Lane A holds up under every fill and cost test, in both halves, and the bootstrap keeps the mean above zero. But it is ~4.6 trades
a week with very wide stops (50-75 NQ points), and bolted onto the evals at ATLAS-style size it roughly doubles the eval fail rate
and makes funded accounts blow up far more often. **Verdict: keep it running in the paper shadow bot (free, already logging) and
let forward days decide. No Sim101 routing needed (fills don't move the result) and no eval/funded use.** Pre-registered bar 4 failed.

## 1. Fills and costs (taken trades, 1 micro MNQ)
| fill model | trades | /week | won | mean R | PF ($) | net $ | $/month | max DD $ |
|---|---|---|---|---|---|---|---|---|
| F1 next open +1 tick (paper) | 40 | 4.6 | 50% | +0.50R | 1.55 | +$1,563 | +$780 | $1,101 |
| F2 +2 ticks | 40 | 4.6 | 50% | +0.50R | 1.56 | +$1,573 | +$785 | $1,104 |
| F3 +3 ticks | 40 | 4.6 | 50% | +0.50R | 1.56 | +$1,583 | +$790 | $1,107 |
| FS stop fills 2 ticks worse | 40 | 4.6 | 50% | +0.49R | 1.55 | +$1,553 | +$775 | $1,107 |
| FL limit at the level (15 min) | 31 (9 missed) | 3.6 | 45% | +0.34R | 0.97 | -$35 | -$18 | $499 |

Skipped signals at F1: 53, -0.31R, -$1,956. Gap +0.81R. A tick or two of slippage is nothing against a ~250-tick stop, so the
market entry is fine. A limit at the level is WORSE: it only fills when price comes back through the level (bad selection).
Note: 1R at 1 micro is about $80-150 here because the stops are so wide.

## 2. Splits (F1, descriptive only, too small to pick from)
| split | taken n | mean R | net $ | skipped mean R |
|---|---|---|---|---|
| Globex H/L | 18 | +0.50 | +$1,209 | -0.31 |
| ORB H/L | 16 | +0.87 | +$1,030 | -0.25 |
| prior-day H/L | 6 | -0.51 | -$676 | -0.58 |
| 09:45-10:30 | 32 | +0.40 | +$798 | -0.10 |
| 10:30-12:00 | 7 | +1.14 | +$793 | -0.20 |
| 12:00-15:00 | 1 | -1.02 | -$28 | -0.75 |
| long | 17 | +0.23 | -$199 | -0.47 |
| short | 23 | +0.69 | +$1,761 | -0.14 |
| absorption weak / mid / strong (thirds) | 13 / 14 / 13 | +0.61 / +0.50 / +0.38 | +$836 / +$789 / -$63 | - |

Stronger absorption is NOT better (no dose-response): a warning sign that part of the gap may be luck. Prior-day levels and longs
are weak; with 6 and 17 trades that is noise. Nothing gets filtered on this.

## 3. Week by week and the bootstrap
Positive weeks: 6 of 9 (W40 +1.0R, W41 +7.0, W42 +2.0, W43 +6.9, W44 -2.0, W45 -2.0, W46 0.0, W47 +2.0, W48 +5.0).
Day-block bootstrap of taken mean R: +0.49R, 90% CI [+0.11, +0.89], 95% CI [+0.03, +0.97], P(mean <= 0) = 1.8%.

## 4. The halves problem
| | older 09-27..10-27 | newer 10-28..11-26 |
|---|---|---|
| candidates / day | 1.84 | 1.81 |
| taken | 21, +0.71R, PF 1.88, +$954 | 19, +0.26R, PF 1.35, +$609 |
| skipped mean R | -0.59R | -0.06R |
| mean stop (ticks) | 200 | 303 |
| mean RTH range (pts) | 376 | 667 |
| exits target / stop | 12 / 9 | 8 / 11 |

Why the newer half is weaker: same number of setups, but the market got much wilder (daily range +77%, stops 50% wider). Taken
trades still made money (+0.26R). Most of the gap's shrink is the SKIPPED trades getting better (-0.59R to -0.06R), not the taken
trades breaking. So it's a regime problem, not fewer setups. It also means absorption picks winners less well when everything is moving fast.

## 5. Overlap with LIT / ATLAS
LIT 18 trades and ATLAS 5 (ATLAS cache reaches only 10-09) on these days. 3 of 40 lane A trades were open at the same time as a LIT/ATLAS
trade (lane A +1.0R on those). On one account, one-at-a-time would block a few trades. Not a real conflict.

## 6. MFFU engines (rank.py machinery, live LIT sizing, lane A sized like ATLAS: $500 on 50K / $250 on 25K, 30% of room)
2,000 bootstrap paths of the 51 real days only (one regime, the same days the edge was found on = optimistic for lane A).
| plan | stream | eval pass | fail | median days | eval DD median | 6-mo net | $/month | funded blown |
|---|---|---|---|---|---|---|---|---|
| Builder 50K | LIT + ATLAS (today) | 76.0% | 14.2% | 11 | $1,099 | +$3,190 | +$532 | 7% |
| Builder 50K | + lane A | 70.3% | 28.9% | 8 | $1,378 | +$6,036 | +$1,006 | 47% |
| Builder 50K | lane A alone | 59.5% | 33.2% | 14 | $1,479 | +$3,397 | +$566 | 56% |
| Builder 25K | LIT + ATLAS (today) | 73.0% | 0.0% | 13 | $545 | +$1,230 | +$205 | 9% |
| Builder 25K | + lane A | 73.8% | 21.0% | 9 | $626 | +$2,674 | +$446 | 50% |
| Builder 25K | lane A alone | 58.5% | 30.6% | 14 | $671 | +$1,444 | +$241 | 50% |
| Rapid EOD 25K | LIT + ATLAS (today) | 12.5% | 0.0% | 47 | $144 | +$64 | +$11 | 4% |
| Rapid EOD 25K | + lane A | 59.2% | 29.3% | 20 | $671 | +$2,385 | +$398 | 66% |
| Rapid EOD 25K | lane A alone | 47.0% | 36.8% | 21 | $711 | +$1,438 | +$240 | 43% |

Read: on these days lane A adds money on paper but at a big cost in risk. Fail % doubles on Builder 50K (bar 4: pass -5.7 pts = FAIL),
funded accounts get blown in about half the runs, and the bad-case result (p10) on Rapid gets worse. Rapid EOD 25K jumps because LIT + ATLAS
alone barely trade on those days. That is the "more trades" effect, not proof. In-sample days + one regime + 40 trades = not for live money.

## Pre-registered bars
1 F2 taken mean R > 0: PASS (+0.50R). 2 bootstrap 90% CI low > 0: PASS (+0.11R). 3 both halves > 0: PASS (+0.71 / +0.26R).
4 adding lane A costs <= 2 pts of eval pass on every plan: **FAIL** (Builder 50K -5.7 pts). Not forward-worthy for Sim101 routing.

## What next (forward gate, unchanged from the pre-registration)
Keep the paper shadow (engine/of_paper lane A) logging every day from 2026-11-27. It becomes an owner card for the evals only after
>= 30 resolved forward TAKEN trades with mean R >= +0.20 after costs, PF >= 1.30, TAKEN > SKIPPED, neither forward half below 0R,
max DD <= 6R. At ~4.6 trades/week that's ~6-7 weeks (mid-January). Even then, the eval size has to be re-tested smaller than ATLAS's
$500/$250 (the funded blow-up rate above is the problem to solve). Fail = REJECTED into STRATEGY.md "Tested and rejected".
