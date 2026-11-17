---
title: LIT walk-forward re-tuning (2026-11-17) - re-fit LIT's knobs every month / quarter on the trailing 6 / 12 months, trade the next period out of sample, 2022-05 to 2026-10
family: other
date: 2026-11-17
status: rejected - re-tuning makes more in 2022-25, but the gain is inside the noise, mostly 2025 alone, and random re-picks do almost as well; it loses in both 2026 halves in all 8 versions. 2023 loses at every one of the 27 settings, so the weak years are not a tuning problem. Paper only, nothing live changed.
summary: LIT was tuned on 2026 Jan-Jun and makes about $0 in 2021-25. Test - does a LIT that re-tunes itself (walk-forward) make money in the old years too? Grid of 27 points (displacement 0.7 / 0.8 / 0.9 ATR, breakeven at 1R / 1.5R / off, target banked at 5R / 8R / 12R; the knobs that moved $ most in a one-at-a-time scan). Each point is a full engine/lit.py backtest with costs. Eight versions (refit monthly or quarterly, trailing 6 or 12 months, score = net minus max drawdown, or PF with at least 1.5 trades a week). Monthly / 12 months / net-minus-DD was named the main one before looking. Every trade is out of sample (2022-05 to 2026-10), re-sized after splicing (LIT size rule, live Builder eval path two_week room_f 0.4 to session 80, Rapid EOD LIT lane). Main version - 2022-25 +$23,095 (PF 1.19, $511 a month) vs static +$710. The +$22.4k gain is 1.3 standard errors and +$26.3k of it is 2025 (2023 and 2024 are worse than static). A random setting at each refit makes +$4.7k (median); the main version beats 93.5% of random draws (95% needed), and the other 7 versions beat only 44-83%. 2026 - Jan-Jun +$22,867 vs +$33,901 (-$11.0k), Jul-Oct +$6,909 vs +$9,919 (-$3.0k); every version loses in both halves (-$9.5k to -$15.6k / -$1.7k to -$7.8k). Stability - the main version changes setting at 13 of 53 refits and picks today's setting at only 1 of 54. 2023 loses money at all 27 settings (best -$6.6k), so no re-tuning of these knobs fixes the bad years. They look like a regime LIT does not trade well, not a fit to 2026. Nothing adopted.
runs: none saved (research/lit/wf_retune.json, tools/lit_wf_retune.py)
---

## For the owner (one minute)

**Question:** LIT was tuned on Jan-Jun 2026. Would a LIT that **re-tunes itself every month** make money in 2022-25 as well?
**Answer: no, not reliably, and it costs money in 2026.** Keep today's LIT.

| What (2022-05 to 2026-10, costs in, every trade out of sample) | 2022-25 $ a month | 2026 Jan-Jun $ a month | 2026 Jul-Oct $ a month | Builder 50K 2-week pass (Jan-Jun / Jul-Oct) |
|---|---:|---:|---:|---|
| **Today's LIT (fixed knobs)** | **$16** | **$5,562** | **$2,670** | **44.5% / 39.1%** |
| Re-tune every month on the last 12 months (main version) | $511 | $3,752 | $1,860 | 39.5% / 40.6% |
| Best fixed knobs picked on 2021-25 (cheats: sees the answers) | $450 | $3,479 | $1,009 | 43.7% / 29.0% |

In plain words:
- Re-tuning does make about **$500 a month more in 2022-25**, but almost all of it is **one year (2025)**. It **loses more than
  today's LIT in 2023 and 2024**, the two bad years. Picking a **random** setting every month also beats today's LIT there (+$4.7k
  vs +$0.7k). Today's knobs are simply among the worst for 2022-25, so beating them proves little.
- In 2026 it gives back **about $1,800 a month (Jan-Jun) and $800 a month (Jul-Oct)**. All 8 versions lose in both halves.
- **2023 loses at every one of the 27 settings** (best -$6.6k). No tuning of these knobs saves the bad year. LIT's weak years
  look like a market type it doesn't trade well, not knobs fitted to 2026.
