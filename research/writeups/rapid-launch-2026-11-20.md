---
title: Rapid EOD 25K launch check - MFFU rules vs the code, what it trades at real fills, sizing vs the $500 DLL, payout path
family: risk
date: 2026-11-20
status: finding - no live change. Rules match MFFU (0 gaps that cost money). Keep LIT + ATLAS $250 as built (atlas-on-rapid stays YES). rapid25-lit-bank flips YES -> NO at real fills (eval fail 0.5 -> 3.1% Jan-Jun-like, over the pre-set 1-point limit). New optional card: size ATLAS's Rapid lane on a 10-tick stop (fewer accounts lost, -$31 to -$141 a month); patch in the lead's wires.
summary: MFFU's help center (read 2026-11-20) = the code for the Rapid EOD 25K with DLL - $1,500 target, $1,000 EOD trailing floor locking at +$100, DLL $500 = a soft pause (resets 6 PM ET; the bot's day also starts 18:00 ET), 2 minis / 20 micros, 30% best day in the eval only, 4 days, Tier-1 news banned funded only (-2/+2 min; bot -3/+2.5), daily payouts above $1,100, $250 since the last, $500 minimum, 90%, 7-day inactivity. At ATLAS's real fills (10 ticks a side), LIT + ATLAS makes $1,883 / $800 a month (Jan-Jun / Jul-Oct-like; -$50 2021-25-like) vs LIT alone $221 / $191 and ATLAS alone $707 / $141. Eval passes in 80-86% of runs within 60 trading days, median 33 / 26 days; first payout median Feb 10 / Feb 18 2027 (middle half Jan 20-Mar 16 / Jan 22-Apr 13); 12% / 26% of runs lose the first Rapid before any payout; 6 months pays $11,428 / $4,945 before fees. A full ATLAS stop at real fills overshoots its sized $ by up to ~36% (tight stops, many micros): days under -$500 1.1 per 100 traded days Jan-Jun-like -> MFFU's soft pause (never a fail). Sizing on a 10-tick stop makes that 0 and cuts the funded loss 27.2 -> 24.0% / 38.0 -> 34.5% for -$141 / -$31 a month.
runs: tools/money/rapid25_launch.py run / sizing -> research/lab/rapid25_launch.json; design research/second/rapid25_launch_design.md (committed 4139ee46 before any run); tests/test_rapid_launch.py
---

# Rapid EOD 25K launch check (2026-11-20)

## For the owner (one minute)

**Add the Rapid today as built: Zlarior (LIT) + ATLAS $250 on it. Rules all match MFFU. Expect the eval to pass in about
5-7 weeks and the first payout around mid-February.**

| What | Jan-Jun-like | Jul-Oct-like | 2021-25-like |
|---|---:|---:|---:|
| $ a month to you, LIT + ATLAS (as built) | $1,883 | $800 | -$50 |
| LIT alone / ATLAS alone | $221 / $707 | $191 / $141 | -$22 / -$47 |
| Eval passes within 60 trading days (median days) | 80.5% (33) | 85.5% (26) | 7.5% |
| First payout (middle half of runs) | Feb 10 (Jan 20-Mar 16) | Feb 18 (Jan 22-Apr 13) | none |
| Lose the first Rapid before any payout | 11.7% | 25.7% | 97.8% |
| Paid to you in 6 months (before the $97.20 fees) | $11,428 | $4,945 | $68 |

All at ATLAS's real fills (10 ticks a side). $ after MFFU's 90% and every re-buy, before the 30% tax pot.

## 1. Rules: MFFU today vs the code

Read 2026-11-20: help.myfundedfutures.com articles 16727601 (Rapid EOD 25K), 18337038 (Rapid EOD with DLL), 8230009 (news
policy), myfundedfutures.com/plans/rapid-eod.

