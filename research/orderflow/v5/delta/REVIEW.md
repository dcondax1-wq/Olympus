# Adversarial review of v5 "delta" (2026-11-27). PAPER ONLY.

**The claim holds: there is no YES-candidate. If anything, "weak" for O2 and O1 is generous.**

## Re-run
- `run.py` logic was re-run in memory, without writing results.json. All 6 rows match RESULT.md exactly, and the core.py sha matches frozen.json.
- O1 and O2 were rebuilt independently from the raw `NQ_bars5m.csv.gz` without core.py. The numbers match: O2 44 trades, -0.007R,
  +$620, PF 1.19, 38.6% wins; O1 26 trades, +0.098R, +$477, PF 1.17.
- `oos.py` runs and reports 0 new days.

## Checked, no problem found
- **Look-ahead: none.** Bar `t` is the bar's open (ofsum docstring). The overnight window ends with the 09:25 bar (mod < 570). The decision
  is made at the 09:35 close. M's z-score and breakout use only bars up to and including the signal bar, at its close. A V pivot is
  used only from m+2. The 15m extremes and CVD are taken at q's close.
- **Fills: not optimistic.** The limit needs 1 tick through. The fill bar checks only the stop, never the target, and the stop wins
  ties. Stops slip 2 ticks, gap-through stops fill at the open, and time exits slip 2 ticks. $1.90 a round turn is in R and in $.
  O2 got 44/44 limit fills. The only real-world risk is queue position, which RESULT.md already notes.
- **Book overlap: none.** O2 takes one trade per day (44 = 44 RTH days). The pool's opposite side is never booked.
- **Halves:** 26/25 of the 51 days, about 22 RTH days each. The $ halves add up to the total.
- **Placebo:** O2 uses a per-day sign flip and O1 a label shuffle, both as pre-registered. Holm is over 6.
- **Pre-registration:** file times run DESIGN 09:40:06, core 09:41:27, results 09:41:39, RESULT 09:43:03. The code follows the design,
  and only the 6 pre-registered variants are scored. One small mismatch: DESIGN says the entry bar opens at or before 15:55, but the code
  uses 15:45. This does not affect O, and M/V signals stop at 15:00.

## Weaknesses the claim understates
1. **O2's +$620 comes from fixed 1-micro sizing.** In R, PF is 0.99 and the sum is -0.33R. Under the project's rule (size follows the
   stop), constant $500 risk gives about **-$163**, not +$722. The +$722 is a rounding effect of floor(500/risk), which makes the
   size 0 on stops wider than $500.
2. **The result is fragile.** Drop O2's single best trade and net falls to +$47; drop two and it is -$521. A bootstrap of net $ puts the
   5th to 95th percentile at -$1,724 to +$3,049, with P(net <= 0) = 0.35. For O1, dropping the best trade gives -$96.
3. **Direction drift:** in the older half shorts made +0.33R and longs lost -0.31R. In the newer half both sides lose (-0.59 / -0.44).
   The positive gap R in both halves comes partly from "both sides lose, and the opposite side loses more". It does not show a profit.
4. O2 trades 5 a week, above the project's 2-4 a week band.
5. A small note in RESULT: the no-divergence V1 fades come to -0.53R on the resolved pool, not -0.51R. That is not a result, so it changes nothing.

Verdict unchanged: M1, M2, V1 and V2 are NO. O1 and O2 are at best "weak" (both about 0R in risk terms). Keep them frozen for the
out-of-sample run; do not trade them.
