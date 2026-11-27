# Order flow v5 "trapped": trapped-trader fades and initiative continuations: RESULT (2026-11-27)

PAPER RESEARCH ONLY. Nothing in engine/ was touched, no order, no commit. Rules written first: `DESIGN.md` (6 variants, look 1),
then a dated post-hoc addendum `DESIGN_look2.md` (written after look 1, before look 2: only the two delta thresholds changed).
Code `core.py` (reuses the v5 levels simulator) + `run.py` -> `results.json` (look 1), `results_look2.json` (look 2), `frozen.json`;
out-of-sample scorer `oos.py`. Data: 51 real NQ tick-summary days 2026-09-27..11-26. Entry E5 (limit at the broken level 5 min,
then market +18 ticks). Stop 1 tick beyond the breakout excursion, stop fill 2 ticks worse, one 2R target, $1.90 round trip, R with costs.

## Verdict: NO. Heavy aggressive delta on a key-level breakout tells us nothing about what happens next.

Look 1 (pre-registered thresholds: breakout-bar delta >= 8% of volume, beyond-level delta >= 15%):
| var | idea | trades | /wk | win % | mean R | PF | $ 1 micro | max DD | halves R (old / new) | placebo p | Holm | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | fade failed key break, bar delta | 2 | 0.2 | 50 | +0.47 | 1.93 | +$79 | $84 | +0.47 / none | 0.43 | 0.87 | TOO FEW |
| T2 | fade failed key break, beyond-level delta | 0 | 0 | - | - | - | $0 | $0 | - | - | - | TOO FEW |
| T3 | fade failed new session high/low | 9 | 0.9 | 33 | -0.03 | 0.41 | -$583 | $866 | +0.26 / -1.01 | 0.29 | 0.87 | TOO FEW |
| C1 | key break holds, bar delta | 9 | 0.9 | 33 | -0.34 | 0.45 | -$576 | $576 | -0.25 / -1.01 | 0.74 | 0.87 | TOO FEW |
| C2 | key break holds, beyond-level delta | 0 | 0 | - | - | - | $0 | $0 | - | - | - | TOO FEW |
| C3 | new session high/low holds, bar delta | 10 | 1.0 | 50 | +0.19 | 1.61 | +$494 | $342 | +0.33 (9) / -1.01 (1) | 0.12 | 0.49 | TOO FEW |

Look 2 (POST-HOC, thresholds 5% / 5%; seen look 1 first, so this is not a clean test):
| var | trades | /wk | win % | mean R | PF | $ 1 micro | max DD | halves R | gap labelled - not | placebo p | Holm | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | 10 | 1.0 | 30 | -0.15 | 1.29 | +$175 | $351 | -0.04 / -1.13 | -0.18 | 0.65 | 1.0 | TOO FEW |
| T2 | 12 | 1.2 | 42 | +0.13 | 2.47 | +$663 | $265 | +0.16 / +0.11 | -0.06 | 0.55 | 1.0 | TOO FEW |
| T3 | 21 | 2.1 | 33 | -0.04 | 0.58 | -$697 | $1,021 | -0.04 / -0.03 | +0.24 | 0.24 | 1.0 | NO |
| C1 | 17 | 1.7 | 35 | -0.10 | 0.93 | -$179 | $1,617 | +0.02 / -0.36 | +0.02 | 0.48 | 1.0 | TOO FEW |
| C2 | 10 | 1.0 | 40 | +0.09 | 2.37 | +$1,630 | $904 | -0.18 / +0.49 | +0.17 | 0.37 | 1.0 | TOO FEW |
| C3 | 25 | 2.5 | 36 | -0.04 | 1.25 | +$690 | $1,776 | -0.14 / +0.08 | -0.01 | 0.51 | 1.0 | NO |

In plain words:
- Look 1 was badly set: my "heavy delta" bars were too rare (2-11 of 35-73 breakouts), and the beyond-level threshold flagged
  none at all. That was checked, and it is not a bug. The volume that trades beyond a level is 5,000-30,000 contracts, so its net
  delta is only a few %. Every variant: TOO FEW.
- Look 2 lowered the bar to "top 30%". Now the label fires, and it picks nothing. The delta-heavy breakouts do no better than the
  others (gap -0.18 to +0.24R, every placebo p 0.24-0.65, Holm 1.0). No variant is positive in both halves with a real gap.
- The price pattern alone (label ignored; information only, not scored, not order flow):
  - key break that holds 1 bar: 43 trades, +0.11R, +$2,842;
  - failed key break faded: 33 trades, +0.15R, +$950;
  - failed new session high/low faded: 67 trades, -0.19R, -$2,794 (fading failed new highs/lows loses);
  - new session high/low that holds: 55 trades, 0.00R, +$1,626.
  These are post-hoc numbers on 51 days. They would need their own dated design and the 2021-25 check (bars only, possible).
- The difference from lane A: lane A reads PASSIVE absorption at a one-bar rejection, and that works. Aggressive delta on a bar
  that CLOSES beyond the level adds nothing on these days, fade or follow.

## Frozen for tonight's new days (picked by the rule fixed in DESIGN_look2.md, not by hand)
`frozen.json` = **C3@look1** and **C3@look2**: "new RTH high/low (after 10:00) closes beyond, the next bar holds, the breakout bar's
delta is >= 8% (look 1) / >= 5% (look 2) of its volume, buy the retest (E5), 2R". Both are weak or NO in-sample. They are frozen
only so the ~260 new real days give a clean read: about 1 and 2.5 trades a week, so roughly 50 and 125 OOS trades.
Run after the pull: `python -X utf8 research/orderflow/v5/trapped/oos.py` (same table, Holm over the 2). Plumbing was checked with
`--holdout 10` (last 10 in-sample days treated as new: it runs; that output is not a result).

## Limits
- 51 days, one autumn-2026 regime; halves are thin (several variants have 0-2 newer-half trades).
- Look 2 is post-hoc: 12 tests in this family. Even a look-2 pass would only have been "weak".
- E5 on 5m bars only (on a level-fill bar only the stop is checked). Most continuation fills were the market +18-tick fallback
  (the retest often never came), and that cost is modelled, not measured.
- No 2021-25 check possible for the order-flow label (no ticks before 2026).
