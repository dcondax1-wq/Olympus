# Fleet v2 (2026-11-22): add LucidPro 50K accounts to the $300 fleet. Pre-registered, committed BEFORE the scored run

Question (owner): the lever is not a new edge, it is the SAME proven bots on MORE accounts at MORE firms. How much more $/month and
how much sooner is the $70,000 Corvette fund if 0 / 1 / 2 / 3 / 5 LucidPro 50K accounts are added to the $300 plan
(Rapid EOD 50K + FundedNext 50K alternating)? Paper only: nothing bought, no live file touched.

## Engine (unchanged: extend, not rewrite)
research/fleet/fleet.py (v1) -> research/plans/rank.py via research/onebook/book.py, real fills. 1,000 paths x 504 sessions
(24 months, 5-session blocks, seed 23). Spans H1 = 2026 Jan-Jun, H2 = Jul-Oct, REF = 2021-25. Every account of a fleet steps the
SAME market path (same bots, same days). Start state = the owner's 4 MFFU accounts (sunk), exactly as v1. New code lives in
research/fleet/fleet2.py (imports fleet.py; adds account type "LU", failure logging, the correlation metrics). N=0 must
reproduce v1's L3 / S0 / P4 rows at $300 (check, reported).

## Lucid account type "LU" (research/lit/lucid_rules.json = firm_rules.json plan lucid_pro_50k, identical numbers)
LucidPro 50K, DLL on: eval target $3,000, EOD trailing MLL $2,000 locking at +$100, no eval consistency, no time limit; the bot's own
soft DLL clamp $1,000 (as rank.py); funded: DLL $1,200 (LucidScale), 40% best-day payout rule, $500 minimum, $2,000 then $2,500
max, buffer $52,100, 90% split, 40 micros. LIT ONLY (book B01; ATLAS is not wired on Lucid). Max payouts 5 (rank.py / firm_rules
cap; Lucid's page names none: UNVERIFIED, conservative). Household caps 10 evals / 5 funded: never binding (N <= 5).
Lucid is a third firm: an MFFU live move does not stop it. Lucid is never hit by the MFFU Builder-5th-payout trap.
Not modelled (stated): the live hedge guard (LIT and ATLAS can be opposite on different accounts in reality; the guard then skips
a trade: the sim ignores it = slightly generous); Lucid's written OK for the same bot at other firms; NinjaTrader support.
## UNVERIFIED price
LucidPro 50K price = ASSUMED $126.00 (rank.py PLANS; a code price; lucidtrading.com returns 403). Sensitivity: $76 and $176.
## Grid (pre-registered)
Total monthly budget B in {$300, $500, $800} (B is the WHOLE fleet's fees, Lucid included; unused rolls over; payouts not recycled).
N in {0, 1, 2, 3, 5} = the most Lucid accounts open at once (evals + funded; a dead/finished one is re-bought if budget allows).
Buy order: LU-first (Lucid up to N, then alternate Rapid EOD 50K / FundedNext 50K) | BASE-first (alternate R50 / FN as v1 L3, then Lucid).
Fleets: 3 budgets x (N=0 once + 4 N x 2 orders) = 27 main. Sensitivity (price $76 / $176): N in {1,2,3,5} x 3 budgets x 2 orders x 2
prices = 48. Total 75 fleets, every one reported. Policy P4 (Builder closed after 4th payout), re-buy stop S0, as the v1 pick.
## Metrics (per fleet x span)
6-month net $ (owner payouts - fees), $/month (net6/6 and net12/12), p10 of net6 and net12 (worst 10%), fees, payouts, median months
to $70k (cumulative payouts - fees) and P(within 12 months), 24-month net.
Correlation (honest): log every account failure (eval fail / stuck, funded lost) with its session. P(3+ accounts fail in the same
10 sessions = 2 weeks) in the first 6 and 24 months, for ALL accounts and for Lucid accounts only; also the worst number of
failures on one 10-session window and the mean over paths. "Same-day" = the max failures on one session.
Marginal $ per extra Lucid account = net6(N) - net6(N-1 step) over the step's accounts, per budget, per span; diminishing if falling.
2021-25-like: REF net6 and how much MORE it loses than N=0 at the same budget; bound check REF loss <= 2 x REF fees.
## Pick / decide-card rule (written now)
Compare every mix with the owner's $300 N=0 plan. A Decide card only if a mix has: H1 net6 > and H2 net6 > the $300 N=0 plan, AND REF loss
<= 2 x its total fees, AND still true at the +$50 Lucid price. Best mix per budget = highest H2 net6 among mixes meeting the REF bound
(2 x fees) AND H1 net6 >= the same budget's N=0. If more accounts do not help, the write-up shows why (fee ramp, caps, correlation)
and the next best lever in $. docs/TESTED_AND_REJECTED.md line only if something is rejected.
