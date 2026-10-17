# The exact strategy the bot trades: Liquidity Engine, eval mode

Market: NQ futures, traded as MNQ micros ($2 per point), on 5-minute candles. All times are New York (ET).
Settings: engine defaults + `grade_sizing: false`, `conviction_step: 0`, `max_trades_day: 1`, `risk_usd: 650`, `dd_aware: false`, `equity_filter: {lookback: 15, min_sum_r: 0, cold_mode: half}` (`live_model.json`).

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
- **Risk $650 per trade.** Micros = $650 ÷ (stop points × $2), rounded down, max 40.
  - 2026 stops: median 44 points (most between 36 and 53, range 12–60). Size: median 6 micros (2–25). Dollar risk: median $595 (up to $655 with fees).
  - Typical: a 44-point stop × 7 micros ≈ $616.
- **Half size** in a trending market (10-day efficiency above 0.45).
- **1 trade per day.** Done for the day after a winner.
- **No new entries:**
  - from 15 minutes before to 30 minutes after a high-impact US release (CPI, NFP, FOMC…)
  - after 13:00 on FOMC days
  - once the day's range has reached 1.6× the 20-day average

## 9. Cold-streak filter (half size in bad stretches)
- The bot keeps a **shadow record of every signal** in rules 1–8 (`data/shadow_ledger.json`).
- Before each entry it adds up the R of the **last 15 signals that have already finished**.
- **Above 0R:** full size.
- **0R or below:** the trade is **still taken, at half size**. Alerts say "HALF SIZE - cold-streak filter".
- Full size comes back **automatically** as soon as the last 15 signals add back up above 0R.
- Every setup is traded, so it keeps 2+ setups a week. Only the size changes.

## How it performed (fresh rerun of the real engine on TradingView NQ1! futures data, commissions and slippage included)

| | 2026 (Jan 2 – Oct 16) | All 5 years (Oct 2021 – Oct 2026) |
|---|---:|---:|
| Trades | 97 | 824 |
| Setups per week | 2.4 (2+ in 92% of weeks) | 3.2 |
| Win rate | 26% | 22% |
| Profit factor | 2.55 | 1.30 |
| Net | +$21,359 | +$38,194 |
| Max drawdown | −$4,379 | −$13,389 |
| Worst day | −$651 | −$704 |

**MFFU 50K eval ($3k target, $2k trailing max loss).** A new eval was started on every trading day:

| | 2026 | All 5 years |
|---|---:|---:|
| Passed within 2 weeks | 25% | 12% |
| Failed within 2 weeks | 0% | 6% |
| Passed within 1 month | 37% | 19% |
| Failed within 1 month | 1% | 20% |
| Run back to back (new eval after each pass/fail) | 6 passed, 2 failed | 20 passed, 31 failed |
| Typical time to pass, when it passes | 14 trading days | 14 trading days |

**What to expect:**
- No setting passes "for sure" in 2 weeks. The $3k target is about 5R at $650; the $2k limit is about 3 full losses. A 2-week pass needs 2 big winners early. In 2026 that happened 1 time in 4.
- It wins about 1 trade in 4. Winners are big (often 2–5R), losers are about 1R or less.
- 2026 was a good year for this model. Over 5 years at this size, more evals failed than passed.
- The older, safer setup ($350, sit out cold streaks) almost never failed but took months to pass and traded 1.4 times a week. It's still available by setting `risk_usd: 350`, `dd_aware: true` and `cold_mode: skip`.
- Past results are not a promise. Paper-trade it before risking money.
