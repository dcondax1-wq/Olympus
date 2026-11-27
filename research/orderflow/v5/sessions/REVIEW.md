# Adversarial review of v5 "sessions" (2026-11-27)

Re-ran core.py myself without writing into this folder (scripts in scratchpad/rev_ss/). S3 and V0 reproduce exactly:
S3 38 trades, +0.150R, PF 1.26, +$669, DD $1,319, halves -0.267 / +0.526, gap +0.203 / +0.966, p 0.0702, Holm 0.4212.
V0 63 trades, +0.295R, +$2,648. The "weak" label follows the pre-set bar correctly.

## Checked and clean
- No look-ahead: signal + absorption use the closed signal bar only; entry is on the next bar; ORB levels only from the 10:00
  bar, Globex levels only from 09:30. Case (c) in the entry rule (stop without a level touch) can never fire, so it is harmless.
- Fills are not too good: limit fill at the level, market fallback +18 ticks, stop checked first and alone on the fill bar,
  stop slip 2 ticks, gap-through uses the open. $1.90 cost is in both R and $.
- 6 variants tested = 6 in Holm; V0 / SW / time-of-day splits are marked descriptive. The freeze pick (S3, then S6 on net $
  among Holm-1.0 NOs) follows the rule. DESIGN.md is older than core.py and results.json (09:27 vs 09:29). File times cannot
  prove nothing ran earlier, but nothing in the content contradicts it.
- One position at a time; no double counting in S3. Halves are 26 / 25 days as written.

## Problems found
1. **S3 adds nothing new to lane A.** 23 of its 38 trades are the same trades as V0 (lane A): +0.475R. The 15 trades that
   only S3 takes (levels re-armed at 10:30) are **-0.348R**. So the midday "edge" is lane A's own trades again, not a new
   session effect.
2. **The $ total rests on one trade.** The best trade is +$674 (169-point stop). Without it S3 is -$5 at 1 micro; without
   the best two it is -$424. Trades with stops <= 60 points (24 of them) are -0.08R / -$119. All the positive R comes from 14
   wide-stop trades (+0.54R).
3. **Market +18 fills lose:** 18 trades at -0.15R; the 20 limit fills at the level are +0.42R.
4. **Sundays counted as trading days.** 7 Sunday files pass the 50,000-row filter, so the "51 days" are 44 weekdays plus 7
   Sundays. Effects: (a) trades/week is understated (S3 is really ~4.3/week, above the 2-4 house band; S6 ~24/week);
   (b) **on 7 of 9 Mondays PD H/L is missing**, because the "previous usable day" is the Sunday, which has no RTH. The same
   bug is in of_battery.levels, so lane A / V0 have it too. Fixed re-run (weekday-only usable list, 44 days): S3 37 trades,
   +0.10R, PF 1.28, +$709, p 0.069, Holm 0.42, older half -0.27R: **still weak, verdict unchanged**. V0 becomes 66 trades,
   +0.256R, +$2,588, p 0.044. All other variants are still NO / TOO FEW.
5. **$500-risk DD not reported.** At $500 risk S3 makes +$3,768 but its max DD is **$2,799**, which is bigger than a 50K
   eval's room. The "$1,550/month" line should carry that number.
6. The placebo shuffles the absorbed label, so it tests absorbed vs not absorbed, not "better than zero". The gap is helped
   by not-absorbed candidates being bad. This matches the design; it is not an error, but p 0.07 is no proof of profit.

## Corrected reading
S3 is weak by the rules, but as a new finding it is effectively NO: its edge is lane A's own 23 trades, its own 15 trades
lose, and the $ total depends on one trade. The main conclusions hold: there is no session window, FT is worse, ANY is noise.
Side fix worth doing in a separate task: skip weekend files when picking the "previous day" for PD H/L (core.py
_prev_usable and of_battery.levels).
