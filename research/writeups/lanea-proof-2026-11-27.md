# Lane A (absorbed level fade) stress test, 2026-11-27

PAPER RESEARCH ONLY: nothing here changes a bot, a size or an arming. Pre-registered first: `research/orderflow/DESIGN_lanea_proof.md`
(commit 9ed922a5, pushed before any result). Code `research/orderflow/lanea_proof/proof.py`, numbers `research/orderflow/lanea_proof/results.json`.
Data: 51 real NQ tick-summary days 2026-09-27..11-26 (PC, quote-rule sides). The re-simulator reproduces the paper bot's R on 93 of 93
signals. Costs $1.90 round trip per micro in everything. These are the SAME days look 1 found the candidate on: a stress test, not proof.

## Plain words
Lane A holds up under every fill and cost test, in both halves, and the bootstrap keeps the mean above zero. It's ~4.6 trades a
week with very wide stops (50-75 NQ points, $90-150 a micro). **All 4 pre-registered bars pass → worth a Sim101 forward test**
(behind a switch default OFF, Sim-only, owner's yes). But the SIZE test says the catch: if the edge turns out fake, any useful
size costs the evals a lot. The only size that is "free" at zero edge (risk cap $50, off near the floor) is so small it adds
~$100-200 per 6 months. So: forward-test it, and don't size it into an eval until the forward gate passes.

**Correction (02:00 ET):** the first eval run (sent to the lead at ~00:30 ET) had a bug. A stopped trade's worst open loss
used the whole 5m bar's low, even past the stop, so evals "failed" on losses the trade never held. Fixed (worst loss capped at
the stop fill). Bar 4 went from FAIL to PASS. Fill, split, bootstrap and halves numbers are unchanged (they never used it).

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
| Builder 50K | + lane A | 81.7% | 16.6% | 9 | $1,131 | +$7,530 | +$1,255 | 21% |
| Builder 50K | lane A alone | 78.7% | 7.2% | 14 | $1,188 | +$5,474 | +$912 | 14% |
| Builder 25K | LIT + ATLAS (today) | 73.0% | 0.0% | 13 | $545 | +$1,230 | +$205 | 9% |
| Builder 25K | + lane A | 88.0% | 3.1% | 10 | $557 | +$3,513 | +$586 | 21% |
| Builder 25K | lane A alone | 79.1% | 1.2% | 15 | $580 | +$2,551 | +$425 | 3% |
| Rapid EOD 25K | LIT + ATLAS (today) | 12.5% | 0.0% | 47 | $144 | +$64 | +$11 | 4% |
| Rapid EOD 25K | + lane A | 84.7% | 0.8% | 20 | $515 | +$4,819 | +$803 | 37% |
| Rapid EOD 25K | lane A alone | 74.7% | 1.2% | 22 | $597 | +$3,562 | +$594 | 3% |

Read: AS MEASURED, lane A adds money and passes faster. Funded blow-ups go up (7-9% → ~21%, Rapid 4% → 37%). Rapid EOD jumps
because LIT + ATLAS barely trade on these days. That is the "more trades" effect. All of this assumes the measured +0.50R is real.

## 7. Size test (pre-registered DESIGN_lanea_size.md; 1,000 paths; LIT + ATLAS as today; lane A at (a) measured / (b) half / (c) zero edge)
Sizes: fixed 1/2/3 micros, risk caps $50/$100/$150, ATLAS-style (REF); gates: UP (only after +$1,000 / +$500 above start), FLOOR (off
within $1,000 / $500 of the trailing floor). Full grid in `lanea_proof/size_results.json`. Key rows (eval pass / fail %, 6-mo net, funded blown %):
| plan | lane A size | (a) measured | (c) zero edge |
|---|---|---|---|
| Builder 50K | none (base) | 74.7 / 15.2, $3,309, 7% | same |
| Builder 50K | $50 cap, FLOOR (the pick) | 75.2 / 13.4, $3,424, 7% | 73.8 / 14.6, $3,335, 8% |
| Builder 50K | $150 cap, no gate | 84.2 / 9.5, $4,712, 2% | 71.1 / 25.4, $3,414, 17% |
| Builder 50K | 1 micro, UP+FLOOR | 75.4 / 15.7, $4,435, 8% | 73.3 / 16.2, $3,114, 15% |
| Builder 50K | ATLAS-style, no gate | 81.8 / 16.5, $7,552, 19% | 51.6 / 48.0, $2,354, 69% |
| Builder 25K | none (base) | 70.3 / 0.0, $1,318, 9% | same |
| Builder 25K | $50 cap, FLOOR | 72.3 / 0.0, $1,446, 8% | 71.1 / 0.0, $1,350, 9% |
| Builder 25K | $150 cap, FLOOR | 79.3 / 0.0, $2,359, 8% | 62.6 / 0.0, $1,072, 21% |
| Builder 25K | 1 micro, no gate | 65.4 / 34.6, $2,917, 43% | 43.6 / 56.4, $923, 78% |
| Builder 25K | ATLAS-style, no gate | 87.3 / 3.7, $3,510, 20% | 62.4 / 20.2, $1,199, 56% |
| Rapid EOD 25K | none (base) | 13.2 / 0.0, $79, 4% | same |
| Rapid EOD 25K | $50 cap, FLOOR | 25.3 / 0.0, $286, 7% | 19.0 / 0.0, $168, 6% |
| Rapid EOD 25K | $100 cap, FLOOR | 68.3 / 0.0, $1,415, 13% | 35.6 / 0.0, $378, 15% |
| Rapid EOD 25K | ATLAS-style, no gate | 84.9 / 1.0, $5,091, 36% | 36.0 / 16.7, $228, 41% |

Lessons: (1) a FIXED micro count that ignores the room is the worst. 1 micro on a 25K fails a third of evals, because lane A's own
1-micro drawdown (~$1,100) is bigger than a 25K's $1,000 max loss. (2) The FLOOR gate is the best single guard. (3) Only the $50 cap
(+ FLOOR / UP) is safe at zero edge on all three plans (pick rule → **$50 cap + FLOOR**). It trades only ~20% of lane A's signals
(stops <= ~23 pts) and adds just +$115 (50K) / +$128 (25K) / +$207 (Rapid) over 6 months as measured. (4) Anything that adds real $
($100-150 caps, 1 micro gated, ATLAS-style) costs 5-23 pass points or 5-60 blow-up points if the edge is zero.
**Bottom line: no size is both free and worth having. The money is only there if the edge is real → the forward gate decides, then size.**

## What next (forward gate, unchanged from the pre-registration)
Keep the paper shadow (engine/of_paper lane A) logging every day from 2026-11-27. It becomes an owner card for the evals only after
>= 30 resolved forward TAKEN trades with mean R >= +0.20 after costs, PF >= 1.30, TAKEN > SKIPPED, neither forward half below 0R,
max DD <= 6R. At ~4.6 trades/week that's ~6-7 weeks (mid-January). Then re-run `size.py` on the forward days. The size
candidates are $100-150 risk cap + FLOOR gate (best $ at measured edge with the smallest zero-edge damage). The nightly scoreboard spec
is `lanea_proof/LEAD_WIRES.md` (pure function `scoreboard.score`). Note: the 51 history days themselves score REJECTED on this gate
(max DD 6.06R > 6R), so the bar is strict. Fail = REJECTED into STRATEGY.md "Tested and rejected".
