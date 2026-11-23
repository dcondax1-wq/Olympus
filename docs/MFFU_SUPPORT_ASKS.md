# MFFU support asks (night-payday 2026-11-23)

Send this ONE message to MFFU support (help center chat or email) before ATLAS's first payout request. It has no account ids and no
names. When they answer, paste the answer to Claude: it updates docs/ACCOUNT_RULES.md, research/lit/mffu_rules.json and the payout
code (engine/payout_autopilot.py, engine/rapid.py) to match. Until then the bot takes the safe side (see "What the bot does now").

## Copy-paste message

> Hi, I have a few quick payout questions:
>
> 1. Rapid EOD 25K sim funded: is there a waiting time before the first payout request (for example 24 hours after the first funded trade)?
> 2. If I request a payout after the 4:10 PM ET close, or on a Saturday or Sunday, does it count the same as a request during the day? When is it paid?
> 3. I have a Builder 25K sim funded account. If my Builder 50K evaluation passes, may I hold the Builder 50K sim funded account at the same time? (The Builder 50K guide says one sim funded account per user on the Builder plan; the account limits article says one 50K and two 25K.)
> 4. What is the exact name of the button to request a payout in the dashboard, and where do I pick which account it is for?
>
> Thank you!

## What the bot does now (until MFFU answers)
| # | Question | Safe side the bot takes | Where |
|---|---|---|---|
| 1 | Rapid first-payout wait | no request on the first funded trading day: the earliest is the day after the first funded trade | engine/rapid.payout_advice |
| 2 | After-close / weekend requests | the push comes after the 16:10 ET close on a trading day; the morning brief repeats it until recorded | engine/payout_autopilot, tools/morning_brief |
| 3 | 2nd Builder funded | nothing automatic: at Zlarior's pass the owner checks with MFFU before activating the 50K funded | docs/ACCOUNT_RULES.md "Open conflict" |
| 4 | Button name | the push says "left menu Payouts -> request $X from <account>" (what the help pages say) | engine/payout_autopilot.STEPS |

## Other support questions (separate, only if needed)
- Cloud VM: ask only before running NinjaTrader on a cloud VM (docs/PC_OFF_PLAN.md section 4).
- Inactivity keep-alive: not asked, by the owner's choice (2026-11-20, research/lit/mffu_rules.json inactivity.ask_support).
