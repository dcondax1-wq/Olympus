# Kalshi edge, team C (weather, economics, daily index, other daily series): NO EDGE FOUND

2026-11-11. Research only. It used Kalshi's public market-data API (no key, read only), the free archived NWS forecasts from the Iowa Environmental Mesonet, and the repo's own ES/NQ futures bars. No orders were placed. The live bot, the server, the keys and `engine/` were not touched. Sibyl is unchanged because nothing passed, so there is nothing to feed it.

## The answer

**No edge found.** I looked at 262 cells in three families. None of them beat the noise bar on the training data, so none was carried forward. The obvious "outside signal" ideas lose money on the held-out data:

- **Weather:** buying whenever the official NWS forecast says a price is 5c or more too cheap loses **-11.7% per $1** on the held-out block. It loses -12.8% on 13 cities it never saw.
- **S&P 500 daily range:** a realised-volatility model built on ES futures gets no better than the market's own price.
- **Other series:** gas prices, FX and Rotten Tomatoes show nothing above the noise bar.

On these markets the crowd's price is a better forecast than the free public forecast.

## Data

| Item | Value |
|---|---|
| Markets | Every settled market, with hourly yes bid/ask quotes, from Kalshi's public API (live `/markets` plus `/historical`; batch candlesticks) |
| Weather | 7 big cities (NY, Chicago, Miami, Austin, LA, Denver, Philadelphia), daily highs, quotes from 2026-05-31 to 2026-11-09 (163 days, 23,822 trade units). Replication: 13 other cities (daily highs) and 7 cities' daily lows, 2026-09 to 11 (17,667 and 2,229 units) |
| Forecast | **A real archived forecast, not reconstructed.** NWS MOS (GFS MOS, NAM MOS, National Blend) for the exact station each market settles on, stamped with its run time. Evening decision (8 pm local, 29 h before close): 18Z/12Z run of the day before. Morning decision (7 am local, 18 h before close): 00Z run of the day. Each run was public by then. Bias and spread were fitted on the previous 60 settled days only |
| Naive baseline | Climatology (30-day mean) plus 0.7 x yesterday's high |
| S&P 500 / Nasdaq-100 daily close ranges | KXINX: 175 days, 2026-03 to 11 (8,883 units). KXNASDAQ100 (replication): 170 days (6,763 units). Strikes within 1.2% of the close before September; all strikes after. Model = realised 5-minute vol from `data/ES_5m.csv` / `NQ_5m.csv` (futures only), centred on the market's own median |
| Other series (n >= 300 quoted markets) | Daily US gas and diesel (AAA), USD/JPY and EUR/USD daily range, Rotten Tomatoes. Also downloaded but not used: Treasury 10Y, Spotify and NYC rain had no quotes; TSA, Netflix and weekly/monthly gas had fewer than 300 |
| Costs | Taker buys at the ask (no side: 1 minus the yes bid); fee 0.07 x p x (1-p); spread over 4c skipped |
| Protocol | Time split: first 75% of days train, last 25% held out and read once. Clusters = settlement day. Null = outcomes drawn from the market's own mid prices; a cell must beat the 95th percentile of the max t over all cells. Then a frozen rule is checked on unseen cities or on Nasdaq |

## Results (per $1 staked, after spread and fee; 95% range = cluster bootstrap by day)

| Candidate | n train | n test | Edge per $1, test (train) | Test 95% range | Replication (frozen, unseen) | Verdict |
|---|---|---|---|---|---|---|
| Weather: buy when the NWS forecast says 5c+ too cheap (7 cities) | 4,119 | 1,605 | **-11.7%** (-1.7%) | -18.9% to -4.5% | 13 other cities -12.8% (n 3,156); daily lows -12.0% (n 242) | **No edge, loses** |
| Weather: best training cell (evening, buy NO at 95-99c) | 1,624 | 554 | +0.2% (+0.8%) | -0.8% to +1.1% | other cities +0.2% (n 1,138); lows +0.6% (n 452) | Noise: t 2.04 vs 2.07 needed; about zero everywhere |
| Weather: buy everything (control) | | 6,022 | -3.2% | -3.3% to -3.2% | | Taker cost |
| S&P 500 daily: buy when the vol model says 6c+ too cheap | 139 | 18 | n/a (-7.7%) | n/a | Nasdaq-100 train days +19.1% (n 61) | **No edge**: negative in training, too few in test |
| S&P 500: best training cell (6 h out, YES 10-30c) | 205 | 45 | -22.1% (+16.9%) | -68% to +25% | Nasdaq-100 test days +38.1% (n 39) | Noise: t 1.14 vs 1.95 needed; sign flips |
| S&P 500 daily: buy everything (control) | | 4,066 | -11.9% | -13.3% to -10.6% | | Taker cost |
| Gas/FX/RT: best training cell (daily gas, buy NO at 95-99c, 3 h out) | 128 | 31 | +1.8% (+1.8%) | (+1.5% to +2.1%) | none | Noise: t 1.48 vs 1.72 needed. It won every bet so far (159 of 159). One loss at 98c wipes out about 50 wins, and the bootstrap range is too narrow because it never saw a loss. **Watch only** |
| US gas: momentum model (NO, 3c+ cheap, 12 h out) | 178 | 52 | +50.6% (-10.0%) | -58% to +178% | none | No edge: negative in training |

