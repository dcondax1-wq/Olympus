# REVIEW: v5 "trapped" (adversarial check, 2026-11-27)

Verdict of the review: **the NO holds.** I re-ran both looks from `core.py` in a separate script (in my scratchpad; none of
their files were rewritten). Every number matches to the cent: C3@look1 73 candidates, 11 labelled, 10 booked, +0.192R,
PF 1.61, +$494, DD $342, halves +0.325R (9, +$835) / -1.009R (1, -$342), gap +0.509, p 0.1218, Holm 0.4872. Look 2 C3
25 trades -0.043R +$690 DD $1,776 p 0.5105; T3 21 trades -0.038R -$697 p 0.24. The price-only books match per variant
(C1 43 / +0.106R / +$2,842, T1 33 / +0.153R / +$950, T3 67 / -0.193R / -$2,794, C3 55 / -0.001R / +$1,626).
`oos.py` prints "0 new usable days"; `--holdout 10` runs.

## What I tried to break
| check | result |
|---|---|
| Look-ahead | None found. B's close and delta decide the breakout. The decision is at F's close (F = B+1 for HOLD, B+1..B+2 for FADE). Entry is from F+1. The stop uses B..F only. SX = the max/min of RTH bars before B. ORB levels are used only from 10:00, and pdh/pdl/onh/onl are known before 09:30. |
| Fills too good | No. 0 "marketable" fills in any book. Limit fills at L need 1 tick through, and on that bar only the stop is checked. The rest is the market +18-tick fallback (8 of 10 C3@look1, 18 of 25 C3@look2), and stop fills are 2 ticks worse. If anything this is harsh: with a plain F+1-open entry, C3@look1 is 11 trades +0.28R and C3@look2 26 trades +0.12R +$1,792. But the label gap stays at +0.20 / -0.19R (p 0.35 / 0.72), so the NO is unchanged. |
| Costs | In: $1.90 a round turn plus the slippage above, R = net $ / risk $. |
| Design after results | Can't be settled from file times. DESIGN.md was last saved 09:31:11, and core.py, DESIGN_look2.md, run.py and results*.json were all rewritten 09:33:11-09:33:31, so no look-1-only file survives. The 2-minute window is short. The content argues against tuning: the 15% XD threshold labels 0 of 88 candidates (max signed share 12.6%), and no one picks that after seeing outcomes. A post-hoc design could only bias toward YES, so it can't undo a NO. |
| More variants than registered | 6 at look 1, plus the same 6 at look 2 (disclosed, dated addendum). Only the two thresholds changed. Frozen picks follow the stated rule (look 1: C3 lowest Holm; look 2: C3 over T3 on net $). |
| Placebo | Matches the design: a label shuffle over every resolved candidate. Overlapping candidates make it optimistic, not pessimistic. |
| Overlapping trades | 0 overlaps in any of the 12 books. |
| Halves | Correct: 26 / 25 days by date. |
| Threshold sweep (information only, my run) | C3 at BD 0.03-0.12: the newer-half gap is negative at every threshold except 0.04 (+0.03R, 12 trades). Best raw p 0.12 (at 0.08). There is no hidden threshold where the label works. |

## Errors in the write-up (none changes the verdict)
1. **Look-1 Holm is over 4 tests, not 6.** T2 and C2 have p = None, and `holm()` drops them, so m = 4. Over 6 as DESIGN
   says, C3@look1 Holm = 0.73 (not 0.49). That is more conservative and the verdict is the same.
2. **Trades/week is understated by about 14%.** 7 of the 51 days are Sundays (no RTH), but they count in the n/(51/5)
   divisor (the same issue as levels REVIEW). On 44 weekdays: C3@look1 1.14/wk (not 0.98), C3@look2 2.84/wk (not 2.45).
   The OOS trade-count projections scale the same way.
3. **R and $ disagree in sign for C3@look2** (-0.04R but +$690, PF 1.25). At a fixed 1 micro, wide-stop trades dominate
   the $, so the "+$" should not be read as an edge. Mean R (equal risk) is the honest number here.
4. Inherited from lane A levels (`of_battery.levels`): **Mondays get no pdh/pdl** because the "previous usable day" is the
   Sunday file. This hits KEY variants T1/T2/C1/C2, not the frozen C3 (SX). Thanksgiving 11-26 is traded once
   (T2@look2).

## Housekeeping
Running `oos.py` created `trapped/__pycache__/`. I deleted it. Nothing else in this folder was changed except this file.
