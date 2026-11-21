# Pre-registration: the premarket brief's day bias (written 2026-11-20 BEFORE any measurement)

Owner order: "thinking process before, and through trades". The brief shows ONE simple day bias. Rule 5 of the day:
any claim that it works must be pre-registered and measured on 2021-25 AND both 2026 halves, with hit rate and sample.
This file is committed before `tools/premarket_brief.py --measure` is run for the first time. Nothing below is changed
after seeing the numbers; any later idea is a NEW rule id with its own file.

## Data
`data/NQ_5m.csv` (TradingView CME NQ1! + NinjaTrader pushed bars; futures only), `data/VIX_1d.csv`, `data/news/events.csv`.
Periods: 2021-25 = first full day in the file .. 2025-12-31; 2026 H1 = 2026-01-01 .. 2026-06-30; 2026 H2 = 2026-07-01 .. last day.
Days: CME weekdays with a full RTH (09:30-16:00 ET); early-close days and days with a missing 07:55 or 09:30 bar are dropped.

## Rule B1 (primary): overnight drift
- At 08:00 ET: overnight move = close of the 07:55 bar - open of the 18:00 bar (the CME day's first bar).
- ATR = mean of the last 14 completed CME-day ranges (high - low, 18:00-17:00).
- Call UP if move >= +0.20 x ATR, DOWN if move <= -0.20 x ATR, else NONE.
- Outcome: RTH body = close of the 15:55 bar - open of the 09:30 bar. HIT if the sign matches the call (|body| < 1 pt dropped).

## Rule B2 (secondary): fade yesterday's candle (bias-filters.md idea, used as a day call here for the first time)
- Yesterday's CME day close vs its open: up -> call DOWN, down -> call UP, |close - open| < 0.10 x ATR -> NONE.
- Same outcome and hit definition as B1.

## Baselines and the bar for "works"
- Coin = 50%. Drift baseline = the share of up RTH bodies in the same period (a call that is always UP gets this).
- A rule "works" only if, in EACH of the three periods: n >= 40 calls, hit rate > 50% with a one-sided binomial p < 0.05,
  AND hit rate above the drift baseline of the called days (UP calls vs share up, DOWN calls vs share down).
- Two rules were tested, so p must be < 0.025 (Bonferroni) for the claim. Anything less = "no better than a coin":
  the brief then shows the call as CONTEXT ONLY.

## "Not reliable today" flags (shown with the call, decided now, measured as subgroups only)
Tier-1 (high) US release at or after 08:30 today; VIX band high (>= 30); early close; overnight data missing or stale.
VIX bands (fixed now): calm < 15, normal 15-20, elevated 20-30, high >= 30.
