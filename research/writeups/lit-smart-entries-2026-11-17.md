---
title: LIT smart entries (2026-11-17) - same setups, smarter ways in - conditional pullback limits, 1m confirmation combos, entry timing around the 15-minute check
family: other
date: 2026-11-17
status: rejected - nothing passes both 2026 halves; today's entry (tap of the 5m CISD level, first 1m CISD, buy the next 1m open) stays
summary: Owner 2026-11-17 "smart entries". 31 new entry rules on the exact live LIT setups (engine/lit.py candidates, live filters, one trade a day, Monday rule, weekly stop; stop 1 tick beyond the sweep extreme, VIX-band target >= 1.5R banked at 8R, BE + 1.25, the 15-minute check, costs in), picked on Jan-Jun 2026 and checked on Jul-Oct, 2021-25 shown (5m days), scored at the LIT size, on the live eval path (two_week room_f 0.4 kept to session 80) and on the funded 50K. Limit fills only when price trades through by 1 tick and the fill bar gets no target / breakeven credit. None is better in both halves. Pullback limits after a big 1m CISD candle get a better price but put breakeven and the 15-minute check closer, and Jul-Oct winners dip first: H2 loses $5.3-9.1k (of $9.9k). Waiting 5-15 minutes for the trade to prove itself misses the fast runners (-$8-26k a half). Half now / half at minute 15 kills the one-winner eval pass (2-week pass 44.5% -> 15%). Closest: 1m CISD or a 1m break of structure, whichever first (+$1,778 Jan-Jun, -$787 Jul-Oct; eval path -$877 / +$2,069): rejected. Wide-stop half size and an entry-quality score were not re-run (already rejected). Nothing to switch on. Paper only.
runs: none saved (grid in research/lit/smart_entries.json)
---

## For the owner (one minute)

Today's LIT (the bar to beat): **$5,562 / $2,670 / $25 a month** (Jan-Jun / Jul-Oct / 2021-25, LIT size), eval 2-week pass /
fail **44.5 / 0.0%** and **39.1 / 0.0%**, a pass takes a median **11 / 12 sessions**.

| Idea (cells) | $ a month H1 | $ a month H2 | $ a month 2021-25 | Eval pass speed (2-week pass, median sessions) | Verdict |
|---|---:|---:|---:|---|---|
| **Today's entry** | **$5,562** | **$2,670** | **$25** | 44.5% (11) / 39.1% (12) | keep |
| (a) Limit on a pullback into the 1m CISD candle (50% / the 1m CISD level), 3 or 5 min, then market; only when that candle ran far or is tall (16) | $4,213 - $5,516 | **$225 - $1,236** | $20 - $162 | 41-49% / 29-31% (7.5-16 sessions) | rejected: every one loses Jul-Oct |
| (b) 1m CISD OR a 1m break of structure, whichever first (1) | $5,854 | $2,459 | $105 | 51.3% (8.5) / 34.8% (14) | rejected: Jul-Oct -$787, eval Jan-Jun -$877 |
| (b) 1m CISD + a strong close (top third / above the last high) (2) | $5,001 - $5,307 | $2,703 - $2,727 | $28 - $74 | 43.7-44.5% / 37.7-39.1% | rejected: Jan-Jun -$1.6k / -$3.4k |
| (b) 1m CISD AND a break of the 1m swing / close back above the zone / inside the swept level / 2+ down candles (5) | $1,646 - $3,729 | $133 - $2,719 | -$186 - $264 | 22-43% / 10-42% | rejected: Jan-Jun -$11k to -$24k, 3 drop under 2 trades a week |
| (d) Wait 5-15 min after the fill, enter only if the trade is working (4) | $1,217 - $2,948 | -$13 - $509 | $39 - $279 | 21-46% / 3-12% | rejected: misses the fast winners |
| (d) Half now, half at minute 5 / 15 if working, same $ risk (3) | $3,903 - $4,137 | $1,391 - $1,883 | $4 - $88 | **15.1% / 7-29%** (22-31 sessions) | rejected: the eval's one-winner pass breaks |
| (c) Skip / half size on wide stops (x ATR) | - | - | - | - | not re-run: rejected 2026-11-04 and 2026-11-15 |
| (e) Entry-quality score as size | - | - | - | - | not re-run: rejected 2026-10-19, 10-30, 11-04, 11-15 |

