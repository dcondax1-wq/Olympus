---
title: Risk summary: size down the two kinds of trades that lose
family: risk
date: 2026-10-17
status: adopt-candidate
summary: Recommendation: trade a quarter size (not half) in cold streaks and half size on late entries. On the same trades it makes 2021-25 +$11.5k instead of +$6.5k (PF 1.19 vs 1.09, max DD -$9.2k vs -$11.4k) and 2026 +$20.6k instead of +$20.1k (PF 4.12 vs 3.48), and cuts 1-month eval fails in 2021-25 from 9.6% to 5.2%. Every setup is still traded.
runs: baseline, risk_pkg_q25_late_live, risk_cold_q25, risk_pkg_half_late, risk_pkg_q25_late, risk_pkg_q25_hot8, risk_pkg_q25_prop1000, risk_sit_late_half, risk_hot8_150, risk_eval_prop1000, risk_usd1000, risk_usd600, risk_refoff, risk_ref30, loss_no_cold, loss_all_full
---

## The answer to "risking too much or not enough?"

Both, in different places.

- **It risks too much on two kinds of trade that lost money in both periods:**
  - trades taken during a cold streak
  - late entries, where the 15-minute trend had already turned the trade's way
- **On every other trade the risk is about right.** More risk (a higher $ amount, or less scaling on wide stops) makes more money in 2026, but it makes the drawdown and the eval fail rate grow faster than the profit. Less risk drops setups below 2 a week.

Over 2021-25 the strategy has no edge in R: 285R won, 287R lost. All of the 5-year profit comes from sizing, and most of it from the cold-streak filter.

- With the filter off, 2021-25 is -$2,542.
- With today's half size it is +$6,491.
- With the change below it is +$11,546.

## The recommendation (one change to sizing)

The engine still picks the micros from the stop, exactly as today. The live loop then multiplies them by one number, in the place where it applies the cold-streak half size now:

