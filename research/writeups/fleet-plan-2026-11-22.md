---
title: Fleet plan - which mix of prop accounts for a $150 / $300 / $500 a month eval budget, and when the $70,000 Corvette fund is reached; never take a Builder's 5th payout; Rapid EOD 50K + FundedNext 50K is the money; MFFU's Rapid Risk-team live move is the big unknown
family: money
date: 2026-11-22
status: done - paper only, nothing bought. No new Decide card from this file (the buys are already on cards plan-rapid50k-max2-rebuys / plan-fundednext50k-max2-rebuys); one new owner question for MFFU.
summary: Lane E follow-up. Pre-registered (research/fleet/DESIGN.md, edc8d1d07 + 82fa56b43 before the scored run). 72 fleets (6 buy lists x 3 budgets x 2 re-buy stops x 2 Builder payout policies) on rank.py's real-fills engine, every account of a fleet on the SAME market path, 1,000 paths x 24 months, starting from the owner's 4 MFFU accounts. Picks (best Jul-Oct-like 6-month net with 2021-25 no worse than today's types by more than a month's budget) - $150 = FundedNext 50K first, then Rapid EOD 50K - $26,747 / $34,221 / -$222 in 6 months (Jul-Oct / Jan-Jun / 2021-25-like), $70k in ~12.8 / 10.2 months; $300 and $500 = Rapid EOD 50K and FundedNext 50K alternating - $44,726 / $73,788 / -$784 ($300; worst 10% $13,954 / $27,165), $70k in ~8.4 / 5.8 months; $500 adds only +$3.9k / +$4.8k for twice the bad-market loss. Every pick closes a Builder after its 4th payout (taking the 5th = MFFU live move = every sim stops: 12-month net drops by half or more). Sensitivity (post-hoc) - if MFFU's Risk team moves a Rapid live once it has paid $7,000 (their own example), the $300 pick makes $27,500 / $28,484 and never reaches $70k on sim payouts; closing each Rapid at $6,500 paid keeps $35,320 / $44,768 and reaches $70k in ~12.3 / 9.1 months.
runs: research/fleet/fleet.py -> results.json; research/fleet/sens.py -> sens.json (labelled post-hoc)
---

## Headline

**Budget $300 a month (the sweet spot).** This week, buy ONE MFFU Rapid EOD 50K ($165). Run Zlarior + ATLAS on it, with LIT at
half size until its eval passes (the one-account book). Next month, buy a FundedNext Rapid Daily 50K (~$150). After that,
alternate the two whenever the budget and MFFU's caps allow. Close every Builder after its 4th payout: never request the 5th.
**6 months: +$44,726 (Jul-Oct-like) / +$73,788 (Jan-Jun-like) / -$784 (2021-25-like).** Worst 10% of runs: +$13,954 / +$27,165 /
-$1,740. **$70,000 Corvette fund: about 8.4 months (Jul-Oct-like) or 5.8 months (Jan-Jun-like). The chance of reaching it
within 12 months is 84% / 99%. In a 2021-25-like market it is never reached.**

**The catch: MFFU's Risk team can move a Rapid to live at its own discretion.** Their own example is approval at $7,000 total
profit. Every MFFU sim account then stops. If that happens at $7,000, the same plan makes $27,500 / $28,484 in 6 months and
does not reach $70k from sim payouts alone (the live account is valued at $0 here; it is really worth something, plus up to
$5,000 Reserve). One question to MFFU settles which world we are in (Next, step 2).

## For the owner (one minute)

