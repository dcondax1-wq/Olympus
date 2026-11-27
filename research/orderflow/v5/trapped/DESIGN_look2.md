# v5 "trapped" ADDENDUM, look 2 (written 2026-11-27 AFTER look 1, BEFORE running look 2). POST-HOC: not a clean test.

## Why
Look 1 (DESIGN.md, thresholds BD 0.08 / XD 0.15) labelled almost nothing: BD 2-11 of 35-73 candidates, XD 0 of 35-53. All 6
variants TOO FEW (< 20 booked). Checked it is not a bug: the beyond-level cells hold 5,000-30,000 contracts, so their delta
share is only a few % (my XD threshold was never checked against its distribution; BD 0.08 was the RTH-bar 88th pct, and
breakout bars are not more one-sided than that). What I have seen: look-1's table (outcomes at 0.08 / 0.15), the price-only
books, and the candidates' bd_share percentiles (median ~0.04, p75 ~0.055) plus 8 XD values (|dx|/vx 0.5-7%).

## The one change (nothing else moves: same 6 variants, levels, patterns, entry, stop, target, costs, scores, pass bar)
- BD: delta[B] x dir >= **0.05** x volume[B] (the RTH-bar 70th pct of |delta| share, known before look 1: "top 30%").
- XD: vx >= 100 and dx x dir >= **0.05** x vx.
Run as look 2: `run.py --look 2` -> results_look2.json; Holm over its 6. Twelve tests have now been run in this family;
the look-2 Holm (over 6) is reported with that note, and a look-2 YES is at best "weak" in my RESULT (post-hoc).

## Freeze rule (fixed now): frozen.json = 2 variants
1. Look 1's best by (verdict, Holm p, net $) = C3 (already fixed by look 1).
2. Look 2's best by the same key if its verdict is better than TOO FEW, else look 1's second (T1).
`oos.py` scores each frozen variant with ITS look's thresholds. The new real days decide; in-sample decides nothing.