| situation at entry | multiplier | today |
|---|---:|---:|
| normal | x1 | x1 |
| cold streak (last 15 finished signals add up to 0R or less) | **x0.25** | x0.5 |
| late entry (the 15-minute trend already points the trade's way: the -1 item of the confluence score) | **x0.5** | x1 |
| both at once | **x0.125** | x0.5 |

- The result is rounded down, with a floor of 1 micro.
- Every setup is still taken and alerted, so it keeps 2+ setups a week.
- Nothing else changes: entries, stops, targets, the 1-trade-a-day limit, the $800 risk up to a 20-pt stop, and the trending-regime half size.
- **For the Pine script**, it is one line on top of the cold-streak half size that is being ported now:
  - micros = max(1, floor(micros × cold × late))
  - cold = 0.25 in a cold streak
  - late = 0.5 when the script's "15m already aligned" flag is on (`m15al`, already computed for the score)

## Full table: live vs recommended (same trades, costs included, exact live-loop replay)

| | 2026 live | 2026 recommended | 2026 cold x0.25 only | 2021-25 live | 2021-25 recommended | 2021-25 cold x0.25 only |
|---|---:|---:|---:|---:|---:|---:|
| Trades | 89 | 89 | 89 | 679 | 679 | 679 |
| Setups per week | 2.16 | 2.16 | 2.16 | 3.17 | 3.17 | 3.17 |
| Weeks with 2+ setups | 71% | 71% | 71% | 92% | 92% | 92% |
| Win rate | 24.7% | 24.7% | 24.7% | 20.5% | 20.5% | 20.5% |
| Profit factor | 3.48 | **4.12** | 3.55 | 1.09 | **1.19** | 1.16 |
| Net | +$20,111 | **+$20,583** | +$19,543 | +$6,491 | **+$11,546** | +$10,230 |
| Max drawdown | -$2,661 | **-$2,153** | -$2,333 | -$11,401 | **-$9,183** | -$9,158 |
| Worst day | -$554 | -$524 | -$554 | -$875 | -$875 | -$875 |
| Median $ at risk | $239 | $212 | $234 | $213 | $118 | $125 |
| Eval pass / fail within 2 weeks | 19.8% / 0.0% | 20.8% / 0.0% | 19.8% / 0.0% | 4.1% / 2.1% | 4.0% / 1.9% | 4.0% / 2.1% |
| Eval pass / fail within 1 month | 30.5% / 0.0% | 31.6% / 0.0% | 30.5% / 0.0% | 8.8% / 9.6% | 8.7% / **5.2%** | 8.5% / 7.5% |
| Eval pass / fail within 3 months | 53.7% / 19.7% | 53.7% / **0.0%** | 53.7% / 0.0% | 21.7% / 59.1% | **31.0% / 28.4%** | 27.6% / 36.0% |
| Back-to-back evals passed / failed | 4 / 1 | 4 / 1 | 4 / 1 | 7 / 18 | **7 / 10** | 7 / 12 |
| Back-to-back from 20 start days: passes / fails per year | 5.5 / 1.4 | 5.6 / 0.9 | 5.5 / 1.3 | 1.5 / 4.3 | 1.5 / **2.5** | 1.5 / 2.9 |
| Evals bought per pass | 1.25 | 1.16 | 1.23 | 3.89 | **2.63** | 2.91 |

- **MFFU Builder 50K** rules: $3,000 target, $2,000 end-of-day trailing max loss that locks at $50,100, soft $1,000 daily limit.
- **Rolling evals:** a new eval was started on every trading day.
- **Back-to-back:** a new eval starts the day after each pass or fail.
- **"20 start days":** the same back-to-back chain started on 20 different first days, so one lucky or unlucky first eval does not decide the comparison.

**By year (net, PF):**

| year | trades | live | recommended | cold x0.25 only |
|---|---:|---:|---:|---:|
| 2021 (Nov-Dec) | 26 | +$1,718 (1.52) | +$2,140 (1.75) | +$1,718 (1.52) |
| 2022 | 153 | -$6,951 (0.60) | -$4,377 (0.68) | -$5,196 (0.64) |
| 2023 | 193 | +$8,433 (1.40) | +$7,452 (1.42) | +$8,024 (1.44) |
| 2024 | 166 | +$1,737 (1.09) | +$4,555 (1.29) | +$3,717 (1.23) |
| 2025 | 141 | +$1,554 (1.11) | +$1,776 (1.16) | +$1,967 (1.17) |
| 2026 | 89 | +$20,111 (3.48) | +$20,583 (4.12) | +$19,543 (3.55) |

The recommended sizing is better in 5 of 6 years. 2023 is the exception: -$981 net, with a slightly higher PF.

## Why it works

**Cold-streak trades lose money in both periods.** The bot already trades them at half size, so the smaller size only cuts a leak.

| period | cold-streak trades | their avg R | other trades | their avg R |
|---|---:|---:|---:|---:|
| 2021-25 | 351 | -0.11R | 328 | +0.11R |
| 2026 | 28 | -0.10R | 61 | +0.59R |

- **A quarter beats a half at every setting tested** in 2021-25: lookback 10, 12, 15, 20 and 25 signals, and thresholds -2R, 0R and +2R.
- It is not a lucky setting: the smaller the size in a cold streak, the better the 5-year result. Sitting out entirely (skip mode) is best of all, but you rejected it because it paused trading for 14 weeks.

**Late entries lose too.** The engine already scores them -1, but it still takes them when the other items make up for it.

| period | late entries | avg R | other entries | avg R |
|---|---:|---:|---:|---:|
| 2021-25 | 91 | -0.06R | 588 | +0.01R |
| 2026 | 11 | -0.61R | 78 | +0.52R |

**How strong the late-entry evidence is:**
- **2021-25:** the difference is small and on its own would not prove anything.
- **2026:** it is clear, but it rests on 11 trades.
- **Noise check:** halving a random 13% of trades instead (same count) beats the late rule's gain about 1 time in 10 in 2021-25, and less than 1 time in 100 in 2026.
- **The mechanism makes sense.** When the 15m structure has already turned, part of the move is gone and the draw is closer.
- **Caveat:** this factor was flagged by the existing lessons table, which looks at both periods. 2026 is therefore not a perfectly untouched check for this half.
- **If only one part can be ported by Sunday, port the cold-streak quarter size.** It carries most of the 5-year gain: +$3.7k of +$5.1k, and 1-month eval fails 9.6% → 7.5%. It costs $568 in 2026.

## What you will notice

- **Many more 1-micro trades.**
  - 2021-25: 333 of 679 trades are at 1 micro (live: 205).
  - 2026: 34 of 89 (live: 24).
- **Cold streaks can last a long time.** The longest:
  - 18 weeks: Sep 2022 - Jan 2023
  - 16 weeks: Nov 2023 - Mar 2024
  - 15 weeks: Sep - Dec 2025
  - 13 weeks: May - Aug 2026
- **During a cold streak most trades are 1 micro**, about $100 at risk. The bot still trades and alerts every setup. Full size comes back automatically as soon as the shadow record adds back up above 0R (unchanged).
- **A strong winner during a cold streak makes less.**
  - Example: the +5R winner on 2026-08-07 would make $740 instead of $1,481 (3 micros instead of 6).
  - That is the price for losing much less in the bad stretches.

## What NOT to do (all tested, same trades, numbers in the runs)

| idea | 2026 net / PF | 2021-25 net / PF | 1-month eval fails 2021-25 | verdict |
|---|---:|---:|---:|---|
| live (reference) | +$20.1k / 3.48 | +$6.5k / 1.09 | 9.6% | |
| risk $1,000 instead of $800 | +$25.2k / 3.47 | +$6.9k / 1.07 | 20.9% | more fails, no 5-year gain |
| risk $600 | +$15.0k / 3.51 | +$1.5k / 1.03 | 1.5% | 2.09 setups a week in 2026, much less profit |
| $800 on every stop (no wide-stop scaling) | +$26.5k / 2.62 | +$16.6k / 1.13 | 37.4% | max DD -$16.8k, evals fail 4x as often |
| full risk up to a 30-pt stop | +$23.5k / 3.01 | +$8.7k / 1.09 | 20.7% | more fails |
| $800 on every trade (no de-risking at all) | +$26.2k / 2.10 | -$1.4k / 0.99 | 68.9% | loses over 5 years |
| cold-streak filter off | +$20.9k / 3.07 | -$2.5k / 0.98 | 27.4% | the filter is what makes 2021-25 positive |
| half size while the account is $1.5k below its high | +$14.4k / 3.53 | -$0.4k / 0.99 | 2.8% | cuts size right before the recoveries |
| half size after 3 losers in a row | +$18.1k / 3.63 | +$3.0k / 1.05 | 3.6% | worse in both |
| 1.5x right after a winner | +$20.8k / 3.05 | +$4.0k / 1.05 | 15.4% | worse in both |
| eval: size down once the cushion is under $1,000 | +$19.2k / 3.55 | +$2.9k / 1.05 | 2.1% | far fewer fails, but fewer passes per year (1.25 vs 1.5) and the result depends on the exact $ threshold |
| eval: press after the floor locks / bank the pass | about the same | about the same | 9-11% | changes almost nothing (the bot rarely risks more than what is left to the target) |

**Close calls, left out on purpose (no extra rules before Sunday):**
- **1.5x when the last 15 signals add up to +8R or more:**
  - beats the live rules in both periods: 2026 +$24.3k, 2021-25 +$9.0k
  - its extra profit comes from pressing size in hot streaks
  - more risk: 2026 max DD -$3.1k, 3-month eval fails 29% vs 20%
  - Run `risk_hot8_150`; combined with the quarter size, `risk_pkg_q25_hot8`.
- **Half size when VIX closed at 20 or higher:**
  - helped 2021-25: PF 1.14, max DD -$6.8k
  - changed nothing useful in 2026, which had only 12 such trades
  - Run `risk_sit_vix20_half`.
- **Half size after -2R in a week:**
  - helped 2021-25: +$7.9k
  - never triggered in 2026, so it has no out-of-sample evidence
  - Run `risk_week_brake2r`.

## How it was tested

- **Data and replay:** the exact live-loop replay on TradingView CME NQ1! 5-minute data, with commissions and slippage. This is the same 768 trades as the dashboard baseline.
- **Sizing:** redone from the engine's own rule. The engine's sizing stop was rebuilt for every trade, and all 768 give back the engine's micros exactly.
  - The post-hoc method matches engine replays with other settings ($1,000 risk, 30-pt reference stop, no wide-stop scaling) to within $650 of 5-year net. The risk-level and wide-stop runs use the engine replays themselves.
  - The recommended sizing was cross-checked against the dashboard's own sizing code (`runlib.size`) and is identical trade by trade.
- **No look-ahead:** a rule only sees the trade's setup and trades that had already finished.
- **Rules tried:**
  - about 60 runs in this family, saved in the run library (family "risk")
  - plus a 45-point cold-streak grid
  - plus 15 one-factor situational rules (picked on 2021-25, then checked on 2026)
  - plus a random-rule noise check
- **Reproduce:** `python tools/research_risk.py all` reruns everything; `python tools/research_risk.py recommend` prints this page's tables.
