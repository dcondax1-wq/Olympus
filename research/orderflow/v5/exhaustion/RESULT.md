# Order flow v5 "exhaustion": exhaustion prints, finished / unfinished auctions, delta exhaustion: RESULT (2026-11-27)

PAPER RESEARCH ONLY. Rules were written first in `DESIGN.md` (6 variants, before any outcome; only feature-distribution
counts were peeked, declared there). Code: `core.py` + `run.py` (numbers in `results.json`, ~2 s), out-of-sample scorer
`oos.py`, frozen rules `frozen.json`. No engine/ file touched, nothing committed.
Data: 51 real NQ tick-summary days, 2026-09-27..11-26. Pool = 283 new 1-hour highs/lows after 3 same-direction 5m bars
(09:45-15:00 ET). Entry: market at the next bar's open + 18 ticks (no level, so the E5 fallback). Stop 1 tick beyond the
signal bar's extreme, stop fill 2 ticks worse, one 2R target (X6: the extreme itself), $1.90 a round trip. R includes costs.

## Verdict: NO. No exhaustion mark is a tradeable edge. Two "weak" rows are frozen for tonight's new days.
| var | rule | trades | /wk | win % | mean R | PF ($) | $ at 1 micro | max DD | halves R (old / new) | gap label-minus-not (old / new) | placebo p | Holm | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| X1 | fade, thin top (exhaustion print) | 81 | 7.9 | 27.2 | -0.26 | 1.47 | +$1,461 | $1,118 | -0.50 / -0.02 | -0.04 / +0.35 | 0.17 | 1.0 | weak |
| X2 | fade, finished auction (1-pt top row one-sided) | 75 | 7.4 | 20.0 | -0.46 | 0.64 | -$1,396 | $2,627 | -0.73 / -0.23 | -0.20 / +0.05 | 0.62 | 1.0 | NO |
| X3 | fade, delta exhaustion after 3 push bars | 64 | 6.3 | 21.9 | -0.37 | 0.84 | -$616 | $1,430 | -0.72 / -0.05 | -0.28 / +0.32 | 0.42 | 1.0 | NO |
| X4 | fade, thin top AND delta exhaustion | 21 | 2.1 | 28.6 | -0.18 | 1.79 | +$749 | $271 | -0.66 / +0.11 | -0.17 / +0.44 | 0.17 | 1.0 | weak |
| X5 | fade, 2 of the 3 marks | 51 | 5.0 | 25.5 | -0.29 | 1.04 | +$116 | $1,024 | -0.65 / -0.01 | -0.18 / +0.31 | 0.26 | 1.0 | NO |
| X6 | revisit an unfinished extreme (with the push) | 130 | 12.8 | 30.0 | -0.50 | 0.30 | -$3,333 | $3,337 | -0.62 / -0.34 | -0.40 / +0.16 | 0.73 | 1.0 | NO |

In plain words:
- **Fading a fresh 1-hour high/low after a 3-bar push loses** whatever the footprint says: the whole pool, as if all taken, is
  -0.40R a trade (-$1,147 at 1 micro). Pushes into new extremes keep going more often than they exhaust.
- **The marks barely separate.** The best (X1 thin top, X4 thin + delta) are about +0.16 / +0.24R better than the rest
  (p 0.17, Holm 1.0), and only in the newer half. In the older half every mark was WORSE than no mark.
- **"Unfinished auctions get revisited" is false here** (X6): buying a pullback to retake an unfinished high wins 30%, -0.50R.
  Unfinished extremes were revisited LESS than finished ones (gap -0.13R).
- **Why X1/X4 show +$ but -R:** at 1 micro the few winners had wide stops (X1 winners median 26 pts risk vs losers 18; X4 65 vs
  30). At the house sizing (size follows the stop, $500 a trade) X1 loses **-$11,633** and X4 **-$2,408** over the 51 days.
  The 1-micro $ is a sizing accident, not an edge. Both also trade 7.9 / 2.1 a week (house wants 2-4).
- Even with a free entry (next open + 1 tick, information only) every mean R stays negative (X1 -0.13R, p 0.085 raw).
- Most of X1's money came in the last 10 days (+$1,484 of +$1,461), i.e. the first 41 days were net negative.

## Frozen for the out-of-sample test (pre-set pick rule, not by hand)
`frozen.json` = **X1 (thin top fade)** and **X4 (thin top + delta exhaustion fade)**: the two "weak" rows by (verdict, Holm,
net $). Neither is expected to pass; they are frozen so tonight's ~260 new real days give a clean second look.
Run after the pull: `python -X utf8 research/orderflow/v5/exhaustion/oos.py` (days in data/pc_days not in the 51, Holm over 2;
writes oos_results.json). Mock-split check (`--holdout-last 10`) runs.
To call either a candidate on the new days it must pass the same bar: >= 20 trades, net $ > 0, PF >= 1.2, mean R > 0 in both
halves, gap > 0 in both halves, placebo and Holm p < 0.10. Mean R > 0 matters most (the house sizes by the stop).

## Limits
- 51 days, one regime (autumn 2026); no 2021-25 test possible (no ticks before 2026).
- At a single NQ tick the extreme almost always has 1-2 contracts on one side, so the classic single-tick "zero print" fired
  in 1% of the pool; the 1-point (4-tick) row was used instead (declared in DESIGN.md before the run).
- Entry is modelled (market +18 ticks); exits on 5m bars, stop first when a bar touches both (conservative).
- No fishing: 6 variants, none changed after the run.
