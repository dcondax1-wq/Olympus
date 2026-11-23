# ARM red team (2026-11-23): day-armfix d97fa5075 -> day-armfix-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | ATLAS is ALREADY funded on the PC (stage funded, +$401). The YES switch called account_b.to_funded, which REFUSES an already-funded account ("a new funded account needs a new eval first"): Monday's YES would fail and ATLAS stays NOT armed. And any name change made the bot drop ATLAS's state file (engine/account_b._load: another account's file = start clean): closes, ledger, open trade, held, lock -> funded profit, best day and consistency back to zero | HIGH | go.rename_funded(): Name only, every funded field kept (start day, $25,000 start, payouts, eval account, plan, sizing), disarmed until arm_b, state file carried to the new Name (copy of the old kept), put back on any write failure; tracker identical before/after (+$401, $25,401, floor $24,401) |
| 2 | Passed EVAL path took NinjaTrader's balance as the funded start on today's date: with history ($25,401) the +$401 becomes $0 | HIGH | refused unless NinjaTrader is within $50 of the plan start; else [FIX] Start page > Accounts > Funded with the real start day |
| 3 | Phone line `nar` quoted full NinjaTrader Names (e.g. "MFFUEVBLDR... is not in NinjaTrader; MFFUSFBLDR...") into the glance, which rides in the PUBLIC status post | HIGH (privacy) | arm_report.mask(): ids -> last 4 ("...6018"); dates / plain words kept |
| 4 | Name switch while the bot runs: the running bot keeps the old Name in memory and saves its state under it (history lost again) | MED | switch only with the bot stopped ([FIX] STOP BOT, START BOT, YES) |
| 5 | Candidate filter passed balances {}: a 50K-balance account with the same plan letters + last 4 could be offered | MED | real NinjaTrader balances (slot_problem 25K) |
| 6 | YES prompt on closed / piped-empty stdin raised EOFError out of step_arm (no summary) | MED | EOF / Ctrl+C / OSError = no YES |
| 7 | An exception mid-START printed no summary | MED | step_arm wrapper: bot not running = NOT ARMED + reason; running = one [CHECK] line (never a guessed ARMED) |
| 8 | Old eval Name still listed next to its funded twin: ATLAS keeps trading the old one silently | LOW | one [CHECK] line naming both, nothing changed |
| 9 | Route-check failure (ATLAS not armed) stops Zlarior too: unchanged, existing; the new flow adds a non-YES / Start-page path into it (it said so in the summary) | info | not changed (owner / lead decision) |
| 10 | Stale phone reason: shown only while the heartbeat says not armed, cleared by the next successful START, ignored after 36 h | OK | - |

Checked OK: nothing arms without the typed phrase (rc 1, no arm_b, name untouched for "", partial, None, "YES" as the phrase);
YES only from a typed YES (Enter / default / "Y" / "yes please" = no); Start page / auto (inp None) never switch; no env /
argv path; one-candidate rule refuses 2 matches, Rapid letters, Sim / Lucid / other firms, an EV twin, Zlarior's own;
case / spaces match the one real account and the switch uses NinjaTrader's exact Name; summary truthful on every exit
(no phrase, arm problem, server down, bot not started, route-check stop, ATLAS refused, exception); arm_status.json is
gitignored, rows <= 200 chars, glance nar <= 110. account_b.py / second.py / live*.py untouched (helper rule): the fix is
in engine/go.py + engine/arm_report.py. test_account_b_funded: 65/71 on origin/pc AND on day-armfix (the same 6 failures).
Merges: armfix-rt + clockfix-rt + ready-rt all clean (ready-rt's .gitignore lines moved to avoid the one conflict).
