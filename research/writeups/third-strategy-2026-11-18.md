---
title: Third strategy hunt (2026-11-18/19 night) - post-close move into the 18:00 reopen, Camarilla / floor pivots, TD Sequential 9-count - nothing passes; one paper lead (follow the post-close move) fails 2025 and trades ~1 a week
family: other
date: 2026-11-19
status: rejected - 0 of 172 cells hold in 2026 H1, H2, 2025 and 2021-24 (coin-flip sides give 0.4); the two Jan-Jun picks lose Jul-Oct; no Decide proposal; nothing live changed
summary: Lead order - a NEW third NQ strategy that adds money without overlapping Zlarior (LIT, London / NY sweep reversals) or ATLAS (NY EMA / MACD / S-R), ideally at other times or in another way, high win rate and good PF. After reading the rejected list (ORBs, gap fades, every VWAP / band / RSI / turtle-soup fade, level sweep-reclaims in all 9 windows, the lunch squeeze / value-area / 80% rule / London fade, the famous published edges, draw-on-liquidity bias, BLITZ) three untested families were pre-declared - PCM the 16:00-17:00 post-close move (mega-cap earnings hour, MFFU must be flat) traded at the 18:00 Globex reopen, with it or against it (80 cells); CAM the classic Camarilla H3/L3 fade, H4/L4 breakout and floor-trader R1/S1 fade (44 cells); TDS DeMark's TD Sequential 9-count exhaustion fade on 15m / 1h bars of the whole CME day (48 cells). CME NQ1! 5m 2021-10 -> 2026-10-16, costs in ($1.90 a micro + 1 tick), stops 1 tick beyond the structure, $500 a trade, flat by 15:55. Result - 0 of 172 hold in all four spans vs 0.4 with coin-flip directions. The Jan-Jun picks (Camarilla H4 breakout, 2.4/wk, H1 +$9,856 PF 1.58; TD 1h 9-count to bar 1, 2.1/wk, H1 +$19,125 PF 1.98) both lose Jul-Oct (-$3,187 / -$1,379) and 2025; placebo p 0.90 / 0.74 in H2. Win rates are low (21-44%), not high. The one consistent pattern - FOLLOW a big post-close move at the reopen - is positive in H1, H2 and 2021-24 in 14 of its 32 cells (coin-flip: 0 hold), placebo p 0.005 over 2021-25, but it loses 2025 in every cell and trades 0.2-1.4 a week, and added to LIT's 50K at $250 it raises 40-session eval fails (H2 0 -> 13.7%). Paper lead only. All three families registered in the ZEUS Lab (kind new_strategy, Rejected).
runs: (no rl runs) research/second/third_strategy.json, tools/third_strategy.py
---

## For the owner (one minute)

| What | Result |
|---|---|
| New ideas tested | 3 families, 172 versions: the after-hours earnings move into the 18:00 reopen, the classic Camarilla / floor-trader pivots, the DeMark 9-count |
| Hold in Jan-Jun + Jul-Oct + 2025 + 2021-24 | **0** (luck alone gives about 0.4) |
| Best Jan-Jun picks, then Jul-Oct | pivots breakout +$1,683/mo -> **-$881/mo**; 9-count +$3,265/mo -> **-$381/mo** (both lose 2025 too) |
| Win rate | low: 21-44% (these are not high-win-rate strategies) |
| Overlap with Zlarior / ATLAS | about none (daily correlation -0.20 to +0.28) - but there is no steady money to add |
| Closest idea | "follow a big after-hours move at the 18:00 reopen": +$689 / +$566 a month in Jan-Jun / Jul-Oct, +$384 in 2021-24, but **-$306 a month in 2025**, only ~1.3 trades a week |
| Added to Zlarior's 50K eval at $250 | more failed evals (Jul-Oct 40-session fails 0% -> 13.7%) |
| Verdict | **Nothing passes. No proposal, nothing changed.** Keep Zlarior + ATLAS. |

## What was asked and what was not redone

Find a third NQ strategy that wins money on its own clock or in its own way (Asia, lunch, the last hour; mean reversion
vs LIT's / ATLAS's breakouts), high win rate, good PF, judged on the adopt bar (pick on 2026 Jan-Jun, check Jul-Oct, 2025 and
2021-24; costs in; 2-4 trades a week; $ a month, max DD, correlation with Zlarior and ATLAS, eval speed).

Not redone (all on `docs/TESTED_AND_REJECTED.md` or in the write-ups): ORBs of every length, gap fades incl. the failed
opening drive (E2), VWAP / band / RSI / ATR-stretch / turtle-soup / round-number fades (scalp-mean-reversion, 87,920
configs), level sweep-reclaims and window mean reversion in all 9 tradable windows (allday 7,800; stop-hunt 28.7M; strategy
tree 1.13M; Data City 114k), the lunch squeeze, PM continuation, value-area failed auction, 80% rule and London extension
fade (new-strategy hunt), Gao / pre-FOMC / turn of month / overnight drift / RSI(2) / TSMOM / NR7 (public strategies),
the draw-on-liquidity bias trade (hq-bias), exhaustion fades (hq-reversion), the noise-area scalp (BLITZ). A grep of the
write-ups found no Camarilla / floor-pivot or TD Sequential strategy (only quarterly pivots as LIT sweep levels), and
`tools/allday.py` gave the 18:00 window no "prior window", so the post-close move was never traded at the reopen.

