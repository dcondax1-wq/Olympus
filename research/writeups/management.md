---
title: Managing the trade: breakeven, locks, time stop, giveback
family: management
date: 2026-10-17
status: finding
summary: Today's management is at its sweet spot on all-days rules, with one exception: on trending days (10-day efficiency above 0.45) NOT moving the stop to breakeven at +1R (or waiting until +3R) adds +$4.7k to 2021-25 (PF 1.09 → 1.15) and leaves 2026 net unchanged (+$20.1k; PF 3.48 → 3.39 through the cold-streak filter). Profit locks, other time stops and giveback levels all lose.
runs: baseline, mgt_be000, mgt_be075, mgt_be125, mgt_be150, mgt_be200, mgt_betrend075, mgt_betrend150, mgt_betrend200, mgt_betrend250, mgt_betrend300, mgt_betrend_off, mgt_betrend300_replay, mgt_lock15_5, mgt_lock20_5, mgt_lock20_10, mgt_lock30_10, mgt_lock30_15, mgt_ts0, mgt_ts15, mgt_ts20, mgt_ts45, mgt_ts60, mgt_tsr025, mgt_tsr100, mgt_gb075, mgt_gb100, mgt_nogb, mgt_ifvgfail, mgt_newsflat0
---

## What was tested

Today: stop to breakeven (entry + 1 tick) at **+1R**; **time stop** if not +0.5R after 30 minutes; **giveback** exit
when a trade that was +0.5R closes back through entry; flat by 15:55; close 5 minutes before high-impact news.

With 1 trade a day, management cannot change which trades are taken, so every variant was re-simulated bar by bar on
the exact replay's own trades with a copy of the engine's exit logic. The simulator reproduces all 768 baseline trades
exactly (exit, time, R, $), so these numbers are exact. The final candidate was also run as a full replay.

Tested before on the old settings: breakeven off / 0.75R / 1.5R, time stop 0 / 15 / 60, giveback off / 1R, partials
and trails (all rejected); earlier breakeven or nearer targets on trending days (0.5-0.75R, caps 1.5-2.5R) in
`study_regime_exits.py`. New here: later breakeven on trending days, profit locks, the time-stop threshold, the gap
"failure" exit.

## Results (exact, costs included, cold-streak filter on)

