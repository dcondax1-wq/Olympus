# The exact strategy the bot trades: Liquidity Engine (original, 1 trade/day) + cold-streak filter

Market: NQ futures, traded as MNQ micros ($2 per point), on 5-minute candles. All times are New York (ET).
Settings: engine defaults + `grade_sizing: false`, `conviction_step: 0`, `max_trades_day: 1`, `equity_filter: {lookback: 15, min_sum_r: 0}` (`live_model.json`).

## 1. Mark the liquidity
These are the pools the bot watches:
- **Major pools:**
  - prior day high/low
  - prior week high/low
  - overnight high/low
  - London high/low (02:00–05:00)
  - Asia high/low (20:00–00:00)
  - 1H swing highs/lows
  - any equal highs/lows (two levels within 6 points)
- **Minor pools:** 15-minute swing highs/lows.

## 2. Wait for a sweep
- From **08:00 ET**, price trades at least **1 tick through** a pool. That pool is now "taken".
- Sweeping a **low** arms a **long** setup; sweeping a **high** arms a **short**.
- The lowest price of the sweep (highest for shorts) is the **extreme**. If price keeps running, the extreme moves with it.
- The setup expires **60 minutes** after the last new extreme.

## 3. Entry trigger, only inside the killzones (09:30–11:30 and 13:30–15:30)
- **IFVG:** look at the leg that ran into the sweep (from its origin, up to 120 minutes before the extreme, to the extreme). Take the first fair value gap of at least **3 points** inside that leg. The trigger is the first candle whose **body closes back through that gap** (above it for longs, below it for shorts).
- **CISD:** used only when the leg has no fair value gap. The trigger is a candle closing back through the open of the run of candles that made the extreme.
- **Fill:** the open of the next 5-minute candle.

## 4. Confluence check (needs a score of at least 1)
- **+1** if the 1H trend agrees with the trade; **−1** if it's against it.
- **+1** if the sweep happened in **discount** of the 1H swing range for a long, or **premium** for a short.
- **+1** for a clean path: at most 1 unswept swing between entry and target. **−1** if there are 3 or more.
- **−1** if the 15-minute trend already points the trade's way (the entry is late).

## 5. Stop
- **Beyond the sweep extreme + 2 points.**
- **Minimum 10 points:** a tighter stop is widened to 10.
- **Maximum 60 points:** if the stop would be wider, use the far side of the inverted gap instead, provided that's 10–60 points. Otherwise **skip the trade**.

## 6. Target (draw on liquidity)
- The **nearest untaken major pool** that is **at least 1.5R away**. The exit order sits 1 tick in front of it.
- **Capped at 5R.** With no major pool in range, the target is **2R**.

## 7. Managing the trade
- **Breakeven:** at **+1R**, move the stop to entry + 1 tick.
- **Time stop:** if the trade hasn't reached **+0.5R within 30 minutes**, close it.
- **Giveback:** once it has been **+0.5R**, a candle closing back through the entry closes it.
- **Close everything by 15:55 ET.**
- **News:** close 5 minutes before a high-impact release.

## 8. Risk management
- **Risk $350 per trade.** Micros = $350 ÷ (stop points × $2), rounded down, max 40.
  - Typical: a 44-point stop × 3 micros ≈ $300.
- **Half size** in a trending market (10-day efficiency above 0.45).
- **Never risk more than 25% of the cushion** above the eval's trailing max-loss level.
- **1 trade per day.** Done for the day after a winner, or at **−$600** on the day.
- **No new entries:**
  - from 15 minutes before to 30 minutes after a high-impact US release (CPI, NFP, FOMC…)
  - after 13:00 on FOMC days
  - once the day's range has reached 1.6× the 20-day average