## The three families (hypotheses fixed before the run, `tools/third_strategy.py` docstring)

1. **PCM - post-close move into the 18:00 reopen (80 cells; a time LIT / ATLAS never trade).** M = 16:00 close -> 17:00
   close. When |M| >= k x its own 20-day mean (k 0.5 / 1 / 1.5 / 2), trade the 18:00 reopen WITH the move ("follow") or
   AGAINST it ("fade"). Entry at the 18:00 open, or on the first 5m close beyond the 18:00-18:15 range until 20:00. Stop 1
   tick beyond the 16:00-17:00 window's far extreme, or beyond the 18:00-18:15 range. Target 1R / 2R, or (fade) the 16:00
   close. Out at 09:25 or 15:55. Mon-Thu evenings. (Nearest old idea: LIT's 18:00 F-BoS, a LIT entry; this is a standalone
   follow / fade of the whole move.)
2. **CAM - Camarilla and floor-trader pivots, NY hours (44 cells).** From yesterday's RTH high / low / close: fade a probe
   of H3 / L3 that closes back inside within 3 bars (stop beyond the probe or H4 / L4; target 2R, yesterday's close or the
   far L3 / H3), break with a 5m close beyond H4 / L4 (stop beyond H3 / L3 or the breakout bar; 2R / 3R / 15:55), fade an
   R1 / S1 probe to the pivot P or 2R. Entries 09:30 -> 11:30 or 15:00, one a day.
3. **TDS - TD Sequential 9-count exhaustion (48 cells; mean reversion, any hour).** 15m or 1h bars of the whole CME day: 9
   closes in a row above (below) the close 4 bars earlier, after a price flip -> fade at the 9th close or the first
   counter close within 3 bars; optional "perfected" count. Stop 1 tick beyond the setup's extreme; target 1R / 2R / setup
   bar 1's close. Signals 18:00-15:30 or 09:30-15:30 only, one a day, out 15:55.

Execution: own 24-hour walk on CME NQ1! 5m (2021-10 -> 2026-10-16; TradingView export, futures only): signal on a bar
close, entry next 5m open + 1 tick, stop fills at the stop (or the open through it) - 1 tick, a target needs a
trade-through, stop + target in one bar = stop, time exits 1 tick worse, never held past 15:55 (MFFU flat 16:10) or through
the 17:00 halt. $1.90 a micro. $500 a trade, micros = floor(500 / (stop x $2 + $1.90)), 1-40; stops under 8 pts widened to
8, over 150 pts skipped. Judging = the 2026-11-17 hunt's bar: "holds" = n >= 5, net > 0, PF >= 1.1 in each of H1, H2,
2025, 2021-24; chance = coin-flip directions (stop / target mirrored), 10 seeds; H1 pick = n >= 20, PF >= 1.2, 2-4 a week,
best H1 $.

## Results (every cell counted: 172)

| Family | Cells | Hold all 4 spans | Coin-flip mean (max) | H1 + H2 both > 0 | 2-4/wk in H1 | H1 pick |
|---|---:|---:|---:|---:|---:|---|
| PCM post-close move | 80 | 0 | 0.0 (0) | 20 | 8 | none (no 2-4/wk cell with PF >= 1.2) |
| CAM pivots | 44 | 0 | 0.1 (1) | 1 | 9 | `cam_break4_bar_r3_u11` |
| TDS 9-count | 48 | 0 | 0.3 (1) | 2 | 15 | `tds_60_a_bar9_start_all` |
| **All** | **172** | **0** | **0.4** | 23 | 32 | |

**The picks and the closest cell** ($500 a trade; $/mo = net / sessions x 21):

| Cell | Span | Trades (/wk) | Win % | PF | Net $ | $/mo | Max DD | Placebo p |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `cam_break4_bar_r3_u11` (5m close beyond Camarilla H4 / L4 by 11:30, stop beyond the bar, 3R) | H1 | 66 (2.44) | 39.4 | 1.58 | +9,856 | +1,683 | -2,923 | |
| | H2 | 31 (1.94) | 22.6 | 0.68 | -3,187 | -881 | -5,992 | 0.90 |
| | 2025 | 105 (1.98) | 27.6 | 0.89 | -3,667 | -312 | -9,282 | |
| | 2021-24 | 363 (2.16) | 33.1 | 1.22 | +24,269 | +638 | -12,439 | 0.33 (21-25) |
| `tds_60_a_bar9_start_all` (1h 9-count, fade at the 9th close to bar 1, any hour) | H1 | 57 (2.11) | 26.3 | 1.98 | +19,125 | +3,265 | -7,568 | |
| | H2 | 39 (2.44) | 25.6 | 0.89 | -1,379 | -381 | -6,445 | 0.74 |
| | 2025 | 122 (2.30) | 21.3 | 0.80 | -9,115 | -775 | -15,944 | |
| | 2021-24 | 371 (2.21) | 22.4 | 1.00 | +123 | +3 | -17,774 | 0.82 (21-25) |
| `pcm_k5_follow_or15_r2_x0925` (follow a post-close move >= 0.5x its mean on an 18:00-18:15 break, 2R, out 09:25) | H1 | 34 (1.26) | 44.1 | 1.50 | +4,036 | +689 | -1,289 | |
| | H2 | 22 (1.38) | 40.9 | 1.36 | +2,048 | +566 | -3,966 | 0.61 |
| | 2025 | 51 (0.96) | 31.4 | 0.78 | -3,594 | -306 | -4,462 | |
| | 2021-24 | 193 (1.15) | 42.5 | 1.28 | +14,623 | +384 | -11,590 | 0.005 (21-25) |

