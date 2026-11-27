# REVIEW: v5 exhaustion (adversarial check, 2026-11-27). PAPER ONLY. No other file in this folder was edited.

**Verdict: the NO holds.** I tried to break it and could not. I re-ran every number from core.py with my own script
(scratchpad/exrev/r1.py..r3.py, no writes here) and got exactly the same results: 283 pool bars; X1 81 trades, -0.26R, PF 1.47, +$1,461,
DD $1,118, $500-risk -$11,633, p 0.1726; X4 21 trades, -0.18R, +$749, -$2,408 at $500; X6 -$3,333.

## Checked, clean
- Look-ahead: none. The labels, the new 1-hour extreme, the stop and X6's room all use bar i, which is closed when the decision is made.
  The entry is bar i+1's open. The footprint rows line up with their own bar: on all 11,884 bars, k runs exactly 0..range.
- Fills: the market entry is open +/-18 ticks against us, so it is worse than the open and never better. Stop-first when a bar hits
  both, the target needs 1 tick through, stops fill 2 ticks worse and a gap fills at the open. Every one of these choices is
  conservative. Costs are $1.90 a round trip, inside R. The free entry (+1 tick) is still negative (X1 -0.13R, X4 -0.20R).
- Overlap: the busy rule books one position per variant. An up push and a down push can't happen on the same bar.
  Halves are split by day, 26 older / 25 newer, as the design says.
- Pre-registration: the files were saved in this order: DESIGN.md 09:35:08, core.py 09:35:46, results.json 09:35:48. I found no
  exhaustion result anywhere before that. There are 6 variants in the design and 6 in the code, with matching thresholds.
  The freeze pick follows the stated rule. (File times can't prove the design came first, but nothing contradicts it.)
- Data looks sane: NQ is about 26-29k and the median 5m RTH range is 42 points. I checked the top winners by hand and their bars are real.

## Problems found (none changes the verdict)
1. **Trades/week is understated.** The 51 "days" include 7 Sundays that have no RTH bars at all, so there are only 44 sessions,
   one of them Thanksgiving, which closed early. Real rates: X1 **9.2/wk** (not 7.9), X4 **2.4/wk** (not 2.1),
   X6 14.8/wk, and the pool 32/wk (not 27.7). The halves are really 23 vs 21 trading days. Same formula in oos.py.
2. **The placebo p is optimistic.** 124 of the 283 pool bars sit right next to another pool bar, so their as-if outcomes overlap.
   The shuffle treats them as independent, which makes p too small. A day-clustered bootstrap of X1's booked mean R gives
   a 90% CI of [-0.50, +0.00], and for X4 [-0.62, +0.30]. Neither is above zero.
3. **The "weak" label and PF come from sizing.** X1's 5 biggest winners make +$2,475, more than the whole net (+$1,461).
   Those 5 had stops of 87-154 points. The median trade is -1.05R. X1's first 41 days net -$24, and the last 10 make
   +$1,484. Under the house rule (size follows the stop) there is nothing here. RESULT.md already says this, and I confirm it.
4. X1 and X4 are nested (X4 is a subset of X1), so the two frozen OOS tests aren't independent evidence.

**Bottom line:** NO. X1 and X4 shouldn't go near a bot unless they show mean R > 0 on new days at house sizing. I see no
reason to expect that.
