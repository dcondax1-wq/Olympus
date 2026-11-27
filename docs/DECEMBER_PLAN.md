# December 2026 money plan

Built 2026-11-27 05:38 UTC by `python -X utf8 tools/december_plan.py` (dashboard: tools/web_public/nq/december.json). A plan to read: nothing here changes a bot, a size or an account.

## The month in one look
- **22 trading sessions**: 21 full days, 1 half day(s); closed: Fri Dec 25.
- **Contract roll Thu Dec 10** 00:00 ET (Dec -> Mar contract, hands-free). The same morning has CPI at 08:30.
- **Big news:** 2026-12-04 08:30 Non-Farm Payrolls (jobs report); 2026-12-09 14:00 FOMC rate decision + projections; 2026-12-09 14:30 FOMC press conference; 2026-12-10 08:30 CPI (consumer inflation); 2026-12-30 14:00 FOMC minutes (Dec meeting). LIT goes flat 5 min before each; MFFU evals allow news trading.
- **Expected trades:** LIT about 12 setups (copied to each LIT account), ATLAS about 9 (2026 pace).
- Note: Holiday hours (Dec 24 halt 13:15, Dec 25 closed, Dec 31 full day, Jan 1 closed) come from 5 years of CME bars + the rule (engine/cme_calendar); CME posts the exact hours about 2 weeks before: re-check around Dec 10.
- Note: The forecast is from today's balances on Jan-Oct 2026 (good) and 2021-25 (bad) market paths; the real December can be either.

## Your accounts by Dec 31 (forecast from today's balances, 1,000 paths)
| account | bots | 2026-like market | 2021-25-like (bad) market |
|---|---|---|---|
| Zlarior 50K eval (profit $-822) | LIT | pass 49% / fail 17%; median pass Thu Dec 17 | pass 7% / fail 33% |
| Zlarior 25K #2 eval (profit $19) | LIT | pass 66% / fail 1%; median pass Thu Dec 10 | pass 19% / fail 5% |
| Rapid EOD 25K eval (profit $-5) | LIT + ATLAS | pass 25% / fail 0%; median pass Tue Jan 19 | pass 3% / fail 25% |
| ATLAS 25K funded (profit $401) | ATLAS | first payout by Dec 31: 43%; median Wed Dec 30 | 6% |

## ATLAS funded: the first payout
- Profit now $401. MFFU's first-payout minimum: profit $1,350 (buffer $1,100 + $250) -> ask $250 ($200 to you); $949 more profit needed.
- The plan's first payout goal: $1,000 at $2,100 profit ($800 lands); $1,699 more needed.
- Forecast (2026-like): early case (5% of paths) Mon Dec 07, median Wed Dec 30, 43% chance it is in by Dec 31. Rules: 2 traded days a cycle, best day <= 50% of the cycle's profit, 48 h after the first funded trade; 5 sim payouts then live.
- **December cash, honest:** 43% x $800 = about $346 expected from ATLAS in December (2026-like market); the evals pay nothing until they pass and get funded (January at the earliest).

## MFFU 7-day rule
- MFFU closes an account after 7 calendar days with no executed trade; the bot's keep-alive trades 1 micro when a clock gets short (switch on per account).
- ATLAS 25K funded: last fill Wed Nov 25, trade by Tue Dec 01 (MFFU's last day Wed Dec 02), keep-alive ON.
- Zlarior 25K #2: last fill Wed Nov 25, trade by Tue Dec 01 (MFFU's last day Wed Dec 02), keep-alive ON.
- Zlarior 50K: last fill Wed Nov 25, trade by Tue Dec 01 (MFFU's last day Wed Dec 02), keep-alive ON.
- Rapid EOD 25K: last fill Wed Nov 25, trade by Tue Dec 01 (MFFU's last day Wed Dec 02), keep-alive ON.
- If an account's last trade is Mon Dec 21, its safe deadline is 2026-12-27 and the only session left is 2026-12-24 (Christmas Eve half day, halt 13:15 ET): the keep-alive must trade it, or trade any account that is quiet by Tue Dec 22.
- New Year: Thu Dec 31 is a full day, Fri Jan 1 closed. Last trade Mon Dec 28 -> safe by 2027-01-03 (3 sessions left): no squeeze.

## Week by week
| week of | sessions | LIT setups | ATLAS setups |
|---|---|---|---|
| Mon Nov 30 | 4 | ~2.3 | ~1.7 |
| Mon Dec 07 | 5 | ~2.9 | ~2.2 |
| Mon Dec 14 | 5 | ~2.9 | ~2.2 |
| Mon Dec 21 | 3.5 | ~2.0 | ~1.5 |
| Mon Dec 28 | 4 | ~2.3 | ~1.7 |

## Day by day
| day | market | what the bots do |
|---|---|---|
| Tue Dec 01 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Wed Dec 02 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Thu Dec 03 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Fri Dec 04 | open | Non-Farm Payrolls (jobs report) 08:30 ET: LIT flat by 08:25 (5 min before); MFFU evals allow news |
| Mon Dec 07 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Tue Dec 08 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Wed Dec 09 | open | FOMC rate decision + projections 14:00 ET: LIT flat by 13:55 (5 min before); MFFU evals allow news; FOMC press conference 14:30 ET: LIT flat by 14:25 (5 min before); MFFU evals allow news |
| Thu Dec 10 | open | CPI (consumer inflation) 08:30 ET: LIT flat by 08:25 (5 min before); MFFU evals allow news; contract roll: orders move from MNQ 12-26 to MNQ 03-27 at 00:00 ET (roll_auto, hands-free) |
| Fri Dec 11 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Mon Dec 14 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Tue Dec 15 | open | PPI (producer inflation) 08:30 ET (medium: no pause) |
| Wed Dec 16 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Thu Dec 17 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Fri Dec 18 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Mon Dec 21 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Tue Dec 22 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Wed Dec 23 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Thu Dec 24 | half day (halt 13:15) | half day: halt 13:15 ET; no new entry after 13:00, everything flat by 13:10 |
| Fri Dec 25 | CLOSED | CME closed: no session, no trades. |
| Mon Dec 28 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Tue Dec 29 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |
| Wed Dec 30 | open | FOMC minutes (Dec meeting) 14:00 ET: LIT flat by 13:55 (5 min before); MFFU evals allow news |
| Thu Dec 31 | open | normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET. |

## Taxes
- Move 30% of every payout into the tax pot the day it lands.
- A payout that LANDS in December is 2026 income (paid with the Jan 15, 2027 quarterly 1040-ES for Sep-Dec); one that lands in January is 2027 income (first 2027 quarterly due Apr 15, 2027). Same tax either way, only the year and the due date move. Eval fees paid in 2026 lower 2026's profit.
- Source: research/writeups/taxes-2026-11-17.md (not tax advice: ask a pro for your own case).
