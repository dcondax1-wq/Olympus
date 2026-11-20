---
title: Payday plan - when each account pays first, what could make it sooner, and where the losses sit (2026-11-20)
family: money
date: 2026-11-20
status: done - paper only. Plan = a forecast from today's balances. 0 of 8 payout levers and 0 of 2 loss cuts pass the rule fixed before the run; no Decide card added, nothing live changed.
summary: Owner 2026-11-19 "We need these fundeds paying next month latest". From today's board (Zlarior 50K $49,193 / $1,025 room, 25K #2 $25,000, ATLAS funded $24,887 / $887 room, Rapid EOD 25K from Nov 20), all accounts on the same 1,000 Monte Carlo paths a market (money_plan seats, live sizing, MFFU rules, costs in, Thanksgiving off). At least one payout by Dec 31 62% / by Jan 15 81% in a Jul-Oct-like market (77% / 90% Jan-Jun-like, 15% / 21% 2021-25-like); the first one is almost always ATLAS's 25K ($800 to you). 8 pre-registered levers judged on payout date AND the chance of losing the account - none is better on both; nearest miss = ATLAS on Zlarior's 50K NOW instead of after the pass. Loss anatomy - no bucket loses money in both 2026 halves except ATLAS at VIX < 15 (already rejected); 2 untested cross-bot loss cuts both cost money.
runs: research/lab/payday_plan.json (tools/money/payday_plan.py), research/lab/payday_losses.json (tools/payday_losses.py), Lab rows research/lab/payday_levers.json, design research/lab/payday_design_2026-11-20.md (committed 7029ddba before any run)
---

## For the owner

**Chance at least one account pays you:** by **Dec 31: 62 in 100**, by **Jan 15: 81 in 100** (a market like Jul-Oct 2026).
Jan-Jun-like: 77 / 90. If the market turns like 2021-25 (the bots had no edge): 15 / 21. The first payout is almost always
**ATLAS's funded 25K: about $800 to you** (MFFU pays $1,000, keeps 20%), $560 after the 30% tax pot.

| Account (today) | First payout: middle date | 8 in 10 runs between | $ to you | Pays by Dec 31 / Jan 15 | Lost before it pays |
|---|---|---|---|---|---|
| **ATLAS 25K, funded** ($24,887, $887 room) | **Mon Jan 4** | Dec 8 - Feb 26 | **$800** | **50% / 66%** | 8% |
| Zlarior 25K #2, eval ($25,000, $1,500 to pass) | Tue Feb 9 | Dec 22 - none by mid-May (17% get none) | $800 | 19% / 31% | 24% |
| Zlarior 50K, eval ($49,193, $3,807 to pass, $1,025 room) | Wed Feb 10 | Dec 30 - May 18 | $1,600 | 12% / 27% | 31% |
| Rapid EOD 25K, eval (starts Nov 20) | Wed Feb 10 | Jan 5 - none by mid-May (11% get none) | ~$690 (90%) | 8% / 23% | 18% |
| **Any account** | **Thu Dec 24** | Dec 8 - Jan 28 | | **62% / 81%** | |

Jul-Oct-like market (the fair row; Zlarior was picked on Jan-Jun). "Lost before it pays" = the eval fails or the funded
account is blown before its first payout (then a re-buy: $91.80 / $63 / $97.20). Jan-Jun-like: ATLAS Dec 18, 25K #2 Feb 3,
50K Feb 11, Rapid Feb 2. The evals pass long before they pay: 25K #2 funded about Dec 9, the 50K about Dec 24, the Rapid
about Dec 31 - then each funded account needs about 6-9 more weeks of profit above MFFU's buffer before the first request.

**What makes it come sooner:** nothing we can switch on safely tonight. 8 ideas tested; each one that brings the payout
sooner also raises the chance of losing an account (table below). The honest levers are the ones already running: leave
the PC on every weekday (a missed week costs a week), and ask for ATLAS's payout the day the bot pings you (balance about
$26,850, 2 traded days, no day over half the cycle).

**Cutting losses:** the losses do not sit in one place we can cut without cutting more winners. Details below.

## The levers (8, fixed before the run; same 1,000 paths; Jul-Oct-like / Jan-Jun-like)

Bar (design file): in BOTH 2026 halves, paid by Jan 15 +1 point or more and the middle first payout not later, AND the
chance of losing the account before it pays up 0.5 point at most (6-month lost up 1 point at most), 2021-25 not worse by
more than 2 points, and no more than $25 a month less.

