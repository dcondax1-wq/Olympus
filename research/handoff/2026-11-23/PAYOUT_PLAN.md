# First-payout plan, per account (2026-11-23, from the PC's own numbers)

Source: the PC's public status post (tools/board.fetch_lite, 2026-11-22 evening ET). Dates and odds: tools/money/payday_plan.py
`--asof 2026-11-23` (the live sizing code + MFFU rules, 1,000 simulated runs per market, 5-session week blocks of the stored
trades, Thanksgiving Nov 26 = no session). **Estimates, not promises.** "Jul-Oct-like" = a market like 2026 Jul-Oct (the check half);
"2021-25-like" = the long history, where these strategies mostly lose.

| Account (today) | $ still to make: pass | $ still to make: first payout | First payout to you | Earliest realistic (10%) / typical (median), Jul-Oct-like | Paid by Dec 31 / Jan 31 | 2021-25-like |
|---|---|---|---|---|---|---|
| **ATLAS 25K funded** (MFFU profit +$401, best day $514) | done (funded) | **+$1,699** (to $2,100 MFFU profit, then ask the max $1,000; the $514 day is fine once the cycle is over $1,028) | **$800** ($1,000 x 80%) | **Dec 4 / Dec 23** | 61% / 85% | 21% by Dec 31; 73% lose it first |
| **Zlarior 50K eval** ($49,214, room $1,046) | **+$3,786** | +$4,100 more after the pass (ask the max $2,000) = **$7,886 in all** | **$1,600** ($2,000 x 80%) | Dec 31 / **Feb 16** (funded: median Dec 28) | 10% / 37% | no payout; 96% fail first |
| **Zlarior 25K #2 eval** ($25,024) | **+$1,476** | +$2,100 more after the pass (ask $1,000) = **$3,576 in all** | **$800** ($1,000 x 80%) | Dec 28 / **Feb 17** (funded: median Dec 10) | 14% / 39% | no payout; 89% fail first |
| **Rapid EOD 25K eval** ($25,000, session 2) | **+$1,500** (4+ days, best day <= 30%) | about +$2,100 MFFU profit after the pass (keeps $1,100 buffer + the bot's $500, $500 min) = **about $3,600 in all** | **about $620** (median request ~$690 x 90%) | Jan 6 / **Feb 11** (funded: median Jan 4) | 6% / 38% | no payout; 93% fail first |

Plain words:
- **ATLAS is the next money: about $800, most likely just before Christmas** (Dec 23 median; a 1-in-10 chance by Dec 4). It needs about
  $1,700 more profit. The phone says "Payout ready: ATLAS 25K can request $1,000 now" the day it is allowed (engine/payout_autopilot).
- The three evals each need a pass first; their first payout is most likely **mid-February**, with about a 1-in-3 chance by Jan 31.
- Splits: Builder accounts pay **80%** to you (not 90%); only the Rapid pays **90%**.
- If the market behaves like 2021-25 instead of 2026, expect almost no payouts and most evals failed: the real risk.
- Reality check: the Zlarior 50K is 26 sessions in and down $786 (the backtest's median pass is 7 sessions). The simulation starts
  from today's real balances, so it already counts that.

How each number was made (assumptions):
- $ to pass = MFFU target - balance. $ to the first payout = the owner's plan: ask only the max request ($1,000 on a 25K at $2,100 MFFU
  profit; $2,000 on a 50K at $4,100), because each Builder gets only 4 payouts before you must close it (never take #5).
- Rapid: the bot keeps $500 above MFFU's $1,100 buffer; MFFU's minimum request is $500; its first request in the runs is $690 (median).
- Pace = the stored backtest trades of each account's own strategy at the live sizing (Zlarior = LIT, ATLAS = ATLAS, the Rapid = both
  lanes), not a flat $/week. For a rough feel: 2026 Jul-Oct-like ATLAS funded about $45-$150 a week, LIT on the 50K about $260 a week.
Command: `python -X utf8 tools/money/payday_plan.py --n 1000 --only plan --asof 2026-11-23` (25 s here).
