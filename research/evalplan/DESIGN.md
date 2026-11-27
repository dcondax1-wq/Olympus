# Order flow on the evals + funded account: rollout sim (2026-11-27), pre-registered BEFORE the run

Question (lead, night-of-evalplan): if lane A (absorption level fade, engine/of_paper.py) traded on the owner's 4 MFFU accounts,
what happens to pass %, days to pass, fail %, $ in 6 months, and what is the downside if lane A's edge is really zero?
PAPER RESEARCH ONLY. Nothing here changes a bot, a size, a switch or an account.

## Inputs (fixed)
- Lane A trades: the 40 TAKEN rows of research/orderflow/real_verdict.json (51 real tick days 2026-09-27..11-26, quote-rule sides).
  Stop in points = |usd_1 / R| / 2 (1 micro = $2/pt; usd_1 is after costs, so the stop is slightly over-stated = conservative).
- Trade rate: 40 trades / the number of distinct days that had any lane-A candidate (one lane-A trade a day at most, as the bot).
- Outcome model (the bot's one target): +2R at the target or -1R at the stop. Scenario = the win rate:
  REAL p = 0.50 (as measured, +0.5R); Q25 = 25% of the measured edge (+0.12R, p 0.375); ZERO = no edge (0R, p 1/3);
  BAD = the skipped group's win rate (p 0.24, -0.28R). Worst open loss of a winner: -0.5R.
- Engines: research/alloc/alloc.py (= research/onebook/book.py on research/plans/rank.py: the live LIT two_week sizing,
  ATLAS at its real fills, the MFFU rules, re-buy on a fail), today's state of each account and today's book (alloc ACCTS).
- Lane A sizing (an added lane, stack_q): $ a trade = min(lane $, 30% of the room, the soft daily loss left).
  SMALL = $100 (25K) / $200 (50K); FULL = ATLAS-size $250 / $500. Stop over the lane $ = no trade (big stops get skipped).
- Placement: after the account's own LIT / ATLAS trades of the session (one position at a time). Sensitivity: OF only on days
  the account's own lanes did not trade (the strictest hedge guard).
- Paths: 1,000 a market, 5-session week blocks: H1 = 2026 Jan-Jun-like, H2 = Jul-Oct-like, REF = 2021-25-like; the OF trade is
  drawn independently of the market path (we only have Sep-Nov 2026 ticks: an honest limit).
## Reported per account x lane setting x scenario x market
eval: pass % within 60 sessions from today, median sessions to pass, fail %; 6 months from today: net $ (payouts after split -
re-buys), $/month, p10, chance of losing the funded account.
## Rule (fixed before the run)
A lane-A setting is "worth a forward plan" on an account only if REAL and Q25 both beat no-OF in H1 AND H2 net $, and ZERO
costs at most one eval price over 6 months in H2. Even then nothing goes live: the gate ladder (Sim101 forward n >= 20) comes first.