In plain words: **LIT's entry is already the smart one.** A better price shrinks the stop distance in R, so the +1R breakeven
and the 15-minute check sit closer, and in Jul-Oct the winners dip before they run (the same thing `lit-entry-precision.md`
found on 2026-10-18). Waiting for proof costs the runners. Nothing changes; your steps: none.

## 1. What was tested (written before the runs)

Already in "Tested and rejected", so NOT re-run (the rule): a plain resting limit at the zone, a limit at the CISD close /
FVG / 1m CISD level / 50% of the candle for everyone, a 1m BOS / 2m / 3m CISD / close back above the zone as the trigger,
tap tolerance, longer / shorter windows, two-step half-limit entries, "skip when the fill ran away", buy-stop above the CISD
candle, chasing a missed limit (`lit-entry-precision.md`, `lit-1m-management.md`, `lit-untested-entries.md`,
`lit-tight-stops-size.md`); skip a stop wider than 2.51 / 2.81 x ATR (`2026-11-15-lit-deep.md`), the wide third at x0.75
(`2026-11-04_lit_ideas_night.md`: Jul-Oct -$1,597); the A+ quality score, setup-strength tilts (sweep depth, displacement,
climax volume, wick, quick fill, clear path), level age, target distance, trade grades (`lit-edge-2026-10-30.md`,
`2026-11-04_lit_ideas_night.md`, `lit-trade-selection.md`, learn loop 2026-11-15).

New here (31 cells, every one counted):

| Family | Rule | Cells |
|---|---|---:|
| A conditional pullback limit | only when the 1m CISD candle closed more than x planned R above the 5m CISD level (x = 0.14 / 0.25 = the Jan-Jun median / top third of live trades) or the candle is taller than 0.22 / 0.27 R: a limit at the candle's 50% or at the 1m CISD level for 3 / 5 minutes, then market; otherwise the live next-open entry | 16 |
| B confirmation combos | 1m CISD OR a 1m break of structure (last 3-bar swing high before the post-tap low); AND that break; AND the close back above the 5m CISD level; AND back inside the swept level (nearest / all); a run of 2+ down candles; a strong close (top third of the candle); a close above the previous candle's high | 8 |
| D1 wait for proof | wait 5 / 10 / 15 minutes after the would-be fill; enter at full size (size from the real stop) only if the close is at or above the would-be entry, or (15 min) it passes the 15-minute check | 4 |
| D2 staged | half at the live entry, the other half at minute 5 / 15 if working (close >= entry, or passes the 15-minute check); the two halves together inside the live trade's $ risk (full stop + 1 tick + commission); no add = the half only | 3 |

## 2. How it was tested