| Setting | 2026 PF | 2026 net | 2026 max DD | 2026 eval 1 mo pass/fail % | 2021-25 PF | 2021-25 net | 2021-25 max DD | 2021-25 eval 1 mo pass/fail % | back-to-back pass/fail | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Today** | 3.48 | +$20.1k | −$2.7k | 30.5/0.0 | 1.09 | +$6.5k | −$11.4k | 8.8/9.6 | 7/18 | baseline |
| No breakeven move | 2.54 | +$16.7k | −$3.1k | 22.5/0.0 | 1.11 | +$9.4k | −$11.9k | 8.7/14.4 | 9/18 | rejected |
| Breakeven at +0.75R | 3.27 | +$16.9k | −$2.6k | 28.3/0.0 | 1.06 | +$4.0k | −$10.9k | 6.7/9.9 | 6/18 | rejected |
| Breakeven at +1.25R | 3.47 | +$20.1k | −$2.7k | 30.5/0.0 | 1.01 | +$0.7k | −$11.7k | 6.8/9.8 | 7/19 | rejected |
| Breakeven at +1.5R | 3.15 | +$19.3k | −$3.1k | 30.5/0.0 | 1.03 | +$2.0k | −$11.8k | 6.8/9.9 | 6/18 | rejected |
| Breakeven at +2R | 2.68 | +$16.6k | −$3.1k | 19.8/0.0 | 1.07 | +$5.8k | −$11.5k | 8.6/10.8 | 6/18 | rejected |
| Trending days: breakeven at +0.75R | 3.50 | +$20.2k | −$2.6k | 30.5/0.0 | 1.07 | +$5.3k | −$11.4k | 8.8/9.1 | 7/18 | rejected |
| Trending days: breakeven at +1.5R | 3.39 | +$20.1k | −$2.7k | 30.5/0.0 | 1.11 | +$8.0k | −$11.5k | 9.0/9.7 | 7/18 | promising |
| Trending days: breakeven at +2R | 3.39 | +$20.1k | −$2.7k | 30.5/0.0 | 1.11 | +$8.0k | −$11.5k | 9.0/9.7 | 7/18 | promising |
| Trending days: breakeven at +2.5R | 3.39 | +$20.1k | −$2.7k | 30.5/0.0 | 1.12 | +$9.2k | −$11.6k | 9.0/9.6 | 7/19 | promising |
| **Trending days: breakeven at +3R** | 3.39 | +$20.1k | −$2.7k | 30.5/0.0 | **1.15** | **+$11.2k** | −$11.4k | 9.0/9.6 | 8/18 | **promising** |
| Trending days: never breakeven | 3.39 | +$20.1k | −$2.7k | 30.5/0.0 | 1.14 | +$11.0k | −$11.4k | 9.0/9.6 | 8/18 | promising |
| Lock +0.5R after +1.5R | 3.67 | +$21.5k | −$2.1k | 38.0/0.0 | 0.98 | −$1.1k | −$14.1k | 7.4/6.7 | 6/16 | rejected |
| Lock +0.5R after +2R | 3.37 | +$19.2k | −$2.2k | 30.5/0.0 | 1.00 | −$0.3k | −$12.3k | 6.6/7.8 | 5/17 | rejected |
| Lock +1R after +2R | 3.05 | +$17.2k | −$2.4k | 33.7/0.0 | 0.95 | −$3.6k | −$10.3k | 3.9/8.5 | 4/16 | rejected |
| Lock +1R after +3R | 3.32 | +$18.8k | −$2.4k | 30.5/0.0 | 1.06 | +$4.8k | −$10.3k | 6.6/8.5 | 6/17 | rejected |
| Lock +1.5R after +3R | 3.17 | +$17.6k | −$2.3k | 29.9/0.0 | 1.08 | +$5.9k | −$11.4k | 6.8/8.5 | 6/15 | rejected |
| No time stop | 3.29 | +$19.6k | −$3.0k | 30.5/0.0 | 1.04 | +$2.9k | −$13.8k | 9.3/15.0 | 6/20 | rejected |
| Time stop 15 min | 3.27 | +$18.2k | −$2.5k | 29.9/0.0 | 0.97 | −$1.8k | −$9.7k | 8.1/8.8 | 4/16 | rejected |
| Time stop 20 min | 3.28 | +$18.5k | −$2.8k | 30.5/0.0 | 1.04 | +$2.8k | −$11.6k | 8.4/8.3 | 6/16 | rejected |
| Time stop 45 min | 3.08 | +$17.6k | −$2.8k | 19.8/0.0 | 1.04 | +$3.0k | −$12.5k | 8.3/11.9 | 6/19 | rejected |
| Time stop 60 min | 3.33 | +$19.7k | −$2.8k | 30.5/0.0 | 1.06 | +$5.1k | −$12.8k | 8.9/11.7 | 7/19 | rejected |
| Time stop asks +0.25R | 3.35 | +$19.8k | −$2.8k | 30.5/0.0 | 1.02 | +$1.8k | −$12.9k | 8.3/13.0 | 6/18 | rejected |
| Time stop asks +1R | 3.48 | +$19.7k | −$2.5k | 30.5/0.0 | 1.02 | +$1.4k | −$11.7k | 6.4/8.6 | 5/17 | rejected |
| Giveback after +0.75R | 3.33 | +$20.5k | −$2.8k | 30.5/0.0 | 1.06 | +$5.0k | −$13.6k | 7.6/14.0 | 7/22 | rejected |
| Giveback after +1R | 3.12 | +$20.2k | −$2.7k | 30.5/0.0 | 1.02 | +$2.0k | −$11.4k | 9.3/12.4 | 7/20 | rejected |
| No giveback exit | 3.11 | +$20.1k | −$2.7k | 30.5/0.0 | 1.02 | +$1.9k | −$11.4k | 9.3/12.4 | 7/20 | rejected |
| Exit on a close back through the gap | 3.20 | +$18.7k | −$2.7k | 30.5/0.0 | 1.04 | +$3.3k | −$10.4k | 6.6/8.8 | 7/15 | rejected |
| Keep trades open into news | 3.48 | +$20.1k | −$2.7k | 30.5/0.0 | 1.09 | +$6.5k | −$11.4k | 8.8/9.6 | 7/18 | no effect |

Trades are the same in every row: 89 in 2026 (2.16 a week), 679 in 2021-25 (3.17 a week).

## What it means

- **Breakeven at +1R, the 30-minute time stop and the +0.5R giveback are each at their best value** for all days.
  Moving any of them a little either way loses money in 2021-25 (be careful: 1.25R instead of 1R costs $5.8k in
  2021-25, so small changes here are noisy).
- **Profit locks** raise the win rate (to 28-35%) but cut the trades that would have gone on to the target: they
  lose in 2021-25 every time.
- **Trending days are the exception.** On days the market has been trending (10-day efficiency above 0.45; these
  trades already run at half size), moving the stop to breakeven at +1R cuts trades that would have reached the pool.
  Waiting longer helps 2021-25 steadily: +1.5R → +$1.5k, +2.5R → +$2.7k, +3R or never → +$4.5k to +$4.7k (no
  knife-edge). 2026 net is unchanged (+$20,114 vs +$20,111); its PF dips 3.48 → 3.39 only because one 2026 trade
  that now reaches its target (+2.98R instead of −0.02R) switches later trades from half to full size through the
  cold-streak filter during the bad spring stretch. Without the cold-streak filter the change is better in both
  periods (2026 PF 3.07 → 3.10, 2021-25 PF 0.98 → 1.02).
- **Why it works, and the honest caveat:** of the 30 trades it changes, 25 lose a little more (breakeven −0.02R
  becomes a giveback exit around −0.2R) and 5 win big (4 reach the target at +3 to +5R). The gain rests on those 5
  trades, so it is a modest, plausible edge, not a proven one. By year: 2021 +$1.9k, 2022 +$1.9k, 2023 −$0.1k,
  2024 +$1.1k, 2025 −$0.1k, 2026 $0.

## Verdict

- Keep breakeven at +1R, the 30-minute time stop and the giveback exit for normal days.
- **Candidate:** on trending days, move to breakeven only at +3R (`be_at_r_trending: 3`). It is the only
  management change that adds money in 2021-25 without taking any from 2026. Easy to port: the Pine script already
  computes the 10-day efficiency for the half-size rule.