Cells looked at: 262 (weather 60, index 58, other 144). Carried past the noise bar: 0. Survived the held-out block: 0.

### Who forecasts better (Brier score, lower is better; held-out block)

| | Market mid | NWS MOS model | Naive (climatology + persistence) | Best mix (weight set on train) |
|---|---|---|---|---|
| Weather, 7 cities, evening | **0.089** | 0.117 | 0.168 | 0.089 (5% forecast) |
| Weather, 7 cities, morning | **0.079** | 0.110 | 0.167 | 0.080 |
| Weather, 13 other cities, morning | **0.082** | 0.112 | 0.167 | market only |
| S&P 500, 2 h before close | 0.0053 | 0.0047 | | |
| S&P 500, 6 h before close | **0.0136** | 0.0145 | | |

The NWS forecast is good: its error is about 1.9 F on the high, against 4.8 F for the naive model. But the market is better still, because traders already use that forecast and newer models. Mixing the forecast into the market price does not help out of sample. The S&P vol model is roughly level with the market: a little better at some hours and worse at others, not enough to pay a 1-2c spread.

## Economic releases (descriptive only: 4 to 13 events each, too few to test)

Each row buys the highest-priced bracket 24 h before the release (n = events):

| Series | Events | Favourite ask | Favourite won | Result per $1 |
|---|---|---|---|---|
| Fed decision | 8 | 57c | 63% | +8% (1 to 2 events from 0) |
| CPI m/m | 13 | 96c | 92% | -4% |
| CPI y/y | 12 | 98c | 83% | -15% |
| Core CPI | 13 | 94c | 92% | -3% |
| Payrolls | 13 | 96c | 85% | -12% |
| Unemployment | 13 | 97c | 100% | +3% |
| GDP | 4 | 97c | 100% | +3% |
| Jobless claims (weekly) | 47 | 86c | 77% | -11% |

The pattern is noise around zero, and slightly negative where there are more events. Telling a real 2-3c edge apart needs hundreds of releases, which means decades of data.

## What would change the answer

1. **A faster or better forecast than the crowd has.** Free MOS is about 4 to 6 hours old when you can use it, and the market already prices it. Only paid, high-resolution, frequently updated ensembles, or live station observations on the afternoon of the day (a different, intraday study), could plausibly beat it.
2. **Maker fills.** Every family loses 3% (weather) to 12% (S&P) per $1 to the spread plus fee when you take the ask. Resting orders could only be tested with order-book and trade-tape data (team B's `book_recorder.py` design).
3. **More history for the rare pockets.** The 95-99c "NO" pockets, in weather and in daily gas, sit at +0.2% to +1.8%. Separating +1% from zero at 98c needs about 3,000 independent bets. Weather markets keep more than a year of history, so that is reachable with the batch harvester if it is run longer.
4. **A cash-index feed for the daily S&P/Nasdaq markets.** I centred the model on the market's own median because there was no point-in-time SPX feed. So this tested only the width of the distribution, not its level. The futures files also end on 2026-10-16, so the last month of the test has no model.

## Caveats

- Quotes are hourly bid/ask closes, not fills. Thin books would fill worse.
- The weather discovery period, June to November, is a single season. The replication cities only have September to November.
- Index train and test hold different strike sets: before September only strikes within 1.2% of the close were fetched, to save API calls. Far strikes are near-certain and never pass the spread filter.
- The S&P index Brier scores in the test block are much lower because the test block includes many far strikes.

## Files and reruns

`research/kalshi_edge_C/`:

| File | What it is |
|---|---|
| `kc.py` | Polite public client |
| `harvest_c.py`, `harvest_all.sh` | Harvest (resumable) |
| `mos_fetch.py` | Archived NWS forecasts |
| `lib_c.py` | Stats, null and bootstrap |
| `weather.py`, `index_daily.py`, `other.py` | The three studies |
| `report.py` | Builds the table, `results.json` and `edge_rules_C.json` |
| `check.py` | Sanity checks |
| `peek_train.py` | Train-only viewer |
| `data/*.jsonl.gz`, `mos.json.gz` | Data, 2.6 MB |
| `results_*.json` | Results |

```
bash research/kalshi_edge_C/harvest_all.sh          # refetch (about 2 h, public API, cached and resumable)
python research/kalshi_edge_C/mos_fetch.py          # archived NWS MOS forecasts
python research/kalshi_edge_C/weather.py            # weather study
python research/kalshi_edge_C/index_daily.py        # S&P / Nasdaq daily
python research/kalshi_edge_C/other.py              # gas / FX / RT + economics table
python research/kalshi_edge_C/report.py             # table + edge_rules_C.json
python research/kalshi_edge_C/check.py              # checks (ALL OK)
```
