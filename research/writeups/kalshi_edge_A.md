---
title: Kalshi edge, team A (calibration / base rate): NO EDGE FOUND
family: kalshi
date: 2026-11-10
status: rejected - no edge found (calibration / base rate)
---

# Kalshi edge, team A (calibration / base rate): NO EDGE FOUND

2026-11-10. Research only: Kalshi's public market-data API (no key, read only), no order, the live bot and `engine/` untouched.
Reproduce: `python research/kalshi_edge_A/harvest.py` (about 6 min per series, cached), `python research/kalshi_edge_A/analyze.py`, `python research/kalshi_edge_A/check.py`.

## The answer

**No edge found.** Out of the 38 cells that were big enough to test (and 7 pre-written textbook ideas), none beat the noise on training data, and none is positive with a confidence interval above zero on the held-out last 14 days. Buying at the asking price, the whole market loses 2% to 21% per dollar to spread plus Kalshi's fee. The market is priced about right.

## What data

| Item | Value |
|---|---|
| Source | Kalshi public API: settled markets + 1-minute bid/ask candles (the earlier research only had the bot's own 1,836 favourite bets, which cannot show whether a price is wrong) |
| Markets | 13,452 settled markets, closing 2026-09-12 to 2026-11-10, random sample per series (1,500 each) |
| Series | BTC / ETH / SOL / XRP / DOGE 15-minute, BTC and ETH hourly above/below, S&P 500 and Nasdaq-100 hourly above/below |
| Quotes | yes ask and yes bid at 2-5, 10-30 and 60-240 minutes before close; a buy pays the ask (no side: 1 minus the yes bid); spread over 4c skipped |
| Fee | 0.07 x p x (1-p) per contract (the formula the bot's own P&L matched); Kalshi rounds up to the cent so real cost is slightly higher |
| Trade units | 38,114 (market x time bucket x side) |
| Split | Train = closes before 2026-10-27, Test (held out, read once) = 2026-10-27 to 2026-11-10 |
| Not covered | Sports, politics, weather, economics (not pulled: about 4 queries per second limit made 23 series too slow; weather and gold/oil/SOL/XRP hourly series are in the script, not run) |

## Results (everything after spread and fee, per $1 staked, 95% range = cluster bootstrap)

Trades that settle at the same minute in the same asset class are one cluster (one BTC move settles a whole strike ladder), so the ranges are wider than a naive count would give.

| Candidate | n (train / test) | Edge per $1, train | Edge per $1, test (held out) | Test 95% range | Verdict |
|---|---|---|---|---|---|
| Buy any side priced 90c or more | 4,285 / 1,355 | -0.2% | -0.7% | -2.0% to +0.5% | No edge |
| Buy any side priced 95c or more | 2,954 / 887 | +0.1% | -0.6% | -1.9% to +0.6% | No edge |
| Sell the longshot (buy NO, YES 10c or less), 2-5 min before close | 1,339 / 428 | -0.5% | -2.1% | -5.0% to +0.5% | No edge |
| Sell the longshot, 10-30 min before close | 598 / 221 | +1.1% | +0.7% | -2.4% to +3.3% | Watch only: same sign both blocks, range includes zero |
| 15-min crypto, side 90c+ | 3,119 / 941 | 0.0% | -0.4% | -1.9% to +1.1% | No edge |
| Hourly crypto above/below, side 90c+ | 544 / 172 | +0.1% | +1.3% | -1.0% to +3.0% | Too thin (172, 120 clusters), range includes zero |
| S&P/Nasdaq hourly, side 90c+ | 622 / 242 | -1.2% | -3.5% | -7.7% to +0.1% | Negative |
| Best cell by training t-stat: 15-min crypto, 2-5 min, buy NO, 50-70c | 277 / too few | +9.9% (t 2.1) | n/a | n/a | Below the multiple-testing bar (needs t above 3.23): noise |
| All 38 eligible cells (asset class x time x side x price band) | 38 cells | max t 2.1 | none carried | n/a | **0 carried, 0 survive** |
| Buying everything (control) | 12,000+ per block | -2.0% (15-min, near close) to -21% (index, near close) | same within 0.5 pt | n/a | Taker cost is the whole story |

Multiple testing: a market-calibrated simulation (300 runs, outcomes drawn at the market's own mid price, one random draw per settle-minute cluster so strike ladders move together) says the best of 38 cells reaches t = 3.23 by luck 5% of the time. The best real cell reached 2.1. The 7 pre-written ideas use a Bonferroni-adjusted range; none has a lower bound above zero.

## Where the market is a little wrong (before any cost)

At the mid price, with no spread and no fee:

| Where | Won vs priced (train / test) | Reading |
|---|---|---|
| 15-min crypto, YES priced 1-10c | -2.3 / -1.8 pts | Longshots are overpriced in both blocks (the classic longshot bias) |
| Hourly crypto, YES priced 1-10c | -0.9 / -0.8 pts | Same sign |
| Index, YES priced 1-10c | -1.3 / -1.4 pts | Same sign |
| 15-min crypto, 50-70c | -2.7 / -2.5 pts | Same sign, test range includes zero |
| Everything else | flips sign between blocks | Noise |

So the longshot bias is real in direction and about 1 to 2 points, but a taker pays 1 to 2 points of spread plus fee to collect it. A resting (maker) order at the mid with no fee and no adverse selection would earn it, but that is an upper bound I cannot verify: a resting order fills mostly when the price moves against it.

## What would be needed to find (or rule out) an edge

1. **More data**: the longshot-NO idea needs about 3,000 independent trades to shrink its range to about +/-1.5 points; today it has 819. Pull the other series in the script and run the harvest weekly (60 days of history is all the live API keeps; older markets are under `/historical`).
2. **Tick or trade-level data**: 1-minute bid/ask hides who crossed whom. With real fills I can test maker entries honestly (fill probability and adverse selection), the only route that could turn a 1 to 2 point bias into profit.
3. **Maker rebates or lower fees**: at 0.07 x p x (1-p) a 95c buy costs 0.33c, a 5c buy 0.33c; the spread is the bigger cost. Fee relief alone does not make the taker side positive.
4. **An outside signal**: pricing a crypto threshold needs spot and volatility; calibration of the price alone has nothing left to find.

## Honesty notes

- The cells were chosen on training data only, the last 14 days read once. The seven pooled ideas were written before the held-out block was read (they are the textbook favourite / longshot hypotheses, not picked from the cells).
- The random 1,500-market sample per series is not the whole population; samples are spread across all 59 days.
- Bid/ask at a 1-minute close is a quote, not a guaranteed fill; thin books would fill worse.
- The earlier finding "95c and above is +1.4% per $" came from the bot's own bets (no market-wide data). On the market-wide data it is +0.1% (train) and -0.6% (test): that pocket is not an edge, it is the bot's entry timing plus luck.

## Files

`research/kalshi_edge_A/`: `harvest.py` (public API pull), `analyze.py` (walk-forward + null), `check.py` (checks), `results.json` (every cell, calibration, pre-registered candidates), `edge_rules_A.json` (status no_edge_found, zero rules, one watch item with a paper forward-test config), `data/snap_*.jsonl` (the quotes, 3.6 MB).
Sibyl is unchanged (nothing to feed it).