| Lever | Account | Middle first payout | Paid by Jan 15 | Lost before it pays | Lost in 6 months | $ a month | Verdict |
|---|---|---|---|---|---|---|---|
| L1 ATLAS funded at 40% of the room (open card) | ATLAS 25K | Jan 4 -> Jan 11 / Dec 18 -> Dec 23 | 66 -> 58 / 84 -> 81% | 7.8 -> 4.6 / 7.7 -> 5.5% | 10.2 -> 5.8 / 12.5 -> 7.5% | -$26 / -$25 | no: safer but later (your choice; card stays as it is) |
| L2 ask at $1,000 instead of $750 (open card) | ATLAS 25K + 25K #2 | Jan 4 -> Jan 6 / Dec 18 -> Dec 22 | 66 -> 63 / 84 -> 80% | same | same | -$9 / -$12 | no: later, a bit less |
| L3 ATLAS risks only what reaches the $1,000 line | ATLAS 25K | Jan 4 -> Dec 31 / same | 66 -> 68 / 84 -> 84% | same | 10.2 -> 10.7 / 12.5 -> 11.4% | **-$91** / -$70 | no: barely sooner, $91 a month less |
| L4 ATLAS on Zlarior's 50K NOW (half size in the eval) vs after the pass | Zlarior 50K | Feb 2 -> Jan 21 / Jan 13 -> Jan 12 | 36 -> 43 / 54 -> 59% | 40.7 -> 38.2 / 26.0 -> 8.0% | 20.0 -> 20.2 / **8.3 -> 9.7%** | +$111 / +$122 | **no (nearest miss)**: Jan-Jun 6-month lost +1.4 pts; 2021-25-like 48 -> 63% |
| L5 25K #2 at 40% of the room with a $300 cap | 25K #2 | Feb 9 -> Feb 16 / Feb 3 -> Feb 5 | 31 -> 26 / 34 -> 31% | 24.3 -> 23.7 / 16.3 -> 16.5% | 17.3 -> 16.3 / same | -$16 / -$6 | no: later |
| L6 Rapid: ATLAS $150 instead of $250 | Rapid 25K | Feb 10 -> Feb 18 / Feb 2 -> Feb 5 | 23 -> 14 / 27 -> 19% | 18.4 -> 18.1 / 8.4 -> 5.8% | 28.9 -> 25.6 / 21.3 -> 7.8% | **-$198** / -$522 | no: safer but much later and less |
| L7 Rapid: ATLAS $350 instead of $250 | Rapid 25K | Feb 10 -> Feb 9 / Feb 2 -> Feb 1 | 23 -> 26 / 27 -> 28% | 18.4 -> 20.2 / 8.4 -> 9.8% | **28.9 -> 36.8** / 21.3 -> 29.1% | +$155 / +$348 | no: more money, many more accounts lost |
| L8 Rapid: Zlarior 1 micro banked at the day's room (open card) | Rapid 25K | Feb 10 -> Feb 1 / Feb 2 -> Jan 29 | 23 -> 31 / 27 -> 33% | 18.4 -> 19.8 / **8.4 -> 11.6%** | 28.9 -> 31.9 / same | +$89 / +$2 | no: sooner, but more evals die first |

L4 (combo50k-now) ran on tools/money/combo_account.py's own account model from today's hole (600 week-block paths a market,
both sides on the same paths), so its "after the pass" row differs from the plan table. Read: switching ATLAS on now
brings the 50K's first payout about 1-8 trading days sooner and does NOT raise the chance today's eval dies (Jan-Jun it
falls 26 -> 8%), but more funded accounts get lost within 6 months (Jan-Jun +1.4 pts, 2021-25-like 48 -> 63%). It misses
the bar fixed in advance, so no new card; the open card zlarior-atlas-50k and the advice "after the 50K passes" stand.
Already tested before and not re-run (docs/TESTED_AND_REJECTED.md): ask at $500 / asap on the 25K, Rapid day caps / loose
guard, keep $1,000 on the Rapid, Zlarior on ATLAS's funded 25K.

ATLAS keeps trading 1 micro under $100 of room (your yes, Nov 19): not in this model (it counts under $100 as lost), so
ATLAS's "lost" numbers above are about 1 point too high (tools/atlas_more.py: lost in 6 months 10.5 -> 9.5%, first payout
unchanged).

## Loss anatomy (all bots; the Rapid lanes trade the same signals at other sizes)

Trades: research/anatomy (tools/win_loss_anatomy.py build 2026-11-19), costs in. Today, 2026 Jan-Jun / Jul-Oct / 2021-25:

