# The exact strategy the bot trades: Liquidity Engine, eval mode

Market: NQ futures, traded as MNQ micros ($2 per point), on 5-minute candles. All times are New York (ET).
Settings: engine defaults + `grade_sizing: false`, `conviction_step: 0`, `max_trades_day: 1`, `risk_usd: 800`, `risk_ref_stop: 20`, `dd_aware: false`, `use_fallback: false`, `be_at_r_trending: 3.0`, `memory_seed: false`, `equity_filter: {lookback: 15, min_sum_r: 0, cold_mode: half, cold_size: 0.25}`, `sizing: {late_mult: 0.5}` (`live_model.json`).

**Version:** locked 2026-10-17 (evening) for Monday 2026-10-19. Changes from the morning lock: quarter size in cold streaks (was half), half size on late entries (new), breakeven at +3R on trending days (was +1R). Research: `research/writeups/risk-summary.md`, `trade-construction-summary.md`; every experiment: `research/runs/`.

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

## 6. Target (draw on liquidity, always a real level)
- The **nearest untaken major pool** at least **1.5R** away: prior day high/low, prior week high/low, overnight, London and Asia highs/lows, 1H swing highs/lows, or equal highs/lows. The exit order sits 1 tick in front of it.
- **If that draw is more than 5R away**, the trade still aims at it, but profit is banked at **5R on the way**. Big draws like last week's high are rarely reached the same day.
- **No major pool in range: no trade.** There are no fixed-R targets without a draw.
- Tested and rejected:
  - holding for the far draw with no cap (2026 PF 2.21)
  - exiting at the last minor pool on the way (2026 PF 1.67)
  - draws limited to the day's reach (PF ~1.8)

## 7. Managing the trade
- **Breakeven:** at **+1R**, move the stop to entry + 1 tick. **On a trending day** (10-day efficiency above 0.45, the same test that halves the size) wait until **+3R**: reversal trades against a trend need room, and the giveback rule below still protects them.
- **Time stop:** if the trade hasn't reached **+0.5R within 30 minutes**, close it.
- **Giveback:** once it has been **+0.5R**, a candle closing back through the entry closes it.
- **Close everything by 15:55 ET.**
- **News:** close 5 minutes before a high-impact release.

## 8. Risk management (size follows the stop)
- **Risk $800 when the stop is 20 points or less.** With a wider stop the risk shrinks in proportion: a 40-pt stop risks $400, a 60-pt stop about $267.
  - Micros = risk ÷ (stop points × $2), rounded down, max 40.
  - Examples from 2026:
    - 13.75-pt stop: 28 micros, $770 at risk
    - 53-pt stop: 2 micros, about $212 at risk
- **Why:** over 5 years, stops under 20 pts averaged +0.34R per trade and 20–30 pts +0.10R, while 30–60 pts averaged about 0R.
- **Half size** in a trending market (10-day efficiency above 0.45).
- **Half size on a late entry:** when the 15-minute structure has already turned the trade's way at entry (the −1 item of the confluence score), part of the move is gone, so the size is halved. These trades lost money in both 2021–25 and 2026.
- The size rules multiply (cold streak × late entry), rounded down once, never below 1 micro.
- **1 trade per day.** Done for the day after a winner.
- **No new entries:**
  - from 15 minutes before to 30 minutes after a high-impact US release (CPI, NFP, FOMC…)
  - after 13:00 on FOMC days
  - once the day's range has reached 1.6× the 20-day average

## 9. Cold-streak filter (quarter size in bad stretches)
- The bot keeps a **shadow record of every signal** in rules 1–8 (`data/shadow_ledger.json`).
- Before each entry it adds up the R of the **last 15 signals that have already finished**.
- **Above 0R:** full size.
- **0R or below:** the trade is **still taken, at a quarter of the size** (was half until 2026-10-17: over 2021–25 the quarter size beat the half at every lookback and threshold tested). Alerts say "0.25x SIZE - cold-streak filter".
- Full size comes back **automatically** as soon as the last 15 signals add back up above 0R.
- Every setup is traded, so it keeps 2–4 setups a week. Only the size changes. Cold streaks can last 13–18 weeks; during them most trades are 1 micro (about $100 at risk).

## How it performed (fresh rerun of the live settings on TradingView NQ1! futures data, commissions and slippage included; `python tools/export_backtest.py`)

| | 2026 (Jan 2 – Oct 16) | 2021–25 | All 5 years (Nov 2021 – Oct 2026) |
|---|---:|---:|---:|
| Trades | 89 | 679 | 768 |
| Setups per week | 2.16 (2+ in 71% of weeks) | 3.17 (2+ in 92% of weeks) | 3.0 (2+ in 89% of weeks) |
| Win rate | 25.8% | 21.1% | 21.6% |
| Profit factor | 3.94 | 1.27 | 1.54 |
| Net | +$20,487 ($2,088/month) | +$16,379 ($321/month) | +$36,866 ($606/month) |
| Max drawdown | −$2,249 | −$9,265 | −$9,265 |

Before this lock (half size in cold streaks, breakeven at 1R on every day): 2026 +$20,111 (PF 3.48, max DD −$2,661), 2021–25 +$6,491 (PF 1.09, max DD −$11,401), all years +$26,602 (PF 1.32). Run `live_2026-10-17am` in the research library.

**MFFU 50K eval ($3k target, $2k trailing max loss).** A new eval was started on every trading day:

| | 2026 | 2021–25 | All 5 years |
|---|---:|---:|---:|
| Passed / failed within 2 weeks | 20.4% / 0.0% | 4.1% / 1.9% | 6.7% / 1.6% |
| Passed / failed within 1 month | 34.0% / 0.0% | 8.8% / 5.2% | 13.1% / 4.4% |
| Passes slower than 3 weeks · median sessions to pass | 53.8% · 18 | 81.2% · 32.5 | 75.9% · 31 |
| Back to back (new eval after each pass/fail) | 4 passed, 1 failed | 8 passed, 10 failed | 12 passed, 11 failed |

**Owner's eval-speed rule (2026-10-17):** an eval should be decided within 2 weeks and never take over 3 weeks to pass. At this size most passes still take 3 weeks or more. The researched "fast-eval" press (run `risk_fast_press1000`: $800 on any stop while the eval is less than $1,000 down) halves the time to pass and decides 27% / 15% of evals within 2 weeks (2026 / 2021–25) at the same cost per funded account, but fails about twice as many evals a year. It is built in (`sizing.press` in `live_model.json`) and OFF until the owner turns it on.

**Also tested and not adopted:**
- 10–15 pt stops (structural stops are rarely that tight; fixed 15-pt stops get wicked out and lose money)
- the ATM model with a sharp V (about 0.2–1.5 trades a week, about break-even)
- re-sweep, inducement, FBOS and RBOS as size rules (no edge that held in both 2021–25 and 2026; they are recorded on every trade and shown in the trade reports)

All variants are in `research/lab/variant_results.json`.

**What to expect:**
- No setting passes "for sure" in 2 weeks. At $800 the $3k target is about 4 full winners' worth of R, and the $2k limit is about 2–3 full losses.
- Cold streaks of 13–18 weeks happen; during them most trades are 1 micro. That is the rule working, not the bot being broken.
- It wins about 1 trade in 4. Winners are big (often 2–5R); wide-stop losers are small because size follows the stop.
- 2026 was a good year for this model. Over 5 years at this size, more back-to-back evals failed than passed.
- Past results are not a promise. Paper-trade it before risking money.
