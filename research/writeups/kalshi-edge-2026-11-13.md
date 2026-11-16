---
title: Kalshi edges, team K1 (2026-11-13): NO EDGE FOUND
family: kalshi
date: 2026-11-13
status: rejected - no edge found (team K1)
---

# Kalshi edges, team K1 (2026-11-13): NO EDGE FOUND

Research only. Kalshi's public market-data API (no key, GET only, about 3 requests a second), the repo's CME futures
exports (`data/NQ_1m.csv`, `data/ES_5m.csv`, TradingView, futures only), CBOE VXN/VIX closes, and free weather data
(Iowa Environmental Mesonet station reports, NWS climate reports, api.weather.gov). No orders, no keys, nothing on the VM
touched. Earlier no-edge work was not redone: crypto (teams A, B), daily index ranges and the archived NWS forecast for
weather (team C), the bot's own bets (2026-11-04).

## The answer in one table

Edge per $1 = profit after Kalshi's fee (0.07 x p x (1-p), rounded up per contract; maker 0.0175) and after paying the
spread (taker buys at the ask). 95% range = cluster bootstrap (one cluster = one settle time / one settle day).
Train = before the split, test = after it, read once. $/month = test edge x $3 per trade (the go-live rule-1 size) x
trades per month at full market coverage.

| Idea | n train / test | Edge per $1 train (95%) | Edge per $1 test (95%) | $/month at $3 a trade | Verdict |
|---|---|---|---|---|---|
| Nasdaq-100 hourly above/below, futures fair-value model, 10 min before close | 102 / 46 | +5.8% (-6.9 to +18.8) | **-5.7%** (-33.6 to +26.9) | about -$4 | No edge |
| Same, 30 min before close | 115 / 48 | +0.2% (-10.2 to +10.3) | **-12.1%** (-35.2 to +13.7) | about -$8 | No edge |
| S&P 500 hourly above/below, same model, 10 min | 171 / 103 | -7.4% (-20.1 to +5.3) | -3.3% (-20.8 to +13.9) | about -$5 | No edge |
| S&P 500, 30 min | 103 / 42 | -1.0% (-14.9 to +12.3) | -2.3% (-22.4 to +15.9) | about -$1 | No edge |
| Control: buy every live YES at the ask, 30 min (test) | - / 399 NQ, 429 ES | | -7.4% NQ (-14.1 to -0.6), -3.8% ES (-10.0 to +2.2) | | The taker cost |
| Resting limit order 2c inside the spread, Nasdaq (best of 32 cells on train: 20 min, NO side) | 415 / 192 | -2.1% (-9.3 to +4.8) | **-10.7%** (-25.0 to +2.7) | about -$30 | No edge: adverse selection |
| Same, S&P 500 (best train cell, same settings) | 345 / 146 | +0.5% (-8.4 to +9.3) | **-14.1%** (-27.0 to -0.6) | about -$30 | No edge, loses |
| Weather: thermometer "lock" (high already above / below a bracket) still priced under 99c | 9 / 6 | -3.2% | -106% (all 6 lost) | n/a (too rare) | No edge: the market prices locks at 99-100c |
| Weather: model of how much more the high still rises after 1 pm | 6,593 / 9,216 quotes | -37.5% (-45.3 to -29.7) | **-42.8%** (-48.4 to -37.3) | loses about $1.30 per $3 trade | Market far better |

Splits: index train = 2026-01-02 to 06-30, test = 07-01 to 10-16 (the futures files end 10-16). Weather train = settle
days before 2026-09-15, test from 09-15 (team C's hourly quote snapshots, 7 cities).

## What each study did, in plain words

**1. Index fair value (Nasdaq-100 `KXNASDAQ100U`, S&P 500 `KXINXU`, hourly 10:00-16:00 ET).** The index level comes from
the futures at the decision minute minus the futures-minus-index gap seen at Kalshi's last settlement (Kalshi publishes the
value it settled on; the gap is only reused inside one futures contract). The chance of finishing above each strike comes
from a fat-tailed bell curve whose width is set by the last hour's realised futures volatility and the prior day's VXN/VIX;
all weights were fitted on the training half only. The fit chose realised vol x 1.5, no weight on VXN/VIX, a 3x wider
curve when the 9:30 cash open is inside the hour, and heavy tails. Kalshi quotes: 1-minute yes bid/ask for the last 66
minutes of about 9,800 markets (an even random sample of 16,715 chosen strikes near the money, 1,380 events per index;
the API rate limit stopped the rest).

