---
title: ATLAS round 3 - why the funded 25K pays about $580 a month and what could raise it (39 versions), plus the BLITZ funded fix
family: other
date: 2026-11-04
status: nothing to switch on. ATLAS's funded pay is capped by MFFU's 5-payout rule, not by size or targets; no funded-phase knob moves it; the only thing that does is more trades from a second window (the stop-hunt members at half size), which is already running as a paper shadow. BLITZ funded: corrected to $322 / $82 a month; one fix to test lifts it to $357 / $218.
summary: Job 30. The owner's ATLAS 25K passes its eval often (2-week pass / fail 65.5 / 0.0 and 43.5 / 0.0) but the funded account pays only $586 / $519 a month (6-month Monte Carlo, to you, 80% split). 39 versions on the same ATLAS trades - funded sizing, ask line, winner cap, day take-profit, trades a day, a consistency-aware cap, partial exits, member target banking, and a second entry window (the stop-hunt members). Judged on 2026 only - Jan-Jun pick, Jul-Oct check - and, because the eval is unchanged by any funded-phase knob, with the eval's pass / fail beside every row. Then the BLITZ funded-only verdict in plain words and one fix.
runs: ar3_funded_today, ar3_funded_max_trades_day_3, ar3_funded_size_60pct_max1000, ar3_funded_half_off_at_10R, ar3_funded_winner_cap_600, ar3_units_hunts_x05, ar3_units_hunt_trend_x05, ar3_units_hunt_asia_x05, ar3_units_sr_vix_bank5, ar3_units_ema_3R, ar3_combo_hunt_trend_x05_day_tp5000
---

## For the owner (one minute)

| Idea | Jan-Jun | Jul-Oct | Verdict |
|---|---|---|---|
| **Today** (ATLAS funded 25K, 60% of the room, <= $750, winner <= $1,000) | **$586 a month** to you, 78% of accounts reach the 5-payout cap | **$519**, 51% reach it | the bar. A sim-funded account pays at most 5 x $1,000 x 80% = **$4,000**; today's accounts collect 88% / 78% of that in 6 months |
| Ask for the payout sooner or later ($250 / $500 / $1,000 / $1,250 above the buffer) | $576-588 | $506-520 | no change (+-2%) |
| Bigger size (80% / 100% of the room, $1,000 a trade) | $558-592 | $451-518 | no: more stuck accounts in Jul-Oct (up to 24%), pay equal or lower |
| Higher or lower winner cap ($600 / $1,500 / $2,000) | $528-572 | $380-483 | **worse** (the 50% best-day rule gets harder) |
| Stop for the day at +$300 / +$500 / +$800 | $585-586 | $521-524 | no change |
| 3 trades a day (today 2); 1 a day | **$609** / $506 | $519 / $408 | 3: +4% in Jan-Jun, flat in Jul-Oct (harmless); 1: -14% / -21% |
| Winner sized to fit the 50% rule (consistency-aware cap) | $580-583 | $498-532 | no (-1% to +3% in the 6-month view; the per-month-with-fees view falls 4-12%) |
| Half the position off at 1R / 1.5R / 2R | $495 / $525 / $560 | $537 / $462 / $507 | no: the 3R winners are the money |
| Bank targets sooner (S/R at 3R / 5R, EMA 3R, MACD 3R) | $372-529 | $341-485 | **worse**, and the S/R banks cut the eval to 53.8 / 37.7 |
| **A second entry window: the two stop-hunt members at half size** (Asia + any-hour hunts, paper in ATLAS v2) | **$620** (+6%) | **$524** (+1%) | **the only thing that works**: per month once the eval fee and the wait between accounts are counted +32% / +36% ($1,009 / $831 vs $767 / $613); eval 2-week pass / fail **67.2 / 0.0 and 55.1 / 0.0** (better, fails stay 0); costs: 5.5-6.1 trades a week (rule 2-4), Jul-Oct PF 3.06 -> 2.63, 19% of Jul-Oct accounts get stuck |
| The trend hunt alone, half size (+ stop at +$500 a day) | $570-571 (-3%) | $593-597 (+14-15%) | per month with fees: +4-10% / +35-44%; eval 66.4 / 0.0 and 55.1 / 0.0; 4.5-4.7 / 4.0-4.2 trades a week; **better in Jul-Oct, a hair lower in Jan-Jun** |
| The Asia hunt alone | $646 (+10%) | $408 (-21%) | no: Jul-Oct worse |