- Your steps: none. Nothing changes.

## Per year (LIT size rule: $800 risk up to a 20-point stop, weekly stop; MNQ $1.40 + 1 tick a fill)

Builder = MFFU Builder 50K eval with the live size (two_week, room_f 0.4 to session 80, $1.90 a micro), a fresh eval started on
every session of the row: 2-week pass / fail %, median sessions to a pass (within 60). Fails were 0% in every row and version
(the 40%-of-room cap shrinks size as the room shrinks), so slow passing is the cost, not blown evals. Rapid = Rapid EOD 50K, **LIT lane
alone** (no ATLAS): same size, 30 micros, best-day cap 30% x $3,000 x 0.95, pass = $3,000 with the best day <= 30% and 4 days.
A 2-week pass is near 0% everywhere, so the table shows passes within 60 sessions (median sessions). Slower than the LIT + ATLAS
stack numbers in `rapid-levers-2026-11-16.md`. Compare rows with each other only.

**Today's LIT (static, disp 0.8 / BE 1R / bank 8R)**

| Year | Trades/wk | PF | Net $ | $/month | Max DD | Builder 2w pass/fail (median) | Rapid pass in 60 (median) |
|---|---:|---:|---:|---:|---:|---|---|
| 2022 (May-Dec) | 2.41 | 1.83 | +$9,853 | +$1,189 | -$1,541 | 21.8 / 0.0 (19.5) | 0% |
| 2023 | 2.40 | 0.62 | -$13,025 | -$1,060 | -$13,273 | 4.0 / 0.0 (35) | 0% |
| 2024 | 2.61 | 1.02 | +$671 | +$54 | -$8,305 | 12.4 / 0.0 (16) | 0% |
| 2025 | 2.21 | 1.19 | +$3,210 | +$261 | -$7,071 | 9.6 / 0.0 (17) | 0% |
| **2022-25** | 2.41 | 1.01 | **+$710** | +$16 | -$19,426 | 11.5 / 0.0 (18) | 0% |
| 2026 Jan-Jun | 3.12 | 4.98 | **+$33,901** | +$5,562 | -$2,196 | 44.5 / 0.0 (11) | 36.7% (50) |
| 2026 Jul-Oct | 2.56 | 2.91 | **+$9,919** | +$2,670 | -$1,396 | 39.1 / 0.0 (12) | 57.7% (42) |

**Walk-forward, main version (refit monthly, trailing 12 months, score = net - |max DD|)**

| Year | Trades/wk | PF | Net $ | $/month | Max DD | Builder 2w pass/fail (median) | Rapid pass in 60 (median) | vs static (1 s.e.) |
|---|---:|---:|---:|---:|---:|---|---|---|
| 2022 (May-Dec) | 2.44 | 1.82 | +$11,834 | +$1,428 | -$1,865 | 19.4 / 0.0 (15) | 0% | +$1,981 ($3,669) |
| 2023 | 2.40 | 0.66 | -$15,765 | -$1,283 | -$17,139 | 7.2 / 0.0 (9) | 7.0% (23) | -$2,741 ($6,928) |
| 2024 | 2.66 | 0.92 | -$2,509 | -$203 | -$9,016 | 9.6 / 0.0 (14) | 0.8% | -$3,180 ($6,592) |
| 2025 | 2.23 | 1.95 | +$29,535 | +$2,404 | -$6,379 | 26.1 / 0.0 (7) | 0.4% | +$26,324 ($13,797) |
| **2022-25** | 2.43 | 1.19 | **+$23,095** | +$511 | -$23,933 | 15.4 / 0.0 (12) | 3.3% (39) | **+$22,385 ($17,224)** |
| 2026 Jan-Jun | 3.12 | 2.30 | +$22,867 | +$3,752 | -$2,526 | 39.5 / 0.0 (9) | 44.5% (42) | **-$11,034 ($8,943)** |
| 2026 Jul-Oct | 2.56 | 1.92 | +$6,909 | +$1,860 | -$2,780 | 40.6 / 0.0 (8) | 35.9% (36.5) | **-$3,010 ($2,359)** |