Who forecasts better on the held-out half (Brier score, lower is better, only strikes with a live market):

| | 55 min | 30 min | 10 min |
|---|---|---|---|
| Nasdaq: market mid / model | **0.1103** / 0.1119 | **0.1317** / 0.1346 | **0.1104** / 0.1120 |
| S&P: market mid / model | **0.1034** / 0.1054 | **0.1128** / 0.1142 | **0.1201** / 0.1216 |

The market is a little better everywhere. The model looked slightly ahead on Nasdaq 10 minutes out in training (+5.8% per
$1), and that disappeared on the test half (-5.7%). With a 3-5c spread (median 5c Nasdaq, 2-3c S&P), a model has to be
clearly better than the crowd to pay for crossing it, and this one is not.

There are no hourly *range* markets in 2026 (the old `INXI` / `NASDAQ100I` series stopped in 2025); daily ranges were
team C's study (no edge).

**2. Weather (daily-high markets, 7 cities).** Team C already showed the archived NWS forecast (MOS / National Blend)
loses -11.7% per $1 against the market. K1 asked a different question: on the settle day, does the market lag what the
station has *already* recorded? It does not. Brackets the thermometer has already decided trade at 99-100c; the few
"locks" still priced lower were cases where our hourly station reading disagreed with the official climate report, and
the market was right every time. A model of how much the high still rises after 1 pm was far worse than the market
(Brier 0.210 vs 0.092 on the test half).

**3. Market making (resting a limit 1-2c inside the spread) on the hourly index markets.** 32 settings per index
(50/30/20/10 minutes before close, 1 or 2c inside, YES or NO side, resting 5 or 60 minutes). An order counts as filled
only when the market trades *through* its price afterwards. Fills come 35-90% of the time, but the filled contracts are
worth up to 8c (typically 2-6c) less than the mid at posting (adverse selection: you get filled when the price is moving against you), which is
more than the 1-3c you gain by not crossing the spread. Every best-on-train cell lost on the test half. If every order
were filled regardless, some cells would earn up to +44% per $1, which is exactly the gap the adverse selection takes.

## Honest limits

- Index: 1-minute candles, not the order book; about 59% of the chosen markets (random, even across days); S&P uses 5-minute
  futures bars (the 1-minute file is Nasdaq only). n per held-out cell is 40-100 trades, so a small edge (1-2% per $1)
  could hide inside the 95% ranges; a large one cannot.
- Maker fills are a proxy (no queue position, our order does not move the book). A real maker needs the order-book recorder
  of team B and months of data.
- Weather: no archive of the api.weather.gov forecast exists, so the forecast question gets forward evidence only (below).
- Futures exports end 2026-10-16; nothing after that was tested.

## What runs forward (paper only)

`tools/kalshi_paper.py` (stdlib, GET-only, no key; `tests/test_kalshi_paper.py`): every 15 minutes it settles open paper
signals, logs the frozen rules of `research/kalshi_edge_K1/paper_rules.json` (weather lock as a control, index model
OFF but parameterised), and keeps a forecast log: the NWS next-day high per city next to the market's quotes, settled
later with the official high. Ledger: `research/kalshi_edge_K1/paper/k1_paper.json` (or `--out`). The bar for real money
is in `docs/KALSHI_GO_LIVE.md`; today no rule meets it.

## Rerun

```
python research/kalshi_edge_K1/analyze_index.py --series KXNASDAQ100U   # and --series KXINXU (data committed, no network)
python research/kalshi_edge_K1/analyze_mm.py --series KXNASDAQ100U      # and KXINXU
python research/kalshi_edge_K1/weather_lock.py                          # needs cache/wobs.json.gz (weather_obs.py) + team C snapshots
python research/kalshi_edge_K1/harvest_index.py                         # refetch / extend the quotes (slow: rate-limited)
python -X utf8 -m tests.test_kalshi_paper
```
Results: `research/kalshi_edge_K1/results_index_*.json`, `results_mm_*.json`, `results_weather.json`.
