# Kalshi edge, team B (structure and behaviour): NO EDGE FOUND

2026-11-10. Paper research only: no order, no key, no bot code touched. Scripts, data and results are in `research/kalshi_edge_B/`.

## Verdict in one line

I tested five ideas that are not "price band calibration" on about 28,000 settled crypto markets with real quotes. **None gives an edge that survives fees, a held-out block and a second asset.** One pocket looked real (and replicated across two assets) until I ran it on two months of data it had never seen: it vanished. Dropping the bot's losing bet kinds is the only thing the data supports.

## What data this used

The repo's own Kalshi data is thin (aggregates plus the last 40 trades), so I pulled Kalshi's PUBLIC market data (no key, read-only) and Coinbase public candles (spot proxy for the index Kalshi settles on).

| set | what | size |
|---|---|---|
| 15-minute up/down, BTC / ETH | settled markets with one quote per minute for the last 16 min | 2,900 each over 31 days, plus an older 2,900 each (32 more days) |
| 15-minute up/down, SOL / XRP | same | 2,900 each, 31 days |
| Hourly ladders, BTC / ETH | strikes within 1.2% of the final value, quotes for the last 30 min | 5,935 markets (327 hours) / 5,221 (492 hours) |
| Bot's own history | `research/kalshi/edge_tables.json` (feed 2026-11-04): 1,836 buys, 41 days, fees in | |