**Best fixed knobs picked on 2021-25 (in-sample: an upper bound, not a real result): disp 0.8 / BE off / bank 5R**

| Year | Trades/wk | PF | Net $ | $/month | Max DD | Builder 2w pass/fail (median) | Rapid pass in 60 (median) |
|---|---:|---:|---:|---:|---:|---|---|
| 2022 (May-Dec) | 2.30 | 1.35 | +$6,768 | +$817 | -$2,708 | 26.7 / 0.0 (12) | 23.6% (51) |
| 2023 | 2.34 | 0.86 | -$6,690 | -$544 | -$9,264 | 11.6 / 0.0 (8) | 7.0% (23) |
| 2024 | 2.55 | 0.95 | -$1,925 | -$156 | -$10,797 | 8.8 / 0.0 (6) | 0.8% (13.5) |
| 2025 | 2.19 | 1.85 | +$22,167 | +$1,804 | -$3,819 | 19.3 / 0.0 (13) | 34.9% (33.5) |
| **2022-25** | 2.35 | 1.16 | **+$20,321** | +$450 | -$18,122 | 16.1 / 0.0 (11) | 18.7% (37) |
| 2026 Jan-Jun | 3.12 | 2.36 | +$21,204 | +$3,479 | -$2,243 | 43.7 / 0.0 (7) | 62.5% (36) |
| 2026 Jul-Oct | 2.56 | 1.53 | +$3,746 | +$1,009 | -$2,490 | 29.0 / 0.0 (9) | 39.7% (36) |

Even the cheating upper bound loses in 2023 and 2024 and gives back $12.7k / $6.2k in the 2026 halves.

## All 8 walk-forward versions (net $, difference vs static with 1 s.e.)

| Version | 2022-25 | vs static | Random-pick placebo: share beaten | 2026 Jan-Jun vs static | 2026 Jul-Oct vs static | Setting changes |
|---|---:|---:|---:|---:|---:|---|
| Monthly, 6 mo, net-DD | +$2,355 | +$1,645 ($14.1k) | 44% | -$9,503 ($8.0k) | -$4,520 ($3.9k) | 24 of 53 |
| Monthly, 6 mo, PF | +$7,184 | +$6,473 ($14.4k) | 59% | -$10,880 ($5.0k) | -$7,802 ($4.2k) | 32 of 53 |
| **Monthly, 12 mo, net-DD (main)** | **+$23,095** | **+$22,385 ($17.2k)** | **93.5%** | **-$11,034 ($8.9k)** | **-$3,010 ($2.4k)** | 13 of 53 |
| Monthly, 12 mo, PF | +$11,086 | +$10,376 ($13.7k) | 70% | -$15,029 ($7.7k) | -$1,712 ($2.2k) | 21 of 53 |
| Quarterly, 6 mo, net-DD | +$11,052 | +$10,342 ($14.5k) | 72% | -$10,447 ($5.8k) | -$7,443 ($4.4k) | 16 of 17 |
| Quarterly, 6 mo, PF | +$4,735 | +$4,024 ($14.9k) | 51% | -$10,734 ($7.8k) | -$6,812 ($4.4k) | 14 of 17 |
| Quarterly, 12 mo, net-DD | +$14,753 | +$14,042 ($15.8k) | 83% | -$11,669 ($9.5k) | -$5,673 ($4.6k) | 8 of 17 |
| Quarterly, 12 mo, PF | +$9,269 | +$8,559 ($13.7k) | 66% | -$15,649 ($7.7k) | -$6,812 ($4.4k) | 13 of 17 |
| Static today | +$710 | - | - | - | - | - |

