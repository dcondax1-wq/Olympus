# Rapid EOD 25K launch - report (day-rapid, 2026-11-20)

## For the owner

| What | Result |
|---|---|
| MFFU rules vs the bot | All match (target $1,500, $1,000 EOD floor, $500 DLL = soft pause, 20 micros, 30% eval day, 4 days, funded news ban, payouts). 0 gaps |
| What it trades | LIT + ATLAS $250, as built. $1,883 / $800 a month (Jan-Jun / Jul-Oct-like) vs LIT alone $221 / $191, ATLAS alone $707 / $141 |
| Card atlas-on-rapid | Stays **YES** |
| Card rapid25-lit-bank | Now **NO** at real fills (+$101/mo but the eval fails 0.5% -> 3.1%) |
| Eval pass | 80-86% of runs, about Dec 29 - Jan 8 (median) |
| First payout | about Feb 10-18 (middle half Jan 20 - Apr 13); 6 months pays $4,945-$11,428 |
| Lose the first Rapid before a payout | 12-26% (re-buy $97.20 the same night) |
| Shows up everywhere once added | START BOT, Board, PC report, trade alerts: tested, 11/11 |

All at ATLAS's real fills (10 ticks a side); $ after MFFU's 90% and fees, before the 30% tax pot. 2021-25-like markets: ~$0.

### Rapid first week (3 steps)
1. Phone: open your PC link + `/add-account/` -> Rapid EOD 25K -> tap the Name -> type `I ACCEPT LIVE RISK` -> Add + start trading (it waits for flat by itself).
2. Check you get alerts named **"Rapid EOD 25K"** on the first trade; no trade for 5 days = the bot pushes an inactivity warning (MFFU closes at 7).
3. Thanksgiving week: nothing to do (Thu closed, Fri early close handled). If MFFU pauses the day at -$500, that is normal: it resumes 6 PM ET.

## For the lead

- New: tools/money/rapid25_launch.py (run / sizing), research/lab/rapid25_launch.json, research/second/rapid25_launch_design.md
  (committed 4139ee46 before any run), research/writeups/rapid-launch-2026-11-20.md, tests/test_rapid_launch.py (11/11).
- Changed: tools/web_public/business/decisions.json (rapid25-lit-bank re-valued at real fills -> recommend no, valued by
  rapid25_launch.py; atlas-on-rapid why/risk text; statuses kept open), tools/money/money_plan.py (write_decisions also keeps
  items valued by rapid25_launch.py), tests/test_money_plan.py (part b reads rapid25_launch.json "cards" for those).
- Tests: test_rapid_launch 11/11, test_money_plan 18/18 (browser part skipped: no playwright python), test_rapid25 94/94,
  test_trade_alerts 21/21, test_decide 13/14 (a: the source file must exist on the merged tree; it does on this branch -> 14/14 after the write-up commit).
- Nothing live touched: no engine file, live_model*, accounts, server, sw.js.
- Screenshots (390x844 @2): rapid25-lit-bank.png, atlas-on-rapid.png (business/plan.html Decide list).

---------------------------------------------------------------------------------------------------------------------------
# Round 2: Rapid EOD 50K (the 5th funded slot)

| What | Result |
|---|---|
| 50K vs a 2nd Rapid 25K | **50K wins**: $4,944 / $2,274 a month vs $1,742 / $769 (Jan-Jun / Jul-Oct-like, real fills) |
| What it trades | LIT + ATLAS $500 (LIT alone $803 / $791, ATLAS alone $2,666 / $545) |
| Size | ATLAS on a 10-tick stop: -1 to -3% $, fewer 50Ks lost (26.6% -> 22.7% Jul-Oct-like) |
| Eval | passes 92-94%, ~23 trading days |
| First payout | ~40-48 trading days after the buy (bought Dec 24: ~Feb 22 - Mar 4) |
| Lose it before a payout | 9-16% |
| Rules vs code | all match |
| **Blocker** | the bot runs ONE Rapid: the 50K would be refused next to the 25K. Lead builds two-Rapid support first (LEAD_WIRES R2-1) |

### The day he buys it (only after the lead says two Rapids work)
1. MFFU checkout: Rapid EOD 50K, the cheaper version (the $1,000 daily loss version is fine: the bot already stops at -$1,000), code `CLUB`, paid from kept payouts ($165).
2. Phone: PC link + `/add-account/` -> Rapid EOD 50K -> tap the Name -> type `I ACCEPT LIVE RISK` -> Add + start trading.
3. Tell Claude "50K added: DLL yes/no" so the $1,000 pause line is recorded; first alert should say "Rapid EOD 50K".

Files: research/second/rapid50_launch_design.md (09348676, before any run), tools/money/rapid25_launch.py r50,
research/lab/rapid50_launch.json, research/writeups/rapid50-ready-2026-11-20.md, tools/money/money_book.py (USD_MONTH at real fills).
Tests: test_money_ideas 17/17, test_rapid_launch 11/11.