| Bot | Trades a week | PF | $ a month | Max drawdown |
|---|---|---|---|---|
| Zlarior (LIT size) | 3.1 / 2.6 / 2.4 | 4.98 / 2.91 / 1.01 | $5,681 / $2,786 / $25 | -$2,196 / -$1,396 / -$19,426 |
| ATLAS ($250 a trade) | 4.3 / 3.3 / 5.2 | 3.02 / 2.73 / 1.09 | $4,313 / $2,311 / $302 | -$1,533 / -$1,224 / -$12,430 |

Where the losing $ sit (share of losing $ vs share of trades, Jul-Oct; average R a trade Jan-Jun / Jul-Oct / 2021-25):
- **Hour:** Zlarior London 02-05 = 51% of losing $ with 48% of trades (normal); London late 05-08 = 27% / 33%, +0.70 /
  +0.43 / -0.04R: weaker than average in all three periods, but still WINNING in 2026. ATLAS NY 09:30-11:30 = 35% / 35%,
  +0.77 / +0.63 / +0.04R: the same story.
- **Weekday:** Zlarior Monday Jul-Oct 35% of losing $ with 20% of trades (-0.14R, 8 trades) but Jan-Jun +1.38R; Thursday
  +0.60 / +0.07 / -0.28R (weak, positive in 2026). ATLAS Tuesday +0.25 / +0.59 / 0.00R. No weekday loses in both halves.
- **News:** Tier-1 news days are 14-15% of trades and 9-14% of losing $ for both bots; a release inside the trade is rare
  (2-4%) and not worse. Nothing to cut.
- **Member (ATLAS):** S/R 38% of Jul-Oct losing $ with 31% of trades (+0.42R), MACD 37% / 28% (+0.47R), EMA 25% / 41%
  (+0.93R); in Jan-Jun the order flips (EMA weakest, +0.69R). Every member wins in both halves.
- **Stop size:** Zlarior's middle third of stops (31.5-49 pts) = 54% of Jul-Oct losing $ with 35% of trades; Jan-Jun
  +0.24R but Jul-Oct +0.69R and 2021-25 the best third: not consistent (stop skips are in T&R).
- **VIX:** most losing $ are at VIX 15-20 because most trades are. The ONE bucket that loses money in all three periods:
  **ATLAS at VIX < 15** (-0.30 / -0.58 / -0.08R; Jul-Oct 32% of losing $ with 16% of trades). Already tested and rejected
  (2026-11-18 atlas-health: a knife edge, $543 / $581 / $490 / $330 at a 14.5 / 15 / 15.5 / 16 cut; only 4 Jan-Jun trades).
- **Both bots the same day:** ATLAS does worse on Zlarior's losing days (+0.27 vs +1.08R Jan-Jun, +0.15 vs +0.49R
  Jul-Oct, -0.21 vs +0.13R 2021-25), and both lost on 13 of 60 / 2 of 15 / 111 of 364 shared days.

The two untested loss cuts built on that last finding (fixed before the run):

| Cut | Trades cut (Jan-Jun / Jul-Oct / 2021-25) | Those trades made | $ a month after the cut vs today | Verdict |
|---|---|---|---|---|
| C1 ATLAS stops for the day after a Zlarior loss closed | 17 / 3 / 125 | +0.82 / +1.07 / +0.02R | $3,733 / $2,085 / $291 vs $4,313 / $2,311 / $302; DD 2021-25 -$12,430 -> -$14,841 | no |
| C2 Zlarior stops for the day after an ATLAS loss closed | 13 / 5 / 130 | +0.98 / +0.83 / +0.25R | $3,948 / $2,489 / -$187 vs $5,681 / $2,786 / $25 | no |

Why: ATLAS is worse on Zlarior's losing days mostly in the trades taken BEFORE Zlarior's loss is known; the ones a rule
can still skip were winners. On ATLAS's funded 25K, C1 moves the first payout Jan 4 -> Jan 13 and the chance of losing it
before it pays 7.8 -> 11.8% (Jul-Oct-like). **Nothing survived.**

## How it was run

`python -X utf8 tools/money/payday_plan.py` (n = 1,000 a market, ~2 min) and `python -X utf8 tools/payday_losses.py --seat`.
Seats = tools/money/money_plan.py (the live sizing code, MFFU Builder / Rapid rules as coded there), from today's board:
Zlarior 50K eval session 25 on Nov 20; 25K #2 session 3; ATLAS funded with the -$113 day in its cycle and the 48 h wait over;
Rapid EOD 25K from Nov 20 (LIT + ATLAS $250, the 30% guard, the $500 day, keep $500). Every account on the same week-block
paths (one bad week hits all of them). Thursday Nov 26 counted as no session, Friday Nov 27 as a normal one, Dec 25 and
Jan 1 closed. A path with no payout in 6 months counts as "after mid-May" in the date ranges. Backtests overstate; these are
estimates, not promises.
