# The exact strategy the bot trades: Liquidity Engine (original, 1 trade/day)

Market: NQ futures, traded as MNQ micros ($2 per point), on 5-minute candles. All times are New York (ET).
Settings: engine defaults + `grade_sizing: false`, `conviction_step: 0`, `max_trades_day: 1` (`live_model.json`).

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

## How it performed (TradingView NQ1! futures data, commissions and slippage included)

| Period | Trades | Trades/week | Win % | Profit factor | Net | Max drawdown | 50K eval pass rate (luck alone) |
|---|---:|---:|---:|---:|---:|---:|---|
| **2026 (Jan 2 – Oct 16)** | 93 | 2.3 | 26% | **2.41** | **+$11,630** | −$3,147 | **48%** (27%) |
| Apr–Dec 2025 | 118 | 3.2 | 20% | 1.14 | +$1,361 | −$3,362 | 12% (1%) |

**2026 by month:**

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |
|---|---|---|---|---|---|---|---|---|---|
| +$894 | −$436 | +$2,684 | −$832 | −$790 | −$928 | −$340 | +$5,288 | +$4,125 | +$1,964 |

**What to expect:**
- It wins about 1 trade in 4. The winners are big (often 2–5R), so most of the profit comes in strong trending stretches like Aug–Oct.
- Losing months are small, but there can be several in a row (Apr–Jul 2026).
- The worst drawdown ($3,147) is over the eval's $2,000 trailing limit. To stay inside it, risk about **$200–250 per trade**; profit scales down by the same proportion.