**What this means:** ATLAS's funded money is not held back by trade size or exits; it is held back by MFFU's payout rules (5 requests of at most $1,000, the best day under half the cycle). Nothing in the funded phase lifts it by more than a few percent. Faster payouts come only from more trades, and the stop-hunt members (already running on paper in ATLAS v2) are the one idea that improves both halves on the money-per-month view and on the eval. **No live change.** Recommendation: keep the ATLAS v2 paper shadow and decide after 20+ hunt trades; the lever beyond ATLAS itself is the second funded 25K MFFU allows, not a bigger size.

**BLITZ funded-only, in plain words:** the $108 -> $0 figure from last night was too small a sample (22 and 6 three-month starts). With 1,000 six-month paths a funded 25K at BLITZ's $150 size pays **$322 a month in Jan-Jun and $82 in Jul-Oct** (any payout in 84% / 49% of the 6 months). It earns less than ATLAS because BLITZ's small edge cannot build the $1,350 balance a first payout needs before the room runs thin: 24% / 59% of accounts get "stuck" (the bot stops trading when one stop could end the account). **One fix to test (paper):** BLITZ's own later-break size in the funded phase (first band break of the day x0.5, later x1.75), stop trading only when the room is one micro's risk (today two), and a day take-profit of +$600 (today +$400): **$357 (+11%) in Jan-Jun, $218 (+166%) in Jul-Oct**, stuck 15% / 11%, lost 0%. The Plutus page now shows $322 / $82.

Your steps: none.

## 1. Why $586 / $519 (the cap)

The funded 25K trades about 4 times a week in Jan-Jun (3 in Jul-Oct) and makes **$1,610 / $1,430 a month** of trading profit (PF 2.98 / 3.06). Only $586 / $519 comes out because:
1. A sim-funded Builder 25K pays at most **5 requests of $250-1,000**, 80% to you: **$4,000 per account**, then MFFU moves it to live. In 6 months **78% / 51%** of simulated accounts reach the 5th payout, so the average account has already collected 88% / 78% of the cap. The room for a better number is +14% / +28% at most, and only by getting there sooner.
2. A request needs the best day under 50% of the cycle's profit and 2 traded days; on 44-48 of 126 sessions the money was there but the rule held it back.
3. The account is never lost (0%) but 8% end "stuck" (room under $100).

The renewal view used below ("cycling net $/mo") = a funded account, paid out, then a new $43 eval (divided by the 92-100% pass rate), 7 sessions of eval and paperwork, then the next account: (money to you per account - eval fee) / (sessions per account + 7) x 21. It shows how fast the cap is reached: today **$767 / $613 a month**.

## 2. The ideas (written down before testing) and the results

