# Payday check (night-payday 2026-11-23): payout math + dates against docs/ACCOUNT_RULES.md

Read only. Never requests, arms or trades. The code checked: engine/funded_life.track (Builder funded: ATLAS, later Zlarior),
engine/rapid.payout_advice (Rapid EOD), engine/payout_autopilot (the phone push), tools/morning_brief + tools/pc_guard (the brief
and the 16:15 summary), tools/web_public/business/payoutcoach.js + engine/payout_coach.py (the phone card). Dates: business/payday.json
(tools/money/payday_plan.py --asof 2026-11-23, 1,000 Jul-Oct-like paths; an ESTIMATE, not a promise).

## Rules vs code
| Rule (ACCOUNT_RULES) | Builder 25K funded (ATLAS) | Builder 50K funded (Zlarior after the pass) | Rapid EOD 25K / 50K funded | Code |
|---|---|---|---|---|
| Buffer kept in | $1,100 | $2,100 | $1,100 / $2,100 (+ the bot's $500 / $1,000 cushion) | ok |
| Minimum request | $250 above the buffer | $500 above the buffer | $500 | ok |
| Maximum request | $1,000 | $2,000 | none | ok |
| Owner's plan | ask only at the max: $1,000 at $2,100 profit | $2,000 at $4,100 | the day the balance passes buffer + cushion + $500 | ok |
| First request wait | 48 h after the first funded trade | 48 h | 24 h (third-party page only) | Builder ok; **Rapid: FIXED** (was not checked) |
| Traded days a cycle | 2 | 2 | not stated | ok |
| Consistency | best day <= 50% of the cycle | 50% | none funded (30% in the eval) | ok |
| Between payouts | every 2 days (the 2-day cycle) | same | daily, $250 / $500 net since the last | ok |
| Split | 80% | 80% | 90% | ok |
| Payout #5 | never (MFFU moves you live, every sim sleeps) | never | n/a | ok (guard) |

Fixed tonight: the Rapid's FIRST request now waits for the trading day after the first funded trade (24 h), labelled "needs MFFU
confirm". Wording: the phone push, the 16:15 summary, the morning brief (its own line 2 + the title) and the phone card all say
"REQUEST PAYOUT TODAY: <account> $X". One push per payout cycle (Builder) / per day (Rapid), until the owner records it.

## Per account (as of 2026-11-23)
| Account | Now | MFFU's earliest legal request | Plan's request | $ to you | Most likely (10% chance by) |
|---|---|---|---|---|---|
| ATLAS 25K funded | +$401 MFFU profit, 2 traded days, 48 h done | the first close at >= $1,350 profit with the best day <= 50% (MFFU would pay $250 = $200 to you) | $1,000 at $2,100 profit ($1,699 more) | $800 | Dec 23 (Dec 4) |
| Zlarior Builder 50K eval | $3,786 to pass | after the pass: 48 h + 2 days, $2,600 profit (min $500) | $2,000 at $4,100 | $1,600 | Feb 16 (Dec 31) |
| Zlarior Builder 25K #2 eval | $1,476 to pass | after the pass: 48 h + 2 days, $1,350 | $1,000 at $2,100 | $800 | Feb 17 (Dec 28) |
| Rapid EOD 25K eval | $1,500 to pass, 4 days, best day <= 30% | after the pass: day 2 funded, $1,600 profit ($500) | from $2,100 profit ($500+) | ~$690 avg | Feb 11 (Jan 6) |

## What the owner clicks, and when
The push lands after MFFU's close (16:10 ET; a half day 13:00 / 13:15) on the first eligible day, and the next morning brief repeats it
until it is recorded. Then: MFFU dashboard (myfundedfutures.com) -> left menu **Payouts** -> request the $ shown for that account.
First payout only: Personal Settings > KYC, a Riseworks account, sign the Riseworks agreements MFFU emails. Paid in 6-12 business hours.
Then TRADE_HOME -> P (records it: the push stops, the Money pipeline counts it).

## Needs MFFU confirm (ask support before the first request)
1. Rapid EOD funded: is there a 24 h wait after the first funded trade? (we wait one trading day to be safe)
2. A request made after the 16:10 close, or on a weekend: does it count, and is it paid the next business day?
3. One sim-funded Builder per person (Builder 50K guide) vs 1 x 50K + 2 x 25K (limits article): under the strict reading Zlarior's
   50K cannot become funded while ATLAS's 25K is.
4. The request button's name and the account picker (not on the help pages).
