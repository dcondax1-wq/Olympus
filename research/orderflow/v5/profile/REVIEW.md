# REVIEW: v5 "profile" (adversarial reviewer, 2026-11-27)

Verdict: the headline HOLDS. There is no YES-candidate, all 6 variants are TOO FEW, and P6 is the only one that made money.
Some supporting claims are worded too strongly (see 1-3).

## What I re-ran (scripts in the reviewer scratchpad, no file here was changed)
- core.py run on the same 51 days reproduces every P3/P6 number exactly: P6 has 22 candidates, 19 resolved, 15 absorbed,
  15 booked, +0.367R, PF 1.92, +$595, $500-risk +$2,894, max DD $166, placebo p 0.079, halves +0.52R/$277 and +0.19R/$317.
- **1m re-simulation of the 15 P6 trades** (data/NQ_1m.csv plus the day offset, same E5/stop/target rules on 1m bars, stop
  first in a minute): the same 15 outcomes (every stop and target matches), +$626, +0.367R. The 5m coarse fills do not
  flatter it.
- Look-ahead: none found. The absorption zone, the stop and the signal all come from the signal bar, which has closed.
  Entry starts on the next bar. The prior profile uses only the prior RTH day. The LVN composite uses only bars before 09:30.
- Costs are in ($1.90 a round turn, stop +2 ticks, flat -2 ticks, the target needs 1 tick through). No booked trades overlap
  (busy = 0). The halves split 26/25 days correctly.
- Pre-registration: file times are DESIGN 09:37:32, then core 09:38:17, then results 09:38:45. File times cannot prove
  the order. The content argues against tuning: the P4 gate fired 0 times and was left unchanged. P3 and P6 reuse lane A's
  known absorption gate, as DESIGN admits.

## Problems
1. **"P6 is weak" misuses the pre-set label.** By DESIGN, "weak" needs 20 or more booked trades, so P6 is TOO FEW. Its own mean is
   not distinguishable from zero: t = 0.77 in R and 1.05 in $. The sign-flip p for mean > 0 is 0.23 in R and 0.15 in $.
   The bootstrap P(mean <= 0) is 0.21 in R. It is fragile: drop the best trade (10-08, +4.14R) and the mean falls to
   +0.10R. Drop the best two and the R total is -1.8R (the $ total is still +$98). Ungated, all 19 resolved candidates
   average +0.07R.
2. **"Absorption separates winners from losers in both halves" rests on 4 non-absorbed trades**: 3 in the older half
   (10-05, 10-21, 10-28) and **1 in the newer half (11-12)**. The newer-half gap of +1.22R (P6) and +1.12R (P3) is one
   trade. The placebo (p 0.079) tests only the gate, comparing 15 absorbed against 4 non-absorbed. It does not test whether
   P6 makes money.
3. **The trades/week and $/month figures are understated (this direction is conservative).** "51/5 weeks" counts 7 Sunday
   files that cannot trade. With 44 trading days (8.8 weeks), P6 makes 1.70 trades a week, not 1.47. The 51 days span
   2.0 calendar months, not "~2.4", so P6 makes about $298/month at 1 micro, or about $1,450/month at $500 risk.
4. Holm runs over 5 p-values, not 6 (P4 has none). Over 6, P6's Holm p would be 0.40 instead of 0.32. The verdict is the same.
5. The LVN note "a 5m bar's delta is typically ~7% of its volume" is wrong. The median |delta|/volume over 3,396 RTH bars
   is **3.3%**, and only 6.7% of bars reach 10%. Among the 82 P4 candidates the median is 2.0% (max 11.3%), and only 4
   reach 5% with the trade. The conclusion (the gate is miscalibrated) is right, and the gap is bigger than stated.

## Corrected one-line verdict
NO YES-candidate. All 6 variants are TOO FEW. P6 is TOO FEW (not "weak"): 15 trades, +$595 at 1 micro, and it holds on 1m
bars. Its own edge is not significant (p ~0.2) and rests on 2 big winners. The gate's separation in the newer half is one
trade. Score it forward through oos.py only; do not change anything because of it.