| Eval budget a month | What to buy (in order) | 6 months, Jul-Oct-like / Jan-Jun-like / 2021-25-like | Worst 10% (Jul-Oct-like) | $70k Corvette (median), Jul-Oct / Jan-Jun-like |
|---|---|---|---|---|
| Today's types only (Builder 50K / 25K, Rapid 25K), $150 | re-buy what dies | $19,514 / $32,602 / -$506 | $5,671 | 16.0 / 10.7 months |
| **$150** | FundedNext 50K first, then Rapid EOD 50K | **$26,747 / $34,221 / -$222** | $11,056 | **12.8 / 10.2 months** |
| **$300** | Rapid EOD 50K this week, then FundedNext 50K, alternate | **$44,726 / $73,788 / -$784** | $13,954 | **8.4 / 5.8 months** |
| $500 | same as $300 (3 buys in week 1) | $48,589 / $78,621 / -$1,483 | $18,594 | 8.2 / 5.5 months |
| If MFFU moves a Rapid live at $7,000 ($300 plan) | same | $27,500 / $28,484 / -$839 | $13,146 | not reached from sim payouts |
| Defensive: close each Rapid at $6,500 paid ($300 plan) | same | $35,320 / $44,768 / -$825 | $13,670 | 12.3 / 9.1 months |

In plain words:
- **Never take a Builder's 5th payout.** MFFU moves you to live on it and every sim account stops. Taking it ends the run in
  85-99% of 12-month runs. It cuts 12-month money by about half or more: $111,275 -> $59,472 on the $300 plan and
  $49,301 -> $19,578 on today's types (Jul-Oct-like). Take
  payouts 1-4 on Zlarior's 50K, ATLAS's 25K and the 25K #2, then close that account and buy the next one from the list.
- **The money is Rapid EOD 50K + FundedNext 50K.** Both have daily payouts and a high split. More Builders (L4) make the least
  ($14,274 Jul-Oct-like) and almost never reach $70k inside a year.
- **$300 a month is the sweet spot.** $500 adds about $3,900 in a Jul-Oct-like market, but doubles the loss in a 2021-25-like
  one (-$1,483 vs -$784). Below $300 the first buys wait for budget.
- **A bad market costs little.** In 2021-25-like markets every plan loses roughly its fees (-$222 to -$1,483 over 6 months).
  "Stop all buying after 3 dead accounts in a row" cuts that to about $0, for about $4,000 less in a Jul-Oct-like market
  (row S3 below). That is cheap insurance if you would rather not lose at all.
- **It is a 2026 bet** (same bots on every account: a bad week hits them all together).

Next:
1. **This week:** decide the open card plan-rapid50k-max2-rebuys (buy one Rapid EOD 50K). The fleet plan says yes at a $300 budget.
2. **Ask MFFU support (hands-only, 2 minutes):** "At what total profit does the Risk Management Team review a Rapid EOD account
   for the live move, and does the Reserve get paid out?" If the answer is near $7,000, close each Rapid at about $6,500 paid
   (defensive row). If not, let them run.
3. **Next month:** decide plan-fundednext50k-max2-rebuys (the second firm), then alternate the two. Re-check with
   `python -X utf8 research/fleet/fleet.py`.

## Order of moves ($300 plan)