- `tools/lit_smart_entries.py` wraps `engine/lit.simulate_x` in its own process only (engine and `live_model*.json` untouched):
  the wrapper walks the live tap -> 1m CISD, applies the variant, and hands the fill (bar + price) to the engine's own
  executor through the research hook `cand["mkt"]`. Stop, target (>= 1.5R from the real fill), BE + 1.25, the 15-minute
  check and 15:55 are the live code. A setup that does not fill leaves the day free (the engine's one-a-day queue).
- `check`: with the variant off the wrapper gives the live 631 trades (120 in 2026) entry for entry, exit for exit, $ for $
  (+$45,085), and the D2 scorer with no stage equals the live LIT size.
- Fills (conservative): market = next open + 1 tick; a limit fills only when price trades THROUGH it by 1 tick, at
  min(limit, open); if that bar breaks the stop it is a stop-out, else the trade is managed from the next bar (no target
  or breakeven credit on the fill bar). Decisions on a bar's close act from the next bar.
- Data: TradingView NQ1! 5m + the 2026 1m file (futures only). 2021-25 has no 1m bars: the same rules run on the 5m
  fallback (minutes rounded to 5m bars), a reference line only.
- Money: `tools/lit_edge.evaluate` (LIT size rule with the weekly stop; live eval path two_week room_f 0.4 kept to session
  80, $1.90, a fresh eval every session + Monte Carlo; funded 50K Monte Carlo, live funded sizing). D2 has its own copy of
  each path with the two legs. Gate: more $ in H1 AND H2 at the LIT size and on the eval path, no more 2-week fails,
  2+ trades a week.

## 3. Results

Base: LIT H1 PF 4.98 +$33,901 ($5,562/mo, DD -$2,196, 3.12/wk); H2 PF 2.91 +$9,919 ($2,670/mo, DD -$1,396, 2.56/wk);
2021-25 PF 1.01 +$1,265 ($25/mo, DD -$19,426). Eval path H1 +$33,663 / H2 +$11,735, 2-week 44.5/0.0 and 39.1/0.0, median
11 / 12 sessions. Funded 50K $929 / $915 a month.

Columns: $ a month at the LIT size H1 / H2 / 2021-25; change in net $ vs today (LIT size) H1 / H2 / 2021-25; change on the
eval path H1 / H2; eval 2-week pass/fail % (median sessions to pass) H1, H2; trades a week H1 / H2; PF H1 / H2; max DD H1 /
H2; funded 50K $/month change H1 / H2. Every row: rejected.

| Cell | Rule | $/mo H1 / H2 / 21-25 | d net LIT | d net eval | Eval 2-week (median) | /wk | PF | Max DD | Funded d$/mo |
|---|---|---|---|---|---|---|---|---|---|
| A_ran50_mid_3m | when the 1m CISD candle closed more than 0.14R above the 5m CISD level (Jan-Jun q50): limit at its 50% for 3 min, then market | 4,538 / 225 / 121 | -6,242 / -9,085 / +4,907 | -12,151 / -8,332 | 41.2/0.0 (12.5), 29.0/0.0 (9) | 3.12 / 2.44 | 4.23 / 1.15 | -2,318 / -2,761 | -169 / -712 |
| A_ran50_mid_5m | when the 1m CISD candle closed more than 0.14R above the 5m CISD level (Jan-Jun q50): limit at its 50% for 5 min, then market | 4,382 / 251 / 121 | -7,194 / -8,985 / +4,907 | -12,674 / -8,726 | 41.2/0.0 (11), 29.0/0.0 (7) | 3.12 / 2.44 | 3.99 / 1.16 | -2,318 / -3,294 | -244 / -727 |
| A_ran50_cz1_3m | when the 1m CISD candle closed more than 0.14R above the 5m CISD level (Jan-Jun q50): limit at the 1m CISD level for 3 min, then market | 5,064 / 586 / 41 | -3,034 / -7,742 / +848 | -7,322 / -7,071 | 45.4/0.0 (9), 29.0/0.0 (12) | 3.12 / 2.5 | 4.5 / 1.4 | -2,285 / -2,520 | -16 / -600 |
| A_ran50_cz1_5m | when the 1m CISD candle closed more than 0.14R above the 5m CISD level (Jan-Jun q50): limit at the 1m CISD level for 5 min, then market | 4,581 / 584 / 41 | -5,977 / -7,751 / +848 | -6,328 / -9,474 | 45.4/0.0 (10), 29.0/0.0 (14) | 3.12 / 2.5 | 4.06 / 1.37 | -2,285 / -3,047 | -79 / -648 |
| A_ran67_mid_3m | when the 1m CISD candle closed more than 0.25R above the 5m CISD level (Jan-Jun q67): limit at its 50% for 3 min, then market | 5,284 / 632 / 162 | -1,692 / -7,572 / +6,988 | -5,935 / -5,834 | 44.5/0.0 (10), 30.4/0.0 (9) | 3.12 / 2.5 | 4.93 / 1.45 | -2,276 / -2,459 | -7 / -656 |
| A_ran67_mid_5m | when the 1m CISD candle closed more than 0.25R above the 5m CISD level (Jan-Jun q67): limit at its 50% for 5 min, then market | 5,153 / 488 / 162 | -2,490 / -8,105 / +6,988 | -8,474 / -6,946 | 43.7/0.0 (10.5), 30.4/0.0 (8.5) | 3.12 / 2.5 | 4.73 / 1.33 | -2,276 / -2,992 | -71 / -692 |
| A_ran67_cz1_3m | when the 1m CISD candle closed more than 0.25R above the 5m CISD level (Jan-Jun q67): limit at the 1m CISD level for 3 min, then market | 5,179 / 962 / 109 | -2,335 / -6,345 / +4,307 | -4,210 / -5,128 | 48.7/0.0 (9), 30.4/0.0 (14.5) | 3.12 / 2.56 | 4.77 / 1.69 | -2,235 / -2,159 | +68 / -525 |
| A_ran67_cz1_5m | when the 1m CISD candle closed more than 0.25R above the 5m CISD level (Jan-Jun q67): limit at the 1m CISD level for 5 min, then market | 4,941 / 789 / 109 | -3,787 / -6,987 / +4,307 | -6,039 / -7,661 | 48.7/0.0 (9), 30.4/0.0 (16) | 3.12 / 2.56 | 4.46 / 1.53 | -2,235 / -2,686 | +7 / -605 |
| A_big50_mid_3m | when the 1m CISD candle is more than 0.22R tall (Jan-Jun q50): limit at its 50% for 3 min, then market | 5,516 / 777 / 40 | -281 / -7,032 / +800 | -9,170 / -6,115 | 47.9/0.0 (9), 30.4/0.0 (9) | 3.05 / 2.5 | 4.96 / 1.56 | -2,290 / -2,119 | -70 / -621 |
| A_big50_mid_5m | when the 1m CISD candle is more than 0.22R tall (Jan-Jun q50): limit at its 50% for 5 min, then market | 5,437 / 661 / 40 | -760 / -7,463 / +800 | -11,794 / -6,103 | 47.9/0.0 (8.5), 30.4/0.0 (9) | 3.05 / 2.5 | 4.75 / 1.44 | -2,449 / -2,267 | -131 / -639 |
| A_big50_cz1_3m | when the 1m CISD candle is more than 0.22R tall (Jan-Jun q50): limit at the 1m CISD level for 3 min, then market | 4,443 / 1,236 / 20 | -6,820 / -5,329 / -232 | -7,674 / -5,252 | 45.4/0.0 (7.5), 30.4/0.0 (13.5) | 3.09 / 2.56 | 4.07 / 2.0 | -2,298 / -1,533 | -53 / -462 |
| A_big50_cz1_5m | when the 1m CISD candle is more than 0.22R tall (Jan-Jun q50): limit at the 1m CISD level for 5 min, then market | 4,213 / 1,004 / 20 | -8,225 / -6,189 / -232 | -12,109 / -6,529 | 43.7/0.0 (8), 30.4/0.0 (14) | 3.09 / 2.56 | 3.79 / 1.68 | -2,298 / -1,991 | -177 / -511 |
| A_big67_mid_3m | when the 1m CISD candle is more than 0.27R tall (Jan-Jun q67): limit at its 50% for 3 min, then market | 5,336 / 723 / 31 | -1,377 / -7,232 / +335 | -9,866 / -6,104 | 42.0/0.0 (11), 30.4/0.0 (9) | 3.09 / 2.5 | 4.86 / 1.5 | -2,290 / -2,119 | -108 / -642 |
| A_big67_mid_5m | when the 1m CISD candle is more than 0.27R tall (Jan-Jun q67): limit at its 50% for 5 min, then market | 5,290 / 684 / 31 | -1,658 / -7,380 / +335 | -10,386 / -6,124 | 42.0/0.0 (11), 30.4/0.0 (9) | 3.09 / 2.5 | 4.76 / 1.46 | -2,449 / -2,267 | -124 / -639 |
| A_big67_cz1_3m | when the 1m CISD candle is more than 0.27R tall (Jan-Jun q67): limit at the 1m CISD level for 3 min, then market | 5,104 / 1,182 / 99 | -2,790 / -5,529 / +3,798 | -8,810 / -5,312 | 42.0/0.0 (11), 30.4/0.0 (13.5) | 3.09 / 2.56 | 4.65 / 1.92 | -2,298 / -1,533 | -82 / -493 |
| A_big67_cz1_5m | when the 1m CISD candle is more than 0.27R tall (Jan-Jun q67): limit at the 1m CISD level for 5 min, then market | 4,994 / 1,028 / 99 | -3,459 / -6,101 / +3,798 | -9,095 / -6,555 | 42.0/0.0 (11), 30.4/0.0 (14) | 3.09 / 2.56 | 4.53 / 1.71 | -2,298 / -1,991 | -101 / -515 |
| B_or_bos | 1m CISD OR a 1m break of structure, whichever first | 5,854 / 2,459 / 105 | +1,778 / -787 / +4,102 | -877 / +2,069 | 51.3/0.0 (8.5), 34.8/0.0 (14) | 3.16 / 2.63 | 5.36 / 2.53 | -2,196 / -1,965 | +21 / -60 |
| B_and_bos | 1m CISD AND a close above the last 1m swing high | 3,729 / 1,084 / 264 | -11,169 / -5,891 / +12,213 | -15,102 / -3,480 | 36.1/0.0 (11), 27.5/0.0 (10) | 2.5 / 2.18 | 3.84 / 1.94 | -1,403 / -1,645 | -312 / -388 |
| B_and_zone | 1m CISD AND the close back above the 5m CISD level | 3,217 / 2,719 / 23 | -14,291 / +178 / -81 | -13,017 / +1,785 | 29.4/0.0 (14.5), 42.0/0.0 (11) | 2.97 / 2.5 | 3.01 / 2.96 | -2,096 / -1,231 | -294 / +22 |
| B_and_swept_near | 1m CISD AND the close back inside the swept level (the nearest one) | 2,839 / 133 / -18 | -16,599 / -9,424 / -2,173 | -17,775 / -11,881 | 25.2/0.0 (17), 10.1/0.0 (5) | 1.68 / 1.35 | 5.31 / 1.13 | -1,059 / -2,331 | -470 / -739 |
| B_and_swept_all | 1m CISD AND the close back above every swept level | 1,646 / 1,625 / 138 | -23,867 / -3,883 / +5,773 | -22,496 / -5,504 | 21.8/0.0 (18.5), 24.6/0.0 (12) | 1.25 / 1.15 | 4.17 / 3.21 | -925 / -1,573 | -643 / -452 |
| B_run2 | 1m CISD from a run of 2+ down candles | 3,551 / 2,377 / -186 | -12,257 / -1,090 / -10,759 | -14,897 / +798 | 42.9/0.0 (10), 36.2/0.0 (18) | 2.27 / 1.79 | 3.46 / 3.46 | -1,952 / -1,611 | -477 / -128 |
| B_strong | 1m CISD candle closes in its top third | 5,307 / 2,703 / 74 | -1,551 / +122 / +2,527 | -289 / +26 | 44.5/0.0 (11), 39.1/0.0 (12) | 3.12 / 2.56 | 5.05 / 2.91 | -2,196 / -1,383 | -26 / -6 |
| B_engulf | 1m CISD candle closes above the previous candle's high | 5,001 / 2,727 / 28 | -3,421 / +208 / +143 | -4,109 / +298 | 43.7/0.0 (11), 37.7/0.0 (10.5) | 3.12 / 2.56 | 4.68 / 3.03 | -2,096 / -1,383 | -13 / -1 |
| D1_wait5_above | wait 5 min after the would-be fill; enter (full size, real stop) only if the close is at or above the would-be entry | 2,697 / 20 / 39 | -17,460 / -9,846 / +717 | -13,886 / -10,704 | 46.2/0.0 (9), 2.9/0.0 (52) | 1.99 / 0.96 | 4.49 / 1.03 | -2,194 / -1,094 | -222 / -852 |
| D1_wait10_above | wait 10 min after the would-be fill; enter (full size, real stop) only if the close is at or above the would-be entry | 2,948 / 314 / 256 | -15,933 / -8,752 / +11,801 | -14,438 / -5,582 | 43.7/0.0 (10.5), 11.6/0.0 (29) | 1.88 / 1.28 | 3.82 / 1.4 | -1,216 / -1,330 | -172 / -713 |
| D1_wait15_above | wait 15 min after the would-be fill; enter (full size, real stop) only if the close is at or above the would-be entry | 1,312 / 509 / 279 | -25,906 / -8,030 / +12,976 | -24,025 / -6,186 | 22.7/0.0 (20.5), 7.2/0.0 (22.5) | 1.91 / 1.22 | 2.22 / 1.71 | -3,080 / -2,244 | -726 / -697 |
| D1_wait15_t15 | wait 15 min after the would-be fill; enter (full size, real stop) only if it passes the 15-minute check | 1,217 / -13 / 255 | -26,481 / -9,967 / +11,741 | -29,294 / -7,836 | 21.0/0.0 (20.5), 7.2/0.0 (13.5) | 2.46 / 1.99 | 1.86 / 0.99 | -3,779 / -2,900 | -739 / -798 |
| D2_stage5_above | half at the live entry, the other half at minute 5 only if the close is at or above the entry (both halves inside the live $ risk) | 4,137 / 1,391 / 4 | -8,682 / -4,751 / -1,076 | -10,995 / -1,128 | 15.1/0.0 (22), 10.1/0.0 (30.5) | 3.12 / 2.56 | 5.43 / 2.56 | -1,262 / -791 | -41 / -136 |
| D2_stage15_above | half at the live entry, the other half at minute 15 only if the close is at or above the entry (both halves inside the live $ risk) | 3,951 / 1,586 / 60 | -9,821 / -4,029 / +1,804 | -13,605 / -3,365 | 15.1/0.0 (28), 7.2/0.0 (28) | 3.12 / 2.56 | 4.91 / 2.67 | -1,357 / -1,197 | -134 / -190 |
| D2_stage15_t15 | half at the live entry, the other half at minute 15 only if it passes the 15-minute check (both halves inside the live $ risk) | 3,903 / 1,883 / 88 | -10,111 / -2,924 / +3,208 | -13,237 / -1,169 | 15.1/0.0 (22.5), 29.0/0.0 (19.5) | 3.12 / 2.56 | 4.18 / 2.75 | -1,603 / -1,015 | -247 / -132 |

What the numbers say:
- **A (pullback limits): Jul-Oct falls apart in every cell** ($2,670 -> $225-1,236 a month). 28-48 of 120 trades fill on the
  limit at a better price, but the smaller risk puts the +1R breakeven and the 15-minute check closer: Jul 20 target
  +$1,460 -> breakeven +$4, Oct 13 target +$3,169 -> breakeven, Sep 9 target +$1,160 -> cut -$112. The timeouts enter later
  and worse. Jan-Jun also loses in all 16 (-$281 to -$8,225). 2021-25 (5m) is up in most, a reference only.
- **B (confirmation): only "CISD or BOS" adds trades** (1 in each 2026 half) and wins Jan-Jun at the LIT size (+$1,778) but
  loses Jul-Oct (-$787) and the Jan-Jun eval path (-$877); its Jul-Oct 2-week pass drops 39.1 -> 34.8%. A strong close
  changes 34 / 16 trades for -$1,551 / +$122. Every AND-filter removes winners as often as losers (the entry candle of a
  winner looks like a loser's) and three drop to 1.25-1.79 trades a week.
- **D1 (wait for proof): the trades that are not yet "working" after 5-15 minutes are the winners too** (Jul-Oct winners dip
  a median 0.54R first, `lit-1m-management.md`), and the fast ones are gone before the check. -$8k to -$26k a half.
- **D2 (staged): smaller losses** (max DD -$1,262 / -$791 vs -$2,196 / -$1,396) **but less money** (-$8.7k to -$10.1k H1,
  -$2.9k to -$4.8k H2) and the eval's "one winner passes" sizing breaks: 2-week pass 44.5 -> 15.1% (Jan-Jun), median 22-31
  sessions. The 15-minute cut already caps the losers that the half-size first leg was meant to protect.
- No 2-week fails anywhere (room 0.4 holds them at 0.0% in every cell).

## Verdict

- **Keep today's entry.** 31 new cells, 0 pass the gate; not one is up in both halves even at the LIT size alone.
- Nothing in `engine/`, `live_model.json` or `live_model_lit.json` changed. No adopt-candidate, no lead worth a paper shadow.
- Honest caveats: 1m bars, not ticks (inside a minute the stop is assumed first; a limit needs a trade-through, which is
  conservative); a limit fill is managed from the next 1m bar, so its 15-minute check runs 1 minute later than a market
  fill's; samples are thin (80 / 40 trades); 2021-25 has no 1m bars, so the 1m rules cannot be checked there.

## Files and how to rerun

- `python -X utf8 tools/lit_smart_entries.py check` (base == live, 631 trades)
- `python -X utf8 tools/lit_smart_entries.py grid [A|B|D1|D2 ...]` (SE_OUT=<file> per process, ~6 s a cell) -> `merge` ->
  `research/lit/smart_entries.json`; `report` prints the table rows.
