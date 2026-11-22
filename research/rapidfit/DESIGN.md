# Rapid 25K slot (2026-11-22): pre-registered design, committed BEFORE any run

Question (lead): the Rapid 25K's LIT lane sits out 58-64% of signals (the $427 best-day guard). Best legal use of the slot?

## Already tested (not re-invented)
- (a) LIT off = ATLAS only: rapid25-lit-lane-2026-11-18 rule (d) "clearly worse"; rapid25_launch R2 at real fills $707 / $141 a month vs
  both lanes $1,883 / $800.
- (b) LIT at 1 micro, bank at the day's room: rapid25-lit-lane rule (b) (small win at 1-tick fills), rapid25_launch R4 at real fills
  +$24 / +$101 a month but 60-session eval fail 0.5 -> 3.1% Jan-Jun -> card rapid25-lit-bank recommend NO. (b+) full size + bank:
  worse (eval fail 3.8 / 4.0%). (c') 1 micro letting the day break 30%: worse.
- (d) a Rapid EOD 50K in the slot: research/writeups/plan-ranking-2026-11-22.md (one slot, 6 months).
## This run (one engine, real fills, same paths)
research/plans/rank.py (LIT + ATLAS on one account, ATLAS at 10 ticks a side, each plan's own eval + payout rules, re-buy on
fail / death, 1,000 week-block paths, 126 sessions, seed 23; it reproduces rapid25_launch R3 exactly): (a) Rapid 25K ATLAS only,
(c) Rapid 25K LIT + ATLAS (today), (d) Rapid EOD 50K LIT + ATLAS ($165). (b) is quoted from rapid25_launch R4 (same engine family).
Reported: 6-month net $ per slot, $ a month, eval pass % / median sessions, first payout median, funded lost %, no-payout %, and a
fixed-size view of the lane's trades (trades a week, PF, net $, max DD at $250 a trade on the 25K / $500 on the 50K).
## Decision rule (fixed)
A candidate replaces (c) only if its 6-month net $ beats (c) in BOTH 2026 halves, its 2021-25 loss is not worse by more than its
price, and its first-eval 60-session fail % is not higher by > 1 point. ONE Decide card for a winner, unless an open card already asks
the same question (then: no new card, say which card).