| When | Move | Why |
|---|---|---|
| This week | Buy 1 Rapid EOD 50K ($165), LIT x0.5 in the eval + ATLAS $500 lane | MFFU is then at 5 accounts (the 5 sim-funded cap), so no more MFFU buys until one closes |
| Month 2 | Buy 1 FundedNext Rapid Daily 50K (~$150) when the budget has it | Second firm: an MFFU live move does not stop it; max 2 active |
| Each payout, Builders (Zlarior 50K, ATLAS 25K, 25K #2) | Take payouts 1, 2, 3, 4. Then close the account, never request #5 | The 5th Builder payout = live move = every MFFU sim stops |
| Each payout, Rapid EOD | Daily, above the buffer + the bot's $1,000 keep | Until MFFU answers the Risk-team question (step 2) |
| Each payout, FundedNext | All 5 (max $1,200 each), then the account ends -> buy the next from the list | Its 15th payout on the profile = live review: stop after 14 |
| When an account dies or closes | Buy the next type in the alternation, if budget + caps allow | Average 6-month buys (Jul-Oct-like): 3.3 Rapid 50K + 4.8 FundedNext, ~$1,259 in fees |


## 1. What was tested (design committed before the scored run: research/fleet/DESIGN.md)

- **Engine:** research/plans/rank.py, through research/onebook/book.py. Real fills: ATLAS at 10 ticks a side. Each plan uses its
  own eval and payout rules. Every account of a fleet trades the SAME market path, because the same bots trade on the same
  days. 1,000 paths x 504 sessions (24 months; months 7-24 mean "if the market stays like this"). Spans as always: H1 = 2026
  Jan-Jun, H2 = Jul-Oct, REF = 2021-25.
- **Start state:** the owner's 4 MFFU accounts, as sunk cost:
  - Zlarior Builder 50K eval at -$807 with $1,025 room (book B09: LIT eval, LIT + ATLAS once funded)
  - ATLAS Builder 25K funded at -$113 with $887 room
  - Rapid EOD 25K eval, fresh (LIT + ATLAS)
  - Builder 25K #2 eval, fresh (LIT only)
- **Caps:** MFFU 5 sim-funded in all (evals + funded <= 5 here); Builder 50K 1, Builder 25K 2, Rapid EOD 3 per size.
  FundedNext: at most 2 active, and it stops at its 15th profile payout (live review). Lucid: off (red team running).
- **Live trap:** a Builder's 5th payout, or a $10,000 Rapid day (never happens at our sizing), moves the owner to live. Every
  MFFU sim and every MFFU purchase then stops for the rest of the run. The live account is valued at $0 (conservative).
  FundedNext keeps running.
- **Budget:** $B is added at the start of each 21-session month, unused money rolls over, and payouts are not recycled into fees.
- **Grid (72 fleets):**
  - Buy lists: L0 today's types, L1 Rapid 50K then Rapid 25K, L2 FundedNext then Rapid 50K, L3 Rapid 50K / FundedNext
    alternating, L4 Builder 50K then Builder 25K, L5 Rapid 25K only.
  - Re-buy stop: S0 none, or S3 = stop all buying after 3 dead / failed accounts in a row.
  - Builders: P5 take the 5th payout, or P4 close after the 4th.
- **Pick rule:** per budget, the highest H2 6-month net among fleets whose REF 6-month net is no worse than "today's types,
  S0, P4" minus one month's budget. Picks: $150 L2-S0-P4, $300 L3-S0-P4, $500 L3-S0-P4. The best H1 is the same fleet at
  $300 / $500; at $150 it is L1.

## 2. Every fleet with Builders closed after payout 4 (P4); 6-month net after fees

| Budget | Buy list | Re-buy stop | 6-month net $ Jan-Jun-like / Jul-Oct-like / 2021-25-like | worst 10% (6 mo) H1 / H2 / REF | $70k reached (median months) H1 / H2 | $70k within 12 months H1 / H2 |
|---|---|---|---|---|---|---|
| $150 | L0 today's types (B50, B25, R25) | S0 | $32,602 / $19,514 / $-506 | $9,386 / $5,671 / $-882 | 10.7 / 16.0 | 65.7% / 12.6% |
| $150 | L0 today's types (B50, B25, R25) | S3 | $31,800 / $18,677 / $27 | $6,533 / $3,810 / $-281 | 11.1 / - | 57.0% / 11.7% |
| $150 | L1 Rapid EOD 50K, then Rapid 25K | S0 | $43,430 / $23,076 / $-426 | $12,770 / $5,277 / $-854 | 7.9 / 11.2 | 95.2% / 61.1% |
| $150 | L1 Rapid EOD 50K, then Rapid 25K | S3 | $41,927 / $21,850 / $11 | $10,504 / $4,362 / $-427 | 8.1 / 12.7 | 81.2% / 45.5% |
| $150 | L2 FundedNext 50K, then Rapid EOD 50K | S0 | $34,221 / $26,747 / $-222 | $14,293 / $11,056 / $-900 | 10.2 / 12.8 | 73.0% / 41.4% |
| $150 | L2 FundedNext 50K, then Rapid EOD 50K | S3 | $32,547 / $25,210 / $25 | $9,347 / $5,587 / $-300 | 10.4 / 14.7 | 61.1% / 35.8% |
| $150 | L3 Rapid EOD 50K + FundedNext 50K alternating | S0 | $34,209 / $26,648 / $-222 | $14,293 / $10,980 / $-900 | 10.1 / 12.7 | 73.7% / 42.6% |
| $150 | L3 Rapid EOD 50K + FundedNext 50K alternating | S3 | $32,556 / $25,134 / $25 | $9,347 / $5,587 / $-300 | 10.3 / 14.5 | 61.5% / 36.6% |
| $150 | L4 Builder 50K, then Builder 25K | S0 | $20,705 / $14,272 / $-458 | $6,432 / $4,948 / $-900 | 21.7 / - | 14.2% / 0.2% |
| $150 | L4 Builder 50K, then Builder 25K | S3 | $20,427 / $14,013 / $76 | $5,600 / $3,994 / $-155 | - / - | 14.2% / 0.2% |
| $150 | L5 Rapid EOD 25K only | S0 | $32,957 / $17,977 / $-471 | $9,011 / $3,611 / $-875 | 10.2 / 18.3 | 68.5% / 7.9% |
| $150 | L5 Rapid EOD 25K only | S3 | $32,358 / $17,457 / $43 | $7,002 / $2,628 / $-194 | 10.6 / - | 58.2% / 7.7% |
| $300 | L0 today's types (B50, B25, R25) | S0 | $32,743 / $19,579 / $-1,048 | $9,658 / $5,757 / $-1,793 | 10.6 / 16.0 | 65.8% / 12.7% |
| $300 | L0 today's types (B50, B25, R25) | S3 | $31,844 / $18,755 / $7 | $7,513 / $3,811 / $-281 | 11.2 / - | 56.7% / 11.7% |
| $300 | L1 Rapid EOD 50K, then Rapid 25K | S0 | $58,976 / $30,632 / $-1,036 | $21,426 / $6,524 / $-1,777 | 6.8 / 10.0 | 97.9% / 71.9% |
| $300 | L1 Rapid EOD 50K, then Rapid 25K | S3 | $57,676 / $29,604 / $-81 | $18,519 / $5,667 / $-495 | 7.0 / 10.8 | 89.1% / 58.1% |
| $300 | L2 FundedNext 50K, then Rapid EOD 50K | S0 | $63,385 / $41,677 / $-669 | $25,051 / $14,973 / $-1,800 | 6.4 / 9.0 | 97.8% / 80.2% |
| $300 | L2 FundedNext 50K, then Rapid EOD 50K | S3 | $56,396 / $36,594 / $-7 | $12,296 / $5,855 / $-600 | 7.0 / 11.2 | 71.9% / 52.9% |
| $300 | L3 Rapid EOD 50K + FundedNext 50K alternating | S0 | $73,788 / $44,726 / $-784 | $27,165 / $13,954 / $-1,740 | 5.8 / 8.4 | 98.7% / 83.9% |
| $300 | L3 Rapid EOD 50K + FundedNext 50K alternating | S3 | $67,374 / $40,742 / $-47 | $15,269 / $6,201 / $-480 | 6.0 / 9.8 | 77.5% / 57.7% |
| $300 | L4 Builder 50K, then Builder 25K | S0 | $20,701 / $14,274 / $-644 | $6,464 / $4,948 / $-1,456 | 21.7 / - | 14.2% / 0.2% |
| $300 | L4 Builder 50K, then Builder 25K | S3 | $20,416 / $14,015 / $73 | $5,577 / $3,994 / $-155 | - / - | 14.2% / 0.2% |
| $300 | L5 Rapid EOD 25K only | S0 | $33,154 / $18,045 / $-603 | $9,011 / $3,699 / $-1,264 | 10.2 / 18.3 | 68.7% / 8.0% |
| $300 | L5 Rapid EOD 25K only | S3 | $32,468 / $17,488 / $31 | $6,958 / $2,672 / $-194 | 10.6 / - | 58.3% / 7.8% |
| $500 | L0 today's types (B50, B25, R25) | S0 | $32,739 / $19,579 / $-1,160 | $9,658 / $5,757 / $-2,206 | 10.6 / 16.0 | 65.8% / 12.7% |
| $500 | L0 today's types (B50, B25, R25) | S3 | $31,844 / $18,755 / $7 | $7,513 / $3,811 / $-281 | 11.2 / - | 56.7% / 11.7% |
| $500 | L1 Rapid EOD 50K, then Rapid 25K | S0 | $60,784 / $31,359 / $-1,518 | $22,052 / $7,089 / $-2,961 | 6.7 / 9.9 | 97.9% / 73.3% |
| $500 | L1 Rapid EOD 50K, then Rapid 25K | S3 | $59,251 / $30,308 / $-91 | $18,133 / $5,997 / $-495 | 6.9 / 10.6 | 89.4% / 58.5% |
| $500 | L2 FundedNext 50K, then Rapid EOD 50K | S0 | $78,550 / $48,576 / $-1,467 | $35,557 / $18,540 / $-2,970 | 5.5 / 8.2 | 98.9% / 85.3% |
| $500 | L2 FundedNext 50K, then Rapid EOD 50K | S3 | $67,387 / $41,745 / $-142 | $16,994 / $10,156 / $-765 | 6.1 / 9.9 | 78.4% / 58.0% |
| $500 | L3 Rapid EOD 50K + FundedNext 50K alternating | S0 | $78,621 / $48,589 / $-1,483 | $35,446 / $18,594 / $-2,985 | 5.5 / 8.2 | 98.9% / 85.3% |
| $500 | L3 Rapid EOD 50K + FundedNext 50K alternating | S3 | $67,387 / $41,745 / $-142 | $16,994 / $10,156 / $-765 | 6.1 / 9.9 | 78.4% / 58.0% |
| $500 | L4 Builder 50K, then Builder 25K | S0 | $20,701 / $14,274 / $-643 | $6,464 / $4,948 / $-1,456 | 21.7 / - | 14.2% / 0.2% |
| $500 | L4 Builder 50K, then Builder 25K | S3 | $20,416 / $14,015 / $73 | $5,577 / $3,994 / $-155 | - / - | 14.2% / 0.2% |
| $500 | L5 Rapid EOD 25K only | S0 | $33,154 / $18,045 / $-607 | $9,011 / $3,699 / $-1,264 | 10.2 / 18.3 | 68.7% / 8.0% |
| $500 | L5 Rapid EOD 25K only | S3 | $32,468 / $17,488 / $31 | $6,958 / $2,672 / $-194 | 10.6 / - | 58.3% / 7.8% |

## 3. The live trap: taking the Builder's 5th payout (P5) vs closing after the 4th (P4), 12 months

| Budget | Buy list (S0) | Builder 5th payout TAKEN (P5): 12-month net H1 / H2, live move by month 12 | Builder CLOSED after payout 4 (P4): 12-month net H1 / H2 |
|---|---|---|---|
| $150 | L0 today's types (B50, B25, R25) | $29,968 / $19,578, 99.4% / 98.7% | $81,491 / $49,301 |
| $150 | L3 Rapid EOD 50K + FundedNext 50K alternating | $41,100 / $37,054, 92.8% / 85.4% | $110,905 / $68,712 |
| $150 | L4 Builder 50K, then Builder 25K | $19,385 / $14,776, 99.5% / 98.9% | $45,661 / $32,663 |
| $300 | L0 today's types (B50, B25, R25) | $29,972 / $19,539, 99.5% / 98.9% | $81,673 / $49,347 |
| $300 | L3 Rapid EOD 50K + FundedNext 50K alternating | $82,054 / $59,472, 92.8% / 85.4% | $201,992 / $111,275 |
| $300 | L4 Builder 50K, then Builder 25K | $19,390 / $14,775, 99.5% / 98.9% | $45,661 / $32,661 |
| $500 | L0 today's types (B50, B25, R25) | $29,982 / $19,539, 99.5% / 98.9% | $81,672 / $49,347 |
| $500 | L3 Rapid EOD 50K + FundedNext 50K alternating | $84,344 / $60,884, 92.8% / 85.4% | $205,180 / $112,968 |
| $500 | L4 Builder 50K, then Builder 25K | $19,390 / $14,775, 99.5% / 98.9% | $45,661 / $32,661 |

## 4. Sensitivity (labelled post-hoc, research/fleet/sens.json): MFFU's Risk team moving a Rapid live

| Fleet (S0, P4) | No move (model) 6 mo H2 / H1 / REF; $70k median H2 / H1 | Risk team moves at $7,000 paid: 6 mo H2 / H1; live by month 6 | Close each Rapid at $6,500 paid: 6 mo H2 / H1; $70k median H2 / H1 |
|---|---|---|---|
| $150 L2 FundedNext, then Rapid 50K | $26,747 / $34,221 / -$222; 12.8 / 10.2 mo | $25,175 / $26,468; 37 / 70% | $25,592 / $28,301; 17.4 / 14.4 mo |
| $300 L3 alternating | $44,726 / $73,788 / -$784; 8.4 / 5.8 mo | $27,500 / $28,484; 78 / 94% | $35,320 / $44,768; 12.3 / 9.1 mo |
| $300 L2 FundedNext, then Rapid 50K | $41,677 / $63,385 / -$669; 9.0 / 6.4 mo | $30,721 / $31,397; 67 / 87% | $35,311 / $42,954; 13.0 / 9.7 mo |
| $300 L1 Rapid 50K, then Rapid 25K | $30,632 / $58,976 / -$1,036; 10.0 / 6.8 mo | $13,044 / $12,628; 79 / 94% | $21,490 / $31,581; 14.9 / 10.6 mo |
| $500 L3 alternating | $48,589 / $78,621 / -$1,483; 8.2 / 5.5 mo | $30,705 / $31,387; 79 / 94% | $39,073 / $50,119; 12.0 / 8.5 mo |

Reading:
- With a $7,000 Risk-team move, the FundedNext-heavy plans hold up best. The second firm keeps paying after MFFU goes live.
  The all-MFFU Rapid plan (L1) falls to about $13k.
- Closing each Rapid at $6,500 paid is the middle road. It costs $9-29k if MFFU never moves you, and gains $8-16k if it moves
  you at $7,000.
- Which world we are in is one question to MFFU support (Next, step 2).

## 5. Limits (honest)

- The live account is valued at $0 in every row. A real live account keeps trading and the Reserve (up to $5,000) may be paid,
  so every "live move" row is a floor.
- The start state is approximate: today's balances are from the owner's typed numbers (Nov 17-19), and the session counts are
  guesses. The PC has not reported since then.
- The FundedNext price ($149.99, RAPID code) and Rapid EOD 50K price ($165 CLUB) are not owner purchases yet.
- Months 7-24 repeat the same market span (bootstrap). The Corvette dates past month 6 assume the market stays like that half.
- Same bots on every account: a bad stretch hits all accounts on the same days. That is modelled (one shared path), but no
  plan protects against a 2021-25-like market except spending less (S3, or a smaller budget).
- 72 fleets + 15 sensitivity rows were tried. The picks follow the rule written before the run.
