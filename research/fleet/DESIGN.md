# Fleet plan (lane E follow-up, 2026-11-22): pre-registered, committed before the scored run

Question (lead): with an eval budget of $150 / $300 / $500 a month, which mix of account types (and re-buy stop) gives the
owner the most payout $ in 6 months, and when does he reach $70,000 (the Corvette fund)? Paper only, nothing bought.

## Engine
research/plans/rank.py via research/onebook/book.py (real fills: ATLAS 10 ticks a side). One fleet = several account slots
stepped on the SAME market path (same bots, same days: bad weeks hit every account together). 1,000 paths x 252 sessions
(12 months, 5-session blocks, seed 23); 6-month numbers = the first 126 sessions; H1 / H2 / REF as rank.py.

## Start state = the owner's 4 MFFU accounts (sunk cost, no fee counted)
Zlarior Builder 50K eval (-$807, room $1,025; book B09 = LIT eval, LIT + ATLAS once funded, the approved card),
ATLAS Builder 25K funded (-$113, room $887, 0 payouts; ATLAS only), Rapid EOD 25K eval fresh (LIT + ATLAS),
Zlarior Builder 25K #2 eval fresh (LIT only). A dead / failed one is replaced from the fleet's buy list.

## Rules modelled (research/lit/mffu_rules.json, firm_rules.json)
MFFU caps: 5 sim-funded in all; Builder 50K 1, Builder 25K 2, Rapid EOD 3 per size. Policy: active MFFU evals + funded <= 5,
and per type evals + funded <= its cap. FundedNext Rapid Daily 50K ($149.99): at most 2 active; its 15th payout on the profile
= live review -> FundedNext stops (conservative). Lucid: OFF (red team running), not used.
Live trap: a Builder's 5th payout = live move -> every MFFU sim account and MFFU purchase suspended for the rest of the
horizon (live account valued $0: conservative; FundedNext keeps going). Rapid: live at a $10,000 net day (checked every day;
our sizing caps a day near $2,000, so expected never) - the Risk-team discretionary move cannot be modelled (top risk, stated).
Budget: B $ a month accrues at the start of each 21-session month, unused $ rolls over; payouts are NOT recycled into fees.

## Grid (pre-registered; 6 buy lists x 3 budgets x 2 re-buy stops x 2 Builder payout policies = 72 fleets)
Buy lists (new evals, first type that fits caps + budget, repeated while possible):
L0 today's types (Builder 50K, Builder 25K, Rapid EOD 25K) | L1 Rapid EOD 50K, then Rapid EOD 25K | L2 FundedNext 50K, then
Rapid EOD 50K | L3 Rapid EOD 50K and FundedNext 50K alternating | L4 Builder 50K, then Builder 25K | L5 Rapid EOD 25K only.
New-account books: Rapid EOD 50K = B11 (LIT x0.5 in the eval, onebook pick); every other type = B03 (LIT + ATLAS first-come).
Re-buy stop: S0 none (budget only) | S3 stop ALL new buys after 3 eval fails / dead accounts in a row with no payout between.
Builder payout policy: P5 take every payout (5th = live move) | P4 close a Builder after its 4th payout (no live move).
## Reported per fleet x span
6-month owner $, fees, net $, $/month, p10 (worst 10%) net, payouts, P(live move), Corvette $70,000 (cumulative owner $ -
fees): median months to reach, P(by 6 / 12 months).
## Pick rule
Per budget: the fleet with the highest H2 (Jul-Oct-like) 6-month net among fleets whose REF 6-month net is no worse than
the L0-S0-P4 fleet at that budget by more than one month's budget. Also shown: best H1, and the order of moves of the pick.