## 9. Cold-streak filter (sit out the bad stretches)
- The bot keeps a **shadow record of every signal** in rules 1–8, traded or not (`data/shadow_ledger.json`).
- Before each entry it adds up the R of the **last 15 signals that have already finished**.
- **Above 0R:** take the trade as normal.
- **0R or below:** don't take it. The signal is still tracked on paper, and alerts say "NOT TAKEN - cold-streak filter".
- Trading resumes **automatically** as soon as the last 15 signals add back up above 0R.
- Nothing else changes: same entries, stops, targets and risk. So the reward-to-risk of each trade stays the same.
- Why 15: chosen on 2021–24 data only, then checked on 2025 and 2026, which it never saw. Every lookback from 14 to 18 improves every period, so it isn't one lucky number.

## How it performed (verified Oct 17 2026: fresh rerun on TradingView NQ1! futures data, commissions and slippage included)

| Period | Version | Trades | Trades/week | Win % | Avg win / avg loss | Profit factor | Net | Max drawdown |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **2026 (Jan 2 – Oct 16)** | original | 93 | 2.3 | 26% | +2.82R / −0.47R | 2.41 | +$11,630 | −$3,147 |
| | **with filter (live)** | 59 | 1.4 | **32%** | +2.76R / −0.45R | **2.99** | **+$10,339** | **−$1,174** |
| 2025 (full year) | original | 148 | 2.9 | 22% | +1.92R / −0.51R | 1.32 | +$3,860 | −$3,362 |
| | **with filter** | 70 | 1.4 | **34%** | +1.80R / −0.53R | **1.95** | **+$5,906** | **−$1,226** |
| Oct 2021 – Dec 2024 | original | 562 | 3.5 | 22% | +2.04R / −0.53R | 0.96 | −$1,922 | −$8,900 |
| | **with filter** | 285 | 1.8 | 24% | +2.12R / −0.53R | **1.18** | **+$5,005** | **−$4,958** |
| **All 5 years** | original | 803 | 3.1 | 22% | +2.12R / −0.52R | 1.19 | +$13,568 | −$8,900 |
| | **with filter** | 414 | 1.6 | **27%** | +2.16R / −0.52R | **1.54** | **+$21,250** | **−$4,958** |

**2026 by month:**

| | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |
|---|---|---|---|---|---|---|---|---|---|---|
| original | +$894 | −$436 | +$2,684 | −$832 | −$790 | −$928 | −$340 | +$5,288 | +$4,125 | +$1,964 |
| with filter | +$283 | −$436 | +$1,016 | −$832 | paused | paused | paused | +$4,218 | +$4,125 | +$1,964 |

**MFFU 50K eval ($3k target, $2k trailing max loss).** A new eval was started on every trading day, then I checked where it stood 3 and 6 months (60 and 120 sessions) later:

| Started in | Version | Passed by 3 mo | Failed by 3 mo | Passed by 6 mo | Failed by 6 mo |
|---|---|---:|---:|---:|---:|
| 2026 | original | 29% | 27% | 8% | 90% |
| | **with filter** | 25% | **0%** | **43%** | **0%** |
| All 5 years | original | 19% | 34% | 27% | 65% |
| | **with filter** | 17% | **3%** | **37%** | **11%** |

Evals not counted as passed or failed were still running. Run back to back over all 5 years (a new eval the day after each pass or fail): filter 7 passes, 4 fails; original 8 passes, 12 fails.

*Correction:* an earlier version of this page said "83 passed, 0 failed" for 2026. That count let each eval run until the data ended, so it hid how slow passing is.

**What to expect:**
- It wins about 1 trade in 3. Winners are still big (about 2.8R); losers are still small (about 0.45R).
- **It rarely fails the eval, but it's slow.** A pass typically takes 2–5 months. Most of the profit comes in strong stretches (Aug–Oct 2026).
- **It goes quiet in bad stretches.** In 2026 it paused from May 1 to Aug 6, about 14 weeks with no real trades, while the signals kept being tracked on paper. It traded in 26 of 42 weeks: about 2 trades a week while active, and 1.4 a week on average overall.
- In 2021–24 the filter still had a $4,958 drawdown. That's over the $2,000 limit, so failing is possible in a bad year.
- Past results are not a promise. Paper-trade it before risking money.