Rules used everywhere: taker buy at the ask, fee `0.07 x p x (1-p)` per contract (matches the bot's own P&L), edge = average profit per $1 contract after fees. Splits are by time: train first 55%, val next 20%, test last 25% (touched once). 95% intervals are cluster bootstraps (by day, or by hour for ladders) widened by a Wilson interval on the win rate. About 300 strategy cells were scored in total, so a lone "significant" cell is expected by luck: every candidate was therefore re-run on data it was not found on.

## Results

| candidate | n | edge per $1 after fees | 95% interval | held-out / second asset | verdict |
|---|---|---|---|---|---|
| 1. Strike ladder must be monotone (BTC hourly): buy yes low strike + no high strike when the pair costs under $1 | 300,000 pairs, 327 hours, 6 horizons | 0 violations, even before fees | n/a | n/a | **Nothing to harvest.** Ladders are consistent |
| 2a. Lognormal volatility model vs quoted price, BTC 15m (60 cells) | 2,900 mkts | best cell (8 min, gap >= 10c) +0.120 | [+0.034, +0.213] | test +0.115 (n 26); ETH same cell -0.005 (n 131); neighbours 6 and 10 min about 0 | **Rejected.** Market is the better forecaster (Brier 0.1265 vs model 0.1306 at 5 min); best cell is p about 0.06 against an efficient-market null |
| 2b. Same model, BTC hourly ladders (60 cells) | 5,935 mkts | no cell positive in train, val and test | | | **Rejected** |
| 3. Time of day (24 UTC hours, BTC 15m) | about 50 bets per hour | -0.10 to +0.10 | | pure noise: that range is what 50-bet cells give by luck | **No pattern** |
| 3b. CPI / FOMC / jobs windows | | | | one month holds one jobs print and one FOMC | **Cannot be tested** with 31 days |
| 4a. Late favourite, BTC hourly, 97-99c, 10 min out | 318 bets (234 hours), 1 loss | +0.019 | [+0.005, +0.022] | test +0.023 (n 64); **ETH same rule -0.009 (n 290, win 96.9%)**; 8 and 12 min neighbours +0.011, +0.004 | **Rejected** (lone cell, not replicated) |
| 4b. Late favourite, 15m, 95-97c, 8 min out | discovery: BTC 127, ETH 139 bets, 1 loss total | +0.031 BTC, +0.038 ETH | BTC [-0.005, +0.039], ETH [+0.011, +0.039] | looked replicated across two assets. **Frozen, then run on 4 unseen sets (BTC older, ETH older, SOL, XRP): 544 bets, 18 losses, win 96.7% vs break-even 96.2%, edge +0.005** | [-0.014, +0.020] **No edge.** Regression to the mean |
| 5. Maker (resting bid) on the favourite | 1,600 to 2,400 per horizon | upper bound (assumes every order fills) -0.006 to +0.002 on 15m, +0.010 to +0.018 on hourly | | when the fill proxy triggers (price came down to the bid): -0.04 to -0.38 | **No edge.** Fills arrive when the price moves against you |
| Late convergence, all 15m / hourly favourite bands | 20 + 12 cells | mostly within +-0.01 | straddle 0 | 90-95c is negative in 10 of 11 cells | **No edge**, matches the bot's own history |

Cost map (`costs.json`): a taker needs about 2.2c of true edge at 50c, 1.3c at 85c, 0.5c at 92c and 0.25c at 97c on 15m markets (hourly ladders cost 0.4c more: wider spread, 1c). The favourite end is cheap to trade but pays 3.5c to win and loses 96c, so it needs a win rate of 96.6% and shows exactly that, no more.

## What the bot should stop doing (bot's own bets, fees in, n shown)

| bet kind | n | result | evidence | action |
|---|---|---|---|---|
| Buying at 90-95c | 581 | -$248, ROI -4.7% | 95% interval -7.9% to -1.6% (proven); my independent test: hourly 5-min 90-95c -6.4c per $1 (n 140, proven); 15m 90-95c negative in all 5 horizons (n 179-471 each, none alone proven) | **Stop** |
| XRP (all strategies) | 192 | -$107, ROI -6.1% | interval -10.9% to -1.2% (proven) | **Stop** |
| "15-minute favourites" strategy | 1,131 | -$88.77 | win 95.0%, needs 96.6% (interval 93.5-96.1, entirely below) | **Stay off** |
| "Value" strategy | 40 | -$13.04 | win 75%; small n, not proven | pause |
| Solana, HYPE, BNB, Ethereum, Dogecoin | 142 / 122 / 77 / 165 / 165 | -$13 / -$12 / -$8 / -$5 / -$1 | intervals include 0 | watch, no proof either way |
| Flip-exit sell-backs, Sniper test, arb, arbx | 16 / 14 / 4 / 5 | -$8 / -$5 / -$3 / -$1 | n < 30: too few to judge | keep off |

Keep-as-is (not negative, not proven positive): Bitcoin (ROI +0.7%, interval +0.1 to +1.2%, n 623), "Late favourite (BTC hourly)" (+$16, n 182, 3 losses, indistinguishable from 0). Honest read: the only positive pockets in the bot's history are 95-99c entries on BTC, worth about +1% of stake, which is a rounding error against one loss of 96c. The bot's total after fees is -$62.82 on $21,602 staked (-0.3%).

## No edge found: what data would be needed

1. **Order-book depth and queue position** (not in public candles): needed to test whether resting orders get filled without adverse selection. Today only a fill proxy exists.
2. **12 or more months of 1-minute quotes** (Kalshi keeps candles for settled markets, I only pulled about 2 months of 15m and 2 weeks of hourly): needed for event windows (CPI, FOMC, jobs: about 12 of each per year) and for a held-out block large enough to confirm a 1-3c edge (a 1c edge on favourites needs thousands of bets to separate from one loss).
3. **The CF Benchmarks index itself** (I used Coinbase; the gap has a 0.026% standard deviation at expiry): needed for any model that trades the last 2-3 minutes.
4. **Non-crypto series** (economics, weather) with settled-market quotes: crypto 15m / hourly is the most efficient, most-watched corner; behaviour edges, if any, are more likely in thin markets, but then each trade is small.

## Run it

```
python research/kalshi_edge_B/study.py            # ladders, favourites, vol model, maker (needs data/, committed)
python research/kalshi_edge_B/study2.py KXBTC15M KXETH15M   # candidate deep dive + efficient-market null (NPERM=150)
python research/kalshi_edge_B/replicate_hourly.py          # BTC vs ETH hourly and 15m favourites
python research/kalshi_edge_B/test_frozen.py      # the frozen rule on unseen data (the decisive test)
python research/kalshi_edge_B/stop_bleed.py       # the bot's own bet kinds
python research/kalshi_edge_B/costs.py            # spread and fee cost map
python research/kalshi_edge_B/collect.py 15m KXBTC15M 2900   # refetch (public API, rate limited, about 15 min)
```
Results: `results.json`, `results_candidate.json`, `results_replication.json`, `results_frozen.json`, `stop_bleed.json`, `costs.json`.

Known limits: Coinbase is a proxy for the settlement index; quotes are minute-close bid/ask (no depth); hourly ladders keep only strikes within 1.2% of the final value (irrelevant at the favourite end, it only trims far tails); 15m data covers about 2 months, one market regime.

## Follow-up experiment design (not run, not deployed)

Goal: answer the two questions this study could not. (a) Can a resting (maker) order get filled without being picked off? (b) Do CPI / FOMC / jobs windows misprice?

- **What to record, free, for 3 months:** `tools/kalshi_kit/public/book_recorder.py` (stdlib, GET-only, no key, selftested with a stubbed API). Each minute it stores the top of book of every open market in BTC/ETH/SOL/XRP 15-minute and BTC/ETH hourly series, the full order book of the 12 mid-priced markets nearest expiry, and the public trade tape. Raw JSON lines, about 30-100 MB a day, stops itself at 4 GB. At most 40 requests a minute, one at a time, back-off on 429.
- **Where:** the Oracle VM, as its own cron or service, in a folder outside the bot. Not deployed by this change: the owner decides.
- **Maker question:** replay a resting bid on the favourite at each minute; a fill happens when a trade prints at or through our price while we are at the front by queue size from the book. Measure profit per fill after the 1.75% maker fee, and the same for fills that happen within 60 s of a spot move against us. Needs about 3 months and at least 500 simulated fills to separate a 1c edge.
- **Event windows:** list CPI, FOMC and jobs release times (about 12 each over 3 months is only 3 each: log 12 months, or accept that this stays exploratory), compare the model-vs-quote gap and the favourite win rate in the 30 minutes after each release against the same hours on other days.
- **Decision rule written now, before the data exists:** an idea counts only if the last third of the recording (never used to tune) shows a positive edge after fees whose 95% interval is above 0, on at least two assets, with n shown. Otherwise the answer is again "no edge found".