| Rule | MFFU (DLL version) | Code | Match |
|---|---|---|---|
| Price | $97 shown ($162 list) | $97.20 (owner's price) | yes |
| Target | $1,500 | preset target 1500 | yes |
| Max loss | $1,000 EOD trailing, locks at start + $100 | mll 1000, trail eod, lock 100 / 25,100 | yes |
| Daily loss | $500, soft pause for the session, eval + funded, resets 6 PM ET | rules dll 500 (bot's own day stop), mffu_dll 500; trading_day rolls at 18:00 ET | yes |
| Max size | 2 minis / 20 micros | max_micros 20 | yes |
| Consistency | 30% best day, eval only | best_day 0.3 eval, bot keeps a day <= $427 | yes |
| Min days | 4 | min_days 4 | yes |
| News | Tier-1 banned on sim funded only, no position / order 2 min before + after | news_ban funded, bot flat 3 min before, back 2.5 min after | yes (safer) |
| Flat by | before the daily session close (no clock time stated) | flat 16:10 ET, no entry in the last 15 min on half days | yes (safer) |
| Payouts | daily; $1,100 buffer first; then $250 net since the last; $500 min; 90%; no cap | buffer 1100, since 250, PAY_MIN 500, SPLIT 0.9, keep $500 extra | yes |
| Inactivity | 7 days (eval + funded) | push from day 5 (account_b, both lanes count) | yes |

No gap that costs money. The night-rapidready audit (2026-11-19) said "no DLL": that was the non-DLL version's page; the
owner's version has the $500 DLL, already recorded the same day (engine/rapid.PLANS mffu_dll).

## 2. What it trades (pre-registered rows, 1,000 paths, 10 ticks a side)

| Row | H1 $/mo | H2 $/mo | REF $/mo | Eval pass (median) H1 / H2 | Eval fail 60 d H1 / H2 | Funded lost 6 m H1 / H2 |
|---|---:|---:|---:|---|---|---|
| R1 LIT only | 221 | 191 | -22 | 25.4% (42) / 42.1% (42) | 0.0 / 0.0% | 5.6 / 14.1% |
| R2 ATLAS only $250 | 707 | 141 | -47 | 48.5% (42) / 64.2% (34) | 0.8 / 0.7% | 4.3 / 8.6% |
| R3 LIT + ATLAS (as built) | 1,883 | 800 | -50 | 80.5% (33) / 85.5% (26) | 0.5 / 2.0% | 27.2 / 38.0% |
| R4 R3 + LIT bank lane | 1,907 | 901 | -49 | 79.3% (29.5) / 92.0% (21) | 3.1 / 2.7% | 28.7 / 39.1% |

At 1 tick (backtest) R3 = $2,322 / $1,016 / -$12; R4 = $2,323 / $1,105 / -$5. R3 at 10 ticks equals tools/atlas_risk.py's
base row exactly (same engine, same paths).

Decisions by the design's rules:
- **atlas-on-rapid: YES** (R3 > R1 in $ and has fewer no-payout runs in both halves: 7.4 / 15.1% vs 55 / 50%).
- **rapid25-lit-bank: NO** (was yes at 1 tick). It adds $24 / $101 a month and passes ~4-5 days sooner, but the eval fails
  0.5 -> 3.1% in a Jan-Jun-like market (limit +1 point). Built OFF, stays OFF.
- **ATLAS only: no card** (below R3 in every market).

Why the funded loss with ATLAS is high (27-38%): with ATLAS far more runs get funded at all; a funded loss = a $97.20
re-buy, already in the $.

## 3. Sizing vs the DLL and the EOD floor

- LIT lane: live two_week sizing (room_f 0.4: risk <= 40% of the room, $400 at the start), then a full stop + 2 ticks must fit
  the day's $500 left (multi_account.qty_for), max 20 micros, and the 30% guard (a winner keeps the day <= $427).
- ATLAS lane: $ = min($250, 30% of the room, $500 + today's closed loss) / one full stop of 1 micro ((stop + 1 tick) x $2 +
  $1.90). Examples: 10-pt stop = 11 micros ($246 sized); after LIT lost $400 = 4 micros ($90).
- One position at a time on the account, so the worst sized day is -$500 and the worst sized trade is 40% of the room: one day
  can never reach the EOD floor while the room is over $500, and shrinks with the room after that.
- At real fills the sizing assumes 1 tick but ATLAS pays ~10: a full stop costs up to ~36% more on a tight stop (5-pt stop,
  20 micros: $248 sized, $338 real). Sim: 1.1 days per 100 under -$500 (Jan-Jun-like), 0 Jul-Oct-like. MFFU's DLL is a soft
  pause, so this never fails the account; it only ends a day the bot was ending anyway.
- Conditional row (design: > 1 per 100 -> test it): ATLAS sized on a 10-tick stop: $1,742 / $769 / -$46 a month (-$141 / -$31 /
  +$4), eval unchanged (80.5 / 85.5%), funded lost 27.2 -> 24.0% / 38.0 -> 34.5%, days under -$500 -> 0, first payout same.
  A safety-for-money trade: offered as a Decide card (LEAD_WIRES), not changed.

## 4. Payout path (R3, as built)

Fri Nov 20 = session 1, Thanksgiving skipped. Eval median 33 / 26 trading days -> passes about Jan 8 / Dec 29; funded payout
needs $1,100 + $500 kept + $500 minimum: first payout median Feb 10 / Feb 18 2027, middle half Jan 20-Mar 16 / Jan 22-Apr 13.
The first Rapid is lost before any payout in 11.7% / 25.7% of runs (re-buy the same night). 2021-25-like markets: no payout.

## How it was done / limits

tools/money/rapid25_launch.py on tools/money/money_plan.RSeat + rapid25.acct("25k", keep $500), ATLAS re-priced with
tools/atlas_fills.priced via tools/atlas_risk.T_at; eval stats rapid_levers.eval_stats on 2,000 eval paths; DLL days = traded
days under -$500 in the slot's day list. Limits: three real ATLAS fills are the cost evidence; exit slippage at 10 ticks is
assumed; the Monte Carlo reshuffles past weeks.
