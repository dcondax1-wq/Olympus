---
title: Targets: where profits are taken
family: targets
date: 2026-10-17
status: rejected
summary: Today's target (nearest major pool at least 1.5R away, banking at 5R when the draw is farther) is the best of 15 variants. Nearer caps (3-4R) cut 2026 profit by $5-8k; farther caps (6-8R) help 2021-25 a little but cost 2026 $5-7k; exiting in front of the pool changes almost nothing.
runs: baseline, screen_baseline, tgt_minrr12, tgt_minrr20, tgt_minrr25, tgt_minrr30, tgt_maxrr3, tgt_maxrr4, tgt_maxrr6, tgt_maxrr8, tgt_major_next, tgt_touch0, tgt_touch2, tgt_front4, tgt_front8, tgt_front16
---

## What was tested

Today the target is the **nearest untaken major pool at least 1.5R away**, with the exit order 1 tick in front of it.
When that pool is more than 5R away the trade still aims at it but banks at **5R**. No major pool in range = no trade.

- **Minimum distance** of the pool: 1.2R, 2R, 2.5R, 3R (changes which trades are taken: one-pass 5-year backtest).
- **Banking cap**: 3R, 4R, 6R, 8R (one-pass backtest).
- **Aim for the second major pool** instead of the first (one-pass backtest).
- **Fill rules**: the target needs 0 or 2 ticks of trade-through instead of 1, or the exit sits 4 / 8 / 16 ticks
  (1 / 2 / 4 points) in front of the pool. These cannot change which trades are taken, so they were re-simulated on
  the exact replay's own trades (the simulator reproduces all 768 baseline trades exactly).

Tested before on the old settings: min 1R / 2R, caps 3R / 8R, nearest-any-pool and fixed 2R / 3R targets (all
rejected), and on today's settings: no cap, the draw mode and "last real pool" (2026 PF 1.6-2.2).

## Results (costs included, cold-streak filter on)

| Setting | 2026 trades | /wk | PF | net | max DD | eval 1 mo pass/fail % | 2021-25 trades | /wk | PF | net | max DD | eval 1 mo pass/fail % | back-to-back pass/fail | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Today, exact replay** | 89 | 2.16 | 3.48 | +$20.1k | −$2.7k | 30.5/0.0 | 679 | 3.17 | 1.09 | +$6.5k | −$11.4k | 8.8/9.6 | 7/18 | baseline |
| **Today, one-pass yardstick** | 89 | 2.16 | 3.45 | +$19.9k | −$2.7k | 30.5/0.0 | 691 | 3.18 | 1.11 | +$8.8k | −$11.6k | 9.5/9.5 | 7/18 | yardstick |
| Pool at least 1.2R away | 89 | 2.16 | 3.26 | +$17.9k | −$2.2k | 19.8/0.0 | 712 | 3.28 | 1.01 | +$0.5k | −$14.1k | 5.6/9.7 | 6/17 | rejected |
| Pool at least 2R away | 86 | 2.09 | 3.33 | +$19.2k | −$3.1k | 30.5/0.0 | 665 | 3.06 | 1.04 | +$3.0k | −$9.4k | 7.1/8.0 | 6/16 | rejected |
| Pool at least 2.5R away | 85 | 2.06 | 3.32 | +$18.7k | −$3.1k | 30.5/0.0 | 618 | 2.84 | 1.03 | +$2.4k | −$9.3k | 8.7/7.5 | 7/17 | rejected |
| Pool at least 3R away | 83 | 2.01 | 3.30 | +$18.7k | −$3.2k | 30.5/0.0 | 584 | 2.69 | 1.00 | −$0.3k | −$11.4k | 8.3/10.6 | 6/17 | rejected |
| Bank at 3R | 95 | 2.31 | 2.24 | +$11.8k | −$2.3k | 14.4/0.0 | 725 | 3.33 | 1.06 | +$4.7k | −$10.9k | 6.1/9.2 | 7/17 | rejected |
| Bank at 4R | 93 | 2.26 | 2.62 | +$15.2k | −$2.8k | 25.1/0.0 | 702 | 3.23 | 1.08 | +$6.0k | −$11.9k | 8.8/9.0 | 8/17 | rejected |
| Bank at 6R | 86 | 2.09 | 2.65 | +$13.3k | −$2.6k | 17.6/0.0 | 684 | 3.15 | 1.12 | +$9.2k | −$10.7k | 9.5/7.1 | 7/17 | rejected |
| Bank at 8R | 85 | 2.06 | 2.86 | +$15.0k | −$2.6k | 16.0/0.0 | 670 | 3.08 | 1.14 | +$10.1k | −$11.4k | 9.5/6.9 | 7/17 | rejected |
| Second major pool | 83 | 2.01 | 3.70 | +$18.3k | −$3.0k | 30.5/0.0 | 626 | 2.88 | 1.04 | +$3.0k | −$9.8k | 10.2/8.2 | 9/18 | rejected |
| Fill on touch (0 ticks) | 89 | 2.16 | 3.48 | +$20.1k | −$2.7k | 30.5/0.0 | 679 | 3.17 | 1.09 | +$6.5k | −$11.4k | 8.8/9.6 | 7/18 | no effect |
| Fill after 2 ticks | 89 | 2.16 | 3.48 | +$20.1k | −$2.7k | 30.5/0.0 | 679 | 3.17 | 1.09 | +$6.5k | −$11.4k | 8.8/9.6 | 7/18 | no effect |
| Exit 4 ticks in front | 89 | 2.16 | 3.47 | +$20.1k | −$2.7k | 30.5/0.0 | 679 | 3.17 | 1.08 | +$6.0k | −$11.4k | 8.6/9.6 | 7/18 | rejected |
| Exit 8 ticks in front | 89 | 2.16 | 3.46 | +$20.0k | −$2.7k | 30.5/0.0 | 679 | 3.17 | 1.07 | +$5.3k | −$11.5k | 8.6/9.5 | 6/17 | rejected |
| Exit 16 ticks in front | 89 | 2.16 | 3.45 | +$19.9k | −$2.7k | 30.5/0.0 | 679 | 3.17 | 1.05 | +$4.2k | −$11.6k | 8.5/10.2 | 6/18 | rejected |

Rows 3-11 are one-pass backtests: compare them with the yardstick row. The fill rows are exact (replay entries).

## What it means

- **2026's profit is a handful of big winners that reach far pools.** Any cap below 5R cuts them: banking at 3R
  halves 2026 profit (PF 3.48 → 2.24) and still does not help 2021-25.
- **Letting winners run past 5R** helps 2021-25 a little (+$0.4k to +$1.3k against the yardstick) but costs 2026
  $5-7k: 5R is the balance point between the two periods.
- **Asking for a farther pool (2-3R) or the second pool** loses the trades with a near draw that pay well in 2021-25.
  1.2R lets in trades whose reward is too small for the costs.
- **Exiting in front of the pool does not catch more winners.** Few trades stall within 1-4 points of the pool;
  most either touch it or turn well before it. Each extra tick in front just gives away a little on every winner.

## Verdict

Keep the target exactly as it is: nearest major pool at least 1.5R away, exit 1 tick in front, bank at 5R on the way
to a farther draw, no trade without a major pool.
