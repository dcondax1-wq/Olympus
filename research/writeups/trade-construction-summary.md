---
title: Trade construction: what to change before Sunday
family: other
date: 2026-10-17
status: finding
summary: One change is worth making: on trending days, move the stop to breakeven at +3R instead of +1R. Same trades, same 2026 profit (+$20.1k) and eval odds, +$4.7k in 2021-25 (PF 1.09 → 1.15). Stops, targets, the other exits, filters and timing are already at their best; 140+ variants tested, no leak found.
runs: baseline, mgt_betrend300_replay, mgt_betrend300, mgt_betrend250, mgt_betrend_off, combo_risk_sizing, combo_betrend3_risksizing, bias_both_07, combo_betrend3_both07, combo_betrend3_bothhalf, leak_both_off
---

## The recommendation (one change)

**Keep every rule as it is, except: on a trending day (10-day efficiency above 0.45, the same test that already
halves the size), move the stop to breakeven only once the trade is +3R, instead of +1R.**

`live_model.json` params: add `"be_at_r_trending": 3.0` (the engine option already exists; nothing else changes).
Pine: where the script moves the stop to breakeven at `beAtR`, use 3.0 instead when the regime is trending
(`regimeEr` is already computed for the half-size rule). Two lines.

Status: **promising, not a strict pass.** 2026 net is the same and 2021-25 is clearly better, but the 2026 profit
factor dips from 3.48 to 3.39 (explained below). If the owner only accepts strict passes, the answer is "keep the
current rules": nothing else came close.

## Full table: today's rules vs the recommendation (exact, costs included)

| | 2026 today | 2026 new | 2021-25 today | 2021-25 new | All years today | All years new |
|---|---:|---:|---:|---:|---:|---:|
| Trades | 89 | 89 | 679 | 679 | 768 | 768 |
| Trades a week | 2.16 | 2.16 | 3.17 | 3.17 | 3.0 | 3.0 |
| Weeks with 2+ trades | 71% | 71% | 92% | 92% | 89% | 89% |
| Win rate | 24.7% | 25.8% | 20.5% | 21.1% | 21.0% | 21.6% |
| Average R per trade | +0.38 | +0.41 | −0.00 | +0.01 | +0.04 | +0.06 |
| Profit factor | 3.48 | 3.39 | 1.09 | **1.15** | 1.32 | **1.37** |
| Net | +$20,111 | +$20,114 | +$6,491 | **+$11,174** | +$26,602 | **+$31,288** |
| Max drawdown | −$2,661 | −$2,658 | −$11,401 | −$11,420 | −$11,401 | −$11,420 |
| Worst day | −$554 | −$554 | −$875 | −$875 | −$875 | −$875 |
| Eval passed / failed within 2 weeks | 19.8% / 0% | 19.8% / 0% | 4.1% / 2.1% | 4.2% / 2.2% | 6.5% / 1.7% | 6.6% / 1.8% |
| Eval passed / failed within 1 month | 30.5% / 0% | 30.5% / 0% | 8.8% / 9.6% | 9.0% / 9.6% | 12.2% / 8.0% | 12.4% / 8.0% |
| Back-to-back evals passed / failed | 4 / 1 | 4 / 1 | 7 / 18 | 8 / 18 | 11 / 19 | 12 / 19 |

By year (net): 2021 +$1.7k → +$3.6k · 2022 −$7.0k → −$5.1k · 2023 +$8.4k → +$8.3k · 2024 +$1.7k → +$2.9k ·
2025 +$1.6k → +$1.4k · 2026 +$20.1k → +$20.1k. No year is worse by more than $0.1k.

Method: management-only change, so the trades are the same; exits re-simulated on the exact live-loop replay's
trades (the simulator reproduces all 768 baseline trades exactly) and confirmed by a full exact replay
(run `mgt_betrend300_replay`).

## Why it helps, and how sure we are

- Trending-day trades are reversals against a trending market (already at half size). Moving them to breakeven at
  +1R cut the few that went on to the pool. Without the early breakeven, the giveback exit (close back through
  entry after +0.5R) still protects them, so the cost is small: about −0.2R instead of −0.02R on 25 trades.
- Over 5 years it changes only 30 trades: 25 lose a little more, 5 win big (4 reach the target at +3R to +5R).
  So the gain rests on about one trade a year: plausible, not proven.
- Not a knife-edge: waiting until +1.5R adds $1.5k, +2.5R $2.7k, +3R $4.7k, never $4.5k in 2021-25; all leave 2026
  net unchanged.
- The 2026 PF dip is a side effect of the cold-streak filter, not of worse trades: one April trade becomes +2.98R
  instead of −0.02R, which keeps later trades at full size during the bad spring stretch. 2026 R per trade rises
  (+0.38 → +0.41) and, without the cold-streak filter, the change is better in both periods (2026 PF 3.07 → 3.10,
  2021-25 PF 0.98 → 1.02).

## If the sizing recommendation is adopted too

The sizing research (`risk-summary.md`) recommends quarter size in cold streaks and half size on late entries. The two
changes touch different things (sizes vs the breakeven move) and add up (run `combo_betrend3_risksizing`, exact,
same trades):