- **Both Jan-Jun picks are 2026-H1 flukes.** The 9-count's +$19k sits on one half (years: 2021 -$2.9k, 2022 +$13.0k,
  2023 -$4.3k, 2024 -$9.7k, 2025 -$9.5k, 2026 +$16.7k); the Camarilla breakout is an old-years edge (2022 +$13.3k, 2024
  +$11.9k) that lost 2023, 2025 and Jul-Oct. Their H1 PF of 1.6-2.0 is what picking the best of 44-48 looks like.
- **Pivots as fades lose.** 1 of 24 Camarilla H3 / L3 fade cells (+$115 on 8 trades) and 0 of 8 R1 / S1 fade cells are
  positive in H2; every fade cell loses H1; only one is positive in 2021-24 (PF 1.11, and it loses all of 2025-26). Same
  story as every level fade before: a level probe reverses about half the time.
- **The 9-count as a fade loses on 15m** (all 24 15m cells lose 2021-24, -$0.6k to -$62k) and is a coin flip on 1h
  (2021-24 PF 0.60-1.03).
- **The post-close FOLLOW is the one real-looking pattern.** 14 of its 32 follow cells are positive in H1, H2 and 2021-24
  (with coin-flip sides no PCM cell holds), its best placebo p is 0.005 over 2021-25 - but none of the 14 reaches PF 1.1 in
  2025 (0.61-1.05; 10 of them lose), H2 alone is not significant (p 0.61), and it trades 0.2-1.4 a week. FADING the
  post-close move loses (0 of 48 fade cells positive in both 2026 halves; 2R fade at the open: win 23%, PF 0.49 in H1).

**Correlation and winning days** (daily $ vs Zlarior's `research/lab/backtest_live.json` and ATLAS's
`research/runs/atlas_base.json`): -0.12 / +0.28 / +0.03 with Zlarior and -0.20 / -0.13 / +0.06 with ATLAS for the post-close
follow (H1 / H2 / 2021-25); the two picks -0.05..+0.25 / -0.12..+0.01. They add 1.1-2.4 green days a month on days both
bots were not green, but also 3-8 losing days a month.

**Eval speed** (fresh MFFU Builder 50K every session: +$3,000, $2,000 end-of-day trailing; "LIT 50K" = Zlarior's daily $
at the LIT size from `backtest_live.json` on the same rules - a simple view, not the live two_week sizing path):

| Cell | Own 50K at $400: pass / fail in 40 sessions (H1 / H2 / 2021-25) | LIT 50K alone, 40 sessions | LIT 50K + this at $250 |
|---|---|---|---|
| post-close follow | 0/0 · 0/66.7 · 12.6/19.9 | 96.0/4.0 · 78.1/0.0 · 23.2/56.5 | 94.9/5.1 · 78.1/13.7 · 28.7/62.8 |
| Camarilla breakout | 65.5/23.8 · 0/100 · 26.3/42.4 | (same) | 84.0/16.0 · 65.8/31.5 · 30.3/57.2 |
| 9-count 1h | 45.7/51.1 · 20.8/79.2 · 20.8/76.2 | (same) | 70.9/29.1 · 41.1/58.9 · 21.2/78.0 |

None speeds up Zlarior's eval without more failed evals; on their own accounts none passes reliably.

## Verdict

Nothing passes: no third strategy, no new account, no Decide proposal, nothing built for live; Zlarior, ATLAS and BLITZ
unchanged. Paper lead only (not proposed): "follow a big post-close move at the 18:00 reopen" - re-check when 2026 Nov-Dec
bars are in (it needs 2025-like years to stop losing and more than ~1 trade a week). Registered in the ZEUS Lab as kind
`new_strategy` (bot "third"): `third_pcm`, `third_cam`, `third_tds`, all Rejected, 172 cells counted in the many-tests bar.
Not done: 1m execution (1m starts 2025-12-29; no 5m survivor to confirm), ES (5m only from 2025-04).

Reproduce: `python -X utf8 tools/third_strategy.py grid` (~30 s) -> `research/second/third_strategy.json`;
`python -X utf8 tools/third_strategy.py register`.