| # | Idea | Why it could add money | Versions |
|---|---|---|---|
| 1 | The ask line above the buffer | bigger or earlier requests | 4 |
| 2 | The funded winner cap | winners fit the 50% rule | 3 |
| 3 | The funded size (share of the room, $ cap per trade) | faster to the buffer | 5 |
| 4 | A day take-profit (stop for the day at +$X) | no single day breaks the 50% rule | 3 |
| 5 | Trades a day (1 / 3 vs 2) | more days that count | 2 |
| 6 | A consistency-aware cap (a trade's target may not exceed what the cycle already holds) | the 50% rule never blocks | 3 |
| 7 | Half off at 1R / 1.5R / 2R (from the stored trade path) | bank before the pullback | 3 |
| 8 | Target banking per member (S/R and EMA at 3R / 5R, MACD 3R) | faster, steadier wins | 5 |
| 9 | A second entry window: the stop-hunt members (Asia 18:00-02:00 hunt, trend hunt any hour) at half size | trades at hours ATLAS does not use | 3 |
| 10 | Combinations (ask line + cap; ask line + day stop; hunts + 3 a day; trend hunt + 3 a day / day stop / $1,000 cap); the 39th row is today's baseline | | 7 |

Judging as always: Jan-Jun pick, Jul-Oct check, 2026 only; costs in; funded phase = MC 500 paths x 126 sessions (5-session blocks of the span) on the funded rules (floor locked at +$100, $600 soft daily loss, $1,100 buffer, MFFU consistency, 80%); the eval row is `tools/atlas_v2.score` (the real account-B eval rules) and is unchanged by every funded-phase knob. The replay of today's rules reproduces the stored `atlas_funded.json` ($586 / $519 vs $582 / $517, 50-300 vs 1,000 paths). Half-off uses the bar-open path of the stored trades (a touch inside a bar is missed, so it is conservative). Nothing was skipped: trade counts per week are shown; the 2-4 rule is breached only by the hunt versions.

## 3. What to change (owner decides)

**Nothing today.** The result in one line: the only version that improves both halves is the stop-hunt window, and it is already running on paper (ATLAS v2 shadow, `second_model.json`). It adds trades (5.5-6.1 a week for both hunts, 4.2-4.7 for the trend hunt alone), so it needs the 2-4 rule discussed; judge it on the paper tally. The funded-phase knobs are not worth touching.

## 4. Rejected tonight and why

Ask line; winner cap changes; bigger size; day stop; consistency-aware cap; partial exits; every target-banking change (S/R 3R / 5R lose 14-37%, EMA / MACD 3R lose 7-23%); one trade a day; the Asia hunt alone (Jan-Jun only). Why none helps: the account is paid by cycle, not by size - a bigger winner breaks the 50% rule, a smaller one slows the cycle, and the cap is 5 requests.

## 5. BLITZ funded fix (table)

`tools/blitz_funded_fix.py`, 1,000 six-month Monte Carlo paths per span of the account-C trades, funded rules of a Builder 25K (`research/scalp/blitz_funded_fix.json`).

| idea | Jan-Jun $/mo | Jul-Oct $/mo | any payout % (H1/H2) | stuck % (H1/H2) |
|---|---|---|---|---|
| today_f0.10_cap150_tp400 | 322 (+0%) | 82 (+0%) | 84.4 / 48.6 | 24.0 / 58.9 |
| size_f0.05_cap100 | 326 (+1%) | 68 (-17%) | 84.7 / 46.7 | 22.9 / 58.5 |
| size_f0.15_cap150 | 309 (-4%) | 100 (+22%) | 81.5 / 53.3 | 28.7 / 55.2 |
| size_f0.1_cap200 | 320 (-1%) | 83 (+1%) | 84.4 / 48.6 | 24.2 / 58.3 |
| size_f0.15_cap250 | 297 (-8%) | 128 (+56%) | 81.3 / 55.6 | 29.6 / 52.9 |
| size_f0.2_cap300 | 273 (-15%) | 172 (+110%) | 77.3 / 62.9 | 34.2 / 47.9 |
| day_tp_200 | 223 (-31%) | 85 (+4%) | 77.6 / 51.7 | 30.8 / 51.7 |
| day_tp_300 | 306 (-5%) | 108 (+32%) | 83.8 / 53.9 | 23.7 / 55.2 |
| day_tp_600 | 350 (+9%) | 90 (+10%) | 86.9 / 50.6 | 17.6 / 56.9 |
| day_tp_none | 303 (-6%) | 91 (+11%) | 85.2 / 50.8 | 19.4 / 57.0 |
| later_break_size_x0.5_x1.75 | 316 (-2%) | 153 (+87%) | 81.8 / 58.9 | 28.7 / 50.8 |
| later_break_only | 370 (+15%) | 22 (-73%) | 98.3 / 22.0 | 1.0 / 53.3 |
| later_break_size_cap200 | 296 (-8%) | 185 (+126%) | 78.4 / 64.3 | 35.1 / 46.6 |
| keep_trading_stuck_x0.75 | 331 (+3%) | 89 (+9%) | 87.5 / 54.5 | 19.8 / 44.0 |
| keep_trading_stuck_x0.5 | 334 (+4%) | 96 (+17%) | 88.4 / 60.5 | 16.2 / 13.5 |
| later_break_cap200_stuck_x0.75 | 305 (-5%) | 199 (+143%) | 80.9 / 70.3 | 30.6 / 33.7 |
| later_break_cap200_stuck_x0.5 | 311 (-3%) | 212 (+159%) | 83.0 / 77.2 | 24.9 / 10.7 |
| later_break_size_stuck_x0.5 | 335 (+4%) | 176 (+115%) | 87.4 / 70.8 | 18.4 / 12.2 |
| stuck_x0.5_day_tp_600 | 359 (+11%) | 106 (+29%) | 89.9 / 63.8 | 12.5 / 12.8 |
| later_break_size_stuck_x0.5_day_tp_600 | 357 (+11%) | 218 (+166%) | 87.6 / 74.5 | 15.4 / 11.4 |


Reading: "stuck" is the main loss (24% / 59% of accounts): the bot stops trading when one stop could end the account, and at $150 BLITZ's edge rarely rebuilds the room. Lower stop line alone: +4% / +17%, stuck 16% / 14%. The later-break size alone: -2% / +87%. All three together: +11% / +166%. A bigger fixed size or a tighter day stop moves one half and hurts the other. Test the three together on paper before the funded switch.

## 6. Corrections to last night's published figure

Plutus's BLITZ row said $108 / $0 a month funded-only (22 and 6 three-month starts, too few). It now shows the Monte Carlo figure **$322 / $82** (`tools/blitz_funded_study.py`, key `funded_mc`; the page text says 6-month Monte Carlo). The round-3 writeup (`2026-11-04_lit_ideas_round3.md`) quotes the old figure: superseded by this note.

## Appendix - every ATLAS version

| version | funded $/mo to you Jan-Jun / Jul-Oct (worst 10%) | cycling net $/mo after eval fees | PF | trades/wk | 5 payouts reached % | lost / stuck % | eval 2-week pass / fail Jan-Jun and Jul-Oct |
|---|---|---|---|---|---|---|---|
| funded:today | 586 (400) / 519 (256) | 767 / 613 | 2.98 / 3.06 | 3.98 / 3.05 | 77.6 / 51.2 | 0.0 / 7.8 and 0.0 / 7.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:ask_250 | 576 (398) / 506 (250) | 756 / 604 | 2.99 / 3.07 | 3.99 / 3.06 | 79.4 / 53.0 | 0.0 / 8.2 and 0.0 / 8.0 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:ask_500 | 579 (399) / 513 (250) | 759 / 610 | 2.98 / 3.06 | 3.98 / 3.05 | 78.2 / 51.6 | 0.0 / 8.2 and 0.0 / 8.2 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:ask_1000 | 588 (400) / 520 (267) | 763 / 606 | 2.97 / 3.08 | 3.98 / 3.06 | 76.6 / 49.4 | 0.0 / 7.4 and 0.0 / 6.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:ask_1250 | 587 (400) / 510 (267) | 748 / 585 | 2.98 / 3.09 | 3.99 / 3.05 | 75.6 / 46.8 | 0.0 / 7.0 and 0.0 / 6.6 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:winner_cap_600 | 572 (387) / 380 (0) | 675 / 449 | 2.74 / 2.4 | 3.4 / 2.55 | 69.0 / 23.0 | 0.0 / 4.6 and 0.0 / 18.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:winner_cap_1500 | 569 (109) / 483 (133) | 740 / 561 | 3.04 / 3.04 | 4.13 / 3.05 | 74.8 / 40.6 | 0.0 / 10.8 and 0.0 / 10.4 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:size_100pct_max750 | 558 (0) / 451 (0) | 786 / 643 | 2.98 / 3.02 | 4.02 / 3.09 | 76.4 / 47.8 | 0.0 / 13.2 and 0.0 / 23.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:size_60pct_max500 | 571 (383) / 517 (257) | 706 / 597 | 2.97 / 2.93 | 3.98 / 3.11 | 69.0 / 48.2 | 0.0 / 7.2 and 0.0 / 5.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:day_take_profit_800 | 586 (400) / 521 (256) | 771 / 616 | 2.95 / 3.16 | 3.95 / 3.01 | 78.0 / 51.8 | 0.0 / 7.8 and 0.0 / 7.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:cons_aware_floor300_k1.0 | 583 (400) / 511 (264) | 703 / 586 | 2.92 / 2.99 | 3.98 / 3.11 | 73.0 / 50.2 | 0.0 / 4.8 and 0.0 / 4.4 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:half_off_at_1.0R | 495 (101) / 537 (267) | 606 / 626 | 2.19 / 2.86 | 3.99 / 3.12 | 52.4 / 51.2 | 0.0 / 15.4 and 0.0 / 2.6 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:ask_1000_cons_aware | 588 (400) / 515 (267) | 700 / 589 | 2.95 / 2.99 | 3.97 / 3.11 | 71.2 / 43.2 | 0.0 / 4.0 and 0.0 / 4.0 | 65.5 / 0.0 and 43.5 / 0.0 |
| units:hunts_x0.5 | 620 (640) / 524 (0) | 1009 / 831 | 3.03 / 2.63 | 5.5 / 6.11 | 91.6 / 72.2 | 0.0 / 6.4 and 0.0 / 19.2 | 67.2 / 0.0 and 55.1 / 0.0 |
| units:sr_vix_bank5 | 372 (0) / 341 (0) | 511 / 415 | 2.27 / 2.44 | 3.93 / 2.88 | 32.4 / 11.6 | 0.0 / 34.6 and 0.0 / 15.8 | 51.3 / 0.0 and 31.9 / 0.0 |
| units:ema_3R | 521 (0) / 399 (0) | 844 / 577 | 2.66 / 2.37 | 4.17 / 3.31 | 73.8 / 38.2 | 0.0 / 20.8 and 0.0 / 30.4 | 69.7 / 0.0 and 44.9 / 0.0 |
| funded:winner_cap_2000 | 528 (0) / 415 (0) | 674 / 498 | 2.96 / 2.68 | 4.11 / 3.03 | 61.6 / 27.2 | 0.0 / 14.0 and 0.0 / 15.2 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:size_60pct_max1000 | 592 (400) / 518 (253) | 807 / 609 | 2.91 / 2.94 | 3.99 / 3.05 | 81.6 / 51.0 | 0.0 / 8.2 and 0.0 / 7.6 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:day_take_profit_300 | 585 (399) / 524 (256) | 765 / 622 | 2.95 / 3.2 | 3.94 / 2.99 | 77.8 / 53.0 | 0.0 / 7.8 and 0.0 / 7.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:max_trades_day_1 | 506 (133) / 408 (106) | 608 / 481 | 3.07 / 3.19 | 3.16 / 2.48 | 49.8 / 20.4 | 0.0 / 11.2 and 0.0 / 11.6 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:cons_aware_floor400_k1.0 | 580 (399) / 532 (267) | 722 / 624 | 2.88 / 2.96 | 3.99 / 3.11 | 74.4 / 56.6 | 0.0 / 5.2 and 0.0 / 4.0 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:half_off_at_1.5R | 525 (119) / 462 (110) | 667 / 543 | 2.37 / 2.53 | 3.99 / 3.05 | 61.0 / 41.2 | 0.0 / 12.0 and 0.0 / 11.6 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:ask_1000_day_tp_500 | 589 (400) / 523 (267) | 761 / 612 | 2.94 / 3.2 | 3.95 / 3.0 | 77.2 / 50.0 | 0.0 / 7.4 and 0.0 / 6.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| units:hunt_asia_x0.5 | 646 (641) / 408 (0) | 1058 / 618 | 3.42 / 2.11 | 4.92 / 5.43 | 97.0 / 43.4 | 0.0 / 2.0 and 0.0 / 33.6 | 73.9 / 0.0 and 44.9 / 0.0 |
| units:sr_vix_bank3 | 420 (0) / 447 (133) | 568 / 507 | 2.35 / 2.75 | 3.92 / 2.9 | 42.0 / 28.0 | 0.0 / 27.8 and 0.0 / 7.0 | 53.8 / 0.0 and 37.7 / 0.0 |
| units:macd_3R | 525 (0) / 485 (133) | 699 / 563 | 2.46 / 2.46 | 4.15 / 3.05 | 67.8 / 43.0 | 0.0 / 16.8 and 0.0 / 9.2 | 57.1 / 0.0 and 49.3 / 0.0 |
| funded:size_80pct_max750 | 585 (382) / 494 (0) | 785 / 621 | 2.99 / 3.07 | 3.99 / 3.03 | 79.0 / 51.2 | 0.0 / 8.8 and 0.0 / 15.4 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:size_80pct_max1000 | 585 (362) / 492 (0) | 824 / 619 | 2.9 / 2.97 | 3.99 / 3.03 | 81.4 / 52.0 | 0.0 / 9.8 and 0.0 / 16.6 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:day_take_profit_500 | 585 (400) / 522 (255) | 767 / 618 | 2.95 / 3.18 | 3.95 / 3.0 | 77.8 / 52.4 | 0.0 / 7.8 and 0.0 / 7.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:max_trades_day_3 | 609 (532) / 519 (256) | 837 / 613 | 3.15 / 3.06 | 4.08 / 3.05 | 86.2 / 51.2 | 0.0 / 6.0 and 0.0 / 7.8 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:cons_aware_floor300_k1.5 | 578 (393) / 498 (255) | 677 / 561 | 2.91 / 3.06 | 3.98 / 3.1 | 68.6 / 40.6 | 0.0 / 3.6 and 0.0 / 4.4 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:half_off_at_2.0R | 560 (267) / 507 (221) | 701 / 612 | 2.55 / 2.84 | 3.99 / 3.06 | 69.8 / 49.6 | 0.0 / 9.2 and 0.0 / 8.2 | 65.5 / 0.0 and 43.5 / 0.0 |
| funded:winner_600_ask_1000 | 580 (400) / 370 (0) | 678 / 439 | 2.76 / 2.37 | 3.4 / 2.55 | 68.0 / 20.6 | 0.0 / 4.6 and 0.0 / 17.0 | 65.5 / 0.0 and 43.5 / 0.0 |
| units:hunt_trend_x0.5 | 570 (127) / 593 (400) | 797 / 830 | 2.99 / 3.82 | 4.72 / 4.2 | 77.6 / 83.0 | 0.0 / 11.0 and 0.0 / 8.4 | 66.4 / 0.0 and 55.1 / 0.0 |
| units:ema_vix_bank3 | 529 (0) / 451 (0) | 807 / 569 | 2.63 / 2.69 | 3.99 / 3.09 | 73.4 / 41.6 | 0.0 / 19.2 and 0.0 / 17.8 | 72.3 / 0.0 and 39.1 / 0.0 |
| combo:hunt_trend_x0.5|max_day=3 | 584 (253) / 542 (0) | 852 / 817 | 2.94 / 3.51 | 4.92 / 4.38 | 81.4 / 75.0 | 0.0 / 10.0 and 0.0 / 16.6 | 66.4 / 0.0 and 55.1 / 0.0 |
| combo:hunts_x0.5|max_day=3 | 646 (647) / 480 (0) | 1100 / 791 | 3.2 / 2.53 | 5.91 / 6.64 | 97.0 / 65.2 | 0.0 / 2.4 and 0.0 / 27.0 | 67.2 / 0.0 and 55.1 / 0.0 |
| combo:hunt_trend_x0.5|cfg={'pct_max_usd':1000.0} | 574 (128) / 597 (400) | 804 / 852 | 2.83 / 3.78 | 4.72 / 4.21 | 79.8 / 84.2 | 0.0 / 10.8 and 0.0 / 8.0 | 66.4 / 0.0 and 55.1 / 0.0 |
| combo:hunt_trend_x0.5|day_tp=500.0 | 571 (107) / 597 (400) | 840 / 882 | 2.79 / 3.67 | 4.52 / 3.99 | 80.6 / 85.6 | 0.0 / 12.2 and 0.0 / 8.6 | 66.4 / 0.0 and 55.1 / 0.0 |
