# Pre-registration: Nov 16-19 (4 of 12 won) - noise or the edge dying? (written 2026-11-20 ~11:45 UTC, before the refreshed data is read)

Committed before `noise.py` runs on the refreshed tape (research/kalshi_k8_day/data/tape.jsonl, Aug 3 - Nov 20, public Kalshi
trades, fetched today at 1 request a second). The numbers below are fixed now; nothing is changed after seeing the result.

## Data
- The 3 live legs only: gold DOWN 05:15 ET, gold UP 16:45 ET, silver UP 16:45 ET (engine/kalshi_clock LEGS, its own calendar).
- A bet = the leg-day, priced by walking the public takers of our side from +20 s with $2.50 (research/kalshi_k8_monday/k8m_data
  walk_from rules: whole contracts, under half the wanted contracts by 45 s = no bet). Won = Kalshi's result equals our side.
  Fees: verify.py exact. Break-even win rate of a bet = its price + fee per contract.
- Baseline = Aug 3 - Nov 13 (before the bad stretch). The stretch = Nov 16-19 (12 bets). Nov 20 morning = the first bet after it,
  reported, not tested.

## Tests (one-sided, alpha 0.05 each; 3 tests -> also read at Bonferroni 0.0167)
1. **Block bootstrap (primary).** How often did the baseline produce a 4-weekday stretch with 4 or fewer wins of its bets?
   (a) every run of 4 consecutive trading days in the baseline (the real order, correlation kept), and (b) 100,000 draws of 4
   random baseline days, each day's 3 bets kept together (gold and silver at 16:45 win or lose together). p = share <= 4 of 12.
2. **Trend in the win rate.** Weekly win rate (Mon-Fri weeks, Aug 3 - Nov 20) regressed on the week number, weighted by bets;
   one-sided p for a falling slope from a permutation test (20,000 shuffles of the weeks).
3. **Price creep.** The same for the weekly average price paid at +20 s (a rising price = others copying the clock); one-sided p
   for a rising slope, permutation as in 2.

## Plain verdict, fixed now
- **Noise (keep the plan)**: test 1 p >= 0.05 (a stretch this bad happens at least 1 time in 20 in the good months) and neither
  2 nor 3 significant.
- **Warning (go live at $2.50 as planned, the stops guard it; check again after 20 live bets)**: test 1 p < 0.05, or one of 2 / 3
  p < 0.05, but not both a falling win rate and a rising price.
- **Edge dying (do NOT go live Monday; paper only, ask the owner)**: test 1 p < 0.0167 AND (2 or 3 p < 0.0167).
- Also reported (no decision): the chance the true win rate of the last 60 bets is under the break-even (Beta(1,1) posterior),
  and the 4-week and Aug-Nov records in $ at $2.50.