Placebo = the same refit dates with a random one of the 27 settings each time (1,000 draws). Median random draw: +$4.7k in
2022-25 (monthly) / +$4.4k (quarterly), and +$30.8k for all of 2026 vs +$43.8k static. "Share beaten" = how many random draws
the version beats in 2022-25 (95% would be convincing).

## Verdict (rules set before the run)

1. **Beat static in 2022-25 out of sample:** yes on the raw number in all 8, but **no version is clear of the noise.** The main
   version's gain is 1.3 s.e., beats 93.5% of random re-picks (not 95%), and 2025 alone is +$26.3k of the +$22.4k. In 2023
   and 2024 it does worse than static. The other 7 versions beat random re-picks only 44-83% of the time.
2. **Not worse in 2026 H1 / H2 by more than noise:** the main version is -$11.0k (1.2 s.e.) and -$3.0k (1.3 s.e.). Every
   version is worse in **both** halves, and four of them by about 2 s.e. in a half. That pattern is not noise.
3. **Stability:** the main version changes setting at 13 of 53 refits (mostly the target bank 5R / 8R / 12R: 9 changes; BE 4;
   displacement 3). It picks today's setting at only 1 of 54 months. Its favourites are "BE off / bank 12R" (18 months),
   "BE 1.5R / bank 8R" (10) and "BE off / bank 5R" (10). Quarterly / 6 months flips at 16 of 17 refits (noise chasing).

**Rejected.** Re-tuning these knobs does not insure against a regime change. The bad years stay bad (2023 loses at all 27
settings: worst -$30.1k, median -$17.2k, best -$6.6k; 2024 is positive at only 9 of 27). The good years (2022, 2025, 2026)
are good at almost every setting (2022: 27/27 positive, 2025: 26/27). So the years differ by **market regime, not by
knobs**. A re-tuner can only lag behind: it learns "BE off" from 2024-25 and pays for it in 2026, when BE at 1R was right.
One useful fact for later: today's knobs are among the weakest in 2022-25 (rank 18 of 27). The cheaper insurance question
is *when not to trade* (a regime filter), not *how to re-tune*. The drift switch and the 6 bias / regime studies already
tried that without success (see "Tested and rejected").

## Method

- `tools/lit_wf_retune.py` (~2-3 min, 1 CPU) -> `research/lit/wf_retune.json`. Each of the 27 grid points is one
  `tools/lit_final.run` = engine/lit.py `run_x` with live_model.json "lit" plus the point (2021-11-08 .. 2026-10-16, true 1m in
  2026, 5m days before; no 1m data before 2026). Re-sizing the static run reproduces the engine's $ exactly (max diff $0.00).
- Grid choice: a one-at-a-time scan of 15 knobs over all years (displacement, sweep depth, VIX band, min / max R:R, BE
  trigger / offset, wait, 1m CISD window, min / max stop, HOW size, 15-minute check time, inducement distance). The three that
  moved $ most in both regimes were kept, 3 values each, today's value in the middle. Sweep depth, BE offset and the 15-minute
  check barely move 2021-25 (the check only acts on 1m days). HOW size 0.5 (+$11.8k 2021-25, -$11.4k H1) and the inducement
  distance were left out to keep the grid at 27.
- The first out-of-sample month is 2022-05 for every version (data starts 2021-11; the 12-month window grows from 6 to 12
  months in its first half-year). Ties go to today's setting. Trades of the picked setting are spliced month by month, then
  re-sized as one list: the weekly stop is re-counted, and the eval / Rapid paths run on the spliced list.
- Noise = 1 s.e. of the per-session difference vs static over the row (sqrt(n) x sd). The placebo uses LIT-size $ per month of
  each grid run.
- Not done: the eval path's Monte Carlo and the funded 50K path. The LIT-size gate already fails in 2026, so they cannot change
  the verdict.