| | 2026 sizing only | 2026 sizing + breakeven | 2021-25 sizing only | 2021-25 sizing + breakeven | All years sizing only | All years both |
|---|---:|---:|---:|---:|---:|---:|
| Profit factor | 4.12 | 3.94 | 1.19 | **1.27** | 1.48 | **1.54** |
| Net | +$20,583 | +$20,487 | +$11,546 | **+$16,379** | +$32,129 | **+$36,866** |
| Max drawdown | −$2,153 | −$2,249 | −$9,183 | −$9,265 | −$9,183 | −$9,265 |
| Eval 1 month pass / fail | 31.6% / 0% | 31.6% / 0% | 8.7% / 5.2% | 8.9% / 5.3% | 12.3% / 4.4% | 12.5% / 4.4% |
| Back-to-back passed / failed | 4 / 1 | 4 / 1 | 7 / 10 | 8 / 10 | 11 / 11 | 12 / 11 |

Same pattern as on its own: 2026 money unchanged (−$96), its PF dips through the cold-streak state, 2021-25 +$4.8k.
Against today's live rules the pair is better in both periods (2026 +$0.4k, PF 3.94 vs 3.48; 2021-25 +$9.9k, PF 1.27
vs 1.09).

## What NOT to do (tested today on the live settings)

| Idea | What happened |
|---|---|
| Wider or ATR-scaled stop buffer (3-6 pts, 0.1-0.5 x ATR) | fewer trades (under 2 a week) and less 2026 profit; ATR 0.15 looked good only by skipping trades, its neighbours are worse |
| Tighter buffer (1 pt), stop beyond the gap | wicked out more; 2021-25 loses money with the gap stop |
| Widest stop 45-50 / 70-80 | 45-50 cuts good trades; 70-80 adds about-break-even trades (useful only if more trades a week are wanted) |
| Draw at least 2-3R away, or the second pool | 2021-25 profit falls to −$0.3k to +$3.0k |
| Bank at 3R / 4R | 2026 profit falls by $5-8k |
| Bank at 6R / 8R | 2021-25 +$0.4k to +$1.3k, but 2026 −$5k to −$7k |
| Exit a few ticks in front of the pool | changes almost nothing, slightly worse |
| Breakeven earlier or later on all days, profit locks, other time stops, giveback at 0.75-1R | every one loses money in 2021-25; locks lose in every variant |
| Bias as a filter (yesterday's candle, last week's midpoint, weekly open, SMT) | 0.8-1.9 trades a week |
| Bias as a confluence point | the replacement trades lose (2021-25 PF 0.94-0.96) |
| Skip trending markets, VIX above 25, range block 1.2x, morning or afternoon only | under 2 trades a week or less profit |
| Full size in trending markets | a little more profit but more failed evals (2021-25 1-month fail 13.6%) |

## Worth more research (not for Sunday)

- **Size-down when two biases disagree** (the trade follows yesterday's candle AND is on the wrong side of last
  week's midpoint; about 1 trade in 5): 70% size raises PF in both periods (2026 3.48 → 3.62, 2021-25 1.09 → 1.12)
  and cuts drawdown, but costs 2026 $0.75k. **With the recommended breakeven change on top** (run
  `combo_betrend3_both07`):

  | | 2026 today | 2026 combo | 2021-25 today | 2021-25 combo | All years today | All years combo |
  |---|---:|---:|---:|---:|---:|---:|
  | PF | 3.48 | 3.52 | 1.09 | 1.18 | 1.32 | 1.41 |
  | Net | +$20.1k | +$19.4k | +$6.5k | +$12.7k | +$26.6k | +$32.0k |
  | Max drawdown | −$2.7k | −$2.4k | −$11.4k | −$10.1k | −$11.4k | −$10.1k |
  | Eval 1 month pass / fail | 30.5% / 0% | 30.5% / 0% | 8.8% / 9.6% | 7.7% / 6.7% | 12.2% / 8.0% | 11.0% / 5.6% |
  | Back-to-back passed / failed | 4 / 1 | 4 / 1 | 7 / 18 | 7 / 15 | 11 / 19 | 12 / 16 |

  Better in every 2021-25 year (2021 +$1.5k, 2022 +$3.1k, 2023 +$0.5k, 2024 +$0.1k, 2025 +$1.0k), 2026 −$0.75k. It
  fails the strict rule (2026 net lower), the size rule is not in the engine or the Pine script yet, it is sizing (the
  other researcher's area), and both biases were found on these same trades. Worth a proper out-of-sample check
  after Sunday, not a change for Sunday.
- **More trades a week:** "widest stop 80" lifts 2026 to 2.7 a week (88% of weeks with 2+) for −$0.9k.

## Checks

- **Leak:** none. The trade memory and the exit learner change no trade (`leakage-check.md`).
- **Engine:** new options `stop_buf_atr`, `w_pdc`, `w_pwmid` are off by default; the baseline replay re-run from
  scratch after the edits gives the same 768 trades.
- Write-ups: `stops.md`, `targets.md`, `management.md`, `bias-filters.md`, `leakage-check.md`. Every run is in the run
  library; `python tools/research_trade.py all` reproduces them.
