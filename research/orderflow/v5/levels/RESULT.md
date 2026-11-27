# Order flow v5 "levels": lane A's absorption fade at 5 more level types: RESULT (2026-11-27)

PAPER RESEARCH ONLY. Rules were written first in `DESIGN.md` (6 variants, before any number). Code: `core.py` + `run.py`
(numbers in `results.json`), out-of-sample scorer `oos.py`, frozen rules `frozen.json`.
Data: 51 real NQ tick-summary days, 2026-09-27..11-26. Entry E5 (limit at the level for 5 min, then market +18 ticks).
Stop 1 tick beyond the sweep bar, stop fill 2 ticks worse. 2R target that needs 1 tick through. $1.90 round trip. R includes costs.

## Verdict: NO. Absorption does not make these levels tradeable.
| var | levels | trades | /wk | win % | mean R | PF | $ at 1 micro | max DD | halves R (old / new) | gap abs-not (old / new) | placebo p | Holm | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L1 | prior-week H/L | 8 | 0.8 | 25 | -0.49 | 1.48 | +$106 | $195 | -0.79 / +0.39 | -2.72 / n/a | 0.78 | 1.0 | TOO FEW |
| L2 | Globex VAH / VAL / POC | 40 | 3.9 | 22.5 | -0.48 | 0.76 | -$652 | $1,162 | -0.25 / -0.86 | +1.00 / -0.13 | 0.14 | 0.84 | NO |
| L3 | naked prior-day POC | 3 | 0.3 | 0 | -1.08 | 0 | -$514 | $514 | n/a / -1.08 | n/a | 0.51 | 1.0 | TOO FEW |
| L4 | VWAP +/- 1 sd | 52 | 5.1 | 15.4 | -0.72 | 0.65 | -$1,042 | $1,475 | -0.67 / -0.77 | +0.11 / -0.39 | 0.64 | 1.0 | NO |
| L5 | round 00 / 50 | 188 | 18.4 | 21.8 | -0.57 | 0.69 | -$4,194 | $5,267 | -0.53 / -0.61 | -0.33 / +0.04 | 0.73 | 1.0 | NO |
| L6 | all of them together | 207 | 20.3 | 23.7 | -0.52 | 0.73 | -$3,986 | $4,005 | -0.42 / -0.60 | -0.11 / +0.10 | 0.50 | 1.0 | NO |
| (V0 control) | lane A's own levels, same simulator | 63 | 6.2 | 46.0 | +0.30 | 1.65 | +$2,648 | $1,164 | +0.21 / +0.41 | +0.96 / +0.68 | 0.026 | - | not scored |

In plain words:
- No new level type made money once absorbed. Every booked mean R is negative in both halves, except L1, which has 8 trades.
- Absorbed and non-absorbed trades do about equally badly (gap near 0, placebo p 0.14-0.78). At these levels the absorption read picks nothing.
- Round numbers and VWAP bands fire often (5-18 a week) and lose steadily. Prior-week H/L and naked POCs almost never get tested in the 09:45-15:00 window (9 and 4 candidates in 51 days).
- L2 (Globex value area) was the closest. Its absorption gap was +1.0R in the older half and gone in the newer half (-0.13R), and the trades lost money in both halves.
- The control V0 runs through the same simulator, and lane A's own levels still work: 93 of 93 signals and absorption reads match `engine/of_paper`, and 40 of 40 fill types match. So the NO is about the levels. It is not a simulator bug.

## Frozen for the out-of-sample test (picked by the pre-set rule, not by hand)
`frozen.json` = **L2 (Globex VAH/VAL/POC)** and **L4 (VWAP +/- 1 sd)**: the two best by (verdict, Holm p, net $). Both are NO.
They are frozen only so tonight's new real days give a clean second look. No improvement to them is expected.
Run after the pull: `python -X utf8 research/orderflow/v5/levels/oos.py` (prints the same table for days not in the 51; Holm over
the 2). Checked on a mock split (last 10 days held out): it runs.

## Side finding for the lead (lane A itself; nothing changed, engine/ untouched)
- `engine/of_paper.replay_summary` calls `step()` once for the whole day. Exits are resolved after the signal loop, so after the day's first taken trade every later absorbed signal is marked "busy".
- So lane A's in-sample book (40 trades, +0.49R) is really "the first absorbed signal of each day". The live PC runs `step()` every 5 min and would take the later ones too.
- With a true one-position-at-a-time rule, lane A takes 63 trades:
  - the 40 first-of-day trades: +0.48R;
  - the 23 later ones: -0.03R;
  - all 63: +0.30R, +$2,648 at 1 micro, label-shuffle p 0.026 (this simulator: costs in R, 2-tick stop slip).
- Lane A still holds up. But the forward paper bot (live, every 5 min) will book about 6 trades a week, not 4, and the extra ones look flat.
- The forward gate should either score first-of-day only (what history supports) or accept a lower mean.
- This is post-hoc: it is information for the lead's next dated design, not a rule change.

## Limits
- 51 days and one regime (autumn 2026). The 2021-25 check cannot be run (no ticks before 2026).
- Levels from 1-point profile bins.
- E5 is read from 5m bars only: on a bar where the limit fills at the level, only the stop is checked, which is conservative.
- No fishing: there were 6 variants, none was changed after the run, and the 2 thresholds that were clarified (Saturday gap, prior-week fallback source) were written into DESIGN.md before the first run.
